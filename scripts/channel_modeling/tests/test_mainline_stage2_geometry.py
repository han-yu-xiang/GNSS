from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
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
from scripts.channel_modeling.run_mainline_stage2_geometry_audit import (
    MAX_TIME_ORIGIN_RESIDUAL_SECONDS,
    REPO_ROOT,
    _timestamp_origin_audit,
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

    def test_window_index_accepts_canonical_zero_tracking_channel(self):
        row = path_row("run-a", "1", "1")
        row["tracking_channel"] = "0"

        indexed = build_stage2_window_index([row])

        self.assertEqual(indexed[0]["tracking_channel"], "0")

    def test_window_index_rejects_noncanonical_tracking_channel(self):
        for value in ("00", "-1", "1.0"):
            row = path_row("run-a", "1", "1")
            row["tracking_channel"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "tracking_channel"):
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
        self.assertEqual(diagnostics["first_valid_rmc_utc"], "2024-04-23T12:00:00.000Z")
        self.assertEqual(counts["G03"], 1)

    def test_conflicting_duplicate_gsv_epoch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "conflict.nmea"
            path.write_text(
                "\n".join(
                    (
                        checksummed("GPRMC,120000.00,A,4807.038,N,01131.000,E,0.0,0.0,230424,,,A"),
                        checksummed("GPGSV,1,1,1,03,10,120,40"),
                        checksummed("GPGSV,1,1,1,03,80,120,40"),
                    )
                ) + "\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "conflicting duplicate.*GSV"):
                parse_checksum_valid_gps_gsv_files([path], source_root=root)

    def test_identical_duplicate_gsv_epoch_chooses_source_deterministically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("z_track.nmea", "a_track.nmea"):
                (root / name).write_text(
                    "\n".join(
                        (
                            checksummed("GPRMC,120000.00,A,4807.038,N,01131.000,E,0.0,0.0,230424,,,A"),
                            checksummed("GPGSV,1,1,1,03,45,120,40"),
                        )
                    ) + "\n",
                    encoding="ascii",
                )
            first, _, _ = parse_checksum_valid_gps_gsv_files(
                [root / "z_track.nmea", root / "a_track.nmea"], source_root=root
            )
            second, _, _ = parse_checksum_valid_gps_gsv_files(
                [root / "a_track.nmea", root / "z_track.nmea"], source_root=root
            )
        self.assertEqual(first[0].nmea_file, "a_track.nmea")
        self.assertEqual(second[0].nmea_file, "a_track.nmea")

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
            [path_row("run-gap", "1", "1"), path_row("run-gap", "2", "1")],
            {
                ("run-gap", "1"): origin + timedelta(seconds=1.25),
                ("run-gap", "2"): origin + timedelta(seconds=19.75),
            },
            {("scene-a", "G03"): gap_records},
        )
        self.assertTrue(all(row["status"] == "MISSING" for row in gap_overlay))
        self.assertTrue(all(row["missing_reason"] == "GSV_GAP_OR_CADENCE_LIMIT" for row in gap_overlay))


class MainlineStage2TimeOriginAuditTests(unittest.TestCase):
    def test_time_origin_residual_over_limit_fails_closed(self):
        scene_tasks = {"scene-a": [{"run_id": "run-a"}]}
        stage0 = {
            "run-a": [
                {"window_id": "1", "recording_time_s": "0"},
                {"window_id": "2", "recording_time_s": "1"},
            ]
        }
        t0 = datetime(2024, 4, 23, tzinfo=timezone.utc)
        utc = {
            ("run-a", "1"): t0,
            ("run-a", "2"): t0 + timedelta(seconds=19),
        }
        with self.assertRaisesRegex(ValueError, "time-origin residual.*scene-a"):
            _timestamp_origin_audit(scene_tasks, stage0, utc)

    def test_measured_subsecond_origin_residual_is_verified(self):
        scene_tasks = {"scene-a": [{"run_id": "run-a"}]}
        stage0 = {
            "run-a": [
                {"window_id": "1", "recording_time_s": "0"},
                {"window_id": "2", "recording_time_s": "1"},
            ]
        }
        t0 = datetime(2024, 4, 23, tzinfo=timezone.utc)
        utc = {
            ("run-a", "1"): t0,
            ("run-a", "2"): t0 + timedelta(seconds=1.02304),
        }
        audit = _timestamp_origin_audit(scene_tasks, stage0, utc)
        self.assertEqual(audit["scene-a"]["gps_time_alignment_status"], "VERIFIED")
        self.assertLessEqual(
            audit["scene-a"]["max_time_origin_residual_seconds"],
            MAX_TIME_ORIGIN_RESIDUAL_SECONDS,
        )

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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _initialize_ignored_test_project(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "init", "--quiet"], check=True)
    (root / ".gitignore").write_text("dataset_generation_logs/\n", encoding="utf-8")


class MainlineStage2GeometryAuditCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        _initialize_ignored_test_project(self.root)
        self.code_root = Path(__file__).resolve().parents[3]
        self.output = self.root / "dataset_generation_logs/channel_modeling/mainline_1023_geometry_route_20261024T000000Z"
        self.script = Path(__file__).resolve().parents[1] / "run_mainline_stage2_geometry_audit.py"
        self._build_fixture()

    def _build_fixture(self):
        from scripts.event_database.align_modeling_context import (
            GPS_EPOCH,
            GPS_UTC_LEAP_SECONDS,
            GPS_WEEK_SECONDS,
        )

        scene = "scene-a"
        run_id = "run-a"
        task_root = self.root / "scenes/scene-a/sage"
        stage0 = task_root / "stage0.csv"
        stage0.parent.mkdir(parents=True)
        anchor = datetime(2024, 4, 23, 12, 0, 0, tzinfo=timezone.utc)
        gps_seconds = (anchor - GPS_EPOCH).total_seconds() + GPS_UTC_LEAP_SECONDS
        gps_week = int(gps_seconds // GPS_WEEK_SECONDS)
        tow_s = gps_seconds - gps_week * GPS_WEEK_SECONDS
        _write_csv(
            stage0,
            ["window_id", "tow_s", "recording_time_s"],
            [{"window_id": "1", "tow_s": f"{tow_s:.3f}", "recording_time_s": "0"}],
        )
        stage2_source = task_root / "stage2.csv"
        stage2_source.write_text("frozen stage2 source fixture\n", encoding="ascii")

        cohort_path = self.root / "dataset_generation_logs/channel_modeling/mainline_1023_cohort_v1_20261022T082520Z/cohort.json"
        cohort_path.parent.mkdir(parents=True)
        manifest_path = self.root / "reports/data_consolidation_20261003/manifest.csv"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text("fixture manifest\n", encoding="ascii")
        code_pin_path = self.code_root / "scripts/channel_modeling/freeze_mainline_1023_cohort.py"

        ledger_path = self.root / "dataset_generation_logs/channel_modeling/mainline_1023_model_v1_20261023T135341Z/stage2_ledger.csv"
        _write_csv(
            ledger_path,
            [
                "run_id", "scene_id", "prn", "tracking_channel", "environment_class",
                "elevation_group", "window_id", "path_id", "source_stage2_csv_sha256",
            ],
            [
                {
                    "run_id": run_id,
                    "scene_id": scene,
                    "prn": "G03",
                    "tracking_channel": "2",
                    "environment_class": "Urban",
                    "elevation_group": "MISSING",
                    "window_id": "1",
                    "path_id": str(path_id),
                    "source_stage2_csv_sha256": _sha256(stage2_source),
                }
                for path_id in (1, 2)
            ],
        )

        nmea = self.root / "scenes/scene-a/trajectory/scene-a_trajectory.nmea"
        nmea.parent.mkdir(parents=True)
        nmea.write_text(
            "\n".join(
                (
                    checksummed("GPRMC,120000.00,A,4807.038,N,01131.000,E,0.0,0.0,230424,,,A"),
                    checksummed("GPGSV,1,1,1,03,42,123,40"),
                )
            )
            + "\n",
            encoding="ascii",
        )
        rinex = self.root / "scenes/scene-a/navigation/RINEXFILE.26N"
        rinex.parent.mkdir(parents=True)
        rinex.write_text(
            "     3.04           NAVIGATION DATA     GPS                 RINEX VERSION / TYPE\n"
            "                                                            END OF HEADER\n"
            "G03 2024 04 23 00 00 00.0\n",
            encoding="ascii",
        )
        run_index = self.root / "dataset/multipath_event_database/v1/partitions/ingestion_id=ingestion_20260825_event_path_v1/facts/sage_runs.csv"
        _write_csv(
            run_index,
            [
                "run_id", "scene_id", "prn", "tracking_channel", "trajectory_relpath",
                "rinex_nav_relpath", "context_missing_legacy",
            ],
            [
                {
                    "run_id": "indexed-other-prn",
                    "scene_id": scene,
                    "prn": "G25",
                    "tracking_channel": "5",
                    "trajectory_relpath": "scenes/scene-a/trajectory/scene-a_trajectory.nmea",
                    "rinex_nav_relpath": "scenes/scene-a/navigation/RINEXFILE.26N",
                    "context_missing_legacy": "0",
                },
            ],
        )

        cohort_path.write_text(
            json.dumps(
                {
                    "cohort_id": "synthetic_geometry_fixture",
                    "eligible_count": 1,
                    "tasks": [
                        {
                            "run_id": run_id,
                            "scene_id": scene,
                            "prn": "G03",
                            "tracking_channel": 2,
                            "environment_class": "Urban",
                            "elevation_group": "MISSING",
                            "stage_counts_from_gate_a": {
                                "stage0_valid_40ms_windows": 1,
                                "stage2_selected_path_count": 2,
                            },
                            "stage_csvs": {
                                "stage0_valid_windows": {
                                    "path": stage0.relative_to(self.root).as_posix(),
                                    "sha256": _sha256(stage0),
                                    "size_bytes": stage0.stat().st_size,
                                },
                                "stage2_selected_paths": {
                                    "path": stage2_source.relative_to(self.root).as_posix(),
                                    "sha256": _sha256(stage2_source),
                                    "size_bytes": stage2_source.stat().st_size,
                                },
                            },
                        }
                    ],
                    "source_sha256": {
                        "manifest": {
                            "path": manifest_path.relative_to(self.root).as_posix(),
                            "sha256": _sha256(manifest_path),
                        },
                        "cohort_generator": {
                            "path": "scripts/channel_modeling/freeze_mainline_1023_cohort.py",
                            "sha256": _sha256(code_pin_path),
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

    def _run(self):
        return subprocess.run(
            [
                sys.executable,
                str(self.script),
                "--project-root",
                str(self.root),
                "--code-root",
                str(self.code_root),
                "--output-dir",
                str(self.output),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_missing_required_input_fails_without_creating_output_namespace(self):
        (self.root / "scenes/scene-a/navigation/RINEXFILE.26N").unlink()

        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

    def test_output_must_use_timestamped_private_namespace_and_be_git_ignored(self):
        self.output = self.root / "docs/review-output"
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timestamped mainline_1023_geometry_route", result.stderr)
        self.assertFalse(self.output.exists())

        self.output = self.root / "dataset_generation_logs/channel_modeling/mainline_1023_geometry_route_20261024T000000Z"
        (self.root / ".gitignore").write_text("reports/\n", encoding="utf-8")
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not ignored by Git", result.stderr)
        self.assertFalse(self.output.exists())

    def test_code_root_must_be_the_executing_worktree(self):
        self.code_root = self.root
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code_root must match", result.stderr)
        self.assertFalse(self.output.exists())

    def test_noncanonical_channel_value_fails_closed_before_output(self):
        cohort_path = self.root / "dataset_generation_logs/channel_modeling/mainline_1023_cohort_v1_20261022T082520Z/cohort.json"
        cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
        cohort["tasks"][0]["tracking_channel"] = 2.5
        cohort_path.write_text(json.dumps(cohort), encoding="utf-8")

        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tracking_channel", result.stderr)
        self.assertFalse(self.output.exists())

    def test_existing_output_namespace_is_refused_and_preserved(self):
        self.output.mkdir(parents=True)
        sentinel = self.output / "preserve.txt"
        sentinel.write_text("preserve", encoding="ascii")

        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(sentinel.read_text(encoding="ascii"), "preserve")

    def test_conflicting_scene_source_paths_fail_closed_before_output(self):
        index_path = self.root / "dataset/multipath_event_database/v1/partitions/ingestion_id=ingestion_20260825_event_path_v1/facts/sage_runs.csv"
        with index_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        alternate = self.root / "scenes/scene-a/trajectory/alternate.nmea"
        alternate.write_text("", encoding="ascii")
        rows.append(
            {
                "run_id": "indexed-conflict",
                "scene_id": "scene-a",
                "prn": "G28",
                "tracking_channel": "6",
                "trajectory_relpath": "scenes/scene-a/trajectory/alternate.nmea",
                "rinex_nav_relpath": "scenes/scene-a/navigation/RINEXFILE.26N",
                "context_missing_legacy": "0",
            }
        )
        _write_csv(index_path, list(rows[0]), rows)

        result = self._run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("one scene-level NMEA/RINEX source pair", result.stderr)
        self.assertFalse(self.output.exists())

    def test_schema_reconciles_all_stage2_windows_without_coordinates_or_raw_nmea(self):
        result = self._run()

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        overlay_path = self.output / "geometry_window_overlay.csv"
        summary_path = self.output / "geometry_coverage_summary.csv"
        audit_path = self.output / "geometry_alignment_audit.json"
        with overlay_path.open(newline="", encoding="utf-8") as handle:
            overlay_reader = csv.DictReader(handle)
            overlay = list(overlay_reader)
            self.assertEqual(
                overlay_reader.fieldnames,
                [
                    "run_id", "window_id", "scene_id", "prn", "tracking_channel",
                    "environment_class", "frozen_elevation_group", "window_utc",
                    "nearest_candidate_utc", "nearest_candidate_source_file",
                    "nearest_candidate_record_id", "candidate_delta_seconds_signed",
                    "candidate_delta_seconds_abs", "local_cadence_limit_seconds",
                    "candidate_cell_status", "gsv_source_utc", "elevation_deg", "azimuth_deg",
                    "source_file", "status", "missing_reason",
                ],
            )
        self.assertEqual(len(overlay), 1)
        self.assertEqual((overlay[0]["run_id"], overlay[0]["window_id"]), ("run-a", "1"))
        self.assertEqual(overlay[0]["status"], "GSV_MATCHED")
        with summary_path.open(newline="", encoding="utf-8") as handle:
            summary = list(csv.DictReader(handle))
        total = next(row for row in summary if row["summary_scope"] == "TOTAL")
        self.assertEqual(total["window_count"], "1")
        self.assertEqual(total["gsv_matched_count"], "1")

        output_bytes = b"".join(
            path.read_bytes() for path in (overlay_path, summary_path, audit_path)
        )
        self.assertNotIn(b"4807.038", output_bytes)
        self.assertNotIn(b"01131.000", output_bytes)
        self.assertNotIn(b"GPGSV,1,1,1,03,42,123,40", output_bytes)
        self.assertNotIn(b"raw_gsv_sentence", output_bytes)
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertEqual(audit["input_counts"]["stage2_window_count"], 1)
        self.assertEqual(audit["input_counts"]["stage2_path_row_count"], 2)
        self.assertEqual(audit["input_counts"]["overlay_row_count"], 1)
        self.assertEqual(audit["scenes"][0]["gps_time_alignment_status"], "VERIFIED")
        self.assertEqual(audit["scenes"][0]["gps_prn_inventory_count"], 1)
        self.assertEqual(audit["cohort_source_pins"]["cohort_generator"]["root"], "code_worktree")
        self.assertEqual(
            audit["audit_software"]["audit_runner"]["sha256"],
            _sha256(self.script),
        )
        for name in ("geometry_identity_helper", "gps_time_helper", "nmea_rinex_parser"):
            self.assertEqual(audit["audit_software"][name]["root"], "code_worktree")
            self.assertEqual(len(audit["audit_software"][name]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
