"""Directly runnable Layer 1 output tests; pytest is not required."""

from __future__ import annotations

from audit_layer1_outputs import audit_outputs


def test_layer1_audit() -> None:
    result = audit_outputs()
    assert result["audit"] == "LAYER1_CONTROLLED_AUDIT_PASS"
    assert result["trial_count"] == 216


if __name__ == "__main__":
    test_layer1_audit()
    print("PASS test_layer1_audit")
