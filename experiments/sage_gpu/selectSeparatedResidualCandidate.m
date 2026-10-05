function [candidate, trace] = selectSeparatedResidualCandidate( ...
    delays, dopplers, metric, existingDelays, minimumSeparation)
% Experimental copy of frozen initializeResidualPath candidate rejection.
% Keep candidate selection, tie removal, and exhaustion behavior aligned with
% scripts/sage_pipeline/run_nav_sage_pipeline.m; do not tune this helper.

delays = double(delays(:));
dopplers = double(dopplers(:).');
metric = double(metric);
existingDelays = double(existingDelays(:).');
assert(isequal(size(metric), [numel(delays), numel(dopplers)]), ...
    "Residual metric dimensions do not match the candidate grids.");

trace = struct( ...
    "candidate_rank", {}, ...
    "candidate_delay", {}, ...
    "candidate_doppler", {}, ...
    "candidate_score", {}, ...
    "min_separation_to_existing_paths", {}, ...
    "accepted", {}, ...
    "rejection_reason", {});
candidateRank = 1;

for attempt = 1:numel(metric)
    currentMaximum = max(metric(:));
    [score, linearIndex] = max(metric(:));
    [delayIndex, dopplerIndex] = ind2sub(size(metric), linearIndex);
    delay = delays(delayIndex);
    doppler = dopplers(dopplerIndex);
    separation = abs(delay - existingDelays);
    minimumObservedSeparation = min(separation);
    accepted = all(separation >= minimumSeparation);

    if accepted
        reason = "ACCEPTED";
    else
        reason = "REJECT_SEPARATION";
    end
    trace(end + 1) = struct( ... %#ok<AGROW>
        "candidate_rank", candidateRank, ...
        "candidate_delay", delay, ...
        "candidate_doppler", doppler, ...
        "candidate_score", score, ...
        "min_separation_to_existing_paths", minimumObservedSeparation, ...
        "accepted", accepted, ...
        "rejection_reason", reason);

    if accepted
        candidate = struct( ...
            "delaySamples", delay, ...
            "dopplerHz", doppler, ...
            "score", score);
        return;
    end

    tiedMaximum = metric == currentMaximum;
    metric(tiedMaximum) = -inf;
    candidateRank = candidateRank + nnz(tiedMaximum);
end

error("No separated residual path could be initialized.");
end
