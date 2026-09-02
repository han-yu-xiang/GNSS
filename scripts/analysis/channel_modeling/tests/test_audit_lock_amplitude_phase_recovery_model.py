from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
AUDITOR_PATH = ROOT / "scripts" / "analysis" / "channel_modeling" / "audit_lock_amplitude_phase_recovery_model.py"


def load_auditor():
    assert AUDITOR_PATH.exists(), f"auditor is not implemented yet: {AUDITOR_PATH}"
    spec = importlib.util.spec_from_file_location("audit_lock_amplitude_phase_recovery_model", AUDITOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_auditor_module_is_available_after_red():
    assert AUDITOR_PATH.exists(), "The independent auditor must exist before auditor tests can pass."


def test_auditor_rejects_gold_selection_policy():
    auditor = load_auditor()
    with pytest.raises(ValueError):
        auditor.validate_manifest_policy({"gold_labels_used_for_selection": True})


def test_auditor_rejects_missing_required_artifact(tmp_path):
    auditor = load_auditor()
    with pytest.raises(FileNotFoundError):
        auditor.require_required_artifacts(tmp_path)


def test_auditor_rejects_nonmonotone_envelope():
    auditor = load_auditor()
    with pytest.raises(ValueError):
        auditor.validate_envelope_values([1.0, 0.4, 0.5], direction="entry")


def test_auditor_rejects_active_zero_amplitude():
    auditor = load_auditor()
    with pytest.raises(ValueError):
        auditor.validate_active_amplitude(0.0, mapping_mode="EMPIRICAL_DIAGNOSTIC_PROXY")

