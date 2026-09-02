from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import logsumexp


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
DELAY_FIELD = "excess_delay_samples"
ABS_DOPPLER_FIELD = "absolute_doppler_hz"
SIGNED_DOPPLER_FIELD = "doppler_offset_hz"
WEIGHT_FIELD = "track_weight_recomputed_primary"
MIN_COMPONENT_MASS = 5.0
RANDOM_SEED = 20260831


def _bool_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def load_cell_population(path: Path = SOURCE_CSV) -> pd.DataFrame:
    """Load the read-only population and keep only elevation-ready cell rows."""
    frame = pd.read_csv(path)
    primary = _bool_mask(frame["primary_population_included"])
    ready = _bool_mask(frame["elevation_ready"]) & _bool_mask(frame["cell_ready"])
    frame = frame.loc[primary & ready].copy()
    frame["cell_id"] = frame["environment_class"].astype(str) + "/" + frame["elevation_band"].astype(str)
    numeric_fields = [DELAY_FIELD, ABS_DOPPLER_FIELD, SIGNED_DOPPLER_FIELD, WEIGHT_FIELD]
    frame[numeric_fields] = frame[numeric_fields].apply(pd.to_numeric, errors="coerce")
    if frame[numeric_fields].isna().any().any():
        raise ValueError("non-finite modeling input in the elevation-ready population")
    if (frame[DELAY_FIELD] <= 0).any() or (frame[ABS_DOPPLER_FIELD] < 0).any():
        raise ValueError("delay and absolute Doppler must be in their physical ranges")
    if (frame[WEIGHT_FIELD] <= 0).any():
        raise ValueError("track weights must be positive")
    return frame


def _weighted_mean_scale(values: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    total = float(np.sum(weights))
    center = np.sum(values * weights[:, None], axis=0) / total
    centered = values - center
    variance = np.sum(centered * centered * weights[:, None], axis=0) / total
    scale = np.sqrt(np.maximum(variance, 1e-12))
    return center, scale


def _positive_definite(covariance: np.ndarray) -> bool:
    if not np.isfinite(covariance).all():
        return False
    eigenvalues = np.linalg.eigvalsh((covariance + covariance.T) / 2.0)
    return bool(np.all(eigenvalues > 0.0))


def _log_gaussian_components(
    values: np.ndarray,
    means: np.ndarray,
    covariances: np.ndarray,
) -> np.ndarray:
    """Return one log-density column per Gaussian component."""
    n_components = means.shape[0]
    output = np.empty((values.shape[0], n_components), dtype=float)
    dimension = values.shape[1]
    constant = dimension * np.log(2.0 * np.pi)
    for index in range(n_components):
        covariance = (covariances[index] + covariances[index].T) / 2.0
        sign, logdet = np.linalg.slogdet(covariance)
        if sign <= 0 or not np.isfinite(logdet):
            raise ValueError("covariance is not positive definite")
        difference = values - means[index]
        solved = np.linalg.solve(covariance, difference.T).T
        quadratic = np.sum(difference * solved, axis=1)
        output[:, index] = -0.5 * (constant + logdet + quadratic)
    return output


def _initial_means(values: np.ndarray, weights: np.ndarray, n_components: int, rng: np.random.Generator) -> np.ndarray:
    """Deterministic weighted quantile/farthest-point initialization."""
    total = float(np.sum(weights))
    if n_components == 1:
        return np.sum(values * weights[:, None], axis=0, keepdims=True) / total

    order = np.argsort(values[:, 0], kind="mergesort")
    cumulative = np.cumsum(weights[order]) / total
    targets = (np.arange(n_components, dtype=float) + 0.5) / n_components
    chosen: list[int] = []
    for target in targets:
        index = int(order[min(np.searchsorted(cumulative, target, side="left"), len(order) - 1)])
        if index not in chosen:
            chosen.append(index)
    if len(chosen) < n_components:
        # A deterministic farthest-point completion handles tied quantiles.
        first = int(np.argmax(weights))
        chosen = [first]
        while len(chosen) < n_components:
            distances = np.min(
                np.vstack([np.sum((values - values[item]) ** 2, axis=1) for item in chosen]),
                axis=0,
            )
            distances[chosen] = -np.inf
            best = int(np.argmax(distances))
            if not np.isfinite(distances[best]):
                remaining = [index for index in range(len(values)) if index not in chosen]
                best = remaining[0]
            chosen.append(best)
    return values[np.asarray(chosen[:n_components], dtype=int)].copy()


def fit_weighted_gmm(
    values: np.ndarray,
    weights: np.ndarray,
    n_components: int,
    *,
    seed: int = RANDOM_SEED,
    max_iter: int = 300,
    tolerance: float = 1e-8,
) -> dict[str, Any]:
    """Fit a small weighted full-covariance GMM with deterministic restarts."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("values must have shape (n, 2)")
    if len(values) != len(weights) or not np.isfinite(values).all() or not np.isfinite(weights).all():
        raise ValueError("values and weights must be finite")
    if np.any(weights <= 0) or n_components < 1 or len(values) < n_components:
        raise ValueError("invalid GMM input")

    center, scale = _weighted_mean_scale(values, weights)
    standardized = (values - center) / scale
    global_cov = np.cov(standardized.T, aweights=weights, ddof=0)
    global_cov = np.atleast_2d(global_cov).astype(float)
    if global_cov.shape != (2, 2):
        global_cov = np.eye(2, dtype=float)
    floor = max(1e-5, float(np.trace(global_cov)) * 1e-5 / 2.0)
    global_cov = (global_cov + global_cov.T) / 2.0 + floor * np.eye(2)
    total_weight = float(np.sum(weights))
    rng = np.random.default_rng(seed + n_components * 1009)
    best: dict[str, Any] | None = None

    for restart in range(8):
        if restart == 0:
            means = _initial_means(standardized, weights, n_components, rng)
        else:
            # Small deterministic perturbations explore alternative local optima.
            means = _initial_means(standardized, weights, n_components, rng)
            means += rng.normal(0.0, 0.08, size=means.shape)
        covariances = np.repeat(global_cov[None, :, :], n_components, axis=0)
        proportions = np.full(n_components, 1.0 / n_components, dtype=float)
        previous = -np.inf
        converged = False
        failed = False
        for iteration in range(max_iter):
            component_logpdf = _log_gaussian_components(standardized, means, covariances)
            log_joint = component_logpdf + np.log(np.maximum(proportions, 1e-300))[None, :]
            log_density = logsumexp(log_joint, axis=1)
            responsibilities = np.exp(log_joint - log_density[:, None])
            masses = np.sum(weights[:, None] * responsibilities, axis=0)
            if np.any(masses <= 1e-8) or not np.isfinite(masses).all():
                failed = True
                break
            new_means = (weights[:, None] * responsibilities).T @ standardized / masses[:, None]
            new_covariances = np.empty_like(covariances)
            for component in range(n_components):
                difference = standardized - new_means[component]
                covariance = (difference * (weights * responsibilities[:, component])[:, None]).T @ difference
                covariance /= masses[component]
                covariance = (covariance + covariance.T) / 2.0 + floor * np.eye(2)
                new_covariances[component] = covariance
            means = new_means
            covariances = new_covariances
            proportions = masses / total_weight
            log_likelihood = float(np.sum(weights * log_density))
            if not np.isfinite(log_likelihood) or not all(_positive_definite(covariance) for covariance in covariances):
                failed = True
                break
            if abs(log_likelihood - previous) <= tolerance * (1.0 + abs(log_likelihood)):
                converged = True
                break
            previous = log_likelihood
        if failed:
            continue
        component_logpdf = _log_gaussian_components(standardized, means, covariances)
        log_density = logsumexp(component_logpdf + np.log(proportions)[None, :], axis=1)
        responsibilities = np.exp(component_logpdf + np.log(proportions)[None, :] - log_density[:, None])
        masses = np.sum(weights[:, None] * responsibilities, axis=0)
        log_likelihood = float(np.sum(weights * log_density))
        candidate = {
            "means_standardized": means,
            "covariances_standardized": covariances,
            "proportions": proportions,
            "responsibilities": responsibilities,
            "component_effective_mass": masses,
            "weighted_log_likelihood": log_likelihood,
            "iterations": iteration + 1,
            "converged": converged,
            "center": center,
            "scale": scale,
        }
        if best is None or candidate["weighted_log_likelihood"] > best["weighted_log_likelihood"]:
            best = candidate

    if best is None:
        return {"status": "fit_failed", "n_components": n_components}
    return {"status": "fit_ok", "n_components": n_components, **best}


def _physical_model(fit: dict[str, Any]) -> dict[str, Any]:
    center = np.asarray(fit["center"], dtype=float)
    scale = np.asarray(fit["scale"], dtype=float)
    scale_matrix = np.diag(scale)
    means = np.asarray(fit["means_standardized"], dtype=float) * scale[None, :] + center[None, :]
    covariances = np.asarray(
        [scale_matrix @ covariance @ scale_matrix for covariance in fit["covariances_standardized"]],
        dtype=float,
    )
    return {
        "n_components": int(fit["n_components"]),
        "center": center.tolist(),
        "scale": scale.tolist(),
        "means": means.tolist(),
        "covariances": covariances.tolist(),
        "proportions": np.asarray(fit["proportions"], dtype=float).tolist(),
        "component_effective_mass": np.asarray(fit["component_effective_mass"], dtype=float).tolist(),
        "weighted_log_likelihood": float(fit["weighted_log_likelihood"]),
        "iterations": int(fit["iterations"]),
        "converged": bool(fit["converged"]),
    }


def predict_log_density(model: dict[str, Any], xy: np.ndarray) -> np.ndarray:
    """Evaluate a stored physical-coordinate model at [delay, abs Doppler]."""
    values = np.asarray(xy, dtype=float)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("xy must have shape (n, 2)")
    center = np.asarray(model["center"], dtype=float)
    scale = np.asarray(model["scale"], dtype=float)
    means = np.asarray(model["means"], dtype=float)
    covariances = np.asarray(model["covariances"], dtype=float)
    proportions = np.asarray(model["proportions"], dtype=float)
    standardized_values = (values - center) / scale
    standardized_means = (means - center[None, :]) / scale[None, :]
    scale_matrix = np.diag(1.0 / scale)
    standardized_covariances = np.asarray(
        [scale_matrix @ covariance @ scale_matrix for covariance in covariances],
        dtype=float,
    )
    return logsumexp(
        _log_gaussian_components(standardized_values, standardized_means, standardized_covariances)
        + np.log(np.maximum(proportions, 1e-300))[None, :],
        axis=1,
    ) - np.log(np.prod(scale))


def _parameter_count(n_components: int) -> int:
    # K means, K 2-D full covariances, and K-1 independent mixture weights.
    return n_components * 2 + n_components * 3 + (n_components - 1)


def _fit_one_candidate(cell_frame: pd.DataFrame, n_components: int, seed: int) -> dict[str, Any]:
    values = cell_frame[[DELAY_FIELD, ABS_DOPPLER_FIELD]].to_numpy(float)
    weights = cell_frame[WEIGHT_FIELD].to_numpy(float)
    fit = fit_weighted_gmm(values, weights, n_components, seed=seed)
    result: dict[str, Any] = {"n_components": n_components, "status": "rejected"}
    if fit["status"] != "fit_ok":
        result["rejection_reason"] = "fit_failed"
        return result
    masses = np.asarray(fit["component_effective_mass"], dtype=float)
    if np.any(masses < MIN_COMPONENT_MASS):
        result["rejection_reason"] = "component_effective_mass_below_5"
        result["component_effective_mass"] = masses.tolist()
        return result
    physical = _physical_model(fit)
    n_eff = float(np.sum(weights) ** 2 / np.sum(weights**2))
    bic = -2.0 * float(fit["weighted_log_likelihood"]) + _parameter_count(n_components) * np.log(max(n_eff, 2.0))
    result.update(
        {
            "status": "fit_ok",
            "physical_model": physical,
            "component_effective_mass": masses.tolist(),
            "bic": float(bic),
            "n_eff": n_eff,
            "row_count": int(len(cell_frame)),
            "track_count": int(cell_frame["track_id"].nunique()),
        }
    )
    return result


def _validation_score(cell_frame: pd.DataFrame, n_components: int, seed: int) -> tuple[float, int, list[str], list[str]]:
    scores: list[float] = []
    used: list[str] = []
    skipped: list[str] = []
    for scene_id in sorted(cell_frame["scene_id"].astype(str).unique()):
        test = cell_frame[cell_frame["scene_id"].astype(str) == scene_id]
        train = cell_frame[cell_frame["scene_id"].astype(str) != scene_id]
        train_weight = float(train[WEIGHT_FIELD].sum())
        if train_weight < max(MIN_COMPONENT_MASS, n_components * MIN_COMPONENT_MASS):
            skipped.append(f"{scene_id}:insufficient_training_mass")
            continue
        fit = _fit_one_candidate(train, n_components, seed + len(used) + 1)
        if fit["status"] != "fit_ok":
            skipped.append(f"{scene_id}:{fit.get('rejection_reason', 'fit_failed')}")
            continue
        model = fit["physical_model"]
        test_values = test[[DELAY_FIELD, ABS_DOPPLER_FIELD]].to_numpy(float)
        test_weights = test[WEIGHT_FIELD].to_numpy(float)
        log_density = predict_log_density(model, test_values)
        if not np.isfinite(log_density).all() or float(test_weights.sum()) <= 0:
            skipped.append(f"{scene_id}:nonfinite_validation")
            continue
        score = -float(np.sum(test_weights * log_density) / np.sum(test_weights))
        scores.append(score)
        used.append(scene_id)
    if not scores:
        return float("nan"), 0, used, skipped
    return float(np.mean(scores)), len(scores), used, skipped


def fit_cell_models(frame: pd.DataFrame, cell_id: str) -> list[dict[str, Any]]:
    """Fit and validate K=1,2,3 weighted full-covariance models for one cell."""
    cell_frame = frame[frame["cell_id"].astype(str) == cell_id].copy()
    if cell_frame.empty:
        raise ValueError(f"unknown or empty cell: {cell_id}")
    candidates: list[dict[str, Any]] = []
    for n_components in (1, 2, 3):
        candidate = _fit_one_candidate(cell_frame, n_components, RANDOM_SEED)
        if candidate["status"] != "fit_ok":
            candidate.update(
                {
                    "cell_id": cell_id,
                    "mean_weighted_nlpd": float("nan"),
                    "validation_fold_count": 0,
                    "validation_scenes": [],
                    "skipped_validation_scenes": [],
                }
            )
            candidates.append(candidate)
            continue
        nlpd, fold_count, used, skipped = _validation_score(cell_frame, n_components, RANDOM_SEED)
        if not np.isfinite(nlpd):
            candidate["status"] = "rejected"
            candidate["rejection_reason"] = "no_valid_scene_grouped_validation_fold"
        candidate.update(
            {
                "cell_id": cell_id,
                "mean_weighted_nlpd": nlpd,
                "validation_fold_count": fold_count,
                "validation_scenes": used,
                "skipped_validation_scenes": skipped,
            }
        )
        candidates.append(candidate)
    return candidates


def select_cell_model(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [candidate for candidate in candidates if candidate.get("status") == "fit_ok"]
    if not valid:
        return None
    valid.sort(key=lambda candidate: (float(candidate["mean_weighted_nlpd"]), float(candidate["bic"])))
    selected = dict(valid[0])
    selected["selection_rule"] = "lowest scene-grouped held-out weighted negative log density; BIC tie-break"
    return selected


def _candidate_row(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "cell_id": candidate["cell_id"],
        "n_components": candidate["n_components"],
        "status": candidate["status"],
        "rejection_reason": candidate.get("rejection_reason", ""),
        "row_count": candidate.get("row_count", ""),
        "track_count": candidate.get("track_count", ""),
        "n_eff": candidate.get("n_eff", ""),
        "component_effective_mass": json.dumps(candidate.get("component_effective_mass", [])),
        "mean_weighted_nlpd": candidate.get("mean_weighted_nlpd", ""),
        "validation_fold_count": candidate.get("validation_fold_count", 0),
        "validation_scenes": ";".join(candidate.get("validation_scenes", [])),
        "skipped_validation_scenes": ";".join(candidate.get("skipped_validation_scenes", [])),
        "bic": candidate.get("bic", ""),
    }


def _fit_signed_sensitivity(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell_id in CELL_ORDER:
        cell_frame = frame[frame["cell_id"] == cell_id].copy()
        if cell_frame.empty:
            continue
        values = cell_frame[[DELAY_FIELD, SIGNED_DOPPLER_FIELD]].to_numpy(float)
        weights = cell_frame[WEIGHT_FIELD].to_numpy(float)
        for n_components in (1, 2, 3):
            if float(weights.sum()) < n_components * MIN_COMPONENT_MASS:
                rows.append({"cell_id": cell_id, "n_components": n_components, "status": "not_fit", "reason": "insufficient_effective_mass"})
                continue
            fit = fit_weighted_gmm(values, weights, n_components, seed=RANDOM_SEED + 7000)
            if fit["status"] != "fit_ok":
                rows.append({"cell_id": cell_id, "n_components": n_components, "status": "fit_failed", "reason": "fit_failed"})
                continue
            masses = np.asarray(fit["component_effective_mass"], dtype=float)
            rows.append(
                {
                    "cell_id": cell_id,
                    "n_components": n_components,
                    "status": "fit_ok" if np.all(masses >= MIN_COMPONENT_MASS) else "below_mass_threshold",
                    "reason": "" if np.all(masses >= MIN_COMPONENT_MASS) else "component_effective_mass_below_5",
                    "weighted_log_likelihood": float(fit["weighted_log_likelihood"]),
                    "component_effective_mass": json.dumps(masses.tolist()),
                    "weighted_signed_doppler_mean_hz": float(np.sum(weights * values[:, 1]) / np.sum(weights)),
                    "positive_weight_fraction": float(np.sum(weights[values[:, 1] > 0]) / np.sum(weights)),
                    "negative_weight_fraction": float(np.sum(weights[values[:, 1] < 0]) / np.sum(weights)),
                }
            )
    return rows


def main() -> None:
    frame = load_cell_population()
    model_dir = OUTPUT_ROOT / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    all_candidates: list[dict[str, Any]] = []
    selected_models: dict[str, Any] = {}
    summaries: list[dict[str, Any]] = []
    for cell_id in CELL_ORDER:
        candidates = fit_cell_models(frame, cell_id)
        all_candidates.extend(candidates)
        selected = select_cell_model(candidates)
        selected_models[cell_id] = None if selected is None else {
            "model_family": "weighted full-covariance Gaussian mixture",
            "coordinates": {
                "x": {"field": DELAY_FIELD, "unit": "samples relative to the direct-path reference"},
                "y": {"field": ABS_DOPPLER_FIELD, "unit": "Hz, absolute relative Doppler"},
            },
            "weight_field": WEIGHT_FIELD,
            "model": selected["physical_model"],
            "selection": {
                "n_components": selected["n_components"],
                "mean_weighted_nlpd": selected["mean_weighted_nlpd"],
                "bic": selected["bic"],
                "validation_fold_count": selected["validation_fold_count"],
                "validation_scenes": selected["validation_scenes"],
                "selection_rule": selected["selection_rule"],
            },
        }
        summaries.append(
            {
                "cell_id": cell_id,
                "row_count": int(len(frame[frame["cell_id"] == cell_id])),
                "track_count": int(frame.loc[frame["cell_id"] == cell_id, "track_id"].nunique()),
                "scene_count": int(frame.loc[frame["cell_id"] == cell_id, "scene_id"].nunique()),
                "selected_n_components": "" if selected is None else selected["n_components"],
                "selected_mean_weighted_nlpd": "" if selected is None else selected["mean_weighted_nlpd"],
                "selected_bic": "" if selected is None else selected["bic"],
                "selected_status": "empirical_only" if selected is None else "fit_ok",
            }
        )

    pd.DataFrame([_candidate_row(candidate) for candidate in all_candidates]).to_csv(
        model_dir / "delay_doppler_2d_candidates.csv", index=False
    )
    pd.DataFrame(summaries).to_csv(model_dir / "delay_doppler_cell_summary.csv", index=False)
    (model_dir / "selected_delay_doppler_2d_models.json").write_text(
        json.dumps(
            {
                "schema_version": "path_level_delay_doppler_2d_v1",
                "source_population": str(SOURCE_CSV),
                "source_rows": int(len(frame)),
                "primary_model_coordinates": "[excess_delay_samples, absolute_doppler_hz]",
                "signed_doppler_is_sensitivity_only": True,
                "cells": selected_models,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(_fit_signed_sensitivity(frame)).to_csv(
        model_dir / "signed_doppler_sensitivity.csv", index=False
    )


if __name__ == "__main__":
    main()
