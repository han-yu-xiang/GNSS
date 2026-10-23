"""Identity and time-index transforms for the Mainline Stage2 audit.

This module is deliberately limited to small tabular metadata.  It does not
open Stage2 scientific payloads, MATLAB files, or raw receiver samples.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence

from scripts.event_database.align_modeling_context import (
    GPS_WEEK_SECONDS,
    gps_tow_to_utc,
)
from scripts.preprocessing.satellite_geometry import (
    ElevationRecord,
    elevation_group,
    nmea_payload,
    parse_gsv_satellites,
    parse_nmea_datetime,
)


_CANONICAL_POSITIVE_INTEGER = re.compile(r"^[1-9][0-9]*$")
_CANONICAL_NONNEGATIVE_INTEGER = re.compile(r"^(?:0|[1-9][0-9]*)$")
_MAX_GSV_GAP_SECONDS = 5.0


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
    if not _CANONICAL_NONNEGATIVE_INTEGER.fullmatch(value):
        raise ValueError("invalid tracking_channel: expected nonnegative canonical decimal ID")
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
        environment_class = str(row.get("environment_class", "")).strip()
        elevation_group = str(row.get("elevation_group", "")).strip()

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
            "environment_class": environment_class,
            "elevation_group": elevation_group,
        }
        prior = windows_by_key.get(window_key)
        if prior is None:
            windows_by_key[window_key] = candidate
            continue

        conflicts = [
            field
            for field in (
                "scene_id",
                "prn",
                "tracking_channel",
                "environment_class",
                "elevation_group",
            )
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


def _as_utc(value: datetime, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"invalid {field}: timezone-aware datetime required")
    return value.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _format_number(value: float) -> str:
    if abs(value) < 0.0000005:
        value = 0.0
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _source_name(value: object) -> str:
    text = str(value).replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:/", text):
        return text.rsplit("/", 1)[-1]
    return text.removeprefix("./")


def parse_checksum_valid_gps_gsv_files(
    nmea_files: Sequence[Path],
    *,
    source_root: Path,
) -> tuple[list[ElevationRecord], Counter[str], dict[str, int | str]]:
    """Read checksum-verified GPS GSV observations with valid RMC timestamps.

    The shared ``parse_nmea_files`` helper accepts any ``*GSV`` talker and
    treats its satellite number as a GPS PRN.  This adapter keeps its checksum,
    date and satellite-field parsing primitives but restricts observations to
    ``$GPGSV`` and active checksum-valid RMC anchors, preventing constellation
    number collisions from masquerading as GPS PRNs.
    """

    root = source_root.resolve()
    observations: dict[tuple[datetime, str], ElevationRecord] = {}
    conflicting_observations: set[tuple[datetime, str]] = set()
    prn_counts: Counter[str] = Counter()
    diagnostics = Counter(
        {
            "nmea_files_seen": 0,
            "nmea_sentence_count": 0,
            "checksum_present_count": 0,
            "checksum_valid_count": 0,
            "bad_checksum_count": 0,
            "missing_checksum_count": 0,
            "valid_rmc_count": 0,
            "gsv_sentence_count": 0,
            "gps_gsv_checksum_valid_count": 0,
            "ignored_non_gps_gsv_count": 0,
            "gps_gsv_untimestamped_count": 0,
            "duplicate_gsv_observation_count": 0,
            "conflicting_gsv_observation_count": 0,
        }
    )
    first_rmc_utc: datetime | None = None

    for path in nmea_files:
        resolved = path.resolve()
        try:
            source_identity = resolved.relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError(f"NMEA source is outside source_root: {path}") from error
        diagnostics["nmea_files_seen"] += 1
        current_time: datetime | None = None
        with resolved.open("r", encoding="ascii", errors="replace") as handle:
            for raw_line in handle:
                fields, checksum_ok = nmea_payload(raw_line)
                if fields is None:
                    continue
                diagnostics["nmea_sentence_count"] += 1
                sentence = fields[0].upper()
                checksum_present = "*" in raw_line
                if checksum_present:
                    diagnostics["checksum_present_count"] += 1
                if checksum_present and checksum_ok:
                    diagnostics["checksum_valid_count"] += 1
                elif checksum_present:
                    diagnostics["bad_checksum_count"] += 1

                if sentence in {"GPRMC", "GNRMC"}:
                    if not checksum_present or not checksum_ok or len(fields) < 10 or fields[2] != "A":
                        current_time = None
                        if not checksum_present:
                            diagnostics["missing_checksum_count"] += 1
                        continue
                    try:
                        current_time = parse_nmea_datetime(fields[1], fields[9])
                    except (IndexError, TypeError, ValueError):
                        current_time = None
                        continue
                    if first_rmc_utc is None or current_time < first_rmc_utc:
                        first_rmc_utc = current_time
                    diagnostics["valid_rmc_count"] += 1
                    continue

                if not sentence.endswith("GSV"):
                    continue
                diagnostics["gsv_sentence_count"] += 1
                if sentence != "GPGSV":
                    diagnostics["ignored_non_gps_gsv_count"] += 1
                    continue
                if not checksum_present:
                    diagnostics["missing_checksum_count"] += 1
                    continue
                if not checksum_ok:
                    continue
                diagnostics["gps_gsv_checksum_valid_count"] += 1
                if current_time is None:
                    diagnostics["gps_gsv_untimestamped_count"] += 1
                    continue
                try:
                    message_count = int(fields[1])
                    message_number = int(fields[2])
                    satellites_in_view = int(fields[3])
                except (IndexError, ValueError):
                    continue

                for prn, elevation, azimuth, snr in parse_gsv_satellites(fields):
                    prn_counts[prn] += 1
                    try:
                        group = elevation_group(elevation)
                    except ValueError:
                        continue
                    observation_key = (current_time, prn)
                    record = ElevationRecord(
                        utc_time=current_time,
                        prn=prn,
                        elevation_deg=elevation,
                        azimuth_deg=azimuth,
                        snr_db_hz=snr,
                        elevation_group=group,
                        gsv_total_messages=message_count,
                        gsv_message_number=message_number,
                        satellites_in_view=satellites_in_view,
                        nmea_file=source_identity,
                        raw_gsv_sentence=raw_line.strip(),
                    )
                    if observation_key in conflicting_observations:
                        continue
                    existing = observations.get(observation_key)
                    if existing is not None:
                        diagnostics["duplicate_gsv_observation_count"] += 1
                        if (
                            existing.elevation_deg != record.elevation_deg
                            or existing.azimuth_deg != record.azimuth_deg
                        ):
                            diagnostics["conflicting_gsv_observation_count"] += 1
                            conflicting_observations.add(observation_key)
                            observations.pop(observation_key, None)
                            continue
                        existing_order = (
                            existing.nmea_file.casefold(),
                            existing.gsv_message_number,
                            existing.raw_gsv_sentence,
                        )
                        record_order = (
                            record.nmea_file.casefold(),
                            record.gsv_message_number,
                            record.raw_gsv_sentence,
                        )
                        if record_order < existing_order:
                            observations[observation_key] = record
                        continue
                    observations[observation_key] = record

    if conflicting_observations:
        raise ValueError("conflicting duplicate GPS GSV observation epochs detected")

    records = sorted(
        observations.values(),
        key=lambda record: (record.utc_time, int(record.prn[1:])),
    )
    diagnostic_values: dict[str, int | str] = dict(diagnostics)
    diagnostic_values["first_valid_rmc_utc"] = _iso_utc(first_rmc_utc) if first_rmc_utc else ""
    return records, prn_counts, diagnostic_values


def _prepare_gsv_cells(
    records_by_scene_prn: Mapping[tuple[str, str], Sequence[ElevationRecord]],
) -> dict[tuple[str, str], list[dict[str, object]]]:
    prepared: dict[tuple[str, str], list[dict[str, object]]] = {}
    for key, source_records in records_by_scene_prn.items():
        if not isinstance(key, tuple) or len(key) != 2:
            raise ValueError("GSV record key must be (scene_id, prn)")
        scene_id = str(key[0]).strip()
        prn = str(key[1]).strip()
        if not scene_id or not prn:
            raise ValueError("GSV record key requires scene_id and prn")

        records: list[ElevationRecord] = []
        for record in source_records:
            if str(record.prn).strip() != prn:
                raise ValueError(f"GSV record PRN conflicts with scene/PRN key {key}")
            _as_utc(record.utc_time, field="GSV utc_time")
            if (
                not math.isfinite(record.elevation_deg)
                or not 0 <= record.elevation_deg <= 90
                or not math.isfinite(record.azimuth_deg)
                or not 0 <= record.azimuth_deg < 360
            ):
                raise ValueError(f"invalid GSV geometry for {key} at {record.utc_time}")
            records.append(record)

        records.sort(
            key=lambda record: (
                _as_utc(record.utc_time, field="GSV utc_time"),
                _source_name(record.nmea_file),
                record.gsv_message_number,
                record.elevation_deg,
                record.azimuth_deg,
            )
        )
        timestamps = [_as_utc(record.utc_time, field="GSV utc_time") for record in records]
        if any(current == previous for previous, current in zip(timestamps, timestamps[1:])):
            raise ValueError(f"duplicate timestamp for scene/PRN {key}")

        cells: list[dict[str, object]] = []
        component_start = 0
        component_id = 0
        boundaries = [
            index
            for index, (previous, current) in enumerate(zip(timestamps, timestamps[1:]))
            if (current - previous).total_seconds() > _MAX_GSV_GAP_SECONDS
        ]
        component_ranges: list[tuple[int, int]] = []
        for boundary in boundaries:
            component_ranges.append((component_start, boundary + 1))
            component_start = boundary + 1
        if records:
            component_ranges.append((component_start, len(records)))

        for start, stop in component_ranges:
            component_times = timestamps[start:stop]
            gaps = [
                (component_times[index] - component_times[index - 1]).total_seconds()
                for index in range(1, len(component_times))
            ]
            cadence_limit = min(_MAX_GSV_GAP_SECONDS, median(gaps) / 2) if gaps else 0.0
            for local_index, absolute_index in enumerate(range(start, stop)):
                current = timestamps[absolute_index]
                lower = (
                    timestamps[absolute_index - 1]
                    + (current - timestamps[absolute_index - 1]) / 2
                    if local_index > 0
                    else current - timedelta(seconds=cadence_limit)
                )
                upper = (
                    current + (timestamps[absolute_index + 1] - current) / 2
                    if local_index + 1 < len(component_times)
                    else current + timedelta(seconds=cadence_limit)
                )
                cells.append(
                    {
                        "record": records[absolute_index],
                        "utc": current,
                        "lower": lower,
                        "upper": upper,
                        "cadence_limit": cadence_limit,
                        "component_id": component_id,
                    }
                )
            component_id += 1
        prepared[(scene_id, prn)] = cells
    return prepared


def _inside_long_gsv_gap(target: datetime, cells: Sequence[Mapping[str, object]]) -> bool:
    times = [cell["utc"] for cell in cells]
    return any(
        (right - left).total_seconds() > _MAX_GSV_GAP_SECONDS
        and left < target < right
        for left, right in zip(times, times[1:])
    )


def build_gsv_window_overlay(
    windows: Sequence[Mapping[str, str]],
    utc_by_window: Mapping[tuple[str, str], datetime],
    records_by_scene_prn: Mapping[tuple[str, str], Sequence[ElevationRecord]],
    *,
    max_tolerance_seconds: float = 5.0,
) -> list[dict[str, str]]:
    """Match Stage2 windows to actual same-scene, same-PRN GSV observations.

    Matching uses a nearest-observation Voronoi cell. Cells are split at gaps
    over five seconds; no endpoint padding is allowed into such a gap. Outside
    gaps, endpoint extension is limited to half the median component cadence
    and the caller's tolerance.
    """

    if (
        not math.isfinite(max_tolerance_seconds)
        or max_tolerance_seconds <= 0
        or max_tolerance_seconds > _MAX_GSV_GAP_SECONDS
    ):
        raise ValueError("max_tolerance_seconds must be in (0, 5]")

    prepared = _prepare_gsv_cells(records_by_scene_prn)
    seen_keys: set[tuple[str, str]] = set()
    output: list[dict[str, str]] = []
    for window in windows:
        run_id = _required_text(window, "run_id")
        window_id = _positive_canonical_id(window, "window_id")
        scene_id = _required_text(window, "scene_id")
        prn = _required_text(window, "prn")
        key = (run_id, window_id)
        if key in seen_keys:
            raise ValueError(f"duplicate Stage2 window identity: {key}")
        seen_keys.add(key)

        base = {
            "run_id": run_id,
            "window_id": window_id,
            "scene_id": scene_id,
            "prn": prn,
            "tracking_channel": str(window.get("tracking_channel", "")).strip(),
            "environment_class": str(window.get("environment_class", "")).strip(),
            "frozen_elevation_group": str(window.get("elevation_group", "MISSING")).strip()
            or "MISSING",
            "window_utc": "",
            "nearest_candidate_utc": "",
            "nearest_candidate_source_file": "",
            "nearest_candidate_record_id": "",
            "candidate_delta_seconds_signed": "",
            "candidate_delta_seconds_abs": "",
            "local_cadence_limit_seconds": "",
            "candidate_cell_status": "NO_CANDIDATE",
            "gsv_source_utc": "",
            "elevation_deg": "",
            "azimuth_deg": "",
            "source_file": "",
            "status": "MISSING",
            "missing_reason": "",
        }

        target_value = utc_by_window.get(key)
        if target_value is None:
            base["missing_reason"] = "INVALID_TIME_ANCHOR"
            output.append(base)
            continue
        target = _as_utc(target_value, field="window UTC")
        base["window_utc"] = _iso_utc(target)

        cells = prepared.get((scene_id, prn), [])
        if not cells:
            base["missing_reason"] = "NO_TARGET_PRN_GSV"
            output.append(base)
            continue
        if _inside_long_gsv_gap(target, cells):
            base["missing_reason"] = "GSV_GAP_OR_CADENCE_LIMIT"
            output.append(base)
            continue

        candidate = min(
            cells,
            key=lambda cell: (
                abs((cell["utc"] - target).total_seconds()),
                cell["utc"],
                _source_name(cell["record"].nmea_file),
                cell["record"].gsv_message_number,
            ),
        )
        record = candidate["record"]
        signed_delta = (candidate["utc"] - target).total_seconds()
        absolute_delta = abs(signed_delta)
        cadence_limit = float(candidate["cadence_limit"])
        in_cell = candidate["lower"] <= target <= candidate["upper"]
        base.update(
            {
                "nearest_candidate_utc": _iso_utc(candidate["utc"]),
                "nearest_candidate_source_file": _source_name(record.nmea_file),
                "nearest_candidate_record_id": (
                    f"{_source_name(record.nmea_file)}|{_iso_utc(candidate['utc'])}|"
                    f"{record.prn}|message_{record.gsv_message_number}"
                ),
                "candidate_delta_seconds_signed": _format_number(signed_delta),
                "candidate_delta_seconds_abs": _format_number(absolute_delta),
                "local_cadence_limit_seconds": _format_number(cadence_limit),
                "candidate_cell_status": "IN_CELL" if in_cell else "OUTSIDE_CELL",
            }
        )

        if in_cell and absolute_delta <= cadence_limit and absolute_delta <= max_tolerance_seconds:
            base.update(
                {
                    "gsv_source_utc": _iso_utc(candidate["utc"]),
                    "elevation_deg": _format_number(record.elevation_deg),
                    "azimuth_deg": _format_number(record.azimuth_deg),
                    "source_file": _source_name(record.nmea_file),
                    "status": "GSV_MATCHED",
                }
            )
        elif not in_cell:
            base["missing_reason"] = "NO_TEMPORAL_OVERLAP"
        elif absolute_delta > cadence_limit:
            base["missing_reason"] = "GSV_GAP_OR_CADENCE_LIMIT"
        else:
            base["missing_reason"] = "OUT_OF_TOLERANCE"

        output.append(base)
    return output


def _tolerance_label(value: float) -> str:
    return _format_number(value).replace(".", "_")


def _sensitivity_count(rows: Sequence[Mapping[str, str]], tolerance: float) -> int:
    count = 0
    for row in rows:
        if row.get("candidate_cell_status") != "IN_CELL":
            continue
        delta = row.get("candidate_delta_seconds_abs", "")
        cadence = row.get("local_cadence_limit_seconds", "")
        try:
            absolute_delta = float(delta)
            cadence_limit = float(cadence)
        except (TypeError, ValueError):
            continue
        if math.isfinite(absolute_delta) and math.isfinite(cadence_limit):
            if absolute_delta <= tolerance and absolute_delta <= cadence_limit:
                count += 1
    return count


def summarize_geometry_coverage(
    overlay: Sequence[Mapping[str, str]],
    task_sources: Sequence[Mapping[str, str]],
    tolerances_seconds: Sequence[float] = (0.5, 1.0, 2.0, 5.0),
) -> list[dict[str, str]]:
    """Summarize row-preserving GSV coverage and per-task source availability."""

    tolerances = sorted(set(float(value) for value in tolerances_seconds))
    if not tolerances or any(
        not math.isfinite(value) or value <= 0 or value > _MAX_GSV_GAP_SECONDS
        for value in tolerances
    ):
        raise ValueError("tolerances_seconds must contain unique values in (0, 5]")

    overlay_by_run: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    seen_window_keys: set[tuple[str, str]] = set()
    for row in overlay:
        run_id = _required_text(row, "run_id")
        window_id = _positive_canonical_id(row, "window_id")
        if (run_id, window_id) in seen_window_keys:
            raise ValueError(f"duplicate overlay window identity: {(run_id, window_id)}")
        seen_window_keys.add((run_id, window_id))
        if row.get("status") not in {"GSV_MATCHED", "MISSING"}:
            raise ValueError(f"invalid overlay status for {(run_id, window_id)}")
        overlay_by_run[run_id].append(row)

    source_by_run: dict[str, Mapping[str, str]] = {}
    for source in task_sources:
        run_id = _required_text(source, "run_id")
        if run_id in source_by_run:
            raise ValueError(f"duplicate task source run_id: {run_id}")
        source_by_run[run_id] = source
        for overlay_row in overlay_by_run.get(run_id, []):
            for field in ("scene_id", "prn"):
                source_value = str(source.get(field, "")).strip()
                overlay_value = str(overlay_row.get(field, "")).strip()
                if source_value and overlay_value and source_value != overlay_value:
                    raise ValueError(f"task source {field} conflicts with overlay for run_id {run_id}")

    if source_by_run and set(overlay_by_run) - set(source_by_run):
        raise ValueError(
            f"overlay contains run_id absent from task sources: {sorted(set(overlay_by_run) - set(source_by_run))}"
        )

    grouped: dict[tuple[str, str, str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in overlay:
        grouped[
            (
                str(row.get("scene_id", "")).strip(),
                str(row.get("environment_class", "")).strip(),
                str(row.get("prn", "")).strip(),
                str(row.get("frozen_elevation_group", "")).strip(),
            )
        ].append(row)

    def coverage_row(
        scope: str,
        rows: Sequence[Mapping[str, str]],
        dimensions: tuple[str, str, str, str] = ("", "", "", ""),
    ) -> dict[str, str]:
        matched = sum(row.get("status") == "GSV_MATCHED" for row in rows)
        missing = len(rows) - matched
        reasons = Counter(
            str(row.get("missing_reason", "")).strip()
            for row in rows
            if row.get("status") == "MISSING" and str(row.get("missing_reason", "")).strip()
        )
        result = {
            "summary_scope": scope,
            "scene_id": dimensions[0],
            "environment_class": dimensions[1],
            "prn": dimensions[2],
            "frozen_elevation_group": dimensions[3],
            "run_id": "",
            "window_count": str(len(rows)),
            "gsv_matched_count": str(matched),
            "missing_count": str(missing),
            "missing_reason_counts": ";".join(
                f"{key}={reasons[key]}" for key in sorted(reasons)
            ),
        }
        for tolerance in tolerances:
            result[f"matched_within_{_tolerance_label(tolerance)}s"] = str(
                _sensitivity_count(rows, tolerance)
            )
        return result

    summary = [coverage_row("TOTAL", overlay)]
    for dimensions in sorted(grouped):
        summary.append(coverage_row("GROUPED", grouped[dimensions], dimensions))

    source_fields = (
        "scene_id",
        "environment_class",
        "prn",
        "frozen_elevation_group",
        "nmea_available",
        "nmea_file_count",
        "rmc_valid_count",
        "gsv_valid_count",
        "target_prn_in_rinex",
        "gps_time_alignment_status",
        "target_prn_gsv_record_count",
    )
    for run_id in sorted(source_by_run):
        source = source_by_run[run_id]
        rows = overlay_by_run.get(run_id, [])
        row = coverage_row("TASK_SOURCE", rows)
        row["run_id"] = run_id
        for field in source_fields:
            row[field] = str(source.get(field, "")).strip()
        summary.append(row)
    return summary
