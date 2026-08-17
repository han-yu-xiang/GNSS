function plot_G06_window203_overlay
% Plot Window203 raw NAV-wiped correlation with Stage2 P1/P2 overlay
%
% Place in:
%   F:\F1023_V70_D0117_P2
%
% Run:
%   matlab -batch "plot_G06_window203_overlay"
%
% Output:
%   sage_results\G06_nav_sage_v1\diagnostics\window203_raw_correlation_overlay.png
%   sage_results\G06_nav_sage_v1\diagnostics\window203_raw_correlation_overlay.csv

clear; clc;

fprintf('G06 Window203 raw correlation + Stage2 overlay\n');

rootDir = fileparts(mfilename('fullpath'));
resultDir = fullfile(rootDir,'sage_results','G06_nav_sage_v1');
diagDir = fullfile(resultDir,'diagnostics');
if ~isfolder(diagDir)
    mkdir(diagDir);
end

% Load Stage0 window catalog / cfg
S = load(fullfile(resultDir,'stage0_nav_catalog.mat'),'windowCatalog','cfg');
windows = S.windowCatalog;
cfg = S.cfg;

row = windows(windows.window_id==203,:);
assert(height(row)==1,'Window 203 not found.');

% Load Stage2 internal path diagnostic if available
pathCsv = fullfile(diagDir,'window203_stage2_internal_paths.csv');
assert(isfile(pathCsv),['Missing ',pathCsv,...
    '. Run plot_G06_window203_stage2_internal_ddm first.']);
pathTable = readtable(pathCsv);

% Sort by path id and keep first two paths (P1/P2)
pathTable = sortrows(pathTable,'path_id');
pathTable = pathTable(pathTable.path_id<=2,:);

fprintf('Using Stage2 paths:\n');
disp(pathTable);

% Resolve raw IQ
addressCandidates = { ...
    fullfile(rootDir,'raw','data_address.txt'), ...
    fullfile(rootDir,'data_address.txt')};

addressFile = '';
for k = 1:numel(addressCandidates)
    if isfile(addressCandidates{k})
        addressFile = addressCandidates{k};
        break;
    end
end
assert(~isempty(addressFile),'data_address.txt not found.');

rawFile = strtrim(fileread(addressFile));
rawFile = strrep(rawFile,'"','');
rawFile = strrep(rawFile,'''','');
if ~isfile(rawFile)
    candidate = fullfile(rootDir,rawFile);
    assert(isfile(candidate),'Raw IQ file not found: %s',rawFile);
    rawFile = candidate;
end

fprintf('Raw IQ: %s\n',rawFile);

% Read 40 ms IQ
N = cfg.samplesPer40Ms;
fid = fopen(rawFile,'rb','ieee-le');
assert(fid>0,'Cannot open raw IQ file.');
cleanupObj = onCleanup(@() fclose(fid));

status = fseek(fid,double(row.sample_start_zero_based)*4,'bof');
assert(status==0,'Cannot seek raw IQ file.');

raw = fread(fid,2*N,'int16=>double');
assert(numel(raw)==2*N,'Short read from raw IQ file.');

iq = complex(raw(1:2:end),raw(2:2:end));

% NAV wipe
split = round(row.split_samples);
assert(split>0 && split<length(iq),'Invalid split_samples.');

iq(1:split) = row.nav_symbol_1 * iq(1:split);
iq(split+1:end) = row.nav_symbol_2 * iq(split+1:end);

% Normalize
iq = iq - mean(iq);
iq = iq / sqrt(mean(abs(iq).^2));

% Doppler compensation by Stage2 P1 reference
if ismember('relative_doppler_hz',pathTable.Properties.VariableNames)
    relDopp = pathTable.relative_doppler_hz;
else
    relDopp = zeros(height(pathTable),1);
end

if ismember('path_id',pathTable.Properties.VariableNames) && any(pathTable.path_id==1)
    p1Row = pathTable(pathTable.path_id==1,:);
else
    p1Row = pathTable(1,:);
end

% Use tracking Doppler as common wipe, consistent with simple raw-peak check
doppler0 = row.tracking_doppler_hz;
n = (0:length(iq)-1).';
iq = iq .* exp(-1j*2*pi*doppler0*n/cfg.fsHz);

% Build sampled local code
code = gps_ca(cfg.targetPrn);
sampleIndex = (0:N-1).';
codeFreq = row.code_frequency_hz;
chipPhase = mod(sampleIndex * codeFreq / cfg.fsHz, 1023);
chipIndex = floor(chipPhase) + 1;
localCode = code(chipIndex);

% Correlate across integer-sample delays
corrVals = ifft(fft(iq).*conj(fft(localCode)));
profile = abs(corrVals).^2;
profile = profile / max(profile);

delayChip = (0:N-1).' / cfg.samplesPerChip;

% Focus display on first 1 chip
mask = delayChip <= 1.0;
x = delayChip(mask);
y = 10*log10(profile(mask) + eps);

% Peak values at P1/P2 positions
overlay = table();
for k = 1:height(pathTable)
    dchip = pathTable.excess_delay_chip(k);
    dsamp = round(dchip * cfg.samplesPerChip);
    idx = mod(dsamp, N) + 1;
    peakDb = 10*log10(profile(idx) + eps);

    overlay.path_id(k,1) = pathTable.path_id(k);
    overlay.excess_delay_chip(k,1) = dchip;
    overlay.relative_doppler_hz(k,1) = relDopp(k);
    overlay.stage2_relative_power_db(k,1) = pathTable.relative_power_db(k);
    overlay.raw_profile_db(k,1) = peakDb;
end

% Plot
figure('Visible','off');
plot(x,y,'LineWidth',1.2);
hold on;
grid on;

colors = {'r','m'};
for k = 1:height(overlay)
    dchip = overlay.excess_delay_chip(k);
    [~,nearest] = min(abs(x - dchip));
    yp = y(nearest);

    plot(dchip, yp, 'o', 'MarkerSize', 8, 'LineWidth', 1.5);
    txt = sprintf(' P%d | raw %.1f dB | stage2 %.1f dB', ...
        overlay.path_id(k), overlay.raw_profile_db(k), ...
        overlay.stage2_relative_power_db(k));
    text(dchip, yp + 1.0, txt, 'FontSize', 9);
end

xlabel('Delay (chip)');
ylabel('Normalized raw correlation (dB)');
title('G06 Window203 raw correlation with Stage2 P1/P2 overlay');
xlim([0 1.0]);
ylim([-40 5]);

saveas(gcf,fullfile(diagDir,'window203_raw_correlation_overlay.png'));
close;

writetable(overlay,fullfile(diagDir,'window203_raw_correlation_overlay.csv'));

fprintf('Saved:\n');
fprintf('  %s\n',fullfile(diagDir,'window203_raw_correlation_overlay.png'));
fprintf('  %s\n',fullfile(diagDir,'window203_raw_correlation_overlay.csv'));
fprintf('\nInterpretation rule:\n');
fprintf('If P2 lands on a clear local peak above nearby background, it supports a real peak.\n');
fprintf('If P2 does not align with any local peak, Stage2 P2 is more likely a model component than a directly visible peak.\n');

end


function ca = gps_ca(prn)
tap = [ ...
    2 6;3 7;4 8;5 9;1 9;2 10;1 8;2 9; ...
    3 10;2 3;3 4;5 6;6 7;7 8;8 9;9 10; ...
    1 4;2 5;3 6;4 7;5 8;6 9;1 3;4 6; ...
    5 7;6 8;7 9;8 10;1 6;2 7;3 8;4 9];

g1 = -ones(1,10);
g2 = -ones(1,10);
ca = zeros(1023,1);

for i = 1:1023
    ca(i) = g1(10) * g2(tap(prn,1)) * g2(tap(prn,2));
    g1fb = g1(3) * g1(10);
    g2fb = g2(2) * g2(3) * g2(6) * g2(8) * g2(9) * g2(10);
    g1 = [g1fb, g1(1:9)];
    g2 = [g2fb, g2(1:9)];
end
end
