#!/usr/bin/env python3
"""Extend a verified Mainline Stage2/GSV audit with private route summaries.

This runner verifies every file pinned by the preceding geometry audit, then
reads only Stage0 and Stage2 CSVs plus checksum-validated RMC sentences. It
does not open raw IQ, MAT/HDF5, CIR, or PDP payloads. Coordinate-bearing output
is written only into the existing local geometry-audit namespace.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.channel_modeling.mainline_stage2_geometry import (  # noqa: E402
    build_stage0_utc_index,
    build_stage2_window_index,
)
from scripts.channel_modeling.mainline_stage2_trajectory import (  # noqa: E402
    aggregate_stage2_metrics_by_fix,
    build_route_segment_rows,
    build_trajectory_window_overlay,
    parse_valid_rmc_fixes_with_diagnostics,
    split_trajectory_components,
    summarize_spatial_dependence,
)
from scripts.channel_modeling.run_mainline_stage2_geometry_audit import (  # noqa: E402
    COHORT_REL,
    MAINLINE_COHORT_ID,
    MAINLINE_COHORT_TASK_COUNT,
    MAINLINE_STAGE2_LEDGER_SHA256,
    RUN_INDEX_REL,
    STAGE2_LEDGER_REL,
    _positive_count,
    _project_rel,
    _read_csv,
    _required_text,
    _write_csv,
)
from scripts.event_database.align_modeling_context import sha256_file  # noqa: E402


GEOMETRY_AUDIT_NAME = "geometry_alignment_audit.json"
GEOMETRY_OVERLAY_NAME = "geometry_window_overlay.csv"
GEOMETRY_COVERAGE_NAME = "geometry_coverage_summary.csv"
TRAJECTORY_OVERLAY_NAME = "trajectory_window_overlay.csv"
ROUTE_SEGMENTS_NAME = "route_segments.csv"
SPATIAL_SUMMARY_NAME = "spatial_dependence_summary.csv"
TRAJECTORY_AUDIT_NAME = "trajectory_segmentation_audit.json"
ROUTE_OUTPUT_NAMES = (
    TRAJECTORY_OVERLAY_NAME,
    ROUTE_SEGMENTS_NAME,
    SPATIAL_SUMMARY_NAME,
    TRAJECTORY_AUDIT_NAME,
)
ALLOWED_AUDIT_INPUT_SUFFIXES = {".csv", ".nmea", ".26n", ".py", ".json", ".md"}
ROUTE_BIN_LENGTHS_M = (50, 100, 250)
LAG_EDGES_M = (0, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 20000)
BASE_MAX_GAP_SECONDS = 2.5
BASE_JUMP_SPEED_MPS = 80.0

TRAJECTORY_OVERLAY_FIELDS = (
    "run_id", "window_id", "scene_id", "prn", "tracking_channel",
    "window_utc", "position_utc", "position_delta_seconds",
    "position_delta_seconds_abs", "position_source_path",
    "position_source_record_id", "latitude_deg", "longitude_deg",
    "route_component_id", "route_cumulative_distance_m",
    "receiver_speed_mps", "receiver_course_deg", "position_status",
    "missing_reason",
)
ROUTE_SEGMENT_FIELDS = (
    "route_segment_id", "scene_id", "component_id", "bin_length_m", "bin_index",
    "bin_start_m", "bin_end_m", "observed_distance_min_m", "observed_distance_max_m",
    "fix_count", "stage2_window_count", "run_count", "prn_count",
    "co_located_cross_prn_fix_count", "median_receiver_speed_mps",
    "min_receiver_speed_mps", "max_receiver_speed_mps", "valid_receiver_speed_fix_count",
    "circular_mean_receiver_course_deg", "valid_receiver_course_fix_count", "drive_state",
    "sustained_drive_state_change_candidate", "sustained_speed_change_candidate",
    "sustained_course_change_candidate", "candidate_min_fix_count_per_bin",
    "candidate_speed_delta_threshold_mps", "candidate_speed_stability_mps",
    "candidate_stationary_speed_limit_mps", "candidate_course_delta_threshold_deg",
    "candidate_course_stability_deg", "analysis_unit_role",
)
SPATIAL_SUMMARY_FIELDS = (
    "metric_name", "lag_lower_m", "lag_upper_m", "pair_count", "run_count", "scene_count",
    "mean_scene_normalized_semivariance", "mean_scene_correlation_proxy",
    "decorrelation_threshold", "correlation_range_candidate_m",
    "effective_local_unit_count_candidate", "estimate_status", "range_scene_block_count",
    "range_lag_band_count", "leave_one_scene_out_range_count",
    "leave_one_scene_out_range_cv", "minimum_scene_count_for_range",
    "minimum_lag_bands_for_range", "maximum_scene_block_cv_for_range",
    "cross_prn_colocated_group_count", "cross_prn_colocated_run_pair_count", "interpretation",
)


def _resolve_audit_input(project_root: Path, code_root: Path, key: str) -> Path:
    text = str(key).replace("\\", "/").strip()
    pure = PurePosixPath(text)
    if not text or pure.is_absolute() or ".." in pure.parts:
        raise ValueError("geometry input path is not a safe relative path")
    parts = pure.parts
    if parts[0] == "project_root":
        base, relative_parts = project_root, parts[1:]
    elif parts[0] == "code_worktree":
        base, relative_parts = code_root, parts[1:]
    else:
        base, relative_parts = project_root, parts
    if not relative_parts:
        raise ValueError("geometry input path is empty")
    resolved_base = base.resolve(strict=True)
    resolved = resolved_base.joinpath(*relative_parts).resolve(strict=True)
    try:
        resolved.relative_to(resolved_base)
    except ValueError as error:
        raise ValueError("geometry input resolves outside its declared root") from error
    if not resolved.is_file():
        raise ValueError("geometry input is not a regular file")
    if resolved.suffix.casefold() not in ALLOWED_AUDIT_INPUT_SUFFIXES:
        raise ValueError("geometry audit pins a disallowed payload type")
    return resolved


def _verify_geometry_input_pins(
    project_root: Path, code_root: Path, geometry_audit: Mapping[str, Any]
) -> dict[Path, dict[str, Any]]:
    input_files = geometry_audit.get("input_files")
    if not isinstance(input_files, dict) or len(input_files) < 5:
        raise ValueError("geometry audit input_files must contain pinned inputs")

    verified: dict[Path, dict[str, Any]] = {}
    for key, raw_entry in sorted(input_files.items()):
        if not isinstance(raw_entry, dict):
            raise ValueError("geometry audit contains an invalid input pin")
        expected_sha = str(raw_entry.get("sha256", "")).strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            raise ValueError("geometry audit contains an invalid SHA-256 pin")
        expected_size = _positive_count(
            raw_entry.get("size_bytes"), label="geometry input size", allow_zero=True
        )
        path = _resolve_audit_input(project_root, code_root, str(key))
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise ValueError(f"geometry input size mismatch: {key}")
        actual_sha = sha256_file(path)
        if actual_sha != expected_sha:
            raise ValueError(f"geometry input SHA-256 mismatch: {key}")
        if path in verified:
            raise ValueError("geometry audit aliases one input path under multiple keys")
        verified[path] = {"key": str(key), **raw_entry, "sha256": actual_sha}

    software = geometry_audit.get("audit_software")
    if not isinstance(software, dict):
        raise ValueError("geometry audit software pins are missing")
    expected_software = {
        "audit_runner": ("scripts/channel_modeling/run_mainline_stage2_geometry_audit.py", "audit_software:audit_runner"),
        "geometry_identity_helper": ("scripts/channel_modeling/mainline_stage2_geometry.py", "audit_software:geometry_identity_helper"),
    }
    for name, (expected_relative, expected_role) in expected_software.items():
        pin = software.get(name)
        if not isinstance(pin, dict):
            raise ValueError(f"geometry audit is missing software pin {name}")
        path_text = str(pin.get("path", "")).replace("\\", "/")
        if pin.get("root") != "code_worktree" or path_text != expected_relative:
            raise ValueError(f"geometry audit software path mismatch for {name}")
        path = _resolve_audit_input(project_root, code_root, f"code_worktree/{path_text}")
        verified_entry = verified.get(path)
        if verified_entry is None or verified_entry.get("role") != expected_role:
            raise ValueError(f"geometry software input record missing for {name}")
        if str(pin.get("sha256", "")).lower() != verified_entry["sha256"]:
            raise ValueError(f"geometry software SHA mismatch for {name}")
    return verified


def _validate_window_overlay_reconciliation(
    stage2_windows: Sequence[Mapping[str, Any]],
    overlay_rows: Sequence[Mapping[str, Any]],
) -> int:
    expected: dict[tuple[str, str], tuple[str, str, str]] = {}
    for row in stage2_windows:
        key = (str(row.get("run_id", "")).strip(), str(row.get("window_id", "")).strip())
        if not all(key) or key in expected:
            raise ValueError("Stage2 window identities are empty or duplicated")
        expected[key] = (
            str(row.get("scene_id", "")).strip(),
            str(row.get("prn", "")).strip(),
            str(row.get("tracking_channel", "")).strip(),
        )

    actual: dict[tuple[str, str], tuple[str, str, str]] = {}
    for row in overlay_rows:
        key = (str(row.get("run_id", "")).strip(), str(row.get("window_id", "")).strip())
        if not all(key) or key in actual:
            raise ValueError("geometry overlay identities are empty or duplicated")
        status = str(row.get("status", "")).strip()
        if status not in {"GSV_MATCHED", "MISSING"}:
            raise ValueError("geometry overlay contains an unknown match status")
        if status == "GSV_MATCHED":
            if not str(row.get("elevation_deg", "")).strip() or not str(row.get("gsv_source_utc", "")).strip():
                raise ValueError("matched geometry row is missing measured elevation evidence")
        elif str(row.get("elevation_deg", "")).strip():
            raise ValueError("unmatched geometry row must not contain an elevation")
        actual[key] = (
            str(row.get("scene_id", "")).strip(),
            str(row.get("prn", "")).strip(),
            str(row.get("tracking_channel", "")).strip(),
        )

    if set(actual) != set(expected):
        raise ValueError("geometry overlay window identities do not reconcile to Stage2")
    for key, identity in expected.items():
        if actual[key] != identity:
            raise ValueError(f"geometry overlay identity metadata mismatch for {key}")
    return len(expected)


def _load_geometry_audit(
    project_root: Path, code_root: Path, output_dir: Path
) -> tuple[dict[str, Any], dict[Path, dict[str, Any]], list[dict[str, str]]]:
    audit_path = output_dir / GEOMETRY_AUDIT_NAME
    if not audit_path.is_file():
        raise ValueError("geometry alignment audit is missing")
    try:
        geometry_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("geometry alignment audit cannot be read as JSON") from error
    if not isinstance(geometry_audit, dict) or geometry_audit.get("schema_version") != "mainline-stage2-gsv-geometry-audit-v1":
        raise ValueError("unsupported geometry audit schema")
    if geometry_audit.get("audit_status") != "PASS":
        raise ValueError("geometry alignment audit is not PASS")
    if geometry_audit.get("cohort_id") != MAINLINE_COHORT_ID:
        raise ValueError("geometry audit cohort identity mismatch")
    if int(geometry_audit.get("cohort_task_count", -1)) != MAINLINE_COHORT_TASK_COUNT:
        raise ValueError("geometry audit task count mismatch")

    verified_inputs = _verify_geometry_input_pins(project_root, code_root, geometry_audit)
    counts = geometry_audit.get("input_counts")
    if not isinstance(counts, dict):
        raise ValueError("geometry audit input counts are missing")
    expected_counts = {
        "stage0_window_count": 285752,
        "stage2_path_row_count": 16761,
        "stage2_window_count": 7847,
        "overlay_row_count": 7847,
    }
    for field, expected in expected_counts.items():
        if int(counts.get(field, -1)) != expected:
            raise ValueError(f"geometry audit count mismatch: {field}")
    if geometry_audit.get("stage2_ledger_sha256_before") != MAINLINE_STAGE2_LEDGER_SHA256 or geometry_audit.get("stage2_ledger_sha256_after") != MAINLINE_STAGE2_LEDGER_SHA256:
        raise ValueError("geometry audit Task 6 ledger pin mismatch")

    geometry_overlay_path = output_dir / GEOMETRY_OVERLAY_NAME
    coverage_path = output_dir / GEOMETRY_COVERAGE_NAME
    if not geometry_overlay_path.is_file() or not coverage_path.is_file():
        raise ValueError("geometry audit output CSV is missing")
    geometry_overlay = _read_csv(geometry_overlay_path, label="GSV geometry overlay")
    coverage_rows = _read_csv(coverage_path, label="GSV coverage summary")
    if len(geometry_overlay) != expected_counts["overlay_row_count"]:
        raise ValueError("GSV geometry overlay row count mismatch")
    total_rows = [row for row in coverage_rows if row.get("summary_scope") == "TOTAL"]
    if len(total_rows) != 1:
        raise ValueError("GSV coverage summary must contain one TOTAL row")
    total = total_rows[0]
    for field, expected in (
        ("window_count", expected_counts["stage2_window_count"]),
        ("gsv_matched_count", int(counts["gsv_matched_count"])),
        ("missing_count", int(counts["missing_count"])),
    ):
        if int(total.get(field, -1)) != expected:
            raise ValueError(f"GSV coverage summary mismatch: {field}")
    return geometry_audit, verified_inputs, geometry_overlay


def _cohort_input_path(
    raw_entry: Mapping[str, Any], project_root: Path, verified_inputs: Mapping[Path, Mapping[str, Any]], *, label: str
) -> tuple[Path, str]:
    path_text = str(raw_entry.get("path", "")).strip()
    candidate = Path(path_text)
    if candidate.is_absolute():
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(project_root.resolve(strict=True))
        except ValueError as error:
            raise ValueError(f"{label} escapes the project root") from error
    else:
        resolved = (project_root / candidate).resolve(strict=True)
        try:
            resolved.relative_to(project_root.resolve(strict=True))
        except ValueError as error:
            raise ValueError(f"{label} escapes the project root") from error
    entry = verified_inputs.get(resolved)
    expected_sha = str(raw_entry.get("sha256", "")).strip().lower()
    if entry is None or entry.get("sha256") != expected_sha:
        raise ValueError(f"{label} is not bound to the geometry input audit")
    if _positive_count(raw_entry.get("size_bytes"), label=f"{label} size", allow_zero=True) != resolved.stat().st_size:
        raise ValueError(f"{label} size changed after geometry audit")
    return resolved, expected_sha


def _load_cohort_and_inputs(
    project_root: Path,
    code_root: Path,
    geometry_audit: Mapping[str, Any],
    verified_inputs: Mapping[Path, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, list[dict[str, str]]], list[dict[str, str]], str]:
    cohort_path = (project_root / COHORT_REL).resolve(strict=True)
    cohort_pin = verified_inputs.get(cohort_path)
    if cohort_pin is None or cohort_pin.get("role") != "cohort":
        raise ValueError("frozen cohort is not present in verified geometry input pins")
    cohort_sha = str(cohort_pin["sha256"])
    if cohort_sha != str(geometry_audit.get("cohort_sha256", "")).lower():
        raise ValueError("geometry audit cohort SHA-256 mismatch")
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    if not isinstance(cohort, dict) or cohort.get("cohort_id") != MAINLINE_COHORT_ID:
        raise ValueError("frozen cohort identity mismatch")
    raw_tasks = cohort.get("tasks")
    if not isinstance(raw_tasks, list) or len(raw_tasks) != MAINLINE_COHORT_TASK_COUNT:
        raise ValueError("frozen cohort task list does not reconcile")
    if _positive_count(cohort.get("eligible_count"), label="cohort eligible_count") != len(raw_tasks):
        raise ValueError("frozen cohort eligible_count does not reconcile")
    source_pins = cohort.get("source_sha256")
    if not isinstance(source_pins, dict) or not source_pins:
        raise ValueError("frozen cohort source SHA pins are missing")
    for name, source_pin in source_pins.items():
        if not isinstance(source_pin, dict):
            raise ValueError(f"invalid frozen cohort source pin: {name}")
        source_text = str(source_pin.get("path", "")).strip()
        source_candidate = Path(source_text)
        source_base = (
            code_root
            if not source_candidate.is_absolute()
            and source_candidate.parts
            and source_candidate.parts[0].casefold() == "scripts"
            else project_root
        )
        source_path = source_candidate.resolve(strict=True) if source_candidate.is_absolute() else (source_base / source_candidate).resolve(strict=True)
        try:
            source_path.relative_to(source_base.resolve(strict=True))
        except ValueError as error:
            raise ValueError(f"frozen cohort source escapes its declared root: {name}") from error
        verified_source = verified_inputs.get(source_path)
        expected_sha = str(source_pin.get("sha256", "")).strip().lower()
        if verified_source is None or verified_source.get("sha256") != expected_sha:
            raise ValueError(f"frozen cohort source pin not verified by geometry audit: {name}")

    tasks: list[dict[str, Any]] = []
    seen_runs: set[str] = set()
    stage0_by_run: dict[str, list[dict[str, str]]] = {}
    stage2_rows: list[dict[str, str]] = []
    for raw in raw_tasks:
        if not isinstance(raw, dict):
            raise ValueError("invalid frozen cohort task row")
        run_id = _required_text(raw, "run_id")
        scene_id = _required_text(raw, "scene_id")
        prn = _required_text(raw, "prn").upper()
        if not re.fullmatch(r"G(?:0[1-9]|[12][0-9]|3[0-2])", prn) or run_id in seen_runs:
            raise ValueError("invalid or duplicate frozen cohort run identity")
        seen_runs.add(run_id)
        channel = _positive_count(raw.get("tracking_channel"), label="tracking_channel", allow_zero=True)
        stage_csvs = raw.get("stage_csvs")
        counts = raw.get("stage_counts_from_gate_a")
        if not isinstance(stage_csvs, dict) or not isinstance(counts, dict):
            raise ValueError("cohort Stage CSV references or counts are missing")
        stage0_entry = stage_csvs.get("stage0_valid_windows")
        stage2_entry = stage_csvs.get("stage2_selected_paths")
        if not isinstance(stage0_entry, dict) or not isinstance(stage2_entry, dict):
            raise ValueError("cohort Stage0/Stage2 input references are missing")
        stage0_path, stage0_sha = _cohort_input_path(
            stage0_entry, project_root, verified_inputs, label=f"Stage0 input {run_id}"
        )
        stage2_path, stage2_sha = _cohort_input_path(
            stage2_entry, project_root, verified_inputs, label=f"Stage2 input {run_id}"
        )
        stage0_rows = _read_csv(stage0_path, label=f"Stage0 {run_id}")
        if len(stage0_rows) != _positive_count(
            counts.get("stage0_valid_40ms_windows"), label=f"Stage0 row count {run_id}", allow_zero=True
        ):
            raise ValueError(f"Stage0 row count mismatch for {run_id}")
        task = {
            **raw,
            "run_id": run_id,
            "scene_id": scene_id,
            "prn": prn,
            "tracking_channel": str(channel),
            "stage0_path": stage0_path,
            "stage0_sha256": stage0_sha,
            "stage2_source_path": stage2_path,
            "stage2_source_sha256": stage2_sha,
            "expected_stage0_windows": len(stage0_rows),
            "expected_stage2_paths": _positive_count(
                counts.get("stage2_selected_path_count"), label=f"Stage2 row count {run_id}", allow_zero=True
            ),
        }
        tasks.append(task)
        stage0_by_run[run_id] = stage0_rows

    ledger_path = (project_root / STAGE2_LEDGER_REL).resolve(strict=True)
    ledger_pin = verified_inputs.get(ledger_path)
    if ledger_pin is None or ledger_pin.get("role") != "stage2_ledger":
        raise ValueError("Task 6 Stage2 ledger is not present in verified input pins")
    if str(geometry_audit.get("stage2_ledger_path", "")).replace("\\", "/") != STAGE2_LEDGER_REL.as_posix():
        raise ValueError("geometry audit Stage2 ledger path mismatch")
    ledger_sha_before = str(ledger_pin["sha256"])
    if ledger_sha_before != MAINLINE_STAGE2_LEDGER_SHA256:
        raise ValueError("Task 6 Stage2 ledger differs from its approved SHA-256")
    stage2_rows = _read_csv(ledger_path, label="Task 6 Stage2 ledger")
    task_by_run = {str(task["run_id"]): task for task in tasks}
    if {str(row.get("run_id", "")).strip() for row in stage2_rows} != set(task_by_run):
        raise ValueError("Task 6 Stage2 ledger run IDs do not reconcile with cohort")
    rows_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stage2_rows:
        run_id = _required_text(row, "run_id")
        task = task_by_run[run_id]
        for field, expected in (
            ("scene_id", str(task["scene_id"])),
            ("prn", str(task["prn"])),
            ("tracking_channel", str(task["tracking_channel"])),
            ("environment_class", str(task.get("environment_class", "")).strip()),
            ("elevation_group", str(task.get("elevation_group", "MISSING")).strip() or "MISSING"),
        ):
            if str(row.get(field, "")).strip() != expected:
                raise ValueError(f"Stage2 ledger {field} conflicts with cohort for {run_id}")
        if str(row.get("source_stage2_csv_sha256", "")).strip().lower() != task["stage2_source_sha256"]:
            raise ValueError(f"Stage2 source SHA-256 conflicts with cohort for {run_id}")
        rows_by_run[run_id].append(row)
    for run_id, task in task_by_run.items():
        if len(rows_by_run[run_id]) != task["expected_stage2_paths"]:
            raise ValueError(f"Stage2 path row count mismatch for {run_id}")
    if sha256_file(ledger_path) != ledger_sha_before:
        raise ValueError("Task 6 Stage2 ledger changed while it was read")
    return cohort, tasks, stage0_by_run, stage2_rows, ledger_sha_before


def _route_sensitivity(fixes_by_scene: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    scenarios = (
        ("GAP_1_5S", 1.5, BASE_JUMP_SPEED_MPS),
        ("GAP_2_5S", 2.5, BASE_JUMP_SPEED_MPS),
        ("GAP_5S", 5.0, BASE_JUMP_SPEED_MPS),
        ("JUMP_50MPS", BASE_MAX_GAP_SECONDS, 50.0),
        ("JUMP_80MPS", BASE_MAX_GAP_SECONDS, 80.0),
        ("JUMP_120MPS", BASE_MAX_GAP_SECONDS, 120.0),
    )
    result: dict[str, Any] = {}
    for label, gap, speed in scenarios:
        component_count = 0
        break_counts: Counter[str] = Counter()
        for fixes in fixes_by_scene.values():
            segmented = split_trajectory_components(
                fixes, max_gap_seconds=gap, jump_speed_mps=speed
            )
            component_count += len({row["component_id"] for row in segmented})
            break_counts.update(row["break_reason"] or "CONNECTED" for row in segmented)
        result[label] = {
            "max_gap_seconds": gap,
            "jump_speed_mps": speed,
            "component_count": component_count,
            "fix_count_by_break_reason": dict(sorted(break_counts.items())),
        }
    return result


def _scene_route_summaries(
    tasks: Sequence[Mapping[str, Any]],
    stage0_by_run: Mapping[str, Sequence[Mapping[str, str]]],
    stage2_windows: Sequence[Mapping[str, Any]],
    trajectory_overlay: Sequence[Mapping[str, Any]],
    fixes_by_scene: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    task_by_scene: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for task in tasks:
        task_by_scene[str(task["scene_id"])].append(task)
    stage2_by_scene: Counter[str] = Counter(str(row["scene_id"]) for row in stage2_windows)
    stage0_by_scene: Counter[str] = Counter()
    for task in tasks:
        stage0_by_scene[str(task["scene_id"])] += len(stage0_by_run[str(task["run_id"])])
    overlay_by_scene: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in trajectory_overlay:
        overlay_by_scene[str(row["scene_id"])].append(row)

    result = []
    for scene_id in sorted(task_by_scene):
        fixes = list(fixes_by_scene.get(scene_id, []))
        components: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        breaks: Counter[str] = Counter()
        for row in fixes:
            components[str(row["component_id"])].append(row)
            breaks[str(row.get("break_reason") or "CONNECTED")] += 1
        route_distance_m = sum(
            max(float(row["cumulative_distance_m"]) for row in component_rows)
            for component_rows in components.values()
        )
        scene_overlay = overlay_by_scene.get(scene_id, [])
        matched = sum(row.get("position_status") == "POSITION_MATCHED" for row in scene_overlay)
        missing_reasons = Counter(
            str(row.get("missing_reason") or "UNKNOWN")
            for row in scene_overlay
            if row.get("position_status") != "POSITION_MATCHED"
        )
        result.append(
            {
                "scene_id": scene_id,
                "environment_class": str(task_by_scene[scene_id][0].get("environment_class", "UNKNOWN")),
                "task_count": len(task_by_scene[scene_id]),
                "stage0_valid_window_count": stage0_by_scene[scene_id],
                "stage2_window_count": stage2_by_scene[scene_id],
                "position_matched_window_count": matched,
                "position_unlocated_window_count": len(scene_overlay) - matched,
                "position_missing_reason_counts": dict(sorted(missing_reasons.items())),
                "valid_rmc_fix_count": len(fixes),
                "route_component_count": len(components),
                "route_distance_km": route_distance_m / 1000.0,
                "route_break_fix_counts": dict(sorted(breaks.items())),
            }
        )
    return result


def _aggregate_environment_summaries(scene_summaries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, int | float]] = {}
    for scene in scene_summaries:
        environment = str(scene.get("environment_class", "UNKNOWN"))
        row = groups.setdefault(
            environment,
            {
                "scene_count": 0,
                "task_count": 0,
                "stage0_valid_window_count": 0,
                "stage2_window_count": 0,
                "position_matched_window_count": 0,
                "position_unlocated_window_count": 0,
                "valid_rmc_fix_count": 0,
                "route_component_count": 0,
                "route_distance_km": 0.0,
            },
        )
        row["scene_count"] += 1
        for field in (
            "task_count", "stage0_valid_window_count", "stage2_window_count",
            "position_matched_window_count", "position_unlocated_window_count",
            "valid_rmc_fix_count", "route_component_count",
        ):
            row[field] += int(scene[field])
        row["route_distance_km"] += float(scene["route_distance_km"])
    return [{"environment_class": key, **groups[key]} for key in sorted(groups)]


def _validate_window_output_keys(
    stage2_windows: Sequence[Mapping[str, Any]],
    trajectory_overlay: Sequence[Mapping[str, Any]],
) -> int:
    expected = {
        (str(row["run_id"]), str(row["window_id"])): (
            str(row["scene_id"]), str(row["prn"]), str(row["tracking_channel"])
        )
        for row in stage2_windows
    }
    actual: dict[tuple[str, str], tuple[str, str, str]] = {}
    for row in trajectory_overlay:
        key = (str(row.get("run_id", "")), str(row.get("window_id", "")))
        if not all(key) or key in actual:
            raise ValueError("trajectory overlay identities are empty or duplicated")
        status = str(row.get("position_status", ""))
        if status not in {"POSITION_MATCHED", "POSITION_MISSING"}:
            raise ValueError("trajectory overlay contains an unknown position status")
        if status == "POSITION_MATCHED":
            if not row.get("position_utc") or not row.get("latitude_deg") or not row.get("longitude_deg"):
                raise ValueError("matched trajectory row is missing observed-position fields")
            if row.get("missing_reason"):
                raise ValueError("matched trajectory row cannot have a missing reason")
        elif not row.get("missing_reason"):
            raise ValueError("unlocated trajectory window needs an explicit missing reason")
        actual[key] = (
            str(row.get("scene_id", "")),
            str(row.get("prn", "")),
            str(row.get("tracking_channel", "")),
        )
    if set(actual) != set(expected):
        raise ValueError("trajectory overlay window identities do not reconcile to Stage2")
    for key, identity in expected.items():
        if actual[key] != identity:
            raise ValueError(f"trajectory window identity metadata mismatch for {key}")
    return len(expected)


def _render_sanitized_report(audit: Mapping[str, Any]) -> str:
    """Render only aggregate allowlisted values; never serialize private fields."""

    counts = audit.get("input_counts", {})
    route = audit.get("route_counts", {})
    summary_rows = audit.get("environment_summary", [])
    route_thresholds = audit.get("route_thresholds", {})
    sensitivity = route_thresholds.get("sensitivity", {}) if isinstance(route_thresholds, dict) else {}
    spatial = audit.get("spatial_dependence", {})
    gsv = audit.get("gsv_geometry_counts", {})
    counts = counts if isinstance(counts, dict) else {}
    route = route if isinstance(route, dict) else {}
    sensitivity = sensitivity if isinstance(sensitivity, dict) else {}
    spatial = spatial if isinstance(spatial, dict) else {}
    gsv = gsv if isinstance(gsv, dict) else {}

    def count(value: Any) -> str:
        if isinstance(value, bool):
            return "UNKNOWN"
        if isinstance(value, int):
            return f"{value:,}"
        if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
            return f"{int(value):,}"
        return "UNKNOWN"

    def distance(value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "UNKNOWN"
        return f"{number:.3f}" if number >= 0 else "UNKNOWN"

    lines = [
        "# Mainline Stage2 trajectory and spatial audit",
        "",
        f"- Audit state: `{ 'PASS' if audit.get('audit_status') == 'PASS' else 'NOT_PASS' }`.",
        f"- Stage0-valid windows: {count(counts.get('stage0_window_count'))}; Stage2-selected windows: {count(counts.get('stage2_window_count'))}; Stage2 paths: {count(counts.get('stage2_path_row_count'))}.",
        f"- Measured GSV elevation matches: {count(gsv.get('matched_count'))}; explicit missing: {count(gsv.get('missing_count'))}.",
        f"- Stage2 windows with measured route position: {count(route.get('position_matched_window_count'))}; unlocated but retained: {count(route.get('position_unlocated_window_count'))}.",
        f"- Valid RMC fixes: {count(route.get('valid_rmc_fix_count'))}; continuity components: {count(route.get('route_component_count'))}; total within-component route distance: {distance(route.get('route_distance_km'))} km.",
        "",
        "| Environment | Scenes | Tasks | Stage2 windows | Located | Unlocated | RMC fixes | Route km |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows if isinstance(summary_rows, list) else []:
        environment = str(row.get("environment_class", "UNKNOWN"))
        if environment not in {"Highway/Open", "Mountain/Valley", "Special Reflective", "Urban"}:
            environment = "OTHER"
        lines.append(
            f"| {environment} | {count(row.get('scene_count'))} | {count(row.get('task_count'))} | {count(row.get('stage2_window_count'))} | {count(row.get('position_matched_window_count'))} | {count(row.get('position_unlocated_window_count'))} | {count(row.get('valid_rmc_fix_count'))} | {distance(row.get('route_distance_km'))} |"
        )
    bin_counts = route.get("candidate_bin_count_by_length_m", {})
    if not isinstance(bin_counts, dict):
        bin_counts = {}
    safe_bin_counts = {key: count(bin_counts.get(key)) for key in ("50", "100", "250")}
    bin_support = route.get("candidate_bin_count_with_stage2_window_support_by_length_m", {})
    if not isinstance(bin_support, dict):
        bin_support = {}
    safe_bin_support = {key: count(bin_support.get(key)) for key in ("50", "100", "250")}
    sensitivity_counts = {
        name: count(item.get("component_count"))
        for name, item in sensitivity.items()
        if name in {"GAP_1_5S", "GAP_2_5S", "GAP_5S", "JUMP_50MPS", "JUMP_80MPS", "JUMP_120MPS"}
        and isinstance(item, dict)
    } if isinstance(sensitivity, dict) else {}
    spatial_statuses = spatial.get("estimate_status_counts", {})
    if not isinstance(spatial_statuses, dict):
        spatial_statuses = {}
    safe_spatial_statuses = {
        key: count(spatial_statuses.get(key))
        for key in ("INSUFFICIENT_SPATIAL_SUPPORT", "STABLE_SCENE_BLOCK_CANDIDATE")
    }
    missing_reasons = route.get("position_missing_reason_counts", {})
    if not isinstance(missing_reasons, dict):
        missing_reasons = {}
    safe_missing_reasons = {
        key: count(missing_reasons.get(key))
        for key in ("OUTSIDE_POSITION_TOLERANCE", "WITHIN_ROUTE_DISCONTINUITY_GAP")
    }
    rmc_diagnostics = route.get("rmc_diagnostics_total", {})
    if not isinstance(rmc_diagnostics, dict):
        rmc_diagnostics = {}
    stable_candidate_count = count(spatial.get("stable_range_candidate_count"))
    lines.extend(
        [
            "",
            f"- Unlocated-window reasons: `{safe_missing_reasons}`.",
            f"- RMC diagnostics: checksum-invalid={count(rmc_diagnostics.get('checksum_invalid_rmc_count'))}, inactive={count(rmc_diagnostics.get('inactive_rmc_count'))}, invalid-time/coordinate={count(rmc_diagnostics.get('invalid_datetime_count'))}/{count(rmc_diagnostics.get('invalid_coordinate_count'))}, duplicate/out-of-order={count(rmc_diagnostics.get('duplicate_timestamp_count'))}/{count(rmc_diagnostics.get('out_of_order_timestamp_count'))}.",
            f"- Route-bin counts (50/100/250 m): `{safe_bin_counts}`; bins with Stage2-window support: `{safe_bin_support}`. They are descriptive candidates, not independent units.",
            f"- Threshold sensitivity component counts: `{sensitivity_counts}`.",
            f"- Spatial dependence: `{safe_spatial_statuses}`; stable_range_candidates={stable_candidate_count}; descriptive only; no independence claim.",
            "- Window matching uses nearest checksum-valid same-scene RMC fix; no interpolation; windows across continuity gaps stay unlocated. Precise coordinates and NMEA paths are kept only in the local ignored audit namespace.",
            "- Task 5 impact: NO. CIR/HDF5 was not accessed. Gate F remains pending; no formal model fitting or model-validation claim is made.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_exclusive_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field, "") for field in fields})


def _audit(project_root: Path, code_root: Path, output_dir: Path) -> dict[str, Any]:
    project_root = project_root.resolve(strict=True)
    code_root = code_root.resolve(strict=True)
    output_dir = output_dir.resolve(strict=True)
    try:
        output_dir.relative_to(project_root)
    except ValueError as error:
        raise ValueError("output namespace must be inside project root") from error
    if not output_dir.is_dir():
        raise ValueError("existing geometry output namespace is required")
    collisions = [name for name in ROUTE_OUTPUT_NAMES if (output_dir / name).exists()]
    if collisions:
        raise FileExistsError(f"route output already exists: {', '.join(collisions)}")

    geometry_audit, verified_inputs, geometry_overlay = _load_geometry_audit(
        project_root, code_root, output_dir
    )
    cohort, tasks, stage0_by_run, stage2_paths, ledger_sha_before = _load_cohort_and_inputs(
        project_root, code_root, geometry_audit, verified_inputs
    )
    tasks_by_run = {str(task["run_id"]): task for task in tasks}
    if set(stage0_by_run) != set(tasks_by_run):
        raise ValueError("Stage0 run identities do not reconcile with cohort")

    rows_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stage2_paths:
        rows_by_run[str(row["run_id"])].append(row)
    stage2_windows = build_stage2_window_index(stage2_paths)
    if _validate_window_overlay_reconciliation(stage2_windows, geometry_overlay) != len(stage2_windows):
        raise ValueError("GSV overlay row count does not reconcile to Stage2 windows")

    scene_audits = geometry_audit.get("scenes")
    if not isinstance(scene_audits, list):
        raise ValueError("geometry audit scene time pins are missing")
    gps_week_by_scene: dict[str, int] = {}
    for scene in scene_audits:
        scene_id = _required_text(scene, "scene_id")
        if scene.get("gps_time_alignment_status") != "VERIFIED":
            raise ValueError(f"geometry audit time alignment is not verified for {scene_id}")
        week = _positive_count(scene.get("gps_week"), label=f"GPS week for {scene_id}", allow_zero=True)
        if scene_id in gps_week_by_scene:
            raise ValueError("duplicate scene time pin in geometry audit")
        gps_week_by_scene[scene_id] = week
    scenes = {str(task["scene_id"]) for task in tasks}
    if set(gps_week_by_scene) != scenes:
        raise ValueError("geometry audit GPS-week scenes do not exactly reconcile to cohort")

    run_rows = [{"run_id": task["run_id"], "scene_id": task["scene_id"]} for task in tasks]
    utc_by_window = build_stage0_utc_index(run_rows, stage0_by_run, gps_week_by_scene)
    stage2_window_keys = {(str(row["run_id"]), str(row["window_id"])) for row in stage2_windows}
    if stage2_window_keys - set(utc_by_window):
        raise ValueError("Stage2 window identities do not reconcile to Stage0 UTC index")

    source_pairs, source_index_path, source_index_sha = _load_scene_sources_for_route(
        project_root, scenes, verified_inputs
    )
    fixes_by_scene: dict[str, list[dict[str, Any]]] = {}
    rmc_diagnostics: dict[str, dict[str, int]] = {}
    base_segmented_by_scene: dict[str, list[dict[str, Any]]] = {}
    for scene_id, (nmea_path, _rinex_path) in sorted(source_pairs.items()):
        fixes, diagnostics = parse_valid_rmc_fixes_with_diagnostics([nmea_path])
        fixes = [{**fix, "scene_id": scene_id} for fix in fixes]
        if not fixes:
            raise ValueError(f"no valid measured RMC fixes for {scene_id}")
        segmented = split_trajectory_components(
            fixes,
            max_gap_seconds=BASE_MAX_GAP_SECONDS,
            jump_speed_mps=BASE_JUMP_SPEED_MPS,
        )
        fixes_by_scene[scene_id] = segmented
        rmc_diagnostics[scene_id] = diagnostics

    trajectory_overlay = build_trajectory_window_overlay(
        stage2_windows, utc_by_window, fixes_by_scene
    )
    if _validate_window_output_keys(stage2_windows, trajectory_overlay) != 7847:
        raise ValueError("trajectory overlay does not preserve all 7,847 Stage2 windows")
    route_segments = build_route_segment_rows(
        trajectory_overlay, [row for rows in fixes_by_scene.values() for row in rows],
        lengths_m=ROUTE_BIN_LENGTHS_M,
    )
    fix_metrics = aggregate_stage2_metrics_by_fix(stage2_paths, trajectory_overlay)
    spatial_summary = summarize_spatial_dependence(fix_metrics, lag_edges_m=LAG_EDGES_M)

    scene_summaries = _scene_route_summaries(
        tasks, stage0_by_run, stage2_windows, trajectory_overlay, fixes_by_scene
    )
    environment_summaries = _aggregate_environment_summaries(scene_summaries)
    route_status_counts = Counter(str(row["position_status"]) for row in trajectory_overlay)
    route_missing_reasons = Counter(
        str(row["missing_reason"])
        for row in trajectory_overlay
        if row["position_status"] != "POSITION_MATCHED"
    )
    route_break_counts: Counter[str] = Counter()
    component_total = 0
    route_distance_km = 0.0
    rmc_total = Counter()
    for scene_id, fixes in fixes_by_scene.items():
        route_break_counts.update(str(row.get("break_reason") or "CONNECTED") for row in fixes)
        components: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in fixes:
            components[str(row["component_id"])].append(row)
        component_total += len(components)
        route_distance_km += sum(
            max(float(row["cumulative_distance_m"]) for row in group) for group in components.values()
        ) / 1000.0
        rmc_total.update(rmc_diagnostics[scene_id])

    bin_count_by_length = {
        str(length): sum(int(row["bin_length_m"]) == length for row in route_segments)
        for length in ROUTE_BIN_LENGTHS_M
    }
    bin_support_by_length = {
        str(length): sum(
            int(row["bin_length_m"]) == length and int(row["stage2_window_count"]) > 0
            for row in route_segments
        )
        for length in ROUTE_BIN_LENGTHS_M
    }
    spatial_status_counts = Counter(str(row["estimate_status"]) for row in spatial_summary)
    spatial_supported_scenes = max((int(row["scene_count"]) for row in spatial_summary), default=0)
    threshold_sensitivity = _route_sensitivity(fixes_by_scene)

    if sha256_file(project_root / STAGE2_LEDGER_REL) != ledger_sha_before:
        raise ValueError("Task 6 Stage2 ledger SHA-256 changed during route audit")
    # Check all route names again immediately before exclusive creation.
    collisions = [name for name in ROUTE_OUTPUT_NAMES if (output_dir / name).exists()]
    if collisions:
        raise FileExistsError(f"route output already exists: {', '.join(collisions)}")

    _write_exclusive_csv(output_dir / TRAJECTORY_OVERLAY_NAME, TRAJECTORY_OVERLAY_FIELDS, trajectory_overlay)
    _write_exclusive_csv(output_dir / ROUTE_SEGMENTS_NAME, ROUTE_SEGMENT_FIELDS, route_segments)
    _write_exclusive_csv(output_dir / SPATIAL_SUMMARY_NAME, SPATIAL_SUMMARY_FIELDS, spatial_summary)

    output_file_audit = {}
    for name in (TRAJECTORY_OVERLAY_NAME, ROUTE_SEGMENTS_NAME, SPATIAL_SUMMARY_NAME):
        path = output_dir / name
        output_file_audit[name] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    audit: dict[str, Any] = {
        "schema_version": "mainline-stage2-trajectory-audit-v1",
        "audit_status": "PASS",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "cohort_id": cohort.get("cohort_id"),
        "cohort_sha256": geometry_audit.get("cohort_sha256"),
        "cohort_task_count": len(tasks),
        "scene_count": len(scenes),
        "geometry_audit_path": _project_rel(project_root, output_dir / GEOMETRY_AUDIT_NAME),
        "geometry_audit_sha256": sha256_file(output_dir / GEOMETRY_AUDIT_NAME),
        "geometry_overlay_sha256": sha256_file(output_dir / GEOMETRY_OVERLAY_NAME),
        "geometry_coverage_sha256": sha256_file(output_dir / GEOMETRY_COVERAGE_NAME),
        "geometry_input_pin_count_verified": len(verified_inputs),
        "scene_source_index_sha256": source_index_sha,
        "stage2_ledger_sha256_before": ledger_sha_before,
        "stage2_ledger_sha256_after": sha256_file(project_root / STAGE2_LEDGER_REL),
        "input_counts": {
            "stage0_window_count": sum(len(rows) for rows in stage0_by_run.values()),
            "stage2_path_row_count": len(stage2_paths),
            "stage2_window_count": len(stage2_windows),
            "stage2_windows_with_stage0_utc": len(stage2_window_keys),
            "stage2_windows_with_geometry_row": len(geometry_overlay),
            "stage2_windows_with_trajectory_row": len(trajectory_overlay),
        },
        "gsv_geometry_counts": {
            "matched_count": int(geometry_audit["input_counts"]["gsv_matched_count"]),
            "missing_count": int(geometry_audit["input_counts"]["missing_count"]),
        },
        "route_counts": {
            "position_matched_window_count": route_status_counts["POSITION_MATCHED"],
            "position_unlocated_window_count": route_status_counts["POSITION_MISSING"],
            "position_missing_reason_counts": dict(sorted(route_missing_reasons.items())),
            "valid_rmc_fix_count": sum(len(rows) for rows in fixes_by_scene.values()),
            "rmc_diagnostics_total": dict(sorted(rmc_total.items())),
            "route_component_count": component_total,
            "route_break_fix_counts": dict(sorted(route_break_counts.items())),
            "route_distance_km": route_distance_km,
            "candidate_bin_count_by_length_m": bin_count_by_length,
            "candidate_bin_count_with_stage2_window_support_by_length_m": bin_support_by_length,
            "candidate_bin_lengths_m": list(ROUTE_BIN_LENGTHS_M),
        },
        "route_thresholds": {
            "position_match_max_delta_seconds": 2.5,
            "base_max_gap_seconds": BASE_MAX_GAP_SECONDS,
            "base_jump_speed_mps": BASE_JUMP_SPEED_MPS,
            "continuity_thresholds_are_audit_ceilings_not_tuned_parameters": True,
            "sensitivity": threshold_sensitivity,
        },
        "spatial_dependence": {
            "summary_row_count": len(spatial_summary),
            "lag_edges_m": list(LAG_EDGES_M),
            "estimate_status_counts": dict(sorted(spatial_status_counts.items())),
            "maximum_scene_support_in_any_metric_lag_band": spatial_supported_scenes,
            "stable_range_candidate_count": sum(
                row.get("estimate_status") == "STABLE_SCENE_BLOCK_CANDIDATE"
                for row in spatial_summary
            ),
            "interpretation": "DESCRIPTIVE_ONLY_NOT_AN_INDEPENDENCE_CLAIM",
        },
        "scene_summaries": scene_summaries,
        "environment_summary": environment_summaries,
        "privacy_and_scope": {
            "precise_coordinates_and_source_record_paths": "LOCAL_ROUTE_OVERLAY_ONLY",
            "raw_nmea_text_in_reports_or_audit_json": False,
            "raw_iq_mat_hdf5_cir_pdp_accessed": False,
            "task5_impact": "NO",
            "gate_f": "PENDING",
            "formal_model_fit": "NOT_PERFORMED",
            "independence_claim": "NOT_MADE",
        },
        "output_files": output_file_audit,
    }
    with (output_dir / TRAJECTORY_AUDIT_NAME).open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return audit


def _load_scene_sources_for_route(
    project_root: Path, scenes: set[str], verified_inputs: Mapping[Path, Mapping[str, Any]]
) -> tuple[dict[str, tuple[Path, Path]], Path, str]:
    run_index_path = (project_root / RUN_INDEX_REL).resolve(strict=True)
    index_pin = verified_inputs.get(run_index_path)
    if index_pin is None or index_pin.get("role") != "scene_source_path_index":
        raise ValueError("SAGE scene source index is not bound to geometry audit")
    rows = _read_csv(run_index_path, label="SAGE scene source index")
    required = {"scene_id", "trajectory_relpath", "rinex_nav_relpath", "context_missing_legacy"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("SAGE scene source index lacks required route fields")
    pairs: dict[str, tuple[Path, Path]] = {}
    for scene_id in sorted(scenes):
        candidates: set[tuple[Path, Path]] = set()
        for row in rows:
            if row.get("scene_id", "").strip() != scene_id:
                continue
            trajectory = row.get("trajectory_relpath", "").strip()
            rinex = row.get("rinex_nav_relpath", "").strip()
            if not trajectory and not rinex:
                continue
            if not trajectory or not rinex:
                raise ValueError(f"incomplete NMEA/RINEX source pair for {scene_id}")
            if row.get("context_missing_legacy", "").strip() == "1":
                continue
            nmea_path = (project_root / trajectory).resolve(strict=True)
            rinex_path = (project_root / rinex).resolve(strict=True)
            for path, role in ((nmea_path, "scene_nmea"), (rinex_path, "scene_rinex_nav")):
                pin = verified_inputs.get(path)
                if pin is None or pin.get("role") != role:
                    raise ValueError(f"scene source not covered by geometry hash pins for {scene_id}")
            candidates.add((nmea_path, rinex_path))
        if len(candidates) != 1:
            raise ValueError(f"expected one pinned NMEA/RINEX source pair for {scene_id}")
        pairs[scene_id] = next(iter(candidates))
    return pairs, run_index_path, str(index_pin["sha256"])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--code-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        output_dir = args.output_dir if args.output_dir.is_absolute() else args.project_root / args.output_dir
        audit = _audit(args.project_root, args.code_root, output_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, csv.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "audit_status": audit["audit_status"],
                "output_dir": str(output_dir.resolve()),
                "input_counts": audit["input_counts"],
                "route_counts": audit["route_counts"],
                "spatial_dependence": audit["spatial_dependence"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
