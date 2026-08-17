function result = run_shared_core_regression(varargin)
%RUN_SHARED_CORE_REGRESSION Replay one frozen reference Stage0 catalog.
%
% This is a thin regression harness. It does not copy or reimplement any
% Stage1-Stage4 numerical algorithm. It loads the frozen G28 Stage0 catalog,
% invokes the current shared core with Resume=false, writes only to a fresh
% darkroom regression namespace, and compares the generated CSV artifacts to
% the frozen reference CSV artifacts.
%
% The harness is intended for a normal Windows MATLAB user. Codex must not
% launch MATLAB from its sandbox.

scriptDir = fileparts(mfilename("fullpath"));
defaultProjectRoot = fileparts(fileparts(fileparts(scriptDir)));
parser = inputParser;
addParameter(parser, "ProjectRoot", defaultProjectRoot, @(v) ...
    ischar(v) || (isstring(v) && isscalar(v)));
parse(parser, varargin{:});
projectRoot = string(parser.Results.ProjectRoot);

% G06 was checked first but rejected as a strict replay baseline because its
% protected legacy directory has no run_context.json. Keep this baseline
% fixed; do not allow a caller to redirect the scientific comparison.
sceneId = "F1023_V70_D0117_P2";
prnLabel = "G28";
prnNumber = 28;
trackingChannel = 1;
baselineDir = fullfile(projectRoot, "scenes", sceneId, ...
    "sage_results", "nav_sage_v2", prnLabel);
runContextFile = fullfile(baselineDir, "run_context.json");
stage0Mat = fullfile(baselineDir, "stage0_nav_catalog.mat");
metadataFile = fullfile(projectRoot, "scenes", sceneId, "metadata.json");

timestamp = char(datetime("now", "TimeZone", "UTC", ...
    "Format", "yyyyMMdd'T'HHmmss'Z'"));
regressionRoot = fullfile(projectRoot, "dataset_generation_logs", ...
    "darkroom_channel_emulation", ...
    "shared_core_matlab_regression_" + string(timestamp));

receipt = struct( ...
    "status", "NOT_STARTED", ...
    "regression_baseline_scene", sceneId, ...
    "regression_baseline_prn", prnLabel, ...
    "regression_baseline_channel", trackingChannel, ...
    "baseline_artifact_path", baselineDir, ...
    "baseline_provenance", runContextFile, ...
    "execution_mode", "new_only", ...
    "resume", false, ...
    "output_namespace", regressionRoot, ...
    "matlab_user", string(getenv("USERNAME")), ...
    "started_utc", string(datetime("now", "TimeZone", "UTC")), ...
    "ended_utc", "", ...
    "error_message", "");

try
    assert(isfolder(baselineDir), ...
        "Baseline artifact directory is missing: %s", baselineDir);
    assert(isfile(runContextFile), ...
        "Strict baseline requires run_context.json: %s", runContextFile);
    assert(isfile(stage0Mat), ...
        "Baseline Stage0 MAT is missing: %s", stage0Mat);
    assert(~isfolder(regressionRoot) && ~isfile(regressionRoot), ...
        "Regression namespace already exists; new-only refuses reuse: %s", ...
        regressionRoot);
    assert(~contains(lower(char(regressionRoot)), "sage_results"), ...
        "Regression namespace must not be under sage_results.");

    context = readJsonWithBom(runContextFile);
    assert(string(context.sceneId) == sceneId, ...
        "Baseline scene does not match frozen selection.");
    assert(string(context.prnLabel) == prnLabel, ...
        "Baseline PRN does not match frozen selection.");
    assert(double(context.trackingChannel) == trackingChannel, ...
        "Baseline tracking channel does not match frozen selection.");
    assert(double(context.samplingRateHz) == 10230000, ...
        "Baseline is not a 10.23 MHz recording.");

    metadata = readJsonWithBom(metadataFile);
    assert(double(metadata.signal.sample_rate_hz) == 10230000, ...
        "Current metadata is not 10.23 MHz.");
    assert(string(metadata.raw_iq.path) == string(context.rawFile), ...
        "Current metadata raw path differs from frozen run context.");
    rawInfo = dir(string(context.rawFile));
    assert(isscalar(rawInfo) && rawInfo.bytes > 0, ...
        "Baseline raw input is missing or empty: %s", context.rawFile);

    requiredReferenceFiles = [ ...
        "stage1_nav_fast_scan.csv", ...
        "stage2_model_orders.csv", ...
        "stage2_selected_windows.csv", ...
        "stage2_selected_paths.csv", ...
        "stage3_persistence.csv", ...
        "stage3_reliable_centers.csv", ...
        "stage4_joint_summary.csv", ...
        "stage4_joint_paths.csv"];
    for fileName = reshape(requiredReferenceFiles, 1, [])
        assert(isfile(fullfile(baselineDir, fileName)), ...
            "Baseline output is missing: %s", fullfile(baselineDir, fileName));
    end

    beforeSnapshot = snapshotFiles(baselineDir, requiredReferenceFiles);
    loaded = load(stage0Mat, "symbolCatalog", "windowCatalog", "cfg");
    symbolCatalog = loaded.symbolCatalog;
    windowCatalog = loaded.windowCatalog;
    cfg = loaded.cfg;
    cfg.resumeExistingStages = false;
    cfg.sceneId = char(sceneId);
    cfg.prnLabel = char(prnLabel);
    cfg.trackingChannel = trackingChannel;
    assert(double(cfg.fsHz) == 10230000, ...
        "Frozen Stage0 configuration is not 10.23 MHz.");

    coreDirectory = fullfile(projectRoot, "scripts", "sage_pipeline", "core");
    assert(isfile(fullfile(coreDirectory, ...
        "run_sage_stage1_stage4_core.m")), ...
        "Shared core file is missing: %s", coreDirectory);
    addpath(coreDirectory, "-begin");
    mkdir(regressionRoot);

    fprintf("Shared-core regression baseline: %s/%s/ch%d\n", ...
        sceneId, prnLabel, trackingChannel);
    fprintf("Regression output: %s\n", regressionRoot);
    fprintf("Resume: false\n");

    coreResult = run_sage_stage1_stage4_core( ...
        windowCatalog, symbolCatalog, string(context.rawFile), ...
        regressionRoot, cfg);
    %#ok<NASGU> The returned object confirms the shared call completed.

    comparison = compareOutputs(baselineDir, regressionRoot);
    afterSnapshot = snapshotFiles(baselineDir, requiredReferenceFiles);
    baselineUnchanged = isequaln(beforeSnapshot, afterSnapshot);
    comparison.baseline_unchanged = baselineUnchanged;
    comparison.overall_pass = comparison.overall_pass && baselineUnchanged;
    writeComparisonCsv(comparison, fullfile(regressionRoot, ...
        "comparison_summary.csv"));

    receipt.status = ternary(comparison.overall_pass, "PASS", "FAIL");
    receipt.ended_utc = string(datetime("now", "TimeZone", "UTC"));
    receipt.stage1_candidate_identity = comparison.stage1_candidate_identity;
    receipt.stage2_evaluated_identity = comparison.stage2_evaluated_identity;
    receipt.stage2_selected_model_identity = comparison.stage2_selected_model_identity;
    receipt.stage3_reliable_center_identity = comparison.stage3_reliable_center_identity;
    receipt.stage4_event_identity = comparison.stage4_event_identity;
    receipt.confirmed_event_identity = comparison.confirmed_event_identity;
    receipt.confirmed_path_identity = comparison.confirmed_path_identity;
    receipt.comparison_tolerance = comparison.comparison_tolerance;
    receipt.max_abs_error = comparison.max_abs_error;
    receipt.max_rel_error = comparison.max_rel_error;
    receipt.baseline_unchanged = baselineUnchanged;
    writeJson(receipt, fullfile(regressionRoot, "regression_receipt.json"));

    if ~comparison.overall_pass
        error("Shared-core regression comparison failed; see %s", ...
            fullfile(regressionRoot, "comparison_summary.csv"));
    end
    fprintf("PRODUCTION_REFACTOR_REGRESSION=PASS\n");
    result = receipt;
catch exception
    receipt.status = "FAILED";
    receipt.ended_utc = string(datetime("now", "TimeZone", "UTC"));
    receipt.error_message = string(exception.message);
    if isfolder(regressionRoot)
        writeJson(receipt, fullfile(regressionRoot, "regression_receipt.json"));
    end
    rethrow(exception);
end
end


function value = readJsonWithBom(filename)
%READJSONWITHBOM Decode JSON bytes without corrupting an encoding marker.
% The regression harness accepts UTF-8 (with or without BOM) and UTF-16LE/
% UTF-16BE BOM input. It fails closed for empty, malformed, or undecodable
% input and never removes or substitutes characters from the source bytes.
fileId = fopen(filename, "rb", "ieee-le");
assert(fileId >= 0, "Cannot open JSON input: %s", filename);
cleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
bytes = fread(fileId, Inf, "*uint8");
assert(~isempty(bytes), "JSON input is empty: %s", filename);

encoding = "UTF-8";
startIndex = 1;
if numel(bytes) >= 3 && isequal(bytes(1:3), uint8([239; 187; 191]))
    encoding = "UTF-8";
    startIndex = 4;
elseif numel(bytes) >= 2 && isequal(bytes(1:2), uint8([255; 254]))
    encoding = "UTF-16LE";
    startIndex = 3;
elseif numel(bytes) >= 2 && isequal(bytes(1:2), uint8([254; 255]))
    encoding = "UTF-16BE";
    startIndex = 3;
end

payload = bytes(startIndex:end);
assert(~isempty(payload), "JSON input contains only a BOM: %s", filename);

try
    if encoding == "UTF-8"
        jsonText = native2unicode(payload.', "UTF-8");
    else
        assert(mod(numel(payload), 2) == 0, ...
            "UTF-16 JSON byte length is odd: %s", filename);
        first = uint16(payload(1:2:end));
        second = uint16(payload(2:2:end));
        if encoding == "UTF-16LE"
            codeUnits = bitor(first, bitshift(second, 8));
        else
            codeUnits = bitor(bitshift(first, 8), second);
        end
        jsonText = char(codeUnits.');
    end
catch exception
    error("JSON decoding failed for %s: %s", filename, exception.message);
end

assert(~isempty(strtrim(jsonText)), "JSON input is blank: %s", filename);
try
    value = jsondecode(jsonText);
catch exception
    error("Invalid JSON in %s: %s", filename, exception.message);
end
end


function comparison = compareOutputs(baselineDir, actualDir)
absTol = 1e-9;
relTol = 1e-12;
specs = [ ...
    struct("file", "stage1_nav_fast_scan.csv", ...
        "keys", ["window_id"], "exact", ["window_id", "scan_valid"]), ...
    struct("file", "stage2_model_orders.csv", ...
        "keys", ["window_id", "model_order"], ...
        "exact", ["window_id", "model_order", "model_valid", "selected"]), ...
    struct("file", "stage2_selected_windows.csv", ...
        "keys", ["window_id"], "exact", ["window_id", "selected_L"]), ...
    struct("file", "stage2_selected_paths.csv", ...
        "keys", ["window_id", "path_id"], ...
        "exact", ["window_id", "selected_L", "path_id", "is_multipath"]), ...
    struct("file", "stage3_persistence.csv", ...
        "keys", ["center_window_id", "multipath_id"], ...
        "exact", ["center_window_id", "multipath_id", "persistence_pass"]), ...
    struct("file", "stage3_reliable_centers.csv", ...
        "keys", ["center_window_id"], ...
        "exact", ["center_window_id", "reliable_multipath"]), ...
    struct("file", "stage4_joint_summary.csv", ...
        "keys", ["center_window_id"], ...
        "exact", ["center_window_id", "joint_selected_L", ...
            "joint_multipath_count", "joint_valid"]), ...
    struct("file", "stage4_joint_paths.csv", ...
        "keys", ["center_window_id", "path_id"], ...
        "exact", ["center_window_id", "joint_selected_L", "path_id", ...
            "is_multipath"])];

records = repmat(emptyComparisonRecord(), 0, 1);
overall = true;
maxAbs = 0;
maxRel = 0;
for spec = reshape(specs, 1, [])
    record = compareTableFile( ...
        fullfile(baselineDir, spec.file), ...
        fullfile(actualDir, spec.file), spec, absTol, relTol);
    records(end + 1, 1) = record; %#ok<AGROW>
    overall = overall && record.pass;
    maxAbs = max(maxAbs, record.max_abs_error);
    maxRel = max(maxRel, record.max_rel_error);
end

stage2Selected = readtable(fullfile(baselineDir, ...
    "stage2_selected_windows.csv"), "VariableNamingRule", "preserve");
stage2SelectedActual = readtable(fullfile(actualDir, ...
    "stage2_selected_windows.csv"), "VariableNamingRule", "preserve");
stage2Models = readtable(fullfile(baselineDir, ...
    "stage2_model_orders.csv"), "VariableNamingRule", "preserve");
stage2ModelsActual = readtable(fullfile(actualDir, ...
    "stage2_model_orders.csv"), "VariableNamingRule", "preserve");
stage3Reliable = readtable(fullfile(baselineDir, ...
    "stage3_reliable_centers.csv"), "VariableNamingRule", "preserve");
stage3ReliableActual = readtable(fullfile(actualDir, ...
    "stage3_reliable_centers.csv"), "VariableNamingRule", "preserve");
stage4Summary = readtable(fullfile(baselineDir, ...
    "stage4_joint_summary.csv"), "VariableNamingRule", "preserve");
stage4SummaryActual = readtable(fullfile(actualDir, ...
    "stage4_joint_summary.csv"), "VariableNamingRule", "preserve");
stage4Paths = readtable(fullfile(baselineDir, ...
    "stage4_joint_paths.csv"), "VariableNamingRule", "preserve");
stage4PathsActual = readtable(fullfile(actualDir, ...
    "stage4_joint_paths.csv"), "VariableNamingRule", "preserve");

comparison = struct( ...
    "overall_pass", overall, ...
    "categorical_identity_pass", overall, ...
    "numeric_pass", overall, ...
    "records", records, ...
    "comparison_tolerance", struct("absolute", absTol, "relative", relTol), ...
    "max_abs_error", maxAbs, ...
    "max_rel_error", maxRel, ...
    "stage1_candidate_identity", ...
        identityStatus(stage2Selected.window_id, stage2SelectedActual.window_id), ...
    "stage2_evaluated_identity", identityStatus( ...
        unique(stage2Models.window_id), unique(stage2ModelsActual.window_id)), ...
    "stage2_selected_model_identity", identityStatus( ...
        stage2Selected.window_id, stage2SelectedActual.window_id), ...
    "stage3_reliable_center_identity", identityStatus( ...
        stage3Reliable.center_window_id, stage3ReliableActual.center_window_id), ...
    "stage4_event_identity", identityStatus( ...
        stage4Summary.center_window_id, stage4SummaryActual.center_window_id), ...
    "confirmed_event_identity", identityStatus( ...
        stage4Summary.center_window_id(stage4Summary.joint_multipath_count > 0), ...
        stage4SummaryActual.center_window_id(stage4SummaryActual.joint_multipath_count > 0)), ...
    "confirmed_path_identity", identityStatus( ...
        pathIdentity(stage4Paths), pathIdentity(stage4PathsActual)), ...
    "baseline_unchanged", false);
end


function record = compareTableFile(baselineFile, actualFile, spec, absTol, relTol)
record = emptyComparisonRecord();
record.file = spec.file;
if ~isfile(actualFile)
    record.pass = false;
    record.message = "actual_file_missing";
    return;
end
baseline = readtable(baselineFile, "VariableNamingRule", "preserve");
actual = readtable(actualFile, "VariableNamingRule", "preserve");
record.baseline_rows = height(baseline);
record.actual_rows = height(actual);
if ~isequal(baseline.Properties.VariableNames, actual.Properties.VariableNames)
    record.pass = false;
    record.message = "column_schema_mismatch";
    return;
end
keyNames = cellstr(spec.keys);
baseline = sortrows(baseline, keyNames);
actual = sortrows(actual, keyNames);
if height(baseline) ~= height(actual)
    record.pass = false;
    record.message = "row_count_mismatch";
    return;
end

exactNames = intersect(cellstr(spec.exact), baseline.Properties.VariableNames, "stable");
for name = reshape(exactNames, 1, [])
    if ~sameExact(baseline.(name), actual.(name))
        record.pass = false;
        record.exact_mismatch_count = record.exact_mismatch_count + 1;
    end
end

for name = reshape(baseline.Properties.VariableNames, 1, [])
    left = baseline.(name);
    right = actual.(name);
    if isnumeric(left) || islogical(left)
        [pass, absError, relError, mismatchCount] = compareNumeric( ...
            double(left), double(right), absTol, relTol);
        record.numeric_mismatch_count = ...
            record.numeric_mismatch_count + mismatchCount;
        record.max_abs_error = max(record.max_abs_error, absError);
        record.max_rel_error = max(record.max_rel_error, relError);
        if ~pass
            record.pass = false;
        end
    elseif ~sameExact(left, right)
        record.pass = false;
        record.exact_mismatch_count = record.exact_mismatch_count + 1;
    end
end
record.categorical_pass = record.exact_mismatch_count == 0;
record.numeric_pass = record.numeric_mismatch_count == 0;
record.pass = record.pass && record.categorical_pass && record.numeric_pass;
if record.pass
    record.message = "PASS";
else
    record.message = "mismatch";
end
end


function [pass, maxAbs, maxRel, mismatchCount] = compareNumeric(left, right, absTol, relTol)
pass = true;
maxAbs = 0;
maxRel = 0;
mismatchCount = 0;
if ~isequal(size(left), size(right))
    pass = false;
    mismatchCount = 1;
    return;
end
for index = 1:numel(left)
    a = left(index);
    b = right(index);
    if isnan(a) && isnan(b)
        continue;
    end
    if isinf(a) || isinf(b)
        if isequal(a, b)
            continue;
        end
        pass = false;
        mismatchCount = mismatchCount + 1;
        continue;
    end
    absolute = abs(a - b);
    relative = absolute / max([abs(a), abs(b), eps]);
    maxAbs = max(maxAbs, absolute);
    maxRel = max(maxRel, relative);
    if absolute > absTol + relTol * max(abs(a), abs(b))
        pass = false;
        mismatchCount = mismatchCount + 1;
    end
end
end


function status = identityStatus(left, right)
status = struct("pass", sameExact(left, right), ...
    "baseline_count", numel(left), "actual_count", numel(right));
end


function identity = pathIdentity(tableValue)
if isempty(tableValue)
    identity = zeros(0, 2);
    return;
end
identity = [double(tableValue.center_window_id), double(tableValue.path_id)];
if ismember("is_multipath", tableValue.Properties.VariableNames)
    identity = [identity, double(tableValue.is_multipath)];
end
end


function tf = sameExact(left, right)
if isnumeric(left) || islogical(left)
    tf = isequaln(left, right);
else
    tf = isequaln(string(left), string(right));
end
end


function snapshot = snapshotFiles(root, names)
snapshot = repmat(struct("name", "", "bytes", 0, "datenum", 0), 0, 1);
for name = reshape(names, 1, [])
    info = dir(fullfile(root, name));
    assert(isscalar(info), "Cannot snapshot baseline file: %s", ...
        fullfile(root, name));
    snapshot(end + 1, 1) = struct("name", name, ...
        "bytes", info.bytes, "datenum", info.datenum); %#ok<AGROW>
end
end


function writeComparisonCsv(comparison, filename)
records = comparison.records;
if isempty(records)
    return;
end
tableValue = struct2table(records);
writetable(tableValue, filename);
end


function writeJson(value, filename)
fileId = fopen(filename, "w", "n", "UTF-8");
assert(fileId >= 0, "Cannot write regression receipt: %s", filename);
cleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
fwrite(fileId, jsonencode(value), "char");
end


function value = ternary(condition, trueValue, falseValue)
if condition
    value = trueValue;
else
    value = falseValue;
end
end


function record = emptyComparisonRecord()
record = struct( ...
    "file", "", "pass", false, "categorical_pass", false, ...
    "numeric_pass", false, "message", "", "baseline_rows", 0, ...
    "actual_rows", 0, "exact_mismatch_count", 0, ...
    "numeric_mismatch_count", 0, "max_abs_error", 0, ...
    "max_rel_error", 0);
end
