"""Focused tests for the Stage2-all-MPC Mainline ledger."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "build_mainline_1023_stage2_ledger.py"
SPEC = importlib.util.spec_from_file_location("mainline_stage2_ledger", MODULE_PATH)
LEDGER = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = LEDGER
SPEC.loader.exec_module(LEDGER)


class MainlineStage2LedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.task = self._make_fixture()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_keeps_all_stage2_rows_and_stage_labels_are_non_gating(self) -> None:
        result = self._build_ledger()
        with (self.task["output_dir"] / "stage2_ledger.csv").open(
            newline="", encoding="utf-8"
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 5)
        self.assertEqual(sum(row["modeling_role"] == "MPC_CANDIDATE" for row in rows), 2)
        self.assertEqual(sum(row["modeling_role"] == "DIRECT_REFERENCE" for row in rows), 3)
        mpc_by_window = {int(row["window_id"]): row for row in rows if row["is_multipath"] == "1"}
        self.assertEqual(mpc_by_window[2]["stage3_persistence"], "YES")
        self.assertEqual(mpc_by_window[2]["stage4_mapping"], "CONFIRMED_EXACT_PATH")
        self.assertEqual(mpc_by_window[3]["stage3_persistence"], "NO")
        self.assertEqual(mpc_by_window[3]["stage4_mapping"], "NOT_EVALUATED_NOT_STAGE3_PERSISTENT")
        self.assertEqual(result["counts"]["stage2_mpc_count"], 2)

    def test_missing_elevation_and_window_dependence_are_explicit(self) -> None:
        self._build_ledger()
        with (self.task["output_dir"] / "stage2_ledger.csv").open(
            newline="", encoding="utf-8"
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertTrue(all(row["elevation_group"] == "MISSING" for row in rows))
        self.assertTrue(all(row["mean_elevation_deg"] == "" for row in rows))
        self.assertTrue(all(row["dependence_cluster_id"] == "run_test_scene_G01_ch0" for row in rows))
        self.assertTrue(all(row["window_independence_assumed"] == "NO" for row in rows))
        self.assertTrue(all(row["cir_feature_status"] == "PENDING_TASK5_COMPLETION" for row in rows))

    def test_available_elevation_group_does_not_invent_a_numeric_mean(self) -> None:
        self.assertEqual(
            LEDGER._validate_elevation(
                {"elevation_group": "Low", "mean_elevation_deg": None}, "run_without_mean"
            ),
            ("Low", "", "NOT_AVAILABLE_IN_FROZEN_COHORT"),
        )

    def test_unmatched_stage4_path_is_unmapped_not_negative(self) -> None:
        stage4_path = self.task["stage4_path"]
        with stage4_path.open(newline="", encoding="utf-8") as stream:
            table = list(csv.DictReader(stream))
        table = [row for row in table if row["path_id"] != "2"]
        self._write_csv(stage4_path, ["center_window_id", "path_id", "is_multipath", "joint_selected_L"], table)
        self.task["cohort"] = self._refresh_csv_pin(self.task["cohort"], "stage4_joint_paths", stage4_path)
        self.task["cohort"]["tasks"][0]["stage_counts_from_gate_a"]["stage4_confirmed_mpc_count"] = 0
        audit_path = self.root / self.task["cohort"]["source_sha256"]["gate_a_audit_json"]["path"]
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit["stage_aggregate_counts"]["stage4_confirmed_mpc_count"] = 0
        audit_path.write_text(json.dumps(audit), encoding="utf-8")
        self.task["cohort"]["source_sha256"]["gate_a_audit_json"]["sha256"] = self._sha(audit_path)
        self._write_cohort(self.task["cohort_path"], self.task["cohort"])
        self._refresh_external_pins()

        self._build_ledger(expected=self._expected(stage4_confirmed=0))
        with (self.task["output_dir"] / "stage2_ledger.csv").open(
            newline="", encoding="utf-8"
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(
            next(row for row in rows if row["window_id"] == "2" and row["is_multipath"] == "1")["stage4_mapping"],
            "UNMAPPED",
        )

    def test_duplicate_stage2_identity_is_rejected(self) -> None:
        stage2_path = self.task["stage2_path"]
        with stage2_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        rows.append(dict(rows[-1]))
        self._write_csv(stage2_path, list(rows[0].keys()), rows)
        self.task["cohort"] = self._refresh_csv_pin(self.task["cohort"], "stage2_selected_paths", stage2_path)
        self._write_cohort(self.task["cohort_path"], self.task["cohort"])
        self._refresh_external_pins()

        with self.assertRaisesRegex(LEDGER.LedgerError, "duplicate Stage2 identity"):
            self._build_ledger()

    def test_stale_manifest_pin_is_rejected(self) -> None:
        (self.root / "reports/data_consolidation_20261003/MAINLINE_SAGE_1023_RERUN_MANIFEST.csv").write_text(
            "changed\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(LEDGER.LedgerError, "SHA-256 mismatch"):
            self._build_ledger()

    def test_changed_cohort_bytes_are_rejected_even_if_embedded_stage_pin_changes(self) -> None:
        stage2_path = self.task["stage2_path"]
        with stage2_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        rows[0]["relative_power_db"] = "-99.0"
        self._write_csv(stage2_path, list(rows[0].keys()), rows)
        self.task["cohort"] = self._refresh_csv_pin(self.task["cohort"], "stage2_selected_paths", stage2_path)
        self._write_cohort(self.task["cohort_path"], self.task["cohort"])
        # Do not refresh the independent digest: the cohort bytes themselves are frozen.
        with self.assertRaisesRegex(LEDGER.LedgerError, "cohort SHA-256 mismatch"):
            self._build_ledger()

    def test_stage4_joint_summary_digest_is_pinned_outside_the_cohort(self) -> None:
        stage4_summary_path = self.task["stage4_summary_path"]
        self._write_csv(
            stage4_summary_path,
            ["center_window_id", "joint_valid", "joint_selected_L"],
            [{"center_window_id": "2", "joint_valid": "0", "joint_selected_L": "2"}],
        )
        with self.assertRaisesRegex(LEDGER.LedgerError, "Stage4 summary SHA-256 mismatch"):
            self._build_ledger()

    def test_stage4_summary_pin_manifest_is_itself_digest_pinned(self) -> None:
        pins_path = self.task["stage4_summary_pins_path"]
        pins_path.write_text(pins_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(LEDGER.LedgerError, "Stage4 summary pin manifest: SHA-256 mismatch"):
            self._build_ledger()

    def test_existing_output_namespace_is_never_overwritten(self) -> None:
        self.task["output_dir"].mkdir()
        marker = self.task["output_dir"] / "existing.txt"
        marker.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(LEDGER.LedgerError, "refusing overwrite"):
            self._build_ledger()
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_nonfinite_core_feature_is_rejected(self) -> None:
        stage2_path = self.task["stage2_path"]
        with stage2_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        rows[0]["relative_power_db"] = "NaN"
        self._write_csv(stage2_path, list(rows[0].keys()), rows)
        self.task["cohort"] = self._refresh_csv_pin(self.task["cohort"], "stage2_selected_paths", stage2_path)
        self._write_cohort(self.task["cohort_path"], self.task["cohort"])
        self._refresh_external_pins()

        with self.assertRaisesRegex(LEDGER.LedgerError, "non-finite Stage2 value"):
            self._build_ledger()

    def _make_fixture(self) -> dict:
        files = {
            "cohort_generator": "scripts/channel_modeling/freeze_mainline_1023_cohort.py",
            "gate_a_audit_json": "reports/data_consolidation_20261003/audit.json",
            "gate_a_audit_markdown": "reports/data_consolidation_20261003/audit.md",
            "gate_a_eligible_runs": "reports/data_consolidation_20261003/eligible_runs.csv",
            "gate_a_task_audit": "reports/data_consolidation_20261003/task_audit.csv",
            "manifest": "reports/data_consolidation_20261003/MAINLINE_SAGE_1023_RERUN_MANIFEST.csv",
            "summary": "reports/data_consolidation_20261003/MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv",
            "targeted_test": "scripts/channel_modeling/tests/test_freeze_mainline_1023_cohort.py",
        }
        for relative in files.values():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")

        run_id = "run_test_scene_G01_ch0"
        task_dir = self.root / "scenes/test_scene/sage_results/G01_ch0"
        task_dir.mkdir(parents=True)
        stage2_path = task_dir / "stage2.csv"
        stage3_path = task_dir / "stage3.csv"
        stage4_path = task_dir / "stage4.csv"
        self._write_csv(stage2_path, [
            "window_id", "recording_time_s", "selected_L", "path_id", "is_multipath",
            "delay_samples", "excess_delay_samples", "excess_delay_chips",
            "excess_path_length_m", "doppler_hz", "doppler_offset_hz", "relative_power_db",
        ], [
            self._stage2_row(1, 1, 0, 1), self._stage2_row(2, 1, 0, 2),
            self._stage2_row(2, 2, 1, 2), self._stage2_row(3, 1, 0, 2),
            self._stage2_row(3, 2, 1, 2),
        ])
        self._write_csv(stage3_path, [
            "center_window_id", "multipath_id", "persistence_pass", "matched_window_count", "longest_consecutive_count",
        ], [
            {"center_window_id": "2", "multipath_id": "1", "persistence_pass": "1", "matched_window_count": "3", "longest_consecutive_count": "2"},
            {"center_window_id": "3", "multipath_id": "1", "persistence_pass": "0", "matched_window_count": "1", "longest_consecutive_count": "1"},
        ])
        stage4_summary_path = task_dir / "stage4_joint_summary.csv"
        self._write_csv(stage4_summary_path, ["center_window_id", "joint_valid", "joint_selected_L"], [
            {"center_window_id": "2", "joint_valid": "1", "joint_selected_L": "2"},
        ])
        self._write_csv(stage4_path, ["center_window_id", "path_id", "is_multipath", "joint_selected_L"], [
            {"center_window_id": "2", "path_id": "2", "is_multipath": "1", "joint_selected_L": "2"},
        ])

        source_pins = {
            key: {"path": relative, "sha256": self._sha(self.root / relative)}
            for key, relative in files.items()
        }
        stage_csvs = {
            "stage2_selected_paths": {"path": self._relative(stage2_path), "sha256": self._sha(stage2_path)},
            "stage3_persistence": {"path": self._relative(stage3_path), "sha256": self._sha(stage3_path)},
            "stage4_joint_paths": {"path": self._relative(stage4_path), "sha256": self._sha(stage4_path)},
        }
        audit = {
            "audit_status": "PASS", "eligible_count": 1, "excluded_count": 1,
            "stage_aggregate_counts": {
                "stage2_selected_path_count": 5, "direct_path_count": 3,
            "stage2_mpc_count": 2, "stage3_persistence_row_count": 2,
            "stage3_persistent_mpc_count": 1,
                "stage4_confirmed_mpc_count": 1,
            },
            "warnings": [{"code": "scene_prn_elevation_join_missing", "run_id": run_id}],
        }
        audit_path = self.root / files["gate_a_audit_json"]
        audit_path.write_text(json.dumps(audit), encoding="utf-8")
        source_pins["gate_a_audit_json"]["sha256"] = self._sha(audit_path)

        eligible_path = self.root / files["gate_a_eligible_runs"]
        self._write_csv(eligible_path, ["run_id", "scene_id", "prn", "tracking_channel", "execution_status"], [
            {"run_id": run_id, "scene_id": "test_scene", "prn": "G01", "tracking_channel": "0", "execution_status": "COMPLETE"},
        ])
        source_pins["gate_a_eligible_runs"]["sha256"] = self._sha(eligible_path)

        task = {
            "run_id": run_id, "scene_id": "test_scene", "prn": "G01", "tracking_channel": 0,
            "output_namespace": "scenes/test_scene/sage_results/G01_ch0",
            "source_summary_status": "COMPLETE", "environment_class": "Urban",
            "elevation_group": "MISSING", "mean_elevation_deg": None,
            "stage_counts_from_gate_a": {
                "direct_path_count": 3, "stage2_mpc_count": 2,
                "stage2_selected_path_count": 5, "stage3_persistent_mpc_count": 1,
                "stage4_confirmed_mpc_count": 1,
            },
            "stage_csvs": stage_csvs,
        }
        cohort = {
            "cohort_id": "fixture", "eligible_count": 1, "excluded_count": 1,
            "excluded": [{"run_id": "excluded_run", "execution_status": "PENDING"}],
            "source_sha256": source_pins, "tasks": [task],
        }
        cohort_path = self.root / "dataset_generation_logs/cohort.json"
        self._write_cohort(cohort_path, cohort)
        stage4_summary_pins_path = (
            self.root / LEDGER.DEFAULT_STAGE4_SUMMARY_PIN_MANIFEST
        )
        stage4_summary_pins_sha256 = self._write_stage4_summary_pins(
            cohort_path, cohort, stage4_summary_pins_path
        )
        return {
            "cohort": cohort, "cohort_path": cohort_path, "output_dir": self.root / "output",
            "stage2_path": stage2_path, "stage4_path": stage4_path,
            "stage4_summary_path": stage4_summary_path,
            "stage4_summary_pins_path": stage4_summary_pins_path,
            "stage4_summary_pins_sha256": stage4_summary_pins_sha256,
            "cohort_sha256": self._sha(cohort_path),
        }

    @staticmethod
    def _expected(stage4_confirmed: int = 1) -> object:
        return LEDGER.ExpectedCounts(
            cohort=1, excluded=1, stage2=5, direct=3, mpc=2,
            stage3_rows=2, stage3_persistent=1,
            stage4_confirmed=stage4_confirmed, missing_elevation=1,
        )

    @staticmethod
    def _stage2_row(window: int, path: int, is_multipath: int, selected_l: int) -> dict[str, str]:
        return {
            "window_id": str(window), "recording_time_s": f"{window * 0.02:.2f}",
            "selected_L": str(selected_l), "path_id": str(path), "is_multipath": str(is_multipath),
            "delay_samples": "1.2", "excess_delay_samples": "1.2",
            "excess_delay_chips": "0.12", "excess_path_length_m": "35.0",
            "doppler_hz": "-5000", "doppler_offset_hz": "25", "relative_power_db": "-3.4",
        }

    def _refresh_csv_pin(self, cohort: dict, name: str, path: Path) -> dict:
        for task in cohort["tasks"]:
            if name in task["stage_csvs"] and task["stage_csvs"][name]["path"] == self._relative(path):
                task["stage_csvs"][name]["sha256"] = self._sha(path)
        return cohort

    def _write_cohort(self, path: Path, cohort: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cohort, indent=2), encoding="utf-8")

    def _build_ledger(self, expected: object | None = None) -> dict:
        with (
            patch.object(LEDGER, "EXPECTED_COHORT_SHA256", self.task["cohort_sha256"]),
            patch.object(
                LEDGER,
                "DEFAULT_STAGE4_SUMMARY_PIN_MANIFEST",
                self._relative(self.task["stage4_summary_pins_path"]),
            ),
            patch.object(
                LEDGER,
                "EXPECTED_STAGE4_SUMMARY_PIN_MANIFEST_SHA256",
                self.task["stage4_summary_pins_sha256"],
            ),
        ):
            return LEDGER.build_ledger(
                self.root,
                self.task["cohort_path"],
                self.task["output_dir"],
                expected=expected or self._expected(),
            )

    def _refresh_external_pins(self) -> None:
        self.task["cohort_sha256"] = self._sha(self.task["cohort_path"])
        self.task["stage4_summary_pins_sha256"] = self._write_stage4_summary_pins(
            self.task["cohort_path"],
            json.loads(self.task["cohort_path"].read_text(encoding="utf-8")),
            self.task["stage4_summary_pins_path"],
        )

    def _write_stage4_summary_pins(self, cohort_path: Path, cohort: dict, pins_path: Path) -> str:
        root = self.root.resolve()
        pins = {}
        for task in cohort["tasks"]:
            relative = (
                Path(task["output_namespace"]) / "stage4_joint_summary.csv"
            ).as_posix()
            source = (root / relative).resolve()
            pins[task["run_id"]] = {
                "path": relative,
                "sha256": self._sha(source),
            }
        payload = {
            "schema_version": 1,
            "cohort_sha256": self._sha(cohort_path),
            "task_count": len(pins),
            "stage4_joint_summary_sha256_by_run_id": pins,
        }
        pins_path.parent.mkdir(parents=True, exist_ok=True)
        pins_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return self._sha(pins_path)

    def _write_csv(self, path: Path, fieldnames: list[str], rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
