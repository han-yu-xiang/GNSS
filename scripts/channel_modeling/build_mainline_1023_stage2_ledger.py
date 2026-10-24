#!/usr/bin/env python3
"""Build a read-only, all-Stage2-path Mainline ledger from the frozen cohort.

This tool reads only the pinned Manifest/Summary/cohort/audit and Stage2/3/4
CSV text. It does not open raw IQ, MAT, HDF5, CIR, or complex-alpha payloads.
The Stage2 MPC flag alone controls candidate inclusion; later-stage labels are
annotations only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class LedgerError(RuntimeError):
    """A fail-closed input, identity, or conservation error."""


@dataclass(frozen=True)
class ExpectedCounts:
    cohort: int = 83
    excluded: int = 6
    stage2: int = 16_761
    direct: int = 7_847
    mpc: int = 8_914
    stage3_rows: int = 8_914
    stage3_persistent: int = 2_228
    stage4_confirmed: int = 120
    missing_elevation: int = 9


DEFAULT_EXPECTED = ExpectedCounts()
EXPECTED_COHORT_SHA256 = "287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229"
DEFAULT_STAGE4_SUMMARY_PIN_MANIFEST = (
    "reports/data_consolidation_20261003/mainline_1023_model_v1/"
    "stage4_joint_summary_sha256_pins_20261023.json"
)
EXPECTED_STAGE4_SUMMARY_PIN_MANIFEST_SHA256 = (
    "32c10789efefe4e87cabee4ac8978cd36a4a132f4d3b5640c8e4b8b0851a635d"
)
STAGE2_REQUIRED = (
    "window_id",
    "recording_time_s",
    "selected_L",
    "path_id",
    "is_multipath",
    "delay_samples",
    "excess_delay_samples",
    "excess_delay_chips",
    "excess_path_length_m",
    "doppler_hz",
    "doppler_offset_hz",
    "relative_power_db",
)
STAGE3_REQUIRED = (
    "center_window_id",
    "multipath_id",
    "persistence_pass",
    "matched_window_count",
    "longest_consecutive_count",
)
STAGE4_REQUIRED = ("center_window_id", "path_id", "is_multipath")
STAGE4_PATH_REQUIRED = (*STAGE4_REQUIRED, "joint_selected_L")
STAGE4_SUMMARY_REQUIRED = ("center_window_id", "joint_valid", "joint_selected_L")
HASH_PATTERN_LENGTH = 64
MAX_STAGE_CSV_BYTES = 64 * 1024 * 1024


def _fail(message: str) -> None:
    raise LedgerError(message)


def _project_path(root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        _fail(f"{label}: missing relative path")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        _fail(f"{label}: path escapes project root: {relative}")
    if not candidate.is_file():
        _fail(f"{label}: file missing: {candidate}")
    return candidate


def _project_directory(root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        _fail(f"{label}: missing relative path")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        _fail(f"{label}: path escapes project root: {relative}")
    if not candidate.is_dir():
        _fail(f"{label}: directory missing: {candidate}")
    return candidate


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_pinned_bytes(root: Path, relative: str, expected_sha: str, label: str) -> tuple[Path, bytes]:
    if not isinstance(expected_sha, str) or len(expected_sha) != HASH_PATTERN_LENGTH:
        _fail(f"{label}: malformed SHA-256 pin")
    path = _project_path(root, relative, label)
    try:
        data = path.read_bytes()
    except OSError as exc:
        _fail(f"{label}: read failed: {path}: {exc}")
    actual = _sha256_bytes(data)
    if actual.lower() != expected_sha.lower():
        _fail(f"{label}: SHA-256 mismatch for {path}: expected {expected_sha}, got {actual}")
    return path, data


def _read_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(f"{label}: invalid JSON: {exc}")
    if not isinstance(value, dict):
        _fail(f"{label}: expected a JSON object")
    return value


def _read_csv_bytes(data: bytes, label: str, required: Iterable[str]) -> tuple[list[str], list[dict[str, str]]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        _fail(f"{label}: CSV is not UTF-8: {exc}")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = reader.fieldnames
    if not headers:
        _fail(f"{label}: CSV has no header")
    if len(headers) != len(set(headers)):
        _fail(f"{label}: duplicate CSV header")
    missing = [column for column in required if column not in headers]
    if missing:
        _fail(f"{label}: missing columns: {', '.join(missing)}")
    rows: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            _fail(f"{label}: row {row_number} has more fields than its header")
        rows.append({key: (value or "").strip() for key, value in row.items() if key is not None})
    return headers, rows


def _as_int(value: str, label: str) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        _fail(f"{label}: expected integer, got {value!r}")
    if not math.isfinite(number) or not number.is_integer():
        _fail(f"{label}: expected finite integer, got {value!r}")
    return int(number)


def _as_finite(value: str, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        _fail(f"{label}: expected numeric value, got {value!r}")
    if not math.isfinite(number):
        _fail(f"{label}: non-finite Stage2 value {value!r}")
    return number


def _as_binary(value: str, label: str) -> int:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes"}:
        return 1
    if normalized in {"0", "false", "no"}:
        return 0
    _fail(f"{label}: expected binary value, got {value!r}")


def _validate_elevation(task: dict[str, Any], run_id: str) -> tuple[str, str, str]:
    group = task.get("elevation_group")
    mean = task.get("mean_elevation_deg")
    if group == "MISSING":
        if mean not in (None, ""):
            _fail(f"{run_id}: missing elevation group has a non-missing mean")
        return "MISSING", "", "SUMMARY_MISSING"
    if group not in {"High", "Mid", "Low"}:
        _fail(f"{run_id}: unknown elevation group {group!r}")
    if mean in (None, ""):
        return str(group), "", "NOT_AVAILABLE_IN_FROZEN_COHORT"
    value = _as_finite(str(mean), f"{run_id}.mean_elevation_deg")
    return str(group), format(value, ".15g"), "AVAILABLE"


def _load_source_pins(
    project_root: Path,
    source_root: Path,
    cohort: dict[str, Any],
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    pins = cohort.get("source_sha256")
    if not isinstance(pins, dict):
        _fail("cohort: source_sha256 must be an object")
    required = {"manifest", "summary", "gate_a_audit_json", "gate_a_eligible_runs"}
    if not required.issubset(pins):
        _fail(f"cohort: missing source pins: {', '.join(sorted(required - set(pins)))}")
    observed: dict[str, str] = {}
    contents: dict[str, dict[str, Any]] = {}
    for key, pin in pins.items():
        if not isinstance(pin, dict):
            _fail(f"cohort: malformed source pin {key}")
        relative = pin.get("path", "")
        parts = Path(relative).parts if isinstance(relative, str) else ()
        pin_root = source_root if parts and parts[0].lower() in {"scripts", "docs"} else project_root
        path, data = _read_pinned_bytes(pin_root, relative, pin.get("sha256", ""), key)
        observed[key] = _sha256_bytes(data)
        if key in {"gate_a_audit_json", "gate_a_eligible_runs"}:
            contents[key] = {"path": path, "data": data}
    return observed, contents


def _load_stage4_summary_pins(
    source_root: Path,
    cohort_sha256: str,
    tasks: list[dict[str, Any]],
) -> tuple[Path, str, dict[str, dict[str, str]]]:
    path, data = _read_pinned_bytes(
        source_root,
        DEFAULT_STAGE4_SUMMARY_PIN_MANIFEST,
        EXPECTED_STAGE4_SUMMARY_PIN_MANIFEST_SHA256,
        "Stage4 summary pin manifest",
    )
    manifest = _read_json_bytes(data, "Stage4 summary pin manifest")
    if manifest.get("schema_version") != 1:
        _fail("Stage4 summary pin manifest has an unsupported schema_version")
    if str(manifest.get("cohort_sha256", "")).lower() != cohort_sha256.lower():
        _fail("Stage4 summary pin manifest is bound to a different cohort SHA-256")
    if manifest.get("task_count") != len(tasks):
        _fail("Stage4 summary pin manifest task_count does not match the cohort")
    entries = manifest.get("stage4_joint_summary_sha256_by_run_id")
    if not isinstance(entries, dict):
        _fail("Stage4 summary pin manifest has no run_id pin map")
    task_ids = {str(task.get("run_id", "")) for task in tasks}
    if set(entries) != task_ids:
        _fail("Stage4 summary pin run_id set does not exactly match the cohort")

    validated: dict[str, dict[str, str]] = {}
    for task in tasks:
        run_id = str(task["run_id"])
        entry = entries.get(run_id)
        if not isinstance(entry, dict):
            _fail(f"{run_id}: malformed Stage4 summary pin")
        expected_path = (Path(str(task.get("output_namespace", ""))) / "stage4_joint_summary.csv").as_posix()
        relative_path = entry.get("path")
        digest = entry.get("sha256")
        if relative_path != expected_path:
            _fail(f"{run_id}: Stage4 summary pin path does not match its exact output namespace")
        if not isinstance(digest, str) or len(digest) != HASH_PATTERN_LENGTH:
            _fail(f"{run_id}: malformed Stage4 summary SHA-256 pin")
        validated[run_id] = {"path": relative_path, "sha256": digest.lower()}
    return path, _sha256_bytes(data), validated


def _validate_cohort_and_audit(
    root: Path,
    cohort: dict[str, Any],
    pin_contents: dict[str, dict[str, Any]],
    expected: ExpectedCounts,
) -> tuple[dict[str, Any], list[dict[str, str]], set[str]]:
    tasks = cohort.get("tasks")
    excluded = cohort.get("excluded")
    if not isinstance(tasks, list) or len(tasks) != expected.cohort:
        _fail(f"cohort: expected {expected.cohort} task rows")
    if not isinstance(excluded, list) or len(excluded) != expected.excluded:
        _fail(f"cohort: expected {expected.excluded} excluded identities")
    if cohort.get("eligible_count") != expected.cohort or cohort.get("excluded_count") != expected.excluded:
        _fail("cohort: eligible/excluded header counts do not match the frozen scope")

    audit = _read_json_bytes(pin_contents["gate_a_audit_json"]["data"], "Gate A audit")
    if audit.get("audit_status") != "PASS":
        _fail("Gate A audit is not PASS")
    if audit.get("eligible_count") != expected.cohort or audit.get("excluded_count") != expected.excluded:
        _fail("Gate A audit cohort counts do not match the frozen scope")
    aggregate = audit.get("stage_aggregate_counts")
    if not isinstance(aggregate, dict):
        _fail("Gate A audit has no stage_aggregate_counts")
    expected_audit = {
        "stage2_selected_path_count": expected.stage2,
        "direct_path_count": expected.direct,
        "stage2_mpc_count": expected.mpc,
        "stage3_persistence_row_count": expected.stage3_rows,
        "stage3_persistent_mpc_count": expected.stage3_persistent,
        "stage4_confirmed_mpc_count": expected.stage4_confirmed,
    }
    for key, value in expected_audit.items():
        if aggregate.get(key) != value:
            _fail(f"Gate A audit {key}={aggregate.get(key)!r}, expected {value}")

    headers, eligible_rows = _read_csv_bytes(
        pin_contents["gate_a_eligible_runs"]["data"],
        "Gate A eligible_runs.csv",
        ("run_id", "scene_id", "prn", "tracking_channel", "execution_status"),
    )
    del headers
    eligible: dict[str, dict[str, str]] = {}
    for row in eligible_rows:
        run_id = row["run_id"]
        if not run_id or run_id in eligible:
            _fail(f"Gate A eligible list has an empty or duplicate run_id: {run_id!r}")
        eligible[run_id] = row
    if set(eligible) != {task.get("run_id") for task in tasks}:
        _fail("cohort run_id set does not exactly equal Gate A eligible run_id set")

    excluded_ids: set[str] = set()
    for item in excluded:
        run_id = item.get("run_id") if isinstance(item, dict) else item
        if not isinstance(run_id, str) or not run_id or run_id in excluded_ids:
            _fail("cohort has an empty or duplicate excluded run_id")
        excluded_ids.add(run_id)
    if excluded_ids.intersection(eligible):
        _fail("cohort eligible and excluded identity sets overlap")

    seen_keys: set[tuple[str, str, int]] = set()
    elevation_missing_ids: set[str] = set()
    status_counts: Counter[str] = Counter()
    for task in tasks:
        run_id = task.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            _fail("cohort contains a task without run_id")
        key = (run_id, str(task.get("scene_id", "")), _as_int(str(task.get("tracking_channel", "")), f"{run_id}.tracking_channel"))
        if key in seen_keys:
            _fail(f"cohort has duplicate task identity {key}")
        seen_keys.add(key)
        row = eligible[run_id]
        if (
            row["scene_id"] != str(task.get("scene_id", ""))
            or row["prn"] != str(task.get("prn", ""))
            or _as_int(row["tracking_channel"], f"{run_id}.eligible_channel") != key[2]
            or row["execution_status"] != str(task.get("source_summary_status", ""))
        ):
            _fail(f"cohort identity/status does not match Gate A for {run_id}")
        if row["execution_status"] not in {"ALREADY_COMPLETE", "COMPLETE"}:
            _fail(f"cohort contains ineligible execution status for {run_id}")
        status_counts[row["execution_status"]] += 1
        group, _, _ = _validate_elevation(task, run_id)
        if group == "MISSING":
            elevation_missing_ids.add(run_id)

    expected_status_counts = Counter({"ALREADY_COMPLETE": 1, "COMPLETE": 82})
    if status_counts != expected_status_counts and expected.cohort == 83:
        _fail(f"cohort status counts {dict(status_counts)} do not match 1 ALREADY_COMPLETE + 82 COMPLETE")

    warnings = audit.get("warnings", [])
    warned_missing = {
        warning.get("run_id")
        for warning in warnings
        if isinstance(warning, dict) and warning.get("code") == "scene_prn_elevation_join_missing"
    }
    if expected.cohort == 83:
        if len(elevation_missing_ids) != expected.missing_elevation:
            _fail(f"cohort has {len(elevation_missing_ids)} missing elevation summaries; expected {expected.missing_elevation}")
        if elevation_missing_ids != warned_missing:
            _fail("missing-elevation run identities do not match Gate A warning identities")
    return audit, tasks, excluded_ids


def _task_csv(root: Path, task: dict[str, Any], key: str, required: Iterable[str]) -> tuple[Path, str, list[dict[str, str]]]:
    record = task.get("stage_csvs", {}).get(key)
    if not isinstance(record, dict):
        _fail(f"{task.get('run_id')}: cohort has no {key} reference")
    path, data = _read_pinned_bytes(root, record.get("path", ""), record.get("sha256", ""), f"{task.get('run_id')} {key}")
    if len(data) > MAX_STAGE_CSV_BYTES:
        _fail(f"{task.get('run_id')} {key}: text CSV exceeds bounded read size")
    output_namespace = _project_directory(root, str(task.get("output_namespace", "")), f"{task.get('run_id')} output namespace")
    if path.parent != output_namespace:
        _fail(f"{task.get('run_id')}: {key} is outside its exact output namespace")
    _, rows = _read_csv_bytes(data, f"{task.get('run_id')} {key}", required)
    return path, _sha256_bytes(data), rows


def _task_sibling_csv(
    root: Path,
    task: dict[str, Any],
    filename: str,
    required: Iterable[str],
) -> tuple[Path, str, list[dict[str, str]]]:
    namespace = _project_directory(root, str(task.get("output_namespace", "")), f"{task.get('run_id')} output namespace")
    path = namespace / filename
    if not path.is_file():
        _fail(f"{task.get('run_id')}: required association CSV missing: {path}")
    try:
        size = path.stat().st_size
        if size > MAX_STAGE_CSV_BYTES:
            _fail(f"{task.get('run_id')} {filename}: text CSV exceeds bounded read size")
        data = path.read_bytes()
    except OSError as exc:
        _fail(f"{task.get('run_id')} {filename}: read failed: {exc}")
    if len(data) != size:
        _fail(f"{task.get('run_id')} {filename}: file changed while being read")
    _, rows = _read_csv_bytes(data, f"{task.get('run_id')} {filename}", required)
    return path, _sha256_bytes(data), rows


def _validate_stage2(task: dict[str, Any], rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], set[tuple[int, int]], dict[int, dict[str, Any]]]:
    run_id = str(task["run_id"])
    seen: set[tuple[int, int]] = set()
    by_window: dict[int, dict[str, Any]] = {}
    normalized: list[dict[str, Any]] = []
    numeric_fields = tuple(column for column in STAGE2_REQUIRED if column not in {"window_id", "selected_L", "path_id", "is_multipath"})
    for line_number, row in enumerate(rows, start=2):
        window_id = _as_int(row["window_id"], f"{run_id} Stage2 row {line_number} window_id")
        path_id = _as_int(row["path_id"], f"{run_id} Stage2 row {line_number} path_id")
        selected_l = _as_int(row["selected_L"], f"{run_id} Stage2 row {line_number} selected_L")
        is_multipath = _as_binary(row["is_multipath"], f"{run_id} Stage2 row {line_number} is_multipath")
        if window_id <= 0 or path_id <= 0 or selected_l <= 0 or path_id > selected_l:
            _fail(f"{run_id} Stage2 row {line_number}: invalid window/path/model order")
        if (is_multipath == 0 and path_id != 1) or (is_multipath == 1 and path_id == 1):
            _fail(f"{run_id} Stage2 row {line_number}: direct/MPC path_id classification conflicts")
        key = (window_id, path_id)
        if key in seen:
            _fail(f"{run_id}: duplicate Stage2 identity (window_id,path_id)={key}")
        seen.add(key)
        numeric = {field: _as_finite(row[field], f"{run_id} Stage2 row {line_number} {field}") for field in numeric_fields}
        if window_id in by_window:
            previous = by_window[window_id]
            if previous["selected_L"] != selected_l or not math.isclose(previous["recording_time_s"], numeric["recording_time_s"], abs_tol=1e-9, rel_tol=0):
                _fail(f"{run_id}: inconsistent Stage2 window metadata for window_id={window_id}")
        else:
            by_window[window_id] = {"selected_L": selected_l, "recording_time_s": numeric["recording_time_s"], "path_ids": []}
        by_window[window_id]["path_ids"].append(path_id)
        normalized.append({
            "window_id": window_id,
            "path_id": path_id,
            "selected_L": selected_l,
            "is_multipath": is_multipath,
            **numeric,
            "source_row_number": line_number,
        })
    for window_id, window in by_window.items():
        if sorted(window["path_ids"]) != list(range(1, window["selected_L"] + 1)):
            _fail(f"{run_id}: path ids do not conserve selected_L at window {window_id}")
    return normalized, seen, by_window


def _validate_stage3(rows: list[dict[str, str]], run_id: str) -> dict[tuple[int, int], dict[str, Any]]:
    by_key: dict[tuple[int, int], dict[str, Any]] = {}
    for line_number, row in enumerate(rows, start=2):
        key = (
            _as_int(row["center_window_id"], f"{run_id} Stage3 row {line_number} center_window_id"),
            _as_int(row["multipath_id"], f"{run_id} Stage3 row {line_number} multipath_id"),
        )
        if key in by_key:
            _fail(f"{run_id}: duplicate Stage3 identity {key}")
        persistence = _as_binary(row["persistence_pass"], f"{run_id} Stage3 row {line_number} persistence_pass")
        by_key[key] = {
            "persistence": persistence,
            "matched_window_count": _as_int(row["matched_window_count"], f"{run_id} Stage3 row {line_number} matched_window_count"),
            "longest_consecutive_count": _as_int(row["longest_consecutive_count"], f"{run_id} Stage3 row {line_number} longest_consecutive_count"),
        }
    return by_key


def _validate_stage4(
    path_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
    run_id: str,
) -> tuple[dict[tuple[int, int], dict[str, int]], dict[int, dict[str, int]]]:
    summaries: dict[int, dict[str, int]] = {}
    for line_number, row in enumerate(summary_rows, start=2):
        center = _as_int(row["center_window_id"], f"{run_id} Stage4 summary row {line_number} center_window_id")
        if center in summaries:
            _fail(f"{run_id}: duplicate Stage4 summary identity center_window_id={center}")
        summaries[center] = {
            "joint_valid": _as_binary(row["joint_valid"], f"{run_id} Stage4 summary row {line_number} joint_valid"),
            "joint_selected_L": _as_int(row["joint_selected_L"], f"{run_id} Stage4 summary row {line_number} joint_selected_L"),
        }
    by_key: dict[tuple[int, int], dict[str, int]] = {}
    for line_number, row in enumerate(path_rows, start=2):
        key = (
            _as_int(row["center_window_id"], f"{run_id} Stage4 row {line_number} center_window_id"),
            _as_int(row["path_id"], f"{run_id} Stage4 row {line_number} path_id"),
        )
        if key in by_key:
            _fail(f"{run_id}: duplicate Stage4 identity {key}")
        is_multipath = _as_binary(row["is_multipath"], f"{run_id} Stage4 row {line_number} is_multipath")
        selected_l = _as_int(row["joint_selected_L"], f"{run_id} Stage4 row {line_number} joint_selected_L")
        summary = summaries.get(key[0])
        if summary is None or not summary["joint_valid"] or summary["joint_selected_L"] != selected_l or key[1] > selected_l:
            _fail(f"{run_id}: Stage4 path {key} conflicts with its joint summary")
        by_key[key] = {"is_multipath": is_multipath, "joint_selected_L": selected_l}
    return by_key, summaries


def _stage4_mapping(
    row: dict[str, Any],
    stage3: dict[str, Any] | None,
    stage4_paths: dict[tuple[int, int], dict[str, int]],
    stage4_summaries: dict[int, dict[str, int]],
) -> str:
    if stage3 is None:
        return "UNMAPPED"
    if not stage3["persistence"]:
        return "NOT_EVALUATED_NOT_STAGE3_PERSISTENT"
    summary = stage4_summaries.get(row["window_id"])
    if summary is None or not summary["joint_valid"]:
        return "UNMAPPED"
    selected_l = summary["joint_selected_L"]
    if selected_l == 1:
        return "NOT_CONFIRMED_L1_NO_MPC"
    if selected_l >= row["path_id"]:
        path = stage4_paths.get((row["window_id"], row["path_id"]))
        if path is not None and path["is_multipath"] == 1:
            return "CONFIRMED_EXACT_PATH"
    return "UNMAPPED"


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


LEDGER_FIELDS = [
    "run_id", "scene_id", "prn", "tracking_channel", "source_summary_status",
    "environment_class", "elevation_group", "mean_elevation_deg", "mean_elevation_deg_status",
    "elevation_join_granularity",
    "window_id", "path_id", "selected_L", "recording_time_s", "is_multipath", "modeling_role",
    "delay_samples", "excess_delay_samples", "excess_delay_chips", "excess_path_length_m",
    "doppler_hz", "doppler_offset_hz", "relative_power_db", "dependence_cluster_id",
    "window_independence_assumed", "stage3_persistence", "stage3_match_status",
    "stage3_matched_window_count", "stage3_longest_consecutive_count", "stage4_mapping",
    "cir_feature_status", "source_stage2_csv_sha256", "source_stage3_csv_sha256",
    "source_stage4_csv_sha256", "stage2_source_row_number",
]


def build_ledger(
    project_root: Path | str,
    cohort_path: Path | str,
    output_dir: Path | str,
    *,
    source_root: Path | str | None = None,
    expected: ExpectedCounts = DEFAULT_EXPECTED,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    code_root = Path(source_root).resolve() if source_root is not None else root
    cohort_file = Path(cohort_path).resolve()
    output = Path(output_dir).resolve()
    if not root.is_dir():
        _fail(f"project root is not a directory: {root}")
    if not code_root.is_dir():
        _fail(f"source root is not a directory: {code_root}")
    try:
        cohort_file.relative_to(root)
        output.relative_to(root)
    except ValueError:
        _fail("cohort and output paths must remain within the project root")
    if not cohort_file.is_file():
        _fail(f"cohort file missing: {cohort_file}")
    if output.exists():
        _fail(f"output namespace already exists; refusing overwrite: {output}")
    if not output.parent.is_dir():
        _fail(f"output parent directory must already exist: {output.parent}")

    try:
        cohort_bytes = cohort_file.read_bytes()
    except OSError as exc:
        _fail(f"cohort read failed: {exc}")
    cohort_sha = _sha256_bytes(cohort_bytes)
    if cohort_sha.lower() != EXPECTED_COHORT_SHA256.lower():
        _fail(
            "cohort SHA-256 mismatch: "
            f"expected {EXPECTED_COHORT_SHA256}, got {cohort_sha}"
        )
    cohort = _read_json_bytes(cohort_bytes, "cohort")
    pin_hashes, pin_contents = _load_source_pins(root, code_root, cohort)
    audit, tasks, excluded_ids = _validate_cohort_and_audit(root, cohort, pin_contents, expected)
    stage4_summary_pin_path, stage4_summary_pin_manifest_sha, stage4_summary_pins = (
        _load_stage4_summary_pins(code_root, cohort_sha, tasks)
    )

    rows_out: list[dict[str, Any]] = []
    task_summaries: list[dict[str, Any]] = []
    stage2_identity_keys: set[tuple[str, int, int]] = set()
    global_counts: Counter[str] = Counter()
    elevation_task_counts: Counter[str] = Counter()
    stage3_unmapped_count = 0
    stage4_unmapped_count = 0
    stage3_row_count = 0
    stage4_path_rows_without_stage2_key = 0
    source_csvs: dict[str, dict[str, Any]] = {}

    for task in sorted(tasks, key=lambda item: str(item.get("run_id", ""))):
        run_id = str(task["run_id"])
        scene_id = str(task["scene_id"])
        prn = str(task["prn"])
        tracking_channel = _as_int(str(task["tracking_channel"]), f"{run_id}.tracking_channel")
        elevation_group, mean_elevation, mean_elevation_status = _validate_elevation(task, run_id)
        elevation_task_counts[elevation_group] += 1

        stage2_path, stage2_sha, stage2_raw = _task_csv(root, task, "stage2_selected_paths", STAGE2_REQUIRED)
        stage3_path, stage3_sha, stage3_raw = _task_csv(root, task, "stage3_persistence", STAGE3_REQUIRED)
        stage4_path, stage4_sha, stage4_raw = _task_csv(root, task, "stage4_joint_paths", STAGE4_PATH_REQUIRED)
        stage4_summary_path, stage4_summary_sha, stage4_summary_raw = _task_sibling_csv(
            root, task, "stage4_joint_summary.csv", STAGE4_SUMMARY_REQUIRED
        )
        summary_pin = stage4_summary_pins[run_id]
        summary_relative_path = stage4_summary_path.relative_to(root).as_posix()
        if summary_relative_path != summary_pin["path"]:
            _fail(f"{run_id}: Stage4 summary resolved path differs from its external pin")
        if stage4_summary_sha.lower() != summary_pin["sha256"]:
            _fail(f"{run_id}: Stage4 summary SHA-256 mismatch against external pin")
        source_csvs[run_id] = {
            "stage2": {"path": stage2_path.relative_to(root).as_posix(), "sha256": stage2_sha},
            "stage3": {"path": stage3_path.relative_to(root).as_posix(), "sha256": stage3_sha},
            "stage4": {"path": stage4_path.relative_to(root).as_posix(), "sha256": stage4_sha},
            "stage4_summary": {"path": stage4_summary_path.relative_to(root).as_posix(), "sha256": stage4_summary_sha},
        }

        stage2_rows, stage2_keys, stage2_windows = _validate_stage2(task, stage2_raw)
        stage3_map = _validate_stage3(stage3_raw, run_id)
        stage4_map, stage4_summaries = _validate_stage4(stage4_raw, stage4_summary_raw, run_id)
        stage3_row_count += len(stage3_map)
        expected_run_counts = task.get("stage_counts_from_gate_a", {})
        stage4_classifications = {
            (row["window_id"], row["path_id"]): _stage4_mapping(
                row,
                stage3_map.get((row["window_id"], row["path_id"] - 1)) if row["is_multipath"] else None,
                stage4_map,
                stage4_summaries,
            )
            for row in stage2_rows
            if row["is_multipath"]
        }
        actual_run_counts = {
            "stage2_selected_path_count": len(stage2_rows),
            "direct_path_count": sum(not row["is_multipath"] for row in stage2_rows),
            "stage2_mpc_count": sum(row["is_multipath"] for row in stage2_rows),
            "stage3_persistent_mpc_count": sum(item["persistence"] for item in stage3_map.values()),
            "stage4_confirmed_mpc_count": sum(value == "CONFIRMED_EXACT_PATH" for value in stage4_classifications.values()),
        }
        for key, actual in actual_run_counts.items():
            expected_value = expected_run_counts.get(key)
            if expected_value != actual:
                _fail(f"{run_id}: {key}={actual}, Gate A recorded {expected_value!r}")

        stage2_mpc_keys = {
            (row["window_id"], row["path_id"] - 1)
            for row in stage2_rows
            if row["is_multipath"]
        }
        stage3_orphans = set(stage3_map).difference(stage2_mpc_keys)
        if stage3_orphans:
            _fail(f"{run_id}: Stage3 identities do not map to Stage2 MPC keys: {sorted(stage3_orphans)[:5]}")
        stage4_path_rows_without_stage2_key += len(set(stage4_map).difference(stage2_keys))

        run_stage3_unmapped = 0
        run_stage4_unmapped = 0
        for row in stage2_rows:
            key_global = (run_id, row["window_id"], row["path_id"])
            if key_global in stage2_identity_keys:
                _fail(f"duplicate global (run_id,window_id,path_id) identity: {key_global}")
            stage2_identity_keys.add(key_global)
            if not row["is_multipath"]:
                stage3_status = "NOT_APPLICABLE"
                stage3_match_status = "NOT_APPLICABLE_DIRECT_PATH"
                stage3_matched = ""
                stage3_longest = ""
                stage4_status = "NOT_APPLICABLE"
                role = "DIRECT_REFERENCE"
            else:
                stage3_key = (row["window_id"], row["path_id"] - 1)
                stage3 = stage3_map.get(stage3_key)
                if stage3 is None:
                    stage3_status = "UNMAPPED"
                    stage3_match_status = "NO_EXACT_STAGE3_ROW"
                    stage3_matched = ""
                    stage3_longest = ""
                    run_stage3_unmapped += 1
                else:
                    stage3_status = "YES" if stage3["persistence"] else "NO"
                    stage3_match_status = "EXACT_STAGE3_PATH_MATCH"
                    stage3_matched = stage3["matched_window_count"]
                    stage3_longest = stage3["longest_consecutive_count"]
                stage4_status = _stage4_mapping(row, stage3, stage4_map, stage4_summaries)
                if stage4_status == "UNMAPPED":
                    run_stage4_unmapped += 1
                role = "MPC_CANDIDATE"

            rows_out.append({
                "run_id": run_id,
                "scene_id": scene_id,
                "prn": prn,
                "tracking_channel": tracking_channel,
                "source_summary_status": task["source_summary_status"],
                "environment_class": task.get("environment_class", ""),
                "elevation_group": elevation_group,
                "mean_elevation_deg": mean_elevation,
                "mean_elevation_deg_status": mean_elevation_status,
                "elevation_join_granularity": "SCENE_PRN_GROUP" if elevation_group != "MISSING" else "MISSING_NO_SUMMARY",
                "window_id": row["window_id"],
                "path_id": row["path_id"],
                "selected_L": row["selected_L"],
                "recording_time_s": format(row["recording_time_s"], ".15g"),
                "is_multipath": int(row["is_multipath"]),
                "modeling_role": role,
                **{field: format(row[field], ".15g") for field in (
                    "delay_samples", "excess_delay_samples", "excess_delay_chips",
                    "excess_path_length_m", "doppler_hz", "doppler_offset_hz", "relative_power_db",
                )},
                "dependence_cluster_id": run_id,
                "window_independence_assumed": "NO",
                "stage3_persistence": stage3_status,
                "stage3_match_status": stage3_match_status,
                "stage3_matched_window_count": stage3_matched,
                "stage3_longest_consecutive_count": stage3_longest,
                "stage4_mapping": stage4_status,
                "cir_feature_status": "PENDING_TASK5_COMPLETION",
                "source_stage2_csv_sha256": stage2_sha,
                "source_stage3_csv_sha256": stage3_sha,
                "source_stage4_csv_sha256": stage4_sha,
                "stage2_source_row_number": row["source_row_number"],
            })
        stage3_unmapped_count += run_stage3_unmapped
        stage4_unmapped_count += run_stage4_unmapped
        global_counts.update({key: value for key, value in actual_run_counts.items()})
        task_summaries.append({
            "run_id": run_id,
            "scene_id": scene_id,
            "prn": prn,
            "tracking_channel": tracking_channel,
            "source_summary_status": task["source_summary_status"],
            "environment_class": task.get("environment_class", ""),
            "elevation_group": elevation_group,
            "mean_elevation_deg": mean_elevation,
            "mean_elevation_deg_status": mean_elevation_status,
            "stage2_selected_path_count": actual_run_counts["stage2_selected_path_count"],
            "direct_path_count": actual_run_counts["direct_path_count"],
            "stage2_mpc_count": actual_run_counts["stage2_mpc_count"],
            "stage3_persistent_mpc_count": actual_run_counts["stage3_persistent_mpc_count"],
            "stage4_confirmed_mpc_count": actual_run_counts["stage4_confirmed_mpc_count"],
            "stage3_unmapped_mpc_count": run_stage3_unmapped,
            "stage4_unmapped_mpc_count": run_stage4_unmapped,
        })

    actual_global = {
        "stage2_selected_path_count": global_counts["stage2_selected_path_count"],
        "direct_path_count": global_counts["direct_path_count"],
        "stage2_mpc_count": global_counts["stage2_mpc_count"],
        "stage3_persistence_row_count": stage3_row_count,
        "stage3_persistent_mpc_count": global_counts["stage3_persistent_mpc_count"],
        "stage4_confirmed_mpc_count": global_counts["stage4_confirmed_mpc_count"],
    }
    expected_global = {
        "stage2_selected_path_count": expected.stage2,
        "direct_path_count": expected.direct,
        "stage2_mpc_count": expected.mpc,
        "stage3_persistence_row_count": expected.stage3_rows,
        "stage3_persistent_mpc_count": expected.stage3_persistent,
        "stage4_confirmed_mpc_count": expected.stage4_confirmed,
    }
    if actual_global != expected_global:
        _fail(f"global Stage2/3/4 counts {actual_global} do not match {expected_global}")
    if len(rows_out) != expected.stage2 or len(stage2_identity_keys) != expected.stage2:
        _fail(f"ledger row conservation failed: {len(rows_out)} rows, {len(stage2_identity_keys)} unique identities")
    if rows_out and sum(row["is_multipath"] == 1 for row in rows_out) != expected.mpc:
        _fail("all-MPC candidate conservation failed")
    if len(excluded_ids.intersection({row["run_id"] for row in rows_out})):
        _fail("excluded run identity entered the ledger")

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    audit = {
        "schema_version": "1.0",
        "audit_status": "STAGE2_LEDGER_PASS_CIR_ASSOCIATION_PENDING",
        "generated_at_utc": timestamp,
        "cohort_id": cohort.get("cohort_id"),
        "cohort_sha256": cohort_sha,
        "gate_a_audit_sha256": pin_hashes["gate_a_audit_json"],
        "scope": "frozen 83-task Mainline cohort; Stage2 selected-path rows only",
        "policy": {
            "modeling_population": "ALL_STAGE2_MULTIPATH",
            "stage2_mpc_is_inclusion_gate": True,
            "direct_paths": "retained_in_same_ledger_as_reference_only",
            "stage3_stage4": "association_annotations_only_never_candidate_filters",
            "elevation_join": "frozen scene+PRN group labels for 74 tasks; 9 missing groups preserved; no imputation",
            "mean_elevation_degrees": "unavailable in the frozen cohort for all 83 tasks; blank, not inferred from group labels",
            "relative_power_semantics": "relative dB; not calibrated absolute receive power",
            "window_dependence": "window records are repeated measures; cluster by run_id; do not treat overlapping windows as independent",
            "cir_features": "PENDING_TASK5_COMPLETION; no CIR/HDF5 payload opened",
            "complex_alpha": "NOT_EXTRACTED; no Stage2 MAT payload opened",
            "raw_iq_content_read": False,
            "mat_or_hdf5_payload_opened": False,
            "matlab_or_sage_run": False,
        },
        "counts": {
            "eligible_tasks": len(tasks),
            "excluded_tasks": len(excluded_ids),
            **actual_global,
            "ledger_rows": len(rows_out),
            "unique_run_window_path_keys": len(stage2_identity_keys),
            "stage3_unmapped_mpc_rows": stage3_unmapped_count,
            "stage4_unmapped_mpc_rows": stage4_unmapped_count,
            "stage4_path_rows_without_stage2_key": stage4_path_rows_without_stage2_key,
            "missing_elevation_tasks": elevation_task_counts["MISSING"],
            "elevation_tasks": dict(sorted(elevation_task_counts.items())),
        },
        "field_units": {
            "recording_time_s": "s",
            "delay_samples": "samples",
            "excess_delay_samples": "samples",
            "excess_delay_chips": "chips",
            "excess_path_length_m": "m",
            "doppler_hz": "Hz",
            "doppler_offset_hz": "Hz relative to the direct/reference path",
            "relative_power_db": "relative dB; not absolute power",
            "mean_elevation_deg": "degrees when available; currently missing for all 83 cohort rows",
        },
        "source_hashes": {
            "cohort": cohort_sha,
            "stage4_summary_pin_manifest": {
                "path": stage4_summary_pin_path.relative_to(code_root).as_posix(),
                "sha256": stage4_summary_pin_manifest_sha,
            },
            "cohort_pinned_sources": pin_hashes,
            "stage_csvs_by_run_id": source_csvs,
        },
        "per_run_summary_file": "stage2_task_summary.csv",
        "ledger_file": "stage2_ledger.csv",
    }

    staging = output.parent / f".{output.name}.building-{uuid.uuid4().hex}"
    try:
        staging.mkdir()
        _write_csv(staging / "stage2_ledger.csv", LEDGER_FIELDS, rows_out)
        _write_csv(staging / "stage2_task_summary.csv", list(task_summaries[0].keys()), task_summaries)
        _write_json(staging / "feature_audit.json", audit)
        if output.exists():
            _fail(f"output namespace appeared during build; refusing publish: {output}")
        os.rename(staging, output)
    except Exception:
        # Preserve a partial staging namespace for forensic review; never clean it implicitly.
        raise

    return {
        "audit_status": audit["audit_status"],
        "output_dir": str(output),
        "ledger_path": str(output / "stage2_ledger.csv"),
        "summary_path": str(output / "stage2_task_summary.csv"),
        "audit_path": str(output / "feature_audit.json"),
        "counts": audit["counts"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--source-root", type=Path, help="repository checkout containing pinned scripts/docs; defaults to project root")
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_ledger(args.project_root, args.cohort, args.output_dir, source_root=args.source_root)
    except (LedgerError, OSError) as exc:
        print(json.dumps({"audit_status": "FAIL", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
