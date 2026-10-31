function tests = test_mainline_stage2_path_csv_schema
tests = functiontests(localfunctions);
end

function testMissingCsvAttributeColumnIsRejected(testCase)
tmp = tempname;
mkdir(tmp);
cleanup = onCleanup(@() rmdir(tmp, 's')); %#ok<NASGU>
[stage2Run, csvTable] = makeFixture();
csvTable.relative_power_db = [];
csvPath = fullfile(tmp, 'stage2_selected_paths.csv');
writetable(csvTable, csvPath);

testCase.verifyError(@() verify_mainline_stage2_path_csv_attributes( ...
    csvPath, stage2Run), ...
    'GNSS:SAGE:GateEStage2CsvSchemaMismatch');
end

function testMissingLedgerAttributeColumnIsRejected(testCase)
tmp = tempname;
mkdir(tmp);
cleanup = onCleanup(@() rmdir(tmp, 's')); %#ok<NASGU>
[stage2Run, csvTable] = makeFixture();
stage2Run.relative_power_db = [];
csvPath = fullfile(tmp, 'stage2_selected_paths.csv');
writetable(csvTable, csvPath);

testCase.verifyError(@() verify_mainline_stage2_path_csv_attributes( ...
    csvPath, stage2Run), ...
    'GNSS:SAGE:GateEStage2CsvSchemaMismatch');
end

function testCompleteSchemaAndMatchingAttributesPass(testCase)
tmp = tempname;
mkdir(tmp);
cleanup = onCleanup(@() rmdir(tmp, 's')); %#ok<NASGU>
[stage2Run, csvTable] = makeFixture();
csvPath = fullfile(tmp, 'stage2_selected_paths.csv');
writetable(csvTable, csvPath);

result = verify_mainline_stage2_path_csv_attributes(csvPath, stage2Run);
testCase.verifyEqual(result.status, "PASS");
testCase.verifyLessThanOrEqual(result.max_abs_attribute_difference, 1e-12);
end

function [stage2Run, csvTable] = makeFixture()
stage2Run = table(repmat("run_a", 2, 1), [7; 7], [1; 2], ...
    [0; 1], [0; 0.75], [0; 1.25], [0; -50], ...
    [0; -3.010299956639812], ...
    'VariableNames', {'run_id', 'window_id', 'path_id', ...
    'is_multipath', 'delay_samples', 'excess_delay_samples', ...
    'doppler_offset_hz', 'relative_power_db'});
csvTable = table([7; 7], [1; 2], [0; 1], [0; 0.75], ...
    [0; 1.25], [0; -50], [0; -3.010299956639812], ...
    'VariableNames', {'window_id', 'path_id', 'is_multipath', ...
    'delay_samples', 'excess_delay_samples', 'doppler_offset_hz', ...
    'relative_power_db'});
end
