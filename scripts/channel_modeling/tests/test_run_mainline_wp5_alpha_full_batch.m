function tests = test_run_mainline_wp5_alpha_full_batch
tests = functiontests(localfunctions);
end

function testSerialBatchExportsEveryPathAndBuildsIntegratedLedger(testCase)
fixture = makeFixture();
cleanup = onCleanup(@() rmdir(fixture.root, 's')); %#ok<NASGU>
result = run_mainline_wp5_alpha_full_batch(fixture.projectRoot, fixture.outputRoot);
testCase.verifyEqual(result.status, "COMPLETE");
testCase.verifyEqual(result.run_count, 1);
testCase.verifyEqual(result.exported_run_count, 1);
testCase.verifyEqual(result.stage2_path_count, 2);
testCase.verifyEqual(result.stage2_window_count, 1);
testCase.verifyEqual(result.stage2_mpc_count, 1);
testCase.verifyEqual(result.stage2_direct_count, 1);

alpha = readtable(fullfile(fixture.outputRoot, fixture.runId, ...
    'stage2_alpha.csv'), 'Delimiter', ',', 'TextType', 'string');
ledger = readtable(fullfile(fixture.outputRoot, fixture.runId, ...
    'stage2_modeling_ledger.csv'), 'Delimiter', ',', 'TextType', 'string');
testCase.verifyEqual(height(alpha), 2);
testCase.verifyEqual(alpha.run_id, repmat(string(fixture.runId), 2, 1));
testCase.verifyEqual(alpha.window_id, [1; 1]);
testCase.verifyEqual(alpha.path_id, [1; 2]);
testCase.verifyEqual(alpha.alpha_status, ["AVAILABLE"; "AVAILABLE"]);
testCase.verifyEqual(alpha.relative_power_check_status, ["PASS"; "PASS"]);
testCase.verifyEqual(alpha.alpha_real, [1; 0.5], 'AbsTol', 1e-12);
testCase.verifyEqual(alpha.alpha_imag, [0; 0], 'AbsTol', 1e-12);
testCase.verifyEqual(height(ledger), 2);
testCase.verifyEqual(ledger.path_id, [1; 2]);
testCase.verifyEqual(height(readtable(fullfile(fixture.outputRoot, ...
    'stage2_alpha_all_paths.csv'), 'Delimiter', ',')), 2);
testCase.verifyEqual(height(readtable(fullfile(fixture.outputRoot, ...
    'stage2_modeling_ledger_all_paths.csv'), 'Delimiter', ',')), 2);
validation = validate_mainline_wp5_alpha_full_batch( ...
    fixture.projectRoot, fixture.outputRoot, fixture.task6LedgerPath, ...
    sha256File(fixture.task6LedgerPath));
testCase.verifyEqual(validation.status, "PASS");
testCase.verifyEqual(validation.stage2_path_count, 2);
testCase.verifyEqual(validation.alpha_available_count, 2);
testCase.verifyEqual(validation.path_identity_error_count, 0);
validationRuns = readtable(validation.independent_per_run_report, ...
    'Delimiter', ',', 'TextType', 'string');
testCase.verifyTrue(ismember('run_id', validationRuns.Properties.VariableNames));
testCase.verifyEqual(validationRuns.status, "PASS");
end

function testChangedInputIsRejectedBeforeRunOutputIsCreated(testCase)
fixture = makeFixture();
cleanup = onCleanup(@() rmdir(fixture.root, 's')); %#ok<NASGU>
fid = fopen(fixture.stage2MatPath, 'ab');
fwrite(fid, uint8(0));
fclose(fid);
result = run_mainline_wp5_alpha_full_batch(fixture.projectRoot, fixture.outputRoot);
testCase.verifyEqual(result.status, "PARTIAL");
testCase.verifyEqual(result.rejected_run_count, 1);
testCase.verifyFalse(isfolder(fullfile(fixture.outputRoot, fixture.runId)));
audit = readtable(fullfile(fixture.outputRoot, 'run_export_audit.csv'), ...
    'Delimiter', ',', 'TextType', 'string');
testCase.verifyEqual(audit.status, "REJECTED_INPUT_CHANGED");
testCase.verifyNotEmpty(audit.error_message);
end

function fixture = makeFixture()
fixture.root = tempname;
mkdir(fixture.root);
fixture.projectRoot = fullfile(fixture.root, 'project');
mkdir(fixture.projectRoot);
sourceDir = fullfile(fixture.projectRoot, 'scenes', 'Synthetic', ...
    'sage_results', 'frozen');
mkdir(sourceDir);
fixture.runId = 'run_20261003_Synthetic_G01_ch0';
fixture.stage2MatPath = fullfile(sourceDir, 'stage2.mat');
path1 = struct('alpha', 1 + 0i);
path2 = struct('alpha', 0.5 + 0i);
model = struct('paths', [path1; path2]);
models = cell(2, 1);
models{2} = model;
fit = struct('windowId', 1, 'selectedOrder', 2, 'models', {models});
stage2Fits = {fit}; %#ok<NASGU>
save(fixture.stage2MatPath, 'stage2Fits');

stage2 = table([1; 1], [2; 2], [1; 2], ...
    [0; -6.020599913279624], [0; 1], [0; 1], [0; 1], ...
    [0; 0.1], [0; 3], [0; 3], [10; 12], [0; 2], ...
    'VariableNames', {'window_id', 'selected_L', 'path_id', ...
    'relative_power_db', 'recording_time_s', 'is_multipath', ...
    'delay_samples', 'excess_delay_samples', 'excess_delay_chips', ...
    'excess_path_length_m', 'doppler_hz', 'doppler_offset_hz'});
fixture.stage2CsvPath = fullfile(sourceDir, 'stage2_selected_paths.csv');
writetable(stage2, fixture.stage2CsvPath);
fixture.task6LedgerPath = fullfile(fixture.projectRoot, 'stage2_ledger.csv');
ledgerSource = stage2;
ledgerSource.run_id = repmat(string(fixture.runId), 2, 1);
ledgerSource.scene_id = repmat("Synthetic", 2, 1);
ledgerSource.prn = repmat("G01", 2, 1);
ledgerSource.tracking_channel = zeros(2, 1);
ledgerSource.source_stage2_csv_sha256 = repmat( ...
    string(sha256File(fixture.stage2CsvPath)), 2, 1);
ledgerSource.stage2_source_row_number = [2; 3];
ledgerSource = movevars(ledgerSource, ...
    {'run_id', 'scene_id', 'prn', 'tracking_channel'}, 'Before', 1);
writetable(ledgerSource, fixture.task6LedgerPath);

fixture.stage3Path = fullfile(sourceDir, 'stage3_persistence.csv');
writetable(table(zeros(0,1), zeros(0,1), false(0,1), zeros(0,1), ...
    zeros(0,1), 'VariableNames', {'center_window_id', 'multipath_id', ...
    'persistence_pass', 'matched_window_count', ...
    'longest_consecutive_count'}), fixture.stage3Path);
fixture.reliablePath = fullfile(sourceDir, 'stage3_reliable_centers.csv');
writetable(table(zeros(0,1), 'VariableNames', {'center_window_id'}), ...
    fixture.reliablePath);
fixture.stage4SummaryPath = fullfile(sourceDir, 'stage4_joint_summary.csv');
writetable(table(zeros(0,1), false(0,1), zeros(0,1), ...
    'VariableNames', {'center_window_id', 'joint_valid', ...
    'joint_selected_L'}), fixture.stage4SummaryPath);
fixture.stage4PathsPath = fullfile(sourceDir, 'stage4_joint_paths.csv');
writetable(table(zeros(0,1), zeros(0,1), false(0,1), ...
    'VariableNames', {'center_window_id', 'path_id', 'is_multipath'}), ...
    fixture.stage4PathsPath);

sageFolder = fullfile(fixture.projectRoot, 'scripts', 'sage_pipeline');
mkdir(sageFolder);
fixture.sagePath = fullfile(sageFolder, 'run_nav_sage_pipeline.m');
writeBytes(fixture.sagePath, uint8('frozen source'));
fixture.outputRoot = fullfile(fixture.projectRoot, ...
    'dataset_generation_logs', 'channel_modeling', 'wp5_alpha_test');
mkdir(fixture.outputRoot);
manifest = table(string(fixture.runId), "Synthetic", "G01", 0, ...
    10230000, string(sha256File(fixture.sagePath)), ...
    string(fixture.stage2MatPath), string(sha256File(fixture.stage2MatPath)), ...
    string(fixture.stage2CsvPath), string(sha256File(fixture.stage2CsvPath)), ...
    string(fixture.stage3Path), string(sha256File(fixture.stage3Path)), ...
    string(fixture.reliablePath), string(sha256File(fixture.reliablePath)), ...
    string(fixture.stage4SummaryPath), string(sha256File(fixture.stage4SummaryPath)), ...
    string(fixture.stage4PathsPath), string(sha256File(fixture.stage4PathsPath)), ...
    2, 2, 1, 1, 1, "READY", "NONE", ...
    'VariableNames', {'run_id', 'scene_id', 'prn', 'tracking_channel', ...
    'sample_rate_hz', 'frozen_sage_sha256', 'stage2_mat_path', ...
    'stage2_mat_sha256', 'stage2_selected_paths_csv_path', ...
    'stage2_selected_paths_csv_sha256', 'stage3_persistence_csv_path', ...
    'stage3_persistence_csv_sha256', 'stage3_reliable_centers_csv_path', ...
    'stage3_reliable_centers_csv_sha256', 'stage4_joint_summary_csv_path', ...
    'stage4_joint_summary_csv_sha256', 'stage4_joint_paths_csv_path', ...
    'stage4_joint_paths_csv_sha256', 'expected_stage2_rows', ...
    'stage2_path_rows', 'stage2_window_count', 'stage2_mpc_count', ...
    'stage2_direct_count', 'preflight_status', 'preflight_reason'});
manifestPath = fullfile(fixture.outputRoot, 'input_manifest.csv');
writetable(manifest, manifestPath);
preflight = struct('status', 'PREFLIGHT_PASS', 'run_count', 1, ...
    'ready_run_count', 1, 'rejected_run_count', 0, ...
    'stage2_path_count', 2, 'stage2_window_count', 1, ...
    'stage2_mpc_count', 1, 'stage2_direct_count', 1, ...
    'input_manifest_sha256', sha256File(manifestPath));
fid = fopen(fullfile(fixture.outputRoot, 'source_preflight.json'), 'w');
fwrite(fid, jsonencode(preflight), 'char');
fclose(fid);
end

function writeBytes(path, bytes)
fid = fopen(path, 'wb');
fwrite(fid, bytes, 'uint8');
fclose(fid);
end

function sha = sha256File(path)
digest = java.security.MessageDigest.getInstance('SHA-256');
fid = fopen(path, 'rb');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
while true
    bytes = fread(fid, 1024 * 1024, '*uint8');
    if isempty(bytes), break; end
    digest.update(typecast(bytes(:), 'int8'));
end
raw = typecast(digest.digest(), 'uint8');
sha = lower(reshape(dec2hex(raw, 2).', 1, []));
end
