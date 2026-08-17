#!/usr/bin/env python3
"""Generate read-only batch-sampled-v1 manifests and offline coverage replay.

This planner never opens raw IQ, never calls MATLAB/SAGE, and never writes
inside a scene or a sage_results directory.  It uses only Stage0 window CSVs,
trajectory/geometry text/CSV files, and existing Stage3/Stage4 CSVs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


PROFILE_VERSION = "batch-sampled-v1"
SCHEMA_VERSION = "sampling-manifest-v1"
TIME_STRATA = 24
TIME_MINIMUM = 20
INITIAL_TARGET = 800
MAX_STAGE1_WINDOWS = 1200
BURST_HALF_WIDTH = 5
BURST_WIDTH = 2 * BURST_HALF_WIDTH + 1
MAX_GEOMETRY_DELTA_SECONDS = 5.0
MIN_GEOMETRY_COVERAGE = 0.90
MAX_STAGE2_BASE_CANDIDATES = 24
STAGE2_NEIGHBOR_RADIUS = 2


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    scene_id: str
    prn: str
    tracking_channel: int
    sampling_rate_hz: int
    result_relative_path: str
    task_group: str


@dataclass
class GeometryResult:
    status: str
    warning: str
    source_file: str
    anchor_source: str
    coverage_ratio: float | None
    p95_delta_seconds: float | None
    max_delta_seconds: float | None
    mapping: dict[int, dict[str, Any]]


GOLD_TASKS: tuple[TaskSpec, ...] = (
    TaskSpec(
        "reference_F1023_V70_D0117_P2_G06_ch4",
        "F1023_V70_D0117_P2",
        "G06",
        4,
        10_230_000,
        "sage_results/G06_nav_sage_v1",
        "reference",
    ),
    TaskSpec(
        "reference_F1023_V70_D0117_P2_G11_ch5",
        "F1023_V70_D0117_P2",
        "G11",
        5,
        10_230_000,
        "sage_results/nav_sage_v2/G11",
        "reference",
    ),
    TaskSpec(
        "reference_F1023_V70_D0117_P2_G12_ch6",
        "F1023_V70_D0117_P2",
        "G12",
        6,
        10_230_000,
        "sage_results/nav_sage_v2/G12",
        "reference",
    ),
    TaskSpec(
        "reference_F1023_V70_D0117_P2_G25_ch0",
        "F1023_V70_D0117_P2",
        "G25",
        0,
        10_230_000,
        "sage_results/nav_sage_v2/G25",
        "reference",
    ),
    TaskSpec(
        "reference_F1023_V70_D0117_P2_G28_ch1",
        "F1023_V70_D0117_P2",
        "G28",
        1,
        10_230_000,
        "sage_results/nav_sage_v2/G28",
        "reference",
    ),
    TaskSpec(
        "reference_F1023_V70_D0117_P2_G29_ch7",
        "F1023_V70_D0117_P2",
        "G29",
        7,
        10_230_000,
        "sage_results/nav_sage_v2/G29",
        "reference",
    ),
    TaskSpec(
        "reference_F1023_V70_D0117_P2_G32_ch11",
        "F1023_V70_D0117_P2",
        "G32",
        11,
        10_230_000,
        "sage_results/nav_sage_v2/G32",
        "reference",
    ),
    TaskSpec(
        "waveA_F1023_V70_D0120_P7_G16_ch1",
        "F1023_V70_D0120_P7",
        "G16",
        1,
        10_230_000,
        "sage_results/nav_sage_v2/G16",
        "waveA",
    ),
    TaskSpec(
        "waveA_F1023_v50_D0127_P1_G25_ch0",
        "F1023_v50_D0127_P1",
        "G25",
        0,
        10_230_000,
        "sage_results/nav_sage_v2/G25",
        "waveA",
    ),
    TaskSpec(
        "waveA_F1023_V70_D0122_P1_G12_ch6",
        "F1023_V70_D0122_P1",
        "G12",
        6,
        10_230_000,
        "sage_results/nav_sage_v2/G12",
        "waveA",
    ),
    TaskSpec(
        "wave2A_F1023_V120_D0121_P2_G11_ch0",
        "F1023_V120_D0121_P2",
        "G11",
        0,
        10_230_000,
        "sage_results/nav_sage_v2/G11",
        "wave2A",
    ),
)


def stable_int(*parts: object) -> int:
    """Return a deterministic unsigned integer from arbitrary string parts."""

    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return [dict(row) for row in reader]


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parse_int(value: Any) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    return int(round(number))


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "pass"}


def normalize_group(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"low", "mid", "high"}:
        return text.capitalize()
    return ""


def load_stage0(path: Path) -> list[dict[str, Any]]:
    rows = read_csv_rows(path)
    required = {
        "window_id",
        "recording_time_s",
        "tow_s",
        "cn0_db_hz",
        "vehicle_speed_kmh",
        "relative_doppler_bound_hz",
    }
    missing = sorted(required - set(rows[0]) if rows else required)
    if missing:
        raise ValueError(f"Stage0 CSV missing columns {missing}: {path}")
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        window_id = parse_int(row.get("window_id"))
        if window_id is None or window_id in seen:
            raise ValueError(f"Invalid or duplicate window_id in {path}: {row.get('window_id')}")
        seen.add(window_id)
        item = dict(row)
        item["window_id"] = window_id
        item["recording_time_s_value"] = parse_float(row.get("recording_time_s"))
        item["tow_s_value"] = parse_float(row.get("tow_s"))
        item["cn0_value"] = parse_float(row.get("cn0_db_hz"))
        item["speed_value"] = parse_float(row.get("vehicle_speed_kmh"))
        item["doppler_bound_value"] = parse_float(row.get("relative_doppler_bound_hz"))
        normalized.append(item)
    return sorted(normalized, key=lambda row: row["window_id"])


def parse_nmea_datetime(line: str) -> datetime | None:
    parts = line.strip().split(",")
    if len(parts) < 10 or parts[0].split("*")[0] not in {"$GPRMC", "$GNRMC"}:
        return None
    if parts[2] != "A":
        return None
    time_text = parts[1].split("*")[0]
    date_text = parts[9].split("*")[0]
    if not time_text or not date_text:
        return None
    try:
        if "." in time_text:
            time_value = datetime.strptime(time_text, "%H%M%S.%f").time()
        else:
            time_value = datetime.strptime(time_text, "%H%M%S").time()
        date_value = datetime.strptime(date_text, "%d%m%y").date()
    except ValueError:
        return None
    return datetime.combine(date_value, time_value, tzinfo=timezone.utc)


def find_nmea_anchor(scene_dir: Path) -> tuple[datetime | None, Path | None, str]:
    files = sorted((scene_dir / "trajectory").glob("*.nmea"))
    if len(files) != 1:
        return None, None, f"expected one trajectory NMEA file, found {len(files)}"
    path = files[0]
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                anchor = parse_nmea_datetime(line)
                if anchor is not None:
                    return anchor, path, "trajectory_first_valid_RMC"
    except OSError as exc:
        return None, path, f"cannot read trajectory NMEA: {exc}"
    return None, path, "no valid active RMC timestamp"


def parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def find_geometry_file(scene_dir: Path) -> Path | None:
    exact = sorted((scene_dir / "satellite").glob("*_satellite_elevation_timeseries.csv"))
    if exact:
        return exact[0]
    fallback = sorted((scene_dir / "satellite").glob("*timeseries*.csv"))
    return fallback[0] if fallback else None


def load_geometry_result(
    scene_dir: Path,
    prn: str,
    stage0_rows: Sequence[dict[str, Any]],
) -> GeometryResult:
    source_file = find_geometry_file(scene_dir)
    anchor, nmea_path, anchor_source = find_nmea_anchor(scene_dir)
    warnings: list[str] = []
    if source_file is None:
        warnings.append("satellite elevation timeseries CSV is missing")
    if anchor is None:
        warnings.append(anchor_source)
    if source_file is None or anchor is None:
        return GeometryResult(
            "warning_fallback",
            "; ".join(warnings),
            str(source_file) if source_file else "",
            anchor_source,
            None,
            None,
            None,
            {},
        )

    try:
        source_rows = read_csv_rows(source_file)
    except (OSError, ValueError) as exc:
        return GeometryResult(
            "warning_fallback",
            f"cannot read geometry CSV: {exc}",
            str(source_file),
            anchor_source,
            None,
            None,
            None,
            {},
        )

    geometry_rows: list[dict[str, Any]] = []
    for row in source_rows:
        if str(row.get("prn", "")).strip().upper() != prn.upper():
            continue
        timestamp = parse_utc(row.get("utc_time", ""))
        elevation = parse_float(row.get("elevation_deg"))
        if timestamp is None or elevation is None:
            continue
        geometry_rows.append(
            {
                "timestamp": timestamp,
                "elevation_deg": elevation,
                "azimuth_deg": parse_float(row.get("azimuth_deg")),
                "snr_db_hz": parse_float(row.get("snr_db_hz")),
                "elevation_group": normalize_group(row.get("elevation_group")),
                "nmea_file": str(row.get("nmea_file", "")).strip(),
            }
        )
    if not geometry_rows:
        return GeometryResult(
            "warning_fallback",
            f"no valid geometry rows for {prn}",
            str(source_file),
            anchor_source,
            0.0,
            None,
            None,
            {},
        )

    geometry_rows.sort(key=lambda row: row["timestamp"])
    times = [row["timestamp"] for row in geometry_rows]
    nmea_name = nmea_path.name if nmea_path else ""
    nonempty_nmea_names = {row["nmea_file"] for row in geometry_rows if row["nmea_file"]}
    matching_nmea = bool(nonempty_nmea_names) and nonempty_nmea_names == {nmea_name}
    if not matching_nmea:
        warnings.append("geometry nmea_file does not match the single trajectory file")

    deltas: list[float] = []
    provisional: dict[int, dict[str, Any]] = {}
    for row in stage0_rows:
        recording_time = row["recording_time_s_value"]
        if recording_time is None:
            continue
        target = anchor + timedelta(seconds=recording_time)
        position = bisect_left(times, target)
        candidates = []
        if position < len(times):
            candidates.append(position)
        if position > 0:
            candidates.append(position - 1)
        if not candidates:
            continue
        nearest_index = min(candidates, key=lambda index: abs((times[index] - target).total_seconds()))
        delta = abs((times[nearest_index] - target).total_seconds())
        deltas.append(delta)
        if delta <= MAX_GEOMETRY_DELTA_SECONDS:
            geometry = geometry_rows[nearest_index]
            provisional[row["window_id"]] = {
                "elevation_deg": geometry["elevation_deg"],
                "azimuth_deg": geometry["azimuth_deg"],
                "snr_db_hz": geometry["snr_db_hz"],
                "elevation_group": geometry["elevation_group"],
                "geometry_source_utc": geometry["timestamp"].isoformat().replace("+00:00", "Z"),
                "geometry_time_delta_s": delta,
            }

    coverage_ratio = len(provisional) / len(stage0_rows) if stage0_rows else 0.0
    p95_delta = percentile(deltas, 0.95)
    max_delta = max(deltas) if deltas else None
    if coverage_ratio < MIN_GEOMETRY_COVERAGE:
        warnings.append(
            f"window-level geometry coverage {coverage_ratio:.3f} is below {MIN_GEOMETRY_COVERAGE:.2f}"
        )
    if p95_delta is None or p95_delta > MAX_GEOMETRY_DELTA_SECONDS:
        warnings.append(
            f"geometry nearest-time p95 is {p95_delta!r}s, tolerance is {MAX_GEOMETRY_DELTA_SECONDS:.1f}s"
        )
    if not matching_nmea:
        warnings.append("geometry alignment is not trusted because source NMEA identity is unverified")

    reliable = (
        coverage_ratio >= MIN_GEOMETRY_COVERAGE
        and p95_delta is not None
        and p95_delta <= MAX_GEOMETRY_DELTA_SECONDS
        and matching_nmea
    )
    if reliable:
        status = "verified"
        mapping = provisional
        if len(provisional) < len(stage0_rows):
            warnings.append("some windows are outside geometry tolerance; those rows have no elevation stratum")
    else:
        status = "warning_fallback"
        mapping = {}
        warnings.append("elevation sampling disabled; falling back to time plus C/N0")
    return GeometryResult(
        status,
        "; ".join(dict.fromkeys(warnings)),
        str(source_file),
        anchor_source,
        coverage_ratio,
        p95_delta,
        max_delta,
        mapping,
    )


def assign_time_bins(rows: Sequence[dict[str, Any]]) -> None:
    values = [row["recording_time_s_value"] for row in rows]
    finite = [value for value in values if value is not None]
    if not finite:
        values = [float(index) for index in range(len(rows))]
        finite = values
        basis = "window_index_fallback"
    else:
        basis = "recording_time_s"
    lower = min(finite)
    upper = max(finite)
    span = upper - lower
    for index, row in enumerate(rows):
        value = values[index] if values[index] is not None else float(index)
        if span <= 0:
            bin_index = 0
        else:
            bin_index = min(TIME_STRATA - 1, max(0, int((value - lower) / span * TIME_STRATA)))
        row["time_bin_index"] = bin_index
        row["time_stratum"] = f"time_{bin_index:02d}"
        row["time_stratification_basis"] = basis


def assign_cn0_strata(rows: Sequence[dict[str, Any]]) -> tuple[float | None, float | None]:
    values = [row["cn0_value"] for row in rows if row["cn0_value"] is not None]
    p20 = percentile(values, 0.20)
    p80 = percentile(values, 0.80)
    for row in rows:
        value = row["cn0_value"]
        if value is None or p20 is None or p80 is None:
            row["cn0_stratum"] = "cn0_unknown"
        elif value <= p20:
            row["cn0_stratum"] = "cn0_low"
        elif value <= p80:
            row["cn0_stratum"] = "cn0_mid"
        else:
            row["cn0_stratum"] = "cn0_high"
    return p20, p80


def annotate_rows(rows: Sequence[dict[str, Any]], geometry: GeometryResult) -> tuple[float | None, float | None]:
    assign_time_bins(rows)
    p20, p80 = assign_cn0_strata(rows)
    for row in rows:
        joined = geometry.mapping.get(row["window_id"], {})
        row["elevation_group"] = joined.get("elevation_group", "")
        row["elevation_deg"] = joined.get("elevation_deg")
        row["azimuth_deg"] = joined.get("azimuth_deg")
        row["geometry_snr_db_hz"] = joined.get("snr_db_hz")
        row["geometry_source_utc"] = joined.get("geometry_source_utc", "")
        row["geometry_time_delta_s"] = joined.get("geometry_time_delta_s")
        row["geometry_join_status"] = (
            "verified" if joined else geometry.status
        )
        row["selection_reasons"] = []
        row["selection_strata"] = []
        row["selection_phase"] = "not_selected"
        row["selected"] = False
    return p20, p80


def evenly_spaced_ids(ids: Sequence[int], count: int, seed: str, key: str) -> list[int]:
    ordered = sorted(set(ids))
    if len(ordered) <= count:
        return ordered
    offset = stable_int(seed, key) % len(ordered)
    positions: list[int] = []
    used: set[int] = set()
    for index in range(count):
        position = int(((index + 0.5) * len(ordered) / count + offset) % len(ordered))
        if position not in used:
            used.add(position)
            positions.append(position)
    if len(positions) < count:
        for position in sorted(range(len(ordered)), key=lambda item: stable_int(seed, key, item)):
            if position not in used:
                used.add(position)
                positions.append(position)
                if len(positions) == count:
                    break
    return [ordered[position] for position in sorted(positions)]


def add_selection(
    rows_by_id: dict[int, dict[str, Any]],
    selected: set[int],
    ids: Iterable[int],
    reason: str,
    stratum: str,
    phase: str,
    max_count: int | None = None,
) -> int:
    added = 0
    for window_id in ids:
        if window_id not in rows_by_id or window_id in selected:
            if window_id in rows_by_id:
                row = rows_by_id[window_id]
                if reason not in row["selection_reasons"]:
                    row["selection_reasons"].append(reason)
                if stratum and stratum not in row["selection_strata"]:
                    row["selection_strata"].append(stratum)
            continue
        if max_count is not None and added >= max_count:
            break
        selected.add(window_id)
        row = rows_by_id[window_id]
        row["selected"] = True
        row["selection_phase"] = phase
        row["selection_reasons"].append(reason)
        if stratum:
            row["selection_strata"].append(stratum)
        added += 1
    return added


def robust_difference(rows: Sequence[dict[str, Any]], field: str, index: int) -> float:
    current = rows[index].get(field)
    values: list[float] = []
    if current is not None:
        for neighbor in (index - 1, index + 1):
            if 0 <= neighbor < len(rows):
                other = rows[neighbor].get(field)
                if other is not None:
                    values.append(abs(current - other))
    return max(values, default=0.0)


def low_cost_risk_order(rows: Sequence[dict[str, Any]], seed: str) -> list[int]:
    scored: list[tuple[float, int, int]] = []
    for index, row in enumerate(rows):
        score = 0.0
        score += robust_difference(rows, "cn0_value", index)
        score += 0.05 * robust_difference(rows, "speed_value", index)
        score += 0.02 * robust_difference(rows, "doppler_bound_value", index)
        if index in {0, len(rows) - 1}:
            score += 2.0
        if index > 0 and row.get("elevation_group") != rows[index - 1].get("elevation_group"):
            score += 1.0
        tie = stable_int(seed, "risk", row["window_id"])
        scored.append((score, tie, row["window_id"]))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [item[2] for item in scored]


def make_burst_ids(center: int, rows_by_id: dict[int, dict[str, Any]], half_width: int) -> list[int]:
    return [
        window_id
        for window_id in range(center - half_width, center + half_width + 1)
        if window_id in rows_by_id
    ]


def build_sampling_plan(
    task: TaskSpec,
    stage0_rows: Sequence[dict[str, Any]],
    geometry: GeometryResult,
    seed: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [dict(row) for row in stage0_rows]
    annotate_rows(rows, geometry)
    rows_by_id = {row["window_id"]: row for row in rows}
    selected: set[int] = set()
    warnings: list[str] = []
    n0 = len(rows)

    if n0 <= MAX_STAGE1_WINDOWS:
        add_selection(
            rows_by_id,
            selected,
            rows_by_id,
            "full_scan_equivalent",
            "full_scan",
            "full_scan",
        )
        sampling_mode = "full-scan-equivalent"
        initial_count = n0
        extension_count = 0
    else:
        sampling_mode = PROFILE_VERSION
        time_groups: dict[int, list[int]] = {index: [] for index in range(TIME_STRATA)}
        for row in rows:
            time_groups[row["time_bin_index"]].append(row["window_id"])
        for time_bin, ids in time_groups.items():
            chosen = evenly_spaced_ids(ids, TIME_MINIMUM, seed, f"time_min_{time_bin}")
            add_selection(
                rows_by_id,
                selected,
                chosen,
                "time_stratum_minimum",
                f"time_{time_bin:02d}",
                "initial",
            )

        # One deterministic contiguous 11-window burst per time layer.
        for time_bin, ids in time_groups.items():
            if not ids:
                continue
            center = ids[stable_int(seed, "burst_center", time_bin) % len(ids)]
            add_selection(
                rows_by_id,
                selected,
                make_burst_ids(center, rows_by_id, BURST_HALF_WIDTH),
                "deterministic_11_window_burst",
                f"time_{time_bin:02d}_burst",
                "initial",
            )

        if geometry.status == "verified":
            for group in ("Low", "Mid", "High"):
                ids = [row["window_id"] for row in rows if row.get("elevation_group") == group]
                chosen = evenly_spaced_ids(ids, TIME_MINIMUM, seed, f"elevation_{group}")
                add_selection(
                    rows_by_id,
                    selected,
                    chosen,
                    "elevation_stratum_minimum",
                    f"elevation_{group}",
                    "initial",
                )
                if len(ids) < TIME_MINIMUM:
                    warnings.append(f"elevation_{group}_underfilled:{len(ids)}<{TIME_MINIMUM}")
        else:
            warnings.append("elevation strata disabled because geometry window join is not verified")

        for group in ("cn0_low", "cn0_mid", "cn0_high"):
            ids = [row["window_id"] for row in rows if row.get("cn0_stratum") == group]
            chosen = evenly_spaced_ids(ids, TIME_MINIMUM, seed, f"{group}_minimum")
            add_selection(
                rows_by_id,
                selected,
                chosen,
                "cn0_stratum_minimum",
                group,
                "initial",
            )
            if len(ids) < TIME_MINIMUM:
                warnings.append(f"{group}_underfilled:{len(ids)}<{TIME_MINIMUM}")

        initial_budget = min(INITIAL_TARGET, n0, MAX_STAGE1_WINDOWS)
        remaining_initial = max(0, initial_budget - len(selected))
        remaining_ids = [window_id for window_id in rows_by_id if window_id not in selected]
        remaining_ids.sort(key=lambda window_id: stable_int(seed, "initial_fill", window_id))
        add_selection(
            rows_by_id,
            selected,
            remaining_ids,
            "deterministic_seeded_fill",
            "seeded_reserve",
            "initial",
            remaining_initial,
        )
        if len(selected) > initial_budget:
            warnings.append(
                f"mandatory strata exceed initial target: {len(selected)}>{initial_budget}; retained before extension"
            )
        initial_count = len(selected)

        extension_budget = max(0, MAX_STAGE1_WINDOWS - len(selected))
        risk_order = low_cost_risk_order(rows, seed)
        extension_added = 0
        for center in risk_order:
            if extension_added >= extension_budget:
                break
            block = make_burst_ids(center, rows_by_id, BURST_HALF_WIDTH)
            new_ids = [window_id for window_id in block if window_id not in selected]
            if not new_ids or len(new_ids) > extension_budget - extension_added:
                continue
            extension_added += add_selection(
                rows_by_id,
                selected,
                block,
                "low_cost_risk_burst_extension",
                "risk_burst",
                "extension",
            )
        extension_count = extension_added
        if len(selected) < min(MAX_STAGE1_WINDOWS, n0):
            warnings.append(
                f"sampling budget not fully used: selected={len(selected)}, target={min(MAX_STAGE1_WINDOWS, n0)}"
            )

    if len(selected) > min(MAX_STAGE1_WINDOWS, n0):
        raise AssertionError("sampling planner exceeded Stage1 window budget")

    for row in rows:
        if not row["selected"]:
            row["selection_phase"] = "not_selected"
        row["seed"] = seed
        row["sampling_mode"] = sampling_mode
        row["profile_version"] = PROFILE_VERSION
        row["selection_reason"] = ";".join(row["selection_reasons"])
        row["stratum"] = ";".join(row["selection_strata"])
        row["selected_status"] = "selected" if row["selected"] else "not_selected"

    counts_by_reason: dict[str, int] = {}
    for row in rows:
        for reason in row["selection_reasons"]:
            counts_by_reason[reason] = counts_by_reason.get(reason, 0) + 1
    plan = {
        "schema_version": SCHEMA_VERSION,
        "profile_version": PROFILE_VERSION,
        "seed": seed,
        "sampling_mode": sampling_mode,
        "task": {
            "task_id": task.task_id,
            "scene_id": task.scene_id,
            "prn": task.prn,
            "tracking_channel": task.tracking_channel,
            "sampling_rate_hz": task.sampling_rate_hz,
            "task_group": task.task_group,
            "result_relative_path": task.result_relative_path,
        },
        "source": {
            "stage0_window_count": n0,
            "stage0_window_ids_preserved": True,
            "geometry_join_status": geometry.status,
            "geometry_warning": geometry.warning,
            "geometry_source_file": geometry.source_file,
            "geometry_anchor_source": geometry.anchor_source,
            "geometry_coverage_ratio": geometry.coverage_ratio,
            "geometry_p95_delta_seconds": geometry.p95_delta_seconds,
            "geometry_max_delta_seconds": geometry.max_delta_seconds,
        },
        "selection": {
            "selected_window_count": len(selected),
            "not_selected_window_count": n0 - len(selected),
            "initial_selected_count": initial_count,
            "extension_selected_count": extension_count,
            "stage1_reduction": 1.0 - (len(selected) / n0 if n0 else 0.0),
            "initial_target": INITIAL_TARGET,
            "maximum_stage1_windows": MAX_STAGE1_WINDOWS,
            "time_strata": TIME_STRATA,
            "time_minimum_per_stratum": TIME_MINIMUM,
            "burst_width": BURST_WIDTH,
            "burst_half_width": BURST_HALF_WIDTH,
            "stage2_base_candidate_cap": MAX_STAGE2_BASE_CANDIDATES,
            "stage2_neighbor_radius": STAGE2_NEIGHBOR_RADIUS,
            "stage2_candidate_theoretical_cap": MAX_STAGE2_BASE_CANDIDATES
            * (2 * STAGE2_NEIGHBOR_RADIUS + 1),
            "selection_counts_by_reason": counts_by_reason,
        },
        "warnings": list(dict.fromkeys(warnings)),
        "source_hashes": {},
    }
    return plan, rows


def load_gold_centers(result_dir: Path) -> tuple[list[int], list[int]]:
    stage3_path = result_dir / "stage3_reliable_centers.csv"
    stage4_path = result_dir / "stage4_joint_summary.csv"
    reliable: list[int] = []
    confirmed: list[int] = []
    if stage3_path.is_file():
        for row in read_csv_rows(stage3_path):
            center = parse_int(row.get("center_window_id"))
            if center is not None and (
                "reliable_multipath" not in row or truthy(row.get("reliable_multipath"))
            ):
                reliable.append(center)
    if stage4_path.is_file():
        for row in read_csv_rows(stage4_path):
            center = parse_int(row.get("center_window_id"))
            joint_count = parse_int(row.get("joint_multipath_count")) or 0
            if center is not None and truthy(row.get("joint_valid")) and joint_count > 0:
                confirmed.append(center)
    return sorted(set(reliable)), sorted(set(confirmed))


def coverage_for_center(center: int, selected: set[int], universe: set[int]) -> tuple[bool, bool, str]:
    closure = list(range(center - STAGE2_NEIGHBOR_RADIUS, center + STAGE2_NEIGHBOR_RADIUS + 1))
    if center not in universe:
        return False, False, "center_not_in_stage0_universe"
    missing = [window_id for window_id in closure if window_id not in universe]
    if missing:
        return center in selected, False, f"closure_not_in_stage0:{','.join(map(str, missing))}"
    if center not in selected:
        return False, False, "center_not_selected"
    missing_selected = [window_id for window_id in closure if window_id not in selected]
    if missing_selected:
        return True, False, f"closure_not_selected:{','.join(map(str, missing_selected))}"
    return True, True, "covered"


def replay_coverage(
    task: TaskSpec,
    plan: dict[str, Any],
    manifest_rows: Sequence[dict[str, Any]],
    reliable_centers: Sequence[int],
    confirmed_centers: Sequence[int],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    selected = {
        int(row["window_id"])
        for row in manifest_rows
        if row.get("selected_status") == "selected"
    }
    universe = {int(row["window_id"]) for row in manifest_rows}
    event_rows: list[dict[str, Any]] = []
    for center in confirmed_centers:
        center_covered, closure_covered, reason = coverage_for_center(center, selected, universe)
        event_rows.append(
            {
                "task_id": task.task_id,
                "scene_id": task.scene_id,
                "prn": task.prn,
                "seed": plan["seed"],
                "center_window_id": center,
                "center_covered": center_covered,
                "closure_pm2_covered": closure_covered,
                "coverage_reason": reason,
            }
        )
    stage3_rows: list[dict[str, Any]] = []
    for center in reliable_centers:
        center_covered, closure_covered, reason = coverage_for_center(center, selected, universe)
        stage3_rows.append(
            {
                "task_id": task.task_id,
                "scene_id": task.scene_id,
                "prn": task.prn,
                "seed": plan["seed"],
                "center_window_id": center,
                "center_covered": center_covered,
                "closure_pm2_covered": closure_covered,
                "coverage_reason": reason,
            }
        )

    def ratio(rows: Sequence[dict[str, Any]], field: str) -> float | None:
        if not rows:
            return None
        return sum(bool(row[field]) for row in rows) / len(rows)

    reasons = sorted(
        {
            row["coverage_reason"]
            for row in event_rows + stage3_rows
            if row["coverage_reason"] != "covered"
        }
    )
    summary = {
        "task_id": task.task_id,
        "scene_id": task.scene_id,
        "prn": task.prn,
        "tracking_channel": task.tracking_channel,
        "task_group": task.task_group,
        "seed": plan["seed"],
        "sampling_mode": plan["sampling_mode"],
        "geometry_join_status": plan["source"]["geometry_join_status"],
        "stage0_window_count": plan["source"]["stage0_window_count"],
        "stage1_selected_count": plan["selection"]["selected_window_count"],
        "stage1_not_selected_count": plan["selection"]["not_selected_window_count"],
        "stage1_reduction": plan["selection"]["stage1_reduction"],
        "confirmed_event_count_gold": len(confirmed_centers),
        "event_center_recall": ratio(event_rows, "center_covered"),
        "event_closure_pm2_recall": ratio(event_rows, "closure_pm2_covered"),
        "stage3_reliable_center_count_gold": len(reliable_centers),
        "stage3_center_recall": ratio(stage3_rows, "center_covered"),
        "stage3_closure_pm2_recall": ratio(stage3_rows, "closure_pm2_covered"),
        "uncovered_reason_count": len(reasons),
        "uncovered_reasons": ";".join(reasons),
        "coverage_status": "covered" if not reasons else "uncovered",
    }
    return summary, event_rows, stage3_rows


MANIFEST_FIELDS = [
    "task_id",
    "scene_id",
    "prn",
    "tracking_channel",
    "sampling_rate_hz",
    "task_group",
    "profile_version",
    "seed",
    "window_id",
    "recording_time_s",
    "tow_s",
    "cn0_db_hz",
    "vehicle_speed_kmh",
    "relative_doppler_bound_hz",
    "time_stratum",
    "time_stratification_basis",
    "cn0_stratum",
    "elevation_group",
    "elevation_deg",
    "azimuth_deg",
    "geometry_snr_db_hz",
    "geometry_source_utc",
    "geometry_time_delta_s",
    "geometry_join_status",
    "sampling_mode",
    "selected_status",
    "selection_phase",
    "selection_reason",
    "stratum",
]


def manifest_rows_for_csv(task: TaskSpec, rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.update(
            {
                "task_id": task.task_id,
                "scene_id": task.scene_id,
                "prn": task.prn,
                "tracking_channel": task.tracking_channel,
                "sampling_rate_hz": task.sampling_rate_hz,
                "task_group": task.task_group,
            }
        )
        output.append(item)
    return output


def task_result_dir(project_root: Path, task: TaskSpec) -> Path:
    return project_root / "scenes" / task.scene_id / task.result_relative_path


def task_slug(task: TaskSpec) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", task.task_id)


def build_one_task(
    project_root: Path,
    output_root: Path,
    task: TaskSpec,
    seeds: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    result_dir = task_result_dir(project_root, task)
    stage0_path = result_dir / "stage0_valid_40ms_windows.csv"
    if not stage0_path.is_file():
        raise FileNotFoundError(f"Stage0 catalog missing: {stage0_path}")
    stage0_rows = load_stage0(stage0_path)
    geometry = load_geometry_result(project_root / "scenes" / task.scene_id, task.prn, stage0_rows)
    reliable_centers, confirmed_centers = load_gold_centers(result_dir)
    source_files = [stage0_path]
    if geometry.source_file:
        source_files.append(Path(geometry.source_file))
    for filename in ("stage3_reliable_centers.csv", "stage4_joint_summary.csv", "stage4_joint_paths.csv"):
        path = result_dir / filename
        if path.is_file():
            source_files.append(path)

    summaries: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    stage3_replay: list[dict[str, Any]] = []
    for seed in seeds:
        plan, rows = build_sampling_plan(task, stage0_rows, geometry, seed)
        plan["source_hashes"] = {
            str(path): sha256_file(path) for path in source_files if path.is_file()
        }
        plan["gold_read_only"] = {
            "stage3_reliable_centers": list(reliable_centers),
            "stage4_confirmed_event_centers": list(confirmed_centers),
            "selection_does_not_use_gold_labels": True,
        }
        summary, event_rows, stage3_rows = replay_coverage(
            task, plan, rows, reliable_centers, confirmed_centers
        )
        plan["coverage_replay"] = summary
        plan["coverage_replay"]["uncovered_event_centers"] = [
            row["center_window_id"]
            for row in event_rows
            if not row["closure_pm2_covered"]
        ]
        plan["coverage_replay"]["uncovered_stage3_centers"] = [
            row["center_window_id"]
            for row in stage3_rows
            if not row["closure_pm2_covered"]
        ]

        seed_dir = output_root / task_slug(task) / seed
        if seed_dir.exists():
            raise FileExistsError(f"Refusing to overwrite sampling output: {seed_dir}")
        seed_dir.mkdir(parents=True, exist_ok=False)
        (seed_dir / "sampling_plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        manifest = manifest_rows_for_csv(task, rows)
        write_csv(seed_dir / "sampling_window_manifest.csv", manifest, MANIFEST_FIELDS)
        summaries.append(summary)
        events.extend(event_rows)
        stage3_replay.extend(stage3_rows)
    return summaries, events, stage3_replay


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("dataset_generation_logs/sampling_validation/batch_sampled_v1_offline_coverage"),
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        default=[f"seed_{index:02d}" for index in range(10)],
        help="Deterministic seed labels; defaults to seed_00 through seed_09.",
    )
    parser.add_argument(
        "--task-id",
        action="append",
        dest="task_ids",
        help="Restrict the run to one or more GOLD_TASKS task_id values.",
    )
    return parser.parse_args(argv)


def run(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    output_root = args.output_root
    if not output_root.is_absolute():
        output_root = project_root / output_root
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"Output root is not empty; refusing overwrite: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    selected_tasks = list(GOLD_TASKS)
    if args.task_ids:
        wanted = set(args.task_ids)
        selected_tasks = [task for task in selected_tasks if task.task_id in wanted]
        missing = wanted - {task.task_id for task in selected_tasks}
        if missing:
            raise ValueError(f"Unknown task_id(s): {sorted(missing)}")
    if not selected_tasks:
        raise ValueError("No tasks selected")
    if not args.seeds:
        raise ValueError("At least one deterministic seed is required")
    if len(set(args.seeds)) != len(args.seeds):
        raise ValueError("Seed labels must be unique")

    summaries: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    stage3_rows: list[dict[str, Any]] = []
    for task in selected_tasks:
        task_summaries, task_events, task_stage3 = build_one_task(
            project_root, output_root, task, args.seeds
        )
        summaries.extend(task_summaries)
        event_rows.extend(task_events)
        stage3_rows.extend(task_stage3)

    summary_fields = [
        "task_id",
        "scene_id",
        "prn",
        "tracking_channel",
        "task_group",
        "seed",
        "sampling_mode",
        "geometry_join_status",
        "stage0_window_count",
        "stage1_selected_count",
        "stage1_not_selected_count",
        "stage1_reduction",
        "confirmed_event_count_gold",
        "event_center_recall",
        "event_closure_pm2_recall",
        "stage3_reliable_center_count_gold",
        "stage3_center_recall",
        "stage3_closure_pm2_recall",
        "uncovered_reason_count",
        "uncovered_reasons",
        "coverage_status",
    ]
    write_csv(output_root / "coverage_replay.csv", summaries, summary_fields)
    write_csv(
        output_root / "coverage_replay_events.csv",
        event_rows,
        [
            "task_id",
            "scene_id",
            "prn",
            "seed",
            "center_window_id",
            "center_covered",
            "closure_pm2_covered",
            "coverage_reason",
        ],
    )
    write_csv(
        output_root / "coverage_replay_stage3_centers.csv",
        stage3_rows,
        [
            "task_id",
            "scene_id",
            "prn",
            "seed",
            "center_window_id",
            "center_covered",
            "closure_pm2_covered",
            "coverage_reason",
        ],
    )
    root_manifest = {
        "schema_version": SCHEMA_VERSION,
        "profile_version": PROFILE_VERSION,
        "project_root": str(project_root),
        "output_root": str(output_root),
        "task_count": len(selected_tasks),
        "seed_labels": list(args.seeds),
        "task_ids": [task.task_id for task in selected_tasks],
        "matlab_invoked": False,
        "sage_invoked": False,
        "raw_iq_opened": False,
        "gold_labels_used_for_selection": False,
        "output_is_outside_sage_results": True,
    }
    (output_root / "sampling_validation_manifest.json").write_text(
        json.dumps(root_manifest, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(f"sampling_validation_output={output_root}")
    print(f"tasks={len(selected_tasks)} seeds={len(args.seeds)} plans={len(selected_tasks) * len(args.seeds)}")
    print(f"coverage_replay={output_root / 'coverage_replay.csv'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:  # pragma: no cover - CLI diagnostics
        raise SystemExit(f"ERROR: {exc}")
