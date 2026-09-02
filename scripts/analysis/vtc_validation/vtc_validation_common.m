function varargout = vtc_validation_common(action, varargin)
%VTC_VALIDATION_COMMON Shared signal, injection, and local-joint-estimation code.
% This file is deliberately separate from the frozen production pipeline.

switch string(action)
    case "prepare_case"
        varargout{1} = prepareCase(varargin{1}, varargin{2});
    case "load_observations"
        [varargout{1}, varargout{2}] = loadObservations(varargin{1});
    case "inject_observations"
        varargout{1} = injectObservations(varargin{:});
    case "estimate_joint"
        varargout{1} = estimateJoint(varargin{:});
    case "match_injected"
        varargout{1} = matchInjected(varargin{:});
    case "match_native"
        varargout{1} = matchNative(varargin{:});
    case "source_path"
        varargout{1} = sourcePath(varargin{:});
    case "estimator"
        varargout{1} = estimatorFromContract(varargin{1});
    case "tolerances"
        varargout{1} = tolerancesFromContract(varargin{1});
    case "solve_amplitudes"
        varargout{1} = solveAmplitudesExternal(varargin{:});
    case "cancel_secondary"
        varargout{1} = cancelSecondary(varargin{:});
    case "dll_zero_crossing"
        [varargout{1}, varargout{2}, varargout{3}] = dllZeroCrossing(varargin{:});
    otherwise
        error("Unknown VTC validation action: %s", action);
end
end


function data = prepareCase(contract, caseJson)
data = struct();
data.sceneId = string(caseJson.scene_id);
data.prnLabel = string(caseJson.prn_label);
data.prn = double(caseJson.prn);
data.environment = string(caseJson.environment);
data.centerWindowId = double(caseJson.center_window_id);
data.outputDir = fullfile(projectRootFromContract(contract), "scenes", ...
    data.sceneId, "sage_results", "nav_sage_v2", data.prnLabel);
data.rawFile = sourcePath(contract, data.prnLabel + "_raw_iq");
data.stage0Windows = readtable(fullfile(data.outputDir, ...
    "stage0_valid_40ms_windows.csv"));
data.stage0Symbols = readtable(fullfile(data.outputDir, ...
    "stage0_valid_symbols.csv"));
centerRows = data.stage0Windows( ...
    data.stage0Windows.window_id == data.centerWindowId, :);
assert(height(centerRows) == 1, ...
    "Expected one Stage0 row for center window %d.", data.centerWindowId);
data.centerWindow = centerRows(1, :);
data.dopplerBoundHz = double(centerRows.relative_doppler_bound_hz);
data.snapshots = caseJson.five_snapshot_symbols;
data.centerCodeFrequencyHz = double(data.snapshots(3).code_frequency_hz);
native = caseJson.native_stage4_paths;
directIndex = find([native.is_multipath] == 0, 1, "first");
assert(~isempty(directIndex), "No direct path in contract case.");
data.directPath = pathFromJson(native(directIndex));
data.nativePaths = repmat(emptyPath(), 0, 1);
for index = 1:numel(native)
    nativePath = pathFromJson(native(index));
    nativePath.directDelaySamples = data.directPath.delaySamples;
    nativePath.directDopplerHz = data.directPath.dopplerHz;
    data.nativePaths(end + 1, 1) = nativePath; %#ok<AGROW>
end
data.contexts = cell(1, numel(data.snapshots));
for index = 1:numel(data.snapshots)
    data.contexts{index} = makeSignalContext( ...
        data.prn, data.centerCodeFrequencyHz, 204600);
end
end


function [observations, readInfo] = loadObservations(data)
observations = cell(1, numel(data.snapshots));
readInfo = repmat(struct( ...
    "sample_start_zero_based", nan, "sample_count", 204600, ...
    "nav_symbol", nan), 1, numel(data.snapshots));
for index = 1:numel(data.snapshots)
    row = data.snapshots(index);
    observations{index} = readIq(data.rawFile, ...
        double(row.sample_start_zero_based), 204600);
    observations{index} = double(row.nav_symbol) * observations{index};
    observations{index} = normalizeSignal(observations{index});
    readInfo(index).sample_start_zero_based = ...
        double(row.sample_start_zero_based);
    readInfo(index).nav_symbol = double(row.nav_symbol);
end
end


function injected = injectObservations(baseObservations, data, ...
    excessDelaySamples, relativeDopplerHz, relativePowerDb, phaseRad)
injected = cell(size(baseObservations));
ratio = 10^(relativePowerDb / 20);
centerTime = double(data.snapshots(3).recording_time_s);
for index = 1:numel(baseObservations)
    context = data.contexts{index};
    directReplica = makeReplica(data.directPath.delaySamples, ...
        data.directPath.dopplerHz, context);
    directAlpha = directReplica \ baseObservations{index};
    elapsed = double(data.snapshots(index).recording_time_s) - centerTime;
    phaseAtSnapshot = phaseRad + 2 * pi * relativeDopplerHz * elapsed;
    secondary = makeReplica( ...
        data.directPath.delaySamples + excessDelaySamples, ...
        data.directPath.dopplerHz + relativeDopplerHz, context);
    secondaryAlpha = directAlpha * ratio * exp(1j * phaseAtSnapshot);
    injected{index} = baseObservations{index} + secondary * secondaryAlpha;
end
end


function result = estimateJoint(observations, data, estimator)
direct = data.directPath;
models = repmat(invalidModel(1), estimator.maximum_model_order, 1);
models(1) = evaluateJointModel( ...
    direct, observations, data.contexts, data.dopplerBoundHz, estimator);
for order = 2:estimator.maximum_model_order
    previous = models(order - 1);
    if ~previous.valid || isempty(previous.paths)
        break;
    end
    residuals = cell(size(observations));
    for snapshot = 1:numel(observations)
        alpha = solveSnapshotAlpha(previous.paths, ...
            observations{snapshot}, data.contexts{snapshot});
        pathsWithAlpha = previous.paths;
        for pathIndex = 1:numel(pathsWithAlpha)
            pathsWithAlpha(pathIndex).alpha = alpha(pathIndex);
        end
        residuals{snapshot} = observations{snapshot} ...
            - synthesize(pathsWithAlpha, data.contexts{snapshot});
    end
    newPath = initializeResidualPath(residuals, previous.paths, ...
        data.contexts, data.dopplerBoundHz, estimator);
    initialPaths = sortPaths([previous.paths; newPath]);
    paths = runSage(initialPaths, observations, data.contexts, ...
        data.dopplerBoundHz, estimator);
    models(order) = evaluateJointModel( ...
        paths, observations, data.contexts, data.dopplerBoundHz, estimator);
end

selectedOrder = 1;
for order = 2:estimator.maximum_model_order
    previous = models(selectedOrder);
    current = models(order);
    bicGain = previous.bic - current.bic;
    if current.valid && bicGain >= estimator.minimum_sequential_bic_gain ...
            && current.snapshotWins >= estimator.minimum_joint_snapshot_wins
        selectedOrder = order;
    else
        break;
    end
end
selected = models(selectedOrder);
result = struct( ...
    "models", models, "selectedOrder", selectedOrder, ...
    "selected", selected, "jointValid", selected.valid, ...
    "jointRss", selected.rss, "jointBic", selected.bic, ...
    "snapshotWins", selected.snapshotWins);
end


function match = matchInjected(selected, truthExcess, truthDoppler, truthPower, tolerances)
match = struct( ...
    "found", false, "delayErrorSamples", nan, ...
    "dopplerErrorHz", nan, "powerErrorDb", nan, "cost", nan, ...
    "pathIndex", nan);
if isempty(selected.paths) || numel(selected.paths) < 2
    return;
end
direct = selected.paths(1);
for pathIndex = 2:numel(selected.paths)
    path = selected.paths(pathIndex);
    delayError = (path.delaySamples - direct.delaySamples) - truthExcess;
    dopplerError = (path.dopplerHz - direct.dopplerHz) - truthDoppler;
    powerError = selected.relativePowerDb(pathIndex) - truthPower;
    cost = abs(delayError) / tolerances.delay ...
        + abs(dopplerError) / tolerances.doppler ...
        + abs(powerError) / tolerances.power;
    if ~match.found || cost < match.cost
        match.found = true;
        match.delayErrorSamples = delayError;
        match.dopplerErrorHz = dopplerError;
        match.powerErrorDb = powerError;
        match.cost = cost;
        match.pathIndex = pathIndex;
    end
end
if match.found
    match.found = abs(match.delayErrorSamples) <= tolerances.delay ...
        && abs(match.dopplerErrorHz) <= tolerances.doppler ...
        && abs(match.powerErrorDb) <= tolerances.power;
end
end


function match = matchNative(selected, nativePath, tolerances)
match = struct( ...
    "found", false, "delayDriftSamples", nan, ...
    "dopplerDriftHz", nan, "powerDriftDb", nan, ...
    "cost", nan, "pathIndex", nan);
if isempty(selected.paths) || numel(selected.paths) < 2
    return;
end
direct = selected.paths(1);
truthExcess = nativePath.delaySamples - nativePath.directDelaySamples;
truthDoppler = nativePath.dopplerHz - nativePath.directDopplerHz;
truthPower = nativePath.relativePowerDb;
for pathIndex = 2:numel(selected.paths)
    path = selected.paths(pathIndex);
    delayDrift = (path.delaySamples - direct.delaySamples) - truthExcess;
    dopplerDrift = (path.dopplerHz - direct.dopplerHz) - truthDoppler;
    powerDrift = selected.relativePowerDb(pathIndex) - truthPower;
    cost = abs(delayDrift) / tolerances.delay ...
        + abs(dopplerDrift) / tolerances.doppler ...
        + abs(powerDrift) / tolerances.power;
    if ~match.found || cost < match.cost
        match.found = true;
        match.delayDriftSamples = delayDrift;
        match.dopplerDriftHz = dopplerDrift;
        match.powerDriftDb = powerDrift;
        match.cost = cost;
        match.pathIndex = pathIndex;
    end
end
end


function path = pathFromJson(jsonPath)
path = emptyPath();
path.delaySamples = double(jsonPath.delay_samples);
path.dopplerHz = double(jsonPath.doppler_hz);
path.isMultipath = logical(jsonPath.is_multipath);
if isfield(jsonPath, "mean_relative_power_db")
    path.relativePowerDb = double(jsonPath.mean_relative_power_db);
elseif isfield(jsonPath, "relative_power_db")
    path.relativePowerDb = double(jsonPath.relative_power_db);
else
    path.relativePowerDb = nan;
end
end


function path = emptyPath()
path = struct( ...
    "delaySamples", nan, "dopplerHz", nan, ...
    "relativePowerDb", nan, "isMultipath", false, "alpha", 0, ...
    "directDelaySamples", nan, "directDopplerHz", nan);
end


function model = invalidModel(order)
model = struct( ...
    "paths", repmat(emptyPath(), 0, 1), "rss", inf, "bic", inf, ...
    "valid", false, "relativePowerDb", nan(1, order), ...
    "minimumMultipathPowerDb", nan, "maximumRelativeDopplerHz", nan, ...
    "maximumCoherence", nan, "snapshotRss", [], "snapshotWins", 0);
end


function model = evaluateJointModel(paths, observations, contexts, dopplerBound, estimator)
paths = sortPaths(paths);
snapshotRss = zeros(1, numel(observations));
pathPower = zeros(numel(observations), numel(paths));
for snapshot = 1:numel(observations)
    alpha = solveSnapshotAlpha(paths, observations{snapshot}, contexts{snapshot});
    pathsSnapshot = paths;
    for pathIndex = 1:numel(pathsSnapshot)
        pathsSnapshot(pathIndex).alpha = alpha(pathIndex);
        pathPower(snapshot, pathIndex) = abs(alpha(pathIndex))^2;
    end
    snapshotRss(snapshot) = residualRss( ...
        observations{snapshot}, pathsSnapshot, contexts{snapshot});
end
rss = sum(snapshotRss);
n = numel(observations) * numel(observations{1});
order = numel(paths);
parameterCount = 2 * order + 2 * numel(observations) * order + 1;
bic = 2 * n * log(max(rss / n, realmin)) ...
    + parameterCount * log(2 * n);
meanPower = mean(pathPower, 1);
relativePowerDb = 10 * log10(max(meanPower, realmin) ...
    / max(meanPower(1), realmin));
if order == 1
    minimumPower = nan;
    maximumRelativeDoppler = 0;
    minimumSeparation = nan;
else
    minimumPower = min(relativePowerDb(2:end));
    maximumRelativeDoppler = max(abs([paths(2:end).dopplerHz] ...
        - paths(1).dopplerHz));
    minimumSeparation = min(diff([paths.delaySamples]));
end
coherence = replicaCoherence(paths, contexts{1});
valid = all(isfinite([rss, bic]));
if order > 1
    valid = valid && minimumPower >= estimator.minimum_path_power_db ...
        && maximumRelativeDoppler <= dopplerBound + 1e-6 ...
        && minimumSeparation >= estimator.minimum_path_separation_samples - 1e-6 ...
        && coherence <= estimator.maximum_path_coherence;
end
if order == 1
    snapshotWins = numel(observations);
else
    onePath = paths(1);
    onePathRss = zeros(1, numel(observations));
    for snapshot = 1:numel(observations)
        alpha = solveSnapshotAlpha(onePath, observations{snapshot}, contexts{snapshot});
        onePath.alpha = alpha;
        onePathRss(snapshot) = residualRss( ...
            observations{snapshot}, onePath, contexts{snapshot});
    end
    snapshotWins = nnz(snapshotRss < onePathRss);
end
model = struct( ...
    "paths", paths, "rss", rss, "bic", bic, "valid", valid, ...
    "relativePowerDb", relativePowerDb, ...
    "minimumMultipathPowerDb", minimumPower, ...
    "maximumRelativeDopplerHz", maximumRelativeDoppler, ...
    "maximumCoherence", coherence, "snapshotRss", snapshotRss, ...
    "snapshotWins", snapshotWins);
end


function newPath = initializeResidualPath(residuals, existing, contexts, ...
    dopplerBound, estimator)
earliestDelay = min([existing.delaySamples]);
delayMinimum = ceil(earliestDelay + estimator.minimum_path_separation_samples);
delayMaximum = floor(earliestDelay + estimator.maximum_excess_delay_samples);
% Use the frozen production coarse residual-search grid for initialization;
% the local refinement below uses the frozen 0.1-sample/5-Hz grid.
delays = makeGrid(delayMinimum, delayMaximum, 1.0);
dopplers = makeGrid(existing(1).dopplerHz - dopplerBound, ...
    existing(1).dopplerHz + dopplerBound, 50.0);
scores = zeros(numel(delays), numel(dopplers));
for dopplerIndex = 1:numel(dopplers)
    for snapshot = 1:numel(residuals)
        context = contexts{snapshot};
        wiped = residuals{snapshot} .* exp(-1j * 2 * pi ...
            * dopplers(dopplerIndex) * context.timeSeconds);
        correlation = ifft(fft(wiped) .* conj(context.localCodeFft));
        indices = mod(round(delays), context.n) + 1;
        scores(:, dopplerIndex) = scores(:, dopplerIndex) ...
            + abs(correlation(indices)).^2 / context.n;
    end
end
[~, linearIndex] = max(scores(:));
[delayIndex, dopplerIndex] = ind2sub(size(scores), linearIndex);
newPath = emptyPath();
newPath.delaySamples = delays(delayIndex);
newPath.dopplerHz = dopplers(dopplerIndex);
for attempt = 1:numel(scores)
    separation = abs(newPath.delaySamples - [existing.delaySamples]);
    if all(separation >= estimator.minimum_path_separation_samples - 1e-9)
        return;
    end
    scores(linearIndex) = -inf;
    [~, linearIndex] = max(scores(:));
    [delayIndex, dopplerIndex] = ind2sub(size(scores), linearIndex);
    newPath.delaySamples = delays(delayIndex);
    newPath.dopplerHz = dopplers(dopplerIndex);
end
error("No separated residual path was found.");
end


function paths = runSage(paths, observations, contexts, dopplerBound, estimator)
previousRss = inf;
for iteration = 1:estimator.sage_iterations
    for pathIndex = 1:numel(paths)
        other = setdiff(1:numel(paths), pathIndex);
        hidden = cell(size(observations));
        for snapshot = 1:numel(observations)
            if isempty(other)
                hidden{snapshot} = observations{snapshot};
            else
                alpha = solveSnapshotAlpha(paths, observations{snapshot}, contexts{snapshot});
                otherPaths = paths(other);
                for otherIndex = 1:numel(other)
                    otherPaths(otherIndex).alpha = alpha(other(otherIndex));
                end
                hidden{snapshot} = observations{snapshot} ...
                    - synthesize(otherPaths, contexts{snapshot});
            end
        end
        paths(pathIndex) = refineJointPath(paths(pathIndex), hidden, ...
            contexts, dopplerBound, estimator);
    end
    paths = sortPaths(paths);
    current = evaluateJointModel(paths, observations, contexts, dopplerBound, estimator);
    if iteration > 1 && abs(previousRss - current.rss) ...
            / max(previousRss, eps) < estimator.sage_tolerance
        return;
    end
    previousRss = current.rss;
end
end


function path = refineJointPath(path, observations, contexts, dopplerBound, estimator)
delayGrid = makeGrid(path.delaySamples - estimator.local_delay_half_width_samples, ...
    path.delaySamples + estimator.local_delay_half_width_samples, estimator.delay_step_samples);
scores = zeros(size(delayGrid));
for index = 1:numel(delayGrid)
    for snapshot = 1:numel(observations)
        replica = makeReplica(delayGrid(index), path.dopplerHz, contexts{snapshot});
        scores(index) = scores(index) + abs(replica' * observations{snapshot})^2 ...
            / max(real(replica' * replica), eps);
    end
end
[~, best] = max(scores);
path.delaySamples = delayGrid(best);
dopplerGrid = makeGrid(max(path.dopplerHz - estimator.local_doppler_half_width_hz, ...
    path.dopplerHz - dopplerBound), min(path.dopplerHz + estimator.local_doppler_half_width_hz, ...
    path.dopplerHz + dopplerBound), estimator.local_doppler_step_hz);
scores = zeros(size(dopplerGrid));
for index = 1:numel(dopplerGrid)
    for snapshot = 1:numel(observations)
        replica = makeReplica(path.delaySamples, dopplerGrid(index), contexts{snapshot});
        scores(index) = scores(index) + abs(replica' * observations{snapshot})^2 ...
            / max(real(replica' * replica), eps);
    end
end
[~, best] = max(scores);
path.dopplerHz = dopplerGrid(best);
end


function paths = sortPaths(paths)
[~, order] = sort([paths.delaySamples]);
paths = paths(order);
end


function alpha = solveSnapshotAlpha(paths, observed, context)
replicas = buildReplicas(paths, context);
alpha = replicas \ observed;
end


function signal = synthesize(paths, context)
signal = buildReplicas(paths, context) * [paths.alpha].';
end


function rss = residualRss(observed, paths, context)
residual = observed - synthesize(paths, context);
rss = real(residual' * residual);
end


function coherence = replicaCoherence(paths, context)
if numel(paths) < 2
    coherence = 0;
    return;
end
replicas = buildReplicas(paths, context);
replicas = replicas ./ max(sqrt(sum(abs(replicas).^2, 1)), eps);
matrix = abs(replicas' * replicas);
matrix(1:size(matrix, 1) + 1:end) = 0;
coherence = max(matrix(:));
end


function replicas = buildReplicas(paths, context)
replicas = complex(zeros(context.n, numel(paths)));
for index = 1:numel(paths)
    replicas(:, index) = makeReplica(paths(index).delaySamples, ...
        paths(index).dopplerHz, context);
end
end


function context = makeSignalContext(prn, codeFrequencyHz, n)
fsHz = 10230000;
if ~isfinite(codeFrequencyHz) || codeFrequencyHz <= 0
    codeFrequencyHz = 1023000;
end
chips = generateGpsCaCode(prn);
sampleIndex = (0:n - 1).';
chipPhase = mod(sampleIndex * codeFrequencyHz / fsHz, 1023);
chipIndex = floor(chipPhase) + 1;
localCode = chips(chipIndex);
context = struct( ...
    "n", n, "localCodeFft", fft(localCode), ...
    "signedBins", signedFftBins(n), "timeSeconds", sampleIndex / fsHz);
end


function replica = makeReplica(delaySamples, dopplerHz, context)
phase = exp(-1j * 2 * pi * context.signedBins * delaySamples / context.n);
shiftedCode = ifft(context.localCodeFft .* phase);
replica = shiftedCode .* exp(1j * 2 * pi * dopplerHz * context.timeSeconds);
end


function values = makeGrid(minimum, maximum, step)
if maximum < minimum
    values = minimum;
    return;
end
values = minimum:step:maximum;
if isempty(values) || values(end) < maximum - 1e-9
    values = [values, maximum]; %#ok<AGROW>
end
end


function iq = readIq(filename, startSample, sampleCount)
fileId = fopen(filename, "rb", "ieee-le");
assert(fileId >= 0, "Cannot open raw IQ file: %s", filename);
cleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
status = fseek(fileId, double(startSample) * 4, "bof");
assert(status == 0, "Cannot seek to raw sample %.0f.", startSample);
raw = fread(fileId, 2 * sampleCount, "int16=>double");
assert(numel(raw) == 2 * sampleCount, ...
    "Short raw-IQ read at sample %.0f.", startSample);
iq = complex(raw(1:2:end), raw(2:2:end));
end


function observed = normalizeSignal(observed)
observed = observed - mean(observed);
rmsValue = sqrt(mean(abs(observed).^2));
assert(isfinite(rmsValue) && rmsValue > 0, "Invalid IQ signal power.");
observed = observed / rmsValue;
end


function bins = signedFftBins(n)
if mod(n, 2) == 0
    bins = [0:n / 2 - 1, -n / 2:-1].';
else
    bins = [0:(n - 1) / 2, -(n - 1) / 2:-1].';
end
end


function caCode = generateGpsCaCode(prn)
g2TapTable = [ ...
    2,6; 3,7; 4,8; 5,9; 1,9; 2,10; 1,8; 2,9; ...
    3,10; 2,3; 3,4; 5,6; 6,7; 7,8; 8,9; 9,10; ...
    1,4; 2,5; 3,6; 4,7; 5,8; 6,9; 1,3; 4,6; ...
    5,7; 6,8; 7,9; 8,10; 1,6; 2,7; 3,8; 4,9];
assert(prn >= 1 && prn <= size(g2TapTable, 1), ...
    "Unsupported GPS PRN: %d", prn);
g1 = -ones(1, 10);
g2 = -ones(1, 10);
caCode = zeros(1023, 1);
taps = g2TapTable(prn, :);
for index = 1:1023
    caCode(index) = g1(10) * g2(taps(1)) * g2(taps(2));
    g1Feedback = g1(3) * g1(10);
    g2Feedback = g2(2) * g2(3) * g2(6) * g2(8) * g2(9) * g2(10);
    g1 = [g1Feedback, g1(1:9)];
    g2 = [g2Feedback, g2(1:9)];
end
end


function path = sourcePath(contract, role)
sources = contract.source_paths;
for index = 1:numel(sources)
    if string(sources(index).role) == string(role)
        path = string(sources(index).path);
        return;
    end
end
error("Source role not present in validation contract: %s", role);
end


function root = projectRootFromContract(contract)
root = string(contract.output_namespace);
for index = 1:4
    root = fileparts(root);
end
end


function estimator = estimatorFromContract(contract)
e = contract.estimator;
estimator = struct( ...
    "maximum_model_order", double(e.maximum_model_order), ...
    "delay_step_samples", double(e.delay_step_samples), ...
    "minimum_path_separation_samples", double(e.minimum_path_separation_samples), ...
    "local_delay_half_width_samples", double(e.local_delay_half_width_samples), ...
    "local_doppler_step_hz", double(e.local_doppler_step_hz), ...
    "local_doppler_half_width_hz", double(e.local_doppler_half_width_hz), ...
    "maximum_excess_delay_samples", 30, ...
    "minimum_path_power_db", double(e.minimum_path_power_db), ...
    "maximum_path_coherence", double(e.maximum_path_coherence), ...
    "minimum_sequential_bic_gain", double(e.minimum_sequential_bic_gain), ...
    "minimum_joint_snapshot_wins", double(e.minimum_joint_snapshot_wins), ...
    "sage_iterations", double(e.sage_iterations), ...
    "sage_tolerance", double(e.sage_tolerance));
end


function tolerances = tolerancesFromContract(contract)
m = contract.matching;
tolerances = struct( ...
    "delay", double(m.delay_tolerance_samples), ...
    "doppler", double(m.doppler_tolerance_hz), ...
    "power", double(m.power_tolerance_db));
end


function amplitudes = solveAmplitudesExternal(observations, data, paths)
amplitudes = complex(zeros(numel(paths), numel(observations)));
for snapshot = 1:numel(observations)
    amplitudes(:, snapshot) = solveSnapshotAlpha( ...
        paths, observations{snapshot}, data.contexts{snapshot});
end
end


function residual = cancelSecondary(observed, context, paths, alpha, ...
    delayErrorSamples, dopplerErrorHz, powerErrorDb)
residual = observed;
for pathIndex = 2:numel(paths)
    path = paths(pathIndex);
    path.delaySamples = path.delaySamples + delayErrorSamples;
    path.dopplerHz = path.dopplerHz + dopplerErrorHz;
    path.alpha = alpha(pathIndex) * 10^(powerErrorDb / 20);
    residual = residual - synthesize(path, context);
end
end


function [zeroCrossing, discriminator, valid] = dllZeroCrossing( ...
    signal, context, directPath, spacingChips, offsetGridChips)
samplesPerChip = 10;
discriminator = zeros(size(offsetGridChips));
for index = 1:numel(offsetGridChips)
    earlyDelay = directPath.delaySamples ...
        + (offsetGridChips(index) - spacingChips / 2) * samplesPerChip;
    lateDelay = directPath.delaySamples ...
        + (offsetGridChips(index) + spacingChips / 2) * samplesPerChip;
    early = makeReplica(earlyDelay, directPath.dopplerHz, context);
    late = makeReplica(lateDelay, directPath.dopplerHz, context);
    discriminator(index) = abs(early' * signal) - abs(late' * signal);
end
crossingIndices = find(discriminator(1:end - 1) .* discriminator(2:end) <= 0);
if isempty(crossingIndices)
    [~, nearest] = min(abs(discriminator));
    zeroCrossing = offsetGridChips(nearest);
    valid = false;
    return;
end
midpoints = (offsetGridChips(crossingIndices) ...
    + offsetGridChips(crossingIndices + 1)) / 2;
[~, choice] = min(abs(midpoints));
index = crossingIndices(choice);
x1 = offsetGridChips(index);
x2 = offsetGridChips(index + 1);
y1 = discriminator(index);
y2 = discriminator(index + 1);
if y2 == y1
    zeroCrossing = (x1 + x2) / 2;
else
    zeroCrossing = x1 - y1 * (x2 - x1) / (y2 - y1);
end
valid = isfinite(zeroCrossing);
end
