import sys
from pathlib import Path


HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

from audit_stage3_academic_population import (  # noqa: E402
    canonical_window_id,
    classify_stage4_outcome,
    elevation_band,
    strict_stage4_confirmation,
)


def test_elevation_band_uses_frozen_half_open_bins():
    assert elevation_band(0.0) == "LOW"
    assert elevation_band(29.999) == "LOW"
    assert elevation_band(30.0) == "MID"
    assert elevation_band(59.999) == "MID"
    assert elevation_band(60.0) == "HIGH"
    assert elevation_band(90.0) == "HIGH"
    assert elevation_band(-0.1) == ""
    assert elevation_band(90.1) == ""


def test_canonical_window_id_rejects_non_integral_ids():
    assert canonical_window_id("12") == "12"
    assert canonical_window_id("12.0") == "12"
    assert canonical_window_id("12.25") == ""
    assert canonical_window_id("") == ""


def test_strict_stage4_confirmation_requires_joint_valid_and_a_multipath_path():
    confirmed, reasons = strict_stage4_confirmation(
        {"joint_valid": "1", "joint_multipath_count": "1"},
        [{"is_multipath": "0"}, {"is_multipath": "1"}],
    )
    assert confirmed is True
    assert reasons == []

    confirmed, reasons = strict_stage4_confirmation(
        {"joint_valid": "1", "joint_multipath_count": "1"},
        [{"is_multipath": "0"}],
    )
    assert confirmed is False
    assert "joint_multipath_count_mismatch" in reasons


def test_stage4_outcome_distinguishes_cap_missing_from_available_rejection():
    assert classify_stage4_outcome(
        stage4_summary=None, reliable_rank=9, confirmed=False
    ) == "stage4_missing_due_to_maximum_joint_centers_cap"
    assert classify_stage4_outcome(
        stage4_summary=None, reliable_rank=3, confirmed=False
    ) == "stage4_missing_after_candidate_gate"
    assert classify_stage4_outcome(
        stage4_summary={"joint_valid": "1"}, reliable_rank=3, confirmed=False
    ) == "stage4_available_rejected"
    assert classify_stage4_outcome(
        stage4_summary={"joint_valid": "1"}, reliable_rank=3, confirmed=True
    ) == "stage4_confirmed"
