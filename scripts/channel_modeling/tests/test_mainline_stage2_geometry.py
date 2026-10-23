from __future__ import annotations

import unittest
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.preprocessing.satellite_geometry import ElevationRecord
from scripts.channel_modeling.mainline_stage2_geometry import (
    build_gsv_window_overlay,
    build_stage0_utc_index,
    build_stage2_window_index,
    parse_checksum_valid_gps_gsv_files,
    summarize_geometry_coverage,
)


def path_row(
    run_id: str,
    window_id: str,
    path_id: str,
    *,
    scene_id: str = "scene-a",
    prn: str = "G03",
    tracking_channel: str = "2",
    elevation_group: str = "MISSING",
    environment_class: str = "Urban",
) -> dict[str, str]:
    return {
        "run_id": run_id,
        "scene_id": scene_id,
        "prn": prn,
        "tracking_channel": tracking_channel,
        "elevation_group": elevation_group,
        "environment_class": environment_class,
        "window_id": window_id,
        "path_id": path_id,
    }


def elevation_record(
    second: float,
    *,
    prn: str = "G03",
    source: str = "track.nmea",
    elevation: float = 42.0,
    azimuth: float = 123.0,
    message_number: int = 1,
) -> ElevationRecord:
    return ElevationRecord(
        utc_time=datetime(2024, 4, 23, tzinfo=timezone.utc) + timedelta(seconds=second),
        prn=prn,
        elevation_deg=elevation,
        azimuth_deg=azimuth,
        snr_db_hz=40.0,
        elevation_group="Mid",
        gsv_total_messages=1,
        gsv_message_number=message_number,
        satellites_in_view=1,
        nmea_file=source,
        raw_gsv_sentence="$GPGSV,1,1,1,03,42,123,40*00",
    )


def checksummed(sentence_body: str) -> str:
    checksum = 0
    for character in sentence_body:
        checksum ^= ord(character)
    return f"${sentence_body}*{checksum:02X}"


class MainlineStage2GeometryIndexTests(unittest.TestCase):
    def test_window_index_collapses_paths_in_first_seen_order_and_scopes_ids_by_run(self):
        rows = [
            path_row("run-b", "10", "1", scene_id="scene-b"),
            path_row("run-a", "2", "1"),
            path_row("run-b", "10", "2", scene_id="scene-b"),
            path_row("run-a", "1", "1"),
            path_row("run-c", "10", "1", scene_id="scene-c"),
        ]

        windows = build_stage2_window_index(rows)

        self.assertEqual(
            [(row["run_id"], row["window_id"]) for row in windows],
            [("run-b", "10"), ("run-a", "2"), ("run-a", "1"), ("run-c", "10")],
        )
        self.assertEqual(windows[0]["scene_id"], "scene-b")
        self.assertEqual(windows[-1]["scene_id"], "scene-c")
        self.assertEqual(windows[1]["elevation_group"], "MISSING")
        self.assertEqual(windows[1]["environment_class"], "Urban")

    def test_window_index_rejects_noncanonical_window_and_path_ids(self):
        for field, value in (
            ("window_id", "0"),
            ("window_id", "01"),
            ("window_id", "1.0"),
            ("window_id", "-1"),
            ("path_id", "0"),
            ("path_id", "02"),
        ):
            row = path_row("run-a", "1", "1")
            row[field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, field):
                build_stage2_window_index([row])

    def test_window_index_rejects_duplicate_path_identity(self):
        row = path_row("run-a", "4", "2")

        with self.assertRaisesRegex(ValueError, "duplicate.*path"):
            build_stage2_window_index([row, dict(row)])

    def test_window_index_rejects_conflicting_scene_prn_or_channel_within_window(self):
        base = path_row("run-a", "4", "1")
        for changed in (
            dict(base, path_id="2", scene_id="scene-b"),
            dict(base, path_id="2", prn="G04"),
            dict(base, path_id="2", tracking_channel="3"),
        ):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "conflict"):
                build_stage2_window_index([base, changed])

    def test_window_index_rejects_a_run_assigned_to_multiple_scenes(self):
        with self.assertRaisesRegex(ValueError, "run_id.*scene"):
            build_stage2_window_index(
                [
                    path_row("run-a", "1", "1", scene_id="scene-a"),
                    path_row("run-a", "2", "1", scene_id="scene-b"),
                ]
            )

    def test_utc_index_handles_utc_midnight_and_gps_week_rollover(self):
        runs = [{"run_id": "midnight", "scene_id": "scene-a"}, {"run_id": "rollover", "scene_id": "scene-b"}]
        stage0 = {
            "midnight": [
                {"window_id": "1", "tow_s": "17.9", "recording_time_s": "0"},
                {"window_id": "2", "tow_s": "18.1", "recording_time_s": "0.2"},
            ],
            "rollover": [
                {"window_id": "1", "tow_s": "604799.5", "recording_time_s": "0"},
                {"window_id": "2", "tow_s": "0.5", "recording_time_s": "1"},
            ],
        }

        index = build_stage0_utc_index(runs, stage0, {"scene-a": 2048, "scene-b": 2047})

        self.assertEqual(
            index[("midnight", "1")],
            datetime(2019, 4, 6, 23, 59, 59, 900000, tzinfo=timezone.utc),
        )
        self.assertEqual(
            index[("midnight", "2")],
            datetime(2019, 4, 7, 0, 0, 0, 100000, tzinfo=timezone.utc),
        )
        self.assertEqual(
            index[("rollover", "1")],
            datetime(2019, 4, 6, 23, 59, 41, 500000, tzinfo=timezone.utc),
        )
        self.assertEqual(
            index[("rollover", "2")],
            datetime(2019, 4, 6, 23, 59, 42, 500000, tzinfo=timezone.utc),
        )

    def test_utc_index_rejects_missing_stage0_run_rows_and_duplicate_windows(self):
        run = [{"run_id": "run-a", "scene_id": "scene-a"}]
        with self.assertRaisesRegex(ValueError, "Stage0.*run-a"):
            build_stage0_utc_index(run, {}, {"scene-a": 2048})

        duplicate = [
            {"window_id": "1", "tow_s": "10", "recording_time_s": "0"},
            {"window_id": "1", "tow_s": "11", "recording_time_s": "1"},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate.*window_id"):
            build_stage0_utc_index(run, {"run-a": duplicate}, {"scene-a": 2048})

    def test_utc_index_rejects_invalid_tow_or_recording_time(self):
        run = [{"run_id": "run-a", "scene_id": "scene-a"}]
        for field, value in (
            ("tow_s", "-0.1"),
            ("tow_s", "604800"),
            ("tow_s", "NaN"),
            ("recording_time_s", "-1"),
            ("recording_time_s", "inf"),
        ):
            row = {"window_id": "1", "tow_s": "1", "recording_time_s": "0"}
            row[field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, field):
                build_stage0_utc_index(run, {"run-a": [row]}, {"scene-a": 2048})

    def test_utc_index_rejects_noncanonical_ids_and_missing_fields(self):
        run = [{"run_id": "run-a", "scene_id": "scene-a"}]
        for row, expected in (
            ({"window_id": "01", "tow_s": "1", "recording_time_s": "0"}, "window_id"),
            ({"window_id": "1", "tow_s": "1"}, "recording_time_s"),
        ):
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, expected):
                build_stage0_utc_index(run, {"run-a": [row]}, {"scene-a": 2048})


class MainlineStage2GeometryOverlayTests(unittest.TestCase):
    def test_only_checksum_valid_gsv_records_enter_the_overlay_input(self):
        valid_rmc = checksummed(
            "GPRMC,120000.00,A,4807.038,N,01131.000,E,0.0,0.0,230424,,,A"
        )
        valid_gsv = checksummed("GPGSV,1,1,1,03,45,120,40")
        bad_body = "GPGSV,1,1,1,04,20,100,30"
        bad_checksum = int(checksummed(bad_body).rsplit("*", 1)[1], 16) ^ 1
        invalid_gsv = f"${bad_body}*{bad_checksum:02X}"
        unchecked_gsv = "$GPGSV,1,1,1,05,35,110,35"
        other_constellation = checksummed("GLGSV,1,1,1,03,15,210,20")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "scene.nmea"
            path.write_text(
                "\n".join(
                    (valid_rmc, valid_gsv, invalid_gsv, unchecked_gsv, other_constellation)
                ) + "\n",
                encoding="ascii",
            )

            records, counts, diagnostics = parse_checksum_valid_gps_gsv_files(
                [path], source_root=root
            )

        self.assertEqual([record.prn for record in records], ["G03"])
        self.assertEqual(records[0].elevation_deg, 45.0)
        self.assertEqual(diagnostics["bad_checksum_count"], 1)
        self.assertEqual(diagnostics["missing_checksum_count"], 1)
        self.assertEqual(diagnostics["checksum_valid_count"], 3)
        self.assertEqual(diagnostics["ignored_non_gps_gsv_count"], 1)
        self.assertEqual(diagnostics["gps_gsv_untimestamped_count"], 0)
        self.assertEqual(counts["G03"], 1)

    def test_overlay_matches_only_same_scene_and_prn_and_preserves_all_windows(self):
        target = datetime(2024, 4, 23, tzinfo=timezone.utc)
        windows = [
            path_row("run-a", "1", "1", scene_id="scene-a", prn="G03"),
            path_row("run-b", "1", "1", scene_id="scene-b", prn="G03"),
            path_row("run-a", "2", "1", scene_id="scene-a", prn="G04"),
        ]
        rows = build_gsv_window_overlay(
            windows,
            {("run-a", "1"): target, ("run-b", "1"): target, ("run-a", "2"): target},
            {
                ("scene-a", "G03"): [elevation_record(0, source="a.nmea")],
                ("scene-b", "G03"): [elevation_record(0, source="b.nmea")],
            },
        )

        self.assertEqual(
            [(row["run_id"], row["window_id"]) for row in rows],
            [("run-a", "1"), ("run-b", "1"), ("run-a", "2")],
        )
        self.assertEqual(
            [row["status"] for row in rows],
            ["GSV_MATCHED", "GSV_MATCHED", "MISSING"],
        )
        self.assertEqual(rows[0]["source_file"], "a.nmea")
        self.assertEqual(rows[1]["source_file"], "b.nmea")
        self.assertEqual(rows[2]["missing_reason"], "NO_TARGET_PRN_GSV")
        self.assertEqual(rows[0]["frozen_elevation_group"], "MISSING")
        self.assertNotIn("raw_gsv_sentence", rows[0])

    def test_overlay_nearest_tie_is_deterministic_and_retains_candidate_delta(self):
        origin = datetime(2024, 4, 23, tzinfo=timezone.utc)
        row = path_row("run-a", "1", "1", elevation_group="Low")
        records = [
            elevation_record(2, source="z.nmea", elevation=10, message_number=1),
            elevation_record(0, source="a.nmea", elevation=20, message_number=2),
        ]

        overlay = build_gsv_window_overlay(
            [row], {("run-a", "1"): origin + timedelta(seconds=1)},
            {("scene-a", "G03"): records},
        )

        self.assertEqual(overlay[0]["source_file"], "a.nmea")
        self.assertEqual(overlay[0]["nearest_candidate_utc"], "2024-04-23T00:00:00.000Z")
        self.assertEqual(overlay[0]["candidate_delta_seconds_signed"], "-1")
        self.assertEqual(overlay[0]["candidate_delta_seconds_abs"], "1")
        self.assertEqual(overlay[0]["elevation_deg"], "20")

    def test_overlay_caps_endpoint_extension_and_does_not_bridge_gsv_gaps(self):
        origin = datetime(2024, 4, 23, tzinfo=timezone.utc)
        windows = [path_row("run-a", "1", "1"), path_row("run-a", "2", "1")]
        overlay = build_gsv_window_overlay(
            windows,
            {
                ("run-a", "1"): origin - timedelta(seconds=0.5),
                ("run-a", "2"): origin - timedelta(seconds=0.6),
            },
            {("scene-a", "G03"): [elevation_record(0), elevation_record(1)]},
        )
        self.assertEqual(overlay[0]["status"], "GSV_MATCHED")
        self.assertEqual(overlay[0]["local_cadence_limit_seconds"], "0.5")
        self.assertEqual(overlay[1]["status"], "MISSING")

        gap_records = [
            elevation_record(0), elevation_record(1),
            elevation_record(20), elevation_record(21),
        ]
        gap_overlay = build_gsv_window_overlay(
            [path_row("run-gap", "1", "1")],
            {("run-gap", "1"): origin + timedelta(seconds=10)},
            {("scene-a", "G03"): gap_records},
        )
        self.assertEqual(gap_overlay[0]["status"], "MISSING")
        self.assertEqual(gap_overlay[0]["missing_reason"], "GSV_GAP_OR_CADENCE_LIMIT")

    def test_overlay_marks_missing_time_anchor_and_rejects_duplicate_window_identity(self):
        row = path_row("run-a", "1", "1")
        missing_time = build_gsv_window_overlay(
            [row], {}, {("scene-a", "G03"): [elevation_record(0)]}
        )
        self.assertEqual(missing_time[0]["missing_reason"], "INVALID_TIME_ANCHOR")
        with self.assertRaisesRegex(ValueError, "duplicate.*window"):
            build_gsv_window_overlay([row, dict(row)], {}, {})

    def test_coverage_reports_tolerance_sensitivity_and_one_task_source_row(self):
        origin = datetime(2024, 4, 23, tzinfo=timezone.utc)
        windows = [path_row("run-a", "1", "1"), path_row("run-a", "2", "1")]
        overlay = build_gsv_window_overlay(
            windows,
            {
                ("run-a", "1"): origin + timedelta(seconds=1),
                ("run-a", "2"): origin + timedelta(seconds=1.5),
            },
            {("scene-a", "G03"): [elevation_record(0), elevation_record(4), elevation_record(8)]},
        )
        task = {
            "run_id": "run-a",
            "scene_id": "scene-a",
            "environment_class": "Urban",
            "prn": "G03",
            "nmea_available": "YES",
            "nmea_file_count": "1",
            "rmc_valid_count": "1",
            "gsv_valid_count": "3",
            "target_prn_in_rinex": "YES",
            "gps_time_alignment_status": "VERIFIED",
            "target_prn_gsv_record_count": "3",
        }

        summary = summarize_geometry_coverage(overlay, [task])

        total = next(row for row in summary if row["summary_scope"] == "TOTAL")
        task_rows = [row for row in summary if row["summary_scope"] == "TASK_SOURCE"]
        self.assertEqual(total["window_count"], "2")
        self.assertEqual(total["matched_within_0_5s"], "0")
        self.assertEqual(total["matched_within_1s"], "1")
        self.assertEqual(total["matched_within_2s"], "2")
        self.assertEqual(total["matched_within_5s"], "2")
        self.assertEqual(len(task_rows), 1)
        self.assertEqual(task_rows[0]["target_prn_in_rinex"], "YES")
        self.assertEqual(task_rows[0]["gsv_matched_count"], "2")

    def test_coverage_rejects_duplicate_overlay_or_task_identities(self):
        overlay = [{"run_id": "run-a", "window_id": "1", "status": "MISSING"}]
        with self.assertRaisesRegex(ValueError, "duplicate.*window"):
            summarize_geometry_coverage([*overlay, dict(overlay[0])], [])
        task = {"run_id": "run-a", "scene_id": "scene-a", "prn": "G03"}
        with self.assertRaisesRegex(ValueError, "duplicate.*run_id"):
            summarize_geometry_coverage([], [task, dict(task)])


if __name__ == "__main__":
    unittest.main()
