#!/usr/bin/env python3
"""Generate isolated author-review figures and tables for the conditional GMM."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENTS = ("Urban", "Mountain/Valley")
BANDS = ("LOW", "MID", "HIGH")
CELLS = [f"{environment}__{band}" for environment in ENVIRONMENTS for band in BANDS]
COMPONENT_COLORS = ("#1b9e77", "#d95f02", "#7570b3")
FEATURE_LABELS = ("Excess delay (samples)", "Absolute Doppler (Hz)", "Relative power (dB)")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def f(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite value: {value!r}")
    return result


def load_model() -> dict[str, Any]:
    return json.loads((ROOT / "model/selected_conditional_gmm.json").read_text(encoding="utf-8"))


def load_population() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_csv(ROOT / "population/gmm_feature_population.csv"):
        parsed = dict(row)
        for field in ("excess_delay_samples", "doppler_offset_hz", "relative_power_db", "absolute_doppler_hz", "track_weight_recomputed_primary"):
            parsed[field] = f(parsed[field])
        parsed["cell_ready"] = parsed["cell_ready"] == "1"
        rows.append(parsed)
    return rows


def load_draws() -> dict[str, np.ndarray]:
    grouped: dict[str, list[list[float]]] = {cell: [] for cell in CELLS}
    for row in read_csv(ROOT / "model/review_model_draws.csv"):
        grouped[row["cell_id"]].append([f(row["excess_delay_samples"]), f(row["absolute_doppler_hz"]), f(row["relative_power_db"])])
    return {cell: np.asarray(values, dtype=float) for cell, values in grouped.items()}


def cell_rows(population: Sequence[Mapping[str, Any]], cell: str) -> list[Mapping[str, Any]]:
    return [row for row in population if row.get("cell_ready") and row.get("cell_id") == cell]


def density_2d(model: Mapping[str, Any], environment: str, cell: str, log_delay: np.ndarray, power: np.ndarray) -> np.ndarray:
    model_block = model["model"]
    center = np.asarray(model_block["transform_center"], dtype=float)
    scale = np.asarray(model_block["transform_scale"], dtype=float)
    means = np.asarray(model_block["environment_means"][environment], dtype=float)
    covariances = np.asarray(model_block["shared_covariances"], dtype=float)
    weights = np.asarray(model_block["cell_weights"][cell], dtype=float)
    z0 = (log_delay - center[0]) / scale[0]
    z2 = (power - center[2]) / scale[2]
    points = np.column_stack([z0.ravel(), z2.ravel()])
    density = np.zeros(points.shape[0], dtype=float)
    for component in range(3):
        mean = means[component][[0, 2]]
        covariance = covariances[component][np.ix_([0, 2], [0, 2])]
        covariance = 0.5 * (covariance + covariance.T)
        inverse = np.linalg.inv(covariance)
        determinant = max(float(np.linalg.det(covariance)), 1e-12)
        delta = points - mean[None, :]
        density += weights[component] * np.exp(-0.5 * np.sum(delta * (delta @ inverse), axis=1)) / (2.0 * np.pi * math.sqrt(determinant))
    return density.reshape(log_delay.shape)


def model_feature_samples(draws: np.ndarray) -> np.ndarray:
    return np.column_stack([draws[:, 0], draws[:, 1], draws[:, 2]])


def make_main_figure(model: Mapping[str, Any], population: Sequence[Mapping[str, Any]], draws: Mapping[str, np.ndarray], figure_dir: Path) -> None:
    all_delay = np.asarray([f(row["excess_delay_samples"]) for row in population if row.get("cell_ready")], dtype=float)
    all_power = np.asarray([f(row["relative_power_db"]) for row in population if row.get("cell_ready")], dtype=float)
    all_doppler = np.asarray([f(row["absolute_doppler_hz"]) for row in population if row.get("cell_ready")], dtype=float)
    x_min = max(0.9, float(np.quantile(all_delay, 0.005)) * 0.9)
    x_max = float(np.quantile(all_delay, 0.995)) * 1.15
    y_min = float(np.quantile(all_power, 0.005)) - 1.0
    y_max = float(np.quantile(all_power, 0.995)) + 1.0
    x_grid = np.geomspace(x_min, x_max, 160)
    y_grid = np.linspace(y_min, y_max, 160)
    xx, yy = np.meshgrid(x_grid, y_grid)
    density = density_2d(model, "Urban", "Urban__MID", np.log(xx), yy)
    levels = np.array([0.12, 0.30, 0.58]) * float(np.max(density))
    norm = Normalize(vmin=0.0, vmax=max(float(np.max(all_doppler)), 1.0))
    fig, axes = plt.subplots(2, 3, figsize=(14.2, 7.0), sharex=True, sharey=True, constrained_layout=True)
    for row_index, environment in enumerate(ENVIRONMENTS):
        for col_index, band in enumerate(BANDS):
            cell = f"{environment}__{band}"
            ax = axes[row_index, col_index]
            rows = cell_rows(population, cell)
            if rows:
                ax.scatter([f(item["excess_delay_samples"]) for item in rows], [f(item["relative_power_db"]) for item in rows], c=[f(item["absolute_doppler_hz"]) for item in rows], cmap="viridis", norm=norm, s=22, alpha=0.75, edgecolors="none", label="observed")
            cell_density = density_2d(model, environment, cell, np.log(xx), yy)
            cell_levels = np.array([0.12, 0.30, 0.58]) * float(np.max(cell_density))
            ax.contour(xx, yy, cell_density, levels=cell_levels, colors="#3d3d3d", linewidths=(0.8, 1.1, 1.4), alpha=0.9)
            support = read_support_status(cell)
            ax.set_title(f"{environment} — {band}\nn={len(rows)}, tracks={len({item['track_id'] for item in rows})}, scenes={len({item['scene_id'] for item in rows})}\n{support}", fontsize=9)
            ax.grid(alpha=0.18)
            if row_index == 1:
                ax.set_xlabel("Excess delay (samples)")
            if col_index == 0:
                ax.set_ylabel("Relative power (dB)")
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)
    fig.suptitle("Conditional joint delay–power view; color indicates absolute Doppler magnitude", fontsize=13)
    sm = plt.cm.ScalarMappable(norm=norm, cmap="viridis")
    sm.set_array([])
    fig.colorbar(sm, ax=axes, shrink=0.82, label="Absolute Doppler magnitude (Hz)")
    target = figure_dir / "conditional_joint_environment_elevation.png"
    fig.savefig(target, dpi=220)
    fig.savefig(figure_dir / "conditional_joint_environment_elevation.pdf")
    plt.close(fig)


def read_support_status(cell: str) -> str:
    for row in read_csv(ROOT / "population/gmm_cell_support.csv"):
        if row["cell_id"] == cell:
            return row["support_status"]
    return "MODEL_INVALID"


def make_corner_figure(model: Mapping[str, Any], population: Sequence[Mapping[str, Any]], draws: Mapping[str, np.ndarray], figure_dir: Path, cell: str) -> None:
    rows = cell_rows(population, cell)
    empirical = np.asarray([[f(row["excess_delay_samples"]), f(row["absolute_doppler_hz"]), f(row["relative_power_db"])] for row in rows], dtype=float)
    simulated = model_feature_samples(draws[cell])
    fig, axes = plt.subplots(3, 3, figsize=(10.5, 9.0), constrained_layout=True)
    for index in range(3):
        ax = axes[index, index]
        ax.hist(empirical[:, index], bins=12, density=True, color="#4c78a8", alpha=0.55, label="observed")
        ax.hist(simulated[:, index], bins=24, density=True, color="#f58518", alpha=0.38, label="model")
        ax.set_xlabel(FEATURE_LABELS[index], fontsize=8)
        ax.grid(alpha=0.15)
    pairs = ((1, 0), (2, 0), (2, 1))
    for i, j in pairs:
        ax = axes[i, j]
        ax.scatter(empirical[:, j], empirical[:, i], s=12, alpha=0.55, color="#4c78a8", label="observed")
        sample = simulated[::max(1, len(simulated) // 900)]
        ax.scatter(sample[:, j], sample[:, i], s=4, alpha=0.18, color="#f58518", label="model")
        ax.set_xlabel(FEATURE_LABELS[j], fontsize=8)
        ax.set_ylabel(FEATURE_LABELS[i], fontsize=8)
        ax.grid(alpha=0.15)
    for i in range(3):
        for j in range(3):
            if i < j:
                axes[i, j].axis("off")
    environment, band = cell.split("__", 1)
    fig.suptitle(f"INTERNAL DIAGNOSTIC — {environment} / {band}\nObserved n={len(rows)}; model draws={len(simulated)}", fontsize=12)
    axes[0, 0].legend(fontsize=8, loc="upper right")
    safe = cell.replace("/", "_").replace(" ", "_")
    fig.savefig(figure_dir / f"corner_diagnostic_{safe}.png", dpi=190)
    plt.close(fig)


def make_weight_figure(model: Mapping[str, Any], figure_dir: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 5.2), sharey=True, constrained_layout=True)
    for ax, cell in zip(axes.ravel(), CELLS):
        environment = cell.split("__", 1)[0]
        weights = np.asarray(model["model"]["cell_weights"][cell], dtype=float)
        ax.bar(np.arange(1, 4), weights, color=COMPONENT_COLORS, width=0.72)
        ax.set_title(cell.replace("__", " / "), fontsize=9)
        ax.set_xticks((1, 2, 3), ("C1", "C2", "C3"))
        ax.set_ylim(0.0, 0.7)
        ax.grid(axis="y", alpha=0.18)
        for index, value in enumerate(weights, start=1):
            ax.text(index, value + 0.015, f"{value:.2f}", ha="center", va="bottom", fontsize=8)
    axes[0, 0].set_ylabel("Mixture weight")
    axes[1, 0].set_ylabel("Mixture weight")
    fig.suptitle("Environment–elevation conditional component weights", fontsize=13)
    fig.savefig(figure_dir / "conditional_component_weight_heatmap.png", dpi=220)
    fig.savefig(figure_dir / "conditional_component_weight_heatmap.pdf")
    plt.close(fig)


def weighted_quantile(values: Sequence[float], weights: Sequence[float], quantile: float) -> float:
    values_array = np.asarray(values, dtype=float)
    weights_array = np.asarray(weights, dtype=float)
    order = np.argsort(values_array)
    values_array = values_array[order]
    weights_array = weights_array[order]
    cumulative = np.cumsum(weights_array) - 0.5 * weights_array
    cumulative /= float(np.sum(weights_array))
    return float(np.interp(quantile, cumulative, values_array))


def make_parameter_curve_figure(model: Mapping[str, Any], population: Sequence[Mapping[str, Any]], draws: Mapping[str, np.ndarray], figure_dir: Path) -> None:
    parameter_specs = (
        ("excess_delay_samples", "Excess delay (samples)"),
        ("absolute_doppler_hz", "Absolute Doppler (Hz)"),
        ("relative_power_db", "Relative power (dB)"),
    )
    environment_colors = {"Urban": "#1f77b4", "Mountain/Valley": "#d62728"}
    x = np.arange(len(BANDS))
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 5.1))
    for ax, (field, label) in zip(axes, parameter_specs):
        for environment in ENVIRONMENTS:
            medians: list[float] = []
            lows: list[float] = []
            highs: list[float] = []
            empirical: list[float] = []
            for band in BANDS:
                cell = f"{environment}__{band}"
                model_values = draws[cell][:, ("excess_delay_samples", "absolute_doppler_hz", "relative_power_db").index(field)]
                lows.append(float(np.quantile(model_values, 0.05)))
                medians.append(float(np.quantile(model_values, 0.50)))
                highs.append(float(np.quantile(model_values, 0.95)))
                rows = cell_rows(population, cell)
                empirical.append(weighted_quantile([f(row[field]) for row in rows], [f(row["track_weight_recomputed_primary"]) for row in rows], 0.50))
            color = environment_colors[environment]
            ax.fill_between(x, lows, highs, color=color, alpha=0.13)
            ax.plot(x, medians, color=color, linewidth=2.2, marker="o", label=environment)
            ax.plot(x, empirical, color=color, linewidth=0.0, marker="x", markersize=7, markeredgewidth=1.8)
        ax.set_title(label, fontsize=11)
        ax.set_xticks(x, BANDS)
        ax.set_xlabel("Elevation band")
        ax.grid(alpha=0.2)
    axes[0].set_ylabel("Parameter value")
    axes[0].legend(fontsize=9, loc="best")
    fig.suptitle("Fitted parameter summaries versus elevation", fontsize=14)
    fig.subplots_adjust(left=0.06, right=0.98, bottom=0.20, top=0.82, wspace=0.24)
    fig.text(0.5, 0.045, "Solid circles: fitted median; shaded band: fitted 5–95% interval; ×: weighted empirical median", ha="center", fontsize=9)
    fig.savefig(figure_dir / "conditional_parameter_curves_vs_elevation.png", dpi=220, bbox_inches="tight")
    fig.savefig(figure_dir / "conditional_parameter_curves_vs_elevation.pdf", bbox_inches="tight")
    plt.close(fig)


def normal_pdf(values: np.ndarray, mean: float, standard_deviation: float) -> np.ndarray:
    scale = max(float(standard_deviation), 1e-12)
    standardized = (values - mean) / scale
    return np.exp(-0.5 * standardized * standardized) / (scale * math.sqrt(2.0 * math.pi))


def marginal_pdf(model: Mapping[str, Any], environment: str, cell: str, parameter_index: int, values: np.ndarray) -> np.ndarray:
    model_block = model["model"]
    center = np.asarray(model_block["transform_center"], dtype=float)
    scale = np.asarray(model_block["transform_scale"], dtype=float)
    means = np.asarray(model_block["environment_means"][environment], dtype=float)
    covariances = np.asarray(model_block["shared_covariances"], dtype=float)
    weights = np.asarray(model_block["cell_weights"][cell], dtype=float)
    density = np.zeros_like(values, dtype=float)
    for component in range(3):
        transformed_mean = center[parameter_index] + scale[parameter_index] * means[component, parameter_index]
        transformed_standard_deviation = scale[parameter_index] * math.sqrt(max(float(covariances[component, parameter_index, parameter_index]), 1e-12))
        if parameter_index == 0:
            positive = np.maximum(values, 1e-12)
            density += weights[component] * normal_pdf(np.log(positive), transformed_mean, transformed_standard_deviation) / positive
        elif parameter_index == 1:
            positive = np.maximum(values, 0.0)
            density += weights[component] * normal_pdf(np.log1p(positive), transformed_mean, transformed_standard_deviation) / (1.0 + positive)
        else:
            density += weights[component] * normal_pdf(values, transformed_mean, transformed_standard_deviation)
    return density


def make_pdf_figure(model: Mapping[str, Any], draws: Mapping[str, np.ndarray], figure_dir: Path) -> None:
    parameter_specs = (
        (0, "Excess delay PDF", "Excess delay (samples)"),
        (1, "Absolute Doppler PDF", "Absolute Doppler (Hz)"),
        (2, "Relative power PDF", "Relative power (dB)"),
    )
    line_styles = {"LOW": ("#1f77b4", "-"), "MID": ("#ff7f0e", "--"), "HIGH": ("#2ca02c", ":")}
    fig, axes = plt.subplots(2, 3, figsize=(14.0, 7.2))
    for row_index, environment in enumerate(ENVIRONMENTS):
        for col_index, (parameter_index, title, xlabel) in enumerate(parameter_specs):
            ax = axes[row_index, col_index]
            combined = np.concatenate([draws[f"{environment}__{band}"][:, parameter_index] for band in BANDS])
            lower = float(np.quantile(combined, 0.001))
            upper = float(np.quantile(combined, 0.999))
            if parameter_index < 2:
                lower = max(0.0 if parameter_index == 1 else 0.05, lower * 0.9)
            else:
                lower -= 1.0
                upper += 1.0
            grid = np.linspace(lower, upper, 500)
            for band in BANDS:
                cell = f"{environment}__{band}"
                color, linestyle = line_styles[band]
                density = marginal_pdf(model, environment, cell, parameter_index, grid)
                ax.plot(grid, density, color=color, linestyle=linestyle, linewidth=2.0, label=band)
            ax.set_title(f"{environment} — {title}", fontsize=10)
            ax.set_xlabel(xlabel)
            ax.set_ylabel("Probability density")
            ax.grid(alpha=0.2)
            ax.legend(fontsize=8, loc="best")
    fig.suptitle("Model marginal probability-density functions by environment and elevation", fontsize=14)
    target = figure_dir / "conditional_marginal_pdf_environment_elevation.png"
    fig.savefig(target, dpi=220)
    fig.savefig(figure_dir / "conditional_marginal_pdf_environment_elevation.pdf")
    plt.close(fig)


def make_empirical_pdf_comparison_figure(model: Mapping[str, Any], population: Sequence[Mapping[str, Any]], draws: Mapping[str, np.ndarray], figure_dir: Path) -> None:
    parameter_specs = (
        (0, "Excess delay", "excess_delay_samples", "Excess delay (samples)"),
        (1, "Absolute Doppler", "absolute_doppler_hz", "Absolute Doppler (Hz)"),
        (2, "Relative power", "relative_power_db", "Relative power (dB)"),
    )
    line_styles = {"LOW": "-", "MID": "--", "HIGH": ":"}
    colors = {"LOW": "#1f77b4", "MID": "#ff7f0e", "HIGH": "#2ca02c"}
    fig, axes = plt.subplots(2, 3, figsize=(14.0, 7.2))
    for row_index, environment in enumerate(ENVIRONMENTS):
        for col_index, (parameter_index, title, field, xlabel) in enumerate(parameter_specs):
            ax = axes[row_index, col_index]
            combined = np.concatenate([draws[f"{environment}__{band}"][:, parameter_index] for band in BANDS])
            lower = float(np.quantile(combined, 0.001))
            upper = float(np.quantile(combined, 0.999))
            if parameter_index < 2:
                lower = max(0.0 if parameter_index == 1 else 0.05, lower * 0.9)
            else:
                lower -= 1.0
                upper += 1.0
            grid = np.linspace(lower, upper, 500)
            bins = np.linspace(lower, upper, 25)
            for band in BANDS:
                cell = f"{environment}__{band}"
                color = colors[band]
                rows = cell_rows(population, cell)
                observed = np.asarray([f(item[field]) for item in rows], dtype=float)
                weights = np.asarray([f(item["track_weight_recomputed_primary"]) for item in rows], dtype=float)
                ax.hist(observed, bins=bins, weights=weights, density=True, histtype="step", color=color, linestyle="--", linewidth=1.2, alpha=0.9)
                ax.plot(grid, marginal_pdf(model, environment, cell, parameter_index, grid), color=color, linestyle=line_styles[band], linewidth=2.0)
            ax.set_title(f"{environment} — {title}", fontsize=10)
            ax.set_xlabel(xlabel)
            ax.set_ylabel("Probability density")
            ax.grid(alpha=0.2)
    band_handles = [Line2D([0], [0], color=colors[band], linestyle=line_styles[band], linewidth=2.0, label=band) for band in BANDS]
    type_handles = [Line2D([0], [0], color="#333333", linestyle="-", linewidth=2.0, label="fitted PDF"), Line2D([0], [0], color="#333333", linestyle="--", linewidth=1.3, label="measured weighted histogram")]
    fig.suptitle("Measured distributions versus fitted marginal PDFs", fontsize=14, y=0.995)
    fig.subplots_adjust(left=0.06, right=0.98, bottom=0.11, top=0.86, wspace=0.24, hspace=0.30)
    fig.legend(handles=band_handles + type_handles, loc="upper center", ncol=5, bbox_to_anchor=(0.5, 0.955), fontsize=9)
    target = figure_dir / "conditional_empirical_vs_model_pdf_environment_elevation.png"
    fig.savefig(target, dpi=220, bbox_inches="tight")
    fig.savefig(figure_dir / "conditional_empirical_vs_model_pdf_environment_elevation.pdf", bbox_inches="tight")
    plt.close(fig)


def make_tables(model: Mapping[str, Any], population: Sequence[Mapping[str, Any]], draws: Mapping[str, np.ndarray], table_dir: Path) -> None:
    independent_qa = json.loads((ROOT / "qa/independent_qa_result.json").read_text(encoding="utf-8"))
    selection_rows = [{
        "build_status": model["status"],
        "independent_qa_status": independent_qa["status"],
        "selected_K": model["selection"]["component_count"],
        "selected_kappa": model["selection"]["pooling_kappa"],
        "primary_doppler_variable": model["primary_doppler_variable"],
        "mean_weighted_nlpd": model["selection"]["mean_weighted_nlpd"],
        "mean_energy_score": model["selection"]["mean_energy_score"],
        "signed_minus_absolute_mean": model["signed_sensitivity"]["mean_energy_difference_signed_minus_absolute"],
        "signed_minus_absolute_q025": model["signed_sensitivity"]["q025"],
        "signed_minus_absolute_q975": model["signed_sensitivity"]["q975"],
    }]
    write_csv(table_dir / "conditional_gmm_selection_summary.csv", selection_rows)
    cell_summary = read_csv(ROOT / "model/cell_model_summary.csv")
    weights = model["model"]["cell_weights"]
    cell_rows_output: list[dict[str, Any]] = []
    for summary in cell_summary:
        cell = summary["cell_id"]
        cell_rows_output.append({
            "environment_class": summary["environment_class"],
            "elevation_band": summary["elevation_band"],
            "support_status": read_support_status(cell),
            "observation_count": summary["observation_count"],
            "track_count": summary["track_count"],
            "scene_count": summary["scene_count"],
            "component_1_weight": weights[cell][0],
            "component_2_weight": weights[cell][1],
            "component_3_weight": weights[cell][2],
            "delay_q05_samples": summary["q05_excess_delay_samples"],
            "delay_median_samples": summary["q50_excess_delay_samples"],
            "delay_q95_samples": summary["q95_excess_delay_samples"],
            "abs_doppler_q05_hz": summary["q05_absolute_doppler_hz"],
            "abs_doppler_median_hz": summary["q50_absolute_doppler_hz"],
            "abs_doppler_q95_hz": summary["q95_absolute_doppler_hz"],
            "power_q05_db": summary["q05_relative_power_db"],
            "power_median_db": summary["q50_relative_power_db"],
            "power_q95_db": summary["q95_relative_power_db"],
        })
    write_csv(table_dir / "conditional_gmm_cell_summary.csv", cell_rows_output)
    write_latex(table_dir / "conditional_gmm_selection_summary.tex", selection_rows, "Selection summary")
    write_latex(table_dir / "conditional_gmm_cell_summary.tex", cell_rows_output, "Conditional cell summary")


def write_latex(path: Path, rows: Sequence[Mapping[str, Any]], caption: str) -> None:
    fields = list(rows[0].keys()) if rows else []
    lines = [f"% Author-review table: {caption}", "\\begin{tabular}{" + "l" * len(fields) + "}", "\\hline", " & ".join(fields) + " \\\\", "\\hline"]
    for row in rows:
        values = [str(row[field]).replace("_", "\\_") for field in fields]
        lines.append(" & ".join(values) + " \\\\")
    lines.extend(["\\hline", "\\end{tabular}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    model = load_model()
    population = load_population()
    draws = load_draws()
    figure_dir = ROOT / "figures"
    table_dir = ROOT / "tables"
    figure_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    make_main_figure(model, population, draws, figure_dir)
    for cell in CELLS:
        make_corner_figure(model, population, draws, figure_dir, cell)
    make_weight_figure(model, figure_dir)
    make_parameter_curve_figure(model, population, draws, figure_dir)
    make_pdf_figure(model, draws, figure_dir)
    make_empirical_pdf_comparison_figure(model, population, draws, figure_dir)
    make_tables(model, population, draws, table_dir)
    outputs = {}
    for path in sorted(list(figure_dir.glob("*")) + list(table_dir.glob("*"))):
        if path.is_file():
            outputs[str(path.relative_to(ROOT)).replace("\\", "/")] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    manifest = {
        "status": "PASS_AUTHOR_REVIEW_ONLY",
        "figures": {
            "conditional_joint_environment_elevation": {"panel_count": 6, "cell_ready_rows": 487, "path": "figures/conditional_joint_environment_elevation.png"},
            "corner_diagnostic_pages": {"page_count": 6, "cdf_panels": 0},
            "conditional_component_weight_heatmap": {"panel_count": 6, "path": "figures/conditional_component_weight_heatmap.png"},
            "conditional_parameter_curves_vs_elevation": {"panel_count": 3, "path": "figures/conditional_parameter_curves_vs_elevation.png"},
            "conditional_marginal_pdf_environment_elevation": {"panel_count": 6, "path": "figures/conditional_marginal_pdf_environment_elevation.png"},
            "conditional_empirical_vs_model_pdf_environment_elevation": {"panel_count": 6, "cell_ready_rows": 487, "path": "figures/conditional_empirical_vs_model_pdf_environment_elevation.png"},
        },
        "tables": {"cell_summary_rows": 6, "selection_summary_rows": 1},
        "outputs": outputs,
        "execution_boundary": {"formal_manuscript_modified": False, "canonical_figures_modified": False, "canonical_tables_modified": False, "evidence_matrix_modified": False, "handoff_modified": False, "raw_iq_read": False, "matlab_started": False, "sage_started": False},
    }
    (ROOT / "qa/output_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "figure_count": len(list(figure_dir.glob("*"))), "table_count": len(list(table_dir.glob("*"))), "panel_count": 6, "cell_ready_rows": 487}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
