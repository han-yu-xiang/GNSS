from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import betaln, betainc, logsumexp
from scipy.stats import norm


OUTPUT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = (
    Path(r"E:\GNSS_Multipath_Project")
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/"
    "population/gmm_feature_population.csv"
)
ENVIRONMENTS = ("Urban", "Mountain/Valley")
ELEVATION_BANDS = ("LOW", "MID", "HIGH")
CELL_ORDER = tuple(f"{environment}/{band}" for environment in ENVIRONMENTS for band in ELEVATION_BANDS)
POWER_FIELD = "relative_power_db"
WEIGHT_FIELD = "track_weight_recomputed_primary"
MIN_COMPONENT_MASS = 5.0
RANDOM_SEED = 20260831
DB_TO_LINEAR = np.log(10.0) / 10.0


def _bool_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def load_power_population(path: Path = SOURCE_CSV) -> pd.DataFrame:
    frame = pd.read_csv(path)
    mask = _bool_mask(frame["primary_population_included"]) & _bool_mask(frame["elevation_ready"]) & _bool_mask(frame["cell_ready"])
    frame = frame.loc[mask].copy()
    frame["cell_id"] = frame["environment_class"].astype(str) + "/" + frame["elevation_band"].astype(str)
    frame[[POWER_FIELD, WEIGHT_FIELD]] = frame[[POWER_FIELD, WEIGHT_FIELD]].apply(pd.to_numeric, errors="coerce")
    if frame[[POWER_FIELD, WEIGHT_FIELD]].isna().any().any() or (frame[WEIGHT_FIELD] <= 0).any():
        raise ValueError("non-finite or non-positive relative-power input")
    ratio = 10.0 ** (frame[POWER_FIELD].to_numpy(float) / 10.0)
    if not np.isfinite(ratio).all() or not np.all((ratio > 0) & (ratio <= 1)):
        raise ValueError("relative powers must map to linear ratios in (0, 1]")
    return frame


def _weighted_mean_variance(values: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    total = float(np.sum(weights))
    mean = float(np.sum(weights * values) / total)
    variance = float(np.sum(weights * (values - mean) ** 2) / total)
    return mean, max(variance, 1e-12)


def _normal_logpdf(values: np.ndarray, mean: float, std: float) -> np.ndarray:
    return norm.logpdf(values, loc=mean, scale=max(float(std), 1e-8))


def _normal_cdf(values: np.ndarray, mean: float, std: float) -> np.ndarray:
    return norm.cdf(values, loc=mean, scale=max(float(std), 1e-8))


def _fit_single_gaussian(values: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    mean, variance = _weighted_mean_variance(values, weights)
    std = float(np.sqrt(variance))
    log_likelihood = float(np.sum(weights * _normal_logpdf(values, mean, std)))
    return {
        "family": "single_gaussian_db",
        "status": "fit_ok",
        "parameters": {"mean_db": mean, "std_db": std},
        "weighted_log_likelihood": log_likelihood,
        "parameter_count": 2,
    }


def _fit_weighted_gaussian_mixture_1d(
    values: np.ndarray,
    weights: np.ndarray,
    n_components: int = 2,
    *,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if len(values) < n_components or not np.isfinite(values).all() or not np.isfinite(weights).all() or np.any(weights <= 0):
        return {"family": "gaussian_mixture_db", "status": "fit_failed", "n_components": n_components}
    total = float(np.sum(weights))
    mean, variance = _weighted_mean_variance(values, weights)
    variance_floor = max(1e-5, variance * 1e-5)
    order = np.argsort(values, kind="mergesort")
    cumulative = np.cumsum(weights[order]) / total
    rng = np.random.default_rng(seed)
    best: dict[str, Any] | None = None
    for restart in range(8):
        targets = (np.arange(n_components, dtype=float) + 0.5) / n_components
        indices = [int(order[min(np.searchsorted(cumulative, target), len(order) - 1)]) for target in targets]
        means = values[np.asarray(indices)] + (0.0 if restart == 0 else rng.normal(0, 0.03 * np.sqrt(variance), n_components))
        variances = np.full(n_components, max(variance, variance_floor), dtype=float)
        proportions = np.full(n_components, 1.0 / n_components, dtype=float)
        previous = -np.inf
        failed = False
        for iteration in range(300):
            component_logpdf = np.column_stack([_normal_logpdf(values, means[i], np.sqrt(variances[i])) for i in range(n_components)])
            log_joint = component_logpdf + np.log(np.maximum(proportions, 1e-300))[None, :]
            log_density = logsumexp(log_joint, axis=1)
            responsibilities = np.exp(log_joint - log_density[:, None])
            masses = np.sum(weights[:, None] * responsibilities, axis=0)
            if np.any(masses <= 1e-10) or not np.isfinite(masses).all():
                failed = True
                break
            means = np.sum(weights[:, None] * responsibilities * values[:, None], axis=0) / masses
            variances = np.sum(weights[:, None] * responsibilities * (values[:, None] - means[None, :]) ** 2, axis=0) / masses
            variances = np.maximum(variances, variance_floor)
            proportions = masses / total
            log_likelihood = float(np.sum(weights * log_density))
            if not np.isfinite(log_likelihood):
                failed = True
                break
            if abs(log_likelihood - previous) <= 1e-8 * (1.0 + abs(log_likelihood)):
                break
            previous = log_likelihood
        if failed:
            continue
        component_logpdf = np.column_stack([_normal_logpdf(values, means[i], np.sqrt(variances[i])) for i in range(n_components)])
        log_density = logsumexp(component_logpdf + np.log(proportions)[None, :], axis=1)
        responsibilities = np.exp(component_logpdf + np.log(proportions)[None, :] - log_density[:, None])
        masses = np.sum(weights[:, None] * responsibilities, axis=0)
        candidate = {
            "family": "gaussian_mixture_db",
            "status": "fit_ok",
            "n_components": n_components,
            "parameters": {
                "means_db": means.tolist(),
                "stds_db": np.sqrt(variances).tolist(),
                "proportions": proportions.tolist(),
            },
            "component_effective_mass": masses.tolist(),
            "weighted_log_likelihood": float(np.sum(weights * log_density)),
            "parameter_count": 5,
            "iterations": iteration + 1,
        }
        if best is None or candidate["weighted_log_likelihood"] > best["weighted_log_likelihood"]:
            best = candidate
    return best if best is not None else {"family": "gaussian_mixture_db", "status": "fit_failed", "n_components": n_components}


def _fit_beta_ratio(values_db: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    ratio = np.power(10.0, values_db / 10.0)
    if not np.all((ratio > 0) & (ratio < 1)):
        return {"family": "beta_linear_ratio", "status": "not_applicable", "reason": "ratio_outside_open_unit_interval"}
    mean, variance = _weighted_mean_variance(ratio, weights)
    maximum_variance = mean * (1.0 - mean)
    if variance <= 0 or variance >= maximum_variance:
        return {"family": "beta_linear_ratio", "status": "fit_failed", "reason": "invalid_beta_moments"}
    concentration = maximum_variance / variance - 1.0
    alpha = max(mean * concentration, 1e-6)
    beta = max((1.0 - mean) * concentration, 1e-6)
    log_density_ratio = (alpha - 1.0) * np.log(ratio) + (beta - 1.0) * np.log1p(-ratio) - betaln(alpha, beta)
    # Convert the ratio density to a density in dB for likelihood comparison.
    log_jacobian = np.log(DB_TO_LINEAR) + np.log(ratio)
    return {
        "family": "beta_linear_ratio",
        "status": "fit_ok",
        "parameters": {"alpha": float(alpha), "beta": float(beta)},
        "weighted_log_likelihood": float(np.sum(weights * (log_density_ratio + log_jacobian))),
        "parameter_count": 2,
        "transformation": "r=10^(P_db/10), f_Pdb=f_r(r)*ln(10)/10*r",
    }


def fit_power_candidates(values: np.ndarray, weights: np.ndarray) -> list[dict[str, Any]]:
    """Fit the planned marginal candidates to path-relative power."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.ndim != 1 or len(values) != len(weights) or not np.isfinite(values).all() or not np.isfinite(weights).all():
        raise ValueError("values and weights must be finite one-dimensional arrays")
    if np.any(weights <= 0):
        raise ValueError("weights must be positive")
    candidates = [_fit_single_gaussian(values, weights)]
    mixture = _fit_weighted_gaussian_mixture_1d(values, weights, 2)
    if mixture["status"] == "fit_ok" and np.min(mixture["component_effective_mass"]) < MIN_COMPONENT_MASS:
        mixture["status"] = "rejected"
        mixture["reason"] = "component_effective_mass_below_5"
    candidates.append(mixture)
    candidates.append(_fit_beta_ratio(values, weights))
    for candidate in candidates:
        if candidate.get("status") != "fit_ok":
            continue
        n_eff = float(np.sum(weights) ** 2 / np.sum(weights**2))
        candidate["n_eff"] = n_eff
        candidate["bic"] = float(-2.0 * candidate["weighted_log_likelihood"] + candidate["parameter_count"] * np.log(max(n_eff, 2.0)))
    return candidates


def evaluate_power_pdf(model: dict[str, Any], x_db: np.ndarray) -> np.ndarray:
    """Evaluate a selected model as a density with respect to dB power."""
    x_db = np.asarray(x_db, dtype=float)
    family = model["family"]
    parameters = model["parameters"]
    if family == "single_gaussian_db":
        return np.exp(_normal_logpdf(x_db, parameters["mean_db"], parameters["std_db"]))
    if family == "gaussian_mixture_db":
        density = np.zeros_like(x_db, dtype=float)
        for mean, std, proportion in zip(parameters["means_db"], parameters["stds_db"], parameters["proportions"]):
            density += float(proportion) * np.exp(_normal_logpdf(x_db, mean, std))
        return density
    if family == "beta_linear_ratio":
        alpha = float(parameters["alpha"])
        beta = float(parameters["beta"])
        valid = np.isfinite(x_db) & (x_db < 0.0)
        ratio = np.clip(np.power(10.0, x_db / 10.0), 1e-300, 1.0 - 1e-15)
        log_pdf = (alpha - 1.0) * np.log(ratio) + (beta - 1.0) * np.log1p(-ratio) - betaln(alpha, beta)
        output = np.zeros_like(x_db, dtype=float)
        output[valid] = np.exp(log_pdf[valid] + np.log(DB_TO_LINEAR) + np.log(ratio[valid]))
        return output
    raise ValueError(f"unknown power model family: {family}")


def _power_cdf(model: dict[str, Any], x_db: np.ndarray) -> np.ndarray:
    x_db = np.asarray(x_db, dtype=float)
    family = model["family"]
    parameters = model["parameters"]
    if family == "single_gaussian_db":
        return _normal_cdf(x_db, parameters["mean_db"], parameters["std_db"])
    if family == "gaussian_mixture_db":
        output = np.zeros_like(x_db, dtype=float)
        for mean, std, proportion in zip(parameters["means_db"], parameters["stds_db"], parameters["proportions"]):
            output += float(proportion) * _normal_cdf(x_db, mean, std)
        return output
    if family == "beta_linear_ratio":
        ratio = np.clip(np.power(10.0, x_db / 10.0), 0.0, 1.0)
        return betainc(float(parameters["alpha"]), float(parameters["beta"]), ratio)
    raise ValueError(f"unknown power model family: {family}")


def _fit_and_score_cell(cell_frame: pd.DataFrame, cell_id: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    values = cell_frame[POWER_FIELD].to_numpy(float)
    weights = cell_frame[WEIGHT_FIELD].to_numpy(float)
    full_candidates = fit_power_candidates(values, weights)
    for candidate in full_candidates:
        candidate["cell_id"] = cell_id
        candidate["row_count"] = int(len(cell_frame))
        candidate["track_count"] = int(cell_frame["track_id"].nunique())
        candidate["validation_nlpd"] = float("nan")
        candidate["validation_ecdf_distance"] = float("nan")
        candidate["validation_fold_count"] = 0
        candidate["validation_scenes"] = []
        candidate["skipped_validation_scenes"] = []
        if candidate.get("status") != "fit_ok":
            continue
        nlpd_scores: list[float] = []
        ecdf_scores: list[float] = []
        used: list[str] = []
        skipped: list[str] = []
        for scene_id in sorted(cell_frame["scene_id"].astype(str).unique()):
            test = cell_frame[cell_frame["scene_id"].astype(str) == scene_id]
            train = cell_frame[cell_frame["scene_id"].astype(str) != scene_id]
            if float(train[WEIGHT_FIELD].sum()) < MIN_COMPONENT_MASS:
                skipped.append(f"{scene_id}:insufficient_training_mass")
                continue
            train_candidates = fit_power_candidates(train[POWER_FIELD].to_numpy(float), train[WEIGHT_FIELD].to_numpy(float))
            train_candidate = next((item for item in train_candidates if item["family"] == candidate["family"] and item.get("status") == "fit_ok"), None)
            if train_candidate is None:
                skipped.append(f"{scene_id}:candidate_unavailable")
                continue
            test_values = test[POWER_FIELD].to_numpy(float)
            test_weights = test[WEIGHT_FIELD].to_numpy(float)
            log_pdf = np.log(np.maximum(evaluate_power_pdf(train_candidate, test_values), 1e-300))
            if not np.isfinite(log_pdf).all():
                skipped.append(f"{scene_id}:nonfinite_validation")
                continue
            nlpd_scores.append(float(-np.sum(test_weights * log_pdf) / np.sum(test_weights)))
            sort_order = np.argsort(test_values, kind="mergesort")
            cumulative = np.cumsum(test_weights[sort_order]) / np.sum(test_weights)
            fitted_cdf = _power_cdf(train_candidate, test_values[sort_order])
            ecdf_scores.append(float(np.mean(np.abs(cumulative - fitted_cdf))))
            used.append(scene_id)
        if nlpd_scores:
            candidate["validation_nlpd"] = float(np.mean(nlpd_scores))
            candidate["validation_ecdf_distance"] = float(np.mean(ecdf_scores))
            candidate["validation_fold_count"] = len(nlpd_scores)
            candidate["validation_scenes"] = used
        else:
            candidate["status"] = "rejected"
            candidate["reason"] = "no_valid_scene_grouped_validation_fold"
        candidate["skipped_validation_scenes"] = skipped
    valid = [item for item in full_candidates if item.get("status") == "fit_ok" and np.isfinite(item.get("validation_nlpd", np.nan))]
    selected = None
    if valid:
        selected = sorted(valid, key=lambda item: (item["validation_nlpd"], item["validation_ecdf_distance"], item["bic"]))[0]
        selected = dict(selected)
        selected["selection_rule"] = "lowest scene-grouped held-out weighted NLPD; ECDF distance and BIC tie-breaks"
    return full_candidates, selected


def _candidate_row(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "cell_id": candidate.get("cell_id", ""),
        "family": candidate.get("family", ""),
        "status": candidate.get("status", ""),
        "reason": candidate.get("reason", ""),
        "row_count": candidate.get("row_count", ""),
        "track_count": candidate.get("track_count", ""),
        "n_eff": candidate.get("n_eff", ""),
        "weighted_log_likelihood": candidate.get("weighted_log_likelihood", ""),
        "bic": candidate.get("bic", ""),
        "validation_nlpd": candidate.get("validation_nlpd", ""),
        "validation_ecdf_distance": candidate.get("validation_ecdf_distance", ""),
        "validation_fold_count": candidate.get("validation_fold_count", 0),
        "validation_scenes": ";".join(candidate.get("validation_scenes", [])),
        "skipped_validation_scenes": ";".join(candidate.get("skipped_validation_scenes", [])),
        "parameters": json.dumps(candidate.get("parameters", {})),
    }


def main() -> None:
    frame = load_power_population()
    model_dir = OUTPUT_ROOT / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    all_candidates: list[dict[str, Any]] = []
    selected_models: dict[str, Any] = {}
    summary_rows: list[dict[str, Any]] = []
    for cell_id in CELL_ORDER:
        cell_frame = frame[frame["cell_id"] == cell_id].copy()
        candidates, selected = _fit_and_score_cell(cell_frame, cell_id)
        all_candidates.extend(candidates)
        selected_models[cell_id] = None if selected is None else {
            "model_family": selected["family"],
            "quantity": "path-relative power",
            "unit": "dB relative to the direct-path reference",
            "model": selected["parameters"],
            "transformation": selected.get("transformation", "identity in dB"),
            "selection": {
                "validation_nlpd": selected["validation_nlpd"],
                "validation_ecdf_distance": selected["validation_ecdf_distance"],
                "bic": selected["bic"],
                "validation_fold_count": selected["validation_fold_count"],
                "validation_scenes": selected["validation_scenes"],
                "selection_rule": selected["selection_rule"],
            },
        }
        summary_rows.append(
            {
                "cell_id": cell_id,
                "row_count": int(len(cell_frame)),
                "track_count": int(cell_frame["track_id"].nunique()),
                "scene_count": int(cell_frame["scene_id"].nunique()),
                "selected_family": "empirical_only" if selected is None else selected["family"],
                "selected_validation_nlpd": "" if selected is None else selected["validation_nlpd"],
                "selected_validation_ecdf_distance": "" if selected is None else selected["validation_ecdf_distance"],
                "selected_bic": "" if selected is None else selected["bic"],
            }
        )
    pd.DataFrame([_candidate_row(item) for item in all_candidates]).to_csv(model_dir / "relative_power_candidates.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(model_dir / "relative_power_cell_summary.csv", index=False)
    (model_dir / "selected_relative_power_models.json").write_text(
        json.dumps(
            {
                "schema_version": "path_relative_power_distribution_v1",
                "source_population": str(SOURCE_CSV),
                "source_rows": int(len(frame)),
                "quantity_definition": "relative_power_db is path power relative to the direct-path reference; it is not a received fading-envelope sample",
                "cells": selected_models,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
