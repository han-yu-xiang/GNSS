from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.analysis.channel_modeling.rain_stage3_effect_layer_v1 import (
    FINAL_COLUMNS,
    apply_effect_to_rows,
    build_stage3_episodes,
    fit_rain_effect_model,
    load_stage3_evidence,
    validate_output_namespace,
    validate_new_only_namespace,
)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_load_stage3_evidence_filters_to_reliable_persistent_paths(tmp_path: Path) -> None:
    stage3 = tmp_path / "stage3_persistence.csv"
    reliable = tmp_path / "stage3_reliable_centers.csv"
    _write_csv(
        stage3,
        [
            "center_window_id", "center_recording_time_s", "selected_L", "multipath_id",
            "excess_delay_samples", "doppler_offset_hz", "relative_power_db",
            "matched_window_count", "longest_consecutive_count", "persistence_pass", "match_pattern",
        ],
        [
            {"center_window_id": 10, "center_recording_time_s": 1, "selected_L": 2, "multipath_id": 1,
             "excess_delay_samples": 1.1, "doppler_offset_hz": 5, "relative_power_db": -6,
             "matched_window_count": 3, "longest_consecutive_count": 3, "persistence_pass": 1, "match_pattern": "111"},
            {"center_window_id": 11, "center_recording_time_s": 1.1, "selected_L": 2, "multipath_id": 1,
             "excess_delay_samples": 1.2, "doppler_offset_hz": 6, "relative_power_db": -7,
             "matched_window_count": 2, "longest_consecutive_count": 2, "persistence_pass": 0, "match_pattern": "110"},
        ],
    )
    _write_csv(
        reliable,
        ["center_window_id", "recording_time_s", "selected_L", "multipath_count", "minimum_path_run", "reliable_multipath"],
        [{"center_window_id": 10, "recording_time_s": 1, "selected_L": 2, "multipath_count": 1, "minimum_path_run": 3, "reliable_multipath": 1}],
    )

    evidence = load_stage3_evidence(
        [{"weather": "Clear", "scene_id": "s", "prn": "G01", "tracking_channel": 1,
          "stage3_persistence": stage3, "stage3_reliable_centers": reliable}]
    )

    assert len(evidence) == 1
    assert evidence[0]["delay_ns"] == pytest.approx(1.1 * 1e9 / 10_230_000)
    assert evidence[0]["source_semantics"] == "STAGE3_RELIABLE_EVIDENCE"
    assert evidence[0]["gold_labels_used_for_selection"] is False


def test_build_stage3_episodes_merges_overlapping_persistence_support() -> None:
    evidence = [
        {"task_id": "a", "center_window_id": 10},
        {"task_id": "a", "center_window_id": 14},
        {"task_id": "a", "center_window_id": 20},
    ]

    result = build_stage3_episodes(evidence, persistence_radius=2)

    assert [row["episode_id"] for row in result] == ["a__episode_0001", "a__episode_0001", "a__episode_0002"]


def test_fit_model_is_stage4_independent_and_keeps_scientific_provenance() -> None:
    evidence = [
        {"weather": "Clear", "task_id": "c", "episode_id": "c__episode_0001", "delay_ns": 100.0,
         "doppler_hz": 1.0, "power_db": -5.0, "path_id": 1,
         "source_semantics": "STAGE3_RELIABLE_EVIDENCE", "gold_labels_used_for_selection": False},
        {"weather": "MidRain", "task_id": "m", "episode_id": "m__episode_0001", "delay_ns": 120.0,
         "doppler_hz": 2.0, "power_db": -8.0, "path_id": 1,
         "source_semantics": "STAGE3_RELIABLE_EVIDENCE", "gold_labels_used_for_selection": False},
        {"weather": "HeavyRain", "task_id": "h", "episode_id": "h__episode_0001", "delay_ns": 140.0,
         "doppler_hz": 3.0, "power_db": -10.0, "path_id": 1,
         "source_semantics": "STAGE3_RELIABLE_EVIDENCE", "gold_labels_used_for_selection": False},
    ]

    model = fit_rain_effect_model(evidence)

    assert model["model_id"] == "rain-stage3-effect-layer-v1"
    assert model["stage4_used_for_fit"] is False
    assert model["gold_labels_used_for_selection"] is False
    assert "Clear" in model["distributions"]
    assert "MidRain" in model["distributions"]
    assert model["support"]["RainPooled"]["path_row_count"] == 2
    assert model["support"]["RainPooled"]["task_count"] == 2


def test_apply_preserves_schema_main_path_and_positive_nlos_with_continuous_phase() -> None:
    model = {
        "model_id": "rain-stage3-effect-layer-v1",
        "distributions": {
            "Clear": {
                "log_delay_ns": [0.0, 0.0], "doppler_hz": [0.0, 0.0], "power_db": [0.0, 0.0]
            },
            "HeavyRain": {
                "log_delay_ns": [0.1, 0.1], "doppler_hz": [10.0, 10.0], "power_db": [-6.0, -6.0]
            },
        },
    }
    rows = [
        {"ms": "1", "SatelliteID": "Low", "NLOSPathID": "0", "RelativeDelay": "0",
         "RelativeDoppler": "0", "RelativeAmplitude": "1", "RelativePhase_rad": "0"},
        {"ms": "1", "SatelliteID": "Low", "NLOSPathID": "1", "RelativeDelay": "100",
         "RelativeDoppler": "1", "RelativeAmplitude": "0.5", "RelativePhase_rad": "0"},
        {"ms": "2", "SatelliteID": "Low", "NLOSPathID": "1", "RelativeDelay": "100",
         "RelativeDoppler": "1", "RelativeAmplitude": "0.5", "RelativePhase_rad": "0"},
        {"ms": "41", "SatelliteID": "Low", "NLOSPathID": "1", "RelativeDelay": "100",
         "RelativeDoppler": "1", "RelativeAmplitude": "0.5", "RelativePhase_rad": "0"},
    ]

    output = apply_effect_to_rows(rows, model, weather="HeavyRain", master_seed=7)

    assert list(output[0]) == list(FINAL_COLUMNS)
    assert output[0]["RelativeDelay"] == pytest.approx(0.0)
    assert output[1]["RelativeAmplitude"] > 0
    assert output[1]["RelativeDelay"] == output[2]["RelativeDelay"]
    assert output[1]["RelativeDoppler"] == output[2]["RelativeDoppler"]
    assert output[2]["RelativePhase_rad"] != output[1]["RelativePhase_rad"]


def test_new_only_rejects_existing_namespace(tmp_path: Path) -> None:
    existing = tmp_path / "already_exists"
    existing.mkdir()

    with pytest.raises(FileExistsError):
        validate_new_only_namespace(existing)


def test_new_only_accepts_absent_namespace(tmp_path: Path) -> None:
    validate_new_only_namespace(tmp_path / "new_namespace")


def test_sage_results_namespace_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        validate_output_namespace(tmp_path / "scenes" / "x" / "sage_results" / "rain")
