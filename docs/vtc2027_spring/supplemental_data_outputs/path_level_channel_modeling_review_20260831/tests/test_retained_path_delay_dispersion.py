import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from derive_retained_path_delay_dispersion import (  # noqa: E402
    compute_path_set_delay_dispersion,
    weighted_ecdf,
)


def test_direct_only_path_set_has_zero_dispersion():
    group = pd.DataFrame(
        {
            "excess_delay_samples": [],
            "relative_power_db": [],
        }
    )
    result = compute_path_set_delay_dispersion(group)
    assert result["retained_path_count"] == 0
    assert result["rms_delay_dispersion_samples"] == 0.0


def test_two_path_dispersion_matches_closed_form():
    group = pd.DataFrame(
        {
            "excess_delay_samples": [1.0, 3.0],
            "relative_power_db": [0.0, 0.0],
        }
    )
    result = compute_path_set_delay_dispersion(group)
    expected = np.sqrt(14.0 / 9.0)
    assert np.isclose(result["weighted_mean_delay_samples"], 4.0 / 3.0)
    assert np.isclose(result["rms_delay_dispersion_samples"], expected)


def test_weighted_ecdf_is_monotone_and_ends_at_one():
    x, y = weighted_ecdf(np.array([3.0, 1.0, 1.0]), np.array([1.0, 2.0, 1.0]))
    assert np.all(np.diff(x) > 0)
    assert np.all(np.diff(y) >= 0)
    assert y[-1] == 1.0
