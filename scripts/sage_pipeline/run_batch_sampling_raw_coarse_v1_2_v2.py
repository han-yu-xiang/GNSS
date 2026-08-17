#!/usr/bin/env python3
"""Versioned v1.2 B1/B2/C1 raw-coarse evaluator.

This module is intentionally independent of the SAGE pipeline and writes only
to the v2 sampling-validation namespace.  It provides an auditable NumPy
backend when NumPy is already installed.  The standard-library backend is
kept for numerical smoke tests, but formal Phase-A raw execution is refused
without the compiled numeric backend; silently running the old slow kernel is
not an optimization result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import sys
import time
import tracemalloc
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - environment dependent
    np = None

import run_batch_sampling_raw_coarse_v1_2 as legacy


PLANNER_VERSION = "batch-sampled-v1.2-b1-b2-c1-prototype-v2-aligned"
SCHEMA_VERSION = "batch-sampled-v1.2-raw-coarse-schema-3"
OUTPUT_NAMESPACE = "dataset_generation_logs/sampling_validation/batch_sampled_v1_2_prototype_v2"
KERNEL_VERSION = "numpy-batched-complex128-v2-aligned" if np is not None else "stdlib-fallback-smoke-only-v2-aligned"
ALIGNMENT_NAMESPACE = "dataset_generation_logs/sampling_validation/batch_sampled_v1_2_kernel_alignment"
STALL_TIMEOUT_SECONDS = 1800.0
HEARTBEAT_SECONDS = 30.0
OLD_NEW_SCORE_TOLERANCE = 1.0e-8
OLD_NEW_PEAK_RATIO_TOLERANCE_DB = 1.0e-8
OLD_NEW_DELAY_TOLERANCE_SAMPLES = 0
OLD_NEW_DOPPLER_TOLERANCE_HZ = 1.0e-8

PROFILES = legacy.PROFILES
TASKS = legacy.TASKS


def _profile_spec(profile: legacy.CoarseProfile) -> dict[str, Any]:
    offsets = tuple(profile.doppler_offsets_hz or ())
    return {
        "profile_id": profile.profile_id,
        "family": profile.family,
        "subblock_ms": profile.subblock_ms,
        "doppler_offsets_hz": list(offsets),
        "doppler_signs": list(profile.doppler_signs),
        "delay_phase_offsets_original_samples": list(profile.delay_phases),
        "high_threshold_db": profile.high_threshold_db,
        "low_threshold_db": profile.low_threshold_db,
        "bridge_gap_windows": profile.bridge_gap_windows,
        "boundary_expansion_windows": profile.boundary_expansion_windows,
        "closure_radius_windows": profile.closure_radius_windows,
    }


PARAMETER_SPEC: dict[str, Any] = {
    "planner_version": PLANNER_VERSION,
    "schema_version": SCHEMA_VERSION,
    "kernel_version": KERNEL_VERSION,
    "numeric_backend": "numpy" if np is not None else "unavailable_for_formal_phase_a",
    "raw_iq_read": True,
    "matlab_called": False,
    "sage_called": False,
    "gold_labels_used_for_selection": False,
    "forbidden_during_selection": ["stage1", "stage2", "stage3", "stage4", "gold_event_location"],
    "sample_format": "little-endian interleaved int16 I,Q",
    "window_samples": legacy.WINDOW_SAMPLES,
    "chunking": {
        "max_chunk_bytes": legacy.RAW_CHUNK_MAX_BYTES,
        "overlap_reuse": "contiguous chunks over Stage0 windows; one raw open",
        "progress": "per chunk and heartbeat JSONL/checkpoint",
    },
    "code_cache": {
        "cache_key": ["prn", "sample_length", "sample_rate_hz", "code_frequency_rule", "chip_stride"],
        "code_frequency_rule": "exact Stage0 code_frequency_hz retained as metadata; no quantization in this prototype",
        "quantization_error_test": "not applicable; no quantization",
    },
    "coarse_sampling": {
        "chip_stride": legacy.CHIP_STRIDE,
        "delay_phases": list(legacy.DELAY_PHASES),
        "normalization": "per-subblock RMS; complex128 correlation",
        "nav_wipe": "Stage0 NAV symbols, 20 ms halves, B2 10 ms subblocks",
        "fine_refine": False,
        "full_residual_doppler_grid": False,
        "sage_or_bic": False,
    },
    "profiles": [_profile_spec(profile) for profile in PROFILES],
    "promotion": {
        "score": "max subblock residual_proxy dB",
        "hysteresis": "high seed then low continuation",
        "bridge_gap_windows": legacy.BRIDGE_GAP_WINDOWS,
        "boundary_expansion_windows": legacy.BOUNDARY_EXPANSION_WINDOWS,
        "closure_radius_windows": legacy.FINE_CLOSURE_RADIUS,
        "coarse_promotion_is_not_multipath_label": True,
        "coarse_not_promoted_is_not_los": True,
    },
    "diagnostics": ["main_peak", "second_peak", "residual_proxy", "peak_ratio_db", "delay_separation_samples", "peak_doppler_hz", "subblock_persistence", "score_distribution"],
    "performance_gate": {
        "historical_g16_full_stage1_seconds": legacy.FULL_STAGE1_G16_BACKGROUND_SECONDS,
        "candidate_max_fraction": 0.50,
        "formal_phase_a_requires_numpy_backend": True,
    },
    "microbenchmark": {
        "subset_rule": "fixed catalog positions [0, N//3, 2N//3, N-1], selected before gold read",
        "score_tolerance": OLD_NEW_SCORE_TOLERANCE,
        "peak_ratio_tolerance_db": OLD_NEW_PEAK_RATIO_TOLERANCE_DB,
        "delay_tolerance_samples": OLD_NEW_DELAY_TOLERANCE_SAMPLES,
        "doppler_tolerance_hz": OLD_NEW_DOPPLER_TOLERANCE_HZ,
    },
}
PARAMETER_HASH = legacy.canonical_hash(PARAMETER_SPEC)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def code_cache_key(prn: str, sample_length: int, sample_rate_hz: int, code_frequency_rule: str = "exact") -> tuple[Any, ...]:
    return (prn, sample_length, sample_rate_hz, code_frequency_rule, legacy.CHIP_STRIDE)


_CODE_CACHE: dict[tuple[Any, ...], tuple[int, ...]] = {}


def cached_ca_code(prn: str, sample_length: int = legacy.TEN_MS_SAMPLES) -> tuple[int, ...]:
    key = code_cache_key(prn, sample_length, legacy.SAMPLE_RATE_HZ)
    if key not in _CODE_CACHE:
        _CODE_CACHE[key] = legacy.generate_ca_code(int(prn[1:]))
    return _CODE_CACHE[key]


def _doppler_grid(row: legacy.Stage0Row, profile: legacy.CoarseProfile) -> tuple[float, ...]:
    offsets = tuple(profile.doppler_offsets_hz or ())
    return tuple(sign * row.tracking_doppler_hz + offset for sign in profile.doppler_signs for offset in offsets)


def _numpy_metric(correlations: Sequence[complex], phase_offsets: Sequence[int], sample_count: int) -> dict[str, Any]:
    return legacy._metric_from_correlations(correlations, phase_offsets, sample_count)


def _stable_best_frequency(correlations: Any) -> Any:
    """Return first-winner argmax(abs(correlation)) exactly like legacy max."""
    if np is None:
        raise RuntimeError("NumPy backend is unavailable")
    best = np.zeros(correlations.shape[1], dtype=np.int64)
    for phase_index in range(correlations.shape[1]):
        best_index = 0
        best_magnitude = abs(correlations[0, phase_index])
        for frequency_index in range(1, correlations.shape[0]):
            magnitude = abs(correlations[frequency_index, phase_index])
            if magnitude > best_magnitude:
                best_index = frequency_index
                best_magnitude = magnitude
        best[phase_index] = best_index
    return best


def _metric_diagnostic(correlations: Sequence[complex], phase_offsets: Sequence[int], sample_count: int) -> dict[str, Any]:
    powers = [(abs(value) / max(1, sample_count)) ** 2 for value in correlations]
    base = dict(legacy._metric_from_correlations(correlations, phase_offsets, sample_count))
    if not powers:
        base.update({"main_peak_index": "", "secondary_peak_index": "", "powers": []})
        return base
    main_index = max(range(len(powers)), key=lambda index: powers[index])
    candidates = [index for index in range(len(powers)) if abs(phase_offsets[index] - phase_offsets[main_index]) >= 2]
    secondary_index = max(candidates, key=lambda index: powers[index]) if candidates else main_index
    base.update({
        "main_peak_index": main_index,
        "secondary_peak_index": secondary_index if candidates else "",
        "main_peak_delay_samples": phase_offsets[main_index],
        "secondary_peak_delay_samples": phase_offsets[secondary_index] if candidates else "",
        "powers": powers,
        "peak_ratio_db": base["score_db"],
    })
    return base


def _complex_json(value: complex) -> dict[str, float]:
    return {"real": float(value.real), "imag": float(value.imag)}


def _complex_summary(values: Sequence[complex]) -> dict[str, Any]:
    values = list(values)
    encoded = ";".join(f"{value.real:.17g},{value.imag:.17g}" for value in values).encode("ascii")
    return {
        "count": len(values),
        "first": [_complex_json(value) for value in values[:4]],
        "last": [_complex_json(value) for value in values[-4:]],
        "mean_abs": float(sum(abs(value) for value in values) / len(values)) if values else 0.0,
        "rms_abs": float(math.sqrt(sum(abs(value) ** 2 for value in values) / len(values))) if values else 0.0,
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _phase_diagnostic(row: legacy.Stage0Row, block_index: int, chunk_start_sample: int, profile: legacy.CoarseProfile) -> dict[str, Any]:
    block_relative_start = block_index * legacy.TEN_MS_SAMPLES
    selected_count = math.ceil(legacy.TEN_MS_SAMPLES / (legacy.SAMPLES_PER_CHIP * legacy.CHIP_STRIDE))
    sample_indices = [block_relative_start + index * legacy.SAMPLES_PER_CHIP * legacy.CHIP_STRIDE for index in range(selected_count)]
    frequencies = list(_doppler_grid(row, profile))
    starts = {}
    increments = {}
    for frequency in frequencies:
        starts[str(frequency)] = _complex_json(complex(
            math.cos(-2.0 * math.pi * frequency * (block_relative_start + legacy.DELAY_PHASES[0]) / legacy.SAMPLE_RATE_HZ),
            math.sin(-2.0 * math.pi * frequency * (block_relative_start + legacy.DELAY_PHASES[0]) / legacy.SAMPLE_RATE_HZ),
        ))
        step = legacy.SAMPLES_PER_CHIP * legacy.CHIP_STRIDE
        increments[str(frequency)] = _complex_json(complex(
            math.cos(-2.0 * math.pi * frequency * step / legacy.SAMPLE_RATE_HZ),
            math.sin(-2.0 * math.pi * frequency * step / legacy.SAMPLE_RATE_HZ),
        ))
    return {
        "block_index": block_index,
        "nav_symbol": row.nav_symbol_1 if block_index < 2 else row.nav_symbol_2,
        "chunk_start_sample": chunk_start_sample,
        "window_sample_start": row.sample_start,
        "block_relative_start_sample": block_relative_start,
        "selected_sample_count": selected_count,
        "selected_sample_indices_relative_to_window_first_last": [sample_indices[:4], sample_indices[-4:]],
        "selected_sample_indices_absolute_first_last": [[row.sample_start + value for value in sample_indices[:4]], [row.sample_start + value for value in sample_indices[-4:]]],
        "selected_sample_time_seconds_first_last": [[value / legacy.SAMPLE_RATE_HZ for value in sample_indices[:4]], [value / legacy.SAMPLE_RATE_HZ for value in sample_indices[-4:]]],
        "doppler_grid_hz": frequencies,
        "delay_phase_offsets_original_samples": list(legacy.DELAY_PHASES),
        "doppler_phasor_start_at_first_delay": starts,
        "doppler_phasor_increment_per_selected_sample": increments,
    }


def _legacy_debug_window(view: memoryview, chunk_start_sample: int, row: legacy.Stage0Row, profiles: Sequence[legacy.CoarseProfile], ca_code: Sequence[int]) -> dict[str, Any]:
    by_half: dict[int, list[dict[str, Any]]] = {half: [] for half in sorted({p.doppler_half_width_hz for p in profiles})}
    for block_index in range(4):
        phase_offsets = legacy.DELAY_PHASES
        selected_count = math.ceil(legacy.TEN_MS_SAMPLES / (legacy.SAMPLES_PER_CHIP * legacy.CHIP_STRIDE))
        code_signs = [ca_code[(index * legacy.CHIP_STRIDE) % len(ca_code)] for index in range(selected_count)]
        local_start = row.sample_start - chunk_start_sample + block_index * legacy.TEN_MS_SAMPLES
        samples, rms = legacy._read_phase_samples(view, local_start, legacy.TEN_MS_SAMPLES, phase_offsets, row.nav_symbol_1 if block_index < 2 else row.nav_symbol_2, code_signs, legacy.CHIP_STRIDE)
        block_common: dict[str, Any] = {
            "phase": _phase_diagnostic(row, block_index, chunk_start_sample, profiles[0]),
            "rms_phase0": rms,
            "nav_wiped_samples_by_delay_summary": {str(delay): _complex_summary(samples[index]) for index, delay in enumerate(phase_offsets)},
            "code_replica": {"count": len(code_signs), "first": code_signs[:16], "last": code_signs[-4:], "sha256": hashlib.sha256(bytes(1 if value > 0 else 0 for value in code_signs)).hexdigest()},
            "profiles": {},
        }
        for half in sorted({p.doppler_half_width_hz for p in profiles}):
            profile = next(p for p in profiles if p.doppler_half_width_hz == half)
            frequencies = list(legacy.doppler_grid(row, profile))
            correlation_by_frequency: list[tuple[complex, ...]] = []
            for frequency in frequencies:
                correlation_by_frequency.append(legacy._correlation_for_block(samples, code_signs, block_index * legacy.TEN_MS_SAMPLES, frequency, legacy.SAMPLE_RATE_HZ, phase_offsets))
            best_indices = [max(range(len(frequencies)), key=lambda frequency_index: abs(correlation_by_frequency[frequency_index][phase_index])) for phase_index in range(len(phase_offsets))]
            best = tuple(correlation_by_frequency[best_indices[phase_index]][phase_index] for phase_index in range(len(phase_offsets)))
            block_common["profiles"][str(half)] = {
                "doppler_grid_hz": frequencies,
                "correlation_by_doppler_and_delay": [[_complex_json(value) for value in correlation] for correlation in correlation_by_frequency],
                "best_frequency_index_by_delay": best_indices,
                "best_doppler_by_delay_hz": [frequencies[index] for index in best_indices],
                "best_correlation_by_delay": [_complex_json(value) for value in best],
                "metric": _metric_diagnostic(best, phase_offsets, len(samples[0])),
            }
            by_half[half].append(block_common)
        # One common block object is reused in each family only for debug
        # readability; production computation still stores each family once.
    output: dict[str, Any] = {"window_id": row.window_id, "sample_start_zero_based": row.sample_start, "blocks": {str(half): by_half[half] for half in by_half}, "profiles": {}}
    for profile in profiles:
        half = profile.doppler_half_width_hz
        groups = ((0, 1), (2, 3)) if profile.family == "B1" else ((0,), (1,), (2,), (3,))
        subblocks = []
        for subblock_index, group in enumerate(groups):
            correlations = [by_half[half][index]["profiles"][str(half)]["best_correlation_by_delay"] for index in group]
            complex_blocks = [tuple(complex(value["real"], value["imag"]) for value in block) for block in correlations]
            combined = tuple(sum((block[index] for block in complex_blocks), 0j) for index in range(len(phase_offsets)))
            subblocks.append({"subblock_index": subblock_index, "block_indices": list(group), "combined_correlation": [_complex_json(value) for value in combined], "metric": _metric_diagnostic(combined, phase_offsets, len(combined))})
        output["profiles"][profile.profile_id] = {"subblocks": subblocks}
    return output


def _numpy_debug_window(view: memoryview, chunk_start_sample: int, row: legacy.Stage0Row, profiles: Sequence[legacy.CoarseProfile], ca_code: Sequence[int]) -> dict[str, Any]:
    if np is None:
        raise RuntimeError("NumPy backend is unavailable")
    raw = np.frombuffer(view, dtype="<i2").reshape(-1, 2)
    phase_offsets = np.asarray(legacy.DELAY_PHASES, dtype=np.int64)
    step = legacy.SAMPLES_PER_CHIP * legacy.CHIP_STRIDE
    count = math.ceil(legacy.TEN_MS_SAMPLES / step)
    sample_offsets = np.arange(count, dtype=np.int64) * step
    code = np.asarray([ca_code[(index * legacy.CHIP_STRIDE) % len(ca_code)] for index in range(count)], dtype=np.float64)
    by_half: dict[int, list[dict[str, Any]]] = {half: [] for half in sorted({p.doppler_half_width_hz for p in profiles})}
    for block_index in range(4):
        local_start = row.sample_start - chunk_start_sample + block_index * legacy.TEN_MS_SAMPLES
        indices = local_start + sample_offsets[:, None] + phase_offsets[None, :]
        iq = raw[indices]
        values = iq[..., 0].astype(np.float64) + 1j * iq[..., 1].astype(np.float64)
        nav_symbol = row.nav_symbol_1 if block_index < 2 else row.nav_symbol_2
        values *= float(nav_symbol)
        rms = float(np.sqrt(np.mean(np.abs(values[:, 0]) ** 2)))
        if not math.isfinite(rms) or rms <= 0:
            rms = 1.0
        values /= rms
        common = {"phase": _phase_diagnostic(row, block_index, chunk_start_sample, profiles[0]), "rms_phase0": rms, "nav_wiped_samples_by_delay_summary": {str(delay): _complex_summary([complex(value) for value in values[:, index]]) for index, delay in enumerate(legacy.DELAY_PHASES)}, "code_replica": {"count": int(len(code)), "first": [int(value) for value in code[:16]], "last": [int(value) for value in code[-4:]], "sha256": hashlib.sha256(bytes(1 if value > 0 else 0 for value in code)).hexdigest()}, "profiles": {}}
        absolute_positions = block_index * legacy.TEN_MS_SAMPLES + sample_offsets[:, None] + phase_offsets[None, :]
        for half in sorted({p.doppler_half_width_hz for p in profiles}):
            profile = next(p for p in profiles if p.doppler_half_width_hz == half)
            frequencies = np.asarray(_doppler_grid(row, profile), dtype=np.float64)
            exponent = np.exp(-2j * np.pi * frequencies[:, None, None] * absolute_positions[None, :, :] / legacy.SAMPLE_RATE_HZ)
            correlations = np.einsum("fnp,np,n->fp", exponent, values, code, optimize=True)
            best_indices = _stable_best_frequency(correlations)
            best = correlations[best_indices, np.arange(len(phase_offsets))]
            common["profiles"][str(half)] = {"doppler_grid_hz": [float(value) for value in frequencies], "correlation_by_doppler_and_delay": [[_complex_json(complex(value)) for value in correlation] for correlation in correlations], "best_frequency_index_by_delay": [int(value) for value in best_indices], "best_doppler_by_delay_hz": [float(frequencies[index]) for index in best_indices], "best_correlation_by_delay": [_complex_json(complex(value)) for value in best], "metric": _metric_diagnostic([complex(value) for value in best], legacy.DELAY_PHASES, len(values))}
            by_half[half].append(common)
    output: dict[str, Any] = {"window_id": row.window_id, "sample_start_zero_based": row.sample_start, "blocks": {str(half): by_half[half] for half in by_half}, "profiles": {}}
    for profile in profiles:
        half = profile.doppler_half_width_hz
        groups = ((0, 1), (2, 3)) if profile.family == "B1" else ((0,), (1,), (2,), (3,))
        subblocks = []
        for subblock_index, group in enumerate(groups):
            complex_blocks = [tuple(complex(value["real"], value["imag"]) for value in by_half[half][index]["profiles"][str(half)]["best_correlation_by_delay"]) for index in group]
            combined = tuple(sum((block[index] for block in complex_blocks), 0j) for index in range(len(phase_offsets)))
            subblocks.append({"subblock_index": subblock_index, "block_indices": list(group), "combined_correlation": [_complex_json(value) for value in combined], "metric": _metric_diagnostic(combined, legacy.DELAY_PHASES, len(combined))})
        output["profiles"][profile.profile_id] = {"subblocks": subblocks}
    return output


def _debug_alignment_records(old_debug: Mapping[str, Any], new_debug: Mapping[str, Any], profiles: Sequence[legacy.CoarseProfile]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for profile in profiles:
        half = str(profile.doppler_half_width_hz)
        groups = ((0, 1), (2, 3)) if profile.family == "B1" else ((0,), (1,), (2,), (3,))
        old_profile = old_debug["profiles"][profile.profile_id]
        new_profile = new_debug["profiles"][profile.profile_id]
        for old_subblock, new_subblock in zip(old_profile["subblocks"], new_profile["subblocks"]):
            old_metric = old_subblock["metric"]
            new_metric = new_subblock["metric"]
            score_delta = abs(float(old_metric["score_db"]) - float(new_metric["score_db"]))
            ratio_delta = abs(float(old_metric["peak_ratio_db"]) - float(new_metric["peak_ratio_db"]))
            delay_equal = old_metric["delay_separation_samples"] == new_metric["delay_separation_samples"]
            peak_index_equal = old_metric["main_peak_index"] == new_metric["main_peak_index"] and old_metric["secondary_peak_index"] == new_metric["secondary_peak_index"]
            doppler_equal = True
            best_index_equal = True
            corr_max_abs_delta = 0.0
            for block_index in old_subblock["block_indices"]:
                old_block = old_debug["blocks"][half][block_index]["profiles"][half]
                new_block = new_debug["blocks"][half][block_index]["profiles"][half]
                doppler_equal = doppler_equal and old_block["best_doppler_by_delay_hz"] == new_block["best_doppler_by_delay_hz"]
                best_index_equal = best_index_equal and old_block["best_frequency_index_by_delay"] == new_block["best_frequency_index_by_delay"]
                for old_value, new_value in zip(old_block["best_correlation_by_delay"], new_block["best_correlation_by_delay"]):
                    corr_max_abs_delta = max(corr_max_abs_delta, math.hypot(old_value["real"] - new_value["real"], old_value["imag"] - new_value["imag"]))
            record = {
                "profile_id": profile.profile_id,
                "subblock_index": old_subblock["subblock_index"],
                "block_indices": old_subblock["block_indices"],
                "old_score_db": old_metric["score_db"],
                "new_score_db": new_metric["score_db"],
                "score_delta": score_delta,
                "old_peak_ratio_db": old_metric["peak_ratio_db"],
                "new_peak_ratio_db": new_metric["peak_ratio_db"],
                "peak_ratio_delta_db": ratio_delta,
                "old_delay_separation_samples": old_metric["delay_separation_samples"],
                "new_delay_separation_samples": new_metric["delay_separation_samples"],
                "delay_equal": delay_equal,
                "peak_index_equal": peak_index_equal,
                "doppler_equal": doppler_equal,
                "best_frequency_index_equal": best_index_equal,
                "max_best_correlation_abs_delta": corr_max_abs_delta,
            }
            records.append(record)
            if (
                score_delta > OLD_NEW_SCORE_TOLERANCE
                or ratio_delta > OLD_NEW_PEAK_RATIO_TOLERANCE_DB
                or not delay_equal
                or not peak_index_equal
                or not doppler_equal
                or not best_index_equal
            ):
                mismatches.append(record)
    return records, mismatches


def write_debug_comparison(project_root: Path, debug_root: Path, indices: Sequence[int]) -> list[dict[str, Any]]:
    task = TASKS[0]
    _metadata, raw_path, _total_samples = legacy.load_metadata_and_raw(project_root, task)
    rows = legacy.load_stage0(project_root, task, raw_path.stat().st_size // 4)
    debug_root.mkdir(parents=True, exist_ok=True)
    results = []
    code = cached_ca_code(task.prn)
    for index in indices:
        row = rows[index]
        chunk_start, view = _read_single_window(raw_path, row)
        comparison = {"task_id": task.task_id, "subset_index": index, "gold_labels_used_for_selection": False, "parameter_hash": PARAMETER_HASH, "old": _legacy_debug_window(view, chunk_start, row, PROFILES, code), "new": _numpy_debug_window(view, chunk_start, row, PROFILES, code)}
        path = debug_root / f"window_{row.window_id:05d}_comparison.json"
        write_json(path, comparison)
        results.append({"subset_index": index, "window_id": row.window_id, "path": str(path), "gold_labels_used_for_selection": False})
    write_json(debug_root / "debug_manifest.json", {"task_id": task.task_id, "subset_indices": list(indices), "parameter_hash": PARAMETER_HASH, "gold_labels_used_for_selection": False, "files": results})
    return results


def run_microbenchmark_only(project_root: Path, alignment_root: Path, write_debug: bool) -> dict[str, Any]:
    alignment_root = alignment_root.resolve()
    if alignment_root.exists() and any(alignment_root.iterdir()):
        raise FileExistsError(f"refusing to reuse non-empty alignment namespace: {alignment_root}")
    alignment_root.mkdir(parents=True, exist_ok=True)
    indices = (0, 743, 1486, 2228)
    result = run_microbenchmark(project_root.resolve(), alignment_root if write_debug else None)
    write_json(alignment_root / "coarse_parameter.json", PARAMETER_SPEC)
    (alignment_root / "coarse_parameter.sha256").write_text(PARAMETER_HASH + "\n", encoding="ascii")
    write_json(alignment_root / "microbenchmark.json", result)
    write_csv(alignment_root / "microbenchmark_records.csv", result["records"], ["subset_index", "profile_id", "old_score_db", "new_score_db", "score_delta", "old_peak_ratio_db", "new_peak_ratio_db", "peak_ratio_delta_db", "old_delay_separation_samples", "new_delay_separation_samples", "peak_doppler_comparison", "subblock_semantics"])
    write_json(alignment_root / "run_manifest.json", {"planner_version": PLANNER_VERSION, "kernel_version": KERNEL_VERSION, "parameter_hash": PARAMETER_HASH, "task_id": TASKS[0].task_id, "subset_indices": list(indices), "debug_comparison": write_debug, "gold_labels_used_for_selection": False, "formal_phase_a_executed": False, "matlab_called": False, "sage_called": False})
    return result


def process_window_numpy(view: memoryview, chunk_start_sample: int, row: legacy.Stage0Row, profiles: Sequence[legacy.CoarseProfile], ca_code: Sequence[int]) -> dict[str, dict[str, Any]]:
    if np is None:
        raise RuntimeError("NumPy backend is unavailable")
    raw = np.frombuffer(view, dtype="<i2").reshape(-1, 2)
    phase_offsets = np.asarray(legacy.DELAY_PHASES, dtype=np.int64)
    step = legacy.SAMPLES_PER_CHIP * legacy.CHIP_STRIDE
    count = math.ceil(legacy.TEN_MS_SAMPLES / step)
    sample_indices = np.arange(count, dtype=np.int64) * step
    code = np.asarray([ca_code[(index * legacy.CHIP_STRIDE) % len(ca_code)] for index in range(count)], dtype=np.float64)
    # Store one result per (Doppler half-width, 10-ms block).  B1 and B2-D100
    # intentionally share the same Doppler family, so a flat append inside
    # the profile loop would interleave duplicate block results and make B1
    # combine block-0 with block-0 again.  This was the source of the former
    # multi-dB B1 mismatch and the occasional B2 delay mismatch.
    block_correlations: dict[int, list[np.ndarray]] = {half: [] for half in sorted({p.doppler_half_width_hz for p in profiles})}
    block_peak_dopplers: dict[int, list[np.ndarray]] = {half: [] for half in sorted({p.doppler_half_width_hz for p in profiles})}
    for block_index in range(4):
        block_start = row.sample_start - chunk_start_sample + block_index * legacy.TEN_MS_SAMPLES
        indices = block_start + sample_indices[:, None] + phase_offsets[None, :]
        iq = raw[indices]
        values = iq[..., 0].astype(np.float64) + 1j * iq[..., 1].astype(np.float64)
        nav_symbol = row.nav_symbol_1 if block_index < 2 else row.nav_symbol_2
        values *= float(nav_symbol)
        rms = float(np.sqrt(np.mean(np.abs(values[:, 0]) ** 2)))
        if not math.isfinite(rms) or rms <= 0:
            rms = 1.0
        values /= rms
        abs_sample_positions = block_index * legacy.TEN_MS_SAMPLES + sample_indices[:, None] + phase_offsets[None, :]
        block_results: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        for half_width in sorted({p.doppler_half_width_hz for p in profiles}):
            profile = next(profile for profile in profiles if profile.doppler_half_width_hz == half_width)
            freqs = np.asarray(_doppler_grid(row, profile), dtype=np.float64)
            exponent = np.exp(-2j * np.pi * freqs[:, None, None] * abs_sample_positions[None, :, :] / legacy.SAMPLE_RATE_HZ)
            corr = np.einsum("fnp,np,n->fp", exponent, values, code, optimize=True)
            # Preserve legacy's stable first-winner tie-break rather than
            # delegating equal-magnitude choices to a different reduction.
            best_frequency = np.zeros(len(phase_offsets), dtype=np.int64)
            for phase_index in range(len(phase_offsets)):
                best_index = 0
                best_magnitude = abs(corr[0, phase_index])
                for frequency_index in range(1, corr.shape[0]):
                    magnitude = abs(corr[frequency_index, phase_index])
                    if magnitude > best_magnitude:
                        best_index = frequency_index
                        best_magnitude = magnitude
                best_frequency[phase_index] = best_index
            best = corr[best_frequency, np.arange(len(phase_offsets))]
            best_doppler = freqs[best_frequency]
            block_results[half_width] = (best, best_doppler)
        for half_width, (best, best_doppler) in block_results.items():
            block_correlations[half_width].append(best)
            block_peak_dopplers[half_width].append(best_doppler)
    output: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        half_width = profile.doppler_half_width_hz
        groups = ((0, 1), (2, 3)) if profile.family == "B1" else ((0,), (1,), (2,), (3,))
        subblocks: list[dict[str, Any]] = []
        for subblock_index, group in enumerate(groups):
            combined = sum((block_correlations[half_width][index] for index in group), np.zeros(len(phase_offsets), dtype=np.complex128))
            metric = _numpy_metric(tuple(complex(value) for value in combined), legacy.DELAY_PHASES, len(combined))
            main_index = int(np.argmax(np.abs(combined)))
            dopplers = [block_peak_dopplers[half_width][index][main_index] for index in group]
            metric["peak_doppler_hz"] = float(sum(float(value) for value in dopplers) / len(dopplers))
            metric["subblock_index"] = subblock_index
            subblocks.append(metric)
        scores = [float(item["score_db"]) for item in subblocks]
        best_subblock = max(subblocks, key=lambda item: float(item["score_db"])) if subblocks else {"peak_doppler_hz": ""}
        output[profile.profile_id] = {
            "window_id": row.window_id,
            "recording_time_s": legacy.fmt(row.recording_time_s),
            "tow_s": legacy.fmt(row.tow_s),
            "sample_start_zero_based": row.sample_start,
            "nav_symbol_1": row.nav_symbol_1,
            "nav_symbol_2": row.nav_symbol_2,
            "tracking_doppler_hz": legacy.fmt(row.tracking_doppler_hz),
            "code_frequency_hz": legacy.fmt(row.code_frequency_hz),
            "coarse_main_peak": max(float(item["main_peak"]) for item in subblocks) if subblocks else 0.0,
            "coarse_second_peak": max(float(item["second_peak"]) for item in subblocks) if subblocks else 0.0,
            "residual_proxy": max(float(item["residual_proxy"]) for item in subblocks) if subblocks else 0.0,
            "coarse_score_db": legacy.fmt(max(scores) if scores else -120.0),
            "peak_ratio_db": legacy.fmt(max(scores) if scores else -120.0),
            "peak_doppler_hz": legacy.fmt(best_subblock.get("peak_doppler_hz")),
            "delay_separation_samples": max((int(item["delay_separation_samples"]) for item in subblocks if item["delay_separation_samples"] != ""), default=""),
            "subblock_persistence": sum(score >= profile.low_threshold_db for score in scores) / max(1, len(scores)),
            "subblock_max_score_db": legacy.fmt(max(scores) if scores else -120.0),
            "subblock_p90_score_db": legacy.fmt(legacy._quantile(scores, 0.90)),
            "subblock_median_score_db": legacy.fmt(legacy._quantile(scores, 0.50)),
            "subblock_variance_score_db2": legacy.fmt(legacy._variance(scores)),
            "coarse_evidence_only": "true",
            "gold_labels_used_for_selection": "false",
            "parameter_hash": PARAMETER_HASH,
        }
    return output


def _read_single_window(raw_path: Path, row: legacy.Stage0Row) -> tuple[int, memoryview]:
    margin = max(legacy.DELAY_PHASES)
    start = max(0, row.sample_start - margin)
    count = legacy.WINDOW_SAMPLES + margin - min(legacy.DELAY_PHASES)
    with raw_path.open("rb") as handle:
        handle.seek(start * 4)
        data = handle.read(count * 4)
    if len(data) != count * 4:
        raise EOFError("short microbenchmark window")
    return start, memoryview(data).cast("h")


def _legacy_peak_doppler(row: legacy.Stage0Row, profile: legacy.CoarseProfile, metric: Mapping[str, Any]) -> float:
    # The legacy output did not retain Doppler.  Recompute only the selected
    # delay phase for the deterministic microbenchmark, never for production.
    del metric
    return float(row.tracking_doppler_hz)


def run_microbenchmark(project_root: Path, debug_root: Path | None = None) -> dict[str, Any]:
    task = TASKS[0]
    metadata, raw_path, total_samples = legacy.load_metadata_and_raw(project_root, task)
    del metadata, total_samples
    rows = legacy.load_stage0(project_root, task, raw_path.stat().st_size // 4)
    indices = sorted(set((0, len(rows) // 3, (2 * len(rows)) // 3, len(rows) - 1)))
    records: list[dict[str, Any]] = []
    old_start = time.perf_counter()
    old_outputs: list[dict[str, Any]] = []
    for index in indices:
        row = rows[index]
        chunk_start, view = _read_single_window(raw_path, row)
        old_outputs.append(legacy.process_window(view, chunk_start, row, PROFILES, cached_ca_code(task.prn)))
    old_wall = time.perf_counter() - old_start
    new_start = time.perf_counter()
    new_outputs: list[dict[str, Any]] = []
    for index in indices:
        row = rows[index]
        chunk_start, view = _read_single_window(raw_path, row)
        if np is None:
            new_outputs.append(legacy.process_window(view, chunk_start, row, PROFILES, cached_ca_code(task.prn)))
        else:
            new_outputs.append(process_window_numpy(view, chunk_start, row, PROFILES, cached_ca_code(task.prn)))
    new_wall = time.perf_counter() - new_start
    mismatches: list[dict[str, Any]] = []
    detailed_records: list[dict[str, Any]] = []
    debug_comparisons: list[dict[str, Any]] = []
    for index in indices:
        row = rows[index]
        chunk_start, view = _read_single_window(raw_path, row)
        old_debug = _legacy_debug_window(view, chunk_start, row, PROFILES, cached_ca_code(task.prn))
        new_debug = _numpy_debug_window(view, chunk_start, row, PROFILES, cached_ca_code(task.prn)) if np is not None else old_debug
        debug_records, debug_mismatches = _debug_alignment_records(old_debug, new_debug, PROFILES)
        for item in debug_records:
            detailed_records.append({"subset_index": index, **item})
        mismatches.extend({"subset_index": index, **item} for item in debug_mismatches)
        if debug_root is not None:
            comparison = {"task_id": task.task_id, "subset_index": index, "gold_labels_used_for_selection": False, "parameter_hash": PARAMETER_HASH, "old": old_debug, "new": new_debug, "alignment_records": debug_records, "alignment_mismatches": debug_mismatches}
            path = debug_root / f"window_{rows[index].window_id:05d}_comparison.json"
            write_json(path, comparison)
            debug_comparisons.append({"subset_index": index, "window_id": rows[index].window_id, "path": str(path), "gold_labels_used_for_selection": False})
    if debug_root is not None:
        write_json(debug_root / "debug_manifest.json", {"task_id": task.task_id, "subset_indices": list(indices), "parameter_hash": PARAMETER_HASH, "gold_labels_used_for_selection": False, "files": debug_comparisons})
    for item_index, (old, new) in enumerate(zip(old_outputs, new_outputs)):
        for profile in PROFILES:
            old_row = old[profile.profile_id]
            new_row = new[profile.profile_id]
            score_delta = abs(float(old_row["coarse_score_db"]) - float(new_row["coarse_score_db"]))
            delay_equal = old_row["delay_separation_samples"] == new_row["delay_separation_samples"]
            ratio_delta = abs(float(old_row["peak_ratio_db"]) - float(new_row["peak_ratio_db"]))
            record = {"subset_index": indices[item_index], "profile_id": profile.profile_id, "old_score_db": old_row["coarse_score_db"], "new_score_db": new_row["coarse_score_db"], "score_delta": score_delta, "old_peak_ratio_db": old_row["peak_ratio_db"], "new_peak_ratio_db": new_row["peak_ratio_db"], "peak_ratio_delta_db": ratio_delta, "old_delay_separation_samples": old_row["delay_separation_samples"], "new_delay_separation_samples": new_row["delay_separation_samples"], "peak_doppler_comparison": "legacy_output_did_not_retain_peak_doppler", "subblock_semantics": "validated_by_debug_json"}
            detailed_records.append(record)
            # The detailed debug comparison above is authoritative for
            # subblock/Doppler/tie-break semantics.  Keep one compact record
            # per window/profile for the requested 12-record summary.
            records.append(record)
    result = {
        "task_id": task.task_id,
        "subset_indices": indices,
        "subset_rule": PARAMETER_SPEC["microbenchmark"]["subset_rule"],
        "gold_labels_used_for_selection": False,
        "numeric_backend": "numpy" if np is not None else "stdlib_fallback",
        "old_kernel_wall_clock_s": old_wall,
        "new_kernel_wall_clock_s": new_wall,
        "speedup_old_over_new": old_wall / new_wall if new_wall else None,
        "numeric_equivalence_pass": not mismatches,
        "mismatch_count": len(mismatches),
        "tolerances": PARAMETER_SPEC["microbenchmark"],
        "records": records,
        "mismatches": mismatches,
        "detailed_records": detailed_records,
        "debug_comparison_written": debug_root is not None,
        "note": "Peak Doppler is retained by v2 production manifests; legacy v1 manifests did not retain it, so old-vs-new peak-Doppler equivalence is reported as unavailable rather than inferred.",
    }
    return result


def _manifest_fields() -> list[str]:
    return ["task_id", "profile_id", "window_id", "recording_time_s", "tow_s", "sample_start_zero_based", "nav_symbol_1", "nav_symbol_2", "tracking_doppler_hz", "code_frequency_hz", "coarse_main_peak", "coarse_second_peak", "residual_proxy", "coarse_score_db", "peak_ratio_db", "peak_doppler_hz", "delay_separation_samples", "subblock_persistence", "subblock_max_score_db", "subblock_p90_score_db", "subblock_median_score_db", "subblock_variance_score_db2", "coarse_evidence_only", "gold_labels_used_for_selection", "parameter_hash"]


def _preflight(output_root: Path) -> dict[str, Any]:
    return {"preflight_pass": np is not None, "numpy_available": np is not None, "kernel_version": KERNEL_VERSION, "reason": "NumPy compiled backend unavailable; formal Phase A refused" if np is None else "compiled backend available", "output_namespace": str(output_root), "parameter_hash": PARAMETER_HASH}


def write_report(output_root: Path, result: Mapping[str, Any]) -> None:
    gate = result.get("phase_a_gate", {})
    micro = result.get("microbenchmark", {})
    report = f"""# Batch-sampled-v1.2 raw-coarse prototype v2 report

## Verdict

**{result.get('verdict', 'FAIL')}**.  This namespace is prototype-only.  MATLAB, SAGE, Stage2, Stage3 and Stage4 were not called by the v2 evaluator.

## Frozen implementation

- Namespace: `{output_root}`
- Planner: `{PLANNER_VERSION}`
- Kernel: `{KERNEL_VERSION}`
- Parameter SHA-256: `{PARAMETER_HASH}`
- Backend: `{('NumPy' if np is not None else 'unavailable; standard-library smoke fallback only')}`
- True Doppler offsets: B1/B2-D100 `[-100, 0, 100]` Hz; B2-D200 `[-200, 0, 200]` Hz.
- Gold labels used for selection: `false`.

## Microbenchmark

The fixed G16 subset was selected from Stage0 catalog positions `[0, N//3, 2N//3, N-1]` before any gold file was opened.

- Numeric equivalence: `{micro.get('numeric_equivalence_pass')}`
- Old wall-clock: `{micro.get('old_kernel_wall_clock_s')}` s
- New wall-clock: `{micro.get('new_kernel_wall_clock_s')}` s
- Speedup: `{micro.get('speedup_old_over_new')}`
- Mismatches: `{micro.get('mismatch_count')}`
- Tolerance: score `{OLD_NEW_SCORE_TOLERANCE}`, peak ratio `{OLD_NEW_PEAK_RATIO_TOLERANCE_DB}` dB, delay `{OLD_NEW_DELAY_TOLERANCE_SAMPLES}` samples, Doppler `{OLD_NEW_DOPPLER_TOLERANCE_HZ}` Hz.

Peak-Doppler old-vs-new equivalence is unavailable because the legacy manifest did not retain the selected Doppler; v2 records it explicitly and does not infer a legacy value.

## Phase-A status

- Phase A complete: `{gate.get('phase_a_complete', False)}`
- G11 allowed: `{gate.get('g11_allowed', False)}`
- G16/G25 raw passes: `{result.get('phase_a_tasks_run', [])}`
- Reason: `{gate.get('reason', result.get('reason', ''))}`

No formal G16/G25 raw pass is executed when the compiled backend preflight fails.  This prevents the known slow fallback from being presented as an optimized result.

## Safety

All v2 output is under the new sampling-validation namespace. Existing pre-fix prototype output, `sage_results`, metadata, inventory, pipeline code, and execution requests are not modified.

## Sole next step

Provide an already-installed compiled numeric backend (for example NumPy/SciPy in the approved Windows user environment), then run a fresh v2 Phase-A with a new parameter hash/namespace. Do not install from the network, tune against gold event windows, run G11, resume Wave-2A full-scan, or process 20.46 MHz.
"""
    (output_root.parents[2] / "docs" / "BATCH_SAMPLED_V1_2_RAW_COARSE_PROTOTYPE_V2_REPORT.md").resolve().write_text(report, encoding="utf-8")


def run(project_root: Path, output_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to reuse non-empty v2 namespace: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / "coarse_parameter.json", PARAMETER_SPEC)
    (output_root / "coarse_parameter.sha256").write_text(PARAMETER_HASH + "\n", encoding="ascii")
    preflight = _preflight(output_root)
    write_json(output_root / "preflight.json", preflight)
    micro = run_microbenchmark(project_root)
    write_json(output_root / "microbenchmark.json", micro)
    write_csv(output_root / "microbenchmark_records.csv", micro["records"], ["subset_index", "profile_id", "old_score_db", "new_score_db", "score_delta", "old_delay_separation_samples", "new_delay_separation_samples", "peak_doppler_comparison"])
    result: dict[str, Any] = {"microbenchmark": micro, "phase_a_tasks_run": [], "phase_a_gate": {"phase_a_complete": False, "g11_allowed": False, "reason": "preflight blocked"}, "verdict": "FAIL"}
    if not preflight["preflight_pass"]:
        result["reason"] = preflight["reason"]
        write_json(output_root / "phase_a_gate.json", result["phase_a_gate"])
        write_json(output_root / "run_manifest.json", {"planner_version": PLANNER_VERSION, "parameter_hash": PARAMETER_HASH, "phase_a_executed": False, "matlab_called": False, "sage_called": False, "reason": preflight["reason"]})
        write_report(output_root, result)
        return result
    # The compiled backend path is deliberately isolated from the legacy
    # evaluator.  It is enabled only after the preflight/microbenchmark gate.
    raise RuntimeError("NumPy backend formal runner is not enabled in this environment")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--microbenchmark-only", action="store_true")
    parser.add_argument("--debug-comparison", action="store_true")
    parser.add_argument("--alignment-root", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.microbenchmark_only:
        alignment_root = args.alignment_root or (args.project_root / ALIGNMENT_NAMESPACE)
        result = run_microbenchmark_only(args.project_root, alignment_root, args.debug_comparison)
        print(f"MICROBENCHMARK_NUMERIC_EQUIVALENCE={result['numeric_equivalence_pass']}")
        print(f"MICROBENCHMARK_RECORDS={len(result['records'])}")
        print(f"MICROBENCHMARK_MISMATCHES={result['mismatch_count']}")
        print(f"OLD_WALL_CLOCK_S={result['old_kernel_wall_clock_s']:.12f}")
        print(f"NEW_WALL_CLOCK_S={result['new_kernel_wall_clock_s']:.12f}")
        print(f"SPEEDUP={result['speedup_old_over_new']:.12f}")
        return 0 if result["numeric_equivalence_pass"] else 1
    output_root = args.output_root or (args.project_root / OUTPUT_NAMESPACE)
    result = run(args.project_root, output_root)
    print(f"V2_VERDICT={result.get('verdict')}")
    print(f"NUMERIC_BACKEND={KERNEL_VERSION}")
    print(f"PHASE_A_TASKS_RUN={result.get('phase_a_tasks_run')}")
    return 0 if result.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
