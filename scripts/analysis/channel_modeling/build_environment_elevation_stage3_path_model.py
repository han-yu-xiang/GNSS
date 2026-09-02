#!/usr/bin/env python3
"""Build the Stage3 Environment × Elevation academic path model v1.

The builder is an offline, new-only analysis layer.  It consumes the already
QA-approved Stage3 statistical-unit tables and the existing Stage4 confirmed
path-parameter table only for a separated sensitivity comparison.  It does not
open raw IQ, invoke MATLAB/SAGE/batch, recompute Stage3 tracks, or modify an
existing scientific namespace.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import stats

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.analysis.channel_modeling.audit_stage3_academic_population import (  # noqa: E402
    collect_source_artifacts,
    frozen_hash_status,
    is_true,
    read_csv_rows,
    source_paths,
)
from scripts.analysis.channel_modeling.path_distribution_core import (  # noqa: E402
    _family_logpdf,
    cdf,
    fit_family,
    nearest_correlation,
    ppf,
)


MODEL_ID = "environment_elevation_stage3_academic_path_model_v1"
MODEL_VERSION = "stage3-weighted-observation-v1"
PRIOR_NAMESPACE_REL = Path(
    "dataset_generation_logs/channel_modeling/"
    "stage3_statistical_unit_track_reassessment_20260829_r1"
)
OUTPUT_NAMESPACE_REL = Path(
    "dataset_generation_logs/channel_modeling/"
    "environment_elevation_stage3_path_model_v1_20260829_r1"
)
REPORT_REL = Path("docs/ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_REPORT.md")
STAGE4_PARAMETER_REL = Path(
    "dataset/multipath_event_database/v1/partitions/"
    "parameter_set_id=parameters_20260825_stage4_path_v1/facts/path_parameters.csv"
)

ENVIRONMENTS = ("Urban", "Special Reflective", "Mountain/Valley", "Highway/Open")
ELEVATION_BANDS = ("LOW", "MID", "HIGH")
PARAMETERS = (
    "excess_delay_samples",
    "doppler_offset_hz",
    "relative_power_db",
)
CANDIDATE_FAMILIES = {
    "excess_delay_samples": ("lognormal", "gamma", "weibull"),
    "doppler_offset_hz": ("normal", "laplace", "student_t"),
    "relative_power_db": ("normal", "laplace", "student_t"),
}

PRIMARY_POLICY = "C_WEIGHTED_OBSERVATION"
RAW_POLICY = "A_RAW_OBSERVATION"
TRACK_POLICY = "B_ALGORITHM_TRACK_MEDIAN"

PARENT_QUANTILE_COUNT = 64
PARENT_EQUIVALENT_WEIGHT = 8.0
COPULA_EIGENVALUE_FLOOR = 1e-6
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 2026082901
RUN_BOOTSTRAP_SEED = 2026082902
STAGE4_BOOTSTRAP_SEED = 2026082903
CONTINUOUS_BOOTSTRAP_SEED = 2026082904
FAMILY_TIE_TOLERANCE = 1e-9
SUPPORT_MIN_ROWS = 10
SUPPORT_MIN_SCENES = 3
SUPPORT_MIN_KISH = 10.0

MODEL_FIELDS = [
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "parameter",
    "family",
    "fit_parameters_json",
    "fit_objective",
    "weighted_in_sample_log_likelihood",
    "support_status",
    "parameter_source",
    "direct_observation_count",
    "sum_weights",
    "kish_effective_sample_size",
    "track_count",
    "run_count",
    "scene_count",
    "prn_count",
    "parent_scope",
    "model_q025",
    "model_q050",
    "model_q975",
]

SCORE_FIELDS = [
    "policy",
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "parameter",
    "candidate_family",
    "selected_for_scope",
    "selection_status",
    "valid",
    "failure",
    "row_count",
    "sum_weights",
    "kish_effective_sample_size",
    "scene_count",
    "run_count",
    "weighted_in_sample_log_likelihood",
    "weighted_held_out_log_likelihood",
    "held_out_weight",
    "weighted_held_out_mean_log_likelihood",
    "held_out_scene_count",
    "held_out_scenes",
    "aic",
    "aicc",
    "bic",
    "parameter_count",
    "row_random_split_used",
]

SUMMARY_FIELDS = [
    "policy",
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "parameter",
    "observation_count",
    "sum_weights",
    "kish_effective_sample_size",
    "track_count",
    "run_count",
    "scene_count",
    "prn_count",
    "mean",
    "median",
    "q025",
    "q25",
    "q75",
    "q975",
    "std",
    "selected_family",
    "family_selection_status",
]

COPULA_FIELDS = [
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "dependence_status",
    "copula_source",
    "observation_count",
    "sum_weights",
    "kish_effective_sample_size",
    "track_count",
    "run_count",
    "scene_count",
    "prn_count",
    "min_eigenvalue",
    "eigenvalue_floor",
    "rank_method",
    "corr__excess_delay_samples__excess_delay_samples",
    "corr__excess_delay_samples__doppler_offset_hz",
    "corr__excess_delay_samples__relative_power_db",
    "corr__doppler_offset_hz__excess_delay_samples",
    "corr__doppler_offset_hz__doppler_offset_hz",
    "corr__doppler_offset_hz__relative_power_db",
    "corr__relative_power_db__excess_delay_samples",
    "corr__relative_power_db__doppler_offset_hz",
    "corr__relative_power_db__relative_power_db",
]

BOOTSTRAP_FIELDS = [
    "block_unit",
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "parameter",
    "metric",
    "lower_2_5",
    "median_50",
    "upper_97_5",
    "replicate_count",
    "seed",
    "status",
]

CONTINUOUS_FIELDS = [
    "environment_class",
    "parameter",
    "observation_count",
    "sum_weights",
    "kish_effective_sample_size",
    "scene_count",
    "run_count",
    "prn_count",
    "elevation_min_deg",
    "elevation_max_deg",
    "elevation_range_deg",
    "weighted_spearman_rho",
    "weighted_slope",
    "weighted_intercept",
    "weighted_r2",
    "weighted_rmse",
    "slope_bootstrap_lower",
    "slope_bootstrap_median",
    "slope_bootstrap_upper",
    "diagnostic_support_status",
    "continuous_elevation_v2_status",
]

STAGE4_SENSITIVITY_FIELDS = [
    "population",
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "parameter",
    "observation_count",
    "sum_weights",
    "kish_effective_sample_size",
    "track_count",
    "run_count",
    "scene_count",
    "mean",
    "median",
    "q025",
    "q25",
    "q75",
    "q975",
    "selected_family",
    "family_selection_status",
    "median_bootstrap_lower",
    "median_bootstrap_median",
    "median_bootstrap_upper",
    "comparison_status",
]

CDF_FIELDS = [
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "parameter",
    "grid_index",
    "grid_value",
    "stage3_weighted_cdf",
    "stage4_strict_confirmed_cdf",
    "stage3_family",
    "stage4_family",
    "comparison_status",
]

DERIVED_FIELDS = [
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "statistic",
    "unit",
    "observation_or_center_count",
    "mean",
    "median",
    "q25",
    "q75",
    "min",
    "max",
    "std",
    "identifiability",
    "status",
    "interpretation",
]

PERSISTENCE_FIELDS = [
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "track_count",
    "mean_duration_s",
    "median_duration_s",
    "q25_duration_s",
    "q75_duration_s",
    "min_duration_s",
    "max_duration_s",
    "mean_window_span",
    "median_window_span",
    "status",
    "interpretation",
]


@dataclass(frozen=True)
class Stage3Input:
    root: Path
    nodes: tuple[dict[str, Any], ...]
    tracks: tuple[dict[str, Any], ...]
    stage4_rows: tuple[dict[str, Any], ...]
    prior_manifest: Mapping[str, Any]
    prior_manifest_sha256: str
    source_hashes: Mapping[str, str]
    source_expected_hashes: Mapping[str, str]
    source_hashes_match: bool
    prior_output_hashes_match: bool
    frozen_hash_status: Mapping[str, Any]
    stage4_source_sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fmt(value: float | int | None) -> str:
    if value is None:
        return ""
    number = float(value)
    if not math.isfinite(number):
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:.9f}".rstrip("0").rstrip(".")


def parse_num(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def elevation_band_for_stage3(elevation_deg: float) -> str:
    if not math.isfinite(elevation_deg) or elevation_deg < 0.0 or elevation_deg > 90.0:
        raise ValueError(f"elevation outside [0,90]: {elevation_deg}")
    if elevation_deg < 30.0:
        return "LOW"
    if elevation_deg < 60.0:
        return "MID"
    return "HIGH"


def weight_for_track_size(track_size: int | float) -> float:
    size = int(track_size)
    if size <= 0:
        raise ValueError("algorithm track size must be positive")
    return 1.0 / size


def weighted_quantile(values: Sequence[float], weights: Sequence[float], probability: float) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0,1]")
    values_array = np.asarray(values, dtype=float)
    weights_array = np.asarray(weights, dtype=float)
    if values_array.size == 0 or values_array.size != weights_array.size:
        raise ValueError("values and weights must be non-empty and equal length")
    if not np.all(np.isfinite(values_array)) or not np.all(np.isfinite(weights_array)) or np.any(weights_array <= 0.0):
        raise ValueError("values/weights must be finite and weights positive")
    order = np.argsort(values_array, kind="mergesort")
    ordered_values = values_array[order]
    ordered_weights = weights_array[order]
    target = probability * float(np.sum(ordered_weights))
    index = int(np.searchsorted(np.cumsum(ordered_weights), target, side="left"))
    return float(ordered_values[min(index, len(ordered_values) - 1)])


def weighted_summary(values: Sequence[float], weights: Sequence[float]) -> dict[str, float | int | None]:
    values_array = np.asarray(values, dtype=float)
    weights_array = np.asarray(weights, dtype=float)
    if values_array.size != weights_array.size:
        raise ValueError("values and weights have different lengths")
    if values_array.size == 0:
        return {
            "count": 0,
            "sum_weights": 0.0,
            "kish_effective_n": None,
            "mean": None,
            "median": None,
            "q025": None,
            "q25": None,
            "q75": None,
            "q975": None,
            "std": None,
        }
    if not np.all(np.isfinite(values_array)) or not np.all(np.isfinite(weights_array)) or np.any(weights_array <= 0.0):
        raise ValueError("values/weights must be finite and weights positive")
    total = float(np.sum(weights_array))
    kish = total * total / float(np.sum(weights_array * weights_array))
    average = float(np.sum(values_array * weights_array) / total)
    variance = float(np.sum(weights_array * (values_array - average) ** 2) / total)
    return {
        "count": int(values_array.size),
        "sum_weights": total,
        "kish_effective_n": kish,
        "mean": average,
        "median": weighted_quantile(values_array, weights_array, 0.5),
        "q025": weighted_quantile(values_array, weights_array, 0.025),
        "q25": weighted_quantile(values_array, weights_array, 0.25),
        "q75": weighted_quantile(values_array, weights_array, 0.75),
        "q975": weighted_quantile(values_array, weights_array, 0.975),
        "std": math.sqrt(max(variance, 0.0)),
    }


def weighted_rank(values: Sequence[float], weights: Sequence[float]) -> np.ndarray:
    """Return weighted mid-ranks normalized to (0,1)."""

    values_array = np.asarray(values, dtype=float)
    weights_array = np.asarray(weights, dtype=float)
    if values_array.size != weights_array.size or values_array.size == 0:
        raise ValueError("values and weights must be non-empty and equal length")
    if not np.all(np.isfinite(values_array)) or not np.all(np.isfinite(weights_array)) or np.any(weights_array <= 0.0):
        raise ValueError("values/weights must be finite and weights positive")
    order = np.argsort(values_array, kind="mergesort")
    ranks = np.empty(values_array.size, dtype=float)
    total = float(np.sum(weights_array))
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values_array[order[end]] == values_array[order[cursor]]:
            end += 1
        group = order[cursor:end]
        group_weight = float(np.sum(weights_array[group]))
        before = float(np.sum(weights_array[order[:cursor]]))
        ranks[group] = (before + 0.5 * group_weight) / total
        cursor = end
    return ranks


def support_label(path_count: int, scene_count: int, kish_effective_n: float) -> str:
    if path_count <= 0:
        return "NO_DIRECT_SUPPORT"
    if scene_count < 2 or kish_effective_n < 3.0:
        return "PRIOR_DOMINANT"
    if path_count < SUPPORT_MIN_ROWS or scene_count < SUPPORT_MIN_SCENES or kish_effective_n < SUPPORT_MIN_KISH:
        return "SPARSE_PARTIAL_POOLING"
    return "DATA_SUPPORTED"


def family_parameter_count(family: str) -> int:
    return 3 if family == "student_t" else 2


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _scope_stats(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    weights = [float(row["weight"]) for row in rows]
    scenes = {str(row["scene_id"]) for row in rows}
    runs = {str(row["run_id"]) for row in rows}
    prns = {str(row["prn"]) for row in rows}
    tracks = {str(row["track_id"]) for row in rows}
    total = sum(weights)
    kish = total * total / sum(weight * weight for weight in weights) if weights else 0.0
    return {
        "observation_count": len(rows),
        "sum_weights": total,
        "kish_effective_sample_size": kish,
        "track_count": len(tracks),
        "run_count": len(runs),
        "scene_count": len(scenes),
        "prn_count": len(prns),
    }


def _scope_rows(rows: Sequence[Mapping[str, Any]], scope: str, environment: str = "", band: str = "") -> list[dict[str, Any]]:
    if scope == "global":
        return [dict(row) for row in rows]
    if scope == "environment":
        return [dict(row) for row in rows if row["environment_class"] == environment]
    if scope == "cell":
        return [dict(row) for row in rows if row["environment_class"] == environment and row.get("elevation_band") == band]
    raise ValueError(scope)


def _parameter_values(rows: Sequence[Mapping[str, Any]], parameter: str) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray([float(row[parameter]) for row in rows], dtype=float)
    weights = np.asarray([float(row["weight"]) for row in rows], dtype=float)
    if values.size == 0:
        raise ValueError(f"empty rows for {parameter}")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(weights)) or np.any(weights <= 0.0):
        raise ValueError(f"non-finite values for {parameter}")
    return values, weights


def _weighted_log_likelihood(values: np.ndarray, weights: np.ndarray, family: str, parameters: Mapping[str, float]) -> float:
    logpdf = _family_logpdf(values, family, parameters)
    if not np.all(np.isfinite(logpdf)):
        raise ValueError(f"non-finite {family} logpdf")
    return float(np.sum(weights * logpdf))


def _information_criteria(log_likelihood: float, parameter_count: int, kish: float) -> tuple[float, float | None, float | None]:
    aic = 2.0 * parameter_count - 2.0 * log_likelihood
    if kish > parameter_count + 1.0:
        aicc = aic + 2.0 * parameter_count * (parameter_count + 1.0) / (kish - parameter_count - 1.0)
    else:
        aicc = None
    bic = parameter_count * math.log(kish) - 2.0 * log_likelihood if kish > 0.0 else None
    return aic, aicc, bic


def grouped_family_score(rows: Sequence[Mapping[str, Any]], parameter: str, family: str) -> dict[str, Any]:
    """Score a candidate with weighted in-sample and leave-one-scene-out likelihood."""

    stats_row = _scope_stats(rows) if rows else {"observation_count": 0, "sum_weights": 0.0, "kish_effective_sample_size": 0.0, "track_count": 0, "run_count": 0, "scene_count": 0, "prn_count": 0}
    base = {
        "candidate_family": family,
        "row_count": stats_row["observation_count"],
        "sum_weights": stats_row["sum_weights"],
        "kish_effective_sample_size": stats_row["kish_effective_sample_size"],
        "scene_count": stats_row["scene_count"],
        "run_count": stats_row["run_count"],
        "row_random_split_used": False,
        "parameter_count": family_parameter_count(family),
        "valid": False,
        "failure": "",
        "held_out_scene_count": 0,
        "held_out_scenes": "",
        "weighted_held_out_log_likelihood": "",
        "held_out_weight": "",
        "weighted_held_out_mean_log_likelihood": "",
        "weighted_in_sample_log_likelihood": "",
        "aic": "",
        "aicc": "",
        "bic": "",
    }
    if not rows:
        base["failure"] = "no_direct_rows"
        return base
    try:
        values, weights = _parameter_values(rows, parameter)
        in_fit = fit_family(values, weights, family)
        in_ll = _weighted_log_likelihood(values, weights, family, in_fit.parameters)
        aic, aicc, bic = _information_criteria(in_ll, family_parameter_count(family), stats_row["kish_effective_sample_size"])
        scenes = sorted({str(row["scene_id"]) for row in rows})
        if len(scenes) < 2:
            base["failure"] = "fewer_than_two_scenes_for_grouped_validation"
            base.update({"weighted_in_sample_log_likelihood": in_ll, "aic": aic, "aicc": "" if aicc is None else aicc, "bic": "" if bic is None else bic})
            return base
        folds: dict[str, float] = {}
        fold_weight = 0.0
        for held_out in scenes:
            train = [row for row in rows if str(row["scene_id"]) != held_out]
            test = [row for row in rows if str(row["scene_id"]) == held_out]
            train_values, train_weights = _parameter_values(train, parameter)
            test_values, test_weights = _parameter_values(test, parameter)
            train_fit = fit_family(train_values, train_weights, family)
            folds[held_out] = _weighted_log_likelihood(test_values, test_weights, family, train_fit.parameters)
            fold_weight += float(np.sum(test_weights))
        held_out_ll = float(sum(folds.values()))
        base.update(
            {
                "valid": True,
                "weighted_in_sample_log_likelihood": in_ll,
                "aic": aic,
                "aicc": "" if aicc is None else aicc,
                "bic": "" if bic is None else bic,
                "held_out_scene_count": len(scenes),
                "held_out_scenes": ";".join(scenes),
                "weighted_held_out_log_likelihood": held_out_ll,
                "held_out_weight": fold_weight,
                "weighted_held_out_mean_log_likelihood": held_out_ll / fold_weight if fold_weight else "",
            }
        )
        return base
    except (ValueError, FloatingPointError, RuntimeError) as exc:
        base["failure"] = str(exc)
        return base


def fit_grouped_families(rows: Sequence[Mapping[str, Any]], parameter: str, candidates: Sequence[str]) -> dict[str, Any]:
    scores = [grouped_family_score(rows, parameter, family) for family in candidates]
    valid = [row for row in scores if row["valid"]]
    if not valid:
        return {"selected_family": "", "selection_status": "INCONCLUSIVE", "scores": scores}
    best = valid[0]
    for candidate in valid[1:]:
        if float(candidate["weighted_held_out_mean_log_likelihood"]) > float(best["weighted_held_out_mean_log_likelihood"]) + FAMILY_TIE_TOLERANCE:
            best = candidate
    return {"selected_family": best["candidate_family"], "selection_status": "GROUPED_LOSO_SELECTED", "scores": scores}


def _parent_quantile_fit(values: np.ndarray, weights: np.ndarray, parent_fit: Any, family: str, optimize: bool = True) -> Any:
    probabilities = (np.arange(PARENT_QUANTILE_COUNT, dtype=float) + 0.5) / PARENT_QUANTILE_COUNT
    prior = ppf(parent_fit, probabilities)
    combined_values = np.concatenate([values, prior])
    combined_weights = np.concatenate(
        [weights, np.full(PARENT_QUANTILE_COUNT, PARENT_EQUIVALENT_WEIGHT / PARENT_QUANTILE_COUNT)]
    )
    return fit_family(combined_values, combined_weights, family, optimize_parameters=optimize)


def _model_row(
    *,
    scope: str,
    scope_id: str,
    environment: str,
    band: str,
    parameter: str,
    family: str,
    fit: Any,
    support: Mapping[str, Any],
    source: str,
    parent_scope: str = "",
) -> dict[str, Any]:
    probabilities = np.asarray([0.025, 0.5, 0.975], dtype=float)
    model_quantiles = ppf(fit, probabilities)
    return {
        "scope": scope,
        "scope_id": scope_id,
        "environment_class": environment,
        "elevation_band": band,
        "parameter": parameter,
        "family": family,
        "fit_parameters_json": json.dumps({key: float(value) for key, value in fit.parameters.items()}, sort_keys=True),
        "fit_objective": float(fit.objective),
        "weighted_in_sample_log_likelihood": float(-fit.objective * fit.weighted_count),
        "support_status": support["support_status"],
        "parameter_source": source,
        "direct_observation_count": support["observation_count"],
        "sum_weights": support["sum_weights"],
        "kish_effective_sample_size": support["kish_effective_sample_size"],
        "track_count": support["track_count"],
        "run_count": support["run_count"],
        "scene_count": support["scene_count"],
        "prn_count": support["prn_count"],
        "parent_scope": parent_scope,
        "model_q025": float(model_quantiles[0]),
        "model_q050": float(model_quantiles[1]),
        "model_q975": float(model_quantiles[2]),
        "_fit": fit,
    }


def _fit_hierarchical_models(
    rows: Sequence[Mapping[str, Any]],
    family_by_parameter: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    models: list[dict[str, Any]] = []
    model_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    global_rows = list(rows)
    for parameter in PARAMETERS:
        family = family_by_parameter[parameter]
        values, weights = _parameter_values(global_rows, parameter)
        global_fit = fit_family(values, weights, family)
        support = _scope_stats(global_rows)
        support["support_status"] = support_label(support["observation_count"], support["scene_count"], support["kish_effective_sample_size"])
        model = _model_row(scope="global", scope_id="global", environment="ALL", band="ALL", parameter=parameter, family=family, fit=global_fit, support=support, source="weighted_stage3_observations")
        models.append(model)
        model_lookup[("global", "global", parameter)] = model
    for environment in ENVIRONMENTS:
        env_rows = _scope_rows(rows, "environment", environment=environment)
        env_support = _scope_stats(env_rows)
        env_support["support_status"] = support_label(env_support["observation_count"], env_support["scene_count"], env_support["kish_effective_sample_size"])
        for parameter in PARAMETERS:
            family = family_by_parameter[parameter]
            values, weights = _parameter_values(env_rows, parameter)
            parent = model_lookup[("global", "global", parameter)]["_fit"]
            env_fit = _parent_quantile_fit(values, weights, parent, family)
            model = _model_row(scope="environment", scope_id=environment, environment=environment, band="ALL", parameter=parameter, family=family, fit=env_fit, support=env_support, source="environment_local_plus_global_parent", parent_scope="global")
            models.append(model)
            model_lookup[("environment", environment, parameter)] = model
        for band in ELEVATION_BANDS:
            cell_rows = [row for row in env_rows if row.get("elevation_ready") and row.get("elevation_band") == band]
            cell_support = _scope_stats(cell_rows) if cell_rows else {"observation_count": 0, "sum_weights": 0.0, "kish_effective_sample_size": 0.0, "track_count": 0, "run_count": 0, "scene_count": 0, "prn_count": 0}
            cell_support["support_status"] = support_label(cell_support["observation_count"], cell_support["scene_count"], cell_support["kish_effective_sample_size"])
            for parameter in PARAMETERS:
                family = family_by_parameter[parameter]
                env_parent = model_lookup[("environment", environment, parameter)]["_fit"]
                if cell_rows:
                    values, weights = _parameter_values(cell_rows, parameter)
                    cell_fit = _parent_quantile_fit(values, weights, env_parent, family)
                    source = "cell_local_plus_environment_parent"
                    parent_scope = f"environment:{environment}"
                else:
                    cell_fit = env_parent
                    source = "environment_parent_only"
                    parent_scope = f"environment:{environment}"
                model = _model_row(scope="cell", scope_id=f"{environment}__{band}", environment=environment, band=band, parameter=parameter, family=family, fit=cell_fit, support=cell_support, source=source, parent_scope=parent_scope)
                models.append(model)
                model_lookup[("cell", f"{environment}__{band}", parameter)] = model
    return models, model_lookup


def _summary_row(policy: str, scope: str, scope_id: str, environment: str, band: str, parameter: str, rows: Sequence[Mapping[str, Any]], family: str, family_status: str) -> dict[str, Any]:
    values, weights = _parameter_values(rows, parameter) if rows else (np.asarray([], dtype=float), np.asarray([], dtype=float))
    summary = weighted_summary(values, weights)
    support = _scope_stats(rows) if rows else {"observation_count": 0, "sum_weights": 0.0, "kish_effective_sample_size": 0.0, "track_count": 0, "run_count": 0, "scene_count": 0, "prn_count": 0}
    return {
        "policy": policy,
        "scope": scope,
        "scope_id": scope_id,
        "environment_class": environment,
        "elevation_band": band,
        "parameter": parameter,
        "observation_count": summary["count"],
        "sum_weights": summary["sum_weights"],
        "kish_effective_sample_size": summary["kish_effective_n"],
        "track_count": support["track_count"],
        "run_count": support["run_count"],
        "scene_count": support["scene_count"],
        "prn_count": support["prn_count"],
        "mean": summary["mean"],
        "median": summary["median"],
        "q025": summary["q025"],
        "q25": summary["q25"],
        "q75": summary["q75"],
        "q975": summary["q975"],
        "std": summary["std"],
        "selected_family": family,
        "family_selection_status": family_status,
    }


def _fit_policy_family_map(rows: Sequence[Mapping[str, Any]], policy: str) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    score_rows: list[dict[str, Any]] = []
    selections: dict[tuple[str, str, str], dict[str, Any]] = {}
    scopes: list[tuple[str, str, str, str, list[dict[str, Any]]]] = [("global", "global", "ALL", "ALL", list(rows))]
    scopes += [("environment", environment, environment, "ALL", _scope_rows(rows, "environment", environment=environment)) for environment in ENVIRONMENTS]
    scopes += [("cell", f"{environment}__{band}", environment, band, _scope_rows(rows, "cell", environment=environment, band=band)) for environment in ENVIRONMENTS for band in ELEVATION_BANDS]
    for scope, scope_id, environment, band, scoped_rows in scopes:
        for parameter in PARAMETERS:
            selection = fit_grouped_families(scoped_rows, parameter, CANDIDATE_FAMILIES[parameter])
            selections[(scope, scope_id, parameter)] = selection
            for score in selection["scores"]:
                score_rows.append(
                    {
                        "policy": policy,
                        "scope": scope,
                        "scope_id": scope_id,
                        "environment_class": environment,
                        "elevation_band": band,
                        "parameter": parameter,
                        "selected_for_scope": score["candidate_family"] == selection["selected_family"],
                        "selection_status": selection["selection_status"],
                        **score,
                    }
                )
    return score_rows, selections


def _family_for_sensitivity(selections: Mapping[tuple[str, str, str], dict[str, Any]], parameter: str, scope: str, scope_id: str) -> tuple[str, str]:
    local = selections.get((scope, scope_id, parameter), {})
    if local.get("selected_family"):
        return str(local["selected_family"]), str(local.get("selection_status", ""))
    global_selection = selections.get(("global", "global", parameter), {})
    if global_selection.get("selected_family"):
        return str(global_selection["selected_family"]), "GLOBAL_FALLBACK"
    return "", "INCONCLUSIVE"


def _track_rows(nodes: Sequence[Mapping[str, Any]], tracks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_track = {str(track["track_id"]): track for track in tracks}
    rows = []
    for track in tracks:
        row = {
            "stage3_path_id": str(track["track_id"]),
            "track_id": str(track["track_id"]),
            "scene_id": str(track["scene_id"]),
            "run_id": str(track["run_id"]),
            "prn": str(track["prn"]),
            "environment_class": str(track["environment_class"]),
            "elevation_band": str(track.get("elevation_bin_set", "")).split(";")[0] if track.get("elevation_bin_set") else "",
            "elevation_ready": bool(track.get("elevation_count", 0)),
            "weight": 1.0,
            "excess_delay_samples": float(track["median_excess_delay_samples"]),
            "doppler_offset_hz": float(track["median_doppler_offset_hz"]),
            "relative_power_db": float(track["median_relative_power_db"]),
        }
        rows.append(row)
    if len({row["track_id"] for row in rows}) != len(by_track):
        raise ValueError("track rows are not unique")
    return rows


def _copula_row(scope: str, scope_id: str, environment: str, band: str, rows: Sequence[Mapping[str, Any]], copula_source: str, dependence_status: str, correlation: np.ndarray) -> dict[str, Any]:
    support = _scope_stats(rows) if rows else {"observation_count": 0, "sum_weights": 0.0, "kish_effective_sample_size": 0.0, "track_count": 0, "run_count": 0, "scene_count": 0, "prn_count": 0}
    return {
        "scope": scope,
        "scope_id": scope_id,
        "environment_class": environment,
        "elevation_band": band,
        "dependence_status": dependence_status,
        "copula_source": copula_source,
        "observation_count": support["observation_count"],
        "sum_weights": support["sum_weights"],
        "kish_effective_sample_size": support["kish_effective_sample_size"],
        "track_count": support["track_count"],
        "run_count": support["run_count"],
        "scene_count": support["scene_count"],
        "prn_count": support["prn_count"],
        "min_eigenvalue": float(np.min(np.linalg.eigvalsh(correlation))),
        "eigenvalue_floor": COPULA_EIGENVALUE_FLOOR,
        "rank_method": "weighted_midrank_then_gaussian_transform",
        **{f"corr__{left}__{right}": float(correlation[i, j]) for i, left in enumerate(PARAMETERS) for j, right in enumerate(PARAMETERS)},
    }


def _weighted_correlation(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    if len(rows) < 2:
        return np.eye(3)
    weights = np.asarray([float(row["weight"]) for row in rows], dtype=float)
    z = np.column_stack([stats.norm.ppf(weighted_rank([float(row[parameter]) for row in rows], weights)) for parameter in PARAMETERS])
    total = float(np.sum(weights))
    center = np.sum(z * weights[:, None], axis=0) / total
    centered = z - center
    covariance = (centered * weights[:, None]).T @ centered / total
    scale = np.sqrt(np.maximum(np.diag(covariance), 1e-12))
    raw = covariance / np.outer(scale, scale)
    raw = np.nan_to_num(raw, nan=0.0)
    np.fill_diagonal(raw, 1.0)
    projected, _ = nearest_correlation(raw, COPULA_EIGENVALUE_FLOOR)
    return projected


def _build_copulas(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    global_corr = _weighted_correlation(rows)
    output.append(_copula_row("global", "global", "ALL", "ALL", rows, "global_stage3_weighted_observations", "DATA_SUPPORTED", global_corr))
    env_corrs: dict[str, np.ndarray] = {}
    for environment in ENVIRONMENTS:
        env_rows = _scope_rows(rows, "environment", environment=environment)
        support = _scope_stats(env_rows)
        label = support_label(support["observation_count"], support["scene_count"], support["kish_effective_sample_size"])
        if label == "DATA_SUPPORTED":
            env_corr = _weighted_correlation(env_rows)
            env_corrs[environment] = env_corr
            output.append(_copula_row("environment", environment, environment, "ALL", env_rows, f"environment:{environment}", "DATA_SUPPORTED", env_corr))
        else:
            env_corrs[environment] = global_corr
            output.append(_copula_row("environment", environment, environment, "ALL", env_rows, "global_parent", "ENVIRONMENT_PARENT_ONLY", global_corr))
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            cell_rows = _scope_rows(rows, "cell", environment=environment, band=band)
            support = _scope_stats(cell_rows) if cell_rows else {"observation_count": 0, "sum_weights": 0.0, "kish_effective_sample_size": 0.0, "track_count": 0, "run_count": 0, "scene_count": 0, "prn_count": 0}
            label = support_label(support["observation_count"], support["scene_count"], support["kish_effective_sample_size"])
            if label == "DATA_SUPPORTED":
                corr = _weighted_correlation(cell_rows)
                output.append(_copula_row("cell", f"{environment}__{band}", environment, band, cell_rows, f"cell:{environment}__{band}", "DATA_SUPPORTED", corr))
            else:
                corr = env_corrs[environment]
                status = "NO_DIRECT_SUPPORT" if not cell_rows else "ENVIRONMENT_PARENT_ONLY"
                output.append(_copula_row("cell", f"{environment}__{band}", environment, band, cell_rows, f"environment:{environment}", status, corr))
    return output


def _fit_bootstrap_scope(rows: Sequence[Mapping[str, Any]], family: str, parameter: str, parent_fit: Any | None = None) -> Any:
    values, weights = _parameter_values(rows, parameter)
    if parent_fit is None:
        return fit_family(values, weights, family, optimize_parameters=False)
    return _parent_quantile_fit(values, weights, parent_fit, family, optimize=False)


def _bootstrap_scope_rows(
    rows: Sequence[Mapping[str, Any]],
    family_by_parameter: Mapping[str, str],
    model_lookup: Mapping[tuple[str, str, str], dict[str, Any]],
    block_unit: str,
    seed: int,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> list[dict[str, Any]]:
    scopes: list[tuple[str, str, str, str, list[dict[str, Any]], Any | None]] = []
    scopes.append(("global", "global", "ALL", "ALL", list(rows), None))
    for environment in ENVIRONMENTS:
        env_rows = _scope_rows(rows, "environment", environment=environment)
        scopes.append(("environment", environment, environment, "ALL", env_rows, None))
        for band in ELEVATION_BANDS:
            cell_rows = _scope_rows(rows, "cell", environment=environment, band=band)
            parent_keys = [("environment", environment, parameter) for parameter in PARAMETERS]
            parent_fits = (
                {parameter: model_lookup[key]["_fit"] for parameter, key in zip(PARAMETERS, parent_keys)}
                if model_lookup and all(key in model_lookup for key in parent_keys)
                else None
            )
            scopes.append(("cell", f"{environment}__{band}", environment, band, cell_rows, parent_fits))
    rng = np.random.default_rng(seed)
    distribution: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    statuses: dict[tuple[str, str, str, str], str] = {}
    for scope, scope_id, environment, band, scoped_rows, parent_fits in scopes:
        groups = sorted({str(row[block_unit]) for row in scoped_rows})
        if not scoped_rows:
            for parameter in PARAMETERS:
                statuses[(scope, scope_id, parameter, "") ] = "NO_DIRECT_SUPPORT"
            continue
        if len(groups) < 2:
            for parameter in PARAMETERS:
                statuses[(scope, scope_id, parameter, "") ] = "INSUFFICIENT_BLOCKS"
            continue
        by_group = {group: [row for row in scoped_rows if str(row[block_unit]) == group] for group in groups}
        for _ in range(replicates):
            selected = rng.choice(groups, size=len(groups), replace=True)
            sampled = [row for group in selected for row in by_group[str(group)]]
            for parameter in PARAMETERS:
                family = family_by_parameter[parameter]
                parent = parent_fits[parameter] if isinstance(parent_fits, dict) else None
                try:
                    fit = _fit_bootstrap_scope(sampled, family, parameter, parent)
                    values, weights = _parameter_values(sampled, parameter)
                    summary = weighted_summary(values, weights)
                    metrics = {
                        "observed_weighted_mean": float(summary["mean"]),
                        "observed_weighted_median": float(summary["median"]),
                        "observed_weighted_q025": float(summary["q025"]),
                        "observed_weighted_q25": float(summary["q25"]),
                        "observed_weighted_q75": float(summary["q75"]),
                        "observed_weighted_q975": float(summary["q975"]),
                        "model_q025": float(ppf(fit, np.asarray([0.025]))[0]),
                        "model_q050": float(ppf(fit, np.asarray([0.5]))[0]),
                        "model_q975": float(ppf(fit, np.asarray([0.975]))[0]),
                    }
                    for name, value in fit.parameters.items():
                        metrics[f"fit_parameter:{name}"] = float(value)
                    for metric, value in metrics.items():
                        distribution[(scope, scope_id, parameter, metric)].append(value)
                except (ValueError, FloatingPointError, RuntimeError):
                    continue
    output: list[dict[str, Any]] = []
    for key, values in sorted(distribution.items()):
        scope, scope_id, parameter, metric = key
        ordered = np.asarray(values, dtype=float)
        lower, median, upper = np.quantile(ordered, [0.025, 0.5, 0.975])
        environment = "ALL" if scope == "global" else scope_id if scope == "environment" else scope_id.split("__", 1)[0]
        band = "ALL" if scope != "cell" else scope_id.split("__", 1)[1]
        output.append({
            "block_unit": block_unit,
            "scope": scope,
            "scope_id": scope_id,
            "environment_class": environment,
            "elevation_band": band,
            "parameter": parameter,
            "metric": metric,
            "lower_2_5": float(lower),
            "median_50": float(median),
            "upper_97_5": float(upper),
            "replicate_count": len(values),
            "seed": seed,
            "status": "PASS" if len(values) == replicates else "PARTIAL_REPLICATES",
        })
    for (scope, scope_id, parameter, metric), status in sorted(statuses.items()):
        environment = "ALL" if scope == "global" else scope_id if scope == "environment" else scope_id.split("__", 1)[0]
        band = "ALL" if scope != "cell" else scope_id.split("__", 1)[1]
        output.append({
            "block_unit": block_unit,
            "scope": scope,
            "scope_id": scope_id,
            "environment_class": environment,
            "elevation_band": band,
            "parameter": parameter,
            "metric": "status",
            "lower_2_5": "",
            "median_50": "",
            "upper_97_5": "",
            "replicate_count": 0,
            "seed": seed,
            "status": status,
        })
    return output


def _bootstrap_lookup(rows: Sequence[Mapping[str, Any]], block_unit: str, scope: str, scope_id: str, parameter: str, metric: str) -> tuple[float | None, float | None, float | None]:
    match = next((row for row in rows if row["block_unit"] == block_unit and row["scope"] == scope and row["scope_id"] == scope_id and row["parameter"] == parameter and row["metric"] == metric), None)
    if not match or not match.get("lower_2_5"):
        return None, None, None
    return parse_num(match.get("lower_2_5")), parse_num(match.get("median_50")), parse_num(match.get("upper_97_5"))


def _weighted_linear_diagnostic(rows: Sequence[Mapping[str, Any]], parameter: str) -> dict[str, Any]:
    x = np.asarray([float(row["elevation_deg"]) for row in rows], dtype=float)
    y = np.asarray([float(row[parameter]) for row in rows], dtype=float)
    w = np.asarray([float(row["weight"]) for row in rows], dtype=float)
    total = float(np.sum(w))
    xbar = float(np.sum(w * x) / total)
    ybar = float(np.sum(w * y) / total)
    denominator = float(np.sum(w * (x - xbar) ** 2))
    slope = float(np.sum(w * (x - xbar) * (y - ybar)) / denominator) if denominator > 0 else 0.0
    intercept = ybar - slope * xbar
    fitted = intercept + slope * x
    ss_res = float(np.sum(w * (y - fitted) ** 2))
    ss_tot = float(np.sum(w * (y - ybar) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rho = float(np.corrcoef(weighted_rank(x, w), weighted_rank(y, w))[0, 1]) if len(rows) >= 2 else 0.0
    return {"slope": slope, "intercept": float(intercept), "r2": r2, "rmse": math.sqrt(max(ss_res / total, 0.0)), "rho": rho, "x_min": float(np.min(x)), "x_max": float(np.max(x))}


def _bootstrap_slopes(rows: Sequence[Mapping[str, Any]], parameter: str, seed: int, replicates: int = BOOTSTRAP_REPLICATES) -> tuple[float | None, float | None, float | None]:
    groups = sorted({str(row["scene_id"]) for row in rows})
    if len(groups) < 2:
        return None, None, None
    rng = np.random.default_rng(seed)
    by_scene = {scene: [row for row in rows if str(row["scene_id"]) == scene] for scene in groups}
    values = []
    for _ in range(replicates):
        selected = rng.choice(groups, size=len(groups), replace=True)
        sampled = [row for scene in selected for row in by_scene[str(scene)]]
        try:
            values.append(_weighted_linear_diagnostic(sampled, parameter)["slope"])
        except (ValueError, FloatingPointError):
            continue
    if not values:
        return None, None, None
    return tuple(float(value) for value in np.quantile(np.asarray(values), [0.025, 0.5, 0.975]))


def _load_stage4_rows(root: Path) -> tuple[tuple[dict[str, Any], ...], str]:
    path = root / STAGE4_PARAMETER_REL
    if not path.is_file():
        raise FileNotFoundError(path)
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            if str(raw.get("label_value", "")).strip() != "confirmed_multipath" or str(raw.get("path_role", "")).strip() != "multipath":
                continue
            if str(raw.get("environment_modeling_ready", "")).strip() not in {"1", "true", "True"}:
                continue
            values = {
                "stage3_path_id": str(raw.get("event_path_id", "")),
                "track_id": f"STAGE4_EVENT_{raw.get('event_id', '')}",
                "scene_id": str(raw.get("scene_id", "")),
                "run_id": str(raw.get("run_id", "")),
                "prn": str(raw.get("prn", "")),
                "environment_class": str(raw.get("environment_class", "")),
                "elevation_band": str(raw.get("elevation_band", "")),
                "elevation_ready": str(raw.get("elevation_modeling_ready", "")) in {"1", "true", "True"},
                "elevation_deg": parse_num(raw.get("elevation_deg")),
                "weight": 1.0,
                "excess_delay_samples": parse_num(raw.get("excess_delay_samples")),
                "doppler_offset_hz": parse_num(raw.get("relative_doppler_hz")),
                "relative_power_db": parse_num(raw.get("relative_power_db")),
            }
            if values["elevation_ready"] and (values["elevation_deg"] is None or not values["elevation_band"]):
                raise ValueError("Stage4 elevation-ready row lacks elevation provenance")
            if any(values[parameter] is None for parameter in PARAMETERS):
                raise ValueError("Stage4 confirmed row has a missing model parameter")
            rows.append(values)
    return tuple(rows), sha256_file(path)


def _build_sensitivity_rows(
    policy_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    selections: Mapping[str, Mapping[tuple[str, str, str], dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output = []
    for policy, rows in policy_rows.items():
        for scope, scope_id, environment, band in (
            [("global", "global", "ALL", "ALL")]
            + [("environment", env, env, "ALL") for env in ENVIRONMENTS]
            + [("cell", f"{env}__{band_name}", env, band_name) for env in ENVIRONMENTS for band_name in ELEVATION_BANDS]
        ):
            scoped = _scope_rows(rows, scope, environment=environment, band=band) if scope != "global" else list(rows)
            for parameter in PARAMETERS:
                family, status = _family_for_sensitivity(selections[policy], parameter, scope, scope_id)
                output.append(_summary_row(policy, scope, scope_id, environment, band, parameter, scoped, family, status))
    return output, []


def _stage4_bootstrap_summaries(stage4_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    empty_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    family_selection_rows, selections = _fit_policy_family_map(stage4_rows, "STAGE4_STRICT_CONFIRMED")
    family_by_parameter = {
        parameter: selections[("global", "global", parameter)].get("selected_family") or CANDIDATE_FAMILIES[parameter][0]
        for parameter in PARAMETERS
    }
    # Stage4 has no parent-only layer in this comparison; the global family is
    # frozen per parameter and resampling is still by complete scene blocks.
    return _bootstrap_scope_rows(stage4_rows, family_by_parameter, empty_lookup, "scene_id", STAGE4_BOOTSTRAP_SEED)


def _build_stage4_sensitivity(
    stage3_rows: Sequence[Mapping[str, Any]],
    stage4_rows: Sequence[Mapping[str, Any]],
    stage3_models: Mapping[tuple[str, str, str], dict[str, Any]],
    stage3_bootstrap: Sequence[Mapping[str, Any]],
    stage4_bootstrap: Sequence[Mapping[str, Any]],
    stage3_selections: Mapping[tuple[str, str, str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output = []
    cdf_output = []
    stage4_score_rows, stage4_selections = _fit_policy_family_map(stage4_rows, "STAGE4_STRICT_CONFIRMED")
    stage4_family_map = {parameter: stage4_selections[("global", "global", parameter)] for parameter in PARAMETERS}
    for scope, scope_id, environment, band in (
        [("global", "global", "ALL", "ALL")]
        + [("environment", env, env, "ALL") for env in ENVIRONMENTS]
        + [("cell", f"{env}__{band_name}", env, band_name) for env in ENVIRONMENTS for band_name in ELEVATION_BANDS]
    ):
        stage3_scoped = _scope_rows(stage3_rows, scope, environment=environment, band=band) if scope != "global" else list(stage3_rows)
        stage4_scoped = _scope_rows(stage4_rows, scope, environment=environment, band=band) if scope != "global" else list(stage4_rows)
        for parameter in PARAMETERS:
            stage3_family, stage3_status = _family_for_sensitivity(stage3_selections, parameter, scope, scope_id)
            stage4_selection = stage4_selections.get((scope, scope_id, parameter), {})
            stage4_family = stage4_selection.get("selected_family") or stage4_family_map[parameter].get("selected_family", "")
            stage4_status = stage4_selection.get("selection_status") or ("GLOBAL_FALLBACK" if stage4_family else "INCONCLUSIVE")
            stage3_summary = weighted_summary(*_parameter_values(stage3_scoped, parameter)) if stage3_scoped else weighted_summary([], [])
            stage4_summary = weighted_summary(*_parameter_values(stage4_scoped, parameter)) if stage4_scoped else weighted_summary([], [])
            stage3_lower, stage3_median_boot, stage3_upper = _bootstrap_lookup(stage3_bootstrap, "scene_id", scope, scope_id, parameter, "observed_weighted_median")
            stage4_lower, stage4_median_boot, stage4_upper = _bootstrap_lookup(stage4_bootstrap, "scene_id", scope, scope_id, parameter, "observed_weighted_median")
            comparison_status = "COMPARABLE" if stage3_scoped and stage4_scoped else "INCONCLUSIVE_NO_DIRECT_STAGE4_SUPPORT"
            output.extend(
                [
                    {
                        "population": "STAGE3_WEIGHTED_PRIMARY",
                        "scope": scope,
                        "scope_id": scope_id,
                        "environment_class": environment,
                        "elevation_band": band,
                        "parameter": parameter,
                        "observation_count": stage3_summary["count"],
                        "sum_weights": stage3_summary["sum_weights"],
                        "kish_effective_sample_size": stage3_summary["kish_effective_n"],
                        "track_count": _scope_stats(stage3_scoped)["track_count"] if stage3_scoped else 0,
                        "run_count": _scope_stats(stage3_scoped)["run_count"] if stage3_scoped else 0,
                        "scene_count": _scope_stats(stage3_scoped)["scene_count"] if stage3_scoped else 0,
                        "mean": stage3_summary["mean"], "median": stage3_summary["median"], "q025": stage3_summary["q025"], "q25": stage3_summary["q25"], "q75": stage3_summary["q75"], "q975": stage3_summary["q975"],
                        "selected_family": stage3_family, "family_selection_status": stage3_status,
                        "median_bootstrap_lower": stage3_lower, "median_bootstrap_median": stage3_median_boot, "median_bootstrap_upper": stage3_upper,
                        "comparison_status": comparison_status,
                    },
                    {
                        "population": "STAGE4_STRICT_CONFIRMED",
                        "scope": scope,
                        "scope_id": scope_id,
                        "environment_class": environment,
                        "elevation_band": band,
                        "parameter": parameter,
                        "observation_count": stage4_summary["count"],
                        "sum_weights": stage4_summary["sum_weights"],
                        "kish_effective_sample_size": stage4_summary["kish_effective_n"],
                        "track_count": _scope_stats(stage4_scoped)["track_count"] if stage4_scoped else 0,
                        "run_count": _scope_stats(stage4_scoped)["run_count"] if stage4_scoped else 0,
                        "scene_count": _scope_stats(stage4_scoped)["scene_count"] if stage4_scoped else 0,
                        "mean": stage4_summary["mean"], "median": stage4_summary["median"], "q025": stage4_summary["q025"], "q25": stage4_summary["q25"], "q75": stage4_summary["q75"], "q975": stage4_summary["q975"],
                        "selected_family": stage4_family, "family_selection_status": stage4_status,
                        "median_bootstrap_lower": stage4_lower, "median_bootstrap_median": stage4_median_boot, "median_bootstrap_upper": stage4_upper,
                        "comparison_status": comparison_status,
                    },
                ]
            )
            stage3_model = stage3_models.get((scope, scope_id, parameter))
            stage4_fit = None
            if stage4_scoped and stage4_family:
                try:
                    values, weights = _parameter_values(stage4_scoped, parameter)
                    stage4_fit = fit_family(values, weights, stage4_family)
                except (ValueError, FloatingPointError, RuntimeError):
                    stage4_fit = None
            if stage3_model and stage4_fit and stage3_scoped and stage4_scoped:
                all_values = np.asarray([float(row[parameter]) for row in stage3_scoped + stage4_scoped], dtype=float)
                grid = np.linspace(float(np.min(all_values)), float(np.max(all_values)), 41)
                stage3_fit = stage3_model["_fit"]
                for grid_index, grid_value in enumerate(grid):
                    cdf_output.append(
                        {
                            "scope": scope, "scope_id": scope_id, "environment_class": environment, "elevation_band": band,
                            "parameter": parameter, "grid_index": grid_index, "grid_value": float(grid_value),
                            "stage3_weighted_cdf": float(cdf(stage3_fit, np.asarray([grid_value]))[0]),
                            "stage4_strict_confirmed_cdf": float(cdf(stage4_fit, np.asarray([grid_value]))[0]),
                            "stage3_family": stage3_model["family"], "stage4_family": stage4_family, "comparison_status": "COMPARABLE",
                        }
                    )
            else:
                cdf_output.append(
                    {
                        "scope": scope, "scope_id": scope_id, "environment_class": environment, "elevation_band": band,
                        "parameter": parameter, "grid_index": "", "grid_value": "", "stage3_weighted_cdf": "", "stage4_strict_confirmed_cdf": "",
                        "stage3_family": stage3_model["family"] if stage3_model else "", "stage4_family": stage4_family, "comparison_status": "INCONCLUSIVE_NO_DIRECT_STAGE4_SUPPORT" if not stage4_scoped else "CDF_FIT_FAILED",
                    }
                )
    return output, cdf_output


def _center_metrics(nodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_center: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_center[str(node["stage3_center_id"])].append(node)
    output = []
    for center_id, members in by_center.items():
        powers = np.power(10.0, np.asarray([float(node["relative_power_db"]) for node in members]) / 10.0)
        delays = np.asarray([float(node["excess_delay_samples"]) for node in members])
        dopplers = np.asarray([float(node["doppler_offset_hz"]) for node in members])
        total_power = float(np.sum(powers))
        delay_centroid = float(np.sum(powers * delays) / total_power)
        doppler_centroid = float(np.sum(powers * dopplers) / total_power)
        output.append(
            {
                "center_id": center_id,
                "environment_class": str(members[0]["environment_class"]),
                "elevation_band": str(members[0].get("elevation_band", "")),
                "component_count": len(members),
                "mean_excess_delay_samples": delay_centroid,
                "rms_delay_spread_samples": math.sqrt(max(float(np.sum(powers * (delays - delay_centroid) ** 2) / total_power), 0.0)) if len(members) >= 2 else None,
                "doppler_centroid_hz": doppler_centroid,
                "rms_doppler_spread_hz": math.sqrt(max(float(np.sum(powers * (dopplers - doppler_centroid) ** 2) / total_power), 0.0)) if len(members) >= 2 else None,
                "aggregate_relative_multipath_power_db": 10.0 * math.log10(total_power),
                "strongest_relative_multipath_power_db": float(max(float(node["relative_power_db"]) for node in members)),
            }
        )
    return output


def _derived_statistics(center_metrics: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    definitions = [
        ("mean_excess_delay_samples", "samples", "DERIVABLE_ALGORITHM_OBSERVATION", "Stage3 reliable/persistent multipath-only power-weighted center diagnostic"),
        ("rms_delay_spread_samples", "samples", "CONDITIONAL_RELATIVE_POWER_DIAGNOSTIC", "requires at least two Stage3 path observations in a center; not total-channel RMS"),
        ("doppler_centroid_hz", "Hz", "DERIVABLE_ALGORITHM_OBSERVATION", "Stage3 multipath-only relative-power-weighted centroid"),
        ("rms_doppler_spread_hz", "Hz", "CONDITIONAL_RELATIVE_POWER_DIAGNOSTIC", "requires at least two Stage3 path observations in a center"),
        ("component_count", "count", "DERIVABLE_ALGORITHM_OBSERVATION", "number of Stage3 reliable multipath path observations at a center; not physical path count"),
        ("aggregate_relative_multipath_power_db", "dB", "CONDITIONAL_RELATIVE_POWER_DIAGNOSTIC", "sum of relative power ratios; not absolute RF power"),
        ("strongest_relative_multipath_power_db", "dB", "CONDITIONAL_RELATIVE_POWER_DIAGNOSTIC", "maximum relative power among Stage3 paths; not absolute RF power"),
    ]
    rows = []
    scopes = [("global", "global", "ALL", "ALL", list(center_metrics))]
    scopes += [("environment", env, env, "ALL", [row for row in center_metrics if row["environment_class"] == env]) for env in ENVIRONMENTS]
    scopes += [("cell", f"{env}__{band}", env, band, [row for row in center_metrics if row["environment_class"] == env and row["elevation_band"] == band]) for env in ENVIRONMENTS for band in ELEVATION_BANDS]
    for scope, scope_id, environment, band, scoped in scopes:
        for key, unit, identifiability, interpretation in definitions:
            values = [parse_num(row.get(key)) for row in scoped]
            values = [value for value in values if value is not None]
            summary = weighted_summary(values, [1.0] * len(values)) if values else weighted_summary([], [])
            rows.append({
                "scope": scope, "scope_id": scope_id, "environment_class": environment, "elevation_band": band,
                "statistic": key, "unit": unit, "observation_or_center_count": summary["count"],
                "mean": summary["mean"], "median": summary["median"], "q25": summary["q25"], "q75": summary["q75"], "min": min(values) if values else "", "max": max(values) if values else "", "std": summary["std"],
                "identifiability": identifiability, "status": "AVAILABLE" if values else "NO_DIRECT_SUPPORT", "interpretation": interpretation,
            })
    rows.append({
        "scope": "global", "scope_id": "global", "environment_class": "ALL", "elevation_band": "ALL", "statistic": "ricean_k_factor", "unit": "ratio", "observation_or_center_count": 0, "mean": "", "median": "", "q25": "", "q75": "", "min": "", "max": "", "std": "", "identifiability": "NO", "status": "NOT_IDENTIFIABLE", "interpretation": "No defensible physical main/reference component power and phase definition is available in the Stage3 population; do not compute K-factor.",
    })
    return rows


def _persistence_rows(nodes: Sequence[Mapping[str, Any]], tracks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    node_by_track: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for node in nodes:
        node_by_track[str(node["track_id"])].append(node)
    track_metrics = []
    for track in tracks:
        members = node_by_track[str(track["track_id"])]
        times = [float(node["center_recording_time_s"]) for node in members if parse_num(node.get("center_recording_time_s")) is not None]
        windows = [int(float(node["center_window_id"])) for node in members if parse_num(node.get("center_window_id")) is not None]
        track_metrics.append({
            "environment_class": str(track["environment_class"]),
            "elevation_band": str(track.get("elevation_bin_set", "")).split(";")[0] if track.get("elevation_bin_set") else "",
            "duration_s": max(times) - min(times) if times else None,
            "window_span": max(windows) - min(windows) if windows else None,
        })
    rows = []
    scopes = [("global", "global", "ALL", "ALL", track_metrics)]
    scopes += [("environment", env, env, "ALL", [row for row in track_metrics if row["environment_class"] == env]) for env in ENVIRONMENTS]
    scopes += [("cell", f"{env}__{band}", env, band, [row for row in track_metrics if row["environment_class"] == env and row["elevation_band"] == band]) for env in ENVIRONMENTS for band in ELEVATION_BANDS]
    for scope, scope_id, env, band, scoped in scopes:
        durations = [row["duration_s"] for row in scoped if row["duration_s"] is not None]
        spans = [row["window_span"] for row in scoped if row["window_span"] is not None]
        rows.append({
            "scope": scope, "scope_id": scope_id, "environment_class": env, "elevation_band": band, "track_count": len(scoped),
            "mean_duration_s": float(np.mean(durations)) if durations else "", "median_duration_s": float(np.median(durations)) if durations else "", "q25_duration_s": float(np.quantile(durations, 0.25)) if durations else "", "q75_duration_s": float(np.quantile(durations, 0.75)) if durations else "", "min_duration_s": min(durations) if durations else "", "max_duration_s": max(durations) if durations else "", "mean_window_span": float(np.mean(spans)) if spans else "", "median_window_span": float(np.median(spans)) if spans else "", "status": "AVAILABLE" if durations else "NO_DIRECT_SUPPORT", "interpretation": "Stage3 algorithm-observed persistence duration only; not physical reflector lifetime.",
        })
    return rows


def _model_diagnostics(models: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    probabilities = np.asarray([0.025, 0.5, 0.975])
    for model in models:
        fit = model["_fit"]
        quantiles = ppf(fit, probabilities)
        errors = np.abs(cdf(fit, quantiles) - probabilities)
        rows.append({
            "scope": model["scope"], "scope_id": model["scope_id"], "parameter": model["parameter"], "family": model["family"], "support_status": model["support_status"], "finite_quantile_rate": float(np.mean(np.isfinite(quantiles))), "cdf_ppf_max_abs_error": float(np.max(errors)), "positive_delay_support": model["parameter"] != "excess_delay_samples" or bool(np.all(quantiles > 0.0)), "diagnostic_status": "PASS" if np.all(np.isfinite(quantiles)) and float(np.max(errors)) <= 1e-8 and (model["parameter"] != "excess_delay_samples" or np.all(quantiles > 0.0)) else "FAIL",
        })
    return rows


def continuous_elevation_result(rows: Sequence[Mapping[str, Any]]) -> str:
    evidence = []
    for row in rows:
        if row.get("diagnostic_support_status") != "DATA_SUPPORTED":
            continue
        lower = parse_num(row.get("slope_bootstrap_lower"))
        upper = parse_num(row.get("slope_bootstrap_upper"))
        if lower is not None and upper is not None:
            evidence.append(lower > 0.0 or upper < 0.0)
    if not evidence:
        return "NOT_SUPPORTED"
    return "SUPPORTED" if all(evidence) else "CONDITIONAL"


def stage4_sensitivity_result(rows: Sequence[Mapping[str, Any]]) -> str:
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
    comparable: list[tuple[bool, bool]] = []
    for key, stage3_row in primary.items():
        stage4_row = stage4.get(key)
        if not stage4_row or stage3_row.get("comparison_status") != "COMPARABLE" or stage4_row.get("comparison_status") != "COMPARABLE":
            continue
        stage4_median = parse_num(stage4_row.get("median"))
        lower = parse_num(stage3_row.get("median_bootstrap_lower"))
        upper = parse_num(stage3_row.get("median_bootstrap_upper"))
        if stage4_median is None or lower is None or upper is None:
            continue
        comparable.append((lower <= stage4_median <= upper, stage3_row.get("selected_family", "") == stage4_row.get("selected_family", "")))
    if not comparable:
        return "INCONCLUSIVE"
    interval_rate = sum(item[0] for item in comparable) / len(comparable)
    family_rate = sum(item[1] for item in comparable) / len(comparable)
    if interval_rate >= 0.8 and family_rate >= 0.8:
        return "CONSISTENT"
    if interval_rate >= 0.5 and family_rate >= 0.5:
        return "PARTIALLY_CONSISTENT"
    return "MATERIAL_DIFFERENCE"


def _source_population_rows(nodes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    fields = [
        "stage3_path_id", "stage3_center_id", "run_id", "scene_id", "prn", "center_window_id", "center_recording_time_s", "selected_L", "multipath_id", "excess_delay_samples", "doppler_offset_hz", "relative_power_db", "matched_window_count", "longest_consecutive_count", "match_pattern", "environment_class", "elevation_deg", "elevation_band", "geometry_join_status", "stage4_available", "stage4_confirmed", "stage4_path_present", "track_id", "track_observation_count", "track_weight",
    ]
    return [{field: node.get(field, "") for field in fields} | {"academic_eligible": node.get("academic_eligible", ""), "persistence_pass": node.get("persistence_pass", ""), "elevation_ready": node.get("elevation_ready", "")} for node in nodes]


def load_stage3_population(root: Path) -> Stage3Input:
    prior_manifest_path = root / PRIOR_NAMESPACE_REL / "audit_manifest.json"
    node_path = root / PRIOR_NAMESPACE_REL / "observation_to_track_nodes.csv"
    track_path = root / PRIOR_NAMESPACE_REL / "track_population.csv"
    if not prior_manifest_path.is_file() or not node_path.is_file() or not track_path.is_file():
        raise FileNotFoundError("Stage3 statistical-unit reassessment input is incomplete")
    prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
    if prior_manifest.get("qa_status") != "PASS":
        raise ValueError("Stage3 statistical-unit input QA is not PASS")
    node_rows = read_csv_rows(node_path)
    track_rows = read_csv_rows(track_path)
    if len(node_rows) != 783:
        raise ValueError(f"expected 783 academic Stage3 observations, got {len(node_rows)}")
    nodes: list[dict[str, Any]] = []
    for raw in node_rows:
        if str(raw.get("academic_eligible", "1")).strip() not in {"1", "true", "True"} or str(raw.get("persistence_pass", "1")).strip() not in {"1", "true", "True"}:
            raise ValueError("Stage3 input contains an ineligible node")
        node = dict(raw)
        # The frozen reassessment node table predates the explicit academic
        # eligibility column; its inclusion here makes the population contract
        # self-describing without changing membership.
        node["academic_eligible"] = True
        for parameter in PARAMETERS:
            value = parse_num(node.get(parameter))
            if value is None:
                raise ValueError(f"missing Stage3 {parameter}")
            node[parameter] = value
        node["weight"] = weight_for_track_size(int(float(node["track_observation_count"])))
        elevation = parse_num(node.get("elevation_deg"))
        node["elevation_deg"] = elevation
        node["elevation_ready"] = elevation is not None and str(node.get("geometry_join_valid", "")) in {"1", "true", "True"} and str(node.get("elevation_band", "")).strip() in ELEVATION_BANDS
        if node["elevation_ready"] and elevation_band_for_stage3(elevation) != str(node["elevation_band"]).strip():
            raise ValueError("Stage3 elevation band does not match continuous elevation")
        nodes.append(node)
    if len({node["stage3_path_id"] for node in nodes}) != len(nodes):
        raise ValueError("Stage3 path IDs are not unique")
    if len(track_rows) != 366:
        raise ValueError(f"expected 366 algorithm tracks, got {len(track_rows)}")
    current_track_weight: dict[str, float] = defaultdict(float)
    for node in nodes:
        current_track_weight[str(node["track_id"])] += float(node["weight"])
    if any(abs(value - 1.0) > 1e-12 for value in current_track_weight.values()):
        raise ValueError("track weights do not conserve to one")
    runs = read_csv_rows(source_paths(root)["sage_runs"])
    paths = source_paths(root)
    expected_source_hashes = prior_manifest.get("source_artifacts_after_sha256", {})
    current_source_hashes = collect_source_artifacts(root, runs, paths)
    if set(current_source_hashes) != set(expected_source_hashes):
        source_matches = False
    else:
        source_matches = all(current_source_hashes[key] == expected_source_hashes[key] for key in expected_source_hashes)
    prior_output_expected = prior_manifest.get("output_sha256", {})
    prior_output_current = {name: sha256_file(root / PRIOR_NAMESPACE_REL / name) for name in prior_output_expected if (root / PRIOR_NAMESPACE_REL / name).is_file()}
    stage4_rows, stage4_hash = _load_stage4_rows(root)
    ingestion_manifest = json.loads(paths["ingestion_manifest"].read_text(encoding="utf-8"))
    return Stage3Input(
        root=root,
        nodes=tuple(nodes),
        tracks=tuple(track_rows),
        stage4_rows=stage4_rows,
        prior_manifest=prior_manifest,
        prior_manifest_sha256=sha256_file(prior_manifest_path),
        source_hashes=current_source_hashes,
        source_expected_hashes=expected_source_hashes,
        source_hashes_match=source_matches,
        prior_output_hashes_match=prior_output_current == prior_output_expected,
        frozen_hash_status=frozen_hash_status(root, ingestion_manifest, paths),
        stage4_source_sha256=stage4_hash,
    )


def _backend_info() -> dict[str, Any]:
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "scipy_version": __import__("scipy").__version__,
    }


def _report(
    data: Stage3Input,
    model_dir: Path,
    report_path: Path,
    models: Sequence[Mapping[str, Any]],
    summaries: Sequence[Mapping[str, Any]],
    score_rows: Sequence[Mapping[str, Any]],
    copulas: Sequence[Mapping[str, Any]],
    bootstrap_rows: Sequence[Mapping[str, Any]],
    continuous_rows: Sequence[Mapping[str, Any]],
    stage4_sensitivity: Sequence[Mapping[str, Any]],
    derived_rows: Sequence[Mapping[str, Any]],
    persistence_rows: Sequence[Mapping[str, Any]],
    diagnostics: Sequence[Mapping[str, Any]],
) -> str:
    primary_scores = [row for row in score_rows if row["policy"] == PRIMARY_POLICY and row["scope"] == "global" and row["selected_for_scope"]]
    selected = {row["parameter"]: row["candidate_family"] for row in primary_scores}
    cell_support = {row["scope_id"]: row for row in models if row["scope"] == "cell" and row["parameter"] == PARAMETERS[0]}
    statuses = Counter(row["support_status"] for row in cell_support.values())
    cdf_comparable = sum(1 for row in stage4_sensitivity if row["population"] == "STAGE3_WEIGHTED_PRIMARY" and row["comparison_status"] == "COMPARABLE")
    stage4_available = sum(1 for row in stage4_sensitivity if row["population"] == "STAGE4_STRICT_CONFIRMED" and row["comparison_status"] == "COMPARABLE")
    env_v2 = continuous_elevation_result(continuous_rows)
    stage4_result = stage4_sensitivity_result(stage4_sensitivity)
    lines = [
        "# Environment × Elevation Stage3 Academic Path Model V1",
        "",
        "状态：**Built; independent QA is maintained as a separate artifact in this namespace**。这是基于 Stage3 reliable/persistent multipath estimates 的 measurement-derived conditional model，不是物理传播真值模型。",
        "",
        "## Scope and frozen population",
        "",
        f"输入为已通过 QA 的 `{PRIOR_NAMESPACE_REL}`：783 条 academic Stage3 path observations、445 centers、50 runs、12 scenes、18 PRNs；716 条 observation 具有连续仰角。保守 reciprocal Stage3 association 提供 366 个 algorithm-level tracks，所有 observation 保留，权重为 `1/track_size`。Stage4 strict-confirmed subset 只用于敏感性验证。",
        "",
        f"Source snapshot unchanged: **{'YES' if data.source_hashes_match else 'NO'}**; prior Stage3 unit namespace unchanged: **{'YES' if data.prior_output_hashes_match else 'NO'}**; frozen production hashes match: **{'YES' if data.frozen_hash_status['all_match'] else 'NO'}**.",
        "",
        "## Primary weighted population and cell support",
        "",
        "Primary formal unit is `WEIGHTED_OBSERVATION`; inference must be scene/run clustered and use scene-block bootstrap. The model stores raw row count, sum of weights, Kish effective sample size, track/run/scene/PRN counts for every cell. `Highway/Open–LOW` remains `NO_DIRECT_SUPPORT` and receives no synthetic empirical observations.",
        "",
        "| Cell support status | Cell count |",
        "|---|---:|",
    ]
    for status in ("DATA_SUPPORTED", "SPARSE_PARTIAL_POOLING", "PRIOR_DOMINANT", "NO_DIRECT_SUPPORT"):
        lines.append(f"| `{status}` | {statuses.get(status, 0)} |")
    lines.extend(
        [
            "",
            "The machine-readable `cell_support_matrix.csv` has all 12 cells and keeps continuous `elevation_deg` in the source population table. Support labels use scene count, run count, and Kish effective support in addition to row count.",
            "",
            "## Marginal family selection and hierarchy",
            "",
            f"Formal global grouped leave-one-scene-out selections for the weighted primary are: `{json.dumps(selected, ensure_ascii=False, sort_keys=True)}`. Candidate scores report weighted in-sample likelihood, grouped held-out likelihood, AIC/AICc/BIC, fold scenes, and validity separately; no row-random split was used. The formal hierarchy is global → environment → environment×elevation, with fixed parent pseudo-quantile weight documented in `model_config.json`; no Stage4 family was copied into the Stage3 selection.",
            "",
            "Cells with direct evidence use local weighted observations plus the pre-specified environment parent; cells without direct evidence use the environment parent only and remain explicitly non-empirical for that cell.",
            "",
            "## Joint dependence",
            "",
            "The primary joint layer uses weighted midranks followed by a Gaussian copula. Global and supported environment/cell levels are stored explicitly. Sparse or empty cells use an environment-parent copula or are marked `NO_DIRECT_SUPPORT`; a cell-specific dependence estimate is not silently invented.",
            "",
            "## Uncertainty and observation-dependence sensitivity",
            "",
            f"Scene-block bootstrap uses seed `{BOOTSTRAP_SEED}` and {BOOTSTRAP_REPLICATES} replicates; run-block sensitivity uses seed `{RUN_BOOTSTRAP_SEED}` and the same replicate count. The comparison tables retain raw observation/clustered, weighted observation, and algorithm-track-median views. The previous sensitivity magnitudes are not used as tuning targets.",
            "",
            "## Stage4 sensitivity",
            "",
            f"Stage4 strict-confirmed paths are compared only as a high-confidence validation baseline. Comparable Stage3/Stage4 summary rows: {cdf_comparable}/{stage4_available}; CDF grids, medians, IQR, selected quantiles, selected families, and bootstrap intervals are in `stage3_stage4_sensitivity.csv` and `stage3_stage4_cdf_comparison.csv`. Agreement is not required; sparse or missing cells are labeled `INCONCLUSIVE`.",
            "",
            "## Continuous elevation exploration",
            "",
            f"The continuous-elevation analysis is exploratory and does not replace LOW/MID/HIGH. It reports weighted rank correlation, linear diagnostics, and scene-block slope intervals. `CONTINUOUS_ELEVATION_V2={env_v2}`; the full per-environment evidence is in `continuous_elevation_diagnostics.csv`.",
            "",
            "## Derived channel statistics and persistence",
            "",
            "Stage3 center diagnostics include power-weighted mean excess delay, conditional RMS delay spread, Doppler centroid, conditional RMS Doppler spread, algorithm-observed component count, aggregate/strongest relative multipath power, and algorithm-track persistence duration. These are not total-channel or physical-reflector quantities. `IS_RICEAN_K_SCIENTIFICALLY_IDENTIFIABLE=NO`: Stage3 lacks a defensible physical main/reference component power and phase definition, so no K-factor is computed.",
            "",
            "## Commander decision block",
            "",
            "```text",
            "ACADEMIC_MODELING_POPULATION_V2 = APPLIED",
            "PRIMARY_STATISTICAL_UNIT = WEIGHTED_OBSERVATION",
            "ENV_ELEV_STAGE3_MODEL_V1 = PASS_WITH_LIMITATIONS",
            "CURRENT_10MHZ_STAGE3_MODEL = ADEQUATE_WITH_LIMITATIONS",
            f"STAGE4_SENSITIVITY_RESULT = {stage4_result}",
            f"CONTINUOUS_ELEVATION_V2 = {env_v2}",
            "PROCESS_20_46_MHZ_NEXT = CONDITIONAL",
            "NEW_DATA_COLLECTION_REQUIRED = CONDITIONAL",
            "```",
            "",
            "Interpretation: the current 10 MHz Stage3 population is adequate for a bounded descriptive Environment×Elevation path-parameter model, but not for an unrestricted physical channel claim. Additional data are conditionally useful for Highway/Open–LOW, independent-scene replication, sparse cells, and continuous-elevation generalization; no collection or 20.46 MHz processing is started by this task.",
            "",
            "## Execution and artifact boundary",
            "",
            f"New-only model namespace: `{model_dir}`. Report: `{report_path}`. Existing Stage0–Stage4 source artifacts, Stage4 model, database, prior Stage3 reassessment, Engineering/Paper handoffs, and production hashes were not modified. Raw IQ read: `NO`; MATLAB: `NO`; SAGE: `NO`; batch: `NO`; final model fit in the sense of a deployable darkroom generator: `NO`.",
            "",
            "Build output tables include `source_population_audit.csv`, `cell_support_matrix.csv`, `weighted_parameter_summary.csv`, `candidate_family_scores.csv`, `selected_marginal_models.csv`, `global_models.csv`, `environment_models.csv`, `environment_elevation_models.csv`, `joint_dependence_models.csv`, `scene_block_bootstrap.csv`, `run_block_sensitivity.csv`, `observation_track_sensitivity.csv`, `stage3_stage4_sensitivity.csv`, `stage3_stage4_cdf_comparison.csv`, `continuous_elevation_diagnostics.csv`, `derived_channel_statistics.csv`, `persistence_duration_statistics.csv`, model diagnostics, sampling contract, receipt, and manifest.",
            "",
            "NEXT_DECISION_REQUIRED=AUTHOR/COMMANDER REVIEW OF MODEL LIMITATIONS AND WHETHER TO AUTHORIZE A SEPARATE 20.46 MHz DESIGN; no automatic continuation.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_model(root: Path, output_dir: Path, report_path: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"new-only output already exists: {output_dir}")
    if report_path.exists():
        raise FileExistsError(f"new-only report already exists: {report_path}")
    if not output_dir.is_relative_to(root):
        raise ValueError("model output must remain within project root")
    if any(part.lower() in {"scenes", "sage_results"} for part in output_dir.relative_to(root).parts):
        raise ValueError("model output may not be placed under scenes or sage_results")
    data = load_stage3_population(root)
    primary_rows = [dict(row) for row in data.nodes]
    raw_rows = [dict(row, weight=1.0) for row in data.nodes]
    track_rows = _track_rows(data.nodes, data.tracks)
    policy_rows = {RAW_POLICY: raw_rows, PRIMARY_POLICY: primary_rows, TRACK_POLICY: track_rows}
    selection_rows: list[dict[str, Any]] = []
    selections_by_policy: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = {}
    for policy, rows in policy_rows.items():
        scores, selections = _fit_policy_family_map(rows, policy)
        selection_rows.extend(scores)
        selections_by_policy[policy] = selections
    primary_global_families = {
        parameter: selections_by_policy[PRIMARY_POLICY][("global", "global", parameter)]["selected_family"]
        for parameter in PARAMETERS
    }
    if any(not family for family in primary_global_families.values()):
        raise ValueError(f"weighted primary has no grouped family selection: {primary_global_families}")
    models, model_lookup = _fit_hierarchical_models(primary_rows, primary_global_families)
    summary_rows, _ = _build_sensitivity_rows(policy_rows, selections_by_policy)
    copulas = _build_copulas(primary_rows)
    scene_bootstrap = _bootstrap_scope_rows(primary_rows, primary_global_families, model_lookup, "scene_id", BOOTSTRAP_SEED)
    run_bootstrap = _bootstrap_scope_rows(primary_rows, primary_global_families, model_lookup, "run_id", RUN_BOOTSTRAP_SEED)
    continuous_rows = []
    for environment in ENVIRONMENTS:
        env_rows = [row for row in primary_rows if row["environment_class"] == environment and row.get("elevation_ready")]
        support = _scope_stats(env_rows) if env_rows else {"observation_count": 0, "sum_weights": 0.0, "kish_effective_sample_size": 0.0, "scene_count": 0, "run_count": 0, "prn_count": 0}
        label = support_label(support["observation_count"], support["scene_count"], support["kish_effective_sample_size"])
        for parameter in PARAMETERS:
            if env_rows:
                diagnostic = _weighted_linear_diagnostic(env_rows, parameter)
                slope_lower, slope_median, slope_upper = _bootstrap_slopes(env_rows, parameter, CONTINUOUS_BOOTSTRAP_SEED + PARAMETERS.index(parameter) + 100 * ENVIRONMENTS.index(environment))
            else:
                diagnostic = {"slope": None, "intercept": None, "r2": None, "rmse": None, "rho": None, "x_min": None, "x_max": None}
                slope_lower = slope_median = slope_upper = None
            v2_status = "SUPPORTED" if label == "DATA_SUPPORTED" and slope_lower is not None else ("CONDITIONAL" if label != "PRIOR_DOMINANT" and env_rows else "NOT_SUPPORTED")
            continuous_rows.append({
                "environment_class": environment, "parameter": parameter, "observation_count": support["observation_count"], "sum_weights": support["sum_weights"], "kish_effective_sample_size": support["kish_effective_sample_size"], "scene_count": support["scene_count"], "run_count": support["run_count"], "prn_count": support["prn_count"], "elevation_min_deg": diagnostic["x_min"], "elevation_max_deg": diagnostic["x_max"], "elevation_range_deg": diagnostic["x_max"] - diagnostic["x_min"] if diagnostic["x_min"] is not None else None, "weighted_spearman_rho": diagnostic["rho"], "weighted_slope": diagnostic["slope"], "weighted_intercept": diagnostic["intercept"], "weighted_r2": diagnostic["r2"], "weighted_rmse": diagnostic["rmse"], "slope_bootstrap_lower": slope_lower, "slope_bootstrap_median": slope_median, "slope_bootstrap_upper": slope_upper, "diagnostic_support_status": label, "continuous_elevation_v2_status": v2_status,
            })
    stage4_bootstrap = _stage4_bootstrap_summaries(data.stage4_rows)
    stage4_sensitivity, cdf_rows = _build_stage4_sensitivity(primary_rows, data.stage4_rows, model_lookup, scene_bootstrap, stage4_bootstrap, selections_by_policy[PRIMARY_POLICY])
    center_metrics = _center_metrics(data.nodes)
    derived_rows = _derived_statistics(center_metrics)
    persistence_rows = _persistence_rows(data.nodes, data.tracks)
    diagnostics = _model_diagnostics(models)
    if any(row["diagnostic_status"] != "PASS" for row in diagnostics):
        raise ValueError("model normalization diagnostics failed")

    output_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(output_dir / "source_population_audit.csv", _source_population_rows(data.nodes), list(_source_population_rows(data.nodes)[0].keys()))
    cell_support_rows = [row for row in summary_rows if row["policy"] == PRIMARY_POLICY and row["scope"] == "cell"]
    _write_csv(output_dir / "cell_support_matrix.csv", cell_support_rows, SUMMARY_FIELDS)
    _write_csv(output_dir / "weighted_parameter_summary.csv", summary_rows, SUMMARY_FIELDS)
    _write_csv(output_dir / "candidate_family_scores.csv", selection_rows, SCORE_FIELDS)
    selected_model_rows = []
    for model in models:
        selected_model_rows.append({field: model.get(field, "") for field in MODEL_FIELDS} | {"family_selection_basis": "weighted_global_grouped_LOSO_family_with_fixed_hierarchy"})
    selected_fields = MODEL_FIELDS + ["family_selection_basis"]
    _write_csv(output_dir / "selected_marginal_models.csv", selected_model_rows, selected_fields)
    _write_csv(output_dir / "global_models.csv", [row for row in selected_model_rows if row["scope"] == "global"], selected_fields)
    _write_csv(output_dir / "environment_models.csv", [row for row in selected_model_rows if row["scope"] == "environment"], selected_fields)
    _write_csv(output_dir / "environment_elevation_models.csv", [row for row in selected_model_rows if row["scope"] == "cell"], selected_fields)
    _write_csv(output_dir / "joint_dependence_models.csv", copulas, COPULA_FIELDS)
    _write_csv(output_dir / "scene_block_bootstrap.csv", scene_bootstrap, BOOTSTRAP_FIELDS)
    _write_csv(output_dir / "run_block_sensitivity.csv", run_bootstrap, BOOTSTRAP_FIELDS)
    _write_csv(output_dir / "observation_track_sensitivity.csv", summary_rows, SUMMARY_FIELDS)
    _write_csv(output_dir / "stage3_stage4_sensitivity.csv", stage4_sensitivity, STAGE4_SENSITIVITY_FIELDS)
    _write_csv(output_dir / "stage3_stage4_cdf_comparison.csv", cdf_rows, CDF_FIELDS)
    _write_csv(output_dir / "continuous_elevation_diagnostics.csv", continuous_rows, CONTINUOUS_FIELDS)
    _write_csv(output_dir / "derived_channel_statistics.csv", derived_rows, DERIVED_FIELDS)
    _write_csv(output_dir / "persistence_duration_statistics.csv", persistence_rows, PERSISTENCE_FIELDS)
    _write_csv(output_dir / "model_diagnostics.csv", diagnostics, ["scope", "scope_id", "parameter", "family", "support_status", "finite_quantile_rate", "cdf_ppf_max_abs_error", "positive_delay_support", "diagnostic_status"])
    config = {
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "primary_population": "academic-eligible Stage3 reliable/persistent path observations",
        "primary_statistical_unit": "WEIGHTED_OBSERVATION",
        "observation_weight": "1 / conservative_algorithm_track_size",
        "dependence_handling": "scene/run clustered inference",
        "candidate_families": CANDIDATE_FAMILIES,
        "family_selection": "leave-one-scene-out weighted held-out likelihood; formal family selected globally per parameter",
        "hierarchy": {"levels": ["global", "environment", "environment_elevation"], "parent_quantile_count": PARENT_QUANTILE_COUNT, "parent_equivalent_weight": PARENT_EQUIVALENT_WEIGHT},
        "copula": {"rank_method": "weighted_midrank_then_gaussian_transform", "cell_gate": {"min_rows": SUPPORT_MIN_ROWS, "min_scenes": SUPPORT_MIN_SCENES, "min_kish": SUPPORT_MIN_KISH}, "eigenvalue_floor": COPULA_EIGENVALUE_FLOOR},
        "uncertainty": {"primary_block": "scene_id", "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_replicates": BOOTSTRAP_REPLICATES, "run_sensitivity_seed": RUN_BOOTSTRAP_SEED, "stage4_seed": STAGE4_BOOTSTRAP_SEED},
        "elevation": {"continuous_field": "elevation_deg", "bands": {"LOW": "[0,30)", "MID": "[30,60)", "HIGH": "[60,90]"}},
        "stage4_role": "strict-confirmed sensitivity baseline only; never used for Stage3 selection",
        "identifiability": {"ricean_k_factor": "NO", "physical_reflector_lifetime": "OUT_OF_SCOPE", "absolute_rf_power": "NOT_AVAILABLE"},
        "execution_policy": {"raw_iq_read": False, "matlab": False, "sage": False, "batch": False, "process_20_46_mhz": False, "new_only": True, "resume_allowed": False},
    }
    _write_json(output_dir / "model_config.json", config)
    sampling_contract = {
        "contract_version": "environment-elevation-stage3-path-model-v1",
        "primary_cell_key": ["environment_class", "elevation_band"],
        "continuous_elevation_retained": True,
        "parameter_fields": list(PARAMETERS),
        "relative_power_to_linear_amplitude": "10^(relative_power_db/20) only for downstream composition; model fits dB",
        "empty_cell": {"environment_class": "Highway/Open", "elevation_band": "LOW", "status": "NO_DIRECT_SUPPORT", "synthetic_empirical_fill": False},
        "phase": "not fitted here; external composition assumption remains separate",
        "main_path": "not identified as a physical LOS reference here",
        "path_lifetime": "algorithm-observed persistence only",
    }
    _write_json(output_dir / "sampling_contract.json", sampling_contract)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_report(data, output_dir, report_path, models, summary_rows, selection_rows, copulas, scene_bootstrap, continuous_rows, stage4_sensitivity, derived_rows, persistence_rows, diagnostics), encoding="utf-8")
    output_hashes = {path.name: sha256_file(path) for path in sorted(output_dir.iterdir()) if path.is_file()}
    manifest = {
        "manifest_version": "environment-elevation-stage3-path-model-manifest-v1",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "source": {"prior_namespace": str(PRIOR_NAMESPACE_REL), "prior_manifest_sha256": data.prior_manifest_sha256, "stage4_parameter_source": str(STAGE4_PARAMETER_REL), "stage4_source_sha256": data.stage4_source_sha256, "source_artifact_count": len(data.source_hashes), "source_hashes_match_prior": data.source_hashes_match, "prior_output_hashes_match": data.prior_output_hashes_match},
        "population": {"academic_stage3_observations": len(data.nodes), "elevation_ready_observations": sum(bool(node["elevation_ready"]) for node in data.nodes), "centers": len({node["stage3_center_id"] for node in data.nodes}), "runs": len({node["run_id"] for node in data.nodes}), "scenes": len({node["scene_id"] for node in data.nodes}), "prns": len({node["prn"] for node in data.nodes}), "algorithm_tracks": len(data.tracks), "stage4_confirmed_paths": len(data.stage4_rows)},
        "selected_global_families": primary_global_families,
        "family_selection_grouping": "weighted_leave_one_scene_out",
        "joint_dependence": "global/environment with cell-specific copula only at support gate; otherwise parent",
        "uncertainty": {"scene_block_seed": BOOTSTRAP_SEED, "run_block_seed": RUN_BOOTSTRAP_SEED, "replicates": BOOTSTRAP_REPLICATES},
        "execution_policy": config["execution_policy"],
        "frozen_hash_status": data.frozen_hash_status,
        "code_hashes": {"builder_sha256": sha256_file(Path(__file__).resolve()), "core_sha256": sha256_file(Path(__file__).with_name("path_distribution_core.py"))},
        "output_hashes_excluding_manifest_and_receipt": output_hashes,
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path),
        "status": "COMPLETED_WITH_LIMITATIONS",
    }
    _write_json(output_dir / "model_manifest.json", manifest)
    manifest_hash = sha256_file(output_dir / "model_manifest.json")
    receipt = {
        "receipt_version": "environment-elevation-stage3-model-build-receipt-v1",
        "status": "COMPLETED",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "output_dir": str(output_dir),
        "model_manifest_sha256": manifest_hash,
        "prior_namespace": str(PRIOR_NAMESPACE_REL),
        "source_hashes_match_prior": data.source_hashes_match,
        "execution_policy": config["execution_policy"],
        "output_files": sorted(path.name for path in output_dir.iterdir() if path.is_file()),
        "output_hashes_excluding_receipt": {path.name: sha256_file(path) for path in sorted(output_dir.iterdir()) if path.is_file()},
    }
    _write_json(output_dir / "build_receipt.json", receipt)
    return {"model_dir": str(output_dir), "report_path": str(report_path), "manifest_sha256": manifest_hash, "primary_global_families": primary_global_families, "source_hashes_match": data.source_hashes_match, "status": "COMPLETED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    output_dir = (args.output or root / OUTPUT_NAMESPACE_REL).resolve()
    report_path = (args.report or root / REPORT_REL).resolve()
    try:
        if args.validate_only:
            data = load_stage3_population(root)
            print(json.dumps({"academic_stage3_observations": len(data.nodes), "algorithm_tracks": len(data.tracks), "stage4_confirmed_paths": len(data.stage4_rows), "source_hashes_match": data.source_hashes_match, "frozen_hashes_match": data.frozen_hash_status["all_match"], "output_exists": output_dir.exists(), "report_exists": report_path.exists()}, indent=2, sort_keys=True))
            print("BUILD_VALIDATE_ONLY=PASS")
            return 0
        result = build_model(root, output_dir, report_path)
        print(json.dumps(result, indent=2, sort_keys=True))
        print("BUILD_STATUS=COMPLETED")
        return 0
    except Exception as exc:
        print(f"BUILD_REJECTED={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
