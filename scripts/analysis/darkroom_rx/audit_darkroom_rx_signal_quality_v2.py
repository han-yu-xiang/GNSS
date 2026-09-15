"""Versioned, read-only positioning audit for the 0913DarkroomRx smoke run.

This module is an audit-layer compatibility revision.  It does not invoke
GNSS-SDR, MATLAB, SAGE, or read raw IQ.  The v1 audit namespace and source
remain immutable; v2 adds provenance-safe parsing for the file naming and
position-output conventions observed in the real GNSS-SDR output.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from . import audit_darkroom_rx_signal_quality as v1
    from .darkroom_rx_common import canonical_json_bytes, sha256_file
    from .run_darkroom_rx_gnss_sdr_batch import load_and_validate_manifest, select_tasks
except ImportError:
    from scripts.analysis.darkroom_rx import audit_darkroom_rx_signal_quality as v1
    from scripts.analysis.darkroom_rx.darkroom_rx_common import (
        canonical_json_bytes,
        sha256_file,
    )
    from scripts.analysis.darkroom_rx.run_darkroom_rx_gnss_sdr_batch import (
        load_and_validate_manifest,
        select_tasks,
    )


V2_SCHEMA_VERSION = "darkroom-rx-signal-quality-audit-v2"
_ORIGINAL_LOAD_MAT_FIELDS = v1._load_mat_fields
_ORIGINAL_PVT_SUMMARY = v1._pvt_summary
_ORIGINAL_TRACKING_CHANNEL = v1._tracking_channel
_ORIGINAL_PARSE_NMEA = v1.parse_nmea_lines


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def decode_numeric_mat_vector(value: object, *, label: str) -> np.ndarray:
    """Decode numeric MATLAB vectors, including 7.3 one-byte scalar fields.

    MATLAB 7.3 readers can expose uint8-like scalar fields as ``V1`` values.
    Interpreting those bytes as unsigned counts is lossless for fields such as
    ``valid_sats`` and ``solution_status``.  No padding, truncation, or zero
    substitution is performed.
    """

    array = np.asarray(value)
    if array.size == 0:
        return np.asarray([], dtype=float)
    flat = array.reshape(-1)
    if flat.dtype.kind in {"V", "S"} and flat.dtype.itemsize == 1:
        if flat.dtype.kind == "V":
            return flat.view(np.uint8).reshape(-1)
        return np.fromiter((item[0] for item in flat), dtype=np.uint8, count=flat.size)
    try:
        return flat.astype(float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"MAT field {label} is not numerically decodable: {flat.dtype}") from exc


def parse_tracking_channel(path: Path) -> int | None:
    """Parse legacy channel labels and GNSS-SDR numeric channel suffixes."""

    stem = path.stem
    match = re.search(r"(?:ch_|channel_?)(\d+)", stem, re.IGNORECASE)
    if match:
        return int(match.group(1))
    # GNSS-SDR 0.0.16 emitted ``<task>_<channel>.mat`` despite the configured
    # ``..._track_ch_`` prefix.  Do not mistake a task's trailing ``_1023``
    # token for a channel.
    suffix = re.search(r"_(\d+)$", stem)
    if suffix:
        value = int(suffix.group(1))
        if value != 1023 and 0 <= value <= 63:
            return value
    return None


def _load_mat_fields_v2(path: Path, names: Sequence[str]) -> dict[str, np.ndarray]:
    arrays = _ORIGINAL_LOAD_MAT_FIELDS(path, names)
    return {
        name: decode_numeric_mat_vector(value, label=f"{path.name}:{name}")
        for name, value in arrays.items()
    }


def _parse_nmea_epochs(lines: Sequence[str]) -> tuple[list[tuple[float, bool, int | None, float | None]], list[float], dict[float, dict[str, Any]]]:
    raw_epochs: list[tuple[float, bool, int | None, float | None]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line.startswith("$"):
            continue
        fields = line.split("*")[0].split(",")
        sentence = fields[0][-3:].upper()
        if sentence not in {"GGA", "RMC"} or len(fields) < 3:
            continue
        seconds = v1._nmea_seconds_of_day(fields[1])
        if seconds is None:
            continue
        if sentence == "GGA":
            try:
                fix_quality = int(fields[6] or "0")
            except (IndexError, ValueError):
                fix_quality = 0
            try:
                satellites = int(fields[7]) if fields[7] else None
            except (IndexError, ValueError):
                satellites = None
            try:
                hdop = float(fields[8]) if fields[8] else None
            except (IndexError, ValueError):
                hdop = None
            raw_epochs.append((seconds, fix_quality > 0, satellites, hdop))
        else:
            valid = len(fields) > 2 and fields[2].strip().upper() == "A"
            raw_epochs.append((seconds, valid, None, None))

    unwrapped = v1._unwrap_day([item[0] for item in raw_epochs])
    grouped: dict[float, dict[str, Any]] = {}
    ordered_keys: list[float] = []
    for item, timestamp in zip(raw_epochs, unwrapped):
        key = round(timestamp, 3)
        if key not in grouped:
            grouped[key] = {"valid": False, "satellites": [], "hdop": []}
            ordered_keys.append(key)
        record = grouped[key]
        record["valid"] = bool(record["valid"] or item[1])
        if item[2] is not None:
            record["satellites"].append(item[2])
        if item[3] is not None and math.isfinite(item[3]):
            record["hdop"].append(item[3])
    return raw_epochs, ordered_keys, grouped


def _nominal_epoch_step(times: np.ndarray) -> float:
    positive = np.diff(times)
    positive = positive[np.isfinite(positive) & (positive > 0)]
    if not positive.size:
        return 1.0
    rounded = np.round(positive, 3)
    counts = Counter(float(value) for value in rounded)
    highest = max(counts.values())
    return min(value for value, count in counts.items() if count == highest)


def parse_nmea_lines_with_output_gaps(lines: Iterable[str]) -> dict[str, Any]:
    """Parse NMEA and distinguish missing emitted epochs from explicit no-fix.

    A gap is inferred only between two recognized emitted epochs.  It is
    reported as ``POSITION_OUTPUT_GAP`` and never converted into a physical
    receiver lock-loss or an explicit no-fix epoch.
    """

    line_list = list(lines)
    # ``audit_task_v2`` temporarily replaces v1.parse_nmea_lines at the
    # module boundary.  Call the captured original here to avoid recursively
    # entering this compatibility wrapper.
    base = _ORIGINAL_PARSE_NMEA(line_list)
    raw_epochs, ordered_keys, grouped = _parse_nmea_epochs(line_list)
    if not ordered_keys:
        return {
            **base,
            "explicit_no_fix_epoch_count": 0,
            "inferred_missing_epoch_count": 0,
            "position_output_gap_count": 0,
            "max_position_output_gap_s": 0.0,
            "expected_position_epoch_count": 0,
            "position_epoch_coverage_fraction": None,
            "position_output_gap_intervals": [],
        }

    times = np.asarray(ordered_keys, dtype=float)
    nominal = _nominal_epoch_step(times)
    gap_intervals: list[dict[str, Any]] = []
    inferred_missing = 0
    for previous, current in zip(times[:-1], times[1:]):
        delta = float(current - previous)
        missing = max(int(round(delta / nominal)) - 1, 0)
        if missing <= 0 or delta <= nominal * 1.5:
            continue
        start = float(previous + nominal)
        duration = float(missing * nominal)
        gap_intervals.append(
            {
                "start_s": start,
                "end_s": float(start + duration),
                "duration_s": duration,
                "provenance": "MISSING_EXPECTED_EPOCH",
                "nominal_epoch_step_s": nominal,
                "missing_epoch_count": missing,
            }
        )
        inferred_missing += missing

    explicit_no_fix = sum(not bool(record["valid"]) for record in grouped.values())
    expected = int(times.size + inferred_missing)
    return {
        **base,
        "explicit_no_fix_epoch_count": int(explicit_no_fix),
        "inferred_missing_epoch_count": int(inferred_missing),
        "position_output_gap_count": len(gap_intervals),
        "max_position_output_gap_s": max(
            (float(item["duration_s"]) for item in gap_intervals), default=0.0
        ),
        "expected_position_epoch_count": expected,
        "position_epoch_coverage_fraction": (
            float(times.size / expected) if expected else None
        ),
        "position_output_gap_intervals": gap_intervals,
        "nmea_nominal_epoch_step_s": nominal,
        "nmea_recognized_epoch_count": len(raw_epochs),
    }


def _pvt_summary_v2(paths: Sequence[Path]) -> dict[str, Any]:
    """PVT fallback with byte-safe status/count decoding."""

    names = [
        "RX_time",
        "TOW_at_current_symbol_ms",
        "solution_status",
        "solution_type",
        "valid_sats",
        "latitude",
        "longitude",
        "HDOP",
    ]
    all_time: list[float] = []
    all_valid: list[bool] = []
    all_sats: list[float] = []
    all_hdop: list[float] = []
    for path in paths:
        arrays = _load_mat_fields_v2(path, names)
        status = decode_numeric_mat_vector(
            arrays.get("solution_status", []), label=f"{path.name}:solution_status"
        )
        sats = decode_numeric_mat_vector(
            arrays.get("valid_sats", np.full(status.size, np.nan)),
            label=f"{path.name}:valid_sats",
        )
        time_values = arrays.get("RX_time", arrays.get("TOW_at_current_symbol_ms", []))
        times = decode_numeric_mat_vector(time_values, label=f"{path.name}:time")
        if not status.size or times.size != status.size or sats.size != status.size:
            continue
        if "TOW_at_current_symbol_ms" in arrays and "RX_time" not in arrays:
            times = times / 1000.0
        finite_times = times[np.isfinite(times)]
        if finite_times.size:
            times = times - float(finite_times[0])
        valid = np.isfinite(status) & (status > 0) & np.isfinite(sats) & (sats >= 4)
        all_time.extend(times.tolist())
        all_valid.extend(valid.tolist())
        all_sats.extend(sats[valid].tolist())
        hdop = decode_numeric_mat_vector(
            arrays.get("HDOP", np.full(status.size, np.nan)),
            label=f"{path.name}:HDOP",
        )
        if hdop.size == status.size:
            all_hdop.extend(hdop[valid & np.isfinite(hdop)].tolist())
    if not all_time:
        return parse_nmea_lines_with_output_gaps([])
    order = np.argsort(np.asarray(all_time), kind="stable")
    times = np.asarray(all_time, dtype=float)[order]
    valid = np.asarray(all_valid, dtype=bool)[order]
    unique = np.concatenate(([True], np.diff(times) > 1e-9))
    times = times[unique]
    valid = valid[unique]
    fix_runs = v1._run_durations(times, valid)
    no_fix_runs = v1._run_durations(times, ~valid)
    return {
        "position_output_observed": True,
        "recognized_sentence_count": 0,
        "position_epoch_count": int(times.size),
        "valid_fix_epoch_count": int(valid.sum()),
        "valid_fix_fraction": float(valid.mean()),
        "max_consecutive_fix_s": max((run["duration_s"] for run in fix_runs), default=0.0),
        "fix_interval_count": len(fix_runs),
        "max_no_fix_interval_s": max((run["duration_s"] for run in no_fix_runs), default=0.0),
        "median_valid_sats": float(np.median(all_sats)) if all_sats else None,
        "median_hdop": float(np.median(all_hdop)) if all_hdop else None,
        "fix_intervals": fix_runs,
        "no_fix_intervals": no_fix_runs,
        "explicit_no_fix_epoch_count": int((~valid).sum()),
        "inferred_missing_epoch_count": 0,
        "position_output_gap_count": 0,
        "max_position_output_gap_s": 0.0,
        "expected_position_epoch_count": int(times.size),
        "position_epoch_coverage_fraction": 1.0,
        "position_output_gap_intervals": [],
    }


def _read_nmea_v2(paths: Sequence[Path]) -> dict[str, Any]:
    lines: list[str] = []
    for path in paths:
        lines.extend(path.read_text(encoding="ascii", errors="replace").splitlines())
    return parse_nmea_lines_with_output_gaps(lines)


def _parse_stdout_ttff(output: Path) -> dict[str, Any]:
    paths = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and "stdout" in path.name.lower()
    )
    time_pattern = re.compile(r"Current receiver time:\s*([0-9]+(?:\.[0-9]+)?)\s*s\b", re.IGNORECASE)
    fix_pattern = re.compile(r"First position fix", re.IGNORECASE)
    for path in paths:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        fix_index = next((i for i, line in enumerate(lines) if fix_pattern.search(line)), None)
        if fix_index is None:
            continue
        values = [(i, float(match.group(1))) for i, line in enumerate(lines) if (match := time_pattern.search(line))]
        before = [value for index, value in values if index < fix_index]
        after = [value for index, value in values if index > fix_index]
        return {
            "first_fix_receiver_time_lower_bound_s": before[-1] if before else None,
            "first_fix_receiver_time_upper_bound_s": after[0] if after else None,
            "first_fix_log_line": lines[fix_index].strip(),
            "first_fix_stdout_path": str(path),
        }
    return {
        "first_fix_receiver_time_lower_bound_s": None,
        "first_fix_receiver_time_upper_bound_s": None,
        "first_fix_log_line": "",
        "first_fix_stdout_path": "",
    }


def _position_from_output(output: Path) -> tuple[dict[str, Any], str, list[Path]]:
    nmea_paths = sorted(output.rglob("*.nmea")) if output.is_dir() else []
    if nmea_paths:
        return _read_nmea_v2(nmea_paths), "NMEA", nmea_paths
    pvt_paths = (
        sorted(path for path in output.rglob("*.mat") if "pvt" in path.stem.lower())
        if output.is_dir()
        else []
    )
    if pvt_paths:
        return _pvt_summary_v2(pvt_paths), "PVT_MAT", pvt_paths
    return parse_nmea_lines_with_output_gaps([]), "MISSING", []


def audit_task_v2(
    manifest: Mapping[str, Any], row: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the v2 overlay against v1's read-only task audit, then enrich it."""

    saved = (v1._load_mat_fields, v1._tracking_channel, v1.parse_nmea_lines, v1._pvt_summary)
    v1._load_mat_fields = _load_mat_fields_v2
    v1._tracking_channel = parse_tracking_channel
    v1.parse_nmea_lines = parse_nmea_lines_with_output_gaps
    v1._pvt_summary = _pvt_summary_v2
    try:
        summary, prns, losses, _base_positions = v1.audit_task(manifest, row)
    finally:
        v1._load_mat_fields, v1._tracking_channel, v1.parse_nmea_lines, v1._pvt_summary = saved

    output = Path(str(row["output_windows_path"]))
    position, position_source, _position_paths = _position_from_output(output)
    summary.update(
        {
            "position_source": position_source,
            "position_epoch_count": position["position_epoch_count"],
            "valid_fix_epoch_count": position["valid_fix_epoch_count"],
            "valid_fix_fraction": position["valid_fix_fraction"],
            "max_consecutive_fix_s": position["max_consecutive_fix_s"],
            "max_no_fix_interval_s": position["max_no_fix_interval_s"],
            "median_valid_sats": position["median_valid_sats"],
            "median_hdop": position["median_hdop"],
            "explicit_no_fix_epoch_count": position.get("explicit_no_fix_epoch_count", 0),
            "inferred_missing_epoch_count": position.get("inferred_missing_epoch_count", 0),
            "position_output_gap_count": position.get("position_output_gap_count", 0),
            "max_position_output_gap_s": position.get("max_position_output_gap_s", 0.0),
            "expected_position_epoch_count": position.get("expected_position_epoch_count", position["position_epoch_count"]),
            "position_epoch_coverage_fraction": position.get("position_epoch_coverage_fraction"),
            **_parse_stdout_ttff(output),
        }
    )
    interval_rows = [
        {"task_id": row["task_id"], "interval_type": "FIX", **interval}
        for interval in position["fix_intervals"]
    ] + [
        {"task_id": row["task_id"], "interval_type": "NO_FIX", **interval}
        for interval in position["no_fix_intervals"]
    ] + [
        {"task_id": row["task_id"], "interval_type": "POSITION_OUTPUT_GAP", **interval}
        for interval in position.get("position_output_gap_intervals", [])
    ]
    return summary, prns, losses, interval_rows


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("x", newline="", encoding="utf-8-sig") as handle:
        if not fieldnames:
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_vehicle_template(path: Path, summaries: Sequence[Mapping[str, Any]]) -> None:
    _write_csv(
        path,
        [
            {
                "task_id": row["task_id"],
                "vehicle_test_utc_to_fill": "",
                "vehicle_map_position_visible_to_fill": "",
                "vehicle_accuracy_display_to_fill": "",
                "vehicle_gps_time_updating_to_fill": "",
                "vehicle_recovered_without_reboot_to_fill": "",
                "vehicle_recovered_after_reboot_to_fill": "",
                "notes_to_fill": "",
            }
            for row in summaries
        ],
    )


def _fmt(value: object, digits: int = 3) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _write_report(path: Path, *, manifest: Mapping[str, Any], summaries: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "# 0913DarkroomRx GNSS-SDR 信号质量 v2 只读审计",
        "",
        f"- 生成时间（UTC）：`{utc_now()}`",
        f"- Immutable request：`{manifest['request_id']}`",
        f"- Manifest SHA-256：`{manifest['_manifest_sha256']}`",
        f"- v2 schema：`{V2_SCHEMA_VERSION}`",
        f"- v1 audit source SHA-256：`{sha256_file(Path(v1.__file__).resolve())}`",
        "- 本审计只读取已生成的 GNSS-SDR 输出；未读取 raw IQ，未调用 MATLAB、SAGE 或 GNSS-SDR。",
        "- `POSITION_OUTPUT_GAP` 只表示相邻已输出位置历元之间缺少可见输出，不等同于显式 NO_FIX 或物理失锁。",
        "",
        "## 任务级结果",
        "",
        "|任务|环境|执行|定位分类|有效/期望历元|输出覆盖率|最长连续定位(s)|显式无解历元|输出缺口|最大缺口(s)|TTFF下界/上界(s)|失锁事件|QA|",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summaries:
        expected = row.get("expected_position_epoch_count")
        valid = row.get("valid_fix_epoch_count")
        lines.append(
            "|{task_id}|{environment_class}|{execution_status}|{positionability}|"
            "{valid}/{expected}|{coverage}|{max_fix}|{explicit_no_fix}|{gap_count}|"
            "{max_gap}|{ttff_lo}/{ttff_hi}|{losses}|{qa}|".format(
                task_id=_fmt(row.get("task_id")),
                environment_class=_fmt(row.get("environment_class")),
                execution_status=_fmt(row.get("execution_status")),
                positionability=_fmt(row.get("positionability")),
                valid=_fmt(valid),
                expected=_fmt(expected),
                coverage=_fmt(row.get("position_epoch_coverage_fraction")),
                max_fix=_fmt(row.get("max_consecutive_fix_s")),
                explicit_no_fix=_fmt(row.get("explicit_no_fix_epoch_count")),
                gap_count=_fmt(row.get("position_output_gap_count")),
                max_gap=_fmt(row.get("max_position_output_gap_s")),
                ttff_lo=_fmt(row.get("first_fix_receiver_time_lower_bound_s")),
                ttff_hi=_fmt(row.get("first_fix_receiver_time_upper_bound_s")),
                losses=_fmt(row.get("total_lock_loss_events")),
                qa=_fmt(row.get("diagnostic_qa_status")),
            )
        )
    lines.extend(
        [
            "",
            "## 判读边界",
            "",
            "- `SUSTAINED_FIX` 仅表示 GNSS-SDR 在当前配置下具有至少 5 s 的连续有效定位输出。",
            "- tracking MAT 文件的数字后缀已按 GNSS-SDR 实际输出 convention 映射为 channel；这只修正审计 provenance，不改变输入或 GNSS-SDR 结果。",
            "- `carrier_lock_test` 的 20 ms/100 ms 去抖规则仍沿用 v1；tracking lock-loss event 与 PVT 位置输出是两个独立观测层。",
            "- 缺少 NMEA 输出历元被单独标记为 `POSITION_OUTPUT_GAP`，不会被伪造为 explicit no-fix。",
            "- 车辆界面异常而 GNSS-SDR 持续定位时，只能作为车机接收链、恢复逻辑或 HMI 的后续对照线索，不能单凭本审计判定硬件故障。",
            "",
            "## 当前 smoke 结论",
            "",
            "本 v2 审计对 GOOD smoke 运行的工程输出完整性与可定位性进行校正后的只读表达；它不提供车辆端行为结论，也不把 tracking event 解释为物理多径或车辆必然失锁。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--qa-dir", type=Path, required=True)
    parser.add_argument("--task-id", action="append", default=[])
    return parser


def _write_hash_sidecar(path: Path) -> None:
    path.with_suffix(path.suffix + ".sha256").write_text(
        sha256_file(path) + "\n", encoding="ascii"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        qa_dir = args.qa_dir.resolve()
        if qa_dir.exists():
            raise FileExistsError(f"QA namespace exists; new-only audit rejected: {qa_dir}")
        manifest = load_and_validate_manifest(args.manifest, args.expected_manifest_sha256)
        project_root = Path(str(manifest["project_root"])).resolve()
        allowed_root = (project_root / "dataset_generation_logs/darkroom_rx_gnss_sdr_qa").resolve()
        try:
            qa_dir.relative_to(allowed_root)
        except ValueError as exc:
            raise ValueError(f"QA directory must be inside {allowed_root}") from exc
        tasks = select_tasks(manifest["tasks"], args.task_id)
        summaries: list[dict[str, Any]] = []
        prns: list[dict[str, Any]] = []
        losses: list[dict[str, Any]] = []
        intervals: list[dict[str, Any]] = []
        for row in tasks:
            summary, task_prns, task_losses, task_intervals = audit_task_v2(manifest, row)
            summaries.append(summary)
            prns.extend(task_prns)
            losses.extend(task_losses)
            intervals.extend(task_intervals)

        qa_dir.mkdir(parents=True)
        outputs = {
            "task_summary": qa_dir / "task_summary.csv",
            "prn_tracking_summary": qa_dir / "prn_tracking_summary.csv",
            "lock_loss_intervals": qa_dir / "lock_loss_intervals.csv",
            "position_intervals": qa_dir / "position_intervals.csv",
            "vehicle_observation_template": qa_dir / "vehicle_observation_template.csv",
            "report": qa_dir / "signal_quality_report_cn.md",
        }
        _write_csv(outputs["task_summary"], summaries)
        _write_csv(outputs["prn_tracking_summary"], prns)
        _write_csv(outputs["lock_loss_intervals"], losses)
        _write_csv(outputs["position_intervals"], intervals)
        _write_vehicle_template(outputs["vehicle_observation_template"], summaries)
        _write_report(outputs["report"], manifest=manifest, summaries=summaries)
        for path in outputs.values():
            _write_hash_sidecar(path)
        artifact_records = {
            name: {"path": str(path), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            for name, path in outputs.items()
        }
        audit_manifest = {
            "schema_version": V2_SCHEMA_VERSION,
            "created_utc": utc_now(),
            "source_manifest_path": manifest["_manifest_path"],
            "source_manifest_sha256": manifest["_manifest_sha256"],
            "selected_task_ids": [row["task_id"] for row in tasks],
            "raw_iq_read": False,
            "matlab_invoked": False,
            "sage_invoked": False,
            "gnss_sdr_invoked_by_auditor": False,
            "v1_audit_source_path": str(Path(v1.__file__).resolve()),
            "v1_audit_source_sha256": sha256_file(Path(v1.__file__).resolve()),
            "v2_audit_source_path": str(Path(__file__).resolve()),
            "v2_audit_source_sha256": sha256_file(Path(__file__).resolve()),
            "compatibility_changes": [
                "numeric tracking filename suffix maps to channel",
                "NMEA missing emitted epochs are POSITION_OUTPUT_GAP",
                "PVT one-byte MATLAB fields decode as unsigned counts",
                "stdout TTFF is reported as bounded receiver-time evidence",
            ],
            "artifacts": artifact_records,
        }
        manifest_path = qa_dir / "audit_manifest.json"
        manifest_path.write_bytes(canonical_json_bytes(audit_manifest))
        _write_hash_sidecar(manifest_path)
        manifest_sha = sha256_file(manifest_path)
        print(f"QA_DIRECTORY={qa_dir}")
        print(f"AUDIT_MANIFEST={manifest_path}")
        print(f"AUDIT_MANIFEST_SHA256={manifest_sha}")
        print(f"AUDITED_TASKS={len(tasks)}")
        print(f"QA_PASS_TASKS={sum(row['diagnostic_qa_status'] == 'PASS' for row in summaries)}")
        print("RAW_IQ_READ=false")
        print("MATLAB_INVOKED=false")
        print("SAGE_INVOKED=false")
        print("GNSS_SDR_INVOKED_BY_AUDITOR=false")
        return 0
    except Exception as exc:
        print(f"DARKROOM_RX_AUDIT_V2_REJECTED={type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
