import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "run_nav_sage_pipeline.m"
CORE = ROOT / "core" / "run_sage_stage1_stage4_core.m"
CONFIG = ROOT / "core" / "default_sage_configuration.m"
DOPPLER = ROOT / "core" / "compute_sage_doppler_bound.m"
RAIN_ENTRY = ROOT / "rain" / "run_rain_sage_pipeline.m"
RAIN_STAGE0 = ROOT / "rain" / "build_rain_stage0.m"
RAIN_STANDALONE = ROOT / "rain" / "run_rain_sage_stage1_stage4.m"
RAIN_CONFIG = ROOT / "rain" / "default_rain_sage_configuration.m"
RAIN_DOPPLER = ROOT / "rain" / "compute_rain_doppler_bound.m"
RAIN_SMOKE = ROOT / "rain" / "run_rain_matlab_syntax_smoke.m"
SYNTAX_SMOKE = ROOT / "regression" / "run_matlab_syntax_smoke.m"


class SharedCoreStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.production = PRODUCTION.read_text(encoding="utf-8")
        self.core = CORE.read_text(encoding="utf-8")
        self.config = CONFIG.read_text(encoding="utf-8")
        self.doppler = DOPPLER.read_text(encoding="utf-8")
        self.rain_entry = RAIN_ENTRY.read_text(encoding="utf-8")
        self.rain_stage0 = RAIN_STAGE0.read_text(encoding="utf-8")
        self.rain_standalone = RAIN_STANDALONE.read_text(encoding="utf-8")
        self.rain_config = RAIN_CONFIG.read_text(encoding="utf-8")
        self.rain_doppler = RAIN_DOPPLER.read_text(encoding="utf-8")
        self.rain_smoke = RAIN_SMOKE.read_text(encoding="utf-8")

    def test_production_is_monolithic_and_core_is_preserved_as_audit_evidence(self) -> None:
        self.assertNotIn("run_sage_stage1_stage4_core(", self.production)
        self.assertIn("run_sage_stage1_stage4_local(", self.production)
        self.assertIn("default_sage_configuration(", self.production)
        self.assertIn("run_sage_stage1_stage4_core(", self.core)

    def test_production_contains_stage_helpers_and_core_keeps_audit_copy(self) -> None:
        for name in (
            "determineDopplerSign",
            "runFastScan",
            "runStage2",
            "flattenStage2",
            "evaluatePersistence",
            "runJointStage",
            "makeReplica",
            "readIq",
        ):
            self.assertIn(name, self.production)
            self.assertIn(name, self.core)

    def test_core_contains_stage_boundaries(self) -> None:
        for name in (
            "determineDopplerSign",
            "runFastScan",
            "runStage2",
            "flattenStage2",
            "evaluatePersistence",
            "runJointStage",
            "loadNavWipedFortyMs",
            "loadNavWipedTwentyMs",
        ):
            self.assertIn(name, self.core)

    def test_multiline_struct_calls_have_explicit_matlab_continuation(self) -> None:
        for path in (CORE, CONFIG, DOPPLER, PRODUCTION, RAIN_ENTRY, RAIN_STAGE0):
            lines = path.read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines, start=1):
                if line.rstrip().endswith("("):
                    self.assertTrue(
                        line.rstrip().endswith("..."),
                        f"{path}:{line_number} multiline MATLAB call lacks ...",
                    )
        self.assertIn("result = struct( ...", self.core)
        self.assertIn("result = struct( ...", self.production)

    def test_frozen_configuration_values_are_present(self) -> None:
        expected = (
            "cfg.pipelineVersion = 3;",
            "cfg.mainDopplerHalfWidthHz = 125;",
            "cfg.scanMainDopplerStepHz = 25;",
            "cfg.scanResidualDopplerStepHz = 50;",
            "cfg.maximumModelOrder = 4;",
            "cfg.delayStepSamples = 0.1;",
            "cfg.persistenceRadius = 2;",
            "cfg.jointSnapshotCount = 5;",
            "cfg.minimumJointSnapshotWins = 4;",
        )
        for marker in expected:
            self.assertIn(marker, self.config)

    def test_shared_doppler_fallback_is_single_source(self) -> None:
        self.assertIn("compute_sage_doppler_bound(", self.production)
        self.assertIn("compute_rain_doppler_bound(", self.rain_stage0)
        self.assertIn("fallback_120_kmh", self.rain_doppler)
        self.assertIn("minimumRelativeDopplerBoundHz", self.rain_doppler)
        self.assertIn("absoluteRelativeDopplerCeilingHz", self.rain_doppler)

    def test_rain_calls_standalone_but_defaults_to_preflight(self) -> None:
        self.assertIn("run_rain_sage_stage1_stage4(", self.rain_entry)
        self.assertNotIn("run_sage_stage1_stage4_core(", self.rain_entry)
        self.assertNotIn('"core"', self.rain_entry)
        self.assertIn('addParameter(parser, "PreflightOnly", true', self.rain_entry)
        self.assertIn('addParameter(parser, "Resume", false', self.rain_entry)
        self.assertIn("RAIN_STAGE1_STAGE4_COMPLETED", self.rain_entry)

    def test_rain_namespace_isolated(self) -> None:
        self.assertIn('"rain_sage_v1"', self.rain_entry)
        self.assertNotIn("nav_sage_v2", self.rain_entry)
        self.assertIn("standalone_rain_branch_local", self.rain_stage0)

    def test_standalone_numerical_body_matches_extracted_source(self) -> None:
        marker = "assert(isfolder(outputDir)"
        self.assertIn(marker, self.core)
        self.assertIn(marker, self.rain_standalone)
        core_body = self.core[self.core.index(marker):]
        rain_body = self.rain_standalone[self.rain_standalone.index(marker):]
        self.assertEqual(core_body.rstrip(), rain_body.rstrip())
        self.assertNotIn("run_sage_stage1_stage4_core", self.rain_standalone)

    def test_standalone_contains_all_stage_boundaries(self) -> None:
        for name in (
            "runFastScan",
            "runStage2",
            "flattenStage2",
            "evaluatePersistence",
            "runJointStage",
            "loadNavWipedFortyMs",
            "loadNavWipedTwentyMs",
        ):
            self.assertIn(name, self.rain_standalone)

    def test_rain_sources_have_no_shared_core_dependency(self) -> None:
        for source in (self.rain_entry, self.rain_stage0, self.rain_standalone):
            self.assertNotIn("run_sage_stage1_stage4_core", source)
            self.assertNotIn("default_sage_configuration", source)
            self.assertNotIn("compute_sage_doppler_bound", source)
        self.assertIn("default_rain_sage_configuration", self.rain_stage0)
        self.assertIn("compute_rain_doppler_bound", self.rain_stage0)

    def test_matlab_syntax_smoke_is_parse_only(self) -> None:
        smoke = SYNTAX_SMOKE.read_text(encoding="utf-8")
        for name in (
            "run_sage_stage1_stage4_core.m",
            "default_sage_configuration.m",
            "compute_sage_doppler_bound.m",
            "run_shared_core_regression.m",
            "run_rain_sage_pipeline.m",
            "build_rain_stage0.m",
        ):
            self.assertIn(name, smoke)
        self.assertIn("checkcode", smoke)
        self.assertIn('"raw_iq_opened", false', smoke)
        self.assertIn('"sage_executed", false', smoke)
        self.assertNotIn("run_sage_stage1_stage4_core(", smoke)
        self.assertIn("diagnostic_count", smoke)
        self.assertIn("DIAGNOSTIC file=", smoke)

    def test_rain_matlab_syntax_smoke_is_rain_only(self) -> None:
        smoke = SYNTAX_SMOKE.read_text(encoding="utf-8")
        for name in (
            "run_rain_sage_pipeline.m",
            "build_rain_stage0.m",
            "run_rain_sage_stage1_stage4.m",
            "default_rain_sage_configuration.m",
            "compute_rain_doppler_bound.m",
        ):
            self.assertIn(name, smoke)
        self.assertIn('"Scope", "rain"', self.rain_smoke)
        self.assertNotIn("run_sage_stage1_stage4_core", self.rain_smoke)


if __name__ == "__main__":
    unittest.main()
