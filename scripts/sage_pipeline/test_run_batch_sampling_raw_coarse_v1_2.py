import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_batch_sampling_raw_coarse_v1_2 import (  # noqa: E402
    BOUNDARY_EXPANSION_WINDOWS,
    CoarseProfile,
    DELAY_PHASES,
    FINE_CLOSURE_RADIUS,
    PARAMETER_HASH,
    PARAMETER_SPEC,
    Stage0Row,
    TASKS,
    _metric_from_correlations,
    _window_component_rows,
    build_chunk_plan,
    canonical_hash,
    doppler_grid,
    generate_ca_code,
    load_gold_after_freeze,
    nav_wipe,
    process_window,
    project_budget,
)


class RawCoarsePrototypeTests(unittest.TestCase):
    def test_parameter_hash_and_gold_leakage_guard(self):
        self.assertEqual(PARAMETER_HASH, canonical_hash(PARAMETER_SPEC))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                load_gold_after_freeze(Path(directory), TASKS[0], {"selection_frozen": False, "gold_labels_used_for_selection": False})

    def test_int16_iq_layout_and_sample_offset(self):
        import struct

        raw = b"".join(struct.pack("<hh", index, -index) for index in range(8))
        view = memoryview(raw).cast("h")
        sample_offset = 3
        self.assertEqual(view[2 * sample_offset], 3)
        self.assertEqual(view[2 * sample_offset + 1], -3)

    def test_nav_wipe_is_deterministic(self):
        values = [1 + 2j, -3 + 4j]
        self.assertEqual(nav_wipe(1, values), values)
        self.assertEqual(nav_wipe(-1, values), [-value for value in values])
        self.assertEqual(generate_ca_code(16), generate_ca_code(16))
        self.assertEqual(len(generate_ca_code(16)), 1023)

    def test_chunk_plan_reuses_overlapping_windows(self):
        rows = tuple(Stage0Row(index + 1, index * 204600, 1, -1, -3000.0, 1023000.0, None, None) for index in range(8))
        plans = build_chunk_plan(rows)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].start_sample, 0)
        self.assertEqual(plans[0].end_sample_exclusive, 7 * 204600 + 409200 + 2)
        self.assertLess(plans[0].byte_count, len(rows) * 409200 * 4)

    def test_b1_b2_block_slicing_and_deterministic_window_score(self):
        row = Stage0Row(1, 100, 1, -1, -3000.0, 1023000.0, 1.0, 1.0)
        # The test uses zero IQ, so the output is deterministic and finite;
        # it exercises the 40ms -> four 10ms primitive without any raw file.
        raw = b"\x00\x00" * (4 * 409200)
        view = memoryview(raw).cast("h")
        profiles = (
            CoarseProfile("B1_20msx2_D100", "B1", 20, 100),
            CoarseProfile("B2_10msx4_D100", "B2", 10, 100),
            CoarseProfile("B2_10msx4_D200", "B2", 10, 200),
        )
        result_a = process_window(view, 98, row, profiles, generate_ca_code(16))
        result_b = process_window(view, 98, row, profiles, generate_ca_code(16))
        self.assertEqual(result_a, result_b)
        self.assertEqual(set(result_a), {profile.profile_id for profile in profiles})
        self.assertTrue(all(result_a[profile.profile_id]["coarse_evidence_only"] == "true" for profile in profiles))

    def test_declared_doppler_half_width_defines_the_actual_grid(self):
        d100 = CoarseProfile("B2_10msx4_D100", "B2", 10, 100)
        d200 = CoarseProfile("B2_10msx4_D200", "B2", 10, 200)
        self.assertEqual(d100.doppler_offsets_hz, (-100, 0, 100))
        self.assertEqual(d200.doppler_offsets_hz, (-200, 0, 200))
        row = Stage0Row(1, 0, 1, -1, -3000.0, 1023000.0, None, None)
        self.assertEqual(doppler_grid(row, d100), (-3100.0, -3000.0, -2900.0, 2900.0, 3000.0, 3100.0))

    def test_score_and_component_merge(self):
        profile = CoarseProfile("B2_10msx4_D100", "B2", 10, 100)
        rows = [{"window_id": index, "coarse_score_db": -5.0 if index in (4, 6) else -12.0} for index in range(1, 10)]
        components, reasons = _window_component_rows(rows, profile)
        self.assertEqual(len(components), 1)
        self.assertIn(5, components[0].window_ids)
        self.assertIn(4, reasons)
        self.assertEqual(components[0].promoted_window_ids[0], 1)

    def test_projection_marks_over_budget_without_truncation(self):
        profile = CoarseProfile("B2_10msx4_D100", "B2", 10, 100)
        rows = [{"window_id": index, "coarse_score_db": -5.0} for index in range(1, 6001)]
        components, _ = _window_component_rows(rows, profile)
        projected = project_budget(set(range(1, 6001)), components, set(range(1, 6001)))
        self.assertGreater(projected["potential_fine_window_count"], 4800)
        self.assertEqual(projected["budget_projection"]["4800"]["status"], "budget_exhausted_inconclusive")

    def test_metric_peak_separation_is_not_a_multipath_label(self):
        metric = _metric_from_correlations([10 + 0j, 1 + 0j, 8 + 0j, 2 + 0j, 1 + 0j], DELAY_PHASES, 5)
        self.assertEqual(metric["delay_separation_samples"], 2)
        self.assertLess(metric["score_db"], 0.0)


if __name__ == "__main__":
    unittest.main()
