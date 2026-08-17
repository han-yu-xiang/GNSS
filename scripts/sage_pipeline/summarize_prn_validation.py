#!/usr/bin/env python3
"""Summarize existing reference-scene PRN SAGE validation results.

This tool is read-only with respect to all SAGE result directories.  It reads
the existing CSV products and dataset inventory, then creates two summary
files in the reference scene's ``sage_results`` directory.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REFERENCE_SCENE = "F1023_V70_D0117_P2"
PRN_RESULT_DIRS = {
    "G06": Path("G06_nav_sage_v1"),
    "G11": Path("nav_sage_v2/G11"),
    "G25": Path("nav_sage_v2/G25"),
    "G28": Path("nav_sage_v2/G28"),
}

SUMMARY_FIELDS = [
    "prn",
    "tracking_channel",
    "stage0_nav_symbols",
    "stage0_40ms_windows",
    "stage1_scanned_windows",
    "stage1_candidate_windows",
    "stage2_L1_selected",
    "stage2_L2_selected",
    "stage2_L3_selected",
    "stage2_L4_selected",
    "stage2_L_ge_2",
    "stage2_L_ge_3",
    "stage3_reliable_events",
    "stage4_joint_results",
    "stage4_confirmed_multipath_events",
    "confirmed_mp_window_ids",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(r"E:\GNSS_Multipath_Project"),
        help="GNSS_Multipath_Project root directory",
    )
    parser.add_argument(
        "--scene-id",
        default=REFERENCE_SCENE,
        help="Reference scene ID to summarize",
    )
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required result file is missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def is_true(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def as_int(value: Any) -> int:
    return int(float(str(value)))


def format_number(value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.6g}"


def load_channel_map(inventory_path: Path, scene_id: str) -> dict[str, int]:
    rows = read_csv_rows(inventory_path)
    matches = [row for row in rows if row.get("scene_id") == scene_id]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one inventory row for {scene_id}, found {len(matches)}"
        )
    raw_map = json.loads(matches[0]["prn_tracking_channel_map"])
    channel_map: dict[str, int] = {}
    for prn, candidates in raw_map.items():
        if len(candidates) != 1:
            raise ValueError(
                f"Expected one tracking channel for {scene_id}/{prn}, "
                f"found {candidates}"
            )
        channel_map[prn] = int(candidates[0])
    return channel_map


def summarize_prn(
    prn: str, result_dir: Path, tracking_channel: int
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    stage0_symbols = read_csv_rows(result_dir / "stage0_valid_symbols.csv")
    stage0_windows = read_csv_rows(result_dir / "stage0_valid_40ms_windows.csv")
    stage1 = read_csv_rows(result_dir / "stage1_nav_fast_scan.csv")
    stage2 = read_csv_rows(result_dir / "stage2_selected_windows.csv")
    stage3 = read_csv_rows(result_dir / "stage3_reliable_centers.csv")
    stage4 = read_csv_rows(result_dir / "stage4_joint_summary.csv")
    stage4_paths = read_csv_rows(result_dir / "stage4_joint_paths.csv")

    selected_counts = {
        order: sum(as_int(row["selected_L"]) == order for row in stage2)
        for order in range(1, 5)
    }
    confirmed = [
        row
        for row in stage4
        if is_true(row.get("joint_valid", "0"))
        and as_int(row.get("joint_multipath_count", "0")) > 0
    ]
    confirmed_ids = {as_int(row["center_window_id"]) for row in confirmed}
    confirmed_paths = [
        row
        for row in stage4_paths
        if as_int(row["center_window_id"]) in confirmed_ids
        and is_true(row.get("is_multipath", "0"))
    ]

    for event in confirmed:
        event["prn"] = prn
        event["tracking_channel"] = str(tracking_channel)
    for path in confirmed_paths:
        path["prn"] = prn

    summary = {
        "prn": prn,
        "tracking_channel": tracking_channel,
        "stage0_nav_symbols": len(stage0_symbols),
        "stage0_40ms_windows": len(stage0_windows),
        "stage1_scanned_windows": len(stage1),
        "stage1_candidate_windows": len(stage2),
        "stage2_L1_selected": selected_counts[1],
        "stage2_L2_selected": selected_counts[2],
        "stage2_L3_selected": selected_counts[3],
        "stage2_L4_selected": selected_counts[4],
        "stage2_L_ge_2": sum(selected_counts[order] for order in range(2, 5)),
        "stage2_L_ge_3": sum(selected_counts[order] for order in range(3, 5)),
        "stage3_reliable_events": len(stage3),
        "stage4_joint_results": len(stage4),
        "stage4_confirmed_multipath_events": len(confirmed),
        "confirmed_mp_window_ids": ";".join(
            str(window_id) for window_id in sorted(confirmed_ids)
        ),
    }
    return summary, confirmed, confirmed_paths


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(str(value) for value in row) + " |" for row in rows
    )
    return lines


def write_report(
    report_path: Path,
    scene_id: str,
    summaries: list[dict[str, Any]],
    events: list[dict[str, str]],
    paths: list[dict[str, str]],
) -> None:
    lines = [
        "# Reference Scene PRN Validation Report",
        "",
        f"- Scene: `{scene_id}`",
        f"- Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`",
        "- Source: existing Stage0–Stage4 CSV results only; no SAGE processing was run.",
        "",
        "## PRN summary",
        "",
    ]
    lines.extend(
        markdown_table(
            [
                "PRN",
                "Channel",
                "NAV symbols",
                "40 ms windows",
                "Stage1 scanned",
                "Stage1 candidates",
                "L1",
                "L2",
                "L3",
                "L4",
                "L>=2",
                "L>=3",
                "Stage3 reliable",
                "Stage4 joint",
                "Confirmed MP",
                "Confirmed windows",
            ],
            [
                [
                    row["prn"],
                    row["tracking_channel"],
                    row["stage0_nav_symbols"],
                    row["stage0_40ms_windows"],
                    row["stage1_scanned_windows"],
                    row["stage1_candidate_windows"],
                    row["stage2_L1_selected"],
                    row["stage2_L2_selected"],
                    row["stage2_L3_selected"],
                    row["stage2_L4_selected"],
                    row["stage2_L_ge_2"],
                    row["stage2_L_ge_3"],
                    row["stage3_reliable_events"],
                    row["stage4_joint_results"],
                    row["stage4_confirmed_multipath_events"],
                    row["confirmed_mp_window_ids"] or "—",
                ]
                for row in summaries
            ],
        )
    )
    lines.extend(["", "## Confirmed multipath events", ""])
    lines.extend(
        markdown_table(
            [
                "PRN",
                "Channel",
                "Window",
                "Time (s)",
                "Stage2 L",
                "Joint L",
                "MP paths",
                "Min MP power (dB)",
                "Max relative Doppler (Hz)",
                "Max coherence",
            ],
            [
                [
                    event["prn"],
                    event["tracking_channel"],
                    event["center_window_id"],
                    format_number(event["recording_time_s"]),
                    event["stage2_L"],
                    event["joint_selected_L"],
                    event["joint_multipath_count"],
                    format_number(event["minimum_multipath_power_db"]),
                    format_number(event["maximum_relative_doppler_hz"]),
                    format_number(event["maximum_coherence"]),
                ]
                for event in events
            ],
        )
    )
    lines.extend(["", "## Confirmed multipath paths", ""])
    lines.extend(
        markdown_table(
            [
                "PRN",
                "Window",
                "Path",
                "Excess delay (samples)",
                "Excess delay (chips)",
                "Doppler offset (Hz)",
                "Relative power (dB)",
            ],
            [
                [
                    path["prn"],
                    path["center_window_id"],
                    path["path_id"],
                    format_number(path["excess_delay_samples"]),
                    format_number(path["excess_delay_chips"]),
                    format_number(path["doppler_offset_hz"]),
                    format_number(path["mean_relative_power_db"]),
                ]
                for path in paths
            ],
        )
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    scene_id = args.scene_id
    sage_root = project_root / "scenes" / scene_id / "sage_results"
    inventory_path = project_root / "dataset" / "dataset_inventory.csv"
    if not sage_root.is_dir():
        raise FileNotFoundError(f"SAGE result root is missing: {sage_root}")

    summary_path = sage_root / "prn_validation_summary.csv"
    report_path = sage_root / "prn_validation_report.md"
    for output in (summary_path, report_path):
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite existing summary: {output}")

    channel_map = load_channel_map(inventory_path, scene_id)
    summaries: list[dict[str, Any]] = []
    events: list[dict[str, str]] = []
    paths: list[dict[str, str]] = []
    for prn, relative_dir in PRN_RESULT_DIRS.items():
        if prn not in channel_map:
            raise KeyError(f"Inventory has no tracking channel for {scene_id}/{prn}")
        summary, prn_events, prn_paths = summarize_prn(
            prn, sage_root / relative_dir, channel_map[prn]
        )
        summaries.append(summary)
        events.extend(prn_events)
        paths.extend(prn_paths)

    with summary_path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summaries)
    write_report(report_path, scene_id, summaries, events, paths)

    print(f"Summary: {summary_path}")
    print(f"Report : {report_path}")
    print(f"PRNs   : {len(summaries)}")
    print(f"Confirmed multipath events: {len(events)}")
    print(f"Confirmed multipath paths : {len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
