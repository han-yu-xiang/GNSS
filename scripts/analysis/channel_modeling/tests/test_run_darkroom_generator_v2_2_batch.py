from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.run_darkroom_generator_v2_2_batch import (
    BATCH_ENVIRONMENTS,
    BATCH_QUALITY_MODES,
    build_batch_rows,
    validate_execution_duration,
    validate_new_only_collection_dir,
)


def test_build_batch_rows_has_frozen_eight_cell_order_and_20ms_rows() -> None:
    rows = build_batch_rows(
        collection_id="smoke_20ms",
        duration_ms=20,
        master_seed=20260827,
    )

    assert len(rows) == 8
    assert [row["environment_class"] for row in rows] == [
        "Urban",
        "Urban",
        "Special Reflective",
        "Special Reflective",
        "Mountain/Valley",
        "Mountain/Valley",
        "Highway/Open",
        "Highway/Open",
    ]
    assert [row["quality_mode"] for row in rows] == list(BATCH_QUALITY_MODES) * 4
    assert all(row["duration_ms"] == 20 for row in rows)
    assert all(row["expected_rows"] == 240 for row in rows)
    assert all(row["new_only"] is True for row in rows)
    assert all(row["resume_allowed"] is False for row in rows)


def test_build_batch_rows_uses_frozen_environment_and_quality_sequences() -> None:
    rows = build_batch_rows(collection_id="five_minutes", duration_ms=300_000, master_seed=20260827)

    assert tuple(dict.fromkeys(row["environment_class"] for row in rows)) == BATCH_ENVIRONMENTS
    assert all(row["duration_ms"] == 300_000 for row in rows)
    assert all(row["expected_rows"] == 3_600_000 for row in rows)
    assert all(row["gold_labels_used_for_generation"] is False for row in rows)


def test_new_only_collection_dir_rejects_existing_namespace(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(FileExistsError):
        validate_new_only_collection_dir(existing)


def test_new_only_collection_dir_accepts_absent_namespace(tmp_path: Path) -> None:
    absent = tmp_path / "absent"

    validate_new_only_collection_dir(absent)
    assert not absent.exists()


def test_20ms_is_validation_only_and_cannot_execute_eight_quality_cells() -> None:
    with pytest.raises(ValueError, match="20 ms is validation-only"):
        validate_execution_duration(20)


def test_5min_is_allowed_for_full_quality_batch_execution() -> None:
    validate_execution_duration(300_000)
