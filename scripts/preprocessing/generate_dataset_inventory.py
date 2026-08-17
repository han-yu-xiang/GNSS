#!/usr/bin/env python3
"""Build a read-only SAGE input inventory for every project scene.

The scanner reads scene metadata, GNSS-SDR logs, and file structure. It writes
only the requested inventory CSV and never modifies scene contents.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence


TRACKING_EVENT_RE = re.compile(
    r"Tracking of GPS L1 C/A signal started on channel\s+(\d+)\s+"
    r"for satellite GPS PRN\s+(\d+)"
)
NAV_MESSAGE_RE = re.compile(
    r"(?:New )?GPS NAV message received in channel\s+(\d+):.*?"
    r"satellite GPS PRN\s+(\d+)"
)
TRACKING_FILE_RE = re.compile(r"_track_ch_(\d+)\.(dat|mat)$", re.IGNORECASE)
TELEMETRY_FILE_RE = re.compile(r"_telemetry_ch_(\d+)\.(dat|mat)$", re.IGNORECASE)


FIELDNAMES = (
    "scene_id",
    "scene_role",
    "signal_type",
    "sampling_rate_hz",
    "raw_path",
    "raw_storage_mode",
    "gnss_sdr_status",
    "tracking_exists",
    "tracking_file_count",
    "tracking_dat_count",
    "tracking_mat_count",
    "tracking_channels",
    "tracking_channel_prn_map",
    "telemetry_exists",
    "telemetry_file_count",
    "telemetry_dat_count",
    "telemetry_mat_count",
    "telemetry_crc_count",
    "telemetry_channels",
    "observables_exists",
    "observables_file_count",
    "rinex_nav_exists",
    "rinex_nav_file_count",
    "rinex_nav_files",
    "trajectory_exists",
    "trajectory_file_count",
    "trajectory_files",
    "satellite_geometry_status",
    "satellite_geometry_completed",
    "satellite_geometry_file_count",
    "satellite_geometry_prns",
    "available_prn_count",
    "available_prns",
    "prn_tracking_channel_map",
    "sage_results_status",
    "sage_results_exists",
    "sage_result_file_count",
    "inventory_warnings",
)


def read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def nested(mapping: dict[str, object], *keys: str, default: object = "") -> object:
    value: object = mapping
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def relative_file_list(files: Iterable[Path], scene_path: Path) -> list[str]:
    return [path.relative_to(scene_path).as_posix() for path in sorted(files)]


def channel_file_sets(files: Sequence[Path], pattern: re.Pattern[str]) -> dict[str, set[int]]:
    channels: dict[str, set[int]] = {"dat": set(), "mat": set()}
    for path in files:
        match = pattern.search(path.name)
        if match:
            channels[match.group(2).lower()].add(int(match.group(1)))
    return channels


def parse_log_mappings(
    log_files: Sequence[Path],
) -> tuple[dict[int, set[str]], dict[str, set[int]]]:
    tracking_by_channel: dict[int, set[str]] = defaultdict(set)
    nav_prn_channels: dict[str, set[int]] = defaultdict(set)
    for log_file in log_files:
        text = log_file.read_text(encoding="utf-8", errors="replace")
        for match in TRACKING_EVENT_RE.finditer(text):
            channel = int(match.group(1))
            prn_number = int(match.group(2))
            if 1 <= prn_number <= 32:
                tracking_by_channel[channel].add(f"G{prn_number:02d}")
        for match in NAV_MESSAGE_RE.finditer(text):
            channel = int(match.group(1))
            prn_number = int(match.group(2))
            if 1 <= prn_number <= 32:
                nav_prn_channels[f"G{prn_number:02d}"].add(channel)
    return tracking_by_channel, nav_prn_channels


def read_satellite_prns(summary_files: Sequence[Path]) -> tuple[set[str], list[str]]:
    prns: set[str] = set()
    warnings: list[str] = []
    for path in summary_files:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if "prn" not in (reader.fieldnames or []):
                    warnings.append(f"satellite_summary_missing_prn:{path.name}")
                    continue
                for row in reader:
                    prn = (row.get("prn") or "").strip()
                    if re.fullmatch(r"G(?:0[1-9]|[12]\d|3[0-2])", prn):
                        prns.add(prn)
        except (OSError, UnicodeError, csv.Error) as error:
            warnings.append(f"satellite_summary_unreadable:{path.name}:{error}")
    return prns, warnings


def scene_inventory(scene_path: Path) -> dict[str, object]:
    scene_id = scene_path.name
    metadata_path = scene_path / "metadata.json"
    metadata = read_json(metadata_path)
    warnings: list[str] = []
    if metadata.get("scene_id") != scene_id:
        warnings.append(f"metadata_scene_id_mismatch:{metadata.get('scene_id')}")

    tracking_dir = scene_path / "gnss_sdr" / "tracking"
    telemetry_dir = scene_path / "gnss_sdr" / "telemetry"
    observables_dir = scene_path / "gnss_sdr" / "observables"
    log_dir = scene_path / "gnss_sdr" / "logs"
    nav_dir = scene_path / "navigation" / "rinex_nav"
    trajectory_dir = scene_path / "trajectory"
    satellite_dir = scene_path / "satellite"
    sage_dir = scene_path / "sage_results"

    tracking_files = sorted(path for path in tracking_dir.glob("*") if path.is_file())
    telemetry_files = sorted(path for path in telemetry_dir.glob("*") if path.is_file())
    observable_files = sorted(path for path in observables_dir.glob("*") if path.is_file())
    log_files = sorted(path for path in log_dir.glob("*.log") if path.is_file())
    nav_files = sorted(path for path in nav_dir.glob("*") if path.is_file())
    trajectory_files = sorted(path for path in trajectory_dir.glob("*") if path.is_file())
    satellite_files = sorted(path for path in satellite_dir.glob("*") if path.is_file())
    sage_files = sorted(path for path in sage_dir.rglob("*") if path.is_file())

    tracking_channels = channel_file_sets(tracking_files, TRACKING_FILE_RE)
    telemetry_channels = channel_file_sets(telemetry_files, TELEMETRY_FILE_RE)
    tracking_by_channel, nav_prn_channels = parse_log_mappings(log_files)

    tracking_mat_channels = tracking_channels["mat"]
    telemetry_mat_channels = telemetry_channels["mat"]
    eligible_channels = tracking_mat_channels & telemetry_mat_channels
    available_map: dict[str, list[int]] = {}
    for prn, channels in sorted(nav_prn_channels.items()):
        usable = sorted(channels & eligible_channels)
        if usable:
            available_map[prn] = usable

    for prn, channels in available_map.items():
        for channel in channels:
            if prn not in tracking_by_channel.get(channel, set()):
                warnings.append(f"nav_mapping_without_tracking_start:{prn}:ch{channel}")

    if not log_files:
        warnings.append("gnss_sdr_log_missing")
    if tracking_files and not tracking_by_channel:
        warnings.append("tracking_mapping_not_found_in_log")
    if telemetry_files and not available_map:
        warnings.append("no_available_prn_mapping")

    tracking_map_json = {
        f"ch{channel}": sorted(prns)
        for channel, prns in sorted(tracking_by_channel.items())
    }
    all_tracking_channels = sorted(tracking_channels["dat"] | tracking_channels["mat"])
    all_telemetry_channels = sorted(
        telemetry_channels["dat"] | telemetry_channels["mat"]
    )

    summary_files = [
        path
        for path in satellite_files
        if path.name.endswith("_satellite_elevation_summary.csv")
    ]
    satellite_prns, satellite_warnings = read_satellite_prns(summary_files)
    warnings.extend(satellite_warnings)

    satellite_status = str(
        nested(metadata, "processing_status", "satellite_geometry", default="unknown")
    )
    satellite_completed = (
        satellite_status == "completed"
        and len(summary_files) > 0
        and any(
            path.name.endswith("_satellite_elevation_timeseries.csv")
            for path in satellite_files
        )
    )

    metadata_sage_status = str(
        nested(metadata, "processing_status", "sage", default="unknown")
    )
    if sage_files and metadata_sage_status == "completed":
        sage_status = "completed"
    elif sage_files:
        sage_status = "files_present_metadata_not_completed"
        warnings.append(f"sage_metadata_status:{metadata_sage_status}")
    else:
        sage_status = metadata_sage_status

    telemetry_dat_count = sum(path.suffix.lower() == ".dat" for path in telemetry_files)
    telemetry_mat_count = sum(path.suffix.lower() == ".mat" for path in telemetry_files)
    telemetry_crc_count = sum(
        path.name.lower().endswith(".txt") and "crc" in path.name.lower()
        for path in telemetry_files
    )

    return {
        "scene_id": scene_id,
        "scene_role": metadata.get("scene_role", "standard_scene"),
        "signal_type": nested(metadata, "signal", "signal_type"),
        "sampling_rate_hz": nested(metadata, "signal", "sample_rate_hz"),
        "raw_path": nested(metadata, "raw_iq", "path"),
        "raw_storage_mode": nested(metadata, "raw_iq", "storage_mode"),
        "gnss_sdr_status": nested(metadata, "gnss_sdr", "run_status"),
        "tracking_exists": bool_text(bool(tracking_files)),
        "tracking_file_count": len(tracking_files),
        "tracking_dat_count": sum(path.suffix.lower() == ".dat" for path in tracking_files),
        "tracking_mat_count": sum(path.suffix.lower() == ".mat" for path in tracking_files),
        "tracking_channels": ";".join(f"ch{value}" for value in all_tracking_channels),
        "tracking_channel_prn_map": compact_json(tracking_map_json),
        "telemetry_exists": bool_text(bool(telemetry_files)),
        "telemetry_file_count": len(telemetry_files),
        "telemetry_dat_count": telemetry_dat_count,
        "telemetry_mat_count": telemetry_mat_count,
        "telemetry_crc_count": telemetry_crc_count,
        "telemetry_channels": ";".join(f"ch{value}" for value in all_telemetry_channels),
        "observables_exists": bool_text(bool(observable_files)),
        "observables_file_count": len(observable_files),
        "rinex_nav_exists": bool_text(bool(nav_files)),
        "rinex_nav_file_count": len(nav_files),
        "rinex_nav_files": ";".join(relative_file_list(nav_files, scene_path)),
        "trajectory_exists": bool_text(bool(trajectory_files)),
        "trajectory_file_count": len(trajectory_files),
        "trajectory_files": ";".join(relative_file_list(trajectory_files, scene_path)),
        "satellite_geometry_status": satellite_status,
        "satellite_geometry_completed": bool_text(satellite_completed),
        "satellite_geometry_file_count": len(satellite_files),
        "satellite_geometry_prns": ";".join(sorted(satellite_prns)),
        "available_prn_count": len(available_map),
        "available_prns": ";".join(sorted(available_map)),
        "prn_tracking_channel_map": compact_json(available_map),
        "sage_results_status": sage_status,
        "sage_results_exists": bool_text(bool(sage_files)),
        "sage_result_file_count": len(sage_files),
        "inventory_warnings": ";".join(sorted(set(warnings))),
    }


def write_inventory_atomic(output_path: Path, rows: Sequence[dict[str, object]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Generate the SAGE dataset inventory CSV.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=default_root,
        help=f"Project root (default: {default_root})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV (default: PROJECT_ROOT/dataset/dataset_inventory.csv)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.expanduser().resolve()
    scenes_root = project_root / "scenes"
    if not scenes_root.is_dir():
        raise SystemExit(f"scenes directory not found: {scenes_root}")
    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else project_root / "dataset" / "dataset_inventory.csv"
    )

    rows = [
        scene_inventory(scene_path)
        for scene_path in sorted(path for path in scenes_root.iterdir() if path.is_dir())
    ]
    write_inventory_atomic(output_path, rows)
    completed_geometry = sum(
        row["satellite_geometry_completed"] == "true" for row in rows
    )
    with_available_prns = sum(int(row["available_prn_count"]) > 0 for row in rows)
    sage_completed = sum(row["sage_results_status"] == "completed" for row in rows)
    print(f"Inventory: {output_path}")
    print(f"Scenes: {len(rows)}")
    print(f"Satellite geometry completed: {completed_geometry}")
    print(f"Scenes with available PRNs: {with_available_prns}")
    print(f"SAGE completed: {sage_completed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

