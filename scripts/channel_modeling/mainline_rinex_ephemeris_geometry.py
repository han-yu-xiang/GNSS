"""GPS broadcast-orbit geometry for a separately labeled recovery overlay.

This module does not change the receiver-measured GSV geometry pipeline.  It
propagates only healthy GPS LNAV records in a bounded toe interval and returns
geometric elevation; callers must retain its distinct derived provenance.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence


GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
GPS_WEEK_SECONDS = 604800.0
GPS_UTC_OFFSET_SECONDS = 18.0
GPS_MU_M3_S2 = 3.986005e14
EARTH_ROTATION_RAD_S = 7.2921151467e-5
SPEED_OF_LIGHT_M_S = 299792458.0
WGS84_A_M = 6378137.0
WGS84_F = 1.0 / 298.257223563
_GPS_PRN = re.compile(r"^G\d{2}$")
_GPS_RECORD = re.compile(r"^G\d{2}\s")


@dataclass(frozen=True)
class GpsEphemeris:
    prn: str
    toc_gps_calendar: datetime
    af0_s: float
    af1_s_s: float
    af2_s_s2: float
    iode: float
    crs_m: float
    delta_n_rad_s: float
    m0_rad: float
    cuc_rad: float
    eccentricity: float
    cus_rad: float
    sqrt_a_m_sqrt: float
    toe_seconds: float
    cic_rad: float
    omega0_rad: float
    cis_rad: float
    inclination0_rad: float
    crc_m: float
    argument_perigee_rad: float
    omega_dot_rad_s: float
    idot_rad_s: float
    week_number: int
    health: int
    fit_interval_hours: float


def _fixed_fields(line: str, start: int, count: int = 4, *, blank_as_zero: bool = False) -> list[float]:
    text = line[start:].rstrip("\r\n")
    if len(text) < count * 19:
        raise ValueError("incomplete RINEX navigation record")
    values: list[float] = []
    for index in range(count):
        raw = text[index * 19 : (index + 1) * 19].strip()
        if not raw:
            if blank_as_zero:
                values.append(0.0)
                continue
            raise ValueError("blank field in RINEX navigation record")
        try:
            value = float(raw.replace("D", "E").replace("d", "E"))
        except ValueError as exc:
            raise ValueError("invalid numeric field in RINEX navigation record") from exc
        if not math.isfinite(value):
            raise ValueError("non-finite value in RINEX navigation record")
        values.append(value)
    return values


def parse_gps_lnav_records(text: str) -> list[GpsEphemeris]:
    """Parse GPS records from RINEX 3 navigation text; ignore other systems."""
    lines = text.splitlines()
    records: list[GpsEphemeris] = []
    index = 0
    in_header = any("END OF HEADER" in line for line in lines)
    if in_header:
        while index < len(lines) and "END OF HEADER" not in lines[index]:
            index += 1
        index += 1

    while index < len(lines):
        line = lines[index]
        if not _GPS_RECORD.match(line):
            index += 1
            continue
        if len(lines) - index < 8:
            raise ValueError("incomplete RINEX navigation record")
        try:
            prn = line[:3]
            epoch_parts = line[3:23].split()
            if len(epoch_parts) != 6:
                # Whitespace before the epoch varies by RINEX producer; token
                # parsing is safe here because the remaining numeric fields
                # remain fixed-width beginning at column 23.
                epoch_parts = line[:23].split()[1:]
            if len(epoch_parts) != 6:
                raise ValueError("invalid RINEX toc")
            year, month, day, hour, minute = (int(part) for part in epoch_parts[:5])
            seconds = float(epoch_parts[5])
            whole_seconds = int(seconds)
            toc = datetime(year, month, day, hour, minute, whole_seconds) + timedelta(
                seconds=seconds - whole_seconds
            )
            clock = _fixed_fields(line, 23, 3)
            row1 = _fixed_fields(lines[index + 1], 4)
            row2 = _fixed_fields(lines[index + 2], 4)
            row3 = _fixed_fields(lines[index + 3], 4)
            row4 = _fixed_fields(lines[index + 4], 4)
            row5 = _fixed_fields(lines[index + 5], 4)
            row6 = _fixed_fields(lines[index + 6], 4)
            # Transmission/fit/spare fields are optional in RINEX 3 NAV.
            row7 = _fixed_fields(lines[index + 7], 4, blank_as_zero=True)
            week = int(round(row5[2]))
            health = int(round(row6[1]))
            if abs(row5[2] - week) > 1e-6 or abs(row6[1] - health) > 1e-6:
                raise ValueError("non-integral GPS week or health field")
            records.append(
                GpsEphemeris(
                    prn=prn,
                    toc_gps_calendar=toc,
                    af0_s=clock[0],
                    af1_s_s=clock[1],
                    af2_s_s2=clock[2],
                    iode=row1[0],
                    crs_m=row1[1],
                    delta_n_rad_s=row1[2],
                    m0_rad=row1[3],
                    cuc_rad=row2[0],
                    eccentricity=row2[1],
                    cus_rad=row2[2],
                    sqrt_a_m_sqrt=row2[3],
                    toe_seconds=row3[0],
                    cic_rad=row3[1],
                    omega0_rad=row3[2],
                    cis_rad=row3[3],
                    inclination0_rad=row4[0],
                    crc_m=row4[1],
                    argument_perigee_rad=row4[2],
                    omega_dot_rad_s=row4[3],
                    idot_rad_s=row5[0],
                    week_number=week,
                    health=health,
                    fit_interval_hours=row7[1],
                )
            )
        except (IndexError, OverflowError) as exc:
            raise ValueError("invalid RINEX navigation record") from exc
        index += 8
    return records


def _gps_seconds(utc_time: datetime, gps_utc_offset_seconds: float) -> float:
    if utc_time.tzinfo is None or utc_time.utcoffset() is None:
        raise ValueError("observation time must be timezone-aware")
    if not math.isfinite(gps_utc_offset_seconds) or gps_utc_offset_seconds < 0:
        raise ValueError("invalid GPS-UTC offset")
    gps_time = utc_time.astimezone(timezone.utc) + timedelta(
        seconds=gps_utc_offset_seconds
    )
    return (gps_time - GPS_EPOCH).total_seconds()


def select_ephemeris(
    records: Sequence[GpsEphemeris],
    prn: str,
    observation_utc: datetime,
    *,
    max_toe_age_s: float = 7200.0,
    gps_utc_offset_seconds: float = GPS_UTC_OFFSET_SECONDS,
) -> GpsEphemeris | None:
    """Choose the nearest healthy exact-PRN record inside the age bound."""
    if not _GPS_PRN.fullmatch(prn):
        raise ValueError("invalid GPS PRN")
    if not math.isfinite(max_toe_age_s) or max_toe_age_s < 0:
        raise ValueError("invalid maximum toe age")
    observation_gps_s = _gps_seconds(observation_utc, gps_utc_offset_seconds)
    eligible: list[tuple[float, GpsEphemeris]] = []
    for record in records:
        if record.prn != prn or record.health != 0:
            continue
        if record.week_number < 0 or not 0.0 <= record.toe_seconds < GPS_WEEK_SECONDS:
            continue
        ephemeris_gps_s = record.week_number * GPS_WEEK_SECONDS + record.toe_seconds
        # RINEX GPS week numbers are continuous; folding this difference by a
        # week would make an ephemeris exactly one week stale look current.
        age = abs(observation_gps_s - ephemeris_gps_s)
        if age <= max_toe_age_s:
            eligible.append((age, record))
    if not eligible:
        return None
    eligible.sort(key=lambda item: (item[0], item[1].toc_gps_calendar, item[1].iode))
    return eligible[0][1]


def _normalize_week_seconds(value: float) -> float:
    while value > GPS_WEEK_SECONDS / 2:
        value -= GPS_WEEK_SECONDS
    while value < -GPS_WEEK_SECONDS / 2:
        value += GPS_WEEK_SECONDS
    return value


def _satellite_ecef(ephemeris: GpsEphemeris, gps_seconds: float, travel_s: float) -> tuple[float, float, float]:
    toe_abs = ephemeris.week_number * GPS_WEEK_SECONDS + ephemeris.toe_seconds
    transmit_abs = gps_seconds - travel_s
    tk = _normalize_week_seconds(transmit_abs - toe_abs)
    a = ephemeris.sqrt_a_m_sqrt**2
    if not math.isfinite(a) or a <= 0 or not 0 <= ephemeris.eccentricity < 1:
        raise ValueError("invalid broadcast orbit parameters")
    mean_motion = math.sqrt(GPS_MU_M3_S2 / (a**3)) + ephemeris.delta_n_rad_s
    mean_anomaly = ephemeris.m0_rad + mean_motion * tk
    eccentric_anomaly = mean_anomaly
    for _ in range(20):
        residual = eccentric_anomaly - ephemeris.eccentricity * math.sin(eccentric_anomaly) - mean_anomaly
        step = residual / (1 - ephemeris.eccentricity * math.cos(eccentric_anomaly))
        eccentric_anomaly -= step
        if abs(step) < 1e-13:
            break
    else:
        raise ValueError("Kepler equation failed to converge")

    eccentricity = ephemeris.eccentricity
    true_anomaly = math.atan2(
        math.sqrt(1 - eccentricity**2) * math.sin(eccentric_anomaly),
        math.cos(eccentric_anomaly) - eccentricity,
    )
    phi = true_anomaly + ephemeris.argument_perigee_rad
    twice_phi = 2 * phi
    u = phi + ephemeris.cuc_rad * math.cos(twice_phi) + ephemeris.cus_rad * math.sin(twice_phi)
    radius = a * (1 - eccentricity * math.cos(eccentric_anomaly))
    radius += ephemeris.crc_m * math.cos(twice_phi) + ephemeris.crs_m * math.sin(twice_phi)
    inclination = ephemeris.inclination0_rad + ephemeris.idot_rad_s * tk
    inclination += ephemeris.cic_rad * math.cos(twice_phi) + ephemeris.cis_rad * math.sin(twice_phi)
    x_orbit = radius * math.cos(u)
    y_orbit = radius * math.sin(u)
    omega = ephemeris.omega0_rad + (ephemeris.omega_dot_rad_s - EARTH_ROTATION_RAD_S) * tk
    omega -= EARTH_ROTATION_RAD_S * ephemeris.toe_seconds
    x_ecef = x_orbit * math.cos(omega) - y_orbit * math.cos(inclination) * math.sin(omega)
    y_ecef = x_orbit * math.sin(omega) + y_orbit * math.cos(inclination) * math.cos(omega)
    z_ecef = y_orbit * math.sin(inclination)
    return x_ecef, y_ecef, z_ecef


def _receiver_ecef(latitude_deg: float, longitude_deg: float, height_m: float) -> tuple[float, float, float]:
    latitude = math.radians(latitude_deg)
    longitude = math.radians(longitude_deg)
    eccentricity_sq = WGS84_F * (2 - WGS84_F)
    prime_vertical = WGS84_A_M / math.sqrt(1 - eccentricity_sq * math.sin(latitude) ** 2)
    x = (prime_vertical + height_m) * math.cos(latitude) * math.cos(longitude)
    y = (prime_vertical + height_m) * math.cos(latitude) * math.sin(longitude)
    z = (prime_vertical * (1 - eccentricity_sq) + height_m) * math.sin(latitude)
    return x, y, z


def satellite_elevation_deg(
    ephemeris: GpsEphemeris,
    observation_utc: datetime,
    latitude_deg: float,
    longitude_deg: float,
    height_m: float = 0.0,
    *,
    gps_utc_offset_seconds: float = GPS_UTC_OFFSET_SECONDS,
) -> float:
    """Propagate one GPS LNAV record and return topocentric elevation."""
    if ephemeris.health != 0:
        raise ValueError("ephemeris is unhealthy")
    if not -90 <= latitude_deg <= 90 or not math.isfinite(latitude_deg):
        raise ValueError("invalid latitude")
    if not -180 <= longitude_deg <= 180 or not math.isfinite(longitude_deg):
        raise ValueError("invalid longitude")
    if not math.isfinite(height_m) or abs(height_m) > 10000:
        raise ValueError("invalid receiver height")
    gps_time = _gps_seconds(observation_utc, gps_utc_offset_seconds)
    receiver = _receiver_ecef(latitude_deg, longitude_deg, height_m)
    travel_s = 0.075
    for _ in range(5):
        satellite_tx = _satellite_ecef(ephemeris, gps_time, travel_s)
        angle = EARTH_ROTATION_RAD_S * travel_s
        cosine = math.cos(angle)
        sine = math.sin(angle)
        satellite = (
            cosine * satellite_tx[0] + sine * satellite_tx[1],
            -sine * satellite_tx[0] + cosine * satellite_tx[1],
            satellite_tx[2],
        )
        travel_s = math.dist(receiver, satellite) / SPEED_OF_LIGHT_M_S

    dx = satellite[0] - receiver[0]
    dy = satellite[1] - receiver[1]
    dz = satellite[2] - receiver[2]
    lat = math.radians(latitude_deg)
    lon = math.radians(longitude_deg)
    east = -math.sin(lon) * dx + math.cos(lon) * dy
    north = (
        -math.sin(lat) * math.cos(lon) * dx
        - math.sin(lat) * math.sin(lon) * dy
        + math.cos(lat) * dz
    )
    up = (
        math.cos(lat) * math.cos(lon) * dx
        + math.cos(lat) * math.sin(lon) * dy
        + math.sin(lat) * dz
    )
    elevation = math.degrees(math.atan2(up, math.hypot(east, north)))
    if not math.isfinite(elevation) or not -90.0 <= elevation <= 90.0:
        raise ValueError("invalid computed elevation")
    return elevation
