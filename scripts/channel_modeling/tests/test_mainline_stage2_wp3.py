"""Synthetic-only contracts for Mainline Stage2 WP3; never reads science payloads."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mainline_stage2_wp3 import (
    build_wp3_population, make_scene_folds, condition_support_tables,
    scene_window_weights, fit_model, score_model, quantile_diagnostics,
    evaluate_scene_loso,
)
from run_mainline_stage2_wp3 import _paired_deltas


def fixture_rows():
    windows = pd.DataFrame([
        {"run_id": "R1", "window_id": 1, "scene_id": "U1", "environment_class": "Urban",
         "prn": "G01", "tracking_channel": 1, "mpc_count": 2,
         "elevation_value_deg": 35.0, "elevation_source": "GSV_MEASURED",
         "receiver_height_source": "", "position_source": "EXISTING_NMEA",
         "position_status": "POSITION_MATCHED", "receiver_speed_mps": 12.0},
        {"run_id": "R1", "window_id": 2, "scene_id": "U1", "environment_class": "Urban",
         "prn": "G01", "tracking_channel": 1, "mpc_count": 0,
         "elevation_value_deg": "", "elevation_source": "MISSING",
         "receiver_height_source": "", "position_source": "EXISTING_NMEA",
         "position_status": "POSITION_MATCHED", "receiver_speed_mps": 12.0},
        {"run_id": "R2", "window_id": 1, "scene_id": "M1", "environment_class": "Mountain/Valley",
         "prn": "G02", "tracking_channel": 2, "mpc_count": 1,
         "elevation_value_deg": 40.0, "elevation_source": "EPHEMERIS_DERIVED",
         "receiver_height_source": "GGA_ELLIPSOIDAL_HEIGHT", "position_source": "GNSS_SDR_PVT_SINGLE",
         "position_status": "POSITION_MATCHED", "receiver_speed_mps": ""},
    ])
    paths = pd.DataFrame([
        {"run_id": "R1", "window_id": 1, "scene_id": "U1", "environment_class": "Urban",
         "prn": "G01", "tracking_channel": 1, "path_id": 2, "is_multipath": 1,
         "excess_delay_chips": 0.2, "doppler_offset_hz": -5.0, "relative_power_db": -8.0,
         "elevation_source": "GSV_MEASURED", "receiver_height_source": ""},
        {"run_id": "R1", "window_id": 1, "scene_id": "U1", "environment_class": "Urban",
         "prn": "G01", "tracking_channel": 1, "path_id": 3, "is_multipath": 1,
         "excess_delay_chips": 0.3, "doppler_offset_hz": 3.0, "relative_power_db": -12.0,
         "elevation_source": "GSV_MEASURED", "receiver_height_source": ""},
        {"run_id": "R2", "window_id": 1, "scene_id": "M1", "environment_class": "Mountain/Valley",
         "prn": "G02", "tracking_channel": 2, "path_id": 2, "is_multipath": 1,
         "excess_delay_chips": 0.1, "doppler_offset_hz": 1.0, "relative_power_db": -3.0,
         "elevation_source": "EPHEMERIS_DERIVED",
         "receiver_height_source": "GGA_ELLIPSOIDAL_HEIGHT"},
    ])
    return paths, windows


def fit_fixture():
    rows = []
    for scene, environment, offset in [
        ("U1", "Urban", 2.0), ("U2", "Urban", 2.2), ("U3", "Urban", 2.1),
        ("M1", "Mountain/Valley", -1.0), ("M2", "Mountain/Valley", -0.8),
        ("M3", "Mountain/Valley", -0.9),
    ]:
        for i, elevation in enumerate([25.0, 32.0, 40.0, 48.0, 57.0, 68.0]):
            y = offset + 0.7 * ((elevation - 45.0) / 10.0) + ((i % 3) - 1) * 0.15
            rows.append({
                "run_id": scene, "window_id": i + 1, "path_id": 2,
                "scene_id": scene, "environment_class": environment,
                "excess_delay_chips": 0.12 + 0.01 * i + 0.004 * (i % 2),
                "doppler_offset_hz": y, "relative_power_db": -9.0 + 0.4 * y,
                "elevation_value_deg": elevation, "elevation_source": "GSV_MEASURED",
                "receiver_height_source": "", "is_multipath": 1,
            })
    return pd.DataFrame(rows)


class WP3PopulationTests(unittest.TestCase):
    def test_exact_window_join_preserves_each_mpc_and_window_level_source(self):
        paths, windows = fixture_rows()
        joined = build_wp3_population(paths, windows)
        self.assertEqual(len(joined), 3)
        self.assertEqual(joined[["run_id", "window_id", "path_id"]].drop_duplicates().shape[0], 3)
        self.assertEqual(joined["elevation_source"].tolist(), ["GSV_MEASURED", "GSV_MEASURED", "EPHEMERIS_DERIVED"])
        self.assertEqual(joined.loc[joined.run_id == "R2", "receiver_height_source"].unique().tolist(),
                         ["GGA_ELLIPSOIDAL_HEIGHT"])
        self.assertEqual(joined.loc[joined.run_id == "R1", "receiver_speed_mps"].unique().tolist(), [12.0])

    def test_zero_mpc_run_remains_in_window_denominator_not_path_rows(self):
        paths, windows = fixture_rows()
        zero_only = windows.iloc[[0]].copy()
        zero_only.loc[:, "run_id"] = "R3"
        zero_only.loc[:, "scene_id"] = "S1"
        zero_only.loc[:, "environment_class"] = "Special Reflective"
        zero_only.loc[:, "prn"] = "G03"
        zero_only.loc[:, "tracking_channel"] = 3
        zero_only.loc[:, "mpc_count"] = 0
        windows = pd.concat([windows, zero_only], ignore_index=True)
        joined = build_wp3_population(paths, windows)
        self.assertEqual(windows.run_id.nunique(), 3)
        self.assertEqual(joined.run_id.nunique(), 2)
        self.assertEqual(int(windows.loc[windows.run_id.eq("R3"), "mpc_count"].sum()), 0)

    def test_support_tables_keep_zero_mpc_selected_windows_and_source_strata(self):
        paths, windows = fixture_rows()
        joined = build_wp3_population(paths, windows)
        trajectory = pd.DataFrame([
            {"run_id": "R1", "window_id": 1, "scene_id": "U1",
             "position_source": "EXISTING_NMEA", "position_source_record_id": "route.nmea:10",
             "receiver_speed_mps": 12.0},
            {"run_id": "R1", "window_id": 2, "scene_id": "U1",
             "position_source": "EXISTING_NMEA", "position_source_record_id": "route.nmea:10",
             "receiver_speed_mps": 12.0},
            {"run_id": "R2", "window_id": 1, "scene_id": "M1",
             "position_source": "GNSS_SDR_PVT_SINGLE", "position_source_record_id": "",
             "receiver_speed_mps": ""},
        ])
        scene, source, motion = condition_support_tables(joined, windows, trajectory)
        urban = next(row for row in scene.to_dict("records") if row["scene_id"] == "U1")
        self.assertEqual(urban["selected_window_n"], 2)
        self.assertEqual(urban["mpc_n"], 2)
        self.assertEqual(urban["missing_elevation_window_n"], 1)
        self.assertEqual(urban["gsv_measured_window_n"], 1)
        gga = next(row for row in source.to_dict("records")
                   if row["scene_id"] == "M1" and row["receiver_height_source"] == "GGA_ELLIPSOIDAL_HEIGHT")
        self.assertEqual(gga["window_n"], 1)
        self.assertEqual(gga["mpc_n"], 1)
        urban_motion = next(row for row in motion.to_dict("records") if row["scene_id"] == "U1")
        self.assertEqual(urban_motion["distinct_speed_source_record_n"], 1)
        self.assertEqual(urban_motion["max_windows_per_speed_source_record"], 2)

    def test_scene_window_weights_prevent_scene_and_multi_path_window_dominance(self):
        frame = pd.DataFrame([
            {"scene_id": "A", "run_id": "A", "window_id": 1},
            {"scene_id": "A", "run_id": "A", "window_id": 1},
            {"scene_id": "A", "run_id": "A", "window_id": 2},
            {"scene_id": "B", "run_id": "B", "window_id": 1},
        ])
        weights = scene_window_weights(frame)
        self.assertAlmostEqual(float(weights.sum()), 1.0)
        self.assertEqual(weights[:2].tolist(), [0.125, 0.125])
        self.assertAlmostEqual(float(weights[2]), 0.25)
        self.assertAlmostEqual(float(weights[3]), 0.5)

    def test_static_normal_lognormal_and_laplace_use_exact_weighted_mle(self):
        rows = []
        for index, value in enumerate([0.0, 0.0, 10.0, 10.0], start=1):
            rows.append({"scene_id": "U1", "environment_class": "Urban", "run_id": "R1",
                         "window_id": index, "doppler_offset_hz": value,
                         "relative_power_db": value})
        frame = pd.DataFrame(rows)
        normal = fit_model(frame, "doppler_offset_hz", "normal", "M0")
        laplace = fit_model(frame, "relative_power_db", "laplace", "M0")
        self.assertEqual(normal["optimizer_message"], "CLOSED_FORM_WEIGHTED_MLE")
        self.assertAlmostEqual(normal["parameters"]["loc"], 5.0, places=10)
        self.assertAlmostEqual(normal["parameters"]["scale"], 5.0, places=10)
        self.assertEqual(laplace["optimizer_message"], "CLOSED_FORM_WEIGHTED_MLE")
        self.assertAlmostEqual(laplace["parameters"]["loc"], 0.0, places=10)
        self.assertAlmostEqual(laplace["parameters"]["scale"], 5.0, places=10)

        positive = frame.copy()
        positive["excess_delay_chips"] = [1.0, 1.0, 3.0, 3.0]
        lognormal = fit_model(positive, "excess_delay_chips", "lognormal", "M0")
        self.assertEqual(lognormal["optimizer_message"], "CLOSED_FORM_WEIGHTED_MLE")
        self.assertAlmostEqual(lognormal["parameters"]["scale"], 3.0 ** 0.5, places=10)
        self.assertAlmostEqual(lognormal["parameters"]["shape"], 0.5 * np.log(3.0), places=10)

    def test_environment_and_elevation_models_fit_without_using_held_scene(self):
        frame = fit_fixture()
        train = frame[frame.scene_id != "U1"].copy()
        held = frame[frame.scene_id == "U1"].copy()
        for model in ("M0", "M1", "M2"):
            fit = fit_model(train, "doppler_offset_hz", "normal", model)
            self.assertEqual(fit["status"], "PASS", fit)
            self.assertNotIn("U1", fit["training_scene_ids"])
            score = score_model(fit, held, "doppler_offset_hz")
            self.assertEqual(score["status"], "PASS", score)
            self.assertEqual(score["test_path_n"], 6)
            self.assertEqual(score["test_window_n"], 6)
            self.assertTrue(pd.notna(score["window_balanced_mean_log_score"]))
        conditional = fit_model(train, "doppler_offset_hz", "normal", "M2")
        self.assertTrue(pd.notna(conditional["parameters"]["elevation_slope_per_10deg"]))

    def test_m2_refuses_missing_or_non_finite_condition_values(self):
        frame = fit_fixture()
        frame.loc[frame.index[0], "elevation_value_deg"] = float("nan")
        fit = fit_model(frame, "doppler_offset_hz", "normal", "M2")
        self.assertNotEqual(fit["status"], "PASS")
        self.assertIn("elevation", fit["failure_reason"].lower())

    def test_m2_refuses_to_pool_gsv_and_ephemeris_sources(self):
        frame = fit_fixture()
        frame.loc[frame.index[0], "elevation_source"] = "EPHEMERIS_DERIVED"
        frame.loc[frame.index[0], "receiver_height_source"] = "GGA_ELLIPSOIDAL_HEIGHT"
        fit = fit_model(frame, "doppler_offset_hz", "normal", "M2")
        self.assertEqual(fit["status"], "MIXED_ELEVATION_SOURCES")

    def test_loso_comparisons_pair_models_on_identical_test_identities(self):
        scores, folds, tails = evaluate_scene_loso(
            fit_fixture(), families={"doppler_offset_hz": ("normal",)}
        )
        measured = scores[scores.data_scope == "GSV_MEASURED"]
        self.assertEqual(len(measured), 6 * 3)
        for held, group in measured.groupby("held_out_scene_id"):
            self.assertEqual(set(group.model), {"M0", "M1", "M2"})
            self.assertEqual(group.test_identity_sha256.nunique(), 1)
            for training_json in group.training_scene_ids:
                self.assertNotIn(held, training_json)
        self.assertEqual(len(folds[folds.data_scope == "GSV_MEASURED"]), 6)
        self.assertTrue((measured.score_status == "PASS").all())
        self.assertEqual(set(tails[tails.data_scope == "GSV_MEASURED"].model), {"M0", "M1", "M2"})
        paired = _paired_deltas(scores)
        all_mpc = paired.loc[paired.data_scope.eq("ALL_MPC")]
        self.assertEqual(set(all_mpc.comparison), {"M1-M0"})
        self.assertTrue(paired.paired_status.isin(
            {"PASS", "IDENTITY_MISMATCH", "FIT_OR_SCORE_UNAVAILABLE"}
        ).all())

    def test_quantile_diagnostics_report_window_balanced_coverage_and_support(self):
        frame = fit_fixture()
        fit = fit_model(frame[frame.scene_id != "U1"], "doppler_offset_hz", "normal", "M0")
        diagnostics = quantile_diagnostics(fit, frame[frame.scene_id == "U1"], "doppler_offset_hz")
        self.assertEqual({row["quantile"] for row in diagnostics}, {0.05, 0.5, 0.95})
        self.assertTrue(all(row["test_path_n"] == 6 for row in diagnostics))
        self.assertTrue(all(row["test_window_n"] == 6 for row in diagnostics))
        self.assertTrue(all(0.0 <= row["window_balanced_coverage"] <= 1.0 for row in diagnostics))

    def test_empirical_tail_quantiles_do_not_let_multi_mpc_window_dominate(self):
        frame = pd.DataFrame([
            {"run_id": "R1", "window_id": 1, "path_id": 2, "scene_id": "U1",
             "environment_class": "Urban", "relative_power_db": 0.0},
            {"run_id": "R1", "window_id": 2, "path_id": 2, "scene_id": "U1",
             "environment_class": "Urban", "relative_power_db": 10.0},
            {"run_id": "R1", "window_id": 2, "path_id": 3, "scene_id": "U1",
             "environment_class": "Urban", "relative_power_db": 10.0},
            {"run_id": "R1", "window_id": 2, "path_id": 4, "scene_id": "U1",
             "environment_class": "Urban", "relative_power_db": 10.0},
        ])
        fit = fit_model(frame, "relative_power_db", "normal", "M0")
        diagnostics = quantile_diagnostics(
            fit, frame, "relative_power_db", quantiles=(0.5,)
        )
        self.assertEqual(diagnostics[0]["empirical_heldout_quantile"], 0.0)

    def test_duplicate_window_or_mpc_identity_is_rejected(self):
        paths, windows = fixture_rows()
        with self.assertRaisesRegex(ValueError, "duplicate window"):
            build_wp3_population(paths, pd.concat([windows, windows.iloc[[0]]], ignore_index=True))
        with self.assertRaisesRegex(ValueError, "duplicate MPC"):
            build_wp3_population(pd.concat([paths, paths.iloc[[0]]], ignore_index=True), windows)

    def test_window_label_mismatch_is_rejected_instead_of_silently_joined(self):
        paths, windows = fixture_rows()
        windows.loc[0, "environment_class"] = "Highway/Open"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            build_wp3_population(paths, windows)

    def test_scene_folds_hold_out_exactly_one_complete_scene(self):
        paths, windows = fixture_rows()
        joined = build_wp3_population(paths, windows)
        folds = make_scene_folds(joined)
        self.assertEqual([f["held_out_scene_id"] for f in folds], ["M1", "U1"])
        for fold in folds:
            self.assertEqual(set(fold["train"].scene_id) & set(fold["test"].scene_id), set())
            self.assertEqual(set(fold["test"].scene_id), {fold["held_out_scene_id"]})


if __name__ == "__main__":
    unittest.main()
