from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
CORE_PATH = ROOT / "scripts" / "analysis" / "channel_modeling" / "lock_amplitude_phase_recovery_core.py"


def load_core():
    assert CORE_PATH.exists(), f"v1 core is not implemented yet: {CORE_PATH}"
    spec = importlib.util.spec_from_file_location("lock_amplitude_phase_recovery_core", CORE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_core_module_is_available_after_red():
    assert CORE_PATH.exists(), "The mapping core must exist before the behavior tests can pass."


def test_raised_cosine_envelopes_have_exact_endpoints_and_are_monotone():
    core = load_core()
    entry = [core.raised_cosine_entry(i / 10.0, 0.2) for i in range(11)]
    recovery = [core.raised_cosine_recovery(i / 10.0, 0.2) for i in range(11)]
    assert entry[0] == pytest.approx(1.0, abs=1e-12)
    assert entry[-1] == pytest.approx(0.2, abs=1e-12)
    assert recovery[0] == pytest.approx(0.2, abs=1e-12)
    assert recovery[-1] == pytest.approx(1.0, abs=1e-12)
    assert all(entry[i] >= entry[i + 1] for i in range(10))
    assert all(recovery[i] <= recovery[i + 1] for i in range(10))


def test_phase_uses_one_ms_relative_doppler_increment_and_wraps():
    core = load_core()
    expected = core.wrap_to_pi(0.25 + 2.0 * 3.141592653589793 * 125.0 * 0.001)
    assert core.evolve_phase_1ms(0.25, 125.0) == pytest.approx(expected, abs=1e-12)
    assert -3.141592653589793 <= core.wrap_to_pi(20.0) < 3.141592653589793


def test_shared_envelope_preserves_nlos_relative_amplitude_and_allows_nlos_above_path_zero():
    core = load_core()
    amplitudes = core.compose_path_amplitudes(0.8, 0.5, (True, True, False), (1.5, 0.25, None))
    assert amplitudes == pytest.approx((0.4, 0.6, 0.1, 0.0), abs=1e-12)


def test_inactive_slots_use_zero_amplitude_and_null_nonamplitude_fields():
    core = load_core()
    row = core.compose_slot_row(2, 3, False, None, None, None)
    assert row["RelativeAmplitude"] == 0.0
    assert row["RelativeDelay"] is None
    assert row["RelativeDoppler"] is None
    assert row["RelativePhase_rad"] is None


def test_state_sequence_has_entry_hold_recovery_and_no_overlap():
    core = load_core()
    states = core.make_state_sequence(lock_duration_ms=100, entry_ramp_ms=20, recovery_ms=100)
    assert states[:20] == [core.LockState.FADING_TO_LOCK_BAD] * 20
    assert states[20:100] == [core.LockState.LOCK_BAD_HOLD] * 80
    assert states[100:200] == [core.LockState.RECOVERING] * 100
    assert len(states) == 200


def test_nearest_grid_match_respects_tolerance_and_lower_index_tie_break():
    core = load_core()
    rows = [
        {"time_s": "1.00", "time_bin_index": "10"},
        {"time_s": "1.02", "time_bin_index": "11"},
    ]
    chosen = core.nearest_time_row(rows, 1.01, 0.011)
    assert chosen["time_bin_index"] == "10"
    assert core.nearest_time_row(rows, 2.0, 0.011) is None


def test_recovery_detection_stops_at_continuity_gap():
    core = load_core()
    rows = [
        {"time_s": 1.00, "common_gain_db": -0.5, "continuity_valid": "1"},
        {"time_s": 1.02, "common_gain_db": -0.4, "continuity_valid": "1"},
        {"time_s": 1.04, "common_gain_db": -0.3, "continuity_valid": "0"},
        {"time_s": 1.06, "common_gain_db": -0.2, "continuity_valid": "1"},
    ]
    result = core.find_recovery_time(rows, baseline_db=0.0, event_end_s=0.98, step_s=0.02)
    assert result.status == "RECOVERY_INCONCLUSIVE_GAP"
    assert result.duration_s is None


def test_empirical_mode_rejects_exact_zero_floor_and_stress_requires_explicit_floor():
    core = load_core()
    with pytest.raises(ValueError):
        core.validate_floor(0.0, core.LockMappingMode.EMPIRICAL_DIAGNOSTIC_PROXY)
    with pytest.raises(ValueError):
        core.validate_floor(None, core.LockMappingMode.FORCED_LOCK_LOSS_STRESS)
    assert core.validate_floor(0.01, core.LockMappingMode.FORCED_LOCK_LOSS_STRESS) == pytest.approx(0.01)


def test_canonical_manifest_hash_is_order_invariant():
    core = load_core()
    left = {"b": 2, "a": [1, 2]}
    right = {"a": [1, 2], "b": 2}
    assert core.sha256_json(left) == core.sha256_json(right)
