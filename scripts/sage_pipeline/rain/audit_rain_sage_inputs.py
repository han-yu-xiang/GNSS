#!/usr/bin/env python3
"""Read-only audit for the rerun Rain GNSS-SDR inputs.

The audit reads configuration text and 32-byte telemetry records only.  It
never opens a raw IQ .bin file.  Tracking MAT internal variables are reported
as deferred to the normal-user MATLAB preflight.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import struct
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PROJECT_ROOT = Path(r"E:\GNSS_Multipath_Project")
DEFAULT_OUTPUT_DIR = DEFAULT_PROJECT_ROOT / "dataset_generation_logs" / "darkroom_channel_emulation"
SCENES = ("F1023_clear", "F1023_midrain", "F1023_heavyrain")
TELEMETRY_RECORD = struct.Struct("<dQdii")
SUPPORTED_SAMPLE_RATE_HZ = 10_230_000


def parse_conf(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rate = re.search(r"(?m)^\s*SignalSource\.sampling_frequency\s*=\s*([0-9]+)", text)
    filename = re.search(r"(?m)^\s*SignalSource\.filename\s*=\s*(.*?)\s*$", text)
    return {
        "sampling_frequency_hz": int(rate.group(1)) if rate else None,
        "configured_raw_path": filename.group(1).strip() if filename else None,
        "item_type_ishort": "SignalSource.item_type=ishort" in text,
        "gps_l1_ca_tracking": "GPS_L1_CA_DLL_PLL_Tracking" in text,
        "telemetry_dump_enabled": "TelemetryDecoder_1C.dump=true" in text,
        "observables_dump_enabled": "Observables.dump=true" in text,
        "pvt_output_enabled": "PVT.output_enabled=true" in text,
        "nmea_output_enabled": "PVT.nmea_output_file_enabled=true" in text,
        "rinex_output_enabled": "PVT.rinex_output_enabled=true" in text,
        "xml_output_enabled": "PVT.xml_output_enabled=true" in text,
    }


def parse_telemetry(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    size = TELEMETRY_RECORD.size
    remainder = len(data) % size
    rows = [
        TELEMETRY_RECORD.unpack_from(data, offset)
        for offset in range(0, len(data) - remainder, size)
    ]
    valid = [row for row in rows if row[4] > 0 and row[3] in (-1, 1)]
    prns = sorted({row[4] for row in valid})
    tow = [row[0] for row in valid]
    samples = [row[1] for row in valid]
    tow_steps = [b - a for a, b in zip(tow, tow[1:])]
    sample_steps = [b - a for a, b in zip(samples, samples[1:])]
    tow_valid = sum(abs(step - 0.02) <= 2e-6 for step in tow_steps)
    sample_valid = sum(abs(step - 204_600) <= 2 for step in sample_steps)
    return {
        "file_size_bytes": len(data),
        "record_bytes": size,
        "record_count": len(rows),
        "remainder_bytes": remainder,
        "valid_nav_symbol_count": len(valid),
        "prns": [f"G{prn:02d}" for prn in prns],
        "tow_start_s": tow[0] if tow else None,
        "tow_end_s": tow[-1] if tow else None,
        "tow_span_s": tow[-1] - tow[0] if len(tow) >= 2 else None,
        "tow_step_count": len(tow_steps),
        "tow_step_valid_count": tow_valid,
        "sample_step_count": len(sample_steps),
        "sample_step_valid_count": sample_valid,
        "continuity_pass": bool(
            rows
            and remainder == 0
            and len(valid) == len(rows)
            and (not tow_steps or tow_valid == len(tow_steps))
            and (not sample_steps or sample_valid == len(sample_steps))
        ),
        "valid": bool(rows and remainder == 0 and valid and len(prns) == 1),
    }


def file_info(path: Path | None) -> dict[str, Any]:
    exists = bool(path and path.is_file())
    return {
        "path": str(path) if path else None,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists and path else None,
        "nonempty": bool(exists and path and path.stat().st_size > 0),
    }


def channel_from_name(path: Path) -> int | None:
    match = re.search(r"_telemetry_ch_(\d+)\.dat$", path.name)
    return int(match.group(1)) if match else None


def audit_scene(project_root: Path, scene_id: str) -> dict[str, Any]:
    rain_dir = project_root / "rain" / scene_id
    conf_files = sorted(rain_dir.glob("*.conf"))
    raw_files = sorted(rain_dir.glob("*.bin"))
    conf = parse_conf(conf_files[0]) if len(conf_files) == 1 else {}
    raw = raw_files[0] if len(raw_files) == 1 else None
    channels: list[dict[str, Any]] = []
    telemetry_dir = rain_dir / "results" / "telemetry"
    tracking_dir = rain_dir / "results" / "tracking"
    for telemetry_path in sorted(telemetry_dir.glob("*_telemetry_ch_*.dat")):
        channel = channel_from_name(telemetry_path)
        if channel is None or telemetry_path.stat().st_size == 0:
            continue
        telemetry = parse_telemetry(telemetry_path)
        if not telemetry["valid"]:
            continue
        prns = telemetry["prns"]
        if len(prns) != 1:
            continue
        tracking_dat = tracking_dir / f"{scene_id}_track_ch_{channel}.dat"
        tracking_mat = tracking_dir / f"{scene_id}_track_ch_{channel}.mat"
        telemetry_mat = telemetry_dir / f"{scene_id}_telemetry_ch_{channel}.mat"
        channels.append(
            {
                "tracking_channel": channel,
                "prn": prns[0],
                "telemetry": telemetry,
                "tracking_dat": file_info(tracking_dat),
                "tracking_mat": file_info(tracking_mat),
                "telemetry_dat": file_info(telemetry_path),
                "telemetry_mat": file_info(telemetry_mat),
                "tracking_mat_schema_status": (
                    "present_nonempty_schema_deferred_to_matlab_preflight"
                    if tracking_mat.is_file() and tracking_mat.stat().st_size > 0
                    else "missing_or_empty"
                ),
            }
        )
    xml = rain_dir / "results" / "navigation" / "gps_ephemeris.xml"
    result: dict[str, Any] = {
        "scene_id": scene_id,
        "weather_condition": scene_id.removeprefix("F1023_"),
        "source_rerun_id": "20260817_gnss_sdr_rerun",
        "raw": file_info(raw),
        "configuration": {
            **conf,
            "path": str(conf_files[0]) if len(conf_files) == 1 else None,
        },
        "navigation_xml": file_info(xml),
        "nmea_available": False,
        "pvt_available": False,
        "trajectory_available": False,
        "geometry_available": False,
        "elevation_conditioning": False,
        "channels": channels,
    }
    reasons: list[str] = []
    if not result["raw"]["nonempty"]:
        reasons.append("raw_missing_or_empty")
    if result["configuration"].get("sampling_frequency_hz") != SUPPORTED_SAMPLE_RATE_HZ:
        reasons.append("sample_rate_not_10230000")
    if not channels:
        reasons.append("no_valid_telemetry_channel")
    for channel_data in channels:
        channel = channel_data["tracking_channel"]
        if not channel_data["tracking_dat"]["nonempty"]:
            reasons.append(f"tracking_dat_missing_or_empty_ch{channel}")
        if not channel_data["tracking_mat"]["nonempty"]:
            reasons.append(f"tracking_mat_missing_or_empty_ch{channel}")
        if not channel_data["telemetry"]["continuity_pass"]:
            reasons.append(f"telemetry_continuity_failed_ch{channel}")
    result["rain_sage_input_ready"] = not reasons
    result["rain_sage_static_reasons"] = reasons
    result["execution_ready"] = False
    result["execution_gate_note"] = (
        "Static gate only; MATLAB must load the tracking MAT before any "
        "Commander-approved SAGE request."
    )
    return result


def build_audit(project_root: Path) -> dict[str, Any]:
    scenes = [audit_scene(project_root, scene_id) for scene_id in SCENES]
    prn_sets = {
        scene["weather_condition"]: sorted({item["prn"] for item in scene["channels"]})
        for scene in scenes
    }
    intersection = sorted(
        set(prn_sets["clear"])
        & set(prn_sets["midrain"])
        & set(prn_sets["heavyrain"])
    )
    pair_candidates = sorted(set(prn_sets["clear"]) & set(prn_sets["midrain"]))
    return {
        "audit_version": "rain-sage-input-audit-1.0",
        "source_rerun_id": "20260817_gnss_sdr_rerun",
        "sample_rate_required_hz": SUPPORTED_SAMPLE_RATE_HZ,
        "rain_mvp_policy": {
            "nmea_required": False,
            "pvt_required": False,
            "rinex_required": False,
            "trajectory_required": False,
            "geometry_required": False,
            "elevation_conditioning": False,
            "common_prn_required_for_sage": False,
            "common_prn_preferred_for_matched_validation": True,
        },
        "scenes": scenes,
        "prn_sets": prn_sets,
        "intersection_all_three": intersection,
        "matched_pair_candidates": pair_candidates,
        "raw_iq_samples_opened": False,
        "sage_executed": False,
        "matlab_executed": False,
    }


def write_outputs(audit: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rain_sage_input_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rows: list[dict[str, Any]] = []
    for scene in audit["scenes"]:
        for channel in scene["channels"]:
            rows.append(
                {
                    "source_rerun_id": audit["source_rerun_id"],
                    "scene_id": scene["scene_id"],
                    "weather_condition": scene["weather_condition"],
                    "PRN": channel["prn"],
                    "tracking_channel": channel["tracking_channel"],
                    "sample_rate_hz": scene["configuration"].get(
                        "sampling_frequency_hz"
                    ),
                    "raw_exists": scene["raw"]["nonempty"],
                    "tracking_dat_exists": channel["tracking_dat"]["nonempty"],
                    "tracking_mat_exists": channel["tracking_mat"]["nonempty"],
                    "telemetry_valid": channel["telemetry"]["valid"],
                    "telemetry_records": channel["telemetry"]["record_count"],
                    "valid_nav_symbols": channel["telemetry"][
                        "valid_nav_symbol_count"
                    ],
                    "nmea_available": scene["nmea_available"],
                    "pvt_available": scene["pvt_available"],
                    "geometry_available": scene["geometry_available"],
                    "rain_sage_input_ready": scene["rain_sage_input_ready"],
                    "execution_ready": scene["execution_ready"],
                    "notes": scene["execution_gate_note"],
                }
            )
    if rows:
        with (output_dir / "rain_sage_input_audit.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(list(argv) if argv is not None else None)
    audit = build_audit(args.project_root)
    write_outputs(audit, args.output_dir)
    print(
        json.dumps(
            {
                "scenes": len(audit["scenes"]),
                "intersection_all_three": audit["intersection_all_three"],
                "matched_pair_candidates": audit["matched_pair_candidates"],
                "ready_channel_count": sum(
                    len(scene["channels"])
                    for scene in audit["scenes"]
                    if scene["rain_sage_input_ready"]
                ),
                "raw_iq_samples_opened": audit["raw_iq_samples_opened"],
                "output_dir": str(args.output_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

