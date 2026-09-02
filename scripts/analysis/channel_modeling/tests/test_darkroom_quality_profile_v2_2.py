from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from scripts.analysis.channel_modeling.darkroom_generator_core import DistributionSpec, FadeModel, LockModel
from scripts.analysis.channel_modeling.darkroom_quality_profile_v2_2 import (
    GOOD_TRACKED_BASELINE,
    POOR_CONDITIONAL,
    QualityProfileRequest,
    generate_quality_timeline,
)


def _models() -> SimpleNamespace:
    depth = DistributionSpec(
        family="normal",
        parameters={"loc": 8.0, "scale": 0.0},
        support_status="TEST",
        parameter_source="TEST",
    )
    fade = FadeModel(depth=depth, duration=depth, entry_rate_per_s=0.0, support_status="FADE_TEST")
    lock = LockModel(
        entry_probability_per_ms=0.0,
        duration_shape=1.0,
        duration_scale_s=0.020,
        recovery_shape=1.0,
        recovery_scale_s=0.010,
        depth=depth,
        support_status="LOCK_TEST",
    )
    return SimpleNamespace(lock_models={"Urban": lock}, fade_models={"Urban": fade})


def _request(mode: str, duration_ms: int = 1000, band: str = "LOW") -> QualityProfileRequest:
    return QualityProfileRequest(
        simulation_id="quality-test",
        pairing_id="quality-pair-test",
        environment_class="Urban",
        elevation_band=band,
        duration_ms=duration_ms,
        master_seed=20260827,
        quality_mode=mode,
    )


def test_good_mode_is_tracked_without_quality_event() -> None:
    result = generate_quality_timeline(_request(GOOD_TRACKED_BASELINE), _models(), [])
    assert len(result.states) == 1000
    assert set(result.states) == {"TRACKED_GOOD"}
    assert result.event_catalog == ()
    assert np.array_equal(result.envelope_linear, np.ones(1000))
    assert all(result.phase_observable)


def test_poor_mode_emits_one_complete_event_with_positive_floor() -> None:
    registry: list[dict[str, object]] = []
    result = generate_quality_timeline(_request(POOR_CONDITIONAL), _models(), registry)
    assert len(result.event_catalog) == 1
    event = result.event_catalog[0]
    assert event["complete_event"] is True
    assert event["entry_probability_used"] is False
    assert event["entry_ramp_ms"] == min(20, int(event["lock_duration_ms"]))
    assert event["event_end_ms"] - event["event_start_ms"] + 1 == (
        int(event["lock_duration_ms"]) + int(event["recovery_duration_ms"])
    )
    assert event["floor_linear"] > 0.0
    assert result.states.count("FADING_TO_LOCK_BAD") == int(event["entry_ramp_ms"])
    if int(event["lock_duration_ms"]) > int(event["entry_ramp_ms"]):
        assert "LOCK_BAD_HOLD" in result.states
    assert "RECOVERING" in result.states
    event_start = int(event["event_start_ms"]) - 1
    event_end = int(event["event_end_ms"])
    assert all(not flag for flag in result.phase_observable[event_start:event_end])
    assert all(flag for flag in result.phase_observable[:event_start])
    assert all(flag for flag in result.phase_observable[event_end:])
    assert float(np.min(result.envelope_linear)) > 0.0
    assert any(row["stream_name"].startswith(f"{POOR_CONDITIONAL}:") for row in registry)


def test_poor_event_does_not_truncate_when_duration_does_not_fit() -> None:
    with pytest.raises(ValueError, match="QUALITY_EPISODE_DOES_NOT_FIT"):
        generate_quality_timeline(_request(POOR_CONDITIONAL, duration_ms=220), _models(), [])


def test_quality_streams_are_band_specific_and_deterministic() -> None:
    first_registry: list[dict[str, object]] = []
    second_registry: list[dict[str, object]] = []
    first = generate_quality_timeline(_request(POOR_CONDITIONAL, band="LOW"), _models(), first_registry)
    second = generate_quality_timeline(_request(POOR_CONDITIONAL, band="LOW"), _models(), second_registry)
    assert first.states == second.states
    assert np.array_equal(first.envelope_linear, second.envelope_linear)
    assert first.event_catalog == second.event_catalog
    assert first_registry == second_registry
    low_registry: list[dict[str, object]] = []
    mid_registry: list[dict[str, object]] = []
    generate_quality_timeline(_request(POOR_CONDITIONAL, band="LOW"), _models(), low_registry)
    generate_quality_timeline(_request(POOR_CONDITIONAL, band="MID"), _models(), mid_registry)
    assert {row["seed_uint64"] for row in low_registry} != {row["seed_uint64"] for row in mid_registry}


def test_unknown_quality_mode_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported quality mode"):
        generate_quality_timeline(_request("UNKNOWN"), _models(), [])
