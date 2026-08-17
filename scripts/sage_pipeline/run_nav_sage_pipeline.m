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

%% Stage 1-4 monolithic local implementation
stageResult = run_sage_stage1_stage4_local( ...
    windowCatalog, symbolCatalog, rawFile, outputDir, cfg);
dopplerSignUsed = stageResult.dopplerSignUsed;
stage1Table = stageResult.stage1Table;
candidateIndices = stageResult.candidateIndices;
stage2Fits = stageResult.stage2Fits;
modelTable = stageResult.modelTable;
selectedTable = stageResult.selectedTable;
pathTable = stageResult.pathTable;
persistenceTable = stageResult.persistenceTable;
reliableTable = stageResult.reliableTable;
jointFits = stageResult.jointFits;
jointSummaryTable = stageResult.jointSummaryTable;
jointPathTable = stageResult.jointPathTable;

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



function cfg = default_sage_configuration(targetPrn, samplingRateHz, resumeExisting)
cfg.pipelineVersion = 3;
cfg.targetPrn = targetPrn;
cfg.resumeExistingStages = resumeExisting;

cfg.fsHz = samplingRateHz;
cfg.nominalCodeRateHz = 1.023e6;
cfg.samplesPerChip = cfg.fsHz / cfg.nominalCodeRateHz;
cfg.samplesPerMs = round(cfg.fsHz / 1000);
cfg.samplesPer20Ms = 20 * cfg.samplesPerMs;
cfg.samplesPer40Ms = 40 * cfg.samplesPerMs;
cfg.gpsL1Hz = 1575.42e6;
cfg.c = 299792458;
cfg.lambdaM = cfg.c / cfg.gpsL1Hz;
cfg.gpsUtcLeapSeconds = 18;

cfg.minimumCn0DbHz = 30;
cfg.minimumCarrierLock = -0.5;
cfg.sampleStepTolerance = 2;
cfg.towStepToleranceS = 2e-6;

cfg.maximumVehicleSpeedKmh = 120;
cfg.speedMarginKmh = 10;
cfg.minimumRelativeDopplerBoundHz = 40;
cfg.dopplerMarginHz = 20;
cfg.absoluteRelativeDopplerCeilingHz = ...
    2 * (cfg.maximumVehicleSpeedKmh / 3.6) / cfg.lambdaM;

cfg.mainDelayMinimumSamples = -5;
cfg.mainDelayMaximumSamples = 10;
cfg.maximumExcessDelaySamples = 30;
cfg.mainDopplerHalfWidthHz = 125;

cfg.scanMainDopplerStepHz = 25;
cfg.scanResidualDopplerStepHz = 50;
cfg.scanDelayStepSamples = 0.2;
cfg.scanLocalDelayHalfWidthSamples = 1;
cfg.scanLocalDopplerHalfWidthHz = 30;
cfg.scanLocalDopplerStepHz = 10;
cfg.screenPeakSeparationSamples = 2;
cfg.screenPeakDopplerSeparationHz = 40;
cfg.screenResidualPowerDb = -25;
cfg.maximumBaseCandidates = 24;
cfg.minimumBaseCandidates = 8;
cfg.neighborRadius = 2;
cfg.stage1CheckpointInterval = 20;

cfg.maximumModelOrder = 4;
cfg.delayStepSamples = 0.1; % 0.01 chip
cfg.minimumPathSeparationSamples = 1.0; % 0.10 chip
cfg.localDelayHalfWidthSamples = 0.8;
cfg.localDopplerHalfWidthHz = 30;
cfg.localDopplerStepHz = 5;
cfg.maximumSageIterations = 10;
cfg.sageTolerance = 1e-6;
cfg.minimumPathPowerDb = -25;
cfg.maximumPathCoherence = 0.98;
cfg.minimumSequentialBicGain = 10;
cfg.minimumIncrementalRssPercent = 0.002;
cfg.stage2CheckpointInterval = 2;

cfg.persistenceRadius = 2;
cfg.persistenceMinimumConsecutive = 3;
cfg.persistenceDelayToleranceSamples = 1.5;
cfg.persistenceDopplerToleranceHz = 40;
cfg.persistencePowerToleranceDb = 10;

cfg.jointSnapshotCount = 5;
cfg.maximumJointCenters = 8;
cfg.maximumJointIterations = 8;
cfg.minimumJointSnapshotWins = 4;
end

function [boundHz, source] = compute_sage_doppler_bound(speedKmh, cfg)
%COMPUTE_SAGE_DOPPLER_BOUND Existing production relative-Doppler fallback.
% This utility contains the pre-refactor production formula unchanged.

if isfinite(speedKmh)
    speedForBound = min(cfg.maximumVehicleSpeedKmh, ...
        max(0, speedKmh) + cfg.speedMarginKmh);
    source = "NMEA_RMC";
else
    speedForBound = cfg.maximumVehicleSpeedKmh;
    source = "fallback_120_kmh";
end
boundHz = 2 * (speedForBound / 3.6) / cfg.lambdaM ...
    + cfg.dopplerMarginHz;
boundHz = max(boundHz, cfg.minimumRelativeDopplerBoundHz);
boundHz = min(boundHz, cfg.absoluteRelativeDopplerCeilingHz);
end

function result = run_sage_stage1_stage4_local(windowCatalog, symbolCatalog, rawFile, outputDir, cfg)
%RUN_SAGE_STAGE1_STAGE4_LOCAL Monolithic Stage1-Stage4 execution.
% This local body was mechanically reinserted from the frozen extraction
% source without parameter, threshold, or output-schema changes.

assert(isfolder(outputDir), "SAGE output directory is missing: %s", outputDir);
stage1Mat = fullfile(outputDir, "stage1_nav_fast_scan.mat");
stage1Csv = fullfile(outputDir, "stage1_nav_fast_scan.csv");
stage2Mat = fullfile(outputDir, "stage2_nav_sage_L1_L4.mat");
stage2ModelsCsv = fullfile(outputDir, "stage2_model_orders.csv");
stage2SelectedCsv = fullfile(outputDir, "stage2_selected_windows.csv");
stage2PathsCsv = fullfile(outputDir, "stage2_selected_paths.csv");
stage3Mat = fullfile(outputDir, "stage3_nav_persistence.mat");
stage3Csv = fullfile(outputDir, "stage3_persistence.csv");
stage3ReliableCsv = fullfile(outputDir, "stage3_reliable_centers.csv");
stage4Mat = fullfile(outputDir, "stage4_nav_joint_100ms.mat");
stage4SummaryCsv = fullfile(outputDir, "stage4_joint_summary.csv");
stage4PathsCsv = fullfile(outputDir, "stage4_joint_paths.csv");
dopplerSignFile = fullfile(outputDir, "doppler_sign.mat");

if cfg.resumeExistingStages && checkpointConfigurationMatches(dopplerSignFile, cfg)
    loaded = load(dopplerSignFile, "dopplerSignUsed");
    dopplerSignUsed = loaded.dopplerSignUsed;
else
    dopplerSignUsed = determineDopplerSign(windowCatalog, rawFile, cfg);
    save(dopplerSignFile, "dopplerSignUsed", "cfg");
end
fprintf("GNSS-SDR Doppler sign used: %+d\n", dopplerSignUsed);

stage1CanResume = cfg.resumeExistingStages && checkpointConfigurationMatches(stage1Mat, cfg);
if stage1CanResume
    loaded = load(stage1Mat, "stage1Table");
    stage1Table = loaded.stage1Table;
    if ismember('scan_valid', stage1Table.Properties.VariableNames) && any(stage1Table.scan_valid == 1)
        fprintf("Stage 1 loaded: %d windows\n", height(stage1Table));
    else
        fprintf(["Stage 1 checkpoint has no valid scans; ", ...
            "recomputing with pipeline V%d.\n"], cfg.pipelineVersion);
        stage1CanResume = false;
    end
end
if ~stage1CanResume
    fprintf("\nStage 1: NAV-wiped 40 ms fast scan...\n");
    stage1Table = runFastScan(windowCatalog, rawFile, dopplerSignUsed, outputDir, cfg);
    writetable(stage1Table, stage1Csv);
    save(stage1Mat, "stage1Table", "dopplerSignUsed", "cfg");
end

failedStage1 = stage1Table.scan_valid ~= 1;
if all(failedStage1)
    firstFailure = "unknown Stage 1 error";
    if ismember('error_message', stage1Table.Properties.VariableNames)
        messages = stage1Table.error_message;
        messages = messages(strlength(messages) > 0);
        if ~isempty(messages)
            firstFailure = messages(1);
        end
    end
    error(["Stage 1 failed for all %d windows. ", ...
        "First error: %s"], height(stage1Table), firstFailure);
elseif any(failedStage1)
    warning("Stage 1 failed for %d of %d windows.", nnz(failedStage1), height(stage1Table));
end

candidateIndices = chooseStage2Candidates(stage1Table, windowCatalog, cfg);
fprintf("Stage 1 selected %d windows including neighbors.\n", numel(candidateIndices));

if cfg.resumeExistingStages && checkpointConfigurationMatches(stage2Mat, cfg)
    loaded = load(stage2Mat, "stage2Fits", "modelTable", "selectedTable", "pathTable");
    stage2Fits = loaded.stage2Fits;
    modelTable = loaded.modelTable;
    selectedTable = loaded.selectedTable;
    pathTable = loaded.pathTable;
    fprintf("Stage 2 loaded: %d fitted windows\n", numel(stage2Fits));
else
    fprintf("\nStage 2: NAV-wiped fractional SAGE L=1..4...\n");
    stage2Fits = runStage2(candidateIndices, windowCatalog, stage1Table, rawFile, dopplerSignUsed, outputDir, cfg);
    [modelTable, selectedTable, pathTable] = flattenStage2(stage2Fits, cfg);
    writetable(modelTable, stage2ModelsCsv);
    writetable(selectedTable, stage2SelectedCsv);
    writetable(pathTable, stage2PathsCsv);
    save(stage2Mat, "stage2Fits", "modelTable", "selectedTable", "pathTable", "cfg");
end

if cfg.resumeExistingStages && checkpointConfigurationMatches(stage3Mat, cfg)
    loaded = load(stage3Mat, "persistenceTable", "reliableTable");
    persistenceTable = loaded.persistenceTable;
    reliableTable = loaded.reliableTable;
    fprintf("Stage 3 loaded: %d reliable centers\n", height(reliableTable));
else
    fprintf("\nStage 3: adjacent-window persistence...\n");
    [persistenceTable, reliableTable] = evaluatePersistence(stage2Fits, windowCatalog, cfg);
    writetable(persistenceTable, stage3Csv);
    writetable(reliableTable, stage3ReliableCsv);
    save(stage3Mat, "persistenceTable", "reliableTable", "cfg");
end

if cfg.resumeExistingStages && checkpointConfigurationMatches(stage4Mat, cfg)
    loaded = load(stage4Mat, "jointFits", "jointSummaryTable", "jointPathTable");
    jointFits = loaded.jointFits;
    jointSummaryTable = loaded.jointSummaryTable;
    jointPathTable = loaded.jointPathTable;
    fprintf("Stage 4 loaded: %d joint estimates\n", height(jointSummaryTable));
else
    fprintf("\nStage 4: NAV-wiped joint 100 ms estimation...\n");
    [jointFits, jointSummaryTable, jointPathTable] = runJointStage(reliableTable, stage2Fits, symbolCatalog, windowCatalog, rawFile, dopplerSignUsed, cfg);
    writetable(jointSummaryTable, stage4SummaryCsv);
    writetable(jointPathTable, stage4PathsCsv);
    save(stage4Mat, "jointFits", "jointSummaryTable", "jointPathTable", "cfg");
end

% Keep the Stage 1-4 result container scalar.  stage2Fits and jointFits are
% intentionally non-scalar cell arrays; passing them directly to struct(...)
% makes MATLAB expand the result into a struct array and requires all cell
% dimensions to match.  Field assignment preserves each scientific output
% value without changing its size or contents.
result = struct();
result.dopplerSignUsed = dopplerSignUsed;
result.stage1Table = stage1Table;
result.candidateIndices = candidateIndices;
result.stage2Fits = stage2Fits;
result.modelTable = modelTable;
result.selectedTable = selectedTable;
result.pathTable = pathTable;
result.persistenceTable = persistenceTable;
result.reliableTable = reliableTable;
result.jointFits = jointFits;
result.jointSummaryTable = jointSummaryTable;
result.jointPathTable = jointPathTable;
assert(isstruct(result) && isscalar(result), ...
    "Stage 1-4 result container must remain scalar.");
end

function signUsed = determineDopplerSign( ...
    windows, rawFile, cfg)
probeCount = min(5, height(windows));
indices = unique(round(linspace(1, height(windows), probeCount)));
scores = zeros(2, 1);
signs = [1, -1];
for signIndex = 1:2
    for index = reshape(indices, 1, [])
        row = windows(index, :);
        observed = loadNavWipedFortyMs(row, rawFile, cfg);
        context = makeSignalContext( ...
            row.code_frequency_hz, cfg.samplesPer40Ms, cfg);
        dopplerReference = signs(signIndex) ...
            * row.tracking_doppler_hz;
        dopplerGrid = dopplerReference ...
            + (-cfg.mainDopplerHalfWidthHz: ...
                cfg.scanMainDopplerStepHz: ...
                cfg.mainDopplerHalfWidthHz);
        [path, ~] = gridSearchPath(observed, context, ...
            cfg.mainDelayMinimumSamples: ...
                cfg.mainDelayMaximumSamples, ...
            dopplerGrid);
        scores(signIndex) = scores(signIndex) + path.score;
    end
end
[~, best] = max(scores);
signUsed = signs(best);
end


function stage1Table = runFastScan( ...
    windows, rawFile, dopplerSign, outputDir, cfg)
progressFile = fullfile(outputDir, ...
    "stage1_nav_progress.mat");
records = repmat(emptyStage1Record(), height(windows), 1);
completed = false(height(windows), 1);
if cfg.resumeExistingStages ...
        && checkpointConfigurationMatches(progressFile, cfg)
    loaded = load(progressFile, "records", "completed");
    if numel(loaded.completed) == height(windows)
        records = loaded.records;
        completed = loaded.completed;
        fprintf("Stage 1 resumed: %d / %d\n", ...
            nnz(completed), height(windows));
    end
end

for index = 1:height(windows)
    if completed(index)
        continue;
    end
    try
        records(index) = scanOneWindow( ...
            windows(index, :), rawFile, ...
            dopplerSign, cfg);
    catch exception
        record = emptyStage1Record();
        record.window_id = windows.window_id(index);
        record.recording_time_s = ...
            windows.recording_time_s(index);
        record.error_message = string(exception.message);
        records(index) = record;
    end
    completed(index) = true;
    if mod(index, cfg.stage1CheckpointInterval) == 0 ...
            || index == height(windows)
        fprintf("Stage 1: %d / %d\n", ...
            index, height(windows));
        save(progressFile, "records", "completed", "cfg");
    end
end
stage1Table = struct2table(records);
stage1Table = sortrows(stage1Table, 'window_id');
end


function record = scanOneWindow( ...
    row, rawFile, dopplerSign, cfg)
observed = loadNavWipedFortyMs(row, rawFile, cfg);
context = makeSignalContext( ...
    row.code_frequency_hz, cfg.samplesPer40Ms, cfg);
referenceDoppler = dopplerSign * row.tracking_doppler_hz;
dopplerGrid = referenceDoppler ...
    + (-cfg.mainDopplerHalfWidthHz: ...
        cfg.scanMainDopplerStepHz: ...
        cfg.mainDopplerHalfWidthHz);
[mainPath, ~] = gridSearchPath(observed, context, ...
    cfg.mainDelayMinimumSamples: ...
        cfg.mainDelayMaximumSamples, dopplerGrid);
mainPath = refinePath(mainPath, observed, context, ...
    cfg.mainDelayMinimumSamples, ...
    cfg.mainDelayMaximumSamples, ...
    referenceDoppler - cfg.mainDopplerHalfWidthHz, ...
    referenceDoppler + cfg.mainDopplerHalfWidthHz, ...
    cfg.scanDelayStepSamples, ...
    cfg.scanLocalDelayHalfWidthSamples, ...
    cfg.scanLocalDopplerStepHz, ...
    cfg.scanLocalDopplerHalfWidthHz);
mainPath = solveAmplitudes(mainPath, observed, context);
residual = observed - synthesize(mainPath, context);

delayMinimum = ceil(mainPath.delaySamples ...
    + cfg.minimumPathSeparationSamples);
delayMaximum = floor(mainPath.delaySamples ...
    + cfg.maximumExcessDelaySamples);
delayCandidates = delayMinimum:delayMaximum;
relativeDoppler = makeGrid( ...
    -row.relative_doppler_bound_hz, ...
    row.relative_doppler_bound_hz, ...
    cfg.scanResidualDopplerStepHz);
dopplerCandidates = mainPath.dopplerHz + relativeDoppler;
[~, metric] = gridSearchPath(residual, context, ...
    delayCandidates, dopplerCandidates);
peaks = selectResidualPeaks(metric, delayCandidates, ...
    dopplerCandidates, mainPath.score, cfg);

record = emptyStage1Record();
record.window_id = row.window_id;
record.recording_time_s = row.recording_time_s;
record.tow_s = row.tow_s;
record.cn0_db_hz = row.cn0_db_hz;
record.nav_symbol_1 = row.nav_symbol_1;
record.nav_symbol_2 = row.nav_symbol_2;
record.main_delay_samples = mainPath.delaySamples;
record.main_doppler_hz = mainPath.dopplerHz;
record.main_score = mainPath.score;
record.scan_valid = true;
for peakIndex = 1:min(3, numel(peaks))
    % Use complete character-vector field names.  Mixing a string scalar
    % prefix with a character vector can create a nonscalar string array
    % in some MATLAB releases, which is invalid for dynamic field access.
    delayField = sprintf('residual_peak%d_delay_samples', peakIndex);
    dopplerField = sprintf('residual_peak%d_doppler_hz', peakIndex);
    powerField = sprintf('residual_peak%d_power_db', peakIndex);
    record.(delayField) = peaks(peakIndex).delaySamples;
    record.(dopplerField) = peaks(peakIndex).dopplerHz;
    record.(powerField) = peaks(peakIndex).powerDb;
end
record.has_one_strong_residual = ...
    record.residual_peak1_power_db ...
        >= cfg.screenResidualPowerDb;
record.has_two_strong_residuals = ...
    record.residual_peak2_power_db ...
        >= cfg.screenResidualPowerDb;
record.screen_score_db = record.residual_peak2_power_db;
end


function peaks = selectResidualPeaks( ...
    metric, delays, dopplers, mainScore, cfg)
peaks = repmat(emptyPeak(), 0, 1);
[sortedScores, order] = sort(metric(:), "descend");
for orderIndex = 1:numel(order)
    [delayIndex, dopplerIndex] = ...
        ind2sub(size(metric), order(orderIndex));
    delay = delays(delayIndex);
    doppler = dopplers(dopplerIndex);
    independent = true;
    for existing = 1:numel(peaks)
        if abs(delay - peaks(existing).delaySamples) ...
                < cfg.screenPeakSeparationSamples ...
                && abs(doppler - peaks(existing).dopplerHz) ...
                < cfg.screenPeakDopplerSeparationHz
            independent = false;
            break;
        end
    end
    if ~independent
        continue;
    end
    peak = emptyPeak();
    peak.delaySamples = delay;
    peak.dopplerHz = doppler;
    peak.score = sortedScores(orderIndex);
    peak.powerDb = 10 * log10( ...
        max(peak.score, realmin) / max(mainScore, realmin));
    peaks(end + 1, 1) = peak; %#ok<AGROW>
    if numel(peaks) == 3
        break;
    end
end
end


function indices = chooseStage2Candidates(stage1, windows, cfg)
valid = stage1.scan_valid == 1 ...
    & isfinite(stage1.residual_peak1_power_db);
validIndices = find(valid);
if isempty(validIndices)
    indices = [];
    return;
end

twoPeak = find(valid ...
    & stage1.has_two_strong_residuals == 1);
[~, twoOrder] = sort( ...
    stage1.residual_peak2_power_db(twoPeak), "descend");
twoPeak = twoPeak(twoOrder);

[~, oneOrder] = sort( ...
    stage1.residual_peak1_power_db(validIndices), "descend");
onePeak = validIndices(oneOrder);
base = unique([twoPeak; onePeak], "stable");
baseCount = min(cfg.maximumBaseCandidates, numel(base));
base = base(1:baseCount);
if numel(base) < cfg.minimumBaseCandidates
    count = min(cfg.minimumBaseCandidates, numel(onePeak));
    base = unique([base; onePeak(1:count)], "stable");
end

selected = false(height(windows), 1);
for index = reshape(base, 1, [])
    range = max(1, index - cfg.neighborRadius): ...
        min(height(windows), index + cfg.neighborRadius);
    selected(range) = true;
end
indices = find(selected);
end


function fits = runStage2(candidateIndices, windows, ...
    stage1, rawFile, dopplerSign, outputDir, cfg)
progressFile = fullfile(outputDir, ...
    "stage2_nav_progress.mat");
fits = cell(numel(candidateIndices), 1);
completed = false(numel(candidateIndices), 1);
if cfg.resumeExistingStages ...
        && checkpointConfigurationMatches(progressFile, cfg)
    loaded = load(progressFile, "fits", ...
        "completed", "candidateIndices");
    if isequal(loaded.candidateIndices, candidateIndices)
        fits = loaded.fits;
        completed = loaded.completed;
        fprintf("Stage 2 resumed: %d / %d\n", ...
            nnz(completed), numel(candidateIndices));
    end
end

for position = 1:numel(candidateIndices)
    if completed(position)
        continue;
    end
    index = candidateIndices(position);
    try
        fits{position} = fitAllOrders( ...
            windows(index, :), stage1(index, :), ...
            rawFile, dopplerSign, cfg);
    catch exception
        fits{position} = struct( ...
            "windowId", windows.window_id(index), ...
            "catalogIndex", index, ...
            "models", {cell(cfg.maximumModelOrder, 1)}, ...
            "selectedOrder", nan, ...
            "errorMessage", string(exception.message));
    end
    completed(position) = true;
    if mod(position, cfg.stage2CheckpointInterval) == 0 ...
            || position == numel(candidateIndices)
        fprintf("Stage 2: %d / %d\n", ...
            position, numel(candidateIndices));
        save(progressFile, "fits", "completed", ...
            "candidateIndices", "cfg");
    end
end
end


function fit = fitAllOrders( ...
    row, scanRow, rawFile, dopplerSign, cfg)
observed = loadNavWipedFortyMs(row, rawFile, cfg);
context = makeSignalContext( ...
    row.code_frequency_hz, cfg.samplesPer40Ms, cfg);
referenceDoppler = dopplerSign * row.tracking_doppler_hz;

seed = makePath(scanRow.main_delay_samples, ...
    scanRow.main_doppler_hz);
seed = refinePath(seed, observed, context, ...
    cfg.mainDelayMinimumSamples, ...
    cfg.mainDelayMaximumSamples, ...
    referenceDoppler - cfg.mainDopplerHalfWidthHz, ...
    referenceDoppler + cfg.mainDopplerHalfWidthHz, ...
    cfg.delayStepSamples, cfg.localDelayHalfWidthSamples, ...
    cfg.localDopplerStepHz, cfg.localDopplerHalfWidthHz);
seed = solveAmplitudes(seed, observed, context);

models = cell(cfg.maximumModelOrder, 1);
models{1} = evaluateModel(seed, observed, context, ...
    referenceDoppler, row.relative_doppler_bound_hz, cfg);

for order = 2:cfg.maximumModelOrder
    try
        previousPaths = models{order - 1}.paths;
        if isempty(previousPaths)
            error("Previous model has no usable paths.");
        end
        residual = observed - synthesize(previousPaths, context);
        newPath = initializeResidualPath(residual, ...
            previousPaths, context, ...
            row.relative_doppler_bound_hz, cfg);
        initial = sortPaths([previousPaths, newPath]);
        [paths, history] = runSage(initial, observed, context, ...
            referenceDoppler, row.relative_doppler_bound_hz, cfg);
        models{order} = evaluateModel(paths, observed, context, ...
            referenceDoppler, row.relative_doppler_bound_hz, cfg);
        models{order}.rssHistory = history;
    catch exception
        models{order} = invalidModel(order, exception.message);
    end
end

selectedOrder = 1;
for order = 2:cfg.maximumModelOrder
    previous = models{selectedOrder};
    current = models{order};
    bicGain = previous.bic - current.bic;
    rssGainPercent = 100 * (previous.rss - current.rss) ...
        / max(previous.rss, eps);
    if current.valid ...
            && bicGain >= cfg.minimumSequentialBicGain ...
            && rssGainPercent >= cfg.minimumIncrementalRssPercent
        selectedOrder = order;
    else
        break;
    end
end

fit = struct( ...
    "windowId", row.window_id, ...
    "catalogIndex", row.window_id, ...
    "recordingTimeS", row.recording_time_s, ...
    "towS", row.tow_s, ...
    "models", {models}, ...
    "selectedOrder", selectedOrder, ...
    "errorMessage", "");
end


function newPath = initializeResidualPath( ...
    residual, existing, context, dopplerBound, cfg)
earliestDelay = min([existing.delaySamples]);
delayMinimum = ceil(earliestDelay ...
    + cfg.minimumPathSeparationSamples);
delayMaximum = floor(earliestDelay ...
    + cfg.maximumExcessDelaySamples);
delays = delayMinimum:delayMaximum;
directDoppler = existing(1).dopplerHz;
dopplers = directDoppler + makeGrid( ...
    -dopplerBound, dopplerBound, ...
    cfg.scanResidualDopplerStepHz);
[newPath, metric] = gridSearchPath( ...
    residual, context, delays, dopplers);

for attempt = 1:numel(metric)
    separation = abs(newPath.delaySamples ...
        - [existing.delaySamples]);
    if all(separation >= cfg.minimumPathSeparationSamples)
        return;
    end
    metric(metric == max(metric(:))) = -inf;
    [score, linearIndex] = max(metric(:));
    [delayIndex, dopplerIndex] = ...
        ind2sub(size(metric), linearIndex);
    newPath = makePath( ...
        delays(delayIndex), dopplers(dopplerIndex));
    newPath.score = score;
end
error("No separated residual path could be initialized.");
end


function [paths, history] = runSage(paths, observed, context, ...
    referenceDoppler, dopplerBound, cfg)
history = nan(cfg.maximumSageIterations, 1);
for iteration = 1:cfg.maximumSageIterations
    for pathIndex = 1:numel(paths)
        otherIndices = setdiff(1:numel(paths), pathIndex);
        hidden = observed;
        if ~isempty(otherIndices)
            hidden = hidden - synthesize( ...
                paths(otherIndices), context);
        end
        candidate = refinePath(paths(pathIndex), ...
            hidden, context, ...
            cfg.mainDelayMinimumSamples, ...
            cfg.mainDelayMaximumSamples ...
                + cfg.maximumExcessDelaySamples, ...
            referenceDoppler - dopplerBound, ...
            referenceDoppler + dopplerBound, ...
            cfg.delayStepSamples, cfg.localDelayHalfWidthSamples, ...
            cfg.localDopplerStepHz, cfg.localDopplerHalfWidthHz);
        if isempty(otherIndices) ...
                || all(abs(candidate.delaySamples ...
                    - [paths(otherIndices).delaySamples]) ...
                    >= cfg.minimumPathSeparationSamples)
            paths(pathIndex) = candidate;
        end
    end
    paths = solveAmplitudes(sortPaths(paths), observed, context);
    history(iteration) = residualRss(observed, paths, context);
    if iteration > 1 ...
            && abs(history(iteration - 1) - history(iteration)) ...
                / max(history(iteration - 1), eps) ...
                < cfg.sageTolerance
        history = history(1:iteration);
        return;
    end
end
end


function model = evaluateModel(paths, observed, context, ...
    referenceDoppler, dopplerBound, cfg)
paths = solveAmplitudes(sortPaths(paths), observed, context);
rss = residualRss(observed, paths, context);
n = numel(observed);
order = numel(paths);
parameterCount = 4 * order + 1;
bic = 2 * n * log(max(rss / n, realmin)) ...
    + parameterCount * log(2 * n);
powers = abs([paths.alpha]).^2;
relativePowerDb = 10 * log10( ...
    max(powers, realmin) / max(powers(1), realmin));

if order == 1
    minimumSeparation = nan;
    minimumMultipathPower = nan;
    maximumRelativeDoppler = 0;
else
    minimumSeparation = min(diff([paths.delaySamples]));
    minimumMultipathPower = min(relativePowerDb(2:end));
    maximumRelativeDoppler = max(abs( ...
        [paths(2:end).dopplerHz] - paths(1).dopplerHz));
end
coherence = replicaCoherence(paths, context);
valid = all(isfinite([rss, bic])) ...
    && abs(paths(1).dopplerHz - referenceDoppler) ...
        <= cfg.mainDopplerHalfWidthHz + dopplerBound;
if order > 1
    valid = valid ...
        && minimumSeparation ...
            >= cfg.minimumPathSeparationSamples - 1e-6 ...
        && minimumMultipathPower >= cfg.minimumPathPowerDb ...
        && maximumRelativeDoppler <= dopplerBound + 1e-6 ...
        && coherence <= cfg.maximumPathCoherence;
end
model = struct( ...
    "order", order, "paths", paths, ...
    "rss", rss, "bic", bic, "valid", valid, ...
    "relativePowerDb", relativePowerDb, ...
    "minimumSeparationSamples", minimumSeparation, ...
    "minimumMultipathPowerDb", minimumMultipathPower, ...
    "maximumRelativeDopplerHz", maximumRelativeDoppler, ...
    "maximumCoherence", coherence, ...
    "rssHistory", []);
end


function model = invalidModel(order, message)
model = struct( ...
    "order", order, "paths", [], ...
    "rss", inf, "bic", inf, "valid", false, ...
    "relativePowerDb", nan(1, order), ...
    "minimumSeparationSamples", nan, ...
    "minimumMultipathPowerDb", nan, ...
    "maximumRelativeDopplerHz", nan, ...
    "maximumCoherence", nan, ...
    "rssHistory", [], ...
    "errorMessage", string(message));
end


function [modelTable, selectedTable, pathTable] = ...
    flattenStage2(fits, cfg)
modelRecords = repmat(emptyModelRecord(), 0, 1);
selectedRecords = repmat(emptySelectedRecord(), 0, 1);
pathRecords = repmat(emptyPathRecord(), 0, 1);
for fitIndex = 1:numel(fits)
    fit = fits{fitIndex};
    if isempty(fit) || ~isfinite(fit.selectedOrder)
        continue;
    end
    for order = 1:cfg.maximumModelOrder
        model = fit.models{order};
        previousBic = nan;
        previousRss = nan;
        if order > 1
            previousBic = fit.models{order - 1}.bic;
            previousRss = fit.models{order - 1}.rss;
        end
        modelRecords(end + 1, 1) = struct( ... %#ok<AGROW>
            "window_id", fit.windowId, ...
            "recording_time_s", fit.recordingTimeS, ...
            "model_order", order, ...
            "multipath_count", order - 1, ...
            "rss", model.rss, ...
            "bic", model.bic, ...
            "bic_gain_from_previous", previousBic - model.bic, ...
            "rss_gain_percent_from_previous", ...
                100 * (previousRss - model.rss) ...
                / max(previousRss, eps), ...
            "model_valid", model.valid, ...
            "selected", order == fit.selectedOrder, ...
            "minimum_multipath_power_db", ...
                model.minimumMultipathPowerDb, ...
            "minimum_separation_samples", ...
                model.minimumSeparationSamples, ...
            "maximum_relative_doppler_hz", ...
                model.maximumRelativeDopplerHz, ...
            "maximum_coherence", model.maximumCoherence);
    end
    selected = fit.models{fit.selectedOrder};
    selectedRecords(end + 1, 1) = struct( ... %#ok<AGROW>
        "window_id", fit.windowId, ...
        "recording_time_s", fit.recordingTimeS, ...
        "tow_s", fit.towS, ...
        "selected_L", fit.selectedOrder, ...
        "multipath_count", fit.selectedOrder - 1, ...
        "selected_bic", selected.bic, ...
        "selected_rss", selected.rss, ...
        "minimum_multipath_power_db", ...
            selected.minimumMultipathPowerDb, ...
        "maximum_relative_doppler_hz", ...
            selected.maximumRelativeDopplerHz, ...
        "maximum_coherence", selected.maximumCoherence);

    for pathIndex = 1:fit.selectedOrder
        path = selected.paths(pathIndex);
        pathRecords(end + 1, 1) = struct( ... %#ok<AGROW>
            "window_id", fit.windowId, ...
            "recording_time_s", fit.recordingTimeS, ...
            "selected_L", fit.selectedOrder, ...
            "path_id", pathIndex, ...
            "is_multipath", pathIndex > 1, ...
            "delay_samples", path.delaySamples, ...
            "excess_delay_samples", path.delaySamples ...
                - selected.paths(1).delaySamples, ...
            "excess_delay_chips", (path.delaySamples ...
                - selected.paths(1).delaySamples) ...
                / cfg.samplesPerChip, ...
            "excess_path_length_m", (path.delaySamples ...
                - selected.paths(1).delaySamples) ...
                / cfg.samplesPerChip ...
                * cfg.c / cfg.nominalCodeRateHz, ...
            "doppler_hz", path.dopplerHz, ...
            "doppler_offset_hz", path.dopplerHz ...
                - selected.paths(1).dopplerHz, ...
            "relative_power_db", ...
                selected.relativePowerDb(pathIndex));
    end
end
modelTable = struct2table(modelRecords);
selectedTable = struct2table(selectedRecords);
pathTable = struct2table(pathRecords);
end


function [persistence, reliable] = evaluatePersistence( ...
    fits, windows, cfg)
records = repmat(emptyPersistenceRecord(), 0, 1);
reliableRecords = repmat(emptyReliableRecord(), 0, 1);
for fitIndex = 1:numel(fits)
    centerFit = fits{fitIndex};
    if isempty(centerFit) || centerFit.selectedOrder < 2
        continue;
    end
    centerModel = centerFit.models{centerFit.selectedOrder};
    neighborIds = centerFit.windowId ...
        + (-cfg.persistenceRadius:cfg.persistenceRadius);
    allPathRuns = nan(centerFit.selectedOrder - 1, 1);
    for pathIndex = 2:centerFit.selectedOrder
        centerPath = centerModel.paths(pathIndex);
        centerPower = centerModel.relativePowerDb(pathIndex);
        matched = false(size(neighborIds));
        for neighborPosition = 1:numel(neighborIds)
            neighborFit = findFitByWindowId( ...
                fits, neighborIds(neighborPosition));
            if isempty(neighborFit) ...
                    || neighborFit.selectedOrder < 2
                continue;
            end
            model = neighborFit.models{neighborFit.selectedOrder};
            for candidatePath = 2:neighborFit.selectedOrder
                excessCenter = centerPath.delaySamples ...
                    - centerModel.paths(1).delaySamples;
                excessNeighbor = ...
                    model.paths(candidatePath).delaySamples ...
                    - model.paths(1).delaySamples;
                dopplerCenter = centerPath.dopplerHz ...
                    - centerModel.paths(1).dopplerHz;
                dopplerNeighbor = ...
                    model.paths(candidatePath).dopplerHz ...
                    - model.paths(1).dopplerHz;
                if abs(excessNeighbor - excessCenter) ...
                        <= cfg.persistenceDelayToleranceSamples ...
                        && abs(dopplerNeighbor - dopplerCenter) ...
                        <= cfg.persistenceDopplerToleranceHz ...
                        && abs(model.relativePowerDb(candidatePath) ...
                            - centerPower) ...
                        <= cfg.persistencePowerToleranceDb
                    matched(neighborPosition) = true;
                    break;
                end
            end
        end
        runLength = longestTrueRun(matched);
        allPathRuns(pathIndex - 1) = runLength;
        records(end + 1, 1) = struct( ... %#ok<AGROW>
            "center_window_id", centerFit.windowId, ...
            "center_recording_time_s", ...
                centerFit.recordingTimeS, ...
            "selected_L", centerFit.selectedOrder, ...
            "multipath_id", pathIndex - 1, ...
            "excess_delay_samples", centerPath.delaySamples ...
                - centerModel.paths(1).delaySamples, ...
            "doppler_offset_hz", centerPath.dopplerHz ...
                - centerModel.paths(1).dopplerHz, ...
            "relative_power_db", centerPower, ...
            "matched_window_count", nnz(matched), ...
            "longest_consecutive_count", runLength, ...
            "persistence_pass", runLength ...
                >= cfg.persistenceMinimumConsecutive, ...
            "match_pattern", strjoin(string(double(matched)), ""));
    end
    pass = all(allPathRuns >= cfg.persistenceMinimumConsecutive);
    if pass
        reliableRecords(end + 1, 1) = struct( ... %#ok<AGROW>
            "center_window_id", centerFit.windowId, ...
            "recording_time_s", centerFit.recordingTimeS, ...
            "selected_L", centerFit.selectedOrder, ...
            "multipath_count", centerFit.selectedOrder - 1, ...
            "minimum_path_run", min(allPathRuns), ...
            "reliable_multipath", true);
    end
end
persistence = struct2table(records);
reliable = struct2table(reliableRecords);
if ~isempty(reliable)
    reliable = sortrows(reliable, ...
        {'selected_L', 'minimum_path_run'}, ...
        {'descend', 'descend'});
end
end


function [jointFits, summaryTable, pathTable] = ...
    runJointStage(reliable, fits, symbols, windows, ...
    rawFile, dopplerSign, cfg)
if isempty(reliable)
    jointFits = {};
    summaryTable = struct2table( ...
        repmat(emptyJointSummaryRecord(), 0, 1));
    pathTable = struct2table( ...
        repmat(emptyJointPathRecord(), 0, 1));
    return;
end

centerCount = min(cfg.maximumJointCenters, height(reliable));
jointFits = cell(centerCount, 1);
summaryRecords = repmat(emptyJointSummaryRecord(), 0, 1);
pathRecords = repmat(emptyJointPathRecord(), 0, 1);
for centerPosition = 1:centerCount
    centerId = reliable.center_window_id(centerPosition);
    centerFit = findFitByWindowId(fits, centerId);
    windowRow = windows(centerId, :);
    symbolCenter = windowRow.symbol_index;
    snapshotIndices = symbolCenter + (-2:2);
    if any(snapshotIndices < 1) ...
            || any(snapshotIndices > height(symbols))
        continue;
    end
    if ~all(symbols.continuous_to_next(snapshotIndices))
        continue;
    end

    snapshots = cell(cfg.jointSnapshotCount, 1);
    for snapshot = 1:cfg.jointSnapshotCount
        symbolRow = symbols(snapshotIndices(snapshot), :);
        snapshots{snapshot} = loadNavWipedTwentyMs( ...
            symbolRow, rawFile, cfg);
    end
    context = makeSignalContext( ...
        windowRow.code_frequency_hz, ...
        cfg.samplesPer20Ms, cfg);
    referenceDoppler = dopplerSign ...
        * windowRow.tracking_doppler_hz;
    dopplerBound = windowRow.relative_doppler_bound_hz;

    models = cell(cfg.maximumModelOrder, 1);
    for order = 1:cfg.maximumModelOrder
        seedModel = centerFit.models{order};
        if ~seedModel.valid || isempty(seedModel.paths)
            models{order} = invalidJointModel(order);
            continue;
        end
        try
            paths = seedModel.paths;
            paths = optimizeJointPaths(paths, snapshots, ...
                context, referenceDoppler, dopplerBound, cfg);
            models{order} = evaluateJointModel(paths, snapshots, ...
                context, referenceDoppler, dopplerBound, cfg);
        catch
            models{order} = invalidJointModel(order);
        end
    end
    selectedOrder = 1;
    for order = 2:cfg.maximumModelOrder
        previous = models{selectedOrder};
        current = models{order};
        if current.valid ...
                && previous.bic - current.bic ...
                    >= cfg.minimumSequentialBicGain ...
                && current.snapshotWins ...
                    >= cfg.minimumJointSnapshotWins
            selectedOrder = order;
        else
            break;
        end
    end
    selected = models{selectedOrder};
    jointFits{centerPosition} = struct( ...
        "centerWindowId", centerId, ...
        "models", {models}, ...
        "selectedOrder", selectedOrder);

    summaryRecords(end + 1, 1) = struct( ... %#ok<AGROW>
        "center_window_id", centerId, ...
        "recording_time_s", windowRow.recording_time_s, ...
        "stage2_L", centerFit.selectedOrder, ...
        "joint_selected_L", selectedOrder, ...
        "joint_multipath_count", selectedOrder - 1, ...
        "joint_rss", selected.rss, ...
        "joint_bic", selected.bic, ...
        "snapshot_wins_vs_L1", selected.snapshotWins, ...
        "minimum_multipath_power_db", ...
            selected.minimumMultipathPowerDb, ...
        "maximum_relative_doppler_hz", ...
            selected.maximumRelativeDopplerHz, ...
        "maximum_coherence", selected.maximumCoherence, ...
        "joint_valid", selected.valid);

    for pathIndex = 1:selectedOrder
        path = selected.paths(pathIndex);
        pathRecords(end + 1, 1) = struct( ... %#ok<AGROW>
            "center_window_id", centerId, ...
            "joint_selected_L", selectedOrder, ...
            "path_id", pathIndex, ...
            "is_multipath", pathIndex > 1, ...
            "delay_samples", path.delaySamples, ...
            "excess_delay_samples", path.delaySamples ...
                - selected.paths(1).delaySamples, ...
            "excess_delay_chips", (path.delaySamples ...
                - selected.paths(1).delaySamples) ...
                / cfg.samplesPerChip, ...
            "doppler_hz", path.dopplerHz, ...
            "doppler_offset_hz", path.dopplerHz ...
                - selected.paths(1).dopplerHz, ...
            "mean_relative_power_db", ...
                selected.relativePowerDb(pathIndex));
    end
end
summaryTable = struct2table(summaryRecords);
pathTable = struct2table(pathRecords);
end


function paths = optimizeJointPaths(paths, snapshots, ...
    context, referenceDoppler, dopplerBound, cfg)
for iteration = 1:cfg.maximumJointIterations
    previous = evaluateJointModel(paths, snapshots, context, ...
        referenceDoppler, dopplerBound, cfg);
    for pathIndex = 1:numel(paths)
        other = setdiff(1:numel(paths), pathIndex);
        hidden = cell(size(snapshots));
        for snapshot = 1:numel(snapshots)
            if isempty(other)
                hidden{snapshot} = snapshots{snapshot};
            else
                alpha = solveSnapshotAlpha( ...
                    paths, snapshots{snapshot}, context);
                otherPaths = paths(other);
                for index = 1:numel(other)
                    otherPaths(index).alpha = alpha(other(index));
                end
                hidden{snapshot} = snapshots{snapshot} ...
                    - synthesize(otherPaths, context);
            end
        end
        candidate = refineJointPath(paths(pathIndex), ...
            hidden, context, ...
            referenceDoppler - dopplerBound, ...
            referenceDoppler + dopplerBound, cfg);
        if isempty(other) ...
                || all(abs(candidate.delaySamples ...
                    - [paths(other).delaySamples]) ...
                    >= cfg.minimumPathSeparationSamples)
            paths(pathIndex) = candidate;
        end
    end
    paths = sortPaths(paths);
    current = evaluateJointModel(paths, snapshots, context, ...
        referenceDoppler, dopplerBound, cfg);
    if abs(previous.rss - current.rss) ...
            / max(previous.rss, eps) < cfg.sageTolerance
        break;
    end
end
end


function path = refineJointPath(path, observations, context, ...
    dopplerMinimum, dopplerMaximum, cfg)
delayGrid = makeGrid( ...
    path.delaySamples - cfg.localDelayHalfWidthSamples, ...
    path.delaySamples + cfg.localDelayHalfWidthSamples, ...
    cfg.delayStepSamples);
scores = zeros(size(delayGrid));
for index = 1:numel(delayGrid)
    replica = makeReplica(delayGrid(index), ...
        path.dopplerHz, context);
    energy = real(replica' * replica);
    for snapshot = 1:numel(observations)
        scores(index) = scores(index) ...
            + abs(replica' * observations{snapshot}).^2 ...
            / max(energy, eps);
    end
end
[~, best] = max(scores);
path.delaySamples = delayGrid(best);

dopplerGrid = makeGrid( ...
    max(dopplerMinimum, path.dopplerHz ...
        - cfg.localDopplerHalfWidthHz), ...
    min(dopplerMaximum, path.dopplerHz ...
        + cfg.localDopplerHalfWidthHz), ...
    cfg.localDopplerStepHz);
scores = zeros(size(dopplerGrid));
for index = 1:numel(dopplerGrid)
    replica = makeReplica(path.delaySamples, ...
        dopplerGrid(index), context);
    energy = real(replica' * replica);
    for snapshot = 1:numel(observations)
        scores(index) = scores(index) ...
            + abs(replica' * observations{snapshot}).^2 ...
            / max(energy, eps);
    end
end
[~, best] = max(scores);
path.dopplerHz = dopplerGrid(best);
end


function model = evaluateJointModel(paths, snapshots, context, ...
    referenceDoppler, dopplerBound, cfg)
paths = sortPaths(paths);
k = numel(snapshots);
l = numel(paths);
snapshotRss = zeros(k, 1);
pathPower = zeros(k, l);
for snapshot = 1:k
    alpha = solveSnapshotAlpha(paths, ...
        snapshots{snapshot}, context);
    snapshotPaths = paths;
    for pathIndex = 1:l
        snapshotPaths(pathIndex).alpha = alpha(pathIndex);
        pathPower(snapshot, pathIndex) = abs(alpha(pathIndex)).^2;
    end
    snapshotRss(snapshot) = residualRss( ...
        snapshots{snapshot}, snapshotPaths, context);
end
rss = sum(snapshotRss);
n = k * numel(snapshots{1});
parameterCount = 2 * l + 2 * k * l + 1;
bic = 2 * n * log(max(rss / n, realmin)) ...
    + parameterCount * log(2 * n);
meanPower = mean(pathPower, 1);
relativePowerDb = 10 * log10( ...
    max(meanPower, realmin) / max(meanPower(1), realmin));
if l == 1
    minimumPower = nan;
    maximumRelativeDoppler = 0;
    minimumSeparation = nan;
else
    minimumPower = min(relativePowerDb(2:end));
    maximumRelativeDoppler = max(abs( ...
        [paths(2:end).dopplerHz] - paths(1).dopplerHz));
    minimumSeparation = min(diff([paths.delaySamples]));
end
coherence = replicaCoherence(paths, context);
valid = all(isfinite([rss, bic])) ...
    && abs(paths(1).dopplerHz - referenceDoppler) ...
        <= cfg.mainDopplerHalfWidthHz + dopplerBound;
if l > 1
    valid = valid ...
        && minimumPower >= cfg.minimumPathPowerDb ...
        && maximumRelativeDoppler <= dopplerBound + 1e-6 ...
        && minimumSeparation ...
            >= cfg.minimumPathSeparationSamples - 1e-6 ...
        && coherence <= cfg.maximumPathCoherence;
end

snapshotWins = k;
if l > 1
    onePath = paths(1);
    onePathRss = zeros(k, 1);
    for snapshot = 1:k
        alpha = solveSnapshotAlpha(onePath, ...
            snapshots{snapshot}, context);
        onePath.alpha = alpha;
        onePathRss(snapshot) = residualRss( ...
            snapshots{snapshot}, onePath, context);
    end
    snapshotWins = nnz(snapshotRss < onePathRss);
end
model = struct( ...
    "paths", paths, "rss", rss, "bic", bic, ...
    "valid", valid, "relativePowerDb", relativePowerDb, ...
    "minimumMultipathPowerDb", minimumPower, ...
    "maximumRelativeDopplerHz", maximumRelativeDoppler, ...
    "maximumCoherence", coherence, ...
    "snapshotRss", snapshotRss, ...
    "snapshotWins", snapshotWins);
end


function model = invalidJointModel(order)
model = struct( ...
    "paths", [], "rss", inf, "bic", inf, ...
    "valid", false, ...
    "relativePowerDb", nan(1, order), ...
    "minimumMultipathPowerDb", nan, ...
    "maximumRelativeDopplerHz", nan, ...
    "maximumCoherence", nan, ...
    "snapshotRss", [], "snapshotWins", 0);
end


function alpha = solveSnapshotAlpha(paths, observed, context)
replicas = buildReplicas(paths, context);
alpha = replicas \ observed;
end


function fit = findFitByWindowId(fits, windowId)
fit = [];
for index = 1:numel(fits)
    if ~isempty(fits{index}) ...
            && isfield(fits{index}, 'windowId') ...
            && fits{index}.windowId == windowId
        fit = fits{index};
        return;
    end
end
end


function lengthOut = longestTrueRun(values)
lengthOut = 0;
current = 0;
for index = 1:numel(values)
    if values(index)
        current = current + 1;
        lengthOut = max(lengthOut, current);
    else
        current = 0;
    end
end
end


function observed = loadNavWipedFortyMs(row, rawFile, cfg)
observed = readIq(rawFile, ...
    row.sample_start_zero_based, cfg.samplesPer40Ms);
split = round(row.split_samples);
assert(split > 0 && split < numel(observed), ...
    "Invalid navigation-symbol split.");
observed(1:split) = row.nav_symbol_1 ...
    * observed(1:split);
observed(split + 1:end) = row.nav_symbol_2 ...
    * observed(split + 1:end);
observed = normalizeSignal(observed);
end


function observed = loadNavWipedTwentyMs(row, rawFile, cfg)
observed = readIq(rawFile, ...
    row.sample_start_zero_based, cfg.samplesPer20Ms);
observed = row.nav_symbol * observed;
observed = normalizeSignal(observed);
end


function observed = normalizeSignal(observed)
observed = observed - mean(observed);
rmsValue = sqrt(mean(abs(observed).^2));
assert(isfinite(rmsValue) && rmsValue > 0, ...
    "Invalid IQ signal power.");
observed = observed / rmsValue;
end


function context = makeSignalContext(codeFrequencyHz, n, cfg)
if ~isfinite(codeFrequencyHz) || codeFrequencyHz <= 0
    codeFrequencyHz = cfg.nominalCodeRateHz;
end
chips = generateGpsCaCode(cfg.targetPrn);
sampleIndex = (0:n - 1).';
chipPhase = mod(sampleIndex * codeFrequencyHz / cfg.fsHz, 1023);
chipIndex = floor(chipPhase) + 1;
localCode = chips(chipIndex);
context = struct( ...
    "n", n, ...
    "localCodeFft", fft(localCode), ...
    "signedBins", signedFftBins(n), ...
    "timeSeconds", sampleIndex / cfg.fsHz);
end


function [bestPath, metric] = gridSearchPath( ...
    observed, context, delayCandidates, dopplerCandidates)
delayCandidates = round(delayCandidates(:));
dopplerCandidates = dopplerCandidates(:).';
assert(~isempty(delayCandidates) && ~isempty(dopplerCandidates), ...
    "Empty delay or Doppler search grid.");
indices = mod(delayCandidates, context.n) + 1;
metric = zeros(numel(delayCandidates), numel(dopplerCandidates));
for dopplerIndex = 1:numel(dopplerCandidates)
    wiped = observed .* exp(-1j * 2 * pi ...
        * dopplerCandidates(dopplerIndex) ...
        * context.timeSeconds);
    correlation = ifft(fft(wiped) ...
        .* conj(context.localCodeFft));
    metric(:, dopplerIndex) = ...
        abs(correlation(indices)).^2 / context.n;
end
[score, linearIndex] = max(metric(:));
[delayIndex, dopplerIndex] = ...
    ind2sub(size(metric), linearIndex);
bestPath = makePath(delayCandidates(delayIndex), ...
    dopplerCandidates(dopplerIndex));
bestPath.score = score;
end


function path = refinePath(path, observed, context, ...
    delayMinimum, delayMaximum, dopplerMinimum, dopplerMaximum, ...
    delayStep, delayHalfWidth, dopplerStep, dopplerHalfWidth)
for iteration = 1:2
    delayGrid = makeGrid( ...
        max(delayMinimum, path.delaySamples - delayHalfWidth), ...
        min(delayMaximum, path.delaySamples + delayHalfWidth), ...
        delayStep);
    scores = zeros(size(delayGrid));
    for index = 1:numel(delayGrid)
        replica = makeReplica(delayGrid(index), ...
            path.dopplerHz, context);
        scores(index) = abs(replica' * observed).^2 ...
            / max(real(replica' * replica), eps);
    end
    [~, best] = max(scores);
    path.delaySamples = delayGrid(best);

    dopplerGrid = makeGrid( ...
        max(dopplerMinimum, ...
            path.dopplerHz - dopplerHalfWidth), ...
        min(dopplerMaximum, ...
            path.dopplerHz + dopplerHalfWidth), ...
        dopplerStep);
    scores = zeros(size(dopplerGrid));
    for index = 1:numel(dopplerGrid)
        replica = makeReplica(path.delaySamples, ...
            dopplerGrid(index), context);
        scores(index) = abs(replica' * observed).^2 ...
            / max(real(replica' * replica), eps);
    end
    [path.score, best] = max(scores);
    path.dopplerHz = dopplerGrid(best);
end
end


function replica = makeReplica(delaySamples, dopplerHz, context)
phase = exp(-1j * 2 * pi * context.signedBins ...
    * delaySamples / context.n);
shiftedCode = ifft(context.localCodeFft .* phase);
replica = shiftedCode .* exp(1j * 2 * pi ...
    * dopplerHz * context.timeSeconds);
end


function replicas = buildReplicas(paths, context)
replicas = complex(zeros(context.n, numel(paths)));
for index = 1:numel(paths)
    replicas(:, index) = makeReplica( ...
        paths(index).delaySamples, ...
        paths(index).dopplerHz, context);
end
end


function paths = solveAmplitudes(paths, observed, context)
replicas = buildReplicas(paths, context);
alpha = replicas \ observed;
for index = 1:numel(paths)
    paths(index).alpha = alpha(index);
    paths(index).score = abs(replicas(:, index)' * observed).^2 ...
        / max(real(replicas(:, index)' ...
            * replicas(:, index)), eps);
end
end


function signal = synthesize(paths, context)
replicas = buildReplicas(paths, context);
signal = replicas * [paths.alpha].';
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
replicas = replicas ./ max( ...
    sqrt(sum(abs(replicas).^2, 1)), eps);
matrix = abs(replicas' * replicas);
matrix(1:size(matrix, 1) + 1:end) = 0;
coherence = max(matrix(:));
end


function path = makePath(delaySamples, dopplerHz)
path = struct( ...
    "delaySamples", double(delaySamples), ...
    "dopplerHz", double(dopplerHz), ...
    "alpha", complex(0), ...
    "score", 0);
end


function paths = sortPaths(paths)
[~, order] = sort([paths.delaySamples]);
paths = paths(order);
end


function values = makeGrid(minimum, maximum, step)
if maximum < minimum
    values = [];
    return;
end
count = floor((maximum - minimum) / step + 1e-9);
values = minimum + (0:count) * step;
if isempty(values) || maximum - values(end) > 0.25 * step
    values(end + 1) = maximum;
end
end


function bins = signedFftBins(n)
if mod(n, 2) == 0
    bins = [0:n / 2 - 1, -n / 2:-1].';
else
    bins = [0:(n - 1) / 2, ...
        -(n - 1) / 2:-1].';
end
end


function iq = readIq(filename, startSample, sampleCount)
fileId = fopen(filename, "rb", "ieee-le");
assert(fileId >= 0, "Cannot open raw IQ file: %s", filename);
cleanup = onCleanup(@() fclose(fileId));
status = fseek(fileId, double(startSample) * 4, "bof");
assert(status == 0, ...
    "Cannot seek to raw sample %.0f.", startSample);
raw = fread(fileId, 2 * sampleCount, "int16=>double");
assert(numel(raw) == 2 * sampleCount, ...
    "Short raw-IQ read at sample %.0f.", startSample);
iq = complex(raw(1:2:end), raw(2:2:end));
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
    caCode(index) = g1(10) ...
        * g2(taps(1)) * g2(taps(2));
    g1Feedback = g1(3) * g1(10);
    g2Feedback = g2(2) * g2(3) * g2(6) ...
        * g2(8) * g2(9) * g2(10);
    g1 = [g1Feedback, g1(1:9)];
    g2 = [g2Feedback, g2(1:9)];
end
end



function record = emptyStage1Record()
record = struct( ...
    "window_id", nan, "recording_time_s", nan, ...
    "tow_s", nan, "cn0_db_hz", nan, ...
    "nav_symbol_1", nan, "nav_symbol_2", nan, ...
    "scan_valid", false, ...
    "main_delay_samples", nan, "main_doppler_hz", nan, ...
    "main_score", nan, ...
    "residual_peak1_delay_samples", nan, ...
    "residual_peak1_doppler_hz", nan, ...
    "residual_peak1_power_db", nan, ...
    "residual_peak2_delay_samples", nan, ...
    "residual_peak2_doppler_hz", nan, ...
    "residual_peak2_power_db", nan, ...
    "residual_peak3_delay_samples", nan, ...
    "residual_peak3_doppler_hz", nan, ...
    "residual_peak3_power_db", nan, ...
    "has_one_strong_residual", false, ...
    "has_two_strong_residuals", false, ...
    "screen_score_db", nan, "error_message", "");
end


function peak = emptyPeak()
peak = struct("delaySamples", nan, "dopplerHz", nan, ...
    "score", nan, "powerDb", nan);
end


function record = emptyModelRecord()
record = struct( ...
    "window_id", nan, "recording_time_s", nan, ...
    "model_order", nan, "multipath_count", nan, ...
    "rss", nan, "bic", nan, ...
    "bic_gain_from_previous", nan, ...
    "rss_gain_percent_from_previous", nan, ...
    "model_valid", false, "selected", false, ...
    "minimum_multipath_power_db", nan, ...
    "minimum_separation_samples", nan, ...
    "maximum_relative_doppler_hz", nan, ...
    "maximum_coherence", nan);
end


function record = emptySelectedRecord()
record = struct( ...
    "window_id", nan, "recording_time_s", nan, ...
    "tow_s", nan, "selected_L", nan, ...
    "multipath_count", nan, "selected_bic", nan, ...
    "selected_rss", nan, ...
    "minimum_multipath_power_db", nan, ...
    "maximum_relative_doppler_hz", nan, ...
    "maximum_coherence", nan);
end


function record = emptyPathRecord()
record = struct( ...
    "window_id", nan, "recording_time_s", nan, ...
    "selected_L", nan, "path_id", nan, ...
    "is_multipath", false, "delay_samples", nan, ...
    "excess_delay_samples", nan, ...
    "excess_delay_chips", nan, ...
    "excess_path_length_m", nan, ...
    "doppler_hz", nan, "doppler_offset_hz", nan, ...
    "relative_power_db", nan);
end


function record = emptyPersistenceRecord()
record = struct( ...
    "center_window_id", nan, ...
    "center_recording_time_s", nan, ...
    "selected_L", nan, "multipath_id", nan, ...
    "excess_delay_samples", nan, ...
    "doppler_offset_hz", nan, "relative_power_db", nan, ...
    "matched_window_count", nan, ...
    "longest_consecutive_count", nan, ...
    "persistence_pass", false, "match_pattern", "");
end


function record = emptyReliableRecord()
record = struct( ...
    "center_window_id", nan, "recording_time_s", nan, ...
    "selected_L", nan, "multipath_count", nan, ...
    "minimum_path_run", nan, "reliable_multipath", false);
end


function record = emptyJointSummaryRecord()
record = struct( ...
    "center_window_id", nan, "recording_time_s", nan, ...
    "stage2_L", nan, "joint_selected_L", nan, ...
    "joint_multipath_count", nan, ...
    "joint_rss", nan, "joint_bic", nan, ...
    "snapshot_wins_vs_L1", nan, ...
    "minimum_multipath_power_db", nan, ...
    "maximum_relative_doppler_hz", nan, ...
    "maximum_coherence", nan, "joint_valid", false);
end


function record = emptyJointPathRecord()
record = struct( ...
    "center_window_id", nan, "joint_selected_L", nan, ...
    "path_id", nan, "is_multipath", false, ...
    "delay_samples", nan, "excess_delay_samples", nan, ...
    "excess_delay_chips", nan, "doppler_hz", nan, ...
    "doppler_offset_hz", nan, ...
    "mean_relative_power_db", nan);
end
