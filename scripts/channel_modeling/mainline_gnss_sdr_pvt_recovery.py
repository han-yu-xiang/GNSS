"""Read GNSS-SDR RTKLIB PVT dumps and recover missing Stage2 positions.

Only explicit RTKLIB single-point XYZ solutions are eligible.  Existing NMEA
matches always take precedence; no position is interpolated or extrapolated.
"""

from __future__ import annotations

import bisect
import math
import struct
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence


GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
GPS_UTC_OFFSET_SECONDS = 18.0
# GNSS-SDR RTKLIB dump: uint32 TOW-ms, uint32 week, 17 doubles,
# 3 uint8 values, 2 floats, and 4 doubles (187 bytes total).
PVT_RECORD = struct.Struct("<II17d3B2f4d")
PVT_POSITION_FIELDS = (
    "run_id", "window_id", "scene_id", "prn", "tracking_channel",
    "window_utc", "position_utc", "position_delta_seconds",
    "position_source_path", "position_source_record_id", "latitude_deg",
    "longitude_deg", "position_status", "missing_reason",
)
PVT_OVERLAY_FIELDS = (
    "run_id", "window_id", "scene_id", "prn", "tracking_channel",
    "window_utc", "original_position_status", "original_missing_reason",
    "position_recovery_status", "position_source", "position_utc",
    "position_delta_seconds", "position_source_file", "pvt_record_id",
    "pvt_rx_tow_delta_seconds", "pvt_solution_status", "pvt_solution_type", "pvt_valid_satellites",
    "pvt_pdop", "latitude_deg", "longitude_deg",
)


@dataclass(frozen=True)
class PvtSolution:
    record_index: int
    tow_ms: int
    gps_week: int
    rx_time_s: float
    receiver_clock_offset_s: float
    ecef_position_m: tuple[float, float, float]
    ecef_velocity_m_s: tuple[float, float, float]
    covariance_terms_m2: tuple[float, float, float, float, float, float]
    latitude_deg: float
    longitude_deg: float
    height_m: float
    valid_satellites: int
    solution_status: int
    solution_type: int
    ambiguity_ratio: float
    ambiguity_threshold: float
    gdop: float
    pdop: float
    hdop: float
    vdop: float

    @property
    def position_utc(self) -> datetime:
        return GPS_EPOCH + timedelta(
            weeks=self.gps_week,
            seconds=self.rx_time_s - GPS_UTC_OFFSET_SECONDS,
        )

    @property
    def is_valid_single_point(self) -> bool:
        numeric = (
            self.rx_time_s,
            self.receiver_clock_offset_s,
            *self.ecef_position_m,
            *self.ecef_velocity_m_s,
            *self.covariance_terms_m2,
            self.latitude_deg,
            self.longitude_deg,
            self.height_m,
            self.ambiguity_ratio,
            self.ambiguity_threshold,
            self.gdop,
            self.pdop,
            self.hdop,
            self.vdop,
        )
        if not all(math.isfinite(value) for value in numeric):
            return False
        if self.solution_status != 5 or self.solution_type != 0 or self.valid_satellites < 4:
            return False
        if not -90.0 <= self.latitude_deg <= 90.0:
            return False
        if not -180.0 <= self.longitude_deg <= 180.0:
            return False
        if any(value < 0.0 for value in self.covariance_terms_m2[:3]):
            return False
        if any(value < 0.0 for value in (self.gdop, self.pdop, self.hdop, self.vdop)):
            return False
        if (
            not 0 <= self.tow_ms < 604_800_000
            or not 0.0 <= self.rx_time_s < 604_800.0
            or self.gps_week < 0
        ):
            return False
        # GNSS-SDR records both the receiver-aligned observation RX_time and
        # each channel's decoded TOW_at_current_symbol_ms. They need not be
        # equal: asynchronous channel symbol timing can lag the common RX epoch.
        return True


def parse_pvt_dump(data: bytes) -> list[PvtSolution]:
    """Parse complete GNSS-SDR RTKLIB records; reject any partial final row."""
    if len(data) % PVT_RECORD.size:
        raise ValueError(
            f"PVT dump does not end on a record boundary ({PVT_RECORD.size} bytes)"
        )
    output: list[PvtSolution] = []
    for index, record in enumerate(PVT_RECORD.iter_unpack(data), start=1):
        tow_ms, week = record[:2]
        values = record[2:19]
        valid_satellites, status, solution_type = record[19:22]
        ambiguity_ratio, ambiguity_threshold = record[22:24]
        gdop, pdop, hdop, vdop = record[24:28]
        output.append(
            PvtSolution(
                record_index=index,
                tow_ms=tow_ms,
                gps_week=week,
                rx_time_s=values[0],
                receiver_clock_offset_s=values[1],
                ecef_position_m=tuple(values[2:5]),
                ecef_velocity_m_s=tuple(values[5:8]),
                covariance_terms_m2=tuple(values[8:14]),
                latitude_deg=values[14],
                longitude_deg=values[15],
                height_m=values[16],
                valid_satellites=valid_satellites,
                solution_status=status,
                solution_type=solution_type,
                ambiguity_ratio=ambiguity_ratio,
                ambiguity_threshold=ambiguity_threshold,
                gdop=gdop,
                pdop=pdop,
                hdop=hdop,
                vdop=vdop,
            )
        )
    return output


def _index_unique(rows: Sequence[Mapping[str, str]], label: str) -> dict[tuple[str, str], Mapping[str, str]]:
    indexed: dict[tuple[str, str], Mapping[str, str]] = {}
    for row in rows:
        key = (row.get("run_id", ""), row.get("window_id", ""))
        if not all(key):
            raise ValueError(f"blank run_id/window_id in {label}")
        if key in indexed:
            raise ValueError(f"duplicate identity in {label}: {key}")
        indexed[key] = row
    return indexed


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _pvt_epoch_groups(
    records: Sequence[PvtSolution],
) -> tuple[list[datetime], list[float], dict[datetime, PvtSolution], set[datetime]]:
    grouped: dict[datetime, list[PvtSolution]] = defaultdict(list)
    for record in records:
        if record.is_valid_single_point:
            grouped[record.position_utc].append(record)

    selected: dict[datetime, PvtSolution] = {}
    ambiguous: set[datetime] = set()
    for epoch, group in grouped.items():
        reference = group[0]
        same_position = all(
            abs(record.latitude_deg - reference.latitude_deg) <= 1e-9
            and abs(record.longitude_deg - reference.longitude_deg) <= 1e-9
            and abs(record.height_m - reference.height_m) <= 0.01
            for record in group[1:]
        )
        if not same_position:
            ambiguous.add(epoch)
            continue
        # Equal-timestamp records can be solver updates from multiple input
        # channels.  If their positions agree, use the strongest satellite
        # support, then lower PDOP, then stable original record order.
        selected[epoch] = min(
            group,
            key=lambda item: (-item.valid_satellites, item.pdop, item.record_index),
        )
    epochs = sorted(set(selected) | ambiguous)
    return epochs, [epoch.timestamp() for epoch in epochs], selected, ambiguous


def build_pvt_position_overlay(
    geometry_rows: Sequence[Mapping[str, str]],
    trajectory_rows: Sequence[Mapping[str, str]],
    pvt_by_scene: Mapping[str, Sequence[PvtSolution]],
    *,
    pvt_source_by_scene: Mapping[str, str],
    max_position_delta_seconds: float = 0.5,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Fill only missing old positions from exact-identity nearby PVT fixes.

    Returned first value is a complete merged trajectory overlay suitable for
    the independent ephemeris runner.  The second is the separate audit layer
    and retains the old missing classification for every Stage2 identity.
    """
    if not math.isfinite(max_position_delta_seconds) or max_position_delta_seconds < 0:
        raise ValueError("maximum position delta must be finite and nonnegative")
    geometry = _index_unique(geometry_rows, "geometry overlay")
    trajectory = _index_unique(trajectory_rows, "trajectory overlay")
    if geometry.keys() != trajectory.keys():
        raise ValueError("geometry and trajectory overlays must have the same identity set")
    scenes = {row.get("scene_id", "") for row in geometry.values()}
    if set(pvt_by_scene) != scenes or set(pvt_source_by_scene) != scenes:
        raise ValueError("PVT records and source paths must cover exactly the overlay scenes")

    indexes = {
        scene: _pvt_epoch_groups(records)
        for scene, records in pvt_by_scene.items()
    }
    merged: list[dict[str, str]] = []
    overlay: list[dict[str, str]] = []
    for key, geom in geometry.items():
        original = trajectory[key]
        for field in ("scene_id", "prn", "tracking_channel", "window_utc"):
            if geom.get(field, "") != original.get(field, ""):
                raise ValueError(f"{field} mismatch for identity {key}")
        scene = geom["scene_id"]
        pvt_path = pvt_source_by_scene[scene]
        original_status = original.get("position_status", "")
        if original_status == "POSITION_MATCHED":
            source = "EXISTING_NMEA"
            merged_row = dict(original)
            merged_row["position_source"] = source
            merged.append(merged_row)
            overlay.append(
                {
                    "run_id": key[0],
                    "window_id": key[1],
                    "scene_id": scene,
                    "prn": geom["prn"],
                    "tracking_channel": geom["tracking_channel"],
                    "window_utc": geom["window_utc"],
                    "original_position_status": original_status,
                    "original_missing_reason": "",
                    "position_recovery_status": "PRESERVED_EXISTING_POSITION",
                    "position_source": source,
                    "position_utc": original.get("position_utc", ""),
                    "position_delta_seconds": original.get("position_delta_seconds", ""),
                    "position_source_file": original.get("position_source_path", ""),
                    "pvt_record_id": "",
                    "pvt_rx_tow_delta_seconds": "",
                    "pvt_solution_status": "",
                    "pvt_solution_type": "",
                    "pvt_valid_satellites": "",
                    "pvt_pdop": "",
                    "latitude_deg": original.get("latitude_deg", ""),
                    "longitude_deg": original.get("longitude_deg", ""),
                }
            )
            continue
        if original_status not in {"POSITION_MISSING", "MISSING", ""}:
            raise ValueError(f"unknown original position status for identity {key}: {original_status}")

        window_utc = datetime.fromisoformat(
            geom["window_utc"].replace("Z", "+00:00")
        )
        if window_utc.tzinfo is None or window_utc.utcoffset() is None:
            raise ValueError(f"window_utc has no timezone for identity {key}")
        window_utc = window_utc.astimezone(timezone.utc)
        epochs, epoch_timestamps, selected, ambiguous = indexes[scene]
        target = window_utc.timestamp()
        insertion = bisect.bisect_left(epoch_timestamps, target)
        candidate_indices = [index for index in (insertion - 1, insertion) if 0 <= index < len(epochs)]
        if not candidate_indices:
            selected_epoch = None
            delta = math.inf
        else:
            selected_epoch = min(
                (epochs[index] for index in candidate_indices),
                key=lambda epoch: (abs(epoch.timestamp() - target), epoch),
            )
            delta = selected_epoch.timestamp() - target
        if selected_epoch is not None and abs(delta) <= max_position_delta_seconds:
            if selected_epoch in ambiguous:
                pvt = None
                recovery_status = "AMBIGUOUS_PVT_SOLUTIONS_AT_EPOCH"
            else:
                pvt = selected[selected_epoch]
                recovery_status = "RECOVERED_FROM_PVT_SINGLE"
        else:
            pvt = None
            recovery_status = "NO_VALID_PVT_FIX_WITHIN_TOLERANCE"

        merged_row = dict(original)
        merged_row["position_source"] = ""
        if pvt is not None:
            merged_row.update(
                {
                    "position_utc": _format_utc(pvt.position_utc),
                    "position_delta_seconds": f"{delta:.6f}",
                    "position_source_path": pvt_path,
                    "position_source_record_id": f"{PathLikeName(pvt_path)}:record={pvt.record_index:08d}",
                    "latitude_deg": f"{pvt.latitude_deg:.9f}",
                    "longitude_deg": f"{pvt.longitude_deg:.9f}",
                    "position_status": "POSITION_MATCHED",
                    "missing_reason": "",
                    "position_source": "GNSS_SDR_PVT_SINGLE",
                }
            )
        merged.append(merged_row)
        overlay.append(
            {
                "run_id": key[0],
                "window_id": key[1],
                "scene_id": scene,
                "prn": geom["prn"],
                "tracking_channel": geom["tracking_channel"],
                "window_utc": geom["window_utc"],
                "original_position_status": original_status,
                "original_missing_reason": original.get("missing_reason", ""),
                "position_recovery_status": recovery_status,
                "position_source": "GNSS_SDR_PVT_SINGLE" if pvt is not None else "",
                "position_utc": _format_utc(pvt.position_utc) if pvt else "",
                "position_delta_seconds": f"{delta:.6f}" if pvt else "",
                "position_source_file": pvt_path if pvt else "",
                "pvt_record_id": (
                    f"{PathLikeName(pvt_path)}:record={pvt.record_index:08d}" if pvt else ""
                ),
                "pvt_rx_tow_delta_seconds": (
                    f"{pvt.rx_time_s - pvt.tow_ms / 1000.0:.6f}" if pvt else ""
                ),
                "pvt_solution_status": str(pvt.solution_status) if pvt else "",
                "pvt_solution_type": str(pvt.solution_type) if pvt else "",
                "pvt_valid_satellites": str(pvt.valid_satellites) if pvt else "",
                "pvt_pdop": f"{pvt.pdop:.6f}" if pvt else "",
                "latitude_deg": f"{pvt.latitude_deg:.9f}" if pvt else "",
                "longitude_deg": f"{pvt.longitude_deg:.9f}" if pvt else "",
            }
        )
    return merged, overlay


def PathLikeName(path: str) -> str:
    """Return a stable basename without importing pathlib into hot row loops."""
    return path.replace("\\", "/").rsplit("/", 1)[-1]
