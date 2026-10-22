#!/usr/bin/env python3
"""Freeze the audited 83-run 10.23 MHz CIR/model cohort without editing authorities.

The command is deliberately fail-closed: it binds the Gate A report to the
current Manifest/Summary bytes, validates the exact 83+6 identity partition,
and only publishes into a new UTC-versioned directory. It reads text CSV/JSON
and file metadata. It never opens raw IQ, MAT, or HDF5 payloads.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


PILOT_RUN_ID = "run_20261003_F1023_V70_D0117_P2_G28_ch1"
EXPECTED_COUNTS = {
    "ALREADY_COMPLETE": 1,
    "COMPLETE": 82,
    "PENDING": 4,
    "FAILED": 2,
    "IN_PROGRESS": 0,
}
ELIGIBLE_STATUSES = {"ALREADY_COMPLETE", "COMPLETE"}
EXPECTED_EXCLUDED_RUN_IDS = {
    "run_20261003_F1023_V120_D0121_P2_G06_ch6",
    "run_20261003_F1023_V120_D0121_P2_G12_ch5",
    "run_20261003_F1023_V70_D0120_P9_G23_ch10",
    "run_20261003_F1023_V80_D0117_P8_G29_ch9",
    "run_20261003_F1023_V70_D0120_P1_G26_ch3",
    "run_20261003_F1023_V70_D0120_P1_G27_ch8",
}
IDENTITY_FIELDS = (
    "run_id",
    "scene_id",
    "prn",
    "tracking_channel",
    "mapping_warning",
)
GATE_A_ELIGIBLE_IDENTITY_FIELDS = (
    "run_id",
    "scene_id",
    "prn",
    "tracking_channel",
)
STAGE_FILES = {
    "stage0_valid_windows": "stage0_valid_40ms_windows.csv",
    "stage1_scan": "stage1_nav_fast_scan.csv",
    "stage2_selected_paths": "stage2_selected_paths.csv",
    "stage3_persistence": "stage3_persistence.csv",
    "stage4_joint_paths": "stage4_joint_paths.csv",
}
TASK_AUDIT_NUMERIC_FIELDS = (
    "stage0_valid_40ms_windows",
    "stage1_scanned_windows",
    "stage2_evaluated_windows",
    "stage2_selected_path_count",
    "direct_path_count",
    "stage2_mpc_count",
    "stage3_persistent_mpc_count",
    "stage4_confirmed_mpc_count",
)


class CohortError(ValueError):
    """Raised when authoritative inputs or evidence fail a release check."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CohortError(f"Cannot read JSON evidence {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CohortError(f"JSON evidence must be an object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise CohortError(f"CSV has no header: {path}")
            rows = [dict(row) for row in reader]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CohortError(f"Cannot read CSV {path}: {exc}") from exc
    if any(None in row for row in rows):
        raise CohortError(f"CSV row has more cells than its header: {path}")
    return rows


def _required_fields(rows: list[dict[str, str]], fields: tuple[str, ...], label: str) -> None:
    if not rows:
        raise CohortError(f"{label} is empty")
    missing = sorted(set(fields) - set(rows[0]))
    if missing:
        raise CohortError(f"{label} is missing required columns: {', '.join(missing)}")


def _unique_by_run_id(rows: list[dict[str, str]], label: str) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        run_id = (row.get("run_id") or "").strip()
        if not run_id:
            raise CohortError(f"{label} contains a blank run_id")
        if run_id in indexed:
            raise CohortError(f"{label} contains duplicate run_id {run_id}")
        indexed[run_id] = row
    return indexed


def _safe_relative_path(value: str, label: str) -> str:
    normalized = value.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in normalized:
        raise CohortError(f"Unsafe or non-relative {label}: {value!r}")
    return path.as_posix()


def _project_path(project_root: Path, relative: str) -> Path:
    path = (project_root / Path(*PurePosixPath(relative).parts)).resolve()
    root = project_root.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise CohortError(f"Artifact path escapes project root: {relative}") from exc
    return path


def _portable_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _file_metadata(path: Path, project_root: Path, *, include_sha256: bool) -> dict[str, Any]:
    if not path.is_file():
        raise CohortError(f"Required audited artifact is missing: {_portable_path(path, project_root)}")
    stat = path.stat()
    metadata: dict[str, Any] = {
        "path": _portable_path(path, project_root),
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if include_sha256:
        metadata["sha256"] = sha256_file(path)
    return metadata


def _parse_optional_number(value: str | None, *, integer: bool = False) -> int | float | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise CohortError(f"Expected numeric audit value, got {value!r}") from exc
    if not math.isfinite(parsed):
        raise CohortError(f"Non-finite audit value is not publishable: {value!r}")
    if integer:
        if not parsed.is_integer():
            raise CohortError(f"Expected integer audit value, got {value!r}")
        return int(parsed)
    return parsed


def _validate_pilot(
    pilot_row: dict[str, str],
    output_path: Path,
    project_root: Path,
    audit: dict[str, Any],
) -> dict[str, Any]:
    pilot = audit.get("known_existing_pilot_cir", {})
    if pilot.get("run_id") != PILOT_RUN_ID or pilot.get("counted_as_reexport") is not False:
        raise CohortError("Gate A does not identify the expected existing pilot exactly once")
    if pilot.get("output_present_in_inventory") is not True:
        raise CohortError("Gate A does not confirm the existing pilot output inventory")

    channel = pilot_row["tracking_channel"].strip()
    prefix = f"{pilot_row['prn']}_ch{channel}"
    h5_path = output_path / f"{prefix}_code_domain_cir.h5"
    metadata_path = output_path / f"{prefix}_code_domain_cir_metadata.json"
    metadata_record = _read_json(metadata_path)
    if not h5_path.is_file():
        raise CohortError("Existing pilot HDF5 artifact is missing")
    for field, expected in (
        ("run_id", PILOT_RUN_ID),
        ("scene_id", pilot_row["scene_id"]),
        ("prn", pilot_row["prn"]),
        ("tracking_channel", int(channel)),
    ):
        if metadata_record.get(field) != expected:
            raise CohortError(f"Existing pilot metadata identity mismatch in {field}")
    if metadata_record.get("raw_iq_sha256") not in ("NOT_RECOMPUTED", None, ""):
        raise CohortError("Pilot metadata indicates a raw-IQ hash was recorded; do not infer fresh raw-IQ validation")
    validation = metadata_record.get("validation", {})
    required_true = (
        "cir_all_finite",
        "raw_iq_rms_all_positive",
        "time_monotonic_nondecreasing",
        "delay_grid_fixed",
        "pdp_stage0_window_one_to_one",
        "pdp_40ms_arithmetic_mean_of_40_powers",
    )
    if not all(validation.get(key) is True for key in required_true):
        raise CohortError("Existing pilot read-back validation metadata is incomplete or not PASS")
    if metadata_record.get("stage0_window_count") != 898 or metadata_record.get("delay_grid_count") != 451:
        raise CohortError("Existing pilot shape metadata differs from the audited 898 × 451 pilot")

    baseline_audit = project_root / "reports" / "data_consolidation_20261003" / "BASELINE_CIR_EXPORT_AUDIT.md"
    try:
        audit_text = baseline_audit.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise CohortError(f"Cannot read existing pilot baseline audit: {exc}") from exc
    if "F1023_V70_D0117_P2 / G28 / ch1" not in audit_text or "Read-back validation reported" not in audit_text:
        raise CohortError("Existing pilot baseline audit report does not substantiate read-back validation")
    return {
        "status": "EXISTING_VALIDATED",
        "metadata": _file_metadata(metadata_path, project_root, include_sha256=True),
        "hdf5_metadata_only": _file_metadata(h5_path, project_root, include_sha256=False),
        "baseline_audit": _file_metadata(baseline_audit, project_root, include_sha256=True),
        "read_back_validation": {key: validation[key] for key in required_true},
        "cir_snapshot_count": metadata_record.get("cir_snapshot_count"),
        "stage0_window_count": metadata_record.get("stage0_window_count"),
        "delay_grid_count": metadata_record.get("delay_grid_count"),
        "raw_iq_sha256": "NOT_RECOMPUTED",
        "hdf5_payload_opened": False,
    }


def build_release(
    *,
    manifest_path: Path,
    summary_path: Path,
    audit_path: Path,
    eligible_path: Path,
    project_root: Path,
    task_audit_path: Path | None = None,
    audit_md_path: Path | None = None,
) -> dict[str, Any]:
    """Validate current authorities against Gate A and prepare immutable JSON."""
    manifest_path = Path(manifest_path)
    summary_path = Path(summary_path)
    audit_path = Path(audit_path)
    eligible_path = Path(eligible_path)
    project_root = Path(project_root)
    task_audit_path = Path(task_audit_path or audit_path.parent / "task_audit.csv")
    audit_md_path = Path(audit_md_path or audit_path.parent / "audit.md")

    for path in (manifest_path, summary_path, audit_path, eligible_path, task_audit_path, audit_md_path):
        if not path.is_file():
            raise CohortError(f"Required freeze input is missing: {path}")

    manifest = _read_csv(manifest_path)
    summary = _read_csv(summary_path)
    eligible = _read_csv(eligible_path)
    task_audit = _read_csv(task_audit_path)
    audit = _read_json(audit_path)
    _required_fields(manifest, IDENTITY_FIELDS, "Manifest")
    _required_fields(summary, IDENTITY_FIELDS + ("execution_status", "output_namespace", "frozen_sage_sha256"), "Summary")
    _required_fields(eligible, GATE_A_ELIGIBLE_IDENTITY_FIELDS + ("execution_status", "audit_status", "output_namespace", "cohort_eligible"), "Gate A eligible_runs.csv")
    _required_fields(task_audit, ("run_id", "audit_status", "environment_class", "elevation_group", *TASK_AUDIT_NUMERIC_FIELDS), "Gate A task_audit.csv")

    manifest_by_id = _unique_by_run_id(manifest, "Manifest")
    summary_by_id = _unique_by_run_id(summary, "Summary")
    eligible_by_id = _unique_by_run_id(eligible, "Gate A eligible list")
    task_audit_by_id = _unique_by_run_id(task_audit, "Gate A task audit")
    if len(manifest) != 89 or len(summary) != 89:
        raise CohortError(f"Expected 89 Manifest/Summary rows, got {len(manifest)}/{len(summary)}")
    if set(manifest_by_id) != set(summary_by_id):
        raise CohortError("Manifest and Summary run_id sets differ")

    for run_id, manifest_row in manifest_by_id.items():
        summary_row = summary_by_id[run_id]
        for field in IDENTITY_FIELDS:
            if (manifest_row.get(field) or "").strip() != (summary_row.get(field) or "").strip():
                raise CohortError(f"Manifest/Summary identity mismatch: {run_id} field {field}")

    status_counts = Counter((row.get("execution_status") or "").strip() for row in summary)
    normalized_counts = {key: status_counts.get(key, 0) for key in EXPECTED_COUNTS}
    if normalized_counts != EXPECTED_COUNTS:
        raise CohortError(f"Summary status counts changed from Gate A: {normalized_counts}")

    source_sha = {
        "manifest": sha256_file(manifest_path),
        "summary": sha256_file(summary_path),
        "audit_json": sha256_file(audit_path),
        "audit_markdown": sha256_file(audit_md_path),
        "eligible_runs_csv": sha256_file(eligible_path),
        "task_audit_csv": sha256_file(task_audit_path),
    }
    if audit.get("audit_status") != "PASS":
        raise CohortError("Gate A audit_status is not PASS")
    if audit.get("manifest", {}).get("sha256", "").lower() != source_sha["manifest"]:
        raise CohortError("Current Manifest SHA-256 is stale relative to Gate A")
    if audit.get("summary", {}).get("sha256", "").lower() != source_sha["summary"]:
        raise CohortError("Current Summary SHA-256 is stale relative to Gate A")
    if audit.get("eligible_count") != 83 or audit.get("excluded_count") != 6:
        raise CohortError("Gate A counts do not identify the approved 83+6 population")
    if len(eligible_by_id) != 83 or set(eligible_by_id) != {
        run_id for run_id, row in summary_by_id.items() if row["execution_status"] in ELIGIBLE_STATUSES
    }:
        raise CohortError("Gate A eligible identity set differs from current COMPLETE/ALREADY_COMPLETE rows")
    if len(task_audit_by_id) != 83 or set(task_audit_by_id) != set(eligible_by_id):
        raise CohortError("Gate A task audit does not cover the exact 83 eligible identities")
    if set(summary_by_id) - set(eligible_by_id) != EXPECTED_EXCLUDED_RUN_IDS:
        raise CohortError("The six excluded identities differ from the user-approved fixed set")
    if eligible_by_id.get(PILOT_RUN_ID, {}).get("execution_status") != "ALREADY_COMPLETE":
        raise CohortError("The existing CIR pilot must occur exactly once as ALREADY_COMPLETE")

    for run_id, eligible_row in eligible_by_id.items():
        summary_row = summary_by_id[run_id]
        audit_row = task_audit_by_id[run_id]
        if eligible_row.get("audit_status") != "PASS" or eligible_row.get("cohort_eligible", "").strip().lower() != "true":
            raise CohortError(f"Gate A row is not PASS/eligible: {run_id}")
        if audit_row.get("audit_status") != "PASS":
            raise CohortError(f"Gate A per-task audit is not PASS: {run_id}")
        for field in ("scene_id", "prn", "tracking_channel", "execution_status", "output_namespace"):
            if (eligible_row.get(field) or "").strip() != (summary_row.get(field) or "").strip():
                raise CohortError(f"Gate A/summary mismatch: {run_id} field {field}")
        if (summary_row.get("frozen_sage_sha256") or "").strip() == "":
            raise CohortError(f"Missing frozen SAGE source SHA in Summary: {run_id}")
        if not _safe_relative_path(summary_row["output_namespace"], f"output_namespace for {run_id}"):
            raise CohortError(f"Invalid output namespace: {run_id}")
        for field in TASK_AUDIT_NUMERIC_FIELDS:
            _parse_optional_number(audit_row.get(field), integer=True)

    items: list[dict[str, Any]] = []
    seen_output_namespaces: set[str] = set()
    pilot_validation: dict[str, Any] | None = None
    for run_id in sorted(eligible_by_id):
        summary_row = summary_by_id[run_id]
        eligible_row = eligible_by_id[run_id]
        audit_row = task_audit_by_id[run_id]
        namespace = _safe_relative_path(summary_row["output_namespace"], f"output_namespace for {run_id}")
        if namespace in seen_output_namespaces:
            raise CohortError(f"Two cohort rows share output namespace {namespace}")
        seen_output_namespaces.add(namespace)
        output_path = _project_path(project_root, namespace)
        stage_csvs = {
            key: _file_metadata(output_path / filename, project_root, include_sha256=True)
            for key, filename in STAGE_FILES.items()
        }
        relocation = _file_metadata(output_path / "relocation_receipt.json", project_root, include_sha256=True)
        relocation_record = _read_json(output_path / "relocation_receipt.json")
        if relocation_record.get("relocation_status") != "VERIFIED_SAME_VOLUME_MOVE":
            raise CohortError(f"Relocation receipt is not verified: {run_id}")
        if relocation_record.get("scene_id") != summary_row["scene_id"]:
            raise CohortError(f"Relocation receipt scene identity mismatch: {run_id}")
        try:
            receipt_prn = int(str(relocation_record.get("prn", "")).removeprefix("G"))
            summary_prn = int(summary_row["prn"].removeprefix("G"))
            receipt_channel = int(relocation_record.get("tracking_channel"))
            summary_channel = int(summary_row["tracking_channel"])
        except (TypeError, ValueError) as exc:
            raise CohortError(f"Relocation receipt PRN/channel is not numeric: {run_id}") from exc
        if receipt_prn != summary_prn or receipt_channel != summary_channel:
            raise CohortError(f"Relocation receipt PRN/channel mismatch: {run_id}")
        if relocation_record.get("frozen_sage_sha256") != summary_row["frozen_sage_sha256"]:
            raise CohortError(f"Relocation receipt frozen source SHA mismatch: {run_id}")

        stage_counts = {
            field: _parse_optional_number(audit_row.get(field), integer=True)
            for field in TASK_AUDIT_NUMERIC_FIELDS
        }
        item = {
            "run_id": run_id,
            "scene_id": summary_row["scene_id"],
            "prn": summary_row["prn"],
            "tracking_channel": int(summary_row["tracking_channel"]),
            "output_namespace": namespace,
            "source_summary_status": summary_row["execution_status"],
            "mapping_warning": summary_row["mapping_warning"],
            "environment_class": eligible_row.get("environment_class"),
            "elevation_group": eligible_row.get("elevation_group"),
            "mean_elevation_deg": _parse_optional_number(eligible_row.get("mean_elevation_deg")),
            "source_frozen_sage_sha256": summary_row["frozen_sage_sha256"],
            "stage_counts_from_gate_a": stage_counts,
            "stage_csvs": stage_csvs,
            "relocation_receipt": relocation,
        }
        if run_id == PILOT_RUN_ID:
            pilot_validation = _validate_pilot(summary_row, output_path, project_root, audit)
            item["existing_cir_pilot"] = pilot_validation
        items.append(item)

    if len(items) != 83 or sum(item["run_id"] == PILOT_RUN_ID for item in items) != 1:
        raise CohortError("Cohort must contain exactly 83 identities and one pilot")

    excluded = []
    for run_id in sorted(EXPECTED_EXCLUDED_RUN_IDS):
        row = summary_by_id[run_id]
        excluded.append({
            "run_id": run_id,
            "scene_id": row["scene_id"],
            "prn": row["prn"],
            "tracking_channel": int(row["tracking_channel"]),
            "source_summary_status": row["execution_status"],
            "mapping_warning": row["mapping_warning"],
        })

    code_path = Path(__file__).resolve()
    test_path = code_path.parent / "tests" / "test_freeze_mainline_1023_cohort.py"
    if not test_path.is_file():
        raise CohortError("Targeted freeze regression test file is missing")
    sources = {
        "manifest": {"path": _portable_path(manifest_path, project_root), "sha256": source_sha["manifest"]},
        "summary": {"path": _portable_path(summary_path, project_root), "sha256": source_sha["summary"]},
        "gate_a_audit_json": {"path": _portable_path(audit_path, project_root), "sha256": source_sha["audit_json"]},
        "gate_a_audit_markdown": {"path": _portable_path(audit_md_path, project_root), "sha256": source_sha["audit_markdown"]},
        "gate_a_eligible_runs": {"path": _portable_path(eligible_path, project_root), "sha256": source_sha["eligible_runs_csv"]},
        "gate_a_task_audit": {"path": _portable_path(task_audit_path, project_root), "sha256": source_sha["task_audit_csv"]},
        "cohort_generator": {"path": "scripts/channel_modeling/freeze_mainline_1023_cohort.py", "sha256": sha256_file(code_path)},
        "targeted_test": {"path": "scripts/channel_modeling/tests/test_freeze_mainline_1023_cohort.py", "sha256": sha256_file(test_path)},
    }
    cohort = {
        "schema_version": 1,
        "cohort_id": "mainline_1023_model_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "eligible_count": 83,
        "excluded_count": 6,
        "population_policy": "ALREADY_COMPLETE|COMPLETE rows in current Gate-A-audited 10.23 MHz Mainline; exact approved six identities remain outside CIR/model cohort without exclusion reasons; no new SAGE rerun.",
        "status_counts_at_freeze": normalized_counts,
        "source_sha256": sources,
        "tasks": items,
        "excluded": excluded,
    }
    cohort_sha = hashlib.sha256(_json_bytes(cohort)).hexdigest()
    cir_tasks = {
        "schema_version": 1,
        "cohort_id": cohort["cohort_id"],
        "source_cohort_sha256": cohort_sha,
        "task_count": 83,
        "tasks": [
            {
                "run_id": item["run_id"],
                "scene_id": item["scene_id"],
                "prn": item["prn"],
                "tracking_channel": item["tracking_channel"],
                "output_namespace": item["output_namespace"],
                "task_status": "EXISTING_VALIDATED" if item["run_id"] == PILOT_RUN_ID else "NEW_REQUIRED",
            }
            for item in items
        ],
    }
    cir_sha = hashlib.sha256(_json_bytes(cir_tasks)).hexdigest()
    validation = {
        "validation_status": "PASS",
        "gate_b_pass": True,
        "validated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest_summary_identity_match_count": 89,
        "status_counts": normalized_counts,
        "eligible_count": 83,
        "excluded_count": 6,
        "unique_run_ids": True,
        "unique_output_namespaces": True,
        "eligible_identity_set_matches_gate_a": True,
        "six_excluded_identity_set_matches_approved_set": True,
        "existing_pilot_occurrences": 1,
        "new_cir_required_count": 82,
        "pilot_run_id": PILOT_RUN_ID,
        "pilot_status": "EXISTING_VALIDATED",
        "raw_iq_content_read": False,
        "raw_iq_hash_recomputed": False,
        "mat_payload_opened": False,
        "hdf5_payload_opened": False,
        "cohort_json_sha256": cohort_sha,
        "cir_tasks_json_sha256": cir_sha,
        "gate_a_audit_sha256": source_sha["audit_json"],
    }
    return {"cohort": cohort, "cir_tasks": cir_tasks, "validation": validation}


def publish_release(release: dict[str, Any], output_root: Path, *, timestamp: str | None = None) -> Path:
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not timestamp.endswith("Z") or any(ch not in "0123456789TZ" for ch in timestamp):
        raise CohortError("Timestamp must be a compact UTC value ending in Z")
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    version_dir = output_root / f"mainline_1023_cohort_v1_{timestamp}"
    version_dir.mkdir(exist_ok=False)
    cohort_bytes = _json_bytes(release["cohort"])
    cir_bytes = _json_bytes(release["cir_tasks"])
    validation = dict(release["validation"])
    validation["cohort_json_sha256"] = hashlib.sha256(cohort_bytes).hexdigest()
    validation["cir_tasks_json_sha256"] = hashlib.sha256(cir_bytes).hexdigest()
    for filename, payload in (
        ("cohort.json", cohort_bytes),
        ("cir_tasks.json", cir_bytes),
        ("cohort_validation.json", _json_bytes(validation)),
    ):
        with (version_dir / filename).open("xb") as stream:
            stream.write(payload)
    return version_dir


def _default_paths(project_root: Path) -> dict[str, Path]:
    report_dir = project_root / "reports" / "data_consolidation_20261003" / "mainline_1023_model_v1" / "audit_20261022T074307Z"
    authority_dir = project_root / "reports" / "data_consolidation_20261003"
    return {
        "manifest": authority_dir / "MAINLINE_SAGE_1023_RERUN_MANIFEST.csv",
        "summary": authority_dir / "MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv",
        "audit": report_dir / "audit.json",
        "eligible": report_dir / "eligible_runs.csv",
        "task_audit": report_dir / "task_audit.csv",
        "audit_md": report_dir / "audit.md",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true", help="validate current sources without publishing")
    mode.add_argument("--publish", action="store_true", help="validate and publish a new immutable UTC cohort directory")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--audit-md", type=Path)
    parser.add_argument("--eligible-runs", type=Path)
    parser.add_argument("--task-audit", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    defaults = _default_paths(project_root)
    try:
        release = build_release(
            manifest_path=args.manifest or defaults["manifest"],
            summary_path=args.summary or defaults["summary"],
            audit_path=args.audit_json or defaults["audit"],
            audit_md_path=args.audit_md or defaults["audit_md"],
            eligible_path=args.eligible_runs or defaults["eligible"],
            task_audit_path=args.task_audit or defaults["task_audit"],
            project_root=project_root,
        )
        if args.validate_only:
            print(json.dumps(release["validation"], ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        output_root = args.output_root or project_root / "dataset_generation_logs" / "channel_modeling"
        version_dir = publish_release(release, output_root)
        print(json.dumps({
            "published_directory": _portable_path(version_dir, project_root),
            "cohort_json_sha256": release["validation"]["cohort_json_sha256"],
            "cir_tasks_json_sha256": release["validation"]["cir_tasks_json_sha256"],
            "validation_status": "PASS",
            "gate_b_pass": True,
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (CohortError, OSError) as exc:
        print(f"COHORT_FREEZE_FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
