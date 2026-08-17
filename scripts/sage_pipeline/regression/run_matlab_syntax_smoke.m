function result = run_matlab_syntax_smoke(varargin)
%RUN_MATLAB_SYNTAX_SMOKE Parse-only gate with diagnostic reporting.
% This helper invokes MATLAB's Code Analyzer parser only. It does not load
% raw IQ, construct Stage0, call the SAGE core, or run any pipeline stage.

scriptDir = fileparts(mfilename("fullpath"));
defaultProjectRoot = fileparts(fileparts(fileparts(scriptDir)));
parser = inputParser;
addParameter(parser, "ProjectRoot", defaultProjectRoot, @(value) ...
    ischar(value) || (isstring(value) && isscalar(value)));
addParameter(parser, "Scope", "all", @(value) ...
    ischar(value) || (isstring(value) && isscalar(value)));
parse(parser, varargin{:});
projectRoot = string(parser.Results.ProjectRoot);
scope = lower(string(parser.Results.Scope));

if scope == "rain"
    files = [
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "run_rain_sage_pipeline.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "build_rain_stage0.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "run_rain_sage_stage1_stage4.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "default_rain_sage_configuration.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "compute_rain_doppler_bound.m")];
elseif scope == "all"
    files = [
        fullfile(projectRoot, "scripts", "sage_pipeline", "core", ...
            "run_sage_stage1_stage4_core.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "core", ...
            "default_sage_configuration.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "core", ...
            "compute_sage_doppler_bound.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "regression", ...
            "run_shared_core_regression.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "run_rain_sage_pipeline.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "build_rain_stage0.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "run_rain_sage_stage1_stage4.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "default_rain_sage_configuration.m")
        fullfile(projectRoot, "scripts", "sage_pipeline", "rain", ...
            "compute_rain_doppler_bound.m")];
else
    error("Unsupported syntax-smoke Scope: %s", scope);
end

records = repmat(struct( ...
    "file", "", "status", "NOT_RUN", "message", "", ...
    "diagnostic_count", 0, "error_count", 0), 0, 1);
diagnostics = repmat(emptyDiagnostic(), 0, 1);
allPass = true;
for index = 1:numel(files)
    filePath = string(files(index));
    record = struct("file", filePath, "status", "FAIL", ...
        "message", "", "diagnostic_count", 0, "error_count", 0);
    try
        assert(isfile(filePath), "MATLAB source is missing: %s", filePath);
        issues = checkcode(char(filePath), "-id");
        fileDiagnostics = normalizeDiagnostics(filePath, issues);
        diagnostics = [diagnostics; fileDiagnostics]; %#ok<AGROW>
        hasError = any(string({fileDiagnostics.severity}) == "error");
        message = diagnosticSummary(fileDiagnostics);
        record.diagnostic_count = numel(fileDiagnostics);
        record.error_count = nnz(string({fileDiagnostics.severity}) == "error");
        if hasError
            record.message = message;
            allPass = false;
        else
            record.status = ternary(record.diagnostic_count == 0, ...
                "PASS", "PASS_WITH_WARNINGS");
            record.message = message;
        end
    catch exception
        record.message = string(exception.message);
        diagnostic = emptyDiagnostic();
        diagnostic.file = filePath;
        diagnostic.severity = "error";
        diagnostic.id = "CHECKCODE_EXCEPTION";
        diagnostic.message = string(exception.message);
        diagnostics(end + 1, 1) = diagnostic; %#ok<AGROW>
        record.diagnostic_count = 1;
        record.error_count = 1;
        allPass = false;
    end
    records(end + 1, 1) = record; %#ok<AGROW>
    fprintf("%s %s\n", record.status, filePath);
    if strlength(record.message) > 0
        fprintf("  %s\n", record.message);
    end
end

result = struct( ...
    "status", ternary(allPass, "PASS", "FAIL"), ...
    "scope", scope, ...
    "matlab_syntax_smoke", allPass, ...
    "raw_iq_opened", false, ...
    "sage_executed", false, ...
    "records", records, ...
    "diagnostics", diagnostics);
if allPass
    fprintf("MATLAB_SYNTAX_SMOKE=PASS\n");
else
    fprintf("MATLAB_SYNTAX_SMOKE=FAIL\n");
    error("MATLAB syntax smoke failed; numerical regression is blocked.");
end
end


function diagnostics = normalizeDiagnostics(filePath, issues)
diagnostics = repmat(emptyDiagnostic(), 0, 1);
if isempty(issues)
    return;
end
if iscell(issues)
    issues = [issues{:}];
end
assert(isstruct(issues), ...
    "MATLAB checkcode returned an unsupported diagnostic type.");
for index = 1:numel(issues)
    issue = issues(index);
    diagnostic = emptyDiagnostic();
    diagnostic.file = string(filePath);
    diagnostic.line = getNumericField(issue, "line");
    diagnostic.column = getNumericField(issue, "column");
    diagnostic.id = getStringField(issue, "id", "CHECKCODE_DIAGNOSTIC");
    diagnostic.message = getStringField(issue, "message", "");
    explicitSeverity = getStringField(issue, "severity", "");
    if strlength(explicitSeverity) == 0
        explicitSeverity = getStringField(issue, "type", "");
    end
    diagnostic.severity = inferSeverity(explicitSeverity, diagnostic.message);
    diagnostics(end + 1, 1) = diagnostic; %#ok<AGROW>
    fprintf("DIAGNOSTIC file=%s line=%s column=%s severity=%s id=%s message=%s\n", ...
        diagnostic.file, numberText(diagnostic.line), ...
        numberText(diagnostic.column), diagnostic.severity, ...
        diagnostic.id, diagnostic.message);
end
end


function message = diagnosticSummary(diagnostics)
if isempty(diagnostics)
    message = "no diagnostics";
    return;
end
parts = strings(numel(diagnostics), 1);
for index = 1:numel(diagnostics)
    parts(index) = sprintf("%s:%s:%s [%s] %s", ...
        diagnostics(index).file, numberText(diagnostics(index).line), ...
        numberText(diagnostics(index).column), diagnostics(index).severity, ...
        diagnostics(index).message);
end
message = strjoin(parts, " | ");
end


function record = emptyDiagnostic()
record = struct( ...
    "file", "", "line", nan, "column", nan, ...
    "severity", "", "id", "", "message", "");
end


function value = getNumericField(record, name)
value = nan;
if isfield(record, name)
    candidate = record.(name);
    if isnumeric(candidate) && isscalar(candidate)
        value = double(candidate);
    end
end
end


function value = getStringField(record, name, defaultValue)
value = string(defaultValue);
if isfield(record, name)
    candidate = record.(name);
    if ischar(candidate) || (isstring(candidate) && isscalar(candidate))
        value = string(candidate);
    end
end
end


function severity = inferSeverity(explicitSeverity, message)
text = lower(strtrim(string(explicitSeverity)));
if any(contains(text, ["error", "fatal", "syntax", "parse"]))
    severity = "error";
    return;
end
messageText = lower(string(message));
if any(contains(messageText, ["syntax error", "invalid expression", ...
        "parse error", "unexpected token", "unbalanced delimiter", ...
        "not a function"]))
    severity = "error";
else
    severity = "warning";
end
end


function text = numberText(value)
if isfinite(value)
    text = string(sprintf("%.0f", value));
else
    text = "?";
end
end


function value = ternary(condition, trueValue, falseValue)
if condition
    value = trueValue;
else
    value = falseValue;
end
end
