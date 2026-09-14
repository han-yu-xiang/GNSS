from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import special, stats


PROJECT_ROOT = Path(r"E:\GNSS_Multipath_Project")
SOURCE_PATH = (
    PROJECT_ROOT
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/"
    "population/gmm_feature_population.csv"
)
ENVIRONMENTS = ("Urban", "Mountain/Valley")
EXPECTED_COUNTS = {
    "rows": 518,
    "Urban": 346,
    "Mountain/Valley": 172,
    "tracks": 236,
    "scenes": 9,
}
REQUIRED_COLUMNS = {
    "primary_population_included",
    "environment_class",
    "scene_id",
    "track_id",
    "doppler_offset_hz",
    "relative_power_db",
    "excess_delay_samples",
}
MODEL_COLUMNS = ("doppler_offset_hz", "relative_power_db")
STD_FLOOR = 0.25
MAX_ITERATIONS = 500
TOLERANCE = 1e-8


def _boolean_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"population is missing required columns: {missing}")


def recompute_track_weights(frame: pd.DataFrame, track_column: str = "track_id") -> pd.DataFrame:
    """Assign each track unit total mass, with equal mass per row within a track."""
    if track_column not in frame.columns:
        raise ValueError(f"missing track column: {track_column}")
    if frame.empty:
        raise ValueError("cannot weight an empty frame")
    output = frame.copy()
    sizes = output.groupby(track_column, sort=False)[track_column].transform("size")
    if (sizes <= 0).any() or not np.isfinite(sizes.to_numpy(float)).all():
        raise ValueError("invalid track sizes")
    output["analysis_weight"] = 1.0 / sizes.astype(float)
    if not np.isfinite(output["analysis_weight"].to_numpy(float)).all():
        raise ValueError("non-finite analysis weights")
    if (output.groupby(track_column)["analysis_weight"].sum() - 1.0).abs().max() > 1e-10:
        raise ValueError("track weights do not sum to one")
    return output


def load_primary_population(path: Path = SOURCE_PATH) -> pd.DataFrame:
    raw = pd.read_csv(path)
    _require_columns(raw, REQUIRED_COLUMNS)
    primary = raw.loc[_boolean_mask(raw["primary_population_included"])].copy()
    if len(primary) != EXPECTED_COUNTS["rows"]:
        raise ValueError(f"primary population has {len(primary)} rows; expected 518")
    for environment in ENVIRONMENTS:
        count = int((primary["environment_class"].astype(str) == environment).sum())
        if count != EXPECTED_COUNTS[environment]:
            raise ValueError(f"{environment} has {count} rows; expected {EXPECTED_COUNTS[environment]}")
    if primary["track_id"].nunique() != EXPECTED_COUNTS["tracks"]:
        raise ValueError("primary population has an unexpected track count")
    if primary["scene_id"].nunique() != EXPECTED_COUNTS["scenes"]:
        raise ValueError("primary population has an unexpected scene count")
    numeric = list(MODEL_COLUMNS) + ["excess_delay_samples"]
    primary[numeric] = primary[numeric].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(primary[numeric].to_numpy(float)).all():
        raise ValueError("primary population has non-finite model fields")
    return recompute_track_weights(primary)


def _validate_vectors(values: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    if x.ndim != 1 or w.ndim != 1 or len(x) != len(w) or len(x) == 0:
        raise ValueError("values and weights must be non-empty equal-length vectors")
    if not np.isfinite(x).all() or not np.isfinite(w).all() or np.any(w <= 0.0):
        raise ValueError("values and weights must be finite and weights positive")
    return x, w


def weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    x, w = _validate_vectors(values, weights)
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must lie in [0, 1]")
    order = np.argsort(x, kind="mergesort")
    cumulative = np.cumsum(w[order]) / np.sum(w)
    return float(x[order][np.searchsorted(cumulative, quantile, side="left")])


def _weighted_mean_std(values: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    mean = float(np.average(values, weights=weights))
    variance = float(np.average((values - mean) ** 2, weights=weights))
    return mean, max(float(np.sqrt(max(variance, 0.0))), STD_FLOOR)


def _initial_means(values: np.ndarray, weights: np.ndarray, components: int, rng: np.random.Generator) -> list[np.ndarray]:
    quantile_positions = (np.arange(components, dtype=float) + 0.5) / components
    base = np.array([weighted_quantile(values, weights, q) for q in quantile_positions], dtype=float)
    mean, std = _weighted_mean_std(values, weights)
    starts = [base]
    if components > 1:
        starts.append(np.linspace(mean - std, mean + std, components, dtype=float))
        starts.append(np.array([weighted_quantile(values, weights, q) for q in np.linspace(0.1, 0.9, components)]))
        probability = weights / np.sum(weights)
        for _ in range(8):
            starts.append(np.sort(rng.choice(values, size=components, replace=False, p=probability)))
    return starts


def _gmm_log_components(values: np.ndarray, means: np.ndarray, stds: np.ndarray, proportions: np.ndarray) -> np.ndarray:
    return np.column_stack(
        [
            np.log(proportions[k]) + stats.norm.logpdf(values, loc=means[k], scale=stds[k])
            for k in range(len(means))
        ]
    )


def fit_weighted_gmm(values: np.ndarray, weights: np.ndarray, components: int, seed: int = 0) -> dict[str, Any]:
    x, w = _validate_vectors(values, weights)
    if components not in (1, 2, 3):
        raise ValueError("components must be 1, 2, or 3")
    if np.sum(w) < 5.0 * components:
        raise ValueError("insufficient effective weight for requested component count")
    total_weight = float(np.sum(w))
    rng = np.random.default_rng(seed)
    global_mean, global_std = _weighted_mean_std(x, w)
    if components == 1:
        means = np.array([global_mean], dtype=float)
        stds = np.array([global_std], dtype=float)
        proportions = np.array([1.0], dtype=float)
        iterations = 1
        best_log_likelihood = float(np.sum(w * _gmm_log_components(x, means, stds, proportions)[:, 0]))
    else:
        best: tuple[float, np.ndarray, np.ndarray, np.ndarray, int] | None = None
        for initial_means in _initial_means(x, w, components, rng):
            means = np.asarray(initial_means, dtype=float)
            if len(np.unique(means)) != components:
                means = np.linspace(global_mean - global_std, global_mean + global_std, components)
            stds = np.full(components, global_std, dtype=float)
            proportions = np.full(components, 1.0 / components, dtype=float)
            for iteration in range(MAX_ITERATIONS):
                log_component = _gmm_log_components(x, means, stds, proportions)
                log_normalizer = special.logsumexp(log_component, axis=1)
                responsibilities = np.exp(log_component - log_normalizer[:, None])
                masses = np.sum(w[:, None] * responsibilities, axis=0)
                if np.any(masses <= 1e-12):
                    break
                new_proportions = masses / total_weight
                new_means = np.sum(w[:, None] * responsibilities * x[:, None], axis=0) / masses
                new_variance = np.sum(
                    w[:, None] * responsibilities * (x[:, None] - new_means[None, :]) ** 2,
                    axis=0,
                ) / masses
                new_stds = np.maximum(np.sqrt(np.maximum(new_variance, 0.0)), STD_FLOOR)
                delta = max(
                    float(np.max(np.abs(new_means - means))),
                    float(np.max(np.abs(new_stds - stds))),
                    float(np.max(np.abs(new_proportions - proportions))),
                )
                means, stds, proportions = new_means, new_stds, new_proportions
                if delta < TOLERANCE:
                    break
            order = np.argsort(means)
            means, stds, proportions = means[order], stds[order], proportions[order]
            log_likelihood = float(np.sum(w * special.logsumexp(_gmm_log_components(x, means, stds, proportions), axis=1)))
            effective_masses = proportions * total_weight
            if np.all(effective_masses >= 5.0):
                candidate = (log_likelihood, means.copy(), stds.copy(), proportions.copy(), iteration + 1)
                if best is None or candidate[0] > best[0]:
                    best = candidate
        if best is None:
            raise ValueError("no GMM initialization produced five units of effective weight per component")
        best_log_likelihood, means, stds, proportions, iterations = best
    effective_masses = proportions * total_weight
    return {
        "status": "fit_ok",
        "components": int(components),
        "means": [float(v) for v in means],
        "stds": [float(v) for v in stds],
        "proportions": [float(v) for v in proportions],
        "effective_component_mass": [float(v) for v in effective_masses],
        "iterations": int(iterations),
        "weighted_log_likelihood": float(best_log_likelihood),
        "std_floor": float(STD_FLOOR),
    }


def gmm_logpdf(values: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    means = np.asarray(model["means"], dtype=float)
    stds = np.asarray(model["stds"], dtype=float)
    proportions = np.asarray(model["proportions"], dtype=float)
    return special.logsumexp(_gmm_log_components(x, means, stds, proportions), axis=1)


def gmm_pdf(values: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    return np.exp(gmm_logpdf(values, model))


def gmm_cdf(values: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    means = np.asarray(model["means"], dtype=float)
    stds = np.asarray(model["stds"], dtype=float)
    proportions = np.asarray(model["proportions"], dtype=float)
    return sum(proportions[k] * stats.norm.cdf(x, loc=means[k], scale=stds[k]) for k in range(len(means)))


def weighted_cdf_distance(values: np.ndarray, weights: np.ndarray, model: dict[str, Any]) -> float:
    x, w = _validate_vectors(values, weights)
    order = np.argsort(x, kind="mergesort")
    empirical = np.cumsum(w[order]) / np.sum(w)
    fitted = gmm_cdf(x[order], model)
    return float(np.max(np.abs(empirical - fitted)))


def effective_sample_size(weights: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    return float(np.sum(w) ** 2 / np.sum(w**2))


def _score_model(values: np.ndarray, weights: np.ndarray, model: dict[str, Any]) -> dict[str, float]:
    logpdf = gmm_logpdf(values, model)
    weighted_log_likelihood = float(np.sum(weights * logpdf))
    parameter_count = 3 * int(model["components"]) - 1
    n_eff = effective_sample_size(weights)
    return {
        "weighted_log_likelihood": weighted_log_likelihood,
        "weighted_nlpd": float(-weighted_log_likelihood / np.sum(weights)),
        "aic": float(-2.0 * weighted_log_likelihood + 2.0 * parameter_count),
        "bic": float(-2.0 * weighted_log_likelihood + parameter_count * np.log(max(n_eff, 1.0))),
        "maximum_weighted_cdf_deviation": weighted_cdf_distance(values, weights, model),
        "effective_sample_size": n_eff,
        "parameter_count": float(parameter_count),
    }


def _validate_model_frame(frame: pd.DataFrame, value_column: str) -> None:
    _require_columns(frame, {value_column, "scene_id", "track_id", "environment_class"})
    values = pd.to_numeric(frame[value_column], errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(float)).all():
        raise ValueError(f"{value_column} contains non-finite values")


def evaluate_gmm_complexity(
    frame: pd.DataFrame,
    value_column: str,
    components_list: tuple[int, ...] = (1, 2, 3),
    seeds: tuple[int, ...] = (2026091301, 2026091302, 2026091303),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit K=1/2/3 and evaluate complete-scene leave-one-out NLPD."""
    _validate_model_frame(frame, value_column)
    if len(components_list) != len(seeds):
        raise ValueError("components_list and seeds must have equal length")
    source = recompute_track_weights(frame)
    scenes = sorted(source["scene_id"].astype(str).unique())
    summary_rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    for components, seed in zip(components_list, seeds):
        values = source[value_column].to_numpy(float)
        weights = source["analysis_weight"].to_numpy(float)
        model = fit_weighted_gmm(values, weights, int(components), int(seed))
        metrics = _score_model(values, weights, model)
        model_json = json.dumps(model, sort_keys=True)
        fold_scores: list[float] = []
        fold_weights: list[float] = []
        for fold_index, held_out_scene in enumerate(scenes):
            train = source.loc[source["scene_id"].astype(str) != held_out_scene].copy()
            test = source.loc[source["scene_id"].astype(str) == held_out_scene].copy()
            train = recompute_track_weights(train)
            test = recompute_track_weights(test)
            train_model = fit_weighted_gmm(
                train[value_column].to_numpy(float),
                train["analysis_weight"].to_numpy(float),
                int(components),
                int(seed) + 10000 + fold_index,
            )
            test_values = test[value_column].to_numpy(float)
            test_weights = test["analysis_weight"].to_numpy(float)
            test_nlpd = float(-np.sum(test_weights * gmm_logpdf(test_values, train_model)) / np.sum(test_weights))
            fold_scores.append(test_nlpd)
            fold_weights.append(float(np.sum(test_weights)))
            fold_rows.append(
                {
                    "value": value_column,
                    "components": int(components),
                    "held_out_scene": held_out_scene,
                    "training_scenes": ";".join(scene for scene in scenes if scene != held_out_scene),
                    "train_row_count": int(len(train)),
                    "test_row_count": int(len(test)),
                    "train_track_count": int(train["track_id"].nunique()),
                    "test_track_count": int(test["track_id"].nunique()),
                    "test_weight": float(np.sum(test_weights)),
                    "weighted_nlpd": test_nlpd,
                    "status": "VALID",
                }
            )
        fold_array = np.asarray(fold_scores, dtype=float)
        summary_rows.append(
            {
                "value": value_column,
                "components": int(components),
                "full_row_count": int(len(source)),
                "full_track_count": int(source["track_id"].nunique()),
                "full_scene_count": int(len(scenes)),
                "full_weighted_nlpd": metrics["weighted_nlpd"],
                "full_weighted_log_likelihood": metrics["weighted_log_likelihood"],
                "aic": metrics["aic"],
                "bic": metrics["bic"],
                "maximum_weighted_cdf_deviation": metrics["maximum_weighted_cdf_deviation"],
                "effective_sample_size": metrics["effective_sample_size"],
                "scene_loso_nlpd_mean": float(np.mean(fold_array)),
                "scene_loso_nlpd_std": float(np.std(fold_array, ddof=1)) if len(fold_array) > 1 else 0.0,
                "scene_loso_nlpd_se": float(np.std(fold_array, ddof=1) / np.sqrt(len(fold_array))) if len(fold_array) > 1 else 0.0,
                "scene_loso_nlpd_weighted_mean": float(np.average(fold_array, weights=np.asarray(fold_weights))),
                "scene_loso_fold_count": int(len(fold_array)),
                "model_json": model_json,
                "selection_status": "NOT_SELECTED",
            }
        )
    summary = pd.DataFrame(summary_rows)
    folds = pd.DataFrame(fold_rows)
    best_index = int(summary["scene_loso_nlpd_mean"].idxmin())
    best_mean = float(summary.loc[best_index, "scene_loso_nlpd_mean"])
    best_se = float(summary.loc[best_index, "scene_loso_nlpd_se"])
    threshold = best_mean + best_se
    eligible = summary.loc[summary["scene_loso_nlpd_mean"] <= threshold + 1e-12]
    selected_components = int(eligible["components"].min())
    summary.loc[summary["components"] == selected_components, "selection_status"] = "SELECTED_ONE_SE_RULE"
    summary.loc[summary["components"] != selected_components, "selection_status"] = "RETAINED_FOR_COMPARISON"
    summary["one_se_threshold"] = threshold
    summary["best_mean_components"] = int(summary.loc[best_index, "components"])
    return summary, folds
