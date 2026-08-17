#!/usr/bin/env python3
"""Create a fresh, immutable G16 Phase-A retry manifest.

This preparation-only helper never opens raw IQ and never calls the coarse
evaluator.  It preserves the interrupted first-run namespace as evidence and
creates a distinct manifest/output namespace for a fresh run only.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OLD_REQUEST_ID = "phase_a1_g16_20260812"
NEW_REQUEST_ID = "phase_a1_g16_retry1_20260812"
NEW_PHASE_ID = "Phase-A1-Retry1"
MANIFEST_NAMESPACE = "batch_sampled_v1_2_phase_a_retry_requests_20260812"
OUTPUT_NAMESPACE = "batch_sampled_v1_2_phase_a_retry_outputs_20260812"
EXPECTED_PARAMETER_HASH = "41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2"
EXPECTED_KERNEL_VERSION = "numpy-batched-complex128-v2-aligned"
V2_RELATIVE = Path("scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2_v2.py")
PIPELINE_RELATIVE = Path("scripts/sage_pipeline/run_nav_sage_pipeline.m")
EXECUTOR_RELATIVE = Path("scripts/sage_pipeline/run_raw_coarse_phase_a.py")
ALIGNMENT_REPORT_RELATIVE = Path("docs/RAW_COARSE_NUMPY_KERNEL_ALIGNMENT_REPORT.md")
ALIGNMENT_DIR_RELATIVE = Path("dataset_generation_logs/sampling_validation/batch_sampled_v1_2_kernel_alignment_v2")
LOCK_RELATIVE = Path("dataset_generation_logs/sampling_validation/batch_sampled_v1_2_phase_a_execution.lock")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not an object: {path}")
    return value


def load_v2_identity(project_root: Path) -> tuple[str, str]:
    scripts_dir = project_root / "scripts" / "sage_pipeline"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    module = importlib.import_module("run_batch_sampling_raw_coarse_v1_2_v2")
    return str(module.PARAMETER_HASH), str(module.KERNEL_VERSION)


def require_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"required file is missing: {path}")


def prepare(project_root: Path) -> tuple[Path, str, Path]:
    project_root = project_root.resolve()
    old_manifest = project_root / "dataset_generation_logs" / "sampling_validation" / "batch_sampled_v1_2_phase_a_execution_requests_20260812" / "phase_a1_g16_20260812" / "execution_manifest.json"
    old_output = project_root / "dataset_generation_logs" / "sampling_validation" / "batch_sampled_v1_2_phase_a_outputs_20260812" / "Phase-A1_F1023_V70_D0120_P7_G16_ch1"
    old_receipt = old_output / "execution_receipt.json"
    new_namespace = project_root / "dataset_generation_logs" / "sampling_validation" / MANIFEST_NAMESPACE
    new_task_dir = new_namespace / NEW_REQUEST_ID
    new_output_root = project_root / "dataset_generation_logs" / "sampling_validation" / OUTPUT_NAMESPACE
    new_output = new_output_root / "Phase-A1-Retry1_F1023_V70_D0120_P7_G16_ch1"
    lock_path = project_root / LOCK_RELATIVE

    for path in (old_manifest, old_receipt, project_root / V2_RELATIVE, project_root / PIPELINE_RELATIVE, project_root / EXECUTOR_RELATIVE, project_root / ALIGNMENT_REPORT_RELATIVE):
        require_file(path)
    if not old_output.is_dir():
        raise RuntimeError(f"interrupted output directory is missing: {old_output}")
    old = load_json(old_manifest)
    receipt = load_json(old_receipt)
    if old.get("request_id") != OLD_REQUEST_ID:
        raise RuntimeError("the superseded manifest is not the expected original G16 request")
    if receipt.get("request_id") != OLD_REQUEST_ID or receipt.get("status") != "interrupted":
        raise RuntimeError("the superseded receipt is not an interrupted G16 receipt")
    if new_namespace.exists() or new_output_root.exists() or new_output.exists():
        raise RuntimeError("retry manifest/output namespace already exists; refusing reuse")
    if lock_path.exists():
        raise RuntimeError(f"Phase-A global lock exists: {lock_path}")

    v2_path = project_root / V2_RELATIVE
    current_hashes = {
        "pipeline_script_sha256": sha256_file(project_root / PIPELINE_RELATIVE),
        "prototype_script_sha256": sha256_file(v2_path),
        "executor_script_sha256": sha256_file(project_root / EXECUTOR_RELATIVE),
        "alignment_report_sha256": sha256_file(project_root / ALIGNMENT_REPORT_RELATIVE),
        "alignment_parameter_file_sha256": sha256_file(project_root / ALIGNMENT_DIR_RELATIVE / "coarse_parameter.json"),
        "alignment_parameter_hash_file_sha256": sha256_file(project_root / ALIGNMENT_DIR_RELATIVE / "coarse_parameter.sha256"),
    }
    current_parameter_hash, current_kernel_version = load_v2_identity(project_root)
    if current_parameter_hash != EXPECTED_PARAMETER_HASH:
        raise RuntimeError("current v2 parameter hash is not the frozen value")
    if current_kernel_version != EXPECTED_KERNEL_VERSION:
        raise RuntimeError("current v2 kernel version is not the frozen value")
    for key in ("pipeline_script_sha256", "prototype_script_sha256", "alignment_report_sha256", "alignment_parameter_file_sha256", "alignment_parameter_hash_file_sha256"):
        if str(old.get("hashes", {}).get(key, "")).casefold() != current_hashes[key].casefold():
            raise RuntimeError(f"superseded manifest source hash changed: {key}")
    if (project_root / ALIGNMENT_DIR_RELATIVE / "coarse_parameter.sha256").read_text(encoding="ascii").strip() != EXPECTED_PARAMETER_HASH:
        raise RuntimeError("alignment parameter hash file changed")

    manifest = copy.deepcopy(old)
    manifest.update(
        {
            "request_id": NEW_REQUEST_ID,
            "phase_id": NEW_PHASE_ID,
            "generated_at_utc": utc_now(),
            "status": "READY_FOR_HUMAN_REVIEW_RETRY",
            "fresh_run_only": True,
            "resume_allowed": False,
            "supersedes_interrupted_manifest": OLD_REQUEST_ID,
            "previous_interruption_receipt": str(old_receipt),
            "previous_interruption_receipt_sha256": sha256_file(old_receipt),
        }
    )
    manifest["sequence"] = 1
    policy = manifest.setdefault("execution_policy", {})
    policy.update({"new_only": True, "resume": False, "overwrite": False, "default_execute": False, "automatic_next_task": False})
    manifest["output"].update(
        {
            "namespace": str(new_output),
            "exists_before_execution": False,
            "must_be_absent_or_empty_before_execution": True,
            "namespace_kind": "sampling_validation_raw_coarse_phase_a_retry_only",
        }
    )
    manifest["hashes"].update(current_hashes)
    checks = manifest.setdefault("preflight_checks", {})
    checks.update(
        {
            "all_input_checks_pass": True,
            "fresh_output_namespace_absent": True,
            "global_lock_absent": True,
            "previous_interruption_preserved": True,
            "old_manifest_untouched": True,
            "old_output_untouched": True,
            "fresh_run_only": True,
            "resume_allowed": False,
        }
    )
    manifest["retry_provenance"] = {
        "retry_reason": "supersede_interrupted_run_without_resume",
        "superseded_manifest_id": OLD_REQUEST_ID,
        "superseded_manifest_path": str(old_manifest),
        "superseded_manifest_sha256": sha256_file(old_manifest),
        "previous_interruption_receipt": str(old_receipt),
        "previous_interruption_receipt_sha256": sha256_file(old_receipt),
        "selection_and_science_parameters_unchanged": True,
    }

    new_task_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = new_task_dir / "execution_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    manifest_sha = sha256_file(manifest_path)
    (new_task_dir / "execution_manifest.sha256").write_text(manifest_sha + "\n", encoding="ascii")
    generation_receipt = {
        "receipt_type": "raw_coarse_phase_a_retry_manifest_generation",
        "generated_at_utc": manifest["generated_at_utc"],
        "request_id": NEW_REQUEST_ID,
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "supersedes_interrupted_manifest": OLD_REQUEST_ID,
        "previous_interruption_receipt": str(old_receipt),
        "fresh_run_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "coarse_evaluator_called": False,
        "matlab_called": False,
        "sage_called": False,
    }
    (new_task_dir / "retry_manifest_generation_receipt.json").write_text(json.dumps(generation_receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return manifest_path, manifest_sha, new_output


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    manifest_path, manifest_sha, output = prepare(project_root)
    print(f"RETRY_MANIFEST={manifest_path}")
    print(f"RETRY_MANIFEST_SHA256={manifest_sha}")
    print(f"RETRY_OUTPUT_NAMESPACE={output}")
    print("FRESH_RUN_ONLY=true")
    print("RESUME_ALLOWED=false")
    print(f"SUPERSEDES_INTERRUPTED_MANIFEST={OLD_REQUEST_ID}")
    print("RAW_IQ_READ=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
