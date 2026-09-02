"""Directly runnable DLL output tests; pytest is not required."""

from audit_dll_code_bias_outputs import audit_outputs


def test_dll_audit() -> None:
    result = audit_outputs()
    assert result["audit"] == "DLL_CODE_BIAS_AUDIT_PASS"
    assert result["mode_counts"]["pre_cancellation"] == 20
    assert result["mode_counts"]["fitted_model_cancellation"] == 20


if __name__ == "__main__":
    test_dll_audit()
    print("PASS test_dll_audit")
