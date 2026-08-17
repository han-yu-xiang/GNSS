"""Generate an immutable, preflighted raw-coarse v3 G16 task manifest.

This preparation tool deliberately does not open the raw IQ file.  It verifies
the current raw path, size, and mtime against the previously frozen raw hash
receipt, while the real capture executor remains responsible for re-hashing
the raw file immediately before opening it.  No posterior SAGE result is read
or used for task selection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import raw_coarse_v3_common as common


SCENE_ID = "F1023_V70_D0120_P7"
PRN = "G16"
TRACKING_CHANNEL = 1
SAMPLE_RATE_HZ = 10_230_000
EXPECTED_PARAMETER_SHA256 = "3f6330f8c88b4901feda2e0cb9bd9e8dcd6350aec6270fd0d3985f5ca2669642"
EXPECTED_V2_KERNEL_SHA256 = "959141371075c7f417f945dbe3f915f362a9337bb77582306f2b3ef16919ddfb"
EXPECTED_STAGE0_COUNT = 2229

DEFAULT_PARAMETER_MANIFEST = (
    "dataset_generation_logs/sampling_validation/"
    "batch_sampled_v1_3_parameter_manifest_r6_20260812/v3_parameter_schema_manifest.json"
)
DEFAULT_OLD_MANIFEST = (
    "dataset_generation_logs/sampling_validation/"
    "batch_sampled_v1_2_phase_a_retry_requests_20260812/"
    "phase_a1_g16_retry1_20260812/execution_manifest.json"
)
DEFAULT_ENVIRONMENT_RECEIPT = (
    "dataset_generation_logs/sampling_validation/"
    "batch_sampled_v1_2_phase_a_execution_requests_20260812/environment_receipt.json"
)
DEFAULT_REQUEST_DIR = (
    "dataset_generation_logs/sampling_validation/"
    "batch_sampled_v1_3_g16_evidence_task_requests_20260812_r1/"
    "g16_v3_evidence_capture_20260812_r1"
)
DEFAULT_OUTPUT_NAMESPACE = (
    "dataset_generation_logs/sampling_validation/"
    "batch_sampled_v1_3_g16_evidence_outputs_20260812_r1_"
    "F1023_V70_D0120_P7_G16_ch1"
)
DEFAULT_REQUEST_ID = "g16_v3_evidence_capture_20260812_r1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return common.sha256_file(path)


def resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def require_file(path: Path, label: str) -> dict[str, Any]:
    path = resolved(path)
    if not path.is_file():
        raise FileNotFoundError(f"{label} missing: {path}")
    stat = path.stat()
    if stat.st_size <= 0:
        raise ValueError(f"{label} is empty: {path}")
    return {
        "path": str(path),
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": sha256_file(path),
    }


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(resolved(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return value


def bool_text(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_inventory_row(path: Path, scene_id: str) -> tuple[dict[str, str], dict[str, Any]]:
    path = resolved(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    matches = [row for row in rows if row.get("scene_id", "") == scene_id]
    if len(matches) != 1:
        raise ValueError(f"inventory scene row is not unique: {scene_id} ({len(matches)})")
    row = matches[0]
    try:
        channel_map = json.loads(row.get("prn_tracking_channel_map", "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("inventory prn_tracking_channel_map is invalid JSON") from exc
    candidates = channel_map.get(PRN, [])
    if not isinstance(candidates, list) or [int(value) for value in candidates] != [TRACKING_CHANNEL]:
        raise ValueError(f"inventory channel mapping is not uniquely G16/ch1: {candidates}")
    sampling_rate = int(row.get("sampling_rate_hz", "0"))
    if sampling_rate != SAMPLE_RATE_HZ:
        raise ValueError(f"inventory sample rate mismatch: {sampling_rate}")
    return row, {
        "scene_row_unique": True,
        "scene_id": scene_id,
        "sampling_rate_hz": sampling_rate,
        "raw_path": row.get("raw_path", ""),
        "raw_storage_mode": row.get("raw_storage_mode", ""),
        "gnss_sdr_status": row.get("gnss_sdr_status", ""),
        "tracking_exists": bool_text(row.get("tracking_exists", "")),
        "telemetry_exists": bool_text(row.get("telemetry_exists", "")),
        "observables_exists": bool_text(row.get("observables_exists", "")),
        "rinex_nav_exists": bool_text(row.get("rinex_nav_exists", "")),
        "trajectory_exists": bool_text(row.get("trajectory_exists", "")),
        "satellite_geometry_status": row.get("satellite_geometry_status", ""),
        "sage_results_status": row.get("sage_results_status", ""),
        "prn_tracking_channel_candidates": [TRACKING_CHANNEL],
        "requested_tracking_channel": TRACKING_CHANNEL,
        "channel_mapping_unique": True,
    }


def stage0_receipt(path: Path) -> dict[str, Any]:
    path = resolved(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"window_id", "sample_start_zero_based", "nav_symbol_1", "nav_symbol_2"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Stage0 catalog is missing required fields: {path}")
    ids = []
    for row in rows:
        try:
            ids.append(int(row["window_id"]))
        except (TypeError, ValueError) as exc:
            raise ValueError("Stage0 contains an invalid window_id") from exc
    if len(rows) != EXPECTED_STAGE0_COUNT:
        raise ValueError(f"Stage0 count mismatch: expected {EXPECTED_STAGE0_COUNT}, got {len(rows)}")
    if sorted(ids) != list(range(1, EXPECTED_STAGE0_COUNT + 1)):
        raise ValueError("Stage0 window IDs are not the complete unique 1..2229 sequence")
    receipt = require_file(path, "Stage0 valid 40ms catalog")
    receipt.update({
        "row_count": len(rows),
        "window_id_count": len(set(ids)),
        "window_ids_unique": len(set(ids)) == len(ids),
        "window_id_min": min(ids),
        "window_id_max": max(ids),
        "required_fields_present": True,
    })
    return receipt


def path_from_metadata(scene_root: Path, value: str, label: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return resolved(candidate)
    return resolved(scene_root / candidate)


def audit_secondary_doppler_semantics(project_root: Path) -> dict[str, Any]:
    capture_path = resolved(project_root / "scripts/sage_pipeline/run_raw_coarse_v3_evidence_capture.py")
    common_path = resolved(project_root / "scripts/sage_pipeline/raw_coarse_v3_common.py")
    capture_text = capture_path.read_text(encoding="utf-8")
    common_text = common_path.read_text(encoding="utf-8")
    checks = {
        "secondary_uses_selected_delay_index": (
            'secondary_dopplers.append(float(block_profile["best_doppler_by_delay_hz"][second_index]))'
            in capture_text
        ),
        "secondary_not_main_delay_index": "[main_index]))" not in capture_text.split("secondary_dopplers.append", 1)[-1].split("secondary_doppler =", 1)[0],
        "secondary_not_tracking_aggregate": "secondary_doppler - float(row.tracking_doppler_hz)" in capture_text,
        "secondary_null_when_inadmissible": '"secondary_doppler_hz": secondary_doppler if secondary_valid else None' in capture_text,
        "b1_groups_exact": 'return ((0, 1), (2, 3)) if profile.family == "B1"' in capture_text,
        "b2_groups_exact": '((0,), (1,), (2,), (3,))' in capture_text,
        "nav_0_1_symbol_1": '"0": "nav_symbol_1", "1": "nav_symbol_1"' in common_text,
        "nav_2_3_symbol_2": '"2": "nav_symbol_2", "3": "nav_symbol_2"' in common_text,
        "cross_scale_mapping_frozen": "B1 group 0 -> B2 subblocks 0,1; B1 group 1 -> B2 subblocks 2,3" in common_text,
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"v3 code semantic audit failed: {failed}")
    return {
        "pass": True,
        "checks": checks,
        "interpretation": (
            "secondary_doppler_hz is the Doppler-grid-selected value at the chosen "
            "secondary delay index, averaged only across the primitive blocks in the "
            "same subblock group; it is not main-delay, tracking-only, or window-aggregate Doppler"
        ),
    }


def _old_raw_receipt(old_manifest: Mapping[str, Any]) -> dict[str, Any]:
    raw = old_manifest.get("inputs", {}).get("raw_iq", {})
    required = ("path", "size_bytes", "mtime_ns", "sha256")
    if any(not raw.get(field) for field in required):
        raise ValueError("old immutable manifest lacks the frozen raw path/stat/hash receipt")
    return {
        "path": str(raw["path"]),
        "size_bytes": int(raw["size_bytes"]),
        "mtime_ns": int(raw["mtime_ns"]),
        "sha256": str(raw["sha256"]).lower(),
    }


def build_preflight(
    project_root: Path,
    parameter_manifest_path: Path,
    old_manifest_path: Path,
    environment_receipt_path: Path,
    output_namespace: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = resolved(project_root)
    scene_root = root / "scenes" / SCENE_ID
    metadata_path = scene_root / "metadata.json"
    metadata = load_json(metadata_path, "scene metadata")
    if metadata.get("scene_id") != SCENE_ID:
        raise ValueError("metadata scene_id mismatch")
    if int(metadata.get("signal", {}).get("sample_rate_hz", 0)) != SAMPLE_RATE_HZ:
        raise ValueError("metadata sample rate is not 10.23MHz")
    if metadata.get("signal", {}).get("complex_iq") is not True:
        raise ValueError("metadata does not declare complex IQ")

    inventory_path = root / "dataset/dataset_inventory.csv"
    inventory_row, inventory_info = load_inventory_row(inventory_path, SCENE_ID)
    metadata_raw_path = path_from_metadata(scene_root, metadata["raw_iq"]["path"], "raw IQ")
    old_manifest = load_json(old_manifest_path, "old raw provenance manifest")
    frozen_raw = _old_raw_receipt(old_manifest)
    if resolved(frozen_raw["path"]) != metadata_raw_path:
        raise ValueError("frozen raw path differs from current metadata raw_iq.path")
    raw_stat = metadata_raw_path.stat()
    if int(raw_stat.st_size) != frozen_raw["size_bytes"] or int(raw_stat.st_mtime_ns) != frozen_raw["mtime_ns"]:
        raise ValueError("current raw stat differs from frozen raw provenance")
    raw_info = {
        **frozen_raw,
        "exists": True,
        "current_size_bytes": int(raw_stat.st_size),
        "current_mtime_ns": int(raw_stat.st_mtime_ns),
        "content_hash_source": str(resolved(old_manifest_path)),
        "content_hash_revalidated_this_preflight": False,
        "content_hash_revalidation_note": "full raw read deliberately deferred by execution-preparation guard",
    }

    stage0_path = scene_root / "sage_results/nav_sage_v2/G16/stage0_valid_40ms_windows.csv"
    stage0 = stage0_receipt(stage0_path)
    metadata_info = require_file(metadata_path, "scene metadata")
    inventory_info["inventory_path"] = str(resolved(inventory_path))
    inventory_info["inventory_sha256"] = sha256_file(inventory_path)
    if resolved(inventory_row.get("raw_path", "")) != metadata_raw_path:
        raise ValueError("inventory raw path differs from metadata raw_iq.path")

    tracking_path = scene_root / f"gnss_sdr/tracking/{SCENE_ID}_track_ch_{TRACKING_CHANNEL}.mat"
    telemetry_path = scene_root / f"gnss_sdr/telemetry/{SCENE_ID}_telemetry_ch_{TRACKING_CHANNEL}.dat"
    navigation_path = path_from_metadata(scene_root, metadata["navigation"]["files"]["rinex_nav"], "RINEX NAV")
    trajectory_path = path_from_metadata(scene_root, metadata["trajectory"]["file"], "trajectory")
    geometry_paths = [path_from_metadata(scene_root, value, "satellite geometry") for value in metadata["satellite_geometry"]["outputs"]]
    tracking = require_file(tracking_path, "tracking MAT")
    telemetry = require_file(telemetry_path, "telemetry DAT")
    navigation = require_file(navigation_path, "RINEX NAV")
    trajectory = require_file(trajectory_path, "trajectory NMEA")
    geometry = [require_file(path, "satellite geometry CSV") for path in geometry_paths]
    if metadata.get("gnss_sdr", {}).get("run_status") != "SUCCESS":
        raise ValueError("metadata GNSS-SDR status is not SUCCESS")
    if metadata.get("satellite_geometry", {}).get("status") != "completed":
        raise ValueError("metadata satellite geometry status is not completed")
    if metadata.get("navigation", {}).get("status") != "completed" or metadata.get("trajectory", {}).get("status") != "completed":
        raise ValueError("metadata navigation/trajectory status is not completed")

    parameter_manifest_path = resolved(parameter_manifest_path)
    parameter_manifest_sha = sha256_file(parameter_manifest_path)
    parameter_manifest = common.load_frozen_manifest(parameter_manifest_path, parameter_manifest_sha, root)
    if parameter_manifest.get("parameter_sha256") != EXPECTED_PARAMETER_SHA256:
        raise ValueError("v3 parameter SHA-256 does not match requested frozen value")
    v2_path = root / "scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2_v2.py"
    v2_sha = sha256_file(v2_path)
    if v2_sha.lower() != EXPECTED_V2_KERNEL_SHA256:
        raise ValueError("v2 kernel SHA-256 does not match requested frozen value")

    environment_receipt_path = resolved(environment_receipt_path)
    environment = load_json(environment_receipt_path, "compiled backend environment receipt")
    python_path = resolved(environment["python_executable"])
    if str(python_path).lower() != r"d:\research\channelmodeling-agent\.venv\scripts\python.exe".lower():
        raise ValueError("compiled Python executable differs from frozen expected path")
    python_info = require_file(python_path, "compiled Python executable")
    if environment.get("python_executable_sha256", "").lower() != python_info["sha256"].lower():
        raise ValueError("compiled Python executable hash differs from environment receipt")

    source_relatives = {
        "v2_kernel": "scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2_v2.py",
        "v3_common": "scripts/sage_pipeline/raw_coarse_v3_common.py",
        "v3_evidence_capture": "scripts/sage_pipeline/run_raw_coarse_v3_evidence_capture.py",
        "v3_feature_builder": "scripts/sage_pipeline/build_raw_coarse_v3_features.py",
        "v3_manifest_generator": "scripts/sage_pipeline/generate_raw_coarse_v3_g16_task_manifest.py",
        "pipeline_protected": "scripts/sage_pipeline/run_nav_sage_pipeline.m",
    }
    source_hashes = {name: sha256_file(root / relative) for name, relative in source_relatives.items()}
    semantics = audit_secondary_doppler_semantics(root)
    output_namespace = resolved(output_namespace)
    allowed_root = root / "dataset_generation_logs" / "sampling_validation"
    if output_namespace.exists():
        raise FileExistsError(f"new output namespace already exists: {output_namespace}")
    if not common.is_within(output_namespace, allowed_root) or not output_namespace.name.startswith("batch_sampled_v1_3_"):
        raise ValueError("new output namespace is outside the v1.3 sampling namespace")
    if "sage_results" in output_namespace.parts or common.is_within(output_namespace, root / "scenes"):
        raise ValueError("new output namespace points to scenes/sage_results")
    if "retry" in str(output_namespace).lower() or "v1_2" in str(output_namespace).lower():
        raise ValueError("new output namespace points to a protected retry/v1.2 namespace")

    old_manifest_sha = sha256_file(old_manifest_path)
    tracking_provenance = {
        "path": tracking["path"],
        "sha256": tracking["sha256"],
        "source": "GNSS-SDR tracking MAT; channel selected by unique inventory PRN map",
    }
    telemetry_provenance = {
        "path": telemetry["path"],
        "sha256": telemetry["sha256"],
        "source": "GNSS-SDR telemetry DAT; channel-aligned provenance",
    }
    navigation_provenance = {
        "path": navigation["path"],
        "sha256": navigation["sha256"],
        "source": metadata.get("navigation", {}).get("source"),
        "rinex_nav_usage": metadata.get("satellite_geometry", {}).get("algorithm", {}).get("rinex_nav_usage"),
    }
    manifest = {
        "manifest_type": "raw_coarse_v3_evidence_capture_task_manifest",
        "manifest_version": "v1.3-g16-preparation-1",
        "immutable_after_creation": True,
        "request_id": DEFAULT_REQUEST_ID,
        "generated_at_utc": utc_now(),
        "task": {
            "task_id": DEFAULT_REQUEST_ID,
            "scene_id": SCENE_ID,
            "prn": PRN,
            "tracking_channel": TRACKING_CHANNEL,
            "sample_rate_hz": SAMPLE_RATE_HZ,
        },
        "execution_policy": {
            "new_only": True,
            "resume_allowed": False,
            "overwrite": False,
            "allow_real_raw": "requires explicit --allow-real-raw outside this preparation run",
            "gold_labels_used_for_selection": False,
            "posterior_replay_during_capture": False,
            "matlab_called": False,
            "sage_pipeline_called": False,
        },
        "selection_freeze": {
            "gold_labels_used_for_selection": False,
            "selection_sources": ["metadata.json", "dataset_inventory.csv", "Stage0 valid 40ms catalog", "raw stat/provenance"],
            "gold_location_selection": False,
            "frozen_before_any_posterior_replay": True,
        },
        "project": {
            "project_root": str(root),
            "scene_root": str(scene_root.resolve()),
            "inventory_path": str(inventory_path.resolve()),
            "inventory_sha256": inventory_info["inventory_sha256"],
        },
        "metadata": {
            "path": metadata_info["path"],
            "sha256": metadata_info["sha256"],
            "scene_id": metadata["scene_id"],
            "scene_role": "standard_scene",
            "gnss_sdr_status": metadata["gnss_sdr"]["run_status"],
            "navigation_status": metadata["navigation"]["status"],
            "trajectory_status": metadata["trajectory"]["status"],
            "satellite_geometry_status": metadata["satellite_geometry"]["status"],
            "raw_storage_mode": metadata["raw_iq"].get("storage_mode"),
        },
        "inputs": {
            "metadata_path": metadata_info["path"],
            "metadata_sha256": metadata_info["sha256"],
            "raw_path": raw_info["path"],
            "raw_sha256": raw_info["sha256"],
            "stage0_path": stage0["path"],
            "stage0_sha256": stage0["sha256"],
            "raw_iq": raw_info,
            "stage0_valid_40ms_windows": stage0,
            "tracking_mat": tracking,
            "telemetry_dat": telemetry,
            "rinex_nav": navigation,
            "trajectory_nmea": trajectory,
            "satellite_geometry_csv": geometry,
            "input_hash_revalidation_policy": "all non-raw hashes checked now; raw content hash rechecked by capture executor before opening",
        },
        "provenance": {
            "tracking": tracking_provenance,
            "telemetry": telemetry_provenance,
            "navigation": navigation_provenance,
            "trajectory": {"path": trajectory["path"], "sha256": trajectory["sha256"], "source": metadata.get("trajectory", {}).get("source")},
            "satellite_geometry": {"paths": [item["path"] for item in geometry], "sha256": [item["sha256"] for item in geometry], "source": metadata.get("satellite_geometry", {}).get("algorithm")},
            "inventory_channel_candidates": [TRACKING_CHANNEL],
            "channel_mapping_unique": True,
        },
        "v3_parameter_manifest": {
            "path": str(parameter_manifest_path),
            "sha256": parameter_manifest_sha,
            "parameter_sha256": EXPECTED_PARAMETER_SHA256,
            "version": parameter_manifest.get("version"),
        },
        "parameter_sha256": EXPECTED_PARAMETER_SHA256,
        "v2_kernel": {
            "path": str(v2_path.resolve()),
            "sha256": v2_sha,
            "version": parameter_manifest.get("v2_kernel", {}).get("version"),
            "parameter_sha256": parameter_manifest.get("v2_kernel", {}).get("parameter_sha256"),
        },
        "source_hashes": source_hashes,
        "runtime": {
            "python_executable": str(python_path),
            "python_executable_sha256": python_info["sha256"],
            "environment_receipt_path": str(environment_receipt_path),
            "environment_receipt_sha256": sha256_file(environment_receipt_path),
            "python_version": environment.get("python_version"),
            "numpy_version": environment.get("numpy", {}).get("version"),
            "scipy_version": environment.get("scipy", {}).get("version"),
            "numpy_openblas": environment.get("openblas_receipt", {}).get("numpy_config_contains_openblas"),
            "scipy_openblas": environment.get("openblas_receipt", {}).get("scipy_config_contains_openblas"),
        },
        "output": {
            "namespace": str(output_namespace),
            "exists_before_execution": False,
            "new_only": True,
            "namespace_kind": "sampling_validation_raw_coarse_v3_evidence_only",
            "not_sage_results": True,
            "forbidden_targets": ["scenes/**/sage_results", "Retry1 artifact", "batch_sampled_v1_2_*"],
        },
        "protected_provenance": {
            "old_raw_hash_manifest": str(resolved(old_manifest_path)),
            "old_raw_hash_manifest_sha256": old_manifest_sha,
            "old_manifest_untouched": True,
            "old_retry_output_untouched": True,
            "reference_sage_results_untouched": True,
        },
        "code_semantics_audit": semantics,
        "preflight": {
            "sample_rate_10230000": True,
            "target_channel_unique_and_is_1": True,
            "stage0_complete_2229": True,
            "all_inputs_exist_and_nonempty": True,
            "raw_stat_matches_frozen_provenance": True,
            "raw_content_hash_revalidated_this_preflight": False,
            "raw_content_hash_revalidation_deferred_by_no_full_raw_guard": True,
            "output_namespace_absent": True,
            "output_namespace_is_v1_3_and_not_sage_results": True,
            "old_v1_2_and_retry_namespaces_not_targeted": True,
            "gold_labels_used_for_selection": False,
            "manifest_source_hashes_frozen": True,
            "all_preparation_gates_pass_except_deferred_raw_content_rehash": True,
        },
        "replay_after_freeze": False,
        "gold_labels_used_for_selection": False,
    }
    audit = {
        "project_root": str(root),
        "request_id": manifest["request_id"],
        "task": manifest["task"],
        "parameter_sha256": EXPECTED_PARAMETER_SHA256,
        "v2_kernel_sha256": v2_sha,
        "metadata": metadata_info,
        "raw": raw_info,
        "stage0": stage0,
        "inventory": inventory_info,
        "tracking": tracking,
        "telemetry": telemetry,
        "navigation": navigation,
        "trajectory": trajectory,
        "geometry": geometry,
        "runtime": manifest["runtime"],
        "output": manifest["output"],
        "code_semantics_audit": semantics,
        "gold_labels_used_for_selection": False,
        "stage_result_replay": "not read; no posterior gold source is part of this preparation",
        "raw_content_hash_note": "frozen SHA is recorded and current size/mtime match; content rehash is deferred because the user prohibited reading the full raw file",
    }
    return manifest, audit


def write_report(path: Path, manifest: Mapping[str, Any], audit: Mapping[str, Any], manifest_sha256: str) -> None:
    lines = [
        "# Raw-Coarse v3 G16 Evidence-Capture Preflight",
        "",
        "- Status: `READY_FOR_HUMAN_REVIEW_ONLY`",
        "- Task: `F1023_V70_D0120_P7 / G16 / ch1 / 10.23 MHz`",
        f"- Task manifest SHA-256: `{manifest_sha256}`",
        f"- Parameter SHA-256: `{manifest['parameter_sha256']}`",
        f"- v2 kernel SHA-256: `{manifest['v2_kernel']['sha256']}`",
        "- `gold_labels_used_for_selection=false`",
        "- This preparation did not execute evidence capture and did not read the full raw IQ file.",
        "",
        "## Gates",
        "",
        "- Metadata sample rate is 10230000 Hz.",
        "- Inventory maps G16 uniquely to tracking channel 1.",
        "- Stage0 catalog has 2229 unique windows with IDs 1..2229.",
        "- Tracking, telemetry, RINEX NAV, trajectory and both geometry CSVs exist and were hashed.",
        "- The new output namespace is absent and is under `dataset_generation_logs/sampling_validation/batch_sampled_v1_3_*`.",
        "- No path targets `scenes/**/sage_results`, Retry1, or v1.2 namespaces.",
        "",
        "## Raw hash limitation",
        "",
        "The raw file is currently present at the metadata-resolved path with size and mtime matching the frozen Retry1 provenance. Its frozen SHA-256 is recorded in the manifest. A content rehash was deliberately not performed in this preparation because the request forbids reading the full 3.5 GB raw file. The real capture executor must re-check the content hash immediately before opening raw data; a mismatch must reject execution.",
        "",
        "## Code audit",
        "",
        "- `secondary_doppler_hz` is obtained from `best_doppler_by_delay_hz[secondary_peak_index]` for the selected secondary delay, per primitive block, then averaged only across the blocks belonging to that subblock. It is not main-delay Doppler, tracking Doppler alone, or a window aggregate Doppler.",
        "- B1 groups primitive blocks `(0,1)` and `(2,3)`; B2 uses `(0)`, `(1)`, `(2)`, `(3)`.",
        "- Blocks 0/1 use `nav_symbol_1`; blocks 2/3 use `nav_symbol_2`.",
        "- Cross-scale mapping is fixed by the parameter manifest: B1 group 0 -> B2 blocks 0/1 and B1 group 1 -> B2 blocks 2/3.",
        "",
        "## Frozen runtime and namespace",
        "",
        f"- Python: `{manifest['runtime']['python_executable']}`",
        f"- NumPy: `{manifest['runtime']['numpy_version']}`; SciPy: `{manifest['runtime']['scipy_version']}`; OpenBLAS receipt: NumPy={manifest['runtime']['numpy_openblas']}, SciPy={manifest['runtime']['scipy_openblas']}",
        f"- Output namespace: `{manifest['output']['namespace']}`",
        "- The only next action permitted is human review followed by the exact command below; do not execute it during this preparation.",
        "",
        "## Next command (not executed)",
        "",
        "```powershell",
        f"& '{manifest['runtime']['python_executable']}' `",
        f"  '{Path(manifest['project']['project_root']) / 'scripts/sage_pipeline/run_raw_coarse_v3_evidence_capture.py'}' `",
        f"  --project-root '{manifest['project']['project_root']}' `",
        f"  --task-manifest '{Path(manifest['manifest_path']) if manifest.get('manifest_path') else '<manifest-path>'}' `",
        f"  --expected-manifest-sha256 {manifest_sha256} `",
        "  --allow-real-raw",
        "```",
    ]
    path.write_text("\n".join(lines).replace("\n        ", "\n"), encoding="utf-8")


def generate(project_root: Path, request_dir: Path, output_namespace: Path, parameter_manifest: Path, old_manifest: Path, environment_receipt: Path) -> tuple[Path, str, Path]:
    project_root = resolved(project_root)
    request_dir = resolved(request_dir)
    if request_dir.exists():
        raise FileExistsError(f"immutable request namespace already exists: {request_dir}")
    manifest, audit = build_preflight(project_root, parameter_manifest, old_manifest, environment_receipt, output_namespace)
    request_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = request_dir / "execution_manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    data = (json.dumps(manifest, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    manifest_path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (request_dir / "execution_manifest.sha256").write_text(digest + "\n", encoding="ascii")
    audit["manifest_path"] = str(manifest_path)
    audit["manifest_sha256"] = digest
    (request_dir / "preflight_report.json").write_text(json.dumps(audit, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    report_path = request_dir / "preflight_report.md"
    # Re-render with the now-known manifest path.
    report_manifest = dict(manifest)
    write_report(report_path, report_manifest, audit, digest)
    return manifest_path, digest, report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a new-only G16 raw-coarse v3 task manifest without raw reads")
    parser.add_argument("--project-root", type=Path, default=common.PROJECT_ROOT)
    parser.add_argument("--request-dir", type=Path, default=None)
    parser.add_argument("--output-namespace", type=Path, default=None)
    parser.add_argument("--parameter-manifest", type=Path, default=None)
    parser.add_argument("--old-manifest", type=Path, default=None)
    parser.add_argument("--environment-receipt", type=Path, default=None)
    args = parser.parse_args()
    root = resolved(args.project_root)
    request_dir = args.request_dir or root / DEFAULT_REQUEST_DIR
    output_namespace = args.output_namespace or root / DEFAULT_OUTPUT_NAMESPACE
    parameter_manifest = args.parameter_manifest or root / DEFAULT_PARAMETER_MANIFEST
    old_manifest = args.old_manifest or root / DEFAULT_OLD_MANIFEST
    environment_receipt = args.environment_receipt or root / DEFAULT_ENVIRONMENT_RECEIPT
    manifest_path, digest, report_path = generate(root, request_dir, output_namespace, parameter_manifest, old_manifest, environment_receipt)
    print(f"G16_V3_TASK_MANIFEST={manifest_path}")
    print(f"G16_V3_TASK_MANIFEST_SHA256={digest}")
    print(f"G16_V3_PREFLIGHT_REPORT={report_path}")
    print("RAW_FULL_READ=false")
    print("EVIDENCE_CAPTURE_EXECUTED=false")
    print("GOLD_LABELS_USED_FOR_SELECTION=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
