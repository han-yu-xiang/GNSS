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



