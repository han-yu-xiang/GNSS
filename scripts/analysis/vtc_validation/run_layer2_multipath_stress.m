function run_layer2_multipath_stress(contractPath)
%RUN_LAYER2_MULTIPATH_STRESS Test incremental recovery in real multipath.

if nargin < 1
    contractPath = fullfile(fileparts(fileparts(fileparts(fileparts(mfilename("fullpath"))))), ...
        "docs", "vtc2027_spring", "evidence", "validation_v1", ...
        "validation_contract.json");
end
contract = jsondecode(fileread(contractPath));
assert(~contract.production_execution && ~contract.resume, ...
    "Validation contract is not isolated from production/resume.");
outDir = string(contract.output_namespace);
if ~isfolder(outDir)
    mkdir(outDir);
end

estimator = vtc_validation_common("estimator", contract);
tolerances = vtc_validation_common("tolerances", contract);
trialRows = repmat(emptyLayer2Row(), 0, 1);
trialOrdinal = 0;

for eventIndex = 1:numel(contract.layer2.events)
    caseJson = contract.layer2.events(eventIndex);
    data = vtc_validation_common("prepare_case", contract, caseJson);
    [baseObservations, readInfo] = vtc_validation_common( ...
        "load_observations", data);
    nativeSecondaryIndex = find([data.nativePaths.isMultipath], 1, "first");
    assert(~isempty(nativeSecondaryIndex), ...
        "Layer 2 event has no native confirmed secondary path.");
    nativePath = data.nativePaths(nativeSecondaryIndex);
    fprintf("Layer 2 event %s/%s center=%d loaded\n", ...
        data.sceneId, data.prnLabel, data.centerWindowId);

    for delay = contract.layer2.excess_delay_samples
        for doppler = contract.layer2.relative_doppler_hz
            for power = contract.layer2.relative_power_db
                for phase = contract.layer2.relative_phase_rad
                    trialOrdinal = trialOrdinal + 1;
                    row = emptyLayer2Row();
                    row.trial_id = string(sprintf("L2_%04d", trialOrdinal));
                    row.layer = "Layer2_MultipathStress";
                    row.scene_id = data.sceneId;
                    row.prn_label = data.prnLabel;
                    row.environment = data.environment;
                    row.center_window_id = data.centerWindowId;
                    row.source_interval_start_zero_based = min([readInfo.sample_start_zero_based]);
                    row.source_interval_end_zero_based = max([readInfo.sample_start_zero_based]) + 204600 - 1;
                    row.excess_delay_truth_samples = delay;
                    row.relative_doppler_truth_hz = doppler;
                    row.relative_power_truth_db = power;
                    row.phase_truth_rad = phase;
                    try
                        observations = vtc_validation_common( ...
                            "inject_observations", baseObservations, data, ...
                            delay, doppler, power, phase);
                        result = vtc_validation_common( ...
                            "estimate_joint", observations, data, estimator);
                        injectedMatch = vtc_validation_common( ...
                            "match_injected", result.selected, delay, doppler, power, tolerances);
                        nativePathMatch = vtc_validation_common( ...
                            "match_native", result.selected, nativePath, tolerances);
                        row.selected_order = result.selectedOrder;
                        row.joint_valid = result.jointValid;
                        row.injected_match = injectedMatch.found;
                        row.injected_delay_error_samples = injectedMatch.delayErrorSamples;
                        row.injected_doppler_error_hz = injectedMatch.dopplerErrorHz;
                        row.injected_power_error_db = injectedMatch.powerErrorDb;
                        row.injected_match_cost = injectedMatch.cost;
                        row.native_path_consistency = nativePathMatch.found ...
                            && abs(nativePathMatch.delayDriftSamples) <= tolerances.delay ...
                            && abs(nativePathMatch.dopplerDriftHz) <= tolerances.doppler ...
                            && abs(nativePathMatch.powerDriftDb) <= tolerances.power;
                        row.native_delay_drift_samples = nativePathMatch.delayDriftSamples;
                        row.native_doppler_drift_hz = nativePathMatch.dopplerDriftHz;
                        row.native_power_drift_db = nativePathMatch.powerDriftDb;
                        row.joint_rss = result.jointRss;
                        row.joint_bic = result.jointBic;
                        row.snapshot_wins = result.snapshotWins;
                        row.failure_reason = classifyFailure(result, injectedMatch, nativePathMatch);
                    catch exception
                        row.failure_reason = "MATLAB_ERROR: " + string(exception.message);
                    end
                    trialRows(end + 1, 1) = row; %#ok<AGROW>
                end
            end
        end
    end
end

trialTable = struct2table(trialRows);
writetable(trialTable, fullfile(outDir, "layer2_multipath_stress_trials.csv"));
summaryTable = makeLayer2Summary(trialTable);
writetable(summaryTable, fullfile(outDir, "layer2_multipath_stress_summary.csv"));
fprintf("Layer 2 wrote %d trials to %s\n", height(trialTable), outDir);
end


function row = emptyLayer2Row()
row = struct( ...
    "trial_id", "", "layer", "", "scene_id", "", "prn_label", "", ...
    "environment", "", "center_window_id", nan, ...
    "source_interval_start_zero_based", nan, ...
    "source_interval_end_zero_based", nan, ...
    "excess_delay_truth_samples", nan, ...
    "relative_doppler_truth_hz", nan, ...
    "relative_power_truth_db", nan, "phase_truth_rad", nan, ...
    "selected_order", nan, "joint_valid", false, ...
    "injected_match", false, "injected_delay_error_samples", nan, ...
    "injected_doppler_error_hz", nan, "injected_power_error_db", nan, ...
    "injected_match_cost", nan, "native_path_consistency", false, ...
    "native_delay_drift_samples", nan, "native_doppler_drift_hz", nan, ...
    "native_power_drift_db", nan, "joint_rss", nan, ...
    "joint_bic", nan, "snapshot_wins", nan, "failure_reason", "NOT_RUN");
end


function reason = classifyFailure(result, injectedMatch, nativeMatch)
if result.selectedOrder < 3
    reason = "NO_THREE_COMPONENT_MODEL_SELECTED";
elseif ~result.jointValid
    reason = "SELECTED_MODEL_INVALID";
elseif ~injectedMatch.found
    reason = "INJECTED_PATH_OUTSIDE_TOLERANCE";
elseif ~nativeMatch.found
    reason = "NO_NATIVE_PATH_MATCH";
else
    reason = "PASS";
end
reason = string(reason);
end


function summary = makeLayer2Summary(trials)
template = struct( ...
    "layer", "Layer2_MultipathStress", "scene_id", "", "prn_label", "", ...
    "environment", "", "relative_power_db", nan, "trial_count", nan, ...
    "recovery_count", nan, "recovery_rate", nan, ...
    "native_consistency_count", nan, "native_consistency_rate", nan, ...
    "median_abs_delay_error_samples", nan, ...
    "median_abs_doppler_error_hz", nan, ...
    "median_abs_power_error_db", nan);
summaryRows = repmat(template, 0, 1);
keys = unique(trials(:, {"scene_id", "prn_label", "environment", ...
    "relative_power_truth_db"}), "rows");
for index = 1:height(keys)
    subset = trials(strcmp(trials.scene_id, keys.scene_id(index)) ...
        & strcmp(trials.prn_label, keys.prn_label(index)) ...
        & strcmp(trials.environment, keys.environment(index)) ...
        & trials.relative_power_truth_db == keys.relative_power_truth_db(index), :);
    row = template;
    row.scene_id = string(keys.scene_id(index));
    row.prn_label = string(keys.prn_label(index));
    row.environment = string(keys.environment(index));
    row.relative_power_db = keys.relative_power_truth_db(index);
    row.trial_count = height(subset);
    row.recovery_count = nnz(subset.injected_match);
    row.recovery_rate = row.recovery_count / max(row.trial_count, 1);
    row.native_consistency_count = nnz(subset.native_path_consistency);
    row.native_consistency_rate = row.native_consistency_count / max(row.trial_count, 1);
    finite = isfinite(subset.injected_delay_error_samples) ...
        & isfinite(subset.injected_doppler_error_hz) ...
        & isfinite(subset.injected_power_error_db);
    if any(finite)
        row.median_abs_delay_error_samples = median(abs(subset.injected_delay_error_samples(finite)));
        row.median_abs_doppler_error_hz = median(abs(subset.injected_doppler_error_hz(finite)));
        row.median_abs_power_error_db = median(abs(subset.injected_power_error_db(finite)));
    end
    summaryRows(end + 1, 1) = row; %#ok<AGROW>
end
summary = struct2table(summaryRows);
end
