#!/usr/bin/env python3
"""Shared satellite-geometry extraction for GNSS multipath scenes.

Algorithm semantics intentionally match the preserved reference experiment:

* elevation, azimuth, and SNR are extracted from timestamped NMEA GSV records;
* RINEX NAV is used only to select GPS PRNs that have ephemeris records;
* no satellite position is recomputed from broadcast ephemerides;
* raw IQ data is never read.
"""

from __future__ import annotations

import csv
import hashlib
import math
import re
import statistics
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


ELEVATION_FIELDS = (
    "utc_time",
    "prn",
    "elevation_deg",
    "azimuth_deg",
    "snr_db_hz",
    "elevation_group",
    "gsv_total_messages",
    "gsv_message_number",
    "satellites_in_view",
    "nmea_file",
    "raw_gsv_sentence",
)

SUMMARY_FIELDS = (
    "prn",
    "start_utc",
    "end_utc",
    "min_elevation_deg",
    "max_elevation_deg",
    "mean_elevation_deg",
    "median_elevation_deg",
    "elevation_std_deg",
    "circular_mean_azimuth_deg",
    "mean_snr_db_hz",
    "observation_count",
    "low_count",
    "mid_count",
    "high_count",
    "primary_elevation_group",
)


class SatelliteGeometryError(RuntimeError):
    """Base class for satellite-geometry generation errors."""


class InputValidationError(SatelliteGeometryError):
    """Raised when required scene inputs are missing or ambiguous."""


class ExistingOutputError(SatelliteGeometryError):
    """Raised when existing output is partial or invalid."""


class NoRetainedObservationsError(SatelliteGeometryError):
    """Raised when no timestamped GSV observation survives NAV filtering."""


@dataclass(frozen=True)
class ElevationRecord:
    utc_time: datetime
    prn: str
    elevation_deg: float
    azimuth_deg: float
    snr_db_hz: float | None
    elevation_group: str
    gsv_total_messages: int
    gsv_message_number: int
    satellites_in_view: int
    nmea_file: str
    raw_gsv_sentence: str


@dataclass(frozen=True)
class ExistingOutputInfo:
    observation_count: int
    satellite_count: int


@dataclass(frozen=True)
class SatelliteGeometryResult:
    scene_id: str
    status: str
    nmea_files: tuple[Path, ...]
    nav_files: tuple[Path, ...]
    output_files: tuple[Path, ...]
    observation_count: int
    satellite_count: int
    nav_prn_count: int
    bad_checksum_count: int
    untimestamped_gsv_count: int
    ignored_prns: tuple[str, ...]
    duration_seconds: float


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def elevation_group(elevation_deg: float) -> str:
    if 0.0 <= elevation_deg < 30.0:
        return "Low"
    if 30.0 <= elevation_deg < 60.0:
        return "Mid"
    if 60.0 <= elevation_deg <= 90.0:
        return "High"
    raise ValueError(f"elevation outside [0, 90] degrees: {elevation_deg}")


def nmea_payload(line: str) -> tuple[list[str] | None, bool]:
    text = line.strip().lstrip("\ufeff")
    if not text.startswith("$"):
        return None, False

    content = text[1:]
    checksum_ok = True
    if "*" in content:
        body, supplied_checksum = content.split("*", 1)
        checksum = 0
        for character in body:
            checksum ^= ord(character)
        try:
            checksum_ok = checksum == int(supplied_checksum[:2], 16)
        except (ValueError, IndexError):
            checksum_ok = False
    else:
        body = content
    return body.split(","), checksum_ok


def parse_nmea_datetime(time_text: str, date_text: str) -> datetime:
    if len(time_text) < 6 or len(date_text) != 6:
        raise ValueError("incomplete NMEA date or time")
    hour = int(time_text[0:2])
    minute = int(time_text[2:4])
    second_float = float(time_text[4:])
    second = int(second_float)
    microsecond = round((second_float - second) * 1_000_000)
    if microsecond == 1_000_000:
        second += 1
        microsecond = 0
    day = int(date_text[0:2])
    month = int(date_text[2:4])
    year_2digit = int(date_text[4:6])
    year = 2000 + year_2digit if year_2digit < 80 else 1900 + year_2digit
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        second,
        microsecond,
        tzinfo=timezone.utc,
    )


def parse_rinex_nav_prns(nav_files: Sequence[Path]) -> set[str]:
    prns: set[str] = set()
    for nav_file in nav_files:
        in_header = True
        with nav_file.open("r", encoding="ascii", errors="replace") as handle:
            for line in handle:
                if in_header:
                    if "END OF HEADER" in line:
                        in_header = False
                    continue
                match_v3 = re.match(r"^G(\d{2})\s", line)
                if match_v3:
                    prns.add(f"G{int(match_v3.group(1)):02d}")
                    continue
                match_v2 = re.match(
                    r"^\s*(\d{1,2})\s+\d{2}\s+\d{1,2}\s+\d{1,2}\s+"
                    r"\d{1,2}\s+\d{1,2}",
                    line,
                )
                if match_v2:
                    prn_number = int(match_v2.group(1))
                    if 1 <= prn_number <= 32:
                        prns.add(f"G{prn_number:02d}")
    return prns


def parse_gsv_satellites(
    fields: Sequence[str],
) -> Iterable[tuple[str, float, float, float | None]]:
    index = 4
    while index + 3 < len(fields):
        prn_text, elevation_text, azimuth_text, snr_text = fields[index : index + 4]
        index += 4
        if not prn_text or not elevation_text or not azimuth_text:
            continue
        try:
            prn_number = int(prn_text)
            elevation = float(elevation_text)
            azimuth = float(azimuth_text)
            snr = float(snr_text) if snr_text else None
        except ValueError:
            continue
        if 1 <= prn_number <= 32:
            yield f"G{prn_number:02d}", elevation, azimuth, snr


def parse_nmea_files(
    nmea_files: Sequence[Path],
) -> tuple[list[ElevationRecord], Counter[str], int, int]:
    deduplicated: dict[tuple[datetime, str], ElevationRecord] = {}
    all_prn_counts: Counter[str] = Counter()
    bad_checksum_count = 0
    untimestamped_gsv_count = 0

    for nmea_file in nmea_files:
        current_time: datetime | None = None
        with nmea_file.open("r", encoding="ascii", errors="replace") as handle:
            for raw_line in handle:
                fields, checksum_ok = nmea_payload(raw_line)
                if fields is None:
                    continue
                if not checksum_ok:
                    bad_checksum_count += 1
                    continue
                sentence_type = fields[0][-3:].upper() if fields[0] else ""
                if sentence_type == "RMC":
                    try:
                        current_time = parse_nmea_datetime(fields[1], fields[9])
                    except (IndexError, TypeError, ValueError):
                        current_time = None
                    continue
                if sentence_type != "GSV":
                    continue
                if current_time is None:
                    untimestamped_gsv_count += 1
                    continue
                try:
                    total_messages = int(fields[1])
                    message_number = int(fields[2])
                    satellites_in_view = int(fields[3])
                except (IndexError, ValueError):
                    continue

                raw_sentence = raw_line.strip()
                for prn, elevation, azimuth, snr in parse_gsv_satellites(fields):
                    all_prn_counts[prn] += 1
                    try:
                        group = elevation_group(elevation)
                    except ValueError:
                        continue
                    deduplicated[(current_time, prn)] = ElevationRecord(
                        utc_time=current_time,
                        prn=prn,
                        elevation_deg=elevation,
                        azimuth_deg=azimuth,
                        snr_db_hz=snr,
                        elevation_group=group,
                        gsv_total_messages=total_messages,
                        gsv_message_number=message_number,
                        satellites_in_view=satellites_in_view,
                        nmea_file=nmea_file.name,
                        raw_gsv_sentence=raw_sentence,
                    )

    records = sorted(
        deduplicated.values(),
        key=lambda record: (record.utc_time, int(record.prn[1:])),
    )
    return records, all_prn_counts, bad_checksum_count, untimestamped_gsv_count


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def display_number(value: float | None, decimals: int = 3) -> str:
    if value is None:
        return ""
    return f"{value:.{decimals}f}"


def circular_mean_degrees(values: Sequence[float]) -> float:
    radians = [math.radians(value) for value in values]
    mean_sine = statistics.fmean(math.sin(value) for value in radians)
    mean_cosine = statistics.fmean(math.cos(value) for value in radians)
    return math.degrees(math.atan2(mean_sine, mean_cosine)) % 360.0


def summarize_records(records: Sequence[ElevationRecord]) -> list[dict[str, object]]:
    by_prn: dict[str, list[ElevationRecord]] = {}
    for record in records:
        by_prn.setdefault(record.prn, []).append(record)

    rows: list[dict[str, object]] = []
    group_order = {"Low": 0, "Mid": 1, "High": 2}
    for prn in sorted(by_prn, key=lambda value: int(value[1:])):
        prn_records = sorted(by_prn[prn], key=lambda record: record.utc_time)
        elevations = [record.elevation_deg for record in prn_records]
        azimuths = [record.azimuth_deg for record in prn_records]
        snrs = [
            record.snr_db_hz for record in prn_records if record.snr_db_hz is not None
        ]
        group_counts = Counter(record.elevation_group for record in prn_records)
        primary_group = sorted(
            group_counts,
            key=lambda group: (-group_counts[group], group_order[group]),
        )[0]
        rows.append(
            {
                "prn": prn,
                "start_utc": iso_utc(prn_records[0].utc_time),
                "end_utc": iso_utc(prn_records[-1].utc_time),
                "min_elevation_deg": display_number(min(elevations)),
                "max_elevation_deg": display_number(max(elevations)),
                "mean_elevation_deg": display_number(statistics.fmean(elevations)),
                "median_elevation_deg": display_number(statistics.median(elevations)),
                "elevation_std_deg": display_number(
                    statistics.pstdev(elevations) if len(elevations) > 1 else 0.0
                ),
                "circular_mean_azimuth_deg": display_number(
                    circular_mean_degrees(azimuths)
                ),
                "mean_snr_db_hz": display_number(
                    statistics.fmean(snrs) if snrs else None
                ),
                "observation_count": len(prn_records),
                "low_count": group_counts["Low"],
                "mid_count": group_counts["Mid"],
                "high_count": group_counts["High"],
                "primary_elevation_group": primary_group,
            }
        )
    return rows


def write_timeseries_csv(records: Sequence[ElevationRecord], output_file: Path) -> None:
    with output_file.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ELEVATION_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "utc_time": iso_utc(record.utc_time),
                    "prn": record.prn,
                    "elevation_deg": display_number(record.elevation_deg),
                    "azimuth_deg": display_number(record.azimuth_deg),
                    "snr_db_hz": display_number(record.snr_db_hz),
                    "elevation_group": record.elevation_group,
                    "gsv_total_messages": record.gsv_total_messages,
                    "gsv_message_number": record.gsv_message_number,
                    "satellites_in_view": record.satellites_in_view,
                    "nmea_file": record.nmea_file,
                    "raw_gsv_sentence": record.raw_gsv_sentence,
                }
            )


def write_summary_csv(rows: Sequence[dict[str, object]], output_file: Path) -> None:
    with output_file.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _validate_csv(
    path: Path, expected_fields: Sequence[str]
) -> tuple[int, set[str]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ExistingOutputError(f"output is missing or empty: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != tuple(expected_fields):
                raise ExistingOutputError(f"unexpected CSV header: {path}")
            row_count = 0
            prns: set[str] = set()
            for row in reader:
                row_count += 1
                if row.get("prn"):
                    prns.add(row["prn"])
    except (OSError, UnicodeError, csv.Error) as error:
        raise ExistingOutputError(f"cannot read output {path}: {error}") from error
    if row_count == 0:
        raise ExistingOutputError(f"output has no data rows: {path}")
    return row_count, prns


def validate_existing_outputs(
    timeseries_file: Path, summary_file: Path
) -> ExistingOutputInfo | None:
    exists = (timeseries_file.exists(), summary_file.exists())
    if not any(exists):
        return None
    if not all(exists):
        raise ExistingOutputError(
            f"partial output exists: timeseries={exists[0]}, summary={exists[1]}"
        )
    observation_count, timeseries_prns = _validate_csv(
        timeseries_file, ELEVATION_FIELDS
    )
    summary_count, summary_prns = _validate_csv(summary_file, SUMMARY_FIELDS)
    if summary_count != len(summary_prns) or timeseries_prns != summary_prns:
        raise ExistingOutputError(
            f"timeseries/summary PRN mismatch: {timeseries_file}, {summary_file}"
        )
    return ExistingOutputInfo(
        observation_count=observation_count,
        satellite_count=len(timeseries_prns),
    )


def _find_inputs(scene_path: Path, scene_id: str) -> tuple[list[Path], list[Path]]:
    nmea_dir = scene_path / "gnss_sdr" / "nmea"
    nav_dir = scene_path / "navigation" / "rinex_nav"
    nmea_files = sorted(path for path in nmea_dir.glob("*.nmea") if path.is_file())
    nav_files = sorted(path for path in nav_dir.glob("*.26N") if path.is_file())
    expected_nmea = nmea_dir / f"{scene_id}_trajectory.nmea"
    if expected_nmea.is_file():
        nmea_files = [expected_nmea]
    if len(nmea_files) != 1:
        raise InputValidationError(
            f"expected one NMEA file in {nmea_dir}, found {len(nmea_files)}"
        )
    if len(nav_files) != 1:
        raise InputValidationError(
            f"expected one RINEX NAV file in {nav_dir}, found {len(nav_files)}"
        )
    return nmea_files, nav_files


def generate_satellite_geometry(
    scene_path: Path,
    *,
    overwrite: bool = False,
) -> SatelliteGeometryResult:
    """Generate or validate satellite-geometry CSV files for one scene."""
    started = time.perf_counter()
    scene_path = scene_path.expanduser().resolve()
    if not scene_path.is_dir():
        raise InputValidationError(f"scene directory not found: {scene_path}")
    scene_id = scene_path.name
    nmea_files, nav_files = _find_inputs(scene_path, scene_id)

    output_dir = scene_path / "satellite"
    timeseries_file = output_dir / f"{scene_id}_satellite_elevation_timeseries.csv"
    summary_file = output_dir / f"{scene_id}_satellite_elevation_summary.csv"
    output_files = (timeseries_file, summary_file)
    existing = validate_existing_outputs(timeseries_file, summary_file)
    if existing is not None and not overwrite:
        nav_prns = parse_rinex_nav_prns(nav_files)
        return SatelliteGeometryResult(
            scene_id=scene_id,
            status="skipped_existing",
            nmea_files=tuple(nmea_files),
            nav_files=tuple(nav_files),
            output_files=output_files,
            observation_count=existing.observation_count,
            satellite_count=existing.satellite_count,
            nav_prn_count=len(nav_prns),
            bad_checksum_count=0,
            untimestamped_gsv_count=0,
            ignored_prns=(),
            duration_seconds=time.perf_counter() - started,
        )
    if overwrite:
        raise ExistingOutputError("overwrite mode is intentionally unsupported")

    nav_prns = parse_rinex_nav_prns(nav_files)
    if not nav_prns:
        raise InputValidationError("no GPS ephemeris records found in RINEX NAV")
    records, all_prn_counts, bad_checksums, untimestamped_gsv = parse_nmea_files(
        nmea_files
    )
    retained = [record for record in records if record.prn in nav_prns]
    if not retained:
        raise NoRetainedObservationsError(
            "no timestamped GSV satellites are also present in RINEX NAV"
        )

    summary_rows = summarize_records(retained)
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_timeseries = timeseries_file.with_name(
        f".{timeseries_file.name}.{uuid.uuid4().hex}.tmp"
    )
    temp_summary = summary_file.with_name(
        f".{summary_file.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        write_timeseries_csv(retained, temp_timeseries)
        write_summary_csv(summary_rows, temp_summary)
        _validate_csv(temp_timeseries, ELEVATION_FIELDS)
        _validate_csv(temp_summary, SUMMARY_FIELDS)
        temp_timeseries.rename(timeseries_file)
        temp_summary.rename(summary_file)
    finally:
        if temp_timeseries.exists():
            temp_timeseries.unlink()
        if temp_summary.exists():
            temp_summary.unlink()

    validate_existing_outputs(timeseries_file, summary_file)
    retained_prns = {record.prn for record in retained}
    ignored_prns = tuple(sorted(set(all_prn_counts) - nav_prns))
    return SatelliteGeometryResult(
        scene_id=scene_id,
        status="completed",
        nmea_files=tuple(nmea_files),
        nav_files=tuple(nav_files),
        output_files=output_files,
        observation_count=len(retained),
        satellite_count=len(retained_prns),
        nav_prn_count=len(nav_prns),
        bad_checksum_count=bad_checksums,
        untimestamped_gsv_count=untimestamped_gsv,
        ignored_prns=ignored_prns,
        duration_seconds=time.perf_counter() - started,
    )


__all__ = [
    "ELEVATION_FIELDS",
    "SUMMARY_FIELDS",
    "ExistingOutputError",
    "InputValidationError",
    "NoRetainedObservationsError",
    "SatelliteGeometryError",
    "SatelliteGeometryResult",
    "generate_satellite_geometry",
    "sha256_file",
    "validate_existing_outputs",
]

