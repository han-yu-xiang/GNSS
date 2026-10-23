from __future__ import annotations

import math
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.channel_modeling.mainline_stage2_trajectory import (
    aggregate_stage2_metrics_by_fix,
    build_route_segment_rows,
    build_trajectory_window_overlay,
    parse_valid_rmc_fixes,
    split_trajectory_components,
    summarize_spatial_dependence,
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


def route_fix(
    scene: str,
    component: str,
    seconds: float,
    cumulative_distance_m: float,
    *,
    latitude_deg: float = 0.0,
    longitude_deg: float = 0.0,
    speed_mps: float | None = 5.0,
    course_deg: float | None = 90.0,
    source_record_id: str | None = None,
):
    return {
        "scene_id": scene,
        "component_id": component,
        "utc_time": datetime(2024, 4, 23, tzinfo=timezone.utc)
        + timedelta(seconds=seconds),
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
        "cumulative_distance_m": cumulative_distance_m,
        "receiver_speed_mps": speed_mps,
        "receiver_course_deg": course_deg,
        "source_path": f"{scene}.nmea",
        "source_record_id": source_record_id or f"{scene}.nmea:{seconds}",
    }


def stage2_window(run_id: str, window_id: str, scene: str, prn: str = "G03"):
    return {
        "run_id": run_id,
        "window_id": window_id,
        "scene_id": scene,
        "prn": prn,
        "tracking_channel": "2",
    }


def stage2_path(
    run_id: str,
    window_id: str,
    scene: str,
    prn: str,
    path_id: str,
    *,
    multipath: bool,
    excess_delay_chips: str = "",
    doppler_offset_hz: str = "",
    relative_power_db: str = "",
):
    return {
        "run_id": run_id,
        "window_id": window_id,
        "scene_id": scene,
        "prn": prn,
        "tracking_channel": "2",
        "path_id": path_id,
        "is_multipath": "1" if multipath else "0",
        "modeling_role": "MPC_CANDIDATE" if multipath else "DIRECT_REFERENCE",
        "excess_delay_chips": excess_delay_chips,
        "doppler_offset_hz": doppler_offset_hz,
        "relative_power_db": relative_power_db,
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


class MainlineStage2TrajectoryOverlayTests(unittest.TestCase):
    def test_preserves_all_keys_uses_same_scene_and_breaks_ties_by_earlier_fix(self):
        t0 = datetime(2024, 4, 23, tzinfo=timezone.utc)
        windows = [stage2_window("run-a", "1", "scene-a"), stage2_window("run-b", "1", "scene-b")]
        utc = {("run-a", "1"): t0 + timedelta(seconds=1), ("run-b", "1"): t0 + timedelta(seconds=1)}
        fixes = {
            "scene-a": [
                route_fix("scene-a", "component_0001", 0, 0, source_record_id="a:1"),
                route_fix("scene-a", "component_0001", 2, 10, source_record_id="a:2"),
            ]
        }

        overlay = build_trajectory_window_overlay(windows, utc, fixes)

        self.assertEqual([(row["run_id"], row["window_id"]) for row in overlay], [("run-a", "1"), ("run-b", "1")])
        self.assertEqual(overlay[0]["position_status"], "POSITION_MATCHED")
        self.assertEqual(overlay[0]["position_source_record_id"], "a:1")
        self.assertEqual(overlay[0]["position_delta_seconds"], "-1")
        self.assertEqual(overlay[1]["position_status"], "POSITION_MISSING")
        self.assertEqual(overlay[1]["missing_reason"], "NO_VALID_SCENE_FIX")

    def test_position_tolerance_boundary_is_inclusive_and_overrun_is_missing(self):
        t0 = datetime(2024, 4, 23, tzinfo=timezone.utc)
        windows = [stage2_window("run-a", "1", "scene-a"), stage2_window("run-a", "2", "scene-a")]
        utc = {
            ("run-a", "1"): t0 + timedelta(seconds=2.5),
            ("run-a", "2"): t0 + timedelta(seconds=2.500001),
        }
        fixes = {"scene-a": [route_fix("scene-a", "component_0001", 0, 12.5)]}

        overlay = build_trajectory_window_overlay(windows, utc, fixes)

        self.assertEqual(overlay[0]["position_status"], "POSITION_MATCHED")
        self.assertEqual(overlay[0]["position_delta_seconds_abs"], "2.5")
        self.assertEqual(overlay[1]["missing_reason"], "OUTSIDE_POSITION_TOLERANCE")

    def test_windows_inside_component_break_gap_are_not_carried_to_either_fix(self):
        t0 = datetime(2024, 4, 23, tzinfo=timezone.utc)
        windows = [
            stage2_window("run-a", "before", "scene-a"),
            stage2_window("run-a", "gap", "scene-a"),
            stage2_window("run-a", "after", "scene-a"),
        ]
        utc = {
            ("run-a", "before"): t0 - timedelta(seconds=0.5),
            ("run-a", "gap"): t0 + timedelta(seconds=2),
            ("run-a", "after"): t0 + timedelta(seconds=4.5),
        }
        fixes = {
            "scene-a": [
                route_fix("scene-a", "component_0001", -1, 0, source_record_id="a:0"),
                route_fix("scene-a", "component_0001", 0, 20, source_record_id="a:1"),
                route_fix("scene-a", "component_0002", 4, 0, source_record_id="a:2"),
                route_fix("scene-a", "component_0002", 5, 20, source_record_id="a:3"),
            ]
        }

        overlay = build_trajectory_window_overlay(windows, utc, fixes)

        self.assertEqual([row["position_status"] for row in overlay], ["POSITION_MATCHED", "POSITION_MISSING", "POSITION_MATCHED"])
        self.assertEqual(overlay[1]["missing_reason"], "WITHIN_ROUTE_DISCONTINUITY_GAP")
        self.assertEqual(overlay[0]["route_component_id"], "component_0001")
        self.assertEqual(overlay[2]["route_component_id"], "component_0002")

    def test_missing_utc_and_duplicate_window_identity_fail_or_remain_explicit(self):
        window = stage2_window("run-a", "1", "scene-a")
        missing_time = build_trajectory_window_overlay([window], {}, {})
        self.assertEqual(missing_time[0]["missing_reason"], "MISSING_STAGE0_UTC")

        with self.assertRaisesRegex(ValueError, "duplicate Stage2 window identity"):
            build_trajectory_window_overlay([window, dict(window)], {}, {})


class MainlineStage2RouteBinTests(unittest.TestCase):
    def test_fixed_distance_boundaries_and_ids_are_deterministic(self):
        fixes = [
            route_fix("scene-a", "component_0001", 0, 0),
            route_fix("scene-a", "component_0001", 1, 49.999),
            route_fix("scene-a", "component_0001", 2, 50),
            route_fix("scene-a", "component_0001", 3, 100),
        ]

        first = build_route_segment_rows([], fixes)
        second = build_route_segment_rows([], fixes)
        bins_50 = [row for row in first if row["bin_length_m"] == "50"]
        bins_100 = [row for row in first if row["bin_length_m"] == "100"]

        self.assertEqual([row["bin_index"] for row in bins_50], ["0", "1", "2"])
        self.assertEqual([row["bin_index"] for row in bins_100], ["0", "1"])
        self.assertEqual(first, second)
        self.assertEqual([row["route_segment_id"] for row in bins_50], [
            "scene-a__component_0001__L50__B000000",
            "scene-a__component_0001__L50__B000001",
            "scene-a__component_0001__L50__B000002",
        ])

    def test_component_boundaries_never_merge_equal_distance_bins(self):
        fixes = [
            route_fix("scene-a", "component_0001", 0, 0),
            route_fix("scene-a", "component_0002", 10, 0),
        ]

        bins = [row for row in build_route_segment_rows([], fixes, lengths_m=(100,))]

        self.assertEqual(len(bins), 2)
        self.assertEqual({row["component_id"] for row in bins}, {"component_0001", "component_0002"})
        self.assertEqual({row["bin_index"] for row in bins}, {"0"})

    def test_co_located_prns_are_retained_as_shared_descriptive_support(self):
        fixes = [route_fix("scene-a", "component_0001", 0, 25)]
        overlay = [
            {
                "run_id": "run-a",
                "window_id": "1",
                "scene_id": "scene-a",
                "prn": "G03",
                "position_status": "POSITION_MATCHED",
                "route_component_id": "component_0001",
                "route_cumulative_distance_m": "25",
                "position_source_record_id": "scene-a.nmea:000001",
            },
            {
                "run_id": "run-b",
                "window_id": "1",
                "scene_id": "scene-a",
                "prn": "G28",
                "position_status": "POSITION_MATCHED",
                "route_component_id": "component_0001",
                "route_cumulative_distance_m": "25",
                "position_source_record_id": "scene-a.nmea:000001",
            },
        ]

        bins = build_route_segment_rows(overlay, fixes, lengths_m=(50,))

        self.assertEqual(len(bins), 1)
        self.assertEqual(bins[0]["stage2_window_count"], "2")
        self.assertEqual(bins[0]["run_count"], "2")
        self.assertEqual(bins[0]["prn_count"], "2")
        self.assertEqual(bins[0]["co_located_cross_prn_fix_count"], "1")
        self.assertEqual(bins[0]["analysis_unit_role"], "DESCRIPTIVE_CANDIDATE_BIN_NOT_INDEPENDENT_SAMPLE")

    def test_sustained_speed_and_course_changes_are_annotations_not_new_components(self):
        fixes = []
        for bin_index in range(6):
            speed = 0.5 if bin_index < 3 else 10.0
            course = 2.0 if bin_index < 3 else 92.0
            for offset in (5, 15, 25):
                distance = bin_index * 50 + offset
                fixes.append(
                    route_fix(
                        "scene-a",
                        "component_0001",
                        distance,
                        distance,
                        speed_mps=speed,
                        course_deg=course,
                    )
                )

        rows = [row for row in build_route_segment_rows([], fixes, lengths_m=(50,))]

        candidate = next(row for row in rows if row["bin_index"] == "3")
        self.assertEqual(candidate["sustained_drive_state_change_candidate"], "YES")
        self.assertEqual(candidate["sustained_course_change_candidate"], "YES")
        self.assertTrue(all(row["component_id"] == "component_0001" for row in rows))

    def test_duplicate_overlay_identity_is_rejected(self):
        fix = route_fix("scene-a", "component_0001", 0, 0)
        window = {
            "run_id": "run-a",
            "window_id": "1",
            "scene_id": "scene-a",
            "prn": "G03",
            "position_status": "POSITION_MATCHED",
            "route_component_id": "component_0001",
            "route_cumulative_distance_m": "0",
        }
        with self.assertRaisesRegex(ValueError, "duplicate trajectory window identity"):
            build_route_segment_rows([window, dict(window)], [fix], lengths_m=(50,))


class MainlineStage2SpatialAggregationTests(unittest.TestCase):
    def test_aggregates_only_selected_windows_and_collapses_windows_at_one_fix(self):
        overlay = [
            {
                "run_id": "run-a", "window_id": "1", "scene_id": "scene-a", "prn": "G03",
                "tracking_channel": "2",
                "position_status": "POSITION_MATCHED", "position_utc": "2024-04-23T12:00:00.000Z",
                "position_source_record_id": "scene-a.nmea:1", "route_component_id": "component_0001",
                "route_cumulative_distance_m": "5",
            },
            {
                "run_id": "run-a", "window_id": "2", "scene_id": "scene-a", "prn": "G03",
                "tracking_channel": "2",
                "position_status": "POSITION_MATCHED", "position_utc": "2024-04-23T12:00:00.000Z",
                "position_source_record_id": "scene-a.nmea:1", "route_component_id": "component_0001",
                "route_cumulative_distance_m": "5",
            },
            {
                "run_id": "run-a", "window_id": "3", "scene_id": "scene-a", "prn": "G03",
                "tracking_channel": "2",
                "position_status": "POSITION_MISSING", "position_utc": "", "missing_reason": "OUTSIDE_POSITION_TOLERANCE",
            },
        ]
        paths = [
            stage2_path("run-a", "1", "scene-a", "G03", "1", multipath=False),
            stage2_path("run-a", "1", "scene-a", "G03", "2", multipath=True,
                        excess_delay_chips="0.2", doppler_offset_hz="-40", relative_power_db="-3"),
            stage2_path("run-a", "2", "scene-a", "G03", "1", multipath=False),
            stage2_path("run-a", "3", "scene-a", "G03", "1", multipath=True,
                        excess_delay_chips="0.4", doppler_offset_hz="-20", relative_power_db="-6"),
        ]

        metrics = aggregate_stage2_metrics_by_fix(paths, overlay)

        located = next(row for row in metrics if row["fix_utc"])
        unlocated = next(row for row in metrics if not row["fix_utc"])
        self.assertEqual(located["window_count"], 2)
        self.assertEqual(located["stage2_path_row_count"], 3)
        self.assertEqual(located["mean_mpc_count_per_window"], 0.5)
        self.assertEqual(located["total_mpc_count_across_windows"], 1)
        self.assertEqual(located["direct_reference_path_count"], 2)
        self.assertAlmostEqual(located["median_excess_delay_chips"], 0.2)
        self.assertAlmostEqual(located["median_doppler_offset_hz"], -40.0)
        self.assertAlmostEqual(located["median_relative_power_db"], -3.0)
        self.assertEqual(unlocated["window_count"], 1)
        self.assertEqual(unlocated["mean_mpc_count_per_window"], 1.0)
        self.assertEqual(unlocated["location_status"], "POSITION_MISSING")

    def test_rejects_path_identity_or_direct_role_conflicts(self):
        overlay = [{
            "run_id": "run-a", "window_id": "1", "scene_id": "scene-a", "prn": "G03",
            "tracking_channel": "2",
            "position_status": "POSITION_MISSING", "position_utc": "",
        }]
        path = stage2_path("run-a", "1", "scene-a", "G03", "1", multipath=True)
        path["modeling_role"] = "DIRECT_REFERENCE"

        with self.assertRaisesRegex(ValueError, "modeling_role conflicts"):
            aggregate_stage2_metrics_by_fix([path], overlay)

        with self.assertRaisesRegex(ValueError, "no trajectory overlay identity"):
            aggregate_stage2_metrics_by_fix(
                [stage2_path("run-b", "1", "scene-a", "G03", "1", multipath=False)], overlay
            )

        with self.assertRaisesRegex(ValueError, "has no Stage2 path rows"):
            aggregate_stage2_metrics_by_fix([], overlay)

        wrong_channel = dict(overlay[0], tracking_channel="3")
        with self.assertRaisesRegex(ValueError, "channel conflicts"):
            aggregate_stage2_metrics_by_fix(
                [stage2_path("run-a", "1", "scene-a", "G03", "1", multipath=False)],
                [wrong_channel],
            )

    def test_same_fix_cross_prn_support_is_reported_separately(self):
        overlay = [
            {
                "run_id": "run-a", "window_id": "1", "scene_id": "scene-a", "prn": "G03",
                "tracking_channel": "2",
                "position_status": "POSITION_MATCHED", "position_utc": "2024-04-23T12:00:00.000Z",
                "position_source_record_id": "scene-a.nmea:1", "route_component_id": "component_0001",
                "route_cumulative_distance_m": "5",
            },
            {
                "run_id": "run-b", "window_id": "1", "scene_id": "scene-a", "prn": "G28",
                "tracking_channel": "2",
                "position_status": "POSITION_MATCHED", "position_utc": "2024-04-23T12:00:00.000Z",
                "position_source_record_id": "scene-a.nmea:1", "route_component_id": "component_0001",
                "route_cumulative_distance_m": "5",
            },
        ]
        paths = [
            stage2_path("run-a", "1", "scene-a", "G03", "1", multipath=False),
            stage2_path("run-b", "1", "scene-a", "G28", "1", multipath=False),
        ]
        metrics = aggregate_stage2_metrics_by_fix(paths, overlay)

        self.assertEqual(len(metrics), 2)
        summary = summarize_spatial_dependence(metrics, lag_edges_m=(0, 50, 100))
        self.assertTrue(all(row["cross_prn_colocated_group_count"] == 1 for row in summary))
        self.assertTrue(all(row["estimate_status"] == "INSUFFICIENT_SPATIAL_SUPPORT" for row in summary))

    def test_sparse_lag_bands_keep_zero_pair_rows_and_null_estimates(self):
        metrics = [
            {
                "scene_id": "scene-a", "run_id": "run-a", "prn": "G03", "location_status": "POSITION_MATCHED",
                "fix_utc": f"2024-04-23T12:00:0{i}.000Z", "route_component_id": "component_0001",
                "route_cumulative_distance_m": float(i), "position_source_record_id": f"fix:{i}",
                "mean_mpc_count_per_window": i, "median_excess_delay_chips": None,
                "median_doppler_offset_hz": None, "median_relative_power_db": None,
            }
            for i in range(2)
        ]

        summary = summarize_spatial_dependence(metrics, lag_edges_m=(0, 2, 10, 100))

        mpc = [row for row in summary if row["metric_name"] == "mean_mpc_count_per_window"]
        self.assertEqual(len(mpc), 3)
        self.assertEqual(mpc[-1]["pair_count"], 0)
        self.assertEqual(mpc[-1]["scene_count"], 0)
        self.assertTrue(all(row["correlation_range_candidate_m"] is None for row in mpc))
        self.assertTrue(all(row["effective_local_unit_count_candidate"] is None for row in mpc))

    def test_scene_block_stable_decay_can_yield_a_candidate_range(self):
        metrics = []
        for scene_number in range(10):
            scene = f"scene-{scene_number:02d}"
            for position in range(100):
                metrics.append(
                    {
                        "scene_id": scene,
                        "run_id": f"{scene}-run",
                        "prn": "G03",
                        "location_status": "POSITION_MATCHED",
                        "fix_utc": f"2024-04-23T12:{position // 60:02d}:{position % 60:02d}.000Z",
                        "route_component_id": "component_0001",
                        "route_cumulative_distance_m": float(position),
                        "position_source_record_id": f"{scene}:fix:{position}",
                        "mean_mpc_count_per_window": float(position),
                        "median_excess_delay_chips": None,
                        "median_doppler_offset_hz": None,
                        "median_relative_power_db": None,
                    }
                )

        summary = summarize_spatial_dependence(metrics, lag_edges_m=(0, 10, 20, 30, 40, 50, 60))

        mpc = [row for row in summary if row["metric_name"] == "mean_mpc_count_per_window"]
        self.assertTrue(all(row["estimate_status"] == "STABLE_SCENE_BLOCK_CANDIDATE" for row in mpc))
        self.assertTrue(all(row["correlation_range_candidate_m"] is not None for row in mpc))
        self.assertTrue(all(row["effective_local_unit_count_candidate"] is not None for row in mpc))
        self.assertTrue(all(row["scene_count"] == 10 for row in mpc))


if __name__ == "__main__":
    unittest.main()
