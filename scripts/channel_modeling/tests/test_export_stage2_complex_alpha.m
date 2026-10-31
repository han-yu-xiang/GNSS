function tests = test_export_stage2_complex_alpha
tests = functiontests(localfunctions);
end

function testKeepsEveryStage2PathAndMarksUnavailableAlpha(testCase)
tempRoot = tempname;
mkdir(tempRoot);
cleanup = onCleanup(@() rmdir(tempRoot, 's')); %#ok<NASGU>

stage2MatPath = fullfile(tempRoot, 'stage2.mat');
selectedPathsPath = fullfile(tempRoot, 'selected_paths.csv');
outputCsvPath = fullfile(tempRoot, 'alpha.csv');

path1 = struct('delaySamples', 0.2, 'dopplerHz', -2100, ...
    'alpha', 1.25 - 0.5i, 'score', 0);
path2 = struct('delaySamples', 2.1, 'dopplerHz', -2070, ...
    'alpha', -0.75 + 0.125i, 'score', 0);
selectedModel17 = struct('paths', [path1; path2]);
models17 = cell(2, 1);
models17{2} = selectedModel17;
fit17 = struct('windowId', 17, 'selectedOrder', 2, ...
    'models', {models17});

path18 = struct('delaySamples', 0.1, 'dopplerHz', -2090, 'score', 0);
selectedModel18 = struct('paths', path18);
models18 = cell(1, 1);
models18{1} = selectedModel18;
fit18 = struct('windowId', 18, 'selectedOrder', 1, ...
    'models', {models18});

stage2Fits = {fit17; fit18}; %#ok<NASGU>
save(stage2MatPath, 'stage2Fits');

directPower = abs(path1.alpha)^2;
relativePower2 = 10 * log10(abs(path2.alpha)^2 / directPower);
selectedPaths = table([17; 17; 18; 19], [2; 2; 1; 1], ...
    [1; 2; 1; 1], [0; relativePower2; 0; 0], ...
    [0.2; 2.1; 0.1; 0.0], [-2100; -2070; -2090; -2080], ...
    'VariableNames', {'window_id', 'selected_L', 'path_id', ...
    'relative_power_db', 'delay_samples', 'doppler_hz'});
writetable(selectedPaths, selectedPathsPath);

provenance = sampleProvenance();
export_stage2_complex_alpha(stage2MatPath, selectedPathsPath, ...
    outputCsvPath, provenance);

actual = readtable(outputCsvPath, 'TextType', 'string');
testCase.verifyEqual(height(actual), 4);
testCase.verifyEqual(actual.window_id, [17; 17; 18; 19]);
testCase.verifyEqual(actual.path_id, [1; 2; 1; 1]);
testCase.verifyEqual(actual.alpha_status, ...
    ["AVAILABLE"; "AVAILABLE"; "MISSING"; "MISSING"]);
testCase.verifyEqual(actual.alpha_missing_reason, ...
    ["NONE"; "NONE"; "ALPHA_FIELD_MISSING"; ...
    "NO_STAGE2_FIT_FOR_WINDOW"]);
testCase.verifyEqual(actual.alpha_real(1:2), [1.25; -0.75], ...
    'AbsTol', 1e-12);
testCase.verifyEqual(actual.alpha_imag(1:2), [-0.5; 0.125], ...
    'AbsTol', 1e-12);
testCase.verifyEqual(actual.alpha_magnitude(1:2), ...
    abs([path1.alpha; path2.alpha]), 'AbsTol', 1e-12);
testCase.verifyEqual(actual.alpha_phase_rad(1:2), ...
    angle([path1.alpha; path2.alpha]), 'AbsTol', 1e-12);
testCase.verifyTrue(all(isnan(actual.alpha_real(3:4))));
testCase.verifyTrue(all(isnan(actual.alpha_imag(3:4))));
testCase.verifyTrue(all(actual.SAGE_ALPHA_IS_FROM_WINDOW_NORMALIZED_IQ ...
    == "YES"));
testCase.verifyEqual(actual.relative_power_check_status(1:2), ...
    ["PASS"; "PASS"]);
testCase.verifyEqual(actual.source_selected_paths_csv_path, ...
    repmat(string(selectedPathsPath), 4, 1));
testCase.verifyEqual(actual.stage2_mat_sha256, ...
    repmat(string(provenance.stage2_mat_sha256), 4, 1));
testCase.verifyEqual(actual.selected_paths_csv_sha256, ...
    repmat(string(provenance.selected_paths_csv_sha256), 4, 1));

selectedPaths.relative_power_db(2) = 0;
mismatchPathsPath = fullfile(tempRoot, 'selected_paths_mismatch.csv');
writetable(selectedPaths, mismatchPathsPath);
mismatchOutputPath = fullfile(tempRoot, 'alpha_mismatch.csv');
export_stage2_complex_alpha(stage2MatPath, mismatchPathsPath, ...
    mismatchOutputPath, provenance);
mismatch = readtable(mismatchOutputPath, 'TextType', 'string');
testCase.verifyEqual(mismatch.alpha_status(2), "AVAILABLE");
testCase.verifyEqual(mismatch.relative_power_check_status(2), "MISMATCH");
end

function testRetainsNonfiniteAlphaWithExplicitReason(testCase)
tempRoot = tempname;
mkdir(tempRoot);
cleanup = onCleanup(@() rmdir(tempRoot, 's')); %#ok<NASGU>

alphaPath = complex(NaN, 1);
path = struct('delaySamples', 0, 'dopplerHz', 0, ...
    'alpha', alphaPath, 'score', 0);
model = struct('paths', path);
models = {model};
fit = struct('windowId', 1, 'selectedOrder', 1, 'models', {models});
stage2Fits = {fit}; %#ok<NASGU>
stage2MatPath = fullfile(tempRoot, 'stage2.mat');
save(stage2MatPath, 'stage2Fits');

selectedPathsPath = fullfile(tempRoot, 'selected_paths.csv');
writetable(table(1, 1, 1, 0, 'VariableNames', ...
    {'window_id', 'selected_L', 'path_id', 'relative_power_db'}), ...
    selectedPathsPath);
outputCsvPath = fullfile(tempRoot, 'alpha.csv');
export_stage2_complex_alpha(stage2MatPath, selectedPathsPath, ...
    outputCsvPath, sampleProvenance());
actual = readtable(outputCsvPath, 'TextType', 'string');
testCase.verifyEqual(height(actual), 1);
testCase.verifyEqual(actual.alpha_status, "MISSING");
testCase.verifyEqual(actual.alpha_missing_reason, ...
    "ALPHA_NONFINITE_OR_INVALID");
testCase.verifyTrue(isnan(actual.alpha_magnitude));
end

function testRejectsDuplicateOrIncompleteSelectedPathIdentity(testCase)
tempRoot = tempname;
mkdir(tempRoot);
cleanup = onCleanup(@() rmdir(tempRoot, 's')); %#ok<NASGU>
stage2MatPath = fullfile(tempRoot, 'stage2.mat');
stage2Fits = {}; %#ok<NASGU>
save(stage2MatPath, 'stage2Fits');
selectedPathsPath = fullfile(tempRoot, 'selected_paths.csv');
writetable(table([1; 1], [2; 2], [1; 1], [0; 0], ...
    'VariableNames', {'window_id', 'selected_L', 'path_id', ...
    'relative_power_db'}), selectedPathsPath);
testCase.verifyError(@() export_stage2_complex_alpha( ...
    stage2MatPath, selectedPathsPath, fullfile(tempRoot, 'alpha.csv'), ...
    sampleProvenance()), 'GNSS:SAGE:DuplicateSelectedPathIdentity');
end

function testRefusesToOverwriteExistingOutput(testCase)
tempRoot = tempname;
mkdir(tempRoot);
cleanup = onCleanup(@() rmdir(tempRoot, 's')); %#ok<NASGU>
stage2MatPath = fullfile(tempRoot, 'stage2.mat');
stage2Fits = {}; %#ok<NASGU>
save(stage2MatPath, 'stage2Fits');
selectedPathsPath = fullfile(tempRoot, 'selected_paths.csv');
writetable(table(1, 1, 1, 0, 'VariableNames', ...
    {'window_id', 'selected_L', 'path_id', 'relative_power_db'}), ...
    selectedPathsPath);
outputCsvPath = fullfile(tempRoot, 'alpha.csv');
fid = fopen(outputCsvPath, 'w');
fwrite(fid, 'do-not-overwrite');
fclose(fid);
testCase.verifyError(@() export_stage2_complex_alpha( ...
    stage2MatPath, selectedPathsPath, outputCsvPath, sampleProvenance()), ...
    'GNSS:SAGE:AlphaOutputCollision');
testCase.verifyEqual(fileread(outputCsvPath), 'do-not-overwrite');
end

function provenance = sampleProvenance()
provenance = struct('run_id', 'test_run', 'scene_id', 'test_scene', ...
    'prn', 'G28', 'tracking_channel', 1, ...
    'sample_rate_hz', 10230000, ...
    'frozen_sage_sha256', repmat('a', 1, 64), ...
    'stage2_mat_sha256', repmat('b', 1, 64), ...
    'selected_paths_csv_sha256', repmat('c', 1, 64));
end
