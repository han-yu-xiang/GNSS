import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.channel_modeling.prepare_wp5_alpha_full_cohort import (
    FrozenPins,
    prepare_manifest,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class PrepareWp5AlphaFullCohortTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, Path, dict[str, Path]]:
        task_id = "run_20261003_TestScene_G01_ch0"
        namespace = Path("scenes/TestScene/sage_results/rerun/G01_ch0")
        source = root / namespace
        source.mkdir(parents=True)
        output_parent = root / "dataset_generation_logs/channel_modeling"
        output_parent.mkdir(parents=True)

        stage2_rows = [
            {
                "window_id": "1", "recording_time_s": "0.04", "selected_L": "2",
                "path_id": "1", "is_multipath": "0", "delay_samples": "0",
                "excess_delay_samples": "0", "excess_delay_chips": "0",
                "excess_path_length_m": "0", "doppler_hz": "10",
                "doppler_offset_hz": "0", "relative_power_db": "0",
            },
            {
                "window_id": "1", "recording_time_s": "0.04", "selected_L": "2",
                "path_id": "2", "is_multipath": "1", "delay_samples": "1",
                "excess_delay_samples": "1", "excess_delay_chips": "0.1",
                "excess_path_length_m": "3", "doppler_hz": "12",
                "doppler_offset_hz": "2", "relative_power_db": "-6.020599913279624",
            },
        ]
        stage2_path = source / "stage2_selected_paths.csv"
        with stage2_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(stage2_rows[0]))
            writer.writeheader()
            writer.writerows(stage2_rows)

        stage3_path = source / "stage3_persistence.csv"
        stage3_path.write_text(
            "center_window_id,multipath_id,persistence_pass,matched_window_count,longest_consecutive_count\n"
            "1,1,0,1,1\n", encoding="utf-8"
        )
        reliable_path = source / "stage3_reliable_centers.csv"
        reliable_path.write_text("center_window_id\n1\n", encoding="utf-8")
        stage4_paths_path = source / "stage4_joint_paths.csv"
        stage4_paths_path.write_text(
            "center_window_id,path_id,is_multipath,joint_selected_L\n", encoding="utf-8"
        )
        stage4_summary_path = source / "stage4_joint_summary.csv"
        stage4_summary_path.write_text(
            "center_window_id,joint_valid,joint_selected_L\n1,0,0\n", encoding="utf-8"
        )
        mat_path = source / "stage2_nav_sage_L1_L4.mat"
        mat_path.write_bytes(b"synthetic-test-MAT-metadata-only")
        context_path = source / "run_context.json"
        context_path.write_text(json.dumps({
            "sceneId": "TestScene", "prn": 1, "prnLabel": "G01",
            "trackingChannel": 0, "samplingRateHz": 10230000,
        }), encoding="utf-8")

        sage_source = root / "scripts/sage_pipeline/run_nav_sage_pipeline.m"
        sage_source.parent.mkdir(parents=True)
        sage_source.write_bytes(b"synthetic-frozen-sage-source")
        frozen_sha = sha256(sage_source)
        receipt_path = source / "relocation_receipt.json"
        receipt_path.write_text(json.dumps({
            "scene_id": "TestScene", "prn": 1, "tracking_channel": 0,
            "frozen_sage_sha256": frozen_sha,
            "final_relocated_path": str(source), "resume": False,
            "matlab_exit_code": 0,
            "relocation_status": "VERIFIED_SAME_VOLUME_MOVE",
        }), encoding="utf-8")

        stage2_sha = sha256(stage2_path)
        task = {
            "run_id": task_id, "scene_id": "TestScene", "prn": "G01",
            "tracking_channel": 0, "source_frozen_sage_sha256": frozen_sha,
            "output_namespace": namespace.as_posix(),
            "relocation_receipt": {
                "path": (namespace / "relocation_receipt.json").as_posix(),
                "sha256": sha256(receipt_path), "size_bytes": receipt_path.stat().st_size,
            },
            "stage_counts_from_gate_a": {
                "stage2_selected_path_count": 2, "direct_path_count": 1,
                "stage2_mpc_count": 1,
            },
            "stage_csvs": {
                "stage2_selected_paths": {
                    "path": (namespace / stage2_path.name).as_posix(),
                    "sha256": stage2_sha, "size_bytes": stage2_path.stat().st_size,
                },
                "stage3_persistence": {
                    "path": (namespace / stage3_path.name).as_posix(),
                    "sha256": sha256(stage3_path), "size_bytes": stage3_path.stat().st_size,
                },
                "stage4_joint_paths": {
                    "path": (namespace / stage4_paths_path.name).as_posix(),
                    "sha256": sha256(stage4_paths_path), "size_bytes": stage4_paths_path.stat().st_size,
                },
            },
        }
        cohort_path = root / "cohort.json"
        cohort_path.write_text(json.dumps({
            "eligible_count": 1, "excluded_count": 0, "tasks": [task],
        }), encoding="utf-8")
        cohort_sha = sha256(cohort_path)
        pin_path = root / "stage4_pins.json"
        pin_path.write_text(json.dumps({
            "cohort_sha256": cohort_sha, "task_count": 1,
            "stage4_joint_summary_sha256_by_run_id": {
                task_id: {
                    "path": (namespace / stage4_summary_path.name).as_posix(),
                    "sha256": sha256(stage4_summary_path),
                }
            },
        }), encoding="utf-8")

        ledger_path = root / "stage2_ledger.csv"
        ledger_fields = [
            "run_id", "scene_id", "prn", "tracking_channel", "window_id",
            "path_id", "selected_L", "recording_time_s", "is_multipath",
            "delay_samples", "excess_delay_samples", "excess_delay_chips",
            "excess_path_length_m", "doppler_hz", "doppler_offset_hz",
            "relative_power_db", "source_stage2_csv_sha256",
            "stage2_source_row_number",
        ]
        with ledger_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=ledger_fields)
            writer.writeheader()
            for line_no, row in enumerate(stage2_rows, start=2):
                writer.writerow({
                    "run_id": task_id, "scene_id": "TestScene", "prn": "G01",
                    "tracking_channel": "0", **row,
                    "source_stage2_csv_sha256": stage2_sha,
                    "stage2_source_row_number": str(line_no),
                })
        return cohort_path, ledger_path, pin_path, {
            "stage2": stage2_path, "mat": mat_path, "receipt": receipt_path,
            "stage4_summary": stage4_summary_path, "sage": sage_source,
        }

    def pins(self, cohort: Path, ledger: Path, stage4_pins: Path, sage: Path) -> FrozenPins:
        return FrozenPins(
            cohort_sha256=sha256(cohort), ledger_sha256=sha256(ledger),
            stage4_pin_manifest_sha256=sha256(stage4_pins),
            frozen_sage_sha256=sha256(sage), run_count=1, path_count=2,
            window_count=1, mpc_count=1, direct_count=1, excluded_count=0,
        )

    def test_builds_identity_bound_manifest_from_receipts_and_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cohort, ledger, pins_path, paths = self.fixture(root)
            out = root / "dataset_generation_logs/channel_modeling/wp5_alpha_test"
            result = prepare_manifest(
                root, cohort, ledger, pins_path, out,
                self.pins(cohort, ledger, pins_path, paths["sage"])
            )
            self.assertEqual(result["ready_run_count"], 1)
            self.assertEqual(result["rejected_run_count"], 0)
            manifest = read_manifest(out / "input_manifest.csv")
            self.assertEqual(manifest[0]["run_id"], "run_20261003_TestScene_G01_ch0")
            self.assertEqual(manifest[0]["preflight_status"], "READY")
            self.assertEqual(manifest[0]["stage2_path_rows"], "2")
            self.assertEqual(manifest[0]["stage2_window_count"], "1")
            self.assertEqual(manifest[0]["stage2_mpc_count"], "1")
            self.assertEqual(manifest[0]["mat_sha256_basis"], "RECOMPUTED_NO_RECEIPT_PIN")
            self.assertEqual(manifest[0]["stage2_mat_sha256"], sha256(paths["mat"]))

    def test_records_one_run_pin_failure_without_rewriting_its_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cohort, ledger, pins_path, paths = self.fixture(root)
            with paths["stage2"].open("a", encoding="utf-8") as stream:
                stream.write("\n")
            before = paths["stage2"].read_bytes()
            out = root / "dataset_generation_logs/channel_modeling/wp5_alpha_test"
            result = prepare_manifest(
                root, cohort, ledger, pins_path, out,
                self.pins(cohort, ledger, pins_path, paths["sage"])
            )
            manifest = read_manifest(out / "input_manifest.csv")
            self.assertEqual(result["rejected_run_count"], 1)
            self.assertEqual(manifest[0]["preflight_status"], "REJECTED")
            self.assertIn("STAGE2_SELECTED_PATHS_PIN_MISMATCH", manifest[0]["preflight_reason"])
            self.assertEqual(paths["stage2"].read_bytes(), before)

    def test_rejects_wrong_global_ledger_pin_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cohort, ledger, pins_path, _ = self.fixture(root)
            out = root / "dataset_generation_logs/channel_modeling/wp5_alpha_test"
            pins = self.pins(cohort, ledger, pins_path, root / "scripts/sage_pipeline/run_nav_sage_pipeline.m")
            wrong = FrozenPins(**{**pins.__dict__, "ledger_sha256": "0" * 64})
            with self.assertRaisesRegex(ValueError, "ledger SHA-256 mismatch"):
                prepare_manifest(root, cohort, ledger, pins_path, out, wrong)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
