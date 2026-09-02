from __future__ import annotations

import pytest

from scripts.analysis.channel_modeling.audit_darkroom_generator_v2_1 import (
    enforce_v21_canonical_rows,
    enforce_v21_support_summary,
)


def _row(amplitude: float) -> dict[str, str]:
    return {
        "ms": "1",
        "SatelliteID": "Low",
        "NLOSPathID": "1",
        "RelativeDelay": "10",
        "RelativeDoppler": "1",
        "RelativeAmplitude": str(amplitude),
        "RelativePhase_rad": "0",
    }


def test_v21_auditor_rejects_zero_nlos_amplitude() -> None:
    with pytest.raises(ValueError, match="positive"):
        enforce_v21_canonical_rows([_row(0.0)])


def test_v21_auditor_requires_all_active_support_contract() -> None:
    enforce_v21_support_summary({
        "ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT": True,
        "ACTIVATION_MODEL_NOT_USED_FOR_GENERATION": True,
        "CONDITIONAL_MULTIPATH_SCENARIO": True,
    })
    with pytest.raises(ValueError, match="CONDITIONAL_MULTIPATH_SCENARIO"):
        enforce_v21_support_summary({
            "ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT": True,
            "ACTIVATION_MODEL_NOT_USED_FOR_GENERATION": True,
        })
