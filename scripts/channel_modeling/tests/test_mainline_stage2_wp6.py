"""Synthetic-only regression tests for the Mainline Stage2 WP6 model."""

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
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
         "excess_delay_samples": 2.0,
         "excess_delay_chips": 0.2, "doppler_offset_hz": -4.0, "relative_power_db": -8.0},
        {"run_id": "R1", "window_id": "1", "path_id": "3", "scene_id": "S1",
         "is_multipath": 1, "modeling_role": "MPC_CANDIDATE",
         "excess_delay_samples": 4.0,
         "excess_delay_chips": 0.4, "doppler_offset_hz": 2.0, "relative_power_db": -12.0},
        {"run_id": "R1", "window_id": "2", "path_id": "2", "scene_id": "S1",
         "is_multipath": 1, "modeling_role": "MPC_CANDIDATE",
         "excess_delay_samples": 3.0,
         "excess_delay_chips": 0.3, "doppler_offset_hz": 1.0, "relative_power_db": -6.0},
    ])
    return windows, mpcs


def _mark_frame(scene_n=4, windows_per_scene=8, paths_per_window=1, identical=False):
    rows = []
    for scene_index in range(scene_n):
        scene = f"S{scene_index + 1}"
        for window_index in range(windows_per_scene):
            for path_index in range(paths_per_window):
                x = float(scene_index * windows_per_scene + window_index + path_index + 1)
                if identical:
                    delay, doppler, power = x, x, x
                else:
                    delay = 0.04 + 0.01 * x + 0.0003 * x * x
                    doppler = (-1) ** window_index * (x * 0.7) + 0.13 * scene_index
                    power = -4.0 - 0.17 * x + 0.09 * (x % 3)
                rows.append({
                    "run_id": f"R{scene_index + 1}", "window_id": str(window_index + 1),
                    "path_id": str(path_index + 2), "scene_id": scene,
                    "excess_delay_samples": 10.0 * delay,
                    "excess_delay_chips": delay, "doppler_offset_hz": doppler,
                    "relative_power_db": power,
                })
    return pd.DataFrame(rows)


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
            "excess_delay_samples": 2.0,
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


class WP6MarkModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wp6 = _load_module()
        import mainline_stage2_wp3
        cls.wp3 = mainline_stage2_wp3

    def _api(self, name):
        self.assertIsNotNone(self.wp6, "WP6 module/API has not been implemented")
        fn = getattr(self.wp6, name, None)
        self.assertTrue(callable(fn), f"required WP6 API is missing: {name}")
        return fn

    def _normal_fits(self):
        return {
            variable: {"family": "normal", "status": "PASS",
                       "parameters": {"loc": 0.0, "scale": 1.0}}
            for variable in ("excess_delay_chips", "doppler_offset_hz", "relative_power_db")
        }

    def test_inner_loso_never_uses_outer_scene_for_family_selection(self):
        select = self._api("select_mark_families_nested")
        frame = _mark_frame(scene_n=4)
        families, inner_scores, failures = select(
            frame, outer_training_scenes=("S1", "S2", "S3"))
        self.assertIsInstance(families, dict)
        self.assertGreater(len(inner_scores), 0)
        self.assertNotIn("S4", set(inner_scores.inner_held_out_scene_id))
        for row in inner_scores.itertuples(index=False):
            self.assertNotIn("S4", row.inner_training_scene_ids)
        self.assertIsInstance(failures, pd.DataFrame)

    def test_mark_fit_reuses_wp3_families_and_window_scene_weights(self):
        self.assertIs(self.wp6._wp3_fit_static, self.wp3._fit_static)
        self.assertIs(self.wp6._wp3_scene_window_weights, self.wp3.scene_window_weights)
        self.assertEqual(self.wp6.MARK_FAMILIES, self.wp3.VARIABLE_FAMILIES)

    def test_identity_copula_matches_product_marginal_density(self):
        score = self._api("score_mark_models")
        frame = _mark_frame(scene_n=1, windows_per_scene=2, paths_per_window=2)
        per_window, _ = score(self._normal_fits(), np.eye(3), frame)
        np.testing.assert_allclose(
            per_window.product_marginal_log_score,
            per_window.gaussian_copula_log_score,
            rtol=0, atol=1e-12)

    def test_copula_log_density_matches_hand_calculation(self):
        log_density = self._api("gaussian_copula_log_density")
        uniforms = np.asarray([[0.5, 0.5]])
        corr = np.asarray([[1.0, 0.5], [0.5, 1.0]])
        expected = -0.5 * np.log(np.linalg.det(corr))
        self.assertAlmostEqual(float(log_density(uniforms, corr)[0]), expected, places=12)

    def test_scene_balanced_kendall_and_projection_are_recorded(self):
        fit = self._api("fit_scene_balanced_copula")
        corr, diagnostics = fit(_mark_frame(scene_n=3, identical=True), self._normal_fits())
        self.assertTrue(diagnostics["projection_applied"])
        self.assertGreater(np.linalg.eigvalsh(corr).min(), 0.0)
        self.assertEqual(diagnostics["scene_n_used"], 3)
        for tau in diagnostics["pairwise_scene_tau_k"]["excess_delay_chips|doppler_offset_hz"].values():
            self.assertAlmostEqual(tau, 1.0, places=12)

    def test_mark_scores_pair_identical_heldout_keys_and_sum_within_window(self):
        score = self._api("score_mark_models")
        frame = _mark_frame(scene_n=1, windows_per_scene=2, paths_per_window=2)
        per_window, per_scene = score(self._normal_fits(), np.eye(3), frame)
        self.assertEqual(set(map(tuple, per_window[["run_id", "window_id"]].to_numpy())),
                         set(map(tuple, frame[["run_id", "window_id"]].drop_duplicates().to_numpy())))
        first = frame.loc[frame.window_id.eq("1")]
        expected = sum(
            self.wp6._wp3_distribution_logpdf("normal", first[column].to_numpy(), {"loc": 0.0, "scale": 1.0})
            for column in ("excess_delay_chips", "doppler_offset_hz", "relative_power_db")
        ).sum()
        self.assertAlmostEqual(float(per_window.loc[per_window.window_id.eq("1"),
                                                   "product_marginal_log_score"].iloc[0]),
                               float(expected), places=12)
        self.assertEqual(len(per_scene), 1)

    def test_tail_quantiles_use_train_fit_and_flag_expected_support_below_ten(self):
        calibrate = self._api("calibrate_mark_tails")
        fit = {"family": "normal", "status": "PASS", "parameters": {"loc": 0.0, "scale": 1.0}}
        heldout = pd.DataFrame({"excess_delay_chips": [0.2, 0.3, 0.4, 0.5]})
        tails = calibrate(fit, heldout, "excess_delay_chips")
        self.assertEqual(len(tails), 6)
        self.assertTrue(set(tails.status) == {"LOW_SUPPORT"})
        self.assertTrue((tails.training_fit_used == True).all())
        self.assertTrue((tails.heldout_n == 4).all())

    def test_fit_failures_remain_visible_and_final_refit_is_separate(self):
        select = self._api("select_mark_families_nested")
        fit_final = self._api("fit_final_mark_model")
        frame = _mark_frame(scene_n=3, windows_per_scene=1)
        families, inner_scores, failures = select(frame)
        self.assertTrue(all(value is None for value in families.values()))
        self.assertGreater(len(failures), 0)
        self.assertTrue(inner_scores.score_status.ne("PASS").any())
        final = fit_final(frame)
        self.assertIn("selection", final)
        self.assertIn("full_population_refits", final)
        self.assertTrue(all(v["status"] != "PASS" for v in final["full_population_refits"].values()))


def _window_pdp_fixture(scene_n=3, windows_per_scene=3):
    windows = []
    mpcs = []
    for scene_index in range(scene_n):
        scene = f"S{scene_index + 1}"
        for window_index in range(windows_per_scene):
            run_id = f"R{scene_index + 1}"
            win_id = str(window_index + 1)
            x = float(scene_index * windows_per_scene + window_index + 1)
            y_rms = float(1.0 + 0.2 * x + 50 * scene_index)
            y_peak = float(-0.5 + 0.1 * x + 20 * scene_index)
            windows.append({
                "run_id": run_id, "window_id": win_id, "scene_id": scene,
                "environment_class": "Urban", "stage2_mpc_count": 1,
                "pdp_peak_at_grid_boundary": window_index == 0,
                "pdp_rms_width_code_delay_samples": y_rms,
                "pdp_peak_minus_sage_direct_delay_samples": y_peak,
            })
            delay_chips = 0.1 + 0.03 * x
            mpcs.append({
                "run_id": run_id, "window_id": win_id, "path_id": "2", "scene_id": scene,
                "excess_delay_samples": 10 * delay_chips,
                "excess_delay_chips": delay_chips,
                "doppler_offset_hz": x - 3.0, "relative_power_db": -6.020599913279624,
            })
    return pd.DataFrame(windows), pd.DataFrame(mpcs)


def _window_scene_folds(windows):
    folds = []
    for scene in sorted(windows.scene_id.astype(str).unique()):
        test = windows.loc[windows.scene_id.astype(str).eq(scene)].copy().reset_index(drop=True)
        train = windows.loc[~windows.scene_id.astype(str).eq(scene)].copy().reset_index(drop=True)
        folds.append({"held_out_scene_id": scene, "train": train, "test": test,
                      "training_scene_ids": tuple(sorted(train.scene_id.astype(str).unique()))})
    return folds


class WP6CirPdpAssociationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wp6 = _load_module()

    def _api(self, name):
        self.assertIsNotNone(self.wp6, "WP6 module/API has not been implemented")
        fn = getattr(self.wp6, name, None)
        self.assertTrue(callable(fn), f"required WP6 API is missing: {name}")
        return fn

    def test_weighted_delay_moments_include_unit_direct_reference(self):
        derive = self._api("derive_window_delay_summaries")
        windows, mpcs = _fixture_frames()
        result = derive(windows, mpcs)
        row = result.loc[result.window_id.eq("1")].iloc[0]
        weights = np.asarray([1.0, 10 ** (-8.0 / 10.0), 10 ** (-12.0 / 10.0)])
        delays = np.asarray([0.0, 2.0, 4.0])
        centroid = float(np.dot(weights, delays) / weights.sum())
        rms = float(np.sqrt(np.dot(weights, (delays - centroid) ** 2) / weights.sum()))
        self.assertAlmostEqual(row.sage_relative_power_delay_centroid_samples, centroid, places=12)
        self.assertAlmostEqual(row.sage_relative_power_delay_rms_samples, rms, places=12)

    def test_zero_mpc_window_is_retained_with_direct_only_moments(self):
        derive = self._api("derive_window_delay_summaries")
        windows, mpcs = _fixture_frames()
        result = derive(windows, mpcs)
        zero = result.loc[result.stage2_mpc_count.eq(0)]
        self.assertEqual(len(zero), 1)
        self.assertEqual(len(result), len(windows))
        self.assertEqual(zero.iloc[0].sage_relative_power_delay_centroid_samples, 0.0)
        self.assertEqual(zero.iloc[0].sage_relative_power_delay_rms_samples, 0.0)

    def test_all_window_keys_and_boundary_flags_survive(self):
        derive = self._api("derive_window_delay_summaries")
        windows, mpcs = _fixture_frames()
        result = derive(windows, mpcs)
        self.assertEqual(set(map(tuple, result[["run_id", "window_id"]].to_numpy())),
                         set(map(tuple, windows[["run_id", "window_id"]].to_numpy())))
        self.assertEqual(result.pdp_peak_at_grid_boundary.sum(),
                         windows.pdp_peak_at_grid_boundary.sum())

    def test_pdp_regression_uses_only_training_scenes(self):
        derive = self._api("derive_window_delay_summaries")
        evaluate = self._api("evaluate_cir_pdp_loso")
        windows, mpcs = _window_pdp_fixture()
        summarized = derive(windows, mpcs)
        predictions, _ = evaluate(summarized, _window_scene_folds(summarized))
        held = predictions.loc[
            predictions.outer_held_out_scene_id.eq("S3")
            & predictions.target.eq("pdp_rms_width_code_delay_samples")]
        training_mean = summarized.loc[summarized.scene_id.ne("S3"),
                                       "pdp_rms_width_code_delay_samples"].mean()
        self.assertTrue(np.allclose(held.baseline_training_mean, training_mean))
        self.assertNotEqual(float(held.iloc[0].baseline_training_mean),
                            float(summarized.loc[summarized.scene_id.eq("S3"),
                                                 "pdp_rms_width_code_delay_samples"].mean()))

    def test_scene_macro_mae_rmse_are_hand_computable(self):
        derive = self._api("derive_window_delay_summaries")
        evaluate = self._api("evaluate_cir_pdp_loso")
        windows, mpcs = _window_pdp_fixture(scene_n=2, windows_per_scene=3)
        summarized = derive(windows, mpcs)
        predictions, scores = evaluate(summarized, _window_scene_folds(summarized))
        rows = predictions.loc[
            predictions.outer_held_out_scene_id.eq("S1")
            & predictions.target.eq("pdp_rms_width_code_delay_samples")]
        manual_mae = float(np.mean(np.abs(rows.observed - rows.baseline_prediction)))
        manual_rmse = float(np.sqrt(np.mean((rows.observed - rows.baseline_prediction) ** 2)))
        summary = scores.loc[
            scores.outer_held_out_scene_id.eq("S1")
            & scores.target.eq("pdp_rms_width_code_delay_samples")
            & scores.model.eq("INTERCEPT")].iloc[0]
        self.assertAlmostEqual(summary.mae, manual_mae, places=12)
        self.assertAlmostEqual(summary.rmse, manual_rmse, places=12)

    def test_duplicate_keys_and_invalid_pdp_responses_fail_closed(self):
        derive = self._api("derive_window_delay_summaries")
        evaluate = self._api("evaluate_cir_pdp_loso")
        windows, mpcs = _fixture_frames()
        duplicate = pd.concat([windows, windows.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            derive(duplicate, mpcs)
        summarized = derive(windows, mpcs)
        summarized.loc[0, "pdp_rms_width_code_delay_samples"] = -1.0
        with self.assertRaisesRegex(ValueError, "RMS|negative"):
            evaluate(summarized, _window_scene_folds(summarized))
