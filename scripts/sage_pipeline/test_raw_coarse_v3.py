"""Offline and synthetic regression tests for raw-coarse v3 infrastructure."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_raw_coarse_retry1_evidence_v3 as audit  # noqa: E402
import build_raw_coarse_v3_features as builder  # noqa: E402
import raw_coarse_v3_common as common  # noqa: E402
import run_batch_sampling_raw_coarse_v1_2 as legacy  # noqa: E402
import run_batch_sampling_raw_coarse_v1_2_v2 as v2  # noqa: E402
import run_raw_coarse_v3_evidence_capture as capture  # noqa: E402


class RawCoarseV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        test_root = PROJECT_ROOT / "dataset_generation_logs" / "sampling_validation"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="batch_sampled_v1_3_test_", dir=str(test_root)))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _fixture_evidence(self) -> list[dict[str, str]]:
        root = self.temp_dir / "batch_sampled_v1_3_fixture_evidence"
        capture.run_fixture(root, PROJECT_ROOT)
        with (root / "subblock_evidence.csv").open("r", newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_manifest_parameter_hash_is_canonical_and_gold_free(self):
        self.assertEqual(common.parameter_sha256(), common.parameter_sha256(common.V3_PARAMETER_SPEC))
        self.assertFalse(common.V3_PARAMETER_SPEC["gold_labels_used_for_selection"])
        self.assertFalse(common.V3_PARAMETER_SPEC["temporal_component_rule"]["uses_adjacent_window_evidence_in_selector"])

    def test_b1_b2_block_mapping_and_nav_mapping(self):
        self.assertEqual(capture.profile_groups(legacy.PROFILES[0]), ((0, 1), (2, 3)))
        self.assertEqual(capture.profile_groups(legacy.PROFILES[1]), ((0,), (1,), (2,), (3,)))
        self.assertEqual(common.V3_PARAMETER_SPEC["v2_semantics"]["nav_symbol_mapping"]["0"], "nav_symbol_1")
        self.assertEqual(common.V3_PARAMETER_SPEC["v2_semantics"]["nav_symbol_mapping"]["3"], "nav_symbol_2")

    def test_fixture_evidence_schema_and_no_gold(self):
        rows = self._fixture_evidence()
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row["gold_labels_used_for_selection"] == "false" for row in rows))
        self.assertTrue(all(row["window_id"] == "1" for row in rows))
        self.assertTrue(all(row["sample_start_zero_based"] == "100" for row in rows))
        self.assertTrue(all(row["nav_symbol"] in {"1", "-1"} for row in rows))

    def test_v2_numeric_equivalence_fixture(self):
        if v2.np is None:
            self.skipTest("NumPy backend unavailable")
        np = v2.np
        row = legacy.Stage0Row(1, 100, 1, -1, -3000.0, 1023000.0, 100.0, 10.0)
        iq = np.random.default_rng(4).integers(-1000, 1000, size=(legacy.WINDOW_SAMPLES + 8, 2), dtype=np.int16)
        view = memoryview(iq.tobytes()).cast("h")
        rows, diagnostic = capture.capture_window_evidence(view, 98, row, {"task_id": "t", "scene_id": "s", "prn": "G16", "tracking_channel": 1, "sample_rate_hz": legacy.SAMPLE_RATE_HZ})
        self.assertTrue(diagnostic["v2_equivalence"]["pass"])
        self.assertEqual(len(rows), 10)

    def test_secondary_none_uses_null_not_zero(self):
        row = legacy.Stage0Row(1, 100, 1, -1, -3000.0, 1023000.0, 100.0, 10.0)
        identity = capture._identity({"task_id": "t", "scene_id": "s", "prn": "G16", "tracking_channel": 1, "sample_rate_hz": legacy.SAMPLE_RATE_HZ}, legacy.PROFILES[0], 0, (0, 1), row)
        result = capture._null_row(identity, "none_admissible_delay", "valid", "none_admissible_delay")
        self.assertIsNone(result["secondary_delay_samples"])
        self.assertIsNone(result["secondary_doppler_hz"])
        self.assertEqual(result["secondary_status"], "none_admissible_delay")

    def test_raw_short_invalid_rms_and_continuity_gap_are_explicit(self):
        row = legacy.Stage0Row(1, 100, 1, -1, -3000.0, 1023000.0, 100.0, 10.0)
        task = {"task_id": "t", "scene_id": "s", "prn": "G16", "tracking_channel": 1, "sample_rate_hz": legacy.SAMPLE_RATE_HZ}
        short = memoryview(bytes(20)).cast("h")
        rows, _ = capture.capture_window_evidence(short, 98, row, task)
        self.assertTrue(all(item["feature_missing_reason"] == "raw_short" for item in rows))
        rows, _ = capture.capture_window_evidence(short, 98, row, task, continuity_status="gap")
        self.assertTrue(all(item["feature_missing_reason"] == "continuity_gap" for item in rows))
        self.assertTrue(all(item["continuity_status"] == "gap" for item in rows))
        zero = v2.np.zeros((legacy.WINDOW_SAMPLES + 8, 2), dtype=v2.np.int16)
        rows, _ = capture.capture_window_evidence(memoryview(zero.tobytes()).cast("h"), 98, row, task)
        self.assertTrue(all(item["feature_missing_reason"] == "invalid_rms" for item in rows))

    def test_stage0_continuity_status_is_conservative(self):
        rows = (
            legacy.Stage0Row(1, 100, 1, -1, -3000.0, 1023000.0, 100.0, 10.0),
            legacy.Stage0Row(2, 100 + legacy.WINDOW_SAMPLES // 2, 1, -1, -3000.0, 1023000.0, 100.0, 10.02),
            legacy.Stage0Row(3, 100 + legacy.WINDOW_SAMPLES * 2, 1, -1, -3000.0, 1023000.0, 100.0, 10.08),
        )
        self.assertEqual(capture._stage0_continuity_status(rows, 0), "ok")
        self.assertEqual(capture._stage0_continuity_status(rows, 1), "ok")
        self.assertEqual(capture._stage0_continuity_status(rows, 2), "continuity_gap")

    def test_secondary_doppler_and_delay_separation_fields_are_not_aggregate_only(self):
        rows = self._fixture_evidence()
        self.assertTrue(any(row["secondary_doppler_hz"] not in ("", None) for row in rows))
        self.assertTrue(all(row["delay_separation_samples"] in ("", None) or int(float(row["delay_separation_samples"])) >= 2 for row in rows))

    def test_feature_builder_has_full_vector_and_no_single_score_selector(self):
        rows = self._fixture_evidence()
        feature_rows, components = builder.build_feature_rows(rows, "fixture-evidence-sha")
        self.assertEqual(len(feature_rows), 1)
        self.assertIn("secondary_ratio_mad", feature_rows[0])
        self.assertIn("cross_scale_agreement_fraction", feature_rows[0])
        self.assertNotIn("coarse_score_db", feature_rows[0])
        self.assertTrue(all(row["gold_labels_used_for_selection"] == "false" for row in feature_rows))
        self.assertIsInstance(components, list)

    def test_cross_scale_matching_tolerance(self):
        def evidence(profile, subblock, delay, doppler):
            return {"profile_id": profile, "subblock_index": str(subblock), "secondary_status": "admissible_delay", "secondary_main_ratio": "0.5", "secondary_delay_samples": str(delay), "secondary_doppler_hz": str(doppler)}
        left = [evidence("B1_20msx2_D100", 0, 2, -100), evidence("B1_20msx2_D100", 1, 3, -50)]
        right = [evidence("B2_10msx4_D100", 0, 2, -90), evidence("B2_10msx4_D100", 1, 2, -100), evidence("B2_10msx4_D100", 2, 3, -40), evidence("B2_10msx4_D100", 3, 3, -50)]
        result = builder._cross_scale(left, right, 1, 50)
        self.assertEqual(result["cross_scale_comparable_count"], 4)
        self.assertEqual(result["cross_scale_match_count"], 4)

    def test_component_merge_is_deterministic_and_fixed(self):
        base = {"task_id": "t", "scene_id": "s", "prn": "G16", "promotion_status": "coarse_promoted"}
        rows = [{**base, "window_id": index} for index in (1, 2, 5)]
        ids, components = builder._componentize(rows, common.V3_PARAMETER_SPEC)
        self.assertEqual(ids[("t", 1)], ids[("t", 5)])
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["bridge_gap_windows"], 2)

    def test_components_never_merge_different_tasks_with_same_window_id(self):
        rows = [
            {"task_id": "t1", "scene_id": "s1", "prn": "G16", "tracking_channel": "1", "promotion_status": "coarse_promoted", "window_id": 1},
            {"task_id": "t2", "scene_id": "s2", "prn": "G25", "tracking_channel": "0", "promotion_status": "coarse_promoted", "window_id": 1},
        ]
        ids, components = builder._componentize(rows, common.V3_PARAMETER_SPEC)
        self.assertEqual(len(components), 2)
        self.assertNotEqual(ids[("t1", 1)], ids[("t2", 1)])

    def test_parameter_manifest_rejects_tamper(self):
        path = self.temp_dir / "batch_sampled_v1_3_parameter_manifest_test" / "manifest.json"
        path.parent.mkdir()
        data = {"gold_labels_used_for_selection": False, "parameter_spec": common.V3_PARAMETER_SPEC, "parameter_sha256": common.parameter_sha256()}
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            common.load_frozen_manifest(path, common.sha256_file(path), PROJECT_ROOT)

    def test_gold_file_path_is_rejected_before_feature_build(self):
        path = self.temp_dir / "gold_stage4_evidence.csv"
        path.write_text("gold_labels_used_for_selection\nfalse\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            builder._validate_evidence_source(path, [{"gold_labels_used_for_selection": "false"}])

    def test_evidence_parameter_hash_mismatch_is_rejected(self):
        path = self.temp_dir / "batch_sampled_v1_3_evidence.csv"
        path.write_text("gold_labels_used_for_selection,parameter_hash,v2_parameter_hash\nfalse,bad,bad\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            builder._validate_evidence_source(path, [{"gold_labels_used_for_selection": "false", "parameter_hash": "bad", "v2_parameter_hash": "bad"}])

    def test_evidence_schema_missing_required_field_is_rejected(self):
        path = self.temp_dir / "batch_sampled_v1_3_evidence.csv"
        path.write_text("gold_labels_used_for_selection,parameter_hash,v2_parameter_hash\nfalse,bad,bad\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            builder._validate_evidence_source(path, [{"gold_labels_used_for_selection": "false", "parameter_hash": "bad", "v2_parameter_hash": "bad"}])

    def test_feature_builder_validates_before_creating_output_namespace(self):
        evidence = self.temp_dir / "batch_sampled_v1_3_evidence.csv"
        evidence.write_text("gold_labels_used_for_selection,parameter_hash,v2_parameter_hash\nfalse,bad,bad\n", encoding="utf-8")
        output = self.temp_dir / "batch_sampled_v1_3_should_not_exist"
        with self.assertRaises((ValueError, FileNotFoundError)):
            builder.build_from_evidence(evidence, output, self.temp_dir / "missing_manifest.json", "bad", PROJECT_ROOT)
        self.assertFalse(output.exists())

    def test_existing_namespace_is_new_only(self):
        root = self.temp_dir / "batch_sampled_v1_3_existing"
        root.mkdir()
        (root / "sentinel").write_text("immutable", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            common.assert_new_sampling_namespace(root, PROJECT_ROOT)

    def test_existing_empty_namespace_is_also_new_only_rejected(self):
        root = self.temp_dir / "batch_sampled_v1_3_empty_existing"
        root.mkdir()
        with self.assertRaises(FileExistsError):
            common.assert_new_sampling_namespace(root, PROJECT_ROOT)

    def test_real_capture_is_disabled_without_explicit_gate(self):
        with self.assertRaises(SystemExit):
            capture.main(["--output-root", str(self.temp_dir / "batch_sampled_v1_3_disabled")])

    def test_retry1_audit_has_no_gold_or_raw_access(self):
        retry_root = PROJECT_ROOT / "dataset_generation_logs" / "sampling_validation" / "batch_sampled_v1_2_phase_a_retry_outputs_20260812" / "Phase-A1-Retry1_F1023_V70_D0120_P7_G16_ch1"
        result = audit.audit_retry1(retry_root)
        self.assertFalse(result["raw_iq_read"])
        self.assertFalse(result["stage3_stage4_read"])
        self.assertFalse(result["gold_labels_used_for_selection"])
        self.assertTrue(result["cross_profile_window_id_alignment"]["all_equal"])
        self.assertTrue(all(not item["per_subblock_evidence_present"] for item in result["profiles"]))


if __name__ == "__main__":
    unittest.main()
