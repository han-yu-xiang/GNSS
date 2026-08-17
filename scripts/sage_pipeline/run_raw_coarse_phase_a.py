#!/usr/bin/env python3
"""Manifest-gated task-aware executor for raw-coarse Phase-A.

The default operation is validation-only.  This module never accepts scene,
PRN, channel, raw path, or output path as task-selection arguments: those
values must come from one immutable, hash-verified manifest.  The execute path
is deliberately narrow and orchestrates the existing v2 NumPy kernel and
legacy chunk/promotion helpers for exactly one manifest task.
"""

from __future__ import annotations

import argparse
import csv
import contextlib
import hashlib
import importlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
import tracemalloc
from types import SimpleNamespace
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPECTED_MANIFEST_NAMESPACE = "batch_sampled_v1_2_phase_a_execution_requests_20260812"
EXPECTED_OUTPUT_ROOT_NAME = "batch_sampled_v1_2_phase_a_outputs_20260812"
RETRY_MANIFEST_NAMESPACE = "batch_sampled_v1_2_phase_a_retry_requests_20260812"
RETRY_OUTPUT_ROOT_NAME = "batch_sampled_v1_2_phase_a_retry_outputs_20260812"
EXPECTED_PARAMETER_HASH = "41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2"
EXPECTED_KERNEL_VERSION = "numpy-batched-complex128-v2-aligned"
EXPECTED_PLANNER_VERSION = "batch-sampled-v1.2-b1-b2-c1-prototype-v2-aligned"
EXPECTED_SCHEMA_VERSION = "batch-sampled-v1.2-raw-coarse-schema-3"
EXPECTED_PYTHON = Path(r"D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe")
EXPECTED_PYTHON_VERSION = "3.12.9"
EXPECTED_NUMPY_VERSION = "2.5.1"
EXPECTED_SCIPY_VERSION = "1.18.0"
EXPECTED_SAMPLE_RATE_HZ = 10_230_000
G16_REQUEST_ID = "phase_a1_g16_20260812"
G16_RETRY_REQUEST_ID = "phase_a1_g16_retry1_20260812"
G25_REQUEST_ID = "phase_a2_g25_20260812"
G16_QA_RECEIPT_RELATIVE = Path(
    "dataset_generation_logs/sampling_validation/batch_sampled_v1_2_phase_a_qa/g16_qa_pass.json"
)
LOCK_RELATIVE = Path(
    "dataset_generation_logs/sampling_validation/batch_sampled_v1_2_phase_a_execution.lock"
)
V2_RELATIVE = Path("scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2_v2.py")
PIPELINE_RELATIVE = Path("scripts/sage_pipeline/run_nav_sage_pipeline.m")
ALIGNMENT_REPORT_RELATIVE = Path("docs/RAW_COARSE_NUMPY_KERNEL_ALIGNMENT_REPORT.md")
ALIGNMENT_DIR_RELATIVE = Path(
    "dataset_generation_logs/sampling_validation/batch_sampled_v1_2_kernel_alignment_v2"
)
STALL_TIMEOUT_SECONDS = 1800.0
TOTAL_TIMEOUT_SECONDS = 48.0 * 3600.0

_INTERRUPT_PROVENANCE: dict[str, Any] = {
    "signal_number": None,
    "signal_name": None,
    "received_at_utc": None,
    "handler_installed": False,
}
_EXECUTION_CONTEXT: dict[str, Any] = {
    "phase": "preflight",
    "current_function": "main",
    "current_chunk": None,
    "last_progress_at_utc": None,
    "last_progress_monotonic": None,
}
_WORKER_PID: int | None = None


def _signal_name(signum: int) -> str:
    try:
        return signal.Signals(signum).name
    except ValueError:
        return f"signal_{signum}"


def _record_interrupt_signal(signum: int, _frame: Any) -> None:
    _INTERRUPT_PROVENANCE.update(
        {
            "signal_number": signum,
            "signal_name": _signal_name(signum),
            "received_at_utc": utc_now(),
        }
    )
    raise KeyboardInterrupt


def install_interrupt_handlers() -> None:
    """Record console/termination provenance while retaining KeyboardInterrupt semantics."""
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        signum = getattr(signal, name, None)
        if signum is not None:
            try:
                signal.signal(signum, _record_interrupt_signal)
            except (OSError, RuntimeError, ValueError):
                continue
    _INTERRUPT_PROVENANCE["handler_installed"] = True


def set_execution_context(**values: Any) -> None:
    _EXECUTION_CONTEXT.update(values)

ALLOWED_TASKS: dict[str, dict[str, Any]] = {
    G16_REQUEST_ID: {
        "phase_id": "Phase-A1",
        "scene_id": "F1023_V70_D0120_P7",
        "prn": "G16",
        "tracking_channel": 1,
        "sample_rate_hz": EXPECTED_SAMPLE_RATE_HZ,
    },
    G16_RETRY_REQUEST_ID: {
        "phase_id": "Phase-A1-Retry1",
        "scene_id": "F1023_V70_D0120_P7",
        "prn": "G16",
        "tracking_channel": 1,
        "sample_rate_hz": EXPECTED_SAMPLE_RATE_HZ,
    },
    G25_REQUEST_ID: {
        "phase_id": "Phase-A2",
        "scene_id": "F1023_v50_D0127_P1",
        "prn": "G25",
        "tracking_channel": 0,
        "sample_rate_hz": EXPECTED_SAMPLE_RATE_HZ,
    },
}


class ExecutorRejected(RuntimeError):
    """A safety or validation gate rejected the request."""


@dataclass
class ValidationResult:
    manifest_path: Path
    project_root: Path
    manifest: dict[str, Any]
    manifest_sha256: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backend: dict[str, Any] = field(default_factory=dict)
    evaluator_api_available: bool = False
    g16_qa_pass: bool = False
    g16_qa_reason: str = "not_applicable"

    @property
    def task(self) -> dict[str, Any]:
        return self.manifest.get("task", {})

    @property
    def execution_eligible(self) -> bool:
        return not self.errors

    @property
    def execute_dispatch_available(self) -> bool:
        return self.execution_eligible and self.evaluator_api_available


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutorRejected(f"cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExecutorRejected(f"JSON root must be an object: {path}")
    return value


def normalized_path(path: Path) -> str:
    """Canonical Windows-style path for case-insensitive boundary checks."""
    value = str(path.resolve(strict=False)).replace("/", "\\")
    while len(value) > 3 and value.endswith("\\"):
        value = value[:-1]
    return value.casefold()


def is_within(path: Path, parent: Path) -> bool:
    child = normalized_path(path)
    base = normalized_path(parent)
    return child == base or child.startswith(base + "\\")


def locate_project_root(manifest_path: Path) -> Path:
    resolved = manifest_path.resolve(strict=False)
    for candidate in (resolved.parent, *resolved.parents):
        if all((candidate / marker).is_dir() for marker in ("dataset", "scenes", "scripts")):
            return candidate
    raise ExecutorRejected(
        "cannot derive project root from manifest; expected dataset/scenes/scripts siblings"
    )


def read_manifest_and_verify_hash(
    manifest_path: Path, expected_sha256: str
) -> tuple[dict[str, Any], str]:
    if not manifest_path.is_file():
        raise ExecutorRejected(f"manifest does not exist: {manifest_path}")
    expected = expected_sha256.strip().casefold()
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise ExecutorRejected("ExpectedManifestSha256 must be a 64-character SHA-256 hex string")
    raw = manifest_path.read_bytes()
    actual = sha256_bytes(raw)
    if actual.casefold() != expected:
        raise ExecutorRejected(
            f"manifest SHA-256 mismatch: expected {expected}, actual {actual}"
        )
    sidecar = manifest_path.with_suffix(".sha256")
    if sidecar.is_file():
        sidecar_value = sidecar.read_text(encoding="ascii").strip().casefold()
        if sidecar_value != actual.casefold():
            raise ExecutorRejected(
                f"manifest sidecar SHA-256 mismatch: {sidecar}; expected {actual}"
            )
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExecutorRejected(f"manifest is not valid UTF-8 JSON: {manifest_path}") from exc
    if not isinstance(value, dict):
        raise ExecutorRejected("manifest root must be a JSON object")
    return value, actual


def require_equal(errors: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def require_casefold_equal(errors: list[str], label: str, actual: Any, expected: Any) -> None:
    if str(actual).casefold() != str(expected).casefold():
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def manifest_task_errors(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    request_id = manifest.get("request_id")
    if request_id not in ALLOWED_TASKS:
        errors.append(
            f"request_id is not an allowed Phase-A task (G11 and all other tasks are rejected): {request_id!r}"
        )
        return errors
    expected = ALLOWED_TASKS[request_id]
    require_equal(errors, "manifest_type", manifest.get("manifest_type"), "raw_coarse_phase_a_execution_manifest")
    require_equal(errors, "manifest_version", manifest.get("manifest_version"), "phase-a-readiness-1")
    require_equal(errors, "phase_id", manifest.get("phase_id"), expected["phase_id"])
    task = manifest.get("task")
    if not isinstance(task, dict):
        errors.append("task must be a JSON object")
        return errors
    for key, value in expected.items():
        if key == "phase_id":
            continue
        require_equal(errors, f"task.{key}", task.get(key), value)
    policy = manifest.get("execution_policy")
    if not isinstance(policy, dict):
        errors.append("execution_policy must be a JSON object")
    else:
        require_equal(errors, "execution_policy.resume", policy.get("resume"), False)
        require_equal(errors, "execution_policy.overwrite", policy.get("overwrite"), False)
        require_equal(errors, "execution_policy.new_only", policy.get("new_only"), True)
        require_equal(errors, "execution_policy.default_execute", policy.get("default_execute"), False)
    prototype = manifest.get("prototype")
    if not isinstance(prototype, dict):
        errors.append("prototype must be a JSON object")
    else:
        require_equal(errors, "prototype.planner_version", prototype.get("planner_version"), EXPECTED_PLANNER_VERSION)
        require_equal(errors, "prototype.schema_version", prototype.get("schema_version"), EXPECTED_SCHEMA_VERSION)
        require_equal(errors, "prototype.kernel_version", prototype.get("kernel_version"), EXPECTED_KERNEL_VERSION)
        require_equal(errors, "prototype.parameter_sha256", prototype.get("parameter_sha256"), EXPECTED_PARAMETER_HASH)
        require_equal(errors, "prototype.expected_parameter_sha256", prototype.get("expected_parameter_sha256"), EXPECTED_PARAMETER_HASH)
        require_equal(errors, "prototype.gold_labels_used_for_selection", prototype.get("gold_labels_used_for_selection"), False)
        if not isinstance(prototype.get("selection_forbidden_inputs"), list) or "Stage3" not in prototype.get("selection_forbidden_inputs", []):
            errors.append("prototype selection guard does not forbid Stage3/gold selection inputs")
    if request_id == G25_REQUEST_ID and manifest.get("task", {}).get("prn") != "G25":
        errors.append("G25 manifest task identity is inconsistent")
    if request_id == G16_RETRY_REQUEST_ID:
        require_equal(errors, "fresh_run_only", manifest.get("fresh_run_only"), True)
        require_equal(errors, "resume_allowed", manifest.get("resume_allowed"), False)
        require_equal(errors, "supersedes_interrupted_manifest", manifest.get("supersedes_interrupted_manifest"), G16_REQUEST_ID)
        previous_receipt = manifest.get("previous_interruption_receipt")
        if not isinstance(previous_receipt, str) or not previous_receipt:
            errors.append("previous_interruption_receipt must be a non-empty path")
    return errors


def validate_output_namespace(
    manifest: Mapping[str, Any],
    project_root: Path,
    errors: list[str],
    *,
    allow_existing_names: frozenset[str] = frozenset(),
) -> Path | None:
    output = manifest.get("output")
    if not isinstance(output, dict) or not isinstance(output.get("namespace"), str):
        errors.append("output.namespace is missing")
        return None
    value = Path(output["namespace"])
    if not value.is_absolute():
        errors.append("output.namespace must be absolute")
        return None
    output_path = value.resolve(strict=False)
    output_root_name = RETRY_OUTPUT_ROOT_NAME if manifest.get("request_id") == G16_RETRY_REQUEST_ID else EXPECTED_OUTPUT_ROOT_NAME
    expected_root = project_root / "dataset_generation_logs" / "sampling_validation" / output_root_name
    if not is_within(output_path, expected_root):
        errors.append("output namespace is outside the frozen Phase-A output root")
    if "\\sage_results\\" in normalized_path(output_path) or "/sage_results/" in str(output_path).casefold():
        errors.append("output namespace is under sage_results")
    forbidden_names = {
        "batch_sampled_v1_2_prototype",
        "batch_sampled_v1_2_prototype_v2",
        "batch_sampled_v1_2_prototype_v2_retry",
        "batch_sampled_v1_2_a0_offline",
        "batch_sampled_v1_2_kernel_alignment",
        "batch_sampled_v1_2_kernel_alignment_v2",
    }
    if any(part.casefold() in forbidden_names for part in output_path.parts):
        errors.append("output namespace collides with an immutable old prototype/alignment namespace")
    if output_path.exists():
        existing_names = frozenset(item.name for item in output_path.iterdir())
        if not existing_names.issubset(allow_existing_names):
            errors.append("output namespace already exists; new_only forbids reuse or resume")
    if not is_within(output_path, project_root):
        errors.append("output namespace escapes project root")
    return output_path


def load_inventory_row(project_root: Path, scene_id: str, prn: str, channel: int, errors: list[str]) -> dict[str, Any] | None:
    inventory_path = project_root / "dataset" / "dataset_inventory.csv"
    if not inventory_path.is_file():
        errors.append(f"dataset inventory missing: {inventory_path}")
        return None
    with inventory_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    matches = [row for row in rows if row.get("scene_id", "").casefold() == scene_id.casefold()]
    if len(matches) != 1:
        errors.append(f"inventory scene row is not unique for {scene_id}: {len(matches)} rows")
        return None
    row = matches[0]
    try:
        mapping = json.loads(row.get("prn_tracking_channel_map", "{}"))
    except json.JSONDecodeError:
        errors.append("inventory prn_tracking_channel_map is invalid JSON")
        return row
    try:
        channels = sorted({int(value) for value in mapping.get(prn, [])})
    except (TypeError, ValueError):
        errors.append(f"inventory channel mapping is not integer-valued for {scene_id}/{prn}")
        channels = []
    if channels != [channel]:
        errors.append(
            f"inventory mapping for {scene_id}/{prn} is {channels}; exact requested channel is [{channel}]"
        )
    for key, expected in (
        ("sampling_rate_hz", EXPECTED_SAMPLE_RATE_HZ),
        ("gnss_sdr_status", "SUCCESS"),
        ("tracking_exists", "true"),
        ("telemetry_exists", "true"),
        ("rinex_nav_exists", "true"),
        ("trajectory_exists", "true"),
        ("satellite_geometry_status", "completed"),
    ):
        actual = row.get(key)
        if str(actual).casefold() != str(expected).casefold():
            errors.append(f"inventory.{key}: expected {expected!r}, got {actual!r}")
    return row


def receipt_path_value(receipt: Mapping[str, Any]) -> Path | None:
    value = receipt.get("path")
    return Path(value) if isinstance(value, str) and value else None


def check_file_receipt(
    errors: list[str], label: str, receipt: Mapping[str, Any] | None, expected_path: Path | None, *, hash_content: bool
) -> Path | None:
    if not isinstance(receipt, Mapping):
        errors.append(f"manifest input receipt missing: {label}")
        return None
    recorded = receipt_path_value(receipt)
    if recorded is None or expected_path is None:
        errors.append(f"manifest input path missing: {label}")
        return None
    if normalized_path(recorded) != normalized_path(expected_path):
        errors.append(f"{label} path differs from current metadata-derived path")
    if not recorded.is_file():
        errors.append(f"{label} does not exist: {recorded}")
        return recorded
    if not bool(receipt.get("exists")):
        errors.append(f"{label} manifest receipt says exists=false")
    current_size = recorded.stat().st_size
    if receipt.get("size_bytes") != current_size:
        errors.append(f"{label} size changed: manifest={receipt.get('size_bytes')}, current={current_size}")
    if hash_content:
        expected_hash = receipt.get("sha256")
        actual_hash = sha256_file(recorded)
        if not expected_hash or actual_hash.casefold() != str(expected_hash).casefold():
            errors.append(f"{label} SHA-256 changed")
    return recorded


def check_inputs(
    manifest: Mapping[str, Any], project_root: Path, errors: list[str]
) -> dict[str, Any]:
    task = manifest["task"]
    scene_root = project_root / "scenes" / task["scene_id"]
    metadata_path = scene_root / "metadata.json"
    metadata_receipt = manifest.get("inputs", {}).get("metadata")
    if isinstance(metadata_receipt, str):
        recorded_metadata_path = Path(metadata_receipt)
        if normalized_path(recorded_metadata_path) != normalized_path(metadata_path):
            errors.append("metadata path differs from current scene-derived path")
        if not recorded_metadata_path.is_file():
            errors.append(f"metadata does not exist: {recorded_metadata_path}")
        else:
            expected_metadata_hash = manifest.get("inputs", {}).get("input_hash_basis", {}).get("metadata_sha256")
            if expected_metadata_hash and sha256_file(recorded_metadata_path).casefold() != str(expected_metadata_hash).casefold():
                errors.append("metadata SHA-256 changed since readiness receipt")
    else:
        check_file_receipt(errors, "metadata", metadata_receipt, metadata_path, hash_content=True)
    if not metadata_path.is_file():
        return {}
    metadata = load_json(metadata_path)
    require_equal(errors, "metadata.scene_id", metadata.get("scene_id"), task["scene_id"])
    require_equal(errors, "metadata.signal.sample_rate_hz", metadata.get("signal", {}).get("sample_rate_hz"), EXPECTED_SAMPLE_RATE_HZ)
    require_equal(errors, "metadata.signal.complex_iq", metadata.get("signal", {}).get("complex_iq"), True)
    raw_value = metadata.get("raw_iq", {}).get("path")
    if not raw_value:
        errors.append("metadata.raw_iq.path is missing")
        raw_path = None
    else:
        raw_path = Path(str(raw_value))
        if not raw_path.is_absolute():
            raw_path = (scene_root / raw_path).resolve()
        else:
            raw_path = raw_path.resolve(strict=False)
    raw_receipt = manifest.get("inputs", {}).get("raw_iq")
    current_raw_stat: os.stat_result | None = None
    if raw_path is not None:
        recorded_raw = check_file_receipt(errors, "raw IQ", raw_receipt, raw_path, hash_content=False)
        if recorded_raw is not None and recorded_raw.is_file():
            current_raw_stat = recorded_raw.stat()
            if current_raw_stat.st_size % 4 != 0 or current_raw_stat.st_size <= 0:
                errors.append("raw IQ is empty or not aligned to interleaved int16 I/Q samples")
            if raw_receipt.get("mtime_ns") is not None and raw_receipt.get("mtime_ns") != current_raw_stat.st_mtime_ns:
                errors.append("raw IQ mtime changed since readiness receipt")
    stage0_path = scene_root / "sage_results" / "nav_sage_v2" / task["prn"] / "stage0_valid_40ms_windows.csv"
    stage0_receipt = manifest.get("inputs", {}).get("stage0_valid_40ms_windows")
    check_file_receipt(errors, "Stage0 catalog", stage0_receipt, stage0_path, hash_content=True)
    if stage0_path.is_file() and stage0_path.stat().st_size == 0:
        errors.append("Stage0 catalog is empty")
    track_path = scene_root / "gnss_sdr" / "tracking" / f"{task['scene_id']}_track_ch_{task['tracking_channel']}.mat"
    telemetry_path = scene_root / "gnss_sdr" / "telemetry" / f"{task['scene_id']}_telemetry_ch_{task['tracking_channel']}.dat"
    navigation_path = scene_root / "navigation" / "rinex_nav" / "RINEXFILE.26N"
    trajectory_value = metadata.get("trajectory", {}).get("file")
    trajectory_path = Path(str(trajectory_value)) if trajectory_value else None
    if trajectory_path is not None and not trajectory_path.is_absolute():
        trajectory_path = (scene_root / trajectory_path).resolve()
    geometry_paths: list[Path] = []
    for value in metadata.get("satellite_geometry", {}).get("outputs", []):
        path = Path(str(value))
        geometry_paths.append(path.resolve() if path.is_absolute() else (scene_root / path).resolve())
    inputs = manifest.get("inputs", {})
    check_file_receipt(errors, "tracking MAT", inputs.get("tracking_mat"), track_path, hash_content=True)
    check_file_receipt(errors, "telemetry DAT", inputs.get("telemetry_dat"), telemetry_path, hash_content=True)
    check_file_receipt(errors, "RINEX NAV", inputs.get("rinex_nav"), navigation_path, hash_content=True)
    check_file_receipt(errors, "trajectory NMEA", inputs.get("trajectory_nmea"), trajectory_path, hash_content=True)
    geometry_receipts = inputs.get("satellite_geometry_csv")
    if not isinstance(geometry_receipts, list) or len(geometry_receipts) != len(geometry_paths):
        errors.append("satellite geometry receipt count differs from current metadata")
    else:
        for index, (receipt, path) in enumerate(zip(geometry_receipts, geometry_paths)):
            check_file_receipt(errors, f"satellite geometry CSV {index}", receipt, path, hash_content=True)
    # Recompute the same readiness input bundle hash without reading raw IQ
    # content.  This catches path/stat, metadata, Stage0, and exact channel
    # mapping drift while preserving the preparation rule that raw bytes are
    # not fully hashed in validation-only mode.
    inventory_path = project_root / "dataset" / "dataset_inventory.csv"
    inventory_candidates: list[int] = []
    if inventory_path.is_file():
        with inventory_path.open("r", encoding="utf-8-sig", newline="") as handle:
            inventory_rows = list(csv.DictReader(handle))
        matching_rows = [row for row in inventory_rows if row.get("scene_id", "").casefold() == str(task["scene_id"]).casefold()]
        if len(matching_rows) == 1:
            try:
                mapping = json.loads(matching_rows[0].get("prn_tracking_channel_map", "{}"))
                inventory_candidates = sorted({int(value) for value in mapping.get(str(task["prn"]), [])})
            except (json.JSONDecodeError, TypeError, ValueError):
                inventory_candidates = []
    current_basis = {
        "hash_scope": "readiness-input-bundle; raw content is not hashed in preparation",
        "scene_id": task["scene_id"],
        "prn": task["prn"],
        "tracking_channel": task["tracking_channel"],
        "sample_rate_hz": task["sample_rate_hz"],
        "metadata_sha256": sha256_file(metadata_path) if metadata_path.is_file() else None,
        "stage0_sha256": sha256_file(stage0_path) if stage0_path.is_file() else None,
        "raw_path": str(raw_path) if raw_path else None,
        "raw_size_bytes": current_raw_stat.st_size if current_raw_stat else None,
        "raw_mtime_ns": current_raw_stat.st_mtime_ns if current_raw_stat else None,
        "inventory_channel_candidates": inventory_candidates,
    }
    current_input_hash = sha256_bytes(canonical_json(current_basis).encode("utf-8"))
    recorded_input_hash = manifest.get("inputs", {}).get("input_hash_sha256")
    if not recorded_input_hash or current_input_hash.casefold() != str(recorded_input_hash).casefold():
        errors.append(f"input_hash_sha256 changed: manifest={recorded_input_hash}, current={current_input_hash}")
    return {
        "metadata_path": str(metadata_path),
        "raw_path": str(raw_path) if raw_path else None,
        "stage0_path": str(stage0_path),
        "raw_content_hash_checked": False,
        "stage0_sha256_current": sha256_file(stage0_path) if stage0_path.is_file() else None,
        "input_hash_sha256_current": current_input_hash,
    }


def read_candidate_backend(project_root: Path, manifest: Mapping[str, Any], errors: list[str]) -> dict[str, Any]:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        errors.append("runtime receipt is missing")
        return {}
    expected = Path(str(runtime.get("python_executable", "")))
    if normalized_path(expected) != normalized_path(EXPECTED_PYTHON):
        errors.append(f"manifest Python executable is not the frozen path: {expected}")
    if not expected.is_file():
        errors.append(f"frozen Python executable does not exist: {expected}")
        return {"python_executable": str(expected), "available": False}
    environment_receipt_path = Path(manifest.get("_environment_receipt_path", ""))
    if not environment_receipt_path.is_file():
        environment_receipt_path = project_root / "dataset_generation_logs" / "sampling_validation" / EXPECTED_MANIFEST_NAMESPACE / "environment_receipt.json"
    if environment_receipt_path.is_file():
        frozen_environment = load_json(environment_receipt_path)
        recorded_hash = frozen_environment.get("python_executable_sha256")
        if recorded_hash and sha256_file(expected).casefold() != str(recorded_hash).casefold():
            errors.append("Python executable SHA-256 differs from frozen environment receipt")
    probe_code = r'''
import contextlib, io, json, platform, sys
info = {"python_version": platform.python_version(), "architecture": platform.architecture()[0], "executable": sys.executable}
try:
    import numpy as np
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        np.show_config()
    info["numpy"] = {"available": True, "version": np.__version__, "path": np.__file__, "config": out.getvalue()}
except Exception as exc:
    info["numpy"] = {"available": False, "error": repr(exc)}
try:
    import scipy
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        scipy.show_config()
    info["scipy"] = {"available": True, "version": scipy.__version__, "path": scipy.__file__, "config": out.getvalue()}
except Exception as exc:
    info["scipy"] = {"available": False, "error": repr(exc)}
try:
    sys.path.insert(0, sys.argv[1])
    import run_batch_sampling_raw_coarse_v1_2_v2 as v2
    info["v2"] = {"parameter_hash": v2.PARAMETER_HASH, "kernel_version": v2.KERNEL_VERSION, "planner_version": v2.PLANNER_VERSION, "task_aware_entrypoint": callable(getattr(v2, "process_window_numpy", None)) and callable(getattr(v2, "legacy", None).RawChunkReader) and all(callable(getattr(v2.legacy, name, None)) for name in ("build_promotion_manifest", "project_budget", "load_gold_after_freeze", "replay_coverage"))}
except Exception as exc:
    info["v2"] = {"import_error": repr(exc), "task_aware_entrypoint": False}
print(json.dumps(info, ensure_ascii=True))
'''
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    try:
        completed = subprocess.run(
            [str(expected), "-c", probe_code, str((project_root / "scripts" / "sage_pipeline").resolve())],
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"compiled Python probe failed: {exc}")
        return {"python_executable": str(expected), "available": False}
    if completed.returncode != 0:
        errors.append(f"compiled Python probe returned {completed.returncode}: {completed.stderr[-500:]}")
        return {"python_executable": str(expected), "available": False, "returncode": completed.returncode}
    try:
        receipt = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"compiled Python probe did not return JSON: {exc}")
        return {"python_executable": str(expected), "available": False}
    require_equal(errors, "Python version", receipt.get("python_version"), EXPECTED_PYTHON_VERSION)
    require_equal(errors, "NumPy version", receipt.get("numpy", {}).get("version"), EXPECTED_NUMPY_VERSION)
    require_equal(errors, "SciPy version", receipt.get("scipy", {}).get("version"), EXPECTED_SCIPY_VERSION)
    if not receipt.get("numpy", {}).get("available") or not receipt.get("scipy", {}).get("available"):
        errors.append("NumPy/SciPy compiled backend is not importable")
    config = (receipt.get("numpy", {}).get("config", "") + receipt.get("scipy", {}).get("config", "")).casefold()
    if "openblas" not in config:
        errors.append("NumPy/SciPy backend receipt does not identify OpenBLAS")
    v2 = receipt.get("v2", {})
    require_equal(errors, "v2 parameter hash", v2.get("parameter_hash"), EXPECTED_PARAMETER_HASH)
    require_equal(errors, "v2 kernel version", v2.get("kernel_version"), EXPECTED_KERNEL_VERSION)
    require_equal(errors, "v2 planner version", v2.get("planner_version"), EXPECTED_PLANNER_VERSION)
    return {"python_executable": str(expected), "available": True, **receipt}


def check_frozen_source_hashes(project_root: Path, manifest: Mapping[str, Any], errors: list[str]) -> None:
    hashes = manifest.get("hashes")
    if not isinstance(hashes, Mapping):
        errors.append("manifest hashes object is missing")
        return
    current_files = {
        "pipeline_script_sha256": project_root / PIPELINE_RELATIVE,
        "prototype_script_sha256": project_root / V2_RELATIVE,
        "alignment_report_sha256": project_root / ALIGNMENT_REPORT_RELATIVE,
        "alignment_parameter_file_sha256": project_root / ALIGNMENT_DIR_RELATIVE / "coarse_parameter.json",
        "alignment_parameter_hash_file_sha256": project_root / ALIGNMENT_DIR_RELATIVE / "coarse_parameter.sha256",
    }
    if manifest.get("request_id") == G16_RETRY_REQUEST_ID:
        current_files["executor_script_sha256"] = project_root / "scripts" / "sage_pipeline" / "run_raw_coarse_phase_a.py"
    for key, path in current_files.items():
        expected = hashes.get(key)
        if not path.is_file():
            errors.append(f"frozen source file missing: {path}")
        elif not expected or sha256_file(path).casefold() != str(expected).casefold():
            errors.append(f"frozen source hash changed: {key}")
    parameter_file = current_files["alignment_parameter_hash_file_sha256"]
    if parameter_file.is_file() and parameter_file.read_text(encoding="ascii").strip() != EXPECTED_PARAMETER_HASH:
        errors.append("alignment parameter hash file does not contain the frozen parameter hash")
    report = project_root / ALIGNMENT_REPORT_RELATIVE
    if report.is_file():
        report_text = report.read_text(encoding="utf-8-sig")
        for marker in ("KERNEL_ALIGNMENT_PASS", "NUMERIC_MICROBENCHMARK_PASS", EXPECTED_PARAMETER_HASH):
            if marker not in report_text:
                errors.append(f"alignment report missing frozen marker: {marker}")
    else:
        errors.append("alignment report is missing")


def check_g16_qa_receipt(project_root: Path, g16_manifest_sha256: str) -> tuple[bool, str]:
    path = project_root / G16_QA_RECEIPT_RELATIVE
    if not path.is_file():
        return False, f"independent G16 QA PASS receipt is missing: {path}"
    try:
        receipt = load_json(path)
    except ExecutorRejected as exc:
        return False, str(exc)
    required = {
        "receipt_type": "independent_g16_phase_a_qa_pass",
        "qa_status": "PASS",
        "request_id": G16_REQUEST_ID,
        "manifest_sha256": g16_manifest_sha256,
    }
    for key, value in required.items():
        if receipt.get(key) != value:
            return False, f"G16 QA receipt field {key} is not the required value"
    if receipt.get("executor_status") != "completed" or receipt.get("exit_code") != 0:
        return False, "G16 QA receipt does not attest a completed zero-exit executor run"
    if receipt.get("raw_read_status") != "ok" or receipt.get("outputs_complete") is not True:
        return False, "G16 QA receipt does not attest complete raw output"
    return True, f"verified independent G16 QA receipt: {path}"


def validate_manifest(
    manifest_path: Path,
    expected_sha256: str,
    *,
    allow_existing_names: frozenset[str] = frozenset(),
) -> ValidationResult:
    manifest_path = manifest_path.resolve(strict=False)
    manifest, actual_sha256 = read_manifest_and_verify_hash(manifest_path, expected_sha256)
    project_root = locate_project_root(manifest_path)
    result = ValidationResult(manifest_path, project_root, manifest, actual_sha256)
    result.errors.extend(manifest_task_errors(manifest))
    output_path = validate_output_namespace(manifest, project_root, result.errors, allow_existing_names=allow_existing_names)
    task = manifest.get("task", {})
    if isinstance(task, dict) and task.get("scene_id") and task.get("prn"):
        load_inventory_row(project_root, str(task["scene_id"]), str(task["prn"]), int(task.get("tracking_channel", -1)), result.errors)
    if not result.errors:
        check_inputs(manifest, project_root, result.errors)
    else:
        # Still report frozen backend information in validation-only output,
        # but avoid opening scene files after an identity failure.
        result.warnings.append("input inspection skipped after manifest identity/policy failure")
    check_frozen_source_hashes(project_root, manifest, result.errors)
    result.backend = read_candidate_backend(project_root, manifest, result.errors)
    result.evaluator_api_available = bool(result.backend.get("v2", {}).get("task_aware_entrypoint"))
    if manifest.get("request_id") == G25_REQUEST_ID:
        g16_manifest = project_root / "dataset_generation_logs" / "sampling_validation" / EXPECTED_MANIFEST_NAMESPACE / "phase_a1_g16_20260812" / "execution_manifest.json"
        g16_hash = sha256_file(g16_manifest) if g16_manifest.is_file() else ""
        result.g16_qa_pass, result.g16_qa_reason = check_g16_qa_receipt(project_root, g16_hash)
        if not result.g16_qa_pass:
            result.errors.append(f"G25 execution gate: {result.g16_qa_reason}")
    elif manifest.get("request_id") == G16_REQUEST_ID:
        result.g16_qa_reason = "G16 is the only first task; no prior QA receipt is required"
    if output_path is None:
        result.errors.append("output namespace could not be resolved")
    return result


def dry_run_lines(result: ValidationResult) -> list[str]:
    manifest = result.manifest
    task = result.task
    inputs = manifest.get("inputs", {})
    output = manifest.get("output", {})
    lines = [
        "VALIDATION_ONLY=true",
        f"REQUEST_ID={manifest.get('request_id')}",
        f"TASK={task.get('scene_id')}/{task.get('prn')}/ch{task.get('tracking_channel')}/{task.get('sample_rate_hz')}",
        f"RAW_IQ={inputs.get('raw_iq', {}).get('path')}",
        f"STAGE0={inputs.get('stage0_valid_40ms_windows', {}).get('path')}",
        f"BACKEND_PYTHON={result.backend.get('python_executable')}",
        f"BACKEND_PYTHON_VERSION={result.backend.get('python_version')}",
        f"NUMPY={result.backend.get('numpy', {}).get('version')}",
        f"SCIPY={result.backend.get('scipy', {}).get('version')}",
        f"KERNEL_VERSION={manifest.get('prototype', {}).get('kernel_version')}",
        f"PARAMETER_SHA256={manifest.get('prototype', {}).get('parameter_sha256')}",
        f"GOLD_LABELS_USED_FOR_SELECTION={manifest.get('prototype', {}).get('gold_labels_used_for_selection')}",
        f"OUTPUT_NAMESPACE={output.get('namespace')}",
        f"OUTPUT_EXISTS={Path(output.get('namespace', '')) .exists() if output.get('namespace') else 'unknown'}",
        f"EVALUATOR_TASK_API_AVAILABLE={result.evaluator_api_available}",
        f"EXECUTION_ELIGIBLE={result.execution_eligible}",
        f"EXECUTE_DISPATCH_AVAILABLE={result.execute_dispatch_available}",
    ]
    if result.g16_qa_reason:
        lines.append(f"G16_QA_GATE={result.g16_qa_pass} ({result.g16_qa_reason})")
    if result.errors:
        lines.append("REASONS:")
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.append("WARNINGS:")
        lines.extend(f"- {warning}" for warning in result.warnings)
    lines.append("RAW_IQ_READ_DURING_VALIDATION=false")
    return lines


def acquire_global_lock(project_root: Path, request_id: str) -> tuple[int, Path]:
    path = project_root / LOCK_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"request_id": request_id, "pid": os.getpid(), "created_at_utc": utc_now()})
    try:
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
        return descriptor, path
    except FileExistsError as exc:
        raise ExecutorRejected(f"Phase-A global lock already exists: {path}; refusing concurrent or stale execution") from exc


def release_global_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def collect_output_files(output_root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    if not output_root.is_dir():
        return files
    for path in sorted(item for item in output_root.rglob("*") if item.is_file()):
        files.append({"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return files


def collect_progress(output_root: Path) -> dict[str, Any]:
    progress: dict[str, Any] = {
        "raw_bytes": None,
        "chunks": None,
        "windows_processed": None,
        "last_progress_file": None,
        "last_event": None,
        "last_timestamp_utc": None,
        "last_chunk": None,
        "elapsed_s": None,
        "estimated_remaining_s": None,
    }
    for path in output_root.rglob("*") if output_root.is_dir() else ():
        if not path.is_file():
            continue
        name = path.name.casefold()
        if name in {"cost_measurement.json", "run_manifest.json", "execution_summary.json", "checkpoint.json"}:
            try:
                value = load_json(path)
            except ExecutorRejected:
                continue
            for target, keys in {
                "raw_bytes": ("bytes_read_actual", "bytes_read_actual_contiguous_chunks", "raw_bytes"),
                "chunks": ("chunk_count", "chunks", "chunks_processed"),
                "windows_processed": ("windows_processed", "processed_windows", "stage0_window_count"),
            }.items():
                for key in keys:
                    if value.get(key) is not None:
                        progress[target] = value[key]
                        break
        if "progress" in name or "checkpoint" in name:
            progress["last_progress_file"] = str(path)
        if name == "progress.jsonl":
            try:
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                if records:
                    last = records[-1]
                    progress.update(
                        {
                            "last_event": last.get("event"),
                            "last_timestamp_utc": last.get("timestamp_utc"),
                            "last_chunk": last.get("chunk_id") or last.get("current_chunk"),
                            "elapsed_s": last.get("elapsed_s"),
                            "estimated_remaining_s": last.get("estimated_remaining_s"),
                            "windows_processed": last.get("processed_windows_total", progress["windows_processed"]),
                            "raw_bytes": last.get("bytes_read_total", progress["raw_bytes"]),
                        }
                    )
            except (OSError, ValueError, TypeError):
                progress["progress_parse_error"] = True
    return progress


def import_v2(project_root: Path) -> Any:
    scripts_dir = str((project_root / "scripts" / "sage_pipeline").resolve())
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    module = importlib.import_module("run_batch_sampling_raw_coarse_v1_2_v2")
    return module


def write_csv_file(path: Path, rows: Iterable[Mapping[str, Any]], fields: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def append_progress(path: Path, event: str, **values: Any) -> None:
    timestamp = utc_now()
    _EXECUTION_CONTEXT["last_progress_at_utc"] = timestamp
    _EXECUTION_CONTEXT["last_progress_monotonic"] = time.monotonic()
    record = {
        "timestamp_utc": timestamp,
        "event": event,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "phase": _EXECUTION_CONTEXT.get("phase"),
        "current_function": _EXECUTION_CONTEXT.get("current_function"),
        "current_chunk": _EXECUTION_CONTEXT.get("current_chunk"),
        **values,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def run_raw_pass_adapter(v2: Any, task: Any, raw_path: Path, rows: Any, profiles: Any, progress_path: Path) -> Any:
    """Orchestrate the frozen v2 NumPy window kernel over contiguous chunks."""
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    tracemalloc.start()
    feature_rows: dict[str, list[dict[str, Any]]] = {profile.profile_id: [] for profile in profiles}
    chunk_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    actual_bytes = 0
    ca_code = v2.cached_ca_code(task.prn)
    reader = v2.legacy.RawChunkReader(raw_path, rows)
    for plan, view in reader.iter_chunks():
        chunk_start = time.perf_counter()
        set_execution_context(phase="raw_coarse", current_function="run_raw_pass_adapter", current_chunk=plan.chunk_id)
        try:
            for row_index in plan.window_indices:
                window_output = v2.process_window_numpy(view, plan.start_sample, rows[row_index], profiles, ca_code)
                for profile_id, output in window_output.items():
                    feature_rows[profile_id].append(output)
            actual_bytes += plan.byte_count
            chunk_rows.append({
                "chunk_id": plan.chunk_id,
                "start_sample": plan.start_sample,
                "end_sample_exclusive": plan.end_sample_exclusive,
                "bytes_read": plan.byte_count,
                "covered_window_start_id": rows[plan.window_indices[0]].window_id,
                "covered_window_end_id": rows[plan.window_indices[-1]].window_id,
                "covered_window_count": len(plan.window_indices),
                "reused_samples_within_covered_windows": sum(v2.legacy.WINDOW_SAMPLES for _ in plan.window_indices) - sum(max(0, min(rows[index].sample_start + v2.legacy.WINDOW_SAMPLES, plan.end_sample_exclusive) - max(rows[index].sample_start, plan.start_sample)) for index in plan.window_indices),
                "chunk_wall_clock_s": time.perf_counter() - chunk_start,
                "raw_read_status": "ok",
                "error": "",
            })
            elapsed = time.perf_counter() - start_wall
            completed_chunks = len(chunk_rows)
            rate = completed_chunks / elapsed if elapsed > 0 else 0.0
            append_progress(
                progress_path,
                "chunk_completed",
                chunk_id=plan.chunk_id,
                processed_windows=len(plan.window_indices),
                processed_windows_total=sum(len(item.window_indices) for item in reader.plans[:completed_chunks]),
                total_windows=len(rows),
                bytes_read=plan.byte_count,
                bytes_read_total=actual_bytes,
                elapsed_s=elapsed,
                estimated_remaining_s=(len(reader.plans) - completed_chunks) / rate if rate > 0 else None,
                last_progress_age_s=0.0,
            )
        except Exception as exc:
            errors.append(f"{plan.chunk_id}: {type(exc).__name__}: {exc}")
            chunk_rows.append({
                "chunk_id": plan.chunk_id,
                "start_sample": plan.start_sample,
                "end_sample_exclusive": plan.end_sample_exclusive,
                "bytes_read": plan.byte_count,
                "covered_window_start_id": rows[plan.window_indices[0]].window_id,
                "covered_window_end_id": rows[plan.window_indices[-1]].window_id,
                "covered_window_count": len(plan.window_indices),
                "reused_samples_within_covered_windows": "",
                "chunk_wall_clock_s": time.perf_counter() - chunk_start,
                "raw_read_status": "error",
                "error": str(exc),
            })
            append_progress(progress_path, "chunk_failed", chunk_id=plan.chunk_id, processed_windows=0, total_windows=len(rows), error=str(exc), elapsed_s=time.perf_counter() - start_wall)
    theoretical_bytes = len(rows) * v2.legacy.WINDOW_SAMPLES * 4
    unique_window_samples = v2.legacy.merged_interval_samples(rows)
    actual_samples = actual_bytes // 4
    wall = time.perf_counter() - start_wall
    _current_memory, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    cost = {
        "task_id": task.task_id,
        "raw_path": str(raw_path),
        "raw_read_status": "ok" if not errors else "error",
        "window_count": len(rows),
        "chunk_count": len(reader.plans),
        "fopen_count_actual": len(reader.plans),
        "fopen_count_theoretical_per_window_reopen": len(rows),
        "fseek_count_actual": len(reader.plans),
        "fseek_count_theoretical_per_window_reopen": len(rows),
        "bytes_read_actual_contiguous_chunks": actual_bytes,
        "bytes_read_theoretical_per_window_reopen": theoretical_bytes,
        "bytes_read_unique_stage0_window_union": unique_window_samples * 4,
        "reused_samples_from_overlapping_windows": len(rows) * v2.legacy.WINDOW_SAMPLES - unique_window_samples,
        "chunk_gap_samples_read": max(0, actual_samples - unique_window_samples),
        "read_amplification_vs_window_reopen": actual_bytes / theoretical_bytes if theoretical_bytes else 0.0,
        "read_reduction_vs_window_reopen": 1.0 - actual_bytes / theoretical_bytes if theoretical_bytes else 0.0,
        "wall_clock_s": wall,
        "cpu_time_s": time.process_time() - start_cpu,
        "peak_memory_bytes_tracemalloc": peak_memory,
        "per_window_coarse_avg_wall_clock_s": wall / len(rows) if rows else 0.0,
        "errors": errors,
        "cost_is_shared_raw_pass_for_profiles": True,
        "full_stage1_comparison": {
            "historical_g16_stage1_wall_clock_s": v2.legacy.FULL_STAGE1_G16_BACKGROUND_SECONDS,
            "coarse_wall_clock_fraction_of_historical_stage1": wall / v2.legacy.FULL_STAGE1_G16_BACKGROUND_SECONDS if task.prn == "G16" else "not_applicable",
            "comparison_is_stage1_only_not_total_pipeline": True,
        },
    }
    return SimpleNamespace(task=task, profile_rows=feature_rows, chunk_rows=chunk_rows, cost=cost, errors=errors)


def find_v2_task(v2: Any, task: Mapping[str, Any]) -> Any:
    for candidate in v2.TASKS:
        if (
            candidate.scene_id == task.get("scene_id")
            and candidate.prn == task.get("prn")
            and candidate.tracking_channel == task.get("tracking_channel")
        ):
            return candidate
    raise ExecutorRejected("manifest task is not represented by the frozen v2 task table")


def run_task_with_v2_adapter(result: ValidationResult, output_root: Path, stdout_path: Path, stderr_path: Path) -> int:
    """Run exactly one manifest task through existing v2 scientific functions.

    This is orchestration only.  It does not implement correlation, scoring,
    or promotion; those remain in v2.  Gold is opened only after all coarse
    production files are frozen, and is used for replay/reporting only.
    """
    v2 = import_v2(result.project_root)
    manifest = result.manifest
    task = find_v2_task(v2, manifest["task"])
    if v2.PARAMETER_HASH != EXPECTED_PARAMETER_HASH or v2.KERNEL_VERSION != EXPECTED_KERNEL_VERSION:
        raise ExecutorRejected("v2 parameter or kernel identity changed after validation")
    progress_path = output_root / "progress.jsonl"
    log_lines = [f"task={task.task_id}", f"parameter_hash={v2.PARAMETER_HASH}", "gold_labels_used_for_selection=false"]
    try:
        metadata, raw_path, total_samples = v2.legacy.load_metadata_and_raw(result.project_root, task)
        rows = v2.legacy.load_stage0(result.project_root, task, total_samples)
        append_progress(progress_path, "input_loaded", total_windows=len(rows), raw_bytes=raw_path.stat().st_size)
        v2.write_json(output_root / "coarse_parameter.json", v2.PARAMETER_SPEC)
        (output_root / "coarse_parameter.sha256").write_text(v2.PARAMETER_HASH + "\n", encoding="ascii")
        v2.write_json(output_root / "selection_freeze.json", {
            "task_id": task.task_id,
            "selection_frozen": True,
            "selection_frozen_at_utc": utc_now(),
            "parameter_hash": v2.PARAMETER_HASH,
            "gold_labels_used_for_selection": False,
            "stage1_stage2_stage3_stage4_used_for_selection": False,
        })
        task_dir = output_root / task.task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        v2.write_json(task_dir / "input_receipt.json", {
            "task_id": task.task_id,
            "scene_id": task.scene_id,
            "prn": task.prn,
            "tracking_channel": task.tracking_channel,
            "sample_rate_hz": EXPECTED_SAMPLE_RATE_HZ,
            "metadata_path": str(result.project_root / "scenes" / task.scene_id / "metadata.json"),
            "metadata_sha256": sha256_file(result.project_root / "scenes" / task.scene_id / "metadata.json"),
            "raw_path_from_metadata": str(raw_path),
            "raw_bytes": raw_path.stat().st_size,
            "stage0_path": str(result.project_root / "scenes" / task.scene_id / "sage_results" / task.result_dir / "stage0_valid_40ms_windows.csv"),
            "stage0_sha256": sha256_file(result.project_root / "scenes" / task.scene_id / "sage_results" / task.result_dir / "stage0_valid_40ms_windows.csv"),
            "stage0_window_count": len(rows),
            "raw_read_mode": "read_only",
        })
        append_progress(progress_path, "selection_frozen", total_windows=len(rows), gold_labels_used_for_selection=False)
        raw_result = run_raw_pass_adapter(v2, task, raw_path, rows, v2.PROFILES, progress_path)
        v2.write_csv(task_dir / "chunk_manifest.csv", raw_result.chunk_rows, [
            "chunk_id", "start_sample", "end_sample_exclusive", "bytes_read", "covered_window_start_id", "covered_window_end_id", "covered_window_count", "reused_samples_within_covered_windows", "chunk_wall_clock_s", "raw_read_status", "error",
        ])
        append_progress(progress_path, "raw_pass_completed", processed_windows=len(rows), chunks=len(raw_result.chunk_rows), raw_bytes=raw_result.cost.get("bytes_read_actual_contiguous_chunks"), raw_read_status=raw_result.cost.get("raw_read_status"))
        if raw_result.errors:
            raise RuntimeError("raw pass reported errors: " + "; ".join(raw_result.errors))
        promotions: dict[str, list[dict[str, Any]]] = {}
        frozen = {"selection_frozen": True, "gold_labels_used_for_selection": False}
        for profile in v2.PROFILES:
            feature_rows = [dict(row, profile_id=profile.profile_id) for row in raw_result.profile_rows[profile.profile_id]]
            promotion_rows, components = v2.legacy.build_promotion_manifest(feature_rows, profile)
            promotions[profile.profile_id] = promotion_rows
            profile_dir = task_dir / profile.profile_id
            v2.write_csv(profile_dir / "coarse_window_manifest.csv", feature_rows, v2.legacy.manifest_fields())
            v2.write_csv(profile_dir / "promotion_manifest.csv", promotion_rows, v2.legacy.manifest_fields() + ["promotion_status", "promotion_reason", "promotion_component_id", "not_promoted", "coverage_status", "fine_availability"])
            component_rows = [{
                "task_id": task.task_id,
                "profile_id": profile.profile_id,
                "component_id": component.component_id,
                "first_window_id": component.first_window_id,
                "last_window_id": component.last_window_id,
                "component_window_count": len(component.window_ids),
                "promoted_window_count": len(component.promoted_window_ids),
                "max_score_db": component.max_score_db,
                "parameter_hash": v2.PARAMETER_HASH,
                "gold_labels_used_for_selection": "false",
            } for component in components]
            v2.write_csv(profile_dir / "promotion_components.csv", component_rows, ["task_id", "profile_id", "component_id", "first_window_id", "last_window_id", "component_window_count", "promoted_window_count", "max_score_db", "parameter_hash", "gold_labels_used_for_selection"])
            projection = v2.legacy.project_budget({int(row["window_id"]) for row in promotion_rows if row["promotion_status"] == "coarse_promoted"}, components, {row.window_id for row in rows})
            profile_cost = dict(raw_result.cost)
            profile_cost.update({"task_id": task.task_id, "profile_id": profile.profile_id, "promotion_fraction": sum(row["promotion_status"] == "coarse_promoted" for row in promotion_rows) / len(promotion_rows), "component_count": len(components), "potential_fine_window_count": projection["potential_fine_window_count"], "budget_projection": projection["budget_projection"], "closure_missing_count": projection["closure_missing_count"], "parameter_hash": v2.PARAMETER_HASH})
            v2.write_json(profile_dir / "cost_measurement.json", profile_cost)
            v2.write_json(profile_dir / "run_manifest.json", {
                "task_id": task.task_id,
                "profile_id": profile.profile_id,
                "stage0_window_count": len(rows),
                "raw_path": str(raw_path),
                "raw_read_only": True,
                "coarse_only": True,
                "stage1_output_written": False,
                "stage2_stage3_stage4_executed": False,
                "gold_labels_used_for_selection": False,
                "parameter_hash": v2.PARAMETER_HASH,
            })
            append_progress(progress_path, "profile_written", profile_id=profile.profile_id, promoted_windows=sum(row["promotion_status"] == "coarse_promoted" for row in promotion_rows), component_count=len(components))
        # This is post-freeze replay only.  It never feeds back into coarse
        # selection or thresholds.
        gold = v2.legacy.load_gold_after_freeze(result.project_root, task, frozen)
        coverage_summaries: list[dict[str, Any]] = []
        for profile in v2.PROFILES:
            coverage_rows, summary = v2.legacy.replay_coverage(task, profile, promotions[profile.profile_id], gold)
            profile_dir = task_dir / profile.profile_id
            v2.write_csv(profile_dir / "coverage_replay.csv", coverage_rows, ["record_type", "task_id", "profile_id", "event_center_window_id", "center_promoted", "closure_expected_count", "closure_promoted_count", "closure_missing_count", "coverage_status", "gold_labels_used_for_selection"])
            coverage_summaries.append(summary)
        v2.write_json(task_dir / "post_freeze_coverage_summary.json", {
            "task_id": task.task_id,
            "gold_labels_used_for_selection": False,
            "research_pass_not_judged_by_executor": True,
            "profiles": coverage_summaries,
        })
        v2.write_json(output_root / "run_manifest.json", {
            "executor": "run_raw_coarse_phase_a.py",
            "task_id": task.task_id,
            "parameter_hash": v2.PARAMETER_HASH,
            "coarse_only": True,
            "stage1_output_written": False,
            "stage2_stage3_stage4_executed": False,
            "gold_read_after_selection_freeze": True,
            "gold_labels_used_for_selection": False,
            "automatic_next_task": False,
            "status": "completed",
        })
        stdout_path.write_text("\n".join(log_lines + ["raw_pass_completed", "post_freeze_coverage_completed"]) + "\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return 0
    except Exception as exc:
        stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        raise


def write_execution_receipt(
    output_root: Path,
    result: ValidationResult,
    *,
    status: str,
    start_utc: str,
    end_utc: str,
    exit_code: int | None,
    stdout_path: Path | None,
    stderr_path: Path | None,
    error: str | None,
    interruption_reason: str | None = None,
    last_progress_age_s: float | None = None,
) -> Path:
    manifest = result.manifest
    receipt = {
        "receipt_type": "raw_coarse_phase_a_executor_receipt",
        "receipt_version": "executor-1",
        "request_id": manifest.get("request_id"),
        "manifest_sha256": result.manifest_sha256,
        "parameter_sha256": manifest.get("prototype", {}).get("parameter_sha256"),
        "kernel_version": manifest.get("prototype", {}).get("kernel_version"),
        "prototype_script_sha256": manifest.get("hashes", {}).get("prototype_script_sha256"),
        "pipeline_script_sha256": manifest.get("hashes", {}).get("pipeline_script_sha256"),
        "python_executable": result.backend.get("python_executable"),
        "python_executable_sha256": sha256_file(Path(result.backend["python_executable"])) if result.backend.get("python_executable") and Path(result.backend["python_executable"]).is_file() else None,
        "python_version": result.backend.get("python_version"),
        "numpy_version": result.backend.get("numpy", {}).get("version"),
        "scipy_version": result.backend.get("scipy", {}).get("version"),
        "openblas_backend": "openblas" in (json.dumps(result.backend).casefold()),
        "start_utc": start_utc,
        "end_utc": end_utc,
        "exit_code": exit_code,
        "status": status,
        "raw_read_status": "ok" if status == "completed" and exit_code == 0 else status,
        "stdout_log": str(stdout_path) if stdout_path else None,
        "stderr_log": str(stderr_path) if stderr_path else None,
        "error": error,
        "interruption_reason": interruption_reason,
        "interrupt_provenance": dict(_INTERRUPT_PROVENANCE),
        "execution_context": dict(_EXECUTION_CONTEXT),
        "executor_pid": os.getpid(),
        "worker_pid": _WORKER_PID,
        "last_progress_age_s": last_progress_age_s,
        "progress": collect_progress(output_root),
        "output_files": collect_output_files(output_root),
        "resume": False,
        "automatic_next_task": False,
        "gold_labels_used_for_selection": False,
    }
    path = output_root / "execution_receipt.json"
    path.write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return path


def invoke_evaluator(result: ValidationResult) -> int:
    """Run one exact manifest task in a monitored worker process."""
    if not result.evaluator_api_available:
        raise ExecutorRejected(
            "current v2 evaluator does not expose the required task-aware function set; execution is blocked before raw IQ access"
        )
    output_root = Path(result.manifest["output"]["namespace"]).resolve(strict=False)
    output_root.mkdir(parents=True, exist_ok=False)
    stdout_path = output_root / "executor_stdout.log"
    stderr_path = output_root / "executor_stderr.log"
    worker_script = Path(__file__).resolve()
    python_path = Path(result.backend["python_executable"])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    start_utc = utc_now()
    start = time.monotonic()
    last_progress = start
    process: subprocess.Popen[str] | None = None
    exit_code: int | None = None
    status = "failed"
    error: str | None = None
    interruption_reason: str | None = None
    last_progress_age_s: float | None = None
    global _WORKER_PID
    try:
        with stdout_path.open("w", encoding="utf-8", buffering=1) as stdout, stderr_path.open("w", encoding="utf-8", buffering=1) as stderr:
            process = subprocess.Popen(
                [str(python_path), str(worker_script), "--manifest", str(result.manifest_path), "--expected-manifest-sha256", result.manifest_sha256, "--worker"],
                stdout=stdout,
                stderr=stderr,
                cwd=str(result.project_root),
                env=env,
                text=True,
            )
            _WORKER_PID = process.pid
            set_execution_context(phase="executor_monitor", current_function="invoke_evaluator", current_chunk=None)
            while process.poll() is None:
                time.sleep(1.0)
                now = time.monotonic()
                mtimes = [path.stat().st_mtime for path in output_root.rglob("*") if path.is_file() and path not in {stdout_path, stderr_path}]
                if any(mtime >= start for mtime in mtimes):
                    last_progress = now
                    _EXECUTION_CONTEXT["last_progress_at_utc"] = utc_now()
                    _EXECUTION_CONTEXT["last_progress_monotonic"] = now
                if now - last_progress > STALL_TIMEOUT_SECONDS:
                    error = f"stall timeout exceeded ({STALL_TIMEOUT_SECONDS}s without output progress)"
                    interruption_reason = "internal_stall_timeout"
                    last_progress_age_s = now - last_progress
                    process.terminate()
                    status = "interrupted"
                    break
                if now - start > TOTAL_TIMEOUT_SECONDS:
                    error = f"total timeout exceeded ({TOTAL_TIMEOUT_SECONDS}s)"
                    interruption_reason = "internal_total_timeout"
                    last_progress_age_s = now - last_progress
                    process.terminate()
                    status = "interrupted"
                    break
            if process.poll() is None:
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            exit_code = process.returncode
            if status != "interrupted":
                status = "completed" if exit_code == 0 else "failed"
                if exit_code != 0:
                    error = f"task-aware evaluator returned exit code {exit_code}"
    except KeyboardInterrupt:
        last_progress_age_s = time.monotonic() - last_progress
        if process is not None and process.poll() is None:
            process.terminate()
        status = "interrupted"
        interruption_reason = "external_keyboardinterrupt_or_signal"
        error = "KeyboardInterrupt; evaluator terminated and outputs preserved"
        exit_code = process.returncode if process is not None else None
    except Exception as exc:
        status = "failed"
        error = repr(exc)
    receipt_path = write_execution_receipt(
        output_root,
        result,
        status=status,
        start_utc=start_utc,
        end_utc=utc_now(),
        exit_code=exit_code,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        error=error,
        interruption_reason=interruption_reason,
        last_progress_age_s=last_progress_age_s,
    )
    print(f"EXECUTION_RECEIPT={receipt_path}")
    return 0 if status == "completed" and exit_code == 0 else 1


def execute(result: ValidationResult, confirm_phase_a: bool) -> int:
    if not result.execution_eligible:
        raise ExecutorRejected("execution preflight rejected: " + "; ".join(result.errors))
    if not confirm_phase_a:
        raise ExecutorRejected("execution is blocked unless --confirm-phase-a is supplied")
    if not result.execute_dispatch_available:
        raise ExecutorRejected(
            "execution is blocked because the current v2 evaluator does not expose the required task-aware API; no raw IQ was opened"
        )
    _, lock_path = acquire_global_lock(result.project_root, result.manifest["request_id"])
    try:
        return invoke_evaluator(result)
    finally:
        release_global_lock(lock_path)


def run_worker(args: argparse.Namespace) -> int:
    """Private worker path; parent owns the global lock and receipt."""
    result = validate_manifest(
        args.manifest,
        args.expected_manifest_sha256,
        allow_existing_names=frozenset({"executor_stdout.log", "executor_stderr.log"}),
    )
    if not result.execution_eligible:
        print("WORKER_REJECTED=" + "; ".join(result.errors), file=sys.stderr)
        return 2
    if not result.evaluator_api_available:
        print("WORKER_REJECTED=task-aware v2 function set unavailable", file=sys.stderr)
        return 2
    output_root = Path(result.manifest["output"]["namespace"]).resolve(strict=False)
    worker_stdout = output_root / "worker_stdout.log"
    worker_stderr = output_root / "worker_stderr.log"
    try:
        install_interrupt_handlers()
        exit_code = run_task_with_v2_adapter(result, output_root, worker_stdout, worker_stderr)
        print(f"WORKER_COMPLETED request_id={result.manifest['request_id']}")
        return exit_code
    except KeyboardInterrupt:
        print("WORKER_INTERRUPTED", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"WORKER_FAILED={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-phase-a", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        install_interrupt_handlers()
        if args.worker:
            return run_worker(args)
        result = validate_manifest(args.manifest, args.expected_manifest_sha256)
        if args.confirm_phase_a and not args.execute:
            raise ExecutorRejected("--confirm-phase-a is valid only together with --execute")
        if args.execute:
            return execute(result, args.confirm_phase_a)
        for line in dry_run_lines(result):
            print(line)
        return 0
    except ExecutorRejected as exc:
        print(f"EXECUTOR_REJECTED={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
