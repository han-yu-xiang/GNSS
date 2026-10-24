#!/usr/bin/env python3
"""Validate and build a separate coordinate-free ephemeris recovery overlay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.channel_modeling.mainline_rinex_ephemeris_geometry import (
    GpsEphemeris,
    parse_gps_lnav_records,
    satellite_elevation_deg,
    select_ephemeris,
)


EXPECTED_SCENES = (
    "F1023_V120_D0121_P2",
    "F1023_v50_D0127_P1",
    "F1023_V70_D0117_P2",
    "F1023_V70_D0117_P4",
    "F1023_V70_D0120_P1",
    "F1023_V70_D0120_P5",
    "F1023_V70_D0120_P7",
    "F1023_V70_D0120_P8",
    "F1023_V70_D0120_P9",
    "F1023_V70_D0122_P1",
    "F1023_V70_D0122_P2",
    "F1023_V80_D0117_P8",
    "F1023_v90_D0117_P7",
)
EXPECTED_WINDOWS = 7847
GEOMETRY_FIELDS = (
    "run_id", "window_id", "scene_id", "prn", "tracking_channel",
    "environment_class", "frozen_elevation_group", "window_utc",
    "elevation_deg", "source_file", "status", "missing_reason",
)
TRAJECTORY_FIELDS = (
    "run_id", "window_id", "scene_id", "prn", "tracking_channel",
    "window_utc", "position_utc", "position_delta_seconds",
    "position_source_path", "position_source_record_id", "latitude_deg",
    "longitude_deg", "position_status", "missing_reason",
)
OVERLAY_FIELDS = (
    "run_id", "window_id", "scene_id", "prn", "tracking_channel",
    "environment_class", "frozen_elevation_group", "window_utc",
    "gsv_original_status", "gsv_original_missing_reason",
    "gsv_source_file", "gsv_measured_elevation_deg",
    "ephemeris_derived_elevation_deg", "elevation_value_deg",
    "elevation_source", "elevation_missing_reason",
    "receiver_position_status", "receiver_position_source", "position_utc", "position_delta_seconds",
    "position_source_file", "receiver_position_record_id",
    "receiver_height_m", "receiver_height_source", "receiver_height_record_id",
    "receiver_height_source_file", "receiver_height_utc", "receiver_height_assumption_m",
    "nav_source_file", "nav_toc_gps_calendar",
    "nav_week", "nav_toe_seconds", "nav_toe_age_seconds",
)
SUMMARY_FIELDS = (
    "summary_scope", "scene_id", "environment_class", "window_count",
    "gsv_measured_count", "ephemeris_derived_count", "elevation_missing_count",
    "derived_gga_height_count", "derived_zero_height_count",
    "position_matched_count", "position_missing_count",
    "joint_elevation_position_count", "joint_coverage_percent",
)
MISSING_FIELDS = ("summary_scope", "scene_id", "environment_class", "reason", "window_count")


def _read_csv(path: Path, required_fields: Sequence[str]) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        missing = set(required_fields) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing required fields {sorted(missing)}: {path}")
        return [dict(row) for row in reader]


def _index_unique(rows: Sequence[Mapping[str, str]], label: str) -> dict[tuple[str, str], Mapping[str, str]]:
    indexed: dict[tuple[str, str], Mapping[str, str]] = {}
    for row in rows:
        key = (row.get("run_id", ""), row.get("window_id", ""))
        if not all(key):
            raise ValueError(f"blank run_id/window_id in {label}")
        if key in indexed:
            raise ValueError(f"duplicate identity in {label}: {key}")
        indexed[key] = row
    return indexed


def _parse_utc(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timezone missing from {field}")
    return parsed.astimezone(timezone.utc)


def _source_ref(value: str, project_root: Path | None) -> str:
    if not value:
        return ""
    path = Path(value)
    if path.is_absolute() and project_root is not None:
        try:
            return path.resolve(strict=False).relative_to(project_root.resolve()).as_posix()
        except ValueError as exc:
            raise ValueError(f"source path is outside the project root: {value}") from exc
    if path.is_absolute():
        raise ValueError("absolute provenance path requires a project root")
    return path.as_posix()


def _nmea_fields(line: str) -> list[str] | None:
    sentence = line.strip()
    if not sentence.startswith("$") or "*" not in sentence:
        return None
    body, checksum_text = sentence[1:].rsplit("*", 1)
    if not re.fullmatch(r"[0-9A-Fa-f]{2}", checksum_text):
        return None
    checksum = 0
    for character in body:
        checksum ^= ord(character)
    if checksum != int(checksum_text, 16):
        return None
    fields = body.split(",")
    if not fields or len(fields[0]) < 3:
        return None
    return fields


def _parse_nmea_time(value: str) -> time | None:
    if not re.fullmatch(r"\d{6}(?:\.\d+)?", value):
        return None
    hour, minute = int(value[:2]), int(value[2:4])
    seconds = float(value[4:])
    whole = int(seconds)
    micros = round((seconds - whole) * 1_000_000)
    if micros == 1_000_000:
        whole += 1
        micros = 0
    if hour > 23 or minute > 59 or whole > 59:
        return None
    return time(hour, minute, whole, micros, tzinfo=timezone.utc)


def _parse_nmea_date(value: str) -> date | None:
    if not re.fullmatch(r"\d{6}", value):
        return None
    day, month, short_year = int(value[:2]), int(value[2:4]), int(value[4:])
    year = 2000 + short_year if short_year < 80 else 1900 + short_year
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _nmea_coordinate(value: str, hemisphere: str, *, latitude: bool) -> float | None:
    if not value:
        return None
    try:
        packed = float(value)
    except ValueError:
        return None
    if not math.isfinite(packed) or hemisphere not in ({"N", "S"} if latitude else {"E", "W"}):
        return None
    degrees = math.floor(packed / 100.0)
    minutes = packed - degrees * 100.0
    limit = 90 if latitude else 180
    if not 0 <= minutes < 60 or degrees > limit or (degrees == limit and minutes != 0):
        return None
    result = degrees + minutes / 60.0
    if hemisphere in {"S", "W"}:
        result = -result
    return result


def _distance_m(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    radius_m = 6_371_000.0
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    haversine = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    return 2 * radius_m * math.asin(min(1.0, math.sqrt(haversine)))


def build_exact_gga_height_index(
    geometry_rows: Sequence[Mapping[str, str]],
    trajectory_rows: Sequence[Mapping[str, str]],
    nmea_text_by_scene: Mapping[str, str],
    *,
    nmea_source_by_scene: Mapping[str, str] | None = None,
    max_position_delta_m: float = 1.0,
) -> tuple[dict[tuple[str, str], dict[str, object]], dict[str, dict[str, int]]]:
    """Index exact-time, valid GGA ellipsoidal heights after position cross-check."""
    if not math.isfinite(max_position_delta_m) or max_position_delta_m < 0:
        raise ValueError("invalid maximum GGA/trajectory position difference")
    geometry = _index_unique(geometry_rows, "geometry overlay")
    trajectory = _index_unique(trajectory_rows, "trajectory overlay")
    if geometry.keys() != trajectory.keys():
        raise ValueError("geometry and trajectory overlays must have the same identity set")
    if set(nmea_text_by_scene) - {row.get("scene_id", "") for row in geometry.values()}:
        raise ValueError("NMEA source contains a scene outside the geometry overlay")

    windows_by_scene_tod: dict[tuple[str, time], list[tuple[tuple[str, str], datetime, datetime]]] = defaultdict(list)
    for key, row in geometry.items():
        scene = row.get("scene_id", "")
        instant = _parse_utc(row.get("window_utc", ""), "window_utc")
        position_instant: datetime | None = None
        if trajectory[key].get("position_status") == "POSITION_MATCHED":
            position_instant = _parse_utc(trajectory[key].get("position_utc", ""), "position_utc")
            windows_by_scene_tod[(scene, position_instant.timetz())].append((key, instant, position_instant))
        for field in ("scene_id", "window_utc"):
            if row.get(field, "") != trajectory[key].get(field, ""):
                raise ValueError(f"{field} mismatch for GGA identity {key}")

    sources = nmea_source_by_scene or {}
    counts: dict[str, dict[str, int]] = {}
    output: dict[tuple[str, str], dict[str, object]] = {}
    for scene, text in nmea_text_by_scene.items():
        stats = Counter()
        gga_by_instant: dict[datetime, list[dict[str, object]]] = defaultdict(list)
        active_rmc_utc: datetime | None = None
        valid_rmc_dates: set[date] = set()
        source_file = sources.get(scene, f"{scene}_trajectory.nmea")
        for line_number, line in enumerate(text.splitlines(), start=1):
            fields = _nmea_fields(line)
            if fields is None:
                if line.strip():
                    stats["invalid_checksum_or_sentence_count"] += 1
                continue
            sentence_type = fields[0][-3:].upper()
            if sentence_type == "RMC":
                if len(fields) > 9 and fields[2] == "A":
                    parsed_date = _parse_nmea_date(fields[9])
                    parsed_time = _parse_nmea_time(fields[1])
                    if parsed_date is not None and parsed_time is not None:
                        active_rmc_utc = datetime.combine(
                            parsed_date, parsed_time.replace(tzinfo=None), tzinfo=timezone.utc
                        )
                        valid_rmc_dates.add(parsed_date)
                continue
            if sentence_type != "GGA":
                continue
            if len(fields) < 13:
                stats["invalid_gga_count"] += 1
                continue
            tod = _parse_nmea_time(fields[1])
            latitude = _nmea_coordinate(fields[2], fields[3], latitude=True)
            longitude = _nmea_coordinate(fields[4], fields[5], latitude=False)
            try:
                quality = int(fields[6])
                satellites = int(fields[7])
                hdop = float(fields[8])
                altitude = float(fields[9])
                geoid = float(fields[11])
            except ValueError:
                stats["invalid_gga_count"] += 1
                continue
            if (
                tod is None
                or latitude is None
                or longitude is None
                or quality <= 0
                or satellites < 4
                or not math.isfinite(hdop)
                or hdop < 0
                or fields[10] != "M"
                or fields[12] != "M"
                or not math.isfinite(altitude)
                or not math.isfinite(geoid)
            ):
                stats["invalid_gga_count"] += 1
                continue
            height = altitude + geoid
            if not math.isfinite(height) or abs(height) > 10_000:
                stats["invalid_gga_count"] += 1
                continue
            if active_rmc_utc is None:
                stats["gga_without_valid_rmc_date_count"] += 1
                continue
            candidates = [
                datetime.combine(active_rmc_utc.date() + timedelta(days=offset), tod.replace(tzinfo=None), tzinfo=timezone.utc)
                for offset in (-1, 0, 1)
            ]
            gga_utc = min(candidates, key=lambda candidate: abs((candidate - active_rmc_utc).total_seconds()))
            gga_by_instant[gga_utc].append(
                {
                    "latitude_deg": latitude,
                    "longitude_deg": longitude,
                    "height_m": height,
                    "quality": quality,
                    "satellites": satellites,
                    "hdop": hdop,
                    "line_number": line_number,
                    "tod": tod,
                    "gga_utc": gga_utc,
                }
            )
            stats["valid_gga_record_count"] += 1

        stats["valid_rmc_date_count"] = len(valid_rmc_dates)
        for gga_records in gga_by_instant.values():
            first = gga_records[0]
            signature = (
                first["latitude_deg"], first["longitude_deg"], first["height_m"],
                first["quality"], first["satellites"], first["hdop"],
            )
            if any(
                (
                    record["latitude_deg"], record["longitude_deg"], record["height_m"],
                    record["quality"], record["satellites"], record["hdop"],
                ) != signature
                for record in gga_records[1:]
            ):
                stats["conflicting_exact_time_gga_count"] += 1
                continue
            gga_utc = first["gga_utc"]
            tod = first["tod"]
            for key, window_utc, position_utc in windows_by_scene_tod.get((scene, tod), ()):
                if position_utc != gga_utc:
                    continue
                stats["exact_position_fix_gga_candidate_count"] += 1
                trajectory_row = trajectory[key]
                if trajectory_row.get("position_status") != "POSITION_MATCHED":
                    stats["gga_position_unavailable_count"] += 1
                    continue
                try:
                    trajectory_lat = float(trajectory_row["latitude_deg"])
                    trajectory_lon = float(trajectory_row["longitude_deg"])
                except (KeyError, ValueError):
                    stats["gga_position_unavailable_count"] += 1
                    continue
                position_delta_m = _distance_m(
                    float(first["latitude_deg"]),
                    float(first["longitude_deg"]),
                    trajectory_lat,
                    trajectory_lon,
                )
                if not math.isfinite(position_delta_m) or position_delta_m > max_position_delta_m:
                    stats["gga_position_mismatch_count"] += 1
                    continue
                if key in output:
                    prior = output[key]
                    if prior["height_m"] != first["height_m"]:
                        output.pop(key)
                        stats["conflicting_identity_gga_count"] += 1
                    continue
                output[key] = {
                    "scene_id": scene,
                    "window_utc": window_utc.isoformat().replace("+00:00", "Z"),
                    "position_utc": position_utc.isoformat().replace("+00:00", "Z"),
                    "height_m": float(first["height_m"]),
                    "quality": int(first["quality"]),
                    "satellites": int(first["satellites"]),
                    "hdop": float(first["hdop"]),
                    "record_id": f"{Path(source_file).name}:{int(first['line_number']):06d}",
                    "source_file": source_file,
                    "position_delta_m": position_delta_m,
                }
                stats["exact_gga_position_consistent_identity_count"] += 1
        counts[scene] = dict(stats)
    return output, counts


def build_recovery_overlay(
    geometry_rows: Sequence[Mapping[str, str]],
    trajectory_rows: Sequence[Mapping[str, str]],
    ephemerides_by_scene: Mapping[str, Sequence[GpsEphemeris]],
    *,
    nav_source_by_scene: Mapping[str, str] | None = None,
    receiver_height_by_identity: Mapping[tuple[str, str], Mapping[str, object]] | None = None,
    project_root: Path | None = None,
    gps_utc_offset_seconds: float = 18.0,
) -> list[dict[str, str]]:
    """Join old overlays by exact identity and add a distinct derived layer."""
    geometry = _index_unique(geometry_rows, "geometry overlay")
    trajectory = _index_unique(trajectory_rows, "trajectory overlay")
    if geometry.keys() != trajectory.keys():
        raise ValueError("geometry and trajectory overlays must have the same identity set")
    if set(ephemerides_by_scene) - {row["scene_id"] for row in geometry.values()}:
        raise ValueError("ephemeris source contains a scene outside the geometry overlay")

    nav_sources = nav_source_by_scene or {}
    receiver_heights = receiver_height_by_identity or {}
    if set(receiver_heights) - set(geometry):
        raise ValueError("GGA height source contains an identity outside the geometry overlay")
    computed_cache: dict[tuple[object, ...], float] = {}
    selected_cache: dict[tuple[str, str, datetime], GpsEphemeris | None] = {}
    output: list[dict[str, str]] = []
    for key, geom in geometry.items():
        traj = trajectory[key]
        for field in ("scene_id", "prn", "tracking_channel", "window_utc"):
            if geom.get(field, "") != traj.get(field, ""):
                raise ValueError(f"{field} mismatch for identity {key}")
        scene = geom["scene_id"]
        position_status = traj.get("position_status", "")
        if position_status not in {"POSITION_MATCHED", "POSITION_MISSING", "MISSING", ""}:
            raise ValueError(f"unknown position_status for identity {key}: {position_status}")
        if geom.get("status") not in {"GSV_MATCHED", "MISSING"}:
            raise ValueError(f"unknown geometry status for identity {key}: {geom.get('status')}")

        source = "MISSING"
        measured = ""
        derived = ""
        value = ""
        missing_reason = ""
        nav_toc = ""
        nav_week = ""
        nav_toe = ""
        nav_age = ""
        receiver_height = ""
        receiver_height_source = ""
        receiver_height_record_id = ""
        receiver_height_source_file = ""
        receiver_height_utc = ""
        receiver_height_assumption = ""
        if geom["status"] == "GSV_MATCHED":
            source = "GSV_MEASURED"
            measured = geom.get("elevation_deg", "")
            if not measured:
                raise ValueError(f"GSV_MATCHED row has no measured elevation: {key}")
            float(measured)
            value = measured
        elif position_status != "POSITION_MATCHED":
            missing_reason = "NO_VALID_POSITION"
        else:
            try:
                latitude = float(traj["latitude_deg"])
                longitude = float(traj["longitude_deg"])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"matched position has invalid coordinates for {key}") from exc
            if not math.isfinite(latitude) or not math.isfinite(longitude):
                raise ValueError(f"matched position has non-finite coordinates for {key}")
            position_utc = _parse_utc(traj.get("position_utc", ""), "position_utc")
            observation_utc = _parse_utc(geom.get("window_utc", ""), "window_utc")
            selection_key = (scene, geom["prn"], observation_utc)
            if selection_key not in selected_cache:
                selected_cache[selection_key] = select_ephemeris(
                    ephemerides_by_scene.get(scene, ()),
                    geom["prn"],
                    observation_utc,
                    gps_utc_offset_seconds=gps_utc_offset_seconds,
                )
            ephemeris = selected_cache[selection_key]
            if ephemeris is None:
                missing_reason = "NO_HEALTHY_EPHEMERIS_FOR_PRN_WITHIN_2H"
            else:
                gga_height = receiver_heights.get(key)
                if gga_height is not None:
                    if gga_height.get("scene_id") != scene:
                        raise ValueError(f"GGA scene mismatch for identity {key}")
                    if _parse_utc(str(gga_height.get("window_utc", "")), "GGA window_utc") != observation_utc:
                        raise ValueError(f"GGA timestamp mismatch for identity {key}")
                    if _parse_utc(str(gga_height.get("position_utc", "")), "GGA position_utc") != position_utc:
                        raise ValueError(f"GGA does not match the validated position epoch for identity {key}")
                    if float(gga_height.get("position_delta_m", math.inf)) > 1.0:
                        raise ValueError(f"GGA position cross-check failed for identity {key}")
                    height_m = float(gga_height["height_m"])
                    if not math.isfinite(height_m) or abs(height_m) > 10_000:
                        raise ValueError(f"invalid GGA ellipsoidal height for identity {key}")
                    receiver_height_source = "GGA_ELLIPSOIDAL_HEIGHT"
                    receiver_height_record_id = str(gga_height["record_id"])
                    receiver_height_source_file = _source_ref(str(gga_height["source_file"]), project_root)
                    receiver_height_utc = str(gga_height["position_utc"])
                    receiver_height = f"{height_m:.6f}"
                else:
                    height_m = 0.0
                    receiver_height_source = "ZERO_HEIGHT_ASSUMPTION"
                    receiver_height_utc = ""
                    receiver_height_assumption = "0.0"
                    receiver_height = f"{height_m:.6f}"
                cache_key = (scene, geom["prn"], observation_utc, latitude, longitude, height_m)
                if cache_key not in computed_cache:
                    computed_cache[cache_key] = satellite_elevation_deg(
                        ephemeris,
                        observation_utc,
                        latitude,
                        longitude,
                        height_m=height_m,
                        gps_utc_offset_seconds=gps_utc_offset_seconds,
                    )
                derived = f"{computed_cache[cache_key]:.9f}"
                value = derived
                source = "EPHEMERIS_DERIVED"
                nav_toc = ephemeris.toc_gps_calendar.isoformat()
                nav_week = str(ephemeris.week_number)
                nav_toe = f"{ephemeris.toe_seconds:.3f}"
                toe_absolute = ephemeris.week_number * 604800 + ephemeris.toe_seconds
                gps_absolute = (observation_utc + timedelta(seconds=gps_utc_offset_seconds) - datetime(1980, 1, 6, tzinfo=timezone.utc)).total_seconds()
                age = gps_absolute - toe_absolute
                if age > 302400:
                    age -= 604800
                elif age < -302400:
                    age += 604800
                nav_age = f"{abs(age):.3f}"

        output.append(
            {
                "run_id": key[0],
                "window_id": key[1],
                "scene_id": scene,
                "prn": geom["prn"],
                "tracking_channel": geom["tracking_channel"],
                "environment_class": geom.get("environment_class", ""),
                "frozen_elevation_group": geom.get("frozen_elevation_group", ""),
                "window_utc": geom["window_utc"],
                "gsv_original_status": geom["status"],
                "gsv_original_missing_reason": geom.get("missing_reason", ""),
                "gsv_source_file": _source_ref(geom.get("source_file", ""), project_root),
                "gsv_measured_elevation_deg": measured,
                "ephemeris_derived_elevation_deg": derived,
                "elevation_value_deg": value,
                "elevation_source": source,
                "elevation_missing_reason": missing_reason,
                "receiver_position_status": position_status or "MISSING",
                "receiver_position_source": traj.get(
                    "position_source",
                    "EXISTING_NMEA" if position_status == "POSITION_MATCHED" else "",
                ),
                "position_utc": traj.get("position_utc", ""),
                "position_delta_seconds": traj.get("position_delta_seconds", ""),
                "position_source_file": _source_ref(traj.get("position_source_path", ""), project_root),
                "receiver_position_record_id": traj.get("position_source_record_id", ""),
                "receiver_height_m": receiver_height,
                "receiver_height_source": receiver_height_source,
                "receiver_height_record_id": receiver_height_record_id,
                "receiver_height_source_file": receiver_height_source_file,
                "receiver_height_utc": receiver_height_utc,
                "receiver_height_assumption_m": receiver_height_assumption,
                "nav_source_file": nav_sources.get(scene, "") if source == "EPHEMERIS_DERIVED" else "",
                "nav_toc_gps_calendar": nav_toc,
                "nav_week": nav_week,
                "nav_toe_seconds": nav_toe,
                "nav_toe_age_seconds": nav_age,
            }
        )
    return output


def summarize_recovery(rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    """Summarize per-scene, per-environment, and total support."""
    groups: dict[tuple[str, str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        groups[("TOTAL", "", "")].append(row)
        groups[("ENVIRONMENT", "", row.get("environment_class", ""))].append(row)
        groups[("SCENE", row.get("scene_id", ""), row.get("environment_class", ""))].append(row)

    output: list[dict[str, str]] = []
    for (scope, scene, environment), group in sorted(groups.items()):
        total = len(group)
        measured = sum(row["elevation_source"] == "GSV_MEASURED" for row in group)
        derived = sum(row["elevation_source"] == "EPHEMERIS_DERIVED" for row in group)
        missing = sum(row["elevation_source"] == "MISSING" for row in group)
        derived_gga_height = sum(
            row["elevation_source"] == "EPHEMERIS_DERIVED"
            and row.get("receiver_height_source") == "GGA_ELLIPSOIDAL_HEIGHT"
            for row in group
        )
        derived_zero_height = sum(
            row["elevation_source"] == "EPHEMERIS_DERIVED"
            and row.get("receiver_height_source") == "ZERO_HEIGHT_ASSUMPTION"
            for row in group
        )
        position = sum(row["receiver_position_status"] == "POSITION_MATCHED" for row in group)
        joint = sum(
            row["elevation_source"] != "MISSING"
            and row["receiver_position_status"] == "POSITION_MATCHED"
            for row in group
        )
        output.append(
            {
                "summary_scope": scope,
                "scene_id": scene,
                "environment_class": environment,
                "window_count": str(total),
                "gsv_measured_count": str(measured),
                "ephemeris_derived_count": str(derived),
                "elevation_missing_count": str(missing),
                "derived_gga_height_count": str(derived_gga_height),
                "derived_zero_height_count": str(derived_zero_height),
                "position_matched_count": str(position),
                "position_missing_count": str(total - position),
                "joint_elevation_position_count": str(joint),
                "joint_coverage_percent": f"{100 * joint / total:.6f}" if total else "0.000000",
            }
        )
    return output


def summarize_missing_reasons(rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    counts: Counter[tuple[str, str, str, str]] = Counter()
    for row in rows:
        if row["elevation_source"] == "MISSING":
            counts[("TOTAL", "", "", row["elevation_missing_reason"])] += 1
            counts[("SCENE", row["scene_id"], row["environment_class"], row["elevation_missing_reason"])] += 1
    return [
        {
            "summary_scope": scope,
            "scene_id": scene,
            "environment_class": environment,
            "reason": reason,
            "window_count": str(count),
        }
        for (scope, scene, environment, reason), count in sorted(counts.items())
    ]


def validate_gsv_pilot(
    geometry_rows: Sequence[Mapping[str, str]],
    trajectory_rows: Sequence[Mapping[str, str]],
    records: Sequence[GpsEphemeris],
    scene_id: str,
    *,
    receiver_height_by_identity: Mapping[tuple[str, str], Mapping[str, object]] | None = None,
    gps_utc_offset_seconds: float = 18.0,
) -> dict[str, object]:
    geometry = _index_unique(geometry_rows, "geometry overlay")
    trajectory = _index_unique(trajectory_rows, "trajectory overlay")
    if geometry.keys() != trajectory.keys():
        raise ValueError("geometry and trajectory overlays must have the same identity set")
    candidates = []
    errors: list[float] = []
    exact_gga_height_count = 0
    for key, row in geometry.items():
        if row.get("scene_id") != scene_id or row.get("status") != "GSV_MATCHED":
            continue
        pos = trajectory[key]
        if pos.get("position_status") != "POSITION_MATCHED":
            continue
        for field in ("scene_id", "prn", "tracking_channel", "window_utc"):
            if row.get(field, "") != pos.get(field, ""):
                raise ValueError(f"{field} mismatch for pilot identity {key}")
        candidates.append(key)
        eph = select_ephemeris(
            records,
            row["prn"],
            _parse_utc(row["window_utc"], "window_utc"),
            gps_utc_offset_seconds=gps_utc_offset_seconds,
        )
        if eph is None:
            continue
        gga_height = (receiver_height_by_identity or {}).get(key)
        if gga_height is not None:
            if gga_height.get("scene_id") != scene_id or _parse_utc(
                str(gga_height.get("window_utc", "")), "GGA window_utc"
            ) != _parse_utc(row["window_utc"], "window_utc"):
                raise ValueError(f"GGA identity/time mismatch for pilot identity {key}")
            if _parse_utc(str(gga_height.get("position_utc", "")), "GGA position_utc") != _parse_utc(
                pos.get("position_utc", ""), "position_utc"
            ):
                raise ValueError(f"GGA position epoch mismatch for pilot identity {key}")
            if float(gga_height.get("position_delta_m", math.inf)) > 1.0:
                raise ValueError(f"GGA position cross-check failed for pilot identity {key}")
            height_m = float(gga_height["height_m"])
            exact_gga_height_count += 1
        else:
            height_m = 0.0
        elevation = satellite_elevation_deg(
            eph,
            _parse_utc(row["window_utc"], "window_utc"),
            float(pos["latitude_deg"]),
            float(pos["longitude_deg"]),
            height_m=height_m,
            gps_utc_offset_seconds=gps_utc_offset_seconds,
        )
        errors.append(elevation - float(row["elevation_deg"]))

    if len(errors) != len(candidates):
        raise ValueError(
            f"pilot ephemeris coverage incomplete: {len(errors)}/{len(candidates)} GSV+position rows"
        )
    if not errors:
        raise ValueError("pilot has no eligible GSV+position comparison rows")
    absolute = sorted(abs(value) for value in errors)
    p95_index = max(0, math.ceil(0.95 * len(absolute)) - 1)
    result: dict[str, object] = {
        "scene_id": scene_id,
        "comparison_count": len(errors),
        "signed_bias_deg": statistics.fmean(errors),
        "mae_deg": statistics.fmean(absolute),
        "p95_absolute_error_deg": absolute[p95_index],
        "max_absolute_error_deg": max(absolute),
        "within_1_degree_count": sum(value <= 1.0 for value in absolute),
        "comparison_scope": "existing GSV-measured windows with existing validated same-scene position",
        "exact_gga_height_count": exact_gga_height_count,
        "zero_height_assumption_count": len(errors) - exact_gga_height_count,
    }
    result["passed"] = result["mae_deg"] < 0.5 and result["max_absolute_error_deg"] < 1.0
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_scene_navigation(project_root: Path, scene_id: str) -> tuple[Path, list[GpsEphemeris]]:
    nav_dir = project_root / "scenes" / scene_id / "navigation" / "rinex_nav"
    candidates = sorted(nav_dir.glob("*.26N")) if nav_dir.is_dir() else []
    if len(candidates) != 1:
        raise ValueError(f"expected exactly one RINEX NAV in {nav_dir}, found {len(candidates)}")
    nav_path = candidates[0]
    records = parse_gps_lnav_records(nav_path.read_text(encoding="ascii", errors="strict"))
    if not records:
        raise ValueError(f"no GPS LNAV records parsed from {nav_path}")
    return nav_path, records


def _load_scene_nmea(project_root: Path, scene_id: str) -> tuple[Path, str]:
    nmea_dir = project_root / "scenes" / scene_id / "gnss_sdr" / "nmea"
    candidates = sorted(nmea_dir.glob("*trajectory.nmea")) if nmea_dir.is_dir() else []
    if len(candidates) != 1:
        raise ValueError(f"expected exactly one primary trajectory NMEA file in {nmea_dir}, found {len(candidates)}")
    path = candidates[0]
    return path, path.read_text(encoding="ascii", errors="strict")


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_recovery_outputs(
    output_dir: Path,
    overlay: Sequence[Mapping[str, str]],
    summary: Sequence[Mapping[str, str]],
    audit: Mapping[str, object],
) -> None:
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(output_dir / "geometry_ephemeris_recovery_overlay.csv", OVERLAY_FIELDS, overlay)
    _write_csv(output_dir / "geometry_ephemeris_recovery_by_scene.csv", SUMMARY_FIELDS, summary)
    _write_csv(output_dir / "geometry_ephemeris_recovery_missing_reasons.csv", MISSING_FIELDS, summarize_missing_reasons(overlay))
    with (output_dir / "geometry_ephemeris_recovery_audit.json").open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _load_overlays(geometry_path: Path, trajectory_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return _read_csv(geometry_path, GEOMETRY_FIELDS), _read_csv(trajectory_path, TRAJECTORY_FIELDS)


def _pilot(
    project_root: Path,
    geometry_path: Path,
    trajectory_path: Path,
    scene_id: str,
) -> dict[str, object]:
    if scene_id not in EXPECTED_SCENES:
        raise ValueError(f"pilot scene is outside the frozen 13-scene cohort: {scene_id}")
    geometry, trajectory = _load_overlays(geometry_path, trajectory_path)
    _, records = _load_scene_navigation(project_root, scene_id)
    nmea_path, nmea_text = _load_scene_nmea(project_root, scene_id)
    gga_by_identity, gga_counts = build_exact_gga_height_index(
        geometry,
        trajectory,
        {scene_id: nmea_text},
        nmea_source_by_scene={
            scene_id: nmea_path.resolve().relative_to(project_root.resolve()).as_posix()
        },
    )
    result = validate_gsv_pilot(
        geometry,
        trajectory,
        records,
        scene_id,
        receiver_height_by_identity=gga_by_identity,
    )
    result["nav_records"] = len(records)
    nav_path, _ = _load_scene_navigation(project_root, scene_id)
    result["nav_file_sha256"] = _sha256(nav_path)
    result["gga_height_audit"] = gga_counts.get(scene_id, {})
    result["nmea_file_sha256"] = _sha256(nmea_path)
    return result


def _run_full(
    project_root: Path,
    geometry_path: Path,
    trajectory_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    geometry, trajectory = _load_overlays(geometry_path, trajectory_path)
    geometry_index = _index_unique(geometry, "geometry overlay")
    if len(geometry_index) != EXPECTED_WINDOWS:
        raise ValueError(f"expected {EXPECTED_WINDOWS} Stage2 windows, found {len(geometry_index)}")
    scenes = {row["scene_id"] for row in geometry}
    if scenes != set(EXPECTED_SCENES):
        raise ValueError(f"scene set differs from frozen cohort: {sorted(scenes ^ set(EXPECTED_SCENES))}")

    ephemerides_by_scene: dict[str, list[GpsEphemeris]] = {}
    nav_source_by_scene: dict[str, str] = {}
    nav_audit: dict[str, object] = {}
    nmea_text_by_scene: dict[str, str] = {}
    nmea_source_by_scene: dict[str, str] = {}
    nmea_path_by_scene: dict[str, Path] = {}
    for scene in sorted(scenes):
        nav_path, records = _load_scene_navigation(project_root, scene)
        nmea_path, nmea_text = _load_scene_nmea(project_root, scene)
        ephemerides_by_scene[scene] = records
        relative = nav_path.resolve().relative_to(project_root.resolve()).as_posix()
        nav_source_by_scene[scene] = relative
        nav_audit[scene] = {
            "relative_path": relative,
            "sha256": _sha256(nav_path),
            "size_bytes": nav_path.stat().st_size,
            "gps_lnav_record_count": len(records),
            "prns": sorted({record.prn for record in records}),
        }
        nmea_relative = nmea_path.resolve().relative_to(project_root.resolve()).as_posix()
        nmea_text_by_scene[scene] = nmea_text
        nmea_source_by_scene[scene] = nmea_relative
        nmea_path_by_scene[scene] = nmea_path
        nav_audit[scene]["nmea_trajectory"] = {
            "relative_path": nmea_relative,
            "sha256": _sha256(nmea_path),
            "size_bytes": nmea_path.stat().st_size,
        }
    gga_by_identity, gga_audit = build_exact_gga_height_index(
        geometry,
        trajectory,
        nmea_text_by_scene,
        nmea_source_by_scene=nmea_source_by_scene,
    )
    overlay = build_recovery_overlay(
        geometry,
        trajectory,
        ephemerides_by_scene,
        nav_source_by_scene=nav_source_by_scene,
        receiver_height_by_identity=gga_by_identity,
        project_root=project_root,
    )
    if len(overlay) != EXPECTED_WINDOWS:
        raise ValueError(f"recovery overlay row count mismatch: {len(overlay)}")
    overlay_keys = [(row["run_id"], row["window_id"]) for row in overlay]
    if len(set(overlay_keys)) != EXPECTED_WINDOWS or set(overlay_keys) != set(geometry_index):
        raise ValueError("recovery overlay identities do not reconcile exactly to the old geometry overlay")
    if sum(row["elevation_source"] == "GSV_MEASURED" for row in overlay) != 5128:
        raise ValueError("original GSV measured count changed from the audited baseline of 5,128")
    summary = summarize_recovery(overlay)
    total = next(row for row in summary if row["summary_scope"] == "TOTAL")
    input_files = {
        str(path.resolve().relative_to(project_root.resolve()).as_posix()): {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in (geometry_path, trajectory_path)
    }
    input_files.update(
        {
            nmea_source_by_scene[scene]: {
                "sha256": _sha256(nmea_path_by_scene[scene]),
                "size_bytes": nmea_path_by_scene[scene].stat().st_size,
            }
            for scene in sorted(scenes)
        }
    )
    audit = {
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "method": "GPS LNAV broadcast orbit propagated to signal transmit time, Earth-rotation corrected, topocentric elevation from existing matched position",
        "elevation_sources": {"measured": "GSV_MEASURED", "derived": "EPHEMERIS_DERIVED"},
        "gps_utc_offset_seconds": 18,
        "rinex_navigation_toc_time_scale": "GPS",
        "maximum_ephemeris_toe_age_seconds": 7200,
        "receiver_height_policy": "Exact-time valid same-scene GGA ellipsoidal height (MSL altitude + geoid separation), cross-checked within 1 m of the matched trajectory position; otherwise an explicit zero-height assumption",
        "gga_position_time_join": "Exact NMEA GGA UTC equals the existing trajectory position_utc; Stage2 window linkage is inherited from the existing (run_id, window_id) trajectory overlay and its original position-time tolerance",
        "gga_trajectory_position_max_delta_m": 1.0,
        "old_geometry_overlay": str(geometry_path.resolve().relative_to(project_root.resolve()).as_posix()),
        "old_trajectory_overlay": str(trajectory_path.resolve().relative_to(project_root.resolve()).as_posix()),
        "input_files": input_files,
        "rinex_navigation_by_scene": nav_audit,
        "exact_gga_height_by_scene": gga_audit,
        "derived_rows_using_exact_gga_height": sum(
            row["elevation_source"] == "EPHEMERIS_DERIVED"
            and row["receiver_height_source"] == "GGA_ELLIPSOIDAL_HEIGHT"
            for row in overlay
        ),
        "derived_rows_using_zero_height_assumption": sum(
            row["elevation_source"] == "EPHEMERIS_DERIVED"
            and row["receiver_height_source"] == "ZERO_HEIGHT_ASSUMPTION"
            for row in overlay
        ),
        "window_identity_count": len(overlay),
        "unique_run_window_identity_count": len(set(overlay_keys)),
        "gsv_measured_count": int(total["gsv_measured_count"]),
        "ephemeris_derived_count": int(total["ephemeris_derived_count"]),
        "elevation_missing_count": int(total["elevation_missing_count"]),
        "position_matched_count": int(total["position_matched_count"]),
        "joint_elevation_position_count": int(total["joint_elevation_position_count"]),
        "coordinate_or_raw_nmea_content_in_audit": False,
        "stage2_ledger_modified": False,
        "task5_cir_modified": False,
        "gnss_sdr_rerun": False,
    }
    write_recovery_outputs(output_dir, overlay, summary, audit)
    return audit


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--geometry-overlay", type=Path, required=True)
    parser.add_argument("--trajectory-overlay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--validate-scene", help="run only the GSV-vs-ephemeris pilot for one frozen scene")
    args = parser.parse_args(argv)
    try:
        if args.validate_scene:
            result = _pilot(
                args.project_root.resolve(),
                args.geometry_overlay.resolve(),
                args.trajectory_overlay.resolve(),
                args.validate_scene,
            )
            print(json.dumps(result, sort_keys=True))
            return 0 if result["passed"] else 2
        if args.output_dir is None:
            raise ValueError("--output-dir is required for the full overlay")
        result = _run_full(
            args.project_root.resolve(),
            args.geometry_overlay.resolve(),
            args.trajectory_overlay.resolve(),
            args.output_dir.resolve(),
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
