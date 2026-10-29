"""WP6 analysis primitives for the frozen Mainline Stage2 population.

The count model is conditional on a window having been selected by Stage2.
It is not a model of all Stage0 windows.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy import stats

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from mainline_stage2_wp3 import (  # noqa: E402
    VARIABLE_FAMILIES as _wp3_variable_families,
    _distribution_logpdf as _wp3_distribution_logpdf,
    _distribution_ppf as _wp3_distribution_ppf,
    _fit_static as _wp3_fit_static,
    make_scene_folds as _wp3_make_scene_folds,
    scene_window_weights as _wp3_scene_window_weights,
)


FEATURES_SHA256 = "258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4"
MPC_SHA256 = "8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b"
EXPECTED_INPUT_HASHES = {"features": FEATURES_SHA256, "mpcs": MPC_SHA256}
WINDOW_KEY = ("run_id", "window_id")
MPC_KEY = ("run_id", "window_id", "path_id")
COUNT_SUPPORT = (0, 1, 2, 3)
DEFAULT_CONTRACT = {
    "window_n": 7847,
    "mpc_n": 8914,
    "scene_n": 13,
    "count_support": COUNT_SUPPORT,
}
MARK_FAMILIES = _wp3_variable_families
MARK_VARIABLES = tuple(MARK_FAMILIES)
TAIL_QUANTILES = (0.01, 0.05, 0.10, 0.90, 0.95, 0.99)
COPULA_PIT_EPSILON = 1e-10
COPULA_EIGENVALUE_FLOOR = 1e-6

WINDOW_REQUIRED = {
    "run_id", "window_id", "scene_id", "stage2_mpc_count",
    "pdp_peak_at_grid_boundary", "pdp_rms_width_code_delay_samples",
    "pdp_peak_minus_sage_direct_delay_samples",
}
MPC_REQUIRED = {
    "run_id", "window_id", "path_id", "scene_id", "is_multipath",
    "modeling_role", "excess_delay_samples", "excess_delay_chips", "doppler_offset_hz",
    "relative_power_db",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_pinned_csv(path, required_columns, expected_sha, label):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"{label} input does not exist: {path}")
    actual_sha = _sha256(path)
    if expected_sha and actual_sha.lower() != str(expected_sha).lower():
        raise ValueError(f"{label} SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")
    frame = pd.read_csv(path, dtype={key: "string" for key in ("run_id", "window_id", "path_id", "scene_id")})
    missing = sorted(required_columns.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} schema missing required columns: {missing}")
    return frame, actual_sha


def load_wp6_inputs(features_path, mpc_path, expected_hashes=None, expected_contract=None):
    """Read the two frozen WP4 CSVs and bind their exact bytes and row counts."""
    hashes = EXPECTED_INPUT_HASHES if expected_hashes is None else dict(expected_hashes)
    if set(hashes) != {"features", "mpcs"}:
        raise ValueError("expected_hashes must contain exactly 'features' and 'mpcs'")
    windows, features_sha = _read_pinned_csv(
        features_path, WINDOW_REQUIRED, hashes["features"], "features")
    mpcs, mpc_sha = _read_pinned_csv(mpc_path, MPC_REQUIRED, hashes["mpcs"], "MPC")
    validate_wp6_population(windows, mpcs, expected_contract=expected_contract)
    manifest = {
        "features_path": str(Path(features_path).resolve()),
        "features_sha256": features_sha,
        "features_rows": int(len(windows)),
        "mpc_path": str(Path(mpc_path).resolve()),
        "mpc_sha256": mpc_sha,
        "mpc_rows": int(len(mpcs)),
        "window_key": list(WINDOW_KEY),
        "mpc_key": list(MPC_KEY),
        "population_scope": "Stage2-selected windows only; conditional on Stage2 selection",
    }
    return windows, mpcs, manifest


def _require_columns(frame, required, label):
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"{label} schema missing required columns: {missing}")


def _canonicalize_keys(frame, keys, label):
    frame = frame.copy()
    for key in keys:
        if frame[key].isna().any():
            raise ValueError(f"{label} contains missing {key}")
        values = frame[key].astype("string").str.strip()
        if values.eq("").any():
            raise ValueError(f"{label} contains empty {key}")
        frame[key] = values
    return frame


def _numeric(frame, column, label, allow_missing=False):
    values = pd.to_numeric(frame[column], errors="coerce").astype(float)
    if not allow_missing and (values.isna().any() or not np.isfinite(values.to_numpy()).all()):
        raise ValueError(f"{label}.{column} contains missing or non-finite values")
    return values


def validate_wp6_population(windows, mpcs, expected_contract=None):
    """Validate exact window/path identity and the selected-window denominator."""
    contract = dict(DEFAULT_CONTRACT if expected_contract is None else expected_contract)
    required = {
        "window_n", "mpc_n", "scene_n", "count_support"
    }
    if not required.issubset(contract):
        raise ValueError(f"expected_contract missing fields: {sorted(required - set(contract))}")
    _require_columns(windows, WINDOW_REQUIRED, "windows")
    _require_columns(mpcs, MPC_REQUIRED, "MPCs")
    windows = _canonicalize_keys(windows, (*WINDOW_KEY, "scene_id"), "windows")
    mpcs = _canonicalize_keys(mpcs, (*MPC_KEY, "scene_id"), "MPCs")

    if windows.duplicated(list(WINDOW_KEY)).any():
        raise ValueError("duplicate selected-window key")
    if mpcs.duplicated(list(MPC_KEY)).any():
        raise ValueError("duplicate MPC path key")

    window_counts = _numeric(windows, "stage2_mpc_count", "windows")
    rounded = np.rint(window_counts.to_numpy())
    if not np.array_equal(window_counts.to_numpy(), rounded):
        raise ValueError("stage2_mpc_count must contain integer counts")
    support = tuple(int(value) for value in contract["count_support"])
    if not set(rounded.astype(int)).issubset(set(support)):
        raise ValueError(f"window count outside declared support {support}")

    for column in ("excess_delay_chips", "doppler_offset_hz", "relative_power_db"):
        _numeric(mpcs, column, "MPCs")
    delay_samples = _numeric(mpcs, "excess_delay_samples", "MPCs")
    delay_chips = _numeric(mpcs, "excess_delay_chips", "MPCs")
    if not np.allclose(delay_samples.to_numpy(), 10.0 * delay_chips.to_numpy(),
                       rtol=1e-9, atol=1e-8):
        raise ValueError("excess_delay_samples does not match the frozen 10 samples/chip conversion")
    multipath = pd.to_numeric(mpcs["is_multipath"], errors="coerce")
    if multipath.isna().any() or not multipath.eq(1).all():
        raise ValueError("MPC input includes a row not identified as a multipath path")
    if not mpcs["modeling_role"].astype("string").eq("MPC_CANDIDATE").all():
        raise ValueError("MPC input includes a row outside MPC_CANDIDATE role")

    scene_by_run = windows.groupby("run_id", dropna=False)["scene_id"].nunique()
    if not scene_by_run.eq(1).all():
        raise ValueError("a run_id maps to more than one scene_id")
    window_scene = windows.set_index(list(WINDOW_KEY))["scene_id"]
    mpc_scene = mpcs.set_index(list(WINDOW_KEY))["scene_id"]
    extra_window_keys = mpc_scene.index.difference(window_scene.index)
    if len(extra_window_keys):
        raise ValueError(f"MPC paths reference unknown selected-window keys: {list(extra_window_keys[:3])}")
    joined_scene = mpc_scene.to_frame("mpc_scene").join(window_scene.rename("window_scene"), how="left")
    if not joined_scene["mpc_scene"].eq(joined_scene["window_scene"]).all():
        raise ValueError("MPC scene_id does not match its selected-window scene_id")

    observed = mpcs.groupby(list(WINDOW_KEY), dropna=False).size()
    declared = windows.set_index(list(WINDOW_KEY))["stage2_mpc_count"].astype(int)
    reconciled = observed.reindex(declared.index, fill_value=0)
    if not reconciled.astype(int).equals(declared):
        mismatch = declared[reconciled.astype(int).ne(declared)].head(3).to_dict()
        raise ValueError(f"selected-window MPC counts do not reconcile with path rows: {mismatch}")

    actual = {
        "window_n": int(len(windows)),
        "mpc_n": int(len(mpcs)),
        "scene_n": int(windows["scene_id"].nunique()),
        "count_support": tuple(sorted(set(rounded.astype(int)))),
    }
    for key in ("window_n", "mpc_n", "scene_n"):
        if actual[key] != int(contract[key]):
            raise ValueError(f"{key} mismatch: expected {contract[key]}, got {actual[key]}")
    if not set(actual["count_support"]).issubset(set(support)):
        raise ValueError(f"observed count support {actual['count_support']} exceeds {support}")
    return None


def _validate_count_frame(frame, label):
    _require_columns(frame, (*WINDOW_KEY, "scene_id", "stage2_mpc_count"), label)
    if frame.duplicated(list(WINDOW_KEY)).any():
        raise ValueError(f"{label} contains duplicate selected-window keys")
    counts = _numeric(frame, "stage2_mpc_count", label)
    if not np.array_equal(counts.to_numpy(), np.rint(counts.to_numpy())):
        raise ValueError(f"{label} contains noninteger count values")
    if not set(counts.astype(int)).issubset(set(COUNT_SUPPORT)):
        raise ValueError(f"{label} contains counts outside {COUNT_SUPPORT}")
    if frame["scene_id"].isna().any() or frame["scene_id"].astype("string").str.strip().eq("").any():
        raise ValueError(f"{label} contains missing scene_id")
    return counts.astype(int)


def fit_count_probabilities(training_windows):
    """Equal-scene macro empirical frequencies; no smoothing for absent bins."""
    counts = _validate_count_frame(training_windows, "training windows")
    if training_windows.empty:
        raise ValueError("cannot fit count probabilities with no training windows")
    work = training_windows[["scene_id"]].copy()
    work["count"] = counts.to_numpy()
    scene_probabilities = []
    for _, scene in work.groupby("scene_id", sort=True, dropna=False):
        frequencies = scene["count"].value_counts(normalize=True)
        scene_probabilities.append({category: float(frequencies.get(category, 0.0))
                                    for category in COUNT_SUPPORT})
    scene_n = len(scene_probabilities)
    return {
        category: float(sum(scene[category] for scene in scene_probabilities) / scene_n)
        for category in COUNT_SUPPORT
    }


def score_count_fold(training_windows, test_windows):
    """Score a held-out scene set without smoothing unseen training categories."""
    train_counts = _validate_count_frame(training_windows, "training windows")
    test_counts = _validate_count_frame(test_windows, "test windows")
    train_scenes = set(training_windows["scene_id"].astype("string"))
    test_scenes = set(test_windows["scene_id"].astype("string"))
    overlap = train_scenes.intersection(test_scenes)
    if overlap:
        raise ValueError(f"training/test scene leakage: {sorted(overlap)}")
    probabilities = fit_count_probabilities(training_windows)
    rows = test_windows[list(WINDOW_KEY + ("scene_id",))].copy().reset_index(drop=True)
    observed = test_counts.to_numpy()
    row_probabilities = np.asarray([probabilities[int(count)] for count in observed], dtype=float)
    rows["stage2_mpc_count"] = observed
    rows["predicted_probability"] = row_probabilities
    supported = row_probabilities > 0.0
    rows["status"] = np.where(supported, "SCORED", "UNSUPPORTED_COUNT_CATEGORY")
    rows["log_score"] = np.where(supported, np.log(np.maximum(row_probabilities, np.finfo(float).tiny)), np.nan)
    scene_rows = []
    for scene_id, scene in rows.groupby("scene_id", sort=True, dropna=False):
        is_supported = scene["status"].eq("SCORED").all()
        scene_rows.append({
            "scene_id": scene_id,
            "window_n": int(len(scene)),
            "unsupported_window_n": int(scene["status"].ne("SCORED").sum()),
            "status": "SCORED" if is_supported else "UNSUPPORTED_COUNT_CATEGORY",
            "mean_log_score": float(scene["log_score"].mean()) if is_supported else np.nan,
        })
    return probabilities, rows, pd.DataFrame(scene_rows)


def _prepare_mark_frame(frame, label="MPCs"):
    required = set(MPC_KEY) | {"scene_id"} | set(MARK_VARIABLES)
    _require_columns(frame, required, label)
    result = _canonicalize_keys(frame, (*MPC_KEY, "scene_id"), label)
    if result.duplicated(list(MPC_KEY)).any():
        raise ValueError(f"{label} contains duplicate MPC identity")
    if result.empty:
        raise ValueError(f"{label} is empty")
    for variable in MARK_VARIABLES:
        values = _numeric(result, variable, label)
        result[variable] = values
    run_scenes = result.groupby("run_id")["scene_id"].nunique()
    if not run_scenes.eq(1).all():
        raise ValueError(f"{label} maps a run_id to more than one scene")
    return result


def _fit_one_mark(frame, variable, family):
    values = frame[variable].to_numpy(dtype=float)
    weights = _wp3_scene_window_weights(frame)
    fitted = _wp3_fit_static(values, weights, family)
    return {
        "variable": variable,
        "family": family,
        "status": fitted.get("status", "FAILED"),
        "parameters": fitted.get("parameters", {}),
        "failure_reason": fitted.get("failure_reason", ""),
        "optimizer_message": fitted.get("optimizer_message", ""),
        "boundary_parameters": fitted.get("boundary_parameters", []),
        "weighted_log_score": fitted.get("weighted_log_score"),
        "training_scene_ids": sorted(frame.scene_id.astype(str).unique().tolist()),
        "training_scene_n": int(frame.scene_id.nunique()),
        "training_mpc_n": int(len(frame)),
        "training_window_n": int(frame[list(WINDOW_KEY)].drop_duplicates().shape[0]),
        "weighting": "WP3_SCENE_WINDOW_BALANCED_PSEUDO_LIKELIHOOD",
    }


def _usable_fit(fit):
    # Boundary and optimizer outcomes remain visible but cannot select a family.
    return fit.get("status") == "PASS"


def select_mark_families_nested(mpcs, outer_training_scenes=None):
    """Select each mark family by inner complete-scene LOSO only.

    A candidate is selectable only if every inner held-out scene has a finite,
    non-boundary fit trained on the other outer-training scenes.
    """
    frame = _prepare_mark_frame(mpcs, "nested family-selection MPCs")
    all_scenes = tuple(sorted(frame.scene_id.astype(str).unique()))
    training_scenes = (all_scenes if outer_training_scenes is None else
                       tuple(sorted({str(scene) for scene in outer_training_scenes})))
    unknown = set(training_scenes).difference(all_scenes)
    if unknown:
        raise ValueError(f"outer_training_scenes contain unknown scenes: {sorted(unknown)}")
    outer = frame.loc[frame.scene_id.astype(str).isin(training_scenes)].copy()
    if outer.scene_id.nunique() < 2:
        raise ValueError("nested selection requires at least two outer-training scenes")

    inner_rows = []
    for variable, candidate_families in MARK_FAMILIES.items():
        for family in candidate_families:
            for held_scene in training_scenes:
                test = outer.loc[outer.scene_id.astype(str).eq(held_scene)].copy()
                train = outer.loc[~outer.scene_id.astype(str).eq(held_scene)].copy()
                fit = _fit_one_mark(train, variable, family)
                score_status = fit["status"]
                mean_window_log_score = np.nan
                failure_reason = fit["failure_reason"]
                if _usable_fit(fit):
                    row_logpdf = _wp3_distribution_logpdf(
                        family, test[variable].to_numpy(dtype=float), fit["parameters"])
                    if np.isfinite(row_logpdf).all():
                        scored = test[[*WINDOW_KEY]].copy()
                        scored["row_logpdf"] = row_logpdf
                        per_window = scored.groupby(list(WINDOW_KEY), sort=False)["row_logpdf"].mean()
                        mean_window_log_score = float(per_window.mean())
                        score_status = "PASS" if np.isfinite(mean_window_log_score) else "NONFINITE_SCORE"
                    else:
                        score_status = "NONFINITE_SCORE"
                        failure_reason = "inner held-out log density contains non-finite values"
                inner_rows.append({
                    "variable": variable,
                    "family": family,
                    "outer_training_scenes": list(training_scenes),
                    "inner_held_out_scene_id": held_scene,
                    "inner_training_scene_ids": [s for s in training_scenes if s != held_scene],
                    "training_window_n": int(train[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                    "test_window_n": int(test[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                    "fit_status": fit["status"],
                    "score_status": score_status,
                    "mean_window_log_score": mean_window_log_score,
                    "failure_reason": failure_reason,
                    "boundary_parameters": fit["boundary_parameters"],
                })

    inner_scores = pd.DataFrame(inner_rows)
    family_rows = []
    selected = {}
    for variable, candidate_families in MARK_FAMILIES.items():
        candidates = inner_scores.loc[inner_scores.variable.eq(variable)]
        for family in candidate_families:
            family_rows_for = candidates.loc[candidates.family.eq(family)]
            complete = (len(family_rows_for) == len(training_scenes)
                        and family_rows_for.score_status.eq("PASS").all())
            mean_score = (float(family_rows_for.mean_window_log_score.mean()) if complete else np.nan)
            family_rows.append({
                "variable": variable,
                "family": family,
                "inner_scene_n": int(len(family_rows_for)),
                "inner_scene_n_pass": int(family_rows_for.score_status.eq("PASS").sum()),
                "selection_score": mean_score,
                "status": "SELECTABLE" if complete else "NOT_SELECTABLE",
            })
        selectable = [row for row in family_rows if row["variable"] == variable
                      and row["status"] == "SELECTABLE"]
        winner = max(selectable, key=lambda row: row["selection_score"]) if selectable else None
        selected[variable] = winner["family"] if winner else None
    failures = inner_scores.loc[inner_scores.score_status.ne("PASS")].copy().reset_index(drop=True)
    return selected, inner_scores, failures


def _distribution_cdf(family, values, parameters):
    values = np.asarray(values, dtype=float)
    if family == "gamma":
        return stats.gamma.cdf(values, a=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "lognormal":
        return stats.lognorm.cdf(values, s=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "weibull":
        return stats.weibull_min.cdf(values, c=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "normal":
        return stats.norm.cdf(values, loc=parameters["loc"], scale=parameters["scale"])
    if family == "laplace":
        return stats.laplace.cdf(values, loc=parameters["loc"], scale=parameters["scale"])
    if family == "student_t":
        return stats.t.cdf(values, df=parameters["df"], loc=parameters["loc"], scale=parameters["scale"])
    raise ValueError(f"unsupported distribution family: {family}")


def fit_scene_balanced_copula(training_mpcs, fitted_marginals):
    """Estimate a descriptive scene-macro Gaussian-copula correlation.

    Kendall statistics are computed separately within each training scene and
    averaged equally over scenes; path rows are not inferential replicates.
    """
    frame = _prepare_mark_frame(training_mpcs, "copula training MPCs")
    if frame.scene_id.nunique() < 2:
        return None, {"status": "INSUFFICIENT_TRAINING_SCENES", "scene_n_used": int(frame.scene_id.nunique())}
    missing = [v for v in MARK_VARIABLES if v not in fitted_marginals]
    if missing:
        raise ValueError(f"fitted marginals missing variables: {missing}")
    failed = [v for v in MARK_VARIABLES if not _usable_fit(fitted_marginals[v])]
    if failed:
        return None, {"status": "MARGINAL_FIT_UNAVAILABLE", "failed_variables": failed}

    pairwise = {}
    scene_rhos = {}
    scenes = sorted(frame.scene_id.astype(str).unique())
    raw = np.eye(len(MARK_VARIABLES), dtype=float)
    for i, first in enumerate(MARK_VARIABLES):
        for j in range(i + 1, len(MARK_VARIABLES)):
            second = MARK_VARIABLES[j]
            taus = {}
            for scene in scenes:
                values = frame.loc[frame.scene_id.astype(str).eq(scene), [first, second]]
                tau = stats.kendalltau(values[first], values[second], nan_policy="omit").statistic
                taus[scene] = float(tau) if np.isfinite(tau) else None
            if any(value is None for value in taus.values()):
                pairwise[f"{first}|{second}"] = taus
                return None, {
                    "status": "UNESTIMABLE_SCENE_PAIRWISE_KENDALL",
                    "scene_n_used": len(scenes),
                    "pairwise_scene_tau_k": pairwise,
                    "failed_pair": f"{first}|{second}",
                }
            rhos = {scene: float(np.sin(np.pi * tau / 2.0)) for scene, tau in taus.items()}
            rho = float(np.mean(list(rhos.values())))
            raw[i, j] = raw[j, i] = rho
            pairwise[f"{first}|{second}"] = taus
            scene_rhos[f"{first}|{second}"] = rhos

    eigenvalues_before = np.linalg.eigvalsh(raw)
    projection_applied = bool(eigenvalues_before.min() <= COPULA_EIGENVALUE_FLOOR)
    corr = raw.copy()
    if projection_applied:
        eigenvalues, eigenvectors = np.linalg.eigh(raw)
        corr = (eigenvectors * np.maximum(eigenvalues, COPULA_EIGENVALUE_FLOOR)) @ eigenvectors.T
        diagonal_scale = np.sqrt(np.diag(corr))
        corr = corr / np.outer(diagonal_scale, diagonal_scale)
        np.fill_diagonal(corr, 1.0)
    eigenvalues_after = np.linalg.eigvalsh(corr)
    diagnostics = {
        "status": "PASS",
        "scene_n_used": int(len(scenes)),
        "training_scene_ids": scenes,
        "pairwise_scene_tau_k": pairwise,
        "pairwise_scene_gaussian_rho": scene_rhos,
        "scene_macro_estimand": "EQUAL_AVERAGE_OF_WITHIN_SCENE_KENDALL_TRANSFORMS",
        "path_row_inference": "DESCRIPTIVE_ONLY; PATHS/WINDOWS ARE CLUSTERED",
        "projection_applied": projection_applied,
        "projection_method": "EIGENVALUE_FLOOR_THEN_RENORMALIZE_DIAGONAL" if projection_applied else "NONE",
        "eigenvalue_floor": COPULA_EIGENVALUE_FLOOR,
        "eigenvalues_before": eigenvalues_before.tolist(),
        "eigenvalues_after": eigenvalues_after.tolist(),
        "correlation_before_projection": raw.tolist(),
        "correlation": corr.tolist(),
        "conditional_generation_assumption": "EXCHANGEABLE_CONDITIONAL_IID_MARKS_GIVEN_STAGE2_COUNT",
    }
    return corr, diagnostics


def gaussian_copula_log_density(uniforms, correlation):
    """Gaussian copula log density for rows of marginal PIT values."""
    uniforms = np.asarray(uniforms, dtype=float)
    correlation = np.asarray(correlation, dtype=float)
    if uniforms.ndim == 1:
        uniforms = uniforms.reshape(1, -1)
    if (uniforms.ndim != 2 or correlation.shape != (uniforms.shape[1], uniforms.shape[1])
            or not np.isfinite(uniforms).all() or not np.isfinite(correlation).all()):
        raise ValueError("uniforms and correlation have incompatible or non-finite values")
    if not np.allclose(correlation, correlation.T, rtol=0, atol=1e-10):
        raise ValueError("copula correlation matrix must be symmetric")
    try:
        chol = np.linalg.cholesky(correlation)
    except np.linalg.LinAlgError as exc:
        raise ValueError("copula correlation matrix must be positive definite") from exc
    clipped = np.clip(uniforms, COPULA_PIT_EPSILON, 1.0 - COPULA_PIT_EPSILON)
    z = stats.norm.ppf(clipped)
    transformed = np.linalg.solve(chol, z.T).T
    logdet = 2.0 * float(np.log(np.diag(chol)).sum())
    quadratic = np.einsum("ij,ij->i", transformed, transformed) - np.einsum("ij,ij->i", z, z)
    return -0.5 * (logdet + quadratic)


def score_mark_models(fitted_marginals, copula, test_mpcs):
    """Return paired per-window and macro per-scene product/copula scores."""
    frame = _prepare_mark_frame(test_mpcs, "held-out MPCs")
    missing = [v for v in MARK_VARIABLES if v not in fitted_marginals]
    if missing:
        raise ValueError(f"fitted marginals missing variables: {missing}")
    corr = None if copula is None else np.asarray(copula, dtype=float)
    if corr is not None and corr.shape != (len(MARK_VARIABLES), len(MARK_VARIABLES)):
        raise ValueError("copula matrix dimension does not match mark variables")
    product_rows = np.zeros(len(frame), dtype=float)
    uniforms = np.zeros((len(frame), len(MARK_VARIABLES)), dtype=float) if corr is not None else None
    for index, variable in enumerate(MARK_VARIABLES):
        fit = fitted_marginals[variable]
        if not _usable_fit(fit):
            raise ValueError(f"marginal fit unavailable for {variable}: {fit.get('status')}")
        family, parameters = fit["family"], fit["parameters"]
        product_rows += _wp3_distribution_logpdf(family, frame[variable].to_numpy(), parameters)
        if uniforms is not None:
            uniforms[:, index] = _distribution_cdf(family, frame[variable].to_numpy(), parameters)
    product_finite = np.isfinite(product_rows)
    copula_rows = (gaussian_copula_log_density(uniforms, corr)
                   if corr is not None and product_finite.all() else None)
    copula_finite = np.isfinite(copula_rows) if copula_rows is not None else np.zeros(len(frame), dtype=bool)
    work = frame[[*WINDOW_KEY, "scene_id"]].copy()
    work["product_row_score"] = np.where(product_finite, product_rows, np.nan)
    work["copula_row_score"] = (np.where(copula_finite, product_rows + copula_rows, np.nan)
                                 if copula_rows is not None else np.nan)
    work["product_row_status"] = np.where(product_finite, "SCORED", "UNSCORABLE_NONFINITE_DENSITY")
    work["copula_row_status"] = np.where(copula_finite, "SCORED", "COPULA_UNAVAILABLE")
    rows = []
    for identity, group in work.groupby(list(WINDOW_KEY), sort=True, dropna=False):
        product_status = ("SCORED" if group.product_row_status.eq("SCORED").all()
                          else "UNSCORABLE_NONFINITE_DENSITY")
        copula_status = ("SCORED" if group.copula_row_status.eq("SCORED").all()
                         else "COPULA_UNAVAILABLE")
        status = ("SCORED" if product_status == "SCORED" and copula_status == "SCORED"
                  else "PRODUCT_ONLY_COPULA_UNAVAILABLE" if product_status == "SCORED"
                  else "UNSCORABLE_NONFINITE_DENSITY")
        rows.append({
            "run_id": identity[0], "window_id": identity[1],
            "scene_id": group.scene_id.iloc[0], "path_n": int(len(group)), "status": status,
            "product_score_status": product_status, "copula_score_status": copula_status,
            "product_marginal_log_score": (float(group.product_row_score.sum())
                                            if product_status == "SCORED" else np.nan),
            "gaussian_copula_log_score": (float(group.copula_row_score.sum())
                                           if copula_status == "SCORED" else np.nan),
        })
    per_window = pd.DataFrame(rows)
    scene_rows = []
    for scene_id, group in per_window.groupby("scene_id", sort=True, dropna=False):
        product_status = ("SCORED" if group.product_score_status.eq("SCORED").all()
                          else "UNSCORABLE_NONFINITE_DENSITY")
        copula_status = ("SCORED" if group.copula_score_status.eq("SCORED").all()
                         else "COPULA_UNAVAILABLE")
        status = ("SCORED" if product_status == "SCORED" and copula_status == "SCORED"
                  else "PRODUCT_ONLY_COPULA_UNAVAILABLE" if product_status == "SCORED"
                  else "UNSCORABLE_NONFINITE_DENSITY")
        scene_rows.append({
            "scene_id": scene_id, "window_n": int(len(group)),
            "unscorable_window_n": int(group.product_score_status.ne("SCORED").sum()),
            "unscorable_copula_window_n": int(group.copula_score_status.ne("SCORED").sum()),
            "status": status, "product_score_status": product_status,
            "copula_score_status": copula_status,
            "product_marginal_mean_window_log_score": (
                float(group.product_marginal_log_score.mean()) if product_status == "SCORED" else np.nan),
            "gaussian_copula_mean_window_log_score": (
                float(group.gaussian_copula_log_score.mean()) if copula_status == "SCORED" else np.nan),
        })
    return per_window, pd.DataFrame(scene_rows)


def calibrate_mark_tails(fit, heldout_mpcs, variable, quantiles=TAIL_QUANTILES):
    """Compare training-fit quantiles with held-out empirical tails, retaining low support."""
    if variable not in MARK_FAMILIES:
        raise ValueError(f"unknown mark variable: {variable}")
    if variable not in heldout_mpcs:
        raise ValueError(f"held-out table missing {variable}")
    values = pd.to_numeric(heldout_mpcs[variable], errors="coerce").to_numpy(dtype=float)
    if values.size == 0 or not np.isfinite(values).all():
        return pd.DataFrame([{
            "variable": variable, "family": fit.get("family"), "quantile": q,
            "heldout_n": int(values.size), "status": "HELDOUT_DATA_UNAVAILABLE",
            "failure_reason": "empty or non-finite held-out observations",
        } for q in quantiles])
    if not _usable_fit(fit):
        return pd.DataFrame([{
            "variable": variable, "family": fit.get("family"), "quantile": q,
            "heldout_n": int(values.size), "status": "FIT_UNAVAILABLE",
            "failure_reason": fit.get("failure_reason", fit.get("status", "")),
        } for q in quantiles])
    rows = []
    for q in quantiles:
        predicted = _wp3_distribution_ppf(fit["family"], float(q), fit["parameters"])
        empirical = float(np.quantile(values, q, method="linear"))
        coverage = float(np.mean(values <= predicted))
        expected_tail_n = float(len(values) * min(q, 1.0 - q))
        rows.append({
            "variable": variable, "family": fit["family"], "quantile": float(q),
            "training_predicted_quantile": float(predicted),
            "heldout_empirical_quantile": empirical,
            "quantile_difference_predicted_minus_empirical": float(predicted - empirical),
            "heldout_coverage_at_predicted_quantile": coverage,
            "expected_tail_support_n": expected_tail_n,
            "heldout_n": int(len(values)),
            "status": "LOW_SUPPORT" if expected_tail_n < 10 else "DESCRIPTIVE_DIAGNOSTIC",
            "training_fit_used": True,
            "uncertainty_claim": "DESCRIPTIVE_ONLY; MPC PATH ROWS ARE CLUSTERED",
        })
    return pd.DataFrame(rows)


def _fit_selected_marginals(training_mpcs, selected_families):
    fits = {}
    for variable in MARK_VARIABLES:
        family = selected_families.get(variable)
        if family is None:
            fits[variable] = {"variable": variable, "family": None, "status": "NO_SELECTABLE_FAMILY",
                              "parameters": {}, "failure_reason": "all inner candidate fits failed or were unsupported"}
        else:
            fits[variable] = _fit_one_mark(training_mpcs, variable, family)
    return fits


def fit_final_mark_model(mpcs):
    """Select by complete-scene LOSO, then separately refit on all scenes."""
    frame = _prepare_mark_frame(mpcs, "final mark-model MPCs")
    selection, inner_scores, failures = select_mark_families_nested(frame)
    refits = _fit_selected_marginals(frame, selection)
    copula = None
    copula_diagnostics = {"status": "MARGINAL_FIT_UNAVAILABLE"}
    if all(_usable_fit(fit) for fit in refits.values()):
        copula, copula_diagnostics = fit_scene_balanced_copula(frame, refits)
    return {
        "selection": selection,
        "inner_scores": inner_scores,
        "selection_failures": failures,
        "full_population_refits": refits,
        "full_population_copula": copula,
        "full_population_copula_diagnostics": copula_diagnostics,
        "full_refit_scope": "DESCRIPTIVE_FULL_POPULATION_REFIT_NOT_OUT_OF_SCENE_EVIDENCE",
    }


def evaluate_nested_mark_loso(mpcs):
    """Evaluate nested family selection and paired product/copula scores by scene."""
    frame = _prepare_mark_frame(mpcs, "nested LOSO MPCs")
    scenes = tuple(sorted(frame.scene_id.astype(str).unique()))
    if len(scenes) < 3:
        raise ValueError("outer LOSO requires at least three scenes")
    fold_rows, parameter_rows, failure_rows = [], [], []
    tail_frames, window_frames, scene_score_frames, copula_rows, inner_frames = [], [], [], [], []
    for held_scene in scenes:
        test = frame.loc[frame.scene_id.astype(str).eq(held_scene)].copy()
        train = frame.loc[~frame.scene_id.astype(str).eq(held_scene)].copy()
        selected, inner_scores, inner_failures = select_mark_families_nested(train)
        if not inner_scores.empty:
            inner = inner_scores.copy()
            inner.insert(0, "outer_held_out_scene_id", held_scene)
            inner_frames.append(inner)
        if not inner_failures.empty:
            failures = inner_failures.copy()
            failures.insert(0, "outer_held_out_scene_id", held_scene)
            failure_rows.append(failures)
        fitted = _fit_selected_marginals(train, selected)
        for variable, fit in fitted.items():
            parameter_rows.append({
                "outer_held_out_scene_id": held_scene,
                "variable": variable,
                "selected_family": selected[variable],
                "fit_status": fit["status"],
                "parameters_json": fit.get("parameters", {}),
                "training_scene_ids": fit.get("training_scene_ids", sorted(train.scene_id.unique().tolist())),
                "training_scene_n": int(train.scene_id.nunique()),
                "training_mpc_n": int(len(train)),
                "training_window_n": int(train[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                "fit_failure_reason": fit.get("failure_reason", ""),
                "boundary_parameters": fit.get("boundary_parameters", []),
            })
            tail_rows = calibrate_mark_tails(fit, test, variable)
            tail_rows.insert(0, "outer_held_out_scene_id", held_scene)
            tail_frames.append(tail_rows)
        all_marginals_pass = all(_usable_fit(fit) for fit in fitted.values())
        corr = None
        copula_diag = {"status": "MARGINAL_FIT_UNAVAILABLE"}
        if all_marginals_pass:
            corr, copula_diag = fit_scene_balanced_copula(train, fitted)
        copula_rows.append({
            "outer_held_out_scene_id": held_scene,
            "status": copula_diag.get("status"),
            "training_scene_n": int(train.scene_id.nunique()),
            "training_scene_ids": sorted(train.scene_id.astype(str).unique().tolist()),
            "correlation_json": corr.tolist() if corr is not None else None,
            "diagnostics_json": copula_diag,
        })
        if all_marginals_pass:
            per_window, per_scene = score_mark_models(fitted, corr, test)
            per_window.insert(0, "outer_held_out_scene_id", held_scene)
            per_scene.insert(0, "outer_held_out_scene_id", held_scene)
            window_frames.append(per_window)
            scene_score_frames.append(per_scene)
            scene_score = per_scene.iloc[0]
            copula_available = scene_score.copula_score_status == "SCORED"
            fold_rows.append({
                "held_out_scene_id": held_scene,
                "training_scene_ids": sorted(train.scene_id.astype(str).unique().tolist()),
                "training_scene_n": int(train.scene_id.nunique()),
                "test_window_n": int(test[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                "test_mpc_n": int(len(test)),
                "selected_families": selected,
                "fit_status": "PASS" if copula_available else "PRODUCT_ONLY_COPULA_UNAVAILABLE",
                "copula_status": copula_diag.get("status"),
                "product_marginal_mean_window_log_score": scene_score.product_marginal_mean_window_log_score,
                "gaussian_copula_mean_window_log_score": scene_score.gaussian_copula_mean_window_log_score,
                "copula_minus_product_score": (
                    scene_score.gaussian_copula_mean_window_log_score
                    - scene_score.product_marginal_mean_window_log_score if copula_available else np.nan),
                "uncertainty_claim": "DESCRIPTIVE_LOSO_FOLDS; TRAINING SETS OVERLAP",
            })
        else:
            path_counts = test.groupby(list(WINDOW_KEY), sort=True).size().rename("path_n").reset_index()
            unscorable_windows = test[list(WINDOW_KEY + ("scene_id",))].drop_duplicates(
                list(WINDOW_KEY)).merge(
                    path_counts, on=list(WINDOW_KEY), how="left", sort=False,
                    validate="one_to_one")
            unscorable_windows["outer_held_out_scene_id"] = held_scene
            unscorable_windows["status"] = "UNSCORABLE_MARGINAL_FIT"
            unscorable_windows["product_score_status"] = "UNSCORABLE_MARGINAL_FIT"
            unscorable_windows["copula_score_status"] = "NOT_EVALUATED"
            unscorable_windows["product_marginal_log_score"] = np.nan
            unscorable_windows["gaussian_copula_log_score"] = np.nan
            window_frames.append(unscorable_windows)
            scene_score_frames.append(pd.DataFrame([{
                "outer_held_out_scene_id": held_scene,
                "scene_id": held_scene,
                "window_n": int(test[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                "unscorable_window_n": int(test[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                "unscorable_copula_window_n": int(test[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                "status": "UNSCORABLE_MARGINAL_FIT",
                "product_score_status": "UNSCORABLE_MARGINAL_FIT",
                "copula_score_status": "NOT_EVALUATED",
                "product_marginal_mean_window_log_score": np.nan,
                "gaussian_copula_mean_window_log_score": np.nan,
            }]))
            fold_rows.append({
                "held_out_scene_id": held_scene,
                "training_scene_ids": sorted(train.scene_id.astype(str).unique().tolist()),
                "training_scene_n": int(train.scene_id.nunique()),
                "test_window_n": int(test[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                "test_mpc_n": int(len(test)),
                "selected_families": selected,
                "fit_status": "UNSCORABLE_MARGINAL_FIT",
                "copula_status": copula_diag.get("status"),
                "product_marginal_mean_window_log_score": np.nan,
                "gaussian_copula_mean_window_log_score": np.nan,
                "copula_minus_product_score": np.nan,
                "uncertainty_claim": "DESCRIPTIVE_LOSO_FOLDS; TRAINING SETS OVERLAP",
            })
    return {
        "folds": pd.DataFrame(fold_rows),
        "parameters": pd.DataFrame(parameter_rows),
        "failures": pd.concat(failure_rows, ignore_index=True) if failure_rows else pd.DataFrame(),
        "tails": pd.concat(tail_frames, ignore_index=True) if tail_frames else pd.DataFrame(),
        "window_scores": pd.concat(window_frames, ignore_index=True) if window_frames else pd.DataFrame(),
        "scene_scores": pd.concat(scene_score_frames, ignore_index=True) if scene_score_frames else pd.DataFrame(),
        "copula_diagnostics": pd.DataFrame(copula_rows),
        "inner_scores": pd.concat(inner_frames, ignore_index=True) if inner_frames else pd.DataFrame(),
    }


def derive_window_delay_summaries(windows, mpcs):
    """Derive relative-power delay moments and retain every Stage2 window.

    The direct reference contributes unit relative power at zero excess delay.
    MPC delay uses the frozen Stage2 sample coordinate (10 samples/chip), and
    relative dB power is converted to linear power relative to that reference.
    """
    required_windows = set(WINDOW_KEY) | {
        "scene_id", "stage2_mpc_count", "pdp_peak_at_grid_boundary",
        "pdp_rms_width_code_delay_samples", "pdp_peak_minus_sage_direct_delay_samples",
    }
    _require_columns(windows, required_windows, "window PDP table")
    _require_columns(mpcs, set(MPC_KEY) | {
        "scene_id", "excess_delay_samples", "excess_delay_chips", "relative_power_db",
    }, "MPC delay table")
    result = _canonicalize_keys(windows, (*WINDOW_KEY, "scene_id"), "window PDP table")
    paths = _canonicalize_keys(mpcs, (*MPC_KEY, "scene_id"), "MPC delay table")
    if result.duplicated(list(WINDOW_KEY)).any():
        raise ValueError("duplicate selected-window identity in PDP table")
    if paths.duplicated(list(MPC_KEY)).any():
        raise ValueError("duplicate MPC identity in delay table")
    counts = _numeric(result, "stage2_mpc_count", "window PDP table")
    if not np.array_equal(counts.to_numpy(), np.rint(counts.to_numpy())) or (counts < 0).any():
        raise ValueError("stage2_mpc_count must be a nonnegative integer")
    delay_samples = _numeric(paths, "excess_delay_samples", "MPC delay table").to_numpy()
    delay_chips = _numeric(paths, "excess_delay_chips", "MPC delay table").to_numpy()
    relative_db = _numeric(paths, "relative_power_db", "MPC delay table").to_numpy()
    if not np.allclose(delay_samples, 10.0 * delay_chips, rtol=1e-9, atol=1e-8):
        raise ValueError("MPC delay samples disagree with the frozen 10 samples/chip conversion")
    path_keys = paths.set_index(list(WINDOW_KEY)).index
    window_keys = result.set_index(list(WINDOW_KEY)).index
    extra = path_keys.difference(window_keys)
    if len(extra):
        raise ValueError(f"MPC rows reference unknown selected windows: {list(extra[:3])}")
    window_scene = result.set_index(list(WINDOW_KEY))["scene_id"]
    path_scene = paths.set_index(list(WINDOW_KEY))["scene_id"]
    scene_join = path_scene.to_frame("path_scene").join(window_scene.rename("window_scene"), how="left")
    if not scene_join.path_scene.eq(scene_join.window_scene).all():
        raise ValueError("MPC scene identity disagrees with Stage2 window scene")
    observed_counts = paths.groupby(list(WINDOW_KEY), sort=False).size().reindex(window_keys, fill_value=0)
    declared_counts = counts.astype(int).to_numpy()
    if not np.array_equal(observed_counts.to_numpy(dtype=int), declared_counts):
        raise ValueError("MPC path rows do not reconcile with stage2_mpc_count")

    linear_power = np.power(10.0, relative_db / 10.0)
    if not np.isfinite(linear_power).all() or (linear_power < 0).any():
        raise ValueError("relative MPC powers cannot be represented as finite linear weights")
    paths = paths.copy()
    paths["_delay_samples"] = delay_samples
    paths["_relative_power"] = linear_power
    grouped = {identity: group for identity, group in paths.groupby(list(WINDOW_KEY), sort=False)}

    centroids, spreads, power_sums, statuses = [], [], [], []
    for row in result.itertuples(index=False):
        identity = (getattr(row, "run_id"), getattr(row, "window_id"))
        group = grouped.get(identity)
        if group is None or group.empty:
            centroid = spread = 0.0
            total_power = 1.0
            status = "DIRECT_ONLY_STAGE2_SELECTED_WINDOW"
        else:
            delays = np.concatenate(([0.0], group["_delay_samples"].to_numpy(dtype=float)))
            powers = np.concatenate(([1.0], group["_relative_power"].to_numpy(dtype=float)))
            total_power = float(powers.sum())
            if not np.isfinite(total_power) or total_power <= 0:
                raise ValueError(f"nonpositive/nonfinite relative power sum for window {identity}")
            centroid = float(np.dot(powers, delays) / total_power)
            spread = float(np.sqrt(np.dot(powers, (delays - centroid) ** 2) / total_power))
            status = "SAGE_RELATIVE_DELAY_MOMENTS_DERIVED"
        centroids.append(centroid)
        spreads.append(spread)
        power_sums.append(total_power)
        statuses.append(status)
    result["sage_relative_power_delay_centroid_samples"] = centroids
    result["sage_relative_power_delay_rms_samples"] = spreads
    result["sage_direct_plus_mpc_relative_power_sum"] = power_sums
    result["sage_delay_summary_status"] = statuses
    result["sage_delay_summary_semantics"] = (
        "DIRECT_REFERENCE_UNIT_POWER_AT_ZERO_PLUS_MPC_RELATIVE_POWER; STAGE2_SELECTED WINDOWS")
    return result


def make_wp6_scene_folds(windows, mpcs):
    """Apply the WP3 complete-scene fold helper to all selected windows.

    Environment labels are mapped from the frozen MPC table at scene level;
    zero-MPC selected windows stay in the window table and fold denominator.
    """
    _require_columns(mpcs, {"scene_id", "environment_class"}, "MPC scene labels")
    mapping = mpcs[["scene_id", "environment_class"]].drop_duplicates().copy()
    mapping["scene_id"] = mapping["scene_id"].astype("string").str.strip()
    mapping["environment_class"] = mapping["environment_class"].astype("string").str.strip()
    if mapping.scene_id.duplicated().any():
        raise ValueError("a scene_id maps to multiple environment classes")
    enriched = windows.copy()
    if "environment_class" in enriched.columns:
        enriched = enriched.drop(columns="environment_class")
    enriched = enriched.merge(mapping, on="scene_id", how="left", validate="many_to_one")
    if enriched.environment_class.isna().any():
        missing = sorted(enriched.loc[enriched.environment_class.isna(), "scene_id"].astype(str).unique())
        raise ValueError(f"selected windows lack an MPC-derived scene environment: {missing}")
    return _wp3_make_scene_folds(enriched)


def _normalise_boundary_flags(values):
    result = []
    for value in values:
        if isinstance(value, (bool, np.bool_)):
            result.append(bool(value))
        elif isinstance(value, (int, np.integer, float, np.floating)) and value in (0, 1):
            result.append(bool(value))
        elif str(value).strip().lower() in {"true", "1"}:
            result.append(True)
        elif str(value).strip().lower() in {"false", "0"}:
            result.append(False)
        else:
            raise ValueError(f"invalid PDP boundary flag: {value!r}")
    return np.asarray(result, dtype=bool)


def _fit_window_regression(train, target, predictor):
    y = pd.to_numeric(train[target], errors="coerce").to_numpy(dtype=float)
    x = pd.to_numeric(train[predictor], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    if not valid.any():
        return {"status": "NO_FINITE_TRAINING_RESPONSE", "training_n": 0}
    x_fit, y_fit = x[valid], y[valid]
    baseline_mean = float(y_fit.mean())
    fit = {"status": "PASS", "training_n": int(len(y_fit)), "baseline_mean": baseline_mean,
           "training_response_missing_n": int(len(y) - len(y_fit))}
    if len(y_fit) < 2 or np.ptp(x_fit) <= np.finfo(float).eps * max(1.0, float(np.max(np.abs(x_fit)))):
        fit.update(linear_status="UNIDENTIFIABLE_CONSTANT_OR_SMALL_TRAINING_PREDICTOR",
                   linear_intercept=np.nan, linear_slope=np.nan)
        return fit
    design = np.column_stack((np.ones(len(x_fit)), x_fit))
    coefficients, _, rank, _ = np.linalg.lstsq(design, y_fit, rcond=None)
    if rank < 2 or not np.isfinite(coefficients).all():
        fit.update(linear_status="UNIDENTIFIABLE_RANK_DEFICIENT_TRAINING_DESIGN",
                   linear_intercept=np.nan, linear_slope=np.nan)
    else:
        fit.update(linear_status="PASS", linear_intercept=float(coefficients[0]),
                   linear_slope=float(coefficients[1]))
    return fit


def evaluate_cir_pdp_loso(windows_with_summaries, scene_folds):
    """Predict accepted CIR/PDP window features from SAGE moments by held scene."""
    required = set(WINDOW_KEY) | {
        "scene_id", "stage2_mpc_count", "pdp_peak_at_grid_boundary",
        "sage_relative_power_delay_centroid_samples", "sage_relative_power_delay_rms_samples",
        "pdp_rms_width_code_delay_samples", "pdp_peak_minus_sage_direct_delay_samples",
    }
    _require_columns(windows_with_summaries, required, "CIR/PDP LOSO windows")
    frame = _canonicalize_keys(windows_with_summaries, (*WINDOW_KEY, "scene_id"), "CIR/PDP LOSO windows")
    if frame.duplicated(list(WINDOW_KEY)).any():
        raise ValueError("duplicate selected-window identity in CIR/PDP LOSO input")
    frame["_boundary_flag"] = _normalise_boundary_flags(frame.pdp_peak_at_grid_boundary)
    targets = {
        "pdp_rms_width_code_delay_samples": "sage_relative_power_delay_rms_samples",
        "pdp_peak_minus_sage_direct_delay_samples": "sage_relative_power_delay_centroid_samples",
    }
    for target in targets:
        frame[target] = pd.to_numeric(frame[target], errors="coerce")
        finite = frame[target].dropna().to_numpy(dtype=float)
        if not np.isfinite(finite).all():
            raise ValueError(f"{target} contains non-finite response")
        if target == "pdp_rms_width_code_delay_samples" and (finite < 0).any():
            raise ValueError("PDP RMS width cannot be negative")
    for predictor in targets.values():
        values = pd.to_numeric(frame[predictor], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"SAGE window predictor {predictor} is non-finite")

    expected_keys = set(map(tuple, frame[list(WINDOW_KEY)].itertuples(index=False, name=None)))
    held_scenes = []
    tested_keys = []
    prediction_frames, score_rows = [], []
    for fold in scene_folds:
        held_scene = str(fold["held_out_scene_id"])
        train = _canonicalize_keys(fold["train"], (*WINDOW_KEY, "scene_id"), "LOSO training windows")
        test = _canonicalize_keys(fold["test"], (*WINDOW_KEY, "scene_id"), "LOSO test windows")
        if train.duplicated(list(WINDOW_KEY)).any() or test.duplicated(list(WINDOW_KEY)).any():
            raise ValueError("duplicate window key within a LOSO fold")
        train_scenes = set(train.scene_id.astype(str))
        test_scenes = set(test.scene_id.astype(str))
        if test_scenes != {held_scene}:
            raise ValueError(f"LOSO fold {held_scene} does not contain exactly its held-out scene")
        if train_scenes.intersection(test_scenes):
            raise ValueError(f"scene leakage in CIR/PDP fold {held_scene}")
        test_keys = list(map(tuple, test[list(WINDOW_KEY)].itertuples(index=False, name=None)))
        expected_test = set(map(tuple, frame.loc[frame.scene_id.astype(str).eq(held_scene),
                                                list(WINDOW_KEY)].itertuples(index=False, name=None)))
        if set(test_keys) != expected_test:
            raise ValueError(f"held-out fold {held_scene} omits or adds selected windows")
        expected_train = expected_keys.difference(expected_test)
        train_keys = set(map(tuple, train[list(WINDOW_KEY)].itertuples(index=False, name=None)))
        if train_keys != expected_train:
            raise ValueError(f"training fold {held_scene} omits or adds selected windows")
        if train_keys.intersection(test_keys):
            raise ValueError(f"window identity leakage in CIR/PDP fold {held_scene}")
        held_scenes.append(held_scene)
        tested_keys.extend(test_keys)

        train_data = frame.merge(train[[*WINDOW_KEY]], on=list(WINDOW_KEY), how="inner", validate="one_to_one")
        test_data = frame.merge(test[[*WINDOW_KEY]], on=list(WINDOW_KEY), how="inner", validate="one_to_one")
        for target, predictor in targets.items():
            model_fit = _fit_window_regression(train_data, target, predictor)
            x_test = test_data[predictor].to_numpy(dtype=float)
            baseline = np.full(len(test_data), model_fit.get("baseline_mean", np.nan), dtype=float)
            if model_fit.get("linear_status") == "PASS":
                linear = model_fit["linear_intercept"] + model_fit["linear_slope"] * x_test
            else:
                linear = np.full(len(test_data), np.nan, dtype=float)
            y_test = test_data[target].to_numpy(dtype=float)
            boundary = test_data["_boundary_flag"].to_numpy(dtype=bool)
            prediction_frames.append(pd.DataFrame({
                "outer_held_out_scene_id": held_scene,
                "run_id": test_data.run_id.to_numpy(),
                "window_id": test_data.window_id.to_numpy(),
                "scene_id": test_data.scene_id.to_numpy(),
                "target": target, "predictor": predictor,
                "stage2_mpc_count": test_data.stage2_mpc_count.to_numpy(),
                "pdp_peak_at_grid_boundary": boundary,
                "observed": y_test,
                "predictor_value": x_test,
                "baseline_training_mean": model_fit.get("baseline_mean", np.nan),
                "baseline_prediction": baseline,
                "linear_intercept": model_fit.get("linear_intercept", np.nan),
                "linear_slope": model_fit.get("linear_slope", np.nan),
                "linear_prediction": linear,
                "baseline_fit_status": model_fit["status"],
                "linear_fit_status": model_fit.get("linear_status", "NOT_FIT"),
                "training_scene_ids": json.dumps(
                    sorted(train.scene_id.astype(str).unique().tolist()), separators=(",", ":")),
                "training_window_n": int(len(train_data)),
                "heldout_response_status": np.where(np.isfinite(y_test), "OBSERVED", "MISSING_RESPONSE_RETAINED"),
            }))
            for model_name, predicted in (("INTERCEPT", baseline), ("LINEAR", linear)):
                valid = np.isfinite(y_test) & np.isfinite(predicted)
                if valid.any():
                    residual = predicted[valid] - y_test[valid]
                    status = "SCORED"
                    mae = float(np.mean(np.abs(residual)))
                    rmse = float(np.sqrt(np.mean(residual ** 2)))
                else:
                    status, mae, rmse = "NO_SCORABLE_HELDOUT_RESPONSE", np.nan, np.nan
                score_rows.append({
                    "outer_held_out_scene_id": held_scene, "scene_id": held_scene,
                    "target": target, "model": model_name,
                    "window_n": int(len(test_data)),
                    "scored_window_n": int(valid.sum()),
                    "missing_or_unscorable_window_n": int(len(test_data) - valid.sum()),
                    "boundary_peak_window_n": int(boundary.sum()),
                    "status": status, "mae": mae, "rmse": rmse,
                    "training_scene_ids": sorted(train.scene_id.astype(str).unique().tolist()),
                    "training_window_n": int(len(train_data)),
                    "uncertainty_claim": "PER_SCENE_DESCRIPTIVE; WINDOWS MAY OVERLAP",
                })
    if len(held_scenes) != len(set(held_scenes)) or set(held_scenes) != set(frame.scene_id.astype(str).unique()):
        raise ValueError("scene folds must hold out every selected scene exactly once")
    if len(tested_keys) != len(expected_keys) or set(tested_keys) != expected_keys:
        raise ValueError("scene folds do not partition all selected Stage2 windows exactly once")
    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    scores = pd.DataFrame(score_rows)
    return predictions, scores
