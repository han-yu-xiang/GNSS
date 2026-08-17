"""Safe, allowlist-based batch executor for the existing NAV-SAGE pipeline.

The executor is intentionally conservative:

* a plan file and an explicit selected_tasks.csv are required;
* the default mode is dry-run and never invokes MATLAB;
* only tasks whose plan status is ``ready`` can execute;
* existing nav_sage_v2 output directories are always skipped;
* the reference G06_nav_sage_v1 result is permanently protected;
* input paths, the pipeline hash, and the target directory are rechecked just
  before launch;
* each task is isolated, logged, and allowed to fail without stopping later
  selected tasks.

No SAGE algorithm is implemented here.  MATLAB is invoked only when the
caller explicitly supplies ``--execute``.  The current project workflow uses
this module with an immutable batch plan and a small, human-approved task
allowlist.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_PLAN = Path(
    r"dataset_generation_logs\batch_sage\batch_sage_dry_run_20260808T113454Z\batch_sage_plan.csv"
)
PIPELINE_RELATIVE = Path("scripts") / "sage_pipeline" / "run_nav_sage_pipeline.m"
EXECUTION_NAMESPACE = "batch_sage_execution"
EXPERIMENT_NAMESPACE = "nav_sage_v2"
PROTECTED_REFERENCE_SCENE = "F1023_V70_D0117_P2"
PROTECTED_REFERENCE_PRN = "G06"
EXECUTION_REQUEST_SCHEMA = "windows_execution_request_v1"
SUPPORTED_SAMPLE_RATE_HZ = 10_230_000
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")

REQUIRED_PLAN_COLUMNS = {
    "task_id",
    "scene_id",
    "scene_role",
    "prn",
    "tracking_channel",
    "output_path",
    "status",
    "execution_allowed",
    "requires_manual_channel_selection",
    "pipeline_sha256",
    "hard_gate_failures",
    "raw_path",
    "tracking_path",
    "telemetry_path",
    "navigation_path",
    "trajectory_path",
    "satellite_timeseries_path",
    "satellite_summary_path",
    "metadata_path",
    "sample_rate_hz",
}

REQUIRED_OUTPUT_FILES = (
    "run_context.json",
    "stage0_valid_symbols.csv",
    "stage0_valid_40ms_windows.csv",
    "stage1_nav_fast_scan.csv",
    "stage2_model_orders.csv",
    "stage2_selected_windows.csv",
    "stage2_selected_paths.csv",
    "stage3_persistence.csv",
    "stage3_reliable_centers.csv",
    "stage4_joint_summary.csv",
    "stage4_joint_paths.csv",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_time(value: Optional[datetime] = None) -> str:
    return (value or utc_now()).isoformat()


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def as_int(value: Any) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_path(path: Path) -> str:
    """Return a Windows-safe canonical path for equality and containment checks."""

    return os.path.normcase(os.path.abspath(os.fspath(path)))


def paths_equal(left: Path, right: Path) -> bool:
    return normalized_path(left) == normalized_path(right)


def is_path_inside(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([normalized_path(path), normalized_path(root)]) == normalized_path(root)
    except ValueError:
        return False


def resolve_request_path(value: Any, project_root: Path, label: str) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"Execution request is missing {label}.")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve()
    if not is_path_inside(resolved, project_root):
        raise ValueError(f"Execution request {label} escapes project root: {resolved}")
    return resolved


def strict_request_bool(request: Dict[str, Any], field: str) -> Optional[bool]:
    value = request.get(field)
    if type(value) is not bool:  # bool must not be accepted as an integer or string.
        return None
    return value


def validate_execution_request_policy(request: Dict[str, Any]) -> List[str]:
    """Validate policy fields which must reach the MATLAB command unchanged."""

    errors: List[str] = []
    if request.get("schema_version") != EXECUTION_REQUEST_SCHEMA:
        errors.append("unsupported_execution_request_schema")
    if request.get("experiment_namespace") != EXPERIMENT_NAMESPACE:
        errors.append("request_experiment_namespace_mismatch")
    if request.get("execution_mode") != "new_only":
        errors.append("request_execution_mode_must_be_new_only")
    if strict_request_bool(request, "new_only") is not True:
        errors.append("request_new_only_must_be_true")
    if strict_request_bool(request, "resume_allowed") is not False:
        errors.append("request_resume_allowed_must_be_false")
    if type(request.get("max_parallel_matlab")) is not int or request.get("max_parallel_matlab") != 1:
        errors.append("request_max_parallel_matlab_must_be_one")
    if request.get("allowed_sample_rates_hz") != [SUPPORTED_SAMPLE_RATE_HZ]:
        errors.append("request_allowed_sample_rates_must_be_10230000_only")
    return sorted(set(errors))


def load_execution_request(
    manifest_path: Path,
    expected_sha256: str,
    project_root: Path,
    plan_path: Path,
    selected_path: Path,
    pipeline_path: Path,
) -> Dict[str, Any]:
    """Read and revalidate the immutable request before any task is launched."""

    manifest_path = manifest_path.resolve()
    if not is_path_inside(manifest_path, project_root):
        raise ValueError(f"Execution request manifest escapes project root: {manifest_path}")
    expected = str(expected_sha256 or "").strip().lower()
    if not SHA256_PATTERN.fullmatch(expected):
        raise ValueError("Expected request SHA-256 must be exactly 64 hexadecimal characters.")
    actual = sha256_file(manifest_path)
    if actual is None:
        raise FileNotFoundError(f"Execution request manifest does not exist: {manifest_path}")
    if actual.lower() != expected:
        raise ValueError(f"Execution request SHA-256 mismatch: expected {expected}; actual {actual}.")

    try:
        request = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Execution request is not readable JSON: {manifest_path}") from exc
    if not isinstance(request, dict):
        raise ValueError("Execution request root must be a JSON object.")

    policy_errors = validate_execution_request_policy(request)
    if policy_errors:
        raise ValueError("Execution request policy rejected: " + ";".join(policy_errors))

    request_root = resolve_request_path(request.get("project_root"), project_root, "project_root")
    if not paths_equal(request_root, project_root):
        raise ValueError(f"Execution request project_root mismatch: {request_root} != {project_root}")

    wrapper_path = project_root / "scripts" / "sage_pipeline" / "Invoke-BatchSageWindows.ps1"
    artifact_specs = (
        ("plan_path", plan_path, "plan_sha256", "plan"),
        ("selected_tasks_snapshot_path", selected_path, "selected_tasks_sha256", "selected-task snapshot"),
        ("pipeline_path", pipeline_path, "pipeline_sha256", "pipeline"),
        ("python_executor_path", Path(__file__).resolve(), "python_executor_sha256", "Python executor"),
        ("wrapper_path", wrapper_path, "wrapper_sha256", "Windows wrapper"),
    )
    for path_field, actual_path, hash_field, label in artifact_specs:
        requested_path = resolve_request_path(request.get(path_field), project_root, label)
        if not paths_equal(requested_path, actual_path):
            raise ValueError(f"Execution request {label} path mismatch: {requested_path} != {actual_path}")
        expected_hash = str(request.get(hash_field) or "").strip().lower()
        if not SHA256_PATTERN.fullmatch(expected_hash):
            raise ValueError(f"Execution request has invalid {hash_field}.")
        actual_hash = sha256_file(actual_path)
        if actual_hash is None or actual_hash.lower() != expected_hash:
            raise ValueError(f"{label} SHA-256 mismatch: expected {expected_hash}; actual {actual_hash}")

    for path_field, hash_field, label in (
        ("production_manifest_path", "production_manifest_sha256", "production manifest"),
        ("production_inventory_path", "production_inventory_sha256", "production inventory"),
        ("dataset_inventory_path", "dataset_inventory_sha256", "dataset inventory"),
    ):
        artifact_path = resolve_request_path(request.get(path_field), project_root, label)
        expected_hash = str(request.get(hash_field) or "").strip().lower()
        if not SHA256_PATTERN.fullmatch(expected_hash):
            raise ValueError(f"Execution request has invalid {hash_field}.")
        actual_hash = sha256_file(artifact_path)
        if actual_hash is None or actual_hash.lower() != expected_hash:
            raise ValueError(f"{label} SHA-256 mismatch: expected {expected_hash}; actual {actual_hash}")

    if request.get("selection_sha256"):
        selected_hash = sha256_file(selected_path)
        if selected_hash is None or selected_hash.lower() != str(request["selection_sha256"]).lower():
            raise ValueError("Execution request selection_sha256 does not match selected-task snapshot.")
    return request


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), [dict(row) for row in reader]


def write_csv(path: Path, rows: Iterable[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean(row.get(field)) for field in fieldnames})


def append_jsonl(path: Path, event: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value[:180] or "task"


def matlab_quote(value: str) -> str:
    """Quote a value for a MATLAB character literal without using a shell."""

    return "'" + value.replace("'", "''") + "'"


def build_matlab_expression(
    pipeline_dir: Path,
    scene_id: str,
    prn: str,
    tracking_channel: int,
    project_root: Path,
    resume: bool,
) -> str:
    if type(resume) is not bool:
        raise TypeError("resume must be a bool")
    resume_literal = "true" if resume else "false"
    return (
        f"addpath({matlab_quote(str(pipeline_dir))}); "
        f"run_nav_sage_pipeline({matlab_quote(scene_id)}, "
        f"{matlab_quote(prn)}, "
        f"{matlab_quote('TrackingChannel')}, {tracking_channel}, "
        f"{matlab_quote('ProjectRoot')}, {matlab_quote(str(project_root))}, "
        f"{matlab_quote('Resume')}, {resume_literal});"
    )


def result_is_complete(output_dir: Path) -> bool:
    return output_dir.is_dir() and all((output_dir / name).is_file() for name in REQUIRED_OUTPUT_FILES)


def is_protected_task(row: Dict[str, str]) -> bool:
    scene_id = str(row.get("scene_id", "")).strip()
    prn = str(row.get("prn", "")).strip().upper()
    output_path = str(row.get("output_path", ""))
    if scene_id == PROTECTED_REFERENCE_SCENE and prn == PROTECTED_REFERENCE_PRN:
        return True
    return "G06_nav_sage_v1" in output_path.replace("/", "\\")


def plan_row_key(row: Dict[str, str]) -> Tuple[str, str, str]:
    return (
        str(row.get("scene_id", "")).strip(),
        str(row.get("prn", "")).strip().upper(),
        str(row.get("tracking_channel", "")).strip(),
    )


def load_plan(path: Path) -> Tuple[List[str], Dict[str, Dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f"Plan file does not exist: {path}")
    fields, rows = read_csv(path)
    missing = sorted(REQUIRED_PLAN_COLUMNS - set(fields))
    if missing:
        raise ValueError(f"Plan is missing required columns: {', '.join(missing)}")
    by_id: Dict[str, Dict[str, str]] = {}
    for row in rows:
        task_id = str(row.get("task_id", "")).strip()
        if not task_id:
            raise ValueError("Plan contains a row without task_id")
        if task_id in by_id:
            raise ValueError(f"Plan contains duplicate task_id: {task_id}")
        by_id[task_id] = row
    return fields, by_id


def load_selected_tasks(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Selected task file does not exist: {path}")
    fields, rows = read_csv(path)
    if "task_id" not in fields and not {"scene_id", "prn", "tracking_channel"}.issubset(fields):
        raise ValueError(
            "selected_tasks.csv must contain task_id, or scene_id + prn + tracking_channel"
        )
    if not rows:
        raise ValueError("selected_tasks.csv contains no selected tasks")
    return rows


def resolve_selected_rows(
    selected_rows: Sequence[Dict[str, str]],
    plan_by_id: Dict[str, Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    selected: List[Dict[str, str]] = []
    rejected: List[Dict[str, Any]] = []
    seen: set[str] = set()

    key_to_ids: Dict[Tuple[str, str, str], List[str]] = {}
    for task_id, row in plan_by_id.items():
        key_to_ids.setdefault(plan_row_key(row), []).append(task_id)

    for selection in selected_rows:
        task_id = str(selection.get("task_id", "")).strip()
        if not task_id:
            key = (
                str(selection.get("scene_id", "")).strip(),
                str(selection.get("prn", "")).strip().upper(),
                str(selection.get("tracking_channel", "")).strip(),
            )
            matches = key_to_ids.get(key, [])
            if len(matches) == 1:
                task_id = matches[0]
            elif not matches:
                rejected.append({"selection": selection, "reason": "task_not_in_plan"})
                continue
            else:
                rejected.append({"selection": selection, "reason": "selection_matches_multiple_plan_rows"})
                continue

        if task_id in seen:
            rejected.append({"task_id": task_id, "reason": "duplicate_selected_task"})
            continue
        seen.add(task_id)
        plan_row = plan_by_id.get(task_id)
        if plan_row is None:
            rejected.append({"task_id": task_id, "reason": "task_not_in_plan"})
            continue

        for field in ("scene_id", "prn", "tracking_channel"):
            requested = str(selection.get(field, "")).strip()
            if requested and requested.upper() != str(plan_row.get(field, "")).strip().upper():
                rejected.append({"task_id": task_id, "reason": f"selected_{field}_does_not_match_plan"})
                break
        else:
            selected.append(plan_row)
    return selected, rejected


def validate_request_scope(
    request: Dict[str, Any],
    selected: Sequence[Dict[str, str]],
    rejected: Sequence[Dict[str, Any]],
    production_manifest_path: Path,
) -> List[str]:
    """Ensure the immutable request names exactly the tasks about to be run."""

    errors: List[str] = []
    if rejected:
        errors.append("request_selected_snapshot_contains_rejected_or_unknown_task")

    ordered = request.get("ordered_task_ids")
    if not isinstance(ordered, list) or not ordered or any(not isinstance(item, str) or not item.strip() for item in ordered):
        errors.append("request_ordered_task_ids_invalid")
        ordered_ids: List[str] = []
    else:
        ordered_ids = [item.strip() for item in ordered]
        if len(set(ordered_ids)) != len(ordered_ids):
            errors.append("request_ordered_task_ids_duplicate")

    selected_ids = [str(row.get("task_id", "")).strip() for row in selected]
    if selected_ids != ordered_ids:
        errors.append("request_task_order_or_scope_mismatch")

    if len(selected) == 1:
        row = selected[0]
        comparisons = (
            ("scene_id", str(request.get("scene_id", "")).strip(), str(row.get("scene_id", "")).strip()),
            ("PRN", str(request.get("PRN", "")).strip().upper(), str(row.get("prn", "")).strip().upper()),
        )
        for field, requested, actual in comparisons:
            if not requested or requested != actual:
                errors.append(f"request_{field}_scope_mismatch")
        requested_channel = as_int(request.get("tracking_channel"))
        actual_channel = as_int(row.get("tracking_channel"))
        if requested_channel is None or requested_channel != actual_channel:
            errors.append("request_tracking_channel_scope_mismatch")
        requested_rate = as_int(request.get("sample_rate_hz"))
        actual_rate = as_int(row.get("sample_rate_hz"))
        if requested_rate is None or requested_rate != actual_rate or requested_rate != SUPPORTED_SAMPLE_RATE_HZ:
            errors.append("request_sample_rate_scope_mismatch")
        requested_output = str(request.get("expected_output_namespace", "")).strip()
        if not requested_output or not paths_equal(Path(requested_output), Path(str(row.get("output_path", "")).strip())):
            errors.append("request_output_namespace_scope_mismatch")
        requested_production_id = str(request.get("production_task_id", "")).strip()
        actual_production_id = str(row.get("production_task_id", "")).strip()
        if not requested_production_id:
            errors.append("request_production_task_id_missing")
        elif requested_production_id != actual_production_id:
            errors.append("request_production_task_id_scope_mismatch")

    try:
        production_manifest = json.loads(production_manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        errors.append("production_manifest_unreadable")
        production_manifest = {}
    manifest_tasks = production_manifest.get("tasks", []) if isinstance(production_manifest, dict) else []
    if not isinstance(manifest_tasks, list):
        errors.append("production_manifest_tasks_invalid")
        manifest_tasks = []

    for row in selected:
        production_id = str(row.get("production_task_id", "")).strip()
        if not production_id:
            production_id = str(request.get("production_task_id", "")).strip()
        matches = [task for task in manifest_tasks if isinstance(task, dict) and str(task.get("task_id", "")).strip() == production_id]
        if len(matches) != 1:
            errors.append(f"production_manifest_task_scope_missing:{production_id}")
            continue
        task = matches[0]
        if str(task.get("scene_id", "")).strip() != str(row.get("scene_id", "")).strip():
            errors.append(f"production_manifest_scene_mismatch:{production_id}")
        if str(task.get("PRN", "")).strip().upper() != str(row.get("prn", "")).strip().upper():
            errors.append(f"production_manifest_prn_mismatch:{production_id}")
        if as_int(task.get("tracking_channel")) != as_int(row.get("tracking_channel")):
            errors.append(f"production_manifest_channel_mismatch:{production_id}")
        if as_int(task.get("sample_rate_hz")) != SUPPORTED_SAMPLE_RATE_HZ:
            errors.append(f"production_manifest_sample_rate_mismatch:{production_id}")
        if not paths_equal(Path(str(task.get("expected_output_namespace", ""))), Path(str(row.get("output_path", "")))):
            errors.append(f"production_manifest_output_mismatch:{production_id}")
        if task.get("new_only") is not True:
            errors.append(f"production_manifest_new_only_mismatch:{production_id}")
        if task.get("resume_allowed") is not False:
            errors.append(f"production_manifest_resume_allowed_mismatch:{production_id}")
    return sorted(set(errors))


def path_gate_errors(row: Dict[str, str], project_root: Path) -> List[str]:
    errors: List[str] = []
    for field in (
        "raw_path",
        "tracking_path",
        "telemetry_path",
        "navigation_path",
        "trajectory_path",
        "satellite_timeseries_path",
        "satellite_summary_path",
        "metadata_path",
    ):
        raw_path = str(row.get(field, "")).strip()
        if not raw_path:
            errors.append(f"{field}_missing_from_plan")
            continue
        path = Path(raw_path)
        if not path.is_file():
            errors.append(f"{field}_not_found")
            continue
        try:
            if path.stat().st_size <= 0:
                errors.append(f"{field}_empty")
        except OSError:
            errors.append(f"{field}_stat_failed")

    metadata_path = Path(str(row.get("metadata_path", "")).strip())
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
            if metadata.get("scene_id") not in {None, "", row.get("scene_id")}:  # type: ignore[union-attr]
                errors.append("metadata_scene_id_mismatch")
        except (OSError, json.JSONDecodeError):
            errors.append("metadata_unreadable")

    # The path must remain in the fixed namespace selected by the current
    # pipeline.  This also prevents a selected CSV from redirecting execution
    # into a historical or unrelated result directory.
    scene_id = str(row.get("scene_id", "")).strip()
    prn = str(row.get("prn", "")).strip().upper()
    expected_output = project_root / "scenes" / scene_id / "sage_results" / EXPERIMENT_NAMESPACE / prn
    plan_output = Path(str(row.get("output_path", "")).strip())
    try:
        if plan_output.resolve() != expected_output.resolve():
            errors.append("output_path_does_not_match_pipeline_namespace")
    except OSError:
        errors.append("output_path_resolution_failed")

    if plan_output.exists():
        errors.append("existing_output_directory_or_file")
    if "G06_nav_sage_v1" in str(plan_output).replace("/", "\\"):
        errors.append("protected_G06_nav_sage_v1_target")
    return errors


def validate_selected_task(
    row: Dict[str, str],
    project_root: Path,
    pipeline_path: Path,
    request: Optional[Dict[str, Any]] = None,
) -> List[str]:
    errors: List[str] = []
    task_id = str(row.get("task_id", "")).strip()
    if request is not None:
        errors.extend(f"request_policy:{error}" for error in validate_execution_request_policy(request))
    if not task_id:
        errors.append("missing_task_id")
    if is_protected_task(row):
        errors.append("protected_reference_or_G06_v1")
    if str(row.get("scene_role", "")).strip().lower() == "reference_scene":
        errors.append("reference_scene_is_protected")
    if str(row.get("status", "")).strip() != "ready":
        errors.append(f"plan_status_not_ready:{row.get('status', '')}")
    if not as_bool(row.get("execution_allowed")):
        errors.append("plan_execution_not_allowed")
    if as_bool(row.get("requires_manual_channel_selection")):
        errors.append("manual_channel_selection_required")
    if str(row.get("hard_gate_failures", "")).strip():
        errors.append("plan_contains_hard_gate_failures")

    channel = as_int(row.get("tracking_channel"))
    if channel is None or channel < 0:
        errors.append("invalid_tracking_channel")
    if not str(row.get("prn", "")).strip().upper().startswith("G"):
        errors.append("invalid_prn")
    if not str(row.get("scene_id", "")).strip():
        errors.append("missing_scene_id")
    if as_int(row.get("sample_rate_hz")) != SUPPORTED_SAMPLE_RATE_HZ:
        errors.append("unsupported_sample_rate;only_10230000_hz_is_supported")

    expected_hash = str(row.get("pipeline_sha256", "")).strip()
    actual_hash = sha256_file(pipeline_path)
    if not expected_hash:
        errors.append("plan_pipeline_hash_missing")
    elif actual_hash != expected_hash:
        errors.append("pipeline_hash_mismatch")

    errors.extend(path_gate_errors(row, project_root))
    return sorted(set(errors))


def transition_event(
    history_path: Path,
    task_id: str,
    old_status: str,
    new_status: str,
    reason: str = "",
    **extra: Any,
) -> None:
    event = {
        "timestamp_utc": iso_time(),
        "task_id": task_id,
        "old_status": old_status,
        "new_status": new_status,
        "reason": reason,
    }
    event.update(extra)
    append_jsonl(history_path, event)


def result_qa(output_dir: Path) -> List[str]:
    errors: List[str] = []
    if not output_dir.is_dir():
        return ["output_directory_missing_after_run"]
    for name in REQUIRED_OUTPUT_FILES:
        path = output_dir / name
        if not path.is_file():
            errors.append(f"required_output_missing:{name}")
        else:
            try:
                if path.stat().st_size <= 0:
                    errors.append(f"required_output_empty:{name}")
            except OSError:
                errors.append(f"required_output_stat_failed:{name}")
    return errors


def execute_task(
    row: Dict[str, str],
    project_root: Path,
    pipeline_path: Path,
    matlab_executable: str,
    task_log_path: Path,
    timeout_seconds: Optional[float],
    history_path: Path,
    new_only: bool,
    resume_allowed: bool,
) -> Dict[str, Any]:
    task_id = str(row.get("task_id", "")).strip()
    output_dir = Path(str(row.get("output_path", "")).strip())
    channel = as_int(row.get("tracking_channel"))
    if new_only is not True or resume_allowed is not False:
        raise RuntimeError("execution policy requires new_only=true and resume_allowed=false")
    start = utc_now()
    transition_event(history_path, task_id, "ready", "running", "preflight_passed")

    expression = build_matlab_expression(
        pipeline_path.parent,
        str(row.get("scene_id", "")).strip(),
        str(row.get("prn", "")).strip().upper(),
        int(channel),
        project_root,
        resume=resume_allowed,
    )
    command_preview = f"{matlab_executable} -batch {expression}"
    result: Dict[str, Any] = {
        "task_id": task_id,
        "scene_id": row.get("scene_id", ""),
        "prn": row.get("prn", ""),
        "tracking_channel": channel,
        "output_path": str(output_dir),
        "status": "failed",
        "start_time_utc": iso_time(start),
        "end_time_utc": "",
        "duration_seconds": "",
        "exit_code": "",
        "error_message": "",
        "command_preview": command_preview,
        "task_log_path": str(task_log_path),
    }

    try:
        # The target was checked before entering this function.  Check again
        # after the transition to close the race between workers/processes.
        if output_dir.exists():
            raise RuntimeError("existing_output_directory_before_matlab_launch")
        with task_log_path.open("w", encoding="utf-8") as log_handle:
            log_handle.write(f"command={command_preview}\n")
            log_handle.write(f"started_utc={result['start_time_utc']}\n\n")
            completed = subprocess.run(
                [matlab_executable, "-batch", expression],
                cwd=str(project_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        result["exit_code"] = completed.returncode
        if completed.returncode != 0:
            raise RuntimeError(f"matlab_exit_code:{completed.returncode}")
        qa_errors = result_qa(output_dir)
        if qa_errors:
            raise RuntimeError(";".join(qa_errors))
        result["status"] = "completed"
        transition_event(
            history_path,
            task_id,
            "running",
            "completed",
            "matlab_exit_0_and_output_qa_pass",
            exit_code=completed.returncode,
        )
    except subprocess.TimeoutExpired as exc:
        result["error_message"] = f"timeout:{exc.timeout}"
        transition_event(history_path, task_id, "running", "failed", result["error_message"])
    except Exception as exc:  # one task must not terminate the batch
        result["error_message"] = str(exc)
        transition_event(history_path, task_id, "running", "failed", result["error_message"])
    finally:
        end = utc_now()
        result["end_time_utc"] = iso_time(end)
        result["duration_seconds"] = round((end - start).total_seconds(), 3)
    return result


def make_rejected_result(item: Dict[str, Any], log_dir: Path) -> Dict[str, Any]:
    selection = item.get("selection", {})
    task_id = item.get("task_id") or selection.get("task_id", "")
    return {
        "task_id": task_id,
        "scene_id": selection.get("scene_id", ""),
        "prn": selection.get("prn", ""),
        "tracking_channel": selection.get("tracking_channel", ""),
        "output_path": "",
        "status": "skipped",
        "start_time_utc": "",
        "end_time_utc": "",
        "duration_seconds": "",
        "exit_code": "",
        "error_message": item.get("reason", "selection_rejected"),
        "command_preview": "",
        "task_log_path": str(log_dir),
    }


def write_execution_report(
    path: Path,
    execution_id: str,
    plan_path: Path,
    selected_path: Path,
    mode: str,
    results: Sequence[Dict[str, Any]],
) -> None:
    counts: Dict[str, int] = {}
    for result in results:
        status = str(result.get("status", ""))
        counts[status] = counts.get(status, 0) + 1
    lines = [
        "# Batch SAGE Execution Report",
        "",
        f"- Execution ID: `{execution_id}`",
        f"- Mode: `{mode}`",
        f"- Plan: `{plan_path}`",
        f"- Selected tasks: `{selected_path}`",
        "",
        "> This report is generated by the executor. Dry-run mode never invokes MATLAB.",
        "",
        "## Status counts",
        "",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Task results", "", "| Task | Scene | PRN | Ch. | Status | Error |", "|---|---|---|---:|---|---|"])
    for result in results:
        error = clean(result.get("error_message")).replace("|", "\\|")
        lines.append(
            f"| {clean(result.get('task_id'))} | {clean(result.get('scene_id'))} | "
            f"{clean(result.get('prn'))} | {clean(result.get('tracking_channel'))} | "
            f"{clean(result.get('status'))} | {error} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_root = script_path.parents[2]
    parser = argparse.ArgumentParser(
        description="Execute an explicit selected-task batch through run_nav_sage_pipeline.m"
    )
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--selected-tasks",
        type=Path,
        required=True,
        help="CSV with task_id, or scene_id/prn/tracking_channel; never defaults to all ready tasks",
    )
    parser.add_argument(
        "--request-manifest",
        type=Path,
        default=None,
        help="Immutable windows_execution_request_v1 JSON; required for --execute",
    )
    parser.add_argument(
        "--expected-request-sha256",
        default=None,
        help="Human-reviewed SHA-256 for --request-manifest",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview selected tasks; never invoke MATLAB")
    mode.add_argument("--execute", action="store_true", help="Explicitly invoke MATLAB for selected ready tasks")
    parser.add_argument("--matlab-executable", default="matlab")
    parser.add_argument("--timeout-seconds", type=float, default=None)
    parser.add_argument("--log-root", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    plan_path = args.plan.resolve()
    selected_path = args.selected_tasks.resolve()
    pipeline_path = project_root / PIPELINE_RELATIVE
    if not pipeline_path.is_file():
        raise FileNotFoundError(f"Pipeline entrypoint does not exist: {pipeline_path}")

    if (args.request_manifest is None) != (args.expected_request_sha256 is None):
        raise ValueError("--request-manifest and --expected-request-sha256 must be supplied together.")
    if args.execute and args.request_manifest is None:
        raise ValueError("--execute requires an immutable request manifest and expected SHA-256.")

    request: Optional[Dict[str, Any]] = None
    production_manifest_path: Optional[Path] = None
    if args.request_manifest is not None:
        request = load_execution_request(
            args.request_manifest.resolve(),
            str(args.expected_request_sha256),
            project_root,
            plan_path,
            selected_path,
            pipeline_path,
        )
        production_manifest_path = resolve_request_path(
            request.get("production_manifest_path"), project_root, "production manifest"
        )

    # Explicitly require a selection file and load it before creating logs.
    _, plan_by_id = load_plan(plan_path)
    selected_rows = load_selected_tasks(selected_path)
    selected, rejected = resolve_selected_rows(selected_rows, plan_by_id)
    if request is not None and production_manifest_path is not None:
        scope_errors = validate_request_scope(request, selected, rejected, production_manifest_path)
        if scope_errors:
            raise ValueError("Execution request task scope rejected: " + ";".join(scope_errors))

    execution_new_only = True if request is None else bool(request["new_only"])
    execution_resume_allowed = False if request is None else bool(request["resume_allowed"])

    execution_id = f"{EXECUTION_NAMESPACE}_{utc_now().strftime('%Y%m%dT%H%M%SZ')}"
    log_root = (
        args.log_root.resolve()
        if args.log_root is not None
        else project_root / "dataset_generation_logs" / EXECUTION_NAMESPACE / execution_id
    )
    log_root.mkdir(parents=True, exist_ok=False)
    task_logs = log_root / "task_logs"
    task_logs.mkdir(parents=True, exist_ok=False)
    locks_dir = log_root / "locks"
    locks_dir.mkdir(parents=True, exist_ok=False)
    history_path = log_root / "status_history.jsonl"
    execution_log_path = log_root / "batch_execution_log.csv"
    report_path = log_root / "batch_execution_report.md"

    results: List[Dict[str, Any]] = [make_rejected_result(item, log_root) for item in rejected]
    for row in selected:
        task_id = str(row.get("task_id", "")).strip()
        validation_errors = validate_selected_task(row, project_root, pipeline_path, request=request)
        if validation_errors:
            result = {
                "task_id": task_id,
                "scene_id": row.get("scene_id", ""),
                "prn": row.get("prn", ""),
                "tracking_channel": row.get("tracking_channel", ""),
                "output_path": row.get("output_path", ""),
                "status": "skipped",
                "start_time_utc": "",
                "end_time_utc": "",
                "duration_seconds": "",
                "exit_code": "",
                "error_message": ";".join(validation_errors),
                "command_preview": "",
                "task_log_path": "",
            }
            transition_event(history_path, task_id, "ready", "skipped", result["error_message"])
            results.append(result)
            continue

        channel = as_int(row.get("tracking_channel"))
        expression = build_matlab_expression(
            pipeline_path.parent,
            str(row.get("scene_id", "")).strip(),
            str(row.get("prn", "")).strip().upper(),
            int(channel),
            project_root,
            resume=execution_resume_allowed,
        )
        command_preview = f"{args.matlab_executable} -batch {expression}"
        if not args.execute:
            result = {
                "task_id": task_id,
                "scene_id": row.get("scene_id", ""),
                "prn": row.get("prn", ""),
                "tracking_channel": channel,
                "output_path": row.get("output_path", ""),
                "status": "ready",
                "start_time_utc": "",
                "end_time_utc": "",
                "duration_seconds": "",
                "exit_code": "",
                "error_message": "dry_run_only_not_executed",
                "command_preview": command_preview,
                "task_log_path": "",
            }
            transition_event(history_path, task_id, "ready", "ready", "dry_run_preview", command_preview=command_preview)
            results.append(result)
            continue

        task_log_path = task_logs / f"{safe_filename(task_id)}.log"
        lock_path = locks_dir / f"{safe_filename(task_id)}.lock"
        try:
            # Keep the lock as an audit artifact.  A new execution directory
            # is required for a retry, so an old run cannot be accidentally
            # resumed or launched twice under the same namespace.
            with lock_path.open("x", encoding="utf-8") as lock_handle:
                json.dump(
                    {
                        "task_id": task_id,
                        "execution_id": execution_id,
                        "created_utc": iso_time(utc_now()),
                    },
                    lock_handle,
                    ensure_ascii=False,
                    indent=2,
                )
                lock_handle.write("\n")
        except FileExistsError:
            error_message = "task_lock_already_exists"
            result = {
                "task_id": task_id,
                "scene_id": row.get("scene_id", ""),
                "prn": row.get("prn", ""),
                "tracking_channel": channel,
                "output_path": row.get("output_path", ""),
                "status": "skipped",
                "start_time_utc": "",
                "end_time_utc": "",
                "duration_seconds": "",
                "exit_code": "",
                "error_message": error_message,
                "command_preview": command_preview,
                "task_log_path": str(task_log_path),
                "lock_path": str(lock_path),
            }
            transition_event(history_path, task_id, "ready", "skipped", error_message)
            results.append(result)
            continue

        try:
            result = execute_task(
                row,
                project_root,
                pipeline_path,
                args.matlab_executable,
                task_log_path,
                args.timeout_seconds,
                history_path,
                execution_new_only,
                execution_resume_allowed,
            )
        except Exception as exc:  # isolate unexpected per-task failures
            error_message = f"executor_exception:{exc}"
            result = {
                "task_id": task_id,
                "scene_id": row.get("scene_id", ""),
                "prn": row.get("prn", ""),
                "tracking_channel": channel,
                "output_path": row.get("output_path", ""),
                "status": "failed",
                "start_time_utc": "",
                "end_time_utc": "",
                "duration_seconds": "",
                "exit_code": "",
                "error_message": error_message,
                "command_preview": command_preview,
                "task_log_path": str(task_log_path),
                "lock_path": str(lock_path),
            }
            transition_event(history_path, task_id, "ready", "failed", error_message)
        result["lock_path"] = str(lock_path)
        results.append(result)

    fields = [
        "task_id",
        "scene_id",
        "prn",
        "tracking_channel",
        "output_path",
        "status",
        "start_time_utc",
        "end_time_utc",
        "duration_seconds",
        "exit_code",
        "error_message",
        "command_preview",
        "task_log_path",
        "lock_path",
    ]
    write_csv(execution_log_path, results, fields)
    write_execution_report(
        report_path,
        execution_id,
        plan_path,
        selected_path,
        "execute" if args.execute else "dry-run",
        results,
    )

    print(f"execution_id={execution_id}")
    print(f"mode={'execute' if args.execute else 'dry-run'}")
    print(f"selected_rows={len(selected_rows)}")
    print(f"accepted_rows={len(selected)}")
    print(f"rejected_rows={len(rejected)}")
    if request is not None:
        print(f"request_id={request.get('request_id', '')}")
        print(f"request_sha256={str(args.expected_request_sha256).lower()}")
        print(f"new_only={str(execution_new_only).lower()}")
        print(f"resume_allowed={str(execution_resume_allowed).lower()}")
    print(f"execution_log={execution_log_path}")
    print(f"execution_report={report_path}")
    print("matlab_invoked=" + ("true" if args.execute and bool(selected) else "false"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
