"""Behavior tests for the restricted, read-only MATLAB v5 reader."""

from __future__ import annotations

import unittest
from pathlib import Path

from mat_v5_reader import load_mat_v5


ROOT = Path(__file__).resolve().parents[3]
G25_STAGE4 = (
    ROOT
    / "scenes"
    / "F1023_V80_D0117_P8"
    / "sage_results"
    / "nav_sage_v2"
    / "G25"
    / "stage4_nav_joint_100ms.mat"
)


class MatV5ReaderTests(unittest.TestCase):
    def test_reads_nested_joint_fits_from_frozen_stage4_artifact(self) -> None:
        content = load_mat_v5(G25_STAGE4)
        self.assertIn("jointFits", content)
        fits = content["jointFits"]
        self.assertEqual(len(fits), 8)
        selected = next(fit for fit in fits if int(fit["centerWindowId"]) == 985)
        self.assertEqual(int(selected["selectedOrder"]), 2)
        self.assertEqual(len(selected["models"]), 4)
        self.assertEqual(len(selected["models"][0]["snapshotRss"]), 5)
        self.assertLess(selected["models"][1]["rss"], selected["models"][0]["rss"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
