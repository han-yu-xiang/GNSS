"""Core, auditable primitives for the environment/elevation path model.

This module deliberately contains no raw-IQ, MATLAB, SAGE, or production-pipeline
entry points.  It consumes the frozen Stage4 path-parameter CSV only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import optimize, stats


ENVIRONMENTS: tuple[str, ...] = (
    "Urban",
    "Special Reflective",
    "Mountain/Valley",
    "Highway/Open",
)
ELEVATION_BANDS: tuple[str, ...] = ("LOW", "MID", "HIGH")
FIT_PARAMETERS: tuple[str, ...] = (
    "relative_delay_ns",
    "relative_doppler_hz",
    "relative_power_db",
)
OUTPUT_PARAMETERS: tuple[str, ...] = (
    *FIT_PARAMETERS,
    "relative_amplitude_linear",
)
_BAND_LIMITS: dict[str, tuple[float, float, bool]] = {
    "LOW": (0.0, 30.0, False),
    "MID": (30.0, 60.0, False),
    "HIGH": (60.0, 90.0, True),
}
_ALLOWED_FAMILIES = {
    "lognormal",
    "gamma",
    "weibull",
    "student_t",
    "normal",
    "laplace",
}


@dataclass(frozen=True)
class FitConfig:
    model_id: str
    model_version: str
    parameter_set_id: str
    source_relative_path: str
    source_sha256: str
    environments: tuple[str, ...]
    elevation_bands: tuple[str, ...]
    candidate_families: Mapping[str, tuple[str, ...]]
    family_tie_tolerance: float
    parent_quantile_count: int
    prior_equivalent_weight: float
    copula_shrinkage_denominator: float
    copula_eigenvalue_floor: float
    bootstrap_seed: int
    bootstrap_replicates: int
    qa_draw_seed: int
    qa_draw_count: int
    output_namespace: str
    execution_policy: Mapping[str, Any]
    sampling_contract: Mapping[str, Any]
    protected_source: Mapping[str, Any]

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "FitConfig":
        expected_env = tuple(data.get("environments", ()))
        expected_bands = tuple(data.get("elevation_bands", ()))
        if expected_env != ENVIRONMENTS:
            raise ValueError(f"environment order/values are not frozen: {expected_env}")
        if expected_bands != ELEVATION_BANDS:
            raise ValueError(f"elevation bands are not frozen: {expected_bands}")
        candidate_data = data.get("candidate_families", {})
        candidate_families = {
            str(parameter): tuple(str(family) for family in families)
            for parameter, families in candidate_data.items()
        }
        for parameter in FIT_PARAMETERS:
            if parameter not in candidate_families:
                raise ValueError(f"missing candidate families for {parameter}")
            if any(family not in _ALLOWED_FAMILIES for family in candidate_families[parameter]):
                raise ValueError(f"unknown family for {parameter}: {candidate_families[parameter]}")
        hierarchical = data.get("hierarchical_prior", {})
        copula = data.get("copula", {})
        uncertainty = data.get("uncertainty", {})
        if int(hierarchical.get("parent_quantile_count", 0)) != 64:
            raise ValueError("parent quantile count must remain 64")
        if float(hierarchical.get("prior_equivalent_weight", 0.0)) != 8.0:
            raise ValueError("prior equivalent weight must remain 8.0")
        if float(copula.get("shrinkage_denominator", 0.0)) != 10.0:
            raise ValueError("copula shrinkage denominator must remain 10.0")
        return cls(
            model_id=str(data["model_id"]),
            model_version=str(data["model_version"]),
            parameter_set_id=str(data["parameter_set_id"]),
            source_relative_path=str(data["source_relative_path"]),
            source_sha256=str(data["source_sha256"]).lower(),
            environments=expected_env,
            elevation_bands=expected_bands,
            candidate_families=candidate_families,
            family_tie_tolerance=float(data["family_tie_tolerance"]),
            parent_quantile_count=int(hierarchical["parent_quantile_count"]),
            prior_equivalent_weight=float(hierarchical["prior_equivalent_weight"]),
            copula_shrinkage_denominator=float(copula["shrinkage_denominator"]),
            copula_eigenvalue_floor=float(copula["eigenvalue_floor"]),
            bootstrap_seed=int(uncertainty["bootstrap_seed"]),
            bootstrap_replicates=int(uncertainty["bootstrap_replicates"]),
            qa_draw_seed=int(uncertainty["qa_draw_seed"]),
            qa_draw_count=int(uncertainty["qa_draw_count"]),
            output_namespace=str(data["output_namespace"]),
            execution_policy=dict(data.get("execution_policy", {})),
            sampling_contract=dict(data.get("sampling_contract", {})),
            protected_source=dict(data.get("protected_source", {})),
        )


def load_frozen_config(path: Path) -> FitConfig:
    """Load and validate the versioned modeling contract."""

    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    return FitConfig.from_json(data)


@dataclass(frozen=True)
class PathObservation:
    event_path_id: str
    event_id: str
    run_id: str
    scene_id: str
    prn: str
    tracking_channel: str
    environment: str
    elevation_deg: float | None
    elevation_band: str | None
    geometry_join_valid: bool
    environment_modeling_ready: bool
    elevation_modeling_ready: bool
    estimate_stage: str
    path_role: str
    is_multipath: bool
    label_value: str
    excess_delay_s: float
    relative_doppler_hz: float
    relative_power_db: float
    source_file: str
    source_file_sha256: str
    source_row_number: int


@dataclass(frozen=True)
class ModelVector:
    event_path_id: str
    event_id: str
    run_id: str
    scene_id: str
    environment: str
    elevation_band: str | None
    relative_delay_ns: float
    relative_doppler_hz: float
    relative_power_db: float


@dataclass(frozen=True)
class SourceAudit:
    source_path: str
    source_sha256: str
    source_row_count: int
    environment_ready_count: int
    elevation_ready_count: int
    elevation_excluded_count: int
    environment_counts: Mapping[str, int]
    scene_count: int


@dataclass(frozen=True)
class CellCoverage:
    environment: str
    elevation_band: str
    path_count: int
    event_count: int
    scene_count: int
    support_status: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_bool(value: str, field_name: str, row_number: int) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError(f"row {row_number}: invalid boolean in {field_name}: {value!r}")


def _parse_float(value: str, field_name: str, row_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: invalid float in {field_name}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"row {row_number}: non-finite {field_name}")
    return number


def elevation_band_for(elevation_deg: float) -> str:
    if not math.isfinite(elevation_deg) or elevation_deg < 0.0 or elevation_deg > 90.0:
        raise ValueError(f"elevation outside [0, 90]: {elevation_deg}")
    for band, (lower, upper, inclusive_upper) in _BAND_LIMITS.items():
        if lower <= elevation_deg < upper or (
            inclusive_upper and lower <= elevation_deg <= upper
        ):
            return band
    raise ValueError(f"elevation cannot be assigned to a band: {elevation_deg}")


def load_path_observations(
    project_root: Path, config: FitConfig
) -> tuple[list[PathObservation], SourceAudit]:
    """Read only the frozen Stage4 path partition and enforce its eligibility contract."""

    source_path = project_root / Path(config.source_relative_path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    actual_hash = _sha256(source_path)
    if actual_hash.lower() != config.source_sha256.lower():
        raise ValueError(
            f"source SHA-256 mismatch: expected {config.source_sha256}, got {actual_hash}"
        )

    required_columns = {
        "event_path_id",
        "event_id",
        "run_id",
        "scene_id",
        "prn",
        "tracking_channel",
        "estimate_stage",
        "path_role",
        "is_multipath",
        "label_value",
        "environment_class",
        "elevation_deg",
        "elevation_band",
        "geometry_join_valid",
        "environment_modeling_ready",
        "elevation_modeling_ready",
        "excess_delay_s",
        "relative_doppler_hz",
        "relative_power_db",
        "source_file",
        "source_file_sha256",
        "source_row_number",
    }
    observations: list[PathObservation] = []
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        missing = required_columns - columns
        if missing:
            raise ValueError(f"source is missing required columns: {sorted(missing)}")
        for source_row_number, raw in enumerate(reader, start=2):
            environment = str(raw["environment_class"]).strip()
            if environment not in config.environments:
                raise ValueError(f"row {source_row_number}: unknown environment {environment!r}")
            environment_ready = _parse_bool(
                raw["environment_modeling_ready"], "environment_modeling_ready", source_row_number
            )
            if not environment_ready:
                raise ValueError(f"row {source_row_number}: environment-modeling-ineligible row")
            if str(raw["estimate_stage"]).strip() != "stage4_joint":
                raise ValueError(f"row {source_row_number}: non-Stage4 row")
            if str(raw["path_role"]).strip() != "multipath":
                raise ValueError(f"row {source_row_number}: non-multipath row")
            if not _parse_bool(raw["is_multipath"], "is_multipath", source_row_number):
                raise ValueError(f"row {source_row_number}: is_multipath is not true")
            if str(raw["label_value"]).strip() != "confirmed_multipath":
                raise ValueError(f"row {source_row_number}: non-confirmed label")
            geometry_valid = _parse_bool(
                raw["geometry_join_valid"], "geometry_join_valid", source_row_number
            )
            elevation_ready = _parse_bool(
                raw["elevation_modeling_ready"], "elevation_modeling_ready", source_row_number
            )
            elevation_text = str(raw["elevation_deg"]).strip()
            elevation = (
                _parse_float(elevation_text, "elevation_deg", source_row_number)
                if elevation_text
                else None
            )
            source_band = str(raw["elevation_band"]).strip() or None
            if elevation_ready:
                if not geometry_valid or elevation is None:
                    raise ValueError(
                        f"row {source_row_number}: elevation-ready row lacks valid geometry/elevation"
                    )
                calculated_band = elevation_band_for(elevation)
                if source_band != calculated_band:
                    raise ValueError(
                        f"row {source_row_number}: elevation band mismatch "
                        f"{source_band!r} != {calculated_band!r}"
                    )
                elevation_band = calculated_band
            else:
                if source_band is not None:
                    raise ValueError(
                        f"row {source_row_number}: ineligible row has an elevation band"
                    )
                elevation_band = None
            delay = _parse_float(raw["excess_delay_s"], "excess_delay_s", source_row_number)
            doppler = _parse_float(
                raw["relative_doppler_hz"], "relative_doppler_hz", source_row_number
            )
            power = _parse_float(
                raw["relative_power_db"], "relative_power_db", source_row_number
            )
            if delay <= 0.0:
                raise ValueError(f"row {source_row_number}: NLOS delay must be positive")
            observations.append(
                PathObservation(
                    event_path_id=str(raw["event_path_id"]),
                    event_id=str(raw["event_id"]),
                    run_id=str(raw["run_id"]),
                    scene_id=str(raw["scene_id"]),
                    prn=str(raw["prn"]),
                    tracking_channel=str(raw["tracking_channel"]),
                    environment=environment,
                    elevation_deg=elevation,
                    elevation_band=elevation_band,
                    geometry_join_valid=geometry_valid,
                    environment_modeling_ready=environment_ready,
                    elevation_modeling_ready=elevation_ready,
                    estimate_stage=str(raw["estimate_stage"]),
                    path_role=str(raw["path_role"]),
                    is_multipath=True,
                    label_value=str(raw["label_value"]),
                    excess_delay_s=delay,
                    relative_doppler_hz=doppler,
                    relative_power_db=power,
                    source_file=str(raw["source_file"]),
                    source_file_sha256=str(raw["source_file_sha256"]),
                    source_row_number=int(raw["source_row_number"]),
                )
            )

    environment_counts = {
        environment: sum(row.environment == environment for row in observations)
        for environment in config.environments
    }
    elevation_ready_count = sum(row.elevation_band is not None for row in observations)
    audit = SourceAudit(
        source_path=str(source_path),
        source_sha256=actual_hash,
        source_row_count=len(observations),
        environment_ready_count=len(observations),
        elevation_ready_count=elevation_ready_count,
        elevation_excluded_count=len(observations) - elevation_ready_count,
        environment_counts=environment_counts,
        scene_count=len({row.scene_id for row in observations}),
    )
    expected = {
        "environment_ready_count": 100,
        "elevation_ready_count": 84,
        "elevation_excluded_count": 16,
    }
    for field_name, expected_value in expected.items():
        if getattr(audit, field_name) != expected_value:
            raise ValueError(
                f"frozen source count mismatch for {field_name}: "
                f"expected {expected_value}, got {getattr(audit, field_name)}"
            )
    return observations, audit


def build_cell_coverage(observations: Sequence[PathObservation]) -> list[CellCoverage]:
    """Return all 12 cells; geometry-ineligible rows never enter a cell."""

    coverage: list[CellCoverage] = []
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            rows = [
                row
                for row in observations
                if row.environment == environment and row.elevation_band == band
            ]
            coverage.append(
                CellCoverage(
                    environment=environment,
                    elevation_band=band,
                    path_count=len(rows),
                    event_count=len({row.event_id for row in rows}),
                    scene_count=len({row.scene_id for row in rows}),
                    support_status=classify_support(
                        len(rows), len({row.scene_id for row in rows})
                    ),
                )
            )
    return coverage


def classify_support(path_count: int, scene_count: int) -> str:
    if path_count == 0:
        return "PRIOR_ONLY"
    if 1 <= path_count <= 2:
        return "PRIOR_DOMINANT"
    if 3 <= path_count < 10:
        return "SPARSE_PARTIAL_POOLING"
    if path_count >= 10 and scene_count >= 2:
        return "DATA_SUPPORTED_WITH_GROUPED_VALIDATION"
    return "SPARSE_PARTIAL_POOLING"


def to_model_vector(observation: PathObservation) -> ModelVector:
    return ModelVector(
        event_path_id=observation.event_path_id,
        event_id=observation.event_id,
        run_id=observation.run_id,
        scene_id=observation.scene_id,
        environment=observation.environment,
        elevation_band=observation.elevation_band,
        relative_delay_ns=observation.excess_delay_s * 1e9,
        relative_doppler_hz=observation.relative_doppler_hz,
        relative_power_db=observation.relative_power_db,
    )


def relative_power_db_to_amplitude(values: np.ndarray | Sequence[float]) -> np.ndarray:
    values_array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(values_array)):
        raise ValueError("relative power contains non-finite values")
    return np.power(10.0, values_array / 20.0)


@dataclass(frozen=True)
class PathDraw:
    relative_delay_ns: float
    relative_doppler_hz: float
    relative_amplitude_linear: float


def model_draw_to_output(delay_ns: float, doppler_hz: float, power_db: float) -> PathDraw:
    if not all(math.isfinite(value) for value in (delay_ns, doppler_hz, power_db)):
        raise ValueError("model draw must be finite")
    if delay_ns <= 0.0:
        raise ValueError("NLOS delay draw must remain positive")
    return PathDraw(
        relative_delay_ns=float(delay_ns),
        relative_doppler_hz=float(doppler_hz),
        relative_amplitude_linear=float(relative_power_db_to_amplitude(np.array([power_db]))[0]),
    )


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(values * weights) / np.sum(weights))


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, probability: float) -> float:
    order = np.argsort(values, kind="mergesort")
    ordered_values = values[order]
    ordered_weights = weights[order]
    cumulative = np.cumsum(ordered_weights)
    target = probability * cumulative[-1]
    index = int(np.searchsorted(cumulative, target, side="left"))
    return float(ordered_values[min(index, len(ordered_values) - 1)])


@dataclass(frozen=True)
class FamilyFit:
    family: str
    parameters: Mapping[str, float]
    domain: str
    weighted_count: float
    objective: float


def _initial_parameters(values: np.ndarray, weights: np.ndarray, family: str) -> dict[str, float]:
    mean = _weighted_mean(values, weights)
    variance = _weighted_mean((values - mean) ** 2, weights)
    std = max(math.sqrt(max(variance, 0.0)), max(abs(mean) * 1e-6, 1e-9))
    if family == "lognormal":
        logs = np.log(values)
        log_mean = _weighted_mean(logs, weights)
        log_std = max(math.sqrt(max(_weighted_mean((logs - log_mean) ** 2, weights), 0.0)), 1e-6)
        return {"shape": log_std, "scale": math.exp(log_mean), "loc": 0.0}
    if family == "gamma":
        shape = max(mean * mean / max(variance, 1e-18), 1e-3)
        return {"shape": shape, "scale": max(variance / max(mean, 1e-18), 1e-12), "loc": 0.0}
    if family == "weibull":
        shape = 1.5
        scale = max(mean / math.gamma(1.0 + 1.0 / shape), 1e-12)
        return {"shape": shape, "scale": scale, "loc": 0.0}
    median = _weighted_quantile(values, weights, 0.5)
    if family == "normal":
        return {"loc": mean, "scale": std}
    if family == "laplace":
        scale = max(_weighted_mean(np.abs(values - median), weights), 1e-9)
        return {"loc": median, "scale": scale}
    if family == "student_t":
        mad = _weighted_quantile(np.abs(values - median), weights, 0.5)
        return {"df": 8.0, "loc": median, "scale": max(1.4826 * mad, std * 0.25, 1e-9)}
    raise ValueError(f"unsupported family: {family}")


def _family_logpdf(values: np.ndarray, family: str, parameters: Mapping[str, float]) -> np.ndarray:
    if family == "lognormal":
        return stats.lognorm.logpdf(values, parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "gamma":
        return stats.gamma.logpdf(values, parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "weibull":
        return stats.weibull_min.logpdf(values, parameters["shape"], loc=0.0, scale=parameters["scale"])
    if family == "normal":
        return stats.norm.logpdf(values, loc=parameters["loc"], scale=parameters["scale"])
    if family == "laplace":
        return stats.laplace.logpdf(values, loc=parameters["loc"], scale=parameters["scale"])
    if family == "student_t":
        return stats.t.logpdf(
            values,
            parameters["df"],
            loc=parameters["loc"],
            scale=parameters["scale"],
        )
    raise ValueError(f"unsupported family: {family}")


def fit_family(
    values: np.ndarray | Sequence[float],
    weights: np.ndarray | Sequence[float] | None,
    family: str,
    *,
    optimize_parameters: bool = True,
) -> FamilyFit:
    """Fit one frozen candidate family with deterministic weighted likelihood."""

    if family not in _ALLOWED_FAMILIES:
        raise ValueError(f"unsupported family: {family}")
    values_array = np.asarray(values, dtype=float).reshape(-1)
    if values_array.size == 0 or not np.all(np.isfinite(values_array)):
        raise ValueError("cannot fit an empty/non-finite sample")
    if family in {"lognormal", "gamma", "weibull"} and np.any(values_array <= 0.0):
        raise ValueError(f"{family} requires strictly positive values")
    if weights is None:
        weights_array = np.ones(values_array.size, dtype=float)
    else:
        weights_array = np.asarray(weights, dtype=float).reshape(-1)
        if weights_array.size != values_array.size:
            raise ValueError("weights and values have different lengths")
        if not np.all(np.isfinite(weights_array)) or np.any(weights_array <= 0.0):
            raise ValueError("weights must be finite and positive")
    initial = _initial_parameters(values_array, weights_array, family)

    if family in {"lognormal", "gamma", "weibull"}:
        names = ["shape", "scale"]
        initial_vector = np.array([initial["shape"], initial["scale"]], dtype=float)
        bounds = [(1e-5, 1e3), (1e-12, max(float(np.max(values_array)) * 1e4, 1e-6))]
        domain = "positive"
    elif family == "student_t":
        names = ["df", "loc", "scale"]
        initial_vector = np.array([initial["df"], initial["loc"], initial["scale"]], dtype=float)
        span = max(float(np.ptp(values_array)), initial["scale"], 1.0)
        bounds = [(2.1, 100.0), (float(np.min(values_array) - 10 * span), float(np.max(values_array) + 10 * span)), (1e-9, 100 * span)]
        domain = "real"
    else:
        names = ["loc", "scale"]
        initial_vector = np.array([initial["loc"], initial["scale"]], dtype=float)
        span = max(float(np.ptp(values_array)), initial["scale"], 1.0)
        bounds = [(float(np.min(values_array) - 10 * span), float(np.max(values_array) + 10 * span)), (1e-9, 100 * span)]
        domain = "real"

    def objective(vector: np.ndarray) -> float:
        candidate = dict(initial)
        candidate.update({name: float(value) for name, value in zip(names, vector)})
        logpdf = _family_logpdf(values_array, family, candidate)
        if not np.all(np.isfinite(logpdf)):
            return 1e300
        return float(-np.sum(weights_array * logpdf) / np.sum(weights_array))

    vector = initial_vector
    result_success = True
    if optimize_parameters:
        result = optimize.minimize(
            objective,
            initial_vector,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 300, "ftol": 1e-12, "gtol": 1e-8, "maxls": 40},
        )
        vector = result.x
        result_success = bool(result.success) and np.all(np.isfinite(vector))
        if not result_success:
            # A bounded optimizer can report a line-search warning at a valid
            # finite point.  Accept only a finite, evaluable point; otherwise
            # fail closed instead of silently omitting a candidate family.
            if not np.all(np.isfinite(vector)) or not math.isfinite(objective(vector)):
                raise ValueError(f"family optimization failed for {family}: {result.message}")
    parameters = dict(initial)
    parameters.update({name: float(value) for name, value in zip(names, vector)})
    if family == "student_t":
        parameters["df"] = min(max(parameters["df"], 2.1), 100.0)
    parameters["scale"] = max(parameters["scale"], 1e-12)
    final_objective = objective(np.array([parameters[name] for name in names], dtype=float))
    if not math.isfinite(final_objective):
        raise ValueError(f"non-finite fit objective for {family}")
    return FamilyFit(
        family=family,
        parameters=parameters,
        domain=domain,
        weighted_count=float(np.sum(weights_array)),
        objective=float(final_objective),
    )


def cdf(fit: FamilyFit, values: np.ndarray | Sequence[float]) -> np.ndarray:
    values_array = np.asarray(values, dtype=float)
    if fit.family == "lognormal":
        return stats.lognorm.cdf(values_array, fit.parameters["shape"], loc=0.0, scale=fit.parameters["scale"])
    if fit.family == "gamma":
        return stats.gamma.cdf(values_array, fit.parameters["shape"], loc=0.0, scale=fit.parameters["scale"])
    if fit.family == "weibull":
        return stats.weibull_min.cdf(values_array, fit.parameters["shape"], loc=0.0, scale=fit.parameters["scale"])
    if fit.family == "normal":
        return stats.norm.cdf(values_array, loc=fit.parameters["loc"], scale=fit.parameters["scale"])
    if fit.family == "laplace":
        return stats.laplace.cdf(values_array, loc=fit.parameters["loc"], scale=fit.parameters["scale"])
    if fit.family == "student_t":
        return stats.t.cdf(values_array, fit.parameters["df"], loc=fit.parameters["loc"], scale=fit.parameters["scale"])
    raise ValueError(f"unsupported family: {fit.family}")


def ppf(fit: FamilyFit, probabilities: np.ndarray | Sequence[float]) -> np.ndarray:
    probabilities_array = np.asarray(probabilities, dtype=float)
    if np.any((probabilities_array <= 0.0) | (probabilities_array >= 1.0)):
        raise ValueError("PPF probabilities must be strictly between 0 and 1")
    if fit.family == "lognormal":
        return stats.lognorm.ppf(probabilities_array, fit.parameters["shape"], loc=0.0, scale=fit.parameters["scale"])
    if fit.family == "gamma":
        return stats.gamma.ppf(probabilities_array, fit.parameters["shape"], loc=0.0, scale=fit.parameters["scale"])
    if fit.family == "weibull":
        return stats.weibull_min.ppf(probabilities_array, fit.parameters["shape"], loc=0.0, scale=fit.parameters["scale"])
    if fit.family == "normal":
        return stats.norm.ppf(probabilities_array, loc=fit.parameters["loc"], scale=fit.parameters["scale"])
    if fit.family == "laplace":
        return stats.laplace.ppf(probabilities_array, loc=fit.parameters["loc"], scale=fit.parameters["scale"])
    if fit.family == "student_t":
        return stats.t.ppf(probabilities_array, fit.parameters["df"], loc=fit.parameters["loc"], scale=fit.parameters["scale"])
    raise ValueError(f"unsupported family: {fit.family}")


@dataclass(frozen=True)
class FamilyScore:
    parameter: str
    family: str
    total_log_likelihood: float
    held_out_groups: frozenset[str]
    fold_log_likelihoods: Mapping[str, float]
    valid: bool
    failure: str | None = None


@dataclass(frozen=True)
class FamilySelection:
    parameter: str
    family: str
    total_log_likelihood: float
    candidate_scores: tuple[FamilyScore, ...]
    held_out_groups: frozenset[str]
    row_random_split_used: bool


def _vector_value(vector: ModelVector, parameter: str) -> float:
    if parameter not in FIT_PARAMETERS:
        raise ValueError(f"unsupported model parameter: {parameter}")
    return float(getattr(vector, parameter))


def _as_model_vectors(observations: Sequence[ModelObservation]) -> list[ModelVector]:
    return [to_model_vector(row) if isinstance(row, PathObservation) else row for row in observations]


ModelObservation = PathObservation | ModelVector


def score_family_by_scene(
    observations: Sequence[ModelObservation], parameter: str, family: str
) -> FamilyScore:
    vectors = _as_model_vectors(observations)
    groups = sorted({row.scene_id for row in vectors})
    folds: dict[str, float] = {}
    try:
        for held_out in groups:
            train = [row for row in vectors if row.scene_id != held_out]
            test = [row for row in vectors if row.scene_id == held_out]
            fit = fit_family(
                np.array([_vector_value(row, parameter) for row in train]),
                None,
                family,
            )
            test_values = np.array([_vector_value(row, parameter) for row in test])
            logpdf = _family_logpdf(test_values, family, fit.parameters)
            if not np.all(np.isfinite(logpdf)):
                raise ValueError(f"non-finite held-out likelihood for scene {held_out}")
            folds[held_out] = float(np.sum(logpdf))
        total = float(sum(folds.values()))
        return FamilyScore(
            parameter=parameter,
            family=family,
            total_log_likelihood=total,
            held_out_groups=frozenset(groups),
            fold_log_likelihoods=folds,
            valid=True,
        )
    except (ValueError, FloatingPointError) as exc:
        return FamilyScore(
            parameter=parameter,
            family=family,
            total_log_likelihood=float("-inf"),
            held_out_groups=frozenset(groups),
            fold_log_likelihoods=folds,
            valid=False,
            failure=str(exc),
        )


def select_global_family(
    observations: Sequence[ModelObservation],
    parameter: str,
    candidates: Sequence[str],
) -> FamilySelection:
    if not observations:
        raise ValueError("cannot select a family from no observations")
    scores = tuple(score_family_by_scene(observations, parameter, family) for family in candidates)
    valid_scores = [score for score in scores if score.valid]
    if not valid_scores:
        raise ValueError(f"all candidate families failed for {parameter}")
    best = valid_scores[0]
    tie_tolerance = 1e-9
    for score in valid_scores[1:]:
        if score.total_log_likelihood > best.total_log_likelihood + tie_tolerance:
            best = score
    return FamilySelection(
        parameter=parameter,
        family=best.family,
        total_log_likelihood=best.total_log_likelihood,
        candidate_scores=scores,
        held_out_groups=best.held_out_groups,
        row_random_split_used=False,
    )


@dataclass(frozen=True)
class MarginalModel:
    parameter: str
    family: str
    fit: FamilyFit
    support_status: str
    parameter_source: str
    direct_path_count: int
    direct_scene_count: int
    local_likelihood_row_count: int
    pseudo_observation_weight: float
    parent_scope: str | None


@dataclass(frozen=True)
class HierarchicalMarginalResult:
    global_models: Mapping[str, MarginalModel]
    environment_models: Mapping[tuple[str, str], MarginalModel]
    cell_models: Mapping[tuple[str, str, str], MarginalModel]

    def cell(self, environment: str, elevation_band: str, parameter: str) -> MarginalModel:
        return self.cell_models[(environment, elevation_band, parameter)]


def parent_quantiles(fit: FamilyFit, count: int) -> np.ndarray:
    if count <= 0:
        raise ValueError("quantile count must be positive")
    probabilities = (np.arange(count, dtype=float) + 0.5) / count
    values = ppf(fit, probabilities)
    if not np.all(np.isfinite(values)):
        raise ValueError("parent quantiles are non-finite")
    return values


def _fit_with_parent(
    values: Sequence[float],
    parent_fit: FamilyFit,
    config: FitConfig,
) -> FamilyFit:
    local = np.asarray(values, dtype=float)
    prior = parent_quantiles(parent_fit, config.parent_quantile_count)
    combined = np.concatenate([local, prior])
    weights = np.concatenate(
        [np.ones(local.size, dtype=float), np.full(prior.size, config.prior_equivalent_weight / config.parent_quantile_count)]
    )
    return fit_family(combined, weights, parent_fit.family)


def fit_hierarchical_marginals(
    observations: Sequence[ModelObservation],
    selections: Mapping[str, FamilySelection],
    config: FitConfig,
) -> HierarchicalMarginalResult:
    vectors = _as_model_vectors(observations)
    global_models: dict[str, MarginalModel] = {}
    environment_models: dict[tuple[str, str], MarginalModel] = {}
    cell_models: dict[tuple[str, str, str], MarginalModel] = {}
    for parameter in FIT_PARAMETERS:
        if parameter not in selections:
            raise ValueError(f"missing family selection for {parameter}")
        family = selections[parameter].family
        global_fit = fit_family(
            np.array([_vector_value(row, parameter) for row in vectors]), None, family
        )
        global_models[parameter] = MarginalModel(
            parameter=parameter,
            family=family,
            fit=global_fit,
            support_status="DATA_SUPPORTED_WITH_GROUPED_VALIDATION",
            parameter_source="global_environment_ready_paths",
            direct_path_count=len(vectors),
            direct_scene_count=len({row.scene_id for row in vectors}),
            local_likelihood_row_count=len(vectors),
            pseudo_observation_weight=0.0,
            parent_scope=None,
        )
        for environment in config.environments:
            env_rows = [row for row in vectors if row.environment == environment]
            env_values = np.array([_vector_value(row, parameter) for row in env_rows])
            env_fit = _fit_with_parent(env_values, global_fit, config)
            environment_models[(environment, parameter)] = MarginalModel(
                parameter=parameter,
                family=family,
                fit=env_fit,
                support_status=(
                    "DATA_SUPPORTED_WITH_GROUPED_VALIDATION"
                    if len(env_rows) >= 10 and len({row.scene_id for row in env_rows}) >= 2
                    else "SPARSE_PARTIAL_POOLING"
                ),
                parameter_source="environment_local_plus_global_parent",
                direct_path_count=len(env_rows),
                direct_scene_count=len({row.scene_id for row in env_rows}),
                local_likelihood_row_count=len(env_rows),
                pseudo_observation_weight=config.prior_equivalent_weight,
                parent_scope="global",
            )
            for band in config.elevation_bands:
                cell_rows = [
                    row
                    for row in env_rows
                    if row.elevation_band == band
                ]
                cell_values = np.array([_vector_value(row, parameter) for row in cell_rows])
                if len(cell_rows) == 0:
                    cell_fit = env_fit
                    source = "environment_parent_only"
                    status = "PRIOR_ONLY"
                else:
                    cell_fit = _fit_with_parent(cell_values, env_fit, config)
                    source = "cell_local_plus_environment_parent"
                    status = classify_support(
                        len(cell_rows), len({row.scene_id for row in cell_rows})
                    )
                cell_models[(environment, band, parameter)] = MarginalModel(
                    parameter=parameter,
                    family=family,
                    fit=cell_fit,
                    support_status=status,
                    parameter_source=source,
                    direct_path_count=len(cell_rows),
                    direct_scene_count=len({row.scene_id for row in cell_rows}),
                    local_likelihood_row_count=len(cell_rows),
                    pseudo_observation_weight=(
                        0.0 if len(cell_rows) == 0 else config.prior_equivalent_weight
                    ),
                    parent_scope="environment",
                )
    return HierarchicalMarginalResult(
        global_models=global_models,
        environment_models=environment_models,
        cell_models=cell_models,
    )


def nearest_correlation(
    matrix: np.ndarray | Sequence[Sequence[float]], eigenvalue_floor: float = 1e-6
) -> tuple[np.ndarray, float]:
    matrix_array = np.asarray(matrix, dtype=float)
    if matrix_array.ndim != 2 or matrix_array.shape[0] != matrix_array.shape[1]:
        raise ValueError("correlation matrix must be square")
    if not np.all(np.isfinite(matrix_array)):
        raise ValueError("correlation matrix must be finite")
    symmetric = (matrix_array + matrix_array.T) / 2.0
    diagonal = np.sqrt(np.maximum(np.diag(symmetric), 1e-12))
    symmetric = symmetric / np.outer(diagonal, diagonal)
    np.fill_diagonal(symmetric, 1.0)
    original = symmetric.copy()
    for _ in range(8):
        eigenvalues, eigenvectors = np.linalg.eigh((symmetric + symmetric.T) / 2.0)
        clipped = np.maximum(eigenvalues, eigenvalue_floor)
        symmetric = (eigenvectors * clipped) @ eigenvectors.T
        diagonal = np.sqrt(np.maximum(np.diag(symmetric), 1e-12))
        symmetric = symmetric / np.outer(diagonal, diagonal)
        np.fill_diagonal(symmetric, 1.0)
        if float(np.min(np.linalg.eigvalsh(symmetric))) >= eigenvalue_floor - 1e-12:
            break
    correction = float(np.linalg.norm(symmetric - original, ord="fro"))
    return symmetric, correction


@dataclass(frozen=True)
class CopulaModel:
    parameter_order: tuple[str, ...]
    correlation: np.ndarray
    n_observations: int
    shrinkage_weight: float
    correction_frobenius_norm: float
    source_scope: str


def _copula_from_values(values: np.ndarray, eigenvalue_floor: float, source_scope: str) -> CopulaModel:
    if values.ndim != 2 or values.shape[1] != len(FIT_PARAMETERS):
        raise ValueError("copula values must have three parameter columns")
    if values.shape[0] < 2:
        raw = np.eye(values.shape[1])
    else:
        ranks = np.column_stack(
            [stats.rankdata(values[:, column], method="average") for column in range(values.shape[1])]
        )
        raw_spearman = np.corrcoef(ranks, rowvar=False)
        raw_spearman = np.nan_to_num(raw_spearman, nan=0.0)
        np.fill_diagonal(raw_spearman, 1.0)
        raw = 2.0 * np.sin(np.pi * raw_spearman / 6.0)
        np.fill_diagonal(raw, 1.0)
    projected, correction = nearest_correlation(raw, eigenvalue_floor)
    return CopulaModel(
        parameter_order=FIT_PARAMETERS,
        correlation=projected,
        n_observations=int(values.shape[0]),
        shrinkage_weight=1.0,
        correction_frobenius_norm=correction,
        source_scope=source_scope,
    )


def fit_global_copula(observations: Sequence[ModelObservation], eigenvalue_floor: float) -> CopulaModel:
    vectors = _as_model_vectors(observations)
    values = np.column_stack(
        [[_vector_value(row, parameter) for row in vectors] for parameter in FIT_PARAMETERS]
    )
    return _copula_from_values(values, eigenvalue_floor, "global_environment_ready_paths")


def fit_environment_copulas(
    observations: Sequence[ModelObservation],
    global_copula: CopulaModel,
    config: FitConfig,
) -> dict[str, CopulaModel]:
    vectors = _as_model_vectors(observations)
    result: dict[str, CopulaModel] = {}
    for environment in config.environments:
        rows = [row for row in vectors if row.environment == environment]
        values = np.column_stack(
            [[_vector_value(row, parameter) for row in rows] for parameter in FIT_PARAMETERS]
        )
        local = _copula_from_values(values, config.copula_eigenvalue_floor, f"environment:{environment}")
        weight = len(rows) / (len(rows) + config.copula_shrinkage_denominator)
        blended = weight * local.correlation + (1.0 - weight) * global_copula.correlation
        correlation, correction = nearest_correlation(blended, config.copula_eigenvalue_floor)
        result[environment] = CopulaModel(
            parameter_order=FIT_PARAMETERS,
            correlation=correlation,
            n_observations=len(rows),
            shrinkage_weight=float(weight),
            correction_frobenius_norm=float(correction),
            source_scope=f"environment:{environment}_shrunk_to_global",
        )
    return result


def sample_cell(
    environment: str,
    elevation_band: str,
    marginals: HierarchicalMarginalResult,
    environment_copulas: Mapping[str, CopulaModel],
    size: int,
    rng: np.random.Generator,
    *,
    antithetic: bool = False,
) -> dict[str, np.ndarray]:
    if size <= 0:
        raise ValueError("sample size must be positive")
    copula = environment_copulas[environment]
    latent = gaussian_copula_latent(copula, size, rng, antithetic=antithetic)
    return transform_latent_to_cell(
        latent, environment, elevation_band, marginals, environment_copulas
    )


def gaussian_copula_latent(
    copula: CopulaModel,
    size: int,
    rng: np.random.Generator,
    *,
    antithetic: bool = False,
) -> np.ndarray:
    if size <= 0:
        raise ValueError("sample size must be positive")
    if antithetic and size >= 2:
        half_size = (size + 1) // 2
        half = rng.standard_normal((half_size, 3))
        base = np.vstack([half, -half])[:size]
        # Whiten the deterministic finite sample and recolor it with the
        # assigned copula.  This keeps the QA draw reproducible while making
        # the finite-sample covariance check a diagnostic of the stored
        # correlation, rather than an accidental seed fluctuation.
        base = base - np.mean(base, axis=0, keepdims=True)
        sample_covariance = (base.T @ base) / max(size - 1, 1)
        eigenvalues, eigenvectors = np.linalg.eigh(sample_covariance)
        inverse_sqrt = eigenvectors @ np.diag(1.0 / np.sqrt(np.maximum(eigenvalues, 1e-12))) @ eigenvectors.T
        whitened = base @ inverse_sqrt
        cholesky = np.linalg.cholesky(copula.correlation)
        return whitened @ cholesky.T
    return rng.multivariate_normal(np.zeros(3), copula.correlation, size=size, method="eigh")


def transform_latent_to_cell(
    latent: np.ndarray,
    environment: str,
    elevation_band: str,
    marginals: HierarchicalMarginalResult,
    environment_copulas: Mapping[str, CopulaModel],
) -> dict[str, np.ndarray]:
    if latent.ndim != 2 or latent.shape[1] != len(FIT_PARAMETERS):
        raise ValueError("latent sample must have three columns")
    probabilities = stats.norm.cdf(latent)
    draws: dict[str, np.ndarray] = {}
    for column, parameter in enumerate(FIT_PARAMETERS):
        model = marginals.cell(environment, elevation_band, parameter)
        draws[parameter] = ppf(model.fit, probabilities[:, column])
    draws["relative_amplitude_linear"] = relative_power_db_to_amplitude(draws["relative_power_db"])
    return draws


def bootstrap_global_summary(
    observations: Sequence[ModelObservation],
    selections: Mapping[str, FamilySelection],
    config: FitConfig,
) -> list[dict[str, Any]]:
    """Scene-block bootstrap for global fitted parameters and key quantiles.

    The family is frozen before this routine is called.  Bootstrap resampling is
    by complete scene blocks; no gold labels or event positions are consulted.
    A deterministic closed-form/initial estimator is used inside each replicate
    to keep the uncertainty diagnostic bounded and reproducible.
    """

    vectors = _as_model_vectors(observations)
    scene_groups = {
        scene: [row for row in vectors if row.scene_id == scene]
        for scene in sorted({row.scene_id for row in vectors})
    }
    scenes = tuple(sorted(scene_groups))
    rng = np.random.default_rng(config.bootstrap_seed)
    records: list[dict[str, Any]] = []
    scalar_values: dict[tuple[str, str], list[float]] = {}
    quantile_values: dict[tuple[str, float], list[float]] = {}
    for _replicate in range(config.bootstrap_replicates):
        selected_scenes = rng.choice(scenes, size=len(scenes), replace=True)
        sample_rows = [row for scene in selected_scenes for row in scene_groups[str(scene)]]
        for parameter in FIT_PARAMETERS:
            family = selections[parameter].family
            values = np.array([_vector_value(row, parameter) for row in sample_rows])
            fit = fit_family(values, None, family, optimize_parameters=False)
            for name, value in fit.parameters.items():
                scalar_values.setdefault((parameter, name), []).append(float(value))
            for probability in (0.025, 0.5, 0.975):
                quantile_values.setdefault((parameter, probability), []).append(
                    float(ppf(fit, np.array([probability]))[0])
                )
    for (parameter, name), values in sorted(scalar_values.items()):
        lower, median, upper = np.quantile(np.asarray(values), [0.025, 0.5, 0.975])
        records.append(
            {
                "scope": "global",
                "parameter": parameter,
                "metric": f"fit_parameter:{name}",
                "lower_2_5": float(lower),
                "median_50": float(median),
                "upper_97_5": float(upper),
                "bootstrap_replicates": config.bootstrap_replicates,
                "bootstrap_seed": config.bootstrap_seed,
            }
        )
    for (parameter, probability), values in sorted(quantile_values.items()):
        lower, median, upper = np.quantile(np.asarray(values), [0.025, 0.5, 0.975])
        records.append(
            {
                "scope": "global",
                "parameter": parameter,
                "metric": f"model_quantile:{probability:.3f}",
                "lower_2_5": float(lower),
                "median_50": float(median),
                "upper_97_5": float(upper),
                "bootstrap_replicates": config.bootstrap_replicates,
                "bootstrap_seed": config.bootstrap_seed,
            }
        )
    return records


__all__ = [
    "ENVIRONMENTS",
    "ELEVATION_BANDS",
    "FIT_PARAMETERS",
    "OUTPUT_PARAMETERS",
    "CellCoverage",
    "CopulaModel",
    "FamilyFit",
    "FamilyScore",
    "FamilySelection",
    "FitConfig",
    "HierarchicalMarginalResult",
    "MarginalModel",
    "ModelVector",
    "PathDraw",
    "PathObservation",
    "SourceAudit",
    "bootstrap_global_summary",
    "build_cell_coverage",
    "cdf",
    "classify_support",
    "elevation_band_for",
    "fit_environment_copulas",
    "fit_family",
    "fit_global_copula",
    "fit_hierarchical_marginals",
    "gaussian_copula_latent",
    "load_frozen_config",
    "load_path_observations",
    "model_draw_to_output",
    "nearest_correlation",
    "parent_quantiles",
    "ppf",
    "relative_power_db_to_amplitude",
    "sample_cell",
    "transform_latent_to_cell",
    "score_family_by_scene",
    "select_global_family",
    "to_model_vector",
]
