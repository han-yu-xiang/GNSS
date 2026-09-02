"""Deterministic composition primitives for the darkroom four-path generator.

This module consumes frozen model artifacts only.  It deliberately contains no
raw-IQ, MATLAB, SAGE, production-pipeline, or event/gold lookup code.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy import stats


FINAL_COLUMNS: tuple[str, ...] = (
    "ms",
    "SatelliteID",
    "NLOSPathID",
    "RelativeDelay",
    "RelativeDoppler",
    "RelativeAmplitude",
    "RelativePhase_rad",
)

ENVIRONMENTS: tuple[str, ...] = (
    "Urban",
    "Special Reflective",
    "Mountain/Valley",
    "Highway/Open",
)
ELEVATION_BANDS: tuple[str, ...] = ("LOW", "MID", "HIGH")
SATELLITE_LABELS: dict[str, str] = {"LOW": "Low", "MID": "Mid", "HIGH": "High"}
MS_SECONDS = 0.001


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical bytes used by every request/stream hash."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def derive_stream_seed(
    master_seed: int,
    simulation_id: str,
    environment_class: str,
    elevation_band: str,
    scope_id: str,
    stream_name: str,
) -> int:
    """Derive an order-independent seed from the scientific identity."""

    if not isinstance(master_seed, (int, np.integer)) or int(master_seed) < 0:
        raise ValueError("master_seed must be a non-negative integer")
    if environment_class not in ENVIRONMENTS:
        raise ValueError(f"unknown environment_class: {environment_class}")
    if elevation_band not in ELEVATION_BANDS:
        raise ValueError(f"unknown elevation_band: {elevation_band}")
    if not simulation_id or not scope_id or not stream_name:
        raise ValueError("simulation_id, scope_id and stream_name must be non-empty")
    payload = canonical_json_bytes(
        {
            "master_seed": int(master_seed),
            "simulation_id": str(simulation_id),
            "environment_class": str(environment_class),
            "elevation_band": str(elevation_band),
            "scope_id": str(scope_id),
            "stream_name": str(stream_name),
        }
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def evolve_phase_1ms(phi_rad: float, relative_doppler_hz: float) -> float:
    phi = float(phi_rad)
    doppler = float(relative_doppler_hz)
    if not math.isfinite(phi) or not math.isfinite(doppler):
        raise ValueError("phase and Doppler must be finite")
    return (phi + 2.0 * math.pi * doppler * MS_SECONDS + math.pi) % (2.0 * math.pi) - math.pi


def raised_cosine_envelope(
    duration_ms: int,
    floor_linear: float,
    *,
    direction: str,
) -> np.ndarray:
    """Return inclusive endpoint samples for an entry or recovery envelope."""

    count = int(duration_ms)
    floor = float(floor_linear)
    if count < 1:
        raise ValueError("duration_ms must be positive")
    if not math.isfinite(floor) or floor <= 0.0 or floor > 1.0:
        raise ValueError("floor_linear must be in (0,1]")
    if direction not in {"entry", "recovery"}:
        raise ValueError("direction must be entry or recovery")
    u = np.arange(count + 1, dtype=float) / float(count)
    base = 0.5 * (1.0 - np.cos(np.pi * u))
    if direction == "entry":
        values = 1.0 - (1.0 - floor) * base
    else:
        values = floor + (1.0 - floor) * base
    return values


@dataclass(frozen=True)
class GeneratorConfig:
    model_id: str
    time_step_ms: int
    path_parameter_block_ms: int
    environments: tuple[str, ...]
    elevation_bands: tuple[str, ...]
    source_payload: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.model_id != "darkroom-four-path-generator-v1":
            raise ValueError("unsupported generator model_id")
        if self.time_step_ms != 1:
            raise ValueError("v1 requires a 1 ms time step")
        if self.path_parameter_block_ms != 40:
            raise ValueError("v1 requires 40 ms path-parameter blocks")
        if self.environments != ENVIRONMENTS:
            raise ValueError("environment order is frozen")
        if self.elevation_bands != ELEVATION_BANDS:
            raise ValueError("elevation-band order is frozen")


@dataclass(frozen=True)
class DistributionSpec:
    family: str
    parameters: Mapping[str, float]
    support_status: str
    parameter_source: str


@dataclass(frozen=True)
class PathCellModel:
    environment: str
    elevation_band: str
    distributions: Mapping[str, DistributionSpec]
    copula: np.ndarray
    support_status: str


@dataclass(frozen=True)
class ActivationCellModel:
    occupancy_mean: float
    occupancy_support_status: str
    multiplicity_categories: tuple[int, ...]
    multiplicity_probabilities: tuple[float, ...]
    multiplicity_support_status: str
    path_parameter_support_status: str


@dataclass(frozen=True)
class GainCellModel:
    family: str
    parameters: Mapping[str, float]
    tau_s: float
    gain_support_status: str
    tau_support_status: str


@dataclass(frozen=True)
class FadeModel:
    depth: DistributionSpec
    duration: DistributionSpec
    entry_rate_per_s: float
    support_status: str


@dataclass(frozen=True)
class LockModel:
    entry_probability_per_ms: float
    duration_shape: float
    duration_scale_s: float
    recovery_shape: float
    recovery_scale_s: float
    depth: DistributionSpec
    support_status: str


@dataclass(frozen=True)
class FrozenModels:
    path_cells: Mapping[str, PathCellModel]
    activation_cells: Mapping[str, ActivationCellModel]
    gain_cells: Mapping[str, GainCellModel]
    fade_models: Mapping[str, FadeModel]
    lock_models: Mapping[str, LockModel]
    path_model_manifest_sha256: str
    gain_model_manifest_sha256: str
    activation_model_manifest_sha256: str
    lock_model_manifest_sha256: str
    artifact_hashes: Mapping[str, str]


@dataclass(frozen=True)
class SimulationResult:
    final_rows: tuple[dict[str, Any], ...]
    path_block_rows: tuple[dict[str, Any], ...]
    timeline_rows: tuple[dict[str, Any], ...]
    stream_rows: tuple[dict[str, Any], ...]
    support_summary: Mapping[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric value for {field_name}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite numeric value for {field_name}")
    return number


def _resolve_relative(project_root: Path, relative_path: str) -> Path:
    root = project_root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"source path escapes project root: {relative_path}")
    return candidate


def _verify_declared_file(project_root: Path, relative_path: str, expected_sha256: str | None) -> tuple[Path, str]:
    path = _resolve_relative(project_root, relative_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256_file(path)
    if expected_sha256 is not None and actual.lower() != str(expected_sha256).lower():
        raise ValueError(f"hash mismatch for {relative_path}: {actual} != {expected_sha256}")
    return path, actual


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_generator_config(path: Path, project_root: Path) -> GeneratorConfig:
    config_path = path.resolve()
    data = _read_json(config_path)
    if int(data.get("sample_rate_hz", 0)) != 10_230_000:
        raise ValueError("v1 supports only 10.23 MHz")
    if tuple(data.get("final_columns", ())) != FINAL_COLUMNS:
        raise ValueError("final column order does not match the frozen contract")
    if data.get("execution_policy", {}).get("raw_iq_read") is not False:
        raise ValueError("generator config cannot enable raw IQ")
    if data.get("execution_policy", {}).get("matlab") is not False:
        raise ValueError("generator config cannot enable MATLAB")
    if data.get("execution_policy", {}).get("sage") is not False:
        raise ValueError("generator config cannot enable SAGE")
    if data.get("execution_policy", {}).get("batch") is not False:
        raise ValueError("generator config cannot enable batch")
    if data.get("execution_policy", {}).get("process_20_46_mhz") is not False:
        raise ValueError("generator config cannot enable 20.46 MHz")
    return GeneratorConfig(
        model_id=str(data.get("generator_id", "")),
        time_step_ms=int(data.get("time_step_ms", 0)),
        path_parameter_block_ms=int(data.get("path_parameter_block_ms", 0)),
        environments=tuple(data.get("environments", ())),
        elevation_bands=tuple(data.get("elevation_bands", ())),
        source_payload=data,
    )


def _parent_files(project_root: Path, parent_section: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, Path]]:
    hashes: dict[str, str] = {}
    paths: dict[str, Path] = {}
    for key, value in parent_section.items():
        if not key.endswith("_relative_path"):
            continue
        relative = str(value)
        hash_key = key.removesuffix("_relative_path") + "_sha256"
        expected = str(parent_section[hash_key]) if hash_key in parent_section else None
        path, actual = _verify_declared_file(project_root, relative, expected)
        paths[key] = path
        hashes[relative] = actual
    return hashes, paths


def _distribution_spec(row: Mapping[str, Any]) -> DistributionSpec:
    parameters = json.loads(str(row.get("fit_parameters_json", row.get("parameters", "{}"))))
    if not isinstance(parameters, dict):
        raise ValueError("distribution parameters must be an object")
    return DistributionSpec(
        family=str(row.get("family", "")),
        parameters={str(k): _float(v, str(k)) for k, v in parameters.items()},
        support_status=str(row.get("support_status", "UNKNOWN")),
        parameter_source=str(row.get("parameter_source", "UNKNOWN")),
    )


def _select_hierarchical_row(rows: Sequence[Mapping[str, str]], environment: str, band: str | None) -> Mapping[str, str]:
    def choose(level: str, env: str, elev: str) -> Mapping[str, str] | None:
        matches = [
            row for row in rows
            if row.get("level") == level
            and row.get("environment", "") == env
            and row.get("elevation_band", "") == elev
        ]
        if not matches:
            return None
        row = matches[0]
        if level == "cell" and int(float(row.get("direct_count", row.get("direct_event_count", "0")) or 0)) == 0:
            return None
        return row

    if band is not None:
        selected = choose("cell", environment, band)
        if selected is not None:
            return selected
    selected = choose("environment", environment, "")
    if selected is not None:
        return selected
    selected = choose("global", "", "")
    if selected is not None:
        return selected
    raise ValueError(f"no hierarchical parameter row for {environment}|{band}")


def _copula_from_row(row: Mapping[str, str]) -> np.ndarray:
    names = (
        "relative_delay_ns",
        "relative_doppler_hz",
        "relative_power_db",
    )
    matrix = np.array(
        [
            [_float(row[f"corr__{left}__{right}"], f"corr {left}/{right}") for right in names]
            for left in names
        ],
        dtype=float,
    )
    if not np.allclose(matrix, matrix.T, rtol=0.0, atol=1e-12):
        raise ValueError("path copula is not symmetric")
    eigenvalues = np.linalg.eigvalsh(matrix)
    if float(np.min(eigenvalues)) < -1e-8:
        raise ValueError("path copula is not positive semidefinite")
    return matrix


def load_frozen_models(project_root: Path, config: GeneratorConfig) -> FrozenModels:
    parents = config.source_payload.get("parents")
    if not isinstance(parents, Mapping):
        raise ValueError("generator config has no parent declarations")
    artifact_hashes: dict[str, str] = {}
    parent_paths: dict[str, dict[str, Path]] = {}
    for parent_name in ("path", "gain", "activation", "lock"):
        section = parents.get(parent_name)
        if not isinstance(section, Mapping):
            raise ValueError(f"missing parent section: {parent_name}")
        hashes, paths = _parent_files(project_root, section)
        artifact_hashes.update(hashes)
        parent_paths[parent_name] = paths

    protected = config.source_payload.get("protected_pipeline", {})
    pipeline_rel = str(protected.get("relative_path", "scripts/sage_pipeline/run_nav_sage_pipeline.m"))
    _, pipeline_hash = _verify_declared_file(project_root, pipeline_rel, str(protected.get("sha256")))
    artifact_hashes[pipeline_rel] = pipeline_hash

    path_manifest = _read_json(parent_paths["path"]["model_manifest_relative_path"])
    gain_manifest = _read_json(parent_paths["gain"]["model_manifest_relative_path"])
    activation_manifest = _read_json(parent_paths["activation"]["model_manifest_relative_path"])
    lock_manifest = _read_json(parent_paths["lock"]["model_manifest_relative_path"])
    for manifest, label in (
        (path_manifest, "path"),
        (gain_manifest, "gain"),
        (activation_manifest, "activation"),
        (lock_manifest, "lock"),
    ):
        if str(manifest.get("model_id", "")).strip() == "":
            raise ValueError(f"{label} parent manifest has no model_id")

    path_index_rows = _read_csv_rows(parent_paths["path"]["cell_index_relative_path"])
    path_distribution_rows = _read_csv_rows(parent_paths["path"]["cell_distribution_relative_path"])
    copula_rows = _read_csv_rows(parent_paths["path"]["copula_relative_path"])
    copulas = {
        str(row["environment"]): _copula_from_row(row)
        for row in copula_rows
        if row.get("scope") == "environment"
    }
    path_cells: dict[str, PathCellModel] = {}
    for index_row in path_index_rows:
        environment = str(index_row["environment"])
        band = str(index_row["elevation_band"])
        cell_id = str(index_row["cell_id"])
        rows = [row for row in path_distribution_rows if row.get("scope") == "cell" and row.get("scope_id") == cell_id]
        if {row.get("parameter") for row in rows} != {"relative_delay_ns", "relative_doppler_hz", "relative_power_db"}:
            raise ValueError(f"incomplete path cell distributions: {cell_id}")
        distributions = {str(row["parameter"]): _distribution_spec(row) for row in rows}
        if environment not in copulas:
            raise ValueError(f"missing environment copula: {environment}")
        path_cells[f"{environment}|{band}"] = PathCellModel(
            environment=environment,
            elevation_band=band,
            distributions=distributions,
            copula=copulas[environment],
            support_status=str(index_row.get("support_status", "UNKNOWN")),
        )

    activation_json = _read_json(parent_paths["activation"]["model_relative_path"])
    activation_cells: dict[str, ActivationCellModel] = {}
    occupancy_cells = activation_json.get("occupancy_hierarchy", {}).get("cells", {})
    multiplicity_cells = activation_json.get("multiplicity_hierarchy", {}).get("cells", {})
    for environment in config.environments:
        for band in config.elevation_bands:
            key = f"{environment}|{band}"
            occupancy = occupancy_cells.get(key)
            multiplicity = multiplicity_cells.get(key)
            if not isinstance(occupancy, Mapping) or not isinstance(multiplicity, Mapping):
                raise ValueError(f"missing activation cell: {key}")
            probabilities = tuple(_float(x, "multiplicity probability") for x in multiplicity.get("probabilities", ()))
            categories = tuple(int(x) for x in multiplicity.get("categories", ()))
            if categories != (1, 2, 3) or len(probabilities) != 3:
                raise ValueError(f"invalid multiplicity cell: {key}")
            if not math.isclose(sum(probabilities), 1.0, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(f"multiplicity probabilities do not sum to one: {key}")
            activation_cells[key] = ActivationCellModel(
                occupancy_mean=_float(occupancy.get("mean"), "occupancy mean"),
                occupancy_support_status=str(occupancy.get("support_status", "UNKNOWN")),
                multiplicity_categories=categories,
                multiplicity_probabilities=probabilities,
                multiplicity_support_status=str(multiplicity.get("support_status", "UNKNOWN")),
                path_parameter_support_status=path_cells[key].support_status,
            )

    gain_json = _read_json(parent_paths["gain"]["model_relative_path"])
    gain_marginals = gain_json.get("gain_marginals", {}).get("cells", {})
    temporal_rows = _read_csv_rows(parent_paths["gain"]["temporal_relative_path"])
    gain_cells: dict[str, GainCellModel] = {}
    for environment in config.environments:
        for band in config.elevation_bands:
            key = f"{environment}|{band}"
            cell = gain_marginals.get(key)
            if not isinstance(cell, Mapping):
                raise ValueError(f"missing gain cell: {key}")
            temporal = _select_hierarchical_row(temporal_rows, environment, band)
            gain_cells[key] = GainCellModel(
                family=str(cell.get("family")),
                parameters={str(k): _float(v, str(k)) for k, v in dict(cell.get("parameters", {})).items()},
                tau_s=_float(temporal.get("tau_s"), "tau_s"),
                gain_support_status=str(cell.get("parameter_source", "UNKNOWN")),
                tau_support_status=str(temporal.get("parameter_source", "UNKNOWN")),
            )

    fade_rows = _read_csv_rows(parent_paths["gain"]["fade_relative_path"])
    entry_rows = _read_csv_rows(parent_paths["gain"]["entry_rate_relative_path"])
    fade_models: dict[str, FadeModel] = {}
    for environment in config.environments:
        depth_row = _select_hierarchical_row([row for row in fade_rows if row.get("parameter") == "fade_depth_db"], environment, None)
        duration_row = _select_hierarchical_row([row for row in fade_rows if row.get("parameter") == "fade_duration_s"], environment, None)
        entry_row = _select_hierarchical_row(entry_rows, environment, None)
        depth = _distribution_spec(depth_row)
        duration = _distribution_spec(duration_row)
        fade_models[environment] = FadeModel(
            depth=depth,
            duration=duration,
            entry_rate_per_s=_float(entry_row.get("posterior_mean_rate_per_s"), "fade entry rate"),
            support_status=f"{depth.parameter_source}|{duration.parameter_source}|{entry_row.get('parameter_source', 'UNKNOWN')}",
        )

    lock_rows = _read_csv_rows(parent_paths["lock"]["lock_parameters_relative_path"])
    lock_json = _read_json(parent_paths["lock"]["model_relative_path"])
    recovery = lock_json.get("recovery", {}).get("environment_parameters", ())
    recovery_by_environment = {str(row.get("environment")): row for row in recovery if isinstance(row, Mapping)}
    lock_models: dict[str, LockModel] = {}
    for environment in config.environments:
        lock_row = next((row for row in lock_rows if row.get("environment_class") == environment), None)
        recovery_row = recovery_by_environment.get(environment)
        if lock_row is None or recovery_row is None:
            raise ValueError(f"missing lock/recovery parameters: {environment}")
        depth = fade_models[environment].depth
        lock_models[environment] = LockModel(
            entry_probability_per_ms=_float(lock_row.get("entry_probability_per_ms"), "lock entry probability"),
            duration_shape=_float(lock_row.get("parameter_1"), "lock duration shape"),
            duration_scale_s=_float(lock_row.get("parameter_2"), "lock duration scale"),
            recovery_shape=_float(recovery_row.get("gamma_shape"), "recovery shape"),
            recovery_scale_s=_float(recovery_row.get("gamma_scale_s"), "recovery scale"),
            depth=depth,
            support_status=f"{lock_row.get('support_status', 'UNKNOWN')}|{recovery_row.get('support_status', 'UNKNOWN')}",
        )

    return FrozenModels(
        path_cells=path_cells,
        activation_cells=activation_cells,
        gain_cells=gain_cells,
        fade_models=fade_models,
        lock_models=lock_models,
        path_model_manifest_sha256=str(parents["path"]["model_manifest_sha256"]),
        gain_model_manifest_sha256=str(parents["gain"]["model_manifest_sha256"]),
        activation_model_manifest_sha256=str(parents["activation"]["model_manifest_sha256"]),
        lock_model_manifest_sha256=str(parents["lock"]["model_manifest_sha256"]),
        artifact_hashes=artifact_hashes,
    )


@dataclass(frozen=True)
class GenerationRequest:
    request_id: str
    simulation_id: str
    environment_class: str
    elevation_band: str
    duration_ms: int
    master_seed: int
    activation_mode: str
    lock_mapping_mode: str
    stress_floor_linear: float | None
    output_namespace: str


@dataclass(frozen=True)
class BlockPath:
    slot_id: int
    active: bool
    delay_ns: float | None
    doppler_hz: float | None
    relative_amplitude: float | None

    def __post_init__(self) -> None:
        if self.slot_id not in (1, 2, 3):
            raise ValueError("NLOS slot_id must be 1, 2 or 3")
        if not self.active:
            if self.delay_ns is not None or self.doppler_hz is not None or self.relative_amplitude is not None:
                raise ValueError("inactive NLOS path must use null parameters")
            return
        if self.delay_ns is None or float(self.delay_ns) <= 0.0:
            raise ValueError("active NLOS delay must be positive")
        if self.doppler_hz is None or not math.isfinite(float(self.doppler_hz)):
            raise ValueError("active NLOS Doppler must be finite")
        if self.relative_amplitude is None or not math.isfinite(float(self.relative_amplitude)) or float(self.relative_amplitude) < 0.0:
            raise ValueError("active NLOS amplitude must be finite and non-negative")


def validate_generation_request(payload: Mapping[str, Any], config: GeneratorConfig) -> GenerationRequest:
    required = {
        "request_id",
        "simulation_id",
        "environment_class",
        "elevation_band",
        "duration_ms",
        "master_seed",
        "activation_mode",
        "lock_mapping_mode",
        "new_only",
        "resume_allowed",
        "raw_iq_read",
        "matlab",
        "sage",
        "batch",
        "process_20_46_mhz",
        "output_namespace",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"missing request fields: {','.join(missing)}")
    if not str(payload["request_id"]).strip() or not str(payload["simulation_id"]).strip():
        raise ValueError("request_id and simulation_id must be non-empty")
    if payload["environment_class"] not in config.environments:
        raise ValueError("unsupported environment_class")
    if payload["elevation_band"] not in config.elevation_bands:
        raise ValueError("unsupported elevation_band")
    duration = payload["duration_ms"]
    if isinstance(duration, bool) or not isinstance(duration, (int, np.integer)) or int(duration) < 1:
        raise ValueError("duration_ms must be a positive integer")
    seed = payload["master_seed"]
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or int(seed) < 0:
        raise ValueError("master_seed must be a non-negative integer")
    if payload["activation_mode"] not in {"EMPIRICAL_CONFIRMED_SUPPORT", "CONDITIONAL_ACTIVE_STRESS"}:
        raise ValueError("unsupported activation_mode")
    if payload["activation_mode"] == "CONDITIONAL_ACTIVE_STRESS" and payload.get("request_purpose") not in {"QA", "STRESS"}:
        raise ValueError("CONDITIONAL_ACTIVE_STRESS requires request_purpose QA or STRESS")
    if payload["lock_mapping_mode"] not in {"EMPIRICAL_DIAGNOSTIC_PROXY", "FORCED_LOCK_LOSS_STRESS"}:
        raise ValueError("unsupported lock_mapping_mode")
    for field in ("new_only",):
        if payload[field] is not True:
            raise ValueError(f"{field} must be true")
    for field in ("resume_allowed", "raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz"):
        if payload[field] is not False:
            raise ValueError(f"{field} must be false")
    output = str(payload["output_namespace"])
    if not output.startswith("dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_runs/"):
        raise ValueError("output_namespace is outside the generator run root")
    if ".." in output.replace("\\", "/").split("/"):
        raise ValueError("output_namespace may not contain parent traversal")
    if payload["lock_mapping_mode"] == "FORCED_LOCK_LOSS_STRESS":
        floor = payload.get("stress_floor_linear")
        if floor is None or not math.isfinite(float(floor)) or not 0.0 < float(floor) < 1.0:
            raise ValueError("stress mode requires stress_floor_linear in (0,1)")
    return GenerationRequest(
        request_id=str(payload["request_id"]),
        simulation_id=str(payload["simulation_id"]),
        environment_class=str(payload["environment_class"]),
        elevation_band=str(payload["elevation_band"]),
        duration_ms=int(duration),
        master_seed=int(seed),
        activation_mode=str(payload["activation_mode"]),
        lock_mapping_mode=str(payload["lock_mapping_mode"]),
        stress_floor_linear=(None if payload.get("stress_floor_linear") is None else float(payload["stress_floor_linear"])),
        output_namespace=output,
    )


def _rng_for(
    request: GenerationRequest,
    environment: str,
    band: str,
    scope_id: str,
    stream_name: str,
    registry: list[dict[str, Any]],
) -> np.random.Generator:
    seed = derive_stream_seed(
        request.master_seed,
        request.simulation_id,
        environment,
        band,
        scope_id,
        stream_name,
    )
    registry.append(
        {
            "simulation_id": request.simulation_id,
            "scope_id": scope_id,
            "stream_name": stream_name,
            "seed_uint64": seed,
            "derivation": "sha256(canonical_json(master_seed,simulation_id,environment_class,elevation_band,scope_id,stream_name))[:8]",
        }
    )
    return np.random.default_rng(seed)


def _ppf(spec: DistributionSpec, probabilities: np.ndarray) -> np.ndarray:
    values = np.asarray(probabilities, dtype=float)
    lower = np.nextafter(0.0, 1.0)
    upper = np.nextafter(1.0, 0.0)
    values = np.clip(values, lower, upper)
    p = spec.parameters
    if spec.family == "lognormal":
        return stats.lognorm.ppf(values, p["shape"], loc=p.get("loc", 0.0), scale=p["scale"])
    if spec.family == "gamma":
        return stats.gamma.ppf(values, p["shape"], loc=p.get("loc", 0.0), scale=p["scale"])
    if spec.family == "weibull":
        return stats.weibull_min.ppf(values, p["shape"], loc=p.get("loc", 0.0), scale=p["scale"])
    if spec.family == "student_t":
        return stats.t.ppf(values, p["df"], loc=p["loc"], scale=p["scale"])
    if spec.family == "normal":
        return stats.norm.ppf(values, loc=p["loc"], scale=p["scale"])
    if spec.family == "laplace":
        return stats.laplace.ppf(values, loc=p["loc"], scale=p["scale"])
    raise ValueError(f"unsupported distribution family: {spec.family}")


def _sample_distribution(spec: DistributionSpec, rng: np.random.Generator) -> float:
    p = spec.parameters
    if spec.family == "lognormal":
        value = rng.lognormal(mean=math.log(p["scale"]), sigma=p["shape"]) + p.get("loc", 0.0)
    elif spec.family == "gamma":
        value = rng.gamma(shape=p["shape"], scale=p["scale"]) + p.get("loc", 0.0)
    elif spec.family == "weibull":
        value = p.get("loc", 0.0) + p["scale"] * rng.weibull(p["shape"])
    elif spec.family == "student_t":
        value = p["loc"] + p["scale"] * rng.standard_t(p["df"])
    elif spec.family == "normal":
        value = rng.normal(p["loc"], p["scale"])
    elif spec.family == "laplace":
        value = rng.laplace(p["loc"], p["scale"])
    else:
        raise ValueError(f"unsupported distribution family: {spec.family}")
    if not math.isfinite(float(value)):
        raise ValueError(f"non-finite draw from {spec.family}")
    return float(value)


def _render_endpoint_envelope(duration_ms: int, floor_linear: float, direction: str) -> np.ndarray:
    count = int(duration_ms)
    if count < 1:
        raise ValueError("duration_ms must be positive")
    if count == 1:
        return np.array([floor_linear], dtype=float)
    u = np.linspace(0.0, 1.0, count, dtype=float)
    base = 0.5 * (1.0 - np.cos(np.pi * u))
    if direction == "entry":
        return 1.0 - (1.0 - floor_linear) * base
    if direction == "recovery":
        return floor_linear + (1.0 - floor_linear) * base
    raise ValueError("unknown envelope direction")


def _ordinary_fade_envelope(duration_ms: int, floor_linear: float) -> np.ndarray:
    count = int(duration_ms)
    if count < 1:
        raise ValueError("duration_ms must be positive")
    if count == 1:
        return np.array([floor_linear], dtype=float)
    entry_count = (count + 1) // 2
    recovery_count = count - entry_count + 1
    entry = _render_endpoint_envelope(entry_count, floor_linear, "entry")
    recovery = _render_endpoint_envelope(recovery_count, floor_linear, "recovery")
    return np.concatenate((entry, recovery[1:]))


def sample_common_gain_process(
    request: GenerationRequest,
    models: FrozenModels,
    duration_ms: int,
    registry: list[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    key = f"{request.environment_class}|{request.elevation_band}"
    model = models.gain_cells[key]
    rng = _rng_for(
        request,
        request.environment_class,
        request.elevation_band,
        "timeline",
        "common_gain_latent",
        registry,
    )
    count = int(duration_ms)
    latent = np.empty(count, dtype=float)
    rho = math.exp(-0.001 / max(model.tau_s, 1e-12))
    innovation = math.sqrt(max(1.0 - rho * rho, np.finfo(float).tiny))
    latent[0] = rng.normal()
    for index in range(1, count):
        latent[index] = rho * latent[index - 1] + innovation * rng.normal()
    probabilities = np.clip(stats.norm.cdf(latent), np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0))
    gain_db = _ppf(
        DistributionSpec(model.family, model.parameters, model.gain_support_status, model.gain_support_status),
        probabilities,
    )
    gain_linear = np.power(10.0, gain_db / 20.0)
    if not np.all(np.isfinite(gain_db)) or not np.all(np.isfinite(gain_linear)) or np.any(gain_linear <= 0.0):
        raise ValueError("common-gain process produced invalid values")
    return gain_db, gain_linear, {
        "rho_1ms": rho,
        "gain_support_status": model.gain_support_status,
        "tau_support_status": model.tau_support_status,
        "gain_family": model.family,
    }


def _sample_lock_timeline(
    request: GenerationRequest,
    models: FrozenModels,
    duration_ms: int,
    registry: list[dict[str, Any]],
) -> dict[str, Any]:
    model = models.lock_models[request.environment_class]
    count = int(duration_ms)
    states = ["TRACKED"] * count
    event_ids: list[str | None] = [None] * count
    envelopes = np.ones(count, dtype=float)
    phase_observable = [True] * count
    depth_source = [None] * count
    entry_rng = _rng_for(
        request,
        request.environment_class,
        request.elevation_band,
        "timeline",
        "lock_entry",
        registry,
    )
    event_catalog: list[dict[str, Any]] = []
    index = 0
    event_index = 0
    while index < count:
        if entry_rng.random() >= model.entry_probability_per_ms:
            index += 1
            continue
        event_index += 1
        event_id = f"lock-{event_index:06d}"
        duration_rng = _rng_for(
            request,
            request.environment_class,
            request.elevation_band,
            event_id,
            "lock_duration",
            registry,
        )
        lock_ms = max(20, int(math.ceil(float(duration_rng.gamma(model.duration_shape, model.duration_scale_s)) * 1000.0)))
        recovery_rng = _rng_for(
            request,
            request.environment_class,
            request.elevation_band,
            event_id,
            "lock_recovery_duration",
            registry,
        )
        recovery_ms = max(1, int(math.ceil(float(recovery_rng.gamma(model.recovery_shape, model.recovery_scale_s)) * 1000.0)))
        depth_rng = _rng_for(
            request,
            request.environment_class,
            request.elevation_band,
            event_id,
            "lock_depth_proxy",
            registry,
        )
        if request.lock_mapping_mode == "FORCED_LOCK_LOSS_STRESS":
            if request.stress_floor_linear is None:
                raise ValueError("stress mode requires a stress floor")
            floor = float(request.stress_floor_linear)
            depth_status = "ASSUMPTION_ONLY_USER_STRESS_FLOOR"
        else:
            depth_db = max(0.0, _sample_distribution(model.depth, depth_rng))
            floor = max(1e-12, 10.0 ** (-depth_db / 20.0))
            depth_status = "OBSERVABLE_FADE_PARENT_PROXY"
        entry_ms = min(20, lock_ms)
        sequence = (["FADING_TO_LOCK_BAD"] * entry_ms
                     + ["LOCK_BAD_HOLD"] * (lock_ms - entry_ms)
                     + ["RECOVERING"] * recovery_ms)
        local_envelope = np.concatenate((
            _render_endpoint_envelope(entry_ms, floor, "entry") if entry_ms else np.empty(0),
            np.full(lock_ms - entry_ms, floor, dtype=float),
            _render_endpoint_envelope(recovery_ms, floor, "recovery"),
        ))
        available = min(len(sequence), count - index)
        for offset in range(available):
            position = index + offset
            states[position] = sequence[offset]
            event_ids[position] = event_id
            envelopes[position] = float(local_envelope[offset])
            phase_observable[position] = False
            depth_source[position] = depth_status
        event_catalog.append(
            {
                "event_id": event_id,
                "start_ms": index + 1,
                "lock_duration_ms": lock_ms,
                "entry_ramp_ms": entry_ms,
                "recovery_duration_ms": recovery_ms,
                "floor_linear": floor,
                "depth_source": depth_status,
                "support_status": model.support_status,
                "truncated_at_record_end": available < len(sequence),
            }
        )
        index += available
    return {
        "states": states,
        "event_ids": event_ids,
        "envelopes": envelopes,
        "phase_observable": phase_observable,
        "depth_source": depth_source,
        "event_catalog": event_catalog,
        "support_status": model.support_status,
    }


def _sample_ordinary_fade_timeline(
    request: GenerationRequest,
    models: FrozenModels,
    duration_ms: int,
    lock_timeline: Mapping[str, Any],
    registry: list[dict[str, Any]],
) -> dict[str, Any]:
    model = models.fade_models[request.environment_class]
    count = int(duration_ms)
    states = ["NONE"] * count
    event_ids: list[str | None] = [None] * count
    envelopes = np.ones(count, dtype=float)
    entry_rng = _rng_for(
        request,
        request.environment_class,
        request.elevation_band,
        "timeline",
        "ordinary_fade_entry",
        registry,
    )
    event_catalog: list[dict[str, Any]] = []
    index = 0
    event_index = 0
    probability = 1.0 - math.exp(-max(0.0, model.entry_rate_per_s) / 1000.0)
    while index < count:
        if lock_timeline["states"][index] != "TRACKED" or entry_rng.random() >= probability:
            index += 1
            continue
        event_index += 1
        event_id = f"fade-{event_index:06d}"
        depth_rng = _rng_for(
            request,
            request.environment_class,
            request.elevation_band,
            event_id,
            "ordinary_fade_depth",
            registry,
        )
        duration_rng = _rng_for(
            request,
            request.environment_class,
            request.elevation_band,
            event_id,
            "ordinary_fade_duration",
            registry,
        )
        depth_db = max(0.0, _sample_distribution(model.depth, depth_rng))
        floor = max(1e-12, 10.0 ** (-depth_db / 20.0))
        duration_ms_draw = max(1, int(math.ceil(_sample_distribution(model.duration, duration_rng) * 1000.0)))
        planned_end = min(count, index + duration_ms_draw)
        lock_positions = [
            pos for pos in range(index, planned_end)
            if lock_timeline["states"][pos] != "TRACKED"
        ]
        actual_end = min(lock_positions) if lock_positions else planned_end
        if actual_end <= index:
            index += 1
            continue
        local = _ordinary_fade_envelope(duration_ms_draw, floor)[: actual_end - index]
        for offset, value in enumerate(local):
            position = index + offset
            states[position] = "ORDINARY_FADE"
            event_ids[position] = event_id
            envelopes[position] = float(value)
        event_catalog.append(
            {
                "event_id": event_id,
                "start_ms": index + 1,
                "planned_duration_ms": duration_ms_draw,
                "emitted_duration_ms": actual_end - index,
                "floor_linear": floor,
                "shape": "symmetric_raised_cosine",
                "superseded_by_lock": bool(lock_positions),
                "support_status": model.support_status,
            }
        )
        index = actual_end
    return {
        "states": states,
        "event_ids": event_ids,
        "envelopes": envelopes,
        "event_catalog": event_catalog,
        "support_status": model.support_status,
    }


def _sample_path_vector(cell: PathCellModel, rng: np.random.Generator, count: int) -> list[tuple[float, float, float]]:
    latent = rng.multivariate_normal(np.zeros(3, dtype=float), cell.copula, size=count, method="eigh")
    probabilities = np.clip(stats.norm.cdf(latent), np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0))
    names = ("relative_delay_ns", "relative_doppler_hz", "relative_power_db")
    arrays = {
        name: _ppf(cell.distributions[name], probabilities[:, index])
        for index, name in enumerate(names)
    }
    draws: list[tuple[float, float, float]] = []
    for index in range(count):
        delay = float(arrays["relative_delay_ns"][index])
        doppler = float(arrays["relative_doppler_hz"][index])
        power = float(arrays["relative_power_db"][index])
        if not math.isfinite(delay) or delay <= 0.0 or not math.isfinite(doppler) or not math.isfinite(power):
            raise ValueError("path distribution produced an invalid NLOS draw")
        draws.append((delay, doppler, float(10.0 ** (power / 20.0))))
    return draws


def _sample_block_paths(
    request: GenerationRequest,
    config: GeneratorConfig,
    models: FrozenModels,
    block_index: int,
    registry: list[dict[str, Any]],
) -> tuple[list[BlockPath], dict[str, Any], list[dict[str, Any]]]:
    key = f"{request.environment_class}|{request.elevation_band}"
    activation_model = models.activation_cells[key]
    occurrence_rng = _rng_for(
        request,
        request.environment_class,
        request.elevation_band,
        f"block-{block_index:06d}",
        "block_activation_occurrence",
        registry,
    )
    if request.activation_mode == "CONDITIONAL_ACTIVE_STRESS":
        active = True
    else:
        active = bool(occurrence_rng.random() < activation_model.occupancy_mean)
    if active:
        multiplicity_rng = _rng_for(
            request,
            request.environment_class,
            request.elevation_band,
            f"block-{block_index:06d}",
            "block_activation_multiplicity",
            registry,
        )
        k = int(multiplicity_rng.choice(np.asarray(activation_model.multiplicity_categories), p=np.asarray(activation_model.multiplicity_probabilities)))
    else:
        k = 0
    path_rng = _rng_for(
        request,
        request.environment_class,
        request.elevation_band,
        f"block-{block_index:06d}",
        "block_nlos_joint_parameters",
        registry,
    )
    draws = _sample_path_vector(models.path_cells[key], path_rng, k) if k else []
    indexed = sorted(enumerate(draws), key=lambda item: (item[1][0], -item[1][2], item[1][1], item[0]))
    slots: list[BlockPath] = []
    for slot_id in (1, 2, 3):
        if slot_id <= k:
            delay, doppler, amplitude = indexed[slot_id - 1][1]
            slots.append(BlockPath(slot_id, True, delay, doppler, amplitude))
        else:
            slots.append(BlockPath(slot_id, False, None, None, None))
    activation = {
        "block_id": f"block-{block_index:06d}",
        "z_active": active,
        "k_active": k,
        "occupancy_mean": activation_model.occupancy_mean,
        "occupancy_support_status": activation_model.occupancy_support_status,
        "multiplicity_support_status": activation_model.multiplicity_support_status,
        "path_parameter_support_status": activation_model.path_parameter_support_status,
        "is_prior_only": any(
            status == "PRIOR_ONLY"
            for status in (
                activation_model.occupancy_support_status,
                activation_model.multiplicity_support_status,
                activation_model.path_parameter_support_status,
            )
        ),
    }
    block_rows: list[dict[str, Any]] = []
    for slot in slots:
        block_rows.append(
            {
                "block_id": activation["block_id"],
                "block_start_ms": (block_index - 1) * config.path_parameter_block_ms + 1,
                "block_end_ms": block_index * config.path_parameter_block_ms,
                "NLOSPathID": slot.slot_id,
                "active": slot.active,
                "RelativeDelay": slot.delay_ns,
                "RelativeDoppler": slot.doppler_hz,
                "relative_amplitude_base": slot.relative_amplitude,
                "path_status": "ACTIVE_PATH" if slot.active else "INACTIVE_NO_PATH",
                "activation_mode": request.activation_mode,
                "occupancy_support_status": activation_model.occupancy_support_status,
                "multiplicity_support_status": activation_model.multiplicity_support_status,
                "path_parameter_support_status": activation_model.path_parameter_support_status,
                "prior_only": activation["is_prior_only"],
                "assumption_status": "INDEPENDENT_40MS_BLOCK_ASSUMPTION",
            }
        )
    return slots, activation, block_rows


def generate_simulation(
    request: GenerationRequest,
    config: GeneratorConfig,
    models: FrozenModels,
) -> SimulationResult:
    count = request.duration_ms
    registry: list[dict[str, Any]] = []
    gain_db, gain_linear, gain_meta = sample_common_gain_process(request, models, count, registry)
    lock_timeline = _sample_lock_timeline(request, models, count, registry)
    fade_timeline = _sample_ordinary_fade_timeline(request, models, count, lock_timeline, registry)
    effective = gain_linear * fade_timeline["envelopes"] * lock_timeline["envelopes"]
    phase0_rng = _rng_for(
        request,
        request.environment_class,
        request.elevation_band,
        "simulation",
        "path0_initial_phase",
        registry,
    )
    path0_phase = float(phase0_rng.uniform(-np.pi, np.pi))
    final_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    timeline_rows: list[dict[str, Any]] = []
    block_count = (count + config.path_parameter_block_ms - 1) // config.path_parameter_block_ms
    support_summary: dict[str, Any] = {
        "path_parameter_support_status": models.path_cells[f"{request.environment_class}|{request.elevation_band}"].support_status,
        "common_gain_support_status": gain_meta["gain_support_status"],
        "fade_support_status": models.fade_models[request.environment_class].support_status,
        "lock_support_status": models.lock_models[request.environment_class].support_status,
        "assumption_statuses": [
            "ASSUMPTION_ONLY_UNIFORM_INITIAL_PLUS_DOPPLER_CONTINUOUS",
            "ASSUMPTION_ONLY_ORDINARY_FADE_SHAPE",
            "INDEPENDENT_40MS_BLOCK_ASSUMPTION",
        ],
    }
    for block_index in range(1, block_count + 1):
        slots, activation, current_block_rows = _sample_block_paths(request, config, models, block_index, registry)
        block_start = (block_index - 1) * config.path_parameter_block_ms
        block_end = min(count, block_start + config.path_parameter_block_ms)
        phase_by_slot: dict[int, float | None] = {1: None, 2: None, 3: None}
        for slot in slots:
            if slot.active:
                phase_rng = _rng_for(
                    request,
                    request.environment_class,
                    request.elevation_band,
                    f"block-{block_index:06d}",
                    f"block_nlos_phase_slot_{slot.slot_id}",
                    registry,
                )
                phase_by_slot[slot.slot_id] = float(phase_rng.uniform(-np.pi, np.pi))
        for row in current_block_rows:
            row["phase_initial_rad"] = phase_by_slot.get(int(row["NLOSPathID"]))
        block_rows.extend(current_block_rows)
        for offset in range(block_end - block_start):
            index = block_start + offset
            ms = index + 1
            satellite_id = SATELLITE_LABELS[request.elevation_band]
            final_rows.append(
                {
                    "ms": ms,
                    "SatelliteID": satellite_id,
                    "NLOSPathID": 0,
                    "RelativeDelay": 0.0,
                    "RelativeDoppler": 0.0,
                    "RelativeAmplitude": float(effective[index]),
                    "RelativePhase_rad": path0_phase,
                }
            )
            for slot in slots:
                if slot.active:
                    phase = phase_by_slot[slot.slot_id]
                    assert phase is not None
                    amplitude = float(effective[index] * float(slot.relative_amplitude))
                    final_rows.append(
                        {
                            "ms": ms,
                            "SatelliteID": satellite_id,
                            "NLOSPathID": slot.slot_id,
                            "RelativeDelay": float(slot.delay_ns),
                            "RelativeDoppler": float(slot.doppler_hz),
                            "RelativeAmplitude": amplitude,
                            "RelativePhase_rad": phase,
                        }
                    )
                    phase_by_slot[slot.slot_id] = evolve_phase_1ms(phase, float(slot.doppler_hz))
                else:
                    final_rows.append(
                        {
                            "ms": ms,
                            "SatelliteID": satellite_id,
                            "NLOSPathID": slot.slot_id,
                            "RelativeDelay": None,
                            "RelativeDoppler": None,
                            "RelativeAmplitude": 0.0,
                            "RelativePhase_rad": None,
                        }
                    )
            path0_phase = evolve_phase_1ms(path0_phase, 0.0)
            timeline_rows.append(
                {
                    "simulation_id": request.simulation_id,
                    "ms": ms,
                    "environment_class": request.environment_class,
                    "elevation_band": request.elevation_band,
                    "common_gain_db": float(gain_db[index]),
                    "common_gain_linear": float(gain_linear[index]),
                    "ordinary_fade_state": fade_timeline["states"][index],
                    "ordinary_fade_event_id": fade_timeline["event_ids"][index],
                    "ordinary_fade_envelope_linear": float(fade_timeline["envelopes"][index]),
                    "lock_state": lock_timeline["states"][index],
                    "lock_event_id": lock_timeline["event_ids"][index],
                    "lock_envelope_linear": float(lock_timeline["envelopes"][index]),
                    "effective_common_gain_linear": float(effective[index]),
                    "phase_observable": lock_timeline["phase_observable"][index],
                    "gain_support_status": gain_meta["gain_support_status"],
                    "fade_support_status": models.fade_models[request.environment_class].support_status,
                    "lock_support_status": models.lock_models[request.environment_class].support_status,
                    "assumption_flags": ";".join(support_summary["assumption_statuses"]),
                }
            )
    if len(final_rows) != count * 4:
        raise AssertionError("generator did not emit four rows per millisecond")
    stream_rows = tuple(registry)
    return SimulationResult(
        final_rows=tuple(final_rows),
        path_block_rows=tuple(block_rows),
        timeline_rows=tuple(timeline_rows),
        stream_rows=stream_rows,
        support_summary=support_summary | {"block_count": block_count},
    )


def _format_number(value: float) -> str:
    if not math.isfinite(float(value)):
        raise ValueError("final table cannot contain non-finite numbers")
    return format(float(value), ".17g")


def format_final_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FINAL_COLUMNS, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    previous: tuple[int, int] | None = None
    for row in rows:
        normalized: dict[str, Any] = {}
        for field in FINAL_COLUMNS:
            value = row.get(field)
            if value is None:
                normalized[field] = ""
            elif field in {"ms", "NLOSPathID"}:
                normalized[field] = str(int(value))
            elif field == "SatelliteID":
                if str(value) not in {"Low", "Mid", "High"}:
                    raise ValueError("SatelliteID must be Low, Mid or High")
                normalized[field] = str(value)
            else:
                normalized[field] = _format_number(float(value))
        key = (int(normalized["ms"]), int(normalized["NLOSPathID"]))
        if previous is not None and key <= previous:
            raise ValueError("final rows must be strictly ordered by ms,NLOSPathID")
        previous = key
        writer.writerow(normalized)
    return output.getvalue()
