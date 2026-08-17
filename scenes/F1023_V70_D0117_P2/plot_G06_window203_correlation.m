% plot_G06_window203_correlation.m
% Plot raw NAV-wiped correlation profile for G06 Window 203
%
% Run in:
% F:\F1023_V70_D0117_P2
%
% Output:
% sage_results\G06_nav_sage_v1\diagnostics\window203_raw_correlation.png

clear; clc;

fprintf('G06 Window 203 correlation diagnostic\n');

rootDir = fileparts(mfilename('fullpath'));

sageDir = fullfile(rootDir,'sage_results','G06_nav_sage_v1');
diagDir = fullfile(sageDir,'diagnostics');

if ~exist(diagDir,'dir')
    mkdir(diagDir);
end

stage0File = fullfile(sageDir,'stage0_nav_catalog.mat');
stage4File = fullfile(sageDir,'stage4_joint_paths.csv');

S = load(stage0File);
windows = S.windowCatalog;
cfg = S.cfg;

paths = readtable(stage4File);

windowID = 203;

idx = find(windows.window_id == windowID,1);

assert(~isempty(idx),'Window 203 not found.');

w = windows(idx,:);

fprintf('Window %d\n',windowID);
fprintf('Time %.6f s\n',w.recording_time_s);

% Raw IQ path
addressCandidates = {
    fullfile(rootDir,'raw','data_address.txt')
    fullfile(rootDir,'data_address.txt')
    };

addressFile = '';
for k=1:length(addressCandidates)
    if exist(addressCandidates{k},'file')
        addressFile = addressCandidates{k};
        break;
    end
end

assert(~isempty(addressFile),'data_address.txt not found');

rawFile = strtrim(fileread(addressFile));

fprintf('Raw IQ: %s\n',rawFile);

% Read 40 ms IQ
N = cfg.samplesPer40Ms;

fid=fopen(rawFile,'rb','ieee-le');
assert(fid>0,'Cannot open IQ file');

fseek(fid,double(w.sample_start_zero_based)*4,'bof');

raw=fread(fid,2*N,'int16=>double');

fclose(fid);

iq=complex(raw(1:2:end),raw(2:2:end));

% Remove navigation bit
split=w.split_samples;

iq(1:split)=w.nav_symbol_1*iq(1:split);
iq(split+1:end)=w.nav_symbol_2*iq(split+1:end);

iq=iq-mean(iq);
iq=iq/sqrt(mean(abs(iq).^2));


% Generate GPS C/A code
prn=cfg.targetPrn;

code=gps_ca(prn);

samples=(0:N-1).';

chipRate=cfg.nominalCodeRateHz;

chipIndex=floor(mod(samples*chipRate/cfg.fsHz,1023))+1;

localCode=code(chipIndex);


% Doppler compensation using Path1
p=paths(paths.center_window_id==windowID,:);

doppler=p.doppler_hz(1);

iq=iq.*exp(-1j*2*pi*doppler*samples/cfg.fsHz);


% Correlation
corr=ifft(fft(iq).*conj(fft(localCode)));

profile=abs(corr);

profile=profile/max(profile);

delayChip=(0:N-1)'/N*1023;


% Plot
figure('Visible','off');

plot(delayChip,20*log10(profile+eps),'LineWidth',1.2);

xlabel('Delay (chip)');
ylabel('Normalized correlation (dB)');
title('G06 Window 203 NAV-wiped correlation');

grid on;
xlim([0 3]);

ylim([-40 5]);

hold on;

for k=1:height(p)

    x=p.excess_delay_chips(k);

    plot(x,0,'ro','MarkerSize',8);

    text(x,-3,sprintf('P%d',p.path_id(k)));

end


saveas(gcf,fullfile(diagDir,...
    'window203_raw_correlation.png'));

close;

fprintf('Saved: %s\n',...
    fullfile(diagDir,'window203_raw_correlation.png'));


function ca=gps_ca(prn)

taps=[
2 6;3 7;4 8;5 9;1 9;2 10;1 8;2 9;
3 10;2 3;3 4;5 6;6 7;7 8;8 9;9 10;
1 4;2 5;3 6;4 7;5 8;6 9;1 3;4 6;
5 7;6 8;7 9;8 10;1 6;2 7;3 8;4 9];

g1=-ones(1,10);
g2=-ones(1,10);

ca=zeros(1023,1);

for i=1:1023

    ca(i)=g1(10)*g2(taps(prn,1))*g2(taps(prn,2));

    g1fb=g1(3)*g1(10);
    g2fb=g2(2)*g2(3)*g2(6)*g2(8)*g2(9)*g2(10);

    g1=[g1fb g1(1:9)];
    g2=[g2fb g2(1:9)];

end

end
