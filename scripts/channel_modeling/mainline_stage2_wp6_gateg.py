"""Gate G supplement: count-conditional marks and discrete-delay dependence.

All likelihood-like scores target an individual Stage2-selected MPC mark and
use equal-scene/equal-window composite weights. They are not a likelihood for
an ordered multi-path window or a physical propagation channel.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, special, stats

import mainline_stage2_wp6 as wp6
import mainline_stage2_wp3 as wp3


DELAY_GRID_CHIPS = 0.01
MIN_DELAY_CHIPS = 0.10
DELAY_GRID_TOLERANCE = 1e-8
MARK_VARIABLES = wp6.MARK_VARIABLES
MARK_FAMILIES = wp6.MARK_FAMILIES
WINDOW_KEY = wp6.WINDOW_KEY
MPC_KEY = wp6.MPC_KEY


def _require_finite(values, label):
    array = np.asarray(values, dtype=float)
    if not np.isfinite(array).all():
        raise ValueError(f"{label} must contain only finite values")
    return array


def delay_grid_cells(values, step=DELAY_GRID_CHIPS, minimum=MIN_DELAY_CHIPS,
                     tolerance=DELAY_GRID_TOLERANCE):
    """Return Voronoi cells for the saved SAGE delay lattice.

    The first cell is truncated at the Stage2 minimum path separation. Values
    are algorithmic grid outputs, not rounded measurements of a continuous
    physical delay.
    """
    x = _require_finite(values, "delay values")
    if not np.isfinite(step) or step <= 0 or not np.isfinite(minimum):
        raise ValueError("delay grid step/minimum must be finite and step positive")
    grid_index = np.rint((x - minimum) / step)
    aligned = minimum + grid_index * step
    if np.any(x < minimum - tolerance) or np.any(np.abs(x - aligned) > tolerance):
        raise ValueError("delay value is outside the declared lattice/grid")
    lower = np.maximum(minimum, x - step / 2.0)
    upper = x + step / 2.0
    return lower, upper


def _family_distribution(family, parameters):
    if family == "gamma":
        return stats.gamma(a=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "lognormal":
        return stats.lognorm(s=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "weibull":
        return stats.weibull_min(c=parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "normal":
        return stats.norm(loc=parameters["loc"], scale=parameters["scale"])
    if family == "laplace":
        return stats.laplace(loc=parameters["loc"], scale=parameters["scale"])
    if family == "student_t":
        return stats.t(df=parameters["df"], loc=parameters["loc"], scale=parameters["scale"])
    raise ValueError(f"unsupported marginal family: {family}")


def _logdiffexp(log_a, log_b):
    """Stable log(exp(log_a)-exp(log_b)) for log_a >= log_b."""
    a, b = np.broadcast_arrays(np.asarray(log_a, dtype=float), np.asarray(log_b, dtype=float))
    if np.any(b > a):
        raise ValueError("logdiffexp requires log_a >= log_b")
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        result = a + np.log1p(-np.exp(b - a))
    return np.where(a == b, -np.inf, result)


def _family_log_interval(family, lower, upper, parameters):
    lower, upper = np.broadcast_arrays(np.asarray(lower, dtype=float), np.asarray(upper, dtype=float))
    if np.any(upper <= lower):
        raise ValueError("interval upper bound must exceed lower bound")
    distribution = _family_distribution(family, parameters)
    logcdf_hi = distribution.logcdf(upper)
    logcdf_lo = distribution.logcdf(lower)
    logsf_lo = distribution.logsf(lower)
    logsf_hi = distribution.logsf(upper)
    use_survival = logcdf_hi > np.log(0.5)
    result = np.empty_like(logcdf_hi, dtype=float)
    if np.any(use_survival):
        result[use_survival] = _logdiffexp(logsf_lo[use_survival], logsf_hi[use_survival])
    if np.any(~use_survival):
        result[~use_survival] = _logdiffexp(logcdf_hi[~use_survival], logcdf_lo[~use_survival])
    return result


def delay_grid_log_mass(family, values, parameters, step=DELAY_GRID_CHIPS,
                        minimum=MIN_DELAY_CHIPS):
    """Log PMF induced by discretizing a positive-support family on SAGE's grid.

    The PMF is conditional on the estimator's minimum excess separation.
    """
    lower, upper = delay_grid_cells(values, step=step, minimum=minimum)
    distribution = _family_distribution(family, parameters)
    numerator = _family_log_interval(family, lower, upper, parameters)
    log_normalizer = float(distribution.logsf(minimum))
    if not np.isfinite(log_normalizer):
        raise ValueError("delay truncation probability is non-finite")
    result = numerator - log_normalizer
    if not np.isfinite(result).all():
        raise ValueError("delay lattice probability is non-finite")
    return result


def delay_grid_mass(family, values, parameters, step=DELAY_GRID_CHIPS,
                    minimum=MIN_DELAY_CHIPS):
    return np.exp(delay_grid_log_mass(family, values, parameters, step, minimum))


def fit_delay_grid_marginal(frame, family, step=DELAY_GRID_CHIPS,
                            minimum=MIN_DELAY_CHIPS):
    """Fit a scene/window-weighted discretized family by grouped likelihood."""
    if family not in MARK_FAMILIES["excess_delay_chips"]:
        raise ValueError(f"unsupported delay candidate: {family}")
    values = _require_finite(frame["excess_delay_chips"], "excess delay")
    delay_grid_cells(values, step=step, minimum=minimum)
    weights = wp3.scene_window_weights(frame)
    mean = float(np.dot(weights, values))
    variance = float(np.dot(weights, (values - mean) ** 2))
    if variance <= np.finfo(float).eps:
        return {"variable": "excess_delay_chips", "family": family,
                "status": "CONSTANT_DATA", "parameters": {},
                "failure_reason": "zero weighted variance", "weighted_log_score": None}
    if family == "lognormal":
        log_values = np.log(values)
        shape0 = float(np.sqrt(np.dot(weights, (log_values - np.dot(weights, log_values)) ** 2)))
        scale0 = float(np.exp(np.dot(weights, log_values)))
    elif family == "gamma":
        shape0 = max(mean * mean / variance, 1e-5)
        scale0 = max(variance / max(mean, 1e-10), 1e-10)
    else:
        shape0 = 1.5
        scale0 = max(mean / special.gamma(1.0 + 1.0 / shape0), 1e-8)
    initial = np.array([np.log(max(shape0, 1e-6)), np.log(max(scale0, 1e-8))])
    bounds = [(-12.0, 8.0), (-20.0, 15.0)]

    def decode(theta):
        return {"shape": float(np.exp(theta[0])), "scale": float(np.exp(theta[1])), "loc": 0.0}

    def objective(theta):
        log_mass = delay_grid_log_mass(family, values, decode(theta), step, minimum)
        return -float(np.dot(weights, log_mass)) if np.isfinite(log_mass).all() else np.inf

    result = optimize.minimize(objective, initial, method="L-BFGS-B", bounds=bounds,
                               options={"maxiter": 1200, "ftol": 1e-12, "gtol": 1e-7})
    parameters = decode(result.x)
    boundary = [index for index, (value, (low, high)) in enumerate(zip(result.x, bounds))
                if abs(value - low) < 1e-5 or abs(value - high) < 1e-5]
    status = "PASS" if result.success and np.isfinite(result.fun) and not boundary else (
        "BOUNDARY_PARAMETER" if boundary else "OPTIMIZER_FAILED")
    return {
        "variable": "excess_delay_chips", "family": family, "status": status,
        "parameters": parameters, "failure_reason": "" if status == "PASS" else str(result.message),
        "optimizer_message": str(result.message), "weighted_log_score": -float(result.fun)
        if np.isfinite(result.fun) else None, "boundary_parameters": boundary,
        "observation_model": "SAGE_DELAY_LATTICE_MASS_CONDITIONAL_ON_MINIMUM_SEPARATION",
        "training_row_n": int(len(frame)),
        "training_window_n": int(frame[list(WINDOW_KEY)].drop_duplicates().shape[0]),
        "training_scene_n": int(frame.scene_id.nunique()),
    }


def _fit_margin(frame, variable, family):
    if variable == "excess_delay_chips":
        return fit_delay_grid_marginal(frame, family)
    values = _require_finite(frame[variable], variable)
    weights = wp3.scene_window_weights(frame)
    fit = wp3._fit_static(values, weights, family)
    return {
        "variable": variable, "family": family, "status": fit.get("status", "FAILED"),
        "parameters": fit.get("parameters", {}), "failure_reason": fit.get("failure_reason", ""),
        "optimizer_message": fit.get("optimizer_message", ""),
        "weighted_log_score": fit.get("weighted_log_score"),
        "boundary_parameters": fit.get("boundary_parameters", []),
        "training_scene_ids": sorted(frame.scene_id.astype(str).unique().tolist()),
        "training_scene_n": int(frame.scene_id.nunique()), "training_mpc_n": int(len(frame)),
        "training_window_n": int(frame[list(WINDOW_KEY)].drop_duplicates().shape[0]),
        "weighting": "WP3_SCENE_WINDOW_BALANCED_PSEUDOLIKELIHOOD",
    }


def _fit_usable(fit):
    return fit.get("status") == "PASS"


def _continuous_logpdf(variable, values, fit):
    return wp3._distribution_logpdf(fit["family"], np.asarray(values, dtype=float), fit["parameters"])


def _conditional_delay_cdf(family, values, parameters, minimum=MIN_DELAY_CHIPS):
    distribution = _family_distribution(family, parameters)
    log_survival = float(distribution.logsf(minimum))
    if not np.isfinite(log_survival):
        raise ValueError("delay marginal has no finite mass above minimum separation")
    values = np.asarray(values, dtype=float)
    log_ratio = distribution.logsf(values) - log_survival
    cdf = -np.expm1(np.minimum(log_ratio, 0.0))
    return np.clip(cdf, 0.0, 1.0)


def product_mark_log_score(fitted_marginals, frame):
    """Per-MPC product of a discrete delay PMF and continuous mark densities."""
    required = {*WINDOW_KEY, "path_id", "scene_id", *MARK_VARIABLES}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"mark frame missing required fields: {sorted(missing)}")
    delay_fit = fitted_marginals.get("excess_delay_chips")
    if not delay_fit or not _fit_usable(delay_fit):
        raise ValueError("delay marginal fit is unavailable")
    scores = delay_grid_log_mass(delay_fit["family"], frame.excess_delay_chips.to_numpy(float),
                                 delay_fit["parameters"])
    for variable in MARK_VARIABLES[1:]:
        fit = fitted_marginals.get(variable)
        if not fit or not _fit_usable(fit):
            raise ValueError(f"marginal fit is unavailable for {variable}")
        scores = scores + _continuous_logpdf(variable, frame[variable].to_numpy(float), fit)
    if not np.isfinite(scores).all():
        raise ValueError("product mark score contains non-finite values")
    return scores


def _normal_log_interval(lower, upper, loc=0.0, scale=1.0):
    lower, upper = np.broadcast_arrays(np.asarray(lower, dtype=float), np.asarray(upper, dtype=float))
    if np.any(upper <= lower) or not np.isfinite(scale) or scale <= 0:
        raise ValueError("normal interval must have positive width and scale")
    lo = (lower - loc) / scale
    hi = (upper - loc) / scale
    use_sf = lo > 0
    result = np.empty_like(lo, dtype=float)
    if np.any(use_sf):
        result[use_sf] = _logdiffexp(special.log_ndtr(-lo[use_sf]),
                                     special.log_ndtr(-hi[use_sf]))
    if np.any(~use_sf):
        result[~use_sf] = _logdiffexp(special.log_ndtr(hi[~use_sf]),
                                      special.log_ndtr(lo[~use_sf]))
    return result


def continuous_pair_copula_log_factor(z_continuous, rho):
    """Bivariate Gaussian-copula log factor for two continuous PITs."""
    z = _require_finite(z_continuous, "continuous latent scores")
    if z.ndim == 1:
        z = z.reshape(1, -1)
    if z.ndim != 2 or z.shape[1] != 2 or not np.isfinite(rho) or abs(rho) >= 1:
        raise ValueError("continuous copula requires an n-by-2 array and |rho| < 1")
    denominator = 1.0 - rho * rho
    first, second = z[:, 0], z[:, 1]
    return (-0.5 * np.log(denominator)
            + (2.0 * rho * first * second - rho * rho * (first * first + second * second))
            / (2.0 * denominator))


def _validate_correlation(correlation, dimension=3):
    corr = np.asarray(correlation, dtype=float)
    if (corr.shape != (dimension, dimension) or not np.isfinite(corr).all()
            or not np.allclose(corr, corr.T, rtol=0, atol=1e-10)
            or not np.allclose(np.diag(corr), 1.0, rtol=0, atol=1e-10)):
        raise ValueError("copula correlation matrix is malformed")
    try:
        np.linalg.cholesky(corr)
    except np.linalg.LinAlgError as exc:
        raise ValueError("copula correlation matrix must be positive definite") from exc
    return corr


def mixed_interval_copula_log_factor(z_lower, z_upper, z_continuous, correlation):
    """Mixed Copula correction for one latent grid variable and two continuous ones.

    The returned log factor is the joint mixed density/mass divided by the
    product of the three marginal measures. The grid-variable likelihood is
    integrated over its latent-normal interval.
    """
    corr = _validate_correlation(correlation)
    lo, hi = np.broadcast_arrays(np.asarray(z_lower, dtype=float), np.asarray(z_upper, dtype=float))
    zc = np.asarray(z_continuous, dtype=float)
    if zc.ndim == 1:
        zc = zc.reshape(1, -1)
    if (lo.ndim != 1 or zc.shape != (len(lo), 2) or np.isnan(lo).any() or np.isnan(hi).any()
            or np.any(hi <= lo) or not np.isfinite(zc).all()):
        raise ValueError("mixed copula inputs have invalid interval or continuous-score shapes")

    corr_cont = corr[1:, 1:]
    cross = corr[0, 1:]
    inv_cont = np.linalg.inv(corr_cont)
    conditional_mean = zc @ inv_cont @ cross
    conditional_variance = float(1.0 - cross @ inv_cont @ cross)
    if not np.isfinite(conditional_variance) or conditional_variance <= 0:
        raise ValueError("copula conditional variance is not positive")
    log_pair_factor = stats.multivariate_normal.logpdf(zc, mean=np.zeros(2), cov=corr_cont)
    log_pair_factor -= stats.norm.logpdf(zc).sum(axis=1)
    log_conditional_mass = _normal_log_interval(lo, hi, loc=conditional_mean,
                                                scale=np.sqrt(conditional_variance))
    log_independent_mass = _normal_log_interval(lo, hi)
    result = log_pair_factor + log_conditional_mass - log_independent_mass
    if not np.isfinite(result).all():
        raise ValueError("mixed copula interval factor is non-finite")
    return result


def mixed_gaussian_copula_log_score(fitted_marginals, correlation, frame):
    """Per-MPC mixed log score: delay-cell mass × continuous densities × copula."""
    corr = _validate_correlation(correlation)
    base = product_mark_log_score(fitted_marginals, frame)
    lower, upper = delay_grid_cells(frame.excess_delay_chips.to_numpy(float))
    delay_fit = fitted_marginals["excess_delay_chips"]
    marginal_lo = _conditional_delay_cdf(delay_fit["family"], lower, delay_fit["parameters"])
    marginal_hi = _conditional_delay_cdf(delay_fit["family"], upper, delay_fit["parameters"])
    if np.any(marginal_hi <= marginal_lo):
        raise ValueError("delay marginal maps a lattice interval to zero probability")
    z_lo = special.ndtri(marginal_lo)
    z_hi = special.ndtri(marginal_hi)
    uniforms = []
    for variable in MARK_VARIABLES[1:]:
        fit = fitted_marginals[variable]
        distribution = wp6._distribution_cdf(fit["family"], frame[variable].to_numpy(float),
                                             fit["parameters"])
        uniforms.append(np.clip(distribution, 1e-12, 1.0 - 1e-12))
    z_cont = special.ndtri(np.column_stack(uniforms))
    return base + mixed_interval_copula_log_factor(z_lo, z_hi, z_cont, corr)


def _decode_partial_correlations(theta):
    p12, p13, p23_given_1 = np.tanh(np.asarray(theta, dtype=float))
    r23 = p12 * p13 + np.sqrt(max(0.0, 1.0 - p12 * p12) * max(0.0, 1.0 - p13 * p13)) * p23_given_1
    return np.array([[1.0, p12, p13], [p12, 1.0, r23], [p13, r23, 1.0]])


def _correlation_start_from_kendall(frame, fitted_marginals):
    pairs = np.eye(3)
    scenes = sorted(frame.scene_id.astype(str).unique())
    columns = []
    delay_fit = fitted_marginals[MARK_VARIABLES[0]]
    lower, upper = delay_grid_cells(frame.excess_delay_chips.to_numpy(float))
    u_lo = _conditional_delay_cdf(delay_fit["family"], lower, delay_fit["parameters"])
    u_hi = _conditional_delay_cdf(delay_fit["family"], upper, delay_fit["parameters"])
    columns.append((u_lo + u_hi) / 2.0)
    for variable in MARK_VARIABLES[1:]:
        fit = fitted_marginals[variable]
        cdf = wp6._distribution_cdf(fit["family"], frame[variable].to_numpy(float), fit["parameters"])
        columns.append(np.clip(cdf, 1e-12, 1.0 - 1e-12))
    uniforms = np.column_stack(columns)
    for i in range(3):
        for j in range(i + 1, 3):
            rhos = []
            for scene in scenes:
                mask = frame.scene_id.astype(str).to_numpy() == scene
                tau = stats.kendalltau(uniforms[mask, i], uniforms[mask, j], variant="b").statistic
                if not np.isfinite(tau):
                    tau = 0.0
                rhos.append(np.sin(np.pi * tau / 2.0))
            pairs[i, j] = pairs[j, i] = float(np.mean(rhos))
    # Project only the starting value; fitted parameters remain unconstrained
    # except for the valid-correlation vine parameterization.
    eigenvalues, eigenvectors = np.linalg.eigh(pairs)
    projected = (eigenvectors * np.maximum(eigenvalues, 1e-5)) @ eigenvectors.T
    scale = np.sqrt(np.diag(projected))
    projected /= np.outer(scale, scale)
    np.fill_diagonal(projected, 1.0)
    r12, r13, r23 = projected[0, 1], projected[0, 2], projected[1, 2]
    p23 = (r23 - r12 * r13) / np.sqrt(max(1e-10, (1 - r12 * r12) * (1 - r13 * r13)))
    return np.arctanh(np.clip([r12, r13, p23], -0.95, 0.95))


def fit_mixed_gaussian_copula(training_frame, fitted_marginals):
    """Fit a scene/window-balanced mixed composite likelihood on training rows."""
    if any(not _fit_usable(fitted_marginals.get(variable, {})) for variable in MARK_VARIABLES):
        return None, {"status": "MARGINAL_FIT_UNAVAILABLE",
                      "scene_n": int(training_frame.scene_id.nunique())}
    if training_frame.scene_id.nunique() < 2:
        return None, {"status": "INSUFFICIENT_TRAINING_SCENES", "scene_n": int(training_frame.scene_id.nunique())}
    base = product_mark_log_score(fitted_marginals, training_frame)
    weights = wp3.scene_window_weights(training_frame)
    initial_moment = _correlation_start_from_kendall(training_frame, fitted_marginals)

    def objective(theta):
        corr = _decode_partial_correlations(theta)
        try:
            score = mixed_gaussian_copula_log_score(fitted_marginals, corr, training_frame)
        except (ValueError, np.linalg.LinAlgError):
            return np.inf
        return -float(np.dot(weights, score))

    candidates = []
    for start_name, start in (("IDENTITY", np.zeros(3)), ("KENDALL_TAU_B", initial_moment)):
        result = optimize.minimize(objective, start, method="L-BFGS-B",
                                  bounds=[(-4.0, 4.0)] * 3,
                                  options={"maxiter": 500, "ftol": 1e-11, "gtol": 1e-6})
        candidates.append((result, start_name))
    result, start_name = min(candidates, key=lambda item: item[0].fun)
    corr = _decode_partial_correlations(result.x)
    boundary = bool(np.any(np.abs(result.x) >= 3.999))
    status = "PASS" if result.success and np.isfinite(result.fun) and not boundary else (
        "BOUNDARY_CORRELATION" if boundary else "OPTIMIZER_FAILED")
    diagnostics = {
        "status": status, "optimizer_message": str(result.message),
        "start_selected": start_name, "objective_weighted_mean_log_score": -float(result.fun)
        if np.isfinite(result.fun) else None,
        "parameter_vector": result.x.tolist(), "correlation": corr.tolist(),
        "boundary_parameter": boundary, "training_scene_ids": sorted(training_frame.scene_id.astype(str).unique()),
        "training_scene_n": int(training_frame.scene_id.nunique()),
        "training_window_n": int(training_frame[list(WINDOW_KEY)].drop_duplicates().shape[0]),
        "training_mpc_n": int(len(training_frame)),
        "weighting": "EQUAL_SCENE_EQUAL_WINDOW_SPLIT_OVER_MPC_ROWS",
        "estimand": "STAGE2_SELECTED_SINGLE_MPC_MARK_COMPOSITE_LIKELIHOOD",
    }
    return (corr if status == "PASS" else None), diagnostics


def _score_margin(fit, frame, variable):
    if not _fit_usable(fit):
        raise ValueError(f"marginal fit unavailable for {variable}")
    if variable == "excess_delay_chips":
        return delay_grid_log_mass(fit["family"], frame[variable].to_numpy(float), fit["parameters"])
    return _continuous_logpdf(variable, frame[variable].to_numpy(float), fit)


def select_families_nested(frame, training_scenes, count=None):
    """Select per-variable families by inner complete-scene LOSO.

    `count=None` selects M0, while a selected integer N selects the
    count-conditioned M1 margin within that Stage2 count stratum.
    """
    scenes = tuple(sorted({str(scene) for scene in training_scenes}))
    if len(scenes) < 3:
        raise ValueError("nested selection requires at least three training scenes")
    base = frame.loc[frame.scene_id.astype(str).isin(scenes)].copy()
    if count is not None:
        base = base.loc[base.n_mpc.astype(int).eq(int(count))].copy()
    rows = []
    selected = {}
    for variable, candidates in MARK_FAMILIES.items():
        family_scores = []
        for family in candidates:
            scene_scores = []
            for held_scene in scenes:
                train = base.loc[base.scene_id.astype(str).ne(held_scene)].copy()
                test = base.loc[base.scene_id.astype(str).eq(held_scene)].copy()
                status, score, reason = "PASS", np.nan, ""
                if train.empty or test.empty:
                    status, reason = "NO_TRAIN_OR_HELDOUT_SUPPORT", "training or held-out scene has no rows in stratum"
                else:
                    try:
                        fit = _fit_margin(train, variable, family)
                        if not _fit_usable(fit):
                            status, reason = fit.get("status", "FIT_FAILED"), fit.get("failure_reason", "")
                        else:
                            row_score = _score_margin(fit, test, variable)
                            per_window = pd.DataFrame({
                                "run_id": test.run_id.astype(str).to_numpy(),
                                "window_id": test.window_id.astype(str).to_numpy(),
                                "score": row_score,
                            }).groupby(list(WINDOW_KEY), sort=False).score.mean()
                            score = float(per_window.mean())
                            if not np.isfinite(score):
                                status, reason = "NONFINITE_SCORE", "inner held-out score is non-finite"
                    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                        status, reason = "FIT_OR_SCORE_ERROR", str(exc)
                rows.append({
                    "count_condition": "ALL" if count is None else int(count),
                    "variable": variable, "family": family,
                    "inner_held_out_scene_id": held_scene,
                    "inner_training_scene_ids": json.dumps([s for s in scenes if s != held_scene]),
                    "training_mpc_n": int(len(train)), "heldout_mpc_n": int(len(test)),
                    "inner_scene_window_mean_log_score": score,
                    "status": status, "failure_reason": reason,
                })
                if status == "PASS":
                    scene_scores.append(score)
            candidate_mean = float(np.mean(scene_scores)) if len(scene_scores) == len(scenes) else np.nan
            family_scores.append((family, candidate_mean))
        selectable = [(family, score) for family, score in family_scores if np.isfinite(score)]
        selected[variable] = max(selectable, key=lambda item: item[1])[0] if selectable else None
    return selected, pd.DataFrame(rows)


def fit_marginals(frame, families):
    fits = {}
    for variable in MARK_VARIABLES:
        family = families.get(variable)
        if family is None:
            fits[variable] = {"variable": variable, "family": None, "status": "NO_SELECTABLE_FAMILY",
                              "parameters": {}, "failure_reason": "all inner candidates unsupported or failed"}
        else:
            fits[variable] = _fit_margin(frame, variable, family)
    return fits


def prepare_ranked_marks(mpcs):
    """Bind frozen sequential path IDs to their sorted SAGE delay ranks."""
    required = {"run_id", "window_id", "path_id", "scene_id", "selected_L", "excess_delay_chips"}
    missing = required.difference(mpcs.columns)
    if missing:
        raise ValueError(f"ranked MPC input missing columns: {sorted(missing)}")
    frame = mpcs.copy()
    key = list(MPC_KEY)
    if frame.duplicated(key).any():
        raise ValueError("ranked MPC input has duplicate path identity")
    frame["path_id_int"] = pd.to_numeric(frame.path_id, errors="raise").astype(int)
    frame["selected_L_int"] = pd.to_numeric(frame.selected_L, errors="raise").astype(int)
    frame["excess_delay_chips"] = pd.to_numeric(frame.excess_delay_chips, errors="raise")
    rows = []
    for identity, group in frame.groupby(list(WINDOW_KEY), sort=False, dropna=False):
        ordered = group.sort_values("path_id_int", kind="stable")
        n = len(ordered)
        expected_ids = list(range(2, n + 2))
        actual_ids = ordered.path_id_int.tolist()
        if actual_ids != expected_ids:
            raise ValueError(f"path identity sequence is incomplete for {identity}: {actual_ids}")
        if not ordered.selected_L_int.eq(n + 1).all():
            raise ValueError(f"selected_L disagrees with path count for {identity}")
        delays = ordered.excess_delay_chips.to_numpy(float)
        if not np.isfinite(delays).all() or np.any(np.diff(delays) <= 0):
            raise ValueError(f"path delay order is not strictly increasing for {identity}")
        ordered["n_mpc"] = n
        ordered["mpc_rank"] = np.arange(1, n + 1)
        rows.append(ordered)
    if not rows:
        raise ValueError("ranked MPC input is empty")
    return pd.concat(rows, ignore_index=True)


def build_rank_diagnostics(mpcs):
    """Scene- and window-preserving summaries of count/rank effects."""
    frame = prepare_ranked_marks(mpcs)
    summary_rows = []
    contrast_rows = []
    for (scene, count, rank), group in frame.groupby(["scene_id", "n_mpc", "mpc_rank"], sort=True):
        summary_rows.append({
            "scene_id": scene, "n_mpc": int(count), "mpc_rank": int(rank),
            "window_n": int(group[list(WINDOW_KEY)].drop_duplicates().shape[0]),
            "path_row_n": int(len(group)),
            **{f"{variable}_window_macro_mean": float(
                group.groupby(list(WINDOW_KEY), sort=False)[variable].mean().mean())
               for variable in MARK_VARIABLES},
        })
    for (scene, count), group in frame.groupby(["scene_id", "n_mpc"], sort=True):
        wide = group.pivot(index=list(WINDOW_KEY), columns="mpc_rank", values=list(MARK_VARIABLES))
        for variable in MARK_VARIABLES:
            for rank in range(1, int(count)):
                delta = wide[variable][rank + 1] - wide[variable][rank]
                if len(delta):
                    contrast_rows.append({
                        "scene_id": scene, "n_mpc": int(count), "variable": variable,
                        "from_rank": rank, "to_rank": rank + 1,
                        "window_n": int(len(delta)), "mean_within_window_delta": float(delta.mean()),
                        "median_within_window_delta": float(delta.median()),
                        "min_within_window_delta": float(delta.min()),
                        "max_within_window_delta": float(delta.max()),
                        "interpretation": "DESCRIPTIVE_SAGE_DELAY_SORTED_COMPONENT_RANK",
                    })
    return pd.DataFrame(summary_rows), pd.DataFrame(contrast_rows)


def _window_scene_scores(path_scores, models):
    rows = []
    for (run_id, window_id), group in path_scores.groupby(list(WINDOW_KEY), sort=True):
        row = {"run_id": run_id, "window_id": window_id,
               "scene_id": group.scene_id.iloc[0], "n_mpc": int(len(group))}
        for model in models:
            values = group[model].to_numpy(float)
            row[f"{model}_mean_per_mpc"] = float(values.mean()) if np.isfinite(values).all() else np.nan
            row[f"{model}_sum_composite"] = float(values.sum()) if np.isfinite(values).all() else np.nan
            row[f"{model}_status"] = "SCORED" if np.isfinite(values).all() else "UNSCORABLE"
        rows.append(row)
    windows = pd.DataFrame(rows)
    scene_rows = []
    comparison_pairs = (
        ("M0_independent", "M1_count_conditional", "M1_minus_M0"),
        ("M0_independent", "C0_mixed_copula", "C0_minus_M0"),
        ("M1_count_conditional", "C1_count_mixed_copula", "C1_minus_M1"),
    )
    for scene, group in windows.groupby("scene_id", sort=True):
        row = {"scene_id": scene, "window_n": int(len(group)),
               "mpc_n": int(group.n_mpc.sum())}
        for model in models:
            values = group[f"{model}_mean_per_mpc"].to_numpy(float)
            valid = np.isfinite(values)
            row[f"{model}_scene_macro_log_score"] = float(values[valid].mean()) if valid.any() else np.nan
            row[f"{model}_scored_window_n"] = int(valid.sum())
            row[f"{model}_unscorable_window_n"] = int((~valid).sum())
            row[f"{model}_status"] = "SCORED" if valid.all() else (
                "PARTIAL" if valid.any() else "UNSCORABLE")
        by_key = group.set_index(list(WINDOW_KEY))
        for left, right, delta in comparison_pairs:
            left_values = by_key[f"{left}_mean_per_mpc"].to_numpy(float)
            right_values = by_key[f"{right}_mean_per_mpc"].to_numpy(float)
            paired = np.isfinite(left_values) & np.isfinite(right_values)
            differences = right_values[paired] - left_values[paired]
            row[f"{delta}_paired_window_n"] = int(paired.sum())
            row[f"{delta}_unpaired_window_n"] = int((~paired).sum())
            row[f"{delta}_left_mean_paired"] = float(left_values[paired].mean()) if paired.any() else np.nan
            row[f"{delta}_right_mean_paired"] = float(right_values[paired].mean()) if paired.any() else np.nan
            row[f"{delta}_nats_per_mpc"] = float(differences.mean()) if paired.any() else np.nan
            row[f"{delta}_median_window_delta"] = float(np.median(differences)) if paired.any() else np.nan
        scene_rows.append(row)
    return windows, pd.DataFrame(scene_rows)


def build_count_scene_scores(path_scores, models):
    """Held-out model scores by scene and selected-window MPC count."""
    rows = []
    for (scene, count), group in path_scores.groupby(["scene_id", "n_mpc"], sort=True):
        windows = []
        for (run_id, window_id), window in group.groupby(list(WINDOW_KEY), sort=True):
            row = {"run_id": run_id, "window_id": window_id}
            for model in models:
                values = window[model].to_numpy(float)
                row[model] = float(values.mean()) if np.isfinite(values).all() else np.nan
            windows.append(row)
        window_frame = pd.DataFrame(windows)
        result = {"scene_id": str(scene), "n_mpc": int(count),
                  "selected_mpc_window_n": int(len(window_frame)),
                  "mpc_row_n": int(len(group))}
        for model in models:
            values = window_frame[model].to_numpy(float)
            valid = np.isfinite(values)
            result[f"{model}_scored_window_n"] = int(valid.sum())
            result[f"{model}_scene_macro_log_score"] = float(values[valid].mean()) if valid.any() else np.nan
        for left, right, delta in (
            ("M0_independent", "M1_count_conditional", "M1_minus_M0"),
            ("M0_independent", "C0_mixed_copula", "C0_minus_M0"),
            ("M1_count_conditional", "C1_count_mixed_copula", "C1_minus_M1"),
        ):
            left_values = window_frame[left].to_numpy(float)
            right_values = window_frame[right].to_numpy(float)
            paired = np.isfinite(left_values) & np.isfinite(right_values)
            differences = right_values[paired] - left_values[paired]
            result[f"{delta}_paired_window_n"] = int(paired.sum())
            result[f"{delta}_nats_per_mpc"] = float(differences.mean()) if paired.any() else np.nan
        rows.append(result)
    return pd.DataFrame(rows)


def evaluate_nested_loso(mpcs, expected_scenes=13, randomized_pit_draws=32, seed=20261030,
                         progress_callback=None):
    """Nested complete-scene LOSO for M0/M1 and tie-aware C0/C1 comparisons."""
    frame = prepare_ranked_marks(mpcs)
    scenes = tuple(sorted(frame.scene_id.astype(str).unique()))
    if len(scenes) != expected_scenes:
        raise ValueError(f"expected {expected_scenes} complete scenes, got {len(scenes)}")
    if set(frame.n_mpc.astype(int)) != {1, 2, 3}:
        raise ValueError("expected Stage2 MPC count strata N=1,2,3")
    models = ("M0_independent", "M1_count_conditional", "C0_mixed_copula", "C1_count_mixed_copula")
    fold_rows, selection_rows, parameter_rows, copula_rows, score_rows = [], [], [], [], []
    randomized_rows = []
    rng = np.random.default_rng(seed)
    for fold_index, held_scene in enumerate(scenes, start=1):
        training_scenes = tuple(scene for scene in scenes if scene != held_scene)
        train = frame.loc[frame.scene_id.astype(str).isin(training_scenes)].copy()
        test = frame.loc[frame.scene_id.astype(str).eq(held_scene)].copy()
        m0_families, m0_inner = select_families_nested(train, training_scenes)
        m0_fits = fit_marginals(train, m0_families)
        m1_families, m1_fits = {}, {}
        for count in (1, 2, 3):
            family, inner = select_families_nested(train, training_scenes, count=count)
            m1_families[count] = family
            m1_fits[count] = fit_marginals(train.loc[train.n_mpc.eq(count)].copy(), family)
            inner["outer_held_out_scene_id"] = held_scene
            inner["model"] = "M1_count_conditional"
            selection_rows.append(inner)
        m0_inner["outer_held_out_scene_id"] = held_scene
        m0_inner["model"] = "M0_count_independent"
        selection_rows.append(m0_inner)

        c0, c0_diag = fit_mixed_gaussian_copula(train, m0_fits)
        c1, c1_diagnostics = {}, {}
        for count in (1, 2, 3):
            count_train = train.loc[train.n_mpc.eq(count)].copy()
            c1[count], c1_diagnostics[count] = fit_mixed_gaussian_copula(count_train, m1_fits[count])
        fold_rows.append({
            "outer_held_out_scene_id": held_scene,
            "outer_training_scene_ids": json.dumps(list(training_scenes)),
            "training_window_n": int(train[list(WINDOW_KEY)].drop_duplicates().shape[0]),
            "training_mpc_n": int(len(train)), "heldout_window_n": int(test[list(WINDOW_KEY)].drop_duplicates().shape[0]),
            "heldout_mpc_n": int(len(test)), "m0_family_selection_status":
            "PASS" if all(value is not None for value in m0_families.values()) else "INCOMPLETE",
            "m1_family_selection_status": "PASS" if all(
                value is not None for count in m1_families.values() for value in count.values()) else "INCOMPLETE",
            "c0_status": c0_diag["status"],
            "c1_status": json.dumps({str(n): c1_diagnostics[n]["status"] for n in (1, 2, 3)}, sort_keys=True),
        })
        for model, fits in (("M0", m0_fits),):
            for variable, fit in fits.items():
                parameter_rows.append({"outer_held_out_scene_id": held_scene, "model": model,
                                       "count_condition": "ALL", "variable": variable,
                                       **{k: v for k, v in fit.items() if k not in {"parameters"}},
                                       "parameters_json": json.dumps(fit.get("parameters", {}), sort_keys=True)})
        for count in (1, 2, 3):
            for variable, fit in m1_fits[count].items():
                parameter_rows.append({"outer_held_out_scene_id": held_scene, "model": "M1",
                                       "count_condition": count, "variable": variable,
                                       **{k: v for k, v in fit.items() if k not in {"parameters"}},
                                       "parameters_json": json.dumps(fit.get("parameters", {}), sort_keys=True)})
        copula_rows.append({"outer_held_out_scene_id": held_scene, "model": "C0",
                            **{k: v for k, v in c0_diag.items() if k != "correlation"},
                            "correlation_json": json.dumps(c0.tolist()) if c0 is not None else ""})
        for count in (1, 2, 3):
            copula_rows.append({"outer_held_out_scene_id": held_scene, "model": "C1",
                                "count_condition": count,
                                **{k: v for k, v in c1_diagnostics[count].items() if k != "correlation"},
                                "correlation_json": json.dumps(c1[count].tolist()) if c1[count] is not None else ""})

        row = test[[*MPC_KEY, "scene_id", "n_mpc", "mpc_rank"]].copy().reset_index(drop=True)
        row["outer_held_out_scene_id"] = held_scene
        if all(_fit_usable(m0_fits[variable]) for variable in MARK_VARIABLES):
            row["M0_independent"] = product_mark_log_score(m0_fits, test)
        else:
            row["M0_independent"] = np.nan
        c0_score = (mixed_gaussian_copula_log_score(m0_fits, c0, test) if c0 is not None
                    else np.full(len(test), np.nan))
        row["C0_mixed_copula"] = c0_score
        m1_ind, c1_score = np.full(len(test), np.nan), np.full(len(test), np.nan)
        for count in (1, 2, 3):
            positions = np.flatnonzero(test.n_mpc.to_numpy(int) == count)
            if len(positions):
                test_group = test.iloc[positions]
                if all(_fit_usable(m1_fits[count][variable]) for variable in MARK_VARIABLES):
                    m1_ind[positions] = product_mark_log_score(m1_fits[count], test_group)
                if c1[count] is not None:
                    c1_score[positions] = mixed_gaussian_copula_log_score(m1_fits[count], c1[count], test_group)
        row["M1_count_conditional"] = m1_ind
        row["C1_count_mixed_copula"] = c1_score
        score_rows.append(row)

        # Distributional-transform sensitivity: randomize only delay PITs on
        # the training-fold lattice cells, fit a weighted Gaussian correlation,
        # and evaluate it with the deterministic mixed held-out score.
        if randomized_pit_draws > 0 and c0 is not None:
            for draw in range(randomized_pit_draws):
                try:
                    random_corr = _randomized_pit_correlation(train, m0_fits, rng)
                    random_score = mixed_gaussian_copula_log_score(m0_fits, random_corr, test)
                    random_path = test[[*MPC_KEY, "scene_id", "n_mpc"]].copy()
                    random_path["score"] = random_score
                    random_window = random_path.groupby(list(WINDOW_KEY), sort=False).score.mean()
                    independent_window = row.assign(score=row.M0_independent).groupby(
                        list(WINDOW_KEY), sort=False).score.mean()
                    randomized_rows.append({
                        "outer_held_out_scene_id": held_scene, "draw": draw,
                        "status": "PASS",
                        "training_method": "RANDOMIZED_DISTRIBUTIONAL_TRANSFORM_WEIGHTED_GAUSSIAN_CORRELATION",
                        "heldout_mean_window_per_mpc_score": float(random_window.mean()),
                        "independent_mean_window_per_mpc_score": float(independent_window.mean()),
                        "copula_minus_independent": float(random_window.mean() - independent_window.mean()),
                        "correlation_json": json.dumps(random_corr.tolist()),
                        "failure_reason": "",
                    })
                except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
                    randomized_rows.append({
                        "outer_held_out_scene_id": held_scene, "draw": draw,
                        "status": "FAILED_SENSITIVITY_DRAW",
                        "training_method": "RANDOMIZED_DISTRIBUTIONAL_TRANSFORM_WEIGHTED_GAUSSIAN_CORRELATION",
                        "heldout_mean_window_per_mpc_score": np.nan,
                        "independent_mean_window_per_mpc_score": np.nan,
                        "copula_minus_independent": np.nan,
                        "correlation_json": "", "failure_reason": str(exc),
                    })

        if progress_callback is not None:
            progress_callback(fold_index, len(scenes), held_scene)

    path_scores = pd.concat(score_rows, ignore_index=True)
    window_scores, scene_scores = _window_scene_scores(path_scores, models)
    family_scores = pd.concat(selection_rows, ignore_index=True)
    parameter_table = pd.DataFrame(parameter_rows)
    copula_table = pd.DataFrame(copula_rows)
    fold_table = pd.DataFrame(fold_rows)
    rand_table = pd.DataFrame(randomized_rows)
    rank_summary, rank_contrasts = build_rank_diagnostics(frame)
    return {
        "folds": fold_table, "family_selection": family_scores,
        "parameters": parameter_table, "copula_diagnostics": copula_table,
        "path_scores": path_scores, "window_scores": window_scores,
        "scene_scores": scene_scores, "randomized_pit_sensitivity": rand_table,
        "rank_summary": rank_summary, "rank_contrasts": rank_contrasts,
        "count_scene_support": build_count_scene_support(frame),
        "count_scene_scores": build_count_scene_scores(path_scores, models),
    }


def build_count_scene_support(mpcs):
    """Count support by complete scene; never treats MPC rows as scenes."""
    frame = prepare_ranked_marks(mpcs)
    rows = []
    for (scene, count), group in frame.groupby(["scene_id", "n_mpc"], sort=True):
        windows = group.groupby(list(WINDOW_KEY), sort=False)
        row = {"scene_id": str(scene), "n_mpc": int(count),
               "selected_mpc_window_n": int(windows.ngroups), "mpc_row_n": int(len(group))}
        for variable in MARK_VARIABLES:
            row[f"{variable}_window_macro_mean"] = float(windows[variable].mean().mean())
            row[f"{variable}_window_macro_median"] = float(windows[variable].median().median())
        rows.append(row)
    return pd.DataFrame(rows)


def _randomized_pit_correlation(frame, fits, rng):
    delay_fit = fits["excess_delay_chips"]
    lower, upper = delay_grid_cells(frame.excess_delay_chips.to_numpy(float))
    u_lo = _conditional_delay_cdf(delay_fit["family"], lower, delay_fit["parameters"])
    u_hi = _conditional_delay_cdf(delay_fit["family"], upper, delay_fit["parameters"])
    uniforms = [rng.uniform(u_lo, u_hi)]
    for variable in MARK_VARIABLES[1:]:
        fit = fits[variable]
        cdf = wp6._distribution_cdf(fit["family"], frame[variable].to_numpy(float), fit["parameters"])
        uniforms.append(np.clip(cdf, 1e-12, 1 - 1e-12))
    z = special.ndtri(np.column_stack(uniforms))
    weights = wp3.scene_window_weights(frame)
    mean = np.sum(z * weights[:, None], axis=0)
    centered = z - mean
    cov = (centered * weights[:, None]).T @ centered
    scale = np.sqrt(np.maximum(np.diag(cov), 1e-12))
    corr = cov / np.outer(scale, scale)
    corr = 0.5 * (corr + corr.T)
    np.fill_diagonal(corr, 1.0)
    eigenvalues, eigenvectors = np.linalg.eigh(corr)
    if eigenvalues.min() <= 1e-8:
        corr = (eigenvectors * np.maximum(eigenvalues, 1e-8)) @ eigenvectors.T
        scale = np.sqrt(np.diag(corr))
        corr /= np.outer(scale, scale)
        np.fill_diagonal(corr, 1.0)
    return _validate_correlation(corr)
