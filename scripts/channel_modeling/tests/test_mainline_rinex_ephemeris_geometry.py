from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import scripts.channel_modeling.run_mainline_rinex_ephemeris_recovery as recovery_runner

from scripts.channel_modeling.mainline_rinex_ephemeris_geometry import (
    parse_gps_lnav_records,
    satellite_elevation_deg,
    select_ephemeris,
)
from scripts.channel_modeling.run_mainline_rinex_ephemeris_recovery import (
    build_exact_gga_height_index,
    build_recovery_overlay,
    summarize_recovery,
    write_recovery_outputs,
)


def _field(value: float) -> str:
    return f"{value:19.12E}".replace("E", "D")


def nmea_sentence(body: str) -> str:
    checksum = 0
    for character in body:
        checksum ^= ord(character)
    return f"${body}*{checksum:02X}"


def gga_sentence(
    *,
    time: str = "000000.000",
    latitude: str = "0000.0000",
    latitude_hemisphere: str = "N",
    longitude: str = "00000.0000",
    longitude_hemisphere: str = "E",
    quality: int = 1,
    satellites: int = 8,
    hdop: str = "0.9",
    altitude: str = "129.0",
    altitude_unit: str = "M",
    geoid: str = "18.025",
    geoid_unit: str = "M",
) -> str:
    return nmea_sentence(
        f"GPGGA,{time},{latitude},{latitude_hemisphere},{longitude},"
        f"{longitude_hemisphere},{quality},{satellites},{hdop},{altitude},"
        f"{altitude_unit},{geoid},{geoid_unit},,"
    )


def rmc_sentence(*, time: str = "000000.000", date: str = "210126", status: str = "A") -> str:
    return nmea_sentence(
        f"GPRMC,{time},{status},0000.0000,N,00000.0000,E,0,0,{date},,,A"
    )


def rinex3_record(
    prn: str = "G03",
    *,
    epoch: str = "2026 01 21 00 00 00",
    week: float = 2402,
    toe: float = 259218.0,
    health: float = 0.0,
    fit_interval: float = 0.0,
    eccentricity: float = 0.0,
    sqrt_a: float = 5153.7955,
    omega0: float = 0.0,
    inclination: float = 0.0,
) -> str:
    clock = (0.0, 0.0, 0.0)
    rows = (
        clock,
        (0.0, 0.0, 0.0, 0.0),  # IODE, Crs, delta-n, M0
        (0.0, eccentricity, 0.0, sqrt_a),  # Cuc, e, Cus, sqrt(A)
        (toe, 0.0, omega0, 0.0),  # Toe, Cic, Omega0, Cis
        (0.0, 0.0, 0.0, 0.0),  # i0, Crc, omega, Omega-dot
        (0.0, 0.0, week, 0.0),  # IDOT, codes, GPS week, L2P
        (0.0, health, 0.0, 0.0),  # SV accuracy, health, TGD, IODC
        (0.0, fit_interval, 0.0, 0.0),  # transmission time, fit interval, spares
    )
    header = f"{prn} {epoch}" + "".join(_field(value) for value in clock)
    return header + "\n" + "\n".join(
        "    " + "".join(_field(value) for value in row) for row in rows[1:]
    ) + "\n"


def geometry_row(
    run_id: str,
    window_id: str,
    *,
    scene_id: str = "scene-a",
    prn: str = "G03",
    status: str = "MISSING",
    elevation: str = "",
) -> dict[str, str]:
    return {
        "run_id": run_id,
        "window_id": window_id,
        "scene_id": scene_id,
        "prn": prn,
        "tracking_channel": "2",
        "environment_class": "Urban",
        "frozen_elevation_group": "MISSING",
        "window_utc": "2026-01-21T00:00:00.000Z",
        "elevation_deg": elevation,
        "source_file": "trajectory/scene-a_trajectory.nmea" if status == "GSV_MATCHED" else "",
        "status": status,
        "missing_reason": "NO_TARGET_PRN_GSV" if status == "MISSING" else "",
    }


def trajectory_row(
    run_id: str,
    window_id: str,
    *,
    scene_id: str = "scene-a",
    prn: str = "G03",
    status: str = "POSITION_MATCHED",
) -> dict[str, str]:
    return {
        "run_id": run_id,
        "window_id": window_id,
        "scene_id": scene_id,
        "prn": prn,
        "tracking_channel": "2",
        "window_utc": "2026-01-21T00:00:00.000Z",
        "position_utc": "2026-01-21T00:00:00.000Z" if status == "POSITION_MATCHED" else "",
        "position_delta_seconds": "0" if status == "POSITION_MATCHED" else "",
        "position_source_path": "scenes/scene-a/trajectory/scene-a_trajectory.nmea" if status == "POSITION_MATCHED" else "",
        "position_source_record_id": "scene-a_trajectory.nmea:000123" if status == "POSITION_MATCHED" else "",
        "latitude_deg": "0" if status == "POSITION_MATCHED" else "",
        "longitude_deg": "0" if status == "POSITION_MATCHED" else "",
        "position_status": "POSITION_MISSING" if status == "OUTSIDE_OBSERVED_ROUTE_COVERAGE" else status,
        "missing_reason": "" if status == "POSITION_MATCHED" else "OUTSIDE_OBSERVED_ROUTE_COVERAGE",
    }


class MainlineRinexEphemerisGeometryTests(unittest.TestCase):
    def test_parser_reads_rinex3_fields_and_fortran_d_exponents(self):
        records = parse_gps_lnav_records(rinex3_record())

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.prn, "G03")
        self.assertEqual(record.toc_gps_calendar, datetime(2026, 1, 21, tzinfo=None))
        self.assertEqual(record.week_number, 2402)
        self.assertAlmostEqual(record.toe_seconds, 259218.0)
        self.assertAlmostEqual(record.sqrt_a_m_sqrt, 5153.7955)
        self.assertEqual(record.health, 0)

    def test_selection_uses_exact_prn_healthy_record_and_inclusive_two_hour_toe_age(self):
        healthy = rinex3_record(prn="G03", toe=252018.0)
        unhealthy = rinex3_record(prn="G03", toe=252018.0, health=1.0)
        wrong_prn = rinex3_record(prn="G04", toe=252018.0)
        records = parse_gps_lnav_records(unhealthy + wrong_prn + healthy)
        observation = datetime(2026, 1, 21, tzinfo=timezone.utc)
        just_outside = parse_gps_lnav_records(
            rinex3_record(prn="G03", toe=252017.9)
        )[0]

        selected = select_ephemeris(records, "G03", observation)
        rejected = select_ephemeris(records, "G05", observation)
        expired = select_ephemeris([just_outside], "G03", observation)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.health, 0)
        self.assertIsNone(rejected)
        self.assertIsNone(expired)

    def test_selection_handles_gps_week_rollover_and_rejects_stale_record(self):
        record = parse_gps_lnav_records(
            rinex3_record(prn="G03", epoch="1981 12 06 23 59 00", week=100, toe=604000.0)
        )[0]
        # GPS week 101, TOW 50 seconds, represented as UTC with the 18 s offset.
        observation = datetime(1980, 1, 6, tzinfo=timezone.utc) + timedelta(
            weeks=101, seconds=32
        )
        stale_observation = observation + timedelta(hours=3)

        selected = select_ephemeris([record], "G03", observation)
        stale = select_ephemeris([record], "G03", stale_observation)

        self.assertIsNotNone(selected)
        self.assertIsNone(stale)

    def test_selection_rejects_record_one_full_gps_week_old_at_same_toe(self):
        record = parse_gps_lnav_records(
            rinex3_record(
                prn="G03",
                epoch="1981 12 06 00 00 00",
                week=100,
                toe=252018.0,
            )
        )[0]
        # Same time-of-week in continuous GPS week 101 is 604,800 seconds
        # after this full-week RINEX record, not a week rollover alias.
        observation = datetime(1980, 1, 6, tzinfo=timezone.utc) + timedelta(
            weeks=101, seconds=252000
        )

        selected = select_ephemeris([record], "G03", observation)

        self.assertIsNone(selected)

    def test_broadcast_orbit_places_synthetic_zero_inclination_satellite_at_zenith(self):
        record = parse_gps_lnav_records(
            rinex3_record(
                epoch="1980 01 06 00 00 00",
                week=0,
                toe=0.0,
            )
        )[0]

        elevation = satellite_elevation_deg(
            record,
            datetime(1980, 1, 5, 23, 59, 42, tzinfo=timezone.utc),
            latitude_deg=0.0,
            longitude_deg=0.0,
        )

        self.assertGreaterEqual(elevation, 89.9)
        self.assertLessEqual(elevation, 90.0)

    def test_parser_rejects_incomplete_rinex_record(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            parse_gps_lnav_records(rinex3_record().splitlines()[0])

    def test_parser_treats_blank_optional_transmission_and_fit_fields_as_zero(self):
        lines = rinex3_record().splitlines()
        lines[-1] = "    " + _field(0.0) + _field(0.0) + " " * 38

        record = parse_gps_lnav_records("\n".join(lines))[0]

        self.assertEqual(record.fit_interval_hours, 0.0)

    def test_parser_reads_rinex_fit_interval_from_second_last_line_field(self):
        record = parse_gps_lnav_records(rinex3_record(fit_interval=4.0))[0]

        self.assertEqual(record.fit_interval_hours, 4.0)

    def test_propagation_rejects_invalid_receiver_coordinates(self):
        record = parse_gps_lnav_records(rinex3_record())[0]

        with self.assertRaisesRegex(ValueError, "latitude"):
            satellite_elevation_deg(
                record,
                datetime(2026, 1, 21, tzinfo=timezone.utc),
                latitude_deg=91.0,
                longitude_deg=0.0,
            )


class MainlineRinexRecoveryOverlayTests(unittest.TestCase):
    def setUp(self):
        self.ephemeris = parse_gps_lnav_records(rinex3_record())[0]

    def test_overlay_preserves_gsv_and_derives_only_missing_rows_with_position(self):
        geometry = [
            geometry_row("run-a", "1", status="GSV_MATCHED", elevation="42"),
            geometry_row("run-a", "2"),
            geometry_row("run-a", "3", prn="G04"),
            geometry_row("run-b", "1", status="GSV_MATCHED", elevation="51"),
        ]
        trajectory = [
            trajectory_row("run-a", "1"),
            trajectory_row("run-a", "2"),
            trajectory_row("run-a", "3", prn="G04"),
            trajectory_row("run-b", "1", status="OUTSIDE_OBSERVED_ROUTE_COVERAGE"),
        ]

        rows = build_recovery_overlay(
            geometry,
            trajectory,
            {"scene-a": [self.ephemeris]},
            nav_source_by_scene={"scene-a": "scenes/scene-a/navigation/rinex_nav/RINEXFILE.26N"},
        )
        by_key = {(row["run_id"], row["window_id"]): row for row in rows}

        self.assertEqual(len(rows), 4)
        self.assertEqual(by_key[("run-a", "1")]["elevation_source"], "GSV_MEASURED")
        self.assertEqual(by_key[("run-a", "1")]["gsv_measured_elevation_deg"], "42")
        self.assertEqual(by_key[("run-a", "1")]["ephemeris_derived_elevation_deg"], "")
        self.assertEqual(by_key[("run-a", "2")]["elevation_source"], "EPHEMERIS_DERIVED")
        self.assertNotEqual(by_key[("run-a", "2")]["ephemeris_derived_elevation_deg"], "")
        self.assertEqual(
            by_key[("run-a", "2")]["nav_toc_gps_calendar"],
            "2026-01-21T00:00:00",
        )
        self.assertEqual(by_key[("run-a", "2")]["receiver_position_record_id"], "scene-a_trajectory.nmea:000123")
        self.assertEqual(
            by_key[("run-a", "3")]["elevation_missing_reason"],
            "NO_HEALTHY_EPHEMERIS_FOR_PRN_WITHIN_2H",
        )
        self.assertEqual(by_key[("run-b", "1")]["elevation_source"], "GSV_MEASURED")
        self.assertEqual(by_key[("run-b", "1")]["receiver_position_status"], "POSITION_MISSING")
        self.assertNotIn("latitude_deg", by_key[("run-a", "2")])
        self.assertNotIn("longitude_deg", by_key[("run-a", "2")])

    def test_overlay_rejects_nonfinite_or_out_of_range_measured_gsv_elevation(self):
        for elevation in ("NaN", "Inf", "-1", "91"):
            with self.subTest(elevation=elevation), self.assertRaisesRegex(
                ValueError, "invalid measured GSV elevation"
            ):
                build_recovery_overlay(
                    [geometry_row("run-a", "1", status="GSV_MATCHED", elevation=elevation)],
                    [trajectory_row("run-a", "1")],
                    {},
                )

    def test_full_overlay_refuses_to_write_when_required_pilot_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            def fail_unexpected_pilot(_project, _geometry, _trajectory, scene_id):
                if scene_id != recovery_runner.REQUIRED_PILOT_SCENE:
                    raise AssertionError(f"unexpected required pilot scene: {scene_id}")
                return {"scene_id": scene_id, "passed": False, "comparison_count": 145}

            with patch.object(
                recovery_runner,
                "_pilot",
                side_effect=fail_unexpected_pilot,
            ):
                with self.assertRaisesRegex(ValueError, "required GSV pilot failed"):
                    recovery_runner._run_full(
                        root,
                        root / "missing_geometry.csv",
                        root / "missing_trajectory.csv",
                        output,
                    )

            self.assertFalse(output.exists())

    def test_gsv_validation_pilot_rejects_invalid_measured_elevation(self):
        with self.assertRaisesRegex(ValueError, "invalid measured GSV elevation"):
            recovery_runner.validate_gsv_pilot(
                [geometry_row("run-a", "1", status="GSV_MATCHED", elevation="NaN")],
                [trajectory_row("run-a", "1")],
                [],
                "scene-a",
            )

    def test_gsv_validation_pilot_binds_metrics_to_compared_window_identities(self):
        result = recovery_runner.validate_gsv_pilot(
            [geometry_row("run-a", "1", status="GSV_MATCHED", elevation="42")],
            [trajectory_row("run-a", "1")],
            [self.ephemeris],
            "scene-a",
        )

        self.assertEqual(result["comparison_count"], 1)
        self.assertEqual(result["comparison_identity_count"], 1)
        self.assertEqual(
            result["comparison_identity_sha256"],
            "9c1aad927adf677430492c32f0093467bdbe09729104d8c572d004f0b8d51a85",
        )

    def test_full_audit_records_passing_pilot_metrics_and_identity_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            geometry_path = root / "geometry.csv"
            trajectory_path = root / "trajectory.csv"
            geometry_path.write_text("synthetic geometry input\n", encoding="utf-8")
            trajectory_path.write_text("synthetic trajectory input\n", encoding="utf-8")
            output = root / "recovery-output"
            nav_paths = {}
            nmea_paths = {}
            for scene in recovery_runner.EXPECTED_SCENES:
                nav_paths[scene] = root / f"{scene}.nav"
                nmea_paths[scene] = root / f"{scene}.nmea"
                nav_paths[scene].write_text("synthetic nav pin\n", encoding="ascii")
                nmea_paths[scene].write_text("synthetic nmea pin\n", encoding="ascii")

            geometry = []
            trajectory = []
            for index in range(recovery_runner.EXPECTED_WINDOWS):
                scene = recovery_runner.EXPECTED_SCENES[index % len(recovery_runner.EXPECTED_SCENES)]
                matched = index < 5128
                geometry.append(
                    geometry_row(
                        f"run-{index}",
                        "1",
                        scene_id=scene,
                        status="GSV_MATCHED" if matched else "MISSING",
                        elevation="42" if matched else "",
                    )
                )
                trajectory.append(
                    trajectory_row(
                        f"run-{index}",
                        "1",
                        scene_id=scene,
                        status="OUTSIDE_OBSERVED_ROUTE_COVERAGE",
                    )
                )

            pilot = {
                "scene_id": recovery_runner.REQUIRED_PILOT_SCENE,
                "passed": True,
                "comparison_count": 145,
                "comparison_identity_count": 145,
                "comparison_identity_sha256": "a" * 64,
            }
            def passing_pilot(_project, _geometry, _trajectory, scene_id):
                return {**pilot, "scene_id": scene_id}

            with (
                patch.object(recovery_runner, "_pilot", side_effect=passing_pilot),
                patch.object(recovery_runner, "_load_overlays", return_value=(geometry, trajectory)),
                patch.object(
                    recovery_runner,
                    "_load_scene_navigation",
                    side_effect=lambda _root, scene: (nav_paths[scene], []),
                ),
                patch.object(
                    recovery_runner,
                    "_load_scene_nmea",
                    side_effect=lambda _root, scene: (nmea_paths[scene], ""),
                ),
                patch.object(recovery_runner, "build_exact_gga_height_index", return_value=({}, {})),
            ):
                recovery_runner._run_full(root, geometry_path, trajectory_path, output)

            audit = json.loads(
                (output / "geometry_ephemeris_recovery_audit.json").read_text(encoding="utf-8")
            )

        self.assertEqual(audit["required_gsv_pilot"]["scene_id"], recovery_runner.REQUIRED_PILOT_SCENE)
        self.assertEqual(audit["required_gsv_pilot"]["comparison_count"], 145)
        self.assertEqual(audit["required_gsv_pilot"]["comparison_identity_sha256"], "a" * 64)

    def test_overlay_requires_exact_unique_identity_and_consistent_metadata(self):
        geom = geometry_row("run-a", "1")
        traj = trajectory_row("run-a", "1")
        wrong_scene = trajectory_row("run-a", "1", scene_id="scene-b")

        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_recovery_overlay([geom, dict(geom)], [traj], {"scene-a": [self.ephemeris]})
        with self.assertRaisesRegex(ValueError, "scene_id"):
            build_recovery_overlay([geom], [wrong_scene], {"scene-a": [self.ephemeris]})
        with self.assertRaisesRegex(ValueError, "same identity set"):
            build_recovery_overlay([geom], [], {"scene-a": [self.ephemeris]})

    def test_summary_separates_measured_derived_missing_and_joint_position_support(self):
        geometry = [geometry_row("run-a", "1", status="GSV_MATCHED", elevation="42"), geometry_row("run-a", "2")]
        trajectory = [trajectory_row("run-a", "1"), trajectory_row("run-a", "2")]
        rows = build_recovery_overlay(geometry, trajectory, {"scene-a": [self.ephemeris]})

        total = next(row for row in summarize_recovery(rows) if row["summary_scope"] == "TOTAL")

        self.assertEqual(total["window_count"], "2")
        self.assertEqual(total["gsv_measured_count"], "1")
        self.assertEqual(total["ephemeris_derived_count"], "1")
        self.assertEqual(total["elevation_missing_count"], "0")
        self.assertEqual(total["position_matched_count"], "2")
        self.assertEqual(total["joint_elevation_position_count"], "2")

    def test_exact_valid_gga_height_is_joined_by_scene_window_and_position(self):
        geometry = [geometry_row("run-a", "1")]
        trajectory = [trajectory_row("run-a", "1")]
        geometry[0]["window_utc"] = "2026-01-21T00:00:00.310Z"
        trajectory[0]["window_utc"] = geometry[0]["window_utc"]
        nmea = rmc_sentence() + "\n" + gga_sentence() + "\n"

        index, counts = build_exact_gga_height_index(
            geometry, trajectory, {"scene-a": nmea}
        )
        rows = build_recovery_overlay(
            geometry,
            trajectory,
            {"scene-a": [self.ephemeris]},
            receiver_height_by_identity=index,
        )
        result = rows[0]

        self.assertEqual(set(index), {("run-a", "1")})
        self.assertAlmostEqual(index[("run-a", "1")]["height_m"], 147.025)
        self.assertEqual(counts["scene-a"]["exact_gga_position_consistent_identity_count"], 1)
        self.assertEqual(result["receiver_height_source"], "GGA_ELLIPSOIDAL_HEIGHT")
        self.assertEqual(result["receiver_height_m"], "147.025000")
        self.assertEqual(result["receiver_height_record_id"], "scene-a_trajectory.nmea:000002")
        self.assertEqual(result["receiver_height_utc"], "2026-01-21T00:00:00Z")
        self.assertEqual(result["receiver_height_assumption_m"], "")

    def test_gga_height_requires_exact_time_valid_fix_units_and_position_agreement(self):
        geom = [geometry_row("run-a", "1")]
        traj = [trajectory_row("run-a", "1")]
        cases = (
            (gga_sentence(time="000001.000"), "off-time"),
            (gga_sentence(quality=0), "invalid-fix"),
            (gga_sentence(satellites=3), "insufficient-satellites"),
            (gga_sentence(altitude_unit="F"), "invalid-units"),
            (gga_sentence(longitude="00000.0100"), "position-mismatch"),
            (gga_sentence()[:-2] + "00", "invalid-checksum"),
        )

        for sentence, _label in cases:
            with self.subTest(case=_label):
                index, _ = build_exact_gga_height_index(
                    geom, traj, {"scene-a": rmc_sentence() + "\n" + sentence + "\n"}
                )
                self.assertEqual(index, {})

    def test_conflicting_exact_time_gga_records_are_not_used(self):
        geometry = [geometry_row("run-a", "1")]
        trajectory = [trajectory_row("run-a", "1")]
        nmea = "\n".join(
            (rmc_sentence(), gga_sentence(), gga_sentence(altitude="130.0"), "")
        )

        index, counts = build_exact_gga_height_index(
            geometry, trajectory, {"scene-a": nmea}
        )

        self.assertEqual(index, {})
        self.assertEqual(counts["scene-a"]["conflicting_exact_time_gga_count"], 1)

    def test_rows_without_exact_gga_keep_explicit_zero_height_assumption(self):
        geometry = [geometry_row("run-a", "1")]
        trajectory = [trajectory_row("run-a", "1")]
        rows = build_recovery_overlay(
            geometry,
            trajectory,
            {"scene-a": [self.ephemeris]},
            receiver_height_by_identity={},
        )

        self.assertEqual(rows[0]["receiver_height_source"], "ZERO_HEIGHT_ASSUMPTION")
        self.assertEqual(rows[0]["receiver_height_m"], "0.000000")
        self.assertEqual(rows[0]["receiver_height_assumption_m"], "0.0")

    def test_output_is_create_new_and_does_not_contain_coordinates(self):
        geometry = [geometry_row("run-a", "1", status="GSV_MATCHED", elevation="42")]
        trajectory = [trajectory_row("run-a", "1")]
        rows = build_recovery_overlay(geometry, trajectory, {})
        summary = summarize_recovery(rows)

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "new-output"
            write_recovery_outputs(output, rows, summary, {"input_files": {}})
            header = (output / "geometry_ephemeris_recovery_overlay.csv").read_text(encoding="utf-8").splitlines()[0]
            self.assertNotIn("latitude_deg", header)
            self.assertNotIn("longitude_deg", header)
            original = (output / "geometry_ephemeris_recovery_overlay.csv").read_bytes()
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                write_recovery_outputs(output, rows, summary, {"input_files": {}})
            self.assertEqual((output / "geometry_ephemeris_recovery_overlay.csv").read_bytes(), original)

    def test_runner_cli_imports_project_modules_when_invoked_by_path(self):
        repo_root = Path(__file__).resolve().parents[3]
        runner = repo_root / "scripts" / "channel_modeling" / "run_mainline_rinex_ephemeris_recovery.py"

        result = subprocess.run(
            [sys.executable, str(runner), "--help"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--validate-scene", result.stdout)


if __name__ == "__main__":
    unittest.main()
