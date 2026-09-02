from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ConditionalGMMSelectionArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "model/candidate_scores.csv").open(newline="", encoding="utf-8") as handle:
            cls.candidates = list(csv.DictReader(handle))
        with (ROOT / "model/scene_loso_scores.csv").open(newline="", encoding="utf-8") as handle:
            cls.scene_scores = list(csv.DictReader(handle))
        with (ROOT / "model/signed_doppler_sensitivity.csv").open(newline="", encoding="utf-8") as handle:
            cls.signed = list(csv.DictReader(handle))
        cls.selected = json.loads((ROOT / "model/selected_conditional_gmm.json").read_text(encoding="utf-8"))

    def test_candidate_grid_and_scene_coverage(self) -> None:
        self.assertEqual(len(self.candidates), 12)
        self.assertEqual(len(self.scene_scores), 12 * 9)
        self.assertEqual({int(row["component_count"]) for row in self.candidates}, {1, 2, 3})
        self.assertEqual({float(row["pooling_kappa"]) for row in self.candidates}, {4.0, 8.0, 16.0, 32.0})
        for candidate_index in range(12):
            held_out = {row["held_out_scene"] for row in self.scene_scores if int(row["candidate_index"]) == candidate_index}
            self.assertEqual(len(held_out), 9)

    def test_selected_model_is_full_three_dimensional_and_not_m3(self) -> None:
        self.assertEqual(self.selected["status"], "BUILT_PENDING_INDEPENDENT_QA")
        self.assertEqual(self.selected["primary_doppler_variable"], "absolute_relative_doppler_magnitude_hz")
        global_means = self.selected["model"]["global_means"]
        self.assertEqual(len(global_means), int(self.selected["model"]["component_count"]))
        self.assertTrue(all(len(mean_vector) == 3 for mean_vector in global_means))
        self.assertNotIn("M3", json.dumps(self.selected))

    def test_selection_records_adjacent_k_nlpd_complexity_rule(self) -> None:
        selection = self.selected["selection"]
        self.assertEqual(selection["component_count"], 3)
        self.assertEqual(selection["candidate_index"], 10)
        comparisons = selection["complexity_comparisons"]
        self.assertEqual(len(comparisons), 1)
        self.assertEqual(comparisons[0]["decision"], "RETAIN_LARGER_K")
        self.assertLess(float(comparisons[0]["q975"]), 0.0)

    def test_signed_sensitivity_is_present_and_finite(self) -> None:
        self.assertEqual(len(self.signed), 9)
        for row in self.signed:
            self.assertEqual(row["comparison_status"], "SIGNED_SENSITIVITY_ONLY")
            self.assertTrue(float(row["signed_minus_absolute_energy_score"]) == float(row["signed_minus_absolute_energy_score"]))

    def test_review_draw_count_is_complete(self) -> None:
        with (ROOT / "model/review_model_draws.csv").open(newline="", encoding="utf-8") as handle:
            draws = list(csv.DictReader(handle))
        self.assertEqual(len(draws), 6 * 4096)
        self.assertEqual(len({row["cell_id"] for row in draws}), 6)


if __name__ == "__main__":
    unittest.main()
