#!/usr/bin/env python3
"""Independently audit the Stage3 Environment x Elevation path model.

The auditor deliberately does not import the model builder or its fitting and
selection routines.  It re-reads the generated CSV/JSON artifacts, recomputes
provenance hashes, checks the weighted statistical contract, validates the
stored distributions with SciPy, and writes only its own QA files inside the
already-created new model namespace.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy import stats


ENVIRONMENTS = ("Urban", "Special Reflective", "Mountain/Valley", "Highway/Open")
BANDS = ("LOW", "MID", "HIGH")
PARAMETERS = ("excess_delay_samples", "doppler_offset_hz", "relative_power_db")
CANDIDATE_FAMILIES = {
    "excess_delay_samples": ("lognormal", "gamma", "weibull"),
    "doppler_offset_hz": ("normal", "laplace", "student_t"),
    "relative_power_db": ("normal", "laplace", "student_t"),
}
POLICIES = {
    "A_RAW_OBSERVATION",
    "C_WEIGHTED_OBSERVATION",
    "B_ALGORITHM_TRACK_MEDIAN",
}
MODEL_ID = "environment_elevation_stage3_academic_path_model_v1"
BOOTSTRAP_REPLICATES = 1000
REQUIRED_MODEL_FILES = (
    "source_population_audit.csv",
    "cell_support_matrix.csv",
    "weighted_parameter_summary.csv",
    "candidate_family_scores.csv",
    "selected_marginal_models.csv",
    "global_models.csv",
    "environment_models.csv",
    "environment_elevation_models.csv",
    "joint_dependence_models.csv",
    "scene_block_bootstrap.csv",
    "run_block_sensitivity.csv",
    "observation_track_sensitivity.csv",
    "stage3_stage4_sensitivity.csv",
    "stage3_stage4_cdf_comparison.csv",
    "continuous_elevation_diagnostics.csv",
    "derived_channel_statistics.csv",
    "persistence_duration_statistics.csv",
    "model_diagnostics.csv",
    "model_config.json",
    "sampling_contract.json",
    "model_manifest.json",
    "build_receipt.json",
)
QA_FILES = {"independent_qa_result.json", "independent_qa_report.md"}

INGESTION_ID = "ingestion_20260825_event_path_v1"
INGESTION_REL = Path("dataset/multipath_event_database/v1/partitions") / f"ingestion_id={INGESTION_ID}"
INGESTION_MANIFEST_REL = Path("dataset/multipath_event_database/v1/manifests/ingestions") / f"{INGESTION_ID}.json"
ALIGNMENT_ID = "alignment_20260825_tow_geometry_scene_v1"
ALIGNMENT_REL = Path("dataset/multipath_event_database/v1/partitions") / f"alignment_id={ALIGNMENT_ID}"
SCENE_METADATA_REL = Path("dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv")
PRODUCTION_MANIFEST_REL = Path("dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json")
PRODUCTION_INVENTORY_REL = Path("dataset_generation_logs/production_planning_10mhz_20260812/production_inventory_10MHz.csv")
PIPELINE_REL = Path("scripts/sage_pipeline/run_nav_sage_pipeline.m")
WRAPPER_REL = Path("scripts/sage_pipeline/Invoke-BatchSageWindows.ps1")
EXECUTOR_REL = Path("scripts/sage_pipeline/run_batch_sage.py")
STAGE4_PARAMETER_REL = Path(
    "dataset/multipath_event_database/v1/partitions/"
    "parameter_set_id=parameters_20260825_stage4_path_v1/facts/path_parameters.csv"
)


def expected_cell_keys(environments: Sequence[str] = ENVIRONMENTS, bands: Sequence[str] = BANDS) -> tuple[str, ...]:
    return tuple(f"{environment}__{band}" for environment in environments for band in bands)


def is_near_psd_correlation(matrix: Sequence[Sequence[float]], tolerance: float = 1e-8) -> bool:
    array = np.asarray(matrix, dtype=float)
    if array.ndim != 2 or array.shape[0] != array.shape[1] or not np.all(np.isfinite(array)):
        return False
    if not np.allclose(array, array.T, atol=tolerance, rtol=0.0):
        return False
    if not np.allclose(np.diag(array), np.ones(array.shape[0]), atol=tolerance, rtol=0.0):
        return False
    return bool(np.min(np.linalg.eigvalsh(array)) >= -tolerance)


def track_weights_conserve(rows: Sequence[Mapping[str, Any]], tolerance: float = 1e-9) -> bool:
    sums: dict[str, float] = defaultdict(float)
    if not rows:
        return False
    for row in rows:
        track_id = str(row.get("track_id", "")).strip()
        try:
            weight = float(row.get("track_weight", ""))
        except (TypeError, ValueError):
            return False
        if not track_id or not math.isfinite(weight) or weight <= 0.0:
            return False
        sums[track_id] += weight
    return bool(sums) and all(abs(value - 1.0) <= tolerance for value in sums.values())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def scope_keys() -> tuple[tuple[str, str, str, str], ...]:
    return (
        ("global", "global", "ALL", "ALL"),
        *(("environment", environment, environment, "ALL") for environment in ENVIRONMENTS),
        *(("cell", f"{environment}__{band}", environment, band) for environment in ENVIRONMENTS for band in BANDS),
    )


def source_paths(root: Path) -> dict[str, Path]:
    return {
        "ingestion_manifest": root / INGESTION_MANIFEST_REL,
        "sage_runs": root / INGESTION_REL / "facts/sage_runs.csv",
        "events": root / INGESTION_REL / "facts/events.csv",
        "event_paths": root / INGESTION_REL / "facts/event_paths.csv",
        "event_context_aligned": root / ALIGNMENT_REL / "facts/event_context_aligned.csv",
        "time_alignment": root / ALIGNMENT_REL / "dimensions/time_alignment.csv",
        "scene_metadata": root / SCENE_METADATA_REL,
        "production_manifest": root / PRODUCTION_MANIFEST_REL,
        "production_inventory": root / PRODUCTION_INVENTORY_REL,
        "pipeline": root / PIPELINE_REL,
        "wrapper": root / WRAPPER_REL,
        "executor": root / EXECUTOR_REL,
    }


def current_source_hashes(root: Path, paths: Mapping[str, Path]) -> dict[str, str]:
    hashes = {label: sha256_file(path) for label, path in paths.items() if path.is_file()}
    runs = read_csv_rows(paths["sage_runs"])
    artifact_names = (
        "run_context.json",
        "run_context.mat",
        "stage0_valid_40ms_windows.csv",
        "stage3_persistence.csv",
        "stage3_reliable_centers.csv",
        "stage3_nav_persistence.mat",
        "stage4_joint_summary.csv",
        "stage4_joint_paths.csv",
        "stage4_nav_joint_100ms.mat",
    )
    for run in runs:
        relative = str(run.get("source_result_relpath", "")).strip()
        run_id = str(run.get("run_id", "")).strip()
        if not relative or not run_id:
            continue
        directory = root / relative
        for name in artifact_names:
            path = directory / name
            if path.is_file():
                hashes[f"{run_id}::{name}"] = sha256_file(path)
    return hashes


def _family_cdf(family: str, parameters: Mapping[str, float], values: np.ndarray) -> np.ndarray:
    if family == "lognormal":
        return stats.lognorm.cdf(values, parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "gamma":
        return stats.gamma.cdf(values, parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "weibull":
        return stats.weibull_min.cdf(values, parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "normal":
        return stats.norm.cdf(values, loc=parameters["loc"], scale=parameters["scale"])
    if family == "laplace":
        return stats.laplace.cdf(values, loc=parameters["loc"], scale=parameters["scale"])
    if family == "student_t":
        return stats.t.cdf(values, parameters["df"], loc=parameters["loc"], scale=parameters["scale"])
    raise ValueError(family)


def _family_ppf(family: str, parameters: Mapping[str, float], probabilities: np.ndarray) -> np.ndarray:
    if family == "lognormal":
        return stats.lognorm.ppf(probabilities, parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "gamma":
        return stats.gamma.ppf(probabilities, parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "weibull":
        return stats.weibull_min.ppf(probabilities, parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "normal":
        return stats.norm.ppf(probabilities, loc=parameters["loc"], scale=parameters["scale"])
    if family == "laplace":
        return stats.laplace.ppf(probabilities, loc=parameters["loc"], scale=parameters["scale"])
    if family == "student_t":
        return stats.t.ppf(probabilities, parameters["df"], loc=parameters["loc"], scale=parameters["scale"])
    raise ValueError(family)


def _record(checks: list[dict[str, Any]], failures: list[str], name: str, passed: bool, detail: str) -> None:
    status = "PASS" if passed else "FAIL"
    checks.append({"check": name, "status": status, "detail": detail})
    if not passed:
        failures.append(name)


def _finite_interval(row: Mapping[str, Any], lower: str, median: str, upper: str) -> bool:
    values = [parse_float(row.get(key)) for key in (lower, median, upper)]
    return all(value is not None for value in values) and values[0] <= values[1] <= values[2]


def _model_path(root: Path, manifest: Mapping[str, Any]) -> Path:
    relative = str(manifest.get("source", {}).get("prior_namespace", ""))
    default = root / "dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r1"
    return default if not relative else default


def _stage4_result(rows: Sequence[Mapping[str, Any]]) -> str:
    primary = {
        (str(row["scope"]), str(row["scope_id"]), str(row["parameter"])): row
        for row in rows
        if row.get("population") == "STAGE3_WEIGHTED_PRIMARY"
    }
    stage4 = {
        (str(row["scope"]), str(row["scope_id"]), str(row["parameter"])): row
        for row in rows
        if row.get("population") == "STAGE4_STRICT_CONFIRMED"
    }
    comparable = []
    for key, left in primary.items():
        right = stage4.get(key)
        if not right or left.get("comparison_status") != "COMPARABLE" or right.get("comparison_status") != "COMPARABLE":
            continue
        left_median = parse_float(left.get("median"))
        right_median = parse_float(right.get("median"))
        low = parse_float(left.get("median_bootstrap_lower"))
        high = parse_float(left.get("median_bootstrap_upper"))
        if None not in (left_median, right_median, low, high):
            family_same = left.get("selected_family", "") == right.get("selected_family", "")
            comparable.append((low <= right_median <= high, family_same))
    if not comparable:
        return "INCONCLUSIVE"
    interval_rate = sum(item[0] for item in comparable) / len(comparable)
    family_rate = sum(item[1] for item in comparable) / len(comparable)
    if interval_rate >= 0.8 and family_rate >= 0.8:
        return "CONSISTENT"
    if interval_rate >= 0.5 and family_rate >= 0.5:
        return "PARTIALLY_CONSISTENT"
    return "MATERIAL_DIFFERENCE"


def _continuous_result(rows: Sequence[Mapping[str, Any]]) -> str:
    usable = []
    for row in rows:
        if row.get("diagnostic_support_status") == "DATA_SUPPORTED":
            low = parse_float(row.get("slope_bootstrap_lower"))
            high = parse_float(row.get("slope_bootstrap_upper"))
            if low is not None and high is not None:
                usable.append(low > 0.0 or high < 0.0)
    if not usable:
        return "NOT_SUPPORTED"
    if all(usable):
        return "SUPPORTED"
    return "CONDITIONAL"


def audit_model(root: Path, model_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []
    model_manifest_path = model_dir / "model_manifest.json"
    manifest: dict[str, Any] = {}
    if model_manifest_path.is_file():
        try:
            manifest = read_json(model_manifest_path)
        except Exception as exc:  # pragma: no cover - malformed artifact path
            failures.append("model_manifest_json")
            checks.append({"check": "model_manifest_json", "status": "FAIL", "detail": str(exc)})
    else:
        failures.append("model_manifest_exists")
        checks.append({"check": "model_manifest_exists", "status": "FAIL", "detail": str(model_manifest_path)})

    relative_model = model_dir.resolve().relative_to(root.resolve()) if model_dir.resolve().is_relative_to(root.resolve()) else Path("..").joinpath(model_dir.name)
    _record(checks, failures, "new_namespace_safe", relative_model.parts[:2] == ("dataset_generation_logs", "channel_modeling") and not any(part.lower() in {"scenes", "sage_results"} for part in relative_model.parts), str(relative_model))
    missing = [name for name in REQUIRED_MODEL_FILES if not (model_dir / name).is_file()]
    _record(checks, failures, "required_model_files", not missing, f"missing={missing}")

    manifest_source = manifest.get("source", {})
    prior_namespace = root / "dataset_generation_logs/channel_modeling/stage3_statistical_unit_track_reassessment_20260829_r1"
    prior_manifest_path = prior_namespace / "audit_manifest.json"
    prior_manifest: dict[str, Any] = read_json(prior_manifest_path) if prior_manifest_path.is_file() else {}
    _record(checks, failures, "model_identity", manifest.get("model_id") == MODEL_ID, str(manifest.get("model_id")))
    _record(checks, failures, "execution_boundary", manifest.get("execution_policy") == {"batch": False, "matlab": False, "new_only": True, "process_20_46_mhz": False, "raw_iq_read": False, "resume_allowed": False, "sage": False}, json.dumps(manifest.get("execution_policy", {}), sort_keys=True))
    _record(checks, failures, "model_population_contract", manifest.get("population", {}).get("academic_stage3_observations") == 783 and manifest.get("population", {}).get("algorithm_tracks") == 366 and manifest.get("population", {}).get("elevation_ready_observations") == 716, json.dumps(manifest.get("population", {}), sort_keys=True))
    _record(checks, failures, "prior_manifest_qa_pass", prior_manifest.get("qa_status") == "PASS", str(prior_manifest.get("qa_status")))

    paths = source_paths(root)
    source_hashes: dict[str, str] = {}
    if paths["sage_runs"].is_file():
        try:
            source_hashes = current_source_hashes(root, paths)
            expected_hashes = prior_manifest.get("source_artifacts_after_sha256", {})
            _record(checks, failures, "source_artifacts_frozen", set(source_hashes) == set(expected_hashes) and all(source_hashes.get(key) == value for key, value in expected_hashes.items()), f"current={len(source_hashes)} expected={len(expected_hashes)}")
        except Exception as exc:
            _record(checks, failures, "source_artifacts_frozen", False, str(exc))
    else:
        _record(checks, failures, "source_artifacts_frozen", False, "sage_runs.csv is missing")
    prior_output_expected = prior_manifest.get("output_sha256", {})
    prior_output_actual = {name: sha256_file(prior_namespace / name) for name in prior_output_expected if (prior_namespace / name).is_file()}
    _record(checks, failures, "prior_stage3_output_frozen", prior_output_actual == prior_output_expected, f"current={len(prior_output_actual)} expected={len(prior_output_expected)}")
    if prior_manifest_path.is_file():
        _record(checks, failures, "prior_manifest_hash", manifest_source.get("prior_manifest_sha256") == sha256_file(prior_manifest_path), str(manifest_source.get("prior_manifest_sha256")))

    ingestion_manifest = read_json(paths["ingestion_manifest"]) if paths["ingestion_manifest"].is_file() else {}
    frozen_expected = ingestion_manifest.get("frozen_source_hashes", {})
    frozen_actual = {}
    frozen_matches = {}
    frozen_path_by_key = {
        "pipeline_sha256": paths["pipeline"],
        "wrapper_sha256": paths["wrapper"],
        "executor_sha256": paths["executor"],
        "manifest_sha256": paths["production_manifest"],
        "inventory_sha256": paths["production_inventory"],
    }
    for key, path in frozen_path_by_key.items():
        value = sha256_file(path) if path.is_file() else ""
        frozen_actual[key] = value
        frozen_matches[key] = bool(value) and value == frozen_expected.get(key, "")
    frozen_ok = bool(frozen_expected) and all(frozen_matches.values())
    _record(checks, failures, "production_source_wrapper_executor_hashes_frozen", frozen_ok, json.dumps({"actual": frozen_actual, "expected": frozen_expected}, sort_keys=True))
    recorded_frozen = manifest.get("frozen_hash_status", {})
    _record(checks, failures, "manifest_frozen_hash_record_matches", recorded_frozen.get("actual") == frozen_actual and recorded_frozen.get("expected") == frozen_expected and recorded_frozen.get("all_match") == frozen_ok, "recorded model manifest frozen status")
    stage4_path = root / STAGE4_PARAMETER_REL
    stage4_hash = sha256_file(stage4_path) if stage4_path.is_file() else ""
    _record(checks, failures, "stage4_source_hash_recorded", stage4_hash and manifest_source.get("stage4_source_sha256") == stage4_hash, stage4_hash)

    population_rows = read_csv_rows(model_dir / "source_population_audit.csv") if (model_dir / "source_population_audit.csv").is_file() else []
    ids = [row.get("stage3_path_id", "") for row in population_rows]
    _record(checks, failures, "population_row_count_and_unique_ids", len(population_rows) == 783 and len(set(ids)) == 783 and all(ids), f"rows={len(population_rows)} unique={len(set(ids))}")
    _record(checks, failures, "population_eligibility_flags", all(parse_bool(row.get("academic_eligible")) and parse_bool(row.get("persistence_pass")) for row in population_rows), "academic and persistence flags")
    track_sizes: dict[str, int] = {}
    bad_rows = []
    for row in population_rows:
        track = str(row.get("track_id", "")).strip()
        size = parse_float(row.get("track_observation_count"))
        weight = parse_float(row.get("track_weight"))
        if not track or size is None or size <= 0 or int(size) != size or weight is None or abs(weight - 1.0 / int(size)) > 1e-10:
            bad_rows.append(row.get("stage3_path_id", ""))
        else:
            track_sizes[track] = int(size)
    _record(checks, failures, "reciprocal_track_weight_contract", not bad_rows and track_weights_conserve(population_rows), f"bad_rows={len(bad_rows)} tracks={len(track_sizes)}")
    actual_track_counts: dict[str, int] = defaultdict(int)
    for row in population_rows:
        actual_track_counts[str(row.get("track_id", ""))] += 1
    _record(checks, failures, "track_sizes_match_population", set(actual_track_counts) == set(track_sizes) and all(actual_track_counts[key] == track_sizes[key] for key in track_sizes), f"tracks={len(actual_track_counts)}")
    track_population_path = prior_namespace / "track_population.csv"
    prior_track_rows = read_csv_rows(track_population_path) if track_population_path.is_file() else []
    _record(checks, failures, "algorithm_track_population_count", len(prior_track_rows) == 366 and len(actual_track_counts) == 366, f"prior_track_rows={len(prior_track_rows)} source_tracks={len(actual_track_counts)}")
    elevations_ready = 0
    elevation_bad = []
    for row in population_rows:
        if parse_bool(row.get("elevation_ready")):
            elevations_ready += 1
            elevation = parse_float(row.get("elevation_deg"))
            band = str(row.get("elevation_band", "")).strip()
            expected_band = "LOW" if elevation is not None and elevation < 30.0 else "MID" if elevation is not None and elevation < 60.0 else "HIGH" if elevation is not None and elevation <= 90.0 else ""
            if expected_band != band:
                elevation_bad.append(row.get("stage3_path_id", ""))
    _record(checks, failures, "elevation_ready_count_and_frozen_bins", elevations_ready == 716 and not elevation_bad, f"ready={elevations_ready} bad_bins={len(elevation_bad)}")

    support_rows = read_csv_rows(model_dir / "cell_support_matrix.csv") if (model_dir / "cell_support_matrix.csv").is_file() else []
    cells = expected_cell_keys()
    support_keys = {(row.get("scope_id", ""), row.get("parameter", "")) for row in support_rows}
    _record(checks, failures, "cell_support_matrix_complete", len(support_rows) == 36 and support_keys == {(cell, parameter) for cell in cells for parameter in PARAMETERS}, f"rows={len(support_rows)}")
    support_by_cell: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in support_rows:
        support_by_cell[str(row.get("scope_id", ""))].append(row)
    direct_cells = {cell for cell in cells if any((parse_float(row.get("observation_count")) or 0.0) > 0.0 for row in support_by_cell[cell])}
    empty_rows = support_by_cell["Highway/Open__LOW"]
    empty_ok = len(empty_rows) == 3 and all((parse_float(row.get("observation_count")) or 0.0) == 0.0 and (parse_float(row.get("sum_weights")) or 0.0) == 0.0 for row in empty_rows)
    _record(checks, failures, "eleven_direct_cells_and_no_synthetic_empty_cell", len(direct_cells) == 11 and empty_ok, f"direct_cells={len(direct_cells)} empty_cell_ok={empty_ok}")

    model_rows = read_csv_rows(model_dir / "selected_marginal_models.csv") if (model_dir / "selected_marginal_models.csv").is_file() else []
    model_keys = {(row.get("scope", ""), row.get("scope_id", ""), row.get("parameter", "")) for row in model_rows}
    expected_model_keys = {(scope, scope_id, parameter) for scope, scope_id, _, _ in scope_keys() for parameter in PARAMETERS}
    _record(checks, failures, "hierarchical_model_layers_complete", len(model_rows) == 51 and model_keys == expected_model_keys, f"rows={len(model_rows)}")
    selected_global = manifest.get("selected_global_families", {})
    model_family_failures = []
    normalization_failures = []
    model_support_failures = []
    for row in model_rows:
        parameter = str(row.get("parameter", ""))
        family = str(row.get("family", ""))
        if family not in set(sum(CANDIDATE_FAMILIES.values(), ())):
            model_family_failures.append(row.get("scope_id", ""))
            continue
        try:
            parameters = {key: float(value) for key, value in json.loads(row.get("fit_parameters_json", "{}")).items()}
            probabilities = np.asarray([0.025, 0.5, 0.975], dtype=float)
            quantiles = _family_ppf(family, parameters, probabilities)
            cdf_error = float(np.max(np.abs(_family_cdf(family, parameters, quantiles) - probabilities)))
            stored = np.asarray([float(row.get("model_q025")), float(row.get("model_q050")), float(row.get("model_q975"))])
            if not np.all(np.isfinite(quantiles)) or cdf_error > 1e-8 or not np.allclose(quantiles, stored, atol=1e-7, rtol=1e-7):
                normalization_failures.append(row.get("scope_id", ""))
            if parameter == "excess_delay_samples" and not np.all(quantiles > 0.0):
                normalization_failures.append(row.get("scope_id", ""))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            normalization_failures.append(row.get("scope_id", ""))
        if row.get("scope") == "global" and family != selected_global.get(parameter):
            model_family_failures.append(row.get("scope_id", ""))
        if row.get("scope") == "cell" and row.get("scope_id") == "Highway/Open__LOW" and (parse_float(row.get("direct_observation_count")) or 0.0) != 0.0:
            model_support_failures.append(row.get("scope_id", ""))
        if row.get("scope") == "cell" and row.get("scope_id") == "Highway/Open__LOW" and row.get("support_status") != "NO_DIRECT_SUPPORT":
            model_support_failures.append(row.get("scope_id", ""))
    _record(checks, failures, "stored_family_contract_and_normalization", not model_family_failures and not normalization_failures, f"family_failures={len(model_family_failures)} normalization_failures={len(normalization_failures)}")
    _record(checks, failures, "empty_cell_model_is_parent_only", not model_support_failures, f"failures={model_support_failures}")
    layer_counts = {name: len(read_csv_rows(model_dir / name)) if (model_dir / name).is_file() else 0 for name in ("global_models.csv", "environment_models.csv", "environment_elevation_models.csv")}
    _record(checks, failures, "hierarchical_layer_file_counts", layer_counts == {"global_models.csv": 3, "environment_models.csv": 12, "environment_elevation_models.csv": 36}, str(layer_counts))

    candidate_rows = read_csv_rows(model_dir / "candidate_family_scores.csv") if (model_dir / "candidate_family_scores.csv").is_file() else []
    _record(checks, failures, "candidate_family_scores_complete", len(candidate_rows) == 459 and {row.get("policy") for row in candidate_rows} == POLICIES, f"rows={len(candidate_rows)} policies={sorted({row.get('policy') for row in candidate_rows})}")
    grouped_failures = []
    selected_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for row in candidate_rows:
        key = (str(row.get("policy", "")), str(row.get("scope", "")), str(row.get("scope_id", "")), str(row.get("parameter", "")))
        if parse_bool(row.get("selected_for_scope")):
            selected_counts[key] += 1
        if parse_bool(row.get("row_random_split_used")):
            grouped_failures.append("row_random_split")
        if parse_bool(row.get("valid")):
            held_out = parse_float(row.get("held_out_scene_count"))
            scenes = parse_float(row.get("scene_count"))
            held_ll = parse_float(row.get("weighted_held_out_mean_log_likelihood"))
            if held_out is None or scenes is None or held_out != scenes or held_ll is None:
                grouped_failures.append(key)
    _record(checks, failures, "grouped_family_selection_no_row_split", not grouped_failures and all(value <= 1 for value in selected_counts.values()), f"failures={len(grouped_failures)}")

    joint_rows = read_csv_rows(model_dir / "joint_dependence_models.csv") if (model_dir / "joint_dependence_models.csv").is_file() else []
    joint_failures = []
    for row in joint_rows:
        matrix = [[parse_float(row.get(f"corr__{left}__{right}")) for right in PARAMETERS] for left in PARAMETERS]
        if any(value is None for values in matrix for value in values) or not is_near_psd_correlation(matrix):
            joint_failures.append(row.get("scope_id", ""))
        if row.get("scope_id") == "Highway/Open__LOW" and row.get("dependence_status") != "NO_DIRECT_SUPPORT":
            joint_failures.append(row.get("scope_id", ""))
    _record(checks, failures, "joint_dependence_psd_and_gate", len(joint_rows) == 17 and not joint_failures, f"rows={len(joint_rows)} failures={len(joint_failures)}")

    bootstrap_checks = []
    for filename, block_unit, seed_key in (("scene_block_bootstrap.csv", "scene_id", "scene_block_seed"), ("run_block_sensitivity.csv", "run_id", "run_block_seed")):
        rows = read_csv_rows(model_dir / filename) if (model_dir / filename).is_file() else []
        seed = manifest.get("uncertainty", {}).get(seed_key)
        bad = []
        for row in rows:
            if row.get("block_unit") != block_unit or parse_float(row.get("seed")) != parse_float(seed):
                bad.append("contract")
            if row.get("status") == "PASS":
                if parse_float(row.get("replicate_count")) != BOOTSTRAP_REPLICATES or not _finite_interval(row, "lower_2_5", "median_50", "upper_97_5"):
                    bad.append("pass_row")
            elif row.get("status") not in {"NO_DIRECT_SUPPORT", "INSUFFICIENT_BLOCKS", "FIT_FAILURE"}:
                bad.append("unknown_status")
            if row.get("status") == "FIT_FAILURE":
                bad.append("fit_failure")
        bootstrap_checks.append((filename, len(rows), bad))
    _record(checks, failures, "block_bootstrap_contract", all(count > 0 and not bad for _, count, bad in bootstrap_checks), str(bootstrap_checks))

    stage4_rows = read_csv_rows(model_dir / "stage3_stage4_sensitivity.csv") if (model_dir / "stage3_stage4_sensitivity.csv").is_file() else []
    expected_sensitivity_keys = {(population, scope, scope_id, parameter) for population in ("STAGE3_WEIGHTED_PRIMARY", "STAGE4_STRICT_CONFIRMED") for scope, scope_id, _, _ in scope_keys() for parameter in PARAMETERS}
    sensitivity_keys = {(row.get("population", ""), row.get("scope", ""), row.get("scope_id", ""), row.get("parameter", "")) for row in stage4_rows}
    _record(checks, failures, "stage3_stage4_sensitivity_complete", len(stage4_rows) == 102 and sensitivity_keys == expected_sensitivity_keys, f"rows={len(stage4_rows)}")
    cdf_rows = read_csv_rows(model_dir / "stage3_stage4_cdf_comparison.csv") if (model_dir / "stage3_stage4_cdf_comparison.csv").is_file() else []
    cdf_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    cdf_bad = []
    for row in cdf_rows:
        key = (str(row.get("scope", "")), str(row.get("scope_id", "")), str(row.get("parameter", "")))
        cdf_groups[key].append(row)
        if row.get("comparison_status") == "COMPARABLE":
            if parse_float(row.get("grid_index")) is None or parse_float(row.get("grid_value")) is None or any(parse_float(row.get(field)) is None or not 0.0 <= float(row[field]) <= 1.0 for field in ("stage3_weighted_cdf", "stage4_strict_confirmed_cdf")):
                cdf_bad.append(key)
    cdf_shape_ok = True
    for scope, scope_id, _, _ in scope_keys():
        for parameter in PARAMETERS:
            group = cdf_groups[(scope, scope_id, parameter)]
            comparable = any(row.get("comparison_status") == "COMPARABLE" for row in group)
            if comparable and len(group) != 41:
                cdf_shape_ok = False
            if not comparable and len(group) != 1:
                cdf_shape_ok = False
    _record(checks, failures, "stage3_stage4_cdf_contract", cdf_shape_ok and not cdf_bad, f"rows={len(cdf_rows)} bad={len(cdf_bad)}")
    _record(checks, failures, "stage4_is_sensitivity_only", manifest.get("source", {}).get("stage4_parameter_source") == str(STAGE4_PARAMETER_REL) and manifest.get("execution_policy", {}).get("process_20_46_mhz") is False, str(manifest.get("source", {}).get("stage4_parameter_source")))

    continuous_rows = read_csv_rows(model_dir / "continuous_elevation_diagnostics.csv") if (model_dir / "continuous_elevation_diagnostics.csv").is_file() else []
    continuous_bad = [row.get("environment_class", "") for row in continuous_rows if row.get("continuous_elevation_v2_status") not in {"SUPPORTED", "CONDITIONAL", "NOT_SUPPORTED"}]
    _record(checks, failures, "continuous_elevation_diagnostics_complete", len(continuous_rows) == 12 and not continuous_bad, f"rows={len(continuous_rows)} bad={len(continuous_bad)}")
    derived_rows = read_csv_rows(model_dir / "derived_channel_statistics.csv") if (model_dir / "derived_channel_statistics.csv").is_file() else []
    ricean_rows = [row for row in derived_rows if row.get("statistic") == "ricean_k_factor"]
    _record(checks, failures, "ricean_k_not_identifiable", len(ricean_rows) == 1 and ricean_rows[0].get("status") == "NOT_IDENTIFIABLE" and ricean_rows[0].get("identifiability") == "NO", str(ricean_rows[:1]))
    persistence_rows = read_csv_rows(model_dir / "persistence_duration_statistics.csv") if (model_dir / "persistence_duration_statistics.csv").is_file() else []
    persistence_ok = bool(persistence_rows) and all("not physical" in str(row.get("interpretation", "")).lower() for row in persistence_rows)
    _record(checks, failures, "persistence_not_physical_lifetime", persistence_ok, f"rows={len(persistence_rows)}")

    receipt_path = model_dir / "build_receipt.json"
    receipt = read_json(receipt_path) if receipt_path.is_file() else {}
    manifest_hash = sha256_file(model_manifest_path) if model_manifest_path.is_file() else ""
    _record(checks, failures, "build_receipt_completed_and_manifest_bound", receipt.get("status") == "COMPLETED" and receipt.get("model_manifest_sha256") == manifest_hash, str(receipt.get("status")))
    builder_files = set(REQUIRED_MODEL_FILES) - {"build_receipt.json"}
    actual_builder_files = {path.name for path in model_dir.iterdir() if path.is_file() and path.name not in QA_FILES and path.name != "build_receipt.json"}
    manifest_hashes = manifest.get("output_hashes_excluding_manifest_and_receipt", {})
    manifest_hash_ok = actual_builder_files - {"model_manifest.json"} == set(manifest_hashes) and all(sha256_file(model_dir / name) == value for name, value in manifest_hashes.items())
    _record(checks, failures, "model_manifest_output_hashes", manifest_hash_ok, f"actual={len(actual_builder_files)} manifest={len(manifest_hashes)}")
    receipt_hashes = receipt.get("output_hashes_excluding_receipt", {})
    receipt_files_ok = set(receipt.get("output_files", [])) == actual_builder_files | {"model_manifest.json"} and set(receipt_hashes) == actual_builder_files | {"model_manifest.json"} and all(sha256_file(model_dir / name) == value for name, value in receipt_hashes.items())
    _record(checks, failures, "build_receipt_output_hashes", receipt_files_ok, f"receipt_files={len(receipt.get('output_files', []))}")
    report_path = root / str(manifest.get("report_path", "")) if str(manifest.get("report_path", "")).strip() else root / "docs/ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_REPORT.md"
    report_ok = report_path.is_file() and (not manifest.get("report_sha256") or sha256_file(report_path) == manifest.get("report_sha256"))
    _record(checks, failures, "main_report_hash", report_ok, str(report_path))

    stage4_status = _stage4_result(stage4_rows)
    continuous_status = _continuous_result(continuous_rows)
    qa_status = "PASS" if not failures else "FAIL"
    model_status = "PASS_WITH_LIMITATIONS" if qa_status == "PASS" else "FAIL"
    final_block = {
        "ACADEMIC_MODELING_POPULATION_V2": "APPLIED",
        "PRIMARY_STATISTICAL_UNIT": "WEIGHTED_OBSERVATION",
        "ENV_ELEV_STAGE3_MODEL_V1": model_status,
        "CURRENT_10MHZ_STAGE3_MODEL": "ADEQUATE_WITH_LIMITATIONS" if qa_status == "PASS" else "INSUFFICIENT",
        "STAGE4_SENSITIVITY_RESULT": stage4_status,
        "CONTINUOUS_ELEVATION_V2": continuous_status,
        "PROCESS_20_46_MHZ_NEXT": "CONDITIONAL",
        "NEW_DATA_COLLECTION_REQUIRED": "CONDITIONAL" if qa_status == "PASS" else "YES",
    }
    result = {
        "qa_version": "environment-elevation-stage3-model-independent-qa-v1",
        "model_id": manifest.get("model_id", MODEL_ID),
        "model_namespace": str(model_dir),
        "qa_status": qa_status,
        "failure_checks": failures,
        "warning_checks": warnings,
        "check_count": len(checks),
        "checks": checks,
        "recomputed": {
            "stage4_sensitivity_result": stage4_status,
            "continuous_elevation_v2": continuous_status,
            "frozen_hashes": {"actual": frozen_actual, "expected": frozen_expected, "all_match": frozen_ok},
        },
        "final_decision_block": final_block,
    }
    qa_result_path = model_dir / "independent_qa_result.json"
    qa_report_path = model_dir / "independent_qa_report.md"
    qa_result_path.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    passed_count = sum(1 for check in checks if check["status"] == "PASS")
    failed_count = len(failures)
    report_lines = [
        "# Independent QA — Environment × Elevation Stage3 Academic Path Model V1",
        "",
        f"- Namespace: `{model_dir}`",
        f"- QA status: **{qa_status}** ({passed_count} checks passed, {failed_count} failed)",
        "- Auditor independence: this script does not import the Stage3 model builder or its fitting/selection functions.",
        "- Scope: generated artifacts, frozen provenance, weighted observation contract, grouped family selection, hierarchical model normalization, dependence PSD, block bootstrap, Stage4 sensitivity, continuous diagnostics, and identifiability boundaries.",
        "",
        "## Check summary",
        "",
        "| Status | Check | Detail |",
        "|---|---|---|",
    ]
    for check in checks:
        detail = str(check["detail"]).replace("|", "\\|").replace("\n", " ")
        report_lines.append(f"| {check['status']} | `{check['check']}` | {detail} |")
    report_lines.extend(
        [
            "",
            "## Independent conclusions",
            "",
            f"- Stage4 sensitivity result: `{stage4_status}`. This is a validation comparison only; Stage4 does not select or tune the Stage3 model.",
            f"- Continuous elevation V2 result: `{continuous_status}`. LOW/MID/HIGH remains the formal model interface.",
            "- Ricean K-factor: scientifically not identifiable from this Stage3 population because no defensible physical main/reference power-and-phase definition is present.",
            "- Persistence duration is algorithm-observed track persistence, not physical reflector lifetime.",
            "",
            "## Commander decision block",
            "",
            "```text",
            "ACADEMIC_MODELING_POPULATION_V2 = APPLIED",
            "PRIMARY_STATISTICAL_UNIT = WEIGHTED_OBSERVATION",
            f"ENV_ELEV_STAGE3_MODEL_V1 = {final_block['ENV_ELEV_STAGE3_MODEL_V1']}",
            f"CURRENT_10MHZ_STAGE3_MODEL = {final_block['CURRENT_10MHZ_STAGE3_MODEL']}",
            f"STAGE4_SENSITIVITY_RESULT = {final_block['STAGE4_SENSITIVITY_RESULT']}",
            f"CONTINUOUS_ELEVATION_V2 = {final_block['CONTINUOUS_ELEVATION_V2']}",
            f"PROCESS_20_46_MHZ_NEXT = {final_block['PROCESS_20_46_MHZ_NEXT']}",
            f"NEW_DATA_COLLECTION_REQUIRED = {final_block['NEW_DATA_COLLECTION_REQUIRED']}",
            "```",
            "",
            "No MATLAB/SAGE process was started, stopped, resumed, or inspected by this auditor. No raw IQ or 20.46 MHz data were read.",
            "",
        ]
    )
    qa_report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = (args.output or root / "dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r1").resolve()
    result = audit_model(root, output)
    print(json.dumps({"qa_status": result["qa_status"], "failure_checks": result["failure_checks"], "check_count": result["check_count"], "stage4_sensitivity_result": result["recomputed"]["stage4_sensitivity_result"], "continuous_elevation_v2": result["recomputed"]["continuous_elevation_v2"]}, indent=2, sort_keys=True))
    print(f"INDEPENDENT_QA={result['qa_status']}")
    return 0 if result["qa_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
