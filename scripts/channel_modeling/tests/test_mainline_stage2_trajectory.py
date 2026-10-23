from __future__ import annotations

import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.channel_modeling.mainline_stage2_trajectory import (
    parse_valid_rmc_fixes,
    split_trajectory_components,
)


def checksummed(body: str, *, corrupt: bool = False) -> str:
    checksum = 0
    for character in body:
        checksum ^= ord(character)
    if corrupt:
        checksum ^= 1
    return f"${body}*{checksum:02X}"


def rmc(
    time_text: str,
    date_text: str = "230424",
    *,
    status: str = "A",
    latitude: str = "4807.038",
    latitude_hemisphere: str = "N",
    longitude: str = "01131.000",
    longitude_hemisphere: str = "E",
    speed_knots: str = "10.0",
    course_degrees: str = "90.0",
    talker: str = "GP",
    corrupt: bool = False,
) -> str:
    return checksummed(
        f"{talker}RMC,{time_text},{status},{latitude},{latitude_hemisphere},"
        f"{longitude},{longitude_hemisphere},{speed_knots},{course_degrees},"
        f"{date_text},,,A",
        corrupt=corrupt,
    )


def trajectory_fix(seconds: float, latitude_deg: float, longitude_deg: float = 0.0):
    return {
        "utc_time": datetime(2024, 4, 23, tzinfo=timezone.utc)
        + timedelta(seconds=seconds),
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
    }


class MainlineStage2TrajectoryRmcTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def parse_lines(self, name: str, lines: list[str]):
        path = self.root / name
        path.write_text("\n".join(lines) + "\n", encoding="ascii")
        return parse_valid_rmc_fixes([path])

    def test_requires_checksum_valid_active_rmc_and_preserves_source_identity(self):
        fixes = self.parse_lines(
            "track.nmea",
            [
                rmc("120000.00", status="V"),
                rmc("120001.00", corrupt=True),
                rmc("120002.00").split("*", 1)[0],
                checksummed("GPGGA,120003.00,4807.038,N,01131.000,E,1,08,0.9,0,M,0,M,,"),
                rmc("120004.25", talker="GN", speed_knots="", course_degrees=""),
            ],
        )

        self.assertEqual(len(fixes), 1)
        self.assertEqual(fixes[0]["utc_time"], datetime(2024, 4, 23, 12, 0, 4, 250000, tzinfo=timezone.utc))
        self.assertEqual(fixes[0]["source_path"], str((self.root / "track.nmea").resolve()))
        self.assertEqual(fixes[0]["source_record_id"], "track.nmea:000005")
        self.assertIsNone(fixes[0]["receiver_speed_knots"])
        self.assertIsNone(fixes[0]["receiver_course_deg"])

    def test_uses_rmc_calendar_date_across_midnight(self):
        fixes = self.parse_lines(
            "midnight.nmea",
            [
                rmc("235959.750", "230424"),
                rmc("000000.250", "240424"),
            ],
        )

        self.assertEqual(
            [fix["utc_time"] for fix in fixes],
            [
                datetime(2024, 4, 23, 23, 59, 59, 750000, tzinfo=timezone.utc),
                datetime(2024, 4, 24, 0, 0, 0, 250000, tzinfo=timezone.utc),
            ],
        )

    def test_rejects_out_of_range_coordinates_and_invalid_hemispheres(self):
        fixes = self.parse_lines(
            "bounds.nmea",
            [
                rmc("120000.00", latitude="9000.000", latitude_hemisphere="N", longitude="18000.000", longitude_hemisphere="W"),
                rmc("120001.00", latitude="9000.001"),
                rmc("120002.00", longitude="18000.001"),
                rmc("120003.00", latitude="4860.000"),
                rmc("120004.00", latitude_hemisphere="E"),
                rmc("120005.00", longitude_hemisphere="S"),
            ],
        )

        self.assertEqual(len(fixes), 1)
        self.assertEqual(fixes[0]["latitude_deg"], 90.0)
        self.assertEqual(fixes[0]["longitude_deg"], -180.0)

    def test_drops_duplicate_and_out_of_order_timestamps_within_source(self):
        fixes = self.parse_lines(
            "ordered.nmea",
            [
                rmc("120000.00"),
                rmc("120002.00"),
                rmc("120001.00"),
                rmc("120002.00", latitude="4807.100"),
                rmc("120003.00"),
            ],
        )

        self.assertEqual(
            [fix["utc_time"] for fix in fixes],
            [
                datetime(2024, 4, 23, 12, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 23, 12, 0, 2, tzinfo=timezone.utc),
                datetime(2024, 4, 23, 12, 0, 3, tzinfo=timezone.utc),
            ],
        )
        self.assertEqual([fix["source_record_id"] for fix in fixes], [
            "ordered.nmea:000001", "ordered.nmea:000002", "ordered.nmea:000005"
        ])

    def test_returns_receiver_speed_in_knots_and_metres_per_second(self):
        (fix,) = self.parse_lines("speed.nmea", [rmc("120000.00", speed_knots="10.0", course_degrees="359.5")])

        self.assertEqual(fix["receiver_speed_knots"], 10.0)
        self.assertAlmostEqual(fix["receiver_speed_mps"], 10.0 * 0.5144444444444445)
        self.assertEqual(fix["receiver_course_deg"], 359.5)


class MainlineStage2TrajectoryComponentTests(unittest.TestCase):
    def test_gap_at_boundary_is_connected_and_gap_above_boundary_starts_component(self):
        fixes = [
            trajectory_fix(0.0, 0.0),
            trajectory_fix(2.5, 0.00001),
            trajectory_fix(5.0001, 0.00002),
        ]

        result = split_trajectory_components(fixes)

        self.assertEqual([row["component_id"] for row in result], ["component_0001", "component_0001", "component_0002"])
        self.assertEqual(result[1]["break_reason"], "")
        self.assertEqual(result[2]["break_reason"], "TIME_GAP")
        self.assertAlmostEqual(result[1]["cumulative_distance_m"], result[1]["adjacent_distance_m"])
        self.assertEqual(result[2]["cumulative_distance_m"], 0.0)
        self.assertIsNone(result[2]["adjacent_distance_m"])

    def test_duplicate_and_out_of_order_times_break_without_bridging(self):
        fixes = [
            trajectory_fix(0.0, 0.0),
            trajectory_fix(1.0, 0.00001),
            trajectory_fix(1.0, 0.00002),
            trajectory_fix(0.5, 0.00003),
            trajectory_fix(1.5, 0.00004),
        ]

        result = split_trajectory_components(fixes)

        self.assertEqual(
            [row["component_id"] for row in result],
            ["component_0001", "component_0001", "component_0002", "component_0003", "component_0003"],
        )
        self.assertEqual(result[2]["break_reason"], "DUPLICATE_TIMESTAMP")
        self.assertEqual(result[3]["break_reason"], "OUT_OF_ORDER_TIMESTAMP")
        self.assertIsNone(result[2]["adjacent_distance_m"])
        self.assertIsNone(result[3]["adjacent_distance_m"])
        self.assertAlmostEqual(result[4]["implied_speed_mps"], result[4]["adjacent_distance_m"])

    def test_implied_speed_jump_starts_new_component_and_resets_distance(self):
        fixes = [
            trajectory_fix(0.0, 0.0),
            trajectory_fix(1.0, 0.001),
            trajectory_fix(2.0, 0.0011),
        ]

        result = split_trajectory_components(fixes, jump_speed_mps=80.0)

        self.assertEqual([row["component_id"] for row in result], ["component_0001", "component_0002", "component_0002"])
        self.assertEqual(result[1]["break_reason"], "JUMP_SPEED_LIMIT")
        self.assertGreater(result[1]["candidate_speed_mps"], 80.0)
        self.assertIsNone(result[1]["adjacent_distance_m"])
        self.assertEqual(result[1]["cumulative_distance_m"], 0.0)
        self.assertGreater(result[2]["adjacent_distance_m"], 0.0)
        self.assertEqual(result[2]["cumulative_distance_m"], result[2]["adjacent_distance_m"])

    def test_haversine_distance_and_cumulative_distance(self):
        fixes = [trajectory_fix(0.0, 0.0), trajectory_fix(1.0, 0.001), trajectory_fix(2.0, 0.002)]

        result = split_trajectory_components(fixes, jump_speed_mps=200.0)

        self.assertIsNone(result[0]["adjacent_distance_m"])
        self.assertAlmostEqual(result[1]["adjacent_distance_m"], 111.195, places=3)
        self.assertAlmostEqual(result[1]["implied_speed_mps"], 111.195, places=3)
        self.assertAlmostEqual(result[2]["cumulative_distance_m"], 222.390, places=3)

    def test_rejects_invalid_thresholds_and_fix_coordinates(self):
        with self.assertRaisesRegex(ValueError, "max_gap_seconds"):
            split_trajectory_components([trajectory_fix(0, 0)], max_gap_seconds=0)
        with self.assertRaisesRegex(ValueError, "jump_speed_mps"):
            split_trajectory_components([trajectory_fix(0, 0)], jump_speed_mps=float("nan"))
        with self.assertRaisesRegex(ValueError, "latitude"):
            split_trajectory_components([trajectory_fix(0, 91)])
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            split_trajectory_components([{"utc_time": datetime(2024, 1, 1), "latitude_deg": 0, "longitude_deg": 0}])


if __name__ == "__main__":
    unittest.main()
