function result = verify_mainline_stage2_path_csv_attributes(csvPath, stage2Run)
%VERIFY_MAINLINE_STAGE2_PATH_CSV_ATTRIBUTES Compare source and ledger rows.
t = readtable(csvPath, 'Delimiter', ',', 'ReadVariableNames', true, ...
    'TextType', 'string', 'VariableNamingRule', 'preserve');
attributeFields = {'is_multipath', 'delay_samples', ...
    'excess_delay_samples', 'doppler_offset_hz', 'relative_power_db'};
requiredCsvFields = [{'window_id', 'path_id'}, attributeFields];
requiredLedgerFields = [{'run_id', 'window_id', 'path_id'}, ...
    attributeFields];
missingCsvFields = requiredCsvFields(~ismember( ...
    requiredCsvFields, t.Properties.VariableNames));
missingLedgerFields = requiredLedgerFields(~ismember( ...
    requiredLedgerFields, stage2Run.Properties.VariableNames));
assert(isempty(missingCsvFields) && isempty(missingLedgerFields), ...
    'GNSS:SAGE:GateEStage2CsvSchemaMismatch', ...
    'Required columns missing (source CSV: %s; Stage2 ledger: %s).', ...
    strjoin(missingCsvFields, ', '), strjoin(missingLedgerFields, ', '));
csvKey = pathKey(repmat(string(stage2Run.run_id(1)), height(t), 1), ...
    t.window_id, t.path_id);
ledgerKey = pathKey(stage2Run.run_id, stage2Run.window_id, ...
    stage2Run.path_id);
result = struct('status', "FAIL", ...
    'max_abs_attribute_difference', NaN);
if height(t) ~= height(stage2Run) || ...
        numel(unique(csvKey)) ~= height(t) || ...
        ~isequal(sort(csvKey), sort(ledgerKey))
    return;
end
[~, idx] = ismember(csvKey, ledgerKey);
dmax = 0;
for k = 1:numel(attributeFields)
    f = attributeFields{k};
    a = doubleColumn(t.(f));
    b = stage2Run.(f);
    b = doubleColumn(b(idx));
    finite = isfinite(a) & isfinite(b);
    if ~all(finite) || any(abs(a - b) > 1e-12)
        return;
    end
    if any(finite)
        dmax = max(dmax, max(abs(a(finite) - b(finite))));
    end
end
result.status = "PASS";
result.max_abs_attribute_difference = dmax;
end

function key = pathKey(run, window, pathid)
key = string(run(:)) + "|" + string(doubleColumn(window)) + "|" + ...
    string(doubleColumn(pathid));
end

function x = doubleColumn(x)
if iscell(x)
    x = string(x);
end
if isstring(x) || ischar(x) || iscategorical(x)
    x = str2double(string(x));
end
x = double(x(:));
end
