import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_sage_database_dry_run import (  # noqa: E402
    classify_run_label,
    reference_count_key,
    request_hash_key,
    strict_confirmation,
)


class Stage4RuleTests(unittest.TestCase):
    def test_strict_confirmation_requires_valid_summary_and_multipath_path(self):
        summary = {"joint_valid": "1", "joint_multipath_count": "1"}
        paths = [{"is_multipath": "0"}, {"is_multipath": "1"}]

        confirmed, issues = strict_confirmation(summary, paths)

        self.assertTrue(confirmed)
        self.assertEqual(issues, [])

    def test_strict_confirmation_rejects_summary_path_count_mismatch(self):
        summary = {"joint_valid": "1", "joint_multipath_count": "2"}
        paths = [{"is_multipath": "0"}, {"is_multipath": "1"}]

        confirmed, issues = strict_confirmation(summary, paths)

        self.assertFalse(confirmed)
        self.assertIn("joint_multipath_count_mismatch", issues)

    def test_zero_confirmed_event_is_not_los_reference(self):
        self.assertEqual(
            classify_run_label(0, run_scope="standard", reference_control=False),
            "no_confirmed_event",
        )
        self.assertEqual(
            classify_run_label(0, run_scope="reference", reference_control=True),
            "los_reference",
        )

    def test_reference_regression_keys_map_to_stage_counts(self):
        self.assertEqual(reference_count_key("selected_windows"), "stage2_selected")
        self.assertEqual(reference_count_key("l_ge_2"), "stage2_l_ge_2")
        self.assertEqual(reference_count_key("l_ge_3"), "stage2_l_ge_3")
        self.assertEqual(reference_count_key("stage3_centers"), "stage3_reliable_centers")

    def test_request_hash_keys_use_immutable_request_field_names(self):
        self.assertEqual(request_hash_key("manifest_sha256"), "production_manifest_sha256")
        self.assertEqual(request_hash_key("inventory_sha256"), "production_inventory_sha256")
        self.assertEqual(request_hash_key("executor_sha256"), "python_executor_sha256")


if __name__ == "__main__":
    unittest.main()
