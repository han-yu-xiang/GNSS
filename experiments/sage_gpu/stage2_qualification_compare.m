function result = stage2_qualification_compare(cpuScratchFile, gpuResultFile, resultJsonFile)
cpuState = load(cpuScratchFile, "cpuFit", "result");
gpuState = load(gpuResultFile, "gpuFitCpu", "result");
cpuFit = cpuState.cpuFit;
gpuFit = gpuState.gpuFitCpu;
result = compareQualificationStructure(cpuFit, gpuFit);
result.qualification_id = string(cpuState.result.qualification_id);
result.scene_id = string(cpuState.result.scene_id);
result.prn = string(cpuState.result.prn);
result.tracking_channel = double(cpuState.result.tracking_channel);
result.window_id = double(cpuFit.windowId);
result.recording_time_s = double(cpuFit.recordingTimeS);
result.cpu_selected_L = double(cpuFit.selectedOrder);
result.gpu_selected_L = double(gpuFit.selectedOrder);
result.cpu_path_count = numel(cpuFit.models{cpuFit.selectedOrder}.paths);
result.gpu_path_count = numel(gpuFit.models{gpuFit.selectedOrder}.paths);
result.cpu_stage2_time = double(cpuState.result.cpu_compute_seconds);
result.gpu_first_stage2_time = double(gpuState.result.gpu_first_run_compute_seconds);
result.gpu_warm_stage2_time = double(gpuState.result.gpu_warm_run_compute_seconds);
result.gpu_transfer_in_time = double(gpuState.result.gpu_transfer_in_seconds);
result.gpu_transfer_out_time = double(gpuState.result.gpu_transfer_out_seconds);
result.compute_speedup = result.cpu_stage2_time / max(result.gpu_warm_stage2_time, eps);
result.gpu_end_to_end_warm_speedup = double(gpuState.result.warm_end_to_end_speedup);
result.gpu_end_to_end_cold_speedup = double(gpuState.result.cold_end_to_end_speedup);
result.gpu_name = string(gpuState.result.gpu_name);
result.cpu_model_validity_by_order = cellfun( ...
    @(model) logical(model.valid), cpuFit.models);
result.gpu_model_validity_by_order = cellfun( ...
    @(model) logical(model.valid), gpuFit.models);
result.gpu_seed_trace_by_order = gpuFit.seedTraceByOrder;
result.separation_retry_status = classifySeparationRetry(gpuFit);
if result.selected_L_match && result.path_count_match ...
        && result.path_identity_match && result.path_label_match ...
        && result.model_validity_match
    result.gpu_structural_equivalence = "PASS";
else
    result.gpu_structural_equivalence = "FAIL";
end
fid = fopen(resultJsonFile, 'w');
assert(fid >= 0, "Unable to create qualification comparison JSON.");
fwrite(fid, jsonencode(result), 'char');
fclose(fid);
end

function result = compareQualificationStructure(referenceFit, candidateFit)
selectedLMatch = referenceFit.selectedOrder == candidateFit.selectedOrder;
validityMatch = numel(referenceFit.models) == numel(candidateFit.models);
pathCountsMatch = validityMatch;
pathOrdersMatch = validityMatch;
pathLabelsMatch = validityMatch;
refRss = nan(1, numel(referenceFit.models));
candidateRss = nan(1, numel(candidateFit.models));
refBic = nan(1, numel(referenceFit.models));
candidateBic = nan(1, numel(candidateFit.models));
for order = 1:min(numel(referenceFit.models), numel(candidateFit.models))
    a = referenceFit.models{order};
    b = candidateFit.models{order};
    validityMatch = validityMatch && logical(a.valid) == logical(b.valid);
    refRss(order) = double(a.rss);
    candidateRss(order) = double(b.rss);
    refBic(order) = double(a.bic);
    candidateBic(order) = double(b.bic);
    pa = a.paths;
    pb = b.paths;
    pathCountsMatch = pathCountsMatch && numel(pa) == numel(pb);
    if numel(pa) ~= numel(pb)
        pathOrdersMatch = false;
        pathLabelsMatch = false;
        continue;
    end
    labelsA = false(1, numel(pa));
    labelsB = false(1, numel(pb));
    if numel(pa) > 1
        labelsA(2:end) = true;
        labelsB(2:end) = true;
    end
    pathLabelsMatch = pathLabelsMatch && isequal(labelsA, labelsB);
    if numel(pa) > 1
        da = [pa.delaySamples];
        db = [pb.delaySamples];
        pathOrdersMatch = pathOrdersMatch && isequal( ...
            sign(da(:) - da(:).'), sign(db(:) - db(:).'));
    end
end
a = referenceFit.models{referenceFit.selectedOrder};
b = candidateFit.models{candidateFit.selectedOrder};
selectedCountMatch = numel(a.paths) == numel(b.paths);
if selectedCountMatch
    da = [a.paths.delaySamples];
    db = [b.paths.delaySamples];
    selectedOrderMatch = isequal(sign(da(:) - da(:).'), sign(db(:) - db(:).'));
    labelsA = false(1, numel(a.paths));
    labelsB = false(1, numel(b.paths));
    if numel(a.paths) > 1
        labelsA(2:end) = true;
        labelsB(2:end) = true;
    end
    selectedLabelsMatch = isequal(labelsA, labelsB);
else
    selectedOrderMatch = false;
    selectedLabelsMatch = false;
end
[delayAbs, ~] = qualificationDifference([a.paths.delaySamples], [b.paths.delaySamples]);
[dopplerAbs, ~] = qualificationDifference([a.paths.dopplerHz], [b.paths.dopplerHz]);
[powerAbs, ~] = qualificationDifference(a.relativePowerDb, b.relativePowerDb);
[alphaAbs, ~] = qualificationDifference([a.paths.alpha], [b.paths.alpha]);
[scoreAbs, ~] = qualificationDifference([a.paths.score], [b.paths.score]);
[rssAbs, rssRel] = qualificationDifference(refRss, candidateRss);
[bicAbs, bicRel] = qualificationDifference(refBic, candidateBic);
[cpuBestL, cpuSecondBestL, cpuMargin] = qualificationBicMargin(referenceFit);
[gpuBestL, gpuSecondBestL, gpuMargin] = qualificationBicMargin(candidateFit);
result = struct();
result.selected_L_match = logical(selectedLMatch);
result.path_count_match = logical(selectedCountMatch);
result.path_identity_match = logical(selectedOrderMatch && pathOrdersMatch && pathCountsMatch);
result.path_label_match = logical(selectedLabelsMatch && pathLabelsMatch);
result.model_validity_match = logical(validityMatch);
result.max_delay_abs_diff = delayAbs;
result.max_doppler_abs_diff = dopplerAbs;
result.max_relative_power_abs_diff = powerAbs;
result.max_alpha_abs_diff = alphaAbs;
result.max_path_score_abs_diff = scoreAbs;
result.max_rss_abs_diff = rssAbs;
result.max_rss_rel_diff = rssRel;
result.max_bic_abs_diff = bicAbs;
result.max_bic_rel_diff = bicRel;
result.cpu_best_l = cpuBestL;
result.cpu_second_best_l = cpuSecondBestL;
result.cpu_bic_margin = cpuMargin;
result.gpu_best_l = gpuBestL;
result.gpu_second_best_l = gpuSecondBestL;
result.gpu_bic_margin = gpuMargin;
end

function [maxAbsolute, maxRelative] = qualificationDifference(reference, candidate)
reference = double(reference(:));
candidate = double(candidate(:));
if numel(reference) ~= numel(candidate)
    maxAbsolute = inf;
    maxRelative = inf;
    return;
end
if isempty(reference)
    maxAbsolute = 0;
    maxRelative = 0;
    return;
end
delta = abs(candidate - reference);
samePositiveInfinity = isinf(reference) & reference > 0 ...
    & isinf(candidate) & candidate > 0;
sameNegativeInfinity = isinf(reference) & reference < 0 ...
    & isinf(candidate) & candidate < 0;
sameNaN = isnan(reference) & isnan(candidate);
delta(samePositiveInfinity | sameNegativeInfinity | sameNaN) = 0;
delta(isnan(delta)) = inf;
maxAbsolute = max(delta);
denominator = abs(reference);
relative = zeros(size(delta));
nonzero = denominator > 0;
relative(nonzero) = delta(nonzero) ./ denominator(nonzero);
relative(~nonzero & delta ~= 0) = inf;
maxRelative = max(relative);
end

function [bestL, secondBestL, margin] = qualificationBicMargin(fit)
valid = false(1, numel(fit.models));
bic = inf(1, numel(fit.models));
for order = 1:numel(fit.models)
    valid(order) = logical(fit.models{order}.valid) ...
        && isfinite(fit.models{order}.bic);
    bic(order) = double(fit.models{order}.bic);
end
orders = find(valid);
if isempty(orders)
    bestL = nan;
    secondBestL = nan;
    margin = nan;
    return;
end
[~, sortIndex] = sortrows([bic(orders).', orders.'], [1 2]);
orders = orders(sortIndex);
bestL = orders(1);
if numel(orders) < 2
    secondBestL = nan;
    margin = nan;
else
    secondBestL = orders(2);
    margin = bic(secondBestL) - bic(bestL);
end
end
function status = classifySeparationRetry(fit)
if ~isfield(fit, "seedTraceByOrder") || isempty(fit.seedTraceByOrder)
    status = "UNKNOWN";
    return;
end
traces = fit.seedTraceByOrder;
traceSeen = false;
incomplete = false;
triggered = false;
for order = 2:numel(fit.models)
    if order > numel(traces) || isempty(traces{order})
        incomplete = true;
        continue;
    end
    traceSeen = true;
    accepted = [traces{order}.accepted];
    triggered = triggered || any(~accepted);
end
if triggered
    status = "TRIGGERED";
elseif traceSeen && ~incomplete
    status = "NOT_TRIGGERED";
else
    status = "UNKNOWN";
end
end
