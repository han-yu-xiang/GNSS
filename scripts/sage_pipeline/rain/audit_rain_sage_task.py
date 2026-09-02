#!/usr/bin/env python3
"""Read-only independent QA for one standalone Rain SAGE artifact.

The auditor reads only JSON/CSV/MAT metadata and result tables.  It never opens
raw IQ, invokes MATLAB/SAGE, changes the audited namespace, resumes a task, or
deletes an artifact.  QA output is written with exclusive creation semantics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REQUIRED_CSV_OUTPUTS: tuple[str, ...] = (
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

REQUIRED_MAT_OUTPUTS: tuple[str, ...] = (
    "doppler_sign.mat",
    "stage0_nav_catalog.mat",
    "stage1_nav_fast_scan.mat",
    "stage1_nav_progress.mat",
    "stage2_nav_progress.mat",
    "stage2_nav_sage_L1_L4.mat",
    "stage3_nav_persistence.mat",
    "stage4_nav_joint_100ms.mat",
)

REQUIRED_JSON_OUTPUTS: tuple[str, ...] = ("rain_stage0_provenance.json",)
REQUIRED_OUTPUTS: tuple[str, ...] = (
    *REQUIRED_CSV_OUTPUTS,
    *REQUIRED_MAT_OUTPUTS,
    *REQUIRED_JSON_OUTPUTS,
)

CSV_SCHEMAS: dict[str, tuple[str, ...]] = {
    "stage0_valid_symbols.csv": (
        "symbol_id", "telemetry_row", "prn", "tow_s", "sample_start_zero_based",
        "recording_time_s", "nav_symbol", "tracking_index", "tracking_doppler_hz",
        "code_frequency_hz", "cn0_db_hz", "carrier_lock_test", "tracking_tow_ms",
        "next_step_samples", "next_tow_step_s", "continuous_to_next",
    ),
    "stage0_valid_40ms_windows.csv": (
        "window_id", "symbol_index", "sample_start_zero_based", "recording_time_s",
        "tow_s", "nav_symbol_1", "nav_symbol_2", "split_samples",
        "tracking_doppler_hz", "code_frequency_hz", "cn0_db_hz", "vehicle_speed_kmh",
        "speed_source", "relative_doppler_bound_hz",
    ),
    "stage1_nav_fast_scan.csv": (
        "window_id", "recording_time_s", "tow_s", "cn0_db_hz", "nav_symbol_1",
        "nav_symbol_2", "scan_valid", "main_delay_samples", "main_doppler_hz",
        "main_score", "residual_peak1_delay_samples", "residual_peak1_doppler_hz",
        "residual_peak1_power_db", "residual_peak2_delay_samples",
        "residual_peak2_doppler_hz", "residual_peak2_power_db",
        "residual_peak3_delay_samples", "residual_peak3_doppler_hz",
        "residual_peak3_power_db", "has_one_strong_residual",
        "has_two_strong_residuals", "screen_score_db", "error_message",
    ),
    "stage2_model_orders.csv": (
        "window_id", "recording_time_s", "model_order", "multipath_count", "rss",
        "bic", "bic_gain_from_previous", "rss_gain_percent_from_previous",
        "model_valid", "selected", "minimum_multipath_power_db",
        "minimum_separation_samples", "maximum_relative_doppler_hz",
        "maximum_coherence",
    ),
    "stage2_selected_windows.csv": (
        "window_id", "recording_time_s", "tow_s", "selected_L", "multipath_count",
        "selected_bic", "selected_rss", "minimum_multipath_power_db",
        "maximum_relative_doppler_hz", "maximum_coherence",
    ),
    "stage2_selected_paths.csv": (
        "window_id", "recording_time_s", "selected_L", "path_id", "is_multipath",
        "delay_samples", "excess_delay_samples", "excess_delay_chips",
        "excess_path_length_m", "doppler_hz", "doppler_offset_hz", "relative_power_db",
    ),
    "stage3_persistence.csv": (
        "center_window_id", "center_recording_time_s", "selected_L", "multipath_id",
        "excess_delay_samples", "doppler_offset_hz", "relative_power_db",
        "matched_window_count", "longest_consecutive_count", "persistence_pass",
        "match_pattern",
    ),
    "stage3_reliable_centers.csv": (
        "center_window_id", "recording_time_s", "selected_L", "multipath_count",
        "minimum_path_run", "reliable_multipath",
    ),
    "stage4_joint_summary.csv": (
        "center_window_id", "recording_time_s", "stage2_L", "joint_selected_L",
        "joint_multipath_count", "joint_rss", "joint_bic", "snapshot_wins_vs_L1",
        "minimum_multipath_power_db", "maximum_relative_doppler_hz",
        "maximum_coherence", "joint_valid",
    ),
    "stage4_joint_paths.csv": (
        "center_window_id", "joint_selected_L", "path_id", "is_multipath",
        "delay_samples", "excess_delay_samples", "excess_delay_chips", "doppler_hz",
        "doppler_offset_hz", "mean_relative_power_db", "phase_rad", "relative_phase_rad",
        "relative_phase_available", "relative_amplitude", "relative_amplitude_db",
        "phase_source",
    ),
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _text(value).lower()).strip("_")


def _get(mapping: Mapping[str, Any], *names: str, default: Any = "") -> Any:
    normalized = {_key(name): value for name, value in mapping.items()}
    for name in names:
        if _key(name) in normalized:
            return normalized[_key(name)]
    return default


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def parse_float(value: Any) -> float | None:
    text = _text(value)
    if not text:
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


def normalize_prn(value: Any) -> str:
    text = _text(value).upper().replace("GPS", "").replace("PRN", "")
    text = text.strip().lstrip("G")
    number = parse_int(text)
    return f"G{number:02d}" if number is not None else _text(value).upper()


def _same_text(left: Any, right: Any) -> bool:
    return _text(left).casefold() == _text(right).casefold()


def _same_prn(left: Any, right: Any) -> bool:
    return normalize_prn(left) == normalize_prn(right)


def _same_path(left: Path, right: Path) -> bool:
    return str(left.resolve(strict=False)).casefold() == str(right.resolve(strict=False)).casefold()


def _filesystem_path(path: Path) -> Path:
    """Return a filesystem-access path, adding the Windows long-path prefix.

    Displayed paths and provenance remain unchanged.  The prefix is only used
    for read-only filesystem calls that otherwise fail at the Win32 MAX_PATH
    boundary.  UNC paths are converted to the corresponding extended UNC
    form; already-prefixed paths are left untouched.
    """
    if os.name != "nt":
        return path
    value = os.fspath(path)
    if value.startswith("\\\\?\\") or value.startswith("\\\\."):
        return path
    if len(value) < 248:
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)


def nonempty_file(path: Path) -> bool:
    access_path = _filesystem_path(path)
    return access_path.is_file() and access_path.stat().st_size > 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with _filesystem_path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with _filesystem_path(path).open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with _filesystem_path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        return [dict(row) for row in reader], fields


def values(rows: Iterable[Mapping[str, Any]], field: str) -> list[str]:
    return [_text(_get(row, field)) for row in rows if _text(_get(row, field))]


def distinct(rows: Iterable[Mapping[str, Any]], field: str) -> set[str]:
    return set(values(rows, field))


def _as_int_set(rows: Iterable[Mapping[str, Any]], field: str) -> set[int]:
    result: set[int] = set()
    for value in values(rows, field):
        number = parse_int(value)
        if number is not None:
            result.add(number)
    return result


def _numeric_field_finite(row: Mapping[str, Any], field: str) -> bool:
    return parse_float(_get(row, field)) is not None


def _path_is_within_expected_namespace(task: Mapping[str, Any], output_dir: Path) -> bool:
    scene = _text(_get(task, "scene_id", "scene"))
    prn = normalize_prn(_get(task, "prn"))
    configured = _text(_get(task, "expected_output_namespace", "output_dir"))
    if configured:
        return _same_path(output_dir, Path(configured))
    if len(output_dir.parents) < 3 or not scene or not prn:
        return False
    scene_root = output_dir.parents[2]
    namespace = output_dir.parents[0].name
    if scene_root.name.casefold() != scene.casefold():
        return False
    if output_dir.parents[1].name.casefold() != "sage_results":
        return False
    allowed_namespace = namespace.casefold() == "rain_sage_v1" or re.fullmatch(
        r"rain_sage_rerun_v1_\d{8}_r\d+", namespace, flags=re.IGNORECASE
    )
    if not allowed_namespace:
        return False
    expected = scene_root / "sage_results" / namespace / prn
    return _same_path(output_dir, expected)


def _check_schema(
    name: str,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> list[str]:
    missing = [field for field in fields if field not in fields_from_rows(rows, fields)]
    return [f"{name}:missing_columns={','.join(missing)}"] if missing else []


def fields_from_rows(rows: Sequence[Mapping[str, Any]], fallback: Sequence[str]) -> set[str]:
    if rows:
        return set(rows[0].keys())
    return set(fallback)


def _safe_read_csv(
    path: Path,
    schema: Sequence[str],
    issues: list[str],
) -> list[dict[str, str]]:
    try:
        rows, fields = read_csv_rows(path)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        issues.append(f"{path.name}:csv_read_error={exc}")
        return []
    missing = [field for field in schema if field not in fields]
    if missing:
        issues.append(f"{path.name}:missing_columns={','.join(missing)}")
    return rows


def _receipt_status(task: Mapping[str, Any]) -> tuple[str, dict[str, Any] | None, list[str]]:
    receipt_value = _get(task, "execution_receipt_path", "receipt_path")
    if not receipt_value:
        return "NOT_FOUND", None, []
    path = Path(_text(receipt_value))
    access_path = _filesystem_path(path)
    if not access_path.is_file():
        return "NOT_FOUND", None, [f"execution_receipt_missing={path}"]
    try:
        receipt = read_json(access_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return "INVALID", None, [f"execution_receipt_invalid={exc}"]
    exit_code = _get(receipt, "matlab_exit_code", "exit_code", default=None)
    status = _text(_get(receipt, "execution_status", "status", "overall_status")).upper()
    if parse_int(exit_code) == 0 and status in {"COMPLETED", "PASS", "SUCCESS", "RAIN_STAGE1_STAGE4_COMPLETED"}:
        return "VALID", receipt, []
    return "PRESENT_NOT_SUCCESS", receipt, [
        f"execution_receipt_status={status or 'MISSING'}",
        f"execution_receipt_exit_code={_text(exit_code) or 'MISSING'}",
    ]


def _empty_result(task: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    return {
        "task_id": _text(_get(task, "task_id")),
        "weather": _text(_get(task, "weather_condition", "weather")),
        "scene_id": _text(_get(task, "scene_id", "scene")),
        "prn": normalize_prn(_get(task, "prn")),
        "tracking_channel": parse_int(_get(task, "tracking_channel", "channel")),
        "sample_rate_hz": parse_int(_get(task, "sample_rate_hz")),
        "output_dir": str(output_dir),
        "output_namespace_exists": _filesystem_path(output_dir).exists(),
        "new_only_execution": "NOT_APPLICABLE_READ_ONLY_AUDIT",
        "execution_receipt_status": "NOT_FOUND",
        "identity_status": "PASS",
        "artifact_completeness": "PASS",
        "stage_consistency": "PASS",
        "numerical_validity": "PASS",
        "scientific_status": "NOT_ASSESSABLE",
        "overall_status": "FAIL_MISSING_OUTPUT",
        "qa_status": "FAIL",
        "issues": [],
        "warnings": [],
        "missing_outputs": [],
        "stage0_symbols": None,
        "stage0_windows": None,
        "stage1_scanned_windows": None,
        "stage1_invalid_windows": None,
        "stage2_model_rows": None,
        "stage2_selected_windows": None,
        "stage2_model_order_counts": {},
        "stage2_invalid_models": None,
        "stage3_persistence_rows": None,
        "stage3_reliable_centers": None,
        "stage4_joint_rows": None,
        "stage4_joint_valid_rows": None,
        "confirmed_events": None,
        "confirmed_multipath_paths": None,
        "confirmed_center_ids": [],
        "artifact_files": [],
        "raw_iq_read_by_auditor": False,
        "matlab_executed_by_auditor": False,
        "sage_executed_by_auditor": False,
    }


def audit_task(task: Mapping[str, Any], output_dir: Path | None = None) -> dict[str, Any]:
    """Audit an existing Rain output directory without opening raw IQ."""
    if output_dir is None:
        output_dir = Path(_text(_get(task, "expected_output_namespace", "output_dir")))
    result = _empty_result(task, output_dir)
    issues: list[str] = []
    warnings: list[str] = []

    if not _filesystem_path(output_dir).is_dir():
        result["missing_outputs"] = list(REQUIRED_OUTPUTS)
        result["issues"] = [f"output_namespace_missing={output_dir}"]
        return result

    if not _path_is_within_expected_namespace(task, output_dir):
        issues.append("output_namespace_does_not_match_scene_prn_contract")

    paths = {name: output_dir / name for name in REQUIRED_OUTPUTS}
    result["artifact_files"] = [
        {
            "name": name,
            "path": str(path),
            "exists": _filesystem_path(path).is_file(),
            "nonempty": nonempty_file(path),
            "bytes": _filesystem_path(path).stat().st_size if _filesystem_path(path).is_file() else 0,
            "sha256": sha256_file(path) if nonempty_file(path) else "",
        }
        for name, path in paths.items()
    ]
    missing = [name for name, path in paths.items() if not nonempty_file(path)]
    result["missing_outputs"] = missing
    if missing:
        issues.append("missing_or_empty_outputs=" + ",".join(missing))

    provenance: dict[str, Any] = {}
    provenance_path = paths["rain_stage0_provenance.json"]
    if nonempty_file(provenance_path):
        try:
            provenance = read_json(provenance_path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            issues.append(f"provenance_json_invalid={exc}")
    else:
        issues.append("provenance_json_missing_or_empty")

    expected_scene = _text(_get(task, "scene_id", "scene"))
    expected_weather = _text(_get(task, "weather_condition", "weather"))
    expected_prn = normalize_prn(_get(task, "prn"))
    expected_channel = parse_int(_get(task, "tracking_channel", "channel"))
    expected_fs = parse_int(_get(task, "sample_rate_hz"))
    identity_checks = {
        "scene_id": _same_text(_get(provenance, "scene_id"), expected_scene),
        "weather_condition": (not expected_weather) or _same_text(
            _get(provenance, "weather_condition", "weather"), expected_weather
        ),
        "prn": _same_prn(_get(provenance, "prn"), expected_prn),
        "tracking_channel": parse_int(_get(provenance, "tracking_channel")) == expected_channel,
        "sample_rate_hz": parse_float(_get(provenance, "sample_rate_hz")) == expected_fs,
    }
    identity_issues = [name for name, passed in identity_checks.items() if not passed]
    if identity_issues:
        issues.append("provenance_identity_mismatch=" + ",".join(identity_issues))

    stage0_symbols: list[dict[str, str]] = []
    stage0_windows: list[dict[str, str]] = []
    stage1: list[dict[str, str]] = []
    stage2_models: list[dict[str, str]] = []
    stage2_selected: list[dict[str, str]] = []
    stage2_paths: list[dict[str, str]] = []
    stage3_persistence: list[dict[str, str]] = []
    stage3_reliable: list[dict[str, str]] = []
    stage4_summary: list[dict[str, str]] = []
    stage4_paths: list[dict[str, str]] = []
    if not missing:
        stage0_symbols = _safe_read_csv(paths["stage0_valid_symbols.csv"], CSV_SCHEMAS["stage0_valid_symbols.csv"], issues)
        stage0_windows = _safe_read_csv(paths["stage0_valid_40ms_windows.csv"], CSV_SCHEMAS["stage0_valid_40ms_windows.csv"], issues)
        stage1 = _safe_read_csv(paths["stage1_nav_fast_scan.csv"], CSV_SCHEMAS["stage1_nav_fast_scan.csv"], issues)
        stage2_models = _safe_read_csv(paths["stage2_model_orders.csv"], CSV_SCHEMAS["stage2_model_orders.csv"], issues)
        stage2_selected = _safe_read_csv(paths["stage2_selected_windows.csv"], CSV_SCHEMAS["stage2_selected_windows.csv"], issues)
        stage2_paths = _safe_read_csv(paths["stage2_selected_paths.csv"], CSV_SCHEMAS["stage2_selected_paths.csv"], issues)
        stage3_persistence = _safe_read_csv(paths["stage3_persistence.csv"], CSV_SCHEMAS["stage3_persistence.csv"], issues)
        stage3_reliable = _safe_read_csv(paths["stage3_reliable_centers.csv"], CSV_SCHEMAS["stage3_reliable_centers.csv"], issues)
        stage4_summary = _safe_read_csv(paths["stage4_joint_summary.csv"], CSV_SCHEMAS["stage4_joint_summary.csv"], issues)
        stage4_paths = _safe_read_csv(paths["stage4_joint_paths.csv"], CSV_SCHEMAS["stage4_joint_paths.csv"], issues)

    result["stage0_symbols"] = len(stage0_symbols)
    result["stage0_windows"] = len(stage0_windows)
    result["stage1_scanned_windows"] = len(stage1)
    result["stage1_invalid_windows"] = sum(
        parse_bool(_get(row, "scan_valid")) is not True for row in stage1
    )
    result["stage2_model_rows"] = len(stage2_models)
    result["stage2_selected_windows"] = len(distinct(stage2_selected, "window_id"))
    result["stage3_persistence_rows"] = len(stage3_persistence)
    result["stage3_reliable_centers"] = len(distinct(stage3_reliable, "center_window_id"))
    result["stage4_joint_rows"] = len(stage4_summary)
    result["stage4_joint_valid_rows"] = sum(
        parse_bool(_get(row, "joint_valid")) is True for row in stage4_summary
    )

    expected_symbols = parse_int(_get(task, "expected_valid_symbol_count"))
    expected_windows = parse_int(_get(task, "expected_window_count"))
    if expected_symbols is not None and len(stage0_symbols) != expected_symbols:
        issues.append(f"stage0_symbol_count_expected_{expected_symbols}_actual_{len(stage0_symbols)}")
    if expected_windows is not None and len(stage0_windows) != expected_windows:
        issues.append(f"stage0_window_count_expected_{expected_windows}_actual_{len(stage0_windows)}")

    symbol_prns = {normalize_prn(value) for value in values(stage0_symbols, "prn")}
    if symbol_prns and symbol_prns != {expected_prn}:
        issues.append("stage0_symbol_prn_mismatch=" + ",".join(sorted(symbol_prns)))

    stage0_ids = _as_int_set(stage0_windows, "window_id")
    stage1_ids = _as_int_set(stage1, "window_id")
    stage2_selected_ids = _as_int_set(stage2_selected, "window_id")
    stage2_model_ids = _as_int_set(stage2_models, "window_id")
    stage2_path_ids = _as_int_set(stage2_paths, "window_id")
    stage3_reliable_ids = _as_int_set(stage3_reliable, "center_window_id")
    stage3_persistence_ids = _as_int_set(stage3_persistence, "center_window_id")
    stage4_ids = _as_int_set(stage4_summary, "center_window_id")

    if len(stage0_ids) != len(stage0_windows):
        issues.append("stage0_window_id_duplicate_or_invalid")
    if len(stage1_ids) != len(stage1):
        issues.append("stage1_window_id_duplicate_or_invalid")
    if stage0_ids != stage1_ids:
        issues.append(
            f"stage1_full_scan_window_mismatch_missing={sorted(stage0_ids - stage1_ids)}_extra={sorted(stage1_ids - stage0_ids)}"
        )
    if not stage2_selected_ids.issubset(stage1_ids):
        issues.append("stage2_selected_window_not_in_stage1")
    if not stage2_model_ids.issubset(stage2_selected_ids):
        issues.append("stage2_model_window_not_in_selected_windows")
    if not stage2_path_ids.issubset(stage2_selected_ids):
        issues.append("stage2_path_window_not_in_selected_windows")
    if not stage3_reliable_ids.issubset(stage2_selected_ids):
        issues.append("stage3_reliable_center_not_in_stage2_selected_windows")
    if not stage3_persistence_ids.issubset(stage2_selected_ids):
        issues.append("stage3_persistence_center_not_in_stage2_selected_windows")
    if not stage4_ids.issubset(stage3_reliable_ids):
        issues.append("stage4_center_not_in_stage3_reliable_centers")

    order_counts: dict[str, int] = {}
    invalid_models = 0
    per_window_orders: dict[int, set[int]] = {}
    for row in stage2_models:
        order = parse_int(_get(row, "model_order"))
        window = parse_int(_get(row, "window_id"))
        if order is None or window is None:
            issues.append("stage2_model_order_or_window_invalid")
            continue
        order_counts[str(order)] = order_counts.get(str(order), 0) + 1
        per_window_orders.setdefault(window, set()).add(order)
        if parse_bool(_get(row, "model_valid")) is not True:
            invalid_models += 1
    expected_orders = {1, 2, 3, 4}
    incomplete_order_windows = sorted(
        window for window in stage2_selected_ids
        if per_window_orders.get(window, set()) != expected_orders
    )
    if incomplete_order_windows:
        issues.append("stage2_missing_L1_to_L4=" + ",".join(map(str, incomplete_order_windows)))
    result["stage2_model_order_counts"] = order_counts
    result["stage2_invalid_models"] = invalid_models

    scan_errors = [
        _text(_get(row, "error_message"))
        for row in stage1
        if _text(_get(row, "error_message"))
    ]
    if scan_errors:
        issues.append(f"stage1_error_message_rows={len(scan_errors)}")

    if missing:
        result["confirmed_events"] = None
        result["confirmed_multipath_paths"] = None
        result["confirmed_center_ids"] = []
        result["scientific_status"] = "NOT_ASSESSABLE"
        result["identity_status"] = "FAIL" if identity_issues else "PASS"
        result["artifact_completeness"] = "FAIL"
        result["stage_consistency"] = "NOT_ASSESSABLE"
        result["numerical_validity"] = "NOT_ASSESSABLE"
        result["execution_receipt_status"], receipt, receipt_issues = _receipt_status(task)
        issues.extend(receipt_issues)
        if receipt is not None:
            result["execution_receipt"] = receipt
        result["overall_status"] = "FAIL_MISSING_OUTPUT"
        result["qa_status"] = "FAIL"
        result["issues"] = sorted(set(issues))
        result["warnings"] = sorted(set(warnings))
        return result

    confirmed_summary: list[dict[str, str]] = []
    for row in stage4_summary:
        valid = parse_bool(_get(row, "joint_valid"))
        count = parse_int(_get(row, "joint_multipath_count"))
        if valid is None or count is None:
            issues.append("stage4_joint_valid_or_multipath_count_invalid")
        if valid is True and count is not None and count > 0:
            confirmed_summary.append(row)
    confirmed_centers = {
        _text(_get(row, "center_window_id")) for row in confirmed_summary
    }
    confirmed_paths: list[dict[str, str]] = []
    for row in stage4_paths:
        is_mp = parse_bool(_get(row, "is_multipath"))
        center = _text(_get(row, "center_window_id"))
        if is_mp is True:
            if center not in confirmed_centers:
                issues.append(f"stage4_multipath_path_without_confirmed_summary={center}")
            else:
                confirmed_paths.append(row)
            for field in (
                "excess_delay_samples", "doppler_offset_hz", "mean_relative_power_db",
                "relative_amplitude", "relative_phase_rad",
            ):
                if not _numeric_field_finite(row, field):
                    issues.append(f"confirmed_path_nonfinite_{field}={center}")
        elif is_mp is None:
            issues.append("stage4_path_is_multipath_invalid")

    for row in confirmed_summary:
        center = _text(_get(row, "center_window_id"))
        expected_count = parse_int(_get(row, "joint_multipath_count"))
        actual_count = sum(
            _text(_get(path, "center_window_id")) == center for path in confirmed_paths
        )
        if expected_count is not None and actual_count != expected_count:
            issues.append(
                f"stage4_confirmed_path_count_mismatch={center}_expected_{expected_count}_actual_{actual_count}"
            )

    result["confirmed_events"] = len(confirmed_summary)
    result["confirmed_multipath_paths"] = len(confirmed_paths)
    result["confirmed_center_ids"] = sorted(confirmed_centers)
    if stage4_summary and all(parse_bool(_get(row, "joint_valid")) is True for row in stage4_summary):
        if confirmed_summary and confirmed_paths:
            result["scientific_status"] = "PASS_WITH_CONFIRMED_MULTIPATH"
        elif not confirmed_summary and not confirmed_paths:
            result["scientific_status"] = "PASS_NO_CONFIRMED_MULTIPATH"
        else:
            result["scientific_status"] = "NOT_ASSESSABLE"
    else:
        result["scientific_status"] = "NOT_ASSESSABLE"

    receipt_status, receipt, receipt_issues = _receipt_status(task)
    result["execution_receipt_status"] = receipt_status
    issues.extend(receipt_issues)
    if receipt is not None:
        result["execution_receipt"] = receipt

    result["identity_status"] = "FAIL" if identity_issues or any(
        issue.startswith(("output_namespace", "stage0_symbol_prn")) for issue in issues
    ) else "PASS"
    result["artifact_completeness"] = "FAIL" if missing else "PASS"
    result["stage_consistency"] = "FAIL" if any(
        issue.startswith(("stage0_", "stage1_", "stage2_", "stage3_", "stage4_"))
        for issue in issues
    ) else "PASS"
    result["numerical_validity"] = "FAIL" if any(
        "nonfinite" in issue or "invalid" in issue and "stage" in issue for issue in issues
    ) else "PASS"

    if result["identity_status"] == "FAIL":
        overall = "FAIL_IDENTITY_OR_SCHEMA"
    elif result["artifact_completeness"] == "FAIL":
        overall = "FAIL_MISSING_OUTPUT"
    elif result["stage_consistency"] == "FAIL":
        overall = "FAIL_STAGE_CONSISTENCY"
    elif result["numerical_validity"] == "FAIL":
        overall = "FAIL_NUMERICAL_VALIDITY"
    elif receipt_status in {"INVALID", "PRESENT_NOT_SUCCESS", "NOT_FOUND"}:
        overall = "INCONCLUSIVE_NO_EXECUTION_RECEIPT" if receipt_status == "NOT_FOUND" else "INCONCLUSIVE_EXECUTION_RECEIPT"
    else:
        overall = "QA_PASS"
    result["overall_status"] = overall
    result["qa_status"] = "PASS" if overall == "QA_PASS" else "INCONCLUSIVE" if overall.startswith("INCONCLUSIVE") else "FAIL"
    result["issues"] = sorted(set(issues))
    result["warnings"] = sorted(set(warnings))
    return result


def _write_new_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(content)


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    _write_new_text(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def _write_new_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _report_text(result: Mapping[str, Any]) -> str:
    lines = [
        "# Rain SAGE Independent Artifact QA",
        "",
        f"- Task: `{result.get('task_id', '')}`",
        f"- Scene/PRN/channel: `{result.get('scene_id', '')}/{result.get('prn', '')}/ch{result.get('tracking_channel', '')}`",
        f"- Sample rate: `{result.get('sample_rate_hz', '')} Hz`",
        f"- Output: `{result.get('output_dir', '')}`",
        f"- Execution receipt: `{result.get('execution_receipt_status', '')}`",
        "",
        "## QA decisions",
        "",
        f"- Identity: **{result.get('identity_status', '')}**",
        f"- Artifact completeness: **{result.get('artifact_completeness', '')}**",
        f"- Stage consistency: **{result.get('stage_consistency', '')}**",
        f"- Numerical validity: **{result.get('numerical_validity', '')}**",
        f"- Scientific status: **{result.get('scientific_status', '')}**",
        f"- Overall: **{result.get('overall_status', '')}**",
        "",
        "## Stage statistics",
        "",
        f"- Stage0 symbols: `{result.get('stage0_symbols')}`",
        f"- Stage0 windows: `{result.get('stage0_windows')}`",
        f"- Stage1 scanned windows: `{result.get('stage1_scanned_windows')}`",
        f"- Stage1 invalid windows: `{result.get('stage1_invalid_windows')}`",
        f"- Stage2 model rows: `{result.get('stage2_model_rows')}`",
        f"- Stage2 selected windows: `{result.get('stage2_selected_windows')}`",
        f"- Stage2 model order counts: `{json.dumps(result.get('stage2_model_order_counts', {}), sort_keys=True)}`",
        f"- Stage2 invalid model rows: `{result.get('stage2_invalid_models')}`",
        f"- Stage3 persistence rows: `{result.get('stage3_persistence_rows')}`",
        f"- Stage3 reliable centers: `{result.get('stage3_reliable_centers')}`",
        f"- Stage4 joint rows: `{result.get('stage4_joint_rows')}`",
        f"- Stage4 joint-valid rows: `{result.get('stage4_joint_valid_rows')}`",
        f"- Confirmed events: `{result.get('confirmed_events')}`",
        f"- Confirmed multipath paths: `{result.get('confirmed_multipath_paths')}`",
        "",
        "## Issues",
        "",
    ]
    issues = result.get("issues", [])
    lines.extend(f"- `{issue}`" for issue in issues) if issues else lines.append("- None")
    lines += [
        "",
        "## Scientific boundary",
        "",
        "Stage2 L>=2 and Stage3 reliable centers are not counted as confirmed multipath.",
        "Only `joint_valid=1`, `joint_multipath_count>0`, and a matching Stage4 path with `is_multipath=1` count as confirmed.",
        "A valid zero-event result is not interpreted as LOS or physical absence of multipath.",
        "",
        "## Audit side effects",
        "",
        "- Raw IQ opened by auditor: `NO`",
        "- MATLAB executed by auditor: `NO`",
        "- SAGE executed by auditor: `NO`",
        "- Existing artifact modified: `NO`",
    ]
    return "\n".join(lines) + "\n"


def write_audit_outputs(result: Mapping[str, Any], qa_output_dir: Path) -> None:
    if qa_output_dir.exists():
        raise FileExistsError(f"QA output namespace already exists: {qa_output_dir}")
    qa_output_dir.mkdir(parents=True)
    _write_new_json(qa_output_dir / "qa_result.json", result)
    _write_new_text(qa_output_dir / "qa_report.md", _report_text(result))
    artifact_rows = result.get("artifact_files", [])
    _write_new_csv(
        qa_output_dir / "artifact_hashes.csv",
        ("name", "path", "exists", "nonempty", "bytes", "sha256"),
        artifact_rows,
    )


def _task_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.task_json:
        return read_json(Path(args.task_json))
    required = {
        "task_id": args.task_id,
        "weather_condition": args.weather,
        "scene_id": args.scene_id,
        "prn": args.prn,
        "tracking_channel": args.tracking_channel,
        "sample_rate_hz": args.sample_rate_hz,
        "expected_valid_symbol_count": args.expected_valid_symbol_count,
        "expected_window_count": args.expected_window_count,
        "execution_receipt_path": args.execution_receipt_path,
    }
    return {key: value for key, value in required.items() if value not in (None, "")}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-json", help="Read-only task specification JSON")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--qa-output-dir", required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--weather")
    parser.add_argument("--scene-id")
    parser.add_argument("--prn")
    parser.add_argument("--tracking-channel", type=int)
    parser.add_argument("--sample-rate-hz", type=int, default=10230000)
    parser.add_argument("--expected-valid-symbol-count", type=int)
    parser.add_argument("--expected-window-count", type=int)
    parser.add_argument("--execution-receipt-path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    task = _task_from_args(args)
    output_dir = Path(args.output_dir)
    result = audit_task(task, output_dir)
    write_audit_outputs(result, Path(args.qa_output_dir))
    print(f"QA_RESULT={result['overall_status']}")
    print(f"QA_OUTPUT_DIR={args.qa_output_dir}")
    print(f"CONFIRMED_EVENTS={result['confirmed_events']}")
    print(f"CONFIRMED_PATHS={result['confirmed_multipath_paths']}")
    return 0 if result["overall_status"] in {"QA_PASS", "INCONCLUSIVE_NO_EXECUTION_RECEIPT"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
