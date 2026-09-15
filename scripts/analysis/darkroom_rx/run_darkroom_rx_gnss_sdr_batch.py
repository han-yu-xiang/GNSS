"""Validate or sequentially execute one immutable 0913DarkroomRx GNSS-SDR batch.

Validation is the default.  Real GNSS-SDR execution requires both ``--execute``
and ``--confirm-darkroom-rx-gnss-sdr``.  Every selected task is new-only; an
existing output directory is rejected and is never deleted or resumed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .darkroom_rx_common import (
        BYTES_PER_COMPLEX_SAMPLE,
        EXPECTED_FILENAMES,
        ITEM_TYPE,
        SAMPLE_RATE_HZ,
        SCHEMA_VERSION,
        canonical_json_bytes,
        sha256_file,
    )
except ImportError:
    from scripts.analysis.darkroom_rx.darkroom_rx_common import (
        BYTES_PER_COMPLEX_SAMPLE,
        EXPECTED_FILENAMES,
        ITEM_TYPE,
        SAMPLE_RATE_HZ,
        SCHEMA_VERSION,
        canonical_json_bytes,
        sha256_file,
    )


HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _path_is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def load_and_validate_manifest(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Verify the immutable manifest and all frozen source/configuration hashes."""

    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"batch manifest is missing: {path}")
    if not HEX_SHA256.fullmatch(expected_sha256):
        raise ValueError("expected manifest SHA-256 must be 64 hexadecimal characters")
    actual_sha256 = sha256_file(path)
    if actual_sha256.lower() != expected_sha256.lower():
        raise ValueError(
            "batch manifest SHA-256 mismatch: "
            f"expected={expected_sha256.lower()} actual={actual_sha256}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"batch manifest is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("batch manifest root must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {payload.get('schema_version')!r}")
    if payload.get("new_only") is not True or payload.get("resume_allowed") is not False:
        raise ValueError("manifest must freeze new_only=true and resume_allowed=false")
    if payload.get("max_parallel_gnss_sdr") != 1:
        raise ValueError("manifest must freeze max_parallel_gnss_sdr=1")
    policy = _require_mapping(payload.get("execution_policy"), "execution_policy")
    if policy.get("execution_mode") != "new_only":
        raise ValueError("execution_policy.execution_mode must be new_only")
    if policy.get("execute_sequentially") is not True:
        raise ValueError("execution_policy.execute_sequentially must be true")
    contract = _require_mapping(payload.get("input_contract"), "input_contract")
    expected_contract = {
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "item_type": ITEM_TYPE,
        "iq_layout": "interleaved_signed_int16_iq_little_endian",
        "filename_pool_semantics": "POOR",
        "contract_confirmed_by_user": True,
    }
    for key, expected in expected_contract.items():
        if contract.get(key) != expected:
            raise ValueError(f"input contract mismatch for {key}: {contract.get(key)!r}")

    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != len(EXPECTED_FILENAMES):
        raise ValueError(f"manifest must contain exactly {len(EXPECTED_FILENAMES)} tasks")
    if payload.get("task_count") != len(tasks):
        raise ValueError("task_count does not match tasks length")
    ids: list[str] = []
    source_names: list[str] = []
    request_root = path.parent.resolve()
    for index, raw_row in enumerate(tasks):
        row = _require_mapping(raw_row, f"tasks[{index}]")
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"tasks[{index}].task_id must be nonempty")
        ids.append(task_id)
        source_names.append(str(row.get("source_file_name", "")).lower())
        if row.get("sample_rate_hz") != SAMPLE_RATE_HZ or row.get("item_type") != ITEM_TYPE:
            raise ValueError(f"task {task_id} format contract mismatch")
        if row.get("iq_layout") != "interleaved_signed_int16_iq_little_endian":
            raise ValueError(f"task {task_id} IQ layout mismatch")
        if row.get("new_only") is not True or row.get("resume_allowed") is not False:
            raise ValueError(f"task {task_id} is not frozen new-only")
        config_path = Path(str(row.get("config_windows_path", ""))).resolve()
        output_path = Path(str(row.get("output_windows_path", ""))).resolve()
        if not _path_is_within(config_path, request_root / "configs"):
            raise ValueError(f"task {task_id} config escapes immutable request namespace")
        if not _path_is_within(output_path, request_root / "runs"):
            raise ValueError(f"task {task_id} output escapes request runs namespace")
        if "sage_results" in {part.lower() for part in output_path.parts}:
            raise ValueError(f"task {task_id} output may not target sage_results")
    if len(set(ids)) != len(ids):
        raise ValueError("task_id values must be unique")
    if sorted(source_names) != sorted(EXPECTED_FILENAMES):
        raise ValueError("source filename inventory differs from the frozen eight-file contract")

    source_files = _require_mapping(payload.get("source_files"), "source_files")
    for label, raw_record in source_files.items():
        record = _require_mapping(raw_record, f"source_files.{label}")
        source_path = Path(str(record.get("path", "")))
        if not source_path.is_file():
            raise FileNotFoundError(f"frozen source is missing: {label}={source_path}")
        if source_path.stat().st_size != record.get("size_bytes"):
            raise ValueError(f"frozen source size changed: {label}")
        if sha256_file(source_path) != record.get("sha256"):
            raise ValueError(f"frozen source SHA-256 changed: {label}")
    payload["_manifest_path"] = str(path)
    payload["_manifest_sha256"] = actual_sha256
    return payload


def select_tasks(
    tasks: Sequence[Mapping[str, Any]], requested_task_ids: Sequence[str] | None
) -> list[Mapping[str, Any]]:
    """Select tasks without changing frozen manifest order."""

    by_id = {str(row["task_id"]): row for row in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("task_id values must be unique")
    if not requested_task_ids:
        return list(tasks)
    requested = list(requested_task_ids)
    if len(set(requested)) != len(requested):
        raise ValueError("duplicate --task-id values are not allowed")
    unknown = [task_id for task_id in requested if task_id not in by_id]
    if unknown:
        raise ValueError(f"unknown task_id values: {unknown}")
    requested_set = set(requested)
    return [row for row in tasks if str(row["task_id"]) in requested_set]


def validate_task_preflight(
    row: Mapping[str, Any], *, verify_raw_hash: bool
) -> dict[str, Any]:
    """Validate one task without reading raw content unless hash verification is requested."""

    task_id = str(row.get("task_id", ""))
    if not task_id:
        raise ValueError("task_id is missing")
    if row.get("sample_rate_hz") != SAMPLE_RATE_HZ or row.get("item_type") != ITEM_TYPE:
        raise ValueError(f"{task_id}: sample format mismatch")
    if row.get("new_only") is not True or row.get("resume_allowed") is not False:
        raise ValueError(f"{task_id}: execution policy is not new-only")
    raw_path = Path(str(row.get("raw_windows_path", "")))
    config_path = Path(str(row.get("config_windows_path", "")))
    output_path = Path(str(row.get("output_windows_path", "")))
    if not raw_path.is_file():
        raise FileNotFoundError(f"{task_id}: raw IQ is missing: {raw_path}")
    size = raw_path.stat().st_size
    if size <= 0 or size % BYTES_PER_COMPLEX_SAMPLE:
        raise ValueError(f"{task_id}: raw IQ byte length is invalid")
    if size != row.get("raw_size_bytes"):
        raise ValueError(f"{task_id}: raw IQ size changed")
    frozen_mtime = row.get("raw_mtime_ns_at_freeze")
    if frozen_mtime is not None and raw_path.stat().st_mtime_ns != frozen_mtime:
        raise ValueError(f"{task_id}: raw IQ mtime changed after freeze")
    if verify_raw_hash and sha256_file(raw_path) != row.get("raw_sha256"):
        raise ValueError(f"{task_id}: raw IQ SHA-256 changed")
    if not config_path.is_file():
        raise FileNotFoundError(f"{task_id}: GNSS-SDR config is missing: {config_path}")
    if sha256_file(config_path) != row.get("config_sha256"):
        raise ValueError(f"{task_id}: GNSS-SDR config SHA-256 changed")
    if output_path.exists():
        raise FileExistsError(f"{task_id}: output exists; new_only forbids reuse or resume")
    return {
        "task_id": task_id,
        "raw_path": str(raw_path.resolve()),
        "raw_size_bytes": size,
        "raw_hash_verified": verify_raw_hash,
        "config_path": str(config_path.resolve()),
        "output_path": str(output_path.resolve()),
        "output_absent": True,
        "new_only": True,
        "resume_allowed": False,
    }


def build_wsl_command(
    row: Mapping[str, Any], *, distro: str, executable: str
) -> list[str]:
    """Build an argv-safe WSL invocation; the shell fragment contains quoted paths."""

    config = str(row["config_wsl_path"])
    output = str(row["output_wsl_path"])
    if not config.startswith("/mnt/") or not output.startswith("/mnt/"):
        raise ValueError("config/output must be absolute WSL /mnt paths")
    expression = (
        f"cd {shlex.quote(output)} && "
        f"exec {shlex.quote(executable)} --config_file={shlex.quote(config)}"
    )
    return ["wsl.exe", "-d", distro, "--", "bash", "-lc", expression]


@contextmanager
def global_runner_lock(lock_path: Path) -> Iterator[None]:
    """Hold a non-destructive process lock; the persistent lock file is never deleted."""

    import msvcrt

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError(f"global GNSS-SDR runner lock is busy: {lock_path}") from exc
        yield
    finally:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            handle.close()


def _write_exclusive_json(path: Path, value: Mapping[str, Any]) -> str:
    raw = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
    digest = sha256_file(path)
    with path.with_suffix(path.suffix + ".sha256").open("x", encoding="ascii") as handle:
        handle.write(digest + "\n")
    return digest


def _create_output_tree(output_path: Path) -> None:
    output_path.mkdir(parents=True, exist_ok=False)
    for name in (
        "tracking",
        "telemetry",
        "observables",
        "pvt",
        "nmea",
        "rinex",
        "trajectory",
        "navigation",
        "logs",
    ):
        (output_path / name).mkdir()


def execute_one_task(
    *,
    manifest: Mapping[str, Any],
    row: Mapping[str, Any],
    timeout_seconds: float | None,
) -> tuple[dict[str, Any], Path]:
    """Execute one frozen task and always retain a success/failure/interruption receipt."""

    task_id = str(row["task_id"])
    verify = validate_task_preflight(row, verify_raw_hash=True)
    output_path = Path(str(row["output_windows_path"])).resolve()
    _create_output_tree(output_path)
    stdout_path = output_path / "logs" / "gnss_sdr_stdout.log"
    stderr_path = output_path / "logs" / "gnss_sdr_stderr.log"
    command = build_wsl_command(
        row,
        distro=str(manifest["wsl"]["distro"]),
        executable=str(manifest["wsl"]["gnss_sdr_executable"]),
    )
    start_utc = utc_now()
    start_monotonic = time.monotonic()
    status = "failed"
    reason: str | None = None
    exit_code: int | None = None
    process: subprocess.Popen[bytes] | None = None
    try:
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
            try:
                exit_code = process.wait(timeout=timeout_seconds)
                status = "completed" if exit_code == 0 else "failed"
                if exit_code != 0:
                    reason = "GNSS_SDR_NONZERO_EXIT"
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                exit_code = process.returncode
                status = "interrupted"
                reason = "EXECUTOR_TIMEOUT"
    except KeyboardInterrupt:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        exit_code = process.returncode if process is not None else None
        status = "interrupted"
        reason = "PYTHON_KEYBOARD_INTERRUPT_OR_CONSOLE_SIGINT"
    except BaseException as exc:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        status = "failed"
        reason = f"EXECUTOR_EXCEPTION:{type(exc).__name__}:{exc}"
    end_utc = utc_now()
    receipt = {
        "schema_version": "darkroom-rx-gnss-sdr-execution-receipt-v1",
        "request_id": manifest["request_id"],
        "manifest_path": manifest["_manifest_path"],
        "manifest_sha256": manifest["_manifest_sha256"],
        "task_id": task_id,
        "status": status,
        "reason": reason,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "elapsed_s": time.monotonic() - start_monotonic,
        "exit_code": exit_code,
        "command_argv": command,
        "command_expression": command[-1],
        "wsl_distro": manifest["wsl"]["distro"],
        "gnss_sdr_executable": manifest["wsl"]["gnss_sdr_executable"],
        "gnss_sdr_version": manifest["wsl"]["gnss_sdr_version"],
        "input": verify,
        "raw_sha256": row["raw_sha256"],
        "output_path": str(output_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "new_only": True,
        "resume_allowed": False,
        "matlab_invoked": False,
        "sage_invoked": False,
    }
    stamp = end_utc.replace("-", "").replace(":", "").replace(".", "")
    receipt_path = (
        Path(str(manifest["_manifest_path"])).parent
        / "receipts"
        / task_id
        / f"{stamp}_execution_receipt.json"
    )
    _write_exclusive_json(receipt_path, receipt)
    return receipt, receipt_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-darkroom-rx-gnss-sdr", action="store_true")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=0.0,
        help="0 disables timeout; a positive value applies independently to each task",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = load_and_validate_manifest(
            args.manifest, args.expected_manifest_sha256
        )
        tasks = select_tasks(manifest["tasks"], args.task_id)
        if args.timeout_seconds < 0:
            raise ValueError("--timeout-seconds may not be negative")
        if args.confirm_darkroom_rx_gnss_sdr and not args.execute:
            raise ValueError("confirmation flag is only valid together with --execute")
        for row in tasks:
            summary = validate_task_preflight(row, verify_raw_hash=False)
            command = build_wsl_command(
                row,
                distro=str(manifest["wsl"]["distro"]),
                executable=str(manifest["wsl"]["gnss_sdr_executable"]),
            )
            print(f"TASK_ID={summary['task_id']}")
            print(f"RAW_PATH={summary['raw_path']}")
            print(f"RAW_SIZE_BYTES={summary['raw_size_bytes']}")
            print(f"OUTPUT_PATH={summary['output_path']}")
            print(f"WSL_EXPRESSION={command[-1]}")
            print("PREFLIGHT=PASS")
        print(f"ACCEPTED_TASKS={len(tasks)}")
        print("REJECTED_TASKS=0")
        print("NEW_ONLY=true")
        print("RESUME_ALLOWED=false")
        if not args.execute:
            print("VALIDATION_ONLY=true")
            print("GNSS_SDR_INVOKED=false")
            return 0
        if not args.confirm_darkroom_rx_gnss_sdr:
            raise PermissionError(
                "real execution requires --execute --confirm-darkroom-rx-gnss-sdr"
            )
        lock_path = Path(manifest["project_root"]) / (
            "dataset_generation_logs/darkroom_rx_gnss_sdr/.global_runner.lock"
        )
        timeout = args.timeout_seconds if args.timeout_seconds > 0 else None
        with global_runner_lock(lock_path):
            print("GLOBAL_LOCK=ACQUIRED")
            for row in tasks:
                receipt, receipt_path = execute_one_task(
                    manifest=manifest, row=row, timeout_seconds=timeout
                )
                print(f"EXECUTION_RECEIPT={receipt_path}")
                print(f"EXECUTION_STATUS={receipt['status']}")
                if receipt["status"] != "completed":
                    print("BATCH_STOPPED_ON_FIRST_FAILURE=true")
                    return 1
        print("GNSS_SDR_INVOKED=true")
        print("BATCH_STATUS=COMPLETED")
        return 0
    except Exception as exc:
        print(f"DARKROOM_RX_RUNNER_REJECTED={type(exc).__name__}: {exc}")
        print("GNSS_SDR_INVOKED=false")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
