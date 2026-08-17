"""Regression tests for the MATLAB recovery-comparator contract.

These tests are intentionally MATLAB-free.  They exercise the table-name
normalization contract with the two MATLAB representations observed across
versions and statically guard the local-MATLAB implementation against the
original cell-valued dynamic-indexing bug.
"""

from pathlib import Path
import ntpath
import unittest


ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "scripts" / "sage_pipeline" / "regression" / "run_production_recovery_regression.m"


def normalize_names(value):
    """Model the MATLAB helper's canonical row-of-char representation."""
    if isinstance(value, str):
        return [value]
    normalized = []
    for item in value:
        if isinstance(item, (list, tuple)):
            if len(item) != 1:
                raise TypeError("non-scalar dynamic table name")
            item = item[0]
        if not isinstance(item, str) or not item:
            raise TypeError("unsupported dynamic table name")
        normalized.append(item)
    return normalized


def compare_fixture(baseline_names, actual_names, baseline_data, actual_data):
    """Small semantic fixture for schema/data PASS/FAIL behavior."""
    left_names = normalize_names(baseline_names)
    right_names = normalize_names(actual_names)
    if left_names != right_names:
        return False
    return all(baseline_data[name] == actual_data[name] for name in left_names)


def canonical_windows_path(value):
    """Small Windows-only model for the containment boundary tests."""
    value = value.replace("/", "\\")
    return ntpath.normpath(value)


def path_within_root(candidate, root):
    candidate = canonical_windows_path(candidate)
    root = canonical_windows_path(root)
    if not ntpath.isabs(candidate) or not ntpath.isabs(root):
        return False
    prefix = root if root.endswith("\\") else root + "\\"
    return ntpath.normcase(candidate) == ntpath.normcase(root) or candidate.lower().startswith(
        prefix.lower()
    )


AGGREGATE_FIELDS = (
    "row_count_pass",
    "schema_pass",
    "required_columns_pass",
    "exact_pass",
    "categorical_pass",
    "numeric_pass",
)


def aggregate_pass(record):
    """Model the required all-components comparator aggregate."""
    return all(record[field] for field in AGGREGATE_FIELDS)


class ProductionRecoveryComparatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = HARNESS.read_text(encoding="utf-8")

    def test_cell_array_variable_names_are_scalarized(self):
        self.assertEqual(normalize_names(["window_id", "value"]), ["window_id", "value"])
        self.assertIn("scalarTableVariableName(exactNames{nameIndex})", self.text)
        self.assertIn("scalarTableVariableName(baselineNames{nameIndex})", self.text)

    def test_string_array_variable_names_are_normalized(self):
        self.assertEqual(normalize_names(("window_id", "value")), ["window_id", "value"])
        self.assertIn("if isstring(value)", self.text)
        self.assertIn("names = cellstr(reshape(value, 1, []));", self.text)

    def test_different_columns_fail(self):
        self.assertFalse(
            compare_fixture(
                ["window_id", "value"],
                ["window_id", "other"],
                {"window_id": [1], "value": [2]},
                {"window_id": [1], "other": [2]},
            )
        )

    def test_same_names_and_data_pass(self):
        self.assertTrue(
            compare_fixture(
                ["window_id", "value"],
                ("window_id", "value"),
                {"window_id": [1], "value": [2]},
                {"window_id": [1], "value": [2]},
            )
        )

    def test_same_names_and_different_data_fail(self):
        self.assertFalse(
            compare_fixture(
                ["window_id", "value"],
                ("window_id", "value"),
                {"window_id": [1], "value": [2]},
                {"window_id": [1], "value": [3]},
            )
        )

    def test_dynamic_indexing_contract_is_scalar(self):
        self.assertIn("function name = scalarTableVariableName(value)", self.text)
        self.assertIn("name = char(value);", self.text)
        self.assertIn("elseif ischar(value)", self.text)
        self.assertNotIn(
            "for name = reshape(baseline.Properties.VariableNames, 1, [])", self.text
        )
        self.assertNotIn("for name = reshape(exactNames, 1, [])", self.text)

    def test_existing_output_mode_is_explicitly_read_only(self):
        self.assertIn('addParameter(parser, "CompareExistingActualDir"', self.text)
        self.assertIn('comparison_mode", comparisonMode', self.text)
        self.assertIn('comparisonMode = "existing_output_read_only"', self.text)
        self.assertIn('"raw_iq_opened", false', self.text)
        self.assertIn('"sage_executed", false', self.text)
        self.assertIn("validateActualContext", self.text)

    def test_windows_path_containment_pass_cases(self):
        root = r"E:\root\darkroom"
        self.assertTrue(path_within_root(r"E:\root\darkroom\x", root))
        self.assertTrue(path_within_root(r"E:/root/darkroom/x", root))
        self.assertTrue(path_within_root(r"e:/ROOT/DARKROOM/x", root))
        self.assertTrue(path_within_root(root, root))

    def test_windows_path_containment_fail_cases(self):
        root = r"E:\root\darkroom"
        self.assertFalse(path_within_root(r"E:\root\darkroom2\x", root))
        self.assertFalse(path_within_root(r"E:\root\other\x", root))
        self.assertFalse(path_within_root(r"E:\root\darkroom\..\other", root))
        self.assertFalse(path_within_root(r"..\other", root))
        self.assertFalse(path_within_root(r"D:\root\darkroom\x", root))

    def test_matlab_path_fix_canonicalizes_and_bounds_prefix(self):
        self.assertIn("canonicalWindowsPath(candidatePath)", self.text)
        self.assertIn("canonicalWindowsPath(rootPath)", self.text)
        self.assertIn("java.io.File", self.text)
        self.assertIn("strcmpi(candidate, root)", self.text)
        self.assertIn("rootWithSeparator", self.text)
        self.assertIn("trimWindowsTrailingSeparators", self.text)

    def test_aggregate_pass_all_components_pass(self):
        record = {field: True for field in AGGREGATE_FIELDS}
        self.assertTrue(aggregate_pass(record))

    def test_aggregate_pass_any_required_component_fails(self):
        for field in AGGREGATE_FIELDS:
            record = {name: True for name in AGGREGATE_FIELDS}
            record[field] = False
            self.assertFalse(aggregate_pass(record), field)

    def test_matlab_aggregate_and_schema_outputs_are_explicit(self):
        self.assertIn("record.overall_pass = record.row_count_pass", self.text)
        self.assertIn("record.pass = record.overall_pass", self.text)
        self.assertIn("writeSchemaComparisonCsv", self.text)
        self.assertIn('"missing_in_actual"', self.text)
        self.assertIn('"extra_in_actual"', self.text)
        self.assertIn('"types_equal"', self.text)
        self.assertIn("confirmedEventPathIdentity", self.text)


if __name__ == "__main__":
    unittest.main()
