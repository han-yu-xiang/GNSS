#!/usr/bin/env python3
"""Build a local, row-preserving Stage2/GSV geometry audit.

The runner reads only the frozen Stage0/Stage2 CSVs, the Stage2 ledger,
scene-level NMEA/RINEX sources, and small identity indexes.  It never opens
raw IQ, MAT/HDF5, or CIR payloads and never writes into source namespaces.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.channel_modeling.mainline_stage2_geometry import (  # noqa: E402
    build_gsv_window_overlay,
    build_stage0_utc_index,
    build_stage2_window_index,
    parse_checksum_valid_gps_gsv_files,
    summarize_geometry_coverage,
)
from scripts.channel_modeling import mainline_stage2_geometry as geometry_module  # noqa: E402
from scripts.event_database import align_modeling_context as time_alignment_module  # noqa: E402
from scripts.event_database.align_modeling_context import (  # noqa: E402
    GPS_UTC_LEAP_SECONDS,
    first_rinex_record_date,
    gps_week_for_anchor,
    max_time_origin_error_seconds,
    sha256_file,
)
from scripts.preprocessing.satellite_geometry import parse_rinex_nav_prns  # noqa: E402
from scripts.preprocessing import satellite_geometry as satellite_geometry_module  # noqa: E402


COHORT_REL = Path(
    "dataset_generation_logs/channel_modeling/"
    "mainline_1023_cohort_v1_20261022T082520Z/cohort.json"
)
STAGE2_LEDGER_REL = Path(
    "dataset_generation_logs/channel_modeling/"
    "mainline_1023_model_v1_20261023T135341Z/stage2_ledger.csv"
)
RUN_INDEX_REL = Path(
    "dataset/multipath_event_database/v1/partitions/"
    "ingestion_id=ingestion_20260825_event_path_v1/facts/sage_runs.csv"
)
MAINLINE_COHORT_ID = "mainline_1023_model_v1"
MAINLINE_COHORT_TASK_COUNT = 83
MAINLINE_STAGE2_LEDGER_SHA256 = "bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551"
MAX_TIME_ORIGIN_RESIDUAL_SECONDS = 0.5
OUTPUT_NAMESPACE_PARENT = Path("dataset_generation_logs/channel_modeling")
OUTPUT_NAMESPACE_PATTERN = re.compile(r"^mainline_1023_geometry_route_[0-9]{8}T[0-9]{6}Z$")
OUTPUT_FILES = (
    "geometry_window_overlay.csv",
    "geometry_coverage_summary.csv",
    "geometry_alignment_audit.json",
)
OVERLAY_FIELDS = (
    "run_id",
    "window_id",
    "scene_id",
    "prn",
    "tracking_channel",
    "environment_class",
    "frozen_elevation_group",
    "window_utc",
    "nearest_candidate_utc",
    "nearest_candidate_source_file",
    "nearest_candidate_record_id",
    "candidate_delta_seconds_signed",
    "candidate_delta_seconds_abs",
    "local_cadence_limit_seconds",
    "candidate_cell_status",
    "gsv_source_utc",
    "elevation_deg",
    "azimuth_deg",
    "source_file",
    "status",
    "missing_reason",
)
SUMMARY_FIELDS = (
    "summary_scope",
    "scene_id",
    "environment_class",
    "prn",
    "frozen_elevation_group",
    "run_id",
    "window_count",
    "gsv_matched_count",
    "missing_count",
    "missing_reason_counts",
    "matched_within_0_5s",
    "matched_within_1s",
    "matched_within_2s",
    "matched_within_5s",
    "nmea_available",
    "nmea_file_count",
    "rmc_valid_count",
    "gsv_valid_count",
    "target_prn_in_rinex",
    "gps_time_alignment_status",
    "target_prn_gsv_record_count",
)


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"missing required {key}")
    return text


def _positive_count(value: Any, *, label: str, allow_zero: bool = False) -> int:
    text = "" if value is None else str(value).strip()
    if isinstance(value, bool) or not re.fullmatch(r"(?:0|[1-9][0-9]*)", text):
        raise ValueError(f"invalid {label}: expected canonical integer")
    result = int(text)
    if result < 0 or (result == 0 and not allow_zero):
        raise ValueError(f"invalid {label}: expected {'nonnegative' if allow_zero else 'positive'} integer")
    return result


def _sha256_text(value: Any, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError(f"invalid {label}: expected SHA-256")
    return text


def _relative_file(root: Path, value: Any, *, label: str) -> Path:
    text = _required_text({"path": value}, "path")
    supplied = Path(text)
    candidate = supplied if supplied.is_absolute() else root / supplied
    resolved = candidate.resolve(strict=True)
    root_resolved = root.resolve(strict=True)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as error:
        raise ValueError(f"{label} resolves outside project root") from error
    if not resolved.is_file():
        raise ValueError(f"{label} is not a file")
    return resolved


def _project_rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _validate_runtime_code_root(code_root: Path) -> None:
    resolved_root = code_root.resolve(strict=True)
    if resolved_root != REPO_ROOT.resolve(strict=True):
        raise ValueError("code_root must match the code worktree executing this audit")
    loaded_modules = {
        "geometry helper": geometry_module,
        "GPS time helper": time_alignment_module,
        "NMEA/RINEX parser": satellite_geometry_module,
    }
    for label, module in loaded_modules.items():
        module_path = Path(module.__file__).resolve(strict=True)
        try:
            module_path.relative_to(resolved_root)
        except ValueError as error:
            raise ValueError(f"loaded {label} is outside the declared code worktree") from error


def _validate_private_output_namespace(project_root: Path, output_dir: Path) -> Path:
    root = project_root.resolve(strict=True)
    output = output_dir.resolve(strict=False)
    try:
        relative = output.relative_to(root)
    except ValueError as error:
        raise ValueError("output namespace must be inside project root") from error
    if (
        relative.parent != OUTPUT_NAMESPACE_PARENT
        or not OUTPUT_NAMESPACE_PATTERN.fullmatch(relative.name)
    ):
        raise ValueError("output must use a timestamped mainline_1023_geometry_route private namespace")
    ignored = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--no-index", "--quiet", "--", relative.as_posix()],
        capture_output=True,
        text=True,
        check=False,
    )
    if ignored.returncode != 0:
        raise ValueError("output namespace is not ignored by Git")
    return output


def _audit_path(project_root: Path, code_root: Path, path: Path) -> tuple[str, str]:
    resolved = path.resolve()
    for label, base in (("project_root", project_root), ("code_worktree", code_root)):
        try:
            return label, resolved.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    raise ValueError("input file is outside both declared roots")


def _read_csv(path: Path, *, label: str) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"{label} has no CSV header")
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f"{label} has duplicate CSV header names")
        return list(reader)


def _verify_pinned_file(root: Path, entry: Mapping[str, Any], *, label: str) -> tuple[Path, str]:
    path = _relative_file(root, entry.get("path"), label=label)
    expected = _sha256_text(entry.get("sha256"), label=f"{label} sha256")
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch")
    if "size_bytes" in entry and entry.get("size_bytes") not in (None, ""):
        expected_size = _positive_count(entry["size_bytes"], label=f"{label} size", allow_zero=True)
        if path.stat().st_size != expected_size:
            raise ValueError(f"{label} size mismatch")
    return path, actual


def _validate_cohort(
    root: Path, code_root: Path, cohort: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, tuple[Path, str, str]]]:
    tasks_value = cohort.get("tasks")
    if not isinstance(tasks_value, list) or not tasks_value:
        raise ValueError("cohort tasks must be a nonempty list")
    declared_count = _positive_count(cohort.get("eligible_count"), label="eligible_count")
    if declared_count != len(tasks_value):
        raise ValueError("cohort eligible_count does not reconcile with tasks")
    if cohort.get("cohort_id") == MAINLINE_COHORT_ID and declared_count != MAINLINE_COHORT_TASK_COUNT:
        raise ValueError("frozen mainline cohort must contain exactly 83 tasks")

    source_pins = cohort.get("source_sha256")
    if not isinstance(source_pins, dict) or not source_pins:
        raise ValueError("cohort source_sha256 pins are required")
    seen_pin_paths: dict[str, str] = {}
    verified_source_pins: dict[str, tuple[Path, str, str]] = {}
    for name, entry in sorted(source_pins.items()):
        if not isinstance(entry, dict):
            raise ValueError(f"invalid cohort source pin: {name}")
        pin_text = _required_text(entry, "path")
        pin_candidate = Path(pin_text)
        pin_root = (
            code_root
            if not pin_candidate.is_absolute()
            and pin_candidate.parts
            and pin_candidate.parts[0].casefold() == "scripts"
            else root
        )
        path, digest = _verify_pinned_file(pin_root, entry, label=f"cohort source {name}")
        root_label, relative = _audit_path(root, code_root, path)
        rel = f"{root_label}/{relative}".casefold()
        prior = seen_pin_paths.setdefault(rel, digest)
        if prior != digest:
            raise ValueError(f"conflicting source hashes for {name}")
        verified_source_pins[name] = (path, digest, root_label)

    normalized: list[dict[str, Any]] = []
    seen_run_ids: set[str] = set()
    for raw_task in tasks_value:
        if not isinstance(raw_task, dict):
            raise ValueError("cohort task must be an object")
        task = dict(raw_task)
        run_id = _required_text(task, "run_id")
        scene_id = _required_text(task, "scene_id")
        prn = _required_text(task, "prn").upper()
        if not re.fullmatch(r"G(?:0[1-9]|[12][0-9]|3[0-2])", prn):
            raise ValueError(f"invalid GPS PRN for {run_id}")
        channel_value = task.get("tracking_channel")
        channel = _positive_count(channel_value, label=f"tracking_channel for {run_id}", allow_zero=True)
        if channel > 99:
            raise ValueError(f"invalid tracking_channel for {run_id}")
        if run_id in seen_run_ids:
            raise ValueError(f"duplicate cohort run_id: {run_id}")
        seen_run_ids.add(run_id)
        stage_csvs = task.get("stage_csvs")
        if not isinstance(stage_csvs, dict):
            raise ValueError(f"missing stage_csvs for {run_id}")
        stage0_entry = stage_csvs.get("stage0_valid_windows")
        stage2_entry = stage_csvs.get("stage2_selected_paths")
        if not isinstance(stage0_entry, dict) or not isinstance(stage2_entry, dict):
            raise ValueError(f"missing Stage0/Stage2 source pins for {run_id}")
        stage0_path, stage0_sha = _verify_pinned_file(root, stage0_entry, label=f"Stage0 {run_id}")
        stage2_path, stage2_sha = _verify_pinned_file(root, stage2_entry, label=f"Stage2 source {run_id}")
        counts = task.get("stage_counts_from_gate_a")
        if not isinstance(counts, dict):
            raise ValueError(f"missing Gate A stage counts for {run_id}")
        task["run_id"] = run_id
        task["scene_id"] = scene_id
        task["prn"] = prn
        task["tracking_channel"] = str(channel)
        task["stage0_path"] = stage0_path
        task["stage0_sha256"] = stage0_sha
        task["stage2_source_path"] = stage2_path
        task["stage2_source_sha256"] = stage2_sha
        task["expected_stage0_windows"] = _positive_count(
            counts.get("stage0_valid_40ms_windows"), label=f"Stage0 count for {run_id}", allow_zero=True
        )
        task["expected_stage2_paths"] = _positive_count(
            counts.get("stage2_selected_path_count"), label=f"Stage2 path count for {run_id}", allow_zero=True
        )
        normalized.append(task)
    return normalized, verified_source_pins


def _load_scene_sources(root: Path, scene_ids: set[str]) -> tuple[dict[str, tuple[Path, Path]], Path, str, dict[str, int]]:
    index_path = _relative_file(root, RUN_INDEX_REL.as_posix(), label="versioned SAGE run index")
    index_sha = sha256_file(index_path)
    index_rows = _read_csv(index_path, label="versioned SAGE run index")
    required = {"scene_id", "trajectory_relpath", "rinex_nav_relpath", "context_missing_legacy"}
    if not index_rows or not required.issubset(index_rows[0]):
        raise ValueError("versioned SAGE run index is missing required source-path columns")

    sources: dict[str, tuple[Path, Path]] = {}
    indexed_row_counts: dict[str, int] = {}
    for scene_id in sorted(scene_ids):
        scene_rows = [row for row in index_rows if row.get("scene_id", "").strip() == scene_id]
        candidates: set[tuple[Path, Path]] = set()
        usable_rows = 0
        for row in scene_rows:
            trajectory_text = row.get("trajectory_relpath", "").strip()
            rinex_text = row.get("rinex_nav_relpath", "").strip()
            if not trajectory_text and not rinex_text:
                continue
            if not trajectory_text or not rinex_text:
                raise ValueError(f"incomplete NMEA/RINEX path pair in source index for {scene_id}")
            if row.get("context_missing_legacy", "").strip() == "1":
                continue
            trajectory = _relative_file(root, trajectory_text, label=f"NMEA source for {scene_id}")
            rinex = _relative_file(root, rinex_text, label=f"RINEX source for {scene_id}")
            candidates.add((trajectory, rinex))
            usable_rows += 1
        if len(candidates) != 1:
            raise ValueError(
                f"expected one scene-level NMEA/RINEX source pair for {scene_id}, found {len(candidates)}"
            )
        sources[scene_id] = next(iter(candidates))
        indexed_row_counts[scene_id] = usable_rows
    return sources, index_path, index_sha, indexed_row_counts


def _scene_task_rows(tasks: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    by_scene: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for task in tasks:
        by_scene[str(task["scene_id"])].append(task)
    return by_scene


def _timestamp_origin_audit(
    tasks_by_scene: Mapping[str, Sequence[Mapping[str, Any]]],
    stage0_by_run: Mapping[str, Sequence[Mapping[str, str]]],
    utc_by_window: Mapping[tuple[str, str], datetime],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for scene_id, tasks in sorted(tasks_by_scene.items()):
        origins: list[datetime] = []
        for task in tasks:
            run_id = str(task["run_id"])
            for row in stage0_by_run[run_id]:
                window_id = _required_text(row, "window_id")
                try:
                    recording_time = float(row["recording_time_s"])
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(f"invalid recording_time_s in Stage0 {run_id}") from error
                if not math.isfinite(recording_time) or recording_time < 0:
                    raise ValueError(f"invalid recording_time_s in Stage0 {run_id}")
                utc = utc_by_window[(run_id, window_id)]
                origins.append(utc - timedelta(seconds=recording_time))
        if not origins:
            raise ValueError(f"no Stage0 time origins for {scene_id}")
        center = datetime.fromtimestamp(
            median(value.timestamp() for value in origins), tz=timezone.utc
        )
        max_residual = max_time_origin_error_seconds(origins, center)
        if max_residual > MAX_TIME_ORIGIN_RESIDUAL_SECONDS:
            raise ValueError(
                f"GPS time-origin residual exceeds {MAX_TIME_ORIGIN_RESIDUAL_SECONDS}s for {scene_id}"
            )
        result[scene_id] = {
            "recording_time_origin_utc_median": center.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "max_time_origin_residual_seconds": max_residual,
            "maximum_allowed_time_origin_residual_seconds": MAX_TIME_ORIGIN_RESIDUAL_SECONDS,
            "gps_time_alignment_status": "VERIFIED",
            "time_origin_sample_count": len(origins),
        }
    return result


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field, "") for field in fields})


def _audit(root: Path, code_root: Path, output_dir: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    code_root = code_root.resolve(strict=True)
    _validate_runtime_code_root(code_root)
    output_resolved = _validate_private_output_namespace(root, output_dir)
    if output_resolved.exists():
        raise FileExistsError("output directory must not exist before the audit")

    cohort_path = _relative_file(root, COHORT_REL.as_posix(), label="frozen cohort")
    cohort_sha = sha256_file(cohort_path)
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    if not isinstance(cohort, dict):
        raise ValueError("frozen cohort must be a JSON object")
    tasks, verified_source_pins = _validate_cohort(root, code_root, cohort)
    task_by_run = {str(task["run_id"]): task for task in tasks}
    scenes = {str(task["scene_id"]) for task in tasks}

    ledger_path = _relative_file(root, STAGE2_LEDGER_REL.as_posix(), label="Task 6 Stage2 ledger")
    ledger_sha_before = sha256_file(ledger_path)
    if cohort.get("cohort_id") == MAINLINE_COHORT_ID and ledger_sha_before != MAINLINE_STAGE2_LEDGER_SHA256:
        raise ValueError("frozen Task 6 Stage2 ledger SHA-256 differs from the approved pin")
    ledger_rows = _read_csv(ledger_path, label="Task 6 Stage2 ledger")
    if not ledger_rows:
        raise ValueError("Task 6 Stage2 ledger is empty")
    ledger_fields = set(ledger_rows[0])
    required_ledger_fields = {
        "run_id", "scene_id", "prn", "tracking_channel", "environment_class",
        "elevation_group", "window_id", "path_id", "source_stage2_csv_sha256",
    }
    if not required_ledger_fields.issubset(ledger_fields):
        raise ValueError("Task 6 Stage2 ledger lacks required identity/provenance columns")
    ledger_run_ids = {row.get("run_id", "").strip() for row in ledger_rows}
    if ledger_run_ids != set(task_by_run):
        raise ValueError("Task 6 ledger run IDs do not exactly reconcile to frozen cohort")

    rows_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in ledger_rows:
        run_id = _required_text(row, "run_id")
        task = task_by_run[run_id]
        identity_fields = {
            "scene_id": str(task["scene_id"]),
            "prn": str(task["prn"]),
            "tracking_channel": str(task["tracking_channel"]),
            "environment_class": str(task.get("environment_class", "")).strip(),
            "elevation_group": str(task.get("elevation_group", "MISSING")).strip() or "MISSING",
        }
        for field, expected in identity_fields.items():
            actual = str(row.get(field, "")).strip()
            if actual != expected:
                raise ValueError(f"Stage2 ledger {field} conflicts with cohort for {run_id}")
        if str(row.get("source_stage2_csv_sha256", "")).strip().lower() != str(task["stage2_source_sha256"]).lower():
            raise ValueError(f"Stage2 source SHA conflicts with cohort for {run_id}")
        rows_by_run[run_id].append(row)
    for run_id, task in task_by_run.items():
        if len(rows_by_run[run_id]) != int(task["expected_stage2_paths"]):
            raise ValueError(f"Stage2 path-row count mismatch for {run_id}")

    stage0_by_run: dict[str, list[dict[str, str]]] = {}
    input_files: dict[str, dict[str, Any]] = {}
    for label, path, digest in (("cohort", cohort_path, cohort_sha), ("stage2_ledger", ledger_path, ledger_sha_before)):
        input_files[_project_rel(root, path)] = {
            "sha256": digest,
            "size_bytes": path.stat().st_size,
            "role": label,
        }
    for name, (path, digest, root_label) in verified_source_pins.items():
        _, relative = _audit_path(root, code_root, path)
        input_files[f"{root_label}/{relative}"] = {
            "sha256": digest,
            "size_bytes": path.stat().st_size,
            "role": f"cohort_source_pin:{name}",
        }
    runner_path = Path(__file__).resolve(strict=True)
    software_pins: dict[str, dict[str, Any]] = {}
    for name, path in (
        ("audit_runner", runner_path),
        ("geometry_identity_helper", Path(geometry_module.__file__).resolve(strict=True)),
        ("gps_time_helper", Path(time_alignment_module.__file__).resolve(strict=True)),
        ("nmea_rinex_parser", Path(satellite_geometry_module.__file__).resolve(strict=True)),
    ):
        root_label, relative = _audit_path(root, code_root, path)
        digest = sha256_file(path)
        software_pins[name] = {"root": root_label, "path": relative, "sha256": digest}
        input_files[f"{root_label}/{relative}"] = {
            "sha256": digest,
            "size_bytes": path.stat().st_size,
            "role": f"audit_software:{name}",
        }
    for task in tasks:
        run_id = str(task["run_id"])
        stage0_path = Path(task["stage0_path"])
        stage0_rows = _read_csv(stage0_path, label=f"Stage0 {run_id}")
        if len(stage0_rows) != int(task["expected_stage0_windows"]):
            raise ValueError(f"Stage0 row count mismatch for {run_id}")
        stage0_by_run[run_id] = stage0_rows
        stage0_ids = {_required_text(row, "window_id") for row in stage0_rows}
        task_window_ids = {row["window_id"] for row in rows_by_run[run_id]}
        if not task_window_ids.issubset(stage0_ids):
            raise ValueError(f"Stage2 ledger references window absent from Stage0 for {run_id}")
        for role, path, digest in (
            ("stage0", stage0_path, str(task["stage0_sha256"])),
            ("stage2_task_source", Path(task["stage2_source_path"]), str(task["stage2_source_sha256"])),
        ):
            input_files[_project_rel(root, path)] = {
                "sha256": digest,
                "size_bytes": path.stat().st_size,
                "role": role,
            }

    source_pairs, run_index_path, run_index_sha, indexed_row_counts = _load_scene_sources(root, scenes)
    input_files[_project_rel(root, run_index_path)] = {
        "sha256": run_index_sha,
        "size_bytes": run_index_path.stat().st_size,
        "role": "scene_source_path_index",
    }

    records_by_scene_prn: dict[tuple[str, str], list[Any]] = {}
    gps_week_by_scene: dict[str, int] = {}
    scene_audits: list[dict[str, Any]] = []
    task_sources: list[dict[str, str]] = []
    source_rows_by_scene = _scene_task_rows(tasks)
    rinex_prns_by_scene: dict[str, set[str]] = {}
    nmea_by_scene: dict[str, Path] = {}
    rinex_by_scene: dict[str, Path] = {}
    for scene_id, (nmea_path, rinex_path) in sorted(source_pairs.items()):
        nmea_by_scene[scene_id] = nmea_path
        rinex_by_scene[scene_id] = rinex_path
        nmea_sha = sha256_file(nmea_path)
        rinex_sha = sha256_file(rinex_path)
        input_files[_project_rel(root, nmea_path)] = {
            "sha256": nmea_sha,
            "size_bytes": nmea_path.stat().st_size,
            "role": "scene_nmea",
        }
        input_files[_project_rel(root, rinex_path)] = {
            "sha256": rinex_sha,
            "size_bytes": rinex_path.stat().st_size,
            "role": "scene_rinex_nav",
        }
        records, prn_counts, diagnostics = parse_checksum_valid_gps_gsv_files(
            [nmea_path], source_root=root
        )
        anchor_text = str(diagnostics.get("first_valid_rmc_utc", ""))
        if not anchor_text:
            raise ValueError(f"no checksum-valid active RMC anchor for {scene_id}")
        anchor = datetime.fromisoformat(anchor_text.replace("Z", "+00:00"))
        rinex_date = first_rinex_record_date(rinex_path)
        if anchor.date() != rinex_date:
            raise ValueError(f"NMEA/RINEX calendar mismatch for {scene_id}")
        gps_week = gps_week_for_anchor(anchor)
        gps_week_by_scene[scene_id] = gps_week
        rinex_prns = parse_rinex_nav_prns([rinex_path])
        if not rinex_prns:
            raise ValueError(f"RINEX has no GPS PRN inventory for {scene_id}")
        rinex_prns_by_scene[scene_id] = rinex_prns
        by_prn: dict[str, list[Any]] = defaultdict(list)
        for record in records:
            by_prn[record.prn].append(record)
        for prn, prn_records in by_prn.items():
            records_by_scene_prn[(scene_id, prn)] = prn_records
        scene_audits.append(
            {
                "scene_id": scene_id,
                "nmea_path": _project_rel(root, nmea_path),
                "nmea_sha256": nmea_sha,
                "nmea_size_bytes": nmea_path.stat().st_size,
                "rinex_nav_path": _project_rel(root, rinex_path),
                "rinex_nav_sha256": rinex_sha,
                "rinex_nav_size_bytes": rinex_path.stat().st_size,
                "source_index_usable_row_count": indexed_row_counts[scene_id],
                "first_valid_rmc_utc": anchor_text,
                "rinex_first_record_date": rinex_date.isoformat(),
                "gps_week": gps_week,
                "gps_utc_leap_seconds": GPS_UTC_LEAP_SECONDS,
                "gps_time_alignment_status": "VERIFIED",
                "gps_prn_inventory_count": len(rinex_prns),
                "nmea_parser_diagnostics": diagnostics,
                "valid_gps_gsv_observation_count": len(records),
                "valid_gps_gsv_counts_by_prn": {key: prn_counts[key] for key in sorted(prn_counts)},
            }
        )
        for task in source_rows_by_scene[scene_id]:
            target_prn = str(task["prn"])
            task_sources.append(
                {
                    "run_id": str(task["run_id"]),
                    "scene_id": scene_id,
                    "environment_class": str(task.get("environment_class", "")).strip(),
                    "prn": target_prn,
                    "frozen_elevation_group": str(task.get("elevation_group", "MISSING")).strip() or "MISSING",
                    "nmea_available": "YES",
                    "nmea_file_count": "1",
                    "rmc_valid_count": str(diagnostics["valid_rmc_count"]),
                    "gsv_valid_count": str(prn_counts[target_prn]),
                    "target_prn_in_rinex": "YES" if target_prn in rinex_prns else "NO",
                    "gps_time_alignment_status": "VERIFIED",
                    "target_prn_gsv_record_count": str(sum(record.prn == target_prn for record in records)),
                }
            )

    run_rows = [{"run_id": str(task["run_id"]), "scene_id": str(task["scene_id"])} for task in tasks]
    utc_by_window = build_stage0_utc_index(run_rows, stage0_by_run, gps_week_by_scene)
    stage2_paths = [row for task in tasks for row in rows_by_run[str(task["run_id"])]]
    stage2_windows = build_stage2_window_index(stage2_paths)
    stage2_window_keys = {(row["run_id"], row["window_id"]) for row in stage2_windows}
    if stage2_window_keys - set(utc_by_window):
        raise ValueError("Stage2 window identities do not reconcile to Stage0 UTC index")
    overlay = build_gsv_window_overlay(stage2_windows, utc_by_window, records_by_scene_prn)
    if len(overlay) != len(stage2_windows):
        raise ValueError("geometry overlay row count does not reconcile to Stage2 windows")
    coverage = summarize_geometry_coverage(overlay, task_sources)
    if len({(row["run_id"], row["window_id"]) for row in overlay}) != len(overlay):
        raise ValueError("duplicate output overlay window identity")

    origin_audits = _timestamp_origin_audit(source_rows_by_scene, stage0_by_run, utc_by_window)
    for scene in scene_audits:
        scene.update(origin_audits[scene["scene_id"]])
    ledger_sha_after = sha256_file(ledger_path)
    if ledger_sha_after != ledger_sha_before:
        raise ValueError("Task 6 Stage2 ledger changed during geometry audit")

    stage0_window_count = sum(len(rows) for rows in stage0_by_run.values())
    source_pin_audit = {}
    for name, (pin_path, digest, root_label) in sorted(verified_source_pins.items()):
        _, relative = _audit_path(root, code_root, pin_path)
        source_pin_audit[name] = {
            "root": root_label,
            "path": relative,
            "sha256": digest,
        }
    total_coverage = next(row for row in coverage if row["summary_scope"] == "TOTAL")
    audit: dict[str, Any] = {
        "schema_version": "mainline-stage2-gsv-geometry-audit-v1",
        "audit_status": "PASS",
        "cohort_id": cohort.get("cohort_id"),
        "cohort_sha256": cohort_sha,
        "cohort_task_count": len(tasks),
        "scene_count": len(scenes),
        "stage2_ledger_path": _project_rel(root, ledger_path),
        "stage2_ledger_sha256_before": ledger_sha_before,
        "stage2_ledger_sha256_after": ledger_sha_after,
        "stage2_ledger_sha256_pin_enforced": cohort.get("cohort_id") == MAINLINE_COHORT_ID,
        "source_index_path": _project_rel(root, run_index_path),
        "source_index_sha256": run_index_sha,
        "audit_software": software_pins,
        "cohort_source_pins": source_pin_audit,
        "input_counts": {
            "stage0_window_count": stage0_window_count,
            "stage2_path_row_count": len(stage2_paths),
            "stage2_window_count": len(stage2_windows),
            "overlay_row_count": len(overlay),
            "gsv_matched_count": int(total_coverage["gsv_matched_count"]),
            "missing_count": int(total_coverage["missing_count"]),
        },
        "matching_tolerance_sensitivity_seconds": [0.5, 1.0, 2.0, 5.0],
        "matching_policy": {
            "elevation_source": "checksum-valid active-RMC-timestamped GPS GPGSV only",
            "identity": "same scene_id and exact GPS PRN; run_id/window_id retained for output identity",
            "timestamp": "Stage0 GPS TOW converted with existing project GPS week/leap-second helper",
            "time_origin_max_residual_seconds": MAX_TIME_ORIGIN_RESIDUAL_SECONDS,
            "time_origin_residual_exceeding_limit": "audit fails closed before output creation",
            "missing_windows_preserved": True,
            "rinex_use": "GPS PRN inventory cross-check only; no ephemeris geometry recomputation",
            "coordinate_or_raw_nmea_exported": False,
        },
        "input_files": {key: input_files[key] for key in sorted(input_files)},
        "scenes": scene_audits,
    }

    output_resolved.mkdir(parents=True, exist_ok=False)
    _write_csv(output_resolved / OUTPUT_FILES[0], OVERLAY_FIELDS, overlay)
    _write_csv(output_resolved / OUTPUT_FILES[1], SUMMARY_FIELDS, coverage)
    (output_resolved / OUTPUT_FILES[2]).write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return audit


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--code-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        output_dir = args.output_dir
        if not output_dir.is_absolute():
            output_dir = args.project_root / output_dir
        audit = _audit(args.project_root, args.code_root, output_dir)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, csv.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    counts = audit["input_counts"]
    print(
        json.dumps(
            {
                "audit_status": audit["audit_status"],
                "output_dir": str(output_dir.resolve()),
                "cohort_task_count": audit["cohort_task_count"],
                "scene_count": audit["scene_count"],
                **counts,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
