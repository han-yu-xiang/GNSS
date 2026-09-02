from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.audit_darkroom_generator_v2_2 import (
    enforce_v22_canonical_rows,
    enforce_v22_quality_semantics,
)
from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import FINAL_COLUMNS


def _canonical_path(tmp_path: Path, bad: str | None = None) -> Path:
    path = tmp_path / "darkroom_channel_parameters.csv"
    rows = []
    for satellite in ("Low", "Mid", "High"):
        for path_id in range(4):
            row = {
                "ms": 1,
                "SatelliteID": satellite,
                "NLOSPathID": path_id,
                "RelativeDelay": 0.0 if path_id == 0 else 10.0 + path_id,
                "RelativeDoppler": 0.0 if path_id == 0 else float(path_id),
                "RelativeAmplitude": 1.0 if path_id == 0 else 0.1 * path_id,
                "RelativePhase_rad": 0.0,
            }
            rows.append(row)
    if bad == "zero-nlos":
        rows[1]["RelativeAmplitude"] = 0.0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FINAL_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_v22_auditor_accepts_complete_positive_canonical_fixture(tmp_path: Path) -> None:
    result = enforce_v22_canonical_rows(_canonical_path(tmp_path), 1)
    assert result["row_count"] == 12
    assert result["nlos_rows"] == 9


def test_v22_auditor_rejects_nonpositive_nlos(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="strictly positive"):
        enforce_v22_canonical_rows(_canonical_path(tmp_path, "zero-nlos"), 1)


def test_v22_good_quality_semantics_fixture() -> None:
    timeline = {
        (ms, band): {
            "quality_state": "TRACKED_GOOD",
            "quality_event_id": None,
            "quality_envelope_linear": 1.0,
            "phase_observable": True,
        }
        for ms in range(1, 4)
        for band in ("LOW", "MID", "HIGH")
    }
    result = enforce_v22_quality_semantics(timeline, {}, 3, "GOOD_TRACKED_BASELINE", 0, 0)
    assert result["quality_event_count"] == 0
