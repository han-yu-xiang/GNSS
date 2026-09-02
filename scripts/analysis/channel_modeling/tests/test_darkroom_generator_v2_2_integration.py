from __future__ import annotations

from pathlib import Path

from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import (
    generate_v22_simulation,
    load_frozen_v22_parent_models,
    load_v22_config,
    validate_v22_request,
)


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "configs" / "channel_modeling" / "darkroom_multi_elevation_four_slot_generator_v2_2.json"


def _request(config, mode: str, request_id: str):
    return validate_v22_request({
        "request_id": request_id,
        "simulation_id": request_id,
        "pairing_id": "urban-quality-pair-20260827",
        "generator_id": config.model_id,
        "environment_class": "Urban",
        "elevation_bands": ["LOW", "MID", "HIGH"],
        "duration_ms": 80,
        "master_seed": 20260827,
        "quality_mode": mode,
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
    }, config)


def test_v22_generation_determinism_and_strict_positive_paths() -> None:
    config = load_v22_config(CONFIG, ROOT)
    models, _ = load_frozen_v22_parent_models(ROOT, config)
    request = _request(config, "GOOD_TRACKED_BASELINE", "integration-good")
    first = generate_v22_simulation(request, config, models)
    second = generate_v22_simulation(request, config, models)
    assert first.final_rows == second.final_rows
    assert len(first.final_rows) == 80 * 12
    assert all(row["RelativeAmplitude"] > 0.0 for row in first.final_rows)
    assert first.support_summary["quality_event_count_per_band"] == {"LOW": 0, "MID": 0, "HIGH": 0}
