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
from typing import Any, Mapping, Sequence

from scripts.preprocessing.satellite_geometry import nmea_payload, parse_nmea_datetime


_NMEA_CHECKSUM = re.compile(r"^[0-9A-Fa-f]{2}$")
_EARTH_MEAN_RADIUS_M = 6_371_008.8
_KNOT_TO_METRES_PER_SECOND = 0.5144444444444445


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
