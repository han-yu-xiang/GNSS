"""Synthetic runner contracts; no science input or production path is touched."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_mainline_stage2_wp3 import (
    _m1_parameter_contrasts, _package_analysis_log,
    create_new_output_dir, verify_pinned_input,
)


class WP3RunnerTests(unittest.TestCase):
    def test_input_pin_checks_content_not_just_path_or_timestamp(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.csv"
            path.write_bytes(b"synthetic,fixture\n1,2\n")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(verify_pinned_input(path, expected)["sha256"], expected)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                verify_pinned_input(path, "0" * 64)

    def test_output_directory_is_new_and_never_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            output = parent / "wp3_result"
            self.assertEqual(create_new_output_dir(output, parent), output)
            (output / "preserve.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "refusing to reuse"):
                create_new_output_dir(output, parent)
            self.assertEqual((output / "preserve.txt").read_text(encoding="utf-8"), "keep")

    def test_analysis_console_log_is_copied_and_hashable_in_isolated_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "console.log"
            source.write_text("WP3_OUTPUT=synthetic\\nSTATUS=COMPLETED\\n", encoding="utf-8")
            output = root / "wp3_result"
            output.mkdir()
            record = _package_analysis_log(output, source)
            packaged = output / "analysis_execution.txt"
            self.assertEqual(packaged.read_bytes(), source.read_bytes())
            self.assertEqual(record["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(record["size_bytes"], source.stat().st_size)
            with self.assertRaisesRegex(FileExistsError, "refusing to overwrite"):
                _package_analysis_log(output, source)
            self.assertEqual(packaged.read_bytes(), source.read_bytes())

    def test_environment_parameter_ratio_is_only_reported_for_positive_parameters(self):
        parameters = pd.DataFrame([{
            "data_scope": "ALL_MPC", "model": "M1", "variable": "doppler_offset_hz",
            "family": "normal", "fit_status": "PASS", "failure_reason": "",
            "parameters_json": '{"by_environment":{"Urban":{"loc":-2.0,"scale":4.0},'
                                '"Mountain/Valley":{"loc":3.0,"scale":2.0}}}',
        }])
        contrasts = _m1_parameter_contrasts(parameters).set_index("parameter")
        self.assertTrue(pd.isna(contrasts.loc["loc", "urban_to_mountain_valley_ratio"]))
        self.assertEqual(contrasts.loc["loc", "urban_minus_mountain_valley"], -5.0)
        self.assertEqual(contrasts.loc["scale", "urban_to_mountain_valley_ratio"], 2.0)


if __name__ == "__main__":
    unittest.main()
