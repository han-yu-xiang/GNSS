"""Independent, read-only numerical validation of a Gate G supplement package."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy import special, stats

import mainline_stage2_wp6 as wp6
import mainline_stage2_wp6_gateg as gateg


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = PROJECT_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1"
FROZEN_DIR = MODEL_ROOT / "wp4_gate_ef_final_20261029T181100"
DEFAULT_FEATURES = FROZEN_DIR / "stage2_cir_pdp_window_features.csv"
DEFAULT_MPCS = FROZEN_DIR / "stage2_mpc_cir_alpha_linkage.csv"
MODELS = ("M0_independent", "M1_count_conditional", "C0_mixed_copula",
          "C1_count_mixed_copula")
PAIR_COLUMNS = (("M0_independent", "M1_count_conditional", "M1_minus_M0"),
                ("M0_independent", "C0_mixed_copula", "C0_minus_M0"),
                ("M1_count_conditional", "C1_count_mixed_copula", "C1_minus_M1"))


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dist(family, parameters):
    if family == "gamma":
        return stats.gamma(a=parameters["shape"], loc=0, scale=parameters["scale"])
    if family == "lognormal":
        return stats.lognorm(s=parameters["shape"], loc=0, scale=parameters["scale"])
    if family == "weibull":
        return stats.weibull_min(c=parameters["shape"], loc=0, scale=parameters["scale"])
    if family == "normal":
        return stats.norm(loc=parameters["loc"], scale=parameters["scale"])
    if family == "laplace":
        return stats.laplace(loc=parameters["loc"], scale=parameters["scale"])
    if family == "student_t":
        return stats.t(df=parameters["df"], loc=parameters["loc"], scale=parameters["scale"])
    raise ValueError(f"unsupported family {family}")


def _ref_logdiff(log_a, log_b):
    if not np.isfinite(log_a) and log_a != -np.inf:
        raise ValueError("non-finite log interval endpoint")
    if log_b > log_a:
        if log_b - log_a < 1e-12:
            log_b = log_a
        else:
            raise ValueError("reversed log interval endpoints")
    if log_a == log_b:
        return -np.inf
    return float(log_a + np.log(-np.expm1(log_b - log_a)))


def _ref_log_interval(dist, low, high):
    if high <= low:
        raise ValueError("invalid delay cell")
    logcdf_high = float(dist.logcdf(high))
    if logcdf_high > np.log(.5):
        return _ref_logdiff(float(dist.logsf(low)), float(dist.logsf(high)))
    return _ref_logdiff(logcdf_high, float(dist.logcdf(low)))


def _ref_delay_cell(value):
    low = max(gateg.MIN_DELAY_CHIPS, value - gateg.DELAY_GRID_CHIPS / 2)
    high = value + gateg.DELAY_GRID_CHIPS / 2
    return low, high


def _ref_truncated_cdf(dist, value):
    log_survival_min = float(dist.logsf(gateg.MIN_DELAY_CHIPS))
    log_ratio = float(dist.logsf(value)) - log_survival_min
    return float(np.clip(-np.expm1(min(log_ratio, 0.0)), 0.0, 1.0))


def _ref_normal_log_interval(low, high, mean, sd):
    lo, hi = (low - mean) / sd, (high - mean) / sd
    if lo > 0:
        return _ref_logdiff(float(special.log_ndtr(-lo)), float(special.log_ndtr(-hi)))
    return _ref_logdiff(float(special.log_ndtr(hi)), float(special.log_ndtr(lo)))


def _ref_marginal_log_score(row, fit_map):
    delay_fit = fit_map["excess_delay_chips"]
    delay_dist = _dist(delay_fit["family"], delay_fit["parameters"])
    low, high = _ref_delay_cell(float(row.excess_delay_chips))
    score = (_ref_log_interval(delay_dist, low, high)
             - float(delay_dist.logsf(gateg.MIN_DELAY_CHIPS)))
    for variable in gateg.MARK_VARIABLES[1:]:
        fit = fit_map[variable]
        score += float(_dist(fit["family"], fit["parameters"]).logpdf(float(getattr(row, variable))))
    return float(score)


def _ref_mixed_log_score(row, fit_map, correlation):
    score = _ref_marginal_log_score(row, fit_map)
    delay_fit = fit_map["excess_delay_chips"]
    delay_dist = _dist(delay_fit["family"], delay_fit["parameters"])
    low, high = _ref_delay_cell(float(row.excess_delay_chips))
    zlow = special.ndtri(_ref_truncated_cdf(delay_dist, low))
    zhigh = special.ndtri(_ref_truncated_cdf(delay_dist, high))
    zcont = []
    for variable in gateg.MARK_VARIABLES[1:]:
        fit = fit_map[variable]
        dist = _dist(fit["family"], fit["parameters"])
        u = np.clip(float(dist.cdf(float(getattr(row, variable)))), 1e-12, 1 - 1e-12)
        zcont.append(float(special.ndtri(u)))
    zcont = np.asarray(zcont)
    corr = np.asarray(correlation, dtype=float)
    rcc = corr[1:, 1:]
    cross = corr[0, 1:]
    inv = np.linalg.inv(rcc)
    mean = float(zcont @ inv @ cross)
    variance = float(1 - cross @ inv @ cross)
    log_pair_density = float(stats.multivariate_normal.logpdf(zcont, mean=np.zeros(2), cov=rcc)
                              - stats.norm.logpdf(zcont).sum())
    log_cond_mass = _ref_normal_log_interval(zlow, zhigh, mean, np.sqrt(variance))
    log_ind_mass = _ref_normal_log_interval(zlow, zhigh, 0.0, 1.0)
    return float(score + log_pair_density + log_cond_mass - log_ind_mass)


def _load_params(parameters, held_scene, model, count):
    rows = parameters.loc[parameters.outer_held_out_scene_id.astype(str).eq(held_scene)
                          & parameters.model.astype(str).eq(model)
                          & parameters.count_condition.astype(str).eq(str(count))]
    result = {}
    for row in rows.itertuples(index=False):
        if row.status == "PASS":
            result[row.variable] = {"family": row.family,
                                    "parameters": json.loads(row.parameters_json)}
    return result


def _load_corr(diagnostics, held_scene, model, count):
    def normalize_count(value):
        if pd.isna(value) or str(value).strip() == "":
            return "ALL"
        try:
            numeric = float(value)
            if np.isfinite(numeric) and numeric.is_integer():
                return str(int(numeric))
        except (TypeError, ValueError):
            pass
        return str(value).strip()

    conditions = diagnostics.count_condition.map(normalize_count)
    rows = diagnostics.loc[diagnostics.outer_held_out_scene_id.astype(str).eq(held_scene)
                           & diagnostics.model.astype(str).eq(model)
                           & conditions.eq(str(count))]
    if len(rows) != 1 or rows.iloc[0].status != "PASS":
        return None
    return json.loads(rows.iloc[0].correlation_json)


def _bind_source_marks(path_scores, source_mpcs):
    """Attach frozen mark attributes by exact path identity for score recomputation."""
    keys = list(wp6.MPC_KEY)
    if path_scores.duplicated(keys).any() or source_mpcs.duplicated(keys).any():
        raise ValueError("path score/source join has duplicate identity keys")
    attributes = source_mpcs[[*keys, "scene_id", *gateg.MARK_VARIABLES]].copy()
    attributes = attributes.rename(columns={"scene_id": "source_scene_id"})
    joined = path_scores.merge(attributes, on=keys, how="left", validate="one_to_one", indicator=True)
    if not joined._merge.eq("both").all():
        raise ValueError("path score/source mark identity join does not fully match")
    if not joined.scene_id.astype(str).equals(joined.source_scene_id.astype(str)):
        raise ValueError("path score/source mark scene identity mismatch")
    return joined.drop(columns=["_merge", "source_scene_id"])


def _close(actual, expected, tolerance=2e-7):
    if np.isnan(expected):
        return bool(np.isnan(actual))
    return bool(np.isfinite(actual) and abs(float(actual) - float(expected)) <= tolerance)


def _same_identity_and_counts(left, right, key_columns, count_column):
    if len(left) != len(right):
        return False
    for column in key_columns:
        a = left[column].astype("string").fillna("").to_numpy(dtype=str)
        b = right[column].astype("string").fillna("").to_numpy(dtype=str)
        if not np.array_equal(a, b):
            return False
    a_count = pd.to_numeric(left[count_column], errors="coerce").to_numpy(float)
    b_count = pd.to_numeric(right[count_column], errors="coerce").to_numpy(float)
    return bool(np.array_equal(a_count, b_count))


def validate_result_package(output_dir, features_path=DEFAULT_FEATURES, mpc_path=DEFAULT_MPCS):
    output = Path(output_dir).resolve()
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})
        if not ok:
            raise ValueError(f"{name} failed: {detail}")

    windows, source_mpcs, input_manifest = wp6.load_wp6_inputs(features_path, mpc_path)
    source_mpcs = gateg.prepare_ranked_marks(source_mpcs)
    check("frozen_input_hashes", input_manifest["features_sha256"] == wp6.FEATURES_SHA256
          and input_manifest["mpc_sha256"] == wp6.MPC_SHA256, input_manifest)
    manifest = json.loads((output / "input_code_manifest.json").read_text(encoding="utf-8"))
    check("output_input_pins", manifest["input_manifest"]["features_sha256"] == input_manifest["features_sha256"]
          and manifest["input_manifest"]["mpc_sha256"] == input_manifest["mpc_sha256"], "matched")
    code_hash_mismatches = {}
    validator_sha_at_analysis = manifest["source_files"].get(
        "scripts/channel_modeling/validate_mainline_stage2_wp6_gateg.py")
    for relative, expected in manifest["source_files"].items():
        # The analysis runner does not import or call this validator. Bind the
        # actual independent verifier version below, at validation time.
        if relative == "scripts/channel_modeling/validate_mainline_stage2_wp6_gateg.py":
            continue
        source = PROJECT_ROOT / relative
        actual = _sha256(source) if source.is_file() else None
        if actual != expected:
            code_hash_mismatches[relative] = {"expected": expected, "actual": actual}
    check("analysis_source_sha256", not code_hash_mismatches, code_hash_mismatches)
    validator_sha_at_validation = _sha256(Path(__file__).resolve())
    output_manifest = json.loads((output / "output_sha256_manifest.json").read_text(encoding="utf-8"))
    output_hash_mismatches = {}
    for name, expected in output_manifest.items():
        target = output / name
        actual = _sha256(target) if target.is_file() else None
        if actual != expected:
            output_hash_mismatches[name] = {"expected": expected, "actual": actual}
    check("result_file_sha256_manifest", not output_hash_mismatches, output_hash_mismatches)
    record = json.loads((output / "execution_record.json").read_text(encoding="utf-8"))
    check("analysis_completed", record.get("status") == "ANALYSIS_COMPLETE_VALIDATION_PENDING"
          and record.get("outer_completed_fold_n") == 13, record.get("status"))

    fold = pd.read_csv(output / "folds.csv", dtype={"outer_held_out_scene_id": "string"})
    scenes = sorted(windows.scene_id.astype(str).unique().tolist())
    check("outer_scene_folds", len(fold) == 13 and fold.outer_held_out_scene_id.nunique() == 13
          and sorted(fold.outer_held_out_scene_id.astype(str)) == scenes, len(fold))
    for row in fold.itertuples(index=False):
        training = json.loads(row.outer_training_scene_ids)
        check(f"no_outer_leakage_{row.outer_held_out_scene_id}",
              row.outer_held_out_scene_id not in training and sorted(training) ==
              sorted(set(scenes) - {row.outer_held_out_scene_id}), len(training))

    params = pd.read_csv(output / "outer_fold_parameters.csv", dtype={
        "outer_held_out_scene_id": "string", "count_condition": "string"})
    copula = pd.read_csv(output / "copula_diagnostics.csv", dtype={
        "outer_held_out_scene_id": "string", "count_condition": "string"})
    paths = pd.read_csv(output / "heldout_path_scores.csv", dtype={
        "run_id": "string", "window_id": "string", "path_id": "string",
        "scene_id": "string", "outer_held_out_scene_id": "string"})
    source_keys = source_mpcs[list(wp6.MPC_KEY + ("scene_id",))].sort_values(
        list(wp6.MPC_KEY), kind="stable").reset_index(drop=True)
    saved_keys = paths[list(wp6.MPC_KEY + ("scene_id", "outer_held_out_scene_id"))].copy()
    saved_keys["scene_id"] = saved_keys.scene_id.astype(str)
    saved_keys["outer_held_out_scene_id"] = saved_keys.outer_held_out_scene_id.astype(str)
    expected_keys = source_keys.copy()
    expected_keys["scene_id"] = expected_keys.scene_id.astype(str)
    expected_keys["outer_held_out_scene_id"] = expected_keys.scene_id
    expected_keys = expected_keys.sort_values(list(wp6.MPC_KEY), kind="stable").reset_index(drop=True)
    saved_keys = saved_keys.sort_values(list(wp6.MPC_KEY), kind="stable").reset_index(drop=True)
    check("exact_mpc_identity_and_scene", len(paths) == len(source_mpcs)
          and not paths.duplicated(list(wp6.MPC_KEY)).any()
          and expected_keys.equals(saved_keys), f"source={len(source_mpcs)}, output={len(paths)}")
    check("all_path_scores_bind_to_heldout_scene",
          paths.scene_id.astype(str).equals(paths.outer_held_out_scene_id.astype(str)), "scene identity")
    paths = _bind_source_marks(paths, source_mpcs)

    # Independently rebuild each saved path score with scipy distribution and
    # conditional-normal formulas; do not call the exporter/scoring function.
    score_columns = {
        "M0_independent": ("M0", "ALL", None),
        "M1_count_conditional": ("M1", None, None),
        "C0_mixed_copula": ("M0", "ALL", "C0"),
        "C1_count_mixed_copula": ("M1", None, "C1"),
    }
    max_errors = {model: 0.0 for model in MODELS}
    compared = {model: 0 for model in MODELS}
    score_failures = {model: [] for model in MODELS}
    for row in paths.itertuples(index=False):
        held = str(row.outer_held_out_scene_id)
        count = int(row.n_mpc)
        for column, (fit_model, fit_count, cop_model) in score_columns.items():
            actual = float(getattr(row, column))
            selected_count = str(count) if fit_count is None else fit_count
            fit_map = _load_params(params, held, fit_model, selected_count)
            if set(fit_map) != set(gateg.MARK_VARIABLES):
                ref = np.nan
            else:
                ref = _ref_marginal_log_score(row, fit_map)
                if cop_model:
                    corr_count = str(count) if cop_model == "C1" else "ALL"
                    corr = _load_corr(copula, held, cop_model, corr_count)
                    ref = np.nan if corr is None else _ref_mixed_log_score(row, fit_map, corr)
            if np.isnan(ref):
                if not np.isnan(actual):
                    score_failures[column].append((held, str(row.window_id), str(row.path_id), "expected NaN"))
            else:
                error = abs(actual - ref)
                max_errors[column] = max(max_errors[column], float(error))
                compared[column] += 1
                if not _close(actual, ref):
                    score_failures[column].append((held, str(row.window_id), str(row.path_id),
                                                   f"actual={actual}; expected={ref}"))
    for model in MODELS:
        check(f"independent_score_recomputation_{model}", not score_failures[model],
              {"compared": compared[model], "max_error": max_errors[model],
               "first_failure": score_failures[model][:3]})

    # Every output summary is recomputed from the paired path-score file.
    computed = gateg._window_scene_scores(paths, MODELS)
    saved_windows = pd.read_csv(output / "heldout_window_scores.csv", dtype={
        "run_id": "string", "window_id": "string", "scene_id": "string"})
    left = computed[0].sort_values(list(wp6.WINDOW_KEY), kind="stable").reset_index(drop=True)
    right = saved_windows.sort_values(list(wp6.WINDOW_KEY), kind="stable").reset_index(drop=True)
    identity_columns = list(wp6.WINDOW_KEY + ("scene_id",))
    check("window_scores_recomputed", _same_identity_and_counts(
        left, right, identity_columns, "n_mpc"), "window identities and counts")
    for model in MODELS:
        col = f"{model}_mean_per_mpc"
        check(f"window_score_values_{model}", np.allclose(left[col], right[col], equal_nan=True,
              rtol=0, atol=2e-7), f"max error={np.nanmax(np.abs(left[col] - right[col]))}")
        sum_col = f"{model}_sum_composite"
        check(f"window_composite_sums_{model}", np.allclose(left[sum_col], right[sum_col], equal_nan=True,
              rtol=0, atol=2e-7), "recomputed from path-level scores")
    check("count_zero_selected_windows_retained",
          int((pd.to_numeric(windows.stage2_mpc_count).astype(int) == 0).sum()) == 3574,
          int((pd.to_numeric(windows.stage2_mpc_count).astype(int) == 0).sum()))
    support = pd.read_csv(output / "count_scene_support.csv")
    check("count_support_all_scenes", all(
        set(support.loc[support.n_mpc.eq(n), "scene_id"].astype(str)) == set(scenes)
        for n in (1, 2, 3)), support.groupby("n_mpc").scene_id.nunique().to_dict())
    check("no_stage0_unselected_mark_rows", len(paths) == int(len(source_mpcs)), len(paths))

    # Independently check ordered rank identity and ensure diagnostic outputs
    # retain a scene-level summary rather than counting paths as scenes.
    invalid_rank_groups = []
    for _, group in source_mpcs.groupby(list(wp6.WINDOW_KEY), sort=False):
        ordered = group.sort_values("mpc_rank")
        ids = pd.to_numeric(ordered.path_id, errors="raise").astype(int).tolist()
        delays = pd.to_numeric(ordered.excess_delay_chips, errors="raise").to_numpy(float)
        if ids != list(range(2, len(ids) + 2)) or not np.all(np.diff(delays) > 0):
            invalid_rank_groups.append((ordered.run_id.iloc[0], ordered.window_id.iloc[0], ids))
    check("rank_order_all_windows", not invalid_rank_groups,
          {"invalid_group_n": len(invalid_rank_groups), "first_failures": invalid_rank_groups[:3]})
    rank_summary = pd.read_csv(output / "path_rank_scene_summary.csv")
    rank_contrasts = pd.read_csv(output / "path_rank_scene_contrasts.csv")
    check("rank_diagnostic_scene_granularity", rank_summary.scene_id.nunique() == 13
          and rank_contrasts.scene_id.nunique() == 13, "scene-level rank tables")

    validation = {
        "status": "PASS_WITH_LIMITATIONS", "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validator": str(Path(__file__).resolve()),
        "validator_sha256_at_analysis_manifest": validator_sha_at_analysis,
        "validator_sha256_at_validation": validator_sha_at_validation,
        "input_sha256": {"features": input_manifest["features_sha256"], "mpcs": input_manifest["mpc_sha256"]},
        "source_window_n": int(len(windows)), "source_mpc_n": int(len(source_mpcs)),
        "output_scored_path_n": int(len(paths)), "scene_n": int(len(scenes)),
        "score_recomputed_n": compared, "maximum_absolute_score_error": max_errors,
        "check_n": len(checks), "failed_check_n": 0, "checks": checks,
        "limitations": [
            "LOSO training sets overlap; fold-level contrasts are descriptive, not independent repetitions.",
            "Per-MPC score is a scene/window-balanced composite score, not a whole ordered window joint likelihood.",
            "All mark and count conclusions are conditional on Stage2-selected windows.",
            "Component rank is SAGE delay-sorted path_id, not verified physical path identity.",
        ],
    }
    return validation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--mpcs", type=Path, default=DEFAULT_MPCS)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    record_path = output / f"validation_attempt_{stamp}.json"
    try:
        record = validate_result_package(output, args.features, args.mpcs)
        record["command"] = " ".join(sys.argv)
        record["process_exit_code"] = 0
        record_path.write_text(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                               encoding="utf-8")
        print(f"VALIDATION={record['status']} checks={record['check_n']} scores={record['score_recomputed_n']}")
        execution_path = output / "execution_record.json"
        execution = json.loads(execution_path.read_text(encoding="utf-8"))
        execution["validation"] = record["status"]
        execution["validation_record"] = record_path.name
        execution["validation_completed_at_utc"] = record["validated_at_utc"]
        execution_path.write_text(json.dumps(execution, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    except Exception as exc:
        failure = {"status": "FAIL", "validated_at_utc": datetime.now(timezone.utc).isoformat(),
                   "process_exit_code": 1, "command": " ".join(sys.argv),
                   "error": f"{type(exc).__name__}: {exc}"}
        record_path.write_text(json.dumps(failure, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"VALIDATION=FAIL {failure['error']}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
