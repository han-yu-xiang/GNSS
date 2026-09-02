function run_layer1_controlled_recovery(contractPath)
%RUN_LAYER1_CONTROLLED_RECOVERY Execute the frozen G18 controlled layer.
% This is validation-only code. It never calls the production wrapper or
% writes under scenes/**/sage_results.

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
trialRows = repmat(emptyLayer1Row(), 0, 1);
trialOrdinal = 0;

for caseIndex = 1:numel(contract.layer1.cases)
    caseJson = contract.layer1.cases(caseIndex);
    data = vtc_validation_common("prepare_case", contract, caseJson);
    [baseObservations, readInfo] = vtc_validation_common( ...
        "load_observations", data);
    fprintf("Layer 1 case %s/%s center=%d loaded\n", ...
        data.sceneId, data.prnLabel, data.centerWindowId);

    for delay = contract.layer1.excess_delay_samples
        for doppler = contract.layer1.relative_doppler_hz
            for power = contract.layer1.relative_power_db
                for phase = contract.layer1.relative_phase_rad
                    trialOrdinal = trialOrdinal + 1;
                    row = emptyLayer1Row();
                    row.trial_id = string(sprintf("L1_%04d", trialOrdinal));
                    row.layer = "Layer1_Controlled";
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
                        match = vtc_validation_common( ...
                            "match_injected", result.selected, delay, doppler, power, tolerances);
                        row.selected_order = result.selectedOrder;
                        row.joint_valid = result.jointValid;
                        row.injected_match = match.found;
                        row.delay_error_samples = match.delayErrorSamples;
                        row.doppler_error_hz = match.dopplerErrorHz;
                        row.power_error_db = match.powerErrorDb;
                        row.match_cost = match.cost;
                        row.joint_rss = result.jointRss;
                        row.joint_bic = result.jointBic;
                        row.snapshot_wins = result.snapshotWins;
                        row.failure_reason = classifyFailure(result, match);
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
writetable(trialTable, fullfile(outDir, "layer1_controlled_trials.csv"));
summaryTable = makeLayer1Summary(trialTable, contract.layer1.relative_power_db);
writetable(summaryTable, fullfile(outDir, "layer1_controlled_summary.csv"));
fprintf("Layer 1 wrote %d trials to %s\n", height(trialTable), outDir);
end


function row = emptyLayer1Row()
row = struct( ...
    "trial_id", "", "layer", "", "scene_id", "", "prn_label", "", ...
    "environment", "", "center_window_id", nan, ...
    "source_interval_start_zero_based", nan, ...
    "source_interval_end_zero_based", nan, ...
    "excess_delay_truth_samples", nan, ...
    "relative_doppler_truth_hz", nan, ...
    "relative_power_truth_db", nan, "phase_truth_rad", nan, ...
    "selected_order", nan, "joint_valid", false, ...
    "injected_match", false, "delay_error_samples", nan, ...
    "doppler_error_hz", nan, "power_error_db", nan, ...
    "match_cost", nan, "joint_rss", nan, "joint_bic", nan, ...
    "snapshot_wins", nan, "failure_reason", "NOT_RUN");
end


function reason = classifyFailure(result, match)
if result.selectedOrder < 2
    reason = "NO_SECONDARY_MODEL_SELECTED";
elseif ~result.jointValid
    reason = "SELECTED_MODEL_INVALID";
elseif ~match.found
    reason = "INJECTED_PATH_OUTSIDE_TOLERANCE";
else
    reason = "PASS";
end
reason = string(reason);
end


function summary = makeLayer1Summary(trials, powers)
template = struct( ...
    "layer", "Layer1_Controlled", "relative_power_db", nan, ...
    "trial_count", nan, "recovery_count", nan, "recovery_rate", nan, ...
    "median_abs_delay_error_samples", nan, ...
    "median_abs_doppler_error_hz", nan, ...
    "median_abs_power_error_db", nan, "finite_error_count", nan);
summaryRows = repmat(template, 0, 1);
for power = powers
    subset = trials(trials.relative_power_truth_db == power, :);
    pass = subset.injected_match == 1;
    finite = isfinite(subset.delay_error_samples) ...
        & isfinite(subset.doppler_error_hz) ...
        & isfinite(subset.power_error_db);
    row = template;
    row.layer = "Layer1_Controlled";
    row.relative_power_db = power;
    row.trial_count = height(subset);
    row.recovery_count = nnz(pass);
    row.recovery_rate = nnz(pass) / max(height(subset), 1);
    if any(finite)
        row.median_abs_delay_error_samples = median(abs(subset.delay_error_samples(finite)));
        row.median_abs_doppler_error_hz = median(abs(subset.doppler_error_hz(finite)));
        row.median_abs_power_error_db = median(abs(subset.power_error_db(finite)));
    end
    row.finite_error_count = nnz(finite);
    summaryRows(end + 1, 1) = row; %#ok<AGROW>
end
summary = struct2table(summaryRows);
end
