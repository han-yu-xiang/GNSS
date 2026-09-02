import sys
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from fit_delay_doppler_1d import (  # noqa: E402
    evaluate_model_cdf,
    fit_weighted_lognormal,
    fit_weighted_log1p_gaussian_mixture,
    select_candidate,
)


def test_weighted_lognormal_cdf_is_bounded_and_monotone():
    values = np.array([1.0, 1.2, 1.5, 2.0, 2.8, 3.5])
    weights = np.ones_like(values)
    model = fit_weighted_lognormal(values, weights)
    grid = np.linspace(0.0, 8.0, 500)
    cdf = evaluate_model_cdf(model, grid)
    assert cdf[0] == 0.0
    assert np.all(np.diff(cdf) >= -1e-12)
    assert 0.0 <= cdf.min() <= cdf.max() <= 1.0
    assert cdf[-1] > 0.99


def test_log1p_gaussian_mixture_recovers_two_doppler_concentrations():
    rng = np.random.default_rng(31)
    values = np.r_[rng.normal(48.0, 2.0, 80), rng.normal(99.0, 2.5, 80)]
    weights = np.ones_like(values)
    model = fit_weighted_log1p_gaussian_mixture(values, weights, 2)
    means_hz = np.sort(np.expm1(np.asarray(model["means_log1p"])))
    assert np.allclose(means_hz, [48.0, 99.0], atol=5.0)
    grid = np.linspace(0.0, 140.0, 500)
    cdf = evaluate_model_cdf(model, grid)
    assert np.all(np.diff(cdf) >= -1e-12)
    assert cdf[-1] > 0.99


def test_candidate_selection_uses_validation_score_then_bic():
    candidates = [
        {"status": "fit_ok", "validation_nlpd": 2.2, "bic": 80.0, "name": "a"},
        {"status": "fit_ok", "validation_nlpd": 1.8, "bic": 120.0, "name": "b"},
        {"status": "rejected", "validation_nlpd": 1.0, "bic": 10.0, "name": "c"},
    ]
    assert select_candidate(candidates)["name"] == "b"
