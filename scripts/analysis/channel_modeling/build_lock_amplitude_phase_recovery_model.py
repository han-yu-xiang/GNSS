"""Build the receiver-lock amplitude/phase/recovery model from frozen artifacts.

The builder reads only versioned derived tracking/model CSV and JSON artifacts.
It never opens raw IQ, calls MATLAB/SAGE, or writes under ``scenes``.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.analysis.channel_modeling.lock_amplitude_phase_recovery_core import (
    ENVIRONMENTS,
    ELEVATION_BANDS,
    LockMappingMode,
    LockState,
    find_recovery_time,
    make_state_sequence,
    nearest_time_row,
    parse_bool,
    parse_optional_float,
    parse_required_float,
    raised_cosine_entry,
    raised_cosine_recovery,
    sha256_file,
    sha256_json,
    validate_floor,
)


OUTPUT_FILES: tuple[str, ...] = (
    "source_preflight.csv",
    "lock_gain_alignment_catalog.csv",
    "lock_event_envelope_features.csv",
    "recovery_trace_catalog.csv.gz",
    "recovery_family_selection.csv",
    "environment_recovery_parameters.csv",
    "lock_amplitude_mapping_contract.json",
    "phase_policy_contract.json",
    "composition_contract.json",
    "deterministic_scalar_draws.csv",
    "deterministic_state_sequence.csv.gz",
    "lock_amplitude_phase_recovery_model.json",
    "model_manifest.json",
    "build_receipt.json",
    "model_report.md",
)


def manifest_output_hashes(output_dir: Path) -> dict[str, str]:
    """Hash published artifacts without creating a self-referential manifest."""
    hashes: dict[str, str] = {}
    for name in OUTPUT_FILES:
        if name in {"model_manifest.json", "build_receipt.json"}:
            continue
        path = output_dir / name
        if path.is_file():
            hashes[name] = sha256_file(path)
    return hashes


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_csv_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})


def write_csv_gz(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return "1" if value else "0"
    return value


def resolve_source(project_root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError(f"source path must be project-relative: {relative_path}")
    resolved = (project_root / relative).resolve(strict=False)
    root = project_root.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"source escapes project root: {relative_path}") from exc
    return resolved


def require_new_only_namespace(output_dir: Path, project_root: Path) -> None:
    root = (project_root / "dataset_generation_logs" / "channel_modeling").resolve(strict=False)
    candidate = output_dir.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"output namespace must be under {root}: {output_dir}") from exc
    if candidate == root:
        raise ValueError("output namespace cannot be the channel_modeling root")
    if candidate.exists():
        raise FileExistsError(f"new-only output namespace already exists: {candidate}")


def verify_config(config: Mapping[str, Any], project_root: Path) -> dict[str, Path]:
    if config.get("model_id") != "lock-amplitude-phase-recovery-v1":
        raise ValueError("unexpected model id")
    if int(config.get("sample_rate_hz", 0)) != 10230000:
        raise ValueError("only 10.23 MHz is supported")
    if tuple(config.get("environments", ())) != ENVIRONMENTS:
        raise ValueError("environment contract changed")
    if tuple(config.get("elevation_bands", ())) != ELEVATION_BANDS:
        raise ValueError("elevation-band contract changed")
    if config.get("lock_timing_conditioning") != "environment_only":
        raise ValueError("lock timing must remain environment-conditioned only")
    policy = dict(config.get("execution_policy", {}))
    for field in ("raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz", "stage4_event_positions_used"):
        if policy.get(field) is not False:
            raise ValueError(f"execution policy is not offline for {field}")
    if policy.get("gold_labels_used_for_selection") is not False:
        raise ValueError("gold labels cannot be used for selection")
    if policy.get("new_only") is not True or policy.get("resume_allowed") is not False:
        raise ValueError("new-only/non-resumable policy changed")
    state = dict(config.get("state_machine", {}))
    if int(state.get("bad_duration_min_ms", 0)) != 20:
        raise ValueError("20 ms bad-duration minimum changed")
    if int(state.get("recovery_stable_ms", 0)) != 100:
        raise ValueError("100 ms recovery stability rule changed")
    amplitude = dict(config.get("amplitude_mapping", {}))
    if amplitude.get("default_mode") != LockMappingMode.EMPIRICAL_DIAGNOSTIC_PROXY.value:
        raise ValueError("unexpected default amplitude mapping mode")
    if amplitude.get("envelope_shape") != "raised_cosine":
        raise ValueError("unexpected amplitude envelope shape")
    if amplitude.get("stress_floor_required") is not True:
        raise ValueError("stress floor must remain explicit")
    phase = dict(config.get("phase_policy", {}))
    if phase.get("phase_is_data_fitted") is not False:
        raise ValueError("phase cannot be presented as fitted data")
    output_relative = str(config.get("output_namespace", ""))
    output_dir = resolve_source(project_root, output_relative)
    require_new_only_namespace(output_dir, project_root)
    source_values = dict(config.get("sources", {}))
    resolved: dict[str, Path] = {}
    for key, value in source_values.items():
        if key.endswith("_relative_path"):
            resolved[key] = resolve_source(project_root, str(value))
            if not resolved[key].is_file():
                raise FileNotFoundError(resolved[key])
            hash_key = key.removesuffix("_relative_path") + "_sha256"
            expected = str(source_values.get(hash_key, "")).lower()
            actual = sha256_file(resolved[key])
            if not expected or actual != expected:
                raise ValueError(f"source hash mismatch for {key}: {actual} != {expected}")
    protected = dict(config.get("protected_source", {}))
    protected_path = resolve_source(project_root, str(protected["pipeline_relative_path"]))
    if sha256_file(protected_path) != str(protected["pipeline_sha256"]).lower():
        raise ValueError("protected production pipeline hash mismatch")
    resolved["output_dir"] = output_dir
    resolved["project_root"] = project_root.resolve()
    return resolved


def source_preflight_rows(config: Mapping[str, Any], project_root: Path) -> list[dict[str, Any]]:
    sources = dict(config["sources"])
    rows: list[dict[str, Any]] = []
    for key, value in sorted(sources.items()):
        if not key.endswith("_relative_path"):
            continue
        path = resolve_source(project_root, str(value))
        expected = str(sources[key.removesuffix("_relative_path") + "_sha256"]).lower()
        actual = sha256_file(path) if path.is_file() else None
        rows.append(
            {
                "source_key": key,
                "relative_path": str(value),
                "absolute_path": str(path),
                "exists": path.is_file(),
                "expected_sha256": expected,
                "actual_sha256": actual,
                "status": "PASS" if actual == expected else "FAIL",
            }
        )
    return rows


def float_or_none(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def finite_median(values: Sequence[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return None
    return float(np.median(np.asarray(finite, dtype=float)))


def finite_min(values: Sequence[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return min(finite) if finite else None


def read_fade_depth_parameters(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    global_row: dict[str, Any] | None = None
    rows = read_csv(path)
    for row in rows:
        if row.get("parameter") != "fade_depth_db":
            continue
        try:
            params = json.loads(row.get("parameters", "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid fade parameter JSON: {row}") from exc
        item = {
            "family": row.get("family", "lognormal"),
            "parameters": params,
            "direct_count": int(row.get("direct_count", "0")),
            "parameter_source": row.get("parameter_source", ""),
        }
        if row.get("level") == "global":
            global_row = item
        elif row.get("level") == "environment" and row.get("environment"):
            result.setdefault(row["environment"], item)
    if global_row is None:
        raise ValueError("global fade depth parent is missing")
    for environment in ENVIRONMENTS:
        result.setdefault(environment, global_row)
    return result


def fit_recovery_parameters(durations_s: Sequence[float], scenes: Sequence[str]) -> dict[str, Any]:
    values = [float(value) for value in durations_s if math.isfinite(float(value)) and float(value) > 0.0]
    scene_set = {str(scene) for scene in scenes}
    if not values:
        return {
            "observed_count": 0,
            "scene_count": 0,
            "duration_family": "raised_cosine_with_fixed_duration",
            "duration_source": "fixed_100ms_fallback",
            "duration_ms": 100,
            "support_status": "ASSUMPTION_ONLY_REACQUISITION_DEBOUNCE_FALLBACK",
            "gold_labels_used_for_selection": False,
        }
    mean_s = float(np.mean(values))
    median_s = float(np.median(values))
    variance_s = float(np.var(values, ddof=1)) if len(values) > 1 else 0.0
    shape = (mean_s * mean_s / variance_s) if variance_s > 1e-15 else None
    scale = (variance_s / mean_s) if variance_s > 1e-15 else None
    if len(values) >= 10 and len(scene_set) >= 2:
        support = "DATA_SUPPORTED_WITH_GROUPED_VALIDATION"
    else:
        support = "SPARSE_PARTIAL_POOLING"
    return {
        "observed_count": len(values),
        "scene_count": len(scene_set),
        "duration_family": "gamma",
        "duration_source": "environment_observed_or_parent",
        "duration_ms": int(max(1, round(median_s * 1000.0))),
        "median_duration_s": median_s,
        "mean_duration_s": mean_s,
        "gamma_shape": shape,
        "gamma_scale_s": scale,
        "support_status": support,
        "gold_labels_used_for_selection": False,
    }


def _recovery_shape_rmse(trace: Sequence[tuple[float, float]], shape: str) -> float:
    errors: list[float] = []
    for progress, value in trace:
        if shape == "raised_cosine":
            expected = 0.5 * (1.0 - math.cos(math.pi * progress))
        elif shape == "exponential_linear_amplitude":
            expected = 1.0 - math.exp(-5.0 * progress)
        else:
            expected = progress
        errors.append((float(value) - expected) ** 2)
    return math.sqrt(float(np.mean(errors))) if errors else math.inf


def _normalize_recovery_trace(trace: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Normalize an observed recovery trace to [0, 1] without using gold labels.

    The source trace is a gain change in dB relative to the pre-entry baseline.
    Shape comparison is about temporal trajectory, not absolute gain origin or
    depth, so each trace is independently min/max normalized before comparison.
    """
    finite_trace = [
        (float(progress), float(value))
        for progress, value in trace
        if math.isfinite(float(progress)) and math.isfinite(float(value))
    ]
    if not finite_trace:
        return []
    values = [value for _, value in finite_trace]
    low = min(values)
    high = max(values)
    span = high - low
    if span <= 1e-12:
        return [(progress, 0.0) for progress, _ in finite_trace]
    return [(progress, (value - low) / span) for progress, value in finite_trace]


def select_recovery_shape(traces: Sequence[Sequence[tuple[float, float]]]) -> dict[str, Any]:
    candidates = ("raised_cosine", "exponential_linear_amplitude", "linear_db")
    normalized_traces = [_normalize_recovery_trace(trace) for trace in traces]
    normalized_traces = [trace for trace in normalized_traces if trace]
    if normalized_traces:
        scores: dict[str, float | None] = {
            candidate: float(np.mean([_recovery_shape_rmse(trace, candidate) for trace in normalized_traces]))
            for candidate in candidates
        }
        selected = min(candidates, key=lambda candidate: (float(scores[candidate]), candidate))
    else:
        scores = {candidate: None for candidate in candidates}
        selected = "raised_cosine"
    return {
        "selected_shape": selected,
        "candidate_rmse": scores,
        "selection": "minimum_grouped_per_trace_minmax_normalized_rmse_then_lexicographic_tie_break",
        "trace_normalization": "per_trace_minmax_to_unit_interval",
        "gold_labels_used_for_selection": False,
    }


def group_event_rows_by_run(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        run_id = str(row.get("run_id", ""))
        grouped.setdefault(run_id, []).append(dict(row))
    for run_rows in grouped.values():
        run_rows.sort(key=lambda row: float(row.get("time_s", "nan")))
    return grouped


def _valid_continuity(row: Mapping[str, Any]) -> bool:
    try:
        return parse_bool(row.get("continuity_valid", "1"), "continuity_valid")
    except ValueError:
        return False


def build_event_features(
    event: Mapping[str, Any],
    run_rows: Sequence[Mapping[str, Any]],
    next_event_start_s: float | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    run_id = str(event["run_id"])
    event_id = str(event["event_id"])
    start = parse_required_float(event["start_time_s"], "start_time_s")
    end = parse_required_float(event["end_time_s"], "end_time_s")
    post_end = end + 2.0
    if next_event_start_s is not None:
        post_end = min(post_end, next_event_start_s)
    pre_rows = [
        row for row in run_rows
        if start - 1.0 <= float(row["time_s"]) <= start - 0.1
        and str(row.get("lock_state", "")).upper() == "LOCK_GOOD"
        and _valid_continuity(row)
    ]
    entry_rows = [row for row in run_rows if start - 0.1 <= float(row["time_s"]) < start]
    lock_rows = [row for row in run_rows if start <= float(row["time_s"]) <= end]
    post_rows = [row for row in run_rows if end < float(row["time_s"]) <= post_end]
    baseline = finite_median([float_or_none(row.get("common_gain_db")) for row in pre_rows if float_or_none(row.get("common_gain_db")) is not None])
    lock_gain_values = [float_or_none(row.get("common_gain_db")) for row in lock_rows]
    lock_gain_values = [value for value in lock_gain_values if value is not None]
    observed_min = finite_min(lock_gain_values)
    depth_lower_bound = max(0.0, baseline - observed_min) if baseline is not None and observed_min is not None else None
    recovery = find_recovery_time(post_rows, baseline, end) if baseline is not None else None
    if recovery is None:
        recovery_status = "RECOVERY_NO_VALID_BASELINE"
        recovery_duration_s = None
        recovery_reason = "missing_pre_entry_baseline"
    else:
        recovery_status = recovery.status
        recovery_duration_s = recovery.duration_s
        recovery_reason = recovery.reason
    if baseline is None:
        depth_status = "DEPTH_RIGHT_CENSORED"
    else:
        depth_status = "DEPTH_RIGHT_CENSORED" if depth_lower_bound is not None else "DEPTH_RIGHT_CENSORED"
    feature = {
        "run_id": run_id,
        "event_id": event_id,
        "scene_id": event.get("scene_id"),
        "environment": event.get("environment") or event.get("environment_class"),
        "prn": event.get("prn"),
        "tracking_channel": event.get("tracking_channel"),
        "event_start_s": start,
        "event_end_s": end,
        "lock_duration_s": end - start,
        "pre_row_count": len(pre_rows),
        "entry_row_count": len(entry_rows),
        "lock_row_count": len(lock_rows),
        "post_row_count": len(post_rows),
        "pre_entry_gain_db_median": baseline,
        "entry_gain_db_min": finite_min([float_or_none(row.get("common_gain_db")) for row in entry_rows if float_or_none(row.get("common_gain_db")) is not None]),
        "lock_gain_db_min_observed": observed_min,
        "observed_depth_lower_bound_db": depth_lower_bound,
        "depth_status": depth_status,
        "recovery_status": recovery_status,
        "recovery_duration_s": recovery_duration_s,
        "recovery_reason": recovery_reason,
        "continuity_gap_in_post": any(not _valid_continuity(row) for row in post_rows),
        "gold_labels_used_for_selection": False,
        "physical_lock_depth_identified": False,
    }
    segment_rows: list[dict[str, Any]] = []
    for segment_name, rows in (("pre_entry", pre_rows), ("entry", entry_rows), ("lock", lock_rows), ("recovery", post_rows)):
        times = [float(row["time_s"]) for row in rows]
        segment_rows.append(
            {
                "run_id": run_id,
                "event_id": event_id,
                "segment": segment_name,
                "row_count": len(rows),
                "first_time_s": min(times) if times else None,
                "last_time_s": max(times) if times else None,
                "min_common_gain_db": finite_min([float_or_none(row.get("common_gain_db")) for row in rows if float_or_none(row.get("common_gain_db")) is not None]),
                "max_common_gain_db": max([value for value in (float_or_none(row.get("common_gain_db")) for row in rows) if value is not None], default=None),
                "continuity_valid_rows": sum(1 for row in rows if _valid_continuity(row)),
            }
        )
    trace_rows: list[dict[str, Any]] = []
    for row in post_rows:
        gain = float_or_none(row.get("common_gain_db"))
        trace_rows.append(
            {
                "run_id": run_id,
                "event_id": event_id,
                "scene_id": event.get("scene_id"),
                "environment": event.get("environment"),
                "time_s": float(row["time_s"]),
                "relative_time_s": float(row["time_s"]) - end,
                "common_gain_db": gain,
                "normalized_gain_db": gain - baseline if gain is not None and baseline is not None else None,
                "within_1db": abs(gain - baseline) <= 1.0 if gain is not None and baseline is not None else None,
                "continuity_valid": _valid_continuity(row),
            }
        )
    return feature, segment_rows, trace_rows


def simulate_lock_sequence(
    rng: np.random.Generator,
    entry_probability_per_ms: float,
    duration_shape: float,
    duration_scale_s: float,
    recovery_ms: int,
    total_ms: int = 60000,
) -> list[tuple[int, int, str]]:
    if not 0.0 <= entry_probability_per_ms <= 1.0:
        raise ValueError("entry probability must be in [0,1]")
    states: list[str] = []
    index = 0
    while index < total_ms:
        if rng.random() >= entry_probability_per_ms:
            states.append(LockState.TRACKED.value)
            index += 1
            continue
        lock_ms = max(20, int(math.ceil(float(rng.gamma(duration_shape, duration_scale_s) * 1000.0))))
        entry_ms = min(20, lock_ms)
        state_seq = make_state_sequence(lock_ms, entry_ms, max(1, int(recovery_ms)))
        remaining = total_ms - index
        states.extend(state.value for state in state_seq[:remaining])
        index += min(len(state_seq), remaining)
    segments: list[tuple[int, int, str]] = []
    if not states:
        return segments
    segment_start = 1
    current = states[0]
    for position, state in enumerate(states[1:], start=2):
        if state != current:
            segments.append((segment_start, position - 1, current))
            segment_start = position
            current = state
    segments.append((segment_start, len(states), current))
    return segments


def sample_empirical_depth(rng: np.random.Generator, parameter: Mapping[str, Any]) -> float:
    params = dict(parameter.get("parameters", {}))
    shape = float(params.get("shape", 0.5))
    scale = float(params.get("scale", 1.0))
    if not math.isfinite(shape) or shape <= 0.0 or not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("invalid lognormal fade-depth parent")
    return max(0.0, float(rng.lognormal(math.log(scale), shape)))


def sample_recovery_duration_ms(rng: np.random.Generator, parameters: Mapping[str, Any]) -> int:
    if parameters.get("duration_source") == "fixed_100ms_fallback":
        return 100
    shape = parameters.get("gamma_shape")
    scale = parameters.get("gamma_scale_s")
    if shape is None or scale is None or float(shape) <= 0.0 or float(scale) <= 0.0:
        return max(1, int(parameters.get("duration_ms", 100)))
    return max(1, int(math.ceil(float(rng.gamma(float(shape), float(scale)) * 1000.0))))


def _parameter_for_environment(fade_params: Mapping[str, Mapping[str, Any]], environment: str) -> Mapping[str, Any]:
    return fade_params.get(environment) or fade_params["Urban"]


def build_model(project_root: Path, config_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    config = read_json(config_path)
    resolved = verify_config(config, project_root)
    output_dir = resolved["output_dir"]
    source_rows = source_preflight_rows(config, project_root)
    source_map = dict(config["sources"])
    lock_events = read_csv(resolved["lock_event_catalog_relative_path"])
    lock_params = read_csv(resolved["lock_parameters_relative_path"])
    grid = read_csv_gz(resolved["gain_grid_relative_path"])
    fade_params = read_fade_depth_parameters(resolved["fade_parameters_relative_path"])
    if len(lock_events) != 48:
        raise ValueError(f"expected 48 lock events, got {len(lock_events)}")
    grid_by_run = group_event_rows_by_run(grid)
    events_by_run = group_event_rows_by_run(lock_events)
    feature_rows: list[dict[str, Any]] = []
    segment_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    for run_id, events in sorted(events_by_run.items()):
        run_grid = grid_by_run.get(run_id, [])
        for index, event in enumerate(sorted(events, key=lambda row: float(row["start_time_s"]))):
            next_start = None
            if index + 1 < len(events):
                next_start = float(sorted(events, key=lambda row: float(row["start_time_s"]))[index + 1]["start_time_s"])
            feature, segments, traces = build_event_features(event, run_grid, next_start)
            feature_rows.append(feature)
            segment_rows.extend(segments)
            trace_rows.extend(traces)
    if len(feature_rows) != 48:
        raise ValueError(f"feature/event accounting mismatch: {len(feature_rows)}")
    observed_by_env: dict[str, list[float]] = {environment: [] for environment in ENVIRONMENTS}
    scenes_by_env: dict[str, list[str]] = {environment: [] for environment in ENVIRONMENTS}
    traces_by_env: dict[str, list[list[tuple[float, float]]]] = {environment: [] for environment in ENVIRONMENTS}
    for feature in feature_rows:
        environment = str(feature.get("environment"))
        if environment not in observed_by_env:
            continue
        if feature.get("recovery_status") == "RECOVERY_OBSERVED" and feature.get("recovery_duration_s") is not None:
            observed_by_env[environment].append(float(feature["recovery_duration_s"]))
            scenes_by_env[environment].append(str(feature.get("scene_id")))
        trace = [
            (float(row["relative_time_s"]) / max(float(feature["recovery_duration_s"] or 1.0), 1e-9), float(row["normalized_gain_db"] or 0.0))
            for row in trace_rows
            if row["event_id"] == feature["event_id"] and row["normalized_gain_db"] is not None
        ]
        if trace:
            traces_by_env[environment].append(trace)
    all_durations = [value for values in observed_by_env.values() for value in values]
    all_scenes = [scene for values in scenes_by_env.values() for scene in values]
    global_recovery = fit_recovery_parameters(all_durations, all_scenes)
    environment_recovery: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        direct = fit_recovery_parameters(observed_by_env[environment], scenes_by_env[environment])
        if direct["observed_count"] >= 10 and direct["scene_count"] >= 2:
            parameters = direct
            parameters["environment"] = environment
            parameters["parameter_source"] = "environment_direct"
        elif global_recovery["observed_count"] > 0:
            parameters = dict(global_recovery)
            parameters["environment"] = environment
            parameters["parameter_source"] = "global_parent"
            parameters["support_status"] = "PARTIAL_POOLING"
        else:
            parameters = dict(direct)
            parameters["environment"] = environment
            parameters["parameter_source"] = "fixed_fallback"
        environment_recovery.append(parameters)
    shape_selection = select_recovery_shape([trace for values in traces_by_env.values() for trace in values])
    output_dir.mkdir(parents=True, exist_ok=False)
    config_sha = sha256_file(config_path)
    core_path = Path(__file__).resolve().with_name("lock_amplitude_phase_recovery_core.py")
    builder_path = Path(__file__).resolve()
    write_csv(
        output_dir / "source_preflight.csv",
        source_rows,
        ("source_key", "relative_path", "absolute_path", "exists", "expected_sha256", "actual_sha256", "status"),
    )
    write_csv(
        output_dir / "lock_gain_alignment_catalog.csv",
        segment_rows,
        ("run_id", "event_id", "segment", "row_count", "first_time_s", "last_time_s", "min_common_gain_db", "max_common_gain_db", "continuity_valid_rows"),
    )
    write_csv(
        output_dir / "lock_event_envelope_features.csv",
        feature_rows,
        tuple(feature_rows[0].keys()),
    )
    write_csv_gz(
        output_dir / "recovery_trace_catalog.csv.gz",
        trace_rows,
        tuple(trace_rows[0].keys()) if trace_rows else ("run_id", "event_id", "scene_id", "environment", "time_s", "relative_time_s", "common_gain_db", "normalized_gain_db", "within_1db", "continuity_valid"),
    )
    family_rows = [
        {"scope": "global", "family": family, "selected": family == "gamma", "selection_basis": "right_censored_lock_model_parent_for_timing"}
        for family in ("lognormal", "gamma", "weibull")
    ]
    family_rows.extend(
        {"scope": "recovery_shape", "family": family, "selected": family == shape_selection["selected_shape"], "selection_basis": "normalized_trace_rmse"}
        for family in ("raised_cosine", "exponential_linear_amplitude", "linear_db")
    )
    write_csv(output_dir / "recovery_family_selection.csv", family_rows, ("scope", "family", "selected", "selection_basis"))
    write_csv(output_dir / "environment_recovery_parameters.csv", environment_recovery, tuple(environment_recovery[0].keys()))
    mapping_contract = {
        "contract_id": "lock-amplitude-mapping-v1",
        "default_mode": LockMappingMode.EMPIRICAL_DIAGNOSTIC_PROXY.value,
        "allowed_modes": [mode.value for mode in LockMappingMode],
        "formula": "A_i[m] = G_background[m] * G_lock[m] * Z_i * A_rel_i",
        "path_zero_formula": "A_0[m] = G_background[m] * G_lock[m]",
        "envelope_shape": "raised_cosine",
        "empirical_depth_source": "observable_fade_depth_parent",
        "physical_lock_depth_identified": False,
        "hardware_lock_loss_calibrated": False,
        "exact_zero_default": False,
        "numerical_positive_floor_linear": config["amplitude_mapping"]["numerical_positive_floor_linear"],
        "ordinary_fade_conflict_policy": config["amplitude_mapping"]["ordinary_fade_conflict_policy"],
        "gold_labels_used_for_selection": False,
    }
    phase_contract = {
        "contract_id": "phase-policy-v1",
        "initial_distribution": "Uniform(-pi,pi)",
        "recurrence": "phi_next=wrap_to_pi(phi+2*pi*relative_doppler_hz*0.001)",
        "wrap_interval": "[-pi,pi)",
        "lock_bad_resets_phase": False,
        "recovery_resets_phase": False,
        "receiver_reacquisition_phase_reset_modeled": False,
        "phase_is_data_fitted": False,
        "gold_labels_used_for_selection": False,
    }
    composition_contract = {
        "contract_id": "channel-composition-v1",
        "sample_rate_hz": 10230000,
        "path_zero_is_physical_los": False,
        "relative_delay_unit": "ns",
        "relative_doppler_unit": "Hz",
        "relative_amplitude_unit": "linear_amplitude_ratio",
        "relative_phase_unit": "rad",
        "nlos_slot_count": 3,
        "block_policy": "base_delay_doppler_amplitude_fixed_per_block; phase_and_envelope_evolve_per_ms",
        "inactive_semantics": {"amplitude": 0.0, "delay": None, "doppler": None, "phase": None},
        "gold_labels_used_for_selection": False,
    }
    write_json(output_dir / "lock_amplitude_mapping_contract.json", mapping_contract)
    write_json(output_dir / "phase_policy_contract.json", phase_contract)
    write_json(output_dir / "composition_contract.json", composition_contract)
    lock_param_by_env = {str(row["environment_class"]): row for row in lock_params}
    recovery_by_env = {str(row["environment"]): row for row in environment_recovery}
    scalar_rows: list[dict[str, Any]] = []
    scalar_seed = 20260826
    for environment_index, environment in enumerate(ENVIRONMENTS):
        rng = np.random.default_rng(scalar_seed + environment_index)
        lock_param = lock_param_by_env[environment]
        recovery_param = recovery_by_env[environment]
        fade_parent = _parameter_for_environment(fade_params, environment)
        for draw_index in range(4096):
            p = float(lock_param["entry_probability_per_ms"])
            interarrival = int(rng.geometric(p)) if p > 0.0 else None
            duration_ms = max(20, int(math.ceil(float(rng.gamma(float(lock_param["parameter_1"]), float(lock_param["parameter_2"])) * 1000.0))))
            scalar_rows.append(
                {
                    "environment": environment,
                    "draw_index": draw_index,
                    "seed": scalar_seed + environment_index,
                    "entry_probability_per_ms": p,
                    "interarrival_ms": interarrival,
                    "lock_duration_ms": duration_ms,
                    "recovery_duration_ms": sample_recovery_duration_ms(rng, recovery_param),
                    "empirical_depth_proxy_db": sample_empirical_depth(rng, fade_parent),
                    "mapping_mode": LockMappingMode.EMPIRICAL_DIAGNOSTIC_PROXY.value,
                    "gold_labels_used_for_selection": False,
                }
            )
    write_csv(output_dir / "deterministic_scalar_draws.csv", scalar_rows, tuple(scalar_rows[0].keys()))
    state_rows: list[dict[str, Any]] = []
    state_seed = 20260840
    for environment_index, environment in enumerate(ENVIRONMENTS):
        lock_param = lock_param_by_env[environment]
        recovery_param = recovery_by_env[environment]
        for sequence_id in range(64):
            rng = np.random.default_rng(state_seed + environment_index * 1000 + sequence_id)
            segments = simulate_lock_sequence(
                rng,
                float(lock_param["entry_probability_per_ms"]),
                float(lock_param["parameter_1"]),
                float(lock_param["parameter_2"]),
                sample_recovery_duration_ms(rng, recovery_param),
            )
            for segment_index, (start_ms, end_ms, state) in enumerate(segments):
                state_rows.append(
                    {
                        "environment": environment,
                        "sequence_id": sequence_id,
                        "seed": state_seed + environment_index * 1000 + sequence_id,
                        "segment_index": segment_index,
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "state": state,
                    }
                )
    write_csv_gz(output_dir / "deterministic_state_sequence.csv.gz", state_rows, tuple(state_rows[0].keys()))
    model = {
        "model_id": config["model_id"],
        "model_version": config["model_version"],
        "generated_utc": utc_now(),
        "sample_rate_hz": 10230000,
        "counts": {
            "lock_event_count": len(lock_events),
            "common_gain_grid_rows": len(grid),
            "recovery_trace_rows": len(trace_rows),
            "deterministic_scalar_draws": len(scalar_rows),
            "deterministic_state_sequences": 64 * len(ENVIRONMENTS),
        },
        "lock_semantics": {
            "field": "carrier_lock_test",
            "bad_threshold": -0.5,
            "bad_debounce_ms": 20,
            "reacquire_good_ms": 100,
            "time_source": "PRN_start_sample_count / sample_rate_hz",
            "gap_semantics": "INCONCLUSIVE_GAP; never converted to outage",
            "timing_conditioning": "environment_only",
        },
        "recovery": {
            "shape_selection": shape_selection,
            "environment_parameters": environment_recovery,
            "recovery_observation_definition": "within_1db_for_100ms_after_event_end",
            "right_censoring_preserved": True,
        },
        "amplitude_mapping": mapping_contract,
        "phase_policy": phase_contract,
        "composition_contract": composition_contract,
        "execution_policy": config["execution_policy"],
        "scientific_limitations": {
            "physical_lock_depth_identified": False,
            "hardware_lock_loss_calibrated": False,
            "absolute_rf_power_calibrated": False,
            "zero_confirmed_is_not_los": True,
        },
        "source_contract": {
            "config_sha256": config_sha,
            "parent_source_hashes": {key: value for key, value in source_map.items() if key.endswith("_sha256")},
            "protected_pipeline_sha256": config["protected_source"]["pipeline_sha256"],
        },
        "code_hashes": {
            "core": sha256_file(core_path),
            "builder": sha256_file(builder_path),
            "config": config_sha,
        },
    }
    write_json(output_dir / "lock_amplitude_phase_recovery_model.json", model)
    report = f"# Lock-State Amplitude, Phase, and Recovery Model v1\n\n"
    report += f"Status: `IMPLEMENTED_PENDING_INDEPENDENT_QA`\n\n"
    report += "This namespace is an offline composition model. It does not calibrate absolute RF power or guarantee physical receiver lock loss. `LOCK_BAD` remains a receiver diagnostic.\n\n"
    report += f"Lock events aligned: {len(feature_rows)}. Common-gain rows read: {len(grid)}. Recovery traces: {len(trace_rows)}.\n\n"
    report += "The default mode is `EMPIRICAL_DIAGNOSTIC_PROXY`; forced stress mode requires an explicit positive user floor and is not a fitted physical attenuation. Phase is an external uniform-initial plus Doppler-continuous assumption.\n"
    (output_dir / "model_report.md").write_text(report, encoding="utf-8")
    output_hashes = manifest_output_hashes(output_dir)
    manifest = {
        "manifest_version": "raw-lock-amplitude-phase-recovery-manifest-v1",
        "model_id": config["model_id"],
        "config_sha256": config_sha,
        "code_hashes": model["code_hashes"],
        "source_hashes": model["source_contract"]["parent_source_hashes"],
        "output_namespace": str(output_dir),
        "output_hashes": output_hashes,
        "execution_policy": config["execution_policy"],
        "gold_labels_used_for_selection": False,
        "raw_iq_read": False,
        "matlab_executed": False,
        "sage_executed": False,
        "batch_executed": False,
        "status": "IMPLEMENTED_PENDING_INDEPENDENT_QA",
    }
    write_json(output_dir / "model_manifest.json", manifest)
    model_manifest_sha = sha256_file(output_dir / "model_manifest.json")
    receipt_output_hashes = dict(output_hashes)
    receipt_output_hashes["model_manifest.json"] = model_manifest_sha
    receipt = {
        "status": "BUILD_COMPLETED_PENDING_INDEPENDENT_QA",
        "generated_utc": utc_now(),
        "output_namespace": str(output_dir),
        "config_sha256": config_sha,
        "model_manifest_sha256": model_manifest_sha,
        "source_hashes": model["source_contract"]["parent_source_hashes"],
        "code_hashes": model["code_hashes"],
        "source_counts": model["counts"],
        "output_hashes": receipt_output_hashes,
        "elapsed_seconds": time.perf_counter() - started,
        "execution_policy": config["execution_policy"],
    }
    write_json(output_dir / "build_receipt.json", receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        receipt = build_model(args.project_root.resolve(), args.config.resolve())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"BUILD_FAILED={exc}", file=sys.stderr)
        return 1
    print(f"BUILD_RECEIPT={receipt['output_namespace']}\\build_receipt.json")
    print(f"MODEL_MANIFEST_SHA256={receipt['model_manifest_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
