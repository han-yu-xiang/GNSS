function result = run_production_recovery_regression(varargin)
%RUN_PRODUCTION_RECOVERY_REGRESSION Replay one frozen reference G28 task.
%
% This is a thin regression harness. It does not copy or reimplement any
% Stage1-Stage4 numerical algorithm. It loads frozen G28 provenance and the
% baseline Stage0 catalog for comparison, regenerates Stage0 from the copied
% non-raw inputs, invokes the current recovered monolithic production with
% Resume=false, writes only to a fresh darkroom regression namespace, and
% compares the generated CSV artifacts to the frozen reference artifacts.
%
% The harness is intended for a normal Windows MATLAB user. Codex must not
% launch MATLAB from its sandbox.

scriptDir = fileparts(mfilename("fullpath"));
defaultProjectRoot = fileparts(fileparts(fileparts(scriptDir)));
parser = inputParser;
addParameter(parser, "ProjectRoot", defaultProjectRoot, @(v) ...
    ischar(v) || (isstring(v) && isscalar(v)));
addParameter(parser, "CompareExistingActualDir", "", @(v) ...
    ischar(v) || (isstring(v) && isscalar(v)));
parse(parser, varargin{:});
projectRoot = string(parser.Results.ProjectRoot);
actualComparisonDir = string(parser.Results.CompareExistingActualDir);
comparisonOnly = strlength(strtrim(actualComparisonDir)) > 0;
comparisonMode = "fresh_recovery_run";
if comparisonOnly
    comparisonMode = "existing_output_read_only";
end

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
if comparisonOnly
    outputPrefix = "production_recovery_compare_existing_";
else
    outputPrefix = "production_recovery_regression_";
end
regressionRoot = fullfile(projectRoot, "dataset_generation_logs", ...
    "darkroom_channel_emulation", outputPrefix + string(timestamp));

receipt = struct( ...
    "status", "NOT_STARTED", ...
    "regression_baseline_scene", sceneId, ...
    "regression_baseline_prn", prnLabel, ...
    "regression_baseline_channel", trackingChannel, ...
    "baseline_artifact_path", baselineDir, ...
    "baseline_provenance", runContextFile, ...
    "execution_mode", "new_only", ...
    "resume", false, ...
    "comparison_mode", comparisonMode, ...
    "output_namespace", regressionRoot, ...
    "actual_output_namespace", actualComparisonDir, ...
    "raw_iq_opened", false, ...
    "sage_executed", false, ...
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
    actualContext = struct();
    if comparisonOnly
        actualDir = string(actualComparisonDir);
        darkroomRoot = fullfile(projectRoot, "dataset_generation_logs", ...
            "darkroom_channel_emulation");
        assert(isfolder(actualDir), ...
            "Existing actual output directory is missing: %s", actualDir);
        assert(isPathWithinRoot(actualDir, darkroomRoot), ...
            "Existing actual output must remain inside darkroom namespace.");
        assert(~strcmpi(char(actualDir), char(baselineDir)), ...
            "Existing actual output must not be the protected baseline.");
        assert(~isfolder(regressionRoot) && ~isfile(regressionRoot), ...
            "Comparison namespace already exists; new-only refuses reuse: %s", ...
            regressionRoot);
        mkdir(regressionRoot);
        actualContext = validateActualContext(actualDir, sceneId, ...
            prnLabel, trackingChannel);
        fprintf("COMPARE_EXISTING_ACTUAL_DIR=%s\n", actualDir);
        fprintf("Raw IQ opened: false\n");
        fprintf("SAGE executed: false\n");
    else
        regressionProjectRoot = fullfile(regressionRoot, "project");
        mkdir(regressionProjectRoot);
        prepareRegressionProject(projectRoot, regressionProjectRoot, context, sceneId);
        addpath(fullfile(projectRoot, "scripts", "sage_pipeline"), "-begin");

        fprintf("Production-recovery regression baseline: %s/%s/ch%d\n", ...
            sceneId, prnLabel, trackingChannel);
        fprintf("Regression output: %s\n", regressionRoot);
        fprintf("Resume: false\n");

        stageResult = run_nav_sage_pipeline(sceneId, prnNumber, ...
            "TrackingChannel", trackingChannel, ...
            "ProjectRoot", regressionProjectRoot, ...
            "Resume", false);
        assert(isstruct(stageResult) && isscalar(stageResult), ...
            "Production pipeline must return a scalar result container.");
        actualDir = fullfile(regressionProjectRoot, "scenes", sceneId, ...
            "sage_results", "nav_sage_v2", prnLabel);
        receipt.raw_iq_opened = true;
        receipt.sage_executed = true;
    end
    comparison = compareOutputs(baselineDir, actualDir);
    comparison.stage0_catalog_identity = compareStage0Catalogs( ...
        stage0Mat, fullfile(actualDir, "stage0_nav_catalog.mat"));
    comparison.overall_pass = comparison.overall_pass ...
        && comparison.stage0_catalog_identity.pass;
    comparison.comparison_mode = comparisonMode;
    comparison.actual_output_namespace = string(actualDir);

    afterSnapshot = snapshotFiles(baselineDir, requiredReferenceFiles);
    baselineUnchanged = isequaln(beforeSnapshot, afterSnapshot);
    comparison.baseline_unchanged = baselineUnchanged;
    comparison.overall_pass = comparison.overall_pass && baselineUnchanged;
    writeSchemaComparisonCsv(comparison.records, fullfile(regressionRoot, ...
        "production_recovery_schema_comparison.csv"));
    writeComparisonCsv(comparison, fullfile(regressionRoot, ...
        "comparison_summary.csv"));

    receipt.status = ternary(comparison.overall_pass, "PASS", "FAIL");
    receipt.ended_utc = string(datetime("now", "TimeZone", "UTC"));
    receipt.stage0_catalog_identity = comparison.stage0_catalog_identity;
    receipt.stage1_candidate_identity = comparison.stage1_candidate_identity;
    receipt.stage2_evaluated_identity = comparison.stage2_evaluated_identity;
    receipt.stage2_selected_model_identity = comparison.stage2_selected_model_identity;
    receipt.stage3_reliable_center_identity = comparison.stage3_reliable_center_identity;
    receipt.stage4_event_identity = comparison.stage4_event_identity;
    receipt.confirmed_event_identity = comparison.confirmed_event_identity;
    receipt.confirmed_path_identity = comparison.confirmed_path_identity;
    receipt.confirmed_event_path_identity = ...
        comparison.confirmed_event_path_identity;
    receipt.file_level_pass_components = struct( ...
        "row_count_pass", comparison.row_count_pass, ...
        "column_count_pass", comparison.column_count_pass, ...
        "variable_name_set_pass", comparison.variable_name_set_pass, ...
        "variable_order_pass", comparison.variable_order_pass, ...
        "variable_type_pass", comparison.variable_type_pass, ...
        "required_columns_pass", comparison.required_columns_pass, ...
        "exact_pass", comparison.exact_pass, ...
        "categorical_pass", comparison.categorical_identity_pass, ...
        "numeric_pass", comparison.numeric_pass, ...
        "overall_pass", comparison.file_level_overall_pass);
    receipt.actual_output_namespace = string(actualDir);
    receipt.actual_output_context = actualContext;
    receipt.comparison_tolerance = comparison.comparison_tolerance;
    receipt.max_abs_error = comparison.max_abs_error;
    receipt.max_rel_error = comparison.max_rel_error;
    receipt.baseline_unchanged = baselineUnchanged;
    receipt.comparison_overall_pass = comparison.overall_pass;
    writeJson(receipt, fullfile(regressionRoot, "regression_receipt.json"));

    if ~comparison.overall_pass
        error("Production-recovery regression comparison failed; see %s", ...
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


function prepareRegressionProject(projectRoot, regressionProjectRoot, context, sceneId)
%PREPAREREGRESSIONPROJECT Build an isolated non-production input tree.
% Only metadata and the required GNSS-SDR/navigation/trajectory/geometry
% inputs are copied. The raw_iq path in metadata remains the original source;
% no raw samples are copied or opened by this preparation step.
sceneRoot = fullfile(regressionProjectRoot, "scenes", sceneId);
mkdir(sceneRoot);
copyContextFile(context.metadataFile, fullfile(sceneRoot, "metadata.json"));
copyContextFile(context.trackingFile, fullfile(sceneRoot, "gnss_sdr", ...
    "tracking", fileName(context.trackingFile)));
copyContextFile(context.telemetryFile, fullfile(sceneRoot, "gnss_sdr", ...
    "telemetry", fileName(context.telemetryFile)));
copyContextFiles(context.nmeaFiles, fullfile(sceneRoot, "trajectory"));
copyContextFiles(context.rinexNavFiles, fullfile(sceneRoot, ...
    "navigation", "rinex_nav"));
copyContextFiles(context.satelliteFiles, fullfile(sceneRoot, "satellite"));
end


function copyContextFiles(values, destination)
paths = stringList(values);
assert(~isempty(paths), "Required regression input list is empty.");
for pathValue = reshape(paths, 1, [])
    copyContextFile(pathValue, fullfile(destination, fileName(pathValue)));
end
end


function copyContextFile(source, destination)
source = string(source);
destination = string(destination);
assert(isfile(source), "Regression input is missing: %s", source);
destinationDirectory = string(fileparts(destination));
if ~isfolder(destinationDirectory)
    mkdir(destinationDirectory);
end
[success, message] = copyfile(source, destination, "f");
assert(success, "Could not copy regression input %s: %s", source, message);
end


function name = fileName(pathValue)
[~, name, extension] = fileparts(string(pathValue));
name = name + extension;
end


function paths = stringList(value)
if ischar(value) || (isstring(value) && isscalar(value))
    paths = string(value);
elseif iscell(value)
    paths = string(value);
elseif isstring(value)
    paths = value;
else
    paths = string(value);
end
paths = reshape(paths, [], 1);
paths = paths(strlength(paths) > 0);
end


function comparison = compareStage0Catalogs(baselineMat, actualMat)
comparison = struct("pass", false, "symbol_count_baseline", 0, ...
    "symbol_count_actual", 0, "window_count_baseline", 0, ...
    "window_count_actual", 0, "message", "");
if ~isfile(actualMat)
    comparison.message = "actual_stage0_mat_missing";
    return;
end
baseline = load(baselineMat, "symbolCatalog", "windowCatalog");
actual = load(actualMat, "symbolCatalog", "windowCatalog");
comparison.symbol_count_baseline = height(baseline.symbolCatalog);
comparison.symbol_count_actual = height(actual.symbolCatalog);
comparison.window_count_baseline = height(baseline.windowCatalog);
comparison.window_count_actual = height(actual.windowCatalog);
comparison.pass = tablesExactlyEqual(baseline.symbolCatalog, actual.symbolCatalog) ...
    && tablesExactlyEqual(baseline.windowCatalog, actual.windowCatalog);
comparison.message = ternary(comparison.pass, "PASS", ...
    "stage0_catalog_mismatch");
end


function tf = tablesExactlyEqual(left, right)
leftNames = normalizeTableVariableNames(left.Properties.VariableNames);
rightNames = normalizeTableVariableNames(right.Properties.VariableNames);
if ~isequal(leftNames, rightNames) ...
        || height(left) ~= height(right)
    tf = false;
    return;
end
left = sortrows(left, leftNames);
right = sortrows(right, rightNames);
tf = isequaln(left, right);
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
rowCountPass = true;
columnCountPass = true;
variableNameSetPass = true;
variableOrderPass = true;
variableTypePass = true;
requiredColumnsPass = true;
exactPass = true;
categoricalPass = true;
numericPass = true;
maxAbs = 0;
maxRel = 0;
for spec = reshape(specs, 1, [])
    record = compareTableFile( ...
        fullfile(baselineDir, spec.file), ...
        fullfile(actualDir, spec.file), spec, absTol, relTol);
    records(end + 1, 1) = record; %#ok<AGROW>
    overall = overall && record.overall_pass;
    rowCountPass = rowCountPass && record.row_count_pass;
    columnCountPass = columnCountPass && record.column_count_pass;
    variableNameSetPass = variableNameSetPass ...
        && record.variable_name_set_pass;
    variableOrderPass = variableOrderPass && record.variable_order_pass;
    variableTypePass = variableTypePass && record.variable_type_pass;
    requiredColumnsPass = requiredColumnsPass ...
        && record.required_columns_pass;
    exactPass = exactPass && record.exact_pass;
    categoricalPass = categoricalPass && record.categorical_pass;
    numericPass = numericPass && record.numeric_pass;
    maxAbs = max(maxAbs, record.max_abs_error);
    maxRel = max(maxRel, record.max_rel_error);
end

stage1 = readtable(fullfile(baselineDir, ...
    "stage1_nav_fast_scan.csv"), "VariableNamingRule", "preserve");
stage1Actual = readtable(fullfile(actualDir, ...
    "stage1_nav_fast_scan.csv"), "VariableNamingRule", "preserve");

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
    "file_level_overall_pass", overall, ...
    "row_count_pass", rowCountPass, ...
    "column_count_pass", columnCountPass, ...
    "variable_name_set_pass", variableNameSetPass, ...
    "variable_order_pass", variableOrderPass, ...
    "variable_type_pass", variableTypePass, ...
    "required_columns_pass", requiredColumnsPass, ...
    "exact_pass", exactPass, ...
    "categorical_identity_pass", categoricalPass, ...
    "numeric_pass", numericPass, ...
    "records", records, ...
    "comparison_tolerance", struct("absolute", absTol, "relative", relTol), ...
    "max_abs_error", maxAbs, ...
    "max_rel_error", maxRel, ...
    "stage1_candidate_identity", identityStatus( ...
        stage1CandidateIds(stage1), stage1CandidateIds(stage1Actual)), ...
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
    "confirmed_event_path_identity", confirmedEventPathIdentity( ...
        stage4Summary, stage4SummaryActual, stage4Paths, stage4PathsActual), ...
    "baseline_unchanged", false);
end


function ids = stage1CandidateIds(tableValue)
variableNames = normalizeTableVariableNames(tableValue.Properties.VariableNames);
if any(strcmp(variableNames, "scan_valid"))
    ids = tableValue.window_id(tableValue.scan_valid == 1);
else
    ids = tableValue.window_id;
end
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
baselineNames = normalizeTableVariableNames(baseline.Properties.VariableNames);
actualNames = normalizeTableVariableNames(actual.Properties.VariableNames);
record.baseline_columns = numel(baselineNames);
record.actual_columns = numel(actualNames);
record.missing_in_actual = strjoin( ...
    setdiff(baselineNames, actualNames, "stable"), ",");
record.extra_in_actual = strjoin( ...
    setdiff(actualNames, baselineNames, "stable"), ",");
record.column_count_pass = record.baseline_columns == record.actual_columns;
record.variable_name_set_pass = isempty(record.missing_in_actual) ...
    && isempty(record.extra_in_actual);
record.variable_order_pass = isequal(baselineNames, actualNames);
baselineTypes = tableVariableTypes(baseline, baselineNames);
actualTypes = tableVariableTypes(actual, actualNames);
record.baseline_types = strjoin(baselineTypes, "|");
record.actual_types = strjoin(actualTypes, "|");
record.types_equal = isequal(baselineTypes, actualTypes);
record.variable_type_pass = record.types_equal;
record.row_count_pass = record.baseline_rows == record.actual_rows;
record.schema_pass = record.column_count_pass ...
    && record.variable_name_set_pass ...
    && record.variable_order_pass ...
    && record.variable_type_pass;
keyNames = cellstr(spec.keys);
requestedExactNames = cellstr(spec.exact);
missingKeys = setdiff(keyNames, baselineNames, "stable");
missingExactNames = setdiff(requestedExactNames, baselineNames, "stable");
record.missing_required_columns = strjoin( ...
    unique([missingKeys, missingExactNames], "stable"), ",");
record.required_columns_pass = isempty(record.missing_required_columns);
record.exact_pass = false;
record.categorical_pass = false;
record.numeric_pass = false;
record.overall_pass = false;

if ~record.schema_pass
    record.message = "column_schema_mismatch";
    return;
end
if ~record.required_columns_pass
    record.message = "required_column_missing";
    return;
end
if ~record.row_count_pass
    record.message = "row_count_mismatch";
    return;
end
baseline = sortrows(baseline, keyNames);
actual = sortrows(actual, keyNames);

exactNames = requestedExactNames;
record.exact_pass = true;
for nameIndex = 1:numel(exactNames)
    name = scalarTableVariableName(exactNames{nameIndex});
    if ~sameExact(baseline.(name), actual.(name))
        record.exact_pass = false;
        record.exact_mismatch_count = record.exact_mismatch_count + 1;
    end
end

record.categorical_pass = true;
record.numeric_pass = true;
for nameIndex = 1:numel(baselineNames)
    name = scalarTableVariableName(baselineNames{nameIndex});
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
            record.numeric_pass = false;
        end
    elseif ~sameExact(left, right)
        record.categorical_pass = false;
        record.exact_mismatch_count = record.exact_mismatch_count + 1;
    end
end

record.overall_pass = record.row_count_pass ...
    && record.schema_pass ...
    && record.required_columns_pass ...
    && record.exact_pass ...
    && record.categorical_pass ...
    && record.numeric_pass;
record.pass = record.overall_pass;
if record.overall_pass
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
variableNames = normalizeTableVariableNames(tableValue.Properties.VariableNames);
if any(strcmp(variableNames, "is_multipath"))
    identity = [identity, double(tableValue.is_multipath)];
end
end


function identity = confirmedEventPathIdentity(summary, summaryActual, ...
        paths, pathsActual)
%CONFIRMEDEVENTPATHIDENTITY Check the explicit Stage4 confirmation fields.
identity = struct("pass", false, "joint_valid_pass", false, ...
    "joint_multipath_count_pass", false, "path_identity_pass", false, ...
    "baseline_confirmed_event_count", 0, ...
    "actual_confirmed_event_count", 0, ...
    "baseline_confirmed_path_count", 0, ...
    "actual_confirmed_path_count", 0);
identity.joint_valid_pass = sameExact( ...
    summary.joint_valid, summaryActual.joint_valid);
identity.joint_multipath_count_pass = sameExact( ...
    summary.joint_multipath_count, summaryActual.joint_multipath_count);
pathNames = normalizeTableVariableNames(paths.Properties.VariableNames);
actualPathNames = normalizeTableVariableNames( ...
    pathsActual.Properties.VariableNames);
if any(strcmp(pathNames, "is_multipath")) ...
        && any(strcmp(actualPathNames, "is_multipath"))
    identity.path_identity_pass = sameExact( ...
        pathIdentity(paths), pathIdentity(pathsActual));
    identity.baseline_confirmed_path_count = sum(paths.is_multipath == 1);
    identity.actual_confirmed_path_count = sum(pathsActual.is_multipath == 1);
else
    identity.path_identity_pass = false;
end
identity.baseline_confirmed_event_count = sum( ...
    summary.joint_multipath_count > 0);
identity.actual_confirmed_event_count = sum( ...
    summaryActual.joint_multipath_count > 0);
identity.pass = identity.joint_valid_pass ...
    && identity.joint_multipath_count_pass ...
    && identity.path_identity_pass;
end


function types = tableVariableTypes(tableValue, names)
%TABLEVARIABLETYPES Capture imported MATLAB column classes for schema QA.
types = cell(1, numel(names));
for index = 1:numel(names)
    name = scalarTableVariableName(names{index});
    types{index} = class(tableValue.(name));
end
end


function names = normalizeTableVariableNames(value)
%NORMALIZETABLEVARIABLENAMES Return a canonical row cell array of char names.
% MATLAB table metadata can expose VariableNames as either a cell array of
% character vectors or a string array.  Normalize both representations before
% schema comparison and dynamic table indexing.
if isstring(value)
    assert(isvector(value), ...
        "Table variable names must be a vector of string scalars.");
    names = cellstr(reshape(value, 1, []));
elseif iscell(value)
    names = cell(1, numel(value));
    for index = 1:numel(value)
        names{index} = scalarTableVariableName(value{index});
    end
elseif ischar(value)
    assert(isrow(value), ...
        "A character matrix cannot represent table variable names.");
    names = {value};
else
    error("Unsupported table variable-name representation: %s", class(value));
end
names = reshape(names, 1, []);
end


function name = scalarTableVariableName(value)
%SCALARTABLEVARIABLENAME Extract one char row for table dynamic indexing.
if iscell(value)
    assert(isscalar(value), ...
        "A dynamic table variable name must be scalar, not a cell array.");
    value = value{1};
end
if isstring(value)
    assert(isscalar(value), ...
        "A dynamic table variable name must be a string scalar.");
    name = char(value);
elseif ischar(value)
    assert(isrow(value), ...
        "A dynamic table variable name must be a character vector.");
    name = value;
else
    error("Unsupported dynamic table variable-name type: %s", class(value));
end
assert(~isempty(name), "A table variable name cannot be empty.");
end


function context = validateActualContext(actualDir, sceneId, prnLabel, ...
        trackingChannel)
%VALIDATEACTUALCONTEXT Validate scope without opening raw IQ.
contextFile = fullfile(actualDir, "run_context.json");
assert(isfile(contextFile), ...
    "Existing actual output is missing run_context.json: %s", contextFile);
context = readJsonWithBom(contextFile);
assert(isfield(context, "sceneId") && string(context.sceneId) == sceneId, ...
    "Existing actual scene identity does not match the frozen G28 task.");
assert(isfield(context, "prnLabel") && string(context.prnLabel) == prnLabel, ...
    "Existing actual PRN identity does not match the frozen G28 task.");
assert(isfield(context, "trackingChannel") ...
        && double(context.trackingChannel) == trackingChannel, ...
    "Existing actual tracking channel does not match the frozen G28 task.");
assert(isfield(context, "samplingRateHz") ...
        && double(context.samplingRateHz) == 10230000, ...
    "Existing actual output is not a 10.23 MHz result.");
end


function tf = isPathWithinRoot(candidatePath, rootPath)
%ISPATHWITHINROOT Enforce canonical, case-insensitive Windows containment.
% Both inputs are canonicalized before comparison.  The final comparison is
% explicitly bounded by a separator so that darkroom and darkroom2 cannot
% collide.  Any canonicalization failure fails closed.
try
    candidate = canonicalWindowsPath(candidatePath);
    root = canonicalWindowsPath(rootPath);
catch
    tf = false;
    return;
end

separator = char(92);
if isempty(candidate) || isempty(root)
    tf = false;
    return;
end
if root(end) ~= separator
    rootWithSeparator = [root, separator];
else
    rootWithSeparator = root;
end
tf = strcmpi(candidate, root) ...
    || (numel(candidate) >= numel(rootWithSeparator) ...
        && strncmpi(candidate, rootWithSeparator, numel(rootWithSeparator)));
end


function pathValue = canonicalWindowsPath(value)
%CANONICALWINDOWSPATH Produce an absolute, separator-normalized Windows path.
raw = scalarPathText(value);
separator = char(92);
raw = strrep(raw, char(47), separator);
assert(~isempty(raw), "Path cannot be empty.");

% java.io.File.getCanonicalPath resolves relative paths, '.', '..', and
% duplicate separators without changing file contents.  The lexical fallback
% keeps the containment check deterministic if MATLAB is run without a JVM.
if usejava('jvm')
    fileObject = javaObject('java.io.File', raw);
    pathValue = char(fileObject.getCanonicalPath());
else
    pathValue = lexicalNormalizeWindowsPath(raw);
end
pathValue = strrep(pathValue, char(47), separator);
pathValue = trimWindowsTrailingSeparators(pathValue);
if numel(pathValue) >= 2 && pathValue(2) == ':'
    pathValue(1) = upper(pathValue(1));
end
end


function value = scalarPathText(pathValue)
%SCALARPATHTEXT Convert one char/string path to a character vector.
if isstring(pathValue)
    assert(isscalar(pathValue), "Path input must be a string scalar.");
    value = char(pathValue);
elseif ischar(pathValue)
    assert(isrow(pathValue), "Path input must be a character vector.");
    value = pathValue;
else
    error("Unsupported path input type: %s", class(pathValue));
end
end


function pathValue = lexicalNormalizeWindowsPath(raw)
%LEXICALNORMALIZEWINDOWSPATH JVM-free absolute Windows path normalization.
separator = char(92);
if numel(raw) >= 2 && raw(2) == ':'
    assert(numel(raw) >= 3 && raw(3) == separator, ...
        "Drive-relative Windows paths are not supported.");
elseif numel(raw) >= 2 && raw(1) == separator && raw(2) == separator
    % UNC paths are already absolute.
elseif ~isempty(raw) && raw(1) == separator
    current = strrep(char(pwd), char(47), separator);
    assert(numel(current) >= 2 && current(2) == ':', ...
        "Root-relative path cannot be resolved without a drive.");
    raw = [current(1:2), raw];
else
    raw = fullfile(char(pwd), raw);
    raw = strrep(raw, char(47), separator);
end

if numel(raw) >= 2 && raw(1) == separator && raw(2) == separator
    parts = regexp(raw(3:end), '\\+', 'split');
    assert(numel(parts) >= 2 && ~isempty(parts{1}) && ~isempty(parts{2}), ...
        "Invalid UNC path.");
    prefix = [separator, separator, parts{1}, separator, parts{2}];
    remainder = parts(3:end);
else
    assert(numel(raw) >= 3 && raw(2) == ':' && raw(3) == separator, ...
        "Path is not absolute after normalization.");
    prefix = raw(1:3);
    remainder = regexp(raw(4:end), '\\+', 'split');
end

stack = cell(1, 0);
for index = 1:numel(remainder)
    part = remainder{index};
    if isempty(part) || strcmp(part, '.')
        continue;
    elseif strcmp(part, '..')
        if ~isempty(stack)
            stack(end) = [];
        end
    else
        stack{end + 1} = part; %#ok<AGROW>
    end
end
if isempty(stack)
    pathValue = prefix;
else
    pathValue = [prefix, strjoin(stack, separator)];
end
end


function pathValue = trimWindowsTrailingSeparators(pathValue)
separator = char(92);
while numel(pathValue) > 3 && pathValue(end) == separator
    pathValue(end) = [];
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


function writeSchemaComparisonCsv(records, filename)
%WRITESCHEMACOMPARISONCSV Persist one explicit schema row per Stage file.
schemaRecords = repmat(emptySchemaComparisonRecord(), 0, 1);
for index = 1:numel(records)
    schemaRecords(end + 1, 1) = struct( ...
        "file", records(index).file, ...
        "baseline_columns", records(index).baseline_columns, ...
        "actual_columns", records(index).actual_columns, ...
        "missing_in_actual", records(index).missing_in_actual, ...
        "extra_in_actual", records(index).extra_in_actual, ...
        "order_equal", records(index).variable_order_pass, ...
        "types_equal", records(index).types_equal, ...
        "baseline_types", records(index).baseline_types, ...
        "actual_types", records(index).actual_types); %#ok<AGROW>
end
if ~isempty(schemaRecords)
    writetable(struct2table(schemaRecords), filename);
end
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
    "actual_rows", 0, "row_count_pass", false, ...
    "baseline_columns", 0, "actual_columns", 0, ...
    "column_count_pass", false, "variable_name_set_pass", false, ...
    "variable_order_pass", false, "variable_type_pass", false, ...
    "required_columns_pass", false, "schema_pass", false, ...
    "missing_in_actual", "", "extra_in_actual", "", ...
    "missing_required_columns", "", "baseline_types", "", ...
    "actual_types", "", "types_equal", false, ...
    "exact_pass", false, "overall_pass", false, ...
    "exact_mismatch_count", 0, ...
    "numeric_mismatch_count", 0, "max_abs_error", 0, ...
    "max_rel_error", 0);
end


function record = emptySchemaComparisonRecord()
record = struct( ...
    "file", "", "baseline_columns", 0, "actual_columns", 0, ...
    "missing_in_actual", "", "extra_in_actual", "", ...
    "order_equal", false, "types_equal", false, ...
    "baseline_types", "", "actual_types", "");
end
