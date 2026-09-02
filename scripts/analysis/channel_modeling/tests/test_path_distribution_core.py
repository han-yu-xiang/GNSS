from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from scripts.analysis.channel_modeling.path_distribution_core import (
    CellCoverage,
    FIT_PARAMETERS,
    FitConfig,
    ModelVector,
    PathObservation,
    build_cell_coverage,
    classify_support,
    cdf,
    fit_environment_copulas,
    fit_family,
    fit_global_copula,
    fit_hierarchical_marginals,
    load_frozen_config,
    load_path_observations,
    nearest_correlation,
    parent_quantiles,
    ppf,
    relative_power_db_to_amplitude,
    sample_cell,
    select_global_family,
    to_model_vector,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = PROJECT_ROOT / "configs" / "channel_modeling" / "environment_elevation_path_distribution_v1.json"


def example_observation(
    *,
    excess_delay_s: float = 1e-7,
    relative_doppler_hz: float = -12.5,
    relative_power_db: float = -6.020599913279624,
    environment: str = "Urban",
    elevation_band: str | None = "MID",
) -> PathObservation:
    return PathObservation(
        event_path_id="ep-1",
        event_id="event-1",
        run_id="run-1",
        scene_id="scene-1",
        prn="G01",
        tracking_channel="1",
        environment=environment,
        elevation_deg=45.0 if elevation_band else None,
        elevation_band=elevation_band,
        geometry_join_valid=elevation_band is not None,
        environment_modeling_ready=True,
        elevation_modeling_ready=elevation_band is not None,
        estimate_stage="stage4_joint",
        path_role="multipath",
        is_multipath=True,
        label_value="confirmed_multipath",
        excess_delay_s=excess_delay_s,
        relative_doppler_hz=relative_doppler_hz,
        relative_power_db=relative_power_db,
        source_file="source.csv",
        source_file_sha256="source-hash",
        source_row_number=1,
    )


def test_units_and_amplitude_conversion():
    vector = to_model_vector(example_observation())
    assert vector.relative_delay_ns == pytest.approx(100.0, abs=1e-12)
    assert vector.relative_doppler_hz == -12.5
    assert relative_power_db_to_amplitude(
        np.array([-6.020599913279624])
    )[0] == pytest.approx(0.5)


def test_positive_power_db_can_produce_amplitude_above_one():
    amplitude = relative_power_db_to_amplitude(np.array([1.99172158788]))
    assert amplitude[0] > 1.0


def test_empty_and_sparse_support_states():
    assert classify_support(0, 0) == "PRIOR_ONLY"
    assert classify_support(1, 1) == "PRIOR_DOMINANT"
    assert classify_support(5, 2) == "SPARSE_PARTIAL_POOLING"
    assert classify_support(10, 2) == "DATA_SUPPORTED_WITH_GROUPED_VALIDATION"


def test_coverage_returns_all_twelve_cells_and_keeps_unaligned_rows_out_of_cells():
    rows = [
        example_observation(environment="Urban", elevation_band="MID"),
        example_observation(
            environment="Special Reflective", elevation_band=None
        ),
    ]
    coverage = build_cell_coverage(rows)
    assert len(coverage) == 12
    keyed = {(row.environment, row.elevation_band): row for row in coverage}
    assert keyed[("Urban", "MID")].path_count == 1
    assert keyed[("Special Reflective", "LOW")].path_count == 0
    assert sum(row.path_count for row in coverage) == 1


def test_correlation_projection_is_psd_and_has_unit_diagonal():
    matrix = np.array([[1.0, 1.2, -0.4], [1.2, 1.0, 0.9], [-0.4, 0.9, 1.0]])
    projected, correction = nearest_correlation(matrix, 1e-6)
    assert correction >= 0.0
    assert np.allclose(projected, projected.T, atol=1e-12)
    assert np.allclose(np.diag(projected), 1.0, atol=1e-12)
    assert np.linalg.eigvalsh(projected).min() >= 1e-6 - 1e-12


def test_source_contract_and_coverage():
    config = load_frozen_config(CONFIG_PATH)
    rows, audit = load_path_observations(PROJECT_ROOT, config)
    coverage = {(row.environment, row.elevation_band): row.path_count
                for row in build_cell_coverage(rows)}
    assert audit.source_sha256 == "2a44913d1c06f78d2748428b1d72f1b4712a6b5d3f33fc598a14fe17a3e3414a"
    assert (audit.environment_ready_count, audit.elevation_ready_count,
            audit.elevation_excluded_count) == (100, 84, 16)
    assert len(coverage) == 12
    assert coverage[("Urban", "LOW")] == 0
    assert coverage[("Highway/Open", "LOW")] == 0
    assert sum(coverage.values()) == 84


def test_distribution_fit_round_trip_and_fixed_delay_origin():
    values = np.array([1.0, 1.4, 2.0, 3.2, 5.0])
    fit = fit_family(values, None, "lognormal")
    probabilities = np.array([0.05, 0.25, 0.5, 0.9])
    recovered = cdf(fit, ppf(fit, probabilities))
    assert np.allclose(recovered, probabilities, atol=1e-8)
    assert fit.parameters["loc"] == 0.0
    student = fit_family(np.array([-3.0, -1.0, 0.0, 1.0, 4.0]), None, "student_t")
    assert 2.1 <= student.parameters["df"] <= 100.0
    assert student.parameters["scale"] > 0.0


def test_selection_holds_out_complete_scenes():
    rows = []
    for scene, values in {
        "scene_a": [-5.0, -3.0, -1.0],
        "scene_b": [0.0, 1.0, 2.0],
        "scene_c": [8.0, 9.0, 10.0],
    }.items():
        for index, value in enumerate(values):
            row = example_observation(relative_doppler_hz=value)
            rows.append(ModelVector(
                event_path_id=f"{scene}-{index}", event_id=f"{scene}-e{index}",
                run_id=scene, scene_id=scene, environment="Urban",
                elevation_band="MID", relative_delay_ns=100.0,
                relative_doppler_hz=value, relative_power_db=-3.0,
            ))
    selection = select_global_family(rows, "relative_doppler_hz",
                                     ("student_t", "normal", "laplace"))
    assert selection.held_out_groups == {"scene_a", "scene_b", "scene_c"}
    assert selection.row_random_split_used is False


def test_hierarchy_uses_prior_for_empty_cell_and_excludes_unaligned_rows():
    vectors = [to_model_vector(example_observation(elevation_band="MID"))]
    vectors.append(to_model_vector(replace(
        example_observation(), scene_id="scene-2", run_id="run-2")))
    vectors.append(to_model_vector(replace(
        example_observation(), elevation_deg=None, elevation_band=None,
        geometry_join_valid=False, elevation_modeling_ready=False)))
    config = load_frozen_config(CONFIG_PATH)
    selections = {
        parameter: select_global_family(vectors, parameter, config.candidate_families[parameter])
        for parameter in FIT_PARAMETERS
    }
    result = fit_hierarchical_marginals(vectors, selections, config)
    cell = result.cell("Urban", "LOW", "relative_delay_ns")
    parent = result.environment_models[("Urban", "relative_delay_ns")]
    assert cell.fit.parameters == parent.fit.parameters
    assert cell.local_likelihood_row_count == 0
    assert cell.support_status == "PRIOR_ONLY"
    assert cell.parameter_source == "environment_parent_only"
    assert result.cell("Urban", "MID", "relative_delay_ns").local_likelihood_row_count == 2


def test_copula_shrinkage_and_seeded_cell_sampling():
    rows = [
        ModelVector(
            event_path_id=str(index), event_id=str(index), run_id=f"r{index}",
            scene_id=f"s{index % 3}", environment="Urban", elevation_band="MID",
            relative_delay_ns=100.0 + index, relative_doppler_hz=-3.0 + index,
            relative_power_db=-10.0 + index / 2.0,
        )
        for index in range(12)
    ]
    config = load_frozen_config(CONFIG_PATH)
    global_copula = fit_global_copula(rows, config.copula_eigenvalue_floor)
    env_copulas = fit_environment_copulas(rows, global_copula, config)
    assert env_copulas["Urban"].shrinkage_weight == pytest.approx(12.0 / 22.0)
    assert np.linalg.eigvalsh(env_copulas["Urban"].correlation).min() >= 1e-6 - 1e-12
    selections = {
        parameter: select_global_family(rows, parameter, config.candidate_families[parameter])
        for parameter in FIT_PARAMETERS
    }
    marginals = fit_hierarchical_marginals(rows, selections, config)
    left = sample_cell("Urban", "LOW", marginals, env_copulas, 64, np.random.default_rng(7))
    right = sample_cell("Urban", "LOW", marginals, env_copulas, 64, np.random.default_rng(7))
    for parameter, values in left.items():
        assert np.array_equal(values, right[parameter])
    assert np.all(left["relative_delay_ns"] > 0.0)
    assert np.all(np.isfinite(left["relative_doppler_hz"]))
    assert np.all(left["relative_amplitude_linear"] > 0.0)


def test_parent_quantiles_are_deterministic():
    fit = fit_family(np.array([1.0, 2.0, 4.0, 8.0]), None, "lognormal")
    assert np.array_equal(parent_quantiles(fit, 64), parent_quantiles(fit, 64))
