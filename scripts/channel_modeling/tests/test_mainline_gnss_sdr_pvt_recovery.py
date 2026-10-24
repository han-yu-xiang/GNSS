from __future__ import annotations

import struct
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import scripts.channel_modeling.run_mainline_gnss_sdr_pvt_recovery as pvt_runner

from scripts.channel_modeling.mainline_gnss_sdr_pvt_recovery import (
    PVT_RECORD,
    build_pvt_position_overlay,
    parse_pvt_dump,
)


def pvt_record(
    *,
    tow_ms: int = 299_868_020,
    week: int = 2402,
    latitude: float = 51.4,
    longitude: float = 9.8,
    height: float = 100.0,
    valid_satellites: int = 6,
    status: int = 5,
    solution_type: int = 0,
    pdop: float = 2.0,
    rx_time_offset_s: float = 0.0,
) -> bytes:
    doubles = (
        tow_ms / 1000.0 + rx_time_offset_s,
        0.0,
        3_900_000.0,
        700_000.0,
        5_000_000.0,
        0.0,
        0.0,
        0.0,
        1.0,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        latitude,
        longitude,
        height,
    )
    return PVT_RECORD.pack(
        tow_ms,
        week,
        *doubles,
        valid_satellites,
        status,
        solution_type,
        0.0,
        0.0,
        1.5,
        pdop,
        1.2,
        1.0,
    )


def geometry_row(window_id: str, window_utc: str) -> dict[str, str]:
    return {
        "run_id": "run-a",
        "window_id": window_id,
        "scene_id": "scene-a",
        "prn": "G03",
        "tracking_channel": "2",
        "window_utc": window_utc,
    }


def trajectory_row(window_id: str, window_utc: str, *, matched: bool) -> dict[str, str]:
    return {
        "run_id": "run-a",
        "window_id": window_id,
        "scene_id": "scene-a",
        "prn": "G03",
        "tracking_channel": "2",
        "window_utc": window_utc,
        "position_utc": "2026-01-21T11:17:30.020Z" if matched else "",
        "position_delta_seconds": "0" if matched else "",
        "position_source_path": "scenes/scene-a/trajectory/route.nmea" if matched else "",
        "position_source_record_id": "route.nmea:1" if matched else "",
        "latitude_deg": "51.4" if matched else "",
        "longitude_deg": "9.8" if matched else "",
        "position_status": "POSITION_MATCHED" if matched else "POSITION_MISSING",
        "missing_reason": "" if matched else "OUTSIDE_OBSERVED_ROUTE_COVERAGE",
    }


class MainlineGnssSdrPvtDumpTests(unittest.TestCase):
    def test_parses_gnss_sdr_binary_record_and_converts_gps_time_to_utc(self):
        rows = parse_pvt_dump(pvt_record())

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.record_index, 1)
        self.assertEqual(row.solution_status, 5)
        self.assertEqual(row.solution_type, 0)
        self.assertEqual(row.valid_satellites, 6)
        self.assertEqual(row.position_utc, datetime(2026, 1, 21, 11, 17, 30, 20_000, tzinfo=timezone.utc))
        self.assertTrue(row.is_valid_single_point)

    def test_uses_observable_rx_time_not_per_channel_decoded_tow(self):
        row = parse_pvt_dump(pvt_record(rx_time_offset_s=0.08))[0]

        self.assertTrue(row.is_valid_single_point)
        self.assertEqual(row.position_utc, datetime(2026, 1, 21, 11, 17, 30, 100_000, tzinfo=timezone.utc))
        self.assertAlmostEqual(row.rx_time_s - row.tow_ms / 1000.0, 0.08)

    def test_rejects_truncated_or_misaligned_dump(self):
        with self.assertRaisesRegex(ValueError, "record boundary"):
            parse_pvt_dump(pvt_record() + b"x")

    def test_only_accepts_single_point_xyz_with_four_valid_satellites(self):
        rows = parse_pvt_dump(
            pvt_record(status=0)
            + pvt_record(tow_ms=299_868_040, solution_type=1)
            + pvt_record(tow_ms=299_868_060, valid_satellites=3)
            + pvt_record(tow_ms=299_868_080)
        )

        self.assertEqual([row.is_valid_single_point for row in rows], [False, False, False, True])


class MainlineGnssSdrPvtOverlayTests(unittest.TestCase):
    def test_coordinate_output_is_restricted_to_ignored_runtime_namespace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "ignored runtime namespace"):
                pvt_runner.build_outputs(
                    root,
                    root / "missing_geometry.csv",
                    root / "missing_trajectory.csv",
                    root / "reports" / "coordinates",
                )

            self.assertFalse((root / "reports").exists())
            with self.assertRaises(FileNotFoundError):
                pvt_runner.build_outputs(
                    root,
                    root / "missing_geometry.csv",
                    root / "missing_trajectory.csv",
                    root / "dataset_generation_logs" / "channel_modeling" / "run-a",
                )
            with self.assertRaisesRegex(ValueError, "top-level run directory"):
                pvt_runner.build_outputs(
                    root,
                    root / "missing_geometry.csv",
                    root / "missing_trajectory.csv",
                    root / "dataset_generation_logs" / "channel_modeling" / "old-run" / "new-child",
                )

    def test_fills_only_missing_positions_at_direct_epoch_and_preserves_existing_nmea(self):
        time = "2026-01-21T11:17:30.100Z"
        geometry = [geometry_row("1", time), geometry_row("2", time)]
        trajectory = [
            trajectory_row("1", time, matched=False),
            trajectory_row("2", time, matched=True),
        ]

        merged, overlay = build_pvt_position_overlay(
            geometry,
            trajectory,
            {"scene-a": parse_pvt_dump(pvt_record(rx_time_offset_s=0.08))},
            pvt_source_by_scene={"scene-a": "scenes/scene-a/gnss_sdr/pvt/scene-a_pvt.dat"},
            max_position_delta_seconds=0.5,
        )
        by_key = {(row["run_id"], row["window_id"]): row for row in merged}
        overlay_by_key = {(row["run_id"], row["window_id"]): row for row in overlay}

        self.assertEqual(by_key[("run-a", "1")]["position_status"], "POSITION_MATCHED")
        self.assertEqual(by_key[("run-a", "1")]["position_source"], "GNSS_SDR_PVT_SINGLE")
        self.assertEqual(by_key[("run-a", "2")]["position_source_path"], "scenes/scene-a/trajectory/route.nmea")
        self.assertEqual(by_key[("run-a", "2")]["position_source"], "EXISTING_NMEA")
        self.assertEqual(overlay_by_key[("run-a", "1")]["pvt_solution_status"], "5")
        self.assertEqual(overlay_by_key[("run-a", "1")]["position_source"], "GNSS_SDR_PVT_SINGLE")
        self.assertEqual(overlay_by_key[("run-a", "1")]["pvt_rx_tow_delta_seconds"], "0.080000")
        self.assertEqual(by_key[("run-a", "1")]["position_delta_seconds"], "0.000000")

    def test_does_not_interpolate_or_use_an_invalid_or_ambiguous_solution(self):
        target = "2026-01-21T11:17:30.520Z"
        geom = [geometry_row("1", target), geometry_row("2", target)]
        traj = [trajectory_row("1", target, matched=False), trajectory_row("2", target, matched=False)]
        first = parse_pvt_dump(pvt_record())[0]
        invalid = parse_pvt_dump(pvt_record(tow_ms=299_868_040, status=0))[0]
        conflicting = parse_pvt_dump(pvt_record(tow_ms=299_868_040, latitude=51.5))[0]
        conflicting_again = parse_pvt_dump(pvt_record(tow_ms=299_868_040, latitude=51.6))[0]

        merged, overlay = build_pvt_position_overlay(
            geom,
            traj,
            {"scene-a": [first, invalid, conflicting, conflicting_again]},
            pvt_source_by_scene={"scene-a": "scenes/scene-a/gnss_sdr/pvt/scene-a_pvt.dat"},
            max_position_delta_seconds=0.5,
        )

        self.assertEqual([row["position_status"] for row in merged], ["POSITION_MISSING", "POSITION_MISSING"])
        self.assertEqual(
            overlay[0]["position_recovery_status"],
            "AMBIGUOUS_PVT_SOLUTIONS_AT_EPOCH",
        )

    def test_requires_exact_unique_scene_window_identity(self):
        time = "2026-01-21T11:17:30.020Z"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_pvt_position_overlay(
                [geometry_row("1", time), geometry_row("1", time)],
                [trajectory_row("1", time, matched=False)],
                {"scene-a": parse_pvt_dump(pvt_record())},
                pvt_source_by_scene={"scene-a": "scenes/scene-a/gnss_sdr/pvt/scene-a_pvt.dat"},
            )


if __name__ == "__main__":
    unittest.main()
