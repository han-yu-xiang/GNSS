"""Behavior tests for Python-only VTC validation layer runners."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from export_layer3_native_model_support import build_layer3_rows
from run_dll_code_bias_study import build_case_rows
from run_validation_sequence import build_steps
from run_layer1_controlled_recovery import (
    enumerate_trials as enumerate_layer1,
    execute_trial as execute_layer1_trial,
)
from run_layer2_multipath_stress import (
    enumerate_trials as enumerate_layer2,
    execute_trial as execute_layer2_trial,
)
from vtc_validation_common import (
    EstimatorConfig,
    MatchingTolerances,
    PathEstimate,
    ValidationCase,
    estimator_from_contract,
    make_replica,
    make_signal_context,
    prepare_case,
)


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "docs/vtc2027_spring/evidence/validation_v1/validation_contract.json"


class PythonLayerRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_layer1_enumerates_frozen_216_trials_in_stable_order(self) -> None:
        trials = list(enumerate_layer1(self.contract))
        self.assertEqual(len(trials), 216)
        self.assertEqual(trials[0]["trial_id"], "L1_0001")
        self.assertEqual(trials[-1]["trial_id"], "L1_0216")

    def test_layer2_enumerates_frozen_192_trials_in_stable_order(self) -> None:
        trials = list(enumerate_layer2(self.contract))
        self.assertEqual(len(trials), 192)
        self.assertEqual(trials[0]["trial_id"], "L2_0001")
        self.assertEqual(trials[-1]["trial_id"], "L2_0192")

    def test_layer3_exports_all_four_frozen_native_events_without_raw_iq(self) -> None:
        rows = build_layer3_rows(self.contract)
        self.assertEqual(len(rows), 4)
        self.assertEqual({int(row["selected_order"]) for row in rows}, {2})
        self.assertTrue(all(float(row["l1_rss"]) > float(row["selected_rss"]) for row in rows))
        self.assertTrue(all(float(row["delta_bic"]) > 0 for row in rows))

    def test_prepare_case_uses_contract_center_and_stage0_doppler_bound(self) -> None:
        case = prepare_case(self.contract, self.contract["layer1"]["cases"][0])
        self.assertEqual(case.scene_id, "F1023_V70_D0120_P1")
        self.assertEqual(case.prn_label, "G18")
        self.assertEqual(case.center_window_id, 155)
        self.assertEqual(len(case.snapshots), 5)
        self.assertGreater(case.doppler_bound_hz, 0.0)
        self.assertEqual(case.sample_count, 204600)

    def test_estimator_mapping_preserves_all_frozen_thresholds(self) -> None:
        config = estimator_from_contract(self.contract)
        self.assertEqual(config.maximum_model_order, 4)
        self.assertEqual(config.delay_step_samples, 0.1)
        self.assertEqual(config.minimum_path_separation_samples, 1.0)
        self.assertEqual(config.local_doppler_step_hz, 5.0)
        self.assertEqual(config.minimum_sequential_bic_gain, 10.0)
        self.assertEqual(config.minimum_joint_snapshot_wins, 4)

    def _synthetic_case(self, include_native_secondary: bool) -> tuple[ValidationCase, list[np.ndarray]]:
        n = 4092
        context = make_signal_context(1, 1_023_000.0, n)
        direct = PathEstimate(0.0, -100.0)
        native = PathEstimate(2.0, -110.0)
        snapshots = [
            {
                "sample_start_zero_based": index * n,
                "recording_time_s": index * 0.02,
                "nav_symbol": 1,
                "code_frequency_hz": 1_023_000.0,
            }
            for index in range(5)
        ]
        paths = [direct, native] if include_native_secondary else [direct]
        powers = [0.0, -12.041199826559248] if include_native_secondary else [0.0]
        case = ValidationCase(
            scene_id="SYNTHETIC",
            prn_label="G01",
            prn=1,
            environment="Test",
            center_window_id=1,
            raw_file=Path("unused.bin"),
            snapshots=snapshots,
            direct_path=direct,
            native_paths=paths,
            native_relative_power_db=powers,
            doppler_bound_hz=60.0,
            contexts=[context] * 5,
            sample_count=n,
        )
        observations = []
        for index in range(5):
            observed = make_replica(direct.delay_samples, direct.doppler_hz, context)
            if include_native_secondary:
                observed = observed + 0.25 * np.exp(1j * 0.15 * index) * make_replica(
                    native.delay_samples, native.doppler_hz, context
                )
            observations.append(observed)
        return case, observations

    def _small_estimator(self, maximum_order: int) -> EstimatorConfig:
        return EstimatorConfig(
            maximum_model_order=maximum_order,
            delay_step_samples=0.1,
            minimum_path_separation_samples=1.0,
            local_delay_half_width_samples=0.8,
            local_doppler_step_hz=5.0,
            local_doppler_half_width_hz=30.0,
            maximum_excess_delay_samples=8.0,
            minimum_path_power_db=-25.0,
            maximum_path_coherence=0.999,
            minimum_sequential_bic_gain=10.0,
            minimum_joint_snapshot_wins=4,
            sage_iterations=4,
            sage_tolerance=1e-6,
        )

    def test_layer1_executes_one_known_path_trial(self) -> None:
        case, base = self._synthetic_case(include_native_secondary=False)
        trial = {
            "trial_id": "L1_0001", "case": {}, "delay": 3.0,
            "doppler": 30.0, "power": -6.0, "phase": 0.0,
        }
        row = execute_layer1_trial(
            case, base, trial, self._small_estimator(2), MatchingTolerances(0.2, 5.0, 2.0)
        )
        self.assertEqual(row["failure_reason"], "PASS")
        self.assertTrue(row["injected_match"])
        self.assertEqual(row["selected_order"], 2)

    def test_layer2_executes_one_added_path_on_native_multipath(self) -> None:
        case, base = self._synthetic_case(include_native_secondary=True)
        trial = {
            "trial_id": "L2_0001", "case": {}, "delay": 4.0,
            "doppler": 30.0, "power": -6.0, "phase": 0.0,
        }
        row = execute_layer2_trial(
            case, base, trial, self._small_estimator(3), MatchingTolerances(0.25, 5.0, 2.5)
        )
        self.assertEqual(row["failure_reason"], "PASS")
        self.assertTrue(row["injected_match"])
        self.assertTrue(row["native_path_consistency"])
        self.assertEqual(row["selected_order"], 3)

    def test_dll_rows_retain_pre_fitted_and_error_aware_modes(self) -> None:
        case, observations = self._synthetic_case(include_native_secondary=True)
        errors = [{
            "trial_id": "L2_SYNTHETIC",
            "injected_delay_error_samples": 0.0,
            "injected_doppler_error_hz": 0.0,
            "injected_power_error_db": 0.0,
        }]
        rows = build_case_rows(
            case, observations, errors, spacing_chips=0.5,
            meters_per_chip=293.0522561094819,
            offset_grid_chips=np.arange(-1.0, 1.0001, 0.02),
        )
        counts = {
            mode: sum(row["mode"] == mode for row in rows)
            for mode in {row["mode"] for row in rows}
        }
        self.assertEqual(counts["pre_cancellation"], 5)
        self.assertEqual(counts["fitted_model_cancellation"], 5)
        self.assertEqual(counts["error_aware_cancellation"], 5)
        fitted = [row["bias_chips"] for row in rows if row["mode"] == "fitted_model_cancellation"]
        aware = [row["bias_chips"] for row in rows if row["mode"] == "error_aware_cancellation"]
        np.testing.assert_allclose(aware, fitted, atol=1e-10)

    def test_sequence_is_python_only_single_order_and_stops_at_qa(self) -> None:
        steps = build_steps()
        self.assertEqual(
            [step.name for step in steps],
            [
                "layer1", "layer1_audit", "layer2", "layer2_audit",
                "layer3_audit", "dll", "dll_audit", "independent_qa",
            ],
        )
        command_text = " ".join(" ".join(step.arguments) for step in steps).lower()
        self.assertNotIn("matlab", command_text)
        self.assertNotIn(".m ", command_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
