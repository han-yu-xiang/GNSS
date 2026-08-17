"""Read-only summary of existing 10.23 MHz full-SAGE result directories.

This utility never opens raw IQ files and never invokes MATLAB, SAGE, or a
batch executor.  It reads only existing ``nav_sage_v2`` JSON/CSV metadata,
execution logs/receipts, and QA markdown files, then writes monitoring
artifacts under ``dataset_generation_logs/production_monitoring_10MHz``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SAMPLE_RATE_HZ = 10_230_000
DEFAULT_OUTPUT_RELATIVE = Path("dataset_generation_logs/production_monitoring_10MHz")

REQUIRED_OUTPUT_FILES = (
    "run_context.json",
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

SUMMARY_FIELDS = (
    "task_id",
    "scene_id",
    "PRN",
    "channel",
    "sample_rate_hz",
    "result_scope",
    "execution_status",
    "QA_status",
    "runtime_seconds",
    "stage0_windows",
    "stage1_scanned",
    "stage1_selected",
    "stage1_selected_source",
    "stage2_evaluations",
    "stage3_reliable_centers",
    "stage4_rows",
    "stage4_joint_valid",
    "confirmed_events",
    "confirmed_paths",
    "result_directory",
    "output_file_count",
    "required_file_count",
    "nonempty_file_count",
    "missing_required_files",
    "execution_log_path",
    "qa_report_path",
    "provenance_status",
    "warnings",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Project root; defaults to the repository containing this script.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Monitoring output directory; defaults to the fixed 10 MHz namespace.",
    )
    return parser.parse_args(argv)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{path.name}:json_read_error:{type(exc).__name__}"
    if not isinstance(value, dict):
        return None, f"{path.name}:json_root_not_object"
    return value, None


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]] | None, str | None]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle)), None
    except (OSError, UnicodeError, csv.Error) as exc:
        return None, f"{path.name}:csv_read_error:{type(exc).__name__}"


def as_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def csv_value(value: Any) -> str | int | float:
    return "" if value is None else value


def normalize_path(path_value: Any) -> str:
    if not path_value:
        return ""
    try:
        return os.path.normcase(os.path.abspath(str(path_value)))
    except (OSError, TypeError, ValueError):
        return str(path_value).casefold()


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def derive_runtime(row: dict[str, str]) -> float | None:
    direct = as_float(row.get("duration_seconds"))
    if direct is not None:
        return direct
    start = parse_time(row.get("start_time_utc"))
    end = parse_time(row.get("end_time_utc"))
    if start is None or end is None:
        return None
    return (end - start).total_seconds()


def task_key(scene_id: str, prn: str, channel: Any) -> str:
    channel_value = as_int(channel)
    channel_text = str(channel_value if channel_value is not None else channel).strip()
    return f"{scene_id}__{prn}__ch{channel_text}__nav_sage_v2"


def discover_result_dirs(project_root: Path) -> list[Path]:
    scenes_dir = project_root / "scenes"
    if not scenes_dir.is_dir():
        return []
    result_dirs: list[Path] = []
    for scene_dir in sorted(scenes_dir.iterdir()):
        nav_dir = scene_dir / "sage_results" / "nav_sage_v2"
        if not nav_dir.is_dir():
            continue
        for result_dir in sorted(nav_dir.iterdir()):
            if result_dir.is_dir() and any(child.is_file() for child in result_dir.iterdir()):
                result_dirs.append(result_dir)
    return result_dirs


def load_production_task_keys(project_root: Path) -> set[tuple[str, str]]:
    manifest_path = (
        project_root
        / "dataset_generation_logs"
        / "production_planning_10mhz_20260812"
        / "production_task_manifest_10MHz_v1.json"
    )
    manifest, _ = read_json(manifest_path)
    if not manifest:
        return set()
    tasks = manifest.get("tasks", [])
    if not isinstance(tasks, list):
        return set()
    keys: set[tuple[str, str]] = set()
    for task in tasks:
        if not isinstance(task, dict):
            continue
        scene_id = str(task.get("scene_id", "")).strip()
        prn = str(task.get("PRN", task.get("prn", ""))).strip().upper()
        if scene_id and prn:
            keys.add((scene_id, prn))
    return keys


def load_execution_records(project_root: Path) -> list[dict[str, Any]]:
    base = project_root / "dataset_generation_logs" / "batch_sage_execution"
    if not base.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for log_path in sorted(base.rglob("batch_execution_log.csv")):
        rows, error = read_csv_rows(log_path)
        if rows is None:
            continue
        for row in rows:
            row_copy: dict[str, Any] = dict(row)
            row_copy["_execution_log_path"] = str(log_path)
            row_copy["_read_error"] = error or ""
            records.append(row_copy)
    return records


def load_receipt_records(project_root: Path) -> list[dict[str, Any]]:
    base = project_root / "dataset_generation_logs" / "batch_sage_execution"
    if not base.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for receipt_path in sorted(base.rglob("execution_receipt.json")):
        receipt, _ = read_json(receipt_path)
        if not receipt:
            continue
        task_results = receipt.get("task_results", [])
        if not isinstance(task_results, list):
            continue
        for result in task_results:
            if not isinstance(result, dict):
                continue
            row = dict(result)
            row["_receipt_path"] = str(receipt_path)
            records.append(row)
    return records


def match_execution_record(
    result_dir: Path,
    scene_id: str,
    prn: str,
    channel: Any,
    records: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    expected_path = normalize_path(result_dir)
    expected_task = task_key(scene_id, prn, channel)
    matches: list[dict[str, Any]] = []
    for record in records:
        output_path = normalize_path(record.get("output_path"))
        task_id = str(record.get("task_id", "")).strip()
        scene_match = str(record.get("scene_id", "")).strip() == scene_id
        prn_match = str(record.get("prn", record.get("PRN", ""))).strip().upper() == prn.upper()
        channel_match = str(record.get("tracking_channel", "")).strip() == str(channel).strip()
        if output_path == expected_path or task_id == expected_task or (scene_match and prn_match and channel_match):
            matches.append(record)
    if not matches:
        return None
    matches.sort(key=lambda row: parse_time(row.get("end_time_utc")) or datetime.min.replace(tzinfo=timezone.utc))
    return matches[-1]


def qa_candidate_paths(project_root: Path) -> list[Path]:
    candidates: list[Path] = []
    roots = [project_root / "docs", project_root / "scenes"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            lower = path.name.casefold()
            path_text = str(path).casefold()
            if "paper_draft" in path_text:
                continue
            if any(token in lower for token in ("handoff", "workspace_index", "design", "outline", "inventory", "plan")):
                continue
            if any(token in lower for token in ("qa", "validation", "final_validation", "pilot", "wave")):
                candidates.append(path)
    return candidates


def report_matches_task(path: Path, text: str, scene_id: str, prn: str) -> bool:
    if scene_id not in text:
        return False
    pattern = rf"(?<![A-Z0-9]){re.escape(prn)}(?![A-Z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def find_qa_report(
    project_root: Path,
    scene_id: str,
    prn: str,
    result_dir: Path,
) -> tuple[str, str]:
    if scene_id == "F1023_V70_D0117_P2":
        archival_report = result_dir.parent.parent / "reference_scene_final_validation_report.md"
        if archival_report.is_file():
            try:
                archival_text = archival_report.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError):
                archival_text = ""
            if report_matches_task(archival_report, archival_text, scene_id, prn):
                return "VALIDATED", str(archival_report)
    candidates: list[tuple[Path, str]] = []
    result_parent = result_dir.parent.parent
    local_reports = sorted(result_parent.glob("*.md")) if result_parent.is_dir() else []
    for path in local_reports:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        if report_matches_task(path, text, scene_id, prn):
            candidates.append((path, text))
    for path in qa_candidate_paths(project_root):
        if any(path == existing[0] for existing in candidates):
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        if report_matches_task(path, text, scene_id, prn):
            candidates.append((path, text))
    # A QA report next to a result directory is a stronger source than a
    # general project report, while explicit full-production status is the
    # strongest textual marker.
    normalized_scene = re.sub(r"[^a-z0-9]", "", scene_id.casefold())
    normalized_task_path = normalize_path(result_dir)

    def candidate_score(item: tuple[Path, str]) -> tuple[int, int, int, int, float]:
        path, text = item
        name = path.name.casefold()
        score = 0
        if prn.casefold() in name:
            score += 80
        if f"wavea_{prn.casefold()}" in name:
            score += 700
        if f"pilot1_{prn.casefold()}" in name:
            score += 700
        if f"wave2a_{prn.casefold()}" in name:
            score += 700
        if "10mhz_full_sage_production" in name and prn.casefold() in name:
            score += 750
        if normalized_scene in re.sub(r"[^a-z0-9]", "", name):
            score += 100
        if normalized_task_path in normalize_path(text):
            score += 120
        if "reference_scene_final_validation" in name:
            score += 700
        if "full_sage_production" in name or "wavea" in name or "wave2a" in name or "pilot" in name:
            score += 30
        if "QA_REPORT" in path.name.upper() or "VALIDATION" in path.name.upper():
            score += 20
        explicit_pass = bool(
            re.search(r"(?:QA|FINAL QA VERDICT|FINAL QA|最终结论|最终判定|QA RESULT).*?PASS", text, flags=re.IGNORECASE | re.DOTALL)
            or re.search(r"FULL_SAGE_PRODUCTION_TASK_STATUS\s*[:=]\s*PASS", text, flags=re.IGNORECASE)
        )
        explicit_fail = bool(
            re.search(r"(?:QA|FINAL QA VERDICT|FINAL QA|最终结论|最终判定|QA RESULT).*?FAIL", text, flags=re.IGNORECASE | re.DOTALL)
        )
        return (score, int(explicit_pass), int(not explicit_fail), int("PASS" in text.upper()), path.stat().st_mtime)

    candidates.sort(key=candidate_score, reverse=True)
    for path, text in candidates:
        upper = text.upper()
        if re.search(r"FULL_SAGE_PRODUCTION_TASK_STATUS\s*[:=]\s*PASS", upper) or re.search(
            r"(?:QA|FINAL QA VERDICT|FINAL QA|最终结论|最终判定|QA RESULT).*?PASS", upper, flags=re.DOTALL
        ):
            return "PASS", str(path)
        if "QA PASS" in upper or re.search(r"\bQA\s*[:=]\s*\**PASS\b", upper):
            return "PASS", str(path)
    for path, text in candidates:
        upper = text.upper()
        if re.search(r"(?:QA|FINAL QA VERDICT|FINAL QA|最终结论|最终判定|QA RESULT).*?FAIL", upper, flags=re.DOTALL):
            return "FAIL", str(path)
    if candidates:
        return "VALIDATED", str(candidates[0][0])
    return "NOT_RECORDED", ""


def result_scope(
    scene_id: str,
    prn: str,
    production_task_keys: set[tuple[str, str]],
    qa_report_path: str,
) -> str:
    if (scene_id, prn.upper()) in production_task_keys:
        return "production_manifest_10MHz"
    if scene_id == "F1023_V70_D0117_P2":
        return "reference_scene_validation"
    lower = qa_report_path.casefold()
    if "wave2a" in lower or (scene_id == "F1023_V120_D0121_P2" and prn == "G11"):
        return "wave2a_validation"
    if "wavea" in lower or "pilot1" in lower:
        return "wavea_validation"
    return "existing_nav_sage_v2"


def count_rows(
    result_dir: Path,
    filename: str,
    warnings: list[str],
) -> list[dict[str, str]] | None:
    path = result_dir / filename
    if not path.is_file():
        warnings.append(f"missing:{filename}")
        return None
    rows, error = read_csv_rows(path)
    if error:
        warnings.append(error)
    return rows


def build_row(
    project_root: Path,
    result_dir: Path,
    execution_records: list[dict[str, Any]],
    receipt_records: list[dict[str, Any]],
    production_task_keys: set[tuple[str, str]],
) -> dict[str, Any]:
    warnings: list[str] = []
    context_path = result_dir / "run_context.json"
    context, context_error = read_json(context_path) if context_path.is_file() else (None, "run_context.json:missing")
    if context_error:
        warnings.append(context_error)
    scene_id = str((context or {}).get("sceneId") or result_dir.parents[2].name)
    prn = str((context or {}).get("prnLabel") or result_dir.name).upper()
    channel_value = (context or {}).get("trackingChannel", "")
    channel = as_int(channel_value)
    sample_rate = as_int((context or {}).get("samplingRateHz"))
    if sample_rate is None:
        warnings.append("sample_rate_missing_in_run_context")

    stage0_symbols = count_rows(result_dir, "stage0_valid_symbols.csv", warnings)
    stage0_windows = count_rows(result_dir, "stage0_valid_40ms_windows.csv", warnings)
    stage1_scan = count_rows(result_dir, "stage1_nav_fast_scan.csv", warnings)
    stage2_orders = count_rows(result_dir, "stage2_model_orders.csv", warnings)
    stage2_selected = count_rows(result_dir, "stage2_selected_windows.csv", warnings)
    stage3_centers = count_rows(result_dir, "stage3_reliable_centers.csv", warnings)
    stage4_summary = count_rows(result_dir, "stage4_joint_summary.csv", warnings)
    stage4_paths = count_rows(result_dir, "stage4_joint_paths.csv", warnings)

    stage4_joint_valid: int | None = None
    confirmed_events: int | None = None
    confirmed_paths: int | None = None
    if stage4_summary is not None:
        stage4_joint_valid = sum(as_bool(row.get("joint_valid")) for row in stage4_summary)
        if stage4_paths is None:
            confirmed_events = None
            confirmed_paths = None
        else:
            multipath_centers = {
                str(row.get("center_window_id", ""))
                for row in stage4_paths
                if as_bool(row.get("is_multipath"))
            }
            confirmed_events = sum(
                as_bool(row.get("joint_valid"))
                and (as_int(row.get("joint_multipath_count")) or 0) > 0
                and str(row.get("center_window_id", "")) in multipath_centers
                for row in stage4_summary
            )
            confirmed_paths = sum(as_bool(row.get("is_multipath")) for row in stage4_paths)

    execution = match_execution_record(result_dir, scene_id, prn, channel_value, execution_records)
    if execution is None:
        execution = match_execution_record(result_dir, scene_id, prn, channel_value, receipt_records)
    if execution is None:
        execution_status = "output_present_execution_unresolved"
        runtime: float | None = None
        execution_log_path = ""
        warnings.append("execution_record_not_found")
    else:
        execution_status = str(execution.get("status", "completed")).strip() or "unknown"
        runtime = derive_runtime(execution)
        execution_log_path = str(execution.get("_execution_log_path", execution.get("_receipt_path", "")))
        if not execution_log_path:
            warnings.append("execution_source_path_missing")

    qa_status, qa_report_path = find_qa_report(project_root, scene_id, prn, result_dir)
    scope = result_scope(scene_id, prn, production_task_keys, qa_report_path)

    output_files = [path for path in result_dir.iterdir() if path.is_file()]
    required_missing = [name for name in REQUIRED_OUTPUT_FILES if not (result_dir / name).is_file()]
    nonempty_count = sum(path.stat().st_size > 0 for path in output_files)
    if required_missing:
        warnings.append("required_output_missing")
    if any(path.stat().st_size == 0 for path in output_files):
        warnings.append("empty_output_file_present")
    if stage0_symbols is not None and stage0_windows is not None and len(stage0_symbols) < len(stage0_windows):
        warnings.append("stage0_symbol_rows_less_than_window_rows")

    if context is None:
        provenance = "run_context_missing"
    elif execution_status == "output_present_execution_unresolved":
        provenance = "run_context_present_execution_unresolved"
    elif qa_status == "NOT_RECORDED":
        provenance = "run_context_execution_present_qa_not_recorded"
    else:
        provenance = "run_context_execution_qa_provenance_present"

    return {
        "task_id": task_key(scene_id, prn, channel_value),
        "scene_id": scene_id,
        "PRN": prn,
        "channel": csv_value(channel),
        "sample_rate_hz": csv_value(sample_rate),
        "result_scope": scope,
        "execution_status": execution_status,
        "QA_status": qa_status,
        "runtime_seconds": csv_value(runtime),
        "stage0_windows": csv_value(len(stage0_windows) if stage0_windows is not None else None),
        "stage1_scanned": csv_value(len(stage1_scan) if stage1_scan is not None else None),
        "stage1_selected": csv_value(len(stage2_selected) if stage2_selected is not None else None),
        "stage1_selected_source": "stage2_selected_windows.csv" if stage2_selected is not None else "",
        "stage2_evaluations": csv_value(len(stage2_orders) if stage2_orders is not None else None),
        "stage3_reliable_centers": csv_value(len(stage3_centers) if stage3_centers is not None else None),
        "stage4_rows": csv_value(len(stage4_summary) if stage4_summary is not None else None),
        "stage4_joint_valid": csv_value(stage4_joint_valid),
        "confirmed_events": csv_value(confirmed_events),
        "confirmed_paths": csv_value(confirmed_paths),
        "result_directory": str(result_dir),
        "output_file_count": len(output_files),
        "required_file_count": len(REQUIRED_OUTPUT_FILES) - len(required_missing),
        "nonempty_file_count": nonempty_count,
        "missing_required_files": ";".join(required_missing),
        "execution_log_path": execution_log_path,
        "qa_report_path": qa_report_path,
        "provenance_status": provenance,
        "warnings": ";".join(sorted(set(warnings))),
    }


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def format_count(rows: list[dict[str, Any]], field: str, value: str) -> int:
    return sum(str(row.get(field, "")) == value for row in rows)


def write_report(
    path: Path,
    project_root: Path,
    rows: list[dict[str, Any]],
    discovered_count: int,
    excluded_non_10mhz: int,
    excluded_unknown_rate: int,
) -> None:
    completed = format_count(rows, "execution_status", "completed")
    qa_pass = format_count(rows, "QA_status", "PASS")
    qa_missing = format_count(rows, "QA_status", "NOT_RECORDED")
    production_rows = [row for row in rows if row["result_scope"] == "production_manifest_10MHz"]

    def total_int(field: str) -> int:
        total = 0
        for row in rows:
            value = as_int(row.get(field))
            if value is not None:
                total += value
        return total

    lines = [
        "# 10.23 MHz Full SAGE Production Summary Report",
        "",
        f"- Generated UTC: `{utc_now()}`",
        f"- Project root: `{project_root}`",
        "- Mode: **read-only audit/summary**",
        "- Raw IQ opened: **no**",
        "- MATLAB/SAGE/batch executed: **no**",
        "",
        "## Scope",
        "",
        f"Discovered non-empty result namespaces under `scenes/**/sage_results/nav_sage_v2/**`: **{discovered_count}**.",
        f"Included in this 10.23 MHz report: **{len(rows)}** rows with `sample_rate_hz={SAMPLE_RATE_HZ}`.",
        f"Excluded because sample rate was not 10.23 MHz: **{excluded_non_10mhz}**; unknown sample rate: **{excluded_unknown_rate}**.",
        "",
        "The scanner reads run-context JSON, Stage CSV row counts, execution logs/receipts, and QA markdown. It does not open raw IQ, MAT signal payloads, or execute any algorithm. `stage1_selected` is taken from the existing `stage2_selected_windows.csv` because the Stage1 fast-scan CSV is the full scanned-window table.",
        "",
        "## Current status",
        "",
        f"- Existing 10.23 MHz result rows: **{len(rows)}**",
        f"- Rows with execution status `completed`: **{completed}**",
        f"- Rows with explicit QA `PASS`: **{qa_pass}**",
        f"- Rows without a matching QA report: **{qa_missing}**",
        f"- Current production-manifest rows found: **{len(production_rows)}**",
        "",
        "The CSV distinguishes historical reference/Wave validation outputs from rows belonging to the current 10 MHz production manifest through `result_scope`. A present output directory alone is not treated as an execution or QA PASS.",
        "",
        "## Task summary",
        "",
        "| Scene | PRN | Ch. | Scope | Execution | QA | Runtime (s) | Stage0 windows | Stage1 scan/selected | Stage2 eval | Stage3 reliable | Stage4 rows/valid | Confirmed events/paths |",
        "|---|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {scene_id} | {PRN} | {channel} | {result_scope} | {execution_status} | {QA_status} | {runtime_seconds} | {stage0_windows} | {stage1_scanned}/{stage1_selected} | {stage2_evaluations} | {stage3_reliable_centers} | {stage4_rows}/{stage4_joint_valid} | {confirmed_events}/{confirmed_paths} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Aggregate counts (existing rows only)",
            "",
            f"- Stage0 40 ms windows: **{total_int('stage0_windows')}**",
            f"- Stage1 scanned windows: **{total_int('stage1_scanned')}**",
            f"- Stage1 selected windows: **{total_int('stage1_selected')}**",
            f"- Stage2 model evaluations: **{total_int('stage2_evaluations')}**",
            f"- Stage3 reliable centers: **{total_int('stage3_reliable_centers')}**",
            f"- Stage4 joint rows: **{total_int('stage4_rows')}**",
            f"- Stage4 `joint_valid` rows: **{total_int('stage4_joint_valid')}**",
            f"- Confirmed events: **{total_int('confirmed_events')}**",
            f"- Confirmed paths: **{total_int('confirmed_paths')}**",
            "",
            "No delay spread, Doppler spread, K-factor, PDP, or other channel-level parameter was calculated. The event/path database remains a separate planned ingest step.",
            "",
            "## Provenance and warnings",
            "",
            "Each row records its result directory, execution source, QA report source, required-file count, non-empty-file count, and warnings in `production_summary_10MHz.csv`. Missing execution/QA evidence is reported as unresolved/not recorded; it is not inferred from Stage files.",
            "",
            "## Recommended use",
            "",
            "Use the CSV as a read-only production monitor before approving the next Batch A task. A future task should appear with its immutable request, execution status, QA status, runtime, and Stage counts after its independent QA; this tool does not launch or authorize tasks.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run(project_root: Path, output_dir: Path) -> tuple[Path, Path]:
    project_root = project_root.resolve()
    output_dir = output_dir if output_dir.is_absolute() else project_root / output_dir
    result_dirs = discover_result_dirs(project_root)
    execution_records = load_execution_records(project_root)
    receipt_records = load_receipt_records(project_root)
    production_task_keys = load_production_task_keys(project_root)

    rows: list[dict[str, Any]] = []
    excluded_non_10mhz = 0
    excluded_unknown_rate = 0
    for result_dir in result_dirs:
        context, _ = read_json(result_dir / "run_context.json")
        sample_rate = as_int((context or {}).get("samplingRateHz"))
        if sample_rate is None:
            excluded_unknown_rate += 1
            continue
        if sample_rate != SAMPLE_RATE_HZ:
            excluded_non_10mhz += 1
            continue
        rows.append(
            build_row(
                project_root,
                result_dir,
                execution_records,
                receipt_records,
                production_task_keys,
            )
        )
    rows.sort(key=lambda row: (str(row["scene_id"]), str(row["PRN"]), str(row["channel"])))

    csv_path = output_dir / "production_summary_10MHz.csv"
    report_path = output_dir / "production_summary_report.md"
    write_summary(csv_path, rows)
    write_report(report_path, project_root, rows, len(result_dirs), excluded_non_10mhz, excluded_unknown_rate)
    print(f"SUMMARY_CSV={csv_path}")
    print(f"SUMMARY_REPORT={report_path}")
    print(f"DISCOVERED_RESULT_DIRS={len(result_dirs)}")
    print(f"INCLUDED_10MHz_ROWS={len(rows)}")
    print(f"QA_PASS_ROWS={format_count(rows, 'QA_status', 'PASS')}")
    return csv_path, report_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run(args.project_root, args.output_dir or DEFAULT_OUTPUT_RELATIVE)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"AUDIT_FAILED={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
