import unittest

from generate_batch_sampling_plan import (
    GeometryResult,
    TaskSpec,
    build_sampling_plan,
    coverage_for_center,
    stable_int,
)


def synthetic_rows(count: int):
    rows = []
    for index in range(count):
        rows.append(
            {
                "window_id": index + 1,
                "recording_time_s": f"{index * 0.04:.6f}",
                "tow_s": f"{index * 0.04:.6f}",
                "cn0_db_hz": f"{35.0 + (index % 30) * 0.1:.3f}",
                "vehicle_speed_kmh": "20.0",
                "relative_doppler_bound_hz": "40.0",
                "recording_time_s_value": index * 0.04,
                "tow_s_value": index * 0.04,
                "cn0_value": 35.0 + (index % 30) * 0.1,
                "speed_value": 20.0,
                "doppler_bound_value": 40.0,
            }
        )
    return rows


class SamplingPlannerTests(unittest.TestCase):
    def setUp(self):
        self.task = TaskSpec(
            "test_scene_G01_ch0",
            "test_scene",
            "G01",
            0,
            10_230_000,
            "sage_results/nav_sage_v2/G01",
            "test",
        )
        self.geometry = GeometryResult(
            "warning_fallback",
            "test geometry unavailable",
            "",
            "",
            None,
            None,
            None,
            {},
        )

    def test_stable_seed_is_repeatable(self):
        self.assertEqual(stable_int("scene", "seed_00"), stable_int("scene", "seed_00"))
        self.assertNotEqual(stable_int("scene", "seed_00"), stable_int("scene", "seed_01"))

    def test_short_catalog_is_full_scan_equivalent(self):
        plan, manifest = build_sampling_plan(self.task, synthetic_rows(1000), self.geometry, "seed_00")
        self.assertEqual(plan["profile_version"], "batch-sampled-v1")
        self.assertEqual(plan["selection"]["selected_window_count"], 1000)
        self.assertEqual(plan["selection"]["not_selected_window_count"], 0)
        self.assertTrue(all(row["selected_status"] == "selected" for row in manifest))
        self.assertTrue(all(row["sampling_mode"] == "full-scan-equivalent" for row in manifest))

    def test_long_catalog_respects_budget_and_time_minimum(self):
        plan, manifest = build_sampling_plan(self.task, synthetic_rows(2400), self.geometry, "seed_00")
        selected = [row for row in manifest if row["selected_status"] == "selected"]
        self.assertLessEqual(len(selected), 1200)
        self.assertEqual(len(manifest), 2400)
        self.assertEqual({row["window_id"] for row in manifest}, set(range(1, 2401)))
        for time_bin in range(24):
            stratum = f"time_{time_bin:02d}"
            count = sum(
                stratum == row["time_stratum"] and row["selected_status"] == "selected"
                for row in manifest
            )
            self.assertGreaterEqual(count, 20)
        self.assertEqual(plan["selection"]["selected_window_count"], len(selected))
        self.assertGreater(plan["selection"]["stage1_reduction"], 0.0)

    def test_coverage_requires_pm2_closure(self):
        selected = set(range(1, 11))
        universe = set(range(1, 21))
        self.assertEqual(coverage_for_center(5, selected, universe), (True, True, "covered"))
        self.assertEqual(
            coverage_for_center(10, selected, universe),
            (True, False, "closure_not_selected:11,12"),
        )


if __name__ == "__main__":
    unittest.main()
