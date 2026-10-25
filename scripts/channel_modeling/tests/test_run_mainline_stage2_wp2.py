"""Synthetic-only integration contracts for the pinned WP2 report runner."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

CHANNEL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CHANNEL_DIR))
import mainline_stage2_v0 as v0
from run_mainline_stage2_wp2 import run_analysis


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WP2RunnerTests(unittest.TestCase):
    def _write_inputs(self, root: Path):
        mpc_rows, window_rows = [], []
        for scene_index, scene in enumerate(("scene-A", "scene-B", "scene-C")):
            run_id = f"run-{scene_index}"
            for window_index, count in enumerate((0, 1, 2, 1), start=1):
                window_rows.append({"run_id": run_id, "window_id": str(window_index),
                                    "scene_id": scene, "mpc_count": count,
                                    "latitude": 31.0, "longitude": 121.0})
                for path_offset in range(count):
                    delay = float(window_index) + 0.1 * path_offset
                    mpc_rows.append({
                        "run_id": run_id, "window_id": str(window_index), "scene_id": scene,
                        "environment_class": "Urban", "path_id": path_offset + 2,
                        "is_multipath": 1, "excess_delay_chips": delay,
                        "doppler_offset_hz": 0.3 * window_index + 0.2 * scene_index + path_offset,
                        "relative_power_db": 2.0 * scene_index - 3.0 * delay + 0.1 * path_offset,
                    })
        mpc_path = root / "analysis_mpc_rows.csv"
        windows_path = root / "selected_window_rows.csv"
        folds_path = root / "scene_fold_scores.csv"
        pd.DataFrame(mpc_rows).to_csv(mpc_path, index=False)
        pd.DataFrame(window_rows).to_csv(windows_path, index=False)
        mpc = pd.DataFrame(mpc_rows)
        scores, _ = v0.evaluate_loso(
            mpc,
            variables={"excess_delay_chips": ["lognormal"],
                       "doppler_offset_hz": ["normal"],
                       "relative_power_db": ["normal"]},
            scopes=["GLOBAL", "ENV:Urban"],
        )
        # The pinned V0 table also contains other environments; the WP2
        # closure intentionally selects only Global and Urban scopes.
        other_scope = [dict(row, scope="ENV:Other") for row in scores]
        scores.extend(other_scope)
        pd.DataFrame(scores).to_csv(folds_path, index=False)
        private_manifest = root / "private_manifest.json"
        fold_manifest = root / "fold_manifest.json"
        private_manifest.write_text(json.dumps({
            name: {"sha256": _sha(root / name)}
            for name in ("analysis_mpc_rows.csv", "selected_window_rows.csv")
        }), encoding="utf-8")
        fold_manifest.write_text(json.dumps({"scene_fold_scores.csv": {
            "sha256": _sha(folds_path)
        }}), encoding="utf-8")
        hashes = {
            "analysis_mpc_rows.csv": _sha(mpc_path),
            "selected_window_rows.csv": _sha(windows_path),
            "scene_fold_scores.csv": _sha(folds_path),
        }
        population = {
            "mpc_n": 12, "selected_window_n": 12, "run_n": 3, "scene_n": 3,
            "mpc_count_histogram": {"0": 3, "1": 6, "2": 3, "3": 0},
        }
        return mpc_path, windows_path, folds_path, private_manifest, fold_manifest, hashes, population

    def test_runner_pins_population_writes_aggregate_only_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mpc, windows, folds, private_manifest, fold_manifest, hashes, population = self._write_inputs(root)
            output = root / "wp2_output"
            result = run_analysis(
                mpc, windows, folds, output, expected_hashes=hashes,
                expected_population=population, private_manifest=private_manifest,
                fold_manifest=fold_manifest,
                variables={"excess_delay_chips": ["lognormal"],
                           "doppler_offset_hz": ["normal"],
                           "relative_power_db": ["normal"]},
                scopes=("GLOBAL", "ENV:Urban"), bootstrap_iterations=20, seed=7,
            )
            self.assertEqual(result, output)
            for name in (
                "marginal_stability_by_fold.csv", "marginal_stability_summary.csv",
                "tail_calibration_by_scene.csv", "tail_calibration_summary.csv",
                "power_delay_loso_by_scene.csv", "power_delay_loso_summary.csv",
                "selected_count_loso_by_scene.csv", "selected_count_loso_summary.csv",
                "wp2_report.md", "wp2_manifest.json",
            ):
                self.assertTrue((output / name).is_file(), name)
            for name in ("marginal_stability_by_fold.csv", "tail_calibration_by_scene.csv",
                         "power_delay_loso_by_scene.csv", "selected_count_loso_by_scene.csv"):
                columns = set(pd.read_csv(output / name, nrows=0).columns)
                self.assertFalse(columns & {"run_id", "window_id", "path_id", "latitude", "longitude"})
            report = (output / "wp2_report.md").read_text(encoding="utf-8")
            self.assertIn("unselected Stage0 windows were not assigned zero MPC", report)
            manifest = json.loads((output / "wp2_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["population"], population)
            self.assertFalse(manifest["validation"]["row_level_p_values"])
            with self.assertRaises(FileExistsError):
                run_analysis(
                    mpc, windows, folds, output, expected_hashes=hashes,
                    expected_population=population, private_manifest=private_manifest,
                    fold_manifest=fold_manifest,
                    variables={"excess_delay_chips": ["lognormal"],
                               "doppler_offset_hz": ["normal"],
                               "relative_power_db": ["normal"]},
                    scopes=("GLOBAL", "ENV:Urban"), bootstrap_iterations=2,
                )

    def test_runner_rejects_hash_mismatch_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mpc, windows, folds, _, _, hashes, population = self._write_inputs(root)
            hashes["analysis_mpc_rows.csv"] = "0" * 64
            output = root / "must_not_exist"
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                run_analysis(mpc, windows, folds, output, expected_hashes=hashes,
                             expected_population=population,
                             variables={"excess_delay_chips": ["lognormal"],
                                        "doppler_offset_hz": ["normal"],
                                        "relative_power_db": ["normal"]},
                             scopes=("GLOBAL", "ENV:Urban"), bootstrap_iterations=0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
