function export_layer3_native_model_support(contractPath)
%EXPORT_LAYER3_NATIVE_MODEL_SUPPORT Export stored native L=1/model evidence.
% This task reads existing Stage4 MAT/CSV artifacts only; it does not read
% raw IQ and does not rerun any SAGE stage.

if nargin < 1
    contractPath = fullfile(fileparts(fileparts(fileparts(fileparts(mfilename("fullpath"))))), ...
        "docs", "vtc2027_spring", "evidence", "validation_v1", ...
        "validation_contract.json");
end
contract = jsondecode(fileread(contractPath));
outDir = string(contract.output_namespace);
if ~isfolder(outDir)
    mkdir(outDir);
end

rows = repmat(emptyLayer3Row(), 0, 1);
for eventIndex = 1:numel(contract.layer2.events)
    caseJson = contract.layer2.events(eventIndex);
    sceneId = string(caseJson.scene_id);
    prnLabel = string(caseJson.prn_label);
    centerId = double(caseJson.center_window_id);
    root = projectRootFromContract(contract);
    outputDir = fullfile(root, "scenes", sceneId, ...
        "sage_results", "nav_sage_v2", prnLabel);
    matPath = vtc_validation_common("source_path", contract, prnLabel + "_stage4_mat");
    loaded = load(matPath, "jointFits");
    fits = loaded.jointFits;
    fit = [];
    for fitIndex = 1:numel(fits)
        if ~isempty(fits{fitIndex}) ...
                && double(fits{fitIndex}.centerWindowId) == centerId
            fit = fits{fitIndex};
            break;
        end
    end
    assert(~isempty(fit), "Stage4 MAT has no center %d: %s", centerId, matPath);
    selectedOrder = double(fit.selectedOrder);
    l1 = fit.models{1};
    selected = fit.models{selectedOrder};
    assert(numel(l1.snapshotRss) == 5 && numel(selected.snapshotRss) == 5, ...
        "Expected five snapshot RSS values at %s/%s/%d.", ...
        sceneId, prnLabel, centerId);

    summary = readtable(fullfile(outputDir, "stage4_joint_summary.csv"));
    summaryRow = summary(summary.center_window_id == centerId, :);
    assert(height(summaryRow) == 1, "Missing Stage4 summary row for %d.", centerId);
    assert(double(summaryRow.joint_selected_L) == selectedOrder, ...
        "Selected-order mismatch for %s/%s/%d.", sceneId, prnLabel, centerId);

    row = emptyLayer3Row();
    row.scene_id = sceneId;
    row.prn_label = prnLabel;
    row.environment = string(caseJson.environment);
    row.center_window_id = centerId;
    row.selected_order = selectedOrder;
    row.l1_valid = l1.valid;
    row.selected_valid = selected.valid;
    row.l1_rss = l1.rss;
    row.selected_rss = selected.rss;
    row.rss_reduction_percent = 100 * (l1.rss - selected.rss) / max(l1.rss, eps);
    row.l1_bic = l1.bic;
    row.selected_bic = selected.bic;
    row.delta_bic = l1.bic - selected.bic;
    row.l1_snapshot_wins = l1.snapshotWins;
    row.selected_snapshot_wins = selected.snapshotWins;
    for snapshot = 1:5
        row.(sprintf("l1_snapshot_rss_%d", snapshot)) = l1.snapshotRss(snapshot);
        row.(sprintf("selected_snapshot_rss_%d", snapshot)) = selected.snapshotRss(snapshot);
    end
    rows(end + 1, 1) = row; %#ok<AGROW>
end

tableOut = struct2table(rows);
writetable(tableOut, fullfile(outDir, "layer3_native_model_support.csv"));
fprintf("Layer 3 wrote %d native event rows to %s\n", height(tableOut), outDir);
end


function row = emptyLayer3Row()
row = struct( ...
    "scene_id", "", "prn_label", "", "environment", "", ...
    "center_window_id", nan, "selected_order", nan, ...
    "l1_valid", false, "selected_valid", false, ...
    "l1_rss", nan, "selected_rss", nan, "rss_reduction_percent", nan, ...
    "l1_bic", nan, "selected_bic", nan, "delta_bic", nan, ...
    "l1_snapshot_wins", nan, "selected_snapshot_wins", nan, ...
    "l1_snapshot_rss_1", nan, "l1_snapshot_rss_2", nan, ...
    "l1_snapshot_rss_3", nan, "l1_snapshot_rss_4", nan, ...
    "l1_snapshot_rss_5", nan, "selected_snapshot_rss_1", nan, ...
    "selected_snapshot_rss_2", nan, "selected_snapshot_rss_3", nan, ...
    "selected_snapshot_rss_4", nan, "selected_snapshot_rss_5", nan);
end


function root = projectRootFromContract(contract)
root = string(contract.output_namespace);
for index = 1:4
    root = fileparts(root);
end
end
