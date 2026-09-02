from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.audit_nlos_slot_activation_model import (
    audit_activation_model,
)
from scripts.analysis.channel_modeling.build_nlos_slot_activation_model import (
    build_activation_model,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = PROJECT_ROOT / "configs" / "channel_modeling" / "nlos_slot_activation_v1.json"


def test_independent_audit_passes_fresh_model(tmp_path: Path):
    model_dir = tmp_path / "nlos-slot-model"
    build_activation_model(PROJECT_ROOT, CONFIG_PATH, model_dir, allow_test_namespace=True)
    result = audit_activation_model(PROJECT_ROOT, CONFIG_PATH, model_dir, allow_test_namespace=True)
    assert result.model_qa == "PASS_WITH_LIMITATIONS"
    assert result.ready_for_generator_composition == "YES"
    assert result.checks["source_counts"] == {
        "eligible_runs": 63,
        "stage0_windows": 169637,
        "confirmed_events": 94,
        "confirmed_paths": 100,
    }


def test_audit_rejects_tampered_manifest_hash(tmp_path: Path):
    model_dir = tmp_path / "nlos-slot-model"
    build_activation_model(PROJECT_ROOT, CONFIG_PATH, model_dir, allow_test_namespace=True)
    manifest_path = model_dir / "model_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_counts"]["confirmed_events"] = 95
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest|source counts|hash"):
        audit_activation_model(PROJECT_ROOT, CONFIG_PATH, model_dir, allow_test_namespace=True)


def test_audit_rejects_protected_namespace_before_reading_model():
    with pytest.raises(ValueError, match="protected"):
        audit_activation_model(PROJECT_ROOT, CONFIG_PATH, PROJECT_ROOT / "scenes" / "forbidden")
