function assert_wp5_ledger_rows_equal(expected, actual, actualRows, context)
%ASSERT_WP5_LEDGER_ROWS_EQUAL Compare every per-run ledger column to combined.
context = char(string(context));
assert(height(expected) == numel(actualRows) ...
    && all(actualRows >= 1) && all(actualRows <= height(actual)) ...
    && isequal(expected.Properties.VariableNames, ...
        actual.Properties.VariableNames), ...
    'GNSS:WP5:ValidationLedgerColumnMismatch', ...
    '%s ledger row count or column schema differs.', context);

for k = 1:numel(expected.Properties.VariableNames)
    name = expected.Properties.VariableNames{k};
    left = expected.(name);
    column = actual.(name);
    right = column(actualRows, :);
    if isnumeric(left) && isnumeric(right)
        same = (left == right) | (isnan(left) & isnan(right));
        finitePair = isfinite(left) & isfinite(right);
        same = same | (finitePair & abs(left - right) <= 1e-12);
        equal = all(same(:));
    else
        equal = isequaln(left, right);
    end
    assert(equal, 'GNSS:WP5:ValidationLedgerColumnMismatch', ...
        '%s ledger column %s differs between per-run and combined output.', ...
        context, name);
end
end
