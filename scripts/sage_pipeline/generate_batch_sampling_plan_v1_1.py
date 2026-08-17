#!/usr/bin/env python3
"""Offline v1.1 continuous-block sampling and full-scan Stage1 replay.

The script uses existing full-scan Stage1 CSV rows only as a surrogate for
what an actual Stage1 scan would expose.  Candidate seeds are selected from
the initial exposed subset, never from hidden rows.  No raw IQ, MATLAB, SAGE,
correlation, or fitting operation is performed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from generate_batch_sampling_plan import (
    GeometryResult,
    GOLD_TASKS,
    MAX_GEOMETRY_DELTA_SECONDS,
    MAX_STAGE1_WINDOWS,
    MIN_GEOMETRY_COVERAGE,
    PROFILE_VERSION,
    STAGE2_NEIGHBOR_RADIUS,
    TaskSpec,
    annotate_rows,
    coverage_for_center,
    find_geometry_file,
    find_nmea_anchor,
    load_geometry_result,
    load_gold_centers,
    load_stage0,
    parse_utc,
    parse_float,
    parse_int,
    percentile,
    read_csv_rows,
    sha256_file,
    stable_int,
    write_csv,
)


V11_PROFILE_VERSION = "batch-sampled-v1.1"
TIME_STRATA = 24
INITIAL_TARGET = 800
BLOCK_LENGTHS = (11, 21, 31, 41)
TOTAL_BUDGETS = (
    800,
    1000,
    1200,
    1400,
    1600,
    1800,
    2000,
    2200,
    2400,
    2800,
    3200,
    4000,
    4800,
)
MAX_BASE_CANDIDATES = 24
MIN_BASE_CANDIDATES = 8
ADAPTIVE_PM5_BLOCK_LENGTH = 11
GPS_WEEK_SECONDS = 604800.0
GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)


@dataclass(frozen=True)
class BlockConfig:
    name: str
    block_length: int
    total_budget: int
    initial_budget: int


@dataclass(frozen=True)
class TaskInputs:
    """Read-only inputs cached once per task for the replay sweep."""

    stage0_rows: tuple[dict[str, Any], ...]
    stage1_rows: tuple[dict[str, Any], ...]
    geometry: Any
    legacy_geometry: Any
    reliable_centers: tuple[int, ...]
    confirmed_centers: tuple[int, ...]
    source_hashes: dict[str, str]


def config_for(block_length: int, total_budget: int) -> BlockConfig:
    if block_length % 2 == 0 or block_length < 3:
        raise ValueError("block_length must be an odd integer >= 3")
    initial_budget = min(total_budget, max(INITIAL_TARGET, TIME_STRATA * block_length))
    return BlockConfig(
        f"blocks{block_length}_budget{total_budget}",
        block_length,
        total_budget,
        initial_budget,
    )


def normalized_stage1_rows(path: Path) -> list[dict[str, Any]]:
    rows = read_csv_rows(path)
    required = {
        "window_id",
        "scan_valid",
        "residual_peak1_power_db",
        "residual_peak2_power_db",
        "has_two_strong_residuals",
    }
    if rows:
        missing = sorted(required - set(rows[0]))
        if missing:
            raise ValueError(f"Stage1 CSV missing columns {missing}: {path}")
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        window_id = parse_int(row.get("window_id"))
        if window_id is None or window_id in seen:
            raise ValueError(f"Invalid or duplicate Stage1 window_id in {path}")
        seen.add(window_id)
        item = dict(row)
        item["window_id"] = window_id
        item["scan_valid_value"] = parse_int(row.get("scan_valid"))
        item["peak1_power_value"] = parse_float(row.get("residual_peak1_power_db"))
        item["peak2_power_value"] = parse_float(row.get("residual_peak2_power_db"))
        item["two_peak_value"] = parse_int(row.get("has_two_strong_residuals")) or 0
        normalized.append(item)
    return normalized


def load_geometry_result_tow(
    scene_dir: Path,
    prn: str,
    stage0_rows: Sequence[dict[str, Any]],
) -> GeometryResult:
    """Join geometry by Stage0 TOW, with the old recording-time join as a control.

    The first v1 planner assumed ``trajectory_first_RMC + recording_time_s``.
    That is only valid when the trajectory file begins at raw-capture time zero.
    The Stage0 catalog also carries GNSS TOW, so v1.1 tests a second, PRN-specific
    join: convert the trajectory RMC date/time to a GPS-week phase and map each
    Stage0 TOW to the nearest geometry timestamp.  The same conservative 90%
    coverage / 5-second p95 acceptance gates are retained.  No satellite summary
    mean is ever used for a window.
    """

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
            f"{anchor_source}+stage0_tow",
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
            f"{anchor_source}+stage0_tow",
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
                "elevation_group": str(row.get("elevation_group", "")).strip(),
                "nmea_file": str(row.get("nmea_file", "")).strip(),
            }
        )
    if not geometry_rows:
        return GeometryResult(
            "warning_fallback",
            f"no valid geometry rows for {prn}",
            str(source_file),
            f"{anchor_source}+stage0_tow",
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

    anchor_tow = (anchor - GPS_EPOCH).total_seconds() % GPS_WEEK_SECONDS

    def match_with_gps_utc_offset(offset_seconds: float) -> tuple[
        list[float], dict[int, dict[str, Any]]
    ]:
        deltas: list[float] = []
        provisional: dict[int, dict[str, Any]] = {}
        for row in stage0_rows:
            tow = row.get("tow_s_value")
            if tow is None:
                continue
            # Choose the signed difference closest to the trajectory RMC anchor;
            # this handles a GPS-week boundary without using hidden event labels.
            delta_from_anchor = (tow - anchor_tow + GPS_WEEK_SECONDS / 2.0) % GPS_WEEK_SECONDS
            delta_from_anchor -= GPS_WEEK_SECONDS / 2.0
            # Stage0 TOW is GPS time while RMC/geometry UTC is UTC.  The offset
            # is calibrated from the time series below; it is not inferred from
            # any SAGE event or Stage3/Stage4 label.
            target = anchor + timedelta(seconds=delta_from_anchor - offset_seconds)
            position = bisect_left(times, target)
            candidates: list[int] = []
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
        return deltas, provisional

    # Calibrate only against the independent time-series overlap.  The search
    # range covers the known GPS-UTC offset while remaining deterministic and
    # deliberately excludes SAGE-derived labels.  This is an alignment
    # diagnostic, not an event-targeted tuning step.
    calibration: list[tuple[tuple[float, float, float, float], float, list[float], dict[int, dict[str, Any]]]] = []
    for offset_seconds in range(0, 31):
        candidate_deltas, candidate_mapping = match_with_gps_utc_offset(float(offset_seconds))
        candidate_coverage = (
            sum(delta <= MAX_GEOMETRY_DELTA_SECONDS for delta in candidate_deltas) / len(stage0_rows)
            if stage0_rows
            else 0.0
        )
        candidate_p95 = percentile(candidate_deltas, 0.95)
        candidate_max = max(candidate_deltas) if candidate_deltas else math.inf
        calibration.append(
            (
                (
                    -candidate_coverage,
                    candidate_p95 if candidate_p95 is not None else math.inf,
                    candidate_max,
                    float(offset_seconds),
                ),
                float(offset_seconds),
                candidate_deltas,
                candidate_mapping,
            )
        )
    _, selected_offset, deltas, provisional = min(calibration, key=lambda item: item[0])

    coverage_ratio = len(provisional) / len(stage0_rows) if stage0_rows else 0.0
    p95_delta = percentile(deltas, 0.95)
    max_delta = max(deltas) if deltas else None
    if coverage_ratio < MIN_GEOMETRY_COVERAGE:
        warnings.append(
            f"TOW window-level geometry coverage {coverage_ratio:.3f} is below {MIN_GEOMETRY_COVERAGE:.2f}"
        )
    if p95_delta is None or p95_delta > MAX_GEOMETRY_DELTA_SECONDS:
        warnings.append(
            f"TOW geometry nearest-time p95 is {p95_delta!r}s, tolerance is {MAX_GEOMETRY_DELTA_SECONDS:.1f}s"
        )
    if not matching_nmea:
        warnings.append("TOW geometry alignment is not trusted because source NMEA identity is unverified")

    reliable = (
        coverage_ratio >= MIN_GEOMETRY_COVERAGE
        and p95_delta is not None
        and p95_delta <= MAX_GEOMETRY_DELTA_SECONDS
        and matching_nmea
    )
    if reliable:
        status = "verified"
        mapping = provisional
    else:
        status = "warning_fallback"
        mapping = {}
        warnings.append("elevation sampling disabled; time plus C/N0 remains the selection basis")
    result = GeometryResult(
        status,
        "; ".join(dict.fromkeys(warnings)),
        str(source_file),
        f"{anchor_source}+stage0_tow+estimated_gps_utc_offset={selected_offset:.0f}s",
        coverage_ratio,
        p95_delta,
        max_delta,
        mapping,
    )
    setattr(result, "gps_utc_offset_seconds", selected_offset)
    setattr(result, "calibration_candidate_count", len(calibration))
    return result


def stage1_candidate_seeds(
    stage1_rows: Sequence[dict[str, Any]],
    exposed_window_ids: set[int],
) -> list[int]:
    """Reproduce chooseStage2Candidates base ordering on exposed rows only."""

    visible = [row for row in stage1_rows if row["window_id"] in exposed_window_ids]
    valid = [
        row
        for row in visible
        if row.get("scan_valid_value") == 1 and row.get("peak1_power_value") is not None
    ]
    two_peak = [row for row in valid if row.get("two_peak_value") == 1]
    two_peak.sort(
        key=lambda row: (
            -(row.get("peak2_power_value") if row.get("peak2_power_value") is not None else -math.inf),
            row["window_id"],
        )
    )
    one_peak = sorted(
        valid,
        key=lambda row: (
            -row["peak1_power_value"],
            row["window_id"],
        ),
    )
    ordered: list[int] = []
    seen: set[int] = set()
    for row in two_peak + one_peak:
        window_id = row["window_id"]
        if window_id not in seen:
            seen.add(window_id)
            ordered.append(window_id)
    base = ordered[:MAX_BASE_CANDIDATES]
    if len(base) < MIN_BASE_CANDIDATES:
        for row in one_peak[:MIN_BASE_CANDIDATES]:
            if row["window_id"] not in seen:
                base.append(row["window_id"])
                seen.add(row["window_id"])
    return base[:MAX_BASE_CANDIDATES]


def block_ids(center: int, block_length: int, universe: set[int]) -> list[int]:
    half = block_length // 2
    return [
        window_id
        for window_id in range(center - half, center + half + 1)
        if window_id in universe
    ]


def stratum_block_centers(
    ids: Sequence[int], count: int, block_length: int, seed: str, config_name: str, time_bin: int
) -> list[int]:
    ordered = sorted(ids)
    if not ordered or count <= 0:
        return []
    centers: list[int] = []
    for slot in range(count):
        fraction = (slot + 1) / (count + 1)
        position = int(round(fraction * (len(ordered) - 1)))
        jitter_limit = max(0, min(block_length // 2, len(ordered) // max(2, count * 4)))
        if jitter_limit:
            jitter_span = 2 * jitter_limit + 1
            jitter = stable_int(seed, config_name, "block_jitter", time_bin, slot) % jitter_span
            position += int(jitter) - jitter_limit
        position = max(0, min(len(ordered) - 1, position))
        centers.append(ordered[position])
    return centers


def initial_continuous_blocks(
    rows: Sequence[dict[str, Any]], config: BlockConfig, seed: str
) -> tuple[set[int], dict[int, list[str]], list[str]]:
    """Select contiguous blocks distributed across the 24 time strata."""

    universe = {row["window_id"] for row in rows}
    groups: dict[int, list[int]] = {index: [] for index in range(TIME_STRATA)}
    for row in rows:
        groups[row["time_bin_index"]].append(row["window_id"])

    possible_blocks = config.initial_budget // config.block_length
    warnings: list[str] = []
    if possible_blocks < TIME_STRATA and len(rows) > MAX_STAGE1_WINDOWS:
        warnings.append(
            f"only {possible_blocks} initial blocks for {TIME_STRATA} time strata; some strata have no full block"
        )
    # Distribute whole blocks as evenly as possible.  The rotation depends
    # only on seed/config/time-bin, not on any gold event labels.
    base_count = possible_blocks // TIME_STRATA
    remainder = possible_blocks % TIME_STRATA
    allocation_order = sorted(
        range(TIME_STRATA),
        key=lambda time_bin: stable_int(seed, config.name, "allocation", time_bin),
    )
    counts = {time_bin: base_count for time_bin in range(TIME_STRATA)}
    for time_bin in allocation_order[:remainder]:
        counts[time_bin] += 1

    selected: set[int] = set()
    reasons: dict[int, list[str]] = {}
    for time_bin in range(TIME_STRATA):
        ids = groups[time_bin]
        centers = stratum_block_centers(
            ids,
            counts[time_bin],
            config.block_length,
            seed,
            config.name,
            time_bin,
        )
        for block_number, center in enumerate(centers):
            reason = f"initial_continuous_block_L{config.block_length}_T{time_bin:02d}_B{block_number:02d}"
            for window_id in block_ids(center, config.block_length, universe):
                selected.add(window_id)
                reasons.setdefault(window_id, []).append(reason)
    return selected, reasons, warnings


def add_adaptive_blocks(
    initial_selected: set[int],
    base_seeds: Sequence[int],
    universe: set[int],
    config: BlockConfig,
) -> tuple[set[int], dict[int, list[str]], list[str], int, int]:
    """Add seed +/-2 and then seed +/-5 without observing hidden Stage1 rows."""

    selected = set(initial_selected)
    reasons: dict[int, list[str]] = {}
    warnings: list[str] = []
    pm2_added = 0
    pm5_added = 0
    # The 1200 profile is the production gate.  Larger budgets are retained
    # only for an offline minimum-budget diagnostic; they must not be silently
    # clipped to 1200 or the diagnostic would be unable to distinguish a
    # failed 1200-window design from a higher-budget design.
    remaining = max(0, config.total_budget - len(selected))

    for seed_window in base_seeds:
        block = block_ids(seed_window, 2 * STAGE2_NEIGHBOR_RADIUS + 1, universe)
        new_ids = [window_id for window_id in block if window_id not in selected]
        if len(new_ids) > remaining:
            warnings.append(f"pm2_budget_exhausted_at_seed:{seed_window}")
            continue
        for window_id in new_ids:
            selected.add(window_id)
            reasons.setdefault(window_id, []).append(f"adaptive_seed_{seed_window}_pm2")
        pm2_added += len(new_ids)
        remaining -= len(new_ids)

    for seed_window in base_seeds:
        # The adaptive extension is deliberately a fixed seed +/-5 burst.
        # The initial block length (11/21/31/41) is not reused here: doing so
        # would turn a 21-window profile into an undocumented +/-10 guard.
        block = block_ids(seed_window, ADAPTIVE_PM5_BLOCK_LENGTH, universe)
        new_ids = [window_id for window_id in block if window_id not in selected]
        if len(new_ids) > remaining:
            continue
        for window_id in new_ids:
            selected.add(window_id)
            reasons.setdefault(window_id, []).append(f"adaptive_seed_{seed_window}_pm5")
        pm5_added += len(new_ids)
        remaining -= len(new_ids)

    if remaining and base_seeds:
        warnings.append(f"adaptive_budget_unused={remaining}")
    return selected, reasons, warnings, pm2_added, pm5_added


def apply_selection_annotations(
    rows: Sequence[dict[str, Any]],
    initial_selected: set[int],
    final_selected: set[int],
    initial_reasons: dict[int, list[str]],
    adaptive_reasons: dict[int, list[str]],
    seed: str,
    config: BlockConfig,
    sampling_mode: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        window_id = row["window_id"]
        reasons = initial_reasons.get(window_id, []) + adaptive_reasons.get(window_id, [])
        if window_id not in final_selected:
            status = "not_selected"
            phase = "not_selected"
        elif window_id in initial_selected:
            status = "selected"
            phase = "initial"
        else:
            status = "selected"
            phase = "adaptive"
        row.update(
            {
                "seed": seed,
                "profile_version": V11_PROFILE_VERSION,
                "block_length": config.block_length,
                "total_budget": config.total_budget,
                "initial_budget": config.initial_budget,
                "sampling_mode": sampling_mode,
                "selected_status": status,
                "selection_phase": phase,
                "selection_reason": ";".join(reasons),
                "stratum": row.get("time_stratum", ""),
            }
        )
        output.append(row)
    return output


def replay_for_centers(
    centers: Sequence[int], initial_selected: set[int], final_selected: set[int], universe: set[int]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    details: list[dict[str, Any]] = []
    for center in centers:
        initial_center, initial_closure, initial_reason = coverage_for_center(
            center, initial_selected, universe
        )
        final_center, final_closure, final_reason = coverage_for_center(
            center, final_selected, universe
        )
        details.append(
            {
                "center_window_id": center,
                "initial_center_covered": initial_center,
                "initial_closure_pm2_covered": initial_closure,
                "initial_coverage_reason": initial_reason,
                "adaptive_center_covered": final_center,
                "adaptive_closure_pm2_covered": final_closure,
                "adaptive_coverage_reason": final_reason,
            }
        )

    def rate(field: str) -> float | None:
        if not details:
            return None
        return sum(bool(row[field]) for row in details) / len(details)

    summary = {
        "count": len(details),
        "initial_center_recall": rate("initial_center_covered"),
        "adaptive_center_recall": rate("adaptive_center_covered"),
        "initial_closure_pm2_recall": rate("initial_closure_pm2_covered"),
        "adaptive_closure_pm2_recall": rate("adaptive_closure_pm2_covered"),
    }
    return summary, details


def build_plan(
    task: TaskSpec,
    stage0_rows: Sequence[dict[str, Any]],
    stage1_rows: Sequence[dict[str, Any]],
    geometry: Any,
    reliable_centers: Sequence[int],
    confirmed_centers: Sequence[int],
    config: BlockConfig,
    seed: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [dict(row) for row in stage0_rows]
    annotate_rows(rows, geometry)
    universe = {row["window_id"] for row in rows}
    if len(stage1_rows) != len(rows):
        raise ValueError(
            f"Stage0/Stage1 row count mismatch for {task.task_id}: {len(rows)} vs {len(stage1_rows)}"
        )
    if not universe == {row["window_id"] for row in stage1_rows}:
        raise ValueError(f"Stage0/Stage1 window ID mismatch for {task.task_id}")

    if len(rows) <= MAX_STAGE1_WINDOWS:
        initial_selected = set(universe)
        initial_reasons = {window_id: ["full_scan_equivalent"] for window_id in universe}
        base_seeds = stage1_candidate_seeds(stage1_rows, initial_selected)
        final_selected = set(universe)
        adaptive_reasons: dict[int, list[str]] = {}
        adaptive_warnings: list[str] = []
        pm2_added = 0
        pm5_added = 0
        sampling_mode = "full-scan-equivalent"
    else:
        initial_selected, initial_reasons, initial_warnings = initial_continuous_blocks(
            rows, config, seed
        )
        base_seeds = stage1_candidate_seeds(stage1_rows, initial_selected)
        final_selected, adaptive_reasons, adaptive_warnings, pm2_added, pm5_added = add_adaptive_blocks(
            initial_selected, base_seeds, universe, config
        )
        adaptive_warnings = initial_warnings + adaptive_warnings
        sampling_mode = V11_PROFILE_VERSION
    final_rows = apply_selection_annotations(
        rows,
        initial_selected,
        final_selected,
        initial_reasons,
        adaptive_reasons,
        seed,
        config,
        sampling_mode,
    )
    event_summary, event_details = replay_for_centers(
        confirmed_centers, initial_selected, final_selected, universe
    )
    stage3_summary, stage3_details = replay_for_centers(
        reliable_centers, initial_selected, final_selected, universe
    )
    plan = {
        "schema_version": "sampling-manifest-v1.1",
        "profile_version": V11_PROFILE_VERSION,
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
        "strategy": {
            "block_length": config.block_length,
            "total_budget": config.total_budget,
            "initial_budget": config.initial_budget,
            "time_strata": TIME_STRATA,
            "initial_selection_is_continuous_blocks": True,
            "candidate_rule": "Pipeline V3 chooseStage2Candidates ordering on exposed Stage1 rows only",
            "adaptive_order": ["seed_pm2", "seed_pm5_if_budget"],
            "hidden_stage1_rows_used_for_seed_selection": False,
        },
        "source": {
            "stage0_window_count": len(rows),
            "stage1_surrogate_row_count": len(stage1_rows),
            "stage0_window_ids_preserved": True,
            "stage1_source_file": "stage1_nav_fast_scan.csv",
            "geometry_join_status": geometry.status,
            "geometry_warning": geometry.warning,
            "geometry_source_file": geometry.source_file,
            "geometry_coverage_ratio": geometry.coverage_ratio,
            "geometry_p95_delta_seconds": geometry.p95_delta_seconds,
        },
        "selection": {
            "initial_stage1_count": len(initial_selected),
            "adaptive_stage1_count": len(final_selected),
            "adaptive_added_count": len(final_selected - initial_selected),
            "stage1_reduction": 1.0 - len(final_selected) / len(rows) if rows else 0.0,
            "initial_base_seed_count": len(base_seeds),
            "initial_base_seed_window_ids": base_seeds,
            "adaptive_pm2_added_count": pm2_added,
            "adaptive_pm5_added_count": pm5_added,
            "adaptive_budget_remaining": max(0, config.total_budget - len(final_selected)),
            "stage1_budget_respected": len(final_selected) <= config.total_budget,
        },
        "gold_read_only": {
            "stage3_reliable_centers": list(reliable_centers),
            "stage4_confirmed_event_centers": list(confirmed_centers),
            "gold_labels_used_for_selection": False,
        },
        "coverage_replay": {
            "confirmed_events": event_summary,
            "stage3_reliable_centers": stage3_summary,
        },
        "warnings": adaptive_warnings if len(rows) > MAX_STAGE1_WINDOWS else [],
    }
    return plan, final_rows, event_details, stage3_details


MANIFEST_FIELDS = [
    "task_id",
    "scene_id",
    "prn",
    "tracking_channel",
    "sampling_rate_hz",
    "task_group",
    "profile_version",
    "seed",
    "block_length",
    "total_budget",
    "initial_budget",
    "window_id",
    "recording_time_s",
    "tow_s",
    "cn0_db_hz",
    "vehicle_speed_kmh",
    "relative_doppler_bound_hz",
    "time_stratum",
    "cn0_stratum",
    "elevation_group",
    "elevation_deg",
    "geometry_join_status",
    "sampling_mode",
    "selected_status",
    "selection_phase",
    "selection_reason",
    "stratum",
]


def manifest_rows(task: TaskSpec, rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
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


def load_task_inputs(project_root: Path, task: TaskSpec) -> TaskInputs:
    """Load and validate the immutable full-scan surrogate files once."""

    result_dir = task_result_dir(project_root, task)
    stage0_path = result_dir / "stage0_valid_40ms_windows.csv"
    stage1_path = result_dir / "stage1_nav_fast_scan.csv"
    stage3_path = result_dir / "stage3_reliable_centers.csv"
    stage4_path = result_dir / "stage4_joint_summary.csv"
    if not stage0_path.is_file():
        raise FileNotFoundError(f"Stage0 catalog missing: {stage0_path}")
    if not stage1_path.is_file():
        raise FileNotFoundError(f"full-scan Stage1 surrogate missing: {stage1_path}")
    stage0_rows = tuple(load_stage0(stage0_path))
    stage1_rows = tuple(normalized_stage1_rows(stage1_path))
    legacy_geometry = load_geometry_result(
        project_root / "scenes" / task.scene_id,
        task.prn,
        stage0_rows,
    )
    geometry = load_geometry_result_tow(
        project_root / "scenes" / task.scene_id,
        task.prn,
        stage0_rows,
    )
    reliable_centers, confirmed_centers = load_gold_centers(result_dir)
    source_hashes = {
        str(path): sha256_file(path)
        for path in (stage0_path, stage1_path, stage3_path, stage4_path)
        if path.is_file()
    }
    return TaskInputs(
        stage0_rows=stage0_rows,
        stage1_rows=stage1_rows,
        geometry=geometry,
        legacy_geometry=legacy_geometry,
        reliable_centers=tuple(reliable_centers),
        confirmed_centers=tuple(confirmed_centers),
        source_hashes=source_hashes,
    )


def evaluate_task_config(
    project_root: Path,
    task: TaskSpec,
    config: BlockConfig,
    seed: str,
    output_dir: Path | None,
    inputs: TaskInputs | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if inputs is None:
        inputs = load_task_inputs(project_root, task)
    stage0_rows = inputs.stage0_rows
    stage1_rows = inputs.stage1_rows
    geometry = inputs.geometry
    reliable_centers = inputs.reliable_centers
    confirmed_centers = inputs.confirmed_centers
    plan, final_rows, event_details, stage3_details = build_plan(
        task,
        stage0_rows,
        stage1_rows,
        geometry,
        reliable_centers,
        confirmed_centers,
        config,
        seed,
    )
    plan["source"].update(
        {
            "geometry_alignment_method": "stage0_tow_relative_to_trajectory_RMC",
            "estimated_gps_utc_offset_seconds": getattr(inputs.geometry, "gps_utc_offset_seconds", None),
            "geometry_calibration_candidate_count": getattr(inputs.geometry, "calibration_candidate_count", None),
            "legacy_recording_time_geometry_join_status": inputs.legacy_geometry.status,
            "legacy_recording_time_geometry_coverage_ratio": inputs.legacy_geometry.coverage_ratio,
            "legacy_recording_time_geometry_p95_delta_seconds": inputs.legacy_geometry.p95_delta_seconds,
            "legacy_recording_time_geometry_warning": inputs.legacy_geometry.warning,
        }
    )
    plan["source_hashes"] = dict(inputs.source_hashes)
    summary = {
        "task_id": task.task_id,
        "scene_id": task.scene_id,
        "prn": task.prn,
        "tracking_channel": task.tracking_channel,
        "task_group": task.task_group,
        "seed": seed,
        "profile_version": V11_PROFILE_VERSION,
        "config_name": config.name,
        "block_length": config.block_length,
        "total_budget": config.total_budget,
        "initial_budget": config.initial_budget,
        "sampling_mode": plan["sampling_mode"],
        "geometry_join_status": geometry.status,
        "geometry_alignment_method": "stage0_tow_relative_to_trajectory_RMC",
        "estimated_gps_utc_offset_seconds": getattr(geometry, "gps_utc_offset_seconds", None),
        "geometry_calibration_candidate_count": getattr(geometry, "calibration_candidate_count", None),
        "legacy_geometry_join_status": inputs.legacy_geometry.status,
        "legacy_geometry_coverage_ratio": inputs.legacy_geometry.coverage_ratio,
        "legacy_geometry_p95_delta_seconds": inputs.legacy_geometry.p95_delta_seconds,
        "stage0_window_count": len(stage0_rows),
        "initial_stage1_count": plan["selection"]["initial_stage1_count"],
        "adaptive_stage1_count": plan["selection"]["adaptive_stage1_count"],
        "stage1_reduction": plan["selection"]["stage1_reduction"],
        "initial_base_seed_count": plan["selection"]["initial_base_seed_count"],
        "adaptive_pm2_added_count": plan["selection"]["adaptive_pm2_added_count"],
        "adaptive_pm5_added_count": plan["selection"]["adaptive_pm5_added_count"],
        "confirmed_event_count_gold": len(confirmed_centers),
        "initial_event_center_recall": plan["coverage_replay"]["confirmed_events"]["initial_center_recall"],
        "adaptive_event_center_recall": plan["coverage_replay"]["confirmed_events"]["adaptive_center_recall"],
        "initial_event_closure_pm2_recall": plan["coverage_replay"]["confirmed_events"]["initial_closure_pm2_recall"],
        "adaptive_event_closure_pm2_recall": plan["coverage_replay"]["confirmed_events"]["adaptive_closure_pm2_recall"],
        "stage3_reliable_center_count_gold": len(reliable_centers),
        "initial_stage3_closure_pm2_recall": plan["coverage_replay"]["stage3_reliable_centers"]["initial_closure_pm2_recall"],
        "adaptive_stage3_closure_pm2_recall": plan["coverage_replay"]["stage3_reliable_centers"]["adaptive_closure_pm2_recall"],
        "budget_respected": plan["selection"]["stage1_budget_respected"],
        "warnings": ";".join(plan["warnings"]),
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=False)
        (output_dir / "sampling_plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        write_csv(output_dir / "sampling_window_manifest.csv", manifest_rows(task, final_rows), MANIFEST_FIELDS)
    return summary, event_details, stage3_details


def write_summary_csvs(output_root: Path, summaries: list[dict[str, Any]], event_rows: list[dict[str, Any]], stage3_rows: list[dict[str, Any]]) -> None:
    summary_fields = [
        "task_id", "scene_id", "prn", "tracking_channel", "task_group", "seed",
        "profile_version", "config_name", "block_length", "total_budget", "initial_budget",
        "sampling_mode", "geometry_join_status", "geometry_alignment_method",
        "estimated_gps_utc_offset_seconds", "geometry_calibration_candidate_count",
        "legacy_geometry_join_status", "legacy_geometry_coverage_ratio",
        "legacy_geometry_p95_delta_seconds", "stage0_window_count", "initial_stage1_count",
        "adaptive_stage1_count", "stage1_reduction", "initial_base_seed_count",
        "adaptive_pm2_added_count", "adaptive_pm5_added_count", "confirmed_event_count_gold",
        "initial_event_center_recall", "adaptive_event_center_recall",
        "initial_event_closure_pm2_recall", "adaptive_event_closure_pm2_recall",
        "stage3_reliable_center_count_gold", "initial_stage3_closure_pm2_recall",
        "adaptive_stage3_closure_pm2_recall", "budget_respected", "warnings",
    ]
    write_csv(output_root / "coverage_replay_v1_1.csv", summaries, summary_fields)
    event_fields = [
        "task_id", "scene_id", "prn", "seed", "config_name", "block_length", "total_budget",
        "center_window_id", "initial_center_covered", "initial_closure_pm2_covered",
        "initial_coverage_reason", "adaptive_center_covered", "adaptive_closure_pm2_covered",
        "adaptive_coverage_reason",
    ]
    event_output: list[dict[str, Any]] = []
    for row in event_rows:
        event_output.append(dict(row))
    write_csv(output_root / "coverage_replay_events_v1_1.csv", event_output, event_fields)
    write_csv(output_root / "coverage_replay_stage3_centers_v1_1.csv", stage3_rows, event_fields)


def all_known_events_pass(rows: Sequence[dict[str, Any]]) -> bool:
    positive = [row for row in rows if int(row.get("confirmed_event_count_gold") or 0) > 0]
    return bool(positive) and all(
        row.get("adaptive_event_center_recall") == "1.0"
        and row.get("adaptive_event_closure_pm2_recall") == "1.0"
        and row.get("budget_respected", "").lower() == "true"
        for row in positive
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("dataset_generation_logs/sampling_validation/batch_sampled_v1_1_offline_coverage"),
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        default=[f"seed_{index:02d}" for index in range(10)],
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
    if len(set(args.seeds)) != len(args.seeds):
        raise ValueError("Seed labels must be unique")

    tasks = list(GOLD_TASKS)
    # Read each immutable gold task once.  The 4,000+ row budget sweep is a
    # pure in-memory replay after this point; it never re-reads scene files.
    task_inputs = {task.task_id: load_task_inputs(project_root, task) for task in tasks}
    total1200_configs = [config_for(length, 1200) for length in BLOCK_LENGTHS]
    summaries: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    stage3_rows: list[dict[str, Any]] = []

    # Persist plans/manifests for the four declared v1.1 block profiles at
    # the requested 1200 total budget.
    for config in total1200_configs:
        for task in tasks:
            for seed in args.seeds:
                output_dir = output_root / config.name / task_slug(task) / seed
                summary, event_detail, stage3_detail = evaluate_task_config(
                    project_root,
                    task,
                    config,
                    seed,
                    output_dir,
                    task_inputs[task.task_id],
                )
                for detail in event_detail:
                    detail.update(
                        {
                            "task_id": task.task_id,
                            "scene_id": task.scene_id,
                            "prn": task.prn,
                            "seed": seed,
                            "config_name": config.name,
                            "block_length": config.block_length,
                            "total_budget": config.total_budget,
                        }
                    )
                for detail in stage3_detail:
                    detail.update(
                        {
                            "task_id": task.task_id,
                            "scene_id": task.scene_id,
                            "prn": task.prn,
                            "seed": seed,
                            "config_name": config.name,
                            "block_length": config.block_length,
                            "total_budget": config.total_budget,
                        }
                    )
                summaries.append(summary)
                event_rows.extend(event_detail)
                stage3_rows.extend(stage3_detail)

    # Budget sweep is a summary-only diagnostic. It uses the same predeclared
    # block families and never uses gold labels to decide which windows to add.
    sweep_rows: list[dict[str, Any]] = []
    for total_budget in TOTAL_BUDGETS:
        for length in BLOCK_LENGTHS:
            config = config_for(length, total_budget)
            for task in tasks:
                for seed in args.seeds:
                    summary, _, _ = evaluate_task_config(
                        project_root,
                        task,
                        config,
                        seed,
                        output_dir=None,
                        inputs=task_inputs[task.task_id],
                    )
                    sweep_rows.append(
                        {
                            "task_id": task.task_id,
                            "scene_id": task.scene_id,
                            "prn": task.prn,
                            "seed": seed,
                            "config_name": config.name,
                            "block_length": length,
                            "total_budget": total_budget,
                            "initial_budget": config.initial_budget,
                            "stage0_window_count": summary["stage0_window_count"],
                            "initial_stage1_count": summary["initial_stage1_count"],
                            "adaptive_stage1_count": summary["adaptive_stage1_count"],
                            "confirmed_event_count_gold": summary["confirmed_event_count_gold"],
                            "adaptive_event_center_recall": summary["adaptive_event_center_recall"],
                            "adaptive_event_closure_pm2_recall": summary["adaptive_event_closure_pm2_recall"],
                            "budget_respected": summary["budget_respected"],
                        }
                    )

    write_summary_csvs(output_root, summaries, event_rows, stage3_rows)
    write_csv(
        output_root / "budget_sweep_v1_1.csv",
        sweep_rows,
        list(sweep_rows[0]) if sweep_rows else ["task_id"],
    )
    root_manifest = {
        "schema_version": "sampling-validation-v1.1",
        "profile_version": V11_PROFILE_VERSION,
        "project_root": str(project_root),
        "output_root": str(output_root),
        "task_count": len(tasks),
        "seed_labels": list(args.seeds),
        "tasks": [task.task_id for task in tasks],
        "block_lengths_evaluated": list(BLOCK_LENGTHS),
        "total_budgets_swept": list(TOTAL_BUDGETS),
        "full_scan_stage1_surrogate_used": True,
        "hidden_stage1_rows_used_for_seed_selection": False,
        "matlab_invoked": False,
        "sage_invoked": False,
        "raw_iq_opened": False,
        "output_is_outside_sage_results": True,
        "gold_labels_used_for_selection": False,
        "event_recall_gate_passed_for_1200_profiles": all_known_events_pass(
            [row for row in summaries if row["total_budget"] == 1200]
        ),
    }
    (output_root / "sampling_validation_manifest_v1_1.json").write_text(
        json.dumps(root_manifest, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(f"sampling_validation_output={output_root}")
    print(f"tasks={len(tasks)} seeds={len(args.seeds)} total1200_plans={len(tasks) * len(args.seeds) * len(BLOCK_LENGTHS)}")
    print(f"coverage_replay={output_root / 'coverage_replay_v1_1.csv'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:  # pragma: no cover - CLI diagnostics
        raise SystemExit(f"ERROR: {exc}")
