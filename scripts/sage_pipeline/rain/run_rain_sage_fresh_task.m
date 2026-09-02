function result = run_rain_sage_fresh_task(sceneId, prn, outputDir, varargin)
%RUN_RAIN_SAGE_FRESH_TASK Execute one Rain task in a new immutable namespace.
%
% This is a rerun-only orchestration entry.  It reuses the existing Rain
% Stage0 adapter and branch-local Stage1-Stage4 implementation without
% changing their numerical code.  The old rain_sage_v1 namespace is never
% reused, resumed, overwritten, or deleted.

scriptDir = fileparts(mfilename("fullpath"));
addpath(scriptDir, "-begin");

parser = inputParser;
addRequired(parser, "sceneId", @(v) ischar(v) || (isstring(v) && isscalar(v)));
addRequired(parser, "prn", @(v) isnumeric(v) || ischar(v) || ...
    (isstring(v) && isscalar(v)));
addRequired(parser, "outputDir", @(v) ischar(v) || ...
    (isstring(v) && isscalar(v)));
addParameter(parser, "TrackingChannel", [], @(v) isnumeric(v) && ...
    isscalar(v) && isfinite(v) && v == round(v) && v >= 0);
addParameter(parser, "ProjectRoot", fileparts(fileparts(fileparts( ...
    mfilename("fullpath")))), @(v) ischar(v) || ...
    (isstring(v) && isscalar(v)));
addParameter(parser, "Resume", false, @(v) ...
    (islogical(v) || isnumeric(v)) && isscalar(v));
parse(parser, sceneId, prn, outputDir, varargin{:});
options = parser.Results;

assert(~logical(options.Resume), ...
    "Rain fresh rerun is new-only; Resume=true is rejected.");
assert(~isempty(options.TrackingChannel), ...
    "TrackingChannel must be supplied explicitly.");

[prnNumber, prnLabel] = normalizeRainPrn(prn);
sceneId = string(sceneId);
projectRoot = string(options.ProjectRoot);
outputDir = string(outputDir);
expectedOutput = fullfile(projectRoot, "scenes", sceneId, ...
    "sage_results", "rain_sage_rerun_v1_20260827_r4", prnLabel);
assert(strcmpi(char(outputDir), char(expectedOutput)), ...
    "Fresh Rain output must use the frozen rerun namespace: %s", ...
    expectedOutput);
assert(~isfolder(outputDir) && ~isfile(outputDir), ...
    "Fresh Rain output namespace already exists; new-only refuses reuse: %s", ...
    outputDir);

% Stage0 writes only the new output directory.  Its configuration explicitly
% has resumeExistingStages=false, and the Stage1-Stage4 call below receives
% that same non-resumable configuration.
stage0 = build_rain_stage0(sceneId, prnNumber, ...
    "TrackingChannel", options.TrackingChannel, ...
    "ProjectRoot", projectRoot, ...
    "OutputDir", outputDir, ...
    "WriteOutputs", true);
coreResult = run_rain_sage_stage1_stage4( ...
    stage0.windowCatalog, stage0.symbolCatalog, stage0.raw_file, ...
    outputDir, stage0.cfg);

% Keep the orchestration result scalar even though stage results contain
% variable-size tables/cell arrays.
result = struct();
result.status = "RAIN_FRESH_RERUN_COMPLETED";
result.scene_id = sceneId;
result.prn = prnLabel;
result.prn_number = prnNumber;
result.tracking_channel = double(options.TrackingChannel);
result.sample_rate_hz = 10230000;
result.output_namespace = outputDir;
result.resume = false;
result.new_only = true;
result.stage0_symbol_count = height(stage0.symbolCatalog);
result.stage0_window_count = height(stage0.windowCatalog);
result.stage1_scanned_windows = height(coreResult.stage1Table);
result.stage1_candidate_windows = numel(coreResult.candidateIndices);
result.stage2_model_rows = height(coreResult.modelTable);
result.stage2_selected_rows = height(coreResult.selectedTable);
result.stage3_reliable_centers = height(coreResult.reliableTable);
result.stage4_joint_rows = height(coreResult.jointSummaryTable);
result.stage4_joint_paths = height(coreResult.jointPathTable);
assert(isstruct(result) && isscalar(result), ...
    "Fresh Rain result container must remain scalar.");
end


function [prnNumber, prnLabel] = normalizeRainPrn(prn)
if isnumeric(prn)
    prnNumber = double(prn);
else
    text = upper(strtrim(string(prn)));
    text = erase(text, ["GPS", "PRN", "G"]);
    prnNumber = str2double(text);
end
assert(isfinite(prnNumber) && prnNumber == round(prnNumber) ...
    && prnNumber >= 1 && prnNumber <= 32, ...
    "Rain PRN must identify GPS 1 through 32.");
prnLabel = compose("G%02d", prnNumber);
end
