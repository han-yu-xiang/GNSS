from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.build_nlos_slot_activation_model import (
    REQUIRED_OUTPUT_FILES,
    build_activation_model,
    preflight,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = PROJECT_ROOT / "configs" / "channel_modeling" / "nlos_slot_activation_v1.json"


def test_preflight_rejects_existing_output_without_modification(tmp_path: Path):
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "marker.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError, match="new-only"):
        preflight(PROJECT_ROOT, CONFIG_PATH, output, allow_test_namespace=True)
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_preflight_rejects_protected_or_old_namespaces():
    with pytest.raises(ValueError, match="scenes|sage_results"):
        preflight(PROJECT_ROOT, CONFIG_PATH, PROJECT_ROOT / "scenes" / "forbidden", allow_test_namespace=True)
    with pytest.raises(ValueError, match="_trash"):
        preflight(PROJECT_ROOT, CONFIG_PATH, PROJECT_ROOT / "_trash" / "forbidden", allow_test_namespace=True)


def test_validate_only_recomputes_frozen_source_accounting_without_output(tmp_path: Path):
    output = tmp_path / "validation-only"
    info = preflight(PROJECT_ROOT, CONFIG_PATH, output, allow_test_namespace=True)
    assert info["output_exists"] is False
    assert info["source_counts"] == {
        "eligible_runs": 63,
        "stage0_windows": 169637,
        "confirmed_events": 94,
        "confirmed_paths": 100,
    }
    assert not output.exists()


def test_build_publishes_required_artifacts_and_receipt(tmp_path: Path):
    output = tmp_path / "nlos-slot-model"
    receipt = build_activation_model(PROJECT_ROOT, CONFIG_PATH, output, allow_test_namespace=True)
    assert receipt.status == "COMPLETED_WITH_LIMITATIONS"
    assert set(REQUIRED_OUTPUT_FILES).issubset({path.name for path in output.iterdir()})
    manifest = json.loads((output / "model_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_counts"] == {
        "eligible_runs": 63,
        "stage0_windows": 169637,
        "confirmed_events": 94,
        "confirmed_paths": 100,
    }
    assert manifest["execution_policy"]["raw_iq_read"] is False
    assert manifest["execution_policy"]["matlab"] is False
    assert manifest["execution_policy"]["sage"] is False
    assert manifest["execution_policy"]["batch"] is False
    assert manifest["execution_policy"]["process_20_46_mhz"] is False
    assert manifest["gold_labels_used_for_selection"] is False
