#!/usr/bin/env python3
"""Prepare one immutable new-only Rain task request for a not-started task.

This preparer is intentionally separate from the historical-artifact fresh
rerun preparer.  It admits only an exact checklist row whose status is
``NOT_STARTED`` and writes a versioned output leaf that is compatible with the
already validated r4 fresh Rain entry and wrapper.  It never invokes MATLAB,
SAGE, or reads raw IQ samples; a formal request records a byte hash of the raw
file for executor preflight.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ``python path/to/script.py`` places the script directory, rather than the
# project root, first on sys.path.  Add only this fixed project root so the
# shared preparer helpers remain importable without requiring installation.
_SCRIPT_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_SCRIPT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_PROJECT_ROOT))

from scripts.sage_pipeline.rain import prepare_rain_sage_fresh_request as fresh


PROJECT_ROOT = _SCRIPT_PROJECT_ROOT
CHECKLIST_RELATIVE = Path(
    "dataset_generation_logs/darkroom_channel_emulation/"
    "rain_final_planning_20260827/rain_sage_9_task_checklist.csv"
)
REQUEST_ROOT = PROJECT_ROOT / "dataset_generation_logs" / "darkroom_channel_emulation" / "rain_sage_task_requests_20260829"
OUTPUT_NAMESPACE_NAME = "rain_sage_rerun_v1_20260827_r4"


def _absolute(project_root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def _load_checklist(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty Rain checklist: {path}")
    return rows


def expected_output_namespace(project_root: Path, scene_id: str, prn: str) -> Path:
    return (
        _absolute(project_root, ".") / "scenes" / scene_id / "sage_results"
        / OUTPUT_NAMESPACE_NAME / prn
    )


def resolve_not_started_task(
    project_root: Path, scene_id: str, prn: str, channel: int
) -> dict[str, Any]:
    root = _absolute(project_root, ".")
    checklist_path = root / CHECKLIST_RELATIVE
    rows = _load_checklist(checklist_path)
    matches = [
        row
        for row in rows
        if row.get("scene_id") == scene_id
        and row.get("prn") == prn
        and int(row.get("tracking_channel", "-1")) == int(channel)
    ]
    if len(matches) != 1:
        raise ValueError(
            "expected exactly one frozen NOT_STARTED task, "
            f"found {len(matches)} for {scene_id}/{prn}/ch{channel}"
        )
    row = matches[0]
    if row.get("current_status") != "NOT_STARTED":
        raise ValueError(
            f"task status is not NOT_STARTED: {row.get('current_status', '')}"
        )
    if row.get("static_input_gate") != "PASS_STATIC_INPUT_GATE":
        raise ValueError(f"static input gate is not PASS for {scene_id}/{prn}")
    if row.get("output_exists_20260827", "").lower() == "true":
        raise ValueError("task already has a historical output; use the rerun workflow")
    if int(row.get("sample_rate_hz", "-1")) != 10_230_000:
        raise ValueError("Rain single-task request supports only 10.23 MHz")

    output_namespace = expected_output_namespace(root, scene_id, prn)
    if output_namespace.exists():
        raise FileExistsError(f"new output namespace already exists: {output_namespace}")
    return {
        "task_id": (
            f"rain_sage_single_task_v1__{scene_id}__{prn}__ch{int(channel)}"
            "__20260829_r4"
        ),
        "weather_condition": row["weather"],
        "scene_id": scene_id,
        "prn": prn,
        "tracking_channel": int(channel),
        "sample_rate_hz": int(row["sample_rate_hz"]),
        "source": checklist_path.name,
        "static_input_gate": row["static_input_gate"],
        "current_status": row["current_status"],
        "previous_output_namespace": row["expected_output_namespace"],
        "output_exists_at_preparation": False,
        "expected_window_count": int(row["telemetry_records"]) - 2,
        "expected_symbol_count": int(row["telemetry_records"]),
    }


def build_manifest(
    project_root: Path,
    *,
    scene_id: str,
    prn: str,
    channel: int,
    request_dir: Path | None = None,
    compute_raw_hash: bool = True,
) -> dict[str, Any]:
    root = _absolute(project_root, ".")
    task = resolve_not_started_task(root, scene_id, prn, channel)
    output_namespace = expected_output_namespace(root, scene_id, prn)
    inputs = fresh._metadata_and_inputs(root, task, compute_raw_hash=compute_raw_hash)
    sources = fresh._source_records(root)
    sources["single_task_request_preparer"] = fresh._file_record(Path(__file__))
    actual_request_dir = (
        _absolute(root, request_dir)
        if request_dir is not None
        else REQUEST_ROOT / task["task_id"]
    )
    created_utc = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    return {
        "schema_version": "rain-sage-fresh-rerun-request-v1",
        "request_class": "new_only_single_task_v1",
        "request_id": task["task_id"],
        "created_utc": created_utc,
        "project_root": str(root),
        "task": task,
        "inputs": inputs,
        "sources": sources,
        "output": {
            "namespace": str(output_namespace),
            "output_namespace_name": OUTPUT_NAMESPACE_NAME,
            "new_only": True,
            "resume_allowed": False,
        },
        "execution": {
            "execution_mode": "new_only",
            "new_only": True,
            "resume_allowed": False,
            "max_parallel_matlab": 1,
            "normal_user_identity": "TJ-CHANNEL\\Jing_",
            "matlab_executable": r"D:\Program Files\Matlab\bin\matlab.exe",
            "fresh_entry_function": "run_rain_sage_fresh_task",
        },
        "provenance": {
            "gold_labels_used_for_selection": False,
            "raw_iq_content_processed_by_preparer": False,
            "request_purpose": "first_execution_for_not_started_rain_task",
            "checklist_status_at_preparation": task["current_status"],
            "previous_output_namespace_preserved": task["previous_output_namespace"],
            "previous_output_exists_at_preparation": False,
            "source_checklist": str(root / CHECKLIST_RELATIVE),
        },
        "request_paths": {
            "request_directory": str(actual_request_dir),
            "execution_receipt_directory": str(actual_request_dir / "receipts"),
        },
    }


def write_request(manifest: dict[str, Any], request_dir: Path) -> tuple[Path, str]:
    request_dir = Path(request_dir).resolve()
    if request_dir.exists():
        raise FileExistsError(f"request namespace already exists: {request_dir}")
    payload = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    request_dir.mkdir(parents=True)
    manifest_path = request_dir / "execution_manifest.json"
    with manifest_path.open("xb") as handle:
        handle.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    with (request_dir / "execution_manifest.sha256").open("xb") as handle:
        handle.write(f"{digest}  execution_manifest.json\n".encode("ascii"))
    return manifest_path, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--prn", required=True)
    parser.add_argument("--channel", type=int, required=True)
    parser.add_argument("--request-dir", type=Path, default=None)
    args = parser.parse_args()
    manifest = build_manifest(
        args.project_root,
        scene_id=args.scene,
        prn=args.prn,
        channel=args.channel,
        request_dir=args.request_dir,
        compute_raw_hash=True,
    )
    request_dir = (
        Path(args.request_dir)
        if args.request_dir is not None
        else REQUEST_ROOT / manifest["request_id"]
    )
    path, digest = write_request(manifest, request_dir)
    print(f"REQUEST_MANIFEST={path}")
    print(f"REQUEST_MANIFEST_SHA256={digest}")
    print(f"OUTPUT_NAMESPACE={manifest['output']['namespace']}")
    print("EXECUTION_NOT_STARTED=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
