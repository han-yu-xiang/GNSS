from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OUTPUT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = (
    Path(r"E:\GNSS_Multipath_Project")
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/"
    "population/gmm_feature_population.csv"
)
POWER_FIELD = "relative_power_db"
DELAY_FIELD = "excess_delay_samples"
WEIGHT_FIELD = "track_weight_recomputed_primary"
GROUP_FIELDS = ["run_id", "center_window_id"]
ENVIRONMENTS = ("Urban", "Mountain/Valley")
ELEVATION_BANDS = ("LOW", "MID", "HIGH")


def _bool_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def load_population(path: Path = SOURCE_CSV) -> pd.DataFrame:
    frame = pd.read_csv(path)
    mask = _bool_mask(frame["primary_population_included"])
    frame = frame.loc[mask].copy()
    numeric_fields = [POWER_FIELD, DELAY_FIELD, WEIGHT_FIELD]
    frame[numeric_fields] = frame[numeric_fields].apply(pd.to_numeric, errors="coerce")
    if frame[numeric_fields].isna().any().any():
        raise ValueError("non-finite delay, power, or weight input")
    if (frame[DELAY_FIELD] <= 0).any() or (frame[WEIGHT_FIELD] <= 0).any():
        raise ValueError("secondary delays must be positive and weights must be positive")
    frame["cell_id"] = frame["environment_class"].astype(str) + "/" + frame["elevation_band"].astype(str)
    return frame


def compute_path_set_delay_dispersion(group: pd.DataFrame) -> dict[str, Any]:
    """Compute delay moments after adding the normalized direct-path reference."""
    delays = np.concatenate(([0.0], group[DELAY_FIELD].to_numpy(float)))
    powers_linear = np.concatenate(([1.0], np.power(10.0, group[POWER_FIELD].to_numpy(float) / 10.0)))
    total_power = float(np.sum(powers_linear))
    mean_delay = float(np.sum(powers_linear * delays) / total_power)
    second_moment = float(np.sum(powers_linear * delays**2) / total_power)
    variance = max(second_moment - mean_delay**2, 0.0)
    return {
        "retained_path_count": int(len(group)),
        "total_relative_power_linear_including_direct": total_power,
        "weighted_mean_delay_samples": mean_delay,
        "rms_delay_dispersion_samples": float(np.sqrt(variance)),
        "maximum_excess_delay_samples": float(np.max(delays)),
    }


def group_path_sets(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one delay-dispersion record per unique run/window path set."""
    records: list[dict[str, Any]] = []
    for (run_id, center_window_id), group in frame.groupby(GROUP_FIELDS, sort=True, dropna=False):
        environments = group["environment_class"].dropna().astype(str).unique()
        if len(environments) != 1:
            raise ValueError(f"group {run_id}/{center_window_id} has multiple environments")
        bands = group["elevation_band"].dropna().astype(str).unique()
        if len(bands) > 1:
            raise ValueError(f"group {run_id}/{center_window_id} has multiple elevation bands")
        result = compute_path_set_delay_dispersion(group)
        result.update(
            {
                "run_id": str(run_id),
                "center_window_id": int(center_window_id),
                "group_id": f"{run_id}::{center_window_id}",
                "environment_class": environments[0],
                "elevation_band": bands[0] if len(bands) == 1 else "",
                "track_count_in_set": int(group["track_id"].nunique()),
            }
        )
        records.append(result)
    return pd.DataFrame(records)


def weighted_ecdf(values: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.ndim != 1 or len(values) != len(weights) or len(values) == 0:
        raise ValueError("values and weights must be non-empty one-dimensional arrays")
    if not np.isfinite(values).all() or not np.isfinite(weights).all() or np.any(weights <= 0):
        raise ValueError("ECDF values and weights must be finite and positive")
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    cumulative = np.cumsum(weights[order]) / np.sum(weights)
    unique_values, first_indices = np.unique(sorted_values, return_index=True)
    return unique_values, cumulative[first_indices]


def _scope_records(frame: pd.DataFrame, scope: str) -> pd.DataFrame:
    records = group_path_sets(frame)
    records.insert(0, "scope", scope)
    if scope == "environment_only":
        records.insert(2, "cell_id", records["environment_class"])
    else:
        records.insert(2, "cell_id", records["environment_class"] + "/" + records["elevation_band"])
    return records


def _track_balanced_weights(frame: pd.DataFrame, records: pd.DataFrame) -> pd.DataFrame:
    """Give each track equal total influence across its run/window groups."""
    keys = frame[GROUP_FIELDS].astype(str).agg("::".join, axis=1)
    unique_pairs = pd.DataFrame({"track_id": frame["track_id"].astype(str), "group_id": keys}).drop_duplicates()
    group_counts = unique_pairs.groupby("track_id")["group_id"].nunique()
    unique_pairs["track_balanced_contribution"] = unique_pairs["track_id"].map(1.0 / group_counts)
    group_weights = unique_pairs.groupby("group_id")["track_balanced_contribution"].sum()
    output = records[["scope", "cell_id", "group_id", "environment_class", "elevation_band", "rms_delay_dispersion_samples"]].copy()
    output["track_balanced_group_weight"] = output["group_id"].map(group_weights).fillna(0.0)
    return output


def _write_summary(records: pd.DataFrame, path: Path) -> None:
    summary_rows: list[dict[str, Any]] = []
    for (scope, cell_id), group in records.groupby(["scope", "cell_id"], sort=True):
        summary_rows.append(
            {
                "scope": scope,
                "cell_id": cell_id,
                "group_count": int(len(group)),
                "retained_path_observation_count": int(group["retained_path_count"].sum()),
                "median_rms_delay_dispersion_samples": float(group["rms_delay_dispersion_samples"].median()),
                "q25_rms_delay_dispersion_samples": float(group["rms_delay_dispersion_samples"].quantile(0.25)),
                "q75_rms_delay_dispersion_samples": float(group["rms_delay_dispersion_samples"].quantile(0.75)),
            }
        )
    path.write_text(
        "# Retained-path delay-dispersion summary\n\n"
        "Each row represents one unique run/window path set. A normalized direct-path reference is included in the moment calculation.\n\n"
        + pd.DataFrame(summary_rows).to_csv(index=False),
        encoding="utf-8",
    )


def main() -> None:
    frame = load_population()
    environment_records = _scope_records(frame, "environment_only")
    elevation_ready = frame[_bool_mask(frame["elevation_ready"]) & _bool_mask(frame["cell_ready"])].copy()
    elevation_records = _scope_records(elevation_ready, "elevation_ready")
    records = pd.concat([environment_records, elevation_records], ignore_index=True)
    model_dir = OUTPUT_ROOT / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    records.to_csv(model_dir / "retained_path_delay_dispersion.csv", index=False)
    _write_summary(records, model_dir / "retained_path_delay_dispersion_summary.csv")
    balanced = pd.concat(
        [
            _track_balanced_weights(frame, environment_records),
            _track_balanced_weights(elevation_ready, elevation_records),
        ],
        ignore_index=True,
    )
    balanced.to_csv(model_dir / "retained_path_delay_dispersion_track_balanced.csv", index=False)
    (model_dir / "retained_path_delay_dispersion_metadata.json").write_text(
        json.dumps(
            {
                "formula": "tau_rms=sqrt(sum_l p_l tau_l^2/sum_l p_l - (sum_l p_l tau_l/sum_l p_l)^2)",
                "direct_reference": {"delay_samples": 0.0, "relative_power_db": 0.0},
                "secondary_power_transform": "p_l=10^(relative_power_db/10)",
                "scope_counts": {
                    "environment_only": int(len(environment_records)),
                    "elevation_ready": int(len(elevation_records)),
                },
                "source_population": str(SOURCE_CSV),
                "interpretation": "retained-path delay dispersion, not full-channel RMS delay spread",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
