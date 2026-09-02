from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.run_darkroom_generator_v2_1 import (
    ALL_ACTIVE_MASK,
    _validate_generation_confirmation,
    _validate_namespace,
)


ROOT = Path(__file__).resolve().parents[4]


def test_v21_runner_requires_explicit_generation_confirmation() -> None:
    _validate_generation_confirmation(False, False)
    with pytest.raises(ValueError, match="confirm"):
        _validate_generation_confirmation(True, False)
    with pytest.raises(ValueError, match="--generate"):
        _validate_generation_confirmation(False, True)


def test_v21_runner_accepts_only_direct_child_of_v21_root() -> None:
    request_id = "test-v2-1"
    path = _validate_namespace(
        ROOT,
        f"dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_runs/{request_id}",
        request_id,
    )
    assert path.name == request_id
    assert ALL_ACTIVE_MASK == "111"
    with pytest.raises(ValueError, match="v2.1"):
        _validate_namespace(ROOT, f"dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/{request_id}", request_id)


def test_v21_runner_rejects_protected_or_nested_namespace() -> None:
    with pytest.raises(ValueError):
        _validate_namespace(ROOT, "dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_runs/a/b", "b")
    with pytest.raises(ValueError):
        _validate_namespace(ROOT, "scenes/anything", "anything")
