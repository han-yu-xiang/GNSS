import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_rain_sage_inputs as audit  # noqa: E402


class RainInputAuditTests(unittest.TestCase):
    def make_scene(self, root: Path, rate: int = 10_230_000) -> Path:
        scene = root / "rain" / "F1023_clear"
        results = scene / "results"
        (results / "tracking").mkdir(parents=True)
        (results / "telemetry").mkdir(parents=True)
        (results / "observables").mkdir(parents=True)
        (results / "navigation").mkdir(parents=True)
        (scene / "F1023_clear.bin").write_bytes(b"\x00\x01")
        (scene / "F1023_clear.conf").write_text(
            "\n".join(
                [
                    "SignalSource.filename=/mnt/e/rain/F1023_clear/F1023_clear.bin",
                    "SignalSource.item_type=ishort",
                    f"SignalSource.sampling_frequency={rate}",
                    "Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking",
                    "TelemetryDecoder_1C.dump=true",
                    "Observables.dump=true",
                    "PVT.nmea_output_file_enabled=true",
                    "PVT.xml_output_enabled=true",
                ]
            ),
            encoding="utf-8",
        )
        telemetry = b"".join(
            struct.pack("<dQdii", i * 0.02, i * 204600, 0.0, 1, 24)
            for i in range(4)
        )
        (results / "telemetry" / "F1023_clear_telemetry_ch_10.dat").write_bytes(
            telemetry
        )
        (results / "telemetry" / "F1023_clear_telemetry_ch_10.mat").write_bytes(
            b"mat"
        )
        (results / "tracking" / "F1023_clear_track_ch_10.dat").write_bytes(
            b"tracking"
        )
        (results / "tracking" / "F1023_clear_track_ch_10.mat").write_bytes(
            b"mat"
        )
        return scene

    def test_telemetry_record_layout_and_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "telemetry.dat"
            path.write_bytes(
                b"".join(
                    struct.pack("<dQdii", i * 0.02, i * 204600, 0.0, -1, 24)
                    for i in range(3)
                )
            )
            parsed = audit.parse_telemetry(path)
            self.assertEqual(parsed["prns"], ["G24"])
            self.assertEqual(parsed["valid_nav_symbol_count"], 3)
            self.assertTrue(parsed["continuity_pass"])

    def test_missing_nmea_pvt_and_geometry_are_not_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_scene(root)
            result = audit.audit_scene(root, "F1023_clear")
            self.assertTrue(result["rain_sage_input_ready"])
            self.assertFalse(result["nmea_available"])
            self.assertFalse(result["pvt_available"])
            self.assertFalse(result["geometry_available"])
            self.assertFalse(result["execution_ready"])

    def test_wrong_sampling_rate_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_scene(root, rate=20_460_000)
            result = audit.audit_scene(root, "F1023_clear")
            self.assertFalse(result["rain_sage_input_ready"])
            self.assertIn("sample_rate_not_10230000", result["rain_sage_static_reasons"])

    def test_missing_raw_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scene = self.make_scene(root)
            (scene / "F1023_clear.bin").unlink()
            result = audit.audit_scene(root, "F1023_clear")
            self.assertFalse(result["rain_sage_input_ready"])
            self.assertIn("raw_missing_or_empty", result["rain_sage_static_reasons"])

    def test_missing_tracking_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_scene(root)
            (root / "rain" / "F1023_clear" / "results" / "tracking"
             / "F1023_clear_track_ch_10.mat").unlink()
            result = audit.audit_scene(root, "F1023_clear")
            self.assertFalse(result["rain_sage_input_ready"])
            self.assertIn(
                "tracking_mat_missing_or_empty_ch10",
                result["rain_sage_static_reasons"],
            )

    def test_missing_telemetry_produces_no_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scene = self.make_scene(root)
            (root / "rain" / "F1023_clear" / "results" / "telemetry"
             / "F1023_clear_telemetry_ch_10.dat").unlink()
            result = audit.audit_scene(root, "F1023_clear")
            self.assertFalse(result["rain_sage_input_ready"])
            self.assertIn("no_valid_telemetry_channel", result["rain_sage_static_reasons"])

    def test_raw_iq_is_not_opened_by_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_scene(root)
            result = audit.build_audit(root)
            self.assertFalse(result["raw_iq_samples_opened"])
            self.assertFalse(result["sage_executed"])
            self.assertFalse(result["matlab_executed"])

    def test_prn_channel_mapping_is_not_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_scene(root)
            result = audit.audit_scene(root, "F1023_clear")
            self.assertEqual(result["channels"][0]["prn"], "G24")
            self.assertNotEqual(result["channels"][0]["prn"], "G25")
            self.assertEqual(result["channels"][0]["tracking_channel"], 10)

    def test_rain_stage0_has_explicit_prn_channel_mismatch_gate(self) -> None:
        source = (Path(__file__).resolve().parent / "build_rain_stage0.m").read_text(
            encoding="utf-8"
        )
        self.assertIn("Requested PRN %s is not present", source)
        self.assertIn("TrackingChannel", source)

    def test_rain_namespace_is_separate_from_production_namespace(self) -> None:
        source = (Path(__file__).resolve().parent / "run_rain_sage_pipeline.m").read_text(
            encoding="utf-8"
        )
        self.assertIn('"rain_sage_v1"', source)
        self.assertNotIn("nav_sage_v2", source)

    def test_resume_true_is_rejected_and_default_is_false(self) -> None:
        source = (Path(__file__).resolve().parent / "run_rain_sage_pipeline.m").read_text(
            encoding="utf-8"
        )
        self.assertIn('addParameter(parser, "Resume", false', source)
        self.assertIn("Rain pipeline is new-only; Resume=true is rejected.", source)


if __name__ == "__main__":
    unittest.main()
