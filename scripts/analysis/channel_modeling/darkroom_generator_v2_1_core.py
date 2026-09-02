"""Core for the v2.1 fixed-four-slot darkroom parameter generator.

v2.1 is an explicit conditional multipath scenario.  It preserves the v2
parent gain/fade/lock and path-draw semantics, but does not use the empirical
activation model: NLOS slots 1, 2 and 3 are always active and every emitted
NLOS amplitude is strictly positive.  This is a scenario-generation contract,
not a claim that every physical observation contains three paths.
"""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from . import darkroom_generator_v2_core as _v2
except ImportError:
    from scripts.analysis.channel_modeling import darkroom_generator_v2_core as _v2


FINAL_COLUMNS: tuple[str, ...] = _v2.FINAL_COLUMNS
BAND_SEQUENCE: tuple[tuple[str, str], ...] = _v2.BAND_SEQUENCE
ENVIRONMENTS = _v2.ENVIRONMENTS
V21_RUN_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_runs"
ALL_ACTIVE_MASK = "111"
NLOS_SLOT_IDS: tuple[int, ...] = (1, 2, 3)


def canonical_json_bytes(value: Any) -> bytes:
    return _v2.canonical_json_bytes(value)


def sha256_file(path: Path) -> str:
    return _v2.sha256_file(path)


@dataclass(frozen=True)
class GeneratorV21Config:
    model_id: str
    generator_version: str
    sample_rate_hz: int
    time_step_ms: int
    path_parameter_block_ms: int
    environments: tuple[str, ...]
    elevation_bands: tuple[str, ...]
    source_payload: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.model_id != "darkroom-multi-elevation-four-slot-generator-v2-1":
            raise ValueError("unsupported v2.1 generator")
        if self.generator_version != "2.1.0":
            raise ValueError("unsupported v2.1 generator version")
        if self.sample_rate_hz != 10_230_000:
            raise ValueError("v2.1 supports only 10.23 MHz")
        if self.time_step_ms != 1 or self.path_parameter_block_ms != 40:
            raise ValueError("v2.1 requires 1 ms steps and 40 ms blocks")
        if self.environments != ENVIRONMENTS:
            raise ValueError("environment order is frozen")
        if self.elevation_bands != ("LOW", "MID", "HIGH"):
            raise ValueError("all three bands are required in fixed order")


@dataclass(frozen=True)
class GenerationV21Request:
    request_id: str
    simulation_id: str
    environment_class: str
    elevation_bands: tuple[str, ...]
    duration_ms: int
    master_seed: int
    lock_mapping_mode: str
    output_namespace: str


@dataclass(frozen=True)
class V21SimulationResult:
    final_rows: tuple[dict[str, Any], ...]
    path_block_rows: tuple[dict[str, Any], ...]
    path_slot_rows: tuple[dict[str, Any], ...]
    timeline_rows: tuple[dict[str, Any], ...]
    stream_rows: tuple[dict[str, Any], ...]
    support_summary: Mapping[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _resolve(project_root: Path, relative: str) -> Path:
    root = project_root.resolve()
    candidate = (root / str(relative)).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes project root: {relative}")
    return candidate


def load_v21_config(path: Path, project_root: Path) -> GeneratorV21Config:
    config_path = path.resolve()
    data = _read_json(config_path)
    if int(data.get("sample_rate_hz", 0)) != 10_230_000:
        raise ValueError("v2.1 supports only 10.23 MHz")
    if tuple(data.get("final_columns", FINAL_COLUMNS)) != FINAL_COLUMNS:
        raise ValueError("v2.1 final columns do not match the frozen contract")
    slot_policy = data.get("slot_policy", {})
    required_slot_policy = {
        "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
        "nlos_amplitude_constraint": "STRICTLY_POSITIVE",
        "inactive_nlos_policy": "NOT_APPLICABLE_ALL_SLOTS_ACTIVE",
        "assumption_status": "ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT",
    }
    for field_name, expected in required_slot_policy.items():
        if slot_policy.get(field_name) != expected:
            raise ValueError(f"v2.1 slot policy mismatch: {field_name}")
    if slot_policy.get("activation_model_used_for_generation") is not False:
        raise ValueError("v2.1 must not use the activation model for generation")
    if slot_policy.get("conditional_multipath_scenario") is not True:
        raise ValueError("v2.1 conditional scenario flag is missing")
    if tuple(slot_policy.get("nlos_slot_ids", ())) != NLOS_SLOT_IDS:
        raise ValueError("v2.1 NLOS slot ids are not frozen")
    band_policy = data.get("band_policy", {})
    if tuple(band_policy.get("band_order", ())) != ("LOW", "MID", "HIGH"):
        raise ValueError("v2.1 band order is not frozen")
    execution_policy = data.get("execution_policy", {})
    forbidden = ("raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz")
    if any(execution_policy.get(key) is not False for key in forbidden):
        raise ValueError("v2.1 execution policy enables a forbidden action")
    parent = data.get("parent_v2_config")
    if not isinstance(parent, Mapping):
        raise ValueError("v2.1 parent v2 config is missing")
    parent_path = _resolve(project_root, str(parent.get("relative_path", "")))
    if not parent_path.is_file() or sha256_file(parent_path).lower() != str(parent.get("sha256", "")).lower():
        raise ValueError("v2 parent generator config hash mismatch")
    parent_core = data.get("parent_v2_core")
    if not isinstance(parent_core, Mapping):
        raise ValueError("v2.1 parent v2 core is missing")
    parent_core_path = _resolve(project_root, str(parent_core.get("relative_path", "")))
    if not parent_core_path.is_file() or sha256_file(parent_core_path).lower() != str(parent_core.get("sha256", "")).lower():
        raise ValueError("v2 parent core hash mismatch")
    return GeneratorV21Config(
        model_id=str(data.get("generator_id", "")),
        generator_version=str(data.get("generator_version", "")),
        sample_rate_hz=int(data.get("sample_rate_hz", 0)),
        time_step_ms=int(data.get("time_step_ms", 0)),
        path_parameter_block_ms=int(data.get("path_parameter_block_ms", 0)),
        environments=tuple(data.get("environments", ())),
        elevation_bands=tuple(data.get("elevation_bands", ())),
        source_payload=data,
    )


def load_frozen_v21_parent_models(project_root: Path, config: GeneratorV21Config) -> Any:
    parent = config.source_payload["parent_v2_config"]
    parent_path = _resolve(project_root, str(parent["relative_path"]))
    if sha256_file(parent_path).lower() != str(parent["sha256"]).lower():
        raise ValueError("v2.1 parent v2 config changed")
    v2_config = _v2.load_v2_config(parent_path, project_root)
    models = _v2.load_frozen_v2_parent_models(project_root, v2_config)
    if models.path_model_manifest_sha256 != str(config.source_payload["parent_model_manifest_sha256"]):
        raise ValueError("v2.1 path parent manifest provenance mismatch")
    return models


def validate_v21_request(payload: Mapping[str, Any], config: GeneratorV21Config) -> GenerationV21Request:
    required = {
        "request_id", "simulation_id", "generator_id", "environment_class", "elevation_bands",
        "duration_ms", "master_seed", "nlos_activation_policy", "all_nlos_slots_active",
        "conditional_multipath_scenario", "inactive_slot_parameter_policy", "lock_mapping_mode",
        "new_only", "resume_allowed", "raw_iq_read", "matlab", "sage", "batch",
        "process_20_46_mhz", "gold_labels_used_for_generation", "output_namespace",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"missing v2.1 request fields: {','.join(missing)}")
    if str(payload["generator_id"]) != config.model_id:
        raise ValueError("v2.1 generator_id mismatch")
    if not str(payload["request_id"]).strip() or not str(payload["simulation_id"]).strip():
        raise ValueError("request_id and simulation_id must be non-empty")
    if payload["environment_class"] not in config.environments:
        raise ValueError("unsupported environment_class")
    if tuple(payload["elevation_bands"]) != config.elevation_bands:
        raise ValueError("elevation_bands must be exactly LOW,MID,HIGH")
    duration = payload["duration_ms"]
    seed = payload["master_seed"]
    if isinstance(duration, bool) or not isinstance(duration, (int, np.integer)) or int(duration) < 1:
        raise ValueError("duration_ms must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or int(seed) < 0:
        raise ValueError("master_seed must be a non-negative integer")
    if payload["nlos_activation_policy"] != "ALL_THREE_SLOTS_ALWAYS_ACTIVE":
        raise ValueError("nlos_activation_policy must be ALL_THREE_SLOTS_ALWAYS_ACTIVE")
    if payload["all_nlos_slots_active"] is not True:
        raise ValueError("all_nlos_slots_active must be true")
    if payload["conditional_multipath_scenario"] is not True:
        raise ValueError("conditional_multipath_scenario must be true")
    if payload["inactive_slot_parameter_policy"] != "NOT_APPLICABLE_ALL_SLOTS_ACTIVE":
        raise ValueError("inactive slot parameter policy mismatch")
    if payload["lock_mapping_mode"] not in {"EMPIRICAL_DIAGNOSTIC_PROXY", "FORCED_LOCK_LOSS_STRESS"}:
        raise ValueError("unsupported lock_mapping_mode")
    if payload["new_only"] is not True:
        raise ValueError("new_only must be true")
    flags = ("resume_allowed", "raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz", "gold_labels_used_for_generation")
    if any(payload[key] is not False for key in flags):
        raise ValueError("v2.1 request enables a forbidden mode or gold selection")
    output = str(payload["output_namespace"]).replace("\\", "/")
    if not output.startswith(V21_RUN_ROOT + "/") or ".." in output.split("/"):
        raise ValueError("unsafe v2.1 output namespace")
    if output.split("/")[-1] != str(payload["request_id"]):
        raise ValueError("output namespace must end with request_id")
    return GenerationV21Request(
        request_id=str(payload["request_id"]),
        simulation_id=str(payload["simulation_id"]),
        environment_class=str(payload["environment_class"]),
        elevation_bands=tuple(payload["elevation_bands"]),
        duration_ms=int(duration),
        master_seed=int(seed),
        lock_mapping_mode=str(payload["lock_mapping_mode"]),
        output_namespace=output,
    )


def _parent_request(request: GenerationV21Request) -> Any:
    return _v2.GenerationV2Request(
        request_id=request.request_id,
        simulation_id=request.simulation_id,
        environment_class=request.environment_class,
        elevation_bands=request.elevation_bands,
        duration_ms=request.duration_ms,
        master_seed=request.master_seed,
        activation_mode="CONDITIONAL_ACTIVE_STRESS",
        inactive_slot_parameter_policy="LATENT_PARAMETERS_WITH_ZERO_AMPLITUDE",
        lock_mapping_mode=request.lock_mapping_mode,
        output_namespace=request.output_namespace,
    )


def _rng(
    request: GenerationV21Request,
    band: str,
    scope_id: str,
    stream_name: str,
    registry: list[dict[str, Any]],
) -> np.random.Generator:
    parent_request = _parent_request(request)
    return _v2._rng(parent_request, band, scope_id, stream_name, registry)


def _sample_all_active_block(
    request: GenerationV21Request,
    config: GeneratorV21Config,
    models: Any,
    band: str,
    block_index: int,
    registry: list[dict[str, Any]],
) -> tuple[tuple[_v2.V2LatentSlot, ...], list[dict[str, Any]]]:
    key = f"{request.environment_class}|{band}"
    path_rng = _rng(request, band, f"block-{block_index:06d}", "block_nlos_joint_parameters", registry)
    draws = _v2._v1._sample_path_vector(models.path_cells[key], path_rng, 3)
    indexed = sorted(enumerate(draws), key=lambda item: (item[1][0], -item[1][2], item[1][1], item[0]))
    slots: list[_v2.V2LatentSlot] = []
    for slot_id, (_, draw) in enumerate(indexed, start=1):
        if float(draw[2]) <= 0.0:
            raise ValueError("parent path distribution produced a non-positive amplitude")
        phase_rng = _rng(request, band, f"block-{block_index:06d}", f"block_nlos_phase_slot_{slot_id}", registry)
        slots.append(
            _v2.V2LatentSlot(
                slot_id,
                float(draw[0]),
                float(draw[1]),
                float(draw[2]),
                float(phase_rng.uniform(-np.pi, np.pi)),
                active=True,
                output_amplitude_base=float(draw[2]),
            )
        )
    block_id = f"{band.lower()}-block-{block_index:06d}"
    support = models.activation_cells[key]
    block_rows = [
        {
            "block_id": block_id,
            "elevation_band": band,
            "SatelliteID": dict(BAND_SEQUENCE)[band],
            "block_start_ms": (block_index - 1) * config.path_parameter_block_ms + 1,
            "block_end_ms": block_index * config.path_parameter_block_ms,
            "NLOSPathID": slot.slot_id,
            "active": True,
            "activation_mask": ALL_ACTIVE_MASK,
            "K_active": 3,
            "latent_delay_ns": slot.delay_ns,
            "latent_doppler_hz": slot.doppler_hz,
            "latent_relative_amplitude": slot.latent_amplitude,
            "output_relative_amplitude_base": slot.output_amplitude_base,
            "phase_initial_rad": slot.phase_rad,
            "slot_status": "ALWAYS_ACTIVE_PATH",
            "occupancy_support_status": support.occupancy_support_status,
            "multiplicity_support_status": support.multiplicity_support_status,
            "path_parameter_support_status": support.path_parameter_support_status,
            "prior_only": any(
                status == "PRIOR_ONLY"
                for status in (
                    support.occupancy_support_status,
                    support.multiplicity_support_status,
                    support.path_parameter_support_status,
                )
            ),
            "assumption_status": "ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT",
        }
        for slot in slots
    ]
    return tuple(slots), block_rows


def generate_v21_simulation(
    request: GenerationV21Request,
    config: GeneratorV21Config,
    models: Any,
) -> V21SimulationResult:
    registry: list[dict[str, Any]] = []
    parent_request = _parent_request(request)
    timelines: dict[str, tuple[np.ndarray, dict[str, Any]]] = {
        band: _v2._band_timeline(parent_request, models, band, registry)
        for band, _ in BAND_SEQUENCE
    }
    block_count = (request.duration_ms + config.path_parameter_block_ms - 1) // config.path_parameter_block_ms
    support_summary: dict[str, Any] = {
        "generator_id": config.model_id,
        "generator_version": config.generator_version,
        "environment_class": request.environment_class,
        "elevation_bands": list(request.elevation_bands),
        "fixed_structural_slots_per_band": 4,
        "rows_per_ms": 12,
        "block_count": block_count,
        "all_nlos_slots_active": True,
        "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
        "nlos_amplitude_constraint": "STRICTLY_POSITIVE",
        "conditional_multipath_scenario": True,
        "activation_model_used_for_generation": False,
        "assumption_statuses": [
            "ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT",
            "ACTIVATION_MODEL_NOT_USED_FOR_GENERATION",
            "CONDITIONAL_MULTIPATH_SCENARIO",
            "ASSUMPTION_ONLY_UNIFORM_INITIAL_PLUS_DOPPLER_CONTINUOUS",
            "INDEPENDENT_40MS_BLOCK_ASSUMPTION",
            "INTER_SATELLITE_CORRELATION_NOT_MODELED",
        ],
        "parent_path_support_status": {},
        "parent_occupancy_support_status": {},
        "parent_multiplicity_support_status": {},
    }
    for band, _ in BAND_SEQUENCE:
        key = f"{request.environment_class}|{band}"
        activation = models.activation_cells[key]
        support_summary["parent_path_support_status"][band] = models.path_cells[key].support_status
        support_summary["parent_occupancy_support_status"][band] = activation.occupancy_support_status
        support_summary["parent_multiplicity_support_status"][band] = activation.multiplicity_support_status

    phase_by_band: dict[str, float] = {}
    for band, _ in BAND_SEQUENCE:
        phase_rng = _rng(request, band, "simulation", "path0_initial_phase", registry)
        phase_by_band[band] = float(phase_rng.uniform(-np.pi, np.pi))

    final_rows: list[dict[str, Any]] = []
    path_block_rows: list[dict[str, Any]] = []
    path_slot_rows: list[dict[str, Any]] = []
    for block_index in range(1, block_count + 1):
        for band, satellite_id in BAND_SEQUENCE:
            slots, block_rows = _sample_all_active_block(request, config, models, band, block_index, registry)
            path_block_rows.extend(block_rows)
            block_start = (block_index - 1) * config.path_parameter_block_ms
            block_end = min(request.duration_ms, block_start + config.path_parameter_block_ms)
            local_phases = {slot.slot_id: slot.phase_rad for slot in slots}
            effective = timelines[band][0]
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
                phase_by_band[band] = _v2._v1.evolve_phase_1ms(path0_phase, 0.0)
                for slot in slots:
                    current_phase = local_phases[slot.slot_id]
                    output_amplitude = float(effective[index] * slot.latent_amplitude)
                    if output_amplitude <= 0.0:
                        raise ValueError("v2.1 produced a non-positive NLOS output amplitude")
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
                            "assumption_status": "ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT",
                        }
                    )
                    local_phases[slot.slot_id] = _v2._v1.evolve_phase_1ms(current_phase, slot.doppler_hz)

    final_rows.sort(key=lambda row: (int(row["ms"]), {"Low": 0, "Mid": 1, "High": 2}[row["SatelliteID"]], int(row["NLOSPathID"])))
    path_slot_rows.sort(
        key=lambda row: (
            int(row["ms"]),
            {"LOW": 0, "MID": 1, "HIGH": 2}[str(row["elevation_band"])],
            int(row["NLOSPathID"]),
        )
    )
    timeline_rows = tuple(
        timelines[band][1]["rows"][index]
        for index in range(request.duration_ms)
        for band, _ in BAND_SEQUENCE
    )
    if len(final_rows) != request.duration_ms * 12:
        raise AssertionError("v2.1 generator did not emit 12 rows per millisecond")
    if len(path_slot_rows) != request.duration_ms * 9:
        raise AssertionError("v2.1 generator did not emit 9 NLOS rows per millisecond")
    return V21SimulationResult(
        final_rows=tuple(final_rows),
        path_block_rows=tuple(path_block_rows),
        path_slot_rows=tuple(path_slot_rows),
        timeline_rows=timeline_rows,
        stream_rows=tuple(registry),
        support_summary=support_summary,
    )


def format_v21_final_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    for row in rows:
        path_id = int(row.get("NLOSPathID", -1))
        if path_id in NLOS_SLOT_IDS:
            value = row.get("RelativeAmplitude")
            if value is None or not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError("v2.1 NLOS amplitude must be strictly positive")
    return _v2.format_v2_final_rows(rows)

