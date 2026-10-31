import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.channel_modeling.summarize_wp5_alpha_full_batch import (
    summarize_outputs,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SummarizeWp5AlphaFullBatchTests(unittest.TestCase):
    def test_binds_per_run_outputs_to_input_and_independent_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            run_id = "run_test_G01_ch0"
            source_dir = root / "scenes" / "Test" / "sage_results" / "run"
            source_dir.mkdir(parents=True)
            mat = source_dir / "stage2.mat"
            stage2 = source_dir / "stage2_selected_paths.csv"
            mat.write_bytes(b"frozen mat fixture")
            stage2.write_text("window_id,path_id\n1,1\n1,2\n", encoding="utf-8")

            output_root = root / "dataset_generation_logs" / "wp5_alpha"
            run_root = output_root / run_id
            run_root.mkdir(parents=True)
            alpha = run_root / "stage2_alpha.csv"
            ledger = run_root / "stage2_modeling_ledger.csv"
            alpha.write_text(
                "run_id,window_id,path_id,alpha_status,relative_power_check_status\n"
                f"{run_id},1,1,AVAILABLE,PASS\n{run_id},1,2,AVAILABLE,PASS\n",
                encoding="utf-8",
            )
            ledger.write_text(
                f"run_id,window_id,path_id\n{run_id},1,1\n{run_id},1,2\n",
                encoding="utf-8",
            )
            (output_root / "stage2_alpha_all_paths.csv").write_bytes(alpha.read_bytes())
            (output_root / "stage2_modeling_ledger_all_paths.csv").write_bytes(ledger.read_bytes())
            manifest_path = output_root / "input_manifest.csv"
            with manifest_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=[
                    "run_id", "scene_id", "prn", "tracking_channel",
                    "stage2_mat_path", "stage2_mat_sha256", "mat_sha256_basis",
                    "stage2_selected_paths_csv_path", "stage2_selected_paths_csv_sha256",
                    "preflight_status", "stage2_path_rows", "stage2_window_count", "stage2_mpc_count",
                    "stage2_direct_count",
                ])
                writer.writeheader()
                writer.writerow({
                    "run_id": run_id, "scene_id": "Test", "prn": "G01",
                    "tracking_channel": 0, "stage2_mat_path": str(mat),
                    "stage2_mat_sha256": sha256(mat),
                    "mat_sha256_basis": "RECOMPUTED_NO_RECEIPT_PIN",
                    "stage2_selected_paths_csv_path": str(stage2),
                    "stage2_selected_paths_csv_sha256": sha256(stage2),
                    "preflight_status": "READY",
                    "stage2_path_rows": 2, "stage2_window_count": 1,
                    "stage2_mpc_count": 1, "stage2_direct_count": 1,
                })
            audit_path = output_root / "run_export_audit.csv"
            with audit_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=[
                    "run_id", "status", "alpha_output_path", "modeling_ledger_path",
                    "stage2_path_rows", "alpha_available_count", "alpha_missing_count",
                    "relative_power_pass_count", "relative_power_mismatch_count",
                ])
                writer.writeheader()
                writer.writerow({
                    "run_id": run_id, "status": "EXPORTED",
                    "alpha_output_path": str(alpha), "modeling_ledger_path": str(ledger),
                    "stage2_path_rows": 2, "alpha_available_count": 2,
                    "alpha_missing_count": 0, "relative_power_pass_count": 2,
                    "relative_power_mismatch_count": 0,
                })
            validator_path = output_root / "independent_validation_per_run.csv"
            with validator_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["run_id", "status"])
                writer.writeheader()
                writer.writerow({"run_id": run_id, "status": "PASS"})
            preflight = {
                "status": "PREFLIGHT_PASS", "cohort_sha256": "a" * 64,
                "stage2_ledger_sha256": "b" * 64,
                "stage4_pin_manifest_sha256": "c" * 64,
                "frozen_sage_sha256": "d" * 64,
                "run_count": 1, "ready_run_count": 1,
                "mat_sha_receipt_pinned_run_count": 0,
                "mat_sha_recomputed_without_historical_pin_run_count": 1,
            }
            batch = {
                "status": "COMPLETE", "input_manifest_sha256": sha256(manifest_path),
                "run_count": 1, "exported_run_count": 1, "failed_run_count": 0,
                "rejected_run_count": 0, "stage2_path_count": 2,
                "stage2_window_count": 1, "stage2_mpc_count": 1,
                "stage2_direct_count": 1, "alpha_available_count": 2,
                "alpha_missing_count": 0, "relative_power_mismatch_count": 0,
            }
            validation = {
                "status": "PASS", "input_manifest_sha256": sha256(manifest_path),
                "run_count_expected": 1, "run_count_pass": 1,
                "stage2_path_count": 2, "stage2_window_count": 1,
                "stage2_mpc_count": 1, "stage2_direct_count": 1,
                "alpha_available_count": 2, "alpha_missing_count": 0,
                "alpha_nonfinite_available_count": 0,
                "relative_power_mismatch_count": 0,
                "path_identity_error_count": 0, "numeric_error_count": 0,
                "source_sha_error_count": 0,
            }
            for name, value in (("source_preflight.json", preflight),
                                ("batch_export_summary.json", batch),
                                ("independent_validation_summary.json", validation)):
                (output_root / name).write_text(json.dumps(value), encoding="utf-8")
            report_dir = root / "reports"

            result = summarize_outputs(root, output_root, report_dir)

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["per_run_output_manifest_rows"], 1)
            self.assertEqual(result["stage2_path_count"], 2)
            with (report_dir / "per_run_output_manifest.csv").open(encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["run_id"], run_id)
            self.assertEqual(row["alpha_output_sha256"], sha256(alpha))
            self.assertEqual(row["alpha_rows"], "2")
            self.assertEqual(row["mat_sha256_basis"], "RECOMPUTED_NO_RECEIPT_PIN")

    def test_refuses_to_overwrite_existing_report_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_dir = root / "reports"
            output_root = root / "batch"
            output_root.mkdir()
            report_dir.mkdir()
            with self.assertRaisesRegex(ValueError, "already exists"):
                summarize_outputs(root, output_root, report_dir)


if __name__ == "__main__":
    unittest.main()
