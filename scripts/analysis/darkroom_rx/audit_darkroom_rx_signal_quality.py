"""Read-only GNSS-SDR positioning and loss-of-lock audit for 0913DarkroomRx.

The audit never reads raw IQ and never modifies a GNSS-SDR run directory.  It
separates receiver tracking continuity from PVT availability and writes all QA
tables to a caller-supplied, new-only diagnostic namespace.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .darkroom_rx_common import canonical_json_bytes, sha256_file
    from .run_darkroom_rx_gnss_sdr_batch import (
        load_and_validate_manifest,
        select_tasks,
    )
except ImportError:
    from scripts.analysis.darkroom_rx.darkroom_rx_common import (
        canonical_json_bytes,
        sha256_file,
    )
    from scripts.analysis.darkroom_rx.run_darkroom_rx_gnss_sdr_batch import (
        load_and_validate_manifest,
        select_tasks,
    )


LOCK_THRESHOLD = -0.5
BAD_LOCK_DEBOUNCE_S = 0.020
GOOD_REACQUISITION_S = 0.100
SUSTAINED_FIX_MIN_S = 5.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite_float(value: object) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _nmea_seconds_of_day(token: str) -> float | None:
    token = token.strip()
    if len(token) < 6:
        return None
    try:
        hour = int(token[0:2])
        minute = int(token[2:4])
        second = float(token[4:])
    except ValueError:
        return None
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 61):
        return None
    return hour * 3600.0 + minute * 60.0 + second


def _unwrap_day(times: list[float]) -> list[float]:
    unwrapped: list[float] = []
    day_offset = 0.0
    previous: float | None = None
    for value in times:
        adjusted = value + day_offset
        if previous is not None and adjusted < previous - 43_200.0:
            day_offset += 86_400.0
            adjusted = value + day_offset
        unwrapped.append(adjusted)
        previous = adjusted
    return unwrapped


def _run_durations(epoch_times: np.ndarray, mask: np.ndarray) -> list[dict[str, float]]:
    if epoch_times.size == 0 or mask.size != epoch_times.size:
        return []
    positive_steps = np.diff(epoch_times)
    positive_steps = positive_steps[np.isfinite(positive_steps) & (positive_steps > 0)]
    nominal = float(np.median(positive_steps)) if positive_steps.size else 1.0
    gap_limit = max(1.5 * nominal, nominal + 0.25)
    runs: list[dict[str, float]] = []
    start: int | None = None
    for index in range(epoch_times.size):
        contiguous = (
            index > 0
            and math.isfinite(float(epoch_times[index] - epoch_times[index - 1]))
            and 0 < float(epoch_times[index] - epoch_times[index - 1]) <= gap_limit
        )
        if bool(mask[index]):
            if start is None or (index > 0 and not contiguous):
                if start is not None:
                    end = index - 1
                    runs.append(
                        {
                            "start_s": float(epoch_times[start]),
                            "end_s": float(epoch_times[end] + nominal),
                            "duration_s": float(epoch_times[end] - epoch_times[start] + nominal),
                        }
                    )
                start = index
        elif start is not None:
            end = index - 1
            runs.append(
                {
                    "start_s": float(epoch_times[start]),
                    "end_s": float(epoch_times[end] + nominal),
                    "duration_s": float(epoch_times[end] - epoch_times[start] + nominal),
                }
            )
            start = None
    if start is not None:
        end = epoch_times.size - 1
        runs.append(
            {
                "start_s": float(epoch_times[start]),
                "end_s": float(epoch_times[end] + nominal),
                "duration_s": float(epoch_times[end] - epoch_times[start] + nominal),
            }
        )
    return runs


def parse_nmea_lines(lines: Iterable[str]) -> dict[str, Any]:
    """Summarize valid/invalid GGA and RMC epochs without inferring a missing file."""

    raw_epochs: list[tuple[float, bool, int | None, float | None, str]] = []
    recognized = 0
    for raw_line in lines:
        line = raw_line.strip()
        if not line.startswith("$"):
            continue
        fields = line.split("*")[0].split(",")
        sentence = fields[0][-3:].upper()
        if sentence not in {"GGA", "RMC"} or len(fields) < 3:
            continue
        seconds = _nmea_seconds_of_day(fields[1])
        if seconds is None:
            continue
        recognized += 1
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
            raw_epochs.append((seconds, fix_quality > 0, satellites, hdop, sentence))
        else:
            valid = len(fields) > 2 and fields[2].strip().upper() == "A"
            raw_epochs.append((seconds, valid, None, None, sentence))

    if not raw_epochs:
        return {
            "position_output_observed": False,
            "recognized_sentence_count": 0,
            "position_epoch_count": 0,
            "valid_fix_epoch_count": 0,
            "valid_fix_fraction": None,
            "max_consecutive_fix_s": 0.0,
            "fix_interval_count": 0,
            "max_no_fix_interval_s": None,
            "median_valid_sats": None,
            "median_hdop": None,
            "fix_intervals": [],
            "no_fix_intervals": [],
        }

    # Preserve receiver emission order so a midnight rollover can be unwrapped.
    original_times = [item[0] for item in raw_epochs]
    unwrapped = _unwrap_day(original_times)
    grouped: dict[float, dict[str, Any]] = {}
    for item, timestamp in zip(raw_epochs, unwrapped):
        # GNSS-SDR emits matching GGA/RMC timestamps.  Round only for stable grouping.
        key = round(timestamp, 3)
        record = grouped.setdefault(
            key, {"valid": False, "satellites": [], "hdop": []}
        )
        record["valid"] = bool(record["valid"] or item[1])
        if item[2] is not None:
            record["satellites"].append(item[2])
        if item[3] is not None and math.isfinite(item[3]):
            record["hdop"].append(item[3])

    times = np.asarray(sorted(grouped), dtype=float)
    valid = np.asarray([bool(grouped[t]["valid"]) for t in times], dtype=bool)
    fix_runs = _run_durations(times, valid)
    no_fix_runs = _run_durations(times, ~valid)
    valid_sats = [
        value
        for timestamp in times
        if grouped[timestamp]["valid"]
        for value in grouped[timestamp]["satellites"]
    ]
    valid_hdop = [
        value
        for timestamp in times
        if grouped[timestamp]["valid"]
        for value in grouped[timestamp]["hdop"]
    ]
    return {
        "position_output_observed": True,
        "recognized_sentence_count": recognized,
        "position_epoch_count": int(times.size),
        "valid_fix_epoch_count": int(valid.sum()),
        "valid_fix_fraction": float(valid.mean()) if valid.size else None,
        "max_consecutive_fix_s": max(
            (run["duration_s"] for run in fix_runs), default=0.0
        ),
        "fix_interval_count": len(fix_runs),
        "max_no_fix_interval_s": max(
            (run["duration_s"] for run in no_fix_runs), default=0.0
        ),
        "median_valid_sats": float(np.median(valid_sats)) if valid_sats else None,
        "median_hdop": float(np.median(valid_hdop)) if valid_hdop else None,
        "fix_intervals": fix_runs,
        "no_fix_intervals": no_fix_runs,
    }


def classify_positionability(
    summary: Mapping[str, Any], *, recording_duration_s: float
) -> str:
    """Classify observed receiver output; this is not a physical LOS classifier."""

    if summary.get("position_output_observed") is False:
        return "INCONCLUSIVE_NO_POSITION_OUTPUT"
    valid_count = int(summary.get("valid_fix_epoch_count") or 0)
    if valid_count == 0:
        return "NO_FIX_OBSERVED"
    max_run = float(summary.get("max_consecutive_fix_s") or 0.0)
    if max_run >= SUSTAINED_FIX_MIN_S:
        return "SUSTAINED_FIX"
    if int(summary.get("fix_interval_count") or 0) > 1 or valid_count > 1:
        return "INTERMITTENT_FIX"
    return "TRANSIENT_FIX_ONLY"


def extract_debounced_lock_events(
    time_s: Sequence[float] | np.ndarray,
    carrier_lock_test: Sequence[float] | np.ndarray,
    *,
    threshold: float = LOCK_THRESHOLD,
    bad_debounce_s: float = BAD_LOCK_DEBOUNCE_S,
    good_reacquisition_s: float = GOOD_REACQUISITION_S,
) -> list[dict[str, Any]]:
    """Extract confirmed lock-loss runs without bridging missing/continuity gaps."""

    times = np.asarray(time_s, dtype=float).reshape(-1)
    locks = np.asarray(carrier_lock_test, dtype=float).reshape(-1)
    if times.size != locks.size:
        raise ValueError("time and carrier_lock_test arrays must have equal length")
    if times.size == 0:
        return []
    finite = np.isfinite(times) & np.isfinite(locks)
    times = times[finite]
    locks = locks[finite]
    if times.size == 0:
        return []
    order = np.argsort(times, kind="stable")
    times = times[order]
    locks = locks[order]
    unique = np.concatenate(([True], np.diff(times) > 0))
    times = times[unique]
    locks = locks[unique]
    if times.size == 0:
        return []
    positive_dt = np.diff(times)
    positive_dt = positive_dt[np.isfinite(positive_dt) & (positive_dt > 0)]
    nominal_dt = float(np.median(positive_dt)) if positive_dt.size else 0.001
    gap_limit = max(nominal_dt * 2.5, nominal_dt + 1e-9)
    boundaries = [0]
    boundaries.extend(
        int(index + 1)
        for index, delta in enumerate(np.diff(times))
        if not math.isfinite(float(delta)) or delta <= 0 or delta > gap_limit
    )
    boundaries.append(times.size)
    events: list[dict[str, Any]] = []
    for segment_start, segment_end in zip(boundaries[:-1], boundaries[1:]):
        segment_times = times[segment_start:segment_end]
        segment_locks = locks[segment_start:segment_end]
        bad = segment_locks < threshold
        index = 0
        while index < bad.size:
            if not bad[index]:
                index += 1
                continue
            start = index
            while index < bad.size and bad[index]:
                index += 1
            stop = index
            right_censored = stop == bad.size
            end_time = (
                float(segment_times[stop])
                if stop < segment_times.size
                else float(segment_times[-1] + nominal_dt)
            )
            duration = end_time - float(segment_times[start])
            if duration + 1e-12 < bad_debounce_s:
                continue
            reacquired = False
            reacquisition_time: float | None = None
            if stop < bad.size:
                good_stop = stop
                while good_stop < bad.size and not bad[good_stop]:
                    good_stop += 1
                good_end_time = (
                    float(segment_times[good_stop])
                    if good_stop < segment_times.size
                    else float(segment_times[-1] + nominal_dt)
                )
                if good_end_time - float(segment_times[stop]) + 1e-12 >= good_reacquisition_s:
                    reacquired = True
                    reacquisition_time = float(segment_times[stop] + good_reacquisition_s)
            events.append(
                {
                    "loss_start_s": float(segment_times[start]),
                    "loss_end_s": end_time,
                    "duration_ms": float(duration * 1000.0),
                    "reacquired": reacquired,
                    "reacquisition_confirmed_s": reacquisition_time,
                    "right_censored": right_censored,
                    "continuity_gap_bridged": False,
                }
            )
    return events


def _load_mat_fields(path: Path, names: Sequence[str]) -> dict[str, np.ndarray]:
    """Read numeric MAT fields read-only, supporting classic and MATLAB 7.3 files."""

    try:
        from scipy.io import loadmat

        payload = loadmat(path, variable_names=list(names), squeeze_me=True)
        return {
            name: np.asarray(payload[name])
            for name in names
            if name in payload and not name.startswith("__")
        }
    except (NotImplementedError, ValueError, OSError):
        from scripts.analysis.rain_gnss_sdr.audit_rain_gnss_sdr_mvp import mat_fields

        arrays, _info, _available = mat_fields(path, names)
        return arrays


def _distribution(values: np.ndarray) -> dict[str, float | int | None]:
    finite = np.asarray(values, dtype=float).reshape(-1)
    finite = finite[np.isfinite(finite)]
    if not finite.size:
        return {"count": 0, "median": None, "p10": None, "p90": None}
    return {
        "count": int(finite.size),
        "median": float(np.median(finite)),
        "p10": float(np.percentile(finite, 10)),
        "p90": float(np.percentile(finite, 90)),
    }


def _tracking_channel(path: Path) -> int | None:
    match = re.search(r"(?:ch_|channel_?)(\d+)", path.stem, re.IGNORECASE)
    return int(match.group(1)) if match else None


def audit_tracking_file(
    path: Path, *, task_id: str, sample_rate_hz: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    names = [
        "PRN",
        "PRN_start_sample_count",
        "CN0_SNV_dB_Hz",
        "carrier_lock_test",
        "carrier_doppler_hz",
    ]
    arrays = _load_mat_fields(path, names)
    required = ["PRN", "PRN_start_sample_count", "carrier_lock_test"]
    missing = [name for name in required if name not in arrays]
    if missing:
        raise ValueError(f"tracking MAT missing fields {missing}: {path}")
    flattened = {name: np.asarray(value).reshape(-1) for name, value in arrays.items()}
    lengths = {name: value.size for name, value in flattened.items()}
    if len(set(lengths.values())) != 1:
        raise ValueError(f"tracking MAT field lengths differ (no truncation allowed): {lengths}")
    prn = flattened["PRN"].astype(float)
    sample = flattened["PRN_start_sample_count"].astype(float)
    lock = flattened["carrier_lock_test"].astype(float)
    cn0 = flattened.get("CN0_SNV_dB_Hz", np.full(prn.size, np.nan)).astype(float)
    doppler = flattened.get("carrier_doppler_hz", np.full(prn.size, np.nan)).astype(float)
    channel = _tracking_channel(path)
    summaries: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    valid_prns = sorted({int(value) for value in prn[np.isfinite(prn)] if 1 <= value <= 32})
    for prn_number in valid_prns:
        mask = (prn == prn_number) & np.isfinite(sample)
        if not mask.any():
            continue
        times = sample[mask] / float(sample_rate_hz)
        prn_lock = lock[mask]
        events = extract_debounced_lock_events(times, prn_lock)
        cn0_stats = _distribution(cn0[mask])
        doppler_stats = _distribution(doppler[mask])
        finite_lock = np.isfinite(prn_lock)
        lock_good = finite_lock & (prn_lock >= LOCK_THRESHOLD)
        positive_dt = np.diff(np.sort(times[np.isfinite(times)]))
        positive_dt = positive_dt[positive_dt > 0]
        nominal_dt = float(np.median(positive_dt)) if positive_dt.size else None
        continuity_gaps = (
            int(np.sum(positive_dt > nominal_dt * 2.5))
            if nominal_dt is not None
            else 0
        )
        summary = {
            "task_id": task_id,
            "tracking_file": str(path),
            "tracking_file_sha256": sha256_file(path),
            "tracking_channel": channel,
            "prn": f"G{prn_number:02d}",
            "record_count": int(mask.sum()),
            "first_tracking_time_s": float(np.min(times)),
            "last_tracking_time_s": float(np.max(times)),
            "tracking_span_s": float(np.max(times) - np.min(times)),
            "nominal_tracking_interval_s": nominal_dt,
            "continuity_gap_count": continuity_gaps,
            "lock_observed_count": int(finite_lock.sum()),
            "lock_good_fraction": (
                float(lock_good.sum() / finite_lock.sum()) if finite_lock.any() else None
            ),
            "loss_event_count": len(events),
            "total_confirmed_loss_s": float(
                sum(event["duration_ms"] for event in events) / 1000.0
            ),
            "max_confirmed_loss_s": float(
                max((event["duration_ms"] for event in events), default=0.0) / 1000.0
            ),
            "reacquired_event_count": sum(bool(event["reacquired"]) for event in events),
            "right_censored_event_count": sum(
                bool(event["right_censored"]) for event in events
            ),
            "cn0_count": cn0_stats["count"],
            "cn0_median_db_hz": cn0_stats["median"],
            "cn0_p10_db_hz": cn0_stats["p10"],
            "cn0_p90_db_hz": cn0_stats["p90"],
            "doppler_count": doppler_stats["count"],
            "doppler_median_hz": doppler_stats["median"],
            "doppler_p10_hz": doppler_stats["p10"],
            "doppler_p90_hz": doppler_stats["p90"],
        }
        summaries.append(summary)
        for event_index, event in enumerate(events, start=1):
            event_rows.append(
                {
                    "task_id": task_id,
                    "tracking_file": str(path),
                    "tracking_channel": channel,
                    "prn": f"G{prn_number:02d}",
                    "loss_event_index": event_index,
                    **event,
                }
            )
    return summaries, event_rows


def _pvt_summary(paths: Sequence[Path]) -> dict[str, Any]:
    names = [
        "RX_time",
        "TOW_at_current_symbol_ms",
        "solution_status",
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
        arrays = _load_mat_fields(path, names)
        status = np.asarray(arrays.get("solution_status", [])).reshape(-1).astype(float)
        sats = np.asarray(arrays.get("valid_sats", np.full(status.size, np.nan))).reshape(-1).astype(float)
        time_values = arrays.get("RX_time", arrays.get("TOW_at_current_symbol_ms", []))
        times = np.asarray(time_values).reshape(-1).astype(float)
        if not status.size or times.size != status.size or sats.size != status.size:
            continue
        if "TOW_at_current_symbol_ms" in arrays and "RX_time" not in arrays:
            times = times / 1000.0
        finite_times = times[np.isfinite(times)]
        if finite_times.size:
            base = float(finite_times[0])
            times = times - base
        valid = np.isfinite(status) & (status > 0) & np.isfinite(sats) & (sats >= 4)
        all_time.extend(times.tolist())
        all_valid.extend(valid.tolist())
        all_sats.extend(sats[valid].tolist())
        hdop = np.asarray(arrays.get("HDOP", np.full(status.size, np.nan))).reshape(-1).astype(float)
        if hdop.size == status.size:
            all_hdop.extend(hdop[valid & np.isfinite(hdop)].tolist())
    if not all_time:
        return parse_nmea_lines([])
    order = np.argsort(np.asarray(all_time), kind="stable")
    times = np.asarray(all_time, dtype=float)[order]
    valid = np.asarray(all_valid, dtype=bool)[order]
    unique = np.concatenate(([True], np.diff(times) > 1e-9))
    times = times[unique]
    valid = valid[unique]
    fix_runs = _run_durations(times, valid)
    no_fix_runs = _run_durations(times, ~valid)
    return {
        "position_output_observed": True,
        "recognized_sentence_count": 0,
        "position_epoch_count": int(times.size),
        "valid_fix_epoch_count": int(valid.sum()),
        "valid_fix_fraction": float(valid.mean()),
        "max_consecutive_fix_s": max(
            (run["duration_s"] for run in fix_runs), default=0.0
        ),
        "fix_interval_count": len(fix_runs),
        "max_no_fix_interval_s": max(
            (run["duration_s"] for run in no_fix_runs), default=0.0
        ),
        "median_valid_sats": float(np.median(all_sats)) if all_sats else None,
        "median_hdop": float(np.median(all_hdop)) if all_hdop else None,
        "fix_intervals": fix_runs,
        "no_fix_intervals": no_fix_runs,
    }


def _read_nmea_files(paths: Sequence[Path]) -> dict[str, Any]:
    lines: list[str] = []
    for path in paths:
        lines.extend(path.read_text(encoding="ascii", errors="replace").splitlines())
    return parse_nmea_lines(lines)


def _latest_receipt(request_root: Path, task_id: str) -> tuple[Path | None, dict[str, Any] | None]:
    paths = sorted((request_root / "receipts" / task_id).glob("*_execution_receipt.json"))
    if not paths:
        return None, None
    path = paths[-1]
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.is_file() or sidecar.read_text(encoding="ascii").strip() != sha256_file(path):
        raise ValueError(f"receipt hash sidecar missing or invalid: {path}")
    return path, json.loads(path.read_text(encoding="utf-8"))


def _flatten_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def audit_task(
    manifest: Mapping[str, Any], row: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    task_id = str(row["task_id"])
    request_root = Path(str(manifest["_manifest_path"])).parent
    output = Path(str(row["output_windows_path"]))
    receipt_path, receipt = _latest_receipt(request_root, task_id)
    if receipt is not None:
        if receipt.get("manifest_sha256") != manifest["_manifest_sha256"]:
            raise ValueError(f"{task_id}: receipt manifest SHA mismatch")
        if receipt.get("task_id") != task_id or Path(receipt.get("output_path", "")) != output:
            raise ValueError(f"{task_id}: receipt identity/output mismatch")
    files = _flatten_files(output) if output.is_dir() else []
    tracking_paths = sorted((output / "tracking").glob("*.mat")) if output.is_dir() else []
    telemetry_paths = sorted((output / "telemetry").glob("*")) if output.is_dir() else []
    nmea_paths = sorted(output.rglob("*.nmea")) if output.is_dir() else []
    pvt_paths = (
        sorted(path for path in output.rglob("*.mat") if "pvt" in path.stem.lower())
        if output.is_dir()
        else []
    )
    prn_rows: list[dict[str, Any]] = []
    loss_rows: list[dict[str, Any]] = []
    tracking_errors: list[str] = []
    for path in tracking_paths:
        try:
            summaries, events = audit_tracking_file(
                path, task_id=task_id, sample_rate_hz=int(row["sample_rate_hz"])
            )
            prn_rows.extend(summaries)
            loss_rows.extend(events)
        except Exception as exc:
            tracking_errors.append(f"{path.name}: {type(exc).__name__}: {exc}")

    if nmea_paths:
        position = _read_nmea_files(nmea_paths)
        position_source = "NMEA"
    elif pvt_paths:
        position = _pvt_summary(pvt_paths)
        position_source = "PVT_MAT"
    else:
        position = parse_nmea_lines([])
        position_source = "MISSING"
    positionability = classify_positionability(
        position, recording_duration_s=float(row["estimated_duration_s"])
    )
    position_intervals = [
        {"task_id": task_id, "interval_type": "FIX", **interval}
        for interval in position["fix_intervals"]
    ] + [
        {"task_id": task_id, "interval_type": "NO_FIX", **interval}
        for interval in position["no_fix_intervals"]
    ]

    execution_status = receipt.get("status") if receipt else "NOT_EXECUTED"
    diagnostic_status = "PASS"
    reasons: list[str] = []
    if execution_status != "completed":
        diagnostic_status = "INCOMPLETE"
        reasons.append(f"execution_status={execution_status}")
    if not output.is_dir():
        diagnostic_status = "INCOMPLETE"
        reasons.append("output_directory_missing")
    if not tracking_paths or not prn_rows:
        diagnostic_status = "INCOMPLETE"
        reasons.append("usable_tracking_output_missing")
    if tracking_errors:
        diagnostic_status = "INCOMPLETE"
        reasons.append("tracking_parse_error")
    if position_source == "MISSING":
        diagnostic_status = "INCOMPLETE"
        reasons.append("position_output_missing")
    summary = {
        "task_id": task_id,
        "environment_class": row["environment_class"],
        "condition": row["condition"],
        "source_file_name": row["source_file_name"],
        "sample_rate_hz": row["sample_rate_hz"],
        "recording_duration_s": row["estimated_duration_s"],
        "execution_status": execution_status,
        "execution_receipt": str(receipt_path) if receipt_path else "",
        "execution_exit_code": receipt.get("exit_code") if receipt else None,
        "execution_elapsed_s": receipt.get("elapsed_s") if receipt else None,
        "output_path": str(output),
        "output_file_count": len(files),
        "output_total_bytes": sum(path.stat().st_size for path in files),
        "tracking_mat_count": len(tracking_paths),
        "tracking_prn_count": len({record["prn"] for record in prn_rows}),
        "telemetry_file_count": len([path for path in telemetry_paths if path.is_file()]),
        "position_source": position_source,
        "positionability": positionability,
        "position_epoch_count": position["position_epoch_count"],
        "valid_fix_epoch_count": position["valid_fix_epoch_count"],
        "valid_fix_fraction": position["valid_fix_fraction"],
        "max_consecutive_fix_s": position["max_consecutive_fix_s"],
        "max_no_fix_interval_s": position["max_no_fix_interval_s"],
        "median_valid_sats": position["median_valid_sats"],
        "median_hdop": position["median_hdop"],
        "total_lock_loss_events": sum(record["loss_event_count"] for record in prn_rows),
        "max_lock_loss_s_across_prns": max(
            (record["max_confirmed_loss_s"] for record in prn_rows), default=0.0
        ),
        "diagnostic_qa_status": diagnostic_status,
        "diagnostic_qa_reasons": ";".join(reasons),
        "tracking_parse_errors": ";".join(tracking_errors),
        "raw_iq_read_by_auditor": False,
    }
    return summary, prn_rows, loss_rows, position_intervals


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("x", newline="", encoding="utf-8-sig") as handle:
        if not fieldnames:
            handle.write("")
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: object, digits: int = 3) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _write_report(
    path: Path,
    *,
    manifest: Mapping[str, Any],
    summaries: Sequence[Mapping[str, Any]],
) -> None:
    lines = [
        "# 0913DarkroomRx GNSS-SDR 信号质量只读审计",
        "",
        f"- 生成时间（UTC）：`{utc_now()}`",
        f"- Immutable request：`{manifest['request_id']}`",
        f"- Manifest SHA-256：`{manifest['_manifest_sha256']}`",
        "- 输入格式：10.23 MHz、interleaved signed int16 little-endian I/Q。",
        "- 文件名 `pool` 的冻结语义：`POOR`。",
        "- 本审计未读取 raw IQ；只读取已生成的 GNSS-SDR tracking/PVT/NMEA 输出。",
        "",
        "## 任务级定位结果",
        "",
        "|任务|环境|状态|执行|定位分类|有效历元|最长连续定位 (s)|最长无定位 (s)|跟踪 PRN|失锁事件|QA|",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summaries:
        lines.append(
            "|{task_id}|{environment_class}|{condition}|{execution_status}|"
            "{positionability}|{valid_fix_epoch_count}|{max_consecutive_fix_s}|"
            "{max_no_fix_interval_s}|{tracking_prn_count}|{total_lock_loss_events}|"
            "{diagnostic_qa_status}|".format(
                **{key: _fmt(value) for key, value in row.items()}
            )
        )
    lines.extend(
        [
            "",
            "## 判读边界",
            "",
            "- `SUSTAINED_FIX` 的报告门槛为至少连续 5 s 有效定位，仅是本次工程诊断规则。",
            "- `carrier_lock_test < -0.5` 连续至少 20 ms 才计为失锁；恢复需连续 100 ms 锁定。时间缺口不跨越拼接。",
            "- `NO_FIX_OBSERVED` 只表示 GNSS-SDR 在该记录和当前配置下未输出有效解，不等于物理上完全无 GNSS 信号。",
            "- 车辆界面异常而 GNSS-SDR 能持续定位时，只能提示车机接收链、恢复策略或 HMI 具有特异性，不能单凭此审计认定硬件故障。",
            "- GOOD 记录若也无法得到可审计的跟踪/PVT 输出，应先检查采样格式、时钟/频偏和 GNSS-SDR 配置，不能直接归因信道过苛刻。",
            "",
            "## 车辆界面对照判决建议",
            "",
            "|车辆界面|GNSS-SDR|保守解释|",
            "|---|---|---|",
            "|异常/不恢复|NO_FIX_OBSERVED|仿真信号过苛刻的证据增强，但仍需检查配置与输入链|",
            "|异常/不恢复|SUSTAINED_FIX|更倾向车机接收链、恢复逻辑或界面更新问题|",
            "|正常|SUSTAINED_FIX|两套接收端对该记录均可定位|",
            "|任意|INCONCLUSIVE_NO_POSITION_OUTPUT|输出链不完整，不能作接收能力判决|",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_vehicle_template(path: Path, summaries: Sequence[Mapping[str, Any]]) -> None:
    rows = [
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
    ]
    _write_csv(path, rows)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--qa-dir", type=Path, required=True)
    parser.add_argument("--task-id", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        qa_dir = args.qa_dir.resolve()
        if qa_dir.exists():
            raise FileExistsError(f"QA namespace exists; new-only audit rejected: {qa_dir}")
        manifest = load_and_validate_manifest(
            args.manifest, args.expected_manifest_sha256
        )
        project_root = Path(str(manifest["project_root"])).resolve()
        allowed_root = (project_root / "dataset_generation_logs/darkroom_rx_gnss_sdr_qa").resolve()
        try:
            qa_dir.relative_to(allowed_root)
        except ValueError as exc:
            raise ValueError(f"QA directory must be inside {allowed_root}") from exc
        tasks = select_tasks(manifest["tasks"], args.task_id)
        task_summaries: list[dict[str, Any]] = []
        prn_summaries: list[dict[str, Any]] = []
        lock_events: list[dict[str, Any]] = []
        position_intervals: list[dict[str, Any]] = []
        for row in tasks:
            task, prns, losses, positions = audit_task(manifest, row)
            task_summaries.append(task)
            prn_summaries.extend(prns)
            lock_events.extend(losses)
            position_intervals.extend(positions)
        qa_dir.mkdir(parents=True)
        outputs = {
            "task_summary": qa_dir / "task_summary.csv",
            "prn_tracking_summary": qa_dir / "prn_tracking_summary.csv",
            "lock_loss_intervals": qa_dir / "lock_loss_intervals.csv",
            "position_intervals": qa_dir / "position_intervals.csv",
            "vehicle_observation_template": qa_dir / "vehicle_observation_template.csv",
            "report": qa_dir / "signal_quality_report_cn.md",
        }
        _write_csv(outputs["task_summary"], task_summaries)
        _write_csv(outputs["prn_tracking_summary"], prn_summaries)
        _write_csv(outputs["lock_loss_intervals"], lock_events)
        _write_csv(outputs["position_intervals"], position_intervals)
        _write_vehicle_template(outputs["vehicle_observation_template"], task_summaries)
        _write_report(outputs["report"], manifest=manifest, summaries=task_summaries)
        artifact_records = {
            name: {"path": str(path), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
            for name, path in outputs.items()
        }
        audit_manifest = {
            "schema_version": "darkroom-rx-signal-quality-audit-v1",
            "created_utc": utc_now(),
            "source_manifest_path": manifest["_manifest_path"],
            "source_manifest_sha256": manifest["_manifest_sha256"],
            "selected_task_ids": [row["task_id"] for row in tasks],
            "raw_iq_read": False,
            "matlab_invoked": False,
            "sage_invoked": False,
            "artifacts": artifact_records,
        }
        manifest_path = qa_dir / "audit_manifest.json"
        manifest_path.write_bytes(canonical_json_bytes(audit_manifest))
        manifest_sha = sha256_file(manifest_path)
        (qa_dir / "audit_manifest.sha256").write_text(manifest_sha + "\n", encoding="ascii")
        print(f"QA_DIRECTORY={qa_dir}")
        print(f"AUDIT_MANIFEST={manifest_path}")
        print(f"AUDIT_MANIFEST_SHA256={manifest_sha}")
        print(f"AUDITED_TASKS={len(tasks)}")
        print(f"QA_PASS_TASKS={sum(row['diagnostic_qa_status'] == 'PASS' for row in task_summaries)}")
        print("RAW_IQ_READ=false")
        print("MATLAB_INVOKED=false")
        print("SAGE_INVOKED=false")
        return 0
    except Exception as exc:
        print(f"DARKROOM_RX_AUDIT_REJECTED={type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
