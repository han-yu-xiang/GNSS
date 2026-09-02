import sys
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from fit_power_delay_and_rms_cdf import (  # noqa: E402
    empirical_cdf,
    fit_weighted_power_delay_line,
    power_weighted_delay_moments,
)


def test_weighted_power_delay_line_recovers_known_relation():
    delay = np.array([1.0, 2.0, 3.0, 4.0])
    power_db = -2.0 - 3.0 * delay
    weights = np.array([1.0, 2.0, 1.0, 3.0])

    result = fit_weighted_power_delay_line(delay, power_db, weights)

    assert np.isclose(result["intercept_db"], -2.0)
    assert np.isclose(result["slope_db_per_sample"], -3.0)
    assert np.isclose(result["weighted_r_squared"], 1.0)


def test_power_weighted_delay_moments_include_direct_reference_once():
    result = power_weighted_delay_moments(
        secondary_delays_samples=np.array([2.0]),
        secondary_relative_power_db=np.array([0.0]),
    )

    assert np.isclose(result["mean_delay_samples"], 1.0)
    assert np.isclose(result["rms_delay_dispersion_samples"], 1.0)
    assert result["path_count_including_direct"] == 2


def test_empirical_cdf_collapses_duplicate_values_at_their_full_mass():
    x, probability = empirical_cdf(np.array([2.0, 1.0, 1.0]))

    assert np.array_equal(x, np.array([1.0, 2.0]))
    assert np.allclose(probability, np.array([2.0 / 3.0, 1.0]))
