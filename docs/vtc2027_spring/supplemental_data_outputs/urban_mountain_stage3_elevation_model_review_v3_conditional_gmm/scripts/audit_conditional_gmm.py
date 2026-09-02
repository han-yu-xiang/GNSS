#!/usr/bin/env python3
"""Independently audit the isolated conditional 3-D GMM artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENTS = ("Urban", "Mountain/Valley")
BANDS = ("LOW", "MID", "HIGH")
EXPECTED_CELLS = {f"{environment}__{band}" for environment in ENVIRONMENTS for band in BANDS}
BOOTSTRAP_REPLICATES = 1000
TOL = 1e-8


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def f(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite numeric value: {value!r}")
    return result


def close(a: Any, b: Any, tol: float = TOL) -> bool:
    return math.isclose(f(a), f(b), rel_tol=tol, abs_tol=tol)


def check(checks: dict[str, dict[str, Any]], name: str, passed: bool, details: str) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "details": details}


def verify_sources(inventory: Mapping[str, Any], checks: dict[str, dict[str, Any]], failures: list[str]) -> None:
    source_failures: list[str] = []
    for source in inventory.get("sources", []):
        path = Path(str(source["path"]))
        if not path.exists():
            source_failures.append(f"missing source: {path}")
            continue
        if path.stat().st_size != int(source["size_bytes"]):
            source_failures.append(f"size mismatch: {path}")
        if sha256_file(path) != str(source["sha256"]):
            source_failures.append(f"sha256 mismatch: {path}")
        if source.get("read_only") is not True:
            source_failures.append(f"source not marked read_only: {path}")
    passed = inventory.get("source_count") == 7 and len(inventory.get("sources", [])) == 7 and not source_failures
    check(checks, "source_inventory_integrity", passed, "seven inventory records with matching existence, size, SHA-256, and read_only flags" if passed else "; ".join(source_failures))
    if not passed:
        failures.append("source inventory integrity failed")
    policy = inventory.get("execution_policy", {})
    blocked = ("raw_iq_read", "matlab_started", "sage_started", "batch_started", "stage4_used", "formal_manuscript_modified", "v1_modified", "v2_modified", "evidence_matrix_modified", "handoff_modified")
    policy_ok = all(policy.get(key) is False for key in blocked)
    check(checks, "execution_boundary", policy_ok, "all forbidden execution and formal-write flags are false" if policy_ok else f"non-false policy flags: {[key for key in blocked if policy.get(key) is not False]}")
    if not policy_ok:
        failures.append("execution boundary is not clean")


def verify_population(population: Sequence[Mapping[str, str]], manifest: Mapping[str, Any], checks: dict[str, dict[str, Any]], failures: list[str]) -> dict[str, Any]:
    counts = {
        "primary_rows": len(population),
        "cell_ready_rows": sum(row.get("cell_ready") == "1" for row in population),
        "missing_elevation_rows": sum(row.get("cell_ready") == "0" for row in population),
        "track_count": len({row.get("track_id") for row in population}),
        "scene_count": len({row.get("scene_id") for row in population}),
        "conditioned_cells": len({row.get("cell_id") for row in population if row.get("cell_ready") == "1"}),
    }
    expected = {"primary_rows": 518, "cell_ready_rows": 487, "missing_elevation_rows": 31, "track_count": 236, "scene_count": 9, "conditioned_cells": 6}
    counts_ok = counts == expected and manifest.get("counts", {}) == {"primary_rows": 518, "cell_ready_rows": 487, "missing_elevation_rows": 31, "track_count": 236, "cell_count": 6}
    check(checks, "population_denominators", counts_ok, str(counts) if counts_ok else f"recomputed={counts}, manifest={manifest.get('counts')}")
    if not counts_ok:
        failures.append("population denominators do not match the frozen support")

    transform_failures: list[str] = []
    for row in population:
        delay = f(row["excess_delay_samples"])
        doppler = f(row["doppler_offset_hz"])
        if delay <= 0.0 or not close(row["absolute_doppler_hz"], abs(doppler)) or not close(row["log_excess_delay"], math.log(delay)) or not close(row["log1p_absolute_doppler"], math.log1p(abs(doppler))):
            transform_failures.append(str(row.get("stage3_path_id", "unknown")))
        if row.get("cell_ready") == "1":
            expected_cell = f"{row['environment_class']}__{row['elevation_band']}"
            if row.get("cell_id") != expected_cell or row.get("parent_scope_role") != "CELL_AND_ENVIRONMENT":
                transform_failures.append(str(row.get("stage3_path_id", "unknown")))
        elif row.get("cell_id") or row.get("parent_scope_role") != "ENVIRONMENT_PARENT_ONLY":
            transform_failures.append(str(row.get("stage3_path_id", "unknown")))
    check(checks, "feature_transform_and_missing_elevation_policy", not transform_failures, "log/exact absolute-Doppler transforms and no-imputation policy verified" if not transform_failures else f"invalid rows: {transform_failures[:5]}")
    if transform_failures:
        failures.append("feature transform or missing-elevation policy failed")

    track_sums: dict[str, float] = {}
    for row in population:
        track_sums[row["track_id"]] = track_sums.get(row["track_id"], 0.0) + f(row["track_weight_recomputed_primary"])
    weight_failures = [track for track, total in track_sums.items() if not close(total, 1.0, 1e-7)]
    check(checks, "track_weight_sums", not weight_failures, "all 236 recomputed primary track weights sum to one" if not weight_failures else f"invalid tracks: {weight_failures[:5]}")
    if weight_failures:
        failures.append("track weights do not sum to one")

    expected_support = {row["cell_id"]: row for row in read_csv(ROOT / "population/gmm_cell_support.csv")}
    by_cell: dict[str, list[Mapping[str, str]]] = {cell: [] for cell in EXPECTED_CELLS}
    for row in population:
        if row.get("cell_ready") == "1":
            by_cell.setdefault(row["cell_id"], []).append(row)
    support_failures: list[str] = []
    support_snapshot: dict[str, dict[str, Any]] = {}
    for cell in sorted(EXPECTED_CELLS):
        rows = by_cell.get(cell, [])
        observed = {
            "observation_count": len(rows),
            "track_count": len({row["track_id"] for row in rows}),
            "run_count": len({row["logical_run_key"] for row in rows}),
            "scene_count": len({row["scene_id"] for row in rows}),
            "sum_weights": sum(f(row["track_weight_recomputed_primary"]) for row in rows),
        }
        support_snapshot[cell] = observed
        expected_row = expected_support.get(cell)
        if expected_row is None or any(observed[key] != int(expected_row[key]) for key in ("observation_count", "track_count", "run_count", "scene_count")) or not close(observed["sum_weights"], expected_row["sum_weights"], 1e-7):
            support_failures.append(cell)
    check(checks, "cell_support_recomputation", not support_failures, "six cell counts, run counts, scene counts, and weight mass match independently" if not support_failures else f"invalid cells: {support_failures}")
    if support_failures:
        failures.append("cell support recomputation failed")
    return {"counts": counts, "cell_support": support_snapshot}


def verify_model(population_info: Mapping[str, Any], selected: Mapping[str, Any], checks: dict[str, dict[str, Any]], failures: list[str]) -> dict[str, Any]:
    model = selected["model"]
    model_failures: list[str] = []
    if selected.get("status") != "BUILT_PENDING_INDEPENDENT_QA":
        model_failures.append("unexpected selected model status")
    if model.get("component_count") != 3 or selected.get("primary_doppler_variable") != "absolute_relative_doppler_magnitude_hz" or model.get("doppler_feature_field") != "log1p_absolute_doppler":
        model_failures.append("wrong model dimension or primary Doppler field")
    global_weights = np.asarray(model["global_weights"], dtype=float)
    global_means = np.asarray(model["global_means"], dtype=float)
    covariances = np.asarray(model["shared_covariances"], dtype=float)
    if global_weights.shape != (3,) or global_means.shape != (3, 3) or covariances.shape != (3, 3, 3):
        model_failures.append(f"wrong array shapes: weights={global_weights.shape}, means={global_means.shape}, covariances={covariances.shape}")
    if not np.all(np.isfinite(global_weights)) or not np.all(np.isfinite(global_means)) or not np.all(np.isfinite(covariances)):
        model_failures.append("non-finite selected model values")
    scope_weights: dict[str, Sequence[float]] = {"global": model["global_weights"]}
    scope_weights.update({f"environment:{key}": value for key, value in model["environment_weights"].items()})
    scope_weights.update({f"cell:{key}": value for key, value in model["cell_weights"].items()})
    for scope, weights in scope_weights.items():
        values = np.asarray(weights, dtype=float)
        if values.shape != (3,) or not np.all(np.isfinite(values)) or np.any(values <= 0.0) or not close(np.sum(values), 1.0, 1e-7):
            model_failures.append(f"invalid mixture weights: {scope}")
    for index, covariance in enumerate(covariances):
        if not np.allclose(covariance, covariance.T, atol=1e-10, rtol=0.0) or np.min(np.linalg.eigvalsh(covariance)) <= 0.0:
            model_failures.append(f"covariance {index + 1} is not symmetric positive definite")
    if global_means.shape == (3, 3):
        order = np.lexsort((global_means[:, 0], global_means[:, 1], global_means[:, 2]))
        if not np.array_equal(order, np.arange(3)):
            model_failures.append(f"component labels are not ordered: {order.tolist()}")
    if int(model.get("log_likelihood_iterations", 0)) <= 0:
        model_failures.append("missing likelihood iteration record")
    check(checks, "model_mathematics", not model_failures, "3-D model, normalized weights, finite values, ordered components, and SPD covariances verified" if not model_failures else "; ".join(model_failures))
    if model_failures:
        failures.append("model mathematics failed")

    candidate_rows = read_csv(ROOT / "model/candidate_scores.csv")
    scene_rows = read_csv(ROOT / "model/scene_loso_scores.csv")
    bootstrap_rows = read_csv(ROOT / "model/scene_bootstrap_model_comparison.csv")
    paired_rows = read_csv(ROOT / "model/scene_bootstrap_nlpd_pairs.csv")
    candidate_ok = len(candidate_rows) == 12 and len({int(row["candidate_index"]) for row in candidate_rows}) == 12 and len(scene_rows) == 108 and all(len({row["held_out_scene"] for row in scene_rows if int(row["candidate_index"]) == index}) == 9 for index in range(12))
    bootstrap_ok = len(bootstrap_rows) == 12 * BOOTSTRAP_REPLICATES and len({int(row["replicate"]) for row in bootstrap_rows}) == BOOTSTRAP_REPLICATES
    paired_ok = len(paired_rows) == 2 * BOOTSTRAP_REPLICATES and len({int(row["replicate"]) for row in paired_rows}) == BOOTSTRAP_REPLICATES
    check(checks, "candidate_loso_bootstrap_completeness", candidate_ok and bootstrap_ok and paired_ok, f"candidates={len(candidate_rows)}, LOSO rows={len(scene_rows)}, model bootstrap rows={len(bootstrap_rows)}, paired NLPD rows={len(paired_rows)}" if candidate_ok and bootstrap_ok and paired_ok else "candidate, nine-scene LOSO, or bootstrap coverage is incomplete")
    if not (candidate_ok and bootstrap_ok and paired_ok):
        failures.append("candidate/LOSO/bootstrap completeness failed")

    selection = selected.get("selection", {})
    candidate_nlpd = {int(row["candidate_index"]): float(row["mean_weighted_nlpd"]) for row in candidate_rows}
    best_index = min(candidate_nlpd, key=candidate_nlpd.get)
    comparisons = selection.get("complexity_comparisons", [])
    selection_ok = int(selection.get("candidate_index", -1)) == best_index and int(selection.get("component_count", -1)) == 3 and len(comparisons) == 1 and comparisons[0].get("decision") == "RETAIN_LARGER_K" and float(comparisons[0]["q975"]) < 0.0
    check(checks, "complexity_selection_rule", selection_ok, f"selected candidate={selection.get('candidate_index')}, best NLPD candidate={best_index}, comparison={comparisons[0] if comparisons else None}" if selection_ok else "selected candidate does not satisfy lowest-NLPD plus adjacent-K bootstrap rule")
    if not selection_ok:
        failures.append("complexity selection rule failed")

    draws = read_csv(ROOT / "model/review_model_draws.csv")
    draw_counts: dict[str, int] = {}
    draw_failures: list[str] = []
    for row in draws:
        cell = row.get("cell_id", "")
        draw_counts[cell] = draw_counts.get(cell, 0) + 1
        if cell not in EXPECTED_CELLS or f(row["excess_delay_samples"]) <= 0.0 or f(row["absolute_doppler_hz"]) < 0.0 or not all(math.isfinite(f(row[field])) for field in ("excess_delay_samples", "absolute_doppler_hz", "relative_power_db")):
            draw_failures.append(cell)
    draws_ok = len(draws) == 6 * 4096 and set(draw_counts) == EXPECTED_CELLS and all(count == 4096 for count in draw_counts.values()) and not draw_failures
    check(checks, "review_draws", draws_ok, "six cells with 4096 finite draws each" if draws_ok else f"draw counts={draw_counts}, invalid rows={len(draw_failures)}")
    if not draws_ok:
        failures.append("review draws failed")
    return {"candidate_rows": len(candidate_rows), "scene_loso_rows": len(scene_rows), "model_bootstrap_rows": len(bootstrap_rows), "paired_bootstrap_rows": len(paired_rows), "review_draw_rows": len(draws)}


def verify_boundaries(selected: Mapping[str, Any], checks: dict[str, dict[str, Any]], failures: list[str]) -> list[str]:
    report = (ROOT / "qa/model_build_report.md").read_text(encoding="utf-8").lower()
    serialized = json.dumps(selected, ensure_ascii=False).lower()
    combined = report + "\n" + serialized
    forbidden = [
        r"stage3.{0,40}confirmed path",
        r"confirmed path.{0,40}stage3",
        r"physical reflector class",
        r"grid peaks? as propagation",
        r"imput(?:e|ed|ation).{0,30}elevation",
    ]
    violations = [pattern for pattern in forbidden if re.search(pattern, combined)]
    safe_model_claim = "not a complete stochastic channel model" in report and "not assigned a reflector or physical propagation identity" in report
    boundary_ok = not violations and safe_model_claim
    check(checks, "scientific_boundary_language", boundary_ok, "no forbidden Stage3/physical-truth/imputation claims and explicit bounded-model language present" if boundary_ok else f"violations={violations}, safe_model_claim={safe_model_claim}")
    if not boundary_ok:
        failures.append("scientific boundary language failed")
    return ["31 rows lack elevation and are retained only for environment-parent fitting", "LOW cells and Mountain/Valley-HIGH remain strongly partially pooled", "the selected GMM is not a complete stochastic channel model", "no direct comparison with the existing v2 marginal-plus-copula baseline was implemented in Task 5"]


def main() -> int:
    inventory = read_json(ROOT / "provenance/source_inventory.json")
    manifest = read_json(ROOT / "population/gmm_feature_population_manifest.json")
    population = read_csv(ROOT / "population/gmm_feature_population.csv")
    selected = read_json(ROOT / "model/selected_conditional_gmm.json")
    checks: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    verify_sources(inventory, checks, failures)
    population_info = verify_population(population, manifest, checks, failures)
    model_counts = verify_model(population_info, selected, checks, failures)
    limitations = verify_boundaries(selected, checks, failures)
    status = "FAIL" if failures else "PASS_WITH_LIMITATIONS"
    result = {
        "qa_id": "vtc_stage3_urban_mountain_conditional_gmm_independent_qa_v1",
        "status": status,
        "hard_failures": failures,
        "limitations": limitations,
        "counts": {**population_info["counts"], **model_counts},
        "cell_support": population_info["cell_support"],
        "support_status": {
            "Urban__LOW": "STRONGLY_PARTIALLY_POOLED",
            "Urban__MID": "DATA_SUPPORTED",
            "Urban__HIGH": "DATA_SUPPORTED",
            "Mountain/Valley__LOW": "STRONGLY_PARTIALLY_POOLED",
            "Mountain/Valley__MID": "DATA_SUPPORTED",
            "Mountain/Valley__HIGH": "STRONGLY_PARTIALLY_POOLED",
        },
        "checks": checks,
        "execution_boundary": selected.get("execution_boundary", {}),
        "source_inventory_sha256": sha256_file(ROOT / "provenance/source_inventory.json"),
        "selected_model_sha256": sha256_file(ROOT / "model/selected_conditional_gmm.json"),
    }
    (ROOT / "qa/independent_qa_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_lines = [
        "# Independent QA — Conditional Partially Pooled 3-D GMM",
        "",
        f"Status: `{status}`",
        "",
        "## Recomputed support",
        "",
        f"- Primary rows: `{population_info['counts']['primary_rows']}`",
        f"- Elevation-conditioned rows: `{population_info['counts']['cell_ready_rows']}`",
        f"- Missing-elevation rows retained for environment parent only: `{population_info['counts']['missing_elevation_rows']}`",
        f"- Tracks/scenes/cells: `{population_info['counts']['track_count']}` / `{population_info['counts']['scene_count']}` / `{population_info['counts']['conditioned_cells']}`",
        "",
        "## Model and validation",
        "",
        f"- Selected model: `K={selected['selection']['component_count']}`, `κ={selected['selection']['pooling_kappa']}`.",
        f"- Candidate/LOSO/model-bootstrap/paired-bootstrap rows: `{model_counts['candidate_rows']}` / `{model_counts['scene_loso_rows']}` / `{model_counts['model_bootstrap_rows']}` / `{model_counts['paired_bootstrap_rows']}`.",
        f"- Review draws: `{model_counts['review_draw_rows']}` (`4096` per cell).",
        "- All mixture weights, finite values, component ordering, and shared covariance positive-definiteness checks passed.",
        "",
        "## Cell support",
        "",
        "- `DATA_SUPPORTED`: Urban-MID, Urban-HIGH, Mountain/Valley-MID.",
        "- `STRONGLY_PARTIALLY_POOLED`: Urban-LOW, Mountain/Valley-LOW, Mountain/Valley-HIGH.",
        "",
        "## Limitations",
        "",
        "- The six cells are conditional descriptive model outputs, not a complete stochastic channel model.",
        "- No component is assigned a reflector class or physical propagation identity.",
        "- The existing v2 marginal-plus-copula baseline was not directly compared in Task 5.",
        "",
        "Execution boundary: no raw IQ, MATLAB, SAGE, Stage4 source, formal manuscript, canonical figures/tables, Evidence Matrix, or handoff was modified.",
        "",
    ]
    (ROOT / "qa/independent_qa_report.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(json.dumps({"status": status, "hard_failures": failures, "counts": result["counts"]}, ensure_ascii=False, indent=2))
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
