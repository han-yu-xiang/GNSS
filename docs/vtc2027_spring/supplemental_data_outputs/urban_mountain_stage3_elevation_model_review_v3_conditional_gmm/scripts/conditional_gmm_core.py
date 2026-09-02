#!/usr/bin/env python3
"""Weighted partially pooled conditional multivariate Gaussian mixture model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np


FEATURE_FIELDS = ("log_excess_delay", "log1p_absolute_doppler", "relative_power_db")
ENVIRONMENT_FIELD = "environment_class"
CELL_FIELD = "cell_id"
CELL_READY_FIELD = "cell_ready"
WEIGHT_FIELD = "track_weight_recomputed_primary"


@dataclass(frozen=True)
class ConditionalGMMConfig:
    component_count: int
    pooling_kappa: float
    max_iterations: int = 500
    tolerance: float = 1e-7
    covariance_floor: float = 1e-5
    weight_floor: float = 1e-6
    restart_count: int = 10
    seed: int = 2026083104

    def __post_init__(self) -> None:
        if self.component_count not in (1, 2, 3):
            raise ValueError("component_count must be 1, 2, or 3")
        if self.pooling_kappa <= 0.0:
            raise ValueError("pooling_kappa must be positive")


@dataclass
class ConditionalGMM:
    config: ConditionalGMMConfig
    doppler_feature_field: str
    transform_center: np.ndarray
    transform_scale: np.ndarray
    global_weights: np.ndarray
    global_means: np.ndarray
    environment_weights: dict[str, np.ndarray]
    environment_means: dict[str, np.ndarray]
    cell_weights: dict[str, np.ndarray]
    shared_covariances: np.ndarray
    log_likelihood_history: list[float]


def feature_matrix(rows: Sequence[Mapping[str, Any]], doppler_feature_field: str = "log1p_absolute_doppler") -> np.ndarray:
    if not rows:
        raise ValueError("at least one row is required")
    matrix = np.asarray(
        [
            [
                float(row["log_excess_delay"]),
                float(row[doppler_feature_field]),
                float(row["relative_power_db"]),
            ]
            for row in rows
        ],
        dtype=float,
    )
    if not np.all(np.isfinite(matrix)):
        raise ValueError("feature matrix contains a non-finite value")
    return matrix


def row_weights(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    weights = np.asarray([float(row[WEIGHT_FIELD]) for row in rows], dtype=float)
    if not np.all(np.isfinite(weights)) or np.any(weights <= 0.0):
        raise ValueError("weights must be finite and positive")
    return weights


def weighted_center_scale(rows: Sequence[Mapping[str, Any]], doppler_feature_field: str = "log1p_absolute_doppler") -> tuple[np.ndarray, np.ndarray]:
    values = feature_matrix(rows, doppler_feature_field)
    weights = row_weights(rows)
    total = float(np.sum(weights))
    center = np.sum(values * weights[:, None], axis=0) / total
    variance = np.sum(((values - center) ** 2) * weights[:, None], axis=0) / total
    scale = np.sqrt(np.maximum(variance, 1e-12))
    return center, scale


def standardize_features(values: np.ndarray, center: np.ndarray, scale: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    center = np.asarray(center, dtype=float)
    scale = np.asarray(scale, dtype=float)
    if values.ndim != 2 or values.shape[1] != 3 or center.shape != (3,) or scale.shape != (3,):
        raise ValueError("three-dimensional feature shapes are required")
    return (values - center[None, :]) / scale[None, :]


def shrink_probabilities(local_responsibility: np.ndarray, parent: np.ndarray, kappa: float, weight_floor: float = 1e-6) -> np.ndarray:
    local = np.asarray(local_responsibility, dtype=float)
    parent_array = np.asarray(parent, dtype=float)
    if local.ndim != 1 or parent_array.ndim != 1 or local.shape != parent_array.shape:
        raise ValueError("local and parent probabilities must have the same one-dimensional shape")
    if np.any(local < 0.0) or np.any(parent_array < 0.0) or not np.isfinite(kappa) or kappa < 0.0:
        raise ValueError("probability inputs are invalid")
    if float(np.sum(parent_array)) <= 0.0:
        raise ValueError("parent probabilities must have positive mass")
    result = local + kappa * parent_array / float(np.sum(parent_array))
    result = np.maximum(result, weight_floor)
    return result / float(np.sum(result))


def _logsumexp(values: np.ndarray, axis: int = -1) -> np.ndarray:
    maximum = np.max(values, axis=axis, keepdims=True)
    output = maximum + np.log(np.sum(np.exp(values - maximum), axis=axis, keepdims=True))
    return np.squeeze(output, axis=axis)


def _stable_covariance(covariance: np.ndarray, floor: float) -> np.ndarray:
    symmetric = 0.5 * (np.asarray(covariance, dtype=float) + np.asarray(covariance, dtype=float).T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    eigenvalues = np.maximum(eigenvalues, floor)
    return (eigenvectors * eigenvalues[None, :]) @ eigenvectors.T


def _log_gaussian(values: np.ndarray, mean: np.ndarray, covariance: np.ndarray) -> np.ndarray:
    covariance = _stable_covariance(covariance, 1e-12)
    sign, logdet = np.linalg.slogdet(covariance)
    if sign <= 0.0 or not np.isfinite(logdet):
        raise ValueError("covariance is not positive definite")
    centered = values - mean[None, :]
    solved = np.linalg.solve(covariance, centered.T).T
    quadratic = np.sum(centered * solved, axis=1)
    return -0.5 * (3.0 * np.log(2.0 * np.pi) + logdet + quadratic)


def _weighted_covariance(values: np.ndarray, weights: np.ndarray, center: np.ndarray, floor: float) -> np.ndarray:
    total = float(np.sum(weights))
    if total <= 0.0:
        raise ValueError("component responsibility has no mass")
    centered = values - center[None, :]
    covariance = (centered * weights[:, None]).T @ centered / total
    return _stable_covariance(covariance, floor)


def _initial_component_means(values: np.ndarray, weights: np.ndarray, component_count: int, rng: np.random.Generator) -> np.ndarray:
    order = np.argsort(values[:, 2], kind="mergesort")
    sorted_values = values[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    total = float(cumulative[-1])
    means: list[np.ndarray] = []
    for component in range(component_count):
        lower = total * component / component_count
        upper = total * (component + 1) / component_count
        mask = (cumulative > lower) & (cumulative <= upper)
        if not np.any(mask):
            index = min(int(round((component + 0.5) * values.shape[0] / component_count - 0.5)), values.shape[0] - 1)
            means.append(sorted_values[index].copy())
        else:
            selected_values = sorted_values[mask]
            selected_weights = sorted_weights[mask]
            means.append(np.sum(selected_values * selected_weights[:, None], axis=0) / float(np.sum(selected_weights)))
    result = np.asarray(means, dtype=float)
    result += rng.normal(0.0, 1e-4, size=result.shape)
    return result


def _scope_arrays(rows: Sequence[Mapping[str, Any]], doppler_feature_field: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str]]:
    values = feature_matrix(rows, doppler_feature_field)
    weights = row_weights(rows)
    environments = np.asarray([str(row[ENVIRONMENT_FIELD]) for row in rows], dtype=object)
    cells = [str(row.get(CELL_FIELD, "")) if str(row.get(CELL_READY_FIELD, "0")) == "1" else "" for row in rows]
    unique_environments = sorted(set(environments.tolist()))
    unique_cells = sorted(cell for cell in set(cells) if cell)
    return values, weights, environments, unique_environments, unique_cells


def _initial_state(values: np.ndarray, weights: np.ndarray, environments: np.ndarray, cells: Sequence[str], config: ConditionalGMMConfig, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray]:
    component_count = config.component_count
    global_means = _initial_component_means(values, weights, component_count, rng)
    global_weights = np.full(component_count, 1.0 / component_count, dtype=float)
    total = float(np.sum(weights))
    covariance = _weighted_covariance(values, weights, np.average(values, axis=0, weights=weights), config.covariance_floor)
    covariances = np.repeat(covariance[None, :, :], component_count, axis=0)
    environment_weights = {environment: global_weights.copy() for environment in sorted(set(environments.tolist()))}
    environment_means = {environment: global_means.copy() for environment in sorted(set(environments.tolist()))}
    cell_weights = {cell: environment_weights[cell.split("__", 1)[0]].copy() for cell in sorted(set(cells)) if cell}
    if total <= 0.0:
        raise ValueError("source weights have no mass")
    return global_weights, global_means, environment_weights, environment_means, cell_weights, covariances


def _responsibilities(values: np.ndarray, environments: np.ndarray, cells: Sequence[str], environment_weights: Mapping[str, np.ndarray], cell_weights: Mapping[str, np.ndarray], environment_means: Mapping[str, np.ndarray], covariances: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = values.shape[0]
    component_count = covariances.shape[0]
    log_values = np.empty((n, component_count), dtype=float)
    for index in range(n):
        weights = cell_weights[cells[index]] if cells[index] else environment_weights[str(environments[index])]
        for component in range(component_count):
            log_values[index, component] = np.log(max(float(weights[component]), 1e-12)) + float(_log_gaussian(values[index:index + 1], environment_means[str(environments[index])][component], covariances[component])[0])
    log_normalizer = _logsumexp(log_values, axis=1)
    responsibilities = np.exp(log_values - log_normalizer[:, None])
    return responsibilities, log_normalizer


def _reorder_state(global_weights: np.ndarray, global_means: np.ndarray, environment_weights: dict[str, np.ndarray], environment_means: dict[str, np.ndarray], cell_weights: dict[str, np.ndarray], covariances: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray]:
    order = np.lexsort((global_means[:, 0], global_means[:, 1], global_means[:, 2]))
    return (
        global_weights[order],
        global_means[order],
        {key: value[order] for key, value in environment_weights.items()},
        {key: value[order] for key, value in environment_means.items()},
        {key: value[order] for key, value in cell_weights.items()},
        covariances[order],
    )


def _fit_single(values: np.ndarray, weights: np.ndarray, environments: np.ndarray, cells: Sequence[str], config: ConditionalGMMConfig, rng: np.random.Generator) -> tuple[float, tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray, list[float]]]:
    global_weights, global_means, environment_weights, environment_means, cell_weights, covariances = _initial_state(values, weights, environments, cells, config, rng)
    history: list[float] = []
    total_weight = float(np.sum(weights))
    previous = -np.inf
    for _ in range(config.max_iterations):
        responsibilities, log_normalizer = _responsibilities(values, environments, cells, environment_weights, cell_weights, environment_means, covariances)
        log_likelihood = float(np.sum(weights * log_normalizer))
        history.append(log_likelihood)
        if np.isfinite(previous) and abs(log_likelihood - previous) <= config.tolerance * (1.0 + abs(previous)):
            break
        previous = log_likelihood
        weighted_responsibilities = responsibilities * weights[:, None]
        component_mass = np.sum(weighted_responsibilities, axis=0)
        global_weights = np.maximum(component_mass / total_weight, config.weight_floor)
        global_weights /= float(np.sum(global_weights))
        global_means = (weighted_responsibilities.T @ values) / np.maximum(component_mass[:, None], 1e-12)
        new_environment_weights: dict[str, np.ndarray] = {}
        new_environment_means: dict[str, np.ndarray] = {}
        for environment in sorted(set(environments.tolist())):
            mask = environments == environment
            local_mass = np.sum(weighted_responsibilities[mask], axis=0)
            local_total = float(np.sum(weights[mask]))
            new_environment_weights[environment] = shrink_probabilities(local_mass, global_weights, config.pooling_kappa, config.weight_floor)
            new_environment_means[environment] = (weighted_responsibilities[mask].T @ values[mask] + config.pooling_kappa * global_means) / np.maximum(local_mass[:, None] + config.pooling_kappa, 1e-12)
        new_cell_weights: dict[str, np.ndarray] = {}
        for cell in sorted(set(cells)):
            if not cell:
                continue
            environment = cell.split("__", 1)[0]
            mask = np.asarray([candidate == cell for candidate in cells], dtype=bool)
            local_mass = np.sum(weighted_responsibilities[mask], axis=0)
            new_cell_weights[cell] = shrink_probabilities(local_mass, new_environment_weights[environment], config.pooling_kappa, config.weight_floor)
        new_covariances = np.empty_like(covariances)
        for component in range(config.component_count):
            centers = np.asarray([new_environment_means[str(environment)][component] for environment in environments], dtype=float)
            centered = values - centers
            covariance = (centered * weighted_responsibilities[:, component][:, None]).T @ centered / max(float(component_mass[component]), 1e-12)
            new_covariances[component] = _stable_covariance(covariance, config.covariance_floor)
        global_weights, global_means, environment_weights, environment_means, cell_weights, covariances = _reorder_state(global_weights, global_means, new_environment_weights, new_environment_means, new_cell_weights, new_covariances)
    responsibilities, log_normalizer = _responsibilities(values, environments, cells, environment_weights, cell_weights, environment_means, covariances)
    final_log_likelihood = float(np.sum(weights * log_normalizer))
    if not np.isfinite(final_log_likelihood):
        raise ValueError("non-finite final log likelihood")
    return final_log_likelihood, (global_weights, global_means, environment_weights, environment_means, cell_weights, covariances, history)


def fit_conditional_gmm(rows: Sequence[Mapping[str, Any]], config: ConditionalGMMConfig, doppler_feature_field: str = "log1p_absolute_doppler") -> ConditionalGMM:
    raw_values, weights, environments, unique_environments, unique_cells = _scope_arrays(rows, doppler_feature_field)
    center, scale = weighted_center_scale(rows, doppler_feature_field)
    values = standardize_features(raw_values, center, scale)
    cells = [str(row.get(CELL_FIELD, "")) if str(row.get(CELL_READY_FIELD, "0")) == "1" else "" for row in rows]
    best_score = -np.inf
    best_state: tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray, list[float]] | None = None
    for restart in range(config.restart_count):
        rng = np.random.default_rng(config.seed + restart)
        score, state = _fit_single(values, weights, environments, cells, config, rng)
        if best_state is None or score > best_score:
            best_score = score
            best_state = state
    if best_state is None:
        raise ValueError("no valid GMM restart")
    global_weights, global_means, environment_weights, environment_means, cell_weights, covariances, history = best_state
    if set(environment_weights) != set(unique_environments) or set(cell_weights) != set(unique_cells):
        raise ValueError("scope state is incomplete")
    return ConditionalGMM(config, doppler_feature_field, center, scale, global_weights, global_means, environment_weights, environment_means, cell_weights, covariances, history)


def _model_values(model: ConditionalGMM, rows: Sequence[Mapping[str, Any]]) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    raw_values = feature_matrix(rows, model.doppler_feature_field)
    values = standardize_features(raw_values, model.transform_center, model.transform_scale)
    weights = row_weights(rows)
    environments = [str(row[ENVIRONMENT_FIELD]) for row in rows]
    cells = [str(row.get(CELL_FIELD, "")) if str(row.get(CELL_READY_FIELD, "0")) == "1" else "" for row in rows]
    return values, weights, environments, cells


def log_predictive_density(model: ConditionalGMM, rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    values, _, environments, cells = _model_values(model, rows)
    output = np.empty(len(rows), dtype=float)
    for index, environment in enumerate(environments):
        env_key = environment if environment in model.environment_weights else next(iter(model.environment_weights))
        weights = model.cell_weights[cells[index]] if cells[index] in model.cell_weights else model.environment_weights[env_key]
        means = model.environment_means[env_key]
        component_logpdf = np.asarray([np.log(max(float(weights[component]), 1e-12)) + float(_log_gaussian(values[index:index + 1], means[component], model.shared_covariances[component])[0]) for component in range(model.config.component_count)])
        output[index] = float(_logsumexp(component_logpdf, axis=0))
    if not np.all(np.isfinite(output)):
        raise ValueError("non-finite predictive density")
    return output


def sample_conditional(model: ConditionalGMM, environment: str, elevation_band: str | None, count: int, seed: int) -> np.ndarray:
    if count <= 0:
        raise ValueError("count must be positive")
    env_key = environment if environment in model.environment_weights else next(iter(model.environment_weights))
    cell_key = f"{environment}__{elevation_band}" if elevation_band else ""
    weights = model.cell_weights.get(cell_key, model.environment_weights[env_key])
    rng = np.random.default_rng(seed)
    components = rng.choice(model.config.component_count, size=count, p=weights)
    standardized = np.empty((count, 3), dtype=float)
    for component in range(model.config.component_count):
        mask = components == component
        if np.any(mask):
            standardized[mask] = rng.multivariate_normal(model.environment_means[env_key][component], model.shared_covariances[component], size=int(np.sum(mask)))
    return standardized * model.transform_scale[None, :] + model.transform_center[None, :]
