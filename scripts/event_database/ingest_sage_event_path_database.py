"""Build the versioned SAGE event/path audit tables from QA-passed outputs.

This is a downstream, read-only-to-SAGE conversion layer.  It never starts
MATLAB/SAGE, opens raw IQ, or writes into any scene result directory.  The
ingestion partition is created atomically under the versioned database
namespace.  Legacy G06 is retained for provenance and event audit, but its
missing run_context makes it ineligible for modeling input.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from validate_sage_database_dry_run import (
    FROZEN_SOURCE_HASHES,
    REFERENCE_FIXTURE,
    REQUIRED_FILES,
    REQUIRED_HEADERS,
    _int,
    _is_one,
    _text,
    load_csv,
    load_json,
    sha256_file,
    strict_confirmation,
    validate_current_batch,
    validate_reference_fixture,
)


INGESTION_VERSION = "sage-event-path-db-v1/ingest-v1"
DEFAULT_INGESTION_ID = "ingestion_20260825_event_path_v1"
REFERENCE_QA_REPORT = "scenes/F1023_V70_D0117_P2/sage_results/reference_scene_final_validation_report.md"


def modeling_eligibility(*, context_present: bool, run_complete: bool) -> str:
    if not context_present:
        return "excluded_legacy_context_missing"
    if not run_complete:
        return "excluded_incomplete"
    return "eligible_pending_modeling_qa"


def classify_run_label(*, confirmed_events: int, reference_control: bool) -> str:
    if confirmed_events > 0:
        return "confirmed_multipath"
    if reference_control:
        return "los_reference"
    return "no_confirmed_event"


def build_event_context_row(
    *,
    event_id: str,
    run_id: str,
    scene_id: str,
    prn: str,
    center_window_id: str,
    recording_time_s: Any,
    tow_s: Any,
    cn0_db_hz: Any,
    vehicle_speed_kmh: Any,
    speed_source: Any,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "run_id": run_id,
        "scene_id": scene_id,
        "prn": prn,
        "center_window_id": center_window_id,
        "recording_time_s": recording_time_s,
        "tow_s": tow_s,
        "event_utc": None,
        "elevation_deg": None,
        "azimuth_deg": None,
        "tracking_cn0_db_hz": cn0_db_hz,
        "nmea_snr_db_hz": None,
        "vehicle_speed_kmh": vehicle_speed_kmh,
        "speed_source": speed_source,
        "geometry_join_status": "deferred_unavailable",
        "geometry_join_valid": "0",
        "geometry_join_method": None,
        "geometry_source_utc": None,
        "geometry_time_delta_s": None,
        "time_alignment_id": None,
        "missing_reason": "verified_time_alignment_not_available",
        "observation_quality": "inconclusive",
        "derivation_version": "sage-event-path-derivation-v1",
    }


def _relpath(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _normalise_value(value: Any) -> Any:
    return "" if value is None else value


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _normalise_value(row.get(field)) for field in fieldnames})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_fingerprint(source_hashes: dict[str, str]) -> str:
    payload = json.dumps(source_hashes, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_context(path: Path) -> dict[str, Any] | None:
    return load_json(path) if path.is_file() else None


def _read_rows(output_dir: Path) -> dict[str, list[dict[str, str]]]:
    tables: dict[str, list[dict[str, str]]] = {}
    for key, filename in REQUIRED_FILES.items():
        rows, issues = load_csv(output_dir / filename, REQUIRED_HEADERS[key])
        if issues:
            raise ValueError(f"{output_dir}: {issues}")
        tables[key] = rows
    return tables


def _source_hashes(output_dir: Path) -> dict[str, str]:
    hashes = {}
    for filename in list(REQUIRED_FILES.values()) + ["run_context.json"]:
        path = output_dir / filename
        if path.is_file():
            hashes[filename] = sha256_file(path)
    return hashes


def _current_descriptors(root: Path, run_id: str) -> list[dict[str, Any]]:
    manifest_path = root / "dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json"
    summary_path = root / "dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv"
    request_root = root / "dataset_generation_logs/batch_sage_execution_requests"
    manifest = load_json(manifest_path)
    manifest_tasks = {_text(item.get("task_id")): item for item in manifest.get("tasks", [])}
    summary_rows, issues = load_csv(summary_path, {"task_id", "result_directory", "qa_report_path", "execution_log_path"})
    if issues:
        raise ValueError(f"summary: {issues}")
    summary_by_task = {_text(row.get("task_id")): row for row in summary_rows}
    descriptors: list[dict[str, Any]] = []
    for request_dir in sorted(request_root.glob(f"windows_unattended_*_{run_id}_*")):
        request = load_json(request_dir / "execution_request.json")
        plan_rows, plan_issues = load_csv(
            request_dir / "approved_plan_snapshot.csv",
            {"scene_id", "prn", "tracking_channel", "output_path", "sample_rate_hz", "production_task_id"},
        )
        if plan_issues or len(plan_rows) != 1:
            raise ValueError(f"request plan {request_dir.name}: {plan_issues} rows={len(plan_rows)}")
        plan = plan_rows[0]
        production_task_id = _text(plan.get("production_task_id"))
        manifest_task = manifest_tasks[production_task_id]
        wrapper_task_id = _text(request.get("ordered_task_ids", [""])[0])
        summary = summary_by_task[wrapper_task_id]
        output_dir = Path(_text(plan.get("output_path")))
        context = _read_context(output_dir / "run_context.json")
        descriptors.append(
            {
                "scope": "current_batch",
                "scene_id": _text(plan.get("scene_id")),
                "scene_role": _text(manifest_task.get("scene_role")),
                "prn": _text(plan.get("prn")),
                "channel": _int(plan.get("tracking_channel"), None),
                "sample_rate_hz": _int(plan.get("sample_rate_hz"), None),
                "output_dir": output_dir,
                "experiment_namespace": "nav_sage_v2",
                "batch": _text(manifest_task.get("batch")),
                "acceptance_class": "formal_accepted_production" if _text(manifest_task.get("batch")) in {"B_main_production_batch", "C_long_running_batch"} else "validated_only",
                "context": context,
                "request_id": _text(request.get("request_id")),
                "request_sha256": sha256_file(request_dir / "execution_request.json"),
                "qa_report_path": Path(_text(summary.get("qa_report_path"))),
                "execution_log_path": Path(_text(summary.get("execution_log_path"))),
                "pipeline_sha256": _text(request.get("pipeline_sha256")),
                "manifest_sha256": _text(request.get("production_manifest_sha256")),
                "inventory_sha256": _text(request.get("production_inventory_sha256")),
                "metadata_path": Path(_text(plan.get("metadata_path"))),
                "geometry_summary_path": Path(_text(plan.get("satellite_summary_path"))),
                "reference_control": False,
            }
        )
    return descriptors


def _reference_descriptors(root: Path) -> list[dict[str, Any]]:
    descriptors: list[dict[str, Any]] = []
    scene_id = "F1023_V70_D0117_P2"
    scene_dir = root / "scenes" / scene_id
    for expected in REFERENCE_FIXTURE:
        output_dir = root / Path(expected["relative_output"])
        context = _read_context(output_dir / "run_context.json")
        geometry_summary = scene_dir / "satellite" / f"{scene_id}_satellite_elevation_summary.csv"
        descriptors.append(
            {
                "scope": "reference_fixture",
                "scene_id": scene_id,
                "scene_role": "reference_scene",
                "prn": expected["prn"],
                "channel": expected["channel"],
                "sample_rate_hz": 10230000,
                "output_dir": output_dir,
                "experiment_namespace": output_dir.name if expected["prn"] == "G06" else "nav_sage_v2",
                "batch": "reference_fixture",
                "acceptance_class": "reference_validation",
                "context": context,
                "request_id": "",
                "request_sha256": "",
                "qa_report_path": root / REFERENCE_QA_REPORT,
                "execution_log_path": None,
                "pipeline_sha256": "",
                "manifest_sha256": "",
                "inventory_sha256": "",
                "metadata_path": scene_dir / "metadata.json",
                "geometry_summary_path": geometry_summary,
                "reference_control": bool(expected.get("reference_control")),
                "reference_expected_label": expected["label"],
            }
        )
    return descriptors


def _run_id(descriptor: dict[str, Any], ingestion_id: str) -> str:
    return (
        f"{descriptor['scene_id']}__{descriptor['prn']}__ch{descriptor['channel']}__"
        f"{descriptor['experiment_namespace']}__{ingestion_id}"
    )


def _base_run_row(root: Path, descriptor: dict[str, Any], run_id: str, tables: dict[str, list[dict[str, str]]], source_hashes: dict[str, str], validation: dict[str, Any]) -> dict[str, Any]:
    context = descriptor["context"] or {}
    counts = validation["counts"]
    return {
        "run_id": run_id,
        "logical_run_key": f"{descriptor['scene_id']}__{descriptor['prn']}__ch{descriptor['channel']}__{descriptor['experiment_namespace']}",
        "scene_id": descriptor["scene_id"],
        "scene_role": descriptor["scene_role"],
        "prn": descriptor["prn"],
        "constellation": "G",
        "prn_number": descriptor["prn"][1:],
        "tracking_channel": descriptor["channel"],
        "signal_type": "GPS_L1_CA",
        "sampling_rate_hz": descriptor["sample_rate_hz"],
        "raw_storage_mode": "external_storage_or_scene_local",
        "raw_file_relpath": context.get("rawFile"),
        "tracking_file_relpath": context.get("trackingFile"),
        "telemetry_file_relpath": context.get("telemetryFile"),
        "rinex_nav_relpath": context.get("rinexNavFiles"),
        "trajectory_relpath": context.get("nmeaFiles"),
        "satellite_geometry_relpaths": json.dumps(context.get("satelliteFiles", [str(descriptor["geometry_summary_path"])]), ensure_ascii=False),
        "pipeline_family": "nav_sage_pipeline",
        "pipeline_version": None,
        "experiment_namespace": descriptor["experiment_namespace"],
        "context_version": context.get("contextVersion"),
        "parameter_set_id": "not_recorded",
        "code_commit": None,
        "code_sha256": descriptor["pipeline_sha256"],
        "run_created_at_utc": context.get("createdAtUtc"),
        "source_result_relpath": _relpath(root, descriptor["output_dir"]),
        "source_fingerprint": _source_fingerprint(source_hashes),
        "ingestion_version": INGESTION_VERSION,
        "run_status": "complete",
        "stage0_status": "complete",
        "stage1_status": "complete",
        "stage2_status": "complete",
        "stage3_status": "complete" if counts["stage3_reliable_centers"] > 0 else "empty_valid",
        "stage4_status": "complete" if counts["stage4_rows"] > 0 else "empty_valid",
        "stage0_nav_symbol_count": counts["stage0_symbols"],
        "stage0_window_count": counts["stage0_windows"],
        "stage1_scanned_count": counts["stage1_scanned"],
        "stage1_candidate_count": counts["stage2_selected"],
        "stage2_L1_count": sum(1 for row in tables["stage2_windows"] if _int(row.get("selected_L"), 0) == 1),
        "stage2_L2_count": sum(1 for row in tables["stage2_windows"] if _int(row.get("selected_L"), 0) == 2),
        "stage2_L3_count": sum(1 for row in tables["stage2_windows"] if _int(row.get("selected_L"), 0) == 3),
        "stage2_L4_count": sum(1 for row in tables["stage2_windows"] if _int(row.get("selected_L"), 0) == 4),
        "stage2_L_ge_2_count": counts["stage2_l_ge_2"],
        "stage2_L_ge_3_count": counts["stage2_l_ge_3"],
        "stage3_reliable_event_count": counts["stage3_reliable_centers"],
        "stage4_joint_result_count": counts["stage4_rows"],
        "confirmed_event_count": counts["confirmed_events"],
        "confirmed_path_count": counts["confirmed_paths"],
        "qa_status": "pass",
        "qa_issue_count": 0,
        "request_id": descriptor["request_id"],
        "request_sha256": descriptor["request_sha256"],
        "qa_report_path": descriptor["qa_report_path"],
        "execution_log_path": descriptor["execution_log_path"],
        "manifest_sha256": descriptor["manifest_sha256"],
        "inventory_sha256": descriptor["inventory_sha256"],
        "acceptance_class": descriptor["acceptance_class"],
        "batch": descriptor["batch"],
        "context_missing_legacy": "1" if descriptor["context"] is None else "0",
        "modeling_eligibility": modeling_eligibility(context_present=descriptor["context"] is not None, run_complete=True),
    }


def _geometry_row(root: Path, descriptor: dict[str, Any], run_id: str, source_hashes: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = descriptor["geometry_summary_path"]
    issues: list[dict[str, Any]] = []
    rows, load_issues = load_csv(path, {"prn"})
    if load_issues:
        issues.append({"severity": "warning", "issue_code": "geometry_summary_unavailable", "run_id": run_id, "detail": ";".join(load_issues), "action": "keep_geometry_null"})
        source = {}
        source_row = ""
    else:
        source_matches = [row for row in rows if _text(row.get("prn")) == descriptor["prn"]]
        source = source_matches[0] if source_matches else {}
        source_row = str(rows.index(source) + 2) if source else ""
        if not source:
            issues.append({"severity": "warning", "issue_code": "geometry_prn_missing", "run_id": run_id, "detail": descriptor["prn"], "action": "keep_geometry_null"})
    return (
        {
            "geometry_observation_id": f"{run_id}__geometry_summary",
            "scene_id": descriptor["scene_id"],
            "run_id": run_id,
            "prn": descriptor["prn"],
            "geometry_scope": "run_summary",
            "start_utc": source.get("start_utc"),
            "end_utc": source.get("end_utc"),
            "min_elevation_deg": source.get("min_elevation_deg"),
            "max_elevation_deg": source.get("max_elevation_deg"),
            "mean_elevation_deg": source.get("mean_elevation_deg"),
            "median_elevation_deg": source.get("median_elevation_deg"),
            "elevation_std_deg": source.get("elevation_std_deg"),
            "circular_mean_azimuth_deg": source.get("circular_mean_azimuth_deg"),
            "mean_snr_db_hz": source.get("mean_snr_db_hz"),
            "observation_count": source.get("observation_count"),
            "primary_elevation_group": source.get("primary_elevation_group"),
            "geometry_join_status": "deferred_unavailable",
            "geometry_join_valid": "0",
            "source_file": _relpath(root, path),
            "source_file_sha256": sha256_file(path) if path.is_file() else "",
            "source_row_number": source_row,
            "missing_reason": "summary_is_run_level_only; event_time_alignment_not_verified",
            "schema_version": "sage-event-path-db-v1",
        },
        issues,
    )


def _table_fields() -> dict[str, list[str]]:
    return {
        "dimensions/scenes.csv": ["scene_id", "scene_role", "signal_type", "sampling_rate_hz", "metadata_path", "geometry_summary_source_count", "scene_context_status", "schema_version"],
        "dimensions/time_alignment.csv": ["scene_id", "alignment_id", "alignment_method", "verified", "recording_time_origin_utc", "gps_week", "leap_seconds", "max_alignment_error_s", "source_files", "missing_reason", "schema_version"],
        "dimensions/geometry_observations.csv": ["geometry_observation_id", "scene_id", "run_id", "prn", "geometry_scope", "start_utc", "end_utc", "min_elevation_deg", "max_elevation_deg", "mean_elevation_deg", "median_elevation_deg", "elevation_std_deg", "circular_mean_azimuth_deg", "mean_snr_db_hz", "observation_count", "primary_elevation_group", "geometry_join_status", "geometry_join_valid", "source_file", "source_file_sha256", "source_row_number", "missing_reason", "schema_version"],
        "facts/sage_runs.csv": list(_base_run_fields()),
        "facts/candidate_events.csv": ["candidate_id", "run_id", "scene_id", "prn", "center_window_id", "recording_time_s", "selected_L", "multipath_count", "minimum_path_run", "reliable_multipath", "candidate_status", "event_id", "source_file", "source_file_sha256", "source_row_number", "modeling_eligibility", "schema_version"],
        "facts/events.csv": ["event_id", "run_id", "logical_run_key", "scene_id", "prn", "tracking_channel", "center_window_id", "recording_time_s", "stage2_L", "joint_selected_L", "joint_multipath_count", "joint_rss", "joint_bic", "snapshot_wins_vs_L1", "minimum_multipath_power_db", "maximum_relative_doppler_hz", "maximum_coherence", "joint_valid", "event_status", "label_rule_version", "source_file", "source_file_sha256", "source_row_number", "request_id", "qa_status", "modeling_eligibility", "schema_version"],
        "facts/event_paths.csv": ["event_path_id", "event_id", "run_id", "scene_id", "prn", "tracking_channel", "center_window_id", "path_id", "estimate_stage", "path_role", "is_multipath", "delay_samples", "excess_delay_samples", "excess_delay_chips", "excess_delay_s", "derived_excess_path_length_m", "doppler_hz", "doppler_offset_hz", "relative_power_db", "source_power_field", "amplitude", "phase_rad", "coherence", "label_value", "label_rule_version", "source_file", "source_file_sha256", "source_row_number", "modeling_eligibility", "missing_reason", "schema_version"],
        "facts/event_context.csv": ["event_id", "run_id", "scene_id", "prn", "center_window_id", "recording_time_s", "tow_s", "event_utc", "elevation_deg", "azimuth_deg", "tracking_cn0_db_hz", "nmea_snr_db_hz", "vehicle_speed_kmh", "speed_source", "geometry_join_status", "geometry_join_valid", "geometry_join_method", "geometry_source_utc", "geometry_time_delta_s", "time_alignment_id", "missing_reason", "observation_quality", "derivation_version"],
        "labels/run_labels.csv": ["label_id", "run_id", "scene_id", "prn", "label_scope", "label_value", "label_source", "label_rule_version", "review_status", "label_notes", "modeling_eligibility", "schema_version"],
        "labels/event_labels.csv": ["label_id", "event_id", "run_id", "label_scope", "label_value", "label_source", "label_rule_version", "review_status", "label_notes", "modeling_eligibility", "schema_version"],
        "exports/no_confirmed_events.csv": ["run_id", "scene_id", "prn", "confirmed_event_count", "run_label", "physical_los_claim", "modeling_eligibility", "exclusion_or_context_note", "schema_version"],
        "exports/modeling_eligibility.csv": ["run_id", "scene_id", "prn", "acceptance_class", "context_missing_legacy", "modeling_eligibility", "include_in_modeling_ready_input", "exclusion_reason", "schema_version"],
        "exports/run_summary.csv": ["run_id", "scene_id", "prn", "batch", "acceptance_class", "stage0_window_count", "stage2_selected_count", "stage3_reliable_centers", "stage4_rows", "confirmed_events", "confirmed_paths", "run_label", "modeling_eligibility", "schema_version"],
        "qa/ingestion_issues.csv": ["severity", "issue_code", "run_id", "scene_id", "prn", "detail", "action", "schema_version"],
    }


def _base_run_fields() -> Iterable[str]:
    return [
        "run_id", "logical_run_key", "scene_id", "scene_role", "prn", "constellation", "prn_number", "tracking_channel", "signal_type", "sampling_rate_hz", "raw_storage_mode", "raw_file_relpath", "tracking_file_relpath", "telemetry_file_relpath", "rinex_nav_relpath", "trajectory_relpath", "satellite_geometry_relpaths", "pipeline_family", "pipeline_version", "experiment_namespace", "context_version", "parameter_set_id", "code_commit", "code_sha256", "run_created_at_utc", "source_result_relpath", "source_fingerprint", "ingestion_version", "run_status", "stage0_status", "stage1_status", "stage2_status", "stage3_status", "stage4_status", "stage0_nav_symbol_count", "stage0_window_count", "stage1_scanned_count", "stage1_candidate_count", "stage2_L1_count", "stage2_L2_count", "stage2_L3_count", "stage2_L4_count", "stage2_L_ge_2_count", "stage2_L_ge_3_count", "stage3_reliable_event_count", "stage4_joint_result_count", "confirmed_event_count", "confirmed_path_count", "qa_status", "qa_issue_count", "request_id", "request_sha256", "qa_report_path", "execution_log_path", "manifest_sha256", "inventory_sha256", "acceptance_class", "batch", "context_missing_legacy", "modeling_eligibility", "schema_version"
    ]


def _append_issue(issues: list[dict[str, Any]], descriptor: dict[str, Any], severity: str, code: str, detail: str, action: str) -> None:
    issues.append({"severity": severity, "issue_code": code, "run_id": descriptor.get("run_id", ""), "scene_id": descriptor["scene_id"], "prn": descriptor["prn"], "detail": detail, "action": action, "schema_version": "sage-event-path-db-v1"})


def build_ingestion(root: Path, ingestion_id: str, run_id: str) -> dict[str, Any]:
    manifest_path = root / "dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json"
    summary_path = root / "dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv"
    request_root = root / "dataset_generation_logs/batch_sage_execution_requests"
    qa_report_path = root / "docs/10MHz_FULL_SAGE_UNATTENDED_BATCH_20260819_QA_REPORT.md"
    current_validation = validate_current_batch(root, manifest_path, summary_path, request_root, run_id=run_id, qa_report_path=qa_report_path)
    reference_validation = validate_reference_fixture(root)
    reference_validation_by_prn = {item["prn"]: item for item in reference_validation["results"]}
    if current_validation["status"] != "PASS" or reference_validation["status"] != "PASS":
        raise ValueError(f"input QA gate failed: batch={current_validation['status']} reference={reference_validation['status']}")

    descriptors = _current_descriptors(root, run_id) + _reference_descriptors(root)
    if len(descriptors) != 64:
        raise ValueError(f"unexpected ingest run count: {len(descriptors)}")

    db_root = root / "dataset/multipath_event_database/v1"
    partition_root = db_root / "partitions" / f"ingestion_id={ingestion_id}"
    manifest_out = db_root / "manifests/ingestions" / f"{ingestion_id}.json"
    if partition_root.exists() or manifest_out.exists():
        raise FileExistsError(f"ingestion target already exists: {partition_root} or {manifest_out}")
    db_root.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f".staging_{ingestion_id}_", dir=db_root))
    fields = _table_fields()
    tables = {name: [] for name in fields}
    issues: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    run_label_rows: list[dict[str, Any]] = []
    event_label_rows: list[dict[str, Any]] = []
    no_event_rows: list[dict[str, Any]] = []
    modeling_rows: list[dict[str, Any]] = []
    run_summary_rows: list[dict[str, Any]] = []
    scene_seen: dict[str, dict[str, Any]] = {}
    alignment_seen: set[str] = set()

    try:
        for descriptor in descriptors:
            run_id_value = _run_id(descriptor, ingestion_id)
            descriptor["run_id"] = run_id_value
            output_dir = descriptor["output_dir"]
            raw_tables = _read_rows(output_dir)
            validation = reference_validation_by_prn.get(descriptor["prn"]) if descriptor["scope"] == "reference_fixture" else None
            if validation is None:
                # Reuse the per-run contract validator without rebuilding a second status system.
                from validate_sage_database_dry_run import validate_output_namespace

                validation = validate_output_namespace(
                    output_dir,
                    expected_identity={"scene_id": descriptor["scene_id"], "prn": descriptor["prn"], "channel": descriptor["channel"], "sample_rate_hz": descriptor["sample_rate_hz"]},
                    scope="batch",
                )
            source_hashes = _source_hashes(output_dir)
            run_row = _base_run_row(root, descriptor, run_id_value, raw_tables, source_hashes, validation)
            run_row["schema_version"] = "sage-event-path-db-v1"
            run_rows.append(run_row)
            if descriptor["context"] is None:
                _append_issue(issues, descriptor, "warning", "legacy_context_missing", "run_context.json is absent; source run retained for audit but excluded from modeling-ready input", "exclude_from_modeling")
            if descriptor["scope"] == "reference_fixture" and descriptor["prn"] == "G06":
                _append_issue(issues, descriptor, "warning", "legacy_adapter_used", "G06 legacy namespace has no run_context.json; no timestamp or channel context was fabricated", "retain_legacy_audit_only")
            if descriptor["scene_id"] not in scene_seen:
                scene_seen[descriptor["scene_id"]] = {
                    "scene_id": descriptor["scene_id"],
                    "scene_role": descriptor["scene_role"],
                    "signal_type": "GPS_L1_CA",
                    "sampling_rate_hz": descriptor["sample_rate_hz"],
                    "metadata_path": _relpath(root, descriptor["metadata_path"]),
                    "geometry_summary_source_count": 1,
                    "scene_context_status": "not_annotated",
                    "schema_version": "sage-event-path-db-v1",
                }
            if descriptor["scene_id"] not in alignment_seen:
                alignment_seen.add(descriptor["scene_id"])
                tables["dimensions/time_alignment.csv"].append({
                    "scene_id": descriptor["scene_id"],
                    "alignment_id": f"{descriptor['scene_id']}__alignment_unavailable_v1",
                    "alignment_method": "unavailable",
                    "verified": "0",
                    "recording_time_origin_utc": None,
                    "gps_week": None,
                    "leap_seconds": None,
                    "max_alignment_error_s": None,
                    "source_files": json.dumps([_relpath(root, descriptor["metadata_path"]), _relpath(root, descriptor["geometry_summary_path"])], ensure_ascii=False),
                    "missing_reason": "recording_time_to_utc_anchor_not_frozen",
                    "schema_version": "sage-event-path-db-v1",
                })
            geometry_row, geometry_issues = _geometry_row(root, descriptor, run_id_value, source_hashes)
            tables["dimensions/geometry_observations.csv"].append(geometry_row)
            for issue in geometry_issues:
                issue["scene_id"] = descriptor["scene_id"]
                issue["prn"] = descriptor["prn"]
                issue["schema_version"] = "sage-event-path-db-v1"
                issues.append(issue)

            stage0_by_window = {_text(row.get("window_id")): row for row in raw_tables["stage0_windows"]}
            stage4_paths_by_center: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
            for source_row_number, path_row in enumerate(raw_tables["stage4_paths"], start=2):
                stage4_paths_by_center[_text(path_row.get("center_window_id"))].append((source_row_number, path_row))
            event_by_center: dict[str, dict[str, Any]] = {}
            for source_row_number, summary_row in enumerate(raw_tables["stage4_summary"], start=2):
                center = _text(summary_row.get("center_window_id"))
                event_id = f"{run_id_value}__event_{center}"
                parent_paths = [row for _, row in stage4_paths_by_center.get(center, [])]
                confirmed, rule_issues = strict_confirmation(summary_row, parent_paths)
                if rule_issues:
                    raise ValueError(f"{run_id_value}/{center}: Stage4 rule issues {rule_issues}")
                event_status = "confirmed_multipath" if confirmed else "rejected_candidate" if _is_one(summary_row.get("joint_valid")) and (_int(summary_row.get("joint_multipath_count"), 0) or 0) == 0 else "stage4_invalid"
                event_by_center[center] = {"event_id": event_id, "event_status": event_status, "confirmed": confirmed}
                event_row = {
                    "event_id": event_id,
                    "run_id": run_id_value,
                    "logical_run_key": run_row["logical_run_key"],
                    "scene_id": descriptor["scene_id"],
                    "prn": descriptor["prn"],
                    "tracking_channel": descriptor["channel"],
                    "center_window_id": center,
                    "recording_time_s": summary_row.get("recording_time_s"),
                    "stage2_L": summary_row.get("stage2_L"),
                    "joint_selected_L": summary_row.get("joint_selected_L"),
                    "joint_multipath_count": summary_row.get("joint_multipath_count"),
                    "joint_rss": summary_row.get("joint_rss"),
                    "joint_bic": summary_row.get("joint_bic"),
                    "snapshot_wins_vs_L1": summary_row.get("snapshot_wins_vs_L1"),
                    "minimum_multipath_power_db": summary_row.get("minimum_multipath_power_db"),
                    "maximum_relative_doppler_hz": summary_row.get("maximum_relative_doppler_hz"),
                    "maximum_coherence": summary_row.get("maximum_coherence"),
                    "joint_valid": summary_row.get("joint_valid"),
                    "event_status": event_status,
                    "label_rule_version": "stage4-strict-confirmed-v1",
                    "source_file": _relpath(root, output_dir / REQUIRED_FILES["stage4_summary"]),
                    "source_file_sha256": source_hashes[REQUIRED_FILES["stage4_summary"]],
                    "source_row_number": source_row_number,
                    "request_id": descriptor["request_id"],
                    "qa_status": "pass",
                    "modeling_eligibility": run_row["modeling_eligibility"],
                    "schema_version": "sage-event-path-db-v1",
                }
                tables["facts/events.csv"].append(event_row)
                event_label_rows.append({
                    "label_id": f"{event_id}__{event_status}",
                    "event_id": event_id,
                    "run_id": run_id_value,
                    "label_scope": "event",
                    "label_value": event_status,
                    "label_source": "stage4_rule",
                    "label_rule_version": "stage4-strict-confirmed-v1",
                    "review_status": "algorithm_only",
                    "label_notes": "strict Stage4 rule; zero multipath is rejected_candidate, not physical LOS",
                    "modeling_eligibility": run_row["modeling_eligibility"],
                    "schema_version": "sage-event-path-db-v1",
                })
                context_row = stage0_by_window.get(center, {})
                tables["facts/event_context.csv"].append(build_event_context_row(
                    event_id=event_id,
                    run_id=run_id_value,
                    scene_id=descriptor["scene_id"],
                    prn=descriptor["prn"],
                    center_window_id=center,
                    recording_time_s=summary_row.get("recording_time_s"),
                    tow_s=context_row.get("tow_s"),
                    cn0_db_hz=context_row.get("cn0_db_hz"),
                    vehicle_speed_kmh=context_row.get("vehicle_speed_kmh"),
                    speed_source=context_row.get("speed_source"),
                ))
            for source_row_number, path_row in enumerate(raw_tables["stage4_paths"], start=2):
                center = _text(path_row.get("center_window_id"))
                event_info = event_by_center.get(center)
                if event_info is None:
                    raise ValueError(f"{run_id_value}: orphan Stage4 path center {center}")
                is_multipath = _is_one(path_row.get("is_multipath"))
                tables["facts/event_paths.csv"].append({
                    "event_path_id": f"{event_info['event_id']}__path_{path_row.get('path_id')}",
                    "event_id": event_info["event_id"],
                    "run_id": run_id_value,
                    "scene_id": descriptor["scene_id"],
                    "prn": descriptor["prn"],
                    "tracking_channel": descriptor["channel"],
                    "center_window_id": center,
                    "path_id": path_row.get("path_id"),
                    "estimate_stage": "stage4_joint",
                    "path_role": "multipath" if is_multipath else "los",
                    "is_multipath": path_row.get("is_multipath"),
                    "delay_samples": path_row.get("delay_samples"),
                    "excess_delay_samples": path_row.get("excess_delay_samples"),
                    "excess_delay_chips": path_row.get("excess_delay_chips"),
                    "excess_delay_s": None,
                    "derived_excess_path_length_m": None,
                    "doppler_hz": path_row.get("doppler_hz"),
                    "doppler_offset_hz": path_row.get("doppler_offset_hz"),
                    "relative_power_db": path_row.get("mean_relative_power_db"),
                    "source_power_field": "mean_relative_power_db",
                    "amplitude": None,
                    "phase_rad": None,
                    "coherence": None,
                    "label_value": event_info["event_status"],
                    "label_rule_version": "stage4-strict-confirmed-v1",
                    "source_file": _relpath(root, output_dir / REQUIRED_FILES["stage4_paths"]),
                    "source_file_sha256": source_hashes[REQUIRED_FILES["stage4_paths"]],
                    "source_row_number": source_row_number,
                    "modeling_eligibility": run_row["modeling_eligibility"],
                    "missing_reason": "stage4_source_has_no_path_amplitude_phase_coherence" if not is_multipath else "",
                    "schema_version": "sage-event-path-db-v1",
                })
            for source_row_number, candidate_row in enumerate(raw_tables["stage3_centers"], start=2):
                center = _text(candidate_row.get("center_window_id"))
                event_info = event_by_center.get(center)
                candidate_status = event_info["event_status"] if event_info else "not_joint_evaluated"
                tables["facts/candidate_events.csv"].append({
                    "candidate_id": f"{run_id_value}__candidate_{center}",
                    "run_id": run_id_value,
                    "scene_id": descriptor["scene_id"],
                    "prn": descriptor["prn"],
                    "center_window_id": center,
                    "recording_time_s": candidate_row.get("recording_time_s"),
                    "selected_L": candidate_row.get("selected_L"),
                    "multipath_count": candidate_row.get("multipath_count"),
                    "minimum_path_run": candidate_row.get("minimum_path_run"),
                    "reliable_multipath": candidate_row.get("reliable_multipath"),
                    "candidate_status": candidate_status,
                    "event_id": event_info["event_id"] if event_info else None,
                    "source_file": _relpath(root, output_dir / REQUIRED_FILES["stage3_centers"]),
                    "source_file_sha256": source_hashes[REQUIRED_FILES["stage3_centers"]],
                    "source_row_number": source_row_number,
                    "modeling_eligibility": run_row["modeling_eligibility"],
                    "schema_version": "sage-event-path-db-v1",
                })
            run_label = classify_run_label(confirmed_events=run_row["confirmed_event_count"], reference_control=descriptor["reference_control"])
            label_source = "reference_manifest" if run_label == "los_reference" else "stage4_rule" if run_label == "confirmed_multipath" else "operational_state"
            run_label_rows.append({
                "label_id": f"{run_id_value}__{run_label}",
                "run_id": run_id_value,
                "scene_id": descriptor["scene_id"],
                "prn": descriptor["prn"],
                "label_scope": "run",
                "label_value": run_label,
                "label_source": label_source,
                "label_rule_version": "stage4-strict-confirmed-v1",
                "review_status": "algorithm_only",
                "label_notes": "zero confirmed event is coverage state, not physical LOS" if run_label == "no_confirmed_event" else "",
                "modeling_eligibility": run_row["modeling_eligibility"],
                "schema_version": "sage-event-path-db-v1",
            })
            if run_row["confirmed_event_count"] == 0:
                no_event_rows.append({
                    "run_id": run_id_value,
                    "scene_id": descriptor["scene_id"],
                    "prn": descriptor["prn"],
                    "confirmed_event_count": 0,
                    "run_label": run_label,
                    "physical_los_claim": "0",
                    "modeling_eligibility": run_row["modeling_eligibility"],
                    "exclusion_or_context_note": "explicit reference control" if run_label == "los_reference" else "no confirmed event under strict Stage4 rule",
                    "schema_version": "sage-event-path-db-v1",
                })
            modeling_rows.append({
                "run_id": run_id_value,
                "scene_id": descriptor["scene_id"],
                "prn": descriptor["prn"],
                "acceptance_class": descriptor["acceptance_class"],
                "context_missing_legacy": run_row["context_missing_legacy"],
                "modeling_eligibility": run_row["modeling_eligibility"],
                "include_in_modeling_ready_input": "0" if run_row["modeling_eligibility"] != "eligible_pending_modeling_qa" else "1",
                "exclusion_reason": "legacy_context_missing" if run_row["context_missing_legacy"] == "1" else "pending_modeling_readiness_qa",
                "schema_version": "sage-event-path-db-v1",
            })
            run_summary_rows.append({
                "run_id": run_id_value,
                "scene_id": descriptor["scene_id"],
                "prn": descriptor["prn"],
                "batch": descriptor["batch"],
                "acceptance_class": descriptor["acceptance_class"],
                "stage0_window_count": run_row["stage0_window_count"],
                "stage2_selected_count": run_row["stage1_candidate_count"],
                "stage3_reliable_centers": run_row["stage3_reliable_event_count"],
                "stage4_rows": run_row["stage4_joint_result_count"],
                "confirmed_events": run_row["confirmed_event_count"],
                "confirmed_paths": run_row["confirmed_path_count"],
                "run_label": run_label,
                "modeling_eligibility": run_row["modeling_eligibility"],
                "schema_version": "sage-event-path-db-v1",
            })

        tables["dimensions/scenes.csv"] = list(scene_seen.values())
        tables["facts/sage_runs.csv"] = run_rows
        tables["labels/run_labels.csv"] = run_label_rows
        tables["labels/event_labels.csv"] = event_label_rows
        tables["exports/no_confirmed_events.csv"] = no_event_rows
        tables["exports/modeling_eligibility.csv"] = modeling_rows
        tables["exports/run_summary.csv"] = run_summary_rows
        tables["qa/ingestion_issues.csv"] = issues
        for table_name, table_rows in tables.items():
            _write_csv(staging_root / table_name, table_rows, fields[table_name])

        final_parent = partition_root.parent
        final_parent.mkdir(parents=True, exist_ok=True)
        staging_root.rename(partition_root)
        table_hashes = {}
        table_counts = {}
        for table_name in fields:
            final_path = partition_root / table_name
            table_hashes[table_name] = sha256_file(final_path)
            table_counts[table_name] = len(tables[table_name])
        ingestion_manifest = {
            "ingestion_id": ingestion_id,
            "ingestion_version": INGESTION_VERSION,
            "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "status": "completed_with_warnings" if issues else "completed",
            "partition_path": _relpath(root, partition_root),
            "source_scope": {"current_batch_run_id": run_id, "current_batch_tasks": 57, "reference_fixture_runs": 7},
            "run_count": len(run_rows),
            "event_count": len(tables["facts/events.csv"]),
            "event_path_count": len(tables["facts/event_paths.csv"]),
            "confirmed_event_count": sum(1 for row in tables["facts/events.csv"] if row["event_status"] == "confirmed_multipath"),
            "confirmed_path_count": sum(1 for row in tables["facts/event_paths.csv"] if row["label_value"] == "confirmed_multipath" and row["is_multipath"] == "1"),
            "modeling_excluded_runs": [row["run_id"] for row in modeling_rows if row["include_in_modeling_ready_input"] == "0"],
            "table_counts": table_counts,
            "table_sha256": table_hashes,
            "frozen_source_hashes": FROZEN_SOURCE_HASHES,
            "rules": {"schema_version": "sage-event-path-db-v1", "label_rule_version": "stage4-strict-confirmed-v1", "derivation_version": "sage-event-path-derivation-v1"},
            "gate_record": {"raw_iq_read": False, "matlab_started": False, "sage_started": False, "batch_started": False, "existing_sage_artifacts_modified": False, "geometry_event_time_join": False, "channel_parameter_derivation_started": False, "statistical_modeling_started": False},
        }
        _write_json(manifest_out, ingestion_manifest)
        report_dir = root / "dataset_generation_logs/multipath_event_database_ingest_20260825"
        report_path = report_dir / "ingestion_report.md"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_lines = [
            "# SAGE Event/Path Database Ingestion Report",
            "",
            f"- Ingestion: `{ingestion_id}`",
            f"- Status: **{ingestion_manifest['status']}**",
            f"- Partition: `{_relpath(root, partition_root)}`",
            f"- Runs: `{len(run_rows)}`; events: `{len(tables['facts/events.csv'])}`; paths: `{len(tables['facts/event_paths.csv'])}`",
            f"- Strict confirmed events/paths: `{ingestion_manifest['confirmed_event_count']}/{ingestion_manifest['confirmed_path_count']}`",
            f"- Modeling-excluded runs: `{len(ingestion_manifest['modeling_excluded_runs'])}` (legacy G06 missing run_context)",
            "",
            "## G06 handling",
            "",
            "The legacy G06 source and event/path audit rows are retained. Because `run_context.json` is absent, G06 is marked `excluded_legacy_context_missing` and `include_in_modeling_ready_input=0`. No source artifact was deleted or modified; no timestamp/channel context was fabricated.",
            "",
            "## Geometry and modeling boundary",
            "",
            "Run-level geometry summaries are retained as `geometry_scope=run_summary`. Event-time UTC/elevation/azimuth remain null with `geometry_join_status=deferred_unavailable` until time alignment QA. No channel parameters or statistical models were computed.",
            "",
            "## Execution record",
            "",
            "- Raw IQ read: no",
            "- MATLAB/SAGE/batch started: no",
            "- Existing SAGE artifacts/manifest/requests/metadata/inventory modified: no",
            "- Formal database tables written: yes, only in the new versioned partition above",
            "",
        ]
        report_path.write_text("\n".join(report_lines), encoding="utf-8")
        return {"manifest": ingestion_manifest, "manifest_path": str(manifest_out), "report_path": str(report_path), "partition_path": str(partition_root), "issues": issues}
    except Exception:
        if staging_root.exists():
            # Keep failed staging for forensic review; never touch an existing partition.
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--run-id", default="20260819T004818Z")
    parser.add_argument("--ingestion-id", default=DEFAULT_INGESTION_ID)
    args = parser.parse_args(argv)
    result = build_ingestion(args.root.resolve(), args.ingestion_id, args.run_id)
    print(
        f"INGEST_RESULT={result['manifest']['status']}|runs={result['manifest']['run_count']}|"
        f"events={result['manifest']['event_count']}|paths={result['manifest']['event_path_count']}|"
        f"confirmed={result['manifest']['confirmed_event_count']}/{result['manifest']['confirmed_path_count']}|"
        f"modeling_excluded={len(result['manifest']['modeling_excluded_runs'])}"
    )
    print(f"INGEST_PARTITION={result['partition_path']}")
    print(f"INGEST_MANIFEST={result['manifest_path']}")
    print(f"INGEST_REPORT={result['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
