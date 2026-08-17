import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "scripts" / "sage_pipeline" / "regression" / "run_shared_core_regression.m"
BASELINE_METADATA = ROOT / "scenes" / "F1023_V70_D0117_P2" / "metadata.json"


class SharedCoreRegressionHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = HARNESS.read_text(encoding="utf-8")

    def test_fixed_baseline_and_channel(self):
        self.assertIn('sceneId = "F1023_V70_D0117_P2";', self.text)
        self.assertIn('prnLabel = "G28";', self.text)
        self.assertIn("trackingChannel = 1;", self.text)
        self.assertNotIn('"G06_nav_sage_v1"', self.text)

    def test_only_shared_core_is_invoked(self):
        self.assertIn("run_sage_stage1_stage4_core(", self.text)
        self.assertNotIn("run_nav_sage_pipeline(", self.text)
        self.assertNotIn("run_rain_sage_pipeline(", self.text)

    def test_new_only_namespace_and_resume_false(self):
        self.assertIn('"execution_mode", "new_only"', self.text)
        self.assertIn('"resume", false', self.text)
        self.assertIn("cfg.resumeExistingStages = false;", self.text)
        self.assertIn("~isfolder(regressionRoot) && ~isfile(regressionRoot)", self.text)
        self.assertNotIn("rmdir(", self.text)
        self.assertNotIn("delete(", self.text)

    def test_namespace_is_outside_sage_results(self):
        self.assertIn("darkroom_channel_emulation", self.text)
        self.assertIn('contains(lower(char(regressionRoot)), "sage_results")', self.text)

    def test_required_identity_and_numeric_fields_are_compared(self):
        for marker in (
            '"stage1_candidate_identity"',
            '"stage2_evaluated_identity"',
            '"stage3_reliable_center_identity"',
            '"stage4_event_identity"',
            '"confirmed_event_identity"',
            '"confirmed_path_identity"',
            '"joint_valid"',
            '"is_multipath"',
            "max_abs_error",
            "max_rel_error",
        ):
            self.assertIn(marker, self.text)

    def test_all_harness_json_inputs_use_bom_safe_reader(self):
        self.assertIn("context = readJsonWithBom(runContextFile);", self.text)
        self.assertIn("metadata = readJsonWithBom(metadataFile);", self.text)
        self.assertNotIn("jsondecode(fileread(", self.text)
        self.assertEqual(self.text.count("jsondecode("), 1)

    def test_reader_supports_required_encodings_and_fail_closed_cases(self):
        for marker in (
            'encoding = "UTF-8"',
            'encoding = "UTF-16LE"',
            'encoding = "UTF-16BE"',
            "uint8([239; 187; 191])",
            "uint8([255; 254])",
            "uint8([254; 255])",
            "JSON input is empty",
            "JSON input contains only a BOM",
            "JSON input is blank",
            "JSON decoding failed",
            "Invalid JSON",
        ):
            self.assertIn(marker, self.text)

    def test_reader_does_not_delete_or_substitute_source_characters(self):
        self.assertNotIn("erase(", self.text)
        self.assertNotIn("strrep(", self.text)

    def test_baseline_metadata_sha_and_utf8_bom_are_unchanged(self):
        payload = BASELINE_METADATA.read_bytes()
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "960ecd47b390dc8a74dce989a782cbacc9552d680fb6bd5d8dc470b24ee7aa5b",
        )
        self.assertEqual(payload[:3], b"\xef\xbb\xbf")
        self.assertEqual(payload[3:4], b"{")


if __name__ == "__main__":
    unittest.main()
