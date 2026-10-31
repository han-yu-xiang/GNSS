import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import audit_mainline_1023_stage2_cohort as audit


class AuditApiTests(unittest.TestCase):
    def test_required_validation_functions_are_exposed(self):
        self.assertTrue(callable(getattr(audit, "validate_stage2_selected_paths", None)))
        self.assertTrue(callable(getattr(audit, "count_stage4_confirmed_paths", None)))

    def test_prn_labels_are_parsed_as_labels_not_plain_integers(self):
        self.assertEqual(6, audit.parse_prn_number("G06", "summary.prn"))
        self.assertEqual(28, audit.parse_prn_number("28", "receipt.prn"))

    def test_helper_validation_errors_fail_the_task_audit(self):
        collector = audit.Collector()
        start = len(collector.errors)
        collector.add("ERROR", "duplicate_or_blank_key", "run-x", "stage2_selected_paths.csv")
        status, codes = audit.summarize_task_errors(collector.errors, start)
        self.assertEqual("FAIL", status)
        self.assertEqual(["duplicate_or_blank_key"], codes)

    def test_no_new_task_errors_pass(self):
        collector = audit.Collector()
        status, codes = audit.summarize_task_errors(collector.errors, 0)
        self.assertEqual("PASS", status)
        self.assertEqual([], codes)

    def test_manifest_summary_identity_mismatch_is_reported(self):
        mismatches = audit.identity_mismatch_fields(
            {"scene_id": "scene-a", "prn": "G06", "tracking_channel": "1"},
            {"scene_id": "scene-a", "prn": "G07", "tracking_channel": "1"},
        )
        self.assertEqual(["prn"], mismatches)

    def test_noneligible_statuses_never_enter_the_candidate_partition(self):
        rows = [
            {"run_id": "done", "execution_status": "COMPLETE"},
            {"run_id": "pilot", "execution_status": "ALREADY_COMPLETE"},
            {"run_id": "pending", "execution_status": "PENDING"},
            {"run_id": "failed", "execution_status": "FAILED"},
        ]
        eligible, excluded = audit.partition_summary_rows(rows)
        self.assertEqual({"done", "pilot"}, {row["run_id"] for row in eligible})
        self.assertEqual({"pending", "failed"}, {row["run_id"] for row in excluded})

    def test_missing_receipt_is_not_treated_as_present(self):
        with TemporaryDirectory() as temp_dir:
            self.assertFalse(audit.required_receipt_present(Path(temp_dir) / "missing.json"))

    def test_missing_elevation_join_is_left_missing_without_imputation(self):
        self.assertIsNone(audit.lookup_scene_prn_elevation("scene-a", "G06", {}))

    def test_expected_invalid_model_infinity_is_not_reported_as_corruption(self):
        collector = audit.Collector()
        audit.check_numeric_cells(
            "stage2_model_orders.csv",
            [{"model_valid": "0", "rss": "inf", "bic": "inf"}],
            "run-x",
            collector,
        )
        self.assertEqual([], collector.errors)

    def test_infinity_in_valid_model_is_reported(self):
        collector = audit.Collector()
        audit.check_numeric_cells(
            "stage2_model_orders.csv",
            [{"model_valid": "1", "rss": "inf"}],
            "run-x",
            collector,
        )
        self.assertEqual(["infinite_numeric_value"], [item["code"] for item in collector.errors])


@unittest.skipUnless(callable(getattr(audit, "validate_stage2_selected_paths", None)), "audit API not implemented")
class Stage2PathAuditTests(unittest.TestCase):
    def test_valid_path_rows_conserve_direct_and_multipath_counts(self):
        rows = [
            {"window_id": "1", "path_id": "1", "is_multipath": "0"},
            {"window_id": "2", "path_id": "1", "is_multipath": "0"},
            {"window_id": "2", "path_id": "2", "is_multipath": "1"},
        ]
        issues = audit.validate_stage2_selected_paths(rows, 3, 2, 1)
        self.assertEqual([], issues)

    def test_duplicate_window_path_key_is_reported(self):
        rows = [
            {"window_id": "1", "path_id": "1", "is_multipath": "0"},
            {"window_id": "1", "path_id": "1", "is_multipath": "0"},
        ]
        issues = audit.validate_stage2_selected_paths(rows, 2, 2, 0)
        self.assertIn("duplicate_window_path_key", issues)

    def test_path_count_imbalance_is_reported(self):
        rows = [{"window_id": "1", "path_id": "1", "is_multipath": "0"}]
        issues = audit.validate_stage2_selected_paths(rows, 2, 1, 1)
        self.assertIn("stage2_selected_path_count_mismatch", issues)


@unittest.skipUnless(callable(getattr(audit, "count_stage4_confirmed_paths", None)), "audit API not implemented")
class Stage4ConfirmationTests(unittest.TestCase):
    def test_empty_stage4_outputs_are_a_legal_zero_confirmation_case(self):
        self.assertEqual(0, audit.count_stage4_confirmed_paths([], [], [], []))

    def test_only_strictly_confirmed_multipath_rows_are_counted(self):
        summaries = [
            {"center_window_id": "10", "joint_selected_L": "3", "joint_valid": "1", "joint_multipath_count": "2"},
            {"center_window_id": "20", "joint_selected_L": "2", "joint_valid": "1", "joint_multipath_count": "0"},
            {"center_window_id": "30", "joint_selected_L": "2", "joint_valid": "0", "joint_multipath_count": "1"},
        ]
        paths = [
            {"center_window_id": "10", "joint_selected_L": "2", "path_id": "1", "is_multipath": "0"},
            {"center_window_id": "10", "joint_selected_L": "2", "path_id": "2", "is_multipath": "1"},
            {"center_window_id": "10", "joint_selected_L": "2", "path_id": "3", "is_multipath": "1"},
            {"center_window_id": "20", "joint_selected_L": "2", "path_id": "2", "is_multipath": "1"},
            {"center_window_id": "30", "joint_selected_L": "2", "path_id": "2", "is_multipath": "1"},
        ]
        stage3 = [
            {"center_window_id": "10", "multipath_id": "1", "persistence_pass": "1"},
            {"center_window_id": "10", "multipath_id": "2", "persistence_pass": "1"},
            {"center_window_id": "20", "multipath_id": "1", "persistence_pass": "1"},
            {"center_window_id": "30", "multipath_id": "1", "persistence_pass": "1"},
        ]
        stage2 = [
            {"window_id": "10", "path_id": "2", "is_multipath": "1"},
            {"window_id": "10", "path_id": "3", "is_multipath": "1"},
            {"window_id": "20", "path_id": "2", "is_multipath": "1"},
            {"window_id": "30", "path_id": "2", "is_multipath": "1"},
        ]
        self.assertEqual(2, audit.count_stage4_confirmed_paths(stage3, stage2, summaries, paths))


if __name__ == "__main__":
    unittest.main()
