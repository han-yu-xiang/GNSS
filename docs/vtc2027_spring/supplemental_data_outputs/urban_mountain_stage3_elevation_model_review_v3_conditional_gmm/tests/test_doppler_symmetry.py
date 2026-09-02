from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/audit_doppler_symmetry.py"
SPEC = importlib.util.spec_from_file_location("audit_doppler_symmetry", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Doppler symmetry script")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DopplerSymmetryTests(unittest.TestCase):
    def test_mirror_distance_is_zero_for_symmetric_atoms(self) -> None:
        values = np.asarray([-2.0, -1.0, 1.0, 2.0])
        weights = np.ones(4)
        self.assertAlmostEqual(MODULE.weighted_mirror_distance(values, weights), 0.0)

    def test_absolute_transform_folds_sign_without_changing_units(self) -> None:
        values = np.asarray([-50.0, 0.0, 100.0])
        np.testing.assert_allclose(MODULE.absolute_doppler(values), [50.0, 0.0, 100.0])

    def test_diagnostic_outputs_preserve_primary_denominators(self) -> None:
        decision = json.loads((ROOT / "diagnostics/doppler_transform_decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["counts"]["primary_rows"], 518)
        self.assertEqual(decision["counts"]["elevation_ready_rows"], 487)
        self.assertEqual(decision["counts"]["missing_elevation_rows"], 31)
        self.assertFalse(decision["physical_symmetry_claim"])
        self.assertTrue(decision["signed_sensitivity_required"])

    def test_diagnostic_outputs_cover_global_environment_and_cells(self) -> None:
        rows = MODULE.read_csv(ROOT / "diagnostics/doppler_symmetry_by_scope.csv")
        self.assertEqual(len(rows), 9)
        self.assertEqual({row["scope"] for row in rows}, {"global", "environment", "cell"})
        self.assertTrue(all(float(row["weighted_mirror_cdf_distance"]) >= 0.0 for row in rows))


if __name__ == "__main__":
    unittest.main()
