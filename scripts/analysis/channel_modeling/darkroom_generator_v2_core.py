"""Core composition for the multi-elevation fixed-slot darkroom generator v2.

v2 preserves the validated v1 parent-model semantics while changing the output
contract: one request emits Low, Mid and High contexts together, and each
context always emits four structural rows per millisecond.  NLOS activation
still controls amplitude; inactive slots retain finite latent parameters and
are marked in sidecar data by the runner.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from . import darkroom_generator_core as _v1
except ImportError:
    from scripts.analysis.channel_modeling import darkroom_generator_core as _v1


FINAL_COLUMNS: tuple[str, ...] = (
    "ms",
    "SatelliteID",
    "NLOSPathID",
    "RelativeDelay",
    "RelativeDoppler",
    "RelativeAmplitude",
    "RelativePhase_rad",
)
BAND_SEQUENCE: tuple[tuple[str, str], ...] = (("LOW", "Low"), ("MID", "Mid"), ("HIGH", "High"))
ENVIRONMENTS = _v1.ENVIRONMENTS
V2_RUN_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class GeneratorV2Config:
    model_id: str
    generator_version: str
    sample_rate_hz: int
    time_step_ms: int
    path_parameter_block_ms: int
    environments: tuple[str, ...]
    elevation_bands: tuple[str, ...]
    source_payload: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.model_id != "darkroom-multi-elevation-four-slot-generator-v2":
            raise ValueError("unsupported v2 generator")
        if self.generator_version != "2.0.0":
            raise ValueError("unsupported v2 generator version")
        if self.sample_rate_hz != 10_230_000:
            raise ValueError("v2 supports only 10.23 MHz")
        if self.time_step_ms != 1 or self.path_parameter_block_ms != 40:
            raise ValueError("v2 requires 1 ms steps and 40 ms blocks")
        if self.environments != ENVIRONMENTS:
            raise ValueError("environment order is frozen")
        if self.elevation_bands != ("LOW", "MID", "HIGH"):
            raise ValueError("all three bands are required in fixed order")


@dataclass(frozen=True)
class GenerationV2Request:
    request_id: str
    simulation_id: str
    environment_class: str
    elevation_bands: tuple[str, ...]
    duration_ms: int
    master_seed: int
    activation_mode: str
    inactive_slot_parameter_policy: str
    lock_mapping_mode: str
    output_namespace: str


@dataclass(frozen=True)
class V2LatentSlot:
    slot_id: int
    delay_ns: float
    doppler_hz: float
    latent_amplitude: float
    phase_rad: float
    active: bool = False
    output_amplitude_base: float | None = None

    def __post_init__(self) -> None:
        if self.slot_id not in (1, 2, 3):
            raise ValueError("v2 NLOS slot id must be 1, 2 or 3")
        for value, name in (
            (self.delay_ns, "delay_ns"),
            (self.doppler_hz, "doppler_hz"),
            (self.latent_amplitude, "latent_amplitude"),
            (self.phase_rad, "phase_rad"),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"non-finite v2 slot {name}")
        if self.delay_ns <= 0.0 or self.latent_amplitude < 0.0:
            raise ValueError("v2 latent NLOS parameters are outside support")
        if self.output_amplitude_base is not None and (not math.isfinite(float(self.output_amplitude_base)) or self.output_amplitude_base < 0.0):
            raise ValueError("invalid v2 output amplitude base")


@dataclass(frozen=True)
class V2SimulationResult:
    final_rows: tuple[dict[str, Any], ...]
    path_block_rows: tuple[dict[str, Any], ...]
    path_slot_rows: tuple[dict[str, Any], ...]
    timeline_rows: tuple[dict[str, Any], ...]
    stream_rows: tuple[dict[str, Any], ...]
    support_summary: Mapping[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _resolve(project_root: Path, relative: str) -> Path:
    root = project_root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes project root: {relative}")
    return candidate


def load_v2_config(path: Path, project_root: Path) -> GeneratorV2Config:
    config_path = path.resolve()
    data = _read_json(config_path)
    if int(data.get("sample_rate_hz", 0)) != 10_230_000:
        raise ValueError("v2 supports only 10.23 MHz")
    if tuple(data.get("final_columns", FINAL_COLUMNS)) != FINAL_COLUMNS:
        raise ValueError("v2 final columns do not match the frozen contract")
    slot_policy = data.get("slot_policy", {})
    if slot_policy.get("inactive_nlos_policy") != "LATENT_PARAMETERS_WITH_ZERO_AMPLITUDE":
        raise ValueError("v2 inactive slot policy is not frozen")
    band_policy = data.get("band_policy", {})
    if tuple(band_policy.get("band_order", ())) != ("LOW", "MID", "HIGH"):
        raise ValueError("v2 band order is not frozen")
    execution_policy = data.get("execution_policy", {})
    forbidden = ("raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz")
    if any(execution_policy.get(key) is not False for key in forbidden):
        raise ValueError("v2 execution policy enables a forbidden action")
    parent = data.get("parent_generator_config")
    if not isinstance(parent, Mapping):
        raise ValueError("v2 parent generator config is missing")
    parent_path = _resolve(project_root, str(parent.get("relative_path", "")))
    if sha256_file(parent_path).lower() != str(parent.get("sha256", "")).lower():
        raise ValueError("v1 parent generator config hash mismatch")
    return GeneratorV2Config(
        model_id=str(data.get("generator_id", "")),
        generator_version=str(data.get("generator_version", "")),
        sample_rate_hz=int(data.get("sample_rate_hz", 0)),
        time_step_ms=int(data.get("time_step_ms", 0)),
        path_parameter_block_ms=int(data.get("path_parameter_block_ms", 0)),
        environments=tuple(data.get("environments", ())),
        elevation_bands=tuple(data.get("elevation_bands", ())),
        source_payload=data,
    )


def load_frozen_v2_parent_models(project_root: Path, config: GeneratorV2Config) -> Any:
    parent = config.source_payload["parent_generator_config"]
    v1_config_path = _resolve(project_root, str(parent["relative_path"]))
    v1_config = _v1.load_generator_config(v1_config_path, project_root)
    models = _v1.load_frozen_models(project_root, v1_config)
    if models.path_model_manifest_sha256 != str(config.source_payload["parent_model_manifest_sha256"]):
        raise ValueError("v2 path parent manifest provenance mismatch")
    return models


def validate_v2_request(payload: Mapping[str, Any], config: GeneratorV2Config) -> GenerationV2Request:
    required = {
        "request_id", "simulation_id", "generator_id", "environment_class", "elevation_bands",
        "duration_ms", "master_seed", "activation_mode", "inactive_slot_parameter_policy",
        "lock_mapping_mode", "new_only", "resume_allowed", "raw_iq_read", "matlab", "sage",
        "batch", "process_20_46_mhz", "output_namespace",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"missing v2 request fields: {','.join(missing)}")
    if str(payload["generator_id"]) != config.model_id:
        raise ValueError("v2 generator_id mismatch")
    if not str(payload["request_id"]).strip() or not str(payload["simulation_id"]).strip():
        raise ValueError("request_id and simulation_id must be non-empty")
    if payload["environment_class"] not in config.environments:
        raise ValueError("unsupported environment_class")
    bands = tuple(payload["elevation_bands"])
    if bands != config.elevation_bands:
        raise ValueError("elevation_bands must be exactly LOW,MID,HIGH")
    duration = payload["duration_ms"]
    seed = payload["master_seed"]
    if isinstance(duration, bool) or not isinstance(duration, (int, np.integer)) or int(duration) < 1:
        raise ValueError("duration_ms must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or int(seed) < 0:
        raise ValueError("master_seed must be a non-negative integer")
    if payload["activation_mode"] not in {"EMPIRICAL_CONFIRMED_SUPPORT", "CONDITIONAL_ACTIVE_STRESS"}:
        raise ValueError("unsupported activation_mode")
    if payload["activation_mode"] == "CONDITIONAL_ACTIVE_STRESS" and payload.get("request_purpose") not in {"QA", "STRESS"}:
        raise ValueError("active stress requires QA/STRESS request purpose")
    if payload["inactive_slot_parameter_policy"] != "LATENT_PARAMETERS_WITH_ZERO_AMPLITUDE":
        raise ValueError("inactive slot parameter policy mismatch")
    if payload["lock_mapping_mode"] not in {"EMPIRICAL_DIAGNOSTIC_PROXY", "FORCED_LOCK_LOSS_STRESS"}:
        raise ValueError("unsupported lock_mapping_mode")
    if payload["new_only"] is not True:
        raise ValueError("new_only must be true")
    if any(payload[key] is not False for key in ("resume_allowed", "raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz")):
        raise ValueError("v2 request enables a forbidden execution mode")
    output = str(payload["output_namespace"]).replace("\\", "/")
    if not output.startswith(V2_RUN_ROOT + "/") or ".." in output.split("/"):
        raise ValueError("unsafe v2 output namespace")
    if output.split("/")[-1] != str(payload["request_id"]):
        raise ValueError("output namespace must end with request_id")
    return GenerationV2Request(
        request_id=str(payload["request_id"]),
        simulation_id=str(payload["simulation_id"]),
        environment_class=str(payload["environment_class"]),
        elevation_bands=bands,
        duration_ms=int(duration),
        master_seed=int(seed),
        activation_mode=str(payload["activation_mode"]),
        inactive_slot_parameter_policy=str(payload["inactive_slot_parameter_policy"]),
        lock_mapping_mode=str(payload["lock_mapping_mode"]),
        output_namespace=output,
    )


def _legacy_request(request: GenerationV2Request, band: str) -> Any:
    return _v1.GenerationRequest(
        request_id=request.request_id,
        simulation_id=request.simulation_id,
        environment_class=request.environment_class,
        elevation_band=band,
        duration_ms=request.duration_ms,
        master_seed=request.master_seed,
        activation_mode=request.activation_mode,
        lock_mapping_mode=request.lock_mapping_mode,
        stress_floor_linear=None,
        output_namespace=request.output_namespace,
    )


def _rng(request: GenerationV2Request, band: str, scope_id: str, stream_name: str, registry: list[dict[str, Any]]) -> np.random.Generator:
    seed = _v1.derive_stream_seed(request.master_seed, request.simulation_id, request.environment_class, band, scope_id, stream_name)
    registry.append(
        {
            "simulation_id": request.simulation_id,
            "elevation_band": band,
            "scope_id": scope_id,
            "stream_name": stream_name,
            "seed_uint64": seed,
            "derivation": "sha256(canonical_json(master_seed,simulation_id,environment_class,elevation_band,scope_id,stream_name))[:8]",
        }
    )
    return np.random.default_rng(seed)


def apply_activation_mask(latent_slots: Sequence[V2LatentSlot], active_count: int) -> tuple[V2LatentSlot, ...]:
    if len(latent_slots) != 3 or active_count not in (0, 1, 2, 3):
        raise ValueError("v2 requires exactly three NLOS slots and K in 0..3")
    return tuple(
        replace(slot, active=(index < active_count), output_amplitude_base=(slot.latent_amplitude if index < active_count else 0.0))
        for index, slot in enumerate(latent_slots)
    )


def _sample_band_block(
    request: GenerationV2Request,
    config: GeneratorV2Config,
    models: Any,
    band: str,
    block_index: int,
    registry: list[dict[str, Any]],
) -> tuple[tuple[V2LatentSlot, ...], dict[str, Any], list[dict[str, Any]]]:
    key = f"{request.environment_class}|{band}"
    activation_model = models.activation_cells[key]
    occurrence_rng = _rng(request, band, f"block-{block_index:06d}", "block_activation_occurrence", registry)
    is_active = request.activation_mode == "CONDITIONAL_ACTIVE_STRESS" or bool(occurrence_rng.random() < activation_model.occupancy_mean)
    if is_active:
        multiplicity_rng = _rng(request, band, f"block-{block_index:06d}", "block_activation_multiplicity", registry)
        active_count = int(multiplicity_rng.choice(np.asarray(activation_model.multiplicity_categories), p=np.asarray(activation_model.multiplicity_probabilities)))
    else:
        active_count = 0
    path_rng = _rng(request, band, f"block-{block_index:06d}", "block_nlos_joint_parameters", registry)
    draws = _v1._sample_path_vector(models.path_cells[key], path_rng, 3)
    indexed = sorted(enumerate(draws), key=lambda item: (item[1][0], -item[1][2], item[1][1], item[0]))
    latent: list[V2LatentSlot] = []
    for slot_id, (_, draw) in enumerate(indexed, start=1):
        phase_rng = _rng(request, band, f"block-{block_index:06d}", f"block_nlos_phase_slot_{slot_id}", registry)
        latent.append(V2LatentSlot(slot_id, float(draw[0]), float(draw[1]), float(draw[2]), float(phase_rng.uniform(-np.pi, np.pi))))
    slots = apply_activation_mask(latent, active_count)
    mask = "".join("1" if slot.active else "0" for slot in slots)
    block_id = f"{band.lower()}-block-{block_index:06d}"
    block_rows: list[dict[str, Any]] = []
    for slot in slots:
        block_rows.append(
            {
                "block_id": block_id,
                "elevation_band": band,
                "SatelliteID": dict(BAND_SEQUENCE)[band],
                "block_start_ms": (block_index - 1) * config.path_parameter_block_ms + 1,
                "block_end_ms": block_index * config.path_parameter_block_ms,
                "NLOSPathID": slot.slot_id,
                "active": slot.active,
                "activation_mask": mask,
                "K_active": active_count,
                "latent_delay_ns": slot.delay_ns,
                "latent_doppler_hz": slot.doppler_hz,
                "latent_relative_amplitude": slot.latent_amplitude,
                "output_relative_amplitude_base": slot.output_amplitude_base,
                "phase_initial_rad": slot.phase_rad,
                "slot_status": "ACTIVE_PATH" if slot.active else "INACTIVE_LATENT_ZERO_AMPLITUDE",
                "occupancy_support_status": activation_model.occupancy_support_status,
                "multiplicity_support_status": activation_model.multiplicity_support_status,
                "path_parameter_support_status": activation_model.path_parameter_support_status,
                "prior_only": any(
                    status == "PRIOR_ONLY"
                    for status in (
                        activation_model.occupancy_support_status,
                        activation_model.multiplicity_support_status,
                        activation_model.path_parameter_support_status,
                    )
                ),
                "assumption_status": "LATENT_INACTIVE_PARAMETER_NOT_PHYSICAL_PATH",
            }
        )
    activation = {
        "block_id": block_id,
        "elevation_band": band,
        "z_active": is_active,
        "K_active": active_count,
        "activation_mask": mask,
        "occupancy_mean": activation_model.occupancy_mean,
        "occupancy_support_status": activation_model.occupancy_support_status,
        "multiplicity_support_status": activation_model.multiplicity_support_status,
        "path_parameter_support_status": activation_model.path_parameter_support_status,
        "prior_only": any(
            status == "PRIOR_ONLY"
            for status in (
                activation_model.occupancy_support_status,
                activation_model.multiplicity_support_status,
                activation_model.path_parameter_support_status,
            )
        ),
    }
    return slots, activation, block_rows


def _band_timeline(request: GenerationV2Request, models: Any, band: str, registry: list[dict[str, Any]]) -> tuple[np.ndarray, dict[str, Any]]:
    legacy_request = _legacy_request(request, band)
    legacy_registry: list[dict[str, Any]] = []
    gain_db, gain_linear, gain_meta = _v1.sample_common_gain_process(legacy_request, models, request.duration_ms, legacy_registry)
    lock_timeline = _v1._sample_lock_timeline(legacy_request, models, request.duration_ms, legacy_registry)
    fade_timeline = _v1._sample_ordinary_fade_timeline(legacy_request, models, request.duration_ms, lock_timeline, legacy_registry)
    for row in legacy_registry:
        normalized = dict(row)
        normalized.setdefault("elevation_band", band)
        registry.append(normalized)
    effective = gain_linear * fade_timeline["envelopes"] * lock_timeline["envelopes"]
    rows: list[dict[str, Any]] = []
    satellite_id = dict(BAND_SEQUENCE)[band]
    for index in range(request.duration_ms):
        rows.append(
            {
                "simulation_id": request.simulation_id,
                "ms": index + 1,
                "elevation_band": band,
                "SatelliteID": satellite_id,
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
                "assumption_flags": "ASSUMPTION_ONLY_ORDINARY_FADE_SHAPE;INTER_SATELLITE_CORRELATION_NOT_MODELED",
            }
        )
    return effective, {"rows": rows, "gain_meta": gain_meta, "lock": lock_timeline, "fade": fade_timeline}


def generate_v2_simulation(request: GenerationV2Request, config: GeneratorV2Config, models: Any) -> V2SimulationResult:
    registry: list[dict[str, Any]] = []
    timelines: dict[str, tuple[np.ndarray, dict[str, Any]]] = {
        band: _band_timeline(request, models, band, registry) for band, _ in BAND_SEQUENCE
    }
    final_rows: list[dict[str, Any]] = []
    path_block_rows: list[dict[str, Any]] = []
    path_slot_rows: list[dict[str, Any]] = []
    block_count = (request.duration_ms + config.path_parameter_block_ms - 1) // config.path_parameter_block_ms
    support_summary: dict[str, Any] = {
        "generator_id": config.model_id,
        "environment_class": request.environment_class,
        "elevation_bands": list(request.elevation_bands),
        "fixed_structural_slots_per_band": 4,
        "rows_per_ms": 12,
        "block_count": block_count,
        "parent_path_support_status": {},
        "parent_occupancy_support_status": {},
        "parent_multiplicity_support_status": {},
        "assumption_statuses": [
            "LATENT_INACTIVE_PARAMETER_NOT_PHYSICAL_PATH",
            "ASSUMPTION_ONLY_UNIFORM_INITIAL_PLUS_DOPPLER_CONTINUOUS",
            "INDEPENDENT_40MS_BLOCK_ASSUMPTION",
            "INTER_SATELLITE_CORRELATION_NOT_MODELED",
        ],
    }
    for band, satellite_id in BAND_SEQUENCE:
        key = f"{request.environment_class}|{band}"
        activation_model = models.activation_cells[key]
        support_summary["parent_path_support_status"][band] = models.path_cells[key].support_status
        support_summary["parent_occupancy_support_status"][band] = activation_model.occupancy_support_status
        support_summary["parent_multiplicity_support_status"][band] = activation_model.multiplicity_support_status
    phase_by_band: dict[str, float] = {}
    for band, _ in BAND_SEQUENCE:
        phase_rng = _rng(request, band, "simulation", "path0_initial_phase", registry)
        phase_by_band[band] = float(phase_rng.uniform(-np.pi, np.pi))
    block_cache: dict[tuple[str, int], tuple[V2LatentSlot, ...]] = {}
    for block_index in range(1, block_count + 1):
        for band, satellite_id in BAND_SEQUENCE:
            slots, activation, block_rows = _sample_band_block(request, config, models, band, block_index, registry)
            block_cache[(band, block_index)] = slots
            path_block_rows.extend(block_rows)
            block_start = (block_index - 1) * config.path_parameter_block_ms
            block_end = min(request.duration_ms, block_start + config.path_parameter_block_ms)
            local_phases = {slot.slot_id: slot.phase_rad for slot in slots}
            effective = timelines[band][0]
            for offset in range(block_end - block_start):
                index = block_start + offset
                ms = index + 1
                path0_phase = phase_by_band[band]
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
                phase_by_band[band] = _v1.evolve_phase_1ms(path0_phase, 0.0)
                for slot in slots:
                    current_phase = local_phases[slot.slot_id]
                    output_amplitude = float(effective[index] * float(slot.latent_amplitude)) if slot.active else 0.0
                    final_rows.append(
                        {
                            "ms": ms,
                            "SatelliteID": satellite_id,
                            "NLOSPathID": slot.slot_id,
                            "RelativeDelay": slot.delay_ns,
                            "RelativeDoppler": slot.doppler_hz,
                            "RelativeAmplitude": output_amplitude,
                            "RelativePhase_rad": current_phase,
                        }
                    )
                    path_slot_rows.append(
                        {
                            "simulation_id": request.simulation_id,
                            "ms": ms,
                            "elevation_band": band,
                            "SatelliteID": satellite_id,
                            "NLOSPathID": slot.slot_id,
                            "block_id": f"{band.lower()}-block-{block_index:06d}",
                            "active": slot.active,
                            "activation_mask": "".join("1" if item.active else "0" for item in slots),
                            "latent_delay_ns": slot.delay_ns,
                            "latent_doppler_hz": slot.doppler_hz,
                            "latent_relative_amplitude": slot.latent_amplitude,
                            "output_relative_amplitude": output_amplitude,
                            "RelativePhase_rad": current_phase,
                            "slot_status": "ACTIVE_PATH" if slot.active else "INACTIVE_LATENT_ZERO_AMPLITUDE",
                            "assumption_status": "LATENT_INACTIVE_PARAMETER_NOT_PHYSICAL_PATH",
                        }
                    )
                    local_phases[slot.slot_id] = _v1.evolve_phase_1ms(current_phase, slot.doppler_hz)
    final_rows.sort(key=lambda row: (int(row["ms"]), {"Low": 0, "Mid": 1, "High": 2}[row["SatelliteID"]], int(row["NLOSPathID"])))
    path_slot_rows.sort(
        key=lambda row: (
            int(row["ms"]),
            {"LOW": 0, "MID": 1, "HIGH": 2}[str(row["elevation_band"])],
            int(row["NLOSPathID"]),
        )
    )
    timeline_rows = tuple(
        timelines[band][1]["rows"][index]
        for index in range(request.duration_ms)
        for band, _ in BAND_SEQUENCE
    )
    if len(final_rows) != request.duration_ms * 12:
        raise AssertionError("v2 generator did not emit 12 rows per millisecond")
    return V2SimulationResult(
        final_rows=tuple(final_rows),
        path_block_rows=tuple(path_block_rows),
        path_slot_rows=tuple(path_slot_rows),
        timeline_rows=timeline_rows,
        stream_rows=tuple(registry),
        support_summary=support_summary,
    )


def _format(value: Any) -> str:
    if value is None:
        raise ValueError("v2 canonical table does not permit null values")
    if isinstance(value, bool):
        raise ValueError("boolean is not a canonical numeric value")
    if isinstance(value, (float, int, np.integer, np.floating)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("v2 canonical table contains non-finite value")
        return format(number, ".17g")
    if str(value) == "":
        raise ValueError("v2 canonical table contains an empty field")
    return str(value)


def format_v2_final_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FINAL_COLUMNS, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    expected_ms = 1
    expected_index = 0
    band_paths = [(satellite_id, path_id) for _, satellite_id in BAND_SEQUENCE for path_id in range(4)]
    for row in rows:
        normalized = {field: _format(row.get(field)) for field in FINAL_COLUMNS}
        if normalized["SatelliteID"] not in {"Low", "Mid", "High"}:
            raise ValueError("invalid SatelliteID")
        key = (int(normalized["ms"]), normalized["SatelliteID"], int(normalized["NLOSPathID"]))
        expected = (expected_ms, band_paths[expected_index][0], band_paths[expected_index][1])
        if key != expected:
            raise ValueError(f"v2 row order/identity mismatch: {key} != {expected}")
        if int(normalized["NLOSPathID"]) == 0 and float(normalized["RelativeAmplitude"]) <= 0.0:
            raise ValueError("path 0 amplitude must remain positive")
        if int(normalized["NLOSPathID"]) in (1, 2, 3) and float(normalized["RelativeDelay"]) <= 0.0:
            raise ValueError("NLOS delay must remain positive even for inactive latent slots")
        writer.writerow(normalized)
        expected_index += 1
        if expected_index == len(band_paths):
            expected_index = 0
            expected_ms += 1
    if expected_ms - 1 != (len(rows) // 12):
        raise ValueError("v2 row count is not a complete 12-row-per-ms sequence")
    return output.getvalue()
