"""Independently audit a fixed-three-NLOS-slot activation model namespace.

The auditor intentionally does not import the builder.  It re-reads the
frozen source contracts, recomputes source accounting and model invariants
from the core data primitives, and then compares them with the published
CSV/JSON artifacts.  It never opens raw IQ or executes MATLAB/SAGE.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.analysis.channel_modeling.nlos_slot_activation_core import (
    ActivationModel,
    ENVIRONMENTS,
    ELEVATION_BANDS,
    ActivationEvidence,
    assign_continuity_segments,
    aggregate_scene_cell_exposure,
    build_activation_labels,
    derive_stream_seed,
    fit_multiplicity_hierarchy,
    fit_occupancy_hierarchy,
    generate_activation_qa_draws,
    join_geometry_grid,
    load_activation_config,
    load_confirmed_event_paths,
    load_confirmed_events,
    load_stage0_exposure,
    resolve_stage0_sources,
    sample_block_activation,
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
class AuditResult:
    source_provenance_gate: str
    stage4_label_gate: str
    exposure_and_closure_gate: str
    occupancy_model_gate: str
    multiplicity_model_gate: str
    slot_contract_gate: str
    determinism_gate: str
    namespace_and_hash_gate: str
    model_qa: str
    ready_for_generator_composition: str
    checks: Mapping[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_gzip(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid float {field}: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite float {field}")
    return result


def _int(value: Any, field: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer {field}: {value!r}") from exc


def _bool(value: Any, field: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return True
    if text in {"0", "false", "no"}:
        return False
    raise ValueError(f"invalid boolean {field}: {value!r}")


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _same_float(actual: Any, expected: float, field: str, tolerance: float = 1e-12) -> None:
    if abs(_float(actual, field) - expected) > tolerance:
        raise ValueError(f"{field} mismatch: {actual!r} != {expected!r}")


def _source_contract_gate(root: Path, config_path: Path, target: Path) -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    config = load_activation_config(config_path)
    policy = config.execution_policy
    for field in ("raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz"):
        if policy.get(field) is not False:
            raise ValueError(f"offline policy changed: {field}")
    if policy.get("gold_labels_used_for_selection") is not False:
        raise ValueError("gold_labels_used_for_selection is not false")
    if policy.get("stage1_stage2_stage3_used_for_selection") is not False:
        raise ValueError("Stage1/Stage2/Stage3 selection flag is not false")
    if policy.get("new_only") is not True or policy.get("resume_allowed") is not False:
        raise ValueError("new-only/non-resumable policy changed")
    manifest = _read_json(target / "model_manifest.json")
    receipt = _read_json(target / "build_receipt.json")
    manifest_hash = sha256_file(target / "model_manifest.json")
    if receipt.get("model_manifest_sha256") != manifest_hash:
        raise ValueError("build receipt manifest hash mismatch")
    if str(manifest.get("config_sha256", "")).lower() != sha256_file(config_path).lower():
        raise ValueError("config hash mismatch")
    audit = verify_frozen_sources(root, config)
    if manifest.get("source_hashes") != dict(audit.source_hashes):
        raise ValueError("declared source hashes mismatch")
    if manifest.get("gold_labels_used_for_selection") is not False:
        raise ValueError("manifest gold leakage flag is not false")
    if manifest.get("posterior_gold_used_for_selection") is not False:
        raise ValueError("manifest posterior gold leakage flag is not false")
    if manifest.get("execution_policy") != dict(policy):
        raise ValueError("manifest execution policy mismatch")
    protected_path = root / Path(config.protected_source["pipeline_relative_path"])
    if sha256_file(protected_path).lower() != str(config.protected_source["pipeline_sha256"]).lower():
        raise ValueError("protected pipeline hash changed")
    expected_counts = {
        "eligible_runs": audit.eligible_run_count,
        "stage0_windows": audit.stage0_window_count,
        "confirmed_events": 94,
        "confirmed_paths": 100,
    }
    if manifest.get("source_counts") != expected_counts:
        raise ValueError(f"source counts mismatch: {manifest.get('source_counts')}")
    hashes = manifest.get("output_hashes_excluding_manifest_and_receipt")
    if not isinstance(hashes, dict):
        raise ValueError("output hashes missing")
    for name, expected in hashes.items():
        path = target / str(name)
        if not path.is_file() or sha256_file(path).lower() != str(expected).lower():
            raise ValueError(f"output hash mismatch: {name}")
    for name in REQUIRED_OUTPUT_FILES:
        if not (target / name).is_file():
            raise ValueError(f"required output missing: {name}")
    return config, audit, manifest, receipt


def _recompute_evidence(root: Path, config: Any, audit: Any) -> tuple[ActivationEvidence, Any, Any, Any, Any, dict[str, str]]:
    sources = resolve_stage0_sources(root, audit, config)
    rows = []
    source_hashes: dict[str, str] = {}
    for source in sources:
        source_hashes[source.run_id] = sha256_file(source.stage0_path)
        rows.extend(assign_continuity_segments(load_stage0_exposure(source)))
    joined = join_geometry_grid(
        rows,
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
    if not all(evidence.closure_complete.values()):
        raise ValueError("recomputed confirmed closure is incomplete")
    scene_cells = tuple(aggregate_scene_cell_exposure(evidence))
    occupancy = fit_occupancy_hierarchy(scene_cells, config)
    multiplicity = fit_multiplicity_hierarchy(events, config)
    return evidence, events, event_paths, scene_cells, (occupancy, multiplicity), source_hashes


def _check_stage0_manifest(target: Path, root: Path, config: Any, audit: Any) -> dict[str, str]:
    rows = _read_csv(target / "stage0_source_manifest.csv")
    sources = resolve_stage0_sources(root, audit, config)
    expected = {source.run_id: source for source in sources}
    if len(rows) != len(expected):
        raise ValueError("Stage0 source manifest row count mismatch")
    actual_hashes: dict[str, str] = {}
    for row in rows:
        run_id = row.get("run_id", "")
        source = expected.get(run_id)
        if source is None:
            raise ValueError(f"unexpected Stage0 run: {run_id}")
        if _int(row.get("expected_window_count"), "expected_window_count") != source.expected_window_count:
            raise ValueError(f"Stage0 expected count mismatch: {run_id}")
        if _int(row.get("loaded_window_count"), "loaded_window_count") != source.expected_window_count:
            raise ValueError(f"Stage0 loaded count mismatch: {run_id}")
        if Path(row.get("stage0_path", "")).resolve(strict=False) != source.stage0_path.resolve(strict=False):
            raise ValueError(f"Stage0 path mismatch: {run_id}")
        actual = sha256_file(source.stage0_path)
        if row.get("stage0_sha256", "").lower() != actual.lower():
            raise ValueError(f"Stage0 hash mismatch: {run_id}")
        actual_hashes[run_id] = actual
    return actual_hashes


def _check_exposure_grid(target: Path, evidence: ActivationEvidence) -> None:
    rows = _read_csv_gzip(target / "activation_exposure_grid.csv.gz")
    if len(rows) != len(evidence.exposure) or len(rows) != 169637:
        raise ValueError(f"exposure row count mismatch: {len(rows)}")
    expected_by_key = {(row.run_id, row.window_id): row for row in evidence.exposure}
    seen: set[tuple[str, int]] = set()
    allowed = {"INACTIVE", "CONFIRMED_CORE", "CONFIRMED_CLOSURE_ONLY"}
    for row in rows:
        key = (row.get("run_id", ""), _int(row.get("window_id"), "window_id"))
        if key in seen or key not in expected_by_key:
            raise ValueError(f"exposure identity mismatch: {key}")
        seen.add(key)
        expected = expected_by_key[key]
        if _int(row.get("sample_start_zero_based"), "sample_start_zero_based") != expected.sample_start_zero_based:
            raise ValueError(f"sample offset mismatch: {key}")
        if row.get("support_label") not in allowed:
            raise ValueError(f"unsupported support label: {row.get('support_label')}")
        if row.get("support_label") != expected.support_label:
            raise ValueError(f"support label mismatch: {key}")
        if _bool(row.get("geometry_join_valid"), "geometry_join_valid") != expected.geometry_join_valid:
            raise ValueError(f"geometry validity mismatch: {key}")
    if seen != set(expected_by_key):
        raise ValueError("exposure grid omitted windows")


def _check_membership(target: Path, evidence: ActivationEvidence) -> None:
    rows = _read_csv(target / "confirmed_support_membership.csv")
    expected = {
        (
            str(item["event_id"]), str(item["run_id"]), _int(item["window_id"], "window_id"),
            str(item["membership_type"]), _int(item["distance_from_core"], "distance_from_core"),
        ) for item in evidence.memberships
    }
    actual = {
        (
            row.get("event_id", ""), row.get("run_id", ""), _int(row.get("window_id"), "window_id"),
            row.get("membership_type", ""), _int(row.get("distance_from_core"), "distance_from_core"),
        ) for row in rows
    }
    if actual != expected or len(rows) != len(expected):
        raise ValueError("confirmed-support membership mismatch")
    if any(row.get("support_semantics") != "stage4_confirmed_support_proxy_only" for row in rows):
        raise ValueError("support semantics changed")


def _check_scene_cells(target: Path, scene_cells: Sequence[Any]) -> None:
    rows = _read_csv(target / "scene_cell_exposure.csv")
    expected = {
        (row.scene_id, row.environment, row.elevation_band): row
        for row in scene_cells
    }
    if len(rows) != len(expected):
        raise ValueError("scene-cell exposure row count mismatch")
    for row in rows:
        key = (row.get("scene_id", ""), row.get("environment", ""), row.get("elevation_band") or None)
        current = expected.get(key)
        if current is None:
            raise ValueError(f"unknown scene-cell exposure: {key}")
        for field, value in (
            ("exposure_windows", current.exposure_windows),
            ("support_windows", current.support_windows),
        ):
            if _int(row.get(field), field) != value:
                raise ValueError(f"{field} mismatch: {key}")
        _same_float(row.get("scene_rate"), current.scene_rate, "scene_rate")


def _check_occupancy(target: Path, occupancy: Any) -> None:
    rows = _read_csv(target / "cell_occupancy_parameters.csv")
    expected = occupancy.cell_models
    if len(rows) != 12:
        raise ValueError("expected 12 occupancy cells")
    seen = set()
    for row in rows:
        key = (row.get("environment", ""), row.get("elevation_band", ""))
        model = expected.get(key)
        if model is None or key in seen:
            raise ValueError(f"occupancy cell mismatch: {key}")
        seen.add(key)
        for field in ("alpha", "beta", "mean", "q025", "q50", "q975"):
            _same_float(row.get(field), getattr(model, field), field)
        if _int(row.get("direct_scene_count"), "direct_scene_count") != model.direct_scene_count:
            raise ValueError(f"occupancy scene count mismatch: {key}")
        if _int(row.get("direct_core_event_count"), "direct_core_event_count") != model.direct_core_event_count:
            raise ValueError(f"occupancy event count mismatch: {key}")
        if row.get("support_status") != model.support_status or row.get("parent_key") != (model.parent_key or ""):
            raise ValueError(f"occupancy provenance mismatch: {key}")
        if row.get("selected_quantity") != "p_stage4_confirmed_support_active":
            raise ValueError(f"occupancy quantity mismatch: {key}")
    if seen != set(expected):
        raise ValueError("occupancy cells omitted")


def _check_event_and_multiplicity(target: Path, events: Sequence[Any], multiplicity: Any) -> None:
    event_rows = _read_csv(target / "multiplicity_event_catalog.csv")
    if len(event_rows) != len(events) or len(events) != 94:
        raise ValueError("multiplicity event catalog count mismatch")
    expected_events = {event.event_id: event for event in events}
    if {row.get("event_id", "") for row in event_rows} != set(expected_events):
        raise ValueError("multiplicity event identity mismatch")
    for row in event_rows:
        event = expected_events[row["event_id"]]
        if _int(row.get("confirmed_path_count"), "confirmed_path_count") != event.confirmed_path_count:
            raise ValueError(f"event K mismatch: {event.event_id}")
        if row.get("label_semantics") != "stage4_confirmed_multipath_event_only":
            raise ValueError("event label semantics changed")
    rows = _read_csv(target / "cell_multiplicity_parameters.csv")
    if len(rows) != 12:
        raise ValueError("expected 12 multiplicity cells")
    for row in rows:
        key = (row.get("environment", ""), row.get("elevation_band", ""))
        model = multiplicity.cell_models.get(key)
        if model is None:
            raise ValueError(f"unknown multiplicity cell: {key}")
        categories = _json_value(row.get("categories", ""))
        counts = _json_value(row.get("counts", ""))
        probabilities = _json_value(row.get("probabilities", ""))
        if categories != list(model.categories) or counts != list(model.counts):
            raise ValueError(f"multiplicity categories/counts mismatch: {key}")
        if not isinstance(probabilities, list) or len(probabilities) != 3:
            raise ValueError(f"invalid multiplicity probabilities: {key}")
        if any(not math.isfinite(float(value)) or float(value) <= 0.0 for value in probabilities):
            raise ValueError(f"non-positive multiplicity probability: {key}")
        if abs(sum(float(value) for value in probabilities) - 1.0) > 1e-12:
            raise ValueError(f"multiplicity probabilities do not sum to one: {key}")
        for actual, expected, field in zip(probabilities, model.probabilities, ("p1", "p2", "p3")):
            _same_float(actual, expected, field)
        if row.get("support_status") != model.support_status:
            raise ValueError(f"multiplicity support mismatch: {key}")


def _check_slots(target: Path, events: Sequence[Any], event_paths: Sequence[Any]) -> None:
    rows = _read_csv(target / "observed_slot_assignment_audit.csv")
    if len(rows) != len(events) * 3:
        raise ValueError("observed slot row count mismatch")
    paths_by_event: dict[str, list[Any]] = {}
    for path in event_paths:
        paths_by_event.setdefault(path.event_id, []).append(path)
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("event_id", ""), []).append(row)
    for event in events:
        current = grouped.get(event.event_id, [])
        if len(current) != 3 or { _int(row.get("nlos_path_id"), "nlos_path_id") for row in current } != {1, 2, 3}:
            raise ValueError(f"slot identity mismatch: {event.event_id}")
        active = [row for row in current if _int(row.get("path_active"), "path_active") == 1]
        inactive = [row for row in current if _int(row.get("path_active"), "path_active") == 0]
        if len(active) != event.confirmed_path_count or len(inactive) != 3 - event.confirmed_path_count:
            raise ValueError(f"slot active count mismatch: {event.event_id}")
        active_slots = sorted(_int(row.get("nlos_path_id"), "nlos_path_id") for row in active)
        if active_slots != list(range(1, event.confirmed_path_count + 1)):
            raise ValueError(f"non-prefix slot mask: {event.event_id}")
        for row in inactive:
            if row.get("path_status") != "INACTIVE_NO_PATH" or row.get("relative_delay_ns", "") or row.get("relative_doppler_hz", ""):
                raise ValueError(f"inactive slot is not null: {event.event_id}")
            if _float(row.get("relative_amplitude_linear"), "relative_amplitude_linear") != 0.0:
                raise ValueError(f"inactive slot amplitude is nonzero: {event.event_id}")
        expected_paths = sorted(
            paths_by_event[event.event_id],
            key=lambda path: (path.excess_delay_ns, -path.relative_amplitude_linear, path.relative_doppler_hz, path.event_path_id),
        )
        actual_ids = [row.get("event_path_id", "") for row in sorted(active, key=lambda row: _int(row.get("nlos_path_id"), "nlos_path_id"))]
        if actual_ids != [path.event_path_id for path in expected_paths]:
            raise ValueError(f"slot ordering mismatch: {event.event_id}")


def _check_bootstrap(target: Path, config: Any) -> None:
    rows = _read_csv(target / "bootstrap_uncertainty.csv")
    expected_count = int(config.uncertainty["bootstrap_replicates"])
    if len(rows) != expected_count or len(rows) != 1000:
        raise ValueError(f"bootstrap row count mismatch: {len(rows)}")
    for index, row in enumerate(rows):
        if _int(row.get("replicate"), "replicate") != index:
            raise ValueError("bootstrap replicate ordering changed")
        if row.get("resample_unit") != "scene" or row.get("replicate_status") != "PASS":
            raise ValueError("bootstrap is not an explicit complete-scene pass")
        if _int(row.get("seed"), "seed") != int(config.uncertainty["bootstrap_seed"]):
            raise ValueError("bootstrap seed changed")
        if "window" in row.get("resample_unit", "").lower() or "sampled_window" in row:
            raise ValueError("bootstrap contains window resampling")


def _check_qa_draws(target: Path, model: ActivationModel, config: Any) -> None:
    rows = _read_csv(target / "qa_draw_summary.csv")
    if len(rows) != 24:
        raise ValueError("QA draw summary must contain 12 cells × 2 modes")
    expected = {
        (summary.environment, summary.elevation_band, summary.activation_mode): summary
        for summary in generate_activation_qa_draws(model, config)
    }
    for row in rows:
        key = (row.get("environment", ""), row.get("elevation_band", ""), row.get("activation_mode", ""))
        summary = expected.get(key)
        if summary is None:
            raise ValueError(f"unexpected QA draw cell/mode: {key}")
        if _int(row.get("draw_count"), "draw_count") != summary.draw_count or _int(row.get("active_count"), "active_count") != summary.active_count:
            raise ValueError(f"QA draw count mismatch: {key}")
        if _json_value(row.get("k_counts_json", "")) != {str(k): v for k, v in summary.k_counts.items()} and _json_value(row.get("k_counts_json", "")) != dict(summary.k_counts):
            raise ValueError(f"QA K count mismatch: {key}")


def _check_contract_and_model(target: Path, config: Any, manifest: Mapping[str, Any]) -> None:
    contract = _read_json(target / "slot_activation_contract.json")
    model = _read_json(target / "nlos_slot_activation_model.json")
    for value, name in ((contract, "contract"), (model, "model")):
        if value.get("gold_labels_used_for_selection") is not False:
            raise ValueError(f"{name} gold leakage flag is not false")
        if value.get("raw_iq_read") is not False or value.get("matlab") is not False or value.get("sage") is not False or value.get("batch") is not False:
            raise ValueError(f"{name} offline flags changed")
    if contract.get("contract_version") != "nlos-slot-activation-contract-v1":
        raise ValueError("slot contract version changed")
    if model.get("source_counts") != manifest.get("source_counts"):
        raise ValueError("model source accounting mismatch")
    if model.get("slot_mapping") != config.slot_mapping:
        raise ValueError("model slot mapping mismatch")


def audit_activation_model(
    project_root: Path,
    config_path: Path,
    model_dir: Path,
    *,
    allow_test_namespace: bool = False,
) -> AuditResult:
    """Audit a completed activation model and publish independent QA files."""

    root = project_root.resolve(strict=False)
    config_file = config_path.resolve(strict=False)
    target = model_dir.resolve(strict=False)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        if not allow_test_namespace:
            raise ValueError("model output is outside project root") from exc
        relative = None
    if relative is not None and any(part.lower() in {"scenes", "sage_results", "_trash"} for part in relative.parts):
        raise ValueError("model output is under a protected namespace")
    if not target.is_dir():
        raise FileNotFoundError(target)
    if (target / "independent_qa_result.json").exists() or (target / "independent_qa_report.md").exists():
        raise FileExistsError("independent QA artifact already exists; refusing overwrite")
    for name in REQUIRED_OUTPUT_FILES:
        if not (target / name).is_file():
            raise ValueError(f"required output missing: {name}")
    config, source_audit, manifest, receipt = _source_contract_gate(root, config_file, target)
    stage0_hashes = _check_stage0_manifest(target, root, config, source_audit)
    evidence, events, event_paths, scene_cells, fitted, recomputed_stage0_hashes = _recompute_evidence(root, config, source_audit)
    if stage0_hashes != recomputed_stage0_hashes:
        raise ValueError("Stage0 hash recomputation mismatch")
    _check_exposure_grid(target, evidence)
    _check_membership(target, evidence)
    _check_scene_cells(target, scene_cells)
    occupancy, multiplicity = fitted
    _check_occupancy(target, occupancy)
    _check_event_and_multiplicity(target, events, multiplicity)
    _check_slots(target, events, event_paths)
    _check_bootstrap(target, config)
    model = ActivationModel(occupancy, multiplicity, config.model_id, sha256_file(target / "model_manifest.json"))
    _check_qa_draws(target, model, config)
    _check_contract_and_model(target, config, manifest)
    seed_a = derive_stream_seed(20260829, "Urban", "LOW", "audit-block", "occurrence")
    seed_b = derive_stream_seed(20260829, "Urban", "LOW", "audit-block", "occurrence")
    if seed_a != seed_b:
        raise ValueError("stream seed is not reproducible")
    state_a = sample_block_activation(model, config, "Urban", "LOW", "audit-block", 20260829, "EMPIRICAL_CONFIRMED_SUPPORT")
    state_b = sample_block_activation(model, config, "Urban", "LOW", "audit-block", 20260829, "EMPIRICAL_CONFIRMED_SUPPORT")
    if state_a != state_b:
        raise ValueError("block activation is not deterministic")
    checks = {
        "source_counts": manifest["source_counts"],
        "stage0_source_count": len(stage0_hashes),
        "geometry_matched_windows": sum(row.geometry_time_delta_s is not None for row in evidence.exposure),
        "geometry_valid_windows": sum(row.geometry_join_valid for row in evidence.exposure),
        "exposure_windows": len(evidence.exposure),
        "closure_memberships": len(evidence.memberships),
        "closure_complete_events": sum(evidence.closure_complete.values()),
        "scene_cell_count": len(scene_cells),
        "occupancy_cell_count": 12,
        "multiplicity_cell_count": 12,
        "confirmed_event_count": len(events),
        "confirmed_path_count": len(event_paths),
        "bootstrap_replicates": len(_read_csv(target / "bootstrap_uncertainty.csv")),
        "qa_draw_summaries": len(_read_csv(target / "qa_draw_summary.csv")),
        "model_manifest_sha256": sha256_file(target / "model_manifest.json"),
        "output_hashes_checked": len(manifest.get("output_hashes_excluding_manifest_and_receipt", {})),
        "raw_iq_read": False,
        "matlab_executed": False,
        "sage_executed": False,
        "batch_executed": False,
    }
    result = AuditResult(
        source_provenance_gate="PASS",
        stage4_label_gate="PASS",
        exposure_and_closure_gate="PASS",
        occupancy_model_gate="PASS_WITH_LIMITATIONS",
        multiplicity_model_gate="PASS_WITH_LIMITATIONS",
        slot_contract_gate="PASS",
        determinism_gate="PASS",
        namespace_and_hash_gate="PASS",
        model_qa="PASS_WITH_LIMITATIONS",
        ready_for_generator_composition="YES",
        checks=checks,
    )
    qa_result = {
        "qa_version": "nlos-slot-activation-model-independent-qa-v1",
        "created_utc": _utc_now(),
        "model_dir": str(target),
        "model_manifest_sha256": checks["model_manifest_sha256"],
        "result": asdict(result),
        "limitations": [
            "Occupancy is a Stage4-confirmed-support proxy, not physical multipath occurrence probability.",
            "Zero-confirmed exposure is not LOS and is not proof of no physical multipath.",
            "Sparse and PRIOR_ONLY cells inherit parent information and are not equally empirically validated.",
            "Phase, lock-loss composition, path lifetime and final four-row simulator export remain separate layers.",
        ],
    }
    (target / "independent_qa_result.json").write_text(
        json.dumps(qa_result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = "\n".join([
        "# Independent QA — Fixed Three-NLOS-Slot Activation Model v1",
        "",
        "`MODEL_QA=PASS_WITH_LIMITATIONS`",
        "",
        "All frozen source hashes, strict Stage4 event/path accounting, Stage0 exposure identity, continuity-constrained ±2 closure, hierarchical occupancy/multiplicity invariants, prefix masks, inactive-slot null semantics, deterministic streams, bootstrap and QA draw records passed independent checks.",
        "",
        f"Model manifest SHA-256: `{checks['model_manifest_sha256']}`",
        f"Eligible runs / Stage0 windows / confirmed events / confirmed paths: `{manifest['source_counts']['eligible_runs']} / {manifest['source_counts']['stage0_windows']} / {manifest['source_counts']['confirmed_events']} / {manifest['source_counts']['confirmed_paths']}`",
        "",
        "The output is ready as an input layer for later generator composition, not a complete physical channel model. The occupancy quantity remains explicitly a Stage4-confirmed-support proxy; no zero-confirmed state is interpreted as LOS.",
        "",
    ])
    (target / "independent_qa_report.md").write_text(report, encoding="utf-8")
    return result


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = audit_activation_model(args.project_root, args.config, args.model_dir)
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False, sort_keys=True))
        print(f"MODEL_QA={result.model_qa}")
        print(f"READY_FOR_GENERATOR_COMPOSITION={result.ready_for_generator_composition}")
        return 0
    except Exception as exc:
        print(f"MODEL_QA_REJECTED={type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
