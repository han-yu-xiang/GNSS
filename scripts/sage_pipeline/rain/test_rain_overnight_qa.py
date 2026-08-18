import math
import unittest
from pathlib import Path

from scripts.sage_pipeline.rain.audit_rain_sage_overnight_outputs import (
    audit_task_record,
    circular_mean,
    linear_stats,
    parse_bool,
    parse_float,
    summarize_parameter_rows,
)


class RainOvernightQaTests(unittest.TestCase):
    def test_boolean_and_numeric_parsing(self) -> None:
        self.assertTrue(parse_bool("True"))
        self.assertTrue(parse_bool("1"))
        self.assertFalse(parse_bool("false"))
        self.assertEqual(parse_float("1.25"), 1.25)
        self.assertIsNone(parse_float("NaN"))

    def test_linear_stats_are_deterministic(self) -> None:
        stats = linear_stats([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(stats["N"], 4)
        self.assertEqual(stats["median"], 2.5)
        self.assertEqual(stats["P50"], 2.5)
        self.assertEqual(stats["IQR"], 1.5)

    def test_circular_mean_wraps_at_pi(self) -> None:
        value = circular_mean([math.pi - 0.1, -math.pi + 0.1])
        self.assertIsNotNone(value)
        self.assertAlmostEqual(abs(value), math.pi, places=6)

    def test_parameter_summary_keeps_four_tuple_fields(self) -> None:
        rows = [
            {
                "excess_delay": "2.0",
                "relative_doppler_hz": "-3.0",
                "relative_phase_rad": "0.5",
                "relative_amplitude": "0.8",
            }
        ]
        summary = summarize_parameter_rows(rows)
        self.assertEqual(summary["excess_delay"]["N"], 1)
        self.assertEqual(summary["relative_doppler_hz"]["N"], 1)
        self.assertEqual(summary["relative_phase_rad"]["N"], 1)
        self.assertEqual(summary["relative_amplitude"]["N"], 1)

    def test_missing_outputs_fail_closed_without_inventing_zero_event(self) -> None:
        record = {
            "sequence": 1,
            "weather": "Clear",
            "scene": "F1023_clear",
            "prn": "G24",
            "channel": 10,
            "matlab_exit_code": 0,
            "output_dir": str(Path("E:/nonexistent/rain_sage_v1/G24")),
            "failure_reason": "",
        }
        result = audit_task_record(record)
        self.assertTrue(result["missing_outputs"])
        self.assertEqual(result["overall_status"], "SOFTWARE_FAIL")


if __name__ == "__main__":
    unittest.main()
