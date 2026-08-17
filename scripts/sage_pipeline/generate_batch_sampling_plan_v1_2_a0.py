#!/usr/bin/env python3
"""Generate and replay the oracle-free batch-sampled-v1.2 A0 plan.

This module is deliberately independent from the v1 and v1.1 planners.  A0
reads the complete Stage0 40-ms catalog and the already verified, TOW-aligned
geometry diagnostic produced by the v1.1 offline work.  It does not open raw
IQ, tracking MAT files, Stage1, Stage2, Stage3, or Stage4 while producing a
score or promotion component.  Existing Stage3/Stage4 CSVs are read only
after the selection manifests have been frozen, and are used only for
posterior coverage replay.

The script is an offline validation tool.  It does not create a SAGE
execution request and it never writes below a ``sage_results`` directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PLANNER_VERSION = "batch-sampled-v1.2-a0"
SCHEMA_VERSION = "batch-sampled-v1.2-a0-schema-1"
OUTPUT_NAMESPACE = "dataset_generation_logs/sampling_validation/batch_sampled_v1_2_a0_offline"
SAMPLE_RATE_HZ = 10_230_000
WINDOW_STEP_SECONDS = 0.020
SAMPLE_STEP_TOLERANCE = 2
TOW_STEP_TOLERANCE_SECONDS = 0.001
ROLLING_RADIUS = 5
BRIDGE_GAP_WINDOWS = 2
BOUNDARY_EXPANSION_WINDOWS = 1
FINE_CLOSURE_RADIUS = 2
PROFILES = (1200, 2400, 4800)
GEOMETRY_DIAGNOSTIC_ROOT = (
    "dataset_generation_logs/sampling_validation/"
    "batch_sampled_v1_1_offline_coverage/tow_aligned"
)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    group: str
    scene_id: str
    prn: str
    tracking_channel: int
    sample_rate_hz: int = SAMPLE_RATE_HZ

    @property
    def result_dir(self) -> str:
        if self.task_id.endswith("_G06_ch4"):
            return "G06_nav_sage_v1"
        return f"nav_sage_v2/{self.prn}"


@dataclass(frozen=True)
class Component:
    component_id: str
    segment_id: int
    core_windows: tuple[int, ...]
    component_windows: tuple[int, ...]
    promoted_windows: tuple[int, ...]
    fine_candidate_windows: tuple[int, ...]
    max_score: float
    first_window: int
    last_window: int
    continuity_missing: bool = False


@dataclass
class TaskData:
    task: TaskSpec
    stage0_path: Path
    stage0_hash: str
    rows: list[dict[str, Any]]
    geometry_path: Path | None
    geometry_hash: str | None
    geometry_rows: dict[int, dict[str, Any]]
    geometry_status: str
    geometry_warning: str


@dataclass
class ProfileResult:
    task: TaskSpec
    budget: int
    feature_rows: list[dict[str, Any]]
    promotion_rows: list[dict[str, Any]]
    components: list[Component]
    promoted_windows: set[int]
    fine_windows: set[int]
    budget_exhausted: bool
    inconclusive_components: int
    selection_hash: str
    summary: dict[str, Any]


GOLD_TASKS: tuple[TaskSpec, ...] = (
    TaskSpec("reference_F1023_V70_D0117_P2_G06_ch4", "reference", "F1023_V70_D0117_P2", "G06", 4),
    TaskSpec("reference_F1023_V70_D0117_P2_G11_ch5", "reference", "F1023_V70_D0117_P2", "G11", 5),
    TaskSpec("reference_F1023_V70_D0117_P2_G12_ch6", "reference", "F1023_V70_D0117_P2", "G12", 6),
    TaskSpec("reference_F1023_V70_D0117_P2_G25_ch0", "reference", "F1023_V70_D0117_P2", "G25", 0),
    TaskSpec("reference_F1023_V70_D0117_P2_G28_ch1", "reference", "F1023_V70_D0117_P2", "G28", 1),
    TaskSpec("reference_F1023_V70_D0117_P2_G29_ch7", "reference", "F1023_V70_D0117_P2", "G29", 7),
    TaskSpec("reference_F1023_V70_D0117_P2_G32_ch11", "reference", "F1023_V70_D0117_P2", "G32", 11),
    TaskSpec("waveA_F1023_V70_D0120_P7_G16_ch1", "waveA", "F1023_V70_D0120_P7", "G16", 1),
    TaskSpec("waveA_F1023_v50_D0127_P1_G25_ch0", "waveA", "F1023_v50_D0127_P1", "G25", 0),
    TaskSpec("waveA_F1023_V70_D0122_P1_G12_ch6", "waveA", "F1023_V70_D0122_P1", "G12", 6),
    TaskSpec("wave2A_F1023_V120_D0121_P2_G11_ch0", "wave2A", "F1023_V120_D0121_P2", "G11", 0),
)


# This object is the selection contract.  It is hashed and written before
# any gold Stage3/Stage4 file is opened.  Do not tune it from a coverage run.
A0_SELECTION_SPEC: dict[str, Any] = {
    "planner_version": PLANNER_VERSION,
    "schema_version": SCHEMA_VERSION,
    "feature_list": [
        "cn0_db_hz_absolute",
        "cn0_delta_prev_db",
        "cn0_rolling_mad_db",
        "tracking_doppler_hz",
        "tracking_doppler_delta_hz",
        "tracking_doppler_second_delta_hz",
        "code_frequency_hz",
        "code_frequency_delta_hz",
        "vehicle_speed_kmh",
        "vehicle_speed_delta_kmh",
        "relative_doppler_bound_hz",
        "relative_doppler_bound_delta_hz",
        "sample_tow_continuity",
        "carrier_lock_test_if_present",
        "verified_elevation_deg_if_available",
        "verified_azimuth_deg_if_available",
        "verified_snr_db_hz_if_available",
    ],
    "feature_sources": ["stage0_valid_40ms_windows.csv", "v1.1_tow_aligned_geometry_diagnostic_only"],
    "forbidden_selection_sources": ["raw_iq", "tracking_mat", "stage1", "stage2", "stage3", "stage4", "gold_event_location"],
    "normalization": {
        "method": "per-task median and MAD with fixed 1.4826 multiplier",
        "scale_floor": 1.0,
        "z_cap": 6.0,
        "missing_values": "excluded from term and recorded in feature_missing",
    },
    "score_terms": [
        {"name": "cn0_drop", "weight": 1.50, "direction": "negative_prev_delta"},
        {"name": "cn0_rolling_mad", "weight": 1.00, "direction": "absolute"},
        {"name": "cn0_low_level", "weight": 0.50, "direction": "below_task_median"},
        {"name": "doppler_first_difference", "weight": 1.00, "direction": "absolute"},
        {"name": "doppler_second_difference", "weight": 1.00, "direction": "absolute"},
        {"name": "code_frequency_difference", "weight": 0.75, "direction": "absolute"},
        {"name": "speed_difference", "weight": 0.25, "direction": "absolute"},
        {"name": "relative_doppler_bound_difference", "weight": 0.25, "direction": "absolute"},
        {"name": "geometry_elevation_difference", "weight": 0.50, "direction": "absolute"},
        {"name": "geometry_azimuth_difference", "weight": 0.50, "direction": "absolute_circular"},
        {"name": "geometry_snr_difference", "weight": 0.50, "direction": "absolute"},
    ],
    "score_formula": "weighted_mean(capped_robust_z_terms); no learned parameters; no gold fitting",
    "hysteresis": {"high_threshold": 2.50, "low_threshold": 1.50},
    "component_rule": {
        "high_seed": "score >= high_threshold",
        "low_support": "score >= low_threshold",
        "bridge_gap_windows": BRIDGE_GAP_WINDOWS,
        "boundary_expansion_windows": BOUNDARY_EXPANSION_WINDOWS,
        "closure_radius_windows": FINE_CLOSURE_RADIUS,
        "never_cross_continuity_break": True,
        "tie_break": ["descending_component_max_score", "ascending_first_window_id", "ascending_component_id"],
    },
    "budgets": list(PROFILES),
    "budget_rule": "accept whole component plus boundary and closure; never truncate; over-budget is inconclusive",
    "gold_labels_used_for_selection": False,
    "raw_iq_read": False,
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


A0_RULE_HASH = canonical_hash(A0_SELECTION_SPEC)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "na", "null", "none", "n/a"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parse_int(value: Any) -> int | None:
    number = parse_float(value)
    return int(number) if number is not None and number.is_integer() else None


def fmt(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.9g}"
    return value


def percentile(values: Sequence[float], q: float) -> float | None:
    finite = sorted(v for v in values if v is not None and math.isfinite(v))
    if not finite:
        return None
    if len(finite) == 1:
        return finite[0]
    position = (len(finite) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return finite[lower]
    return finite[lower] + (finite[upper] - finite[lower]) * (position - lower)


def median(values: Sequence[float]) -> float | None:
    finite = [v for v in values if v is not None and math.isfinite(v)]
    return statistics.median(finite) if finite else None


def mad(values: Sequence[float], center: float | None = None) -> float | None:
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if not finite:
        return None
    location = statistics.median(finite) if center is None else center
    return statistics.median([abs(v - location) for v in finite])


def task_result_dir(project_root: Path, task: TaskSpec) -> Path:
    return project_root / "scenes" / task.scene_id / "sage_results" / task.result_dir


def stage0_path(project_root: Path, task: TaskSpec) -> Path:
    return task_result_dir(project_root, task) / "stage0_valid_40ms_windows.csv"


def geometry_diagnostic_path(project_root: Path, task: TaskSpec) -> Path | None:
    root = project_root / GEOMETRY_DIAGNOSTIC_ROOT
    matches = sorted(root.glob(f"*/{task.task_id}/seed_00/sampling_window_manifest.csv"))
    if not matches:
        return None
    preferred = [p for p in matches if p.parts[-4] == "blocks11_budget1200"]
    return preferred[0] if preferred else matches[0]


def load_verified_geometry(project_root: Path, task: TaskSpec) -> tuple[Path | None, str | None, dict[int, dict[str, Any]], str, str]:
    path = geometry_diagnostic_path(project_root, task)
    if path is None:
        return None, None, {}, "unavailable", "no v1.1 TOW-aligned diagnostic manifest"
    rows = read_csv_rows(path)
    geometry: dict[int, dict[str, Any]] = {}
    invalid = 0
    for row in rows:
        window_id = parse_int(row.get("window_id"))
        status = str(row.get("geometry_join_status", "")).strip().lower()
        elevation = parse_float(row.get("elevation_deg"))
        if window_id is None:
            continue
        if status == "verified" and elevation is not None:
            geometry[window_id] = {
                "elevation_deg": elevation,
                "azimuth_deg": parse_float(row.get("azimuth_deg")),
                "snr_db_hz": parse_float(row.get("snr_db_hz")),
                "geometry_join_status": "verified",
                "geometry_join_source": str(path),
            }
        else:
            invalid += 1
    if not geometry:
        return path, sha256_file(path), {}, "unavailable", "diagnostic contains no verified window-level rows"
    if invalid:
        warning = f"{invalid} diagnostic rows were not verified; retained only verified rows"
    else:
        warning = ""
    return path, sha256_file(path), geometry, "verified", warning


def load_stage0(project_root: Path, task: TaskSpec) -> TaskData:
    path = stage0_path(project_root, task)
    if not path.is_file():
        raise FileNotFoundError(f"Stage0 catalog missing: {path}")
    source_rows = read_csv_rows(path)
    required = {"window_id", "sample_start_zero_based", "tow_s", "recording_time_s"}
    if source_rows:
        missing = sorted(required - set(source_rows[0]))
        if missing:
            raise ValueError(f"Stage0 catalog missing columns {missing}: {path}")
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for source in source_rows:
        window_id = parse_int(source.get("window_id"))
        if window_id is None or window_id in seen:
            raise ValueError(f"invalid or duplicate window_id in {path}: {source.get('window_id')}")
        seen.add(window_id)
        row = dict(source)
        row["window_id"] = window_id
        row["sample_start_value"] = parse_float(source.get("sample_start_zero_based"))
        row["tow_s_value"] = parse_float(source.get("tow_s"))
        row["recording_time_value"] = parse_float(source.get("recording_time_s"))
        rows.append(row)
    rows.sort(key=lambda item: item["window_id"])
    geometry_path, geometry_hash, geometry_rows, geometry_status, warning = load_verified_geometry(project_root, task)
    return TaskData(
        task=task,
        stage0_path=path,
        stage0_hash=sha256_file(path),
        rows=rows,
        geometry_path=geometry_path,
        geometry_hash=geometry_hash,
        geometry_rows=geometry_rows,
        geometry_status=geometry_status,
        geometry_warning=warning,
    )


def continuity_segments(rows: Sequence[Mapping[str, Any]]) -> tuple[list[int], list[bool], list[bool], list[str]]:
    if not rows:
        return [], [], [], []
    segment_ids = [0] * len(rows)
    to_prev = [False] * len(rows)
    to_next = [False] * len(rows)
    break_reasons = ["start"] + [""] * (len(rows) - 1)
    segment = 0
    for index in range(1, len(rows)):
        previous = rows[index - 1]
        current = rows[index]
        window_ok = current.get("window_id") == previous.get("window_id", 0) + 1
        sample_a = previous.get("sample_start_value")
        sample_b = current.get("sample_start_value")
        tow_a = previous.get("tow_s_value")
        tow_b = current.get("tow_s_value")
        sample_ok = (
            sample_a is not None
            and sample_b is not None
            and abs((sample_b - sample_a) - SAMPLE_RATE_HZ * WINDOW_STEP_SECONDS) <= SAMPLE_STEP_TOLERANCE
        )
        tow_ok = (
            tow_a is not None
            and tow_b is not None
            and abs((tow_b - tow_a) - WINDOW_STEP_SECONDS) <= TOW_STEP_TOLERANCE_SECONDS
        )
        continuous = window_ok and sample_ok and tow_ok
        if continuous:
            to_prev[index] = True
            to_next[index - 1] = True
        else:
            segment += 1
            reasons: list[str] = []
            if not window_ok:
                reasons.append("window_id_gap")
            if not sample_ok:
                reasons.append("sample_gap")
            if not tow_ok:
                reasons.append("tow_gap")
            break_reasons[index] = "+".join(reasons) or "continuity_break"
        segment_ids[index] = segment
    return segment_ids, to_prev, to_next, break_reasons


def previous_difference(values: Sequence[float | None], same_segment: Sequence[bool]) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for index in range(1, len(values)):
        if same_segment[index] and values[index] is not None and values[index - 1] is not None:
            result[index] = values[index] - values[index - 1]
    return result


def rolling_mad_by_segment(values: Sequence[float | None], segment_ids: Sequence[int]) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for index in range(len(values)):
        left = index
        while left > 0 and segment_ids[left - 1] == segment_ids[index] and index - left < ROLLING_RADIUS:
            left -= 1
        right = index
        while right + 1 < len(values) and segment_ids[right + 1] == segment_ids[index] and right - index < ROLLING_RADIUS:
            right += 1
        window = [values[pos] for pos in range(left, right + 1) if values[pos] is not None]
        result[index] = mad(window)
    return result


def circular_difference(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    difference = (current - previous + 180.0) % 360.0 - 180.0
    return difference


def build_feature_rows(data: TaskData) -> list[dict[str, Any]]:
    rows = data.rows
    segment_ids, to_prev, to_next, break_reasons = continuity_segments(rows)
    numeric_names = {
        "cn0": "cn0_db_hz",
        "doppler": "tracking_doppler_hz",
        "code": "code_frequency_hz",
        "speed": "vehicle_speed_kmh",
        "relative_bound": "relative_doppler_bound_hz",
    }
    values: dict[str, list[float | None]] = {
        key: [parse_float(row.get(column)) for row in rows] for key, column in numeric_names.items()
    }
    diffs = {key: previous_difference(series, to_prev) for key, series in values.items()}
    second_doppler: list[float | None] = [None] * len(rows)
    for index in range(2, len(rows)):
        if to_prev[index] and to_prev[index - 1] and diffs["doppler"][index] is not None and diffs["doppler"][index - 1] is not None:
            second_doppler[index] = diffs["doppler"][index] - diffs["doppler"][index - 1]
    cn0_mad = rolling_mad_by_segment(values["cn0"], segment_ids)
    geometry_values: dict[str, list[float | None]] = {
        "elevation": [],
        "azimuth": [],
        "snr": [],
    }
    geometry_statuses: list[str] = []
    for row in rows:
        geometry = data.geometry_rows.get(row["window_id"])
        geometry_values["elevation"].append(geometry.get("elevation_deg") if geometry else None)
        geometry_values["azimuth"].append(geometry.get("azimuth_deg") if geometry else None)
        geometry_values["snr"].append(geometry.get("snr_db_hz") if geometry else None)
        geometry_statuses.append("verified" if geometry else data.geometry_status)
    geometry_diffs: dict[str, list[float | None]] = {"elevation": [None] * len(rows), "azimuth": [None] * len(rows), "snr": [None] * len(rows)}
    for index in range(1, len(rows)):
        if to_prev[index]:
            geometry_diffs["elevation"][index] = (geometry_values["elevation"][index] - geometry_values["elevation"][index - 1]) if geometry_values["elevation"][index] is not None and geometry_values["elevation"][index - 1] is not None else None
            geometry_diffs["azimuth"][index] = circular_difference(geometry_values["azimuth"][index], geometry_values["azimuth"][index - 1])
            geometry_diffs["snr"][index] = (geometry_values["snr"][index] - geometry_values["snr"][index - 1]) if geometry_values["snr"][index] is not None and geometry_values["snr"][index - 1] is not None else None

    missing_field_names = [
        "prompt_i",
        "prompt_q",
        "code_error_chips",
        "code_error_filt_chips",
        "carrier_doppler_rate_hz",
        "code_freq_rate_chips",
        "carrier_lock_test",
        "early",
        "late",
    ]
    all_score_series: dict[str, list[float | None]] = {
        "cn0_drop": [max(0.0, -(value or 0.0)) if value is not None else None for value in diffs["cn0"]],
        "cn0_rolling_mad": cn0_mad,
        "cn0_low_level": [None] * len(rows),
        "doppler_first_difference": [abs(value) if value is not None else None for value in diffs["doppler"]],
        "doppler_second_difference": [abs(value) if value is not None else None for value in second_doppler],
        "code_frequency_difference": [abs(value) if value is not None else None for value in diffs["code"]],
        "speed_difference": [abs(value) if value is not None else None for value in diffs["speed"]],
        "relative_doppler_bound_difference": [abs(value) if value is not None else None for value in diffs["relative_bound"]],
        "geometry_elevation_difference": [abs(value) if value is not None else None for value in geometry_diffs["elevation"]],
        "geometry_azimuth_difference": [abs(value) if value is not None else None for value in geometry_diffs["azimuth"]],
        "geometry_snr_difference": [abs(value) if value is not None else None for value in geometry_diffs["snr"]],
    }
    cn0_center = median(values["cn0"])
    all_score_series["cn0_low_level"] = [
        max(0.0, (cn0_center - value)) if value is not None and cn0_center is not None else None for value in values["cn0"]
    ]
    stats: dict[str, tuple[float | None, float]] = {}
    for name, series in all_score_series.items():
        center = median(series)
        scale = max(1.0, 1.4826 * (mad(series, center) or 0.0)) if center is not None else 1.0
        stats[name] = (center, scale)

    feature_rows: list[dict[str, Any]] = []
    weights = {item["name"]: float(item["weight"]) for item in A0_SELECTION_SPEC["score_terms"]}
    for index, source in enumerate(rows):
        feature_missing = list(missing_field_names)
        if values["speed"][index] is None:
            feature_missing.append("vehicle_speed_kmh_value")
        if data.geometry_status != "verified" or not data.geometry_rows.get(source["window_id"]):
            feature_missing.extend(["elevation_deg", "azimuth_deg", "snr_db_hz", "geometry_unavailable"])
        if not to_prev[index]:
            feature_missing.append("continuity_prev")
        terms: dict[str, float | None] = {}
        for name, series in all_score_series.items():
            value = series[index]
            center, scale = stats[name]
            if value is None or center is None:
                terms[name] = None
                continue
            raw_z = abs(value - center) / scale
            terms[name] = min(6.0, raw_z)
        available = [(name, term) for name, term in terms.items() if term is not None and name in weights]
        denominator = sum(weights[name] for name, _ in available)
        score = sum(weights[name] * float(term) for name, term in available) / denominator if denominator else 0.0
        feature_status = "complete" if len(available) >= 5 and not any(name in feature_missing for name in ("continuity_prev", "geometry_unavailable")) else ("partial" if available else "insufficient")
        row: dict[str, Any] = {
            "task_id": data.task.task_id,
            "scene_id": data.task.scene_id,
            "prn": data.task.prn,
            "tracking_channel": data.task.tracking_channel,
            "sample_rate_hz": data.task.sample_rate_hz,
            "window_id": source["window_id"],
            "segment_id": segment_ids[index],
            "recording_time_s": fmt(source.get("recording_time_value")),
            "tow_s": fmt(source.get("tow_s_value")),
            "sample_start_zero_based": fmt(source.get("sample_start_value")),
            "continuity_to_prev": int(to_prev[index]),
            "continuity_to_next": int(to_next[index]),
            "break_reason": break_reasons[index],
            "cn0_db_hz": fmt(values["cn0"][index]),
            "cn0_delta_prev_db": fmt(diffs["cn0"][index]),
            "cn0_rolling_mad_db": fmt(cn0_mad[index]),
            "tracking_doppler_hz": fmt(values["doppler"][index]),
            "tracking_doppler_delta_hz": fmt(diffs["doppler"][index]),
            "tracking_doppler_second_delta_hz": fmt(second_doppler[index]),
            "code_frequency_hz": fmt(values["code"][index]),
            "code_frequency_delta_hz": fmt(diffs["code"][index]),
            "vehicle_speed_kmh": fmt(values["speed"][index]),
            "vehicle_speed_delta_kmh": fmt(diffs["speed"][index]),
            "relative_doppler_bound_hz": fmt(values["relative_bound"][index]),
            "relative_doppler_bound_delta_hz": fmt(diffs["relative_bound"][index]),
            "carrier_lock_test": "",
            "elevation_deg": fmt(geometry_values["elevation"][index]),
            "azimuth_deg": fmt(geometry_values["azimuth"][index]),
            "snr_db_hz": fmt(geometry_values["snr"][index]),
            "elevation_delta_deg": fmt(geometry_diffs["elevation"][index]),
            "azimuth_delta_deg": fmt(geometry_diffs["azimuth"][index]),
            "snr_delta_db_hz": fmt(geometry_diffs["snr"][index]),
            "geometry_join_status": geometry_statuses[index],
            "geometry_join_source": str(data.geometry_path) if data.geometry_path else "",
            "feature_score": fmt(score),
            "feature_status": feature_status,
            "feature_missing": ";".join(sorted(set(feature_missing))),
            "score_rule_hash": A0_RULE_HASH,
        }
        for name, term in terms.items():
            row[f"score_term_{name}"] = fmt(term)
        feature_rows.append(row)
    return feature_rows


def segment_indices(feature_rows: Sequence[Mapping[str, Any]]) -> dict[int, list[int]]:
    result: dict[int, list[int]] = {}
    for index, row in enumerate(feature_rows):
        result.setdefault(int(row["segment_id"]), []).append(index)
    return result


def build_components(feature_rows: Sequence[Mapping[str, Any]]) -> list[Component]:
    if not feature_rows:
        return []
    scores = [parse_float(row.get("feature_score")) for row in feature_rows]
    segments = segment_indices(feature_rows)
    result: list[Component] = []
    next_id = 1
    for segment_id, indices in segments.items():
        high = [index for index in indices if scores[index] is not None and scores[index] >= A0_SELECTION_SPEC["hysteresis"]["high_threshold"]]
        if not high:
            continue
        runs: list[list[int]] = []
        current: list[int] = []
        for index in high:
            if current and index != current[-1] + 1:
                runs.append(current)
                current = []
            current.append(index)
        if current:
            runs.append(current)
        expanded: list[list[int]] = []
        index_set = set(indices)
        for run in runs:
            left = run[0]
            while left - 1 in index_set and scores[left - 1] is not None and scores[left - 1] >= A0_SELECTION_SPEC["hysteresis"]["low_threshold"]:
                left -= 1
            right = run[-1]
            while right + 1 in index_set and scores[right + 1] is not None and scores[right + 1] >= A0_SELECTION_SPEC["hysteresis"]["low_threshold"]:
                right += 1
            expanded.append(list(range(left, right + 1)))
        merged: list[list[int]] = []
        for run in expanded:
            if merged and run[0] - merged[-1][-1] - 1 <= BRIDGE_GAP_WINDOWS:
                gap = list(range(merged[-1][-1] + 1, run[0]))
                if all(index in index_set for index in gap):
                    merged[-1].extend(gap)
                    merged[-1].extend(run)
                else:
                    merged.append(run)
            else:
                merged.append(run)
        for run in merged:
            core_indices = [index for index in run if scores[index] is not None and scores[index] >= A0_SELECTION_SPEC["hysteresis"]["low_threshold"]]
            core_windows = tuple(int(feature_rows[index]["window_id"]) for index in core_indices)
            component_windows = tuple(int(feature_rows[index]["window_id"]) for index in run)
            promoted_indices = set(run)
            left = run[0] - BOUNDARY_EXPANSION_WINDOWS
            right = run[-1] + BOUNDARY_EXPANSION_WINDOWS
            for index in range(left, right + 1):
                if index in index_set:
                    promoted_indices.add(index)
            promoted_windows = tuple(sorted(int(feature_rows[index]["window_id"]) for index in promoted_indices))
            candidate_indices: set[int] = set(promoted_indices)
            continuity_missing = False
            for index in list(promoted_indices):
                for offset in range(1, FINE_CLOSURE_RADIUS + 1):
                    for neighbor in (index - offset, index + offset):
                        if neighbor not in index_set:
                            continuity_missing = True
                        else:
                            candidate_indices.add(neighbor)
            candidate_windows = tuple(sorted(int(feature_rows[index]["window_id"]) for index in candidate_indices))
            result.append(
                Component(
                    component_id=f"seg{segment_id:03d}_c{next_id:04d}",
                    segment_id=segment_id,
                    core_windows=tuple(sorted(core_windows)),
                    component_windows=component_windows,
                    promoted_windows=promoted_windows,
                    fine_candidate_windows=candidate_windows,
                    max_score=max(float(scores[index]) for index in run if scores[index] is not None),
                    first_window=min(component_windows),
                    last_window=max(component_windows),
                    continuity_missing=continuity_missing,
                )
            )
            next_id += 1
    return result


def apply_budget(feature_rows: Sequence[Mapping[str, Any]], components: Sequence[Component], budget: int) -> tuple[set[int], bool, int, dict[str, str]]:
    by_window = {int(row["window_id"]): row for row in feature_rows}
    ordered = sorted(components, key=lambda item: (-item.max_score, item.first_window, item.component_id))
    selected: set[int] = set()
    budget_exhausted = False
    inconclusive = 0
    component_status: dict[str, str] = {}
    for component in ordered:
        candidate = set(component.fine_candidate_windows)
        projected = len(selected | candidate)
        if component.continuity_missing:
            component_status[component.component_id] = "inconclusive_continuity_missing"
            inconclusive += 1
            continue
        if projected <= budget:
            selected.update(candidate)
            component_status[component.component_id] = "fine_selected"
        else:
            component_status[component.component_id] = "inconclusive_budget_exhausted"
            inconclusive += 1
            budget_exhausted = True
    # The lookup is intentional: it validates the whole selected set is part
    # of the Stage0 universe and makes accidental synthetic window ids fail.
    if any(window_id not in by_window for window_id in selected):
        raise AssertionError("fine selection contains a window outside Stage0")
    return selected, budget_exhausted, inconclusive, component_status


def promotion_rows_for_profile(feature_rows: Sequence[Mapping[str, Any]], components: Sequence[Component], fine_windows: set[int], component_status: Mapping[str, str], budget: int, budget_exhausted: bool) -> list[dict[str, Any]]:
    component_by_window: dict[int, list[Component]] = {}
    promoted_by_window: dict[int, list[Component]] = {}
    for component in components:
        for window_id in component.component_windows:
            component_by_window.setdefault(window_id, []).append(component)
        for window_id in component.promoted_windows:
            promoted_by_window.setdefault(window_id, []).append(component)
    rows: list[dict[str, Any]] = []
    for source in feature_rows:
        window_id = int(source["window_id"])
        component_list = component_by_window.get(window_id, [])
        promoted_list = promoted_by_window.get(window_id, [])
        component = component_list[0] if component_list else (promoted_list[0] if promoted_list else None)
        if window_id in fine_windows:
            status = "fine_scanned"
            reason = "component_boundary_closure_selected"
        elif window_id in promoted_by_window:
            status = "guard_scanned" if component and window_id not in component.component_windows else "promoted_not_budget_selected"
            reason = "component_boundary_or_closure_not_budget_selected"
        else:
            status = "not_promoted"
            reason = "coarse_not_promoted"
        row = dict(source)
        row.update(
            {
                "budget": budget,
                "promotion_status": status,
                "promotion_reason": reason,
                "promotion_component_id": component.component_id if component else "",
                "not_promoted": int(status == "not_promoted"),
                "coverage_status": "inconclusive" if status != "fine_scanned" and budget_exhausted and component else ("coarse_promoted" if promoted_list else "coarse_not_promoted"),
                "fine_scanned": int(window_id in fine_windows),
                "guard_scanned": int(status == "guard_scanned"),
                "coarse_scanned": 1,
                "gold_labels_used_for_selection": "false",
                "selection_phase": "a0_feature_only",
                "planner_version": PLANNER_VERSION,
                "rule_hash": A0_RULE_HASH,
            }
        )
        rows.append(row)
    return rows


def selection_fieldnames() -> list[str]:
    return [
        "task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "window_id", "segment_id",
        "recording_time_s", "tow_s", "sample_start_zero_based", "continuity_to_prev", "continuity_to_next",
        "break_reason", "cn0_db_hz", "cn0_delta_prev_db", "cn0_rolling_mad_db", "tracking_doppler_hz",
        "tracking_doppler_delta_hz", "tracking_doppler_second_delta_hz", "code_frequency_hz", "code_frequency_delta_hz",
        "vehicle_speed_kmh", "vehicle_speed_delta_kmh", "relative_doppler_bound_hz", "relative_doppler_bound_delta_hz",
        "carrier_lock_test", "elevation_deg", "azimuth_deg", "snr_db_hz", "elevation_delta_deg", "azimuth_delta_deg",
        "snr_delta_db_hz", "geometry_join_status", "geometry_join_source", "feature_score", "feature_status", "feature_missing",
        "score_rule_hash", "score_term_cn0_drop", "score_term_cn0_rolling_mad", "score_term_cn0_low_level",
        "score_term_doppler_first_difference", "score_term_doppler_second_difference", "score_term_code_frequency_difference",
        "score_term_speed_difference", "score_term_relative_doppler_bound_difference", "score_term_geometry_elevation_difference",
        "score_term_geometry_azimuth_difference", "score_term_geometry_snr_difference", "budget", "promotion_status",
        "promotion_reason", "promotion_component_id", "not_promoted", "coverage_status", "fine_scanned", "guard_scanned",
        "coarse_scanned", "gold_labels_used_for_selection", "selection_phase", "planner_version", "rule_hash",
    ]


def freeze_selection(project_root: Path, output_root: Path, task_data: Sequence[TaskData]) -> dict[str, Any]:
    selection_freeze = {
        "planner_version": PLANNER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "rule_hash": A0_RULE_HASH,
        "selection_frozen": True,
        "selection_frozen_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "gold_labels_used_for_selection": False,
        "raw_iq_read": False,
        "forbidden_source_read_before_freeze": ["stage1", "stage2", "stage3", "stage4", "gold_event_location"],
        "input_scope": [
            {
                "task_id": item.task.task_id,
                "stage0_path": str(item.stage0_path),
                "stage0_sha256": item.stage0_hash,
                "geometry_diagnostic_path": str(item.geometry_path) if item.geometry_path else "",
                "geometry_diagnostic_sha256": item.geometry_hash or "",
                "geometry_status": item.geometry_status,
            }
            for item in task_data
        ],
        "profiles": [{"fine_budget": budget, "closure_radius": FINE_CLOSURE_RADIUS} for budget in PROFILES],
    }
    freeze_bytes = canonical_json(selection_freeze).encode("utf-8")
    selection_freeze["selection_freeze_sha256"] = hashlib.sha256(freeze_bytes).hexdigest()
    write_json(output_root / "selection_freeze_v1_2_a0.json", selection_freeze)
    return selection_freeze


def _gold_read_guard(selection_frozen: Mapping[str, Any]) -> None:
    if not selection_frozen.get("selection_frozen") or selection_frozen.get("gold_labels_used_for_selection") is not False:
        raise RuntimeError("gold read attempted before immutable A0 selection freeze")


def load_gold_after_freeze(project_root: Path, task: TaskSpec, selection_frozen: Mapping[str, Any]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    _gold_read_guard(selection_frozen)
    result_dir = task_result_dir(project_root, task)
    stage4_path = result_dir / "stage4_joint_summary.csv"
    stage3_path = result_dir / "stage3_reliable_centers.csv"
    confirmed: list[int] = []
    reliable: list[int] = []
    if stage4_path.is_file():
        for row in read_csv_rows(stage4_path):
            valid = parse_int(row.get("joint_valid")) == 1
            count = parse_int(row.get("joint_multipath_count")) or 0
            center = parse_int(row.get("center_window_id"))
            if valid and count > 0 and center is not None:
                confirmed.append(center)
    if stage3_path.is_file():
        for row in read_csv_rows(stage3_path):
            center = parse_int(row.get("center_window_id"))
            reliable_flag = parse_int(row.get("reliable_multipath")) == 1
            if reliable_flag and center is not None:
                reliable.append(center)
    return tuple(sorted(set(confirmed))), tuple(sorted(set(reliable)))


def closure_windows(centers: Iterable[int], universe: set[int], radius: int) -> tuple[set[int], dict[int, list[int]]]:
    expected: set[int] = set()
    missing: dict[int, list[int]] = {}
    for center in sorted(set(centers)):
        wanted = set(range(center - radius, center + radius + 1))
        absent = sorted(wanted - universe)
        expected.update(wanted & universe)
        if absent:
            missing[center] = absent
    return expected, missing


def replay_task_profile(task_data: TaskData, profile: ProfileResult, confirmed: Sequence[int], reliable: Sequence[int]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    universe = {int(row["window_id"]) for row in profile.feature_rows}
    promoted = profile.promoted_windows
    fine = profile.fine_windows
    event_centers = tuple(sorted(set(confirmed)))
    event_closure, event_closure_missing = closure_windows(event_centers, universe, FINE_CLOSURE_RADIUS)
    reliable_closure, reliable_closure_missing = closure_windows(reliable, universe, FINE_CLOSURE_RADIUS)
    initial_center_hits = sum(center in promoted for center in event_centers)
    final_center_hits = sum(center in fine for center in event_centers)
    initial_closure_hits = sum(window_id in promoted for window_id in event_closure)
    final_closure_hits = sum(window_id in fine for window_id in event_closure)
    reliable_closure_hits = sum(window_id in fine for window_id in reliable_closure)
    event_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    feature_by_window = {int(row["window_id"]): row for row in profile.feature_rows}
    component_by_window: dict[int, Component] = {}
    for component in profile.components:
        for window_id in component.fine_candidate_windows:
            component_by_window[window_id] = component
    for center in event_centers:
        closure = set(range(center - FINE_CLOSURE_RADIUS, center + FINE_CLOSURE_RADIUS + 1)) & universe
        missing = sorted(set(range(center - FINE_CLOSURE_RADIUS, center + FINE_CLOSURE_RADIUS + 1)) - universe)
        uncovered = sorted(closure - fine)
        if center not in fine or uncovered or missing:
            if center not in promoted:
                primary = "score_below_threshold"
            elif profile.budget_exhausted and center not in fine:
                primary = "budget_exhausted"
            elif missing:
                primary = "continuity_missing"
            elif center in fine and uncovered:
                primary = "component_gap"
            else:
                primary = "inconclusive"
            if feature_by_window.get(center, {}).get("geometry_join_status") != "verified" and primary == "score_below_threshold":
                primary = "geometry_unavailable"
            failure_rows.append(
                {
                    "task_id": task_data.task.task_id,
                    "budget": profile.budget,
                    "event_center_window_id": center,
                    "failure_reason": primary,
                    "center_initial_promoted": int(center in promoted),
                    "center_final_fine": int(center in fine),
                    "uncovered_closure_window_ids": ";".join(map(str, uncovered)),
                    "missing_closure_window_ids": ";".join(map(str, missing)),
                    "feature_score_at_center": feature_by_window.get(center, {}).get("feature_score", ""),
                    "feature_missing_at_center": feature_by_window.get(center, {}).get("feature_missing", ""),
                    "component_id": component_by_window.get(center).component_id if center in component_by_window else "",
                    "gold_labels_used_for_selection": "false",
                }
            )
        event_rows.append(
            {
                "record_type": "confirmed_event",
                "task_id": task_data.task.task_id,
                "scene_id": task_data.task.scene_id,
                "prn": task_data.task.prn,
                "budget": profile.budget,
                "event_center_window_id": center,
                "initial_promotion_center_hit": int(center in promoted),
                "final_fine_center_hit": int(center in fine),
                "event_closure_expected_count": len(closure),
                "event_closure_initial_hit_count": sum(window_id in promoted for window_id in closure),
                "event_closure_final_hit_count": sum(window_id in fine for window_id in closure),
                "event_closure_missing_count": len(missing),
                "failure_reason": next((row["failure_reason"] for row in failure_rows if row["event_center_window_id"] == center), ""),
                "gold_labels_used_for_selection": "false",
            }
        )
    if not event_rows:
        event_rows.append(
            {
                "record_type": "task_summary",
                "task_id": task_data.task.task_id,
                "scene_id": task_data.task.scene_id,
                "prn": task_data.task.prn,
                "budget": profile.budget,
                "event_center_window_id": "",
                "initial_promotion_center_hit": "",
                "final_fine_center_hit": "",
                "event_closure_expected_count": "",
                "event_closure_initial_hit_count": "",
                "event_closure_final_hit_count": "",
                "event_closure_missing_count": "",
                "failure_reason": "no_confirmed_event_control",
                "gold_labels_used_for_selection": "false",
            }
        )
    center_recall = (final_center_hits / len(event_centers)) if event_centers else None
    initial_center_recall = (initial_center_hits / len(event_centers)) if event_centers else None
    initial_closure_recall = (initial_closure_hits / len(event_closure)) if event_closure else None
    final_closure_recall = (final_closure_hits / len(event_closure)) if event_closure else None
    reliable_recall = (reliable_closure_hits / len(reliable_closure)) if reliable_closure else None
    summary = {
        "task_id": task_data.task.task_id,
        "task_group": task_data.task.group,
        "scene_id": task_data.task.scene_id,
        "prn": task_data.task.prn,
        "tracking_channel": task_data.task.tracking_channel,
        "sample_rate_hz": task_data.task.sample_rate_hz,
        "fine_budget": profile.budget,
        "N0": len(profile.feature_rows),
        "Npromoted": len(profile.promoted_windows),
        "promotion_fraction": len(profile.promoted_windows) / len(profile.feature_rows) if profile.feature_rows else 0.0,
        "component_count": len(profile.components),
        "Nfine_total": len(profile.fine_windows),
        "fine_reduction_fraction": 1.0 - len(profile.fine_windows) / len(profile.feature_rows) if profile.feature_rows else 0.0,
        "budget_exhausted": int(profile.budget_exhausted),
        "inconclusive_count": profile.inconclusive_components,
        "confirmed_event_count": len(event_centers),
        "reliable_center_count": len(set(reliable)),
        "initial_event_center_recall": initial_center_recall,
        "final_event_center_recall": center_recall,
        "initial_pm2_closure_recall": initial_closure_recall,
        "final_pm2_closure_recall": final_closure_recall,
        "stage3_reliable_center_closure_recall": reliable_recall,
        "event_closure_missing_count": sum(len(value) for value in event_closure_missing.values()),
        "reliable_closure_missing_count": sum(len(value) for value in reliable_closure_missing.values()),
        "geometry_status": task_data.geometry_status,
        "geometry_warning": task_data.geometry_warning,
        "gold_labels_used_for_selection": "false",
        "planner_version": PLANNER_VERSION,
        "rule_hash": A0_RULE_HASH,
    }
    return event_rows, summary, failure_rows


def profile_for_task(data: TaskData, budget: int) -> ProfileResult:
    feature_rows = build_feature_rows(data)
    components = build_components(feature_rows)
    fine_windows, budget_exhausted, inconclusive, component_status = apply_budget(feature_rows, components, budget)
    promoted_windows: set[int] = set()
    for component in components:
        promoted_windows.update(component.promoted_windows)
    promotion_rows = promotion_rows_for_profile(feature_rows, components, fine_windows, component_status, budget, budget_exhausted)
    selection_hash = canonical_hash(
        {
            "task_id": data.task.task_id,
            "budget": budget,
            "component_ids": [component.component_id for component in components],
            "promoted_windows": sorted(promoted_windows),
            "fine_windows": sorted(fine_windows),
            "rule_hash": A0_RULE_HASH,
        }
    )
    return ProfileResult(
        task=data.task,
        budget=budget,
        feature_rows=feature_rows,
        promotion_rows=promotion_rows,
        components=list(components),
        promoted_windows=promoted_windows,
        fine_windows=fine_windows,
        budget_exhausted=budget_exhausted,
        inconclusive_components=inconclusive,
        selection_hash=selection_hash,
        summary={},
    )


def report_control_rows(profile_results: Sequence[ProfileResult], task_data_by_id: Mapping[str, TaskData]) -> list[dict[str, Any]]:
    controls = {"reference_F1023_V70_D0117_P2_G25_ch0", "reference_F1023_V70_D0117_P2_G28_ch1", "waveA_F1023_v50_D0127_P1_G25_ch0", "wave2A_F1023_V120_D0121_P2_G11_ch0"}
    rows: list[dict[str, Any]] = []
    for profile in profile_results:
        if profile.task.task_id not in controls:
            continue
        scores = [parse_float(row.get("feature_score")) for row in profile.feature_rows]
        rows.append(
            {
                "task_id": profile.task.task_id,
                "scene_id": profile.task.scene_id,
                "prn": profile.task.prn,
                "budget": profile.budget,
                "N0": len(profile.feature_rows),
                "score_p10": percentile([v for v in scores if v is not None], 0.10),
                "score_p50": percentile([v for v in scores if v is not None], 0.50),
                "score_p90": percentile([v for v in scores if v is not None], 0.90),
                "score_max": max((v for v in scores if v is not None), default=None),
                "promotion_fraction": len(profile.promoted_windows) / len(profile.feature_rows) if profile.feature_rows else 0.0,
                "component_count": len(profile.components),
                "Nfine_total": len(profile.fine_windows),
                "geometry_status": task_data_by_id[profile.task.task_id].geometry_status,
                "promotion_is_not_a_false_positive_label": "true",
                "not_promoted_is_not_LOS_label": "true",
            }
        )
    return rows


def write_report(project_root: Path, output_root: Path, summaries: Sequence[Mapping[str, Any]], controls: Sequence[Mapping[str, Any]], failures: Sequence[Mapping[str, Any]], selection_frozen: Mapping[str, Any]) -> Path:
    positive_tasks = [row for row in summaries if row["task_group"] in {"reference", "waveA"} and row["confirmed_event_count"] > 0]
    hard_pass = all(
        row["final_event_center_recall"] == 1.0 and row["final_pm2_closure_recall"] == 1.0
        for row in positive_tasks
    ) and bool(positive_tasks)
    report_path = project_root / "docs" / "BATCH_SAMPLED_V1_2_A0_OFFLINE_COVERAGE_REPORT.md"
    lines = [
        "# batch-sampled-v1.2 A0 Offline Coverage Report",
        "",
        f"- Planner: `{PLANNER_VERSION}`",
        f"- Rule hash: `{A0_RULE_HASH}`",
        f"- Selection freeze hash: `{selection_frozen['selection_freeze_sha256']}`",
        "- Scope: 11 fixed 10.23 MHz gold tasks; Stage0 and verified TOW-aligned geometry only during selection.",
        "- Raw IQ/MATLAB/SAGE: not read or executed.",
        "- `gold_labels_used_for_selection=false`: confirmed; Stage3/Stage4 were opened only after selection manifests were frozen.",
        "",
        "## Decision",
        "",
        f"**{'PASS' if hard_pass else 'FAIL'}** — the hard gate requires every reference and Wave-A known confirmed event center and its ±2 closure to reach 100% recall in every reported budget profile. A0 is not permitted as the sole production promoter unless this gate passes.",
        "",
        "## Per-task/profile replay",
        "",
        "| task | budget | N0 | Npromoted | components | Nfine | initial center | final center | initial ±2 | final ±2 | Stage3 closure | budget exhausted | inconclusive | geometry |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summaries:
        def pct(value: Any) -> str:
            return "n/a" if value is None else f"{float(value) * 100:.1f}%"
        lines.append(
            f"| {row['task_id']} | {row['fine_budget']} | {row['N0']} | {row['Npromoted']} | {row['component_count']} | {row['Nfine_total']} | {pct(row['initial_event_center_recall'])} | {pct(row['final_event_center_recall'])} | {pct(row['initial_pm2_closure_recall'])} | {pct(row['final_pm2_closure_recall'])} | {pct(row['stage3_reliable_center_closure_recall'])} | {row['budget_exhausted']} | {row['inconclusive_count']} | {row['geometry_status']} |"
        )
    lines.extend([
        "",
        "## Controls",
        "",
        "Promotion is a coarse coverage decision, not a multipath label. `not_promoted` is not LOS. The following controls are reported to expose promotion behavior only:",
        "",
        "| task | budget | score P10 | P50 | P90 | max | promotion fraction | components | Nfine | geometry |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for row in controls:
        lines.append(f"| {row['task_id']} | {row['budget']} | {fmt(row['score_p10'])} | {fmt(row['score_p50'])} | {fmt(row['score_p90'])} | {fmt(row['score_max'])} | {float(row['promotion_fraction']) * 100:.1f}% | {row['component_count']} | {row['Nfine_total']} | {row['geometry_status']} |")
    lines.extend([
        "",
        "## Oracle-free failure analysis",
        "",
        "A missed event is classified only after the frozen replay, using `score_below_threshold`, `component_gap`, `budget_exhausted`, `continuity_missing`, `geometry_unavailable`, or `inconclusive`. No rule or threshold was changed in response to an event position.",
        "",
        "| task | budget | event center | reason | score | feature missing | component |",
        "|---|---:|---:|---|---:|---|---|",
    ])
    if failures:
        for row in failures:
            lines.append(f"| {row['task_id']} | {row['budget']} | {row['event_center_window_id']} | {row['failure_reason']} | {row['feature_score_at_center']} | {row['feature_missing_at_center']} | {row['component_id']} |")
    else:
        lines.append("| none | | | no missed confirmed event center/closure | | | |")
    lines.extend([
        "",
        "## Method and safeguards",
        "",
        "- Stage0 remains the complete mother set; every window receives an A0 feature row.",
        "- Rolling MAD and derivatives stop at window/sample/TOW discontinuities.",
        "- High/low hysteresis, a fixed two-window bridge, one-window boundary expansion, and ±2 closure are frozen in the rule hash.",
        "- A budget accepts complete component + boundary + closure units. It never truncates an over-budget unit; such a unit is `inconclusive`.",
        "- Verified geometry comes only from the v1.1 TOW-aligned diagnostic. Wave-A G25 remains `warning_fallback` and its elevation/azimuth/SNR are missing.",
        "- Stage3/Stage4 are posterior gold sources, not promoter inputs. Stage1 rows were not needed for this center/closure replay.",
        "",
        "## Next action",
    ])
    if hard_pass:
        lines.append("A0 may enter an independent review only; do not generate a sampled SAGE request directly.")
    else:
        lines.append("Do not run a sampled pilot and do not keep tuning A0 against gold. Proceed to the design-specified minimal B1/B2/C1 raw-coarse prototype on G16, Wave-A G25, and Wave-2A G11; this prototype is not part of A0 and must be separately approved.")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def run(project_root: Path, output_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to reuse non-empty A0 output namespace: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    task_data = [load_stage0(project_root, task) for task in GOLD_TASKS]
    task_data_by_id = {item.task.task_id: item for item in task_data}
    selection_frozen = freeze_selection(project_root, output_root, task_data)
    profile_results: list[ProfileResult] = []
    for item in task_data:
        for budget in PROFILES:
            profile = profile_for_task(item, budget)
            profile_results.append(profile)
            profile_dir = output_root / item.task.task_id / f"F{budget}"
            write_csv(profile_dir / "coarse_features.csv", profile.feature_rows, selection_fieldnames()[:50])
            write_csv(profile_dir / "promotion_manifest.csv", profile.promotion_rows, selection_fieldnames())
            component_rows = [
                {
                    "task_id": item.task.task_id,
                    "budget": budget,
                    "component_id": component.component_id,
                    "segment_id": component.segment_id,
                    "first_window": component.first_window,
                    "last_window": component.last_window,
                    "core_count": len(component.core_windows),
                    "component_count": len(component.component_windows),
                    "promoted_count": len(component.promoted_windows),
                    "fine_candidate_count": len(component.fine_candidate_windows),
                    "max_score": component.max_score,
                    "continuity_missing": int(component.continuity_missing),
                    "selection_hash": profile.selection_hash,
                }
                for component in profile.components
            ]
            write_csv(profile_dir / "promotion_components.csv", component_rows, list(component_rows[0]) if component_rows else ["task_id", "budget", "component_id"])
    # This is the first point at which the posterior gold files may be read.
    summaries: list[dict[str, Any]] = []
    all_failure_rows: list[dict[str, Any]] = []
    replay_rows_by_profile: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for profile in profile_results:
        confirmed, reliable = load_gold_after_freeze(project_root, profile.task, selection_frozen)
        replay_rows, summary, failures = replay_task_profile(task_data_by_id[profile.task.task_id], profile, confirmed, reliable)
        profile.summary = summary
        summaries.append(summary)
        all_failure_rows.extend(failures)
        profile_dir = output_root / profile.task.task_id / f"F{profile.budget}"
        write_csv(profile_dir / "coverage_replay_v1_2_a0.csv", replay_rows, [
            "record_type", "task_id", "scene_id", "prn", "budget", "event_center_window_id", "initial_promotion_center_hit",
            "final_fine_center_hit", "event_closure_expected_count", "event_closure_initial_hit_count", "event_closure_final_hit_count",
            "event_closure_missing_count", "failure_reason", "gold_labels_used_for_selection",
        ])
    controls = report_control_rows(profile_results, task_data_by_id)
    summary_fields = list(summaries[0]) if summaries else []
    write_csv(output_root / "a0_profile_summary.csv", summaries, summary_fields)
    write_csv(output_root / "a0_event_failure_analysis.csv", all_failure_rows, list(all_failure_rows[0]) if all_failure_rows else ["task_id", "budget", "event_center_window_id", "failure_reason"])
    write_csv(output_root / "a0_control_promotion_summary.csv", controls, list(controls[0]) if controls else ["task_id", "budget"])
    output_hashes: dict[str, str] = {}
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.name != "sampling_validation_manifest_v1_2_a0.json":
            output_hashes[str(path.relative_to(output_root))] = sha256_file(path)
    manifest = {
        "planner_version": PLANNER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "rule_hash": A0_RULE_HASH,
        "selection_freeze_sha256": selection_frozen["selection_freeze_sha256"],
        "output_namespace": str(output_root),
        "gold_labels_used_for_selection": False,
        "raw_iq_read": False,
        "matlab_or_sage_executed": False,
        "gold_replay_after_selection_freeze": True,
        "tasks": [item.task.__dict__ for item in task_data],
        "profiles": list(PROFILES),
        "summary_path": str(output_root / "a0_profile_summary.csv"),
        "control_summary_path": str(output_root / "a0_control_promotion_summary.csv"),
        "failure_analysis_path": str(output_root / "a0_event_failure_analysis.csv"),
        "output_file_sha256": output_hashes,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    write_json(output_root / "sampling_validation_manifest_v1_2_a0.json", manifest)
    report_path = write_report(project_root, output_root, summaries, controls, all_failure_rows, selection_frozen)
    return {
        "manifest": output_root / "sampling_validation_manifest_v1_2_a0.json",
        "report": report_path,
        "summaries": summaries,
        "controls": controls,
        "failures": all_failure_rows,
        "output_root": output_root,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-root", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    output_root = args.output_root.resolve() if args.output_root else project_root / OUTPUT_NAMESPACE
    result = run(project_root, output_root)
    print(f"A0_OFFLINE_COMPLETED report={result['report']}")
    print(f"MANIFEST={result['manifest']}")
    print(f"RULE_HASH={A0_RULE_HASH}")
    for row in result["summaries"]:
        print(
            f"{row['task_id']} F{row['fine_budget']} N0={row['N0']} Npromoted={row['Npromoted']} "
            f"Nfine={row['Nfine_total']} center={row['final_event_center_recall']} "
            f"closure={row['final_pm2_closure_recall']} stage3closure={row['stage3_reliable_center_closure_recall']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
