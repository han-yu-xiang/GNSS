import unittest
from pathlib import Path


RAIN = Path(__file__).resolve().parent
CORE = RAIN.parent / "core" / "run_sage_stage1_stage4_core.m"


class RainStandalonePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = (RAIN / "run_rain_sage_pipeline.m").read_text(encoding="utf-8")
        self.stage0 = (RAIN / "build_rain_stage0.m").read_text(encoding="utf-8")
        self.standalone = (RAIN / "run_rain_sage_stage1_stage4.m").read_text(
            encoding="utf-8"
        )
        self.config = (RAIN / "default_rain_sage_configuration.m").read_text(
            encoding="utf-8"
        )
        self.doppler = (RAIN / "compute_rain_doppler_bound.m").read_text(
            encoding="utf-8"
        )
        self.smoke = (RAIN / "run_rain_matlab_syntax_smoke.m").read_text(
            encoding="utf-8"
        )

    def test_entry_is_new_only_and_uses_rain_namespace(self) -> None:
        self.assertIn('addParameter(parser, "Resume", false', self.entry)
        self.assertIn('"rain_sage_v1"', self.entry)
        self.assertNotIn("nav_sage_v2", self.entry)
        self.assertIn("run_rain_sage_stage1_stage4(", self.entry)

    def test_entry_has_no_shared_core_dependency(self) -> None:
        for source in (self.entry, self.stage0, self.standalone):
            self.assertNotIn("run_sage_stage1_stage4_core", source)
            self.assertNotIn("default_sage_configuration", source)
            self.assertNotIn("compute_sage_doppler_bound", source)

    def test_stage0_uses_local_configuration_and_fallback(self) -> None:
        self.assertIn("default_rain_sage_configuration", self.stage0)
        self.assertIn("compute_rain_doppler_bound", self.stage0)
        self.assertIn("unavailable_no_NMEA", self.stage0)

    def test_stage0_stage4_body_matches_extracted_source(self) -> None:
        marker = "assert(isfolder(outputDir)"
        core_body = CORE.read_text(encoding="utf-8")
        self.assertEqual(
            core_body[core_body.index(marker) :].rstrip(),
            self.standalone[self.standalone.index(marker) :].rstrip(),
        )

    def test_frozen_configuration_and_criterion_are_present(self) -> None:
        for marker in (
            "cfg.pipelineVersion = 3;",
            "cfg.maximumModelOrder = 4;",
            "cfg.jointSnapshotCount = 5;",
            "cfg.minimumJointSnapshotWins = 4;",
        ):
            self.assertIn(marker, self.config)
        for marker in ("joint_valid", "joint_multipath_count", "is_multipath"):
            self.assertIn(marker, self.standalone)

    def test_doppler_fallback_matches_frozen_formula(self) -> None:
        for marker in (
            "fallback_120_kmh",
            "minimumRelativeDopplerBoundHz",
            "absoluteRelativeDopplerCeilingHz",
        ):
            self.assertIn(marker, self.doppler)

    def test_rain_smoke_is_parse_only_and_rain_scoped(self) -> None:
        self.assertIn('"Scope", "rain"', self.smoke)
        self.assertIn("raw IQ", self.smoke)
        self.assertNotIn("run_sage_stage1_stage4_core", self.smoke)
        self.assertNotIn("readIq(", self.smoke)


if __name__ == "__main__":
    unittest.main()
