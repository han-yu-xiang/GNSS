from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.analysis.channel_modeling.darkroom_generator_core import (
    FINAL_COLUMNS,
    BlockPath,
    GenerationRequest,
    GeneratorConfig,
    canonical_json_bytes,
    derive_stream_seed,
    evolve_phase_1ms,
    format_final_rows,
    generate_simulation,
    load_frozen_models,
    load_generator_config,
    raised_cosine_envelope,
    validate_generation_request,
)


ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = ROOT / "configs" / "channel_modeling" / "darkroom_four_path_generator_v1.json"


def test_final_columns_are_frozen_in_user_order() -> None:
    assert FINAL_COLUMNS == (
        "ms",
        "SatelliteID",
        "NLOSPathID",
        "RelativeDelay",
        "RelativeDoppler",
        "RelativeAmplitude",
        "RelativePhase_rad",
    )


def test_canonical_json_and_stream_seed_are_order_independent() -> None:
    left = {"b": 2, "a": [1, "x"]}
    right = {"a": [1, "x"], "b": 2}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    first = derive_stream_seed(7, "sim", "Highway/Open", "MID", "block-1", "phase")
    second = derive_stream_seed(7, "sim", "Highway/Open", "MID", "block-1", "phase")
    assert first == second
    assert first != derive_stream_seed(7, "sim", "Highway/Open", "MID", "block-1", "gain")


def test_phase_recurrence_uses_one_ms_doppler_and_wrap_interval() -> None:
    value = evolve_phase_1ms(0.25, 125.0)
    expected = (0.25 + 2.0 * np.pi * 125.0 * 0.001 + np.pi) % (2.0 * np.pi) - np.pi
    assert value == pytest.approx(expected, abs=1e-12)
    assert -np.pi <= value < np.pi


def test_raised_cosine_entry_and_recovery_have_exact_endpoints() -> None:
    entry = raised_cosine_envelope(4, 0.2, direction="entry")
    recovery = raised_cosine_envelope(4, 0.2, direction="recovery")
    assert entry == pytest.approx([1.0, 0.882842712474619, 0.6, 0.317157287525381, 0.2], abs=1e-12)
    assert recovery == pytest.approx([0.2, 0.317157287525381, 0.6, 0.882842712474619, 1.0], abs=1e-12)


def test_generation_request_rejects_non_40ms_block_and_enabled_execution() -> None:
    config = GeneratorConfig(
        model_id="darkroom-four-path-generator-v1",
        time_step_ms=1,
        path_parameter_block_ms=40,
        environments=("Urban", "Special Reflective", "Mountain/Valley", "Highway/Open"),
        elevation_bands=("LOW", "MID", "HIGH"),
    )
    payload = {
        "request_id": "r1",
        "simulation_id": "s1",
        "environment_class": "Urban",
        "elevation_band": "MID",
        "duration_ms": 120,
        "master_seed": 123,
        "activation_mode": "EMPIRICAL_CONFIRMED_SUPPORT",
        "lock_mapping_mode": "EMPIRICAL_DIAGNOSTIC_PROXY",
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "output_namespace": "dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_runs/r1",
    }
    request = validate_generation_request(payload, config)
    assert isinstance(request, GenerationRequest)
    payload["resume_allowed"] = True
    with pytest.raises(ValueError, match="resume_allowed"):
        validate_generation_request(payload, config)


def test_format_final_rows_preserves_exact_header_and_null_semantics() -> None:
    rows = [
        {
            "ms": 1,
            "SatelliteID": "Mid",
            "NLOSPathID": 0,
            "RelativeDelay": 0.0,
            "RelativeDoppler": 0.0,
            "RelativeAmplitude": 0.8,
            "RelativePhase_rad": 0.1,
        },
        {
            "ms": 1,
            "SatelliteID": "Mid",
            "NLOSPathID": 1,
            "RelativeDelay": None,
            "RelativeDoppler": None,
            "RelativeAmplitude": 0.0,
            "RelativePhase_rad": None,
        },
    ]
    rendered = format_final_rows(rows)
    parsed = list(csv.reader(io.StringIO(rendered)))
    assert tuple(parsed[0]) == FINAL_COLUMNS
    assert parsed[2][3:5] == ["", ""]
    assert parsed[2][5] == "0"
    assert parsed[2][6] == ""
    assert "None" not in rendered
    assert "NaN" not in rendered


def test_block_path_requires_positive_delay_for_active_nlos() -> None:
    with pytest.raises(ValueError, match="positive"):
        BlockPath(
            slot_id=1,
            active=True,
            delay_ns=0.0,
            doppler_hz=1.0,
            relative_amplitude=0.5,
        )


def test_frozen_generator_config_and_all_parent_models_load_without_raw_inputs() -> None:
    config = load_generator_config(CONFIG_PATH, ROOT)
    models = load_frozen_models(ROOT, config)
    assert config.path_parameter_block_ms == 40
    assert set(models.path_cells) == {
        f"{environment}|{band}"
        for environment in config.environments
        for band in config.elevation_bands
    }
    assert models.path_model_manifest_sha256 == "4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c"


def test_generator_emits_four_rows_per_ms_and_reproduces_same_scientific_request() -> None:
    config = load_generator_config(CONFIG_PATH, ROOT)
    models = load_frozen_models(ROOT, config)
    payload = {
        "request_id": "preview-attempt-1",
        "simulation_id": "preview-120ms-urban-mid",
        "environment_class": "Urban",
        "elevation_band": "MID",
        "duration_ms": 120,
        "master_seed": 20260827,
        "activation_mode": "CONDITIONAL_ACTIVE_STRESS",
        "lock_mapping_mode": "EMPIRICAL_DIAGNOSTIC_PROXY",
        "stress_floor_linear": None,
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "output_namespace": "dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_runs/preview-attempt-1",
    }
    request = validate_generation_request(payload, config)
    first = generate_simulation(request, config, models)
    second = generate_simulation(request, config, models)
    assert len(first.final_rows) == 480
    assert first.final_rows == second.final_rows
    assert [row["NLOSPathID"] for row in first.final_rows[:4]] == [0, 1, 2, 3]
    assert all(row["SatelliteID"] == "Mid" for row in first.final_rows)
    assert all(row["RelativeAmplitude"] == 0.0 for row in first.final_rows if row["NLOSPathID"] in (1, 2, 3) and row["RelativeDelay"] is None)
