"""Read-only GNSS-SDR weather-effect MVP audit.

The tool reads existing GNSS-SDR tracking, telemetry, observables, metadata,
configuration, and navigation XML artifacts only. It never opens raw IQ and
never invokes MATLAB, GNSS-SDR, or SAGE.

The tracking and telemetry MAT files are MATLAB 7.3 files. The existing MATLAB
HDF5 DLL is used through ctypes as a read-only HDF5 reader; the MATLAB
executable is not started.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = PROJECT_ROOT / (
    "dataset_generation_logs/darkroom_channel_emulation/"
    "gnss_sdr_weather_mvp_20260817"
)
MATLAB_HDF5_DLL = Path(r"D:\Program Files\Matlab\bin\win64\hdf5.dll")
PRODUCTION_SOURCE = PROJECT_ROOT / "scripts/sage_pipeline/run_nav_sage_pipeline.m"
REQUESTED_PRODUCTION_SOURCE_SHA256 = (
    "95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0"
)
LOCK_THRESHOLD = -0.5
EXPECTED_SAMPLE_RATE = 10_230_000
EXPECTED_MAPPINGS: dict[str, dict[int, str]] = {
    "F1023_clear": {3: "G29", 8: "G13", 10: "G24", 11: "G12"},
    "F1023_midrain": {8: "G24", 9: "G20"},
    "F1023_heavyrain": {1: "G02", 4: "G31", 7: "G01"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def finite_values(values: np.ndarray) -> np.ndarray:
    flat = np.asarray(values).reshape(-1)
    return flat[np.isfinite(flat)]


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})


def fmt(value: Any, digits: int = 3) -> str:
    if value is None or value == "":
        return "NOT_AVAILABLE"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def distribution(values: np.ndarray, prefix: str) -> dict[str, Any]:
    values = finite_values(values)
    names = ("mean", "median", "std", "iqr", "p10", "p25", "p75", "p90", "min", "max", "mad")
    if not values.size:
        return {
            f"{prefix}_count": 0,
            **{f"{prefix}_{name}": None for name in names},
        }
    median = float(np.median(values))
    return {
        f"{prefix}_count": int(values.size),
        f"{prefix}_mean": float(np.mean(values)),
        f"{prefix}_median": median,
        f"{prefix}_std": float(np.std(values, ddof=0)),
        f"{prefix}_iqr": float(np.quantile(values, 0.75) - np.quantile(values, 0.25)),
        f"{prefix}_p10": float(np.quantile(values, 0.10)),
        f"{prefix}_p25": float(np.quantile(values, 0.25)),
        f"{prefix}_p75": float(np.quantile(values, 0.75)),
        f"{prefix}_p90": float(np.quantile(values, 0.90)),
        f"{prefix}_min": float(np.min(values)),
        f"{prefix}_max": float(np.max(values)),
        f"{prefix}_mad": float(np.median(np.abs(values - median))),
    }


def robust_mad(values: np.ndarray) -> float | None:
    values = finite_values(values)
    if not values.size:
        return None
    median = np.median(values)
    return float(np.median(np.abs(values - median)))


def contiguous_runs(mask: np.ndarray, time_s: np.ndarray, gap_limit_s: float) -> list[int]:
    mask = np.asarray(mask, dtype=bool).reshape(-1)
    time_s = np.asarray(time_s, dtype=float).reshape(-1)
    runs: list[int] = []
    current = 0
    for index, good in enumerate(mask):
        if not good:
            if current:
                runs.append(current)
            current = 0
            continue
        if index == 0 or not mask[index - 1] or not np.isfinite(time_s[index - 1]):
            if current:
                runs.append(current)
            current = 1
            continue
        if time_s[index] - time_s[index - 1] > gap_limit_s:
            if current:
                runs.append(current)
            current = 1
        else:
            current += 1
    if current:
        runs.append(current)
    return runs


def internal_false_runs(mask: np.ndarray, time_s: np.ndarray, gap_limit_s: float) -> list[int]:
    mask = np.asarray(mask, dtype=bool).reshape(-1)
    time_s = np.asarray(time_s, dtype=float).reshape(-1)
    good_indices = np.flatnonzero(mask)
    if good_indices.size < 2:
        return []
    gaps: list[int] = []
    for left, right in zip(good_indices[:-1], good_indices[1:]):
        if right - left > 1 or time_s[right] - time_s[left] > gap_limit_s * 1.5:
            gaps.append(int(right - left - 1))
    return gaps


def derivative_stats(
    values: np.ndarray,
    time_s: np.ndarray,
    valid: np.ndarray,
    gap_limit_s: float,
    prefix: str,
) -> dict[str, Any]:
    values = np.asarray(values, dtype=float).reshape(-1)
    time_s = np.asarray(time_s, dtype=float).reshape(-1)
    valid = np.asarray(valid, dtype=bool).reshape(-1)
    if values.size < 2:
        return {
            f"{prefix}_diff_count": 0,
            f"{prefix}_diff_median_abs": None,
            f"{prefix}_diff_mad": None,
        }
    adjacent = valid[:-1] & valid[1:]
    dt = np.diff(time_s)
    adjacent &= np.isfinite(dt) & (dt > 0) & (dt <= gap_limit_s)
    adjacent &= np.isfinite(values[:-1]) & np.isfinite(values[1:])
    derivative = np.diff(values)[adjacent] / dt[adjacent]
    if not derivative.size:
        return {
            f"{prefix}_diff_count": 0,
            f"{prefix}_diff_median_abs": None,
            f"{prefix}_diff_mad": None,
        }
    return {
        f"{prefix}_diff_count": int(derivative.size),
        f"{prefix}_diff_median_abs": float(np.median(np.abs(derivative))),
        f"{prefix}_diff_mad": robust_mad(derivative),
    }


class Hdf5MatFile:
    """Small read-only HDF5 reader for numeric MATLAB 7.3 MAT datasets."""

    _loaded = False
    _lib: Any = None
    _ll = __import__("ctypes").c_longlong
    _sz = __import__("ctypes").c_ulonglong

    @classmethod
    def _load(cls) -> None:
        if cls._loaded:
            return
        import ctypes

        if not MATLAB_HDF5_DLL.is_file():
            raise RuntimeError(f"Existing HDF5 DLL not found: {MATLAB_HDF5_DLL}")
        os.add_dll_directory(str(MATLAB_HDF5_DLL.parent))
        cls._lib = ctypes.WinDLL(str(MATLAB_HDF5_DLL))
        ll = cls._ll
        sz = cls._sz
        specs = {
            "H5open": ([], ctypes.c_int),
            "H5Fopen": ([ctypes.c_char_p, ctypes.c_uint, ll], ll),
            "H5Fclose": ([ll], ctypes.c_int),
            "H5Gopen2": ([ll, ctypes.c_char_p, ctypes.c_uint], ll),
            "H5Gclose": ([ll], ctypes.c_int),
            "H5Literate2": (
                [ll, ctypes.c_int, ctypes.c_int, ctypes.POINTER(sz), ctypes.c_void_p, ctypes.c_void_p],
                ctypes.c_int,
            ),
            "H5Dopen2": ([ll, ctypes.c_char_p, ctypes.c_uint], ll),
            "H5Dclose": ([ll], ctypes.c_int),
            "H5Dget_space": ([ll], ll),
            "H5Sclose": ([ll], ctypes.c_int),
            "H5Sselect_all": ([ll], ctypes.c_int),
            "H5Sget_simple_extent_ndims": ([ll], ctypes.c_int),
            "H5Sget_simple_extent_dims": (
                [ll, ctypes.POINTER(sz), ctypes.POINTER(sz)],
                ctypes.c_int,
            ),
            "H5Dget_type": ([ll], ll),
            "H5Tget_class": ([ll], ctypes.c_int),
            "H5Tget_size": ([ll], sz),
            "H5Tget_order": ([ll], ctypes.c_int),
            "H5Tget_sign": ([ll], ctypes.c_int),
            "H5Dread": ([ll, ll, ll, ll, ll, ctypes.c_void_p], ctypes.c_int),
            "H5Tclose": ([ll], ctypes.c_int),
        }
        for name, (argtypes, restype) in specs.items():
            function = getattr(cls._lib, name)
            function.argtypes = argtypes
            function.restype = restype
        cls._lib.H5open()
        cls._loaded = True

    def __init__(self, path: Path):
        import ctypes

        self._load()
        self.path = path
        self.fid = self._lib.H5Fopen(str(path).encode(), 0, 0)
        if self.fid < 0:
            raise RuntimeError(f"HDF5 MAT open failed: {path}")
        self._callback_type = ctypes.CFUNCTYPE(
            ctypes.c_int, self._ll, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p
        )

    def close(self) -> None:
        if self.fid >= 0:
            self._lib.H5Fclose(self.fid)
            self.fid = -1

    def __enter__(self) -> "Hdf5MatFile":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def links(self) -> list[str]:
        import ctypes

        group = self._lib.H5Gopen2(self.fid, b"/", 0)
        names: list[str] = []
        index = self._sz(0)

        @self._callback_type
        def callback(_group: int, name: bytes, _info: int, _data: int) -> int:
            names.append(name.decode("utf-8", "replace"))
            return 0

        self._lib.H5Literate2(group, 0, 0, ctypes.byref(index), callback, None)
        self._lib.H5Gclose(group)
        return names

    def read(self, name: str) -> tuple[np.ndarray, dict[str, Any]]:
        import ctypes

        dataset = self._lib.H5Dopen2(self.fid, name.encode(), 0)
        if dataset < 0:
            raise KeyError(f"Dataset {name!r} not found in {self.path}")
        space = self._lib.H5Dget_space(dataset)
        ndims = int(self._lib.H5Sget_simple_extent_ndims(space))
        dims = (self._sz * max(ndims, 1))()
        max_dims = (self._sz * max(ndims, 1))()
        self._lib.H5Sget_simple_extent_dims(space, dims, max_dims)
        shape = tuple(int(dims[index]) for index in range(ndims))
        dtype_id = self._lib.H5Dget_type(dataset)
        type_class = int(self._lib.H5Tget_class(dtype_id))
        type_size = int(self._lib.H5Tget_size(dtype_id))
        type_order = int(self._lib.H5Tget_order(dtype_id))
        type_sign = int(self._lib.H5Tget_sign(dtype_id))
        count = int(np.prod(shape, dtype=np.int64))
        buffer = (ctypes.c_ubyte * (count * type_size))()
        self._lib.H5Sselect_all(space)
        status = int(
            self._lib.H5Dread(
                dataset,
                dtype_id,
                space,
                space,
                0,
                ctypes.cast(buffer, ctypes.c_void_p),
            )
        )
        if status < 0:
            self._lib.H5Tclose(dtype_id)
            self._lib.H5Sclose(space)
            self._lib.H5Dclose(dataset)
            raise RuntimeError(f"HDF5 dataset read failed: {self.path}:{name}")
        byte_order = ">" if type_order == 1 else "<"
        if type_class == 0:
            if type_size == 4:
                dtype = np.dtype(f"{byte_order}{'u' if type_sign == 0 else 'i'}4")
            elif type_size == 8:
                dtype = np.dtype(f"{byte_order}{'u' if type_sign == 0 else 'i'}8")
            else:
                dtype = np.dtype(f"V{type_size}")
        elif type_class == 1:
            dtype = np.dtype(f"{byte_order}f{type_size}")
        else:
            dtype = np.dtype(f"V{type_size}")
        array = np.frombuffer(buffer, dtype=dtype).copy().reshape(shape, order="C")
        self._lib.H5Tclose(dtype_id)
        self._lib.H5Sclose(space)
        self._lib.H5Dclose(dataset)
        return array, {
            "shape": list(shape),
            "dtype": str(dtype),
            "hdf5_type_class": type_class,
            "hdf5_type_size": type_size,
            "hdf5_type_order": type_order,
            "hdf5_type_sign": type_sign,
        }


def mat_fields(
    path: Path, names: Iterable[str]
) -> tuple[dict[str, np.ndarray], dict[str, dict[str, Any]], list[str]]:
    arrays: dict[str, np.ndarray] = {}
    info: dict[str, dict[str, Any]] = {}
    with Hdf5MatFile(path) as mat:
        available = mat.links()
        for name in names:
            if name in available:
                arrays[name], info[name] = mat.read(name)
    return arrays, info, available


def file_record(path: Path, *, hash_file: bool = True) -> dict[str, Any]:
    record: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
    if path.is_file():
        stat = path.stat()
        record.update({"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})
        if hash_file:
            record["sha256"] = sha256_file(path)
    return record


def parse_crc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    tests = re.search(r"^\s*(\d+)\s+\|", text, re.MULTILINE)
    success = re.search(r"\|\s*(\d+)\s+\|", text)
    rate = re.search(r"\|\s*([0-9.]+)\s*$", text, re.MULTILINE)
    return {
        "crc_path": str(path),
        "crc_file_available": path.is_file(),
        "crc_tests": int(tests.group(1)) if tests else None,
        "crc_success": int(success.group(1)) if success else None,
        "crc_success_rate": float(rate.group(1)) if rate else None,
    }


def tracking_metrics(
    scene_id: str,
    weather: str,
    channel: int,
    expected_prn: str,
    tracking_path: Path,
    fs: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, np.ndarray]]:
    names = [
        "PRN",
        "PRN_start_sample_count",
        "CN0_SNV_dB_Hz",
        "carrier_doppler_hz",
        "carrier_doppler_rate_hz",
        "code_freq_chips",
        "code_freq_rate_chips",
        "carrier_lock_test",
        "Prompt_I",
        "Prompt_Q",
        "code_error_chips",
        "code_error_filt_chips",
        "carr_error_hz",
        "carr_error_filt_hz",
    ]
    arrays, info, available = mat_fields(tracking_path, names)
    required = ["PRN", "PRN_start_sample_count", "CN0_SNV_dB_Hz"]
    missing = [name for name in required if name not in arrays]
    if missing:
        raise RuntimeError(f"Tracking MAT missing required fields {missing}: {tracking_path}")
    prn = np.asarray(arrays["PRN"]).reshape(-1).astype(float)
    sample = np.asarray(arrays["PRN_start_sample_count"]).reshape(-1).astype(float)
    cn0 = np.asarray(arrays["CN0_SNV_dB_Hz"]).reshape(-1).astype(float)
    doppler = np.asarray(
        arrays.get("carrier_doppler_hz", np.full_like(cn0, np.nan))
    ).reshape(-1).astype(float)
    code_freq = np.asarray(
        arrays.get("code_freq_chips", np.full_like(cn0, np.nan))
    ).reshape(-1).astype(float)
    lock = np.asarray(
        arrays.get("carrier_lock_test", np.full_like(cn0, np.nan))
    ).reshape(-1).astype(float)
    count = min(len(prn), len(sample), len(cn0), len(doppler), len(code_freq), len(lock))
    prn, sample, cn0, doppler, code_freq, lock = [
        value[:count] for value in (prn, sample, cn0, doppler, code_freq, lock)
    ]
    actual_prns = sorted({int(value) for value in prn[np.isfinite(prn)]})
    actual_prn_label = (
        f"G{actual_prns[0]:02d}"
        if len(actual_prns) == 1
        else ";".join(f"G{x:02d}" for x in actual_prns)
    )
    expected_number = int(expected_prn[1:])
    mapping_status = "PASS" if actual_prns == [expected_number] else "FAIL"
    time_s = sample / float(fs)
    observation_valid = (
        np.isfinite(sample)
        & (prn == expected_number)
        & np.isfinite(cn0)
        & (cn0 > 0)
    )
    finite_lock = observation_valid & np.isfinite(lock)
    lock_good = finite_lock & (lock >= LOCK_THRESHOLD)
    valid_times = time_s[observation_valid]
    median_dt = (
        float(np.median(np.diff(valid_times))) if valid_times.size > 1 else None
    )
    gap_limit = float(median_dt * 2.5) if median_dt and median_dt > 0 else 0.0025
    runs = contiguous_runs(lock_good, time_s, gap_limit)
    internal_gaps = internal_false_runs(lock_good, time_s, gap_limit)
    cn0_stats = distribution(cn0[observation_valid], "cn0_db_hz")
    doppler_valid = observation_valid & np.isfinite(doppler)
    code_valid = observation_valid & np.isfinite(code_freq)
    doppler_stats = distribution(doppler[doppler_valid], "doppler_hz")
    code_stats = distribution(code_freq[code_valid], "code_frequency_chips")
    doppler_stats.update(
        derivative_stats(doppler, time_s, doppler_valid, gap_limit, "doppler")
    )
    code_stats.update(
        derivative_stats(code_freq, time_s, code_valid, gap_limit, "code_frequency")
    )
    row: dict[str, Any] = {
        "scene_id": scene_id,
        "weather_condition": weather,
        "tracking_channel": channel,
        "expected_prn": expected_prn,
        "actual_prn": actual_prn_label,
        "mapping_status": mapping_status,
        "tracking_path": str(tracking_path),
        "tracking_mat_fields": ";".join(available),
        "tracking_record_count": count,
        "tracking_observation_valid_count": int(observation_valid.sum()),
        "tracking_observation_valid_fraction": (
            float(observation_valid.mean()) if count else None
        ),
        "first_valid_tracking_time_s": (
            float(valid_times[0]) if valid_times.size else None
        ),
        "last_valid_tracking_time_s": (
            float(valid_times[-1]) if valid_times.size else None
        ),
        "valid_tracking_duration_s": (
            float(valid_times[-1] - valid_times[0]) if valid_times.size > 1 else None
        ),
        "sample_interval_median_s": median_dt,
        "continuity_gap_limit_s": gap_limit,
        "carrier_lock_threshold": LOCK_THRESHOLD,
        "carrier_lock_observed_count": int(finite_lock.sum()),
        "carrier_lock_observed_fraction": (
            float(finite_lock.sum() / observation_valid.sum())
            if observation_valid.sum()
            else None
        ),
        "carrier_lock_good_count": int(lock_good.sum()),
        "carrier_lock_good_fraction_of_valid": (
            float(lock_good.sum() / observation_valid.sum())
            if observation_valid.sum()
            else None
        ),
        "lock_continuous_segment_count": len(runs),
        "lock_longest_segment_samples": max(runs) if runs else 0,
        "lock_median_segment_samples": float(np.median(runs)) if runs else None,
        "lock_longest_segment_s": (
            float(max(runs) * median_dt) if runs and median_dt else None
        ),
        "lock_internal_interruption_count": len(internal_gaps),
        "lock_reacquisition_like_gap_observed": bool(internal_gaps),
    }
    row.update(cn0_stats)
    row.update(doppler_stats)
    row.update(code_stats)
    fields: list[dict[str, Any]] = []
    field_defs = [
        ("PRN", "integer", "GPS PRN identifier", "actual mapping verification", "mapping"),
        (
            "PRN_start_sample_count",
            "samples",
            "tracking record sample counter",
            "recording-relative time = sample/fs",
            "time",
        ),
        (
            "CN0_SNV_dB_Hz",
            "dB-Hz",
            "signal-to-noise density estimate",
            "C/N0 receiver diagnostic",
            "C/N0",
        ),
        (
            "carrier_doppler_hz",
            "Hz",
            "carrier Doppler estimate",
            "receiver tracking diagnostic; signed",
            "Doppler",
        ),
        (
            "carrier_doppler_rate_hz",
            "artifact field unit",
            "carrier Doppler rate field",
            "present but all-zero in inspected mapped files",
            "not used",
        ),
        (
            "code_freq_chips",
            "chips/s as named by artifact",
            "code frequency field",
            "receiver code tracking diagnostic",
            "code frequency",
        ),
        (
            "code_freq_rate_chips",
            "artifact field unit",
            "code frequency rate field",
            "present but all-zero in inspected mapped files",
            "not used",
        ),
        (
            "carrier_lock_test",
            "dimensionless",
            "carrier lock test",
            f"lock-good operational threshold >= {LOCK_THRESHOLD} from run_nav_sage_pipeline.m",
            "lock continuity",
        ),
        (
            "Prompt_I",
            "artifact units",
            "prompt in-phase correlator output",
            "available receiver correlator diagnostic; not used for weather conclusion",
            "not used",
        ),
        (
            "Prompt_Q",
            "artifact units",
            "prompt quadrature correlator output",
            "available receiver correlator diagnostic; not used for weather conclusion",
            "not used",
        ),
        (
            "code_error_chips",
            "chips",
            "code tracking error",
            "available receiver tracking diagnostic; not used for weather conclusion",
            "not used",
        ),
    ]
    for name, unit, interpretation, use, category in field_defs:
        field_info = info.get(name)
        fields.append(
            {
                "scene_id": scene_id,
                "weather_condition": weather,
                "tracking_channel": channel,
                "source_category": "tracking_mat",
                "source_path": str(tracking_path),
                "variable_name": name,
                "available": name in arrays,
                "dtype": field_info.get("dtype") if field_info else None,
                "shape": json.dumps(field_info.get("shape")) if field_info else None,
                "unit": unit,
                "interpretation": interpretation,
                "used_in_metrics": category,
                "missing_reason": None if name in arrays else "field_not_present",
            }
        )
    arrays["sample_time_s"] = time_s
    arrays["observation_valid"] = observation_valid
    arrays["lock_good"] = lock_good
    arrays["cn0"] = cn0
    return row, fields, arrays


def telemetry_metrics(
    scene_id: str, weather: str, channel: int, telemetry_path: Path, crc_path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    names = [
        "PRN",
        "TOW_at_Preamble_ms",
        "TOW_at_current_symbol_ms",
        "nav_symbol",
        "tracking_sample_counter",
    ]
    arrays, info, _available = mat_fields(telemetry_path, names)
    row: dict[str, Any] = {
        "scene_id": scene_id,
        "weather_condition": weather,
        "tracking_channel": channel,
        "telemetry_path": str(telemetry_path),
        "telemetry_dat_path": str(telemetry_path.with_suffix(".dat")),
        "telemetry_record_count": 0,
        "valid_nav_symbol_count": 0,
        "telemetry_tow_start_source_units": None,
        "telemetry_tow_end_source_units": None,
        "telemetry_tow_span_source_units": None,
        **parse_crc(crc_path),
    }
    if "nav_symbol" in arrays:
        nav = np.asarray(arrays["nav_symbol"]).reshape(-1)
        finite_nav = nav[np.isfinite(nav)]
        row["telemetry_record_count"] = int(len(nav))
        row["valid_nav_symbol_count"] = int(np.isin(finite_nav, [-1, 1]).sum())
        row["nav_symbol_unique"] = ";".join(str(int(x)) for x in np.unique(finite_nav))
    tow = np.asarray(
        arrays.get("TOW_at_current_symbol_ms", np.array([]))
    ).reshape(-1).astype(float)
    tow = tow[np.isfinite(tow)]
    if tow.size:
        row.update(
            {
                "telemetry_tow_start_source_units": float(tow[0]),
                "telemetry_tow_end_source_units": float(tow[-1]),
                "telemetry_tow_span_source_units": float(tow[-1] - tow[0]),
                "telemetry_tow_unit_note": (
                    "source variable is named *_ms; stored values and existing "
                    "metadata use second-like TOW values; no rescaling applied"
                ),
            }
        )
    fields: list[dict[str, Any]] = []
    defs = [
        ("PRN", "integer", "GPS PRN identifier", "mapping cross-check"),
        (
            "tracking_sample_counter",
            "samples",
            "tracking/telemetry sample alignment",
            "continuity provenance",
        ),
        (
            "TOW_at_Preamble_ms",
            "source field unit",
            "navigation message preamble timing",
            "telemetry provenance",
        ),
        (
            "TOW_at_current_symbol_ms",
            "source field unit",
            "current telemetry symbol timing",
            "telemetry span",
        ),
        (
            "nav_symbol",
            "symbol value",
            "decoded navigation symbol; observed values are +/-1",
            "NAV availability",
        ),
    ]
    for name, unit, interpretation, use in defs:
        entry = info.get(name)
        fields.append(
            {
                "scene_id": scene_id,
                "weather_condition": weather,
                "tracking_channel": channel,
                "source_category": "telemetry_mat",
                "source_path": str(telemetry_path),
                "variable_name": name,
                "available": name in arrays,
                "dtype": entry.get("dtype") if entry else None,
                "shape": json.dumps(entry.get("shape")) if entry else None,
                "unit": unit,
                "interpretation": interpretation,
                "used_in_metrics": use,
                "missing_reason": None if name in arrays else "field_not_present",
            }
        )
    fields.append(
        {
            "scene_id": scene_id,
            "weather_condition": weather,
            "tracking_channel": channel,
            "source_category": "telemetry_crc_text",
            "source_path": str(crc_path),
            "variable_name": "CRC tests/success/rate",
            "available": crc_path.is_file(),
            "dtype": "text",
            "shape": None,
            "unit": "count/rate",
            "interpretation": "GNSS-SDR telemetry decoder CRC diagnostic",
            "used_in_metrics": "telemetry summary",
            "missing_reason": None if crc_path.is_file() else "file_not_present",
        }
    )
    return row, fields


def observables_metrics(
    scene_id: str, weather: str, path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    names = [
        "PRN",
        "RX_time",
        "TOW_at_current_symbol_s",
        "Carrier_Doppler_hz",
        "Flag_valid_pseudorange",
    ]
    arrays, info, _available = mat_fields(path, names)
    prn = np.asarray(arrays.get("PRN", np.array([]))).astype(float)
    flags = np.asarray(
        arrays.get("Flag_valid_pseudorange", np.zeros_like(prn))
    ).astype(float)
    positive_prn = prn.reshape(-1)[prn.reshape(-1) > 0].astype(int)
    row = {
        "scene_id": scene_id,
        "weather_condition": weather,
        "observables_path": str(path),
        "observables_available": path.is_file(),
        "observables_row_count": int(prn.shape[0]) if prn.ndim == 2 else 0,
        "observables_column_count": int(prn.shape[1]) if prn.ndim == 2 else 0,
        "observables_nonzero_prn_cells": int(np.count_nonzero(prn)),
        "observables_valid_pseudorange_cells": int(np.count_nonzero(flags > 0)),
        "observables_unique_prns": ";".join(
            f"G{x:02d}" for x in sorted(set(positive_prn))
        ),
    }
    fields = []
    for name, unit, interpretation in [
        ("PRN", "integer", "observable satellite identifier"),
        ("RX_time", "source field unit", "receiver observation time"),
        ("TOW_at_current_symbol_s", "s", "TOW associated with observable"),
        ("Carrier_Doppler_hz", "Hz", "observable Doppler diagnostic"),
        ("Flag_valid_pseudorange", "flag", "observable validity flag"),
    ]:
        entry = info.get(name)
        fields.append(
            {
                "scene_id": scene_id,
                "weather_condition": weather,
                "tracking_channel": "",
                "source_category": "observables_mat",
                "source_path": str(path),
                "variable_name": name,
                "available": name in arrays,
                "dtype": entry.get("dtype") if entry else None,
                "shape": json.dumps(entry.get("shape")) if entry else None,
                "unit": unit,
                "interpretation": interpretation,
                "used_in_metrics": "observables availability",
                "missing_reason": None if name in arrays else "field_not_present",
            }
        )
    return row, fields


def scene_metadata(scene_id: str) -> dict[str, Any]:
    scene_dir = PROJECT_ROOT / "scenes" / scene_id
    metadata_path = scene_dir / "metadata.json"
    metadata = read_json(metadata_path)
    raw = metadata.get("raw_iq", {})
    signal = metadata.get("signal", {})
    gnss = metadata.get("gnss_sdr", {})
    navigation = metadata.get("navigation", {})
    trajectory = metadata.get("trajectory", {})
    return {
        "scene_dir": scene_dir,
        "metadata_path": metadata_path,
        "metadata": metadata,
        "sample_rate_hz": signal.get("sample_rate_hz"),
        "signal_type": signal.get("signal_type"),
        "raw_path": raw.get("path"),
        "raw_exists": Path(raw.get("path", "")).is_file(),
        "raw_size_bytes_declared": raw.get("size_bytes"),
        "raw_sha256_declared": raw.get("sha256"),
        "raw_not_opened": True,
        "estimated_duration_s": metadata.get("recording_duration_estimate_s"),
        "gnss_sdr_status": gnss.get("run_status"),
        "navigation_status": navigation.get("status"),
        "navigation_path": scene_dir / "navigation" / "gps_ephemeris.xml",
        "trajectory_status": trajectory.get("status"),
        "geometry_status": metadata.get("satellite_geometry", {}).get("status"),
        "config_path": scene_dir / "gnss_sdr" / "config" / f"{scene_id}.conf",
        "metadata_hash": sha256_file(metadata_path),
    }


def make_plots(
    output: Path,
    prn_rows: list[dict[str, Any]],
    scene_rows: list[dict[str, Any]],
    g24_data: dict[str, Any],
) -> list[str]:
    figure_dir = output / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    weather_order = ["clear", "midrain", "heavyrain"]
    colors = {"clear": "#377eb8", "midrain": "#4daf4a", "heavyrain": "#e41a1c"}

    scene_counts = {
        row["weather_condition"]: row["tracked_prn_count"] for row in scene_rows
    }
    fig, ax = plt.subplots(figsize=(6.0, 3.5))
    ax.bar(
        weather_order,
        [scene_counts.get(x, 0) for x in weather_order],
        color=[colors[x] for x in weather_order],
    )
    ax.set_ylabel("Tracked PRN count")
    ax.set_xlabel("Weather condition")
    ax.set_title("GNSS-SDR tracked PRNs by recording")
    fig.tight_layout()
    path = figure_dir / "tracked_prn_count.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    created.append(str(path))

    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    for weather in weather_order:
        subset = [row for row in prn_rows if row["weather_condition"] == weather]
        if not subset:
            continue
        labels = [row["expected_prn"] for row in subset]
        values = [row.get("cn0_db_hz_median") or np.nan for row in subset]
        ax.bar(labels, values, alpha=0.75, label=weather, color=colors[weather])
    ax.set_ylabel("Median C/N0 (dB-Hz)")
    ax.set_xlabel("Tracked PRN")
    ax.set_title("Per-PRN median receiver C/N0")
    ax.legend(frameon=False)
    fig.tight_layout()
    path = figure_dir / "median_cn0_by_prn.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    created.append(str(path))

    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    for weather in ["clear", "midrain"]:
        data = g24_data.get(weather)
        if data is None:
            continue
        time_s = data["time_s"] - data["time_s"][0]
        cn0 = data["cn0"]
        stride = max(1, len(time_s) // 3000)
        ax.plot(
            time_s[::stride],
            cn0[::stride],
            linewidth=0.6,
            label=f"G24 {weather}",
            color=colors[weather],
        )
    ax.set_xlabel("Relative tracking time (s; recordings not synchronized)")
    ax.set_ylabel("C/N0 (dB-Hz)")
    ax.set_title("Matched G24 receiver C/N0 traces")
    ax.legend(frameon=False)
    fig.tight_layout()
    path = figure_dir / "g24_matched_cn0_time.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    created.append(str(path))

    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    labels = [
        f"{row['expected_prn']}\n{row['weather_condition']}" for row in prn_rows
    ]
    values = [
        row.get("carrier_lock_good_fraction_of_valid") or np.nan for row in prn_rows
    ]
    ax.bar(
        labels,
        values,
        color=[colors[row["weather_condition"]] for row in prn_rows],
    )
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Lock-good fraction of valid tracking rows")
    ax.set_title("Operational carrier-lock continuity diagnostic")
    fig.tight_layout()
    path = figure_dir / "lock_continuity.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    created.append(str(path))
    return created


def build_report(
    output: Path,
    provenance: dict[str, Any],
    scene_rows: list[dict[str, Any]],
    prn_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    figures: list[str],
) -> None:
    lines = [
        "# GNSS-SDR Weather-Effect MVP (Read-Only)",
        "",
        f"Generated UTC: {provenance['generated_utc']}",
        "",
        "## Scope and controls",
        "",
        "This is a receiver-level, read-only audit of existing GNSS-SDR tracking, telemetry, observables, configuration, metadata, and navigation XML artifacts. It does not claim a rain attenuation law or a multipath/SAGE result.",
        "",
        "- Raw IQ content opened: **NO**; raw paths were checked only from metadata and no raw hash was recomputed.",
        "- MATLAB executable invoked: **NO**; the existing MATLAB HDF5 DLL was used through ctypes only to read v7.3 MAT datasets.",
        "- GNSS-SDR rerun: **NO**.",
        "- SAGE/MATLAB production: **NO**.",
        "- Geometry/PVT/NMEA: not required for this MVP and not used.",
        "- No VTC or Paper handoff was modified.",
        "",
        "The requested historical production-source hash was 95f608...; the actual source at task start and end is recorded in provenance.json. It was already different before this task and was not modified.",
        "",
        "## Dataset and matched-comparison limits",
        "",
        "The three recordings contain 4, 2, and 3 tracked PRNs respectively. The only same-PRN cross-weather pair is G24 (clear/ch10 versus midrain/ch8). Heavy-rain rows are not a same-satellite matched comparison and are shown only as a scene-level receiver diagnostic.",
        "",
        "## Scene-level observations",
        "",
        "| Weather | Scene | Tracked PRNs | Estimated duration (s) | Telemetry records | Observable valid cells | Navigation XML | Geometry |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in scene_rows:
        values = {
            key: fmt(row.get(key))
            for key in [
                "weather_condition",
                "scene_id",
                "tracked_prn_count",
                "estimated_duration_s",
                "telemetry_total_records",
                "observables_valid_pseudorange_cells",
                "navigation_status",
                "geometry_status",
            ]
        }
        lines.append(
            "| {weather_condition} | {scene_id} | {tracked_prn_count} | "
            "{estimated_duration_s} | {telemetry_total_records} | "
            "{observables_valid_pseudorange_cells} | {navigation_status} | "
            "{geometry_status} |".format(**values)
        )
    lines += [
        "",
        "## Per-PRN receiver diagnostics",
        "",
        "The C/N0 values below are the actual CN0_SNV_dB_Hz tracking field. Lock-good uses the existing pipeline operational threshold carrier_lock_test >= -0.5; this is a continuity diagnostic, not a weather classifier. Doppler and code-frequency statistics retain their signed/source units.",
        "",
        "| Weather | PRN | Channel | Mapping | Valid fraction | C/N0 median (dB-Hz) | C/N0 IQR | Lock-good fraction | Longest lock (s) | Doppler IQR (Hz) | Code-frequency IQR (chips/s) | Internal gaps |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in prn_rows:
        values = {
            key: fmt(row.get(key))
            for key in [
                "weather_condition",
                "expected_prn",
                "tracking_channel",
                "mapping_status",
                "tracking_observation_valid_fraction",
                "cn0_db_hz_median",
                "cn0_db_hz_iqr",
                "carrier_lock_good_fraction_of_valid",
                "lock_longest_segment_s",
                "doppler_hz_iqr",
                "code_frequency_chips_iqr",
                "lock_internal_interruption_count",
            ]
        }
        lines.append(
            "| {weather_condition} | {expected_prn} | {tracking_channel} | "
            "{mapping_status} | {tracking_observation_valid_fraction} | "
            "{cn0_db_hz_median} | {cn0_db_hz_iqr} | "
            "{carrier_lock_good_fraction_of_valid} | {lock_longest_segment_s} | "
            "{doppler_hz_iqr} | {code_frequency_chips_iqr} | "
            "{lock_internal_interruption_count} |".format(**values)
        )
    lines += [
        "",
        "## G24 matched pair",
        "",
        "The comparison is between two different recordings and is aligned only by recording-relative tracking time. The delta is midrain minus clear; it is an observed receiver C/N0 difference for the matched G24 recordings, not a direct estimate of rain attenuation.",
        "",
        "| Metric | Clear G24/ch10 | Midrain G24/ch8 | Midrain - clear | Unit |",
        "|---|---:|---:|---:|---|",
    ]
    for row in comparison_rows:
        lines.append(
            f"| {row['metric']} | {fmt(row.get('clear_value'))} | "
            f"{fmt(row.get('midrain_value'))} | "
            f"{fmt(row.get('delta_midrain_minus_clear'))} | {row.get('unit', '')} |"
        )
    lines += [
        "",
        "## Interpretation boundary",
        "",
        "### Direct observations",
        "",
        "- The tracking artifacts expose per-record PRN, sample counter, C/N0, signed carrier Doppler, code frequency, carrier lock test, prompt I/Q, and tracking-error fields.",
        "- The telemetry artifacts expose decoded navigation symbols, TOW fields, and tracking sample counters; CRC text files expose decoder test/success counts.",
        "- The observables MAT files are present and contain PRN, receiver time, TOW, carrier Doppler, and pseudorange-validity fields.",
        "- No PVT/NMEA/trajectory or satellite geometry is available in these standardized rain-MVP scene directories.",
        "",
        "### Supported receiver-level inference",
        "",
        "The artifacts support a descriptive comparison of tracked-PRN count, C/N0 distributions, lock continuity, Doppler variability, code-frequency variability, telemetry decoder diagnostics, and matched G24 receiver traces. Differences should be interpreted as recording-level receiver diagnostics under the listed weather labels.",
        "",
        "### Not proven by this MVP",
        "",
        "- It does not prove monotonic clear-to-rain degradation.",
        "- It does not prove direct rain attenuation, propagation loss, or a weather-conditioned multipath law.",
        "- It does not provide elevation/azimuth conditioning or same-satellite heavy-rain evidence.",
        "- It does not establish a statistical channel model and does not replace full NAV-aided SAGE production.",
        "",
        "## Figures",
        "",
    ]
    lines.extend(f"- {Path(path).relative_to(output)}" for path in figures)
    lines += [
        "",
        "## Provenance",
        "",
        "All source files, hashes, declared raw metadata, actual MAT field names, and read-only controls are recorded in provenance.json and gnss_sdr_field_inventory.csv.",
        "",
        "## Meeting takeaway",
        "",
        "This MVP is suitable for a receiver-level weather-effect discussion based on existing GNSS-SDR outputs, with G24 as the only matched cross-weather PRN. It should be presented as descriptive evidence and not as a completed rain-channel or multipath model.",
    ]
    (output / "gnss_sdr_weather_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    tracked_text = ", ".join(
        f"{row['weather_condition']}:{row['tracked_prn_count']}" for row in scene_rows
    )
    g24_summary = next(
        (row for row in comparison_rows if row["metric"] == "cn0_db_hz_median"),
        {},
    )
    meeting = [
        "# Tomorrow Meeting: GNSS-SDR Weather MVP",
        "",
        "## Decision-safe summary",
        "",
        f"- TRACKED_PRN_COUNT = {tracked_text}",
        "- CN0_WEATHER_RESULT = descriptive per-PRN receiver distributions; no monotonic weather conclusion",
        f"- G24_MATCHED_RESULT = {g24_summary.get('clear_value', 'NOT_AVAILABLE')} dB-Hz clear, {g24_summary.get('midrain_value', 'NOT_AVAILABLE')} dB-Hz midrain, delta is observed receiver difference",
        "- LOCK_CONTINUITY_RESULT = operational carrier-lock continuity metrics are available per mapped PRN; internal gaps are diagnostics, not confirmed reacquisition events",
        "- DOPPLER_STABILITY_RESULT = signed Doppler and robust first-difference distributions are available; they are not rain-specific propagation estimates",
        "- TELEMETRY_RESULT = telemetry MAT and CRC diagnostics are available for mapped channels; navigation XML is present, while PVT/NMEA/geometry are unavailable",
        "- OVERALL_RECEIVER_LEVEL_EVIDENCE = READ_ONLY_DESCRIPTIVE_MVP_READY",
        "",
        "## Five points to say",
        "",
        "1. Existing GNSS-SDR outputs can support a receiver-level comparison without reopening the raw IQ.",
        "2. G24 is the only same-PRN clear/midrain matched pair; heavy-rain observations are not same-satellite matched evidence.",
        "3. C/N0, lock continuity, Doppler, code frequency, telemetry, and observables are reported from actual fields.",
        "4. No direct rain attenuation or monotonic degradation claim is made.",
        "5. This MVP does not alter or replace the validated full-SAGE production route.",
        "",
        "## Controls",
        "",
        "- raw IQ read: no",
        "- MATLAB executable: no",
        "- GNSS-SDR rerun: no",
        "- SAGE: no",
        "- VTC/Paper handoff: unchanged",
    ]
    (output / "TOMORROW_MEETING_GNSS_SDR_MVP.md").write_text(
        "\n".join(meeting) + "\n", encoding="utf-8"
    )


def run(output: Path) -> int:
    if output.exists():
        raise RuntimeError(f"Output namespace already exists; refusing overwrite: {output}")
    output.mkdir(parents=True)
    source_hash_before = sha256_file(PRODUCTION_SOURCE)
    generated = utc_now()
    scene_rows: list[dict[str, Any]] = []
    prn_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    source_files: dict[str, dict[str, Any]] = {}
    g24_data: dict[str, dict[str, np.ndarray]] = {}

    for scene_id, mapping in EXPECTED_MAPPINGS.items():
        metadata = scene_metadata(scene_id)
        weather = metadata["metadata"].get("weather_condition", scene_id)
        scene_dir: Path = metadata["scene_dir"]
        config_path: Path = metadata["config_path"]
        nav_path: Path = metadata["navigation_path"]
        obs_path = (
            scene_dir / "gnss_sdr" / "observables" / f"{scene_id}_observables.mat"
        )
        obs_scene_row, obs_field_rows = observables_metrics(scene_id, weather, obs_path)
        field_rows.extend(obs_field_rows)
        telemetry_total = 0
        telemetry_channels = 0
        crc_rates: list[float] = []
        actual_prn_labels: list[str] = []
        task_rows: list[dict[str, Any]] = []
        for channel, expected_prn in mapping.items():
            tracking_path = (
                scene_dir / "gnss_sdr" / "tracking" / f"{scene_id}_track_ch_{channel}.mat"
            )
            telemetry_path = (
                scene_dir / "gnss_sdr" / "telemetry" / f"{scene_id}_telemetry_ch_{channel}.mat"
            )
            crc_path = (
                scene_dir / "gnss_sdr" / "telemetry" / f"{scene_id}_crc_stats_ch{channel}.txt"
            )
            tracking_row, tracking_fields, arrays = tracking_metrics(
                scene_id, weather, channel, expected_prn, tracking_path, EXPECTED_SAMPLE_RATE
            )
            telemetry_row, telemetry_fields = telemetry_metrics(
                scene_id, weather, channel, telemetry_path, crc_path
            )
            tracking_dat_path = tracking_path.with_suffix(".dat")
            telemetry_dat_path = telemetry_path.with_suffix(".dat")
            tracking_row.update(
                {
                    "tracking_dat_path": str(tracking_dat_path),
                    "tracking_dat_exists": tracking_dat_path.is_file(),
                    "tracking_dat_size_bytes": tracking_dat_path.stat().st_size
                    if tracking_dat_path.is_file()
                    else None,
                }
            )
            telemetry_row.update(
                {
                    "telemetry_dat_exists": telemetry_dat_path.is_file(),
                    "telemetry_dat_size_bytes": telemetry_dat_path.stat().st_size
                    if telemetry_dat_path.is_file()
                    else None,
                }
            )
            prn_rows.append(tracking_row)
            task_rows.append(tracking_row)
            field_rows.extend(tracking_fields)
            field_rows.extend(telemetry_fields)
            telemetry_total += int(telemetry_row.get("telemetry_record_count") or 0)
            telemetry_channels += int(bool(telemetry_row.get("telemetry_record_count")))
            if telemetry_row.get("crc_success_rate") is not None:
                crc_rates.append(float(telemetry_row["crc_success_rate"]))
            actual_prn_labels.append(str(tracking_row["actual_prn"]))
            if expected_prn == "G24":
                valid = arrays["observation_valid"]
                g24_data[weather] = {
                    "time_s": arrays["sample_time_s"][valid],
                    "cn0": arrays["cn0"][valid],
                }
            for source_path in [tracking_path, tracking_dat_path, telemetry_path, telemetry_dat_path, crc_path]:
                source_files[str(source_path)] = file_record(source_path)
        scene_rows.append(
            {
                "scene_id": scene_id,
                "weather_condition": weather,
                "sample_rate_hz": metadata["sample_rate_hz"],
                "signal_type": metadata["signal_type"],
                "raw_path": metadata["raw_path"],
                "raw_exists": metadata["raw_exists"],
                "raw_size_bytes_declared": metadata["raw_size_bytes_declared"],
                "raw_sha256_declared": metadata["raw_sha256_declared"],
                "raw_opened": False,
                "estimated_duration_s": metadata["estimated_duration_s"],
                "tracked_prn_count": len(mapping),
                "prn_list_expected": ";".join(mapping.values()),
                "prn_list_actual": ";".join(actual_prn_labels),
                "telemetry_channel_count": telemetry_channels,
                "telemetry_total_records": telemetry_total,
                "telemetry_crc_mean_success_rate": (
                    float(np.mean(crc_rates)) if crc_rates else None
                ),
                "observables_path": str(obs_path),
                "observables_available": obs_scene_row["observables_available"],
                "observables_row_count": obs_scene_row["observables_row_count"],
                "observables_valid_pseudorange_cells": obs_scene_row[
                    "observables_valid_pseudorange_cells"
                ],
                "navigation_path": str(nav_path),
                "navigation_status": metadata["navigation_status"],
                "trajectory_status": metadata["trajectory_status"],
                "geometry_status": metadata["geometry_status"],
                "gnss_sdr_status": metadata["gnss_sdr_status"],
                "mapping_status": (
                    "PASS"
                    if all(row["mapping_status"] == "PASS" for row in task_rows)
                    else "FAIL"
                ),
            }
        )
        for path in [metadata["metadata_path"], config_path, nav_path, obs_path]:
            source_files[str(path)] = file_record(path)

    g24_clear = next(
        (
            row
            for row in prn_rows
            if row["weather_condition"] == "clear" and row["expected_prn"] == "G24"
        ),
        None,
    )
    g24_mid = next(
        (
            row
            for row in prn_rows
            if row["weather_condition"] == "midrain" and row["expected_prn"] == "G24"
        ),
        None,
    )
    comparison_rows: list[dict[str, Any]] = []
    if g24_clear and g24_mid:
        for metric, unit in [
            ("cn0_db_hz_median", "dB-Hz"),
            ("cn0_db_hz_iqr", "dB"),
            ("carrier_lock_good_fraction_of_valid", "fraction"),
            ("doppler_hz_iqr", "Hz"),
            ("code_frequency_chips_iqr", "chips/s"),
        ]:
            left = g24_clear.get(metric)
            right = g24_mid.get(metric)
            comparison_rows.append(
                {
                    "metric": metric,
                    "clear_value": left,
                    "midrain_value": right,
                    "delta_midrain_minus_clear": (
                        right - left if left is not None and right is not None else None
                    ),
                    "unit": unit,
                }
            )

    source_files[str(PRODUCTION_SOURCE)] = file_record(PRODUCTION_SOURCE)
    source_hash_after = sha256_file(PRODUCTION_SOURCE)
    if source_hash_before != source_hash_after:
        raise RuntimeError(
            "Production source changed during read-only audit; refusing to publish report"
        )
    figures = make_plots(output, prn_rows, scene_rows, g24_data)
    provenance = {
        "generated_utc": generated,
        "completed_utc": utc_now(),
        "tool": str(Path(__file__).resolve()),
        "mode": "read_only_existing_gnss_sdr_outputs",
        "raw_iq_read": False,
        "raw_iq_processed": False,
        "matlab_executable_invoked": False,
        "gnss_sdr_rerun": False,
        "sage_executed": False,
        "vtc_paper_modified": False,
        "production_artifacts_modified": False,
        "hdf5_reader": {
            "library": str(MATLAB_HDF5_DLL),
            "library_exists": MATLAB_HDF5_DLL.is_file(),
            "matlab_executable_started": False,
        },
        "production_source_requested_sha256": REQUESTED_PRODUCTION_SOURCE_SHA256,
        "production_source_actual_sha256_before": source_hash_before,
        "production_source_actual_sha256_after": source_hash_after,
        "production_source_preexisting_mismatch": (
            source_hash_before.lower() != REQUESTED_PRODUCTION_SOURCE_SHA256.lower()
        ),
        "production_source_changed_during_task": source_hash_before != source_hash_after,
        "sample_rate_hz": EXPECTED_SAMPLE_RATE,
        "expected_mappings": EXPECTED_MAPPINGS,
        "matched_cross_weather_prns": ["G24"],
        "same_prn_all_three": [],
        "lock_definition": {
            "field": "carrier_lock_test",
            "threshold": LOCK_THRESHOLD,
            "valid_rows": "PRN match and finite CN0_SNV_dB_Hz > 0",
            "internal_gap_definition": (
                "false runs bracketed by lock-good rows or separated by continuity gap"
            ),
        },
        "source_files": source_files,
        "figures": figures,
        "output_files": [],
    }
    write_csv(output / "gnss_sdr_weather_prn_metrics.csv", prn_rows, list(prn_rows[0].keys()))
    write_csv(output / "gnss_sdr_weather_scene_metrics.csv", scene_rows, list(scene_rows[0].keys()))
    write_csv(
        output / "gnss_sdr_g24_matched_comparison.csv",
        comparison_rows,
        ["metric", "clear_value", "midrain_value", "delta_midrain_minus_clear", "unit"],
    )
    write_csv(
        output / "gnss_sdr_field_inventory.csv",
        field_rows,
        [
            "scene_id",
            "weather_condition",
            "tracking_channel",
            "source_category",
            "source_path",
            "variable_name",
            "available",
            "dtype",
            "shape",
            "unit",
            "interpretation",
            "used_in_metrics",
            "missing_reason",
        ],
    )
    build_report(output, provenance, scene_rows, prn_rows, comparison_rows, figures)
    provenance["output_files"] = [
        str(path) for path in output.rglob("*") if path.is_file()
    ]
    (output / "provenance.json").write_text(
        json.dumps(json_safe(provenance), indent=2) + "\n", encoding="utf-8"
    )
    provenance["output_files"] = [
        str(path) for path in output.rglob("*") if path.is_file()
    ]
    (output / "provenance.json").write_text(
        json.dumps(json_safe(provenance), indent=2) + "\n", encoding="utf-8"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    return run(output)


if __name__ == "__main__":
    raise SystemExit(main())
