from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_environment_lock_model import (
    build_exposure_and_events,
    build_model,
    fit_duration_models,
    fit_entry_rate,
    sample_lock_states,
)


def test_lock_threshold_and_gap_states_are_explicit() -> None:
    states = sample_lock_states(
        [-0.5, -0.5001, float("nan"), -0.6],
        [0.0, 0.001, 0.002, 0.010],
        threshold=-0.5,
        gap_limit_s=0.0025,
    )

    assert states == ["LOCK_GOOD", "LOCK_BAD", "INCONCLUSIVE", "INCONCLUSIVE_GAP"]


def test_exposure_uses_sample_time_and_marks_terminal_loss_censored() -> None:
    states = ["LOCK_GOOD"] * 5 + ["LOCK_BAD"] * 3
    times_s = [index / 1000.0 for index in range(len(states))]

    exposure, events = build_exposure_and_events(
        states,
        times_s,
        debounce_bad_ms=1,
        reacquire_good_ms=1,
    )

    assert exposure["outage_duration_s"] == pytest.approx(0.003)
    assert exposure["locked_exposure_s"] == pytest.approx(0.005)
    assert len(events) == 1
    assert events[0]["duration_ms"] == pytest.approx(3.0)
    assert events[0]["right_censored"] is True


def test_gamma_poisson_entry_rate_and_probability_are_deterministic() -> None:
    exposures = [
        {"environment_class": "Urban", "locked_exposure_s": 100.0},
        {"environment_class": "Urban", "locked_exposure_s": 50.0},
    ]
    events = [
        {"environment_class": "Urban"},
        {"environment_class": "Urban"},
    ]

    result = fit_entry_rate(exposures, events, prior_shape=1.0, prior_rate=1.0)

    assert result["Urban"]["entry_count"] == 2
    assert result["Urban"]["posterior_mean_entry_rate_per_s"] == pytest.approx(3 / 151)
    assert result["Urban"]["entry_probability_per_ms"] == pytest.approx(
        1.0 - __import__("math").exp(-(3 / 151) / 1000.0)
    )


def test_duration_family_selection_is_common_and_supports_right_censoring() -> None:
    events = [
        {"environment_class": "Urban", "duration_s": 0.05, "right_censored": False},
        {"environment_class": "Urban", "duration_s": 0.08, "right_censored": False},
        {"environment_class": "Mountain/Valley", "duration_s": 0.06, "right_censored": True},
    ]

    result = fit_duration_models(events)

    assert result["selected_family"] in {"lognormal", "weibull", "gamma"}
    assert set(result["environment_parameters"]) == {"Urban", "Mountain/Valley"}
    assert result["environment_parameters"]["Urban"]["duration_unit"] == "s"


def test_existing_output_namespace_is_rejected_without_writing(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "marker.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        build_model(tmp_path, output)

    assert marker.read_text(encoding="utf-8") == "keep"
