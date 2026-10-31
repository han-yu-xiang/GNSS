"""Focused synthetic tests for fixed-bin Gate G probability scoring."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
from scipy import integrate, stats


MODULE_PATH = Path(__file__).resolve().parents[1] / "mainline_stage2_wp6_fixed_doppler.py"
if str(MODULE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_PATH.parent))


def _load_module():
    if not MODULE_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("mainline_stage2_wp6_fixed_doppler", MODULE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedDopplerBinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = _load_module()

    def _fn(self, name):
        self.assertIsNotNone(self.api, "fixed-bin Gate G module is not implemented")
        fn = getattr(self.api, name, None)
        self.assertTrue(callable(fn), f"missing fixed-bin API: {name}")
        return fn

    def test_zero_centered_half_open_edges_assign_ties_to_upper_bin(self):
        indices = self._fn("doppler_bin_indices")
        values = np.array([-10.0, -7.5, -2.5, 0.0, 2.5, 7.5, 10.0])
        np.testing.assert_array_equal(indices(values, 5.0), [-2, -1, 0, 0, 1, 2, 2])

    def test_values_adjacent_to_positive_and_negative_edges_stay_in_correct_bins(self):
        indices = self._fn("doppler_bin_indices")
        below_pos = np.nextafter(2.5, -np.inf)
        above_pos = np.nextafter(2.5, np.inf)
        below_neg = np.nextafter(-2.5, -np.inf)
        above_neg = np.nextafter(-2.5, np.inf)
        got = indices(np.array([below_pos, 2.5, above_pos, below_neg, -2.5, above_neg]), 5.0)
        np.testing.assert_array_equal(got, [0, 1, 1, -1, 0, 0])

    def test_bin_cells_are_half_open_and_centered_at_zero(self):
        cells = self._fn("doppler_bin_cells")
        lower, upper = cells(np.array([-1, 0, 1]), 5.0)
        np.testing.assert_array_equal(lower, [-7.5, -2.5, 2.5])
        np.testing.assert_array_equal(upper, [-2.5, 2.5, 7.5])

    def test_invalid_bin_width_is_rejected(self):
        indices = self._fn("doppler_bin_indices")
        for width in (0.0, -5.0, np.inf, np.nan):
            with self.subTest(width=width), self.assertRaisesRegex(ValueError, "width"):
                indices(np.array([0.0]), width)

    def test_normal_and_student_t_bin_masses_normalize_over_full_partition(self):
        log_mass = self._fn("doppler_bin_log_mass")
        centers = np.arange(-4000, 4001, dtype=float) * 5.0
        normal = np.exp(log_mass("normal", centers, 5.0, {"loc": 3.0, "scale": 24.0}))
        student = np.exp(log_mass("student_t", centers, 5.0,
                                  {"df": 5.0, "loc": -2.0, "scale": 18.0}))
        self.assertAlmostEqual(float(normal.sum()), 1.0, places=12)
        self.assertAlmostEqual(float(student.sum()), 1.0, places=12)
        self.assertTrue(np.isfinite(log_mass("normal", np.array([10000.0]), 5.0,
                                             {"loc": 0.0, "scale": 2.0})).all())

    def test_grouped_fit_recovers_synthetic_normal_and_student_t_location_scale(self):
        fit_bins = self._fn("fit_doppler_bins")
        rng = np.random.default_rng(63017)
        rows = []
        for scene, family, loc, scale, df in (
            ("S1", "normal", 7.0, 18.0, None),
            ("S2", "normal", 7.0, 18.0, None),
            ("S3", "student_t", -4.0, 14.0, 6.0),
            ("S4", "student_t", -4.0, 14.0, 6.0),
        ):
            sample = (rng.normal(loc, scale, 8000) if family == "normal"
                      else -4.0 + 14.0 * rng.standard_t(df, 8000))
            bins = np.floor(sample / 5.0 + 0.5).astype(int)
            for index, bin_id in enumerate(bins):
                rows.append({"scene_id": scene, "run_id": f"R-{scene}",
                             "window_id": str(index + 1), "doppler_offset_hz": 5.0 * bin_id})
        frame = pd.DataFrame(rows)
        normal_fit = fit_bins(frame.loc[frame.scene_id.isin(["S1", "S2"])], "normal", 5.0)
        student_fit = fit_bins(frame.loc[frame.scene_id.isin(["S3", "S4"])], "student_t", 5.0)
        self.assertEqual(normal_fit["status"], "PASS", normal_fit)
        self.assertEqual(student_fit["status"], "PASS", student_fit)
        self.assertAlmostEqual(normal_fit["parameters"]["loc"], 7.0, delta=1.0)
        self.assertAlmostEqual(normal_fit["parameters"]["scale"], 18.0, delta=1.2)
        self.assertAlmostEqual(student_fit["parameters"]["loc"], -4.0, delta=1.5)
        self.assertAlmostEqual(student_fit["parameters"]["scale"], 14.0, delta=2.0)
        self.assertTrue(2.1 < student_fit["parameters"]["df"] < 20.0)

    def test_bivariate_normal_rectangle_matches_independent_quadrature(self):
        rectangle = self._fn("normal_rectangle_log_probability")
        lower = np.array([[-0.8, -0.2]])
        upper = np.array([[0.5, 1.1]])
        mean = np.array([[0.2, -0.4]])
        covariance = np.array([[1.0, 0.35], [0.35, 1.2]])
        actual = float(np.exp(rectangle(lower, upper, mean, covariance)[0]))
        sd_x = np.sqrt(covariance[0, 0])
        conditional_sd = np.sqrt(covariance[1, 1] - covariance[1, 0] ** 2 / covariance[0, 0])
        conditional_slope = covariance[1, 0] / covariance[0, 0]
        expected = integrate.quad(
            lambda x: stats.norm.pdf(x, loc=mean[0, 0], scale=sd_x)
            * (stats.norm.cdf(upper[0, 1], loc=mean[0, 1] + conditional_slope * (x - mean[0, 0]),
                              scale=conditional_sd)
               - stats.norm.cdf(lower[0, 1], loc=mean[0, 1] + conditional_slope * (x - mean[0, 0]),
                                scale=conditional_sd)),
            lower[0, 0], upper[0, 0], epsabs=1e-13, epsrel=1e-13)[0]
        self.assertAlmostEqual(actual, expected, delta=2e-11)

    def test_correlated_rectangle_probabilities_normalize_over_complete_partition(self):
        rectangle = self._fn("normal_rectangle_log_probability")
        edges = [-np.inf, -1.1, 0.25, np.inf]
        covariance = np.array([[1.0, -0.55], [-0.55, 1.0]])
        for mean in (np.array([[0.0, 0.0]]), np.array([[0.4, -0.7]])):
            total = 0.0
            for i in range(len(edges) - 1):
                for j in range(len(edges) - 1):
                    lower = np.array([[edges[i], edges[j]]])
                    upper = np.array([[edges[i + 1], edges[j + 1]]])
                    total += float(np.exp(rectangle(lower, upper, mean, covariance)[0]))
            self.assertAlmostEqual(total, 1.0, delta=3e-10)

    def test_invalid_and_numerically_singular_rectangle_covariances_fail_closed(self):
        rectangle = self._fn("normal_rectangle_log_probability")
        lower = np.array([[-0.2, -0.2]])
        upper = np.array([[0.2, 0.2]])
        mean = np.array([[0.0, 0.0]])
        for covariance in (np.array([[1.0, 1.1], [1.1, 1.0]]),
                           np.array([[1.0, 1.0 - 1e-14], [1.0 - 1e-14, 1.0]])):
            with self.subTest(covariance=covariance.tolist()), self.assertRaisesRegex(
                    ValueError, "positive definite|ill-conditioned"):
                rectangle(lower, upper, mean, covariance)

    def test_identity_fixed_bin_copula_equals_discrete_margins_and_power_density(self):
        product = self._fn("fixed_bin_product_log_score")
        copula = self._fn("fixed_bin_copula_log_score")
        fits = {
            "excess_delay_chips": {"family": "lognormal", "status": "PASS",
                                   "parameters": {"shape": 0.55, "scale": 0.4}},
            "doppler_offset_hz": {"family": "student_t", "status": "PASS",
                                  "parameters": {"df": 7.0, "loc": 1.0, "scale": 18.0}},
            "relative_power_db": {"family": "normal", "status": "PASS",
                                  "parameters": {"loc": -8.0, "scale": 3.0}},
        }
        frame = pd.DataFrame({
            "run_id": ["R1", "R1"], "window_id": ["1", "2"],
            "path_id": ["2", "2"], "scene_id": ["S1", "S1"],
            "excess_delay_chips": [0.10, 0.13],
            "doppler_offset_hz": [-2.5, 17.5], "relative_power_db": [-8.0, -11.0],
        })
        independent = product(fits, frame, 5.0)
        joint = copula(fits, np.eye(3), frame, 5.0)
        np.testing.assert_allclose(joint, independent, rtol=0, atol=2e-10)
        expected_power = stats.norm.logpdf(frame.relative_power_db, loc=-8.0, scale=3.0)
        np.testing.assert_allclose(
            independent,
            __import__("mainline_stage2_wp6_gateg").delay_grid_log_mass(
                "lognormal", frame.excess_delay_chips.to_numpy(), {"shape": 0.55, "scale": 0.4})
            + __import__("mainline_stage2_wp6_fixed_doppler").doppler_bin_log_mass(
                "student_t", frame.doppler_offset_hz.to_numpy(), 5.0,
                {"df": 7.0, "loc": 1.0, "scale": 18.0})
            + expected_power,
            rtol=0, atol=1e-12)

    def test_copula_fit_returns_training_bound_positive_definite_matrix(self):
        fit_copula = self._fn("fit_fixed_bin_copula")
        rng = np.random.default_rng(55129)
        correlation = np.array([[1.0, 0.35, -0.2], [0.35, 1.0, 0.25], [-0.2, 0.25, 1.0]])
        z = rng.multivariate_normal(np.zeros(3), correlation, size=2400)
        u_delay = stats.norm.cdf(z[:, 0])
        delay_dist = stats.lognorm(s=0.5, scale=0.4)
        base = delay_dist.cdf(0.1)
        delay = delay_dist.ppf(base + u_delay * (1.0 - base))
        delay = 0.1 + np.round((delay - 0.1) / 0.01) * 0.01
        doppler_raw = 1.5 + 16.0 * z[:, 1]
        doppler = np.floor(doppler_raw / 5.0 + 0.5) * 5.0
        power = -8.0 + 3.0 * z[:, 2]
        frame = pd.DataFrame({
            "scene_id": np.repeat(["S1", "S2", "S3"], 800),
            "run_id": np.repeat(["R1", "R2", "R3"], 800),
            "window_id": np.tile(np.arange(1, 801).astype(str), 3),
            "path_id": "2", "excess_delay_chips": delay,
            "doppler_offset_hz": doppler, "relative_power_db": power,
        })
        fits = {
            "excess_delay_chips": {"family": "lognormal", "status": "PASS",
                                   "parameters": {"shape": 0.5, "scale": 0.4}},
            "doppler_offset_hz": {"family": "normal", "status": "PASS",
                                  "parameters": {"loc": 0.0, "scale": 20.0}},
            "relative_power_db": {"family": "normal", "status": "PASS",
                                  "parameters": {"loc": -8.0, "scale": 3.0}},
        }
        fitted, diagnostics = fit_copula(frame, fits, 5.0)
        self.assertEqual(diagnostics["status"], "PASS", diagnostics)
        self.assertEqual(diagnostics["training_scene_ids"], ["S1", "S2", "S3"])
        self.assertTrue(np.all(np.linalg.eigvalsh(fitted) > 0.0))

    def test_nested_selector_records_only_training_scenes(self):
        select = self._fn("select_doppler_family_nested")
        rng = np.random.default_rng(431)
        rows = []
        for scene_index in range(4):
            scene = f"S{scene_index + 1}"
            values = rng.normal(2.0 + scene_index, 18.0, 300)
            for index, value in enumerate(values):
                bin_center = np.floor(value / 5.0 + 0.5) * 5.0
                rows.append({"scene_id": scene, "run_id": f"R-{scene}",
                             "window_id": str(index + 1), "doppler_offset_hz": bin_center})
        selected, table = select(pd.DataFrame(rows), ("S1", "S2", "S3"), 5.0)
        self.assertIn(selected, ("normal", "student_t"))
        self.assertEqual(set(table.inner_held_out_scene_id), {"S1", "S2", "S3"})
        for row in table.itertuples(index=False):
            training = json.loads(row.inner_training_scene_ids)
            self.assertNotIn(row.inner_held_out_scene_id, training)
            self.assertTrue(set(training).issubset({"S1", "S2", "S3"}))
            self.assertNotIn("S4", training)

    def test_outer_loso_keeps_exact_scene_and_window_pairing(self):
        evaluate = self._fn("evaluate_fixed_bin_loso")
        rng = np.random.default_rng(20261030)
        rows = []
        for scene_index in range(13):
            scene = f"S{scene_index + 1:02d}"
            for window_index in range(24):
                delay = 0.10 + np.round(rng.lognormal(-1.5, 0.45) / 0.01) * 0.01
                doppler = np.floor(rng.normal(scene_index * 0.5, 24.0) / 5.0 + 0.5) * 5.0
                power = rng.normal(-8.0 + scene_index * 0.1, 3.0)
                rows.append({"run_id": f"R-{scene}", "window_id": str(window_index + 1),
                             "path_id": "2", "scene_id": scene, "selected_L": 2,
                             "excess_delay_chips": delay, "doppler_offset_hz": doppler,
                             "relative_power_db": power})
        results = evaluate(pd.DataFrame(rows), widths=(5.0,), expected_scenes=13)
        self.assertEqual(len(results["folds"]), 13)
        self.assertEqual(set(results["path_scores"].outer_held_out_scene_id),
                         {f"S{i:02d}" for i in range(1, 14)})
        for row in results["folds"].itertuples(index=False):
            self.assertNotIn(row.outer_held_out_scene_id, json.loads(row.outer_training_scene_ids))
        for row in results["family_selection"].itertuples(index=False):
            training = json.loads(row.inner_training_scene_ids)
            self.assertNotIn(row.outer_held_out_scene_id, training)
            self.assertNotIn(row.inner_held_out_scene_id, training)
        expected_keys = pd.DataFrame(rows)[["run_id", "window_id", "path_id"]].drop_duplicates()
        actual_keys = results["path_scores"][["run_id", "window_id", "path_id"]].drop_duplicates()
        pd.testing.assert_frame_equal(
            actual_keys.sort_values(list(actual_keys.columns)).reset_index(drop=True),
            expected_keys.sort_values(list(expected_keys.columns)).reset_index(drop=True))
        self.assertEqual(set(results["path_scores"].width_hz), {5.0})

    def test_unpaired_failed_scores_are_reported_not_silently_compared(self):
        summarize = self._fn("paired_scene_score_comparisons")
        paths = pd.DataFrame({
            "outer_held_out_scene_id": ["S1", "S1"], "scene_id": ["S1", "S1"],
            "run_id": ["R1", "R1"], "window_id": ["1", "2"], "path_id": ["2", "2"],
            "width_hz": [5.0, 5.0], "M0_independent": [-1.0, -2.0],
            "C0_copula": [-1.5, np.nan],
        })
        window, comparison = summarize(paths)
        self.assertEqual(int(comparison.iloc[0].paired_window_n), 1)
        self.assertEqual(int(comparison.iloc[0].unpaired_window_n), 1)
        self.assertAlmostEqual(float(comparison.iloc[0].C0_minus_M0_nats_per_mpc), -0.5)
        self.assertTrue(bool(np.isnan(window.loc[window.window_id.eq("2"), "C0_copula"].iloc[0])))

    def test_outer_fold_records_missing_marginal_and_does_not_score_it(self):
        evaluate = self._fn("evaluate_fixed_bin_loso")
        rows = []
        for scene_index in range(13):
            scene = f"S{scene_index + 1:02d}"
            for index in range(3):
                rows.append({"scene_id": scene, "run_id": f"R-{scene}",
                             "window_id": str(index + 1), "path_id": "2",
                             "selected_L": 2, "excess_delay_chips": 0.10 + index * 0.01,
                             "doppler_offset_hz": float(index * 5),
                             "relative_power_db": -8.0 + index})
        with mock.patch.object(self.api, "_select_mark_family_nested", return_value=(None, pd.DataFrame())), \
                mock.patch.object(self.api, "select_doppler_family_nested",
                                  return_value=(None, pd.DataFrame())):
            result = evaluate(pd.DataFrame(rows), widths=(5.0,), expected_scenes=13)
        diagnostics = result["copula_diagnostics"]
        self.assertEqual(set(diagnostics.status), {"MARGINAL_FIT_UNAVAILABLE"})
        self.assertTrue(result["path_scores"].C0_copula.isna().all())
        self.assertTrue(result["path_scores"].M0_independent.isna().all())
        self.assertEqual(set(result["scene_scores"].unpaired_window_n), {3})


if __name__ == "__main__":
    unittest.main()
