#!/usr/bin/env python3
"""Read-only QA and summary helper for the standalone Rain overnight runner.

This module reads only Rain output artifacts and the runner's task records.  It
never opens raw IQ, invokes MATLAB, changes source code, resumes a task, or
deletes/overwrites an artifact.  All output files are created with exclusive
creation semantics so a stale namespace fails closed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REQUIRED_OUTPUTS: tuple[str, ...] = (
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


QA_FIELDS: tuple[str, ...] = (
    "sequence",
    "weather",
    "scene",
    "prn",
    "channel",
    "execution_status",
    "matlab_exit_code",
    "stage0_status",
    "valid_nav_symbols",
    "complete_windows",
    "stage1_status",
    "scanned_windows",
    "selected_windows",
    "stage2_status",
    "stage2_windows",
    "selected_l_ge_2",
    "selected_l_ge_3",
    "stage3_status",
    "reliable_centers",
    "stage4_status",
    "joint_results",
    "joint_valid_rows",
    "confirmed_events",
    "confirmed_multipath_paths",
    "relative_phase_available",
    "darkroom_parameters_ready",
    "overall_status",
    "failure_reason",
    "output_dir",
    "stdout_path",
    "stderr_path",
    "start_utc",
    "end_utc",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _key(value: Any) -> str:
    return _text(value).lower().replace(" ", "_")


def get_value(row: Mapping[str, Any], *names: str, default: Any = "") -> Any:
    normalized = {_key(name): value for name, value in row.items()}
    for name in names:
        if _key(name) in normalized:
            return normalized[_key(name)]
    return default


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    return text in {"1", "true", "yes", "y", "on"}


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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def nonempty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def distinct_values(rows: Iterable[Mapping[str, Any]], field: str) -> set[str]:
    return {_text(get_value(row, field)) for row in rows if _text(get_value(row, field))}


def count_selected_orders(rows: Sequence[Mapping[str, Any]], minimum: int) -> int:
    selected: set[str] = set()
    for row in rows:
        order = parse_int(get_value(row, "selected_L", "selected_l"))
        if order is not None and order >= minimum:
            window = _text(get_value(row, "window_id"))
            if window:
                selected.add(window)
    return len(selected)


def _confirmed_summary_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    confirmed: list[dict[str, str]] = []
    for row in rows:
        joint_valid = parse_bool(get_value(row, "joint_valid"))
        joint_count = parse_int(get_value(row, "joint_multipath_count"))
        if joint_valid and joint_count is not None and joint_count > 0:
            confirmed.append(dict(row))
    return confirmed


def _confirmed_path_rows(
    rows: Sequence[Mapping[str, Any]],
    confirmed_centers: set[str],
) -> list[dict[str, str]]:
    paths: list[dict[str, str]] = []
    for row in rows:
        if not parse_bool(get_value(row, "is_multipath")):
            continue
        center = _text(get_value(row, "center_window_id", "window_id"))
        if center in confirmed_centers:
            paths.append(dict(row))
    return paths


def _path_parameter_row(
    task: Mapping[str, Any], row: Mapping[str, Any], output_path: Path
) -> dict[str, Any]:
    scene = _text(get_value(task, "scene"))
    prn = _text(get_value(task, "prn"))
    center = _text(get_value(row, "center_window_id", "window_id"))
    path_id = _text(get_value(row, "path_id"))
    return {
        "weather": _text(get_value(task, "weather")),
        "scene": scene,
        "prn": prn,
        "tracking_channel": _text(get_value(task, "channel")),
        "event_id": f"{scene}:{prn}:center_window_{center}",
        "path_id": path_id,
        "reference_path_id": "1",
        "joint_valid": "1",
        "is_multipath": "1",
        "excess_delay": _text(get_value(row, "excess_delay_samples")),
        "excess_delay_unit": "samples",
        "relative_doppler_hz": _text(get_value(row, "doppler_offset_hz")),
        "relative_phase_rad": _text(get_value(row, "relative_phase_rad")),
        "relative_phase_available": "1"
        if parse_bool(get_value(row, "relative_phase_available"))
        else "0",
        "relative_amplitude": _text(get_value(row, "relative_amplitude")),
        "relative_amplitude_db": _text(get_value(row, "relative_amplitude_db")),
        "source_stage4_file": str(output_path / "stage4_joint_paths.csv"),
        "run_timestamp": _text(get_value(task, "end_utc")),
        "provenance": "Rain Stage4 joint selected path; output-export-only phase/amplitude",
    }


def _parameter_rows_are_ready(rows: Sequence[Mapping[str, Any]]) -> bool:
    if not rows:
        return False
    required = (
        "excess_delay_samples",
        "doppler_offset_hz",
        "relative_phase_rad",
        "relative_amplitude",
    )
    for row in rows:
        if not parse_bool(get_value(row, "relative_phase_available")):
            return False
        if any(parse_float(get_value(row, field)) is None for field in required):
            return False
    return True


def audit_task_record(task_record: Mapping[str, Any]) -> dict[str, Any]:
    """Audit one task from a runner record without reading raw IQ."""
    output_dir = Path(_text(get_value(task_record, "output_dir")))
    files = {name: output_dir / name for name in REQUIRED_OUTPUTS}
    missing = [name for name, path in files.items() if not nonempty_file(path)]

    stage0_symbols: list[dict[str, str]] = []
    stage0_windows: list[dict[str, str]] = []
    stage1: list[dict[str, str]] = []
    stage2_models: list[dict[str, str]] = []
    stage2_selected: list[dict[str, str]] = []
    stage3_reliable: list[dict[str, str]] = []
    stage4_summary: list[dict[str, str]] = []
    stage4_paths: list[dict[str, str]] = []

    def load_if_present(name: str) -> list[dict[str, str]]:
        path = files[name]
        return read_csv_rows(path) if nonempty_file(path) else []

    stage0_symbols = load_if_present("stage0_valid_symbols.csv")
    stage0_windows = load_if_present("stage0_valid_40ms_windows.csv")
    stage1 = load_if_present("stage1_nav_fast_scan.csv")
    stage2_models = load_if_present("stage2_model_orders.csv")
    stage2_selected = load_if_present("stage2_selected_windows.csv")
    stage3_reliable = load_if_present("stage3_reliable_centers.csv")
    stage4_summary = load_if_present("stage4_joint_summary.csv")
    stage4_paths = load_if_present("stage4_joint_paths.csv")

    confirmed_summary = _confirmed_summary_rows(stage4_summary)
    confirmed_centers = {
        _text(get_value(row, "center_window_id")) for row in confirmed_summary
    }
    confirmed_paths = _confirmed_path_rows(stage4_paths, confirmed_centers)
    parameters_ready = _parameter_rows_are_ready(confirmed_paths)

    execution_code = parse_int(get_value(task_record, "matlab_exit_code"))
    process_ok = execution_code == 0
    all_stage_files = not missing
    if not process_ok:
        overall = "SOFTWARE_FAIL"
        failure_reason = _text(get_value(task_record, "failure_reason")) or (
            "MATLAB process returned non-zero exit code"
        )
    elif not all_stage_files:
        overall = "SOFTWARE_FAIL"
        failure_reason = "missing_or_empty_stage_output:" + ",".join(missing)
    elif confirmed_paths and not parameters_ready:
        overall = "DATA_INSUFFICIENT"
        failure_reason = "confirmed_path_parameter_tuple_incomplete"
    elif confirmed_paths:
        overall = "PASS_WITH_CONFIRMED_MULTIPATH"
        failure_reason = ""
    else:
        overall = "PASS_NO_CONFIRMED_MULTIPATH"
        failure_reason = "no_stage4_confirmed_multipath_under_current_criterion"

    relative_phase = (
        "YES"
        if confirmed_paths and all(
            parse_bool(get_value(row, "relative_phase_available"))
            for row in confirmed_paths
        )
        else "NO"
        if confirmed_paths
        else "NOT_APPLICABLE"
    )
    selected_windows = len(
        distinct_values(stage2_selected, "window_id")
    )
    result: dict[str, Any] = {
        "sequence": _text(get_value(task_record, "sequence")),
        "weather": _text(get_value(task_record, "weather")),
        "scene": _text(get_value(task_record, "scene")),
        "prn": _text(get_value(task_record, "prn")),
        "channel": _text(get_value(task_record, "channel")),
        "execution_status": "COMPLETED" if process_ok else "FAILED",
        "matlab_exit_code": "" if execution_code is None else execution_code,
        "stage0_status": "PASS" if files["stage0_valid_symbols.csv"].is_file() and files["stage0_valid_40ms_windows.csv"].is_file() else "INCOMPLETE",
        "valid_nav_symbols": len(stage0_symbols),
        "complete_windows": len(stage0_windows),
        "stage1_status": "PASS" if nonempty_file(files["stage1_nav_fast_scan.csv"]) else "INCOMPLETE",
        "scanned_windows": len(stage1),
        "selected_windows": selected_windows,
        "stage2_status": "PASS" if all(nonempty_file(files[name]) for name in (
            "stage2_model_orders.csv", "stage2_selected_windows.csv", "stage2_selected_paths.csv"
        )) else "INCOMPLETE",
        "stage2_windows": len(distinct_values(stage2_models, "window_id")),
        "selected_l_ge_2": count_selected_orders(stage2_selected, 2),
        "selected_l_ge_3": count_selected_orders(stage2_selected, 3),
        "stage3_status": "PASS" if nonempty_file(files["stage3_reliable_centers.csv"]) and nonempty_file(files["stage3_persistence.csv"]) else "INCOMPLETE",
        "reliable_centers": len(stage3_reliable),
        "stage4_status": "PASS" if nonempty_file(files["stage4_joint_summary.csv"]) and nonempty_file(files["stage4_joint_paths.csv"]) else "INCOMPLETE",
        "joint_results": len(stage4_summary),
        "joint_valid_rows": sum(parse_bool(get_value(row, "joint_valid")) for row in stage4_summary),
        "confirmed_events": len(confirmed_summary),
        "confirmed_multipath_paths": len(confirmed_paths),
        "relative_phase_available": relative_phase,
        "darkroom_parameters_ready": "YES" if parameters_ready else "NO",
        "overall_status": overall,
        "failure_reason": failure_reason,
        "output_dir": str(output_dir),
        "stdout_path": _text(get_value(task_record, "stdout_path")),
        "stderr_path": _text(get_value(task_record, "stderr_path")),
        "start_utc": _text(get_value(task_record, "start_utc")),
        "end_utc": _text(get_value(task_record, "end_utc")),
        "missing_outputs": missing,
        "parameter_rows": [
            _path_parameter_row(task_record, row, output_dir)
            for row in confirmed_paths
            if _parameter_rows_are_ready([row])
        ],
    }
    return result


def _write_new_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    _write_new_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def audit_task_file(task_record_path: Path, output_receipt: Path) -> dict[str, Any]:
    with task_record_path.open("r", encoding="utf-8") as handle:
        task_record = json.load(handle)
    result = audit_task_record(task_record)
    result["task_record_path"] = str(task_record_path)
    _write_new_json(output_receipt, result)
    return result


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def linear_stats(values: Sequence[float]) -> dict[str, float | int | None]:
    values = [value for value in values if math.isfinite(value)]
    if not values:
        return {"N": 0, "median": None, "IQR": None, "P10": None, "P25": None, "P50": None, "P75": None, "P90": None}
    p25 = percentile(values, 0.25)
    p75 = percentile(values, 0.75)
    return {
        "N": len(values),
        "median": statistics.median(values),
        "IQR": None if p25 is None or p75 is None else p75 - p25,
        "P10": percentile(values, 0.10),
        "P25": p25,
        "P50": percentile(values, 0.50),
        "P75": p75,
        "P90": percentile(values, 0.90),
    }


def circular_mean(values: Sequence[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return None
    angle = math.atan2(sum(math.sin(value) for value in finite), sum(math.cos(value) for value in finite))
    return angle


def summarize_parameter_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    fields = {
        "excess_delay": "excess_delay",
        "relative_doppler_hz": "relative_doppler_hz",
        "relative_amplitude": "relative_amplitude",
        "relative_phase_rad": "relative_phase_rad",
    }
    summary: dict[str, dict[str, Any]] = {}
    for label, field in fields.items():
        values = [
            number
            for row in rows
            if (number := parse_float(get_value(row, field))) is not None
        ]
        data = linear_stats(values)
        if label == "relative_phase_rad":
            data["circular_mean_rad"] = circular_mean(values)
        summary[label] = data
    return summary


def _read_receipts(run_dir: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("receipts/task_*.json")):
        with path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
        record["receipt_path"] = str(path)
        receipts.append(record)
    return sorted(receipts, key=lambda item: int(item.get("sequence", 0)))


def write_csv_new(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def summarize_run(
    run_dir: Path,
    qa_csv: Path,
    parameters_csv: Path,
    report_path: Path,
    meeting_path: Path,
) -> dict[str, Any]:
    receipts = _read_receipts(run_dir)
    qa_rows = [{field: receipt.get(field, "") for field in QA_FIELDS} for receipt in receipts]
    write_csv_new(qa_csv, QA_FIELDS, qa_rows)

    parameter_fields = (
        "weather", "scene", "prn", "tracking_channel", "event_id", "path_id",
        "reference_path_id", "joint_valid", "is_multipath", "excess_delay",
        "excess_delay_unit", "relative_doppler_hz", "relative_phase_rad",
        "relative_phase_available", "relative_amplitude", "relative_amplitude_db",
        "source_stage4_file", "run_timestamp", "provenance",
    )
    parameter_rows = [
        parameter
        for receipt in receipts
        for parameter in receipt.get("parameter_rows", [])
    ]
    write_csv_new(parameters_csv, parameter_fields, parameter_rows)

    statuses = [receipt.get("overall_status", "") for receipt in receipts]
    if any(status == "SOFTWARE_FAIL" for status in statuses):
        run_status = "GLOBAL_SOFTWARE_FAILURE" if receipts and receipts[0].get("overall_status") == "SOFTWARE_FAIL" else "PARTIAL_DATA_FAILURE"
    elif len(receipts) < 9 or any(status not in {"PASS_WITH_CONFIRMED_MULTIPATH", "PASS_NO_CONFIRMED_MULTIPATH"} for status in statuses):
        run_status = "PARTIAL_DATA_FAILURE"
    else:
        run_status = "COMPLETE"

    by_weather: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        by_weather.setdefault(_text(receipt.get("weather")), []).append(receipt)
    all_parameters = parameter_rows
    lines = [
        "# Rain SAGE Overnight QA Report (2026-08-18)",
        "",
        "This report is generated from task receipts and Rain Stage0--Stage4 output artifacts.",
        "It does not interpret Stage2 L>=2 as confirmed multipath.",
        "",
        f"RUN_STATUS={run_status}",
        f"TASKS_ATTEMPTED={len(receipts)}",
        "",
        "## Task QA",
        "",
        "| Sequence | Weather | Scene | PRN | Channel | Status | Stage0 windows | Stage1 scanned | Stage2 L>=2 | Stage3 reliable | Stage4 rows | Confirmed events | Confirmed paths | Failure |",
        "|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for receipt in receipts:
        lines.append(
            "| {sequence} | {weather} | {scene} | {prn} | {channel} | {overall_status} | {complete_windows} | {scanned_windows} | {selected_l_ge_2} | {reliable_centers} | {joint_results} | {confirmed_events} | {confirmed_multipath_paths} | {failure_reason} |".format(**receipt)
        )
    lines += ["", "## Darkroom parameter QA", ""]
    lines.append(f"Parameter table: `{parameters_csv}`")
    lines.append(f"Confirmed-path parameter rows: {len(all_parameters)}")
    for weather, records in by_weather.items():
        weather_parameters = [parameter for receipt in records for parameter in receipt.get("parameter_rows", [])]
        lines.append("")
        lines.append(f"### {weather or 'Unknown'}")
        lines.append(f"Tasks: {len(records)}; confirmed paths: {len(weather_parameters)}")
        stats = summarize_parameter_rows(weather_parameters)
        for name, values in stats.items():
            lines.append(f"- {name}: `{json.dumps(values, ensure_ascii=False)}`")
    lines += [
        "",
        "## Scientific boundary",
        "",
        "Only `joint_valid=1`, `joint_multipath_count>0`, and a path row with `is_multipath=1` are counted as confirmed.",
        "Zero confirmed events is retained as a valid result and is not interpreted as absence of physical multipath.",
        "The descriptive weather summaries are not a universal rain-propagation law.",
        "",
        "## Production protection and artifact-preservation audit",
        "",
        "Production source SHA before/after and Git diff are recorded by the PowerShell runner.",
        "No runner action deletes, moves, resumes, or overwrites prior artifacts.",
        "",
        "Figures are not generated by this dependency-free overnight helper; raw point distributions remain available in the parameter table for later plotting.",
    ]
    _write_new_text(report_path, "\n".join(lines) + "\n")

    meeting_lines = [
        "# Tomorrow Meeting: Rain SAGE Results",
        "",
        f"Run status: `{run_status}`",
        f"Tasks attempted: {len(receipts)}",
        "",
        "| Weather | Tasks | Stage4 completed | Confirmed paths |",
        "|---|---:|---:|---:|",
    ]
    for weather, records in by_weather.items():
        meeting_lines.append(
            f"| {weather} | {len(records)} | {sum(r.get('stage4_status') == 'PASS' for r in records)} | {sum(int(r.get('confirmed_multipath_paths', 0) or 0) for r in records)} |"
        )
    meeting_lines += [
        "",
        "The results are empirical darkroom observations only; they are not a universal atmospheric rain model.",
        "The next step is to use the retained path-level tuples to design darkroom simulation parameters after independent QA.",
    ]
    _write_new_text(meeting_path, "\n".join(meeting_lines) + "\n")

    return {"run_status": run_status, "receipt_count": len(receipts), "parameter_count": len(parameter_rows)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--task-record", type=Path)
    mode.add_argument("--summarize", action="store_true")
    parser.add_argument("--output-receipt", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--qa-csv", type=Path)
    parser.add_argument("--parameters-csv", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--meeting-report", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.task_record:
        if args.output_receipt is None:
            raise SystemExit("--output-receipt is required with --task-record")
        audit_task_file(args.task_record, args.output_receipt)
        return 0
    required = (args.run_dir, args.qa_csv, args.parameters_csv, args.report, args.meeting_report)
    if any(value is None for value in required):
        raise SystemExit("summary mode requires --run-dir, --qa-csv, --parameters-csv, --report, --meeting-report")
    summarize_run(args.run_dir, args.qa_csv, args.parameters_csv, args.report, args.meeting_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
