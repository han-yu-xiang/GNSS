function tests = test_audit_gnss_code_domain_cir_pdp
tests = functiontests(localfunctions);
end

function testRecomputesPdpForInterleavedOverlappingWindows(testCase)
fixture = makeFixture(testCase);
result = audit_gnss_code_domain_cir_pdp( ...
    fixture.hdf5_path, fixture.stage0_table);

testCase.verifyEqual(result.snapshot_count, 80);
testCase.verifyEqual(result.window_count, 2);
testCase.verifyTrue(result.pdp_recomputation_pass);
testCase.verifyLessThanOrEqual(result.max_abs_pdp_difference, ...
    result.pdp_relative_tolerance * max(fixture.expected_pdp(:)));
testCase.verifyEqual(result.window_features.window_id, [11; 12]);
testCase.verifyEqual(result.window_features.cir_snapshot_count, [40; 40]);
testCase.verifyEqual(result.window_features.pdp_peak_code_delay_samples, ...
    [-1; 2]);
testCase.verifyEqual(result.window_features.pdp_total_power_relative_units, ...
    sum(fixture.expected_pdp, 2), 'AbsTol', 1e-14);
testCase.verifyFalse(any(result.window_features.pdp_peak_at_grid_boundary));
end

function testRejectsStoredPdpMismatch(testCase)
fixture = makeFixture(testCase);
oldValue = h5read(fixture.hdf5_path, '/pdp_power', [1, 51], [1, 1]);
h5write(fixture.hdf5_path, '/pdp_power', oldValue + 1e-4, [1, 51], [1, 1]);

testCase.verifyError(@() audit_gnss_code_domain_cir_pdp( ...
    fixture.hdf5_path, fixture.stage0_table), ...
    'GNSS:SAGE:GateFPdpMismatch');
end

function testAcceptsOnlyFloatingPointRoundoffInStoredPdp(testCase)
fixture = makeFixture(testCase);
oldValue = h5read(fixture.hdf5_path, '/pdp_power', [1, 51], [1, 1]);
h5write(fixture.hdf5_path, '/pdp_power', ...
    oldValue + 8 * eps(oldValue), [1, 51], [1, 1]);
result = audit_gnss_code_domain_cir_pdp( ...
    fixture.hdf5_path, fixture.stage0_table);

testCase.verifyTrue(result.pdp_recomputation_pass);
testCase.verifyGreaterThan(result.max_abs_pdp_difference, 0);
testCase.verifyLessThanOrEqual(result.max_relative_pdp_difference, ...
    result.pdp_relative_tolerance);
end

function testRejectsMissingOrUnexpectedWindowIdentity(testCase)
fixture = makeFixture(testCase);
badStage0 = fixture.stage0_table;
badStage0.window_id(2) = 99;
testCase.verifyError(@() audit_gnss_code_domain_cir_pdp( ...
    fixture.hdf5_path, badStage0), ...
    'GNSS:SAGE:GateFWindowIdentityMismatch');
end

function testRejectsCirWindowStartOffsetFromStage0(testCase)
fixture = makeFixture(testCase);
windowIds = h5read(fixture.hdf5_path, '/window_id');
starts = h5read(fixture.hdf5_path, '/sample_start_zero_based');
times = h5read(fixture.hdf5_path, '/time_s');
shifted = windowIds == 12;
starts(shifted) = starts(shifted) + 1;
times(shifted) = starts(shifted) ./ 10230000;
h5write(fixture.hdf5_path, '/sample_start_zero_based', starts);
h5write(fixture.hdf5_path, '/time_s', times);

testCase.verifyError(@() audit_gnss_code_domain_cir_pdp( ...
    fixture.hdf5_path, fixture.stage0_table), ...
    'GNSS:SAGE:GateFWindowIdentityMismatch');
end

function testRejectsNonfiniteCirValues(testCase)
fixture = makeFixture(testCase);
h5write(fixture.hdf5_path, '/cir_real', NaN, [7, 101], [1, 1]);
testCase.verifyError(@() audit_gnss_code_domain_cir_pdp( ...
    fixture.hdf5_path, fixture.stage0_table), ...
    'GNSS:SAGE:GateFNonfiniteValue');
end

function testRejectsIncompletePerWindowSnapshotSequence(testCase)
fixture = makeFixture(testCase);
h5write(fixture.hdf5_path, '/snapshot_index_in_window', ...
    uint8(39), [40, 1], [1, 1]);
testCase.verifyError(@() audit_gnss_code_domain_cir_pdp( ...
    fixture.hdf5_path, fixture.stage0_table), ...
    'GNSS:SAGE:GateFSnapshotOrderMismatch');
end

function fixture = makeFixture(testCase)
temporaryRoot = tempname;
mkdir(temporaryRoot);
testCase.addTeardown(@() removeTemporaryDirectory(temporaryRoot));
hdf5Path = fullfile(temporaryRoot, 'interleaved_two_windows.h5');
delaySamples = (-5:0.1:40).';
snapshotCount = 80;
windowIds = [11 * ones(40, 1); 12 * ones(40, 1)];
snapshotIndices = [(1:40).'; (1:40).'];
sampleStarts = [(0:39).' * 10230; (20:59).' * 10230];
sourceRows = (1:snapshotCount).';
[~, order] = sortrows([sampleStarts, windowIds, snapshotIndices], [1, 2, 3]);
sampleStarts = sampleStarts(order);
windowIds = windowIds(order);
snapshotIndices = snapshotIndices(order);
sourceRows = sourceRows(order);
[snapshotGrid, delayGrid] = ndgrid(sourceRows, 1:numel(delaySamples));
cirReal = 0.02 + snapshotGrid .* 1e-4 + delayGrid .* 2e-5;
cirImag = 0.01 + snapshotGrid .* 7e-5 - delayGrid .* 1e-5;
cirReal(windowIds == 11, 41) = cirReal(windowIds == 11, 41) + 0.35;
cirReal(windowIds == 12, 71) = cirReal(windowIds == 12, 71) + 0.3;
cirPower = cirReal .^ 2 + cirImag .^ 2;
expectedPdp = zeros(2, numel(delaySamples));
for windowIndex = 1:2
    rows = windowIds == (10 + windowIndex);
    expectedPdp(windowIndex, :) = mean(cirPower(rows, :), 1);
end

writeDataset(hdf5Path, '/cir_real', cirReal);
writeDataset(hdf5Path, '/cir_imag', cirImag);
writeDataset(hdf5Path, '/time_s', sampleStarts ./ 10230000);
writeDataset(hdf5Path, '/sample_start_zero_based', sampleStarts);
writeDataset(hdf5Path, '/window_id', uint32(windowIds));
writeDataset(hdf5Path, '/snapshot_index_in_window', uint8(snapshotIndices));
writeDataset(hdf5Path, '/raw_iq_rms', ones(snapshotCount, 1));
writeDataset(hdf5Path, '/tracking_doppler_hz', zeros(snapshotCount, 1));
writeDataset(hdf5Path, '/code_frequency_hz', ...
    1023000 * ones(snapshotCount, 1));
writeDataset(hdf5Path, '/cn0_db_hz', 42 * ones(snapshotCount, 1));
writeDataset(hdf5Path, '/nav_symbol', ones(snapshotCount, 1, 'int8'));
writeDataset(hdf5Path, '/nav_symbol_transition_offset_samples', ...
    zeros(snapshotCount, 1, 'int32'));
writeDataset(hdf5Path, '/delay_samples', delaySamples);
writeDataset(hdf5Path, '/pdp_window_id', uint32([11; 12]));
writeDataset(hdf5Path, '/pdp_time_s', [0; 20 / 1000]);
writeDataset(hdf5Path, '/pdp_start_sample_zero_based', [0; 20 * 10230]);
writeDataset(hdf5Path, '/pdp_interval_count', uint8([40; 40]));
writeDataset(hdf5Path, '/pdp_power', expectedPdp);

stage0 = table(uint32([11; 12]), [0; 20 * 10230], [0; 0.02], ...
    'VariableNames', {'window_id', 'sample_start_zero_based', ...
    'recording_time_s'});
fixture = struct('hdf5_path', hdf5Path, ...
    'stage0_table', stage0, 'expected_pdp', expectedPdp);
end

function writeDataset(filename, datasetName, values)
if isvector(values)
    values = values(:);
end
dimensions = size(values);
chunkSize = dimensions;
chunkSize(1) = min(64, dimensions(1));
h5create(filename, datasetName, dimensions, ...
    'Datatype', class(values), 'ChunkSize', chunkSize);
h5write(filename, datasetName, values);
end

function removeTemporaryDirectory(path)
if isfolder(path)
    rmdir(path, 's');
end
end
