from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


OUTPUT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = (
    Path(r"E:\GNSS_Multipath_Project")
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/"
    "population/gmm_feature_population.csv"
)
SAMPLE_RATE_HZ = 10.23e6
SAMPLE_PERIOD_NS = 1e9 / SAMPLE_RATE_HZ
DELAY_FIELD = "excess_delay_samples"
POWER_FIELD = "relative_power_db"
WEIGHT_FIELD = "track_weight_recomputed_primary"
GROUP_FIELDS = ["run_id", "center_window_id"]
ENVIRONMENTS = ("Urban", "Mountain/Valley")
ELEVATION_BANDS = ("LOW", "MID", "HIGH")
COLORS = {"Urban": "#1f77b4", "Mountain/Valley": "#ff7f0e"}


def _bool_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def load_population(path: Path = SOURCE_CSV) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {
        *GROUP_FIELDS,
        "scene_id",
        "track_id",
        "environment_class",
        "elevation_band",
        "primary_population_included",
        "cell_ready",
        DELAY_FIELD,
        POWER_FIELD,
        WEIGHT_FIELD,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"missing required fields: {sorted(missing)}")
    frame = frame[
        _bool_mask(frame["primary_population_included"])
        & _bool_mask(frame["cell_ready"])
    ].copy()
    frame[[DELAY_FIELD, POWER_FIELD, WEIGHT_FIELD]] = frame[
        [DELAY_FIELD, POWER_FIELD, WEIGHT_FIELD]
    ].apply(pd.to_numeric, errors="coerce")
    numeric = frame[[DELAY_FIELD, POWER_FIELD, WEIGHT_FIELD]].to_numpy(float)
    if not np.isfinite(numeric).all():
        raise ValueError("non-finite delay, power, or weight input")
    if (frame[DELAY_FIELD] <= 0).any() or (frame[WEIGHT_FIELD] <= 0).any():
        raise ValueError("secondary delays and analysis weights must be positive")
    if not set(frame["environment_class"]).issubset(ENVIRONMENTS):
        raise ValueError("unexpected environment class")
    if not set(frame["elevation_band"]).issubset(ELEVATION_BANDS):
        raise ValueError("unexpected elevation band")
    return frame


def fit_weighted_power_delay_line(
    delay_samples: np.ndarray,
    relative_power_db: np.ndarray,
    weights: np.ndarray,
) -> dict[str, float]:
    """Fit P_rel,dB = intercept + slope * excess_delay_samples by WLS."""
    x = np.asarray(delay_samples, dtype=float)
    y = np.asarray(relative_power_db, dtype=float)
    w = np.asarray(weights, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or w.ndim != 1 or not (len(x) == len(y) == len(w)):
        raise ValueError("delay, power, and weights must be equal-length vectors")
    if len(x) < 2 or np.unique(x).size < 2:
        raise ValueError("at least two distinct delay values are required")
    if not np.isfinite(np.column_stack((x, y, w))).all() or np.any(w <= 0):
        raise ValueError("fit inputs must be finite and weights positive")

    design = np.column_stack((np.ones_like(x), x))
    weighted_design = design * np.sqrt(w)[:, None]
    weighted_response = y * np.sqrt(w)
    beta, _, _, _ = np.linalg.lstsq(weighted_design, weighted_response, rcond=None)
    prediction = design @ beta
    weighted_mean = float(np.average(y, weights=w))
    residual_sum = float(np.sum(w * (y - prediction) ** 2))
    total_sum = float(np.sum(w * (y - weighted_mean) ** 2))
    r_squared = 1.0 - residual_sum / total_sum if total_sum > 0 else 1.0
    slope = float(beta[1])
    return {
        "intercept_db": float(beta[0]),
        "slope_db_per_sample": slope,
        "decay_rate_per_sample": float(-slope * np.log(10.0) / 10.0),
        "weighted_r_squared": float(r_squared),
        "weighted_rmse_db": float(np.sqrt(residual_sum / np.sum(w))),
    }


def power_weighted_delay_moments(
    secondary_delays_samples: np.ndarray,
    secondary_relative_power_db: np.ndarray,
) -> dict[str, float | int]:
    """Add one normalized direct reference and calculate delay moments."""
    delay = np.asarray(secondary_delays_samples, dtype=float)
    power_db = np.asarray(secondary_relative_power_db, dtype=float)
    if delay.ndim != 1 or power_db.ndim != 1 or len(delay) != len(power_db):
        raise ValueError("secondary delay and power must be equal-length vectors")
    if not np.isfinite(np.column_stack((delay, power_db))).all():
        raise ValueError("secondary delay and power must be finite")
    delays = np.concatenate(([0.0], delay))
    powers = np.concatenate(([1.0], np.power(10.0, power_db / 10.0)))
    total_power = float(np.sum(powers))
    mean_delay = float(np.sum(powers * delays) / total_power)
    variance = float(np.sum(powers * (delays - mean_delay) ** 2) / total_power)
    return {
        "path_count_including_direct": int(len(delays)),
        "total_relative_power_linear": total_power,
        "mean_delay_samples": mean_delay,
        "rms_delay_dispersion_samples": float(np.sqrt(max(variance, 0.0))),
    }


def empirical_cdf(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("CDF input must be a non-empty finite vector")
    unique_values, counts = np.unique(np.sort(values, kind="mergesort"), return_counts=True)
    probability = np.cumsum(counts) / counts.sum()
    return unique_values, probability


def build_rms_delay_table(frame: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for (run_id, center_window_id), group in frame.groupby(GROUP_FIELDS, sort=True):
        environments = group["environment_class"].astype(str).unique()
        bands = group["elevation_band"].astype(str).unique()
        if len(environments) != 1 or len(bands) != 1:
            raise ValueError(f"mixed group labels for {run_id}/{center_window_id}")
        moments = power_weighted_delay_moments(
            group[DELAY_FIELD].to_numpy(float),
            group[POWER_FIELD].to_numpy(float),
        )
        records.append(
            {
                "run_id": str(run_id),
                "center_window_id": int(center_window_id),
                "environment_class": environments[0],
                "elevation_band": bands[0],
                "secondary_path_count": int(len(group)),
                **moments,
                "rms_delay_dispersion_ns": float(
                    moments["rms_delay_dispersion_samples"] * SAMPLE_PERIOD_NS
                ),
            }
        )
    return pd.DataFrame(records)


def fit_all_cells(frame: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            group = frame[
                (frame["environment_class"] == environment)
                & (frame["elevation_band"] == band)
            ]
            model = fit_weighted_power_delay_line(
                group[DELAY_FIELD].to_numpy(float),
                group[POWER_FIELD].to_numpy(float),
                group[WEIGHT_FIELD].to_numpy(float),
            )
            records.append(
                {
                    "environment": environment,
                    "elevation_band": band,
                    "observation_count": int(len(group)),
                    "track_count": int(group["track_id"].nunique()),
                    "scene_count": int(group["scene_id"].nunique()),
                    **model,
                }
            )
    return pd.DataFrame(records)


def _write_summary(models: pd.DataFrame, rms: pd.DataFrame, path: Path) -> None:
    rms_summary = (
        rms.groupby(["environment_class", "elevation_band"])[
            "rms_delay_dispersion_samples"
        ]
        .agg(group_count="count", median="median", q25=lambda x: x.quantile(0.25), q75=lambda x: x.quantile(0.75))
        .reset_index()
    )
    summary = models.merge(
        rms_summary,
        left_on=["environment", "elevation_band"],
        right_on=["environment_class", "elevation_band"],
        how="left",
    ).drop(columns=["environment_class"])
    summary["median_rms_delay_dispersion_ns"] = summary["median"] * SAMPLE_PERIOD_NS
    summary.to_csv(path, index=False)


def generate_figure(frame: pd.DataFrame, models: pd.DataFrame, rms: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "figure.dpi": 160,
        }
    )
    fig, axes = plt.subplots(2, 3, figsize=(11.4, 7.4), sharex="row", sharey="row")
    for column, band in enumerate(ELEVATION_BANDS):
        top = axes[0, column]
        bottom = axes[1, column]
        for environment in ENVIRONMENTS:
            color = COLORS[environment]
            group = frame[
                (frame["environment_class"] == environment)
                & (frame["elevation_band"] == band)
            ]
            model = models[
                (models["environment"] == environment)
                & (models["elevation_band"] == band)
            ].iloc[0]
            top.scatter(
                group[DELAY_FIELD],
                group[POWER_FIELD],
                s=16,
                alpha=0.34,
                color=color,
                marker="o" if environment == "Urban" else "^",
                linewidths=0,
                label=f"{environment} observations" if column == 0 else None,
            )
            x_grid = np.linspace(group[DELAY_FIELD].min(), group[DELAY_FIELD].max(), 160)
            top.plot(
                x_grid,
                model["intercept_db"] + model["slope_db_per_sample"] * x_grid,
                color=color,
                linewidth=2.1,
                linestyle="-" if environment == "Urban" else "--",
                label=f"{environment} decay fit" if column == 0 else None,
            )

            rms_group = rms[
                (rms["environment_class"] == environment)
                & (rms["elevation_band"] == band)
            ]
            cdf_x, cdf_y = empirical_cdf(rms_group["rms_delay_dispersion_samples"].to_numpy(float))
            bottom.step(
                cdf_x,
                cdf_y,
                where="post",
                color=color,
                linewidth=2.0,
                linestyle="-" if environment == "Urban" else "--",
                label=environment if column == 0 else None,
            )

        top.set_title(f"Power-delay relation | {band}")
        bottom.set_title(f"RMS delay dispersion CDF | {band}")
        top.grid(True, alpha=0.22)
        bottom.grid(True, alpha=0.22)
        top.set_xlabel("Excess delay (samples)")
        bottom.set_xlabel("RMS delay dispersion (samples)")
        bottom.set_ylim(0.0, 1.02)

    axes[0, 0].set_ylabel("Path-relative power (dB)")
    axes[1, 0].set_ylabel("Cumulative probability")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.935))
    fig.suptitle(
        "Measured power-delay decay and retained-path RMS delay dispersion",
        fontsize=16,
        y=0.985,
    )
    fig.text(
        0.5,
        0.012,
        "Decay fits use retained secondary paths. RMS moments include one normalized direct-path reference per run-window path set.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0.02, 0.045, 0.995, 0.89), h_pad=2.15, w_pad=1.6)
    figure_dir = OUTPUT_ROOT / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    stem = figure_dir / "power_delay_decay_and_rms_delay_dispersion_cdf"
    fig.savefig(stem.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    frame = load_population()
    models = fit_all_cells(frame)
    rms = build_rms_delay_table(frame)
    model_dir = OUTPUT_ROOT / "model"
    table_dir = OUTPUT_ROOT / "tables"
    model_dir.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    models.to_csv(model_dir / "power_delay_decay_models.csv", index=False)
    rms.to_csv(model_dir / "retained_path_rms_delay_dispersion_by_run_window.csv", index=False)
    _write_summary(models, rms, table_dir / "power_delay_rms_summary.csv")
    (model_dir / "power_delay_rms_metadata.json").write_text(
        json.dumps(
            {
                "source_population": str(SOURCE_CSV),
                "source_rows": int(len(frame)),
                "run_window_path_sets": int(len(rms)),
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "sample_period_ns": SAMPLE_PERIOD_NS,
                "power_delay_model": "P_rel_dB = intercept_db + slope_db_per_sample * excess_delay_samples",
                "fit_population": "retained secondary path observations; direct reference excluded from decay fit",
                "rms_formula": "sqrt(sum_l p_l*(tau_l-tau_bar)^2/sum_l p_l)",
                "rms_population": "one normalized direct reference plus retained secondary paths in each unique run/window group",
                "interpretation": "retained-path RMS delay dispersion, not complete-CIR RMS delay spread",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    generate_figure(frame, models, rms)


if __name__ == "__main__":
    main()
