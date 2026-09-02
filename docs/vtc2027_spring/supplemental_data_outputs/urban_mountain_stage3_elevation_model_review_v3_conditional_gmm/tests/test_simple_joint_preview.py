from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SimpleJointPreviewTests(unittest.TestCase):
    def test_generator_writes_png_and_pdf_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/generate_simple_joint_preview.py"),
                    "--output-dir",
                    temporary_directory,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            try:
                summary = json.loads(result.stdout)
            except json.JSONDecodeError as error:
                self.fail(f"generator did not emit JSON summary: {error}\n{result.stdout}")
            self.assertEqual(summary["panel_count"], 2)
            self.assertEqual(summary["observation_count"], 518)
            self.assertEqual(summary["environments"], ["Urban", "Mountain/Valley"])
            for name in (
                "simple_joint_delay_power_preview.png",
                "simple_joint_delay_power_preview.pdf",
            ):
                output = Path(temporary_directory) / name
                self.assertTrue(output.exists(), msg=f"missing {name}")
                self.assertGreater(output.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
