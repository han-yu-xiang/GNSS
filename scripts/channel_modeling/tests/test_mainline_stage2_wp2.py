"""Synthetic-only WP2 robustness contracts; no SAGE/CIR payload access."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mainline_stage2_v0 as v0
from mainline_stage2_wp2 import (
    marginal_stability_rows,
    tail_calibration_rows,
    evaluate_power_delay_loso,
    evaluate_selected_count_loso,
    _fit_truncated_nb2,
)


class WP2Tests(unittest.TestCase):
    def test_marginal_rank_is_within_variable_and_scene(self):
        mpc = pd.DataFrame([
            {"scene_id": "A", "environment_class": "Urban", "excess_delay_chips": 1.0,
             "relative_power_db": -3.0},
            {"scene_id": "B", "environment_class": "Urban", "excess_delay_chips": 2.0,
             "relative_power_db": -2.0},
        ])
        folds = pd.DataFrame([
            {"scope": "GLOBAL", "held_out_scene_id": "A", "variable": "excess_delay_chips",
             "family": "gamma", "fit_status": "PASS", "fit_parameters": "[2.0, 0.0, 1.0]",
             "mean_loglik": -2.0, "train_scene_n": 1, "test_n": 1, "finite_test_n": 1},
            {"scope": "GLOBAL", "held_out_scene_id": "A", "variable": "excess_delay_chips",
             "family": "lognormal", "fit_status": "PASS", "fit_parameters": "[0.5, 0.0, 1.0]",
             "mean_loglik": -1.0, "train_scene_n": 1, "test_n": 1, "finite_test_n": 1},
            {"scope": "GLOBAL", "held_out_scene_id": "A", "variable": "relative_power_db",
             "family": "normal", "fit_status": "PASS", "fit_parameters": "[-2.0, 1.0]",
             "mean_loglik": -8.0, "train_scene_n": 1, "test_n": 1, "finite_test_n": 1},
            {"scope": "GLOBAL", "held_out_scene_id": "A", "variable": "relative_power_db",
             "family": "laplace", "fit_status": "PASS", "fit_parameters": "[-2.0, 1.0]",
             "mean_loglik": -4.0, "train_scene_n": 1, "test_n": 1, "finite_test_n": 1},
            {"scope": "GLOBAL", "held_out_scene_id": "B", "variable": "excess_delay_chips",
             "family": "gamma", "fit_status": "PASS", "fit_parameters": "[3.0, 0.0, 1.0]",
             "mean_loglik": -3.0, "train_scene_n": 1, "test_n": 1, "finite_test_n": 1},
            {"scope": "GLOBAL", "held_out_scene_id": "B", "variable": "excess_delay_chips",
             "family": "lognormal", "fit_status": "FAILED", "fit_parameters": "[]",
             "mean_loglik": "", "train_scene_n": 1, "test_n": 1, "finite_test_n": 1},
        ])

        rows, summary = marginal_stability_rows(mpc, folds, scopes=("GLOBAL",))

        by_key = {(r["held_out_scene_id"], r["variable"], r["family"]): r for r in rows}
        self.assertEqual(by_key[("A", "excess_delay_chips", "lognormal")]["heldout_rank"], 1)
        self.assertEqual(by_key[("A", "relative_power_db", "laplace")]["heldout_rank"], 1)
        self.assertEqual(by_key[("A", "relative_power_db", "normal")]["heldout_rank"], 2)
        self.assertIsNone(by_key[("B", "excess_delay_chips", "lognormal")]["heldout_rank"])
        lognormal = [r for r in summary if r["variable"] == "excess_delay_chips" and r["family"] == "lognormal"]
        self.assertEqual(lognormal[0]["failed_fold_n"], 1)
        self.assertEqual(lognormal[0]["rank1_scene_ids"], ["A"])

    def test_support_violating_fold_is_not_ranked_as_a_valid_predictive_fit(self):
        mpc = pd.DataFrame({"scene_id": ["A", "A"], "relative_power_db": [-1.0, 0.0]})
        folds = pd.DataFrame([
            {"scope": "GLOBAL", "held_out_scene_id": "A", "variable": "relative_power_db",
             "family": "normal", "fit_status": "PASS", "fit_parameters": "[0.0, 1.0]",
             "mean_loglik": "-Infinity", "test_n": 2, "finite_test_n": 2, "support_violation_n": 2},
            {"scope": "GLOBAL", "held_out_scene_id": "A", "variable": "relative_power_db",
             "family": "laplace", "fit_status": "PASS", "fit_parameters": "[0.0, 1.0]",
             "mean_loglik": -1.0, "test_n": 2, "finite_test_n": 2, "support_violation_n": 0},
        ])
        rows, summary = marginal_stability_rows(mpc, folds, scopes=("GLOBAL",))
        normal = next(r for r in rows if r["family"] == "normal")
        normal_summary = next(r for r in summary if r["family"] == "normal" and r["row_type"] == "FAMILY_RANK")
        self.assertIsNone(normal["heldout_rank"])
        self.assertEqual(normal_summary["support_limited_fold_n"], 1)

    def test_tail_diagnostics_use_saved_fold_parameters_and_flag_sparse_tails(self):
        mpc = pd.DataFrame({
            "scene_id": ["A"] * 4,
            "environment_class": ["Urban"] * 4,
            "relative_power_db": [0.0, 1.0, 2.0, 3.0],
        })
        folds = pd.DataFrame([{
            "scope": "GLOBAL", "held_out_scene_id": "A", "variable": "relative_power_db",
            "family": "normal", "fit_status": "PASS", "fit_parameters": "[0.0, 1.0]",
            "mean_loglik": -1.0, "train_scene_n": 2, "test_n": 4, "finite_test_n": 4,
        }])

        rows, summary = tail_calibration_rows(mpc, folds, quantiles=(0.9,))

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertAlmostEqual(row["predicted_quantile"], stats.norm.ppf(0.9), places=10)
        self.assertAlmostEqual(row["empirical_coverage"], 0.5)
        self.assertAlmostEqual(row["expected_tail_observation_n"], 0.4)
        self.assertEqual(row["tail_support_status"], "LOW_TAIL_SUPPORT")
        self.assertEqual(summary[0]["low_support_fold_n"], 1)

    def test_positive_tail_fit_is_marked_invalid_for_heldout_support_violation(self):
        mpc = pd.DataFrame({"scene_id": ["A", "A"], "excess_delay_chips": [-1.0, 1.0]})
        folds = pd.DataFrame([{
            "scope": "GLOBAL", "held_out_scene_id": "A", "variable": "excess_delay_chips",
            "family": "lognormal", "fit_status": "PASS", "fit_parameters": "[0.5, 0.0, 1.0]",
            "mean_loglik": "-Infinity", "train_scene_n": 2, "test_n": 2,
            "finite_test_n": 2, "support_violation_n": 1,
        }])
        rows, _ = tail_calibration_rows(mpc, folds, quantiles=(0.9,), scopes=("GLOBAL",))
        self.assertEqual(rows[0]["fit_status"], "HELDOUT_SUPPORT_VIOLATION")
        self.assertEqual(rows[0]["heldout_support_violation_n"], 1)
        self.assertIsNone(rows[0]["empirical_coverage"])

    def test_power_delay_loso_uses_equal_scene_training_weights_and_scene_bootstrap(self):
        rows = []
        # The training scenes have the same slope but different intercepts and
        # unequal row support; equal-scene WLS must return intercept 5, slope 2.
        for scene, xs, intercept in [
            ("A", [0.0, 1.0], 100.0),
            ("B", [0.0, 1.0], 0.0),
            ("C", [0.0, 0.5, 1.0], 10.0),
        ]:
            for x in xs:
                rows.append({"scene_id": scene, "excess_delay_chips": x,
                             "relative_power_db": intercept + 2.0 * x})

        per_scene, summary = evaluate_power_delay_loso(
            pd.DataFrame(rows), scopes=("GLOBAL",), bootstrap_iterations=200, seed=17
        )
        fold_a = next(row for row in per_scene if row["held_out_scene_id"] == "A")
        self.assertEqual(fold_a["train_scene_n"], 2)
        self.assertEqual(fold_a["training_scene_ids"], ["B", "C"])
        self.assertAlmostEqual(fold_a["conditional_intercept_db"], 5.0)
        self.assertAlmostEqual(fold_a["conditional_slope_db_per_chip"], 2.0)
        self.assertEqual(fold_a["train_scene_weight_min"], 1.0)
        self.assertEqual(fold_a["train_scene_weight_max"], 1.0)
        self.assertEqual(len(per_scene), 3)
        self.assertEqual(summary[0]["bootstrap_unit"], "whole_scene_with_multiplicity")
        self.assertEqual(summary[0]["scene_n"], 3)
        self.assertNotIn("p_value", summary[0])

        changed = pd.DataFrame(rows)
        changed.loc[changed.scene_id == "A", "relative_power_db"] += 1e6
        changed_rows, _ = evaluate_power_delay_loso(
            changed, scopes=("GLOBAL",), bootstrap_iterations=200, seed=17
        )
        changed_a = next(row for row in changed_rows if row["held_out_scene_id"] == "A")
        self.assertEqual(fold_a["conditional_slope_db_per_chip"], changed_a["conditional_slope_db_per_chip"])
        self.assertNotEqual(fold_a["conditional_mean_log_score"], changed_a["conditional_mean_log_score"])

    def test_selected_count_models_preserve_zero_and_hold_out_complete_scenes(self):
        windows = pd.DataFrame([
            {"run_id": f"run-{scene}", "window_id": str(index + 1),
             "scene_id": scene, "mpc_count": count}
            for scene in ["A", "B", "C"]
            for index, count in enumerate([0, 1, 2, 0])
        ])
        folds, summary = evaluate_selected_count_loso(windows, bootstrap_iterations=200, seed=23)
        self.assertEqual(len(folds), 3 * 3)
        self.assertEqual({row["candidate_model"] for row in folds}, {
            "EMPIRICAL_CATEGORICAL", "TRUNCATED_POISSON", "TRUNCATED_NB2"
        })
        self.assertEqual({row["estimand"] for row in folds}, {
            "P(MPC count | Stage2-selected window; support 0..3)"
        })
        by_key = {(r["candidate_model"], r["held_out_scene_id"]): r for r in folds}
        held_a = by_key[("TRUNCATED_POISSON", "A")]
        self.assertEqual(held_a["training_scene_ids"], ["B", "C"])
        self.assertEqual(held_a["train_scene_n"], 2)
        self.assertEqual(held_a["test_window_n"], 4)
        self.assertEqual(held_a["observed_count_histogram"], {"0": 2, "1": 1, "2": 1, "3": 0})
        for row in folds:
            if row["predictive_pmf"] is not None:
                self.assertAlmostEqual(sum(row["predictive_pmf"]), 1.0, places=10)
        self.assertEqual(len(summary), 3)
        self.assertTrue(all(r["bootstrap_unit"] == "whole_scene_with_multiplicity" for r in summary))

    def test_selected_count_rejects_duplicate_identity_and_out_of_support(self):
        windows = pd.DataFrame([
            {"run_id": "rA", "window_id": str(i), "scene_id": "A", "mpc_count": 0}
            for i in range(1, 5)
        ] + [
            {"run_id": "rB", "window_id": str(i), "scene_id": "B", "mpc_count": 1}
            for i in range(1, 5)
        ] + [
            {"run_id": "rC", "window_id": str(i), "scene_id": "C", "mpc_count": 2}
            for i in range(1, 5)
        ])
        with self.assertRaisesRegex(ValueError, "duplicate.*identity"):
            evaluate_selected_count_loso(pd.concat([windows, windows.iloc[[0]]], ignore_index=True))
        invalid = windows.copy()
        invalid.loc[0, "mpc_count"] = 4
        with self.assertRaisesRegex(ValueError, "support"):
            evaluate_selected_count_loso(invalid)

    def test_selected_count_flags_unseen_category_without_smoothing(self):
        windows = pd.DataFrame([
            {"run_id": f"run-{scene}", "window_id": str(i + 1), "scene_id": scene,
             "mpc_count": count}
            for scene, counts in [("A", [3, 3, 3, 3]), ("B", [0, 0, 0, 0]),
                                  ("C", [0, 1, 0, 1])]
            for i, count in enumerate(counts)
        ])
        folds, _ = evaluate_selected_count_loso(windows, bootstrap_iterations=0)
        categorical_a = next(r for r in folds if r["candidate_model"] == "EMPIRICAL_CATEGORICAL"
                             and r["held_out_scene_id"] == "A")
        self.assertEqual(categorical_a["unseen_category_n"], 1)
        self.assertEqual(categorical_a["fit_status"], "UNSEEN_HELDOUT_CATEGORY")
        self.assertEqual(categorical_a["mean_log_score"], float("-inf"))

    def test_nb2_infinite_mean_boundary_is_not_reported_as_a_finite_mle(self):
        scene_counts = [0, 0, 0, 1, 1, 2, 3, 3]
        counts = np.asarray(scene_counts * 3, dtype=int)
        weights = np.repeat(1.0 / len(scene_counts), len(counts))
        status, parameters, pmf = _fit_truncated_nb2(counts, weights)
        self.assertEqual(status, "BOUNDARY_MEAN_AT_INFINITY")
        self.assertIsNone(parameters["mean"])
        self.assertEqual(parameters["mean_boundary"], "INFINITY_LIMIT")
        self.assertGreater(parameters["alpha"], 0)
        self.assertAlmostEqual(float(pmf.sum()), 1.0, places=12)


if __name__ == "__main__":
    unittest.main()
