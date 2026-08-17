"""Read-only tests for the v3 G16 task-manifest preparation gate."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_raw_coarse_v3_g16_task_manifest as generator  # noqa: E402


class G16V3ManifestTests(unittest.TestCase):
    def test_semantic_audit_confirms_secondary_and_block_mapping(self):
        result = generator.audit_secondary_doppler_semantics(PROJECT_ROOT)
        self.assertTrue(result["pass"])
        self.assertTrue(result["checks"]["secondary_uses_selected_delay_index"])
        self.assertTrue(result["checks"]["b1_groups_exact"])
        self.assertTrue(result["checks"]["b2_groups_exact"])
        self.assertTrue(result["checks"]["nav_0_1_symbol_1"])
        self.assertTrue(result["checks"]["nav_2_3_symbol_2"])

    def test_current_manifest_is_immutable_and_gold_free(self):
        path = PROJECT_ROOT / "dataset_generation_logs/sampling_validation/batch_sampled_v1_3_g16_evidence_task_requests_20260812_r1/g16_v3_evidence_capture_20260812_r1/execution_manifest.json"
        digest = generator.sha256_file(path)
        sidecar = (path.parent / "execution_manifest.sha256").read_text(encoding="ascii").strip()
        self.assertEqual(digest, sidecar)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(manifest["immutable_after_creation"])
        self.assertFalse(manifest["gold_labels_used_for_selection"])
        self.assertEqual(manifest["parameter_sha256"], generator.EXPECTED_PARAMETER_SHA256)
        self.assertEqual(manifest["v2_kernel"]["sha256"], generator.EXPECTED_V2_KERNEL_SHA256)
        self.assertTrue(Path(manifest["output"]["namespace"]).name.startswith("batch_sampled_v1_3_"))
        self.assertNotIn("sage_results", Path(manifest["output"]["namespace"]).parts)
        serialized = json.dumps(manifest, ensure_ascii=True).lower()
        self.assertNotIn("stage3", serialized)
        self.assertNotIn("stage4", serialized)
        self.assertNotIn("gold_event", serialized)

    def test_preflight_uses_raw_stat_without_hashing_raw_content(self):
        original = generator.sha256_file
        raw_path = generator.resolved(
            generator.load_json(
                PROJECT_ROOT / "scenes/F1023_V70_D0120_P7/metadata.json", "metadata"
            )["raw_iq"]["path"]
        )

        def guarded(path: Path) -> str:
            if generator.resolved(path) == raw_path:
                raise AssertionError("preflight attempted to hash the prohibited full raw file")
            return original(path)

        generator.sha256_file = guarded
        try:
            result, _audit = generator.build_preflight(
                PROJECT_ROOT,
                PROJECT_ROOT / generator.DEFAULT_PARAMETER_MANIFEST,
                PROJECT_ROOT / generator.DEFAULT_OLD_MANIFEST,
                PROJECT_ROOT / generator.DEFAULT_ENVIRONMENT_RECEIPT,
                PROJECT_ROOT / "dataset_generation_logs/sampling_validation/batch_sampled_v1_3_manifest_test_probe",
            )
        finally:
            generator.sha256_file = original
        self.assertFalse(result["preflight"]["raw_content_hash_revalidated_this_preflight"])
        self.assertTrue(result["preflight"]["raw_content_hash_revalidation_deferred_by_no_full_raw_guard"])

    def test_preflight_rejects_existing_output_namespace(self):
        existing = PROJECT_ROOT / "dataset_generation_logs/sampling_validation/batch_sampled_v1_3_evidence_capture_fixture_20260812"
        with self.assertRaises(FileExistsError):
            generator.build_preflight(
                PROJECT_ROOT,
                PROJECT_ROOT / generator.DEFAULT_PARAMETER_MANIFEST,
                PROJECT_ROOT / generator.DEFAULT_OLD_MANIFEST,
                PROJECT_ROOT / generator.DEFAULT_ENVIRONMENT_RECEIPT,
                existing,
            )


if __name__ == "__main__":
    unittest.main()
