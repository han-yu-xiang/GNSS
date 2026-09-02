#!/usr/bin/env python3
"""Build a versioned, read-only modeling-context alignment partition.

The existing event/path audit partition intentionally keeps event geometry
deferred.  This module consumes that immutable partition plus the existing
NMEA/RINEX/geometry and scene-annotation layers and writes a new context
overlay.  It never opens raw IQ and never changes a SAGE result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable


ALIGNMENT_ID = "alignment_20260825_tow_geometry_scene_v1"
ALIGNMENT_VERSION = "sage-event-context-alignment-v1"
SCHEMA_VERSION = "sage-event-path-db-v1"
SOURCE_PARTITION_ID = "ingestion_20260825_event_path_v1"
GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
GPS_WEEK_SECONDS = 604800.0
GPS_UTC_LEAP_SECONDS = 18
MAX_GEOMETRY_DELTA_SECONDS = 5.0
SCENE_METADATA_REL = Path(
    "dataset_generation_logs/production_planning_10mhz_20260812/"
    "scene_metadata_10MHz.csv"
)

EVENT_CONTEXT_FIELDS = [
    "event_id",
    "run_id",
    "scene_id",
    "prn",
    "center_window_id",
    "recording_time_s",
    "tow_s",
    "event_utc",
    "elevation_deg",
    "azimuth_deg",
    "tracking_cn0_db_hz",
    "nmea_snr_db_hz",
    "vehicle_speed_kmh",
    "speed_source",
    "geometry_join_status",
    "geometry_join_valid",
    "geometry_join_method",
    "geometry_source_utc",
    "geometry_time_delta_s",
    "time_alignment_id",
    "missing_reason",
    "observation_quality",
    "derivation_version",
    "context_alignment_version",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field, "") for field in fields})


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def iso_utc(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def format_float(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return ""
    return f"{value:.9f}".rstrip("0").rstrip(".")


def gps_tow_to_utc(
    gps_week: int,
    tow_s: float,
    *,
    leap_seconds: int = GPS_UTC_LEAP_SECONDS,
) -> datetime:
    """Convert GPS week/TOW to UTC with the frozen project offset."""

    if gps_week < 0 or not math.isfinite(tow_s) or not 0 <= tow_s < GPS_WEEK_SECONDS:
        raise ValueError("invalid GPS week or TOW")
    return GPS_EPOCH + timedelta(
        seconds=gps_week * GPS_WEEK_SECONDS + tow_s - leap_seconds
    )


def parse_nmea_rmc_datetime(line: str) -> datetime | None:
    fields = line.strip().split(",")
    if len(fields) < 10 or fields[0].split("*")[0] not in {"$GPRMC", "$GNRMC"}:
        return None
    if fields[2] != "A":
        return None
    time_text = fields[1].split("*")[0]
    date_text = fields[9].split("*")[0]
    if len(time_text) < 6 or len(date_text) != 6:
        return None
    try:
        hours = int(time_text[0:2])
        minutes = int(time_text[2:4])
        seconds = float(time_text[4:])
        day = int(date_text[0:2])
        month = int(date_text[2:4])
        year = 2000 + int(date_text[4:6])
        base = datetime(year, month, day, hours, minutes, tzinfo=timezone.utc)
    except ValueError:
        return None
    if not math.isfinite(seconds) or not 0 <= seconds < 60:
        return None
    return base + timedelta(seconds=seconds)


def first_valid_rmc(path: Path) -> datetime:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            value = parse_nmea_rmc_datetime(line)
            if value is not None:
                return value
    raise ValueError(f"no active RMC timestamp in {path}")


def first_rinex_record_date(path: Path) -> date:
    after_header = False
    pattern = re.compile(r"^\s*[A-Z]\d{2}\s+(\d{4})\s+(\d{2})\s+(\d{2})\s+")
    with path.open("r", encoding="ascii", errors="replace") as handle:
        for line in handle:
            if "END OF HEADER" in line:
                after_header = True
                continue
            if not after_header:
                continue
            match = pattern.match(line)
            if match:
                return date(
                    int(match.group(1)), int(match.group(2)), int(match.group(3))
                )
    raise ValueError(f"no RINEX navigation record date in {path}")


def gps_week_for_anchor(anchor_utc: datetime) -> int:
    gps_time = anchor_utc + timedelta(seconds=GPS_UTC_LEAP_SECONDS)
    return int((gps_time - GPS_EPOCH).total_seconds() // GPS_WEEK_SECONDS)


def nearest_geometry_record(
    target_utc: datetime,
    rows: Iterable[dict[str, Any]],
    *,
    prn: str,
    tolerance_seconds: float = MAX_GEOMETRY_DELTA_SECONDS,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("prn", "")).strip().upper() != prn.strip().upper():
            continue
        timestamp = row.get("_utc_datetime") or parse_utc(row.get("utc_time"))
        if timestamp is None:
            continue
        candidate = dict(row)
        candidate["_utc_datetime"] = timestamp
        candidate["delta_seconds"] = abs((timestamp - target_utc).total_seconds())
        candidates.append(candidate)
    if not candidates:
        return None
    best = min(candidates, key=lambda row: row["delta_seconds"])
    if best["delta_seconds"] > tolerance_seconds:
        return None
    return best


def classify_event_modeling_flags(
    *,
    legacy_context_missing: bool,
    geometry_join_valid: bool,
    confirmed: bool,
) -> dict[str, str]:
    if legacy_context_missing:
        status = "excluded_legacy_context_missing"
        environment = "0"
        elevation = "0"
    else:
        status = "ready" if geometry_join_valid else "ready_with_geometry_exclusions"
        environment = "1"
        elevation = "1" if geometry_join_valid else "0"
    return {
        "run_modeling_status": status,
        "include_in_environment_modeling": environment,
        "include_in_elevation_modeling": elevation,
        "confirmed_for_modeling": "1" if confirmed and environment == "1" else "0",
    }


def max_time_origin_error_seconds(
    origins: Iterable[datetime], center: datetime
) -> float:
    return max(
        (abs(value - center).total_seconds() for value in origins),
        default=0.0,
    )


def resolve_project_path(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_file():
        return candidate
    normalized = str(value).replace("\\", "/")
    root_text = str(root.resolve()).replace("\\", "/")
    if normalized.casefold().startswith((root_text + "/").casefold()):
        relative = normalized[len(root_text) + 1 :]
        candidate = root / Path(relative)
    if not candidate.is_file():
        raise FileNotFoundError(value)
    return candidate


def _source_partition(root: Path) -> Path:
    return root / "dataset/multipath_event_database/v1/partitions" / (
        f"ingestion_id={SOURCE_PARTITION_ID}"
    )


def _alignment_root(root: Path) -> Path:
    return root / "dataset/multipath_event_database/v1/partitions" / (
        f"alignment_id={ALIGNMENT_ID}"
    )


def _load_geometry_cache(root: Path, scene_ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
    cache: dict[str, list[dict[str, Any]]] = {}
    for scene_id in sorted(set(scene_ids)):
        path = root / "scenes" / scene_id / "satellite" / (
            f"{scene_id}_satellite_elevation_timeseries.csv"
        )
        if not path.is_file():
            cache[scene_id] = []
            continue
        rows = []
        for row in read_csv_rows(path):
            timestamp = parse_utc(row.get("utc_time"))
            if timestamp is None:
                continue
            item = dict(row)
            item["_utc_datetime"] = timestamp
            rows.append(item)
        cache[scene_id] = rows
    return cache


def _load_scene_metadata(root: Path, scene_ids: set[str]) -> tuple[list[dict[str, str]], str]:
    path = root / SCENE_METADATA_REL
    rows = read_csv_rows(path)
    by_scene = {row.get("scene_id", ""): row for row in rows}
    missing = sorted(scene_ids - set(by_scene))
    extra = sorted(set(by_scene) - scene_ids)
    if missing or extra or len(rows) != len(by_scene):
        raise ValueError(f"scene metadata coverage mismatch; missing={missing}, extra={extra}")
    output = []
    for scene_id in sorted(scene_ids):
        row = by_scene[scene_id]
        output.append(
            {
                "scene_id": scene_id,
                "environment_class": row.get("environment_class", ""),
                "special_condition": row.get("special_condition", ""),
                "road_type": row.get("road_type", ""),
                "nominal_speed_kmh": row.get("vehicle_speed_kmh", ""),
                "speed_semantics": "human_measurement_description",
                "human_description": row.get("human_description", ""),
                "metadata_source": row.get("metadata_source", ""),
                "annotation_source_file": row.get("annotation_source_file", ""),
                "annotation_method": "human_annotation_import",
                "annotation_version": "scene_environment_annotation_list_v1",
                "environment_verified": "1",
                "source_file": SCENE_METADATA_REL.as_posix(),
                "source_file_sha256": sha256_file(path),
                "schema_version": ALIGNMENT_VERSION,
            }
        )
    return output, sha256_file(path)


def _build_time_alignment(
    root: Path,
    runs: list[dict[str, str]],
    scene_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    week_by_scene: dict[str, int] = {}
    issues: list[dict[str, str]] = []
    for scene_id in sorted(scene_ids):
        scene_runs = [
            row
            for row in runs
            if row["scene_id"] == scene_id and row.get("context_missing_legacy") != "1"
        ]
        if not scene_runs:
            raise ValueError(f"no non-legacy runs available for {scene_id}")
        trajectory = resolve_project_path(root, scene_runs[0]["trajectory_relpath"])
        rinex = resolve_project_path(root, scene_runs[0]["rinex_nav_relpath"])
        anchor = first_valid_rmc(trajectory)
        rinex_date = first_rinex_record_date(rinex)
        if anchor.date() != rinex_date:
            raise ValueError(
                f"NMEA/RINEX calendar mismatch for {scene_id}: {anchor.date()} vs {rinex_date}"
            )
        gps_week = gps_week_for_anchor(anchor)
        week_by_scene[scene_id] = gps_week
        origins: list[datetime] = []
        stage0_sources: list[str] = []
        for run in scene_runs:
            stage0 = root / run["source_result_relpath"] / "stage0_valid_40ms_windows.csv"
            stage0_sources.append(run["source_result_relpath"] + "/stage0_valid_40ms_windows.csv")
            for window in read_csv_rows(stage0):
                tow = parse_float(window.get("tow_s"))
                recording_time = parse_float(window.get("recording_time_s"))
                if tow is None or recording_time is None:
                    raise ValueError(f"invalid Stage0 time fields in {stage0}")
                origins.append(
                    gps_tow_to_utc(gps_week, tow).replace(microsecond=0)
                    + timedelta(microseconds=round((tow % 1) * 1_000_000))
                    - timedelta(seconds=recording_time)
                )
        if not origins:
            raise ValueError(f"no Stage0 windows for {scene_id}")
        origin_seconds = [value.timestamp() for value in origins]
        median_origin = datetime.fromtimestamp(median(origin_seconds), tz=timezone.utc)
        max_error = max_time_origin_error_seconds(origins, median_origin)
        alignment_id = f"{scene_id}__tow_to_utc_v1"
        source_files = [
            SCENE_METADATA_REL.as_posix(),
            str(trajectory.relative_to(root)).replace("\\", "/"),
            str(rinex.relative_to(root)).replace("\\", "/"),
            *sorted(set(stage0_sources)),
            f"scenes/{scene_id}/satellite/{scene_id}_satellite_elevation_timeseries.csv",
        ]
        rows.append(
            {
                "scene_id": scene_id,
                "alignment_id": alignment_id,
                "alignment_method": "tow_to_utc",
                "verified": "1",
                "recording_time_origin_utc": iso_utc(median_origin),
                "gps_week": str(gps_week),
                "leap_seconds": str(GPS_UTC_LEAP_SECONDS),
                "max_alignment_error_s": format_float(max_error),
                "source_files": json.dumps(source_files, ensure_ascii=False),
                "missing_reason": "",
                "nmea_anchor_utc": iso_utc(anchor),
                "rinex_calendar_date": rinex_date.isoformat(),
                "schema_version": ALIGNMENT_VERSION,
            }
        )
    return rows, week_by_scene, issues


def _alignment_source_hashes(root: Path, source_partition: Path) -> dict[str, str]:
    manifest = root / "dataset/multipath_event_database/v1/manifests/ingestions" / (
        f"{SOURCE_PARTITION_ID}.json"
    )
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    return {
        "source_ingestion_manifest_sha256": sha256_file(manifest),
        "source_sage_runs_sha256": sha256_file(source_partition / "facts/sage_runs.csv"),
        "source_events_sha256": sha256_file(source_partition / "facts/events.csv"),
        "source_event_paths_sha256": sha256_file(source_partition / "facts/event_paths.csv"),
        "source_event_context_sha256": sha256_file(source_partition / "facts/event_context.csv"),
        "pipeline_sha256": manifest_data["frozen_source_hashes"]["pipeline_sha256"],
        "wrapper_sha256": manifest_data["frozen_source_hashes"]["wrapper_sha256"],
        "executor_sha256": manifest_data["frozen_source_hashes"]["executor_sha256"],
        "production_manifest_sha256": manifest_data["frozen_source_hashes"]["manifest_sha256"],
        "inventory_sha256": manifest_data["frozen_source_hashes"]["inventory_sha256"],
    }


def _table_hashes(root: Path, final_root: Path, table_paths: list[str]) -> dict[str, str]:
    return {relative: sha256_file(final_root / relative) for relative in sorted(table_paths)}


def build_alignment(root: Path) -> Path:
    root = root.resolve()
    source_partition = _source_partition(root)
    final_root = _alignment_root(root)
    if final_root.exists():
        raise FileExistsError(f"alignment namespace already exists: {final_root}")
    required = [
        source_partition / "facts/sage_runs.csv",
        source_partition / "facts/events.csv",
        source_partition / "facts/event_paths.csv",
        source_partition / "facts/event_context.csv",
        root / SCENE_METADATA_REL,
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    runs = read_csv_rows(source_partition / "facts/sage_runs.csv")
    events = read_csv_rows(source_partition / "facts/events.csv")
    event_paths = read_csv_rows(source_partition / "facts/event_paths.csv")
    old_context = read_csv_rows(source_partition / "facts/event_context.csv")
    run_by_id = {row["run_id"]: row for row in runs}
    event_by_id = {row["event_id"]: row for row in events}
    scene_ids = {row["scene_id"] for row in runs}
    scene_context, scene_metadata_hash = _load_scene_metadata(root, scene_ids)
    time_alignment, week_by_scene, time_issues = _build_time_alignment(root, runs, scene_ids)
    geometry_cache = _load_geometry_cache(root, scene_ids)
    alignment_by_scene = {row["scene_id"]: row for row in time_alignment}
    context_rows: list[dict[str, Any]] = []
    event_eligibility: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = list(time_issues)

    for base in old_context:
        run = run_by_id[base["run_id"]]
        event = event_by_id[base["event_id"]]
        aligned = dict(base)
        aligned["context_alignment_version"] = ALIGNMENT_VERSION
        legacy = run.get("context_missing_legacy") == "1"
        geometry_join_valid = False
        reason = ""
        if legacy:
            aligned.update(
                {
                    "event_utc": "",
                    "elevation_deg": "",
                    "azimuth_deg": "",
                    "nmea_snr_db_hz": "",
                    "geometry_join_status": "unavailable",
                    "geometry_join_valid": "0",
                    "geometry_join_method": "",
                    "geometry_source_utc": "",
                    "geometry_time_delta_s": "",
                    "time_alignment_id": "",
                    "missing_reason": "legacy_context_missing_excluded_from_modeling",
                    "observation_quality": "invalid",
                }
            )
            issues.append(
                {
                    "severity": "warning",
                    "issue_code": "legacy_context_missing",
                    "event_id": base["event_id"],
                    "run_id": base["run_id"],
                    "scene_id": base["scene_id"],
                    "prn": base["prn"],
                    "detail": "G06 legacy run_context.json is absent",
                    "action": "exclude_from_modeling_retain_audit",
                    "alignment_version": ALIGNMENT_VERSION,
                }
            )
        else:
            alignment = alignment_by_scene[base["scene_id"]]
            target = gps_tow_to_utc(
                week_by_scene[base["scene_id"]],
                parse_float(base["tow_s"]) or 0.0,
            )
            aligned["event_utc"] = iso_utc(target)
            aligned["time_alignment_id"] = alignment["alignment_id"]
            match = nearest_geometry_record(
                target,
                geometry_cache[base["scene_id"]],
                prn=base["prn"],
                tolerance_seconds=MAX_GEOMETRY_DELTA_SECONDS,
            )
            same_prn = [
                row
                for row in geometry_cache[base["scene_id"]]
                if str(row.get("prn", "")).strip().upper() == base["prn"].upper()
            ]
            if match is not None:
                geometry_join_valid = True
                aligned.update(
                    {
                        "elevation_deg": match.get("elevation_deg", ""),
                        "azimuth_deg": match.get("azimuth_deg", ""),
                        "nmea_snr_db_hz": match.get("snr_db_hz", ""),
                        "geometry_join_status": "valid",
                        "geometry_join_valid": "1",
                        "geometry_join_method": "tow_to_utc_nearest_gsv",
                        "geometry_source_utc": iso_utc(match["_utc_datetime"]),
                        "geometry_time_delta_s": format_float(match["delta_seconds"]),
                        "missing_reason": "",
                        "observation_quality": "valid",
                    }
                )
            elif not same_prn:
                reason = "geometry_prn_missing_in_timeseries"
                aligned.update(
                    {
                        "elevation_deg": "",
                        "azimuth_deg": "",
                        "nmea_snr_db_hz": "",
                        "geometry_join_status": "unavailable",
                        "geometry_join_valid": "0",
                        "geometry_join_method": "tow_to_utc_nearest_gsv",
                        "geometry_source_utc": "",
                        "geometry_time_delta_s": "",
                        "missing_reason": reason,
                        "observation_quality": "warning",
                    }
                )
            else:
                all_matches = [
                    dict(row, delta_seconds=abs((row["_utc_datetime"] - target).total_seconds()))
                    for row in same_prn
                ]
                nearest = min(all_matches, key=lambda row: row["delta_seconds"])
                reason = "nearest_geometry_delta_exceeds_5s"
                aligned.update(
                    {
                        "elevation_deg": "",
                        "azimuth_deg": "",
                        "nmea_snr_db_hz": "",
                        "geometry_join_status": "inconclusive",
                        "geometry_join_valid": "0",
                        "geometry_join_method": "tow_to_utc_nearest_gsv",
                        "geometry_source_utc": iso_utc(nearest["_utc_datetime"]),
                        "geometry_time_delta_s": format_float(nearest["delta_seconds"]),
                        "missing_reason": reason,
                        "observation_quality": "warning",
                    }
                )
            if reason:
                issues.append(
                    {
                        "severity": "warning",
                        "issue_code": reason,
                        "event_id": base["event_id"],
                        "run_id": base["run_id"],
                        "scene_id": base["scene_id"],
                        "prn": base["prn"],
                        "detail": aligned.get("geometry_time_delta_s", ""),
                        "action": "exclude_from_elevation_conditioned_modeling_retain_context",
                        "alignment_version": ALIGNMENT_VERSION,
                    }
                )
        context_rows.append(aligned)
        flags = classify_event_modeling_flags(
            legacy_context_missing=legacy,
            geometry_join_valid=geometry_join_valid,
            confirmed=event["event_status"] == "confirmed_multipath",
        )
        event_eligibility.append(
            {
                "event_id": base["event_id"],
                "run_id": base["run_id"],
                "scene_id": base["scene_id"],
                "prn": base["prn"],
                "event_status": event["event_status"],
                "confirmed_event": flags["confirmed_for_modeling"],
                "event_utc": aligned["event_utc"],
                "environment_class": next(
                    row["environment_class"] for row in scene_context if row["scene_id"] == base["scene_id"]
                ),
                "geometry_join_status": aligned["geometry_join_status"],
                "geometry_join_valid": aligned["geometry_join_valid"],
                "include_in_environment_modeling": flags["include_in_environment_modeling"],
                "include_in_elevation_modeling": flags["include_in_elevation_modeling"],
                "exclusion_reason": (
                    aligned["missing_reason"]
                    if flags["include_in_elevation_modeling"] == "0"
                    else ""
                ),
                "alignment_id": aligned["time_alignment_id"],
                "alignment_version": ALIGNMENT_VERSION,
            }
        )

    scene_by_id = {row["scene_id"]: row for row in scene_context}
    context_by_event = {row["event_id"]: row for row in context_rows}
    run_event_counts: dict[str, int] = defaultdict(int)
    run_geometry_counts: dict[str, int] = defaultdict(int)
    for row in event_eligibility:
        run_event_counts[row["run_id"]] += 1
        run_geometry_counts[row["run_id"]] += int(row["geometry_join_valid"])
    run_eligibility: list[dict[str, Any]] = []
    for run in runs:
        legacy = run.get("context_missing_legacy") == "1"
        run_eligibility.append(
            {
                "run_id": run["run_id"],
                "scene_id": run["scene_id"],
                "prn": run["prn"],
                "acceptance_class": run["acceptance_class"],
                "context_missing_legacy": run.get("context_missing_legacy", "0"),
                "run_modeling_status": (
                    "excluded_legacy_context_missing"
                    if legacy
                    else "ready_with_geometry_exclusions"
                    if run_geometry_counts[run["run_id"]] < run_event_counts[run["run_id"]]
                    else "ready"
                ),
                "include_in_environment_modeling": "0" if legacy else "1",
                "event_count": str(run_event_counts[run["run_id"]]),
                "geometry_valid_event_count": str(run_geometry_counts[run["run_id"]]),
                "exclusion_reason": "legacy_context_missing" if legacy else "",
                "alignment_id": "" if legacy else alignment_by_scene[run["scene_id"]]["alignment_id"],
                "alignment_version": ALIGNMENT_VERSION,
            }
        )

    confirmed_environment_paths: list[dict[str, Any]] = []
    confirmed_elevation_paths: list[dict[str, Any]] = []
    for path_row in event_paths:
        event = event_by_id[path_row["event_id"]]
        if event["event_status"] != "confirmed_multipath" or path_row.get("is_multipath") != "1":
            continue
        context = context_by_event[path_row["event_id"]]
        run = run_by_id[path_row["run_id"]]
        if run.get("context_missing_legacy") == "1":
            continue
        scene = scene_by_id[path_row["scene_id"]]
        enriched = dict(path_row)
        enriched.update(
            {
                "event_utc": context["event_utc"],
                "environment_class": scene["environment_class"],
                "special_condition": scene["special_condition"],
                "road_type": scene["road_type"],
                "elevation_deg": context["elevation_deg"],
                "azimuth_deg": context["azimuth_deg"],
                "nmea_snr_db_hz": context["nmea_snr_db_hz"],
                "geometry_join_status": context["geometry_join_status"],
                "geometry_join_valid": context["geometry_join_valid"],
                "geometry_source_utc": context["geometry_source_utc"],
                "geometry_time_delta_s": context["geometry_time_delta_s"],
                "alignment_version": ALIGNMENT_VERSION,
            }
        )
        confirmed_environment_paths.append(enriched)
        if context["geometry_join_valid"] == "1":
            confirmed_elevation_paths.append(enriched)

    run_fields = [
        "run_id", "scene_id", "prn", "acceptance_class", "context_missing_legacy",
        "run_modeling_status", "include_in_environment_modeling", "event_count",
        "geometry_valid_event_count", "exclusion_reason", "alignment_id", "alignment_version",
    ]
    event_fields = [
        "event_id", "run_id", "scene_id", "prn", "event_status", "confirmed_event", "event_utc",
        "environment_class", "geometry_join_status", "geometry_join_valid",
        "include_in_environment_modeling", "include_in_elevation_modeling", "exclusion_reason",
        "alignment_id", "alignment_version",
    ]
    path_base_fields = list(event_paths[0].keys()) if event_paths else ["event_id", "run_id", "scene_id", "is_multipath"]
    path_fields = path_base_fields + [
        "event_utc", "environment_class", "special_condition", "road_type", "elevation_deg",
        "azimuth_deg", "nmea_snr_db_hz", "geometry_join_status", "geometry_join_valid",
        "geometry_source_utc", "geometry_time_delta_s", "alignment_version",
    ]
    issue_fields = [
        "severity", "issue_code", "event_id", "run_id", "scene_id", "prn", "detail", "action", "alignment_version"
    ]
    alignment_fields = [
        "scene_id", "alignment_id", "alignment_method", "verified", "recording_time_origin_utc",
        "gps_week", "leap_seconds", "max_alignment_error_s", "source_files", "missing_reason",
        "nmea_anchor_utc", "rinex_calendar_date", "schema_version",
    ]
    scene_fields = list(scene_context[0].keys())
    table_rows: dict[str, tuple[list[str], list[dict[str, Any]]]] = {
        "dimensions/scene_context.csv": (scene_fields, scene_context),
        "dimensions/time_alignment.csv": (alignment_fields, time_alignment),
        "facts/event_context_aligned.csv": (EVENT_CONTEXT_FIELDS, context_rows),
        "exports/modeling_run_eligibility.csv": (run_fields, run_eligibility),
        "exports/modeling_event_eligibility.csv": (event_fields, event_eligibility),
        "exports/confirmed_paths_environment_ready.csv": (path_fields, confirmed_environment_paths),
        "exports/confirmed_paths_elevation_ready.csv": (path_fields, confirmed_elevation_paths),
        "qa/alignment_issues.csv": (issue_fields, issues),
    }

    parent = final_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{ALIGNMENT_ID}.staging-", dir=parent))
    try:
        for relative, (fields, rows) in table_rows.items():
            write_csv_rows(staging / relative, fields, rows)
        table_paths = list(table_rows)
        hashes = _table_hashes(root, staging, table_paths)
        confirmed_event_count = sum(
            1 for row in events if row["event_status"] == "confirmed_multipath"
        )
        confirmed_path_count = sum(
            1 for row in event_paths
            if row.get("is_multipath") == "1"
            and event_by_id[row["event_id"]]["event_status"] == "confirmed_multipath"
        )
        report = f"""# Modeling context alignment — {ALIGNMENT_ID}

## Result

`MODELING_CONTEXT_ALIGNMENT = COMPLETED_WITH_EXCLUSIONS`

The source audit partition remains immutable. This versioned overlay uses the
existing Stage0 TOW, NMEA/GSV UTC geometry, RINEX calendar date, the frozen
18-second GPS–UTC offset, and the existing validated human scene metadata.

## Counts

- Runs: `{len(runs)}`; scene context verified: `{len(scene_context)}/{len(scene_ids)}`.
- Time alignment verified: `{len(time_alignment)}/{len(scene_ids)}`.
- Event contexts: `{len(context_rows)}`; event-time geometry valid: `{sum(1 for row in context_rows if row['geometry_join_valid'] == '1')}`.
- Confirmed events/paths: `{confirmed_event_count}/{confirmed_path_count}`.
- Environment-ready confirmed paths (G06 excluded): `{len(confirmed_environment_paths)}`.
- Elevation-ready confirmed paths (same-PRN nearest GSV within {MAX_GEOMETRY_DELTA_SECONDS:.0f}s): `{len(confirmed_elevation_paths)}`.

## Exclusions

- G06 legacy: retained in the source audit and excluded from both modeling inputs.
- Missing requested PRN in geometry: retained with null event geometry.
- Nearest geometry farther than the fixed tolerance: retained with null event geometry.

No interpolation, scene mean, or filename-derived geometry was used.

## Execution record

- Raw IQ read: no
- MATLAB/SAGE/batch started: no
- Existing SAGE artifacts, requests, manifest, inventory and metadata modified: no
- Channel parameters/statistical model started: no
"""
        (staging / "alignment_report.md").write_text(report, encoding="utf-8")
        manifest = {
            "alignment_id": ALIGNMENT_ID,
            "alignment_version": ALIGNMENT_VERSION,
            "created_utc": iso_utc(datetime.now(timezone.utc)),
            "source_partition": f"dataset/multipath_event_database/v1/partitions/ingestion_id={SOURCE_PARTITION_ID}",
            "rules": {
                "gps_utc_leap_seconds": GPS_UTC_LEAP_SECONDS,
                "geometry_join": "same_prn_nearest_gsv_no_interpolation",
                "max_geometry_delta_seconds": MAX_GEOMETRY_DELTA_SECONDS,
                "g06_policy": "exclude_legacy_context_missing_retain_audit",
            },
            "source_hashes": _alignment_source_hashes(root, source_partition),
            "scene_metadata_sha256": scene_metadata_hash,
            "table_counts": {
                relative: len(rows) for relative, (_, rows) in table_rows.items()
            },
            "table_sha256": hashes,
            "result_counts": {
                "run_count": len(runs),
                "scene_count": len(scene_ids),
                "time_alignment_verified": len(time_alignment),
                "event_context_count": len(context_rows),
                "event_geometry_valid_count": sum(
                    1 for row in context_rows if row["geometry_join_valid"] == "1"
                ),
                "confirmed_event_count": confirmed_event_count,
                "confirmed_path_count": confirmed_path_count,
                "environment_ready_confirmed_path_count": len(confirmed_environment_paths),
                "elevation_ready_confirmed_path_count": len(confirmed_elevation_paths),
                "g06_modeling_excluded_count": sum(
                    1 for row in runs if row.get("context_missing_legacy") == "1"
                ),
            },
            "gate_record": {
                "raw_iq_read": False,
                "matlab_started": False,
                "sage_started": False,
                "batch_started": False,
                "existing_sage_artifacts_modified": False,
                "statistical_modeling_started": False,
                "channel_parameter_derivation_started": False,
            },
            "status": "completed_with_exclusions",
            "independent_qa_status": "PENDING",
        }
        (staging / "alignment_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        staging.rename(final_root)
    except Exception:
        raise
    return final_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    output = build_alignment(args.project_root)
    print(f"ALIGNMENT_RESULT=completed_with_exclusions|path={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
