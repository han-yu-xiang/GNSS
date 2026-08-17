import unittest
from pathlib import Path

from generate_batch_sampling_plan_v1_1 import (
    BlockConfig,
    GOLD_TASKS,
    add_adaptive_blocks,
    initial_continuous_blocks,
    load_geometry_result,
    load_geometry_result_tow,
    load_stage0,
    task_result_dir,
    stage1_candidate_seeds,
)


def synthetic_stage0_rows(count: int):
    rows = []
    for window_id in range(1, count + 1):
        rows.append(
            {
                "window_id": window_id,
                "time_bin_index": min(23, (window_id - 1) * 24 // count),
            }
        )
    return rows


def synthetic_stage1_rows(count: int):
    rows = []
    for window_id in range(1, count + 1):
        rows.append(
            {
                "window_id": window_id,
                "scan_valid_value": 1,
                "peak1_power_value": float(window_id),
                "peak2_power_value": float(window_id),
                "two_peak_value": 0,
            }
        )
    return rows


class BatchSamplingV11Tests(unittest.TestCase):
    def test_candidate_seed_selection_cannot_see_hidden_rows(self):
        rows = synthetic_stage1_rows(100)
        hidden_high_score = rows[-1]["window_id"]
        exposed = set(range(1, 25))
        seeds = stage1_candidate_seeds(rows, exposed)
        self.assertTrue(seeds)
        self.assertNotIn(hidden_high_score, seeds)
        self.assertLessEqual(max(seeds), 24)

    def test_initial_selection_is_continuous_and_budgeted(self):
        rows = synthetic_stage0_rows(2400)
        config = BlockConfig("test_blocks11_budget1200", 11, 1200, 800)
        selected, reasons, warnings = initial_continuous_blocks(rows, config, "seed_00")
        self.assertLessEqual(len(selected), config.initial_budget)
        self.assertEqual(selected, set(reasons))
        self.assertTrue(all(reasons[window_id] for window_id in selected))
        self.assertTrue(any("initial_continuous_block_L11" in reason for values in reasons.values() for reason in values))
        self.assertIsInstance(warnings, list)

    def test_adaptive_phase_uses_fixed_pm5_block_and_respects_extended_budget(self):
        universe = set(range(1, 2501))
        config = BlockConfig("test_blocks21_budget1300", 21, 1300, 800)
        selected, reasons, warnings, pm2_added, pm5_added = add_adaptive_blocks(
            set(), range(10, 2500, 12), universe, config
        )
        self.assertLessEqual(len(selected), 1300)
        self.assertGreater(len(selected), 1200)
        self.assertGreater(pm2_added, 0)
        self.assertGreater(pm5_added, 0)
        self.assertTrue(any("_pm5" in reason for values in reasons.values() for reason in values))
        self.assertIsInstance(warnings, list)

    def test_tow_geometry_alignment_is_independent_of_recording_time_offset(self):
        project_root = Path(__file__).resolve().parents[2]
        task = next(task for task in GOLD_TASKS if task.task_id == "waveA_F1023_V70_D0120_P7_G16_ch1")
        stage0 = load_stage0(task_result_dir(project_root, task) / "stage0_valid_40ms_windows.csv")
        legacy = load_geometry_result(project_root / "scenes" / task.scene_id, task.prn, stage0)
        tow_aligned = load_geometry_result_tow(project_root / "scenes" / task.scene_id, task.prn, stage0)
        self.assertEqual(legacy.status, "warning_fallback")
        self.assertEqual(tow_aligned.status, "verified")
        self.assertGreaterEqual(tow_aligned.coverage_ratio or 0.0, 0.90)
        self.assertLessEqual(tow_aligned.p95_delta_seconds or float("inf"), 5.0)
        self.assertEqual(getattr(tow_aligned, "gps_utc_offset_seconds", None), 17.0)


if __name__ == "__main__":
    unittest.main()
