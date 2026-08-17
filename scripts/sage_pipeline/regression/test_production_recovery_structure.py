"""Static guards for the validated-equivalent monolithic production route."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PRODUCTION = ROOT / "scripts" / "sage_pipeline" / "run_nav_sage_pipeline.m"
SMOKE = ROOT / "scripts" / "sage_pipeline" / "regression" / "run_production_matlab_syntax_smoke.m"
HARNESS = ROOT / "scripts" / "sage_pipeline" / "regression" / "run_production_recovery_regression.m"


def test_production_entry_is_self_contained_for_stage1_to_stage4():
    text = PRODUCTION.read_text(encoding="utf-8")
    assert "coreDirectory" not in text
    assert "run_sage_stage1_stage4_core" not in text
    assert "addpath(core" not in text
    assert "function result = run_sage_stage1_stage4_local" in text
    assert "function cfg = default_sage_configuration" in text
    assert "function [boundHz, source] = compute_sage_doppler_bound" in text


def test_production_contains_required_local_stage_functions():
    text = PRODUCTION.read_text(encoding="utf-8")
    for name in (
        "runFastScan",
        "runStage2",
        "evaluatePersistence",
        "runJointStage",
        "optimizeJointPaths",
        "loadNavWipedFortyMs",
        "gridSearchPath",
        "generateGpsCaCode",
    ):
        assert f"function" in text and name in text


def test_production_preserves_confirmed_criterion_and_resume_interface():
    text = PRODUCTION.read_text(encoding="utf-8")
    assert "joint_multipath_count" in text
    assert "is_multipath" in text
    assert 'addParameter(parser, "Resume"' in text
    assert "resumeExistingStages" in text


def test_production_smoke_is_parse_only_and_warning_tolerant():
    text = SMOKE.read_text(encoding="utf-8")
    assert "checkcode" in text
    assert "PRODUCTION_MATLAB_SYNTAX_SMOKE=PASS" in text
    assert '"raw_iq_opened", false' in text
    assert '"sage_executed", false' in text
    assert "error_count" in text


def test_production_recovery_harness_is_g28_new_only_and_resume_false():
    text = HARNESS.read_text(encoding="utf-8")
    assert 'prnLabel = "G28"' in text
    assert "trackingChannel = 1" in text
    assert '"execution_mode", "new_only"' in text
    assert '"resume", false' in text
    assert '"Resume", false' in text
    assert '"sage_results", "nav_sage_v2", prnLabel' in text
    assert "stageResult = run_nav_sage_pipeline" in text
    assert "isscalar(stageResult)" in text
    assert "PRODUCTION_REFACTOR_REGRESSION=PASS" in text
    assert "run_sage_stage1_stage4_core" not in text


def test_production_recovery_harness_compares_stage0_and_stage1_identity():
    text = HARNESS.read_text(encoding="utf-8")
    assert "compareStage0Catalogs" in text
    assert "stage1CandidateIds(stage1)" in text
    assert "stage1CandidateIds(stage1Actual)" in text
    assert "baseline_unchanged" in text


def test_production_recovery_harness_has_read_only_existing_output_mode():
    text = HARNESS.read_text(encoding="utf-8")
    assert 'addParameter(parser, "CompareExistingActualDir"' in text
    assert 'comparisonMode = "existing_output_read_only"' in text
    assert "validateActualContext" in text
    assert "isPathWithinRoot" in text
    assert '"raw_iq_opened", false' in text
    assert '"sage_executed", false' in text


def test_comparator_normalizes_cell_and_string_table_variable_names():
    text = HARNESS.read_text(encoding="utf-8")
    assert "normalizeTableVariableNames" in text
    assert "scalarTableVariableName" in text
    assert "baselineNames = normalizeTableVariableNames" in text
    assert "actualNames = normalizeTableVariableNames" in text
    assert "for nameIndex = 1:numel(baselineNames)" in text
    assert "for nameIndex = 1:numel(exactNames)" in text


def test_local_stage_result_container_is_scalar_and_preserves_cell_outputs():
    text = PRODUCTION.read_text(encoding="utf-8")
    start = text.index("function result = run_sage_stage1_stage4_local")
    end = text.index("function signUsed = determineDopplerSign", start)
    local_body = text[start:end]

    assert "result = struct();" in local_body
    assert "result.stage2Fits = stage2Fits;" in local_body
    assert "result.jointFits = jointFits;" in local_body
    assert "assert(isstruct(result) && isscalar(result)" in local_body
    assert 'result = struct( ...' not in local_body
