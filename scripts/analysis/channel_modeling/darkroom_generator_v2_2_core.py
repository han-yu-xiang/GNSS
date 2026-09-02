"""Core for the v2.2 paired Good/Poor multi-elevation darkroom generator."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

try:
    from . import darkroom_generator_core as _v1
    from . import darkroom_generator_v2_core as _v2
    from . import darkroom_generator_v2_1_core as _v21
    from .darkroom_quality_profile_v2_2 import (
        GOOD_TRACKED_BASELINE,
        POOR_CONDITIONAL,
        QualityProfileRequest,
        generate_quality_timeline,
    )
except ImportError:
    from scripts.analysis.channel_modeling import darkroom_generator_core as _v1
    from scripts.analysis.channel_modeling import darkroom_generator_v2_core as _v2
    from scripts.analysis.channel_modeling import darkroom_generator_v2_1_core as _v21
    from scripts.analysis.channel_modeling.darkroom_quality_profile_v2_2 import (
        GOOD_TRACKED_BASELINE,
        POOR_CONDITIONAL,
        QualityProfileRequest,
        generate_quality_timeline,
    )


FINAL_COLUMNS: tuple[str, ...] = _v2.FINAL_COLUMNS
BAND_SEQUENCE: tuple[tuple[str, str], ...] = _v2.BAND_SEQUENCE
ENVIRONMENTS: tuple[str, ...] = tuple(_v2.ENVIRONMENTS)
ELEVATION_BANDS: tuple[str, ...] = ("LOW", "MID", "HIGH")
V22_RUN_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs"
V22_REQUEST_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_requests"
V22_MATRIX_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices"
NLOS_SLOT_IDS: tuple[int, ...] = (1, 2, 3)
ALL_ACTIVE_MASK = "111"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _resolve(project_root: Path, relative: str) -> Path:
    root = project_root.resolve()
    candidate = (root / str(relative)).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes project root: {relative}")
    return candidate


@dataclass(frozen=True)
class GeneratorV22Config:
    model_id: str
    generator_version: str
    sample_rate_hz: int
    time_step_ms: int
    path_parameter_block_ms: int
    environments: tuple[str, ...]
    elevation_bands: tuple[str, ...]
    source_payload: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.model_id != "darkroom-multi-elevation-four-slot-generator-v2-2":
            raise ValueError("unsupported v2.2 generator")
        if self.generator_version != "2.2.0":
            raise ValueError("unsupported v2.2 generator version")
        if self.sample_rate_hz != 10_230_000:
            raise ValueError("v2.2 supports only 10.23 MHz")
        if self.time_step_ms != 1 or self.path_parameter_block_ms != 40:
            raise ValueError("v2.2 requires 1 ms steps and 40 ms blocks")
        if self.environments != ENVIRONMENTS:
            raise ValueError("environment order is frozen")
        if self.elevation_bands != ELEVATION_BANDS:
            raise ValueError("all three elevation bands are required")


@dataclass(frozen=True)
class GenerationV22Request:
    request_id: str
    simulation_id: str
    pairing_id: str
    environment_class: str
    elevation_bands: tuple[str, ...]
    duration_ms: int
    master_seed: int
    quality_mode: str
    pre_event_guard_ms: int
    post_event_guard_ms: int
    entry_ramp_cap_ms: int
    output_namespace: str


@dataclass(frozen=True)
class V22SimulationResult:
    final_rows: tuple[dict[str, Any], ...]
    receiver_quality_rows: tuple[dict[str, Any], ...]
    quality_event_rows: tuple[dict[str, Any], ...]
    path_block_rows: tuple[dict[str, Any], ...]
    path_slot_rows: tuple[dict[str, Any], ...]
    random_stream_rows: tuple[dict[str, Any], ...]
    support_summary: Mapping[str, Any]


def load_v22_config(path: Path, project_root: Path) -> GeneratorV22Config:
    config_path = path.resolve()
    data = _read_json(config_path)
    if int(data.get("sample_rate_hz", 0)) != 10_230_000:
        raise ValueError("v2.2 supports only 10.23 MHz")
    if tuple(data.get("final_columns", ())) != FINAL_COLUMNS:
        raise ValueError("v2.2 final columns do not match the frozen contract")
    slot = data.get("slot_policy", {})
    if slot.get("nlos_activation_policy") != "ALL_THREE_SLOTS_ALWAYS_ACTIVE":
        raise ValueError("v2.2 NLOS activation contract mismatch")
    if slot.get("nlos_amplitude_constraint") != "STRICTLY_POSITIVE":
        raise ValueError("v2.2 NLOS positivity contract mismatch")
    if slot.get("conditional_multipath_scenario") is not True or slot.get("activation_model_used_for_generation") is not False:
        raise ValueError("v2.2 conditional slot contract mismatch")
    quality = data.get("quality_policy", {})
    if tuple(quality.get("quality_modes", ())) != (GOOD_TRACKED_BASELINE, POOR_CONDITIONAL):
        raise ValueError("v2.2 quality modes are not frozen")
    execution = data.get("execution_policy", {})
    for field_name in ("new_only",):
        if execution.get(field_name) is not True:
            raise ValueError(f"v2.2 execution policy requires {field_name}=true")
    for field_name in ("resume_allowed", "raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz", "gold_labels_used_for_generation"):
        if execution.get(field_name) is not False:
            raise ValueError(f"v2.2 execution policy requires {field_name}=false")
    parent = data.get("parent_v21_config")
    parent_core = data.get("parent_v21_core")
    if not isinstance(parent, Mapping) or not isinstance(parent_core, Mapping):
        raise ValueError("v2.1 parent provenance is missing")
    parent_path = _resolve(project_root, str(parent.get("relative_path", "")))
    parent_core_path = _resolve(project_root, str(parent_core.get("relative_path", "")))
    if not parent_path.is_file() or sha256_file(parent_path).lower() != str(parent.get("sha256", "")).lower():
        raise ValueError("v2.1 parent config hash mismatch")
    if not parent_core_path.is_file() or sha256_file(parent_core_path).lower() != str(parent_core.get("sha256", "")).lower():
        raise ValueError("v2.1 parent core hash mismatch")
    return GeneratorV22Config(
        model_id=str(data.get("generator_id", "")),
        generator_version=str(data.get("generator_version", "")),
        sample_rate_hz=int(data.get("sample_rate_hz", 0)),
        time_step_ms=int(data.get("time_step_ms", 0)),
        path_parameter_block_ms=int(data.get("path_parameter_block_ms", 0)),
        environments=tuple(data.get("environments", ())),
        elevation_bands=tuple(data.get("elevation_bands", ())),
        source_payload=data,
    )


def load_frozen_v22_parent_models(project_root: Path, config: GeneratorV22Config) -> tuple[Any, Any]:
    parent = config.source_payload["parent_v21_config"]
    parent_path = _resolve(project_root, str(parent["relative_path"]))
    parent_config = _v21.load_v21_config(parent_path, project_root)
    models = _v21.load_frozen_v21_parent_models(project_root, parent_config)
    expected = str(config.source_payload["parent_model_manifests"]["path"])
    if str(models.path_model_manifest_sha256).lower() != expected.lower():
        raise ValueError("v2.2 path parent manifest mismatch")
    return models, parent_config


def validate_v22_request(payload: Mapping[str, Any], config: GeneratorV22Config) -> GenerationV22Request:
    required = {
        "request_id", "simulation_id", "pairing_id", "generator_id", "environment_class", "elevation_bands",
        "duration_ms", "master_seed", "quality_mode", "pre_event_guard_ms", "post_event_guard_ms",
        "entry_ramp_cap_ms", "new_only", "resume_allowed", "raw_iq_read", "matlab", "sage", "batch",
        "process_20_46_mhz", "gold_labels_used_for_generation", "output_namespace",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"missing v2.2 request fields: {','.join(missing)}")
    if str(payload["generator_id"]) != config.model_id:
        raise ValueError("v2.2 generator_id mismatch")
    if not str(payload["request_id"]).strip() or not str(payload["simulation_id"]).strip() or not str(payload["pairing_id"]).strip():
        raise ValueError("request_id, simulation_id and pairing_id must be non-empty")
    if payload["environment_class"] not in config.environments:
        raise ValueError("unsupported environment_class")
    if tuple(payload["elevation_bands"]) != config.elevation_bands:
        raise ValueError("elevation_bands must be exactly LOW,MID,HIGH")
    if payload["quality_mode"] not in (GOOD_TRACKED_BASELINE, POOR_CONDITIONAL):
        raise ValueError("unsupported quality_mode")
    duration = payload["duration_ms"]
    seed = payload["master_seed"]
    if isinstance(duration, bool) or not isinstance(duration, (int, np.integer)) or int(duration) < 1:
        raise ValueError("duration_ms must be positive")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or int(seed) < 0:
        raise ValueError("master_seed must be non-negative")
    for field_name in ("pre_event_guard_ms", "post_event_guard_ms", "entry_ramp_cap_ms"):
        value = payload[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or int(value) < 0:
            raise ValueError(f"{field_name} must be non-negative")
    if int(payload["entry_ramp_cap_ms"]) < 1:
        raise ValueError("entry_ramp_cap_ms must be positive")
    if payload["new_only"] is not True:
        raise ValueError("new_only must be true")
    for field_name in ("resume_allowed", "raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz", "gold_labels_used_for_generation"):
        if payload[field_name] is not False:
            raise ValueError(f"{field_name} must be false")
    output = str(payload["output_namespace"]).replace("\\", "/")
    if not output.startswith(V22_RUN_ROOT + "/") or ".." in output.split("/") or output.split("/")[-1] != str(payload["request_id"]):
        raise ValueError("unsafe v2.2 output namespace")
    return GenerationV22Request(
        request_id=str(payload["request_id"]),
        simulation_id=str(payload["simulation_id"]),
        pairing_id=str(payload["pairing_id"]),
        environment_class=str(payload["environment_class"]),
        elevation_bands=tuple(payload["elevation_bands"]),
        duration_ms=int(duration),
        master_seed=int(seed),
        quality_mode=str(payload["quality_mode"]),
        pre_event_guard_ms=int(payload["pre_event_guard_ms"]),
        post_event_guard_ms=int(payload["post_event_guard_ms"]),
        entry_ramp_cap_ms=int(payload["entry_ramp_cap_ms"]),
        output_namespace=output,
    )


def _pair_rng(request: GenerationV22Request, band: str, scope_id: str, stream_name: str, registry: list[dict[str, Any]]) -> np.random.Generator:
    seed = _v1.derive_stream_seed(request.master_seed, request.pairing_id, request.environment_class, band, scope_id, stream_name)
    registry.append(
        {
            "simulation_id": request.simulation_id,
            "pairing_id": request.pairing_id,
            "environment_class": request.environment_class,
            "elevation_band": band,
            "scope_id": scope_id,
            "stream_name": stream_name,
            "seed_uint64": seed,
            "quality_mode": request.quality_mode,
            "derivation": "sha256(canonical_json(master_seed,pairing_id,environment_class,elevation_band,scope_id,stream_name))[:8]",
        }
    )
    return np.random.default_rng(seed)


def _legacy_request(request: GenerationV22Request, band: str) -> Any:
    return _v1.GenerationRequest(
        request_id=request.request_id,
        simulation_id=request.pairing_id,
        environment_class=request.environment_class,
        elevation_band=band,
        duration_ms=request.duration_ms,
        master_seed=request.master_seed,
        activation_mode="CONDITIONAL_ACTIVE_STRESS",
        lock_mapping_mode="EMPIRICAL_DIAGNOSTIC_PROXY",
        stress_floor_linear=None,
        output_namespace=request.output_namespace,
    )


def _v21_request(request: GenerationV22Request) -> Any:
    return _v21.GenerationV21Request(
        request_id=request.request_id,
        simulation_id=request.pairing_id,
        environment_class=request.environment_class,
        elevation_bands=request.elevation_bands,
        duration_ms=request.duration_ms,
        master_seed=request.master_seed,
        lock_mapping_mode="EMPIRICAL_DIAGNOSTIC_PROXY",
        output_namespace=request.output_namespace,
    )


def _base_gain(request: GenerationV22Request, band: str, models: Any, registry: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    local_registry: list[dict[str, Any]] = []
    gain_db, gain_linear, metadata = _v1.sample_common_gain_process(_legacy_request(request, band), models, request.duration_ms, local_registry)
    for row in local_registry:
        normalized = dict(row)
        normalized.update(
            {
                "simulation_id": request.simulation_id,
                "pairing_id": request.pairing_id,
                "environment_class": request.environment_class,
                "elevation_band": band,
                "quality_mode": request.quality_mode,
            }
        )
        registry.append(normalized)
    return gain_db, gain_linear, metadata


def generate_v22_simulation(request: GenerationV22Request, config: GeneratorV22Config, frozen_models: Any) -> V22SimulationResult:
    registry: list[dict[str, Any]] = []
    parent_config = _v21.load_v21_config(
        _resolve(Path(__file__).resolve().parents[3], str(config.source_payload["parent_v21_config"]["relative_path"])),
        Path(__file__).resolve().parents[3],
    )
    parent_request = _v21_request(request)
    timelines: dict[str, tuple[np.ndarray, dict[str, Any], Any]] = {}
    receiver_quality_rows: list[dict[str, Any]] = []
    quality_event_rows: list[dict[str, Any]] = []
    for band, satellite_id in BAND_SEQUENCE:
        gain_db, gain_linear, gain_meta = _base_gain(request, band, frozen_models, registry)
        quality_request = QualityProfileRequest(
            simulation_id=request.simulation_id,
            pairing_id=request.pairing_id,
            environment_class=request.environment_class,
            elevation_band=band,
            duration_ms=request.duration_ms,
            master_seed=request.master_seed,
            quality_mode=request.quality_mode,
            pre_event_guard_ms=request.pre_event_guard_ms,
            post_event_guard_ms=request.post_event_guard_ms,
            entry_ramp_cap_ms=request.entry_ramp_cap_ms,
        )
        quality = generate_quality_timeline(quality_request, frozen_models, registry)
        effective = gain_linear * quality.envelope_linear
        timelines[band] = (effective, {"gain_db": gain_db, "gain_linear": gain_linear, "gain_meta": gain_meta, "quality": quality}, quality)
        for event in quality.event_catalog:
            quality_event_rows.append(dict(event))
        for index in range(request.duration_ms):
            receiver_quality_rows.append(
                {
                    "simulation_id": request.simulation_id,
                    "pairing_id": request.pairing_id,
                    "ms": index + 1,
                    "elevation_band": band,
                    "SatelliteID": satellite_id,
                    "quality_mode": request.quality_mode,
                    "base_common_gain_db": float(gain_db[index]),
                    "base_common_gain_linear": float(gain_linear[index]),
                    "quality_state": quality.states[index],
                    "quality_event_id": quality.event_ids[index],
                    "quality_envelope_linear": float(quality.envelope_linear[index]),
                    "effective_common_gain_linear": float(effective[index]),
                    "phase_observable": quality.phase_observable[index],
                    "quality_depth_source": "OBSERVABLE_FADE_PARENT_PROXY" if quality.event_catalog else None,
                    "quality_duration_source": "FROZEN_ENVIRONMENT_LOCK_MODEL" if quality.event_catalog else None,
                    "quality_recovery_source": "FROZEN_ENVIRONMENT_RECOVERY_MODEL_OR_PARENT" if quality.event_catalog else None,
                    "quality_support_status": quality.support_status,
                    "assumption_flags": "CONDITIONAL_QUALITY_PROFILE;INTER_SATELLITE_QUALITY_EVENT_CORRELATION_NOT_MODELED;ABSOLUTE_RF_POWER_NOT_AVAILABLE",
                }
            )

    phase_by_band: dict[str, float] = {}
    for band, _satellite_id in BAND_SEQUENCE:
        phase_rng = _pair_rng(request, band, "simulation", "path0_initial_phase", registry)
        phase_by_band[band] = float(phase_rng.uniform(-np.pi, np.pi))

    block_count = (request.duration_ms + config.path_parameter_block_ms - 1) // config.path_parameter_block_ms
    final_rows: list[dict[str, Any]] = []
    path_block_rows: list[dict[str, Any]] = []
    path_slot_rows: list[dict[str, Any]] = []
    for block_index in range(1, block_count + 1):
        for band, satellite_id in BAND_SEQUENCE:
            block_registry: list[dict[str, Any]] = []
            slots, block_rows = _v21._sample_all_active_block(
                parent_request,
                parent_config,
                frozen_models,
                band,
                block_index,
                block_registry,
            )
            for stream_row in block_registry:
                normalized_stream = dict(stream_row)
                normalized_stream.update(
                    {
                        "simulation_id": request.simulation_id,
                        "pairing_id": request.pairing_id,
                        "environment_class": request.environment_class,
                        "elevation_band": band,
                        "quality_mode": request.quality_mode,
                    }
                )
                registry.append(normalized_stream)
            for row in block_rows:
                row = dict(row)
                row.update(
                    {
                        "simulation_id": request.simulation_id,
                        "pairing_id": request.pairing_id,
                        "environment_class": request.environment_class,
                        "quality_mode": request.quality_mode,
                    }
                )
                path_block_rows.append(row)
            block_start = (block_index - 1) * config.path_parameter_block_ms
            block_end = min(request.duration_ms, block_start + config.path_parameter_block_ms)
            local_phases = {slot.slot_id: slot.phase_rad for slot in slots}
            effective, timeline_meta, _quality = timelines[band]
            for offset in range(block_end - block_start):
                index = block_start + offset
                ms = index + 1
                path0_phase = phase_by_band[band]
                final_rows.append(
                    {
                        "ms": ms,
                        "SatelliteID": satellite_id,
                        "NLOSPathID": 0,
                        "RelativeDelay": 0.0,
                        "RelativeDoppler": 0.0,
                        "RelativeAmplitude": float(effective[index]),
                        "RelativePhase_rad": path0_phase,
                    }
                )
                phase_by_band[band] = _v1.evolve_phase_1ms(path0_phase, 0.0)
                for slot in slots:
                    current_phase = local_phases[slot.slot_id]
                    output_amplitude = float(effective[index] * slot.latent_amplitude)
                    if not math.isfinite(output_amplitude) or output_amplitude <= 0.0:
                        raise ValueError("v2.2 produced a non-positive NLOS output amplitude")
                    final_rows.append(
                        {
                            "ms": ms,
                            "SatelliteID": satellite_id,
                            "NLOSPathID": slot.slot_id,
                            "RelativeDelay": slot.delay_ns,
                            "RelativeDoppler": slot.doppler_hz,
                            "RelativeAmplitude": output_amplitude,
                            "RelativePhase_rad": current_phase,
                        }
                    )
                    path_slot_rows.append(
                        {
                            "simulation_id": request.simulation_id,
                            "pairing_id": request.pairing_id,
                            "environment_class": request.environment_class,
                            "ms": ms,
                            "elevation_band": band,
                            "SatelliteID": satellite_id,
                            "NLOSPathID": slot.slot_id,
                            "block_id": f"{band.lower()}-block-{block_index:06d}",
                            "active": True,
                            "activation_mask": ALL_ACTIVE_MASK,
                            "latent_delay_ns": slot.delay_ns,
                            "latent_doppler_hz": slot.doppler_hz,
                            "latent_relative_amplitude": slot.latent_amplitude,
                            "output_relative_amplitude": output_amplitude,
                            "RelativePhase_rad": current_phase,
                            "slot_status": "ALWAYS_ACTIVE_PATH",
                            "quality_mode": request.quality_mode,
                            "assumption_status": "ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT",
                        }
                    )
                    local_phases[slot.slot_id] = _v1.evolve_phase_1ms(current_phase, slot.doppler_hz)

    final_rows.sort(key=lambda row: (int(row["ms"]), {"Low": 0, "Mid": 1, "High": 2}[row["SatelliteID"]], int(row["NLOSPathID"])))
    receiver_quality_rows.sort(key=lambda row: (int(row["ms"]), {"LOW": 0, "MID": 1, "HIGH": 2}[row["elevation_band"]]))
    path_slot_rows.sort(key=lambda row: (int(row["ms"]), {"LOW": 0, "MID": 1, "HIGH": 2}[row["elevation_band"]], int(row["NLOSPathID"])))
    quality_event_rows.sort(key=lambda row: ({"LOW": 0, "MID": 1, "HIGH": 2}[row["elevation_band"]], int(row["event_start_ms"])))
    if len(final_rows) != request.duration_ms * 12:
        raise AssertionError("v2.2 generator did not emit 12 rows per millisecond")
    if len(receiver_quality_rows) != request.duration_ms * 3 or len(path_slot_rows) != request.duration_ms * 9:
        raise AssertionError("v2.2 sidecar row counts are inconsistent")
    stream_keys = [(row.get("elevation_band", ""), row.get("scope_id", ""), row.get("stream_name", ""), row.get("quality_mode", "")) for row in registry]
    if len(stream_keys) != len(set(stream_keys)):
        raise AssertionError("v2.2 random stream registry is not unique")
    support_summary: dict[str, Any] = {
        "generator_id": config.model_id,
        "generator_version": config.generator_version,
        "environment_class": request.environment_class,
        "pairing_id": request.pairing_id,
        "quality_mode": request.quality_mode,
        "elevation_bands": list(request.elevation_bands),
        "fixed_structural_slots_per_band": 4,
        "rows_per_ms": 12,
        "block_count": block_count,
        "all_nlos_slots_active": True,
        "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
        "nlos_amplitude_constraint": "STRICTLY_POSITIVE",
        "conditional_multipath_scenario": True,
        "activation_model_used_for_generation": False,
        "quality_event_count_per_band": {band: len(timelines[band][2].event_catalog) for band, _ in BAND_SEQUENCE},
        "quality_support_status": {band: timelines[band][2].support_status for band, _ in BAND_SEQUENCE},
        "parent_path_support_status": {band: frozen_models.path_cells[f"{request.environment_class}|{band}"].support_status for band, _ in BAND_SEQUENCE},
        "assumption_statuses": [
            "ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT",
            "CONDITIONAL_QUALITY_PROFILE",
            "QUALITY_EVENT_NOT_OCCURRENCE_RATE",
            "ABSOLUTE_RF_POWER_NOT_AVAILABLE",
            "ASSUMPTION_ONLY_UNIFORM_INITIAL_PLUS_DOPPLER_CONTINUOUS",
            "INDEPENDENT_40MS_BLOCK_ASSUMPTION",
            "INTER_SATELLITE_QUALITY_EVENT_CORRELATION_NOT_MODELED",
        ],
    }
    return V22SimulationResult(
        final_rows=tuple(final_rows),
        receiver_quality_rows=tuple(receiver_quality_rows),
        quality_event_rows=tuple(quality_event_rows),
        path_block_rows=tuple(path_block_rows),
        path_slot_rows=tuple(path_slot_rows),
        random_stream_rows=tuple(registry),
        support_summary=support_summary,
    )


def format_v22_final_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    for row in rows:
        if tuple(row.keys()) != FINAL_COLUMNS:
            if set(row.keys()) != set(FINAL_COLUMNS):
                raise ValueError("v2.2 canonical row fields do not match frozen columns")
        path_id = int(row.get("NLOSPathID", -1))
        amplitude = float(row.get("RelativeAmplitude", "nan"))
        if not math.isfinite(amplitude) or amplitude <= 0.0:
            raise ValueError("v2.2 all path amplitudes must be finite and strictly positive")
        if path_id in NLOS_SLOT_IDS and amplitude <= 0.0:
            raise ValueError("v2.2 NLOS amplitude must be strictly positive")
    return _v2.format_v2_final_rows(rows)
