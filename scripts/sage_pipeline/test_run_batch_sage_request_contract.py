"""No-MATLAB regression tests for the production request/executor contract."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
REQUEST_PATH = PROJECT_ROOT / (
    "dataset_generation_logs/batch_sage_execution_requests/"
    "production_10mhz_a3_d0120p5_g16_20260813/execution_request.json"
)
PLAN_PATH = PROJECT_ROOT / (
    "dataset_generation_logs/batch_sage_execution_requests/"
    "production_10mhz_a3_d0120p5_g16_20260813/approved_plan_snapshot.csv"
)
SELECTED_PATH = PROJECT_ROOT / (
    "dataset_generation_logs/batch_sage_execution_requests/"
    "production_10mhz_a3_d0120p5_g16_20260813/selected_tasks_snapshot.csv"
)
PRODUCTION_MANIFEST_PATH = PROJECT_ROOT / (
    "dataset_generation_logs/production_planning_10mhz_20260812/"
    "production_task_manifest_10MHz_v1.json"
)
PIPELINE_PATH = PROJECT_ROOT / "scripts/sage_pipeline/run_nav_sage_pipeline.m"
WRAPPER_PATH = PROJECT_ROOT / "scripts/sage_pipeline/Invoke-BatchSageWindows.ps1"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_batch_sage as executor  # noqa: E402


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_plan_row() -> dict[str, str]:
    _fields, rows = executor.read_csv(PLAN_PATH)
    assert len(rows) == 1
    return rows[0]


class ProductionRequestContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.request = load_json(REQUEST_PATH)
        cls.plan_row = load_plan_row()

    def test_valid_new_only_policy_is_strictly_false_resume(self) -> None:
        self.assertEqual(executor.validate_execution_request_policy(self.request), [])
        self.assertIs(self.request["new_only"], True)
        self.assertIs(self.request["resume_allowed"], False)

    def test_builder_emits_explicit_false_and_is_deterministic(self) -> None:
        kwargs = dict(
            pipeline_dir=PIPELINE_PATH.parent,
            scene_id="F1023_V70_D0120_P5",
            prn="G16",
            tracking_channel=1,
            project_root=PROJECT_ROOT,
        )
        dry_preview = executor.build_matlab_expression(**kwargs, resume=False)
        execute_expression = executor.build_matlab_expression(**kwargs, resume=False)
        self.assertEqual(dry_preview, execute_expression)
        self.assertIn("'Resume', false", dry_preview)
        self.assertNotIn("'Resume', true", dry_preview)

    def test_valid_request_is_reloaded_with_current_source_hashes(self) -> None:
        request = copy.deepcopy(self.request)
        request["pipeline_sha256"] = executor.sha256_file(PIPELINE_PATH)
        request["python_executor_sha256"] = executor.sha256_file(Path(executor.__file__))
        request["wrapper_sha256"] = executor.sha256_file(WRAPPER_PATH)
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            manifest_path = Path(temp_dir) / "execution_request.json"
            manifest_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
            actual_sha = executor.sha256_file(manifest_path)
            loaded = executor.load_execution_request(
                manifest_path,
                str(actual_sha),
                PROJECT_ROOT,
                PLAN_PATH,
                SELECTED_PATH,
                PIPELINE_PATH,
            )
        self.assertEqual(loaded["request_id"], self.request["request_id"])

    def test_tampered_request_is_rejected_before_json_use(self) -> None:
        original_sha = "0" * 64
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            manifest_path = Path(temp_dir) / "tampered_request.json"
            manifest_path.write_bytes(REQUEST_PATH.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                executor.load_execution_request(
                    manifest_path,
                    original_sha,
                    PROJECT_ROOT,
                    PLAN_PATH,
                    SELECTED_PATH,
                    PIPELINE_PATH,
                )

    def test_resume_allowed_true_is_fail_closed(self) -> None:
        request = copy.deepcopy(self.request)
        request["resume_allowed"] = True
        errors = executor.validate_execution_request_policy(request)
        self.assertIn("request_resume_allowed_must_be_false", errors)

    def test_new_only_false_is_fail_closed(self) -> None:
        request = copy.deepcopy(self.request)
        request["new_only"] = False
        errors = executor.validate_execution_request_policy(request)
        self.assertIn("request_new_only_must_be_true", errors)

    def test_existing_output_is_rejected_by_executor_gate(self) -> None:
        errors = executor.validate_selected_task(
            self.plan_row,
            PROJECT_ROOT,
            PIPELINE_PATH,
            request=self.request,
        )
        self.assertIn("existing_output_directory_or_file", errors)

    def test_request_scope_channel_mismatch_is_rejected(self) -> None:
        request = copy.deepcopy(self.request)
        request["tracking_channel"] = 0
        errors = executor.validate_request_scope(
            request,
            [self.plan_row],
            [],
            PRODUCTION_MANIFEST_PATH,
        )
        self.assertIn("request_tracking_channel_scope_mismatch", errors)

    def test_request_scope_sample_rate_mismatch_is_rejected(self) -> None:
        request = copy.deepcopy(self.request)
        request["sample_rate_hz"] = 20_460_000
        errors = executor.validate_request_scope(
            request,
            [self.plan_row],
            [],
            PRODUCTION_MANIFEST_PATH,
        )
        self.assertIn("request_sample_rate_scope_mismatch", errors)

    def test_request_scope_task_order_mismatch_is_rejected(self) -> None:
        request = copy.deepcopy(self.request)
        request["ordered_task_ids"] = ["not-the-selected-task"]
        errors = executor.validate_request_scope(
            request,
            [self.plan_row],
            [],
            PRODUCTION_MANIFEST_PATH,
        )
        self.assertIn("request_task_order_or_scope_mismatch", errors)

    def test_execute_requires_request_manifest(self) -> None:
        with self.assertRaises(ValueError):
            executor.main(
                [
                    "--project-root",
                    str(PROJECT_ROOT),
                    "--plan",
                    str(PLAN_PATH),
                    "--selected-tasks",
                    str(SELECTED_PATH),
                    "--execute",
                ]
            )

    def test_dry_run_uses_same_explicit_false_command_builder(self) -> None:
        production_manifest = load_json(PRODUCTION_MANIFEST_PATH)
        production_task = next(
            task for task in production_manifest["tasks"]
            if task.get("scene_id") == "F1023_V70_D0120_P5" and task.get("PRN") == "G23"
        )
        scene_id = production_task["scene_id"]
        prn = production_task["PRN"]
        channel = int(production_task["tracking_channel"])
        task_id = f"{scene_id}__{prn}__ch{channel}__nav_sage_v2"
        scene_root = PROJECT_ROOT / "scenes" / scene_id
        geometry_outputs = production_task["satellite_geometry_provenance"]["outputs"]
        row = {
            "task_id": task_id,
            "scene_id": scene_id,
            "scene_role": "standard_scene",
            "prn": prn,
            "tracking_channel": str(channel),
            "output_path": production_task["expected_output_namespace"],
            "status": "ready",
            "execution_allowed": "true",
            "requires_manual_channel_selection": "false",
            "pipeline_sha256": executor.sha256_file(PIPELINE_PATH),
            "hard_gate_failures": "",
            "raw_path": production_task["raw_provenance"]["path"],
            "tracking_path": production_task["gnss_sdr_provenance"]["tracking_file"],
            "telemetry_path": production_task["gnss_sdr_provenance"]["telemetry_file"],
            "navigation_path": production_task["navigation_provenance"]["path"],
            "trajectory_path": production_task["trajectory_provenance"]["path"],
            "satellite_timeseries_path": str(PROJECT_ROOT / "scenes" / scene_id / geometry_outputs[0]),
            "satellite_summary_path": str(PROJECT_ROOT / "scenes" / scene_id / geometry_outputs[1]),
            "metadata_path": str(scene_root / "metadata.json"),
            "sample_rate_hz": str(production_task["sample_rate_hz"]),
            "production_task_id": production_task["task_id"],
        }
        fieldnames = list(row.keys())
        request = copy.deepcopy(self.request)
        request.update(
            {
                "request_id": "test_dry_run_resume_contract",
                "ordered_task_ids": [task_id],
                "production_task_id": production_task["task_id"],
                "scene_id": scene_id,
                "PRN": prn,
                "tracking_channel": channel,
                "sample_rate_hz": production_task["sample_rate_hz"],
                "expected_output_namespace": production_task["expected_output_namespace"],
                "pipeline_sha256": executor.sha256_file(PIPELINE_PATH),
                "python_executor_sha256": executor.sha256_file(Path(executor.__file__)),
                "wrapper_sha256": executor.sha256_file(WRAPPER_PATH),
            }
        )
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp_dir:
            root = Path(temp_dir)
            plan_path = root / "plan.csv"
            selected_path = root / "selected.csv"
            request_path = root / "request.json"
            log_root = root / "logs"
            executor.write_csv(plan_path, [row], fieldnames)
            executor.write_csv(
                selected_path,
                [{"task_id": task_id, "scene_id": scene_id, "prn": prn, "tracking_channel": channel}],
                ["task_id", "scene_id", "prn", "tracking_channel"],
            )
            request["plan_path"] = str(plan_path)
            request["plan_sha256"] = executor.sha256_file(plan_path)
            request["selected_tasks_snapshot_path"] = str(selected_path)
            request["selected_tasks_sha256"] = executor.sha256_file(selected_path)
            request["selection_sha256"] = executor.sha256_file(selected_path)
            request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
            request_sha = executor.sha256_file(request_path)
            result_code = executor.main(
                [
                    "--project-root",
                    str(PROJECT_ROOT),
                    "--plan",
                    str(plan_path),
                    "--selected-tasks",
                    str(selected_path),
                    "--request-manifest",
                    str(request_path),
                    "--expected-request-sha256",
                    str(request_sha),
                    "--matlab-executable",
                    "matlab-not-invoked",
                    "--dry-run",
                    "--log-root",
                    str(log_root),
                ]
            )
            self.assertEqual(result_code, 0)
            _fields, results = executor.read_csv(log_root / "batch_execution_log.csv")
            self.assertEqual(len(results), 1)
            self.assertIn("'Resume', false", results[0]["command_preview"])
            self.assertNotIn("'Resume', true", results[0]["command_preview"])


if __name__ == "__main__":
    unittest.main()
