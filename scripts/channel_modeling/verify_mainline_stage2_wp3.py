"""Independent read-only reconciliation for a completed Mainline Stage2 WP3 package."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _close(left: float, right: float, tolerance: float = 1e-10) -> bool:
    return bool(np.isclose(float(left), float(right), rtol=tolerance, atol=tolerance, equal_nan=True))


def verify_package(output_dir: Path, write_report: bool = False) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    manifest_path = output / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    findings: list[str] = []

    output_records = manifest["outputs_sha256"]
    output_hashes_ok = True
    for relative, record in output_records.items():
        target = output / relative
        if not target.is_file() or target.stat().st_size != record["size_bytes"] or _sha256(target) != record["sha256"]:
            output_hashes_ok = False
            findings.append(f"output hash/size mismatch: {relative}")
    checks["manifested_output_hashes_match"] = output_hashes_ok

    input_records = manifest["input_sha256"]
    inputs_ok = True
    for name, record in input_records.items():
        source = Path(record["path"])
        if not source.is_file() or source.stat().st_size != record["size_bytes"] or _sha256(source) != record["sha256"]:
            inputs_ok = False
            findings.append(f"input hash/size mismatch: {name}")
    checks["pinned_input_hashes_match"] = inputs_ok

    mpc = pd.read_csv(input_records["mpc_rows"]["path"])
    windows = pd.read_csv(input_records["selected_windows"]["path"])
    path_ids = ["run_id", "window_id", "path_id"]
    window_ids = ["run_id", "window_id"]
    population_ok = (
        len(mpc) == 8914 and not mpc.duplicated(path_ids).any()
        and len(windows) == 7847 and not windows.duplicated(window_ids).any()
        and windows.run_id.nunique() == 83 and mpc.scene_id.nunique() == 13
    )
    checks["input_population_identities_reconcile"] = bool(population_ok)
    if not population_ok:
        findings.append("input Stage2 counts or unique identities do not reconcile")

    support = pd.read_csv(output / "condition_support_by_scene.csv")
    source_support = pd.read_csv(output / "condition_support_by_scene_source.csv")
    count_support = pd.read_csv(output / "window_mpc_count_support_by_scene.csv")
    expected = (windows.groupby(["scene_id", "environment_class"], as_index=False)
                .agg(selected_window_n=("window_id", "size"), mpc_n=("mpc_count", "sum")))
    actual = support[["scene_id", "environment_class", "selected_window_n", "mpc_n"]]
    reconciled = expected.merge(actual, on=["scene_id", "environment_class"], suffixes=("_expected", "_actual"), how="outer", indicator=True)
    support_ok = (
        len(reconciled) == 13 and reconciled._merge.eq("both").all()
        and reconciled.selected_window_n_expected.eq(reconciled.selected_window_n_actual).all()
        and reconciled.mpc_n_expected.eq(reconciled.mpc_n_actual).all()
        and int(count_support.selected_window_n.sum()) == 7847
        and int(source_support.window_n.sum()) == 7847
        and int(source_support.mpc_n.sum()) == 8914
    )
    checks["support_tables_reconcile_to_selected_windows_and_paths"] = bool(support_ok)
    if not support_ok:
        findings.append("scene/source/window-count support tables fail input reconciliation")

    folds = pd.read_csv(output / "loso_fold_manifest.csv")
    fold_ok = True
    core_scenes = set(support.loc[support.environment_class.isin(["Urban", "Mountain/Valley"]), "scene_id"].astype(str))
    fold_counts_ok = (folds.groupby(["data_scope", "variable", "family"], dropna=False)
                      .held_out_scene_id.nunique().eq(9).all())
    for row in folds.itertuples(index=False):
        training = set(json.loads(row.training_scene_ids))
        test = set(json.loads(row.test_scene_ids))
        held = str(row.held_out_scene_id)
        bad_test_set = test not in (set(), {held})
        bad_ready_fold = row.status == "READY" and test != {held}
        if training & test or held not in core_scenes or bad_test_set or bad_ready_fold or not training.issubset(core_scenes - {held}):
            fold_ok = False
            findings.append(f"invalid fold scene partition: {row.data_scope}/{row.held_out_scene_id}")
            break
    checks["folds_are_complete_scene_partitions"] = bool(fold_ok and fold_counts_ok and len(folds) == 324)
    if not checks["folds_are_complete_scene_partitions"] and not findings:
        findings.append(f"unexpected fold count: {len(folds)}")

    scores = pd.read_csv(output / "loso_fold_scores.csv")
    macros = pd.read_csv(output / "loso_equal_scene_macro_scores.csv")
    score_index = scores.set_index(["data_scope", "variable", "family", "held_out_scene_id", "model"])
    macro_ok = len(macros) == scores.groupby(["data_scope", "variable", "family", "model"], dropna=False).ngroups
    macro_keys = ["data_scope", "variable", "family", "model"]
    for row in macros.itertuples(index=False):
        group = scores
        for key in macro_keys:
            group = group.loc[group[key].eq(getattr(row, key))]
        passed = group.loc[group.score_status.eq("PASS") & group.window_balanced_mean_log_score.notna()]
        expected_n = passed.held_out_scene_id.nunique()
        expected_mean = passed.window_balanced_mean_log_score.mean() if expected_n else np.nan
        if expected_n != int(row.held_out_scene_n_scored) or not _close(expected_mean, row.equal_scene_macro_log_score):
            macro_ok = False
            findings.append(f"macro-score mismatch: {tuple(getattr(row, key) for key in macro_keys)}")
            break
    checks["macro_scores_recompute_from_fold_scores"] = bool(macro_ok)

    paired = pd.read_csv(output / "loso_paired_deltas.csv")
    pair_ok = True
    for row in paired.itertuples(index=False):
        right, left = row.comparison.split("-")
        left_key = (row.data_scope, row.variable, row.family, row.held_out_scene_id, left)
        right_key = (row.data_scope, row.variable, row.family, row.held_out_scene_id, right)
        a, b = score_index.loc[left_key], score_index.loc[right_key]
        same_identity = a.test_identity_sha256 == b.test_identity_sha256
        expected_pass = same_identity and a.score_status == "PASS" and b.score_status == "PASS"
        expected_status = "PASS" if expected_pass else (
            "IDENTITY_MISMATCH" if not same_identity else "FIT_OR_SCORE_UNAVAILABLE"
        )
        delta_matches = (expected_pass and
                         _close(float(b.window_balanced_mean_log_score - a.window_balanced_mean_log_score),
                                row.delta_window_balanced_log_score_right_minus_left))
        if (bool(row.same_test_identity) != bool(same_identity)
                or row.test_identity_sha256_left != a.test_identity_sha256
                or row.test_identity_sha256_right != b.test_identity_sha256
                or row.paired_status != expected_status
                or (expected_pass and not delta_matches)):
            pair_ok = False
        if not pair_ok:
            findings.append(f"paired-score identity/value mismatch: {row.comparison}/{row.held_out_scene_id}")
            break
    checks["paired_deltas_use_same_test_identity_and_recompute"] = bool(pair_ok)

    paired_macro = pd.read_csv(output / "loso_paired_delta_macro.csv")
    expected_rows = []
    paired_keys = ["data_scope", "variable", "family", "comparison"]
    for keys, group in paired.loc[paired.paired_status.eq("PASS")].groupby(paired_keys, sort=True):
        record = dict(zip(paired_keys, keys))
        for env, subset in group.groupby("held_out_environment", sort=True):
            expected_rows.append({**record, "held_out_environment": env,
                                  "paired_scene_n": subset.held_out_scene_id.nunique(),
                                  "mean": subset.delta_window_balanced_log_score_right_minus_left.mean()})
        expected_rows.append({**record, "held_out_environment": "ALL_SCORED_CORE_SCENES",
                              "paired_scene_n": group.held_out_scene_id.nunique(),
                              "mean": group.delta_window_balanced_log_score_right_minus_left.mean()})
    paired_expected = pd.DataFrame(expected_rows)
    pm_ok = len(paired_macro) == len(paired_expected)
    if pm_ok:
        check = paired_macro.merge(paired_expected, on=paired_keys + ["held_out_environment"], suffixes=("_actual", "_expected"), how="outer", indicator=True)
        pm_ok = (check._merge.eq("both").all()
                 and check.paired_scene_n_actual.eq(check.paired_scene_n_expected).all()
                 and all(_close(a, b) for a, b in zip(check.equal_scene_mean_delta_log_score, check["mean"])))
    checks["paired_macro_recomputes_from_matched_fold_deltas"] = bool(pm_ok)
    if not pm_ok:
        findings.append("paired macro scores do not reconcile to matched fold deltas")

    tails = pd.read_csv(output / "loso_tail_diagnostics.csv")
    tail_ok = True
    for row in tails.itertuples(index=False):
        key = (row.data_scope, row.variable, row.family, row.held_out_scene_id, row.model)
        score = score_index.loc[key]
        if row.test_identity_sha256 != score.test_identity_sha256:
            tail_ok = False
            findings.append(f"tail diagnostic identity mismatch: {row.data_scope}/{row.held_out_scene_id}")
            break
        if row.held_out_scene_id in json.loads(row.training_scene_ids):
            tail_ok = False
            findings.append(f"held scene leaked into tail fit: {row.held_out_scene_id}")
            break
    checks["tail_records_match_heldout_identity_and_exclude_held_scene"] = bool(tail_ok)

    details = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "result_dir": str(output),
        "checks": checks,
        "counts": {
            "MPC": int(len(mpc)), "unique_MPC_ids": int(mpc.drop_duplicates(path_ids).shape[0]),
            "selected_windows": int(len(windows)), "unique_selected_window_ids": int(windows.drop_duplicates(window_ids).shape[0]),
            "selected_window_runs": int(windows.run_id.nunique()), "runs_with_MPC": int(mpc.run_id.nunique()),
            "scenes": int(mpc.scene_id.nunique()), "core_scenes": int(len(core_scenes)),
            "fold_rows": int(len(folds)), "fold_score_rows": int(len(scores)),
            "paired_fold_rows": int(len(paired)), "tail_rows": int(len(tails)),
        },
        "findings": findings,
        "validator_sha256": _sha256(Path(__file__).resolve()),
    }
    if write_report:
        report_path = output / "independent_validation_final.json"
        if report_path.exists():
            raise FileExistsError(f"refusing to overwrite independent validation: {report_path}")
        report_path.write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    result = verify_package(args.output_dir, args.write_report)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
