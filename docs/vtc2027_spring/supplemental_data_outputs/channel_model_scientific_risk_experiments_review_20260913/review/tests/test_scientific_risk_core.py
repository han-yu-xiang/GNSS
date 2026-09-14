from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from scientific_risk_core import (  # noqa: E402
    evaluate_gmm_complexity,
    fit_weighted_gmm,
    load_primary_population,
    recompute_track_weights,
)


class PopulationTests(unittest.TestCase):
    def test_recompute_track_weights_gives_each_track_unit_mass(self):
        frame = pd.DataFrame(
            {
                "track_id": ["a", "a", "b"],
                "scene_id": ["s1", "s1", "s2"],
                "environment_class": ["Urban", "Urban", "Urban"],
                "doppler_offset_hz": [-50.0, -45.0, 55.0],
                "relative_power_db": [-4.0, -5.0, -10.0],
            }
        )
        weighted = recompute_track_weights(frame)
        masses = weighted.groupby("track_id")["analysis_weight"].sum().to_dict()
        self.assertEqual(set(masses), {"a", "b"})
        self.assertTrue(np.allclose(list(masses.values()), [1.0, 1.0]))

    def test_load_primary_population_rejects_wrong_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "population.csv"
            pd.DataFrame(
                {
                    "primary_population_included": [True, True, True],
                    "environment_class": ["Urban"] * 3,
                    "scene_id": ["s1"] * 3,
                    "track_id": ["t1", "t1", "t2"],
                    "doppler_offset_hz": [1.0, 2.0, 3.0],
                    "relative_power_db": [-1.0, -2.0, -3.0],
                    "excess_delay_samples": [1.0, 2.0, 3.0],
                }
            ).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "expected 518"):
                load_primary_population(path)


class GaussianMixtureTests(unittest.TestCase):
    def test_two_component_fit_orders_means_and_finds_two_peaks(self):
        values = np.array([-52.0, -49.0, -47.0, 51.0, 55.0, 58.0])
        weights = np.full(len(values), 2.0, dtype=float)
        model = fit_weighted_gmm(values, weights, components=2, seed=7)
        self.assertEqual(model["status"], "fit_ok")
        self.assertLess(model["means"][0], model["means"][1])
        self.assertTrue(np.all(np.asarray(model["stds"]) > 0.0))
        self.assertTrue(np.isclose(sum(model["proportions"]), 1.0))
        self.assertTrue(np.isclose(model["means"][0], -49.33, atol=3.0))
        self.assertTrue(np.isclose(model["means"][1], 54.67, atol=3.0))

    def test_scene_loso_has_disjoint_scene_sets(self):
        rows = []
        for scene, offset in (("s1", 0.0), ("s2", 2.0), ("s3", -2.0)):
            for track_index in range(6):
                rows.extend(
                    [
                        {
                            "scene_id": scene,
                            "track_id": f"{scene}_a{track_index}",
                            "environment_class": "Urban",
                            "doppler_offset_hz": -50.0 + offset + track_index,
                            "relative_power_db": -4.0,
                        },
                        {
                            "scene_id": scene,
                            "track_id": f"{scene}_b{track_index}",
                            "environment_class": "Urban",
                            "doppler_offset_hz": 55.0 + offset + track_index,
                            "relative_power_db": -12.0,
                        },
                    ]
                )
        frame = recompute_track_weights(pd.DataFrame(rows))
        summaries, folds = evaluate_gmm_complexity(
            frame, "doppler_offset_hz", components_list=(1, 2, 3), seeds=(11, 12, 13)
        )
        self.assertEqual(set(summaries["components"]), {1, 2, 3})
        self.assertEqual(len(folds), 9)
        for _, row in folds.iterrows():
            self.assertNotIn(row["held_out_scene"], str(row["training_scenes"]).split(";"))


if __name__ == "__main__":
    unittest.main()
