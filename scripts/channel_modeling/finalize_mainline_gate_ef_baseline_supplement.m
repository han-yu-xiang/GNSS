function summary = finalize_mainline_gate_ef_baseline_supplement( ...
    baseAuditDirectory, supplementDirectory, ...
    stage2LedgerPath, alphaLedgerPath, outputDirectory)
%FINALIZE_MAINLINE_GATE_EF_BASELINE_SUPPLEMENT Bind one legacy baseline audit
% to a complete cohort audit without rereading the other 82 HDF5 files.
% The base and supplement are immutable inputs; only outputDirectory is written.

baseAuditDirectory = canonicalPath(baseAuditDirectory);
supplementDirectory = canonicalPath(supplementDirectory);
stage2LedgerPath = canonicalPath(stage2LedgerPath);
alphaLedgerPath = canonicalPath(alphaLedgerPath);
outputDirectory = canonicalPath(outputDirectory);
assert(isfolder(baseAuditDirectory) && isfolder(supplementDirectory) ...
    && isfile(stage2LedgerPath) && isfile(alphaLedgerPath) ...
    && ~isfolder(outputDirectory) && ~isfile(outputDirectory), ...
    'GNSS:SAGE:GateEFinalizePathInvalid', ...
    'Input audit files must exist and outputDirectory must be new.');
[ok, message] = mkdir(outputDirectory);
assert(ok, 'GNSS:SAGE:GateEFinalizeOutputCreateFailed', '%s', message);
diary(fullfile(outputDirectory, 'gate_e_f_finalization.log'));
fprintf('GATE_EF_FINALIZATION_BEGIN_UTC=%s\n', utcNow());
fprintf('BASE_AUDIT=%s\nSUPPLEMENT=%s\n', baseAuditDirectory, supplementDirectory);

legacyRunId = "run_20261003_F1023_V70_D0117_P2_G28_ch1";
baseInventory = readAuditTable(baseAuditDirectory, 'gate_e_run_inventory.csv');
supplementInventory = readAuditTable(supplementDirectory, 'gate_e_run_inventory.csv');
baseWindows = readAuditTable(baseAuditDirectory, 'stage2_cir_pdp_window_features.csv');
supplementWindows = readAuditTable(supplementDirectory, 'stage2_cir_pdp_window_features.csv');
baseAnomalies = readAuditTable(baseAuditDirectory, 'gate_e_f_anomalies.csv');
supplementAnomalies = readAuditTable(supplementDirectory, 'gate_e_f_anomalies.csv');
baseSummary = readJson(fullfile(baseAuditDirectory, 'gate_e_f_summary.json'));
supplementSummary = readJson(fullfile(supplementDirectory, 'gate_e_f_summary.json'));

assert(height(baseInventory) == 83 && height(supplementInventory) == 1 ...
    && string(supplementInventory.run_id(1)) == legacyRunId ...
    && height(baseWindows) == 7847 && height(supplementWindows) == 7847 ...
    && string(baseSummary.gate_e_status) == "FAIL" ...
    && string(baseSummary.gate_f_status) == "FAIL" ...
    && string(supplementSummary.audit_scope) == "SELECTED_RUN_SUPPLEMENT", ...
    'GNSS:SAGE:GateEFinalizeScopeMismatch', ...
    'Expected a complete 83-run base audit and exactly one selected-run supplement.');

baseRunIds = string(baseInventory.run_id);
assert(numel(unique(baseRunIds)) == 83 ...
    && sum(string(baseInventory.gate_e) == "FAIL") == 1 ...
    && sum(string(baseInventory.run_id) == legacyRunId ...
        & string(baseInventory.gate_e) == "FAIL") == 1 ...
    && sum(string(baseInventory.run_id) == legacyRunId ...
        & string(baseInventory.gate_f) == "NOT_VERIFIED") == 1 ...
    && string(supplementInventory.gate_e(1)) == "PASS_WITH_LIMITATIONS" ...
    && string(supplementInventory.gate_f(1)) == "PASS" ...
    && string(supplementInventory.pdp_status(1)) == "PASS" ...
    && double(supplementInventory.stage0_windows(1)) == 898 ...
    && double(supplementInventory.cir_snapshots(1)) == 35920 ...
    && double(supplementInventory.delay_bins(1)) == 451 ...
    && double(supplementInventory.stage2_windows(1)) == 54 ...
    && double(supplementInventory.stage2_mpc(1)) == 23, ...
    'GNSS:SAGE:GateEFinalizeEvidenceMismatch', ...
    'Base failure or baseline supplement does not match the authorized legacy run.');
supplementLimitation = string(supplementInventory.limitations(1));
assert(strlength(supplementLimitation) > 0 && supplementLimitation ~= "NaN", ...
    'GNSS:SAGE:GateEFinalizeLimitationMissing', ...
    'The legacy baseline limitation must be preserved as explicit text.');
baseInventory.limitations = repmat("NONE", height(baseInventory), 1);
supplementInventory.limitations = string(supplementInventory.limitations);

baseKeys = windowKey(baseWindows.run_id, baseWindows.window_id);
supplementKeys = windowKey(supplementWindows.run_id, supplementWindows.window_id);
legacyMask = string(baseWindows.run_id) == legacyRunId;
supplementLegacyMask = string(supplementWindows.run_id) == legacyRunId;
assert(sum(legacyMask) == 54 && sum(supplementLegacyMask) == 54 ...
    && all(string(baseWindows.cir_link_status(legacyMask)) == "HDF5_AUDIT_FAILED") ...
    && all(string(supplementWindows.cir_link_status(supplementLegacyMask)) ...
        == "CIR_PDP_VERIFIED") ...
    && isequal(baseKeys, supplementKeys), ...
    'GNSS:SAGE:GateEFinalizeWindowMismatch', ...
    'The supplement must replace exactly the same 54 legacy baseline windows.');

stage2 = readAuditTableFromPath(stage2LedgerPath);
alpha = readAuditTableFromPath(alphaLedgerPath);
assert(height(stage2) == 16761 && height(alpha) == 16761 ...
    && numel(unique(pathKey(stage2.run_id, stage2.window_id, stage2.path_id))) == 16761, ...
    'GNSS:SAGE:GateEFinalizeLedgerMismatch', ...
    'Frozen Stage2/alpha path identities are incomplete or duplicated.');

baseInventory(string(baseInventory.run_id) == legacyRunId, :) = supplementInventory;
baseWindows(legacyMask, :) = supplementWindows(supplementLegacyMask, :);
assert(all(ismember(string(baseInventory.gate_e), ...
    ["PASS", "PASS_WITH_LIMITATIONS"])) ...
    && all(string(baseInventory.gate_f) == "PASS") ...
    && all(string(baseWindows.cir_link_status) == "CIR_PDP_VERIFIED"), ...
    'GNSS:SAGE:GateEFinalizeIncomplete', ...
    'Combined inventory still contains a failed run or unverified Stage2 window.');

links = build_mainline_stage2_cir_gate_f_links(stage2, alpha, baseWindows);
assert(height(links.stage2_window_features) == 7847 ...
    && height(links.stage2_mpc_linkage) == 8914 ...
    && links.counts.stage2_path_rows == 16761 ...
    && links.counts.unmatched_stage2_windows == 0 ...
    && links.counts.alpha_missing_mpc_rows == 0 ...
    && links.counts.alpha_unavailable_path_rows == 0 ...
    && links.counts.relative_power_recomputed_mismatch_all_rows == 0, ...
    'GNSS:SAGE:GateEFinalizeJoinFailed', ...
    'The final lossless Stage2/CIR/alpha identity join failed validation.');

baseAnomalies(string(baseAnomalies.run_id) == legacyRunId, :) = [];
anomalies = [baseAnomalies; supplementAnomalies];
assert(height(anomalies) == 0, 'GNSS:SAGE:GateEFinalizeAnomalyExists', ...
    'Anomalies remain after applying the targeted baseline supplement.');

linked = sum(string(links.stage2_window_features.cir_link_status) ...
    == "CIR_PDP_VERIFIED");
boundary = sum(logical(links.stage2_window_features.pdp_peak_at_grid_boundary));
summary = baseSummary;
summary.created_utc = utcNow();
summary.gate_e_status = 'PASS_WITH_LIMITATIONS';
summary.gate_f_status = 'PASS_WITH_LIMITATIONS';
summary.cir_linked_stage2_windows = linked;
summary.unmatched_stage2_windows = links.counts.unmatched_stage2_windows;
summary.unmatched_mpc_alpha = links.counts.alpha_missing_mpc_rows;
summary.alpha_missing_stage2_path_rows = links.counts.alpha_missing_path_rows;
summary.alpha_unavailable_stage2_path_rows = links.counts.alpha_unavailable_path_rows;
summary.relative_power_recomputed_pass = links.counts.relative_power_recomputed_pass;
summary.relative_power_recomputed_mismatch = links.counts.relative_power_recomputed_mismatch;
summary.relative_power_recomputed_pass_all_rows = links.counts.relative_power_recomputed_pass_all_rows;
summary.relative_power_recomputed_mismatch_all_rows = links.counts.relative_power_recomputed_mismatch_all_rows;
summary.direct_reference_relative_power_mismatch = links.counts.direct_reference_relative_power_mismatch;
summary.pdp_boundary_peak_windows = boundary;
summary.pdp_boundary_peak_fraction = boundary / max(linked, 1);
summary.max_pdp_abs_difference = maxFinite(baseInventory.pdp_max_abs_diff);
summary.max_pdp_relative_difference = maxFinite(baseInventory.pdp_max_rel_diff);
summary.pdp_recomputation_absolute_tolerance = maxFinite(baseInventory.pdp_absolute_tolerance);
summary.pdp_recomputation_relative_tolerance = maxFinite(baseInventory.pdp_relative_tolerance);
summary.alpha_math_checked_path_rows = links.counts.alpha_math_checked_paths;
summary.alpha_extra_path_rows = links.counts.alpha_extra_rows;
summary.mpc_count_distribution = mpcDistribution( ...
    links.stage2_window_features.stage2_mpc_count);
summary.finalization_record_type = 'FULL_AUDIT_WITH_TARGETED_LEGACY_BASELINE_SUPPLEMENT';
summary.baseline_supplement_run_id = char(legacyRunId);
summary.baseline_supplement_directory = supplementDirectory;
summary.baseline_source_limitations = char(supplementLimitation);
summary.audit_execution_code_provenance = ['The full-cohort audit runner SHA was not captured at process start. ' ...
    'The runner SHA in execution_manifest is the corrected runner used for the targeted legacy-baseline supplement; ' ...
    'the streamed CIR/PDP auditor, identity linker and SHA utility are bound by current source hashes.'];
scienceLimitations = string(summary.scientific_limitations);
scienceLimitations(end) = supplementLimitation;
summary.scientific_limitations = cellstr(scienceLimitations);

sceneSummary = summarizeScenes(stage2, links.stage2_window_features);
writetable(baseInventory, fullfile(outputDirectory, 'gate_e_run_inventory.csv'));
writetable(links.stage2_window_features, fullfile(outputDirectory, 'stage2_cir_pdp_window_features.csv'));
writetable(links.stage2_mpc_linkage, fullfile(outputDirectory, 'stage2_mpc_cir_alpha_linkage.csv'));
writetable(sceneSummary, fullfile(outputDirectory, 'gate_f_scene_summary.csv'));
writetable(anomalies, fullfile(outputDirectory, 'gate_e_f_anomalies.csv'));
writeJson(fullfile(outputDirectory, 'gate_e_f_summary.json'), summary);

baseManifest = readJson(fullfile(baseAuditDirectory, 'execution_manifest.json'));
supplementManifest = readJson(fullfile(supplementDirectory, 'execution_manifest.json'));
baseManifest.record_type = 'FULL_AUDIT_WITH_TARGETED_LEGACY_BASELINE_SUPPLEMENT';
baseManifest.base_audit_directory = baseAuditDirectory;
baseManifest.base_audit_log_sha256 = sha256File(fullfile(baseAuditDirectory, 'gate_e_f_execution.log'));
baseManifest.supplement_directory = supplementDirectory;
baseManifest.supplement_audit_log_sha256 = sha256File(fullfile(supplementDirectory, 'gate_e_f_execution.log'));
baseManifest.supplement_summary_sha256 = sha256File(fullfile(supplementDirectory, 'gate_e_f_summary.json'));
baseManifest.baseline_run_id = char(legacyRunId);
baseManifest.finalizer_source_sha256 = sha256File(which('finalize_mainline_gate_ef_baseline_supplement'));
baseManifest.baseline_receipt_sha256 = char(supplementInventory.receipt_sha_actual(1));
baseManifest.baseline_hdf5_sha256_observed = char(supplementInventory.hdf5_sha_actual(1));
baseManifest.supplement_request_sha256 = char(supplementManifest.request_sha256);
baseManifest.base_audit_runner_source_sha256 = 'NOT_CAPTURED_AT_PROCESS_START';
baseManifest.supplement_runner_source_sha256 = sha256File(which('run_mainline_1023_gate_ef_audit'));
baseManifest.cir_pdp_auditor_source_sha256 = sha256File(which('audit_gnss_code_domain_cir_pdp'));
baseManifest.identity_linker_source_sha256 = sha256File(which('build_mainline_stage2_cir_gate_f_links'));
baseManifest.sha256_utility_source_sha256 = sha256File(which('sha256_file_streaming'));
baseManifest.full_cohort_run_count = height(baseInventory);
baseManifest.full_stage2_window_count = height(links.stage2_window_features);
baseManifest.full_stage2_mpc_count = height(links.stage2_mpc_linkage);
baseManifest.finalization_log_path = fullfile(outputDirectory, 'gate_e_f_finalization.log');
writeJson(fullfile(outputDirectory, 'execution_manifest.json'), baseManifest);
writeJson(fullfile(outputDirectory, 'base_summary_sha256.json'), ...
    struct('base_summary_sha256', sha256File(fullfile(baseAuditDirectory, 'gate_e_f_summary.json'))));
fprintf('GATE_EF_FINALIZE_STATUS=%s\n', summary.gate_e_status);
fprintf('GATE_F_FINALIZE_STATUS=%s\n', summary.gate_f_status);
fprintf('GATE_EF_FINALIZE_COUNTS runs=%d windows=%d linked=%d paths=%d mpc=%d unmatched=%d alphaMissing=%d anomalies=%d boundary=%d/%d\n', ...
    height(baseInventory), height(links.stage2_window_features), linked, ...
    links.counts.stage2_path_rows, height(links.stage2_mpc_linkage), ...
    links.counts.unmatched_stage2_windows, links.counts.alpha_missing_mpc_rows, ...
    height(anomalies), boundary, linked);
fprintf('GATE_EF_FINALIZATION_END_UTC=%s\n', utcNow());
diary off;
baseManifest.finalization_log_sha256 = sha256File(fullfile(outputDirectory, 'gate_e_f_finalization.log'));
baseManifest.final_summary_sha256 = sha256File(fullfile(outputDirectory, 'gate_e_f_summary.json'));
baseManifest.final_inventory_sha256 = sha256File(fullfile(outputDirectory, 'gate_e_run_inventory.csv'));
baseManifest.final_window_features_sha256 = sha256File(fullfile(outputDirectory, 'stage2_cir_pdp_window_features.csv'));
baseManifest.final_mpc_linkage_sha256 = sha256File(fullfile(outputDirectory, 'stage2_mpc_cir_alpha_linkage.csv'));
baseManifest.final_scene_summary_sha256 = sha256File(fullfile(outputDirectory, 'gate_f_scene_summary.csv'));
writeJson(fullfile(outputDirectory, 'execution_manifest.json'), baseManifest);
end

function t = readAuditTable(folder, name)
t = readAuditTableFromPath(fullfile(folder, name));
end

function t = readAuditTableFromPath(path)
t = readtable(path, 'Delimiter', ',', 'ReadVariableNames', true, ...
    'TextType', 'string', 'VariableNamingRule', 'preserve');
end

function s = summarizeScenes(stage2, windows)
scenes = unique(string(stage2.scene_id), 'stable');
n = numel(scenes);
runIds = strings(n,1); runs = zeros(n,1); selected = zeros(n,1);
linked = zeros(n,1); mpcs = zeros(n,1); boundary = zeros(n,1);
for k = 1:n
    scene = scenes(k);
    stageMask = string(stage2.scene_id) == scene;
    runSet = unique(string(stage2.run_id(stageMask)), 'stable');
    runIds(k) = strjoin(runSet, '|');
    runs(k) = numel(runSet);
    winMask = string(windows.scene_id) == scene;
    selected(k) = sum(winMask);
    linked(k) = sum(winMask & string(windows.cir_link_status) == "CIR_PDP_VERIFIED");
    mpcs(k) = sum(numericColumn(stage2.is_multipath(stageMask)) == 1);
    boundary(k) = sum(winMask & logical(windows.pdp_peak_at_grid_boundary));
end
s = table(scenes, runIds, runs, selected, linked, linked ./ max(selected,1), ...
    mpcs, boundary, 'VariableNames', {'scene_id','run_ids','run_count', ...
    'stage2_selected_windows','cir_linked_windows','cir_coverage', ...
    'stage2_mpc_count','pdp_boundary_peak_windows'});
end

function labels = mpcDistribution(counts)
counts = double(counts(:));
labels = struct('labels', {{'0','1','2','3','4+'}}, ...
    'window_counts', {[sum(counts==0),sum(counts==1),sum(counts==2), ...
    sum(counts==3),sum(counts>=4)]});
end

function value = maxFinite(values)
values = double(values(:)); values = values(isfinite(values));
if isempty(values), value = NaN; else, value = max(values); end
end

function values = numericColumn(values)
if iscell(values), values = string(values); end
if isstring(values) || ischar(values) || iscategorical(values)
    values = str2double(string(values));
end
values = double(values(:));
end

function key = windowKey(runId, windowId)
key = string(runId(:)) + "|" + string(double(windowId(:)));
end

function key = pathKey(runId, windowId, pathId)
key = string(runId(:)) + "|" + string(double(windowId(:))) + "|" ...
    + string(double(pathId(:)));
end

function path = canonicalPath(value)
path = char(java.io.File(char(value)).getCanonicalPath());
end

function value = readJson(path)
value = jsondecode(fileread(path));
end

function digest = sha256File(path)
digest = sha256_file_streaming(path);
end

function value = utcNow()
value = char(datetime('now','TimeZone','UTC', ...
    'Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
end

function writeJson(path, value)
fid = fopen(path, 'wt', 'n', 'UTF-8');
assert(fid >= 0, 'GNSS:SAGE:GateEFinalizeWriteFailed', ...
    'Unable to create JSON result file.');
cleanup = onCleanup(@() fclose(fid));
fwrite(fid, jsonencode(value, 'PrettyPrint', true), 'char');
fwrite(fid, newline, 'char');
clear cleanup;
end
