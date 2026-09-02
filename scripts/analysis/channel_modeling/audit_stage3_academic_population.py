#!/usr/bin/env python3
"""Reassess the Stage3 population for academic GNSS channel modelling.

This audit is deliberately read-only with respect to the existing SAGE and
database namespaces.  It reads Stage0/Stage3/Stage4 CSV artifacts, run
contexts, the existing geometry alignment, and the frozen provenance files.
It never opens raw IQ, starts MATLAB/SAGE, or fits a new statistical model.
All generated tables are written to a caller-supplied, new-only namespace.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


INGESTION_ID = "ingestion_20260825_event_path_v1"
ALIGNMENT_ID = "alignment_20260825_tow_geometry_scene_v1"
INGESTION_REL = Path("dataset/multipath_event_database/v1/partitions") / (
    f"ingestion_id={INGESTION_ID}"
)
ALIGNMENT_REL = Path("dataset/multipath_event_database/v1/partitions") / (
    f"alignment_id={ALIGNMENT_ID}"
)
INGESTION_MANIFEST_REL = Path(
    "dataset/multipath_event_database/v1/manifests/ingestions"
) / f"{INGESTION_ID}.json"
SCENE_METADATA_REL = Path(
    "dataset_generation_logs/production_planning_10mhz_20260812/"
    "scene_metadata_10MHz.csv"
)
PRODUCTION_MANIFEST_REL = Path(
    "dataset_generation_logs/production_planning_10mhz_20260812/"
    "production_task_manifest_10MHz_v1.json"
)
PRODUCTION_INVENTORY_REL = Path(
    "dataset_generation_logs/production_planning_10mhz_20260812/"
    "production_inventory_10MHz.csv"
)
PIPELINE_REL = Path("scripts/sage_pipeline/run_nav_sage_pipeline.m")
WRAPPER_REL = Path("scripts/sage_pipeline/Invoke-BatchSageWindows.ps1")
EXECUTOR_REL = Path("scripts/sage_pipeline/run_batch_sage.py")

GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
GPS_WEEK_SECONDS = 604800.0
GPS_UTC_LEAP_SECONDS = 18
MAX_GEOMETRY_DELTA_SECONDS = 5.0

PERSISTENCE_RADIUS_WINDOWS = 2
PERSISTENCE_MIN_CONSECUTIVE = 3
PERSISTENCE_DELAY_TOLERANCE_SAMPLES = 1.5
PERSISTENCE_DOPPLER_TOLERANCE_HZ = 40.0
PERSISTENCE_POWER_TOLERANCE_DB = 10.0
STAGE4_MAXIMUM_JOINT_CENTERS = 8

ENVIRONMENTS = [
    "Urban",
    "Special Reflective",
    "Mountain/Valley",
    "Highway/Open",
]
BANDS = ["LOW", "MID", "HIGH"]

RUN_FIELDS = [
    "run_id",
    "logical_run_key",
    "scene_id",
    "prn",
    "tracking_channel",
    "source_result_relpath",
    "qa_status",
    "run_status",
    "stage3_status",
    "stage3_files_complete",
    "run_context_present",
    "context_missing_legacy",
    "environment_class",
    "academic_run_eligible",
    "academic_exclusion_reason",
    "stage3_persistence_row_count",
    "stage3_persistence_pass_row_count",
    "stage3_partial_pass_row_count",
    "stage3_reliable_center_count",
    "stage3_reliable_path_observation_count",
    "stage3_elevation_ready_center_count",
    "stage3_elevation_ready_path_count",
    "stage4_summary_row_count",
    "stage4_joint_valid_count",
    "stage4_confirmed_center_count",
    "stage4_rejected_center_count",
    "stage4_cap_missing_center_count",
    "stage4_confirmed_path_source_count",
    "stage4_confirmed_path_link_count",
]

CENTER_FIELDS = [
    "stage3_center_id",
    "run_id",
    "logical_run_key",
    "scene_id",
    "prn",
    "tracking_channel",
    "source_result_relpath",
    "center_window_id",
    "center_recording_time_s",
    "tow_s",
    "selected_L",
    "multipath_count_declared",
    "stage3_path_observation_count",
    "minimum_path_run",
    "reliable_multipath",
    "persistence_path_count_consistent",
    "persistence_min_matched_window_count",
    "persistence_max_matched_window_count",
    "persistence_min_longest_consecutive_count",
    "persistence_max_longest_consecutive_count",
    "reliable_center_rank_in_run",
    "other_reliable_centers_within_radius",
    "adjacent_reliable_center_within_radius",
    "observation_granularity",
    "environment_class",
    "elevation_deg",
    "elevation_band",
    "geometry_join_status",
    "geometry_join_valid",
    "geometry_source_utc",
    "geometry_time_delta_s",
    "run_context_present",
    "academic_eligible",
    "elevation_ready",
    "academic_exclusion_reason",
    "stage4_available",
    "stage4_joint_valid",
    "stage4_confirmed",
    "stage4_rejected",
    "stage4_outcome",
    "stage4_missing_reason",
    "stage4_event_id",
    "stage4_joint_multipath_count",
    "stage4_confirmed_path_source_count",
]

PATH_FIELDS = [
    "stage3_path_id",
    "stage3_center_id",
    "run_id",
    "logical_run_key",
    "scene_id",
    "prn",
    "tracking_channel",
    "source_result_relpath",
    "center_window_id",
    "center_recording_time_s",
    "tow_s",
    "selected_L",
    "multipath_id",
    "excess_delay_samples",
    "doppler_offset_hz",
    "relative_power_db",
    "matched_window_count",
    "longest_consecutive_count",
    "persistence_pass",
    "match_pattern",
    "persistence_radius_windows",
    "persistence_min_consecutive",
    "persistence_delay_tolerance_samples",
    "persistence_doppler_tolerance_hz",
    "persistence_power_tolerance_db",
    "environment_class",
    "elevation_deg",
    "elevation_band",
    "geometry_join_status",
    "geometry_join_valid",
    "geometry_source_utc",
    "geometry_time_delta_s",
    "run_context_present",
    "academic_eligible",
    "elevation_ready",
    "academic_exclusion_reason",
    "stage4_available",
    "stage4_joint_valid",
    "stage4_confirmed",
    "stage4_rejected",
    "stage4_outcome",
    "stage4_missing_reason",
    "stage4_path_present",
    "stage4_path_id",
    "stage4_path_match_method",
    "stage4_excess_delay_samples",
    "stage4_doppler_offset_hz",
    "stage4_relative_power_db",
    "stage4_path_missing_reason",
]

LINEAGE_FIELDS = [
    "lineage_id",
    "lineage_direction",
    "run_id",
    "logical_run_key",
    "scene_id",
    "prn",
    "tracking_channel",
    "center_window_id",
    "stage3_center_id",
    "stage3_path_id",
    "stage3_present",
    "stage3_multipath_id",
    "stage3_excess_delay_samples",
    "stage3_doppler_offset_hz",
    "stage3_relative_power_db",
    "stage3_persistence_pass",
    "stage4_present",
    "stage4_path_id",
    "stage4_excess_delay_samples",
    "stage4_doppler_offset_hz",
    "stage4_relative_power_db",
    "stage4_available",
    "stage4_joint_valid",
    "stage4_confirmed",
    "stage4_rejected",
    "stage4_outcome",
    "stage4_missing_reason",
    "path_match_method",
    "unmatched_reason",
    "environment_class",
    "elevation_deg",
    "elevation_band",
    "academic_eligible",
    "elevation_ready",
]

ATTRITION_FIELDS = [
    "scope",
    "environment_class",
    "elevation_band",
    "scene_count",
    "run_count",
    "prn_count",
    "stage3_reliable_center_count",
    "stage3_path_observation_count",
    "academic_eligible_center_count",
    "academic_eligible_path_count",
    "elevation_ready_center_count",
    "elevation_ready_path_count",
    "stage4_available_center_count",
    "stage4_joint_valid_center_count",
    "stage4_confirmed_center_count",
    "stage4_rejected_center_count",
    "stage4_cap_missing_center_count",
    "stage4_confirmed_path_source_count",
    "stage4_confirmed_path_link_count",
    "stage4_path_not_retained_count",
    "stage4_summary_missing_path_count",
    "stage4_available_center_rate",
    "stage4_confirmed_center_rate",
    "stage4_confirmed_path_link_rate",
]

MATRIX_FIELDS = [
    "environment_class",
    "elevation_band",
    "scene_count",
    "run_count",
    "prn_count",
    "reliable_center_count",
    "path_observation_count",
    "academic_eligible_center_count",
    "academic_eligible_path_count",
    "stage4_confirmed_center_count",
    "stage4_confirmed_path_link_count",
    "direct_support_status",
]

COMPARISON_FIELDS = [
    "granularity",
    "selection_group",
    "source_layer",
    "parameter",
    "unit",
    "group_n",
    "n",
    "mean",
    "median",
    "q25",
    "q75",
    "min",
    "max",
    "std",
    "selection_note",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: "" if row.get(field) is None else row.get(field, "")
                    for field in fields
                }
            )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_int(value: Any) -> int | None:
    number = parse_float(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def canonical_window_id(value: Any) -> str:
    number = parse_float(value)
    if number is None or not number.is_integer():
        return ""
    return str(int(number))


def format_number(value: float | int | None) -> str:
    if value is None:
        return ""
    number = float(value)
    if not math.isfinite(number):
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:.9f}".rstrip("0").rstrip(".")


def elevation_band(value: float | None) -> str:
    if value is None or not math.isfinite(value) or value < 0 or value > 90:
        return ""
    if value < 30:
        return "LOW"
    if value < 60:
        return "MID"
    return "HIGH"


def strict_stage4_confirmation(
    summary_row: dict[str, Any] | None,
    path_rows: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Apply the frozen Stage4 strict confirmation criterion."""

    if summary_row is None:
        return False, ["stage4_summary_missing"]
    issues: list[str] = []
    joint_valid = parse_int(summary_row.get("joint_valid"))
    joint_count = parse_int(summary_row.get("joint_multipath_count"))
    path_count = sum(1 for row in path_rows if is_true(row.get("is_multipath")))
    if joint_valid is None:
        issues.append("joint_valid_missing_or_non_integer")
    if joint_count is None:
        issues.append("joint_multipath_count_missing_or_non_integer")
    if joint_count is not None and joint_count != path_count:
        issues.append("joint_multipath_count_mismatch")
    confirmed = (
        joint_valid == 1
        and joint_count is not None
        and joint_count > 0
        and path_count > 0
        and not issues
    )
    return confirmed, issues


def classify_stage4_outcome(
    stage4_summary: dict[str, Any] | None,
    reliable_rank: int,
    confirmed: bool,
) -> str:
    if stage4_summary is None:
        if reliable_rank > STAGE4_MAXIMUM_JOINT_CENTERS:
            return "stage4_missing_due_to_maximum_joint_centers_cap"
        return "stage4_missing_after_candidate_gate"
    return "stage4_confirmed" if confirmed else "stage4_available_rejected"


def quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def numeric_summary(values: Iterable[Any]) -> dict[str, Any]:
    numbers = [number for value in values if (number := parse_float(value)) is not None]
    if not numbers:
        return {
            "n": 0,
            "mean": "",
            "median": "",
            "q25": "",
            "q75": "",
            "min": "",
            "max": "",
            "std": "",
        }
    average = mean(numbers)
    std = math.sqrt(mean([(value - average) ** 2 for value in numbers]))
    return {
        "n": len(numbers),
        "mean": format_number(average),
        "median": format_number(quantile(numbers, 0.5)),
        "q25": format_number(quantile(numbers, 0.25)),
        "q75": format_number(quantile(numbers, 0.75)),
        "min": format_number(min(numbers)),
        "max": format_number(max(numbers)),
        "std": format_number(std),
    }


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc)


def gps_tow_to_utc(gps_week: int, tow_s: float) -> datetime:
    return GPS_EPOCH + timedelta(
        seconds=gps_week * GPS_WEEK_SECONDS + tow_s - GPS_UTC_LEAP_SECONDS
    )


def load_geometry(root: Path, scene_ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
    geometry: dict[str, list[dict[str, Any]]] = {}
    for scene_id in sorted(set(scene_ids)):
        path = root / "scenes" / scene_id / "satellite" / (
            f"{scene_id}_satellite_elevation_timeseries.csv"
        )
        values: list[dict[str, Any]] = []
        if path.is_file():
            for row in read_csv_rows(path):
                timestamp = parse_utc(row.get("utc_time"))
                if timestamp is None:
                    continue
                item = dict(row)
                item["_utc_datetime"] = timestamp
                values.append(item)
        geometry[scene_id] = values
    return geometry


def geometry_for_center(
    *,
    run: dict[str, str],
    scene_id: str,
    prn: str,
    tow_s: float | None,
    time_alignment: dict[str, dict[str, str]],
    geometry: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if is_true(run.get("context_missing_legacy")):
        return {
            "elevation_deg": "",
            "elevation_band": "",
            "geometry_join_status": "unavailable",
            "geometry_join_valid": "0",
            "geometry_source_utc": "",
            "geometry_time_delta_s": "",
            "geometry_missing_reason": "legacy_context_missing_excluded_from_modeling",
        }
    if tow_s is None:
        return {
            "elevation_deg": "",
            "elevation_band": "",
            "geometry_join_status": "unavailable",
            "geometry_join_valid": "0",
            "geometry_source_utc": "",
            "geometry_time_delta_s": "",
            "geometry_missing_reason": "stage0_center_window_missing_or_invalid_tow",
        }
    alignment = time_alignment.get(scene_id)
    if alignment is None or parse_int(alignment.get("gps_week")) is None:
        return {
            "elevation_deg": "",
            "elevation_band": "",
            "geometry_join_status": "unavailable",
            "geometry_join_valid": "0",
            "geometry_source_utc": "",
            "geometry_time_delta_s": "",
            "geometry_missing_reason": "verified_time_alignment_unavailable",
        }
    target = gps_tow_to_utc(parse_int(alignment["gps_week"]) or 0, tow_s)
    candidates = [
        row
        for row in geometry.get(scene_id, [])
        if str(row.get("prn", "")).strip().upper() == prn.upper()
    ]
    if not candidates:
        return {
            "elevation_deg": "",
            "elevation_band": "",
            "geometry_join_status": "unavailable",
            "geometry_join_valid": "0",
            "geometry_source_utc": "",
            "geometry_time_delta_s": "",
            "geometry_missing_reason": "geometry_prn_missing_in_timeseries",
        }
    nearest = min(
        candidates,
        key=lambda row: abs((row["_utc_datetime"] - target).total_seconds()),
    )
    delta = abs((nearest["_utc_datetime"] - target).total_seconds())
    if delta > MAX_GEOMETRY_DELTA_SECONDS:
        return {
            "elevation_deg": "",
            "elevation_band": "",
            "geometry_join_status": "inconclusive",
            "geometry_join_valid": "0",
            "geometry_source_utc": nearest["_utc_datetime"].isoformat().replace(
                "+00:00", "Z"
            ),
            "geometry_time_delta_s": format_number(delta),
            "geometry_missing_reason": "nearest_geometry_delta_exceeds_5s",
        }
    elevation = parse_float(nearest.get("elevation_deg"))
    return {
        "elevation_deg": format_number(elevation),
        "elevation_band": elevation_band(elevation),
        "geometry_join_status": "valid",
        "geometry_join_valid": "1",
        "geometry_source_utc": nearest["_utc_datetime"].isoformat().replace(
            "+00:00", "Z"
        ),
        "geometry_time_delta_s": format_number(delta),
        "geometry_missing_reason": "" if elevation is not None else "elevation_missing",
    }


def source_paths(root: Path) -> dict[str, Path]:
    return {
        "ingestion_manifest": root / INGESTION_MANIFEST_REL,
        "sage_runs": root / INGESTION_REL / "facts/sage_runs.csv",
        "events": root / INGESTION_REL / "facts/events.csv",
        "event_paths": root / INGESTION_REL / "facts/event_paths.csv",
        "event_context_aligned": root / ALIGNMENT_REL / "facts/event_context_aligned.csv",
        "time_alignment": root / ALIGNMENT_REL / "dimensions/time_alignment.csv",
        "scene_metadata": root / SCENE_METADATA_REL,
        "production_manifest": root / PRODUCTION_MANIFEST_REL,
        "production_inventory": root / PRODUCTION_INVENTORY_REL,
        "pipeline": root / PIPELINE_REL,
        "wrapper": root / WRAPPER_REL,
        "executor": root / EXECUTOR_REL,
    }


def frozen_hash_status(
    root: Path, manifest: dict[str, Any], paths: dict[str, Path]
) -> dict[str, Any]:
    expected = dict(manifest.get("frozen_source_hashes", {}))
    path_by_hash_key = {
        "pipeline_sha256": paths["pipeline"],
        "wrapper_sha256": paths["wrapper"],
        "executor_sha256": paths["executor"],
        "manifest_sha256": paths["production_manifest"],
        "inventory_sha256": paths["production_inventory"],
    }
    actual = {}
    matches = {}
    for key, path in path_by_hash_key.items():
        value = sha256_file(path) if path.is_file() else ""
        actual[key] = value
        matches[key] = bool(value) and value == expected.get(key, "")
    return {
        "expected": expected,
        "actual": actual,
        "matches": matches,
        "all_match": all(matches.values()),
    }


def collect_source_artifacts(
    root: Path, runs: list[dict[str, str]], paths: dict[str, Path]
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for label, path in paths.items():
        if path.is_file():
            artifacts[label] = sha256_file(path)
    for run in runs:
        directory = root / run["source_result_relpath"]
        relative_names = [
            "run_context.json",
            "run_context.mat",
            "stage0_valid_40ms_windows.csv",
            "stage3_persistence.csv",
            "stage3_reliable_centers.csv",
            "stage3_nav_persistence.mat",
            "stage4_joint_summary.csv",
            "stage4_joint_paths.csv",
            "stage4_nav_joint_100ms.mat",
        ]
        for name in relative_names:
            artifact = directory / name
            if artifact.is_file():
                key = f"{run['run_id']}::{name}"
                artifacts[key] = sha256_file(artifact)
    return artifacts


def stage4_path_lookup(path_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {
        canonical_window_id(row.get("path_id")): row
        for row in path_rows
        if canonical_window_id(row.get("path_id"))
    }


def stage4_multipath_count(path_rows: list[dict[str, str]]) -> int:
    return sum(1 for row in path_rows if is_true(row.get("is_multipath")))


def join_stage4_path(
    path_row: dict[str, str], stage4_paths: list[dict[str, str]]
) -> dict[str, Any] | None:
    multipath_id = parse_int(path_row.get("multipath_id"))
    if multipath_id is None:
        return None
    target_path_id = multipath_id + 1
    for candidate in stage4_paths:
        if parse_int(candidate.get("path_id")) == target_path_id and is_true(
            candidate.get("is_multipath")
        ):
            return candidate
    return None


def stage4_missing_reason(
    center: dict[str, Any], path_hit: dict[str, Any] | None
) -> str:
    if path_hit is not None:
        return ""
    if not is_true(center.get("stage4_available")):
        return str(center.get("stage4_missing_reason", ""))
    if center.get("stage4_outcome") == "stage4_available_rejected":
        return "stage4_available_but_strict_confirmation_rejected_center"
    return "stage4_joint_model_selected_fewer_multipaths_than_stage3"


def group_counts(
    centers: list[dict[str, Any]], paths: list[dict[str, Any]]
) -> dict[str, Any]:
    eligible_centers = [row for row in centers if is_true(row.get("academic_eligible"))]
    eligible_paths = [row for row in paths if is_true(row.get("academic_eligible"))]
    elevation_centers = [row for row in eligible_centers if is_true(row.get("elevation_ready"))]
    elevation_paths = [row for row in eligible_paths if is_true(row.get("elevation_ready"))]
    confirmed_centers = [
        row for row in eligible_centers if row.get("stage4_outcome") == "stage4_confirmed"
    ]
    rejected_centers = [
        row
        for row in eligible_centers
        if row.get("stage4_outcome") == "stage4_available_rejected"
    ]
    cap_centers = [
        row
        for row in eligible_centers
        if row.get("stage4_outcome") == "stage4_missing_due_to_maximum_joint_centers_cap"
    ]
    stage4_path_source_count = sum(
        parse_int(row.get("stage4_confirmed_path_source_count")) or 0
        for row in eligible_centers
    )
    linked = [row for row in eligible_paths if is_true(row.get("stage4_confirmed"))]
    not_retained = [row for row in eligible_paths if not is_true(row.get("stage4_path_present"))]
    summary_missing = [
        row for row in eligible_paths if not is_true(row.get("stage4_available"))
    ]
    scene_values = {row.get("scene_id", "") for row in eligible_centers if row.get("scene_id")}
    run_values = {row.get("run_id", "") for row in eligible_centers if row.get("run_id")}
    prn_values = {row.get("prn", "") for row in eligible_centers if row.get("prn")}
    center_denominator = len(eligible_centers)
    path_denominator = len(eligible_paths)
    return {
        "scene_count": len(scene_values),
        "run_count": len(run_values),
        "prn_count": len(prn_values),
        "stage3_reliable_center_count": len(centers),
        "stage3_path_observation_count": len(paths),
        "academic_eligible_center_count": len(eligible_centers),
        "academic_eligible_path_count": len(eligible_paths),
        "elevation_ready_center_count": len(elevation_centers),
        "elevation_ready_path_count": len(elevation_paths),
        "stage4_available_center_count": sum(
            1 for row in eligible_centers if is_true(row.get("stage4_available"))
        ),
        "stage4_joint_valid_center_count": sum(
            1 for row in eligible_centers if is_true(row.get("stage4_joint_valid"))
        ),
        "stage4_confirmed_center_count": len(confirmed_centers),
        "stage4_rejected_center_count": len(rejected_centers),
        "stage4_cap_missing_center_count": len(cap_centers),
        "stage4_confirmed_path_source_count": stage4_path_source_count,
        "stage4_confirmed_path_link_count": len(linked),
        "stage4_path_not_retained_count": len(not_retained),
        "stage4_summary_missing_path_count": len(summary_missing),
        "stage4_available_center_rate": format_number(
            len([row for row in eligible_centers if is_true(row.get("stage4_available"))])
            / center_denominator
            if center_denominator
            else None
        ),
        "stage4_confirmed_center_rate": format_number(
            len(confirmed_centers) / center_denominator if center_denominator else None
        ),
        "stage4_confirmed_path_link_rate": format_number(
            len(linked) / path_denominator if path_denominator else None
        ),
    }


def make_attrition_rows(
    centers: list[dict[str, Any]], paths: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    specs: list[tuple[str, str, str]] = [("overall", "ALL", "ALL")]
    specs.extend(("environment", environment, "ALL") for environment in ENVIRONMENTS)
    specs.extend(("elevation", "ALL", band) for band in [*BANDS, "UNKNOWN"])
    specs.extend(
        ("environment_elevation", environment, band)
        for environment in ENVIRONMENTS
        for band in BANDS
    )
    for scope, environment, band in specs:
        selected_centers = [
            row
            for row in centers
            if (environment == "ALL" or row.get("environment_class") == environment)
            and (
                band == "ALL"
                or (band == "UNKNOWN" and not row.get("elevation_band"))
                or row.get("elevation_band") == band
            )
        ]
        selected_paths = [
            row
            for row in paths
            if (environment == "ALL" or row.get("environment_class") == environment)
            and (
                band == "ALL"
                or (band == "UNKNOWN" and not row.get("elevation_band"))
                or row.get("elevation_band") == band
            )
        ]
        summary = group_counts(selected_centers, selected_paths)
        rows.append(
            {
                "scope": scope,
                "environment_class": environment,
                "elevation_band": band,
                **summary,
            }
        )
    return rows


def make_support_matrix(
    centers: list[dict[str, Any]], paths: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        for band in BANDS:
            selected_centers = [
                row
                for row in centers
                if row.get("environment_class") == environment
                and row.get("elevation_band") == band
            ]
            selected_paths = [
                row
                for row in paths
                if row.get("environment_class") == environment
                and row.get("elevation_band") == band
            ]
            summary = group_counts(selected_centers, selected_paths)
            output.append(
                {
                    "environment_class": environment,
                    "elevation_band": band,
                    "scene_count": summary["scene_count"],
                    "run_count": summary["run_count"],
                    "prn_count": summary["prn_count"],
                    "reliable_center_count": summary["stage3_reliable_center_count"],
                    "path_observation_count": summary["stage3_path_observation_count"],
                    "academic_eligible_center_count": summary[
                        "academic_eligible_center_count"
                    ],
                    "academic_eligible_path_count": summary["academic_eligible_path_count"],
                    "stage4_confirmed_center_count": summary[
                        "stage4_confirmed_center_count"
                    ],
                    "stage4_confirmed_path_link_count": summary[
                        "stage4_confirmed_path_link_count"
                    ],
                    "direct_support_status": (
                        "DIRECT_STAGE3_SUPPORT"
                        if summary["academic_eligible_path_count"] > 0
                        else "NO_STAGE3_SUPPORT"
                    ),
                }
            )
    return output


def make_comparison_rows(
    centers: list[dict[str, Any]], paths: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    notes = (
        "Descriptive only; center-window observations may share persistence footprints."
    )
    path_groups = {
        "all_stage3_academic_eligible": [
            row for row in paths if is_true(row.get("academic_eligible"))
        ],
        "stage4_confirmed_link": [
            row
            for row in paths
            if is_true(row.get("stage4_confirmed"))
            and is_true(row.get("academic_eligible"))
        ],
        "stage4_available_rejected": [
            row
            for row in paths
            if row.get("stage4_outcome") == "stage4_available_rejected"
        ],
        "stage4_cap_missing": [
            row
            for row in paths
            if row.get("stage4_outcome")
            == "stage4_missing_due_to_maximum_joint_centers_cap"
        ],
    }
    path_parameters = [
        ("excess_delay_samples", "samples", "excess_delay_samples"),
        ("doppler_offset_hz", "Hz", "doppler_offset_hz"),
        ("relative_power_db", "dB", "relative_power_db"),
        ("matched_window_count", "windows", "matched_window_count"),
        ("longest_consecutive_count", "windows", "longest_consecutive_count"),
        ("selected_L", "order", "selected_L"),
    ]
    for group, group_rows in path_groups.items():
        for parameter, unit, field in path_parameters:
            summary = numeric_summary(row.get(field) for row in group_rows)
            rows.append(
                {
                    "granularity": "path_observation",
                    "selection_group": group,
                    "source_layer": "stage3",
                    "parameter": parameter,
                    "unit": unit,
                    "group_n": len(group_rows),
                    **summary,
                    "selection_note": notes,
                }
            )
    linked_rows = [
        row
        for row in paths
        if is_true(row.get("stage4_confirmed"))
        and is_true(row.get("academic_eligible"))
    ]
    for parameter, unit, stage4_field in [
        ("excess_delay_samples", "samples", "stage4_excess_delay_samples"),
        ("doppler_offset_hz", "Hz", "stage4_doppler_offset_hz"),
        ("relative_power_db", "dB", "stage4_relative_power_db"),
    ]:
        summary = numeric_summary(row.get(stage4_field) for row in linked_rows)
        rows.append(
            {
                "granularity": "path_observation",
                "selection_group": "stage4_confirmed_link",
                "source_layer": "stage4",
                "parameter": parameter,
                "unit": unit,
                "group_n": len(linked_rows),
                **summary,
                "selection_note": "Stage4 path values linked by center window and positional path id.",
            }
        )

    center_groups = {
        "all_stage3_academic_eligible": [
            row for row in centers if is_true(row.get("academic_eligible"))
        ],
        "stage4_confirmed": [
            row
            for row in centers
            if row.get("stage4_outcome") == "stage4_confirmed"
            and is_true(row.get("academic_eligible"))
        ],
        "stage4_available_rejected": [
            row
            for row in centers
            if row.get("stage4_outcome") == "stage4_available_rejected"
            and is_true(row.get("academic_eligible"))
        ],
        "stage4_cap_missing": [
            row
            for row in centers
            if row.get("stage4_outcome")
            == "stage4_missing_due_to_maximum_joint_centers_cap"
            and is_true(row.get("academic_eligible"))
        ],
    }
    center_parameters = [
        ("selected_L", "order", "selected_L"),
        ("multipath_count", "paths", "multipath_count_declared"),
        ("minimum_path_run", "windows", "minimum_path_run"),
        ("stage3_path_observation_count", "paths", "stage3_path_observation_count"),
        ("elevation_deg", "deg", "elevation_deg"),
        ("reliable_center_rank_in_run", "rank", "reliable_center_rank_in_run"),
    ]
    for group, group_rows in center_groups.items():
        for parameter, unit, field in center_parameters:
            summary = numeric_summary(row.get(field) for row in group_rows)
            rows.append(
                {
                    "granularity": "reliable_center",
                    "selection_group": group,
                    "source_layer": "stage3",
                    "parameter": parameter,
                    "unit": unit,
                    "group_n": len(group_rows),
                    **summary,
                    "selection_note": notes,
                }
            )
    return rows


def build_lineage_rows(
    path_rows: list[dict[str, Any]],
    centers_by_id: dict[str, dict[str, Any]],
    stage4_multipath_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lineage: list[dict[str, Any]] = []
    linked_stage4_keys: set[tuple[str, str]] = set()
    for row in path_rows:
        center = centers_by_id[row["stage3_center_id"]]
        stage4_path_id = row.get("stage4_path_id", "")
        if stage4_path_id:
            linked_stage4_keys.add((row["run_id"], row["center_window_id"], stage4_path_id))
        lineage.append(
            {
                "lineage_id": row["stage3_path_id"],
                "lineage_direction": "stage3_to_stage4",
                "run_id": row["run_id"],
                "logical_run_key": row["logical_run_key"],
                "scene_id": row["scene_id"],
                "prn": row["prn"],
                "tracking_channel": row["tracking_channel"],
                "center_window_id": row["center_window_id"],
                "stage3_center_id": row["stage3_center_id"],
                "stage3_path_id": row["stage3_path_id"],
                "stage3_present": "1",
                "stage3_multipath_id": row["multipath_id"],
                "stage3_excess_delay_samples": row["excess_delay_samples"],
                "stage3_doppler_offset_hz": row["doppler_offset_hz"],
                "stage3_relative_power_db": row["relative_power_db"],
                "stage3_persistence_pass": row["persistence_pass"],
                "stage4_present": row["stage4_path_present"],
                "stage4_path_id": row["stage4_path_id"],
                "stage4_excess_delay_samples": row["stage4_excess_delay_samples"],
                "stage4_doppler_offset_hz": row["stage4_doppler_offset_hz"],
                "stage4_relative_power_db": row["stage4_relative_power_db"],
                "stage4_available": row["stage4_available"],
                "stage4_joint_valid": row["stage4_joint_valid"],
                "stage4_confirmed": row["stage4_confirmed"],
                "stage4_rejected": row["stage4_rejected"],
                "stage4_outcome": row["stage4_outcome"],
                "stage4_missing_reason": row["stage4_missing_reason"],
                "path_match_method": row["stage4_path_match_method"],
                "unmatched_reason": row["stage4_path_missing_reason"],
                "environment_class": row["environment_class"],
                "elevation_deg": row["elevation_deg"],
                "elevation_band": row["elevation_band"],
                "academic_eligible": row["academic_eligible"],
                "elevation_ready": row["elevation_ready"],
            }
        )
    for row in stage4_multipath_rows:
        key = (
            row["run_id"],
            row["center_window_id"],
            str(parse_int(row["path_id"])),
        )
        if key in linked_stage4_keys:
            continue
        center = centers_by_id.get(row["stage3_center_id"], {})
        lineage.append(
            {
                "lineage_id": (
                    f"{row['run_id']}__center_{row['center_window_id']}"
                    f"__stage4_path_{row['path_id']}"
                ),
                "lineage_direction": "stage4_to_stage3",
                "run_id": row["run_id"],
                "logical_run_key": row.get("logical_run_key", ""),
                "scene_id": row.get("scene_id", ""),
                "prn": row.get("prn", ""),
                "tracking_channel": row.get("tracking_channel", ""),
                "center_window_id": row["center_window_id"],
                "stage3_center_id": row.get("stage3_center_id", ""),
                "stage3_path_id": "",
                "stage3_present": "0",
                "stage3_multipath_id": "",
                "stage3_excess_delay_samples": "",
                "stage3_doppler_offset_hz": "",
                "stage3_relative_power_db": "",
                "stage3_persistence_pass": "",
                "stage4_present": "1",
                "stage4_path_id": row["path_id"],
                "stage4_excess_delay_samples": row.get("excess_delay_samples", ""),
                "stage4_doppler_offset_hz": row.get("doppler_offset_hz", ""),
                "stage4_relative_power_db": row.get("mean_relative_power_db", ""),
                "stage4_available": center.get("stage4_available", "1"),
                "stage4_joint_valid": center.get("stage4_joint_valid", ""),
                "stage4_confirmed": center.get("stage4_confirmed", "0"),
                "stage4_rejected": center.get("stage4_rejected", "0"),
                "stage4_outcome": center.get("stage4_outcome", ""),
                "stage4_missing_reason": center.get("stage4_missing_reason", ""),
                "path_match_method": "",
                "unmatched_reason": (
                    "stage4_multipath_path_not_found_in_stage3_reliable_population"
                ),
                "environment_class": center.get("environment_class", ""),
                "elevation_deg": center.get("elevation_deg", ""),
                "elevation_band": center.get("elevation_band", ""),
                "academic_eligible": center.get("academic_eligible", "0"),
                "elevation_ready": center.get("elevation_ready", "0"),
            }
        )
    return lineage


def build_audit(root: Path, output_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"new-only audit namespace already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    paths = source_paths(root)
    required = list(paths.values())
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    ingestion_manifest = json.loads(paths["ingestion_manifest"].read_text(encoding="utf-8"))
    runs = read_csv_rows(paths["sage_runs"])
    scene_metadata = {row["scene_id"]: row for row in read_csv_rows(paths["scene_metadata"])}
    time_alignment = {
        row["scene_id"]: row for row in read_csv_rows(paths["time_alignment"])
    }
    events = read_csv_rows(paths["events"])
    event_paths = read_csv_rows(paths["event_paths"])
    event_by_center: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in events:
        event_by_center[(row["run_id"], canonical_window_id(row["center_window_id"]))].append(
            row
        )
    event_path_by_center: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in event_paths:
        event_path_by_center[
            (row["run_id"], canonical_window_id(row["center_window_id"]))
        ].append(row)
    geometry = load_geometry(root, [row["scene_id"] for row in runs])
    source_artifacts_before = collect_source_artifacts(root, runs, paths)
    frozen_status = frozen_hash_status(root, ingestion_manifest, paths)

    centers: list[dict[str, Any]] = []
    path_population: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    stage4_source_multipath_rows: list[dict[str, Any]] = []

    for run in runs:
        source_dir = root / run["source_result_relpath"]
        stage0_path = source_dir / "stage0_valid_40ms_windows.csv"
        stage3_path = source_dir / "stage3_persistence.csv"
        stage3_center_path = source_dir / "stage3_reliable_centers.csv"
        stage4_summary_path = source_dir / "stage4_joint_summary.csv"
        stage4_path_path = source_dir / "stage4_joint_paths.csv"
        source_files_complete = all(
            path.is_file()
            for path in [
                stage0_path,
                stage3_path,
                stage3_center_path,
                stage4_summary_path,
                stage4_path_path,
            ]
        )
        if not source_files_complete:
            raise FileNotFoundError(f"incomplete SAGE source namespace: {source_dir}")
        stage0 = {
            canonical_window_id(row.get("window_id")): row
            for row in read_csv_rows(stage0_path)
        }
        stage3_persistence = read_csv_rows(stage3_path)
        stage3_reliable = read_csv_rows(stage3_center_path)
        stage4_summary = read_csv_rows(stage4_summary_path)
        stage4_paths = read_csv_rows(stage4_path_path)
        stage4_by_center = {
            canonical_window_id(row.get("center_window_id")): row
            for row in stage4_summary
        }
        reliable_ids = {
            canonical_window_id(row.get("center_window_id")) for row in stage3_reliable
        }
        pass_rows = [
            row for row in stage3_persistence if is_true(row.get("persistence_pass"))
        ]
        pass_by_center: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in pass_rows:
            pass_by_center[canonical_window_id(row.get("center_window_id"))].append(row)
        partial_pass_count = sum(
            1 for row in pass_rows if canonical_window_id(row.get("center_window_id")) not in reliable_ids
        )
        reliable_rank_by_id = {
            canonical_window_id(row.get("center_window_id")): index
            for index, row in enumerate(stage3_reliable, start=1)
        }
        reliable_ids_list = list(reliable_rank_by_id)
        for rank, reliable_row in enumerate(stage3_reliable, start=1):
            center_window_id = canonical_window_id(reliable_row.get("center_window_id"))
            center_id = f"{run['run_id']}__center_{center_window_id}"
            center_paths = pass_by_center.get(center_window_id, [])
            stage0_row = stage0.get(center_window_id, {})
            tow_s = parse_float(stage0_row.get("tow_s"))
            geometry_values = geometry_for_center(
                run=run,
                scene_id=run["scene_id"],
                prn=run["prn"],
                tow_s=tow_s,
                time_alignment=time_alignment,
                geometry=geometry,
            )
            event_candidates = event_by_center.get((run["run_id"], center_window_id), [])
            event_row = event_candidates[0] if len(event_candidates) == 1 else {}
            local_stage4_row = stage4_by_center.get(center_window_id)
            local_stage4_paths = [
                row
                for row in stage4_paths
                if canonical_window_id(row.get("center_window_id")) == center_window_id
            ]
            stage4_confirmed, stage4_issues = strict_stage4_confirmation(
                local_stage4_row, local_stage4_paths
            )
            stage4_available = local_stage4_row is not None
            stage4_joint_valid = (
                "1" if local_stage4_row is not None and is_true(local_stage4_row.get("joint_valid")) else "0"
            )
            stage4_outcome = classify_stage4_outcome(
                local_stage4_row, rank, stage4_confirmed
            )
            stage4_missing = ""
            if not stage4_available:
                stage4_missing = (
                    "not_selected_by_stage4_maximumJointCenters"
                    if rank > STAGE4_MAXIMUM_JOINT_CENTERS
                    else "stage4_summary_missing_after_candidate_gate"
                )
            event_confirmed = event_row.get("event_status") == "confirmed_multipath"
            if event_row and event_confirmed != stage4_confirmed:
                raise ValueError(
                    "Stage4 source/event-db confirmation disagreement for "
                    f"{run['run_id']} center {center_window_id}: "
                    f"source={stage4_confirmed}, db={event_confirmed}"
                )
            nearby = [
                other_id
                for other_id in reliable_ids_list
                if other_id != center_window_id
                and abs((parse_int(other_id) or 0) - (parse_int(center_window_id) or 0))
                <= PERSISTENCE_RADIUS_WINDOWS
            ]
            min_matched = min(
                (parse_int(row.get("matched_window_count")) or 0 for row in center_paths),
                default=None,
            )
            max_matched = max(
                (parse_int(row.get("matched_window_count")) or 0 for row in center_paths),
                default=None,
            )
            min_run = min(
                (parse_int(row.get("longest_consecutive_count")) or 0 for row in center_paths),
                default=None,
            )
            max_run = max(
                (parse_int(row.get("longest_consecutive_count")) or 0 for row in center_paths),
                default=None,
            )
            legacy_missing = is_true(run.get("context_missing_legacy"))
            academic_eligible = not legacy_missing and bool(
                scene_metadata.get(run["scene_id"], {}).get("environment_class")
            )
            elevation_ready = academic_eligible and bool(geometry_values["elevation_band"])
            exclusion_reason = ""
            if legacy_missing:
                exclusion_reason = "legacy_run_context_missing"
            elif not academic_eligible:
                exclusion_reason = "scene_environment_metadata_missing"
            elif not elevation_ready:
                exclusion_reason = geometry_values["geometry_missing_reason"] or "elevation_unavailable"
            center_record: dict[str, Any] = {
                "stage3_center_id": center_id,
                "run_id": run["run_id"],
                "logical_run_key": run["logical_run_key"],
                "scene_id": run["scene_id"],
                "prn": run["prn"],
                "tracking_channel": run["tracking_channel"],
                "source_result_relpath": run["source_result_relpath"],
                "center_window_id": center_window_id,
                "center_recording_time_s": reliable_row.get("recording_time_s", ""),
                "tow_s": format_number(tow_s),
                "selected_L": reliable_row.get("selected_L", ""),
                "multipath_count_declared": reliable_row.get("multipath_count", ""),
                "stage3_path_observation_count": len(center_paths),
                "minimum_path_run": reliable_row.get("minimum_path_run", ""),
                "reliable_multipath": reliable_row.get("reliable_multipath", ""),
                "persistence_path_count_consistent": int(
                    (parse_int(reliable_row.get("multipath_count")) or -1) == len(center_paths)
                ),
                "persistence_min_matched_window_count": min_matched,
                "persistence_max_matched_window_count": max_matched,
                "persistence_min_longest_consecutive_count": min_run,
                "persistence_max_longest_consecutive_count": max_run,
                "reliable_center_rank_in_run": rank,
                "other_reliable_centers_within_radius": len(nearby),
                "adjacent_reliable_center_within_radius": int(bool(nearby)),
                "observation_granularity": "reliable_center_window",
                "environment_class": scene_metadata.get(run["scene_id"], {}).get(
                    "environment_class", ""
                ),
                "elevation_deg": geometry_values["elevation_deg"],
                "elevation_band": geometry_values["elevation_band"],
                "geometry_join_status": geometry_values["geometry_join_status"],
                "geometry_join_valid": geometry_values["geometry_join_valid"],
                "geometry_source_utc": geometry_values["geometry_source_utc"],
                "geometry_time_delta_s": geometry_values["geometry_time_delta_s"],
                "run_context_present": int((source_dir / "run_context.json").is_file()),
                "academic_eligible": int(academic_eligible),
                "elevation_ready": int(elevation_ready),
                "academic_exclusion_reason": exclusion_reason,
                "stage4_available": int(stage4_available),
                "stage4_joint_valid": stage4_joint_valid,
                "stage4_confirmed": int(stage4_confirmed),
                "stage4_rejected": int(stage4_available and not stage4_confirmed),
                "stage4_outcome": stage4_outcome,
                "stage4_missing_reason": stage4_missing,
                "stage4_event_id": event_row.get("event_id", ""),
                "stage4_joint_multipath_count": (
                    local_stage4_row.get("joint_multipath_count", "")
                    if local_stage4_row
                    else ""
                ),
                "stage4_confirmed_path_source_count": (
                    stage4_multipath_count(local_stage4_paths) if stage4_confirmed else 0
                ),
            }
            centers.append(center_record)
            for persistence_row in center_paths:
                stage4_hit = join_stage4_path(persistence_row, local_stage4_paths)
                path_id = f"{center_id}__mp_{persistence_row.get('multipath_id', '')}"
                path_record: dict[str, Any] = {
                    "stage3_path_id": path_id,
                    "stage3_center_id": center_id,
                    "run_id": run["run_id"],
                    "logical_run_key": run["logical_run_key"],
                    "scene_id": run["scene_id"],
                    "prn": run["prn"],
                    "tracking_channel": run["tracking_channel"],
                    "source_result_relpath": run["source_result_relpath"],
                    "center_window_id": center_window_id,
                    "center_recording_time_s": persistence_row.get(
                        "center_recording_time_s", ""
                    ),
                    "tow_s": format_number(tow_s),
                    "selected_L": persistence_row.get("selected_L", ""),
                    "multipath_id": persistence_row.get("multipath_id", ""),
                    "excess_delay_samples": persistence_row.get(
                        "excess_delay_samples", ""
                    ),
                    "doppler_offset_hz": persistence_row.get("doppler_offset_hz", ""),
                    "relative_power_db": persistence_row.get("relative_power_db", ""),
                    "matched_window_count": persistence_row.get("matched_window_count", ""),
                    "longest_consecutive_count": persistence_row.get(
                        "longest_consecutive_count", ""
                    ),
                    "persistence_pass": int(is_true(persistence_row.get("persistence_pass"))),
                    "match_pattern": persistence_row.get("match_pattern", ""),
                    "persistence_radius_windows": PERSISTENCE_RADIUS_WINDOWS,
                    "persistence_min_consecutive": PERSISTENCE_MIN_CONSECUTIVE,
                    "persistence_delay_tolerance_samples": PERSISTENCE_DELAY_TOLERANCE_SAMPLES,
                    "persistence_doppler_tolerance_hz": PERSISTENCE_DOPPLER_TOLERANCE_HZ,
                    "persistence_power_tolerance_db": PERSISTENCE_POWER_TOLERANCE_DB,
                    "environment_class": center_record["environment_class"],
                    "elevation_deg": center_record["elevation_deg"],
                    "elevation_band": center_record["elevation_band"],
                    "geometry_join_status": center_record["geometry_join_status"],
                    "geometry_join_valid": center_record["geometry_join_valid"],
                    "geometry_source_utc": center_record["geometry_source_utc"],
                    "geometry_time_delta_s": center_record["geometry_time_delta_s"],
                    "run_context_present": center_record["run_context_present"],
                    "academic_eligible": center_record["academic_eligible"],
                    "elevation_ready": center_record["elevation_ready"],
                    "academic_exclusion_reason": center_record["academic_exclusion_reason"],
                    "stage4_available": center_record["stage4_available"],
                    "stage4_joint_valid": center_record["stage4_joint_valid"],
                    "stage4_confirmed": int(stage4_confirmed and stage4_hit is not None),
                    "stage4_rejected": center_record["stage4_rejected"],
                    "stage4_outcome": center_record["stage4_outcome"],
                    "stage4_missing_reason": center_record["stage4_missing_reason"],
                    "stage4_path_present": int(stage4_hit is not None),
                    "stage4_path_id": (
                        stage4_hit.get("path_id", "") if stage4_hit is not None else ""
                    ),
                    "stage4_path_match_method": (
                        "same_run_center_window_id_and_multipath_id_plus_one"
                        if stage4_hit is not None
                        else ""
                    ),
                    "stage4_excess_delay_samples": (
                        stage4_hit.get("excess_delay_samples", "")
                        if stage4_hit is not None
                        else ""
                    ),
                    "stage4_doppler_offset_hz": (
                        stage4_hit.get("doppler_offset_hz", "") if stage4_hit is not None else ""
                    ),
                    "stage4_relative_power_db": (
                        stage4_hit.get("mean_relative_power_db", "")
                        if stage4_hit is not None
                        else ""
                    ),
                    "stage4_path_missing_reason": stage4_missing_reason(
                        center_record, stage4_hit
                    ),
                }
                path_population.append(path_record)

            for local_path in local_stage4_paths:
                if not is_true(local_path.get("is_multipath")):
                    continue
                stage4_source_multipath_rows.append(
                    {
                        **local_path,
                        "run_id": run["run_id"],
                        "logical_run_key": run["logical_run_key"],
                        "scene_id": run["scene_id"],
                        "prn": run["prn"],
                        "tracking_channel": run["tracking_channel"],
                        "center_window_id": center_window_id,
                        "stage3_center_id": center_id,
                    }
                )
        run_centers = [row for row in centers if row["run_id"] == run["run_id"]]
        run_paths = [row for row in path_population if row["run_id"] == run["run_id"]]
        run_eligible = not is_true(run.get("context_missing_legacy"))
        run_rows.append(
            {
                "run_id": run["run_id"],
                "logical_run_key": run["logical_run_key"],
                "scene_id": run["scene_id"],
                "prn": run["prn"],
                "tracking_channel": run["tracking_channel"],
                "source_result_relpath": run["source_result_relpath"],
                "qa_status": run["qa_status"],
                "run_status": run["run_status"],
                "stage3_status": run["stage3_status"],
                "stage3_files_complete": int(source_files_complete),
                "run_context_present": int((source_dir / "run_context.json").is_file()),
                "context_missing_legacy": run.get("context_missing_legacy", ""),
                "environment_class": scene_metadata.get(run["scene_id"], {}).get(
                    "environment_class", ""
                ),
                "academic_run_eligible": int(run_eligible),
                "academic_exclusion_reason": (
                    "legacy_run_context_missing" if not run_eligible else ""
                ),
                "stage3_persistence_row_count": len(stage3_persistence),
                "stage3_persistence_pass_row_count": len(pass_rows),
                "stage3_partial_pass_row_count": partial_pass_count,
                "stage3_reliable_center_count": len(run_centers),
                "stage3_reliable_path_observation_count": len(run_paths),
                "stage3_elevation_ready_center_count": sum(
                    is_true(row.get("elevation_ready")) for row in run_centers
                ),
                "stage3_elevation_ready_path_count": sum(
                    is_true(row.get("elevation_ready")) for row in run_paths
                ),
                "stage4_summary_row_count": len(stage4_summary),
                "stage4_joint_valid_count": sum(
                    is_true(row.get("joint_valid")) for row in stage4_summary
                ),
                "stage4_confirmed_center_count": sum(
                    row.get("stage4_outcome") == "stage4_confirmed" for row in run_centers
                ),
                "stage4_rejected_center_count": sum(
                    row.get("stage4_outcome") == "stage4_available_rejected"
                    for row in run_centers
                ),
                "stage4_cap_missing_center_count": sum(
                    row.get("stage4_outcome")
                    == "stage4_missing_due_to_maximum_joint_centers_cap"
                    for row in run_centers
                ),
                "stage4_confirmed_path_source_count": sum(
                    parse_int(row.get("stage4_confirmed_path_source_count")) or 0
                    for row in run_centers
                ),
                "stage4_confirmed_path_link_count": sum(
                    is_true(row.get("stage4_confirmed")) for row in run_paths
                ),
            }
        )

    centers_by_id = {row["stage3_center_id"]: row for row in centers}
    lineage_rows = build_lineage_rows(
        path_population, centers_by_id, stage4_source_multipath_rows
    )
    attrition_rows = make_attrition_rows(centers, path_population)
    support_rows = make_support_matrix(centers, path_population)
    comparison_rows = make_comparison_rows(centers, path_population)

    write_csv_rows(output_dir / "stage3_run_summary.csv", RUN_FIELDS, run_rows)
    write_csv_rows(output_dir / "stage3_center_summary.csv", CENTER_FIELDS, centers)
    write_csv_rows(output_dir / "stage3_path_population.csv", PATH_FIELDS, path_population)
    write_csv_rows(output_dir / "stage3_stage4_lineage.csv", LINEAGE_FIELDS, lineage_rows)
    write_csv_rows(
        output_dir / "stage3_stage4_attrition_by_environment.csv",
        ATTRITION_FIELDS,
        attrition_rows,
    )
    write_csv_rows(
        output_dir / "environment_elevation_stage3_support_matrix.csv",
        MATRIX_FIELDS,
        support_rows,
    )
    write_csv_rows(
        output_dir / "stage3_stage4_parameter_comparison.csv",
        COMPARISON_FIELDS,
        comparison_rows,
    )

    return {
        "root": root,
        "output_dir": output_dir,
        "paths": paths,
        "ingestion_manifest": ingestion_manifest,
        "runs": runs,
        "centers": centers,
        "path_population": path_population,
        "run_rows": run_rows,
        "lineage_rows": lineage_rows,
        "attrition_rows": attrition_rows,
        "support_rows": support_rows,
        "comparison_rows": comparison_rows,
        "events": events,
        "event_paths": event_paths,
        "event_by_center": event_by_center,
        "event_path_by_center": event_path_by_center,
        "source_artifacts_before": source_artifacts_before,
        "frozen_status": frozen_status,
        "stage4_source_multipath_rows": stage4_source_multipath_rows,
        "gate_record": {
            "raw_iq_read": False,
            "matlab_started": False,
            "sage_started": False,
            "stage3_model_fitting_started": False,
            "statistical_modeling_started": False,
            "existing_stage4_modified": False,
            "existing_sage_namespace_modified": False,
        },
    }


def independent_qa(data: dict[str, Any]) -> dict[str, Any]:
    root: Path = data["root"]
    output_dir: Path = data["output_dir"]
    source_path_map: dict[str, Path] = data["paths"]
    checks: list[dict[str, Any]] = []

    required_outputs = [
        "stage3_run_summary.csv",
        "stage3_center_summary.csv",
        "stage3_path_population.csv",
        "stage3_stage4_lineage.csv",
        "stage3_stage4_attrition_by_environment.csv",
        "environment_elevation_stage3_support_matrix.csv",
        "stage3_stage4_parameter_comparison.csv",
    ]
    output_tables: dict[str, list[dict[str, str]]] = {}
    for name in required_outputs:
        path = output_dir / name
        exists_nonempty = path.is_file() and path.stat().st_size > 0
        checks.append(
            {
                "check": f"output_exists_nonempty:{name}",
                "status": "PASS" if exists_nonempty else "FAIL",
                "detail": str(path),
            }
        )
        if exists_nonempty:
            output_tables[name] = read_csv_rows(path)

    run_rows = output_tables.get("stage3_run_summary.csv", [])
    centers = output_tables.get("stage3_center_summary.csv", [])
    path_population = output_tables.get("stage3_path_population.csv", [])
    lineage = output_tables.get("stage3_stage4_lineage.csv", [])
    matrix = output_tables.get("environment_elevation_stage3_support_matrix.csv", [])

    unique_center_ids = len({row.get("stage3_center_id") for row in centers}) == len(centers)
    unique_path_ids = len({row.get("stage3_path_id") for row in path_population}) == len(
        path_population
    )
    checks.append(
        {
            "check": "unique_stage3_center_ids",
            "status": "PASS" if unique_center_ids else "FAIL",
            "detail": str(len(centers)),
        }
    )
    checks.append(
        {
            "check": "unique_stage3_path_ids",
            "status": "PASS" if unique_path_ids else "FAIL",
            "detail": str(len(path_population)),
        }
    )

    center_ids = {row.get("stage3_center_id") for row in centers}
    path_center_refs_valid = all(row.get("stage3_center_id") in center_ids for row in path_population)
    pass_flags_valid = all(is_true(row.get("persistence_pass")) for row in path_population)
    declared_counts_valid = all(
        parse_int(center.get("stage3_path_observation_count"))
        == sum(1 for row in path_population if row.get("stage3_center_id") == center.get("stage3_center_id"))
        for center in centers
    )
    checks.extend(
        [
            {
                "check": "path_center_references_valid",
                "status": "PASS" if path_center_refs_valid else "FAIL",
                "detail": "all stage3 paths refer to a reliable center",
            },
            {
                "check": "all_population_paths_persistence_pass",
                "status": "PASS" if pass_flags_valid else "FAIL",
                "detail": "population definition requires persistence_pass=true",
            },
            {
                "check": "center_declared_path_counts_reconcile",
                "status": "PASS" if declared_counts_valid else "FAIL",
                "detail": "center summary counts equal path population grouping",
            },
        ]
    )

    # Independent source reread for the main counts.
    source_center_count = 0
    source_path_count = 0
    source_pass_count = 0
    source_stage4_summary_count = 0
    source_stage4_confirmed_center_count = 0
    source_stage4_confirmed_path_count = 0
    source_stage4_multipath_total = 0
    source_stage4_unmatched_count = 0
    source_stage4_available_count = 0
    for run in data["runs"]:
        directory = root / run["source_result_relpath"]
        persistence = read_csv_rows(directory / "stage3_persistence.csv")
        reliable = read_csv_rows(directory / "stage3_reliable_centers.csv")
        summaries = read_csv_rows(directory / "stage4_joint_summary.csv")
        local_paths = read_csv_rows(directory / "stage4_joint_paths.csv")
        source_center_count += len(reliable)
        source_pass_count += sum(1 for row in persistence if is_true(row.get("persistence_pass")))
        reliable_ids = {canonical_window_id(row.get("center_window_id")) for row in reliable}
        source_path_count += sum(
            1
            for row in persistence
            if is_true(row.get("persistence_pass"))
            and canonical_window_id(row.get("center_window_id")) in reliable_ids
        )
        source_stage4_summary_count += len(summaries)
        summary_by_center = {
            canonical_window_id(row.get("center_window_id")): row for row in summaries
        }
        for center_id, summary in summary_by_center.items():
            source_stage4_paths = [
                row
                for row in local_paths
                if canonical_window_id(row.get("center_window_id")) == center_id
            ]
            source_stage4_multipath_total += stage4_multipath_count(source_stage4_paths)
            confirmed, _ = strict_stage4_confirmation(summary, source_stage4_paths)
            source_stage4_available_count += 1
            if confirmed:
                source_stage4_confirmed_center_count += 1
                source_stage4_confirmed_path_count += stage4_multipath_count(
                    source_stage4_paths
                )
                stage3_candidates = [
                    row
                    for row in path_population
                    if row.get("run_id") == run["run_id"]
                    and row.get("center_window_id") == center_id
                ]
                linked_ids = {
                    parse_int(row.get("stage4_path_id"))
                    for row in stage3_candidates
                    if is_true(row.get("stage4_path_present"))
                }
                source_stage4_unmatched_count += sum(
                    1
                    for row in source_stage4_paths
                    if is_true(row.get("is_multipath"))
                    and parse_int(row.get("path_id")) not in linked_ids
                )

    checks.extend(
        [
            {
                "check": "source_recomputed_stage3_reliable_centers",
                "status": "PASS" if source_center_count == len(centers) else "FAIL",
                "detail": f"source={source_center_count}, output={len(centers)}",
            },
            {
                "check": "source_recomputed_stage3_reliable_paths",
                "status": "PASS" if source_path_count == len(path_population) else "FAIL",
                "detail": f"source={source_path_count}, output={len(path_population)}",
            },
            {
                "check": "source_recomputed_stage3_pass_rows",
                "status": "PASS"
                if source_pass_count
                == sum(
                    parse_int(row.get("stage3_persistence_pass_row_count")) or 0
                    for row in run_rows
                )
                else "FAIL",
                "detail": f"source={source_pass_count}; retained reliable-center paths={source_path_count}",
            },
            {
                "check": "source_recomputed_stage4_summary_rows",
                "status": "PASS"
                if source_stage4_summary_count
                == sum(parse_int(row.get("stage4_summary_row_count")) or 0 for row in run_rows)
                else "FAIL",
                "detail": f"source={source_stage4_summary_count}",
            },
            {
                "check": "source_recomputed_stage4_confirmed_centers",
                "status": "PASS"
                if source_stage4_confirmed_center_count
                == sum(
                    row.get("stage4_outcome") == "stage4_confirmed" for row in centers
                )
                else "FAIL",
                "detail": f"source={source_stage4_confirmed_center_count}",
            },
            {
                "check": "source_recomputed_stage4_confirmed_paths",
                "status": "PASS"
                if source_stage4_confirmed_path_count
                == sum(
                    parse_int(row.get("stage4_confirmed_path_source_count")) or 0
                    for row in centers
                )
                else "FAIL",
                "detail": f"source={source_stage4_confirmed_path_count}, unmatched={source_stage4_unmatched_count}",
            },
        ]
    )

    matrix_shape_valid = len(matrix) == len(ENVIRONMENTS) * len(BANDS) and {
        (row.get("environment_class"), row.get("elevation_band")) for row in matrix
    } == {(environment, band) for environment in ENVIRONMENTS for band in BANDS}
    checks.append(
        {
            "check": "environment_elevation_matrix_has_12_direct_cells",
            "status": "PASS" if matrix_shape_valid else "FAIL",
            "detail": str(len(matrix)),
        }
    )

    lineage_stage3_count = sum(1 for row in lineage if row.get("stage3_present") == "1")
    lineage_stage4_count = sum(1 for row in lineage if row.get("stage4_present") == "1")
    checks.extend(
        [
            {
                "check": "lineage_contains_all_stage3_population_paths",
                "status": "PASS" if lineage_stage3_count == len(path_population) else "FAIL",
                "detail": f"lineage={lineage_stage3_count}, population={len(path_population)}",
            },
            {
                "check": "lineage_stage4_multipath_count_reconciles",
                "status": "PASS"
                if lineage_stage4_count == source_stage4_multipath_total
                else "FAIL",
                "detail": f"lineage={lineage_stage4_count}, source={source_stage4_multipath_total}",
            },
        ]
    )

    # Existing alignment is an independent geometry reference for Stage4-linked centers.
    aligned_context = read_csv_rows(source_path_map["event_context_aligned"])
    aligned_by_center = {
        (row["run_id"], canonical_window_id(row.get("center_window_id"))): row
        for row in aligned_context
    }
    geometry_agrees = True
    geometry_checked = 0
    for center in centers:
        key = (center["run_id"], center["center_window_id"])
        aligned = aligned_by_center.get(key)
        if aligned is None:
            continue
        geometry_checked += 1
        if aligned.get("geometry_join_valid") != str(center.get("geometry_join_valid")):
            geometry_agrees = False
            break
        aligned_elevation = parse_float(aligned.get("elevation_deg"))
        center_elevation = parse_float(center.get("elevation_deg"))
        if aligned_elevation is not None or center_elevation is not None:
            if (
                aligned_elevation is None
                or center_elevation is None
                or abs(aligned_elevation - center_elevation) > 1e-9
            ):
                geometry_agrees = False
                break
    checks.append(
        {
            "check": "stage4_center_geometry_matches_existing_alignment",
            "status": "PASS" if geometry_agrees else "FAIL",
            "detail": f"checked={geometry_checked}",
        }
    )

    source_artifacts_after = collect_source_artifacts(
        root, data["runs"], source_path_map
    )
    source_unchanged = source_artifacts_after == data["source_artifacts_before"]
    checks.append(
        {
            "check": "all_read_source_artifacts_unchanged_during_audit",
            "status": "PASS" if source_unchanged else "FAIL",
            "detail": f"artifacts={len(source_artifacts_after)}",
        }
    )
    current_frozen_status = frozen_hash_status(
        root, data["ingestion_manifest"], source_path_map
    )
    checks.append(
        {
            "check": "frozen_source_wrapper_executor_manifest_inventory_hashes",
            "status": "PASS" if current_frozen_status["all_match"] else "FAIL",
            "detail": json.dumps(current_frozen_status["actual"], sort_keys=True),
        }
    )

    status = "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL"
    return {
        "qa_status": status,
        "audit_namespace": str(output_dir),
        "checks": checks,
        "counts": {
            "runs": len(run_rows),
            "stage3_reliable_centers": len(centers),
            "stage3_reliable_path_observations": len(path_population),
            "stage3_stage4_lineage_rows": len(lineage),
            "stage4_summary_rows": source_stage4_summary_count,
            "stage4_confirmed_centers": source_stage4_confirmed_center_count,
            "stage4_confirmed_paths": source_stage4_confirmed_path_count,
            "stage4_multipath_paths_total": source_stage4_multipath_total,
            "stage4_confirmed_paths_unmatched_to_stage3": source_stage4_unmatched_count,
        },
        "source_artifact_count": len(source_artifacts_after),
        "source_artifacts_after_sha256": source_artifacts_after,
        "source_artifacts_unchanged": source_unchanged,
        "frozen_hash_status": current_frozen_status,
        "gate_record": data["gate_record"],
    }


def markdown_table(rows: list[dict[str, Any]], fields: list[str]) -> str:
    if not rows:
        return "_No rows._"
    header = "| " + " | ".join(fields) + " |\n"
    divider = "| " + " | ".join("---" for _ in fields) + " |\n"
    body = ""
    for row in rows:
        body += "| " + " | ".join(str(row.get(field, "")) for field in fields) + " |\n"
    return header + divider + body.rstrip("\n")


def build_qa_report(qa: dict[str, Any]) -> str:
    checks = qa["checks"]
    check_rows = [
        {
            "status": row["status"],
            "check": row["check"],
            "detail": row["detail"],
        }
        for row in checks
    ]
    return (
        "# Stage3 academic modeling reassessment — independent QA\n\n"
        f"- QA status: `{qa['qa_status']}`\n"
        f"- Namespace: `{qa['audit_namespace']}`\n"
        "- Scope: read-only source reread and reconciliation; no MATLAB, SAGE, raw IQ, "
        "or statistical fitting.\n\n"
        "## Checks\n\n"
        + markdown_table(check_rows, ["status", "check", "detail"])
        + "\n\n## Counts\n\n"
        + markdown_table(
            [{"metric": key, "value": value} for key, value in qa["counts"].items()],
            ["metric", "value"],
        )
        + "\n"
    )


def build_report(data: dict[str, Any], qa: dict[str, Any], report_path: Path) -> str:
    centers = data["centers"]
    paths = data["path_population"]
    eligible_centers = [row for row in centers if is_true(row.get("academic_eligible"))]
    eligible_paths = [row for row in paths if is_true(row.get("academic_eligible"))]
    elevation_centers = [row for row in eligible_centers if is_true(row.get("elevation_ready"))]
    elevation_paths = [row for row in eligible_paths if is_true(row.get("elevation_ready"))]
    summary = group_counts(centers, paths)
    support = data["support_rows"]
    positive_cells = sum(row["direct_support_status"] == "DIRECT_STAGE3_SUPPORT" for row in support)
    stage4_eligible_centers = [
        row
        for row in eligible_centers
        if row.get("stage4_outcome") == "stage4_confirmed"
    ]
    stage4_eligible_paths = [
        row
        for row in paths
        if is_true(row.get("stage4_confirmed"))
        and is_true(row.get("academic_eligible"))
    ]
    repeated_centers = sum(is_true(row.get("adjacent_reliable_center_within_radius")) for row in centers)
    stage4_rejection_by_outcome = Counter(row.get("stage4_outcome") for row in eligible_centers)
    hash_rows = [
        {
            "hash": key,
            "expected": data["frozen_status"]["expected"].get(key, ""),
            "actual": data["frozen_status"]["actual"].get(key, ""),
            "match": data["frozen_status"]["matches"].get(key, False),
        }
        for key in [
            "pipeline_sha256",
            "wrapper_sha256",
            "executor_sha256",
            "manifest_sha256",
            "inventory_sha256",
        ]
    ]
    matrix_for_report = [
        {
            "environment": row["environment_class"],
            "elevation": row["elevation_band"],
            "eligible_centers": row["academic_eligible_center_count"],
            "eligible_paths": row["academic_eligible_path_count"],
            "stage4_confirmed_paths": row["stage4_confirmed_path_link_count"],
            "support": row["direct_support_status"],
        }
        for row in support
    ]
    selection_rows = [
        row
        for row in data["comparison_rows"]
        if row["granularity"] == "path_observation"
        and row["parameter"] in {"excess_delay_samples", "doppler_offset_hz", "relative_power_db"}
        and row["source_layer"] == "stage3"
    ]
    selection_for_report = [
        {
            "group": row["selection_group"],
            "parameter": row["parameter"],
            "n": row["n"],
            "median": row["median"],
            "q25": row["q25"],
            "q75": row["q75"],
        }
        for row in selection_rows
    ]
    return f"""# Stage3 Academic Modeling Population Reassessment

Audit timestamp: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`  
Audit namespace: `{data['output_dir']}`  
Independent QA: **{qa['qa_status']}**

## Scope and guardrails

This is the first, read-only academic-mainline reassessment. It consumes the 64 QA-passed and complete SAGE namespaces listed in the immutable ingestion partition, their Stage0/Stage3/Stage4 CSV artifacts, the existing geometry/time-alignment layer, scene metadata, and frozen provenance hashes. It does not start MATLAB/SAGE, read raw IQ, rerun any batch, modify Stage4/database/model/QA history, fit a new Stage3 model, or process 20.46 MHz data. The fixed engineering/darkroom branches are not used to define this population.

The academic candidate is defined as:

`Stage3 reliable center` + `Stage3 persistence path` + `persistence_pass=true`.

The term “Stage3 reliable/persistent multipath component” denotes an algorithm-level estimate, not external physical ground truth. Stage4 strict joint-confirmation remains a high-confidence validation subset. The Stage3 population is still an observation-level population; repeated reliable center windows within a run can share the existing ±2-window persistence footprints.

## A–C. Population and Stage4 attrition

| quantity | count |
| --- | ---: |
| QA-passed complete runs audited | {len(data['runs'])} |
| Stage3 persistence rows (all candidates) | {sum(parse_int(row.get('stage3_persistence_row_count')) or 0 for row in data['run_rows'])} |
| Stage3 `persistence_pass=true` rows before reliable-center restriction | {sum(parse_int(row.get('stage3_persistence_pass_row_count')) or 0 for row in data['run_rows'])} |
| Stage3 reliable centers | {len(centers)} |
| Stage3 reliable-center path observations | {len(paths)} |
| Academic-eligible centers after legacy/context exclusion | {len(eligible_centers)} |
| Academic-eligible path observations | {len(eligible_paths)} |
| Elevation-ready centers | {len(elevation_centers)} |
| Elevation-ready path observations | {len(elevation_paths)} |
| Stage4 strict-confirmed centers after academic exclusion | {len(stage4_eligible_centers)} |
| Stage4 paths linked back to Stage3 population | {len(stage4_eligible_paths)} |
| Stage4 strict-confirmed multipath paths in source (all contexts) | {qa['counts']['stage4_confirmed_paths']} |

Stage3 reliable-center restriction removes `{sum(parse_int(row.get('stage3_partial_pass_row_count')) or 0 for row in data['run_rows'])}` path rows that individually passed persistence but belonged to a center where not every candidate path passed. This is intentional for the proposed conservative Stage3 population and must not be described as a physical absence of multipath.

Stage4 has `{summary['stage4_available_center_count']}` available center rows, `{summary['stage4_confirmed_center_count']}` strict-confirmed academic-eligible centers, `{summary['stage4_rejected_center_count']}` available-but-rejected centers, and `{summary['stage4_cap_missing_center_count']}` reliable centers missing because the Stage4 implementation evaluates at most `{STAGE4_MAXIMUM_JOINT_CENTERS}` candidates per run. The Stage4 cap is an algorithmic selection mechanism and is a major source of Stage3→Stage4 attrition.

## D. Selection, duplication, and lineage findings

The Stage3-to-Stage4 center link is exact on `(run_id, center_window_id)`. The path link is explicitly positional: `stage4 path_id = stage3 multipath_id + 1`, consistent with the frozen source path construction and Stage4 ordering. It is a lineage link, not a claim that either layer has externally verified path identity.

- Stage3 path observations linked to a Stage4 multipath output: `{sum(is_true(row.get('stage4_path_present')) for row in paths)}`.
- Stage3 paths linked to strict-confirmed Stage4 paths: `{len(stage4_eligible_paths)}`.
- Stage4 strict-confirmed source paths not found by that Stage3 positional link: `{qa['counts']['stage4_confirmed_paths_unmatched_to_stage3']}`.
- Reliable centers with another reliable center within the existing ±2-window persistence radius: `{repeated_centers}` of `{len(centers)}`. This is a diagnostic overlap indicator only; no new track/event threshold was introduced.
- Formal track/event consolidation: **not established in this phase**. The tables retain center-window and path-observation granularities and expose overlap indicators so a later Commander-approved deduplication rule can be tested without silently changing the population.

The parameter comparison table tests, descriptively, delay, Doppler, power, matched-window count, consecutive-run count, selected order, and center-level persistence/elevation variables across the full Stage3 population and the Stage4 outcome groups. It does not assign causal meaning to Stage4 selection. The most important confounders are the Stage4 maximum-center cap, Stage4 joint model selection, and repeated center windows.

{markdown_table(selection_for_report, ['group', 'parameter', 'n', 'median', 'q25', 'q75'])}

## Environment × elevation support

Elevation is kept continuous in the path/center tables and binned only for coverage summaries using the frozen bins `LOW=[0,30)`, `MID=[30,60)`, `HIGH=[60,90]`. Direct Stage3 support exists in **{positive_cells}/12** environment×elevation cells. The no-support cell(s) and sparse cells are shown explicitly; no prior-only values are inserted.

{markdown_table(matrix_for_report, ['environment', 'elevation', 'eligible_centers', 'eligible_paths', 'stage4_confirmed_paths', 'support'])}

Stage3 materially expands the academic evidence relative to Stage4-only: it provides `{len(eligible_centers)}` eligible reliable centers and `{len(eligible_paths)}` path observations across `{len({row['scene_id'] for row in eligible_centers})}` scenes and `{len({row['run_id'] for row in eligible_centers})}` runs, while Stage4 strict confirmation retains `{len(stage4_eligible_centers)}` eligible centers and `{len(stage4_eligible_paths)}` linked paths. This supports using Stage4 as a validation subset rather than the sole academic population, subject to the deduplication/weighting conditions below.

## Decisions requested by the audit

- `USE_STAGE3_AS_PRIMARY_ACADEMIC_POPULATION=CONDITIONAL`
  - **Proposed, not applied:** `ACADEMIC_MODELING_POPULATION_V2` would use the academic-eligible Stage3 reliable/persistent population as primary and retain Stage4 strict-confirmed paths as a high-confidence validation subset.
  - Conditions: pre-specify run/scene-block handling and a track/event deduplication or weighting rule; report Stage3 and Stage4 layers separately; do not call Stage3 ground truth; preserve the Stage4 baseline unchanged.
- `PROCESS_20_46_MHZ_NEXT=CONDITIONAL`
  - Do not start it from this audit. First approve the Stage3 population contract and the observation-to-track handling; then a separate 20.46 MHz planning/preflight decision can be made.
- `NEW_DATA_COLLECTION_REQUIRED=CONDITIONAL`
  - Not required to start a bounded Stage3-primary model because Stage3 has direct support in {positive_cells}/12 cells.
  - Required if the paper claims complete support for every cell or wants stronger independent-scene support for the no-support/sparse cells, especially Highway/Open–LOW and other cells with few independent runs/scenes.

No new `environment_elevation_path_distribution_stage3_v1` fit was performed. It may be proposed after the population contract is approved; the existing Stage4 model remains the immutable high-confidence baseline.

## Frozen provenance check

{markdown_table(hash_rows, ['hash', 'expected', 'actual', 'match'])}

The audit source artifact snapshot contains `{len(data['source_artifacts_before'])}` non-raw files and was rehashed after analysis. The independent QA result is `{qa['qa_status']}`. Execution gates recorded in the audit are `{json.dumps(data['gate_record'], sort_keys=True)}`.

## Deliverables

The CSV tables and independent QA files are in [`{data['output_dir']}`]({data['output_dir']}). The report is [`{report_path}`]({report_path}). The namespace is new-only and should not be overwritten; subsequent changes require a new versioned namespace.

This task stops here and waits for Commander approval. No automatic population switch, new fitting, batch continuation, MATLAB task, or data collection was initiated.
"""


def output_hashes(output_dir: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="project root",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="new-only audit output namespace",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="new report path; defaults to docs/STAGE3_ACADEMIC_MODELING_REASSESSMENT.md",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    report_path = args.report_path or root / "docs/STAGE3_ACADEMIC_MODELING_REASSESSMENT.md"
    report_path = report_path if report_path.is_absolute() else root / report_path
    if report_path.exists():
        raise FileExistsError(f"report already exists; refusing to overwrite: {report_path}")

    data = build_audit(root, output_dir)
    qa = independent_qa(data)
    write_json(output_dir / "qa_result.json", qa)
    (output_dir / "qa_report.md").write_text(build_qa_report(qa), encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(data, qa, report_path), encoding="utf-8")

    manifest = {
        "audit_id": "stage3_academic_modeling_reassessment_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_scope": {
            "ingestion_id": INGESTION_ID,
            "alignment_id": ALIGNMENT_ID,
            "run_count": len(data["runs"]),
            "source_artifact_count": len(data["source_artifacts_before"]),
        },
        "definition": {
            "primary_candidate": "Stage3 reliable center + persistence_pass=true path",
            "stage3_semantics": "algorithm-level reliable/persistent multipath estimate",
            "stage4_semantics": "strict joint-confirmed high-confidence validation subset",
            "elevation_bins": {"LOW": "[0,30)", "MID": "[30,60)", "HIGH": "[60,90]"},
            "track_consolidation": "not established; overlap diagnostic only",
        },
        "frozen_hash_status": data["frozen_status"],
        "source_artifacts_before_sha256": data["source_artifacts_before"],
        "source_artifacts_after_sha256": qa.get("source_artifacts_after_sha256", {}),
        "gate_record": data["gate_record"],
        "qa_status": qa["qa_status"],
        "qa_result_sha256": sha256_file(output_dir / "qa_result.json"),
        "qa_report_sha256": sha256_file(output_dir / "qa_report.md"),
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path),
        "output_sha256": output_hashes(output_dir),
    }
    write_json(output_dir / "audit_manifest.json", manifest)
    print(
        json.dumps(
            {
                "qa_status": qa["qa_status"],
                "output_dir": str(output_dir),
                "report_path": str(report_path),
                "stage3_reliable_centers": len(data["centers"]),
                "stage3_reliable_path_observations": len(data["path_population"]),
                "academic_eligible_centers": sum(
                    is_true(row.get("academic_eligible")) for row in data["centers"]
                ),
                "academic_eligible_paths": sum(
                    is_true(row.get("academic_eligible"))
                    for row in data["path_population"]
                ),
            },
            sort_keys=True,
        )
    )
    return 0 if qa["qa_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
