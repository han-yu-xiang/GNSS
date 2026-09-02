function run_dll_code_bias_study(contractPath)
%RUN_DLL_CODE_BIAS_STUDY Quantify signal-level DLL zero-crossing bias.

if nargin < 1
    contractPath = fullfile(fileparts(fileparts(fileparts(fileparts(mfilename("fullpath"))))), ...
        "docs", "vtc2027_spring", "evidence", "validation_v1", ...
        "validation_contract.json");
end
contract = jsondecode(fileread(contractPath));
outDir = string(contract.output_namespace);
layer2Path = fullfile(outDir, "layer2_multipath_stress_trials.csv");
assert(isfile(layer2Path), "Layer 2 trials are required before DLL study.");
layer2 = readtable(layer2Path, "TextType", "string");
successful = layer2(layer2.injected_match == 1, :);
assert(height(successful) > 0, ...
    "No successful Layer 2 recovery rows are available for error-aware DLL study.");

spacingChips = double(contract.dll.early_late_space_chips);
metersPerChip = double(contract.dll.meters_per_chip);
offsetGrid = -1:0.01:1;
rows = repmat(emptyDllRow(), 0, 1);

for eventIndex = 1:numel(contract.layer2.events)
    caseJson = contract.layer2.events(eventIndex);
    data = vtc_validation_common("prepare_case", contract, caseJson);
    [observations, ~] = vtc_validation_common("load_observations", data);
    [paths, fit] = loadNativeSelectedPaths(contract, caseJson);
    assert(fit.selectedOrder >= 2, "DLL case does not contain a selected secondary path.");
    amplitudes = vtc_validation_common("solve_amplitudes", observations, data, paths);
    direct = paths(1);
    eventLabel = string(sprintf("%s_%s_%d", data.sceneId, ...
        data.prnLabel, data.centerWindowId));
    fprintf("DLL case %s loaded with L=%d\n", eventLabel, fit.selectedOrder);

    for snapshot = 1:numel(observations)
        context = data.contexts{snapshot};
        [preBias, ~, preValid] = vtc_validation_common( ...
            "dll_zero_crossing", observations{snapshot}, context, ...
            direct, spacingChips, offsetGrid);
        rows(end + 1, 1) = makeDllRow( ...
            eventLabel, data, snapshot, "pre_cancellation", "NONE", ...
            preBias, preValid, metersPerChip, nan, nan, nan); %#ok<AGROW>

        fittedResidual = vtc_validation_common( ...
            "cancel_secondary", observations{snapshot}, context, ...
            paths, amplitudes(:, snapshot), 0, 0, 0);
        [fittedBias, ~, fittedValid] = vtc_validation_common( ...
            "dll_zero_crossing", fittedResidual, context, direct, ...
            spacingChips, offsetGrid);
        rows(end + 1, 1) = makeDllRow( ...
            eventLabel, data, snapshot, "fitted_model_cancellation", "NONE", ...
            fittedBias, fittedValid, metersPerChip, nan, nan, nan); %#ok<AGROW>

        for errorIndex = 1:height(successful)
            delayError = successful.injected_delay_error_samples(errorIndex);
            dopplerError = successful.injected_doppler_error_hz(errorIndex);
            powerError = successful.injected_power_error_db(errorIndex);
            errorResidual = vtc_validation_common( ...
                "cancel_secondary", observations{snapshot}, context, ...
                paths, amplitudes(:, snapshot), delayError, dopplerError, powerError);
            [errorBias, ~, errorValid] = vtc_validation_common( ...
                "dll_zero_crossing", errorResidual, context, direct, ...
                spacingChips, offsetGrid);
            rows(end + 1, 1) = makeDllRow( ...
                eventLabel, data, snapshot, "error_aware_cancellation", ...
                successful.trial_id(errorIndex), errorBias, errorValid, ...
                metersPerChip, delayError, dopplerError, powerError); %#ok<AGROW>
        end
    end
end

caseTable = struct2table(rows);
writetable(caseTable, fullfile(outDir, "dll_code_bias_cases.csv"));
summaryTable = makeDllSummary(caseTable);
writetable(summaryTable, fullfile(outDir, "dll_code_bias_summary.csv"));
fprintf("DLL study wrote %d rows to %s\n", height(caseTable), outDir);
end


function [paths, fit] = loadNativeSelectedPaths(contract, caseJson)
prnLabel = string(caseJson.prn_label);
centerId = double(caseJson.center_window_id);
matPath = vtc_validation_common("source_path", contract, prnLabel + "_stage4_mat");
loaded = load(matPath, "jointFits");
fit = [];
for index = 1:numel(loaded.jointFits)
    candidate = loaded.jointFits{index};
    if ~isempty(candidate) && double(candidate.centerWindowId) == centerId
        fit = candidate;
        break;
    end
end
assert(~isempty(fit), "No selected Stage4 fit at %s/%d.", prnLabel, centerId);
paths = fit.models{fit.selectedOrder}.paths;
end


function row = emptyDllRow()
row = struct( ...
    "event_label", "", "scene_id", "", "prn_label", "", ...
    "environment", "", "center_window_id", nan, "snapshot_index", nan, ...
    "mode", "", "error_source_trial_id", "", ...
    "zero_crossing_chips", nan, "bias_chips", nan, "bias_m", nan, ...
    "absolute_bias_chips", nan, "absolute_bias_m", nan, ...
    "valid_crossing", false, "delay_error_samples", nan, ...
    "doppler_error_hz", nan, "power_error_db", nan);
end


function row = makeDllRow(eventLabel, data, snapshot, mode, trialId, ...
    biasChips, valid, metersPerChip, delayError, dopplerError, powerError)
row = emptyDllRow();
row.event_label = eventLabel;
row.scene_id = data.sceneId;
row.prn_label = data.prnLabel;
row.environment = data.environment;
row.center_window_id = data.centerWindowId;
row.snapshot_index = snapshot;
row.mode = string(mode);
row.error_source_trial_id = string(trialId);
row.zero_crossing_chips = biasChips;
row.bias_chips = biasChips;
row.bias_m = biasChips * metersPerChip;
row.absolute_bias_chips = abs(biasChips);
row.absolute_bias_m = abs(biasChips * metersPerChip);
row.valid_crossing = valid;
row.delay_error_samples = delayError;
row.doppler_error_hz = dopplerError;
row.power_error_db = powerError;
end


function summary = makeDllSummary(cases)
template = struct( ...
    "event_label", "", "environment", "", "mode", "", ...
    "row_count", nan, "valid_crossing_count", nan, ...
    "median_abs_bias_chips", nan, "p10_abs_bias_chips", nan, ...
    "p90_abs_bias_chips", nan, "median_abs_bias_m", nan, ...
    "p10_abs_bias_m", nan, "p90_abs_bias_m", nan);
summaryRows = repmat(template, 0, 1);
keys = unique(cases(:, {"event_label", "environment", "mode"}), "rows");
for index = 1:height(keys)
    subset = cases(strcmp(cases.event_label, keys.event_label(index)) ...
        & strcmp(cases.environment, keys.environment(index)) ...
        & strcmp(cases.mode, keys.mode(index)), :);
    row = template;
    row.event_label = string(keys.event_label(index));
    row.environment = string(keys.environment(index));
    row.mode = string(keys.mode(index));
    row.row_count = height(subset);
    row.valid_crossing_count = nnz(subset.valid_crossing);
    valuesChips = subset.absolute_bias_chips(subset.valid_crossing == 1);
    valuesMeters = subset.absolute_bias_m(subset.valid_crossing == 1);
    if ~isempty(valuesChips)
        row.median_abs_bias_chips = median(valuesChips);
        row.p10_abs_bias_chips = percentile(valuesChips, 10);
        row.p90_abs_bias_chips = percentile(valuesChips, 90);
        row.median_abs_bias_m = median(valuesMeters);
        row.p10_abs_bias_m = percentile(valuesMeters, 10);
        row.p90_abs_bias_m = percentile(valuesMeters, 90);
    end
    summaryRows(end + 1, 1) = row; %#ok<AGROW>
end
summary = struct2table(summaryRows);
end


function value = percentile(values, percent)
values = sort(values(:));
if isempty(values)
    value = nan;
    return;
end
position = 1 + (numel(values) - 1) * percent / 100;
lower = floor(position);
upper = ceil(position);
if lower == upper
    value = values(lower);
else
    value = values(lower) + (position - lower) * (values(upper) - values(lower));
end
end
