function result = run_rain_matlab_syntax_smoke(varargin)
%RUN_RAIN_MATLAB_SYNTAX_SMOKE Parse-only gate for the standalone Rain branch.
% This entry does not open raw IQ, construct Stage0, run SAGE, or inspect
% shared-core/regression files. It delegates diagnostic formatting to the
% generic parse-only helper with Scope="rain".

scriptDir = fileparts(mfilename("fullpath"));
regressionDir = fullfile(fileparts(scriptDir), "regression");
assert(isfile(fullfile(regressionDir, "run_matlab_syntax_smoke.m")), ...
    "Generic MATLAB syntax smoke helper is missing: %s", regressionDir);
addpath(regressionDir, "-begin");
result = run_matlab_syntax_smoke(varargin{:}, "Scope", "rain");
end
