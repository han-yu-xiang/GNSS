import unittest
import re
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

    def test_telemetry_table_uses_char_name_value_parameter(self) -> None:
        self.assertIn("navSymbol, prn, 'VariableNames'", self.stage0)
        self.assertNotIn('navSymbol, prn, "VariableNames"', self.stage0)
        self.assertIn(
            "{'tow_s', 'sample_counter', 'preamble_tow_s', 'nav_symbol', 'prn'}",
            self.stage0,
        )
        self.assertNotIn(
            '{"tow_s", "sample_counter", "preamble_tow_s", "nav_symbol", "prn"}',
            self.stage0,
        )

    def _without_phase_export(self, source: str) -> str:
        """Remove only the explicitly allowed Stage4 output-export delta."""
        helper_start = source.find("\nfunction [phaseRad, relativePhaseRad")
        if helper_start >= 0:
            helper_end = source.find("\nfunction paths = optimizeJointPaths", helper_start)
            self.assertGreater(helper_end, helper_start)
            source = source[:helper_start] + source[helper_end:]
        original_path_record = (
            "\n        pathRecords(end + 1, 1) = struct( ... %#ok<AGROW>\n"
            "            \"center_window_id\", centerId, ...\n"
            "            \"joint_selected_L\", selectedOrder, ...\n"
            "            \"path_id\", pathIndex, ...\n"
            "            \"is_multipath\", pathIndex > 1, ...\n"
            "            \"delay_samples\", path.delaySamples, ...\n"
            "            \"excess_delay_samples\", path.delaySamples ...\n"
            "                - selected.paths(1).delaySamples, ...\n"
            "            \"excess_delay_chips\", (path.delaySamples ...\n"
            "                - selected.paths(1).delaySamples) ...\n"
            "                / cfg.samplesPerChip, ...\n"
            "            \"doppler_hz\", path.dopplerHz, ...\n"
            "            \"doppler_offset_hz\", path.dopplerHz ...\n"
            "                - selected.paths(1).dopplerHz, ...\n"
            "            \"mean_relative_power_db\", ...\n"
            "                selected.relativePowerDb(pathIndex));"
        )
        source, path_record_count = re.subn(
            r"\n        referencePath = selected\.paths\(1\);.*?"
            r"\n            \"phase_source\", \"joint_selected_path_alpha\"\);",
            original_path_record,
            source,
            flags=re.DOTALL,
        )
        self.assertEqual(path_record_count, 1)
        source, empty_record_count = re.subn(
            r"\n    \"mean_relative_power_db\", nan, \.\.\."
            r"\n    \"phase_rad\", nan, \"relative_phase_rad\", nan, \.\.\."
            r"\n    \"relative_phase_available\", false, \.\.\."
            r"\n    \"relative_amplitude\", nan, \"relative_amplitude_db\", nan, \.\.\."
            r"\n    \"phase_source\", \"\"\);",
            "\n    \"mean_relative_power_db\", nan);",
            source,
            count=1,
        )
        self.assertEqual(empty_record_count, 1)
        return source

    def _without_result_packaging(self, source: str) -> str:
        """Normalize the explicit scalar-container packaging delta.

        The Rain branch must not use the unsafe cell-expanding struct
        constructor.  The numerical body remains compared with the copied
        source, while the output-container fix is checked separately by
        test_rain_result_packaging.py.
        """
        start = source.find("\n% Keep the Stage 1-4 result container scalar.")
        if start < 0:
            start = source.index("\nresult = struct")
        end = source.index("\nend", start)
        return source[:start] + "\n% result packaging normalized\n" + source[end:]

    def test_stage0_stage4_body_matches_extracted_source_except_export_only_delta(self) -> None:
        marker = "assert(isfolder(outputDir)"
        core_body = self._without_result_packaging(CORE.read_text(encoding="utf-8"))
        self.assertEqual(
            core_body[core_body.index(marker) :].rstrip(),
            self._without_result_packaging(
                self._without_phase_export(
                    self.standalone[self.standalone.index(marker) :]
                )
            ).rstrip(),
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
