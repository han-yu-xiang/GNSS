function tests = test_assert_wp5_ledger_rows_equal
tests = functiontests(localfunctions);
end

function testAcceptsEqualRowsIncludingMissingNumericValues(testCase)
expected = fixtureTable();
actual = expected;
assert_wp5_ledger_rows_equal(expected, actual, 1:2, 'fixture');
testCase.verifyTrue(true);
end

function testRejectsChangedStage4OrModelingAttribute(testCase)
expected = fixtureTable();
actual = expected;
actual.stage4_mapping_status(2) = "MAPPED";
testCase.verifyError(@() assert_wp5_ledger_rows_equal( ...
    expected, actual, 1:2, 'fixture'), ...
    'GNSS:WP5:ValidationLedgerColumnMismatch');
end

function expected = fixtureTable()
expected = table([1; 2], [NaN; 0.5], ["DIRECT_PATH"; "MPC"], ...
    ["UNMAPPED"; "NOT_APPLICABLE"], ...
    'VariableNames', {'window_id', 'alpha_real', 'modeling_class', ...
    'stage4_mapping_status'});
end
