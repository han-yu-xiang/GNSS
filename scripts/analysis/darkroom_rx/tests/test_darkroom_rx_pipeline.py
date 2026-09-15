from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.analysis.darkroom_rx.audit_darkroom_rx_signal_quality import (
    audit_tracking_file,
    classify_positionability,
    extract_debounced_lock_events,
    parse_nmea_lines,
)
from scripts.analysis.darkroom_rx.audit_darkroom_rx_signal_quality_v2 import (
    decode_numeric_mat_vector,
    parse_nmea_lines_with_output_gaps,
    parse_tracking_channel,
)
from scripts.analysis.darkroom_rx.darkroom_rx_common import (
    EXPECTED_FILENAMES,
    parse_task_filename,
    render_gnss_sdr_config,
    windows_to_wsl_path,
)
from scripts.analysis.darkroom_rx.prepare_darkroom_rx_gnss_sdr_batch import (
    discover_input_tasks,
    prepare_batch,
)
from scripts.analysis.darkroom_rx.run_darkroom_rx_gnss_sdr_batch import (
    build_wsl_command,
    load_and_validate_manifest,
    main as runner_main,
    select_tasks,
    validate_task_preflight,
)


def _make_eight_inputs(root: Path) -> None:
    root.mkdir()
    for index, name in enumerate(EXPECTED_FILENAMES, start=1):
        # Four int16 values: two deterministic complex samples.
        (root / name).write_bytes(bytes([index]) * 8)


def test_filename_mapping_is_frozen_and_pool_means_poor() -> None:
    task = parse_task_filename(Path("highway_open_pool_1023.bin"))

    assert task.task_id == "highway_open_poor_1023"
    assert task.environment_class == "Highway/Open"
    assert task.condition == "POOR"
    assert task.source_condition_token == "open_pool"
    assert task.sample_rate_hz == 10_230_000
    assert task.item_type == "ishort"


def test_filename_mapping_rejects_unapproved_input() -> None:
    with pytest.raises(ValueError, match="unsupported 0913DarkroomRx filename"):
        parse_task_filename(Path("urban_mystery_1023.bin"))


def test_windows_to_wsl_path_maps_drive_and_rejects_relative() -> None:
    assert windows_to_wsl_path(Path(r"E:\0913DarkroomRx\urban_open_good_1023.bin")) == (
        "/mnt/e/0913DarkroomRx/urban_open_good_1023.bin"
    )
    with pytest.raises(ValueError, match="absolute Windows path"):
        windows_to_wsl_path(Path("relative.bin"))


def test_rendered_config_freezes_format_and_position_outputs() -> None:
    task = parse_task_filename(Path("urban_open_good_1023.bin"))
    text = render_gnss_sdr_config(
        task=task,
        input_wsl_path="/mnt/e/0913DarkroomRx/urban_open_good_1023.bin",
        output_wsl_root="/mnt/e/GNSS_Multipath_Project/dataset_generation_logs/"
        "darkroom_rx_gnss_sdr/request/runs/urban_open_good_1023",
    )

    assert "SignalSource.item_type=ishort" in text
    assert "SignalSource.sampling_frequency=10230000" in text
    assert "DataTypeAdapter.implementation=Ishort_To_Complex" in text
    assert "Channels_1C.count=12" in text
    assert "PVT.positioning_mode=Single" in text
    assert "PVT.output_enabled=true" in text
    assert "PVT.nmea_output_file_enabled=true" in text
    assert "PVT.dump=true" in text
    assert "/mnt/e/rain/" not in text
    assert "PVT.output_enabled=false" not in text


def test_discovery_requires_exact_eight_file_contract(tmp_path: Path) -> None:
    input_dir = tmp_path / "inputs"
    _make_eight_inputs(input_dir)

    tasks = discover_input_tasks(input_dir)

    assert len(tasks) == 8
    assert [task.source_path.name for task in tasks] == list(EXPECTED_FILENAMES)
    assert sum(task.condition == "POOR" for task in tasks) == 3


def test_discovery_rejects_missing_input(tmp_path: Path) -> None:
    input_dir = tmp_path / "inputs"
    _make_eight_inputs(input_dir)
    (input_dir / EXPECTED_FILENAMES[-1]).rename(input_dir / "held_back.bin")

    with pytest.raises(ValueError, match="input inventory mismatch"):
        discover_input_tasks(input_dir)


def test_prepare_batch_is_immutable_new_only(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    input_dir = tmp_path / "inputs"
    _make_eight_inputs(input_dir)
    request_dir = (
        project_root
        / "dataset_generation_logs"
        / "darkroom_rx_gnss_sdr"
        / "darkroom_rx_0913_test"
    )

    manifest_path, digest = prepare_batch(
        project_root=project_root,
        input_dir=input_dir,
        request_dir=request_dir,
        request_id="darkroom_rx_0913_test",
        source_files={},
    )

    assert manifest_path.is_file()
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == digest
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["new_only"] is True
    assert payload["resume_allowed"] is False
    assert payload["max_parallel_gnss_sdr"] == 1
    assert payload["task_count"] == 8
    assert all(row["raw_sha256"] for row in payload["tasks"])
    assert all(not Path(row["output_windows_path"]).exists() for row in payload["tasks"])
    assert len(list((request_dir / "configs").glob("*.conf"))) == 8

    with pytest.raises(FileExistsError, match="already exists"):
        prepare_batch(
            project_root=project_root,
            input_dir=input_dir,
            request_dir=request_dir,
            request_id="darkroom_rx_0913_test",
            source_files={},
        )


def test_manifest_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text('{"schema_version":"darkroom-rx-gnss-sdr-batch-v1"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_and_validate_manifest(path, "0" * 64)


def test_prepared_manifest_passes_validation_only_without_wsl(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    input_dir = tmp_path / "inputs"
    _make_eight_inputs(input_dir)
    request_id = "validation_only_request"
    request_dir = (
        project_root / "dataset_generation_logs" / "darkroom_rx_gnss_sdr" / request_id
    )
    manifest_path, digest = prepare_batch(
        project_root=project_root,
        input_dir=input_dir,
        request_dir=request_dir,
        request_id=request_id,
        source_files={},
    )

    assert runner_main(
        [
            "--manifest",
            str(manifest_path),
            "--expected-manifest-sha256",
            digest,
            "--task-id",
            "urban_good_1023",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "PREFLIGHT=PASS" in output
    assert "VALIDATION_ONLY=true" in output
    assert "GNSS_SDR_INVOKED=false" in output


def test_task_selection_and_wsl_command_are_deterministic() -> None:
    tasks = [
        {"task_id": "a", "config_wsl_path": "/mnt/e/project/a.conf", "output_wsl_path": "/mnt/e/project/a"},
        {"task_id": "b", "config_wsl_path": "/mnt/e/project/b.conf", "output_wsl_path": "/mnt/e/project/b"},
    ]

    assert [row["task_id"] for row in select_tasks(tasks, ["b"])] == ["b"]
    command = build_wsl_command(tasks[1], distro="Ubuntu-22.04", executable="/usr/bin/gnss-sdr")
    assert command[:5] == ["wsl.exe", "-d", "Ubuntu-22.04", "--", "bash"]
    assert "/usr/bin/gnss-sdr" in command[-1]
    assert "--config_file=/mnt/e/project/b.conf" in command[-1]


def test_task_preflight_rejects_existing_output(tmp_path: Path) -> None:
    raw = tmp_path / "raw.bin"
    raw.write_bytes(b"1234")
    config = tmp_path / "task.conf"
    config.write_text("config", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    row = {
        "task_id": "task",
        "raw_windows_path": str(raw),
        "raw_size_bytes": raw.stat().st_size,
        "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        "config_windows_path": str(config),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "output_windows_path": str(output),
        "sample_rate_hz": 10_230_000,
        "item_type": "ishort",
        "new_only": True,
        "resume_allowed": False,
    }

    with pytest.raises(FileExistsError, match="new_only"):
        validate_task_preflight(row, verify_raw_hash=False)


def test_task_preflight_rejects_raw_hash_change(tmp_path: Path) -> None:
    raw = tmp_path / "raw.bin"
    raw.write_bytes(b"1234")
    config = tmp_path / "task.conf"
    config.write_text("config", encoding="utf-8")
    row = {
        "task_id": "task",
        "raw_windows_path": str(raw),
        "raw_size_bytes": 4,
        "raw_sha256": "0" * 64,
        "config_windows_path": str(config),
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "output_windows_path": str(tmp_path / "output"),
        "sample_rate_hz": 10_230_000,
        "item_type": "ishort",
        "new_only": True,
        "resume_allowed": False,
    }

    with pytest.raises(ValueError, match="raw IQ SHA-256 changed"):
        validate_task_preflight(row, verify_raw_hash=True)


def test_lock_event_uses_20ms_bad_and_100ms_good_debounce() -> None:
    times = np.arange(0.0, 0.200, 0.001)
    locks = np.ones(times.size)
    locks[20:45] = -1.0  # 25 ms bad interval

    events = extract_debounced_lock_events(times, locks)

    assert len(events) == 1
    assert events[0]["loss_start_s"] == pytest.approx(0.020)
    assert events[0]["loss_end_s"] == pytest.approx(0.045)
    assert events[0]["duration_ms"] == pytest.approx(25.0)
    assert events[0]["reacquired"] is True
    assert events[0]["right_censored"] is False


def test_short_bad_run_is_not_reported_as_lock_loss() -> None:
    times = np.arange(0.0, 0.150, 0.001)
    locks = np.ones(times.size)
    locks[20:35] = -1.0

    assert extract_debounced_lock_events(times, locks) == []


def test_lock_events_do_not_bridge_continuity_gap() -> None:
    times = np.concatenate((np.arange(0.0, 0.031, 0.001), np.arange(0.200, 0.351, 0.001)))
    locks = np.ones(times.size)
    locks[5:31] = -1.0

    events = extract_debounced_lock_events(times, locks)

    assert len(events) == 1
    assert events[0]["right_censored"] is True
    assert events[0]["reacquired"] is False
    assert events[0]["continuity_gap_bridged"] is False


def test_nmea_and_positionability_report_sustained_fix() -> None:
    lines = []
    for second in range(10):
        stamp = f"1200{second:02d}.00"
        lines.append(f"$GPGGA,{stamp},4835.0,N,00938.0,E,1,06,1.2,500.0,M,0.0,M,,")
        lines.append(f"$GPRMC,{stamp},A,4835.0,N,00938.0,E,0.0,0.0,130926,,,A")

    summary = parse_nmea_lines(lines)
    status = classify_positionability(summary, recording_duration_s=20.0)

    assert summary["valid_fix_epoch_count"] == 10
    assert summary["max_consecutive_fix_s"] == pytest.approx(10.0)
    assert summary["median_valid_sats"] == pytest.approx(6.0)
    assert status == "SUSTAINED_FIX"


def test_nmea_without_valid_solution_is_no_fix_observed() -> None:
    lines = [
        "$GPGGA,120000.00,,,,,0,00,99.9,,,,,,",
        "$GPRMC,120000.00,V,,,,,,,130926,,,N",
    ]
    summary = parse_nmea_lines(lines)

    assert summary["valid_fix_epoch_count"] == 0
    assert classify_positionability(summary, recording_duration_s=120.0) == "NO_FIX_OBSERVED"


def test_missing_position_output_is_inconclusive_not_no_fix() -> None:
    summary = parse_nmea_lines([])

    assert classify_positionability(summary, recording_duration_s=120.0) == (
        "INCONCLUSIVE_NO_POSITION_OUTPUT"
    )


def test_tracking_mat_audit_reports_prn_and_loss_duration(tmp_path: Path) -> None:
    from scipy.io import savemat

    count = 250
    samples = np.arange(count, dtype=np.float64) * 10_230.0
    lock = np.ones(count)
    lock[20:45] = -1.0
    path = tmp_path / "fixture_track_ch_7.mat"
    savemat(
        path,
        {
            "PRN": np.full(count, 11),
            "PRN_start_sample_count": samples,
            "CN0_SNV_dB_Hz": np.full(count, 38.0),
            "carrier_lock_test": lock,
            "carrier_doppler_hz": np.full(count, -1250.0),
        },
    )

    summaries, events = audit_tracking_file(
        path, task_id="fixture", sample_rate_hz=10_230_000
    )

    assert len(summaries) == 1
    assert summaries[0]["tracking_channel"] == 7
    assert summaries[0]["prn"] == "G11"
    assert summaries[0]["loss_event_count"] == 1
    assert summaries[0]["max_confirmed_loss_s"] == pytest.approx(0.025)
    assert len(events) == 1


def test_actual_gnss_sdr_tracking_suffix_maps_to_channel() -> None:
    path = Path("highway_open_good_1023_11.mat")

    assert parse_tracking_channel(path) == 11


def test_nmea_missing_expected_epoch_is_output_gap_not_explicit_no_fix() -> None:
    lines = [
        "$GPGGA,090000.00,4835.0,N,00938.0,E,1,06,1.2,500.0,M,0.0,M,,",
        "$GPGGA,090001.00,4835.0,N,00938.0,E,1,06,1.2,500.0,M,0.0,M,,",
        "$GPGGA,090003.00,4835.0,N,00938.0,E,1,06,1.2,500.0,M,0.0,M,,",
    ]

    summary = parse_nmea_lines_with_output_gaps(lines)

    assert summary["valid_fix_epoch_count"] == 3
    assert summary["explicit_no_fix_epoch_count"] == 0
    assert summary["inferred_missing_epoch_count"] == 1
    assert summary["position_output_gap_count"] == 1
    assert summary["max_position_output_gap_s"] == pytest.approx(1.0)
    assert summary["expected_position_epoch_count"] == 4
    assert summary["position_epoch_coverage_fraction"] == pytest.approx(0.75)
    assert summary["max_no_fix_interval_s"] == pytest.approx(0.0)


def test_matlab_hdf5_one_byte_void_values_decode_as_unsigned_counts() -> None:
    values = np.asarray([b"\x05", b"\x08"], dtype="V1")

    decoded = decode_numeric_mat_vector(values, label="valid_sats")

    assert decoded.dtype.kind in {"u", "f"}
    assert decoded.tolist() == [5, 8]
