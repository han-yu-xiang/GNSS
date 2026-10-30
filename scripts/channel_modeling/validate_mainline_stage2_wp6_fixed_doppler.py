"""Independent read-only validation of fixed-bin Gate G result packages."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import integrate, special, stats

import mainline_stage2_wp6 as wp6
import mainline_stage2_wp6_fixed_doppler as fixed
import mainline_stage2_wp6_gateg as gateg


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = PROJECT_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1"
FROZEN_DIR = MODEL_ROOT / "wp4_gate_ef_final_20261029T181100"
DEFAULT_FEATURES = FROZEN_DIR / "stage2_cir_pdp_window_features.csv"
DEFAULT_MPCS = FROZEN_DIR / "stage2_mpc_cir_alpha_linkage.csv"


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dist(family, parameters):
    if family == "gamma":
        return stats.gamma(a=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "lognormal":
        return stats.lognorm(s=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "weibull":
        return stats.weibull_min(c=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "normal":
        return stats.norm(loc=parameters["loc"], scale=parameters["scale"])
    if family == "student_t":
        return stats.t(df=parameters["df"], loc=parameters["loc"], scale=parameters["scale"])
    if family == "laplace":
        return stats.laplace(loc=parameters["loc"], scale=parameters["scale"])
    raise ValueError(f"unsupported family in saved fold: {family}")


def _logdiff(log_a, log_b):
    if log_b > log_a:
        if log_b - log_a < 1e-12:
            log_b = log_a
        else:
            raise ValueError("reversed log interval")
    if log_a == log_b:
        return -np.inf
    return float(log_a + np.log(-np.expm1(log_b - log_a)))


def _log_interval(dist, low, high):
    logcdf_high = float(dist.logcdf(high))
    if logcdf_high > np.log(.5):
        return _logdiff(float(dist.logsf(low)), float(dist.logsf(high)))
    return _logdiff(logcdf_high, float(dist.logcdf(low)))


def _ref_doppler_bin(value, width):
    # Deliberately written independently of fixed.doppler_bin_indices.
    index = int(np.floor(float(value) / float(width) + 0.5))
    return (index - 0.5) * width, (index + 0.5) * width


def _ref_delay_bounds(value):
    return max(gateg.MIN_DELAY_CHIPS, float(value) - gateg.DELAY_GRID_CHIPS / 2), \
        float(value) + gateg.DELAY_GRID_CHIPS / 2


def _ref_marginal_score(row, fit_map, width):
    delay_fit = fit_map["excess_delay_chips"]
    delay_dist = _dist(delay_fit["family"], delay_fit["parameters"])
    dlow, dhigh = _ref_delay_bounds(row.excess_delay_chips)
    delay_logmass = (_log_interval(delay_dist, dlow, dhigh)
                     - float(delay_dist.logsf(gateg.MIN_DELAY_CHIPS)))
    doppler_fit = fit_map["doppler_offset_hz"]
    doppler_dist = _dist(doppler_fit["family"], doppler_fit["parameters"])
    blow, bhigh = _ref_doppler_bin(row.doppler_offset_hz, width)
    power_fit = fit_map["relative_power_db"]
    power_dist = _dist(power_fit["family"], power_fit["parameters"])
    return float(delay_logmass + _log_interval(doppler_dist, blow, bhigh)
                 + power_dist.logpdf(float(row.relative_power_db)))


def _ref_truncated_delay_cdf(dist, value):
    log_survival_min = float(dist.logsf(gateg.MIN_DELAY_CHIPS))
    log_ratio = float(dist.logsf(value)) - log_survival_min
    return float(np.clip(-np.expm1(min(log_ratio, 0.0)), 0.0, 1.0))


def _ref_normal_quantile(probability):
    probability = np.asarray(probability, dtype=float)
    result = np.empty_like(probability)
    lower = probability <= 0.0
    upper = probability >= 1.0
    middle = ~(lower | upper)
    result[lower] = -np.inf
    result[upper] = np.inf
    result[middle] = special.ndtri(probability[middle])
    return result


def _ref_copula_score(row, fit_map, correlation, width):
    delay_fit = fit_map["excess_delay_chips"]
    delay_dist = _dist(delay_fit["family"], delay_fit["parameters"])
    dl, du = _ref_delay_bounds(row.excess_delay_chips)
    zl, zu = _ref_normal_quantile(np.asarray([_ref_truncated_delay_cdf(delay_dist, dl),
                                              _ref_truncated_delay_cdf(delay_dist, du)]))

    doppler_fit = fit_map["doppler_offset_hz"]
    doppler_dist = _dist(doppler_fit["family"], doppler_fit["parameters"])
    bl, bu = _ref_doppler_bin(row.doppler_offset_hz, width)
    zbl, zbu = special.ndtri(np.clip([doppler_dist.cdf(bl), doppler_dist.cdf(bu)],
                                    1e-14, 1 - 1e-14))

    power_fit = fit_map["relative_power_db"]
    power_dist = _dist(power_fit["family"], power_fit["parameters"])
    up = float(np.clip(power_dist.cdf(row.relative_power_db), 1e-14, 1 - 1e-14))
    zp = float(special.ndtri(up))
    corr = np.asarray(correlation, dtype=float)
    cross = corr[:2, 2]
    covariance = corr[:2, :2] - np.outer(cross, cross)
    mu = zp * cross
    sd0 = float(np.sqrt(covariance[0, 0]))
    slope = float(covariance[1, 0] / covariance[0, 0])
    sd1 = float(np.sqrt(covariance[1, 1] - covariance[1, 0] ** 2 / covariance[0, 0]))

    def integrand(z0):
        conditional_mu = mu[1] + slope * (z0 - mu[0])
        conditional_mass = special.ndtr((zbu - conditional_mu) / sd1) - \
            special.ndtr((zbl - conditional_mu) / sd1)
        return stats.norm.pdf(z0, loc=mu[0], scale=sd0) * conditional_mass

    rectangle, error = integrate.quad(integrand, float(zl), float(zu), epsabs=1e-13,
                                      epsrel=2e-10, limit=200)
    if not np.isfinite(rectangle) or rectangle <= 0 or not np.isfinite(error):
        raise ValueError("independent reference rectangle integration failed")
    return float(power_dist.logpdf(row.relative_power_db) + np.log(rectangle))


def _read_table(output, name, strings=()):
    dtype = {field: "string" for field in strings}
    return pd.read_csv(output / name, dtype=dtype)


def validate_result_package(output_dir, features_path=DEFAULT_FEATURES, mpc_path=DEFAULT_MPCS,
                            quadrature_sample_n=9, tolerance=2e-6):
    output = Path(output_dir).resolve()
    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "status": "PASS" if bool(ok) else "FAIL", "detail": detail})
        if not ok:
            raise ValueError(f"{name} failed: {detail}")

    windows, source, manifest = wp6.load_wp6_inputs(features_path, mpc_path)
    source = gateg.prepare_ranked_marks(source)
    check("pinned_source_inputs", manifest["mpc_sha256"] == wp6.MPC_SHA256
          and manifest["features_sha256"] == wp6.FEATURES_SHA256,
          {"mpcs": manifest["mpc_sha256"], "features": manifest["features_sha256"]})
    execution = json.loads((output / "execution_record.json").read_text(encoding="utf-8"))
    check("analysis_finished_all_outer_folds", execution.get("status") == "ANALYSIS_COMPLETE_VALIDATION_PENDING"
          and execution.get("outer_completed_fold_n") == 13, execution.get("status"))
    check("predeclared_bin_widths_and_primary", tuple(float(x) for x in execution.get("widths_hz", []))
          == fixed.DOPPLER_WIDTHS_HZ
          and float(execution.get("primary_width_hz", np.nan)) == fixed.DOPPLER_PRIMARY_WIDTH_HZ,
          {"widths_hz": execution.get("widths_hz"),
           "primary_width_hz": execution.get("primary_width_hz")})
    code_manifest = json.loads((output / "input_code_manifest.json").read_text(encoding="utf-8"))
    source_errors = {}
    for relative, expected in code_manifest.get("analysis_source_sha256", {}).items():
        path = PROJECT_ROOT / relative
        actual = _sha256(path) if path.is_file() else None
        if actual != expected:
            source_errors[relative] = {"expected": expected, "actual": actual}
    check("analysis_source_sha256", not source_errors, source_errors)
    output_hashes = json.loads((output / "output_sha256_manifest.json").read_text(encoding="utf-8"))
    hash_errors = {}
    for name, expected in output_hashes.items():
        target = output / name
        actual = _sha256(target) if target.is_file() else None
        if actual != expected:
            hash_errors[name] = {"expected": expected, "actual": actual}
    check("analysis_output_hashes", not hash_errors, hash_errors)

    fold = _read_table(output, "folds.csv", ("outer_held_out_scene_id",))
    scenes = sorted(windows.scene_id.astype(str).unique().tolist())
    check("all_13_outer_scenes", len(fold) == 13 and sorted(fold.outer_held_out_scene_id.astype(str)) == scenes,
          fold.outer_held_out_scene_id.astype(str).tolist())
    for row in fold.itertuples(index=False):
        train_scenes = json.loads(row.outer_training_scene_ids)
        expected = sorted(set(scenes) - {str(row.outer_held_out_scene_id)})
        check(f"outer_no_leak_{row.outer_held_out_scene_id}",
              str(row.outer_held_out_scene_id) not in train_scenes and sorted(train_scenes) == expected,
              len(train_scenes))

    paths = _read_table(output, "heldout_path_scores.csv", ("run_id", "window_id", "path_id",
                                                               "scene_id", "outer_held_out_scene_id"))
    identity = list(wp6.MPC_KEY)
    expected_paths = source[identity + ["scene_id"]].copy()
    widths = tuple(float(item) for item in execution["widths_hz"])
    expected_rows = len(source) * len(widths)
    actual_rows = len(paths)
    check("every_frozen_MPC_scored_once_per_width", actual_rows == expected_rows
          and not paths.duplicated(identity + ["width_hz"]).any(),
          {"expected_rows": expected_rows, "actual_rows": actual_rows,
           "duplicate_keys": int(paths.duplicated(identity + ["width_hz"]).sum())})
    for width in widths:
        group = paths.loc[np.isclose(pd.to_numeric(paths.width_hz), width)].copy()
        compare = group[identity + ["scene_id"]].merge(
            expected_paths, on=identity, how="outer", suffixes=("_out", "_source"),
            validate="one_to_one", indicator=True)
        check(f"exact_source_identity_width_{width:g}Hz",
              len(group) == len(source) and compare._merge.eq("both").all()
              and compare.scene_id_out.astype(str).equals(compare.scene_id_source.astype(str))
              and group.outer_held_out_scene_id.astype(str).equals(group.scene_id.astype(str)),
              {"rows": len(group), "source_rows": len(source),
               "unmatched": int(compare._merge.ne("both").sum())})

    selection = _read_table(output, "inner_family_selection.csv", ("outer_held_out_scene_id",
                                                                       "inner_held_out_scene_id"))
    selection_leaks = []
    for row in selection.itertuples(index=False):
        outer = str(row.outer_held_out_scene_id)
        inner_held = str(row.inner_held_out_scene_id)
        train_scenes = json.loads(row.inner_training_scene_ids)
        if outer in train_scenes or inner_held in train_scenes:
            selection_leaks.append({"outer": outer, "inner_held": inner_held,
                                    "training": train_scenes})
    check("nested_selection_excludes_outer_and_inner_holdouts", not selection_leaks,
          {"selection_rows": int(len(selection)), "leaks": selection_leaks[:3]})
    params = _read_table(output, "outer_fold_parameters.csv", ("outer_held_out_scene_id", "variable"))
    expected_parameter_rows = 13 * len(widths) * 3
    param_leaks = []
    for row in params.itertuples(index=False):
        train_scenes = json.loads(row.training_scene_ids)
        if str(row.outer_held_out_scene_id) in train_scenes:
            param_leaks.append(str(row.outer_held_out_scene_id))
    check("all_outer_fold_parameter_records_bound", len(params) == expected_parameter_rows
          and not param_leaks, {"rows": int(len(params)), "expected": expected_parameter_rows,
                                "leak_scenes": param_leaks[:3]})
    diagnostics = _read_table(output, "copula_diagnostics.csv", ("outer_held_out_scene_id",))
    check("all_width_fold_diagnostics_present", len(diagnostics) == 13 * len(widths)
          and not diagnostics.duplicated(["outer_held_out_scene_id", "width_hz"]).any(),
          {"rows": int(len(diagnostics)), "expected": 13 * len(widths)})
    for row in diagnostics.itertuples(index=False):
        train_scenes = json.loads(row.training_scene_ids)
        check(f"copula_train_only_{row.outer_held_out_scene_id}_{row.width_hz:g}",
              str(row.outer_held_out_scene_id) not in train_scenes,
              train_scenes)
        if row.status == "PASS":
            corr = np.asarray(json.loads(row.correlation_json), dtype=float)
            check(f"copula_PD_{row.outer_held_out_scene_id}_{row.width_hz:g}",
                  corr.shape == (3, 3) and np.allclose(corr, corr.T, atol=1e-10)
                  and np.allclose(np.diag(corr), 1.0, atol=1e-10)
                  and np.linalg.eigvalsh(corr).min() > 0.0,
                  np.linalg.eigvalsh(corr).tolist())

    stored_windows = _read_table(output, "heldout_window_scores.csv", ("run_id", "window_id",
                                                                           "scene_id", "outer_held_out_scene_id"))
    scene_scores = _read_table(output, "paired_scene_score_comparisons.csv", ("scene_id",
                                                                                "outer_held_out_scene_id"))
    grouped = paths.groupby(["width_hz", "outer_held_out_scene_id", "scene_id", "run_id", "window_id"],
                            sort=True, dropna=False)
    expected_window_rows = []
    for keys, group in grouped:
        row = dict(zip(["width_hz", "outer_held_out_scene_id", "scene_id", "run_id", "window_id"], keys))
        for model in ("M0_independent", "C0_copula"):
            values = pd.to_numeric(group[model], errors="coerce").to_numpy(float)
            row[model] = float(values.mean()) if len(values) and np.isfinite(values).all() else np.nan
        row["mpc_row_n"] = int(len(group))
        expected_window_rows.append(row)
    expected_windows = pd.DataFrame(expected_window_rows)
    key_columns = ["width_hz", "outer_held_out_scene_id", "scene_id", "run_id", "window_id"]
    merged_window = stored_windows.merge(expected_windows, on=key_columns, how="outer",
                                         suffixes=("_stored", "_ref"), validate="one_to_one", indicator=True)
    window_error = 0.0
    for model in ("M0_independent", "C0_copula"):
        left = pd.to_numeric(merged_window[f"{model}_stored"], errors="coerce").to_numpy(float)
        right = pd.to_numeric(merged_window[f"{model}_ref"], errors="coerce").to_numpy(float)
        finite_pair = np.isfinite(left) & np.isfinite(right)
        if np.any(np.isfinite(left) ^ np.isfinite(right)):
            window_error = np.inf
        elif finite_pair.any():
            window_error = max(window_error, float(np.max(np.abs(left[finite_pair] - right[finite_pair]))))
    check("window_score_aggregation_reproduced", merged_window._merge.eq("both").all()
          and window_error <= 1e-10,
          {"window_rows": len(stored_windows), "max_abs_error": window_error})

    scene_reference = []
    for keys, group in expected_windows.groupby(["width_hz", "outer_held_out_scene_id", "scene_id"],
                                                 sort=True, dropna=False):
        paired = np.isfinite(group.M0_independent.to_numpy(float)) & np.isfinite(
            group.C0_copula.to_numpy(float))
        delta = group.loc[paired, "C0_copula"].to_numpy(float) - \
            group.loc[paired, "M0_independent"].to_numpy(float)
        scene_reference.append({
            "width_hz": keys[0], "outer_held_out_scene_id": keys[1], "scene_id": keys[2],
            "heldout_window_n": len(group), "paired_window_n": int(paired.sum()),
            "unpaired_window_n": int((~paired).sum()),
            "M0_mean_per_paired_window": float(group.loc[paired, "M0_independent"].mean()) if paired.any() else np.nan,
            "C0_mean_per_paired_window": float(group.loc[paired, "C0_copula"].mean()) if paired.any() else np.nan,
            "C0_minus_M0_nats_per_mpc": float(delta.mean()) if len(delta) else np.nan,
        })
    scene_ref = pd.DataFrame(scene_reference)
    merged_scene = scene_scores.merge(scene_ref, on=["width_hz", "outer_held_out_scene_id", "scene_id"],
                                      how="outer", suffixes=("_stored", "_ref"), validate="one_to_one",
                                      indicator=True)
    score_error = 0.0
    numeric_fields = ["heldout_window_n", "paired_window_n", "unpaired_window_n",
                      "M0_mean_per_paired_window", "C0_mean_per_paired_window",
                      "C0_minus_M0_nats_per_mpc"]
    for field in numeric_fields:
        left = pd.to_numeric(merged_scene[f"{field}_stored"], errors="coerce").to_numpy(float)
        right = pd.to_numeric(merged_scene[f"{field}_ref"], errors="coerce").to_numpy(float)
        mismatch = np.isfinite(left) ^ np.isfinite(right)
        if mismatch.any():
            score_error = np.inf
        finite = np.isfinite(left) & np.isfinite(right)
        if finite.any():
            score_error = max(score_error, float(np.max(np.abs(left[finite] - right[finite]))))
    check("scene_paired_scores_reproduced", merged_scene._merge.eq("both").all()
          and score_error <= 1e-10, {"scene_rows": len(scene_scores), "max_abs_error": score_error})

    # Recalculate selected path scores using a separate adaptive one-dimensional
    # integral, not the analysis module's fixed Gauss-Legendre rectangle helper.
    sample_keys = []
    for width in widths:
        subset = paths.loc[np.isclose(pd.to_numeric(paths.width_hz), width)]
        valid_diag = diagnostics.loc[np.isclose(pd.to_numeric(diagnostics.width_hz), width)
                                     & diagnostics.status.astype(str).eq("PASS")]
        held_scenes = sorted(valid_diag.outer_held_out_scene_id.astype(str).unique())
        if held_scenes:
            chosen_scenes = sorted(set([held_scenes[0], held_scenes[len(held_scenes) // 2],
                                        held_scenes[-1]]))
        else:
            chosen_scenes = []
        for scene in chosen_scenes:
            group = subset.loc[subset.outer_held_out_scene_id.astype(str).eq(scene)]
            if len(group):
                sample_keys.append((width, scene, group.iloc[len(group) // 2]["run_id"],
                                    group.iloc[len(group) // 2]["window_id"],
                                    group.iloc[len(group) // 2]["path_id"]))
    sample_keys = sample_keys[:int(quadrature_sample_n)]
    numeric_errors = {"M0_independent": [], "C0_copula": []}
    for width, scene, run_id, window_id, path_id in sample_keys:
        selected = paths.loc[np.isclose(pd.to_numeric(paths.width_hz), width)
                             & paths.outer_held_out_scene_id.astype(str).eq(scene)
                             & paths.run_id.astype(str).eq(str(run_id))
                             & paths.window_id.astype(str).eq(str(window_id))
                             & paths.path_id.astype(str).eq(str(path_id))]
        src = source.loc[source.run_id.astype(str).eq(str(run_id))
                         & source.window_id.astype(str).eq(str(window_id))
                         & source.path_id.astype(str).eq(str(path_id))]
        check(f"reference_sample_identity_{width:g}_{scene}", len(selected) == 1 and len(src) == 1,
              {"score_rows": len(selected), "source_rows": len(src)})
        row = next(src.itertuples(index=False))
        fit_rows = params.loc[params.outer_held_out_scene_id.astype(str).eq(scene)
                              & np.isclose(pd.to_numeric(params.width_hz), width)]
        fit_map = {}
        for fit_row in fit_rows.itertuples(index=False):
            if fit_row.status == "PASS":
                fit_map[str(fit_row.variable)] = {"family": str(fit_row.family),
                                                   "parameters": json.loads(fit_row.parameters_json)}
        if len(fit_map) != 3:
            continue
        score_row = selected.iloc[0]
        expected_m0 = _ref_marginal_score(row, fit_map, width)
        numeric_errors["M0_independent"].append(abs(expected_m0 - float(score_row.M0_independent)))
        diag = diagnostics.loc[diagnostics.outer_held_out_scene_id.astype(str).eq(scene)
                               & np.isclose(pd.to_numeric(diagnostics.width_hz), width)]
        if len(diag) == 1 and diag.iloc[0].status == "PASS":
            expected_c0 = _ref_copula_score(row, fit_map,
                                            json.loads(diag.iloc[0].correlation_json), width)
            numeric_errors["C0_copula"].append(abs(expected_c0 - float(score_row.C0_copula)))
    max_m0 = max(numeric_errors["M0_independent"], default=np.inf)
    max_c0 = max(numeric_errors["C0_copula"], default=np.inf)
    check("independent_adaptive_quadrature_recomputes_mixed_scores",
          len(numeric_errors["M0_independent"]) > 0
          and max_m0 <= tolerance
          and (len(numeric_errors["C0_copula"]) == 0 or max_c0 <= tolerance),
          {"sample_n": len(sample_keys), "M0_recomputed_n": len(numeric_errors["M0_independent"]),
           "C0_recomputed_n": len(numeric_errors["C0_copula"]),
           "M0_max_abs_error": max_m0,
           "C0_max_abs_error": max_c0 if numeric_errors["C0_copula"] else None,
           "C0_validation_scope": "PASS folds only; unavailable if no Copula fold fit passed",
           "tolerance": tolerance})

    result = {
        "status": "PASS_WITH_LIMITATIONS", "validated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "analysis_output_dir": str(output), "independent_validator_sha256": _sha256(Path(__file__).resolve()),
        "input_manifest": manifest, "check_n": len(checks), "failed_check_n": 0,
        "checks": checks, "score_sample_n": len(sample_keys),
        "max_abs_error_independent_quadrature_m0": max_m0,
        "max_abs_error_independent_quadrature_c0": max_c0 if numeric_errors["C0_copula"] else None,
        "scientific_scope": "fixed-bin Stage2 mark distribution; not adaptive SAGE output likelihood, ordered path generator, or physical channel truth",
        "limitation": "path rows within selected windows are not independent; Gate G requires broader scientific acceptance beyond numerical/identity checks",
    }
    (output / "independent_validation_fixed_bins.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    portable = {
        "status": result["status"], "validated_at_utc": result["validated_at_utc"],
        "independent_validator_sha256": result["independent_validator_sha256"],
        "input_sha256": {"features": manifest["features_sha256"],
                         "mpcs": manifest["mpc_sha256"]},
        "input_rows": {"selected_windows": int(len(windows)), "mpcs": int(len(source)),
                       "scenes": int(windows.scene_id.nunique()),
                       "stage2_run_ids": int(windows.run_id.nunique()),
                       "mpc_bearing_run_ids": int(source.run_id.nunique())},
        "check_n": result["check_n"], "failed_check_n": 0,
        "score_sample_n": result["score_sample_n"],
        "max_abs_error_independent_quadrature_m0": max_m0,
        "max_abs_error_independent_quadrature_c0": result[
            "max_abs_error_independent_quadrature_c0"],
        "interpretation": result["scientific_scope"],
        "limitation": result["limitation"],
        "analysis_source_sha256": code_manifest["analysis_source_sha256"],
        "result_file_sha256": output_hashes,
    }
    (output / "independent_validation_portable.json").write_text(
        json.dumps(portable, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    execution["validation"] = result["status"]
    execution["validator_sha256"] = result["independent_validator_sha256"]
    execution["validation_check_n"] = len(checks)
    execution["validated_at_utc"] = result["validated_at_utc"]
    (output / "execution_record.json").write_text(
        json.dumps(execution, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--mpcs", type=Path, default=DEFAULT_MPCS)
    parser.add_argument("--quadrature-sample-n", type=int, default=9)
    parser.add_argument("--tolerance", type=float, default=2e-6)
    args = parser.parse_args(argv)
    result = validate_result_package(args.output_dir, args.features, args.mpcs,
                                     args.quadrature_sample_n, args.tolerance)
    print(f"INDEPENDENT_VALIDATION={result['status']} checks={result['check_n']} "
          f"independent_quadrature_samples={result['score_sample_n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
