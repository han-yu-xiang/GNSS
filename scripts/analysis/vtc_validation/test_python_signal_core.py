"""Behavior tests for the pure-Python VTC validation signal core."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from vtc_validation_common import (
    EstimatorConfig,
    PathEstimate,
    dll_zero_crossing,
    dll_zero_crossing_reference,
    estimate_joint,
    generate_gps_ca_code,
    make_grid,
    make_replica,
    make_signal_context,
    normalize_signal,
    read_iq,
    signed_fft_bins,
    solve_snapshot_alpha,
)


class PythonSignalCoreTests(unittest.TestCase):
    def test_prn1_ca_code_starts_with_frozen_gps_sequence(self) -> None:
        code = generate_gps_ca_code(1)
        self.assertEqual(code.shape, (1023,))
        np.testing.assert_array_equal(
            code[:10], np.array([-1, -1, 1, 1, -1, 1, 1, 1, 1, 1])
        )
        self.assertEqual(set(np.unique(code)), {-1.0, 1.0})

    def test_signed_fft_bins_match_matlab_order(self) -> None:
        np.testing.assert_array_equal(
            signed_fft_bins(4), np.array([0.0, 1.0, -2.0, -1.0])
        )
        np.testing.assert_array_equal(
            signed_fft_bins(5), np.array([0.0, 1.0, 2.0, -2.0, -1.0])
        )

    def test_grid_keeps_non_step_aligned_endpoint(self) -> None:
        np.testing.assert_allclose(make_grid(0.0, 0.25, 0.1), [0.0, 0.1, 0.2, 0.25])

    def test_complex_least_squares_recovers_path_amplitudes(self) -> None:
        context = make_signal_context(prn=1, code_frequency_hz=1_023_000.0, n=4092)
        paths = [
            PathEstimate(delay_samples=0.25, doppler_hz=-100.0),
            PathEstimate(delay_samples=3.0, doppler_hz=-70.0),
        ]
        truth = np.array([1.5 + 0.25j, -0.4 + 0.8j])
        observed = sum(
            make_replica(path.delay_samples, path.doppler_hz, context) * alpha
            for path, alpha in zip(paths, truth, strict=True)
        )
        recovered = solve_snapshot_alpha(paths, observed, context)
        np.testing.assert_allclose(recovered, truth, rtol=1e-10, atol=1e-10)

    def test_direct_only_dll_zero_crossing_is_zero(self) -> None:
        context = make_signal_context(prn=5, code_frequency_hz=1_023_000.0, n=10230)
        direct = PathEstimate(delay_samples=0.3, doppler_hz=125.0)
        signal = make_replica(direct.delay_samples, direct.doppler_hz, context)
        crossing, _, valid = dll_zero_crossing(
            signal, context, direct, spacing_chips=0.5,
            offset_grid_chips=np.arange(-1.0, 1.0001, 0.01),
        )
        self.assertTrue(valid)
        self.assertAlmostEqual(crossing, 0.0, places=8)

    def test_fft_oversampled_dll_matches_replica_loop_reference(self) -> None:
        context = make_signal_context(prn=5, code_frequency_hz=1_023_000.0, n=4092)
        direct = PathEstimate(delay_samples=0.3, doppler_hz=-100.0)
        secondary = PathEstimate(delay_samples=2.7, doppler_hz=-70.0)
        signal = (
            make_replica(direct.delay_samples, direct.doppler_hz, context)
            + (0.25 + 0.1j)
            * make_replica(secondary.delay_samples, secondary.doppler_hz, context)
        )
        offsets = np.arange(-1.0, 1.0001, 0.02)
        reference = dll_zero_crossing_reference(
            signal, context, direct, 0.5, offsets
        )
        optimized = dll_zero_crossing(signal, context, direct, 0.5, offsets)
        np.testing.assert_allclose(optimized[1], reference[1], rtol=1e-9, atol=1e-8)
        self.assertEqual(optimized[2], reference[2])
        self.assertAlmostEqual(optimized[0], reference[0], places=9)

    def test_iq_reader_uses_interleaved_little_endian_int16_and_sample_offset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "iq.bin"
            np.array([1, -2, 3, -4, 5, -6], dtype="<i2").tofile(path)
            values = read_iq(path, start_sample=1, sample_count=2)
            np.testing.assert_array_equal(values, np.array([3 - 4j, 5 - 6j]))

    def test_normalization_removes_mean_and_sets_unit_rms(self) -> None:
        values = normalize_signal(np.array([1 + 1j, 3 + 1j, 5 + 1j]))
        self.assertAlmostEqual(abs(np.mean(values)), 0.0, places=12)
        self.assertAlmostEqual(float(np.sqrt(np.mean(np.abs(values) ** 2))), 1.0, places=12)

    def test_joint_estimator_recovers_known_secondary_path(self) -> None:
        context = make_signal_context(prn=1, code_frequency_hz=1_023_000.0, n=4092)
        direct = PathEstimate(delay_samples=0.0, doppler_hz=-100.0)
        secondary = PathEstimate(delay_samples=3.0, doppler_hz=-70.0)
        observations = []
        for phase in np.linspace(0.0, 0.8, 5):
            observations.append(
                make_replica(direct.delay_samples, direct.doppler_hz, context)
                + 0.5 * np.exp(1j * phase)
                * make_replica(secondary.delay_samples, secondary.doppler_hz, context)
            )
        config = EstimatorConfig(
            maximum_model_order=2,
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
        result = estimate_joint(
            observations, direct, [context] * 5, doppler_bound_hz=50.0, config=config
        )
        self.assertEqual(result.selected_order, 2)
        self.assertTrue(result.joint_valid)
        self.assertAlmostEqual(
            result.selected.paths[1].delay_samples - result.selected.paths[0].delay_samples,
            3.0,
            delta=0.2,
        )
        self.assertAlmostEqual(
            result.selected.paths[1].doppler_hz - result.selected.paths[0].doppler_hz,
            30.0,
            delta=5.0,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
