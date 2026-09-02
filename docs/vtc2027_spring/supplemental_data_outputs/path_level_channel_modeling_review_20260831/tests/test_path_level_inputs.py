import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from audit_path_level_inputs import audit_population  # noqa: E402


def minimal_row() -> dict:
    return {
        "elevation_ready": True,
        "cell_ready": True,
        "environment_class": "Urban",
        "elevation_band": "LOW",
        "track_id": "track-1",
        "track_weight_recomputed_primary": 1.0,
        "excess_delay_samples": 1.2,
        "absolute_doppler_hz": 50.0,
        "relative_power_db": -8.0,
        "doppler_offset_hz": -50.0,
        "scene_id": "scene-1",
        "run_id": "run-1",
        "center_window_id": 1,
    }


def test_audit_accepts_finite_weighted_rows_without_expected_counts():
    frame = pd.DataFrame([minimal_row()])
    result = audit_population(frame, enforce_expected_counts=False)
    assert result["row_counts"]["primary_population_rows"] == 1
    assert result["track_counts"]["unique_tracks"] == 1


def test_audit_rejects_nonfinite_model_value():
    row = minimal_row()
    row["absolute_doppler_hz"] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        audit_population(pd.DataFrame([row]), enforce_expected_counts=False)


def test_audit_rejects_invalid_track_weight_total():
    row = minimal_row()
    row["track_weight_recomputed_primary"] = 0.5
    with pytest.raises(ValueError, match="do not sum to one"):
        audit_population(pd.DataFrame([row]), enforce_expected_counts=False)
