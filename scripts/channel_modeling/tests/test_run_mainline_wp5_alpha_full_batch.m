function tests = test_run_mainline_wp5_alpha_full_batch
tests = functiontests(localfunctions);
end

function testAcceptsFrozenSequenceWithoutStartingScientificExports(testCase)
fixture = makeFrozenBatchFixture(testCase, false, false);
cleanup = onCleanup(@() rmdir(fixture.root, 's')); %#ok<NASGU>

result = run_mainline_wp5_alpha_full_batch( ...
    fixture.projectRoot, fixture.outputRoot);
testCase.verifyEqual(result.status, "PARTIAL");
testCase.verifyEqual(result.run_count, 83);
testCase.verifyEqual(result.rejected_run_count, 83);
testCase.verifyEqual(result.exported_run_count, 0);
testCase.verifyFalse(isfile(fullfile(fixture.outputRoot, ...
    'stage2_alpha_all_paths.csv')));
audit = readtable(fullfile(fixture.outputRoot, 'run_export_audit.csv'), ...
    'Delimiter', ',', 'TextType', 'string');
testCase.verifyEqual(audit.run_id, fixture.expectedRunIds);
testCase.verifyTrue(all(audit.status == "REJECTED_PREFLIGHT"));
end

function testRejectsReorderedFrozenRunSequenceEvenWithRehashedPreflight(testCase)
fixture = makeFrozenBatchFixture(testCase, true, false);
cleanup = onCleanup(@() rmdir(fixture.root, 's')); %#ok<NASGU>

testCase.verifyError(@() run_mainline_wp5_alpha_full_batch( ...
    fixture.projectRoot, fixture.outputRoot), ...
    'GNSS:WP5:FrozenRunOrderMismatch');
testCase.verifyFalse(isfile(fullfile(fixture.outputRoot, ...
    'run_export_audit.csv')));
testCase.verifyFalse(isfile(fullfile(fixture.outputRoot, ...
    'batch_export_summary.json')));
end

function testRejectsChangedFrozenLedgerPinBeforeAnyBatchWrite(testCase)
fixture = makeFrozenBatchFixture(testCase, false, true);
cleanup = onCleanup(@() rmdir(fixture.root, 's')); %#ok<NASGU>

testCase.verifyError(@() run_mainline_wp5_alpha_full_batch( ...
    fixture.projectRoot, fixture.outputRoot), 'GNSS:WP5:FrozenPinMismatch');
testCase.verifyFalse(isfile(fullfile(fixture.outputRoot, ...
    'run_export_audit.csv')));
testCase.verifyFalse(isfile(fullfile(fixture.outputRoot, ...
    'batch_export_summary.json')));
end

function fixture = makeFrozenBatchFixture(testCase, reorder, changeLedgerPin)
fixture.projectRoot = 'E:\GNSS_Multipath_Project';
fixture.sourceOutputRoot = fullfile(fixture.projectRoot, ...
    'dataset_generation_logs', 'channel_modeling', ...
    'mainline_1023_wp5_alpha_full_83run_20261029T055629Z');
sourceManifest = fullfile(fixture.sourceOutputRoot, 'input_manifest.csv');
sourcePreflight = fullfile(fixture.sourceOutputRoot, 'source_preflight.json');
testCase.assumeTrue(isfile(sourceManifest) && isfile(sourcePreflight), ...
    'Frozen WP5 evidence is required for this project integration test.');

fixture.root = tempname;
mkdir(fixture.root);
fixture.outputRoot = fullfile(fixture.root, 'isolated_output');
mkdir(fixture.outputRoot);
manifest = readtable(sourceManifest, 'Delimiter', ',', 'TextType', 'string');
fixture.expectedRunIds = manifest.run_id;
if reorder
    manifest = manifest([2:height(manifest), 1], :);
end
manifest.preflight_status(:) = "REJECTED";
manifest.preflight_reason(:) = "TEST_SCOPE_ONLY_NO_EXPORT";
manifestPath = fullfile(fixture.outputRoot, 'input_manifest.csv');
writetable(manifest, manifestPath);

preflight = jsondecode(fileread(sourcePreflight));
preflight.status = 'PREFLIGHT_PARTIAL';
preflight.ready_run_count = 0;
preflight.rejected_run_count = height(manifest);
preflight.input_manifest = manifestPath;
preflight.input_manifest_sha256 = sha256File(manifestPath);
if changeLedgerPin
    preflight.stage2_ledger_sha256 = repmat('0', 1, 64);
end
writeJson(fullfile(fixture.outputRoot, 'source_preflight.json'), preflight);
end

function writeJson(path, value)
fid = fopen(path, 'w', 'n', 'UTF-8');
assert(fid >= 0, 'Could not create isolated JSON fixture.');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, jsonencode(value), 'char');
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
