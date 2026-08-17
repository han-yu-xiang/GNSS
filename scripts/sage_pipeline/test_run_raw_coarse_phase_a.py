import copy
import json
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
REQUEST_ROOT = PROJECT_ROOT / "dataset_generation_logs" / "sampling_validation" / "batch_sampled_v1_2_phase_a_execution_requests_20260812"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_raw_coarse_phase_a as executor  # noqa: E402


G16_MANIFEST = REQUEST_ROOT / "phase_a1_g16_20260812" / "execution_manifest.json"
G25_MANIFEST = REQUEST_ROOT / "phase_a2_g25_20260812" / "execution_manifest.json"
G16_SHA256 = "bca6c592f3d107841f5b2e9459f48cfacb777cfc8cc28c779a91a0be4e70920c"
G25_SHA256 = "d72a5edafc4691333aa9f048386e673c4188acc70c25fdff4608a582ff4fd907"


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class PhaseAExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g16 = load_manifest(G16_MANIFEST)
        cls.g25 = load_manifest(G25_MANIFEST)

    def test_g16_manifest_sha_is_frozen(self):
        self.assertEqual(executor.sha256_file(G16_MANIFEST), G16_SHA256)

    def test_g25_manifest_sha_is_frozen(self):
        self.assertEqual(executor.sha256_file(G25_MANIFEST), G25_SHA256)

    def test_g16_validation_is_execution_eligible(self):
        result = executor.validate_manifest(G16_MANIFEST, G16_SHA256)
        self.assertFalse(result.execution_eligible)
        self.assertTrue(any("new_only" in error for error in result.errors), result.errors)
        self.assertEqual(result.task["prn"], "G16")
        self.assertTrue(result.evaluator_api_available)

    def test_retry_identity_requires_fresh_run_fields(self):
        manifest = copy.deepcopy(self.g16)
        manifest["request_id"] = executor.G16_RETRY_REQUEST_ID
        manifest["phase_id"] = "Phase-A1-Retry1"
        manifest["fresh_run_only"] = True
        manifest["resume_allowed"] = False
        manifest["supersedes_interrupted_manifest"] = executor.G16_REQUEST_ID
        manifest["previous_interruption_receipt"] = str(PROJECT_ROOT / "interrupted-receipt.json")
        errors = executor.manifest_task_errors(manifest)
        self.assertEqual(errors, [])

    def test_retry_identity_rejects_resume(self):
        manifest = copy.deepcopy(self.g16)
        manifest["request_id"] = executor.G16_RETRY_REQUEST_ID
        manifest["phase_id"] = "Phase-A1-Retry1"
        manifest["fresh_run_only"] = True
        manifest["resume_allowed"] = True
        manifest["supersedes_interrupted_manifest"] = executor.G16_REQUEST_ID
        manifest["previous_interruption_receipt"] = str(PROJECT_ROOT / "interrupted-receipt.json")
        errors = executor.manifest_task_errors(manifest)
        self.assertTrue(any("resume_allowed" in error for error in errors))

    def test_interrupt_handler_records_signal_provenance(self):
        executor._INTERRUPT_PROVENANCE.update({"signal_number": None, "signal_name": None, "received_at_utc": None})
        with self.assertRaises(KeyboardInterrupt):
            executor._record_interrupt_signal(2, None)
        self.assertEqual(executor._INTERRUPT_PROVENANCE["signal_name"], "SIGINT")
        self.assertIsNotNone(executor._INTERRUPT_PROVENANCE["received_at_utc"])

    def test_g25_validation_is_blocked_until_g16_qa(self):
        result = executor.validate_manifest(G25_MANIFEST, G25_SHA256)
        self.assertFalse(result.execution_eligible)
        self.assertTrue(any("G25 execution gate" in error for error in result.errors))

    def test_wrong_sha_rejected_before_json_use(self):
        with self.assertRaises(executor.ExecutorRejected):
            executor.read_manifest_and_verify_hash(G16_MANIFEST, "0" * 64)

    def test_tampered_manifest_bytes_fail_expected_hash(self):
        original = G16_MANIFEST.read_bytes()
        tampered_path = PROJECT_ROOT / "dataset_generation_logs" / "sampling_validation" / "_test_tampered_phase_a_manifest.json"
        try:
            tampered_path.write_bytes(original + b"\n")
            with self.assertRaises(executor.ExecutorRejected):
                executor.read_manifest_and_verify_hash(tampered_path, G16_SHA256)
        finally:
            tampered_path.unlink(missing_ok=True)

    def test_wrong_channel_is_rejected(self):
        manifest = copy.deepcopy(self.g16)
        manifest["task"]["tracking_channel"] = 0
        errors = executor.manifest_task_errors(manifest)
        self.assertTrue(any("tracking_channel" in error for error in errors))

    def test_20mhz_is_rejected(self):
        manifest = copy.deepcopy(self.g16)
        manifest["task"]["sample_rate_hz"] = 20_460_000
        errors = executor.manifest_task_errors(manifest)
        self.assertTrue(any("sample_rate_hz" in error for error in errors))

    def test_g11_request_is_rejected(self):
        manifest = copy.deepcopy(self.g16)
        manifest["request_id"] = "phase_b_g11_20260812"
        manifest["task"]["scene_id"] = "F1023_V120_D0121_P2"
        manifest["task"]["prn"] = "G11"
        errors = executor.manifest_task_errors(manifest)
        self.assertTrue(any("G11" in error or "allowed Phase-A" in error for error in errors))

    def test_existing_or_wrong_namespace_is_rejected(self):
        manifest = copy.deepcopy(self.g16)
        manifest["output"]["namespace"] = str(PROJECT_ROOT / "scenes" / "F1023_V70_D0117_P2" / "sage_results" / "G06_nav_sage_v1")
        errors = []
        executor.validate_output_namespace(manifest, PROJECT_ROOT, errors)
        self.assertTrue(any("outside" in error or "sage_results" in error or "exists" in error for error in errors))

    def test_wrong_python_path_is_rejected(self):
        manifest = copy.deepcopy(self.g16)
        manifest["runtime"]["python_executable"] = r"C:\Python312\python.exe"
        errors = []
        backend = executor.read_candidate_backend(PROJECT_ROOT, manifest, errors)
        self.assertFalse(backend.get("available", False))
        self.assertTrue(any("Python executable" in error for error in errors))

    def test_parameter_hash_change_is_rejected(self):
        manifest = copy.deepcopy(self.g16)
        manifest["prototype"]["parameter_sha256"] = "0" * 64
        errors = executor.manifest_task_errors(manifest)
        self.assertTrue(any("parameter_sha256" in error for error in errors))

    def test_missing_input_is_rejected(self):
        errors = []
        executor.check_file_receipt(errors, "missing Stage0", {}, PROJECT_ROOT / "does_not_exist.csv", hash_content=True)
        self.assertTrue(any("missing" in error or "does not exist" in error for error in errors))

    def test_output_root_boundary_is_strict(self):
        valid = PROJECT_ROOT / "dataset_generation_logs" / "sampling_validation" / executor.EXPECTED_OUTPUT_ROOT_NAME / "task"
        evil = PROJECT_ROOT.parent / (PROJECT_ROOT.name + "_Evil") / "dataset_generation_logs" / "sampling_validation" / executor.EXPECTED_OUTPUT_ROOT_NAME / "task"
        self.assertTrue(executor.is_within(valid, PROJECT_ROOT / "dataset_generation_logs" / "sampling_validation" / executor.EXPECTED_OUTPUT_ROOT_NAME))
        self.assertFalse(executor.is_within(evil, PROJECT_ROOT))

    def test_g25_qa_receipt_is_not_synthesized(self):
        passed, reason = executor.check_g16_qa_receipt(PROJECT_ROOT, G16_SHA256)
        self.assertFalse(passed)
        self.assertIn("missing", reason)

    def test_execute_requires_human_confirmation(self):
        result = executor.validate_manifest(G16_MANIFEST, G16_SHA256)
        with self.assertRaises(executor.ExecutorRejected):
            executor.execute(result, confirm_phase_a=False)

    def test_dry_run_exposes_adapter_but_does_not_execute(self):
        result = executor.validate_manifest(G16_MANIFEST, G16_SHA256)
        self.assertTrue(result.evaluator_api_available)
        self.assertFalse(result.execute_dispatch_available)
        self.assertTrue(any("new_only" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
