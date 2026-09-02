import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from derive_channel_parameters import (  # noqa: E402
    aggregate_event_parameters,
    derive_path_parameters,
    elevation_band,
    summarize_parameter_group,
)


class DeriveChannelParametersTests(unittest.TestCase):
    def test_derives_path_delay_length_and_preserves_signed_doppler(self):
        source = {
            "event_path_id": "path-1",
            "event_id": "event-1",
            "run_id": "run-1",
            "scene_id": "scene-1",
            "prn": "G25",
            "path_id": "2",
            "is_multipath": "1",
            "label_value": "confirmed_multipath",
            "excess_delay_samples": "1.2",
            "excess_delay_chips": "0.12",
            "doppler_offset_hz": "-4.5",
            "relative_power_db": "-8.6",
            "elevation_deg": "83.0",
            "geometry_join_valid": "1",
            "environment_class": "Mountain/Valley",
        }

        result = derive_path_parameters(source)

        self.assertAlmostEqual(result["excess_delay_s"], 1.2 / 10_230_000.0)
        self.assertAlmostEqual(
            result["excess_path_length_m"], 299_792_458.0 * 1.2 / 10_230_000.0
        )
        self.assertEqual(result["relative_doppler_hz"], -4.5)
        self.assertEqual(result["elevation_band"], "HIGH")
        self.assertEqual(result["parameter_source_status"], "complete")

    def test_elevation_band_boundaries_are_explicit(self):
        self.assertEqual(elevation_band(0.0), "LOW")
        self.assertEqual(elevation_band(29.999), "LOW")
        self.assertEqual(elevation_band(30.0), "MID")
        self.assertEqual(elevation_band(59.999), "MID")
        self.assertEqual(elevation_band(60.0), "HIGH")
        self.assertEqual(elevation_band(90.0), "HIGH")
        self.assertIsNone(elevation_band(None))

    def test_event_aggregation_is_descriptive_and_counts_confirmed_paths(self):
        paths = [
            {
                "event_id": "event-1",
                "scene_id": "scene-1",
                "environment_class": "Urban",
                "elevation_band": "MID",
                "elevation_deg": 45.0,
                "excess_delay_chips": 0.1,
                "excess_delay_s": 0.1 / 1_023_000.0,
                "excess_path_length_m": 29.3,
                "relative_doppler_hz": -2.0,
                "relative_power_db": -8.0,
            },
            {
                "event_id": "event-1",
                "scene_id": "scene-1",
                "environment_class": "Urban",
                "elevation_band": "MID",
                "elevation_deg": 45.0,
                "excess_delay_chips": 0.2,
                "excess_delay_s": 0.2 / 1_023_000.0,
                "excess_path_length_m": 58.6,
                "relative_doppler_hz": 3.0,
                "relative_power_db": -4.0,
            },
        ]

        result = aggregate_event_parameters(paths)

        self.assertEqual(result["confirmed_path_count"], 2)
        self.assertEqual(result["max_excess_delay_chips"], 0.2)
        self.assertEqual(result["median_relative_power_db"], -6.0)
        self.assertEqual(result["min_relative_doppler_hz"], -2.0)
        self.assertEqual(result["max_relative_doppler_hz"], 3.0)

    def test_group_summary_reports_descriptive_counts_and_medians(self):
        paths = [
            {
                "event_id": "event-1",
                "scene_id": "scene-1",
                "excess_delay_chips": 0.1,
                "excess_delay_s": 0.1 / 1_023_000.0,
                "excess_path_length_m": 29.3,
                "relative_doppler_hz": -2.0,
                "relative_power_db": -8.0,
            },
            {
                "event_id": "event-1",
                "scene_id": "scene-1",
                "excess_delay_chips": 0.2,
                "excess_delay_s": 0.2 / 1_023_000.0,
                "excess_path_length_m": 58.6,
                "relative_doppler_hz": 3.0,
                "relative_power_db": -4.0,
            },
        ]

        result = summarize_parameter_group("environment_class", "Urban", paths)

        self.assertEqual(result["group_dimension"], "environment_class")
        self.assertEqual(result["group_value"], "Urban")
        self.assertEqual(result["path_count"], 2)
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["scene_count"], 1)
        self.assertAlmostEqual(result["median_excess_delay_chips"], 0.15)


if __name__ == "__main__":
    unittest.main()
