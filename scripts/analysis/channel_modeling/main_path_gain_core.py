"""Read-only core for the common main-path gain and observable fade model.

The module deliberately consumes GNSS-SDR tracking and verified geometry
metadata only.  It has no raw-IQ, MATLAB, SAGE, or production-pipeline entry
point.  C/N0 is treated as a run-normalized receiver-strength proxy; it is
never presented as calibrated RF power or an isolated physical LOS path.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import optimize, stats


ENVIRONMENTS: tuple[str, ...] = (
    "Urban",
    "Special Reflective",
    "Mountain/Valley",
    "Highway/Open",
)
ELEVATION_BANDS: tuple[str, ...] = ("LOW", "MID", "HIGH")
EXPECTED_SAMPLE_RATE_HZ = 10_230_000
LOCK_THRESHOLD = -0.5
DEFAULT_GAP_LIMIT_S = 0.0025
_BAND_LIMITS: dict[str, tuple[float, float, bool]] = {
    "LOW": (0.0, 30.0, False),
    "MID": (30.0, 60.0, False),
    "HIGH": (60.0, 90.0, True),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _resolve_path(project_root: Path, value: str) -> Path:
    candidate = Path(str(value).strip())
    return candidate if candidate.is_absolute() else project_root / candidate


@dataclass(frozen=True)
class GainFadeConfig:
    """Frozen scientific and execution contract loaded from JSON."""

    model_id: str = "main-path-common-gain-fade-v1"
    model_version: str = "v1"
    sample_rate_hz: int = EXPECTED_SAMPLE_RATE_HZ
    environments: tuple[str, ...] = ENVIRONMENTS
    elevation_bands: tuple[str, ...] = ELEVATION_BANDS
    analysis_bin_ms: int = 20
    short_segment_min_duration_s: float = 2.0
    baseline_window_s: float = 10.0
    baseline_quantile: float = 0.9
    minimum_baseline_points: int = 2
    entry_depth_db: float = 3.0
    entry_sustain_ms: int = 20
    exit_depth_db: float = 1.0
    exit_sustain_ms: int = 100
    geometry_tolerance_s: float = 5.0
    family_tie_tolerance: float = 1e-9
    parent_quantile_count: int = 64
    prior_equivalent_weight: float = 8.0
    rate_parent_exposure_s: float = 30.0
    lag_s: tuple[float, ...] = (0.02, 0.04, 0.1, 0.2, 0.5, 1.0)
    tau_min_s: float = 0.02
    tau_max_s: float = 60.0
    bootstrap_seed: int = 20260826
    bootstrap_replicates: int = 1000
    qa_draw_seed: int = 20260827
    qa_draw_count: int = 4096
    source: Mapping[str, Any] = field(default_factory=dict)
    protected_source: Mapping[str, Any] = field(default_factory=dict)
    execution_policy: Mapping[str, Any] = field(default_factory=dict)
    output_namespace: str = "dataset_generation_logs/channel_modeling/main_path_common_gain_fade_v1_20260826_r1"
    marginal_families: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "normal_gain_db": ("student_t", "normal", "laplace"),
            "fade_depth_db": ("lognormal", "gamma", "weibull"),
            "fade_duration_s": ("lognormal", "gamma", "weibull"),
        }
    )

    @classmethod
    def from_json(cls, path: Path) -> "GainFadeConfig":
        with path.open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        analysis = data.get("analysis_grid", {})
        fade = data.get("fade_rule", {})
        geometry = data.get("geometry", {})
        prior = data.get("hierarchical_prior", {})
        temporal = data.get("temporal_model", {})
        uncertainty = data.get("uncertainty", {})
        source = data.get("source", {})
        policy = data.get("execution_policy", {})
        if int(data.get("sample_rate_hz", 0)) != EXPECTED_SAMPLE_RATE_HZ:
            raise ValueError("only the frozen 10.23 MHz model is supported")
        if tuple(data.get("environments", ())) != ENVIRONMENTS:
            raise ValueError("environment order is not frozen")
        if tuple(data.get("elevation_bands", ())) != ELEVATION_BANDS:
            raise ValueError("elevation-band order is not frozen")
        if bool(geometry.get("interpolation", True)):
            raise ValueError("geometry interpolation must remain disabled")
        if not _parse_bool(policy.get("gold_labels_used_for_selection", False)) is False:
            raise ValueError("gold labels may not select this model")
        if not _parse_bool(policy.get("stage3_stage4_used_for_selection", False)) is False:
            raise ValueError("Stage3/Stage4 may not select this model")
        families = {
            str(name): tuple(str(family) for family in values)
            for name, values in data.get("marginal_families", {}).items()
        }
        return cls(
            model_id=str(data["model_id"]),
            model_version=str(data["model_version"]),
            sample_rate_hz=int(data["sample_rate_hz"]),
            analysis_bin_ms=int(analysis.get("bin_ms", 20)),
            short_segment_min_duration_s=float(analysis.get("short_segment_min_duration_s", 2.0)),
            baseline_window_s=float(analysis.get("baseline_window_s", 10.0)),
            baseline_quantile=float(analysis.get("baseline_quantile", 0.9)),
            minimum_baseline_points=int(analysis.get("minimum_baseline_points", 2)),
            entry_depth_db=float(fade.get("entry_depth_db", 3.0)),
            entry_sustain_ms=int(fade.get("entry_sustain_ms", 20)),
            exit_depth_db=float(fade.get("exit_depth_db", 1.0)),
            exit_sustain_ms=int(fade.get("exit_sustain_ms", 100)),
            geometry_tolerance_s=float(geometry.get("maximum_nearest_delta_s", 5.0)),
            family_tie_tolerance=float(data.get("family_tie_tolerance", 1e-9)),
            parent_quantile_count=int(prior.get("parent_quantile_count", 64)),
            prior_equivalent_weight=float(prior.get("prior_equivalent_weight", 8.0)),
            rate_parent_exposure_s=float(prior.get("rate_parent_exposure_s", 30.0)),
            lag_s=tuple(float(value) for value in temporal.get("lag_s", (0.02, 0.04, 0.1, 0.2, 0.5, 1.0))),
            tau_min_s=float(temporal.get("tau_min_s", 0.02)),
            tau_max_s=float(temporal.get("tau_max_s", 60.0)),
            bootstrap_seed=int(uncertainty.get("bootstrap_seed", 20260826)),
            bootstrap_replicates=int(uncertainty.get("bootstrap_replicates", 1000)),
            qa_draw_seed=int(uncertainty.get("qa_draw_seed", 20260827)),
            qa_draw_count=int(uncertainty.get("qa_draw_count", 4096)),
            source=source,
            protected_source=data.get("protected_source", {}),
            execution_policy=policy,
            output_namespace=str(data["output_namespace"]),
            environments=ENVIRONMENTS,
            elevation_bands=ELEVATION_BANDS,
            marginal_families=families,
        )


@dataclass(frozen=True)
class GainRunInput:
    run_id: str
    scene_id: str
    prn: str
    tracking_channel: int
    acceptance_class: str
    environment: str
    tracking_path: Path
    tracking_sha256: str
    time_origin_utc: datetime | None = None
    geometry_path: Path | None = None


@dataclass(frozen=True)
class TrackingObservation:
    run_id: str
    scene_id: str
    prn: str
    tracking_channel: int
    environment: str
    tracking_path: str
    tracking_sha256: str
    times_s: np.ndarray
    cn0_values: np.ndarray
    lock_values: np.ndarray
    states: tuple[str, ...]
    gap_limit_s: float
    median_interval_s: float
    valid_count: int
    inconclusive_count: int


@dataclass(frozen=True)
class GeometryJoinResult:
    valid: bool
    elevation_deg: float | None
    azimuth_deg: float | None
    snr_db_hz: float | None
    source_utc: str | None
    delta_s: float | None
    status: str
    reason: str | None = None


@dataclass
class GainGridRow:
    run_id: str
    scene_id: str
    prn: str
    tracking_channel: int
    environment: str
    time_s: float
    time_bin_index: int
    cn0_db_hz: float | None
    c_ref_run_db_hz: float | None
    common_gain_db: float | None
    common_gain_linear: float | None
    local_upper_db_hz: float | None
    fade_depth_db: float | None
    lock_state: str
    continuity_valid: bool
    elevation_deg: float | None
    elevation_band: str | None
    geometry_join_valid: bool
    geometry_join_status: str
    geometry_time_delta_s: float | None
    baseline_status: str


@dataclass(frozen=True)
class BaselineValue:
    upper_db_hz: float | None
    status: str
    window_count: int


@dataclass(frozen=True)
class FadeEvent:
    event_id: str
    run_id: str
    scene_id: str
    environment: str
    elevation_band: str | None
    start_time_s: float
    end_time_s: float
    max_observed_depth_db: float | None
    right_censored: bool
    censor_reason: str | None
    missing_depth_count: int
    elevation_cell_eligible: bool

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_time_s - self.start_time_s)


@dataclass(frozen=True)
class FadeExtractionResult:
    events: tuple[FadeEvent, ...]
    missing_rows: int


@dataclass(frozen=True)
class FamilyFit:
    family: str
    parameters: Mapping[str, float]
    log_likelihood: float
    converged: bool


@dataclass(frozen=True)
class FamilySelection:
    parameter: str
    selected_family: str
    scores: Mapping[str, float]
    held_out_groups: tuple[str, ...]
    row_random_split_used: bool


@dataclass(frozen=True)
class CellGainMarginal:
    environment: str
    elevation_band: str
    family: str
    parameters: Mapping[str, float]
    support_status: str
    parameter_source: str
    direct_row_count: int


@dataclass(frozen=True)
class CorrelationFit:
    tau_s: float
    pair_count: int
    cross_gap_pairs: int
    fit_status: str


def elevation_band_for(elevation_deg: float) -> str:
    if not math.isfinite(float(elevation_deg)) or not 0.0 <= float(elevation_deg) <= 90.0:
        raise ValueError(f"elevation outside [0,90]: {elevation_deg}")
    for band, (lower, upper, inclusive_upper) in _BAND_LIMITS.items():
        if lower <= elevation_deg < upper or (inclusive_upper and lower <= elevation_deg <= upper):
            return band
    raise ValueError(f"cannot classify elevation {elevation_deg}")


def tracking_sample_to_utc(sample_count: float, sample_rate_hz: int, origin: datetime) -> datetime:
    if sample_rate_hz <= 0 or not math.isfinite(float(sample_count)):
        raise ValueError("invalid sample time")
    return origin + timedelta(seconds=float(sample_count) / float(sample_rate_hz))


def join_nearest_geometry(
    records: Sequence[Mapping[str, Any]],
    prn: str,
    utc_seconds: float,
    *,
    tolerance_s: float = 5.0,
) -> GeometryJoinResult:
    candidates = [row for row in records if str(row.get("prn", "")) == prn]
    if not candidates:
        return GeometryJoinResult(False, None, None, None, None, None, "unavailable", "geometry_prn_missing_in_timeseries")
    valid_candidates = [row for row in candidates if _finite_float(row.get("utc_seconds")) is not None]
    if not valid_candidates:
        return GeometryJoinResult(False, None, None, None, None, None, "unavailable", "geometry_time_invalid")
    nearest = min(valid_candidates, key=lambda row: abs(float(row["utc_seconds"]) - float(utc_seconds)))
    delta = abs(float(nearest["utc_seconds"]) - float(utc_seconds))
    if delta > tolerance_s:
        return GeometryJoinResult(False, None, None, None, None, delta, "inconclusive", "nearest_geometry_delta_exceeds_5s")
    elevation = _finite_float(nearest.get("elevation_deg"))
    azimuth = _finite_float(nearest.get("azimuth_deg"))
    snr = _finite_float(nearest.get("snr_db_hz"))
    if elevation is None or azimuth is None:
        return GeometryJoinResult(False, None, None, snr, str(nearest.get("utc_time", "")) or None, delta, "unavailable", "geometry_values_missing")
    return GeometryJoinResult(
        True,
        elevation,
        azimuth,
        snr,
        str(nearest.get("utc_time", "")) or None,
        delta,
        "valid",
    )


def sample_lock_states(
    lock_values: Sequence[float],
    times_s: Sequence[float],
    *,
    threshold: float = LOCK_THRESHOLD,
    gap_limit_s: float = DEFAULT_GAP_LIMIT_S,
) -> list[str]:
    locks = np.asarray(lock_values, dtype=float).reshape(-1)
    times = np.asarray(times_s, dtype=float).reshape(-1)
    if locks.size != times.size:
        raise ValueError("lock and time arrays must have equal length")
    result: list[str] = []
    for index, value in enumerate(locks):
        if not math.isfinite(float(value)) or not math.isfinite(float(times[index])):
            state = "INCONCLUSIVE"
        elif float(value) < threshold:
            state = "LOCK_BAD"
        else:
            state = "LOCK_GOOD"
        if index > 0 and math.isfinite(float(times[index - 1])) and math.isfinite(float(times[index])):
            if float(times[index]) - float(times[index - 1]) > gap_limit_s:
                state = "INCONCLUSIVE_GAP"
        result.append(state)
    return result


def _median_positive_interval(times_s: np.ndarray) -> float:
    if times_s.size < 2:
        return 0.001
    diffs = np.diff(times_s)
    positive = diffs[np.isfinite(diffs) & (diffs > 0)]
    return float(np.median(positive)) if positive.size else 0.001


def read_tracking_observation(run: GainRunInput, *, sample_rate_hz: int = EXPECTED_SAMPLE_RATE_HZ) -> TrackingObservation:
    """Read four numeric fields through the existing read-only MATLAB-7.3 reader."""

    helper_dir = Path(__file__).resolve().parents[1] / "rain_gnss_sdr"
    if str(helper_dir) not in sys.path:
        sys.path.insert(0, str(helper_dir))
    from audit_rain_gnss_sdr_mvp import Hdf5MatFile  # type: ignore

    names = ("PRN", "PRN_start_sample_count", "CN0_SNV_dB_Hz", "carrier_lock_test")
    arrays: dict[str, np.ndarray] = {}
    with Hdf5MatFile(run.tracking_path) as mat:
        available = set(mat.links())
        missing = [name for name in names if name not in available]
        if missing:
            raise ValueError(f"tracking MAT missing required fields {missing}: {run.tracking_path}")
        for name in names:
            arrays[name] = np.asarray(mat.read(name)[0]).reshape(-1)
    sizes = {name: int(value.size) for name, value in arrays.items()}
    if len(set(sizes.values())) != 1:
        raise ValueError(f"tracking field lengths differ: {sizes}")
    prn = arrays["PRN"].astype(float)
    sample = arrays["PRN_start_sample_count"].astype(float)
    cn0 = arrays["CN0_SNV_dB_Hz"].astype(float)
    lock = arrays["carrier_lock_test"].astype(float)
    expected_prn = float(run.prn[1:])
    signal_valid = np.isfinite(prn) & (prn == expected_prn) & np.isfinite(sample) & np.isfinite(cn0) & (cn0 > 0)
    if np.count_nonzero(signal_valid) < 2:
        raise ValueError(f"insufficient valid tracking records: {run.tracking_path}")
    times = sample / float(sample_rate_hz)
    valid_times = times[signal_valid]
    if np.any(np.diff(valid_times) < 0):
        raise ValueError(f"tracking sample counter is not monotonic: {run.tracking_path}")
    median_dt = _median_positive_interval(valid_times)
    gap_limit = max(median_dt * 2.5, DEFAULT_GAP_LIMIT_S)
    effective_lock = lock.copy()
    effective_lock[~signal_valid] = np.nan
    states = sample_lock_states(effective_lock, times, gap_limit_s=gap_limit)
    return TrackingObservation(
        run_id=run.run_id,
        scene_id=run.scene_id,
        prn=run.prn,
        tracking_channel=run.tracking_channel,
        environment=run.environment,
        tracking_path=str(run.tracking_path),
        tracking_sha256=run.tracking_sha256,
        times_s=times,
        cn0_values=cn0,
        lock_values=effective_lock,
        states=tuple(states),
        gap_limit_s=gap_limit,
        median_interval_s=median_dt,
        valid_count=int(np.count_nonzero(signal_valid)),
        inconclusive_count=int(times.size - np.count_nonzero(signal_valid)),
    )


def compute_run_reference(observation: TrackingObservation) -> float:
    values = np.asarray(observation.cn0_values, dtype=float).reshape(-1)
    states = np.asarray(observation.states, dtype=object).reshape(-1)
    valid = (states == "LOCK_GOOD") & np.isfinite(values) & (values > 0)
    if not np.any(valid):
        raise ValueError(f"no LOCK_GOOD C/N0 reference for {observation.run_id}")
    return float(np.median(values[valid]))


def db_to_linear_amplitude(gain_db: np.ndarray | Sequence[float]) -> np.ndarray:
    values = np.asarray(gain_db, dtype=float)
    if np.any(~np.isfinite(values)):
        raise ValueError("non-finite dB gain")
    return np.power(10.0, values / 20.0)


def build_analysis_grid(observation: TrackingObservation, *, bin_ms: int = 20) -> list[GainGridRow]:
    if bin_ms <= 0:
        raise ValueError("bin_ms must be positive")
    times = np.asarray(observation.times_s, dtype=float).reshape(-1)
    cn0 = np.asarray(observation.cn0_values, dtype=float).reshape(-1)
    if len(observation.states) != times.size or cn0.size != times.size:
        raise ValueError("tracking arrays and states must have equal length")
    reference = compute_run_reference(observation)
    bin_s = float(bin_ms) / 1000.0
    finite_times = np.isfinite(times)
    groups: dict[int, list[int]] = {}
    for index in np.flatnonzero(finite_times):
        groups.setdefault(int(math.floor(float(times[index]) / bin_s)), []).append(int(index))
    rows: list[GainGridRow] = []
    previous_last_time: float | None = None
    previous_index: int | None = None
    for bin_index in sorted(groups):
        indices = groups[bin_index]
        values = cn0[indices]
        finite_values = values[np.isfinite(values) & (values > 0)]
        if finite_values.size:
            value = float(np.median(finite_values))
            gain = value - reference
            amplitude = float(db_to_linear_amplitude(np.asarray([gain]))[0])
        else:
            value = None
            gain = None
            amplitude = None
        internal_gap = any(
            math.isfinite(float(times[right]))
            and math.isfinite(float(times[left]))
            and float(times[right]) - float(times[left]) > observation.gap_limit_s
            for left, right in zip(indices, indices[1:])
        )
        first_time = float(times[indices[0]])
        gap_before = previous_last_time is not None and first_time - previous_last_time > observation.gap_limit_s
        continuity_valid = not internal_gap and not gap_before
        states = [observation.states[index] for index in indices]
        if all(state == "LOCK_GOOD" for state in states):
            lock_state = "LOCK_GOOD"
        elif any(state == "LOCK_BAD" for state in states):
            lock_state = "LOCK_BAD"
        elif any(state == "INCONCLUSIVE_GAP" for state in states) or gap_before:
            lock_state = "INCONCLUSIVE_GAP"
        else:
            lock_state = "INCONCLUSIVE"
        rows.append(
            GainGridRow(
                run_id=observation.run_id,
                scene_id=observation.scene_id,
                prn=observation.prn,
                tracking_channel=observation.tracking_channel,
                environment=observation.environment,
                time_s=float((bin_index + 0.5) * bin_s),
                time_bin_index=bin_index,
                cn0_db_hz=value,
                c_ref_run_db_hz=reference,
                common_gain_db=gain,
                common_gain_linear=amplitude,
                local_upper_db_hz=None,
                fade_depth_db=None,
                lock_state=lock_state,
                continuity_valid=continuity_valid,
                elevation_deg=None,
                elevation_band=None,
                geometry_join_valid=False,
                geometry_join_status="not_joined",
                geometry_time_delta_s=None,
                baseline_status="gap_boundary" if gap_before else "pending",
            )
        )
        previous_last_time = float(times[indices[-1]])
        previous_index = indices[-1]
    return rows


def _segment_indices(rows: Sequence[GainGridRow], *, bin_s: float = 0.02) -> list[list[int]]:
    segments: list[list[int]] = []
    current: list[int] = []
    previous_time: float | None = None
    for index, row in enumerate(rows):
        break_before = (
            bool(current)
            and (
                not row.continuity_valid
                or previous_time is None
                or row.time_s - previous_time > max(DEFAULT_GAP_LIMIT_S, bin_s * 1.5)
            )
        )
        if break_before:
            segments.append(current)
            current = []
        current.append(index)
        previous_time = row.time_s
    if current:
        segments.append(current)
    return segments


def compute_local_upper_baseline(
    rows: Sequence[GainGridRow],
    *,
    window_s: float = 10.0,
    quantile: float = 0.9,
    short_segment_min_duration_s: float = 2.0,
    minimum_points: int = 2,
) -> list[BaselineValue]:
    if not rows:
        return []
    if not 0.0 < quantile < 1.0:
        raise ValueError("baseline quantile must be in (0,1)")
    result = [BaselineValue(None, "baseline_inconclusive", 0) for _ in rows]
    for segment in _segment_indices(rows):
        duration = rows[segment[-1]].time_s - rows[segment[0]].time_s + 0.02
        if duration < short_segment_min_duration_s:
            for index in segment:
                if rows[index].baseline_status != "gap_boundary":
                    rows[index].baseline_status = "baseline_inconclusive"
                result[index] = BaselineValue(None, "baseline_inconclusive", 0)
            continue
        segment_short = duration < window_s
        for index in segment:
            row = rows[index]
            if not row.continuity_valid:
                row.baseline_status = "gap_boundary"
                result[index] = BaselineValue(None, "gap_boundary", 0)
                continue
            if segment_short:
                candidates = [
                    rows[item].cn0_db_hz
                    for item in segment
                    if rows[item].lock_state == "LOCK_GOOD" and rows[item].cn0_db_hz is not None
                ]
            else:
                half = window_s / 2.0
                candidates = [
                    rows[item].cn0_db_hz
                    for item in segment
                    if abs(rows[item].time_s - row.time_s) <= half
                    and rows[item].lock_state == "LOCK_GOOD"
                    and rows[item].cn0_db_hz is not None
                ]
            if len(candidates) < minimum_points:
                row.baseline_status = "baseline_inconclusive"
                result[index] = BaselineValue(None, "baseline_inconclusive", len(candidates))
                continue
            upper = float(np.quantile(np.asarray(candidates, dtype=float), quantile))
            row.local_upper_db_hz = upper
            if row.cn0_db_hz is not None and row.lock_state == "LOCK_GOOD":
                row.fade_depth_db = max(0.0, upper - row.cn0_db_hz)
            row.baseline_status = "valid"
            result[index] = BaselineValue(upper, "valid", len(candidates))
    return result


def extract_fade_events(
    rows: Sequence[GainGridRow],
    config: GainFadeConfig | None = None,
) -> FadeExtractionResult:
    config = config or GainFadeConfig()
    if not rows:
        return FadeExtractionResult((), 0)
    bin_s = config.analysis_bin_ms / 1000.0
    entry_bins = max(1, int(math.ceil((config.entry_sustain_ms / 1000.0) / bin_s)))
    exit_bins = max(1, int(math.ceil((config.exit_sustain_ms / 1000.0) / bin_s)))
    events: list[FadeEvent] = []
    missing_rows = 0
    active: dict[str, Any] | None = None
    low_count = 0

    def finish(end_time: float, censored: bool, reason: str | None) -> None:
        nonlocal active
        if active is None:
            return
        events.append(
            FadeEvent(
                event_id=f"{active['run_id']}:fade:{len(events) + 1:04d}",
                run_id=active["run_id"],
                scene_id=active["scene_id"],
                environment=active["environment"],
                elevation_band=active["elevation_band"],
                start_time_s=float(active["start_time_s"]),
                end_time_s=float(end_time),
                max_observed_depth_db=(
                    float(active["max_depth"]) if active["max_depth"] is not None else None
                ),
                right_censored=bool(censored),
                censor_reason=reason,
                missing_depth_count=int(active["missing"]),
                elevation_cell_eligible=bool(active["elevation_cell_eligible"]),
            )
        )
        active = None

    for row_index, row in enumerate(rows):
        depth = row.fade_depth_db
        if active is not None and depth is None:
            active["missing"] += 1
            missing_rows += 1
        if row.lock_state == "LOCK_BAD":
            finish(row.time_s, True, "lock_bad_transition")
            low_count = 0
            continue
        if not row.continuity_valid or row.lock_state.startswith("INCONCLUSIVE"):
            if active is not None:
                finish(row.time_s, True, "continuity_gap")
            low_count = 0
            continue
        high = depth is not None and depth >= config.entry_depth_db
        low = depth is not None and depth <= config.exit_depth_db
        if active is None:
            if high:
                start_index = row_index
                prior = rows[max(0, start_index - entry_bins + 1): start_index + 1]
                if len(prior) >= entry_bins and all(
                    item.fade_depth_db is not None
                    and item.fade_depth_db >= config.entry_depth_db
                    and item.lock_state == "LOCK_GOOD"
                    and item.continuity_valid
                    for item in prior
                ):
                    bands = {item.elevation_band for item in prior}
                    active = {
                        "run_id": row.run_id,
                        "scene_id": row.scene_id,
                        "environment": row.environment,
                        "elevation_band": row.elevation_band if len(bands) == 1 else None,
                        "elevation_cell_eligible": len(bands) <= 1 and None not in bands,
                        "start_time_s": prior[0].time_s,
                        "max_depth": max(float(item.fade_depth_db) for item in prior),
                        "missing": 0,
                    }
            low_count = 0
            continue
        if depth is not None and active["max_depth"] is not None:
            active["max_depth"] = max(float(active["max_depth"]), float(depth))
        if low:
            low_count += 1
            if low_count >= exit_bins:
                finish(row.time_s, False, None)
                low_count = 0
        else:
            low_count = 0
    if active is not None:
        finish(rows[-1].time_s + bin_s, True, "record_end")
    return FadeExtractionResult(tuple(events), missing_rows)


def _normal_parameters(values: np.ndarray, weights: np.ndarray | None = None) -> dict[str, float]:
    if weights is None:
        mean = float(np.mean(values))
        scale = float(np.std(values, ddof=0))
    else:
        total = float(np.sum(weights))
        mean = float(np.sum(values * weights) / total)
        scale = float(np.sqrt(np.sum(weights * (values - mean) ** 2) / total))
    return {"loc": mean, "scale": max(scale, 1e-9)}


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values, kind="mergesort")
    ordered_values = values[order]
    ordered_weights = weights[order]
    cutoff = 0.5 * float(np.sum(ordered_weights))
    index = int(np.searchsorted(np.cumsum(ordered_weights), cutoff, side="left"))
    return float(ordered_values[min(index, ordered_values.size - 1)])


def _scene_balanced_weights(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    """Give each represented scene equal total likelihood weight."""

    counts: dict[str, int] = {}
    for row in rows:
        scene = str(row.get("scene_id", ""))
        counts[scene] = counts.get(scene, 0) + 1
    scene_count = max(len(counts), 1)
    return np.asarray(
        [1.0 / (scene_count * counts[str(row.get("scene_id", ""))]) for row in rows],
        dtype=float,
    )


def _fit_uncensored_family(values: np.ndarray, family: str, weights: np.ndarray | None = None) -> dict[str, float]:
    if values.size == 0:
        raise ValueError("cannot fit an empty sample")
    if family == "normal":
        return _normal_parameters(values, weights)
    if family == "laplace":
        if weights is None:
            location = float(np.median(values))
            scale = float(np.mean(np.abs(values - location)))
        else:
            location = _weighted_median(values, weights)
            scale = float(np.sum(weights * np.abs(values - location)) / np.sum(weights))
        return {"loc": location, "scale": max(scale, 1e-9)}
    if family == "student_t":
        df, loc, scale = stats.t.fit(values)
        return {"df": float(np.clip(df, 2.1, 100.0)), "loc": float(loc), "scale": max(float(scale), 1e-9)}
    positive = np.asarray(values, dtype=float)
    if np.any(positive <= 0):
        raise ValueError(f"{family} requires strictly positive observations")
    if family == "lognormal":
        shape, loc, scale = stats.lognorm.fit(positive, floc=0.0)
        return {"shape": float(shape), "loc": 0.0, "scale": max(float(scale), 1e-12)}
    if family == "gamma":
        shape, loc, scale = stats.gamma.fit(positive, floc=0.0)
        return {"shape": float(shape), "loc": 0.0, "scale": max(float(scale), 1e-12)}
    if family == "weibull":
        shape, loc, scale = stats.weibull_min.fit(positive, floc=0.0)
        return {"shape": float(shape), "loc": 0.0, "scale": max(float(scale), 1e-12)}
    raise ValueError(f"unknown distribution family {family}")


def _family_distribution(fit: FamilyFit) -> stats.rv_continuous:
    if fit.family == "normal":
        return stats.norm(loc=fit.parameters["loc"], scale=fit.parameters["scale"])
    if fit.family == "laplace":
        return stats.laplace(loc=fit.parameters["loc"], scale=fit.parameters["scale"])
    if fit.family == "student_t":
        return stats.t(df=fit.parameters["df"], loc=fit.parameters["loc"], scale=fit.parameters["scale"])
    if fit.family == "lognormal":
        return stats.lognorm(s=fit.parameters["shape"], loc=0.0, scale=fit.parameters["scale"])
    if fit.family == "gamma":
        return stats.gamma(a=fit.parameters["shape"], loc=0.0, scale=fit.parameters["scale"])
    if fit.family == "weibull":
        return stats.weibull_min(c=fit.parameters["shape"], loc=0.0, scale=fit.parameters["scale"])
    raise ValueError(fit.family)


def fit_family(
    values: Sequence[float],
    family: str,
    *,
    right_censored: Sequence[bool] | None = None,
    weights: Sequence[float] | None = None,
) -> FamilyFit:
    data = np.asarray(values, dtype=float).reshape(-1)
    if data.size == 0 or np.any(~np.isfinite(data)):
        raise ValueError("family fit requires finite values")
    censored = np.zeros(data.size, dtype=bool) if right_censored is None else np.asarray(right_censored, dtype=bool).reshape(-1)
    if censored.size != data.size:
        raise ValueError("censor flags have wrong length")
    sample_weights = np.ones(data.size, dtype=float) if weights is None else np.asarray(weights, dtype=float).reshape(-1)
    if sample_weights.size != data.size or np.any(~np.isfinite(sample_weights)) or np.any(sample_weights <= 0):
        raise ValueError("weights must be finite and strictly positive")
    uncensored = data[~censored]
    uncensored_weights = sample_weights[~censored]
    if uncensored.size == 0:
        raise ValueError("at least one exact observation is required")
    parameters = _fit_uncensored_family(uncensored, family, uncensored_weights if weights is not None else None)
    if np.any(censored) or weights is not None:
        keys = tuple(parameters)
        start = np.asarray([parameters[key] for key in keys], dtype=float)

        def unpack(vector: np.ndarray) -> dict[str, float]:
            result = dict(parameters)
            for key, value in zip(keys, vector):
                if family in {"lognormal", "gamma", "weibull"} and key == "loc":
                    result[key] = 0.0
                elif key in {"scale", "shape", "df"}:
                    result[key] = max(float(value), 1e-8)
                else:
                    result[key] = float(value)
            if "df" in result:
                result["df"] = float(np.clip(result["df"], 2.1, 100.0))
            return result

        def objective(vector: np.ndarray) -> float:
            candidate = FamilyFit(family, unpack(vector), 0.0, False)
            distribution = _family_distribution(candidate)
            log_pdf = distribution.logpdf(uncensored)
            log_survival = distribution.logsf(data[censored])
            total = np.sum(uncensored_weights * log_pdf) + np.sum(sample_weights[censored] * log_survival)
            return float(-total) if math.isfinite(float(total)) else 1e100

        fitted = optimize.minimize(objective, start, method="Nelder-Mead", options={"maxiter": 2000})
        parameters = unpack(fitted.x)
        converged = bool(fitted.success)
    else:
        converged = True
    fit = FamilyFit(family, parameters, 0.0, converged)
    distribution = _family_distribution(fit)
    total = np.sum(uncensored_weights * distribution.logpdf(uncensored)) + np.sum(sample_weights[censored] * distribution.logsf(data[censored]))
    return FamilyFit(family, parameters, float(total), converged and math.isfinite(float(total)))


def select_family_by_scene(
    rows: Sequence[Mapping[str, Any]],
    parameter: str,
    candidates: Sequence[str],
) -> FamilySelection:
    groups = sorted({str(row.get("scene_id", "")) for row in rows if row.get(parameter) is not None})
    if not groups:
        raise ValueError(f"no groups for {parameter}")
    scores: dict[str, float] = {}
    for family in candidates:
        fold_scores: list[float] = []
        failed = False
        for holdout in groups:
            training = [row for row in rows if str(row.get("scene_id", "")) != holdout and row.get(parameter) is not None]
            validation = [row for row in rows if str(row.get("scene_id", "")) == holdout and row.get(parameter) is not None]
            if not training or not validation:
                failed = True
                break
            try:
                training_weights = _scene_balanced_weights(training)
                fit = fit_family([float(row[parameter]) for row in training], family, weights=training_weights)
                distribution = _family_distribution(fit)
                validation_values = np.asarray([float(row[parameter]) for row in validation], dtype=float)
                fold_scores.append(float(np.mean(distribution.logpdf(validation_values))))
            except (ValueError, FloatingPointError):
                failed = True
                break
        scores[family] = float("-inf") if failed else float(np.mean(fold_scores))
    order = {name: index for index, name in enumerate(candidates)}
    selected = min(candidates, key=lambda name: (-scores.get(name, float("-inf")), order[name]))
    if not math.isfinite(scores[selected]):
        raise ValueError(f"no valid family for {parameter}")
    return FamilySelection(parameter, selected, scores, tuple(groups), False)


def _support_status(row_count: int, scene_count: int, exposure_s: float = 0.0, event_count: int | None = None) -> str:
    if row_count <= 0 or exposure_s <= 0:
        return "PRIOR_ONLY"
    if scene_count >= 2 and exposure_s >= 60.0 and (event_count is None or event_count >= 10):
        return "DATA_SUPPORTED_WITH_GROUPED_VALIDATION"
    if scene_count <= 1 or (event_count is not None and event_count <= 2):
        return "PRIOR_DOMINANT"
    return "SPARSE_PARTIAL_POOLING"


def fit_hierarchical_gain_marginals(
    rows: Sequence[GainGridRow],
    *,
    environments: Sequence[str] = ENVIRONMENTS,
    elevation_bands: Sequence[str] = ELEVATION_BANDS,
) -> dict[tuple[str, str], CellGainMarginal]:
    valid = [row for row in rows if row.common_gain_db is not None and row.lock_state == "LOCK_GOOD"]
    env_parent: dict[str, dict[str, float]] = {}
    for environment in environments:
        values = np.asarray([row.common_gain_db for row in valid if row.environment == environment], dtype=float)
        env_parent[environment] = _normal_parameters(values) if values.size else {"loc": 0.0, "scale": 1.0}
    result: dict[tuple[str, str], CellGainMarginal] = {}
    for environment in environments:
        for band in elevation_bands:
            direct = [row for row in valid if row.environment == environment and row.elevation_band == band and row.geometry_join_valid]
            if direct:
                values = np.asarray([row.common_gain_db for row in direct], dtype=float)
                parameters = _normal_parameters(values)
                source = "direct_cell"
                support = _support_status(len(direct), len({row.scene_id for row in direct}), exposure_s=len(direct) * 0.02)
            else:
                parameters = dict(env_parent[environment])
                source = "environment_parent_only"
                support = "PRIOR_ONLY"
            result[(environment, band)] = CellGainMarginal(
                environment,
                band,
                "normal",
                parameters,
                support,
                source,
                len(direct),
            )
    return result


def fit_latent_correlation_time(
    rows: Sequence[GainGridRow],
    *,
    lag_s: Sequence[float] = (0.02, 0.04, 0.1, 0.2, 0.5, 1.0),
    tau_min_s: float = 0.02,
    tau_max_s: float = 60.0,
) -> CorrelationFit:
    valid = [
        row for row in rows
        if row.common_gain_db is not None and row.lock_state == "LOCK_GOOD" and row.continuity_valid
    ]
    pairs: list[tuple[float, float, float]] = []
    cross_gap = 0
    continuity_gap_limit = max(DEFAULT_GAP_LIMIT_S, 0.02 * 1.5)
    for left, right in zip(rows, rows[1:]):
        if left.run_id != right.run_id or right.time_s <= left.time_s:
            continue
        dt = right.time_s - left.time_s
        if dt > continuity_gap_limit:
            if (
                left.common_gain_db is not None
                and right.common_gain_db is not None
                and left.lock_state == "LOCK_GOOD"
                and right.lock_state == "LOCK_GOOD"
                and left.continuity_valid
                and right.continuity_valid
            ):
                cross_gap += 1
            continue
        if left.common_gain_db is None or right.common_gain_db is None or left.lock_state != "LOCK_GOOD" or right.lock_state != "LOCK_GOOD" or not left.continuity_valid or not right.continuity_valid:
            continue
        pairs.append((dt, float(left.common_gain_db), float(right.common_gain_db)))
    if len(pairs) < 3:
        return CorrelationFit(tau_min_s, len(pairs), cross_gap, "INCONCLUSIVE")
    observed_lags: list[float] = []
    correlations: list[float] = []
    for lag in lag_s:
        selected = [(x, y) for dt, x, y in pairs if abs(dt - lag) <= max(0.5 * lag, 0.005)]
        if len(selected) >= 3:
            left = np.asarray([item[0] for item in selected], dtype=float)
            right = np.asarray([item[1] for item in selected], dtype=float)
            std_left = float(np.std(left))
            std_right = float(np.std(right))
            if std_left > 0 and std_right > 0:
                corr = float(np.corrcoef(left, right)[0, 1])
                if math.isfinite(corr) and 0.0 < corr < 1.0:
                    observed_lags.append(float(lag))
                    correlations.append(corr)
    if not correlations:
        return CorrelationFit(tau_min_s, len(pairs), cross_gap, "INCONCLUSIVE")
    tau = float(np.median(-np.asarray(observed_lags) / np.log(np.clip(correlations, 1e-6, 1 - 1e-6))))
    return CorrelationFit(float(np.clip(tau, tau_min_s, tau_max_s)), len(pairs), cross_gap, "FITTED")


def resolve_gain_model_runs(project_root: Path, config: GainFadeConfig) -> list[GainRunInput]:
    source = config.source
    sage_rows = read_csv_rows(project_root / Path(str(source["sage_runs_relative_path"])))
    eligibility_rows = read_csv_rows(project_root / Path(str(source["modeling_run_eligibility_relative_path"])))
    scene_rows = read_csv_rows(project_root / Path(str(source["scene_context_relative_path"])))
    time_rows = read_csv_rows(project_root / Path(str(source["time_alignment_relative_path"])))
    eligible = {row.get("run_id", ""): row for row in eligibility_rows if _parse_bool(row.get("include_in_environment_modeling"))}
    scenes = {row.get("scene_id", ""): row for row in scene_rows}
    origins: dict[str, datetime] = {}
    for row in time_rows:
        value = row.get("recording_time_origin_utc", "")
        if row.get("verified") == "1" and value:
            origins[row.get("scene_id", "")] = datetime.fromisoformat(value.replace("Z", "+00:00"))
    result: list[GainRunInput] = []
    for row in sage_rows:
        run_id = row.get("run_id", "")
        if run_id not in eligible:
            continue
        scene_id = row.get("scene_id", "")
        track = _resolve_path(project_root, row.get("tracking_file_relpath", ""))
        if not track.is_file() or track.stat().st_size <= 0:
            raise FileNotFoundError(f"tracking input missing: {track}")
        environment = scenes.get(scene_id, {}).get("environment_class", "")
        if environment not in ENVIRONMENTS:
            raise ValueError(f"missing/unknown environment for {run_id}: {environment}")
        channel = int(row.get("tracking_channel", ""))
        prn = row.get("prn", "")
        geometry = project_root / "scenes" / scene_id / "satellite" / f"{scene_id}_satellite_elevation_timeseries.csv"
        result.append(
            GainRunInput(
                run_id=run_id,
                scene_id=scene_id,
                prn=prn,
                tracking_channel=channel,
                acceptance_class=row.get("acceptance_class", ""),
                environment=environment,
                tracking_path=track,
                tracking_sha256=sha256_file(track),
                time_origin_utc=origins.get(scene_id),
                geometry_path=geometry,
            )
        )
    return sorted(result, key=lambda item: item.run_id)


def sample_normal_common_gain(
    parameters: Mapping[str, float],
    duration_ms: int,
    *,
    seed: int,
    tau_s: float,
) -> np.ndarray:
    if duration_ms < 0:
        raise ValueError("duration_ms must be non-negative")
    rng = np.random.default_rng(seed)
    count = int(duration_ms)
    if count == 0:
        return np.empty(0, dtype=float)
    loc = float(parameters.get("loc", 0.0))
    scale = max(float(parameters.get("scale", 1.0)), 1e-9)
    rho = math.exp(-0.001 / max(float(tau_s), 1e-9))
    innovation = math.sqrt(max(1.0 - rho * rho, 1e-15))
    latent = np.empty(count, dtype=float)
    latent[0] = rng.normal()
    for index in range(1, count):
        latent[index] = rho * latent[index - 1] + innovation * rng.normal()
    return loc + scale * latent


def json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
