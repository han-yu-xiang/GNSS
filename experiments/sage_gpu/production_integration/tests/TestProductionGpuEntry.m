function tests = TestProductionGpuEntry
tests = functiontests(localfunctions);
end

function testResumeTrueIsRejectedBeforeProjectResolution(testCase)
addProductionEntryPath();
verifyError(testCase, @() run_nav_sage_pipeline_gpu_production( ...
    'FIXTURE_SCENE', 3, 'TrackingChannel', 2, ...
    'ProjectRoot', fullfile(tempdir, 'does-not-exist'), ...
    'Resume', true, 'RunId', 'fixture_run_id'), ...
    'GNSS:SAGE:RESUME_MUST_BE_FALSE');
end

function testUnavailableGpuFailsBeforeReadingRawIq(testCase)
addProductionEntryPath();
fixture = makeProjectFixture(testCase, 'FIXTURE_SCENE', 'FIXTURE_SCENE');
gpuStub = [tempname '-gpu-unavailable-stub'];
mkdir(gpuStub);
addTeardown(testCase, @() cleanupFixture(gpuStub));
writeText(fullfile(gpuStub, 'canUseGPU.m'), ...
    sprintf('function available = canUseGPU\navailable = false;\nend\n'));
addpath(gpuStub, '-begin');
clear canUseGPU;
cleanup = onCleanup(@() removeGpuStub(gpuStub)); %#ok<NASGU>

writeProductionHelperShim(testCase, 'assertProductionGpuAvailabilityForTest', ...
    'assertProductionGpuAvailability', {});
verifyError(testCase, @() assertProductionGpuAvailabilityForTest(), ...
    'GNSS:SAGE:GPU_NOT_AVAILABLE');
verifyFalse(testCase, isfile(fullfile(fixture.OutputDir, ...
    'stage0_nav_catalog.mat')));
verifyEqual(testCase, dir(fixture.RawPath).bytes, 0);
end

function testMetadataSceneMismatchFailsClosed(testCase)
addProductionEntryPath();
fixture = makeProjectFixture(testCase, 'FIXTURE_SCENE', 'OTHER_SCENE');
writeProductionHelperShim(testCase, 'assertProductionGpuInputIdentityForTest', ...
    'assertProductionGpuInputIdentity', {});
options = struct('sceneId', "FIXTURE_SCENE", 'TrackingChannel', 2, ...
    'ProjectRoot', string(fixture.ProjectRoot));
gnssSdrDir = fullfile(fixture.ProjectRoot, 'scenes', ...
    'FIXTURE_SCENE', 'gnss_sdr');
telemetryPath = fullfile(gnssSdrDir, 'telemetry', ...
    'FIXTURE_SCENE_telemetry_ch_2.dat');
trackingPath = fullfile(gnssSdrDir, 'tracking', ...
    'FIXTURE_SCENE_track_ch_2.mat');
context = struct('sceneId', "OTHER_SCENE", 'prn', 3, 'prnLabel', "G03", ...
    'trackingChannel', 2, 'samplingRateHz', 10230000, ...
    'gnssSdrDir', string(gnssSdrDir), ...
    'telemetryFile', string(telemetryPath), ...
    'trackingFile', string(trackingPath), ...
    'rawFile', string(fixture.RawPath), 'outputDir', string(fixture.OutputDir));
cfg = struct('targetPrn', 3, 'fsHz', 10230000, 'trackingChannel', 2);
verifyError(testCase, @() assertProductionGpuInputIdentityForTest( ...
    options, 3, context, cfg), ...
    'GNSS:SAGE:GPU_SOURCE_IDENTITY_MISMATCH');
verifyFalse(testCase, isfile(fullfile(fixture.OutputDir, ...
    'stage0_nav_catalog.mat')));
verifyEqual(testCase, dir(fixture.RawPath).bytes, 0);
end

function testDirectEntryRejectsMissingPlanPathBeforeOutputOrInputResolution(testCase)
addProductionEntryPath();
projectRoot = tempname;
mkdir(projectRoot);
addTeardown(testCase, @() cleanupFixture(projectRoot));
outputPath = fullfile(projectRoot, 'scenes', 'NO_SUCH_SCENE', ...
    'sage_results', 'nav_sage_v2', 'G03');
verifyError(testCase, @() run_nav_sage_pipeline_gpu_production( ...
    'NO_SUCH_SCENE', 3, 'TrackingChannel', 2, ...
    'ProjectRoot', projectRoot, 'Resume', false, ...
    'RunId', 'caller_chosen_run', ...
    'ExecutionPlanPath', fullfile(projectRoot, 'fake-plan.json')), ...
    'GNSS:SAGE:GPU_EXECUTION_PLAN_NOT_FOUND');
verifyFalse(testCase, isfolder(outputPath));
end

function testDirectEntryRejectsSchemaValidFakePlanAgainstReleasedPin(testCase)
addProductionEntryPath();
fixture = makeGpuPlanFixture(testCase, false);
projectRoot = fullfile(fixture.Root, 'unresolved-project');
outputPath = fullfile(projectRoot, 'scenes', fixture.SceneId, ...
    'sage_results', 'nav_sage_v2', fixture.PrnLabel);
verifyError(testCase, @() run_nav_sage_pipeline_gpu_production( ...
    fixture.SceneId, 3, 'TrackingChannel', fixture.TrackingChannel, ...
    'ProjectRoot', projectRoot, 'Resume', false, ...
    'RunId', fixture.RunId, 'ExecutionPlanPath', fixture.PlanPath), ...
    'GNSS:SAGE:GPU_EXECUTION_PLAN_SHA_MISMATCH');
verifyFalse(testCase, isfolder(outputPath));
end

function testExecutionPlanHashMustMatchInjectedInternalPin(testCase)
addProductionEntryPath();
fixture = makeGpuPlanFixture(testCase, false);
writeProductionHelperShim(testCase, 'validateProductionGpuExecutionPlanForTest', ...
    'validateProductionGpuExecutionPlan', ...
    {'computeCanonicalGpuTaskIdentitySha256', 'computeFileSha256'});
verifyError(testCase, @() validateProductionGpuExecutionPlanForTest( ...
    fixture.PlanPath, repmat('f', 1, 64), fixture.RunId, fixture.SceneId, ...
    fixture.PrnLabel, fixture.TrackingChannel), ...
    'GNSS:SAGE:GPU_EXECUTION_PLAN_SHA_MISMATCH');
end

function testCanonicalTaskIdentityMatchesFixedCrossLanguageDigest(testCase)
addProductionEntryPath();
writeProductionHelperShim(testCase, ...
    'computeCanonicalGpuTaskIdentitySha256Fixture', ...
    'computeCanonicalGpuTaskIdentitySha256', {});
digest = computeCanonicalGpuTaskIdentitySha256Fixture( ...
    'fixture_run_01', 'FIXTURE_SCENE', 'G03', 2);
verifyEqual(testCase, digest, ...
    'ab5f37a5c381215095ce77ff7394b89d5c307a902985eaa0096a3f86c458e1ba');
end

function testExecutionPlanRejectsMatchingRunIdWithWrongTaskIdentity(testCase)
addProductionEntryPath();
fixture = makeGpuPlanFixture(testCase, true);
writeProductionHelperShim(testCase, 'validateProductionGpuExecutionPlanForTest', ...
    'validateProductionGpuExecutionPlan', ...
    {'computeCanonicalGpuTaskIdentitySha256', 'computeFileSha256'});
verifyError(testCase, @() validateProductionGpuExecutionPlanForTest( ...
    fixture.PlanPath, fixture.PlanSha256, fixture.RunId, fixture.SceneId, ...
    fixture.PrnLabel, fixture.TrackingChannel), ...
    'GNSS:SAGE:GPU_EXECUTION_PLAN_TASK_IDENTITY_MISMATCH');
end

function testRuntimeGpuLockRejectsSecondAcquisitionAndReleasesWithoutDeletingFile(testCase)
addProductionEntryPath();
writeProductionHelperShim(testCase, 'acquireProductionGpuRuntimeLockForTest', ...
    'acquireProductionGpuRuntimeLock', ...
    {'getProductionGpuRuntimeLockPath', 'releaseProductionGpuRuntimeLock'});
projectRoot = tempname;
mkdir(fullfile(projectRoot, 'dataset_generation_logs', ...
    'batch_sage_execution'));
addTeardown(testCase, @() cleanupFixture(projectRoot));
lockPath = fullfile(projectRoot, 'dataset_generation_logs', ...
    'batch_sage_execution', '.gpu_stage2_qualified_runtime.lock');
firstLock = acquireProductionGpuRuntimeLockForTest(projectRoot);
verifyTrue(testCase, isfile(lockPath));
verifyError(testCase, @() acquireProductionGpuRuntimeLockForTest(projectRoot), ...
    'GNSS:SAGE:GPU_GLOBAL_RUNTIME_LOCK_PRESENT');
clear firstLock;
secondLock = acquireProductionGpuRuntimeLockForTest(projectRoot);
verifyTrue(testCase, isfile(lockPath));
clear secondLock;
verifyTrue(testCase, isfile(lockPath));
end

function testAuthorizedAttemptProvenanceDoesNotClaimExecutionSuccess(testCase)
addProductionEntryPath();
writeProductionHelperShim(testCase, 'writeGpuExecutionAttemptForTest', ...
    'writeGpuExecutionAttempt', {});
outputDir = tempname;
mkdir(outputDir);
addTeardown(testCase, @() cleanupFixture(outputDir));
context = struct('outputDir', string(outputDir), 'sceneId', "FIXTURE_SCENE", ...
    'prn', 3, 'prnLabel', "G03", 'trackingChannel', 2);
options = struct('RunId', "fixture_run", 'TrackingChannel', 2, 'Resume', false);
authorization = struct('ExecutionPlanSha256', repmat('a', 1, 64));
sourceContract = struct('frozen_authority_sha256', repmat('b', 1, 64), ...
    'source_contract_sha256', repmat('f', 1, 64), ...
    'qualified_candidate_sha256', repmat('c', 1, 64), ...
    'qualified_probe_sha256', repmat('d', 1, 64), ...
    'qualified_selector_sha256', repmat('e', 1, 64));
attemptPath = writeGpuExecutionAttemptForTest( ...
    context, options, authorization, sourceContract);
attempt = jsondecode(fileread(attemptPath));
verifyEqual(testCase, attempt.attempt_status, 'AUTHORIZED');
verifyEqual(testCase, attempt.execution_mode, 'GPU_STAGE2_QUALIFIED');
verifyEqual(testCase, attempt.resume, false);
verifyFalse(testCase, isfield(attempt, 'success'));
verifyFalse(testCase, isfield(attempt, 'gpu_identity'));
end

function testProductionOutputRecordSchemasMatchFrozen(testCase)
repoRoot = getReviewRepoRoot();
frozenPath = 'E:\\GNSS_Multipath_Project\\scripts\\sage_pipeline\\run_nav_sage_pipeline.m';
productionPath = fullfile(repoRoot, 'scripts', 'sage_pipeline', ...
    'run_nav_sage_pipeline_gpu_production.m');
verifyTrue(testCase, isfile(frozenPath));
verifyTrue(testCase, isfile(productionPath));

shimRoot = tempname;
mkdir(shimRoot);
addTeardown(testCase, @() cleanupSchemaShims(shimRoot));
recordFunctions = { ...
    'emptySymbolRecord', 'emptyWindowRecord', 'emptyStage1Record', ...
    'emptyModelRecord', 'emptySelectedRecord', 'emptyPathRecord', ...
    'emptyPersistenceRecord', 'emptyReliableRecord', ...
    'emptyJointSummaryRecord', 'emptyJointPathRecord'};
writeSchemaShim(frozenPath, shimRoot, 'frozenOutputSchemaForTest', ...
    recordFunctions);
writeSchemaShim(productionPath, shimRoot, ...
    'productionOutputSchemaForTest', recordFunctions);
addpath(shimRoot, '-begin');

frozenSchemas = frozenOutputSchemaForTest();
productionSchemas = productionOutputSchemaForTest();
verifyEqual(testCase, fieldnames(productionSchemas), ...
    fieldnames(frozenSchemas));
for index = 1:numel(recordFunctions)
    recordName = recordFunctions{index};
    frozenRecord = frozenSchemas.(recordName);
    productionRecord = productionSchemas.(recordName);
    verifyEqual(testCase, fieldnames(productionRecord), ...
        fieldnames(frozenRecord), recordName);
    verifyTrue(testCase, isequaln(productionRecord, frozenRecord), ...
        [recordName ' values/schema differ from Frozen']);
end
end

function testGatherGpuFitRestoresFrozenRowShapeForInvalidModels(testCase)
addProductionEntryPath();
productionPath = which('run_nav_sage_pipeline_gpu_production');
verifyNotEmpty(testCase, productionPath);
source = fileread(productionPath);
gatherBlock = extractMatlabFunctionBlock(source, 'gatherGpuFit');
helperBlock = extractMatlabFunctionBlock(source, 'gpuProbeToCpu');
gatherSignature = 'function fitCpu = gatherGpuFit(fitGpu)';
verifyEqual(testCase, count(source, gatherSignature), 1);
gatherBlock = strrep(gatherBlock, gatherSignature, ...
    'function fitCpu = gatherGpuFitForTest(fitGpu)');

shimRoot = tempname;
mkdir(shimRoot);
addTeardown(testCase, @() cleanupGatherShim(shimRoot));
shimPath = fullfile(shimRoot, 'gatherGpuFitForTest.m');
writeText(shimPath, sprintf('%s\n\n%s\n', gatherBlock, helperBlock));
addpath(shimRoot, '-begin');

fitGpu = struct();
fitGpu.models = cell(4, 1);
for order = 1:4
    model = struct();
    model.valid = false;
    model.paths = [];
    model.relativePowerDb = (1:order).' .* 0.25;
    fitGpu.models{order} = model;
end
fitCpu = gatherGpuFitForTest(fitGpu);
for order = 1:4
    verifyFalse(testCase, fitCpu.models{order}.valid);
    verifyEmpty(testCase, fitCpu.models{order}.paths);
    verifyEqual(testCase, size(fitCpu.models{order}.relativePowerDb), ...
        [1 order]);
    verifyEqual(testCase, fitCpu.models{order}.relativePowerDb, ...
        (1:order) .* 0.25);
end
end

function fixture = makeProjectFixture(testCase, requestedSceneId, metadataSceneId)
root = tempname;
mkdir(root);
addTeardown(testCase, @() cleanupFixture(root));
sceneRoot = fullfile(root, 'scenes', requestedSceneId);
gnssRoot = fullfile(sceneRoot, 'gnss_sdr');
telemetryDir = fullfile(gnssRoot, 'telemetry');
trackingDir = fullfile(gnssRoot, 'tracking');
navigationDir = fullfile(sceneRoot, 'navigation', 'rinex_nav');
trajectoryDir = fullfile(sceneRoot, 'trajectory');
satelliteDir = fullfile(sceneRoot, 'satellite');
mkdir(telemetryDir);
mkdir(trackingDir);
mkdir(navigationDir);
mkdir(trajectoryDir);
mkdir(satelliteDir);

rawPath = fullfile(root, 'raw_fixture.bin');
writeText(rawPath, '');
metadata = struct('scene_id', metadataSceneId, ...
    'signal', struct('sample_rate_hz', 10230000), ...
    'raw_iq', struct('path', rawPath));
writeText(fullfile(sceneRoot, 'metadata.json'), jsonencode(metadata));
writeText(fullfile(telemetryDir, ...
    [requestedSceneId '_telemetry_ch_2.dat']), 'fixture');
save(fullfile(trackingDir, ...
    [requestedSceneId '_track_ch_2.mat']), 'metadata');
writeText(fullfile(navigationDir, 'fixture.26N'), 'fixture');
writeText(fullfile(trajectoryDir, 'fixture.nmea'), 'fixture');

fixture = struct('ProjectRoot', root, 'SceneId', requestedSceneId, ...
    'RawPath', rawPath, 'OutputDir', fullfile(sceneRoot, 'sage_results', ...
    'nav_sage_v2', 'G03'));
end

function fixture = makeGpuPlanFixture(testCase, wrongTaskIdentity)
root = tempname;
mkdir(root);
addTeardown(testCase, @() cleanupFixture(root));
runId = 'fixture_run_01';
sceneId = 'FIXTURE_SCENE';
prnLabel = 'G03';
trackingChannel = 2;
identityScene = sceneId;
if wrongTaskIdentity
    identityScene = 'OTHER_SCENE';
end
identityText = sprintf('run_id=%s\nscene_id=%s\nprn=%s\ntracking_channel=%d\n', ...
    runId, identityScene, prnLabel, trackingChannel);
identityDigest = computeTestSha256Utf8(identityText);
task = struct('run_id', runId, 'task_identity_sha256', identityDigest);
plan = struct('schema_version', 'frozen-sage-gpu-execution-plan-v2', ...
    'execution_mode', 'GPU_STAGE2_QUALIFIED', ...
    'source_manifest_sha256', repmat('a', 1, 64), ...
    'resume', false, 'max_parallel_matlab', 1, ...
    'authorized_tasks', {{task}});
planPath = fullfile(root, 'execution-plan.json');
writeText(planPath, jsonencode(plan));
fixture = struct('Root', root, 'PlanPath', planPath, ...
    'PlanSha256', computeTestSha256File(planPath), 'RunId', runId, ...
    'SceneId', sceneId, 'PrnLabel', prnLabel, ...
    'TrackingChannel', trackingChannel);
end

function writeProductionHelperShim(testCase, wrapperName, targetName, dependencyNames)
sourcePath = fullfile(getReviewRepoRoot(), 'scripts', 'sage_pipeline', ...
    'run_nav_sage_pipeline_gpu_production.m');
source = fileread(sourcePath);
blocks = cell(1, numel(dependencyNames) + 1);
blocks{1} = extractMatlabFunctionBlock(source, targetName);
for index = 1:numel(dependencyNames)
    blocks{index + 1} = extractMatlabFunctionBlock(source, dependencyNames{index});
end
shimRoot = tempname;
mkdir(shimRoot);
addTeardown(testCase, @() cleanupHelperShim(shimRoot, wrapperName));
wrapper = sprintf(['function varargout = %s(varargin)\n', ...
    '[varargout{1:nargout}] = %s(varargin{:});\nend'], ...
    wrapperName, targetName);
shimText = strjoin([{wrapper}, blocks], [newline newline]);
writeText(fullfile(shimRoot, [wrapperName '.m']), shimText);
addpath(shimRoot, '-begin');
end

function digest = computeTestSha256Utf8(text)
bytes = unicode2native(text, 'UTF-8');
messageDigest = java.security.MessageDigest.getInstance('SHA-256');
messageDigest.update(typecast(uint8(bytes(:)), 'int8'));
digest = lower(reshape(dec2hex(typecast(messageDigest.digest(), 'uint8'), 2).', 1, []));
end

function digest = computeTestSha256File(path)
fileId = fopen(path, 'rb');
cleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
bytes = fread(fileId, inf, '*uint8');
messageDigest = java.security.MessageDigest.getInstance('SHA-256');
messageDigest.update(typecast(bytes(:), 'int8'));
digest = lower(reshape(dec2hex(typecast(messageDigest.digest(), 'uint8'), 2).', 1, []));
end

function cleanupHelperShim(shimRoot, wrapperName)
if contains(path, shimRoot)
    rmpath(shimRoot);
end
clear(wrapperName);
cleanupFixture(shimRoot);
end

function addProductionEntryPath()
repoRoot = getReviewRepoRoot();
addpath(fullfile(repoRoot, 'scripts', 'sage_pipeline'));
end

function repoRoot = getReviewRepoRoot()
repoRoot = fileparts(fileparts(fileparts(fileparts(fileparts(mfilename('fullpath'))))));
end

function writeSchemaShim(sourcePath, shimRoot, wrapperName, recordFunctions)
source = fileread(sourcePath);
lines = {['function schemas = ' wrapperName '()'], 'schemas = struct();'};
blocks = cell(size(recordFunctions));
for index = 1:numel(recordFunctions)
    recordName = recordFunctions{index};
    lines{end + 1} = ['schemas.' recordName ' = ' recordName '();']; %#ok<AGROW>
    blocks{index} = extractMatlabFunctionBlock(source, recordName);
end
lines{end + 1} = 'end';
shimText = strjoin(lines, newline);
for index = 1:numel(blocks)
    shimText = [shimText newline newline blocks{index}]; %#ok<AGROW>
end
writeText(fullfile(shimRoot, [wrapperName '.m']), shimText);
end

function block = extractMatlabFunctionBlock(source, functionName)
pattern = ['(?m)^[\t ]*function[^\n]*' functionName '\s*\('];
startMatches = regexp(source, pattern, 'start');
assert(numel(startMatches) == 1, ...
    ['Expected one source function: ' functionName]);
functionStarts = regexp(source, '(?m)^[\t ]*function[^\n]*', 'start');
nextStarts = functionStarts(functionStarts > startMatches(1));
if isempty(nextStarts)
    finish = numel(source);
else
    finish = nextStarts(1) - 1;
end
block = strtrim(source(startMatches(1):finish));
end

function cleanupSchemaShims(shimRoot)
if contains(path, shimRoot)
    rmpath(shimRoot);
end
clear frozenOutputSchemaForTest productionOutputSchemaForTest;
cleanupFixture(shimRoot);
end

function cleanupGatherShim(shimRoot)
if contains(path, shimRoot)
    rmpath(shimRoot);
end
clear gatherGpuFitForTest;
cleanupFixture(shimRoot);
end

function removeGpuStub(gpuStub)
rmpath(gpuStub);
clear canUseGPU;
end

function writeText(path, text)
file = fopen(path, 'wt', 'n', 'UTF-8');
cleanup = onCleanup(@() fclose(file)); %#ok<NASGU>
fwrite(file, text, 'char');
end

function cleanupFixture(root)
if isfolder(root)
    rmdir(root, 's');
end
end
