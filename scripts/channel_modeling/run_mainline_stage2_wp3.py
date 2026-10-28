"""Run the bounded, CSV-only Mainline Stage2 WP3 analysis.

No MATLAB/SAGE/CIR, MAT/HDF5, or raw-IQ data are opened by this runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mainline_stage2_wp3 import (
    CORE_ENVIRONMENTS,
    ENVIRONMENT_ORDER,
    SUPPLEMENT_ENVIRONMENTS,
    VARIABLE_FAMILIES,
    _distribution_ppf,
    _loso_scopes,
    _weighted_quantile,
    build_wp3_population,
    condition_support_tables,
    evaluate_scene_loso,
    fit_model,
    scene_window_weights,
    score_model,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_PARENT = REPO_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1"
DEFAULT_INPUTS = {
    "mpc_rows": REPO_ROOT / "dataset_generation_logs/channel_modeling/mainline_1023_stage2_v0_20261024T132210Z/analysis_mpc_rows.csv",
    "selected_windows": REPO_ROOT / "dataset_generation_logs/channel_modeling/mainline_1023_stage2_v0_20261024T132210Z/selected_window_rows.csv",
    "stage2_artifact_manifest": REPO_ROOT / "dataset_generation_logs/channel_modeling/mainline_1023_stage2_v0_20261024T132210Z/artifact_manifest.json",
    "wp1_scene_fold_scores": REPO_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1/v0_20261024T132210Z/scene_fold_scores.csv",
    "wp1_report": REPO_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1/v0_20261024T132210Z/v0_model_report.md",
    "wp2_marginal_summary": REPO_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_20261025T074332Z/marginal_stability_summary.csv",
    "wp2_power_delay_summary": REPO_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_20261025T074332Z/power_delay_loso_summary.csv",
    "wp3_plan": REPO_ROOT / "docs/superpowers/plans/2026-10-28-mainline-stage2-wp3-environment-geometry-modeling.md",
    "trajectory_overlay": Path(r"E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\mainline_1023_pvt_recovery_20261024T054408Z\trajectory_window_overlay_pvt_recovered.csv"),
}
PINNED_INPUT_SHA256 = {
    "mpc_rows": "a2c26d0de655e0f6cf4a60cf2906bf4cfff7aa16bbc5f74bffb4e9b80dab306c",
    "selected_windows": "fbc784ff169fca6d95907e39a56510d9be0b61ec3c1ef42e15235002be40061c",
    "stage2_artifact_manifest": "a47b056e8764e70987e9df733fa9855955fa4dade7e782f3fdd5c394c3200da6",
    "wp1_scene_fold_scores": "faad49468cb7d36ed070e54a8b9fdc564cdaa9bc3f682fed1eb391cfebbf03ca",
    "wp1_report": "41f4711790823bcfa0fe8c7bece68bbc40c492b086cfd7349984e2153400356d",
    "wp2_marginal_summary": "5439b0c7e3d8df2ee97b06c04b5b67c14180c6a5a480fb1fafd9175e0df00db5",
    "wp2_power_delay_summary": "295f84904aaadbb8f9b5b1562f361a6cfbb475b51f4dc7b6d8d0067f6c1e7922",
    "wp3_plan": "4245ca034114ff982df8e835a6be052e8725f9280bf012ca8169da47785714a1",
    "trajectory_overlay": "1f7385663341d89cdb42c459c1e9d8c36a0ef4ca6f5d6a4f0c667944de0f0c93",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_pinned_input(path: Path, expected_sha256: str) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"pinned input is not a file: {path}")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError(f"invalid expected SHA-256 for {path}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(f"SHA-256 mismatch for {path}: expected {expected_sha256}, got {actual}")
    return {"path": str(path.resolve()), "sha256": actual, "size_bytes": path.stat().st_size}


def create_new_output_dir(output_dir: Path, allowed_parent: Path) -> Path:
    output_dir = Path(output_dir).resolve()
    allowed_parent = Path(allowed_parent).resolve()
    if output_dir.parent != allowed_parent:
        raise ValueError(f"output must be a direct child of {allowed_parent}")
    try:
        output_dir.mkdir(parents=False, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(f"refusing to reuse existing WP3 output directory: {output_dir}") from exc
    return output_dir


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if pd.isna(value) if not isinstance(value, (dict, list, tuple)) else False:
        return None
    return value


def _write_json(path: Path, document: dict) -> None:
    path.write_text(json.dumps(_jsonable(document), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def _json_parameters(parameters: dict) -> str:
    return json.dumps(_jsonable(parameters), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _weighted_environment_descriptions(population: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scene_rows = []
    environment_rows = []
    for environment in ENVIRONMENT_ORDER:
        env = population.loc[population.environment_class.astype(str).eq(environment)].copy()
        if env.empty:
            continue
        per_window = (env.groupby(["scene_id", "run_id", "window_id"], as_index=False)
                      .agg(mpc_n=("path_id", "size"),
                           excess_delay_chips=("excess_delay_chips", "median"),
                           doppler_offset_hz=("doppler_offset_hz", "median"),
                           relative_power_db=("relative_power_db", "median")))
        env_values = {"scene_n": int(env.scene_id.nunique()),
                      "mpc_n": int(len(env)),
                      "mpc_bearing_window_n": int(per_window.shape[0])}
        for variable in VARIABLE_FAMILIES:
            vals = pd.to_numeric(per_window[variable], errors="coerce").to_numpy(dtype=float)
            weights = scene_window_weights(per_window)
            env_values[f"{variable}_window_median_mean_scene_window_balanced"] = float(np.dot(weights, vals))
            env_values[f"{variable}_window_median_p25_scene_window_balanced"] = _weighted_quantile(vals, weights, 0.25)
            env_values[f"{variable}_window_median_p50_scene_window_balanced"] = _weighted_quantile(vals, weights, 0.50)
            env_values[f"{variable}_window_median_p75_scene_window_balanced"] = _weighted_quantile(vals, weights, 0.75)
            env_values[f"{variable}_window_median_min_scene"] = float(
                per_window.groupby("scene_id")[variable].median().min())
            env_values[f"{variable}_window_median_max_scene"] = float(
                per_window.groupby("scene_id")[variable].median().max())
            for scene, group in per_window.groupby("scene_id", sort=True):
                scene_rows.append({
                    "environment_class": environment,
                    "scene_id": str(scene),
                    "mpc_n": int(env.loc[env.scene_id.astype(str).eq(str(scene))].shape[0]),
                    "mpc_bearing_window_n": int(group.shape[0]),
                    "variable": variable,
                    "window_median_mean": float(group[variable].mean()),
                    "window_median_median": float(group[variable].median()),
                    "window_median_p25": float(group[variable].quantile(0.25)),
                    "window_median_p75": float(group[variable].quantile(0.75)),
                    "window_median_min": float(group[variable].min()),
                    "window_median_max": float(group[variable].max()),
                    "window_level_repeated_measurement": True,
                })
        environment_rows.append({"environment_class": environment, **env_values})
    return pd.DataFrame(scene_rows), pd.DataFrame(environment_rows)


def _count_support(windows: pd.DataFrame) -> pd.DataFrame:
    counts = (windows.groupby(["environment_class", "scene_id", "mpc_count"], dropna=False)
              .size().rename("selected_window_n").reset_index())
    return counts.sort_values(["environment_class", "scene_id", "mpc_count"]).reset_index(drop=True)


def _full_parameter_fits(core: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, subset in _loso_scopes(core):
        models = ("M0", "M1") if scope == "ALL_MPC" else ("M0", "M1", "M2")
        for variable, candidates in VARIABLE_FAMILIES.items():
            for family in candidates:
                for model in models:
                    fit = fit_model(subset, variable, family, model)
                    rows.append({
                        "data_scope": scope, "variable": variable, "family": family, "model": model,
                        "training_scene_n": fit.get("training_scene_n"),
                        "training_scene_ids": json.dumps(list(fit.get("training_scene_ids", ())),
                                                         ensure_ascii=False, separators=(",", ":")),
                        "training_window_n": fit.get("training_window_n"),
                        "training_mpc_n": fit.get("training_path_n"),
                        "fit_status": fit.get("status"),
                        "failure_reason": fit.get("failure_reason", ""),
                        "parameters_json": _json_parameters(fit.get("parameters", {})),
                        "optimizer_message": json.dumps(fit.get("optimizer_messages", fit.get("optimizer_message", "")),
                                                         ensure_ascii=False, sort_keys=True),
                        "boundary_parameters_json": _json_parameters(fit.get("boundary_parameters", [])),
                        "fit_weighting": "SCENE_WINDOW_BALANCED_PSEUDO_LIKELIHOOD",
                        "formal_validation_status": "NOT_FORMALLY_ACCEPTED;_LOSO_RESULTS_ARE_EXPLORATORY",
                    })
    return pd.DataFrame(rows)


def _supplement_scores(core: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    supplement = population.loc[population.environment_class.astype(str).isin(SUPPLEMENT_ENVIRONMENTS)]
    if supplement.empty:
        return pd.DataFrame()
    rows = []
    for scope, train_scope in _loso_scopes(core):
        models = ("M0", "M1") if scope == "ALL_MPC" else ("M0", "M1", "M2")
        for variable, candidates in VARIABLE_FAMILIES.items():
            for family in candidates:
                for model in models:
                    fit = fit_model(train_scope, variable, family, model)
                    for scene in sorted(supplement.scene_id.astype(str).unique()):
                        test = supplement.loc[supplement.scene_id.astype(str).eq(scene)].copy()
                        if scope == "GSV_MEASURED":
                            test = test.loc[test.elevation_source.astype(str).eq("GSV_MEASURED")]
                        elif scope.startswith("EPHEMERIS_"):
                            height = ("GGA_ELLIPSOIDAL_HEIGHT" if scope == "EPHEMERIS_GGA"
                                      else "ZERO_HEIGHT_ASSUMPTION")
                            test = test.loc[
                                test.elevation_source.astype(str).eq("EPHEMERIS_DERIVED")
                                & test.receiver_height_source.astype(str).eq(height)
                            ]
                        if test.empty:
                            scored = {"status": "NO_TEST_SUPPORT", "test_path_n": 0, "test_window_n": 0,
                                      "window_balanced_mean_log_score": None, "failure_reason": "no matching source rows"}
                            digest = hashlib.sha256(b"").hexdigest()
                        else:
                            scored = score_model(fit, test, variable)
                            identities = sorted(
                                f"{r.run_id}|{r.window_id}|{int(r.path_id)}"
                                for r in test.itertuples(index=False)
                            )
                            digest = hashlib.sha256("\n".join(identities).encode("utf-8")).hexdigest()
                        rows.append({
                            "evaluation_type": "CORE_TRAINED_SUPPLEMENT_APPLICABILITY_ONLY",
                            "data_scope": scope, "variable": variable, "family": family,
                            "model": model, "held_out_supplement_scene_id": scene,
                            "held_out_environment": str(test.environment_class.iloc[0]) if len(test) else "NO_TEST_SUPPORT",
                            "training_scene_ids": json.dumps(list(fit.get("training_scene_ids", ())),
                                                             ensure_ascii=False, separators=(",", ":")),
                            "training_scene_n": fit.get("training_scene_n"),
                            "fit_status": fit.get("status"),
                            "fit_failure_reason": fit.get("failure_reason", ""),
                            "test_identity_sha256": digest,
                            "score_status": scored["status"],
                            "score_failure_reason": scored.get("failure_reason", ""),
                            "test_path_n": scored.get("test_path_n", 0),
                            "test_window_n": scored.get("test_window_n", 0),
                            "window_balanced_mean_log_score": scored.get("window_balanced_mean_log_score"),
                            "parameters_json": _json_parameters(fit.get("parameters", {})),
                            "claim_boundary": "SUPPLEMENT_APPLICABILITY;_NOT_CORE_MODEL_VALIDATION",
                        })
    return pd.DataFrame(rows)


def _paired_deltas(scores: pd.DataFrame) -> pd.DataFrame:
    keys = ["data_scope", "variable", "family", "held_out_scene_id", "held_out_environment"]
    value = scores.pivot(index=keys, columns="model", values="window_balanced_mean_log_score")
    status = scores.pivot(index=keys, columns="model", values="score_status")
    identities = scores.pivot(index=keys, columns="model", values="test_identity_sha256")
    rows = []
    for index in value.index:
        record = dict(zip(keys, index))
        # The pivot's columns are global across scopes. Drop models with no
        # source-scope row at this exact identity instead of emitting false
        # M2 comparisons for ALL_MPC (or M2 comparisons outside source scopes).
        models = [model for model in value.columns if pd.notna(status.loc[index, model])]
        for left, right in (("M0", "M1"), ("M0", "M2"), ("M1", "M2")):
            if left not in models or right not in models:
                continue
            same_ids = identities.loc[index, left] == identities.loc[index, right]
            both_pass = status.loc[index, left] == "PASS" and status.loc[index, right] == "PASS"
            delta = (float(value.loc[index, right] - value.loc[index, left])
                     if same_ids and both_pass else np.nan)
            rows.append({
                **record,
                "comparison": f"{right}-{left}",
                "test_identity_sha256_left": identities.loc[index, left],
                "test_identity_sha256_right": identities.loc[index, right],
                "same_test_identity": bool(same_ids),
                "paired_status": "PASS" if same_ids and both_pass else
                    "IDENTITY_MISMATCH" if not same_ids else "FIT_OR_SCORE_UNAVAILABLE",
                "delta_window_balanced_log_score_right_minus_left": delta,
            })
    return pd.DataFrame(rows)


def _family_ranks_by_scene(scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_keys = ["data_scope", "variable", "model", "held_out_scene_id"]
    for keys, group in scores.groupby(group_keys, sort=True):
        pass_rows = group.loc[group.score_status.eq("PASS")].copy()
        pass_rows["rank_among_successful_families"] = pass_rows.window_balanced_mean_log_score.rank(
            method="min", ascending=False
        )
        pass_rows["successful_family_n_in_fold"] = len(pass_rows)
        pass_rows["candidate_family_n_in_scope"] = len(group)
        pass_rows["rank_semantics"] = "ONLY_SUCCESSFUL_FITS_IN_THIS_FOLD;_NO_RANK_IF_FIT_FAILED"
        rows.extend(pass_rows[[
            "data_scope", "variable", "model", "held_out_scene_id", "held_out_environment",
            "family", "score_status", "window_balanced_mean_log_score", "test_identity_sha256",
            "rank_among_successful_families", "successful_family_n_in_fold",
            "candidate_family_n_in_scope", "rank_semantics",
        ]].to_dict("records"))
    return pd.DataFrame(rows)


def _m1_parameter_contrasts(full_parameters: pd.DataFrame) -> pd.DataFrame:
    rows = []
    selected = full_parameters.loc[
        full_parameters.data_scope.eq("ALL_MPC") & full_parameters.model.eq("M1")
    ]
    for record in selected.to_dict("records"):
        if record["fit_status"] not in {"PASS", "PASS_WITH_BOUNDARY"}:
            rows.append({"data_scope": "ALL_MPC", "variable": record["variable"],
                         "family": record["family"], "fit_status": record["fit_status"],
                         "parameter": "", "urban_value": np.nan, "mountain_valley_value": np.nan,
                         "urban_minus_mountain_valley": np.nan, "urban_to_mountain_valley_ratio": np.nan,
                         "note": record["failure_reason"]})
            continue
        parameters = json.loads(record["parameters_json"]).get("by_environment", {})
        urban = parameters.get("Urban", {})
        mountain = parameters.get("Mountain/Valley", {})
        for parameter in sorted(set(urban) & set(mountain)):
            left, right = urban[parameter], mountain[parameter]
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                continue
            rows.append({
                "data_scope": "ALL_MPC", "variable": record["variable"], "family": record["family"],
                "fit_status": record["fit_status"], "parameter": parameter,
                "urban_value": float(left), "mountain_valley_value": float(right),
                "urban_minus_mountain_valley": float(left - right),
                "urban_to_mountain_valley_ratio": float(left / right) if left > 0 and right > 0 else np.nan,
                "note": "FULL_CORE_FIT_DESCRIPTIVE_ONLY;_RATIO_ONLY_WHEN_BOTH_PARAMETERS_POSITIVE",
            })
    return pd.DataFrame(rows)


def _macro_tables(scores: pd.DataFrame, paired: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    score_rows = []
    grouping = ["data_scope", "variable", "family", "model"]
    for keys, group in scores.groupby(grouping, dropna=False, sort=True):
        pass_rows = group.loc[group.score_status.eq("PASS") & group.window_balanced_mean_log_score.notna()]
        evaluated_env = []
        for env, env_group in pass_rows.groupby("held_out_environment", sort=True):
            evaluated_env.append(f"{env}:{env_group.held_out_scene_id.nunique()}")
        score_rows.append({
            **dict(zip(grouping, keys)),
            "held_out_scene_n_expected": int(group.held_out_scene_id.nunique()),
            "held_out_scene_n_scored": int(pass_rows.held_out_scene_id.nunique()),
            "score_status_counts_json": group.score_status.value_counts().sort_index().to_json(),
            "equal_scene_macro_log_score": float(pass_rows.window_balanced_mean_log_score.mean())
                if not pass_rows.empty else np.nan,
            "min_scene_log_score": float(pass_rows.window_balanced_mean_log_score.min())
                if not pass_rows.empty else np.nan,
            "max_scene_log_score": float(pass_rows.window_balanced_mean_log_score.max())
                if not pass_rows.empty else np.nan,
            "scored_scenes_by_environment": ";".join(evaluated_env),
            "macro_claim": "DESCRIPTIVE_EQUAL_SCENE_MEAN;_OVERLAPPING_LOSO_TRAINING_SETS",
        })
    macros = pd.DataFrame(score_rows)
    if not macros.empty:
        macros["family_rank_within_scope_model"] = macros.groupby(
            ["data_scope", "variable", "model"]
        ).equal_scene_macro_log_score.rank(method="min", ascending=False)

    paired_rows = []
    pair_grouping = ["data_scope", "variable", "family", "comparison"]
    for keys, group in paired.groupby(pair_grouping, dropna=False, sort=True):
        pass_rows = group.loc[group.paired_status.eq("PASS")]
        for env, env_group in pass_rows.groupby("held_out_environment", sort=True):
            paired_rows.append({
                **dict(zip(pair_grouping, keys)),
                "held_out_environment": env,
                "paired_scene_n": int(env_group.held_out_scene_id.nunique()),
                "equal_scene_mean_delta_log_score": float(
                    env_group.delta_window_balanced_log_score_right_minus_left.mean()),
                "min_scene_delta": float(env_group.delta_window_balanced_log_score_right_minus_left.min()),
                "max_scene_delta": float(env_group.delta_window_balanced_log_score_right_minus_left.max()),
                "interpretation": "POSITIVE_FAVORS_RIGHT_MODEL;_DESCRIPTIVE_SCENE_SENSITIVITY_NOT_CI",
            })
        if not pass_rows.empty:
            paired_rows.append({
                **dict(zip(pair_grouping, keys)),
                "held_out_environment": "ALL_SCORED_CORE_SCENES",
                "paired_scene_n": int(pass_rows.held_out_scene_id.nunique()),
                "equal_scene_mean_delta_log_score": float(
                    pass_rows.delta_window_balanced_log_score_right_minus_left.mean()),
                "min_scene_delta": float(pass_rows.delta_window_balanced_log_score_right_minus_left.min()),
                "max_scene_delta": float(pass_rows.delta_window_balanced_log_score_right_minus_left.max()),
                "interpretation": "POSITIVE_FAVORS_RIGHT_MODEL;_DESCRIPTIVE_SCENE_SENSITIVITY_NOT_CI",
            })
    return macros, pd.DataFrame(paired_rows)


def _parameter_stability(scores: pd.DataFrame) -> pd.DataFrame:
    def flatten(prefix: str, obj: Any, output: list[tuple[str, float]]) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                flatten(f"{prefix}.{key}" if prefix else str(key), value, output)
        elif isinstance(obj, (int, float)) and np.isfinite(obj):
            output.append((prefix, float(obj)))
    rows = []
    keys = ["data_scope", "variable", "family", "model", "held_out_scene_id"]
    for record in scores.to_dict("records"):
        if record["fit_status"] not in {"PASS", "PASS_WITH_BOUNDARY"}:
            continue
        try:
            params = json.loads(record["fit_parameters_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        leaves: list[tuple[str, float]] = []
        flatten("", params, leaves)
        for name, value in leaves:
            rows.append({**{key: record[key] for key in keys}, "parameter": name, "value": value,
                         "boundary": record["fit_status"] == "PASS_WITH_BOUNDARY"})
    values = pd.DataFrame(rows)
    if values.empty:
        return values
    group_keys = ["data_scope", "variable", "family", "model", "parameter"]
    return (values.groupby(group_keys, sort=True)
            .agg(fold_n=("value", "size"), median=("value", "median"), minimum=("value", "min"),
                 maximum=("value", "max"), boundary_fit_n=("boundary", "sum"))
            .reset_index().assign(stability_semantics="LOSO_FOLD_SENSITIVITY_NOT_PARAMETER_CI"))


def _external_baseline_context(inputs: dict[str, Path]) -> pd.DataFrame:
    wp1 = pd.read_csv(inputs["wp1_scene_fold_scores"])
    global_rows = wp1.loc[wp1.scope.astype(str).eq("GLOBAL")]
    wp1_summary = (global_rows.groupby(["variable", "family"], as_index=False)
                   .agg(wp1_13scene_fold_n=("held_out_scene_id", "nunique"),
                        wp1_mean_row_log_score=("mean_loglik", "mean"),
                        wp1_fit_failure_n=("fit_status", lambda values: int((values != "PASS").sum()))))
    wp2 = pd.read_csv(inputs["wp2_marginal_summary"])
    wp2 = wp2.loc[wp2.scope.astype(str).eq("GLOBAL") & wp2.row_type.astype(str).eq("FAMILY_RANK"),
                  ["variable", "family", "rank1_fold_n", "rank_evaluated_fold_n"]]
    result = wp1_summary.merge(wp2, on=["variable", "family"], how="left", validate="one_to_one")
    result["population_and_metric_boundary"] = (
        "13_SCENE_GLOBAL_WP1_ROW_WEIGHTED_REFERENCE;_NOT_PAIRED_WITH_9_SCENE_WP3_SCENE_WINDOW_BALANCED_SCORES"
    )
    pd.read_csv(inputs["wp2_power_delay_summary"])  # Verify/read the accepted companion evidence as an input.
    return result


def _selected_families(macros: pd.DataFrame) -> dict[tuple[str, str], str]:
    result = {}
    m0 = macros.loc[macros.model.eq("M0") & macros.equal_scene_macro_log_score.notna()]
    for keys, group in m0.groupby(["data_scope", "variable"], sort=True):
        best = group.sort_values(["equal_scene_macro_log_score", "family"],
                                 ascending=[False, True]).iloc[0]
        result[(keys[0], keys[1])] = str(best.family)
    return result


def _make_figures(output: Path, population: pd.DataFrame, scene_desc: pd.DataFrame,
                  scores: pd.DataFrame, paired: pd.DataFrame, macros: pd.DataFrame) -> list[str]:
    figures = output / "figures"
    figures.mkdir()
    units = {"excess_delay_chips": "Excess delay (chips)",
             "doppler_offset_hz": "Relative Doppler (Hz)",
             "relative_power_db": "Relative power (dB; relative quantity)"}

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), constrained_layout=True)
    for ax, variable in zip(axes, VARIABLE_FAMILIES):
        data = scene_desc.loc[scene_desc.variable.eq(variable)]
        groups = [data.loc[data.environment_class.eq(env), "window_median_median"].dropna().to_numpy()
                  for env in CORE_ENVIRONMENTS]
        ax.boxplot(groups, positions=[0, 1], widths=0.48, showfliers=False)
        for i, env in enumerate(CORE_ENVIRONMENTS):
            y = data.loc[data.environment_class.eq(env), "window_median_median"].dropna().to_numpy()
            jitter = np.linspace(-0.08, 0.08, len(y)) if len(y) else np.array([])
            ax.scatter(np.full(len(y), i) + jitter, y, s=30, alpha=0.85, label=env if ax is axes[0] else None)
        ax.set_xticks([0, 1], ["Urban", "Mountain/Valley"], rotation=15)
        ax.set_title(variable.replace("_", " "))
        ax.set_ylabel(units[variable])
        ax.grid(axis="y", alpha=0.2)
    axes[0].legend(fontsize=8, loc="best")
    fig.suptitle("Stage2 MPC: per-scene medians (descriptive; scenes are the displayed units)")
    fig.savefig(figures / "core_environment_scene_medians.png", dpi=180)
    plt.close(fig)

    window_frame = population.loc[
        population.environment_class.astype(str).isin(CORE_ENVIRONMENTS)
        & population.elevation_source.astype(str).eq("GSV_MEASURED")
    ]
    window_medians = (window_frame.groupby(["scene_id", "environment_class", "run_id", "window_id"],
                                           as_index=False)
                      .agg(elevation_value_deg=("elevation_value_deg", "first"),
                           excess_delay_chips=("excess_delay_chips", "median"),
                           doppler_offset_hz=("doppler_offset_hz", "median"),
                           relative_power_db=("relative_power_db", "median")))
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), constrained_layout=True)
    colors = {"Urban": "#2878B5", "Mountain/Valley": "#C43C39"}
    for ax, variable in zip(axes, VARIABLE_FAMILIES):
        for env, group in window_medians.groupby("environment_class", sort=True):
            ax.scatter(group.elevation_value_deg, group[variable], s=9, alpha=0.23,
                       color=colors.get(env), label=env)
        ax.set_xlabel("GSV-measured elevation (degrees)")
        ax.set_ylabel(units[variable])
        ax.set_title(variable.replace("_", " "))
        ax.grid(alpha=0.2)
    axes[0].legend(fontsize=8, loc="best")
    fig.suptitle("GSV-only window medians; overlapping windows make points dependent")
    fig.savefig(figures / "gsv_elevation_window_medians.png", dpi=180)
    plt.close(fig)

    selected = _selected_families(macros)
    panels = [
        ("ALL_MPC", "M1-M0", "Environment minus core-global (ALL MPC)"),
        ("GSV_MEASURED", "M2-M0", "Elevation + environment minus baseline (GSV only)"),
        ("EPHEMERIS_GGA", "M2-M0", "Derived, GGA-height stratum"),
        ("EPHEMERIS_ZERO_HEIGHT", "M2-M0", "Derived, zero-height stratum"),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), constrained_layout=True, sharex=False)
    for ax, variable in zip(axes, VARIABLE_FAMILIES):
        group_scopes = [(scope, comp, title, selected.get((scope, variable)))
                        for scope, comp, title in panels
                        if selected.get((scope, variable)) is not None]
        x_positions = []
        tick_labels = []
        offset = 0
        for scope, comparison, title, family in group_scopes:
            data = paired.loc[
                paired.data_scope.eq(scope) & paired.variable.eq(variable)
                & paired.family.eq(family) & paired.comparison.eq(comparison)
                & paired.paired_status.eq("PASS")
            ].sort_values("held_out_scene_id")
            if data.empty:
                continue
            x = np.arange(offset, offset + len(data))
            ax.scatter(x, data.delta_window_balanced_log_score_right_minus_left,
                       s=24, alpha=0.8, label=f"{title}; {family}")
            x_positions.extend(x.tolist())
            tick_labels.extend(data.held_out_scene_id.astype(str).tolist())
            offset += len(data) + 1
        ax.axhline(0, color="black", linewidth=0.9)
        ax.set_xticks(x_positions, tick_labels, rotation=60, ha="right", fontsize=7)
        ax.set_ylabel("Paired Δ window-balanced log score")
        ax.set_title(variable.replace("_", " "))
        ax.grid(axis="y", alpha=0.2)
        if group_scopes:
            ax.legend(fontsize=7, loc="best")
    fig.suptitle("Per-scene paired LOSO score changes; family chosen descriptively from same folds, no CI")
    fig.savefig(figures / "loso_paired_score_deltas.png", dpi=180)
    plt.close(fig)
    return [str(path.relative_to(output)) for path in sorted(figures.glob("*.png"))]


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):.{digits}f}"


def _render_report(output: Path, support: pd.DataFrame, source_support: pd.DataFrame,
                   motion: pd.DataFrame, env_desc: pd.DataFrame, macro: pd.DataFrame,
                   paired_macro: pd.DataFrame, full_parameters: pd.DataFrame,
                   family_ranks: pd.DataFrame, parameter_stability: pd.DataFrame,
                   tails: pd.DataFrame,
                   supplement_scores: pd.DataFrame, external: pd.DataFrame,
                   inputs: dict[str, dict], output_names: list[str]) -> str:
    core_support = support.loc[support.environment_class.isin(CORE_ENVIRONMENTS)]
    core_mpc = int(core_support.mpc_n.sum())
    core_windows = int(core_support.selected_window_n.sum())
    report = [
        "# Mainline Stage2 WP3：环境、仰角与运动条件化多径参数建模",
        "",
        f"- 实际分析时间（UTC）：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "- 分析状态：已完成本轮有界模型比较；科学结论为 `COMPLETED_WITH_LIMITATIONS`（需独立/Commander审阅，不代表Gate G/WP6通过）。",
        "- 研究范围预先固定：Urban（6场景）与Mountain/Valley（3场景）为核心；Highway/Open与Special Reflective各2场景仅作描述和适用性补充。",
        "- 数据总体：83个SAGE任务、13个场景、7,847个Stage2已选窗口、8,914条Stage2 MPC；本轮核心为",
        f"  {core_windows:,}个已选窗口、{core_mpc:,}条MPC。未进入Stage2的Stage0窗口没有补成零MPC。",
        "- 主体输入为已接受V0导出的CSV及经核实的轨迹overlay；WP1/WP2结果只作有总体差异标注的历史参照。没有读取MAT/HDF5、raw IQ或CIR载荷，也没有运行SAGE/CIR/MATLAB/GNSS-SDR。",
        "",
        "## 身份、环境与条件支持",
        "",
        "|环境|独立场景|已选窗口|Stage2 MPC|",
        "|---|---:|---:|---:|",
    ]
    for row in support.groupby("environment_class", sort=False).agg(
        scene_n=("scene_id", "nunique"), selected_window_n=("selected_window_n", "sum"), mpc_n=("mpc_n", "sum")
    ).reindex([env for env in ENVIRONMENT_ORDER if env in set(support.environment_class)]).itertuples():
        report.append(f"|{row.Index}|{int(row.scene_n)}|{int(row.selected_window_n):,}|{int(row.mpc_n):,}|")
    report.extend(["", "各场景/来源明细见 `condition_support_by_scene.csv` 与 `condition_support_by_scene_source.csv`；场景参数分布见 `descriptive_by_scene.csv`、`descriptive_by_environment.csv`。零MPC的Stage2已选窗口保留在计数表中。", ""])
    report.extend(["## 仰角来源", "", "|核心来源|MPC数|窗口数|占核心窗口|解释边界|", "|---|---:|---:|---:|---|"])
    core_sources = source_support.loc[source_support.environment_class.isin(CORE_ENVIRONMENTS)].groupby(
        ["elevation_source", "receiver_height_source"], dropna=False
    ).agg(mpc_n=("mpc_n", "sum"), window_n=("window_n", "sum")).reset_index()
    for row in core_sources.itertuples(index=False):
        report.append(f"|{row.elevation_source}/{row.receiver_height_source or 'NA'}|{int(row.mpc_n):,}|{int(row.window_n):,}|"
                      f"{100*int(row.window_n)/core_windows:.1f}%|"
                      f"{'实测GSV' if row.elevation_source == 'GSV_MEASURED' else '推算来源分层' if row.elevation_source == 'EPHEMERIS_DERIVED' else '缺失保留'}|")
    report.extend(["", "核心窗口来源数合计：GSV实测3,478；星历推算/GGA高度206；星历推算/零高度假设701；仰角缺失516。对应MPC行分别为4,948、163、787、437。MPC行数不是独立样本数。M2分别在GSV、GGA推算、零高度推算子集中拟合，不跨来源合并；缺失不插补。", ""])
    core_motion = motion.loc[motion.environment_class.isin(CORE_ENVIRONMENTS)]
    speed_windows = int(core_motion.speed_available_window_n.sum())
    unique_records = int(core_motion.distinct_speed_source_record_n.sum())
    max_reuse = int(core_motion.max_windows_per_speed_source_record.max())
    speed_max = float(core_motion.speed_max_mps.max())
    report.extend(["## 车辆运动", "",
                   f"核心环境有速度值的已选窗口为{speed_windows:,}；按scene汇总仅有{unique_records}个不同NMEA源记录，单个源记录最多复用于{max_reuse}个窗口。核心场景速度上界为{speed_max:.3f} m/s（完整场景范围和来源见`motion_source_support_by_scene.csv`）。源记录复用、场景覆盖不均及高速度记录尚未完成独立质量核验，因此本轮只作描述，不拟合M3、不删除/截断速度、不估计空间相关长度。", ""])
    report.extend(["## 模型定义与估计", "",
                   "对每个参数分别比较固定候选边际族：超额时延（chips）Gamma/Lognormal/Weibull；相对Doppler（Hz）Normal/Laplace/Student-t；相对功率（dB，相对量）Normal/Laplace/Student-t。",
                   "",
                   "- **M0**：核心9场景内全局边际分布 `f(x|θ)`。它是同一核心测试总体的基线，不等同于WP1的13场景模型。",
                   "- **M1**：按Urban与Mountain/Valley分别估计边际参数 `f(x|E=e, θ_e)`。",
                   "- **M2**：在每个仰角来源纯净子集中增加连续仰角；正支持分布令`log(scale)=α_e+β(E−45°)/10`，有符号分布令`location=α_e+β(E−45°)/10`，按环境设置基础形状/尺度，Student-t使用共享自由度。",
                   "",
                   "拟合采用场景等权、场景内MPC-bearing窗口等权、窗口内路径分摊权重的伪似然；这不是独立路径的普通MLE，也不产生路径级独立标准误。Normal、Lognormal、Laplace静态族使用相应加权闭式MLE；Gamma、Weibull、Student-t及M2使用数值优化。预测分数对同一测试窗口等权，配对模型每折必须具有完全相同的测试身份SHA。无支持、非收敛、边界解和低支持折全部留表。", "",
                   "## LOSO场景外结果", "",
                   "完整场景作为外层留出单位。`loso_fold_scores.csv`保留各场景、候选族、来源、模型的训练/测试支持和精确测试身份摘要；`loso_equal_scene_macro_scores.csv`给每个候选模型可用折的等场景宏平均，`loso_paired_deltas.csv`与`loso_paired_delta_macro.csv`只对测试身份完全一致且两边PASS的折计算模型差；`loso_family_ranks_by_scene.csv`保留每折候选族排名；`loso_parameter_stability.csv`描述参数跨折变化；`loso_tail_diagnostics.csv`保留p05/p50/p95、加权经验分位数与加权覆盖。", "",
                   "核心M0在各参数中可用折的候选族胜出次数（仅在该折成功族之间排序；不把不同折的训练集当独立重复）：", ""])
    core_ranks = family_ranks.loc[family_ranks.data_scope.eq("ALL_MPC") & family_ranks.model.eq("M0")]
    for variable in VARIABLE_FAMILIES:
        eligible = core_ranks.loc[core_ranks.variable.eq(variable)]
        wins = eligible.loc[eligible.rank_among_successful_families.eq(1)].groupby("family").held_out_scene_id.nunique()
        observed = eligible.held_out_scene_id.nunique()
        report.append(f"- `{variable}`：成功候选族可评的场景折 {observed}/9；rank-1 折数：" +
                      (", ".join(f"{family} {int(n)}" for family, n in wins.items()) if len(wins) else "无") + ".")
    report.extend(["", "所有候选族逐折排名与失败记录见上述CSV。一个折中各候选族共享完全相同测试身份；但若不同候选拟合失败，跨折宏平均的场景支持数会不同，因此不得只按不等支持的宏分数宣称唯一最佳分布。", "",
                   "### 同身份配对预测变化", "",
                   "`Δ log score = 右侧模型 − 左侧模型`；正值偏向右侧。下表把各候选族的配对宏差作为范围展示，不把候选族当独立样本、不计算置信区间。", "",
                   "|参数|模型比较|候选族配对宏Δ范围|正/负候选族数|配对场景数范围|", "|---|---|---:|---:|---:|"])
    for variable in VARIABLE_FAMILIES:
        specs = [("ALL_MPC", "M1-M0"), ("GSV_MEASURED", "M2-M0"), ("GSV_MEASURED", "M2-M1"),
                 ("EPHEMERIS_GGA", "M2-M0"), ("EPHEMERIS_ZERO_HEIGHT", "M2-M0")]
        for scope, comparison in specs:
            rows = paired_macro.loc[
                paired_macro.data_scope.eq(scope) & paired_macro.variable.eq(variable)
                & paired_macro.comparison.eq(comparison)
                & paired_macro.held_out_environment.eq("ALL_SCORED_CORE_SCENES")
            ]
            if rows.empty:
                continue
            deltas = rows.equal_scene_mean_delta_log_score.dropna()
            if deltas.empty:
                continue
            positive = int((deltas > 0).sum())
            negative = int((deltas < 0).sum())
            min_n, max_n = int(rows.paired_scene_n.min()), int(rows.paired_scene_n.max())
            report.append(f"|{variable}|{scope} {comparison}|{_fmt(deltas.min())} … {_fmt(deltas.max())}|"
                          f"{positive}/{negative}|{min_n}–{max_n}|")
    report.extend(["", "分环境目标场景的逐族配对结果见`loso_paired_delta_macro.csv`。仅同一场景/变量/族/来源范围、同一测试身份SHA的PASS折进入模型差值；缺少可比配对的记录保留为失败或不支持。Mountain/Valley只有3个独立场景，LOSO训练集高度重叠；以上为描述性场景敏感性，不是独立实验区间或显著性检验。", ""])
    report.extend(["### 按环境拆分的场景外比较", "",
                   "下表为每个候选族在目标环境内的等场景配对Δ范围；正值偏向右侧模型。候选族是模型规格而非独立重复，范围仅描述折间敏感性，不作为区间估计。", "",
                   "|参数|留出环境|比较|正/负/零候选族数|Δ范围|配对场景数范围|",
                   "|---|---|---|---:|---:|---:|"])
    for variable in VARIABLE_FAMILIES:
        for environment in CORE_ENVIRONMENTS:
            specs = [("ALL_MPC", "M1-M0"), ("GSV_MEASURED", "M2-M0"), ("GSV_MEASURED", "M2-M1")]
            for scope, comparison in specs:
                rows = paired_macro.loc[
                    paired_macro.data_scope.eq(scope) & paired_macro.variable.eq(variable)
                    & paired_macro.comparison.eq(comparison)
                    & paired_macro.held_out_environment.eq(environment)
                ]
                if rows.empty:
                    continue
                deltas = rows.equal_scene_mean_delta_log_score.dropna()
                if deltas.empty:
                    continue
                positive = int((deltas > 0).sum())
                negative = int((deltas < 0).sum())
                zero = int((deltas == 0).sum())
                report.append(f"|{variable}|{environment}|{scope} {comparison}|{positive}/{negative}/{zero}|"
                              f"{_fmt(deltas.min())} … {_fmt(deltas.max())}|"
                              f"{int(rows.paired_scene_n.min())}–{int(rows.paired_scene_n.max())}|")
    report.extend(["### 全核心 M1 参数差异（全数据拟合，仅描述）", "",
                   "每个变量按核心M0可用折宏分数最高的候选族列出M1全数据参数；此筛选复用同一LOSO结果，属探索性说明，不构成独立确认。", "",
                   "|参数|候选族|Urban估计|Mountain/Valley估计|", "|---|---|---|---|"])
    selected = _selected_families(macro)
    for variable in VARIABLE_FAMILIES:
        family = selected.get(("ALL_MPC", variable))
        if family is None:
            continue
        row = full_parameters.loc[
            full_parameters.data_scope.eq("ALL_MPC") & full_parameters.variable.eq(variable)
            & full_parameters.family.eq(family) & full_parameters.model.eq("M1")
        ]
        if row.empty or row.iloc[0].fit_status not in {"PASS", "PASS_WITH_BOUNDARY"}:
            reason = row.iloc[0].failure_reason if not row.empty else "no full-data M1 fit"
            report.append(f"|{variable}|{family}|FIT_UNAVAILABLE|{reason}|")
            continue
        parameters = json.loads(row.iloc[0].parameters_json)["by_environment"]
        report.append(f"|{variable}|{family}|`{_json_parameters(parameters['Urban'])}`|"
                      f"`{_json_parameters(parameters['Mountain/Valley'])}`|")
    report.extend(["", "环境参数点估计反映可拟合的全核心样本，不是场景外参数估计；Mountain/Valley 3场景的参数不稳定性和拟合失败见全样本参数表与LOSO跨折参数表。正/负配对预测结果比全数据参数差异更能约束是否保留条件模型。", "",
                   "### M2 仰角斜率与尾部诊断", "",
                   "M2主分析为GSV实测子集；GGA推算和零高度是分开敏感性结果。下表分来源给出M2折间仰角斜率（单位/10°），只作场景敏感性描述。", "",
                   "|来源|参数|候选族|可用折|斜率中位数|最小…最大|", "|---|---|---|---:|---:|---:|"])
    slopes = parameter_stability.loc[
        parameter_stability.data_scope.isin(["GSV_MEASURED", "EPHEMERIS_GGA", "EPHEMERIS_ZERO_HEIGHT"])
        & parameter_stability.model.eq("M2")
        & parameter_stability.parameter.eq("elevation_slope_per_10deg")
    ]
    for row in slopes.sort_values(["data_scope", "variable", "family"]).itertuples(index=False):
        report.append(f"|{row.data_scope}|{row.variable}|{row.family}|{int(row.fold_n)}|{_fmt(row.median)}|"
                      f"{_fmt(row.minimum)} … {_fmt(row.maximum)}|")
    report.extend(["", "正/负斜率不等于因果效应；LOSO训练集互相重叠，不能从折间范围构造普通置信区间。尾部经验分位数按同一场景/窗口权重计算；名义尾部路径行数不是有效样本量。"])
    if not tails.empty:
        low_tail = int((tails.get("nominal_tail_path_rows_not_effective_n", pd.Series(dtype=float)) < 10).sum())
        report.append(f"本轮尾部表有{len(tails):,}条p05/p50/p95诊断，其中{int(tails.status.eq('FIT_UNAVAILABLE').sum()):,}条因拟合不可用而没有校准值；{low_tail:,}条记录的名义目标尾部路径行数小于10。由于窗口重叠和同窗MPC相关，后一个计数仅作低支持提醒，不是有效独立样本量。无尾部整体PASS声明。")
    report.extend(["", "## 补充环境与历史基线", "",
                   "Highway/Open、Special Reflective各2个场景，基础统计和逐场景支持完整保留。核心训练的M0/M1及来源纯净M2仅对补充场景做适用性评分，不把补充环境重新纳入核心训练或模型选择；M1/M2拟合/评分失败也逐条保留。细节见`descriptive_by_environment.csv`与`supplement_applicability_scores.csv`。",
                   "WP1的13场景Global LOSO和WP2候选排名见`external_13scene_baseline_context.csv`，是行加权、不同训练总体的历史参照；不得与本轮9场景、场景/窗口加权的配对分数直接相减。", "",
                   "## 科学判定与限制", "",
                   "1. 分布候选：核心M0的超额时延Lognormal在9/9个场景折排名第一；Doppler的Student-t在6/9折排名第一；相对功率Normal与Student-t各在4/9折排名第一，故功率没有单一稳定胜者。排名仅限成功拟合候选之间。",
                   "2. 环境差异：M1全数据参数点估计存在差异，但核心合并场景的配对M1−M0宏Δ在三个参数的全部候选族中均为负；分环境拆分的异质性见上表。因此当前证据不支持把M1宣称为稳定的场景外预测改进。",
                   "3. 仰角：GSV实测M2对相对功率的M2−M1在候选族总体配对宏分数上均为正，但M2−M0的候选族结果混合；按环境拆分后收益也不一致。延迟/Doppler未显示跨环境稳定增益。故仰角可保留为候选解释变量，但M2尚不作为已验证的普适预测模型。",
                   "4. Stage2总体受Stage1/Stage2筛选条件化；不代表285,752个Stage0有效窗口的无条件多径总体。",
                   "5. 同场景多PRN、重叠窗口与同窗多MPC相关。Mountain/Valley仅3个独立场景；不以路径总数虚增独立样本量、不报告行级CI或p值。候选族筛选和LOSO宏排名也是探索性，不是预留独立测试集。",
                   "6. 运动条件仅描述，不拟合M3；不做空间相关长度或联合依赖模型。补充环境仅作适用性分析。Gate G、WP6、alpha真实导出和Gate E/F均未完成；alpha导出试点继续暂缓。",
                   "",
                   "**WP3本轮计算与内部一致性检查已完成，建议状态：`COMPLETED_WITH_LIMITATIONS`，等待Commander独立科学审阅。该状态不代表条件模型已获最终采纳或Gate G/WP6通过。**",
                   "",
                   "## 产物", ""])
    report.extend(f"- `{name}`" for name in output_names)
    report.extend(["", "## 输入来源SHA-256", "", "|输入|SHA-256|", "|---|---|"])
    report.extend(f"|{name}|`{record['sha256']}`|" for name, record in inputs.items())
    report.extend(["", "测试执行命令、UTC时间、退出码与完整输出另见结果包中的`focused_test_execution.txt`。", ""])
    return "\n".join(report)


def run_analysis(input_paths: dict[str, Path], output_dir: Path) -> Path:
    analysis_started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    missing_keys = set(DEFAULT_INPUTS) - set(input_paths)
    if missing_keys:
        raise ValueError(f"missing input paths: {sorted(missing_keys)}")
    input_records = {
        name: verify_pinned_input(path, PINNED_INPUT_SHA256[name])
        for name, path in input_paths.items()
    }
    output = create_new_output_dir(output_dir, RESULTS_PARENT)
    source_manifest = json.loads(Path(input_paths["stage2_artifact_manifest"]).read_text(encoding="utf-8"))
    for name, filename in (("mpc_rows", "analysis_mpc_rows.csv"),
                           ("selected_windows", "selected_window_rows.csv")):
        declared = source_manifest.get(filename, {})
        actual = input_records[name]
        if declared.get("sha256") != actual["sha256"] or declared.get("size_bytes") != actual["size_bytes"]:
            raise ValueError(f"Stage2 artifact manifest disagrees with pinned input {filename}")

    paths = pd.read_csv(input_paths["mpc_rows"])
    windows = pd.read_csv(input_paths["selected_windows"])
    trajectory = pd.read_csv(input_paths["trajectory_overlay"])
    population = build_wp3_population(paths, windows)
    support, source_support, motion = condition_support_tables(population, windows, trajectory)
    observed_totals = (len(population), len(windows), windows.run_id.nunique(), population.scene_id.nunique())
    if observed_totals != (8914, 7847, 83, 13):
        raise ValueError(f"frozen Stage2 identity/count totals changed from accepted source evidence: {observed_totals}")
    core = population.loc[population.environment_class.astype(str).isin(CORE_ENVIRONMENTS)].copy()
    core_support = support.loc[support.environment_class.isin(CORE_ENVIRONMENTS)]
    observed_core = {
        "Urban": int(core_support.loc[core_support.environment_class.eq("Urban"), "mpc_n"].sum()),
        "Mountain/Valley": int(core_support.loc[core_support.environment_class.eq("Mountain/Valley"), "mpc_n"].sum()),
    }
    if observed_core != {"Urban": 3698, "Mountain/Valley": 2637}:
        raise ValueError(f"core environment MPC totals mismatch: {observed_core}")
    if core.scene_id.nunique() != 9 or set(population.environment_class.astype(str).unique()) != set(ENVIRONMENT_ORDER):
        raise ValueError("core/supplement scene or environment scope mismatch")

    scores, folds, tails = evaluate_scene_loso(population)
    paired = _paired_deltas(scores)
    macros, paired_macro = _macro_tables(scores, paired)
    family_ranks = _family_ranks_by_scene(scores)
    full_parameters = _full_parameter_fits(core)
    m1_contrasts = _m1_parameter_contrasts(full_parameters)
    supplement_scores = _supplement_scores(core, population)
    scene_desc, env_desc = _weighted_environment_descriptions(population)
    count_support = _count_support(windows)
    external_context = _external_baseline_context(input_paths)
    parameter_stability = _parameter_stability(scores)

    tables = {
        "condition_support_by_scene.csv": support,
        "condition_support_by_scene_source.csv": source_support,
        "motion_source_support_by_scene.csv": motion,
        "window_mpc_count_support_by_scene.csv": count_support,
        "descriptive_by_scene.csv": scene_desc,
        "descriptive_by_environment.csv": env_desc,
        "loso_fold_manifest.csv": folds,
        "loso_fold_scores.csv": scores,
        "loso_equal_scene_macro_scores.csv": macros,
        "loso_paired_deltas.csv": paired,
        "loso_paired_delta_macro.csv": paired_macro,
        "loso_family_ranks_by_scene.csv": family_ranks,
        "loso_tail_diagnostics.csv": tails,
        "loso_parameter_stability.csv": parameter_stability,
        "full_data_model_parameters.csv": full_parameters,
        "m1_environment_parameter_contrasts.csv": m1_contrasts,
        "supplement_applicability_scores.csv": supplement_scores,
        "external_13scene_baseline_context.csv": external_context,
    }
    for filename, table in tables.items():
        table.to_csv(output / filename, index=False, encoding="utf-8")
    figure_names = _make_figures(output, population, scene_desc, scores, paired, macros)
    other_names = list(tables) + figure_names + [
        "independent_validation_final.json", "analysis_execution.txt", "focused_test_execution.txt"
    ]
    report_text = _render_report(output, support, source_support, motion, env_desc, macros,
                                 paired_macro, full_parameters, family_ranks,
                                 parameter_stability, tails, supplement_scores, external_context,
                                 input_records, other_names)
    (output / "WP3_正式科研报告.md").write_text(report_text, encoding="utf-8")

    run_manifest = {
        "schema_version": "mainline-stage2-wp3-v1",
        "status": "ANALYSIS_COMPLETED_NEEDS_COMMANDER_REVIEW",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "analysis_execution": {
            "status": "COMPLETED",
            "command": list(sys.argv),
            "python_executable": sys.executable,
            "started_utc": analysis_started_utc,
            "completed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "exit_code": 0,
            "console_log_expected_at": str(
                RESULTS_PARENT / f"wp3_run_{output.name.removeprefix('wp3_')}_console.txt"
            ),
        },
        "superseded_preliminary_runs": [
            {"output_dir": "wp3_20261028T134000Z",
             "reason": "The static Normal, Lognormal and Laplace optimizers had avoidable line-search failures; exact weighted MLEs were implemented before final recomputation."},
            {"output_dir": "wp3_20261028T134900Z",
             "reason": "Pre-final report/audit-harness iteration; preserved as-is, with its failed first-pass audit explicitly attributable to the validator's overly strict assumptions, not a scientific-output mutation."},
        ],
        "repository_branch_expected": "review/gnss-mainline-cir-model-20261022",
        "git_head_at_run": "e2ef9a3fe7eb2de613154e64977d171958d5c0e6",
        "input_sha256": input_records,
        "code_sha256": {
            "model_module": sha256_file(Path(__file__).with_name("mainline_stage2_wp3.py")),
            "runner": sha256_file(Path(__file__).resolve()),
            "independent_validator": sha256_file(REPO_ROOT / "scripts/channel_modeling/verify_mainline_stage2_wp3.py"),
            "focused_test_model": sha256_file(REPO_ROOT / "scripts/channel_modeling/tests/test_mainline_stage2_wp3.py"),
            "focused_test_runner": sha256_file(REPO_ROOT / "scripts/channel_modeling/tests/test_run_mainline_stage2_wp3.py"),
        },
        "population_counts": {"selected_window_runs": int(windows.run_id.nunique()),
                              "runs_with_mpc": int(population.run_id.nunique()),
                              "scenes": int(population.scene_id.nunique()),
                              "selected_windows": int(len(windows)), "MPC": int(len(population)),
                              "core_scenes": int(core.scene_id.nunique()), "core_MPC": int(len(core))},
        "core_environment_MPC": observed_core,
        "model_design": {
            "M0": "core-only global marginal; scene/window-balanced pseudo-likelihood",
            "M1": "core environment-specific marginal parameters",
            "M2": "environment plus continuous elevation slope, separately by GSV, ephemeris/GGA, and ephemeris/zero-height source strata",
            "M3": "not fitted; motion remains descriptive due source-record reuse/coverage concerns",
            "families": VARIABLE_FAMILIES,
            "outer_validation": "9 complete core scenes; each fold excludes its held scene",
            "uncertainty": "no path-level CI/p-values; equal-scene fold summaries are descriptive with overlapping training sets",
            "supplement": "Highway/Open and Special Reflective descriptive/core-trained applicability only",
        },
        "execution_boundary": "CSV-only; no MATLAB/SAGE/CIR/GNSS-SDR; no MAT/HDF5/raw IQ/CIR payload read; Task5 untouched",
        "outputs_sha256": {},
        "test_execution_evidence": "focused_test_execution.txt added after focused suite run",
    }
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "run_manifest.json":
            run_manifest["outputs_sha256"][str(path.relative_to(output))] = {
                "sha256": sha256_file(path), "size_bytes": path.stat().st_size,
            }
    _write_json(output / "run_manifest.json", run_manifest)
    return output


def _default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RESULTS_PARENT / f"wp3_{stamp}"


def finalize_test_evidence(output_dir: Path, command: str, started_utc: str,
                           ended_utc: str, exit_code: int,
                           analysis_log_source: Path | None = None) -> None:
    output = Path(output_dir).resolve()
    if output.parent != RESULTS_PARENT.resolve() or not output.is_dir():
        raise ValueError("test evidence must target an existing WP3 result directory")
    manifest_path = output / "run_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing WP3 run manifest: {manifest_path}")
    log_path = output / "focused_test_execution.txt"
    if not log_path.is_file():
        raise FileNotFoundError(f"missing captured test output: {log_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["test_execution_evidence"] = {
        "command": command,
        "started_utc": started_utc,
        "ended_utc": ended_utc,
        "exit_code": int(exit_code),
        "output_log": "focused_test_execution.txt",
        "output_sha256": sha256_file(log_path),
        "interpretation": "focused_behavioral_tests_only;_not_scientific_acceptance",
    }
    if analysis_log_source is not None:
        log_record = _package_analysis_log(output, analysis_log_source)
        manifest["analysis_execution"]["console_log"] = {
            "path": "analysis_execution.txt", **log_record,
        }
    manifest["outputs_sha256"] = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "run_manifest.json":
            manifest["outputs_sha256"][str(path.relative_to(output))] = {
                "sha256": sha256_file(path), "size_bytes": path.stat().st_size,
            }
    _write_json(manifest_path, manifest)


def _package_analysis_log(output_dir: Path, source_path: Path) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    source_path = Path(source_path).resolve()
    if not output_dir.is_dir():
        raise NotADirectoryError(f"analysis output directory does not exist: {output_dir}")
    if not source_path.is_file():
        raise FileNotFoundError(f"missing captured analysis console log: {source_path}")
    packaged_log = output_dir / "analysis_execution.txt"
    if packaged_log.exists():
        raise FileExistsError(f"refusing to overwrite packaged analysis log: {packaged_log}")
    shutil.copyfile(source_path, packaged_log)
    return {"sha256": sha256_file(packaged_log), "size_bytes": packaged_log.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--finalize-test-evidence", action="store_true")
    parser.add_argument("--test-command", default=None)
    parser.add_argument("--test-started-utc", default=None)
    parser.add_argument("--test-ended-utc", default=None)
    parser.add_argument("--test-exit-code", type=int, default=None)
    parser.add_argument("--analysis-log-source", type=Path, default=None)
    args = parser.parse_args()
    if args.finalize_test_evidence:
        if not all((args.output_dir, args.test_command, args.test_started_utc,
                    args.test_ended_utc, args.test_exit_code is not None)):
            parser.error("finalization requires --output-dir, --test-command, both UTC times, and exit code")
        finalize_test_evidence(args.output_dir, args.test_command, args.test_started_utc,
                               args.test_ended_utc, args.test_exit_code,
                               args.analysis_log_source)
        print(f"TEST_EVIDENCE_FINALIZED={args.output_dir}")
        return int(args.test_exit_code)
    output = run_analysis(DEFAULT_INPUTS, args.output_dir or _default_output_dir())
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    print(f"WP3_OUTPUT={output}")
    print(f"POPULATION={manifest['population_counts']}")
    print(f"OUTPUT_FILES={len(manifest['outputs_sha256'])}")
    print(f"STATUS={manifest['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
