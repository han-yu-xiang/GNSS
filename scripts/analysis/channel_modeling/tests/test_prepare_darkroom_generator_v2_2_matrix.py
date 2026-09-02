from __future__ import annotations

from scripts.analysis.channel_modeling.prepare_darkroom_generator_v2_2_matrix import (
    MATRIX_ID,
    QUALITY_SEQUENCE,
    QUALITY_SHORT,
)
from scripts.analysis.channel_modeling.prepare_darkroom_generator_v2_2_request import PAIRING_IDS


def test_v22_matrix_has_eight_rows_in_frozen_order() -> None:
    environments = tuple(PAIRING_IDS)
    assert environments == ("Urban", "Special Reflective", "Mountain/Valley", "Highway/Open")
    assert QUALITY_SEQUENCE == ("GOOD_TRACKED_BASELINE", "POOR_CONDITIONAL")
    assert len(environments) * len(QUALITY_SEQUENCE) == 8
    assert MATRIX_ID == "environment_quality_pair_20s_v2_2_20260827"
    assert QUALITY_SHORT["GOOD_TRACKED_BASELINE"] == "good"
    assert QUALITY_SHORT["POOR_CONDITIONAL"] == "poor"


def test_v22_matrix_pairing_ids_are_unique_by_environment() -> None:
    assert len(set(PAIRING_IDS.values())) == 4
    assert all(value.endswith("-quality-pair-20260827") for value in PAIRING_IDS.values())
