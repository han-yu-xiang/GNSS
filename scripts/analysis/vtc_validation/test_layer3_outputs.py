"""Directly runnable Layer 3 output tests; pytest is not required."""

from audit_layer3_outputs import audit_outputs


def test_layer3_audit() -> None:
    result = audit_outputs()
    assert result["audit"] == "LAYER3_NATIVE_MODEL_AUDIT_PASS"
    assert result["event_count"] == 4


if __name__ == "__main__":
    test_layer3_audit()
    print("PASS test_layer3_audit")
