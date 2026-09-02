import sys
from pathlib import Path


HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

from audit_environment_elevation_stage3_path_model import (  # noqa: E402
    STAGE4_PARAMETER_REL,
    expected_cell_keys,
    is_near_psd_correlation,
    track_weights_conserve,
)


def test_expected_cells_preserve_all_environment_and_band_keys():
    cells = expected_cell_keys(
        ("Urban", "Special Reflective"),
        ("LOW", "MID", "HIGH"),
    )
    assert cells == (
        "Urban__LOW",
        "Urban__MID",
        "Urban__HIGH",
        "Special Reflective__LOW",
        "Special Reflective__MID",
        "Special Reflective__HIGH",
    )


def test_correlation_gate_requires_unit_diagonal_and_nonnegative_eigenvalues():
    assert is_near_psd_correlation([[1.0, 0.2], [0.2, 1.0]])
    assert not is_near_psd_correlation([[1.0, 1.2], [1.2, 1.0]])
    assert not is_near_psd_correlation([[1.0, 0.0], [0.0, 0.9]])


def test_track_weight_conservation_is_checked_independently():
    rows = [
        {"track_id": "T1", "track_weight": "0.5"},
        {"track_id": "T1", "track_weight": "0.5"},
        {"track_id": "T2", "track_weight": "1.0"},
    ]
    assert track_weights_conserve(rows)
    rows[-1]["track_weight"] = "0.9"
    assert not track_weights_conserve(rows)


def test_stage4_reference_is_the_frozen_2026_parameter_set():
    assert "parameter_set_id=parameters_20260825_stage4_path_v1" in str(STAGE4_PARAMETER_REL)
