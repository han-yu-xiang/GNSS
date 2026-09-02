from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WRAPPER = ROOT / "scripts" / "sage_pipeline" / "rain" / "Invoke-RainSageFreshTask.ps1"
PREPARER = ROOT / "scripts" / "sage_pipeline" / "rain" / "prepare_rain_sage_fresh_request.py"
ENTRY = ROOT / "scripts" / "sage_pipeline" / "rain" / "run_rain_sage_fresh_task.m"


def test_wrapper_passes_the_complete_batch_expression_as_one_argument() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    assert "[System.Diagnostics.ProcessStartInfo]::new()" in source
    assert ".ArgumentList.Add('-batch')" in source or '.ArgumentList.Add("-batch")' in source
    assert ".ArgumentList.Add($expression)" in source
    assert "Start-Process -FilePath $MatlabExecutable -ArgumentList @('-batch', $expression)" not in source
    assert "Start-Process -FilePath $MatlabExecutable -ArgumentList @(" not in source


def test_wrapper_cannot_mark_zero_output_as_completed() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    assert "REQUIRED_OUTPUT_FILES" in source
    assert "missing_output_files" in source
    assert "FAILED_OUTPUT_MISSING" in source
    assert "required_output_files" in source


def test_wrapper_records_process_and_output_binding_provenance() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    assert "process_id" in source
    assert "output_namespace_exists" in source
    assert "output_files" in source
    assert "stdout_path" in source
    assert "stderr_path" in source


def test_wrapper_preserves_native_windows_paths_for_matlab_entry_contract() -> None:
    source = WRAPPER.read_text(encoding="utf-8")
    assert "return (Get-CanonicalPath $Path)" in source
    assert ".Replace('\\', '/')" not in source


def test_new_request_revision_does_not_reuse_prior_namespaces() -> None:
    source = PREPARER.read_text(encoding="utf-8")
    assert 'RERUN_REVISION = "r4"' in source
    assert 'OUTPUT_NAMESPACE_NAME = f"rain_sage_rerun_v1_20260827_{RERUN_REVISION}"' in source


def test_matlab_entry_uses_new_r4_namespace() -> None:
    source = ENTRY.read_text(encoding="utf-8")
    assert "rain_sage_rerun_v1_20260827_r4" in source
