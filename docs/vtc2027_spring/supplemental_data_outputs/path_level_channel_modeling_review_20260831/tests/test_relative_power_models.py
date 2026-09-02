import sys
from pathlib import Path

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from fit_relative_power_models import evaluate_power_pdf, fit_power_candidates  # noqa: E402


def _integral(model: dict) -> float:
    x = np.linspace(-80.0, 5.0, 20000)
    return float(np.trapezoid(evaluate_power_pdf(model, x), x))


def test_candidate_pdfs_are_normalized_in_dB():
    rng = np.random.default_rng(21)
    values = np.r_[rng.normal(-8, 1.2, 80), rng.normal(-3, 0.8, 80)]
    weights = np.ones(len(values))
    candidates = fit_power_candidates(values, weights)
    valid = [item for item in candidates if item.get("status") == "fit_ok"]
    assert any(item["family"] == "beta_linear_ratio" for item in valid)
    for candidate in valid:
        assert 0.98 < _integral({"family": candidate["family"], "parameters": candidate["parameters"]}) < 1.02


def test_linear_power_ratios_are_in_open_unit_interval():
    values = np.array([-1.0, -3.0, -7.0, -12.0])
    ratios = np.power(10.0, values / 10.0)
    assert np.all((ratios > 0) & (ratios < 1))


def test_invalid_input_is_rejected():
    values = np.array([-1.0, np.nan])
    weights = np.ones(2)
    try:
        fit_power_candidates(values, weights)
    except ValueError as error:
        assert "finite" in str(error)
    else:
        raise AssertionError("non-finite input was not rejected")
