function tests = TestFullTaskGpuCandidateComparison
tests = functiontests(localfunctions);
end

function testSyntheticPairPassesAndReportsUnthresholdedNumericDeltas(testCase)
pair = makeFixturePair(testCase);
candidateMat = fullfile(pair.CandidateDir, 'stage2_nav_sage_L1_L4.mat');
data = load(candidateMat);
fit = data.stage2Fits{1};
fit.models{2}.paths(2).delaySamples = fit.models{2}.paths(2).delaySamples + 1e-10;
fit.models{2}.paths(2).dopplerHz = fit.models{2}.paths(2).dopplerHz - 2e-8;
fit.models{2}.paths(2).alpha = fit.models{2}.paths(2).alpha + complex(3e-12, -4e-12);
fit.models{2}.paths(2).score = fit.models{2}.paths(2).score + 7e-11;
fit.models{2}.rss = fit.models{2}.rss + 1e-9;
fit.models{2}.bic = fit.models{2}.bic - 2e-9;
data.stage2Fits{1} = fit;
save(candidateMat, '-struct', 'data');

comparison = runFixtureComparison(pair);
verifyTrue(testCase, comparison.Passed);
verifyEqual(testCase, comparison.Stage0.Status, 'PASS');
verifyEqual(testCase, comparison.Stage1.Status, 'PASS');
verifyEqual(testCase, comparison.Stage2.Status, 'PASS');
verifyEqual(testCase, comparison.Stage3.Status, 'PASS');
verifyEqual(testCase, comparison.Stage4.Status, 'PASS');
verifyEqual(testCase, comparison.NumericDiffs.maxDelayAbs, 1e-10, 'AbsTol', 1e-14);
verifyEqual(testCase, comparison.NumericDiffs.maxDopplerAbs, 2e-8, 'AbsTol', 1e-14);
verifyEqual(testCase, comparison.NumericDiffs.maxAlphaAbs, 5e-12, 'AbsTol', 1e-14);
verifyEqual(testCase, comparison.NumericDiffs.maxPathScoreAbs, 7e-11, 'AbsTol', 1e-14);
verifyEqual(testCase, comparison.NumericDiffs.maxRssAbs, 1e-9, 'AbsTol', 1e-14);
verifyEqual(testCase, comparison.NumericDiffs.maxBicAbs, 2e-9, 'AbsTol', 1e-14);
verifyEqual(testCase, comparison.Stage2.WindowRows{1}.CpuBestL, 2);
verifyEqual(testCase, comparison.Stage2.WindowRows{1}.CpuSecondBestL, 1);
verifyEqual(testCase, comparison.Stage2.WindowRows{1}.CpuBicMargin, 10);
verifyEqual(testCase, comparison.Stage2.MinimumCpuBicMarginWindow, 1);
verifyEqual(testCase, comparison.Stage4.StrictConfirmedCount, 1);
end

function testStage0CsvColumnOrderMismatchFails(testCase)
pair = makeFixturePair(testCase);
file = fullfile(pair.CandidateDir, 'stage0_valid_symbols.csv');
value = readtable(file);
writetable(value(:, [2 1]), file);
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function testStage1SemanticIdentityMismatchFails(testCase)
pair = makeFixturePair(testCase);
file = fullfile(pair.CandidateDir, 'stage1_nav_fast_scan.mat');
data = load(file);
data.stage1Table.window_id(1) = 2;
save(file, '-struct', 'data');
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function testStage0FrozenCfgMismatchFails(testCase)
pair = makeFixturePair(testCase);
file = fullfile(pair.CandidateDir, 'stage0_nav_catalog.mat');
data = load(file);
data.cfg.fsHz = 20460000;
save(file, '-struct', 'data');
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function testStage2DirectMpcLabelMismatchFails(testCase)
pair = makeFixturePair(testCase);
file = fullfile(pair.CandidateDir, 'stage2_nav_sage_L1_L4.mat');
data = load(file);
data.pathTable.is_multipath(2) = false;
save(file, '-struct', 'data');
writetable(data.pathTable, fullfile(pair.CandidateDir, 'stage2_selected_paths.csv'));
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function testStage2NumericCsvMustMatchItsMatTable(testCase)
pair = makeFixturePair(testCase);
file = fullfile(pair.CandidateDir, 'stage2_selected_paths.csv');
tableValue = readtable(file);
tableValue.delay_samples(1) = tableValue.delay_samples(1) + 0.25;
writetable(tableValue, file);
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function testStage3PersistenceClassificationMismatchFails(testCase)
pair = makeFixturePair(testCase);
file = fullfile(pair.CandidateDir, 'stage3_nav_persistence.mat');
data = load(file);
data.persistenceTable.persistence_pass(1) = false;
save(file, '-struct', 'data');
writetable(data.persistenceTable, fullfile(pair.CandidateDir, 'stage3_persistence.csv'));
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function testStage4StrictConfirmationMismatchFails(testCase)
pair = makeFixturePair(testCase);
file = fullfile(pair.CandidateDir, 'stage4_nav_joint_100ms.mat');
data = load(file);
data.jointSummaryTable.joint_multipath_count(1) = 0;
save(file, '-struct', 'data');
writetable(data.jointSummaryTable, fullfile(pair.CandidateDir, 'stage4_joint_summary.csv'));
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function testCandidateRunContextIdentityMismatchFails(testCase)
pair = makeFixturePair(testCase);
contextPath = fullfile(pair.CandidateDir, 'run_context.json');
context = jsondecode(fileread(contextPath));
context.prn = 3;
writeJson(contextPath, context);
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function testCandidateProvenanceMismatchFails(testCase)
pair = makeFixturePair(testCase);
provenancePath = fullfile(pair.CandidateDir, 'candidate_provenance.json');
provenance = jsondecode(fileread(provenancePath));
provenance.tracking_channel = 1;
provenance.prn = 3;
writeJson(provenancePath, provenance);
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function testCandidateSourceHashMismatchFails(testCase)
pair = makeFixturePair(testCase);
provenancePath = fullfile(pair.CandidateDir, 'candidate_provenance.json');
provenance = jsondecode(fileread(provenancePath));
provenance.gpu_candidate_source_sha256 = repmat('0', 1, 64);
writeJson(provenancePath, provenance);
verifyError(testCase, @() runFixtureComparison(pair), ...
    'FullTaskGpuCandidate:COMPARISON_FAILED');
end

function comparison = runFixtureComparison(pair)
formalOutputDir = pair.FormalDir; %#ok<NASGU>
candidateOutputDir = pair.CandidateDir; %#ok<NASGU>
taskSceneId = 'F1023_V70_D0117_P2'; %#ok<NASGU>
taskPrn = 28; %#ok<NASGU>
taskChannel = 1; %#ok<NASGU>
scriptPath = fullfile(fileparts(mfilename('fullpath')), ...
    '..', 'Compare-FullTaskGpuCandidateOutputs.m');
validationDir = fileparts(scriptPath);
previousDirectory = pwd;
cleanup = onCleanup(@() cd(previousDirectory)); %#ok<NASGU>
cd(validationDir);
eval(fileread(scriptPath));
comparison = candidateComparison;
end

function pair = makeFixturePair(testCase)
root = tempname;
mkdir(root);
testCase.addTeardown(@() removeFixtureTree(root));
projectRoot = fullfile(root, 'project');
sceneId = 'F1023_V70_D0117_P2';
referenceNamespace = fullfile('scenes', sceneId, 'sage_results', ...
    'rerun_20261003_frozen_v3', 'G28_ch1');
candidateNamespace = fullfile('scenes', sceneId, 'sage_results', ...
    'gpu_candidate_fulltask_20261005', 'G28_ch1');
formalDir = fullfile(projectRoot, referenceNamespace);
candidateDir = fullfile(projectRoot, candidateNamespace);
mkdir(formalDir);
mkdir(candidateDir);

inputRoot = fullfile(root, 'inputs');
mkdir(inputRoot);
identity = struct( ...
    'sceneId', sceneId, ...
    'prn', 28, ...
    'trackingChannel', 1, ...
    'samplingRateHz', 10230000, ...
    'rawFile', fullfile(inputRoot, 'raw.iq'), ...
    'trackingFile', fullfile(inputRoot, 'tracking.mat'), ...
    'telemetryFile', fullfile(inputRoot, 'telemetry.dat'));
formalContext = identity;
formalContext.projectRoot = projectRoot;
formalContext.outputDir = fullfile(projectRoot, 'staging', 'relocated-from-formal-run');
formalContext.referenceOutputNamespace = strrep(referenceNamespace, '\', '/');
formalContext.createdAtUtc = '2026-10-05T00:00:00Z';
candidateContext = identity;
candidateContext.projectRoot = projectRoot;
candidateContext.outputDir = candidateDir;
candidateContext.referenceOutputDir = formalDir;
candidateContext.referenceOutputNamespace = strrep(referenceNamespace, '\', '/');
candidateContext.candidateOutputNamespace = strrep(candidateNamespace, '\', '/');
candidateContext.createdAtUtc = '2026-10-06T00:00:00Z';
writeContext(formalDir, formalContext);
writeContext(candidateDir, candidateContext);

provenance = struct( ...
    'frozen_source_sha256', 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c', ...
    'gpu_candidate_source_sha256', candidateSourceSha256(), ...
    'qualified_gpu_stage2_source_identity', struct( ...
        'probeSha256', 'bfe56ad02c99240257fddd212ba43ee5606a81740b3dda716c5947c433cbfa88', ...
        'selectorSha256', 'a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5'), ...
    'execution_timestamp', '2026-10-06T00:00:00Z', ...
    'scene_id', sceneId, 'prn', 28, 'tracking_channel', 1, ...
    'resume', false, ...
    'reference_output_namespace', strrep(referenceNamespace, '\', '/'), ...
    'candidate_output_namespace', strrep(candidateNamespace, '\', '/'), ...
    'gpu_identity', 'RTX 4060 Laptop GPU');
writeJson(fullfile(candidateDir, 'candidate_provenance.json'), provenance);

cfg = struct('targetPrn', 28, 'fsHz', 10230000, ...
    'resumeExistingStages', false, 'minimumJointSnapshotWins', 4);
symbolCatalog = table(1, true, 'VariableNames', ...
    {'symbol_index', 'continuous_to_next'});
windowCatalog = table(1, 0.04, 1, ...
    'VariableNames', {'window_id', 'recording_time_s', 'symbol_index'});
stage0Symbols = table(1, true, 'VariableNames', ...
    {'symbol_index', 'continuous_to_next'});
stage0Windows = windowCatalog;
stage1Table = table(1, 0.04, 'VariableNames', ...
    {'window_id', 'recording_time_s'});
records = stage1Table;
completed = true;
dopplerSignUsed = 1;
candidateIndices = 1;
fit = makeFit();
stage2Fits = {fit};
fits = stage2Fits;
[modelTable, selectedTable, pathTable] = makeStage2Tables();
persistenceTable = table(1, 0.04, 2, 1, 1.2, 0.1, -5, 3, 3, true, "111", ...
    'VariableNames', {'center_window_id','center_recording_time_s','selected_L', ...
    'multipath_id','excess_delay_samples','doppler_offset_hz','relative_power_db', ...
    'matched_window_count','longest_consecutive_count','persistence_pass','match_pattern'});
reliableTable = table(1, 0.04, 2, 1, 3, true, ...
    'VariableNames', {'center_window_id','recording_time_s','selected_L', ...
    'multipath_count','minimum_path_run','reliable_multipath'});
jointFitModels = makeFit();
for order = 1:4
    jointFitModels.models{order}.snapshotRss = [5 / order; 4 / order];
    jointFitModels.models{order}.snapshotWins = 4;
end
jointFits = {struct('centerWindowId', 1, ...
    'selectedOrder', 2, 'models', {jointFitModels.models})};
jointSummaryTable = table(1, 0.04, 2, 2, 1, 20, 90, 4, -5, 20, 0.1, true, ...
    'VariableNames', {'center_window_id','recording_time_s','stage2_L', ...
    'joint_selected_L','joint_multipath_count','joint_rss','joint_bic', ...
    'snapshot_wins_vs_L1','minimum_multipath_power_db', ...
    'maximum_relative_doppler_hz','maximum_coherence','joint_valid'});
jointPathTable = table([1;1], [2;2], [1;2], [false;true], ...
    [5;6.2], [0;1.2], [0;0.1], [0; -5], ...
    'VariableNames', {'center_window_id','joint_selected_L','path_id', ...
    'is_multipath','delay_samples','excess_delay_samples', ...
    'doppler_offset_hz','mean_relative_power_db'});

for side = 1:2
    if side == 1, outputDir = formalDir; else, outputDir = candidateDir; end
    writetable(stage0Symbols, fullfile(outputDir, 'stage0_valid_symbols.csv'));
    writetable(stage0Windows, fullfile(outputDir, 'stage0_valid_40ms_windows.csv'));
    save(fullfile(outputDir, 'stage0_nav_catalog.mat'), ...
        'symbolCatalog', 'windowCatalog', 'cfg');
    save(fullfile(outputDir, 'doppler_sign.mat'), 'dopplerSignUsed', 'cfg');
    writetable(stage1Table, fullfile(outputDir, 'stage1_nav_fast_scan.csv'));
    save(fullfile(outputDir, 'stage1_nav_fast_scan.mat'), ...
        'stage1Table', 'dopplerSignUsed', 'cfg');
    save(fullfile(outputDir, 'stage1_nav_progress.mat'), ...
        'records', 'completed', 'cfg');
    writetable(modelTable, fullfile(outputDir, 'stage2_model_orders.csv'));
    writetable(selectedTable, fullfile(outputDir, 'stage2_selected_windows.csv'));
    writetable(pathTable, fullfile(outputDir, 'stage2_selected_paths.csv'));
    save(fullfile(outputDir, 'stage2_nav_sage_L1_L4.mat'), ...
        'stage2Fits', 'modelTable', 'selectedTable', 'pathTable', 'cfg');
    save(fullfile(outputDir, 'stage2_nav_progress.mat'), ...
        'fits', 'completed', 'candidateIndices', 'cfg');
    writetable(persistenceTable, fullfile(outputDir, 'stage3_persistence.csv'));
    writetable(reliableTable, fullfile(outputDir, 'stage3_reliable_centers.csv'));
    save(fullfile(outputDir, 'stage3_nav_persistence.mat'), ...
        'persistenceTable', 'reliableTable', 'cfg');
    writetable(jointSummaryTable, fullfile(outputDir, 'stage4_joint_summary.csv'));
    writetable(jointPathTable, fullfile(outputDir, 'stage4_joint_paths.csv'));
    save(fullfile(outputDir, 'stage4_nav_joint_100ms.mat'), ...
        'jointFits', 'jointSummaryTable', 'jointPathTable', 'cfg');
end

pair = struct('Root', root, 'ProjectRoot', projectRoot, ...
    'FormalDir', formalDir, 'CandidateDir', candidateDir, ...
    'ReferenceNamespace', strrep(referenceNamespace, '\', '/'), ...
    'CandidateNamespace', strrep(candidateNamespace, '\', '/'));
end

function fit = makeFit()
models = cell(4, 1);
for order = 1:4
    paths = repmat(struct('delaySamples', 0, 'dopplerHz', 0, ...
        'alpha', complex(0, 0), 'score', 0), 1, order);
    relativePowerDb = zeros(1, order);
    for pathIndex = 1:order
        paths(pathIndex).delaySamples = 5 + 1.2 * (pathIndex - 1);
        paths(pathIndex).dopplerHz = -12 + 0.1 * (pathIndex - 1);
        paths(pathIndex).alpha = complex(1 / pathIndex, -0.1 / pathIndex);
        paths(pathIndex).score = 2 / pathIndex;
        relativePowerDb(pathIndex) = -5 * (pathIndex - 1);
    end
    models{order} = struct('order', order, 'paths', paths, ...
        'rss', 10 / order, 'bic', 100 - 10 * order, ...
        'valid', order <= 2, 'relativePowerDb', relativePowerDb, ...
        'minimumSeparationSamples', 1, 'minimumMultipathPowerDb', -25, ...
        'maximumRelativeDopplerHz', 40, 'maximumCoherence', 0.2, ...
        'rssHistory', [10 / order, 5 / order]);
end
fit = struct('windowId', 1, 'catalogIndex', 1, ...
    'recordingTimeS', 0.04, 'towS', 0.04, 'models', {models}, ...
    'selectedOrder', 2, 'errorMessage', "");
end

function [modelTable, selectedTable, pathTable] = makeStage2Tables()
modelTable = table(repmat(1,4,1), repmat(0.04,4,1), (1:4)', (0:3)', ...
    (10 ./ (1:4))', (100 - 10 .* (1:4))', (1:4)' <= 2, (1:4)' == 2, ...
    'VariableNames', {'window_id','recording_time_s','model_order', ...
    'multipath_count','rss','bic','model_valid','selected'});
selectedTable = table(1, 0.04, 0.04, 2, 1, 80, 5, ...
    'VariableNames', {'window_id','recording_time_s','tow_s','selected_L', ...
    'multipath_count','selected_bic','selected_rss'});
pathTable = table([1;1], [0.04;0.04], [2;2], [1;2], [false;true], ...
    [5;6.2], [0;1.2], [0;1.2], [0;0.1], [0;-5], ...
    'VariableNames', {'window_id','recording_time_s','selected_L','path_id', ...
    'is_multipath','delay_samples','excess_delay_samples', ...
    'excess_delay_chips','doppler_hz','relative_power_db'});
end

function writeContext(outputDir, context)
runContext = context;
cfg = struct('targetPrn', 28, 'fsHz', 10230000, ...
    'resumeExistingStages', false, 'minimumJointSnapshotWins', 4);
save(fullfile(outputDir, 'run_context.mat'), 'runContext', 'cfg');
writeJson(fullfile(outputDir, 'run_context.json'), context);
end

function writeJson(path, value)
file = fopen(path, 'wt');
cleanup = onCleanup(@() fclose(file));
fwrite(file, jsonencode(value), 'char');
end

function digest = candidateSourceSha256()
sourcePath = fullfile(fileparts(mfilename('fullpath')), ...
    '..', '..', 'full_task_candidate', ...
    'run_nav_sage_pipeline_gpu_candidate.m');
fileId = fopen(sourcePath, 'rb');
cleanup = onCleanup(@() fclose(fileId));
bytes = fread(fileId, inf, '*uint8');
messageDigest = java.security.MessageDigest.getInstance('SHA-256');
messageDigest.update(typecast(bytes(:), 'int8'));
digestBytes = typecast(messageDigest.digest(), 'uint8');
digest = lower(reshape(dec2hex(digestBytes, 2).', 1, []));
end

function removeFixtureTree(path)
if isfolder(path), rmdir(path, 's'); end
end
