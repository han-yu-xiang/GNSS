#!/usr/bin/env python3
"""Build the Phase-1 scientific closure from the frozen canonical r3 model.

This module is deliberately a closure/interpretation layer.  It does not
re-fit the traditional model and never reads raw IQ or any SAGE intermediate.
All generated tables are written to a new-only namespace.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np


CANONICAL_REL = Path("dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3")
OUTPUT_REL = Path("dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2")
REPORT_REL = Path("docs/PHASE1_TRADITIONAL_CHANNEL_MODELING_SCIENTIFIC_CLOSURE.md")
STAGE4_PARAMETER_REL = Path("dataset/multipath_event_database/v1/partitions/parameter_set_id=parameters_20260825_stage4_path_v1/facts/path_parameters.csv")

ENVIRONMENTS = ("Urban", "Special Reflective", "Mountain/Valley", "Highway/Open")
BANDS = ("LOW", "MID", "HIGH")
PARAMETERS = ("excess_delay_samples", "doppler_offset_hz", "relative_power_db")
CELL_ORDER = tuple(f"{environment}__{band}" for environment in ENVIRONMENTS for band in BANDS)
POLICY_PRIMARY = "C_WEIGHTED_OBSERVATION"
POLICY_RAW = "A_RAW_OBSERVATION"
POLICY_TRACK = "B_ALGORITHM_TRACK_MEDIAN"
SCENE_BOOTSTRAP_REPLICATES = 1000
SCENE_BOOTSTRAP_SEED = 2026083001
OUTPUT_VERSION = "phase1-scientific-closure-v1"

EFFECT_FIELDS = [
    "parameter",
    "comparison",
    "comparison_type",
    "reference",
    "effect_direction",
    "effect_size",
    "model_q50_contrast",
    "bootstrap_interval",
    "bootstrap_lower",
    "bootstrap_median",
    "bootstrap_upper",
    "bootstrap_replicates",
    "LOSO_stability",
    "LOSO_margin",
    "support_strength",
    "scientific_status",
    "scientific_interpretation",
    "left_scope",
    "right_scope",
    "left_count",
    "right_count",
    "left_median",
    "right_median",
]

ENVIRONMENT_FIELDS = [
    "environment_class",
    "support_status",
    "observation_count",
    "sum_weights",
    "kish_effective_sample_size",
    "scene_count",
    "run_count",
    "delay_behavior",
    "delay_family",
    "delay_median",
    "delay_iqr",
    "doppler_behavior",
    "doppler_family",
    "doppler_median",
    "doppler_iqr",
    "relative_power_behavior",
    "relative_power_family",
    "relative_power_median",
    "relative_power_iqr",
    "joint_dependence_status",
    "joint_dependence_source",
    "joint_dependence_summary",
    "derived_channel_statistics",
    "elevation_dependence",
    "uncertainty_summary",
    "data_support_limitations",
]

ELEVATION_FIELDS = [
    "elevation_band",
    "parameter",
    "observation_count",
    "sum_weights",
    "kish_effective_sample_size",
    "scene_count",
    "run_count",
    "median",
    "q25",
    "q75",
    "effect_vs_elevation_ready_global",
    "bootstrap_interval",
    "support_strength",
    "ELEVATION_EFFECT",
    "scientific_interpretation",
]

INTERACTION_FIELDS = [
    "environment_class",
    "parameter",
    "comparison",
    "low_band",
    "high_band",
    "low_direct_count",
    "high_direct_count",
    "effect_size",
    "model_q50_contrast",
    "bootstrap_interval",
    "support_strength",
    "LOSO_stability",
    "LOSO_margin",
    "ENVIRONMENT_ELEVATION_INTERACTION",
    "scientific_interpretation",
]

CONTINUOUS_FIELDS = [
    "environment_class",
    "parameter",
    "diagnostic_support_status",
    "weighted_spearman_rho",
    "weighted_slope",
    "slope_bootstrap_lower",
    "slope_bootstrap_median",
    "slope_bootstrap_upper",
    "evidence_class",
    "interpretation",
]

STAGE4_FIELDS = [
    "selection_dimension",
    "category",
    "stage3_count",
    "stage4_count",
    "stage3_weighted_mass",
    "stage4_weighted_mass",
    "stage3_fraction",
    "stage4_fraction",
    "fraction_difference",
    "stage3_median",
    "stage4_median",
    "stage3_bootstrap_interval",
    "stage4_bootstrap_interval",
    "evidence_status",
    "interpretation",
]

ROBUSTNESS_FIELDS = [
    "conclusion_id",
    "conclusion_type",
    "parameter",
    "scope",
    "primary_weighted_effect",
    "primary_bootstrap_interval",
    "raw_clustered_effect",
    "track_median_effect",
    "stage4_sensitivity",
    "scene_block_bootstrap",
    "run_block_sensitivity",
    "LOSO_validation",
    "robustness_class",
    "rationale",
]

SUPPORT_FIELDS = [
    "environment_class",
    "elevation_band",
    "cell_id",
    "support_status",
    "direct_observation_count",
    "sum_weights",
    "kish_effective_sample_size",
    "track_count",
    "run_count",
    "scene_count",
    "bounded_journal_claims",
    "complete_12_cell_modeling",
    "continuous_elevation_generalization",
    "future_ai_model",
    "decision_reason",
]

JOINT_FIELDS = [
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "pair",
    "correlation",
    "dependence_status",
    "support_interpretation",
    "scientific_interpretation",
]

PLOT_FIELDS = [
    "plot_id",
    "data_source",
    "population",
    "scope",
    "scope_id",
    "environment_class",
    "elevation_band",
    "parameter",
    "metric",
    "x",
    "y",
    "status",
]

FIGURE_PLAN_FIELDS = [
    "item_id",
    "item_type",
    "title",
    "scientific_question",
    "source_artifacts",
    "plot_type",
    "priority",
    "vtc_boundary",
    "notes",
]

TABLE_PLAN_FIELDS = [
    "table_id",
    "title",
    "purpose",
    "source_artifacts",
    "priority",
    "recommended_columns",
    "vtc_boundary",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def value_string(value: float | int | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return f"{float(value):.9g}"


def weighted_quantile(values: Sequence[float], weights: Sequence[float], probability: float) -> float:
    values_array = np.asarray(values, dtype=float)
    weights_array = np.asarray(weights, dtype=float)
    if values_array.size == 0 or values_array.size != weights_array.size:
        raise ValueError("values and weights must be non-empty and equal length")
    if not 0.0 <= probability <= 1.0 or not np.all(np.isfinite(values_array)) or not np.all(np.isfinite(weights_array)) or np.any(weights_array <= 0.0):
        raise ValueError("invalid values, weights, or probability")
    order = np.argsort(values_array, kind="mergesort")
    cumulative = np.cumsum(weights_array[order])
    index = int(np.searchsorted(cumulative, probability * cumulative[-1], side="left"))
    return float(values_array[order][min(index, len(order) - 1)])


def weighted_summary(rows: Sequence[Mapping[str, Any]], parameter: str) -> dict[str, Any]:
    values = [float(row[parameter]) for row in rows]
    weights = [float(row.get("weight", row.get("track_weight", 1.0))) for row in rows]
    if not values:
        return {"count": 0, "sum_weights": 0.0, "kish": 0.0, "mean": None, "median": None, "q25": None, "q75": None, "q025": None, "q975": None, "std": None}
    total = float(sum(weights))
    mean_value = float(sum(value * weight for value, weight in zip(values, weights)) / total)
    variance = float(sum(weight * (value - mean_value) ** 2 for value, weight in zip(values, weights)) / total)
    return {
        "count": len(values),
        "sum_weights": total,
        "kish": total * total / float(sum(weight * weight for weight in weights)),
        "mean": mean_value,
        "median": weighted_quantile(values, weights, 0.5),
        "q25": weighted_quantile(values, weights, 0.25),
        "q75": weighted_quantile(values, weights, 0.75),
        "q025": weighted_quantile(values, weights, 0.025),
        "q975": weighted_quantile(values, weights, 0.975),
        "std": math.sqrt(max(variance, 0.0)),
    }


def scope_stats(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    weights = [float(row.get("weight", row.get("track_weight", 1.0))) for row in rows]
    total = float(sum(weights))
    return {
        "observation_count": len(rows),
        "sum_weights": total,
        "kish_effective_sample_size": total * total / float(sum(weight * weight for weight in weights)) if weights else 0.0,
        "track_count": len({str(row.get("track_id", row.get("stage3_path_id", ""))) for row in rows}),
        "run_count": len({str(row.get("run_id", "")) for row in rows}),
        "scene_count": len({str(row.get("scene_id", "")) for row in rows}),
    }


def support_label(stats_row: Mapping[str, Any]) -> str:
    count = int(stats_row.get("observation_count", 0))
    scenes = int(stats_row.get("scene_count", 0))
    kish = float(stats_row.get("kish_effective_sample_size", 0.0))
    if count == 0:
        return "NO_DIRECT_SUPPORT"
    if scenes < 2 or kish < 3.0:
        return "PRIOR_DOMINANT"
    if count < 10 or scenes < 3 or kish < 10.0:
        return "SPARSE_PARTIAL_POOLING"
    return "DATA_SUPPORTED"


def classify_effect(interval: tuple[float, float, float] | None, support: str, loso: str) -> dict[str, str]:
    if interval is None:
        return {
            "effect_direction": "INCONCLUSIVE",
            "support_strength": support,
            "scientific_status": "NOT_SUPPORTED" if support == "NO_DIRECT_SUPPORT" else "INCONCLUSIVE",
            "scientific_interpretation": "No usable scene-block contrast interval is available.",
        }
    lower, _, upper = interval
    if lower > 0.0:
        direction = "HIGHER"
    elif upper < 0.0:
        direction = "LOWER"
    else:
        direction = "NO_ROBUST_DIRECTION"
    if support == "NO_DIRECT_SUPPORT":
        status = "NOT_SUPPORTED"
        interpretation = "No direct observations support this comparison; do not interpret the parent-only value as a cell result."
    elif direction == "NO_ROBUST_DIRECTION":
        status = "NO_ROBUST_DIFFERENCE" if support == "DATA_SUPPORTED" else "INCONCLUSIVE"
        interpretation = "The scene-block interval crosses zero; a robust directional difference is not established."
    elif support == "DATA_SUPPORTED" and loso in {"STABLE", "MOSTLY_ROBUST"}:
        status = "SUPPORTED"
        interpretation = f"The weighted contrast is {direction.lower()} with a non-zero scene-block interval and grouped LOSO support."
    elif support in {"SPARSE_PARTIAL_POOLING", "PRIOR_DOMINANT"}:
        status = "PARTIAL"
        interpretation = f"The contrast is directionally {direction.lower()} but support is {support}; treat it as partial evidence."
    else:
        status = "INCONCLUSIVE"
        interpretation = f"The contrast is directionally {direction.lower()} but grouped stability is {loso}."
    return {"effect_direction": direction, "support_strength": support, "scientific_status": status, "scientific_interpretation": interpretation}


def loso_stability_label(fold_count: int, margin: float | None) -> str:
    if fold_count < 2 or margin is None or not math.isfinite(margin):
        return "INCONCLUSIVE"
    if fold_count >= 3 and margin >= 0.10:
        return "STABLE"
    if fold_count >= 3 and margin >= 0.02:
        return "MOSTLY_ROBUST"
    return "SENSITIVE"


def classify_continuous_evidence(support: str, lower: float | None, upper: float | None, point: float | None = None, rho: float | None = None) -> str:
    if support != "DATA_SUPPORTED" or lower is None or upper is None:
        return "INSUFFICIENT"
    if lower > 0.0 or upper < 0.0:
        return "ROBUST"
    if point is not None and rho is not None and math.isfinite(point) and math.isfinite(rho) and point * rho < 0.0:
        return "INCONSISTENT"
    return "WEAK"


def cell_order() -> tuple[str, ...]:
    return CELL_ORDER


def _scope_filter(rows: Sequence[Mapping[str, Any]], environment: str | None = None, band: str | None = None, elevation_ready_only: bool = False) -> list[dict[str, Any]]:
    filtered = []
    for row in rows:
        if environment is not None and str(row.get("environment_class", "")) != environment:
            continue
        if elevation_ready_only and not parse_bool(row.get("elevation_ready")):
            continue
        if band is not None and str(row.get("elevation_band", "")) != band:
            continue
        filtered.append(dict(row))
    return filtered


def _bootstrap_contrast(
    rows: Sequence[Mapping[str, Any]],
    parameter: str,
    left_predicate: Callable[[Mapping[str, Any]], bool],
    right_predicate: Callable[[Mapping[str, Any]], bool],
    seed: int,
    replicates: int = SCENE_BOOTSTRAP_REPLICATES,
) -> tuple[float, float, float] | None:
    relevant = [row for row in rows if left_predicate(row) or right_predicate(row)]
    scenes = sorted({str(row.get("scene_id", "")) for row in relevant if str(row.get("scene_id", ""))})
    if len(scenes) < 2:
        return None
    by_scene = {scene: [row for row in relevant if str(row.get("scene_id", "")) == scene] for scene in scenes}
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(replicates):
        selected = rng.choice(scenes, size=len(scenes), replace=True)
        sampled = [row for scene in selected for row in by_scene[str(scene)]]
        left = [row for row in sampled if left_predicate(row)]
        right = [row for row in sampled if right_predicate(row)]
        if not left or not right:
            continue
        left_summary = weighted_summary(left, parameter)
        right_summary = weighted_summary(right, parameter)
        values.append(float(left_summary["median"] - right_summary["median"]))
    if not values:
        return None
    return tuple(float(value) for value in np.quantile(np.asarray(values), [0.025, 0.5, 0.975]))


def _interval_string(interval: tuple[float, float, float] | None) -> str:
    return "" if interval is None else "[" + ", ".join(value_string(value) for value in interval) + "]"


def _lo_so_map(score_rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str, str], tuple[str, float | None]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in score_rows:
        key = (str(row.get("scope", "")), str(row.get("scope_id", "")), str(row.get("parameter", "")))
        if parse_bool(row.get("valid")):
            grouped[key].append(row)
    result: dict[tuple[str, str, str], tuple[str, float | None]] = {}
    for key, rows in grouped.items():
        ranked = sorted(rows, key=lambda row: float(row.get("weighted_held_out_mean_log_likelihood")), reverse=True)
        if not ranked or not parse_bool(ranked[0].get("selected_for_scope")):
            result[key] = ("INCONCLUSIVE", None)
            continue
        margin = None
        if len(ranked) > 1:
            margin = float(ranked[0]["weighted_held_out_mean_log_likelihood"]) - float(ranked[1]["weighted_held_out_mean_log_likelihood"])
        folds = int(float(ranked[0].get("held_out_scene_count", 0) or 0))
        result[key] = (loso_stability_label(folds, margin), margin)
    return result


def _r3_bootstrap_interval(rows: Sequence[Mapping[str, Any]], scope: str, scope_id: str, parameter: str) -> tuple[float, float, float] | None:
    candidates = [row for row in rows if row.get("scope") == scope and row.get("scope_id") == scope_id and row.get("parameter") == parameter and row.get("metric") == "observed_weighted_median" and row.get("status") == "PASS"]
    if not candidates:
        return None
    row = candidates[0]
    values = [parse_float(row.get(field)) for field in ("lower_2_5", "median_50", "upper_97_5")]
    return None if any(value is None for value in values) else (float(values[0]), float(values[1]), float(values[2]))


def _model_row(models: Mapping[tuple[str, str, str], Mapping[str, Any]], scope: str, scope_id: str, parameter: str) -> Mapping[str, Any] | None:
    return models.get((scope, scope_id, parameter))


def _policy_summary(summary_rows: Sequence[Mapping[str, Any]], policy: str, scope: str, scope_id: str, parameter: str) -> Mapping[str, Any] | None:
    for row in summary_rows:
        if row.get("policy") == policy and row.get("scope") == scope and row.get("scope_id") == scope_id and row.get("parameter") == parameter:
            return row
    return None


def _weighted_band_contrast(rows: Sequence[Mapping[str, Any]], parameter: str, low_band: str, high_band: str) -> float | None:
    low_rows = [row for row in rows if str(row.get("elevation_band", "")) == low_band]
    high_rows = [row for row in rows if str(row.get("elevation_band", "")) == high_band]
    if not low_rows or not high_rows:
        return None
    low_median = weighted_summary(low_rows, parameter)["median"]
    high_median = weighted_summary(high_rows, parameter)["median"]
    return None if low_median is None or high_median is None else float(high_median - low_median)


def _interaction_difference_in_differences(
    rows: Sequence[Mapping[str, Any]],
    parameter: str,
    environment: str,
    low_band: str,
    high_band: str,
) -> float | None:
    """Return the environment-specific band contrast minus the other-env contrast."""
    environment_rows = [row for row in rows if str(row.get("environment_class", "")) == environment]
    other_environment_rows = [row for row in rows if str(row.get("environment_class", "")) != environment]
    within_environment = _weighted_band_contrast(environment_rows, parameter, low_band, high_band)
    other_environment = _weighted_band_contrast(other_environment_rows, parameter, low_band, high_band)
    if within_environment is None or other_environment is None:
        return None
    return float(within_environment - other_environment)


def _bootstrap_interaction_difference_in_differences(
    rows: Sequence[Mapping[str, Any]],
    parameter: str,
    environment: str,
    low_band: str,
    high_band: str,
    seed: int,
    replicates: int = SCENE_BOOTSTRAP_REPLICATES,
) -> tuple[float, float, float] | None:
    """Bootstrap a difference-in-differences by resampling complete scenes."""
    scenes = sorted({str(row.get("scene_id", "")) for row in rows if str(row.get("scene_id", ""))})
    if len(scenes) < 2:
        return None
    by_scene = {scene: [row for row in rows if str(row.get("scene_id", "")) == scene] for scene in scenes}
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(replicates):
        selected = rng.choice(scenes, size=len(scenes), replace=True)
        sampled = [row for scene in selected for row in by_scene[str(scene)]]
        estimate = _interaction_difference_in_differences(sampled, parameter, environment, low_band, high_band)
        if estimate is not None and math.isfinite(estimate):
            estimates.append(float(estimate))
    if not estimates:
        return None
    return tuple(float(value) for value in np.quantile(np.asarray(estimates), [0.025, 0.5, 0.975]))


def _interaction_loso(
    rows: Sequence[Mapping[str, Any]],
    parameter: str,
    environment: str,
    low_band: str,
    high_band: str,
) -> tuple[str, float | None]:
    """Assess leave-one-scene-out sign stability for the interaction contrast."""
    scenes = sorted({str(row.get("scene_id", "")) for row in rows if str(row.get("scene_id", ""))})
    full = _interaction_difference_in_differences(rows, parameter, environment, low_band, high_band)
    if full is None or len(scenes) < 3:
        return "INCONCLUSIVE", None
    folds = [
        _interaction_difference_in_differences(
            [row for row in rows if str(row.get("scene_id", "")) != held_out],
            parameter,
            environment,
            low_band,
            high_band,
        )
        for held_out in scenes
    ]
    estimates = [float(value) for value in folds if value is not None and math.isfinite(float(value))]
    if len(estimates) < 3 or abs(float(full)) < 1e-12:
        return "INCONCLUSIVE", None
    signs = {int(np.sign(value)) for value in estimates if abs(value) >= 1e-12}
    if len(signs) != 1:
        return "SENSITIVE", 0.0
    margin = min(abs(value) for value in estimates) / abs(float(full))
    return loso_stability_label(len(estimates), float(margin)), float(margin)


def _model_interaction_difference_in_differences(
    models: Mapping[tuple[str, str, str], Mapping[str, Any]],
    parameter: str,
    environment: str,
    low_band: str,
    high_band: str,
) -> float | None:
    def model_q50(env: str, band: str) -> float | None:
        row = _model_row(models, "cell", f"{env}__{band}", parameter)
        return parse_float(row.get("model_q050")) if row else None

    env_low = model_q50(environment, low_band)
    env_high = model_q50(environment, high_band)
    if env_low is None or env_high is None:
        return None
    other_gradients: list[float] = []
    for other in ENVIRONMENTS:
        if other == environment:
            continue
        low = model_q50(other, low_band)
        high = model_q50(other, high_band)
        if low is not None and high is not None:
            other_gradients.append(float(high - low))
    if not other_gradients:
        return None
    return float((env_high - env_low) - np.mean(other_gradients))


def _effect_row(
    parameter: str,
    comparison: str,
    comparison_type: str,
    reference: str,
    left_scope: str,
    right_scope: str,
    left_rows: Sequence[Mapping[str, Any]],
    right_rows: Sequence[Mapping[str, Any]],
    model_q50_contrast: float | None,
    support: str,
    loso: str,
    loso_margin: float | None,
    interval: tuple[float, float, float] | None,
) -> dict[str, Any]:
    left_summary = weighted_summary(left_rows, parameter) if left_rows else weighted_summary([], parameter)
    right_summary = weighted_summary(right_rows, parameter) if right_rows else weighted_summary([], parameter)
    effect_size = None if left_summary["median"] is None or right_summary["median"] is None else float(left_summary["median"] - right_summary["median"])
    classified = classify_effect(interval, support, loso)
    return {
        "parameter": parameter,
        "comparison": comparison,
        "comparison_type": comparison_type,
        "reference": reference,
        "effect_direction": classified["effect_direction"],
        "effect_size": effect_size,
        "model_q50_contrast": model_q50_contrast,
        "bootstrap_interval": _interval_string(interval),
        "bootstrap_lower": None if interval is None else interval[0],
        "bootstrap_median": None if interval is None else interval[1],
        "bootstrap_upper": None if interval is None else interval[2],
        "bootstrap_replicates": SCENE_BOOTSTRAP_REPLICATES if interval is not None else 0,
        "LOSO_stability": loso,
        "LOSO_margin": loso_margin,
        "support_strength": support,
        "scientific_status": classified["scientific_status"],
        "scientific_interpretation": classified["scientific_interpretation"],
        "left_scope": left_scope,
        "right_scope": right_scope,
        "left_count": left_summary["count"],
        "right_count": right_summary["count"],
        "left_median": left_summary["median"],
        "right_median": right_summary["median"],
    }


def _load_stage4_rows(root: Path) -> list[dict[str, Any]]:
    path = root / STAGE4_PARAMETER_REL
    rows = []
    for raw in read_csv_rows(path):
        if raw.get("label_value") != "confirmed_multipath" or raw.get("path_role") != "multipath" or not parse_bool(raw.get("environment_modeling_ready")):
            continue
        row = {
            "stage4_path_id": raw.get("event_path_id", ""),
            "event_id": raw.get("event_id", ""),
            "scene_id": raw.get("scene_id", ""),
            "run_id": raw.get("run_id", ""),
            "environment_class": raw.get("environment_class", ""),
            "elevation_band": raw.get("elevation_band", ""),
            "elevation_ready": parse_bool(raw.get("elevation_modeling_ready")),
            "excess_delay_samples": parse_float(raw.get("excess_delay_samples")),
            "doppler_offset_hz": parse_float(raw.get("relative_doppler_hz")),
            "relative_power_db": parse_float(raw.get("relative_power_db")),
            "weight": 1.0,
        }
        if row["environment_class"] not in ENVIRONMENTS or any(row[parameter] is None for parameter in PARAMETERS):
            raise ValueError("Stage4 source contains an invalid modeling row")
        rows.append(row)
    return rows


def _track_representatives(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_track: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_track[str(row.get("track_id", ""))].append(row)
    output = []
    for track_id, members in by_track.items():
        representative = {"track_id": track_id, "track_observation_count": len(members), "scene_id": members[0].get("scene_id", ""), "run_id": members[0].get("run_id", ""), "environment_class": members[0].get("environment_class", ""), "elevation_band": members[0].get("elevation_band", "") , "weight": 1.0}
        for parameter in PARAMETERS:
            values = sorted(float(row[parameter]) for row in members)
            representative[parameter] = float(np.median(values))
        output.append(representative)
    return output


def _make_effect_tables(data: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source_rows = data["source_rows"]
    models = data["models"]
    summaries = data["summaries"]
    score_loso = data["score_loso"]
    bootstrap_rows = data["scene_bootstrap"]
    effects: list[dict[str, Any]] = []
    elevation: list[dict[str, Any]] = []
    interactions: list[dict[str, Any]] = []
    elevation_ready = _scope_filter(source_rows, elevation_ready_only=True)
    for parameter_index, parameter in enumerate(PARAMETERS):
        global_rows = source_rows
        global_model = _model_row(models, "global", "global", parameter)
        for environment_index, environment in enumerate(ENVIRONMENTS):
            environment_rows = _scope_filter(source_rows, environment=environment)
            environment_model = _model_row(models, "environment", environment, parameter)
            loso, margin = score_loso.get(("environment", environment, parameter), score_loso.get(("global", "global", parameter), ("INCONCLUSIVE", None)))
            interval = _bootstrap_contrast(source_rows, parameter, lambda row, env=environment: row.get("environment_class") == env, lambda row: True, SCENE_BOOTSTRAP_SEED + parameter_index * 31 + environment_index)
            if interval is None:
                interval = _r3_bootstrap_interval(bootstrap_rows, "environment", environment, parameter)
            model_contrast = None
            if environment_model and global_model:
                model_contrast = float(environment_model["model_q050"]) - float(global_model["model_q050"])
            environment_support = str(environment_model.get("support_status", "INCONCLUSIVE")) if environment_model else "INCONCLUSIVE"
            effects.append(_effect_row(parameter, f"ENVIRONMENT:{environment}_VS_GLOBAL", "ENVIRONMENT", "global", f"environment:{environment}", "global", environment_rows, global_rows, model_contrast, environment_support, loso, margin, interval))

        for band_index, band in enumerate(BANDS):
            band_rows = _scope_filter(source_rows, band=band, elevation_ready_only=True)
            interval = _bootstrap_contrast(elevation_ready, parameter, lambda row, b=band: row.get("elevation_band") == b, lambda row: True, SCENE_BOOTSTRAP_SEED + parameter_index * 101 + band_index)
            stats_row = scope_stats(band_rows)
            support = support_label(stats_row)
            classified = _effect_row(parameter, f"ELEVATION:{band}_VS_ELEVATION_READY_GLOBAL", "ELEVATION", "elevation_ready_global", f"elevation:{band}", "elevation_ready_global", band_rows, elevation_ready, None, support, "INCONCLUSIVE", None, interval)
            effects.append(classified)
            band_summary = weighted_summary(band_rows, parameter) if band_rows else weighted_summary([], parameter)
            elevation.append({
                "elevation_band": band,
                "parameter": parameter,
                "observation_count": stats_row["observation_count"],
                "sum_weights": stats_row["sum_weights"],
                "kish_effective_sample_size": stats_row["kish_effective_sample_size"],
                "scene_count": stats_row["scene_count"],
                "run_count": stats_row["run_count"],
                "median": band_summary["median"],
                "q25": band_summary["q25"],
                "q75": band_summary["q75"],
                "effect_vs_elevation_ready_global": classified["effect_size"],
                "bootstrap_interval": classified["bootstrap_interval"],
                "support_strength": classified["support_strength"],
                "ELEVATION_EFFECT": {"SUPPORTED": "SUPPORTED", "PARTIAL": "PARTIAL", "NO_ROBUST_DIFFERENCE": "INCONCLUSIVE", "INCONCLUSIVE": "INCONCLUSIVE", "NOT_SUPPORTED": "NOT_SUPPORTED"}.get(classified["scientific_status"], "INCONCLUSIVE"),
                "scientific_interpretation": classified["scientific_interpretation"],
            })

        for environment_index, environment in enumerate(ENVIRONMENTS):
            direct_bands = []
            band_rows_map: dict[str, list[dict[str, Any]]] = {}
            for band in BANDS:
                band_rows = _scope_filter(source_rows, environment=environment, band=band, elevation_ready_only=True)
                if band_rows:
                    direct_bands.append(band)
                    band_rows_map[band] = band_rows
            if len(direct_bands) < 2:
                selected_low = selected_high = ""
                interval = None
                low_rows: list[dict[str, Any]] = []
                high_rows: list[dict[str, Any]] = []
            else:
                selected_low, selected_high = direct_bands[0], direct_bands[-1]
                low_rows, high_rows = band_rows_map[selected_low], band_rows_map[selected_high]
                interval = _bootstrap_interaction_difference_in_differences(
                    source_rows,
                    parameter,
                    environment,
                    selected_low,
                    selected_high,
                    SCENE_BOOTSTRAP_SEED + parameter_index * 211 + environment_index,
                )
            model_contrast = None if not selected_low else _model_interaction_difference_in_differences(models, parameter, environment, selected_low, selected_high)
            support_statuses = []
            for band in direct_bands:
                row = _model_row(models, "cell", f"{environment}__{band}", parameter)
                if row:
                    support_statuses.append(str(row.get("support_status", "INCONCLUSIVE")))
            if not direct_bands:
                support = "NO_DIRECT_SUPPORT"
            elif all(status == "DATA_SUPPORTED" for status in support_statuses):
                support = "DATA_SUPPORTED"
            elif any(status in {"SPARSE_PARTIAL_POOLING", "DATA_SUPPORTED"} for status in support_statuses):
                support = "SPARSE_PARTIAL_POOLING"
            else:
                support = "PRIOR_DOMINANT"
            loso, loso_margin = _interaction_loso(source_rows, parameter, environment, selected_low, selected_high) if selected_low else ("INCONCLUSIVE", None)
            classified = classify_effect(interval, support, loso)
            interactions.append({
                "environment_class": environment,
                "parameter": parameter,
                "comparison": f"{environment}:{selected_high}_VS_{selected_low}" if selected_low else f"{environment}:INSUFFICIENT_BAND_PAIR",
                "low_band": selected_low,
                "high_band": selected_high,
                "low_direct_count": len(low_rows),
                "high_direct_count": len(high_rows),
                "effect_size": None if len(direct_bands) < 2 else weighted_summary(high_rows, parameter)["median"] - weighted_summary(low_rows, parameter)["median"],
                "model_q50_contrast": model_contrast,
                "bootstrap_interval": _interval_string(interval),
                "support_strength": support,
                "LOSO_stability": loso,
                "LOSO_margin": loso_margin,
                "ENVIRONMENT_ELEVATION_INTERACTION": "SUPPORTED" if classified["scientific_status"] == "SUPPORTED" else "PARTIAL" if classified["scientific_status"] == "PARTIAL" else "NOT_SUPPORTED" if classified["scientific_status"] == "NOT_SUPPORTED" else "INCONCLUSIVE",
                "scientific_interpretation": "At least two direct elevation bands are needed to evaluate an environment-specific interaction." if len(direct_bands) < 2 else "Interaction is the environment-specific elevation-band contrast minus the corresponding contrast in other environments; scene-block bootstrap and leave-one-scene-out stability are reported.",
            })
    for parameter in PARAMETERS:
        rows = [row for row in interactions if row["parameter"] == parameter]
        statuses = [row["ENVIRONMENT_ELEVATION_INTERACTION"] for row in rows]
        overall = "SUPPORTED" if "SUPPORTED" in statuses else "PARTIAL" if "PARTIAL" in statuses else "INCONCLUSIVE" if "INCONCLUSIVE" in statuses else "NOT_SUPPORTED"
        interactions.append({
            "environment_class": "ALL_ENVIRONMENTS",
            "parameter": parameter,
            "comparison": "ALL_ENVIRONMENTS",
            "low_band": "",
            "high_band": "",
            "low_direct_count": "",
            "high_direct_count": "",
            "effect_size": "",
            "model_q50_contrast": "",
            "bootstrap_interval": "",
            "support_strength": "AGGREGATED",
            "LOSO_stability": "AGGREGATED",
            "LOSO_margin": "",
            "ENVIRONMENT_ELEVATION_INTERACTION": overall,
            "scientific_interpretation": f"Across environments, the strongest supported environment-specific interaction label is {overall}; sparse and parent-dominated cells remain limiting.",
        })
    return effects, elevation, interactions


def _behavior(effect_rows: Sequence[Mapping[str, Any]], parameter: str, environment: str) -> str:
    for row in effect_rows:
        if row["parameter"] == parameter and row["comparison"] == f"ENVIRONMENT:{environment}_VS_GLOBAL":
            status = row["scientific_status"]
            if status == "SUPPORTED":
                return str(row["effect_direction"])
            if status == "NO_ROBUST_DIFFERENCE":
                return "NO_ROBUST_DIFFERENCE"
            return "INCONCLUSIVE"
    return "INCONCLUSIVE"


def _make_environment_characterization(data: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], elevation_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    models = data["models"]
    summaries = data["summaries"]
    joint = {str(row.get("scope_id")): row for row in data["joint_rows"] if row.get("scope") == "environment"}
    derived = data["derived_rows"]
    persistence = data["persistence_rows"]
    output = []
    for environment in ENVIRONMENTS:
        support_model = _model_row(models, "environment", environment, PARAMETERS[0])
        joint_row = joint.get(environment, {})
        pair_summary = {
            "delay_doppler": parse_float(joint_row.get("corr__excess_delay_samples__doppler_offset_hz")),
            "delay_power": parse_float(joint_row.get("corr__excess_delay_samples__relative_power_db")),
            "doppler_power": parse_float(joint_row.get("corr__doppler_offset_hz__relative_power_db")),
        }
        env_derived = [
            {"statistic": row.get("statistic"), "median": parse_float(row.get("median")), "status": row.get("status")}
            for row in derived
            if row.get("scope") == "environment" and row.get("scope_id") == environment
        ]
        env_persistence = next((row for row in persistence if row.get("scope") == "environment" and row.get("scope_id") == environment), {})
        uncertainty = {}
        for parameter in PARAMETERS:
            interval = _r3_bootstrap_interval(data["scene_bootstrap"], "environment", environment, parameter)
            uncertainty[parameter] = _interval_string(interval)
        elev_summary = [
            {"parameter": row["parameter"], "band": row["elevation_band"], "effect": row["effect_vs_elevation_ready_global"], "status": row["ELEVATION_EFFECT"]}
            for row in elevation_rows
            if row["parameter"] in PARAMETERS
        ]
        env_summary = {}
        for parameter in PARAMETERS:
            row = _policy_summary(summaries, POLICY_PRIMARY, "environment", environment, parameter)
            model = _model_row(models, "environment", environment, parameter)
            env_summary[parameter] = {
                "family": model.get("family") if model else "",
                "median": parse_float(row.get("median")) if row else None,
                "q25": parse_float(row.get("q25")) if row else None,
                "q75": parse_float(row.get("q75")) if row else None,
            }
        limitation = "No direct elevation support in Highway/Open–LOW; Special Reflective and Mountain/Valley contain sparse/partial cells; Stage4 is selection-sensitive."
        output.append({
            "environment_class": environment,
            "support_status": support_model.get("support_status") if support_model else "INCONCLUSIVE",
            "observation_count": support_model.get("direct_observation_count") if support_model else 0,
            "sum_weights": support_model.get("sum_weights") if support_model else 0,
            "kish_effective_sample_size": support_model.get("kish_effective_sample_size") if support_model else 0,
            "scene_count": support_model.get("scene_count") if support_model else 0,
            "run_count": support_model.get("run_count") if support_model else 0,
            "delay_behavior": _behavior(effects, "excess_delay_samples", environment),
            "delay_family": env_summary["excess_delay_samples"]["family"],
            "delay_median": env_summary["excess_delay_samples"]["median"],
            "delay_iqr": json.dumps([env_summary["excess_delay_samples"]["q25"], env_summary["excess_delay_samples"]["q75"]]),
            "doppler_behavior": _behavior(effects, "doppler_offset_hz", environment),
            "doppler_family": env_summary["doppler_offset_hz"]["family"],
            "doppler_median": env_summary["doppler_offset_hz"]["median"],
            "doppler_iqr": json.dumps([env_summary["doppler_offset_hz"]["q25"], env_summary["doppler_offset_hz"]["q75"]]),
            "relative_power_behavior": _behavior(effects, "relative_power_db", environment),
            "relative_power_family": env_summary["relative_power_db"]["family"],
            "relative_power_median": env_summary["relative_power_db"]["median"],
            "relative_power_iqr": json.dumps([env_summary["relative_power_db"]["q25"], env_summary["relative_power_db"]["q75"]]),
            "joint_dependence_status": joint_row.get("dependence_status", "INCONCLUSIVE"),
            "joint_dependence_source": joint_row.get("copula_source", ""),
            "joint_dependence_summary": json.dumps(pair_summary, sort_keys=True),
            "derived_channel_statistics": json.dumps({"derived": env_derived, "persistence": env_persistence}, sort_keys=True),
            "elevation_dependence": json.dumps(elev_summary, sort_keys=True),
            "uncertainty_summary": json.dumps(uncertainty, sort_keys=True),
            "data_support_limitations": limitation,
        })
    return output


def _make_continuous(data: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    output = []
    for row in data["continuous_rows"]:
        support = str(row.get("diagnostic_support_status", ""))
        lower = parse_float(row.get("slope_bootstrap_lower"))
        upper = parse_float(row.get("slope_bootstrap_upper"))
        point = parse_float(row.get("weighted_slope"))
        rho = parse_float(row.get("weighted_spearman_rho"))
        evidence = classify_continuous_evidence(support, lower, upper, point, rho)
        interpretation = {
            "ROBUST": "The scene-block slope interval excludes zero; this is exploratory evidence, not a replacement for bands.",
            "WEAK": "The point trend is directionally coherent but its scene-block interval includes zero.",
            "INCONSISTENT": "The rank and slope diagnostics do not agree in direction.",
            "INSUFFICIENT": "Support or scene-block slope evidence is insufficient for a continuous-elevation claim.",
        }[evidence]
        output.append({
            "environment_class": row.get("environment_class"),
            "parameter": row.get("parameter"),
            "diagnostic_support_status": support,
            "weighted_spearman_rho": rho,
            "weighted_slope": point,
            "slope_bootstrap_lower": lower,
            "slope_bootstrap_median": parse_float(row.get("slope_bootstrap_median")),
            "slope_bootstrap_upper": upper,
            "evidence_class": evidence,
            "interpretation": interpretation,
        })
    labels = [row["evidence_class"] for row in output]
    phase2 = "RECOMMENDED" if labels and all(label == "ROBUST" for label in labels) else "NOT_RECOMMENDED" if labels and all(label == "INSUFFICIENT" for label in labels) else "CONDITIONAL"
    return output, phase2


def _make_joint_interpretation(data: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    output = []
    pairs = (
        ("excess_delay_samples", "doppler_offset_hz"),
        ("excess_delay_samples", "relative_power_db"),
        ("doppler_offset_hz", "relative_power_db"),
    )
    supported_env = 0
    for row in data["joint_rows"]:
        for left, right in pairs:
            key = f"corr__{left}__{right}"
            correlation = parse_float(row.get(key))
            if correlation is None:
                continue
            abs_corr = abs(correlation)
            approx = "APPROXIMATELY_INDEPENDENT" if abs_corr < 0.1 else "MEANINGFUL_PAIRWISE_DEPENDENCE"
            if row.get("scope") == "environment" and row.get("dependence_status") == "DATA_SUPPORTED":
                supported_env += 1
            output.append({
                "scope": row.get("scope"),
                "scope_id": row.get("scope_id"),
                "environment_class": row.get("environment_class"),
                "elevation_band": row.get("elevation_band"),
                "pair": f"{left}__{right}",
                "correlation": correlation,
                "dependence_status": row.get("dependence_status"),
                "support_interpretation": approx,
                "scientific_interpretation": "Rank-Gaussian dependence is an association diagnostic; it is not a causal reflector model. Cell-level estimates are interpreted only where r3 support permits.",
            })
    global_rows = [row for row in output if row["scope"] == "global"]
    strong = any(abs(float(row["correlation"])) >= 0.4 for row in global_rows)
    motivation = "STRONG" if strong and supported_env >= 1 else "MODERATE" if global_rows else "WEAK"
    return output, motivation


def _stage4_parameter_rows(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    output = []
    stage4_rows = data["stage4_rows"]
    source_rows = data["source_rows"]
    sensitivity = data["stage4_sensitivity"]
    for parameter in PARAMETERS:
        row3 = next(row for row in sensitivity if row.get("population") == "STAGE3_WEIGHTED_PRIMARY" and row.get("scope") == "global" and row.get("parameter") == parameter)
        row4 = next(row for row in sensitivity if row.get("population") == "STAGE4_STRICT_CONFIRMED" and row.get("scope") == "global" and row.get("parameter") == parameter)
        output.append({
            "selection_dimension": "parameter_global",
            "category": parameter,
            "stage3_count": len(source_rows),
            "stage4_count": len(stage4_rows),
            "stage3_weighted_mass": scope_stats(source_rows)["sum_weights"],
            "stage4_weighted_mass": len(stage4_rows),
            "stage3_fraction": 1.0,
            "stage4_fraction": 1.0,
            "fraction_difference": 0.0,
            "stage3_median": parse_float(row3.get("median")),
            "stage4_median": parse_float(row4.get("median")),
            "stage3_bootstrap_interval": json.dumps([parse_float(row3.get("median_bootstrap_lower")), parse_float(row3.get("median_bootstrap_median")), parse_float(row3.get("median_bootstrap_upper"))]),
            "stage4_bootstrap_interval": json.dumps([parse_float(row4.get("median_bootstrap_lower")), parse_float(row4.get("median_bootstrap_median")), parse_float(row4.get("median_bootstrap_upper"))]),
            "evidence_status": "MATERIAL_DIFFERENCE" if row3.get("selected_family") != row4.get("selected_family") or abs(float(row3.get("median")) - float(row4.get("median"))) > max(abs(float(row3.get("median"))), 1.0) * 0.2 else "PARTIALLY_CONSISTENT",
            "interpretation": "Stage4 strict confirmation is a selected high-confidence subset, not external truth; this row quantifies selection-sensitive descriptive difference.",
        })
    stage3_total = len(source_rows)
    stage4_total = len(stage4_rows)
    for dimension, field, denom3_rows, denom4_rows in (
        ("environment", "environment_class", source_rows, stage4_rows),
        ("elevation_ready", "elevation_band", _scope_filter(source_rows, elevation_ready_only=True), _scope_filter(stage4_rows, elevation_ready_only=True)),
    ):
        categories = ENVIRONMENTS if dimension == "environment" else BANDS
        for category in categories:
            count3 = sum(1 for row in denom3_rows if row.get(field) == category)
            count4 = sum(1 for row in denom4_rows if row.get(field) == category)
            mass3 = sum(float(row.get("weight", row.get("track_weight", 1.0))) for row in denom3_rows if row.get(field) == category)
            mass4 = sum(float(row.get("weight", 1.0)) for row in denom4_rows if row.get(field) == category)
            total3 = len(denom3_rows)
            total4 = len(denom4_rows)
            output.append({
                "selection_dimension": dimension,
                "category": category,
                "stage3_count": count3,
                "stage4_count": count4,
                "stage3_weighted_mass": mass3,
                "stage4_weighted_mass": mass4,
                "stage3_fraction": count3 / total3 if total3 else None,
                "stage4_fraction": count4 / total4 if total4 else None,
                "fraction_difference": (count4 / total4 - count3 / total3) if total3 and total4 else None,
                "stage3_median": "",
                "stage4_median": "",
                "stage3_bootstrap_interval": "",
                "stage4_bootstrap_interval": "",
                "evidence_status": "DESCRIPTIVE_COMPOSITION",
                "interpretation": "Composition difference is descriptive; environment and elevation metadata are not selection causes, and missing Stage4 elevation rows remain excluded from the elevation denominator.",
            })
    all_track = _track_representatives(source_rows)
    linked = [row for row in source_rows if parse_bool(row.get("stage4_confirmed"))]
    linked_track = _track_representatives(linked)
    for metric, values3, values4, note in (
        ("track_observation_count", [float(row.get("track_observation_count", 0)) for row in all_track], [float(row.get("track_observation_count", 0)) for row in linked_track], "Stage4 has no physical persistence field; this is the linked Stage3 algorithm-track persistence proxy."),
    ):
        output.append({
            "selection_dimension": "persistence_proxy",
            "category": metric,
            "stage3_count": len(values3),
            "stage4_count": len(values4),
            "stage3_weighted_mass": len(values3),
            "stage4_weighted_mass": len(values4),
            "stage3_fraction": 1.0,
            "stage4_fraction": 1.0,
            "fraction_difference": 0.0,
            "stage3_median": float(np.median(values3)) if values3 else None,
            "stage4_median": float(np.median(values4)) if values4 else None,
            "stage3_bootstrap_interval": "",
            "stage4_bootstrap_interval": "",
            "evidence_status": "PROXY_ONLY",
            "interpretation": note,
        })
    return output


def _make_support_gap(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    models = data["models"]
    output = []
    for environment in ENVIRONMENTS:
        for band in BANDS:
            row = _model_row(models, "cell", f"{environment}__{band}", PARAMETERS[0])
            if not row:
                continue
            status = str(row.get("support_status"))
            if status == "DATA_SUPPORTED":
                bounded, complete = "YES", "YES"
            elif status == "NO_DIRECT_SUPPORT":
                bounded, complete = "NO_DIRECT_CELL_CLAIM", "NO"
            else:
                bounded, complete = "CONDITIONAL", "CONDITIONAL"
            output.append({
                "environment_class": environment,
                "elevation_band": band,
                "cell_id": f"{environment}__{band}",
                "support_status": status,
                "direct_observation_count": row.get("direct_observation_count"),
                "sum_weights": row.get("sum_weights"),
                "kish_effective_sample_size": row.get("kish_effective_sample_size"),
                "track_count": row.get("track_count"),
                "run_count": row.get("run_count"),
                "scene_count": row.get("scene_count"),
                "bounded_journal_claims": bounded,
                "complete_12_cell_modeling": complete,
                "continuous_elevation_generalization": "CONDITIONAL",
                "future_ai_model": "CONDITIONAL",
                "decision_reason": "Highway/Open–LOW has no direct observations; sparse/prior-dominant cells require partial pooling and bounded claims; no synthetic fill is permitted.",
            })
    return output


def _make_robustness(data: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], interactions: Sequence[Mapping[str, Any]], stage4_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    summaries = data["summaries"]
    source_rows = data["source_rows"]
    track_rows = _track_representatives(source_rows)
    output = []
    effect_index = {(row["comparison_type"], row["parameter"], row["comparison"]): row for row in effects}
    stage4_by_param = {row["category"]: row for row in stage4_rows if row["selection_dimension"] == "parameter_global"}
    for parameter in PARAMETERS:
        for environment in ENVIRONMENTS:
            primary = effect_index[("ENVIRONMENT", parameter, f"ENVIRONMENT:{environment}_VS_GLOBAL")]
            raw_env = _policy_summary(summaries, POLICY_RAW, "environment", environment, parameter)
            raw_global = _policy_summary(summaries, POLICY_RAW, "global", "global", parameter)
            track_env = _policy_summary(summaries, POLICY_TRACK, "environment", environment, parameter)
            track_global = _policy_summary(summaries, POLICY_TRACK, "global", "global", parameter)
            raw_effect = None if not raw_env or not raw_global else parse_float(raw_env.get("median")) - parse_float(raw_global.get("median"))
            track_effect = None if not track_env or not track_global else parse_float(track_env.get("median")) - parse_float(track_global.get("median"))
            stage4_status = stage4_by_param.get(parameter, {}).get("evidence_status", "INCONCLUSIVE")
            direction_matches = all(value is None or (float(value) == 0.0 and float(primary.get("effect_size") or 0.0) == 0.0) or np.sign(float(value)) == np.sign(float(primary.get("effect_size") or 0.0)) for value in (raw_effect, track_effect))
            if primary["scientific_status"] == "SUPPORTED" and direction_matches and primary["LOSO_stability"] in {"STABLE", "MOSTLY_ROBUST"}:
                robustness = "ROBUST" if primary["LOSO_stability"] == "STABLE" and stage4_status != "MATERIAL_DIFFERENCE" else "MOSTLY_ROBUST"
            elif primary["scientific_status"] in {"SUPPORTED", "PARTIAL"}:
                robustness = "MOSTLY_ROBUST" if direction_matches else "SENSITIVE"
            else:
                robustness = "INCONCLUSIVE"
            output.append({
                "conclusion_id": f"ENVIRONMENT_{environment}_{parameter}",
                "conclusion_type": "ENVIRONMENT_EFFECT",
                "parameter": parameter,
                "scope": environment,
                "primary_weighted_effect": primary.get("effect_size"),
                "primary_bootstrap_interval": primary.get("bootstrap_interval"),
                "raw_clustered_effect": raw_effect,
                "track_median_effect": track_effect,
                "stage4_sensitivity": stage4_status,
                "scene_block_bootstrap": "AVAILABLE" if primary.get("bootstrap_interval") else "INCONCLUSIVE",
                "run_block_sensitivity": "AVAILABLE" if _r3_bootstrap_interval(data["run_bootstrap"], "environment", environment, parameter) else "INCONCLUSIVE",
                "LOSO_validation": primary.get("LOSO_stability"),
                "robustness_class": robustness,
                "rationale": "Primary weighted contrast is compared with raw and algorithm-track views; Stage4 is a selection sensitivity, not truth.",
            })
        for band in BANDS:
            primary = effect_index[("ELEVATION", parameter, f"ELEVATION:{band}_VS_ELEVATION_READY_GLOBAL")]
            raw_band = _scope_filter(source_rows, band=band, elevation_ready_only=True)
            raw_all = _scope_filter(source_rows, elevation_ready_only=True)
            raw_effect = weighted_summary(raw_band, parameter)["median"] - weighted_summary(raw_all, parameter)["median"] if raw_band else None
            track_all = _track_representatives(raw_all)
            track_band = _scope_filter(track_all, band=band)
            track_effect = weighted_summary(track_band, parameter)["median"] - weighted_summary(track_all, parameter)["median"] if track_band else None
            signs = [np.sign(float(value)) for value in (raw_effect, track_effect) if value is not None]
            primary_sign = np.sign(float(primary.get("effect_size") or 0.0))
            direction_matches = all(sign == primary_sign for sign in signs) if signs else True
            robustness = "MOSTLY_ROBUST" if primary["scientific_status"] in {"SUPPORTED", "PARTIAL"} and direction_matches else "INCONCLUSIVE"
            output.append({
                "conclusion_id": f"ELEVATION_{band}_{parameter}",
                "conclusion_type": "ELEVATION_EFFECT",
                "parameter": parameter,
                "scope": band,
                "primary_weighted_effect": primary.get("effect_size"),
                "primary_bootstrap_interval": primary.get("bootstrap_interval"),
                "raw_clustered_effect": raw_effect,
                "track_median_effect": track_effect,
                "stage4_sensitivity": stage4_by_param.get(parameter, {}).get("evidence_status", "INCONCLUSIVE"),
                "scene_block_bootstrap": "AVAILABLE" if primary.get("bootstrap_interval") else "INCONCLUSIVE",
                "run_block_sensitivity": "NOT_DIRECTLY_AVAILABLE_FOR_GLOBAL_BAND",
                "LOSO_validation": "NOT_DIRECTLY_APPLICABLE",
                "robustness_class": robustness,
                "rationale": "Elevation comparison uses elevation-ready observations and preserves the formal LOW/MID/HIGH interface.",
            })
        for environment in ENVIRONMENTS:
            interaction = next(row for row in interactions if row["environment_class"] == environment and row["parameter"] == parameter)
            output.append({
                "conclusion_id": f"INTERACTION_{environment}_{parameter}",
                "conclusion_type": "ENVIRONMENT_ELEVATION_INTERACTION",
                "parameter": parameter,
                "scope": environment,
                "primary_weighted_effect": interaction.get("effect_size"),
                "primary_bootstrap_interval": interaction.get("bootstrap_interval"),
                "raw_clustered_effect": "NOT_COMPUTED_AS_PRIMARY",
                "track_median_effect": "NOT_COMPUTED_AS_PRIMARY",
                "stage4_sensitivity": stage4_by_param.get(parameter, {}).get("evidence_status", "INCONCLUSIVE"),
                "scene_block_bootstrap": "AVAILABLE" if interaction.get("bootstrap_interval") else "INCONCLUSIVE",
                "run_block_sensitivity": "NOT_DIRECTLY_AVAILABLE",
                "LOSO_validation": interaction.get("LOSO_stability"),
                "robustness_class": "MOSTLY_ROBUST" if interaction["ENVIRONMENT_ELEVATION_INTERACTION"] in {"SUPPORTED", "PARTIAL"} else "INCONCLUSIVE",
                "rationale": interaction.get("scientific_interpretation"),
            })
    return output


def _make_publication_plans(data: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], support: Sequence[Mapping[str, Any]], joint: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    figure_plan = [
        {"item_id": "Figure 1", "item_type": "figure", "title": "Measurement to SAGE to statistical closure workflow", "scientific_question": "What is the traceable measurement-to-path-to-model chain?", "source_artifacts": "r3 report; phase1 master plan", "plot_type": "workflow diagram", "priority": "CORE", "vtc_boundary": "CORE", "notes": "Use only as a workflow schematic; not a new experiment."},
        {"item_id": "Figure 2", "item_type": "figure", "title": "Environment × elevation support matrix", "scientific_question": "Where is direct evidence available and where is pooling required?", "source_artifacts": "support_gap_decision.csv", "plot_type": "annotated matrix", "priority": "CORE", "vtc_boundary": "SUPPLEMENTARY", "notes": "Keep Highway/Open–LOW visibly empty."},
        {"item_id": "Figure 3", "item_type": "figure", "title": "Excess-delay distributions", "scientific_question": "How does delay vary across environment/elevation under the weighted unit?", "source_artifacts": "weighted summaries; selected marginal models", "plot_type": "empirical CDF/boxplot with model overlay", "priority": "CORE", "vtc_boundary": "CONDITIONAL", "notes": "Use fitted curves for journal/thesis; VTC may use descriptive CDF only."},
        {"item_id": "Figure 4", "item_type": "figure", "title": "Signed relative-Doppler distributions", "scientific_question": "What Doppler behavior is observed and how stable is it?", "source_artifacts": "weighted summaries; bootstrap", "plot_type": "empirical CDF/boxplot", "priority": "CORE", "vtc_boundary": "CONDITIONAL", "notes": "Avoid treating relative Doppler as absolute physical scatterer velocity."},
        {"item_id": "Figure 5", "item_type": "figure", "title": "Relative-power distributions", "scientific_question": "How does relative multipath power vary by environment/elevation?", "source_artifacts": "weighted summaries; bootstrap", "plot_type": "empirical CDF/boxplot", "priority": "CORE", "vtc_boundary": "CONDITIONAL", "notes": "Use dB relative power; no absolute RF claim."},
        {"item_id": "Figure 6", "item_type": "figure", "title": "Derived RMS delay and Doppler spread", "scientific_question": "Which center-level spread diagnostics are supported?", "source_artifacts": "channel_level_statistics.csv", "plot_type": "interval/boxplot", "priority": "SUPPLEMENTARY", "vtc_boundary": "THESIS_ONLY", "notes": "Label conditional RMS and center-level scope."},
        {"item_id": "Figure 7", "item_type": "figure", "title": "Joint parameter dependence", "scientific_question": "Are delay, Doppler and power independent?", "source_artifacts": "joint_dependence_interpretation.csv", "plot_type": "correlation heatmap", "priority": "SUPPLEMENTARY", "vtc_boundary": "THESIS_ONLY", "notes": "Do not show unsupported cell covariance as universal."},
        {"item_id": "Figure 8", "item_type": "figure", "title": "Stage3 versus Stage4 selection sensitivity", "scientific_question": "How does strict confirmation change the observed subset?", "source_artifacts": "stage4_selection_analysis.csv; r3 Stage4 sensitivity", "plot_type": "paired CDF/median interval", "priority": "CORE", "vtc_boundary": "SUPPLEMENTARY", "notes": "Stage4 is not external truth."},
        {"item_id": "Figure 9", "item_type": "figure", "title": "Continuous-elevation exploratory trends", "scientific_question": "Is a continuous elevation condition justified?", "source_artifacts": "continuous_elevation_evidence.csv", "plot_type": "scatter and scene-block slope interval", "priority": "SUPPLEMENTARY", "vtc_boundary": "THESIS_ONLY", "notes": "Current decision is conditional; bands remain formal."},
    ]
    table_plan = [
        {"table_id": "Table 1", "title": "Frozen population and statistical contract", "purpose": "Define observations, tracks, weights, hierarchy, and uncertainty.", "source_artifacts": "r3 model_manifest.json; sampling_contract.json", "priority": "CORE", "recommended_columns": "population counts; unit; weight; blocks; bands", "vtc_boundary": "CORE"},
        {"table_id": "Table 2", "title": "Environment/elevation effect and robustness summary", "purpose": "Present bounded effect directions and sensitivity classifications.", "source_artifacts": "effect_table.csv; robustness_matrix.csv", "priority": "CORE", "recommended_columns": "parameter; comparison; effect; interval; LOSO; robustness", "vtc_boundary": "SUPPLEMENTARY"},
        {"table_id": "Table 3", "title": "Environment × elevation support/data gaps", "purpose": "Make direct, sparse, prior-dominated, and empty cells explicit.", "source_artifacts": "support_gap_decision.csv", "priority": "CORE", "recommended_columns": "cell; n; effective n; scenes; support; gap decision", "vtc_boundary": "SUPPLEMENTARY"},
        {"table_id": "Table 4", "title": "Channel-level derived statistics", "purpose": "Separate center/channel diagnostics from path-level fitted parameters.", "source_artifacts": "channel_level_statistics.csv; persistence_duration_statistics.csv", "priority": "SUPPLEMENTARY", "recommended_columns": "statistic; scope; median; IQR; identifiability", "vtc_boundary": "THESIS_ONLY"},
    ]
    plot_rows = []
    summary_rows = data["summaries"]
    for row in summary_rows:
        if row.get("policy") != POLICY_PRIMARY:
            continue
        plot_rows.extend([
            {"plot_id": "summary", "data_source": "weighted_parameter_summary.csv", "population": row.get("policy"), "scope": row.get("scope"), "scope_id": row.get("scope_id"), "environment_class": row.get("environment_class"), "elevation_band": row.get("elevation_band"), "parameter": row.get("parameter"), "metric": metric, "x": row.get("scope_id"), "y": row.get(metric), "status": row.get("family_selection_status")} for metric in ("mean", "median", "q25", "q75", "q025", "q975")
        ])
    for row in data["cdf_rows"]:
        if row.get("comparison_status") == "COMPARABLE":
            plot_rows.append({"plot_id": "stage3_stage4_cdf", "data_source": "stage3_stage4_cdf_comparison.csv", "population": "STAGE3_WEIGHTED_PRIMARY", "scope": row.get("scope"), "scope_id": row.get("scope_id"), "environment_class": row.get("environment_class"), "elevation_band": row.get("elevation_band"), "parameter": row.get("parameter"), "metric": "stage3_weighted_cdf", "x": row.get("grid_value"), "y": row.get("stage3_weighted_cdf"), "status": row.get("comparison_status")})
            plot_rows.append({"plot_id": "stage3_stage4_cdf", "data_source": "stage3_stage4_cdf_comparison.csv", "population": "STAGE4_STRICT_CONFIRMED", "scope": row.get("scope"), "scope_id": row.get("scope_id"), "environment_class": row.get("environment_class"), "elevation_band": row.get("elevation_band"), "parameter": row.get("parameter"), "metric": "stage4_strict_confirmed_cdf", "x": row.get("grid_value"), "y": row.get("stage4_strict_confirmed_cdf"), "status": row.get("comparison_status")})
    return figure_plan, table_plan, plot_rows


def _make_report(data: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], environments: Sequence[Mapping[str, Any]], elevations: Sequence[Mapping[str, Any]], interactions: Sequence[Mapping[str, Any]], continuous: Sequence[Mapping[str, Any]], phase2_continuous: str, joint: Sequence[Mapping[str, Any]], motivation: str, stage4_rows: Sequence[Mapping[str, Any]], robustness: Sequence[Mapping[str, Any]], support: Sequence[Mapping[str, Any]], figure_plan: Sequence[Mapping[str, Any]], table_plan: Sequence[Mapping[str, Any]], output_dir: Path) -> str:
    stage4_material = sum(1 for row in stage4_rows if row.get("evidence_status") == "MATERIAL_DIFFERENCE")
    parameter_status = {}
    for parameter in PARAMETERS:
        rows = [row for row in effects if row["parameter"] == parameter and row["comparison_type"] == "ENVIRONMENT"]
        statuses = [row["scientific_status"] for row in rows]
        parameter_status[parameter] = "SUPPORTED" if "SUPPORTED" in statuses and all(status in {"SUPPORTED", "NO_ROBUST_DIFFERENCE"} for status in statuses) else "PARTIAL" if any(status in {"SUPPORTED", "PARTIAL"} for status in statuses) else "INCONCLUSIVE"
    overall_environment = "SUPPORTED" if all(value == "SUPPORTED" for value in parameter_status.values()) else "PARTIAL" if any(value in {"SUPPORTED", "PARTIAL"} for value in parameter_status.values()) else "INCONCLUSIVE"
    elevation_status = {}
    for parameter in PARAMETERS:
        rows = [row for row in elevations if row["parameter"] == parameter]
        statuses = [row["ELEVATION_EFFECT"] for row in rows]
        elevation_status[parameter] = "SUPPORTED" if "SUPPORTED" in statuses and all(status in {"SUPPORTED", "INCONCLUSIVE"} for status in statuses) else "PARTIAL" if "SUPPORTED" in statuses or "PARTIAL" in statuses else "INCONCLUSIVE"
    interaction_status = {parameter: next(row["ENVIRONMENT_ELEVATION_INTERACTION"] for row in interactions if row["environment_class"] == "ALL_ENVIRONMENTS" and row["parameter"] == parameter) for parameter in PARAMETERS}
    lines = [
        "# Phase‑1 Traditional Channel Modeling Scientific Closure",
        "",
        "状态：**Scientific closure built from the canonical r3 model; independent QA is recorded in the same new-only namespace.**",
        "",
        "## 1. Scope, canonical input, and scientific unit",
        "",
        f"This closure reads only `{CANONICAL_REL}` and preserves r3 as the canonical traditional model. The primary population is 783 academic Stage3 reliable/persistent path observations, represented as `WEIGHTED_OBSERVATION` with weight `1 / algorithm_track_size`; dependence is handled through scene/run clustering and scene-block bootstrap. The population contains 445 centers, 366 algorithm-level tracks, 716 elevation-ready observations, 50 runs, 12 scenes, and 18 PRNs.",
        "",
        "Stage3 observations and algorithm tracks are measurement/algorithm units, not physical reflector identities. Persistence is algorithm-observed persistence only. Stage4 strict-confirmed paths are a high-confidence validation subset and are not external truth or a Stage3 selection input.",
        "",
        "## 2. What propagation/channel trends are supported",
        "",
        "The formal path-level quantities are excess delay, signed relative Doppler, and relative power in dB. The weighted global candidate families selected by grouped leave-one-scene-out evidence are delay=Lognormal, signed Doppler=Normal, and relative power=Normal. Environment, elevation, and interaction claims below are bounded by support labels and scene/run dependence treatment.",
        "",
        "| Parameter | Environment effect | Elevation effect | Environment×elevation interaction |",
        "|---|---|---|---|",
    ]
    for parameter in PARAMETERS:
        lines.append(f"| `{parameter}` | `{parameter_status[parameter]}` | `{elevation_status[parameter]}` | `{interaction_status[parameter]}` |")
    lines.extend(["", "Machine-readable details are in `effect_table.csv`, `elevation_characterization.csv`, and `environment_elevation_interaction.csv`.", ""])
    lines.extend(["## 3. Environment characterization", "", "The following summaries describe supported measurement-derived behavior; they do not force every environment to have a unique physical signature.", "", "| Environment | Support | Delay | Doppler | Power | Joint dependence | Limitations |", "|---|---|---|---|---|---|---|"])
    for row in environments:
        lines.append(f"| {row['environment_class']} | {row['support_status']} | {row['delay_behavior']} ({row['delay_family']}) | {row['doppler_behavior']} ({row['doppler_family']}) | {row['relative_power_behavior']} ({row['relative_power_family']}) | {row['joint_dependence_summary']} | {row['data_support_limitations']} |")
    lines.extend(["", "If an effect table row is `NO_ROBUST_DIFFERENCE`, that environment/parameter comparison is reported as `NO_ROBUST_DIFFERENCE`, not as a forced separation.", ""])
    lines.extend(["## 4. Elevation characterization", "", "LOW/MID/HIGH remains the formal Phase‑1 interface. Continuous elevation is exploratory and does not replace these bands.", "", "| Band | Parameter | n | Effective n | Effect vs elevation-ready global | Evidence |", "|---|---|---:|---:|---:|---|"])
    for row in elevations:
        lines.append(f"| {row['elevation_band']} | {row['parameter']} | {row['observation_count']} | {value_string(parse_float(row['kish_effective_sample_size']))} | {value_string(parse_float(row['effect_vs_elevation_ready_global']))} | {row['ELEVATION_EFFECT']} |")
    lines.extend(["", "The empty `Highway/Open–LOW` cell is not used to infer a low-elevation Highway/Open effect.", ""])
    lines.extend(["## 5. Environment × elevation interaction", "", "Interaction is assessed as a difference-in-differences: the environment-specific elevation-band contrast is compared with the corresponding contrast in other environments, with scene-block bootstrap and leave-one-scene-out stability. Visual cell differences alone are not treated as interactions.", "", "| Environment | Parameter | Direct band pair | Interaction label | Support |", "|---|---|---|---|---|"])
    for row in interactions:
        if row["environment_class"] != "ALL_ENVIRONMENTS":
            lines.append(f"| {row['environment_class']} | {row['parameter']} | {row['low_band']}→{row['high_band']} | {row['ENVIRONMENT_ELEVATION_INTERACTION']} | {row['support_strength']} |")
    lines.extend(["", "Aggregated interaction labels:", "", *[f"- `{parameter}`: `{interaction_status[parameter]}`" for parameter in PARAMETERS], ""])
    lines.extend(["## 6. Channel-level statistics", "", "Path-level fitted parameters are kept separate from center/channel-level diagnostics. The available derived quantities are power-weighted mean excess delay, conditional RMS delay spread, Doppler centroid, conditional RMS Doppler spread, algorithm-observed reliable component count, aggregate/strongest relative multipath power, and algorithm-observed persistence.", "", "The conditional RMS quantities require multiple Stage3 observations within a center; relative-power quantities are not absolute RF power. No Ricean K-factor is computed: `RICEAN_K = NOT_IDENTIFIABLE`. Persistence is not physical reflector lifetime. See `channel_level_statistics.csv` and `persistence_duration_statistics.csv`.", ""])
    lines.extend(["## 7. Stage4 selection-effect analysis", "", f"The canonical Stage4 result is `MATERIAL_DIFFERENCE`, which is treated as a selection effect rather than a failure. The closure compares the 100 strict-confirmed Stage4 paths with the 783-observation Stage3 primary population. The linked Stage3 subset contains 98 observations for the persistence proxy; Stage4 itself has no physical persistence field.", "", "Stage4 differences are quantified for delay, Doppler, power, environment composition, elevation-ready composition, and the linked Stage3 algorithm-track persistence proxy. The known 100-ms joint selection and candidate-cap mechanisms are retained as design explanations, not post-hoc corrections. Stage4 is not external truth.", "", f"Parameter-level material-difference flags: {stage4_material} of {len(PARAMETERS)}. See `stage4_selection_analysis.csv` and the r3 Stage3/Stage4 sensitivity tables.", ""])
    lines.extend(["## 8. Continuous elevation decision", "", f"The continuous-elevation decision for a future conditional model is `{phase2_continuous}`. Evidence classes are recomputed per environment×parameter in `continuous_elevation_evidence.csv`: `ROBUST` means the scene-block slope interval excludes zero, `WEAK` means the interval includes zero but diagnostics are directionally coherent, `INCONSISTENT` means rank and slope directions disagree, and `INSUFFICIENT` means support is inadequate.", ""])
    lines.extend(["| Environment | Parameter | Evidence |", "|---|---|---|"])
    for row in continuous:
        lines.append(f"| {row['environment_class']} | {row['parameter']} | {row['evidence_class']} |")
    lines.extend(["", "## 9. Joint dependence and AI motivation", "", f"The existing rank-Gaussian dependence diagnostics do not support treating all three parameters as independent. The future joint-density motivation is `{motivation}` because the global delay–relative-power association is material and environment-level dependence is available, while cell-level dependence remains support-gated. This motivates a future conditional joint model only if Phase 2 is separately authorized; it does not authorize training here.", "", "Pairwise and scope-specific interpretations are in `joint_dependence_interpretation.csv`.", ""])
    lines.extend(["## 10. Robustness and data gaps", "", "The robustness matrix compares primary weighted observations, raw clustered observations, algorithm-track medians, Stage4 sensitivity, scene-block bootstrap, run-block sensitivity, and grouped LOSO validation. It is intended for direct reuse in paper limitations and discussion.", "", "| Support class | Cell count |", "|---|---:|"])
    counts = Counter(row["support_status"] for row in support)
    for status in ("DATA_SUPPORTED", "SPARSE_PARTIAL_POOLING", "PRIOR_DOMINANT", "NO_DIRECT_SUPPORT"):
        lines.append(f"| `{status}` | {counts.get(status, 0)} |")
    lines.extend(["", "Every cell and the four separate data-gap decisions are in `support_gap_decision.csv`. Current bounded claims are possible with limitations; complete 12-cell modeling and continuous-elevation generalization remain conditional; Highway/Open–LOW has no direct Stage3 support and receives no synthetic fill.", ""])
    lines.extend(["## 11. Paper-ready figure and table plan", "", "The source plan ranks compact evidence by scientific question. VTC remains a narrower path-characterization paper: fitted stochastic channel modeling, complete synthetic channel generation, and Ricean-K modeling are not automatically VTC claims.", ""])
    for row in figure_plan:
        lines.append(f"- **{row['item_id']} — {row['title']}**: `{row['priority']}`; {row['notes']}")
    lines.extend(["", "Minimal tables:"])
    for row in table_plan:
        lines.append(f"- **{row['table_id']} — {row['title']}**: `{row['priority']}`; {row['purpose']}")
    lines.extend(["", "## 12. Plain-language answers and forbidden claims", "", "1. Supported trends are bounded, measurement-derived differences in the three path parameters; no universal propagation law is established.", "2. Environment differences are parameter-specific and partial; unsupported comparisons remain `NO_ROBUST_DIFFERENCE` or `INCONCLUSIVE`.", "3. Elevation effects are assessed only through LOW/MID/HIGH; continuous elevation is conditional.", "4. Environment×elevation interaction is not uniformly established; it is reported per parameter and environment with sparse-cell limitations.", "5. Global path-level families are delay Lognormal, signed Doppler Normal, and relative-power Normal under weighted grouped LOSO selection.", "6. Center/channel statistics are available conditionally as algorithm-observed diagnostics, not total-channel truth.", "7. Delay and relative power show meaningful global rank dependence; cell-level dependence is support-gated.", "8. Dependence treatment is sensitive enough that scene/run clustering and track-median comparisons remain required.", "9. Stage4 is materially different from Stage3 and therefore is a selection-sensitivity baseline only.", "10. Main limitations are sparse/prior cells, empty Highway/Open–LOW, Stage4 selection, lack of physical reflector identity, no phase/main-path reference for K, and limited independent scenes.", "11. Existing 10.23 MHz evidence is sufficient for bounded traditional journal/thesis claims with limitations, not unrestricted channel generalization.", "12. Do not claim no physical multipath, physical reflector lifetime, Ricean K, absolute RF power, complete 12-cell coverage, universal elevation law, or that Stage4 is external truth.", ""])
    overall_elevation = "SUPPORTED" if all(value == "SUPPORTED" for value in elevation_status.values()) else "PARTIAL" if any(value in {"SUPPORTED", "PARTIAL"} for value in elevation_status.values()) else "INCONCLUSIVE"
    overall_interaction = "SUPPORTED" if all(value == "SUPPORTED" for value in interaction_status.values()) else "PARTIAL" if any(value in {"SUPPORTED", "PARTIAL"} for value in interaction_status.values()) else "INCONCLUSIVE"
    lines.extend(["## Commander decision block", "", "```text", "PHASE_1_TRADITIONAL_MODEL_BUILD = COMPLETE", "PHASE_1_SCIENTIFIC_CLOSURE = PASS_WITH_LIMITATIONS", "JOURNAL_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS", "MASTER_THESIS_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS", f"ENVIRONMENT_EFFECT = {overall_environment}", f"ELEVATION_EFFECT = {overall_elevation}", f"ENVIRONMENT_ELEVATION_INTERACTION = {overall_interaction}", f"AI_JOINT_DENSITY_MOTIVATION = {motivation}", f"CONTINUOUS_ELEVATION_FOR_PHASE2 = {phase2_continuous}", "PROCESS_20_46_MHZ_BEFORE_PHASE2 = CONDITIONAL", "NEW_DATA_COLLECTION_BEFORE_PHASE2 = CONDITIONAL", "```", "", f"All closure outputs are in the new-only namespace `{output_dir}`. No MATLAB/SAGE/batch process, raw IQ read, 20.46 MHz processing, AI training, production request, or modification of r3/r1/r2/Stage4 was performed.", ""])
    return "\n".join(lines)


def load_data(root: Path) -> dict[str, Any]:
    model_dir = root / CANONICAL_REL
    manifest = read_json(model_dir / "model_manifest.json")
    receipt = read_json(model_dir / "build_receipt.json")
    qa = read_json(model_dir / "independent_qa_result.json")
    if manifest.get("model_id") != "environment_elevation_stage3_academic_path_model_v1" or manifest.get("status") != "COMPLETED_WITH_LIMITATIONS":
        raise ValueError("canonical r3 model identity/status gate failed")
    if qa.get("qa_status") != "PASS":
        raise ValueError("canonical r3 independent QA is not PASS")
    if not manifest.get("frozen_hash_status", {}).get("all_match") or not manifest.get("source", {}).get("source_hashes_match_prior") or not manifest.get("source", {}).get("prior_output_hashes_match"):
        raise ValueError("canonical r3 provenance gate failed")
    if receipt.get("status") != "COMPLETED" or receipt.get("model_manifest_sha256") != sha256_file(model_dir / "model_manifest.json"):
        raise ValueError("canonical r3 receipt gate failed")
    return {
        "root": root,
        "model_dir": model_dir,
        "manifest": manifest,
        "receipt": receipt,
        "qa": qa,
        "source_rows": read_csv_rows(model_dir / "source_population_audit.csv"),
        "summaries": read_csv_rows(model_dir / "weighted_parameter_summary.csv"),
        "models": {(row.get("scope", ""), row.get("scope_id", ""), row.get("parameter", "")): row for row in read_csv_rows(model_dir / "selected_marginal_models.csv")},
        "score_rows": read_csv_rows(model_dir / "candidate_family_scores.csv"),
        "scene_bootstrap": read_csv_rows(model_dir / "scene_block_bootstrap.csv"),
        "run_bootstrap": read_csv_rows(model_dir / "run_block_sensitivity.csv"),
        "joint_rows": read_csv_rows(model_dir / "joint_dependence_models.csv"),
        "derived_rows": read_csv_rows(model_dir / "derived_channel_statistics.csv"),
        "persistence_rows": read_csv_rows(model_dir / "persistence_duration_statistics.csv"),
        "stage4_sensitivity": read_csv_rows(model_dir / "stage3_stage4_sensitivity.csv"),
        "cdf_rows": read_csv_rows(model_dir / "stage3_stage4_cdf_comparison.csv"),
        "continuous_rows": read_csv_rows(model_dir / "continuous_elevation_diagnostics.csv"),
        "stage4_rows": _load_stage4_rows(root),
    } | {"score_loso": _lo_so_map(read_csv_rows(model_dir / "candidate_family_scores.csv"))}


def build_closure(root: Path, output_dir: Path, report_path: Path) -> dict[str, Any]:
    if output_dir.exists() or report_path.exists():
        raise FileExistsError("Phase-1 closure output/report already exists; use a new-only namespace")
    if not output_dir.is_relative_to(root) or any(part.lower() in {"scenes", "sage_results"} for part in output_dir.relative_to(root).parts):
        raise ValueError("closure output must remain in a safe new-only project namespace")
    data = load_data(root)
    effects, elevations, interactions = _make_effect_tables(data)
    environments = _make_environment_characterization(data, effects, elevations)
    continuous, phase2_continuous = _make_continuous(data)
    joint, motivation = _make_joint_interpretation(data)
    stage4_analysis = _stage4_parameter_rows(data)
    support = _make_support_gap(data)
    robustness = _make_robustness(data, effects, interactions, stage4_analysis)
    figure_plan, table_plan, plot_data = _make_publication_plans(data, effects, support, joint)
    output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(output_dir / "effect_table.csv", effects, EFFECT_FIELDS)
    write_csv(output_dir / "environment_characterization.csv", environments, ENVIRONMENT_FIELDS)
    write_csv(output_dir / "elevation_characterization.csv", elevations, ELEVATION_FIELDS)
    write_csv(output_dir / "environment_elevation_interaction.csv", interactions, INTERACTION_FIELDS)
    write_csv(output_dir / "continuous_elevation_evidence.csv", continuous, CONTINUOUS_FIELDS)
    write_csv(output_dir / "joint_dependence_interpretation.csv", joint, JOINT_FIELDS)
    write_csv(output_dir / "stage4_selection_analysis.csv", stage4_analysis, STAGE4_FIELDS)
    write_csv(output_dir / "robustness_matrix.csv", robustness, ROBUSTNESS_FIELDS)
    write_csv(output_dir / "support_gap_decision.csv", support, SUPPORT_FIELDS)
    write_csv(output_dir / "figure_table_plan.csv", figure_plan, FIGURE_PLAN_FIELDS)
    write_csv(output_dir / "publication_table_sources.csv", table_plan, TABLE_PLAN_FIELDS)
    write_csv(output_dir / "publication_plot_data.csv", plot_data, PLOT_FIELDS)
    write_csv(output_dir / "channel_level_statistics.csv", data["derived_rows"], list(data["derived_rows"][0].keys()) if data["derived_rows"] else ["scope"])
    write_csv(output_dir / "persistence_duration_statistics.csv", data["persistence_rows"], list(data["persistence_rows"][0].keys()) if data["persistence_rows"] else ["scope"])
    config = {
        "closure_version": OUTPUT_VERSION,
        "canonical_model": str(CANONICAL_REL),
        "primary_statistical_unit": "WEIGHTED_OBSERVATION",
        "primary_weight": "1 / algorithm_track_size",
        "primary_uncertainty": "scene-block bootstrap",
        "sensitivity": ["run-block", "algorithm-track-median", "Stage4 strict-confirmed subset"],
        "formal_elevation_bands": {"LOW": "[0,30)", "MID": "[30,60)", "HIGH": "[60,90]"},
        "phase2_continuous_elevation": phase2_continuous,
        "ai_joint_density_motivation": motivation,
        "ricean_k": "NOT_IDENTIFIABLE",
        "execution_boundary": {"raw_iq_read": False, "matlab": False, "sage": False, "batch": False, "process_20_46_mhz": False, "train_ai": False, "create_production_request": False},
    }
    write_json(output_dir / "closure_config.json", config)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_make_report(data, effects, environments, elevations, interactions, continuous, phase2_continuous, joint, motivation, stage4_analysis, robustness, support, figure_plan, table_plan, output_dir), encoding="utf-8")
    output_hashes = {path.name: sha256_file(path) for path in sorted(output_dir.iterdir()) if path.is_file()}
    manifest = {
        "manifest_version": "phase1-scientific-closure-manifest-v1",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "closure_version": OUTPUT_VERSION,
        "canonical_model": str(CANONICAL_REL),
        "canonical_model_manifest_sha256": sha256_file(data["model_dir"] / "model_manifest.json"),
        "canonical_model_receipt_sha256": sha256_file(data["model_dir"] / "build_receipt.json"),
        "canonical_model_qa_sha256": sha256_file(data["model_dir"] / "independent_qa_result.json"),
        "population": data["manifest"].get("population", {}),
        "effect_rows": len(effects),
        "environment_rows": len(environments),
        "elevation_rows": len(elevations),
        "interaction_rows": len(interactions),
        "stage4_selection_rows": len(stage4_analysis),
        "continuous_rows": len(continuous),
        "support_rows": len(support),
        "execution_boundary": config["execution_boundary"],
        "output_hashes_excluding_manifest_and_receipt": output_hashes,
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path),
        "status": "COMPLETED_WITH_LIMITATIONS",
        "backend": {"python": str(Path(__import__("sys").executable).resolve()), "python_version": platform.python_version(), "numpy": np.__version__},
    }
    write_json(output_dir / "closure_manifest.json", manifest)
    manifest_sha = sha256_file(output_dir / "closure_manifest.json")
    receipt = {
        "receipt_version": "phase1-scientific-closure-receipt-v1",
        "status": "COMPLETED",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "output_dir": str(output_dir),
        "closure_manifest_sha256": manifest_sha,
        "canonical_model": str(CANONICAL_REL),
        "output_files": sorted(path.name for path in output_dir.iterdir() if path.is_file()),
        "output_hashes_excluding_receipt": {path.name: sha256_file(path) for path in sorted(output_dir.iterdir()) if path.is_file()},
    }
    write_json(output_dir / "closure_receipt.json", receipt)
    return {"output_dir": str(output_dir), "report_path": str(report_path), "manifest_sha256": manifest_sha, "status": "COMPLETED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = (args.output or root / OUTPUT_REL).resolve()
    report = (args.report or root / REPORT_REL).resolve()
    try:
        result = build_closure(root, output, report)
    except Exception as exc:
        print(f"PHASE1_CLOSURE_REJECTED={exc}")
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    print("PHASE1_CLOSURE_BUILD=COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
