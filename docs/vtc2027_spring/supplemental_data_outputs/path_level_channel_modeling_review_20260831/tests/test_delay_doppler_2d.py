import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from fit_delay_doppler_2d import (  # noqa: E402
    fit_cell_models,
    fit_weighted_gmm,
    predict_log_density,
    select_cell_model,
)


def _synthetic_cell() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    first = rng.multivariate_normal([2.0, 40.0], [[0.2, 0.05], [0.05, 9.0]], 24)
    second = rng.multivariate_normal([7.0, 95.0], [[0.3, -0.04], [-0.04, 16.0]], 24)
    values = np.vstack([first, second])
    return pd.DataFrame(
        {
            "cell_id": "Urban/MID",
            "scene_id": np.repeat(["scene-a", "scene-b", "scene-c"], 16),
            "track_id": [f"track-{i}" for i in range(len(values))],
            "excess_delay_samples": values[:, 0],
            "absolute_doppler_hz": np.abs(values[:, 1]),
            "doppler_offset_hz": values[:, 1],
            "track_weight_recomputed_primary": 1.0,
        }
    )


def test_synthetic_fit_returns_finite_density_in_physical_coordinates():
    frame = _synthetic_cell()
    values = frame[["excess_delay_samples", "absolute_doppler_hz"]].to_numpy()
    fit = fit_weighted_gmm(values, np.ones(len(frame)), 2)
    assert fit["status"] == "fit_ok"
    model = {
        "center": fit["center"].tolist(),
        "scale": fit["scale"].tolist(),
        "means": (fit["means_standardized"] * fit["scale"] + fit["center"]).tolist(),
        "covariances": [
            np.diag(fit["scale"]) @ covariance @ np.diag(fit["scale"])
            for covariance in fit["covariances_standardized"]
        ],
        "proportions": fit["proportions"].tolist(),
    }
    log_density = predict_log_density(model, values[:5])
    assert np.isfinite(log_density).all()


def test_scene_grouped_cell_selection_has_a_valid_candidate():
    candidates = fit_cell_models(_synthetic_cell(), "Urban/MID")
    selected = select_cell_model(candidates)
    assert selected is not None
    assert selected["status"] == "fit_ok"
    assert np.isfinite(selected["mean_weighted_nlpd"])


def test_physical_covariance_is_positive_definite():
    frame = _synthetic_cell()
    values = frame[["excess_delay_samples", "absolute_doppler_hz"]].to_numpy()
    fit = fit_weighted_gmm(values, np.ones(len(frame)), 2)
    for covariance in fit["covariances_standardized"]:
        assert np.all(np.linalg.eigvalsh(covariance) > 0)
