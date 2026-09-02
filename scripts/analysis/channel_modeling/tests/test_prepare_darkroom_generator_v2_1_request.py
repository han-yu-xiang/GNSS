from __future__ import annotations

import json

import pytest

from scripts.analysis.channel_modeling.prepare_darkroom_generator_v2_1_request import (
    canonical_request_bytes,
    validate_request_payload_shape,
)


def _payload() -> dict[str, object]:
    return {
        "request_schema_version": "darkroom-generator-request-2.1",
        "request_id": "request-v2-1",
        "simulation_id": "simulation-v2-1",
        "generator_id": "darkroom-multi-elevation-four-slot-generator-v2-1",
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
        "output_namespace": "dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_runs/request-v2-1",
    }


def test_v21_canonical_request_bytes_are_order_independent() -> None:
    first = _payload()
    second = {key: first[key] for key in reversed(list(first))}
    assert canonical_request_bytes(first) == canonical_request_bytes(second)
    assert json.loads(canonical_request_bytes(first)) == first


def test_v21_request_shape_requires_all_active_slots() -> None:
    payload = _payload()
    validate_request_payload_shape(payload)
    payload["nlos_activation_policy"] = "EMPIRICAL_CONFIRMED_SUPPORT"
    with pytest.raises(ValueError, match="ALL_THREE_SLOTS_ALWAYS_ACTIVE"):
        validate_request_payload_shape(payload)
    payload = _payload()
    payload["all_nlos_slots_active"] = False
    with pytest.raises(ValueError, match="all_nlos_slots_active"):
        validate_request_payload_shape(payload)


def test_v21_request_shape_rejects_forbidden_execution_flags() -> None:
    payload = _payload()
    payload["resume_allowed"] = True
    with pytest.raises(ValueError, match="resume_allowed"):
        validate_request_payload_shape(payload)
