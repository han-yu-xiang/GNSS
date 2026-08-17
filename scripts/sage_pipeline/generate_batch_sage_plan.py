"""Generate a read-only batch SAGE execution plan.

This module intentionally does not invoke MATLAB or the SAGE pipeline.  It
reads the project inventory and scene input metadata, checks the fixed output
namespace used by the current pipeline, estimates workload, and writes an
immutable plan under dataset_generation_logs/batch_sage/<plan_id>/.

The planner is deliberately conservative:

* a PRN mapped to more than one tracking channel is kept as one blocked task;
* inventory warnings are not silently resolved;
* an existing nav_sage_v2/<PRN> directory is never a runnable target;
* reference-scene tasks are retained in the plan but are protected/skipped;
* missing estimates are represented as empty fields with an explicit warning.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "batch_sage_plan_v1"
ESTIMATE_MODEL_VERSION = "reference_v1"
EXPERIMENT_NAMESPACE = "nav_sage_v2"
SUPPORTED_SAMPLE_RATES = {10_230_000, 20_460_000}
REFERENCE_SAMPLE_RATE = 10_230_000

REQUIRED_PROJECT_DIRS = ("scenes", "dataset", "scripts", "dataset_generation_logs")
REQUIRED_PIPELINE_FILES = (
    "run_nav_sage_pipeline.m",
    "summarize_prn_validation.py",
)
REQUIRED_RESULT_FILES = (
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

TASK_WARNING_RE = re.compile(
    r"(?P<code>[^:;]+):(?P<prn>G\d{2}):ch(?P<channel>\d+)",
    re.IGNORECASE,
)
PRN_RE = re.compile(r"^G\d{2}$", re.IGNORECASE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(value: Optional[datetime] = None) -> str:
    current = value or utc_now()
    return current.strftime("%Y%m%dT%H%M%SZ")


def clean(value: Any) -> str:
    """Return a CSV-safe scalar representation; None becomes an empty cell."""

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


def as_float(value: Any) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def format_number(value: Optional[float]) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6g}"


def safe_json_loads(value: Any) -> Tuple[Any, Optional[str]]:
    if value is None or str(value).strip() == "":
        return {}, None
    try:
        return json.loads(str(value)), None
    except json.JSONDecodeError as exc:
        return {}, f"invalid_json:{exc.msg}"


def parse_prn_list(value: Any) -> List[str]:
    if value is None:
        return []
    return sorted(
        {
            token.strip().upper()
            for token in str(value).split(";")
            if token.strip()
        }
    )


def parse_channel_map(value: Any) -> Tuple[Dict[str, List[int]], Optional[str]]:
    parsed, error = safe_json_loads(value)
    if error:
        return {}, error
    if not isinstance(parsed, dict):
        return {}, "channel_map_not_object"

    result: Dict[str, List[int]] = {}
    for raw_prn, raw_channels in parsed.items():
        prn = str(raw_prn).strip().upper()
        if isinstance(raw_channels, list):
            channels: List[int] = []
            for raw_channel in raw_channels:
                channel = as_int(raw_channel)
                if channel is not None:
                    channels.append(channel)
            result[prn] = sorted(set(channels))
        else:
            result[prn] = []
    return result, None


def sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def file_info(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {
            "exists": False,
            "size_bytes": None,
            "readable": False,
            "path": "",
        }
    exists = path.is_file()
    size = None
    if exists:
        try:
            size = path.stat().st_size
        except OSError:
            size = None
    return {
        "exists": exists,
        "size_bytes": size,
        "readable": exists,
        "path": str(path),
    }


def resolve_scene_path(scene_dir: Path, value: Any) -> Optional[Path]:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return scene_dir / candidate


def read_json(path: Path) -> Tuple[Dict[str, Any], Optional[str]]:
    if not path.is_file():
        return {}, "file_missing"
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            return {}, "json_not_object"
        return value, None
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"json_read_error:{type(exc).__name__}"


def count_csv_rows(path: Path) -> Optional[int]:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return sum(1 for row in reader if any(str(v or "").strip() for v in row.values()))
    except (OSError, csv.Error, UnicodeError):
        return None


def csv_prns(path: Path) -> Tuple[set[str], Optional[str]]:
    if not path.is_file():
        return set(), "file_missing"
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "prn" not in reader.fieldnames:
                return set(), "prn_column_missing"
            values = {
                str(row.get("prn", "")).strip().upper()
                for row in reader
                if str(row.get("prn", "")).strip()
            }
            return values, None
    except (OSError, csv.Error, UnicodeError) as exc:
        return set(), f"csv_read_error:{type(exc).__name__}"


def result_collision_status(output_dir: Path) -> str:
    if not output_dir.exists():
        return "absent"
    if not output_dir.is_dir():
        return "unknown_existing"
    present = {path.name for path in output_dir.iterdir() if path.is_file()}
    if set(REQUIRED_RESULT_FILES).issubset(present):
        return "complete_existing"
    if present or any(output_dir.iterdir()):
        return "partial_existing"
    return "unknown_existing"


def parse_task_warnings(
    raw_warnings: Any,
    prn: str,
    channel_candidates: Sequence[int],
) -> Tuple[List[str], List[str]]:
    """Return (codes, original warning strings) relevant to one task."""

    raw = str(raw_warnings or "").strip()
    if not raw:
        return [], []

    codes: List[str] = []
    messages: List[str] = []
    for token in [part.strip() for part in raw.split(";") if part.strip()]:
        match = TASK_WARNING_RE.search(token)
        if match:
            warning_prn = match.group("prn").upper()
            warning_channel = as_int(match.group("channel"))
            if warning_prn != prn:
                continue
            if warning_channel is not None and channel_candidates and warning_channel not in channel_candidates:
                continue
        else:
            # An unscoped inventory warning is conservatively attached to all
            # tasks in that scene and must be reviewed before execution.
            if ":" in token and prn not in token.upper():
                continue
        code = token.split(":", 1)[0].strip().lower()
        code = re.sub(r"[^a-z0-9_]+", "_", code).strip("_") or "inventory_warning"
        codes.append(f"inventory_warning_{code}")
        messages.append(token)
    return sorted(set(codes)), messages


def estimate_scale(
    sample_rate_hz: Optional[int],
    exact_window_count: Optional[int],
) -> Dict[str, Any]:
    """Estimate work without reading IQ or executing any SAGE stage.

    Existing Stage0 output is treated as exact only for an already completed
    result.  For a new 10.23 MHz task the reference-scene range is retained as
    a deliberately low-confidence prior.  There is no 20.46 MHz reference
    window-duration baseline in the current project, so those fields remain
    empty rather than being guessed.
    """

    result: Dict[str, Any] = {
        "estimated_valid_nav_symbols": None,
        "estimated_40ms_windows_low": None,
        "estimated_40ms_windows_typical": None,
        "estimated_40ms_windows_high": None,
        "estimated_stage1_windows_low": None,
        "estimated_stage1_windows_typical": None,
        "estimated_stage1_windows_high": None,
        "estimated_stage2_candidates_low": None,
        "estimated_stage2_candidates_typical": None,
        "estimated_stage2_candidates_high": None,
        "estimated_stage2_model_evaluations_low": None,
        "estimated_stage2_model_evaluations_typical": None,
        "estimated_stage2_model_evaluations_high": None,
        "sample_rate_factor": None,
        "workload_units_low": None,
        "workload_units_typical": None,
        "workload_units_high": None,
        "estimate_method": "unavailable",
        "estimate_confidence": "low",
        "estimate_warning": "window_estimate_unavailable",
    }

    if sample_rate_hz in SUPPORTED_SAMPLE_RATES:
        result["sample_rate_factor"] = sample_rate_hz / REFERENCE_SAMPLE_RATE

    if exact_window_count is not None:
        windows = max(int(exact_window_count), 0)
        result["estimated_40ms_windows_low"] = windows
        result["estimated_40ms_windows_typical"] = windows
        result["estimated_40ms_windows_high"] = windows
        result["estimated_stage1_windows_low"] = windows
        result["estimated_stage1_windows_typical"] = windows
        result["estimated_stage1_windows_high"] = windows
        result["estimate_method"] = "existing_stage0_exact"
        result["estimate_confidence"] = "high"
        result["estimate_warning"] = ""
    elif sample_rate_hz == REFERENCE_SAMPLE_RATE:
        # Reference validation observed 319–1175 valid 40 ms windows.  The
        # planner intentionally exposes this as a prior, not as a prediction.
        low_windows, typical_windows, high_windows = 319, 1175, 1175
        result["estimated_40ms_windows_low"] = low_windows
        result["estimated_40ms_windows_typical"] = typical_windows
        result["estimated_40ms_windows_high"] = high_windows
        result["estimated_stage1_windows_low"] = low_windows
        result["estimated_stage1_windows_typical"] = typical_windows
        result["estimated_stage1_windows_high"] = high_windows
        result["estimate_method"] = "reference_prior_v1"
        result["estimate_confidence"] = "low"
        result["estimate_warning"] = "window_estimate_reference_prior"

    low_windows = result["estimated_40ms_windows_low"]
    typical_windows = result["estimated_40ms_windows_typical"]
    high_windows = result["estimated_40ms_windows_high"]
    if low_windows is None or typical_windows is None or high_windows is None:
        return result

    ratios = (0.044, 0.082, 0.298)
    candidate_values = [
        max(0, int((windows * ratio) + 0.999999))
        for windows, ratio in zip(
            (low_windows, typical_windows, high_windows), ratios
        )
    ]
    result["estimated_stage2_candidates_low"] = candidate_values[0]
    result["estimated_stage2_candidates_typical"] = candidate_values[1]
    result["estimated_stage2_candidates_high"] = candidate_values[2]
    result["estimated_stage2_model_evaluations_low"] = candidate_values[0] * 4
    result["estimated_stage2_model_evaluations_typical"] = candidate_values[1] * 4
    result["estimated_stage2_model_evaluations_high"] = candidate_values[2] * 4

    rate_factor = result["sample_rate_factor"] or 1.0
    workloads = []
    for windows, candidates in zip((low_windows, typical_windows, high_windows), candidate_values):
        stage1_units = windows * rate_factor
        stage2_units = candidates * (1 + 2 + 3 + 4) * rate_factor
        workloads.append(round(stage1_units + stage2_units, 3))
    result["workload_units_low"] = workloads[0]
    result["workload_units_typical"] = workloads[1]
    result["workload_units_high"] = workloads[2]
    return result


def check_project_consistency(project_root: Path) -> List[str]:
    issues: List[str] = []
    for directory in REQUIRED_PROJECT_DIRS:
        if not (project_root / directory).is_dir():
            issues.append(f"missing_project_directory:{directory}")
    for file_name in REQUIRED_PIPELINE_FILES:
        if not (project_root / "scripts" / "sage_pipeline" / file_name).is_file():
            issues.append(f"missing_pipeline_file:{file_name}")
    if not (project_root / "docs" / "MULTIPATH_EVENT_DATABASE_DESIGN.md").is_file():
        issues.append("missing_design_document:MULTIPATH_EVENT_DATABASE_DESIGN.md")
    if not (project_root / "docs" / "BATCH_SAGE_DRY_RUN_DESIGN.md").is_file():
        issues.append("missing_design_document:BATCH_SAGE_DRY_RUN_DESIGN.md")
    if not (project_root / "dataset" / "dataset_inventory.csv").is_file():
        issues.append("missing_inventory:dataset_inventory.csv")
    return issues


def load_inventory(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Inventory has no header")
        required = {"scene_id", "available_prns", "prn_tracking_channel_map", "sampling_rate_hz"}
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError(f"Inventory missing required columns: {', '.join(missing)}")
        return [dict(row) for row in reader]


def existing_stage0_count(output_dir: Path, protected_legacy_dir: Optional[Path]) -> Optional[int]:
    candidates = [output_dir / "stage0_valid_40ms_windows.csv"]
    if protected_legacy_dir is not None:
        candidates.append(protected_legacy_dir / "stage0_valid_40ms_windows.csv")
    for candidate in candidates:
        count = count_csv_rows(candidate)
        if count is not None:
            return count
    return None


def make_task(
    project_root: Path,
    inventory_row: Dict[str, str],
    plan_id: str,
    pipeline_path: Path,
    reference_report_path: Path,
) -> Dict[str, Any]:
    scene_id = str(inventory_row.get("scene_id", "")).strip()
    scene_role = str(inventory_row.get("scene_role", "")).strip() or "unknown"
    scene_dir = project_root / "scenes" / scene_id
    metadata_path = scene_dir / "metadata.json"
    metadata, metadata_error = read_json(metadata_path)

    available_prns = parse_prn_list(inventory_row.get("available_prns"))
    channel_map, channel_map_error = parse_channel_map(
        inventory_row.get("prn_tracking_channel_map")
    )
    sample_rate_hz = as_int(inventory_row.get("sampling_rate_hz"))

    tasks: List[Dict[str, Any]] = []
    for prn in available_prns:
        candidates = channel_map.get(prn, [])
        unique_channel = candidates[0] if len(candidates) == 1 else None
        requires_manual = len(candidates) > 1
        tracking_path: Optional[Path] = (
            scene_dir / "gnss_sdr" / "tracking" / f"{scene_id}_track_ch_{unique_channel}.mat"
            if unique_channel is not None
            else None
        )
        telemetry_path: Optional[Path] = (
            scene_dir / "gnss_sdr" / "telemetry" / f"{scene_id}_telemetry_ch_{unique_channel}.dat"
            if unique_channel is not None
            else None
        )
        tracking_candidates = [
            scene_dir / "gnss_sdr" / "tracking" / f"{scene_id}_track_ch_{channel}.mat"
            for channel in candidates
        ]
        telemetry_candidates = [
            scene_dir / "gnss_sdr" / "telemetry" / f"{scene_id}_telemetry_ch_{channel}.dat"
            for channel in candidates
        ]

        raw_path = resolve_scene_path(scene_dir, inventory_row.get("raw_path"))
        navigation_path = resolve_scene_path(scene_dir, inventory_row.get("rinex_nav_files"))
        trajectory_path = resolve_scene_path(scene_dir, inventory_row.get("trajectory_files"))
        satellite_timeseries_path = scene_dir / "satellite" / f"{scene_id}_satellite_elevation_timeseries.csv"
        satellite_summary_path = scene_dir / "satellite" / f"{scene_id}_satellite_elevation_summary.csv"
        output_path = scene_dir / "sage_results" / EXPERIMENT_NAMESPACE / prn

        input_paths = {
            "raw_path": raw_path,
            "tracking_path": tracking_path,
            "telemetry_path": telemetry_path,
            "navigation_path": navigation_path,
            "trajectory_path": trajectory_path,
            "satellite_timeseries_path": satellite_timeseries_path,
            "satellite_summary_path": satellite_summary_path,
            "metadata_path": metadata_path,
        }
        infos = {name: file_info(path) for name, path in input_paths.items()}

        hard_failures: List[str] = []
        warnings: List[str] = []
        warning_codes: List[str] = []

        if metadata_error:
            hard_failures.append(f"metadata_{metadata_error}")
        if metadata.get("scene_id") and metadata.get("scene_id") != scene_id:
            hard_failures.append("metadata_scene_id_mismatch")
        metadata_rate = as_int((metadata.get("signal") or {}).get("sample_rate_hz"))
        if metadata_rate is not None and sample_rate_hz is not None and metadata_rate != sample_rate_hz:
            hard_failures.append("metadata_inventory_sample_rate_mismatch")
        if sample_rate_hz not in SUPPORTED_SAMPLE_RATES:
            hard_failures.append("unsupported_sample_rate")

        if not PRN_RE.match(prn):
            hard_failures.append("invalid_prn_format")
        if prn not in channel_map:
            hard_failures.append("missing_channel_mapping")
        if channel_map_error:
            hard_failures.append(channel_map_error)
        if requires_manual:
            hard_failures.append("ambiguous_tracking_channel")
        if len(candidates) == 1 and unique_channel is None:
            hard_failures.append("invalid_channel_value")

        raw_warning_codes, raw_warning_messages = parse_task_warnings(
            inventory_row.get("inventory_warnings"), prn, candidates
        )
        warning_codes.extend(raw_warning_codes)
        warnings.extend(raw_warning_messages)
        if raw_warning_codes:
            hard_failures.extend(raw_warning_codes)

        inventory_status_checks = {
            "gnss_sdr_status": str(inventory_row.get("gnss_sdr_status", "")).upper() == "SUCCESS",
            "tracking_exists": as_bool(inventory_row.get("tracking_exists")),
            "telemetry_exists": as_bool(inventory_row.get("telemetry_exists")),
            "rinex_nav_exists": as_bool(inventory_row.get("rinex_nav_exists")),
            "trajectory_exists": as_bool(inventory_row.get("trajectory_exists")),
            "satellite_geometry_completed": str(
                inventory_row.get("satellite_geometry_status", "")
            ).lower()
            == "completed",
        }
        for field_name, passed in inventory_status_checks.items():
            if not passed:
                hard_failures.append(f"inventory_{field_name}_not_ready")

        for name, info in infos.items():
            if name == "metadata_path":
                continue
            if not info["exists"]:
                hard_failures.append(f"{name}_missing")
            elif info["size_bytes"] == 0:
                hard_failures.append(f"{name}_empty")

        geometry_prns_inventory = set(parse_prn_list(inventory_row.get("satellite_geometry_prns")))
        geometry_prns_summary, geometry_error = csv_prns(satellite_summary_path)
        if geometry_error:
            hard_failures.append(f"satellite_summary_{geometry_error}")
        geometry_has_prn = prn in geometry_prns_inventory and prn in geometry_prns_summary
        if not geometry_has_prn:
            hard_failures.append("satellite_geometry_prn_missing")

        collision = result_collision_status(output_path)
        if collision != "absent":
            warnings.append(f"output_{collision}")

        protected = scene_role.lower() == "reference_scene"
        protected_legacy_dir: Optional[Path] = None
        if protected and prn == "G06":
            protected_legacy_dir = scene_dir / "sage_results" / "G06_nav_sage_v1"
        exact_window_count = existing_stage0_count(output_path, protected_legacy_dir)
        estimate = estimate_scale(sample_rate_hz, exact_window_count)
        if estimate.get("estimate_warning"):
            warning_codes.append(str(estimate["estimate_warning"]))
            warnings.append(str(estimate["estimate_warning"]))

        task_id_channel = str(unique_channel) if unique_channel is not None else "ambiguous"
        task_id = f"{scene_id}__{prn}__ch{task_id_channel}__{EXPERIMENT_NAMESPACE}"
        if collision == "complete_existing":
            status = "completed_or_existing"
            status_reason = (
                "protected_reference_result_and_complete_existing"
                if protected
                else "complete_existing"
            )
            preflight_status = "not_applicable"
            execution_allowed = False
            priority_class = "protected_or_existing"
            priority_rank = 99
        elif protected:
            status = "skipped"
            status_reason = "protected_reference_result"
            preflight_status = "protected"
            execution_allowed = False
            priority_class = "protected_or_existing"
            priority_rank = 99
        elif collision != "absent":
            status = "completed_or_existing"
            status_reason = collision
            preflight_status = "not_applicable"
            execution_allowed = False
            priority_class = "protected_or_existing"
            priority_rank = 99
        elif hard_failures:
            status = "not_started"
            status_reason = "preflight_blocked"
            preflight_status = "blocked"
            execution_allowed = False
            priority_class = "manual_resolution" if (requires_manual or raw_warning_codes) else "blocked_preflight"
            priority_rank = 90
        else:
            status = "ready"
            status_reason = "ready_for_execution"
            preflight_status = "pass"
            execution_allowed = True
            if sample_rate_hz == REFERENCE_SAMPLE_RATE:
                priority_class = "pilot_10m"
                priority_rank = 10
            else:
                priority_class = "pilot_20m"
                priority_rank = 20

        row: Dict[str, Any] = {
            "plan_id": plan_id,
            "task_id": task_id,
            "scene_id": scene_id,
            "scene_role": scene_role,
            "prn": prn,
            "constellation": prn[0] if prn else "",
            "prn_number": as_int(prn[1:]) if len(prn) > 1 else None,
            "tracking_channel": unique_channel,
            "tracking_channel_candidates": ";".join(str(channel) for channel in candidates),
            "channel_resolution_status": (
                "unique" if len(candidates) == 1 else "ambiguous" if len(candidates) > 1 else "missing"
            ),
            "channel_resolution_method": "inventory_unique" if len(candidates) == 1 else "",
            "requires_manual_channel_selection": requires_manual,
            "signal_type": inventory_row.get("signal_type", ""),
            "sample_rate_hz": sample_rate_hz,
            "sample_rate_supported": sample_rate_hz in SUPPORTED_SAMPLE_RATES,
            "sample_rate_factor": estimate.get("sample_rate_factor"),
            "raw_storage_mode": inventory_row.get("raw_storage_mode", ""),
            "raw_path": raw_path or "",
            "tracking_path": tracking_path or "",
            "tracking_candidate_paths": ";".join(str(path) for path in tracking_candidates),
            "telemetry_path": telemetry_path or "",
            "telemetry_candidate_paths": ";".join(str(path) for path in telemetry_candidates),
            "navigation_path": navigation_path or "",
            "trajectory_path": trajectory_path or "",
            "satellite_timeseries_path": satellite_timeseries_path,
            "satellite_summary_path": satellite_summary_path,
            "metadata_path": metadata_path,
            "raw_exists": infos.get("raw_path", {}).get("exists", False),
            "tracking_exists": infos.get("tracking_path", {}).get("exists", False),
            "telemetry_exists": infos.get("telemetry_path", {}).get("exists", False),
            "navigation_exists": infos.get("navigation_path", {}).get("exists", False),
            "trajectory_exists": infos.get("trajectory_path", {}).get("exists", False),
            "satellite_timeseries_exists": infos.get("satellite_timeseries_path", {}).get("exists", False),
            "satellite_summary_exists": infos.get("satellite_summary_path", {}).get("exists", False),
            "metadata_exists": infos.get("metadata_path", {}).get("exists", False),
            "raw_size_bytes": infos.get("raw_path", {}).get("size_bytes"),
            "tracking_size_bytes": infos.get("tracking_path", {}).get("size_bytes"),
            "telemetry_size_bytes": infos.get("telemetry_path", {}).get("size_bytes"),
            "navigation_size_bytes": infos.get("navigation_path", {}).get("size_bytes"),
            "trajectory_size_bytes": infos.get("trajectory_path", {}).get("size_bytes"),
            "satellite_geometry_prn": geometry_has_prn,
            "geometry_prns_inventory": ";".join(sorted(geometry_prns_inventory)),
            "geometry_prns_summary": ";".join(sorted(geometry_prns_summary)),
            "output_path": output_path,
            "output_collision_status": collision,
            "existing_result_status": collision if collision != "absent" else "none",
            "estimated_valid_nav_symbols": estimate.get("estimated_valid_nav_symbols"),
            "estimated_40ms_windows_low": estimate.get("estimated_40ms_windows_low"),
            "estimated_40ms_windows_typical": estimate.get("estimated_40ms_windows_typical"),
            "estimated_40ms_windows_high": estimate.get("estimated_40ms_windows_high"),
            "estimated_stage1_windows_low": estimate.get("estimated_stage1_windows_low"),
            "estimated_stage1_windows_typical": estimate.get("estimated_stage1_windows_typical"),
            "estimated_stage1_windows_high": estimate.get("estimated_stage1_windows_high"),
            "estimated_stage2_candidates_low": estimate.get("estimated_stage2_candidates_low"),
            "estimated_stage2_candidates_typical": estimate.get("estimated_stage2_candidates_typical"),
            "estimated_stage2_candidates_high": estimate.get("estimated_stage2_candidates_high"),
            "estimated_stage2_model_evaluations_low": estimate.get("estimated_stage2_model_evaluations_low"),
            "estimated_stage2_model_evaluations_typical": estimate.get("estimated_stage2_model_evaluations_typical"),
            "estimated_stage2_model_evaluations_high": estimate.get("estimated_stage2_model_evaluations_high"),
            "workload_units_low": estimate.get("workload_units_low"),
            "workload_units_typical": estimate.get("workload_units_typical"),
            "workload_units_high": estimate.get("workload_units_high"),
            "estimate_method": estimate.get("estimate_method", ""),
            "estimate_confidence": estimate.get("estimate_confidence", ""),
            "pipeline_entrypoint": "scripts/sage_pipeline/run_nav_sage_pipeline.m",
            "pipeline_version": "Pipeline V3 (project record; not a run_context field)",
            "experiment_namespace": EXPERIMENT_NAMESPACE,
            "parameter_set_id": "not_recorded_dry_run",
            "pipeline_sha256": sha256_file(pipeline_path),
            "preflight_status": preflight_status,
            "hard_gate_failures": ";".join(sorted(set(hard_failures))),
            "warning_codes": ";".join(sorted(set(warning_codes))),
            "warnings": ";".join(sorted(set(warnings))),
            "execution_allowed": execution_allowed,
            "priority_class": priority_class,
            "priority_rank": priority_rank,
            "status": status,
            "status_reason": status_reason,
            "attempt": 0,
            "db_ingestion_status": "not_applicable",
            "context_version": "",
            "run_created_at_utc": "",
            "metadata_scene_match": metadata.get("scene_id", "") in {"", scene_id},
            "metadata_role": metadata.get("scene_role", ""),
            "inventory_scene_sage_status": inventory_row.get("sage_results_status", ""),
            "reference_report_path": reference_report_path,
        }
        tasks.append(row)
    return tasks


def task_fieldnames() -> List[str]:
    return [
        "plan_id",
        "task_id",
        "scene_id",
        "scene_role",
        "prn",
        "constellation",
        "prn_number",
        "tracking_channel",
        "tracking_channel_candidates",
        "channel_resolution_status",
        "channel_resolution_method",
        "requires_manual_channel_selection",
        "signal_type",
        "sample_rate_hz",
        "sample_rate_supported",
        "sample_rate_factor",
        "raw_storage_mode",
        "raw_path",
        "tracking_path",
        "tracking_candidate_paths",
        "telemetry_path",
        "telemetry_candidate_paths",
        "navigation_path",
        "trajectory_path",
        "satellite_timeseries_path",
        "satellite_summary_path",
        "metadata_path",
        "raw_exists",
        "tracking_exists",
        "telemetry_exists",
        "navigation_exists",
        "trajectory_exists",
        "satellite_timeseries_exists",
        "satellite_summary_exists",
        "metadata_exists",
        "raw_size_bytes",
        "tracking_size_bytes",
        "telemetry_size_bytes",
        "navigation_size_bytes",
        "trajectory_size_bytes",
        "satellite_geometry_prn",
        "geometry_prns_inventory",
        "geometry_prns_summary",
        "output_path",
        "output_collision_status",
        "existing_result_status",
        "estimated_valid_nav_symbols",
        "estimated_40ms_windows_low",
        "estimated_40ms_windows_typical",
        "estimated_40ms_windows_high",
        "estimated_stage1_windows_low",
        "estimated_stage1_windows_typical",
        "estimated_stage1_windows_high",
        "estimated_stage2_candidates_low",
        "estimated_stage2_candidates_typical",
        "estimated_stage2_candidates_high",
        "estimated_stage2_model_evaluations_low",
        "estimated_stage2_model_evaluations_typical",
        "estimated_stage2_model_evaluations_high",
        "workload_units_low",
        "workload_units_typical",
        "workload_units_high",
        "estimate_method",
        "estimate_confidence",
        "pipeline_entrypoint",
        "pipeline_version",
        "experiment_namespace",
        "parameter_set_id",
        "pipeline_sha256",
        "preflight_status",
        "hard_gate_failures",
        "warning_codes",
        "warnings",
        "execution_allowed",
        "priority_class",
        "priority_rank",
        "status",
        "status_reason",
        "attempt",
        "db_ingestion_status",
        "context_version",
        "run_created_at_utc",
        "metadata_scene_match",
        "metadata_role",
        "inventory_scene_sage_status",
        "reference_report_path",
    ]


def write_csv(path: Path, rows: Iterable[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: clean(row.get(field)) for field in fieldnames})


def summarize_tasks(tasks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    status_counts = Counter(str(row.get("status", "")) for row in tasks)
    preflight_counts = Counter(str(row.get("preflight_status", "")) for row in tasks)
    rate_counts = Counter(clean(row.get("sample_rate_hz")) for row in tasks)
    priority_counts = Counter(str(row.get("priority_class", "")) for row in tasks)
    collision_counts = Counter(str(row.get("output_collision_status", "")) for row in tasks)
    scene_counts = Counter(str(row.get("scene_id", "")) for row in tasks)
    total_low = sum(float(row.get("workload_units_low") or 0) for row in tasks)
    total_typical = sum(float(row.get("workload_units_typical") or 0) for row in tasks)
    total_high = sum(float(row.get("workload_units_high") or 0) for row in tasks)
    return {
        "task_count": len(tasks),
        "scene_count": len(scene_counts),
        "status_counts": dict(status_counts),
        "preflight_counts": dict(preflight_counts),
        "sample_rate_task_counts": dict(rate_counts),
        "priority_counts": dict(priority_counts),
        "output_collision_counts": dict(collision_counts),
        "workload_units": {
            "low": round(total_low, 3),
            "typical": round(total_typical, 3),
            "high": round(total_high, 3),
        },
        "multi_channel_count": sum(
            1 for row in tasks if as_bool(row.get("requires_manual_channel_selection"))
        ),
        "warning_task_count": sum(1 for row in tasks if row.get("warning_codes")),
        "blocked_task_count": sum(
            1 for row in tasks if str(row.get("preflight_status")) == "blocked"
        ),
        "execution_allowed_count": sum(
            1 for row in tasks if as_bool(row.get("execution_allowed"))
        ),
    }


def markdown_table(rows: Sequence[Dict[str, Any]], columns: Sequence[Tuple[str, str]]) -> List[str]:
    lines = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in rows:
        lines.append(
            "| " + " | ".join(clean(row.get(key)).replace("|", "\\|") for key, _ in columns) + " |"
        )
    return lines


def write_report(
    path: Path,
    plan_id: str,
    project_root: Path,
    inventory_path: Path,
    design_path: Path,
    pipeline_path: Path,
    reference_report_path: Path,
    consistency_issues: Sequence[str],
    tasks: Sequence[Dict[str, Any]],
    manifest_path: Path,
    issues_path: Path,
) -> None:
    summary = summarize_tasks(tasks)
    lines: List[str] = []
    lines.append("# Batch SAGE Dry-Run Plan Report")
    lines.append("")
    lines.append(f"- Plan ID: `{plan_id}`")
    lines.append(f"- Generated UTC: `{utc_now().isoformat()}`")
    lines.append(f"- Project root: `{project_root}`")
    lines.append(f"- Inventory: `{inventory_path}`")
    lines.append(f"- Design document: `{design_path}`")
    lines.append(f"- Pipeline entrypoint: `{pipeline_path}`")
    lines.append(f"- Reference report: `{reference_report_path}`")
    lines.append("")
    lines.append("> This is a read-only planning result. No MATLAB process or SAGE stage was run.")
    lines.append("> This report does not authorize execution of any task.")
    lines.append("")

    lines.append("## 1. Project consistency check")
    lines.append("")
    if consistency_issues:
        lines.append("`blocked`")
        for issue in consistency_issues:
            lines.append(f"- `{issue}`")
    else:
        lines.append("`pass`: required project directories, design documents, inventory and pipeline entrypoint were found.")
    lines.append("")

    lines.append("## 2. Plan summary")
    lines.append("")
    summary_rows = [
        {"metric": "Scene count", "value": summary["scene_count"]},
        {"metric": "Scene-PRN logical task count", "value": summary["task_count"]},
        {"metric": "Execution allowed after preflight", "value": summary["execution_allowed_count"]},
        {"metric": "Preflight blocked", "value": summary["blocked_task_count"]},
        {"metric": "Multi-channel/manual selection", "value": summary["multi_channel_count"]},
        {"metric": "Tasks with warnings (including estimate warnings)", "value": summary["warning_task_count"]},
    ]
    lines.extend(markdown_table(summary_rows, [("metric", "Metric"), ("value", "Value")]))
    lines.append("")
    lines.append("Status counts:")
    for key, value in sorted(summary["status_counts"].items()):
        lines.append(f"- `{key}`: {value}")
    lines.append("")
    lines.append("Sample-rate task counts:")
    for key, value in sorted(summary["sample_rate_task_counts"].items()):
        lines.append(f"- `{key or 'unknown'} Hz`: {value}")
    lines.append("")
    lines.append(
        "Relative workload units (not wall-clock minutes): "
        f"low `{format_number(summary['workload_units']['low'])}`, "
        f"typical `{format_number(summary['workload_units']['typical'])}`, "
        f"high `{format_number(summary['workload_units']['high'])}`."
    )
    lines.append("")

    lines.append("## 3. Protected, existing and manual-resolution tasks")
    lines.append("")
    protected_or_existing = [
        row
        for row in tasks
        if row.get("status") in {"skipped", "completed_or_existing"}
    ]
    if protected_or_existing:
        lines.extend(
            markdown_table(
                protected_or_existing,
                [
                    ("scene_id", "Scene"),
                    ("prn", "PRN"),
                    ("tracking_channel_candidates", "Channel candidates"),
                    ("status", "Status"),
                    ("status_reason", "Reason"),
                    ("output_collision_status", "Output"),
                ],
            )
        )
    else:
        lines.append("No protected or existing task found.")
    lines.append("")

    manual_rows = [
        row
        for row in tasks
        if row.get("requires_manual_channel_selection") or row.get("hard_gate_failures")
    ]
    lines.append("Manual/blocking task details:")
    lines.append("")
    if manual_rows:
        lines.extend(
            markdown_table(
                manual_rows,
                [
                    ("scene_id", "Scene"),
                    ("prn", "PRN"),
                    ("tracking_channel_candidates", "Candidates"),
                    ("hard_gate_failures", "Blocking codes"),
                    ("warning_codes", "Warning codes"),
                    ("status", "Status"),
                ],
            )
        )
    else:
        lines.append("None.")
    lines.append("")

    lines.append("## 4. Ready queue estimate")
    lines.append("")
    ready_rows = sorted(
        [row for row in tasks if row.get("status") == "ready"],
        key=lambda row: (
            as_int(row.get("priority_rank")) or 999,
            float(row.get("workload_units_typical") or 1e30),
            str(row.get("scene_id")),
            str(row.get("prn")),
        ),
    )
    if ready_rows:
        lines.extend(
            markdown_table(
                ready_rows,
                [
                    ("priority_class", "Priority"),
                    ("scene_id", "Scene"),
                    ("prn", "PRN"),
                    ("tracking_channel", "Ch."),
                    ("sample_rate_hz", "Hz"),
                    ("estimated_40ms_windows_typical", "40 ms typical"),
                    ("estimated_stage2_candidates_typical", "Stage2 typical"),
                    ("estimated_stage2_model_evaluations_typical", "Stage2 fits"),
                    ("workload_units_typical", "Work units"),
                ],
            )
        )
    else:
        lines.append("No task is ready. Resolve blockers or inspect the input paths first.")
    lines.append("")

    lines.append("## 5. Estimation rules")
    lines.append("")
    lines.append("- Existing Stage0 windows are recorded as `existing_stage0_exact` only for already existing result directories.")
    lines.append("- New 10.23 MHz tasks use the low-confidence reference prior of 319–1175 40 ms windows; this is not an observed count.")
    lines.append("- New 20.46 MHz tasks have no current project reference-duration baseline and therefore keep window and Stage2 estimates empty until a read-only coverage estimator or pilot provides evidence.")
    lines.append("- Stage1 estimate equals the estimated 40 ms window count; Stage2 model evaluations equal candidate estimate × 4.")
    lines.append("- Stage2 candidate ratios use the reference-derived 4.4% / 8.2% / 29.8% low/typical/high prior and must be recalibrated after the first standard-scene pilot.")
    lines.append("")

    lines.append("## 6. Output artifacts")
    lines.append("")
    lines.append(f"- Plan CSV: `{path.parent / 'batch_sage_plan.csv'}`")
    lines.append(f"- Manifest: `{manifest_path}`")
    lines.append(f"- Issues: `{issues_path}`")
    lines.append(f"- This report: `{path}`")
    lines.append("")
    lines.append("The output directory is outside all scene directories. No SAGE result directory was created or modified by this dry-run.")
    lines.append("")
    lines.append("## Current Status")
    lines.append("")
    lines.append("The plan is generated for review only. The next safe action is to inspect blocked input/channel records and select a small pilot explicitly; do not call MATLAB directly from this report.")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_issues(path: Path, tasks: Sequence[Dict[str, Any]]) -> None:
    rows: List[Dict[str, Any]] = []
    for task in tasks:
        for code in [
            value for value in str(task.get("hard_gate_failures", "")).split(";") if value
        ]:
            rows.append(
                {
                    "plan_id": task.get("plan_id"),
                    "task_id": task.get("task_id"),
                    "scene_id": task.get("scene_id"),
                    "prn": task.get("prn"),
                    "severity": "blocking",
                    "issue_code": code,
                    "message": task.get("warnings", ""),
                    "resolution_status": "unresolved",
                }
            )
        for code in [value for value in str(task.get("warning_codes", "")).split(";") if value]:
            rows.append(
                {
                    "plan_id": task.get("plan_id"),
                    "task_id": task.get("task_id"),
                    "scene_id": task.get("scene_id"),
                    "prn": task.get("prn"),
                    "severity": "warning",
                    "issue_code": code,
                    "message": task.get("warnings", ""),
                    "resolution_status": "review",
                }
            )
    fields = [
        "plan_id",
        "task_id",
        "scene_id",
        "prn",
        "severity",
        "issue_code",
        "message",
        "resolution_status",
    ]
    write_csv(path, rows, fields)


def create_plan_directory(output_root: Path, plan_id: str) -> Path:
    base = output_root / plan_id
    candidate = base
    suffix = 1
    while candidate.exists():
        candidate = output_root / f"{plan_id}_{suffix:02d}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def build_manifest(
    plan_id: str,
    project_root: Path,
    inventory_path: Path,
    design_path: Path,
    batch_design_path: Path,
    pipeline_path: Path,
    reference_report_path: Path,
    consistency_issues: Sequence[str],
    summary: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "estimate_model_version": ESTIMATE_MODEL_VERSION,
        "plan_id": plan_id,
        "generated_at_utc": utc_now().isoformat(),
        "project_root": str(project_root),
        "output_dir": str(output_dir),
        "execution_mode": "dry_run_only",
        "sage_execution_performed": False,
        "matlab_invoked": False,
        "source_files": {
            "inventory": {"path": str(inventory_path), "sha256": sha256_file(inventory_path)},
            "database_design": {"path": str(design_path), "sha256": sha256_file(design_path)},
            "batch_design": {"path": str(batch_design_path), "sha256": sha256_file(batch_design_path)},
            "pipeline": {"path": str(pipeline_path), "sha256": sha256_file(pipeline_path)},
            "reference_report": {"path": str(reference_report_path), "sha256": sha256_file(reference_report_path)},
        },
        "project_consistency_issues": list(consistency_issues),
        "summary": summary,
        "protected_scene_policy": "scene_role=reference_scene is skipped and never executed by this planner",
        "output_policy": "existing nav_sage_v2/<PRN> is never overwritten",
        "notes": [
            "The planner reads inventory and input metadata only.",
            "No MATLAB/SAGE call is present in the dry-run path.",
            "Missing estimates are represented as null/empty fields with warnings.",
        ],
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    script_path = Path(__file__).resolve()
    default_root = script_path.parents[2]
    parser = argparse.ArgumentParser(description="Generate a read-only batch SAGE plan")
    parser.add_argument("--project-root", type=Path, default=default_root)
    parser.add_argument("--inventory", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    project_root = args.project_root.resolve()
    inventory_path = (args.inventory or project_root / "dataset" / "dataset_inventory.csv").resolve()
    output_root = (
        args.output_root
        or project_root / "dataset_generation_logs" / "batch_sage"
    ).resolve()
    design_path = project_root / "docs" / "MULTIPATH_EVENT_DATABASE_DESIGN.md"
    batch_design_path = project_root / "docs" / "BATCH_SAGE_DRY_RUN_DESIGN.md"
    pipeline_path = project_root / "scripts" / "sage_pipeline" / "run_nav_sage_pipeline.m"
    reference_report_path = (
        project_root
        / "scenes"
        / "F1023_V70_D0117_P2"
        / "sage_results"
        / "reference_scene_final_validation_report.md"
    )

    consistency_issues = check_project_consistency(project_root)
    if consistency_issues:
        raise RuntimeError("Project consistency check failed: " + "; ".join(consistency_issues))
    if not inventory_path.is_file():
        raise RuntimeError(f"Inventory does not exist: {inventory_path}")

    plan_id = f"batch_sage_dry_run_{utc_stamp()}"
    output_dir = create_plan_directory(output_root, plan_id)
    source_snapshot_path = output_dir / "source_inventory_snapshot.csv"
    plan_path = output_dir / "batch_sage_plan.csv"
    report_path = output_dir / "batch_sage_plan_report.md"
    manifest_path = output_dir / "batch_sage_plan_manifest.json"
    issues_path = output_dir / "batch_sage_plan_issues.csv"

    source_snapshot_path.write_bytes(inventory_path.read_bytes())
    inventory_rows = load_inventory(inventory_path)
    tasks: List[Dict[str, Any]] = []
    for inventory_row in inventory_rows:
        tasks.extend(
            make_task(
                project_root,
                inventory_row,
                plan_id,
                pipeline_path,
                reference_report_path,
            )
        )

    # Stable plan ordering: scene, PRN, then unique channel or ambiguity.
    tasks.sort(
        key=lambda row: (
            str(row.get("scene_id")),
            str(row.get("prn")),
            as_int(row.get("tracking_channel"))
            if as_int(row.get("tracking_channel")) is not None
            else 999,
        )
    )
    fields = task_fieldnames()
    write_csv(plan_path, tasks, fields)
    write_issues(issues_path, tasks)
    summary = summarize_tasks(tasks)
    manifest = build_manifest(
        plan_id,
        project_root,
        inventory_path,
        design_path,
        batch_design_path,
        pipeline_path,
        reference_report_path,
        consistency_issues,
        summary,
        output_dir,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report(
        report_path,
        plan_id,
        project_root,
        inventory_path,
        design_path,
        pipeline_path,
        reference_report_path,
        consistency_issues,
        tasks,
        manifest_path,
        issues_path,
    )

    print(f"plan_id={plan_id}")
    print(f"plan_dir={output_dir}")
    print(f"plan_csv={plan_path}")
    print(f"report_md={report_path}")
    print(f"manifest_json={manifest_path}")
    print(f"issues_csv={issues_path}")
    print(f"task_count={summary['task_count']}")
    print(f"execution_allowed_count={summary['execution_allowed_count']}")
    print(f"blocked_task_count={summary['blocked_task_count']}")
    print(f"multi_channel_count={summary['multi_channel_count']}")
    print(f"sage_execution_performed={manifest['sage_execution_performed']}")
    print(f"matlab_invoked={manifest['matlab_invoked']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
