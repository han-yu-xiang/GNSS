"""WP6 analysis primitives for the frozen Mainline Stage2 population.

The count model is conditional on a window having been selected by Stage2.
It is not a model of all Stage0 windows.
"""

from __future__ import annotations

import hashlib
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
    "modeling_role", "excess_delay_chips", "doppler_offset_hz",
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
    if copula is None:
        raise ValueError("copula matrix is unavailable; retain fold as unscorable")
    corr = np.asarray(copula, dtype=float)
    if corr.shape != (len(MARK_VARIABLES), len(MARK_VARIABLES)):
        raise ValueError("copula matrix dimension does not match mark variables")
    product_rows = np.zeros(len(frame), dtype=float)
    uniforms = np.zeros((len(frame), len(MARK_VARIABLES)), dtype=float)
    for index, variable in enumerate(MARK_VARIABLES):
        fit = fitted_marginals[variable]
        if not _usable_fit(fit):
            raise ValueError(f"marginal fit unavailable for {variable}: {fit.get('status')}")
        family, parameters = fit["family"], fit["parameters"]
        product_rows += _wp3_distribution_logpdf(family, frame[variable].to_numpy(), parameters)
        uniforms[:, index] = _distribution_cdf(family, frame[variable].to_numpy(), parameters)
    copula_rows = gaussian_copula_log_density(uniforms, corr)
    finite = np.isfinite(product_rows) & np.isfinite(copula_rows)
    work = frame[[*WINDOW_KEY, "scene_id"]].copy()
    work["product_row_score"] = np.where(finite, product_rows, np.nan)
    work["copula_row_score"] = np.where(finite, product_rows + copula_rows, np.nan)
    work["row_status"] = np.where(finite, "SCORED", "UNSCORABLE_NONFINITE_DENSITY")
    rows = []
    for identity, group in work.groupby(list(WINDOW_KEY), sort=True, dropna=False):
        status = "SCORED" if group.row_status.eq("SCORED").all() else "UNSCORABLE_NONFINITE_DENSITY"
        rows.append({
            "run_id": identity[0], "window_id": identity[1],
            "scene_id": group.scene_id.iloc[0], "path_n": int(len(group)), "status": status,
            "product_marginal_log_score": float(group.product_row_score.sum()) if status == "SCORED" else np.nan,
            "gaussian_copula_log_score": float(group.copula_row_score.sum()) if status == "SCORED" else np.nan,
        })
    per_window = pd.DataFrame(rows)
    scene_rows = []
    for scene_id, group in per_window.groupby("scene_id", sort=True, dropna=False):
        status = "SCORED" if group.status.eq("SCORED").all() else "UNSCORABLE_NONFINITE_DENSITY"
        scene_rows.append({
            "scene_id": scene_id, "window_n": int(len(group)),
            "unscorable_window_n": int(group.status.ne("SCORED").sum()), "status": status,
            "product_marginal_mean_window_log_score": (
                float(group.product_marginal_log_score.mean()) if status == "SCORED" else np.nan),
            "gaussian_copula_mean_window_log_score": (
                float(group.gaussian_copula_log_score.mean()) if status == "SCORED" else np.nan),
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
            tail_frames.append(calibrate_mark_tails(fit, test, variable))
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
        if all_marginals_pass and corr is not None:
            per_window, per_scene = score_mark_models(fitted, corr, test)
            per_window.insert(0, "outer_held_out_scene_id", held_scene)
            per_scene.insert(0, "outer_held_out_scene_id", held_scene)
            window_frames.append(per_window)
            scene_score_frames.append(per_scene)
            scene_score = per_scene.iloc[0]
            fold_rows.append({
                "held_out_scene_id": held_scene,
                "training_scene_ids": sorted(train.scene_id.astype(str).unique().tolist()),
                "training_scene_n": int(train.scene_id.nunique()),
                "test_window_n": int(test[list(WINDOW_KEY)].drop_duplicates().shape[0]),
                "test_mpc_n": int(len(test)),
                "selected_families": selected,
                "fit_status": "PASS",
                "copula_status": copula_diag.get("status"),
                "product_marginal_mean_window_log_score": scene_score.product_marginal_mean_window_log_score,
                "gaussian_copula_mean_window_log_score": scene_score.gaussian_copula_mean_window_log_score,
                "copula_minus_product_score": scene_score.gaussian_copula_mean_window_log_score
                    - scene_score.product_marginal_mean_window_log_score,
                "uncertainty_claim": "DESCRIPTIVE_LOSO_FOLDS; TRAINING SETS OVERLAP",
            })
        else:
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
