import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freeze_mainline_1023_cohort import (
    CohortError,
    build_release,
    publish_release,
)


PILOT_RUN_ID = "run_20261003_F1023_V70_D0117_P2_G28_ch1"


class FreezeMainline1023CohortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.manifest = self.root / "manifest.csv"
        self.summary = self.root / "summary.csv"
        self.audit = self.root / "audit.json"
        self.audit_md = self.root / "audit.md"
        self.eligible = self.root / "eligible.csv"
        self.task_audit = self.root / "task_audit.csv"
        self.rows = self._make_rows()
        self._write_csv(self.manifest, self.rows)
        self._write_csv(self.summary, self.rows)
        self._write_eligible()
        self._write_task_audit()
        self._write_audit()
        self.audit_md.write_text("Gate A audit fixture PASS\n", encoding="utf-8")
        self._write_artifact_metadata()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _write_csv(path, rows):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def _make_rows(self):
        rows = []
        excluded = [
            ("run_20261003_F1023_V120_D0121_P2_G06_ch6", "F1023_V120_D0121_P2", "G06", "6", "PENDING", "WARNING"),
            ("run_20261003_F1023_V120_D0121_P2_G12_ch5", "F1023_V120_D0121_P2", "G12", "5", "PENDING", "WARNING"),
            ("run_20261003_F1023_V70_D0120_P9_G23_ch10", "F1023_V70_D0120_P9", "G23", "10", "PENDING", "WARNING"),
            ("run_20261003_F1023_V80_D0117_P8_G29_ch9", "F1023_V80_D0117_P8", "G29", "9", "PENDING", "WARNING"),
            ("run_20261003_F1023_V70_D0120_P1_G26_ch3", "F1023_V70_D0120_P1", "G26", "3", "FAILED", "NONE"),
            ("run_20261003_F1023_V70_D0120_P1_G27_ch8", "F1023_V70_D0120_P1", "G27", "8", "FAILED", "NONE"),
        ]
        for index in range(89):
            if index >= 83:
                run_id, scene_id, prn, channel, status, mapping_warning = excluded[index - 83]
            else:
                run_id = PILOT_RUN_ID if index == 0 else f"run_scene_{index:03d}"
                scene_id = "scene_pilot" if index == 0 else f"scene_{index:03d}"
                prn = "G28" if index == 0 else f"G{index:02d}"
                channel = "1" if index == 0 else str(index % 12)
                status = "ALREADY_COMPLETE" if index == 0 else "COMPLETE"
                mapping_warning = "NONE"
            output_namespace = f"scenes/{scene_id}/sage_results/run/{prn}_ch{channel}"
            rows.append({
                "run_id": run_id,
                "scene_id": scene_id,
                "prn": prn,
                "tracking_channel": channel,
                "mapping_warning": mapping_warning,
                "execution_status": status,
                "output_namespace": output_namespace,
                "frozen_sage_sha256": "a" * 64,
            })
        return rows

    def _write_eligible(self):
        eligible = []
        for row in self.rows[:83]:
            eligible.append({
                "run_id": row["run_id"],
                "scene_id": row["scene_id"],
                "prn": row["prn"],
                "tracking_channel": row["tracking_channel"],
                "mapping_warning": row["mapping_warning"],
                "execution_status": row["execution_status"],
                "audit_status": "PASS",
                "environment_class": "Urban",
                "elevation_group": "MISSING" if row["run_id"] == PILOT_RUN_ID else "Mid",
                "output_namespace": row["output_namespace"],
                "cohort_eligible": "true",
            })
        self._write_csv(self.eligible, eligible)

    def _write_task_audit(self):
        fields = {
            "run_id": "",
            "audit_status": "PASS",
            "environment_class": "Urban",
            "elevation_group": "Mid",
            "stage0_valid_40ms_windows": "10",
            "stage1_scanned_windows": "10",
            "stage2_evaluated_windows": "2",
            "stage2_selected_path_count": "3",
            "direct_path_count": "2",
            "stage2_mpc_count": "1",
            "stage3_persistent_mpc_count": "0",
            "stage4_confirmed_mpc_count": "0",
        }
        self._write_csv(self.task_audit, [{**fields, "run_id": row["run_id"]} for row in self.rows[:83]])

    def _write_audit(self):
        audit = {
            "audit_status": "PASS",
            "manifest": {"sha256": self._sha(self.manifest), "rows": 89},
            "summary": {"sha256": self._sha(self.summary), "rows": 89},
            "eligible_count": 83,
            "excluded_count": 6,
            "known_existing_pilot_cir": {
                "run_id": PILOT_RUN_ID,
                "counted_as_reexport": False,
                "output_present_in_inventory": True,
            },
        }
        self.audit.write_text(json.dumps(audit), encoding="utf-8")

    def _write_artifact_metadata(self):
        for row in self.rows[:83]:
            output = self.project / Path(row["output_namespace"])
            output.mkdir(parents=True, exist_ok=True)
            for filename in (
                "stage0_valid_40ms_windows.csv",
                "stage1_nav_fast_scan.csv",
                "stage2_selected_paths.csv",
                "stage3_persistence.csv",
                "stage4_joint_paths.csv",
                "relocation_receipt.json",
            ):
                target = output / filename
                if filename == "relocation_receipt.json":
                    target.write_text(json.dumps({
                        "scene_id": row["scene_id"],
                        "prn": row["prn"][1:],
                        "tracking_channel": int(row["tracking_channel"]),
                        "frozen_sage_sha256": "a" * 64,
                        "relocation_status": "VERIFIED_SAME_VOLUME_MOVE",
                    }), encoding="utf-8")
                else:
                    target.write_text("metadata-only fixture\n", encoding="utf-8")
        pilot = self.project / Path(self.rows[0]["output_namespace"])
        (pilot / "G28_ch1_code_domain_cir.h5").write_bytes(b"fixture")
        (pilot / "G28_ch1_code_domain_cir_metadata.json").write_text(
            json.dumps({
                "run_id": PILOT_RUN_ID,
                "scene_id": self.rows[0]["scene_id"],
                "prn": "G28",
                "tracking_channel": 1,
                "raw_iq_sha256": "NOT_RECOMPUTED",
                "stage0_window_count": 898,
                "cir_snapshot_count": 35920,
                "delay_grid_count": 451,
                "validation": {
                    "cir_all_finite": True,
                    "raw_iq_rms_all_positive": True,
                    "time_monotonic_nondecreasing": True,
                    "delay_grid_fixed": True,
                    "pdp_stage0_window_one_to_one": True,
                    "pdp_40ms_arithmetic_mean_of_40_powers": True,
                },
            }), encoding="utf-8"
        )
        (self.project / "reports" / "data_consolidation_20261003").mkdir(parents=True)
        (self.project / "reports" / "data_consolidation_20261003" / "BASELINE_CIR_EXPORT_AUDIT.md").write_text(
            "Read-back validation reported PASS for F1023_V70_D0117_P2 / G28 / ch1\n", encoding="utf-8"
        )

    @staticmethod
    def _sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _build(self):
        return build_release(
            manifest_path=self.manifest,
            summary_path=self.summary,
            audit_path=self.audit,
            audit_md_path=self.audit_md,
            eligible_path=self.eligible,
            task_audit_path=self.task_audit,
            project_root=self.project,
        )

    def _read_eligible(self):
        with self.eligible.open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_freezes_83_unique_identities_one_validated_pilot_and_82_new_tasks(self):
        release = self._build()
        self.assertEqual(release["cohort"]["eligible_count"], 83)
        self.assertEqual(len(release["cohort"]["tasks"]), 83)
        self.assertEqual(len({task["run_id"] for task in release["cohort"]["tasks"]}), 83)
        self.assertEqual(len(release["cir_tasks"]["tasks"]), 83)
        states = [task["task_status"] for task in release["cir_tasks"]["tasks"]]
        self.assertEqual(states.count("EXISTING_VALIDATED"), 1)
        self.assertEqual(states.count("NEW_REQUIRED"), 82)
        self.assertEqual(release["cohort"]["excluded_count"], 6)
        self.assertTrue(release["validation"]["gate_b_pass"])

    def test_stale_summary_sha_against_gate_a_is_rejected(self):
        with self.summary.open("a", encoding="utf-8") as stream:
            stream.write("\n")
        with self.assertRaises(CohortError):
            self._build()

    def test_wrong_prn_or_channel_in_audit_eligible_identity_is_rejected(self):
        eligible = self._read_eligible()
        eligible[0]["tracking_channel"] = "9"
        self._write_csv(self.eligible, eligible)
        with self.assertRaises(CohortError):
            self._build()

    def test_duplicate_manifest_run_id_is_rejected(self):
        self.rows[-1]["run_id"] = self.rows[0]["run_id"]
        self._write_csv(self.manifest, self.rows)
        self._write_csv(self.summary, self.rows)
        self._write_eligible()
        self._write_audit()
        with self.assertRaises(CohortError):
            self._build()

    def test_duplicate_pilot_in_eligible_set_is_rejected(self):
        eligible = self._read_eligible()
        eligible.append(dict(eligible[0]))
        self._write_csv(self.eligible, eligible)
        with self.assertRaises(CohortError):
            self._build()

    def test_pending_excluded_identity_cannot_be_substituted_into_cohort(self):
        eligible = self._read_eligible()
        excluded = self.rows[83]
        eligible[-1] = {
            **eligible[-1],
            "run_id": excluded["run_id"],
            "scene_id": excluded["scene_id"],
            "prn": excluded["prn"],
            "tracking_channel": excluded["tracking_channel"],
            "execution_status": excluded["execution_status"],
            "output_namespace": excluded["output_namespace"],
        }
        self._write_csv(self.eligible, eligible)
        with self.assertRaises(CohortError):
            self._build()

    def test_publish_refuses_existing_utc_version_directory_without_overwrite(self):
        release = self._build()
        output_root = self.root / "published"
        first = publish_release(release, output_root, timestamp="20261022T000000Z")
        before = (first / "cohort.json").read_bytes()
        with self.assertRaises(FileExistsError):
            publish_release(release, output_root, timestamp="20261022T000000Z")
        self.assertEqual((first / "cohort.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
