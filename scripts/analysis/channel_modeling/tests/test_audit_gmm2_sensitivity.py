import sys
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

from audit_gmm2_sensitivity import (  # noqa: E402
    fit_gmm2_weighted,
    fit_normal_weighted,
    mixture_logpdf,
    order_components,
)


def test_weighted_normal_fit_uses_observation_weights():
    fit = fit_normal_weighted(np.array([0.0, 0.0, 2.0, 2.0]), np.array([0.5, 0.5, 1.0, 1.0]))
    assert np.isclose(fit["loc"], 4.0 / 3.0)
    assert fit["scale"] > 0.0


def test_weighted_gmm2_recovers_and_orders_two_components():
    values = np.array([-2.2, -2.0, -1.8, 1.8, 2.0, 2.2])
    weights = np.ones(values.size)
    fit = order_components(fit_gmm2_weighted(values, weights, seed=7))
    assert fit["component_weights"][0] > 0.25
    assert fit["component_weights"][1] > 0.25
    assert fit["component_means"][0] < fit["component_means"][1]
    assert fit["mean_separation"] > 3.0


def test_mixture_logpdf_is_finite_for_fitted_components():
    values = np.array([-2.0, -1.0, 1.0, 2.0])
    fit = order_components(fit_gmm2_weighted(values, np.ones(4), seed=11))
    logpdf = mixture_logpdf(values, fit)
    assert np.all(np.isfinite(logpdf))
