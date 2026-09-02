"""Directly runnable Layer 2 output tests; pytest is not required."""

from __future__ import annotations

from audit_layer2_outputs import audit_outputs


def test_layer2_audit() -> None:
    result = audit_outputs()
    assert result["audit"] == "LAYER2_MULTIPATH_STRESS_AUDIT_PASS"
    assert result["trial_count"] == 192
    assert len(result["source_events"]) == 4


if __name__ == "__main__":
    test_layer2_audit()
    print("PASS test_layer2_audit")
