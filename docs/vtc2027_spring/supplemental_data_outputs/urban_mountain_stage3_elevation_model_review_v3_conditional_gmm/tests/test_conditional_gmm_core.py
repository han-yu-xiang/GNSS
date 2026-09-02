from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/conditional_gmm_core.py"
SPEC = importlib.util.spec_from_file_location("conditional_gmm_core", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load conditional GMM core")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def synthetic_rows(seed: int = 7, count: int = 120) -> list[dict[str, object]]:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for index in range(count):
        component = index % 2
        environment = "Urban" if index % 2 == 0 else "Mountain/Valley"
        band = ("LOW", "MID", "HIGH")[index % 3]
        center = np.asarray([0.0, 0.0, -8.0]) if component == 0 else np.asarray([1.2, 0.8, -2.0])
        value = center + rng.normal(0.0, 0.12, size=3)
        rows.append(
            {
                "log_excess_delay": value[0],
                "log1p_absolute_doppler": value[1],
                "relative_power_db": value[2],
                "track_weight_recomputed_primary": 1.0,
                "environment_class": environment,
                "cell_id": f"{environment}__{band}",
                "cell_ready": "1",
            }
        )
    return rows


class ConditionalGMMCoreTests(unittest.TestCase):
    def test_shrink_probabilities_moves_toward_parent(self) -> None:
        local = np.asarray([0.9, 0.1])
        parent = np.asarray([0.2, 0.8])
        weak = MODULE.shrink_probabilities(local, parent, 4.0)
        strong = MODULE.shrink_probabilities(local, parent, 32.0)
        self.assertLess(np.linalg.norm(strong - parent / parent.sum()), np.linalg.norm(weak - parent / parent.sum()))

    def test_two_component_model_recovers_separated_clusters(self) -> None:
        rows = synthetic_rows()
        config = MODULE.ConditionalGMMConfig(component_count=2, pooling_kappa=8.0, restart_count=4, seed=23)
        model = MODULE.fit_conditional_gmm(rows, config)
        self.assertEqual(model.global_weights.shape, (2,))
        self.assertEqual(model.global_means.shape, (2, 3))
        self.assertTrue(np.all(np.linalg.eigvalsh(model.shared_covariances[0]) >= config.covariance_floor - 1e-10))
        self.assertTrue(np.all(np.linalg.eigvalsh(model.shared_covariances[1]) >= config.covariance_floor - 1e-10))
        self.assertLess(model.global_means[0, 2], model.global_means[1, 2])
        self.assertAlmostEqual(float(np.sum(model.global_weights)), 1.0, places=12)

    def test_predictive_density_and_sampling_are_finite(self) -> None:
        rows = synthetic_rows()
        model = MODULE.fit_conditional_gmm(rows, MODULE.ConditionalGMMConfig(2, 8.0, restart_count=3, seed=31))
        log_density = MODULE.log_predictive_density(model, rows[:10])
        samples = MODULE.sample_conditional(model, "Urban", "LOW", 128, seed=41)
        self.assertTrue(np.all(np.isfinite(log_density)))
        self.assertEqual(samples.shape, (128, 3))
        self.assertTrue(np.all(np.isfinite(samples)))

    def test_fit_is_deterministic_for_same_seed(self) -> None:
        rows = synthetic_rows()
        config = MODULE.ConditionalGMMConfig(2, 8.0, restart_count=3, seed=59)
        first = MODULE.fit_conditional_gmm(rows, config)
        second = MODULE.fit_conditional_gmm(rows, config)
        np.testing.assert_allclose(first.global_means, second.global_means, atol=1e-12)
        np.testing.assert_allclose(first.shared_covariances, second.shared_covariances, atol=1e-12)
        np.testing.assert_allclose(first.global_weights, second.global_weights, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
