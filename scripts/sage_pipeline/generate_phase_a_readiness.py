#!/usr/bin/env python3
"""Prepare immutable raw-coarse Phase-A execution receipts.

This helper is intentionally preparation-only.  It reads metadata, inventory,
Stage0 catalogs, and file metadata, but never opens raw IQ and never reads
Stage1/Stage2/Stage3/Stage4 results.  It does not call the raw-coarse runner,
MATLAB, SAGE, or create an execution-output directory.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_PARAMETER_HASH = "41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2"
PYTHON_EXECUTABLE = r"D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe"
NAMESPACE_NAME = "batch_sampled_v1_2_phase_a_execution_requests_20260812"
OUTPUT_NAMESPACE_NAME = "batch_sampled_v1_2_phase_a_outputs_20260812"
ALIGNMENT_NAMESPACE = "dataset_generation_logs/sampling_validation/batch_sampled_v1_2_kernel_alignment_v2"
V2_SCRIPT = "scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2_v2.py"
PIPELINE_SCRIPT = "scripts/sage_pipeline/run_nav_sage_pipeline.m"
ALIGNMENT_REPORT = "docs/RAW_COARSE_NUMPY_KERNEL_ALIGNMENT_REPORT.md"

TASKS: tuple[dict[str, Any], ...] = (
    {
        "sequence": 1,
        "phase_id": "Phase-A1",
        "scene_id": "F1023_V70_D0120_P7",
        "prn": "G16",
        "tracking_channel": 1,
        "sample_rate_hz": 10_230_000,
    },
    {
        "sequence": 2,
        "phase_id": "Phase-A2",
        "scene_id": "F1023_v50_D0127_P1",
        "prn": "G25",
        "tracking_channel": 0,
        "sample_rate_hz": 10_230_000,
    },
)

PROFILES = (
    {"profile_id": "B1_20msx2_D100", "subblock_ms": 20, "doppler_offsets_hz": [-100, 0, 100]},
    {"profile_id": "B2_10msx4_D100", "subblock_ms": 10, "doppler_offsets_hz": [-100, 0, 100]},
    {"profile_id": "B2_10msx4_D200", "subblock_ms": 10, "doppler_offsets_hz": [-200, 0, 200]},
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_reference(scene_root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (scene_root / path).resolve()


def file_receipt(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": None, "exists": False, "size_bytes": None, "sha256": None}
    exists = path.is_file()
    stat = path.stat() if exists else None
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": stat.st_size if stat else None,
        "mtime_ns": stat.st_mtime_ns if stat else None,
        "sha256": sha256_file(path) if exists else None,
    }


def parse_int(value: Any) -> int | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else None


def load_inventory(project_root: Path) -> list[dict[str, str]]:
    with (project_root / "dataset" / "dataset_inventory.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def inventory_receipt(rows: list[dict[str, str]], task: dict[str, Any]) -> dict[str, Any]:
    matches = [row for row in rows if row.get("scene_id", "").casefold() == task["scene_id"].casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"inventory scene mapping is not unique: {task['scene_id']} ({len(matches)} rows)")
    row = matches[0]
    try:
        mapping = json.loads(row.get("prn_tracking_channel_map", "{}"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid prn_tracking_channel_map for {task['scene_id']}") from exc
    candidates = [parse_int(value) for value in mapping.get(task["prn"], [])]
    candidates = sorted({value for value in candidates if value is not None})
    expected = task["tracking_channel"]
    return {
        "scene_row_unique": True,
        "scene_id": row.get("scene_id"),
        "sampling_rate_hz": parse_int(row.get("sampling_rate_hz")),
        "raw_path": row.get("raw_path"),
        "raw_storage_mode": row.get("raw_storage_mode"),
        "gnss_sdr_status": row.get("gnss_sdr_status"),
        "tracking_exists": row.get("tracking_exists"),
        "telemetry_exists": row.get("telemetry_exists"),
        "observables_exists": row.get("observables_exists"),
        "rinex_nav_exists": row.get("rinex_nav_exists"),
        "trajectory_exists": row.get("trajectory_exists"),
        "satellite_geometry_status": row.get("satellite_geometry_status"),
        "sage_results_status": row.get("sage_results_status"),
        "prn_tracking_channel_candidates": candidates,
        "requested_tracking_channel": expected,
        "channel_mapping_unique": candidates == [expected],
        "raw_path_matches_metadata_checked_later": True,
    }


def stage0_receipt(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False, "row_count": 0, "sha256": None}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    window_ids = [parse_int(row.get("window_id")) for row in rows]
    valid_ids = [value for value in window_ids if value is not None]
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "row_count": len(rows),
        "window_id_count": len(valid_ids),
        "window_ids_unique": len(valid_ids) == len(set(valid_ids)),
        "window_id_min": min(valid_ids) if valid_ids else None,
        "window_id_max": max(valid_ids) if valid_ids else None,
    }


def environment_receipt(project_root: Path) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_executable_expected": PYTHON_EXECUTABLE,
        "python_executable_matches_expected": str(Path(sys.executable).resolve()).casefold() == str(Path(PYTHON_EXECUTABLE).resolve()).casefold(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "architecture": platform.architecture()[0],
        "machine": platform.machine(),
        "python_executable_sha256": None,
        "pyvenv_cfg_sha256": None,
        "numpy": {"available": False},
        "scipy": {"available": False},
    }
    python_path = Path(sys.executable).resolve()
    if python_path.is_file():
        receipt["python_executable_sha256"] = sha256_file(python_path)
    pyvenv = python_path.parent.parent / "pyvenv.cfg"
    if pyvenv.is_file():
        receipt["pyvenv_cfg_sha256"] = sha256_file(pyvenv)
    try:
        import numpy as np  # type: ignore

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            np.show_config()
        receipt["numpy"] = {
            "available": True,
            "version": np.__version__,
            "path": str(Path(np.__file__).resolve()),
            "show_config": output.getvalue(),
        }
    except Exception as exc:  # pragma: no cover - environment dependent
        receipt["numpy"] = {"available": False, "error": repr(exc)}
    try:
        import scipy  # type: ignore

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            scipy.show_config()
        receipt["scipy"] = {
            "available": True,
            "version": scipy.__version__,
            "path": str(Path(scipy.__file__).resolve()),
            "show_config": output.getvalue(),
        }
    except Exception as exc:  # pragma: no cover - environment dependent
        receipt["scipy"] = {"available": False, "error": repr(exc)}
    receipt["openblas_receipt"] = {
        "numpy_config_contains_openblas": "openblas" in receipt["numpy"].get("show_config", "").lower(),
        "scipy_config_contains_openblas": "openblas" in receipt["scipy"].get("show_config", "").lower(),
    }
    receipt["project_root"] = str(project_root.resolve())
    return receipt


def protected_paths(project_root: Path) -> dict[str, Any]:
    paths = [
        project_root / "scenes" / "F1023_V70_D0117_P2" / "sage_results" / "G06_nav_sage_v1",
        project_root / "scenes" / "F1023_V70_D0117_P2" / "sage_results" / "nav_sage_v2",
    ]
    return {
        "paths": [{"path": str(path), "exists": path.exists()} for path in paths],
        "reference_scene_legacy_g06_present": paths[0].is_dir(),
        "policy": "No Phase-A output path is inside scenes/*/sage_results; existing reference/full-SAGE paths are never targets.",
    }


def prepare_task(project_root: Path, task: dict[str, Any], inventory_rows: list[dict[str, str]], output_root: Path, v2_parameter_hash: str) -> dict[str, Any]:
    scene_root = project_root / "scenes" / task["scene_id"]
    metadata_path = scene_root / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig")) if metadata_path.is_file() else {}
    raw_value = metadata.get("raw_iq", {}).get("path")
    raw_path = resolve_reference(scene_root, raw_value)
    stage0_path = scene_root / "sage_results" / "nav_sage_v2" / task["prn"] / "stage0_valid_40ms_windows.csv"
    track_path = scene_root / "gnss_sdr" / "tracking" / f"{task['scene_id']}_track_ch_{task['tracking_channel']}.mat"
    telemetry_path = scene_root / "gnss_sdr" / "telemetry" / f"{task['scene_id']}_telemetry_ch_{task['tracking_channel']}.dat"
    navigation_path = scene_root / "navigation" / "rinex_nav" / "RINEXFILE.26N"
    trajectory_path = resolve_reference(scene_root, metadata.get("trajectory", {}).get("file"))
    geometry_outputs = [
        resolve_reference(scene_root, value)
        for value in metadata.get("satellite_geometry", {}).get("outputs", [])
    ]
    output_namespace = output_root / f"{task['phase_id']}_{task['scene_id']}_{task['prn']}_ch{task['tracking_channel']}"
    inventory = inventory_receipt(inventory_rows, task)
    stage0 = stage0_receipt(stage0_path)
    metadata_receipt = file_receipt(metadata_path)
    raw_receipt = file_receipt(raw_path)
    input_files = {
        "metadata": metadata_receipt,
        "raw_iq": raw_receipt,
        "stage0_valid_40ms_windows": stage0,
        "tracking_mat": file_receipt(track_path),
        "telemetry_dat": file_receipt(telemetry_path),
        "rinex_nav": file_receipt(navigation_path),
        "trajectory_nmea": file_receipt(trajectory_path),
        "satellite_geometry_csv": [file_receipt(value) for value in geometry_outputs],
    }
    input_hash_basis = {
        "hash_scope": "readiness-input-bundle; raw content is not hashed in preparation",
        "scene_id": task["scene_id"],
        "prn": task["prn"],
        "tracking_channel": task["tracking_channel"],
        "sample_rate_hz": task["sample_rate_hz"],
        "metadata_sha256": metadata_receipt["sha256"],
        "stage0_sha256": stage0["sha256"],
        "raw_path": raw_receipt["path"],
        "raw_size_bytes": raw_receipt["size_bytes"],
        "raw_mtime_ns": raw_receipt.get("mtime_ns"),
        "inventory_channel_candidates": inventory["prn_tracking_channel_candidates"],
    }
    input_hash = sha256_bytes(canonical_json(input_hash_basis).encode("utf-8"))
    checks = {
        "scene_metadata_exists": metadata_receipt["exists"],
        "metadata_scene_id_matches": metadata.get("scene_id") == task["scene_id"],
        "sample_rate_is_10_23mhz": metadata.get("signal", {}).get("sample_rate_hz") == task["sample_rate_hz"] == 10_230_000,
        "complex_iq_declared": metadata.get("signal", {}).get("complex_iq") is True,
        "raw_iq_exists_and_aligned": raw_receipt["exists"] and int(raw_receipt["size_bytes"] or 0) > 0 and int(raw_receipt["size_bytes"] or 0) % 4 == 0,
        "stage0_exists_nonempty": stage0["exists"] and stage0["row_count"] > 0 and stage0["window_ids_unique"],
        "tracking_mat_exists_nonempty": input_files["tracking_mat"]["exists"] and int(input_files["tracking_mat"]["size_bytes"] or 0) > 0,
        "telemetry_dat_exists_nonempty": input_files["telemetry_dat"]["exists"] and int(input_files["telemetry_dat"]["size_bytes"] or 0) > 0,
        "navigation_exists_nonempty": input_files["rinex_nav"]["exists"] and int(input_files["rinex_nav"]["size_bytes"] or 0) > 0,
        "trajectory_exists_nonempty": input_files["trajectory_nmea"]["exists"] and int(input_files["trajectory_nmea"]["size_bytes"] or 0) > 0,
        "geometry_csvs_exist_nonempty": bool(input_files["satellite_geometry_csv"]) and all(item["exists"] and int(item["size_bytes"] or 0) > 0 for item in input_files["satellite_geometry_csv"]),
        "inventory_scene_unique": inventory["scene_row_unique"],
        "inventory_channel_unique_and_matches": inventory["channel_mapping_unique"],
        "output_namespace_does_not_exist": not output_namespace.exists(),
        "output_namespace_is_not_under_sage_results": "\\sage_results\\" not in str(output_namespace).casefold() and "/sage_results/" not in str(output_namespace).casefold(),
    }
    checks["all_input_checks_pass"] = all(checks.values())
    return {
        "request_id": task["phase_id"].lower().replace("-", "_") + "_" + task["prn"].lower() + "_20260812",
        "manifest_type": "raw_coarse_phase_a_execution_manifest",
        "manifest_version": "phase-a-readiness-1",
        "immutable_after_creation": True,
        "generated_at_utc": utc_now(),
        "sequence": task["sequence"],
        "phase_id": task["phase_id"],
        "task": {key: task[key] for key in ("scene_id", "prn", "tracking_channel", "sample_rate_hz")},
        "status": "READY_FOR_HUMAN_REVIEW",
        "execution_policy": {
            "human_confirmation_required": True,
            "default_execute": False,
            "resume": False,
            "overwrite": False,
            "new_only": True,
            "fixed_order": ["Phase-A1/G16", "Phase-A2/G25"],
            "g11_allowed_before_phase_a_success": False,
        },
        "prototype": {
            "entrypoint": str((project_root / V2_SCRIPT).resolve()),
            "prototype_script_sha256": sha256_file(project_root / V2_SCRIPT),
            "planner_version": "batch-sampled-v1.2-b1-b2-c1-prototype-v2-aligned",
            "schema_version": "batch-sampled-v1.2-raw-coarse-schema-3",
            "kernel_version": "numpy-batched-complex128-v2-aligned",
            "parameter_sha256": v2_parameter_hash,
            "expected_parameter_sha256": EXPECTED_PARAMETER_HASH,
            "parameter_hash_matches_alignment": v2_parameter_hash == EXPECTED_PARAMETER_HASH,
            "profiles": PROFILES,
            "gold_labels_used_for_selection": False,
            "selection_inputs": ["metadata", "dataset_inventory", "Stage0 catalog", "raw IQ during later execution"],
            "selection_forbidden_inputs": ["Stage1", "Stage2", "Stage3", "Stage4", "gold event locations"],
        },
        "runtime": {
            "python_executable": str(Path(sys.executable).resolve()),
            "numpy_scipy_receipt_reference": "root readiness receipt environment_receipt.json",
        },
        "inputs": {
            "scene_root": str(scene_root.resolve()),
            "metadata": str(metadata_path.resolve()),
            "raw_iq": raw_receipt,
            "stage0_valid_40ms_windows": stage0,
            "tracking_mat": input_files["tracking_mat"],
            "telemetry_dat": input_files["telemetry_dat"],
            "rinex_nav": input_files["rinex_nav"],
            "trajectory_nmea": input_files["trajectory_nmea"],
            "satellite_geometry_csv": input_files["satellite_geometry_csv"],
            "input_hash_sha256": input_hash,
            "input_hash_basis": input_hash_basis,
            "raw_content_sha256": None,
            "raw_content_hash_note": "Not computed during preparation; raw path, size, alignment, and mtime are recorded. The future executor must re-check raw existence/stat before opening it.",
        },
        "inventory": inventory,
        "output": {
            "namespace": str(output_namespace.resolve()),
            "exists_before_execution": output_namespace.exists(),
            "must_be_absent_or_empty_before_execution": True,
            "namespace_kind": "sampling_validation_raw_coarse_phase_a_only",
            "not_sage_results": True,
        },
        "hashes": {
            "pipeline_script": str((project_root / PIPELINE_SCRIPT).resolve()),
            "pipeline_script_sha256": sha256_file(project_root / PIPELINE_SCRIPT),
            "prototype_script_sha256": sha256_file(project_root / V2_SCRIPT),
            "alignment_report_sha256": sha256_file(project_root / ALIGNMENT_REPORT),
            "alignment_parameter_file_sha256": sha256_file(project_root / ALIGNMENT_NAMESPACE / "coarse_parameter.json"),
            "alignment_parameter_hash_file_sha256": sha256_file(project_root / ALIGNMENT_NAMESPACE / "coarse_parameter.sha256"),
            "hash_receipt_semantics": "Each current file hash is frozen into this manifest; pipeline and prototype are separate artifacts and are not expected to have equal byte hashes.",
        },
        "protected_scope": protected_paths(project_root),
        "preflight_checks": checks,
        "runner_gate": {
            "formal_v2_runner_enabled": False,
            "current_code_behavior": "run_batch_sampling_raw_coarse_v1_2_v2.py writes prototype artifacts then refuses formal Phase-A with RuntimeError",
            "execution_allowed_by_this_manifest": False,
            "reason": "Human review is required and the current v2 formal runner is intentionally not enabled; do not invoke it until a separately reviewed executor implementation exists.",
        },
    }


def report_text(root: Path, receipt: dict[str, Any], manifests: list[dict[str, Any]]) -> str:
    lines = [
        "# RAW-Coarse Phase-A Execution Readiness",
        "",
        f"Generated: `{receipt['generated_at_utc']}`",
        "",
        "## Decision",
        "",
        "This document prepares, but does not authorize or execute, the raw-coarse Phase-A run. No raw IQ content was read; MATLAB, SAGE, Stage1, Stage2, Stage3, Stage4, and G11 were not run.",
        "",
        "Overall status: `READY_FOR_HUMAN_REVIEW`; execution remains blocked by the explicit human gate and by the current v2 runner's intentional formal-runner refusal.",
        "",
        "The only permitted order is:",
        "",
        "1. Phase-A1 — `F1023_V70_D0120_P7/G16/ch1/10.23MHz`",
        "2. After an independent G16 QA decision, Phase-A2 — `F1023_v50_D0127_P1/G25/ch0/10.23MHz`",
        "",
        "The manifests are immutable by SHA-256 receipt. A changed manifest, code hash, parameter hash, or input receipt invalidates the preparation.",
        "",
        "## Frozen implementation",
        "",
        f"- Parameter SHA-256: `{EXPECTED_PARAMETER_HASH}`",
        "- Kernel: `numpy-batched-complex128-v2-aligned`",
        "- Planner: `batch-sampled-v1.2-b1-b2-c1-prototype-v2-aligned`",
        "- Schema: `batch-sampled-v1.2-raw-coarse-schema-3`",
        "- Python: `D:\\Research\\ChannelModeling-Agent\\.venv\\Scripts\\python.exe`",
        "- NumPy/SciPy/OpenBLAS receipt: `environment_receipt.json` in the readiness namespace",
        "- Frozen profiles: B1 20ms×2 D100 `[-100,0,+100] Hz`; B2 10ms×4 D100 `[-100,0,+100] Hz`; B2 10ms×4 D200 `[-200,0,+200] Hz`.",
        "- `gold_labels_used_for_selection=false`.",
        "- No threshold, Doppler grid, normalization, or promotion rule was changed.",
        "",
        "## Task readiness",
        "",
        "| Order | Task | Channel | Stage0 rows | Raw bytes | Input checks | Output namespace before run | Status |",
        "|---:|---|---:|---:|---:|---|---|---|",
    ]
    for manifest in manifests:
        task = manifest["task"]
        inputs = manifest["inputs"]
        checks = manifest["preflight_checks"]
        lines.append(
            f"| {manifest['sequence']} | `{task['scene_id']}/{task['prn']}` | ch{task['tracking_channel']} | {inputs['stage0_valid_40ms_windows']['row_count']} | {inputs['raw_iq']['size_bytes']} | `{checks['all_input_checks_pass']}` | `{manifest['output']['exists_before_execution']}` | `{manifest['status']}` |"
        )
    lines += [
        "",
        "Both tasks are 10.23 MHz and have unique inventory channel mappings. Their metadata, raw paths, Stage0 catalogs, tracking MAT, telemetry DAT, RINEX NAV, trajectory NMEA, and both satellite geometry CSVs passed the preparation checks.",
        "",
        "## Input and hash gates",
        "",
        "The manifests record an `input_hash_sha256` built from scene/PRN/channel/sample-rate, metadata SHA-256, Stage0 SHA-256, raw absolute path, raw size, raw mtime, and inventory channel candidates. The full raw content SHA-256 is intentionally not computed during preparation because the raw files are multi-gigabyte; the future executor must repeat path/stat/alignment checks immediately before opening raw IQ.",
        "",
        "`pipeline_script_sha256` and `prototype_script_sha256` are frozen separately. They are not expected to be equal: consistency means the manifest receipt matches the exact current files, while the parameter hash matches the passed kernel-alignment receipt. The alignment report states `KERNEL_ALIGNMENT_PASS=true`, `NUMERIC_MICROBENCHMARK_PASS=true`, and `FORMAL_G16_G25_PHASE_A_EXECUTED=false`.",
        "",
        "The execution namespace is outside `scenes/*/sage_results`, so it cannot overwrite G06 legacy/reference/full SAGE outputs. Existing `F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1` and reference `nav_sage_v2` outputs were only existence-checked as protected paths; no contents were changed.",
        "",
        "## Immutable manifest locations",
        "",
        f"- Readiness namespace: `{root}`",
    ]
    for manifest in manifests:
        lines.append(f"- `{manifest['phase_id']}` manifest: `{manifest['_manifest_path']}`")
        lines.append(f"  - SHA-256: `{manifest['_manifest_sha256']}`")
    lines += [
        "- Environment receipt: `environment_receipt.json`",
        "- Root receipt: `phase_a_readiness_receipt.json`",
        "",
        "## Success gates after human execution",
        "",
        "### G16 scientific and engineering gates",
        "",
        "- All three frozen profiles must complete without raw read errors or partial status.",
        "- Confirmed-event center recall must be 100% for all four known G16 confirmed centers.",
        "- Each known center's ±2 closure recall must be 100%.",
        "- Stage3 reliable-center closure must be reported.",
        "- Promotion must not degenerate to all Stage0 windows.",
        "- Raw bytes, chunk reuse, wall-clock, CPU time, peak memory, windows/s, and bytes/s must be recorded. The total raw-coarse wall-clock must be materially below the historical G16 full Stage1 background (~3900 s), with the project candidate target at or below 50% of that background.",
        "",
        "### G25 control gates",
        "",
        "- The complete control run must finish with no raw read error or partial status.",
        "- Report score distributions, promotion fraction, component count, potential fine-window size, and cost.",
        "- Promotion is evidence only; it is not a multipath label, and not-promoted is not LOS.",
        "",
        "Only if G16 satisfies center/closure recall, non-all-window promotion, and cost gates, and G25 completes as a control, may the project evaluate whether G11 is eligible. This readiness package does not authorize G11.",
        "",
        "## Non-actions and safety rules",
        "",
        "- Do not edit `run_nav_sage_pipeline.m`, metadata, inventory, or any scene data.",
        "- Do not overwrite `G06_nav_sage_v1`, reference `nav_sage_v2`, Pilot/ Wave-A SAGE results, or old prototype namespaces.",
        "- Do not read Stage3/Stage4 or known event positions to choose parameters or promote windows. Gold is post-freeze evaluation only.",
        "- Do not tune threshold/Doppler grids, resume, truncate over budget, run G11, restore Wave-2A full-scan, or process 20.46 MHz.",
        "- Do not invoke the current v2 formal CLI as if it were enabled: it intentionally raises `RuntimeError(""NumPy backend formal runner is not enabled in this environment"")` after its preparation path. A separately reviewed task-aware executor is required before any actual raw read.",
        "",
        "## Recommended human action",
        "",
        "1. Have `TJ-CHANNEL\\Jing_` review the two manifest sidecars and compare all frozen hashes.",
        "2. Resolve the current formal-runner implementation gate through a separately reviewed, task-aware executor that consumes exactly one manifest at a time and preserves the new output namespace.",
        "3. Execute only Phase-A1 G16, perform independent QA, and stop if any gate fails.",
        "4. Only after G16 QA passes, execute Phase-A2 G25 with the same frozen parameter hash and then decide on G11 eligibility.",
        "",
        "## Current conclusion",
        "",
        "`FORMAL_PHASE_A_EXECUTED=false`. The preparation inputs are complete and the immutable manifests are generated, but `EXECUTION_ALLOWED=false` until human review and the current formal-runner gate are resolved. No G11 execution is allowed.",
        "",
    ]
    return "\n".join(lines)


def run(project_root: Path) -> int:
    project_root = project_root.resolve()
    namespace = project_root / "dataset_generation_logs" / "sampling_validation" / NAMESPACE_NAME
    output_root = project_root / "dataset_generation_logs" / "sampling_validation" / OUTPUT_NAMESPACE_NAME
    if namespace.exists():
        raise FileExistsError(f"refusing to reuse immutable manifest namespace: {namespace}")
    if output_root.exists():
        raise FileExistsError(f"refusing to reuse Phase-A output namespace: {output_root}")
    if str(Path(sys.executable).resolve()).casefold() != str(Path(PYTHON_EXECUTABLE).resolve()).casefold():
        raise RuntimeError(f"run this preparation with the frozen interpreter: {PYTHON_EXECUTABLE}")

    scripts_dir = project_root / "scripts" / "sage_pipeline"
    sys.path.insert(0, str(scripts_dir))
    import run_batch_sampling_raw_coarse_v1_2_v2 as v2  # type: ignore

    if v2.PARAMETER_HASH != EXPECTED_PARAMETER_HASH:
        raise RuntimeError(f"current v2 parameter hash mismatch: {v2.PARAMETER_HASH}")

    inventory_rows = load_inventory(project_root)
    environment = environment_receipt(project_root)
    root_receipt: dict[str, Any] = {
        "receipt_type": "raw_coarse_phase_a_execution_readiness",
        "receipt_version": "phase-a-readiness-1",
        "generated_at_utc": utc_now(),
        "project_root": str(project_root),
        "manifest_namespace": str(namespace),
        "reserved_output_namespace": str(output_root),
        "reserved_output_namespace_exists_before_preparation": False,
        "phase_a_order": ["Phase-A1/G16", "Phase-A2/G25"],
        "expected_parameter_sha256": EXPECTED_PARAMETER_HASH,
        "current_parameter_sha256": v2.PARAMETER_HASH,
        "kernel_alignment_pass": True,
        "numeric_microbenchmark_pass": True,
        "formal_phase_a_executed": False,
        "gold_labels_used_for_selection": False,
        "matlab_called": False,
        "sage_called": False,
        "g11_started": False,
        "environment_receipt": "environment_receipt.json",
        "old_namespaces_untouched": True,
    }
    manifests: list[dict[str, Any]] = []
    for task in TASKS:
        manifest = prepare_task(project_root, task, inventory_rows, output_root, v2.PARAMETER_HASH)
        if not manifest["preflight_checks"]["all_input_checks_pass"]:
            raise RuntimeError(f"preflight failed for {manifest['request_id']}")
        task_dir = namespace / manifest["request_id"]
        manifest_path = task_dir / "execution_manifest.json"
        manifest.pop("_manifest_path", None)
        manifest.pop("_manifest_sha256", None)
        write_json(manifest_path, manifest)
        manifest_hash = sha256_file(manifest_path)
        (task_dir / "execution_manifest.sha256").write_text(manifest_hash + "\n", encoding="ascii")
        manifest["_manifest_path"] = str(manifest_path)
        manifest["_manifest_sha256"] = manifest_hash
        manifests.append(manifest)
        root_receipt.setdefault("manifests", []).append({"request_id": manifest["request_id"], "path": str(manifest_path), "sha256": manifest_hash})
    write_json(namespace / "environment_receipt.json", environment)
    root_receipt["readiness_manifest_sha256"] = sha256_bytes(canonical_json(root_receipt).encode("utf-8"))
    write_json(namespace / "phase_a_readiness_receipt.json", root_receipt)
    report_path = project_root / "docs" / "RAW_COARSE_PHASE_A_EXECUTION_READINESS.md"
    report_path.write_text(report_text(namespace, root_receipt, manifests), encoding="utf-8")
    print(f"READINESS_NAMESPACE={namespace}")
    print(f"G16_MANIFEST={manifests[0]['_manifest_path']}")
    print(f"G16_SHA256={manifests[0]['_manifest_sha256']}")
    print(f"G25_MANIFEST={manifests[1]['_manifest_path']}")
    print(f"G25_SHA256={manifests[1]['_manifest_sha256']}")
    print(f"REPORT={report_path}")
    print("FORMAL_PHASE_A_EXECUTED=false")
    print("G11_STARTED=false")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    return run(args.project_root)


if __name__ == "__main__":
    raise SystemExit(main())
