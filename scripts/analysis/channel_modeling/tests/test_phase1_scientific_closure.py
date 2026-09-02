import sys
from pathlib import Path


HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

from build_phase1_scientific_closure import (  # noqa: E402
    CELL_ORDER,
    _interaction_difference_in_differences,
    _track_representatives,
    classify_continuous_evidence,
    classify_effect,
    loso_stability_label,
    weighted_quantile,
)


def test_weighted_quantile_uses_primary_observation_mass():
    assert weighted_quantile([1.0, 2.0, 10.0], [1.0, 1.0, 0.5], 0.5) == 2.0


def test_effect_classification_requires_interval_and_support_evidence():
    result = classify_effect((0.1, 0.4, 0.8), "DATA_SUPPORTED", "STABLE")
    assert result["effect_direction"] == "HIGHER"
    assert result["support_strength"] == "DATA_SUPPORTED"
    assert result["scientific_status"] == "SUPPORTED"

    result = classify_effect((-0.2, 0.1, 0.4), "DATA_SUPPORTED", "STABLE")
    assert result["scientific_status"] == "NO_ROBUST_DIFFERENCE"

    result = classify_effect((0.1, 0.4, 0.8), "NO_DIRECT_SUPPORT", "INCONCLUSIVE")
    assert result["scientific_status"] == "NOT_SUPPORTED"


def test_loso_stability_is_margin_and_fold_aware():
    assert loso_stability_label(12, 0.20) == "STABLE"
    assert loso_stability_label(5, 0.03) == "MOSTLY_ROBUST"
    assert loso_stability_label(5, 0.001) == "SENSITIVE"
    assert loso_stability_label(1, 0.5) == "INCONCLUSIVE"


def test_continuous_elevation_labels_weak_and_insufficient_evidence():
    assert classify_continuous_evidence("DATA_SUPPORTED", 0.1, 0.2) == "ROBUST"
    assert classify_continuous_evidence("DATA_SUPPORTED", -0.1, 0.2) == "WEAK"
    assert classify_continuous_evidence("DATA_SUPPORTED", -0.2, -0.1) == "ROBUST"
    assert classify_continuous_evidence("PRIOR_DOMINANT", None, None) == "INSUFFICIENT"


def test_cell_order_is_frozen_and_empty_highway_low_is_present():
    assert len(CELL_ORDER) == 12
    assert CELL_ORDER[0] == "Urban__LOW"
    assert CELL_ORDER[-1] == "Highway/Open__HIGH"
    assert "Highway/Open__LOW" in CELL_ORDER


def test_track_representative_preserves_observation_count_for_persistence_proxy():
    rows = [
        {"track_id": "T1", "scene_id": "S1", "run_id": "R1", "environment_class": "Urban", "elevation_band": "MID", "excess_delay_samples": "1", "doppler_offset_hz": "2", "relative_power_db": "-3"},
        {"track_id": "T1", "scene_id": "S1", "run_id": "R1", "environment_class": "Urban", "elevation_band": "MID", "excess_delay_samples": "2", "doppler_offset_hz": "3", "relative_power_db": "-4"},
    ]
    representative = _track_representatives(rows)[0]
    assert representative["track_observation_count"] == 2


def test_interaction_is_difference_in_differences_against_other_environments():
    rows = [
        {"environment_class": "Urban", "elevation_band": "LOW", "excess_delay_samples": 1.0, "weight": 1.0},
        {"environment_class": "Urban", "elevation_band": "HIGH", "excess_delay_samples": 11.0, "weight": 1.0},
        {"environment_class": "Mountain/Valley", "elevation_band": "LOW", "excess_delay_samples": 2.0, "weight": 1.0},
        {"environment_class": "Mountain/Valley", "elevation_band": "HIGH", "excess_delay_samples": 4.0, "weight": 1.0},
    ]
    assert _interaction_difference_in_differences(rows, "excess_delay_samples", "Urban", "LOW", "HIGH") == 8.0
