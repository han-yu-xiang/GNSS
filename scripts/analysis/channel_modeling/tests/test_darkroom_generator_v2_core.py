from __future__ import annotations

import csv
import io
import math
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.darkroom_generator_v2_core import (
    BAND_SEQUENCE,
    FINAL_COLUMNS,
    V2LatentSlot,
    apply_activation_mask,
    format_v2_final_rows,
    generate_v2_simulation,
    load_frozen_v2_parent_models,
    load_v2_config,
    validate_v2_request,
)


ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = ROOT / "configs" / "channel_modeling" / "darkroom_multi_elevation_four_slot_generator_v2.json"


def test_v2_schema_and_band_order_are_frozen() -> None:
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


def test_inactive_slots_keep_latent_parameters_but_zero_output_amplitude() -> None:
    latent = [
        V2LatentSlot(1, 100.0, -20.0, 0.4, 0.1),
        V2LatentSlot(2, 200.0, 30.0, 0.3, -0.2),
        V2LatentSlot(3, 300.0, 40.0, 0.2, 0.3),
    ]
    slots = apply_activation_mask(latent, active_count=1)
    assert [slot.active for slot in slots] == [True, False, False]
    assert all(slot.delay_ns > 0 for slot in slots)
    assert all(math.isfinite(slot.doppler_hz) for slot in slots)
    assert all(math.isfinite(slot.phase_rad) for slot in slots)
    assert [slot.output_amplitude_base for slot in slots] == [0.4, 0.0, 0.0]


def test_request_requires_all_three_bands_and_forbids_single_band_override() -> None:
    config = load_v2_config(CONFIG_PATH, ROOT)
    payload = {
        "request_id": "test-v2",
        "simulation_id": "sim-v2",
        "generator_id": config.model_id,
        "environment_class": "Urban",
        "elevation_bands": ["LOW", "MID", "HIGH"],
        "duration_ms": 120,
        "master_seed": 20260827,
        "activation_mode": "EMPIRICAL_CONFIRMED_SUPPORT",
        "inactive_slot_parameter_policy": "LATENT_PARAMETERS_WITH_ZERO_AMPLITUDE",
        "lock_mapping_mode": "EMPIRICAL_DIAGNOSTIC_PROXY",
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "output_namespace": "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/test-v2",
    }
    request = validate_v2_request(payload, config)
    assert request.elevation_bands == ("LOW", "MID", "HIGH")
    payload["elevation_bands"] = ["MID"]
    with pytest.raises(ValueError, match="elevation_bands"):
        validate_v2_request(payload, config)


def test_format_v2_rows_rejects_empty_fields() -> None:
    rows = [
        {
            "ms": 1,
            "SatelliteID": "Low",
            "NLOSPathID": 0,
            "RelativeDelay": 0.0,
            "RelativeDoppler": 0.0,
            "RelativeAmplitude": 1.0,
            "RelativePhase_rad": 0.1,
        },
        {
            "ms": 1,
            "SatelliteID": "Low",
            "NLOSPathID": 1,
            "RelativeDelay": 100.0,
            "RelativeDoppler": 2.0,
            "RelativeAmplitude": 0.0,
            "RelativePhase_rad": -0.2,
        },
    ]
    rendered = format_v2_final_rows(rows)
    parsed = list(csv.reader(io.StringIO(rendered)))
    assert tuple(parsed[0]) == FINAL_COLUMNS
    assert all(cell != "" for row in parsed[1:] for cell in row)


def test_real_frozen_models_emit_120ms_all_band_rows_with_exact_order() -> None:
    config = load_v2_config(CONFIG_PATH, ROOT)
    models = load_frozen_v2_parent_models(ROOT, config)
    payload = {
        "request_id": "test-v2-generation",
        "simulation_id": "test-v2-generation-simulation",
        "generator_id": config.model_id,
        "environment_class": "Urban",
        "elevation_bands": ["LOW", "MID", "HIGH"],
        "duration_ms": 120,
        "master_seed": 20260827,
        "activation_mode": "EMPIRICAL_CONFIRMED_SUPPORT",
        "inactive_slot_parameter_policy": "LATENT_PARAMETERS_WITH_ZERO_AMPLITUDE",
        "lock_mapping_mode": "EMPIRICAL_DIAGNOSTIC_PROXY",
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "output_namespace": "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/test-v2-generation",
    }
    request = validate_v2_request(payload, config)
    result = generate_v2_simulation(request, config, models)
    assert len(result.final_rows) == 1440
    first = [(row["SatelliteID"], row["NLOSPathID"]) for row in result.final_rows[:12]]
    assert first == [
        ("Low", 0), ("Low", 1), ("Low", 2), ("Low", 3),
        ("Mid", 0), ("Mid", 1), ("Mid", 2), ("Mid", 3),
        ("High", 0), ("High", 1), ("High", 2), ("High", 3),
    ]
    assert len({row["ms"] for row in result.final_rows}) == 120
    first_slots = [(row["elevation_band"], row["NLOSPathID"]) for row in result.path_slot_rows[:9]]
    assert first_slots == [
        ("LOW", 1), ("LOW", 2), ("LOW", 3),
        ("MID", 1), ("MID", 2), ("MID", 3),
        ("HIGH", 1), ("HIGH", 2), ("HIGH", 3),
    ]
    for row in result.final_rows:
        assert row["RelativeDelay"] is not None
        assert row["RelativeDoppler"] is not None
        assert row["RelativeAmplitude"] is not None
        assert row["RelativePhase_rad"] is not None
        assert math.isfinite(float(row["RelativePhase_rad"]))
    assert result.stream_rows
    assert all(row.get("elevation_band") in {"LOW", "MID", "HIGH"} for row in result.stream_rows)
