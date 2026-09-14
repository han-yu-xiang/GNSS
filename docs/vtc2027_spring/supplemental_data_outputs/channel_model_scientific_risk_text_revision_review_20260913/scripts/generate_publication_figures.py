from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[5]
OUTPUT_ROOT = Path(__file__).resolve().parents[1]
FIGURE_ROOT = OUTPUT_ROOT / "figures"

SOURCE_CSV = (
    PROJECT_ROOT
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/"
    "population/gmm_feature_population.csv"
)
DELAY_MODEL_JSON = (
    PROJECT_ROOT
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "environment_level_basic_channel_model_review_20260902/model/"
    "selected_excess_delay_shifted_lognormal_preview.json"
)
POWER_MODEL_JSON = (
    PROJECT_ROOT
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "signed_doppler_power_relationship_review_20260903/model/"
    "signed_doppler_power_distribution_models.json"
)
EMPIRICAL_DOPPLER_MODEL_JSON = (
    PROJECT_ROOT
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "channel_model_scientific_risk_experiments_review_20260913/review/"
    "model/signed_doppler_empirical_model.json"
)
PIECEWISE_TABLE_CSV = (
    PROJECT_ROOT
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "power_delay_continuous_piecewise_review_20260905/tables/"
    "power_delay_continuous_piecewise_parameters.csv"
)

ENVIRONMENTS = ("Urban", "Mountain/Valley")
COLORS = {"Urban": "#2B78A6", "Mountain/Valley": "#D9772A"}
WEIGHT_FIELD = "track_weight_recomputed_primary"
NS_PER_SAMPLE = 1e9 / 10.23e6
CUTPOINT_SAMPLES = 1.95
CUTPOINT_NS = CUTPOINT_SAMPLES * NS_PER_SAMPLE

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 7.4,
        "axes.titlesize": 8.2,
        "axes.labelsize": 7.6,
        "legend.fontsize": 6.8,
        "xtick.labelsize": 6.8,
        "ytick.labelsize": 6.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)


def load_population() -> pd.DataFrame:
    frame = pd.read_csv(SOURCE_CSV)
    included = frame["primary_population_included"].astype(str).str.lower().isin({"1", "true"})
    frame = frame.loc[included].copy()
    numeric = ["excess_delay_samples", "doppler_offset_hz", "relative_power_db", WEIGHT_FIELD]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    if len(frame) != 518 or not np.isfinite(frame[numeric].to_numpy(float)).all():
        raise ValueError("Unexpected or non-finite modeling population")
    frame["excess_delay_ns"] = frame["excess_delay_samples"] * NS_PER_SAMPLE
    return frame


def weighted_histogram(values: np.ndarray, weights: np.ndarray, bins: np.ndarray):
    mass, edges = np.histogram(values, bins=bins, weights=weights)
    return edges, mass / (np.sum(weights) * np.diff(edges))


def weighted_ecdf(values: np.ndarray, weights: np.ndarray):
    order = np.argsort(values, kind="mergesort")
    x = values[order]
    y = np.cumsum(weights[order]) / np.sum(weights)
    return x, y


def delay_pdf_cdf(model: dict, grid_ns: np.ndarray):
    p = model["params"]
    grid_samples = grid_ns / NS_PER_SAMPLE
    shape = float(p["std_log"])
    scale = float(np.exp(float(p["mean_log"])))
    loc = float(p.get("loc", 0.0))
    shifted = grid_samples - loc
    valid = shifted > 0
    pdf = np.zeros_like(grid_samples, dtype=float)
    cdf = np.zeros_like(grid_samples, dtype=float)
    log_ratio = np.log(shifted[valid] / scale)
    pdf[valid] = (
        np.exp(-0.5 * (log_ratio / shape) ** 2)
        / (shifted[valid] * shape * math.sqrt(2.0 * math.pi))
        / NS_PER_SAMPLE
    )
    cdf[valid] = 0.5 * (
        1.0
        + np.fromiter(
            (math.erf(value / (shape * math.sqrt(2.0))) for value in log_ratio),
            dtype=float,
            count=len(log_ratio),
        )
    )
    return pdf, cdf


def gmm_pdf_cdf(params: dict, grid: np.ndarray):
    pdf = np.zeros_like(grid, dtype=float)
    cdf = np.zeros_like(grid, dtype=float)
    for mean, std, weight in zip(params["means"], params["stds"], params["proportions"]):
        normalized = (grid - mean) / std
        pdf += weight * np.exp(-0.5 * normalized**2) / (std * math.sqrt(2.0 * math.pi))
        cdf += weight * 0.5 * (
            1.0
            + np.fromiter(
                (math.erf(value / math.sqrt(2.0)) for value in normalized),
                dtype=float,
                count=len(normalized),
            )
        )
    return pdf, cdf


def panel_label(axis, label: str):
    axis.text(-0.12, 1.07, label, transform=axis.transAxes, fontsize=8.2, fontweight="bold")


def save_figure(figure: plt.Figure, stem: str):
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURE_ROOT / f"{stem}.pdf", bbox_inches="tight", pad_inches=0.02)
    figure.savefig(FIGURE_ROOT / f"{stem}.png", bbox_inches="tight", pad_inches=0.02, dpi=300)
    plt.close(figure)


def distribution_figure(groups, models, field, bins, grid, xlabel, density_label, stem, delay=False):
    figure, axes = plt.subplots(2, 2, figsize=(7.05, 2.55), sharex="col")
    for column, environment in enumerate(ENVIRONMENTS):
        group = groups[environment]
        values = group[field].to_numpy(float)
        weights = group[WEIGHT_FIELD].to_numpy(float)
        top = axes[0, column]
        bottom = axes[1, column]

        edges, density = weighted_histogram(values, weights, bins)
        top.bar(
            edges[:-1], density, width=np.diff(edges), align="edge",
            color=COLORS[environment], alpha=0.30,
            edgecolor=COLORS[environment], linewidth=0.5,
        )
        if delay:
            pdf, cdf = delay_pdf_cdf(models[environment], grid)
        else:
            pdf, cdf = gmm_pdf_cdf(models[environment], grid)
        top.plot(grid, pdf, color="#111111", linewidth=1.45)
        x_ecdf, y_ecdf = weighted_ecdf(values, weights)
        bottom.step(x_ecdf, y_ecdf, where="post", color=COLORS[environment], linewidth=1.25)
        bottom.plot(grid, cdf, color="#111111", linewidth=1.35, linestyle="--")

        top.set_title(f"{environment} ($n={len(group)}$)")
        bottom.set_xlabel(xlabel)
        top.grid(axis="y", color="#d7d7d7", linewidth=0.4, alpha=0.75)
        bottom.grid(color="#d7d7d7", linewidth=0.4, alpha=0.75)
        bottom.set_ylim(0, 1.02)
        top.set_axisbelow(True)
        bottom.set_axisbelow(True)

    axes[0, 0].set_ylabel(density_label)
    axes[1, 0].set_ylabel("Cumulative probability")
    for axis, label in zip(axes.flat, ("(a)", "(b)", "(c)", "(d)")):
        panel_label(axis, label)
    hist = Patch(facecolor="#777777", edgecolor="#777777", alpha=0.30, label="Measured density")
    fit_pdf = Line2D([0], [0], color="#111111", lw=1.45, label="Fitted density")
    ecdf = Line2D([0], [0], color="#666666", lw=1.25, label="Measured cumulative")
    fit_cdf = Line2D([0], [0], color="#111111", lw=1.35, ls="--", label="Fitted cumulative")
    figure.legend(handles=[hist, fit_pdf, ecdf, fit_cdf], loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.015))
    figure.tight_layout(rect=(0, 0, 1, 0.91), h_pad=0.30, w_pad=0.9)
    save_figure(figure, stem)


def combined_distribution_figure(groups, delay_models, power_models):
    delay_spec = {
        "field": "excess_delay_ns",
        "bins": np.arange(0.9, 4.11, 0.2) * NS_PER_SAMPLE,
        "grid": np.linspace(0.9, 4.1, 700) * NS_PER_SAMPLE,
        "xlabel": "Excess delay (ns)",
        "density_label": r"Weighted density (ns$^{-1}$)",
        "title": "Excess delay",
        "models": delay_models,
        "delay": True,
    }
    power_spec = {
        "field": "relative_power_db",
        "bins": np.arange(-22.5, 0.51, 1.0),
        "grid": np.linspace(-22.5, 0.5, 900),
        "xlabel": "Relative path power (dB)",
        "density_label": r"Weighted density (dB$^{-1}$)",
        "title": "Relative path power",
        "models": {
            environment: power_models["relative_power"][environment]["selected"]["params"]
            for environment in ENVIRONMENTS
        },
        "delay": False,
    }

    figure, axes = plt.subplots(3, 2, figsize=(7.05, 5.70))
    panel_names = ("(a)", "(b)", "(c)", "(d)", "(e)", "(f)")

    for row, specification in ((0, delay_spec), (2, power_spec)):
        density_axis = axes[row, 0]
        cumulative_axis = axes[row, 1]
        grid = specification["grid"]
        for environment in ENVIRONMENTS:
            group = groups[environment]
            values = group[specification["field"]].to_numpy(float)
            weights = group[WEIGHT_FIELD].to_numpy(float)
            color = COLORS[environment]
            edges, density = weighted_histogram(values, weights, specification["bins"])
            density_axis.stairs(
                density,
                edges,
                fill=True,
                color=color,
                alpha=0.12,
                linewidth=0.7,
            )
            density_axis.stairs(density, edges, color=color, linewidth=0.9)
            if specification["delay"]:
                pdf, cdf = delay_pdf_cdf(specification["models"][environment], grid)
            else:
                pdf, cdf = gmm_pdf_cdf(specification["models"][environment], grid)
            density_axis.plot(grid, pdf, color=color, linewidth=1.45, linestyle="--")
            x_ecdf, y_ecdf = weighted_ecdf(values, weights)
            cumulative_axis.step(x_ecdf, y_ecdf, where="post", color=color, linewidth=1.05)
            cumulative_axis.plot(grid, cdf, color=color, linewidth=1.35, linestyle="--")

        density_axis.set_title(f'{specification["title"]}: density')
        cumulative_axis.set_title(f'{specification["title"]}: cumulative')
        density_axis.set_xlabel(specification["xlabel"])
        cumulative_axis.set_xlabel(specification["xlabel"])
        density_axis.set_ylabel(specification["density_label"])
        cumulative_axis.set_ylabel("Cumulative probability")
        density_axis.set_xlim(float(grid[0]), float(grid[-1]))
        cumulative_axis.set_xlim(float(grid[0]), float(grid[-1]))
        cumulative_axis.set_ylim(0, 1.02)
        density_axis.grid(axis="y", color="#d7d7d7", linewidth=0.4, alpha=0.75)
        cumulative_axis.grid(color="#d7d7d7", linewidth=0.4, alpha=0.75)
        density_axis.set_axisbelow(True)
        cumulative_axis.set_axisbelow(True)

    doppler_model = json.loads(EMPIRICAL_DOPPLER_MODEL_JSON.read_text(encoding="utf-8"))
    quantiles = {
        item["environment"]: item
        for item in doppler_model["quantiles"]
    }
    for column, environment in enumerate(ENVIRONMENTS):
        axis = axes[1, column]
        group = groups[environment]
        values = group["doppler_offset_hz"].to_numpy(float)
        weights = group[WEIGHT_FIELD].to_numpy(float)
        color = COLORS[environment]
        x_ecdf, y_ecdf = weighted_ecdf(values, weights)
        axis.step(x_ecdf, y_ecdf, where="post", color=color, linewidth=1.35)
        summary = quantiles[environment]
        for quantile, linestyle in ((10, ":"), (50, "--"), (90, ":")):
            value = float(summary[f"P{quantile}_hz"])
            axis.axvline(value, color="#444444", linewidth=0.75, linestyle=linestyle)
            axis.text(
                value,
                0.06 if quantile != 50 else 0.18,
                f"P{quantile}",
                rotation=90,
                ha="right",
                va="bottom",
                fontsize=6.4,
                color="#333333",
            )
        axis.set_title(f"Signed relative Doppler: {environment}")
        axis.set_xlabel("Signed relative Doppler (Hz)")
        axis.set_ylabel("Cumulative probability")
        axis.set_xlim(-130, 115)
        axis.set_ylim(0, 1.02)
        axis.grid(color="#d7d7d7", linewidth=0.4, alpha=0.75)
        axis.set_axisbelow(True)

    for axis, label in zip(axes.flat, panel_names):
        panel_label(axis, label)

    handles = [
        Line2D([0], [0], color=COLORS["Urban"], lw=1.25, label="Urban measured"),
        Line2D([0], [0], color=COLORS["Urban"], lw=1.45, ls="--", label="Urban fitted"),
        Line2D([0], [0], color=COLORS["Mountain/Valley"], lw=1.25, label="Mountain/Valley measured"),
        Line2D([0], [0], color=COLORS["Mountain/Valley"], lw=1.45, ls="--", label="Mountain/Valley fitted"),
        Line2D([0], [0], color="#444444", lw=0.8, ls="--", label="Doppler weighted quantiles"),
    ]
    figure.legend(handles=handles, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.005))
    figure.tight_layout(rect=(0, 0, 1, 0.955), h_pad=0.72, w_pad=1.05)
    save_figure(figure, "figure2_parameter_distributions")


def power_delay_figure(groups, summary, stem="figure3_power_delay"):
    figure, axes = plt.subplots(1, 2, figsize=(7.16, 2.30), sharex=True, sharey=True)
    for axis, environment, label in zip(axes, ENVIRONMENTS, ("(a)", "(b)")):
        group = groups[environment]
        row = summary.loc[summary["environment"] == environment].iloc[0]
        low = group.loc[group["excess_delay_samples"] < CUTPOINT_SAMPLES]
        high = group.loc[group["excess_delay_samples"] >= CUTPOINT_SAMPLES]
        axis.scatter(low["excess_delay_ns"], low["relative_power_db"], s=6.5, color="#2B78A6", alpha=0.28, edgecolors="none")
        axis.scatter(high["excess_delay_ns"], high["relative_power_db"], s=6.5, color="#D9772A", alpha=0.28, edgecolors="none")
        x_low = np.linspace(float(low["excess_delay_ns"].min()), CUTPOINT_NS, 100)
        x_high = np.linspace(CUTPOINT_NS, float(high["excess_delay_ns"].max()), 100)
        b_low = float(row["left_slope_db_per_sample"]) * 100.0 / NS_PER_SAMPLE
        b_high = float(row["right_slope_db_per_sample"]) * 100.0 / NS_PER_SAMPLE
        p_break = float(row["connection_power_db"])
        axis.plot(x_low, p_break + b_low * (x_low - CUTPOINT_NS) / 100.0, color="#2B78A6", linewidth=1.8)
        axis.plot(x_high, p_break + b_high * (x_high - CUTPOINT_NS) / 100.0, color="#D9772A", linewidth=1.8)
        axis.axvline(CUTPOINT_NS, color="#444444", linestyle="--", linewidth=0.75)
        axis.scatter([CUTPOINT_NS], [p_break], color="#222222", s=14, zorder=4)
        axis.set_title(f"{environment} ($n={len(group)}$)")
        axis.set_xlim(85, 405)
        axis.set_ylim(-23, 1)
        axis.grid(axis="y", color="#d7d7d7", linewidth=0.4, alpha=0.75)
        axis.set_axisbelow(True)
        panel_label(axis, label)
    axes[0].set_ylabel("Relative path power (dB)")
    axes[0].set_xlabel("Excess delay (ns)")
    axes[1].set_xlabel("Excess delay (ns)")
    handles = [
        Line2D([0], [0], color="#2B78A6", lw=1.8, label="Low-delay fit"),
        Line2D([0], [0], color="#D9772A", lw=1.8, label="High-delay fit"),
        Line2D([0], [0], color="#444444", lw=0.75, ls="--", marker="o", markersize=3, label="Connected breakpoint"),
    ]
    figure.legend(handles=handles, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.02))
    figure.tight_layout(rect=(0, 0, 1, 0.84), w_pad=1.05)
    save_figure(figure, stem)


def main():
    population = load_population()
    groups = {env: population.loc[population["environment_class"] == env].copy() for env in ENVIRONMENTS}
    delay_models = json.loads(DELAY_MODEL_JSON.read_text(encoding="utf-8"))["models"]
    power_models = json.loads(POWER_MODEL_JSON.read_text(encoding="utf-8"))["variables"]
    piecewise = pd.read_csv(PIECEWISE_TABLE_CSV)

    combined_distribution_figure(groups, delay_models, power_models)
    power_delay_figure(groups, piecewise)

    audit = {
        "source_population": str(SOURCE_CSV),
        "selection": "primary_population_included == true",
        "weight": "1 / retained observations in the same satellite track",
        "observations": int(len(population)),
        "tracks": int(population["track_id"].nunique()),
        "scenes": int(population["scene_id"].nunique()),
        "environment_counts": {env: int(len(groups[env])) for env in ENVIRONMENTS},
        "outputs": [
            "figure2_parameter_distributions.pdf",
            "figure3_power_delay.pdf",
        ],
        "legacy_individual_figures_retained": [
            "figure2_excess_delay.pdf",
            "figure3_signed_doppler.pdf",
            "figure4_relative_power.pdf",
            "figure5_power_delay.pdf",
        ],
        "combined_figure_layout": "3 rows x 2 columns; delay and power use measured/fitted density and CDF panels, while Doppler uses one empirical CDF panel per environment with P10/P50/P90 markers",
        "doppler_model": "track-balanced empirical CDF",
        "models_refit": False,
        "source_data_modified": False,
    }
    (OUTPUT_ROOT / "qa" / "figure_generation.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
