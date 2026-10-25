"""Scene-level WP2 robustness diagnostics on existing Stage2 V0 CSV outputs.

This module does not load signals, MAT/HDF5/CIR payloads, or production code.
MPC and window records remain repeated observations; only complete scenes are
the fold and summary units.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import optimize, stats
from scipy.special import gammaln, logsumexp

import mainline_stage2_v0 as v0


PARAMETER_NAMES = {
    "gamma": ("shape", "loc", "scale"),
    "lognormal": ("shape", "loc", "scale"),
    "weibull": ("shape", "loc", "scale"),
    "normal": ("loc", "scale"),
    "laplace": ("loc", "scale"),
    "student_t": ("df", "loc", "scale"),
}
DEFAULT_SCOPES = ("GLOBAL", "ENV:Urban")
MIN_EXPECTED_TAIL_N = 10.0


def _empty(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _parameters(value: Any) -> list[float]:
    if _empty(value) or value == "":
        return []
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, (list, tuple)):
        raise ValueError("fold fit_parameters must be a JSON array")
    result = [float(v) for v in parsed]
    if not np.isfinite(result).all():
        raise ValueError("fold fit_parameters must be finite")
    return result


def _score(value: Any) -> float | None:
    if _empty(value) or value == "":
        return None
    result = float(value)
    return None if math.isnan(result) else result


def _validate_folds(fold_scores: pd.DataFrame, scopes: Iterable[str]) -> pd.DataFrame:
    required = {
        "scope", "held_out_scene_id", "variable", "family", "fit_status",
        "fit_parameters", "mean_loglik", "test_n", "finite_test_n",
    }
    missing = required - set(fold_scores.columns)
    if missing:
        raise ValueError("fold score table missing columns: " + ",".join(sorted(missing)))
    selected = fold_scores[fold_scores.scope.isin(tuple(scopes))].copy()
    if selected.empty:
        raise ValueError("fold score table has no requested scopes")
    key = ["scope", "held_out_scene_id", "variable", "family"]
    if selected.duplicated(key).any():
        raise ValueError("duplicate scope/scene/variable/family fold")
    unknown = set(selected.family.astype(str)) - set(PARAMETER_NAMES)
    if unknown:
        raise ValueError("unknown candidate family: " + ",".join(sorted(unknown)))
    return selected


def _scope_rows(mpc: pd.DataFrame, scope: str) -> pd.DataFrame:
    if "scene_id" not in mpc:
        raise ValueError("MPC rows require scene_id")
    if scope == "GLOBAL":
        return mpc
    if scope.startswith("ENV:"):
        if "environment_class" not in mpc:
            raise ValueError("environment fold requires environment_class")
        return mpc[mpc.environment_class.astype(str) == scope.removeprefix("ENV:")]
    raise ValueError("unsupported fold scope: " + scope)


def marginal_stability_rows(
    mpc: pd.DataFrame,
    fold_scores: pd.DataFrame,
    scopes: Iterable[str] = DEFAULT_SCOPES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Summarize saved LOSO fit parameters and per-scene family ranks.

    The fold estimates overlap and are a sensitivity display, not independent
    estimates or confidence intervals. Ranks compare only families for the
    same scope, held-out scene, and variable.
    """
    scopes = tuple(scopes)
    selected = _validate_folds(fold_scores, scopes)
    rows: list[dict[str, Any]] = []
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for (scope, held, variable), group in selected.groupby(
        ["scope", "held_out_scene_id", "variable"], sort=True
    ):
        scope_data = _scope_rows(mpc, str(scope))
        if str(variable) not in scope_data:
            raise ValueError("fold variable missing from MPC input: " + str(variable))
        if not (scope_data.scene_id.astype(str) == str(held)).any():
            raise ValueError(f"held-out scene absent from MPC input: {scope}/{held}")
        held_values = pd.to_numeric(scope_data.loc[
            scope_data.scene_id.astype(str) == str(held), str(variable)
        ], errors="coerce").to_numpy(dtype=float)
        value_n = int(len(held_values))
        finite_value_n = int(np.isfinite(held_values).sum())
        for _, record in group.iterrows():
            status = str(record.fit_status)
            params = _parameters(record.fit_parameters)
            if status == "PASS" and len(params) != len(PARAMETER_NAMES[str(record.family)]):
                raise ValueError("fit parameter count does not match candidate family")
            if int(float(record.test_n)) != value_n:
                raise ValueError(f"held-out row count mismatch for {scope}/{held}/{variable}")
            if int(float(record.finite_test_n)) != finite_value_n:
                raise ValueError(f"held-out finite count mismatch for {scope}/{held}/{variable}")
            score = _score(record.mean_loglik)
            item = dict(
                scope=str(scope), held_out_scene_id=str(held), variable=str(variable),
                family=str(record.family), fit_status=status, fit_parameters=params,
                mean_loglik=score, test_n=int(float(record.test_n)),
                finite_test_n=int(float(record.finite_test_n)),
                support_violation_n=(int(float(record.support_violation_n))
                                     if "support_violation_n" in record.index and not _empty(record.support_violation_n)
                                     else 0),
                heldout_rank=None,
            )
            rows.append(item)
            buckets[(str(scope), str(variable), str(record.family))].append(item)

        eligible = [r for r in rows if r["scope"] == str(scope)
                    and r["held_out_scene_id"] == str(held)
                    and r["variable"] == str(variable)
                    and r["fit_status"] == "PASS" and r["mean_loglik"] is not None
                    and np.isfinite(r["mean_loglik"]) and r["support_violation_n"] == 0]
        eligible.sort(key=lambda r: (-r["mean_loglik"], r["family"]))
        last_score: float | None = None
        current_rank = 0
        for position, item in enumerate(eligible, start=1):
            if last_score is None or item["mean_loglik"] != last_score:
                current_rank = position
                last_score = item["mean_loglik"]
            item["heldout_rank"] = current_rank

    summaries: list[dict[str, Any]] = []
    for (scope, variable, family), group in sorted(buckets.items()):
        ranks = [r["heldout_rank"] for r in group if r["heldout_rank"] is not None]
        summaries.append(dict(
            row_type="FAMILY_RANK", scope=scope, variable=variable, family=family,
            parameter_name="", fit_fold_n=sum(r["fit_status"] == "PASS" for r in group),
            failed_fold_n=sum(r["fit_status"] != "PASS" for r in group),
            rank_evaluated_fold_n=len(ranks),
            support_limited_fold_n=sum(r["support_violation_n"] > 0 or
                                       (r["mean_loglik"] is not None and not np.isfinite(r["mean_loglik"]))
                                       for r in group),
            rank1_fold_n=sum(rank == 1 for rank in ranks),
            rank1_scene_ids=[r["held_out_scene_id"] for r in group if r["heldout_rank"] == 1],
            rank_median=float(np.median(ranks)) if ranks else None,
            rank_min=min(ranks) if ranks else None, rank_max=max(ranks) if ranks else None,
            parameter_fold_n=None, parameter_min=None, parameter_q25=None,
            parameter_median=None, parameter_q75=None, parameter_max=None,
            parameter_range=None,
        ))
        for index, name in enumerate(PARAMETER_NAMES[family]):
            values = [r["fit_parameters"][index] for r in group if r["fit_status"] == "PASS"]
            if not values:
                continue
            q25, median, q75 = np.quantile(values, [0.25, 0.5, 0.75]).tolist()
            summaries.append(dict(
                row_type="PARAMETER_SENSITIVITY", scope=scope, variable=variable,
                family=family, parameter_name=name, fit_fold_n=None, failed_fold_n=None,
                rank_evaluated_fold_n=None, support_limited_fold_n=None, rank1_scene_ids=None,
                rank1_fold_n=None, rank_median=None, rank_min=None, rank_max=None,
                parameter_fold_n=len(values), parameter_min=float(min(values)),
                parameter_q25=float(q25), parameter_median=float(median),
                parameter_q75=float(q75), parameter_max=float(max(values)),
                parameter_range=float(max(values) - min(values)),
            ))
    return rows, summaries


def tail_calibration_rows(
    mpc: pd.DataFrame,
    fold_scores: pd.DataFrame,
    quantiles: Iterable[float] = (0.01, 0.05, 0.10, 0.90, 0.95, 0.99),
    scopes: Iterable[str] = DEFAULT_SCOPES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Measure held-out quantile calibration from saved training-fold fits."""
    quantiles = tuple(float(q) for q in quantiles)
    if not quantiles or any(not 0.0 < q < 1.0 for q in quantiles):
        raise ValueError("quantiles must be a non-empty sequence inside (0,1)")
    scopes = tuple(scopes)
    selected = _validate_folds(fold_scores, scopes)
    rows: list[dict[str, Any]] = []
    for _, record in selected.iterrows():
        scope, held, variable, family = map(str, (
            record.scope, record.held_out_scene_id, record.variable, record.family
        ))
        scoped = _scope_rows(mpc, scope)
        test = scoped[scoped.scene_id.astype(str) == held]
        if variable not in test:
            raise ValueError("fold variable missing from MPC input: " + variable)
        values = pd.to_numeric(test[variable], errors="coerce").to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(values) != int(float(record.test_n)):
            raise ValueError(f"held-out row count mismatch for {scope}/{held}/{variable}")
        if len(finite) != int(float(record.finite_test_n)):
            raise ValueError(f"held-out finite count mismatch for {scope}/{held}/{variable}")
        status = str(record.fit_status)
        params = _parameters(record.fit_parameters)
        support_violation_n = (int(float(record.support_violation_n))
                               if "support_violation_n" in record.index and not _empty(record.support_violation_n)
                               else 0)
        if status == "PASS" and len(params) != len(PARAMETER_NAMES[family]):
            raise ValueError("fit parameter count does not match candidate family")
        dist = v0.DISTRIBUTIONS[family]
        for q in quantiles:
            expected_tail_n = len(finite) * min(q, 1.0 - q)
            support_status = "SUPPORTED" if expected_tail_n >= MIN_EXPECTED_TAIL_N else "LOW_TAIL_SUPPORT"
            item = dict(
                scope=scope, held_out_scene_id=held, variable=variable, family=family,
                quantile=q, nominal_tail_fraction=min(q, 1.0 - q),
                test_n=len(values), finite_test_n=len(finite),
                expected_tail_observation_n=expected_tail_n,
                tail_support_status=support_status, fit_status=status,
                heldout_support_violation_n=support_violation_n,
                predicted_quantile=None, empirical_quantile=None,
                empirical_coverage=None, coverage_error=None, quantile_error=None,
            )
            if status == "PASS" and family in v0.POSITIVE and support_violation_n:
                item["fit_status"] = "HELDOUT_SUPPORT_VIOLATION"
            elif status == "PASS" and len(finite):
                predicted = float(dist.ppf(q, *params))
                if np.isfinite(predicted):
                    empirical_q = float(np.quantile(finite, q))
                    coverage = float(np.mean(finite <= predicted))
                    item.update(
                        predicted_quantile=predicted, empirical_quantile=empirical_q,
                        empirical_coverage=coverage, coverage_error=coverage - q,
                        quantile_error=empirical_q - predicted,
                    )
                else:
                    item["fit_status"] = "INVALID_PREDICTIVE_QUANTILE"
            rows.append(item)

    grouped: dict[tuple[str, str, str, float], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["scope"], row["variable"], row["family"], row["quantile"])].append(row)
    summary = []
    for (scope, variable, family, q), group in sorted(grouped.items()):
        valid = [r for r in group if r["coverage_error"] is not None]
        supported = [r for r in valid if r["tail_support_status"] == "SUPPORTED"]
        summary.append(dict(
            scope=scope, variable=variable, family=family, quantile=q,
            nominal_tail_fraction=min(q, 1.0 - q), fold_n=len(group),
            evaluated_fold_n=len(valid), supported_fold_n=len(supported),
            low_support_fold_n=sum(r["tail_support_status"] == "LOW_TAIL_SUPPORT" for r in group),
            failed_or_invalid_fold_n=len(group) - len(valid),
            macro_empirical_coverage=float(np.mean([r["empirical_coverage"] for r in valid])) if valid else None,
            macro_coverage_error=float(np.mean([r["coverage_error"] for r in valid])) if valid else None,
            macro_absolute_quantile_error=float(np.mean([abs(r["quantile_error"]) for r in valid])) if valid else None,
        ))
    return rows, summary


def _scene_balanced_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame.groupby("scene_id")["scene_id"].transform("size").to_numpy(dtype=float)
    if not len(counts) or np.any(counts <= 0):
        raise ValueError("scene-balanced fit requires non-empty scenes")
    return 1.0 / counts


def _weighted_normal(values: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    total = float(weights.sum())
    mean = float(np.sum(weights * values) / total)
    variance = float(np.sum(weights * (values - mean) ** 2) / total)
    scale = math.sqrt(variance)
    if not np.isfinite(mean) or not np.isfinite(scale) or scale <= 0:
        raise ValueError("weighted Normal fit has nonpositive or invalid scale")
    return mean, scale


def _paired_scene_bootstrap(values: np.ndarray, iterations: int, seed: int) -> tuple[float | None, float | None]:
    if iterations <= 0 or not len(values):
        return None, None
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(values), size=(iterations, len(values)))
    means = values[draws].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return float(low), float(high)


def evaluate_power_delay_loso(
    mpc: pd.DataFrame,
    bootstrap_iterations: int = 2000,
    seed: int = 20261025,
    scopes: Iterable[str] = ("GLOBAL",),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compare scene-balanced Normal power baseline with power~delay LOSO.

    Each scene has total training weight one. Scores are first averaged within
    each held-out scene; paired uncertainty resamples complete scenes. This is
    predictive evidence on the Stage2-selected MPC population, not a causal or
    universal physical law.
    """
    if bootstrap_iterations < 0:
        raise ValueError("bootstrap_iterations must be nonnegative")
    required = {"scene_id", "relative_power_db", "excess_delay_chips"}
    missing = required - set(mpc.columns)
    if missing:
        raise ValueError("MPC input missing columns: " + ",".join(sorted(missing)))
    if mpc.scene_id.isna().any():
        raise ValueError("MPC scene_id cannot be missing")

    rows: list[dict[str, Any]] = []
    for scope in tuple(scopes):
        scoped = _scope_rows(mpc, scope).copy()
        scoped["_x"] = pd.to_numeric(scoped.excess_delay_chips, errors="coerce")
        scoped["_y"] = pd.to_numeric(scoped.relative_power_db, errors="coerce")
        scoped = scoped[np.isfinite(scoped["_x"]) & np.isfinite(scoped["_y"])].copy()
        scenes = sorted(scoped.scene_id.astype(str).unique())
        if len(scenes) < 3:
            raise ValueError(f"{scope} requires at least three scenes for LOSO")
        scoped["scene_id"] = scoped.scene_id.astype(str)

        for held in scenes:
            train = scoped[scoped.scene_id != held].copy()
            test = scoped[scoped.scene_id == held]
            train_scenes = sorted(train.scene_id.unique().tolist())
            if len(train_scenes) < 2 or test.empty:
                rows.append(dict(scope=scope, held_out_scene_id=held,
                    fit_status="INSUFFICIENT_SCENE_SUPPORT", train_scene_n=len(train_scenes),
                    test_n=len(test), training_scene_ids=train_scenes))
                continue
            weights = _scene_balanced_weights(train)
            try:
                baseline_mean, baseline_scale = _weighted_normal(train["_y"].to_numpy(float), weights)
                design = np.column_stack([np.ones(len(train)), train["_x"].to_numpy(float)])
                root_weight = np.sqrt(weights)
                coefficients, _, rank, _ = np.linalg.lstsq(
                    design * root_weight[:, None], train["_y"].to_numpy(float) * root_weight, rcond=None
                )
                if rank != 2:
                    raise ValueError("weighted linear design is rank deficient")
                fitted = design @ coefficients
                residual_scale = math.sqrt(float(np.sum(weights * (train["_y"].to_numpy(float) - fitted) ** 2)
                                                / float(weights.sum())))
                if not np.isfinite(residual_scale) or residual_scale <= 0:
                    raise ValueError("conditional Gaussian residual scale is nonpositive or invalid")
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                rows.append(dict(scope=scope, held_out_scene_id=held,
                    fit_status="FIT_FAILED", failure_reason=f"{type(exc).__name__}: {exc}",
                    train_scene_n=len(train_scenes), train_n=len(train), test_n=len(test),
                    training_scene_ids=train_scenes))
                continue

            x_test = test["_x"].to_numpy(float)
            y_test = test["_y"].to_numpy(float)
            conditional_mean = coefficients[0] + coefficients[1] * x_test
            baseline_log = stats.norm.logpdf(y_test, loc=baseline_mean, scale=baseline_scale)
            conditional_log = stats.norm.logpdf(y_test, loc=conditional_mean, scale=residual_scale)
            if not np.isfinite(baseline_log).all() or not np.isfinite(conditional_log).all():
                fit_status = "NONFINITE_HELDOUT_SCORE"
            else:
                fit_status = "PASS"
            baseline_score = float(np.mean(baseline_log)) if np.isfinite(baseline_log).all() else None
            conditional_score = float(np.mean(conditional_log)) if np.isfinite(conditional_log).all() else None
            baseline_rmse = float(np.sqrt(np.mean((y_test - baseline_mean) ** 2)))
            conditional_rmse = float(np.sqrt(np.mean((y_test - conditional_mean) ** 2)))
            row = dict(
                scope=scope, held_out_scene_id=held, fit_status=fit_status,
                train_scene_n=len(train_scenes), training_scene_ids=train_scenes,
                train_n=len(train), test_n=len(test),
                train_scene_weight_min=float(min(weights[train.scene_id.to_numpy() == scene].sum()
                                                 for scene in train_scenes)),
                train_scene_weight_max=float(max(weights[train.scene_id.to_numpy() == scene].sum()
                                                 for scene in train_scenes)),
                baseline_family="SCENE_BALANCED_NORMAL_MARGINAL",
                baseline_loc=float(baseline_mean), baseline_scale=float(baseline_scale),
                conditional_family="SCENE_BALANCED_LINEAR_GAUSSIAN",
                conditional_intercept_db=float(coefficients[0]),
                conditional_slope_db_per_chip=float(coefficients[1]),
                conditional_scale=float(residual_scale),
                baseline_mean_log_score=baseline_score,
                conditional_mean_log_score=conditional_score,
                delta_mean_log_score=(conditional_score - baseline_score
                                      if conditional_score is not None and baseline_score is not None else None),
                baseline_rmse_db=baseline_rmse, conditional_rmse_db=conditional_rmse,
                delta_rmse_db=conditional_rmse - baseline_rmse,
            )
            rows.append(row)

    summaries: list[dict[str, Any]] = []
    for scope in tuple(scopes):
        group = [r for r in rows if r["scope"] == scope]
        valid = [r for r in group if r.get("fit_status") == "PASS"
                 and r.get("delta_mean_log_score") is not None]
        score_delta = np.asarray([r["delta_mean_log_score"] for r in valid], dtype=float)
        rmse_delta = np.asarray([r["delta_rmse_db"] for r in valid], dtype=float)
        low_score, high_score = _paired_scene_bootstrap(score_delta, bootstrap_iterations, seed)
        low_rmse, high_rmse = _paired_scene_bootstrap(rmse_delta, bootstrap_iterations, seed)
        slopes = [r["conditional_slope_db_per_chip"] for r in valid]
        summaries.append(dict(
            scope=scope, scene_n=len(group), evaluated_scene_n=len(valid),
            failed_or_unsupported_scene_n=len(group) - len(valid),
            negative_slope_scene_n=sum(value < 0 for value in slopes),
            slope_median_db_per_chip=float(np.median(slopes)) if slopes else None,
            slope_min_db_per_chip=float(min(slopes)) if slopes else None,
            slope_max_db_per_chip=float(max(slopes)) if slopes else None,
            macro_delta_mean_log_score=float(np.mean(score_delta)) if len(score_delta) else None,
            delta_mean_log_score_scene_bootstrap_95_low=low_score,
            delta_mean_log_score_scene_bootstrap_95_high=high_score,
            macro_delta_rmse_db=float(np.mean(rmse_delta)) if len(rmse_delta) else None,
            delta_rmse_scene_bootstrap_95_low=low_rmse,
            delta_rmse_scene_bootstrap_95_high=high_rmse,
            bootstrap_iteration_n=bootstrap_iterations if valid else 0,
            bootstrap_unit="whole_scene_with_multiplicity",
            inferential_claim="descriptive_scene_generalization_only_no_p_value",
        ))
    return rows, summaries


COUNT_SUPPORT = np.arange(4, dtype=int)
COUNT_ESTIMAND = "P(MPC count | Stage2-selected window; support 0..3)"


def _validated_selected_windows(windows: pd.DataFrame) -> pd.DataFrame:
    required = {"run_id", "window_id", "scene_id", "mpc_count"}
    missing = required - set(windows.columns)
    if missing:
        raise ValueError("selected-window input missing columns: " + ",".join(sorted(missing)))
    result = windows[list(required)].copy()
    if result[list(required)].isna().any().any():
        raise ValueError("selected-window identities/counts cannot be missing")
    for column in ("run_id", "scene_id"):
        result[column] = result[column].astype(str)
        if result[column].str.strip().eq("").any():
            raise ValueError(f"{column} cannot be blank")
    canonical = []
    for value in result.window_id:
        text = str(value)
        if not text.isascii() or not text.isdecimal() or str(int(text)) != text or int(text) < 1:
            raise ValueError("window_id must be a canonical positive decimal identity")
        canonical.append(text)
    result["window_id"] = canonical
    if result.duplicated(["run_id", "window_id"]).any():
        raise ValueError("duplicate (run_id, window_id) identity")
    if result.groupby("run_id").scene_id.nunique().gt(1).any():
        raise ValueError("one run_id maps to multiple scene_id values")
    counts = pd.to_numeric(result.mpc_count, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(counts).all() or np.any(counts % 1 != 0):
        raise ValueError("mpc_count must be a finite integer")
    if np.any((counts < 0) | (counts > 3)):
        raise ValueError("mpc_count outside observed Stage2 selected-window support 0..3")
    result["mpc_count"] = counts.astype(int)
    return result


def _truncated_poisson_pmf(rate: float) -> np.ndarray:
    if rate == 0:
        return np.asarray([1.0, 0.0, 0.0, 0.0])
    log_mass = COUNT_SUPPORT * math.log(rate) - rate - gammaln(COUNT_SUPPORT + 1)
    return np.exp(log_mass - logsumexp(log_mass))


def _fit_truncated_poisson(counts: np.ndarray, weights: np.ndarray) -> tuple[str, dict[str, float], np.ndarray | None]:
    target = float(np.sum(weights * counts) / weights.sum())
    if target == 0:
        return "BOUNDARY_AT_ZERO", {"rate": 0.0}, _truncated_poisson_pmf(0.0)
    if target >= 3.0:
        return "BOUNDARY_AT_MAX_SUPPORT", {"boundary": "MAX_SUPPORT"}, np.asarray([0.0, 0.0, 0.0, 1.0])

    def expected(rate: float) -> float:
        return float(np.dot(COUNT_SUPPORT, _truncated_poisson_pmf(rate)))

    upper = 1.0
    while expected(upper) <= target and upper < 1e8:
        upper *= 2.0
    if expected(upper) <= target:
        return "FIT_FAILED", {}, None
    rate = float(optimize.brentq(lambda value: expected(value) - target, 0.0, upper,
                                 xtol=1e-12, rtol=1e-12, maxiter=500))
    pmf = _truncated_poisson_pmf(rate)
    return "PASS", {"rate": rate}, pmf


def _truncated_nb2_pmf(mean: float, alpha: float) -> np.ndarray:
    if mean <= 0 or alpha <= 0:
        raise ValueError("NB2 mean and dispersion must be positive")
    size = 1.0 / alpha
    log_mass = (gammaln(COUNT_SUPPORT + size) - gammaln(size) - gammaln(COUNT_SUPPORT + 1)
                + size * math.log(size / (size + mean))
                + COUNT_SUPPORT * math.log(mean / (size + mean)))
    return np.exp(log_mass - logsumexp(log_mass))


def _truncated_nb2_infinite_mean_limit_pmf(alpha: float) -> np.ndarray:
    """Conditional 0..3 limit as the NB2 mean tends to infinity at fixed size."""
    if alpha <= 0:
        raise ValueError("NB2 dispersion must be positive")
    size = 1.0 / alpha
    log_mass = gammaln(COUNT_SUPPORT + size) - gammaln(size) - gammaln(COUNT_SUPPORT + 1)
    return np.exp(log_mass - logsumexp(log_mass))


def _fit_truncated_nb2(counts: np.ndarray, weights: np.ndarray) -> tuple[str, dict[str, Any], np.ndarray | None]:
    # Parameters are optimized on log scale. Multiple modest starts reduce
    # sensitivity to the mean/dispersion ridge in this four-point support.
    def objective(theta: np.ndarray) -> float:
        mean, alpha = np.exp(theta)
        pmf = _truncated_nb2_pmf(float(mean), float(alpha))
        probabilities = pmf[counts]
        if not np.isfinite(probabilities).all() or np.any(probabilities <= 0):
            return math.inf
        return float(-np.sum(weights * np.log(probabilities)))

    starts = [np.log([0.5, alpha]) for alpha in (0.01, 0.2, 2.0)]
    bounds = [(-12.0, 8.0), (-12.0, 8.0)]
    candidates = [optimize.minimize(objective, start, method="L-BFGS-B", bounds=bounds,
                                    options={"maxiter": 2000, "ftol": 1e-12, "gtol": 1e-8})
                  for start in starts]
    successful = [result for result in candidates if result.success and np.isfinite(result.fun)]
    if not successful:
        return "FIT_FAILED", {}, None
    best = min(successful, key=lambda result: float(result.fun))
    mean, alpha = np.exp(best.x)
    if float(best.x[0]) >= bounds[0][1] - 1e-4:
        # For support-truncated NB2 the conditional PMF has a finite limit as
        # mean -> infinity. Reporting the optimizer's arbitrary upper bound as
        # a finite MLE would be misleading; optimize the identifiable limit
        # over dispersion and retain the boundary explicitly.
        def limit_objective(log_alpha: float) -> float:
            pmf = _truncated_nb2_infinite_mean_limit_pmf(float(np.exp(log_alpha)))
            probabilities = pmf[counts]
            return float(-np.sum(weights * np.log(probabilities)))

        limit = optimize.minimize_scalar(limit_objective, method="bounded",
                                         bounds=bounds[1], options={"xatol": 1e-10, "maxiter": 2000})
        if not limit.success or not np.isfinite(limit.fun):
            return "FIT_FAILED", {}, None
        alpha_limit = float(np.exp(limit.x))
        alpha_boundary = (float(limit.x) <= bounds[1][0] + 1e-4 or
                          float(limit.x) >= bounds[1][1] - 1e-4)
        status = "BOUNDARY_MEAN_AND_DISPERSION" if alpha_boundary else "BOUNDARY_MEAN_AT_INFINITY"
        return status, {"mean": None, "alpha": alpha_limit, "mean_boundary": "INFINITY_LIMIT"}, \
            _truncated_nb2_infinite_mean_limit_pmf(alpha_limit)

    pmf = _truncated_nb2_pmf(float(mean), float(alpha))
    alpha_boundary = (float(best.x[1]) <= bounds[1][0] + 1e-5 or
                      float(best.x[1]) >= bounds[1][1] - 1e-5)
    status = "BOUNDARY_DISPERSION" if alpha_boundary else "PASS"
    return status, {"mean": float(mean), "alpha": float(alpha)}, pmf


def _scene_equal_categorical(counts: np.ndarray, scenes: np.ndarray) -> np.ndarray:
    scene_pmfs = []
    for scene in sorted(set(scenes.tolist())):
        values = counts[scenes == scene]
        scene_pmfs.append(np.bincount(values, minlength=4).astype(float) / len(values))
    return np.mean(np.asarray(scene_pmfs), axis=0)


def _pmf_metrics(pmf: np.ndarray, observed: np.ndarray) -> tuple[float, float, int, int]:
    probabilities = pmf[observed]
    unseen_mask = probabilities == 0
    unseen_category_n = int(len(set(observed[unseen_mask].tolist())))
    unseen_observation_n = int(np.count_nonzero(unseen_mask))
    log_scores = np.full(len(observed), -np.inf, dtype=float)
    positive = probabilities > 0
    log_scores[positive] = np.log(probabilities[positive])
    log_score = float(np.mean(log_scores))
    predicted_mean = float(np.dot(COUNT_SUPPORT, pmf))
    rmse = float(np.sqrt(np.mean((observed - predicted_mean) ** 2)))
    return log_score, rmse, unseen_category_n, unseen_observation_n


def evaluate_selected_count_loso(
    windows: pd.DataFrame,
    bootstrap_iterations: int = 2000,
    seed: int = 20261025,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """LOSO count models for Stage2-selected windows only, with capped support 0..3."""
    if bootstrap_iterations < 0:
        raise ValueError("bootstrap_iterations must be nonnegative")
    selected = _validated_selected_windows(windows)
    scenes = sorted(selected.scene_id.unique().tolist())
    if len(scenes) < 3:
        raise ValueError("selected-count LOSO requires at least three complete scenes")
    model_names = ("EMPIRICAL_CATEGORICAL", "TRUNCATED_POISSON", "TRUNCATED_NB2")
    rows: list[dict[str, Any]] = []
    for held in scenes:
        train = selected[selected.scene_id != held].copy()
        test = selected[selected.scene_id == held]
        train_scenes = sorted(train.scene_id.unique().tolist())
        if len(train_scenes) < 2 or test.empty:
            raise ValueError("every count fold requires at least two training scenes and a held-out scene")
        train_counts = train.mpc_count.to_numpy(dtype=int)
        weights = _scene_balanced_weights(train)
        held_counts = test.mpc_count.to_numpy(dtype=int)
        held_hist = {str(value): int(np.count_nonzero(held_counts == value)) for value in COUNT_SUPPORT}

        categorical = _scene_equal_categorical(train_counts, train.scene_id.to_numpy())
        poisson_status, poisson_params, poisson = _fit_truncated_poisson(train_counts, weights)
        nb_status, nb_params, nb2 = _fit_truncated_nb2(train_counts, weights)
        fits = {
            "EMPIRICAL_CATEGORICAL": ("PASS", {f"p{value}": float(categorical[value]) for value in COUNT_SUPPORT}, categorical),
            "TRUNCATED_POISSON": (poisson_status, poisson_params, poisson),
            "TRUNCATED_NB2": (nb_status, nb_params, nb2),
        }
        for model in model_names:
            fit_status, parameters, pmf = fits[model]
            row: dict[str, Any] = dict(
                estimand=COUNT_ESTIMAND, scope="GLOBAL", held_out_scene_id=held,
                candidate_model=model, fit_status=fit_status,
                train_scene_n=len(train_scenes), training_scene_ids=train_scenes,
                train_selected_window_n=len(train), test_window_n=len(test),
                observed_count_histogram=held_hist, fit_parameters=parameters,
                predictive_pmf=[float(value) for value in pmf] if pmf is not None else None,
                unseen_category_n=0, unseen_heldout_observation_n=0,
                mean_log_score=None, rmse_count=None,
            )
            if pmf is not None and np.isfinite(pmf).all() and np.all(pmf >= 0) and abs(float(pmf.sum()) - 1.0) <= 1e-9:
                log_score, rmse, unseen_categories, unseen_observations = _pmf_metrics(pmf, held_counts)
                row.update(
                    unseen_category_n=unseen_categories,
                    unseen_heldout_observation_n=unseen_observations,
                    fit_status=("UNSEEN_HELDOUT_CATEGORY" if model == "EMPIRICAL_CATEGORICAL" and unseen_categories else fit_status),
                    mean_log_score=log_score, rmse_count=rmse,
                )
            rows.append(row)

    summaries: list[dict[str, Any]] = []
    categorical_by_scene = {r["held_out_scene_id"]: r for r in rows
                            if r["candidate_model"] == "EMPIRICAL_CATEGORICAL"}
    for model in model_names:
        group = [r for r in rows if r["candidate_model"] == model]
        evaluated = [r for r in group if r["mean_log_score"] is not None and r["rmse_count"] is not None]
        scores = np.asarray([r["mean_log_score"] for r in evaluated], dtype=float)
        rmse_values = np.asarray([r["rmse_count"] for r in evaluated], dtype=float)
        rmse_deltas = np.asarray([
            r["rmse_count"] - categorical_by_scene[r["held_out_scene_id"]]["rmse_count"]
            for r in evaluated if categorical_by_scene[r["held_out_scene_id"]]["rmse_count"] is not None
        ], dtype=float)
        paired_scores = []
        for row in evaluated:
            baseline = categorical_by_scene[row["held_out_scene_id"]]["mean_log_score"]
            if baseline is not None and np.isfinite(baseline) and np.isfinite(row["mean_log_score"]):
                paired_scores.append(row["mean_log_score"] - baseline)
        score_low, score_high = _paired_scene_bootstrap(np.asarray(paired_scores), bootstrap_iterations, seed)
        rmse_low, rmse_high = _paired_scene_bootstrap(rmse_deltas, bootstrap_iterations, seed)
        finite_scores = bool(len(scores) and np.isfinite(scores).all())
        macro_score = float(np.mean(scores)) if finite_scores else None
        if finite_scores:
            macro_score_status = "FINITE"
        elif np.isneginf(scores).any():
            macro_score_status = "NEGATIVE_INFINITY_FROM_ZERO_PROBABILITY"
        else:
            macro_score_status = "NO_EVALUABLE_OR_NONFINITE_SCENES"
        summaries.append(dict(
            estimand=COUNT_ESTIMAND, scope="GLOBAL", candidate_model=model,
            held_out_scene_n=len(group), evaluated_scene_n=len(evaluated),
            failed_or_unsupported_scene_n=len(group) - len(evaluated),
            fit_status_counts={status: sum(r["fit_status"] == status for r in group)
                               for status in sorted({r["fit_status"] for r in group})},
            boundary_fit_scene_n=sum(r["fit_status"] in {
                "BOUNDARY_AT_ZERO", "BOUNDARY_AT_MAX_SUPPORT", "BOUNDARY_SOLUTION",
                "BOUNDARY_DISPERSION", "BOUNDARY_MEAN_AT_INFINITY",
                "BOUNDARY_MEAN_AND_DISPERSION",
            } for r in group),
            unseen_category_scene_n=sum(r["unseen_category_n"] > 0 for r in group),
            macro_mean_log_score=macro_score,
            macro_mean_log_score_status=macro_score_status,
            paired_finite_scene_n=len(paired_scores),
            macro_log_score_delta_vs_categorical=(float(np.mean(paired_scores)) if paired_scores else None),
            log_score_delta_scene_bootstrap_95_low=score_low,
            log_score_delta_scene_bootstrap_95_high=score_high,
            macro_rmse_count=float(np.mean(rmse_values)) if len(rmse_values) else None,
            macro_rmse_delta_vs_categorical=float(np.mean(rmse_deltas)) if len(rmse_deltas) else None,
            rmse_delta_scene_bootstrap_95_low=rmse_low,
            rmse_delta_scene_bootstrap_95_high=rmse_high,
            bootstrap_iteration_n=bootstrap_iterations if evaluated else 0,
            bootstrap_unit="whole_scene_with_multiplicity",
            model_selection_claim="selection_conditional_exploratory_no_unselected_stage0_zero_assignment",
        ))
    return rows, summaries
