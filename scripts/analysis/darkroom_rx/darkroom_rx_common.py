"""Shared contracts for the 0913 darkroom receiver GNSS-SDR workflow."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping


SAMPLE_RATE_HZ = 10_230_000
ITEM_TYPE = "ishort"
BYTES_PER_COMPLEX_SAMPLE = 4
WSL_DISTRO = "Ubuntu-22.04"
GNSS_SDR_EXECUTABLE = "/usr/bin/gnss-sdr"
GNSS_SDR_VERSION = "0.0.16"
SCHEMA_VERSION = "darkroom-rx-gnss-sdr-batch-v1"

EXPECTED_FILENAMES: tuple[str, ...] = (
    "highway_open_good_1023.bin",
    "highway_open_pool_1023.bin",
    "highway_rain_1023.bin",
    "mountain_open_good_1023.bin",
    "mountain_open_pool_1023.bin",
    "mountain_rain_1023.bin",
    "urban_open_good_1023.bin",
    "urban_open_pool_1023.bin",
)

_FILENAME_MAP: Mapping[str, tuple[str, str, str, str]] = {
    "highway_open_good_1023.bin": (
        "highway_open_good_1023",
        "Highway/Open",
        "GOOD",
        "open_good",
    ),
    "highway_open_pool_1023.bin": (
        "highway_open_poor_1023",
        "Highway/Open",
        "POOR",
        "open_pool",
    ),
    "highway_rain_1023.bin": (
        "highway_rain_1023",
        "Highway/Open",
        "RAIN",
        "rain",
    ),
    "mountain_open_good_1023.bin": (
        "mountain_valley_good_1023",
        "Mountain/Valley",
        "GOOD",
        "open_good",
    ),
    "mountain_open_pool_1023.bin": (
        "mountain_valley_poor_1023",
        "Mountain/Valley",
        "POOR",
        "open_pool",
    ),
    "mountain_rain_1023.bin": (
        "mountain_valley_rain_1023",
        "Mountain/Valley",
        "RAIN",
        "rain",
    ),
    "urban_open_good_1023.bin": (
        "urban_good_1023",
        "Urban",
        "GOOD",
        "open_good",
    ),
    "urban_open_pool_1023.bin": (
        "urban_poor_1023",
        "Urban",
        "POOR",
        "open_pool",
    ),
}


@dataclass(frozen=True)
class DarkroomRxTask:
    task_id: str
    environment_class: str
    condition: str
    source_condition_token: str
    source_path: Path
    sample_rate_hz: int = SAMPLE_RATE_HZ
    item_type: str = ITEM_TYPE
    iq_layout: str = "interleaved_signed_int16_iq_little_endian"


def parse_task_filename(path: Path) -> DarkroomRxTask:
    """Map one manually confirmed source filename to its frozen task identity."""

    key = path.name.lower()
    if key not in _FILENAME_MAP:
        raise ValueError(f"unsupported 0913DarkroomRx filename: {path.name}")
    task_id, environment, condition, source_token = _FILENAME_MAP[key]
    return DarkroomRxTask(
        task_id=task_id,
        environment_class=environment,
        condition=condition,
        source_condition_token=source_token,
        source_path=path,
    )


def with_resolved_source(task: DarkroomRxTask) -> DarkroomRxTask:
    return replace(task, source_path=task.source_path.resolve())


def windows_to_wsl_path(path: Path) -> str:
    """Convert one absolute drive-letter Windows path to WSL /mnt form."""

    text = str(path)
    match = re.fullmatch(r"([A-Za-z]):[\\/](.*)", text)
    if not match:
        raise ValueError(f"expected absolute Windows path, got: {text}")
    drive = match.group(1).lower()
    tail = match.group(2).replace("\\", "/").lstrip("/")
    return f"/mnt/{drive}/{tail}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def estimated_duration_s(size_bytes: int) -> float:
    if size_bytes <= 0 or size_bytes % BYTES_PER_COMPLEX_SAMPLE:
        raise ValueError("raw IQ size must be positive and divisible by four")
    return size_bytes / float(BYTES_PER_COMPLEX_SAMPLE * SAMPLE_RATE_HZ)


def render_gnss_sdr_config(
    *,
    task: DarkroomRxTask,
    input_wsl_path: str,
    output_wsl_root: str,
) -> str:
    """Render the frozen GPS L1 C/A receiver settings with task-local outputs."""

    if not input_wsl_path.startswith("/mnt/") or not output_wsl_root.startswith("/mnt/"):
        raise ValueError("GNSS-SDR paths must be absolute WSL /mnt paths")
    token = task.task_id
    root = output_wsl_root.rstrip("/")
    return f"""; 0913 DarkroomRx GNSS-SDR positioning/lock diagnostic
; Generated configuration.  Source is interleaved signed int16 little-endian I/Q.
; task_id={token}

[GNSS-SDR]
GNSS-SDR.internal_fs_sps=10230000
GNSS-SDR.observable_interval_ms=20
GNSS-SDR.tow_to_trk=true
GNSS-SDR.pre_2009_file=false

SignalSource.implementation=File_Signal_Source
SignalSource.filename={input_wsl_path}
SignalSource.item_type=ishort
SignalSource.sampling_frequency=10230000
SignalSource.samples=0
SignalSource.repeat=false
SignalSource.enable_throttle_control=false

SignalConditioner.implementation=Signal_Conditioner
DataTypeAdapter.implementation=Ishort_To_Complex
InputFilter.implementation=Pass_Through
InputFilter.item_type=gr_complex
Resampler.implementation=Pass_Through
Resampler.item_type=gr_complex

Channels_1C.count=12
Channels.in_acquisition=12
Channel.signal=1C

Acquisition_1C.implementation=GPS_L1_CA_PCPS_Acquisition
Acquisition_1C.item_type=gr_complex
Acquisition_1C.pfa=0.01
Acquisition_1C.doppler_max=10000
Acquisition_1C.doppler_step=250
Acquisition_1C.blocking=true

Tracking_1C.implementation=GPS_L1_CA_DLL_PLL_Tracking
Tracking_1C.item_type=gr_complex
Tracking_1C.extend_correlation_symbols=1
Tracking_1C.pll_bw_hz=40.0
Tracking_1C.dll_bw_hz=4.0
Tracking_1C.early_late_space_chips=0.5
Tracking_1C.carrier_aiding=true
Tracking_1C.enable_fll_pull_in=true
Tracking_1C.enable_fll_steady_state=false
Tracking_1C.fll_bw_hz=15.0
Tracking_1C.pull_in_time_s=5
Tracking_1C.dump=true
Tracking_1C.dump_filename={root}/tracking/{token}_track_ch_
Tracking_1C.dump_mat=true

TelemetryDecoder_1C.implementation=GPS_L1_CA_Telemetry_Decoder
TelemetryDecoder_1C.dump=true
TelemetryDecoder_1C.dump_filename={root}/telemetry/{token}_telemetry_ch_
TelemetryDecoder_1C.dump_mat=true
TelemetryDecoder_1C.remove_dat=false
TelemetryDecoder_1C.dump_crc_stats=true
TelemetryDecoder_1C.dump_crc_stats_filename={root}/telemetry/{token}_crc_stats

Observables.implementation=Hybrid_Observables
Observables.enable_carrier_smoothing=false
Observables.dump=true
Observables.dump_filename={root}/observables/{token}_observables.dat
Observables.dump_mat=true

PVT.implementation=RTKLIB_PVT
PVT.positioning_mode=Single
PVT.output_rate_ms=1000
PVT.display_rate_ms=1000
PVT.iono_model=Broadcast
PVT.trop_model=Saastamoinen
PVT.flag_rtcm_server=false
PVT.flag_rtcm_tty_port=false
PVT.output_enabled=true
PVT.rtcm_output_file_enabled=false
PVT.rinex_output_enabled=true
PVT.rinex_version=3
PVT.rinex_name=RINEXFILE
PVT.rinexobs_rate_ms=1000
PVT.rinex_output_path={root}/rinex
PVT.nmea_output_file_enabled=true
PVT.nmea_rate_ms=1000
PVT.nmea_output_file_path={root}/nmea
PVT.nmea_dump_filename={token}_trajectory.nmea
PVT.gpx_output_enabled=true
PVT.gpx_rate_ms=1000
PVT.gpx_output_path={root}/trajectory
PVT.geojson_output_enabled=true
PVT.geojson_rate_ms=1000
PVT.geojson_output_path={root}/trajectory
PVT.kml_output_enabled=true
PVT.kml_rate_ms=1000
PVT.kml_output_path={root}/trajectory
PVT.xml_output_enabled=true
PVT.xml_output_path={root}/navigation
PVT.dump=true
PVT.dump_filename={root}/pvt/{token}_pvt.dat
PVT.dump_mat=true
"""
