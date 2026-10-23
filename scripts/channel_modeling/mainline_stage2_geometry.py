"""Identity and time-index transforms for the Mainline Stage2 audit.

This module is deliberately limited to small tabular metadata.  It does not
open Stage2 scientific payloads, MATLAB files, or raw receiver samples.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Mapping, Sequence

from scripts.event_database.align_modeling_context import (
    GPS_WEEK_SECONDS,
    gps_tow_to_utc,
)


_CANONICAL_POSITIVE_INTEGER = re.compile(r"^[1-9][0-9]*$")


def _required_text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if value is None:
        raise ValueError(f"missing {field}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"missing {field}")
    return text


def _positive_canonical_id(row: Mapping[str, object], field: str) -> str:
    value = _required_text(row, field)
    if not _CANONICAL_POSITIVE_INTEGER.fullmatch(value):
        raise ValueError(f"invalid {field}: expected positive canonical decimal ID")
    return value


def _finite_number(row: Mapping[str, object], field: str) -> float:
    value = row.get(field)
    try:
        number = float(value) if value is not None and str(value).strip() else math.nan
    except (TypeError, ValueError):
        number = math.nan
    if not math.isfinite(number):
        raise ValueError(f"invalid {field}: expected finite number")
    return number


def _channel_text(row: Mapping[str, object]) -> str:
    tracking_channel = row.get("tracking_channel")
    channel = row.get("channel")
    tracking_text = str(tracking_channel).strip() if tracking_channel is not None else ""
    channel_text = str(channel).strip() if channel is not None else ""
    if tracking_text and channel_text and tracking_text != channel_text:
        raise ValueError("conflicting tracking_channel and channel")
    value = tracking_text or channel_text
    if not value:
        raise ValueError("missing tracking_channel")
    if not _CANONICAL_POSITIVE_INTEGER.fullmatch(value):
        raise ValueError("invalid tracking_channel: expected positive canonical decimal ID")
    return value


def build_stage2_window_index(
    path_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    """Collapse Stage2 paths to unique, validated run/window identities.

    First-seen order is retained so the output remains aligned to the frozen
    Stage2 ledger while window identifiers are always scoped by ``run_id``.
    """

    windows_by_key: dict[tuple[str, str], dict[str, str]] = {}
    seen_path_keys: set[tuple[str, str, str]] = set()
    scene_by_run: dict[str, str] = {}

    for row in path_rows:
        run_id = _required_text(row, "run_id")
        window_id = _positive_canonical_id(row, "window_id")
        path_id = _positive_canonical_id(row, "path_id")
        scene_id = _required_text(row, "scene_id")
        prn = _required_text(row, "prn")
        channel = _channel_text(row)

        path_key = (run_id, window_id, path_id)
        if path_key in seen_path_keys:
            raise ValueError(f"duplicate Stage2 path identity: {path_key}")
        seen_path_keys.add(path_key)

        prior_scene = scene_by_run.setdefault(run_id, scene_id)
        if prior_scene != scene_id:
            raise ValueError(f"run_id {run_id} has conflicting scene_id values")

        window_key = (run_id, window_id)
        candidate = {
            "run_id": run_id,
            "window_id": window_id,
            "scene_id": scene_id,
            "prn": prn,
            "tracking_channel": channel,
        }
        prior = windows_by_key.get(window_key)
        if prior is None:
            windows_by_key[window_key] = candidate
            continue

        conflicts = [
            field
            for field in ("scene_id", "prn", "tracking_channel")
            if prior[field] != candidate[field]
        ]
        if conflicts:
            raise ValueError(
                f"conflicting metadata for run/window {window_key}: {', '.join(conflicts)}"
            )

    return list(windows_by_key.values())


def build_stage0_utc_index(
    run_rows: Sequence[Mapping[str, str]],
    stage0_rows_by_run: Mapping[str, Sequence[Mapping[str, str]]],
    gps_week_by_scene: Mapping[str, int],
) -> dict[tuple[str, str], datetime]:
    """Map each Stage0 ``(run_id, window_id)`` to UTC using project GPS time.

    Rows are ordered by recording time for rollover detection.  A TOW decrease
    larger than half a GPS week is treated as one forward GPS-week rollover;
    smaller backwards movements, duplicate window IDs, and invalid clock
    fields fail closed.
    """

    runs_by_id: dict[str, str] = {}
    for run in run_rows:
        run_id = _required_text(run, "run_id")
        scene_id = _required_text(run, "scene_id")
        if run_id in runs_by_id:
            raise ValueError(f"duplicate run_id in run rows: {run_id}")
        runs_by_id[run_id] = scene_id

    unknown_stage0_runs = set(stage0_rows_by_run) - set(runs_by_id)
    if unknown_stage0_runs:
        raise ValueError(f"Stage0 rows supplied for unknown run_id: {sorted(unknown_stage0_runs)}")

    utc_by_window: dict[tuple[str, str], datetime] = {}
    for run_id, scene_id in runs_by_id.items():
        if scene_id not in gps_week_by_scene:
            raise ValueError(f"missing gps_week for scene_id {scene_id}")
        gps_week = gps_week_by_scene[scene_id]
        if isinstance(gps_week, bool) or not isinstance(gps_week, int) or gps_week < 0:
            raise ValueError(f"invalid gps_week for scene_id {scene_id}")

        rows = stage0_rows_by_run.get(run_id)
        if not rows:
            raise ValueError(f"missing Stage0 rows for run_id {run_id}")

        seen_window_ids: set[str] = set()
        ordered_rows: list[tuple[float, str, float]] = []
        for row in rows:
            window_id = _positive_canonical_id(row, "window_id")
            if window_id in seen_window_ids:
                raise ValueError(f"duplicate Stage0 window_id for run_id {run_id}: {window_id}")
            seen_window_ids.add(window_id)

            tow_s = _finite_number(row, "tow_s")
            if not 0 <= tow_s < GPS_WEEK_SECONDS:
                raise ValueError(f"invalid tow_s for run_id {run_id}, window_id {window_id}")
            recording_time_s = _finite_number(row, "recording_time_s")
            if recording_time_s < 0:
                raise ValueError(
                    f"invalid recording_time_s for run_id {run_id}, window_id {window_id}"
                )
            ordered_rows.append((recording_time_s, window_id, tow_s))

        ordered_rows.sort(key=lambda item: item[0])
        if any(
            ordered_rows[index][0] == ordered_rows[index - 1][0]
            for index in range(1, len(ordered_rows))
        ):
            raise ValueError(f"duplicate recording_time_s for run_id {run_id}")

        effective_week = gps_week
        previous_tow: float | None = None
        for _, window_id, tow_s in ordered_rows:
            if previous_tow is not None and tow_s < previous_tow:
                if previous_tow - tow_s > GPS_WEEK_SECONDS / 2:
                    effective_week += 1
                else:
                    raise ValueError(
                        f"nonmonotonic tow_s for run_id {run_id}, window_id {window_id}"
                    )
            elif previous_tow is not None and tow_s - previous_tow > GPS_WEEK_SECONDS / 2:
                raise ValueError(
                    f"unexpected forward tow_s jump for run_id {run_id}, window_id {window_id}"
                )

            utc_by_window[(run_id, window_id)] = gps_tow_to_utc(effective_week, tow_s)
            previous_tow = tow_s

    return utc_by_window
