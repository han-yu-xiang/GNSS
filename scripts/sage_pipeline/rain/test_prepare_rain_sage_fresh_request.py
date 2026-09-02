from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
PREPARER = ROOT / "scripts" / "sage_pipeline" / "rain" / "prepare_rain_sage_fresh_request.py"
FRESH_ENTRY = ROOT / "scripts" / "sage_pipeline" / "rain" / "run_rain_sage_fresh_task.m"
FRESH_WRAPPER = ROOT / "scripts" / "sage_pipeline" / "rain" / "Invoke-RainSageFreshTask.ps1"


def load_preparer():
    assert PREPARER.is_file(), "fresh request preparer must exist"
    spec = importlib.util.spec_from_file_location("rain_fresh_preparer", PREPARER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_request_uses_only_frozen_clear_g24_task():
    module = load_preparer()
    task = module.resolve_task(ROOT, "F1023_clear", "G24", 10)
    assert task["scene_id"] == "F1023_clear"
    assert task["prn"] == "G24"
    assert task["tracking_channel"] == 10
    assert task["sample_rate_hz"] == 10_230_000
    assert task["source"] == "rain_sage_9_task_checklist.csv"
    assert task["task_id"].endswith("__20260827_r4")


def test_fresh_namespace_is_distinct_from_old_rain_sage_v1():
    module = load_preparer()
    namespace = module.expected_output_namespace(ROOT, "F1023_clear", "G24")
    assert namespace.name == "G24"
    assert "rain_sage_rerun_v1_20260827_r4" in namespace.parts
    assert "rain_sage_v1" not in namespace.parts


def test_manifest_contract_is_new_only_and_explicitly_nonresumable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    module = load_preparer()
    synthetic_namespace = (
        tmp_path / "scenes" / "F1023_clear" / "sage_results"
        / "rain_sage_rerun_v1_20260827_r4" / "G24"
    )
    monkeypatch.setattr(
        module,
        "expected_output_namespace",
        lambda _root, _scene_id, _prn: synthetic_namespace,
    )
    manifest = module.build_manifest(
        ROOT,
        scene_id="F1023_clear",
        prn="G24",
        channel=10,
        request_dir=tmp_path / "request",
        compute_raw_hash=False,
    )
    assert manifest["execution"]["execution_mode"] == "new_only"
    assert manifest["execution"]["new_only"] is True
    assert manifest["execution"]["resume_allowed"] is False
    assert manifest["provenance"]["gold_labels_used_for_selection"] is False
    assert manifest["output"]["namespace"].endswith("rain_sage_rerun_v1_20260827_r4\\G24") or manifest["output"]["namespace"].endswith("rain_sage_rerun_v1_20260827_r4/G24")


def test_manifest_rejects_existing_namespace(tmp_path: Path):
    module = load_preparer()
    namespace = tmp_path / "scenes" / "F1023_clear" / "sage_results" / "rain_sage_rerun_v1_20260827_r1" / "G24"
    namespace.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        module.assert_output_namespace_absent(namespace)


def test_fresh_matlab_entry_cannot_resume_and_requires_explicit_output():
    assert FRESH_ENTRY.is_file(), "fresh MATLAB entry must exist"
    source = FRESH_ENTRY.read_text(encoding="utf-8")
    assert "function result = run_rain_sage_fresh_task" in source
    assert '"OutputDir"' in source
    assert "Resume=true" in source or "Resume', true" in source
    assert "rain_sage_rerun_v1_20260827_r4" in source


def test_fresh_wrapper_defaults_to_validation_and_requires_confirmation():
    assert FRESH_WRAPPER.is_file(), "fresh wrapper must exist"
    source = FRESH_WRAPPER.read_text(encoding="utf-8")
    assert "ConfirmRainSageRerun" in source
    assert "if (-not $Execute)" in source
    assert "matlab_invoked = $false" in source
    assert "ExpectedOutputNamespaceName" in source
    assert "Assert-GlobalMutexAvailable" in source
    assert "GLOBAL_LOCK=AVAILABLE" in source
