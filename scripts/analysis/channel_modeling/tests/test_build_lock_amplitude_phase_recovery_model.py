from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
BUILDER_PATH = ROOT / "scripts" / "analysis" / "channel_modeling" / "build_lock_amplitude_phase_recovery_model.py"


def load_builder():
    assert BUILDER_PATH.exists(), f"builder is not implemented yet: {BUILDER_PATH}"
    spec = importlib.util.spec_from_file_location("build_lock_amplitude_phase_recovery_model", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_builder_module_is_available_after_red():
    assert BUILDER_PATH.exists(), "The v1 builder must exist before builder tests can pass."


def test_recovery_fit_marks_no_observation_as_assumption_fallback():
    builder = load_builder()
    result = builder.fit_recovery_parameters([], [])
    assert result["support_status"] == "ASSUMPTION_ONLY_REACQUISITION_DEBOUNCE_FALLBACK"
    assert result["duration_source"] == "fixed_100ms_fallback"
    assert result["duration_ms"] == 100


def test_recovery_fit_uses_observed_environment_values_without_gold_input():
    builder = load_builder()
    result = builder.fit_recovery_parameters([0.10, 0.20, 0.30], ["scene-a", "scene-a", "scene-b"])
    assert result["observed_count"] == 3
    assert result["duration_source"] == "environment_observed_or_parent"
    assert result["duration_ms"] > 0
    assert result["gold_labels_used_for_selection"] is False


def test_recovery_shape_selection_is_invariant_to_dB_translation():
    builder = load_builder()
    trace = [(0.0, -31.0), (0.5, -30.5), (1.0, -30.0)]
    shifted_trace = [(progress, value + 20.0) for progress, value in trace]
    base = builder.select_recovery_shape([trace])
    shifted = builder.select_recovery_shape([shifted_trace])
    assert shifted["selected_shape"] == base["selected_shape"]
    assert shifted["candidate_rmse"] == pytest.approx(base["candidate_rmse"])


def test_manifest_output_hashes_exclude_manifest_and_receipt_self_references(tmp_path):
    builder = load_builder()
    for name in builder.OUTPUT_FILES:
        if name not in {"model_manifest.json", "build_receipt.json"}:
            (tmp_path / name).write_bytes(name.encode("utf-8"))
    hashes = builder.manifest_output_hashes(tmp_path)
    assert "model_manifest.json" not in hashes
    assert "build_receipt.json" not in hashes
    assert hashes


def test_namespace_validator_rejects_existing_output(tmp_path):
    builder = load_builder()
    existing = tmp_path / "dataset_generation_logs" / "channel_modeling" / "existing"
    existing.parent.mkdir(parents=True)
    existing.mkdir()
    with pytest.raises(FileExistsError):
        builder.require_new_only_namespace(existing, tmp_path)


def test_namespace_validator_rejects_path_outside_channel_modeling(tmp_path):
    builder = load_builder()
    outside = tmp_path / "outside"
    with pytest.raises(ValueError):
        builder.require_new_only_namespace(outside, tmp_path / "project")
