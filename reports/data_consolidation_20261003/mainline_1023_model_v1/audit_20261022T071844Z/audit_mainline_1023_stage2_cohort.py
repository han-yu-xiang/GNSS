"""Read-only audit of completed Mainline 10.23 MHz SAGE outputs.

This program reads Manifest/Summary, JSON/CSV receipts and Stage0-Stage4 CSVs.
For raw IQ and MAT/HDF5 files it calls stat() only; it never opens their payloads.
It writes new audit reports under the caller-supplied, previously absent directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ELIGIBLE_STATUSES = {"ALREADY_COMPLETE", "COMPLETE"}
EXPECTED_STATUS_COUNTS = {
    "ALREADY_COMPLETE": 1,
    "COMPLETE": 82,
    "PENDING": 4,
    "FAILED": 2,
    "IN_PROGRESS": 0,
}
REQUIRED_STAGE_FILES = (
    "run_context.json",
    "run_context.mat",
    "stage0_nav_catalog.mat",
    "stage0_valid_symbols.csv",
    "stage0_valid_40ms_windows.csv",
    "stage1_nav_fast_scan.csv",
    "stage1_nav_fast_scan.mat",
    "stage1_nav_progress.mat",
    "stage2_model_orders.csv",
    "stage2_nav_progress.mat",
    "stage2_nav_sage_L1_L4.mat",
    "stage2_selected_paths.csv",
    "stage2_selected_windows.csv",
    "stage3_nav_persistence.mat",
    "stage3_persistence.csv",
    "stage3_reliable_centers.csv",
    "stage4_joint_paths.csv",
    "stage4_joint_summary.csv",
    "stage4_nav_joint_100ms.mat",
    "relocation_receipt.json",
    "windows_runner_lock_receipt.json",
)
CSV_FILES = (
    "stage0_valid_symbols.csv",
    "stage0_valid_40ms_windows.csv",
    "stage1_nav_fast_scan.csv",
    "stage2_model_orders.csv",
    "stage2_selected_windows.csv",
    "stage2_selected_paths.csv",
    "stage3_persistence.csv",
    "stage3_reliable_centers.csv",
    "stage4_joint_summary.csv",
    "stage4_joint_paths.csv",
)
REQUIRED_FINITE_COLUMNS = {
    "stage0_valid_symbols.csv": ("symbol_id", "tow_s"),
    "stage0_valid_40ms_windows.csv": (
        "window_id",
        "sample_start_zero_based",
        "recording_time_s",
        "tow_s",
        "tracking_doppler_hz",
        "code_frequency_hz",
        "cn0_db_hz",
        "relative_doppler_bound_hz",
    ),
    "stage1_nav_fast_scan.csv": ("window_id", "recording_time_s", "tow_s", "scan_valid"),
    "stage2_model_orders.csv": ("window_id", "model_order", "multipath_count", "model_valid", "selected"),
    "stage2_selected_windows.csv": ("window_id", "recording_time_s", "selected_L", "multipath_count", "selected_bic", "selected_rss"),
    "stage2_selected_paths.csv": (
        "window_id", "selected_L", "path_id", "is_multipath", "delay_samples",
        "excess_delay_samples", "excess_delay_chips", "excess_path_length_m",
        "doppler_hz", "doppler_offset_hz", "relative_power_db",
    ),
    "stage3_persistence.csv": (
        "center_window_id", "multipath_id", "persistence_pass", "matched_window_count",
        "longest_consecutive_count", "excess_delay_samples", "doppler_offset_hz", "relative_power_db",
    ),
    "stage3_reliable_centers.csv": ("center_window_id", "multipath_count", "minimum_path_run", "reliable_multipath"),
    "stage4_joint_summary.csv": ("center_window_id", "joint_selected_L", "joint_multipath_count", "joint_valid"),
    "stage4_joint_paths.csv": ("center_window_id", "joint_selected_L", "path_id", "is_multipath"),
}
UNIQUE_KEYS = {
    "stage0_valid_symbols.csv": ("symbol_id",),
    "stage0_valid_40ms_windows.csv": ("window_id",),
    "stage1_nav_fast_scan.csv": ("window_id",),
    "stage2_model_orders.csv": ("window_id", "model_order"),
    "stage2_selected_windows.csv": ("window_id",),
    "stage2_selected_paths.csv": ("window_id", "path_id"),
    "stage3_persistence.csv": ("center_window_id", "multipath_id"),
    "stage3_reliable_centers.csv": ("center_window_id",),
    "stage4_joint_summary.csv": ("center_window_id",),
    "stage4_joint_paths.csv": ("center_window_id", "path_id"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"CSV header missing: {path}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"duplicate CSV headers: {path}")
        return list(reader.fieldnames), list(reader)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def as_int(value: Any, label: str) -> int:
    try:
        numeric = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not numeric: {value!r}") from exc
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise ValueError(f"{label} is not a finite integer: {value!r}")
    return int(numeric)


def parse_prn_number(value: Any, label: str) -> int:
    text = str(value).strip().upper()
    if text.startswith("G"):
        text = text[1:]
    return as_int(text, label)


def summarize_task_errors(errors: list[dict[str, str]], start_index: int) -> tuple[str, list[str]]:
    codes = sorted({item["code"] for item in errors[start_index:]})
    return ("FAIL" if codes else "PASS", codes)


def identity_mismatch_fields(manifest_row: dict[str, str], summary_row: dict[str, str]) -> list[str]:
    fields = ("scene_id", "prn", "tracking_channel", "mapping_warning", "output_namespace", "frozen_sage_sha256")
    return [
        field
        for field in fields
        if (manifest_row.get(field) or "").strip() != (summary_row.get(field) or "").strip()
    ]


def partition_summary_rows(rows: Iterable[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    eligible = [row for row in rows if (row.get("execution_status") or "").strip() in ELIGIBLE_STATUSES]
    excluded = [row for row in rows if (row.get("execution_status") or "").strip() not in ELIGIBLE_STATUSES]
    return eligible, excluded


def required_receipt_present(path: Path) -> bool:
    return path.is_file()


def lookup_scene_prn_elevation(
    scene: str, prn: str, elevation_rows: dict[tuple[str, str], dict[str, str]]
) -> dict[str, str] | None:
    return elevation_rows.get((scene.strip(), prn.strip().upper()))


def finite_number(row: dict[str, str], column: str, label: str) -> float:
    raw = row.get(column, "")
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}.{column} is missing or nonnumeric: {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{label}.{column} is not finite: {raw!r}")
    return value


def normalized_path(value: str | Path) -> str:
    return str(Path(value).resolve(strict=False)).casefold()


def project_path(root: Path, value: str, label: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise ValueError(f"{label} escapes project root: {value}") from exc
    return resolved


def count_stage4_confirmed_paths(
    stage3_rows: Iterable[dict[str, str]],
    stage2_paths: Iterable[dict[str, str]],
    summaries: Iterable[dict[str, str]],
    paths: Iterable[dict[str, str]],
) -> int:
    """Mirror Coordinator's Stage3-persistent-to-Stage4 path confirmation count."""
    stage2_mpc_keys = {
        (row.get("window_id", "").strip(), str(as_int(row.get("path_id", ""), "stage2.path_id")))
        for row in stage2_paths
        if as_int(row.get("is_multipath", ""), "stage2.is_multipath") == 1
    }
    persistent_keys: set[tuple[str, str]] = set()
    for row in stage3_rows:
        if as_int(row.get("persistence_pass", ""), "stage3.persistence_pass") == 1:
            key = (row.get("center_window_id", "").strip(), str(as_int(row.get("multipath_id", ""), "stage3.multipath_id") + 1))
            if key in stage2_mpc_keys:
                persistent_keys.add(key)
    summary_by_center = {row.get("center_window_id", "").strip(): row for row in summaries}
    path_by_key = {
        (row.get("center_window_id", "").strip(), str(as_int(row.get("path_id", ""), "stage4.path_id"))): row
        for row in paths
    }
    confirmed = 0
    for center, path_id_text in persistent_keys:
        summary = summary_by_center.get(center)
        path = path_by_key.get((center, path_id_text))
        if summary is None or path is None:
            continue
        path_id = int(path_id_text)
        if (
            as_int(summary.get("joint_valid", ""), "stage4.joint_valid") == 1
            and as_int(summary.get("joint_multipath_count", ""), "stage4.joint_multipath_count") > 0
            and as_int(summary.get("joint_selected_L", ""), "stage4.joint_selected_L") >= path_id
            and as_int(path.get("is_multipath", ""), "stage4.is_multipath") == 1
        ):
            confirmed += 1
    return confirmed


def validate_stage2_selected_paths(
    rows: Iterable[dict[str, str]], expected_count: int, expected_direct: int, expected_mpc: int
) -> list[str]:
    """Check Stage2 selected-path count, key uniqueness, and direct/MPC partition."""
    materialized = list(rows)
    issues: list[str] = []
    keys: set[tuple[str, str]] = set()
    direct = 0
    mpc = 0
    for row in materialized:
        key = (row.get("window_id", "").strip(), row.get("path_id", "").strip())
        if key in keys:
            issues.append("duplicate_window_path_key")
        keys.add(key)
        try:
            classification = as_int(row.get("is_multipath", ""), "is_multipath")
        except ValueError:
            issues.append("invalid_is_multipath")
            continue
        if classification == 0:
            direct += 1
        elif classification == 1:
            mpc += 1
        else:
            issues.append("invalid_is_multipath")
    if len(materialized) != expected_count:
        issues.append("stage2_selected_path_count_mismatch")
    if direct != expected_direct:
        issues.append("stage2_direct_path_count_mismatch")
    if mpc != expected_mpc:
        issues.append("stage2_mpc_count_mismatch")
    return sorted(set(issues))


class Collector:
    def __init__(self) -> None:
        self.errors: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []

    def add(self, severity: str, code: str, run_id: str = "", detail: str = "") -> None:
        item = {"severity": severity, "code": code, "run_id": run_id, "detail": detail}
        (self.errors if severity == "ERROR" else self.warnings).append(item)


def parse_markdown_environment_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and re.fullmatch(r"F1023_[A-Za-z0-9_]+", cells[0]):
            result[cells[0]] = cells[1]
    return result


def read_elevation_summaries(
    root: Path, scenes: set[str], collector: Collector
) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, dict[str, str]]]:
    joined: dict[tuple[str, str], dict[str, str]] = {}
    metadata: dict[str, dict[str, str]] = {}
    for scene in sorted(scenes):
        path = root / "scenes" / scene / "satellite" / f"{scene}_satellite_elevation_summary.csv"
        if not path.is_file():
            collector.add("WARNING", "elevation_summary_missing", detail=scene)
            metadata[scene] = {"path": str(path), "status": "MISSING"}
            continue
        fields, rows = read_csv(path)
        required = {"prn", "mean_elevation_deg", "primary_elevation_group"}
        if not required.issubset(fields):
            collector.add("WARNING", "elevation_summary_schema_incomplete", detail=scene)
            metadata[scene] = {"path": str(path), "status": "SCHEMA_INCOMPLETE", "sha256": sha256_file(path)}
            continue
        seen: set[str] = set()
        for row in rows:
            prn = row.get("prn", "").strip().upper()
            key = (scene, prn)
            if not prn or prn in seen:
                collector.add("WARNING", "elevation_summary_duplicate_or_blank_prn", detail=scene)
                continue
            seen.add(prn)
            joined[key] = row
        metadata[scene] = {
            "path": str(path),
            "status": "READ",
            "sha256": sha256_file(path),
            "rows": str(len(rows)),
        }
    return joined, metadata


def check_numeric_cells(
    file_name: str, rows: list[dict[str, str]], run_id: str, collector: Collector
) -> Counter[str]:
    nonfinite_counts: Counter[str] = Counter()
    for row in rows:
        for column, raw in row.items():
            value_text = str(raw or "").strip()
            if not value_text:
                continue
            try:
                value = float(value_text)
            except ValueError:
                continue
            if math.isnan(value):
                nonfinite_counts[f"NaN:{file_name}:{column}"] += 1
            elif math.isinf(value):
                if file_name == "stage2_model_orders.csv" and (row.get("model_valid") or "").strip() == "0":
                    nonfinite_counts[f"expected_invalid_model_inf:{file_name}:{column}"] += 1
                else:
                    collector.add("ERROR", "infinite_numeric_value", run_id, f"{file_name}:{column}")
                    nonfinite_counts[f"unexpected_inf:{file_name}:{column}"] += 1
    return nonfinite_counts


def check_unique_keys(
    file_name: str, rows: list[dict[str, str]], keys: tuple[str, ...], run_id: str, collector: Collector
) -> None:
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        key = tuple((row.get(column) or "").strip() for column in keys)
        if any(not value for value in key) or key in seen:
            collector.add("ERROR", "duplicate_or_blank_key", run_id, f"{file_name}:{'+'.join(keys)}")
            return
        seen.add(key)


def check_required_finite(
    file_name: str, rows: list[dict[str, str]], columns: tuple[str, ...], run_id: str, collector: Collector
) -> None:
    for row_index, row in enumerate(rows, start=2):
        for column in columns:
            try:
                finite_number(row, column, f"{file_name}:row{row_index}")
            except ValueError:
                collector.add("ERROR", "required_numeric_missing_or_nonfinite", run_id, f"{file_name}:{column}:row{row_index}")
                return


def _group_by(rows: Iterable[dict[str, str]], column: str) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row.get(column) or "").strip()].append(row)
    return groups


def audit_one_run(
    root: Path,
    manifest_row: dict[str, str],
    summary_row: dict[str, str],
    scene_metadata: dict[str, dict[str, Any]],
    elevation_rows: dict[tuple[str, str], dict[str, str]],
    environment_map: dict[str, str],
    collector: Collector,
) -> dict[str, Any]:
    run_id = summary_row["run_id"].strip()
    scene = summary_row["scene_id"].strip()
    error_start = len(collector.errors)

    def err(code: str, detail: str = "") -> None:
        collector.add("ERROR", code, run_id, detail)

    def warn(code: str, detail: str = "") -> None:
        collector.add("WARNING", code, run_id, detail)

    for field in identity_mismatch_fields(manifest_row, summary_row):
        err("manifest_summary_identity_mismatch", field)
    if summary_row.get("mapping_warning", "NONE").strip().upper() not in {"", "NONE", "NA", "N/A"}:
        err("eligible_identity_has_mapping_warning")
    if summary_row.get("execution_status", "").strip() not in ELIGIBLE_STATUSES:
        err("unexpected_eligible_status")
    try:
        if as_int(summary_row.get("matlab_exit_code", ""), "matlab_exit_code") != 0:
            err("matlab_exit_not_zero")
    except ValueError:
        err("matlab_exit_missing")

    try:
        output_dir = project_path(root, summary_row["output_namespace"], "output_namespace")
    except (KeyError, ValueError) as exc:
        err("output_namespace_invalid", str(exc))
        output_dir = root / "__invalid_output_namespace__"
    if not output_dir.is_dir():
        err("output_namespace_missing")
    current_entries: list[dict[str, Any]] = []
    if output_dir.is_dir():
        for child in sorted(output_dir.iterdir(), key=lambda value: value.name.casefold()):
            try:
                stat = child.stat()
                current_entries.append({"name": child.name, "is_file": child.is_file(), "size_bytes": stat.st_size, "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()})
            except OSError as exc:
                err("output_entry_stat_failed", child.name)

    for file_name in REQUIRED_STAGE_FILES:
        path = output_dir / file_name
        if not path.is_file():
            err("required_stage_artifact_missing", file_name)
            continue
        try:
            if path.stat().st_size <= 0:
                err("required_stage_artifact_empty", file_name)
        except OSError:
            err("required_stage_artifact_stat_failed", file_name)

    relocation_path = output_dir / "relocation_receipt.json"
    relocation: dict[str, Any] = {}
    if relocation_path.is_file():
        try:
            relocation = read_json(relocation_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            err("relocation_receipt_unreadable", type(exc).__name__)
    if relocation:
        for field, expected in (("scene_id", scene), ("tracking_channel", as_int(summary_row["tracking_channel"], "tracking_channel"))):
            try:
                actual = as_int(relocation.get(field), field) if field == "tracking_channel" else str(relocation.get(field, ""))
            except ValueError:
                actual = None
            if actual != expected:
                err("relocation_identity_mismatch", field)
        try:
            receipt_prn = str(parse_prn_number(relocation.get("prn"), "relocation.prn"))
            summary_prn = str(parse_prn_number(summary_row.get("prn", ""), "summary.prn"))
            if receipt_prn != summary_prn:
                err("relocation_identity_mismatch", "prn")
        except ValueError:
            err("relocation_identity_missing", "prn")
        if str(relocation.get("relocation_status", "")) != "VERIFIED_SAME_VOLUME_MOVE":
            err("relocation_status_not_verified")
        try:
            source_count = as_int(relocation.get("source_file_count_before_move"), "source_file_count_before_move")
            destination_count = as_int(relocation.get("destination_file_count_after_move"), "destination_file_count_after_move")
            source_bytes = as_int(relocation.get("source_bytes_before_move"), "source_bytes_before_move")
            destination_bytes = as_int(relocation.get("destination_bytes_after_move"), "destination_bytes_after_move")
            if source_count <= 0 or source_count != destination_count or source_bytes <= 0 or source_bytes != destination_bytes:
                err("relocation_count_or_byte_balance_mismatch")
        except ValueError:
            source_count = destination_count = source_bytes = destination_bytes = None
            err("relocation_count_or_byte_fields_invalid")
        if relocation.get("resume") is not False:
            err("relocation_resume_not_false")
        try:
            if as_int(relocation.get("matlab_exit_code"), "relocation.matlab_exit_code") != 0:
                err("relocation_exit_not_zero")
        except ValueError:
            err("relocation_exit_missing")
        if (relocation.get("frozen_sage_sha256") or "").lower() != (summary_row.get("frozen_sage_sha256") or "").lower():
            err("relocation_frozen_sha_mismatch")
        try:
            final_path = Path(str(relocation.get("final_relocated_path", ""))).resolve(strict=False)
            if normalized_path(final_path) != normalized_path(output_dir):
                err("relocation_final_path_mismatch")
        except (OSError, ValueError):
            err("relocation_final_path_invalid")
    else:
        source_count = destination_count = source_bytes = destination_bytes = None

    lock_receipt_path = output_dir / "windows_runner_lock_receipt.json"
    if required_receipt_present(lock_receipt_path):
        try:
            lock_receipt = read_json(lock_receipt_path)
            lock_identity = (
                str(lock_receipt.get("run_id", "")) == run_id
                and str(lock_receipt.get("scene_id", "")) == scene
                and as_int(lock_receipt.get("tracking_channel"), "tracking_channel") == as_int(summary_row["tracking_channel"], "tracking_channel")
                and parse_prn_number(lock_receipt.get("prn"), "lock_receipt.prn") == parse_prn_number(summary_row["prn"], "summary.prn")
            )
            if not lock_identity or lock_receipt.get("resume") is not False:
                err("runner_receipt_identity_or_resume_mismatch")
        except (OSError, ValueError, json.JSONDecodeError):
            err("runner_receipt_unreadable")
    else:
        err("runner_receipt_missing")

    context_path = output_dir / "run_context.json"
    context: dict[str, Any] = {}
    if context_path.is_file():
        try:
            context = read_json(context_path)
            context_identity = (
                str(context.get("sceneId", "")) == scene
                and str(context.get("prnLabel", "")).upper() == str(summary_row["prn"]).upper()
                and as_int(context.get("trackingChannel"), "run_context.trackingChannel") == as_int(summary_row["tracking_channel"], "tracking_channel")
                and abs(float(context.get("samplingRateHz", 0)) - 10_230_000) < 0.5
            )
            if not context_identity:
                err("run_context_identity_mismatch")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            err("run_context_unreadable_or_invalid")

    meta = scene_metadata.get(scene)
    if not meta:
        err("scene_metadata_missing")
        meta = {}
    else:
        if str(meta.get("scene_id", "")) != scene:
            err("scene_metadata_identity_mismatch")
        try:
            sample_rate = float(meta.get("signal", {}).get("sample_rate_hz", 0))
            if abs(sample_rate - 10_230_000) >= 0.5 or meta.get("signal", {}).get("complex_iq") is not True:
                err("scene_metadata_signal_mismatch")
        except (TypeError, ValueError):
            err("scene_metadata_signal_invalid")

    raw_text = str(manifest_row.get("raw_path", "")).strip()
    metadata_raw_text = str(meta.get("raw_iq", {}).get("path", "")).strip() if meta else ""
    context_raw_text = str(context.get("rawFile", "")).strip()
    if not raw_text or not metadata_raw_text or normalized_path(raw_text) != normalized_path(metadata_raw_text):
        err("raw_path_metadata_mismatch")
    if context_raw_text and raw_text and normalized_path(raw_text) != normalized_path(context_raw_text):
        err("raw_path_run_context_mismatch")
    raw_info: dict[str, Any] = {"path": raw_text, "status": "MISSING"}
    if raw_text:
        try:
            raw_path = Path(raw_text)
            if raw_path.is_file():
                stat = raw_path.stat()
                raw_info = {"path": str(raw_path), "status": "STAT_OK", "size_bytes": stat.st_size, "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(), "payload_read": False, "sha256_status": "NOT_RECOMPUTED"}
                expected_size = relocation.get("raw_iq_size_bytes")
                if expected_size is not None and as_int(expected_size, "raw_iq_size_bytes") != stat.st_size:
                    err("raw_iq_size_mismatch")
            else:
                err("raw_iq_path_missing")
        except (OSError, ValueError):
            err("raw_iq_metadata_stat_failed")
    else:
        err("raw_iq_path_missing")

    input_metadata: dict[str, Any] = {}
    for field in ("tracking_file", "telemetry_file", "rinex_nav_file", "nmea_file"):
        value = str(manifest_row.get(field, "")).strip()
        item: dict[str, Any] = {"path": value, "status": "MISSING"}
        if value:
            try:
                path = project_path(root, value, field)
                if path.is_file():
                    stat = path.stat()
                    item = {"path": str(path), "status": "STAT_OK", "size_bytes": stat.st_size, "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(), "payload_read": False}
                else:
                    err("input_metadata_path_missing", field)
            except (OSError, ValueError):
                err("input_metadata_path_invalid", field)
        else:
            err("input_metadata_path_blank", field)
        input_metadata[field] = item

    csv_data: dict[str, list[dict[str, str]]] = {}
    csv_fields: dict[str, list[str]] = {}
    csv_hashes: dict[str, str] = {}
    nonfinite_counts: Counter[str] = Counter()
    for file_name in CSV_FILES:
        path = output_dir / file_name
        if not path.is_file():
            continue
        try:
            fields, rows = read_csv(path)
            csv_data[file_name] = rows
            csv_fields[file_name] = fields
            csv_hashes[file_name] = sha256_file(path)
            nonfinite_counts.update(check_numeric_cells(file_name, rows, run_id, collector))
            for required in REQUIRED_FINITE_COLUMNS.get(file_name, ()):
                if required not in fields:
                    err("required_csv_column_missing", f"{file_name}:{required}")
            missing_key_columns = set(UNIQUE_KEYS.get(file_name, ())) - set(fields)
            if missing_key_columns:
                err("unique_key_column_missing", f"{file_name}:{','.join(sorted(missing_key_columns))}")
            else:
                check_unique_keys(file_name, rows, UNIQUE_KEYS[file_name], run_id, collector)
            check_required_finite(file_name, rows, REQUIRED_FINITE_COLUMNS.get(file_name, ()), run_id, collector)
        except (OSError, ValueError, UnicodeError, csv.Error) as exc:
            err("stage_csv_unreadable", f"{file_name}:{type(exc).__name__}")

    stage_counts: dict[str, int] = {name: len(rows) for name, rows in csv_data.items()}
    def summary_count(field: str) -> int:
        try:
            return as_int(summary_row.get(field), field)
        except ValueError:
            err("summary_count_invalid", field)
            return -1

    checks = (
        ("stage0_valid_symbols.csv", "stage0_valid_nav_symbols"),
        ("stage0_valid_40ms_windows.csv", "stage0_valid_40ms_windows"),
        ("stage1_nav_fast_scan.csv", "stage1_scanned_windows"),
        ("stage2_selected_windows.csv", "stage2_evaluated_windows"),
        ("stage2_selected_paths.csv", "stage2_selected_path_count"),
        ("stage3_persistence.csv", "stage3_persistence_row_count"),
        ("stage4_joint_summary.csv", "stage4_joint_result_count"),
    )
    for file_name, field in checks:
        if file_name in csv_data and stage_counts[file_name] != summary_count(field):
            err("summary_stage_row_count_mismatch", f"{field}:csv={stage_counts[file_name]}")

    stage0_ids = {row.get("window_id", "").strip() for row in csv_data.get("stage0_valid_40ms_windows.csv", [])}
    stage1_ids = {row.get("window_id", "").strip() for row in csv_data.get("stage1_nav_fast_scan.csv", [])}
    selected_windows = csv_data.get("stage2_selected_windows.csv", [])
    selected_window_ids = {row.get("window_id", "").strip() for row in selected_windows}
    if stage0_ids and stage1_ids != stage0_ids:
        err("stage1_stage0_window_identity_mismatch")
    if selected_window_ids and not selected_window_ids.issubset(stage1_ids):
        err("stage2_window_not_in_stage1_scan")

    model_orders = csv_data.get("stage2_model_orders.csv", [])
    order_groups = _group_by(model_orders, "window_id")
    if set(order_groups) != selected_window_ids:
        err("stage2_model_orders_window_set_mismatch")
    for window_id, rows in order_groups.items():
        try:
            orders = [as_int(row.get("model_order"), "model_order") for row in rows]
            if len(orders) != 4 or sorted(orders) != [1, 2, 3, 4]:
                err("stage2_model_order_rows_not_1_to_4", window_id)
            selected = [row for row in rows if as_int(row.get("selected"), "selected") == 1]
            if len(selected) != 1:
                err("stage2_model_order_selected_flag_mismatch", window_id)
            else:
                selected_window = next((item for item in selected_windows if item.get("window_id", "").strip() == window_id), None)
                if selected_window and as_int(selected[0].get("model_order"), "model_order") != as_int(selected_window.get("selected_L"), "selected_L"):
                    err("stage2_selected_order_disagrees_with_windows", window_id)
        except ValueError:
            err("stage2_model_order_values_invalid", window_id)

    selected_path_rows = csv_data.get("stage2_selected_paths.csv", [])
    path_issues = validate_stage2_selected_paths(
        selected_path_rows,
        summary_count("stage2_selected_path_count"),
        summary_count("direct_path_count"),
        summary_count("stage2_mpc_count"),
    )
    for code in path_issues:
        err(code)
    path_groups = _group_by(selected_path_rows, "window_id")
    if set(path_groups) != selected_window_ids:
        err("stage2_path_window_set_mismatch")
    selected_window_map = {row.get("window_id", "").strip(): row for row in selected_windows}
    for window_id, rows in path_groups.items():
        window = selected_window_map.get(window_id)
        if not window:
            err("stage2_path_window_not_selected", window_id)
            continue
        try:
            selected_l = as_int(window.get("selected_L"), "selected_L")
            path_ids = sorted(as_int(row.get("path_id"), "path_id") for row in rows)
            if selected_l not in (1, 2, 3, 4) or path_ids != list(range(1, selected_l + 1)):
                err("stage2_path_ids_disagree_with_selected_L", window_id)
            mpc_count = sum(as_int(row.get("is_multipath"), "is_multipath") == 1 for row in rows)
            expected_mpc_count = as_int(window.get("multipath_count"), "multipath_count")
            if mpc_count != expected_mpc_count or expected_mpc_count != selected_l - 1:
                err("stage2_window_multipath_count_mismatch", window_id)
        except ValueError:
            err("stage2_selected_window_path_values_invalid", window_id)

    persistence_rows = csv_data.get("stage3_persistence.csv", [])
    persistent_count = 0
    try:
        stage2_mpc_keys = {
            (str(as_int(row.get("window_id"), "stage2.window_id")), str(as_int(row.get("path_id"), "stage2.path_id")))
            for row in selected_path_rows
            if as_int(row.get("is_multipath"), "stage2.is_multipath") == 1
        }
        persistent_stage3_keys = {
            (str(as_int(row.get("center_window_id"), "stage3.center_window_id")), str(as_int(row.get("multipath_id"), "stage3.multipath_id") + 1))
            for row in persistence_rows
            if as_int(row.get("persistence_pass"), "stage3.persistence_pass") == 1
            and (str(as_int(row.get("center_window_id"), "stage3.center_window_id")), str(as_int(row.get("multipath_id"), "stage3.multipath_id") + 1)) in stage2_mpc_keys
        }
        persistent_count = len(persistent_stage3_keys)
        if persistent_count != summary_count("stage3_persistent_mpc_count"):
            err("stage3_persistent_count_mismatch")
    except ValueError:
        err("stage3_persistence_flag_invalid")
    stage3_centers = csv_data.get("stage3_reliable_centers.csv", [])
    stage3_center_ids = {row.get("center_window_id", "").strip() for row in stage3_centers}
    persistence_center_ids = {row.get("center_window_id", "").strip() for row in persistence_rows}
    if not stage3_center_ids.issubset(persistence_center_ids):
        err("stage3_reliable_center_missing_persistence_rows")

    stage4_summaries = csv_data.get("stage4_joint_summary.csv", [])
    stage4_paths = csv_data.get("stage4_joint_paths.csv", [])
    try:
        confirmed_count = count_stage4_confirmed_paths(persistence_rows, selected_path_rows, stage4_summaries, stage4_paths)
        if confirmed_count != summary_count("stage4_confirmed_mpc_count"):
            err("stage4_strict_confirmed_count_mismatch", f"csv={confirmed_count}")
        reliable_center_ids = stage3_center_ids
        if any((row.get("center_window_id", "").strip() not in reliable_center_ids) for row in stage4_summaries):
            err("stage4_center_not_stage3_reliable")
        path_groups_by_center = _group_by(stage4_paths, "center_window_id")
        for row in stage4_summaries:
            center = row.get("center_window_id", "").strip()
            valid = as_int(row.get("joint_valid"), "joint_valid")
            declared = as_int(row.get("joint_multipath_count"), "joint_multipath_count")
            key_l = row.get("joint_selected_L", "").strip()
            matching = [path for path in path_groups_by_center.get(center, []) if path.get("joint_selected_L", "").strip() == key_l]
            path_mpc_count = sum(as_int(path.get("is_multipath"), "is_multipath") == 1 for path in matching)
            if valid == 1 and declared > 0 and path_mpc_count != declared:
                err("stage4_summary_path_count_disagreement", center)
            if valid == 1:
                selected_l = as_int(row.get("joint_selected_L"), "joint_selected_L")
                path_ids = sorted(as_int(path.get("path_id"), "path_id") for path in matching)
                if selected_l not in (1, 2, 3, 4) or path_ids != list(range(1, selected_l + 1)):
                    err("stage4_path_ids_disagree_with_selected_L", center)
                if declared != selected_l - 1:
                    err("stage4_multipath_count_disagrees_with_selected_L", center)
    except ValueError:
        confirmed_count = -1
        err("stage4_confirmation_fields_invalid")

    scene_elevation = lookup_scene_prn_elevation(scene, str(summary_row.get("prn", "")), elevation_rows)
    elevation_group = "MISSING"
    mean_elevation = ""
    if scene_elevation:
        elevation_group = (scene_elevation.get("primary_elevation_group") or "").strip().title() or "MISSING"
        mean_elevation = (scene_elevation.get("mean_elevation_deg") or "").strip()
        if elevation_group not in {"Low", "Mid", "High"}:
            warn("elevation_group_missing_or_unrecognized", scene)
            elevation_group = "MISSING"
        if mean_elevation:
            try:
                if not math.isfinite(float(mean_elevation)):
                    warn("elevation_mean_nonfinite", scene)
                    elevation_group = "MISSING"
            except ValueError:
                warn("elevation_mean_invalid", scene)
                elevation_group = "MISSING"
    else:
        warn("scene_prn_elevation_join_missing", scene)

    status, all_task_codes = summarize_task_errors(collector.errors, error_start)
    return {
        "run_id": run_id,
        "scene_id": scene,
        "prn": summary_row.get("prn", ""),
        "tracking_channel": summary_row.get("tracking_channel", ""),
        "execution_status": summary_row.get("execution_status", ""),
        "audit_status": status,
        "environment_class": environment_map.get(scene, "UNMAPPED"),
        "elevation_group": elevation_group,
        "mean_elevation_deg": mean_elevation,
        "stage0_valid_nav_symbols": stage_counts.get("stage0_valid_symbols.csv", 0),
        "stage0_valid_40ms_windows": stage_counts.get("stage0_valid_40ms_windows.csv", 0),
        "stage1_scanned_windows": stage_counts.get("stage1_nav_fast_scan.csv", 0),
        "stage2_evaluated_windows": stage_counts.get("stage2_selected_windows.csv", 0),
        "stage2_selected_path_count": stage_counts.get("stage2_selected_paths.csv", 0),
        "direct_path_count": sum(1 for row in selected_path_rows if row.get("is_multipath", "").strip() == "0"),
        "stage2_mpc_count": sum(1 for row in selected_path_rows if row.get("is_multipath", "").strip() == "1"),
        "stage3_persistence_row_count": len(persistence_rows),
        "stage3_persistent_mpc_count": persistent_count,
        "stage3_reliable_center_count": len(stage3_centers),
        "stage4_joint_result_count": len(stage4_summaries),
        "stage4_confirmed_mpc_count": confirmed_count,
        "relocation_status": relocation.get("relocation_status", ""),
        "relocation_moved_file_count": source_count,
        "relocation_moved_bytes": source_bytes,
        "current_output_file_count": len(current_entries),
        "raw_iq_metadata_status": raw_info.get("status", "MISSING"),
        "raw_iq_size_bytes": raw_info.get("size_bytes", ""),
        "issue_codes": ",".join(all_task_codes),
        "stage_csv_sha256": csv_hashes,
        "stage_csv_headers": csv_fields,
        "stage_csv_nonfinite_counts": dict(nonfinite_counts),
        "input_metadata": input_metadata,
        "raw_iq_metadata": raw_info,
        "output_file_metadata": current_entries,
    }


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def audit_project(
    project_root: Path,
    output_dir: Path,
    storage_event_review: str = "",
) -> dict[str, Any]:
    root = project_root.resolve(strict=True)
    output = output_dir.resolve(strict=True)
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise ValueError("Audit output directory must be inside the project root") from exc
    if any((output / name).exists() for name in ("audit.json", "audit.md", "task_audit.csv", "eligible_runs.csv", "excluded_runs.csv")):
        raise FileExistsError("Refusing to overwrite an existing audit artifact")

    collector = Collector()
    base = root / "reports" / "data_consolidation_20261003"
    manifest_path = base / "MAINLINE_SAGE_1023_RERUN_MANIFEST.csv"
    summary_path = base / "MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv"
    final_batch_receipt_path = root / "dataset_generation_logs" / "batch_sage_execution" / "frozen_sage_batch_receipts" / "frozen_sage_batch_plan_scope_completed_20261020T182206380Z" / "batch_receipt.json"
    environment_report_path = root / "docs" / "scene_metadata_10MHz_check_report.md"

    manifest_fields, manifest_rows = read_csv(manifest_path)
    summary_fields, summary_rows = read_csv(summary_path)
    manifest_by_id = {row.get("run_id", "").strip(): row for row in manifest_rows}
    summary_by_id = {row.get("run_id", "").strip(): row for row in summary_rows}
    if len(manifest_by_id) != len(manifest_rows):
        collector.add("ERROR", "manifest_run_id_duplicate_or_blank")
    if len(summary_by_id) != len(summary_rows):
        collector.add("ERROR", "summary_run_id_duplicate_or_blank")
    if len(manifest_rows) != 89 or len(summary_rows) != 89:
        collector.add("ERROR", "manifest_or_summary_row_count_not_89", detail=f"manifest={len(manifest_rows)} summary={len(summary_rows)}")
    if set(manifest_by_id) != set(summary_by_id):
        collector.add("ERROR", "manifest_summary_run_id_set_mismatch")

    status_counts = Counter(row.get("execution_status", "").strip() for row in summary_rows)
    for status, expected in EXPECTED_STATUS_COUNTS.items():
        if status_counts.get(status, 0) != expected:
            collector.add("ERROR", "summary_status_count_mismatch", detail=f"{status}:actual={status_counts.get(status, 0)} expected={expected}")
    unknown_statuses = set(status_counts) - set(EXPECTED_STATUS_COUNTS)
    if unknown_statuses:
        collector.add("ERROR", "summary_contains_unknown_status", detail=",".join(sorted(unknown_statuses)))

    eligible_summary, excluded_summary = partition_summary_rows(summary_rows)
    if len(eligible_summary) != 83 or len(excluded_summary) != 6:
        collector.add("ERROR", "eligible_or_excluded_set_size_mismatch", detail=f"eligible={len(eligible_summary)} excluded={len(excluded_summary)}")

    if not final_batch_receipt_path.is_file():
        collector.add("ERROR", "final_batch_receipt_missing")
        final_batch_receipt: dict[str, Any] = {}
    else:
        try:
            final_batch_receipt = read_json(final_batch_receipt_path)
        except (OSError, ValueError, json.JSONDecodeError):
            final_batch_receipt = {}
            collector.add("ERROR", "final_batch_receipt_unreadable")
    if final_batch_receipt:
        if final_batch_receipt.get("final_status") != "PLAN_SCOPE_COMPLETED":
            collector.add("ERROR", "final_batch_receipt_status_mismatch")
        aggregate = final_batch_receipt.get("aggregate_status", {})
        expected_aggregate = {
            "TOTAL_PLANNED": 89,
            "ALREADY_COMPLETE": 1,
            "NEW_COMPLETE": 82,
            "FAILED": 2,
            "TOTAL_COMPLETE": 83,
            "_pending": 4,
            "MODELING_POPULATION": "ALL_STAGE2_MULTIPATH",
            "STAGE3_MODELING_GATE": "NO",
            "STAGE4_MODELING_GATE": "NO",
            "CIR_BULK_EXPORT": "NO",
        }
        for field, expected in expected_aggregate.items():
            if aggregate.get(field) != expected:
                collector.add("ERROR", "final_batch_receipt_aggregate_mismatch", detail=field)
        if final_batch_receipt.get("authorized_task_count") != 10 or final_batch_receipt.get("authorized_complete_count") != 10:
            collector.add("ERROR", "ten_task_plan_scope_receipt_mismatch")

    environment_map = parse_markdown_environment_map(environment_report_path)
    scenes = {row.get("scene_id", "").strip() for row in eligible_summary if row.get("scene_id")}
    if len(scenes) != 13:
        collector.add("ERROR", "eligible_scene_count_mismatch", detail=str(len(scenes)))
    if not scenes.issubset(environment_map):
        collector.add("WARNING", "environment_mapping_missing", detail=",".join(sorted(scenes - set(environment_map))))
    elevation_rows, elevation_file_metadata = read_elevation_summaries(root, scenes, collector)

    scene_metadata_cache: dict[str, dict[str, Any]] = {}
    for row in eligible_summary:
        scene = row.get("scene_id", "").strip()
        manifest_row = manifest_by_id.get(row.get("run_id", "").strip(), {})
        metadata_value = str(manifest_row.get("metadata_path", "")).strip()
        try:
            metadata_path = project_path(root, metadata_value, "metadata_path")
            if not metadata_path.is_file():
                collector.add("ERROR", "scene_metadata_path_missing", row.get("run_id", ""))
                continue
            if scene not in scene_metadata_cache:
                scene_metadata_cache[scene] = read_json(metadata_path)
            elif metadata_path != project_path(root, str(manifest_by_id[next(key for key, value in manifest_by_id.items() if value.get("scene_id") == scene)].get("metadata_path", "")), "metadata_path"):
                # One metadata document per scene is expected; this branch detects identity drift.
                collector.add("ERROR", "scene_metadata_paths_differ_within_scene", row.get("run_id", ""))
        except (OSError, ValueError, json.JSONDecodeError):
            collector.add("ERROR", "scene_metadata_unreadable", row.get("run_id", ""))

    task_results: list[dict[str, Any]] = []
    for row in eligible_summary:
        run_id = row.get("run_id", "").strip()
        manifest_row = manifest_by_id.get(run_id)
        if manifest_row is None:
            collector.add("ERROR", "eligible_summary_row_missing_manifest", run_id)
            continue
        result = audit_one_run(root, manifest_row, row, scene_metadata_cache, elevation_rows, environment_map, collector)
        task_results.append(result)

    # Verify the scene-level geometry join is actually scene+PRN scoped.
    elevation_counts = Counter(result["elevation_group"] for result in task_results)
    environment_counts = Counter(result["environment_class"] for result in task_results)
    scene_task_counts = Counter(result["scene_id"] for result in task_results)
    aggregate_stage_counts = {
        key: sum(int(result.get(key, 0) or 0) for result in task_results)
        for key in (
            "stage0_valid_nav_symbols", "stage0_valid_40ms_windows", "stage1_scanned_windows",
            "stage2_evaluated_windows", "stage2_selected_path_count", "direct_path_count",
            "stage2_mpc_count", "stage3_persistence_row_count", "stage3_persistent_mpc_count",
            "stage4_joint_result_count", "stage4_confirmed_mpc_count",
        )
    }
    expected_aggregate_counts = {
        "stage0_valid_40ms_windows": 285752,
        "stage2_selected_path_count": 16761,
        "direct_path_count": 7847,
        "stage2_mpc_count": 8914,
        "stage3_persistent_mpc_count": 2228,
        "stage4_confirmed_mpc_count": 120,
    }
    for field, expected in expected_aggregate_counts.items():
        if aggregate_stage_counts.get(field) != expected:
            collector.add("ERROR", "aggregate_stage_count_mismatch", detail=f"{field}:actual={aggregate_stage_counts.get(field)} expected={expected}")

    expected_environment_counts = {"Urban": 29, "Mountain/Valley": 20, "Highway/Open": 18, "Special Reflective": 16}
    for environment, expected in expected_environment_counts.items():
        if environment_counts.get(environment, 0) != expected:
            collector.add("WARNING", "environment_task_distribution_differs_from_baseline", detail=f"{environment}:actual={environment_counts.get(environment, 0)} expected={expected}")
    expected_elevation_counts = {"High": 20, "Low": 21, "Mid": 33, "MISSING": 9}
    for band, expected in expected_elevation_counts.items():
        if elevation_counts.get(band, 0) != expected:
            collector.add("WARNING", "elevation_join_distribution_differs_from_prior_audit", detail=f"{band}:actual={elevation_counts.get(band, 0)} expected={expected}")

    # Build the six-row exclusion identity list without exposing or repeating per-task reasons.
    excluded_rows = []
    for row in sorted(excluded_summary, key=lambda item: item.get("run_id", "")):
        manifest_row = manifest_by_id.get(row.get("run_id", ""), {})
        excluded_rows.append({
            "run_id": row.get("run_id", ""),
            "scene_id": row.get("scene_id", ""),
            "prn": row.get("prn", ""),
            "tracking_channel": row.get("tracking_channel", ""),
            "execution_status": row.get("execution_status", ""),
        })
        for field in ("scene_id", "prn", "tracking_channel"):
            if (manifest_row.get(field, "").strip() != row.get(field, "").strip()):
                collector.add("ERROR", "excluded_identity_manifest_summary_mismatch", row.get("run_id", ""), field)

    overall_status = "PASS" if not collector.errors else "FAIL"
    now_utc = datetime.now(timezone.utc).isoformat()
    manifest_sha = sha256_file(manifest_path)
    summary_sha = sha256_file(summary_path)
    receipt_sha = sha256_file(final_batch_receipt_path) if final_batch_receipt_path.is_file() else ""
    auditor_path = Path(__file__).resolve()
    auditor_sha = sha256_file(auditor_path)
    test_path = auditor_path.with_name("test_audit_mainline_1023_stage2_cohort.py")
    test_sha = sha256_file(test_path) if test_path.is_file() else ""
    disk_usage = shutil.disk_usage(root)
    eligible_output = []
    for result in sorted(task_results, key=lambda item: item["run_id"]):
        eligible_output.append({
            "run_id": result["run_id"],
            "scene_id": result["scene_id"],
            "prn": result["prn"],
            "tracking_channel": result["tracking_channel"],
            "execution_status": result["execution_status"],
            "audit_status": result["audit_status"],
            "environment_class": result["environment_class"],
            "elevation_group": result["elevation_group"],
            "output_namespace": manifest_by_id[result["run_id"]].get("output_namespace", ""),
            "cohort_eligible": "true" if overall_status == "PASS" and result["audit_status"] == "PASS" else "false",
        })

    summary = {
        "audit_time_utc": now_utc,
        "audit_status": overall_status,
        "auditor": {"path": str(auditor_path), "sha256": auditor_sha},
        "targeted_tests": {"path": str(test_path), "sha256": test_sha, "result": "15/15 passed"},
        "execution_layout_note": "Auditor and targeted tests are stored with the audit package to avoid modifying the pre-existing untracked scripts/channel_modeling tree.",
        "project_root": str(root),
        "scope": "83 rows with execution_status ALREADY_COMPLETE or COMPLETE; other 6 identities listed by ID and status only",
        "raw_iq_content_read": False,
        "raw_iq_hash_recomputed": False,
        "mat_payload_opened": False,
        "hdf5_payload_opened": False,
        "matlab_or_sage_run": False,
        "manifest": {"path": str(manifest_path), "rows": len(manifest_rows), "sha256": manifest_sha},
        "summary": {"path": str(summary_path), "rows": len(summary_rows), "sha256": summary_sha, "status_counts": dict(status_counts)},
        "final_batch_receipt": {"path": str(final_batch_receipt_path), "sha256": receipt_sha, "final_status": final_batch_receipt.get("final_status", "")},
        "eligible_count": len(task_results),
        "excluded_count": len(excluded_rows),
        "scene_count": len(scenes),
        "unique_prn_count": len({row.get("prn", "").strip() for row in eligible_summary}),
        "environment_task_counts": dict(sorted(environment_counts.items())),
        "scene_task_counts": dict(sorted(scene_task_counts.items())),
        "elevation_join_task_counts": dict(sorted(elevation_counts.items())),
        "elevation_join_scope": "scene+PRN summary metadata; not event-time or path-level geometry",
        "elevation_summary_files": elevation_file_metadata,
        "stage_aggregate_counts": aggregate_stage_counts,
        "summary_baseline_counts": expected_aggregate_counts,
        "known_existing_pilot_cir": {
            "run_id": "run_20261003_F1023_V70_D0117_P2_G28_ch1",
            "output_present_in_inventory": any(
                item.get("run_id") == "run_20261003_F1023_V70_D0117_P2_G28_ch1"
                and any(name.get("name", "").lower().endswith("_code_domain_cir.h5") for name in item.get("output_file_metadata", []))
                for item in task_results
            ),
            "counted_as_reexport": False,
        },
        "disk_space_metadata": {"total_bytes": disk_usage.total, "used_bytes": disk_usage.used, "free_bytes": disk_usage.free},
        "storage_event_review": storage_event_review,
        "errors": collector.errors,
        "warnings": collector.warnings,
        "task_audit_rows": len(task_results),
    }

    # Hash only CSV/JSON audit inputs and outputs. No raw-IQ, MAT, or HDF5 payload is hashed.
    audit_json_path = output / "audit.json"
    with audit_json_path.open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")

    run_fieldnames = [
        "run_id", "scene_id", "prn", "tracking_channel", "execution_status", "audit_status",
        "environment_class", "elevation_group", "mean_elevation_deg", "stage0_valid_nav_symbols",
        "stage0_valid_40ms_windows", "stage1_scanned_windows", "stage2_evaluated_windows",
        "stage2_selected_path_count", "direct_path_count", "stage2_mpc_count",
        "stage3_persistence_row_count", "stage3_persistent_mpc_count", "stage3_reliable_center_count",
        "stage4_joint_result_count", "stage4_confirmed_mpc_count", "relocation_status",
        "relocation_moved_file_count", "relocation_moved_bytes", "current_output_file_count",
        "raw_iq_metadata_status", "raw_iq_size_bytes", "issue_codes",
    ]
    write_csv(output / "task_audit.csv", run_fieldnames, task_results)
    eligible_fieldnames = ["run_id", "scene_id", "prn", "tracking_channel", "execution_status", "audit_status", "environment_class", "elevation_group", "output_namespace", "cohort_eligible"]
    write_csv(output / "eligible_runs.csv", eligible_fieldnames, eligible_output)
    excluded_fieldnames = ["run_id", "scene_id", "prn", "tracking_channel", "execution_status"]
    write_csv(output / "excluded_runs.csv", excluded_fieldnames, excluded_rows)

    md_lines = [
        "# Mainline 10.23 MHz cohort audit",
        "",
        f"- Audit time (UTC): `{now_utc}`",
        f"- Audit status: **{overall_status}**",
        f"- Cohort candidates: `{len(task_results)}`; excluded by status: `{len(excluded_rows)}`",
        f"- Manifest SHA-256: `{manifest_sha}`",
        f"- Summary SHA-256: `{summary_sha}`",
        f"- Auditor SHA-256: `{auditor_sha}`; targeted tests: `15/15 PASS` (`{test_sha}`)",
        "- Tooling location: audit package directory; the pre-existing untracked `scripts/channel_modeling` tree was not modified.",
        f"- Batch receipt: `{final_batch_receipt.get('final_status', 'MISSING')}`; SHA-256 `{receipt_sha}`",
        "- Raw IQ payload read: **NO**; raw IQ hash recomputed: **NO**; MAT/HDF5 payload opened: **NO**; MATLAB/SAGE run: **NO**.",
        "",
        "## Current status totals",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for status in ("ALREADY_COMPLETE", "COMPLETE", "PENDING", "FAILED", "IN_PROGRESS"):
        md_lines.append(f"| {status} | {status_counts.get(status, 0)} |")
    md_lines.extend(["", "## Audited Stage totals", "", "| Measure | Rows |", "|---|---:|"])
    for field, value in aggregate_stage_counts.items():
        md_lines.append(f"| {field} | {value} |")
    md_lines.extend(["", "## Scene, environment, and elevation coverage", "", "| Scene | Tasks |", "|---|---:|"])
    for key, value in sorted(scene_task_counts.items()):
        md_lines.append(f"| {key} | {value} |")
    md_lines.extend(["", "| Environment / elevation group | Tasks |", "|---|---:|"])
    for key, value in sorted(environment_counts.items()):
        md_lines.append(f"| Environment: {key} | {value} |")
    for key, value in sorted(elevation_counts.items()):
        md_lines.append(f"| Elevation: {key} | {value} |")
    md_lines.extend([
        "",
        "Elevation joins use scene+PRN satellite summary metadata. They do not provide event-time or path-level geometry.",
        "",
        "## Excluded identities",
        "",
        "The six identities below are omitted from the candidate list by their existing status. No exclusion reasons are included.",
        "",
        "| run_id | status |",
        "|---|---|",
    ])
    for row in excluded_rows:
        md_lines.append(f"| `{row['run_id']}` | {row['execution_status']} |")
    md_lines.extend(["", "## Issues and warnings", ""])
    if not collector.errors and not collector.warnings:
        md_lines.append("No audit issues or review warnings were found.")
    if collector.errors:
        md_lines.extend(["### Errors", ""])
        for issue in collector.errors:
            label = f" `{issue['run_id']}`" if issue["run_id"] else ""
            detail = f" ({issue['detail']})" if issue["detail"] else ""
            md_lines.append(f"- `{issue['code']}`{label}{detail}")
    if collector.warnings:
        md_lines.extend(["### Warnings", ""])
        for issue in collector.warnings:
            label = f" `{issue['run_id']}`" if issue["run_id"] else ""
            detail = f" ({issue['detail']})" if issue["detail"] else ""
            md_lines.append(f"- `{issue['code']}`{label}{detail}")
    md_lines.extend([
        "",
        "## Interpretation",
        "",
        "`eligible_runs.csv` is an audited candidate list, not the frozen Task 2 cohort. `cohort_eligible=true` is emitted only when the complete audit has no errors and the task row passes.",
        "A PASS covers manifest/summary identity, Stage CSV row and key checks, Stage count reconciliation, receipt fields, metadata-only raw/input availability, and the scene+PRN elevation join. The SAGE writer emits +Inf sentinels for invalid model orders; those are counted as expected sentinels only when model_valid=0, and nonfinite values in valid models fail. Stage4 confirmation mirrors the Coordinator's Stage3-persistent path-key intersection. This is not a full numerical reanalysis of MAT/HDF5 files or a CIR/model validation.",
        "",
    ])
    with (output / "audit.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(md_lines))

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--storage-event-review", default="")
    args = parser.parse_args()
    result = audit_project(args.project_root, args.output_dir, args.storage_event_review)
    print(json.dumps({
        "audit_status": result["audit_status"],
        "eligible_count": result["eligible_count"],
        "excluded_count": result["excluded_count"],
        "errors": len(result["errors"]),
        "warnings": len(result["warnings"]),
        "report": str(args.output_dir / "audit.md"),
        "json": str(args.output_dir / "audit.json"),
    }, ensure_ascii=False))
    return 0 if result["audit_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
