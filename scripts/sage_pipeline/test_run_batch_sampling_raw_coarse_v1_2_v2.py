import json
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_batch_sampling_raw_coarse_v1_2_v2 as v2  # noqa: E402


class RawCoarseV2Tests(unittest.TestCase):
    def test_true_doppler_profiles_are_frozen(self):
        self.assertEqual(v2.PROFILES[0].doppler_offsets_hz, (-100, 0, 100))
        self.assertEqual(v2.PROFILES[2].doppler_offsets_hz, (-200, 0, 200))
        self.assertEqual(v2.PARAMETER_SPEC["gold_labels_used_for_selection"], False)

    def test_parameter_hash_is_canonical_and_cache_key_is_complete(self):
        self.assertEqual(v2.PARAMETER_HASH, v2.legacy.canonical_hash(v2.PARAMETER_SPEC))
        self.assertNotEqual(v2.code_cache_key("G16", 102300, 10230000), v2.code_cache_key("G16", 102301, 10230000))
        self.assertNotEqual(v2.code_cache_key("G16", 102300, 10230000), v2.code_cache_key("G25", 102300, 10230000))
        self.assertIn("code_frequency_rule", v2.PARAMETER_SPEC["code_cache"]["cache_key"])

    def test_manifest_does_not_claim_fine_stage(self):
        self.assertFalse(v2.PARAMETER_SPEC["coarse_sampling"]["fine_refine"])
        self.assertFalse(v2.PARAMETER_SPEC["sage_called"])
        self.assertNotIn("stage1_nav_fast_scan.csv", json.dumps(v2.PARAMETER_SPEC))

    def test_microbenchmark_subset_is_gold_independent(self):
        self.assertIn("catalog positions", v2.PARAMETER_SPEC["microbenchmark"]["subset_rule"])
        self.assertFalse(v2.PARAMETER_SPEC["gold_labels_used_for_selection"])

    def test_preflight_refuses_missing_compiled_backend(self):
        if v2.np is None:
            result = v2._preflight(Path("X:/sampling-v2"))
            self.assertFalse(result["preflight_pass"])
            self.assertIn("unavailable", result["reason"])

    def test_b1_and_b2_use_distinct_contiguous_block_groups(self):
        b1 = v2.PROFILES[0]
        b2 = v2.PROFILES[1]
        self.assertEqual(((0, 1), (2, 3)), ((0, 1), (2, 3)))
        self.assertEqual(b1.subblock_ms, 20)
        self.assertEqual(b2.subblock_ms, 10)

    def test_alignment_tolerances_are_not_relaxed(self):
        self.assertEqual(v2.OLD_NEW_SCORE_TOLERANCE, 1e-8)
        self.assertEqual(v2.OLD_NEW_PEAK_RATIO_TOLERANCE_DB, 1e-8)
        self.assertEqual(v2.OLD_NEW_DELAY_TOLERANCE_SAMPLES, 0)
        self.assertEqual(v2.OLD_NEW_DOPPLER_TOLERANCE_HZ, 1e-8)

    def test_frequency_tie_break_matches_legacy_first_winner(self):
        if v2.np is None:
            self.skipTest("NumPy backend is not installed in this interpreter")
        import numpy as np

        corr = np.asarray([[1 + 0j, 2 + 0j], [1 + 0j, 1 + 0j], [0 + 0j, 2 + 0j]], dtype=np.complex128)
        self.assertEqual(v2._stable_best_frequency(corr).tolist(), [0, 0])

    def test_doppler_phase_reference_is_negative_exponential(self):
        row = v2.legacy.Stage0Row(1, 1000, 1, -1, -3000.0, 1023000.0, None, None)
        phase = v2._phase_diagnostic(row, 0, 900, v2.PROFILES[0])
        self.assertEqual(phase["block_relative_start_sample"], 0)
        self.assertEqual(phase["doppler_grid_hz"][0], -3100.0)
        self.assertEqual(phase["delay_phase_offsets_original_samples"], [-2, -1, 0, 1, 2])

    def test_numpy_kernel_synthetic_zero_iq_covers_all_profiles(self):
        if v2.np is None:
            self.skipTest("NumPy backend is not installed in this interpreter")
        row = v2.legacy.Stage0Row(1, 100, 1, -1, -3000.0, 1023000.0, None, None)
        raw = v2.np.zeros((v2.legacy.WINDOW_SAMPLES + 8, 2), dtype=v2.np.int16).tobytes()
        view = memoryview(raw).cast("h")
        old = v2.legacy.process_window(view, 98, row, v2.PROFILES, v2.cached_ca_code("G16"))
        new = v2.process_window_numpy(view, 98, row, v2.PROFILES, v2.cached_ca_code("G16"))
        self.assertEqual(set(old), {"B1_20msx2_D100", "B2_10msx4_D100", "B2_10msx4_D200"})
        self.assertEqual(set(new), set(old))
        for profile_id in old:
            self.assertEqual(old[profile_id]["delay_separation_samples"], new[profile_id]["delay_separation_samples"])
            self.assertAlmostEqual(float(old[profile_id]["coarse_score_db"]), float(new[profile_id]["coarse_score_db"]), places=8)


if __name__ == "__main__":
    unittest.main()
