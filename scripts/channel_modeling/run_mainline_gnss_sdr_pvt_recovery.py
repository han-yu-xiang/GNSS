#!/usr/bin/env python3
"""Create a separate Stage2 position overlay from existing GNSS-SDR PVT dumps."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.channel_modeling.mainline_gnss_sdr_pvt_recovery import (
    PVT_OVERLAY_FIELDS,
    PVT_RECORD,
    PvtSolution,
    build_pvt_position_overlay,
    parse_pvt_dump,
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
GEOMETRY_FIELDS = ("run_id", "window_id", "scene_id", "prn", "tracking_channel", "window_utc")
TRAJECTORY_REQUIRED_FIELDS = (
    "run_id", "window_id", "scene_id", "prn", "tracking_channel", "window_utc",
    "position_utc", "position_delta_seconds", "position_source_path",
    "position_source_record_id", "latitude_deg", "longitude_deg", "position_status",
    "missing_reason",
)
SUMMARY_FIELDS = (
    "scene_id", "window_count", "original_nmea_position_count",
    "pvt_position_recovered_count", "position_matched_after_recovery_count",
    "position_still_missing_count", "ambiguous_pvt_epoch_window_count",
    "no_valid_pvt_fix_window_count", "pvt_record_count",
    "valid_single_point_record_count", "unique_pvt_epoch_count",
    "duplicate_epoch_record_count", "pvt_rx_tow_offset_median_ms",
    "pvt_rx_tow_offset_max_abs_ms",
)
SUMMARY_SUM_FIELDS = (
    "window_count", "original_nmea_position_count",
    "pvt_position_recovered_count", "position_matched_after_recovery_count",
    "position_still_missing_count", "ambiguous_pvt_epoch_window_count",
    "no_valid_pvt_fix_window_count", "pvt_record_count",
    "valid_single_point_record_count", "unique_pvt_epoch_count",
    "duplicate_epoch_record_count",
)


def _read_csv(path: Path, required_fields: Sequence[str]) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        missing = set(required_fields) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing fields {sorted(missing)}: {path}")
        return [dict(row) for row in reader], list(reader.fieldnames)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"input path is outside the project root: {path}") from exc


def _read_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        content = line.split(";", 1)[0].strip()
        if "=" in content:
            key, value = content.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def _load_scene_pvt(project_root: Path, scene: str) -> tuple[Path, list[PvtSolution], dict[str, object]]:
    scene_root = project_root / "scenes" / scene
    pvt_path = scene_root / "gnss_sdr" / "pvt" / f"{scene}_pvt.dat"
    config_path = scene_root / "gnss_sdr" / "config" / f"{scene}.conf"
    status_path = scene_root / "gnss_sdr" / "run_status.json"
    for path in (pvt_path, config_path, status_path):
        if not path.is_file():
            raise ValueError(f"required existing GNSS-SDR file is missing: {path}")

    config = _read_config(config_path)
    if config.get("PVT.dump", "").lower() != "true":
        raise ValueError(f"historical config does not enable PVT.dump for {scene}")
    if config.get("PVT.positioning_mode", "").lower() != "single":
        raise ValueError(f"unexpected historical PVT positioning mode for {scene}")
    status = json.loads(status_path.read_text(encoding="utf-8-sig"))
    if status.get("status") != "SUCCESS" or status.get("return_code") != 0:
        raise ValueError(f"historical GNSS-SDR run is not recorded as successful for {scene}")

    raw = pvt_path.read_bytes()
    records = parse_pvt_dump(raw)
    if not records:
        raise ValueError(f"PVT dump contains no complete records for {scene}")
    counts = Counter((record.solution_status, record.solution_type) for record in records)
    valid = [record for record in records if record.is_valid_single_point]
    if not valid:
        raise ValueError(f"PVT dump has no valid single-point XYZ solutions for {scene}")
    unique_epochs = {record.position_utc for record in records}
    rx_tow_offsets_ms = [
        1000.0 * (record.rx_time_s - record.tow_ms / 1000.0)
        for record in records
    ]
    pdops = sorted(record.pdop for record in valid)
    valid_satellites = [record.valid_satellites for record in valid]
    pdop_p95 = pdops[max(0, math.ceil(0.95 * len(pdops)) - 1)]
    audit = {
        "pvt_dump": {
            "relative_path": _relative(pvt_path, project_root),
            "sha256": _sha256(pvt_path),
            "size_bytes": len(raw),
            "record_size_bytes": PVT_RECORD.size,
            "record_count": len(records),
            "solution_status_type_counts": {
                f"{status_code}/{type_code}": count
                for (status_code, type_code), count in sorted(counts.items())
            },
            "valid_single_point_xyz_count": len(valid),
            "unique_epoch_count": len(unique_epochs),
            "duplicate_epoch_record_count": len(records) - len(unique_epochs),
            "rx_tow_offset_min_ms": min(rx_tow_offsets_ms),
            "rx_tow_offset_median_ms": statistics.median(rx_tow_offsets_ms),
            "rx_tow_offset_max_ms": max(rx_tow_offsets_ms),
            "rx_tow_offset_max_abs_ms": max(abs(value) for value in rx_tow_offsets_ms),
            "valid_fix_quality": {
                "valid_satellites_min": min(valid_satellites),
                "valid_satellites_median": statistics.median(valid_satellites),
                "valid_satellites_max": max(valid_satellites),
                "pdop_median": statistics.median(pdops),
                "pdop_p95": pdop_p95,
                "pdop_max": max(pdops),
            },
            "gps_time_start_utc": min(record.position_utc for record in records).isoformat().replace("+00:00", "Z"),
            "gps_time_end_utc": max(record.position_utc for record in records).isoformat().replace("+00:00", "Z"),
        },
        "config": {
            "relative_path": _relative(config_path, project_root),
            "sha256": _sha256(config_path),
            "pvt_dump_enabled": config.get("PVT.dump", "").lower() == "true",
            "positioning_mode": config.get("PVT.positioning_mode", ""),
            "output_rate_ms": config.get("PVT.output_rate_ms", ""),
        },
        "run_status": {
            "relative_path": _relative(status_path, project_root),
            "sha256": _sha256(status_path),
            "status": status.get("status"),
            "return_code": status.get("return_code"),
            "duration_seconds": status.get("duration_s"),
            "declared_pvt_file_count": status.get("pvt_file_count"),
        },
    }
    return pvt_path, records, audit


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_outputs(
    project_root: Path,
    geometry_path: Path,
    trajectory_path: Path,
    output_dir: Path,
    *,
    max_position_delta_seconds: float = 0.5,
) -> dict[str, object]:
    geometry, _ = _read_csv(geometry_path, GEOMETRY_FIELDS)
    trajectory, trajectory_header = _read_csv(trajectory_path, TRAJECTORY_REQUIRED_FIELDS)
    if len(geometry) != EXPECTED_WINDOWS:
        raise ValueError(f"expected {EXPECTED_WINDOWS} Stage2 windows, found {len(geometry)}")
    scenes = {row["scene_id"] for row in geometry}
    if scenes != set(EXPECTED_SCENES):
        raise ValueError(f"scene set differs from frozen 13-scene cohort: {sorted(scenes ^ set(EXPECTED_SCENES))}")

    pvt_by_scene: dict[str, list[PvtSolution]] = {}
    pvt_paths: dict[str, str] = {}
    scene_audit: dict[str, dict[str, object]] = {}
    for scene in EXPECTED_SCENES:
        path, records, audit = _load_scene_pvt(project_root, scene)
        pvt_by_scene[scene] = records
        pvt_paths[scene] = _relative(path, project_root)
        scene_audit[scene] = audit

    merged, overlay = build_pvt_position_overlay(
        geometry,
        trajectory,
        pvt_by_scene,
        pvt_source_by_scene=pvt_paths,
        max_position_delta_seconds=max_position_delta_seconds,
    )
    keys = [(row["run_id"], row["window_id"]) for row in merged]
    if len(merged) != EXPECTED_WINDOWS or len(set(keys)) != EXPECTED_WINDOWS:
        raise ValueError("PVT-recovered overlay must preserve 7,847 unique Stage2 identities")

    original_by_key = {(row["run_id"], row["window_id"]): row for row in trajectory}
    if set(keys) != set(original_by_key):
        raise ValueError("PVT-recovered identity set differs from the original trajectory overlay")
    by_scene: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in overlay:
        by_scene[row["scene_id"]].append(row)
    summary: list[dict[str, object]] = []
    scene_counts: dict[str, dict[str, int | str]] = {}
    for scene in EXPECTED_SCENES:
        rows = by_scene[scene]
        original_count = sum(row["original_position_status"] == "POSITION_MATCHED" for row in rows)
        recovered = sum(row["position_recovery_status"] == "RECOVERED_FROM_PVT_SINGLE" for row in rows)
        still_missing = sum(row["position_recovery_status"] not in {"RECOVERED_FROM_PVT_SINGLE", "PRESERVED_EXISTING_POSITION"} for row in rows)
        ambiguous = sum(row["position_recovery_status"] == "AMBIGUOUS_PVT_SOLUTIONS_AT_EPOCH" for row in rows)
        no_fix = sum(row["position_recovery_status"] == "NO_VALID_PVT_FIX_WITHIN_TOLERANCE" for row in rows)
        pvt_audit = scene_audit[scene]["pvt_dump"]
        counts = {
            "window_count": len(rows),
            "original_nmea_position_count": original_count,
            "pvt_position_recovered_count": recovered,
            "position_matched_after_recovery_count": original_count + recovered,
            "position_still_missing_count": still_missing,
            "ambiguous_pvt_epoch_window_count": ambiguous,
            "no_valid_pvt_fix_window_count": no_fix,
            "pvt_record_count": int(pvt_audit["record_count"]),
            "valid_single_point_record_count": int(pvt_audit["valid_single_point_xyz_count"]),
            "unique_pvt_epoch_count": int(pvt_audit["unique_epoch_count"]),
            "duplicate_epoch_record_count": int(pvt_audit["duplicate_epoch_record_count"]),
            "pvt_rx_tow_offset_median_ms": f"{float(pvt_audit['rx_tow_offset_median_ms']):.3f}",
            "pvt_rx_tow_offset_max_abs_ms": f"{float(pvt_audit['rx_tow_offset_max_abs_ms']):.3f}",
        }
        scene_counts[scene] = counts
        summary.append({"scene_id": scene, **counts})
    totals: dict[str, int | str] = {
        field: sum(int(item[field]) for item in scene_counts.values())
        for field in SUMMARY_SUM_FIELDS
    }
    all_rx_tow_offsets_ms = [
        1000.0 * (record.rx_time_s - record.tow_ms / 1000.0)
        for records in pvt_by_scene.values()
        for record in records
    ]
    totals["pvt_rx_tow_offset_median_ms"] = f"{statistics.median(all_rx_tow_offsets_ms):.3f}"
    totals["pvt_rx_tow_offset_max_abs_ms"] = (
        f"{max(abs(value) for value in all_rx_tow_offsets_ms):.3f}"
    )
    if totals["window_count"] != EXPECTED_WINDOWS:
        raise ValueError("per-scene PVT recovery counts do not sum to the full cohort")
    if totals["original_nmea_position_count"] != 5540:
        raise ValueError("original NMEA position baseline changed from 5,540")
    if totals["position_matched_after_recovery_count"] + totals["position_still_missing_count"] != EXPECTED_WINDOWS:
        raise ValueError("recovered and missing position counts do not reconcile")
    summary.append({"scene_id": "TOTAL", **totals})

    pvt_status_counts: dict[str, int] = defaultdict(int)
    for scene in pvt_by_scene:
        for record in pvt_by_scene[scene]:
            pvt_status_counts[f"{record.solution_status}/{record.solution_type}"] += 1
    audit = {
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "method": "direct time match to saved RTKLIB single-point PVT dump; GPS week/RX_time converted with 18 s GPS-UTC; telemetry TOW retained as a separate channel-symbol diagnostic; no interpolation/extrapolation",
        "position_source": "GNSS_SDR_PVT_SINGLE",
        "rtklib_solution_status_single": 5,
        "rtklib_solution_type_xyz": 0,
        "minimum_valid_satellites": 4,
        "maximum_time_delta_seconds": max_position_delta_seconds,
        "window_identity_count": len(keys),
        "unique_run_window_identity_count": len(set(keys)),
        "original_position_count": totals["original_nmea_position_count"],
        "pvt_recovered_position_count": totals["pvt_position_recovered_count"],
        "position_matched_after_recovery_count": totals["position_matched_after_recovery_count"],
        "position_still_missing_count": totals["position_still_missing_count"],
        "ambiguous_pvt_epoch_window_count": totals["ambiguous_pvt_epoch_window_count"],
        "solution_status_type_counts": dict(sorted(pvt_status_counts.items())),
        "scene_pvt_audit": scene_audit,
        "input_files": {
            _relative(geometry_path, project_root): {"sha256": _sha256(geometry_path), "size_bytes": geometry_path.stat().st_size},
            _relative(trajectory_path, project_root): {"sha256": _sha256(trajectory_path), "size_bytes": trajectory_path.stat().st_size},
        },
        "coordinates_in_audit": False,
        "original_geometry_overlay_modified": False,
        "original_trajectory_overlay_modified": False,
        "stage2_ledger_modified": False,
        "task5_cir_modified": False,
        "gnss_sdr_rerun": False,
    }

    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(output_dir / "trajectory_pvt_recovery_overlay.csv", PVT_OVERLAY_FIELDS, overlay)
    _write_csv(output_dir / "trajectory_pvt_recovery_by_scene.csv", SUMMARY_FIELDS, summary)
    merged_fields = list(trajectory_header)
    if "position_source" not in merged_fields:
        merged_fields.append("position_source")
    _write_csv(output_dir / "trajectory_window_overlay_pvt_recovered.csv", merged_fields, merged)
    with (output_dir / "trajectory_pvt_recovery_audit.json").open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return audit


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--geometry-overlay", type=Path, required=True)
    parser.add_argument("--trajectory-overlay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-position-delta-seconds", type=float, default=0.5)
    args = parser.parse_args(argv)
    try:
        audit = build_outputs(
            args.project_root.resolve(),
            args.geometry_overlay.resolve(),
            args.trajectory_overlay.resolve(),
            args.output_dir.resolve(),
            max_position_delta_seconds=args.max_position_delta_seconds,
        )
        print(json.dumps(audit, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
