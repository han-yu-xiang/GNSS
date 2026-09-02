from __future__ import annotations

import csv
import importlib.util
import json
import math
import sys
import unittest
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/build_gmm_feature_population.py"
SPEC = importlib.util.spec_from_file_location("build_gmm_feature_population", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load feature population script")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GMMFeaturePopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "population/gmm_feature_population.csv").open(newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))
        with (ROOT / "population/gmm_cell_support.csv").open(newline="", encoding="utf-8") as handle:
            cls.cells = list(csv.DictReader(handle))
        cls.manifest = json.loads((ROOT / "population/gmm_feature_population_manifest.json").read_text(encoding="utf-8"))

    def test_feature_population_denominators(self) -> None:
        self.assertEqual(len(self.rows), 518)
        self.assertEqual(sum(row["cell_ready"] == "1" for row in self.rows), 487)
        self.assertEqual(sum(row["cell_ready"] == "0" for row in self.rows), 31)
        self.assertEqual(len(self.cells), 6)

    def test_transforms_are_finite_and_support_aware(self) -> None:
        for row in self.rows:
            values = [float(row[field]) for field in ("absolute_doppler_hz", "log_excess_delay", "log1p_absolute_doppler")]
            self.assertTrue(all(math.isfinite(value) for value in values))
            self.assertGreaterEqual(values[0], 0.0)
            self.assertGreater(float(row["excess_delay_samples"]), 0.0)
            if row["cell_ready"] == "1":
                self.assertIn(row["elevation_band"], {"LOW", "MID", "HIGH"})
                self.assertEqual(row["parent_scope_role"], "CELL_AND_ENVIRONMENT")
            else:
                self.assertEqual(row["elevation_band"], "")
                self.assertEqual(row["cell_id"], "")
                self.assertEqual(row["parent_scope_role"], "ENVIRONMENT_PARENT_ONLY")

    def test_track_weights_sum_to_one(self) -> None:
        totals: dict[str, float] = defaultdict(float)
        for row in self.rows:
            totals[row["track_id"]] += float(row["track_weight_recomputed_primary"])
        self.assertEqual(len(totals), 236)
        for total in totals.values():
            self.assertAlmostEqual(total, 1.0, places=10)

    def test_six_cell_counts_match_frozen_support(self) -> None:
        counts = {row["cell_id"]: int(row["observation_count"]) for row in self.cells}
        self.assertEqual(counts, {"Urban__LOW": 18, "Urban__MID": 169, "Urban__HIGH": 129, "Mountain/Valley__LOW": 22, "Mountain/Valley__MID": 117, "Mountain/Valley__HIGH": 32})
        status = {row["cell_id"]: row["support_status"] for row in self.cells}
        self.assertEqual(status["Urban__LOW"], "STRONGLY_PARTIALLY_POOLED")
        self.assertEqual(status["Mountain/Valley__LOW"], "STRONGLY_PARTIALLY_POOLED")
        self.assertEqual(status["Mountain/Valley__HIGH"], "STRONGLY_PARTIALLY_POOLED")

    def test_manifest_preserves_source_and_execution_boundary(self) -> None:
        self.assertEqual(self.manifest["counts"]["primary_rows"], 518)
        self.assertFalse(self.manifest["execution_boundary"]["stage4_source_used"])
        self.assertFalse(self.manifest["execution_boundary"]["formal_manuscript_modified"])


if __name__ == "__main__":
    unittest.main()
