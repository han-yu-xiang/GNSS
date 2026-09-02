from __future__ import annotations

import math

import pytest

from scripts.analysis.channel_modeling.audit_darkroom_generator_v2 import (
    audit_canonical_rows,
    validate_phase_sequence,
)


def _rows(duration_ms: int = 1) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ms in range(1, duration_ms + 1):
        for satellite_id in ("Low", "Mid", "High"):
            for path_id in range(4):
                rows.append(
                    {
                        "ms": ms,
                        "SatelliteID": satellite_id,
                        "NLOSPathID": path_id,
                        "RelativeDelay": 0.0 if path_id == 0 else 100.0 * path_id,
                        "RelativeDoppler": 0.0 if path_id == 0 else float(path_id),
                        "RelativeAmplitude": 1.0 if path_id == 0 else (0.0 if path_id == 3 else 0.2),
                        "RelativePhase_rad": 0.0,
                    }
                )
    return rows


def test_auditor_accepts_exact_all_band_fixed_slot_rows() -> None:
    result = audit_canonical_rows(_rows(2), duration_ms=2)
    assert result["exact_12_rows_per_ms"] is True
    assert result["canonical_empty_field_count"] == 0
    assert result["fixed_slot_identity"] is True


def test_auditor_rejects_duplicate_or_wrong_order_rows() -> None:
    rows = _rows()
    rows[-1] = dict(rows[-2])
    with pytest.raises(ValueError, match="identity|duplicate|order"):
        audit_canonical_rows(rows, duration_ms=1)


def test_auditor_rejects_empty_or_nonfinite_canonical_values() -> None:
    rows = _rows()
    rows[1]["RelativeDelay"] = ""
    with pytest.raises(ValueError, match="empty"):
        audit_canonical_rows(rows, duration_ms=1)
    rows = _rows()
    rows[1]["RelativeDelay"] = math.inf
    with pytest.raises(ValueError, match="finite"):
        audit_canonical_rows(rows, duration_ms=1)


def test_phase_sequence_uses_one_ms_doppler_recurrence() -> None:
    phases = [0.2, 0.2 + 2.0 * math.pi * 10.0 * 0.001]
    validate_phase_sequence(phases, 10.0)
    with pytest.raises(ValueError, match="phase"):
        validate_phase_sequence([0.2, 0.3], 10.0)

