function result = run_production_matlab_syntax_smoke(varargin)
%RUN_PRODUCTION_MATLAB_SYNTAX_SMOKE Parse-only gate for production entry.
% This helper invokes MATLAB Code Analyzer on the recovered monolithic
% production file only. It does not open raw IQ, build Stage0, call SAGE, or
% write a production result.

scriptDir = fileparts(mfilename("fullpath"));
defaultProjectRoot = fileparts(fileparts(fileparts(scriptDir)));
parser = inputParser;
addParameter(parser, "ProjectRoot", defaultProjectRoot, @(value) ...
    ischar(value) || (isstring(value) && isscalar(value)));
parse(parser, varargin{:});
projectRoot = string(parser.Results.ProjectRoot);
productionFile = fullfile(projectRoot, "scripts", "sage_pipeline", ...
    "run_nav_sage_pipeline.m");

record = struct("file", productionFile, "status", "FAIL", ...
    "diagnostic_count", 0, "error_count", 0, "message", "");
diagnostics = repmat(emptyDiagnostic(), 0, 1);
allPass = false;
try
    assert(isfile(productionFile), ...
        "Production MATLAB source is missing: %s", productionFile);
    issues = checkcode(char(productionFile), "-id");
    diagnostics = normalizeDiagnostics(productionFile, issues);
    record.diagnostic_count = numel(diagnostics);
    record.error_count = nnz(string({diagnostics.severity}) == "error");
    allPass = record.error_count == 0;
    if allPass
        record.status = ternary(record.diagnostic_count == 0, ...
            "PASS", "PASS_WITH_WARNINGS");
    end
    record.message = diagnosticSummary(diagnostics);
catch exception
    record.message = string(exception.message);
    diagnostic = emptyDiagnostic();
    diagnostic.file = productionFile;
    diagnostic.severity = "error";
    diagnostic.id = "CHECKCODE_EXCEPTION";
    diagnostic.message = string(exception.message);
    diagnostics(end + 1, 1) = diagnostic; %#ok<AGROW>
    record.diagnostic_count = 1;
    record.error_count = 1;
end

fprintf("%s %s\n", record.status, productionFile);
if strlength(record.message) > 0
    fprintf("  %s\n", record.message);
end
result = struct( ...
    "status", ternary(allPass, "PASS", "FAIL"), ...
    "matlab_syntax_smoke", allPass, ...
    "production_file", productionFile, ...
    "raw_iq_opened", false, ...
    "sage_executed", false, ...
    "record", record, ...
    "diagnostics", diagnostics);
if allPass
    fprintf("PRODUCTION_MATLAB_SYNTAX_SMOKE=PASS\n");
else
    fprintf("PRODUCTION_MATLAB_SYNTAX_SMOKE=FAIL\n");
    error("Production MATLAB syntax smoke failed; G28 regression is blocked.");
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
