"""Run bounded WP2 robustness diagnostics on pinned V0 CSV extracts only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mainline_stage2_v0 as v0  # noqa: E402
from mainline_stage2_wp2 import (  # noqa: E402
    DEFAULT_SCOPES,
    evaluate_power_delay_loso,
    evaluate_selected_count_loso,
    marginal_stability_rows,
    tail_calibration_rows,
    _validated_selected_windows,
)


PRIVATE_ROOT = ROOT / "dataset_generation_logs/channel_modeling/mainline_1023_stage2_v0_20261024T132210Z"
REPORT_ROOT = ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1/v0_20261024T132210Z"
DEFAULT_MPC = PRIVATE_ROOT / "analysis_mpc_rows.csv"
DEFAULT_WINDOWS = PRIVATE_ROOT / "selected_window_rows.csv"
DEFAULT_FOLDS = REPORT_ROOT / "scene_fold_scores.csv"
PRIVATE_MANIFEST = PRIVATE_ROOT / "artifact_manifest.json"
FOLD_MANIFEST = REPORT_ROOT / "runtime_artifact_manifest.json"
DEFAULT_OUTPUT_PARENT = ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1"

EXPECTED_INPUT_SHA256 = {
    "analysis_mpc_rows.csv": "a2c26d0de655e0f6cf4a60cf2906bf4cfff7aa16bbc5f74bffb4e9b80dab306c",
    "selected_window_rows.csv": "fbc784ff169fca6d95907e39a56510d9be0b61ec3c1ef42e15235002be40061c",
    "scene_fold_scores.csv": "faad49468cb7d36ed070e54a8b9fdc564cdaa9bc3f682fed1eb391cfebbf03ca",
}
EXPECTED_POPULATION = {
    "mpc_n": 8914,
    "selected_window_n": 7847,
    "run_n": 83,
    "scene_n": 13,
    "mpc_count_histogram": {"0": 3574, "1": 1412, "2": 1081, "3": 1780},
}
OUTPUT_TABLES = (
    "marginal_stability_by_fold.csv",
    "marginal_stability_summary.csv",
    "tail_calibration_by_scene.csv",
    "tail_calibration_summary.csv",
    "power_delay_loso_by_scene.csv",
    "power_delay_loso_summary.csv",
    "selected_count_loso_by_scene.csv",
    "selected_count_loso_summary.csv",
)
FORBIDDEN_OUTPUT_FIELDS = {
    "run_id", "window_id", "path_id", "latitude", "longitude", "elevation_deg",
    "receiver_height_m", "receiver_position", "source_record_id",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _verify_manifest_entry(manifest_path: Path | None, name: str, expected_hash: str) -> None:
    if manifest_path is None:
        return
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = document.get(name)
    if not isinstance(record, dict) or record.get("sha256") != expected_hash:
        raise ValueError(f"input artifact manifest does not pin {name} to the expected SHA256")


def _require_hashes(paths: Mapping[str, Path], expected_hashes: Mapping[str, str],
                    private_manifest: Path | None, fold_manifest: Path | None) -> dict[str, dict[str, Any]]:
    if set(paths) != set(expected_hashes):
        raise ValueError("expected SHA256 mapping must name exactly the three pinned inputs")
    verified: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256_file(path)
        if actual != expected_hashes[name]:
            raise ValueError(f"pinned input SHA256 mismatch for {name}: {actual}")
        owner = private_manifest if name != "scene_fold_scores.csv" else fold_manifest
        _verify_manifest_entry(owner, name, actual)
        verified[name] = {"path": _display_path(path), "sha256": actual, "size_bytes": path.stat().st_size}
    return verified


def _validate_fold_coverage(mpc: pd.DataFrame, folds: pd.DataFrame,
                            scopes: tuple[str, ...], variables: Mapping[str, list[str]]) -> None:
    scoped_folds = folds[folds.scope.astype(str).isin(scopes)]
    expected: set[tuple[str, str, str, str]] = set()
    for scope in scopes:
        group = mpc if scope == "GLOBAL" else mpc[mpc.environment_class.astype(str) == scope.removeprefix("ENV:")]
        scenes = sorted(group.scene_id.astype(str).unique())
        for scene in scenes:
            for variable, families in variables.items():
                for family in families:
                    expected.add((scope, scene, variable, family))
    actual = set(zip(scoped_folds.scope.astype(str), scoped_folds.held_out_scene_id.astype(str),
                     scoped_folds.variable.astype(str), scoped_folds.family.astype(str)))
    if actual != expected:
        missing = len(expected - actual)
        extra = len(actual - expected)
        raise ValueError(f"saved V0 fold coverage differs from the declared contract (missing={missing}, extra={extra})")
    for (scope, scene, variable, _), group in scoped_folds.groupby(
        ["scope", "held_out_scene_id", "variable", "family"], sort=False
    ):
        source = mpc if scope == "GLOBAL" else mpc[mpc.environment_class.astype(str) == str(scope).removeprefix("ENV:")]
        test = source[source.scene_id.astype(str) == str(scene)]
        values = pd.to_numeric(test[variable], errors="coerce")
        finite_n = int(pd.Series(values).map(lambda value: math.isfinite(float(value)) if pd.notna(value) else False).sum())
        if not group.test_n.astype(int).eq(len(test)).all() or not group.finite_test_n.astype(int).eq(finite_n).all():
            raise ValueError(f"saved V0 fold test support disagrees with pinned MPC rows: {scope}/{scene}/{variable}")
        if not group.train_scene_n.astype(int).eq(source.scene_id.nunique() - 1).all():
            raise ValueError(f"saved V0 training scene count mismatch: {scope}/{scene}/{variable}")


def _validate_population(mpc: pd.DataFrame, windows: pd.DataFrame,
                         expected: Mapping[str, Any] | None) -> tuple[pd.DataFrame, dict[str, Any]]:
    required_mpc = {"run_id", "window_id", "scene_id", "environment_class", "path_id",
                    "is_multipath", "excess_delay_chips", "doppler_offset_hz", "relative_power_db"}
    missing = required_mpc - set(mpc.columns)
    if missing:
        raise ValueError("pinned MPC extract missing columns: " + ",".join(sorted(missing)))
    required_identity = ["run_id", "window_id", "scene_id", "environment_class", "path_id", "is_multipath"]
    if mpc[required_identity].isna().any().any():
        raise ValueError("pinned MPC extract has missing identity fields")
    if not pd.to_numeric(mpc.is_multipath, errors="coerce").eq(1).all():
        raise ValueError("analysis_mpc_rows.csv must contain only MPC path records")
    if mpc.duplicated(["run_id", "window_id", "path_id"]).any():
        raise ValueError("duplicate (run_id, window_id, path_id) MPC identity")
    path_ids = pd.to_numeric(mpc.path_id, errors="coerce").to_numpy(dtype=float)
    if not pd.notna(path_ids).all() or (path_ids % 1 != 0).any() or (path_ids < 1).any():
        raise ValueError("path_id must be a positive integer identity")
    selected = _validated_selected_windows(windows)
    mpc = mpc.copy()
    for column in ("run_id", "window_id", "scene_id"):
        mpc[column] = mpc[column].astype(str)
    if set(mpc.run_id) - set(selected.run_id) or set(mpc.scene_id) - set(selected.scene_id):
        raise ValueError("MPC identity contains a run or scene absent from selected-window ledger")
    run_scene = selected.groupby("run_id").scene_id.first().to_dict()
    if any(run_scene.get(run) != scene for run, scene in mpc[["run_id", "scene_id"]].drop_duplicates().itertuples(index=False, name=None)):
        raise ValueError("MPC run-to-scene identity disagrees with selected-window ledger")
    selected_keys = set(zip(selected.run_id, selected.window_id))
    mpc_keys = list(zip(mpc.run_id, mpc.window_id))
    if not set(mpc_keys).issubset(selected_keys):
        raise ValueError("MPC path identity is not a subset of Stage2-selected windows")
    observed_counts = mpc.groupby(["run_id", "window_id"]).size().to_dict()
    derived_counts = [int(observed_counts.get(key, 0)) for key in zip(selected.run_id, selected.window_id)]
    if derived_counts != selected.mpc_count.astype(int).tolist():
        raise ValueError("selected-window MPC counts disagree with path-level identities")
    if len(mpc) != len(set(mpc_keys)) and mpc[["run_id", "window_id", "path_id"]].duplicated().any():
        raise ValueError("duplicate MPC path identity")
    histogram = {str(value): int((selected.mpc_count == value).sum()) for value in range(4)}
    population = dict(mpc_n=len(mpc), selected_window_n=len(selected), run_n=selected.run_id.nunique(),
                      scene_n=selected.scene_id.nunique(), mpc_count_histogram=histogram)
    if expected is not None and population != dict(expected):
        raise ValueError(f"pinned population does not match frozen WP2 expectation: {population}")
    return selected, population


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "item"):
        return _jsonable(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return "NEGATIVE_INFINITY" if value < 0 else "POSITIVE_INFINITY" if value > 0 else None
    return value


def _csv_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        if FORBIDDEN_OUTPUT_FIELDS & set(row):
            raise ValueError("aggregate WP2 output contains a forbidden identity/coordinate field")
        result.append({key: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
                       if isinstance(value, (dict, list, tuple)) else _jsonable(value)
                       for key, value in row.items()})
    return result


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    records = _csv_records(rows)
    columns = sorted({key for row in records for key in row})
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(records)


def _report_text(population: Mapping[str, Any], marginal_summary: list[dict[str, Any]],
                 tail_summary: list[dict[str, Any]], relation_summary: list[dict[str, Any]],
                 count_summary: list[dict[str, Any]], runtime_seconds: float,
                 task5_evidence: Mapping[str, Any] | None) -> str:
    rank_lines = []
    for row in marginal_summary:
        if row["row_type"] == "FAMILY_RANK":
            rank_lines.append(
                f"- {row['scope']} / {row['variable']} / {row['family']}: "
                f"rank-1 {row['rank1_fold_n']}/{row['rank_evaluated_fold_n']} valid scene folds; "
                f"rank-1 held-out scenes={json.dumps(row['rank1_scene_ids'], ensure_ascii=False)}; "
                f"support-limited {row['support_limited_fold_n']}, failed {row['failed_fold_n']}."
            )
    tail_low_support = sum(int(row["low_support_fold_n"]) for row in tail_summary)
    relation_lines = []
    for row in relation_summary:
        relation_lines.append(
            f"- {row['scope']}: negative fitted slope in {row['negative_slope_scene_n']}/"
            f"{row['evaluated_scene_n']} held-out fits; slope median/range "
            f"{row['slope_median_db_per_chip']:.6g} [{row['slope_min_db_per_chip']:.6g}, {row['slope_max_db_per_chip']:.6g}] dB/chip; "
            f"conditional-minus-marginal scene-macro log score {row['macro_delta_mean_log_score']:.6g} "
            f"(whole-scene bootstrap 95% interval "
            f"[{row['delta_mean_log_score_scene_bootstrap_95_low']:.6g}, {row['delta_mean_log_score_scene_bootstrap_95_high']:.6g}]); "
            f"RMSE delta {row['macro_delta_rmse_db']:.6g} dB."
        )
    count_lines = []
    for row in count_summary:
        delta = row["macro_log_score_delta_vs_categorical"]
        delta_text = "not estimable on finite paired folds" if delta is None else f"{delta:.6g}"
        interval = ("not estimable" if row["log_score_delta_scene_bootstrap_95_low"] is None else
                    f"[{row['log_score_delta_scene_bootstrap_95_low']:.6g}, {row['log_score_delta_scene_bootstrap_95_high']:.6g}]")
        count_lines.append(
            f"- {row['candidate_model']}: evaluated {row['evaluated_scene_n']}/{row['held_out_scene_n']} scenes; "
            f"macro log-score delta vs empirical categorical = {delta_text} over "
            f"{row['paired_finite_scene_n']} finite paired scenes (whole-scene 95% interval {interval}); "
            f"macro RMSE delta = {row['macro_rmse_delta_vs_categorical']!s}; "
            f"unseen-category scenes={row['unseen_category_scene_n']}, boundary fits={row['boundary_fit_scene_n']}."
        )
    boundary_lines = [
        f"- {row['candidate_model']}: {json.dumps(row['fit_status_counts'], sort_keys=True)}"
        for row in count_summary if row["boundary_fit_scene_n"]
    ]
    task5_text = "Not sampled in this invocation." if task5_evidence is None else (
        f"Read-only sample at {task5_evidence.get('checked_local', 'UNKNOWN')}: "
        f"{task5_evidence.get('status', 'UNKNOWN')}, {task5_evidence.get('completed', 'UNKNOWN')}/80; "
        f"{task5_evidence.get('current_run_id', 'no current run')}. No production action was taken."
    )
    return f"""# WP2 Stage2 robustness closure

Status: `COMPLETED_WITH_LIMITATIONS` (bounded exploratory robustness evidence; not formal Gate G).

## Frozen population and method

- {population['mpc_n']:,} Stage2 MPC path records, {population['selected_window_n']:,} Stage2-selected windows, {population['run_n']} runs, {population['scene_n']} scenes.
- Window count histogram on the selected-window denominator: {json.dumps(population['mpc_count_histogram'], sort_keys=True)}.
- The 7,847 windows were selected from the 285,752 Stage0-valid windows. All count estimands are conditional on that Stage2 selection and capped observed support 0–3; unselected Stage0 windows were not assigned zero MPC.
- Reused frozen V0 scene-LOSO fold parameters/ranks; did not rerun V0 fits. Tail quantiles use each fold's training-only parameters. Power-delay and count models use full-scene LOSO with equal total weight per training scene and whole-scene bootstrap; no row-level p-values are emitted.
- Runtime: {runtime_seconds:.1f} s. No raw IQ, MAT/HDF5/CIR payload, MATLAB, SAGE, GNSS-SDR, or Task 5 production was accessed or invoked.

## Scene sensitivity and fit ranking

{chr(10).join(rank_lines)}

Per-fold parameter estimates and interquartile ranges are descriptive sensitivity summaries across overlapping LOSO training sets, not independent estimates or confidence intervals. Failed fits and support-limited folds remain visible.

## Held-out tails

Evaluated p01/p05/p10/p90/p95/p99 held-out quantile calibration using saved training-fold parameters. {tail_low_support} family/scene/quantile records are flagged below the predeclared expected-tail support of 10 observations. Tail evidence is therefore limited where flagged; it is not converted into a pass claim.

## Power-delay relationship and scene-out prediction

{chr(10).join(relation_lines)}

Fitted slopes are predictive associations in the Stage2-selected MPC population, not causal effects or a universal law. A positive macro score delta favors the conditional candidate on average; the 13-scene unit, its interval, RMSE and fold-direction consistency must all be considered together.

## Stage2-selected-window MPC-count candidates

{chr(10).join(count_lines)}

The empirical categorical candidate has no smoothing; unseen held-out categories receive zero probability and are explicitly reported. Parametric PMFs are normalized on 0–3. Count-model conclusions apply only to Stage2-selected windows; these results do not describe all Stage0 windows or justify imputing unselected windows as zero.

Boundary/failure accounting: {chr(10).join(boundary_lines) if boundary_lines else "No boundary or failed fits."} A boundary candidate is not interpreted as a finite interior MLE; its boundary status and any limiting PMF are retained explicitly.

## Task 5 and alpha boundary

{task5_text}

The real alpha export pilot remains deferred until WP2 review. This report does not establish Gate E/F, complete CIR association, or formal model acceptance.

## Files

See the adjacent `*_by_fold.csv` / `*_by_scene.csv`, summary CSVs, and `wp2_manifest.json` for fold-level aggregates, code/input/output hashes, and explicit support statuses. Outputs contain no `(run_id, window_id, path_id)` keys or exact coordinates.
"""


def run_analysis(
    mpc_path: Path,
    windows_path: Path,
    folds_path: Path,
    output_dir: Path,
    *,
    expected_hashes: Mapping[str, str] = EXPECTED_INPUT_SHA256,
    expected_population: Mapping[str, Any] | None = EXPECTED_POPULATION,
    private_manifest: Path | None = None,
    fold_manifest: Path | None = None,
    variables: Mapping[str, list[str]] = v0.VARIABLES,
    scopes: tuple[str, ...] = DEFAULT_SCOPES,
    bootstrap_iterations: int = 2000,
    seed: int = 20261025,
    task5_evidence: Mapping[str, Any] | None = None,
) -> Path:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    inputs = {"analysis_mpc_rows.csv": Path(mpc_path),
              "selected_window_rows.csv": Path(windows_path),
              "scene_fold_scores.csv": Path(folds_path)}
    input_records = _require_hashes(inputs, expected_hashes, private_manifest, fold_manifest)
    started = time.perf_counter()

    mpc_columns = ["run_id", "window_id", "scene_id", "environment_class", "path_id",
                   "is_multipath", "excess_delay_chips", "doppler_offset_hz", "relative_power_db"]
    mpc = pd.read_csv(inputs["analysis_mpc_rows.csv"], usecols=mpc_columns,
                      dtype={"run_id": str, "window_id": str, "scene_id": str})
    windows = pd.read_csv(inputs["selected_window_rows.csv"], usecols=["run_id", "window_id", "scene_id", "mpc_count"],
                          dtype={"run_id": str, "window_id": str, "scene_id": str})
    folds = pd.read_csv(inputs["scene_fold_scores.csv"])
    selected, population = _validate_population(mpc, windows, expected_population)
    _validate_fold_coverage(mpc, folds, tuple(scopes), variables)

    marginal_rows, marginal_summary = marginal_stability_rows(mpc, folds, scopes=scopes)
    tail_rows, tail_summary = tail_calibration_rows(mpc, folds, scopes=scopes)
    relation_rows, relation_summary = evaluate_power_delay_loso(
        mpc, bootstrap_iterations=bootstrap_iterations, seed=seed, scopes=("GLOBAL",)
    )
    count_rows, count_summary = evaluate_selected_count_loso(
        selected, bootstrap_iterations=bootstrap_iterations, seed=seed
    )

    elapsed = time.perf_counter() - started
    # Recheck source bytes before creating results; a changed input invalidates this run.
    final_input_records = _require_hashes(inputs, expected_hashes, private_manifest, fold_manifest)
    if final_input_records != input_records:
        raise ValueError("pinned inputs changed during WP2 analysis")
    output_dir.mkdir(parents=True, exist_ok=False)

    table_rows = {
        OUTPUT_TABLES[0]: marginal_rows,
        OUTPUT_TABLES[1]: marginal_summary,
        OUTPUT_TABLES[2]: tail_rows,
        OUTPUT_TABLES[3]: tail_summary,
        OUTPUT_TABLES[4]: relation_rows,
        OUTPUT_TABLES[5]: relation_summary,
        OUTPUT_TABLES[6]: count_rows,
        OUTPUT_TABLES[7]: count_summary,
    }
    for name, rows in table_rows.items():
        _write_csv(output_dir / name, rows)
    report_path = output_dir / "wp2_report.md"
    with report_path.open("x", encoding="utf-8", newline="\n") as report:
        report.write(_report_text(population, marginal_summary, tail_summary,
                                  relation_summary, count_summary, elapsed, task5_evidence))

    source_paths = {
        "mainline_stage2_v0.py": Path(v0.__file__),
        "mainline_stage2_wp2.py": Path(__file__).with_name("mainline_stage2_wp2.py"),
        "run_mainline_stage2_wp2.py": Path(__file__),
    }
    output_records = {}
    for name in (*OUTPUT_TABLES, "wp2_report.md"):
        path = output_dir / name
        output_records[name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
    manifest = {
        "schema_version": 1,
        "status": "WP2_ROBUSTNESS_COMPLETE_WITH_LIMITATIONS",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Stage2-selected SAGE-only WP2 robustness; no production or CIR payload access",
        "population": population,
        "selection_boundary": {
            "stage0_valid_window_n": 285752,
            "stage2_selected_window_n": population["selected_window_n"],
            "unselected_stage0_windows_assigned_zero_mpc": False,
            "count_support": [0, 1, 2, 3],
        },
        "validation": {
            "outer_unit": "whole_scene_id",
            "training_scene_weight": "each training scene has total weight one",
            "uncertainty_unit": "whole_scene_with_multiplicity",
            "bootstrap_iterations": bootstrap_iterations,
            "seed": seed,
            "row_level_p_values": False,
        },
        "inputs": input_records,
        "sources": {name: {"path": _display_path(path), "sha256": sha256_file(path)}
                    for name, path in source_paths.items()},
        "outputs": output_records,
        "manifest_self_hash": "omitted_to_avoid_recursive_hash",
    }
    manifest_path = output_dir / "wp2_manifest.json"
    with manifest_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(_jsonable(manifest), handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    args = parser.parse_args()
    if args.bootstrap_iterations < 0:
        parser.error("--bootstrap-iterations must be nonnegative")
    output = args.output_dir or DEFAULT_OUTPUT_PARENT / (
        "wp2_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    result = run_analysis(
        DEFAULT_MPC, DEFAULT_WINDOWS, DEFAULT_FOLDS, output,
        private_manifest=PRIVATE_MANIFEST, fold_manifest=FOLD_MANIFEST,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
