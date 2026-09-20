from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.generate_darkroom_5min_multiseed_collection import (
    COLLECTION_ID,
    FORMAL_DURATION_MS,
    build_collection_matrix,
    build_smoke_matrix,
    derive_rain_seed,
    read_generation_manifest,
    table_filename,
    validate_collection_namespace,
    validate_canonical_rows,
)


def test_matrix_contains_the_approved_48_realizations_in_stable_order() -> None:
    rows = build_collection_matrix(collection_id=COLLECTION_ID, duration_ms=FORMAL_DURATION_MS)

    assert len(rows) == 48
    assert [row["environment_slug"] for row in rows[:12]] == ["urban"] * 12
    assert [row["mode"] for row in rows[:12]] == ["good"] * 4 + ["poor"] * 4 + ["rain"] * 4
    assert [row["sample_index"] for row in rows[:12]] == ["01", "02", "03", "04"] * 3
    assert all(row["duration_ms"] == 300_000 for row in rows)
    assert all(row["expected_rows"] == 3_600_000 for row in rows)
    assert all(row["new_only"] is True for row in rows)
    assert all(row["resume_allowed"] is False for row in rows)


def test_good_poor_share_base_seed_and_rain_points_to_matching_good() -> None:
    rows = build_collection_matrix(collection_id=COLLECTION_ID, duration_ms=FORMAL_DURATION_MS)
    by_key = {(row["environment_slug"], row["mode"], row["sample_index"]): row for row in rows}

    for environment_slug in {row["environment_slug"] for row in rows}:
        for index in ("01", "02", "03", "04"):
            good = by_key[(environment_slug, "good", index)]
            poor = by_key[(environment_slug, "poor", index)]
            rain = by_key[(environment_slug, "rain", index)]
            assert good["base_master_seed"] == poor["base_master_seed"]
            assert rain["base_source_table"] == good["final_table"]
            assert rain["base_source_sha256"] is None
            assert rain["rain_seed"] == derive_rain_seed(good["base_master_seed"])
            assert rain["base_quality"] == "GOOD_TRACKED_BASELINE"
            assert rain["weather_layer"] == "RainPooled"


def test_final_filename_is_deterministic_and_explicit() -> None:
    assert table_filename("urban", "good", "01") == "urban__good__01.csv"
    assert table_filename("special_reflective", "rain", "04") == "special_reflective__rain__04.csv"


def test_smoke_matrix_is_a_new_three_mode_pair_not_a_truncated_poor_run() -> None:
    rows = build_smoke_matrix(collection_id="smoke_collection")

    assert len(rows) == 3
    assert {(row["environment_slug"], row["sample_index"]) for row in rows} == {("urban", "01")}
    assert [row["mode"] for row in rows] == ["good", "poor", "rain"]
    assert all(row["duration_ms"] == FORMAL_DURATION_MS for row in rows)


def test_collection_namespace_requires_new_direct_child(tmp_path: Path) -> None:
    project_root = tmp_path
    collection_root = project_root / "dataset_generation_logs" / "channel_modeling"
    collection_root.mkdir(parents=True)

    candidate = collection_root / "new_collection"
    validate_collection_namespace(project_root, candidate, require_absent=True)
    assert not candidate.exists()

    candidate.mkdir()
    with pytest.raises(FileExistsError):
        validate_collection_namespace(project_root, candidate, require_absent=True)

    with pytest.raises(ValueError):
        validate_collection_namespace(project_root, project_root / "scenes" / "x", require_absent=True)


def test_canonical_rows_require_twelve_rows_per_ms_and_four_paths_per_band() -> None:
    rows = []
    for band in ("Low", "Mid", "High"):
        for path_id in range(4):
            rows.append(
                {
                    "ms": 1,
                    "SatelliteID": band,
                    "NLOSPathID": path_id,
                    "RelativeDelay": 0.0,
                    "RelativeDoppler": 0.0,
                    "RelativeAmplitude": 1.0,
                    "RelativePhase_rad": 0.0,
                }
            )

    summary = validate_canonical_rows(rows, duration_ms=1)

    assert summary["rows"] == 12
    assert summary["rows_per_millisecond"] == 12
    assert summary["path_ids_per_band"] == {"Low": [0, 1, 2, 3], "Mid": [0, 1, 2, 3], "High": [0, 1, 2, 3]}


def test_generation_manifest_reader_requires_the_frozen_contract(tmp_path: Path) -> None:
    path = tmp_path / "generation_manifest.csv"
    path.write_text(
        "task_id,actual_rows,final_sha256,generation_status\n"
        "task-a,12,abc,COMPLETED\n",
        encoding="utf-8",
    )

    rows = read_generation_manifest(path)

    assert rows == [{"task_id": "task-a", "actual_rows": "12", "final_sha256": "abc", "generation_status": "COMPLETED"}]
