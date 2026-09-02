#!/usr/bin/env python3
"""Fit and select partially pooled conditional 3-D GMM candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "scripts/conditional_gmm_core.py"
CORE_SPEC = importlib.util.spec_from_file_location("conditional_gmm_core_for_candidate_fit", CORE_PATH)
if CORE_SPEC is None or CORE_SPEC.loader is None:
    raise RuntimeError("cannot load conditional GMM core")
CORE = importlib.util.module_from_spec(CORE_SPEC)
sys.modules[CORE_SPEC.name] = CORE
CORE_SPEC.loader.exec_module(CORE)


K_VALUES = (1, 2, 3)
KAPPA_VALUES = (4.0, 8.0, 16.0, 32.0)
SCORING_DRAWS = 4096
FINAL_DRAWS = 4096
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 2026083105
BASE_SEED = 2026083104
ENVIRONMENTS = ("Urban", "Mountain/Valley")
BANDS = ("LOW", "MID", "HIGH")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--reuse-scoring", action="store_true", help="reuse existing candidate and scene-LOSO score CSVs")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            output: dict[str, Any] = {}
            for field in fields:
                value = row.get(field, "")
                if isinstance(value, (float, np.floating)):
                    value = float(value)
                    if not math.isfinite(value):
                        raise ValueError(f"non-finite output: {path}/{field}")
                    output[field] = f"{value:.12g}"
                else:
                    output[field] = value
            writer.writerow(output)


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_rows(path: Path) -> list[dict[str, Any]]:
    raw_rows = read_csv(path)
    if len(raw_rows) != 518:
        raise ValueError(f"expected 518 rows, got {len(raw_rows)}")
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        row = dict(raw)
        for field in CORE.FEATURE_FIELDS:
            row[field] = float(raw[field])
        row["doppler_offset_hz"] = float(raw["doppler_offset_hz"])
        row["track_weight_recomputed_primary"] = float(raw["track_weight_recomputed_primary"])
        row["absolute_doppler_hz"] = float(raw["absolute_doppler_hz"])
        row["cell_ready"] = str(raw["cell_ready"])
        rows.append(row)
    if sum(row["cell_ready"] == "1" for row in rows) != 487:
        raise ValueError("elevation-ready denominator changed")
    return rows


def model_config(component_count: int, pooling_kappa: float, seed: int) -> Any:
    return CORE.ConditionalGMMConfig(
        component_count=component_count,
        pooling_kappa=pooling_kappa,
        max_iterations=500,
        tolerance=1e-7,
        covariance_floor=1e-5,
        weight_floor=1e-6,
        restart_count=10,
        seed=seed,
    )


def scene_ids(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted({str(row["scene_id"]) for row in rows})


def target_features(row: Mapping[str, Any]) -> np.ndarray:
    return CORE.feature_matrix([row], "log1p_absolute_doppler")[0]


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    values_array = np.asarray(values, dtype=float)
    weights_array = np.asarray(weights, dtype=float)
    return float(np.sum(values_array * weights_array) / np.sum(weights_array))


def energy_score_for_rows(model: Any, rows: Sequence[Mapping[str, Any]], seed: int, draw_count: int = SCORING_DRAWS) -> float:
    if not rows:
        raise ValueError("energy score requires rows")
    draws_by_scope: dict[tuple[str, str], np.ndarray] = {}
    for row in rows:
        key = (str(row["environment_class"]), str(row["elevation_band"]) if row["cell_ready"] == "1" else "")
        if key not in draws_by_scope:
            draws_by_scope[key] = CORE.sample_conditional(model, key[0], key[1] or None, draw_count, seed + len(draws_by_scope))
    scores: list[float] = []
    weights: list[float] = []
    for row in rows:
        key = (str(row["environment_class"]), str(row["elevation_band"]) if row["cell_ready"] == "1" else "")
        draws = draws_by_scope[key]
        target = target_features(row)
        first_term = float(np.linalg.norm(draws - target[None, :], axis=1).mean())
        paired_term = float(np.linalg.norm(draws - np.roll(draws, 1, axis=0), axis=1).mean())
        scores.append(first_term - 0.5 * paired_term)
        weights.append(float(row["track_weight_recomputed_primary"]))
    return weighted_mean(scores, weights)


def convert_signed_draws_to_primary(draws: np.ndarray) -> np.ndarray:
    output = np.asarray(draws, dtype=float).copy()
    output[:, 1] = np.log1p(np.abs(output[:, 1]))
    return output


def fit_scene_fold(train_rows: Sequence[Mapping[str, Any]], test_rows: Sequence[Mapping[str, Any]], component_count: int, pooling_kappa: float, seed: int, doppler_feature_field: str = "log1p_absolute_doppler") -> dict[str, Any]:
    config = model_config(component_count, pooling_kappa, seed)
    model = CORE.fit_conditional_gmm(train_rows, config, doppler_feature_field=doppler_feature_field)
    log_density = CORE.log_predictive_density(model, test_rows)
    test_weights = np.asarray([float(row["track_weight_recomputed_primary"]) for row in test_rows], dtype=float)
    nlpd = float(-np.sum(log_density * test_weights) / np.sum(test_weights))
    energy = energy_score_for_rows(model, test_rows, seed + 100000)
    if doppler_feature_field == "doppler_offset_hz":
        # Evaluate signed sensitivity in the same physical magnitude space.
        magnitude_draws_by_scope: dict[tuple[str, str], np.ndarray] = {}
        scores: list[float] = []
        for row in test_rows:
            key = (str(row["environment_class"]), str(row["elevation_band"]) if row["cell_ready"] == "1" else "")
            if key not in magnitude_draws_by_scope:
                signed_draws = CORE.sample_conditional(model, key[0], key[1] or None, SCORING_DRAWS, seed + 200000 + len(magnitude_draws_by_scope))
                magnitude_draws_by_scope[key] = convert_signed_draws_to_primary(signed_draws)
            draws = magnitude_draws_by_scope[key]
            target = target_features(row)
            first_term = float(np.linalg.norm(draws - target[None, :], axis=1).mean())
            paired_term = float(np.linalg.norm(draws - np.roll(draws, 1, axis=0), axis=1).mean())
            scores.append(first_term - 0.5 * paired_term)
        energy = weighted_mean(scores, test_weights)
    return {"model": model, "nlpd": nlpd, "energy_score": energy, "test_weight": float(np.sum(test_weights)), "test_rows": len(test_rows)}


def fit_scene_loso(rows: Sequence[Mapping[str, Any]], component_count: int, pooling_kappa: float, candidate_index: int, doppler_feature_field: str = "log1p_absolute_doppler") -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for fold_index, held_out_scene in enumerate(scene_ids(rows)):
        train_rows = [row for row in rows if str(row["scene_id"]) != held_out_scene]
        test_rows = [row for row in rows if str(row["scene_id"]) == held_out_scene]
        fit = fit_scene_fold(train_rows, test_rows, component_count, pooling_kappa, BASE_SEED + candidate_index * 10000 + fold_index, doppler_feature_field)
        output.append({"candidate_index": candidate_index, "component_count": component_count, "pooling_kappa": pooling_kappa, "held_out_scene": held_out_scene, "train_scene_count": len(scene_ids(train_rows)), "test_row_count": fit["test_rows"], "test_weight": fit["test_weight"], "weighted_nlpd": fit["nlpd"], "energy_score": fit["energy_score"], "status": "VALID"})
    return output


def aggregate_candidate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    weights = np.asarray([float(row["test_weight"]) for row in rows], dtype=float)
    return {"scene_count": len(rows), "mean_weighted_nlpd": weighted_mean([float(row["weighted_nlpd"]) for row in rows], weights), "mean_energy_score": weighted_mean([float(row["energy_score"]) for row in rows], weights), "total_test_weight": float(np.sum(weights)), "status": "VALID" if len(rows) == len(scene_ids_from_fold_rows(rows)) else "INVALID"}


def scene_ids_from_fold_rows(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return sorted({str(row["held_out_scene"]) for row in rows})


def bootstrap_comparisons(scene_scores: Sequence[Mapping[str, Any]], candidate_keys: Sequence[tuple[int, int, float]], candidate_summaries: Sequence[Mapping[str, Any]], seed: int) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    scenes = sorted({str(row["held_out_scene"]) for row in scene_scores})
    by_candidate_scene = {(int(row["candidate_index"]), str(row["held_out_scene"])): row for row in scene_scores}
    best_k1 = min((row for row in candidate_summaries if int(row["component_count"]) == 1), key=lambda row: float(row["mean_weighted_nlpd"]))
    best_k1_index = int(best_k1["candidate_index"])
    output: list[dict[str, Any]] = []
    for replicate in range(BOOTSTRAP_REPLICATES):
        sampled_scenes = [str(value) for value in rng.choice(scenes, size=len(scenes), replace=True)]
        for key in candidate_keys:
            selected_rows = [by_candidate_scene[(key[0], scene)] for scene in sampled_scenes]
            weights = np.asarray([float(row["test_weight"]) for row in selected_rows], dtype=float)
            nlpd = weighted_mean([float(row["weighted_nlpd"]) for row in selected_rows], weights)
            energy = weighted_mean([float(row["energy_score"]) for row in selected_rows], weights)
            base_rows = [by_candidate_scene[(best_k1_index, scene)] for scene in sampled_scenes]
            base_weights = np.asarray([float(row["test_weight"]) for row in base_rows], dtype=float)
            base_nlpd = weighted_mean([float(row["weighted_nlpd"]) for row in base_rows], base_weights)
            base_energy = weighted_mean([float(row["energy_score"]) for row in base_rows], base_weights)
            output.append({"candidate_index": key[0], "component_count": key[1], "pooling_kappa": key[2], "replicate": replicate, "weighted_nlpd": nlpd, "energy_score": energy, "nlpd_difference_from_best_k1": nlpd - base_nlpd, "energy_difference_from_best_k1": energy - base_energy})
    return output


def paired_nlpd_bootstrap(scene_scores: Sequence[Mapping[str, Any]], candidate_summaries: Sequence[Mapping[str, Any]], seed: int) -> list[dict[str, Any]]:
    """Bootstrap adjacent-K NLPD differences using the same held-out scenes."""
    rng = np.random.default_rng(seed + 1)
    scenes = sorted({str(row["held_out_scene"]) for row in scene_scores})
    by_candidate_scene = {(int(row["candidate_index"]), str(row["held_out_scene"])): row for row in scene_scores}
    best_by_k: dict[int, Mapping[str, Any]] = {}
    for row in candidate_summaries:
        component_count = int(row["component_count"])
        if component_count not in best_by_k or float(row["mean_weighted_nlpd"]) < float(best_by_k[component_count]["mean_weighted_nlpd"]):
            best_by_k[component_count] = row
    output: list[dict[str, Any]] = []
    for larger_k in sorted(k for k in best_by_k if k > 1):
        smaller_k = larger_k - 1
        if smaller_k not in best_by_k:
            continue
        larger = best_by_k[larger_k]
        smaller = best_by_k[smaller_k]
        larger_index = int(larger["candidate_index"])
        smaller_index = int(smaller["candidate_index"])
        for replicate in range(BOOTSTRAP_REPLICATES):
            sampled_scenes = [str(value) for value in rng.choice(scenes, size=len(scenes), replace=True)]
            larger_rows = [by_candidate_scene[(larger_index, scene)] for scene in sampled_scenes]
            smaller_rows = [by_candidate_scene[(smaller_index, scene)] for scene in sampled_scenes]
            larger_weights = np.asarray([float(row["test_weight"]) for row in larger_rows], dtype=float)
            smaller_weights = np.asarray([float(row["test_weight"]) for row in smaller_rows], dtype=float)
            larger_nlpd = weighted_mean([float(row["weighted_nlpd"]) for row in larger_rows], larger_weights)
            smaller_nlpd = weighted_mean([float(row["weighted_nlpd"]) for row in smaller_rows], smaller_weights)
            output.append({
                "replicate": replicate,
                "larger_component_count": larger_k,
                "larger_candidate_index": larger_index,
                "smaller_component_count": smaller_k,
                "smaller_candidate_index": smaller_index,
                "larger_nlpd": larger_nlpd,
                "smaller_nlpd": smaller_nlpd,
                "nlpd_difference_larger_minus_smaller": larger_nlpd - smaller_nlpd,
            })
    return output


def select_candidate(candidate_summaries: Sequence[Mapping[str, Any]], paired_bootstrap_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = [row for row in candidate_summaries if row["status"] == "VALID"]
    if not valid:
        raise ValueError("no valid GMM candidate")
    best = min(valid, key=lambda row: float(row["mean_weighted_nlpd"]))
    comparisons: list[dict[str, Any]] = []
    best_k = int(best["component_count"])
    while best_k > 1:
        lower_candidates = [row for row in valid if int(row["component_count"]) == best_k - 1]
        if not lower_candidates:
            raise ValueError(f"missing valid adjacent lower-K candidate for K={best_k}")
        lower = min(lower_candidates, key=lambda row: float(row["mean_weighted_nlpd"]))
        pair_rows = [
            row for row in paired_bootstrap_rows
            if int(row["larger_candidate_index"]) == int(best["candidate_index"])
            and int(row["smaller_candidate_index"]) == int(lower["candidate_index"])
        ]
        if len(pair_rows) != BOOTSTRAP_REPLICATES:
            raise ValueError(f"expected {BOOTSTRAP_REPLICATES} paired bootstrap rows, got {len(pair_rows)}")
        differences = [float(row["nlpd_difference_larger_minus_smaller"]) for row in pair_rows]
        q025 = float(np.quantile(differences, 0.025))
        q975 = float(np.quantile(differences, 0.975))
        comparison = {
            "larger_component_count": best_k,
            "larger_candidate_index": int(best["candidate_index"]),
            "smaller_component_count": best_k - 1,
            "smaller_candidate_index": int(lower["candidate_index"]),
            "mean_nlpd_difference_larger_minus_smaller": float(np.mean(differences)),
            "q025": q025,
            "q975": q975,
            "decision": "RETAIN_LARGER_K" if q975 < 0.0 else "RETAIN_SMALLER_K",
        }
        comparisons.append(comparison)
        if q975 < 0.0:
            break
        best = lower
        best_k -= 1
    return {"candidate_index": int(best["candidate_index"]), "component_count": int(best["component_count"]), "pooling_kappa": float(best["pooling_kappa"]), "selection_status": "SELECTED_BY_SCENE_LOSO_NLPD_WITH_ADJACENT_K_COMPLEXITY_RULE", "mean_weighted_nlpd": float(best["mean_weighted_nlpd"]), "mean_energy_score": float(best["mean_energy_score"]), "complexity_comparisons": comparisons}


def serialize_model(model: Any) -> dict[str, Any]:
    return {
        "component_count": model.config.component_count,
        "pooling_kappa": model.config.pooling_kappa,
        "doppler_feature_field": model.doppler_feature_field,
        "transform_center": model.transform_center.tolist(),
        "transform_scale": model.transform_scale.tolist(),
        "global_weights": model.global_weights.tolist(),
        "global_means": model.global_means.tolist(),
        "environment_weights": {key: value.tolist() for key, value in model.environment_weights.items()},
        "environment_means": {key: value.tolist() for key, value in model.environment_means.items()},
        "cell_weights": {key: value.tolist() for key, value in model.cell_weights.items()},
        "shared_covariances": model.shared_covariances.tolist(),
        "log_likelihood_iterations": len(model.log_likelihood_history),
    }


def component_rows(model: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for component in range(model.config.component_count):
        base = {"scope": "global", "scope_id": "global", "component": component + 1, "component_weight": float(model.global_weights[component])}
        base.update({f"mean_z_{index + 1}": float(model.global_means[component, index]) for index in range(3)})
        for row_index in range(3):
            for column_index in range(3):
                base[f"cov_z_{row_index + 1}_{column_index + 1}"] = float(model.shared_covariances[component, row_index, column_index])
        output.append(base)
    for environment in sorted(model.environment_weights):
        for component in range(model.config.component_count):
            row = {"scope": "environment", "scope_id": environment, "component": component + 1, "component_weight": float(model.environment_weights[environment][component])}
            row.update({f"mean_z_{index + 1}": float(model.environment_means[environment][component, index]) for index in range(3)})
            output.append(row)
    for cell in sorted(model.cell_weights):
        for component in range(model.config.component_count):
            environment = cell.split("__", 1)[0]
            row = {"scope": "cell", "scope_id": cell, "component": component + 1, "component_weight": float(model.cell_weights[cell][component])}
            row.update({f"mean_z_{index + 1}": float(model.environment_means[environment][component, index]) for index in range(3)})
            output.append(row)
    return output


def summary_from_draws(draws: np.ndarray, rows: Sequence[Mapping[str, Any]], environment: str, band: str) -> dict[str, Any]:
    weights = [float(row["track_weight_recomputed_primary"]) for row in rows]
    return {"environment_class": environment, "elevation_band": band, "cell_id": f"{environment}__{band}", "observation_count": len(rows), "track_count": len({row["track_id"] for row in rows}), "scene_count": len({row["scene_id"] for row in rows}), "sum_weights": sum(weights), "q05_excess_delay_samples": float(np.quantile(np.exp(draws[:, 0]), 0.05)), "q50_excess_delay_samples": float(np.quantile(np.exp(draws[:, 0]), 0.50)), "q95_excess_delay_samples": float(np.quantile(np.exp(draws[:, 0]), 0.95)), "q05_absolute_doppler_hz": float(np.quantile(np.expm1(draws[:, 1]), 0.05)), "q50_absolute_doppler_hz": float(np.quantile(np.expm1(draws[:, 1]), 0.50)), "q95_absolute_doppler_hz": float(np.quantile(np.expm1(draws[:, 1]), 0.95)), "q05_relative_power_db": float(np.quantile(draws[:, 2], 0.05)), "q50_relative_power_db": float(np.quantile(draws[:, 2], 0.50)), "q95_relative_power_db": float(np.quantile(draws[:, 2], 0.95))}


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    output_root = args.output_root.resolve()
    feature_path = output_root / "population/gmm_feature_population.csv"
    selected_path = output_root / "model/selected_conditional_gmm.json"
    candidate_path = output_root / "model/candidate_scores.csv"
    scene_path = output_root / "model/scene_loso_scores.csv"
    bootstrap_path = output_root / "model/scene_bootstrap_model_comparison.csv"
    paired_bootstrap_path = output_root / "model/scene_bootstrap_nlpd_pairs.csv"
    sensitivity_path = output_root / "model/signed_doppler_sensitivity.csv"
    component_path = output_root / "model/cell_component_parameters.csv"
    summary_path = output_root / "model/cell_model_summary.csv"
    draws_path = output_root / "model/review_model_draws.csv"
    manifest_path = output_root / "qa/model_build_manifest.json"
    report_path = output_root / "qa/model_build_report.md"
    output_paths = [selected_path, candidate_path, scene_path, bootstrap_path, paired_bootstrap_path, sensitivity_path, component_path, summary_path, draws_path, manifest_path, report_path]
    if any(path.exists() for path in output_paths) and not args.overwrite:
        raise FileExistsError("model output exists; rerun with --overwrite")
    rows = load_rows(feature_path)
    candidate_keys: list[tuple[int, int, float]] = []
    all_scene_rows: list[dict[str, Any]] = []
    candidate_summaries: list[dict[str, Any]] = []
    if args.reuse_scoring:
        if not candidate_path.exists() or not scene_path.exists():
            raise FileNotFoundError("--reuse-scoring requires existing candidate_scores.csv and scene_loso_scores.csv")
        for raw in read_csv(scene_path):
            row = dict(raw)
            for field in ("candidate_index", "component_count", "test_row_count"):
                row[field] = int(row[field])
            for field in ("pooling_kappa", "test_weight", "weighted_nlpd", "energy_score"):
                row[field] = float(row[field])
            all_scene_rows.append(row)
        for raw in read_csv(candidate_path):
            row = dict(raw)
            for field in ("candidate_index", "component_count", "scene_count"):
                row[field] = int(row[field])
            for field in ("pooling_kappa", "mean_weighted_nlpd", "mean_energy_score", "total_test_weight"):
                row[field] = float(row[field])
            candidate_summaries.append(row)
        candidate_keys = [(int(row["candidate_index"]), int(row["component_count"]), float(row["pooling_kappa"])) for row in candidate_summaries]
    else:
        candidate_index = 0
        for component_count in K_VALUES:
            for pooling_kappa in KAPPA_VALUES:
                candidate_keys.append((candidate_index, component_count, pooling_kappa))
                print(f"fitting candidate {candidate_index}: K={component_count}, kappa={pooling_kappa}")
                all_scene_rows.extend(fit_scene_loso(rows, component_count, pooling_kappa, candidate_index))
                candidate_index += 1
    by_candidate: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in all_scene_rows:
        by_candidate[int(row["candidate_index"])].append(row)
    if not args.reuse_scoring:
        for index, component_count, pooling_kappa in candidate_keys:
            aggregate = aggregate_candidate(by_candidate[index])
            candidate_summaries.append({"candidate_index": index, "component_count": component_count, "pooling_kappa": pooling_kappa, **aggregate})
    bootstrap_rows = bootstrap_comparisons(all_scene_rows, candidate_keys, candidate_summaries, BOOTSTRAP_SEED)
    paired_bootstrap_rows = paired_nlpd_bootstrap(all_scene_rows, candidate_summaries, BOOTSTRAP_SEED)
    selected = select_candidate(candidate_summaries, paired_bootstrap_rows)
    selected_config = model_config(selected["component_count"], selected["pooling_kappa"], BASE_SEED + selected["candidate_index"] * 10000)
    selected_model = CORE.fit_conditional_gmm(rows, selected_config)
    signed_scene_rows = fit_scene_loso(rows, selected["component_count"], selected["pooling_kappa"], selected["candidate_index"], doppler_feature_field="doppler_offset_hz")
    abs_selected_rows = by_candidate[selected["candidate_index"]]
    abs_energy_by_scene = {str(row["held_out_scene"]): float(row["energy_score"]) for row in abs_selected_rows}
    signed_rows: list[dict[str, Any]] = []
    for row in signed_scene_rows:
        scene = str(row["held_out_scene"])
        signed_rows.append({**row, "absolute_primary_energy_score": float(abs_energy_by_scene[scene]), "signed_minus_absolute_energy_score": float(row["energy_score"]) - float(abs_energy_by_scene[scene]), "comparison_status": "SIGNED_SENSITIVITY_ONLY"})
    signed_differences = [float(row["signed_minus_absolute_energy_score"]) for row in signed_rows]
    final_draw_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        for band in BANDS:
            cell_rows = [row for row in rows if row["cell_id"] == f"{environment}__{band}"]
            draws = CORE.sample_conditional(selected_model, environment, band, FINAL_DRAWS, seed=2026083106 + len(summary_rows))
            summary_rows.append(summary_from_draws(draws, cell_rows, environment, band))
            for draw_index, draw in enumerate(draws):
                final_draw_rows.append({"environment_class": environment, "elevation_band": band, "cell_id": f"{environment}__{band}", "draw_index": draw_index, "excess_delay_samples": float(np.exp(draw[0])), "absolute_doppler_hz": float(np.expm1(draw[1])), "relative_power_db": float(draw[2])})
    selected_payload = {
        "model_id": "vtc_stage3_urban_mountain_conditional_partially_pooled_3d_gmm_v1",
        "model_version": "absolute-doppler-conditional-shared-covariance-gmm-v1",
        "status": "BUILT_PENDING_INDEPENDENT_QA",
        "primary_doppler_variable": "absolute_relative_doppler_magnitude_hz",
        "signed_doppler_sensitivity_required": True,
        "selection": selected,
        "population": {"rows": len(rows), "cell_ready_rows": sum(row["cell_ready"] == "1" for row in rows), "missing_elevation_rows": sum(row["cell_ready"] == "0" for row in rows), "track_count": len({row["track_id"] for row in rows}), "scene_count": len(scene_ids(rows))},
        "model": serialize_model(selected_model),
        "signed_sensitivity": {"scene_count": len(signed_rows), "mean_energy_difference_signed_minus_absolute": float(np.mean(signed_differences)), "q025": float(np.quantile(signed_differences, 0.025)), "q975": float(np.quantile(signed_differences, 0.975))},
        "execution_boundary": {"raw_iq_read": False, "matlab_started": False, "sage_started": False, "batch_started": False, "stage4_source_used": False, "formal_manuscript_modified": False, "v1_modified": False, "v2_modified": False, "evidence_matrix_modified": False, "handoff_modified": False},
    }
    write_csv(candidate_path, candidate_summaries, ["candidate_index", "component_count", "pooling_kappa", "scene_count", "mean_weighted_nlpd", "mean_energy_score", "total_test_weight", "status"])
    write_csv(scene_path, all_scene_rows, list(all_scene_rows[0].keys()))
    write_csv(bootstrap_path, bootstrap_rows, list(bootstrap_rows[0].keys()))
    write_csv(paired_bootstrap_path, paired_bootstrap_rows, list(paired_bootstrap_rows[0].keys()))
    write_csv(sensitivity_path, signed_rows, list(signed_rows[0].keys()))
    write_csv(component_path, component_rows(selected_model), list(component_rows(selected_model)[0].keys()))
    write_csv(summary_path, summary_rows, list(summary_rows[0].keys()))
    write_csv(draws_path, final_draw_rows, list(final_draw_rows[0].keys()))
    write_json(selected_path, selected_payload)
    report = "\n".join([
        "# Conditional Partially Pooled 3-D GMM Model-Fit Report",
        "",
        f"Status: `{selected_payload['status']}`",
        f"Selected K: `{selected['component_count']}`",
        f"Selected pooling kappa: `{selected['pooling_kappa']}`",
        f"Primary Doppler variable: `{selected_payload['primary_doppler_variable']}`",
        "",
        "The model uses shared component covariances, environment-specific means, and environment--elevation mixture weights with partial pooling. The global model is a regularization parent and is not an all-path paper conclusion.",
        "",
        f"Scene-LOSO selected mean weighted NLPD: `{selected['mean_weighted_nlpd']:.6g}`",
        f"Scene-LOSO selected mean energy score: `{selected['mean_energy_score']:.6g}`",
        f"Signed-minus-absolute energy difference across selected-fold sensitivity: mean `{selected_payload['signed_sensitivity']['mean_energy_difference_signed_minus_absolute']:.6g}`, 95% empirical interval `[{selected_payload['signed_sensitivity']['q025']:.6g}, {selected_payload['signed_sensitivity']['q975']:.6g}]`.",
        "",
        "The signed sensitivity remains an internal decision gate. A GMM component is not assigned a reflector or physical propagation identity. The model is not a complete stochastic channel model.",
        "",
        "Execution boundary: raw IQ, MATLAB, SAGE, batch, Stage4 sources, formal manuscript, figures, tables, Evidence Matrix, and handoffs were not modified.",
        "",
    ])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    manifest = {
        "model_build_id": "vtc_stage3_urban_mountain_conditional_gmm_fit_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_feature_population_sha256": sha256_file(feature_path),
        "candidate_grid": {"K": list(K_VALUES), "kappa": list(KAPPA_VALUES)},
        "scene_loso_scene_count": len(scene_ids(rows)),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "paired_bootstrap_rows": len(paired_bootstrap_rows),
        "scoring_draws_per_scope": SCORING_DRAWS,
        "final_draws_per_cell": FINAL_DRAWS,
        "selected_model_sha256": sha256_file(selected_path),
        "execution_boundary": selected_payload["execution_boundary"],
    }
    write_json(manifest_path, manifest)
    print(json.dumps({"status": "PASS_BUILD_PENDING_QA", "selected": selected, "signed_sensitivity": selected_payload["signed_sensitivity"], "candidate_count": len(candidate_summaries), "scene_loso_rows": len(all_scene_rows), "bootstrap_rows": len(bootstrap_rows), "final_draw_rows": len(final_draw_rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
