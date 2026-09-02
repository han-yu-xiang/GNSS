from __future__ import annotations

from collections import Counter
import csv
import gzip
from dataclasses import replace
from pathlib import Path

import pytest
import numpy as np

from scripts.analysis.channel_modeling.nlos_slot_activation_core import (
    ActivationModel,
    ConfirmedEvent,
    BlockActivationState,
    ENVIRONMENTS,
    ELEVATION_BANDS,
    ExposureWindow,
    MultiplicityHierarchy,
    MultiplicityModel,
    OccupancyHierarchy,
    BetaOccupancyModel,
    PathDraw,
    SceneCellExposure,
    Stage0Source,
    assign_continuity_segments,
    aggregate_scene_cell_exposure,
    activation_mask,
    build_activation_labels,
    canonicalize_paths,
    classify_occupancy_support,
    derive_stream_seed,
    fit_beta_pseudo_posterior,
    fit_dirichlet_counts,
    fit_multiplicity_hierarchy,
    fit_occupancy_hierarchy,
    generate_activation_qa_draws,
    emit_internal_slot_rows,
    join_geometry_grid,
    load_activation_config,
    load_confirmed_events,
    load_stage0_exposure,
    sample_path_count,
    sample_block_activation,
    scene_block_bootstrap,
    verify_frozen_sources,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = PROJECT_ROOT / "configs" / "channel_modeling" / "nlos_slot_activation_v1.json"


def test_frozen_source_contract():
    config = load_activation_config(CONFIG_PATH)
    audit = verify_frozen_sources(PROJECT_ROOT, config)
    events = load_confirmed_events(PROJECT_ROOT, config)

    assert audit.eligible_run_count == 63
    assert audit.stage0_window_count == 169637
    assert len(events) == 94
    assert sum(event.confirmed_path_count for event in events) == 100
    assert Counter(event.confirmed_path_count for event in events) == Counter({1: 89, 2: 4, 3: 1})


def test_config_rejects_wrong_environment_or_band(tmp_path: Path):
    config_text = CONFIG_PATH.read_text(encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text(config_text.replace('"HIGH"', '"HIGH_BAD"', 1), encoding="utf-8")
    with pytest.raises(ValueError, match="elevation"):
        load_activation_config(bad)


def test_stage0_loader_preserves_window_identity_and_count(tmp_path: Path):
    stage0 = tmp_path / "stage0_valid_40ms_windows.csv"
    fields = ["window_id", "sample_start_zero_based", "recording_time_s", "tow_s"]
    with stage0.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"window_id": "1", "sample_start_zero_based": "100", "recording_time_s": "1.0", "tow_s": "100.0"},
            {"window_id": "2", "sample_start_zero_based": "204700", "recording_time_s": "1.02", "tow_s": "100.02"},
        ])
    source = Stage0Source("run-1", "scene-1", "G01", "0", "Urban", stage0, 2)
    rows = load_stage0_exposure(source)
    assert [row.window_id for row in rows] == [1, 2]
    assert [row.sample_start_zero_based for row in rows] == [100, 204700]
    assert all(row.environment == "Urban" for row in rows)


def test_continuity_segments_break_on_sample_or_tow_gap(tmp_path: Path):
    stage0 = tmp_path / "stage0_valid_40ms_windows.csv"
    fields = ["window_id", "sample_start_zero_based", "recording_time_s", "tow_s"]
    with stage0.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"window_id": "1", "sample_start_zero_based": "100", "recording_time_s": "1.0", "tow_s": "100.0"},
            {"window_id": "2", "sample_start_zero_based": "204700", "recording_time_s": "1.02", "tow_s": "100.02"},
            {"window_id": "3", "sample_start_zero_based": "1000000", "recording_time_s": "2.0", "tow_s": "101.0"},
        ])
    source = Stage0Source("run-1", "scene-1", "G01", "0", "Urban", stage0, 3)
    rows = assign_continuity_segments(load_stage0_exposure(source))
    assert [row.continuity_segment for row in rows] == [0, 0, 1]


def test_geometry_join_uses_nearest_row_and_lower_bin_tie(tmp_path: Path):
    grid = tmp_path / "grid.csv.gz"
    fields = ["run_id", "time_s", "time_bin_index", "environment", "elevation_deg", "elevation_band", "azimuth_deg", "nmea_snr_db_hz", "geometry_join_valid", "geometry_join_status"]
    with gzip.open(grid, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {"run_id": "run-1", "time_s": "1.00", "time_bin_index": "10", "environment": "Urban", "elevation_deg": "20", "elevation_band": "LOW", "azimuth_deg": "100", "nmea_snr_db_hz": "40", "geometry_join_valid": "1", "geometry_join_status": "valid"},
            {"run_id": "run-1", "time_s": "1.02", "time_bin_index": "11", "environment": "Urban", "elevation_deg": "21", "elevation_band": "LOW", "azimuth_deg": "101", "nmea_snr_db_hz": "41", "geometry_join_valid": "1", "geometry_join_status": "valid"},
        ])
    stage0 = tmp_path / "stage0_valid_40ms_windows.csv"
    fields0 = ["window_id", "sample_start_zero_based", "recording_time_s", "tow_s"]
    with stage0.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields0)
        writer.writeheader()
        writer.writerow({"window_id": "1", "sample_start_zero_based": "0", "recording_time_s": "1.01", "tow_s": "0.0"})
    source = Stage0Source("run-1", "scene-1", "G01", "0", "Urban", stage0, 1)
    rows = assign_continuity_segments(load_stage0_exposure(source))
    joined = join_geometry_grid(rows, grid, tolerance_s=0.011)
    assert joined[0].time_bin_index == 10
    assert joined[0].geometry_join_status == "valid"


def _synthetic_exposure(count: int = 10, split_after: int | None = None) -> list[ExposureWindow]:
    rows = []
    for window_id in range(1, count + 1):
        rows.append(ExposureWindow(
            run_id="run-1",
            scene_id="scene-1",
            prn="G01",
            tracking_channel="0",
            environment="Urban",
            window_id=window_id,
            sample_start_zero_based=(window_id - 1) * 204600,
            recording_time_s=(window_id - 1) * 0.02,
            tow_s=(window_id - 1) * 0.02,
            continuity_segment=1 if split_after is not None and window_id > split_after else 0,
        ))
    return rows


def _event(event_id: str, center: int) -> ConfirmedEvent:
    return ConfirmedEvent(
        event_id=event_id,
        run_id="run-1",
        scene_id="scene-1",
        prn="G01",
        tracking_channel="0",
        center_window_id=center,
        environment="Urban",
        elevation_deg=None,
        elevation_band=None,
        elevation_modeling_ready=False,
        confirmed_path_count=1,
        event_utc="",
    )


def test_closure_union_preserves_core_and_membership_provenance():
    evidence = build_activation_labels(_synthetic_exposure(), [_event("e1", 5), _event("e2", 7)], closure_radius=2)
    labels = {row.window_id: row.support_label for row in evidence.exposure}
    assert labels[5] == "CONFIRMED_CORE"
    assert labels[7] == "CONFIRMED_CORE"
    assert sum(label != "INACTIVE" for label in labels.values()) == 7
    memberships = [row for row in evidence.memberships if row["window_id"] == 6]
    assert {row["event_id"] for row in memberships} == {"e1", "e2"}
    assert len(memberships) == 2


def test_closure_does_not_cross_continuity_segment():
    evidence = build_activation_labels(_synthetic_exposure(split_after=5), [_event("e1", 5)], closure_radius=2)
    assert evidence.closure_complete["e1"] is False
    assert {row["window_id"] for row in evidence.memberships} == {3, 4, 5}


def test_scene_cell_exposure_uses_unique_support_windows():
    evidence = build_activation_labels(_synthetic_exposure(), [_event("e1", 5)], closure_radius=2)
    rows = aggregate_scene_cell_exposure(evidence)
    cell = [row for row in rows if row.elevation_band is None and row.environment == "Urban"][0]
    assert cell.exposure_windows == 10
    assert cell.support_windows == 5
    assert cell.scene_rate == pytest.approx(0.5)


def test_beta_pseudo_posterior_has_finite_ordered_quantiles():
    model = fit_beta_pseudo_posterior([0.0, 0.5, 1.0], parent_mean=None, parent_mass=8.0)
    assert model.alpha == pytest.approx(2.0)
    assert model.beta == pytest.approx(2.0)
    assert 0.0 < model.q025 < model.q50 < model.q975 < 1.0


def test_occupancy_uses_equal_scene_weight_not_window_count():
    rows = [
        SceneCellExposure("scene-a", "Urban", "MID", 10000, 0, (), 0.0),
        SceneCellExposure("scene-b", "Urban", "MID", 1, 1, ("e1",), 1.0),
    ]
    result = fit_occupancy_hierarchy(rows, load_activation_config(CONFIG_PATH))
    cell = result.cell_models[("Urban", "MID")]
    assert cell.direct_scene_count == 2
    assert cell.mean == pytest.approx(0.5)


def test_occupancy_support_distinguishes_zero_exposure_and_zero_confirmation():
    assert classify_occupancy_support(2, 0) == "EXPOSURE_ONLY_ZERO_CONFIRMED"
    assert classify_occupancy_support(0, 0) == "PRIOR_ONLY"
    assert classify_occupancy_support(2, 10) == "DATA_SUPPORTED_WITH_GROUPED_VALIDATION"


def test_dirichlet_probabilities_are_normalized_and_positive():
    model = fit_dirichlet_counts([89, 4, 1], None, parent_mass=8.0)
    assert model.categories == (1, 2, 3)
    assert model.counts == (89, 4, 1)
    assert sum(model.probabilities) == pytest.approx(1.0, abs=1e-12)
    assert all(value > 0.0 for value in model.probabilities)
    assert sample_path_count(model, np.random.default_rng(1234)) in {1, 2, 3}


def test_multiplicity_hierarchy_uses_event_counts_and_empty_parent():
    config = load_activation_config(CONFIG_PATH)
    events = load_confirmed_events(PROJECT_ROOT, config)
    result = fit_multiplicity_hierarchy(events, config)
    assert result.global_model.counts == (89, 4, 1)
    empty = result.cell_models[("Highway/Open", "LOW")]
    parent = result.environment_models["Highway/Open"]
    assert empty.support_status == "PRIOR_ONLY"
    assert empty.probabilities == parent.probabilities


def test_dirichlet_rejects_invalid_categories():
    with pytest.raises(ValueError, match="counts"):
        fit_dirichlet_counts([1, -1, 0], None, parent_mass=8.0)


def test_activation_masks_are_prefixes():
    assert activation_mask(0) == (False, False, False)
    assert activation_mask(1) == (True, False, False)
    assert activation_mask(2) == (True, True, False)
    assert activation_mask(3) == (True, True, True)
    with pytest.raises(ValueError, match="K"):
        activation_mask(4)


def test_canonical_slot_order_is_independent_of_input_order():
    paths = [
        PathDraw(100.0, 2.0, 0.2, stable_source_id="b"),
        PathDraw(50.0, -1.0, 0.4, stable_source_id="a"),
    ]
    first = canonicalize_paths(paths)
    second = canonicalize_paths(list(reversed(paths)))
    assert [row.nlos_path_id for row in first] == [1, 2]
    assert [row.relative_delay_ns for row in first] == [50.0, 100.0]
    assert first == second


def test_internal_slot_rows_keep_inactive_parameters_null():
    state = BlockActivationState("b1", "Urban", "MID", "CONDITIONAL_ACTIVE_STRESS", True, 1, (True, False, False), "DATA", "PRIOR")
    rows = emit_internal_slot_rows(state, [PathDraw(12.0, -3.0, 0.5, stable_source_id="a")], block_length_ms=2)
    assert len(rows) == 8
    for ms in (1, 2):
        current = [row for row in rows if row.ms == ms]
        assert [row.nlos_path_id for row in current] == [0, 1, 2, 3]
        inactive = [row for row in current if row.nlos_path_id in (2, 3)]
        assert all(row.path_status == "INACTIVE_NO_PATH" for row in inactive)
        assert all(row.relative_amplitude_linear == 0.0 for row in inactive)
        assert all(row.relative_delay_ns is None and row.relative_doppler_hz is None and row.relative_phase_rad is None for row in inactive)


def _toy_activation_model(*, occupancy_mean: float = 0.25, prior_only: bool = False) -> ActivationModel:
    occupancy = BetaOccupancyModel(
        level="cell",
        key="Urban|LOW",
        alpha=occupancy_mean * 10.0,
        beta=(1.0 - occupancy_mean) * 10.0,
        mean=occupancy_mean,
        q025=0.01,
        q50=occupancy_mean,
        q975=0.99,
        direct_scene_count=0 if prior_only else 2,
        direct_core_event_count=0 if prior_only else 4,
        support_status="PRIOR_ONLY" if prior_only else "SPARSE_PARTIAL_POOLING",
        parent_key="Urban",
    )
    parent_occupancy = replace(occupancy, level="environment", key="Urban", parent_key="global")
    global_occupancy = replace(occupancy, level="global", key="global", parent_key=None)
    occupancy_hierarchy = OccupancyHierarchy(
        global_model=global_occupancy,
        environment_models={environment: replace(parent_occupancy, key=environment) for environment in ENVIRONMENTS},
        cell_models={
            (environment, band): replace(occupancy, key=f"{environment}|{band}")
            for environment in ENVIRONMENTS
            for band in ELEVATION_BANDS
        },
        scene_cell_exposure=(),
    )
    multiplicity = MultiplicityModel(
        level="cell",
        key="Urban|LOW",
        categories=(1, 2, 3),
        counts=(7, 2, 1),
        alpha=(7.0, 2.0, 1.0),
        probabilities=(0.7, 0.2, 0.1),
        q025=(0.0, 0.0, 0.0),
        q50=(0.0, 0.0, 0.0),
        q975=(1.0, 1.0, 1.0),
        direct_event_count=0 if prior_only else 10,
        support_status="PRIOR_ONLY" if prior_only else "SPARSE_PARTIAL_POOLING",
        parent_key="Urban",
    )
    parent_multiplicity = replace(multiplicity, level="environment", key="Urban", parent_key="global")
    global_multiplicity = replace(multiplicity, level="global", key="global", parent_key=None)
    multiplicity_hierarchy = MultiplicityHierarchy(
        global_model=global_multiplicity,
        environment_models={environment: replace(parent_multiplicity, key=environment) for environment in ENVIRONMENTS},
        cell_models={
            (environment, band): replace(multiplicity, key=f"{environment}|{band}")
            for environment in ENVIRONMENTS
            for band in ELEVATION_BANDS
        },
    )
    return ActivationModel(occupancy_hierarchy, multiplicity_hierarchy)


def test_stream_seeds_are_reproducible_and_cell_order_independent():
    first = derive_stream_seed(20260829, "Urban", "LOW", "block-1", "occurrence")
    second = derive_stream_seed(20260829, "Urban", "LOW", "block-1", "occurrence")
    assert first == second
    assert first != derive_stream_seed(20260829, "Urban", "LOW", "block-1", "multiplicity")
    assert first != derive_stream_seed(20260829, "Urban", "MID", "block-1", "occurrence")
    assert first != derive_stream_seed(20260829, "Urban", "LOW", "block-2", "occurrence")


def test_scene_block_bootstrap_uses_complete_scenes_and_explicit_status():
    evidence = build_activation_labels(_synthetic_exposure(count=10), [_event("e1", 5)], closure_radius=2)
    result = scene_block_bootstrap(evidence, [_event("e1", 5)], load_activation_config(CONFIG_PATH))
    assert result.replicate_count == 1000
    assert result.seed == 20260828
    assert len(result.records) == 1000
    assert all(record["resample_unit"] == "scene" for record in result.records)
    assert all(record["replicate_status"] == "PASS" for record in result.records)
    assert all("sampled_window_ids" not in record for record in result.records)


def test_qa_draws_are_deterministic_and_follow_bounded_frequency_tolerance():
    config = load_activation_config(CONFIG_PATH)
    model = _toy_activation_model()
    first = generate_activation_qa_draws(model, config)
    second = generate_activation_qa_draws(model, config)
    assert first == second
    assert len(first) == 24
    for summary in first:
        assert summary.draw_count == 4096
        assert sum(summary.k_counts.values()) == 4096
        if summary.activation_mode == "CONDITIONAL_ACTIVE_STRESS":
            assert summary.active_count == 4096
        else:
            observed = summary.active_count / summary.draw_count
            assert observed == pytest.approx(0.25, abs=0.05)


def test_prior_only_activation_state_propagates_lineage():
    config = load_activation_config(CONFIG_PATH)
    state = sample_block_activation(
        _toy_activation_model(prior_only=True),
        config,
        "Urban",
        "LOW",
        "block-1",
        20260829,
        "CONDITIONAL_ACTIVE_STRESS",
    )
    assert state.z_active is True
    assert state.is_prior_only is True
    assert state.occupancy_support_status == "PRIOR_ONLY"
    assert state.multiplicity_support_status == "PRIOR_ONLY"
