from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.audit_environment_elevation_path_model import audit_model
from scripts.analysis.channel_modeling.build_environment_elevation_path_model import build_model


PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = PROJECT_ROOT / "configs" / "channel_modeling" / "environment_elevation_path_distribution_v1.json"


def test_audit_accepts_built_model(tmp_path: Path):
    output = tmp_path / "model"
    build_model(PROJECT_ROOT, CONFIG_PATH, output, allow_test_namespace=True)
    result = audit_model(PROJECT_ROOT, CONFIG_PATH, output, allow_test_namespace=True)
    assert result.model_qa == "PASS_WITH_LIMITATIONS"
    assert result.ready_for_darkroom_generator_integration == "NO"


def test_audit_rejects_tampered_artifact(tmp_path: Path):
    output = tmp_path / "model"
    build_model(PROJECT_ROOT, CONFIG_PATH, output, allow_test_namespace=True)
    path = output / "cell_coverage.csv"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        audit_model(PROJECT_ROOT, CONFIG_PATH, output, allow_test_namespace=True)
