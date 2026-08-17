function result = run_nav_sage_pipeline(sceneId, prn, varargin)
%RUN_NAV_SAGE_PIPELINE Navigation-symbol-aided multipath estimation.
%
% First-stage generic entry point for one scene, one GPS PRN, and one
% explicitly selected GNSS-SDR tracking channel. This version intentionally
% supports only 10.23 MHz recordings so that the validated mathematical
% configuration remains unchanged.
%
% Example:
%   run_nav_sage_pipeline("F1023_V70_D0117_P4", 11, ...
%       "TrackingChannel", 2)
%
% Processing stages:
%   0. Build a catalog from continuous, complete PRN telemetry symbols.
%   1. Wipe the known GPS NAV symbols and scan all valid 40 ms windows.
%   2. Apply 0.01-chip fractional-delay SAGE, L=1..4, to candidates.
%   3. Validate selected paths in five adjacent 40 ms windows.
%   4. Apply common-geometry, five-snapshot 100 ms joint estimation.
%
% L is total path count; multipath count is L-1.
% No previous GNSS-SDR or SAGE result folder is used.
% No specialized MATLAB toolbox is required.

scriptDir = fileparts(mfilename("fullpath"));
coreDirectory = fullfile(scriptDir, "core");
assert(isfile(fullfile(coreDirectory, "run_sage_stage1_stage4_core.m")) && ...
    isfile(fullfile(coreDirectory, "default_sage_configuration.m")), ...
    "Shared SAGE core files are missing: %s", coreDirectory);
addpath(coreDirectory, "-begin");

options = parsePipelineInputs(sceneId, prn, varargin{:});
[prnNumber, prnLabel] = normalizePrn(options.prn);
context = resolveInputs(options, prnNumber, prnLabel);
cfg = default_sage_configuration(prnNumber, ...
    context.samplingRateHz, options.Resume);
cfg.sceneId = char(context.sceneId);
cfg.prnLabel = char(context.prnLabel);
cfg.trackingChannel = context.trackingChannel;

rawFile = context.rawFile;
resultDir = context.gnssSdrDir;
outputDir = context.outputDir;
telemetryFile = context.telemetryFile;
trackingFile = context.trackingFile;
saveRunContext(context, cfg);

fprintf("%s navigation-aided SAGE pipeline V%d\n", ...
    prnLabel, cfg.pipelineVersion);
fprintf("Scene        : %s\n", context.sceneId);
fprintf("PRN          : %s\n", prnLabel);
fprintf("Channel      : %d\n", context.trackingChannel);
fprintf("Project root : %s\n", context.projectRoot);
fprintf("Raw IQ       : %s\n", rawFile);
fprintf("GNSS-SDR     : %s\n", resultDir);
fprintf("Output       : %s\n", outputDir);
fprintf("Delay grid   : %.3f chip\n", ...
    cfg.delayStepSamples / cfg.samplesPerChip);
fprintf("Maximum excess delay: %.2f chips\n", ...
    cfg.maximumExcessDelaySamples / cfg.samplesPerChip);
fprintf("Fallback path Doppler: +/- %.2f Hz\n\n", ...
    cfg.absoluteRelativeDopplerCeilingHz);

assert(isfile(telemetryFile), ...
    "Missing %s telemetry file: %s", prnLabel, telemetryFile);
assert(isfile(trackingFile), ...
    "Missing %s tracking file: %s", prnLabel, trackingFile);

telemetry = readTelemetryDat(telemetryFile);
tracking = readTrackingMat(trackingFile);
[nmeaUtcSod, nmeaSpeedKmh] = ...
    readNmeaSpeed(context.trajectoryDir);

stage0Mat = fullfile(outputDir, "stage0_nav_catalog.mat");
stage0SymbolsCsv = fullfile(outputDir, ...
    "stage0_valid_symbols.csv");
stage0WindowsCsv = fullfile(outputDir, ...
    "stage0_valid_40ms_windows.csv");
overviewFile = fullfile(outputDir, ...
    prnLabel + "_nav_sage_overview.png");

%% Stage 0
if cfg.resumeExistingStages ...
        && checkpointConfigurationMatches(stage0Mat, cfg)
    loaded = load(stage0Mat, ...
        "symbolCatalog", "windowCatalog");
    symbolCatalog = loaded.symbolCatalog;
    windowCatalog = loaded.windowCatalog;
    fprintf("Stage 0 loaded: %d symbols, %d windows\n", ...
        height(symbolCatalog), height(windowCatalog));
else
    fprintf("Stage 0: building navigation-symbol catalog...\n");
    symbolCatalog = buildSymbolCatalog( ...
        telemetry, tracking, cfg);
    windowCatalog = buildFortyMsCatalog( ...
        symbolCatalog, nmeaUtcSod, nmeaSpeedKmh, cfg);
    assert(~isempty(windowCatalog), ...
        "No complete %s 40 ms windows were found.", prnLabel);
    writetable(symbolCatalog, stage0SymbolsCsv);
    writetable(windowCatalog, stage0WindowsCsv);
    save(stage0Mat, "symbolCatalog", ...
        "windowCatalog", "cfg");
    fprintf(['Stage 0 completed: %d valid symbols, ', ...
        '%d complete 40 ms windows\n'], ...
        height(symbolCatalog), height(windowCatalog));
end

%% Stage 1-4 shared core
coreResult = run_sage_stage1_stage4_core( ...
    windowCatalog, symbolCatalog, rawFile, outputDir, cfg);
dopplerSignUsed = coreResult.dopplerSignUsed;
stage1Table = coreResult.stage1Table;
candidateIndices = coreResult.candidateIndices;
stage2Fits = coreResult.stage2Fits;
modelTable = coreResult.modelTable;
selectedTable = coreResult.selectedTable;
pathTable = coreResult.pathTable;
persistenceTable = coreResult.persistenceTable;
reliableTable = coreResult.reliableTable;
jointFits = coreResult.jointFits;
jointSummaryTable = coreResult.jointSummaryTable;
jointPathTable = coreResult.jointPathTable;

plotOverview(stage1Table, selectedTable, ...
    reliableTable, jointSummaryTable, ...
    overviewFile, cfg);

fprintf("\n================ Pipeline completed ================\n");
fprintf("Valid NAV symbols    : %d\n", height(symbolCatalog));
fprintf("Scanned 40 ms windows: %d\n", height(stage1Table));
fprintf("Full SAGE windows    : %d\n", numel(stage2Fits));
fprintf("Selected L>=2        : %d\n", ...
    sum(selectedTable.selected_L >= 2));
fprintf("Selected L>=3        : %d\n", ...
    sum(selectedTable.selected_L >= 3));
fprintf("Reliable centers     : %d\n", height(reliableTable));
fprintf("Joint 100 ms results : %d\n", ...
    height(jointSummaryTable));
fprintf("Overview             : %s\n", overviewFile);
result = struct( ...
    "scene_id", context.sceneId, ...
    "prn", context.prnLabel, ...
    "tracking_channel", context.trackingChannel, ...
    "sampling_rate_hz", cfg.fsHz, ...
    "output_dir", context.outputDir, ...
    "valid_nav_symbols", height(symbolCatalog), ...
    "scanned_windows", height(stage1Table), ...
    "stage2_fits", numel(stage2Fits), ...
    "reliable_centers", height(reliableTable), ...
    "joint_results", height(jointSummaryTable));
end


function options = parsePipelineInputs(sceneId, prn, varargin)
scriptDir = fileparts(mfilename("fullpath"));
defaultProjectRoot = fileparts(fileparts(scriptDir));
parser = inputParser;
addRequired(parser, "sceneId", @(value) ...
    ischar(value) || (isstring(value) && isscalar(value)));
addRequired(parser, "prn", @(value) ...
    (isnumeric(value) && isscalar(value)) ...
    || ischar(value) || (isstring(value) && isscalar(value)));
addParameter(parser, "TrackingChannel", [], @(value) ...
    isempty(value) || (isnumeric(value) && isscalar(value) ...
    && isfinite(value) && value >= 0 && value == round(value)));
addParameter(parser, "ProjectRoot", defaultProjectRoot, @(value) ...
    ischar(value) || (isstring(value) && isscalar(value)));
addParameter(parser, "Resume", true, @(value) ...
    (islogical(value) || isnumeric(value)) && isscalar(value));
parse(parser, sceneId, prn, varargin{:});
options = parser.Results;
options.sceneId = string(options.sceneId);
options.ProjectRoot = string(options.ProjectRoot);
options.Resume = logical(options.Resume);
assert(~isempty(options.TrackingChannel), ...
    "TrackingChannel must be supplied explicitly in phase 1.");
end


function [prnNumber, prnLabel] = normalizePrn(prn)
if isnumeric(prn)
    prnNumber = double(prn);
else
    text = upper(strtrim(string(prn)));
    text = erase(text, "GPS");
    text = erase(text, "PRN");
    text = erase(text, "G");
    prnNumber = str2double(text);
end
assert(isfinite(prnNumber) && prnNumber == round(prnNumber) ...
    && prnNumber >= 1 && prnNumber <= 32, ...
    "PRN must identify a GPS satellite from 1 through 32.");
prnLabel = compose("G%02d", prnNumber);
end


function context = resolveInputs(options, prnNumber, prnLabel)
projectRoot = string(options.ProjectRoot);
assert(isfolder(projectRoot), ...
    "Project root not found: %s", projectRoot);
sceneId = string(options.sceneId);
assert(~contains(sceneId, ["/", "\", ":"]), ...
    "Invalid scene_id: %s", sceneId);
sceneDir = fullfile(projectRoot, "scenes", sceneId);
assert(isfolder(sceneDir), "Scene folder not found: %s", sceneDir);

metadataFile = fullfile(sceneDir, "metadata.json");
assert(isfile(metadataFile), ...
    "Scene metadata not found: %s", metadataFile);
metadataText = fileread(metadataFile);
if ~isempty(metadataText) && metadataText(1) == char(65279)
    metadataText(1) = [];
end
metadata = jsondecode(metadataText);
assert(isfield(metadata, "scene_id") ...
    && string(metadata.scene_id) == sceneId, ...
    "metadata scene_id does not match folder: %s", sceneId);
assert(isfield(metadata, "signal") ...
    && isfield(metadata.signal, "sample_rate_hz"), ...
    "metadata.signal.sample_rate_hz is missing.");
samplingRateHz = double(metadata.signal.sample_rate_hz);
assert(abs(samplingRateHz - 10.23e6) < 1, ...
    ['Phase-1 run_nav_sage_pipeline supports only 10.23 MHz; ', ...
    'scene %s uses %.0f Hz.'], sceneId, samplingRateHz);
assert(isfield(metadata, "raw_iq") ...
    && isfield(metadata.raw_iq, "path"), ...
    "metadata.raw_iq.path is missing.");
rawFile = string(metadata.raw_iq.path);
assert(isfile(rawFile), "Raw IQ file not found: %s", rawFile);

gnssSdrDir = fullfile(sceneDir, "gnss_sdr");
navigationDir = fullfile(sceneDir, "navigation");
trajectoryDir = fullfile(sceneDir, "trajectory");
satelliteDir = fullfile(sceneDir, "satellite");
assert(isfolder(gnssSdrDir), ...
    "GNSS-SDR folder not found: %s", gnssSdrDir);
assert(isfolder(navigationDir), ...
    "Navigation folder not found: %s", navigationDir);
assert(isfolder(trajectoryDir), ...
    "Trajectory folder not found: %s", trajectoryDir);
assert(isfolder(satelliteDir), ...
    "Satellite folder not found: %s", satelliteDir);

channel = double(options.TrackingChannel);
telemetryFile = fullfile(gnssSdrDir, "telemetry", ...
    sprintf("%s_telemetry_ch_%d.dat", sceneId, channel));
trackingFile = fullfile(gnssSdrDir, "tracking", ...
    sprintf("%s_track_ch_%d.mat", sceneId, channel));
assert(isfile(telemetryFile), ...
    "Telemetry file not found: %s", telemetryFile);
assert(isfile(trackingFile), ...
    "Tracking file not found: %s", trackingFile);

nmeaFiles = dir(fullfile(trajectoryDir, "*.nmea"));
assert(isscalar(nmeaFiles), ...
    "Expected exactly one trajectory NMEA file in %s; found %d.", ...
    trajectoryDir, numel(nmeaFiles));
navFiles = dir(fullfile(navigationDir, "rinex_nav", "*.26N"));
assert(isscalar(navFiles), ...
    "Expected exactly one RINEX NAV file; found %d.", numel(navFiles));
satelliteFiles = dir(fullfile(satelliteDir, "*.csv"));

outputDir = fullfile(sceneDir, "sage_results", ...
    "nav_sage_v2", prnLabel);
if ~isfolder(outputDir)
    mkdir(outputDir);
end

context = struct();
context.contextVersion = 1;
context.sceneId = sceneId;
context.prn = prnNumber;
context.prnLabel = prnLabel;
context.trackingChannel = channel;
context.samplingRateHz = samplingRateHz;
context.projectRoot = projectRoot;
context.sceneDir = string(sceneDir);
context.metadataFile = string(metadataFile);
context.rawFile = rawFile;
context.gnssSdrDir = string(gnssSdrDir);
context.navigationDir = string(navigationDir);
context.trajectoryDir = string(trajectoryDir);
context.satelliteDir = string(satelliteDir);
context.telemetryFile = string(telemetryFile);
context.trackingFile = string(trackingFile);
context.nmeaFiles = absoluteFileNames(nmeaFiles);
context.rinexNavFiles = absoluteFileNames(navFiles);
context.satelliteFiles = absoluteFileNames(satelliteFiles);
context.outputDir = string(outputDir);
context.createdAtUtc = string(datetime("now", ...
    "TimeZone", "UTC", "Format", "yyyy-MM-dd'T'HH:mm:ssXXX"));
end


function paths = absoluteFileNames(files)
paths = strings(numel(files), 1);
for index = 1:numel(files)
    paths(index) = string(fullfile(files(index).folder, files(index).name));
end
end


function saveRunContext(context, cfg)
contextMat = fullfile(context.outputDir, "run_context.mat");
contextJson = fullfile(context.outputDir, "run_context.json");
if isfile(contextMat)
    loaded = load(contextMat, "runContext");
    assert(isfield(loaded, "runContext") ...
        && runContextsMatch(loaded.runContext, context), ...
        ['Existing output belongs to a different scene/PRN/channel. ', ...
        'Refusing to reuse: %s'], context.outputDir);
    return;
end
runContext = context; %#ok<NASGU>
save(contextMat, "runContext", "cfg");
fileId = fopen(contextJson, "wt", "n", "UTF-8");
assert(fileId >= 0, "Cannot write run context: %s", contextJson);
cleanup = onCleanup(@() fclose(fileId));
fwrite(fileId, jsonencode(context), "char");
end


function matches = runContextsMatch(left, right)
matches = string(left.sceneId) == string(right.sceneId) ...
    && double(left.prn) == double(right.prn) ...
    && double(left.trackingChannel) == double(right.trackingChannel) ...
    && double(left.samplingRateHz) == double(right.samplingRateHz) ...
    && string(left.rawFile) == string(right.rawFile) ...
    && string(left.telemetryFile) == string(right.telemetryFile) ...
    && string(left.trackingFile) == string(right.trackingFile);
end


function telemetry = readTelemetryDat(filename)
fileId = fopen(filename, "rb", "ieee-le");
assert(fileId >= 0, "Cannot open telemetry file: %s", filename);
cleanup = onCleanup(@() fclose(fileId));

fileInfo = dir(filename);
recordBytes = 32;
assert(mod(fileInfo.bytes, recordBytes) == 0, ...
    "Telemetry file size is not a multiple of 32 bytes.");
recordCount = fileInfo.bytes / recordBytes;

towCurrentS = nan(recordCount, 1);
sampleCounter = zeros(recordCount, 1, "uint64");
towPreambleS = nan(recordCount, 1);
navSymbol = zeros(recordCount, 1, "int32");
prn = zeros(recordCount, 1, "int32");
for index = 1:recordCount
    towCurrentS(index) = fread(fileId, 1, "double=>double");
    sampleCounter(index) = fread(fileId, 1, "uint64=>uint64");
    towPreambleS(index) = fread(fileId, 1, "double=>double");
    navSymbol(index) = fread(fileId, 1, "int32=>int32");
    prn(index) = fread(fileId, 1, "int32=>int32");
end
telemetry = table(towCurrentS, sampleCounter, ...
    towPreambleS, navSymbol, prn, ...
    'VariableNames', { ...
        'tow_s', 'sample_counter', 'preamble_tow_s', ...
        'nav_symbol', 'prn'});
end


function tracking = readTrackingMat(filename)
data = load(filename);
tracking = struct();
tracking.sample = double(pickVector(data, { ...
    'PRN_start_sample_count', ...
    'PRN_start_sample_counter'}, true));
tracking.prn = double(pickVector(data, {'PRN'}, true));
tracking.doppler = double(pickVector(data, { ...
    'carrier_doppler_hz'}, true));
tracking.codeFreq = double(pickVector(data, { ...
    'code_freq_chips'}, true));
tracking.cn0 = double(pickVector(data, { ...
    'CN0_SNV_dB_Hz', 'CN0_dB_Hz'}, true));
tracking.lock = double(pickVector(data, { ...
    'carrier_lock_test'}, false));
tracking.towMs = double(pickVector(data, {'TOW_ms'}, false));

n = numel(tracking.sample);
tracking.prn = padVector(tracking.prn, n, nan);
tracking.doppler = padVector(tracking.doppler, n, nan);
tracking.codeFreq = padVector(tracking.codeFreq, n, nan);
tracking.cn0 = padVector(tracking.cn0, n, nan);
tracking.lock = padVector(tracking.lock, n, nan);
tracking.towMs = padVector(tracking.towMs, n, 0);
end


function [utcSod, speedKmh] = readNmeaSpeed(nmeaDir)
utcSod = [];
speedKmh = [];
files = dir(fullfile(nmeaDir, "*.nmea"));
if isempty(files)
    return;
end
text = fileread(fullfile(files(1).folder, files(1).name));
lines = splitlines(string(text));
for index = 1:numel(lines)
    line = strtrim(lines(index));
    if ~(startsWith(line, "$GPRMC") ...
            || startsWith(line, "$GNRMC"))
        continue;
    end
    fields = split(line, ",");
    if numel(fields) < 8 || fields(3) ~= "A"
        continue;
    end
    timeText = char(fields(2));
    knots = str2double(fields(8));
    if numel(timeText) < 6 || ~isfinite(knots)
        continue;
    end
    hh = str2double(timeText(1:2));
    mm = str2double(timeText(3:4));
    ss = str2double(timeText(5:end));
    if all(isfinite([hh, mm, ss]))
        utcSod(end + 1, 1) = ... %#ok<AGROW>
            hh * 3600 + mm * 60 + ss;
        speedKmh(end + 1, 1) = knots * 1.852; %#ok<AGROW>
    end
end
if numel(utcSod) >= 2
    [utcSod, uniqueIndices] = unique(utcSod, "stable");
    speedKmh = speedKmh(uniqueIndices);
end
end


function catalog = buildSymbolCatalog(telemetry, tracking, cfg)
records = repmat(emptySymbolRecord(), 0, 1);
for index = 1:height(telemetry)
    if telemetry.prn(index) ~= cfg.targetPrn ...
            || ~ismember(double(telemetry.nav_symbol(index)), [-1, 1])
        continue;
    end
    sample = double(telemetry.sample_counter(index));
    [sampleError, trackIndex] = min(abs(tracking.sample - sample));
    if isempty(trackIndex) || sampleError > cfg.sampleStepTolerance
        continue;
    end
    if tracking.prn(trackIndex) ~= cfg.targetPrn ...
            || ~isfinite(tracking.doppler(trackIndex)) ...
            || tracking.cn0(trackIndex) < cfg.minimumCn0DbHz
        continue;
    end
    if isfinite(tracking.lock(trackIndex)) ...
            && tracking.lock(trackIndex) < cfg.minimumCarrierLock
        continue;
    end

    continuousToNext = false;
    nextStepSamples = nan;
    nextTowStepS = nan;
    if index < height(telemetry)
        nextStepSamples = double( ...
            telemetry.sample_counter(index + 1) ...
            - telemetry.sample_counter(index));
        nextTowStepS = telemetry.tow_s(index + 1) ...
            - telemetry.tow_s(index);
        continuousToNext = ...
            telemetry.prn(index + 1) == cfg.targetPrn ...
            && ismember(double(telemetry.nav_symbol(index + 1)), ...
                [-1, 1]) ...
            && abs(nextStepSamples - cfg.samplesPer20Ms) ...
                <= cfg.sampleStepTolerance ...
            && abs(nextTowStepS - 0.020) ...
                <= cfg.towStepToleranceS;
    end

    records(end + 1, 1) = struct( ... %#ok<AGROW>
        "symbol_id", numel(records) + 1, ...
        "telemetry_row", index, ...
        "prn", cfg.targetPrn, ...
        "tow_s", telemetry.tow_s(index), ...
        "sample_start_zero_based", sample, ...
        "recording_time_s", sample / cfg.fsHz, ...
        "nav_symbol", double(telemetry.nav_symbol(index)), ...
        "tracking_index", trackIndex, ...
        "tracking_doppler_hz", tracking.doppler(trackIndex), ...
        "code_frequency_hz", tracking.codeFreq(trackIndex), ...
        "cn0_db_hz", tracking.cn0(trackIndex), ...
        "carrier_lock_test", tracking.lock(trackIndex), ...
        "tracking_tow_ms", tracking.towMs(trackIndex), ...
        "next_step_samples", nextStepSamples, ...
        "next_tow_step_s", nextTowStepS, ...
        "continuous_to_next", continuousToNext);
end
catalog = struct2table(records);
catalog = sortrows(catalog, 'sample_start_zero_based');
catalog.symbol_id = (1:height(catalog)).';
end


function windows = buildFortyMsCatalog( ...
    symbols, nmeaUtcSod, nmeaSpeedKmh, cfg)
records = repmat(emptyWindowRecord(), 0, 1);
for index = 1:height(symbols) - 2
    if ~(symbols.continuous_to_next(index) ...
            && symbols.continuous_to_next(index + 1))
        continue;
    end
    % The catalog excludes invalid telemetry rows.  Require adjacency in
    % the original telemetry stream too, otherwise a rejected row could
    % accidentally be bridged and assigned the wrong navigation symbol.
    if symbols.telemetry_row(index + 1) ...
            ~= symbols.telemetry_row(index) + 1 ...
            || symbols.telemetry_row(index + 2) ...
            ~= symbols.telemetry_row(index) + 2
        continue;
    end
    sampleSteps = diff( ...
        symbols.sample_start_zero_based(index:index + 2));
    towSteps = diff(symbols.tow_s(index:index + 2));
    if any(abs(sampleSteps - cfg.samplesPer20Ms) ...
            > cfg.sampleStepTolerance) ...
            || any(abs(towSteps - 0.020) ...
            > cfg.towStepToleranceS)
        continue;
    end

    speed = interpolateNmeaSpeed( ...
        symbols.tow_s(index), nmeaUtcSod, ...
        nmeaSpeedKmh, cfg);
    [dopplerBound, speedSource] = ...
        speedToDopplerBound(speed, cfg);
    splitSamples = symbols.sample_start_zero_based(index + 1) ...
        - symbols.sample_start_zero_based(index);
    records(end + 1, 1) = struct( ... %#ok<AGROW>
        "window_id", numel(records) + 1, ...
        "symbol_index", index, ...
        "sample_start_zero_based", ...
            symbols.sample_start_zero_based(index), ...
        "recording_time_s", ...
            symbols.recording_time_s(index), ...
        "tow_s", symbols.tow_s(index), ...
        "nav_symbol_1", symbols.nav_symbol(index), ...
        "nav_symbol_2", symbols.nav_symbol(index + 1), ...
        "split_samples", splitSamples, ...
        "tracking_doppler_hz", ...
            symbols.tracking_doppler_hz(index), ...
        "code_frequency_hz", ...
            symbols.code_frequency_hz(index), ...
        "cn0_db_hz", min(symbols.cn0_db_hz(index:index + 1)), ...
        "vehicle_speed_kmh", speed, ...
        "speed_source", speedSource, ...
        "relative_doppler_bound_hz", dopplerBound);
end
windows = struct2table(records);
end


function speed = interpolateNmeaSpeed( ...
    gpsTowS, utcSod, speedKmh, cfg)
speed = nan;
if numel(utcSod) < 2
    return;
end
targetUtcSod = mod(gpsTowS ...
    - cfg.gpsUtcLeapSeconds, 86400);
if targetUtcSod >= min(utcSod) ...
        && targetUtcSod <= max(utcSod)
    speed = interp1(utcSod, speedKmh, ...
        targetUtcSod, "linear");
end
end


function [boundHz, source] = speedToDopplerBound(speedKmh, cfg)
[boundHz, source] = compute_sage_doppler_bound(speedKmh, cfg);
end


function matches = checkpointConfigurationMatches(filename, expectedCfg)
matches = false;
if ~isfile(filename)
    return;
end
try
    loaded = load(filename, 'cfg');
    matches = isfield(loaded, 'cfg') ...
        && isstruct(loaded.cfg) ...
        && isfield(loaded.cfg, 'pipelineVersion') ...
        && isfield(loaded.cfg, 'targetPrn') ...
        && isfield(loaded.cfg, 'trackingChannel') ...
        && isfield(loaded.cfg, 'sceneId') ...
        && isfield(loaded.cfg, 'fsHz') ...
        && isequal(double(loaded.cfg.pipelineVersion), ...
            double(expectedCfg.pipelineVersion)) ...
        && isequal(double(loaded.cfg.targetPrn), ...
            double(expectedCfg.targetPrn)) ...
        && isequal(double(loaded.cfg.trackingChannel), ...
            double(expectedCfg.trackingChannel)) ...
        && string(loaded.cfg.sceneId) == string(expectedCfg.sceneId) ...
        && isequal(double(loaded.cfg.fsHz), ...
            double(expectedCfg.fsHz));
catch
    matches = false;
end
end


function output = pickVector(data, names, required)
output = [];
for index = 1:numel(names)
    if isfield(data, names{index})
        output = data.(names{index});
        output = output(:);
        return;
    end
end
if required
    error("Missing MAT variable. Tried: %s", ...
        strjoin(string(names), ", "));
end
end


function output = padVector(input, n, fillValue)
if isempty(input)
    output = repmat(fillValue, n, 1);
elseif numel(input) >= n
    output = input(1:n);
else
    output = [input(:); ...
        repmat(fillValue, n - numel(input), 1)];
end
end


function plotOverview(stage1, selected, reliable, joint, ...
    outputFile, cfg)
figureHandle = figure('Color', 'w', ...
    'Position', [80, 80, 1700, 1000]);
subplot(2, 2, 1);
scatter(stage1.recording_time_s, ...
    stage1.residual_peak1_power_db, 18, 'filled');
hold on;
scatter(stage1.recording_time_s, ...
    stage1.residual_peak2_power_db, 18, 'filled');
yline(cfg.screenResidualPowerDb, 'r--');
grid on;
xlabel("Recording time (s)");
ylabel("Residual power relative to direct path (dB)");
title("NAV-wiped 40 ms residual scan");
legend("Peak 1", "Peak 2", "Screen threshold");

subplot(2, 2, 2);
if isempty(selected)
    text(0.5, 0.5, "No Stage-2 fit", ...
        'HorizontalAlignment', 'center');
else
    stem(selected.recording_time_s, ...
        selected.selected_L, 'filled');
end
ylim([0.5, 4.5]);
grid on;
xlabel("Recording time (s)");
ylabel("Selected L");
title("Fractional SAGE model order");

subplot(2, 2, 3);
if isempty(reliable)
    text(0.5, 0.5, "No persistent multipath center", ...
        'HorizontalAlignment', 'center');
else
    stem(reliable.recording_time_s, ...
        reliable.selected_L - 1, 'filled');
end
grid on;
xlabel("Recording time (s)");
ylabel("Persistent multipath count");
title("Adjacent-window persistence");

subplot(2, 2, 4);
if isempty(joint)
    text(0.5, 0.5, "No joint 100 ms estimate", ...
        'HorizontalAlignment', 'center');
else
    stem(joint.center_window_id, ...
        joint.joint_selected_L, 'filled');
end
ylim([0.5, 4.5]);
grid on;
xlabel("Center window ID");
ylabel("Joint selected L");
title("Five-snapshot 100 ms result");

try
    exportgraphics(figureHandle, outputFile, ...
        'Resolution', 180);
catch
    saveas(figureHandle, outputFile);
end
close(figureHandle);
end


function record = emptySymbolRecord()
record = struct( ...
    "symbol_id", nan, "telemetry_row", nan, "prn", nan, ...
    "tow_s", nan, "sample_start_zero_based", nan, ...
    "recording_time_s", nan, "nav_symbol", nan, ...
    "tracking_index", nan, "tracking_doppler_hz", nan, ...
    "code_frequency_hz", nan, "cn0_db_hz", nan, ...
    "carrier_lock_test", nan, "tracking_tow_ms", nan, ...
    "next_step_samples", nan, "next_tow_step_s", nan, ...
    "continuous_to_next", false);
end


function record = emptyWindowRecord()
record = struct( ...
    "window_id", nan, "symbol_index", nan, ...
    "sample_start_zero_based", nan, ...
    "recording_time_s", nan, "tow_s", nan, ...
    "nav_symbol_1", nan, "nav_symbol_2", nan, ...
    "split_samples", nan, "tracking_doppler_hz", nan, ...
    "code_frequency_hz", nan, "cn0_db_hz", nan, ...
    "vehicle_speed_kmh", nan, "speed_source", "", ...
    "relative_doppler_bound_hz", nan);
end



