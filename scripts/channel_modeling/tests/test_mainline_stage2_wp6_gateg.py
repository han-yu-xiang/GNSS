"""Synthetic-only tests for the Gate G quantized-delay supplement."""

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import integrate, stats


MODULE_PATH = Path(__file__).resolve().parents[1] / "mainline_stage2_wp6_gateg.py"
if str(MODULE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_PATH.parent))

import validate_mainline_stage2_wp6_gateg as independent_validator


def _load_module():
    if not MODULE_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("mainline_stage2_wp6_gateg", MODULE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuantizedDelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = _load_module()

    def _fn(self, name):
        self.assertIsNotNone(self.api, "Gate G supplement module is not implemented")
        fn = getattr(self.api, name, None)
        self.assertTrue(callable(fn), f"missing Gate G API: {name}")
        return fn

    def test_delay_grid_cells_use_lower_selection_bound(self):
        cells = self._fn("delay_grid_cells")
        lower, upper = cells(np.array([0.10, 0.11, 0.12]))
        np.testing.assert_allclose(lower, [0.10, 0.105, 0.115], rtol=0, atol=1e-14)
        np.testing.assert_allclose(upper, [0.105, 0.115, 0.125], rtol=0, atol=1e-14)

    def test_off_lattice_delay_is_rejected(self):
        cells = self._fn("delay_grid_cells")
        with self.assertRaisesRegex(ValueError, "lattice|grid"):
            cells(np.array([0.10, 0.105]))

    def test_truncated_delay_bin_probabilities_normalize_over_grid(self):
        mass = self._fn("delay_grid_mass")
        grid = np.arange(0.10, 12.001, 0.01)
        parameters = {"shape": 0.55, "scale": 0.45}
        probabilities = mass("lognormal", grid, parameters)
        self.assertTrue(np.isfinite(probabilities).all())
        self.assertTrue((probabilities > 0).all())
        self.assertAlmostEqual(float(probabilities.sum()), 1.0, places=7)

    def test_tail_interval_probabilities_remain_finite_in_log_space(self):
        interval = self._fn("_family_log_interval")
        normal = self._fn("_normal_log_interval")
        lognormal_tail = interval("lognormal", np.array([8.0]), np.array([8.01]),
                                  {"shape": 0.7, "scale": 0.5})
        normal_tail = normal(np.array([8.0]), np.array([8.01]))
        self.assertTrue(np.isfinite(lognormal_tail).all())
        self.assertTrue(np.isfinite(normal_tail).all())
        self.assertLess(float(normal_tail[0]), -30.0)

    def test_conditional_delay_cdf_respects_truncation_and_scalar_input(self):
        cdf = self._fn("_conditional_delay_cdf")
        parameters = {"shape": 0.6, "scale": 0.4}
        values = cdf("lognormal", np.array([0.1, 0.2, 0.4]), parameters)
        self.assertEqual(float(values[0]), 0.0)
        self.assertTrue((np.diff(values) > 0).all())
        self.assertAlmostEqual(float(cdf("lognormal", 0.1, parameters)), 0.0, places=14)

    def test_discrete_and_continuous_product_score_is_finite_for_ties(self):
        score = self._fn("product_mark_log_score")
        fits = {
            "excess_delay_chips": {"family": "lognormal", "status": "PASS",
                                   "parameters": {"shape": 0.6, "scale": 0.4}},
            "doppler_offset_hz": {"family": "normal", "status": "PASS",
                                  "parameters": {"loc": 0.0, "scale": 20.0}},
            "relative_power_db": {"family": "student_t", "status": "PASS",
                                   "parameters": {"df": 6.0, "loc": -8.0, "scale": 3.0}},
        }
        frame = pd.DataFrame({
            "run_id": ["R1", "R1", "R2"], "window_id": ["1", "2", "1"],
            "path_id": ["2", "2", "2"], "scene_id": ["S1", "S1", "S2"],
            "excess_delay_chips": [0.10, 0.10, 0.11],
            "doppler_offset_hz": [1.0, 1.0, -2.0],
            "relative_power_db": [-8.0, -8.0, -9.0],
        })
        values = score(fits, frame)
        self.assertTrue(np.isfinite(values).all())
        self.assertEqual(values[0], values[1])

    def test_identity_mixed_copula_equals_product_discrete_score(self):
        product = self._fn("product_mark_log_score")
        mixed = self._fn("mixed_gaussian_copula_log_score")
        fits = {
            "excess_delay_chips": {"family": "lognormal", "status": "PASS",
                                   "parameters": {"shape": 0.6, "scale": 0.4}},
            "doppler_offset_hz": {"family": "normal", "status": "PASS",
                                  "parameters": {"loc": 0.0, "scale": 20.0}},
            "relative_power_db": {"family": "normal", "status": "PASS",
                                  "parameters": {"loc": -8.0, "scale": 3.0}},
        }
        frame = pd.DataFrame({
            "run_id": ["R1", "R1", "R2"], "window_id": ["1", "2", "1"],
            "path_id": ["2", "2", "2"], "scene_id": ["S1", "S1", "S2"],
            "excess_delay_chips": [0.10, 0.10, 0.11],
            "doppler_offset_hz": [1.0, 1.0, -2.0],
            "relative_power_db": [-8.0, -8.0, -9.0],
        })
        np.testing.assert_allclose(mixed(fits, np.eye(3), frame), product(fits, frame),
                                   rtol=0, atol=2e-12)

    def test_continuous_pair_copula_factor_matches_hand_density(self):
        factor = self._fn("continuous_pair_copula_log_factor")
        z = np.array([[0.25, -0.8]])
        rho = 0.4
        expected = stats.multivariate_normal.logpdf(
            z[0], mean=np.zeros(2), cov=[[1.0, rho], [rho, 1.0]])
        expected -= stats.norm.logpdf(z[0]).sum()
        actual = factor(z, rho)
        self.assertAlmostEqual(float(actual[0]), float(expected), places=12)

    def test_mixed_interval_factor_matches_numerical_gaussian_integration(self):
        factor = self._fn("mixed_interval_copula_log_factor")
        corr = np.array([[1.0, 0.35, -0.15],
                         [0.35, 1.0, 0.45],
                         [-0.15, 0.45, 1.0]])
        lower, upper = -0.25, 0.42
        z_cont = np.array([[0.3, -0.6]])
        actual = float(factor(np.array([lower]), np.array([upper]), z_cont, corr)[0])
        covariance = corr[1:, 1:]
        z = z_cont[0]
        cond_mean = corr[0, 1:] @ np.linalg.solve(covariance, z)
        cond_var = 1.0 - corr[0, 1:] @ np.linalg.solve(covariance, corr[1:, 0])
        numerator = integrate.quad(
            lambda value: stats.multivariate_normal.pdf([value, *z], mean=np.zeros(3), cov=corr),
            lower, upper, epsabs=1e-12)[0]
        denominator = stats.norm.cdf(upper) - stats.norm.cdf(lower)
        expected = np.log(numerator) - np.log(denominator) - stats.norm.logpdf(z).sum()
        # The closed form is equivalent to the integral above; keep the
        # conditional-normal values explicit to catch a wrong conditioning set.
        expected_conditional = (stats.multivariate_normal.logpdf(z, mean=np.zeros(2), cov=covariance)
                                - stats.norm.logpdf(z).sum()
                                + np.log(stats.norm.cdf(upper, loc=cond_mean, scale=np.sqrt(cond_var))
                                         - stats.norm.cdf(lower, loc=cond_mean, scale=np.sqrt(cond_var)))
                                - np.log(denominator))
        self.assertAlmostEqual(actual, float(expected), places=9)
        self.assertAlmostEqual(actual, float(expected_conditional), places=9)

    def test_independent_reference_recomputes_mixed_score(self):
        scorer = self._fn("mixed_gaussian_copula_log_score")
        fits = {
            "excess_delay_chips": {"family": "lognormal", "status": "PASS",
                                   "parameters": {"shape": 0.6, "scale": 0.4}},
            "doppler_offset_hz": {"family": "normal", "status": "PASS",
                                  "parameters": {"loc": 0.0, "scale": 20.0}},
            "relative_power_db": {"family": "student_t", "status": "PASS",
                                   "parameters": {"df": 6.0, "loc": -8.0, "scale": 3.0}},
        }
        frame = pd.DataFrame({
            "run_id": ["R1"], "window_id": ["1"], "path_id": ["2"], "scene_id": ["S1"],
            "excess_delay_chips": [0.13], "doppler_offset_hz": [15.0],
            "relative_power_db": [-11.0],
        })
        corr = np.array([[1.0, 0.25, -0.1], [0.25, 1.0, 0.3], [-0.1, 0.3, 1.0]])
        implementation = float(scorer(fits, corr, frame)[0])
        reference_fit = {key: {"family": value["family"], "parameters": value["parameters"]}
                         for key, value in fits.items()}
        reference = independent_validator._ref_mixed_log_score(
            next(frame.itertuples(index=False)), reference_fit, corr)
        self.assertAlmostEqual(implementation, reference, places=8)

    def test_validator_binds_frozen_mark_attributes_to_saved_path_scores(self):
        bind = getattr(independent_validator, "_bind_source_marks", None)
        self.assertTrue(callable(bind), "validator must attach source mark values by exact MPC identity")
        scores = pd.DataFrame({
            "run_id": ["R1"], "window_id": ["1"], "path_id": ["2"],
            "scene_id": ["S1"], "outer_held_out_scene_id": ["S1"], "n_mpc": [1],
        })
        source = scores[["run_id", "window_id", "path_id", "scene_id"]].copy()
        source["excess_delay_chips"] = 0.1
        source["doppler_offset_hz"] = 2.0
        source["relative_power_db"] = -5.0
        bound = bind(scores, source)
        self.assertEqual(float(bound.loc[0, "excess_delay_chips"]), 0.1)
        with self.assertRaisesRegex(ValueError, "identity|join|match"):
            bind(scores, source.iloc[0:0])

    def test_validator_reads_unstratified_copula_as_all_count(self):
        load = getattr(independent_validator, "_load_corr", None)
        self.assertTrue(callable(load), "validator correlation reader must be available")
        diagnostics = pd.DataFrame([{
            "outer_held_out_scene_id": "S1", "model": "C0", "count_condition": np.nan,
            "status": "PASS", "correlation_json": "[[1,0,0],[0,1,0],[0,0,1]]",
        }, {
            "outer_held_out_scene_id": "S1", "model": "C1", "count_condition": 2.0,
            "status": "PASS", "correlation_json": "[[1,0,0],[0,1,0],[0,0,1]]",
        }])
        self.assertEqual(np.asarray(load(diagnostics, "S1", "C0", "ALL")).shape, (3, 3))
        self.assertEqual(np.asarray(load(diagnostics, "S1", "C1", "2")).shape, (3, 3))

    def test_validator_identity_check_is_dtype_independent(self):
        same = getattr(independent_validator, "_same_identity_and_counts", None)
        self.assertTrue(callable(same))
        left = pd.DataFrame({"run_id": pd.Series(["R1"], dtype="string"),
                             "window_id": pd.Series(["01"], dtype="string"),
                             "scene_id": pd.Series(["S1"], dtype="string"), "n_mpc": [2]})
        right = pd.DataFrame({"run_id": ["R1"], "window_id": ["01"],
                              "scene_id": ["S1"], "n_mpc": [2.0]})
        self.assertTrue(same(left, right, ["run_id", "window_id", "scene_id"], "n_mpc"))
        right.loc[0, "window_id"] = "1"
        self.assertFalse(same(left, right, ["run_id", "window_id", "scene_id"], "n_mpc"))

    def test_invalid_correlation_is_rejected(self):
        mixed = self._fn("mixed_gaussian_copula_log_score")
        frame = pd.DataFrame({
            "run_id": ["R1"], "window_id": ["1"], "path_id": ["2"], "scene_id": ["S1"],
            "excess_delay_chips": [0.1], "doppler_offset_hz": [0.0],
            "relative_power_db": [-8.0],
        })
        fits = {
            "excess_delay_chips": {"family": "lognormal", "status": "PASS",
                                   "parameters": {"shape": 0.6, "scale": 0.4}},
            "doppler_offset_hz": {"family": "normal", "status": "PASS",
                                  "parameters": {"loc": 0.0, "scale": 20.0}},
            "relative_power_db": {"family": "normal", "status": "PASS",
                                  "parameters": {"loc": -8.0, "scale": 3.0}},
        }
        invalid = np.array([[1.0, 0.95, 0.95], [0.95, 1.0, -0.95], [0.95, -0.95, 1.0]])
        with self.assertRaisesRegex(ValueError, "positive definite|correlation"):
            mixed(fits, invalid, frame)

    def test_path_rank_uses_frozen_ids_and_rejects_identity_or_delay_mismatch(self):
        prepare = self._fn("prepare_ranked_marks")
        frame = pd.DataFrame([
            {"run_id": "R1", "window_id": "1", "path_id": "2", "scene_id": "S1",
             "selected_L": 3, "excess_delay_chips": 0.1},
            {"run_id": "R1", "window_id": "1", "path_id": "3", "scene_id": "S1",
             "selected_L": 3, "excess_delay_chips": 0.2},
        ])
        ranked = prepare(frame.iloc[::-1].reset_index(drop=True))
        self.assertEqual(ranked.mpc_rank.tolist(), [1, 2])
        with self.assertRaisesRegex(ValueError, "identity|path_id|sequence|selected_L"):
            prepare(frame.iloc[[0]].copy())
        wrong_delay = frame.copy()
        wrong_delay.loc[wrong_delay.path_id.eq("3"), "excess_delay_chips"] = 0.05
        with self.assertRaisesRegex(ValueError, "order|delay"):
            prepare(wrong_delay)

    def test_scene_score_deltas_use_exact_paired_window_support(self):
        scorer = self._fn("_window_scene_scores")
        models = ("M0_independent", "M1_count_conditional", "C0_mixed_copula",
                  "C1_count_mixed_copula")
        frame = pd.DataFrame({
            "run_id": ["R1"] * 3, "window_id": ["1", "2", "3"],
            "scene_id": ["S1"] * 3, "n_mpc": [1, 1, 1],
            "M0_independent": [0.0, 1.0, 2.0],
            "M1_count_conditional": [1.0, 3.0, np.nan],
            "C0_mixed_copula": [np.nan, 2.0, 3.0],
            "C1_count_mixed_copula": [0.0, np.nan, 5.0],
        })
        windows, scenes = scorer(frame, models)
        row = scenes.iloc[0]
        self.assertEqual(row.M1_minus_M0_paired_window_n, 2)
        self.assertAlmostEqual(row.M1_minus_M0_nats_per_mpc, 1.5)
        self.assertEqual(row.C0_minus_M0_paired_window_n, 2)
        self.assertAlmostEqual(row.C0_minus_M0_nats_per_mpc, 1.0)
        self.assertEqual(row.C1_minus_M1_paired_window_n, 1)
        self.assertAlmostEqual(row.C1_minus_M1_nats_per_mpc, -1.0)
        self.assertEqual(windows.M1_count_conditional_status.tolist(), ["SCORED", "SCORED", "UNSCORABLE"])

    def test_count_support_counts_selected_windows_not_mpc_rows(self):
        build = self._fn("build_count_scene_support")
        rows = []
        for scene in ("S1", "S2"):
            for count in (1, 2, 3):
                for window in ("1", "2"):
                    for rank in range(1, count + 1):
                        rows.append({"run_id": f"R-{scene}", "window_id": f"{count}-{window}",
                                     "path_id": str(rank + 1), "scene_id": scene,
                                     "selected_L": count + 1, "excess_delay_chips": .1 + rank * .1,
                                     "doppler_offset_hz": rank * 2.0,
                                     "relative_power_db": -rank * 3.0})
        support = build(pd.DataFrame(rows))
        self.assertEqual(support.groupby("n_mpc").selected_mpc_window_n.sum().to_dict(),
                         {1: 4, 2: 4, 3: 4})
        self.assertEqual(support.groupby("n_mpc").mpc_row_n.sum().to_dict(),
                         {1: 4, 2: 8, 3: 12})


if __name__ == "__main__":
    unittest.main()
