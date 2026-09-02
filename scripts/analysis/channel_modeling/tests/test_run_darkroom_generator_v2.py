from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.run_darkroom_generator_v2 import (
    _validate_generation_confirmation,
    _validate_namespace,
    build_validation_summary,
)


def test_v2_namespace_requires_request_specific_new_only_run_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    allowed = _validate_namespace(
        project_root,
        "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/request-v2",
        "request-v2",
    )
    assert allowed == (project_root / "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/request-v2").resolve()
    for bad in (
        "dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_runs/request-v2",
        "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/../escape",
        "scenes/request-v2",
        "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/request-v2/child",
    ):
        with pytest.raises(ValueError):
            _validate_namespace(project_root, bad, "request-v2")


def test_generation_requires_explicit_confirmation() -> None:
    _validate_generation_confirmation(False, False)
    with pytest.raises(ValueError, match="confirm"):
        _validate_generation_confirmation(True, False)
    with pytest.raises(ValueError, match="generate"):
        _validate_generation_confirmation(False, True)
    _validate_generation_confirmation(True, True)


def test_validation_summary_has_all_bands_and_twelve_rows_per_ms() -> None:
    request = {
        "request_id": "request-v2",
        "simulation_id": "simulation-v2",
        "environment_class": "Urban",
        "elevation_bands": ["LOW", "MID", "HIGH"],
        "duration_ms": 120,
        "master_seed": 20260827,
        "output_namespace": "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/request-v2",
        "generator_config_sha256": "config-sha",
        "parent_artifacts": {"path": "path-sha"},
        "source_hashes": {"core": "core-sha"},
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
    }
    context = {"request": request, "output_dir": Path("C:/not-created"), "request_sha256": "request-sha", "backend": {}}
    summary = build_validation_summary(context)
    assert summary["elevation_bands"] == ["LOW", "MID", "HIGH"]
    assert summary["expected_rows"] == 1440
    assert summary["matlab_invoked"] is False
    assert summary["gold_labels_used_for_generation"] is False

