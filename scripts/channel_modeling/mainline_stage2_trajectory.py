"""Validated scene-local route fixes and continuity components for Task 7.

This module only parses small, checksum-validated NMEA RMC records and
transforms in-memory fix rows.  It does not modify source trajectories or
read SAGE/CIR payloads.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
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

    fixes: list[dict[str, Any]] = []
    seen_utc: set[datetime] = set()

    for path_value in nmea_paths:
        path = Path(path_value).resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"NMEA source is not a regular file: {path}")
        last_file_utc: datetime | None = None
        with path.open("r", encoding="ascii", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                fields = _checksum_valid_rmc_line(raw_line)
                if fields is None or not fields or fields[0].upper() not in {"GPRMC", "GNRMC"}:
                    continue
                if len(fields) < 10 or fields[2].strip().upper() != "A":
                    continue
                try:
                    utc_time = parse_nmea_datetime(fields[1].strip(), fields[9].strip())
                    latitude_deg = _parse_coordinate(
                        fields[3].strip(), fields[4].strip(), latitude=True
                    )
                    longitude_deg = _parse_coordinate(
                        fields[5].strip(), fields[6].strip(), latitude=False
                    )
                except (IndexError, TypeError, ValueError, OverflowError):
                    continue

                if last_file_utc is not None and utc_time <= last_file_utc:
                    continue
                last_file_utc = utc_time
                if utc_time in seen_utc:
                    continue
                seen_utc.add(utc_time)

                speed_knots = _optional_float(fields[7], minimum=0.0, maximum=1_000.0)
                course_deg = _optional_float(fields[8], minimum=0.0, maximum=360.0)
                fixes.append(
                    {
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
                    }
                )

    fixes.sort(
        key=lambda fix: (
            fix["utc_time"],
            fix["source_path"].casefold(),
            fix["source_line_number"],
        )
    )
    return fixes


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

    A duplicate/out-of-order timestamp, gap above ``max_gap_seconds`` or
    implied speed above ``jump_speed_mps`` begins a fresh component. Rejected
    edges are recorded as candidates/reasons but are excluded from cumulative
    distance. Cumulative distance resets to zero at every component break.
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

    Position is assigned only by nearest-neighbor. No interpolation is used.
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
