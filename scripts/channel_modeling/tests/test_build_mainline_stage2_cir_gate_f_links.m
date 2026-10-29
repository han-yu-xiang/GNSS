function tests = test_build_mainline_stage2_cir_gate_f_links
tests = functiontests(localfunctions);
end

function testKeepsAllMpcRowsAndMapsAlphaAndWindowFeatures(testCase)
[stage2, alpha, features] = makeLedgerFixture();
result = build_mainline_stage2_cir_gate_f_links(stage2, alpha, features);

testCase.verifyEqual(height(result.stage2_window_features), 2);
testCase.verifyEqual(result.stage2_window_features.window_id, [1; 2]);
testCase.verifyEqual(result.stage2_window_features.stage2_path_count, [2; 1]);
testCase.verifyEqual(result.stage2_window_features.stage2_mpc_count, [1; 0]);
testCase.verifyTrue(all(result.stage2_window_features.cir_link_status == ...
    "CIR_PDP_VERIFIED"));
testCase.verifyEqual(height(result.stage2_mpc_linkage), 1);
testCase.verifyEqual(result.stage2_mpc_linkage.path_id, 2);
testCase.verifyEqual(result.stage2_mpc_linkage.sage_alpha_real, 0.5);
testCase.verifyEqual(result.stage2_mpc_linkage.sage_alpha_imag, 0.5);
testCase.verifyEqual(result.stage2_mpc_linkage.sage_alpha_status, "AVAILABLE");
testCase.verifyEqual(result.counts.stage2_path_rows, 3);
testCase.verifyEqual(result.counts.stage2_mpc_rows, 1);
testCase.verifyEqual(result.counts.alpha_missing_path_rows, 0);
end

function testSelectedWindowWithoutFeatureIsRetainedAsUnmatched(testCase)
[stage2, alpha, features] = makeLedgerFixture();
features = features(features.window_id == 1, :);
result = build_mainline_stage2_cir_gate_f_links(stage2, alpha, features);

testCase.verifyEqual(height(result.stage2_window_features), 2);
testCase.verifyEqual(result.stage2_window_features.cir_link_status, ...
    ["CIR_PDP_VERIFIED"; "NO_CIR_FEATURE"]);
testCase.verifyTrue(isfinite(result.stage2_window_features.pdp_peak_power(1)));
testCase.verifyTrue(isnan(result.stage2_window_features.pdp_peak_power(2)));
testCase.verifyEqual(height(result.stage2_mpc_linkage), 1);
testCase.verifyEqual(result.stage2_mpc_linkage.cir_link_status, ...
    "CIR_PDP_VERIFIED");
testCase.verifyEqual(result.counts.unmatched_stage2_windows, 1);
end

function testMissingAlphaDoesNotDropStage2Mpc(testCase)
[stage2, alpha, features] = makeLedgerFixture();
alpha = alpha(alpha.path_id == 1 | alpha.window_id == 2, :);
result = build_mainline_stage2_cir_gate_f_links(stage2, alpha, features);

testCase.verifyEqual(height(result.stage2_mpc_linkage), 1);
testCase.verifyEqual(result.stage2_mpc_linkage.path_id, 2);
testCase.verifyEqual(result.stage2_mpc_linkage.sage_alpha_status, ...
    "NO_ALPHA_RECORD");
testCase.verifyEqual(result.counts.alpha_missing_mpc_rows, 1);
end

function testDuplicatePathIdentityIsRejected(testCase)
[stage2, alpha, features] = makeLedgerFixture();
stage2 = [stage2; stage2(1, :)];
testCase.verifyError(@() build_mainline_stage2_cir_gate_f_links( ...
    stage2, alpha, features), ...
    'GNSS:SAGE:GateFStage2IdentityDuplicate');
end

function testAlphaAndStage2ParameterValuesAreIndependentlyChecked(testCase)
[stage2, alpha, features] = makeLedgerFixture();
alpha.relative_power_db(2) = alpha.relative_power_db(2) + 0.1;
testCase.verifyError(@() build_mainline_stage2_cir_gate_f_links( ...
    stage2, alpha, features), ...
    'GNSS:SAGE:GateFPathAttributeMismatch');
end

function testDirectReferenceRelativePowerIsIncludedInFullCheck(testCase)
[stage2, alpha, features] = makeLedgerFixture();
stage2.relative_power_db(1) = 0.25;
alpha.relative_power_db(1) = 0.25;
result = build_mainline_stage2_cir_gate_f_links(stage2, alpha, features);

testCase.verifyEqual(result.counts.relative_power_recomputed_mismatch, 0);
testCase.verifyEqual( ...
    result.counts.relative_power_recomputed_mismatch_all_rows, 1);
testCase.verifyEqual( ...
    result.counts.direct_reference_relative_power_mismatch, 1);
end

function testRejectsMatchedAlphaFromDifferentPrn(testCase)
[stage2, alpha, features] = makeLedgerFixture();
alpha.prn(2) = "G02";
testCase.verifyError(@() build_mainline_stage2_cir_gate_f_links( ...
    stage2, alpha, features), ...
    'GNSS:SAGE:GateFPathIdentityMismatch');
end

function [stage2, alpha, features] = makeLedgerFixture()
runId = repmat("run_a", 3, 1);
stage2 = table(runId, [1; 1; 2], [1; 2; 1], [0; 1; 0], ...
    [0; 1.8; 0], [0; -50; 0], [0; -3.010299956639812; 0], ...
    'VariableNames', {'run_id', 'window_id', 'path_id', ...
    'is_multipath', 'excess_delay_samples', 'doppler_offset_hz', ...
    'relative_power_db'});

alpha = table(runId, [1; 1; 2], [1; 2; 1], ...
    [1; 0.5; 2], [0; 0.5; 0], [1; sqrt(0.5); 2], ...
    [0; pi / 4; 0], repmat("AVAILABLE", 3, 1), ...
    repmat("PASS", 3, 1), [0; 1.8; 0], [0; -50; 0], ...
    [0; -3.010299956639812; 0], ...
    'VariableNames', {'run_id', 'window_id', 'path_id', ...
    'alpha_real', 'alpha_imag', 'alpha_magnitude', ...
    'alpha_phase_rad', 'alpha_status', ...
    'relative_power_check_status', 'excess_delay_samples', ...
    'doppler_offset_hz', 'relative_power_db'});

stage2.scene_id = repmat("scene_a", 3, 1);
stage2.prn = repmat("G01", 3, 1);
stage2.tracking_channel = ones(3, 1);
alpha.scene_id = repmat("scene_a", 3, 1);
alpha.prn = repmat("G01", 3, 1);
alpha.tracking_channel = ones(3, 1);

features = table(repmat("run_a", 2, 1), [1; 2], ...
    [10; 20], [40; 40], [0.25; 0.5], ...
    repmat("CIR_PDP_VERIFIED", 2, 1), ...
    'VariableNames', {'run_id', 'window_id', ...
    'pdp_peak_power', 'cir_snapshot_count', ...
    'pdp_rms_width_code_delay_samples', 'cir_link_status'});
end
