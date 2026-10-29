"""Synthetic-only regression tests for the Mainline Stage2 WP6 model."""

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "mainline_stage2_wp6.py"
if str(MODULE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_PATH.parent))


def _load_module():
    if not MODULE_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("mainline_stage2_wp6", MODULE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_frames():
    windows = pd.DataFrame([
        {"run_id": "R1", "window_id": "1", "scene_id": "S1",
         "stage2_mpc_count": 2, "pdp_peak_at_grid_boundary": False,
         "pdp_rms_width_code_delay_samples": 0.8,
         "pdp_peak_minus_sage_direct_delay_samples": 1.2},
        {"run_id": "R1", "window_id": "2", "scene_id": "S1",
         "stage2_mpc_count": 1, "pdp_peak_at_grid_boundary": True,
         "pdp_rms_width_code_delay_samples": 1.1,
         "pdp_peak_minus_sage_direct_delay_samples": 2.3},
        {"run_id": "R2", "window_id": "1", "scene_id": "S2",
         "stage2_mpc_count": 0, "pdp_peak_at_grid_boundary": False,
         "pdp_rms_width_code_delay_samples": 0.0,
         "pdp_peak_minus_sage_direct_delay_samples": 0.0},
    ])
    mpcs = pd.DataFrame([
        {"run_id": "R1", "window_id": "1", "path_id": "2", "scene_id": "S1",
         "is_multipath": 1, "modeling_role": "MPC_CANDIDATE",
         "excess_delay_chips": 0.2, "doppler_offset_hz": -4.0, "relative_power_db": -8.0},
        {"run_id": "R1", "window_id": "1", "path_id": "3", "scene_id": "S1",
         "is_multipath": 1, "modeling_role": "MPC_CANDIDATE",
         "excess_delay_chips": 0.4, "doppler_offset_hz": 2.0, "relative_power_db": -12.0},
        {"run_id": "R1", "window_id": "2", "path_id": "2", "scene_id": "S1",
         "is_multipath": 1, "modeling_role": "MPC_CANDIDATE",
         "excess_delay_chips": 0.3, "doppler_offset_hz": 1.0, "relative_power_db": -6.0},
    ])
    return windows, mpcs


class WP6InputAndCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wp6 = _load_module()

    def _api(self, name):
        self.assertIsNotNone(self.wp6, "WP6 module/API has not been implemented")
        fn = getattr(self.wp6, name, None)
        self.assertTrue(callable(fn), f"required WP6 API is missing: {name}")
        return fn

    def test_pinned_schema_and_exact_window_path_keys_reconcile(self):
        load_wp6_inputs = self._api("load_wp6_inputs")
        validate = self._api("validate_wp6_population")
        windows, mpcs = _fixture_frames()
        with tempfile.TemporaryDirectory() as temp:
            features_path = Path(temp) / "features.csv"
            mpc_path = Path(temp) / "mpcs.csv"
            windows.to_csv(features_path, index=False)
            mpcs.to_csv(mpc_path, index=False)
            hashes = {
                "features": hashlib.sha256(features_path.read_bytes()).hexdigest(),
                "mpcs": hashlib.sha256(mpc_path.read_bytes()).hexdigest(),
            }
            loaded_windows, loaded_mpcs, manifest = load_wp6_inputs(
                features_path, mpc_path, expected_hashes=hashes,
                expected_contract={
                    "window_n": 3, "mpc_n": 3, "scene_n": 2,
                    "count_support": (0, 1, 2),
                })
        validate(loaded_windows, loaded_mpcs, expected_contract={
            "window_n": 3, "mpc_n": 3, "scene_n": 2,
            "count_support": (0, 1, 2),
        })
        self.assertEqual((len(loaded_windows), len(loaded_mpcs)), (3, 3))
        self.assertEqual(manifest["features_sha256"], hashes["features"])
        self.assertEqual(manifest["mpc_sha256"], hashes["mpcs"])
        self.assertEqual(set(loaded_mpcs.scene_id), {"S1"})

    def test_zero_mpc_selected_windows_remain_in_the_count_denominator(self):
        validate = self._api("validate_wp6_population")
        windows, mpcs = _fixture_frames()
        validate(windows, mpcs, expected_contract={
            "window_n": 3, "mpc_n": 3, "scene_n": 2,
            "count_support": (0, 1, 2),
        })
        zero_rows = windows.loc[windows.stage2_mpc_count.eq(0)]
        self.assertEqual(len(windows), 3)
        self.assertEqual(len(zero_rows), 1)
        self.assertEqual(zero_rows.iloc[0].window_id, "1")
        self.assertEqual(set(mpcs.window_id), {"1", "2"})

    def test_duplicate_missing_extra_and_inconsistent_count_keys_fail(self):
        validate = self._api("validate_wp6_population")
        windows, mpcs = _fixture_frames()
        duplicate = pd.concat([mpcs, mpcs.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate(windows, duplicate, expected_contract={
                "window_n": 3, "mpc_n": 3, "scene_n": 2,
                "count_support": (0, 1, 2),
            })

        missing = mpcs.iloc[:-1].copy()
        with self.assertRaisesRegex(ValueError, "count|path|reconcil"):
            validate(windows, missing, expected_contract={
                "window_n": 3, "mpc_n": 3, "scene_n": 2,
                "count_support": (0, 1, 2),
            })

        extra = pd.concat([mpcs, pd.DataFrame([{
            "run_id": "R9", "window_id": "9", "path_id": "2", "scene_id": "S9",
            "is_multipath": 1, "modeling_role": "MPC_CANDIDATE",
            "excess_delay_chips": 0.2, "doppler_offset_hz": 0.0, "relative_power_db": -9.0,
        }])], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "window|key|reconcil"):
            validate(windows, extra, expected_contract={
                "window_n": 3, "mpc_n": 4, "scene_n": 2,
                "count_support": (0, 1, 2),
            })

    def test_scene_macro_count_probabilities_use_training_scenes_only(self):
        fit = self._api("fit_count_probabilities")
        training = pd.DataFrame([
            {"run_id": "A", "window_id": str(i), "scene_id": "A", "stage2_mpc_count": n}
            for i, n in enumerate([0, 1, 1, 1, 1, 1, 1, 1, 1, 1])
        ] + [
            {"run_id": "B", "window_id": str(i), "scene_id": "B", "stage2_mpc_count": n}
            for i, n in enumerate([2, 3])
        ])
        fitted = fit(training)
        self.assertEqual(fitted, {0: 0.05, 1: 0.45, 2: 0.25, 3: 0.25})
        self.assertAlmostEqual(sum(fitted.values()), 1.0)

    def test_unsupported_count_category_is_not_smoothed(self):
        score = self._api("score_count_fold")
        training = pd.DataFrame([
            {"run_id": "A", "window_id": "1", "scene_id": "A", "stage2_mpc_count": 0},
            {"run_id": "B", "window_id": "1", "scene_id": "B", "stage2_mpc_count": 0},
        ])
        heldout = pd.DataFrame([
            {"run_id": "T", "window_id": "1", "scene_id": "T", "stage2_mpc_count": 3},
        ])
        probabilities, per_window, per_scene = score(training, heldout)
        self.assertEqual(probabilities[3], 0.0)
        self.assertEqual(per_window.iloc[0].status, "UNSUPPORTED_COUNT_CATEGORY")
        self.assertTrue(pd.isna(per_window.iloc[0].log_score))
        self.assertEqual(per_scene.iloc[0].status, "UNSUPPORTED_COUNT_CATEGORY")
