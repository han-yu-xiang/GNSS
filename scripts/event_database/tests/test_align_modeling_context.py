import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from align_modeling_context import (
    classify_event_modeling_flags,
    gps_tow_to_utc,
    max_time_origin_error_seconds,
    nearest_geometry_record,
)


class AlignModelingContextTests(unittest.TestCase):
    def test_gps_tow_uses_frozen_eighteen_second_offset(self):
        result = gps_tow_to_utc(2403, 218628.52, leap_seconds=18)
        self.assertEqual(result, datetime(2026, 1, 27, 12, 43, 30, 520000, tzinfo=timezone.utc))

    def test_nearest_geometry_requires_matching_prn_and_tolerance(self):
        target = datetime(2026, 1, 27, 12, 43, 30, 520000, tzinfo=timezone.utc)
        rows = [
            {"prn": "G11", "utc_time": "2026-01-27T12:43:30.000Z"},
            {"prn": "G31", "utc_time": "2026-01-27T12:43:30.990Z"},
        ]
        match = nearest_geometry_record(target, rows, prn="G31", tolerance_seconds=5.0)
        self.assertIsNotNone(match)
        self.assertEqual(match["prn"], "G31")
        self.assertAlmostEqual(match["delta_seconds"], 0.47, places=6)

        self.assertIsNone(
            nearest_geometry_record(target, rows, prn="G25", tolerance_seconds=5.0)
        )

    def test_legacy_g06_is_excluded_but_geometry_gap_is_flagged(self):
        legacy = classify_event_modeling_flags(
            legacy_context_missing=True,
            geometry_join_valid=False,
            confirmed=True,
        )
        self.assertEqual(legacy["run_modeling_status"], "excluded_legacy_context_missing")
        self.assertEqual(legacy["include_in_environment_modeling"], "0")
        self.assertEqual(legacy["include_in_elevation_modeling"], "0")

        partial = classify_event_modeling_flags(
            legacy_context_missing=False,
            geometry_join_valid=False,
            confirmed=True,
        )
        self.assertEqual(partial["run_modeling_status"], "ready_with_geometry_exclusions")
        self.assertEqual(partial["include_in_environment_modeling"], "1")
        self.assertEqual(partial["include_in_elevation_modeling"], "0")

    def test_time_origin_error_aggregates_datetime_values(self):
        center = datetime(2026, 1, 27, 12, 43, 30, tzinfo=timezone.utc)
        values = [center, center + __import__("datetime").timedelta(milliseconds=12)]
        self.assertAlmostEqual(max_time_origin_error_seconds(values, center), 0.012)


if __name__ == "__main__":
    unittest.main()
