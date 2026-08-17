#!/usr/bin/env python3
"""Prepare scene-level trajectory NMEA files from GNSS-SDR outputs.

The tool copies, but never moves, each scene's trajectory NMEA file from
``gnss_sdr/nmea`` to ``trajectory``. The reference scene is read-only: its
existing target is compared and logged, never overwritten. No raw IQ data is
read and no GNSS-SDR, SAGE, MATLAB, or satellite geometry process is run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


REFERENCE_SCENE_ID = "F1023_V70_D0117_P2"


class TrajectoryPreparationError(RuntimeError):
    """Base class for per-scene trajectory preparation failures."""


class InputValidationError(TrajectoryPreparationError):
    """Raised when scene input or metadata is invalid."""


class ExistingFileConflict(TrajectoryPreparationError):
    """Raised when an existing destination differs from its source."""


@dataclass(frozen=True)
class FileOutcome:
    source: Path
    destination: Path
    action: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class SceneResult:
    scene_id: str
    status: str
    duration_seconds: float
    outcome: FileOutcome | None = None
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identify_trajectory_nmea(scene_path: Path, scene_id: str) -> Path:
    source_dir = scene_path / "gnss_sdr" / "nmea"
    if not source_dir.is_dir():
        raise InputValidationError(f"NMEA source directory not found: {source_dir}")

    expected = source_dir / f"{scene_id}_trajectory.nmea"
    candidates = sorted(path for path in source_dir.glob("*.nmea") if path.is_file())
    if expected.is_file():
        return expected
    if len(candidates) == 1:
        return candidates[0]
    raise InputValidationError(
        f"expected {expected.name} or exactly one *.nmea file in {source_dir}; "
        f"found {len(candidates)}"
    )


def compare_existing(source: Path, destination: Path) -> FileOutcome:
    source_size = source.stat().st_size
    source_hash = sha256_file(source)
    if not destination.is_file():
        raise ExistingFileConflict(f"destination is missing: {destination}")
    destination_size = destination.stat().st_size
    destination_hash = sha256_file(destination)
    if source_size != destination_size or source_hash != destination_hash:
        raise ExistingFileConflict(
            f"destination differs: source={source} size={source_size} "
            f"sha256={source_hash}; destination={destination} "
            f"size={destination_size} sha256={destination_hash}"
        )
    return FileOutcome(
        source=source,
        destination=destination,
        action="skipped_identical",
        size_bytes=source_size,
        sha256=source_hash,
    )


def copy_verified(source: Path, destination: Path, dry_run: bool) -> FileOutcome:
    source_size = source.stat().st_size
    source_hash = sha256_file(source)
    if destination.exists():
        return compare_existing(source, destination)
    if dry_run:
        return FileOutcome(
            source=source,
            destination=destination,
            action="would_copy",
            size_bytes=source_size,
            sha256=source_hash,
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with source.open("rb") as source_handle, temporary.open("xb") as temp_handle:
            shutil.copyfileobj(source_handle, temp_handle, length=1024 * 1024)
            temp_handle.flush()
            os.fsync(temp_handle.fileno())

        copied_size = temporary.stat().st_size
        copied_hash = sha256_file(temporary)
        if copied_size != source_size or copied_hash != source_hash:
            raise TrajectoryPreparationError(
                f"copy verification failed for {source}: expected size={source_size} "
                f"sha256={source_hash}, got size={copied_size} sha256={copied_hash}"
            )
        temporary.rename(destination)
    finally:
        if temporary.exists():
            temporary.unlink()

    return FileOutcome(
        source=source,
        destination=destination,
        action="copied",
        size_bytes=source_size,
        sha256=source_hash,
    )


def load_metadata(metadata_path: Path, scene_id: str) -> dict[str, object]:
    if not metadata_path.is_file():
        raise InputValidationError(f"metadata file not found: {metadata_path}")
    try:
        with metadata_path.open("r", encoding="utf-8-sig") as handle:
            metadata = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputValidationError(f"invalid metadata {metadata_path}: {error}") from error
    if not isinstance(metadata, dict):
        raise InputValidationError(f"metadata root is not an object: {metadata_path}")
    if metadata.get("scene_id") != scene_id:
        raise InputValidationError(
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


def update_metadata(
    metadata_path: Path,
    metadata: dict[str, object],
    scene_path: Path,
    outcome: FileOutcome,
) -> None:
    processing_status = metadata.setdefault("processing_status", {})
    available_data = metadata.setdefault("available_data", {})
    if not isinstance(processing_status, dict) or not isinstance(available_data, dict):
        raise InputValidationError(
            f"processing_status/available_data must be objects: {metadata_path}"
        )
    processing_status["trajectory"] = "completed"
    available_data["trajectory"] = "available"
    metadata["trajectory"] = {
        "status": "completed",
        "source": "gnss_sdr/nmea",
        "destination": "trajectory",
        "source_file": outcome.source.relative_to(scene_path).as_posix(),
        "file": outcome.destination.relative_to(scene_path).as_posix(),
        "sha256": outcome.sha256,
        "preparation_method": "copy",
        "prepared_at": utc_now(),
    }
    write_metadata_atomic(metadata_path, metadata)


def log_result(log: BatchLog, result: SceneResult) -> None:
    outcome = result.outcome
    log.write(
        f"scene_id={result.scene_id} status={result.status} "
        f"source={outcome.source if outcome else '-'} "
        f"destination={outcome.destination if outcome else '-'} "
        f"file_action={outcome.action if outcome else '-'} "
        f"size_bytes={outcome.size_bytes if outcome else 0} "
        f"sha256={outcome.sha256 if outcome else '-'} "
        f"duration_seconds={result.duration_seconds:.6f} "
        f"error={result.error or '-'}"
    )


def process_scene(scene_path: Path, dry_run: bool, log: BatchLog) -> SceneResult:
    started = time.perf_counter()
    scene_id = scene_path.name
    try:
        metadata_path = scene_path / "metadata.json"
        metadata = load_metadata(metadata_path, scene_id)
        source = identify_trajectory_nmea(scene_path, scene_id)
        destination = scene_path / "trajectory" / source.name

        if scene_id == REFERENCE_SCENE_ID:
            try:
                outcome = compare_existing(source, destination)
                result = SceneResult(
                    scene_id=scene_id,
                    status="skipped_identical",
                    duration_seconds=time.perf_counter() - started,
                    outcome=outcome,
                )
            except ExistingFileConflict as error:
                result = SceneResult(
                    scene_id=scene_id,
                    status="preserved_existing_conflict",
                    duration_seconds=time.perf_counter() - started,
                    error=str(error),
                )
            log_result(log, result)
            return result

        outcome = copy_verified(source, destination, dry_run)
        if dry_run:
            status = "dry_run"
        else:
            compare_existing(source, destination)
            update_metadata(metadata_path, metadata, scene_path, outcome)
            status = "completed" if outcome.action == "copied" else "skipped_identical"
        result = SceneResult(
            scene_id=scene_id,
            status=status,
            duration_seconds=time.perf_counter() - started,
            outcome=outcome,
        )
    except Exception as error:  # Keep failures isolated to one scene.
        result = SceneResult(
            scene_id=scene_id,
            status=(
                "conflict_existing"
                if isinstance(error, ExistingFileConflict)
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
        description="Copy GNSS-SDR trajectory NMEA files into scene trajectory directories."
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
        help="Process only this scene ID; may be specified more than once.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without copying files or updating metadata.",
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
        / f"trajectory_prepare_{timestamp}.log"
    )
    results: list[SceneResult] = []
    with BatchLog(log_path) as log:
        log.write(
            f"batch_start project_root={project_root} scenes={len(scene_paths)} "
            f"dry_run={args.dry_run}"
        )
        for scene_path in scene_paths:
            result = process_scene(scene_path, args.dry_run, log)
            results.append(result)
            copied = int(result.outcome is not None and result.outcome.action == "copied")
            size = result.outcome.size_bytes if result.outcome else 0
            print(
                f"{result.scene_id}: {result.status}; copied={copied}; "
                f"size_bytes={size}; duration_seconds={result.duration_seconds:.3f}"
            )

        counts: dict[str, int] = {}
        for result in results:
            counts[result.status] = counts.get(result.status, 0) + 1
        copied_files = sum(
            1
            for result in results
            if result.outcome is not None and result.outcome.action == "copied"
        )
        copied_bytes = sum(
            result.outcome.size_bytes
            for result in results
            if result.outcome is not None and result.outcome.action == "copied"
        )
        summary = ",".join(f"{key}:{counts[key]}" for key in sorted(counts))
        log.write(
            f"batch_complete status_counts={summary} copied_files={copied_files} "
            f"copied_bytes={copied_bytes}"
        )

    print(f"Log: {log_path}")
    print(
        "Summary: "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    )
    failed = sum(
        count
        for status, count in counts.items()
        if status in {"failed", "conflict_existing"}
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

