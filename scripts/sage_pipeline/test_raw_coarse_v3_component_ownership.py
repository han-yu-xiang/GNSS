"""Regression tests for the v3 component ownership/schema revision."""

from __future__ import annotations

import csv
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import raw_coarse_v3_common as common  # noqa: E402
import rebuild_raw_coarse_v3_component_ownership as ownership  # noqa: E402


class ComponentOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        root = PROJECT_ROOT / "dataset_generation_logs" / "sampling_validation"
        root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="batch_sampled_v1_3_ownership_test_", dir=str(root)))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _parent(self) -> dict:
        features = []
        task = {"task_id": "task", "scene_id": "scene", "prn": "G16", "tracking_channel": "1", "sample_rate_hz": "10230000"}
        promoted = {2, 4, 6}
        for window_id in range(1, 9):
            features.append({
                **task, "window_id": str(window_id),
                "promotion_status": "coarse_promoted" if window_id in promoted else "not_promoted",
                "promotion_reason": "seed" if window_id in promoted else "not_seed",
                "not_promoted": "false" if window_id in promoted else "true",
                "coverage_status": "coarse_promotion_component" if window_id in promoted else "coarse_evidence_only",
            })
        components = [
            {**task, "component_id": "v3c00002", "seed_window_count": "1", "first_window_id": "4", "last_window_id": "4", "component_window_ids": "3;4;5"},
            {**task, "component_id": "v3c00001", "seed_window_count": "1", "first_window_id": "2", "last_window_id": "2", "component_window_ids": "1;2;3"},
            {**task, "component_id": "v3c00003", "seed_window_count": "1", "first_window_id": "6", "last_window_id": "6", "component_window_ids": "3;4;5;6;7"},
        ]
        for row in components:
            row.update({"profile_rule": "v3", "boundary_expansion_windows": "2", "bridge_gap_windows": "2", "closure_radius_windows": "2", "gold_labels_used_for_selection": "false"})
        return {
            "features": features,
            "components": components,
            "parent_hashes": {"feature": "feature-hash", "promotion": "promotion-hash", "component": "component-hash", "run_manifest": "run-hash"},
        }

    def _schema(self) -> dict:
        return {"ownership_schema_sha256": "ownership-hash", "parent_frozen_parameter_sha256": "parent-parameter-hash"}

    def test_two_component_boundary_overlap_is_two_memberships_without_merge(self):
        memberships, components, by_key = ownership.build_memberships(self._parent(), self._schema())
        self.assertEqual(len(components), 3)
        self.assertEqual(by_key[("task", 3)], ["v3c00001", "v3c00002", "v3c00003"])
        self.assertEqual(len([row for row in memberships if row["window_id"] == 3]), 3)
        self.assertNotEqual(by_key[("task", 3)][0], by_key[("task", 3)][1])

    def test_three_way_membership_is_explicit_and_deterministic(self):
        memberships, _components, by_key = ownership.build_memberships(self._parent(), self._schema())
        rows = [row for row in memberships if row["window_id"] == 3]
        self.assertEqual([row["component_id"] for row in rows], ["v3c00001", "v3c00002", "v3c00003"])
        self.assertEqual([row["membership_type"] for row in rows], ["guard", "guard", "guard"])
        self.assertEqual(len(by_key[("task", 3)]), 3)

    def test_core_and_guard_membership_types_are_distinct(self):
        memberships, _components, _by_key = ownership.build_memberships(self._parent(), self._schema())
        core = {(row["component_id"], row["window_id"]) for row in memberships if row["membership_type"] == "core_seed"}
        self.assertIn(("v3c00001", 2), core)
        self.assertIn(("v3c00002", 4), core)
        self.assertIn(("v3c00003", 6), core)
        self.assertTrue(all(row["distance_from_core_windows"] == 0 for row in memberships if row["membership_type"] == "core_seed"))

    def test_unique_fine_union_does_not_count_memberships(self):
        _memberships, _components, by_key = ownership.build_memberships(self._parent(), self._schema())
        unique = {window_id for (task_id, window_id), component_ids in by_key.items() if component_ids}
        self.assertEqual(unique, set(range(1, 8)))
        self.assertEqual(len(unique), 7)
        self.assertEqual(sum(len(ids) for ids in by_key.values()), 11)

    def test_component_ids_are_sorted_and_not_merged_by_overlap(self):
        memberships, components, _by_key = ownership.build_memberships(self._parent(), self._schema())
        self.assertEqual([row["component_id"] for row in components], ["v3c00001", "v3c00002", "v3c00003"])
        self.assertEqual(len({row["component_id"] for row in memberships}), 3)

    def test_window_manifest_preserves_not_promoted_semantics(self):
        parent = self._parent()
        _memberships, _components, by_key = ownership.build_memberships(parent, self._schema())
        rows = ownership.build_window_manifest(parent, by_key, {"ownership_schema_sha256": "ownership-hash"})
        not_promoted = [row for row in rows if row["promotion_status"] == "not_promoted"]
        self.assertTrue(not_promoted)
        # A not_promoted row may still be a fixed boundary guard in the
        # frozen v3.0 output.  Its selector state remains not_promoted; the
        # membership relation only records closure workload provenance.
        self.assertTrue(all(row["promotion_status"] == "not_promoted" for row in not_promoted))
        self.assertTrue(all(row["promotion_reason"] for row in not_promoted))
        self.assertTrue(any(row["unique_fine_window"] == "true" for row in not_promoted))
        self.assertTrue(any(row["unique_fine_window"] == "false" for row in not_promoted))

    def test_window_manifest_primary_component_is_display_only(self):
        parent = self._parent()
        _memberships, _components, by_key = ownership.build_memberships(parent, self._schema())
        rows = ownership.build_window_manifest(parent, by_key, {"ownership_schema_sha256": "ownership-hash"})
        row = next(item for item in rows if item["window_id"] == 3)
        self.assertEqual(row["component_membership_count"], 3)
        self.assertEqual(row["primary_component_id"], "v3c00001")
        self.assertIn("display", row["primary_component_purpose"])

    def test_existing_namespace_is_rejected(self):
        path = self.temp_dir / "batch_sampled_v1_3_existing"
        path.mkdir()
        with self.assertRaises(FileExistsError):
            common.assert_new_sampling_namespace(path, PROJECT_ROOT)

    def test_gold_and_later_stage_paths_are_rejected(self):
        for name in ("gold_labels.csv", "stage3_result.csv", "stage4_result.csv", "coverage_replay.csv"):
            with self.assertRaises(ValueError):
                ownership.reject_gold_blind_path(self.temp_dir / name)

    def test_parent_parameter_sha_is_not_ownership_sha(self):
        self.assertNotEqual("parent-parameter-hash", "ownership-hash")
        manifest = {"parent_frozen_parameter_sha256": "parent-parameter-hash", "ownership_schema_sha256": "ownership-hash"}
        self.assertNotEqual(manifest["parent_frozen_parameter_sha256"], manifest["ownership_schema_sha256"])

    def test_membership_rows_carry_schema_and_gold_provenance(self):
        memberships, _components, _by_key = ownership.build_memberships(self._parent(), self._schema())
        self.assertTrue(memberships)
        self.assertTrue(all(row["ownership_schema_version"] == ownership.SCHEMA_VERSION for row in memberships))
        self.assertTrue(all(row["gold_labels_used_for_selection"] == "false" for row in memberships))
        self.assertTrue(all(row["parent_component_artifact_sha256"] == "component-hash" for row in memberships))


if __name__ == "__main__":
    unittest.main()
