"""Auditable fixed-three-NLOS-slot activation model primitives.

This module deliberately contains no raw-IQ, MATLAB, SAGE, or production
pipeline entry point.  It consumes only the frozen CSV/JSON/CSV.GZ model
artifacts named by the versioned activation configuration.
"""

from __future__ import annotations

import csv
import bisect
import gzip
import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import stats


ENVIRONMENTS: tuple[str, ...] = (
    "Urban",
    "Special Reflective",
    "Mountain/Valley",
    "Highway/Open",
)
ELEVATION_BANDS: tuple[str, ...] = ("LOW", "MID", "HIGH")
_BAND_LIMITS: dict[str, tuple[float, float, bool]] = {
    "LOW": (0.0, 30.0, False),
    "MID": (30.0, 60.0, False),
    "HIGH": (60.0, 90.0, True),
}
_SOURCE_SUFFIXES = (
    "_relative_path",
    "_sha256",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_gzip(path: Path) -> Iterable[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def _required_float(value: Any, field_name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid float {field_name}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite {field_name}: {value!r}")
    return result


def _optional_float(value: Any, field_name: str) -> float | None:
    if value is None or str(value).strip() in {"", "nan", "NaN", "null", "None"}:
        return None
    return _required_float(value, field_name)


def _required_int(value: Any, field_name: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer {field_name}: {value!r}") from exc


def _bool01(value: Any, field_name: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    raise ValueError(f"invalid boolean {field_name}: {value!r}")


def elevation_band_for(elevation_deg: float) -> str:
    if not math.isfinite(elevation_deg) or not 0.0 <= elevation_deg <= 90.0:
        raise ValueError(f"elevation outside [0,90]: {elevation_deg}")
    for band, (lower, upper, inclusive_upper) in _BAND_LIMITS.items():
        if lower <= elevation_deg < upper or (inclusive_upper and lower <= elevation_deg <= upper):
            return band
    raise ValueError(f"elevation has no band: {elevation_deg}")


@dataclass(frozen=True)
class ActivationConfig:
    raw: Mapping[str, Any]
    model_id: str
    model_version: str
    sample_rate_hz: int
    environments: tuple[str, ...]
    elevation_bands: tuple[str, ...]
    source: Mapping[str, str]
    stage4_confirmation: Mapping[str, Any]
    exposure: Mapping[str, Any]
    occupancy: Mapping[str, Any]
    multiplicity: Mapping[str, Any]
    slot_mapping: Mapping[str, Any]
    uncertainty: Mapping[str, Any]
    output_namespace: str
    execution_policy: Mapping[str, Any]
    protected_source: Mapping[str, Any]

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "ActivationConfig":
        environments = tuple(data.get("environments", ()))
        bands = tuple(data.get("elevation_bands", ()))
        if environments != ENVIRONMENTS:
            raise ValueError(f"environment order/values are not frozen: {environments}")
        if bands != ELEVATION_BANDS:
            raise ValueError(f"elevation band order/values are not frozen: {bands}")
        if int(data.get("sample_rate_hz", 0)) != 10230000:
            raise ValueError("sample rate must be 10230000 Hz")
        source = {str(k): str(v) for k, v in dict(data.get("source", {})).items()}
        required_source_keys = {
            "event_parameters_relative_path", "event_parameters_sha256",
            "path_parameters_relative_path", "path_parameters_sha256",
            "events_relative_path", "events_sha256",
            "event_paths_relative_path", "event_paths_sha256",
            "sage_runs_relative_path", "sage_runs_sha256",
            "run_summary_relative_path", "run_summary_sha256",
            "modeling_run_eligibility_relative_path", "modeling_run_eligibility_sha256",
            "event_context_aligned_relative_path", "event_context_aligned_sha256",
            "scene_context_relative_path", "scene_context_sha256",
            "geometry_grid_relative_path", "geometry_grid_sha256",
            "path_model_manifest_relative_path", "path_model_manifest_sha256",
            "gain_model_manifest_relative_path", "gain_model_manifest_sha256",
        }
        missing = sorted(required_source_keys.difference(source))
        if missing:
            raise ValueError(f"missing source contract fields: {missing}")
        exposure = dict(data.get("exposure", {}))
        if int(exposure.get("closure_radius_windows", -1)) != 2:
            raise ValueError("closure radius must remain 2 windows")
        if float(exposure.get("geometry_join_max_delta_s", 0.0)) != 0.011:
            raise ValueError("geometry join tolerance must remain 0.011 s")
        multiplicity = dict(data.get("multiplicity", {}))
        if list(multiplicity.get("categories", ())) != [1, 2, 3]:
            raise ValueError("conditional multiplicity categories must be [1,2,3]")
        if list(multiplicity.get("base_dirichlet_prior", ())) != [0.5, 0.5, 0.5]:
            raise ValueError("base Dirichlet prior is not frozen")
        return cls(
            raw=dict(data),
            model_id=str(data["model_id"]),
            model_version=str(data["model_version"]),
            sample_rate_hz=10230000,
            environments=environments,
            elevation_bands=bands,
            source=source,
            stage4_confirmation=dict(data.get("stage4_confirmation", {})),
            exposure=exposure,
            occupancy=dict(data.get("occupancy", {})),
            multiplicity=multiplicity,
            slot_mapping=dict(data.get("slot_mapping", {})),
            uncertainty=dict(data.get("uncertainty", {})),
            output_namespace=str(data["output_namespace"]),
            execution_policy=dict(data.get("execution_policy", {})),
            protected_source=dict(data.get("protected_source", {})),
        )


def load_activation_config(path: Path) -> ActivationConfig:
    return ActivationConfig.from_json(_read_json(_canonical(path)))


@dataclass(frozen=True)
class ConfirmedEvent:
    event_id: str
    run_id: str
    scene_id: str
    prn: str
    tracking_channel: str
    center_window_id: int
    environment: str
    elevation_deg: float | None
    elevation_band: str | None
    elevation_modeling_ready: bool
    confirmed_path_count: int
    event_utc: str


@dataclass(frozen=True)
class EventPathObservation:
    event_path_id: str
    event_id: str
    run_id: str
    scene_id: str
    path_id: int
    environment: str
    elevation_band: str | None
    excess_delay_ns: float
    relative_doppler_hz: float
    relative_power_db: float
    relative_amplitude_linear: float


@dataclass(frozen=True)
class Stage0Source:
    run_id: str
    scene_id: str
    prn: str
    tracking_channel: str
    environment: str
    stage0_path: Path
    expected_window_count: int


@dataclass(frozen=True)
class ExposureWindow:
    run_id: str
    scene_id: str
    prn: str
    tracking_channel: str
    environment: str
    window_id: int
    sample_start_zero_based: int
    recording_time_s: float
    tow_s: float
    nav_symbol_1: int | None = None
    nav_symbol_2: int | None = None
    continuity_segment: int = 0
    geometry_elevation_deg: float | None = None
    elevation_band: str | None = None
    azimuth_deg: float | None = None
    nmea_snr_db_hz: float | None = None
    geometry_join_valid: bool = False
    geometry_join_status: str = "not_joined"
    geometry_time_delta_s: float | None = None
    time_bin_index: int | None = None
    support_label: str = "INACTIVE"


class GeometryJoinResult(list[ExposureWindow]):
    """List-compatible join result with aggregate diagnostics."""

    def __init__(self, rows: Iterable[ExposureWindow], matched_count: int = 0, valid_count: int = 0):
        super().__init__(rows)
        self.matched_count = matched_count
        self.valid_count = valid_count


@dataclass(frozen=True)
class ActivationEvidence:
    exposure: tuple[ExposureWindow, ...]
    memberships: tuple[Mapping[str, Any], ...]
    closure_complete: Mapping[str, bool]


@dataclass(frozen=True)
class SceneCellExposure:
    scene_id: str
    environment: str
    elevation_band: str | None
    exposure_windows: int
    support_windows: int
    core_event_ids: tuple[str, ...]
    scene_rate: float


@dataclass(frozen=True)
class BetaOccupancyModel:
    level: str
    key: str
    alpha: float
    beta: float
    mean: float
    q025: float
    q50: float
    q975: float
    direct_scene_count: int
    direct_core_event_count: int
    support_status: str
    parent_key: str | None = None


@dataclass(frozen=True)
class OccupancyHierarchy:
    global_model: BetaOccupancyModel
    environment_models: Mapping[str, BetaOccupancyModel]
    cell_models: Mapping[tuple[str, str], BetaOccupancyModel]
    scene_cell_exposure: tuple[SceneCellExposure, ...]


@dataclass(frozen=True)
class MultiplicityModel:
    level: str
    key: str
    categories: tuple[int, ...]
    counts: tuple[int, ...]
    alpha: tuple[float, ...]
    probabilities: tuple[float, ...]
    q025: tuple[float, ...]
    q50: tuple[float, ...]
    q975: tuple[float, ...]
    direct_event_count: int
    support_status: str
    parent_key: str | None = None


@dataclass(frozen=True)
class MultiplicityHierarchy:
    global_model: MultiplicityModel
    environment_models: Mapping[str, MultiplicityModel]
    cell_models: Mapping[tuple[str, str], MultiplicityModel]


@dataclass(frozen=True)
class ActivationModel:
    """Fitted activation layers consumed by a later block generator.

    This object deliberately contains no generated path rows.  It keeps the
    occurrence proxy and conditional multiplicity model separate, while
    carrying the immutable provenance needed by downstream composition.
    """

    occupancy: OccupancyHierarchy
    multiplicity: MultiplicityHierarchy
    model_id: str = "nlos-slot-activation-v1"
    model_manifest_sha256: str = ""
    path_parameter_support_status: Mapping[tuple[str, str], str] = field(default_factory=dict)


@dataclass(frozen=True)
class PathDraw:
    relative_delay_ns: float
    relative_doppler_hz: float
    relative_amplitude_linear: float
    relative_phase_rad: float | None = None
    stable_source_id: str = ""


@dataclass(frozen=True)
class SlottedPath:
    nlos_path_id: int
    path_active: bool
    path_status: str
    relative_delay_ns: float | None
    relative_doppler_hz: float | None
    relative_amplitude_linear: float
    relative_phase_rad: float | None


@dataclass(frozen=True)
class BlockActivationState:
    block_id: str
    environment: str
    elevation_band: str
    activation_mode: str
    z_active: bool
    k_active: int
    active_mask: tuple[bool, bool, bool]
    occupancy_support_status: str
    multiplicity_support_status: str
    path_parameter_support_status: str = "EXTERNAL_FROZEN_MODEL"
    is_prior_only: bool = False
    master_seed: int | None = None
    block_seed: int | None = None


@dataclass(frozen=True)
class SlotRow:
    ms: int
    satellite_id: str
    nlos_path_id: int
    path_active: bool
    path_status: str
    relative_delay_ns: float | None
    relative_doppler_hz: float | None
    relative_amplitude_linear: float
    relative_phase_rad: float | None


@dataclass(frozen=True)
class QADrawSummary:
    environment: str
    elevation_band: str
    activation_mode: str
    draw_count: int
    active_count: int
    k_counts: Mapping[int, int]
    seed: int


@dataclass(frozen=True)
class BootstrapResult:
    records: tuple[Mapping[str, Any], ...]
    seed: int
    replicate_count: int


@dataclass(frozen=True)
class SourceAudit:
    source_hashes: Mapping[str, str]
    eligible_run_count: int
    stage0_window_count: int
    eligible_run_ids: tuple[str, ...]
    run_records: tuple[Mapping[str, str], ...]
    run_summary_by_id: Mapping[str, Mapping[str, str]]
    scene_context_by_scene: Mapping[str, Mapping[str, str]]


def _source_path(project_root: Path, config: ActivationConfig, key: str) -> Path:
    relative_key = f"{key}_relative_path"
    if relative_key not in config.source:
        raise KeyError(relative_key)
    return _canonical(project_root / Path(config.source[relative_key]))


def _verify_declared_sources(project_root: Path, config: ActivationConfig) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, declared_path in sorted(config.source.items()):
        if not key.endswith("_relative_path"):
            continue
        stem = key[: -len("_relative_path")]
        path = _canonical(project_root / Path(declared_path))
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        expected = config.source.get(f"{stem}_sha256", "").lower()
        if actual.lower() != expected:
            raise ValueError(f"source hash mismatch for {stem}: expected {expected}, got {actual}")
        hashes[stem] = actual
    return hashes


def _load_scene_context(project_root: Path, config: ActivationConfig) -> dict[str, dict[str, str]]:
    rows = _read_csv(_source_path(project_root, config, "scene_context"))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        scene = str(row.get("scene_id", "")).strip()
        environment = str(row.get("environment_class", row.get("environment", ""))).strip()
        if not scene or environment not in ENVIRONMENTS:
            raise ValueError(f"invalid scene context row: {row}")
        if scene in result and result[scene] != row:
            raise ValueError(f"duplicate scene context: {scene}")
        result[scene] = row
    return result


def verify_frozen_sources(project_root: Path, config: ActivationConfig) -> SourceAudit:
    root = _canonical(project_root)
    hashes = _verify_declared_sources(root, config)
    eligibility_rows = _read_csv(_source_path(root, config, "modeling_run_eligibility"))
    eligible_ids = tuple(sorted(
        str(row["run_id"]) for row in eligibility_rows
        if _bool01(row.get("include_in_environment_modeling", "0"), "include_in_environment_modeling")
    ))
    if len(eligible_ids) != 63:
        raise ValueError(f"expected 63 environment-eligible runs, got {len(eligible_ids)}")
    if any("G06" in run_id and "__G06__" in run_id for run_id in eligible_ids):
        raise ValueError("G06 legacy run must remain excluded")
    run_rows = _read_csv(_source_path(root, config, "sage_runs"))
    run_by_id = {str(row["run_id"]): row for row in run_rows}
    if len(run_by_id) != len(run_rows):
        raise ValueError("duplicate run_id in sage_runs")
    selected_runs: list[Mapping[str, str]] = []
    for run_id in eligible_ids:
        if run_id not in run_by_id:
            raise ValueError(f"eligible run missing from sage_runs: {run_id}")
        row = run_by_id[run_id]
        if _required_int(row.get("sampling_rate_hz"), "sampling_rate_hz") != 10230000:
            raise ValueError(f"non-10.23 MHz eligible run: {run_id}")
        selected_runs.append(row)
    summary_rows = _read_csv(_source_path(root, config, "run_summary"))
    summary_by_id = {str(row["run_id"]): row for row in summary_rows}
    if set(eligible_ids) != set(summary_by_id).intersection(eligible_ids):
        missing = sorted(set(eligible_ids).difference(summary_by_id))
        raise ValueError(f"eligible run missing from run_summary: {missing}")
    stage0_total = sum(_required_int(summary_by_id[run_id]["stage0_window_count"], "stage0_window_count") for run_id in eligible_ids)
    if stage0_total != 169637:
        raise ValueError(f"expected 169637 Stage0 windows, got {stage0_total}")
    scene_context = _load_scene_context(root, config)
    for row in selected_runs:
        scene = str(row["scene_id"])
        if scene not in scene_context:
            raise ValueError(f"eligible run scene missing from scene_context: {scene}")
        expected_environment = str(scene_context[scene].get("environment_class", scene_context[scene].get("environment", "")))
        if expected_environment not in ENVIRONMENTS:
            raise ValueError(f"invalid environment for scene {scene}: {expected_environment}")
    return SourceAudit(
        source_hashes=hashes,
        eligible_run_count=len(eligible_ids),
        stage0_window_count=stage0_total,
        eligible_run_ids=eligible_ids,
        run_records=tuple(selected_runs),
        run_summary_by_id={run_id: summary_by_id[run_id] for run_id in eligible_ids},
        scene_context_by_scene=scene_context,
    )


def _event_lookup(project_root: Path, config: ActivationConfig) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]]]:
    events = {str(row["event_id"]): row for row in _read_csv(_source_path(project_root, config, "events"))}
    paths_by_event: dict[str, list[dict[str, str]]] = {}
    for row in _read_csv(_source_path(project_root, config, "event_paths")):
        paths_by_event.setdefault(str(row["event_id"]), []).append(row)
    return events, paths_by_event


def load_confirmed_events(project_root: Path, config: ActivationConfig) -> list[ConfirmedEvent]:
    audit = verify_frozen_sources(project_root, config)
    eligible = set(audit.eligible_run_ids)
    event_rows, paths_by_event = _event_lookup(project_root, config)
    rows = _read_csv(_source_path(project_root, config, "event_parameters"))
    result: list[ConfirmedEvent] = []
    seen: set[str] = set()
    for row in rows:
        event_id = str(row.get("event_id", ""))
        run_id = str(row.get("run_id", ""))
        if run_id not in eligible:
            continue
        if event_id in seen:
            raise ValueError(f"duplicate confirmed event: {event_id}")
        seen.add(event_id)
        if row.get("parameter_source_status") != "complete":
            raise ValueError(f"incomplete event parameter row: {event_id}")
        if not _bool01(row.get("environment_modeling_ready", "0"), "environment_modeling_ready"):
            raise ValueError(f"event is not environment-ready: {event_id}")
        event_source = event_rows.get(event_id)
        if event_source is None:
            raise ValueError(f"event parameter row missing source event: {event_id}")
        if _required_int(event_source.get("joint_valid"), "joint_valid") != 1:
            raise ValueError(f"event does not meet joint_valid criterion: {event_id}")
        if _required_int(event_source.get("joint_multipath_count"), "joint_multipath_count") <= 0:
            raise ValueError(f"event has no confirmed multipath count: {event_id}")
        if event_source.get("event_status") != "confirmed_multipath":
            raise ValueError(f"event status is not confirmed_multipath: {event_id}")
        k = _required_int(row.get("confirmed_path_count"), "confirmed_path_count")
        if k not in {1, 2, 3}:
            raise ValueError(f"confirmed path count outside fixed slot capacity: {event_id}: {k}")
        paths = [p for p in paths_by_event.get(event_id, []) if p.get("path_role") == "multipath" and _bool01(p.get("is_multipath", "0"), "is_multipath")]
        if len(paths) != k:
            raise ValueError(f"event/path count mismatch for {event_id}: expected {k}, got {len(paths)}")
        for path in paths:
            if path.get("estimate_stage") != "stage4_joint" or path.get("label_value") != "confirmed_multipath":
                raise ValueError(f"non-Stage4 confirmed path included: {event_id}")
        elevation = _optional_float(row.get("elevation_deg"), "elevation_deg")
        band = str(row.get("elevation_band", "")).strip() or None
        if elevation is not None and band != elevation_band_for(elevation):
            raise ValueError(f"event elevation band mismatch: {event_id}")
        elevation_ready = _bool01(row.get("elevation_modeling_ready", "0"), "elevation_modeling_ready")
        if elevation_ready and (elevation is None or band is None):
            raise ValueError(f"elevation-ready event lacks elevation context: {event_id}")
        result.append(ConfirmedEvent(
            event_id=event_id,
            run_id=run_id,
            scene_id=str(row["scene_id"]),
            prn=str(row["prn"]),
            tracking_channel=str(row["tracking_channel"] if "tracking_channel" in row else event_source.get("tracking_channel", "")),
            center_window_id=_required_int(row.get("center_window_id"), "center_window_id"),
            environment=str(row["environment_class"]),
            elevation_deg=elevation,
            elevation_band=band,
            elevation_modeling_ready=elevation_ready,
            confirmed_path_count=k,
            event_utc=str(row.get("event_utc", "")),
        ))
    result.sort(key=lambda event: (event.run_id, event.center_window_id, event.event_id))
    if len(result) != 94:
        raise ValueError(f"expected 94 confirmed events after legacy exclusion, got {len(result)}")
    return result


def load_confirmed_event_paths(project_root: Path, config: ActivationConfig) -> list[EventPathObservation]:
    events = {event.event_id: event for event in load_confirmed_events(project_root, config)}
    result: list[EventPathObservation] = []
    for row in _read_csv(_source_path(project_root, config, "path_parameters")):
        event_id = str(row.get("event_id", ""))
        if event_id not in events:
            continue
        if row.get("estimate_stage") != "stage4_joint" or row.get("path_role") != "multipath":
            continue
        if not _bool01(row.get("is_multipath", "0"), "is_multipath") or row.get("label_value") != "confirmed_multipath":
            continue
        power_db = _required_float(row.get("relative_power_db"), "relative_power_db")
        result.append(EventPathObservation(
            event_path_id=str(row["event_path_id"]),
            event_id=event_id,
            run_id=str(row["run_id"]),
            scene_id=str(row["scene_id"]),
            path_id=_required_int(row.get("path_id"), "path_id"),
            environment=str(row["environment_class"]),
            elevation_band=str(row.get("elevation_band", "")).strip() or None,
            excess_delay_ns=_required_float(row.get("excess_delay_s"), "excess_delay_s") * 1e9,
            relative_doppler_hz=_required_float(row.get("relative_doppler_hz"), "relative_doppler_hz"),
            relative_power_db=power_db,
            relative_amplitude_linear=10.0 ** (power_db / 20.0),
        ))
    if len(result) != 100:
        raise ValueError(f"expected 100 confirmed event paths, got {len(result)}")
    return result


def resolve_stage0_sources(project_root: Path, audit: SourceAudit, config: ActivationConfig) -> list[Stage0Source]:
    """Resolve Stage0 from each audited run's recorded result namespace."""

    root = _canonical(project_root)
    scene_context = audit.scene_context_by_scene
    sources: list[Stage0Source] = []
    for run in sorted(audit.run_records, key=lambda row: str(row["run_id"])):
        run_id = str(run["run_id"])
        scene_id = str(run["scene_id"])
        result_relpath = str(run.get("source_result_relpath", "")).strip()
        if not result_relpath:
            raise ValueError(f"missing source_result_relpath for {run_id}")
        stage0 = _canonical(root / Path(result_relpath) / str(config.exposure["stage0_filename"]))
        if not stage0.is_file():
            raise FileNotFoundError(stage0)
        context = scene_context.get(scene_id, {})
        environment = str(context.get("environment_class", context.get("environment", ""))).strip()
        if environment not in ENVIRONMENTS:
            raise ValueError(f"unknown environment for {scene_id}: {environment}")
        sources.append(Stage0Source(
            run_id=run_id,
            scene_id=scene_id,
            prn=str(run["prn"]),
            tracking_channel=str(run["tracking_channel"]),
            environment=environment,
            stage0_path=stage0,
            expected_window_count=_required_int(audit.run_summary_by_id[run_id]["stage0_window_count"], "stage0_window_count"),
        ))
    if len(sources) != audit.eligible_run_count:
        raise ValueError(f"resolved {len(sources)} Stage0 sources, expected {audit.eligible_run_count}")
    return sources


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None or str(value).strip() in {"", "nan", "NaN", "null", "None"}:
        return None
    return _required_int(value, field_name)


def load_stage0_exposure(source: Stage0Source) -> list[ExposureWindow]:
    rows = _read_csv(source.stage0_path)
    required = {"window_id", "sample_start_zero_based", "recording_time_s", "tow_s"}
    if not rows:
        raise ValueError(f"empty Stage0 exposure: {source.stage0_path}")
    if not required.issubset(rows[0]):
        raise ValueError(f"Stage0 missing required columns: {sorted(required.difference(rows[0]))}")
    result: list[ExposureWindow] = []
    seen: set[int] = set()
    for row in rows:
        window_id = _required_int(row.get("window_id"), "window_id")
        if window_id in seen:
            raise ValueError(f"duplicate Stage0 window id {window_id}: {source.run_id}")
        seen.add(window_id)
        result.append(ExposureWindow(
            run_id=source.run_id,
            scene_id=source.scene_id,
            prn=source.prn,
            tracking_channel=source.tracking_channel,
            environment=source.environment,
            window_id=window_id,
            sample_start_zero_based=_required_int(row.get("sample_start_zero_based"), "sample_start_zero_based"),
            recording_time_s=_required_float(row.get("recording_time_s"), "recording_time_s"),
            tow_s=_required_float(row.get("tow_s"), "tow_s"),
            nav_symbol_1=_optional_int(row.get("nav_symbol_1"), "nav_symbol_1"),
            nav_symbol_2=_optional_int(row.get("nav_symbol_2"), "nav_symbol_2"),
        ))
    result.sort(key=lambda row: row.window_id)
    if len(result) != source.expected_window_count:
        raise ValueError(f"Stage0 row count mismatch for {source.run_id}: expected {source.expected_window_count}, got {len(result)}")
    if [row.window_id for row in result] != list(range(1, len(result) + 1)):
        raise ValueError(f"Stage0 window IDs are not contiguous 1..N for {source.run_id}")
    return result


def assign_continuity_segments(windows: Sequence[ExposureWindow]) -> list[ExposureWindow]:
    """Assign segments without bridging window, sample, or TOW discontinuities."""

    ordered = sorted(windows, key=lambda row: (row.run_id, row.window_id))
    result: list[ExposureWindow] = []
    previous: ExposureWindow | None = None
    segment = -1
    expected_sample_step = 10230000 * 0.02
    for row in ordered:
        new_segment = previous is None or row.run_id != previous.run_id
        if previous is not None and not new_segment:
            sample_delta = row.sample_start_zero_based - previous.sample_start_zero_based
            tow_delta = row.tow_s - previous.tow_s
            new_segment = (
                row.window_id != previous.window_id + 1
                or abs(sample_delta - expected_sample_step) > 3.0
                or abs(tow_delta - 0.02) > 0.002
            )
        if new_segment:
            segment += 1
        result.append(replace(row, continuity_segment=segment))
        previous = row
    return result


def _geometry_grid_rows(path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    iterator: Iterable[dict[str, str]]
    if path.suffix.lower() == ".gz":
        iterator = _read_csv_gzip(path)
    else:
        iterator = iter(_read_csv(path))
    for row in iterator:
        run_id = str(row.get("run_id", ""))
        if not run_id:
            raise ValueError("geometry grid row has empty run_id")
        grouped.setdefault(run_id, []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: (_required_float(row.get("time_s"), "time_s"), _required_int(row.get("time_bin_index"), "time_bin_index")))
    return grouped


def join_geometry_grid(
    windows: Sequence[ExposureWindow],
    geometry_grid_path: Path,
    *,
    tolerance_s: float = 0.011,
) -> GeometryJoinResult:
    if tolerance_s <= 0.0:
        raise ValueError("geometry join tolerance must be positive")
    grouped = _geometry_grid_rows(_canonical(geometry_grid_path))
    time_values_by_run = {
        run_id: [_required_float(row.get("time_s"), "time_s") for row in rows]
        for run_id, rows in grouped.items()
    }
    result: list[ExposureWindow] = []
    matched = 0
    valid = 0
    for window in windows:
        candidates = grouped.get(window.run_id, [])
        if not candidates:
            result.append(replace(window, geometry_join_status="run_not_in_geometry_grid"))
            continue
        time_values = time_values_by_run[window.run_id]
        insertion = bisect.bisect_left(time_values, window.recording_time_s)
        candidate_indices: set[int] = set()
        if insertion < len(candidates):
            candidate_indices.add(insertion)
            same_time = time_values[insertion]
            left = insertion - 1
            while left >= 0 and time_values[left] == same_time:
                candidate_indices.add(left)
                left -= 1
            right = insertion + 1
            while right < len(candidates) and time_values[right] == same_time:
                candidate_indices.add(right)
                right += 1
        if insertion > 0:
            candidate_indices.add(insertion - 1)
            same_time = time_values[insertion - 1]
            left = insertion - 2
            while left >= 0 and time_values[left] == same_time:
                candidate_indices.add(left)
                left -= 1
            right = insertion
            while right < len(candidates) and time_values[right] == same_time:
                candidate_indices.add(right)
                right += 1
        ranked: list[tuple[float, int, dict[str, str]]] = []
        for index in sorted(candidate_indices):
            row = candidates[index]
            time_value = time_values[index]
            time_bin = _required_int(row.get("time_bin_index"), "time_bin_index")
            ranked.append((abs(time_value - window.recording_time_s), time_bin, row))
        ranked.sort(key=lambda item: (item[0], item[1]))
        delta, _, row = ranked[0]
        if delta > tolerance_s:
            result.append(replace(window, geometry_join_status="nearest_geometry_delta_exceeds_tolerance", geometry_time_delta_s=delta))
            continue
        grid_environment = str(row.get("environment", "")).strip()
        if grid_environment and grid_environment != window.environment:
            raise ValueError(f"geometry/environment mismatch for {window.run_id}/{window.window_id}: {grid_environment} != {window.environment}")
        elevation = _optional_float(row.get("elevation_deg"), "elevation_deg")
        band = str(row.get("elevation_band", "")).strip() or None
        if elevation is not None:
            expected_band = elevation_band_for(elevation)
            if band is not None and band != expected_band:
                raise ValueError(f"geometry elevation-band mismatch at {window.run_id}/{window.window_id}")
            band = expected_band
        join_valid = _bool01(row.get("geometry_join_valid", "0"), "geometry_join_valid")
        matched += 1
        if join_valid:
            valid += 1
        result.append(replace(
            window,
            geometry_elevation_deg=elevation,
            elevation_band=band,
            azimuth_deg=_optional_float(row.get("azimuth_deg"), "azimuth_deg"),
            nmea_snr_db_hz=_optional_float(row.get("nmea_snr_db_hz"), "nmea_snr_db_hz"),
            geometry_join_valid=join_valid,
            geometry_join_status=str(row.get("geometry_join_status", "valid" if join_valid else "invalid")),
            geometry_time_delta_s=delta,
            time_bin_index=_required_int(row.get("time_bin_index"), "time_bin_index"),
        ))
    return GeometryJoinResult(result, matched_count=matched, valid_count=valid)


def build_activation_labels(
    exposure: Sequence[ExposureWindow],
    events: Sequence[ConfirmedEvent],
    *,
    closure_radius: int = 2,
) -> ActivationEvidence:
    if closure_radius < 0:
        raise ValueError("closure radius must be non-negative")
    by_key = {(row.run_id, row.window_id): row for row in exposure}
    if len(by_key) != len(exposure):
        raise ValueError("exposure contains duplicate run/window keys")
    memberships: list[dict[str, Any]] = []
    closure_complete: dict[str, bool] = {}
    membership_keys: set[tuple[str, str, int]] = set()
    core_windows: set[tuple[str, int]] = set()
    closure_windows: set[tuple[str, int]] = set()
    for event in events:
        core_key = (event.run_id, event.center_window_id)
        core = by_key.get(core_key)
        if core is None:
            raise ValueError(f"confirmed event center is absent from Stage0 exposure: {event.event_id}")
        core_windows.add(core_key)
        complete = True
        for distance in range(-closure_radius, closure_radius + 1):
            target_key = (event.run_id, event.center_window_id + distance)
            target = by_key.get(target_key)
            if target is None or target.continuity_segment != core.continuity_segment:
                complete = False
                continue
            closure_windows.add(target_key)
            membership_key = (event.event_id, event.run_id, target.window_id)
            if membership_key in membership_keys:
                continue
            membership_keys.add(membership_key)
            memberships.append({
                "event_id": event.event_id,
                "run_id": event.run_id,
                "scene_id": event.scene_id,
                "window_id": target.window_id,
                "core_window_id": event.center_window_id,
                "membership_type": "CONFIRMED_CORE" if distance == 0 else "CONFIRMED_CLOSURE_ONLY",
                "distance_from_core": distance,
                "continuity_segment": target.continuity_segment,
            })
        closure_complete[event.event_id] = complete
    by_window: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for membership in memberships:
        by_window.setdefault((membership["run_id"], membership["window_id"]), []).append(membership)
    labeled: list[ExposureWindow] = []
    for row in exposure:
        members = by_window.get((row.run_id, row.window_id), [])
        if any(member["membership_type"] == "CONFIRMED_CORE" for member in members):
            label = "CONFIRMED_CORE"
        elif members:
            label = "CONFIRMED_CLOSURE_ONLY"
        else:
            label = "INACTIVE"
        labeled.append(replace(row, support_label=label))
    return ActivationEvidence(
        exposure=tuple(sorted(labeled, key=lambda row: (row.run_id, row.window_id))),
        memberships=tuple(sorted(memberships, key=lambda row: (row["run_id"], row["window_id"], row["event_id"]))),
        closure_complete=closure_complete,
    )


def aggregate_scene_cell_exposure(evidence: ActivationEvidence) -> list[SceneCellExposure]:
    core_by_window: dict[tuple[str, int], set[str]] = {}
    for membership in evidence.memberships:
        if membership["membership_type"] == "CONFIRMED_CORE":
            core_by_window.setdefault((membership["run_id"], membership["window_id"]), set()).add(str(membership["event_id"]))

    groups: dict[tuple[str, str, str | None], list[ExposureWindow]] = {}
    for row in evidence.exposure:
        groups.setdefault((row.scene_id, row.environment, None), []).append(row)
        if row.geometry_join_valid and row.elevation_band in ELEVATION_BANDS:
            groups.setdefault((row.scene_id, row.environment, row.elevation_band), []).append(row)
    result: list[SceneCellExposure] = []
    for (scene_id, environment, band), rows in sorted(
        groups.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2] or ""),
    ):
        support_keys = {(row.run_id, row.window_id) for row in rows if row.support_label != "INACTIVE"}
        core_events = set()
        for row in rows:
            core_events.update(core_by_window.get((row.run_id, row.window_id), set()))
        exposure_count = len({(row.run_id, row.window_id) for row in rows})
        result.append(SceneCellExposure(
            scene_id=scene_id,
            environment=environment,
            elevation_band=band,
            exposure_windows=exposure_count,
            support_windows=len(support_keys),
            core_event_ids=tuple(sorted(core_events)),
            scene_rate=(len(support_keys) / exposure_count if exposure_count else 0.0),
        ))
    return result


def classify_occupancy_support(exposure_scene_count: int, confirmed_event_count: int) -> str:
    if exposure_scene_count <= 0:
        return "PRIOR_ONLY"
    if confirmed_event_count <= 0:
        return "EXPOSURE_ONLY_ZERO_CONFIRMED"
    if confirmed_event_count >= 10 and exposure_scene_count >= 2:
        return "DATA_SUPPORTED_WITH_GROUPED_VALIDATION"
    return "SPARSE_PARTIAL_POOLING"


def fit_beta_pseudo_posterior(
    scene_rates: Sequence[float],
    parent_mean: float | None,
    parent_mass: float,
    *,
    level: str = "global",
    key: str = "global",
    direct_scene_count: int | None = None,
    direct_core_event_count: int = 0,
    support_status: str = "UNCLASSIFIED",
    parent_key: str | None = None,
) -> BetaOccupancyModel:
    if parent_mass < 0.0 or not math.isfinite(parent_mass):
        raise ValueError("parent mass must be finite and non-negative")
    alpha = 0.5
    beta = 0.5
    if parent_mean is not None:
        if not 0.0 <= parent_mean <= 1.0 or not math.isfinite(parent_mean):
            raise ValueError("parent mean must lie in [0,1]")
        alpha = parent_mass * parent_mean
        beta = parent_mass * (1.0 - parent_mean)
    for rate in scene_rates:
        if not 0.0 <= float(rate) <= 1.0 or not math.isfinite(float(rate)):
            raise ValueError(f"scene rate outside [0,1]: {rate}")
        alpha += float(rate)
        beta += 1.0 - float(rate)
    if alpha <= 0.0 or beta <= 0.0:
        raise ValueError("Beta posterior parameters must be positive")
    mean = alpha / (alpha + beta)
    q025, q50, q975 = (float(stats.beta.ppf(q, alpha, beta)) for q in (0.025, 0.5, 0.975))
    return BetaOccupancyModel(
        level=level,
        key=key,
        alpha=float(alpha),
        beta=float(beta),
        mean=float(mean),
        q025=q025,
        q50=q50,
        q975=q975,
        direct_scene_count=len(scene_rates) if direct_scene_count is None else int(direct_scene_count),
        direct_core_event_count=int(direct_core_event_count),
        support_status=support_status,
        parent_key=parent_key,
    )


def fit_occupancy_hierarchy(
    scene_cell_exposure: Sequence[SceneCellExposure],
    config: ActivationConfig,
) -> OccupancyHierarchy:
    env_rows = [row for row in scene_cell_exposure if row.elevation_band is None]
    if len({(row.scene_id, row.environment) for row in env_rows}) != len(env_rows):
        raise ValueError("duplicate scene/environment exposure rows")
    global_rates = [row.scene_rate for row in env_rows]
    global_event_count = len({event_id for row in env_rows for event_id in row.core_event_ids})
    global_model = fit_beta_pseudo_posterior(
        global_rates,
        parent_mean=None,
        parent_mass=0.0,
        level="global",
        key="global",
        direct_core_event_count=global_event_count,
        support_status=classify_occupancy_support(len(env_rows), global_event_count),
    )
    parent_mass = float(config.occupancy["parent_equivalent_scene_count"])
    environment_models: dict[str, BetaOccupancyModel] = {}
    for environment in config.environments:
        direct = [row for row in env_rows if row.environment == environment]
        event_count = len({event_id for row in direct for event_id in row.core_event_ids})
        environment_models[environment] = fit_beta_pseudo_posterior(
            [row.scene_rate for row in direct],
            parent_mean=global_model.mean,
            parent_mass=parent_mass,
            level="environment",
            key=environment,
            direct_core_event_count=event_count,
            support_status=classify_occupancy_support(len(direct), event_count),
            parent_key="global",
        )
    cell_models: dict[tuple[str, str], BetaOccupancyModel] = {}
    for environment in config.environments:
        parent = environment_models[environment]
        for band in config.elevation_bands:
            direct = [row for row in scene_cell_exposure if row.environment == environment and row.elevation_band == band]
            event_count = len({event_id for row in direct for event_id in row.core_event_ids})
            support = classify_occupancy_support(len(direct), event_count)
            if not direct:
                cell_models[(environment, band)] = BetaOccupancyModel(
                    level="cell",
                    key=f"{environment}|{band}",
                    alpha=parent.alpha,
                    beta=parent.beta,
                    mean=parent.mean,
                    q025=parent.q025,
                    q50=parent.q50,
                    q975=parent.q975,
                    direct_scene_count=0,
                    direct_core_event_count=0,
                    support_status="PRIOR_ONLY",
                    parent_key=environment,
                )
                continue
            cell_models[(environment, band)] = fit_beta_pseudo_posterior(
                [row.scene_rate for row in direct],
                parent_mean=parent.mean,
                parent_mass=parent_mass,
                level="cell",
                key=f"{environment}|{band}",
                direct_core_event_count=event_count,
                support_status=support,
                parent_key=environment,
            )
    return OccupancyHierarchy(
        global_model=global_model,
        environment_models=environment_models,
        cell_models=cell_models,
        scene_cell_exposure=tuple(scene_cell_exposure),
    )


def _multiplicity_support(event_count: int, scene_count: int) -> str:
    if event_count == 0:
        return "PRIOR_ONLY"
    if event_count >= 10 and scene_count >= 2:
        return "DATA_SUPPORTED_WITH_GROUPED_VALIDATION"
    if event_count >= 3:
        return "SPARSE_PARTIAL_POOLING"
    return "PRIOR_DOMINANT"


def fit_dirichlet_counts(
    counts: Sequence[int],
    parent_probabilities: Sequence[float] | None,
    parent_mass: float,
    *,
    level: str = "global",
    key: str = "global",
    direct_event_count: int | None = None,
    support_status: str = "UNCLASSIFIED",
    parent_key: str | None = None,
) -> MultiplicityModel:
    categories = (1, 2, 3)
    if len(counts) != len(categories):
        raise ValueError("counts must contain K=1,2,3")
    integer_counts = tuple(int(value) for value in counts)
    if any(value < 0 for value in integer_counts):
        raise ValueError("counts must be non-negative")
    if parent_mass < 0.0 or not math.isfinite(parent_mass):
        raise ValueError("parent mass must be finite and non-negative")
    if parent_probabilities is None:
        parent = np.zeros(3, dtype=float)
        base = np.full(3, 0.5, dtype=float)
    else:
        parent = np.asarray(parent_probabilities, dtype=float)
        if parent.shape != (3,) or not np.all(np.isfinite(parent)) or np.any(parent <= 0.0):
            raise ValueError("parent probabilities must be finite and positive")
        if not math.isclose(float(parent.sum()), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("parent probabilities must sum to one")
        base = parent * float(parent_mass)
    alpha_array = base + np.asarray(integer_counts, dtype=float)
    if np.any(alpha_array <= 0.0):
        raise ValueError("Dirichlet parameters must be positive")
    probabilities = alpha_array / alpha_array.sum()
    q025 = np.array([stats.beta.ppf(0.025, alpha, alpha_array.sum() - alpha) for alpha in alpha_array], dtype=float)
    q50 = np.array([stats.beta.ppf(0.5, alpha, alpha_array.sum() - alpha) for alpha in alpha_array], dtype=float)
    q975 = np.array([stats.beta.ppf(0.975, alpha, alpha_array.sum() - alpha) for alpha in alpha_array], dtype=float)
    return MultiplicityModel(
        level=level,
        key=key,
        categories=categories,
        counts=integer_counts,
        alpha=tuple(float(value) for value in alpha_array),
        probabilities=tuple(float(value) for value in probabilities),
        q025=tuple(float(value) for value in q025),
        q50=tuple(float(value) for value in q50),
        q975=tuple(float(value) for value in q975),
        direct_event_count=sum(integer_counts) if direct_event_count is None else int(direct_event_count),
        support_status=support_status,
        parent_key=parent_key,
    )


def _multiplicity_counts(events: Sequence[ConfirmedEvent]) -> tuple[int, int, int]:
    counts = [0, 0, 0]
    seen: set[str] = set()
    for event in events:
        if event.event_id in seen:
            raise ValueError(f"duplicate event in multiplicity input: {event.event_id}")
        seen.add(event.event_id)
        if event.confirmed_path_count not in (1, 2, 3):
            raise ValueError(f"invalid path count: {event.confirmed_path_count}")
        counts[event.confirmed_path_count - 1] += 1
    return tuple(counts)  # type: ignore[return-value]


def fit_multiplicity_hierarchy(
    events: Sequence[ConfirmedEvent],
    config: ActivationConfig,
) -> MultiplicityHierarchy:
    global_counts = _multiplicity_counts(events)
    global_scenes = len({event.scene_id for event in events})
    global_model = fit_dirichlet_counts(
        global_counts,
        None,
        0.0,
        level="global",
        key="global",
        direct_event_count=len(events),
        support_status=_multiplicity_support(len(events), global_scenes),
    )
    parent_mass = float(config.multiplicity["parent_equivalent_event_count"])
    environment_models: dict[str, MultiplicityModel] = {}
    for environment in config.environments:
        direct = [event for event in events if event.environment == environment]
        counts = _multiplicity_counts(direct)
        environment_models[environment] = fit_dirichlet_counts(
            counts,
            global_model.probabilities,
            parent_mass,
            level="environment",
            key=environment,
            direct_event_count=len(direct),
            support_status=_multiplicity_support(len(direct), len({event.scene_id for event in direct})),
            parent_key="global",
        )
    cell_models: dict[tuple[str, str], MultiplicityModel] = {}
    for environment in config.environments:
        parent = environment_models[environment]
        for band in config.elevation_bands:
            direct = [event for event in events if event.environment == environment and event.elevation_modeling_ready and event.elevation_band == band]
            key = (environment, band)
            if not direct:
                cell_models[key] = replace(
                    parent,
                    level="cell",
                    key=f"{environment}|{band}",
                    counts=(0, 0, 0),
                    direct_event_count=0,
                    support_status="PRIOR_ONLY",
                    parent_key=environment,
                )
                continue
            counts = _multiplicity_counts(direct)
            cell_models[key] = fit_dirichlet_counts(
                counts,
                parent.probabilities,
                parent_mass,
                level="cell",
                key=f"{environment}|{band}",
                direct_event_count=len(direct),
                support_status=_multiplicity_support(len(direct), len({event.scene_id for event in direct})),
                parent_key=environment,
            )
    return MultiplicityHierarchy(
        global_model=global_model,
        environment_models=environment_models,
        cell_models=cell_models,
    )


def sample_path_count(model: MultiplicityModel, rng: np.random.Generator) -> int:
    if tuple(model.categories) != (1, 2, 3):
        raise ValueError("multiplicity model categories must be (1,2,3)")
    return int(rng.choice(np.asarray(model.categories), p=np.asarray(model.probabilities)))


def derive_stream_seed(
    master_seed: int,
    environment: str,
    elevation_band: str,
    block_id: str,
    stream_name: str,
) -> int:
    """Derive an order-independent, reproducible RNG seed for one stream."""

    if not isinstance(master_seed, (int, np.integer)):
        raise TypeError("master_seed must be an integer")
    if environment not in ENVIRONMENTS:
        raise ValueError(f"unknown environment: {environment}")
    if elevation_band not in ELEVATION_BANDS:
        raise ValueError(f"unknown elevation band: {elevation_band}")
    if not str(block_id):
        raise ValueError("block_id must be non-empty")
    if not str(stream_name):
        raise ValueError("stream_name must be non-empty")
    payload = json.dumps(
        {
            "master_seed": int(master_seed),
            "environment": environment,
            "elevation_band": elevation_band,
            "block_id": str(block_id),
            "stream_name": str(stream_name),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    # Keep the result in NumPy's portable non-negative signed 63-bit range.
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)


def _activation_cell_models(
    model: ActivationModel,
    environment: str,
    elevation_band: str,
) -> tuple[BetaOccupancyModel, MultiplicityModel, str]:
    if environment not in ENVIRONMENTS:
        raise ValueError(f"unknown environment: {environment}")
    if elevation_band not in ELEVATION_BANDS:
        raise ValueError(f"unknown elevation band: {elevation_band}")
    key = (environment, elevation_band)
    try:
        occupancy = model.occupancy.cell_models[key]
        multiplicity = model.multiplicity.cell_models[key]
    except KeyError as exc:
        raise ValueError(f"activation model has no cell model: {environment}|{elevation_band}") from exc
    path_status = model.path_parameter_support_status.get(key, "EXTERNAL_FROZEN_MODEL")
    return occupancy, multiplicity, str(path_status)


def sample_block_activation(
    model: ActivationModel,
    config: ActivationConfig,
    environment: str,
    elevation_band: str,
    block_id: str,
    master_seed: int,
    activation_mode: str,
) -> BlockActivationState:
    """Sample the hurdle state once for a block, with isolated RNG streams."""

    allowed_modes = {"EMPIRICAL_CONFIRMED_SUPPORT", "CONDITIONAL_ACTIVE_STRESS"}
    if activation_mode not in allowed_modes:
        raise ValueError(f"unsupported activation mode: {activation_mode}")
    occupancy, multiplicity, path_status = _activation_cell_models(model, environment, elevation_band)
    block_seed = derive_stream_seed(master_seed, environment, elevation_band, block_id, "block")
    if activation_mode == "CONDITIONAL_ACTIVE_STRESS":
        z_active = True
    else:
        occurrence_rng = np.random.default_rng(
            derive_stream_seed(master_seed, environment, elevation_band, block_id, "occurrence")
        )
        z_active = bool(occurrence_rng.random() < occupancy.mean)
    if z_active:
        multiplicity_rng = np.random.default_rng(
            derive_stream_seed(master_seed, environment, elevation_band, block_id, "multiplicity")
        )
        k_active = sample_path_count(multiplicity, multiplicity_rng)
    else:
        k_active = 0
    occupancy_status = str(occupancy.support_status)
    multiplicity_status = str(multiplicity.support_status)
    is_prior_only = any(
        status == "PRIOR_ONLY"
        for status in (occupancy_status, multiplicity_status, path_status)
    )
    return BlockActivationState(
        block_id=str(block_id),
        environment=environment,
        elevation_band=elevation_band,
        activation_mode=activation_mode,
        z_active=z_active,
        k_active=k_active,
        active_mask=activation_mask(k_active),
        occupancy_support_status=occupancy_status,
        multiplicity_support_status=multiplicity_status,
        path_parameter_support_status=path_status,
        is_prior_only=is_prior_only,
        master_seed=int(master_seed),
        block_seed=block_seed,
    )


def _scene_rate(rows: Sequence[ExposureWindow]) -> float:
    keys = {(row.run_id, row.window_id) for row in rows}
    support = {(row.run_id, row.window_id) for row in rows if row.support_label != "INACTIVE"}
    return len(support) / len(keys) if keys else 0.0


def _scene_cell_rate(rows: Sequence[ExposureWindow], band: str | None) -> float:
    if band is not None:
        rows = [row for row in rows if row.geometry_join_valid and row.elevation_band == band]
    return _scene_rate(rows)


def _event_counts_by_environment(
    events: Sequence[ConfirmedEvent],
    scene: str,
    environment: str,
    band: str | None,
) -> tuple[int, int, int]:
    selected = [
        event for event in events
        if event.scene_id == scene
        and event.environment == environment
        and (band is None or (event.elevation_modeling_ready and event.elevation_band == band))
    ]
    return tuple(sum(event.confirmed_path_count == k for event in selected) for k in (1, 2, 3))


def scene_block_bootstrap(
    evidence: ActivationEvidence,
    events: Sequence[ConfirmedEvent],
    config: ActivationConfig,
) -> BootstrapResult:
    """Resample complete scenes and return explicit replicate diagnostics.

    The returned records contain no synthetic exposure rows.  A malformed
    replicate is recorded as ``FAILED`` with its reason instead of being
    silently replaced by another replicate.
    """

    replicate_count = int(config.uncertainty["bootstrap_replicates"])
    seed = int(config.uncertainty["bootstrap_seed"])
    if replicate_count <= 0:
        raise ValueError("bootstrap replicate count must be positive")
    exposure_by_scene: dict[str, list[ExposureWindow]] = {}
    for row in evidence.exposure:
        exposure_by_scene.setdefault(row.scene_id, []).append(row)
    scene_ids = tuple(sorted(exposure_by_scene))
    if not scene_ids:
        raise ValueError("bootstrap requires at least one scene")
    scene_environment: dict[str, str] = {}
    for scene, rows in exposure_by_scene.items():
        environments = {row.environment for row in rows}
        if len(environments) != 1:
            raise ValueError(f"scene has multiple environments: {scene}")
        scene_environment[scene] = next(iter(environments))
    rng = np.random.default_rng(seed)
    records: list[Mapping[str, Any]] = []
    for replicate in range(replicate_count):
        sampled = tuple(str(value) for value in rng.choice(scene_ids, size=len(scene_ids), replace=True))
        record: dict[str, Any] = {
            "replicate": replicate,
            "resample_unit": "scene",
            "sampled_scene_ids": sampled,
            "sampled_scene_count": len(sampled),
            "replicate_status": "PASS",
        }
        try:
            environment_rates: dict[str, list[float]] = {environment: [] for environment in ENVIRONMENTS}
            cell_rates: dict[str, list[float]] = {
                f"{environment}|{band}": []
                for environment in ENVIRONMENTS
                for band in ELEVATION_BANDS
            }
            environment_event_counts: dict[str, int] = {environment: 0 for environment in ENVIRONMENTS}
            cell_event_counts: dict[str, int] = {
                f"{environment}|{band}": 0
                for environment in ENVIRONMENTS
                for band in ELEVATION_BANDS
            }
            for scene in sampled:
                rows = exposure_by_scene[scene]
                environment = scene_environment[scene]
                environment_rates[environment].append(_scene_rate(rows))
                environment_event_counts[environment] += sum(
                    event.scene_id == scene and event.environment == environment for event in events
                )
                for band in ELEVATION_BANDS:
                    key = f"{environment}|{band}"
                    cell_rows = [row for row in rows if row.geometry_join_valid and row.elevation_band == band]
                    if cell_rows:
                        cell_rates[key].append(_scene_rate(cell_rows))
                    cell_event_counts[key] += sum(
                        event.scene_id == scene
                        and event.environment == environment
                        and event.elevation_modeling_ready
                        and event.elevation_band == band
                        for event in events
                    )
            record["environment_scene_rates"] = {
                key: tuple(values) for key, values in environment_rates.items()
            }
            record["cell_scene_rates"] = {key: tuple(values) for key, values in cell_rates.items()}
            record["environment_event_counts"] = environment_event_counts
            record["cell_event_counts"] = cell_event_counts
            record["environment_rate"] = {
                key: float(np.mean(values)) if values else None
                for key, values in environment_rates.items()
            }
            record["cell_rate"] = {
                key: float(np.mean(values)) if values else None
                for key, values in cell_rates.items()
            }
        except Exception as exc:  # preserve the failed replicate as a receipt
            record["replicate_status"] = "FAILED"
            record["failure_reason"] = f"{type(exc).__name__}: {exc}"
        records.append(record)
    return BootstrapResult(records=tuple(records), seed=seed, replicate_count=replicate_count)


def generate_activation_qa_draws(
    model: ActivationModel,
    config: ActivationConfig,
) -> list[QADrawSummary]:
    """Generate deterministic predictive activation/K frequency summaries."""

    master_seed = int(config.uncertainty["qa_draw_seed"])
    draw_count = int(config.uncertainty["qa_draw_count"])
    if draw_count <= 0:
        raise ValueError("QA draw count must be positive")
    summaries: list[QADrawSummary] = []
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            for mode in ("EMPIRICAL_CONFIRMED_SUPPORT", "CONDITIONAL_ACTIVE_STRESS"):
                active_count = 0
                k_counts: dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
                for draw_index in range(draw_count):
                    state = sample_block_activation(
                        model,
                        config,
                        environment,
                        band,
                        f"qa-{draw_index}",
                        master_seed,
                        mode,
                    )
                    active_count += int(state.z_active)
                    k_counts[state.k_active] += 1
                summaries.append(QADrawSummary(
                    environment=environment,
                    elevation_band=band,
                    activation_mode=mode,
                    draw_count=draw_count,
                    active_count=active_count,
                    k_counts=k_counts,
                    seed=master_seed,
                ))
    return summaries


def activation_mask(k: int) -> tuple[bool, bool, bool]:
    masks = {
        0: (False, False, False),
        1: (True, False, False),
        2: (True, True, False),
        3: (True, True, True),
    }
    try:
        return masks[int(k)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"K must be one of 0,1,2,3: {k!r}") from exc


def _path_sort_key(path: PathDraw) -> tuple[float, float, float, str]:
    if not math.isfinite(path.relative_delay_ns) or path.relative_delay_ns < 0.0:
        raise ValueError(f"invalid relative delay: {path.relative_delay_ns}")
    if not math.isfinite(path.relative_doppler_hz):
        raise ValueError(f"invalid relative Doppler: {path.relative_doppler_hz}")
    if not math.isfinite(path.relative_amplitude_linear) or path.relative_amplitude_linear < 0.0:
        raise ValueError(f"invalid relative amplitude: {path.relative_amplitude_linear}")
    return (
        path.relative_delay_ns,
        -path.relative_amplitude_linear,
        path.relative_doppler_hz,
        str(path.stable_source_id),
    )


def canonicalize_paths(paths: Sequence[PathDraw]) -> list[SlottedPath]:
    if len(paths) not in {1, 2, 3}:
        raise ValueError(f"active NLOS path count must be 1..3: {len(paths)}")
    ordered = sorted(paths, key=_path_sort_key)
    return [SlottedPath(
        nlos_path_id=index,
        path_active=True,
        path_status="ACTIVE_NLOS",
        relative_delay_ns=float(path.relative_delay_ns),
        relative_doppler_hz=float(path.relative_doppler_hz),
        relative_amplitude_linear=float(path.relative_amplitude_linear),
        relative_phase_rad=None if path.relative_phase_rad is None else float(path.relative_phase_rad),
    ) for index, path in enumerate(ordered, start=1)]


def _satellite_id(elevation_band: str) -> str:
    mapping = {"LOW": "Low", "MID": "Mid", "HIGH": "High"}
    if elevation_band not in mapping:
        raise ValueError(f"unknown elevation band: {elevation_band}")
    return mapping[elevation_band]


def emit_internal_slot_rows(
    block: BlockActivationState,
    paths: Sequence[PathDraw],
    *,
    block_length_ms: int,
) -> list[SlotRow]:
    if block_length_ms <= 0:
        raise ValueError("block_length_ms must be positive")
    if block.k_active not in {0, 1, 2, 3} or tuple(block.active_mask) != activation_mask(block.k_active):
        raise ValueError("block K and active mask are inconsistent")
    if bool(block.z_active) != (block.k_active > 0):
        raise ValueError("block Z_active and K_active are inconsistent")
    if len(paths) != block.k_active:
        raise ValueError(f"path count does not match block K: {len(paths)} != {block.k_active}")
    ordered = canonicalize_paths(paths) if paths else []
    by_id = {path.nlos_path_id: path for path in ordered}
    satellite_id = _satellite_id(block.elevation_band)
    rows: list[SlotRow] = []
    for ms in range(1, block_length_ms + 1):
        rows.append(SlotRow(ms, satellite_id, 0, True, "MAIN_EXTERNAL", 0.0, 0.0, 1.0, None))
        for path_id in range(1, 4):
            path = by_id.get(path_id)
            if path is None:
                rows.append(SlotRow(ms, satellite_id, path_id, False, "INACTIVE_NO_PATH", None, None, 0.0, None))
            else:
                rows.append(SlotRow(
                    ms,
                    satellite_id,
                    path_id,
                    True,
                    path.path_status,
                    path.relative_delay_ns,
                    path.relative_doppler_hz,
                    path.relative_amplitude_linear,
                    path.relative_phase_rad,
                ))
    return rows


__all__ = [
    "ActivationModel",
    "ActivationConfig",
    "ActivationEvidence",
    "BetaOccupancyModel",
    "BlockActivationState",
    "ConfirmedEvent",
    "ENVIRONMENTS",
    "ELEVATION_BANDS",
    "EventPathObservation",
    "ExposureWindow",
    "GeometryJoinResult",
    "MultiplicityHierarchy",
    "MultiplicityModel",
    "PathDraw",
    "QADrawSummary",
    "SceneCellExposure",
    "SlottedPath",
    "SlotRow",
    "SourceAudit",
    "Stage0Source",
    "assign_continuity_segments",
    "aggregate_scene_cell_exposure",
    "build_activation_labels",
    "classify_occupancy_support",
    "derive_stream_seed",
    "elevation_band_for",
    "fit_beta_pseudo_posterior",
    "fit_dirichlet_counts",
    "fit_multiplicity_hierarchy",
    "fit_occupancy_hierarchy",
    "join_geometry_grid",
    "load_activation_config",
    "load_confirmed_event_paths",
    "load_confirmed_events",
    "load_stage0_exposure",
    "resolve_stage0_sources",
    "sample_path_count",
    "sample_block_activation",
    "scene_block_bootstrap",
    "generate_activation_qa_draws",
    "sha256_file",
    "verify_frozen_sources",
]
