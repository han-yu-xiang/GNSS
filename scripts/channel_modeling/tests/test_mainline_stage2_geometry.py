from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts.channel_modeling.mainline_stage2_geometry import (
    build_stage0_utc_index,
    build_stage2_window_index,
)


def path_row(
    run_id: str,
    window_id: str,
    path_id: str,
    *,
    scene_id: str = "scene-a",
    prn: str = "G03",
    tracking_channel: str = "2",
) -> dict[str, str]:
    return {
        "run_id": run_id,
        "scene_id": scene_id,
        "prn": prn,
        "tracking_channel": tracking_channel,
        "window_id": window_id,
        "path_id": path_id,
    }


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


if __name__ == "__main__":
    unittest.main()
