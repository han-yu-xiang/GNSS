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




