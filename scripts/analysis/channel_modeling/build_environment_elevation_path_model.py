"""Build the v1 environment x elevation conditional NLOS path model.

The builder is intentionally separate from the SAGE pipeline.  Its only data
input is the frozen Stage4-confirmed path-parameter partition; it never opens
raw IQ, tracking files, MATLAB files, or SAGE result files directly.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import json
import math
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np

from scripts.analysis.channel_modeling.path_distribution_core import (
    ENVIRONMENTS,
    ELEVATION_BANDS,
    FIT_PARAMETERS,
    CellCoverage,
    FitConfig,
    HierarchicalMarginalResult,
    ModelVector,
    bootstrap_global_summary,
    build_cell_coverage,
    cdf,
    fit_environment_copulas,
    fit_global_copula,
    fit_hierarchical_marginals,
    gaussian_copula_latent,
    load_frozen_config,
    load_path_observations,
    ppf,
    sample_cell,
    select_global_family,
    to_model_vector,
)
from scipy import stats


REQUIRED_OUTPUT_FILES: tuple[str, ...] = (
    "source_path_audit.csv",
    "cell_coverage.csv",
    "marginal_family_selection.csv",
    "global_environment_marginals.csv",
    "cell_distribution_parameters.csv",
    "environment_copula_parameters.csv",
    "cell_model_index.csv",
    "bootstrap_uncertainty.csv",
    "fit_diagnostics.csv",
    "sampling_contract.json",
    "model_manifest.json",
    "model_report.md",
    "build_receipt.json",
)


@dataclass(frozen=True)
class BuildReceipt:
    status: str
    output_dir: str
    model_manifest_sha256: str
    source_sha256: str
    config_sha256: str
    selected_families: Mapping[str, str]
    source_counts: Mapping[str, int]
    execution_policy: Mapping[str, Any]
    output_files: tuple[str, ...]
    output_hashes: Mapping[str, str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        _canonical(path).relative_to(_canonical(root))
        return True
    except ValueError:
        return False


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False, default=_json_default)
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _backend_receipt() -> dict[str, Any]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            np.show_config()
        except AttributeError:
            np.__config__.show()
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "numpy_version": np.__version__,
        "scipy_version": stats.__version__ if hasattr(stats, "__version__") else __import__("scipy").__version__,
        "numpy_show_config": output.getvalue(),
    }


def _validate_execution_policy(config: FitConfig) -> None:
    policy = config.execution_policy
    required_false = ("raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz")
    for field in required_false:
        if policy.get(field) is not False:
            raise ValueError(f"execution policy must keep {field}=false")
    if policy.get("gold_labels_used_for_selection") is not False:
        raise ValueError("gold_labels_used_for_selection must be false")
    if policy.get("posterior_gold_used_for_selection") is not False:
        raise ValueError("posterior_gold_used_for_selection must be false")
    if policy.get("new_only") is not True or policy.get("resume_allowed") is not False:
        raise ValueError("model output must be new-only and non-resumable")


def preflight(
    project_root: Path,
    config_path: Path,
    output_dir: Path,
    *,
    allow_test_namespace: bool = False,
) -> dict[str, Any]:
    """Perform read-only checks; this function never creates the output directory."""

    root = _canonical(project_root)
    config_file = _canonical(config_path)
    target = _canonical(output_dir)
    if not root.is_dir():
        raise FileNotFoundError(root)
    if not config_file.is_file():
        raise FileNotFoundError(config_file)
    if target.exists():
        raise FileExistsError(f"new-only output already exists: {target}")
    if not _is_within(target, root) and not allow_test_namespace:
        raise ValueError("output must remain inside the project root")
    relative_parts = {part.lower() for part in target.relative_to(root).parts} if _is_within(target, root) else set()
    if "scenes" in relative_parts or "sage_results" in relative_parts:
        raise ValueError("model output may not be placed under scenes or sage_results")
    if not allow_test_namespace and (
        "dataset_generation_logs" not in relative_parts or "channel_modeling" not in relative_parts
    ):
        raise ValueError("model output must be under dataset_generation_logs/channel_modeling")
    config = load_frozen_config(config_file)
    _validate_execution_policy(config)
    source = root / Path(config.source_relative_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    source_hash = _sha256(source)
    if source_hash.lower() != config.source_sha256.lower():
        raise ValueError(f"source hash mismatch: expected {config.source_sha256}, got {source_hash}")
    protected = root / Path(str(config.protected_source["pipeline_relative_path"]))
    protected_hash = _sha256(protected)
    if protected_hash.lower() != str(config.protected_source["pipeline_sha256"]).lower():
        raise ValueError(
            f"protected pipeline hash mismatch: expected {config.protected_source['pipeline_sha256']}, got {protected_hash}"
        )
    observations, audit = load_path_observations(root, config)
    coverage = build_cell_coverage(observations)
    return {
        "project_root": str(root),
        "config_path": str(config_file),
        "config_sha256": _sha256(config_file),
        "output_dir": str(target),
        "output_exists": False,
        "source_path": audit.source_path,
        "source_sha256": audit.source_sha256,
        "source_counts": {
            "environment_ready_paths": audit.environment_ready_count,
            "elevation_ready_paths": audit.elevation_ready_count,
            "elevation_excluded_paths": audit.elevation_excluded_count,
        },
        "scene_count": audit.scene_count,
        "cell_coverage": [asdict(row) for row in coverage],
        "execution_policy": dict(config.execution_policy),
        "backend": _backend_receipt(),
        "protected_pipeline_sha256": protected_hash,
    }


def _family_selection_rows(selections: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for parameter in FIT_PARAMETERS:
        selection = selections[parameter]
        for score in selection.candidate_scores:
            rows.append(
                {
                    "parameter": parameter,
                    "candidate_family": score.family,
                    "selected": score.family == selection.family,
                    "valid": score.valid,
                    "total_held_out_log_likelihood": score.total_log_likelihood,
                    "held_out_scene_count": len(score.held_out_groups),
                    "held_out_scenes": ";".join(sorted(score.held_out_groups)),
                    "fold_log_likelihood_json": json.dumps(dict(sorted(score.fold_log_likelihoods.items())), sort_keys=True),
                    "failure": score.failure or "",
                    "row_random_split_used": selection.row_random_split_used,
                }
            )
    return rows


def _marginal_row(scope: str, scope_id: str, model: Any) -> dict[str, Any]:
    parameters = {name: float(value) for name, value in model.fit.parameters.items()}
    return {
        "scope": scope,
        "scope_id": scope_id,
        "parameter": model.parameter,
        "family": model.family,
        "fit_parameters_json": json.dumps(parameters, sort_keys=True),
        "support_status": model.support_status,
        "parameter_source": model.parameter_source,
        "direct_path_count": model.direct_path_count,
        "direct_scene_count": model.direct_scene_count,
        "local_likelihood_row_count": model.local_likelihood_row_count,
        "pseudo_observation_weight": model.pseudo_observation_weight,
        "parent_scope": model.parent_scope or "",
        "fit_objective": model.fit.objective,
    }


def _cell_parameter_rows(marginals: HierarchicalMarginalResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            cell_id = f"{environment}__{band}"
            for parameter in FIT_PARAMETERS:
                rows.append(_marginal_row("cell", cell_id, marginals.cell(environment, band, parameter)))
    return rows


def _copula_row(scope: str, environment: str, copula: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "scope": scope,
        "environment": environment,
        "n_observations": copula.n_observations,
        "shrinkage_weight": copula.shrinkage_weight,
        "correction_frobenius_norm": copula.correction_frobenius_norm,
        "source_scope": copula.source_scope,
    }
    for i, left in enumerate(FIT_PARAMETERS):
        for j, right in enumerate(FIT_PARAMETERS):
            row[f"corr__{left}__{right}"] = float(copula.correlation[i, j])
    return row


def _predictive_diagnostics(
    marginals: HierarchicalMarginalResult,
    environment_copulas: Mapping[str, Any],
    config: FitConfig,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, environment in enumerate(ENVIRONMENTS):
        copula = environment_copulas[environment]
        for band_index, band in enumerate(ELEVATION_BANDS):
            seed = config.qa_draw_seed + index * len(ELEVATION_BANDS) + band_index
            latent_rng = np.random.default_rng(seed)
            latent = gaussian_copula_latent(
                copula,
                config.qa_draw_count,
                latent_rng,
                antithetic=True,
            )
            draws = sample_cell(
                environment,
                band,
                marginals,
                environment_copulas,
                config.qa_draw_count,
                np.random.default_rng(seed),
                antithetic=True,
            )
            values = np.column_stack([draws[parameter] for parameter in FIT_PARAMETERS])
            # The assigned Gaussian-copula correlation is checked in the
            # latent Gaussian space, before nonlinear marginal transforms.
            sample_corr = np.corrcoef(latent, rowvar=False)
            correlation_delta = float(np.max(np.abs(sample_corr - copula.correlation)))
            round_trip_errors = []
            for parameter in FIT_PARAMETERS:
                model = marginals.cell(environment, band, parameter)
                probabilities = np.array([0.025, 0.5, 0.975])
                round_trip_errors.append(
                    float(np.max(np.abs(cdf(model.fit, ppf(model.fit, probabilities)) - probabilities)))
                )
            rows.append(
                {
                    "environment": environment,
                    "elevation_band": band,
                    "cell_id": f"{environment}__{band}",
                    "support_status": marginals.cell(environment, band, FIT_PARAMETERS[0]).support_status,
                    "qa_seed": seed,
                    "qa_draw_count": config.qa_draw_count,
                    "finite_rate": float(np.mean(np.isfinite(values))),
                    "positive_delay_rate": float(np.mean(draws["relative_delay_ns"] > 0.0)),
                    "positive_amplitude_rate": float(np.mean(draws["relative_amplitude_linear"] > 0.0)),
                    "max_copula_abs_corr_delta": correlation_delta,
                    "max_marginal_cdf_ppf_error": max(round_trip_errors),
                    "diagnostic_status": "PASS"
                    if correlation_delta <= 0.05 and max(round_trip_errors) <= 1e-8
                    else "FAIL",
                }
            )
    return rows


def _source_audit_rows(observations: Sequence[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation in observations:
        vector = to_model_vector(observation)
        rows.append(
            {
                "source_row_number": observation.source_row_number,
                "event_path_id": observation.event_path_id,
                "event_id": observation.event_id,
                "run_id": observation.run_id,
                "scene_id": observation.scene_id,
                "prn": observation.prn,
                "tracking_channel": observation.tracking_channel,
                "environment": observation.environment,
                "elevation_deg": observation.elevation_deg if observation.elevation_deg is not None else "",
                "elevation_band": observation.elevation_band or "",
                "geometry_join_valid": observation.geometry_join_valid,
                "elevation_modeling_ready": observation.elevation_modeling_ready,
                "relative_delay_ns": vector.relative_delay_ns,
                "relative_doppler_hz": vector.relative_doppler_hz,
                "relative_power_db": vector.relative_power_db,
                "relative_amplitude_linear": float(10.0 ** (vector.relative_power_db / 20.0)),
                "source_file": observation.source_file,
                "source_file_sha256": observation.source_file_sha256,
            }
        )
    return rows


def _cell_index_rows(
    marginals: HierarchicalMarginalResult,
    coverage: Sequence[CellCoverage],
) -> list[dict[str, Any]]:
    coverage_by_key = {(row.environment, row.elevation_band): row for row in coverage}
    rows: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            current = coverage_by_key[(environment, band)]
            rows.append(
                {
                    "cell_id": f"{environment}__{band}",
                    "environment": environment,
                    "elevation_band": band,
                    "path_count": current.path_count,
                    "event_count": current.event_count,
                    "scene_count": current.scene_count,
                    "support_status": current.support_status,
                    "delay_model_id": f"{environment}__{band}__relative_delay_ns",
                    "doppler_model_id": f"{environment}__{band}__relative_doppler_hz",
                    "power_model_id": f"{environment}__{band}__relative_power_db",
                    "copula_scope": f"environment:{environment}",
                    "joint_sampling_scope": "environment_copula_plus_cell_marginals",
                }
            )
    return rows


def _sampling_contract(config: FitConfig) -> dict[str, Any]:
    return {
        "contract_version": "environment-elevation-path-sampling-contract-v1",
        "model_id": config.model_id,
        "cell_key": ["environment_class", "elevation_band"],
        "fit_parameters": list(FIT_PARAMETERS),
        "output_quantities": {
            "relative_delay_ns": "positive excess delay in nanoseconds",
            "relative_doppler_hz": "signed relative Doppler in hertz",
            "relative_amplitude_linear": "linear amplitude ratio = 10^(relative_power_db/20)",
        },
        "fit_power_representation": "relative_power_db; positive values are retained",
        "main_path_semantics": config.sampling_contract.get("main_path_default", {}),
        "phase_policy": config.sampling_contract.get("phase_policy"),
        "multi_millisecond_policy": config.sampling_contract.get("multi_millisecond_policy"),
        "dependence_policy": config.sampling_contract.get("dependence_policy"),
        "support_status_must_be_propagated": True,
        "prior_only_cells_are_not_empirically_validated": True,
        "external_or_deferred": config.sampling_contract.get("not_included", []),
        "gold_labels_used_for_selection": False,
        "posterior_gold_used_for_selection": False,
    }


def _model_report(
    config: FitConfig,
    audit: Any,
    selections: Mapping[str, Any],
    coverage: Sequence[CellCoverage],
    bootstrap_records: Sequence[Mapping[str, Any]],
) -> str:
    selected = ", ".join(f"{parameter}={selections[parameter].family}" for parameter in FIT_PARAMETERS)
    lines = [
        "# Environment × Elevation Path Distribution Model v1",
        "",
        "Status: `COMPLETED_WITH_SPARSE_PRIOR_CELLS` after the build step; this is a bounded conditional NLOS path-distribution layer, not the final darkroom generator.",
        "",
        "## Scope",
        "",
        "The model consumes only the frozen Stage4-confirmed multipath path partition. It fits relative excess delay, signed relative Doppler, and relative power in dB. The latter is exported as linear amplitude with the fixed `/20` conversion. No LOS/reference path, occurrence rate, path lifetime, absolute power, lock loss, or phase distribution is learned here.",
        "",
        f"Source rows: {audit.source_row_count}; environment-ready: {audit.environment_ready_count}; elevation-ready: {audit.elevation_ready_count}; elevation-excluded: {audit.elevation_excluded_count}.",
        f"Selected global marginal families: {selected}.",
        "",
        "## Cell support",
        "",
        "| Environment | LOW | MID | HIGH |",
        "|---|---:|---:|---:|",
    ]
    for environment in ENVIRONMENTS:
        values = [next(row for row in coverage if row.environment == environment and row.elevation_band == band) for band in ELEVATION_BANDS]
        lines.append("| " + environment + " | " + " | ".join(f"{row.path_count} ({row.support_status})" for row in values) + " |")
    lines.extend(
        [
            "",
            "The two zero-observation cells are inherited exactly from their environment parents and remain `PRIOR_ONLY`: Urban–LOW and Highway/Open–LOW. Sparse cells are not presented as empirically validated strata.",
            "",
            f"Scene-block bootstrap records: {len(bootstrap_records)} summary rows from {config.bootstrap_replicates} replicates (seed {config.bootstrap_seed}). QA draws: {config.qa_draw_count} per cell (base seed {config.qa_draw_seed}).",
            "",
            "## Deferred composition",
            "",
            "A downstream generator must separately define the common/main-path gain, receiver lock-loss behavior, phase initialization/evolution, path count or inactive slots, absolute RF calibration, and the fixed four-row millisecond table. This output must not be interpreted as a completed physical channel model.",
            "",
        ]
    )
    return "\n".join(lines)


def build_model(
    project_root: Path,
    config_path: Path,
    output_dir: Path,
    *,
    allow_test_namespace: bool = False,
) -> BuildReceipt:
    """Build once into a previously absent namespace."""

    preflight_info = preflight(
        project_root, config_path, output_dir, allow_test_namespace=allow_test_namespace
    )
    root = _canonical(project_root)
    config_file = _canonical(config_path)
    target = _canonical(output_dir)
    config = load_frozen_config(config_file)
    target.mkdir(parents=True, exist_ok=False)
    observations, source_audit = load_path_observations(root, config)
    vectors = [to_model_vector(row) for row in observations]
    coverage = build_cell_coverage(observations)
    selections = {
        parameter: select_global_family(vectors, parameter, config.candidate_families[parameter])
        for parameter in FIT_PARAMETERS
    }
    marginals = fit_hierarchical_marginals(vectors, selections, config)
    global_copula = fit_global_copula(vectors, config.copula_eigenvalue_floor)
    environment_copulas = fit_environment_copulas(vectors, global_copula, config)
    bootstrap_records = bootstrap_global_summary(vectors, selections, config)
    diagnostic_rows = _predictive_diagnostics(marginals, environment_copulas, config)

    _write_csv(
        target / "source_path_audit.csv",
        _source_audit_rows(observations),
        (
            "source_row_number", "event_path_id", "event_id", "run_id", "scene_id", "prn",
            "tracking_channel", "environment", "elevation_deg", "elevation_band",
            "geometry_join_valid", "elevation_modeling_ready", "relative_delay_ns",
            "relative_doppler_hz", "relative_power_db", "relative_amplitude_linear",
            "source_file", "source_file_sha256",
        ),
    )
    _write_csv(
        target / "cell_coverage.csv",
        [asdict(row) for row in coverage],
        ("environment", "elevation_band", "path_count", "event_count", "scene_count", "support_status"),
    )
    _write_csv(
        target / "marginal_family_selection.csv",
        _family_selection_rows(selections),
        (
            "parameter", "candidate_family", "selected", "valid", "total_held_out_log_likelihood",
            "held_out_scene_count", "held_out_scenes", "fold_log_likelihood_json", "failure",
            "row_random_split_used",
        ),
    )
    global_environment_rows = []
    for parameter in FIT_PARAMETERS:
        global_environment_rows.append(_marginal_row("global", "global", marginals.global_models[parameter]))
        for environment in ENVIRONMENTS:
            global_environment_rows.append(
                _marginal_row("environment", environment, marginals.environment_models[(environment, parameter)])
            )
    _write_csv(
        target / "global_environment_marginals.csv",
        global_environment_rows,
        (
            "scope", "scope_id", "parameter", "family", "fit_parameters_json", "support_status",
            "parameter_source", "direct_path_count", "direct_scene_count", "local_likelihood_row_count",
            "pseudo_observation_weight", "parent_scope", "fit_objective",
        ),
    )
    _write_csv(
        target / "cell_distribution_parameters.csv",
        _cell_parameter_rows(marginals),
        (
            "scope", "scope_id", "parameter", "family", "fit_parameters_json", "support_status",
            "parameter_source", "direct_path_count", "direct_scene_count", "local_likelihood_row_count",
            "pseudo_observation_weight", "parent_scope", "fit_objective",
        ),
    )
    copula_rows = [_copula_row("global", "", global_copula)] + [
        _copula_row("environment", environment, environment_copulas[environment])
        for environment in ENVIRONMENTS
    ]
    copula_fields = ["scope", "environment", "n_observations", "shrinkage_weight", "correction_frobenius_norm", "source_scope"]
    copula_fields.extend(
        f"corr__{left}__{right}" for left in FIT_PARAMETERS for right in FIT_PARAMETERS
    )
    _write_csv(target / "environment_copula_parameters.csv", copula_rows, copula_fields)
    _write_csv(
        target / "cell_model_index.csv",
        _cell_index_rows(marginals, coverage),
        (
            "cell_id", "environment", "elevation_band", "path_count", "event_count", "scene_count",
            "support_status", "delay_model_id", "doppler_model_id", "power_model_id", "copula_scope",
            "joint_sampling_scope",
        ),
    )
    _write_csv(
        target / "bootstrap_uncertainty.csv",
        bootstrap_records,
        (
            "scope", "parameter", "metric", "lower_2_5", "median_50", "upper_97_5",
            "bootstrap_replicates", "bootstrap_seed",
        ),
    )
    _write_csv(
        target / "fit_diagnostics.csv",
        diagnostic_rows,
        (
            "environment", "elevation_band", "cell_id", "support_status", "qa_seed", "qa_draw_count",
            "finite_rate", "positive_delay_rate", "positive_amplitude_rate", "max_copula_abs_corr_delta",
            "max_marginal_cdf_ppf_error", "diagnostic_status",
        ),
    )
    _write_json(target / "sampling_contract.json", _sampling_contract(config))
    (target / "model_report.md").write_text(
        _model_report(config, source_audit, selections, coverage, bootstrap_records),
        encoding="utf-8",
    )

    generated_without_receipt = sorted(
        path.name for path in target.iterdir() if path.is_file() and path.name not in {"model_manifest.json", "build_receipt.json"}
    )
    output_hashes = {name: _sha256(target / name) for name in generated_without_receipt}
    manifest = {
        "manifest_version": "environment-elevation-path-model-manifest-v1",
        "created_utc": _utc_now(),
        "model_id": config.model_id,
        "model_version": config.model_version,
        "config_path": str(config_file),
        "config_sha256": _sha256(config_file),
        "source_path": source_audit.source_path,
        "source_sha256": source_audit.source_sha256,
        "parameter_set_id": config.parameter_set_id,
        "source_counts": {
            "environment_ready_paths": source_audit.environment_ready_count,
            "elevation_ready_paths": source_audit.elevation_ready_count,
            "elevation_excluded_paths": source_audit.elevation_excluded_count,
        },
        "scene_count": source_audit.scene_count,
        "selected_families": {parameter: selections[parameter].family for parameter in FIT_PARAMETERS},
        "family_selection_grouping": "leave_one_scene_out",
        "gold_labels_used_for_selection": False,
        "posterior_gold_used_for_selection": False,
        "hierarchical_prior": {
            "parent_quantile_count": config.parent_quantile_count,
            "prior_equivalent_weight": config.prior_equivalent_weight,
        },
        "copula": {
            "scope": "environment",
            "shrinkage_denominator": config.copula_shrinkage_denominator,
            "eigenvalue_floor": config.copula_eigenvalue_floor,
        },
        "uncertainty": {
            "bootstrap_seed": config.bootstrap_seed,
            "bootstrap_replicates": config.bootstrap_replicates,
            "qa_draw_seed": config.qa_draw_seed,
            "qa_draw_count": config.qa_draw_count,
        },
        "execution_policy": dict(config.execution_policy),
        "protected_pipeline": dict(config.protected_source),
        "backend": preflight_info["backend"],
        "code_hashes": {
            "builder_sha256": _sha256(Path(__file__).resolve()),
            "core_sha256": _sha256(Path(__file__).with_name("path_distribution_core.py")),
        },
        "output_hashes_excluding_manifest_and_receipt": output_hashes,
        "required_output_files": list(REQUIRED_OUTPUT_FILES),
        "status": "COMPLETED_WITH_SPARSE_PRIOR_CELLS",
    }
    _write_json(target / "model_manifest.json", manifest)
    manifest_hash = _sha256(target / "model_manifest.json")
    all_output_files = tuple(sorted(path.name for path in target.iterdir() if path.is_file()))
    receipt_data = {
        "receipt_version": "environment-elevation-path-model-build-receipt-v1",
        "status": "COMPLETED",
        "created_utc": _utc_now(),
        "output_dir": str(target),
        "model_manifest_sha256": manifest_hash,
        "source_sha256": source_audit.source_sha256,
        "config_sha256": _sha256(config_file),
        "selected_families": {parameter: selections[parameter].family for parameter in FIT_PARAMETERS},
        "source_counts": {
            "environment_ready_paths": source_audit.environment_ready_count,
            "elevation_ready_paths": source_audit.elevation_ready_count,
            "elevation_excluded_paths": source_audit.elevation_excluded_count,
        },
        "execution_policy": dict(config.execution_policy),
        "output_files_excluding_receipt": [name for name in all_output_files if name != "build_receipt.json"],
        "output_hashes_excluding_receipt": {
            name: _sha256(target / name)
            for name in all_output_files
            if name != "build_receipt.json"
        },
    }
    _write_json(target / "build_receipt.json", receipt_data)
    final_hashes = {
        name: _sha256(target / name)
        for name in sorted(path.name for path in target.iterdir() if path.is_file())
        if name != "build_receipt.json"
    }
    return BuildReceipt(
        status="COMPLETED",
        output_dir=str(target),
        model_manifest_sha256=manifest_hash,
        source_sha256=source_audit.source_sha256,
        config_sha256=_sha256(config_file),
        selected_families={parameter: selections[parameter].family for parameter in FIT_PARAMETERS},
        source_counts={
            "environment_ready_paths": source_audit.environment_ready_count,
            "elevation_ready_paths": source_audit.elevation_ready_count,
            "elevation_excluded_paths": source_audit.elevation_excluded_count,
        },
        execution_policy=dict(config.execution_policy),
        output_files=tuple(sorted(final_hashes)),
        output_hashes=final_hashes,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        if args.validate_only:
            info = preflight(args.project_root, args.config, args.output)
            print(json.dumps(info, indent=2, sort_keys=True, default=_json_default))
            print("BUILD_VALIDATE_ONLY=PASS")
            return 0
        receipt = build_model(args.project_root, args.config, args.output)
        print(json.dumps(asdict(receipt), indent=2, sort_keys=True, default=_json_default))
        print("BUILD_STATUS=COMPLETED")
        return 0
    except Exception as exc:  # CLI must fail closed with a non-zero exit.
        print(f"BUILD_REJECTED={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
