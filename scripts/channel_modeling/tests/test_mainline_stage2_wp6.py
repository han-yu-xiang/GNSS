"""Synthetic-only regression tests for the Mainline Stage2 WP6 model."""

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "mainline_stage2_wp6.py"
RUNNER_PATH = Path(__file__).resolve().parents[1] / "run_mainline_stage2_wp6.py"
VALIDATOR_PATH = Path(__file__).resolve().parents[1] / "validate_mainline_stage2_wp6.py"
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


def _load_path(path, module_name):
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(module_name, path)
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


def _joint_score_fixture_frames():
    """Small Stage2 population with a count category supported across held-out folds."""
    windows, source_mpcs = _fixture_frames()
    windows = windows.copy()
    windows["stage2_mpc_count"] = [1, 0, 1]
    mpcs = source_mpcs.iloc[[0, 2]].copy().reset_index(drop=True)
    mpcs.loc[1, ["run_id", "window_id", "scene_id"]] = ["R2", "1", "S2"]
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

    def test_outer_mark_scores_retain_windows_when_family_selection_fails(self):
        evaluate = self._api("evaluate_nested_mark_loso")
        frame = _mark_frame(scene_n=3, windows_per_scene=1)
        result = evaluate(frame)
        self.assertEqual(len(result["window_scores"]), len(frame))
        self.assertTrue(result["window_scores"].status.eq("UNSCORABLE_MARGINAL_FIT").all())
        self.assertEqual(set(result["window_scores"].scene_id), set(frame.scene_id))

    def test_unscorable_mark_output_is_one_row_per_window_for_multipath_windows(self):
        evaluate = self._api("evaluate_nested_mark_loso")
        frame = _mark_frame(scene_n=3, windows_per_scene=2, paths_per_window=2)
        failed = {variable: {"status": "FIT_FAILED", "failure_reason": "synthetic"}
                  for variable in self.wp6.MARK_VARIABLES}
        with patch.object(self.wp6, "_fit_selected_marginals", return_value=failed):
            result = evaluate(frame)
        scores = result["window_scores"]
        expected_window_n = frame[["run_id", "window_id"]].drop_duplicates().shape[0]
        self.assertEqual(len(scores), expected_window_n)
        self.assertFalse(scores.duplicated(["run_id", "window_id"]).any())
        self.assertTrue(scores.path_n.eq(2).all())
        self.assertTrue(scores.status.eq("UNSCORABLE_MARGINAL_FIT").all())


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


def _build_validator_fixture(root, wp6, source_frames=None):
    validator = _load_path(VALIDATOR_PATH, "validate_mainline_stage2_wp6_independent_test")
    windows, mpcs = source_frames if source_frames is not None else _fixture_frames()
    features_path = root / "features.csv"
    mpc_path = root / "mpcs.csv"
    windows.to_csv(features_path, index=False)
    mpcs.to_csv(mpc_path, index=False)
    source_hashes = {
        "features": hashlib.sha256(features_path.read_bytes()).hexdigest(),
        "mpcs": hashlib.sha256(mpc_path.read_bytes()).hexdigest(),
    }
    output = root / "result"
    output.mkdir()
    summaries = wp6.derive_window_delay_summaries(windows, mpcs)
    summaries.to_csv(output / "selected_window_delay_summaries.csv", index=False)
    count_rows = windows[["run_id", "window_id", "scene_id", "stage2_mpc_count"]].copy()
    count_rows["outer_held_out_scene_id"] = count_rows.scene_id
    count_probabilities = []
    for held in sorted(windows.scene_id.unique()):
        training = windows.loc[windows.scene_id.ne(held)]
        scene_frequencies = []
        for _, scene_frame in training.groupby("scene_id", sort=True):
            frequencies = scene_frame.stage2_mpc_count.value_counts(normalize=True)
            scene_frequencies.append({category: float(frequencies.get(category, 0.0))
                                      for category in wp6.COUNT_SUPPORT})
        probabilities = {category: float(np.mean([freq[category] for freq in scene_frequencies]))
                         for category in wp6.COUNT_SUPPORT}
        count_probabilities.extend({"outer_held_out_scene_id": held,
                                    "training_scene_ids": json.dumps(sorted(training.scene_id.unique().tolist())),
                                    "count_category": category, "probability": probability}
                                   for category, probability in probabilities.items())
        mask = count_rows.scene_id.eq(held)
        count_rows.loc[mask, "predicted_probability"] = count_rows.loc[mask, "stage2_mpc_count"]\
            .astype(int).map(probabilities)
        count_rows.loc[mask, "status"] = np.where(count_rows.loc[mask, "predicted_probability"].gt(0),
                                                  "SCORED", "UNSUPPORTED_COUNT_CATEGORY")
        count_rows.loc[mask, "log_score"] = np.where(
            count_rows.loc[mask, "predicted_probability"].gt(0),
            np.log(count_rows.loc[mask, "predicted_probability"].where(
                count_rows.loc[mask, "predicted_probability"].gt(0), 1.0)), np.nan)
    count_rows["training_scene_ids"] = count_rows.scene_id.map(
        lambda scene: json.dumps([s for s in sorted(windows.scene_id.unique()) if s != scene]))
    count_rows.to_csv(output / "count_window_scores.csv", index=False)
    pd.DataFrame([{
        "held_out_scene_id": held,
        "training_scene_ids": json.dumps([scene for scene in sorted(windows.scene_id.unique())
                                           if scene != held]),
        "test_window_n": int(windows.scene_id.eq(held).sum()), "fit_status": "PASS",
    } for held in sorted(windows.scene_id.unique())]).to_csv(output / "count_folds.csv", index=False)
    mpc_windows = mpcs[["run_id", "window_id", "scene_id"]].drop_duplicates().copy()
    mpc_windows["outer_held_out_scene_id"] = mpc_windows.scene_id
    mpc_windows["training_scene_ids"] = mpc_windows.scene_id.map(
        lambda scene: json.dumps([s for s in sorted(mpcs.scene_id.unique()) if s != scene]))
    mpc_windows["status"] = "SCORED"
    mpc_windows["product_score_status"] = "SCORED"
    mpc_windows["copula_score_status"] = "SCORED"
    mpc_windows["path_n"] = mpc_windows.set_index(["run_id", "window_id"]).index.map(
        mpcs.groupby(["run_id", "window_id"]).size())
    mpc_windows["product_marginal_log_score"] = 0.1
    mpc_windows["gaussian_copula_log_score"] = 0.2
    mpc_windows.to_csv(output / "mark_window_scores.csv", index=False)
    mark_scene_rows = []
    mark_scenes = sorted(mpcs.scene_id.unique())
    for scene in mark_scenes:
        scene_window_n = int(mpc_windows.scene_id.eq(scene).sum())
        mark_scene_rows.append({"outer_held_out_scene_id": scene, "scene_id": scene,
                                "window_n": scene_window_n, "status": "SCORED",
                                "product_score_status": "SCORED", "copula_score_status": "SCORED",
                                "product_marginal_mean_window_log_score": 0.1,
                                "gaussian_copula_mean_window_log_score": 0.2})
    pd.DataFrame(mark_scene_rows).to_csv(output / "mark_scene_scores.csv", index=False)
    joint_rows = []
    marks_by_key = mpc_windows.set_index(["run_id", "window_id"])
    counts_by_key = count_rows.set_index(["run_id", "window_id"])
    for window in windows.itertuples(index=False):
        identity = (str(window.run_id), str(window.window_id))
        count_row = counts_by_key.loc[identity]
        n = int(window.stage2_mpc_count)
        count_supported = (str(count_row.status) == "SCORED"
                           and np.isfinite(float(count_row.log_score)))
        mark_component = (float(marks_by_key.loc[identity, "product_marginal_log_score"])
                          if n else 0.0)
        mark_status = "SCORED" if n else "EMPTY_MARK_SET"
        count_log = float(count_row.log_score) if count_supported else np.nan
        status = ("SCORED" if count_supported else
                  "UNSUPPORTED_COUNT_CATEGORY" if str(count_row.status) == "UNSUPPORTED_COUNT_CATEGORY"
                  else "UNSCORABLE_COUNT_SCORE")
        joint_rows.append({
            "run_id": identity[0], "window_id": identity[1], "scene_id": str(window.scene_id),
            "outer_held_out_scene_id": str(window.scene_id), "stage2_mpc_count": n,
            "count_log_score": count_log, "mark_component_log_score": mark_component,
            "mark_component_status": mark_status,
            "joint_product_log_score": count_log + mark_component if count_supported else np.nan,
            "status": status,
        })
    joint_windows = pd.DataFrame(joint_rows)
    joint_windows.to_csv(output / "count_mark_joint_window_scores.csv", index=False)
    joint_scene_rows = []
    for scene, group in joint_windows.groupby("scene_id", sort=True):
        scored = group.status.eq("SCORED")
        scene_status = "SCORED" if scored.all() else (
            "UNSUPPORTED_COUNT_CATEGORY" if group.status.eq("UNSUPPORTED_COUNT_CATEGORY").any()
            else "UNSCORABLE_COUNT_SCORE")
        joint_scene_rows.append({
            "scene_id": scene, "window_n": len(group), "scored_window_n": int(scored.sum()),
            "unscorable_window_n": int((~scored).sum()), "status": scene_status,
            "joint_product_mean_log_score": (
                float(group.loc[scored, "joint_product_log_score"].mean()) if scored.all() else np.nan),
        })
    joint_scenes = pd.DataFrame(joint_scene_rows)
    joint_scenes.to_csv(output / "count_mark_joint_scene_scores.csv", index=False)
    summaries = wp6.derive_window_delay_summaries(windows, mpcs)
    folds = _window_scene_folds(windows)
    pdp_predictions, pdp_scene_scores = wp6.evaluate_cir_pdp_loso(summaries, folds)
    pdp_predictions.to_csv(output / "pdp_window_predictions.csv", index=False)
    pdp_scene_scores["training_scene_ids"] = pdp_scene_scores["training_scene_ids"].map(
        lambda scenes: json.dumps(scenes, separators=(",", ":")))
    pdp_scene_scores.to_csv(output / "pdp_scene_scores.csv", index=False)
    scene_rows = []
    for scene in mark_scenes:
        train_scenes = [s for s in mark_scenes if s != scene]
        scene_rows.append({"held_out_scene_id": scene, "training_scene_ids": json.dumps(train_scenes),
                           "test_window_n": int(mpc_windows.scene_id.eq(scene).sum()),
                           "test_mpc_n": int(mpcs.scene_id.eq(scene).sum()),
                           "fit_status": "PASS"})
    pd.DataFrame(scene_rows).to_csv(output / "mark_folds.csv", index=False)
    params = []
    for scene in mark_scenes:
        for variable in wp6.MARK_VARIABLES:
            family = wp6.MARK_FAMILIES[variable][0]
            params.append({"outer_held_out_scene_id": scene, "variable": variable,
                           "selected_family": family, "fit_status": "PASS",
                           "parameters_json": json.dumps({"loc": 0.0, "scale": 1.0}),
                           "training_scene_ids": json.dumps([s for s in mark_scenes
                                                              if s != scene])})
    pd.DataFrame(params).to_csv(output / "mark_parameters.csv", index=False)
    # Retain realistic diagnostic schemas, including the complete scene/variable/quantile tail grid.
    inner_columns = ["outer_held_out_scene_id", "variable", "family", "outer_training_scenes",
                     "inner_held_out_scene_id", "inner_training_scene_ids", "training_window_n",
                     "test_window_n", "fit_status", "score_status", "mean_window_log_score",
                     "failure_reason", "boundary_parameters"]
    tail_rows = []
    for scene in mark_scenes:
        heldout_n = int(mpcs.scene_id.eq(scene).sum())
        for variable in wp6.MARK_VARIABLES:
            family = wp6.MARK_FAMILIES[variable][0]
            for quantile in (0.01, 0.05, 0.10, 0.90, 0.95, 0.99):
                expected_n = heldout_n * min(quantile, 1.0 - quantile)
                tail_rows.append({
                    "outer_held_out_scene_id": scene, "variable": variable, "family": family,
                    "quantile": quantile, "training_predicted_quantile": 0.1,
                    "heldout_empirical_quantile": 0.2,
                    "quantile_difference_predicted_minus_empirical": -0.1,
                    "heldout_coverage_at_predicted_quantile": 0.0,
                    "expected_tail_support_n": expected_n, "heldout_n": heldout_n,
                    "status": "LOW_SUPPORT" if expected_n < 10 else "DESCRIPTIVE_DIAGNOSTIC",
                    "training_fit_used": True,
                    "uncertainty_claim": "DESCRIPTIVE_ONLY; MPC PATH ROWS ARE CLUSTERED",
                })
    for name, columns in {
        "mark_inner_family_scores.csv": inner_columns,
        "mark_failures.csv": inner_columns,
        "mark_tails.csv": ["outer_held_out_scene_id", "variable", "family", "quantile",
                           "training_predicted_quantile", "heldout_empirical_quantile",
                           "quantile_difference_predicted_minus_empirical",
                           "heldout_coverage_at_predicted_quantile", "expected_tail_support_n",
                           "heldout_n", "status", "training_fit_used", "uncertainty_claim"],
        "copula_diagnostics.csv": ["outer_held_out_scene_id", "status", "correlation_json"],
        "count_scene_scores.csv": ["scene_id", "status", "mean_log_score"],
    }.items():
        frame = pd.DataFrame(tail_rows) if name == "mark_tails.csv" else pd.DataFrame(columns=columns)
        frame.to_csv(output / name, index=False)
    pd.DataFrame(count_probabilities).to_csv(output / "count_probabilities.csv", index=False)
    scorable_joint_scenes = joint_scenes.loc[joint_scenes.status.eq("SCORED"),
                                              "joint_product_mean_log_score"]
    summary = {"window_n": len(windows), "mpc_n": len(mpcs),
               "scene_n": int(windows.scene_id.nunique()), "boundary_peak_n": int(windows.pdp_peak_at_grid_boundary.sum()),
               "count_mark_joint_scene_macro_mean_log_score": (
                   float(scorable_joint_scenes.mean()) if len(scorable_joint_scenes) else None),
               "count_mark_joint_scorable_scene_n": int(len(scorable_joint_scenes)),
               "count_mark_joint_unscorable_window_n": int(joint_windows.status.ne("SCORED").sum()),
               "mark_failure_record_n": 0,
               "mark_low_support_tail_record_n": int(sum(row["status"] == "LOW_SUPPORT" for row in tail_rows))}
    (output / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    project_root = Path(__file__).resolve().parents[3]
    code_files = {}
    for relative in ("scripts/channel_modeling/mainline_stage2_wp6.py",
                     "scripts/channel_modeling/mainline_stage2_wp3.py",
                     "scripts/channel_modeling/run_mainline_stage2_wp6.py",
                     "scripts/channel_modeling/validate_mainline_stage2_wp6.py"):
        code_path = project_root / relative
        if code_path.is_file():
            code_files[relative] = {"path": str(code_path.resolve()),
                                    "sha256": hashlib.sha256(code_path.read_bytes()).hexdigest()}
    provenance = {
        "source_inputs": {
            "features": {"path": str(features_path.resolve()), "sha256": source_hashes["features"],
                         "rows": len(windows)},
            "mpcs": {"path": str(mpc_path.resolve()), "sha256": source_hashes["mpcs"],
                     "rows": len(mpcs)},
        },
        "code_root": str(project_root.resolve()),
        "code_files": code_files,
        "population_scope": "fixture",
    }
    (output / "input_code_manifest.json").write_text(json.dumps(provenance), encoding="utf-8")
    (output / "WP6_联合统计信道模型科研报告.md").write_text("fixture report", encoding="utf-8")
    (output / "execution_record.json").write_text(json.dumps({"status": "COMPLETE"}), encoding="utf-8")
    return validator, features_path, mpc_path, output, source_hashes


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


class WP6RunnerAndIndependentValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wp6 = _load_module()
        cls.runner = _load_path(RUNNER_PATH, "run_mainline_stage2_wp6_tests")
        cls.validator = _load_path(VALIDATOR_PATH, "validate_mainline_stage2_wp6_tests")

    def _runner_api(self, name):
        self.assertIsNotNone(self.runner, "WP6 runner has not been implemented")
        fn = getattr(self.runner, name, None)
        self.assertTrue(callable(fn), f"required runner API is missing: {name}")
        return fn

    def test_runner_refuses_existing_result_directory(self):
        create = self._runner_api("create_new_output_directory")
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "existing"
            target.mkdir()
            marker = target / "keep.txt"
            marker.write_text("do not overwrite", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                create(target)
            self.assertEqual(marker.read_text(encoding="utf-8"), "do not overwrite")

    def test_runner_manifest_binds_fixed_production_inputs_and_code(self):
        build = self._runner_api("build_provenance_manifest")
        root = Path(__file__).resolve().parents[3]
        inputs = {
            "features_sha256": self.wp6.FEATURES_SHA256,
            "mpc_sha256": self.wp6.MPC_SHA256,
            "features_path": "frozen-features.csv", "mpc_path": "frozen-mpcs.csv",
            "features_rows": 7847, "mpc_rows": 8914,
            "window_key": ["run_id", "window_id"],
            "mpc_key": ["run_id", "window_id", "path_id"],
            "population_scope": "fixture manifest test",
        }
        manifest = build(root, inputs)
        self.assertEqual(manifest["source_inputs"]["features"]["sha256"], self.wp6.FEATURES_SHA256)
        self.assertEqual(manifest["source_inputs"]["mpcs"]["sha256"], self.wp6.MPC_SHA256)
        self.assertIn("mainline_stage2_wp6.py", manifest["code_files"])
        for record in manifest["code_files"].values():
            self.assertEqual(len(record["sha256"]), 64)
        bad = dict(inputs, features_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "SHA|pin|frozen"):
            build(root, bad)

    def test_runner_keeps_full_window_and_mpc_row_counts(self):
        summarize = self._runner_api("summarize_population")
        windows, mpcs = _fixture_frames()
        summary = summarize(windows, mpcs)
        self.assertEqual(summary["window_n"], 3)
        self.assertEqual(summary["mpc_n"], 3)
        self.assertEqual(summary["zero_mpc_selected_window_n"], 1)

    def test_runner_derives_copula_delta_from_scene_score_contract(self):
        derive = self._runner_api("add_copula_score_delta")
        scene_scores = pd.DataFrame([
            {"status": "SCORED", "product_marginal_mean_window_log_score": -2.0,
             "gaussian_copula_mean_window_log_score": -1.5},
            {"status": "UNSCORABLE_MARGINAL_FIT", "product_marginal_mean_window_log_score": np.nan,
             "gaussian_copula_mean_window_log_score": np.nan},
        ])
        result = derive(scene_scores)
        self.assertAlmostEqual(result.loc[0, "copula_minus_product_score"], 0.5)
        self.assertTrue(pd.isna(result.loc[1, "copula_minus_product_score"]))
        self.assertNotIn("copula_minus_product_score", scene_scores.columns)

    def test_joint_count_mark_scores_cover_selected_windows_and_scene_balance(self):
        score = self._runner_api("build_joint_count_mark_scores")
        selected = pd.DataFrame([
            {"run_id": "R1", "window_id": "W0", "scene_id": "S1", "stage2_mpc_count": 0},
            {"run_id": "R1", "window_id": "W1", "scene_id": "S1", "stage2_mpc_count": 2},
            {"run_id": "R2", "window_id": "W2", "scene_id": "S2", "stage2_mpc_count": 1},
        ])
        count = selected.copy()
        count["outer_held_out_scene_id"] = count.scene_id
        count["status"] = "SCORED"
        count["log_score"] = [-0.2, -1.0, -0.7]
        marks = pd.DataFrame([
            {"run_id": "R1", "window_id": "W1", "scene_id": "S1", "path_n": 2,
             "status": "SCORED", "product_marginal_log_score": -3.0},
            {"run_id": "R2", "window_id": "W2", "scene_id": "S2", "path_n": 1,
             "status": "SCORED", "product_marginal_log_score": -2.0},
        ])
        windows, scenes = score(count, marks, selected)
        self.assertEqual(len(windows), 3)
        zero = windows.loc[windows.window_id.eq("W0")].iloc[0]
        self.assertEqual(zero.mark_component_log_score, 0.0)
        self.assertEqual(zero.status, "SCORED")
        self.assertAlmostEqual(zero.joint_product_log_score, -0.2)
        self.assertAlmostEqual(windows.loc[windows.window_id.eq("W1"),
                                            "joint_product_log_score"].iloc[0], -4.0)
        scene_map = scenes.set_index("scene_id").joint_product_mean_log_score
        self.assertAlmostEqual(scene_map["S1"], (-0.2 - 4.0) / 2)
        self.assertAlmostEqual(scene_map["S2"], -2.7)
        self.assertAlmostEqual(scenes.joint_product_mean_log_score.mean(), -2.4)

    def test_nested_mark_loso_keeps_product_score_when_copula_is_unavailable(self):
        frame = _mark_frame(scene_n=3, windows_per_scene=2, paths_per_window=2)
        selected = {"excess_delay_chips": "lognormal", "doppler_offset_hz": "student_t",
                    "relative_power_db": "normal"}
        empty = pd.DataFrame()
        fitted = {
            "excess_delay_chips": {"status": "PASS", "family": "lognormal",
                                   "parameters": {"shape": 0.5, "scale": 0.2, "loc": 0.0}},
            "doppler_offset_hz": {"status": "PASS", "family": "student_t",
                                  "parameters": {"df": 5.0, "loc": 0.0, "scale": 1.0}},
            "relative_power_db": {"status": "PASS", "family": "normal",
                                  "parameters": {"loc": 0.0, "scale": 1.0}},
        }
        with patch.object(self.wp6, "select_mark_families_nested",
                          return_value=(selected, empty, empty)), \
             patch.object(self.wp6, "_fit_selected_marginals", return_value=fitted), \
             patch.object(self.wp6, "fit_scene_balanced_copula",
                          return_value=(None, {"status": "UNESTIMABLE_SCENE_PAIRWISE_KENDALL"})):
            result = self.wp6.evaluate_nested_mark_loso(frame)
        scores = result["window_scores"]
        self.assertEqual(len(scores), frame[["run_id", "window_id"]].drop_duplicates().shape[0])
        self.assertTrue(scores.status.eq("PRODUCT_ONLY_COPULA_UNAVAILABLE").all())
        self.assertTrue(np.isfinite(scores.product_marginal_log_score).all())
        self.assertTrue(scores.gaussian_copula_log_score.isna().all())
        self.assertTrue(result["folds"].copula_status.eq("UNESTIMABLE_SCENE_PAIRWISE_KENDALL").all())

    def test_validator_recomputes_counts_and_delay_moments_without_model_module(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNotNone(self.validator, "WP6 independent validator has not been implemented")
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            self.assertIsNotNone(validator)
            self.assertNotIn("mainline_stage2_wp6", validator.__dict__)
            result = validator.validate_result_package(
                output, features, mpcs,
                expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                   "count_support": (0, 1, 2, 3)})
            self.assertEqual(result["status"], "PASS_WITH_LIMITATIONS")
            self.assertEqual(result["window_n"], 3)
            self.assertEqual(result["mpc_n"], 3)

    def test_validator_rejects_positive_manifest_row_count_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            manifest_path = output / "input_code_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_inputs"]["features"]["rows"] += 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "row count differs"):
                validator.validate_result_package(
                    output, features, mpcs,
                    expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                    expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                       "count_support": (0, 1, 2, 3)})

    def test_validator_rejects_nested_failure_row_omitted_from_failure_table(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            row = {
                "outer_held_out_scene_id": "S1", "variable": "excess_delay_chips",
                "family": "gamma", "outer_training_scenes": json.dumps(["S2"]),
                "inner_held_out_scene_id": "S2", "inner_training_scene_ids": json.dumps([]),
                "training_window_n": 1, "test_window_n": 2, "fit_status": "FAILED_OPTIMIZER",
                "score_status": "FAILED_OPTIMIZER", "mean_window_log_score": np.nan,
                "failure_reason": "synthetic optimizer boundary", "boundary_parameters": json.dumps([]),
            }
            inner_path = output / "mark_inner_family_scores.csv"
            failures_path = output / "mark_failures.csv"
            pd.DataFrame([row]).to_csv(inner_path, index=False)
            pd.DataFrame([row]).to_csv(failures_path, index=False)
            summary_path = output / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["mark_failure_record_n"] = 1
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            validator.validate_result_package(
                output, features, mpcs,
                expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                   "count_support": (0, 1, 2, 3)})
            pd.DataFrame(columns=list(row)).to_csv(failures_path, index=False)
            with self.assertRaisesRegex(ValueError, "failure|non-PASS|diagnostic"):
                validator.validate_result_package(
                    output, features, mpcs,
                    expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                    expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                       "count_support": (0, 1, 2, 3)})

    def test_validator_rejects_omitted_tail_support_record(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            path = output / "mark_tails.csv"
            tails = pd.read_csv(path)
            mpc_scene_n = pd.read_csv(mpcs).scene_id.nunique()
            self.assertEqual(len(tails), mpc_scene_n * len(self.wp6.MARK_VARIABLES) * 6)
            tails.iloc[:-1].to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "tail|quantile|diagnostic"):
                validator.validate_result_package(
                    output, features, mpcs,
                    expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                    expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                       "count_support": (0, 1, 2, 3)})

    def test_validator_recomputes_selected_window_count_mark_joint_score(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(
                Path(temp), self.wp6, source_frames=_joint_score_fixture_frames())
            path = output / "count_mark_joint_window_scores.csv"
            joint = pd.read_csv(path)
            scored_index = joint.index[joint.status.eq("SCORED")][0]
            joint.loc[scored_index, "joint_product_log_score"] += 0.25
            joint.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "factorized joint score"):
                validator.validate_result_package(
                    output, features, mpcs,
                    expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                    expected_contract={"window_n": 3, "mpc_n": 2, "scene_n": 2,
                                       "count_support": (0, 1, 2, 3)})

    def test_validator_accepts_csv_float_roundtrip_error_in_frozen_pdp_attribute(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            path = output / "selected_window_delay_summaries.csv"
            frame = pd.read_csv(path)
            frame.loc[0, "pdp_peak_minus_sage_direct_delay_samples"] += 1e-13
            frame.to_csv(path, index=False)
            result = validator.validate_result_package(
                output, features, mpcs,
                expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                   "count_support": (0, 1, 2, 3)})
            self.assertEqual(result["status"], "PASS_WITH_LIMITATIONS")

    def test_validator_records_its_own_version_without_requiring_it_to_match_run_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            manifest_path = output / "input_code_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            verifier = next(name for name in manifest["code_files"]
                            if Path(name).name == "validate_mainline_stage2_wp6.py")
            manifest["code_files"][verifier]["sha256"] = "f" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = validator.validate_result_package(
                output, features, mpcs,
                expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                   "count_support": (0, 1, 2, 3)})
            expected_validator_sha = hashlib.sha256(VALIDATOR_PATH.read_bytes()).hexdigest()
            self.assertEqual(result["validator_sha256"], expected_validator_sha)

    def test_validator_uses_count_fold_table_without_duplicate_window_training_lists(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            path = output / "count_window_scores.csv"
            frame = pd.read_csv(path).drop(columns="training_scene_ids")
            frame.to_csv(path, index=False)
            result = validator.validate_result_package(
                output, features, mpcs,
                expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                   "count_support": (0, 1, 2, 3)})
            self.assertEqual(result["status"], "PASS_WITH_LIMITATIONS")

    def test_validator_rejects_count_fold_scene_that_does_not_match_source_window(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            path = output / "count_window_scores.csv"
            frame = pd.read_csv(path)
            first = frame.index[(frame.run_id.eq("R1")) & (frame.window_id.eq(1))][0]
            second = frame.index[(frame.run_id.eq("R2")) & (frame.window_id.eq(1))][0]
            frame.loc[[first, second], ["scene_id", "outer_held_out_scene_id"]] = \
                frame.loc[[second, first], ["scene_id", "outer_held_out_scene_id"]].to_numpy()
            frame.loc[first, ["predicted_probability", "status", "log_score"]] = [0.5, "SCORED", np.log(0.5)]
            frame.loc[second, ["predicted_probability", "status", "log_score"]] = [1.0, "SCORED", 0.0]
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "source window scene"):
                validator.validate_result_package(
                    output, features, mpcs,
                    expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                    expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                       "count_support": (0, 1, 2, 3)})

    def test_validator_recomputes_each_pdp_scene_score_from_window_predictions(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            path = output / "pdp_scene_scores.csv"
            scores = pd.read_csv(path)
            scores.loc[0, "rmse"] += 0.25
            scores.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "PDP scene score mismatch"):
                validator.validate_result_package(
                    output, features, mpcs,
                    expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                    expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                       "count_support": (0, 1, 2, 3)})

    def test_validator_rejects_material_frozen_pdp_attribute_change(self):
        with tempfile.TemporaryDirectory() as temp:
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            path = output / "selected_window_delay_summaries.csv"
            frame = pd.read_csv(path)
            frame.loc[0, "pdp_peak_minus_sage_direct_delay_samples"] += 1e-4
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "source attribute mismatch"):
                validator.validate_result_package(
                    output, features, mpcs,
                    expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                    expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                       "count_support": (0, 1, 2, 3)})

    def test_validator_detects_corrupted_output_identity_or_fold(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNotNone(self.validator, "WP6 independent validator has not been implemented")
            validator, features, mpcs, output, hashes = _build_validator_fixture(Path(temp), self.wp6)
            predictions_path = output / "pdp_window_predictions.csv"
            predictions = pd.read_csv(predictions_path)
            predictions.loc[0, "outer_held_out_scene_id"] = "S9"
            predictions.to_csv(predictions_path, index=False)
            with self.assertRaisesRegex(ValueError, "held|fold|scene|identity"):
                validator.validate_result_package(
                    output, features, mpcs,
                    expected_hashes={"features": hashes["features"], "mpcs": hashes["mpcs"]},
                    expected_contract={"window_n": 3, "mpc_n": 3, "scene_n": 2,
                                       "count_support": (0, 1, 2, 3)})
