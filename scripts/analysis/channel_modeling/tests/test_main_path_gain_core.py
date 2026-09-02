from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from scripts.analysis.channel_modeling.main_path_gain_core import (
    GainFadeConfig,
    GainGridRow,
    TrackingObservation,
    build_analysis_grid,
    compute_local_upper_baseline,
    compute_run_reference,
    db_to_linear_amplitude,
    elevation_band_for,
    extract_fade_events,
    fit_latent_correlation_time,
    fit_hierarchical_gain_marginals,
    fit_family,
    join_nearest_geometry,
    tracking_sample_to_utc,
)


def _observation(
    *,
    times_s: list[float],
    cn0: list[float],
    lock: list[float] | None = None,
    run_id: str = "run-1",
) -> TrackingObservation:
    lock_values = np.asarray(lock if lock is not None else [0.0] * len(times_s))
    return TrackingObservation(
        run_id=run_id,
        scene_id="scene-1",
        prn="G11",
        tracking_channel=2,
        environment="Urban",
        tracking_path="tracking.mat",
        tracking_sha256="hash-1",
        times_s=np.asarray(times_s, dtype=float),
        cn0_values=np.asarray(cn0, dtype=float),
        lock_values=lock_values,
        states=tuple("LOCK_GOOD" for _ in times_s),
        gap_limit_s=0.0025,
        median_interval_s=0.001,
        valid_count=len(times_s),
        inconclusive_count=0,
    )


def _grid_row(
    time_s: float,
    gain_db: float,
    *,
    run_id: str = "run-1",
    scene_id: str = "scene-1",
    elevation_band: str | None = "MID",
    lock_state: str = "LOCK_GOOD",
    fade_depth_db: float | None = 0.0,
) -> GainGridRow:
    return GainGridRow(
        run_id=run_id,
        scene_id=scene_id,
        prn="G11",
        tracking_channel=2,
        environment="Urban",
        time_s=time_s,
        time_bin_index=round(time_s / 0.02),
        cn0_db_hz=45.0 + gain_db,
        c_ref_run_db_hz=45.0,
        common_gain_db=gain_db,
        common_gain_linear=float(10 ** (gain_db / 20.0)),
        local_upper_db_hz=45.0,
        fade_depth_db=fade_depth_db,
        lock_state=lock_state,
        continuity_valid=True,
        elevation_deg=45.0 if elevation_band else None,
        elevation_band=elevation_band,
        geometry_join_valid=elevation_band is not None,
        geometry_join_status="valid" if elevation_band else "unavailable",
        geometry_time_delta_s=0.5 if elevation_band else None,
        baseline_status="valid",
    )


def test_sample_counter_utc_mapping_preserves_fractional_seconds() -> None:
    origin = datetime(2026, 1, 17, 11, 47, 40, 183000, tzinfo=timezone.utc)
    mapped = tracking_sample_to_utc(10_230_000 * 1.25, 10_230_000, origin)
    assert mapped == datetime(2026, 1, 17, 11, 47, 41, 433000, tzinfo=timezone.utc)


def test_elevation_bins_have_frozen_half_open_boundaries() -> None:
    assert elevation_band_for(0.0) == "LOW"
    assert elevation_band_for(29.999999) == "LOW"
    assert elevation_band_for(30.0) == "MID"
    assert elevation_band_for(59.999999) == "MID"
    assert elevation_band_for(60.0) == "HIGH"
    assert elevation_band_for(90.0) == "HIGH"
    with pytest.raises(ValueError):
        elevation_band_for(90.0001)


def test_nearest_geometry_is_same_prn_and_fails_closed_at_tolerance() -> None:
    records = [
        {"prn": "G11", "utc_seconds": 100.0, "elevation_deg": 35.0, "azimuth_deg": 10.0, "snr_db_hz": 45.0},
        {"prn": "G12", "utc_seconds": 100.01, "elevation_deg": 50.0, "azimuth_deg": 20.0, "snr_db_hz": 46.0},
    ]
    valid = join_nearest_geometry(records, "G11", 100.5, tolerance_s=5.0)
    assert valid.valid is True
    assert valid.elevation_deg == 35.0
    invalid = join_nearest_geometry(records, "G11", 106.0, tolerance_s=5.0)
    assert invalid.valid is False
    assert invalid.reason == "nearest_geometry_delta_exceeds_5s"
    missing = join_nearest_geometry(records, "G13", 100.0, tolerance_s=5.0)
    assert missing.valid is False
    assert missing.reason == "geometry_prn_missing_in_timeseries"


def test_run_reference_and_amplitude_transform_are_explicitly_relative() -> None:
    observation = _observation(times_s=[0.0, 0.001, 0.002], cn0=[40.0, 42.0, 44.0])
    assert compute_run_reference(observation) == pytest.approx(42.0)
    values = db_to_linear_amplitude(np.asarray([0.0, -6.020599913279624, 6.020599913279624]))
    assert np.allclose(values, [1.0, 0.5, 2.0], atol=1e-12)


def test_analysis_grid_does_not_cross_continuity_gap() -> None:
    observation = _observation(
        times_s=[0.000, 0.001, 0.002, 0.020, 0.021],
        cn0=[40.0, 40.0, 40.0, 30.0, 30.0],
    )
    rows = build_analysis_grid(observation, bin_ms=20)
    assert rows
    assert all(row.continuity_valid for row in rows if row.time_s < 0.003)
    assert any(row.baseline_status == "gap_boundary" for row in rows)


def test_local_baseline_is_segment_bounded_and_short_segment_is_inconclusive() -> None:
    rows = [
        _grid_row(index * 0.02, -float(index % 3))
        for index in range(100)
    ]
    rows[50] = _grid_row(1.0, -10.0)
    result = compute_local_upper_baseline(rows, window_s=10.0)
    assert result[50].status == "valid"
    assert result[50].upper_db_hz is not None
    short = [_grid_row(index * 0.02, -1.0) for index in range(20)]
    short_result = compute_local_upper_baseline(short, window_s=10.0)
    assert any(item.status == "baseline_inconclusive" for item in short_result)


def test_fade_state_machine_uses_entry_exit_hysteresis_and_censoring() -> None:
    rows = [_grid_row(index * 0.02, -4.0 if 2 <= index <= 5 else -0.5, fade_depth_db=4.0 if 2 <= index <= 5 else 0.5)
            for index in range(12)]
    rows[6] = _grid_row(0.12, -4.0, lock_state="LOCK_BAD", fade_depth_db=None)
    result = extract_fade_events(rows, GainFadeConfig())
    assert len(result.events) == 1
    event = result.events[0]
    assert event.max_observed_depth_db == pytest.approx(4.0)
    assert event.right_censored is True
    assert event.censor_reason == "lock_bad_transition"
    assert event.missing_depth_count == 1


def test_fade_depth_requires_valid_observation_and_never_uses_zero_for_missing() -> None:
    rows = [
        _grid_row(0.0, -4.0, fade_depth_db=None, lock_state="LOCK_BAD"),
        _grid_row(0.02, -4.0, fade_depth_db=4.0),
    ]
    result = extract_fade_events(rows, GainFadeConfig())
    assert result.events
    assert result.events[0].max_observed_depth_db == pytest.approx(4.0)
    assert result.events[0].missing_depth_count == 0


def test_hierarchical_empty_cell_inherits_environment_parent_and_is_labeled() -> None:
    rows = [_grid_row(index * 0.02, -float(index % 2), elevation_band="MID") for index in range(20)]
    result = fit_hierarchical_gain_marginals(rows, environments=("Urban",), elevation_bands=("LOW", "MID"))
    low = result["Urban", "LOW"]
    mid = result["Urban", "MID"]
    assert low.support_status == "PRIOR_ONLY"
    assert low.parameter_source == "environment_parent_only"
    assert low.parameters == mid.parameters


def test_correlation_fit_is_deterministic_and_does_not_bridge_gap() -> None:
    rows = [_grid_row(index * 0.02, np.sin(index / 4.0)) for index in range(80)]
    rows[40] = _grid_row(2.0, 0.0, lock_state="INCONCLUSIVE_GAP")
    first = fit_latent_correlation_time(rows)
    second = fit_latent_correlation_time(rows)
    assert first.tau_s == pytest.approx(second.tau_s)
    assert first.cross_gap_pairs == 0


def test_weighted_family_fit_balances_scenes_and_positive_location_is_fixed() -> None:
    rows = [
        {"scene_id": "short", "value": -1.0},
        {"scene_id": "long", "value": 0.0},
        {"scene_id": "long", "value": 0.1},
        {"scene_id": "long", "value": 0.2},
    ]
    from scripts.analysis.channel_modeling.main_path_gain_core import _scene_balanced_weights

    weights = _scene_balanced_weights(rows)
    assert float(np.sum(weights[:1])) == pytest.approx(float(np.sum(weights[1:])))
    fit = fit_family([1.0, 2.0, 3.0, 4.0], "lognormal", right_censored=[False, False, True, True])
    assert fit.parameters["loc"] == 0.0
