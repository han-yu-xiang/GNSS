from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from scipy.special import logsumexp
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
DELAY_FIELD = "excess_delay_samples"
DOPPLER_FIELD = "absolute_doppler_hz"
WEIGHT_FIELD = "track_weight_recomputed_primary"
MIN_COMPONENT_MASS = 5.0
RANDOM_SEED = 20260901
ENVIRONMENT_COLORS = {"Urban": "#1f77b4", "Mountain/Valley": "#ff7f0e"}


def _bool_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def load_population(path: Path = SOURCE_CSV) -> pd.DataFrame:
    frame = pd.read_csv(path)
    mask = (
        _bool_mask(frame["primary_population_included"])
        & _bool_mask(frame["elevation_ready"])
        & _bool_mask(frame["cell_ready"])
    )
    frame = frame.loc[mask].copy()
    frame["cell_id"] = frame["environment_class"].astype(str) + "/" + frame["elevation_band"].astype(str)
    numeric_fields = [DELAY_FIELD, DOPPLER_FIELD, WEIGHT_FIELD]
    frame[numeric_fields] = frame[numeric_fields].apply(pd.to_numeric, errors="coerce")
    if frame[numeric_fields].isna().any().any():
        raise ValueError("non-finite one-dimensional modeling input")
    if (frame[DELAY_FIELD] <= 0).any() or (frame[DOPPLER_FIELD] < 0).any() or (frame[WEIGHT_FIELD] <= 0).any():
        raise ValueError("modeling values or weights are outside the admissible range")
    return frame


def _weighted_mean_variance(values: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    total = float(np.sum(weights))
    mean = float(np.sum(weights * values) / total)
    variance = float(np.sum(weights * (values - mean) ** 2) / total)
    return mean, max(variance, 1e-10)


def fit_weighted_lognormal(values: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.ndim != 1 or len(values) != len(weights) or not np.isfinite(values).all() or not np.isfinite(weights).all():
        raise ValueError("values and weights must be finite one-dimensional arrays")
    if np.any(values <= 0) or np.any(weights <= 0):
        raise ValueError("lognormal values and weights must be positive")
    transformed = np.log(values)
    mean_log, variance_log = _weighted_mean_variance(transformed, weights)
    std_log = float(np.sqrt(variance_log))
    log_density = norm.logpdf(transformed, loc=mean_log, scale=std_log) - np.log(values)
    return {
        "family": "lognormal",
        "mean_log": mean_log,
        "std_log": std_log,
        "weighted_log_likelihood": float(np.sum(weights * log_density)),
        "parameter_count": 2,
        "status": "fit_ok",
    }


def fit_weighted_log1p_gaussian_mixture(
    values: np.ndarray,
    weights: np.ndarray,
    n_components: int,
    *,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.ndim != 1 or len(values) != len(weights) or not np.isfinite(values).all() or not np.isfinite(weights).all():
        raise ValueError("values and weights must be finite one-dimensional arrays")
    if np.any(values < 0) or np.any(weights <= 0) or n_components not in (1, 2):
        raise ValueError("invalid log1p-Gaussian-mixture input")

    transformed = np.log1p(values)
    total_weight = float(np.sum(weights))
    global_mean, global_variance = _weighted_mean_variance(transformed, weights)
    variance_floor = max(1e-6, global_variance * 1e-5)
    order = np.argsort(transformed, kind="mergesort")
    cumulative = np.cumsum(weights[order]) / total_weight
    rng = np.random.default_rng(seed + 101 * n_components)
    best: dict[str, Any] | None = None

    for restart in range(8):
        targets = (np.arange(n_components, dtype=float) + 0.5) / n_components
        indices = [int(order[min(np.searchsorted(cumulative, target), len(order) - 1)]) for target in targets]
        means = transformed[np.asarray(indices)].copy()
        if restart:
            means += rng.normal(0.0, 0.04 * np.sqrt(global_variance), size=n_components)
        variances = np.full(n_components, max(global_variance, variance_floor), dtype=float)
        proportions = np.full(n_components, 1.0 / n_components, dtype=float)
        previous = -np.inf
        failed = False

        for iteration in range(300):
            component_logpdf = np.column_stack(
                [norm.logpdf(transformed, loc=means[index], scale=np.sqrt(variances[index])) for index in range(n_components)]
            )
            log_joint = component_logpdf + np.log(np.maximum(proportions, 1e-300))[None, :]
            log_density_transformed = logsumexp(log_joint, axis=1)
            responsibilities = np.exp(log_joint - log_density_transformed[:, None])
            masses = np.sum(weights[:, None] * responsibilities, axis=0)
            if np.any(masses <= 1e-10) or not np.isfinite(masses).all():
                failed = True
                break
            means = np.sum(weights[:, None] * responsibilities * transformed[:, None], axis=0) / masses
            variances = np.sum(
                weights[:, None] * responsibilities * (transformed[:, None] - means[None, :]) ** 2,
                axis=0,
            ) / masses
            variances = np.maximum(variances, variance_floor)
            proportions = masses / total_weight
            log_likelihood = float(np.sum(weights * (log_density_transformed - np.log1p(values))))
            if not np.isfinite(log_likelihood):
                failed = True
                break
            if abs(log_likelihood - previous) <= 1e-8 * (1.0 + abs(log_likelihood)):
                break
            previous = log_likelihood
        if failed:
            continue
        component_logpdf = np.column_stack(
            [norm.logpdf(transformed, loc=means[index], scale=np.sqrt(variances[index])) for index in range(n_components)]
        )
        log_joint = component_logpdf + np.log(np.maximum(proportions, 1e-300))[None, :]
        log_density_transformed = logsumexp(log_joint, axis=1)
        responsibilities = np.exp(log_joint - log_density_transformed[:, None])
        masses = np.sum(weights[:, None] * responsibilities, axis=0)
        candidate = {
            "family": "log1p_gaussian_mixture",
            "n_components": n_components,
            "means_log1p": means.tolist(),
            "stds_log1p": np.sqrt(variances).tolist(),
            "proportions": proportions.tolist(),
            "component_effective_mass": masses.tolist(),
            "weighted_log_likelihood": float(np.sum(weights * (log_density_transformed - np.log1p(values)))),
            "parameter_count": 3 * n_components - 1,
            "status": "fit_ok",
            "iterations": iteration + 1,
        }
        if best is None or candidate["weighted_log_likelihood"] > best["weighted_log_likelihood"]:
            best = candidate
    if best is None:
        return {"family": "log1p_gaussian_mixture", "n_components": n_components, "status": "fit_failed"}
    return best


def evaluate_model_cdf(model: dict[str, Any], x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    output = np.zeros_like(x, dtype=float)
    if model["family"] == "lognormal":
        valid = x > 0
        output[valid] = norm.cdf((np.log(x[valid]) - float(model["mean_log"])) / float(model["std_log"]))
        return np.clip(output, 0.0, 1.0)
    if model["family"] == "log1p_gaussian_mixture":
        valid = x >= 0
        transformed = np.log1p(np.maximum(x[valid], 0.0))
        for mean, std, proportion in zip(model["means_log1p"], model["stds_log1p"], model["proportions"]):
            output[valid] += float(proportion) * norm.cdf((transformed - float(mean)) / float(std))
        return np.clip(output, 0.0, 1.0)
    raise ValueError(f"unknown model family: {model['family']}")


def evaluate_model_logpdf(model: dict[str, Any], x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if model["family"] == "lognormal":
        output = np.full_like(x, -np.inf, dtype=float)
        valid = x > 0
        transformed = np.log(x[valid])
        output[valid] = norm.logpdf(transformed, loc=model["mean_log"], scale=model["std_log"]) - np.log(x[valid])
        return output
    if model["family"] == "log1p_gaussian_mixture":
        output = np.full_like(x, -np.inf, dtype=float)
        valid = x >= 0
        transformed = np.log1p(x[valid])
        component_logpdf = np.column_stack(
            [
                norm.logpdf(transformed, loc=mean, scale=std) + np.log(max(proportion, 1e-300))
                for mean, std, proportion in zip(model["means_log1p"], model["stds_log1p"], model["proportions"])
            ]
        )
        output[valid] = logsumexp(component_logpdf, axis=1) - np.log1p(x[valid])
        return output
    raise ValueError(f"unknown model family: {model['family']}")


def select_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [candidate for candidate in candidates if candidate.get("status") == "fit_ok" and np.isfinite(candidate.get("validation_nlpd", np.nan))]
    if not valid:
        return None
    return sorted(valid, key=lambda candidate: (float(candidate["validation_nlpd"]), float(candidate["bic"])))[0]


def _weighted_ecdf(values: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    cumulative = np.cumsum(weights[order]) / np.sum(weights)
    return sorted_values, cumulative


def _bic(model: dict[str, Any], weights: np.ndarray) -> float:
    n_eff = float(np.sum(weights) ** 2 / np.sum(weights**2))
    return float(-2.0 * model["weighted_log_likelihood"] + model["parameter_count"] * np.log(max(n_eff, 2.0)))


def _scene_grouped_validation(
    frame: pd.DataFrame,
    field: str,
    fit_function,
) -> tuple[float, list[str], list[str]]:
    scores: list[float] = []
    used: list[str] = []
    skipped: list[str] = []
    for scene_id in sorted(frame["scene_id"].astype(str).unique()):
        train = frame[frame["scene_id"].astype(str) != scene_id]
        test = frame[frame["scene_id"].astype(str) == scene_id]
        if float(train[WEIGHT_FIELD].sum()) < MIN_COMPONENT_MASS:
            skipped.append(f"{scene_id}:insufficient_training_mass")
            continue
        model = fit_function(train[field].to_numpy(float), train[WEIGHT_FIELD].to_numpy(float))
        if model.get("status") != "fit_ok":
            skipped.append(f"{scene_id}:fit_failed")
            continue
        masses = np.asarray(model.get("component_effective_mass", [MIN_COMPONENT_MASS]), dtype=float)
        if np.any(masses < MIN_COMPONENT_MASS):
            skipped.append(f"{scene_id}:component_effective_mass_below_5")
            continue
        values = test[field].to_numpy(float)
        weights = test[WEIGHT_FIELD].to_numpy(float)
        log_density = evaluate_model_logpdf(model, values)
        if not np.isfinite(log_density).all():
            skipped.append(f"{scene_id}:nonfinite_validation")
            continue
        scores.append(float(-np.sum(weights * log_density) / np.sum(weights)))
        used.append(scene_id)
    return (float(np.mean(scores)) if scores else float("nan"), used, skipped)


def fit_cell_models(frame: pd.DataFrame, cell_id: str) -> dict[str, Any]:
    cell = frame[frame["cell_id"] == cell_id].copy()
    if cell.empty:
        raise ValueError(f"empty cell: {cell_id}")
    delay_values = cell[DELAY_FIELD].to_numpy(float)
    weights = cell[WEIGHT_FIELD].to_numpy(float)
    delay_model = fit_weighted_lognormal(delay_values, weights)
    delay_score, delay_used, delay_skipped = _scene_grouped_validation(cell, DELAY_FIELD, fit_weighted_lognormal)
    delay_model.update(
        {
            "validation_nlpd": delay_score,
            "validation_scenes": delay_used,
            "skipped_validation_scenes": delay_skipped,
            "bic": _bic(delay_model, weights),
        }
    )

    doppler_candidates: list[dict[str, Any]] = []
    for n_components in (1, 2):
        model = fit_weighted_log1p_gaussian_mixture(cell[DOPPLER_FIELD].to_numpy(float), weights, n_components)
        if model.get("status") == "fit_ok" and np.any(np.asarray(model["component_effective_mass"]) < MIN_COMPONENT_MASS):
            model["status"] = "rejected"
            model["rejection_reason"] = "component_effective_mass_below_5"
        if model.get("status") == "fit_ok":
            fit_function = lambda values, local_weights, count=n_components: fit_weighted_log1p_gaussian_mixture(  # noqa: E731
                values, local_weights, count
            )
            score, used, skipped = _scene_grouped_validation(cell, DOPPLER_FIELD, fit_function)
            model.update(
                {
                    "validation_nlpd": score,
                    "validation_scenes": used,
                    "skipped_validation_scenes": skipped,
                    "bic": _bic(model, weights),
                }
            )
            if not np.isfinite(score):
                model["status"] = "rejected"
                model["rejection_reason"] = "no_valid_scene_grouped_validation_fold"
        doppler_candidates.append(model)
    selected_doppler = select_candidate(doppler_candidates)
    return {
        "cell_id": cell_id,
        "row_count": int(len(cell)),
        "track_count": int(cell["track_id"].nunique()),
        "scene_count": int(cell["scene_id"].nunique()),
        "delay_model": delay_model,
        "doppler_candidates": doppler_candidates,
        "selected_doppler_model": selected_doppler,
    }


def _json_safe_model(model: dict[str, Any] | None) -> dict[str, Any] | None:
    if model is None:
        return None
    safe: dict[str, Any] = {}
    for key, value in model.items():
        if isinstance(value, np.ndarray):
            safe[key] = value.tolist()
        elif isinstance(value, (np.floating, np.integer)):
            safe[key] = value.item()
        else:
            safe[key] = value
    return safe


def _plot(frame: pd.DataFrame, cells: dict[str, Any], figure_dir: Path) -> None:
    figure, axes = plt.subplots(2, 3, figsize=(11.1, 7.0), sharey=True)
    delay_max = float(frame[DELAY_FIELD].max()) * 1.08
    doppler_max = float(frame[DOPPLER_FIELD].max()) * 1.08
    delay_grid = np.linspace(0.0, delay_max, 700)
    doppler_grid = np.linspace(0.0, doppler_max, 700)

    for column, band in enumerate(ELEVATION_BANDS):
        delay_axis = axes[0, column]
        doppler_axis = axes[1, column]
        for environment in ENVIRONMENTS:
            cell_id = f"{environment}/{band}"
            subset = frame[frame["cell_id"] == cell_id]
            weights = subset[WEIGHT_FIELD].to_numpy(float)
            color = ENVIRONMENT_COLORS[environment]

            delay_x, delay_y = _weighted_ecdf(subset[DELAY_FIELD].to_numpy(float), weights)
            delay_axis.step(delay_x, delay_y, where="post", color=color, linewidth=1.55)
            delay_axis.plot(delay_grid, evaluate_model_cdf(cells[cell_id]["delay_model"], delay_grid), color=color, linestyle="--", linewidth=1.65)

            doppler_x, doppler_y = _weighted_ecdf(subset[DOPPLER_FIELD].to_numpy(float), weights)
            doppler_axis.step(doppler_x, doppler_y, where="post", color=color, linewidth=1.55)
            selected = cells[cell_id]["selected_doppler_model"]
            if selected is not None:
                doppler_axis.plot(doppler_grid, evaluate_model_cdf(selected, doppler_grid), color=color, linestyle="--", linewidth=1.65)

        delay_axis.set_title(f"Excess delay | {band}", fontsize=10)
        doppler_axis.set_title(f"Absolute relative Doppler | {band}", fontsize=10)
        delay_axis.set_xlim(0.0, delay_max)
        doppler_axis.set_xlim(0.0, doppler_max)
        delay_axis.set_xlabel("Excess delay (samples)", fontsize=8.5)
        doppler_axis.set_xlabel("Absolute relative Doppler (Hz)", fontsize=8.5)
        for axis in (delay_axis, doppler_axis):
            axis.set_ylim(0.0, 1.02)
            axis.grid(alpha=0.18, linewidth=0.6)
            axis.tick_params(labelsize=8)
    axes[0, 0].set_ylabel("Cumulative probability", fontsize=8.5)
    axes[1, 0].set_ylabel("Cumulative probability", fontsize=8.5)

    handles = []
    for environment in ENVIRONMENTS:
        color = ENVIRONMENT_COLORS[environment]
        handles.append(Line2D([0], [0], color=color, linewidth=1.6, label=f"{environment} measured ECDF"))
        handles.append(Line2D([0], [0], color=color, linewidth=1.6, linestyle="--", label=f"{environment} fitted CDF"))
    figure.legend(handles=handles, loc="upper center", ncol=4, frameon=False, fontsize=8.1, bbox_to_anchor=(0.5, 0.965))
    figure.suptitle("One-dimensional measured and fitted path-parameter distributions", fontsize=12.5, y=0.998)
    figure.text(0.5, 0.012, "Solid steps show weighted empirical CDFs; dashed curves show fitted one-dimensional CDFs.", ha="center", fontsize=8.4)
    figure.subplots_adjust(left=0.075, right=0.985, bottom=0.085, top=0.89, wspace=0.22, hspace=0.36)
    figure.savefig(figure_dir / "delay_doppler_1d_empirical_vs_fitted_cdf.png", dpi=230, bbox_inches="tight")
    figure.savefig(figure_dir / "delay_doppler_1d_empirical_vs_fitted_cdf.pdf", bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    frame = load_population()
    model_dir = OUTPUT_ROOT / "model"
    table_dir = OUTPUT_ROOT / "tables"
    figure_dir = OUTPUT_ROOT / "figures"
    model_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    cells: dict[str, Any] = {}
    summary_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for cell_id in CELL_ORDER:
        result = fit_cell_models(frame, cell_id)
        cells[cell_id] = {
            **result,
            "delay_model": _json_safe_model(result["delay_model"]),
            "doppler_candidates": [_json_safe_model(item) for item in result["doppler_candidates"]],
            "selected_doppler_model": _json_safe_model(result["selected_doppler_model"]),
        }
        selected = result["selected_doppler_model"]
        environment, band = cell_id.rsplit("/", 1)
        summary_rows.append(
            {
                "environment": environment,
                "elevation_band": band,
                "row_count": result["row_count"],
                "track_count": result["track_count"],
                "scene_count": result["scene_count"],
                "delay_family": "lognormal",
                "delay_mu_log": result["delay_model"]["mean_log"],
                "delay_sigma_log": result["delay_model"]["std_log"],
                "delay_validation_nlpd": result["delay_model"]["validation_nlpd"],
                "doppler_family": "empirical_only" if selected is None else "log1p Gaussian mixture",
                "doppler_component_count": "" if selected is None else selected["n_components"],
                "doppler_component_centers_hz": "" if selected is None else json.dumps(np.expm1(np.asarray(selected["means_log1p"])).tolist()),
                "doppler_validation_nlpd": "" if selected is None else selected["validation_nlpd"],
            }
        )
        for candidate in result["doppler_candidates"]:
            candidate_rows.append(
                {
                    "cell_id": cell_id,
                    "n_components": candidate.get("n_components"),
                    "status": candidate.get("status"),
                    "rejection_reason": candidate.get("rejection_reason", ""),
                    "component_effective_mass": json.dumps(candidate.get("component_effective_mass", [])),
                    "validation_nlpd": candidate.get("validation_nlpd", ""),
                    "bic": candidate.get("bic", ""),
                    "validation_scenes": ";".join(candidate.get("validation_scenes", [])),
                    "skipped_validation_scenes": ";".join(candidate.get("skipped_validation_scenes", [])),
                }
            )

    (model_dir / "delay_doppler_1d_models.json").write_text(
        json.dumps(
            {
                "schema_version": "path_level_delay_doppler_1d_v1",
                "source_population": str(SOURCE_CSV),
                "source_rows": int(len(frame)),
                "delay_model": "weighted lognormal in excess-delay samples",
                "doppler_model": "selected one- or two-component weighted Gaussian mixture in log1p absolute-relative-Doppler coordinates",
                "cells": cells,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(candidate_rows).to_csv(model_dir / "delay_doppler_1d_candidates.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(table_dir / "delay_doppler_1d_model_summary.csv", index=False)
    _plot(frame, cells, figure_dir)


if __name__ == "__main__":
    main()
