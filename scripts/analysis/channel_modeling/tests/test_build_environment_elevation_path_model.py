from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.build_environment_elevation_path_model import (
    REQUIRED_OUTPUT_FILES,
    build_model,
    preflight,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = PROJECT_ROOT / "configs" / "channel_modeling" / "environment_elevation_path_distribution_v1.json"


def test_preflight_rejects_existing_or_protected_namespace(tmp_path: Path):
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        preflight(PROJECT_ROOT, CONFIG_PATH, output)

    protected = PROJECT_ROOT / "scenes" / "not-a-real-model-output"
    with pytest.raises(ValueError):
        preflight(PROJECT_ROOT, CONFIG_PATH, protected)


def test_build_output_schema_and_receipt(tmp_path: Path):
    output = tmp_path / "model"
    receipt = build_model(PROJECT_ROOT, CONFIG_PATH, output, allow_test_namespace=True)
    assert receipt.status == "COMPLETED"
    for name in REQUIRED_OUTPUT_FILES:
        assert (output / name).is_file(), name
    manifest = json.loads((output / "model_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_counts"] == {
        "environment_ready_paths": 100,
        "elevation_ready_paths": 84,
        "elevation_excluded_paths": 16,
    }
    assert manifest["execution_policy"]["raw_iq_read"] is False
    assert manifest["execution_policy"]["matlab"] is False
    assert manifest["execution_policy"]["sage"] is False
    assert manifest["gold_labels_used_for_selection"] is False
