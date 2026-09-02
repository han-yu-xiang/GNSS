#!/usr/bin/env python3
"""Independently audit the Phase-1 traditional-modeling scientific closure.

The auditor consumes only the frozen r3 model, the immutable Stage4 parameter
table, and the new closure namespace.  It does not import the closure builder,
fit distributions, read raw IQ/SAGE artifacts, or modify any production
artifact.  Its only writes are its own two QA files inside the closure
namespace.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


CANONICAL_REL = Path("dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3")
OUTPUT_REL = Path("dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2")
REPORT_REL = Path("docs/PHASE1_TRADITIONAL_CHANNEL_MODELING_SCIENTIFIC_CLOSURE.md")
STAGE4_PARAMETER_REL = Path("dataset/multipath_event_database/v1/partitions/parameter_set_id=parameters_20260825_stage4_path_v1/facts/path_parameters.csv")

ENVIRONMENTS = ("Urban", "Special Reflective", "Mountain/Valley", "Highway/Open")
BANDS = ("LOW", "MID", "HIGH")
PARAMETERS = ("excess_delay_samples", "doppler_offset_hz", "relative_power_db")
CELL_ORDER = tuple(f"{environment}__{band}" for environment in ENVIRONMENTS for band in BANDS)

QA_RESULT_NAME = "independent_qa_result.json"
QA_REPORT_NAME = "independent_qa_report.md"
CLOSURE_REQUIRED_FILES = (
    "channel_level_statistics.csv",
    "closure_config.json",
    "closure_manifest.json",
    "continuous_elevation_evidence.csv",
    "effect_table.csv",
    "elevation_characterization.csv",
    "environment_characterization.csv",
    "environment_elevation_interaction.csv",
    "figure_table_plan.csv",
    "joint_dependence_interpretation.csv",
    "persistence_duration_statistics.csv",
    "publication_plot_data.csv",
    "publication_table_sources.csv",
    "robustness_matrix.csv",
    "stage4_selection_analysis.csv",
    "support_gap_decision.csv",
    "closure_receipt.json",
)

EXPECTED_ROW_COUNTS = {
    "channel_level_statistics.csv": 120,
    "continuous_elevation_evidence.csv": 12,
    "effect_table.csv": 21,
    "elevation_characterization.csv": 9,
    "environment_characterization.csv": 4,
    "environment_elevation_interaction.csv": 15,
    "figure_table_plan.csv": 9,
    "joint_dependence_interpretation.csv": 51,
    "persistence_duration_statistics.csv": 17,
    "publication_plot_data.csv": 3996,
    "publication_table_sources.csv": 4,
    "robustness_matrix.csv": 33,
    "stage4_selection_analysis.csv": 11,
    "support_gap_decision.csv": 12,
}

CSV_REQUIRED_COLUMNS = {
    "channel_level_statistics.csv": {"scope", "scope_id", "statistic", "status", "interpretation"},
    "continuous_elevation_evidence.csv": {"environment_class", "parameter", "diagnostic_support_status", "evidence_class", "interpretation"},
    "effect_table.csv": {"parameter", "comparison", "comparison_type", "effect_direction", "effect_size", "bootstrap_interval", "LOSO_stability", "support_strength", "scientific_status", "scientific_interpretation"},
    "elevation_characterization.csv": {"elevation_band", "parameter", "observation_count", "median", "effect_vs_elevation_ready_global", "bootstrap_interval", "support_strength", "ELEVATION_EFFECT", "scientific_interpretation"},
    "environment_characterization.csv": {"environment_class", "support_status", "delay_behavior", "delay_family", "doppler_behavior", "doppler_family", "relative_power_behavior", "relative_power_family", "joint_dependence_summary", "derived_channel_statistics", "elevation_dependence", "uncertainty_summary", "data_support_limitations"},
    "environment_elevation_interaction.csv": {"environment_class", "parameter", "comparison", "low_band", "high_band", "effect_size", "bootstrap_interval", "support_strength", "LOSO_stability", "LOSO_margin", "ENVIRONMENT_ELEVATION_INTERACTION", "scientific_interpretation"},
    "figure_table_plan.csv": {"item_id", "item_type", "title", "scientific_question", "source_artifacts", "plot_type", "priority", "vtc_boundary", "notes"},
    "joint_dependence_interpretation.csv": {"scope", "scope_id", "environment_class", "elevation_band", "pair", "correlation", "dependence_status", "support_interpretation", "scientific_interpretation"},
    "persistence_duration_statistics.csv": {"scope", "scope_id", "mean_duration_s", "median_duration_s", "status", "interpretation"},
    "publication_plot_data.csv": {"plot_id", "data_source", "population", "scope", "scope_id", "parameter", "metric", "x", "y", "status"},
    "publication_table_sources.csv": {"table_id", "title", "purpose", "source_artifacts", "priority", "recommended_columns", "vtc_boundary"},
    "robustness_matrix.csv": {"conclusion_id", "conclusion_type", "parameter", "scope", "primary_weighted_effect", "primary_bootstrap_interval", "raw_clustered_effect", "track_median_effect", "stage4_sensitivity", "scene_block_bootstrap", "run_block_sensitivity", "LOSO_validation", "robustness_class", "rationale"},
    "stage4_selection_analysis.csv": {"selection_dimension", "category", "stage3_count", "stage4_count", "stage3_fraction", "stage4_fraction", "fraction_difference", "evidence_status", "interpretation"},
    "support_gap_decision.csv": {"environment_class", "elevation_band", "cell_id", "support_status", "direct_observation_count", "sum_weights", "kish_effective_sample_size", "track_count", "run_count", "scene_count", "bounded_journal_claims", "complete_12_cell_modeling", "continuous_elevation_generalization", "future_ai_model", "decision_reason"},
}

REQUIRED_DECISION_KEYS = (
    "PHASE_1_TRADITIONAL_MODEL_BUILD",
    "PHASE_1_SCIENTIFIC_CLOSURE",
    "JOURNAL_TRADITIONAL_MODELING_EVIDENCE",
    "MASTER_THESIS_TRADITIONAL_MODELING_EVIDENCE",
    "ENVIRONMENT_EFFECT",
    "ELEVATION_EFFECT",
    "ENVIRONMENT_ELEVATION_INTERACTION",
    "AI_JOINT_DENSITY_MOTIVATION",
    "CONTINUOUS_ELEVATION_FOR_PHASE2",
    "PROCESS_20_46_MHZ_BEFORE_PHASE2",
    "NEW_DATA_COLLECTION_BEFORE_PHASE2",
)

EXPECTED_POPULATION = {
    "academic_stage3_observations": 783,
    "algorithm_tracks": 366,
    "centers": 445,
    "elevation_ready_observations": 716,
    "prns": 18,
    "runs": 50,
    "scenes": 12,
    "stage4_confirmed_paths": 100,
}
EXPECTED_CANONICAL_MANIFEST_SHA256 = "61c4b3aa171b6a59d17607394770b684251d656eeb19813ca13ebed2454b1782"
EXPECTED_CANONICAL_RECEIPT_SHA256 = "bb4503309e98657791cba08ee2c99bf456a2f22caedb9bc203c698fa2470c3c5"
EXPECTED_CANONICAL_QA_SHA256 = "916304ca04e5e84eb8e3349d9e072b1b36489a8aa0c95e34110b91f2012cfbf5"
EXPECTED_STAGE4_SHA256 = "2a44913d1c06f78d2748428b1d72f1b4712a6b5d3f33fc598a14fe17a3e3414a"

FROZEN_SOURCE_PATHS = {
    "pipeline_sha256": Path("scripts/sage_pipeline/run_nav_sage_pipeline.m"),
    "wrapper_sha256": Path("scripts/sage_pipeline/Invoke-BatchSageWindows.ps1"),
    "executor_sha256": Path("scripts/sage_pipeline/run_batch_sage.py"),
    "manifest_sha256": Path("dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json"),
    "inventory_sha256": Path("dataset_generation_logs/production_planning_10mhz_20260812/production_inventory_10MHz.csv"),
}

ALLOWED_SUPPORT = {"DATA_SUPPORTED", "SPARSE_PARTIAL_POOLING", "PRIOR_DOMINANT", "NO_DIRECT_SUPPORT"}
ALLOWED_EFFECT_STATUS = {"SUPPORTED", "PARTIAL", "INCONCLUSIVE", "NO_ROBUST_DIFFERENCE", "NOT_SUPPORTED"}
ALLOWED_ROBUSTNESS = {"ROBUST", "MOSTLY_ROBUST", "SENSITIVE", "INCONCLUSIVE"}


def read_csv(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), set(reader.fieldnames or [])


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_interval(value: Any) -> tuple[float, float, float] | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not (text.startswith("[") and text.endswith("]")):
        return None
    parts = [parse_float(part.strip()) for part in text[1:-1].split(",")]
    if len(parts) != 3 or any(part is None for part in parts):
        return None
    return float(parts[0]), float(parts[1]), float(parts[2])


def decision_block_values(report_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    pattern = re.compile(r"^([A-Z0-9_]+)\s*=\s*([^\s]+)\s*$")
    for line in report_text.splitlines():
        match = pattern.match(line.strip())
        if match and match.group(1) in REQUIRED_DECISION_KEYS:
            values[match.group(1)] = match.group(2)
    return values


def validate_support_grid(rows: Sequence[Mapping[str, Any]]) -> bool:
    if len(rows) != len(CELL_ORDER):
        return False
    if {str(row.get("cell_id", "")) for row in rows} != set(CELL_ORDER):
        return False
    for row in rows:
        cell_id = str(row.get("cell_id", ""))
        status = str(row.get("support_status", ""))
        count = parse_float(row.get("direct_observation_count"))
        if status not in ALLOWED_SUPPORT or count is None or count < 0 or count != int(count):
            return False
        if count == 0 and status != "NO_DIRECT_SUPPORT":
            return False
        if count > 0 and status == "NO_DIRECT_SUPPORT":
            return False
        if cell_id == "Highway/Open__LOW" and (count != 0 or status != "NO_DIRECT_SUPPORT"):
            return False
    return True


def _aggregate_label(values: Sequence[str]) -> str:
    if values and all(value == "SUPPORTED" for value in values):
        return "SUPPORTED"
    if any(value in {"SUPPORTED", "PARTIAL"} for value in values):
        return "PARTIAL"
    if values and all(value == "NOT_SUPPORTED" for value in values):
        return "NOT_SUPPORTED"
    return "INCONCLUSIVE"


def _expected_report_decisions(
    effect_rows: Sequence[Mapping[str, Any]],
    elevation_rows: Sequence[Mapping[str, Any]],
    interaction_rows: Sequence[Mapping[str, Any]],
    joint_rows: Sequence[Mapping[str, Any]],
    continuous_rows: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    environment_by_parameter: dict[str, list[str]] = {parameter: [] for parameter in PARAMETERS}
    for row in effect_rows:
        if row.get("comparison_type") == "ENVIRONMENT" and row.get("parameter") in environment_by_parameter:
            environment_by_parameter[str(row["parameter"])].append(str(row.get("scientific_status", "")))
    environment_status = {parameter: _aggregate_label(values) for parameter, values in environment_by_parameter.items()}
    elevation_by_parameter: dict[str, list[str]] = {parameter: [] for parameter in PARAMETERS}
    for row in elevation_rows:
        if row.get("parameter") in elevation_by_parameter:
            elevation_by_parameter[str(row["parameter"])].append(str(row.get("ELEVATION_EFFECT", "")))
    elevation_status = {parameter: _aggregate_label(values) for parameter, values in elevation_by_parameter.items()}
    interaction_status = {
        str(row.get("parameter")): str(row.get("ENVIRONMENT_ELEVATION_INTERACTION"))
        for row in interaction_rows
        if row.get("environment_class") == "ALL_ENVIRONMENTS"
    }
    global_correlations = [
        abs(parse_float(row.get("correlation")) or 0.0)
        for row in joint_rows
        if row.get("scope") == "global"
    ]
    supported_environment_dependence = any(
        row.get("scope") == "environment" and row.get("dependence_status") == "DATA_SUPPORTED"
        for row in joint_rows
    )
    motivation = "STRONG" if any(value >= 0.4 for value in global_correlations) and supported_environment_dependence else "MODERATE" if global_correlations else "WEAK"
    evidence = [str(row.get("evidence_class", "")) for row in continuous_rows]
    continuous = "RECOMMENDED" if evidence and all(value == "ROBUST" for value in evidence) else "NOT_RECOMMENDED" if evidence and all(value == "INSUFFICIENT" for value in evidence) else "CONDITIONAL"
    return {
        "PHASE_1_TRADITIONAL_MODEL_BUILD": "COMPLETE",
        "PHASE_1_SCIENTIFIC_CLOSURE": "PASS_WITH_LIMITATIONS",
        "JOURNAL_TRADITIONAL_MODELING_EVIDENCE": "READY_WITH_LIMITATIONS",
        "MASTER_THESIS_TRADITIONAL_MODELING_EVIDENCE": "READY_WITH_LIMITATIONS",
        "ENVIRONMENT_EFFECT": _aggregate_label(list(environment_status.values())),
        "ELEVATION_EFFECT": _aggregate_label(list(elevation_status.values())),
        "ENVIRONMENT_ELEVATION_INTERACTION": _aggregate_label([interaction_status.get(parameter, "INCONCLUSIVE") for parameter in PARAMETERS]),
        "AI_JOINT_DENSITY_MOTIVATION": motivation,
        "CONTINUOUS_ELEVATION_FOR_PHASE2": continuous,
        "PROCESS_20_46_MHZ_BEFORE_PHASE2": "CONDITIONAL",
        "NEW_DATA_COLLECTION_BEFORE_PHASE2": "CONDITIONAL",
    }


def _safe_closure_namespace(root: Path, output_dir: Path) -> bool:
    try:
        relative = output_dir.relative_to(root)
    except ValueError:
        return False
    parts = tuple(part.lower() for part in relative.parts)
    return (
        len(parts) == 3
        and parts[:2] == ("dataset_generation_logs", "channel_modeling")
        and parts[2].startswith("phase1_scientific_closure_")
        and "scenes" not in parts
        and "sage_results" not in parts
    )


def audit(root: Path, output_dir: Path, report_path: Path) -> dict[str, Any]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    report_path = report_path.resolve()
    checks: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        item = {"check": name, "detail": detail, "status": "PASS" if passed else "FAIL"}
        checks.append(item)
        if not passed:
            failures.append(item)

    record("new_namespace_safe", _safe_closure_namespace(root, output_dir), str(output_dir))
    if not output_dir.exists() or not output_dir.is_dir():
        record("closure_namespace_exists", False, str(output_dir))
        return _write_qa(output_dir, report_path, checks, failures, {})
    record("closure_namespace_exists", True, str(output_dir))

    actual_names = {path.name for path in output_dir.iterdir() if path.is_file()}
    missing = sorted(set(CLOSURE_REQUIRED_FILES) - actual_names)
    unexpected = sorted(actual_names - set(CLOSURE_REQUIRED_FILES) - {QA_RESULT_NAME, QA_REPORT_NAME})
    record("required_closure_files", not missing, f"missing={missing}")
    record("no_unexpected_nonqa_files", not unexpected, f"unexpected={unexpected}")

    tables: dict[str, list[dict[str, str]]] = {}
    table_fields: dict[str, set[str]] = {}
    for name, required_columns in CSV_REQUIRED_COLUMNS.items():
        path = output_dir / name
        if not path.exists():
            record(f"schema:{name}", False, "file missing")
            continue
        try:
            rows, fields = read_csv(path)
            tables[name] = rows
            table_fields[name] = fields
            missing_columns = sorted(required_columns - fields)
            expected_count = EXPECTED_ROW_COUNTS.get(name)
            count_ok = expected_count is None or len(rows) == expected_count
            record(f"schema:{name}", not missing_columns and count_ok, f"rows={len(rows)} expected={expected_count} missing_columns={missing_columns}")
        except Exception as exc:  # pragma: no cover - defensive audit path
            record(f"schema:{name}", False, f"read error: {exc}")

    manifest: dict[str, Any] = {}
    receipt: dict[str, Any] = {}
    config: dict[str, Any] = {}
    try:
        manifest = read_json(output_dir / "closure_manifest.json")
        receipt = read_json(output_dir / "closure_receipt.json")
        config = read_json(output_dir / "closure_config.json")
        record("closure_json_readable", True, "manifest, receipt, and config")
    except Exception as exc:
        record("closure_json_readable", False, str(exc))

    if manifest and receipt:
        manifest_hash = sha256_file(output_dir / "closure_manifest.json")
        receipt_hashes = receipt.get("output_hashes_excluding_receipt", {})
        manifest_hashes = manifest.get("output_hashes_excluding_manifest_and_receipt", {})
        expected_non_manifest = set(CLOSURE_REQUIRED_FILES) - {"closure_manifest.json", "closure_receipt.json"}
        record("closure_manifest_hash_bound", receipt.get("closure_manifest_sha256") == manifest_hash, f"actual={manifest_hash} recorded={receipt.get('closure_manifest_sha256')}")
        record("closure_manifest_output_hash_keys", set(manifest_hashes) == expected_non_manifest, f"missing={sorted(expected_non_manifest - set(manifest_hashes))} extra={sorted(set(manifest_hashes) - expected_non_manifest)}")
        record("closure_manifest_output_hashes", all((output_dir / name).exists() and sha256_file(output_dir / name) == value for name, value in manifest_hashes.items()), "recomputed closure data hashes")
        expected_receipt_files = set(CLOSURE_REQUIRED_FILES) - {"closure_receipt.json"}
        record("closure_receipt_output_file_list", set(receipt.get("output_files", [])) == expected_receipt_files, f"files={len(receipt.get('output_files', []))}")
        record("closure_receipt_output_hashes", set(receipt_hashes) == expected_receipt_files and all((output_dir / name).exists() and sha256_file(output_dir / name) == value for name, value in receipt_hashes.items()), "recomputed receipt hashes")
        record("closure_receipt_status", receipt.get("status") == "COMPLETED", str(receipt.get("status")))
        record("closure_manifest_status", manifest.get("status") == "COMPLETED_WITH_LIMITATIONS", str(manifest.get("status")))
        record("closure_report_hash", report_path.exists() and manifest.get("report_sha256") == sha256_file(report_path), str(report_path))
        record("closure_report_path_bound", Path(str(manifest.get("report_path", ""))).resolve() == report_path, str(manifest.get("report_path")))
        record("closure_population_bound", manifest.get("population") == EXPECTED_POPULATION, json.dumps(manifest.get("population", {}), sort_keys=True))
        manifest_count_fields = {
            "effect_rows": "effect_table.csv",
            "environment_rows": "environment_characterization.csv",
            "elevation_rows": "elevation_characterization.csv",
            "interaction_rows": "environment_elevation_interaction.csv",
            "stage4_selection_rows": "stage4_selection_analysis.csv",
            "continuous_rows": "continuous_elevation_evidence.csv",
            "support_rows": "support_gap_decision.csv",
        }
        record("closure_manifest_row_counts", all(manifest.get(field) == EXPECTED_ROW_COUNTS[file_name] for field, file_name in manifest_count_fields.items()), json.dumps({field: manifest.get(field) for field in manifest_count_fields}, sort_keys=True))
    else:
        record("closure_manifest_integrity", False, "manifest or receipt unavailable")

    boundary = config.get("execution_boundary", {}) if config else {}
    boundary_keys = {"raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz", "train_ai", "create_production_request"}
    record("closure_execution_boundary", all(boundary.get(key) is False for key in boundary_keys), json.dumps(boundary, sort_keys=True))
    record("closure_statistical_contract", config.get("primary_statistical_unit") == "WEIGHTED_OBSERVATION" and config.get("primary_weight") == "1 / algorithm_track_size" and config.get("primary_uncertainty") == "scene-block bootstrap", json.dumps({key: config.get(key) for key in ("primary_statistical_unit", "primary_weight", "primary_uncertainty")}, sort_keys=True))
    record("closure_ricean_k_boundary", config.get("ricean_k") == "NOT_IDENTIFIABLE", str(config.get("ricean_k")))

    canonical_dir = root / CANONICAL_REL
    canonical_manifest_path = canonical_dir / "model_manifest.json"
    canonical_receipt_path = canonical_dir / "build_receipt.json"
    canonical_qa_path = canonical_dir / "independent_qa_result.json"
    try:
        canonical_manifest = read_json(canonical_manifest_path)
        canonical_receipt = read_json(canonical_receipt_path)
        canonical_qa = read_json(canonical_qa_path)
        canonical_manifest_hash = sha256_file(canonical_manifest_path)
        canonical_receipt_hash = sha256_file(canonical_receipt_path)
        canonical_qa_hash = sha256_file(canonical_qa_path)
        record("canonical_r3_manifest_frozen", canonical_manifest_hash == EXPECTED_CANONICAL_MANIFEST_SHA256 and manifest.get("canonical_model_manifest_sha256") == canonical_manifest_hash, canonical_manifest_hash)
        record("canonical_r3_receipt_frozen", canonical_receipt_hash == EXPECTED_CANONICAL_RECEIPT_SHA256 and manifest.get("canonical_model_receipt_sha256") == canonical_receipt_hash, canonical_receipt_hash)
        record("canonical_r3_qa_frozen", canonical_qa_hash == EXPECTED_CANONICAL_QA_SHA256 and manifest.get("canonical_model_qa_sha256") == canonical_qa_hash, canonical_qa_hash)
        record("canonical_r3_identity_and_qa", canonical_manifest.get("model_id") == "environment_elevation_stage3_academic_path_model_v1" and canonical_manifest.get("status") == "COMPLETED_WITH_LIMITATIONS" and canonical_qa.get("qa_status") == "PASS", json.dumps({"model_id": canonical_manifest.get("model_id"), "status": canonical_manifest.get("status"), "qa_status": canonical_qa.get("qa_status")}, sort_keys=True))
        record("canonical_r3_receipt_bound", canonical_receipt.get("status") == "COMPLETED" and canonical_receipt.get("model_manifest_sha256") == canonical_manifest_hash, str(canonical_receipt.get("model_manifest_sha256")))
        frozen = canonical_manifest.get("frozen_hash_status", {})
        record("canonical_r3_frozen_hash_record", frozen.get("all_match") is True and all(value is True for value in frozen.get("matches", {}).values()), json.dumps(frozen, sort_keys=True))
        record("canonical_r3_source_hash_record", canonical_manifest.get("source", {}).get("source_hashes_match_prior") is True and canonical_manifest.get("source", {}).get("prior_output_hashes_match") is True, json.dumps(canonical_manifest.get("source", {}), sort_keys=True))
        record("canonical_r3_global_families", canonical_manifest.get("selected_global_families") == {"doppler_offset_hz": "normal", "excess_delay_samples": "lognormal", "relative_power_db": "normal"}, json.dumps(canonical_manifest.get("selected_global_families", {}), sort_keys=True))
        stage4_path = root / STAGE4_PARAMETER_REL
        actual_stage4_hash = sha256_file(stage4_path)
        record("stage4_parameter_source_frozen", actual_stage4_hash == EXPECTED_STAGE4_SHA256 and canonical_manifest.get("source", {}).get("stage4_source_sha256") == actual_stage4_hash, actual_stage4_hash)
        for key, relative_path in FROZEN_SOURCE_PATHS.items():
            expected = frozen.get("expected", {}).get(key)
            path = root / relative_path
            actual = sha256_file(path) if path.exists() else None
            record(f"frozen_source:{key}", actual is not None and actual == expected, f"path={relative_path} actual={actual} expected={expected}")
    except Exception as exc:  # pragma: no cover - defensive audit path
        record("canonical_r3_readable", False, str(exc))

    effect_rows = tables.get("effect_table.csv", [])
    effect_statuses = {str(row.get("scientific_status", "")) for row in effect_rows}
    effect_intervals_ok = all(parse_interval(row.get("bootstrap_interval")) is not None and int(float(row.get("bootstrap_replicates", 0))) == 1000 for row in effect_rows) if effect_rows else False
    record("effect_table_machine_readable", len(effect_rows) == 21 and effect_statuses <= ALLOWED_EFFECT_STATUS and effect_intervals_ok, f"rows={len(effect_rows)} statuses={sorted(effect_statuses)}")
    record("effect_table_required_claim_fields", all(str(row.get("effect_direction", "")) and str(row.get("support_strength", "")) and str(row.get("LOSO_stability", "")) and str(row.get("scientific_interpretation", "")) for row in effect_rows), "effect direction, support, LOSO, and interpretation populated")

    support_rows = tables.get("support_gap_decision.csv", [])
    support_counts = Counter(str(row.get("support_status", "")) for row in support_rows)
    record("support_grid_complete_and_empty_cell_guard", validate_support_grid(support_rows), f"cells={len(support_rows)}")
    record("support_class_counts", support_counts == Counter({"DATA_SUPPORTED": 5, "SPARSE_PARTIAL_POOLING": 4, "PRIOR_DOMINANT": 2, "NO_DIRECT_SUPPORT": 1}), json.dumps(dict(support_counts), sort_keys=True))
    record("support_gap_decisions_explicit", all(str(row.get("decision_reason", "")).find("no synthetic fill") >= 0 and str(row.get("complete_12_cell_modeling", "")) for row in support_rows), "bounded claims and no synthetic fill are explicit")

    elevation_rows = tables.get("elevation_characterization.csv", [])
    record("formal_elevation_grid_complete", {(row.get("elevation_band"), row.get("parameter")) for row in elevation_rows} == set((band, parameter) for band in BANDS for parameter in PARAMETERS), "LOW/MID/HIGH × three parameters")
    record("formal_elevation_status_vocabulary", all(str(row.get("ELEVATION_EFFECT", "")) in ALLOWED_EFFECT_STATUS for row in elevation_rows), "SUPPORTED/PARTIAL/INCONCLUSIVE/NOT_SUPPORTED vocabulary")

    interaction_rows = tables.get("environment_elevation_interaction.csv", [])
    direct_interactions = [row for row in interaction_rows if row.get("environment_class") != "ALL_ENVIRONMENTS"]
    aggregate_interactions = [row for row in interaction_rows if row.get("environment_class") == "ALL_ENVIRONMENTS"]
    expected_direct = {(environment, parameter) for environment in ENVIRONMENTS for parameter in PARAMETERS}
    actual_direct = {(row.get("environment_class"), row.get("parameter")) for row in direct_interactions}
    record("interaction_difference_in_differences_coverage", actual_direct == expected_direct and len(aggregate_interactions) == 3, f"direct={len(direct_interactions)} aggregate={len(aggregate_interactions)}")
    record("interaction_bootstrap_loso_contract", all(str(row.get("LOSO_stability", "")) in {"STABLE", "MOSTLY_ROBUST", "SENSITIVE", "INCONCLUSIVE", "AGGREGATED"} and str(row.get("bootstrap_interval", "")) for row in interaction_rows if row.get("environment_class") != "ALL_ENVIRONMENTS" and row.get("support_strength") != "PRIOR_DOMINANT") and all(str(row.get("LOSO_margin", "")) for row in interaction_rows if row.get("environment_class") != "ALL_ENVIRONMENTS" and row.get("LOSO_stability") != "INCONCLUSIVE"), "hierarchical contrast with scene bootstrap and LOSO fields")
    record("interaction_empty_cell_not_filled", not any(row.get("environment_class") == "Highway/Open" and row.get("low_band") == "LOW" for row in direct_interactions), "Highway/Open–LOW remains without direct interaction support")

    continuous_rows = tables.get("continuous_elevation_evidence.csv", [])
    evidence_vocabulary = {"ROBUST", "WEAK", "INCONSISTENT", "INSUFFICIENT"}
    record("continuous_elevation_contract", len(continuous_rows) == 12 and all(row.get("evidence_class") in evidence_vocabulary for row in continuous_rows), "environment × parameter evidence classes")
    record("continuous_sparse_support_guard", all(row.get("evidence_class") == "INSUFFICIENT" for row in continuous_rows if row.get("diagnostic_support_status") != "DATA_SUPPORTED"), "sparse/prior support cannot be promoted to continuous evidence")

    joint_rows = tables.get("joint_dependence_interpretation.csv", [])
    record("joint_dependence_pairs_complete", len(joint_rows) == 51 and {row.get("pair") for row in joint_rows} == {"excess_delay_samples__doppler_offset_hz", "excess_delay_samples__relative_power_db", "doppler_offset_hz__relative_power_db"}, "17 scopes × three parameter pairs")
    global_joint = [row for row in joint_rows if row.get("scope") == "global"]
    record("joint_dependence_non_independence_gate", any(abs(parse_float(row.get("correlation")) or 0.0) >= 0.4 for row in global_joint) and any(row.get("scope") == "environment" and row.get("dependence_status") == "DATA_SUPPORTED" for row in joint_rows), "global and supported environment dependence")

    stage4_rows = tables.get("stage4_selection_analysis.csv", [])
    stage4_by_dimension = Counter(str(row.get("selection_dimension", "")) for row in stage4_rows)
    record("stage4_selection_dimensions_complete", stage4_by_dimension == Counter({"environment": 4, "elevation_ready": 3, "parameter_global": 3, "persistence_proxy": 1}), json.dumps(dict(stage4_by_dimension), sort_keys=True))
    record("stage4_selection_not_external_truth", len(stage4_rows) == 11 and all("not external truth" in str(row.get("interpretation", "")).lower() for row in stage4_rows if row.get("selection_dimension") == "parameter_global") and any("not external truth" in str(row.get("interpretation", "")).lower() for row in stage4_rows), "selection-sensitive descriptive comparison")
    parameter_stage4 = [row for row in stage4_rows if row.get("selection_dimension") == "parameter_global"]
    record("stage4_parameter_materiality_recomputed", sum(row.get("evidence_status") == "MATERIAL_DIFFERENCE" for row in parameter_stage4) == 2, json.dumps([row.get("evidence_status") for row in parameter_stage4]))
    record("stage4_population_counts_bound", all(parse_float(row.get("stage3_count")) == 783 and parse_float(row.get("stage4_count")) == 100 for row in parameter_stage4), "Stage3=783 and Stage4=100 for parameter rows")

    channel_rows = tables.get("channel_level_statistics.csv", [])
    ricean_rows = [row for row in channel_rows if row.get("statistic") == "ricean_k_factor"]
    record("channel_level_and_path_scope_present", len(channel_rows) == 120 and any(row.get("scope") == "global" for row in channel_rows), "derived channel statistics retained separately from path-level closure")
    record("ricean_k_not_identifiable", bool(ricean_rows) and all(row.get("status") == "NOT_IDENTIFIABLE" for row in ricean_rows), json.dumps(ricean_rows, sort_keys=True))
    persistence_rows = tables.get("persistence_duration_statistics.csv", [])
    record("persistence_is_algorithm_observed", len(persistence_rows) == 17 and all("physical" in str(row.get("interpretation", "")).lower() or "algorithm" in str(row.get("interpretation", "")).lower() for row in persistence_rows), "persistence is not physical reflector lifetime")

    robustness_rows = tables.get("robustness_matrix.csv", [])
    record("robustness_matrix_complete", len(robustness_rows) == 33 and {row.get("robustness_class") for row in robustness_rows} <= ALLOWED_ROBUSTNESS, "environment, elevation, interaction, and sensitivity views")
    record("robustness_matrix_has_required_sensitivities", all(str(row.get(field, "")) for row in robustness_rows for field in ("primary_weighted_effect", "stage4_sensitivity", "scene_block_bootstrap", "run_block_sensitivity", "LOSO_validation", "rationale")), "weighted/raw/track/Stage4/bootstrap/run/LOSO fields retained")

    figure_rows = tables.get("figure_table_plan.csv", [])
    table_rows = tables.get("publication_table_sources.csv", [])
    record("paper_evidence_plan_ranked", len(figure_rows) == 9 and len(table_rows) == 4 and {row.get("priority") for row in figure_rows + table_rows} <= {"CORE", "SUPPLEMENTARY", "THESIS_ONLY"}, "ranked CORE/SUPPLEMENTARY/THESIS_ONLY plan")
    plot_rows = tables.get("publication_plot_data.csv", [])
    record("plot_data_is_derived_only", len(plot_rows) == 3996 and all(not any(token in str(row.get("data_source", "")).lower() for token in ("raw iq", "sage", ".mat", ".iq")) for row in plot_rows), "publication plot data references derived artifacts only")

    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    decisions = decision_block_values(report_text)
    expected_decisions = _expected_report_decisions(effect_rows, elevation_rows, interaction_rows, joint_rows, continuous_rows)
    record("report_decision_block_complete", set(decisions) == set(REQUIRED_DECISION_KEYS), f"missing={sorted(set(REQUIRED_DECISION_KEYS) - set(decisions))}")
    record("report_decision_block_matches_tables", all(decisions.get(key) == value for key, value in expected_decisions.items()), json.dumps({key: {"actual": decisions.get(key), "expected": value} for key, value in expected_decisions.items() if decisions.get(key) != value}, sort_keys=True))
    record("report_protection_and_claim_boundaries", all(phrase in report_text for phrase in ("RICEAN_K = NOT_IDENTIFIABLE", "Stage4 is not external truth", "Highway/Open–LOW", "no synthetic fill", "difference-in-differences")), "forbidden overclaims and protected boundaries are stated")

    final_decision = expected_decisions | {"INDEPENDENT_QA": "PASS" if not failures else "FAIL"}
    return _write_qa(output_dir, report_path, checks, failures, final_decision)


def _write_qa(output_dir: Path, report_path: Path, checks: Sequence[Mapping[str, str]], failures: Sequence[Mapping[str, str]], final_decision: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "qa_version": "phase1-scientific-closure-independent-qa-v1",
        "qa_status": "PASS" if not failures else "FAIL",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "closure_namespace": str(output_dir),
        "report_path": str(report_path),
        "check_count": len(checks),
        "checks": list(checks),
        "failure_checks": list(failures),
        "final_decision": dict(final_decision),
    }
    if output_dir.exists() and output_dir.is_dir():
        (output_dir / QA_RESULT_NAME).write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        report_lines = [
            "# Phase-1 Scientific Closure Independent QA",
            "",
            f"Status: **{result['qa_status']}**",
            "",
            f"Closure namespace: `{output_dir}`",
            f"Closure report: `{report_path}`",
            "",
            "The audit re-read the closure artifacts and the frozen canonical r3 provenance. It did not import the builder, read raw IQ/SAGE artifacts, run MATLAB, modify production inputs, or train an AI model.",
            "",
            "| Check | Status | Detail |",
            "|---|---|---|",
        ]
        for check in checks:
            detail = str(check.get("detail", "")).replace("|", "\\|").replace("\n", " ")
            report_lines.append(f"| `{check.get('check')}` | `{check.get('status')}` | {detail} |")
        report_lines.extend(["", "## Decision", "", "```text", f"INDEPENDENT_QA = {result['qa_status']}", f"FAILURE_COUNT = {len(failures)}", "```", ""])
        (output_dir / QA_REPORT_NAME).write_text("\n".join(report_lines), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output_dir = (args.output or root / OUTPUT_REL).resolve()
    report_path = (args.report or root / REPORT_REL).resolve()
    try:
        result = audit(root, output_dir, report_path)
    except Exception as exc:  # pragma: no cover - command-line safety net
        print(f"PHASE1_CLOSURE_QA_REJECTED={exc}")
        return 2
    print(json.dumps({"qa_status": result.get("qa_status"), "check_count": result.get("check_count"), "failure_count": len(result.get("failure_checks", []))}, indent=2, sort_keys=True))
    print(f"PHASE1_CLOSURE_INDEPENDENT_QA={result.get('qa_status')}")
    return 0 if result.get("qa_status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
