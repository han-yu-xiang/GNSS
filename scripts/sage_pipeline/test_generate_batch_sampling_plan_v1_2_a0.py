import csv
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generate_batch_sampling_plan_v1_2_a0 import (  # noqa: E402
    A0_RULE_HASH,
    A0_SELECTION_SPEC,
    Component,
    FINE_CLOSURE_RADIUS,
    PLANNER_VERSION,
    apply_budget,
    build_components,
    build_feature_rows,
    canonical_hash,
    continuity_segments,
    load_gold_after_freeze,
    promotion_rows_for_profile,
    TaskData,
    TaskSpec,
)


def stage0_row(window_id, sample_start, tow, cn0=45.0, doppler=-1000.0, code=1023000.0):
    return {
        "window_id": window_id,
        "sample_start_zero_based": str(sample_start),
        "tow_s": str(tow),
        "recording_time_s": str(tow),
        "cn0_db_hz": str(cn0),
        "tracking_doppler_hz": str(doppler),
        "code_frequency_hz": str(code),
        "vehicle_speed_kmh": "NaN",
        "relative_doppler_bound_hz": "350",
        "sample_start_value": float(sample_start),
        "tow_s_value": float(tow),
        "recording_time_value": float(tow),
    }


def synthetic_data(count=40, break_at=None):
    rows = []
    sample = 0
    tow = 0.0
    for window_id in range(1, count + 1):
        if break_at and window_id == break_at:
            sample += 100
            tow += 0.5
        rows.append(stage0_row(window_id, sample, tow, cn0=45 - (5 if window_id in {20, 21} else 0), doppler=-1000 + (100 if window_id in {20, 21} else 0)))
        sample += 204600
        tow += 0.020
    return rows


class A0Tests(unittest.TestCase):
    def test_rule_hash_is_frozen_and_gold_flag_is_false(self):
        self.assertEqual(A0_RULE_HASH, canonical_hash(A0_SELECTION_SPEC))
        self.assertFalse(A0_SELECTION_SPEC["gold_labels_used_for_selection"])
        self.assertEqual(PLANNER_VERSION, "batch-sampled-v1.2-a0")

    def test_continuity_break_stops_segments_and_rolling_input(self):
        rows = synthetic_data(12, break_at=7)
        segments, to_prev, to_next, reasons = continuity_segments(rows)
        self.assertNotEqual(segments[5], segments[6])
        self.assertFalse(to_prev[6])
        self.assertFalse(to_next[5])
        self.assertIn("sample_gap", reasons[6])

    def test_feature_extraction_marks_missing_fields_and_geometry(self):
        task = TaskSpec("test_task", "test", "scene", "G01", 0)
        data = TaskData(task, Path("stage0.csv"), "hash", synthetic_data(12), None, None, {}, "unavailable", "missing")
        rows = build_feature_rows(data)
        self.assertEqual(len(rows), 12)
        self.assertIn("prompt_i", rows[0]["feature_missing"])
        self.assertIn("geometry_unavailable", rows[0]["feature_missing"])
        self.assertEqual(rows[0]["geometry_join_status"], "unavailable")
        self.assertEqual(rows[0]["score_rule_hash"], A0_RULE_HASH)

    def test_hysteresis_component_merge_is_continuous(self):
        rows = []
        for index in range(1, 12):
            row = stage0_row(index, (index - 1) * 204600, (index - 1) * 0.020)
            row.update({"segment_id": 0, "feature_score": 0.5})
            rows.append(row)
        for index in (4, 6):
            rows[index - 1]["feature_score"] = 3.0
        rows[4]["feature_score"] = 1.0  # fixed two-window bridge between high seeds
        components = build_components(rows)
        self.assertEqual(len(components), 1)
        self.assertIn(5, components[0].component_windows)
        self.assertEqual(components[0].first_window, 4)
        self.assertEqual(components[0].last_window, 6)

    def test_budget_never_truncates_and_marks_inconclusive(self):
        component = Component("c1", 0, (10,), tuple(range(1, 20)), tuple(range(1, 20)), tuple(range(1, 25)), 5.0, 1, 19, False)
        rows = [{"window_id": index} for index in range(1, 30)]
        selected, exhausted, inconclusive, statuses = apply_budget(rows, [component], 10)
        self.assertEqual(selected, set())
        self.assertTrue(exhausted)
        self.assertEqual(inconclusive, 1)
        self.assertEqual(statuses["c1"], "inconclusive_budget_exhausted")

    def test_gold_guard_rejects_unfrozen_access(self):
        task = TaskSpec("test_task", "test", "scene", "G01", 0)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                load_gold_after_freeze(Path(directory), task, {"selection_frozen": False, "gold_labels_used_for_selection": False})

    def test_manifest_field_names_include_provenance(self):
        from generate_batch_sampling_plan_v1_2_a0 import selection_fieldnames

        fields = set(selection_fieldnames())
        for field in ("feature_missing", "promotion_component_id", "not_promoted", "coverage_status", "gold_labels_used_for_selection", "rule_hash"):
            self.assertIn(field, fields)


if __name__ == "__main__":
    unittest.main()
