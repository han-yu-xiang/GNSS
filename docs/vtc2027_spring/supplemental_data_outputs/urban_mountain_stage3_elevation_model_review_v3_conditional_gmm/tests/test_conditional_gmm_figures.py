from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ConditionalGMMFigureArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((ROOT / "qa/output_manifest.json").read_text(encoding="utf-8"))

    def test_main_figure_contains_six_cells(self) -> None:
        figure = self.manifest["figures"]["conditional_joint_environment_elevation"]
        self.assertEqual(figure["panel_count"], 6)
        self.assertEqual(figure["cell_ready_rows"], 487)
        self.assertTrue((ROOT / figure["path"]).exists())

    def test_corner_pages_and_heatmap_are_complete(self) -> None:
        self.assertEqual(self.manifest["figures"]["corner_diagnostic_pages"]["page_count"], 6)
        self.assertEqual(self.manifest["figures"]["corner_diagnostic_pages"]["cdf_panels"], 0)
        heatmap = self.manifest["figures"]["conditional_component_weight_heatmap"]
        self.assertEqual(heatmap["panel_count"], 6)
        self.assertTrue((ROOT / heatmap["path"]).exists())
        self.assertEqual(len(list((ROOT / "figures").glob("corner_diagnostic_*.png"))), 6)

    def test_parameter_curve_figure_is_present(self) -> None:
        curve = self.manifest["figures"]["conditional_parameter_curves_vs_elevation"]
        self.assertEqual(curve["panel_count"], 3)
        self.assertTrue((ROOT / curve["path"]).exists())

    def test_pdf_figure_contains_six_environment_elevation_panels(self) -> None:
        pdf = self.manifest["figures"]["conditional_marginal_pdf_environment_elevation"]
        self.assertEqual(pdf["panel_count"], 6)
        self.assertTrue((ROOT / pdf["path"]).exists())

    def test_empirical_and_model_pdf_comparison_is_present(self) -> None:
        comparison = self.manifest["figures"]["conditional_empirical_vs_model_pdf_environment_elevation"]
        self.assertEqual(comparison["panel_count"], 6)
        self.assertEqual(comparison["cell_ready_rows"], 487)
        self.assertTrue((ROOT / comparison["path"]).exists())

    def test_tables_have_expected_rows(self) -> None:
        self.assertEqual(self.manifest["tables"]["cell_summary_rows"], 6)
        self.assertEqual(self.manifest["tables"]["selection_summary_rows"], 1)
        self.assertTrue((ROOT / "tables/conditional_gmm_cell_summary.csv").exists())
        self.assertTrue((ROOT / "tables/conditional_gmm_selection_summary.csv").exists())

    def test_generation_is_review_only(self) -> None:
        self.assertEqual(self.manifest["status"], "PASS_AUTHOR_REVIEW_ONLY")
        self.assertFalse(self.manifest["execution_boundary"]["formal_manuscript_modified"])
        self.assertFalse(self.manifest["execution_boundary"]["canonical_figures_modified"])
        self.assertFalse(self.manifest["execution_boundary"]["canonical_tables_modified"])


if __name__ == "__main__":
    unittest.main()
