#!/usr/bin/env python3
"""Prepare scene-level RINEX navigation directories from GNSS-SDR outputs.

This tool copies (never moves) RINEX NAV/OBS files from each scene's
``gnss_sdr/rinex`` directory into the standardized ``navigation`` tree.  It
does not read raw IQ data and does not run GNSS-SDR, SAGE, MATLAB, or satellite
geometry processing.

The reference scene is read-only: existing navigation files are compared with
the GNSS-SDR sources and the result is logged, but neither its files nor its
metadata are modified.
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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


REFERENCE_SCENE_ID = "F1023_V70_D0117_P2"


class NavigationPreparationError(RuntimeError):
    """Base class for per-scene preparation failures."""


class InputValidationError(NavigationPreparationError):
    """Raised when a scene does not have exactly one NAV and one OBS file."""


class ExistingFileConflict(NavigationPreparationError):
    """Raised when a destination exists but differs from its source."""


@dataclass(frozen=True)
class FileOutcome:
    source: Path
    destination: Path
    action: str
    size_bytes: int
    sha256: str


@dataclass
class SceneResult:
    scene_id: str
    status: str
    duration_seconds: float
    files: list[FileOutcome] = field(default_factory=list)
    error: str = ""

    @property
    def copied_files(self) -> list[Path]:
        return [item.destination for item in self.files if item.action == "copied"]

    @property
    def total_size_bytes(self) -> int:
        return sum(item.size_bytes for item in self.files)


class BatchLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = path.open("x", encoding="utf-8", newline="\n")

    def close(self) -> None:
        self._handle.close()

    def write(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self._handle.write(f"{timestamp} {message}\n")
        self._handle.flush()

    def __enter__(self) -> "BatchLog":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


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


def find_single_input(source_dir: Path, pattern: str, label: str) -> Path:
    matches = sorted(path for path in source_dir.glob(pattern) if path.is_file())
    if len(matches) != 1:
        raise InputValidationError(
            f"expected exactly one {label} file matching {pattern} in "
            f"{source_dir}, found {len(matches)}"
        )
    return matches[0]


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
            raise NavigationPreparationError(
                f"copy verification failed for {source}: expected size={source_size} "
                f"sha256={source_hash}, got size={copied_size} sha256={copied_hash}"
            )

        # On Windows, rename fails rather than replacing if the destination was
        # created concurrently. This preserves the no-overwrite invariant.
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


def load_metadata(metadata_path: Path, expected_scene_id: str) -> dict[str, object]:
    if not metadata_path.is_file():
        raise InputValidationError(f"metadata file not found: {metadata_path}")
    try:
        with metadata_path.open("r", encoding="utf-8-sig") as handle:
            metadata = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputValidationError(f"invalid metadata: {metadata_path}: {error}") from error
    if not isinstance(metadata, dict):
        raise InputValidationError(f"metadata root is not an object: {metadata_path}")
    if metadata.get("scene_id") != expected_scene_id:
        raise InputValidationError(
            f"metadata scene_id {metadata.get('scene_id')!r} does not match "
            f"directory {expected_scene_id!r}"
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


def update_navigation_metadata(
    metadata_path: Path,
    metadata: dict[str, object],
    scene_path: Path,
    outcomes: Sequence[FileOutcome],
) -> None:
    processing_status = metadata.setdefault("processing_status", {})
    available_data = metadata.setdefault("available_data", {})
    if not isinstance(processing_status, dict) or not isinstance(available_data, dict):
        raise InputValidationError(
            f"processing_status/available_data must be objects: {metadata_path}"
        )

    processing_status["navigation"] = "completed"
    available_data["navigation"] = "available"

    nav_outcome = next(item for item in outcomes if item.destination.suffix.upper() == ".26N")
    obs_outcome = next(item for item in outcomes if item.destination.suffix.upper() == ".26O")
    metadata["navigation"] = {
        "status": "completed",
        "source": "gnss_sdr/rinex",
        "destination": {
            "rinex_nav": "navigation/rinex_nav",
            "rinex_obs": "navigation/rinex_obs",
        },
        "files": {
            "rinex_nav": nav_outcome.destination.relative_to(scene_path).as_posix(),
            "rinex_obs": obs_outcome.destination.relative_to(scene_path).as_posix(),
        },
        "source_files": {
            "rinex_nav": nav_outcome.source.relative_to(scene_path).as_posix(),
            "rinex_obs": obs_outcome.source.relative_to(scene_path).as_posix(),
        },
        "sha256": {
            "rinex_nav": nav_outcome.sha256,
            "rinex_obs": obs_outcome.sha256,
        },
        "preparation_method": "copy",
        "prepared_at": utc_now(),
    }
    write_metadata_atomic(metadata_path, metadata)


def format_paths(paths: Sequence[Path]) -> str:
    return ";".join(str(path) for path in paths) if paths else "-"


def process_scene(scene_path: Path, dry_run: bool, log: BatchLog) -> SceneResult:
    started = time.perf_counter()
    scene_id = scene_path.name
    metadata_path = scene_path / "metadata.json"
    outcomes: list[FileOutcome] = []

    try:
        metadata = load_metadata(metadata_path, scene_id)
        source_dir = scene_path / "gnss_sdr" / "rinex"
        nav_source = find_single_input(source_dir, "*.26N", "RINEX NAV")
        obs_source = find_single_input(source_dir, "*.26O", "RINEX OBS")
        nav_destination = scene_path / "navigation" / "rinex_nav" / nav_source.name
        obs_destination = scene_path / "navigation" / "rinex_obs" / obs_source.name

        if scene_id == REFERENCE_SCENE_ID:
            conflicts: list[str] = []
            for source, destination in (
                (nav_source, nav_destination),
                (obs_source, obs_destination),
            ):
                try:
                    outcomes.append(compare_existing(source, destination))
                except ExistingFileConflict as error:
                    conflicts.append(str(error))

            duration = time.perf_counter() - started
            if conflicts:
                result = SceneResult(
                    scene_id=scene_id,
                    status="preserved_existing_conflict",
                    duration_seconds=duration,
                    files=outcomes,
                    error=" | ".join(conflicts),
                )
            else:
                result = SceneResult(
                    scene_id=scene_id,
                    status="skipped_identical",
                    duration_seconds=duration,
                    files=outcomes,
                )
            log_scene_result(log, result, [nav_source, obs_source])
            return result

        outcomes.append(copy_verified(nav_source, nav_destination, dry_run))
        outcomes.append(copy_verified(obs_source, obs_destination, dry_run))

        if not dry_run:
            # Re-check final destinations before declaring the scene complete.
            for outcome in outcomes:
                compare_existing(outcome.source, outcome.destination)
            update_navigation_metadata(
                metadata_path, metadata, scene_path, outcomes
            )
            status = (
                "completed"
                if any(item.action == "copied" for item in outcomes)
                else "skipped_identical"
            )
        else:
            status = "dry_run"

        result = SceneResult(
            scene_id=scene_id,
            status=status,
            duration_seconds=time.perf_counter() - started,
            files=outcomes,
        )
        log_scene_result(log, result, [nav_source, obs_source])
        return result
    except Exception as error:  # Per-scene isolation is intentional.
        result = SceneResult(
            scene_id=scene_id,
            status=(
                "conflict_existing"
                if isinstance(error, ExistingFileConflict)
                else "failed"
            ),
            duration_seconds=time.perf_counter() - started,
            files=outcomes,
            error=f"{type(error).__name__}: {error}",
        )
        log_scene_result(log, result, [])
        return result


def log_scene_result(
    log: BatchLog, result: SceneResult, source_files: Sequence[Path]
) -> None:
    copied = result.copied_files
    outputs = [item.destination for item in result.files]
    log.write(
        f"scene_id={result.scene_id} status={result.status} "
        f"source_files={format_paths(source_files)} "
        f"copied_files={format_paths(copied)} "
        f"output_files={format_paths(outputs)} "
        f"size_bytes={result.total_size_bytes} "
        f"duration_seconds={result.duration_seconds:.6f} "
        f"error={result.error or '-'}"
    )
    for item in result.files:
        log.write(
            f"scene_id={result.scene_id} file_status={item.action} "
            f"source={item.source} destination={item.destination} "
            f"size_bytes={item.size_bytes} sha256={item.sha256}"
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Copy GNSS-SDR RINEX files into standardized navigation directories."
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
        help="Validate and report actions without copying files or updating metadata.",
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
    found_ids = {path.name for path in scene_paths}
    missing_ids = sorted(selected - found_ids)
    if missing_ids:
        print(
            "ERROR: requested scene(s) not found: " + ", ".join(missing_ids),
            file=sys.stderr,
        )
        return 2

    logs_root = project_root / "dataset_generation_logs"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = logs_root / f"navigation_prepare_{timestamp}.log"
    results: list[SceneResult] = []

    with BatchLog(log_path) as log:
        log.write(
            f"batch_start project_root={project_root} scenes={len(scene_paths)} "
            f"dry_run={args.dry_run}"
        )
        for scene_path in scene_paths:
            result = process_scene(scene_path, args.dry_run, log)
            results.append(result)
            print(
                f"{result.scene_id}: {result.status}; "
                f"copied={len(result.copied_files)}; "
                f"size_bytes={result.total_size_bytes}; "
                f"duration_seconds={result.duration_seconds:.3f}"
            )

        counts: dict[str, int] = {}
        for result in results:
            counts[result.status] = counts.get(result.status, 0) + 1
        total_copied_files = sum(len(result.copied_files) for result in results)
        total_copied_bytes = sum(
            item.size_bytes
            for result in results
            for item in result.files
            if item.action == "copied"
        )
        summary = ",".join(f"{key}:{counts[key]}" for key in sorted(counts))
        log.write(
            f"batch_complete status_counts={summary} "
            f"copied_files={total_copied_files} "
            f"copied_bytes={total_copied_bytes}"
        )

    print(f"Log: {log_path}")
    print(
        "Summary: "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    )
    failures = sum(
        count
        for status, count in counts.items()
        if status in {"failed", "conflict_existing"}
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

