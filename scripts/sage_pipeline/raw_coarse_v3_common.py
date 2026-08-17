"""Shared, immutable configuration and safety helpers for raw-coarse v3.

This module deliberately contains no Stage1--Stage4 reader and no raw-IQ
reader.  It describes the evidence schema and the rules that are frozen before
any posterior gold replay.  The v2 NumPy implementation remains the numerical
authority; this module only records its source hash and semantic contract.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
V3_VERSION = "raw-coarse-v3.0-evidence-feature-foundation"
EVIDENCE_SCHEMA_VERSION = "raw-coarse-v3-subblock-evidence-1"
FEATURE_SCHEMA_VERSION = "raw-coarse-v3-window-features-1"
V2_KERNEL_VERSION = "numpy-batched-complex128-v2-aligned"
V2_PARAMETER_SHA256 = "41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2"
V2_SOURCE_RELATIVE = "scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2_v2.py"
STRICT_TOLERANCES = {
    "score_db": 1.0e-8,
    "peak_ratio_db": 1.0e-8,
    "delay_samples": 0,
    "doppler_hz": 1.0e-8,
}

# The proposal is intentionally conservative and is not fitted to any gold
# event.  It is a candidate evidence-state rule, not a production decision.
# It is kept here so a future selector cannot silently hard-code thresholds.
V3_PARAMETER_SPEC: dict[str, Any] = {
    "version": V3_VERSION,
    "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
    "feature_schema_version": FEATURE_SCHEMA_VERSION,
    "gold_labels_used_for_selection": False,
    "gold_replay_allowed_only_after_freeze": True,
    "sample_format": "little-endian interleaved int16 I,Q",
    "sample_rate_scope_hz": [10230000],
    "v2_semantics": {
        "delay_phase_offsets_samples": [-2, -1, 0, 1, 2],
        "primitive_block_ms": 10,
        "b1_groups": [[0, 1], [2, 3]],
        "b2_groups": [[0], [1], [2], [3]],
        "nav_symbol_mapping": {"0": "nav_symbol_1", "1": "nav_symbol_1", "2": "nav_symbol_2", "3": "nav_symbol_2"},
        "doppler_offsets_hz": {"D100": [-100, 0, 100], "D200": [-200, 0, 200]},
        "doppler_signs": [1, -1],
        "phase_formula": "exp(-2j*pi*(sign*tracking_doppler_hz+offset_hz)*sample_position/sample_rate_hz)",
        "correlation_dtype": "complex128",
        "frequency_tie_break": "first frequency in frozen grid on equal magnitude",
        "delay_tie_break": "first delay in [-2,-1,0,1,2] on equal power",
    },
    "secondary_admissibility": {
        "minimum_delay_separation_samples": 2,
        "requires_finite_main_and_secondary": True,
        "no_admissible_value_semantics": "null + none_admissible_delay",
        "missing_value_semantics": "null + missing_or_inconclusive_reason",
    },
    "feature_list": {
        "multi_subblock_consensus": [
            "secondary_present_count",
            "secondary_present_fraction",
            "secondary_ratio_median",
            "secondary_ratio_mad",
            "secondary_ratio_iqr",
            "secondary_ratio_min",
            "secondary_ratio_max",
        ],
        "secondary_delay_consistency": [
            "secondary_delay_median_samples",
            "secondary_delay_mad_samples",
            "secondary_delay_range_samples",
            "secondary_delay_valid_fraction",
        ],
        "secondary_doppler_consistency": [
            "secondary_doppler_median_hz",
            "secondary_doppler_mad_hz",
            "secondary_doppler_range_hz",
            "secondary_doppler_valid_fraction",
        ],
        "cross_scale_agreement": [
            "cross_scale_match_count",
            "cross_scale_comparable_count",
            "cross_scale_agreement_fraction",
            "cross_scale_delay_disagreement_samples",
            "cross_scale_doppler_disagreement_hz",
        ],
        "reserved_not_in_v3_selector": [
            "adjacent_window_track_persistence",
            "local_novelty",
            "robust_z",
        ],
    },
    "cross_scale_tolerance": {
        "delay_samples": 1,
        "doppler_hz": 50.0,
        "mapping": "B1 group 0 -> B2 subblocks 0,1; B1 group 1 -> B2 subblocks 2,3",
    },
    "candidate_evidence_state": {
        "secondary_presence_min_count": 2,
        "secondary_presence_min_fraction": 0.5,
        "delay_mad_max_samples": 1.5,
        "doppler_mad_max_hz": 50.0,
        "cross_scale_min_agreement_fraction": 0.5,
        "minimum_comparable_cross_scale_pairs": 2,
        "meaning": "coarse promotion evidence only; never a multipath label",
    },
    "temporal_component_rule": {
        "uses_adjacent_window_evidence_in_selector": False,
        "bridge_gap_windows": 2,
        "boundary_expansion_windows": 2,
        "closure_radius_windows": 2,
        "component_rule": "group already-promoted evidence windows by window_id with fixed bridge; no gold-forced blocks",
    },
    "provenance": {
        "raw_read_mode": "read_only_contiguous_chunks",
        "no_sage": True,
        "no_stage2_stage3_stage4_selection": True,
        "null_is_not_zero": True,
        "production_manifest_gold_labels_used_for_selection": False,
    },
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parameter_sha256(spec: Mapping[str, Any] | None = None) -> str:
    return sha256_bytes(canonical_json(spec or V3_PARAMETER_SPEC).encode("utf-8"))


def expected_source_hashes(project_root: Path = PROJECT_ROOT) -> dict[str, str]:
    root = Path(project_root).resolve()
    result = {
        V2_SOURCE_RELATIVE: sha256_file(root / V2_SOURCE_RELATIVE),
    }
    for relative in (
        "scripts/sage_pipeline/raw_coarse_v3_common.py",
        "scripts/sage_pipeline/run_raw_coarse_v3_evidence_capture.py",
        "scripts/sage_pipeline/build_raw_coarse_v3_features.py",
        "scripts/sage_pipeline/audit_raw_coarse_retry1_evidence_v3.py",
    ):
        path = root / relative
        if path.is_file():
            result[relative] = sha256_file(path)
    return result


def build_manifest(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    root = Path(project_root).resolve()
    sources = expected_source_hashes(root)
    return {
        "manifest_type": "raw_coarse_v3_parameter_schema_manifest",
        "manifest_version": "1",
        "version": V3_VERSION,
        "parameter_sha256": parameter_sha256(),
        "parameter_spec": V3_PARAMETER_SPEC,
        "source_hashes": sources,
        "v2_kernel": {
            "version": V2_KERNEL_VERSION,
            "parameter_sha256": V2_PARAMETER_SHA256,
            "source_relative_path": V2_SOURCE_RELATIVE,
            "source_sha256": sources[V2_SOURCE_RELATIVE],
            "authority": "read-only numerical semantics",
        },
        "gold_labels_used_for_selection": False,
        "selection_freeze": {
            "status": "frozen_before_posterior_gold_replay",
            "gold_files_read_before_freeze": False,
            "gold_event_positions_used_for_selection": False,
        },
        "output_policy": {
            "allowed_root_prefix": "dataset_generation_logs/sampling_validation/batch_sampled_v1_3_",
            "scene_sage_results_write": False,
            "new_only": True,
        },
    }


def write_frozen_manifest(output_dir: Path, project_root: Path = PROJECT_ROOT) -> tuple[Path, str]:
    output_dir = Path(output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to reuse non-empty v3 manifest namespace: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(project_root)
    path = output_dir / "v3_parameter_schema_manifest.json"
    data = (json.dumps(manifest, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    path.write_bytes(data)
    digest = sha256_bytes(data)
    (output_dir / "v3_parameter_schema_manifest.sha256").write_text(digest + "\n", encoding="ascii")
    return path, digest


def load_frozen_manifest(path: Path, expected_sha256: str | None = None, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256_file(path)
    if expected_sha256 is not None and actual.lower() != expected_sha256.lower():
        raise ValueError(f"v3 manifest SHA-256 mismatch: expected {expected_sha256}, got {actual}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("gold_labels_used_for_selection") is not False:
        raise ValueError("v3 manifest permits gold labels during selection")
    if value.get("parameter_sha256") != parameter_sha256(value.get("parameter_spec")):
        raise ValueError("v3 parameter SHA-256 does not match parameter_spec")
    current = expected_source_hashes(project_root)
    recorded = value.get("source_hashes", {})
    for relative, digest in recorded.items():
        if relative not in current:
            raise ValueError(f"v3 recorded source is missing: {relative}")
        if current[relative].lower() != str(digest).lower():
            raise ValueError(f"v3 source hash changed: {relative}")
    v2 = value.get("v2_kernel", {})
    if v2.get("parameter_sha256") != V2_PARAMETER_SHA256 or v2.get("version") != V2_KERNEL_VERSION:
        raise ValueError("v2 kernel freeze does not match the aligned v2 authority")
    return value


def is_within(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def assert_new_sampling_namespace(output_root: Path, project_root: Path = PROJECT_ROOT) -> Path:
    root = Path(project_root).resolve()
    output = Path(output_root).resolve()
    if not is_within(output, root / "dataset_generation_logs" / "sampling_validation"):
        raise ValueError("v3 output is outside dataset_generation_logs/sampling_validation")
    if not output.name.startswith("batch_sampled_v1_3_"):
        raise ValueError("v3 output namespace must start with batch_sampled_v1_3_")
    if output.exists():
        raise FileExistsError(f"v3 new_only output namespace already exists: {output}")
    if is_within(output, root / "scenes") or "sage_results" in output.parts:
        raise ValueError("v3 output cannot be under scenes or sage_results")
    output.mkdir(parents=True, exist_ok=True)
    return output


def null_value(value: Any) -> Any:
    """Normalize CSV blanks to explicit Python null without inventing zero."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None
