"""Deterministic paired Good/Poor quality timelines for darkroom v2.2.

This module is a conditional receiver-quality composition layer.  It does not
claim absolute RF power or a physical lock-loss probability, and it does not
read raw IQ or any posterior/gold artifact.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    from . import darkroom_generator_core as _v1
except ImportError:
    from scripts.analysis.channel_modeling import darkroom_generator_core as _v1


GOOD_TRACKED_BASELINE = "GOOD_TRACKED_BASELINE"
POOR_CONDITIONAL = "POOR_CONDITIONAL"
QUALITY_MODES = (GOOD_TRACKED_BASELINE, POOR_CONDITIONAL)


@dataclass(frozen=True)
class QualityProfileRequest:
    simulation_id: str
    pairing_id: str
    environment_class: str
    elevation_band: str
    duration_ms: int
    master_seed: int
    quality_mode: str
    pre_event_guard_ms: int = 100
    post_event_guard_ms: int = 100
    entry_ramp_cap_ms: int = 20


@dataclass(frozen=True)
class QualityTimelineResult:
    states: tuple[str, ...]
    event_ids: tuple[str | None, ...]
    envelope_linear: np.ndarray
    phase_observable: tuple[bool, ...]
    event_catalog: tuple[dict[str, Any], ...]
    support_status: str


def _append_rng(
    request: QualityProfileRequest,
    scope_id: str,
    stream_name: str,
    registry: list[dict[str, Any]],
) -> np.random.Generator:
    # Quality-only streams are disjoint from paired path/gain streams.
    qualified_stream_name = f"{request.quality_mode}:{stream_name}"
    seed = _v1.derive_stream_seed(
        request.master_seed,
        request.pairing_id,
        request.environment_class,
        request.elevation_band,
        scope_id,
        qualified_stream_name,
    )
    registry.append(
        {
            "simulation_id": request.simulation_id,
            "pairing_id": request.pairing_id,
            "environment_class": request.environment_class,
            "elevation_band": request.elevation_band,
            "scope_id": scope_id,
            "stream_name": qualified_stream_name,
            "seed_uint64": seed,
            "quality_mode": request.quality_mode,
            "derivation": "sha256(canonical_json(master_seed,pairing_id,environment_class,elevation_band,scope_id,quality_mode:stream_name))[:8]",
        }
    )
    return np.random.default_rng(seed)


def _validate_request(request: QualityProfileRequest) -> None:
    if request.quality_mode not in QUALITY_MODES:
        raise ValueError(f"unsupported quality mode: {request.quality_mode}")
    if request.duration_ms < 1 or request.master_seed < 0:
        raise ValueError("duration_ms must be positive and master_seed non-negative")
    if request.pre_event_guard_ms < 0 or request.post_event_guard_ms < 0:
        raise ValueError("quality guards must be non-negative")
    if request.entry_ramp_cap_ms < 1:
        raise ValueError("entry_ramp_cap_ms must be positive")


def _empty_good(request: QualityProfileRequest) -> QualityTimelineResult:
    count = int(request.duration_ms)
    return QualityTimelineResult(
        states=("TRACKED_GOOD",) * count,
        event_ids=(None,) * count,
        envelope_linear=np.ones(count, dtype=float),
        phase_observable=(True,) * count,
        event_catalog=(),
        support_status="TRACKED_BASELINE_CONDITIONAL_NO_LOCK_EVENT",
    )


def _poor_timeline(request: QualityProfileRequest, frozen_models: Any, registry: list[dict[str, Any]]) -> QualityTimelineResult:
    lock_model = frozen_models.lock_models[request.environment_class]
    fade_model = frozen_models.fade_models[request.environment_class]
    count = int(request.duration_ms)
    duration_rng = _append_rng(request, "quality-event-000001", "lock_duration", registry)
    recovery_rng = _append_rng(request, "quality-event-000001", "recovery_duration", registry)
    depth_rng = _append_rng(request, "quality-event-000001", "depth_proxy", registry)
    placement_rng = _append_rng(request, "quality-event-000001", "event_placement", registry)

    lock_duration_ms = max(20, int(math.ceil(float(duration_rng.gamma(lock_model.duration_shape, lock_model.duration_scale_s)) * 1000.0)))
    recovery_duration_ms = max(1, int(math.ceil(float(recovery_rng.gamma(lock_model.recovery_shape, lock_model.recovery_scale_s)) * 1000.0)))
    depth_db = max(0.0, float(_v1._sample_distribution(fade_model.depth, depth_rng)))
    floor_linear = max(1e-12, min(1.0, 10.0 ** (-depth_db / 20.0)))
    total_event_ms = lock_duration_ms + recovery_duration_ms
    first_allowed = int(request.pre_event_guard_ms)
    last_allowed = count - int(request.post_event_guard_ms) - total_event_ms
    if last_allowed < first_allowed:
        raise ValueError("QUALITY_EPISODE_DOES_NOT_FIT")
    start_index = int(placement_rng.integers(first_allowed, last_allowed + 1))

    entry_ramp_ms = min(int(request.entry_ramp_cap_ms), lock_duration_ms)
    lock_bad_hold_ms = lock_duration_ms - entry_ramp_ms
    entry = _v1._render_endpoint_envelope(entry_ramp_ms, floor_linear, "entry")
    hold = np.full(lock_bad_hold_ms, floor_linear, dtype=float)
    recovery = _v1._render_endpoint_envelope(recovery_duration_ms, floor_linear, "recovery")
    local_envelope = np.concatenate((entry, hold, recovery))
    if len(local_envelope) != total_event_ms:
        raise AssertionError("quality event envelope length mismatch")

    states = ["TRACKED_GOOD"] * count
    event_ids: list[str | None] = [None] * count
    envelope = np.ones(count, dtype=float)
    phase_observable = [True] * count
    event_id = f"quality-lock-{request.elevation_band.lower()}-000001"
    sequence = ((["FADING_TO_LOCK_BAD"] * entry_ramp_ms)
                + (["LOCK_BAD_HOLD"] * lock_bad_hold_ms)
                + (["RECOVERING"] * recovery_duration_ms))
    for offset, state in enumerate(sequence):
        index = start_index + offset
        states[index] = state
        event_ids[index] = event_id
        envelope[index] = float(local_envelope[offset])
        phase_observable[index] = False

    event_catalog = (
        {
            "simulation_id": request.simulation_id,
            "pairing_id": request.pairing_id,
            "elevation_band": request.elevation_band,
            "quality_mode": request.quality_mode,
            "quality_event_id": event_id,
            "event_start_ms": start_index + 1,
            "entry_ramp_ms": entry_ramp_ms,
            "lock_bad_hold_ms": lock_bad_hold_ms,
            "recovery_duration_ms": recovery_duration_ms,
            "event_end_ms": start_index + total_event_ms,
            "lock_duration_ms": lock_duration_ms,
            "floor_linear": floor_linear,
            "depth_db": depth_db,
            "depth_source": "OBSERVABLE_FADE_PARENT_PROXY",
            "duration_source": "FROZEN_ENVIRONMENT_LOCK_MODEL",
            "recovery_source": "FROZEN_ENVIRONMENT_RECOVERY_MODEL_OR_PARENT",
            "support_status": f"{lock_model.support_status}|{fade_model.support_status}",
            "complete_event": True,
            "entry_probability_used": False,
        },
    )
    return QualityTimelineResult(
        states=tuple(states),
        event_ids=tuple(event_ids),
        envelope_linear=envelope,
        phase_observable=tuple(phase_observable),
        event_catalog=event_catalog,
        support_status=f"{lock_model.support_status}|{fade_model.support_status}",
    )


def generate_quality_timeline(
    request: QualityProfileRequest,
    frozen_models: Any,
    random_stream_registry: list[dict[str, Any]],
) -> QualityTimelineResult:
    _validate_request(request)
    if request.quality_mode == GOOD_TRACKED_BASELINE:
        return _empty_good(request)
    return _poor_timeline(request, frozen_models, random_stream_registry)
