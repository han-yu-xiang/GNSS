from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.run_darkroom_generator_v2_2 import (
    LOCK_NAME,
    _csv_value,
    _validate_generation_confirmation,
    _validate_namespace,
)


ROOT = Path(__file__).resolve().parents[4]


def test_v22_runner_defaults_to_validation_and_requires_explicit_confirmation() -> None:
    _validate_generation_confirmation(False, False)
    with pytest.raises(ValueError, match="confirm"):
        _validate_generation_confirmation(True, False)
    with pytest.raises(ValueError, match="--generate"):
        _validate_generation_confirmation(False, True)


def test_v22_runner_accepts_only_direct_child_of_v22_run_root() -> None:
    request_id = "unit-run"
    path = _validate_namespace(ROOT, f"dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/{request_id}", request_id)
    assert path.name == request_id
    with pytest.raises(ValueError):
        _validate_namespace(ROOT, f"dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_runs/{request_id}", request_id)
    with pytest.raises(ValueError):
        _validate_namespace(ROOT, f"dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/a/{request_id}", request_id)
    with pytest.raises(ValueError):
        _validate_namespace(ROOT, f"scenes/{request_id}", request_id)


def test_v22_runner_writes_null_as_empty_and_rejects_nonfinite_values() -> None:
    assert _csv_value(None) == ""
    assert _csv_value(True) == "true"
    assert _csv_value(1.25) == "1.25"
    with pytest.raises(ValueError, match="non-finite"):
        _csv_value(float("nan"))
    assert LOCK_NAME.endswith("active.lock")
