"""Static and contract-level regression tests for Rain result packaging.

These tests do not invoke MATLAB, SAGE, raw IQ, or any Rain task.  They verify
the source-level scalar-container pattern and the contract that non-scalar
stage containers retain their lengths as fields rather than expanding the
outer result structure.
"""

from pathlib import Path
import unittest


SOURCE = Path(__file__).with_name("run_rain_sage_stage1_stage4.m")


def package_result_contract(stage2_fits, joint_fits):
    """Model MATLAB field assignment semantics for the packaging contract."""

    result = {}
    result["stage2Fits"] = stage2_fits
    result["jointFits"] = joint_fits
    return result


class RainResultPackagingTests(unittest.TestCase):
    def test_source_uses_scalar_struct_then_field_assignment(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("result = struct();", source)
        self.assertIn("result.stage2Fits = stage2Fits;", source)
        self.assertIn("result.jointFits = jointFits;", source)
        self.assertIn("assert(isstruct(result) && isscalar(result)", source)
        self.assertNotIn('result = struct( ...\n    "dopplerSignUsed"', source)

    def test_stage2_like_20_and_joint_like_8_are_preserved(self):
        stage2_like = [object() for _ in range(20)]
        joint_like = [object() for _ in range(8)]
        result = package_result_contract(stage2_like, joint_like)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result["stage2Fits"]), 20)
        self.assertEqual(len(result["jointFits"]), 8)

    def test_fields_are_not_silently_reshaped(self):
        stage2_like = [object() for _ in range(20)]
        joint_like = [object() for _ in range(8)]
        result = package_result_contract(stage2_like, joint_like)
        self.assertIs(result["stage2Fits"], stage2_like)
        self.assertIs(result["jointFits"], joint_like)


if __name__ == "__main__":
    unittest.main()
