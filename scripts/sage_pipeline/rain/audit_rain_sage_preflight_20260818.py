"""Static, no-raw-IQ preflight for the 2026-08-18 Rain SAGE queue.

This audit reads scene metadata, file metadata, tracking MAT headers, and the
32-byte telemetry DAT records needed to verify the channel/PRN mapping.  It
does not open raw IQ samples, invoke MATLAB, run SAGE, or overwrite an
existing preflight artifact.
"""

from __future__ import annotations

import csv
import json
import struct
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(r"E:\GNSS_Multipath_Project")
OUTPUT = PROJECT_ROOT / (
    "dataset_generation_logs/darkroom_channel_emulation/"
    "rain_sage_preflight_20260818.csv"
)

TASKS = (
    ("Clear", "F1023_clear", "G24", 10),
    ("Clear", "F1023_clear", "G29", 3),
    ("Clear", "F1023_clear", "G13", 8),
    ("Clear", "F1023_clear", "G12", 11),
    ("MidRain", "F1023_midrain", "G24", 8),
    ("MidRain", "F1023_midrain", "G20", 9),
    ("HeavyRain", "F1023_heavyrain", "G02", 1),
    ("HeavyRain", "F1023_heavyrain", "G31", 4),
    ("HeavyRain", "F1023_heavyrain", "G01", 7),
)

TELEMETRY_RECORD = struct.Struct("<dQdii")


def metadata(scene: str) -> dict:
    path = PROJECT_ROOT / "scenes" / scene / "metadata.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_ok(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def telemetry_summary(path: Path, expected_prn: int) -> dict:
    if not file_ok(path):
        return {"records": 0, "expected_records": 0, "nav_records": 0,
                "prns": [], "spacing_pass": False, "error": "missing"}
    size = path.stat().st_size
    if size % TELEMETRY_RECORD.size:
        return {"records": 0, "expected_records": 0, "nav_records": 0,
                "prns": [], "spacing_pass": False,
                "error": "size_not_multiple_of_32"}
    records = []
    with path.open("rb") as handle:
        for _ in range(size // TELEMETRY_RECORD.size):
            raw = handle.read(TELEMETRY_RECORD.size)
            if len(raw) != TELEMETRY_RECORD.size:
                return {"records": 0, "expected_records": 0,
                        "nav_records": 0, "prns": [],
                        "spacing_pass": False, "error": "short_record"}
            records.append(TELEMETRY_RECORD.unpack(raw))
    prns = sorted({row[4] for row in records})
    expected = [row for row in records if row[4] == expected_prn]
    nav = [row for row in expected if row[3] in (-1, 1)]
    spacing_pass = True
    if len(expected) > 1:
        for left, right in zip(expected, expected[1:]):
            if right[1] <= left[1] or right[0] <= left[0]:
                spacing_pass = False
                break
    return {
        "records": len(records),
        "expected_records": len(expected),
        "nav_records": len(nav),
        "prns": prns,
        "spacing_pass": spacing_pass,
        "error": "" if spacing_pass else "non_monotonic_expected_records",
    }


def task_row(weather: str, scene: str, prn_label: str, channel: int) -> dict:
    scene_dir = PROJECT_ROOT / "scenes" / scene
    output_dir = scene_dir / "sage_results" / "rain_sage_v1" / prn_label
    row = {
        "weather": weather,
        "scene": scene,
        "prn": prn_label,
        "channel": channel,
        "raw_ready": False,
        "tracking_ready": False,
        "telemetry_ready": False,
        "mapping_ready": False,
        "sample_rate_ready": False,
        "stage0_input_ready": False,
        "output_safe": not output_dir.exists(),
        "preflight_pass": "INPUT_BLOCKED",
        "reason": "",
        "raw_size_bytes": "",
        "tracking_mat_size_bytes": "",
        "telemetry_records": "",
        "valid_nav_symbol_records": "",
        "stage0_runtime_validation": "",
        "output_dir": str(output_dir),
    }
    try:
        data = metadata(scene)
        signal = data["signal"]
        raw_meta = data["raw_iq"]
        raw_path = Path(raw_meta["path"])
        raw_info_ok = raw_path.is_file() and raw_path.stat().st_size > 0
        row["raw_ready"] = raw_info_ok and (
            raw_path.stat().st_size == int(raw_meta["size_bytes"])
        )
        row["raw_size_bytes"] = raw_path.stat().st_size if raw_info_ok else ""
        row["sample_rate_ready"] = (
            int(signal["sample_rate_hz"]) == 10230000
            and signal["raw_format"] == "interleaved_int16_little_endian"
            and bool(signal["complex_iq"])
        )
        channel_entries = [
            item for item in data.get("tracking_channels", [])
            if int(item["tracking_channel"]) == channel
        ]
        mapping_metadata_ok = len(channel_entries) == 1 and (
            channel_entries[0]["prn"] == prn_label
        )
        if mapping_metadata_ok:
            entry = channel_entries[0]
            tracking_mat = scene_dir / entry["tracking_mat_path"]
            tracking_dat = scene_dir / entry["tracking_dat_path"]
            telemetry = scene_dir / entry["telemetry_dat_path"]
            tracking_ok = file_ok(tracking_mat) and file_ok(tracking_dat)
            row["tracking_ready"] = tracking_ok
            if tracking_ok:
                row["tracking_mat_size_bytes"] = tracking_mat.stat().st_size
            tele = telemetry_summary(telemetry, int(prn_label[1:]))
            row["telemetry_records"] = tele["records"]
            row["valid_nav_symbol_records"] = tele["nav_records"]
            row["telemetry_ready"] = (
                tele["records"] > 0 and tele["nav_records"] > 0
                and tele["spacing_pass"]
            )
            row["mapping_ready"] = (
                mapping_metadata_ok and tele["expected_records"] > 0
                and tele["nav_records"] == tele["expected_records"]
            )
            row["stage0_input_ready"] = tracking_ok and row["telemetry_ready"]
            row["stage0_runtime_validation"] = (
                "MATLAB field-load pending; static MAT/telemetry gate PASS"
                if row["stage0_input_ready"] else "static gate failed"
            )
        else:
            row["stage0_runtime_validation"] = "unique metadata mapping unavailable"
        failures = [
            name for name in (
                "raw_ready", "tracking_ready", "telemetry_ready",
                "mapping_ready", "sample_rate_ready", "stage0_input_ready",
                "output_safe",
            ) if not row[name]
        ]
        if not failures:
            row["preflight_pass"] = "PASS_STATIC_INPUT_GATE"
            row["reason"] = (
                "raw metadata/path, 10.23 MHz ishort-compatible input, mapped "
                "tracking/telemetry and static Stage0 gate pass; MATLAB field "
                "load remains an execution-time check"
            )
        else:
            row["reason"] = ";".join(failures)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        row["reason"] = f"preflight_exception:{type(exc).__name__}:{exc}"
    return row


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to overwrite existing preflight: {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    rows = [task_row(*task) for task in TASKS]
    fields = list(rows[0])
    with OUTPUT.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"PREVIEW_UTC={datetime.now(timezone.utc).isoformat()}")
    print(f"PREFLIGHT_OUTPUT={OUTPUT}")
    print(f"TASK_COUNT={len(rows)}")
    print(f"STATIC_PASS_COUNT={sum(row['preflight_pass'] == 'PASS_STATIC_INPUT_GATE' for row in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
