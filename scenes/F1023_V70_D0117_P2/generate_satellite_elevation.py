#!/usr/bin/env python3
"""
Regenerate GPS satellite elevation tables from GNSS-SDR NMEA output.

Place this script in the root directory of one GNSS-SDR result folder, for
example:

    F1023_V70_D0117_P2/
    ├── generate_satellite_elevation.py
    ├── navigation/rinex_nav/RINEXFILE.26N
    ├── trajectory/F1023_V70_D0117_P2_trajectory.nmea
    └── satellite/

Then run:

    python generate_satellite_elevation.py

Only GPS satellites present in the RINEX NAV file are retained. Elevation
classes are:

    Low  : 0 <= elevation < 30 degrees
    Mid  : 30 <= elevation < 60 degrees
    High : 60 <= elevation <= 90 degrees

The script uses only the Python standard library and does not read the raw IQ
file. CSV output is written with an UTF-8 BOM so it opens correctly in Excel.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
import sys
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


def elevation_group(elevation_deg: float) -> str:
    """Return the requested non-overlapping elevation class."""
    if 0.0 <= elevation_deg < 30.0:
        return "Low"
    if 30.0 <= elevation_deg < 60.0:
        return "Mid"
    if 60.0 <= elevation_deg <= 90.0:
        return "High"
    raise ValueError(f"Elevation outside [0, 90] degrees: {elevation_deg}")


def nmea_payload(line: str) -> tuple[list[str] | None, bool]:
    """
    Split one NMEA sentence and verify its checksum.

    Returns (fields, checksum_ok). Non-NMEA lines return (None, False).
    """
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
    """Parse NMEA hhmmss.sss and ddmmyy into a UTC datetime."""
    if len(time_text) < 6 or len(date_text) != 6:
        raise ValueError("Incomplete NMEA date or time")

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
    """Return GPS PRNs for which at least one broadcast ephemeris is present."""
    prns: set[str] = set()

    for nav_file in nav_files:
        in_header = True
        with nav_file.open("r", encoding="ascii", errors="replace") as handle:
            for line in handle:
                if in_header:
                    if "END OF HEADER" in line:
                        in_header = False
                    continue

                # RINEX 3 GPS navigation record, e.g. "G06 2026 01 17 ..."
                match_v3 = re.match(r"^G(\d{2})\s", line)
                if match_v3:
                    prns.add(f"G{int(match_v3.group(1)):02d}")
                    continue

                # Basic RINEX 2 GPS NAV support, e.g. " 6 26  1 17 ..."
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


def parse_gsv_satellites(fields: Sequence[str]) -> Iterable[tuple[str, float, float, float | None]]:
    """Yield GPS PRN, elevation, azimuth and SNR from one GSV sentence."""
    # fields[0:4] are talker/type, total messages, message number, SV count.
    # Remaining values are groups of PRN/elevation/azimuth/SNR. Newer NMEA
    # output can append a signal ID after the final complete group.
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

        # For GPS-only GNSS-SDR output, PRNs 1..32 are GPS satellites.
        if 1 <= prn_number <= 32:
            yield f"G{prn_number:02d}", elevation, azimuth, snr


def parse_nmea_files(
    nmea_files: Sequence[Path],
) -> tuple[list[ElevationRecord], Counter[str], int, int]:
    """
    Parse timestamped GPS GSV observations.

    Returns records, all observed PRN counts, invalid-checksum count and
    untimestamped-GSV count.
    """
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

                    record = ElevationRecord(
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
                    deduplicated[(current_time, prn)] = record

    records = sorted(
        deduplicated.values(),
        key=lambda record: (record.utc_time, int(record.prn[1:])),
    )
    return records, all_prn_counts, bad_checksum_count, untimestamped_gsv_count


def iso_utc(value: datetime) -> str:
    """Format a timezone-aware datetime as ISO 8601 UTC."""
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def display_number(value: float | None, decimals: int = 3) -> str:
    if value is None:
        return ""
    return f"{value:.{decimals}f}"


def write_timeseries_csv(records: Sequence[ElevationRecord], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8-sig", newline="") as handle:
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
            record.snr_db_hz
            for record in prn_records
            if record.snr_db_hz is not None
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


def write_summary_csv(rows: Sequence[dict[str, object]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def find_default_files(root: Path) -> tuple[list[Path], list[Path]]:
    nmea_files = sorted((root / "trajectory").glob("*.nmea"))
    nav_files = sorted(
        path
        for path in (root / "navigation" / "rinex_nav").glob("*")
        if path.is_file()
    )

    if not nmea_files:
        nmea_files = sorted(root.rglob("*.nmea"))
    if not nav_files:
        nav_files = sorted(
            path
            for path in root.rglob("*")
            if path.is_file()
            and "rinex_nav" in {part.lower() for part in path.parts}
        )
    return nmea_files, nav_files


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract timestamped GPS elevations from GNSS-SDR NMEA output and "
            "retain only satellites present in RINEX NAV."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="GNSS-SDR result root (default: directory containing this script)",
    )
    parser.add_argument(
        "--nmea",
        type=Path,
        nargs="+",
        help="Optional explicit NMEA file(s)",
    )
    parser.add_argument(
        "--nav",
        type=Path,
        nargs="+",
        help="Optional explicit RINEX NAV file(s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: ROOT/satellite)",
    )
    return parser.parse_args(argv)


def checked_files(paths: Sequence[Path], label: str) -> list[Path]:
    resolved: list[Path] = []
    for path in paths:
        candidate = path.expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"{label} file not found: {candidate}")
        resolved.append(candidate)
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: root directory not found: {root}", file=sys.stderr)
        return 2

    default_nmea, default_nav = find_default_files(root)
    try:
        nmea_files = checked_files(args.nmea or default_nmea, "NMEA")
        nav_files = checked_files(args.nav or default_nav, "RINEX NAV")
    except FileNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if not nmea_files:
        print(
            "ERROR: no NMEA file found under ROOT/trajectory. "
            "Use --nmea to specify it.",
            file=sys.stderr,
        )
        return 2
    if not nav_files:
        print(
            "ERROR: no RINEX NAV file found under ROOT/navigation/rinex_nav. "
            "Use --nav to specify it.",
            file=sys.stderr,
        )
        return 2

    nav_prns = parse_rinex_nav_prns(nav_files)
    if not nav_prns:
        print("ERROR: no GPS ephemeris records found in RINEX NAV.", file=sys.stderr)
        return 3

    records, all_prn_counts, bad_checksums, untimestamped_gsv = parse_nmea_files(
        nmea_files
    )
    retained = [record for record in records if record.prn in nav_prns]
    if not retained:
        print(
            "ERROR: no timestamped GSV satellites also present in RINEX NAV.",
            file=sys.stderr,
        )
        return 4

    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else root / "satellite"
    )
    prefix = root.name or "gnss_sdr"
    timeseries_file = output_dir / f"{prefix}_satellite_elevation_timeseries.csv"
    summary_file = output_dir / f"{prefix}_satellite_elevation_summary.csv"

    write_timeseries_csv(retained, timeseries_file)
    summary_rows = summarize_records(retained)
    write_summary_csv(summary_rows, summary_file)

    retained_prns = sorted({record.prn for record in retained})
    ignored_prns = sorted(set(all_prn_counts) - nav_prns)
    print(f"Root: {root}")
    print("NMEA: " + ", ".join(str(path) for path in nmea_files))
    print("RINEX NAV: " + ", ".join(str(path) for path in nav_files))
    print("NAV PRNs: " + ", ".join(sorted(nav_prns)))
    print("Retained PRNs: " + ", ".join(retained_prns))
    print(
        f"Retained observations: {len(retained)} "
        f"across {len(retained_prns)} satellites"
    )
    if ignored_prns:
        print("Ignored (no NAV ephemeris): " + ", ".join(ignored_prns))
    if bad_checksums:
        print(f"Warning: skipped {bad_checksums} NMEA sentence(s) with bad checksum")
    if untimestamped_gsv:
        print(f"Warning: skipped {untimestamped_gsv} untimestamped GSV sentence(s)")
    print(f"Timeseries: {timeseries_file}")
    print(f"Summary: {summary_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
