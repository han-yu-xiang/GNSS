% analyze_G06_events.m
% G06 SAGE diagnostic V2
% Compatible with current stage4_joint_paths.csv

clear; clc;

fprintf('G06 SAGE diagnostic analysis V2\n');

rootDir = fileparts(mfilename('fullpath'));
sageDir = fullfile(rootDir,'sage_results','G06_nav_sage_v1');
outDir = fullfile(sageDir,'diagnostics');

if ~exist(outDir,'dir')
    mkdir(outDir);
end

stage4File = fullfile(sageDir,'stage4_joint_paths.csv');
summaryFile = fullfile(sageDir,'stage4_joint_summary.csv');

paths = readtable(stage4File);
summary = readtable(summaryFile);

fprintf('Loaded Stage4 paths: %d\n',height(paths));
fprintf('\n===== Reliable events =====\n');
disp(summary);

%% Check required columns
requiredPaths = {
    'center_window_id'
    'path_id'
    'excess_delay_chips'
    'mean_relative_power_db'
    'doppler_offset_hz'
    };

for i=1:length(requiredPaths)
    assert(ismember(requiredPaths{i},paths.Properties.VariableNames), ...
        'Missing column: %s',requiredPaths{i});
end

%% Plot delay-power distribution
figure('Visible','off');

scatter(paths.excess_delay_chips,...
    paths.mean_relative_power_db,...
    80,'filled');

xlabel('Excess delay (chip)');
ylabel('Relative power (dB)');
title('G06 Stage4 path delay-power');

grid on;

saveas(gcf,...
    fullfile(outDir,'stage4_delay_power.png'));

close;

%% Plot each event separately

events = unique(paths.center_window_id);

for k=1:length(events)

    eventID = events(k);
    p = paths(paths.center_window_id==eventID,:);

    figure('Visible','off');

    scatter(p.excess_delay_chips,...
        p.mean_relative_power_db,...
        100,'filled');

    hold on;

    for j=1:height(p)
        text(p.excess_delay_chips(j),...
            p.mean_relative_power_db(j),...
            sprintf(' P%d',p.path_id(j)));
    end

    xlabel('Excess delay (chip)');
    ylabel('Relative power (dB)');
    title(sprintf('Window %d path distribution',eventID));

    grid on;

    saveas(gcf,...
        fullfile(outDir,...
        sprintf('window_%d_delay_power.png',eventID)));

    close;

end


%% Export simplified diagnostic table

diagnostic = paths(:,{
    'center_window_id',...
    'path_id',...
    'is_multipath',...
    'excess_delay_chips',...
    'doppler_offset_hz',...
    'mean_relative_power_db'});

writetable(diagnostic,...
    fullfile(outDir,'G06_path_power_diagnostic.csv'));


%% Tracking C/N0

trackFile = fullfile(rootDir,...
    'GNSS-SDR_Res',...
    'tracking',...
    'F1023_V70_D0117_P2_track_ch_4.mat');

if exist(trackFile,'file')

    S = load(trackFile);

    fprintf('\nTracking variables:\n');
    disp(fieldnames(S));

    candidates = {
        'CN0_SNV_dB_Hz'
        'CN0_dB_Hz'
        'CN0'
        };

    found = false;

    for i=1:length(candidates)
        if isfield(S,candidates{i})
            cn0=S.(candidates{i});
            fprintf('Using %s\n',candidates{i});
            fprintf('Median C/N0 %.2f dB-Hz\n',median(cn0));

            figure('Visible','off');
            plot(cn0);
            xlabel('Sample');
            ylabel('C/N0 (dB-Hz)');
            title('G06 tracking C/N0');
            grid on;

            saveas(gcf,...
                fullfile(outDir,'G06_CN0.png'));

            close;

            found=true;
            break;
        end
    end

    if ~found
        fprintf('No C/N0 variable found.\n');
    end

end


%% Elevation

elevFile = fullfile(rootDir,...
    'satellite',...
    'F1023_V70_D0117_P2_satellite_elevation_timeseries.csv');

if exist(elevFile,'file')

    elev=readtable(elevFile);

    fprintf('\nElevation columns:\n');
    disp(elev.Properties.VariableNames);

    if ismember('prn',elev.Properties.VariableNames)

        g06=elev(strcmp(string(elev.prn),'G06'),:);

        fprintf('G06 elevation records: %d\n',height(g06));

        writetable(g06,...
            fullfile(outDir,'G06_elevation.csv'));

    end

end


fprintf('\nDiagnostic finished.\n');
fprintf('Output: %s\n',outDir);
