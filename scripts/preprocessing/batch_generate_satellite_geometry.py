#!/usr/bin/env python3
"""Batch-generate satellite geometry for all project scenes."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from satellite_geometry import (
    SatelliteGeometryResult,
    generate_satellite_geometry,
    sha256_file,
)


REFERENCE_SCENE_ID = "F1023_V70_D0117_P2"


@dataclass(frozen=True)
class SceneBatchResult:
    scene_id: str
    status: str
    duration_seconds: float
    geometry: SatelliteGeometryResult | None = None
    error: str = ""


class BatchLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = path.open("x", encoding="utf-8", newline="\n")

    def write(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self._handle.write(f"{timestamp} {message}\n")
        self._handle.flush()

    def __enter__(self) -> "BatchLog":
        return self

    def __exit__(self, *_: object) -> None:
        self._handle.close()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def load_metadata(metadata_path: Path, scene_id: str) -> dict[str, object]:
    if not metadata_path.is_file():
        raise ValueError(f"metadata file not found: {metadata_path}")
    with metadata_path.open("r", encoding="utf-8-sig") as handle:
        metadata = json.load(handle)
    if not isinstance(metadata, dict):
        raise ValueError(f"metadata root is not an object: {metadata_path}")
    if metadata.get("scene_id") != scene_id:
        raise ValueError(
            f"metadata scene_id {metadata.get('scene_id')!r} does not match "
            f"directory {scene_id!r}"
        )
    return metadata


def write_metadata_atomic(metadata_path: Path, metadata: dict[str, object]) -> None:
    temporary = metadata_path.with_name(
        f".{metadata_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(metadata, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, metadata_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def relative_paths(paths: Sequence[Path], scene_path: Path) -> list[str]:
    return [path.relative_to(scene_path).as_posix() for path in paths]


def update_success_metadata(
    metadata_path: Path,
    metadata: dict[str, object],
    scene_path: Path,
    result: SatelliteGeometryResult,
) -> None:
    processing_status = metadata.setdefault("processing_status", {})
    available_data = metadata.setdefault("available_data", {})
    if not isinstance(processing_status, dict) or not isinstance(available_data, dict):
        raise ValueError("processing_status and available_data must be objects")
    processing_status["satellite_geometry"] = "completed"
    available_data["satellite_geometry"] = "available"

    previous = metadata.get("satellite_geometry")
    previous_generated_at = (
        previous.get("generated_at") if isinstance(previous, dict) else None
    )
    generated_at = (
        previous_generated_at
        if result.status == "skipped_existing" and previous_generated_at
        else utc_now()
    )
    metadata["satellite_geometry"] = {
        "status": "completed",
        "sources": ["gnss_sdr/nmea", "navigation/rinex_nav"],
        "input_files": {
            "nmea": relative_paths(result.nmea_files, scene_path),
            "rinex_nav": relative_paths(result.nav_files, scene_path),
        },
        "input_sha256": {
            "nmea": [sha256_file(path) for path in result.nmea_files],
            "rinex_nav": [sha256_file(path) for path in result.nav_files],
        },
        "outputs": relative_paths(result.output_files, scene_path),
        "output_sha256": [sha256_file(path) for path in result.output_files],
        "generated_at": generated_at,
        "statistics": {
            "observation_count": result.observation_count,
            "satellite_count": result.satellite_count,
            "nav_prn_count": result.nav_prn_count,
            "bad_checksum_count": result.bad_checksum_count,
            "untimestamped_gsv_count": result.untimestamped_gsv_count,
            "ignored_prn_count": len(result.ignored_prns),
        },
        "algorithm": {
            "geometry_source": "NMEA_GSV",
            "rinex_nav_usage": "GPS_PRN_filter_only",
            "broadcast_ephemeris_position_recomputation": False,
        },
        "last_batch_status": result.status,
        "error": None,
    }
    write_metadata_atomic(metadata_path, metadata)


def update_failure_metadata(
    metadata_path: Path,
    metadata: dict[str, object],
    error: Exception,
) -> None:
    processing_status = metadata.setdefault("processing_status", {})
    available_data = metadata.setdefault("available_data", {})
    if not isinstance(processing_status, dict) or not isinstance(available_data, dict):
        return
    processing_status["satellite_geometry"] = "failed"
    available_data["satellite_geometry"] = "not_generated"
    metadata["satellite_geometry"] = {
        "status": "failed",
        "sources": ["gnss_sdr/nmea", "navigation/rinex_nav"],
        "last_attempt_at": utc_now(),
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
    }
    write_metadata_atomic(metadata_path, metadata)


def format_paths(paths: Sequence[Path]) -> str:
    return ";".join(str(path) for path in paths) if paths else "-"


def log_result(log: BatchLog, result: SceneBatchResult) -> None:
    geometry = result.geometry
    log.write(
        f"scene_id={result.scene_id} status={result.status} "
        f"nmea_files={format_paths(geometry.nmea_files if geometry else ())} "
        f"nav_files={format_paths(geometry.nav_files if geometry else ())} "
        f"output_files={format_paths(geometry.output_files if geometry else ())} "
        f"observation_count={geometry.observation_count if geometry else 0} "
        f"satellite_count={geometry.satellite_count if geometry else 0} "
        f"nav_prn_count={geometry.nav_prn_count if geometry else 0} "
        f"bad_checksum_count={geometry.bad_checksum_count if geometry else 0} "
        f"untimestamped_gsv_count="
        f"{geometry.untimestamped_gsv_count if geometry else 0} "
        f"ignored_prns={','.join(geometry.ignored_prns) if geometry else '-'} "
        f"duration_seconds={result.duration_seconds:.6f} "
        f"error={result.error or '-'}"
    )


def process_scene(scene_path: Path, log: BatchLog) -> SceneBatchResult:
    started = time.perf_counter()
    scene_id = scene_path.name
    metadata_path = scene_path / "metadata.json"
    metadata: dict[str, object] | None = None
    try:
        metadata = load_metadata(metadata_path, scene_id)
        geometry = generate_satellite_geometry(scene_path, overwrite=False)
        if scene_id != REFERENCE_SCENE_ID:
            update_success_metadata(metadata_path, metadata, scene_path, geometry)
        result = SceneBatchResult(
            scene_id=scene_id,
            status=geometry.status,
            duration_seconds=time.perf_counter() - started,
            geometry=geometry,
        )
    except Exception as error:  # A failed scene must not stop the batch.
        if scene_id != REFERENCE_SCENE_ID and metadata is not None:
            try:
                update_failure_metadata(metadata_path, metadata, error)
            except Exception as metadata_error:
                error = RuntimeError(f"{error}; metadata update failed: {metadata_error}")
        result = SceneBatchResult(
            scene_id=scene_id,
            status=(
                "reference_validation_failed"
                if scene_id == REFERENCE_SCENE_ID
                else "failed"
            ),
            duration_seconds=time.perf_counter() - started,
            error=f"{type(error).__name__}: {error}",
        )
    log_result(log, result)
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Generate NMEA-GSV satellite geometry for project scenes."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=default_root,
        help=f"Project root (default: {default_root})",
    )
    parser.add_argument(
        "--scene",
        action="append",
        dest="scene_ids",
        help="Process only this scene ID; may be supplied more than once.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.expanduser().resolve()
    scenes_root = project_root / "scenes"
    if not scenes_root.is_dir():
        print(f"ERROR: scenes directory not found: {scenes_root}", file=sys.stderr)
        return 2

    selected = set(args.scene_ids or [])
    scene_paths = sorted(
        path
        for path in scenes_root.iterdir()
        if path.is_dir() and (not selected or path.name in selected)
    )
    missing = sorted(selected - {path.name for path in scene_paths})
    if missing:
        print("ERROR: scene(s) not found: " + ", ".join(missing), file=sys.stderr)
        return 2

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = (
        project_root
        / "dataset_generation_logs"
        / f"batch_satellite_geometry_{timestamp}.log"
    )
    results: list[SceneBatchResult] = []
    with BatchLog(log_path) as log:
        log.write(f"batch_start project_root={project_root} scenes={len(scene_paths)}")
        for scene_path in scene_paths:
            result = process_scene(scene_path, log)
            results.append(result)
            geometry = result.geometry
            print(
                f"{result.scene_id}: {result.status}; "
                f"observations={geometry.observation_count if geometry else 0}; "
                f"satellites={geometry.satellite_count if geometry else 0}; "
                f"duration_seconds={result.duration_seconds:.3f}"
            )

        counts: dict[str, int] = {}
        for result in results:
            counts[result.status] = counts.get(result.status, 0) + 1
        generated_files = sum(
            len(result.geometry.output_files)
            for result in results
            if result.geometry is not None and result.geometry.status == "completed"
        )
        summary = ",".join(f"{key}:{counts[key]}" for key in sorted(counts))
        log.write(
            f"batch_complete status_counts={summary} generated_files={generated_files}"
        )

    print(f"Log: {log_path}")
    print(
        "Summary: "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    )
    failures = counts.get("failed", 0) + counts.get("reference_validation_failed", 0)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

