"""Build the fixed-three-NLOS-slot activation model from frozen 10.23 MHz data.

This builder is an offline model-publication tool.  It reads the versioned
Stage0, Stage4 event/path and geometry/model artifacts declared by the
activation configuration.  It never opens raw IQ, tracking files, MATLAB,
SAGE outputs outside the declared Stage0 exposure sources, or any 20.46 MHz
input.  The output namespace is new-only and is intentionally separate from
all ``scenes/**/sage_results`` directories.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import math
import platform
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np

from scripts.analysis.channel_modeling.nlos_slot_activation_core import (
    ActivationConfig,
    ActivationEvidence,
    ActivationModel,
    ENVIRONMENTS,
    ELEVATION_BANDS,
    EventPathObservation,
    ExposureWindow,
    MultiplicityHierarchy,
    OccupancyHierarchy,
    PathDraw,
    SourceAudit,
    assign_continuity_segments,
    aggregate_scene_cell_exposure,
    build_activation_labels,
    fit_multiplicity_hierarchy,
    fit_occupancy_hierarchy,
    generate_activation_qa_draws,
    join_geometry_grid,
    load_activation_config,
    load_confirmed_event_paths,
    load_confirmed_events,
    load_stage0_exposure,
    resolve_stage0_sources,
    scene_block_bootstrap,
    sha256_file,
    verify_frozen_sources,
)


REQUIRED_OUTPUT_FILES: tuple[str, ...] = (
    "source_preflight.csv",
    "stage0_source_manifest.csv",
    "activation_exposure_grid.csv.gz",
    "confirmed_support_membership.csv",
    "scene_cell_exposure.csv",
    "cell_occupancy_parameters.csv",
    "multiplicity_event_catalog.csv",
    "cell_multiplicity_parameters.csv",
    "observed_slot_assignment_audit.csv",
    "bootstrap_uncertainty.csv",
    "qa_draw_summary.csv",
    "slot_activation_contract.json",
    "nlos_slot_activation_model.json",
    "model_manifest.json",
    "model_report.md",
    "build_receipt.json",
)


@dataclass(frozen=True)
class BuildReceipt:
    status: str
    output_dir: str
    model_manifest_sha256: str
    config_sha256: str
    source_hashes: Mapping[str, str]
    source_counts: Mapping[str, int]
    execution_policy: Mapping[str, Any]
    output_files: tuple[str, ...]
    output_hashes: Mapping[str, str]


@dataclass(frozen=True)
class PreparedInputs:
    root: Path
    config_path: Path
    config: ActivationConfig
    source_audit: SourceAudit
    stage0_sources: tuple[Any, ...]
    stage0_rows: tuple[ExposureWindow, ...]
    joined_rows: tuple[ExposureWindow, ...]
    evidence: ActivationEvidence
    events: tuple[Any, ...]
    event_paths: tuple[EventPathObservation, ...]
    scene_cells: tuple[Any, ...]
    occupancy: OccupancyHierarchy
    multiplicity: MultiplicityHierarchy
    stage0_manifest_rows: tuple[Mapping[str, Any], ...]
    declared_source_rows: tuple[Mapping[str, Any], ...]
    stage0_source_hashes: Mapping[str, str]
    geometry_matched_count: int
    geometry_valid_count: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return _json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_safe(value), indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (Mapping, tuple, list)):
        return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _write_csv_gzip(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    import gzip

    with gzip.open(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _backend_receipt() -> dict[str, Any]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        np.show_config()
    scipy = __import__("scipy")
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "architecture": platform.architecture()[0],
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "numpy_show_config": output.getvalue(),
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _validate_namespace(
    project_root: Path,
    output_dir: Path,
    config: ActivationConfig | None = None,
    *,
    allow_test_namespace: bool = False,
) -> tuple[Path, Path]:
    root = project_root.resolve(strict=False)
    target = output_dir.resolve(strict=False)
    if not root.is_dir():
        raise FileNotFoundError(root)
    if target.exists():
        raise FileExistsError(f"new-only output already exists: {target}")
    inside = _is_within(target, root)
    if not inside and not allow_test_namespace:
        raise ValueError("model output must remain inside the project root")
    if inside:
        relative = target.relative_to(root)
        parts = {part.lower() for part in relative.parts}
        if {"scenes", "sage_results", "_trash"}.intersection(parts):
            raise ValueError("model output may not be placed under scenes, sage_results, or _trash")
        if not allow_test_namespace and not {"dataset_generation_logs", "channel_modeling"}.issubset(parts):
            raise ValueError("model output must be under dataset_generation_logs/channel_modeling")
        if config is not None and not allow_test_namespace:
            expected = (root / Path(config.output_namespace)).resolve(strict=False)
            if target != expected:
                raise ValueError(f"output namespace differs from frozen config: {target} != {expected}")
    return root, target


def _validate_execution_policy(config: ActivationConfig) -> None:
    policy = config.execution_policy
    for field in ("raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz"):
        if policy.get(field) is not False:
            raise ValueError(f"execution policy must keep {field}=false: {field}")
    if policy.get("gold_labels_used_for_selection") is not False:
        raise ValueError("gold_labels_used_for_selection must be false")
    if policy.get("stage1_stage2_stage3_used_for_selection") is not False:
        raise ValueError("Stage1/Stage2/Stage3 selection flag must be false")
    if policy.get("new_only") is not True or policy.get("resume_allowed") is not False:
        raise ValueError("activation model output must be new-only and non-resumable")


def _source_rows(root: Path, config: ActivationConfig, hashes: Mapping[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, relative in sorted(config.source.items()):
        if not key.endswith("_relative_path"):
            continue
        stem = key[: -len("_relative_path")]
        path = (root / Path(relative)).resolve(strict=False)
        rows.append({
            "source_key": stem,
            "source_kind": "declared_frozen_source",
            "path": str(path),
            "relative_path": str(relative),
            "sha256": hashes.get(stem, sha256_file(path)),
            "size_bytes": path.stat().st_size,
            "status": "PASS",
        })
    return rows


def _prepare_inputs(
    project_root: Path,
    config_path: Path,
    output_dir: Path,
    *,
    allow_test_namespace: bool = False,
) -> PreparedInputs:
    root = project_root.resolve(strict=False)
    config_file = config_path.resolve(strict=False)
    config = load_activation_config(config_file)
    _validate_execution_policy(config)
    _validate_namespace(root, output_dir, config, allow_test_namespace=allow_test_namespace)
    source_audit = verify_frozen_sources(root, config)
    stage0_sources = resolve_stage0_sources(root, source_audit, config)
    source_manifest_rows: list[dict[str, Any]] = []
    stage0_source_hashes: dict[str, str] = {}
    all_rows: list[ExposureWindow] = []
    for source in stage0_sources:
        stage0_hash = sha256_file(source.stage0_path)
        stage0_source_hashes[source.run_id] = stage0_hash
        rows = assign_continuity_segments(load_stage0_exposure(source))
        all_rows.extend(rows)
        source_manifest_rows.append({
            "run_id": source.run_id,
            "scene_id": source.scene_id,
            "prn": source.prn,
            "tracking_channel": source.tracking_channel,
            "environment": source.environment,
            "stage0_path": str(source.stage0_path),
            "stage0_sha256": stage0_hash,
            "stage0_size_bytes": source.stage0_path.stat().st_size,
            "expected_window_count": source.expected_window_count,
            "loaded_window_count": len(rows),
            "status": "PASS",
        })
    if len(all_rows) != source_audit.stage0_window_count:
        raise ValueError(f"Stage0 total mismatch: expected {source_audit.stage0_window_count}, got {len(all_rows)}")
    joined = join_geometry_grid(
        all_rows,
        root / Path(config.source["geometry_grid_relative_path"]),
        tolerance_s=float(config.exposure["geometry_join_max_delta_s"]),
    )
    events = tuple(load_confirmed_events(root, config))
    event_paths = tuple(load_confirmed_event_paths(root, config))
    evidence = build_activation_labels(
        joined,
        events,
        closure_radius=int(config.exposure["closure_radius_windows"]),
    )
    incomplete = sorted(event_id for event_id, complete in evidence.closure_complete.items() if not complete)
    if incomplete:
        raise ValueError(f"confirmed event closure is incomplete: {incomplete[:5]}")
    scene_cells = tuple(aggregate_scene_cell_exposure(evidence))
    occupancy = fit_occupancy_hierarchy(scene_cells, config)
    multiplicity = fit_multiplicity_hierarchy(events, config)
    if len(events) != 94 or len(event_paths) != 100:
        raise ValueError(f"frozen Stage4 counts changed: events={len(events)}, paths={len(event_paths)}")
    return PreparedInputs(
        root=root,
        config_path=config_file,
        config=config,
        source_audit=source_audit,
        stage0_sources=tuple(stage0_sources),
        stage0_rows=tuple(all_rows),
        joined_rows=tuple(joined),
        evidence=evidence,
        events=events,
        event_paths=event_paths,
        scene_cells=scene_cells,
        occupancy=occupancy,
        multiplicity=multiplicity,
        stage0_manifest_rows=tuple(source_manifest_rows),
        declared_source_rows=tuple(_source_rows(root, config, source_audit.source_hashes)),
        stage0_source_hashes=stage0_source_hashes,
        geometry_matched_count=int(joined.matched_count),
        geometry_valid_count=int(joined.valid_count),
    )


def preflight(
    project_root: Path,
    config_path: Path,
    output_dir: Path,
    *,
    allow_test_namespace: bool = False,
) -> dict[str, Any]:
    """Run all read-only source, count, policy and namespace checks."""

    prepared = _prepare_inputs(
        project_root,
        config_path,
        output_dir,
        allow_test_namespace=allow_test_namespace,
    )
    return {
        "status": "PASS",
        "project_root": str(prepared.root),
        "config_path": str(prepared.config_path),
        "config_sha256": sha256_file(prepared.config_path),
        "output_dir": str(Path(output_dir).resolve(strict=False)),
        "output_exists": False,
        "source_counts": {
            "eligible_runs": prepared.source_audit.eligible_run_count,
            "stage0_windows": prepared.source_audit.stage0_window_count,
            "confirmed_events": len(prepared.events),
            "confirmed_paths": len(prepared.event_paths),
        },
        "stage0_sources": len(prepared.stage0_sources),
        "geometry_matched_windows": prepared.geometry_matched_count,
        "geometry_valid_windows": prepared.geometry_valid_count,
        "closure_memberships": len(prepared.evidence.memberships),
        "source_hashes": dict(prepared.source_audit.source_hashes),
        "stage0_source_hashes": dict(prepared.stage0_source_hashes),
        "execution_policy": dict(prepared.config.execution_policy),
        "backend": _backend_receipt(),
        "protected_pipeline_sha256": prepared.config.protected_source["pipeline_sha256"],
        "raw_iq_read": False,
        "matlab_executed": False,
        "sage_executed": False,
        "batch_executed": False,
    }


def _exposure_row(row: ExposureWindow) -> dict[str, Any]:
    return {
        "run_id": row.run_id,
        "scene_id": row.scene_id,
        "prn": row.prn,
        "tracking_channel": row.tracking_channel,
        "environment": row.environment,
        "window_id": row.window_id,
        "sample_start_zero_based": row.sample_start_zero_based,
        "recording_time_s": row.recording_time_s,
        "tow_s": row.tow_s,
        "nav_symbol_1": row.nav_symbol_1,
        "nav_symbol_2": row.nav_symbol_2,
        "continuity_segment": row.continuity_segment,
        "geometry_elevation_deg": row.geometry_elevation_deg,
        "elevation_band": row.elevation_band,
        "azimuth_deg": row.azimuth_deg,
        "nmea_snr_db_hz": row.nmea_snr_db_hz,
        "geometry_join_valid": int(row.geometry_join_valid),
        "geometry_join_status": row.geometry_join_status,
        "geometry_time_delta_s": row.geometry_time_delta_s,
        "time_bin_index": row.time_bin_index,
        "support_label": row.support_label,
        "support_semantics": "stage4_confirmed_support_proxy_only",
    }


def _scene_cell_rows(scene_cells: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {
            "scene_id": row.scene_id,
            "environment": row.environment,
            "elevation_band": row.elevation_band,
            "exposure_windows": row.exposure_windows,
            "support_windows": row.support_windows,
            "core_event_ids_json": list(row.core_event_ids),
            "scene_rate": row.scene_rate,
            "support_semantics": "stage4_confirmed_support_proxy_only",
        }
        for row in scene_cells
    ]


def _occupancy_rows(prepared: PreparedInputs) -> list[dict[str, Any]]:
    by_cell: dict[tuple[str, str], list[Any]] = {key: [] for key in prepared.occupancy.cell_models}
    for row in prepared.scene_cells:
        if row.elevation_band in ELEVATION_BANDS:
            by_cell[(row.environment, row.elevation_band)].append(row)
    rows: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            model = prepared.occupancy.cell_models[(environment, band)]
            direct = by_cell[(environment, band)]
            exposure_windows = sum(row.exposure_windows for row in direct)
            support_windows = sum(row.support_windows for row in direct)
            rows.append({
                "environment": environment,
                "elevation_band": band,
                "alpha": model.alpha,
                "beta": model.beta,
                "mean": model.mean,
                "q025": model.q025,
                "q50": model.q50,
                "q975": model.q975,
                "direct_scene_count": model.direct_scene_count,
                "direct_core_event_count": model.direct_core_event_count,
                "support_status": model.support_status,
                "parent_key": model.parent_key,
                "exposure_windows": exposure_windows,
                "support_windows": support_windows,
                "time_weighted_support_fraction": support_windows / exposure_windows if exposure_windows else None,
                "selected_quantity": "p_stage4_confirmed_support_active",
            })
    return rows


def _multiplicity_event_rows(events: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": event.event_id,
            "run_id": event.run_id,
            "scene_id": event.scene_id,
            "prn": event.prn,
            "tracking_channel": event.tracking_channel,
            "center_window_id": event.center_window_id,
            "environment": event.environment,
            "elevation_deg": event.elevation_deg,
            "elevation_band": event.elevation_band,
            "elevation_modeling_ready": int(event.elevation_modeling_ready),
            "confirmed_path_count": event.confirmed_path_count,
            "event_utc": event.event_utc,
            "label_semantics": "stage4_confirmed_multipath_event_only",
        }
        for event in events
    ]


def _multiplicity_rows(prepared: PreparedInputs) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        for band in ELEVATION_BANDS:
            model = prepared.multiplicity.cell_models[(environment, band)]
            rows.append({
                "environment": environment,
                "elevation_band": band,
                "categories": list(model.categories),
                "counts": list(model.counts),
                "alpha": list(model.alpha),
                "probabilities": list(model.probabilities),
                "q025": list(model.q025),
                "q50": list(model.q50),
                "q975": list(model.q975),
                "direct_event_count": model.direct_event_count,
                "support_status": model.support_status,
                "parent_key": model.parent_key,
                "conditional_semantics": "K_given_stage4_confirmed_support_active",
            })
    return rows


def _observed_slot_rows(
    events: Sequence[Any],
    event_paths: Sequence[EventPathObservation],
) -> list[dict[str, Any]]:
    paths_by_event: dict[str, list[EventPathObservation]] = {}
    for path in event_paths:
        paths_by_event.setdefault(path.event_id, []).append(path)
    rows: list[dict[str, Any]] = []
    for event in events:
        observations = paths_by_event.get(event.event_id, [])
        draws = [PathDraw(
            relative_delay_ns=path.excess_delay_ns,
            relative_doppler_hz=path.relative_doppler_hz,
            relative_amplitude_linear=path.relative_amplitude_linear,
            stable_source_id=path.event_path_id,
        ) for path in observations]
        ordered = sorted(
            zip(observations, draws),
            key=lambda pair: (
                pair[1].relative_delay_ns,
                -pair[1].relative_amplitude_linear,
                pair[1].relative_doppler_hz,
                pair[1].stable_source_id,
            ),
        )
        if len(ordered) != event.confirmed_path_count:
            raise ValueError(f"observed path count mismatch for slot audit: {event.event_id}")
        active_by_slot = {
            slot: (observation, draw)
            for slot, (observation, draw) in enumerate(ordered, start=1)
        }
        for slot in range(1, 4):
            active = active_by_slot.get(slot)
            if active is None:
                rows.append({
                    "event_id": event.event_id,
                    "run_id": event.run_id,
                    "scene_id": event.scene_id,
                    "environment": event.environment,
                    "elevation_band": event.elevation_band,
                    "confirmed_path_count": event.confirmed_path_count,
                    "nlos_path_id": slot,
                    "path_active": 0,
                    "path_status": "INACTIVE_NO_PATH",
                    "event_path_id": None,
                    "relative_delay_ns": None,
                    "relative_doppler_hz": None,
                    "relative_amplitude_linear": 0.0,
                    "slot_order_semantics": "delay_ascending_amp_desc_doppler_ascending_source_id",
                })
                continue
            observation, draw = active
            rows.append({
                "event_id": event.event_id,
                "run_id": event.run_id,
                "scene_id": event.scene_id,
                "environment": event.environment,
                "elevation_band": event.elevation_band,
                "confirmed_path_count": event.confirmed_path_count,
                "nlos_path_id": slot,
                "path_active": 1,
                "path_status": "ACTIVE_NLOS",
                "event_path_id": observation.event_path_id,
                "relative_delay_ns": draw.relative_delay_ns,
                "relative_doppler_hz": draw.relative_doppler_hz,
                "relative_amplitude_linear": draw.relative_amplitude_linear,
                "slot_order_semantics": "delay_ascending_amp_desc_doppler_ascending_source_id",
            })
    return rows


def _bootstrap_rows(bootstrap: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in bootstrap.records:
        rows.append({
            "replicate": record.get("replicate"),
            "resample_unit": record.get("resample_unit"),
            "sampled_scene_count": record.get("sampled_scene_count"),
            "sampled_scene_ids_json": record.get("sampled_scene_ids"),
            "replicate_status": record.get("replicate_status"),
            "environment_rate_json": record.get("environment_rate"),
            "cell_rate_json": record.get("cell_rate"),
            "environment_event_counts_json": record.get("environment_event_counts"),
            "cell_event_counts_json": record.get("cell_event_counts"),
            "failure_reason": record.get("failure_reason"),
            "seed": bootstrap.seed,
            "replicate_count": bootstrap.replicate_count,
        })
    return rows


def _qa_rows(summaries: Sequence[Any], prepared: PreparedInputs) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        model = prepared.occupancy.cell_models[(summary.environment, summary.elevation_band)]
        rows.append({
            "environment": summary.environment,
            "elevation_band": summary.elevation_band,
            "activation_mode": summary.activation_mode,
            "draw_count": summary.draw_count,
            "active_count": summary.active_count,
            "active_fraction": summary.active_count / summary.draw_count,
            "analytic_occupancy_mean": model.mean,
            "k_counts_json": summary.k_counts,
            "seed": summary.seed,
            "frequency_tolerance": max(
                float(prepared.config.uncertainty["qa_frequency_absolute_floor"]),
                float(prepared.config.uncertainty["qa_frequency_sigma_multiplier"])
                * math.sqrt(model.mean * (1.0 - model.mean) / summary.draw_count),
            ),
            "support_status": model.support_status,
        })
    return rows


def _contract(prepared: PreparedInputs) -> dict[str, Any]:
    config = prepared.config
    return {
        "contract_version": "nlos-slot-activation-contract-v1",
        "model_id": config.model_id,
        "model_version": config.model_version,
        "state_equation": {
            "z_active": "Bernoulli(p_stage4_confirmed_support_active[environment,elevation_band])",
            "k_active_if_z_one": "Categorical(q_1,q_2,q_3 | active)",
            "k_active_if_z_zero": 0,
        },
        "activation_modes": {
            "EMPIRICAL_CONFIRMED_SUPPORT": "sample Z from the bounded Stage4-confirmed-support occupancy proxy, then K",
            "CONDITIONAL_ACTIVE_STRESS": "force Z=1 for an explicitly labeled active stress block, then K",
        },
        "slot_mapping": config.slot_mapping,
        "block_policy": "sample Z, K and path parameters once at block start; hold fixed for every millisecond in the block",
        "support_provenance": {
            "occupancy_quantity": "p_stage4_confirmed_support_active",
            "zero_confirmed_is_not_los": True,
            "prior_only_is_not_empirical_validation": True,
            "path_parameter_source": "environment_elevation_path_distribution_v1 frozen external model",
        },
        "deferred": [
            "absolute RF power calibration",
            "phase initialization and evolution",
            "receiver lock-loss composition",
            "path lifetime and inter-block persistence",
            "final four-row simulator export",
        ],
        "source_config": config.raw,
        "gold_labels_used_for_selection": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
    }


def _model_json(prepared: PreparedInputs, config_sha256: str) -> dict[str, Any]:
    occupancy = {
        "global": asdict(prepared.occupancy.global_model),
        "environments": {key: asdict(value) for key, value in prepared.occupancy.environment_models.items()},
        "cells": {f"{environment}|{band}": asdict(value) for (environment, band), value in prepared.occupancy.cell_models.items()},
    }
    multiplicity = {
        "global": asdict(prepared.multiplicity.global_model),
        "environments": {key: asdict(value) for key, value in prepared.multiplicity.environment_models.items()},
        "cells": {f"{environment}|{band}": asdict(value) for (environment, band), value in prepared.multiplicity.cell_models.items()},
    }
    return {
        "model_id": prepared.config.model_id,
        "model_version": prepared.config.model_version,
        "model_status": "COMPLETED_WITH_LIMITATIONS",
        "sample_rate_hz": prepared.config.sample_rate_hz,
        "source_counts": {
            "eligible_runs": prepared.source_audit.eligible_run_count,
            "stage0_windows": prepared.source_audit.stage0_window_count,
            "confirmed_events": len(prepared.events),
            "confirmed_paths": len(prepared.event_paths),
        },
        "occupancy_hierarchy": occupancy,
        "multiplicity_hierarchy": multiplicity,
        "slot_mapping": prepared.config.slot_mapping,
        "configuration_sha256": config_sha256,
        "gold_labels_used_for_selection": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "provenance": {
            "parameter_model_manifest_sha256": prepared.config.source["path_model_manifest_sha256"],
            "gain_model_manifest_sha256": prepared.config.source["gain_model_manifest_sha256"],
            "stage4_target": "strict confirmed_multipath events and multipath paths only",
            "gold_labels_used_for_selection": False,
            "support_is_stage4_confirmed_proxy_not_physical_occurrence": True,
        },
        "execution_policy": prepared.config.execution_policy,
    }


def _model_report(prepared: PreparedInputs, qa_rows: Sequence[Mapping[str, Any]], bootstrap_rows: Sequence[Mapping[str, Any]]) -> str:
    counts = {
        "eligible_runs": prepared.source_audit.eligible_run_count,
        "stage0_windows": prepared.source_audit.stage0_window_count,
        "confirmed_events": len(prepared.events),
        "confirmed_paths": len(prepared.event_paths),
    }
    prior_cells = [
        f"{environment}|{band}"
        for (environment, band), model in prepared.occupancy.cell_models.items()
        if model.support_status == "PRIOR_ONLY"
    ]
    return "\n".join([
        "# Fixed Three-NLOS-Slot Activation Model v1",
        "",
        "Status: `COMPLETED_WITH_LIMITATIONS`",
        "",
        "This is an offline, scene-balanced Stage4-confirmed-support activation proxy. It is not a physical multipath occurrence probability and is not the completed darkroom signal generator.",
        "",
        "## Frozen accounting",
        "",
        f"- Eligible runs: {counts['eligible_runs']}",
        f"- Stage0 exposure windows: {counts['stage0_windows']}",
        f"- Strict confirmed events: {counts['confirmed_events']}",
        f"- Confirmed NLOS paths: {counts['confirmed_paths']}",
        f"- Scene-block bootstrap: {len(bootstrap_rows)} records; seed {prepared.config.uncertainty['bootstrap_seed']}",
        f"- QA draws: {len(qa_rows)} cell/mode summaries; {prepared.config.uncertainty['qa_draw_count']} draws per summary",
        "",
        "## Interpretation boundaries",
        "",
        "The occupancy layer uses the unique union of confirmed event center ±2 windows as a conservative support label. A zero-confirmed exposure is not LOS and not proof of no physical multipath. Stage1 candidates, Stage2 model orders and Stage3 reliable centers are not activation labels.",
        "",
        f"Prior-only occupancy cells: {', '.join(prior_cells) if prior_cells else 'none'}.",
        "",
        "Conditional K is fit only from event-level confirmed path counts and maps K=0/1/2/3 to 000/100/110/111. Slot IDs are deterministic delay-ordered labels within a block, not persistent reflector identities.",
        "",
        "Main/common-path gain, phase, receiver lock-loss mapping, path lifetime, inter-block persistence, absolute power and final simulator export remain separate/deferred layers.",
        "",
        "No raw IQ, MATLAB, SAGE, batch or 20.46 MHz processing was performed by this builder.",
        "",
    ])


def build_activation_model(
    project_root: Path,
    config_path: Path,
    output_dir: Path,
    *,
    allow_test_namespace: bool = False,
) -> BuildReceipt:
    """Build a fresh activation-model namespace after read-only preflight."""

    start = time.perf_counter()
    prepared = _prepare_inputs(
        project_root,
        config_path,
        output_dir,
        allow_test_namespace=allow_test_namespace,
    )
    root, target = _validate_namespace(
        prepared.root,
        output_dir,
        prepared.config,
        allow_test_namespace=allow_test_namespace,
    )
    config_sha256 = sha256_file(prepared.config_path)
    target.mkdir(parents=True, exist_ok=False)
    try:
        _write_csv(
            target / "source_preflight.csv",
            prepared.declared_source_rows,
            ("source_key", "source_kind", "path", "relative_path", "sha256", "size_bytes", "status"),
        )
        _write_csv(
            target / "stage0_source_manifest.csv",
            prepared.stage0_manifest_rows,
            (
                "run_id", "scene_id", "prn", "tracking_channel", "environment", "stage0_path",
                "stage0_sha256", "stage0_size_bytes", "expected_window_count", "loaded_window_count", "status",
            ),
        )
        _write_csv_gzip(
            target / "activation_exposure_grid.csv.gz",
            (_exposure_row(row) for row in prepared.evidence.exposure),
            tuple(_exposure_row(prepared.evidence.exposure[0]).keys()),
        )
        _write_csv(
            target / "confirmed_support_membership.csv",
            [
                {
                    **dict(membership),
                    "closure_complete": prepared.evidence.closure_complete.get(str(membership["event_id"])),
                    "support_semantics": "stage4_confirmed_support_proxy_only",
                }
                for membership in prepared.evidence.memberships
            ],
            (
                "event_id", "run_id", "scene_id", "window_id", "core_window_id", "membership_type",
                "distance_from_core", "continuity_segment", "closure_complete", "support_semantics",
            ),
        )
        _write_csv(
            target / "scene_cell_exposure.csv",
            _scene_cell_rows(prepared.scene_cells),
            (
                "scene_id", "environment", "elevation_band", "exposure_windows", "support_windows",
                "core_event_ids_json", "scene_rate", "support_semantics",
            ),
        )
        _write_csv(
            target / "cell_occupancy_parameters.csv",
            _occupancy_rows(prepared),
            (
                "environment", "elevation_band", "alpha", "beta", "mean", "q025", "q50", "q975",
                "direct_scene_count", "direct_core_event_count", "support_status", "parent_key",
                "exposure_windows", "support_windows", "time_weighted_support_fraction", "selected_quantity",
            ),
        )
        _write_csv(
            target / "multiplicity_event_catalog.csv",
            _multiplicity_event_rows(prepared.events),
            (
                "event_id", "run_id", "scene_id", "prn", "tracking_channel", "center_window_id", "environment",
                "elevation_deg", "elevation_band", "elevation_modeling_ready", "confirmed_path_count",
                "event_utc", "label_semantics",
            ),
        )
        _write_csv(
            target / "cell_multiplicity_parameters.csv",
            _multiplicity_rows(prepared),
            (
                "environment", "elevation_band", "categories", "counts", "alpha", "probabilities", "q025",
                "q50", "q975", "direct_event_count", "support_status", "parent_key", "conditional_semantics",
            ),
        )
        _write_csv(
            target / "observed_slot_assignment_audit.csv",
            _observed_slot_rows(prepared.events, prepared.event_paths),
            (
                "event_id", "run_id", "scene_id", "environment", "elevation_band", "confirmed_path_count",
                "nlos_path_id", "path_active", "path_status", "event_path_id", "relative_delay_ns",
                "relative_doppler_hz", "relative_amplitude_linear", "slot_order_semantics",
            ),
        )
        bootstrap = scene_block_bootstrap(prepared.evidence, prepared.events, prepared.config)
        bootstrap_rows = _bootstrap_rows(bootstrap)
        _write_csv(
            target / "bootstrap_uncertainty.csv",
            bootstrap_rows,
            (
                "replicate", "resample_unit", "sampled_scene_count", "sampled_scene_ids_json", "replicate_status",
                "environment_rate_json", "cell_rate_json", "environment_event_counts_json", "cell_event_counts_json",
                "failure_reason", "seed", "replicate_count",
            ),
        )
        qa_summaries = generate_activation_qa_draws(
            ActivationModel(prepared.occupancy, prepared.multiplicity, prepared.config.model_id),
            prepared.config,
        )
        qa_rows = _qa_rows(qa_summaries, prepared)
        _write_csv(
            target / "qa_draw_summary.csv",
            qa_rows,
            (
                "environment", "elevation_band", "activation_mode", "draw_count", "active_count",
                "active_fraction", "analytic_occupancy_mean", "k_counts_json", "seed", "frequency_tolerance",
                "support_status",
            ),
        )
        _write_json(target / "slot_activation_contract.json", _contract(prepared))
        _write_json(target / "nlos_slot_activation_model.json", _model_json(prepared, config_sha256))
        (target / "model_report.md").write_text(_model_report(prepared, qa_rows, bootstrap_rows), encoding="utf-8")

        output_hashes_excluding_manifest_and_receipt = {
            path.name: sha256_file(path)
            for path in sorted(target.iterdir())
            if path.is_file() and path.name not in {"model_manifest.json", "build_receipt.json"}
        }
        stage0_manifest_hash = sha256_file(target / "stage0_source_manifest.csv")
        manifest = {
            "manifest_version": "nlos-slot-activation-model-manifest-v1",
            "created_utc": _utc_now(),
            "model_id": prepared.config.model_id,
            "model_version": prepared.config.model_version,
            "model_status": "COMPLETED_WITH_LIMITATIONS",
            "output_namespace": str(target),
            "config_path": str(prepared.config_path),
            "config_sha256": config_sha256,
            "source_hashes": dict(prepared.source_audit.source_hashes),
            "stage0_source_manifest_sha256": stage0_manifest_hash,
            "stage0_source_hashes": dict(prepared.stage0_source_hashes),
            "source_counts": {
                "eligible_runs": prepared.source_audit.eligible_run_count,
                "stage0_windows": prepared.source_audit.stage0_window_count,
                "confirmed_events": len(prepared.events),
                "confirmed_paths": len(prepared.event_paths),
            },
            "closure_membership_count": len(prepared.evidence.memberships),
            "closure_complete_event_count": sum(prepared.evidence.closure_complete.values()),
            "gold_labels_used_for_selection": False,
            "posterior_gold_used_for_selection": False,
            "execution_policy": dict(prepared.config.execution_policy),
            "protected_pipeline": dict(prepared.config.protected_source),
            "backend": _backend_receipt(),
            "code_hashes": {
                "builder_sha256": sha256_file(Path(__file__).resolve()),
                "core_sha256": sha256_file(Path(__file__).with_name("nlos_slot_activation_core.py")),
                "config_sha256": config_sha256,
            },
            "frozen_parent_models": {
                "path_model_manifest_sha256": prepared.config.source["path_model_manifest_sha256"],
                "gain_model_manifest_sha256": prepared.config.source["gain_model_manifest_sha256"],
            },
            "required_output_files": list(REQUIRED_OUTPUT_FILES),
            "output_hashes_excluding_manifest_and_receipt": output_hashes_excluding_manifest_and_receipt,
            "elapsed_seconds_before_manifest": time.perf_counter() - start,
        }
        _write_json(target / "model_manifest.json", manifest)
        manifest_hash = sha256_file(target / "model_manifest.json")
        output_files = tuple(sorted(path.name for path in target.iterdir() if path.is_file()))
        output_hashes = {name: sha256_file(target / name) for name in output_files if name != "build_receipt.json"}
        receipt_data = {
            "receipt_version": "nlos-slot-activation-build-receipt-v1",
            "status": "COMPLETED_WITH_LIMITATIONS",
            "created_utc": _utc_now(),
            "output_dir": str(target),
            "model_manifest_sha256": manifest_hash,
            "config_sha256": config_sha256,
            "source_hashes": dict(prepared.source_audit.source_hashes),
            "stage0_source_manifest_sha256": stage0_manifest_hash,
            "source_counts": manifest["source_counts"],
            "execution_policy": dict(prepared.config.execution_policy),
            "raw_iq_read": False,
            "matlab_executed": False,
            "sage_executed": False,
            "batch_executed": False,
            "output_files_excluding_receipt": [name for name in output_files if name != "build_receipt.json"],
            "output_hashes_excluding_receipt": output_hashes,
            "elapsed_seconds": time.perf_counter() - start,
        }
        _write_json(target / "build_receipt.json", receipt_data)
        return BuildReceipt(
            status="COMPLETED_WITH_LIMITATIONS",
            output_dir=str(target),
            model_manifest_sha256=manifest_hash,
            config_sha256=config_sha256,
            source_hashes=dict(prepared.source_audit.source_hashes),
            source_counts=dict(manifest["source_counts"]),
            execution_policy=dict(prepared.config.execution_policy),
            output_files=tuple(sorted(path.name for path in target.iterdir() if path.is_file())),
            output_hashes={name: sha256_file(target / name) for name in sorted(path.name for path in target.iterdir() if path.is_file())},
        )
    except Exception as exc:
        failure = {
            "receipt_version": "nlos-slot-activation-build-receipt-v1",
            "status": "FAILED",
            "created_utc": _utc_now(),
            "output_dir": str(target),
            "error": f"{type(exc).__name__}: {exc}",
            "execution_policy": dict(prepared.config.execution_policy),
            "raw_iq_read": False,
            "matlab_executed": False,
            "sage_executed": False,
            "batch_executed": False,
        }
        _write_json(target / "build_receipt.json", failure)
        raise


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.validate_only:
            result = preflight(args.project_root, args.config, args.output)
            print(json.dumps(_json_safe(result), indent=2, ensure_ascii=False, sort_keys=True))
            print("VALIDATION_ONLY=PASS")
            return 0
        receipt = build_activation_model(args.project_root, args.config, args.output)
        print(f"MODEL_OUTPUT={receipt.output_dir}")
        print(f"MODEL_MANIFEST_SHA256={receipt.model_manifest_sha256}")
        return 0
    except Exception as exc:
        print(f"MODEL_BUILD_REJECTED={type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
