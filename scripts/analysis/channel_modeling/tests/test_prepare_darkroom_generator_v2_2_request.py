from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import load_v22_config, validate_v22_request
from scripts.analysis.channel_modeling.prepare_darkroom_generator_v2_2_request import (
    PAIRING_IDS,
    build_v22_request_payload,
    canonical_request_bytes,
    validate_request_payload_shape,
)


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "configs" / "channel_modeling" / "darkroom_multi_elevation_four_slot_generator_v2_2.json"


def _payload() -> dict[str, object]:
    config = load_v22_config(CONFIG, ROOT)
    return build_v22_request_payload(
        project_root=ROOT,
        config_path=CONFIG,
        request_id="unit-v22-request",
        environment="Urban",
        quality_mode="GOOD_TRACKED_BASELINE",
        duration_ms=20_000,
        master_seed=20260827,
        pairing_id=PAIRING_IDS["Urban"],
        output_namespace="dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/unit-v22-request",
    )


def test_v22_request_freezes_quality_provenance_and_execution_flags() -> None:
    payload = _payload()
    validate_request_payload_shape(payload)
    config = load_v22_config(CONFIG, ROOT)
    request = validate_v22_request(payload, config)
    assert request.quality_mode == "GOOD_TRACKED_BASELINE"
    assert payload["duration_ms"] == 20_000
    assert payload["sample_rate_hz"] == 10_230_000
    assert payload["source_scene_ids"] == [
        "F1023_V70_D0120_P1", "F1023_V70_D0120_P5", "F1023_V70_D0120_P7",
        "F1023_V70_D0120_P8", "F1023_V70_D0122_P1", "F1023_v50_D0127_P1",
    ]
    assert payload["new_only"] is True
    assert payload["resume_allowed"] is False
    assert payload["raw_iq_read"] is False
    assert payload["gold_labels_used_for_generation"] is False
    assert payload["parent_model_manifests"]["path"] == "4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c"
    assert canonical_request_bytes(payload).startswith(b"{")


@pytest.mark.parametrize("field,value,pattern", [
    ("quality_mode", "UNKNOWN", "quality_mode"),
    ("elevation_bands", ["LOW"], "elevation_bands"),
    ("new_only", False, "new_only"),
    ("resume_allowed", True, "resume_allowed"),
    ("raw_iq_read", True, "raw_iq_read"),
    ("matlab", True, "matlab"),
    ("sage", True, "sage"),
    ("batch", True, "batch"),
    ("process_20_46_mhz", True, "process_20_46_mhz"),
    ("gold_labels_used_for_generation", True, "gold_labels_used_for_generation"),
])
def test_v22_request_rejects_invalid_shape(field: str, value: object, pattern: str) -> None:
    payload = _payload()
    payload[field] = value
    with pytest.raises(ValueError, match=pattern):
        validate_request_payload_shape(payload)


def test_v22_request_rejects_wrong_pairing_for_environment() -> None:
    with pytest.raises(ValueError, match="pairing_id"):
        build_v22_request_payload(
            project_root=ROOT,
            config_path=CONFIG,
            request_id="unit-v22-wrong-pair",
            environment="Urban",
            quality_mode="GOOD_TRACKED_BASELINE",
            duration_ms=20_000,
            master_seed=20260827,
            pairing_id=PAIRING_IDS["Highway/Open"],
            output_namespace="dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/unit-v22-wrong-pair",
        )
