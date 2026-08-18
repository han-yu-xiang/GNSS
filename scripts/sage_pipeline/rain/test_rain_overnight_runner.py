import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "run_all_rain_sage_overnight.ps1"


class RainOvernightRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = RUNNER.read_text(encoding="utf-8")

    def test_task_order_is_frozen(self) -> None:
        expected = [
            'Scene = "F1023_clear"; PRN = "G24"; Channel = 10',
            'Scene = "F1023_clear"; PRN = "G29"; Channel = 3',
            'Scene = "F1023_clear"; PRN = "G13"; Channel = 8',
            'Scene = "F1023_clear"; PRN = "G12"; Channel = 11',
            'Scene = "F1023_midrain"; PRN = "G24"; Channel = 8',
            'Scene = "F1023_midrain"; PRN = "G20"; Channel = 9',
            'Scene = "F1023_heavyrain"; PRN = "G02"; Channel = 1',
            'Scene = "F1023_heavyrain"; PRN = "G31"; Channel = 4',
            'Scene = "F1023_heavyrain"; PRN = "G01"; Channel = 7',
        ]
        positions = [self.source.index(item) for item in expected]
        self.assertEqual(positions, sorted(positions))

    def test_only_rain_namespace_and_no_resume(self) -> None:
        self.assertIn('"rain_sage_v1"', self.source)
        self.assertNotIn('"sage_results\\nav_sage_v2"', self.source)
        self.assertIn("'Resume',false", self.source)
        self.assertNotIn("'Resume',true", self.source)
        self.assertIn("SERIAL", self.source)

    def test_g24_is_global_gate(self) -> None:
        self.assertIn("if ($task.Sequence -eq 1)", self.source)
        self.assertIn("GLOBAL_STOP: Clear G24", self.source)
        self.assertIn("PASS_WITH_CONFIRMED_MULTIPATH", self.source)
        self.assertIn("PASS_NO_CONFIRMED_MULTIPATH", self.source)

    def test_runner_does_not_modify_source_or_call_production(self) -> None:
        self.assertNotIn("run_nav_sage_pipeline(", self.source)
        self.assertNotIn("Set-Content", self.source)
        self.assertNotIn("Out-File", self.source)
        self.assertNotIn("Start-Job", self.source)
        self.assertNotIn("ForEach-Object -Parallel", self.source)

    def test_runner_has_no_delete_or_cleanup_command(self) -> None:
        forbidden = (
            "Remove-Item", "rm -", "rm -rf", "del ", "erase ", "rmdir",
            "git clean", "git rm", "reset --hard", "Path.unlink", "unlink(",
        )
        for token in forbidden:
            self.assertNotIn(token.lower(), self.source.lower())

    def test_required_provenance_and_reports_are_present(self) -> None:
        for marker in (
            "PRODUCTION_SHA_BEFORE",
            "PRODUCTION_SHA_AFTER",
            "rain_sage_execution_qa_20260818.csv",
            "rain_sage_darkroom_parameters_v1.csv",
            "RAIN_SAGE_QA_REPORT_20260818.md",
            "TOMORROW_MEETING_RAIN_SAGE_RESULTS.md",
            "raw_iq_opened_by_runner",
            "gold_labels_used",
        ):
            self.assertIn(marker, self.source)

    def test_named_mutex_serializes_runner_without_file_cleanup(self) -> None:
        self.assertIn("System.Threading.Mutex", self.source)
        self.assertIn("WaitOne(0)", self.source)
        self.assertIn("ReleaseMutex()", self.source)
        self.assertNotIn("rain_sage_overnight.lock", self.source)

    def test_runner_uses_robust_interface_validator(self) -> None:
        self.assertIn("validate_rain_interface.ps1", self.source)
        self.assertIn("Test-RainInterfaceSource", self.source)
        self.assertIn("run_rain_sage_stage1_stage4.m", self.source)
        self.assertNotIn('"run_rain_sage_stage1_stage4"', self.source)


if __name__ == "__main__":
    unittest.main()
