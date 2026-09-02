from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.prepare_darkroom_generator_v2_request import (
    canonical_request_bytes,
    validate_request_payload_shape,
)


ROOT = Path(__file__).resolve().parents[4]


def _payload() -> dict[str, object]:
    return {
        "request_schema_version": "darkroom-generator-request-2",
        "request_id": "request-v2",
        "simulation_id": "simulation-v2",
        "generator_id": "darkroom-multi-elevation-four-slot-generator-v2",
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
        "output_namespace": "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/request-v2",
    }


def test_canonical_request_bytes_are_order_independent() -> None:
    first = _payload()
    second = {key: first[key] for key in reversed(list(first))}
    assert canonical_request_bytes(first) == canonical_request_bytes(second)
    assert json.loads(canonical_request_bytes(first)) == first


def test_request_shape_requires_all_bands_and_no_single_band_field() -> None:
    payload = _payload()
    validate_request_payload_shape(payload)
    payload["elevation_bands"] = ["LOW", "HIGH"]
    with pytest.raises(ValueError, match="LOW,MID,HIGH"):
        validate_request_payload_shape(payload)
    payload = _payload()
    payload["elevation_band"] = "MID"
    with pytest.raises(ValueError, match="single elevation_band"):
        validate_request_payload_shape(payload)


def test_request_shape_rejects_execution_flags() -> None:
    payload = _payload()
    payload["resume_allowed"] = True
    with pytest.raises(ValueError, match="resume_allowed"):
        validate_request_payload_shape(payload)
