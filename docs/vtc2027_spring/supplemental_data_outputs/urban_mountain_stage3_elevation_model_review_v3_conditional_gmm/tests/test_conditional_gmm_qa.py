from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ConditionalGMMIndependentQATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads((ROOT / "qa/independent_qa_result.json").read_text(encoding="utf-8"))

    def test_independent_qa_is_pass_with_limitations(self) -> None:
        self.assertEqual(self.result["status"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(self.result["hard_failures"], [])

    def test_selected_model_has_six_conditioned_cells(self) -> None:
        self.assertEqual(self.result["counts"]["conditioned_cells"], 6)
        self.assertEqual(self.result["counts"]["primary_rows"], 518)
        self.assertEqual(self.result["counts"]["cell_ready_rows"], 487)

    def test_missing_elevation_rows_are_not_imputed(self) -> None:
        self.assertEqual(self.result["counts"]["missing_elevation_rows"], 31)
        self.assertEqual(self.result["support_status"]["Urban__LOW"], "STRONGLY_PARTIALLY_POOLED")
        self.assertEqual(self.result["support_status"]["Mountain/Valley__LOW"], "STRONGLY_PARTIALLY_POOLED")
        self.assertEqual(self.result["support_status"]["Mountain/Valley__HIGH"], "STRONGLY_PARTIALLY_POOLED")

    def test_model_and_validation_counts_are_complete(self) -> None:
        self.assertEqual(self.result["counts"]["candidate_rows"], 12)
        self.assertEqual(self.result["counts"]["scene_loso_rows"], 108)
        self.assertEqual(self.result["counts"]["model_bootstrap_rows"], 12000)
        self.assertEqual(self.result["counts"]["paired_bootstrap_rows"], 2000)
        self.assertEqual(self.result["counts"]["review_draw_rows"], 24576)

    def test_scientific_boundary_check_passed(self) -> None:
        self.assertEqual(self.result["checks"]["scientific_boundary_language"]["status"], "PASS")
        self.assertFalse(self.result["execution_boundary"]["formal_manuscript_modified"])
        self.assertFalse(self.result["execution_boundary"]["stage4_source_used"])


if __name__ == "__main__":
    unittest.main()
