from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.colors import Normalize


OUTPUT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = OUTPUT_ROOT / "model"
FIGURE_DIR = OUTPUT_ROOT / "figures"
TABLE_DIR = OUTPUT_ROOT / "tables"
SOURCE_CSV = (
    Path(r"E:\GNSS_Multipath_Project")
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/"
    "population/gmm_feature_population.csv"
)
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from derive_retained_path_delay_dispersion import weighted_ecdf  # noqa: E402
from fit_delay_doppler_2d import predict_log_density  # noqa: E402
from fit_relative_power_models import evaluate_power_pdf  # noqa: E402


CELL_ORDER = tuple(
    f"{environment}/{band}"
    for environment in ("Urban", "Mountain/Valley")
    for band in ("LOW", "MID", "HIGH")
)
BAND_COLORS = {"LOW": "#377eb8", "MID": "#e41a1c", "HIGH": "#4daf4a"}
BAND_MARKERS = {"LOW": "o", "MID": "^", "HIGH": "s"}
ENVIRONMENT_COLORS = {"Urban": "#1f77b4", "Mountain/Valley": "#ff7f0e"}


def _bool_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def load_population() -> pd.DataFrame:
    frame = pd.read_csv(SOURCE_CSV)
    mask = _bool_mask(frame["primary_population_included"]) & _bool_mask(frame["elevation_ready"]) & _bool_mask(frame["cell_ready"])
    frame = frame.loc[mask].copy()
    frame["cell_id"] = frame["environment_class"].astype(str) + "/" + frame["elevation_band"].astype(str)
    numeric_fields = ["excess_delay_samples", "absolute_doppler_hz", "doppler_offset_hz", "relative_power_db", "track_weight_recomputed_primary"]
    frame[numeric_fields] = frame[numeric_fields].apply(pd.to_numeric, errors="coerce")
    if frame[numeric_fields].isna().any().any():
        raise ValueError("non-finite source value while generating figures")
    return frame


def load_json(name: str) -> dict:
    return json.loads((MODEL_DIR / name).read_text(encoding="utf-8"))


def _cell_title(cell_id: str) -> str:
    environment, band = cell_id.rsplit("/", 1)
    return f"{environment} | {band}"


def _draw_density_contours(ax: plt.Axes, model_entry: dict | None, x: np.ndarray, y: np.ndarray) -> None:
    if not model_entry:
        return
    model = model_entry["model"]
    x_min = max(0.0, float(np.min(x)) - 0.45)
    x_max = float(np.max(x)) + 0.45
    y_min = max(0.0, float(np.min(y)) - 12.0)
    y_max = float(np.max(y)) + 12.0
    grid_x = np.linspace(x_min, x_max, 110)
    grid_y = np.linspace(y_min, y_max, 110)
    mesh_x, mesh_y = np.meshgrid(grid_x, grid_y)
    coordinates = np.column_stack([mesh_x.ravel(), mesh_y.ravel()])
    density = np.exp(predict_log_density(model, coordinates)).reshape(mesh_x.shape)
    levels = np.unique(np.quantile(density.ravel(), [0.70, 0.85, 0.95]))
    levels = levels[(levels > float(np.min(density))) & (levels < float(np.max(density)))]
    if len(levels):
        ax.contour(mesh_x, mesh_y, density, levels=levels, colors="#222222", linewidths=0.9, alpha=0.85)


def plot_delay_doppler(frame: pd.DataFrame, selected: dict) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(10.6, 7.8), sharex=False, sharey=False)
    for index, cell_id in enumerate(CELL_ORDER):
        ax = axes.flat[index]
        cell = frame[frame["cell_id"] == cell_id]
        band = cell_id.rsplit("/", 1)[1]
        x = cell["excess_delay_samples"].to_numpy(float)
        y = cell["absolute_doppler_hz"].to_numpy(float)
        ax.scatter(x, y, s=14, alpha=0.56, color=BAND_COLORS[band], edgecolors="none", label="Measured")
        _draw_density_contours(ax, selected["cells"].get(cell_id), x, y)
        ax.set_title(_cell_title(cell_id), fontsize=10)
        ax.set_xlabel("Excess delay (samples)", fontsize=8.5)
        ax.set_ylabel("Absolute relative Doppler (Hz)", fontsize=8.5)
        ax.grid(alpha=0.18, linewidth=0.6)
        ax.tick_params(labelsize=8)
    contour_handle = Line2D([0], [0], color="#222222", linewidth=1.0, label="Selected density contours")
    measured_handle = Line2D([0], [0], marker="o", color="w", markerfacecolor="#777777", markersize=6, label="Measured retained observations")
    fig.legend(handles=[measured_handle, contour_handle], loc="upper center", ncol=2, frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 0.975))
    fig.suptitle("Path-level delay-Doppler distributions by environment and elevation band", fontsize=12.5, y=0.998)
    fig.text(0.5, 0.012, "Dots show retained path observations; contours show the selected two-dimensional density model.", ha="center", fontsize=8.5)
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.085, top=0.89, wspace=0.28, hspace=0.36)
    fig.savefig(FIGURE_DIR / "delay_doppler_2d_environment_elevation.png", dpi=230, bbox_inches="tight")
    fig.savefig(FIGURE_DIR / "delay_doppler_2d_environment_elevation.pdf", bbox_inches="tight")
    plt.close(fig)


def _power_model_label(family: str) -> str:
    return {
        "single_gaussian_db": "Single Gaussian in dB",
        "gaussian_mixture_db": "Two-Gaussian mixture in dB",
        "beta_linear_ratio": "Beta model after linear-power transform",
    }.get(family, family)


def plot_relative_power(frame: pd.DataFrame, selected: dict) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(10.4, 7.2), sharex=True, sharey=False)
    global_min = float(frame["relative_power_db"].min()) - 1.5
    global_max = 1.5
    x_grid = np.linspace(global_min, global_max, 700)
    for index, cell_id in enumerate(CELL_ORDER):
        ax = axes.flat[index]
        cell = frame[frame["cell_id"] == cell_id]
        values = cell["relative_power_db"].to_numpy(float)
        weights = cell["track_weight_recomputed_primary"].to_numpy(float)
        bins = np.linspace(global_min, global_max, 14)
        ax.hist(values, bins=bins, weights=weights / np.sum(weights), density=True, color="#bdbdbd", alpha=0.70, edgecolor="white", label="Measured weighted histogram")
        entry = selected["cells"].get(cell_id)
        if entry:
            model = {"family": entry["model_family"], "parameters": entry["model"]}
            pdf = evaluate_power_pdf(model, x_grid)
            ax.plot(x_grid, pdf, color="#1b4f9c", linewidth=1.8, label="Selected PDF")
            ax.text(0.03, 0.94, _power_model_label(entry["model_family"]), transform=ax.transAxes, ha="left", va="top", fontsize=7.2, color="#1b4f9c")
        ax.set_title(_cell_title(cell_id), fontsize=10)
        ax.set_xlim(global_min, global_max)
        ax.set_xlabel("Path-relative power (dB)", fontsize=8.5)
        ax.set_ylabel("Density", fontsize=8.5)
        ax.grid(alpha=0.18, linewidth=0.6)
        ax.tick_params(labelsize=8)
        if index == 0:
            ax.legend(frameon=False, fontsize=7.5, loc="lower left")
    fig.suptitle("Measured and fitted path-relative power distributions", fontsize=12.5, y=0.997)
    fig.text(0.5, 0.012, "Power is relative to the direct-path reference; it is not a received fading-envelope fit.", ha="center", fontsize=8.5)
    fig.subplots_adjust(left=0.075, right=0.985, bottom=0.085, top=0.91, wspace=0.28, hspace=0.38)
    fig.savefig(FIGURE_DIR / "relative_power_empirical_vs_fitted.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_delay_dispersion(records: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.3), sharey=True)
    environment_records = records[records["scope"] == "environment_only"]
    for ax, environment in zip(axes[:2], ("Urban", "Mountain/Valley")):
        subset = environment_records[environment_records["environment_class"] == environment]
        x, y = weighted_ecdf(subset["rms_delay_dispersion_samples"].to_numpy(float), np.ones(len(subset)))
        ax.step(x, y, where="post", color=ENVIRONMENT_COLORS[environment], linewidth=2.0)
        ax.set_title(environment, fontsize=10.5)
        ax.set_xlabel("Retained-path delay dispersion (samples)", fontsize=8.5)
        ax.set_xlim(left=0)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.18, linewidth=0.6)
        ax.tick_params(labelsize=8)
    cell_records = records[records["scope"] == "elevation_ready"]
    cell_axis = axes[2]
    cell_handles: list[Line2D] = []
    for cell_id in CELL_ORDER:
        subset = cell_records[cell_records["cell_id"] == cell_id]
        if subset.empty:
            continue
        environment, band = cell_id.rsplit("/", 1)
        x, y = weighted_ecdf(subset["rms_delay_dispersion_samples"].to_numpy(float), np.ones(len(subset)))
        line_style = "-" if environment == "Urban" else "--"
        cell_axis.step(x, y, where="post", color=BAND_COLORS[band], linestyle=line_style, linewidth=1.6)
        cell_handles.append(Line2D([0], [0], color=BAND_COLORS[band], linestyle=line_style, linewidth=1.6, label=f"{environment} | {band}"))
    cell_axis.set_title("Environment x elevation band", fontsize=10.5)
    cell_axis.set_xlabel("Retained-path delay dispersion (samples)", fontsize=8.5)
    cell_axis.set_xlim(left=0)
    cell_axis.set_ylim(0, 1.02)
    cell_axis.grid(alpha=0.18, linewidth=0.6)
    cell_axis.tick_params(labelsize=8)
    axes[0].set_ylabel("Empirical CDF", fontsize=8.5)
    axes[0].text(0.04, 0.07, "one point per unique run/window set", transform=axes[0].transAxes, fontsize=7.5, color="#555555")
    cell_axis.legend(handles=cell_handles, frameon=False, fontsize=6.8, loc="lower right")
    fig.suptitle("Retained-path delay-dispersion ECDF", fontsize=12.5, y=0.99)
    fig.subplots_adjust(left=0.06, right=0.99, bottom=0.16, top=0.84, wspace=0.17)
    fig.savefig(FIGURE_DIR / "retained_path_delay_dispersion_ecdf.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_signed_3d(frame: pd.DataFrame) -> None:
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    figure = plt.figure(figsize=(11.0, 5.8))
    axes = [figure.add_subplot(1, 2, index + 1, projection="3d") for index in range(2)]
    power = frame["relative_power_db"].to_numpy(float)
    color_norm = Normalize(vmin=float(np.min(power)), vmax=float(np.max(power)))
    scalar = plt.cm.ScalarMappable(norm=color_norm, cmap="viridis")
    scalar.set_array(power)
    for ax, environment in zip(axes, ("Urban", "Mountain/Valley")):
        subset = frame[frame["environment_class"] == environment]
        for band in ("LOW", "MID", "HIGH"):
            band_subset = subset[subset["elevation_band"] == band]
            ax.scatter(
                band_subset["excess_delay_samples"],
                band_subset["doppler_offset_hz"],
                band_subset["relative_power_db"],
                c=band_subset["relative_power_db"],
                cmap="viridis",
                norm=color_norm,
                marker=BAND_MARKERS[band],
                s=18,
                alpha=0.76,
                depthshade=False,
            )
        ax.set_title(environment, fontsize=10.5, pad=10)
        ax.set_xlabel("Excess delay (samples)", labelpad=5, fontsize=8)
        ax.set_ylabel("Signed relative Doppler (Hz)", labelpad=5, fontsize=8)
        ax.set_zlabel("Path-relative power (dB)", labelpad=5, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.view_init(elev=23, azim=-58)
        ax.grid(alpha=0.25)
    figure.colorbar(scalar, ax=axes, shrink=0.72, pad=0.08, label="Path-relative power (dB)")
    handles = [Line2D([0], [0], marker=BAND_MARKERS[band], color="black", linestyle="None", markersize=6, label=band) for band in ("LOW", "MID", "HIGH")]
    figure.legend(handles=handles, loc="upper center", ncol=3, frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 0.995))
    figure.suptitle("Measured path-level delay-Doppler-power scatter", fontsize=12.5, y=1.02)
    figure.text(0.5, 0.015, "Color and height show path-relative power; marker shape indicates elevation band.", ha="center", fontsize=8.5)
    figure.subplots_adjust(left=0.01, right=0.91, bottom=0.08, top=0.83, wspace=0.05)
    figure.savefig(FIGURE_DIR / "delay_doppler_power_3d_signed.pdf", bbox_inches="tight")
    plt.close(figure)


def _write_tables(frame: pd.DataFrame, delay_models: dict, power_models: dict, records: pd.DataFrame) -> None:
    delay_summary = pd.read_csv(MODEL_DIR / "delay_doppler_cell_summary.csv")
    delay_rows: list[dict] = []
    for _, row in delay_summary.iterrows():
        cell_id = row["cell_id"]
        entry = delay_models["cells"].get(cell_id)
        model = None if entry is None else entry["model"]
        selection = None if entry is None else entry["selection"]
        environment, band = cell_id.rsplit("/", 1)
        delay_rows.append(
            {
                "environment": environment,
                "elevation_band": band,
                "row_count": int(row["row_count"]),
                "track_count": int(row["track_count"]),
                "scene_count": int(row["scene_count"]),
                "selected_model": "empirical_only" if entry is None else entry["model_family"],
                "selected_component_count": "" if selection is None else selection["n_components"],
                "validation_fold_count": "" if selection is None else selection["validation_fold_count"],
                "validation_nlpd": "" if selection is None else selection["mean_weighted_nlpd"],
                "bic": "" if selection is None else selection["bic"],
                "component_effective_mass": "" if model is None else json.dumps(model["component_effective_mass"]),
                "means_delay_samples_abs_doppler_hz": "" if model is None else json.dumps(model["means"]),
                "covariances_delay_doppler": "" if model is None else json.dumps(model["covariances"]),
                "mixture_proportions": "" if model is None else json.dumps(model["proportions"]),
            }
        )
    pd.DataFrame(delay_rows).to_csv(TABLE_DIR / "delay_doppler_model_summary.csv", index=False)

    power_summary = pd.read_csv(MODEL_DIR / "relative_power_cell_summary.csv")
    power_rows: list[dict] = []
    for _, row in power_summary.iterrows():
        cell_id = row["cell_id"]
        entry = power_models["cells"].get(cell_id)
        environment, band = cell_id.rsplit("/", 1)
        selection = None if entry is None else entry["selection"]
        power_rows.append(
            {
                "environment": environment,
                "elevation_band": band,
                "row_count": int(row["row_count"]),
                "track_count": int(row["track_count"]),
                "scene_count": int(row["scene_count"]),
                "selected_model": "empirical_only" if entry is None else _power_model_label(entry["model_family"]),
                "parameters": "" if entry is None else json.dumps(entry["model"]),
                "validation_fold_count": "" if selection is None else selection["validation_fold_count"],
                "validation_nlpd": "" if selection is None else selection["validation_nlpd"],
                "validation_ecdf_distance": "" if selection is None else selection["validation_ecdf_distance"],
                "bic": "" if selection is None else selection["bic"],
            }
        )
    pd.DataFrame(power_rows).to_csv(TABLE_DIR / "relative_power_model_summary.csv", index=False)

    quantile_rows: list[dict] = []
    for (scope, cell_id), subset in records.groupby(["scope", "cell_id"], sort=True):
        values = subset["rms_delay_dispersion_samples"].to_numpy(float)
        quantile_rows.append(
            {
                "scope": scope,
                "cell_id": cell_id,
                "group_count": int(len(values)),
                "minimum": float(np.min(values)),
                "q10": float(np.quantile(values, 0.10)),
                "q25": float(np.quantile(values, 0.25)),
                "median": float(np.quantile(values, 0.50)),
                "q75": float(np.quantile(values, 0.75)),
                "q90": float(np.quantile(values, 0.90)),
                "maximum": float(np.max(values)),
            }
        )
    pd.DataFrame(quantile_rows).to_csv(TABLE_DIR / "retained_path_delay_dispersion_quantiles.csv", index=False)


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_population()
    delay_models = load_json("selected_delay_doppler_2d_models.json")
    power_models = load_json("selected_relative_power_models.json")
    records = pd.read_csv(MODEL_DIR / "retained_path_delay_dispersion.csv")
    plot_delay_doppler(frame, delay_models)
    plot_delay_dispersion(records)
    plot_signed_3d(frame)
    _write_tables(frame, delay_models, power_models, records)


if __name__ == "__main__":
    main()
