"""MATLAB-free guards for Rain Stage4 phase/amplitude export semantics."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
RAIN_STAGE = ROOT / "scripts" / "sage_pipeline" / "rain" / "run_rain_sage_stage1_stage4.m"
PRODUCTION = ROOT / "scripts" / "sage_pipeline" / "run_nav_sage_pipeline.m"


class RainPhaseExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = RAIN_STAGE.read_text(encoding="utf-8")

    def test_export_is_in_rain_local_stage4_only(self) -> None:
        self.assertIn("function [phaseRad, relativePhaseRad", self.text)
        self.assertIn('"phase_source", "joint_selected_path_alpha"', self.text)
        self.assertNotIn("run_nav_sage_pipeline", self.text)

    def test_required_output_fields_are_present(self) -> None:
        for field in (
            '"phase_rad"',
            '"relative_phase_rad"',
            '"relative_phase_available"',
            '"relative_amplitude"',
            '"relative_amplitude_db"',
        ):
            self.assertIn(field, self.text)

    def test_relative_values_use_complex_alpha_ratio(self) -> None:
        self.assertIn("ratio = pathAlpha / referenceAlpha;", self.text)
        self.assertIn("relativeAmplitude = abs(ratio);", self.text)
        self.assertIn("relativePhaseRad = wrapPhaseHalfOpen(angle(ratio));", self.text)
        self.assertIn("relativeAmplitudeDb = 20 * log10", self.text)

    def test_phase_is_normalized_half_open(self) -> None:
        self.assertIn("function value = wrapPhaseHalfOpen(value)", self.text)
        self.assertIn("mod(value + pi, 2 * pi) - pi", self.text)

    def test_missing_or_invalid_alpha_is_not_zero_filled(self) -> None:
        self.assertIn("phaseRad = nan;", self.text)
        self.assertIn("relativePhaseAvailable = false;", self.text)
        self.assertIn("relativeAmplitude = nan;", self.text)
        self.assertIn("relativeAmplitudeDb = nan;", self.text)

    def test_production_entry_is_not_modified_by_phase_export(self) -> None:
        self.assertNotIn("pathComplexMetrics", PRODUCTION.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
