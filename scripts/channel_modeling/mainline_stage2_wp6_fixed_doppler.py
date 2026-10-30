"""Fixed-bin Doppler scoring for the bounded Gate G observation target.

This module scores the fixed-binned Stage2 marks, not the adaptive SAGE
estimator's exact output likelihood. All parameter estimation is a
scene/window-balanced composite likelihood conditional on Stage2 selection.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import optimize, special

import mainline_stage2_wp3 as wp3
import mainline_stage2_wp6 as wp6
import mainline_stage2_wp6_gateg as gateg


DOPPLER_WIDTHS_HZ = (5.0, 10.0, 20.0)
DOPPLER_PRIMARY_WIDTH_HZ = 5.0
DOPPLER_FAMILIES = ("normal", "student_t")


def _positive_width(width):
    width = float(width)
    if not np.isfinite(width) or width <= 0.0:
        raise ValueError("bin width must be finite and positive")
    return width


def doppler_bin_indices(values, width):
    """Map values to 0-centered half-open bins with edges ``w*(k+1/2)``.

    A value exactly on a boundary belongs to the bin on its right, including
    negative boundaries. This is the deterministic convention for all folds.
    """
    width = _positive_width(width)
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Doppler values must be finite")
    scaled = values / width + 0.5
    if np.any(np.abs(scaled) > np.iinfo(np.int64).max - 1):
        raise ValueError("Doppler value exceeds supported bin index range")
    return np.floor(scaled).astype(np.int64)


def doppler_bin_cells(indices, width):
    """Return lower-inclusive and upper-exclusive edges for integer bin IDs."""
    width = _positive_width(width)
    indices = np.asarray(indices)
    if (not np.issubdtype(indices.dtype, np.number)
            or not np.isfinite(indices.astype(float)).all()
            or not np.equal(indices.astype(float), np.floor(indices.astype(float))).all()):
        raise ValueError("Doppler bin indices must be finite integers")
    integer_indices = indices.astype(np.int64)
    return ((integer_indices.astype(float) - 0.5) * width,
            (integer_indices.astype(float) + 0.5) * width)


def doppler_bin_log_mass(family, values, width, parameters):
    """Log probability of each observed fixed Doppler bin under a margin."""
    if family not in DOPPLER_FAMILIES:
        raise ValueError(f"unsupported fixed-bin Doppler family: {family}")
    bin_ids = doppler_bin_indices(values, width)
    lower, upper = doppler_bin_cells(bin_ids, width)
    result = gateg._family_log_interval(family, lower, upper, parameters)
    if not np.isfinite(result).all():
        raise ValueError("Doppler bin log mass is non-finite")
    return result


def _decode_doppler_parameters(family, theta):
    theta = np.asarray(theta, dtype=float)
    if family == "normal":
        return {"loc": float(theta[0]), "scale": float(np.exp(theta[1]))}
    if family == "student_t":
        return {"df": float(2.0 + np.exp(theta[2])),
                "loc": float(theta[0]), "scale": float(np.exp(theta[1]))}
    raise ValueError(f"unsupported fixed-bin Doppler family: {family}")


def fit_doppler_bins(frame, family, width):
    """Fit a Normal or Student-t margin by grouped fixed-bin likelihood.

    Fitting weights give equal weight to scenes, then selected windows, and
    split each window's weight across its MPC rows. They do not imply rowwise
    independent sampling or uncertainty.
    """
    width = _positive_width(width)
    if family not in DOPPLER_FAMILIES:
        raise ValueError(f"unsupported fixed-bin Doppler family: {family}")
    required = {"scene_id", "run_id", "window_id", "doppler_offset_hz"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Doppler training frame missing fields: {sorted(missing)}")
    if frame.empty:
        return {"variable": "doppler_offset_hz", "family": family, "status": "NO_DATA",
                "parameters": {}, "failure_reason": "empty training frame"}
    values = pd.to_numeric(frame.doppler_offset_hz, errors="coerce").to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError("Doppler training values must be finite")
    if len(values) < 20 or frame.scene_id.nunique() < 2:
        return {"variable": "doppler_offset_hz", "family": family,
                "status": "INSUFFICIENT_TRAINING_SUPPORT", "parameters": {},
                "failure_reason": "requires at least 20 rows and 2 training scenes",
                "training_row_n": int(len(frame)),
                "training_scene_n": int(frame.scene_id.nunique())}
    weights = wp3.scene_window_weights(frame)
    mean = float(np.dot(weights, values))
    variance = float(np.dot(weights, (values - mean) ** 2))
    scale_start = max(float(np.sqrt(variance)), width / np.sqrt(12.0), 1e-6)
    if not np.isfinite(scale_start) or scale_start <= 0.0:
        return {"variable": "doppler_offset_hz", "family": family,
                "status": "CONSTANT_DATA", "parameters": {},
                "failure_reason": "zero or non-finite weighted variance"}

    lower, upper = doppler_bin_cells(doppler_bin_indices(values, width), width)
    loc_bound = max(float(np.max(np.abs(values))) + 4.0 * scale_start, 100.0 * width)
    scale_floor = max(width * 1e-4, 1e-8)
    scale_ceiling = max(float(np.ptp(values)) + 20.0 * scale_start, 100.0 * width)
    bounds = [(-loc_bound, loc_bound), (np.log(scale_floor), np.log(scale_ceiling))]
    starts = [np.array([mean, np.log(scale_start)], dtype=float)]
    if family == "student_t":
        bounds.append((np.log(0.05), np.log(998.0)))
        starts = [np.array([mean, np.log(scale_start), np.log(df - 2.0)], dtype=float)
                  for df in (4.0, 8.0, 20.0)]

    def objective(theta):
        parameters = _decode_doppler_parameters(family, theta)
        log_mass = gateg._family_log_interval(family, lower, upper, parameters)
        if not np.isfinite(log_mass).all():
            return np.inf
        return -float(np.dot(weights, log_mass))

    candidates = [optimize.minimize(objective, start, method="L-BFGS-B", bounds=bounds,
                                    options={"maxiter": 700, "ftol": 1e-11, "gtol": 1e-7})
                  for start in starts]
    result = min(candidates, key=lambda candidate: float(candidate.fun))
    parameters = _decode_doppler_parameters(family, result.x)
    boundary = [index for index, (value, (lo, hi)) in enumerate(zip(result.x, bounds))
                if abs(value - lo) < 1e-5 or abs(value - hi) < 1e-5]
    status = "PASS" if result.success and np.isfinite(result.fun) and not boundary else (
        "BOUNDARY_PARAMETER" if boundary else "OPTIMIZER_FAILED")
    return {
        "variable": "doppler_offset_hz", "family": family, "status": status,
        "parameters": parameters,
        "failure_reason": "" if status == "PASS" else str(result.message),
        "optimizer_message": str(result.message),
        "weighted_mean_log_bin_mass": -float(result.fun) if np.isfinite(result.fun) else None,
        "boundary_parameters": boundary, "bin_width_hz": width,
        "bin_origin_hz": 0.0,
        "bin_convention": "HALF_OPEN_EDGES_W_TIMES_K_PLUS_HALF; TIES_TO_UPPER_BIN",
        "training_scene_ids": sorted(frame.scene_id.astype(str).unique().tolist()),
        "training_scene_n": int(frame.scene_id.nunique()),
        "training_mpc_n": int(len(frame)),
        "training_window_n": int(frame[list(wp6.WINDOW_KEY)].drop_duplicates().shape[0]),
        "weighting": "EQUAL_SCENE_EQUAL_WINDOW_SPLIT_OVER_MPC_ROWS",
        "observation_target": "FIXED_BINNED_STAGE2_DOPPLER_CONDITIONAL_ON_STAGE2_SELECTION",
    }


_LEGENDRE_CACHE = {}


def _legendre_rule(order):
    order = int(order)
    if order < 8 or order > 128:
        raise ValueError("quadrature order must be between 8 and 128")
    if order not in _LEGENDRE_CACHE:
        nodes, weights = np.polynomial.legendre.leggauss(order)
        _LEGENDRE_CACHE[order] = ((nodes + 1.0) / 2.0, weights / 2.0)
    return _LEGENDRE_CACHE[order]


def _normal_quantile_from_log_tails(log_cdf, log_sf):
    log_cdf, log_sf = np.broadcast_arrays(np.asarray(log_cdf, dtype=float),
                                           np.asarray(log_sf, dtype=float))
    result = np.empty_like(log_cdf)
    lower = log_cdf <= np.log(0.5)
    if np.any(lower):
        result[lower] = special.ndtri_exp(log_cdf[lower])
    if np.any(~lower):
        result[~lower] = -special.ndtri_exp(log_sf[~lower])
    return result


def _delay_latent_intervals(values, fit):
    lower, upper = gateg.delay_grid_cells(np.asarray(values, dtype=float))
    distribution = gateg._family_distribution(fit["family"], fit["parameters"])
    log_normalizer = float(distribution.logsf(gateg.MIN_DELAY_CHIPS))
    if not np.isfinite(log_normalizer):
        raise ValueError("delay truncation probability is non-finite")
    def log_tails(points):
        log_sf = distribution.logsf(points) - log_normalizer
        log_sf = np.minimum(log_sf, 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            log_cdf = np.log(-np.expm1(log_sf))
        return log_cdf, log_sf
    lower_cdf, lower_sf = log_tails(lower)
    upper_cdf, upper_sf = log_tails(upper)
    z_lower = _normal_quantile_from_log_tails(lower_cdf, lower_sf)
    z_upper = _normal_quantile_from_log_tails(upper_cdf, upper_sf)
    if np.any(z_upper <= z_lower):
        raise ValueError("delay cell maps to an empty latent-normal interval")
    return z_lower, z_upper


def _doppler_latent_intervals(values, fit, width):
    bin_ids = doppler_bin_indices(values, width)
    lower, upper = doppler_bin_cells(bin_ids, width)
    distribution = gateg._family_distribution(fit["family"], fit["parameters"])
    lower_cdf, upper_cdf = distribution.logcdf(lower), distribution.logcdf(upper)
    lower_sf, upper_sf = distribution.logsf(lower), distribution.logsf(upper)
    z_lower = _normal_quantile_from_log_tails(lower_cdf, lower_sf)
    z_upper = _normal_quantile_from_log_tails(upper_cdf, upper_sf)
    if np.any(z_upper <= z_lower):
        raise ValueError("Doppler bin maps to an empty latent-normal interval")
    return z_lower, z_upper


def normal_rectangle_log_probability(lower, upper, mean, covariance, quadrature_order=32):
    """Log mass of bivariate Normal rectangles, vectorized over observations.

    Integrates the first conditional marginal on its probability scale using
    deterministic Gauss-Legendre quadrature, then evaluates the conditional
    second-coordinate interval in log space. This remains stable for infinite
    outer bounds and tail intervals without relying on stochastic CDF calls.
    """
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    mean = np.asarray(mean, dtype=float)
    covariance = np.asarray(covariance, dtype=float)
    if lower.ndim == 1:
        lower = lower.reshape(1, -1)
    if upper.ndim == 1:
        upper = upper.reshape(1, -1)
    if mean.ndim == 1:
        mean = mean.reshape(1, -1)
    if (lower.ndim != 2 or upper.shape != lower.shape or mean.shape != lower.shape
            or lower.shape[1] != 2 or np.isnan(lower).any() or np.isnan(upper).any()
            or np.isnan(mean).any() or np.any(upper <= lower)):
        raise ValueError("rectangle inputs must be matching n-by-2 arrays with ordered bounds")
    if (covariance.shape != (2, 2) or not np.isfinite(covariance).all()
            or not np.allclose(covariance, covariance.T, rtol=0, atol=1e-12)):
        raise ValueError("rectangle covariance must be finite, symmetric, and 2-by-2")
    try:
        np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError as exc:
        raise ValueError("rectangle covariance must be positive definite") from exc
    eigenvalues = np.linalg.eigvalsh(covariance)
    if eigenvalues[0] <= 1e-12 * max(1.0, float(eigenvalues[-1])):
        raise ValueError("rectangle covariance is ill-conditioned")

    nodes, weights = _legendre_rule(quadrature_order)
    variance_first = float(covariance[0, 0])
    sd_first = np.sqrt(variance_first)
    conditional_slope = float(covariance[1, 0] / variance_first)
    conditional_variance = float(covariance[1, 1] - covariance[1, 0] ** 2 / variance_first)
    if not np.isfinite(conditional_variance) or conditional_variance <= 0.0:
        raise ValueError("conditional rectangle variance must be positive")
    conditional_sd = np.sqrt(conditional_variance)

    a = (lower[:, 0] - mean[:, 0]) / sd_first
    b = (upper[:, 0] - mean[:, 0]) / sd_first
    log_first_mass = gateg._normal_log_interval(a, b)
    if not np.isfinite(log_first_mass).all():
        raise ValueError("first-coordinate rectangle mass is not finite")
    t = nodes[None, :]
    log_p = log_first_mass[:, None]
    standardized_x = np.empty((len(a), len(nodes)), dtype=float)
    lower_tail = b <= 0.0
    upper_tail = a >= 0.0
    middle = ~(lower_tail | upper_tail)
    if np.any(lower_tail):
        log_u_start = special.log_ndtr(a[lower_tail])[:, None]
        log_u = np.logaddexp(log_u_start, np.log(t) + log_p[lower_tail])
        standardized_x[lower_tail] = special.ndtri_exp(log_u)
    if np.any(upper_tail):
        log_s_end = special.log_ndtr(-b[upper_tail])[:, None]
        log_s = np.logaddexp(log_s_end, np.log1p(-t) + log_p[upper_tail])
        standardized_x[upper_tail] = -special.ndtri_exp(log_s)
    if np.any(middle):
        mass = np.exp(log_first_mass[middle])[:, None]
        probability = (special.ndtr(a[middle])[:, None] + t * mass)
        standardized_x[middle] = special.ndtri(np.clip(probability, np.finfo(float).tiny,
                                                         1.0 - np.finfo(float).eps))

    x = mean[:, 0, None] + sd_first * standardized_x
    conditional_mean_second = (mean[:, 1, None]
                               + conditional_slope * (x - mean[:, 0, None]))
    log_second_mass = gateg._normal_log_interval(
        lower[:, 1, None], upper[:, 1, None], loc=conditional_mean_second,
        scale=conditional_sd)
    log_average_second_mass = special.logsumexp(np.log(weights)[None, :] + log_second_mass, axis=1)
    result = log_first_mass + log_average_second_mass
    if not np.isfinite(result).all():
        raise ValueError("rectangle log probability is non-finite")
    return result


def _validate_mark_fits(fitted_marginals):
    required = ("excess_delay_chips", "doppler_offset_hz", "relative_power_db")
    for variable in required:
        fit = fitted_marginals.get(variable)
        if not fit or fit.get("status") != "PASS" or not fit.get("parameters"):
            raise ValueError(f"marginal fit is unavailable for {variable}")
    if fitted_marginals["doppler_offset_hz"].get("family") not in DOPPLER_FAMILIES:
        raise ValueError("fixed-bin Doppler fit must be Normal or Student-t")


def _score_frame_check(frame):
    required = {"run_id", "window_id", "path_id", "scene_id", "excess_delay_chips",
                "doppler_offset_hz", "relative_power_db"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"fixed-bin score frame missing fields: {sorted(missing)}")
    if frame.empty:
        raise ValueError("cannot score an empty MPC frame")
    if frame.duplicated(list(wp6.MPC_KEY)).any():
        raise ValueError("fixed-bin score frame has duplicate MPC identity")
    for variable in ("excess_delay_chips", "doppler_offset_hz", "relative_power_db"):
        if not np.isfinite(pd.to_numeric(frame[variable], errors="coerce").to_numpy(float)).all():
            raise ValueError(f"fixed-bin score frame has non-finite {variable}")


def fixed_bin_product_log_score(fitted_marginals, frame, width):
    """Independent mixed measure: delay mass × Doppler-bin mass × power density."""
    _validate_mark_fits(fitted_marginals)
    _score_frame_check(frame)
    width = _positive_width(width)
    delay_fit = fitted_marginals["excess_delay_chips"]
    doppler_fit = fitted_marginals["doppler_offset_hz"]
    power_fit = fitted_marginals["relative_power_db"]
    delay = gateg.delay_grid_log_mass(delay_fit["family"],
                                     frame.excess_delay_chips.to_numpy(float),
                                     delay_fit["parameters"])
    doppler = doppler_bin_log_mass(doppler_fit["family"],
                                   frame.doppler_offset_hz.to_numpy(float), width,
                                   doppler_fit["parameters"])
    power = wp3._distribution_logpdf(power_fit["family"],
                                    frame.relative_power_db.to_numpy(float),
                                    power_fit["parameters"])
    result = delay + doppler + power
    if not np.isfinite(result).all():
        raise ValueError("fixed-bin product score contains non-finite values")
    return result


def fixed_bin_copula_log_score(fitted_marginals, correlation, frame, width,
                               quadrature_order=32):
    """Joint mixed score for delay cell × Doppler bin × continuous power.

    The bivariate latent-normal rectangle is evaluated conditional on the
    continuous power PIT; the power marginal contributes its density.
    """
    _validate_mark_fits(fitted_marginals)
    _score_frame_check(frame)
    width = _positive_width(width)
    corr = gateg._validate_correlation(correlation, dimension=3)
    delay_fit = fitted_marginals["excess_delay_chips"]
    doppler_fit = fitted_marginals["doppler_offset_hz"]
    power_fit = fitted_marginals["relative_power_db"]
    delay_lower, delay_upper = _delay_latent_intervals(
        frame.excess_delay_chips.to_numpy(float), delay_fit)
    doppler_lower, doppler_upper = _doppler_latent_intervals(
        frame.doppler_offset_hz.to_numpy(float), doppler_fit, width)
    power_cdf = wp6._distribution_cdf(power_fit["family"],
                                      frame.relative_power_db.to_numpy(float),
                                      power_fit["parameters"])
    power_z = special.ndtri(np.clip(power_cdf, 1e-12, 1.0 - 1e-12))
    cross = corr[:2, 2]
    conditional_mean = power_z[:, None] * cross[None, :]
    conditional_covariance = corr[:2, :2] - np.outer(cross, cross)
    rectangles = normal_rectangle_log_probability(
        np.column_stack((delay_lower, doppler_lower)),
        np.column_stack((delay_upper, doppler_upper)),
        conditional_mean, conditional_covariance, quadrature_order=quadrature_order)
    power_logpdf = wp3._distribution_logpdf(power_fit["family"],
                                             frame.relative_power_db.to_numpy(float),
                                             power_fit["parameters"])
    result = power_logpdf + rectangles
    if not np.isfinite(result).all():
        raise ValueError("fixed-bin Copula score contains non-finite values")
    return result


def _interval_midpoint_correlation(frame, fitted_marginals, width):
    delay_lower, delay_upper = _delay_latent_intervals(
        frame.excess_delay_chips.to_numpy(float), fitted_marginals["excess_delay_chips"])
    doppler_lower, doppler_upper = _doppler_latent_intervals(
        frame.doppler_offset_hz.to_numpy(float), fitted_marginals["doppler_offset_hz"], width)
    uniforms = [
        (special.ndtr(delay_lower) + special.ndtr(delay_upper)) / 2.0,
        (special.ndtr(doppler_lower) + special.ndtr(doppler_upper)) / 2.0,
    ]
    power_fit = fitted_marginals["relative_power_db"]
    power_u = wp6._distribution_cdf(power_fit["family"],
                                    frame.relative_power_db.to_numpy(float),
                                    power_fit["parameters"])
    uniforms.append(np.clip(power_u, 1e-10, 1.0 - 1e-10))
    z = special.ndtri(np.clip(np.column_stack(uniforms), 1e-10, 1.0 - 1e-10))
    weights = wp3.scene_window_weights(frame)
    mean = np.sum(z * weights[:, None], axis=0)
    centered = z - mean
    covariance = (centered * weights[:, None]).T @ centered
    scale = np.sqrt(np.maximum(np.diag(covariance), 1e-12))
    correlation = covariance / np.outer(scale, scale)
    correlation = 0.5 * (correlation + correlation.T)
    np.fill_diagonal(correlation, 1.0)
    eigenvalues, eigenvectors = np.linalg.eigh(correlation)
    if eigenvalues.min() <= 1e-6:
        correlation = (eigenvectors * np.maximum(eigenvalues, 1e-6)) @ eigenvectors.T
        scale = np.sqrt(np.diag(correlation))
        correlation /= np.outer(scale, scale)
        np.fill_diagonal(correlation, 1.0)
    return gateg._validate_correlation(correlation, dimension=3)


def fit_fixed_bin_copula(training_frame, fitted_marginals, width,
                         quadrature_order=24, maxiter=180):
    """Fit the 3-D Gaussian Copula by training-only mixed composite likelihood."""
    width = _positive_width(width)
    _validate_mark_fits(fitted_marginals)
    if training_frame.scene_id.nunique() < 2:
        return None, {"status": "INSUFFICIENT_TRAINING_SCENES",
                      "training_scene_n": int(training_frame.scene_id.nunique())}
    _score_frame_check(training_frame)
    initial_moment = _interval_midpoint_correlation(training_frame, fitted_marginals, width)
    weights = wp3.scene_window_weights(training_frame)

    def objective(theta):
        correlation = gateg._decode_partial_correlations(theta)
        try:
            scores = fixed_bin_copula_log_score(fitted_marginals, correlation,
                                                training_frame, width,
                                                quadrature_order=quadrature_order)
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            return np.inf
        return -float(np.dot(weights, scores))

    starts = [("INTERVAL_MIDPOINT", initial_moment), ("IDENTITY", np.eye(3))]
    candidates = []
    for start_name, start_correlation in starts:
        theta = np.arctanh(np.clip([start_correlation[0, 1], start_correlation[0, 2],
                                    (start_correlation[1, 2]
                                     - start_correlation[0, 1] * start_correlation[0, 2])
                                    / np.sqrt(max(1e-10, (1.0 - start_correlation[0, 1] ** 2)
                                                  * (1.0 - start_correlation[0, 2] ** 2)))],
                                   -0.95, 0.95))
        result = optimize.minimize(objective, theta, method="L-BFGS-B",
                                   bounds=[(-3.5, 3.5)] * 3,
                                   options={"maxiter": int(maxiter), "ftol": 1e-8, "gtol": 1e-5})
        candidates.append((result, start_name))
    result, start_name = min(candidates, key=lambda item: float(item[0].fun))
    correlation = gateg._decode_partial_correlations(result.x)
    boundary = bool(np.any(np.abs(result.x) >= 3.499))
    status = "PASS" if result.success and np.isfinite(result.fun) and not boundary else (
        "BOUNDARY_CORRELATION" if boundary else "OPTIMIZER_FAILED")
    diagnostics = {
        "status": status, "optimizer_message": str(result.message),
        "start_selected": start_name,
        "objective_weighted_mean_log_score": -float(result.fun) if np.isfinite(result.fun) else None,
        "parameter_vector": result.x.tolist(), "correlation": correlation.tolist(),
        "boundary_parameter": boundary,
        "training_scene_ids": sorted(training_frame.scene_id.astype(str).unique().tolist()),
        "training_scene_n": int(training_frame.scene_id.nunique()),
        "training_window_n": int(training_frame[list(wp6.WINDOW_KEY)].drop_duplicates().shape[0]),
        "training_mpc_n": int(len(training_frame)), "bin_width_hz": width,
        "bin_origin_hz": 0.0,
        "fitting_measure": "DELAY_CELL_X_DOPPLER_BIN_X_CONTINUOUS_POWER_MIXED_COMPOSITE_LIKELIHOOD",
        "weighting": "EQUAL_SCENE_EQUAL_WINDOW_SPLIT_OVER_MPC_ROWS",
    }
    return (correlation if status == "PASS" else None), diagnostics


def _per_window_mean(frame, scores):
    rows = pd.DataFrame({"run_id": frame.run_id.astype(str).to_numpy(),
                         "window_id": frame.window_id.astype(str).to_numpy(),
                         "score": np.asarray(scores, dtype=float)})
    return rows.groupby(["run_id", "window_id"], sort=False).score.mean()


def _select_mark_family_nested(frame, training_scenes, variable):
    scenes = tuple(sorted(str(scene) for scene in training_scenes))
    if len(scenes) < 3:
        raise ValueError("nested marginal selection requires at least three training scenes")
    if variable not in ("excess_delay_chips", "relative_power_db"):
        raise ValueError("fixed-bin mark selector is limited to delay and power")
    base = frame.loc[frame.scene_id.astype(str).isin(scenes)].copy()
    candidates = gateg.MARK_FAMILIES[variable]
    records = []
    summaries = []
    for family in candidates:
        scene_scores = []
        for held_scene in scenes:
            train = base.loc[base.scene_id.astype(str).ne(held_scene)].copy()
            test = base.loc[base.scene_id.astype(str).eq(held_scene)].copy()
            status, score, reason = "PASS", np.nan, ""
            try:
                if train.empty or test.empty:
                    raise ValueError("inner training or held-out scene is empty")
                fit = gateg._fit_margin(train, variable, family)
                if fit.get("status") != "PASS":
                    raise ValueError(f"inner fit status={fit.get('status')}: {fit.get('failure_reason', '')}")
                row_scores = gateg._score_margin(fit, test, variable)
                score = float(_per_window_mean(test, row_scores).mean())
                if not np.isfinite(score):
                    raise ValueError("inner held-out scene score is non-finite")
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                status, reason = "FIT_OR_SCORE_FAILED", str(exc)
            records.append({
                "variable": variable, "family": family,
                "inner_held_out_scene_id": held_scene,
                "inner_training_scene_ids": json.dumps([scene for scene in scenes if scene != held_scene]),
                "training_mpc_n": int(len(train)), "heldout_mpc_n": int(len(test)),
                "inner_scene_window_mean_log_score": score,
                "status": status, "failure_reason": reason,
            })
            if status == "PASS":
                scene_scores.append(score)
        candidate_score = float(np.mean(scene_scores)) if len(scene_scores) == len(scenes) else np.nan
        summaries.append((family, candidate_score))
    selectable = [(family, score) for family, score in summaries if np.isfinite(score)]
    selected = max(selectable, key=lambda item: item[1])[0] if selectable else None
    return selected, pd.DataFrame(records)


def select_doppler_family_nested(frame, training_scenes, width):
    """Choose a binned Doppler margin using only inner held-out training scenes."""
    width = _positive_width(width)
    scenes = tuple(sorted(str(scene) for scene in training_scenes))
    if len(scenes) < 3:
        raise ValueError("nested Doppler selection requires at least three training scenes")
    base = frame.loc[frame.scene_id.astype(str).isin(scenes)].copy()
    records, summaries = [], []
    for family in DOPPLER_FAMILIES:
        scene_scores = []
        for held_scene in scenes:
            train = base.loc[base.scene_id.astype(str).ne(held_scene)].copy()
            test = base.loc[base.scene_id.astype(str).eq(held_scene)].copy()
            status, score, reason = "PASS", np.nan, ""
            try:
                if train.empty or test.empty:
                    raise ValueError("inner training or held-out scene is empty")
                fit = fit_doppler_bins(train, family, width)
                if fit.get("status") != "PASS":
                    raise ValueError(f"inner fit status={fit.get('status')}: {fit.get('failure_reason', '')}")
                row_scores = doppler_bin_log_mass(family, test.doppler_offset_hz.to_numpy(float),
                                                  width, fit["parameters"])
                score = float(_per_window_mean(test, row_scores).mean())
                if not np.isfinite(score):
                    raise ValueError("inner held-out scene score is non-finite")
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                status, reason = "FIT_OR_SCORE_FAILED", str(exc)
            records.append({
                "variable": "doppler_offset_hz", "family": family,
                "width_hz": width, "inner_held_out_scene_id": held_scene,
                "inner_training_scene_ids": json.dumps([scene for scene in scenes if scene != held_scene]),
                "training_mpc_n": int(len(train)), "heldout_mpc_n": int(len(test)),
                "inner_scene_window_mean_log_score": score,
                "status": status, "failure_reason": reason,
            })
            if status == "PASS":
                scene_scores.append(score)
        candidate_score = float(np.mean(scene_scores)) if len(scene_scores) == len(scenes) else np.nan
        summaries.append((family, candidate_score))
    selectable = [(family, score) for family, score in summaries if np.isfinite(score)]
    selected = max(selectable, key=lambda item: item[1])[0] if selectable else None
    return selected, pd.DataFrame(records)


def paired_scene_score_comparisons(path_scores):
    """Aggregate path composites to windows, then compare models on paired windows."""
    required = {"outer_held_out_scene_id", "scene_id", "run_id", "window_id", "width_hz",
                "M0_independent", "C0_copula"}
    missing = required.difference(path_scores.columns)
    if missing:
        raise ValueError(f"path score table missing fields: {sorted(missing)}")
    window_rows, comparison_rows = [], []
    group_keys = ["width_hz", "outer_held_out_scene_id", "scene_id", "run_id", "window_id"]
    for key, group in path_scores.groupby(group_keys, sort=True, dropna=False):
        row = dict(zip(group_keys, key))
        for model in ("M0_independent", "C0_copula"):
            values = pd.to_numeric(group[model], errors="coerce").to_numpy(float)
            row[model] = float(values.mean()) if len(values) and np.isfinite(values).all() else np.nan
        row["mpc_row_n"] = int(len(group))
        window_rows.append(row)
    windows = pd.DataFrame(window_rows)
    scene_keys = ["width_hz", "outer_held_out_scene_id", "scene_id"]
    for key, group in windows.groupby(scene_keys, sort=True, dropna=False):
        paired = np.isfinite(group.M0_independent.to_numpy(float)) & np.isfinite(
            group.C0_copula.to_numpy(float))
        delta = group.loc[paired, "C0_copula"].to_numpy(float) - group.loc[
            paired, "M0_independent"].to_numpy(float)
        comparison_rows.append({
            **dict(zip(scene_keys, key)), "heldout_window_n": int(len(group)),
            "paired_window_n": int(paired.sum()), "unpaired_window_n": int((~paired).sum()),
            "M0_mean_per_paired_window": float(group.loc[paired, "M0_independent"].mean())
            if paired.any() else np.nan,
            "C0_mean_per_paired_window": float(group.loc[paired, "C0_copula"].mean())
            if paired.any() else np.nan,
            "C0_minus_M0_nats_per_mpc": float(delta.mean()) if len(delta) else np.nan,
            "C0_minus_M0_median_window_delta": float(np.median(delta)) if len(delta) else np.nan,
        })
    return windows, pd.DataFrame(comparison_rows)


def evaluate_fixed_bin_loso(mpcs, widths=DOPPLER_WIDTHS_HZ, expected_scenes=13,
                            progress_callback=None, copula_quadrature_order=24):
    """Nested 13-scene LOSO for fixed-bin independent and Copula mark models."""
    frame = gateg.prepare_ranked_marks(mpcs)
    scenes = tuple(sorted(frame.scene_id.astype(str).unique()))
    if len(scenes) != int(expected_scenes):
        raise ValueError(f"expected {expected_scenes} complete scenes, got {len(scenes)}")
    widths = tuple(_positive_width(width) for width in widths)
    if not widths or len(set(widths)) != len(widths):
        raise ValueError("analysis widths must be nonempty and unique")
    fold_rows, selection_rows, parameter_rows, copula_rows, path_rows = [], [], [], [], []
    for fold_index, held_scene in enumerate(scenes, start=1):
        training_scenes = tuple(scene for scene in scenes if scene != held_scene)
        train = frame.loc[frame.scene_id.astype(str).isin(training_scenes)].copy()
        test = frame.loc[frame.scene_id.astype(str).eq(held_scene)].copy()

        selected_marginals = {}
        for variable in ("excess_delay_chips", "relative_power_db"):
            family, selection = _select_mark_family_nested(train, training_scenes, variable)
            selection["outer_held_out_scene_id"] = held_scene
            selection["width_hz"] = "ALL"
            selection_rows.append(selection)
            selected_marginals[variable] = family

        training_fits = {}
        for variable in ("excess_delay_chips", "relative_power_db"):
            family = selected_marginals[variable]
            training_fits[variable] = (gateg._fit_margin(train, variable, family) if family is not None
                                       else {"variable": variable, "family": None,
                                             "status": "NO_SELECTABLE_FAMILY", "parameters": {},
                                             "failure_reason": "all nested candidates failed"})

        fold_row = {
            "outer_held_out_scene_id": held_scene,
            "outer_training_scene_ids": json.dumps(list(training_scenes)),
            "training_scene_n": int(train.scene_id.nunique()),
            "training_window_n": int(train[list(wp6.WINDOW_KEY)].drop_duplicates().shape[0]),
            "training_mpc_n": int(len(train)),
            "heldout_window_n": int(test[list(wp6.WINDOW_KEY)].drop_duplicates().shape[0]),
            "heldout_mpc_n": int(len(test)),
            "selected_delay_family": selected_marginals["excess_delay_chips"],
            "selected_power_family": selected_marginals["relative_power_db"],
        }

        for width in widths:
            doppler_family, doppler_selection = select_doppler_family_nested(
                train, training_scenes, width)
            doppler_selection["outer_held_out_scene_id"] = held_scene
            doppler_selection["width_hz"] = width
            selection_rows.append(doppler_selection)
            doppler_fit = (fit_doppler_bins(train, doppler_family, width)
                           if doppler_family is not None else {
                               "variable": "doppler_offset_hz", "family": None,
                               "status": "NO_SELECTABLE_FAMILY", "parameters": {},
                               "failure_reason": "all nested candidates failed"})
            fits = {**training_fits, "doppler_offset_hz": doppler_fit}
            for variable, fit in fits.items():
                parameter_rows.append({
                    "outer_held_out_scene_id": held_scene, "width_hz": width,
                    "variable": variable, "family": fit.get("family"),
                    "status": fit.get("status"), "failure_reason": fit.get("failure_reason", ""),
                    "training_scene_ids": json.dumps(fit.get("training_scene_ids", list(training_scenes))),
                    "training_scene_n": fit.get("training_scene_n", len(training_scenes)),
                    "training_window_n": fit.get("training_window_n"),
                    "training_mpc_n": fit.get("training_mpc_n"),
                    "parameters_json": json.dumps(fit.get("parameters", {}), sort_keys=True),
                })
            base_score = np.full(len(test), np.nan)
            if all(fits[variable].get("status") == "PASS" for variable in (
                    "excess_delay_chips", "doppler_offset_hz", "relative_power_db")):
                try:
                    base_score = fixed_bin_product_log_score(fits, test, width)
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    pass
            try:
                copula, copula_diagnostics = fit_fixed_bin_copula(
                    train, fits, width, quadrature_order=copula_quadrature_order)
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                missing_margins = [variable for variable in (
                    "excess_delay_chips", "doppler_offset_hz", "relative_power_db")
                    if fits[variable].get("status") != "PASS"]
                copula_diagnostics = {
                    "status": "MARGINAL_FIT_UNAVAILABLE" if missing_margins else "FIT_FAILED",
                    "failure_reason": str(exc),
                    "unavailable_marginals": json.dumps(missing_margins),
                    "training_scene_ids": list(training_scenes),
                    "training_scene_n": int(len(training_scenes)),
                    "training_window_n": int(train[list(wp6.WINDOW_KEY)].drop_duplicates().shape[0]),
                    "training_mpc_n": int(len(train)), "bin_width_hz": width,
                    "bin_origin_hz": 0.0,
                    "fitting_measure": "DELAY_CELL_X_DOPPLER_BIN_X_CONTINUOUS_POWER_MIXED_COMPOSITE_LIKELIHOOD",
                    "weighting": "EQUAL_SCENE_EQUAL_WINDOW_SPLIT_OVER_MPC_ROWS",
                }
                copula = None
            copula_score = np.full(len(test), np.nan)
            if copula is not None:
                try:
                    copula_score = fixed_bin_copula_log_score(
                        fits, copula, test, width, quadrature_order=copula_quadrature_order)
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    copula_diagnostics["status"] = "HELDOUT_SCORE_FAILED"
                    copula_diagnostics["heldout_failure_reason"] = "non-finite or invalid held-out mixed score"
            copula_rows.append({
                "outer_held_out_scene_id": held_scene, "width_hz": width,
                **{key: value for key, value in copula_diagnostics.items()
                   if key not in {"correlation", "training_scene_ids", "parameter_vector"}},
                "training_scene_ids": json.dumps(copula_diagnostics.get(
                    "training_scene_ids", list(training_scenes))),
                "correlation_json": json.dumps(copula.tolist()) if copula is not None else "",
            })
            score = test[[*wp6.MPC_KEY, "scene_id", "mpc_rank", "n_mpc"]].copy().reset_index(drop=True)
            score["outer_held_out_scene_id"] = held_scene
            score["width_hz"] = width
            score["M0_independent"] = base_score
            score["C0_copula"] = copula_score
            path_rows.append(score)
            fold_row[f"doppler_family_{width:g}hz"] = doppler_family
            fold_row[f"doppler_status_{width:g}hz"] = doppler_fit.get("status")
            fold_row[f"copula_status_{width:g}hz"] = copula_diagnostics.get("status")

        fold_rows.append(fold_row)
        if progress_callback is not None:
            progress_callback(fold_index, len(scenes), held_scene)

    path_scores = pd.concat(path_rows, ignore_index=True)
    window_scores, scene_scores = paired_scene_score_comparisons(path_scores)
    return {
        "folds": pd.DataFrame(fold_rows), "family_selection": pd.concat(selection_rows, ignore_index=True),
        "parameters": pd.DataFrame(parameter_rows), "copula_diagnostics": pd.DataFrame(copula_rows),
        "path_scores": path_scores, "window_scores": window_scores,
        "scene_scores": scene_scores,
    }
