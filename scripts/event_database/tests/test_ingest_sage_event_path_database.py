import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ingest_sage_event_path_database import (  # noqa: E402
    build_event_context_row,
    classify_run_label,
    modeling_eligibility,
)


class IngestRuleTests(unittest.TestCase):
    def test_legacy_missing_context_is_excluded_from_modeling_not_deleted(self):
        self.assertEqual(
            modeling_eligibility(context_present=False, run_complete=True),
            "excluded_legacy_context_missing",
        )

    def test_zero_event_standard_run_gets_no_confirmed_event_label(self):
        self.assertEqual(
            classify_run_label(confirmed_events=0, reference_control=False),
            "no_confirmed_event",
        )

    def test_unverified_geometry_keeps_event_angles_null(self):
        row = build_event_context_row(
            event_id="run__G32__w10",
            run_id="run",
            scene_id="scene",
            prn="G32",
            center_window_id="w10",
            recording_time_s="12.5",
            tow_s="345.0",
            cn0_db_hz="45.0",
            vehicle_speed_kmh="120",
            speed_source="fallback_120_kmh",
        )
        self.assertIsNone(row["event_utc"])
        self.assertIsNone(row["elevation_deg"])
        self.assertIsNone(row["azimuth_deg"])
        self.assertEqual(row["geometry_join_status"], "deferred_unavailable")


if __name__ == "__main__":
    unittest.main()
