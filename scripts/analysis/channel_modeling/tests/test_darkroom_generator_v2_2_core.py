from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import (
    BAND_SEQUENCE,
    ELEVATION_BANDS,
    ENVIRONMENTS,
    FINAL_COLUMNS,
    load_frozen_v22_parent_models,
    load_v22_config,
    format_v22_final_rows,
    generate_v22_simulation,
    validate_v22_request,
)


ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = ROOT / "configs" / "channel_modeling" / "darkroom_multi_elevation_four_slot_generator_v2_2.json"


def _payload(config, *, request_id: str = "test-v2-2", quality_mode: str = "GOOD_TRACKED_BASELINE") -> dict[str, object]:
    return {
        "request_id": request_id,
        "simulation_id": request_id,
        "pairing_id": "urban-quality-pair-20260827",
        "generator_id": config.model_id,
        "environment_class": "Urban",
        "elevation_bands": ["LOW", "MID", "HIGH"],
        "duration_ms": 20_000,
        "master_seed": 20260827,
        "quality_mode": quality_mode,
        "pre_event_guard_ms": 100,
        "post_event_guard_ms": 100,
        "entry_ramp_cap_ms": 20,
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "gold_labels_used_for_generation": False,
        "output_namespace": f"dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/{request_id}",
    }


def test_v22_schema_is_frozen() -> None:
    config = load_v22_config(CONFIG_PATH, ROOT)
    assert config.generator_version == "2.2.0"
    assert config.environments == ENVIRONMENTS
    assert config.elevation_bands == ELEVATION_BANDS
    assert FINAL_COLUMNS == (
        "ms", "SatelliteID", "NLOSPathID", "RelativeDelay",
        "RelativeDoppler", "RelativeAmplitude", "RelativePhase_rad",
    )
    assert BAND_SEQUENCE == (("LOW", "Low"), ("MID", "Mid"), ("HIGH", "High"))
    assert config.source_payload["quality_policy"]["quality_modes"] == [
        "GOOD_TRACKED_BASELINE", "POOR_CONDITIONAL",
    ]


def test_v22_generation_has_exact_order_and_positive_four_slot_rows() -> None:
    config = load_v22_config(CONFIG_PATH, ROOT)
    models, _ = load_frozen_v22_parent_models(ROOT, config)
    request = validate_v22_request(_payload(config), config)
    result = generate_v22_simulation(request, config, models)
    assert len(result.final_rows) == 20_000 * 12
    assert len(result.receiver_quality_rows) == 20_000 * 3
    assert len(result.path_slot_rows) == 20_000 * 9
    assert all(float(row["RelativeAmplitude"]) > 0.0 for row in result.final_rows)
    assert [(row["SatelliteID"], row["NLOSPathID"]) for row in result.final_rows[:12]] == [
        ("Low", 0), ("Low", 1), ("Low", 2), ("Low", 3),
        ("Mid", 0), ("Mid", 1), ("Mid", 2), ("Mid", 3),
        ("High", 0), ("High", 1), ("High", 2), ("High", 3),
    ]
    assert len(result.path_block_rows) == 500 * 3 * 3
    assert all(row["active"] is True and row["activation_mask"] == "111" for row in result.path_block_rows)
    assert all(row["NLOSPathID"] in (1, 2, 3) for row in result.path_slot_rows)
    assert result.support_summary["all_nlos_slots_active"] is True


def test_v22_paired_good_and_poor_share_base_paths_and_gain() -> None:
    config = load_v22_config(CONFIG_PATH, ROOT)
    models, _ = load_frozen_v22_parent_models(ROOT, config)
    good_request = validate_v22_request(_payload(config, request_id="pair-good"), config)
    poor_payload = _payload(config, request_id="pair-poor", quality_mode="POOR_CONDITIONAL")
    poor_request = validate_v22_request(poor_payload, config)
    good = generate_v22_simulation(good_request, config, models)
    poor = generate_v22_simulation(poor_request, config, models)
    for good_row, poor_row in zip(good.final_rows, poor.final_rows):
        assert good_row["ms"] == poor_row["ms"]
        assert good_row["SatelliteID"] == poor_row["SatelliteID"]
        assert good_row["NLOSPathID"] == poor_row["NLOSPathID"]
        if good_row["NLOSPathID"] != 0:
            assert good_row["RelativeDelay"] == poor_row["RelativeDelay"]
            assert good_row["RelativeDoppler"] == poor_row["RelativeDoppler"]
            assert good_row["RelativePhase_rad"] == poor_row["RelativePhase_rad"]
    good_base = {(row["ms"], row["elevation_band"]): row["base_common_gain_linear"] for row in good.receiver_quality_rows}
    poor_base = {(row["ms"], row["elevation_band"]): row["base_common_gain_linear"] for row in poor.receiver_quality_rows}
    assert good_base == poor_base
    assert len(poor.quality_event_rows) == 3


def test_v22_formatter_rejects_nonpositive_path() -> None:
    row = {
        "ms": 1,
        "SatelliteID": "Low",
        "NLOSPathID": 1,
        "RelativeDelay": 1.0,
        "RelativeDoppler": 1.0,
        "RelativeAmplitude": 0.0,
        "RelativePhase_rad": 0.0,
    }
    with pytest.raises(ValueError, match="strictly positive"):
        format_v22_final_rows([row])


def test_v22_rejects_wrong_sample_rate_and_forbidden_mode() -> None:
    config = load_v22_config(CONFIG_PATH, ROOT)
    payload = _payload(config)
    payload["process_20_46_mhz"] = True
    with pytest.raises(ValueError, match="false"):
        validate_v22_request(payload, config)
    payload = _payload(config)
    payload["elevation_bands"] = ["LOW"]
    with pytest.raises(ValueError, match="LOW,MID,HIGH"):
        validate_v22_request(payload, config)
