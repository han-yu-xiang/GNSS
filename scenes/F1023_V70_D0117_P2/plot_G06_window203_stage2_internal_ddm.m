function plot_G06_window203_stage2_internal_ddm
% G06 Window203 Stage2 internal diagnostic
%
% This script uses the actual Stage2 saved results:
%   sage_results/G06_nav_sage_v1/stage2_nav_sage_L1_L4.mat
%
% It extracts the selected Stage2 model for window 203 and plots:
%   delay (chip) - relative Doppler - path locations
%
% It does NOT reimplement a simplified correlator.

clear; clc;

fprintf('G06 Window203 Stage2 internal DDM diagnostic\n');

rootDir=fileparts(mfilename('fullpath'));
resultDir=fullfile(rootDir,'sage_results','G06_nav_sage_v1');

stage2File=fullfile(resultDir,'stage2_nav_sage_L1_L4.mat');

assert(isfile(stage2File),...
    'Missing Stage2 result: %s',stage2File);

loaded=load(stage2File,'stage2Fits');

fits=loaded.stage2Fits;

target=[];

for k=1:numel(fits)

    if isempty(fits{k})
        continue;
    end

    if fits{k}.windowId==203
        target=fits{k};
        break;
    end

end

assert(~isempty(target),...
    'Window 203 not found in Stage2 results');

fprintf('Found Window203\n');
fprintf('Selected L = %d\n',target.selectedOrder);


model=target.models{target.selectedOrder};

paths=model.paths;


delay=[];
doppler=[];
power=[];


for k=1:numel(paths)

    delay(k)=paths(k).delaySamples;
    doppler(k)=paths(k).dopplerHz;

    power(k)=model.relativePowerDb(k);

end


% convert delay to excess chip
delay=delay-delay(1);

cfg=load(stage2File,'cfg');

if isfield(cfg,'cfg')
    samplesPerChip=cfg.cfg.samplesPerChip;
else
    samplesPerChip=10;
end


delayChip=delay/samplesPerChip;

relativeDoppler=doppler-doppler(1);


figure('Visible','off');

scatter(delayChip,relativeDoppler,...
    120,power,'filled');

grid on;
colorbar;

xlabel('Excess delay (chip)');
ylabel('Relative Doppler (Hz)');

title(sprintf('G06 Window203 Stage2 SAGE paths L=%d', ...
    target.selectedOrder));


for k=1:numel(paths)

    text(delayChip(k),relativeDoppler(k),...
        sprintf(' P%d',k));

end


outDir=fullfile(resultDir,'diagnostics');

if ~isfolder(outDir)
    mkdir(outDir);
end


saveas(gcf,...
    fullfile(outDir,...
    'window203_stage2_internal_paths.png'));

close;


T=table((1:numel(paths))',...
    delayChip',...
    relativeDoppler',...
    power',...
    'VariableNames',...
    {'path_id','excess_delay_chip',...
    'relative_doppler_hz','relative_power_db'});


writetable(T,...
    fullfile(outDir,...
    'window203_stage2_internal_paths.csv'));


fprintf('Saved diagnostic files.\n');

end
