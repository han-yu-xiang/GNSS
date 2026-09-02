#!/usr/bin/env python3
"""Generate a simple measured-versus-model joint delay-power preview."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

from generate_conditional_gmm_figures import (
    ENVIRONMENTS,
    f,
    load_model,
    load_population,
)


def density_threshold(density: np.ndarray, enclosed_mass: float) -> float:
    flattened = np.asarray(density, dtype=float).ravel()
    ordered = np.sort(flattened)[::-1]
    cumulative = np.cumsum(ordered)
    cumulative /= cumulative[-1]
    index = min(int(np.searchsorted(cumulative, enclosed_mass)), ordered.size - 1)
    return float(ordered[index])


def environment_density_2d(
    model: dict,
    environment: str,
    log_delay: np.ndarray,
    power: np.ndarray,
) -> np.ndarray:
    model_block = model["model"]
    center = np.asarray(model_block["transform_center"], dtype=float)
    scale = np.asarray(model_block["transform_scale"], dtype=float)
    means = np.asarray(model_block["environment_means"][environment], dtype=float)
    covariances = np.asarray(model_block["shared_covariances"], dtype=float)
    weights = np.asarray(model_block["environment_weights"][environment], dtype=float)
    z_delay = (log_delay - center[0]) / scale[0]
    z_power = (power - center[2]) / scale[2]
    points = np.column_stack([z_delay.ravel(), z_power.ravel()])
    density = np.zeros(points.shape[0], dtype=float)
    for component in range(3):
        mean = means[component][[0, 2]]
        covariance = covariances[component][np.ix_([0, 2], [0, 2])]
        covariance = 0.5 * (covariance + covariance.T)
        inverse = np.linalg.inv(covariance)
        determinant = max(float(np.linalg.det(covariance)), 1e-12)
        delta = points - mean[None, :]
        density += (
            weights[component]
            * np.exp(-0.5 * np.sum(delta * (delta @ inverse), axis=1))
            / (2.0 * np.pi * math.sqrt(determinant))
        )
    return density.reshape(log_delay.shape)


def make_preview(output_dir: Path) -> tuple[Path, Path]:
    model = load_model()
    population = load_population()
    delays = np.asarray([f(row["excess_delay_samples"]) for row in population])
    powers = np.asarray([f(row["relative_power_db"]) for row in population])

    delay_min = max(0.8, float(np.quantile(delays, 0.005)) * 0.95)
    delay_max = float(np.quantile(delays, 0.995)) * 1.08
    power_min = float(np.quantile(powers, 0.005)) - 0.8
    power_max = float(np.quantile(powers, 0.995)) + 0.8
    delay_grid = np.geomspace(delay_min, delay_max, 180)
    power_grid = np.linspace(power_min, power_max, 180)
    delay_mesh, power_mesh = np.meshgrid(delay_grid, power_grid)

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(11.2, 4.5),
        sharex=True,
        sharey=True,
    )
    for column_index, environment in enumerate(ENVIRONMENTS):
        ax = axes[column_index]
        rows = [row for row in population if row["environment_class"] == environment]
        ax.scatter(
            [f(row["excess_delay_samples"]) for row in rows],
            [f(row["relative_power_db"]) for row in rows],
            s=15,
            color="#2878b5",
            alpha=0.38,
            edgecolors="none",
            rasterized=True,
        )
        density = environment_density_2d(
            model,
            environment,
            np.log(delay_mesh),
            power_mesh,
        )
        outer = density_threshold(density, 0.90)
        inner = density_threshold(density, 0.50)
        ax.contour(
            delay_mesh,
            power_mesh,
            density,
            levels=[outer, inner],
            colors=["#d95f02", "#d95f02"],
            linestyles=["--", "-"],
            linewidths=[1.2, 2.0],
        )
        ax.set_title(environment, fontsize=11)
        ax.set_xlabel("Excess delay (samples)")
        ax.grid(alpha=0.16)
        ax.set_xlim(delay_min, delay_max)
        ax.set_ylim(power_min, power_max)
        if column_index == 0:
            ax.set_ylabel("Relative power (dB)")

    legend = [
        Line2D([0], [0], marker="o", linestyle="none", color="#2878b5", alpha=0.65, markersize=5, label="Measured observations"),
        Line2D([0], [0], color="#d95f02", linewidth=2.0, label="Model central 50%"),
        Line2D([0], [0], color="#d95f02", linewidth=1.2, linestyle="--", label="Model central 90%"),
    ]
    fig.suptitle("Measured observations and fitted joint delay-power density", fontsize=13, y=0.985)
    fig.legend(handles=legend, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.94), fontsize=9)
    fig.subplots_adjust(left=0.075, right=0.99, bottom=0.13, top=0.78, wspace=0.08)

    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / "simple_joint_delay_power_preview.png"
    pdf_path = output_dir / "simple_joint_delay_power_preview.pdf"
    fig.savefig(png_path, dpi=240, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return png_path, pdf_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    png_path, pdf_path = make_preview(arguments.output_dir)
    print(json.dumps({
        "panel_count": 2,
        "observation_count": 518,
        "environments": list(ENVIRONMENTS),
        "png": str(png_path),
        "pdf": str(pdf_path),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
