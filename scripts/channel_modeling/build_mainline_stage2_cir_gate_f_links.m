function result = build_mainline_stage2_cir_gate_f_links( ...
    stage2Ledger, alphaLedger, cirWindowFeatures)
%BUILD_MAINLINE_STAGE2_CIR_GATE_F_LINKS Exact, lossless Stage2 linkage.
% Stage2 rows are the left side of every linkage. A missing alpha or CIR
% feature is retained as an explicit status rather than dropping the row.

requiredStage2 = {'run_id', 'scene_id', 'prn', 'tracking_channel', ...
    'window_id', 'path_id', 'is_multipath', 'relative_power_db'};
requiredAlpha = {'run_id', 'scene_id', 'prn', 'tracking_channel', ...
    'window_id', 'path_id', 'alpha_real', ...
    'alpha_imag', 'alpha_magnitude', 'alpha_phase_rad', 'alpha_status'};
assert(istable(stage2Ledger) && all(ismember(requiredStage2, ...
    stage2Ledger.Properties.VariableNames)), ...
    'GNSS:SAGE:GateFStage2SchemaMismatch', ...
    'Stage2 ledger lacks required exact path identity or MPC fields.');
assert(istable(alphaLedger) && all(ismember(requiredAlpha, ...
    alphaLedger.Properties.VariableNames)), ...
    'GNSS:SAGE:GateFAlphaSchemaMismatch', ...
    'WP5 alpha ledger lacks required exact path identity fields.');
assert(istable(cirWindowFeatures) && all(ismember( ...
    {'run_id', 'window_id', 'cir_link_status'}, ...
    cirWindowFeatures.Properties.VariableNames)), ...
    'GNSS:SAGE:GateFCirFeatureSchemaMismatch', ...
    'CIR feature table lacks exact run/window identity or link status.');

stage2Key = pathIdentityKey(stage2Ledger.run_id, ...
    stage2Ledger.window_id, stage2Ledger.path_id);
alphaKey = pathIdentityKey(alphaLedger.run_id, ...
    alphaLedger.window_id, alphaLedger.path_id);
featureKey = windowIdentityKey(cirWindowFeatures.run_id, ...
    cirWindowFeatures.window_id);
assert(numel(unique(stage2Key)) == numel(stage2Key), ...
    'GNSS:SAGE:GateFStage2IdentityDuplicate', ...
    'Stage2 (run_id, window_id, path_id) identities are not unique.');
assert(numel(unique(alphaKey)) == numel(alphaKey), ...
    'GNSS:SAGE:GateFAlphaIdentityDuplicate', ...
    'WP5 alpha (run_id, window_id, path_id) identities are not unique.');
assert(numel(unique(featureKey)) == numel(featureKey), ...
    'GNSS:SAGE:GateFCirIdentityDuplicate', ...
    'CIR (run_id, window_id) feature identities are not unique.');

isMpc = numericColumn(stage2Ledger.is_multipath) == 1;
assert(all(ismember(numericColumn(stage2Ledger.is_multipath), [0, 1])), ...
    'GNSS:SAGE:GateFStage2MpcFlagInvalid', ...
    'Stage2 is_multipath must be binary.');
% One direct reference per selected Stage2 window defines relative power.
stage2WindowKey = windowIdentityKey(stage2Ledger.run_id, ...
    stage2Ledger.window_id);
[uniqueWindowKey, ~, windowGroup] = unique(stage2WindowKey, 'stable');
firstRows = accumarray(windowGroup, (1:height(stage2Ledger)).', [], @min);
pathCounts = accumarray(windowGroup, 1);
mpcCounts = accumarray(windowGroup, double(isMpc));
directCounts = accumarray(windowGroup, double(~isMpc));
assert(all(directCounts == 1), ...
    'GNSS:SAGE:GateFDirectReferenceInvalid', ...
    'Every Stage2-selected window must have exactly one direct reference path.');

[hasAlpha, alphaRow] = ismember(stage2Key, alphaKey);
[hasFeature, featureRow] = ismember(uniqueWindowKey, featureKey);
matchedPaths = find(hasAlpha);
alphaRows = alphaRow(hasAlpha);
assert(all(string(stage2Ledger.scene_id(matchedPaths)) == ...
    string(alphaLedger.scene_id(alphaRows))) ...
    && all(string(stage2Ledger.prn(matchedPaths)) == ...
    string(alphaLedger.prn(alphaRows))) ...
    && all(numericColumn(stage2Ledger.tracking_channel(matchedPaths)) == ...
    numericColumn(alphaLedger.tracking_channel(alphaRows))), ...
    'GNSS:SAGE:GateFPathIdentityMismatch', ...
    'Matched alpha paths disagree in scene, PRN, or tracking channel.');

% Validate numeric path attributes and complex alpha without changing either
% source table. Alpha-only rows remain separately counted below.
alphaReal = nan(height(stage2Ledger), 1);
alphaImag = nan(height(stage2Ledger), 1);
alphaMagnitude = nan(height(stage2Ledger), 1);
alphaPhase = nan(height(stage2Ledger), 1);
alphaStatus = repmat("NO_ALPHA_RECORD", height(stage2Ledger), 1);
relativePowerSourceStatus = repmat("NO_ALPHA_RECORD", ...
    height(stage2Ledger), 1);
if any(hasAlpha)
    rows = find(hasAlpha);
    sourceRows = alphaRow(rows);
    alphaReal(rows) = numericColumn(alphaLedger.alpha_real(sourceRows));
    alphaImag(rows) = numericColumn(alphaLedger.alpha_imag(sourceRows));
    alphaMagnitude(rows) = numericColumn( ...
        alphaLedger.alpha_magnitude(sourceRows));
    alphaPhase(rows) = numericColumn(alphaLedger.alpha_phase_rad(sourceRows));
    alphaStatus(rows) = string(alphaLedger.alpha_status(sourceRows));
    if ismember('relative_power_check_status', ...
            alphaLedger.Properties.VariableNames)
        relativePowerSourceStatus(rows) = string( ...
            alphaLedger.relative_power_check_status(sourceRows));
    else
        relativePowerSourceStatus(rows) = "NOT_RECORDED";
    end
end

isAvailable = hasAlpha & alphaStatus == "AVAILABLE";
assert(all(isfinite(alphaReal(isAvailable))) ...
    && all(isfinite(alphaImag(isAvailable))) ...
    && all(isfinite(alphaMagnitude(isAvailable))) ...
    && all(isfinite(alphaPhase(isAvailable))), ...
    'GNSS:SAGE:GateFAlphaNonfinite', ...
    'An alpha row marked AVAILABLE contains nonfinite components.');
calculatedMagnitude = hypot(alphaReal(isAvailable), alphaImag(isAvailable));
assert(all(abs(calculatedMagnitude - alphaMagnitude(isAvailable)) ...
    <= 1e-10 .* max(1, calculatedMagnitude)), ...
    'GNSS:SAGE:GateFAlphaMagnitudeMismatch', ...
    'Stored alpha magnitude does not equal hypot(real, imag).');
calculatedPhase = angle(complex(alphaReal(isAvailable), alphaImag(isAvailable)));
phaseDifference = angle(exp(1i .* ...
    (alphaPhase(isAvailable) - calculatedPhase)));
assert(all(abs(phaseDifference) <= 1e-10), ...
    'GNSS:SAGE:GateFAlphaPhaseMismatch', ...
    'Stored alpha phase does not equal angle(real + j*imag), modulo 2*pi.');

attributeMaxDifference = struct('relative_power_db', 0, ...
    'delay_samples', 0, 'excess_delay_samples', 0, ...
    'doppler_offset_hz', 0);
for field = {'relative_power_db', 'delay_samples', ...
        'excess_delay_samples', 'doppler_offset_hz'}
    name = field{1};
    if ismember(name, stage2Ledger.Properties.VariableNames) ...
            && ismember(name, alphaLedger.Properties.VariableNames) ...
            && any(hasAlpha)
        stageFieldValues = stage2Ledger.(name);
        alphaFieldValues = alphaLedger.(name);
        stageValues = numericColumn(stageFieldValues(hasAlpha));
        alphaValues = numericColumn(alphaFieldValues(alphaRow(hasAlpha)));
        finite = isfinite(stageValues) & isfinite(alphaValues);
        if any(finite)
            attributeMaxDifference.(name) = max(abs( ...
                stageValues(finite) - alphaValues(finite)));
        end
        assert(all(finite) && all(abs(stageValues - alphaValues) <= 1e-10), ...
            'GNSS:SAGE:GateFPathAttributeMismatch', ...
            'Stage2 and alpha attribute %s differ for a matched path.', name);
    end
end

powerCheckStatus = repmat("NOT_CHECKED_ALPHA_MISSING", ...
    height(stage2Ledger), 1);
recomputedRelativePower = nan(height(stage2Ledger), 1);
for k = 1:numel(uniqueWindowKey)
    rows = find(windowGroup == k);
    directRow = rows(~isMpc(rows));
    if ~isAvailable(directRow)
        powerCheckStatus(rows) = "NOT_CHECKED_REFERENCE_ALPHA_MISSING";
        continue;
    end
    for row = rows.'
        if ~isAvailable(row)
            continue;
        end
        ratioDb = 10 * log10(max(alphaMagnitude(row)^2, realmin) ...
            / max(alphaMagnitude(directRow)^2, realmin));
        recomputedRelativePower(row) = ratioDb;
        observedDb = numericColumn(stage2Ledger.relative_power_db(row));
        if isfinite(observedDb) && abs(ratioDb - observedDb) <= 1e-6
            powerCheckStatus(row) = "PASS";
        elseif isfinite(observedDb)
            powerCheckStatus(row) = "MISMATCH";
        else
            powerCheckStatus(row) = "NOT_CHECKED_RELATIVE_POWER_INVALID";
        end
    end
end

pathLinkage = stage2Ledger;
pathLinkage.sage_alpha_real = alphaReal;
pathLinkage.sage_alpha_imag = alphaImag;
pathLinkage.sage_alpha_magnitude = alphaMagnitude;
pathLinkage.sage_alpha_phase_rad = alphaPhase;
pathLinkage.sage_alpha_status = alphaStatus;
pathLinkage.alpha_source_relative_power_status = relativePowerSourceStatus;
pathLinkage.relative_power_recomputed_db = recomputedRelativePower;
pathLinkage.relative_power_recomputed_status = powerCheckStatus;
pathLinkage.alpha_link_status = repmat("MATCHED", height(stage2Ledger), 1);
pathLinkage.alpha_link_status(~hasAlpha) = "NO_ALPHA_RECORD";

windowTable = stage2Ledger(firstRows, intersect( ...
    {'run_id', 'scene_id', 'prn', 'tracking_channel', 'window_id', ...
    'recording_time_s'}, stage2Ledger.Properties.VariableNames, 'stable'));
windowTable.stage2_path_count = pathCounts;
windowTable.stage2_mpc_count = mpcCounts;
windowTable.stage2_direct_reference_count = directCounts;
windowTable.cir_link_status = repmat("NO_CIR_FEATURE", ...
    numel(uniqueWindowKey), 1);

featureNames = setdiff(cirWindowFeatures.Properties.VariableNames, ...
    {'run_id', 'window_id', 'cir_link_status'}, 'stable');
for k = 1:numel(featureNames)
    name = featureNames{k};
    source = cirWindowFeatures.(name);
    if isnumeric(source)
        aligned = nan(numel(uniqueWindowKey), 1);
    elseif islogical(source)
        aligned = false(numel(uniqueWindowKey), 1);
    else
        aligned = repmat("NOT_AVAILABLE", numel(uniqueWindowKey), 1);
    end
    aligned(hasFeature) = source(featureRow(hasFeature));
    windowTable.(name) = aligned;
end
windowTable.cir_link_status(hasFeature) = string( ...
    cirWindowFeatures.cir_link_status(featureRow(hasFeature)));

% Repeat only window-level feature references on the MPC path join. The
% separate 7,847-row window table remains the canonical feature table.
[hasMpcWindowFeature, mpcWindowFeatureRow] = ismember( ...
    stage2WindowKey(isMpc), featureKey);
mpcLinkage = pathLinkage(isMpc, :);
mpcLinkage.cir_link_status = repmat("NO_CIR_FEATURE", height(mpcLinkage), 1);
mpcLinkage.cir_link_status(hasMpcWindowFeature) = string( ...
    cirWindowFeatures.cir_link_status( ...
    mpcWindowFeatureRow(hasMpcWindowFeature)));
mpcWindowRows = find(isMpc);
for k = 1:numel(featureNames)
    name = featureNames{k};
    source = cirWindowFeatures.(name);
    if isnumeric(source)
        aligned = nan(height(mpcLinkage), 1);
    elseif islogical(source)
        aligned = false(height(mpcLinkage), 1);
    else
        aligned = repmat("NOT_AVAILABLE", height(mpcLinkage), 1);
    end
    aligned(hasMpcWindowFeature) = source( ...
        mpcWindowFeatureRow(hasMpcWindowFeature));
    mpcLinkage.(['cir_', name]) = aligned;
end
% Keep the explicit Stage2 path order; mpcWindowRows is retained to make
% this selection visibly dependent on the source ledger, not a sorted join.
assert(height(mpcLinkage) == numel(mpcWindowRows), ...
    'GNSS:SAGE:GateFInternalRowLoss', ...
    'MPC linkage unexpectedly changed the Stage2 row count.');

result = struct();
result.stage2_window_features = windowTable;
result.stage2_all_path_linkage = pathLinkage;
result.stage2_mpc_linkage = mpcLinkage;
result.alpha_unmatched_keys = alphaKey(~ismember(alphaKey, stage2Key));
result.counts.stage2_path_rows = height(stage2Ledger);
result.counts.stage2_window_count = numel(uniqueWindowKey);
result.counts.stage2_mpc_rows = sum(isMpc);
result.counts.alpha_matched_path_rows = sum(hasAlpha);
result.counts.alpha_missing_path_rows = sum(~hasAlpha);
result.counts.alpha_unavailable_path_rows = sum(~isAvailable);
result.counts.alpha_missing_mpc_rows = sum(isMpc & ~isAvailable);
result.counts.alpha_extra_rows = numel(result.alpha_unmatched_keys);
result.counts.unmatched_stage2_windows = sum(~hasFeature);
result.counts.unmatched_mpc_windows = sum(~hasMpcWindowFeature);
result.counts.relative_power_recomputed_pass = sum( ...
    isMpc & powerCheckStatus == "PASS");
result.counts.relative_power_recomputed_mismatch = sum( ...
    isMpc & powerCheckStatus == "MISMATCH");
result.counts.relative_power_recomputed_pass_all_rows = sum( ...
    powerCheckStatus == "PASS");
result.counts.relative_power_recomputed_mismatch_all_rows = sum( ...
    powerCheckStatus == "MISMATCH");
result.counts.direct_reference_relative_power_mismatch = sum( ...
    ~isMpc & powerCheckStatus == "MISMATCH");
result.counts.alpha_math_checked_paths = sum(isAvailable);
result.max_abs_path_attribute_difference = attributeMaxDifference;
end

function key = pathIdentityKey(runId, windowId, pathId)
runId = string(runId(:));
windowId = numericColumn(windowId(:));
pathId = numericColumn(pathId(:));
key = runId + "|" + string(windowId) + "|" + string(pathId);
end

function key = windowIdentityKey(runId, windowId)
runId = string(runId(:));
windowId = numericColumn(windowId(:));
key = runId + "|" + string(windowId);
end

function values = numericColumn(values)
if iscell(values)
    values = string(values);
end
if isstring(values) || ischar(values) || iscategorical(values)
    values = str2double(string(values));
end
values = double(values(:));
end
