#!/usr/bin/env python3
"""Audit signed relative Doppler symmetry and freeze the magnitude transform."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[5]
LOCAL_DEPS = PROJECT_ROOT / "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v1/.python_deps"
if LOCAL_DEPS.is_dir() and str(LOCAL_DEPS) not in sys.path:
    sys.path.insert(0, str(LOCAL_DEPS))


ENVIRONMENTS = ("Urban", "Mountain/Valley")
BANDS = ("LOW", "MID", "HIGH")
PARAMETER = "doppler_offset_hz"
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 2026083103
LATTICE_MODES = np.asarray(
    [-100.335697904715, -50.335697904715, 49.664302095285, 99.664302095285],
    dtype=float,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
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
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def absolute_doppler(values: Sequence[float] | np.ndarray) -> np.ndarray:
    return np.abs(np.asarray(values, dtype=float))


def weighted_quantile(values: Sequence[float], weights: Sequence[float], probability: float) -> float:
    values_array = np.asarray(values, dtype=float)
    weights_array = np.asarray(weights, dtype=float)
    if values_array.size == 0 or values_array.size != weights_array.size:
        raise ValueError("values and weights must have equal nonzero length")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    order = np.argsort(values_array, kind="mergesort")
    sorted_values = values_array[order]
    sorted_weights = weights_array[order]
    cumulative = np.cumsum(sorted_weights)
    threshold = probability * cumulative[-1]
    index = int(np.searchsorted(cumulative, threshold, side="left"))
    return float(sorted_values[min(index, sorted_values.size - 1)])


def weighted_mirror_distance(values: Sequence[float], weights: Sequence[float]) -> float:
    """Return the sup norm between an empirical CDF and its reflected CDF."""
    values_array = np.asarray(values, dtype=float)
    weights_array = np.asarray(weights, dtype=float)
    if values_array.size == 0 or values_array.size != weights_array.size:
        raise ValueError("values and weights must have equal nonzero length")
    total = float(np.sum(weights_array))
    if total <= 0.0:
        raise ValueError("weights must have positive total")
    grid = np.unique(np.concatenate((values_array, -values_array)))
    distance = 0.0
    for x_value in grid:
        cdf_at_x = float(np.sum(weights_array[values_array <= x_value]) / total)
        reflected_cdf = float(1.0 - np.sum(weights_array[values_array < -x_value]) / total)
        distance = max(distance, abs(cdf_at_x - reflected_cdf))
    return float(distance)


def scope_rows(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str, list[Mapping[str, Any]]]]:
    scopes: list[tuple[str, str, list[Mapping[str, Any]]]] = [("global", "global", list(rows))]
    for environment in ENVIRONMENTS:
        environment_rows = [row for row in rows if row["environment_class"] == environment]
        scopes.append(("environment", environment, environment_rows))
        for band in BANDS:
            scopes.append(("cell", f"{environment}__{band}", [row for row in environment_rows if row.get("elevation_band") == band]))
    return scopes


def summarize_scope(scope: str, scope_id: str, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = np.asarray([float(row[PARAMETER]) for row in rows], dtype=float)
    weights = np.asarray([float(row["track_weight_recomputed_primary"]) for row in rows], dtype=float)
    if values.size == 0:
        raise ValueError(f"empty scope: {scope}/{scope_id}")
    total = float(np.sum(weights))
    positive_mass = float(np.sum(weights[values > 0.0]) / total)
    negative_mass = float(np.sum(weights[values < 0.0]) / total)
    zero_mass = float(np.sum(weights[values == 0.0]) / total)
    return {
        "scope": scope,
        "scope_id": scope_id,
        "observation_count": int(values.size),
        "track_count": len({row["track_id"] for row in rows}),
        "run_count": len({row["run_id"] for row in rows}),
        "scene_count": len({row["scene_id"] for row in rows}),
        "sum_weights": total,
        "kish_effective_sample_size": float(total * total / np.sum(weights * weights)),
        "positive_weight_mass": positive_mass,
        "negative_weight_mass": negative_mass,
        "zero_weight_mass": zero_mass,
        "sign_mass_imbalance": float(positive_mass - negative_mass),
        "weighted_mean_hz": float(np.sum(values * weights) / total),
        "weighted_median_hz": weighted_quantile(values, weights, 0.5),
        "q025_hz": weighted_quantile(values, weights, 0.025),
        "q25_hz": weighted_quantile(values, weights, 0.25),
        "q75_hz": weighted_quantile(values, weights, 0.75),
        "q975_hz": weighted_quantile(values, weights, 0.975),
        "weighted_mirror_cdf_distance": weighted_mirror_distance(values, weights),
        "absolute_mean_hz": float(np.sum(absolute_doppler(values) * weights) / total),
        "absolute_median_hz": weighted_quantile(absolute_doppler(values), weights, 0.5),
        "four_mode_count": int(np.sum(np.min(np.abs(values[:, None] - LATTICE_MODES[None, :]), axis=1) <= 1e-6)),
        "coarse_grid_candidate_count": int(sum(row.get("doppler_provenance_class") in {"COARSE_GRID_LOCK_CANDIDATE", "BOUNDARY_SATURATION_CANDIDATE"} for row in rows)),
    }


def bootstrap_scope(scope: str, scope_id: str, rows: Sequence[Mapping[str, Any]], rng: np.random.Generator) -> list[dict[str, Any]]:
    by_scene: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_scene[row["scene_id"]].append(row)
    scene_ids = sorted(by_scene)
    output: list[dict[str, Any]] = []
    for replicate in range(BOOTSTRAP_REPLICATES):
        sampled_ids = rng.choice(scene_ids, size=len(scene_ids), replace=True)
        sampled_rows = [row for scene_id in sampled_ids for row in by_scene[str(scene_id)]]
        summary = summarize_scope(scope, scope_id, sampled_rows)
        output.append(
            {
                "scope": scope,
                "scope_id": scope_id,
                "replicate": replicate,
                "weighted_mean_hz": summary["weighted_mean_hz"],
                "sign_mass_imbalance": summary["sign_mass_imbalance"],
                "weighted_mirror_cdf_distance": summary["weighted_mirror_cdf_distance"],
                "absolute_median_hz": summary["absolute_median_hz"],
            }
        )
    return output


def load_rows(path: Path) -> list[dict[str, Any]]:
    raw_rows = read_csv(path)
    if len(raw_rows) != 518:
        raise ValueError(f"expected 518 primary rows, got {len(raw_rows)}")
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        row = dict(raw)
        row[PARAMETER] = float(raw[PARAMETER])
        row["track_weight_recomputed_primary"] = float(raw["track_weight_recomputed_primary"])
        rows.append(row)
    if sum(row.get("elevation_ready") == "1" for row in rows) != 487:
        raise ValueError("elevation-ready count changed")
    return rows


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    output_root = args.output_root.resolve()
    # Resolve from the supplied project root rather than relying on v3 depth.
    population_path = project_root / "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/population/population_primary_admitted.csv"
    summary_path = output_root / "diagnostics/doppler_symmetry_by_scope.csv"
    bootstrap_path = output_root / "diagnostics/doppler_symmetry_scene_bootstrap.csv"
    decision_path = output_root / "diagnostics/doppler_transform_decision.json"
    existing = [path for path in (summary_path, bootstrap_path, decision_path) if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError("diagnostic output exists; rerun with --overwrite")
    rows = load_rows(population_path)
    summaries: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    for scope, scope_id, scoped_rows in scope_rows(rows):
        summaries.append(summarize_scope(scope, scope_id, scoped_rows))
        bootstrap_rows.extend(bootstrap_scope(scope, scope_id, scoped_rows, rng))
    write_csv(summary_path, summaries, list(summaries[0].keys()))
    write_csv(bootstrap_path, bootstrap_rows, list(bootstrap_rows[0].keys()))
    decision = {
        "diagnostic_id": "vtc_stage3_urban_mountain_doppler_symmetry_v1",
        "status": "PRIMARY_MAGNITUDE_TRANSFORM_WITH_SIGNED_SENSITIVITY",
        "primary_model_variable": "absolute_relative_doppler_magnitude_hz",
        "source_field_preserved": PARAMETER,
        "transform": "log1p(abs(doppler_offset_hz)/1Hz)",
        "physical_symmetry_claim": False,
        "signed_sensitivity_required": True,
        "stop_if_signed_sensitivity_stably_better": True,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "counts": {"primary_rows": len(rows), "elevation_ready_rows": sum(row.get("elevation_ready") == "1" for row in rows), "missing_elevation_rows": sum(row.get("elevation_ready") != "1" for row in rows), "scope_rows": len(summaries)},
        "execution_boundary": {"raw_iq_read": False, "matlab_started": False, "sage_started": False, "batch_started": False, "stage4_source_used": False, "formal_manuscript_modified": False, "v1_modified": False, "v2_modified": False, "evidence_matrix_modified": False, "handoff_modified": False},
    }
    write_json(decision_path, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
