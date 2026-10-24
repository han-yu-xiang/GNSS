"""Validated scene-local route fixes and continuity components for Task 7.

This module only parses small, checksum-validated NMEA RMC records and
transforms in-memory fix rows.  It does not modify source trajectories or
read SAGE/CIR payloads.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path
from statistics import median, pvariance
from typing import Any, Mapping, Sequence

from scripts.preprocessing.satellite_geometry import nmea_payload, parse_nmea_datetime


_NMEA_CHECKSUM = re.compile(r"^[0-9A-Fa-f]{2}$")
_EARTH_MEAN_RADIUS_M = 6_371_008.8
_KNOT_TO_METRES_PER_SECOND = 0.5144444444444445
_SUSTAINED_MIN_FIXES_PER_BIN = 3
_SUSTAINED_SPEED_DELTA_MPS = 5.0
_SUSTAINED_SPEED_STABILITY_MPS = 2.5
_STATIONARY_SPEED_LIMIT_MPS = 1.0
_SUSTAINED_COURSE_DELTA_DEGREES = 30.0
_SUSTAINED_COURSE_STABILITY_DEGREES = 15.0
_SPATIAL_METRICS = (
    "mean_mpc_count_per_window",
    "median_excess_delay_chips",
    "median_doppler_offset_hz",
    "median_relative_power_db",
)
_MIN_SCENES_FOR_RANGE = 8
_MIN_SUPPORTED_LAG_BANDS_FOR_RANGE = 3
_RANGE_DECORRELATION_THRESHOLD = math.exp(-1.0)
_RANGE_MONOTONICITY_TOLERANCE = 0.05
_RANGE_MAX_SCENE_BLOCK_CV = 0.25


def _checksum_valid_rmc_line(line: str) -> list[str] | None:
    text = line.strip().lstrip("\ufeff")
    if not text.startswith("$") or "*" not in text:
        return None
    payload, checksum_text = text[1:].rsplit("*", 1)
    if not _NMEA_CHECKSUM.fullmatch(checksum_text):
        return None
    fields, checksum_ok = nmea_payload(text)
    if fields is None or not checksum_ok:
        return None
    checksum = 0
    for character in payload:
        checksum ^= ord(character)
    if checksum != int(checksum_text, 16):
        return None
    return fields


def _parse_coordinate(value: str, hemisphere: str, *, latitude: bool) -> float:
    field = "latitude" if latitude else "longitude"
    hemisphere = hemisphere.upper()
    legal_hemispheres = {"N", "S"} if latitude else {"E", "W"}
    maximum_degrees = 90 if latitude else 180
    if hemisphere not in legal_hemispheres:
        raise ValueError(f"invalid {field} hemisphere")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {field} coordinate") from error
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"invalid {field} coordinate")

    degrees = int(numeric // 100)
    minutes = numeric - degrees * 100
    if not 0 <= minutes < 60 or degrees > maximum_degrees:
        raise ValueError(f"{field} coordinate outside legal range")
    if degrees == maximum_degrees and minutes != 0:
        raise ValueError(f"{field} coordinate outside legal range")
    decimal = degrees + minutes / 60.0
    if hemisphere in {"S", "W"}:
        decimal = -decimal
    return decimal


def _optional_float(value: str, *, minimum: float, maximum: float) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number) or not minimum <= number <= maximum:
        return None
    return number


def parse_valid_rmc_fixes(nmea_paths: Sequence[Path]) -> list[dict[str, Any]]:
    """Return chronologically sorted checksum-valid active GPS RMC fixes.

    RMC carries a calendar date as well as UTC time, so midnight rollover is
    resolved by that recorded date rather than inferred from line order. Within
    each file, duplicate and out-of-order valid timestamps are rejected. A
    duplicate UTC timestamp across supplied files is also retained only once,
    with the first input source winning deterministically.
    """

    fixes, _ = parse_valid_rmc_fixes_with_diagnostics(nmea_paths)
    return fixes


def parse_valid_rmc_fixes_with_diagnostics(
    nmea_paths: Sequence[Path],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return accepted RMC fixes and aggregate rejection counters.

    Diagnostic output contains counts only; it deliberately omits coordinates,
    sentence text, source paths and raw NMEA content.
    """

    diagnostics = Counter(
        {
            "rmc_sentence_count": 0,
            "checksum_valid_rmc_count": 0,
            "checksum_invalid_rmc_count": 0,
            "inactive_rmc_count": 0,
            "malformed_rmc_count": 0,
            "invalid_datetime_count": 0,
            "invalid_coordinate_count": 0,
            "duplicate_timestamp_count": 0,
            "out_of_order_timestamp_count": 0,
            "valid_rmc_count": 0,
        }
    )
    fixes: list[dict[str, Any]] = []
    seen_utc: set[datetime] = set()
    fix_by_utc: dict[datetime, dict[str, Any]] = {}

    for path_value in nmea_paths:
        path = Path(path_value).resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"NMEA source is not a regular file: {path}")
        last_file_utc: datetime | None = None
        last_valid_fix: dict[str, Any] | None = None
        barrier_pending = False

        def mark_rejected_rmc() -> None:
            nonlocal barrier_pending
            barrier_pending = True
            if last_valid_fix is not None:
                last_valid_fix["break_after"] = True

        with path.open("r", encoding="ascii", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                text = raw_line.strip().lstrip("\ufeff")
                if not re.match(r"^\$(?:GP|GN)RMC(?:,|\*)", text, flags=re.IGNORECASE):
                    continue
                diagnostics["rmc_sentence_count"] += 1
                fields = _checksum_valid_rmc_line(raw_line)
                if fields is None or not fields or fields[0].upper() not in {"GPRMC", "GNRMC"}:
                    diagnostics["checksum_invalid_rmc_count"] += 1
                    mark_rejected_rmc()
                    continue
                diagnostics["checksum_valid_rmc_count"] += 1
                if len(fields) < 10:
                    diagnostics["malformed_rmc_count"] += 1
                    mark_rejected_rmc()
                    continue
                if fields[2].strip().upper() != "A":
                    diagnostics["inactive_rmc_count"] += 1
                    mark_rejected_rmc()
                    continue
                try:
                    utc_time = parse_nmea_datetime(fields[1].strip(), fields[9].strip())
                except (IndexError, TypeError, ValueError, OverflowError):
                    diagnostics["invalid_datetime_count"] += 1
                    mark_rejected_rmc()
                    continue
                try:
                    latitude_deg = _parse_coordinate(
                        fields[3].strip(), fields[4].strip(), latitude=True
                    )
                    longitude_deg = _parse_coordinate(
                        fields[5].strip(), fields[6].strip(), latitude=False
                    )
                except (IndexError, TypeError, ValueError, OverflowError):
                    diagnostics["invalid_coordinate_count"] += 1
                    mark_rejected_rmc()
                    continue

                if last_file_utc is not None and utc_time <= last_file_utc:
                    if utc_time == last_file_utc:
                        diagnostics["duplicate_timestamp_count"] += 1
                    else:
                        diagnostics["out_of_order_timestamp_count"] += 1
                    mark_rejected_rmc()
                    continue
                last_file_utc = utc_time
                if utc_time in seen_utc:
                    diagnostics["duplicate_timestamp_count"] += 1
                    if utc_time in fix_by_utc:
                        fix_by_utc[utc_time]["break_after"] = True
                    mark_rejected_rmc()
                    continue
                seen_utc.add(utc_time)

                speed_knots = _optional_float(fields[7], minimum=0.0, maximum=1_000.0)
                course_deg = _optional_float(fields[8], minimum=0.0, maximum=360.0)
                fix = {
                        "utc_time": utc_time.astimezone(timezone.utc),
                        "latitude_deg": latitude_deg,
                        "longitude_deg": longitude_deg,
                        "receiver_speed_knots": speed_knots,
                        "receiver_speed_mps": (
                            speed_knots * _KNOT_TO_METRES_PER_SECOND
                            if speed_knots is not None
                            else None
                        ),
                        "receiver_course_deg": course_deg,
                        "source_path": str(path),
                        "source_record_id": f"{path.name}:{line_number:06d}",
                        "source_line_number": line_number,
                        "break_before": barrier_pending,
                        "break_after": False,
                    }
                fixes.append(fix)
                fix_by_utc[utc_time] = fix
                last_valid_fix = fix
                barrier_pending = False

    diagnostics["valid_rmc_count"] = len(fixes)
    fixes.sort(
        key=lambda fix: (
            fix["utc_time"],
            fix["source_path"].casefold(),
            fix["source_line_number"],
        )
    )
    return fixes, dict(diagnostics)


def _validated_fix(fix: Mapping[str, Any], index: int) -> tuple[datetime, float, float]:
    try:
        utc_time = fix["utc_time"]
        latitude = float(fix["latitude_deg"])
        longitude = float(fix["longitude_deg"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"fix {index} requires utc_time, latitude_deg and longitude_deg") from error
    if not isinstance(utc_time, datetime) or utc_time.tzinfo is None or utc_time.utcoffset() is None:
        raise ValueError(f"fix {index} utc_time must be timezone-aware")
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError(f"fix {index} latitude outside [-90, 90]")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError(f"fix {index} longitude outside [-180, 180]")
    return utc_time.astimezone(timezone.utc), latitude, longitude


def _haversine_distance_m(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2.0) ** 2
    )
    central_angle = 2.0 * math.atan2(math.sqrt(haversine), math.sqrt(max(0.0, 1.0 - haversine)))
    return _EARTH_MEAN_RADIUS_M * central_angle


def split_trajectory_components(
    fixes: Sequence[Mapping[str, Any]],
    *,
    max_gap_seconds: float = 2.5,
    jump_speed_mps: float = 80.0,
) -> list[dict[str, Any]]:
    """Assign deterministic continuity components and within-component distance.

    A rejected RMC record, duplicate/out-of-order timestamp, gap above
    ``max_gap_seconds`` or implied speed above ``jump_speed_mps`` begins a
    fresh component. Rejected edges are recorded as candidates/reasons but are
    excluded from cumulative distance. Cumulative distance resets at breaks.
    """

    if not math.isfinite(max_gap_seconds) or max_gap_seconds <= 0:
        raise ValueError("max_gap_seconds must be a positive finite number")
    if not math.isfinite(jump_speed_mps) or jump_speed_mps <= 0:
        raise ValueError("jump_speed_mps must be a positive finite number")

    result: list[dict[str, Any]] = []
    previous: tuple[datetime, float, float] | None = None
    component_number = 0
    cumulative_distance = 0.0

    for index, fix in enumerate(fixes):
        current = _validated_fix(fix, index)
        utc_time, latitude, longitude = current
        break_reason = ""
        adjacent_distance: float | None = None
        implied_speed: float | None = None
        candidate_distance: float | None = None
        candidate_speed: float | None = None

        if previous is None:
            break_reason = "TRACE_START"
        elif bool(fix.get("break_before")):
            break_reason = "REJECTED_RMC_BARRIER"
        else:
            previous_time, previous_latitude, previous_longitude = previous
            elapsed = (utc_time - previous_time).total_seconds()
            if elapsed == 0:
                break_reason = "DUPLICATE_TIMESTAMP"
            elif elapsed < 0:
                break_reason = "OUT_OF_ORDER_TIMESTAMP"
            elif elapsed > max_gap_seconds:
                break_reason = "TIME_GAP"
            else:
                candidate_distance = _haversine_distance_m(
                    previous_latitude,
                    previous_longitude,
                    latitude,
                    longitude,
                )
                candidate_speed = candidate_distance / elapsed
                if candidate_speed > jump_speed_mps:
                    break_reason = "JUMP_SPEED_LIMIT"
                else:
                    adjacent_distance = candidate_distance
                    implied_speed = candidate_speed

        if break_reason:
            component_number += 1
            cumulative_distance = 0.0
        else:
            cumulative_distance += adjacent_distance or 0.0

        enriched = dict(fix)
        enriched.update(
            {
                "utc_time": utc_time,
                "component_id": f"component_{component_number:04d}",
                "adjacent_distance_m": adjacent_distance,
                "implied_speed_mps": implied_speed,
                "candidate_distance_m": candidate_distance,
                "candidate_speed_mps": candidate_speed,
                "cumulative_distance_m": cumulative_distance,
                "break_reason": break_reason,
                "max_gap_seconds": max_gap_seconds,
                "jump_speed_mps": jump_speed_mps,
            }
        )
        result.append(enriched)
        previous = current

    return result


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _format_number(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return ""
    if abs(value) < 0.0000000005:
        value = 0.0
    return f"{value:.9f}".rstrip("0").rstrip(".")


def _as_finite_number(value: Any, *, field: str, minimum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be numeric") from error
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise ValueError(f"{field} is outside its valid range")
    return number


def _validate_scene_fixes(
    scene_id: str,
    fixes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    previous_time: datetime | None = None
    for index, fix in enumerate(fixes):
        utc_time, latitude, longitude = _validated_fix(fix, index)
        if previous_time is not None and utc_time <= previous_time:
            raise ValueError(f"fixes for {scene_id} must have unique increasing UTC timestamps")
        previous_time = utc_time
        component_id = str(fix.get("component_id", "")).strip()
        if not component_id:
            raise ValueError(f"fix {index} for {scene_id} requires component_id")
        cumulative = _as_finite_number(
            fix.get("cumulative_distance_m"),
            field="cumulative_distance_m",
            minimum=0.0,
        )
        fix_scene = str(fix.get("scene_id", scene_id)).strip()
        if fix_scene != scene_id:
            raise ValueError(f"fix scene_id {fix_scene!r} conflicts with key {scene_id!r}")
        normalized.append(
            {
                **dict(fix),
                "utc_time": utc_time,
                "latitude_deg": latitude,
                "longitude_deg": longitude,
                "component_id": component_id,
                "cumulative_distance_m": cumulative,
                "source_path": str(fix.get("source_path", "")),
                "source_record_id": str(fix.get("source_record_id", "")),
                "scene_id": scene_id,
            }
        )
    return normalized


def build_trajectory_window_overlay(
    stage2_windows: Sequence[Mapping[str, str]],
    utc_by_window: Mapping[tuple[str, str], datetime],
    fixes_by_scene: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    max_position_delta_seconds: float = 2.5,
) -> list[dict[str, str]]:
    """Attach each Stage2-selected window to a nearest validated same-scene fix.

    Position is assigned only by nearest-neighbor inside observed component
    coverage. No endpoint extrapolation or interpolation is used.
    A window strictly inside an interval whose endpoints belong to different
    trajectory components is left unlocated rather than carried across that
    discontinuity. Signed delta is ``fix UTC - Stage0 window UTC``.
    """

    if (
        not math.isfinite(max_position_delta_seconds)
        or max_position_delta_seconds < 0
    ):
        raise ValueError("max_position_delta_seconds must be a nonnegative finite number")

    normalized_fixes = {
        str(scene_id).strip(): _validate_scene_fixes(str(scene_id).strip(), rows)
        for scene_id, rows in fixes_by_scene.items()
    }
    utc_values: dict[tuple[str, str], datetime] = {}
    for raw_key, raw_value in utc_by_window.items():
        if not isinstance(raw_key, tuple) or len(raw_key) != 2:
            raise ValueError("UTC index keys must be (run_id, window_id)")
        key = (str(raw_key[0]).strip(), str(raw_key[1]).strip())
        if not all(key):
            raise ValueError("UTC index keys require run_id and window_id")
        if not isinstance(raw_value, datetime) or raw_value.tzinfo is None or raw_value.utcoffset() is None:
            raise ValueError(f"Stage0 UTC for {key} must be timezone-aware")
        if key in utc_values:
            raise ValueError(f"duplicate UTC index key {key}")
        utc_values[key] = raw_value.astimezone(timezone.utc)

    seen_windows: set[tuple[str, str]] = set()
    output: list[dict[str, str]] = []
    for index, raw_window in enumerate(stage2_windows):
        run_id = str(raw_window.get("run_id", "")).strip()
        window_id = str(raw_window.get("window_id", "")).strip()
        scene_id = str(raw_window.get("scene_id", "")).strip()
        prn = str(raw_window.get("prn", "")).strip()
        if not run_id or not window_id or not scene_id or not prn:
            raise ValueError(f"Stage2 window {index} requires run_id, window_id, scene_id and prn")
        key = (run_id, window_id)
        if key in seen_windows:
            raise ValueError(f"duplicate Stage2 window identity {key}")
        seen_windows.add(key)

        row = {
            "run_id": run_id,
            "window_id": window_id,
            "scene_id": scene_id,
            "prn": prn,
            "tracking_channel": str(raw_window.get("tracking_channel", "")),
            "window_utc": "",
            "position_utc": "",
            "position_delta_seconds": "",
            "position_delta_seconds_abs": "",
            "position_source_path": "",
            "position_source_record_id": "",
            "latitude_deg": "",
            "longitude_deg": "",
            "route_component_id": "",
            "route_cumulative_distance_m": "",
            "receiver_speed_mps": "",
            "receiver_course_deg": "",
            "position_status": "POSITION_MISSING",
            "missing_reason": "",
        }
        target_utc = utc_values.get(key)
        if target_utc is None:
            row["missing_reason"] = "MISSING_STAGE0_UTC"
            output.append(row)
            continue
        row["window_utc"] = _iso_utc(target_utc)

        scene_fixes = normalized_fixes.get(scene_id, [])
        if not scene_fixes:
            row["missing_reason"] = "NO_VALID_SCENE_FIX"
            output.append(row)
            continue

        fix_times = [fix["utc_time"] for fix in scene_fixes]
        if target_utc < fix_times[0] or target_utc > fix_times[-1]:
            if target_utc > fix_times[-1] and bool(scene_fixes[-1].get("break_after")):
                row["missing_reason"] = "REJECTED_RMC_BARRIER"
            else:
                row["missing_reason"] = "OUTSIDE_OBSERVED_ROUTE_COVERAGE"
            output.append(row)
            continue
        insertion = _bisect_left(fix_times, target_utc)
        previous_fix = scene_fixes[insertion - 1] if insertion > 0 else None
        next_fix = scene_fixes[insertion] if insertion < len(scene_fixes) else None
        if (
            previous_fix is not None
            and next_fix is not None
            and previous_fix["component_id"] != next_fix["component_id"]
            and previous_fix["utc_time"] < target_utc < next_fix["utc_time"]
        ):
            row["missing_reason"] = "WITHIN_ROUTE_DISCONTINUITY_GAP"
            output.append(row)
            continue

        candidates = [fix for fix in (previous_fix, next_fix) if fix is not None]
        nearest = min(
            candidates,
            key=lambda fix: (
                abs((fix["utc_time"] - target_utc).total_seconds()),
                fix["utc_time"],
                fix["source_record_id"],
            ),
        )
        signed_delta = (nearest["utc_time"] - target_utc).total_seconds()
        if abs(signed_delta) > max_position_delta_seconds:
            row["missing_reason"] = "OUTSIDE_POSITION_TOLERANCE"
            output.append(row)
            continue

        row.update(
            {
                "position_utc": _iso_utc(nearest["utc_time"]),
                "position_delta_seconds": _format_number(signed_delta),
                "position_delta_seconds_abs": _format_number(abs(signed_delta)),
                "position_source_path": nearest["source_path"],
                "position_source_record_id": nearest["source_record_id"],
                "latitude_deg": _format_number(nearest["latitude_deg"]),
                "longitude_deg": _format_number(nearest["longitude_deg"]),
                "route_component_id": nearest["component_id"],
                "route_cumulative_distance_m": _format_number(nearest["cumulative_distance_m"]),
                "receiver_speed_mps": _format_number(
                    _optional_row_number(nearest.get("receiver_speed_mps"), minimum=0.0)
                ),
                "receiver_course_deg": _format_number(
                    _optional_row_number(nearest.get("receiver_course_deg"), minimum=0.0, maximum=360.0)
                ),
                "position_status": "POSITION_MATCHED",
            }
        )
        output.append(row)
    return output


def _bisect_left(values: Sequence[datetime], target: datetime) -> int:
    low = 0
    high = len(values)
    while low < high:
        middle = (low + high) // 2
        if values[middle] < target:
            low = middle + 1
        else:
            high = middle
    return low


def _optional_row_number(
    value: Any,
    *,
    minimum: float,
    maximum: float | None = None,
) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        return None
    return number


def _circular_mean_degrees(values: Sequence[float]) -> float | None:
    if not values:
        return None
    sin_sum = sum(math.sin(math.radians(value)) for value in values)
    cos_sum = sum(math.cos(math.radians(value)) for value in values)
    if math.hypot(sin_sum, cos_sum) < 1e-12:
        return None
    return math.degrees(math.atan2(sin_sum, cos_sum)) % 360.0


def _angular_distance_degrees(left: float, right: float) -> float:
    return abs((left - right + 180.0) % 360.0 - 180.0)


def _bin_index(cumulative_distance_m: float, length_m: int) -> int:
    return int(math.floor(cumulative_distance_m / length_m))


def build_route_segment_rows(
    window_overlay: Sequence[Mapping[str, str]],
    fix_rows: Sequence[Mapping[str, Any]],
    *,
    lengths_m: Sequence[int] = (50, 100, 250),
) -> list[dict[str, str]]:
    """Create descriptive fixed-distance bins without splitting continuity components.

    Route bins are candidate aggregation units, not independent observations.
    Sustained speed/course changes are annotations only: they require three
    consecutive bins with at least three receiver observations each and never
    change component or bin boundaries.
    """

    if not lengths_m:
        raise ValueError("lengths_m must contain at least one positive integer")
    lengths: list[int] = []
    for length in lengths_m:
        if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
            raise ValueError("lengths_m must contain positive integers")
        if length in lengths:
            raise ValueError("lengths_m must not contain duplicates")
        lengths.append(length)

    normalized_fixes: list[dict[str, Any]] = []
    for index, fix in enumerate(fix_rows):
        scene_id = str(fix.get("scene_id", "")).strip()
        if not scene_id:
            raise ValueError(f"fix {index} requires scene_id")
        utc_time, latitude, longitude = _validated_fix(fix, index)
        component_id = str(fix.get("component_id", "")).strip()
        if not component_id:
            raise ValueError(f"fix {index} requires component_id")
        cumulative = _as_finite_number(
            fix.get("cumulative_distance_m"),
            field="cumulative_distance_m",
            minimum=0.0,
        )
        source_record_id = str(fix.get("source_record_id", "")).strip()
        if not source_record_id:
            source_record_id = f"{scene_id}:{utc_time.isoformat()}"
        normalized = {
            **dict(fix),
            "scene_id": scene_id,
            "utc_time": utc_time,
            "latitude_deg": latitude,
            "longitude_deg": longitude,
            "component_id": component_id,
            "cumulative_distance_m": cumulative,
            "source_record_id": source_record_id,
        }
        normalized_fixes.append(normalized)

    groups: dict[tuple[str, str, int, int], dict[str, Any]] = {}

    def get_group(scene_id: str, component_id: str, length: int, bin_number: int) -> dict[str, Any]:
        key = (scene_id, component_id, length, bin_number)
        return groups.setdefault(
            key,
            {
                "fixes": [],
                "window_ids": set(),
                "run_ids": set(),
                "prns": set(),
                "distances": [],
                "prns_by_fix": {},
            },
        )

    for fix in normalized_fixes:
        for length in lengths:
            bin_number = _bin_index(fix["cumulative_distance_m"], length)
            group = get_group(fix["scene_id"], fix["component_id"], length, bin_number)
            group["fixes"].append(fix)
            group["distances"].append(fix["cumulative_distance_m"])

    seen_window_ids: set[tuple[str, str]] = set()
    for index, window in enumerate(window_overlay):
        run_id = str(window.get("run_id", "")).strip()
        window_id = str(window.get("window_id", "")).strip()
        scene_id = str(window.get("scene_id", "")).strip()
        prn = str(window.get("prn", "")).strip()
        if not run_id or not window_id or not scene_id or not prn:
            raise ValueError(f"trajectory overlay row {index} requires run_id, window_id, scene_id and prn")
        identity = (run_id, window_id)
        if identity in seen_window_ids:
            raise ValueError(f"duplicate trajectory window identity {identity}")
        seen_window_ids.add(identity)
        if window.get("position_status") != "POSITION_MATCHED":
            continue
        component_id = str(window.get("route_component_id", "")).strip()
        distance = _as_finite_number(
            window.get("route_cumulative_distance_m"),
            field="route_cumulative_distance_m",
            minimum=0.0,
        )
        fix_id = str(window.get("position_source_record_id", "")).strip()
        for length in lengths:
            bin_number = _bin_index(distance, length)
            key = (scene_id, component_id, length, bin_number)
            group = groups.get(key)
            if group is None:
                raise ValueError(
                    f"matched window {identity} has no source-fix route bin for {scene_id}/{component_id}"
                )
            group["window_ids"].add(identity)
            group["run_ids"].add(run_id)
            group["prns"].add(prn)
            group["distances"].append(distance)
            if fix_id:
                group["prns_by_fix"].setdefault(fix_id, set()).add(prn)

    summaries: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    for key, group in groups.items():
        speed_values = [
            value
            for fix in group["fixes"]
            if (value := _optional_row_number(fix.get("receiver_speed_mps"), minimum=0.0)) is not None
        ]
        course_values = [
            value
            for fix in group["fixes"]
            if (value := _optional_row_number(
                fix.get("receiver_course_deg"), minimum=0.0, maximum=360.0
            )) is not None
        ]
        summaries[key] = {
            **group,
            "speed_values": speed_values,
            "course_values": course_values,
            "median_speed": median(speed_values) if speed_values else None,
            "mean_course": _circular_mean_degrees(course_values),
            "speed_change_candidate": False,
            "drive_state_change_candidate": False,
            "course_change_candidate": False,
        }

    series_keys = sorted({(scene, component, length) for scene, component, length, _ in groups})
    for scene_id, component_id, length in series_keys:
        bins = sorted(
            (key[3], summaries[key])
            for key in summaries
            if key[:3] == (scene_id, component_id, length)
        )
        by_number = dict(bins)
        for bin_number, current in bins:
            previous = by_number.get(bin_number - 1)
            following = by_number.get(bin_number + 1)
            if previous is None or following is None:
                continue
            speed_support = all(
                len(item["speed_values"]) >= _SUSTAINED_MIN_FIXES_PER_BIN
                for item in (previous, current, following)
            )
            if speed_support:
                prev_speed = previous["median_speed"]
                curr_speed = current["median_speed"]
                next_speed = following["median_speed"]
                stable_after = abs(curr_speed - next_speed) <= _SUSTAINED_SPEED_STABILITY_MPS
                sustained_shift = (
                    abs(curr_speed - prev_speed) >= _SUSTAINED_SPEED_DELTA_MPS
                    and abs(next_speed - prev_speed) >= _SUSTAINED_SPEED_DELTA_MPS
                    and stable_after
                )
                prev_state = "STATIONARY" if prev_speed <= _STATIONARY_SPEED_LIMIT_MPS else "MOVING"
                curr_state = "STATIONARY" if curr_speed <= _STATIONARY_SPEED_LIMIT_MPS else "MOVING"
                next_state = "STATIONARY" if next_speed <= _STATIONARY_SPEED_LIMIT_MPS else "MOVING"
                current["drive_state_change_candidate"] = (
                    prev_state != curr_state == next_state
                )
                current["speed_change_candidate"] = sustained_shift

            course_support = all(
                len(item["course_values"]) >= _SUSTAINED_MIN_FIXES_PER_BIN
                and item["mean_course"] is not None
                for item in (previous, current, following)
            )
            if course_support:
                prev_course = previous["mean_course"]
                curr_course = current["mean_course"]
                next_course = following["mean_course"]
                current["course_change_candidate"] = (
                    _angular_distance_degrees(prev_course, curr_course)
                    >= _SUSTAINED_COURSE_DELTA_DEGREES
                    and _angular_distance_degrees(prev_course, next_course)
                    >= _SUSTAINED_COURSE_DELTA_DEGREES
                    and _angular_distance_degrees(curr_course, next_course)
                    <= _SUSTAINED_COURSE_STABILITY_DEGREES
                )

    output: list[dict[str, str]] = []
    for (scene_id, component_id, length, bin_number), summary in sorted(groups.items()):
        stats = summaries[(scene_id, component_id, length, bin_number)]
        speed_values = stats["speed_values"]
        course_values = stats["course_values"]
        mean_course = stats["mean_course"]
        co_located_count = sum(
            1 for prns in stats["prns_by_fix"].values() if len(prns) > 1
        )
        median_speed = stats["median_speed"]
        drive_state = (
            "INSUFFICIENT_SPEED_SUPPORT"
            if median_speed is None
            else "STATIONARY" if median_speed <= _STATIONARY_SPEED_LIMIT_MPS else "MOVING"
        )
        observed_distances = stats["distances"]
        output.append(
            {
                "route_segment_id": f"{scene_id}__{component_id}__L{length}__B{bin_number:06d}",
                "scene_id": scene_id,
                "component_id": component_id,
                "bin_length_m": str(length),
                "bin_index": str(bin_number),
                "bin_start_m": _format_number(float(bin_number * length)),
                "bin_end_m": _format_number(float((bin_number + 1) * length)),
                "observed_distance_min_m": _format_number(min(observed_distances)),
                "observed_distance_max_m": _format_number(max(observed_distances)),
                "fix_count": str(len({fix["source_record_id"] for fix in stats["fixes"]})),
                "stage2_window_count": str(len(stats["window_ids"])),
                "run_count": str(len(stats["run_ids"])),
                "prn_count": str(len(stats["prns"])),
                "co_located_cross_prn_fix_count": str(co_located_count),
                "median_receiver_speed_mps": _format_number(median_speed),
                "min_receiver_speed_mps": _format_number(min(speed_values) if speed_values else None),
                "max_receiver_speed_mps": _format_number(max(speed_values) if speed_values else None),
                "valid_receiver_speed_fix_count": str(len(speed_values)),
                "circular_mean_receiver_course_deg": _format_number(mean_course),
                "valid_receiver_course_fix_count": str(len(course_values)),
                "drive_state": drive_state,
                "sustained_drive_state_change_candidate": "YES" if stats["drive_state_change_candidate"] else "NO",
                "sustained_speed_change_candidate": "YES" if stats["speed_change_candidate"] else "NO",
                "sustained_course_change_candidate": "YES" if stats["course_change_candidate"] else "NO",
                "candidate_min_fix_count_per_bin": str(_SUSTAINED_MIN_FIXES_PER_BIN),
                "candidate_speed_delta_threshold_mps": _format_number(_SUSTAINED_SPEED_DELTA_MPS),
                "candidate_speed_stability_mps": _format_number(_SUSTAINED_SPEED_STABILITY_MPS),
                "candidate_stationary_speed_limit_mps": _format_number(_STATIONARY_SPEED_LIMIT_MPS),
                "candidate_course_delta_threshold_deg": _format_number(_SUSTAINED_COURSE_DELTA_DEGREES),
                "candidate_course_stability_deg": _format_number(_SUSTAINED_COURSE_STABILITY_DEGREES),
                "analysis_unit_role": "DESCRIPTIVE_CANDIDATE_BIN_NOT_INDEPENDENT_SAMPLE",
            }
        )
    return output


def _optional_metric_value(row: Mapping[str, Any], field: str) -> float | None:
    value = row.get(field)
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_iso_utc(value: Any, *, field: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be ISO-8601 UTC") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def aggregate_stage2_metrics_by_fix(
    path_rows: Sequence[Mapping[str, Any]],
    trajectory_overlay: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Collapse selected-window MPC measures to their exact receiver fix.

    Multiple Stage2 windows from one run that resolve to the same checksum-
    valid RMC fix are combined before spatial analysis. Unlocated selected
    windows remain as individual rows with an explicit missing status and are
    excluded only from spatial-lag calculations, not silently discarded.
    Direct/reference paths contribute zero to ``mpc_count``. A zero is thus
    defined only inside the represented Stage2-selected-window frame.
    """

    windows: dict[tuple[str, str], dict[str, Any]] = {}
    for index, overlay in enumerate(trajectory_overlay):
        run_id = str(overlay.get("run_id", "")).strip()
        window_id = str(overlay.get("window_id", "")).strip()
        scene_id = str(overlay.get("scene_id", "")).strip()
        prn = str(overlay.get("prn", "")).strip()
        tracking_channel = str(overlay.get("tracking_channel", "")).strip()
        if not run_id or not window_id or not scene_id or not prn or not tracking_channel:
            raise ValueError(
                f"trajectory overlay row {index} requires run_id, window_id, scene_id, prn and tracking_channel"
            )
        identity = (run_id, window_id)
        if identity in windows:
            raise ValueError(f"duplicate trajectory overlay identity {identity}")
        location_status = str(overlay.get("position_status", "")).strip()
        if location_status not in {"POSITION_MATCHED", "POSITION_MISSING"}:
            raise ValueError(f"trajectory overlay row {index} has invalid position_status")

        fix_utc: datetime | None = None
        component_id = ""
        distance: float | None = None
        source_record_id = ""
        if location_status == "POSITION_MATCHED":
            fix_utc = _parse_iso_utc(overlay.get("position_utc"), field="position_utc")
            component_id = str(overlay.get("route_component_id", "")).strip()
            if not component_id:
                raise ValueError(f"matched overlay window {identity} lacks route_component_id")
            distance = _as_finite_number(
                overlay.get("route_cumulative_distance_m"),
                field="route_cumulative_distance_m",
                minimum=0.0,
            )
            source_record_id = str(overlay.get("position_source_record_id", "")).strip()
        windows[identity] = {
            "run_id": run_id,
            "window_id": window_id,
            "scene_id": scene_id,
            "prn": prn,
            "tracking_channel": tracking_channel,
            "location_status": location_status,
            "fix_utc": fix_utc,
            "component_id": component_id,
            "distance": distance,
            "source_record_id": source_record_id,
            "paths": [],
        }

    path_identities: set[tuple[str, str, str]] = set()
    for index, path in enumerate(path_rows):
        run_id = str(path.get("run_id", "")).strip()
        window_id = str(path.get("window_id", "")).strip()
        scene_id = str(path.get("scene_id", "")).strip()
        prn = str(path.get("prn", "")).strip()
        path_id = str(path.get("path_id", "")).strip()
        identity = (run_id, window_id)
        if not all((run_id, window_id, scene_id, prn, path_id)):
            raise ValueError(f"Stage2 path row {index} requires run_id/window_id/scene_id/prn/path_id")
        if identity not in windows:
            raise ValueError(f"Stage2 path {identity}/{path_id} has no trajectory overlay identity")
        overlay = windows[identity]
        if scene_id != overlay["scene_id"] or prn != overlay["prn"]:
            raise ValueError(f"Stage2 path identity conflicts with trajectory overlay for {identity}")
        path_channel = str(path.get("tracking_channel", "")).strip()
        if not path_channel or path_channel != overlay["tracking_channel"]:
            raise ValueError(f"Stage2 path channel conflicts with trajectory overlay for {identity}")
        path_identity = (run_id, window_id, path_id)
        if path_identity in path_identities:
            raise ValueError(f"duplicate Stage2 path identity {path_identity}")
        path_identities.add(path_identity)

        multipath_text = str(path.get("is_multipath", "")).strip()
        if multipath_text not in {"0", "1"}:
            raise ValueError(f"Stage2 path {path_identity} has invalid is_multipath")
        is_multipath = multipath_text == "1"
        modeling_role = str(path.get("modeling_role", "")).strip()
        expected_role = "MPC_CANDIDATE" if is_multipath else "DIRECT_REFERENCE"
        if modeling_role != expected_role:
            raise ValueError(f"modeling_role conflicts with is_multipath for {path_identity}")
        overlay["paths"].append({**dict(path), "_is_multipath": is_multipath})

    for identity, window in windows.items():
        if not window["paths"]:
            raise ValueError(f"selected Stage2 window {identity} has no Stage2 path rows")

    aggregates: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for identity, window in windows.items():
        if window["location_status"] == "POSITION_MATCHED":
            fix_utc: datetime = window["fix_utc"]
            key = (window["scene_id"], window["run_id"], _iso_utc(fix_utc), "")
        else:
            key = (window["scene_id"], window["run_id"], "", window["window_id"])
        aggregate = aggregates.setdefault(
            key,
            {
                "scene_id": window["scene_id"],
                "run_id": window["run_id"],
                "prn": window["prn"],
                "tracking_channel": window["tracking_channel"],
                "fix_utc": key[2],
                "location_status": window["location_status"],
                "position_source_record_id": window["source_record_id"],
                "route_component_id": window["component_id"],
                "route_cumulative_distance_m": window["distance"],
                "window_ids": set(),
                "path_rows": [],
                "mpc_rows": [],
                "window_summaries": [],
            },
        )
        if aggregate["prn"] != window["prn"] or aggregate["tracking_channel"] != window["tracking_channel"]:
            raise ValueError(f"one run maps to conflicting PRN/channel identities: {window['run_id']}")
        for output_field, window_field in (
            ("position_source_record_id", "source_record_id"),
            ("route_component_id", "component_id"),
            ("route_cumulative_distance_m", "distance"),
        ):
            if aggregate[output_field] != window[window_field]:
                raise ValueError(f"windows mapped to one fix disagree on {output_field}: {identity}")
        aggregate["window_ids"].add(identity)
        aggregate["path_rows"].extend(window["paths"])
        window_mpc_rows = [path for path in window["paths"] if path["_is_multipath"]]
        aggregate["mpc_rows"].extend(window_mpc_rows)
        metric_fields = (
            "excess_delay_chips",
            "doppler_offset_hz",
            "relative_power_db",
        )
        window_summary = {"mpc_count": len(window_mpc_rows)}
        for field in metric_fields:
            values = [
                parsed
                for path in window_mpc_rows
                if (parsed := _optional_metric_value(path, field)) is not None
            ]
            window_summary[field] = median(values) if values else None
            window_summary[f"{field}_path_count"] = len(values)
        aggregate["window_summaries"].append(window_summary)

    output: list[dict[str, Any]] = []
    for _, aggregate in sorted(aggregates.items()):
        window_summaries = aggregate["window_summaries"]
        mpc_counts = [summary["mpc_count"] for summary in window_summaries]
        summary_values = {
            field: [summary[field] for summary in window_summaries if summary[field] is not None]
            for field in ("excess_delay_chips", "doppler_offset_hz", "relative_power_db")
        }
        output.append(
            {
                "scene_id": aggregate["scene_id"],
                "run_id": aggregate["run_id"],
                "prn": aggregate["prn"],
                "tracking_channel": aggregate["tracking_channel"],
                "fix_utc": aggregate["fix_utc"],
                "location_status": aggregate["location_status"],
                "position_source_record_id": aggregate["position_source_record_id"],
                "route_component_id": aggregate["route_component_id"],
                "route_cumulative_distance_m": aggregate["route_cumulative_distance_m"],
                "window_count": len(aggregate["window_ids"]),
                "window_ids": sorted(window_id for _, window_id in aggregate["window_ids"]),
                "stage2_path_row_count": len(aggregate["path_rows"]),
                "direct_reference_path_count": sum(
                    not path["_is_multipath"] for path in aggregate["path_rows"]
                ),
                "mean_mpc_count_per_window": sum(mpc_counts) / len(mpc_counts) if mpc_counts else 0.0,
                "total_mpc_count_across_windows": sum(mpc_counts),
                "median_excess_delay_chips": median(summary_values["excess_delay_chips"])
                if summary_values["excess_delay_chips"] else None,
                "excess_delay_window_count": len(summary_values["excess_delay_chips"]),
                "excess_delay_path_count": sum(
                    summary["excess_delay_chips_path_count"] for summary in window_summaries
                ),
                "median_doppler_offset_hz": median(summary_values["doppler_offset_hz"])
                if summary_values["doppler_offset_hz"] else None,
                "doppler_offset_window_count": len(summary_values["doppler_offset_hz"]),
                "doppler_offset_path_count": sum(
                    summary["doppler_offset_hz_path_count"] for summary in window_summaries
                ),
                "median_relative_power_db": median(summary_values["relative_power_db"])
                if summary_values["relative_power_db"] else None,
                "relative_power_window_count": len(summary_values["relative_power_db"]),
                "relative_power_path_count": sum(
                    summary["relative_power_db_path_count"] for summary in window_summaries
                ),
            }
        )
    return output


def _correlation_range_candidate(
    scene_correlations_by_lag: Mapping[int, Mapping[str, float]],
    lag_edges: Sequence[float],
    *,
    min_scenes: int,
) -> float | None:
    if not scene_correlations_by_lag:
        return None
    supported = [
        index
        for index, values in sorted(scene_correlations_by_lag.items())
        if len(values) >= min_scenes
    ]
    run: list[int] = []
    runs: list[list[int]] = []
    for index in supported:
        if run and index != run[-1] + 1:
            runs.append(run)
            run = []
        run.append(index)
    if run:
        runs.append(run)
    candidate_bands = max(runs, key=len, default=[])
    if len(candidate_bands) < _MIN_SUPPORTED_LAG_BANDS_FOR_RANGE:
        return None

    correlations = [
        sum(scene_correlations_by_lag[index].values())
        / len(scene_correlations_by_lag[index])
        for index in candidate_bands
    ]
    if any(
        right > left + _RANGE_MONOTONICITY_TOLERANCE
        for left, right in zip(correlations, correlations[1:])
    ):
        return None
    threshold = _RANGE_DECORRELATION_THRESHOLD
    for position in range(1, len(candidate_bands)):
        if correlations[position - 1] > threshold >= correlations[position]:
            lag_index = candidate_bands[position]
            return (lag_edges[lag_index] + lag_edges[lag_index + 1]) / 2.0
    return None


def _metric_fix_value(row: Mapping[str, Any], metric: str) -> float | None:
    value = row.get(metric)
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def summarize_spatial_dependence(
    fix_metrics: Sequence[Mapping[str, Any]],
    *,
    lag_edges_m: Sequence[float],
) -> list[dict[str, Any]]:
    """Summarize descriptive within-run spatial dependence by fixed lag bands.

    Pair calculations stay within one scene, run and continuity component.
    Each component is normalized by its own metric variance; normalized lag
    estimates are weighted by valid pair count within run. Runs are equally
    weighted within scene, and scenes are equally weighted in the cross-scene
    profile. Correlation-range
    and effective-local-unit values are only emitted when at least eight
    scenes support at least three consecutive lag bands, the decorrelation
    profile is monotone within tolerance, and leave-one-scene-out range
    sensitivity has coefficient of variation no greater than 0.25. These are
    descriptive candidates, not model fits or independent-sample claims.
    """

    if len(lag_edges_m) < 2:
        raise ValueError("lag_edges_m requires at least two increasing edges")
    edges = [_as_finite_number(edge, field="lag edge", minimum=0.0) for edge in lag_edges_m]
    if any(right <= left for left, right in zip(edges, edges[1:])):
        raise ValueError("lag_edges_m must be strictly increasing")

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    seen_fix: set[tuple[str, str, str]] = set()
    component_distances: dict[tuple[str, str, str], list[float]] = {}
    colocated: dict[tuple[str, str, str], dict[str, set[str]]] = {}
    for index, row in enumerate(fix_metrics):
        if str(row.get("location_status", "POSITION_MATCHED")) != "POSITION_MATCHED":
            continue
        scene_id = str(row.get("scene_id", "")).strip()
        run_id = str(row.get("run_id", "")).strip()
        component_id = str(row.get("route_component_id", "")).strip()
        fix_utc = str(row.get("fix_utc", "")).strip()
        prn = str(row.get("prn", "")).strip()
        if not all((scene_id, run_id, component_id, fix_utc, prn)):
            raise ValueError(f"located fix metric row {index} requires scene/run/component/fix_utc/prn")
        _parse_iso_utc(fix_utc, field="fix_utc")
        identity = (scene_id, run_id, fix_utc)
        if identity in seen_fix:
            raise ValueError(f"duplicate scene/run/fix metric identity {identity}")
        seen_fix.add(identity)
        distance = _as_finite_number(
            row.get("route_cumulative_distance_m"),
            field="route_cumulative_distance_m",
            minimum=0.0,
        )
        normalized = {**dict(row), "route_cumulative_distance_m": distance}
        groups.setdefault((scene_id, run_id, component_id), []).append(normalized)
        component_distances.setdefault((scene_id, run_id, component_id), []).append(distance)
        location_id = str(row.get("position_source_record_id", "")).strip() or fix_utc
        loc_key = (scene_id, component_id, location_id)
        support = colocated.setdefault(loc_key, {"prns": set(), "runs": set()})
        support["prns"].add(prn)
        support["runs"].add(run_id)

    cross_prn_groups = [support for support in colocated.values() if len(support["prns"]) > 1]
    cross_prn_group_count = len(cross_prn_groups)
    cross_prn_run_pair_count = sum(
        len(support["runs"]) * (len(support["runs"]) - 1) // 2
        for support in cross_prn_groups
    )

    accumulators: dict[tuple[str, int], dict[tuple[str, str, str], dict[str, float]]] = {}
    for (scene_id, run_id, component_id), rows in groups.items():
        rows.sort(
            key=lambda row: (
                row["route_cumulative_distance_m"],
                str(row["fix_utc"]),
            )
        )
        values_by_metric = {
            metric: [value for row in rows if (value := _metric_fix_value(row, metric)) is not None]
            for metric in _SPATIAL_METRICS
        }
        variance_by_metric = {
            metric: pvariance(values) if len(values) >= 2 else 0.0
            for metric, values in values_by_metric.items()
        }
        for left_index, left in enumerate(rows):
            left_distance = left["route_cumulative_distance_m"]
            for right in rows[left_index + 1 :]:
                lag = abs(right["route_cumulative_distance_m"] - left_distance)
                if lag < edges[0] or lag >= edges[-1]:
                    continue
                lag_index = bisect_right(edges, lag) - 1
                for metric in _SPATIAL_METRICS:
                    left_value = _metric_fix_value(left, metric)
                    right_value = _metric_fix_value(right, metric)
                    if left_value is None or right_value is None:
                        continue
                    metric_runs = accumulators.setdefault((metric, lag_index), {})
                    component_key = (scene_id, run_id, component_id)
                    accumulator = metric_runs.setdefault(
                        component_key,
                        {"pair_count": 0.0, "semivariance_sum": 0.0, "variance": variance_by_metric[metric]},
                    )
                    accumulator["pair_count"] += 1
                    accumulator["semivariance_sum"] += 0.5 * (left_value - right_value) ** 2

    scene_correlations: dict[tuple[str, int], dict[str, float]] = {}
    scene_semivariances: dict[tuple[str, int], dict[str, float]] = {}
    band_support: dict[tuple[str, int], dict[str, int]] = {}
    for (metric, lag_index), run_values in accumulators.items():
        per_scene_corr: dict[str, list[float]] = {}
        per_scene_gamma: dict[str, list[float]] = {}
        supported_pair_count = 0
        supported_runs: set[str] = set()
        run_component_gamma: dict[tuple[str, str], list[tuple[float, float]]] = {}
        for (scene_id, run_id, _component_id), values in run_values.items():
            supported_pair_count += int(values["pair_count"])
            if values["pair_count"] and values["variance"] > 0:
                gamma = values["semivariance_sum"] / values["pair_count"]
                normalized_gamma = gamma / values["variance"]
                run_component_gamma.setdefault((scene_id, run_id), []).append(
                    (values["pair_count"], normalized_gamma)
                )
        for (scene_id, run_id), component_values in run_component_gamma.items():
            pair_weight = sum(pair_count for pair_count, _ in component_values)
            run_gamma = sum(
                pair_count * normalized_gamma
                for pair_count, normalized_gamma in component_values
            ) / pair_weight
            per_scene_gamma.setdefault(scene_id, []).append(run_gamma)
            per_scene_corr.setdefault(scene_id, []).append(1.0 - run_gamma)
            supported_runs.add(run_id)
        scene_gamma_mean = {
            scene: sum(values) / len(values)
            for scene, values in per_scene_gamma.items()
        }
        scene_corr_mean = {
            scene: sum(values) / len(values)
            for scene, values in per_scene_corr.items()
        }
        scene_semivariances[(metric, lag_index)] = scene_gamma_mean
        scene_correlations[(metric, lag_index)] = scene_corr_mean
        band_support[(metric, lag_index)] = {
            "pair_count": supported_pair_count,
            "run_count": len(supported_runs),
            "scene_count": len(scene_corr_mean),
        }

    output: list[dict[str, Any]] = []
    for metric in _SPATIAL_METRICS:
        correlations_by_lag = {
            lag_index: values
            for (metric_name, lag_index), values in scene_correlations.items()
            if metric_name == metric
        }
        supported_lags = [
            lag_index
            for lag_index, values in correlations_by_lag.items()
            if len(values) >= _MIN_SCENES_FOR_RANGE
        ]
        candidate_range: float | None = None
        estimate_status = "INSUFFICIENT_SPATIAL_SUPPORT"
        range_scene_block_count = 0
        range_lag_band_count = 0
        leave_one_scene_out_range_count = 0
        leave_one_scene_out_range_cv: float | None = None
        if supported_lags:
            contiguous: list[int] = []
            contiguous_groups: list[list[int]] = []
            for lag_index in sorted(supported_lags):
                if contiguous and lag_index != contiguous[-1] + 1:
                    contiguous_groups.append(contiguous)
                    contiguous = []
                contiguous.append(lag_index)
            if contiguous:
                contiguous_groups.append(contiguous)
            longest = max(contiguous_groups, key=len, default=[])
            if len(longest) >= _MIN_SUPPORTED_LAG_BANDS_FOR_RANGE:
                range_lag_band_count = len(longest)
                all_scenes = set.intersection(
                    *(set(correlations_by_lag[index]) for index in longest)
                )
                range_scene_block_count = len(all_scenes)
                if len(all_scenes) >= _MIN_SCENES_FOR_RANGE:
                    full_values = {
                        index: correlations_by_lag[index]
                        for index in longest
                    }
                    candidate_range = _correlation_range_candidate(
                        full_values,
                        edges,
                        min_scenes=_MIN_SCENES_FOR_RANGE,
                    )
                    loo_ranges: list[float] = []
                    if candidate_range is not None:
                        for omitted_scene in sorted(all_scenes):
                            loo = {
                                index: {
                                    scene: value
                                    for scene, value in correlations_by_lag[index].items()
                                    if scene != omitted_scene
                                }
                                for index in longest
                            }
                            loo_range = _correlation_range_candidate(
                                loo,
                                edges,
                                min_scenes=max(2, _MIN_SCENES_FOR_RANGE - 1),
                            )
                            if loo_range is not None:
                                loo_ranges.append(loo_range)
                    leave_one_scene_out_range_count = len(loo_ranges)
                    if candidate_range is not None and len(loo_ranges) == len(all_scenes):
                        center = median(loo_ranges)
                        leave_one_scene_out_range_cv = (
                            math.sqrt(sum((value - center) ** 2 for value in loo_ranges) / len(loo_ranges))
                            / center
                            if center > 0
                            else math.inf
                        )
                        if leave_one_scene_out_range_cv <= _RANGE_MAX_SCENE_BLOCK_CV:
                            candidate_range = center
                            estimate_status = "STABLE_SCENE_BLOCK_CANDIDATE"
                        else:
                            candidate_range = None

        effective_units: float | None = None
        if estimate_status == "STABLE_SCENE_BLOCK_CANDIDATE" and candidate_range:
            effective_units = sum(
                max(1.0, (max(distances) - min(distances)) / candidate_range)
                for distances in component_distances.values()
            )

        for lag_index in range(len(edges) - 1):
            support = band_support.get(
                (metric, lag_index),
                {"pair_count": 0, "run_count": 0, "scene_count": 0},
            )
            gamma_by_scene = scene_semivariances.get((metric, lag_index), {})
            corr_by_scene = scene_correlations.get((metric, lag_index), {})
            normalized_semivariance = (
                sum(gamma_by_scene.values()) / len(gamma_by_scene)
                if gamma_by_scene
                else None
            )
            correlation_proxy = 1.0 - normalized_semivariance if normalized_semivariance is not None else None
            output.append(
                {
                    "metric_name": metric,
                    "lag_lower_m": edges[lag_index],
                    "lag_upper_m": edges[lag_index + 1],
                    "pair_count": support["pair_count"],
                    "run_count": support["run_count"],
                    "scene_count": support["scene_count"],
                    "mean_scene_normalized_semivariance": normalized_semivariance,
                    "mean_scene_correlation_proxy": correlation_proxy,
                    "decorrelation_threshold": _RANGE_DECORRELATION_THRESHOLD,
                    "correlation_range_candidate_m": candidate_range
                    if estimate_status == "STABLE_SCENE_BLOCK_CANDIDATE"
                    else None,
                    "effective_local_unit_count_candidate": effective_units,
                    "estimate_status": estimate_status,
                    "range_scene_block_count": range_scene_block_count,
                    "range_lag_band_count": range_lag_band_count,
                    "leave_one_scene_out_range_count": leave_one_scene_out_range_count,
                    "leave_one_scene_out_range_cv": leave_one_scene_out_range_cv,
                    "minimum_scene_count_for_range": _MIN_SCENES_FOR_RANGE,
                    "minimum_lag_bands_for_range": _MIN_SUPPORTED_LAG_BANDS_FOR_RANGE,
                    "maximum_scene_block_cv_for_range": _RANGE_MAX_SCENE_BLOCK_CV,
                    "cross_prn_colocated_group_count": cross_prn_group_count,
                    "cross_prn_colocated_run_pair_count": cross_prn_run_pair_count,
                    "interpretation": "DESCRIPTIVE_ONLY_NOT_AN_INDEPENDENCE_CLAIM",
                }
            )
    return output
