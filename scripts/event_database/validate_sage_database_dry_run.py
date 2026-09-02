"""Read-only validator for the frozen GNSS SAGE event/path database rules.

The validator never opens raw IQ, MATLAB MAT inputs, or starts MATLAB/SAGE.  It
reads the frozen production manifest, immutable batch requests, QA summary,
run_context JSON and Stage0--Stage4 CSV outputs.  When a report directory is
provided, only the validator's own report files are written; no database fact
tables are created.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FILES = {
    "stage0_symbols": "stage0_valid_symbols.csv",
    "stage0_windows": "stage0_valid_40ms_windows.csv",
    "stage1_scan": "stage1_nav_fast_scan.csv",
    "stage2_models": "stage2_model_orders.csv",
    "stage2_windows": "stage2_selected_windows.csv",
    "stage2_paths": "stage2_selected_paths.csv",
    "stage3_persistence": "stage3_persistence.csv",
    "stage3_centers": "stage3_reliable_centers.csv",
    "stage4_summary": "stage4_joint_summary.csv",
    "stage4_paths": "stage4_joint_paths.csv",
}

REQUIRED_HEADERS = {
    "stage0_symbols": {
        "symbol_id",
        "recording_time_s",
    },
    "stage0_windows": {
        "window_id",
        "recording_time_s",
        "tow_s",
    },
    "stage1_scan": {
        "window_id",
        "recording_time_s",
        "scan_valid",
    },
    "stage2_models": {
        "window_id",
        "model_order",
        "multipath_count",
        "selected",
    },
    "stage2_windows": {
        "window_id",
        "recording_time_s",
        "selected_L",
        "multipath_count",
    },
    "stage2_paths": {
        "window_id",
        "selected_L",
        "path_id",
        "is_multipath",
    },
    "stage3_persistence": {
        "center_window_id",
        "multipath_id",
        "persistence_pass",
    },
    "stage3_centers": {
        "center_window_id",
        "recording_time_s",
        "selected_L",
        "multipath_count",
    },
    "stage4_summary": {
        "center_window_id",
        "joint_selected_L",
        "joint_multipath_count",
        "joint_valid",
    },
    "stage4_paths": {
        "center_window_id",
        "joint_selected_L",
        "path_id",
        "is_multipath",
    },
}

FROZEN_SOURCE_HASHES = {
    "pipeline_sha256": "bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c",
    "wrapper_sha256": "dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3",
    "executor_sha256": "bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b",
    "manifest_sha256": "77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00",
    "inventory_sha256": "af368feba90797584d7690d4927ed32de604651a5a62662f4adce348a89e4bb4",
}

REFERENCE_FIXTURE = [
    {
        "prn": "G06",
        "relative_output": "scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1",
        "channel": 4,
        "selected_windows": 95,
        "l_ge_2": 87,
        "l_ge_3": 58,
        "stage3_centers": 2,
        "stage4_rows": 2,
        "confirmed_events": 2,
        "confirmed_paths": 4,
        "label": "confirmed_multipath",
        "reference_control": False,
        "legacy_context_missing": True,
    },
    {
        "prn": "G11",
        "relative_output": "scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G11",
        "channel": 5,
        "selected_windows": 101,
        "l_ge_2": 56,
        "l_ge_3": 52,
        "stage3_centers": 7,
        "stage4_rows": 7,
        "confirmed_events": 1,
        "confirmed_paths": 1,
        "label": "confirmed_multipath",
        "reference_control": False,
        "legacy_context_missing": False,
    },
    {
        "prn": "G12",
        "relative_output": "scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G12",
        "channel": 6,
        "selected_windows": 96,
        "l_ge_2": 58,
        "l_ge_3": 46,
        "stage3_centers": 4,
        "stage4_rows": 4,
        "confirmed_events": 2,
        "confirmed_paths": 2,
        "label": "confirmed_multipath",
        "reference_control": False,
        "legacy_context_missing": False,
    },
    {
        "prn": "G25",
        "relative_output": "scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G25",
        "channel": 0,
        "selected_windows": 52,
        "l_ge_2": 12,
        "l_ge_3": 10,
        "stage3_centers": 0,
        "stage4_rows": 0,
        "confirmed_events": 0,
        "confirmed_paths": 0,
        "label": "los_reference",
        "reference_control": True,
        "legacy_context_missing": False,
    },
    {
        "prn": "G28",
        "relative_output": "scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G28",
        "channel": 1,
        "selected_windows": 54,
        "l_ge_2": 12,
        "l_ge_3": 8,
        "stage3_centers": 2,
        "stage4_rows": 2,
        "confirmed_events": 0,
        "confirmed_paths": 0,
        "label": "rejected_candidate",
        "reference_control": False,
        "legacy_context_missing": False,
    },
    {
        "prn": "G29",
        "relative_output": "scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G29",
        "channel": 7,
        "selected_windows": 77,
        "l_ge_2": 32,
        "l_ge_3": 26,
        "stage3_centers": 1,
        "stage4_rows": 1,
        "confirmed_events": 1,
        "confirmed_paths": 1,
        "label": "confirmed_multipath",
        "reference_control": False,
        "legacy_context_missing": False,
    },
    {
        "prn": "G32",
        "relative_output": "scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G32",
        "channel": 11,
        "selected_windows": 117,
        "l_ge_2": 86,
        "l_ge_3": 71,
        "stage3_centers": 11,
        "stage4_rows": 8,
        "confirmed_events": 2,
        "confirmed_paths": 3,
        "label": "confirmed_multipath",
        "reference_control": False,
        "legacy_context_missing": False,
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_csv(path: Path, required_headers: Iterable[str]) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        return [], [f"missing_file:{path.name}"]

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = sorted(set(required_headers) - headers)
        issues = [f"missing_header:{path.name}:{name}" for name in missing]
        if not reader.fieldnames:
            issues.append(f"missing_header_row:{path.name}")
            return [], issues
        rows = [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
        ]
    return rows, issues


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any, default: int | None = None) -> int | None:
    text = _text(value)
    if text == "":
        return default
    try:
        number = float(text)
        if not number.is_integer():
            return default
        return int(number)
    except (TypeError, ValueError):
        return default


def _float(value: Any) -> float | None:
    text = _text(value)
    if text == "":
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_one(value: Any) -> bool:
    return _text(value).lower() in {"1", "true"}


def _unique_values(rows: list[dict[str, str]], field: str) -> tuple[set[str], list[str]]:
    values = [_text(row.get(field)) for row in rows]
    duplicates = sorted(value for value, count in Counter(values).items() if value and count > 1)
    return {value for value in values if value}, duplicates


def strict_confirmation(
    summary_row: dict[str, Any], path_rows: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """Apply the frozen Stage4 confirmation rule to one summary row."""

    issues: list[str] = []
    joint_valid = _int(summary_row.get("joint_valid"), default=None)
    joint_multipath_count = _int(summary_row.get("joint_multipath_count"), default=None)
    path_multipath_count = sum(1 for row in path_rows if _is_one(row.get("is_multipath")))

    if joint_valid is None:
        issues.append("joint_valid_missing_or_non_integer")
    if joint_multipath_count is None:
        issues.append("joint_multipath_count_missing_or_non_integer")
    if joint_multipath_count is not None and joint_multipath_count != path_multipath_count:
        issues.append("joint_multipath_count_mismatch")

    confirmed = (
        joint_valid == 1
        and joint_multipath_count is not None
        and joint_multipath_count > 0
        and path_multipath_count > 0
        and not issues
    )
    return confirmed, issues


def classify_run_label(
    confirmed_events: int,
    *,
    run_scope: str,
    reference_control: bool,
) -> str:
    if confirmed_events > 0:
        return "confirmed_multipath"
    if run_scope == "reference" and reference_control:
        return "los_reference"
    return "no_confirmed_event"


def reference_count_key(reference_key: str) -> str:
    return {
        "selected_windows": "stage2_selected",
        "l_ge_2": "stage2_l_ge_2",
        "l_ge_3": "stage2_l_ge_3",
        "stage3_centers": "stage3_reliable_centers",
        "stage4_rows": "stage4_rows",
        "confirmed_events": "confirmed_events",
        "confirmed_paths": "confirmed_paths",
    }[reference_key]


def request_hash_key(frozen_hash_key: str) -> str:
    return {
        "pipeline_sha256": "pipeline_sha256",
        "wrapper_sha256": "wrapper_sha256",
        "executor_sha256": "python_executor_sha256",
        "manifest_sha256": "production_manifest_sha256",
        "inventory_sha256": "production_inventory_sha256",
    }[frozen_hash_key]


def _add_duplicate_issue(issues: list[str], table_name: str, field: str, duplicates: list[str]) -> None:
    if duplicates:
        issues.append(f"duplicate_key:{table_name}:{field}:{','.join(duplicates[:5])}")


def _finite_path_fields(
    rows: list[dict[str, str]], table_name: str, fields: Iterable[str], issues: list[str]
) -> None:
    for index, row in enumerate(rows, start=2):
        for field in fields:
            value = _text(row.get(field))
            if value and _float(value) is None:
                issues.append(f"non_finite_numeric:{table_name}:row{index}:{field}")


def _compare_count(
    issues: list[str], label: str, actual: int, expected: Any, task_id: str = ""
) -> None:
    parsed = _int(expected, default=None)
    if parsed is not None and actual != parsed:
        prefix = f"{task_id}:" if task_id else ""
        issues.append(f"summary_count_mismatch:{prefix}{label}:actual={actual}:expected={parsed}")


def validate_output_namespace(
    output_dir: Path,
    *,
    expected_identity: dict[str, Any] | None = None,
    summary_row: dict[str, Any] | None = None,
    reference_expected: dict[str, Any] | None = None,
    allow_legacy_context_missing: bool = False,
    scope: str = "batch",
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    tables: dict[str, list[dict[str, str]]] = {}

    if not output_dir.is_dir():
        return {
            "output_dir": str(output_dir),
            "status": "FAIL",
            "issues": [f"missing_output_directory:{output_dir}"],
            "warnings": [],
            "counts": {},
        }

    context_path = output_dir / "run_context.json"
    context: dict[str, Any] | None = None
    if context_path.is_file():
        try:
            context = load_json(context_path)
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"invalid_run_context:{type(exc).__name__}")
    elif allow_legacy_context_missing:
        warnings.append("context_missing_legacy_adapter_required")
    else:
        issues.append("missing_run_context_json")

    if context is not None and expected_identity is not None:
        context_checks = {
            "sceneId": expected_identity.get("scene_id"),
            "prnLabel": expected_identity.get("prn"),
            "trackingChannel": _int(expected_identity.get("channel"), default=None),
            "samplingRateHz": _float(expected_identity.get("sample_rate_hz")),
        }
        for field, expected in context_checks.items():
            actual = context.get(field)
            if field == "samplingRateHz":
                if actual is None or expected is None or abs(float(actual) - expected) > 0.5:
                    issues.append(f"run_context_mismatch:{field}:actual={actual}:expected={expected}")
            elif actual != expected:
                issues.append(f"run_context_mismatch:{field}:actual={actual}:expected={expected}")

    for key, filename in REQUIRED_FILES.items():
        rows, table_issues = load_csv(output_dir / filename, REQUIRED_HEADERS[key])
        tables[key] = rows
        issues.extend(table_issues)

    stage0_windows = tables["stage0_windows"]
    stage1_scan = tables["stage1_scan"]
    stage2_models = tables["stage2_models"]
    stage2_windows = tables["stage2_windows"]
    stage2_paths = tables["stage2_paths"]
    stage3_persistence = tables["stage3_persistence"]
    stage3_centers = tables["stage3_centers"]
    stage4_summary = tables["stage4_summary"]
    stage4_paths = tables["stage4_paths"]

    stage0_ids, duplicates = _unique_values(stage0_windows, "window_id")
    _add_duplicate_issue(issues, "stage0_windows", "window_id", duplicates)
    stage1_ids, duplicates = _unique_values(stage1_scan, "window_id")
    _add_duplicate_issue(issues, "stage1_scan", "window_id", duplicates)
    selected_ids, duplicates = _unique_values(stage2_windows, "window_id")
    _add_duplicate_issue(issues, "stage2_windows", "window_id", duplicates)
    center_ids, duplicates = _unique_values(stage3_centers, "center_window_id")
    _add_duplicate_issue(issues, "stage3_centers", "center_window_id", duplicates)
    summary_ids, duplicates = _unique_values(stage4_summary, "center_window_id")
    _add_duplicate_issue(issues, "stage4_summary", "center_window_id", duplicates)

    if stage0_ids != stage1_ids:
        issues.append("stage0_stage1_window_id_mismatch")
    if not selected_ids.issubset(stage0_ids):
        issues.append("stage2_selected_window_not_in_stage0")
    if not center_ids.issubset(selected_ids):
        issues.append("stage3_center_not_in_stage2_selected_windows")
    if not summary_ids.issubset(center_ids):
        issues.append("stage4_center_not_in_stage3_reliable_centers")

    model_by_window: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stage2_models:
        model_by_window[_text(row.get("window_id"))].append(row)
    for window_id in selected_ids:
        rows = model_by_window.get(window_id, [])
        orders = sorted(_int(row.get("model_order"), default=-1) for row in rows)
        if orders != [1, 2, 3, 4]:
            issues.append(f"stage2_model_order_set_mismatch:{window_id}:{orders}")
        selected_rows = [row for row in rows if _is_one(row.get("selected"))]
        selected_l = next(
            (_int(row.get("selected_L"), default=None) for row in stage2_windows if _text(row.get("window_id")) == window_id),
            None,
        )
        selected_orders = [_int(row.get("model_order"), default=None) for row in selected_rows]
        if len(selected_rows) != 1 or selected_l not in selected_orders:
            issues.append(f"stage2_selected_model_mismatch:{window_id}")

    stage2_paths_by_window: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stage2_paths:
        stage2_paths_by_window[_text(row.get("window_id"))].append(row)
    expected_stage2_paths = 0
    for row in stage2_windows:
        window_id = _text(row.get("window_id"))
        selected_l = _int(row.get("selected_L"), default=None)
        if selected_l is None:
            issues.append(f"invalid_selected_L:{window_id}")
            continue
        expected_stage2_paths += selected_l
        if len(stage2_paths_by_window.get(window_id, [])) != selected_l:
            issues.append(f"stage2_path_count_mismatch:{window_id}")
    if len(stage2_paths) != expected_stage2_paths:
        issues.append(
            f"stage2_path_total_mismatch:actual={len(stage2_paths)}:expected={expected_stage2_paths}"
        )

    stage4_paths_by_center: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in stage4_paths:
        stage4_paths_by_center[_text(row.get("center_window_id"))].append(row)
    if not set(stage4_paths_by_center).issubset(summary_ids):
        issues.append("stage4_path_center_not_in_summary")

    strict_events = 0
    strict_paths = 0
    stage4_joint_valid = 0
    stage4_rule_issues: list[str] = []
    for row in stage4_summary:
        center_id = _text(row.get("center_window_id"))
        joint_selected_l = _int(row.get("joint_selected_L"), default=None)
        if joint_selected_l is None:
            issues.append(f"invalid_joint_selected_L:{center_id}")
        elif len(stage4_paths_by_center.get(center_id, [])) != joint_selected_l:
            issues.append(f"stage4_path_count_mismatch:{center_id}")
        if _int(row.get("joint_valid"), default=None) not in {0, 1}:
            issues.append(f"invalid_joint_valid:{center_id}")
        if _is_one(row.get("joint_valid")):
            stage4_joint_valid += 1
        confirmed, rule_issues = strict_confirmation(row, stage4_paths_by_center.get(center_id, []))
        if rule_issues:
            stage4_rule_issues.extend(f"{center_id}:{item}" for item in rule_issues)
        if confirmed:
            strict_events += 1
            strict_paths += sum(
                1
                for path_row in stage4_paths_by_center.get(center_id, [])
                if _is_one(path_row.get("is_multipath"))
            )
    issues.extend(f"stage4_rule:{item}" for item in stage4_rule_issues)

    _finite_path_fields(
        stage2_paths,
        "stage2_paths",
        (
            "delay_samples",
            "excess_delay_samples",
            "excess_delay_chips",
            "excess_path_length_m",
            "doppler_hz",
            "doppler_offset_hz",
            "relative_power_db",
        ),
        issues,
    )
    _finite_path_fields(
        stage4_paths,
        "stage4_paths",
        (
            "delay_samples",
            "excess_delay_samples",
            "excess_delay_chips",
            "doppler_hz",
            "doppler_offset_hz",
            "mean_relative_power_db",
        ),
        issues,
    )

    counts = {
        "stage0_symbols": len(tables["stage0_symbols"]),
        "stage0_windows": len(stage0_windows),
        "stage1_scanned": len(stage1_scan),
        "stage2_evaluations": len(stage2_models),
        "stage2_selected": len(stage2_windows),
        "stage2_l_ge_2": sum(1 for row in stage2_windows if (_int(row.get("selected_L"), 0) or 0) >= 2),
        "stage2_l_ge_3": sum(1 for row in stage2_windows if (_int(row.get("selected_L"), 0) or 0) >= 3),
        "stage2_paths": len(stage2_paths),
        "stage3_persistence_rows": len(stage3_persistence),
        "stage3_reliable_centers": len(stage3_centers),
        "stage4_rows": len(stage4_summary),
        "stage4_joint_valid": stage4_joint_valid,
        "confirmed_events": strict_events,
        "confirmed_paths": strict_paths,
    }

    if summary_row is not None:
        task_id = _text(summary_row.get("task_id"))
        summary_mapping = {
            "stage0_windows": "stage0_windows",
            "stage1_scanned": "stage1_scanned",
            "stage2_evaluations": "stage2_evaluations",
            "stage2_selected": "stage1_selected",
            "stage3_reliable_centers": "stage3_reliable_centers",
            "stage4_rows": "stage4_rows",
            "stage4_joint_valid": "stage4_joint_valid",
            "confirmed_events": "confirmed_events",
            "confirmed_paths": "confirmed_paths",
        }
        for count_key, summary_key in summary_mapping.items():
            _compare_count(issues, count_key, counts[count_key], summary_row.get(summary_key), task_id)
        if _text(summary_row.get("execution_status")) != "completed":
            issues.append(f"summary_execution_not_completed:{task_id}")
        if _text(summary_row.get("QA_status")) != "PASS":
            issues.append(f"summary_qa_not_pass:{task_id}")
        if _text(summary_row.get("missing_required_files")):
            issues.append(f"summary_missing_required_files:{task_id}")
        if _text(summary_row.get("warnings")):
            issues.append(f"summary_warnings_present:{task_id}")
        for provenance_key in ("execution_log_path", "qa_report_path"):
            provenance_path = Path(_text(summary_row.get(provenance_key)))
            if not provenance_path.is_file():
                issues.append(f"missing_provenance_file:{task_id}:{provenance_key}")

    if reference_expected is not None:
        for key in (
            "selected_windows",
            "l_ge_2",
            "l_ge_3",
            "stage3_centers",
            "stage4_rows",
            "confirmed_events",
            "confirmed_paths",
        ):
            actual_key = reference_count_key(key)
            if counts[actual_key] != reference_expected[key]:
                issues.append(
                    f"reference_regression_mismatch:{reference_expected['prn']}:{key}:"
                    f"actual={counts[actual_key]}:expected={reference_expected[key]}"
                )

    if reference_expected is not None and reference_expected.get("label") == "rejected_candidate":
        run_label = "rejected_candidate"
    else:
        run_label = classify_run_label(
            strict_events,
            run_scope=scope,
            reference_control=bool((reference_expected or {}).get("reference_control", False)),
        )
    if reference_expected is not None and run_label != reference_expected.get("label"):
        issues.append(
            f"reference_label_mismatch:{reference_expected['prn']}:"
            f"actual={run_label}:expected={reference_expected['label']}"
        )

    return {
        "output_dir": str(output_dir),
        "status": "PASS" if not issues else "FAIL",
        "issues": sorted(set(issues)),
        "warnings": sorted(set(warnings)),
        "counts": counts,
        "run_label": run_label,
        "geometry_join_status": "deferred_unavailable",
        "formal_event_context_written": False,
    }


def _load_summary(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    rows, issues = load_csv(path, {"task_id", "execution_status", "QA_status", "result_directory"})
    return rows, issues


def _manifest_task_id_from_plan(plan_row: dict[str, str]) -> str:
    return _text(plan_row.get("production_task_id"))


def validate_current_batch(
    root: Path,
    manifest_path: Path,
    summary_path: Path,
    requests_root: Path,
    *,
    run_id: str,
    qa_report_path: Path,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    manifest = load_json(manifest_path)
    manifest_tasks = {_text(task.get("task_id")): task for task in manifest.get("tasks", [])}
    summary_rows, summary_issues = _load_summary(summary_path)
    issues.extend(summary_issues)
    summary_by_task = {_text(row.get("task_id")): row for row in summary_rows}

    request_dirs = sorted(
        path
        for path in requests_root.glob(f"windows_unattended_*_{run_id}_*")
        if path.is_dir()
    )
    if len(request_dirs) != 57:
        issues.append(f"unexpected_request_cardinality:{len(request_dirs)}:expected=57")
    if not qa_report_path.is_file():
        issues.append(f"missing_batch_qa_report:{qa_report_path}")
    else:
        qa_text = qa_report_path.read_text(encoding="utf-8-sig")
        if "FINAL QA VERDICT: **PASS**" not in qa_text or "QA_RESULT: **57/57 task-level ACCEPTED; 0 REJECTED**" not in qa_text:
            issues.append("batch_qa_report_verdict_not_pass")

    actual_task_ids: list[str] = []
    task_results: list[dict[str, Any]] = []
    batch_counts: Counter[str] = Counter()
    for request_dir in request_dirs:
        request_path = request_dir / "execution_request.json"
        plan_path = request_dir / "approved_plan_snapshot.csv"
        if not request_path.is_file() or not plan_path.is_file():
            issues.append(f"missing_request_provenance:{request_dir.name}")
            continue
        try:
            request = load_json(request_path)
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"invalid_execution_request:{request_dir.name}:{type(exc).__name__}")
            continue
        plan_rows, plan_issues = load_csv(
            plan_path,
            {"task_id", "scene_id", "prn", "tracking_channel", "output_path", "sample_rate_hz", "production_task_id"},
        )
        issues.extend(f"{request_dir.name}:{item}" for item in plan_issues)
        if len(plan_rows) != 1:
            issues.append(f"request_plan_cardinality:{request_dir.name}:{len(plan_rows)}")
            continue
        plan_row = plan_rows[0]
        task_id = _text(request.get("ordered_task_ids", [""])[0])
        actual_task_ids.append(task_id)
        if _text(request.get("request_id")) != request_dir.name:
            issues.append(f"request_id_directory_mismatch:{request_dir.name}")
        for key, expected in FROZEN_SOURCE_HASHES.items():
            request_key = request_hash_key(key)
            if _text(request.get(request_key)) != expected:
                issues.append(f"request_frozen_hash_mismatch:{request_dir.name}:{request_key}")
        if request.get("new_only") is not True or request.get("resume_allowed") is not False:
            issues.append(f"request_safety_contract_mismatch:{request_dir.name}")
        if _int(request.get("max_parallel_matlab"), default=None) != 1:
            issues.append(f"request_parallelism_mismatch:{request_dir.name}")
        if 10230000 not in [int(value) for value in request.get("allowed_sample_rates_hz", [])]:
            issues.append(f"request_sample_rate_contract_mismatch:{request_dir.name}")

        manifest_task_id = _manifest_task_id_from_plan(plan_row)
        manifest_task = manifest_tasks.get(manifest_task_id)
        if manifest_task is None:
            issues.append(f"manifest_task_missing:{request_dir.name}:{manifest_task_id}")
            continue
        batch = _text(manifest_task.get("batch"))
        batch_counts[batch] += 1
        if _text(manifest_task.get("scene_id")) != _text(plan_row.get("scene_id")):
            issues.append(f"manifest_plan_scene_mismatch:{task_id}")
        if _text(manifest_task.get("PRN")) != _text(plan_row.get("prn")):
            issues.append(f"manifest_plan_prn_mismatch:{task_id}")
        if _int(manifest_task.get("tracking_channel"), None) != _int(plan_row.get("tracking_channel"), None):
            issues.append(f"manifest_plan_channel_mismatch:{task_id}")
        if _int(manifest_task.get("sample_rate_hz"), None) != _int(plan_row.get("sample_rate_hz"), None):
            issues.append(f"manifest_plan_rate_mismatch:{task_id}")

        summary_row = summary_by_task.get(task_id)
        if summary_row is None:
            issues.append(f"summary_task_missing:{task_id}")
        expected_identity = {
            "scene_id": _text(plan_row.get("scene_id")),
            "prn": _text(plan_row.get("prn")),
            "channel": _int(plan_row.get("tracking_channel"), None),
            "sample_rate_hz": _int(plan_row.get("sample_rate_hz"), None),
        }
        output_dir = Path(_text(plan_row.get("output_path")))
        if str(output_dir).lower().find(str(root).lower()) != 0:
            issues.append(f"output_path_outside_project:{task_id}")
        if "F1023_V70_D0120_P5" in str(output_dir) and output_dir.name.upper() == "G16":
            issues.append(f"protected_historical_output_in_batch:{task_id}")
        row_result = validate_output_namespace(
            output_dir,
            expected_identity=expected_identity,
            summary_row=summary_row,
            scope="batch",
        )
        row_result["task_id"] = task_id
        row_result["production_task_id"] = manifest_task_id
        row_result["batch"] = batch
        task_results.append(row_result)
        issues.extend(f"{task_id}:{item}" for item in row_result["issues"])
        warnings.extend(f"{task_id}:{item}" for item in row_result["warnings"])

    if len(set(actual_task_ids)) != len(actual_task_ids):
        issues.append("duplicate_request_task_id")
    if set(actual_task_ids) != set(summary_by_task).intersection(set(actual_task_ids)):
        issues.append("request_summary_task_set_mismatch")

    actual_hashes = {
        "pipeline_sha256": sha256_file(root / "scripts/sage_pipeline/run_nav_sage_pipeline.m"),
        "wrapper_sha256": sha256_file(root / "scripts/sage_pipeline/Invoke-BatchSageWindows.ps1"),
        "executor_sha256": sha256_file(root / "scripts/sage_pipeline/run_batch_sage.py"),
        "manifest_sha256": sha256_file(manifest_path),
        "inventory_sha256": sha256_file(root / "dataset_generation_logs/production_planning_10mhz_20260812/production_inventory_10MHz.csv"),
    }
    for key, expected in FROZEN_SOURCE_HASHES.items():
        if actual_hashes[key] != expected:
            issues.append(f"actual_frozen_hash_mismatch:{key}")

    state_path = root / "dataset_generation_logs/batch_sage_unattended/run_20260819T004818Z/runner_state.json"
    runner_state = load_json(state_path) if state_path.is_file() else None
    if runner_state is None:
        warnings.append("runner_state_unavailable")
    elif runner_state.get("status") != "completed_pending_batch_qa":
        issues.append(f"runner_state_status_unexpected:{runner_state.get('status')}")

    aggregate = Counter()
    for row_result in task_results:
        aggregate.update(row_result.get("counts", {}))
    result = {
        "status": "PASS" if not issues else "FAIL",
        "request_count": len(request_dirs),
        "task_result_count": len(task_results),
        "batch_counts": dict(sorted(batch_counts.items())),
        "aggregate_counts": dict(sorted(aggregate.items())),
        "actual_task_ids": actual_task_ids,
        "task_results": sorted(task_results, key=lambda item: item.get("task_id", "")),
        "issues": sorted(set(issues)),
        "warnings": sorted(set(warnings)),
        "actual_hashes": actual_hashes,
        "runner_state": runner_state,
        "formal_ingest_allowed": False,
        "database_fact_tables_written": False,
        "geometry_event_context_written": False,
    }
    return result


def validate_reference_fixture(root: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    issues: list[str] = []
    warnings: list[str] = []
    for expected in REFERENCE_FIXTURE:
        output_dir = root / Path(expected["relative_output"])
        identity = {
            "scene_id": "F1023_V70_D0117_P2",
            "prn": expected["prn"],
            "channel": expected["channel"],
            "sample_rate_hz": 10230000,
        }
        result = validate_output_namespace(
            output_dir,
            expected_identity=identity,
            reference_expected=expected,
            allow_legacy_context_missing=bool(expected.get("legacy_context_missing")),
            scope="reference",
        )
        result["prn"] = expected["prn"]
        results.append(result)
        issues.extend(f"{expected['prn']}:{item}" for item in result["issues"])
        warnings.extend(f"{expected['prn']}:{item}" for item in result["warnings"])
    aggregate = Counter()
    for result in results:
        aggregate.update(result.get("counts", {}))
    return {
        "status": "PASS" if not issues else "FAIL",
        "fixture_count": len(results),
        "results": results,
        "aggregate_counts": dict(sorted(aggregate.items())),
        "issues": sorted(set(issues)),
        "warnings": sorted(set(warnings)),
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def build_markdown_report(result: dict[str, Any]) -> str:
    batch = result["current_batch"]
    reference = result["reference_fixture"]
    lines = [
        "# GNSS SAGE Event/Path Database Rules v1 — Read-only Dry-run Report",
        "",
        f"- Validator UTC: `{result['validator_utc']}`",
        f"- Overall dry-run result: **{result['status']}**",
        "- Formal database ingest: **BLOCKED / NOT PERFORMED**",
        "- MATLAB/SAGE/raw IQ: **not started / not read**",
        "- Existing Stage artifacts, manifest, requests, metadata and inventory: **not modified**",
        "",
        "## Frozen rules",
        "",
        "- Schema: `sage-event-path-db-v1`; normalized run/window/candidate/event/path/context layers.",
        "- Strict confirmed event: `joint_valid == 1` AND `joint_multipath_count > 0` AND the corresponding Stage4 path rows contain `is_multipath == 1`; the summary/path counts must agree.",
        "- A zero confirmed-event run is `no_confirmed_event`, never an automatic physical LOS label.",
        "- `los_reference` is allowed only for an explicit reference/control manifest entry with zero confirmed events.",
        "- Stage2 and Stage3 candidates remain candidates; they are not promoted to confirmed paths.",
        "- Event-level geometry/elevation/azimuth remains null/deferred until a verified time alignment exists.",
        "- Stage4 source power remains `mean_relative_power_db`; it is not silently renamed to Stage2 `relative_power_db`.",
        "- Source provenance is required; formal facts are not written by this dry-run.",
        "",
        "## Frozen source hashes",
        "",
        "| Source | SHA-256 |",
        "|---|---|",
    ]
    for key, value in result["frozen_hashes"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "## Current unattended batch",
            "",
            f"- Requests checked: `{batch['request_count']}`; task namespaces checked: `{batch['task_result_count']}`.",
            f"- Batch validator status: **{batch['status']}**.",
            f"- Batch labels: `{batch['batch_counts']}`.",
            f"- Aggregate Stage0 windows: `{batch['aggregate_counts'].get('stage0_windows', 0)}`.",
            f"- Aggregate Stage2 selected windows: `{batch['aggregate_counts'].get('stage2_selected', 0)}`.",
            f"- Aggregate Stage3 reliable centers: `{batch['aggregate_counts'].get('stage3_reliable_centers', 0)}`.",
            f"- Aggregate Stage4 rows: `{batch['aggregate_counts'].get('stage4_rows', 0)}`; strict confirmed events/paths: `{batch['aggregate_counts'].get('confirmed_events', 0)}/{batch['aggregate_counts'].get('confirmed_paths', 0)}`.",
            "",
            "## Reference seven-PRN regression fixture",
            "",
            f"- Fixture status: **{reference['status']}**; runs checked: `{reference['fixture_count']}`.",
            "- Expected regression total: 8 confirmed events and 11 confirmed multipath paths.",
            "",
            "| PRN | Stage2 selected | L≥2 | L≥3 | Stage3 | Stage4 | Confirmed events | Confirmed paths | Label |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in sorted(reference["results"], key=lambda value: value.get("prn", "")):
        counts = item.get("counts", {})
        lines.append(
            f"| {item.get('prn')} | {counts.get('stage2_selected', 0)} | {counts.get('stage2_l_ge_2', 0)} | {counts.get('stage2_l_ge_3', 0)} | {counts.get('stage3_reliable_centers', 0)} | {counts.get('stage4_rows', 0)} | {counts.get('confirmed_events', 0)} | {counts.get('confirmed_paths', 0)} | {item.get('run_label')} |"
        )
    lines.extend(
        [
            "",
            "## Gate decision",
            "",
            "- Dry-run validation is an evidence gate only; it does not create `sage_runs`, `events`, `event_paths`, `event_context`, channel-parameter or statistical-model tables.",
            "- Geometry alignment and channel-parameter derivation remain pending.",
            "- The next step is a separately authorized formal ingest after this report is reviewed; statistical modeling remains blocked.",
            "",
            "## Issues and warnings",
            "",
        ]
    )
    issues = result["issues"]
    warnings = result["warnings"]
    if not issues and not warnings:
        lines.append("- None.")
    else:
        for item in issues:
            lines.append(f"- ERROR: `{item}`")
        for item in warnings:
            lines.append(f"- WARNING: `{item}`")
    return "\n".join(lines) + "\n"


def run_validation(root: Path, *, run_id: str, report_dir: Path | None) -> dict[str, Any]:
    manifest_path = root / "dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json"
    summary_path = root / "dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv"
    requests_root = root / "dataset_generation_logs/batch_sage_execution_requests"
    qa_report_path = root / "docs/10MHz_FULL_SAGE_UNATTENDED_BATCH_20260819_QA_REPORT.md"
    current_batch = validate_current_batch(
        root,
        manifest_path,
        summary_path,
        requests_root,
        run_id=run_id,
        qa_report_path=qa_report_path,
    )
    reference_fixture = validate_reference_fixture(root)

    rules_dir = root / "dataset/multipath_event_database/v1/_schema"
    rule_files = {}
    for filename in ("schema.json", "enums.json", "label_rules.json", "derivation_manifest.json"):
        path = rules_dir / filename
        if not path.is_file():
            current_batch["issues"].append(f"missing_frozen_rule_file:{filename}")
            reference_fixture["issues"].append(f"missing_frozen_rule_file:{filename}")
        else:
            rule_files[filename] = {
                "path": str(path),
                "sha256": sha256_file(path),
            }

    all_issues = sorted(set(current_batch["issues"] + reference_fixture["issues"]))
    all_warnings = sorted(set(current_batch["warnings"] + reference_fixture["warnings"]))
    result = {
        "validator_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "PASS" if not all_issues else "FAIL",
        "frozen_hashes": dict(FROZEN_SOURCE_HASHES),
        "frozen_rule_files": rule_files,
        "current_batch": current_batch,
        "reference_fixture": reference_fixture,
        "issues": all_issues,
        "warnings": all_warnings,
        "formal_ingest_allowed": False,
        "database_fact_tables_written": False,
        "geometry_event_context_written": False,
        "channel_parameter_derivation_started": False,
        "statistical_modeling_started": False,
    }
    result["current_batch"]["status"] = "PASS" if not result["current_batch"]["issues"] else "FAIL"
    result["reference_fixture"]["status"] = "PASS" if not result["reference_fixture"]["issues"] else "FAIL"

    if report_dir is not None:
        report_dir.mkdir(parents=True, exist_ok=True)
        json_path = report_dir / "database_dry_run_result.json"
        markdown_path = report_dir / "database_dry_run_report.md"
        json_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(build_markdown_report(result), encoding="utf-8")
        result["report_paths"] = {
            "json": str(json_path),
            "markdown": str(markdown_path),
        }
        # Re-write JSON once so it records its sibling report paths.
        json_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n",
            encoding="utf-8",
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--run-id", default="20260819T004818Z")
    parser.add_argument("--report-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = run_validation(args.root.resolve(), run_id=args.run_id, report_dir=args.report_dir)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"DRY_RUN_VALIDATOR_ERROR={type(exc).__name__}:{exc}", file=sys.stderr)
        return 2
    print(
        "DRY_RUN_RESULT="
        f"{result['status']}|batch={result['current_batch']['status']}|"
        f"reference={result['reference_fixture']['status']}|"
        f"issues={len(result['issues'])}|warnings={len(result['warnings'])}"
    )
    print(
        "DRY_RUN_SCOPE="
        f"current_batch_tasks={result['current_batch']['task_result_count']}|"
        f"reference_runs={result['reference_fixture']['fixture_count']}|"
        "formal_ingest_allowed=False|database_fact_tables_written=False|"
        "geometry_event_context_written=False|statistical_modeling_started=False"
    )
    if result["issues"]:
        for issue in result["issues"][:20]:
            print(f"ERROR={issue}")
        return 1
    for warning in result["warnings"][:20]:
        print(f"WARNING={warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
