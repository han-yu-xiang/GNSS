import sys
from pathlib import Path


HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

from build_environment_elevation_stage3_path_model import (  # noqa: E402
    ELEVATION_BANDS,
    family_parameter_count,
    elevation_band_for_stage3,
    load_stage3_population,
    continuous_elevation_result,
    stage4_sensitivity_result,
    support_label,
    _bootstrap_scope_rows,
    weighted_rank,
    weighted_summary,
    weight_for_track_size,
)


def test_stage3_elevation_bins_are_frozen_half_open_except_high_endpoint():
    assert ELEVATION_BANDS == ("LOW", "MID", "HIGH")
    assert elevation_band_for_stage3(0.0) == "LOW"
    assert elevation_band_for_stage3(29.999) == "LOW"
    assert elevation_band_for_stage3(30.0) == "MID"
    assert elevation_band_for_stage3(59.999) == "MID"
    assert elevation_band_for_stage3(60.0) == "HIGH"
    assert elevation_band_for_stage3(90.0) == "HIGH"


def test_weight_is_reciprocal_of_conservative_track_size():
    assert weight_for_track_size(1) == 1.0
    assert weight_for_track_size(4) == 0.25


def test_weighted_summary_reports_weighted_quantiles_and_kish_effective_count():
    summary = weighted_summary([1.0, 2.0, 10.0], [1.0, 1.0, 0.5])
    assert summary["count"] == 3
    assert summary["sum_weights"] == 2.5
    assert abs(summary["kish_effective_n"] - (2.5**2 / (1.0**2 + 1.0**2 + 0.5**2))) < 1e-12
    assert summary["median"] == 2.0


def test_weighted_rank_respects_duplicate_weight_mass():
    ranks = weighted_rank([0.0, 10.0], [3.0, 1.0])
    assert ranks[0] < ranks[1]
    assert ranks[0] == 0.375
    assert ranks[1] == 0.875


def test_support_label_uses_scene_and_effective_support_not_rows_alone():
    assert support_label(0, 0, 0.0) == "NO_DIRECT_SUPPORT"
    assert support_label(20, 1, 20.0) == "PRIOR_DOMINANT"
    assert support_label(20, 2, 5.0) == "SPARSE_PARTIAL_POOLING"
    assert support_label(20, 3, 10.0) == "DATA_SUPPORTED"


def test_candidate_parameter_counts_distinguish_student_t():
    assert family_parameter_count("normal") == 2
    assert family_parameter_count("student_t") == 3


def test_bootstrap_can_run_without_stage3_parent_lookup_for_stage4_rows():
    rows = [
        {
            "scene_id": "S1",
            "run_id": "R1",
            "environment_class": "Urban",
            "elevation_band": "MID",
            "weight": 1.0,
            "excess_delay_samples": 1.0,
            "doppler_offset_hz": -10.0,
            "relative_power_db": -3.0,
        },
        {
            "scene_id": "S2",
            "run_id": "R2",
            "environment_class": "Urban",
            "elevation_band": "MID",
            "weight": 1.0,
            "excess_delay_samples": 2.0,
            "doppler_offset_hz": 10.0,
            "relative_power_db": -4.0,
        },
    ]
    families = {
        "excess_delay_samples": "normal",
        "doppler_offset_hz": "normal",
        "relative_power_db": "normal",
    }
    result = _bootstrap_scope_rows(rows, families, {}, "scene_id", 7, replicates=2)
    assert any(row["scope_id"] == "Urban__MID" for row in result)


def test_loaded_population_exposes_explicit_academic_eligibility_flag():
    project_root = HERE.parents[4]
    data = load_stage3_population(project_root)
    assert all(row.get("academic_eligible") is True for row in data.nodes)


def test_continuous_elevation_result_does_not_call_weak_evidence_supported():
    rows = [
        {"diagnostic_support_status": "DATA_SUPPORTED", "slope_bootstrap_lower": "-0.1", "slope_bootstrap_upper": "0.2"},
        {"diagnostic_support_status": "DATA_SUPPORTED", "slope_bootstrap_lower": "0.1", "slope_bootstrap_upper": "0.2"},
    ]
    assert continuous_elevation_result(rows) == "CONDITIONAL"
    assert continuous_elevation_result([rows[1]]) == "SUPPORTED"
    assert continuous_elevation_result([{ "diagnostic_support_status": "PRIOR_DOMINANT" }]) == "NOT_SUPPORTED"


def test_stage4_sensitivity_result_uses_bootstrap_and_family_evidence():
    consistent = [
        {"population": "STAGE3_WEIGHTED_PRIMARY", "scope": "global", "scope_id": "global", "parameter": "excess_delay_samples", "comparison_status": "COMPARABLE", "median": "1", "median_bootstrap_lower": "0", "median_bootstrap_upper": "2", "selected_family": "lognormal"},
        {"population": "STAGE4_STRICT_CONFIRMED", "scope": "global", "scope_id": "global", "parameter": "excess_delay_samples", "comparison_status": "COMPARABLE", "median": "1", "selected_family": "lognormal"},
    ]
    assert stage4_sensitivity_result(consistent) == "CONSISTENT"
    consistent[1]["median"] = "4"
    assert stage4_sensitivity_result(consistent) == "MATERIAL_DIFFERENCE"
