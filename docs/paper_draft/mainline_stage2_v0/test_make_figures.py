"""Narrow regression for paper plots, never touching frozen results."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


class PaperFigureContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        run = subprocess.run(
            [sys.executable, str(HERE / "make_figures.py"), "--output-dir", str(cls.out)],
            text=True,
            capture_output=True,
        )
        if run.returncode:
            raise AssertionError(f"figure generation failed: {run.stdout}\n{run.stderr}")
        cls.audit = json.loads((cls.out / "figure_audit.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_selected_population_and_identity(self):
        a = self.audit
        self.assertEqual((a["scene_n"], a["run_n"], a["selected_window_n"], a["mpc_n"]), (13, 83, 7847, 8914))
        self.assertEqual(a["count_0_1_2_3"], [3574, 1412, 1081, 1780])
        self.assertEqual(a["cir_linked_window_n"], 7847)

    def test_fixed_bin_pairing_and_sign(self):
        rows = self.audit["fixed_bins"]
        self.assertEqual([r["width_hz"] for r in rows], [5, 10, 20])
        for r, expected in zip(rows, [-0.0076837823661569694, -0.008640372430508884, -0.00820576]):
            self.assertEqual((r["scene_n"], r["positive_scene_n"], r["negative_scene_n"], r["paired_window_n"]), (13, 10, 3, 4273))
            self.assertAlmostEqual(r["macro_delta_nats_per_mark"], expected, places=7)

    def test_all_core_figures_exist(self):
        for key in ("F1", "F2", "F3", "F4", "F7"):
            for suffix in ("png", "svg"):
                self.assertGreater((self.out / f"{key}.{suffix}").stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
