"""Prepare and optionally execute an immutable eight-cell v2.2 batch.

This wrapper does not change the v2.2 scientific generator.  It freezes eight
independent v2.2 requests, validates them through the existing new-only runner,
and executes them sequentially only when the caller supplies the explicit
batch confirmation flag.  The collection directory is an index/export
namespace; authoritative per-request outputs remain in the v2.2 runner root.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .darkroom_generator_v2_2_core import (
        ENVIRONMENTS,
        V22_REQUEST_ROOT,
        V22_RUN_ROOT,
        canonical_json_bytes,
        sha256_file,
    )
    from .prepare_darkroom_generator_v2_2_request import (
        PAIRING_IDS,
        build_v22_request_payload,
        write_v22_request_namespace,
    )
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import (
        ENVIRONMENTS,
        V22_REQUEST_ROOT,
        V22_RUN_ROOT,
        canonical_json_bytes,
        sha256_file,
    )
    from scripts.analysis.channel_modeling.prepare_darkroom_generator_v2_2_request import (
        PAIRING_IDS,
        build_v22_request_payload,
        write_v22_request_namespace,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXED_PYTHON = Path(r"D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe")
COLLECTION_ROOT_RELATIVE = Path("dataset_generation_logs/channel_modeling")
RUNNER_RELATIVE = Path("scripts/analysis/channel_modeling/run_darkroom_generator_v2_2.py")
COLLECTION_SCHEMA_VERSION = "darkroom-generator-batch-2.2"
QUALITY_MODES: tuple[str, ...] = ("GOOD_TRACKED_BASELINE", "POOR_CONDITIONAL")
BATCH_ENVIRONMENTS: tuple[str, ...] = tuple(ENVIRONMENTS)
BATCH_QUALITY_MODES: tuple[str, ...] = QUALITY_MODES
QUALITY_SHORT = {"GOOD_TRACKED_BASELINE": "good", "POOR_CONDITIONAL": "poor"}
ENVIRONMENT_SHORT = {
    "Urban": "urban",
    "Special Reflective": "special_reflective",
    "Mountain/Valley": "mountain_valley",
    "Highway/Open": "highway_open",
}
ALLOWED_DURATION_MS = (20, 300_000)
MATRIX_FIELDS: tuple[str, ...] = (
    "matrix_id",
    "matrix_row",
    "accepted",
    "rejected_reason",
    "environment_class",
    "quality_mode",
    "pairing_id",
    "request_id",
    "request_path",
    "request_sha256",
    "output_namespace",
    "output_path",
    "output_absent_at_freeze",
    "duration_ms",
    "master_seed",
    "expected_rows",
    "new_only",
    "resume_allowed",
    "raw_iq_read",
    "matlab",
    "sage",
    "batch",
    "process_20_46_mhz",
    "gold_labels_used_for_generation",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _date_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _normalise_collection_token(collection_id: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", collection_id).strip("_.-")
    if not token or len(token) > 64:
        raise ValueError("collection_id must produce a non-empty token of at most 64 characters")
    return token


def _duration_label(duration_ms: int) -> str:
    if duration_ms == 20:
        return "20ms"
    if duration_ms == 300_000:
        return "5min"
    raise ValueError(f"only validation durations {ALLOWED_DURATION_MS} are supported")


def validate_execution_duration(duration_ms: int) -> None:
    """Allow only the full-duration batch for an eight-cell execute.

    Twenty milliseconds is intentionally retained as a manifest/runner smoke
    duration.  The frozen Poor quality profile contains a complete impairment
    episode and must not be truncated or treated as a valid eight-cell run.
    """

    if duration_ms == 20:
        raise ValueError("20 ms is validation-only; use 300000 ms for eight-cell execution")
    if duration_ms != 300_000:
        raise ValueError(f"full batch execution requires 300000 ms, got {duration_ms}")


def _resolve_inside(path: Path, root: Path) -> Path:
    candidate = path if path.is_absolute() else PROJECT_ROOT / path
    candidate = candidate.resolve()
    root = root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path is outside permitted root: {candidate}") from exc
    return candidate


def validate_new_only_collection_dir(collection_dir: Path) -> None:
    """Reject an existing collection before any batch artifact is written."""

    if collection_dir.exists():
        raise FileExistsError(f"new-only collection namespace already exists: {collection_dir}")


def _collection_dir(project_root: Path, requested: Path) -> Path:
    root = (project_root / COLLECTION_ROOT_RELATIVE).resolve()
    candidate = _resolve_inside(requested, root)
    if candidate == root or candidate.parent != root:
        raise ValueError("collection_dir must be a new direct child of dataset_generation_logs/channel_modeling")
    if candidate.name in {"darkroom_generator_v2_2_requests", "darkroom_generator_v2_2_runs", "darkroom_generator_v2_2_matrices"}:
        raise ValueError("collection_dir cannot be a v2.2 request/run/matrix root")
    return candidate


def build_batch_rows(*, collection_id: str, duration_ms: int, master_seed: int) -> list[dict[str, Any]]:
    """Build deterministic row metadata without reading gold or writing files."""

    if duration_ms not in ALLOWED_DURATION_MS:
        raise ValueError(f"duration_ms must be one of {ALLOWED_DURATION_MS}")
    token = _normalise_collection_token(collection_id)
    duration_label = _duration_label(duration_ms)
    date_tag = _date_tag()
    rows: list[dict[str, Any]] = []
    row_number = 0
    for environment in ENVIRONMENTS:
        for quality_mode in QUALITY_MODES:
            row_number += 1
            request_id = (
                f"{ENVIRONMENT_SHORT[environment]}_{QUALITY_SHORT[quality_mode]}_"
                f"{duration_label}_v2_2_{token}_{date_tag}"
            )
            rows.append(
                {
                    "matrix_row": row_number,
                    "environment_class": environment,
                    "quality_mode": quality_mode,
                    "pairing_id": PAIRING_IDS[environment],
                    "request_id": request_id,
                    "duration_ms": duration_ms,
                    "master_seed": master_seed,
                    "expected_rows": duration_ms * 12,
                    "new_only": True,
                    "resume_allowed": False,
                    "raw_iq_read": False,
                    "matlab": False,
                    "sage": False,
                    "batch": False,
                    "process_20_46_mhz": False,
                    "gold_labels_used_for_generation": False,
                }
            )
    return rows


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_bytes(dict(value)).decode("utf-8"))


def _write_csv_exclusive(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(fields), lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _source_hash(path: Path) -> str:
    return sha256_file(path)


def prepare_batch(
    *,
    project_root: Path,
    config_path: Path,
    collection_dir: Path,
    collection_id: str,
    duration_ms: int,
    master_seed: int,
) -> tuple[Path, str, list[dict[str, Any]]]:
    project_root = project_root.resolve()
    collection_dir = _collection_dir(project_root, collection_dir)
    validate_new_only_collection_dir(collection_dir)
    rows = build_batch_rows(collection_id=collection_id, duration_ms=duration_ms, master_seed=master_seed)
    request_root = (project_root / V22_REQUEST_ROOT).resolve()
    collection_dir.mkdir(parents=True)
    enriched: list[dict[str, Any]] = []
    try:
        for base in rows:
            request_id = str(base["request_id"])
            request_dir = request_root / request_id
            output_relative = f"{V22_RUN_ROOT}/{request_id}"
            payload = build_v22_request_payload(
                project_root=project_root,
                config_path=config_path,
                request_id=request_id,
                environment=str(base["environment_class"]),
                quality_mode=str(base["quality_mode"]),
                duration_ms=int(base["duration_ms"]),
                master_seed=int(base["master_seed"]),
                pairing_id=str(base["pairing_id"]),
                simulation_id=request_id,
                request_purpose=("BATCH_20MS_VALIDATION" if duration_ms == 20 else "BATCH_5MIN_EXPORT"),
                output_namespace=output_relative,
            )
            request_path, request_sha = write_v22_request_namespace(request_dir, payload)
            output_path = (project_root / output_relative).resolve()
            if output_path.exists():
                raise FileExistsError(f"new-only output namespace appeared during freeze: {output_path}")
            row = dict(base)
            row.update(
                {
                    "matrix_id": collection_id,
                    "accepted": True,
                    "rejected_reason": "",
                    "request_path": str(request_path),
                    "request_sha256": request_sha,
                    "output_namespace": output_relative,
                    "output_path": str(output_path),
                    "output_absent_at_freeze": True,
                }
            )
            enriched.append(row)
    except Exception:
        # Never clean up a partial immutable freeze.  A subsequent attempt must
        # use a new collection/request namespace.
        raise

    matrix_csv = collection_dir / "request_matrix.csv"
    _write_csv_exclusive(matrix_csv, MATRIX_FIELDS, enriched)
    script_path = Path(__file__).resolve()
    manifest = {
        "matrix_schema_version": COLLECTION_SCHEMA_VERSION,
        "matrix_id": collection_id,
        "collection_relative_path": collection_dir.relative_to(project_root).as_posix(),
        "created_utc": _utc_now(),
        "generator_version": "2.2.0",
        "generator_config_relative_path": str(config_path.resolve().relative_to(project_root)).replace("\\", "/"),
        "generator_config_sha256": _source_hash(config_path.resolve()),
        "request_root_relative_path": V22_REQUEST_ROOT,
        "run_root_relative_path": V22_RUN_ROOT,
        "runner_relative_path": RUNNER_RELATIVE.as_posix(),
        "runner_sha256": _source_hash(project_root / RUNNER_RELATIVE),
        "batch_script_relative_path": script_path.relative_to(project_root).as_posix(),
        "batch_script_sha256": _source_hash(script_path),
        "ordered_environments": list(ENVIRONMENTS),
        "ordered_quality_modes": list(QUALITY_MODES),
        "duration_ms": duration_ms,
        "duration_label": _duration_label(duration_ms),
        "master_seed": master_seed,
        "accepted_count": len(enriched),
        "rejected_count": 0,
        "request_matrix_relative_path": matrix_csv.relative_to(project_root).as_posix(),
        "expected_rows_per_table": duration_ms * 12,
        "expected_total_rows": duration_ms * 12 * len(enriched),
        "request_rows": enriched,
        "table_export_relative_path": (collection_dir.relative_to(project_root) / "tables").as_posix(),
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "gold_labels_used_for_generation": False,
    }
    manifest_path = collection_dir / "matrix_manifest.json"
    _write_json_exclusive(manifest_path, manifest)
    digest = _source_hash(manifest_path)
    with (collection_dir / "matrix_manifest.sha256").open("x", encoding="ascii", newline="\n") as digest_handle:
        digest_handle.write(digest + "\n")
    return manifest_path, digest, enriched


def _read_manifest(manifest_path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    raw = manifest_path.resolve().read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest.lower() != expected_sha256.lower():
        raise ValueError(f"batch manifest SHA-256 mismatch: {digest} != {expected_sha256}")
    manifest = json.loads(raw.decode("utf-8"))
    if not isinstance(manifest, dict) or raw != canonical_json_bytes(manifest):
        raise ValueError("batch manifest is not canonical frozen JSON")
    return manifest, digest


def _validate_manifest_scope(project_root: Path, manifest_path: Path, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("matrix_schema_version") != COLLECTION_SCHEMA_VERSION:
        raise ValueError("unsupported batch manifest schema")
    collection_dir = manifest_path.resolve().parent
    expected_relative = str(manifest.get("collection_relative_path", "")).replace("\\", "/")
    if expected_relative != collection_dir.relative_to(project_root.resolve()).as_posix():
        raise ValueError("collection path provenance mismatch")
    if manifest.get("accepted_count") != 8 or manifest.get("rejected_count") != 0:
        raise ValueError("batch must contain exactly eight accepted rows")
    if manifest.get("new_only") is not True or manifest.get("resume_allowed") is not False:
        raise ValueError("batch new-only contract mismatch")
    for forbidden in ("raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz", "gold_labels_used_for_generation"):
        if manifest.get(forbidden) is not False:
            raise ValueError(f"batch forbidden flag is not false: {forbidden}")
    matrix_path = project_root / str(manifest["request_matrix_relative_path"])
    if matrix_path.resolve() != collection_dir / "request_matrix.csv":
        raise ValueError("request matrix path provenance mismatch")
    with matrix_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 8:
        raise ValueError("request matrix must contain eight rows")
    return [dict(row) for row in rows]


def _write_batch_lock(lock_path: Path, manifest_sha256: str) -> None:
    if lock_path.exists():
        raise RuntimeError(f"batch lock already exists: {lock_path}")
    with lock_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_bytes({"pid": os.getpid(), "created_utc": _utc_now(), "manifest_sha256": manifest_sha256}).decode("utf-8"))


def _release_batch_lock(lock_path: Path, manifest_sha256: str) -> None:
    if not lock_path.exists():
        return
    released = lock_path.with_name(f"batch_execution.released.{manifest_sha256[:12]}.{time.time_ns()}.lock")
    lock_path.rename(released)


def _copy_exclusive(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"table export already exists: {destination}")
    with source.open("rb") as src, destination.open("xb") as dst:
        while True:
            block = src.read(1024 * 1024)
            if not block:
                break
            dst.write(block)


def _export_tables(project_root: Path, collection_dir: Path, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    tables_dir = collection_dir / "tables"
    if tables_dir.exists():
        raise FileExistsError(f"new-only table export namespace already exists: {tables_dir}")
    tables_dir.mkdir()
    exports: list[dict[str, Any]] = []
    for row in rows:
        source = Path(str(row["output_path"])) / "darkroom_channel_parameters.csv"
        if not source.is_file() or source.stat().st_size == 0:
            raise FileNotFoundError(f"completed canonical table is missing or empty: {source}")
        environment_token = ENVIRONMENT_SHORT[str(row["environment_class"])]
        quality_token = QUALITY_SHORT[str(row["quality_mode"])]
        destination = tables_dir / f"{environment_token}__{quality_token}.csv"
        _copy_exclusive(source, destination)
        exports.append(
            {
                "environment_class": row["environment_class"],
                "quality_mode": row["quality_mode"],
                "request_id": row["request_id"],
                "source_path": str(source),
                "source_sha256": sha256_file(source),
                "destination_path": str(destination),
                "destination_sha256": sha256_file(destination),
                "bytes": destination.stat().st_size,
            }
        )
    manifest = {
        "schema_version": "darkroom-generator-table-export-2.2",
        "created_utc": _utc_now(),
        "table_count": len(exports),
        "exports": exports,
        "gold_labels_used_for_generation": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
    }
    export_manifest = collection_dir / "table_export_manifest.json"
    _write_json_exclusive(export_manifest, manifest)
    digest = sha256_file(export_manifest)
    with (collection_dir / "table_export_manifest.sha256").open("x", encoding="ascii", newline="\n") as digest_handle:
        digest_handle.write(digest + "\n")
    return {"table_export_manifest": str(export_manifest), "table_export_manifest_sha256": digest, "exports": exports}


def _run_one(project_root: Path, row: Mapping[str, Any], log_dir: Path) -> dict[str, Any]:
    runner = (project_root / RUNNER_RELATIVE).resolve()
    request_path = Path(str(row["request_path"])).resolve()
    log_path = log_dir / f"{row['request_id']}.log"
    command = [
        str(FIXED_PYTHON),
        str(runner),
        "--request",
        str(request_path),
        "--expected-request-sha256",
        str(row["request_sha256"]),
        "--generate",
        "--confirm-darkroom-generation-v2-2",
    ]
    started = time.perf_counter()
    with log_path.open("x", encoding="utf-8", newline="") as log:
        log.write("COMMAND=" + json.dumps(command, ensure_ascii=False) + "\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(f"[{row['request_id']}] {line.rstrip()}", flush=True)
            exit_code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            exit_code = None
            log.write("BATCH_INTERRUPTED=KeyboardInterrupt\n")
            raise
    receipt_path = Path(str(row["output_path"])) / "generation_receipt.json"
    receipt_status = None
    if receipt_path.is_file():
        try:
            receipt_status = json.loads(receipt_path.read_text(encoding="utf-8"))["status"]
        except (OSError, json.JSONDecodeError, KeyError):
            receipt_status = "unreadable"
    return {
        "request_id": row["request_id"],
        "exit_code": exit_code,
        "status": "completed" if exit_code == 0 and receipt_status == "completed" else "failed",
        "receipt_status": receipt_status,
        "log_path": str(log_path),
        "elapsed_s": time.perf_counter() - started,
        "output_path": row["output_path"],
    }


def execute_batch(*, project_root: Path, manifest_path: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    project_root = project_root.resolve()
    manifest, manifest_sha256 = _read_manifest(manifest_path.resolve(), expected_manifest_sha256)
    rows = _validate_manifest_scope(project_root, manifest_path.resolve(), manifest)
    validate_execution_duration(int(manifest["duration_ms"]))
    lock_path = manifest_path.resolve().parent / "batch_execution.lock"
    log_dir = manifest_path.resolve().parent / "logs"
    if log_dir.exists():
        raise FileExistsError(f"new-only batch log namespace already exists: {log_dir}")
    log_dir.mkdir()
    for row in rows:
        output_path = Path(str(row["output_path"])).resolve()
        if output_path.exists():
            raise FileExistsError(f"new_only forbids existing output: {output_path}")
    _write_batch_lock(lock_path, manifest_sha256)
    started_utc = _utc_now()
    results: list[dict[str, Any]] = []
    try:
        for row in rows:
            result = _run_one(project_root, row, log_dir)
            results.append(result)
            if result["status"] != "completed":
                break
        all_completed = len(results) == len(rows) and all(item["status"] == "completed" for item in results)
        export_info = _export_tables(project_root, manifest_path.resolve().parent, rows) if all_completed else None
        receipt = {
            "schema_version": "darkroom-generator-batch-receipt-2.2",
            "status": "completed" if all_completed else "failed",
            "started_utc": started_utc,
            "ended_utc": _utc_now(),
            "matrix_id": manifest["matrix_id"],
            "matrix_manifest": str(manifest_path.resolve()),
            "matrix_manifest_sha256": manifest_sha256,
            "duration_ms": manifest["duration_ms"],
            "request_count": len(rows),
            "completed_count": sum(item["status"] == "completed" for item in results),
            "results": results,
            "table_export": export_info,
            "gold_labels_used_for_generation": False,
            "raw_iq_read": False,
            "matlab": False,
            "sage": False,
            "batch": False,
        }
        receipt_path = manifest_path.resolve().parent / "batch_execution_receipt.json"
        _write_json_exclusive(receipt_path, receipt)
        return receipt
    except KeyboardInterrupt:
        interruption = {
            "schema_version": "darkroom-generator-batch-receipt-2.2",
            "status": "interrupted",
            "reason": "KeyboardInterrupt",
            "started_utc": started_utc,
            "ended_utc": _utc_now(),
            "matrix_manifest": str(manifest_path.resolve()),
            "matrix_manifest_sha256": manifest_sha256,
            "results": results,
        }
        path = manifest_path.resolve().parent / "batch_interruption_receipt.json"
        if not path.exists():
            _write_json_exclusive(path, interruption)
        raise
    finally:
        _release_batch_lock(lock_path, manifest_sha256)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--validate-only", action="store_true")
    modes.add_argument("--execute", action="store_true")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2_2.json")
    parser.add_argument("--collection-id")
    parser.add_argument("--collection-dir", type=Path)
    parser.add_argument("--duration-ms", type=int)
    parser.add_argument("--master-seed", type=int, default=20_260_827)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--confirm-darkroom-batch-v2-2", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project_root = args.project_root.resolve()
    try:
        if args.prepare:
            if not args.collection_id or not args.collection_dir or args.duration_ms is None:
                raise ValueError("--prepare requires --collection-id, --collection-dir and --duration-ms")
            manifest_path, digest, rows = prepare_batch(
                project_root=project_root,
                config_path=args.config,
                collection_dir=args.collection_dir,
                collection_id=args.collection_id,
                duration_ms=args.duration_ms,
                master_seed=args.master_seed,
            )
            print(f"COLLECTION_MANIFEST={manifest_path}")
            print(f"COLLECTION_MANIFEST_SHA256={digest}")
            print(f"ACCEPTED_ROWS={len(rows)}")
            print("REJECTED_ROWS=0")
            return 0
        if not args.manifest or not args.expected_manifest_sha256:
            raise ValueError("--validate-only/--execute require --manifest and --expected-manifest-sha256")
        manifest, digest = _read_manifest(args.manifest.resolve(), args.expected_manifest_sha256)
        rows = _validate_manifest_scope(project_root, args.manifest.resolve(), manifest)
        if args.validate_only:
            for row in rows:
                request_path = Path(str(row["request_path"])).resolve()
                if not request_path.is_file() or sha256_file(request_path) != str(row["request_sha256"]):
                    raise ValueError(f"request hash mismatch: {request_path}")
                output_path = Path(str(row["output_path"])).resolve()
                if output_path.exists():
                    raise FileExistsError(f"new_only output already exists: {output_path}")
            print(json.dumps({"execution_eligible": True, "matlab_invoked": False, "sage_invoked": False, "raw_iq_read": False, "batch_invoked": False, "duration_ms": manifest["duration_ms"], "accepted_rows": len(rows), "manifest_sha256": digest, "output_namespaces_absent": True}, ensure_ascii=False, indent=2))
            return 0
        if not args.confirm_darkroom_batch_v2_2:
            raise ValueError("--execute requires --confirm-darkroom-batch-v2-2")
        receipt = execute_batch(project_root=project_root, manifest_path=args.manifest.resolve(), expected_manifest_sha256=args.expected_manifest_sha256)
        print(f"BATCH_EXECUTION_RECEIPT={args.manifest.resolve().parent / 'batch_execution_receipt.json'}")
        print(f"BATCH_STATUS={receipt['status']}")
        return 0 if receipt["status"] == "completed" else 2
    except KeyboardInterrupt:
        print("V22_BATCH_INTERRUPTED=KeyboardInterrupt")
        return 130
    except Exception as exc:
        print(f"V22_BATCH_REJECTED={type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
