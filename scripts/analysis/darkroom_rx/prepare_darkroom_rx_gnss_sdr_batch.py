"""Prepare an immutable eight-file 0913DarkroomRx GNSS-SDR request.

Preparation reads each raw file once only to compute its SHA-256.  It does not
start WSL or GNSS-SDR and it writes only to a new request namespace under
``dataset_generation_logs/darkroom_rx_gnss_sdr``.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .darkroom_rx_common import (
        EXPECTED_FILENAMES,
        GNSS_SDR_EXECUTABLE,
        GNSS_SDR_VERSION,
        SCHEMA_VERSION,
        WSL_DISTRO,
        canonical_json_bytes,
        estimated_duration_s,
        parse_task_filename,
        render_gnss_sdr_config,
        sha256_file,
        windows_to_wsl_path,
        with_resolved_source,
    )
except ImportError:
    from scripts.analysis.darkroom_rx.darkroom_rx_common import (
        EXPECTED_FILENAMES,
        GNSS_SDR_EXECUTABLE,
        GNSS_SDR_VERSION,
        SCHEMA_VERSION,
        WSL_DISTRO,
        canonical_json_bytes,
        estimated_duration_s,
        parse_task_filename,
        render_gnss_sdr_config,
        sha256_file,
        windows_to_wsl_path,
        with_resolved_source,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REQUEST_ROOT_RELATIVE = Path("dataset_generation_logs/darkroom_rx_gnss_sdr")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def discover_input_tasks(input_dir: Path):
    input_dir = input_dir.resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"input directory does not exist: {input_dir}")
    actual = sorted(path.name.lower() for path in input_dir.glob("*.bin") if path.is_file())
    expected = sorted(EXPECTED_FILENAMES)
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise ValueError(f"input inventory mismatch: missing={missing} extra={extra}")
    tasks = []
    for name in EXPECTED_FILENAMES:
        path = input_dir / name
        if path.stat().st_size <= 0 or path.stat().st_size % 4:
            raise ValueError(f"invalid interleaved int16 I/Q byte length: {path}")
        tasks.append(with_resolved_source(parse_task_filename(path)))
    return tasks


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def _source_provenance(source_files: Mapping[str, Path]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for name, path_value in sorted(source_files.items()):
        path = path_value.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"source file is missing: {name}={path}")
        records[name] = {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return records


def prepare_batch(
    *,
    project_root: Path,
    input_dir: Path,
    request_dir: Path,
    request_id: str,
    source_files: Mapping[str, Path],
) -> tuple[Path, str]:
    project_root = project_root.resolve()
    input_dir = input_dir.resolve()
    request_dir = request_dir.resolve()
    allowed_root = (project_root / REQUEST_ROOT_RELATIVE).resolve()
    if not _is_within(request_dir, allowed_root) or request_dir == allowed_root:
        raise ValueError(f"request directory must be inside {allowed_root}")
    if request_dir.exists():
        raise FileExistsError(f"request namespace already exists: {request_dir}")
    if request_dir.name != request_id:
        raise ValueError("request directory basename must equal request_id")

    tasks = discover_input_tasks(input_dir)
    request_dir.mkdir(parents=True)
    configs_dir = request_dir / "configs"
    configs_dir.mkdir()
    (request_dir / "runs").mkdir()

    rows: list[dict[str, object]] = []
    for task in tasks:
        source = task.source_path
        size_bytes = source.stat().st_size
        output_path = request_dir / "runs" / task.task_id
        config_path = configs_dir / f"{task.task_id}.conf"
        output_wsl = windows_to_wsl_path(output_path)
        config_text = render_gnss_sdr_config(
            task=task,
            input_wsl_path=windows_to_wsl_path(source),
            output_wsl_root=output_wsl,
        )
        _write_exclusive(config_path, config_text.encode("utf-8"))
        rows.append(
            {
                "task_id": task.task_id,
                "source_file_name": source.name,
                "environment_class": task.environment_class,
                "condition": task.condition,
                "source_condition_token": task.source_condition_token,
                "sample_rate_hz": task.sample_rate_hz,
                "item_type": task.item_type,
                "iq_layout": task.iq_layout,
                "raw_windows_path": str(source),
                "raw_wsl_path": windows_to_wsl_path(source),
                "raw_size_bytes": size_bytes,
                "raw_mtime_ns_at_freeze": source.stat().st_mtime_ns,
                "raw_sha256": sha256_file(source),
                "estimated_duration_s": estimated_duration_s(size_bytes),
                "config_windows_path": str(config_path),
                "config_wsl_path": windows_to_wsl_path(config_path),
                "config_sha256": sha256_file(config_path),
                "output_windows_path": str(output_path),
                "output_wsl_path": output_wsl,
                "output_absent_at_freeze": not output_path.exists(),
                "new_only": True,
                "resume_allowed": False,
            }
        )
    if not all(bool(row["output_absent_at_freeze"]) for row in rows):
        raise FileExistsError("one or more task output namespaces exist during freeze")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "created_utc": utc_now(),
        "project_root": str(project_root),
        "input_directory": str(input_dir),
        "task_count": len(rows),
        "tasks": rows,
        "input_contract": {
            "sample_rate_hz": 10_230_000,
            "item_type": "ishort",
            "iq_layout": "interleaved_signed_int16_iq_little_endian",
            "filename_pool_semantics": "POOR",
            "gps_signal": "GPS_L1_CA",
            "contract_confirmed_by_user": True,
        },
        "wsl": {
            "distro": WSL_DISTRO,
            "version": 2,
            "linux_user": "gnss",
            "gnss_sdr_executable": GNSS_SDR_EXECUTABLE,
            "gnss_sdr_version": GNSS_SDR_VERSION,
        },
        "execution_policy": {
            "execution_mode": "new_only",
            "stop_on_first_failure": True,
            "execute_sequentially": True,
            "raw_hash_reverification_before_execute": True,
            "explicit_confirmation_required": True,
        },
        "analysis_policy": {
            "carrier_lock_test_threshold": -0.5,
            "bad_lock_debounce_ms": 20,
            "good_lock_reacquisition_ms": 100,
            "tracking_gap_policy": "INCONCLUSIVE_NO_BRIDGING",
            "sustained_position_fix_min_s": 5,
            "pre_acquisition_is_lock_loss": False,
        },
        "source_files": _source_provenance(source_files),
        "new_only": True,
        "resume_allowed": False,
        "max_parallel_gnss_sdr": 1,
        "matlab_invoked": False,
        "sage_invoked": False,
    }
    manifest_path = request_dir / "batch_manifest.json"
    raw = canonical_json_bytes(manifest)
    _write_exclusive(manifest_path, raw)
    digest = sha256_file(manifest_path)
    _write_exclusive(request_dir / "batch_manifest.sha256", (digest + "\n").encode("ascii"))
    return manifest_path, digest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--request-dir", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    here = Path(__file__).resolve()
    source_files = {
        "darkroom_rx_common": here.with_name("darkroom_rx_common.py"),
        "prepare_batch": here,
        "batch_runner": here.with_name("run_darkroom_rx_gnss_sdr_batch.py"),
        "signal_quality_auditor": here.with_name("audit_darkroom_rx_signal_quality.py"),
    }
    try:
        path, digest = prepare_batch(
            project_root=args.project_root,
            input_dir=args.input_dir,
            request_dir=args.request_dir,
            request_id=args.request_id,
            source_files=source_files,
        )
    except Exception as exc:
        print(f"DARKROOM_RX_PREPARE_REJECTED={type(exc).__name__}: {exc}")
        return 2
    print(f"BATCH_MANIFEST={path}")
    print(f"BATCH_MANIFEST_SHA256={digest}")
    print("ACCEPTED_TASKS=8")
    print("REJECTED_TASKS=0")
    print("GNSS_SDR_EXECUTED=false")
    print("RAW_IQ_HASHED=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
