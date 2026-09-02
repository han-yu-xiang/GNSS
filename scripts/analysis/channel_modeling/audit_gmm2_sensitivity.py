#!/usr/bin/env python3
"""Read-only Phase-1 GMM-2 sensitivity audit.

The audit reads the frozen r3 Stage3 source population and the r2/r3 closure
tables.  It does not update the canonical model, production artifacts, or
source data.  All generated files are written to a caller-supplied,
new-only ``phase1_gmm2_sensitivity_audit_*`` namespace.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

try:
    from scipy import optimize, special, stats
except ImportError as exc:  # pragma: no cover - depends on the project venv
    raise RuntimeError("scipy is required; use the Phase-1 analysis environment") from exc


PARAMETERS = {
    "doppler": {
        "field": "doppler_offset_hz",
        "label": "相对多普勒",
        "unit": "Hz",
    },
    "power": {
        "field": "relative_power_db",
        "label": "相对功率",
        "unit": "dB",
    },
}
FAMILIES = ("normal", "student_t", "laplace", "gmm2")
GMM2_MIN_COMPONENT_WEIGHT = 0.10
GMM2_MIN_STANDARDIZED_SEPARATION = 1.0
GMM2_MIN_BIC_IMPROVEMENT = 6.0
MIN_GROUP_EFFECTIVE_SAMPLE_SIZE = 10.0
DEFAULT_BOOTSTRAP_REPLICATES = 1000
DEFAULT_BOOTSTRAP_SEED = 2026083101
EPS = 1e-12
WINDOWS_CHINESE_FONT = Path("C:/Windows/Fonts/msyh.ttc")


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_arrays(rows: Sequence[Mapping[str, Any]], field: str) -> tuple[np.ndarray, np.ndarray]:
    values: list[float] = []
    weights: list[float] = []
    for row in rows:
        value = finite(row.get(field))
        weight = finite(row.get("track_weight"))
        if value is None or weight is None or weight <= 0:
            continue
        values.append(value)
        weights.append(weight)
    if not values:
        raise ValueError(f"no finite values for {field}")
    return np.asarray(values, dtype=float), np.asarray(weights, dtype=float)


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(values * weights) / np.sum(weights))


def weighted_quantile(values: np.ndarray, weights: np.ndarray, probability: float) -> float:
    order = np.argsort(values, kind="mergesort")
    ordered_values = values[order]
    ordered_weights = weights[order]
    target = float(probability) * float(np.sum(ordered_weights))
    index = int(np.searchsorted(np.cumsum(ordered_weights), target, side="left"))
    return float(ordered_values[min(index, len(ordered_values) - 1)])


def kish_effective_sample_size(weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    return total * total / float(np.sum(weights * weights))


def fit_normal_weighted(values: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    loc = weighted_mean(values, weights)
    variance = float(np.sum(weights * (values - loc) ** 2) / np.sum(weights))
    scale = max(math.sqrt(max(variance, 0.0)), max(float(np.ptp(values)) * 1e-6, 1e-9))
    return {"family": "normal", "loc": loc, "scale": scale, "n_parameters": 2}


def fit_laplace_weighted(values: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    loc = weighted_quantile(values, weights, 0.5)
    scale = float(np.sum(weights * np.abs(values - loc)) / np.sum(weights))
    scale = max(scale, max(float(np.ptp(values)) * 1e-6, 1e-9))
    return {"family": "laplace", "loc": loc, "scale": scale, "n_parameters": 2}


def fit_student_t_weighted(values: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    loc0 = weighted_mean(values, weights)
    scale0 = max(float(np.sqrt(np.average((values - loc0) ** 2, weights=weights))), 1e-6)
    initial = np.asarray([8.0, loc0, scale0], dtype=float)
    span = max(float(np.ptp(values)), scale0, 1.0)
    bounds = [(2.05, 100.0), (float(np.min(values) - 10 * span), float(np.max(values) + 10 * span)), (1e-9, 100 * span)]

    def objective(vector: np.ndarray) -> float:
        df, loc, scale = vector
        logpdf = stats.t.logpdf(values, df, loc=loc, scale=scale)
        if not np.all(np.isfinite(logpdf)):
            return 1e300
        return float(-np.sum(weights * logpdf))

    result = optimize.minimize(objective, initial, method="L-BFGS-B", bounds=bounds, options={"maxiter": 400, "ftol": 1e-12, "gtol": 1e-8})
    vector = result.x if np.all(np.isfinite(result.x)) and math.isfinite(objective(result.x)) else initial
    return {
        "family": "student_t",
        "df": float(np.clip(vector[0], 2.05, 100.0)),
        "loc": float(vector[1]),
        "scale": max(float(vector[2]), 1e-9),
        "n_parameters": 3,
        "optimizer_success": bool(result.success),
    }


def _normal_logpdf(values: np.ndarray, loc: float, scale: float) -> np.ndarray:
    return stats.norm.logpdf(values, loc=loc, scale=max(float(scale), 1e-9))


def _gmm2_log_components(values: np.ndarray, means: np.ndarray, scales: np.ndarray, component_weights: np.ndarray) -> np.ndarray:
    return np.column_stack(
        [
            np.log(max(float(component_weights[index]), EPS)) + _normal_logpdf(values, float(means[index]), float(scales[index]))
            for index in range(2)
        ]
    )


def order_components(fit: Mapping[str, Any]) -> dict[str, Any]:
    order = np.argsort(np.asarray(fit["component_means"], dtype=float))
    means = np.asarray(fit["component_means"], dtype=float)[order]
    scales = np.asarray(fit["component_scales"], dtype=float)[order]
    component_weights = np.asarray(fit["component_weights"], dtype=float)[order]
    output = dict(fit)
    output["component_means"] = [float(value) for value in means]
    output["component_scales"] = [float(value) for value in scales]
    output["component_weights"] = [float(value) for value in component_weights]
    output["mean_separation"] = float(abs(means[1] - means[0]))
    output["standardized_separation"] = float(abs(means[1] - means[0]) / max(math.sqrt((scales[0] ** 2 + scales[1] ** 2) / 2), 1e-9))
    output["min_component_weight"] = float(np.min(component_weights))
    return output


def fit_gmm2_weighted(values: np.ndarray, weights: np.ndarray, seed: int = 0) -> dict[str, Any]:
    """Fit a two-component univariate Gaussian mixture by weighted EM."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.size < 4 or values.size != weights.size:
        raise ValueError("GMM-2 requires at least four weighted observations")
    total_weight = float(np.sum(weights))
    spread = max(float(np.std(values)), float(np.ptp(values)) * 1e-4, 1e-6)
    q10, q25, q50, q75, q90 = [weighted_quantile(values, weights, p) for p in (0.10, 0.25, 0.50, 0.75, 0.90)]
    rng = np.random.default_rng(seed)
    initial_pairs = [(q25, q75), (q10, q90), (float(np.min(values)), float(np.max(values)))]
    for _ in range(3):
        initial_pairs.append(tuple(np.sort(rng.choice(values, size=2, replace=False))))
    best: dict[str, Any] | None = None
    scale_floor = max(float(np.ptp(values)) * 1e-5, 1e-6)
    for initial_left, initial_right in initial_pairs:
        if abs(initial_right - initial_left) < scale_floor:
            initial_left, initial_right = q25 - spread * 0.5, q75 + spread * 0.5
        means = np.asarray([initial_left, initial_right], dtype=float)
        scales = np.asarray([max(spread * 0.5, scale_floor)] * 2, dtype=float)
        component_weights = np.asarray([0.5, 0.5], dtype=float)
        previous = -math.inf
        converged = False
        for iteration in range(500):
            log_components = _gmm2_log_components(values, means, scales, component_weights)
            log_total = special.logsumexp(log_components, axis=1)
            responsibilities = np.exp(log_components - log_total[:, None])
            effective = np.sum(weights[:, None] * responsibilities, axis=0)
            if np.any(effective <= EPS):
                break
            means = np.sum(weights[:, None] * responsibilities * values[:, None], axis=0) / effective
            variances = np.sum(weights[:, None] * responsibilities * (values[:, None] - means[None, :]) ** 2, axis=0) / effective
            scales = np.sqrt(np.maximum(variances, scale_floor**2))
            component_weights = effective / total_weight
            log_likelihood = float(np.sum(weights * log_total))
            if abs(log_likelihood - previous) < 1e-9 * max(1.0, abs(previous)):
                converged = True
                break
            previous = log_likelihood
        else:
            log_likelihood = float(np.sum(weights * special.logsumexp(_gmm2_log_components(values, means, scales, component_weights), axis=1)))
        if not np.all(np.isfinite(means)) or not np.all(np.isfinite(scales)) or not math.isfinite(log_likelihood):
            continue
        candidate = order_components(
            {
                "family": "gmm2",
                "component_means": [float(value) for value in means],
                "component_scales": [float(value) for value in scales],
                "component_weights": [float(value) for value in component_weights],
                "log_likelihood": log_likelihood,
                "n_parameters": 5,
                "iterations": iteration + 1,
                "converged": converged,
            }
        )
        if best is None or float(candidate["log_likelihood"]) > float(best["log_likelihood"]):
            best = candidate
    if best is None:
        raise ValueError("GMM-2 optimization did not produce a finite fit")
    return best


def mixture_logpdf(values: np.ndarray, fit: Mapping[str, Any]) -> np.ndarray:
    means = np.asarray(fit["component_means"], dtype=float)
    scales = np.asarray(fit["component_scales"], dtype=float)
    component_weights = np.asarray(fit["component_weights"], dtype=float)
    return special.logsumexp(_gmm2_log_components(np.asarray(values, dtype=float), means, scales, component_weights), axis=1)


def candidate_logpdf(values: np.ndarray, fit: Mapping[str, Any]) -> np.ndarray:
    family = fit["family"]
    if family == "normal":
        return _normal_logpdf(values, float(fit["loc"]), float(fit["scale"]))
    if family == "laplace":
        return stats.laplace.logpdf(values, loc=float(fit["loc"]), scale=float(fit["scale"]))
    if family == "student_t":
        return stats.t.logpdf(values, float(fit["df"]), loc=float(fit["loc"]), scale=float(fit["scale"]))
    if family == "gmm2":
        return mixture_logpdf(values, fit)
    raise ValueError(f"unsupported family: {family}")


def fit_candidate(values: np.ndarray, weights: np.ndarray, family: str, seed: int = 0) -> dict[str, Any]:
    if family == "normal":
        return fit_normal_weighted(values, weights)
    if family == "student_t":
        return fit_student_t_weighted(values, weights)
    if family == "laplace":
        return fit_laplace_weighted(values, weights)
    if family == "gmm2":
        return fit_gmm2_weighted(values, weights, seed=seed)
    raise ValueError(f"unsupported family: {family}")


def score_fit(values: np.ndarray, weights: np.ndarray, fit: Mapping[str, Any]) -> dict[str, Any]:
    logpdf = candidate_logpdf(values, fit)
    if not np.all(np.isfinite(logpdf)):
        raise ValueError(f"non-finite logpdf for {fit['family']}")
    weighted_log_likelihood = float(np.sum(weights * logpdf))
    weight_sum = float(np.sum(weights))
    n_eff = kish_effective_sample_size(weights)
    k = int(fit["n_parameters"])
    aic = 2.0 * k - 2.0 * weighted_log_likelihood
    bic = k * math.log(max(n_eff, 1.0)) - 2.0 * weighted_log_likelihood
    aicc = aic + (2.0 * k * (k + 1.0) / max(n_eff - k - 1.0, 1.0)) if n_eff > k + 1.0 else math.inf
    return {
        "n_observations": int(values.size),
        "weight_sum": weight_sum,
        "kish_effective_sample_size": n_eff,
        "n_parameters": k,
        "weighted_in_sample_log_likelihood": weighted_log_likelihood,
        "log_likelihood_per_weight": weighted_log_likelihood / max(weight_sum, EPS),
        "AIC": aic,
        "AICc": aicc,
        "BIC": bic,
        "fit": dict(fit),
    }


def _serializable_fit(fit: Mapping[str, Any]) -> dict[str, Any]:
    return {key: (value.tolist() if isinstance(value, np.ndarray) else value) for key, value in fit.items()}


def _weighted_histogram(values: np.ndarray, weights: np.ndarray, bins: int = 28) -> tuple[np.ndarray, np.ndarray]:
    low, high = np.quantile(values, [0.005, 0.995])
    pad = max((high - low) * 0.08, 1.0)
    edges = np.linspace(float(low - pad), float(high + pad), bins + 1)
    density, edges = np.histogram(values, bins=edges, weights=weights, density=False)
    density = density / max(float(np.sum(weights)), EPS) / np.diff(edges)
    return density, edges


def _configure_plot_font(matplotlib: Any) -> None:
    """Use an installed Chinese font when available, without changing global files."""
    from matplotlib import font_manager

    if WINDOWS_CHINESE_FONT.exists():
        font_manager.fontManager.addfont(str(WINDOWS_CHINESE_FONT))
        family = font_manager.FontProperties(fname=str(WINDOWS_CHINESE_FONT)).get_name()
        matplotlib.rcParams["font.family"] = family
    matplotlib.rcParams["axes.unicode_minus"] = False


def _plot_parameter(parameter_key: str, values: np.ndarray, weights: np.ndarray, normal_fit: Mapping[str, Any], gmm_fit: Mapping[str, Any], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    _configure_plot_font(matplotlib)
    import matplotlib.pyplot as plt

    colors = {"navy": "#0B1F33", "teal": "#0D8090", "orange": "#E07A3F", "grid": "#D6E0E8", "muted": "#5D6B78"}
    density, edges = _weighted_histogram(values, weights)
    x = np.linspace(float(edges[0]), float(edges[-1]), 500)
    normal_pdf = np.exp(candidate_logpdf(x, normal_fit))
    gmm_pdf = np.exp(candidate_logpdf(x, gmm_fit))
    fig, ax = plt.subplots(figsize=(9.4, 5.0), dpi=180)
    ax.bar((edges[:-1] + edges[1:]) / 2, density, width=np.diff(edges) * 0.90, color=colors["teal"], alpha=0.65, label="加权观测")
    ax.plot(x, normal_pdf, color=colors["navy"], linewidth=2.3, label="正态")
    ax.plot(x, gmm_pdf, color=colors["orange"], linewidth=2.3, label="GMM-2")
    ax.set_title(f"{PARAMETERS[parameter_key]['label']}：正态 vs GMM-2", fontsize=14, color=colors["navy"], weight="bold")
    ax.set_xlabel(f"{PARAMETERS[parameter_key]['label']} / {PARAMETERS[parameter_key]['unit']}", fontsize=11)
    ax.set_ylabel("加权密度", fontsize=11)
    ax.grid(axis="y", color=colors["grid"], linewidth=0.8, alpha=0.8)
    ax.legend(frameon=False, fontsize=10, ncol=3, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _plot_environment_panels(parameter_key: str, rows: Sequence[Mapping[str, Any]], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    _configure_plot_font(matplotlib)
    import matplotlib.pyplot as plt

    groups = sorted({str(row.get("environment_class")) for row in rows})
    colors = {"teal": "#0D8090", "orange": "#E07A3F", "navy": "#0B1F33", "grid": "#D6E0E8"}
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 7.0), dpi=180)
    for axis, group in zip(axes.flat, groups):
        group_rows = [row for row in rows if str(row.get("environment_class")) == group]
        values, weights = as_arrays(group_rows, PARAMETERS[parameter_key]["field"])
        normal_fit = fit_candidate(values, weights, "normal")
        gmm_fit = fit_candidate(values, weights, "gmm2", seed=2026083107)
        density, edges = _weighted_histogram(values, weights, bins=18)
        x = np.linspace(float(edges[0]), float(edges[-1]), 300)
        axis.bar((edges[:-1] + edges[1:]) / 2, density, width=np.diff(edges) * 0.90, color=colors["teal"], alpha=0.62)
        axis.plot(x, np.exp(candidate_logpdf(x, normal_fit)), color=colors["navy"], linewidth=1.8)
        axis.plot(x, np.exp(candidate_logpdf(x, gmm_fit)), color=colors["orange"], linewidth=1.8)
        axis.set_title(group, fontsize=11, color=colors["navy"], weight="bold")
        axis.grid(axis="y", color=colors["grid"], linewidth=0.7, alpha=0.8)
        axis.spines[["top", "right"]].set_visible(False)
    for axis in axes.flat[len(groups):]:
        axis.axis("off")
    fig.suptitle(f"{PARAMETERS[parameter_key]['label']}：按环境查看双峰结构", fontsize=15, color=colors["navy"], weight="bold")
    fig.supxlabel(f"{PARAMETERS[parameter_key]['label']} / {PARAMETERS[parameter_key]['unit']}")
    fig.supylabel("加权密度")
    fig.tight_layout(rect=[0.02, 0.02, 1.0, 0.94])
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _plot_delay_power(rows: Sequence[Mapping[str, Any]], correlation: float, output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    _configure_plot_font(matplotlib)
    import matplotlib.pyplot as plt

    delay, delay_weights = as_arrays(rows, "excess_delay_samples")
    power, power_weights = as_arrays(rows, "relative_power_db")
    if not np.allclose(delay_weights, power_weights):
        raise ValueError("delay/power population weights do not align")
    weights = delay_weights
    environments = [str(row.get("environment_class")) for row in rows]
    palette = {"Urban": "#0D8090", "Special Reflective": "#E07A3F", "Mountain/Valley": "#386A9B", "Highway/Open": "#7B8794"}
    fig, ax = plt.subplots(figsize=(9.4, 5.0), dpi=180)
    for environment in sorted(set(environments)):
        mask = np.asarray([item == environment for item in environments])
        ax.scatter(delay[mask], power[mask], s=8 + 18 * weights[mask], alpha=0.45, color=palette.get(environment, "#0D8090"), label=environment, edgecolors="none")
    # Weighted least-squares trend is a descriptive guide, not a causal fit.
    x_mean = weighted_mean(delay, weights)
    y_mean = weighted_mean(power, weights)
    slope = float(np.sum(weights * (delay - x_mean) * (power - y_mean)) / max(np.sum(weights * (delay - x_mean) ** 2), EPS))
    x_line = np.linspace(float(np.min(delay)), float(np.max(delay)), 200)
    ax.plot(x_line, y_mean + slope * (x_line - x_mean), color="#0B1F33", linewidth=2.6, label="加权趋势")
    ax.set_title("时延–功率联合关系", fontsize=14, color="#0B1F33", weight="bold")
    ax.set_xlabel("多径时延 / samples", fontsize=11)
    ax.set_ylabel("相对功率 / dB", fontsize=11)
    ax.text(0.98, 0.05, f"全局秩高斯相关 ≈ {correlation:.2f}\n统计关联，不代表物理因果", transform=ax.transAxes, ha="right", va="bottom", fontsize=10, color="#0B1F33", bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#D6E0E8"})
    ax.grid(color="#D6E0E8", linewidth=0.8, alpha=0.8)
    ax.legend(frameon=False, fontsize=9, ncol=3, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _fit_and_score(rows: Sequence[Mapping[str, Any]], parameter_key: str, seed: int) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    values, weights = as_arrays(rows, PARAMETERS[parameter_key]["field"])
    fits: dict[str, dict[str, Any]] = {}
    scores: dict[str, dict[str, Any]] = {}
    for offset, family in enumerate(FAMILIES):
        fit = fit_candidate(values, weights, family, seed=seed + offset)
        fits[family] = fit
        scores[family] = score_fit(values, weights, fit)
    return {"values": values, "weights": weights}, {family: {**score, "fit": _serializable_fit(score["fit"])} for family, score in scores.items()}


def _loso(rows: Sequence[Mapping[str, Any]], parameter_key: str, base_seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    field = PARAMETERS[parameter_key]["field"]
    scenes = sorted({str(row.get("scene_id")) for row in rows})
    folds: list[dict[str, Any]] = []
    for fold_index, held_out in enumerate(scenes):
        train = [row for row in rows if str(row.get("scene_id")) != held_out]
        test = [row for row in rows if str(row.get("scene_id")) == held_out]
        test_values, test_weights = as_arrays(test, field)
        for family_index, family in enumerate(FAMILIES):
            train_values, train_weights = as_arrays(train, field)
            fit = fit_candidate(train_values, train_weights, family, seed=base_seed + fold_index * 17 + family_index)
            logpdf = candidate_logpdf(test_values, fit)
            total = float(np.sum(test_weights * logpdf))
            folds.append(
                {
                    "parameter": parameter_key,
                    "held_out_scene": held_out,
                    "family": family,
                    "held_out_observations": int(test_values.size),
                    "held_out_weight_sum": float(np.sum(test_weights)),
                    "held_out_kish_effective_sample_size": kish_effective_sample_size(test_weights),
                    "weighted_held_out_log_likelihood": total,
                    "weighted_held_out_log_likelihood_per_weight": total / max(float(np.sum(test_weights)), EPS),
                    "fit_parameters_json": json.dumps(_serializable_fit(fit), ensure_ascii=False, sort_keys=True),
                }
            )
    summaries: list[dict[str, Any]] = []
    for family in FAMILIES:
        selected = [row for row in folds if row["family"] == family]
        scores = np.asarray([float(row["weighted_held_out_log_likelihood_per_weight"]) for row in selected])
        summaries.append(
            {
                "parameter": parameter_key,
                "family": family,
                "scene_fold_count": len(selected),
                "mean_weighted_held_out_log_likelihood_per_weight": float(np.mean(scores)),
                "median_weighted_held_out_log_likelihood_per_weight": float(np.median(scores)),
                "std_weighted_held_out_log_likelihood_per_weight": float(np.std(scores, ddof=1)),
                "worst_weighted_held_out_log_likelihood_per_weight": float(np.min(scores)),
            }
        )
    return folds, summaries


def _stable_bimodality(score: Mapping[str, Any]) -> bool:
    fit = score["fit"]
    if fit.get("family") != "gmm2":
        return False
    normal_bic = float(score.get("normal_BIC", math.nan))
    gmm_bic = float(score.get("BIC", math.nan))
    return bool(
        float(fit.get("min_component_weight", 0.0)) >= GMM2_MIN_COMPONENT_WEIGHT
        and float(fit.get("standardized_separation", 0.0)) >= GMM2_MIN_STANDARDIZED_SEPARATION
        and normal_bic - gmm_bic >= GMM2_MIN_BIC_IMPROVEMENT
    )


def _scene_summary(rows: Sequence[Mapping[str, Any]], parameter_key: str, seed: int) -> list[dict[str, Any]]:
    field = PARAMETERS[parameter_key]["field"]
    output: list[dict[str, Any]] = []
    for index, scene in enumerate(sorted({str(row.get("scene_id")) for row in rows})):
        scene_rows = [row for row in rows if str(row.get("scene_id")) == scene]
        values, weights = as_arrays(scene_rows, field)
        normal = score_fit(values, weights, fit_candidate(values, weights, "normal", seed=seed + index))
        gmm = score_fit(values, weights, fit_candidate(values, weights, "gmm2", seed=seed + index + 101))
        fit = gmm["fit"]
        gmm["normal_BIC"] = normal["BIC"]
        output.append(
            {
                "parameter": parameter_key,
                "scene_id": scene,
                "observations": int(values.size),
                "weight_sum": float(np.sum(weights)),
                "kish_effective_sample_size": kish_effective_sample_size(weights),
                "component_1_weight": float(fit["component_weights"][0]),
                "component_2_weight": float(fit["component_weights"][1]),
                "component_1_mean": float(fit["component_means"][0]),
                "component_2_mean": float(fit["component_means"][1]),
                "component_1_scale": float(fit["component_scales"][0]),
                "component_2_scale": float(fit["component_scales"][1]),
                "mean_separation": float(fit["mean_separation"]),
                "standardized_separation": float(fit["standardized_separation"]),
                "BIC_normal_minus_gmm2": float(normal["BIC"] - gmm["BIC"]),
                "stable_bimodality": _stable_bimodality(gmm),
            }
        )
    return output


def _group_summary(rows: Sequence[Mapping[str, Any]], parameter_key: str, group_field: str, seed: int) -> list[dict[str, Any]]:
    field = PARAMETERS[parameter_key]["field"]
    group_values = sorted({str(row.get(group_field)) for row in rows if str(row.get(group_field)).strip()})
    output: list[dict[str, Any]] = []
    for index, group in enumerate(group_values):
        group_rows = [row for row in rows if str(row.get(group_field)) == group]
        values, weights = as_arrays(group_rows, field)
        normal = score_fit(values, weights, fit_candidate(values, weights, "normal", seed=seed + index))
        gmm = score_fit(values, weights, fit_candidate(values, weights, "gmm2", seed=seed + index + 101))
        fit = gmm["fit"]
        gmm["normal_BIC"] = normal["BIC"]
        eligible = kish_effective_sample_size(weights) >= MIN_GROUP_EFFECTIVE_SAMPLE_SIZE
        output.append(
            {
                "parameter": parameter_key,
                "grouping": group_field,
                "group": group,
                "observations": int(values.size),
                "weight_sum": float(np.sum(weights)),
                "kish_effective_sample_size": kish_effective_sample_size(weights),
                "component_1_weight": float(fit["component_weights"][0]),
                "component_2_weight": float(fit["component_weights"][1]),
                "component_1_mean": float(fit["component_means"][0]),
                "component_2_mean": float(fit["component_means"][1]),
                "mean_separation": float(fit["mean_separation"]),
                "standardized_separation": float(fit["standardized_separation"]),
                "BIC_normal_minus_gmm2": float(normal["BIC"] - gmm["BIC"]),
                "effective_sample_eligible": eligible,
                "stable_bimodality": bool(eligible and _stable_bimodality(gmm)),
            }
        )
    return output


def _conditional_normal_log_likelihood(rows: Sequence[Mapping[str, Any]], field: str, group_field: str) -> tuple[float, float, int]:
    groups = sorted({str(row.get(group_field)) for row in rows if str(row.get(group_field)).strip()})
    total = 0.0
    weight_sum = 0.0
    used = 0
    for group in groups:
        group_rows = [row for row in rows if str(row.get(group_field)) == group]
        values, weights = as_arrays(group_rows, field)
        fit = fit_normal_weighted(values, weights)
        total += float(np.sum(weights * candidate_logpdf(values, fit)))
        weight_sum += float(np.sum(weights))
        used += 1
    return total, weight_sum, used


def _bootstrap(rows: Sequence[Mapping[str, Any]], parameter_key: str, replicates: int, seed: int) -> list[dict[str, Any]]:
    field = PARAMETERS[parameter_key]["field"]
    scenes = sorted({str(row.get("scene_id")) for row in rows})
    scene_rows = {scene: [row for row in rows if str(row.get("scene_id")) == scene] for scene in scenes}
    rng = np.random.default_rng(seed)
    output: list[dict[str, Any]] = []
    for replicate in range(replicates):
        selected_scenes = rng.choice(scenes, size=len(scenes), replace=True)
        sample_rows = [row for scene in selected_scenes for row in scene_rows[str(scene)]]
        values, weights = as_arrays(sample_rows, field)
        normal = score_fit(values, weights, fit_normal_weighted(values, weights))
        gmm = score_fit(values, weights, fit_gmm2_weighted(values, weights, seed=seed + replicate + 10001))
        fit = gmm["fit"]
        output.append(
            {
                "parameter": parameter_key,
                "replicate": replicate,
                "selected_scene_count": len(selected_scenes),
                "observations": int(values.size),
                "weight_sum": float(np.sum(weights)),
                "kish_effective_sample_size": kish_effective_sample_size(weights),
                "component_1_weight": float(fit["component_weights"][0]),
                "component_2_weight": float(fit["component_weights"][1]),
                "component_1_mean": float(fit["component_means"][0]),
                "component_2_mean": float(fit["component_means"][1]),
                "component_1_scale": float(fit["component_scales"][0]),
                "component_2_scale": float(fit["component_scales"][1]),
                "mean_separation": float(fit["mean_separation"]),
                "standardized_separation": float(fit["standardized_separation"]),
                "BIC_normal_minus_gmm2": float(normal["BIC"] - gmm["BIC"]),
                "log_likelihood_per_weight_normal": float(normal["log_likelihood_per_weight"]),
                "log_likelihood_per_weight_gmm2": float(gmm["log_likelihood_per_weight"]),
                "stable_bimodality": _stable_bimodality({**gmm, "normal_BIC": normal["BIC"]}),
            }
        )
    return output


def _quantiles(values: Iterable[float]) -> tuple[float, float, float]:
    array = np.asarray(list(values), dtype=float)
    return tuple(float(value) for value in np.quantile(array, [0.025, 0.5, 0.975]))


def _bootstrap_summary(rows: Sequence[Mapping[str, Any]], parameter_key: str) -> dict[str, Any]:
    selected = [row for row in rows if row["parameter"] == parameter_key]
    stable_rate = float(np.mean([bool(row["stable_bimodality"]) for row in selected]))
    min_weight = [min(float(row["component_1_weight"]), float(row["component_2_weight"])) for row in selected]
    separation = [float(row["standardized_separation"]) for row in selected]
    bic_delta = [float(row["BIC_normal_minus_gmm2"]) for row in selected]
    ll_delta = [float(row["log_likelihood_per_weight_gmm2"]) - float(row["log_likelihood_per_weight_normal"]) for row in selected]
    return {
        "parameter": parameter_key,
        "replicates": len(selected),
        "stable_bimodality_rate": stable_rate,
        "component_min_weight_q025_median_q975": _quantiles(min_weight),
        "standardized_separation_q025_median_q975": _quantiles(separation),
        "BIC_normal_minus_gmm2_q025_median_q975": _quantiles(bic_delta),
        "log_likelihood_per_weight_delta_q025_median_q975": _quantiles(ll_delta),
        "BIC_win_rate": float(np.mean(np.asarray(bic_delta) > 0.0)),
        "LOSO_like_in_sample_likelihood_win_rate": float(np.mean(np.asarray(ll_delta) > 0.0)),
    }


def _recommendation(
    global_score: Mapping[str, Any],
    loso_rows: Sequence[Mapping[str, Any]],
    bootstrap_summary: Mapping[str, Any],
    scene_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, dict[str, Any]]:
    gmm = global_score["gmm2"]
    normal = global_score["normal"]
    loso_gmm = next(row for row in loso_rows if row["family"] == "gmm2")
    loso_single = max((row for row in loso_rows if row["family"] != "gmm2"), key=lambda row: float(row["mean_weighted_held_out_log_likelihood_per_weight"]))
    loso_gain = float(loso_gmm["mean_weighted_held_out_log_likelihood_per_weight"]) - float(loso_single["mean_weighted_held_out_log_likelihood_per_weight"])
    global_bic_gain = float(normal["BIC"] - gmm["BIC"])
    global_ll_gain = float(gmm["log_likelihood_per_weight"] - normal["log_likelihood_per_weight"])
    scene_eligible = [row for row in scene_rows if float(row["kish_effective_sample_size"]) >= MIN_GROUP_EFFECTIVE_SAMPLE_SIZE]
    scene_stable_rate = float(np.mean([bool(row["stable_bimodality"]) for row in scene_eligible])) if scene_eligible else 0.0
    bootstrap_stable_rate = float(bootstrap_summary["stable_bimodality_rate"])
    bic_win_rate = float(bootstrap_summary["BIC_win_rate"])
    strong = bool(
        global_bic_gain >= 10.0
        and loso_gain > 0.01
        and bootstrap_stable_rate >= 0.70
        and bic_win_rate >= 0.70
        and scene_stable_rate >= 0.50
        and float(gmm["fit"]["min_component_weight"]) >= GMM2_MIN_COMPONENT_WEIGHT
    )
    weak_or_mixed = bool(
        global_bic_gain > 0.0
        and (
            global_ll_gain > 0.001
            or loso_gain > 0.0
            or bootstrap_stable_rate >= 0.40
            or bic_win_rate >= 0.60
        )
    )
    status = "RECOMMENDED" if strong else "CONDITIONAL" if weak_or_mixed else "NOT_RECOMMENDED"
    diagnostics = {
        "global_BIC_gain_normal_minus_gmm2": global_bic_gain,
        "global_log_likelihood_per_weight_gain": global_ll_gain,
        "LOSO_gain_vs_best_single_family_per_weight": loso_gain,
        "best_single_family_by_LOSO": loso_single["family"],
        "eligible_scene_count": len(scene_eligible),
        "scene_stable_bimodality_rate": scene_stable_rate,
        "bootstrap_stable_bimodality_rate": bootstrap_stable_rate,
        "bootstrap_BIC_win_rate": bic_win_rate,
        "decision_rule": {
            "RECOMMENDED": "global BIC gain >= 10, LOSO gain > 0.01 per weight, bootstrap stability >= 70%, bootstrap BIC win rate >= 70%, and at least half eligible scenes stable",
            "CONDITIONAL": "positive global evidence but at least one required out-of-sample or grouped stability criterion is not strong",
            "NOT_RECOMMENDED": "no consistent evidence beyond the canonical single-family fit",
        },
    }
    return status, diagnostics


def _mixing_analysis(
    rows: Sequence[Mapping[str, Any]],
    parameter_key: str,
    global_scores: Mapping[str, Any],
    scene_summary: Sequence[Mapping[str, Any]],
    environment_summary: Sequence[Mapping[str, Any]],
    elevation_summary: Sequence[Mapping[str, Any]],
) -> tuple[str, dict[str, Any]]:
    field = PARAMETERS[parameter_key]["field"]
    global_normal_ll = float(global_scores["normal"]["weighted_in_sample_log_likelihood"])
    global_gmm_ll = float(global_scores["gmm2"]["weighted_in_sample_log_likelihood"])
    global_weight = float(global_scores["normal"]["weight_sum"])
    env_ll, env_weight, env_groups = _conditional_normal_log_likelihood(rows, field, "environment_class")
    elevation_rows = [row for row in rows if str(row.get("elevation_band")).strip()]
    elev_ll, elev_weight, elev_groups = _conditional_normal_log_likelihood(elevation_rows, field, "elevation_band")
    global_gain = (global_gmm_ll - global_normal_ll) / max(global_weight, EPS)
    env_gain = (env_ll - global_normal_ll) / max(env_weight, EPS)
    # The elevation subset has a different denominator because 67 observations
    # are not elevation-ready; the comparison is still explicitly labeled.
    elev_global_normal = score_fit(*as_arrays(elevation_rows, field), fit_normal_weighted(*as_arrays(elevation_rows, field)))["weighted_in_sample_log_likelihood"]
    elev_gain = (elev_ll - elev_global_normal) / max(elev_weight, EPS)
    max_gain = max(env_gain, elev_gain)
    scene_stable_rate = float(np.mean([bool(row["stable_bimodality"]) for row in scene_summary])) if scene_summary else 0.0
    env_eligible = [row for row in environment_summary if bool(row["effective_sample_eligible"])]
    elev_eligible = [row for row in elevation_summary if bool(row["effective_sample_eligible"])]
    env_stable_rate = float(np.mean([bool(row["stable_bimodality"]) for row in env_eligible])) if env_eligible else 0.0
    elev_stable_rate = float(np.mean([bool(row["stable_bimodality"]) for row in elev_eligible])) if elev_eligible else 0.0
    global_stable = _stable_bimodality({**global_scores["gmm2"], "normal_BIC": global_scores["normal"]["BIC"]})
    if not global_stable:
        classification = "INCONCLUSIVE"
    elif max_gain >= 0.75 * max(global_gain, EPS) and max(env_stable_rate, elev_stable_rate) == 0.0:
        classification = "YES"
    elif max_gain >= 0.35 * max(global_gain, EPS) or max(env_stable_rate, elev_stable_rate) < 0.50:
        classification = "PARTIAL"
    else:
        classification = "NO"
    return classification, {
        "global_stable_bimodality": global_stable,
        "global_GMM2_gain_per_weight_vs_normal": global_gain,
        "environment_conditional_normal_gain_per_weight": env_gain,
        "elevation_conditional_normal_gain_per_weight": elev_gain,
        "environment_group_count": env_groups,
        "elevation_group_count": elev_groups,
        "scene_stable_bimodality_rate": scene_stable_rate,
        "environment_stable_bimodality_rate": env_stable_rate,
        "elevation_stable_bimodality_rate": elev_stable_rate,
        "interpretation": "group-conditional Normal gains are diagnostic of mixture contribution; they do not establish physical causality",
    }


def _validate_population(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(rows) != 783:
        raise ValueError(f"expected 783 Stage3 observations, got {len(rows)}")
    by_track: dict[str, list[float]] = {}
    bad_weights = 0
    for row in rows:
        track = str(row.get("track_id"))
        weight = finite(row.get("track_weight"))
        track_size = finite(row.get("track_observation_count"))
        if weight is None or track_size is None or abs(weight - 1.0 / track_size) > 1e-9:
            bad_weights += 1
        by_track.setdefault(track, []).append(float(weight or 0.0))
    conservation_bad = [track for track, values in by_track.items() if abs(sum(values) - 1.0) > 1e-9]
    if bad_weights or conservation_bad:
        raise ValueError(f"weight contract failed: bad_rows={bad_weights}, bad_tracks={len(conservation_bad)}")
    return {
        "observations": len(rows),
        "algorithm_tracks": len(by_track),
        "weight_sum": float(sum(float(row["track_weight"]) for row in rows)),
        "scenes": len({str(row.get("scene_id")) for row in rows}),
        "runs": len({str(row.get("run_id")) for row in rows}),
        "prns": len({str(row.get("prn")) for row in rows}),
        "elevation_ready_observations": sum(bool(str(row.get("elevation_band")).strip()) for row in rows),
    }


def _ensure_new_only_output(root: Path, output: Path) -> None:
    expected_parent = (root / "dataset_generation_logs" / "channel_modeling").resolve()
    output = output.resolve()
    if output.parent != expected_parent:
        raise ValueError("GMM-2 output must be directly under dataset_generation_logs/channel_modeling")
    if not output.name.startswith("phase1_gmm2_sensitivity_audit_"):
        raise ValueError("GMM-2 output namespace must start with phase1_gmm2_sensitivity_audit_")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"new-only output already contains files: {output}")
    output.mkdir(parents=True, exist_ok=True)


def _report_text(
    output: Path,
    population: Mapping[str, Any],
    results: Mapping[str, Any],
    source_hashes: Mapping[str, str],
    bootstrap_replicates: int,
) -> str:
    lines = [
        "# Phase-1 GMM-2 Sensitivity Audit",
        "",
        "本目录是只读敏感性审计，不是 canonical r3 模型替换。所有输出均为 new-only 派生结果。",
        "",
        "## 审计边界",
        "",
        f"- 输入：r3 Stage3 academic population；观测数={population['observations']}，algorithm-level tracks={population['algorithm_tracks']}，权重和={population['weight_sum']:.1f}。",
        "- 权重：沿用 `track_weight = 1 / algorithm_track_size`；按完整 scene block 做 bootstrap。",
        f"- scene-block bootstrap：{bootstrap_replicates} 次；grouped LOSO：按 scene 留一。",
        "- 比较族：Normal、Student-t、Laplace、GMM-2；AIC/AICc/BIC 使用 Kish 有效样本量用于加权修正。",
        "- canonical r3 保持：Doppler=Normal、Power=Normal；joint layer=Gaussian Copula。",
        "",
        "## 审计结论",
        "",
    ]
    for key, label in (("doppler", "Doppler"), ("power", "Power")):
        result = results[key]
        lines.extend(
            [
                f"### {label}",
                "",
                f"- `GMM2_FOR_{label.upper()}` = **{result['recommendation']}**",
                f"- `DOES_BIMODALITY_SURVIVE_SCENE_BLOCK_VALIDATION` = **{result['bimodality_survives_scene_block_validation']}**",
                f"- `IS_BIMODALITY_EXPLAINED_BY_ENVIRONMENT_OR_ELEVATION_MIXING` = **{result['bimodality_explained_by_environment_or_elevation_mixing']}**",
                f"- 全局 BIC 改善（Normal − GMM-2）={result['recommendation_diagnostics']['global_BIC_gain_normal_minus_gmm2']:.2f}；LOSO 相对最佳单模型增益={result['recommendation_diagnostics']['LOSO_gain_vs_best_single_family_per_weight']:.4f}/weight。",
                f"- bootstrap 双峰稳定率={result['bootstrap_summary']['stable_bimodality_rate']:.1%}；bootstrap BIC 胜率={result['bootstrap_summary']['BIC_win_rate']:.1%}；eligible scene 双峰稳定率={result['recommendation_diagnostics']['scene_stable_bimodality_rate']:.1%}。",
                "",
            ]
        )
    lines.extend(
        [
            "## 论文口径",
            "",
            "- GMM-2 只可作为本审计给出的补充 sensitivity model / candidate；无论结论为何，都不覆盖 canonical r3。",
            "- 若训练集拟合改善但 grouped LOSO 或 scene-block component 稳定性不足，不能宣称 GMM-2 更好。",
            "- 相关性与双峰诊断是统计关联/模型选择证据，不证明物理因果，也不把 algorithm-level tracks 解释为物理反射体轨迹。",
            "",
            "## 输入哈希",
            "",
        ]
    )
    for path, digest in source_hashes.items():
        lines.append(f"- `{path}`: `{digest}`")
    lines.extend(["", "## 执行记录", "", "- MATLAB：NO", "- SAGE：NO", "- raw IQ：NO", "- 20.46 MHz：NO", "- AI training：NO", "- canonical r3/r2 数值结果修改：NO", ""])
    return "\n".join(lines) + "\n"


def run_audit(project_root: Path, output_dir: Path, bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES, bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    _ensure_new_only_output(project_root, output_dir)
    r3_dir = project_root / "dataset_generation_logs" / "channel_modeling" / "environment_elevation_stage3_path_model_v1_20260829_r3"
    r2_dir = project_root / "dataset_generation_logs" / "channel_modeling" / "phase1_scientific_closure_20260830_r2"
    population_path = r3_dir / "source_population_audit.csv"
    joint_path = r3_dir / "joint_dependence_models.csv"
    selected_path = r3_dir / "selected_marginal_models.csv"
    r3_manifest = r3_dir / "model_manifest.json"
    r2_closure_manifest = r2_dir / "closure_manifest.json"
    for path in (population_path, joint_path, selected_path, r3_manifest, r2_closure_manifest):
        if not path.exists():
            raise FileNotFoundError(path)
    raw_rows = read_csv(population_path)
    rows = [row for row in raw_rows if row.get("academic_eligible") == "True" and row.get("persistence_pass") == "1"]
    population = _validate_population(rows)
    source_hashes = {str(path.relative_to(project_root)): sha256(path) for path in (population_path, selected_path, joint_path, r3_manifest, r2_closure_manifest)}
    joint_rows = read_csv(joint_path)
    global_joint = next(row for row in joint_rows if row.get("scope") == "global" and row.get("scope_id") == "global")
    global_delay_power_corr = float(global_joint["corr__excess_delay_samples__relative_power_db"])
    results: dict[str, Any] = {}
    all_loso_folds: list[dict[str, Any]] = []
    all_loso_summaries: list[dict[str, Any]] = []
    all_scene_rows: list[dict[str, Any]] = []
    all_environment_rows: list[dict[str, Any]] = []
    all_elevation_rows: list[dict[str, Any]] = []
    all_bootstrap_rows: list[dict[str, Any]] = []
    for parameter_index, parameter_key in enumerate(PARAMETERS):
        arrays, score_map = _fit_and_score(rows, parameter_key, seed=bootstrap_seed + parameter_index * 101)
        for family in FAMILIES:
            score_map[family]["fit"] = _serializable_fit(score_map[family]["fit"])
        loso_folds, loso_summaries = _loso(rows, parameter_key, base_seed=bootstrap_seed + parameter_index * 1001)
        scene_rows = _scene_summary(rows, parameter_key, seed=bootstrap_seed + parameter_index * 2001)
        environment_rows = _group_summary(rows, parameter_key, "environment_class", seed=bootstrap_seed + parameter_index * 3001)
        elevation_rows = _group_summary([row for row in rows if str(row.get("elevation_band")).strip()], parameter_key, "elevation_band", seed=bootstrap_seed + parameter_index * 4001)
        bootstrap_rows = _bootstrap(rows, parameter_key, bootstrap_replicates, seed=bootstrap_seed + parameter_index * 5001)
        bootstrap_summary = _bootstrap_summary(bootstrap_rows, parameter_key)
        recommendation, recommendation_diagnostics = _recommendation(score_map, loso_summaries, bootstrap_summary, scene_rows)
        survives = "YES" if recommendation_diagnostics["scene_stable_bimodality_rate"] >= 0.60 and bootstrap_summary["stable_bimodality_rate"] >= 0.70 else "PARTIAL" if recommendation_diagnostics["scene_stable_bimodality_rate"] >= 0.25 or bootstrap_summary["stable_bimodality_rate"] >= 0.40 else "NO"
        mixing, mixing_diagnostics = _mixing_analysis(rows, parameter_key, score_map, scene_rows, environment_rows, elevation_rows)
        results[parameter_key] = {
            "recommendation": recommendation,
            "bimodality_survives_scene_block_validation": survives,
            "bimodality_explained_by_environment_or_elevation_mixing": mixing,
            "global_scores": score_map,
            "loso_summaries": loso_summaries,
            "bootstrap_summary": bootstrap_summary,
            "recommendation_diagnostics": recommendation_diagnostics,
            "mixing_diagnostics": mixing_diagnostics,
        }
        all_loso_folds.extend(loso_folds)
        all_loso_summaries.extend(loso_summaries)
        all_scene_rows.extend(scene_rows)
        all_environment_rows.extend(environment_rows)
        all_elevation_rows.extend(elevation_rows)
        all_bootstrap_rows.extend(bootstrap_rows)
        _plot_parameter(parameter_key, arrays["values"], arrays["weights"], score_map["normal"]["fit"], score_map["gmm2"]["fit"], output_dir / f"{parameter_key}_normal_vs_gmm2.png")
        _plot_environment_panels(parameter_key, rows, output_dir / f"{parameter_key}_environment_panels.png")
    _plot_delay_power(rows, global_delay_power_corr, output_dir / "joint_delay_power_scatter.png")

    score_rows: list[dict[str, Any]] = []
    for parameter_key, result in results.items():
        for family, score in result["global_scores"].items():
            score_rows.append({
                "parameter": parameter_key,
                "family": family,
                **{key: value for key, value in score.items() if key != "fit"},
                "fit_parameters_json": json.dumps(score["fit"], ensure_ascii=False, sort_keys=True),
            })
    write_csv(output_dir / "candidate_scores.csv", score_rows, ["parameter", "family", "n_observations", "weight_sum", "kish_effective_sample_size", "n_parameters", "weighted_in_sample_log_likelihood", "log_likelihood_per_weight", "AIC", "AICc", "BIC", "fit_parameters_json"])
    write_csv(output_dir / "grouped_loso_folds.csv", all_loso_folds, ["parameter", "held_out_scene", "family", "held_out_observations", "held_out_weight_sum", "held_out_kish_effective_sample_size", "weighted_held_out_log_likelihood", "weighted_held_out_log_likelihood_per_weight", "fit_parameters_json"])
    write_csv(output_dir / "grouped_loso_summary.csv", all_loso_summaries, ["parameter", "family", "scene_fold_count", "mean_weighted_held_out_log_likelihood_per_weight", "median_weighted_held_out_log_likelihood_per_weight", "std_weighted_held_out_log_likelihood_per_weight", "worst_weighted_held_out_log_likelihood_per_weight"])
    write_csv(output_dir / "scene_gmm2_summary.csv", all_scene_rows, ["parameter", "scene_id", "observations", "weight_sum", "kish_effective_sample_size", "component_1_weight", "component_2_weight", "component_1_mean", "component_2_mean", "component_1_scale", "component_2_scale", "mean_separation", "standardized_separation", "BIC_normal_minus_gmm2", "stable_bimodality"])
    write_csv(output_dir / "group_gmm2_summary.csv", all_environment_rows + all_elevation_rows, ["parameter", "grouping", "group", "observations", "weight_sum", "kish_effective_sample_size", "component_1_weight", "component_2_weight", "component_1_mean", "component_2_mean", "mean_separation", "standardized_separation", "BIC_normal_minus_gmm2", "effective_sample_eligible", "stable_bimodality"])
    write_csv(output_dir / "scene_block_bootstrap_gmm2.csv", all_bootstrap_rows, ["parameter", "replicate", "selected_scene_count", "observations", "weight_sum", "kish_effective_sample_size", "component_1_weight", "component_2_weight", "component_1_mean", "component_2_mean", "component_1_scale", "component_2_scale", "mean_separation", "standardized_separation", "BIC_normal_minus_gmm2", "log_likelihood_per_weight_normal", "log_likelihood_per_weight_gmm2", "stable_bimodality"])

    result_payload = {
        "audit_id": output_dir.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETED_READ_ONLY",
        "canonical_model_unchanged": True,
        "execution_boundary": {"matlab": False, "sage": False, "raw_iq_read": False, "process_20_46_mhz": False, "train_ai": False, "canonical_refit": False},
        "population": population,
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": bootstrap_seed,
        "global_joint_delay_power_rank_gaussian_correlation": global_delay_power_corr,
        "results": results,
        "source_hashes": source_hashes,
        "outputs": sorted(path.name for path in output_dir.iterdir()),
    }
    write_json(output_dir / "gmm2_audit_result.json", result_payload)
    audit_config = {
        "input_population": str(population_path.relative_to(project_root)),
        "canonical_r3": "environment_elevation_stage3_path_model_v1_20260829_r3",
        "canonical_r2": "phase1_scientific_closure_20260830_r2",
        "weighting": "track_weight = 1 / algorithm_track_size",
        "families": list(FAMILIES),
        "bootstrap": {"type": "scene_block", "replicates": bootstrap_replicates, "seed": bootstrap_seed},
        "loso": "grouped leave-one-scene-out",
        "information_criteria": "weighted log-likelihood; AIC/AICc/BIC with Kish effective sample size",
        "decision_thresholds": {"min_component_weight": GMM2_MIN_COMPONENT_WEIGHT, "min_standardized_separation": GMM2_MIN_STANDARDIZED_SEPARATION, "min_BIC_improvement": GMM2_MIN_BIC_IMPROVEMENT, "min_group_effective_sample_size": MIN_GROUP_EFFECTIVE_SAMPLE_SIZE},
        "new_only": True,
        "canonical_update": False,
    }
    write_json(output_dir / "audit_config.json", audit_config)
    (output_dir / "audit_report.md").write_text(_report_text(output_dir, population, results, source_hashes, bootstrap_replicates), encoding="utf-8")
    expected_files = {
        "candidate_scores.csv", "grouped_loso_folds.csv", "grouped_loso_summary.csv", "scene_gmm2_summary.csv", "group_gmm2_summary.csv", "scene_block_bootstrap_gmm2.csv", "gmm2_audit_result.json", "audit_config.json", "audit_report.md", "doppler_normal_vs_gmm2.png", "power_normal_vs_gmm2.png", "doppler_environment_panels.png", "power_environment_panels.png", "joint_delay_power_scatter.png",
    }
    actual_files = {path.name for path in output_dir.iterdir()}
    qa = {
        "status": "PASS" if expected_files.issubset(actual_files) else "REJECTED",
        "checks": {
            "population_783": population["observations"] == 783,
            "track_weight_contract": abs(population["weight_sum"] - population["algorithm_tracks"]) < 1e-9,
            "expected_outputs_present": expected_files.issubset(actual_files),
            "canonical_update": False,
            "execution_boundary_clean": True,
            "output_namespace_new_only": output_dir.name.startswith("phase1_gmm2_sensitivity_audit_"),
        },
        "output_file_count": len(actual_files),
        "canonical_input_hashes": source_hashes,
    }
    write_json(output_dir / "independent_qa_result.json", qa)
    result_payload["outputs"] = sorted(path.name for path in output_dir.iterdir())
    return result_payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=DEFAULT_BOOTSTRAP_REPLICATES)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    args = parser.parse_args(argv)
    if args.bootstrap_replicates < 100:
        print("GMM2_AUDIT_REJECTED=bootstrap replicates must be >= 100", file=sys.stderr)
        return 2
    try:
        result = run_audit(args.project_root, args.output_dir, args.bootstrap_replicates, args.bootstrap_seed)
    except Exception as exc:
        print(f"GMM2_AUDIT_REJECTED={exc}", file=sys.stderr)
        return 2
    print(json.dumps({"audit_id": result["audit_id"], "status": result["status"], "results": {key: {"recommendation": value["recommendation"], "bimodality_survives_scene_block_validation": value["bimodality_survives_scene_block_validation"], "bimodality_explained_by_environment_or_elevation_mixing": value["bimodality_explained_by_environment_or_elevation_mixing"]} for key, value in result["results"].items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
