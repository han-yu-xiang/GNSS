#!/usr/bin/env python3
"""B1/B2/C1 raw-coarse prototype for batch-sampled-v1.2.

The evaluator is intentionally independent of ``run_nav_sage_pipeline.m``.
It reads only the approved task's metadata, Stage0 catalog, and raw complex
int16 IQ.  It never writes under a scene and never creates a Stage1 file.
The complete B1/B2 parameter family is frozen before any Stage3/Stage4 gold
file is opened.  Gold is used only by the posterior replay phase.

This prototype uses a sparse, deterministic coarse correlation: the delay
phase grid is one original sample, while the code sequence is sampled every
``chip_stride`` chips to keep this dependency-free Python prototype small.
The output is promotion evidence, not fine Stage1, a path estimate, or a
multipath label.
"""

from __future__ import annotations

import argparse
import array
import csv
import hashlib
import json
import math
import statistics
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PLANNER_VERSION = "batch-sampled-v1.2-b1-b2-c1-prototype"
SCHEMA_VERSION = "batch-sampled-v1.2-raw-coarse-schema-1"
OUTPUT_NAMESPACE = "dataset_generation_logs/sampling_validation/batch_sampled_v1_2_prototype"
SAMPLE_RATE_HZ = 10_230_000
WINDOW_MS = 40
WINDOW_SAMPLES = int(SAMPLE_RATE_HZ * WINDOW_MS / 1000)
TEN_MS_SAMPLES = int(SAMPLE_RATE_HZ * 0.010)
TWENTY_MS_SAMPLES = int(SAMPLE_RATE_HZ * 0.020)
CHIPS_PER_MS = 1023
SAMPLES_PER_CHIP = 10
CHIP_STRIDE = 10
DELAY_PHASES = (-2, -1, 0, 1, 2)
BRIDGE_GAP_WINDOWS = 2
BOUNDARY_EXPANSION_WINDOWS = 2
FINE_CLOSURE_RADIUS = 2
RAW_CHUNK_MAX_BYTES = 64 * 1024 * 1024
RAW_CHUNK_MAX_GAP_SAMPLES = WINDOW_SAMPLES
FULL_STAGE1_G16_BACKGROUND_SECONDS = 65.0 * 60.0
FULL_STAGE1_G16_WINDOW_COUNT = 2229
FULL_STAGE1_COST_GATE_FRACTION = 0.80
FINE_BUDGETS = (1200, 2400, 4800)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    phase: str
    scene_id: str
    prn: str
    tracking_channel: int
    result_namespace: str = "nav_sage_v2"

    @property
    def result_dir(self) -> str:
        return f"{self.result_namespace}/{self.prn}"


@dataclass(frozen=True)
class CoarseProfile:
    profile_id: str
    family: str
    subblock_ms: int
    doppler_half_width_hz: int
    # None means derive the actual tracking-centred coarse grid from the
    # profile's declared half width.  Keep an explicit tuple available for
    # tests/experiments, but never silently fall back to +/-1 Hz for a
    # profile named D100 or D200.
    doppler_offsets_hz: tuple[int, ...] | None = None
    doppler_signs: tuple[int, ...] = (1, -1)
    delay_phases: tuple[int, ...] = DELAY_PHASES
    chip_stride: int = CHIP_STRIDE
    high_threshold_db: float = -10.0
    low_threshold_db: float = -14.0
    bridge_gap_windows: int = BRIDGE_GAP_WINDOWS
    boundary_expansion_windows: int = BOUNDARY_EXPANSION_WINDOWS
    closure_radius_windows: int = FINE_CLOSURE_RADIUS

    def __post_init__(self) -> None:
        if self.doppler_offsets_hz is None:
            object.__setattr__(
                self,
                "doppler_offsets_hz",
                (-self.doppler_half_width_hz, 0, self.doppler_half_width_hz),
            )

    @property
    def subblocks_per_window(self) -> int:
        return WINDOW_MS // self.subblock_ms

    @property
    def doppler_grid_size(self) -> int:
        assert self.doppler_offsets_hz is not None
        return len(self.doppler_offsets_hz) * len(self.doppler_signs)


@dataclass(frozen=True)
class Stage0Row:
    window_id: int
    sample_start: int
    nav_symbol_1: int
    nav_symbol_2: int
    tracking_doppler_hz: float
    code_frequency_hz: float
    tow_s: float | None
    recording_time_s: float | None


@dataclass(frozen=True)
class ChunkPlan:
    chunk_id: str
    start_sample: int
    end_sample_exclusive: int
    window_indices: tuple[int, ...]

    @property
    def sample_count(self) -> int:
        return self.end_sample_exclusive - self.start_sample

    @property
    def byte_count(self) -> int:
        return self.sample_count * 4


@dataclass
class RawPassResult:
    task: TaskSpec
    profile_rows: dict[str, list[dict[str, Any]]]
    chunk_rows: list[dict[str, Any]]
    cost: dict[str, Any]
    errors: list[str]


@dataclass(frozen=True)
class Component:
    component_id: str
    window_ids: tuple[int, ...]
    promoted_window_ids: tuple[int, ...]
    max_score_db: float
    first_window_id: int
    last_window_id: int


@dataclass
class GoldResult:
    confirmed_centers: tuple[int, ...]
    reliable_centers: tuple[int, ...]


TASKS: tuple[TaskSpec, ...] = (
    TaskSpec("phaseA_F1023_V70_D0120_P7_G16_ch1", "phase_a", "F1023_V70_D0120_P7", "G16", 1),
    TaskSpec("phaseA_F1023_v50_D0127_P1_G25_ch0", "phase_a", "F1023_v50_D0127_P1", "G25", 0),
    TaskSpec("phaseB_F1023_V120_D0121_P2_G11_ch0", "phase_b", "F1023_V120_D0121_P2", "G11", 0),
)


# All profiles are frozen at once.  No event file is read while this object
# is constructed or hashed.
PROFILES: tuple[CoarseProfile, ...] = (
    CoarseProfile("B1_20msx2_D100", "B1", 20, 100),
    CoarseProfile("B2_10msx4_D100", "B2", 10, 100),
    CoarseProfile("B2_10msx4_D200", "B2", 10, 200),
)


PARAMETER_SPEC: dict[str, Any] = {
    "planner_version": PLANNER_VERSION,
    "schema_version": SCHEMA_VERSION,
    "input_scope": "10.23MHz complex int16 IQ; Stage0 window catalog; metadata raw_iq.path",
    "raw_iq_read": True,
    "matlab_called": False,
    "sage_called": False,
    "forbidden_during_selection": ["stage1", "stage2", "stage3", "stage4", "gold_event_location"],
    "window_samples": WINDOW_SAMPLES,
    "sample_format": "little-endian interleaved int16 I,Q",
    "chunking": {
        "max_chunk_bytes": RAW_CHUNK_MAX_BYTES,
        "max_gap_samples": RAW_CHUNK_MAX_GAP_SAMPLES,
        "reuse_policy": "contiguous union of overlapping 40ms Stage0 windows; one read per chunk",
    },
    "coarse_sampling": {
        "chip_rate_hz": 1_023_000,
        "samples_per_chip": SAMPLES_PER_CHIP,
        "chip_stride": CHIP_STRIDE,
        "selected_samples_per_1ms": math.ceil(CHIPS_PER_MS / CHIP_STRIDE),
        "delay_phase_offsets_original_samples": list(DELAY_PHASES),
        "normalization": "per-subblock RMS; correlation magnitude normalized by selected sample count and RMS",
        "nav_wipe": "Stage0 nav_symbol_1 for first 20ms and nav_symbol_2 for second 20ms; B2 splits each symbol into two 10ms blocks",
        "fine_refine": False,
        "full_residual_doppler_grid": False,
        "sage_or_bic": False,
    },
    "profiles": [
        {
            "profile_id": profile.profile_id,
            "family": profile.family,
            "subblock_ms": profile.subblock_ms,
            "doppler_grid_hz": [
                f"{sign:+d}*tracking_doppler{offset:+d}Hz" for sign in profile.doppler_signs for offset in profile.doppler_offsets_hz
            ],
            "delay_phase_offsets_original_samples": list(profile.delay_phases),
            "high_threshold_db": profile.high_threshold_db,
            "low_threshold_db": profile.low_threshold_db,
            "bridge_gap_windows": profile.bridge_gap_windows,
            "boundary_expansion_windows": profile.boundary_expansion_windows,
            "closure_radius_windows": profile.closure_radius_windows,
        }
        for profile in PROFILES
    ],
    "promotion": {
        "score": "max across subblock residual_proxy_db; subblock max/p90/median/variance retained",
        "hysteresis": "start at high threshold, continue through low threshold",
        "component_bridge_windows": BRIDGE_GAP_WINDOWS,
        "boundary_expansion_windows": BOUNDARY_EXPANSION_WINDOWS,
        "coarse_not_promoted_is_not_LOS": True,
        "coarse_promotion_is_not_multipath_label": True,
    },
    "cost_gate": {
        "historical_g16_full_stage1_wall_clock_seconds": FULL_STAGE1_G16_BACKGROUND_SECONDS,
        "historical_g16_stage1_window_count": FULL_STAGE1_G16_WINDOW_COUNT,
        "max_allowed_fraction_of_historical_stage1": FULL_STAGE1_COST_GATE_FRACTION,
        "comparison_semantics": "historical Stage1 only; not total Pipeline runtime",
    },
    "fine_budgets_for_projection": list(FINE_BUDGETS),
    "gold_labels_used_for_selection": False,
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


PARAMETER_HASH = canonical_hash(PARAMETER_SPEC)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def parse_int(value: Any) -> int | None:
    number = parse_float(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def fmt(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        return "" if not math.isfinite(value) else f"{value:.9g}"
    return value


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def metadata_path(project_root: Path, task: TaskSpec) -> Path:
    return project_root / "scenes" / task.scene_id / "metadata.json"


def result_path(project_root: Path, task: TaskSpec) -> Path:
    return project_root / "scenes" / task.scene_id / "sage_results" / task.result_dir


def load_metadata_and_raw(project_root: Path, task: TaskSpec) -> tuple[dict[str, Any], Path, int]:
    path = metadata_path(project_root, task)
    if not path.is_file():
        raise FileNotFoundError(f"metadata missing: {path}")
    metadata = json.loads(path.read_text(encoding="utf-8-sig"))
    if metadata.get("scene_id") != task.scene_id:
        raise ValueError(f"metadata scene_id mismatch: {path}")
    sample_rate = parse_int(metadata.get("signal", {}).get("sample_rate_hz"))
    if sample_rate != SAMPLE_RATE_HZ:
        raise ValueError(f"prototype supports only 10.23MHz: {task.task_id} has {sample_rate}")
    if metadata.get("signal", {}).get("complex_iq") is not True:
        raise ValueError(f"metadata does not declare complex IQ: {path}")
    raw_value = metadata.get("raw_iq", {}).get("path")
    if not raw_value:
        raise ValueError(f"metadata raw_iq.path missing: {path}")
    raw_path = Path(str(raw_value))
    if not raw_path.is_absolute():
        raw_path = (path.parent / raw_path).resolve()
    else:
        raw_path = raw_path.resolve()
    if not raw_path.is_file():
        raise FileNotFoundError(f"metadata raw IQ path does not exist: {raw_path}")
    raw_bytes = raw_path.stat().st_size
    if raw_bytes == 0 or raw_bytes % 4 != 0:
        raise ValueError(f"raw IQ is empty or not int16-IQ aligned: {raw_path}")
    return metadata, raw_path, raw_bytes // 4


def load_stage0(project_root: Path, task: TaskSpec, total_samples: int) -> tuple[Stage0Row, ...]:
    path = result_path(project_root, task) / "stage0_valid_40ms_windows.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Stage0 catalog missing: {path}")
    rows = read_csv_rows(path)
    result: list[Stage0Row] = []
    seen: set[int] = set()
    for row in rows:
        window_id = parse_int(row.get("window_id"))
        start = parse_int(row.get("sample_start_zero_based"))
        nav1 = parse_int(row.get("nav_symbol_1"))
        nav2 = parse_int(row.get("nav_symbol_2"))
        doppler = parse_float(row.get("tracking_doppler_hz"))
        code = parse_float(row.get("code_frequency_hz"))
        if None in (window_id, start, nav1, nav2, doppler, code):
            raise ValueError(f"invalid Stage0 row in {path}: {row}")
        if window_id in seen or nav1 not in (-1, 1) or nav2 not in (-1, 1):
            raise ValueError(f"duplicate window or invalid NAV symbol in {path}: {row}")
        if start < 0 or start + WINDOW_SAMPLES + max(DELAY_PHASES) > total_samples:
            raise ValueError(f"Stage0 window exceeds raw file: {task.task_id} window={window_id}")
        seen.add(window_id)
        result.append(Stage0Row(window_id, start, nav1, nav2, doppler, code, parse_float(row.get("tow_s")), parse_float(row.get("recording_time_s"))))
    result.sort(key=lambda item: item.window_id)
    if not result:
        raise ValueError(f"empty Stage0 catalog: {path}")
    return tuple(result)


def build_chunk_plan(rows: Sequence[Stage0Row]) -> tuple[ChunkPlan, ...]:
    if not rows:
        return ()
    plans: list[ChunkPlan] = []
    current_start = max(0, rows[0].sample_start + min(DELAY_PHASES))
    current_end = rows[0].sample_start + WINDOW_SAMPLES + max(DELAY_PHASES)
    current_indices = [0]
    chunk_number = 1
    for index, row in enumerate(rows[1:], start=1):
        start = max(0, row.sample_start + min(DELAY_PHASES))
        end = row.sample_start + WINDOW_SAMPLES + max(DELAY_PHASES)
        proposed_end = max(current_end, end)
        gap = max(0, start - current_end)
        proposed_bytes = (proposed_end - current_start) * 4
        if gap > RAW_CHUNK_MAX_GAP_SAMPLES or proposed_bytes > RAW_CHUNK_MAX_BYTES:
            plans.append(ChunkPlan(f"chunk_{chunk_number:05d}", current_start, current_end, tuple(current_indices)))
            chunk_number += 1
            current_start = start
            current_end = end
            current_indices = [index]
        else:
            current_end = proposed_end
            current_indices.append(index)
    plans.append(ChunkPlan(f"chunk_{chunk_number:05d}", current_start, current_end, tuple(current_indices)))
    return tuple(plans)


def merged_interval_samples(rows: Sequence[Stage0Row]) -> int:
    intervals = sorted((row.sample_start, row.sample_start + WINDOW_SAMPLES) for row in rows)
    if not intervals:
        return 0
    total = 0
    start, end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += end - start
            start, end = next_start, next_end
    return total + end - start


def generate_ca_code(prn: int) -> tuple[int, ...]:
    taps = {
        1: (2, 6), 2: (3, 7), 3: (4, 8), 4: (5, 9), 5: (1, 9), 6: (2, 10),
        7: (1, 8), 8: (2, 9), 9: (3, 10), 10: (2, 3), 11: (3, 4), 12: (5, 6),
        13: (6, 7), 14: (7, 8), 15: (8, 9), 16: (9, 10), 17: (1, 4), 18: (2, 5),
        19: (3, 6), 20: (4, 7), 21: (5, 8), 22: (6, 9), 23: (1, 3), 24: (4, 6),
        25: (5, 7), 26: (6, 8), 27: (7, 9), 28: (8, 10), 29: (1, 6), 30: (2, 7),
        31: (3, 8), 32: (4, 9),
    }
    if prn not in taps:
        raise ValueError(f"unsupported GPS PRN: {prn}")
    g1 = [-1] * 10
    g2 = [-1] * 10
    result: list[int] = []
    tap_a, tap_b = taps[prn]
    for _ in range(1023):
        result.append(g1[9] * g2[tap_a - 1] * g2[tap_b - 1])
        g1_feedback = g1[2] * g1[9]
        g2_feedback = g2[1] * g2[2] * g2[5] * g2[7] * g2[8] * g2[9]
        g1 = [g1_feedback] + g1[:9]
        g2 = [g2_feedback] + g2[:9]
    return tuple(result)


def nav_wipe(symbol: int, values: Sequence[complex]) -> list[complex]:
    if symbol not in (-1, 1):
        raise ValueError("NAV symbol must be +/-1")
    return [value * symbol for value in values]


def _safe_db(numerator: float, denominator: float) -> float:
    if numerator <= 0.0 or denominator <= 0.0:
        return -120.0
    return 10.0 * math.log10(max(numerator / denominator, 1e-12))


def _quantile(values: Sequence[float], q: float) -> float:
    if not values:
        return -120.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _variance(values: Sequence[float]) -> float:
    return statistics.pvariance(values) if len(values) > 1 else 0.0


def doppler_grid(row: Stage0Row, profile: CoarseProfile) -> tuple[float, ...]:
    values = []
    for sign in profile.doppler_signs:
        for offset in profile.doppler_offsets_hz:
            values.append(sign * row.tracking_doppler_hz + offset)
    return tuple(values)


def _correlation_for_block(
    samples_by_phase: Sequence[Sequence[complex]],
    code_signs: Sequence[int],
    block_start_relative_sample: int,
    doppler_hz: float,
    sample_rate_hz: int,
    phase_offsets: Sequence[int],
) -> tuple[complex, ...]:
    step_samples = SAMPLES_PER_CHIP * CHIP_STRIDE
    increment = complex(
        math.cos(-2.0 * math.pi * doppler_hz * step_samples / sample_rate_hz),
        math.sin(-2.0 * math.pi * doppler_hz * step_samples / sample_rate_hz),
    )
    result: list[complex] = []
    for phase_index, phase_offset in enumerate(phase_offsets):
        phase = complex(
            math.cos(-2.0 * math.pi * doppler_hz * (block_start_relative_sample + phase_offset) / sample_rate_hz),
            math.sin(-2.0 * math.pi * doppler_hz * (block_start_relative_sample + phase_offset) / sample_rate_hz),
        )
        accumulator = 0j
        for index, value in enumerate(samples_by_phase[phase_index]):
            accumulator += value * code_signs[index] * phase
            phase *= increment
        result.append(accumulator)
    return tuple(result)


def _read_phase_samples(view: memoryview, local_sample_start: int, block_samples: int, phase_offsets: Sequence[int], nav_symbol: int, code_signs: Sequence[int], chip_stride: int) -> tuple[list[list[complex]], float]:
    selected_count = math.ceil(block_samples / (SAMPLES_PER_CHIP * chip_stride))
    samples: list[list[complex]] = [[] for _ in phase_offsets]
    sum_power = 0.0
    for index in range(selected_count):
        sample_offset = index * SAMPLES_PER_CHIP * chip_stride
        if sample_offset >= block_samples:
            break
        code_sign = code_signs[index % len(code_signs)]
        for phase_index, phase_offset in enumerate(phase_offsets):
            raw_sample = local_sample_start + sample_offset + phase_offset
            if raw_sample < 0 or 2 * raw_sample + 1 >= len(view):
                raise EOFError("raw chunk does not cover requested phase sample")
            real = int(view[2 * raw_sample])
            imag = int(view[2 * raw_sample + 1])
            value = complex(real * nav_symbol, imag * nav_symbol)
            samples[phase_index].append(value)
            if phase_index == 0:
                sum_power += real * real + imag * imag
    rms = math.sqrt(sum_power / max(1, len(samples[0])))
    if rms <= 0.0 or not math.isfinite(rms):
        rms = 1.0
    normalized = [[value / rms for value in phase_values] for phase_values in samples]
    return normalized, rms


def _metric_from_correlations(correlations: Sequence[complex], phase_offsets: Sequence[int], sample_count: int) -> dict[str, Any]:
    powers = [(abs(value) / max(1, sample_count)) ** 2 for value in correlations]
    if not powers:
        return {"main_peak": 0.0, "second_peak": 0.0, "residual_proxy": 0.0, "score_db": -120.0, "delay_separation_samples": ""}
    main_index = max(range(len(powers)), key=lambda index: powers[index])
    main_power = powers[main_index]
    candidates = [index for index, power in enumerate(powers) if abs(phase_offsets[index] - phase_offsets[main_index]) >= 2]
    second_index = max(candidates, key=lambda index: powers[index]) if candidates else main_index
    second_power = powers[second_index] if candidates else 0.0
    return {
        "main_peak": main_power,
        "second_peak": second_power,
        "residual_proxy": second_power / max(main_power, 1e-15),
        "score_db": _safe_db(second_power, main_power),
        "delay_separation_samples": abs(phase_offsets[second_index] - phase_offsets[main_index]) if candidates else "",
    }


def _combine_block_correlations(blocks: Sequence[Sequence[complex]]) -> tuple[complex, ...]:
    if not blocks:
        return ()
    return tuple(sum((block[index] for block in blocks), 0j) for index in range(len(blocks[0])))


def process_window(
    view: memoryview,
    chunk_start_sample: int,
    row: Stage0Row,
    profiles: Sequence[CoarseProfile],
    ca_code: Sequence[int],
) -> dict[str, dict[str, Any]]:
    # One 10-ms raw block is the common primitive.  B1 combines adjacent
    # 10-ms complex correlations; B2 retains each 10-ms block separately.
    block_correlations: list[dict[int, tuple[complex, ...]]] = []
    block_scores: list[dict[int, dict[str, Any]]] = []
    phase_offsets = PROFILES[0].delay_phases
    doppler_profiles = sorted({profile.doppler_half_width_hz for profile in profiles})
    for block_index in range(4):
        block_relative_start = block_index * TEN_MS_SAMPLES
        nav_symbol = row.nav_symbol_1 if block_index < 2 else row.nav_symbol_2
        selected_count = math.ceil(TEN_MS_SAMPLES / (SAMPLES_PER_CHIP * CHIP_STRIDE))
        code_signs = [ca_code[(index * CHIP_STRIDE) % len(ca_code)] for index in range(selected_count)]
        samples, _rms = _read_phase_samples(
            view,
            row.sample_start - chunk_start_sample + block_relative_start,
            TEN_MS_SAMPLES,
            phase_offsets,
            nav_symbol,
            code_signs,
            CHIP_STRIDE,
        )
        correlations_by_offset: dict[int, tuple[complex, ...]] = {}
        scores_by_offset: dict[int, dict[str, Any]] = {}
        for half_width in doppler_profiles:
            profile = next(profile for profile in profiles if profile.doppler_half_width_hz == half_width)
            correlations: list[complex] = []
            for doppler in doppler_grid(row, profile):
                correlation = _correlation_for_block(
                    samples,
                    code_signs,
                    block_relative_start,
                    doppler,
                    SAMPLE_RATE_HZ,
                    phase_offsets,
                )
                for phase_index, value in enumerate(correlation):
                    correlations.append(value)
            # Pick the strongest frequency for each delay phase, preserving
            # the phase-level 1-sample grid for the coarse proxy.
            best_by_phase: list[complex] = []
            grid_size = len(doppler_grid(row, profile))
            for phase_index in range(len(phase_offsets)):
                candidates = [correlations[doppler_index * len(phase_offsets) + phase_index] for doppler_index in range(grid_size)]
                best_by_phase.append(max(candidates, key=lambda value: abs(value)))
            correlations_by_offset[half_width] = tuple(best_by_phase)
            scores_by_offset[half_width] = _metric_from_correlations(best_by_phase, phase_offsets, len(samples[0]))
        block_correlations.append(correlations_by_offset)
        block_scores.append(scores_by_offset)

    output: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        half_width = profile.doppler_half_width_hz
        if profile.family == "B1":
            groups = ((0, 1), (2, 3))
        else:
            groups = ((0,), (1,), (2,), (3,))
        subblocks: list[dict[str, Any]] = []
        for subblock_index, group in enumerate(groups):
            combined = _combine_block_correlations([block_correlations[index][half_width] for index in group])
            metric = _metric_from_correlations(combined, phase_offsets, len(combined) and len(combined) or 1)
            # A combined coherent sum contains two or one 10-ms blocks.  The
            # normalized score is a ratio, so the common denominator cancels.
            metric["subblock_index"] = subblock_index
            subblocks.append(metric)
        scores = [float(item["score_db"]) for item in subblocks]
        window_score = max(scores) if scores else -120.0
        output[profile.profile_id] = {
            "window_id": row.window_id,
            "recording_time_s": fmt(row.recording_time_s),
            "tow_s": fmt(row.tow_s),
            "sample_start_zero_based": row.sample_start,
            "nav_symbol_1": row.nav_symbol_1,
            "nav_symbol_2": row.nav_symbol_2,
            "tracking_doppler_hz": fmt(row.tracking_doppler_hz),
            "code_frequency_hz": fmt(row.code_frequency_hz),
            "coarse_main_peak": max(float(item["main_peak"]) for item in subblocks) if subblocks else 0.0,
            "coarse_second_peak": max(float(item["second_peak"]) for item in subblocks) if subblocks else 0.0,
            "residual_proxy": max(float(item["residual_proxy"]) for item in subblocks) if subblocks else 0.0,
            "coarse_score_db": fmt(window_score),
            "peak_ratio_db": fmt(window_score),
            "delay_separation_samples": max((int(item["delay_separation_samples"]) for item in subblocks if item["delay_separation_samples"] != ""), default=""),
            "subblock_persistence": sum(score >= profile.low_threshold_db for score in scores) / max(1, len(scores)),
            "subblock_max_score_db": fmt(max(scores) if scores else -120.0),
            "subblock_p90_score_db": fmt(_quantile(scores, 0.90)),
            "subblock_median_score_db": fmt(_quantile(scores, 0.50)),
            "subblock_variance_score_db2": fmt(_variance(scores)),
            "coarse_evidence_only": "true",
            "gold_labels_used_for_selection": "false",
            "parameter_hash": PARAMETER_HASH,
        }
    return output


def _window_component_rows(feature_rows: Sequence[Mapping[str, Any]], profile: CoarseProfile) -> tuple[list[Component], dict[int, str]]:
    ordered = sorted(feature_rows, key=lambda row: int(row["window_id"]))
    scores = {int(row["window_id"]): parse_float(row.get("coarse_score_db")) for row in ordered}
    windows = [int(row["window_id"]) for row in ordered]
    high = [window_id for window_id in windows if scores[window_id] is not None and scores[window_id] >= profile.high_threshold_db]
    runs: list[list[int]] = []
    current: list[int] = []
    for window_id in high:
        if current and window_id != current[-1] + 1:
            runs.append(current)
            current = []
        current.append(window_id)
    if current:
        runs.append(current)
    index_set = set(windows)
    expanded: list[list[int]] = []
    for run in runs:
        left = run[0]
        while left - 1 in index_set and scores.get(left - 1) is not None and scores[left - 1] >= profile.low_threshold_db:
            left -= 1
        right = run[-1]
        while right + 1 in index_set and scores.get(right + 1) is not None and scores[right + 1] >= profile.low_threshold_db:
            right += 1
        expanded.append(list(range(left, right + 1)))
    merged: list[list[int]] = []
    for run in expanded:
        if merged and run[0] - merged[-1][-1] - 1 <= profile.bridge_gap_windows:
            gap = list(range(merged[-1][-1] + 1, run[0]))
            if all(window_id in index_set for window_id in gap):
                merged[-1].extend(gap)
                merged[-1].extend(run)
            else:
                merged.append(run)
        else:
            merged.append(run)
    components: list[Component] = []
    reason: dict[int, str] = {}
    for number, run in enumerate(merged, start=1):
        promoted = set(run)
        for window_id in run:
            for offset in range(1, profile.boundary_expansion_windows + 1):
                if window_id - offset in index_set:
                    promoted.add(window_id - offset)
                if window_id + offset in index_set:
                    promoted.add(window_id + offset)
        component = Component(
            f"c{number:04d}",
            tuple(sorted(run)),
            tuple(sorted(promoted)),
            max(scores[window_id] for window_id in run if scores[window_id] is not None),
            min(run),
            max(run),
        )
        components.append(component)
        for window_id in run:
            reason[window_id] = "high_seed_or_low_hysteresis"
        for window_id in promoted - set(run):
            reason[window_id] = "boundary_expansion"
        for gap_window in set(run) - set(high):
            reason[gap_window] = "bridge_gap"
    return components, reason


def build_promotion_manifest(feature_rows: Sequence[Mapping[str, Any]], profile: CoarseProfile) -> tuple[list[dict[str, Any]], list[Component]]:
    components, reasons = _window_component_rows(feature_rows, profile)
    component_by_window: dict[int, str] = {}
    promoted = set()
    for component in components:
        promoted.update(component.promoted_window_ids)
        for window_id in component.promoted_window_ids:
            component_by_window[window_id] = component.component_id
    rows: list[dict[str, Any]] = []
    for source in feature_rows:
        window_id = int(source["window_id"])
        is_promoted = window_id in promoted
        row = dict(source)
        row.update(
            {
                "promotion_status": "coarse_promoted" if is_promoted else "coarse_not_promoted",
                "promotion_reason": reasons.get(window_id, "not_promoted_below_hysteresis"),
                "promotion_component_id": component_by_window.get(window_id, ""),
                "not_promoted": int(not is_promoted),
                "coverage_status": "coarse_promoted" if is_promoted else "coarse_not_promoted",
                "fine_availability": "potential_fine_window" if is_promoted else "not_available_from_coarse",
                "coarse_evidence_only": "true",
                "gold_labels_used_for_selection": "false",
                "parameter_hash": PARAMETER_HASH,
            }
        )
        rows.append(row)
    return rows, components


def project_budget(promoted: set[int], components: Sequence[Component], universe: set[int]) -> dict[str, Any]:
    closure: set[int] = set()
    missing = 0
    for window_id in promoted:
        for offset in range(1, FINE_CLOSURE_RADIUS + 1):
            for neighbor in (window_id - offset, window_id + offset):
                if neighbor in universe:
                    closure.add(neighbor)
                else:
                    missing += 1
    projected = promoted | closure
    return {
        "potential_fine_window_count": len(projected),
        "potential_fine_window_ids": projected,
        "closure_missing_count": missing,
        "budget_projection": {
            str(budget): {
                "status": "within_budget" if len(projected) <= budget else "budget_exhausted_inconclusive",
                "inconclusive": len(projected) > budget or missing > 0,
            }
            for budget in FINE_BUDGETS
        },
    }


class RawChunkReader:
    """Read contiguous chunk ranges and expose an int16 I/Q memory view."""

    def __init__(self, raw_path: Path, rows: Sequence[Stage0Row]) -> None:
        self.raw_path = raw_path
        self.rows = rows
        self.plans = build_chunk_plan(rows)

    def iter_chunks(self) -> Iterable[tuple[ChunkPlan, memoryview]]:
        with self.raw_path.open("rb") as handle:
            for plan in self.plans:
                handle.seek(plan.start_sample * 4)
                data = handle.read(plan.byte_count)
                if len(data) != plan.byte_count:
                    raise EOFError(f"short raw chunk {plan.chunk_id}: expected {plan.byte_count}, got {len(data)}")
                if sys.byteorder != "little":
                    values = array.array("h")
                    values.frombytes(data)
                    values.byteswap()
                    data = values.tobytes()
                yield plan, memoryview(data).cast("h")


def run_raw_pass(task: TaskSpec, raw_path: Path, rows: Sequence[Stage0Row], profiles: Sequence[CoarseProfile]) -> RawPassResult:
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    tracemalloc.start()
    ca_code = generate_ca_code(int(task.prn[1:]))
    feature_rows: dict[str, list[dict[str, Any]]] = {profile.profile_id: [] for profile in profiles}
    chunk_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    actual_bytes = 0
    raw_reader = RawChunkReader(raw_path, rows)
    try:
        for plan, view in raw_reader.iter_chunks():
            chunk_start = time.perf_counter()
            try:
                for row_index in plan.window_indices:
                    window_output = process_window(view, plan.start_sample, rows[row_index], profiles, ca_code)
                    for profile_id, output in window_output.items():
                        feature_rows[profile_id].append(output)
                actual_bytes += plan.byte_count
                chunk_rows.append(
                    {
                        "chunk_id": plan.chunk_id,
                        "start_sample": plan.start_sample,
                        "end_sample_exclusive": plan.end_sample_exclusive,
                        "bytes_read": plan.byte_count,
                        "covered_window_start_id": rows[plan.window_indices[0]].window_id,
                        "covered_window_end_id": rows[plan.window_indices[-1]].window_id,
                        "covered_window_count": len(plan.window_indices),
                        "reused_samples_within_covered_windows": sum(WINDOW_SAMPLES for _ in plan.window_indices) - sum(
                            max(0, min(rows[index].sample_start + WINDOW_SAMPLES, plan.end_sample_exclusive) - max(rows[index].sample_start, plan.start_sample))
                            for index in plan.window_indices
                        ),
                        "chunk_wall_clock_s": time.perf_counter() - chunk_start,
                        "raw_read_status": "ok",
                    }
                )
            except Exception as exc:  # keep the task receipt explicit
                errors.append(f"{plan.chunk_id}: {type(exc).__name__}: {exc}")
                chunk_rows.append(
                    {
                        "chunk_id": plan.chunk_id,
                        "start_sample": plan.start_sample,
                        "end_sample_exclusive": plan.end_sample_exclusive,
                        "bytes_read": plan.byte_count,
                        "covered_window_start_id": rows[plan.window_indices[0]].window_id,
                        "covered_window_end_id": rows[plan.window_indices[-1]].window_id,
                        "covered_window_count": len(plan.window_indices),
                        "reused_samples_within_covered_windows": "",
                        "chunk_wall_clock_s": time.perf_counter() - chunk_start,
                        "raw_read_status": "error",
                        "error": str(exc),
                    }
                )
    finally:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    theoretical_bytes = len(rows) * WINDOW_SAMPLES * 4
    unique_window_samples = merged_interval_samples(rows)
    actual_samples = actual_bytes // 4
    cost = {
        "task_id": task.task_id,
        "raw_path": str(raw_path),
        "raw_read_status": "ok" if not errors else "error",
        "window_count": len(rows),
        "chunk_count": len(raw_reader.plans),
        "fopen_count_actual": len(raw_reader.plans),
        "fopen_count_theoretical_per_window_reopen": len(rows),
        "fseek_count_actual": len(raw_reader.plans),
        "fseek_count_theoretical_per_window_reopen": len(rows),
        "bytes_read_actual_contiguous_chunks": actual_bytes,
        "bytes_read_theoretical_per_window_reopen": theoretical_bytes,
        "bytes_read_unique_stage0_window_union": unique_window_samples * 4,
        "reused_samples_from_overlapping_windows": len(rows) * WINDOW_SAMPLES - unique_window_samples,
        "chunk_gap_samples_read": max(0, actual_samples - unique_window_samples),
        "read_amplification_vs_window_reopen": actual_bytes / theoretical_bytes if theoretical_bytes else 0.0,
        "read_reduction_vs_window_reopen": 1.0 - actual_bytes / theoretical_bytes if theoretical_bytes else 0.0,
        "wall_clock_s": time.perf_counter() - start_wall,
        "cpu_time_s": time.process_time() - start_cpu,
        "peak_memory_bytes_tracemalloc": peak,
        "per_window_coarse_avg_wall_clock_s": (time.perf_counter() - start_wall) / len(rows) if rows else 0.0,
        "errors": errors,
        "cost_is_shared_raw_pass_for_profiles": True,
        "full_stage1_comparison": {
            "historical_g16_stage1_wall_clock_s": FULL_STAGE1_G16_BACKGROUND_SECONDS,
            "coarse_wall_clock_fraction_of_historical_stage1": (time.perf_counter() - start_wall) / FULL_STAGE1_G16_BACKGROUND_SECONDS if task.prn == "G16" else "not_applicable",
            "comparison_is_stage1_only_not_total_pipeline": True,
        },
    }
    return RawPassResult(task, feature_rows, chunk_rows, cost, errors)


def _gold_read_guard(frozen: Mapping[str, Any]) -> None:
    if frozen.get("gold_labels_used_for_selection") is not False or not frozen.get("selection_frozen"):
        raise RuntimeError("gold read attempted before coarse parameter/selection freeze")


def load_gold_after_freeze(project_root: Path, task: TaskSpec, frozen: Mapping[str, Any]) -> GoldResult:
    _gold_read_guard(frozen)
    directory = result_path(project_root, task)
    confirmed: list[int] = []
    reliable: list[int] = []
    stage4 = directory / "stage4_joint_summary.csv"
    stage3 = directory / "stage3_reliable_centers.csv"
    if stage4.is_file():
        for row in read_csv_rows(stage4):
            if parse_int(row.get("joint_valid")) == 1 and (parse_int(row.get("joint_multipath_count")) or 0) > 0:
                center = parse_int(row.get("center_window_id"))
                if center is not None:
                    confirmed.append(center)
    if stage3.is_file():
        for row in read_csv_rows(stage3):
            if parse_int(row.get("reliable_multipath")) == 1:
                center = parse_int(row.get("center_window_id"))
                if center is not None:
                    reliable.append(center)
    return GoldResult(tuple(sorted(set(confirmed))), tuple(sorted(set(reliable))))


def replay_coverage(task: TaskSpec, profile: CoarseProfile, promotion_rows: Sequence[Mapping[str, Any]], gold: GoldResult) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    universe = {int(row["window_id"]) for row in promotion_rows}
    promoted = {int(row["window_id"]) for row in promotion_rows if row.get("promotion_status") == "coarse_promoted"}
    event_centers = gold.confirmed_centers
    event_closure = {window_id for center in event_centers for window_id in range(center - profile.closure_radius_windows, center + profile.closure_radius_windows + 1) if window_id in universe}
    reliable_closure = {window_id for center in gold.reliable_centers for window_id in range(center - profile.closure_radius_windows, center + profile.closure_radius_windows + 1) if window_id in universe}
    rows: list[dict[str, Any]] = []
    for center in event_centers:
        wanted = set(range(center - profile.closure_radius_windows, center + profile.closure_radius_windows + 1))
        available = wanted & universe
        missing = wanted - universe
        rows.append(
            {
                "record_type": "confirmed_event",
                "task_id": task.task_id,
                "profile_id": profile.profile_id,
                "event_center_window_id": center,
                "center_promoted": int(center in promoted),
                "closure_expected_count": len(available),
                "closure_promoted_count": sum(window_id in promoted for window_id in available),
                "closure_missing_count": len(missing),
                "coverage_status": "covered" if center in promoted and available <= promoted and not missing else "missed_or_inconclusive",
                "gold_labels_used_for_selection": "false",
            }
        )
    if not rows:
        rows.append({"record_type": "control_no_confirmed_event", "task_id": task.task_id, "profile_id": profile.profile_id, "event_center_window_id": "", "center_promoted": "", "closure_expected_count": "", "closure_promoted_count": "", "closure_missing_count": "", "coverage_status": "not_applicable", "gold_labels_used_for_selection": "false"})
    center_recall = sum(center in promoted for center in event_centers) / len(event_centers) if event_centers else None
    closure_recall = sum(window_id in promoted for window_id in event_closure) / len(event_closure) if event_closure else None
    reliable_recall = sum(window_id in promoted for window_id in reliable_closure) / len(reliable_closure) if reliable_closure else None
    summary = {
        "task_id": task.task_id,
        "profile_id": profile.profile_id,
        "confirmed_event_count": len(event_centers),
        "known_event_center_recall": center_recall,
        "known_event_pm2_closure_recall": closure_recall,
        "stage3_reliable_center_closure_recall": reliable_recall,
        "promoted_window_count": len(promoted),
        "gold_labels_used_for_selection": "false",
    }
    return rows, summary


def manifest_fields() -> list[str]:
    return [
        "task_id", "profile_id", "window_id", "recording_time_s", "tow_s", "sample_start_zero_based",
        "nav_symbol_1", "nav_symbol_2", "tracking_doppler_hz", "code_frequency_hz", "coarse_main_peak",
        "coarse_second_peak", "residual_proxy", "coarse_score_db", "peak_ratio_db", "delay_separation_samples",
        "subblock_persistence", "subblock_max_score_db", "subblock_p90_score_db", "subblock_median_score_db",
        "subblock_variance_score_db2", "coarse_evidence_only", "gold_labels_used_for_selection", "parameter_hash",
    ]


def add_profile_ids(rows: Sequence[Mapping[str, Any]], profile: CoarseProfile) -> list[dict[str, Any]]:
    return [dict(row, profile_id=profile.profile_id) for row in rows]


def run(project_root: Path, output_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"refusing to reuse non-empty prototype namespace: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    frozen = {
        "planner_version": PLANNER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "parameter_hash": PARAMETER_HASH,
        "selection_frozen": True,
        "selection_frozen_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "gold_labels_used_for_selection": False,
        "raw_iq_read": True,
        "matlab_called": False,
        "sage_called": False,
        "phase_a_tasks": [task.__dict__ for task in TASKS if task.phase == "phase_a"],
        "phase_b_task": next(task.__dict__ for task in TASKS if task.phase == "phase_b"),
        "profile_ids": [profile.profile_id for profile in PROFILES],
        "parameter_spec_sha256": PARAMETER_HASH,
    }
    write_json(output_root / "coarse_parameter.json", PARAMETER_SPEC)
    (output_root / "coarse_parameter.sha256").write_text(PARAMETER_HASH + "\n", encoding="ascii")
    write_json(output_root / "selection_freeze.json", frozen)
    task_inputs: dict[str, tuple[dict[str, Any], Path, tuple[Stage0Row, ...]]] = {}
    for task in TASKS[:2]:
        metadata, raw_path, total_samples = load_metadata_and_raw(project_root, task)
        rows = load_stage0(project_root, task, total_samples)
        task_inputs[task.task_id] = (metadata, raw_path, rows)
        write_json(output_root / task.task_id / "input_receipt.json", {
            "task_id": task.task_id,
            "scene_id": task.scene_id,
            "prn": task.prn,
            "tracking_channel": task.tracking_channel,
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "metadata_path": str(metadata_path(project_root, task)),
            "metadata_sha256": sha256_file(metadata_path(project_root, task)),
            "raw_path_from_metadata": str(raw_path),
            "raw_bytes": raw_path.stat().st_size,
            "stage0_path": str(result_path(project_root, task) / "stage0_valid_40ms_windows.csv"),
            "stage0_sha256": sha256_file(result_path(project_root, task) / "stage0_valid_40ms_windows.csv"),
            "stage0_window_count": len(rows),
            "raw_read_mode": "read_only",
        })
    phase_a_summary: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    profile_promotions: dict[tuple[str, str], list[dict[str, Any]]] = {}
    profile_components: dict[tuple[str, str], list[Component]] = {}
    raw_results: dict[str, RawPassResult] = {}
    for task in TASKS[:2]:
        _metadata, raw_path, rows = task_inputs[task.task_id]
        raw_result = run_raw_pass(task, raw_path, rows, PROFILES)
        raw_results[task.task_id] = raw_result
        cost_rows.append({"task_id": task.task_id, **raw_result.cost})
        write_csv(output_root / task.task_id / "chunk_manifest.csv", raw_result.chunk_rows, [
            "chunk_id", "start_sample", "end_sample_exclusive", "bytes_read", "covered_window_start_id", "covered_window_end_id", "covered_window_count", "reused_samples_within_covered_windows", "chunk_wall_clock_s", "raw_read_status", "error",
        ])
        for profile in PROFILES:
            feature_rows = add_profile_ids(raw_result.profile_rows[profile.profile_id], profile)
            promotion_rows, components = build_promotion_manifest(feature_rows, profile)
            profile_promotions[(task.task_id, profile.profile_id)] = promotion_rows
            profile_components[(task.task_id, profile.profile_id)] = components
            profile_dir = output_root / task.task_id / profile.profile_id
            write_csv(profile_dir / "coarse_window_manifest.csv", feature_rows, manifest_fields())
            write_csv(profile_dir / "promotion_manifest.csv", promotion_rows, manifest_fields() + ["promotion_status", "promotion_reason", "promotion_component_id", "not_promoted", "coverage_status", "fine_availability"])
            component_rows = [{
                "task_id": task.task_id,
                "profile_id": profile.profile_id,
                "component_id": component.component_id,
                "first_window_id": component.first_window_id,
                "last_window_id": component.last_window_id,
                "component_window_count": len(component.window_ids),
                "promoted_window_count": len(component.promoted_window_ids),
                "max_score_db": component.max_score_db,
                "parameter_hash": PARAMETER_HASH,
                "gold_labels_used_for_selection": "false",
            } for component in components]
            write_csv(profile_dir / "promotion_components.csv", component_rows, ["task_id", "profile_id", "component_id", "first_window_id", "last_window_id", "component_window_count", "promoted_window_count", "max_score_db", "parameter_hash", "gold_labels_used_for_selection"])
            projection = project_budget({int(row["window_id"]) for row in promotion_rows if row["promotion_status"] == "coarse_promoted"}, components, {row.window_id for row in rows})
            profile_cost = dict(raw_result.cost)
            profile_cost.update({"task_id": task.task_id, "profile_id": profile.profile_id, "promotion_fraction": sum(row["promotion_status"] == "coarse_promoted" for row in promotion_rows) / len(promotion_rows), "component_count": len(components), "potential_fine_window_count": projection["potential_fine_window_count"], "budget_projection": projection["budget_projection"], "closure_missing_count": projection["closure_missing_count"], "parameter_hash": PARAMETER_HASH})
            write_json(profile_dir / "cost_measurement.json", profile_cost)
            write_json(profile_dir / "run_manifest.json", {
                "task_id": task.task_id,
                "profile_id": profile.profile_id,
                "stage0_window_count": len(rows),
                "raw_path": str(raw_path),
                "raw_read_only": True,
                "coarse_only": True,
                "stage1_output_written": False,
                "stage2_stage3_stage4_executed": False,
                "gold_labels_used_for_selection": False,
                "parameter_hash": PARAMETER_HASH,
            })
            phase_a_summary.append({
                "task_id": task.task_id,
                "profile_id": profile.profile_id,
                "phase": task.phase,
                "N0": len(rows),
                "promotion_fraction": profile_cost["promotion_fraction"],
                "component_count": len(components),
                "potential_fine_window_count": projection["potential_fine_window_count"],
                "budget_exhausted_F1200": projection["budget_projection"]["1200"]["status"],
                "budget_exhausted_F2400": projection["budget_projection"]["2400"]["status"],
                "budget_exhausted_F4800": projection["budget_projection"]["4800"]["status"],
                "raw_read_status": raw_result.cost["raw_read_status"],
                "wall_clock_s_shared_task_pass": raw_result.cost["wall_clock_s"],
                "parameter_hash": PARAMETER_HASH,
                "gold_labels_used_for_selection": "false",
            })
    # Gold files are first opened here, after all parameters and Phase-A
    # production manifests have been written.
    gold_results = {task.task_id: load_gold_after_freeze(project_root, task, frozen) for task in TASKS[:2]}
    for task in TASKS[:2]:
        for profile in PROFILES:
            rows, summary = replay_coverage(task, profile, profile_promotions[(task.task_id, profile.profile_id)], gold_results[task.task_id])
            profile_dir = output_root / task.task_id / profile.profile_id
            write_csv(profile_dir / "coverage_replay.csv", rows, ["record_type", "task_id", "profile_id", "event_center_window_id", "center_promoted", "closure_expected_count", "closure_promoted_count", "closure_missing_count", "coverage_status", "gold_labels_used_for_selection"])
            coverage_rows.append(summary)
            for item in phase_a_summary:
                if item["task_id"] == task.task_id and item["profile_id"] == profile.profile_id:
                    item.update({"known_event_center_recall": summary["known_event_center_recall"], "known_event_pm2_closure_recall": summary["known_event_pm2_closure_recall"], "stage3_reliable_center_closure_recall": summary["stage3_reliable_center_closure_recall"], "confirmed_event_count": summary["confirmed_event_count"]})
    phase_a_cost_gate = []
    for summary in phase_a_summary:
        cost = next(item for item in cost_rows if item["task_id"] == summary["task_id"])
        recall_pass = summary.get("known_event_center_recall") == 1.0 and summary.get("known_event_pm2_closure_recall") == 1.0
        cost_pass = (
            summary["raw_read_status"] == "ok"
            and summary["wall_clock_s_shared_task_pass"] < FULL_STAGE1_G16_BACKGROUND_SECONDS * FULL_STAGE1_COST_GATE_FRACTION
            and cost["bytes_read_actual_contiguous_chunks"] <= cost["bytes_read_theoretical_per_window_reopen"]
        ) if summary["task_id"].endswith("G16_ch1") else False
        phase_a_cost_gate.append({
            "profile_id": summary["profile_id"],
            "g16_event_center_recall_pass": recall_pass,
            "g16_pm2_closure_recall_pass": recall_pass,
            "g16_raw_read_error_pass": summary["raw_read_status"] == "ok",
            "g16_coverage_gap_pass": cost["errors"] == [],
            "g16_clear_cost_advantage_pass": cost_pass,
            "g16_eligible": recall_pass and cost_pass and cost["errors"] == [],
            "parameter_hash": PARAMETER_HASH,
        })
    eligible = [item for item in phase_a_cost_gate if item["g16_eligible"]]
    chosen = sorted(eligible, key=lambda item: item["profile_id"])[0] if eligible else None
    phase_a_gate = {
        "phase_a_complete": True,
        "g16_eligible_profiles": eligible,
        "g11_allowed": bool(chosen),
        "chosen_profile_id": chosen["profile_id"] if chosen else "",
        "reason": "at least one frozen profile passed G16 center+closure+cost gate" if chosen else "no frozen profile passed G16 center+closure+cost gate; G11 prohibited",
        "parameter_hash": PARAMETER_HASH,
        "gold_labels_used_for_selection": False,
    }
    write_csv(output_root / "phase_a_summary.csv", phase_a_summary, list(phase_a_summary[0]) if phase_a_summary else [])
    write_csv(output_root / "phase_a_cost_gate.csv", phase_a_cost_gate, list(phase_a_cost_gate[0]) if phase_a_cost_gate else [])
    write_json(output_root / "phase_a_gate.json", phase_a_gate)
    phase_b_result: dict[str, Any] | None = None
    if chosen:
        task = TASKS[2]
        metadata, raw_path, total_samples = load_metadata_and_raw(project_root, task)
        rows = load_stage0(project_root, task, total_samples)
        task_inputs[task.task_id] = (metadata, raw_path, rows)
        profile = next(profile for profile in PROFILES if profile.profile_id == chosen["profile_id"])
        raw_result = run_raw_pass(task, raw_path, rows, (profile,))
        feature_rows = add_profile_ids(raw_result.profile_rows[profile.profile_id], profile)
        promotion_rows, components = build_promotion_manifest(feature_rows, profile)
        profile_dir = output_root / "phase_b" / task.task_id / profile.profile_id
        write_csv(profile_dir / "coarse_window_manifest.csv", feature_rows, manifest_fields())
        write_csv(profile_dir / "promotion_manifest.csv", promotion_rows, manifest_fields() + ["promotion_status", "promotion_reason", "promotion_component_id", "not_promoted", "coverage_status", "fine_availability"])
        write_csv(profile_dir / "chunk_manifest.csv", raw_result.chunk_rows, ["chunk_id", "start_sample", "end_sample_exclusive", "bytes_read", "covered_window_start_id", "covered_window_end_id", "covered_window_count", "reused_samples_within_covered_windows", "chunk_wall_clock_s", "raw_read_status", "error"])
        projection = project_budget({int(row["window_id"]) for row in promotion_rows if row["promotion_status"] == "coarse_promoted"}, components, {row.window_id for row in rows})
        write_json(profile_dir / "cost_measurement.json", {**raw_result.cost, "profile_id": profile.profile_id, "promotion_fraction": sum(row["promotion_status"] == "coarse_promoted" for row in promotion_rows) / len(promotion_rows), "component_count": len(components), "potential_fine_window_count": projection["potential_fine_window_count"], "budget_projection": projection["budget_projection"], "parameter_hash": PARAMETER_HASH})
        write_json(profile_dir / "run_manifest.json", {"task_id": task.task_id, "profile_id": profile.profile_id, "stage0_window_count": len(rows), "coarse_only": True, "stage1_output_written": False, "stage2_stage3_stage4_executed": False, "gold_labels_used_for_selection": False, "parameter_hash": PARAMETER_HASH})
        phase_b_result = {"task_id": task.task_id, "profile_id": profile.profile_id, "N0": len(rows), "promotion_fraction": sum(row["promotion_status"] == "coarse_promoted" for row in promotion_rows) / len(promotion_rows), "component_count": len(components), "potential_fine_window_count": projection["potential_fine_window_count"], "budget_projection": projection["budget_projection"], "cost": raw_result.cost}
    run_manifest = {
        "planner_version": PLANNER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "parameter_hash": PARAMETER_HASH,
        "phase_a_tasks": [task.task_id for task in TASKS[:2]],
        "phase_b_executed": phase_b_result is not None,
        "phase_b_result": phase_b_result,
        "matlab_called": False,
        "sage_called": False,
        "stage1_output_written": False,
        "stage2_stage3_stage4_executed": False,
        "gold_labels_used_for_selection": False,
        "output_namespace": str(output_root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    write_json(output_root / "run_manifest.json", run_manifest)
    return {"phase_a_summary": phase_a_summary, "phase_a_gate": phase_a_gate, "phase_a_cost_gate": phase_a_cost_gate, "phase_b_result": phase_b_result, "output_root": output_root, "parameter_hash": PARAMETER_HASH}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-root", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    output_root = args.output_root.resolve() if args.output_root else project_root / OUTPUT_NAMESPACE
    result = run(project_root, output_root)
    print(f"RAW_COARSE_PHASE_A_COMPLETED output={result['output_root']}")
    print(f"PARAMETER_HASH={result['parameter_hash']}")
    print(f"G11_ALLOWED={result['phase_a_gate']['g11_allowed']}")
    for row in result["phase_a_summary"]:
        print(f"{row['task_id']} {row['profile_id']} center={row.get('known_event_center_recall')} closure={row.get('known_event_pm2_closure_recall')} promotion={row['promotion_fraction']:.6f} fine_potential={row['potential_fine_window_count']} wall_s={row['wall_clock_s_shared_task_pass']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
