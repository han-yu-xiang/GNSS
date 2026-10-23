function tests = test_mainline_cir_multi_identity
% Regression: accept a second frozen identity and a non-pilot window count.
tests = functiontests(localfunctions);
end

function testNonPilotIdentityAndTwoWindowsExportAndValidate(testCase)
fixture = makeExporterFixture(testCase, 10230000);
summary = exportFixture(fixture);
validation = validate_gnss_code_domain_cir(fixture.hdf5Path, 2);

testCase.verifyEqual(summary.scene_id, 'F1023_V70_D0117_P4');
testCase.verifyEqual(summary.prn, 'G31');
testCase.verifyEqual(summary.tracking_channel, 1);
testCase.verifyEqual(summary.stage0_window_count, 2);
testCase.verifyEqual(summary.cir_snapshot_count, 80);
testCase.verifyEqual(summary.unique_cir_snapshot_start_samples, 60);
testCase.verifyEqual(summary.delay_grid_count, 451);
testCase.verifyEqual(validation.snapshot_count, 80);
testCase.verifyEqual(validation.pdp_window_count, 2);
testCase.verifyTrue(validation.pdp_mean_exactly_recomputed);
testCase.verifyTrue(isfile(fixture.hdf5Path));
testCase.verifyTrue(isfile(fixture.metadataPath));
testCase.verifyTrue(isfile(fixture.comparisonPath));
end

function testSyntheticFixtureCopiesPinnedFrozenSources(testCase)
fixture = makeExporterFixture(testCase, 10230000);
entryPath = fullfile(fixture.projectRoot, 'scripts', 'sage_pipeline', ...
    'run_nav_sage_pipeline.m');
configurationPath = fullfile(fixture.projectRoot, 'scripts', ...
    'sage_pipeline', 'core', 'default_sage_configuration.m');
testCase.verifyEqual(sha256File(entryPath), ...
    'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c');
testCase.verifyEqual(sha256File(configurationPath), ...
    'ac06ad3191ca7ca05480fb84c0465a5082c157f4eaad1ae3018e26e1abed1319');
end

function testIdentityMustMatchFrozenCirTasksRow(testCase)
fixture = makeExporterFixture(testCase, 10230000);
fixture.provenance.tracking_channel = 4;
testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIRIdentityAuthorizationMismatch');
end

function testHeterogeneousCohortRowsSelectExactTask(testCase)
fixture = makeExporterFixture(testCase, 10230000);
newTask = fixture.cohortDocument.tasks;
existingPilotTask = newTask;
existingPilotTask.run_id = 'run_20261003_F1023_V70_D0117_P2_G28_ch1';
existingPilotTask.scene_id = 'F1023_V70_D0117_P2';
existingPilotTask.prn = 'G28';
existingPilotTask.tracking_channel = 1;
existingPilotTask.output_namespace = ...
    'scenes/F1023_V70_D0117_P2/sage_results/rerun_20261003_frozen_v3/G28_ch1';
existingPilotTask.source_summary_status = 'ALREADY_COMPLETE';
existingPilotTask.existing_cir_pilot = struct( ...
    'status', 'EXISTING_VALIDATED');
fixture.cohortDocument.eligible_count = 2;
fixture.cohortDocument.tasks = {newTask, existingPilotTask};
writeJsonFile(fixture.cohortPath, fixture.cohortDocument, testCase);
fixture.cohortSha256 = sha256File(fixture.cohortPath);
fixture.taskDocument.source_cohort_sha256 = fixture.cohortSha256;
writeJsonFile(fixture.cirTasksPath, fixture.taskDocument, testCase);
fixture.provenance.cohort_sha256 = fixture.cohortSha256;
fixture.provenance.cir_tasks_sha256 = sha256File(fixture.cirTasksPath);

decodedCohort = jsondecode(fileread(fixture.cohortPath));
testCase.verifyTrue(iscell(decodedCohort.tasks), ...
    'Different per-task metadata must preserve heterogeneous JSON rows.');
summary = exportFixture(fixture);

testCase.verifyEqual(summary.scene_id, fixture.provenance.scene_id);
testCase.verifyEqual(summary.prn, fixture.provenance.prn);
testCase.verifyEqual(summary.tracking_channel, ...
    fixture.provenance.tracking_channel);
testCase.verifyEqual(summary.stage0_window_count, 2);
testCase.verifyTrue(isfile(fixture.hdf5Path));
end

function testTamperedCirTasksFailsPinnedHash(testCase)
fixture = makeExporterFixture(testCase, 10230000);
fileId = fopen(fixture.cirTasksPath, 'wt', 'n', 'UTF-8');
testCase.assertGreaterThanOrEqual(fileId, 0);
fwrite(fileId, '{}', 'char');
fclose(fileId);
testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIRTaskManifestHashMismatch');
end

function testValidatorAcceptsTwoWindowsAndPartialFinalChunk(testCase)
temporaryRoot = tempname;
mkdir(temporaryRoot);
testCase.addTeardown(@() removeTemporaryDirectory(temporaryRoot));
hdf5Path = writeSyntheticHdf5(fullfile(temporaryRoot, 'two_windows.h5'), 0);

validation = validate_gnss_code_domain_cir(hdf5Path, 2);

testCase.verifyEqual(validation.snapshot_count, 80);
testCase.verifyEqual(validation.pdp_window_count, 2);
testCase.verifyTrue(validation.pdp_mean_exactly_recomputed);
testCase.verifyEqual(validation.max_pdp_recomputation_difference, 0);
end

function testValidatorRejectsPartialStage0WindowSnapshotRemainder(testCase)
temporaryRoot = tempname;
mkdir(temporaryRoot);
testCase.addTeardown(@() removeTemporaryDirectory(temporaryRoot));
hdf5Path = writeSyntheticHdf5(fullfile(temporaryRoot, 'remainder.h5'), 1);

testCase.verifyError(@() validate_gnss_code_domain_cir(hdf5Path, 2), ...
    'GNSS:SAGE:CIRValidationSnapshotCountMismatch');
end

function testValidatorRejectsPdpMismatchInFinalPartialChunk(testCase)
temporaryRoot = tempname;
mkdir(temporaryRoot);
testCase.addTeardown(@() removeTemporaryDirectory(temporaryRoot));
hdf5Path = writeSyntheticHdf5(fullfile(temporaryRoot, 'pdp_mismatch.h5'), 0);
lastSnapshot = h5read(hdf5Path, '/cir_real', [80, 1], [1, 1]);
h5write(hdf5Path, '/cir_real', lastSnapshot + 1, [80, 1], [1, 1]);

testCase.verifyError(@() validate_gnss_code_domain_cir(hdf5Path, 2), ...
    'GNSS:SAGE:CIRValidationPdpRecomputationMismatch');
end

function testValidatorRejectsPdpStage0StartMismatch(testCase)
temporaryRoot = tempname;
mkdir(temporaryRoot);
testCase.addTeardown(@() removeTemporaryDirectory(temporaryRoot));
hdf5Path = writeSyntheticHdf5(fullfile(temporaryRoot, 'bad_start.h5'), 0);
storedStart = h5read(hdf5Path, '/pdp_start_sample_zero_based', [1, 1], [1, 1]);
h5write(hdf5Path, '/pdp_start_sample_zero_based', ...
    storedStart + 10230, [1, 1], [1, 1]);

testCase.verifyError(@() validate_gnss_code_domain_cir(hdf5Path, 2), ...
    'GNSS:SAGE:CIRValidationStage0AlignmentMismatch');
end

function testValidatorAcceptsStage0DecimalTimeRoundTrip(testCase)
temporaryRoot = tempname;
mkdir(temporaryRoot);
testCase.addTeardown(@() removeTemporaryDirectory(temporaryRoot));
hdf5Path = writeSyntheticHdf5( ...
    fullfile(temporaryRoot, 'rounded_stage0_times.h5'), 0);

windowStarts = [386888977; 387298177];
snapshotStarts = [windowStarts(1) + (0:39).' * 10230; ...
    windowStarts(2) + (0:39).' * 10230];
snapshotTimes = snapshotStarts / 10230000;
serializedStage0Times = round(windowStarts / 10230000, 13);
h5write(hdf5Path, '/sample_start_zero_based', snapshotStarts);
h5write(hdf5Path, '/time_s', snapshotTimes);
h5write(hdf5Path, '/pdp_start_sample_zero_based', windowStarts);
h5write(hdf5Path, '/pdp_time_s', serializedStage0Times);

validation = validate_gnss_code_domain_cir(hdf5Path, 2);
testCase.verifyEqual(validation.pdp_window_count, 2);
testCase.verifyTrue(validation.pdp_mean_exactly_recomputed);
end

function testValidatorRejectsPdpTimeOutsideSerializationTolerance(testCase)
temporaryRoot = tempname;
mkdir(temporaryRoot);
testCase.addTeardown(@() removeTemporaryDirectory(temporaryRoot));
hdf5Path = writeSyntheticHdf5( ...
    fullfile(temporaryRoot, 'bad_pdp_time.h5'), 0);
pdpTime = h5read(hdf5Path, '/pdp_time_s');
h5write(hdf5Path, '/pdp_time_s', pdpTime + 1e-9);

testCase.verifyError(@() validate_gnss_code_domain_cir(hdf5Path, 2), ...
    'GNSS:SAGE:CIRValidationStage0AlignmentMismatch');
end

function testValidatorRejectsTruncatedHdf5(testCase)
temporaryRoot = tempname;
mkdir(temporaryRoot);
testCase.addTeardown(@() removeTemporaryDirectory(temporaryRoot));
hdf5Path = fullfile(temporaryRoot, 'truncated.h5');
fileId = fopen(hdf5Path, 'wb');
testCase.assertGreaterThanOrEqual(fileId, 0);
fwrite(fileId, uint8([0, 1, 2, 3, 4, 5, 6, 7]), 'uint8');
fclose(fileId);

testCase.verifyError(@() validate_gnss_code_domain_cir(hdf5Path, 2), ...
    'GNSS:SAGE:CIRValidationReadFailed');
end

function testWrongSamplingRateFailsClosed(testCase)
fixture = makeExporterFixture(testCase, 10230001);
testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIRScopeMismatch');
end

function testRawIqSizeChangeFailsClosed(testCase)
fixture = makeExporterFixture(testCase, 10230000);
fixture.provenance.raw_iq_size_bytes = ...
    fixture.provenance.raw_iq_size_bytes + 4;
testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:RawIqSizeMismatch');
end

function testSceneMetadataCsvMustMatchPinnedHash(testCase)
fixture = makeExporterFixture(testCase, 10230000);
sceneMetadata = readtable(fixture.sceneMetadataPath);
sceneMetadata.raw_file_size_bytes(1) = ...
    sceneMetadata.raw_file_size_bytes(1) + 4;
writetable(sceneMetadata, fixture.sceneMetadataPath);
testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIRSceneMetadataHashMismatch');
end

function testStage2WindowMissingFromStage0FailsClosed(testCase)
fixture = makeExporterFixture(testCase, 10230000);
stage2 = readtable(fixture.stage2Path);
stage2.window_id(1) = 9999;
writetable(stage2, fixture.stage2Path);
fixture = refreshCohortInputFingerprint(fixture, 'stage2_selected_paths');
testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIRStage2WindowMappingMismatch');
end

function testStage2PrimaryTimeMustMatchStage0Window(testCase)
fixture = makeExporterFixture(testCase, 10230000);
stage2 = readtable(fixture.stage2Path);
stage2.recording_time_s(1) = stage2.recording_time_s(1) + 0.001;
writetable(stage2, fixture.stage2Path);
fixture = refreshCohortInputFingerprint(fixture, 'stage2_selected_paths');
testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIRStage2WindowMetadataMismatch');
end

function testDuplicateStage0WindowIdsFailClosed(testCase)
fixture = makeExporterFixture(testCase, 10230000);
fixture.windows.window_id(2) = fixture.windows.window_id(1);
writetable(fixture.windows, fixture.windowsPath);
fixture = refreshCohortInputFingerprint(fixture, 'stage0_valid_windows');
testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:Stage0WindowDuplicateId');
end

function testExistingOutputCollisionIsPreserved(testCase)
fixture = makeExporterFixture(testCase, 10230000);
fileId = fopen(fixture.hdf5Path, 'wb');
testCase.assertGreaterThanOrEqual(fileId, 0);
fwrite(fileId, uint8(7), 'uint8');
fclose(fileId);
testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIROutputCollision');
collisionInfo = dir(fixture.hdf5Path);
testCase.verifyEqual(collisionInfo.bytes, 1);
end

function testRejectsStage2PathOutsideFrozenCohortNamespace(testCase)
fixture = makeExporterFixture(testCase, 10230000);
otherDirectory = fullfile(fixture.root, 'other_run');
mkdir(otherDirectory);
otherStage2Path = fullfile(otherDirectory, 'stage2_selected_paths.csv');
copyfile(fixture.stage2Path, otherStage2Path);
fixture.stage2Path = otherStage2Path;

testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIRInputPathAuthorizationMismatch');
end

function testRejectsProjectRootWithUnpinnedFrozenSource(testCase)
fixture = makeExporterFixture(testCase, 10230000);
fixture.provenance.project_root = fixture.repositoryRoot;

testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIRFrozenSourceHashMismatch');
end

function testRejectsDuplicateOutputDestinationsBeforePublish(testCase)
fixture = makeExporterFixture(testCase, 10230000);
fixture.metadataPath = fixture.hdf5Path;

testCase.verifyError(@() exportFixture(fixture), ...
    'GNSS:SAGE:CIROutputPathsNotUnique');
testCase.verifyFalse(isfile(fixture.hdf5Path));
testCase.verifyFalse(isfile(fixture.comparisonPath));
end

function fixture = makeExporterFixture(testCase, samplingRateHz)
testDirectory = fileparts(mfilename('fullpath'));
channelModelingDirectory = fileparts(testDirectory);
fixture.repositoryRoot = fileparts(fileparts(channelModelingDirectory));
deployedProjectRoot = getenv('GNSS_TEST_PROJECT_ROOT');
if isempty(deployedProjectRoot)
    deployedProjectRoot = 'E:\GNSS_Multipath_Project';
else
    deployedProjectRoot = char(deployedProjectRoot);
end
addpath(channelModelingDirectory);
fixture.root = tempname;
mkdir(fixture.root);
testCase.addTeardown(@() removeTemporaryDirectory(fixture.root));
fixture.projectRoot = fullfile(fixture.root, 'project');
mkdir(fixture.projectRoot);
copyFrozenConfiguration(deployedProjectRoot, fixture.projectRoot);

fixture.outputNamespace = ...
    'scenes/F1023_V70_D0117_P4/sage_results/rerun_20261003_frozen_v3/G31_ch1';
fixture.stageDirectory = fullfile(fixture.projectRoot, ...
    strrep(fixture.outputNamespace, '/', filesep));
fixture.outputDirectory = fullfile(fixture.root, 'cir');
mkdir(fixture.stageDirectory);
mkdir(fixture.outputDirectory);

samplesPerWindow = 40 * 10230;
windowStarts = [0; 20 * 10230];
windowIds = uint32([1001; 1002]);
fixture.windows = table(windowIds, windowStarts, ...
    windowStarts / samplingRateHz, [30000; 31000], ...
    int8([1; -1]), int8([-1; 1]), [900; -1200], ...
    [1023000; 1022990], [43.5; 44.0], ...
    'VariableNames', {'window_id', 'sample_start_zero_based', ...
    'recording_time_s', 'split_samples', 'nav_symbol_1', ...
    'nav_symbol_2', 'tracking_doppler_hz', 'code_frequency_hz', ...
    'cn0_db_hz'});
fixture.windowsPath = fullfile(fixture.stageDirectory, ...
    'stage0_windows.csv');
writetable(fixture.windows, fixture.windowsPath);
dopplerSignUsed = 1; %#ok<NASGU>
save(fullfile(fixture.stageDirectory, 'doppler_sign.mat'), ...
    'dopplerSignUsed', '-v7');

fixture.stage2Path = fullfile(fixture.stageDirectory, ...
    'stage2_selected_paths.csv');
stage2 = table(windowIds, ones(2, 1), fixture.windows.recording_time_s, ...
    [2.5; 3.0], 'VariableNames', ...
    {'window_id', 'path_id', 'recording_time_s', 'delay_samples'});
writetable(stage2, fixture.stage2Path);

fixture.rawIqPath = fullfile(fixture.root, 'synthetic_iq.bin');
rng(31, 'twister');
rawValues = int16(randi([-1000, 1000], ...
    2 * (2 * samplesPerWindow), 1));
fileId = fopen(fixture.rawIqPath, 'wb', 'ieee-le');
testCase.assertGreaterThanOrEqual(fileId, 0);
fwrite(fileId, rawValues, 'int16');
fclose(fileId);
rawInfo = dir(fixture.rawIqPath);

sceneId = 'F1023_V70_D0117_P4';
sceneMetadataDirectory = fullfile(fixture.projectRoot, ...
    'dataset_generation_logs', 'production_planning_10mhz_20260812');
if ~isfolder(sceneMetadataDirectory)
    mkdir(sceneMetadataDirectory);
end
fixture.sceneMetadataPath = fullfile(sceneMetadataDirectory, ...
    'scene_metadata_10MHz.csv');
sceneMetadata = table({sceneId}, {'synthetic_iq.bin'}, ...
    {fixture.rawIqPath}, rawInfo.bytes, samplingRateHz, 1, {'G31'}, ...
    {'TEST'}, 'VariableNames', {'scene_id', 'raw_file_name', ...
    'raw_file_path', 'raw_file_size_bytes', 'sample_rate', ...
    'number_of_PRN_tasks', 'PRN_list', 'environment_class'});
writetable(sceneMetadata, fixture.sceneMetadataPath);

fixture.provenance = struct('project_root', fixture.projectRoot, ...
    'run_id', 'run_20261003_F1023_V70_D0117_P4_G31_ch1', ...
    'scene_id', sceneId, 'prn', 'G31', 'tracking_channel', 1, ...
    'sample_rate_hz', samplingRateHz, ...
    'frozen_sage_sha256', ...
    'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c', ...
    'raw_iq_size_bytes', rawInfo.bytes, ...
    'scene_metadata_sha256', sha256File(fixture.sceneMetadataPath));
task = struct('run_id', fixture.provenance.run_id, ...
    'scene_id', sceneId, 'prn', 'G31', 'tracking_channel', 1, ...
    'task_status', 'NEW_REQUIRED', ...
    'output_namespace', fixture.outputNamespace);
cohortTask = struct('run_id', fixture.provenance.run_id, ...
    'scene_id', sceneId, 'prn', 'G31', 'tracking_channel', 1, ...
    'output_namespace', fixture.outputNamespace, ...
    'source_frozen_sage_sha256', fixture.provenance.frozen_sage_sha256, ...
    'source_summary_status', 'COMPLETE', ...
    'stage_csvs', struct( ...
        'stage0_valid_windows', struct( ...
            'path', relativeToProjectRoot(fixture.projectRoot, fixture.windowsPath), ...
            'sha256', sha256File(fixture.windowsPath)), ...
        'stage2_selected_paths', struct( ...
            'path', relativeToProjectRoot(fixture.projectRoot, fixture.stage2Path), ...
            'sha256', sha256File(fixture.stage2Path))));
fixture.cohortPath = fullfile(fixture.root, 'cohort.json');
fixture.cohortDocument = struct('cohort_id', 'synthetic_test_cohort', ...
    'schema_version', 1, 'eligible_count', 1, 'tasks', cohortTask);
writeJsonFile(fixture.cohortPath, fixture.cohortDocument, testCase);
fixture.cohortSha256 = sha256File(fixture.cohortPath);

taskDocument = struct('cohort_id', 'synthetic_test_cohort', ...
    'schema_version', 1, ...
    'source_cohort_sha256', fixture.cohortSha256, ...
    'task_count', 1, 'tasks', task);
fixture.cirTasksPath = fullfile(fixture.root, 'cir_tasks.json');
fixture.taskDocument = taskDocument;
writeJsonFile(fixture.cirTasksPath, fixture.taskDocument, testCase);
fixture.provenance.cohort_json_path = fixture.cohortPath;
fixture.provenance.cohort_sha256 = fixture.cohortSha256;
fixture.provenance.cir_tasks_json_path = fixture.cirTasksPath;
fixture.provenance.cir_tasks_sha256 = sha256File(fixture.cirTasksPath);
fixture.hdf5Path = fullfile(fixture.outputDirectory, 'cir.h5');
fixture.metadataPath = fullfile(fixture.outputDirectory, ...
    'cir_metadata.json');
fixture.comparisonPath = fullfile(fixture.outputDirectory, ...
    'delay_comparison.csv');
end

function copyFrozenConfiguration(deployedProjectRoot, syntheticProjectRoot)
sourceRoot = fullfile(deployedProjectRoot, 'scripts', 'sage_pipeline');
destinationRoot = fullfile(syntheticProjectRoot, 'scripts', 'sage_pipeline');
mkdir(destinationRoot);
mkdir(fullfile(destinationRoot, 'core'));
copyfile(fullfile(sourceRoot, 'run_nav_sage_pipeline.m'), ...
    fullfile(destinationRoot, 'run_nav_sage_pipeline.m'));
copyfile(fullfile(sourceRoot, 'core', 'default_sage_configuration.m'), ...
    fullfile(destinationRoot, 'core', 'default_sage_configuration.m'));
end

function relativePath = relativeToProjectRoot(projectRoot, fullPath)
projectRoot = char(java.io.File(projectRoot).getCanonicalPath());
fullPath = char(java.io.File(fullPath).getCanonicalPath());
prefix = [projectRoot, filesep];
assert(strncmpi(fullPath, prefix, numel(prefix)), ...
    'Test:CIRFixturePathOutsideProjectRoot', ...
    'Synthetic source path must be under its synthetic project root.');
relativePath = strrep(fullPath(numel(prefix) + 1:end), filesep, '/');
end

function writeJsonFile(path, value, testCase)
fileId = fopen(path, 'wt', 'n', 'UTF-8');
testCase.assertGreaterThanOrEqual(fileId, 0);
fwrite(fileId, jsonencode(value), 'char');
fwrite(fileId, newline, 'char');
fclose(fileId);
end

function fixture = refreshCohortInputFingerprint(fixture, stageName)
input = fixture.cohortDocument.tasks.stage_csvs.(stageName);
if strcmp(stageName, 'stage0_valid_windows')
    input.sha256 = sha256File(fixture.windowsPath);
else
    input.sha256 = sha256File(fixture.stage2Path);
end
fixture.cohortDocument.tasks.stage_csvs.(stageName) = input;
rewriteJsonFile(fixture.cohortPath, fixture.cohortDocument);
fixture.cohortSha256 = sha256File(fixture.cohortPath);
fixture.taskDocument.source_cohort_sha256 = fixture.cohortSha256;
rewriteJsonFile(fixture.cirTasksPath, fixture.taskDocument);
fixture.provenance.cohort_sha256 = fixture.cohortSha256;
fixture.provenance.cir_tasks_sha256 = sha256File(fixture.cirTasksPath);
end

function rewriteJsonFile(path, value)
fileId = fopen(path, 'wt', 'n', 'UTF-8');
assert(fileId >= 0, 'Test:CIRFixtureWriteFailed', ...
    'Could not update synthetic provenance fixture.');
fwrite(fileId, jsonencode(value), 'char');
fwrite(fileId, newline, 'char');
fclose(fileId);
end

function summary = exportFixture(fixture)
summary = export_gnss_code_domain_cir(fixture.rawIqPath, ...
    fixture.windowsPath, fixture.stage2Path, ...
    fixture.sceneMetadataPath, fixture.hdf5Path, ...
    fixture.metadataPath, fixture.comparisonPath, fixture.provenance);
end

function hdf5Path = writeSyntheticHdf5(hdf5Path, snapshotRemainder)
windowCount = 2;
snapshotCount = windowCount * 40 + snapshotRemainder;
samplesPerWindow = 40 * 10230;
[snapshotRows, delayColumns] = ndgrid(1:snapshotCount, 1:451);
cirReal = 1e-3 * sin(snapshotRows * 0.013 + delayColumns * 0.001);
cirImag = 1e-3 * cos(snapshotRows * 0.017 - delayColumns * 0.002);
delaySamples = (-5:0.1:40).';
timeS = (0:snapshotCount - 1).' / 1000;
windowId = [repmat(uint32(1001), 40, 1); ...
    repmat(uint32(1002), 40 + snapshotRemainder, 1)];
snapshotIndex = [uint8((1:40).'); ...
    uint8((1:(40 + snapshotRemainder)).')];
sampleStart = (0:snapshotCount - 1).' * 10230;
pdpPower = zeros(windowCount, 451);
for windowIndex = 1:windowCount
    rows = (windowIndex - 1) * 40 + (1:40);
    windowCir = complex(cirReal(rows, :), cirImag(rows, :));
    pdpPower(windowIndex, :) = mean(abs(windowCir).^2, 1);
end

writeHdf5Dataset(hdf5Path, '/cir_real', cirReal);
writeHdf5Dataset(hdf5Path, '/cir_imag', cirImag);
writeHdf5Dataset(hdf5Path, '/time_s', timeS);
writeHdf5Dataset(hdf5Path, '/delay_samples', delaySamples);
writeHdf5Dataset(hdf5Path, '/raw_iq_rms', ones(snapshotCount, 1));
writeHdf5Dataset(hdf5Path, '/tracking_doppler_hz', zeros(snapshotCount, 1));
writeHdf5Dataset(hdf5Path, '/code_frequency_hz', ...
    1023000 * ones(snapshotCount, 1));
writeHdf5Dataset(hdf5Path, '/cn0_db_hz', 43 * ones(snapshotCount, 1));
writeHdf5Dataset(hdf5Path, '/nav_symbol', ones(snapshotCount, 1, 'int8'));
writeHdf5Dataset(hdf5Path, '/window_id', windowId);
writeHdf5Dataset(hdf5Path, '/snapshot_index_in_window', snapshotIndex);
writeHdf5Dataset(hdf5Path, '/sample_start_zero_based', sampleStart);
writeHdf5Dataset(hdf5Path, ...
    '/nav_symbol_transition_offset_samples', zeros(snapshotCount, 1, 'int32'));
writeHdf5Dataset(hdf5Path, '/pdp_window_id', uint32([1001; 1002]));
writeHdf5Dataset(hdf5Path, '/pdp_time_s', [0; 0.04]);
writeHdf5Dataset(hdf5Path, '/pdp_start_sample_zero_based', ...
    [0; samplesPerWindow]);
writeHdf5Dataset(hdf5Path, '/pdp_interval_count', uint8([40; 40]));
writeHdf5Dataset(hdf5Path, '/pdp_power', pdpPower);
end

function writeHdf5Dataset(filename, datasetName, values)
if isvector(values)
    values = values(:);
end
dimensions = size(values);
chunkSize = dimensions;
chunkSize(1) = min(64, dimensions(1));
h5create(filename, datasetName, dimensions, ...
    'Datatype', class(values), 'ChunkSize', chunkSize);
h5write(filename, datasetName, values);
end

function removeTemporaryDirectory(path)
if isfolder(path)
    rmdir(path, 's');
end
end

function digest = sha256File(filename)
fileId = fopen(filename, 'rb');
assert(fileId >= 0, 'Test:CIRTaskManifestReadFailed', ...
    'Could not open test cir_tasks.json.');
fileCleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
messageDigest = java.security.MessageDigest.getInstance('SHA-256');
while true
    bytes = fread(fileId, 1024 * 1024, '*uint8');
    if isempty(bytes)
        break;
    end
    messageDigest.update(int8(bytes));
end
digestBytes = typecast(messageDigest.digest(), 'uint8');
digest = lower(reshape(dec2hex(digestBytes, 2).', 1, []));
clear fileCleanup;
end
