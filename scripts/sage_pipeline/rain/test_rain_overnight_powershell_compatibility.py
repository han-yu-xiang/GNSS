import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "run_all_rain_sage_overnight.ps1"


class RainOvernightPowerShellCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = RUNNER.read_text(encoding="utf-8")
        cls.active_source = "\n".join(line.split("#", 1)[0] for line in cls.source.splitlines())

    def test_new_item_uses_windows_powershell_51_supported_path(self) -> None:
        for raw_line in self.source.splitlines():
            line = raw_line.split("#", 1)[0]
            if re.search(r"\bNew-Item\b", line):
                self.assertNotIn("-LiteralPath", line)
                self.assertRegex(line, r"-Path\s+")

    def test_literal_path_usage_is_limited_to_verified_cmdlets(self) -> None:
        supported = ("Test-Path", "Get-Content", "Add-Content", "Get-FileHash", "Import-Csv")
        for raw_line in self.source.splitlines():
            line = raw_line.split("#", 1)[0]
            if "-LiteralPath" in line:
                self.assertTrue(
                    any(re.search(r"\b" + re.escape(cmdlet) + r"\b", line) for cmdlet in supported),
                    msg=f"Unverified LiteralPath use: {raw_line}",
                )

    def test_process_invocation_uses_legacy_arguments_property(self) -> None:
        self.assertIn("$info.Arguments =", self.active_source)
        self.assertNotIn("ArgumentList", self.active_source)

    def test_no_known_powershell_7_only_syntax(self) -> None:
        for pattern in (r"\?\?", r"\?\.", r"ForEach-Object\s+-Parallel", r"\$PSStyle", r"ErrorView"):
            self.assertIsNone(re.search(pattern, self.active_source, flags=re.IGNORECASE), pattern)
        self.assertNotRegex(self.active_source, r"\$\([^)]*\?[^)]*:")

    def test_dry_run_and_failure_diagnostics_are_present(self) -> None:
        self.assertRegex(self.source, r"param\(\s*\[switch\]\$DryRun")
        for marker in (
            "OVERNIGHT_RUNNER_DRY_RUN=PASS",
            "MATLAB_STARTED=NO",
            "RAW_IQ_OPENED=NO",
            "SAGE_EXECUTED=NO",
            "OUTPUT_SAGE_CREATED=NO",
            "ERROR_MESSAGE",
            "ERROR_COMMAND",
            "ERROR_POSITION",
            "ERROR_LINE",
            "ERROR_SCRIPT_STACK_TRACE",
            "FULLY_QUALIFIED_ERROR_ID",
            "POWERSHELL_VERSION",
            "exit $script:ExitCode",
        ):
            self.assertIn(marker, self.source)

    def test_dry_run_does_not_call_matlab_or_create_run_directory(self) -> None:
        dry_run_index = self.source.index("if ($DryRun)")
        init_index = self.source.index("$script:RunDir = New-UniqueRunDirectory")
        launch_index = self.source.index("$processResult = Invoke-MatlabBatch")
        self.assertLess(init_index, dry_run_index)
        self.assertLess(dry_run_index, launch_index)
        self.assertIn("New-MatlabExpression", self.source[dry_run_index:launch_index])
        self.assertIn("dry_run_plan.json", self.source)

    def test_formal_initialization_fixes_and_diagnostics_self_test_are_present(self) -> None:
        self.assertNotRegex(self.active_source, r"(?<![A-Za-z.])\$NewLine\b")
        self.assertIn("[Environment]::NewLine", self.active_source)
        self.assertIn("Test-ErrorDiagnosticsSafe", self.active_source)
        self.assertIn("Test-ProcessCaptureSafe", self.active_source)
        self.assertIn("Invoke-CapturedProcess", self.active_source)
        self.assertIn("Assert-NormalUserExecutionIdentity", self.active_source)
        self.assertIn("codexsandboxoffline", self.active_source)
        self.assertIn("WindowsBuiltInRole]::Administrator", self.active_source)
        self.assertIn("[AllowEmptyString()][AllowNull()][string]$Text", self.active_source)
        self.assertIn("ERROR_DIAGNOSTICS_NEVER_THROWS=PASS", self.active_source)
        self.assertIn("TASK_OUTPUT_CAPTURE_NEVER_THROWS=PASS", self.active_source)
        self.assertIn("FORMAL_PATH_RUNTIME_CHECK=PASS", self.active_source)
        for sample in ("format token {0} and empty braces {}", "中文错误文本", "multi-line", "percent 100%"):
            self.assertIn(sample, self.source)

    def test_summary_outputs_are_scoped_to_unique_run_namespace(self) -> None:
        self.assertIn("$summaryDirectory = Join-Path $script:RunDir", self.source)
        self.assertNotIn("Join-Path $MonitorRoot \"rain_sage_execution_qa_20260818.csv\"", self.source)
        self.assertNotIn("Join-Path $MonitorRoot \"RAIN_SAGE_QA_REPORT_20260818.md\"", self.source)

    def test_write_line_calls_use_completed_single_string_arguments(self) -> None:
        for raw_line in self.source.splitlines():
            line = raw_line.split("#", 1)[0]
            if ".WriteLine(" in line:
                self.assertNotIn("-replace", line)
                self.assertNotRegex(line, r"WriteLine\([^)]*\,[^)]*\)")


if __name__ == "__main__":
    unittest.main()
