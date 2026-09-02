"""Pure-Python signal primitives for the isolated VTC validation study.

This module is intentionally independent of the frozen production pipeline.  It
never invokes MATLAB and writes nothing unless a layer runner explicitly asks it
to write inside the validation namespace.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


SAMPLE_RATE_HZ = 10_230_000.0


@dataclass(frozen=True)
class PathEstimate:
    delay_samples: float
    doppler_hz: float


@dataclass(frozen=True)
class SignalContext:
    n: int
    local_code_fft: np.ndarray
    signed_bins: np.ndarray
    time_seconds: np.ndarray


@dataclass(frozen=True)
class EstimatorConfig:
    maximum_model_order: int
    delay_step_samples: float
    minimum_path_separation_samples: float
    local_delay_half_width_samples: float
    local_doppler_step_hz: float
    local_doppler_half_width_hz: float
    maximum_excess_delay_samples: float
    minimum_path_power_db: float
    maximum_path_coherence: float
    minimum_sequential_bic_gain: float
    minimum_joint_snapshot_wins: int
    sage_iterations: int
    sage_tolerance: float


@dataclass(frozen=True)
class ModelFit:
    paths: list[PathEstimate]
    rss: float
    bic: float
    valid: bool
    relative_power_db: np.ndarray
    minimum_multipath_power_db: float
    maximum_relative_doppler_hz: float
    maximum_coherence: float
    snapshot_rss: np.ndarray
    snapshot_wins: int


@dataclass(frozen=True)
class JointResult:
    models: list[ModelFit]
    selected_order: int
    selected: ModelFit
    joint_valid: bool
    joint_rss: float
    joint_bic: float
    snapshot_wins: int


@dataclass(frozen=True)
class MatchingTolerances:
    delay_samples: float
    doppler_hz: float
    power_db: float


@dataclass(frozen=True)
class PathMatch:
    found: bool
    delay_error_samples: float
    doppler_error_hz: float
    power_error_db: float
    cost: float
    path_index: int


@dataclass(frozen=True)
class ValidationCase:
    scene_id: str
    prn_label: str
    prn: int
    environment: str
    center_window_id: int
    raw_file: Path
    snapshots: list[dict[str, Any]]
    direct_path: PathEstimate
    native_paths: list[PathEstimate]
    native_relative_power_db: list[float]
    doppler_bound_hz: float
    contexts: list[SignalContext]
    sample_count: int


def source_path(contract: dict[str, Any], role: str) -> Path:
    matches = [item for item in contract["source_paths"] if item["role"] == role]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one contract source for role {role}")
    return Path(matches[0]["path"])


def estimator_from_contract(contract: dict[str, Any]) -> EstimatorConfig:
    values = contract["estimator"]
    return EstimatorConfig(
        maximum_model_order=int(values["maximum_model_order"]),
        delay_step_samples=float(values["delay_step_samples"]),
        minimum_path_separation_samples=float(values["minimum_path_separation_samples"]),
        local_delay_half_width_samples=float(values["local_delay_half_width_samples"]),
        local_doppler_step_hz=float(values["local_doppler_step_hz"]),
        local_doppler_half_width_hz=float(values["local_doppler_half_width_hz"]),
        maximum_excess_delay_samples=30.0,
        minimum_path_power_db=float(values["minimum_path_power_db"]),
        maximum_path_coherence=float(values["maximum_path_coherence"]),
        minimum_sequential_bic_gain=float(values["minimum_sequential_bic_gain"]),
        minimum_joint_snapshot_wins=int(values["minimum_joint_snapshot_wins"]),
        sage_iterations=int(values["sage_iterations"]),
        sage_tolerance=float(values["sage_tolerance"]),
    )


def tolerances_from_contract(contract: dict[str, Any]) -> MatchingTolerances:
    values = contract["matching"]
    return MatchingTolerances(
        delay_samples=float(values["delay_tolerance_samples"]),
        doppler_hz=float(values["doppler_tolerance_hz"]),
        power_db=float(values["power_tolerance_db"]),
    )


def prepare_case(contract: dict[str, Any], case_json: dict[str, Any]) -> ValidationCase:
    scene_id = str(case_json["scene_id"])
    prn_label = str(case_json["prn_label"])
    center_window_id = int(case_json["center_window_id"])
    output_namespace = Path(contract["output_namespace"])
    project_root = output_namespace.parents[3]
    stage0_path = (
        project_root / "scenes" / scene_id / "sage_results" / "nav_sage_v2"
        / prn_label / "stage0_valid_40ms_windows.csv"
    )
    with stage0_path.open("r", encoding="utf-8-sig", newline="") as handle:
        center_rows = [
            row for row in csv.DictReader(handle)
            if int(row["window_id"]) == center_window_id
        ]
    if len(center_rows) != 1:
        raise ValueError(f"expected one Stage0 row for center window {center_window_id}")
    snapshots = list(case_json["five_snapshot_symbols"])
    sample_count = int(contract["samples_per_20ms"])
    center_code_frequency_hz = float(snapshots[2]["code_frequency_hz"])
    context = make_signal_context(
        int(case_json["prn"]), center_code_frequency_hz, sample_count,
        float(contract["sample_rate_hz"]),
    )
    native_json = list(case_json["native_stage4_paths"])
    direct_json = next(item for item in native_json if not bool(item["is_multipath"]))
    direct_path = PathEstimate(
        delay_samples=float(direct_json["delay_samples"]),
        doppler_hz=float(direct_json["doppler_hz"]),
    )
    native_paths = [
        PathEstimate(float(item["delay_samples"]), float(item["doppler_hz"]))
        for item in native_json
    ]
    native_relative_power_db = [float(item["mean_relative_power_db"]) for item in native_json]
    return ValidationCase(
        scene_id=scene_id,
        prn_label=prn_label,
        prn=int(case_json["prn"]),
        environment=str(case_json["environment"]),
        center_window_id=center_window_id,
        raw_file=source_path(contract, f"{prn_label}_raw_iq"),
        snapshots=snapshots,
        direct_path=direct_path,
        native_paths=native_paths,
        native_relative_power_db=native_relative_power_db,
        doppler_bound_hz=float(center_rows[0]["relative_doppler_bound_hz"]),
        contexts=[context] * len(snapshots),
        sample_count=sample_count,
    )


def generate_gps_ca_code(prn: int) -> np.ndarray:
    taps = (
        (2, 6), (3, 7), (4, 8), (5, 9), (1, 9), (2, 10), (1, 8), (2, 9),
        (3, 10), (2, 3), (3, 4), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10),
        (1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (6, 9), (1, 3), (4, 6),
        (5, 7), (6, 8), (7, 9), (8, 10), (1, 6), (2, 7), (3, 8), (4, 9),
    )
    if not 1 <= prn <= len(taps):
        raise ValueError(f"unsupported GPS PRN: {prn}")
    tap_a, tap_b = taps[prn - 1]
    g1 = np.full(10, -1.0)
    g2 = np.full(10, -1.0)
    code = np.empty(1023, dtype=np.float64)
    for index in range(1023):
        code[index] = g1[9] * g2[tap_a - 1] * g2[tap_b - 1]
        g1_feedback = g1[2] * g1[9]
        g2_feedback = g2[1] * g2[2] * g2[5] * g2[7] * g2[8] * g2[9]
        g1[1:] = g1[:-1]
        g1[0] = g1_feedback
        g2[1:] = g2[:-1]
        g2[0] = g2_feedback
    return code


def signed_fft_bins(n: int) -> np.ndarray:
    if n <= 0:
        raise ValueError("FFT length must be positive")
    if n % 2 == 0:
        return np.concatenate((np.arange(0, n // 2), np.arange(-n // 2, 0))).astype(float)
    half = (n - 1) // 2
    return np.concatenate((np.arange(0, half + 1), np.arange(-half, 0))).astype(float)


def make_grid(minimum: float, maximum: float, step: float) -> np.ndarray:
    if step <= 0:
        raise ValueError("grid step must be positive")
    if maximum < minimum:
        return np.array([minimum], dtype=float)
    count = int(np.floor((maximum - minimum) / step + 1e-12))
    values = minimum + step * np.arange(count + 1, dtype=float)
    if values.size == 0 or values[-1] < maximum - 1e-9:
        values = np.append(values, maximum)
    return values


def make_signal_context(
    prn: int,
    code_frequency_hz: float,
    n: int,
    sample_rate_hz: float = SAMPLE_RATE_HZ,
) -> SignalContext:
    if not np.isfinite(code_frequency_hz) or code_frequency_hz <= 0:
        code_frequency_hz = 1_023_000.0
    chips = generate_gps_ca_code(prn)
    sample_index = np.arange(n, dtype=float)
    chip_phase = np.mod(sample_index * code_frequency_hz / sample_rate_hz, 1023.0)
    local_code = chips[np.floor(chip_phase).astype(np.int64)]
    return SignalContext(
        n=n,
        local_code_fft=np.fft.fft(local_code),
        signed_bins=signed_fft_bins(n),
        time_seconds=sample_index / sample_rate_hz,
    )


def make_replica(delay_samples: float, doppler_hz: float, context: SignalContext) -> np.ndarray:
    phase = np.exp(-1j * 2.0 * np.pi * context.signed_bins * delay_samples / context.n)
    shifted_code = np.fft.ifft(context.local_code_fft * phase)
    return shifted_code * np.exp(1j * 2.0 * np.pi * doppler_hz * context.time_seconds)


def build_replicas(paths: list[PathEstimate], context: SignalContext) -> np.ndarray:
    if not paths:
        return np.empty((context.n, 0), dtype=np.complex128)
    return np.column_stack(
        [make_replica(path.delay_samples, path.doppler_hz, context) for path in paths]
    )


def solve_snapshot_alpha(
    paths: list[PathEstimate], observed: np.ndarray, context: SignalContext
) -> np.ndarray:
    replicas = build_replicas(paths, context)
    return np.linalg.lstsq(replicas, observed, rcond=None)[0]


def solve_all_snapshot_alpha(
    paths: list[PathEstimate],
    observations: list[np.ndarray],
    contexts: list[SignalContext],
) -> np.ndarray:
    if all(context is contexts[0] for context in contexts):
        replicas = build_replicas(paths, contexts[0])
        observed_matrix = np.column_stack(observations)
        return np.linalg.lstsq(replicas, observed_matrix, rcond=None)[0]
    return np.column_stack([
        solve_snapshot_alpha(paths, observed, context)
        for observed, context in zip(observations, contexts, strict=True)
    ])


def synthesize(paths: list[PathEstimate], alpha: np.ndarray, context: SignalContext) -> np.ndarray:
    return build_replicas(paths, context) @ alpha


def residual_rss(
    observed: np.ndarray, paths: list[PathEstimate], alpha: np.ndarray, context: SignalContext
) -> float:
    residual = observed - synthesize(paths, alpha, context)
    return float(np.real(np.vdot(residual, residual)))


def replica_coherence(paths: list[PathEstimate], context: SignalContext) -> float:
    if len(paths) < 2:
        return 0.0
    replicas = build_replicas(paths, context)
    norms = np.maximum(np.sqrt(np.sum(np.abs(replicas) ** 2, axis=0)), np.finfo(float).eps)
    normalized = replicas / norms
    matrix = np.abs(normalized.conj().T @ normalized)
    np.fill_diagonal(matrix, 0.0)
    return float(np.max(matrix))


def evaluate_joint_model(
    paths: list[PathEstimate],
    observations: list[np.ndarray],
    contexts: list[SignalContext],
    doppler_bound_hz: float,
    config: EstimatorConfig,
) -> ModelFit:
    ordered = sorted(paths, key=lambda path: path.delay_samples)
    alpha_matrix = solve_all_snapshot_alpha(ordered, observations, contexts)
    path_power = np.abs(alpha_matrix.T) ** 2
    snapshot_rss = np.empty(len(observations), dtype=float)
    if all(context is contexts[0] for context in contexts):
        replicas = build_replicas(ordered, contexts[0])
        residuals = np.column_stack(observations) - replicas @ alpha_matrix
        snapshot_rss[:] = np.real(np.sum(np.conj(residuals) * residuals, axis=0))
    else:
        for snapshot, (observed, context) in enumerate(zip(observations, contexts, strict=True)):
            snapshot_rss[snapshot] = residual_rss(
                observed, ordered, alpha_matrix[:, snapshot], context
            )
    rss = float(np.sum(snapshot_rss))
    n = len(observations) * observations[0].size
    order = len(ordered)
    parameter_count = 2 * order + 2 * len(observations) * order + 1
    bic = float(
        2 * n * np.log(max(rss / n, np.finfo(float).tiny))
        + parameter_count * np.log(2 * n)
    )
    mean_power = np.mean(path_power, axis=0)
    relative_power_db = 10.0 * np.log10(
        np.maximum(mean_power, np.finfo(float).tiny)
        / max(float(mean_power[0]), np.finfo(float).tiny)
    )
    if order == 1:
        minimum_power = float("nan")
        maximum_relative_doppler = 0.0
        minimum_separation = float("nan")
    else:
        minimum_power = float(np.min(relative_power_db[1:]))
        maximum_relative_doppler = float(
            np.max(np.abs(np.array([path.doppler_hz for path in ordered[1:]]) - ordered[0].doppler_hz))
        )
        minimum_separation = float(np.min(np.diff([path.delay_samples for path in ordered])))
    coherence = replica_coherence(ordered, contexts[0])
    valid = bool(np.isfinite(rss) and np.isfinite(bic))
    if order > 1:
        valid = bool(
            valid
            and minimum_power >= config.minimum_path_power_db
            and maximum_relative_doppler <= doppler_bound_hz + 1e-6
            and minimum_separation >= config.minimum_path_separation_samples - 1e-6
            and coherence <= config.maximum_path_coherence
        )
    if order == 1:
        snapshot_wins = len(observations)
    else:
        one_alpha = solve_all_snapshot_alpha([ordered[0]], observations, contexts)
        one_path_rss = []
        for snapshot, (observed, context) in enumerate(zip(observations, contexts, strict=True)):
            one_path_rss.append(
                residual_rss(observed, [ordered[0]], one_alpha[:, snapshot], context)
            )
        snapshot_wins = int(np.count_nonzero(snapshot_rss < np.asarray(one_path_rss)))
    return ModelFit(
        paths=ordered,
        rss=rss,
        bic=bic,
        valid=valid,
        relative_power_db=relative_power_db,
        minimum_multipath_power_db=minimum_power,
        maximum_relative_doppler_hz=maximum_relative_doppler,
        maximum_coherence=coherence,
        snapshot_rss=snapshot_rss,
        snapshot_wins=snapshot_wins,
    )


def initialize_residual_path(
    residuals: list[np.ndarray],
    existing: list[PathEstimate],
    contexts: list[SignalContext],
    doppler_bound_hz: float,
    config: EstimatorConfig,
) -> PathEstimate:
    earliest_delay = min(path.delay_samples for path in existing)
    delay_minimum = float(np.ceil(earliest_delay + config.minimum_path_separation_samples))
    delay_maximum = float(np.floor(earliest_delay + config.maximum_excess_delay_samples))
    delays = make_grid(delay_minimum, delay_maximum, 1.0)
    dopplers = make_grid(
        existing[0].doppler_hz - doppler_bound_hz,
        existing[0].doppler_hz + doppler_bound_hz,
        50.0,
    )
    scores = np.zeros((delays.size, dopplers.size), dtype=float)
    for doppler_index, doppler in enumerate(dopplers):
        for residual, context in zip(residuals, contexts, strict=True):
            wiped = residual * np.exp(-1j * 2.0 * np.pi * doppler * context.time_seconds)
            correlation = np.fft.ifft(np.fft.fft(wiped) * np.conj(context.local_code_fft))
            indices = np.mod(np.rint(delays).astype(np.int64), context.n)
            scores[:, doppler_index] += np.abs(correlation[indices]) ** 2 / context.n
    flat_order = np.argsort(scores, axis=None)[::-1]
    for flat_index in flat_order:
        delay_index, doppler_index = np.unravel_index(flat_index, scores.shape)
        candidate = PathEstimate(float(delays[delay_index]), float(dopplers[doppler_index]))
        if all(
            abs(candidate.delay_samples - path.delay_samples)
            >= config.minimum_path_separation_samples - 1e-9
            for path in existing
        ):
            return candidate
    raise ValueError("no separated residual path was found")


def refine_joint_path(
    path: PathEstimate,
    observations: list[np.ndarray],
    contexts: list[SignalContext],
    doppler_bound_hz: float,
    config: EstimatorConfig,
) -> PathEstimate:
    delay_grid = make_grid(
        path.delay_samples - config.local_delay_half_width_samples,
        path.delay_samples + config.local_delay_half_width_samples,
        config.delay_step_samples,
    )
    scores = np.zeros(delay_grid.size, dtype=float)
    shared_context = all(context is contexts[0] for context in contexts)
    for index, delay in enumerate(delay_grid):
        if shared_context:
            replica = make_replica(float(delay), path.doppler_hz, contexts[0])
            denominator = max(float(np.real(np.vdot(replica, replica))), np.finfo(float).eps)
            scores[index] = sum(abs(np.vdot(replica, observed)) ** 2 for observed in observations) / denominator
        else:
            for observed, context in zip(observations, contexts, strict=True):
                replica = make_replica(float(delay), path.doppler_hz, context)
                scores[index] += abs(np.vdot(replica, observed)) ** 2 / max(
                    float(np.real(np.vdot(replica, replica))), np.finfo(float).eps
                )
    delay = float(delay_grid[int(np.argmax(scores))])
    doppler_grid = make_grid(
        max(path.doppler_hz - config.local_doppler_half_width_hz, path.doppler_hz - doppler_bound_hz),
        min(path.doppler_hz + config.local_doppler_half_width_hz, path.doppler_hz + doppler_bound_hz),
        config.local_doppler_step_hz,
    )
    scores = np.zeros(doppler_grid.size, dtype=float)
    for index, doppler in enumerate(doppler_grid):
        if shared_context:
            replica = make_replica(delay, float(doppler), contexts[0])
            denominator = max(float(np.real(np.vdot(replica, replica))), np.finfo(float).eps)
            scores[index] = sum(abs(np.vdot(replica, observed)) ** 2 for observed in observations) / denominator
        else:
            for observed, context in zip(observations, contexts, strict=True):
                replica = make_replica(delay, float(doppler), context)
                scores[index] += abs(np.vdot(replica, observed)) ** 2 / max(
                    float(np.real(np.vdot(replica, replica))), np.finfo(float).eps
                )
    return PathEstimate(delay, float(doppler_grid[int(np.argmax(scores))]))


def run_sage(
    paths: list[PathEstimate],
    observations: list[np.ndarray],
    contexts: list[SignalContext],
    doppler_bound_hz: float,
    config: EstimatorConfig,
) -> list[PathEstimate]:
    current_paths = list(paths)
    previous_rss = float("inf")
    for iteration in range(config.sage_iterations):
        for path_index in range(len(current_paths)):
            other_indices = [index for index in range(len(current_paths)) if index != path_index]
            hidden = []
            alpha_matrix = solve_all_snapshot_alpha(current_paths, observations, contexts)
            for snapshot, (observed, context) in enumerate(zip(observations, contexts, strict=True)):
                if not other_indices:
                    hidden.append(observed)
                else:
                    other_paths = [current_paths[index] for index in other_indices]
                    hidden.append(
                        observed - synthesize(
                            other_paths, alpha_matrix[other_indices, snapshot], context
                        )
                    )
            current_paths[path_index] = refine_joint_path(
                current_paths[path_index], hidden, contexts, doppler_bound_hz, config
            )
        current_paths.sort(key=lambda item: item.delay_samples)
        current = evaluate_joint_model(
            current_paths, observations, contexts, doppler_bound_hz, config
        )
        if iteration > 0 and abs(previous_rss - current.rss) / max(
            previous_rss, np.finfo(float).eps
        ) < config.sage_tolerance:
            break
        previous_rss = current.rss
    return current_paths


def estimate_joint(
    observations: list[np.ndarray],
    direct_path: PathEstimate,
    contexts: list[SignalContext],
    doppler_bound_hz: float,
    config: EstimatorConfig,
) -> JointResult:
    models = [
        evaluate_joint_model([direct_path], observations, contexts, doppler_bound_hz, config)
    ]
    for _order in range(2, config.maximum_model_order + 1):
        previous = models[-1]
        if not previous.valid or not previous.paths:
            break
        residuals = []
        alpha_matrix = solve_all_snapshot_alpha(previous.paths, observations, contexts)
        for snapshot, (observed, context) in enumerate(zip(observations, contexts, strict=True)):
            residuals.append(
                observed - synthesize(previous.paths, alpha_matrix[:, snapshot], context)
            )
        new_path = initialize_residual_path(
            residuals, previous.paths, contexts, doppler_bound_hz, config
        )
        paths = run_sage(
            sorted(previous.paths + [new_path], key=lambda item: item.delay_samples),
            observations,
            contexts,
            doppler_bound_hz,
            config,
        )
        models.append(evaluate_joint_model(paths, observations, contexts, doppler_bound_hz, config))
    selected_index = 0
    for index in range(1, len(models)):
        previous = models[selected_index]
        current = models[index]
        bic_gain = previous.bic - current.bic
        if (
            current.valid
            and bic_gain >= config.minimum_sequential_bic_gain
            and current.snapshot_wins >= config.minimum_joint_snapshot_wins
        ):
            selected_index = index
        else:
            break
    selected = models[selected_index]
    return JointResult(
        models=models,
        selected_order=selected_index + 1,
        selected=selected,
        joint_valid=selected.valid,
        joint_rss=selected.rss,
        joint_bic=selected.bic,
        snapshot_wins=selected.snapshot_wins,
    )


def read_iq(filename: str | Path, start_sample: int, sample_count: int) -> np.ndarray:
    if start_sample < 0 or sample_count <= 0:
        raise ValueError("invalid raw-IQ interval")
    raw = np.fromfile(
        Path(filename), dtype="<i2", count=2 * sample_count, offset=start_sample * 4
    )
    if raw.size != 2 * sample_count:
        raise ValueError(f"short raw-IQ read at sample {start_sample}")
    values = raw.astype(np.float64, copy=False)
    return values[0::2] + 1j * values[1::2]


def normalize_signal(observed: np.ndarray) -> np.ndarray:
    centered = np.asarray(observed, dtype=np.complex128) - np.mean(observed)
    rms = float(np.sqrt(np.mean(np.abs(centered) ** 2)))
    if not np.isfinite(rms) or rms <= 0:
        raise ValueError("invalid IQ signal power")
    return centered / rms


def load_observations(case: ValidationCase) -> tuple[list[np.ndarray], list[dict[str, int]]]:
    observations: list[np.ndarray] = []
    read_info: list[dict[str, int]] = []
    for snapshot in case.snapshots:
        start = int(snapshot["sample_start_zero_based"])
        observed = read_iq(case.raw_file, start, case.sample_count)
        observed = float(snapshot["nav_symbol"]) * observed
        observations.append(normalize_signal(observed))
        read_info.append(
            {
                "sample_start_zero_based": start,
                "sample_count": case.sample_count,
                "nav_symbol": int(snapshot["nav_symbol"]),
            }
        )
    return observations, read_info


def inject_observations(
    base_observations: list[np.ndarray],
    case: ValidationCase,
    excess_delay_samples: float,
    relative_doppler_hz: float,
    relative_power_db: float,
    phase_rad: float,
) -> list[np.ndarray]:
    ratio = 10.0 ** (relative_power_db / 20.0)
    center_time = float(case.snapshots[2]["recording_time_s"])
    injected: list[np.ndarray] = []
    shared_context = all(context is case.contexts[0] for context in case.contexts)
    direct_replica_shared = make_replica(
        case.direct_path.delay_samples, case.direct_path.doppler_hz, case.contexts[0]
    ) if shared_context else None
    secondary_shared = make_replica(
        case.direct_path.delay_samples + excess_delay_samples,
        case.direct_path.doppler_hz + relative_doppler_hz,
        case.contexts[0],
    ) if shared_context else None
    for observed, snapshot, context in zip(
        base_observations, case.snapshots, case.contexts, strict=True
    ):
        direct_replica = direct_replica_shared if shared_context else make_replica(
            case.direct_path.delay_samples, case.direct_path.doppler_hz, context
        )
        direct_alpha = np.linalg.lstsq(
            direct_replica.reshape(-1, 1), observed, rcond=None
        )[0][0]
        elapsed = float(snapshot["recording_time_s"]) - center_time
        phase_at_snapshot = phase_rad + 2.0 * np.pi * relative_doppler_hz * elapsed
        secondary = secondary_shared if shared_context else make_replica(
            case.direct_path.delay_samples + excess_delay_samples,
            case.direct_path.doppler_hz + relative_doppler_hz,
            context,
        )
        secondary_alpha = direct_alpha * ratio * np.exp(1j * phase_at_snapshot)
        injected.append(observed + secondary * secondary_alpha)
    return injected


def match_injected(
    selected: ModelFit,
    truth_excess_delay_samples: float,
    truth_relative_doppler_hz: float,
    truth_relative_power_db: float,
    tolerances: MatchingTolerances,
) -> PathMatch:
    return _match_path(
        selected,
        truth_excess_delay_samples,
        truth_relative_doppler_hz,
        truth_relative_power_db,
        tolerances,
    )


def match_native(
    selected: ModelFit,
    native_path: PathEstimate,
    direct_reference: PathEstimate,
    native_relative_power_db: float,
    tolerances: MatchingTolerances,
) -> PathMatch:
    return _match_path(
        selected,
        native_path.delay_samples - direct_reference.delay_samples,
        native_path.doppler_hz - direct_reference.doppler_hz,
        native_relative_power_db,
        tolerances,
    )


def match_injected_and_native(
    selected: ModelFit,
    injected_truth: tuple[float, float, float],
    native_path: PathEstimate,
    direct_reference: PathEstimate,
    native_relative_power_db: float,
    tolerances: MatchingTolerances,
) -> tuple[PathMatch, PathMatch]:
    if len(selected.paths) < 3:
        injected = match_injected(selected, *injected_truth, tolerances)
        native = match_native(
            selected, native_path, direct_reference, native_relative_power_db, tolerances
        )
        if injected.path_index >= 0 and injected.path_index == native.path_index:
            if injected.cost <= native.cost:
                native = PathMatch(
                    False, native.delay_error_samples, native.doppler_error_hz,
                    native.power_error_db, native.cost, native.path_index,
                )
            else:
                injected = PathMatch(
                    False, injected.delay_error_samples, injected.doppler_error_hz,
                    injected.power_error_db, injected.cost, injected.path_index,
                )
        return injected, native

    direct = selected.paths[0]
    native_truth = (
        native_path.delay_samples - direct_reference.delay_samples,
        native_path.doppler_hz - direct_reference.doppler_hz,
        native_relative_power_db,
    )

    def candidate(path_index: int, truth: tuple[float, float, float]) -> PathMatch:
        path = selected.paths[path_index]
        delay_error = path.delay_samples - direct.delay_samples - truth[0]
        doppler_error = path.doppler_hz - direct.doppler_hz - truth[1]
        power_error = float(selected.relative_power_db[path_index]) - truth[2]
        cost = (
            abs(delay_error) / tolerances.delay_samples
            + abs(doppler_error) / tolerances.doppler_hz
            + abs(power_error) / tolerances.power_db
        )
        found = bool(
            abs(delay_error) <= tolerances.delay_samples
            and abs(doppler_error) <= tolerances.doppler_hz
            and abs(power_error) <= tolerances.power_db
        )
        return PathMatch(found, delay_error, doppler_error, power_error, cost, path_index)

    pairs = []
    for injected_index in range(1, len(selected.paths)):
        for native_index in range(1, len(selected.paths)):
            if injected_index == native_index:
                continue
            injected = candidate(injected_index, injected_truth)
            native = candidate(native_index, native_truth)
            pairs.append((injected.cost + native.cost, injected, native))
    _, injected, native = min(pairs, key=lambda item: item[0])
    return injected, native


def _match_path(
    selected: ModelFit,
    truth_excess_delay_samples: float,
    truth_relative_doppler_hz: float,
    truth_relative_power_db: float,
    tolerances: MatchingTolerances,
) -> PathMatch:
    if len(selected.paths) < 2:
        return PathMatch(False, float("nan"), float("nan"), float("nan"), float("nan"), -1)
    direct = selected.paths[0]
    candidates: list[PathMatch] = []
    for index, path in enumerate(selected.paths[1:], start=1):
        delay_error = (
            path.delay_samples - direct.delay_samples - truth_excess_delay_samples
        )
        doppler_error = (
            path.doppler_hz - direct.doppler_hz - truth_relative_doppler_hz
        )
        power_error = float(selected.relative_power_db[index]) - truth_relative_power_db
        cost = (
            abs(delay_error) / tolerances.delay_samples
            + abs(doppler_error) / tolerances.doppler_hz
            + abs(power_error) / tolerances.power_db
        )
        candidates.append(
            PathMatch(True, delay_error, doppler_error, power_error, cost, index)
        )
    best = min(candidates, key=lambda match: match.cost)
    found = bool(
        abs(best.delay_error_samples) <= tolerances.delay_samples
        and abs(best.doppler_error_hz) <= tolerances.doppler_hz
        and abs(best.power_error_db) <= tolerances.power_db
    )
    return PathMatch(
        found,
        best.delay_error_samples,
        best.doppler_error_hz,
        best.power_error_db,
        best.cost,
        best.path_index,
    )


def cancel_secondary(
    observed: np.ndarray,
    context: SignalContext,
    paths: list[PathEstimate],
    alpha: np.ndarray,
    delay_error_samples: float,
    doppler_error_hz: float,
    power_error_db: float,
) -> np.ndarray:
    residual = np.asarray(observed, dtype=np.complex128).copy()
    for index, path in enumerate(paths[1:], start=1):
        adjusted = PathEstimate(
            path.delay_samples + delay_error_samples,
            path.doppler_hz + doppler_error_hz,
        )
        adjusted_alpha = alpha[index] * 10.0 ** (power_error_db / 20.0)
        residual -= make_replica(
            adjusted.delay_samples, adjusted.doppler_hz, context
        ) * adjusted_alpha
    return residual


def dll_zero_crossing(
    signal: np.ndarray,
    context: SignalContext,
    direct_path: PathEstimate,
    spacing_chips: float,
    offset_grid_chips: np.ndarray,
    samples_per_chip: float = 10.0,
) -> tuple[float, np.ndarray, bool]:
    offsets = np.asarray(offset_grid_chips, dtype=float)
    early_delays = direct_path.delay_samples + (
        offsets - spacing_chips / 2.0
    ) * samples_per_chip
    late_delays = direct_path.delay_samples + (
        offsets + spacing_chips / 2.0
    ) * samples_per_chip
    all_delays = np.concatenate((early_delays, late_delays))
    oversampling = None
    for candidate in (1, 2, 4, 5, 10, 20, 50, 100):
        if np.max(np.abs(all_delays * candidate - np.rint(all_delays * candidate))) < 1e-7:
            oversampling = candidate
            break
    if oversampling is None:
        return dll_zero_crossing_reference(
            signal, context, direct_path, spacing_chips, offsets, samples_per_chip
        )

    wiped = signal * np.exp(
        -1j * 2.0 * np.pi * direct_path.doppler_hz * context.time_seconds
    )
    spectrum = np.fft.fft(wiped) * np.conj(context.local_code_fft)
    padded_length = context.n * oversampling
    padded = np.zeros(padded_length, dtype=np.complex128)
    positive_count = (context.n + 1) // 2
    negative_count = context.n - positive_count
    padded[:positive_count] = spectrum[:positive_count]
    if negative_count:
        padded[-negative_count:] = spectrum[positive_count:]
    correlation = np.fft.ifft(padded) * oversampling
    indices = np.mod(np.rint(all_delays * oversampling).astype(np.int64), padded_length)
    values = np.abs(correlation[indices])
    discriminator = values[: offsets.size] - values[offsets.size :]
    return _zero_crossing_from_discriminator(offsets, discriminator)


def dll_zero_crossing_reference(
    signal: np.ndarray,
    context: SignalContext,
    direct_path: PathEstimate,
    spacing_chips: float,
    offset_grid_chips: np.ndarray,
    samples_per_chip: float = 10.0,
) -> tuple[float, np.ndarray, bool]:
    offsets = np.asarray(offset_grid_chips, dtype=float)
    discriminator = np.empty(offsets.size, dtype=float)
    for index, offset in enumerate(offsets):
        early_delay = direct_path.delay_samples + (offset - spacing_chips / 2.0) * samples_per_chip
        late_delay = direct_path.delay_samples + (offset + spacing_chips / 2.0) * samples_per_chip
        early = make_replica(early_delay, direct_path.doppler_hz, context)
        late = make_replica(late_delay, direct_path.doppler_hz, context)
        discriminator[index] = abs(np.vdot(early, signal)) - abs(np.vdot(late, signal))
    return _zero_crossing_from_discriminator(offsets, discriminator)


def _zero_crossing_from_discriminator(
    offsets: np.ndarray, discriminator: np.ndarray
) -> tuple[float, np.ndarray, bool]:
    crossing_indices = np.flatnonzero(discriminator[:-1] * discriminator[1:] <= 0)
    if crossing_indices.size == 0:
        nearest = int(np.argmin(np.abs(discriminator)))
        return float(offsets[nearest]), discriminator, False
    midpoints = (offsets[crossing_indices] + offsets[crossing_indices + 1]) / 2.0
    crossing_index = int(crossing_indices[np.argmin(np.abs(midpoints))])
    x1, x2 = offsets[crossing_index : crossing_index + 2]
    y1, y2 = discriminator[crossing_index : crossing_index + 2]
    if y2 == y1:
        crossing = (x1 + x2) / 2.0
    else:
        crossing = x1 - y1 * (x2 - x1) / (y2 - y1)
    return float(crossing), discriminator, bool(np.isfinite(crossing))
