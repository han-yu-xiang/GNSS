import csv
import json
import os
from pathlib import Path

import pytest

from scripts.sage_pipeline.rain.audit_rain_sage_task import (
    REQUIRED_OUTPUTS,
    _filesystem_path,
    _path_is_within_expected_namespace,
    audit_task,
)


STAGE0_SYMBOL_FIELDS = [
    "symbol_id", "telemetry_row", "prn", "tow_s", "sample_start_zero_based",
    "recording_time_s", "nav_symbol", "tracking_index", "tracking_doppler_hz",
    "code_frequency_hz", "cn0_db_hz", "carrier_lock_test", "tracking_tow_ms",
    "next_step_samples", "next_tow_step_s", "continuous_to_next",
]
STAGE0_WINDOW_FIELDS = [
    "window_id", "symbol_index", "sample_start_zero_based", "recording_time_s",
    "tow_s", "nav_symbol_1", "nav_symbol_2", "split_samples",
    "tracking_doppler_hz", "code_frequency_hz", "cn0_db_hz", "vehicle_speed_kmh",
    "speed_source", "relative_doppler_bound_hz",
]
STAGE1_FIELDS = [
    "window_id", "recording_time_s", "tow_s", "cn0_db_hz", "nav_symbol_1",
    "nav_symbol_2", "scan_valid", "main_delay_samples", "main_doppler_hz",
    "main_score", "residual_peak1_delay_samples", "residual_peak1_doppler_hz",
    "residual_peak1_power_db", "residual_peak2_delay_samples",
    "residual_peak2_doppler_hz", "residual_peak2_power_db",
    "residual_peak3_delay_samples", "residual_peak3_doppler_hz",
    "residual_peak3_power_db", "has_one_strong_residual",
    "has_two_strong_residuals", "screen_score_db", "error_message",
]
STAGE2_MODEL_FIELDS = [
    "window_id", "recording_time_s", "model_order", "multipath_count", "rss",
    "bic", "bic_gain_from_previous", "rss_gain_percent_from_previous",
    "model_valid", "selected", "minimum_multipath_power_db",
    "minimum_separation_samples", "maximum_relative_doppler_hz",
    "maximum_coherence",
]
STAGE2_WINDOW_FIELDS = [
    "window_id", "recording_time_s", "tow_s", "selected_L", "multipath_count",
    "selected_bic", "selected_rss", "minimum_multipath_power_db",
    "maximum_relative_doppler_hz", "maximum_coherence",
]
STAGE2_PATH_FIELDS = [
    "window_id", "recording_time_s", "selected_L", "path_id", "is_multipath",
    "delay_samples", "excess_delay_samples", "excess_delay_chips",
    "excess_path_length_m", "doppler_hz", "doppler_offset_hz", "relative_power_db",
]
STAGE3_PERSISTENCE_FIELDS = [
    "center_window_id", "center_recording_time_s", "selected_L", "multipath_id",
    "excess_delay_samples", "doppler_offset_hz", "relative_power_db",
    "matched_window_count", "longest_consecutive_count", "persistence_pass",
    "match_pattern",
]
STAGE3_RELIABLE_FIELDS = [
    "center_window_id", "recording_time_s", "selected_L", "multipath_count",
    "minimum_path_run", "reliable_multipath",
]
STAGE4_SUMMARY_FIELDS = [
    "center_window_id", "recording_time_s", "stage2_L", "joint_selected_L",
    "joint_multipath_count", "joint_rss", "joint_bic", "snapshot_wins_vs_L1",
    "minimum_multipath_power_db", "maximum_relative_doppler_hz",
    "maximum_coherence", "joint_valid",
]
STAGE4_PATH_FIELDS = [
    "center_window_id", "joint_selected_L", "path_id", "is_multipath",
    "delay_samples", "excess_delay_samples", "excess_delay_chips", "doppler_hz",
    "doppler_offset_hz", "mean_relative_power_db", "phase_rad", "relative_phase_rad",
    "relative_phase_available", "relative_amplitude", "relative_amplitude_db",
    "phase_source",
]


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _task_spec(output_dir: Path) -> dict[str, object]:
    return {
        "task_id": "rain__clear__G24__ch10",
        "weather_condition": "Clear",
        "scene_id": "F1023_clear",
        "prn": "G24",
        "tracking_channel": 10,
        "sample_rate_hz": 10230000,
        "expected_valid_symbol_count": 1,
        "expected_window_count": 1,
        "expected_output_namespace": str(output_dir),
    }


def _make_fixture(tmp_path: Path, confirmed: bool = False) -> tuple[dict[str, object], Path]:
    output_dir = tmp_path / "scenes" / "F1023_clear" / "sage_results" / "rain_sage_v1" / "G24"
    output_dir.mkdir(parents=True)
    for name in REQUIRED_OUTPUTS:
        (output_dir / name).write_bytes(b"placeholder\n")
    for name in (
        "doppler_sign.mat", "stage0_nav_catalog.mat", "stage1_nav_fast_scan.mat",
        "stage1_nav_progress.mat", "stage2_nav_progress.mat", "stage2_nav_sage_L1_L4.mat",
        "stage3_nav_persistence.mat", "stage4_nav_joint_100ms.mat",
    ):
        (output_dir / name).write_bytes(b"MATLAB fixture\n")
    provenance = {
        "scene_id": "F1023_clear",
        "branch": "darkroom_channel_emulation",
        "weather_condition": "clear",
        "prn": "G24",
        "tracking_channel": 10,
        "sample_rate_hz": 10230000,
        "raw_iq_opened": False,
        "geometry_available": False,
        "elevation_conditioning": False,
    }
    (output_dir / "rain_stage0_provenance.json").write_text(
        json.dumps(provenance), encoding="utf-8"
    )
    _write_csv(output_dir / "stage0_valid_symbols.csv", STAGE0_SYMBOL_FIELDS, [{
        "symbol_id": 1, "telemetry_row": 1, "prn": 24, "tow_s": 1.0,
        "sample_start_zero_based": 100, "recording_time_s": 0.0, "nav_symbol": 1,
        "tracking_index": 1, "tracking_doppler_hz": 2.0, "code_frequency_hz": 3.0,
        "cn0_db_hz": 40.0, "carrier_lock_test": 1.0, "tracking_tow_ms": 0,
        "next_step_samples": 204600, "next_tow_step_s": 0.02, "continuous_to_next": 1,
    }])
    _write_csv(output_dir / "stage0_valid_40ms_windows.csv", STAGE0_WINDOW_FIELDS, [{
        "window_id": 1, "symbol_index": 1, "sample_start_zero_based": 100,
        "recording_time_s": 0.0, "tow_s": 1.0, "nav_symbol_1": 1,
        "nav_symbol_2": -1, "split_samples": 204600, "tracking_doppler_hz": 2.0,
        "code_frequency_hz": 3.0, "cn0_db_hz": 40.0, "vehicle_speed_kmh": "NaN",
        "speed_source": "unavailable_no_NMEA", "relative_doppler_bound_hz": 40.0,
    }])
    _write_csv(output_dir / "stage1_nav_fast_scan.csv", STAGE1_FIELDS, [{
        "window_id": 1, "recording_time_s": 0.0, "tow_s": 1.0, "cn0_db_hz": 40.0,
        "nav_symbol_1": 1, "nav_symbol_2": -1, "scan_valid": 1,
        "main_delay_samples": 0.0, "main_doppler_hz": 2.0, "main_score": 10.0,
        "residual_peak1_delay_samples": 2.0, "residual_peak1_doppler_hz": 2.0,
        "residual_peak1_power_db": -30.0, "residual_peak2_delay_samples": "NaN",
        "residual_peak2_doppler_hz": "NaN", "residual_peak2_power_db": "NaN",
        "residual_peak3_delay_samples": "NaN", "residual_peak3_doppler_hz": "NaN",
        "residual_peak3_power_db": "NaN", "has_one_strong_residual": 0,
        "has_two_strong_residuals": 0, "screen_score_db": -30.0, "error_message": "",
    }])
    model_rows = []
    for order in range(1, 5):
        model_rows.append({
            "window_id": 1, "recording_time_s": 0.0, "model_order": order,
            "multipath_count": 0 if order == 1 else 1, "rss": 10.0,
            "bic": 1.0, "bic_gain_from_previous": 0.0,
            "rss_gain_percent_from_previous": 0.0, "model_valid": 1,
            "selected": 1 if order == 1 else 0, "minimum_multipath_power_db": "NaN",
            "minimum_separation_samples": "NaN", "maximum_relative_doppler_hz": 0.0,
            "maximum_coherence": 0.0,
        })
    _write_csv(output_dir / "stage2_model_orders.csv", STAGE2_MODEL_FIELDS, model_rows)
    _write_csv(output_dir / "stage2_selected_windows.csv", STAGE2_WINDOW_FIELDS, [{
        "window_id": 1, "recording_time_s": 0.0, "tow_s": 1.0, "selected_L": 1,
        "multipath_count": 0, "selected_bic": 1.0, "selected_rss": 10.0,
        "minimum_multipath_power_db": "NaN", "maximum_relative_doppler_hz": 0.0,
        "maximum_coherence": 0.0,
    }])
    _write_csv(output_dir / "stage2_selected_paths.csv", STAGE2_PATH_FIELDS, [{
        "window_id": 1, "recording_time_s": 0.0, "selected_L": 1, "path_id": 1,
        "is_multipath": 0, "delay_samples": 0.0, "excess_delay_samples": 0.0,
        "excess_delay_chips": 0.0, "excess_path_length_m": 0.0, "doppler_hz": 2.0,
        "doppler_offset_hz": 0.0, "relative_power_db": 0.0,
    }])
    _write_csv(output_dir / "stage3_persistence.csv", STAGE3_PERSISTENCE_FIELDS, [])
    _write_csv(output_dir / "stage3_reliable_centers.csv", STAGE3_RELIABLE_FIELDS, [{
        "center_window_id": 1, "recording_time_s": 0.0, "selected_L": 1,
        "multipath_count": 0, "minimum_path_run": 0, "reliable_multipath": 0,
    }])
    _write_csv(output_dir / "stage4_joint_summary.csv", STAGE4_SUMMARY_FIELDS, [{
        "center_window_id": 1, "recording_time_s": 0.0, "stage2_L": 1,
        "joint_selected_L": 1, "joint_multipath_count": 1 if confirmed else 0,
        "joint_rss": 10.0, "joint_bic": 1.0, "snapshot_wins_vs_L1": 5,
        "minimum_multipath_power_db": -10.0 if confirmed else "NaN",
        "maximum_relative_doppler_hz": 5.0 if confirmed else 0.0,
        "maximum_coherence": 0.1 if confirmed else 0.0, "joint_valid": 1,
    }])
    path_rows = [{
        "center_window_id": 1, "joint_selected_L": 2 if confirmed else 1,
        "path_id": 1, "is_multipath": 0, "delay_samples": 0.0,
        "excess_delay_samples": 0.0, "excess_delay_chips": 0.0,
        "doppler_hz": 2.0, "doppler_offset_hz": 0.0, "mean_relative_power_db": 0.0,
        "phase_rad": 0.0, "relative_phase_rad": 0.0,
        "relative_phase_available": 1, "relative_amplitude": 1.0,
        "relative_amplitude_db": 0.0, "phase_source": "joint_selected_path_alpha",
    }]
    if confirmed:
        path_rows.append({
        "center_window_id": 1, "joint_selected_L": 2, "path_id": 2,
        "is_multipath": 1, "delay_samples": 2.0, "excess_delay_samples": 2.0,
        "excess_delay_chips": 0.2, "doppler_hz": 7.0, "doppler_offset_hz": 5.0,
        "mean_relative_power_db": -10.0, "phase_rad": 0.5,
        "relative_phase_rad": 0.5, "relative_phase_available": 1,
        "relative_amplitude": 0.316, "relative_amplitude_db": -10.0,
        "phase_source": "joint_selected_path_alpha",
        })
    _write_csv(output_dir / "stage4_joint_paths.csv", STAGE4_PATH_FIELDS, path_rows)
    return _task_spec(output_dir), output_dir


def test_complete_zero_event_artifact_is_not_silently_called_execution_pass(
    tmp_path: Path,
) -> None:
    task, output_dir = _make_fixture(tmp_path)
    result = audit_task(task, output_dir)
    assert result["artifact_completeness"] == "PASS"
    assert result["scientific_status"] == "PASS_NO_CONFIRMED_MULTIPATH"
    assert result["confirmed_events"] == 0
    assert result["confirmed_multipath_paths"] == 0
    assert result["execution_receipt_status"] == "NOT_FOUND"
    assert result["overall_status"] == "INCONCLUSIVE_NO_EXECUTION_RECEIPT"


def test_stage_chain_counts_and_order_accounting_are_reported(tmp_path: Path) -> None:
    task, output_dir = _make_fixture(tmp_path)
    result = audit_task(task, output_dir)
    assert result["stage0_symbols"] == 1
    assert result["stage0_windows"] == 1
    assert result["stage1_scanned_windows"] == 1
    assert result["stage2_model_rows"] == 4
    assert result["stage2_selected_windows"] == 1
    assert result["stage3_reliable_centers"] == 1
    assert result["stage4_joint_rows"] == 1
    assert result["stage2_model_order_counts"] == {"1": 1, "2": 1, "3": 1, "4": 1}


def test_strict_stage4_confirmed_predicate_counts_path(tmp_path: Path) -> None:
    task, output_dir = _make_fixture(tmp_path, confirmed=True)
    result = audit_task(task, output_dir)
    assert result["scientific_status"] == "PASS_WITH_CONFIRMED_MULTIPATH"
    assert result["confirmed_events"] == 1
    assert result["confirmed_multipath_paths"] == 1


def test_wrong_task_identity_fails_closed(tmp_path: Path) -> None:
    task, output_dir = _make_fixture(tmp_path)
    task["prn"] = "G25"
    result = audit_task(task, output_dir)
    assert result["identity_status"] == "FAIL"
    assert result["overall_status"] == "FAIL_IDENTITY_OR_SCHEMA"


def test_missing_required_output_does_not_become_zero_event(tmp_path: Path) -> None:
    task, output_dir = _make_fixture(tmp_path)
    (output_dir / "stage4_joint_summary.csv").write_bytes(b"")
    result = audit_task(task, output_dir)
    assert result["artifact_completeness"] == "FAIL"
    assert result["confirmed_events"] is None
    assert result["scientific_status"] == "NOT_ASSESSABLE"
    assert result["overall_status"] == "FAIL_MISSING_OUTPUT"


def test_existing_output_path_can_be_audited_without_marking_it_new_execution(
    tmp_path: Path,
) -> None:
    task, output_dir = _make_fixture(tmp_path)
    result = audit_task(task, output_dir)
    assert result["output_namespace_exists"] is True
    assert result["new_only_execution"] == "NOT_APPLICABLE_READ_ONLY_AUDIT"


def test_versioned_rerun_namespace_is_accepted_by_auditor(tmp_path: Path) -> None:
    output_dir = (
        tmp_path / "scenes" / "F1023_clear" / "sage_results"
        / "rain_sage_rerun_v1_20260827_r4" / "G24"
    )
    task = {"scene_id": "F1023_clear", "prn": "G24"}
    assert _path_is_within_expected_namespace(task, output_dir)


@pytest.mark.skipif(os.name != "nt", reason="Windows long-path behavior only")
def test_long_windows_receipt_path_gets_extended_prefix() -> None:
    path = Path(
        r"E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_channel_emulation"
        r"\rain_sage_rerun_requests_20260827\rain_sage_fresh_rerun_v1__F1023_clear__G24__ch10__20260827_r4"
        r"\receipts\rain_sage_fresh_rerun_v1__F1023_clear__G24__ch10__20260827_r4_20260827T144043Z_receipt.json"
    )
    assert str(_filesystem_path(path)).startswith("\\\\?\\")


if __name__ == "__main__":
    pytest.main([__file__])
