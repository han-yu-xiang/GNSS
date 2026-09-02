from __future__ import annotations

import csv
import io
import math
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.darkroom_generator_v2_1_core import (
    BAND_SEQUENCE,
    FINAL_COLUMNS,
    ALL_ACTIVE_MASK,
    format_v21_final_rows,
    generate_v21_simulation,
    load_frozen_v21_parent_models,
    load_v21_config,
    validate_v21_request,
)


ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = ROOT / "configs" / "channel_modeling" / "darkroom_multi_elevation_four_slot_generator_v2_1.json"


def _payload(config, request_id: str = "test-v2-1") -> dict[str, object]:
    return {
        "request_id": request_id,
        "simulation_id": "simulation-v2-1",
        "generator_id": config.model_id,
        "environment_class": "Urban",
        "elevation_bands": ["LOW", "MID", "HIGH"],
        "duration_ms": 120,
        "master_seed": 20260827,
        "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
        "all_nlos_slots_active": True,
        "conditional_multipath_scenario": True,
        "inactive_slot_parameter_policy": "NOT_APPLICABLE_ALL_SLOTS_ACTIVE",
        "lock_mapping_mode": "EMPIRICAL_DIAGNOSTIC_PROXY",
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "gold_labels_used_for_generation": False,
        "output_namespace": f"dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_runs/{request_id}",
    }


def test_v21_schema_freezes_all_active_four_slot_contract() -> None:
    assert FINAL_COLUMNS == (
        "ms",
        "SatelliteID",
        "NLOSPathID",
        "RelativeDelay",
        "RelativeDoppler",
        "RelativeAmplitude",
        "RelativePhase_rad",
    )
    assert BAND_SEQUENCE == (("LOW", "Low"), ("MID", "Mid"), ("HIGH", "High"))
    assert ALL_ACTIVE_MASK == "111"


def test_v21_generation_has_positive_nlos_for_every_band_and_millisecond() -> None:
    config = load_v21_config(CONFIG_PATH, ROOT)
    models = load_frozen_v21_parent_models(ROOT, config)
    request = validate_v21_request(_payload(config), config)
    result = generate_v21_simulation(request, config, models)

    assert len(result.final_rows) == 120 * 12
    assert len(result.path_slot_rows) == 120 * 9
    assert len(result.path_block_rows) == 3 * 3 * 3
    assert all(row["RelativeAmplitude"] > 0.0 for row in result.final_rows if row["NLOSPathID"] in (1, 2, 3))
    assert all(row["active"] is True for row in result.path_slot_rows)
    assert all(row["activation_mask"] == "111" for row in result.path_slot_rows)
    assert all(row["K_active"] == 3 for row in result.path_block_rows)
    assert all(row["activation_mask"] == "111" for row in result.path_block_rows)
    assert result.support_summary["all_nlos_slots_active"] is True
    assert result.support_summary["activation_model_used_for_generation"] is False

    first = [(row["SatelliteID"], row["NLOSPathID"]) for row in result.final_rows[:12]]
    assert first == [
        ("Low", 0), ("Low", 1), ("Low", 2), ("Low", 3),
        ("Mid", 0), ("Mid", 1), ("Mid", 2), ("Mid", 3),
        ("High", 0), ("High", 1), ("High", 2), ("High", 3),
    ]
    assert result.final_rows == generate_v21_simulation(request, config, models).final_rows


def test_v21_canonical_formatter_rejects_zero_nlos_amplitude() -> None:
    rows = [
        {
            "ms": 1,
            "SatelliteID": "Low",
            "NLOSPathID": 0,
            "RelativeDelay": 0.0,
            "RelativeDoppler": 0.0,
            "RelativeAmplitude": 1.0,
            "RelativePhase_rad": 0.0,
        },
        {
            "ms": 1,
            "SatelliteID": "Low",
            "NLOSPathID": 1,
            "RelativeDelay": 10.0,
            "RelativeDoppler": 1.0,
            "RelativeAmplitude": 0.0,
            "RelativePhase_rad": 0.0,
        },
    ]
    with pytest.raises(ValueError, match="positive"):
        format_v21_final_rows(rows)


def test_v21_request_rejects_non_all_active_contract() -> None:
    config = load_v21_config(CONFIG_PATH, ROOT)
    payload = _payload(config)
    payload["all_nlos_slots_active"] = False
    with pytest.raises(ValueError, match="all_nlos_slots_active"):
        validate_v21_request(payload, config)
