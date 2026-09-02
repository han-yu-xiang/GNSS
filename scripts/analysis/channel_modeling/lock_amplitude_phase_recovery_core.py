"""Pure Python primitives for the receiver-lock composition model.

This module is deliberately separate from the GNSS/SAGE production pipeline.
It consumes only already-derived tracking/model artifacts and contains no raw
IQ, MATLAB, SAGE, or batch entry point.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence


PI = math.pi
TWO_PI = 2.0 * math.pi
MS_SECONDS = 0.001
RECOVERY_STABLE_ROWS = 5  # 5 x 20 ms = 100 ms
ENVIRONMENTS = ("Urban", "Special Reflective", "Mountain/Valley", "Highway/Open")
ELEVATION_BANDS = ("LOW", "MID", "HIGH")


class LockState(str, Enum):
    TRACKED = "TRACKED"
    FADING_TO_LOCK_BAD = "FADING_TO_LOCK_BAD"
    LOCK_BAD_HOLD = "LOCK_BAD_HOLD"
    RECOVERING = "RECOVERING"
    INCONCLUSIVE = "INCONCLUSIVE"


class LockMappingMode(str, Enum):
    EMPIRICAL_DIAGNOSTIC_PROXY = "EMPIRICAL_DIAGNOSTIC_PROXY"
    FORCED_LOCK_LOSS_STRESS = "FORCED_LOCK_LOSS_STRESS"


@dataclass(frozen=True)
class RecoveryResult:
    status: str
    duration_s: float | None
    stable_start_s: float | None
    consecutive_rows: int
    reason: str


@dataclass(frozen=True)
class StateEnvelopePoint:
    state: LockState
    envelope_linear: float
    phase_observable: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def wrap_to_pi(phi_rad: float) -> float:
    value = float(phi_rad)
    if not math.isfinite(value):
        raise ValueError(f"phase must be finite: {phi_rad!r}")
    wrapped = (value + PI) % TWO_PI - PI
    # The modulo expression already yields [-pi, pi), including at boundaries.
    return wrapped


def evolve_phase_1ms(phi_rad: float, relative_doppler_hz: float) -> float:
    doppler = float(relative_doppler_hz)
    if not math.isfinite(doppler):
        raise ValueError(f"relative Doppler must be finite: {relative_doppler_hz!r}")
    return wrap_to_pi(float(phi_rad) + TWO_PI * doppler * MS_SECONDS)


def _check_unit_interval(u: float) -> float:
    value = float(u)
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"envelope progress must be in [0,1]: {u!r}")
    return value


def _check_floor(floor_linear: float) -> float:
    value = float(floor_linear)
    if not math.isfinite(value) or value <= 0.0 or value > 1.0:
        raise ValueError(f"envelope floor must be in (0,1]: {floor_linear!r}")
    return value


def raised_cosine_entry(progress: float, floor_linear: float) -> float:
    u = _check_unit_interval(progress)
    floor = _check_floor(floor_linear)
    value = 1.0 - (1.0 - floor) * 0.5 * (1.0 - math.cos(PI * u))
    return min(1.0, max(floor, value))


def raised_cosine_recovery(progress: float, floor_linear: float) -> float:
    u = _check_unit_interval(progress)
    floor = _check_floor(floor_linear)
    value = floor + (1.0 - floor) * 0.5 * (1.0 - math.cos(PI * u))
    return min(1.0, max(floor, value))


def validate_floor(floor_linear: float | None, mode: LockMappingMode | str) -> float:
    mode_value = LockMappingMode(mode)
    if mode_value is LockMappingMode.FORCED_LOCK_LOSS_STRESS:
        if floor_linear is None:
            raise ValueError("forced stress mode requires an explicit positive floor")
        return _check_floor(floor_linear)
    if floor_linear is None:
        raise ValueError("empirical mode requires a resolved proxy floor")
    return _check_floor(floor_linear)


def envelope_for_state(
    state: LockState | str,
    progress: float,
    floor_linear: float,
) -> float:
    state_value = LockState(state)
    floor = _check_floor(floor_linear)
    if state_value is LockState.TRACKED:
        return 1.0
    if state_value is LockState.FADING_TO_LOCK_BAD:
        return raised_cosine_entry(progress, floor)
    if state_value is LockState.LOCK_BAD_HOLD:
        return floor
    if state_value is LockState.RECOVERING:
        return raised_cosine_recovery(progress, floor)
    raise ValueError("inconclusive state cannot produce a physical amplitude envelope")


def compose_path_amplitudes(
    background_common_gain_linear: float,
    lock_envelope_linear: float,
    slot_active: tuple[bool, bool, bool],
    nlos_relative_amplitudes: tuple[float | None, float | None, float | None],
) -> tuple[float, float, float, float]:
    background = float(background_common_gain_linear)
    envelope = float(lock_envelope_linear)
    if not math.isfinite(background) or background < 0.0:
        raise ValueError("background common gain must be finite and non-negative")
    if not math.isfinite(envelope) or envelope <= 0.0:
        raise ValueError("active lock envelope must be finite and positive")
    if len(slot_active) != 3 or len(nlos_relative_amplitudes) != 3:
        raise ValueError("exactly three NLOS slots are required")
    path_zero = background * envelope
    result = [path_zero]
    for active, relative in zip(slot_active, nlos_relative_amplitudes):
        if not active:
            result.append(0.0)
            continue
        if relative is None or not math.isfinite(float(relative)) or float(relative) < 0.0:
            raise ValueError("active NLOS relative amplitude must be finite and non-negative")
        result.append(path_zero * float(relative))
    return tuple(result)  # type: ignore[return-value]


def compose_slot_row(
    ms: int,
    path_id: int,
    active: bool,
    delay_ns: float | None,
    doppler_hz: float | None,
    phase_rad: float | None,
) -> dict[str, Any]:
    if int(ms) < 1:
        raise ValueError("ms must start at 1")
    if int(path_id) not in (0, 1, 2, 3):
        raise ValueError("NLOSPathID must be one of 0,1,2,3")
    if not active:
        return {
            "ms": int(ms),
            "NLOSPathID": int(path_id),
            "RelativeDelay": None,
            "RelativeDoppler": None,
            "RelativeAmplitude": 0.0,
            "RelativePhase_rad": None,
            "path_status": "INACTIVE_NO_PATH",
        }
    if delay_ns is None or doppler_hz is None or phase_rad is None:
        raise ValueError("active slot needs delay, Doppler and phase")
    return {
        "ms": int(ms),
        "NLOSPathID": int(path_id),
        "RelativeDelay": float(delay_ns),
        "RelativeDoppler": float(doppler_hz),
        "RelativeAmplitude": None,
        "RelativePhase_rad": wrap_to_pi(float(phase_rad)),
        "path_status": "ACTIVE_PATH",
    }


def make_state_sequence(
    lock_duration_ms: int,
    entry_ramp_ms: int,
    recovery_ms: int,
) -> list[LockState]:
    lock_duration = int(lock_duration_ms)
    entry = int(entry_ramp_ms)
    recovery = int(recovery_ms)
    if lock_duration < 1 or entry < 0 or recovery < 1:
        raise ValueError("state durations must be positive, with entry allowed to be zero")
    entry = min(entry, lock_duration)
    hold = lock_duration - entry
    return (
        [LockState.FADING_TO_LOCK_BAD] * entry
        + [LockState.LOCK_BAD_HOLD] * hold
        + [LockState.RECOVERING] * recovery
    )


def nearest_time_row(
    rows: Sequence[Mapping[str, Any]],
    target_time_s: float,
    max_delta_s: float,
) -> Mapping[str, Any] | None:
    target = float(target_time_s)
    tolerance = float(max_delta_s)
    if not math.isfinite(target) or not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("target time and tolerance must be finite")
    candidates: list[tuple[float, int, int, Mapping[str, Any]]] = []
    for ordinal, row in enumerate(rows):
        try:
            time_s = float(row["time_s"])
            index = int(str(row.get("time_bin_index", ordinal)).strip())
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("grid row lacks valid time_s/time_bin_index") from exc
        delta = abs(time_s - target)
        if delta <= tolerance + 1e-15:
            candidates.append((delta, index, ordinal, row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][3]


def _continuity_valid(row: Mapping[str, Any]) -> bool:
    value = row.get("continuity_valid", row.get("continuity_status", "1"))
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "valid", "continuous"}:
        return True
    if text in {"0", "false", "no", "invalid", "gap", "inconclusive"}:
        return False
    raise ValueError(f"invalid continuity flag: {value!r}")


def find_recovery_time(
    rows: Sequence[Mapping[str, Any]],
    baseline_db: float,
    event_end_s: float,
    step_s: float = 0.02,
    stable_tolerance_db: float = 1.0,
    stable_rows: int = RECOVERY_STABLE_ROWS,
) -> RecoveryResult:
    baseline = float(baseline_db)
    end = float(event_end_s)
    step = float(step_s)
    tolerance = float(stable_tolerance_db)
    if not all(math.isfinite(value) for value in (baseline, end, step, tolerance)) or step <= 0.0:
        raise ValueError("recovery inputs must be finite and step must be positive")
    ordered = sorted((row for row in rows if float(row["time_s"]) > end), key=lambda row: float(row["time_s"]))
    if not ordered:
        return RecoveryResult("RECOVERY_RIGHT_CENSORED", None, None, 0, "no_post_event_rows")
    count = 0
    first_stable_time: float | None = None
    previous_time: float | None = None
    for row in ordered:
        time_s = float(row["time_s"])
        if previous_time is not None and time_s - previous_time > step * 1.5:
            return RecoveryResult("RECOVERY_INCONCLUSIVE_GAP", None, None, count, "time_gap")
        if not _continuity_valid(row):
            return RecoveryResult("RECOVERY_INCONCLUSIVE_GAP", None, None, count, "continuity_invalid")
        gain = row.get("common_gain_db")
        try:
            gain_db = float(gain)
        except (TypeError, ValueError):
            gain_db = math.nan
        if math.isfinite(gain_db) and abs(gain_db - baseline) <= tolerance:
            if count == 0:
                first_stable_time = time_s
            count += 1
            if count >= int(stable_rows):
                assert first_stable_time is not None
                return RecoveryResult(
                    "RECOVERY_OBSERVED",
                    first_stable_time - end,
                    first_stable_time,
                    count,
                    "stable_within_tolerance",
                )
        else:
            count = 0
            first_stable_time = None
        previous_time = time_s
    return RecoveryResult("RECOVERY_RIGHT_CENSORED", None, None, count, "record_ended_before_stability")


def parse_bool(value: Any, field_name: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    raise ValueError(f"invalid boolean {field_name}: {value!r}")


def parse_optional_float(value: Any, field_name: str) -> float | None:
    if value is None or str(value).strip().lower() in {"", "nan", "null", "none"}:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid float {field_name}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite float {field_name}: {value!r}")
    return result


def parse_required_float(value: Any, field_name: str) -> float:
    result = parse_optional_float(value, field_name)
    if result is None:
        raise ValueError(f"missing required float {field_name}")
    return result


def parse_required_int(value: Any, field_name: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer {field_name}: {value!r}") from exc

