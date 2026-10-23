from __future__ import annotations

import unittest

from scripts.channel_modeling.mainline_stage2_model_prep import (
    annotate_cir_association,
    build_validated_cir_window_index,
    leave_one_scene_out_folds,
    mpc_counts_by_selected_window,
)


class MainlineStage2ModelPrepTests(unittest.TestCase):
    def test_mpc_counts_cover_only_stage2_represented_windows_and_keep_zero(self):
        rows = [
            {"run_id": "run-a", "window_id": "1", "path_id": "1", "is_multipath": "0"},
            {"run_id": "run-a", "window_id": "1", "path_id": "2", "is_multipath": "1"},
            {"run_id": "run-a", "window_id": "2", "path_id": "1", "is_multipath": "0"},
            {"run_id": "run-b", "window_id": "1", "path_id": "1", "is_multipath": "0"},
        ]

        self.assertEqual(
            mpc_counts_by_selected_window(rows),
            {("run-a", "1"): 1, ("run-a", "2"): 0, ("run-b", "1"): 0},
        )

    def test_mpc_counts_reject_duplicate_path_identity(self):
        row = {"run_id": "run-a", "window_id": "1", "path_id": "1", "is_multipath": "0"}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            mpc_counts_by_selected_window([row, dict(row)])

    def test_mpc_counts_reject_malformed_or_inconsistent_paths(self):
        with self.assertRaisesRegex(ValueError, "run_id"):
            mpc_counts_by_selected_window(
                [{"run_id": "", "window_id": "1", "path_id": "1", "is_multipath": "0"}]
            )
        with self.assertRaisesRegex(ValueError, "direct|multipath"):
            mpc_counts_by_selected_window(
                [{"run_id": "run-a", "window_id": "1", "path_id": "1", "is_multipath": "1"}]
            )
        with self.assertRaisesRegex(ValueError, "contiguous"):
            mpc_counts_by_selected_window(
                [
                    {"run_id": "run-a", "window_id": "1", "path_id": "1", "is_multipath": "0"},
                    {"run_id": "run-a", "window_id": "1", "path_id": "3", "is_multipath": "1"},
                ]
            )

    def test_loso_keeps_every_scene_wholly_in_one_fold(self):
        rows = [
            {"scene_id": "scene-b", "run_id": "b1", "window_id": "1"},
            {"scene_id": "scene-a", "run_id": "a1", "window_id": "1"},
            {"scene_id": "scene-a", "run_id": "a2", "window_id": "2"},
            {"scene_id": "scene-c", "run_id": "c1", "window_id": "3"},
        ]

        folds = leave_one_scene_out_folds(rows)

        self.assertEqual([fold["held_out_scene_id"] for fold in folds], ["scene-a", "scene-b", "scene-c"])
        for fold in folds:
            self.assertTrue(fold["test_indices"])
            self.assertFalse(set(fold["train_indices"]).intersection(fold["test_indices"]))
            self.assertEqual(
                {rows[index]["scene_id"] for index in fold["test_indices"]},
                {fold["held_out_scene_id"]},
            )
            self.assertNotIn(fold["held_out_scene_id"], {rows[index]["scene_id"] for index in fold["train_indices"]})

    def test_loso_requires_two_scenes_and_nonempty_scene_ids(self):
        with self.assertRaisesRegex(ValueError, "two"):
            leave_one_scene_out_folds([{"scene_id": "only"}])
        with self.assertRaisesRegex(ValueError, "scene_id"):
            leave_one_scene_out_folds([{"scene_id": "a"}, {"scene_id": ""}])

    def test_only_fully_validated_matching_window_index_is_trusted(self):
        evidence = [
            {
                "run_id": "run-a",
                "expected_run_id": "run-a",
                "task_receipt_run_id": "run-a",
                "hdf5_run_id": "run-a",
                "task_receipt_status": "PASS",
                "hdf5_readback_status": "PASS",
                "stage0_window_ids": ["1", "2"],
                "pdp_window_ids": ["1", "2"],
            },
            {
                "run_id": "run-b",
                "expected_run_id": "run-b",
                "task_receipt_run_id": "run-b",
                "hdf5_run_id": "run-b",
                "task_receipt_status": "PASS",
                "hdf5_readback_status": "PENDING",
                "stage0_window_ids": ["1"],
                "pdp_window_ids": [],
            },
        ]

        validated_runs, window_keys = build_validated_cir_window_index(evidence)

        self.assertEqual(validated_runs, {"run-a"})
        self.assertEqual(window_keys, {("run-a", "1"), ("run-a", "2")})

    def test_pass_with_mismatched_or_duplicate_window_ids_is_rejected(self):
        base = {
            "run_id": "run-a",
            "expected_run_id": "run-a",
            "task_receipt_run_id": "run-a",
            "hdf5_run_id": "run-a",
            "task_receipt_status": "PASS",
            "hdf5_readback_status": "PASS",
            "stage0_window_ids": ["1", "2"],
            "pdp_window_ids": ["1", "3"],
        }
        with self.assertRaisesRegex(ValueError, "do not match"):
            build_validated_cir_window_index([base])

        duplicated = dict(base, stage0_window_ids=["1", "1"], pdp_window_ids=["1", "1"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_validated_cir_window_index([duplicated])

    def test_duplicate_run_evidence_is_rejected(self):
        record = {
            "run_id": "run-a",
            "task_receipt_status": "PENDING",
            "hdf5_readback_status": "PENDING",
            "stage0_window_ids": [],
            "pdp_window_ids": [],
        }
        with self.assertRaisesRegex(ValueError, "duplicate run_id"):
            build_validated_cir_window_index([record, dict(record)])

    def test_pass_evidence_must_bind_expected_receipt_and_hdf5_run_identity(self):
        record = {
            "run_id": "run-a",
            "expected_run_id": "run-a",
            "task_receipt_run_id": "run-other",
            "hdf5_run_id": "run-a",
            "task_receipt_status": "PASS",
            "hdf5_readback_status": "PASS",
            "stage0_window_ids": ["1"],
            "pdp_window_ids": ["1"],
        }
        with self.assertRaisesRegex(ValueError, "run identity"):
            build_validated_cir_window_index([record])

    def test_association_uses_exact_run_and_window_and_preserves_all_rows(self):
        rows = [
            {"run_id": "run-a", "window_id": "7", "path_id": "2", "value": "first"},
            {"run_id": "run-a", "window_id": "8", "path_id": "2", "value": "no-match"},
            {"run_id": "run-b", "window_id": "7", "path_id": "2", "value": "same-window-other-run"},
            {"run_id": "run-c", "window_id": "7", "path_id": "2", "value": "unvalidated"},
        ]
        before = [dict(row) for row in rows]

        annotated = annotate_cir_association(
            rows,
            {"run-a", "run-b"},
            {("run-a", "7")},
        )

        self.assertEqual(len(annotated), len(rows))
        self.assertEqual([row["value"] for row in annotated], [row["value"] for row in rows])
        self.assertEqual(
            [row["cir_association_status"] for row in annotated],
            ["ASSOCIATED_VALIDATED", "NO_CIR_CORRESPONDENCE", "NO_CIR_CORRESPONDENCE", "UNASSOCIATED"],
        )
        self.assertEqual(rows, before)
        self.assertNotIn("cir_association_status", rows[0])

    def test_association_rejects_unsafe_index_or_duplicate_stage2_identity(self):
        row = {"run_id": "run-a", "window_id": "1", "path_id": "2"}
        with self.assertRaisesRegex(ValueError, "not validated run"):
            annotate_cir_association([row], set(), {("run-a", "1")})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            annotate_cir_association([row, dict(row)], {"run-a"}, {("run-a", "1")})


if __name__ == "__main__":
    unittest.main()
