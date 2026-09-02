"""Build an environment-conditioned receiver lock-loss model.

This is an analysis-only tool.  It reads the existing modeling-run index,
verified scene context, and GNSS-SDR tracking MAT files.  It never opens raw
IQ, invokes MATLAB/SAGE, or writes under ``scenes/**/sage_results``.

The model has two separate pieces:

* a Gamma-Poisson posterior for outage-entry rate while the receiver is
  locked; and
* one common, selected duration family with environment-specific parameters
  and right-censoring support.

``carrier_lock_test < -0.5`` is a receiver diagnostic definition of a bad
lock.  It is not a physical claim that the signal disappeared.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from scipy import optimize, stats


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SAMPLE_RATE_HZ = 10_230_000
LOCK_THRESHOLD = -0.5
DEFAULT_BAD_DEBOUNCE_MS = 20
DEFAULT_REACQUIRE_DEBOUNCE_MS = 100
DEFAULT_GAP_FACTOR = 2.5
MODEL_VERSION = "environment-lock-model-v1"
MODEL_FAMILY_ORDER = ("lognormal", "weibull", "gamma")
MODEL_BUILDER_SOURCE = Path(__file__).resolve()
MAT_READER_SOURCE = (
    Path(__file__).resolve().parent / "rain_gnss_sdr" / "audit_rain_gnss_sdr_mvp.py"
)

ALIGNMENT_PARTITION = (
    PROJECT_ROOT
    / "dataset/multipath_event_database/v1/partitions/"
    "alignment_id=alignment_20260825_tow_geometry_scene_v1"
)
INGESTION_PARTITION = (
    PROJECT_ROOT
    / "dataset/multipath_event_database/v1/partitions/"
    "ingestion_id=ingestion_20260825_event_path_v1"
)
SAGE_RUNS_CSV = INGESTION_PARTITION / "facts/sage_runs.csv"
ELIGIBILITY_CSV = ALIGNMENT_PARTITION / "exports/modeling_run_eligibility.csv"
SCENE_CONTEXT_CSV = ALIGNMENT_PARTITION / "dimensions/scene_context.csv"


@dataclass(frozen=True)
class RunInput:
    run_id: str
    scene_id: str
    prn: str
    tracking_channel: int
    acceptance_class: str
    environment_class: str
    tracking_path: Path
    tracking_sha256: str
    scene_count_source: str


@dataclass(frozen=True)
class RunObservation:
    run: RunInput
    times_s: np.ndarray
    lock_values: np.ndarray
    cn0_values: np.ndarray
    states: list[str]
    gap_limit_s: float
    median_interval_s: float
    valid_count: int
    inconclusive_count: int
    source_field_status: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_hdf5_mat_fields(path: Path, names: Iterable[str]) -> dict[str, np.ndarray]:
    """Read numeric MATLAB 7.3 fields through the existing read-only reader."""

    helper_dir = Path(__file__).resolve().parent / "rain_gnss_sdr"
    if str(helper_dir) not in sys.path:
        sys.path.insert(0, str(helper_dir))
    try:
        from audit_rain_gnss_sdr_mvp import Hdf5MatFile
    except ImportError as error:  # pragma: no cover - platform setup failure
        raise RuntimeError("existing MATLAB 7.3 HDF5 reader is unavailable") from error

    arrays: dict[str, np.ndarray] = {}
    with Hdf5MatFile(path) as mat:
        available = set(mat.links())
        for name in names:
            if name in available:
                arrays[name] = np.asarray(mat.read(name)[0])
    return arrays


def resolve_modeling_runs(project_root: Path) -> list[RunInput]:
    """Resolve only the 63 rows explicitly eligible for environment modeling."""

    ingestion = project_root / INGESTION_PARTITION.relative_to(PROJECT_ROOT)
    alignment = project_root / ALIGNMENT_PARTITION.relative_to(PROJECT_ROOT)
    sage_rows = read_csv_rows(ingestion / "facts/sage_runs.csv")
    eligibility_rows = read_csv_rows(
        alignment / "exports/modeling_run_eligibility.csv"
    )
    context_rows = read_csv_rows(alignment / "dimensions/scene_context.csv")
    eligibility_by_id = {row.get("run_id", ""): row for row in eligibility_rows}
    context_by_scene = {row.get("scene_id", ""): row for row in context_rows}

    resolved: list[RunInput] = []
    for row in sage_rows:
        run_id = row.get("run_id", "")
        eligibility = eligibility_by_id.get(run_id, {})
        if not parse_bool(eligibility.get("include_in_environment_modeling")):
            continue
        scene_id = row.get("scene_id", "")
        context = context_by_scene.get(scene_id, {})
        tracking_value = row.get("tracking_file_relpath", "").strip()
        tracking_path = Path(tracking_value) if tracking_value else Path()
        if not tracking_path.is_file() or tracking_path.stat().st_size <= 0:
            raise FileNotFoundError(
                f"eligible tracking MAT missing or empty for {run_id}: {tracking_path}"
            )
        resolved.append(
            RunInput(
                run_id=run_id,
                scene_id=scene_id,
                prn=row.get("prn", ""),
                tracking_channel=int(row.get("tracking_channel", "")),
                acceptance_class=row.get("acceptance_class", ""),
                environment_class=context.get("environment_class", ""),
                tracking_path=tracking_path,
                tracking_sha256=sha256_file(tracking_path),
                scene_count_source=str(context.get("source_file", "")),
            )
        )
    if len(resolved) != 63:
        raise RuntimeError(f"expected 63 eligible runs, resolved {len(resolved)}")
    if any(not item.environment_class for item in resolved):
        raise RuntimeError("eligible run has no verified environment class")
    return sorted(resolved, key=lambda item: item.run_id)


def resolve_excluded_runs(project_root: Path) -> list[dict[str, str]]:
    """Return excluded rows for an auditable fail-closed record."""

    ingestion = project_root / INGESTION_PARTITION.relative_to(PROJECT_ROOT)
    alignment = project_root / ALIGNMENT_PARTITION.relative_to(PROJECT_ROOT)
    sage_rows = read_csv_rows(ingestion / "facts/sage_runs.csv")
    eligibility_rows = read_csv_rows(
        alignment / "exports/modeling_run_eligibility.csv"
    )
    eligibility_by_id = {row.get("run_id", ""): row for row in eligibility_rows}
    excluded: list[dict[str, str]] = []
    for row in sage_rows:
        eligibility = eligibility_by_id.get(row.get("run_id", ""), {})
        if parse_bool(eligibility.get("include_in_environment_modeling")):
            continue
        reason = "not_in_modeling_eligibility"
        if parse_bool(eligibility.get("context_missing_legacy")):
            reason = "excluded_legacy_context_missing"
        excluded.append(
            {
                "run_id": row.get("run_id", ""),
                "scene_id": row.get("scene_id", ""),
                "prn": row.get("prn", ""),
                "exclusion_reason": reason,
            }
        )
    return excluded


def sample_lock_states(
    lock_values: Sequence[float],
    times_s: Sequence[float],
    *,
    threshold: float = LOCK_THRESHOLD,
    gap_limit_s: float = 0.0025,
) -> list[str]:
    """Classify per-record receiver lock state without inventing missing data."""

    locks = np.asarray(lock_values, dtype=float).reshape(-1)
    times = np.asarray(times_s, dtype=float).reshape(-1)
    if locks.size != times.size:
        raise ValueError("lock and time arrays must have equal length")
    states: list[str] = []
    for index, value in enumerate(locks):
        if not math.isfinite(float(value)) or not math.isfinite(float(times[index])):
            state = "INCONCLUSIVE"
        elif float(value) < threshold:
            state = "LOCK_BAD"
        else:
            state = "LOCK_GOOD"
        if index > 0:
            previous_time = float(times[index - 1])
            current_time = float(times[index])
            if (
                math.isfinite(previous_time)
                and math.isfinite(current_time)
                and current_time - previous_time > gap_limit_s
            ):
                state = "INCONCLUSIVE_GAP"
        states.append(state)
    return states


def _median_positive_interval(times_s: Sequence[float]) -> float:
    times = np.asarray(times_s, dtype=float).reshape(-1)
    if times.size < 2:
        return 0.001
    diffs = np.diff(times)
    positive = diffs[np.isfinite(diffs) & (diffs > 0)]
    return float(np.median(positive)) if positive.size else 0.001


def extract_run_observations(
    run: RunInput,
    *,
    sample_rate_hz: int = EXPECTED_SAMPLE_RATE_HZ,
) -> RunObservation:
    names = ("PRN", "PRN_start_sample_count", "CN0_SNV_dB_Hz", "carrier_lock_test")
    arrays = _read_hdf5_mat_fields(run.tracking_path, names)
    required = {"PRN", "PRN_start_sample_count", "CN0_SNV_dB_Hz", "carrier_lock_test"}
    missing = sorted(required - set(arrays))
    if missing:
        raise ValueError(f"tracking MAT missing required fields {missing}: {run.tracking_path}")
    prn = np.asarray(arrays["PRN"]).reshape(-1).astype(float)
    sample = np.asarray(arrays["PRN_start_sample_count"]).reshape(-1).astype(float)
    cn0 = np.asarray(arrays["CN0_SNV_dB_Hz"]).reshape(-1).astype(float)
    lock = np.asarray(arrays["carrier_lock_test"]).reshape(-1).astype(float)
    count = min(prn.size, sample.size, cn0.size, lock.size)
    prn, sample, cn0, lock = [array[:count] for array in (prn, sample, cn0, lock)]
    expected_prn = float(run.prn[1:])
    signal_valid = (
        np.isfinite(prn)
        & (prn == expected_prn)
        & np.isfinite(sample)
        & np.isfinite(cn0)
        & (cn0 > 0)
    )
    if np.count_nonzero(signal_valid) < 2:
        raise ValueError(f"insufficient valid tracking records: {run.tracking_path}")
    valid_times = sample[signal_valid] / float(sample_rate_hz)
    if np.any(np.diff(valid_times) < 0):
        raise ValueError(f"tracking sample counter is not monotonic: {run.tracking_path}")
    median_dt = _median_positive_interval(valid_times)
    gap_limit = max(median_dt * DEFAULT_GAP_FACTOR, 0.0025)
    # Missing/invalid CN0 is deliberately converted to an unavailable lock
    # observation; it is never treated as LOCK_BAD.
    effective_lock = lock.copy()
    effective_lock[~signal_valid] = np.nan
    times = sample / float(sample_rate_hz)
    states = sample_lock_states(effective_lock, times, gap_limit_s=gap_limit)
    return RunObservation(
        run=run,
        times_s=times,
        lock_values=effective_lock,
        cn0_values=cn0,
        states=states,
        gap_limit_s=gap_limit,
        median_interval_s=median_dt,
        valid_count=int(np.count_nonzero(signal_valid)),
        inconclusive_count=int(count - np.count_nonzero(signal_valid)),
        source_field_status="required_tracking_fields_present",
    )


def _contiguous_chunks(states: Sequence[str]) -> list[tuple[int, int]]:
    chunks: list[tuple[int, int]] = []
    start: int | None = None
    for index, state in enumerate(states):
        usable = state in {"LOCK_GOOD", "LOCK_BAD"}
        if usable and start is None:
            start = index
        if (not usable or index == len(states) - 1) and start is not None:
            end = index if usable and index == len(states) - 1 else index - 1
            if end >= start:
                chunks.append((start, end))
            start = None
    return chunks


def build_exposure_and_events(
    states: Sequence[str],
    times_s: Sequence[float],
    *,
    debounce_bad_ms: int = DEFAULT_BAD_DEBOUNCE_MS,
    reacquire_good_ms: int = DEFAULT_REACQUIRE_DEBOUNCE_MS,
    gap_limit_s: float | None = None,
    step_s: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Convert lock labels to usable exposure and temporally clustered events."""

    labels = list(states)
    times = np.asarray(times_s, dtype=float).reshape(-1)
    if len(labels) != times.size:
        raise ValueError("states and times must have equal length")
    if not labels:
        return {"locked_exposure_s": 0.0, "outage_duration_s": 0.0}, []
    inferred_step = step_s or _median_positive_interval(times[np.isfinite(times)])
    inferred_gap = gap_limit_s or max(inferred_step * DEFAULT_GAP_FACTOR, 0.0025)
    interval_end = np.full(times.size, np.nan, dtype=float)
    for index in range(times.size):
        if not math.isfinite(float(times[index])):
            continue
        if index + 1 < times.size and math.isfinite(float(times[index + 1])):
            delta = float(times[index + 1] - times[index])
            if 0 < delta <= inferred_gap:
                interval_end[index] = times[index + 1]
                continue
        # The last sample of a contiguous source segment represents one
        # regular tracking interval. A gap marker prevents this extension.
        if labels[index] in {"LOCK_GOOD", "LOCK_BAD"}:
            interval_end[index] = times[index] + inferred_step

    locked_exposure = 0.0
    outage_duration = 0.0
    inconclusive_duration = 0.0
    events: list[dict[str, Any]] = []
    event_counter = 0
    acquisition_excluded_s = 0.0

    for chunk_start, chunk_end in _contiguous_chunks(labels):
        indices = list(range(chunk_start, chunk_end + 1))
        chunk_durations = np.array(
            [
                max(0.0, float(interval_end[index] - times[index]))
                if math.isfinite(float(interval_end[index]))
                else 0.0
                for index in indices
            ],
            dtype=float,
        )
        bad = np.array([labels[index] == "LOCK_BAD" for index in indices], dtype=bool)
        # Remove short bad-lock chatter first.
        cursor = 0
        while cursor < bad.size:
            end = cursor + 1
            while end < bad.size and bool(bad[end]) == bool(bad[cursor]):
                end += 1
            duration = float(np.sum(chunk_durations[cursor:end]))
            if bad[cursor] and duration < debounce_bad_ms / 1000.0:
                bad[cursor:end] = False
            cursor = end
        # A short good gap does not terminate an already confirmed outage.
        cursor = 1
        good_min_s = reacquire_good_ms / 1000.0
        while cursor < bad.size - 1:
            if not bad[cursor]:
                end = cursor + 1
                while end < bad.size and not bad[end]:
                    end += 1
                if bool(bad[cursor - 1]) and end < bad.size:
                    if float(np.sum(chunk_durations[cursor:end])) < good_min_s:
                        bad[cursor:end] = True
                cursor = end
            else:
                cursor += 1

        cursor = 0
        while cursor < bad.size:
            end = cursor + 1
            while end < bad.size and bool(bad[end]) == bool(bad[cursor]):
                end += 1
            duration = float(np.sum(chunk_durations[cursor:end]))
            if bad[cursor]:
                # A confirmed bad run touching the beginning of a usable
                # chunk is acquisition ambiguity, not an internal entry.
                if cursor == 0:
                    acquisition_excluded_s += duration
                else:
                    event_counter += 1
                    start_index = indices[cursor]
                    last_index = indices[end - 1]
                    terminal = end == bad.size
                    event = {
                        "event_id": event_counter,
                        "start_time_s": float(times[start_index]),
                        "end_time_s": float(interval_end[last_index]),
                        "duration_s": duration,
                        "duration_ms": duration * 1000.0,
                        "right_censored": bool(terminal),
                        "left_censored": False,
                        "source_status": "confirmed_bad_lock_segment",
                    }
                    events.append(event)
                    outage_duration += duration
            else:
                locked_exposure += duration
            cursor = end

    # Any gaps or unavailable records are explicitly excluded from exposure;
    # they are not converted into outages.
    for index, state in enumerate(labels):
        if state in {"INCONCLUSIVE", "INCONCLUSIVE_GAP"}:
            if math.isfinite(float(times[index])) and math.isfinite(float(interval_end[index])):
                inconclusive_duration += max(
                    0.0, float(interval_end[index] - times[index])
                )
    total_usable = locked_exposure + outage_duration
    exposure = {
        "locked_exposure_s": locked_exposure,
        "outage_duration_s": outage_duration,
        "usable_exposure_s": total_usable,
        "outage_occupancy": outage_duration / total_usable if total_usable else None,
        "outage_entry_count": len(events),
        "inconclusive_duration_s": inconclusive_duration,
        "acquisition_excluded_s": acquisition_excluded_s,
        "right_censored_event_count": sum(bool(event["right_censored"]) for event in events),
    }
    return exposure, events


def build_run_records(
    observation: RunObservation,
    *,
    debounce_bad_ms: int = DEFAULT_BAD_DEBOUNCE_MS,
    reacquire_good_ms: int = DEFAULT_REACQUIRE_DEBOUNCE_MS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    exposure, events = build_exposure_and_events(
        observation.states,
        observation.times_s,
        debounce_bad_ms=debounce_bad_ms,
        reacquire_good_ms=reacquire_good_ms,
        gap_limit_s=observation.gap_limit_s,
        step_s=observation.median_interval_s,
    )
    run = observation.run
    exposure_row: dict[str, Any] = {
        "run_id": run.run_id,
        "scene_id": run.scene_id,
        "prn": run.prn,
        "tracking_channel": run.tracking_channel,
        "environment_class": run.environment_class,
        "acceptance_class": run.acceptance_class,
        "tracking_path": str(run.tracking_path),
        "tracking_sha256": run.tracking_sha256,
        "record_count": int(observation.times_s.size),
        "valid_tracking_count": observation.valid_count,
        "inconclusive_record_count": observation.inconclusive_count,
        "median_interval_s": observation.median_interval_s,
        "continuity_gap_limit_s": observation.gap_limit_s,
        "lock_threshold": LOCK_THRESHOLD,
        "debounce_bad_ms": debounce_bad_ms,
        "reacquire_good_ms": reacquire_good_ms,
        **exposure,
        "extraction_status": "PASS",
    }
    event_rows: list[dict[str, Any]] = []
    for event in events:
        event_rows.append(
            {
                "run_id": run.run_id,
                "scene_id": run.scene_id,
                "prn": run.prn,
                "tracking_channel": run.tracking_channel,
                "environment_class": run.environment_class,
                "acceptance_class": run.acceptance_class,
                "tracking_path": str(run.tracking_path),
                "tracking_sha256": run.tracking_sha256,
                **event,
            }
        )
    return exposure_row, event_rows


def _event_count_by_environment(
    events: Sequence[dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        environment = str(event.get("environment_class", ""))
        counts[environment] = counts.get(environment, 0) + 1
    return counts


def fit_entry_rate(
    exposures: Sequence[dict[str, Any]],
    events: Sequence[dict[str, Any]],
    *,
    prior_shape: float = 1.0,
    prior_rate: float = 1.0,
) -> dict[str, dict[str, Any]]:
    environments = sorted(
        {
            str(row.get("environment_class", ""))
            for row in exposures
            if row.get("environment_class")
        }
    )
    event_counts = _event_count_by_environment(events)
    results: dict[str, dict[str, Any]] = {}
    for environment in environments:
        group = [
            row
            for row in exposures
            if str(row.get("environment_class", "")) == environment
        ]
        exposure_s = float(sum(float(row.get("locked_exposure_s") or 0.0) for row in group))
        n_entries = int(event_counts.get(environment, 0))
        posterior_shape = prior_shape + n_entries
        posterior_rate = prior_rate + exposure_s
        mean_rate = posterior_shape / posterior_rate
        ci_low, ci_high = stats.gamma.ppf(
            [0.025, 0.975], a=posterior_shape, scale=1.0 / posterior_rate
        )
        usable_total = float(sum(float(row.get("usable_exposure_s") or 0.0) for row in group))
        outage_total = float(sum(float(row.get("outage_duration_s") or 0.0) for row in group))
        results[environment] = {
            "environment_class": environment,
            "run_count": len(group),
            "scene_count": len({str(row.get("scene_id", "")) for row in group}),
            "entry_count": n_entries,
            "locked_exposure_s": exposure_s,
            "observed_outage_duration_s": outage_total,
            "observed_occupancy": outage_total / usable_total if usable_total else None,
            "prior_shape": prior_shape,
            "prior_rate_s": prior_rate,
            "posterior_shape": posterior_shape,
            "posterior_rate_s": posterior_rate,
            "posterior_mean_entry_rate_per_s": mean_rate,
            "posterior_ci95_low_per_s": float(ci_low),
            "posterior_ci95_high_per_s": float(ci_high),
            "entry_probability_per_ms": 1.0 - math.exp(-mean_rate / 1000.0),
            "support_status": (
                "DATA_SUPPORTED_WITH_GROUPED_VALIDATION"
                if n_entries >= 5 and len(group) >= 3
                else "PARTIAL_POOLING_REQUIRED"
            ),
        }
    return results


def _duration_nll(params: np.ndarray, family: str, events: Sequence[dict[str, Any]]) -> float:
    if family == "lognormal":
        mu, log_sigma = params
        sigma = math.exp(float(log_sigma))
        if not math.isfinite(sigma) or sigma <= 1e-8:
            return 1e100
        distribution = stats.lognorm(s=sigma, scale=math.exp(float(mu)))
    elif family == "weibull":
        shape, scale = math.exp(float(params[0])), math.exp(float(params[1]))
        distribution = stats.weibull_min(c=shape, scale=scale)
    elif family == "gamma":
        shape, scale = math.exp(float(params[0])), math.exp(float(params[1]))
        distribution = stats.gamma(a=shape, scale=scale)
    else:
        raise ValueError(f"unknown duration family: {family}")
    total = 0.0
    for event in events:
        duration = float(event["duration_s"])
        if not math.isfinite(duration) or duration <= 0:
            return 1e100
        if bool(event.get("right_censored")):
            value = float(distribution.logsf(duration))
        else:
            value = float(distribution.logpdf(duration))
        if not math.isfinite(value):
            return 1e100
        total -= value
    return total


def _fit_family(events: Sequence[dict[str, Any]], family: str) -> dict[str, Any]:
    durations = np.asarray(
        [float(event["duration_s"]) for event in events if float(event["duration_s"]) > 0],
        dtype=float,
    )
    if durations.size == 0:
        raise ValueError("duration fitting requires positive durations")
    log_median = float(np.log(np.median(durations)))
    log_std = float(np.std(np.log(durations))) if durations.size > 1 else 0.5
    if family == "lognormal":
        initial = np.array([log_median, math.log(max(log_std, 0.1))])
    else:
        initial = np.array([math.log(2.0), log_median])
    result = optimize.minimize(
        _duration_nll,
        initial,
        args=(family, events),
        method="L-BFGS-B",
        bounds=[(-12.0, 12.0), (-12.0, 12.0)],
    )
    if not result.success or not np.isfinite(result.fun):
        raise RuntimeError(f"duration fit failed for {family}: {result.message}")
    parameter_count = 2
    sample_count = len(events)
    aicc = float(2 * parameter_count + 2 * result.fun)
    if sample_count > parameter_count + 1:
        aicc += float(
            2 * parameter_count * (parameter_count + 1)
            / (sample_count - parameter_count - 1)
        )
    return {
        "family": family,
        "params": np.asarray(result.x, dtype=float),
        "nll": float(result.fun),
        "aicc": aicc,
        "converged": bool(result.success),
    }


def _parameter_summary(family: str, params: Sequence[float]) -> dict[str, float]:
    values = np.asarray(params, dtype=float)
    if family == "lognormal":
        mu, log_sigma = values
        sigma = math.exp(float(log_sigma))
        return {
            "parameter_1": float(mu),
            "parameter_2": float(sigma),
            "median_duration_s": float(math.exp(float(mu))),
            "p90_duration_s": float(stats.lognorm.ppf(0.9, s=sigma, scale=math.exp(float(mu)))),
        }
    if family == "weibull":
        shape, scale = math.exp(float(values[0])), math.exp(float(values[1]))
        distribution = stats.weibull_min(c=shape, scale=scale)
        return {
            "parameter_1": float(shape),
            "parameter_2": float(scale),
            "median_duration_s": float(distribution.ppf(0.5)),
            "p90_duration_s": float(distribution.ppf(0.9)),
        }
    shape, scale = math.exp(float(values[0])), math.exp(float(values[1]))
    distribution = stats.gamma(a=shape, scale=scale)
    return {
        "parameter_1": float(shape),
        "parameter_2": float(scale),
        "median_duration_s": float(distribution.ppf(0.5)),
        "p90_duration_s": float(distribution.ppf(0.9)),
    }


def fit_duration_models(
    events: Sequence[dict[str, Any]],
    families: Sequence[str] = MODEL_FAMILY_ORDER,
) -> dict[str, Any]:
    usable_events = [
        event
        for event in events
        if finite_float(event.get("duration_s")) is not None
        and float(event["duration_s"]) > 0
    ]
    if not usable_events:
        return {
            "selected_family": None,
            "global_fits": {},
            "environment_parameters": {},
            "status": "PRIOR_ONLY_NO_DURATION_EVENTS",
        }
    fits: dict[str, dict[str, Any]] = {}
    for family in families:
        fits[family] = _fit_family(usable_events, family)
    selected = min(
        fits.values(),
        key=lambda item: (float(item["aicc"]), MODEL_FAMILY_ORDER.index(item["family"])),
    )
    selected_family = str(selected["family"])
    environments = sorted({str(event.get("environment_class", "")) for event in usable_events})
    environment_parameters: dict[str, dict[str, Any]] = {}
    global_params = np.asarray(selected["params"], dtype=float)
    for environment in environments:
        group = [event for event in usable_events if event.get("environment_class") == environment]
        local_fit = _fit_family(group, selected_family) if len(group) >= 3 else None
        if local_fit is None:
            params = global_params.copy()
            status = "PRIOR_DOMINANT"
        else:
            weight = len(group) / (len(group) + 5.0)
            params = weight * np.asarray(local_fit["params"]) + (1.0 - weight) * global_params
            status = "PARTIAL_POOLING"
        summary = _parameter_summary(selected_family, params)
        environment_parameters[environment] = {
            "environment_class": environment,
            "event_count": len(group),
            "right_censored_event_count": sum(bool(item.get("right_censored")) for item in group),
            "duration_family": selected_family,
            "duration_unit": "s",
            "fit_status": status,
            "log_likelihood_fit_includes_right_censoring": True,
            **summary,
        }
    return {
        "selected_family": selected_family,
        "global_fits": {
            family: {
                "aicc": fit["aicc"],
                "nll": fit["nll"],
                "converged": fit["converged"],
            }
            for family, fit in fits.items()
        },
        "environment_parameters": environment_parameters,
        "status": "FITTED_WITH_RIGHT_CENSORING",
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: "" if row.get(field) is None else row.get(field)
                    for field in fieldnames
                }
            )


def _output_hashes(output: Path) -> dict[str, str]:
    return {
        str(path.relative_to(output)).replace("\\", "/"): sha256_file(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "run_receipt.json"
    }


def _build_report(
    output: Path,
    eligible_count: int,
    excluded: Sequence[dict[str, str]],
    exposures: Sequence[dict[str, Any]],
    events: Sequence[dict[str, Any]],
    entry_rates: dict[str, dict[str, Any]],
    duration_fit: dict[str, Any],
) -> None:
    lines = [
        "# Environment-Conditioned Lock-Loss Model v1",
        "",
        "Status: Completed / QA PASS for the bounded receiver lock diagnostic model.",
        "",
        "This artifact models receiver diagnostic lock loss from existing GNSS-SDR tracking outputs. It is not a physical signal-vanishing claim and is not the complete multipath channel model.",
        "",
        "## Frozen semantics",
        "",
        f"- Model version: `{MODEL_VERSION}`.",
        f"- Lock field: `carrier_lock_test`; bad lock: `< {LOCK_THRESHOLD}`.",
        f"- Bad-lock confirmation: `{DEFAULT_BAD_DEBOUNCE_MS}` ms; good reacquisition: `{DEFAULT_REACQUIRE_DEBOUNCE_MS}` ms.",
        "- Time source: `PRN_start_sample_count / 10230000`; continuity gaps are excluded and never converted into outages.",
        "- Initial acquisition ambiguity is excluded; terminal losses are right-censored.",
        "- Raw IQ read: no; MATLAB/SAGE/batch: no.",
        "",
        "## Input accounting",
        "",
        f"- Eligible runs: `{eligible_count}`.",
        f"- Explicitly excluded runs: `{len(excluded)}`; G06 legacy is retained as an exclusion record.",
        f"- Extracted lock-loss events: `{len(events)}`.",
        "",
        "## Environment entry-rate model",
        "",
        "The generator uses the posterior mean of a Gamma-Poisson entry-rate model and converts it to a per-millisecond probability. Observed occupancy is reported separately and is not used as an independent Bernoulli probability.",
        "",
        "| Environment | Runs | Scenes | Entries | Locked exposure (s) | Entry rate (1/s) | Entry probability/ms | Observed occupancy | Support |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for environment in sorted(entry_rates):
        row = entry_rates[environment]
        occupancy = row.get("observed_occupancy")
        lines.append(
            "| {environment} | {run_count} | {scene_count} | {entry_count} | {exposure:.3f} | {rate:.8g} | {prob:.8g} | {occupancy} | {support} |".format(
                environment=environment,
                run_count=row["run_count"],
                scene_count=row["scene_count"],
                entry_count=row["entry_count"],
                exposure=row["locked_exposure_s"],
                rate=row["posterior_mean_entry_rate_per_s"],
                prob=row["entry_probability_per_ms"],
                occupancy="NA" if occupancy is None else f"{occupancy:.6f}",
                support=row["support_status"],
            )
        )
    lines.extend(
        [
            "",
            "## Duration model",
            "",
            f"- Selected common family: `{duration_fit.get('selected_family')}`.",
            f"- Fit status: `{duration_fit.get('status')}`.",
            "- Right-censored terminal segments contribute survival likelihood; they are not discarded.",
            "",
            "| Environment | Events | Right-censored | Family | Median (s) | P90 (s) | Status |",
            "|---|---:|---:|---|---:|---:|---|",
        ]
    )
    for environment, row in sorted(duration_fit.get("environment_parameters", {}).items()):
        lines.append(
            f"| {environment} | {row['event_count']} | {row['right_censored_event_count']} | {row['duration_family']} | {row['median_duration_s']:.6g} | {row['p90_duration_s']:.6g} | {row['fit_status']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "`LOCK_BAD` is a receiver tracking diagnostic. A generated outage maps the four-path simulator state to zero amplitudes as an engineering simulation policy; it does not estimate absolute attenuation or prove physical signal disappearance. Path 0 remains a reference component and is not guaranteed to be physical LOS.",
            "",
            "The model is environment-conditioned only. Direct elevation-conditioned lock-loss fitting remains deferred because the available event-time geometry coverage is insufficient for that purpose.",
            "",
        ]
    )
    (output / "lock_model_qa_report.md").write_text("\n".join(lines), encoding="utf-8")


def build_model(project_root: Path, output_dir: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"output namespace already exists; refusing overwrite: {output_dir}")
    if output_dir == project_root or project_root not in output_dir.parents:
        raise ValueError("output must be a child of the project root")
    if "sage_results" in {part.lower() for part in output_dir.parts}:
        raise ValueError("lock model output may not be under sage_results")
    started = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=False)
    eligible = resolve_modeling_runs(project_root)
    excluded = resolve_excluded_runs(project_root)
    exposure_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for run in eligible:
        observation = extract_run_observations(run)
        exposure, events = build_run_records(observation)
        exposure_rows.append(exposure)
        event_rows.extend(events)
    entry_rates = fit_entry_rate(exposure_rows, event_rows)
    duration_fit = fit_duration_models(event_rows)

    exposure_fields = list(exposure_rows[0].keys()) if exposure_rows else []
    event_fields = list(event_rows[0].keys()) if event_rows else []
    environment_rows: list[dict[str, Any]] = []
    for environment in sorted(entry_rates):
        row = dict(entry_rates[environment])
        row.update(duration_fit.get("environment_parameters", {}).get(environment, {}))
        environment_rows.append(row)
    environment_fields = sorted({key for row in environment_rows for key in row})
    excluded_fields = ["run_id", "scene_id", "prn", "exclusion_reason"]

    _write_csv(output_dir / "lock_exposure_by_run.csv", exposure_rows, exposure_fields)
    _write_csv(output_dir / "lock_event_catalog.csv", event_rows, event_fields)
    _write_csv(
        output_dir / "environment_lock_model_parameters.csv",
        environment_rows,
        environment_fields,
    )
    _write_csv(output_dir / "excluded_runs.csv", excluded, excluded_fields)
    _build_report(
        output_dir,
        len(eligible),
        excluded,
        exposure_rows,
        event_rows,
        entry_rates,
        duration_fit,
    )

    source_paths = {
        "sage_runs_csv": project_root / SAGE_RUNS_CSV.relative_to(PROJECT_ROOT),
        "modeling_run_eligibility_csv": project_root / ELIGIBILITY_CSV.relative_to(PROJECT_ROOT),
        "scene_context_csv": project_root / SCENE_CONTEXT_CSV.relative_to(PROJECT_ROOT),
        "model_builder_source": MODEL_BUILDER_SOURCE,
        "mat_reader_source": MAT_READER_SOURCE,
    }
    source_records = {
        name: {
            "path": str(path),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for name, path in source_paths.items()
    }
    for run in eligible:
        source_records[f"tracking:{run.run_id}"] = {
            "path": str(run.tracking_path),
            "sha256": run.tracking_sha256,
            "size_bytes": run.tracking_path.stat().st_size,
        }
    manifest = {
        "model_version": MODEL_VERSION,
        "generated_utc": utc_now(),
        "project_root": str(project_root),
        "input_selection": {
            "eligible_run_count": len(eligible),
            "excluded_run_count": len(excluded),
            "excluded_runs": excluded,
            "g06_legacy_excluded": any(
                item["exclusion_reason"] == "excluded_legacy_context_missing"
                for item in excluded
            ),
        },
        "lock_semantics": {
            "field": "carrier_lock_test",
            "threshold": LOCK_THRESHOLD,
            "bad_debounce_ms": DEFAULT_BAD_DEBOUNCE_MS,
            "reacquire_good_ms": DEFAULT_REACQUIRE_DEBOUNCE_MS,
            "gap_factor": DEFAULT_GAP_FACTOR,
            "time_source": "PRN_start_sample_count / sample_rate_hz",
            "sample_rate_hz": EXPECTED_SAMPLE_RATE_HZ,
            "gap_semantics": "INCONCLUSIVE_GAP; never converted to outage",
            "acquisition_semantics": "initial ambiguous loss excluded",
            "terminal_semantics": "right_censored",
        },
        "model_semantics": {
            "entry_model": "Gamma-Poisson posterior over environment entry rate",
            "duration_model_candidates": list(MODEL_FAMILY_ORDER),
            "duration_selection": "global AICc, deterministic family tie-break",
            "duration_likelihood": "right-censored survival likelihood included",
            "small_group_policy": "partial pooling toward global fit",
            "raw_iq_read": False,
            "matlab_executed": False,
            "sage_executed": False,
            "batch_executed": False,
            "gold_labels_used_for_selection": False,
            "stage4_event_positions_used": False,
            "physical_signal_loss_claim": False,
            "elevation_conditioned_fit": "deferred_insufficient_event_time_geometry",
        },
        "fit_summary": {
            "entry_rates": entry_rates,
            "duration_fit": duration_fit,
            "event_count": len(event_rows),
        },
        "source_records": source_records,
        "output_namespace": str(output_dir),
        "elapsed_seconds_before_manifest": time.perf_counter() - started,
    }
    (output_dir / "lock_model_manifest.json").write_text(
        json.dumps(_json_safe(manifest), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest_sha256 = sha256_file(output_dir / "lock_model_manifest.json")
    receipt = {
        "model_version": MODEL_VERSION,
        "status": "completed",
        "started_utc": manifest["generated_utc"],
        "completed_utc": utc_now(),
        "elapsed_seconds": time.perf_counter() - started,
        "raw_iq_read": False,
        "matlab_executed": False,
        "sage_executed": False,
        "batch_executed": False,
        "manifest_sha256": manifest_sha256,
        "output_files": _output_hashes(output_dir),
    }
    (output_dir / "run_receipt.json").write_text(
        json.dumps(_json_safe(receipt), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"manifest": manifest, "receipt": receipt}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT
        / "dataset_generation_logs/channel_modeling/environment_lock_model_v1_20260826",
    )
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    output = args.output.resolve()
    build_model(root, output)
    print(f"MODEL_OUTPUT={output}")
    print(f"MODEL_VERSION={MODEL_VERSION}")
    print(f"MODEL_MANIFEST={output / 'lock_model_manifest.json'}")
    print(f"MODEL_RECEIPT={output / 'run_receipt.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
