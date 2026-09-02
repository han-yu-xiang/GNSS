"""Prepare one immutable fresh Rain SAGE execution request.

This module intentionally does not invoke MATLAB or read raw IQ samples.  The
optional raw SHA-256 is a byte hash only and is disabled by default for unit
tests; the command-line preparation path computes it unless --skip-raw-hash is
explicitly supplied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(r"E:\GNSS_Multipath_Project")
CHECKLIST_PATH = PROJECT_ROOT / "dataset_generation_logs" / "darkroom_channel_emulation" / "rain_final_planning_20260827" / "rain_sage_9_task_checklist.csv"
REQUEST_ROOT = PROJECT_ROOT / "dataset_generation_logs" / "darkroom_channel_emulation" / "rain_sage_rerun_requests_20260827"
RERUN_REVISION = "r4"
OUTPUT_NAMESPACE_NAME = f"rain_sage_rerun_v1_20260827_{RERUN_REVISION}"
PROTECTED_PRODUCTION_SHA256 = "bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c"


def _absolute(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def sha256_file(path: str | Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _file_record(path: Path, *, include_hash: bool = True) -> dict[str, Any]:
    path = _absolute(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    stat = path.stat()
    record: dict[str, Any] = {
        "path": str(path),
        "size_bytes": stat.st_size,
    }
    if include_hash:
        record["sha256"] = sha256_file(path)
    return record


def _load_checklist(path: Path = CHECKLIST_PATH) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty Rain task checklist: {path}")
    return rows


def resolve_task(project_root: Path, scene_id: str, prn: str, channel: int) -> dict[str, Any]:
    """Resolve an exact task from the frozen nine-task checklist."""

    root = _absolute(project_root)
    checklist = root / "dataset_generation_logs" / "darkroom_channel_emulation" / "rain_final_planning_20260827" / "rain_sage_9_task_checklist.csv"
    matches = [
        row
        for row in _load_checklist(checklist)
        if row.get("scene_id") == scene_id
        and row.get("prn") == prn
        and int(row.get("tracking_channel", "-1")) == int(channel)
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one frozen task, found {len(matches)} for {scene_id}/{prn}/ch{channel}")
    row = matches[0]
    if int(row["sample_rate_hz"]) != 10_230_000:
        raise ValueError("Rain fresh rerun supports only 10.23 MHz")
    if row.get("static_input_gate") != "PASS_STATIC_INPUT_GATE":
        raise ValueError(f"static input gate is not PASS for {scene_id}/{prn}")
    if row.get("output_exists_20260827", "").lower() != "true":
        raise ValueError("fresh rerun request is only for the explicitly selected existing-artifact replacement task")
    return {
        "task_id": f"rain_sage_fresh_rerun_v1__{scene_id}__{prn}__ch{int(channel)}__20260827_{RERUN_REVISION}",
        "weather_condition": row["weather"],
        "scene_id": scene_id,
        "prn": prn,
        "tracking_channel": int(channel),
        "sample_rate_hz": int(row["sample_rate_hz"]),
        "source": checklist.name,
        "static_input_gate": row["static_input_gate"],
        "previous_output_namespace": row["expected_output_namespace"],
    }


def expected_output_namespace(project_root: Path, scene_id: str, prn: str) -> Path:
    return _absolute(project_root) / "scenes" / scene_id / "sage_results" / OUTPUT_NAMESPACE_NAME / prn


def assert_output_namespace_absent(namespace: Path) -> None:
    namespace = Path(namespace)
    if namespace.exists():
        raise FileExistsError(f"fresh output namespace already exists: {namespace}")


def _metadata_and_inputs(root: Path, task: dict[str, Any], *, compute_raw_hash: bool) -> dict[str, Any]:
    scene_dir = root / "scenes" / task["scene_id"]
    metadata_path = scene_dir / "metadata.json"
    with metadata_path.open("r", encoding="utf-8-sig") as handle:
        metadata = json.load(handle)
    if metadata.get("scene_id") != task["scene_id"]:
        raise ValueError("metadata scene_id mismatch")
    if metadata.get("branch") != "darkroom_channel_emulation":
        raise ValueError("metadata branch mismatch")
    signal = metadata.get("signal", {})
    if int(signal.get("sample_rate_hz", -1)) != 10_230_000:
        raise ValueError("metadata sample rate mismatch")
    raw_value = metadata.get("raw_iq", {}).get("path")
    if not raw_value:
        raise ValueError("metadata.raw_iq.path is missing")
    raw_path = _absolute(raw_value)
    raw_record = _file_record(raw_path, include_hash=compute_raw_hash)
    raw_record["sha256_status"] = "COMPUTED" if compute_raw_hash else "NOT_COMPUTED_IN_UNIT_TEST"

    tracking_path = scene_dir / "gnss_sdr" / "tracking" / f"{task['scene_id']}_track_ch_{task['tracking_channel']}.mat"
    telemetry_path = scene_dir / "gnss_sdr" / "telemetry" / f"{task['scene_id']}_telemetry_ch_{task['tracking_channel']}.dat"
    navigation_path = scene_dir / "navigation" / "gps_ephemeris.xml"
    config_path = scene_dir / "gnss_sdr" / "config" / f"{task['scene_id']}.conf"
    observables_path = scene_dir / "gnss_sdr" / "observables" / f"{task['scene_id']}_observables.dat"
    input_files = {
        "metadata": _file_record(metadata_path),
        "raw_iq": raw_record,
        "tracking": _file_record(tracking_path),
        "telemetry": _file_record(telemetry_path),
        "navigation": _file_record(navigation_path),
        "gnss_sdr_config": _file_record(config_path),
        "observables": _file_record(observables_path),
    }
    return input_files


def _source_records(root: Path) -> dict[str, dict[str, Any]]:
    script_dir = root / "scripts" / "sage_pipeline" / "rain"
    paths = {
        "fresh_entry": script_dir / "run_rain_sage_fresh_task.m",
        "fresh_wrapper": script_dir / "Invoke-RainSageFreshTask.ps1",
        "request_preparer": script_dir / "prepare_rain_sage_fresh_request.py",
        "artifact_auditor": script_dir / "audit_rain_sage_task.py",
        "stage0_adapter": script_dir / "build_rain_stage0.m",
        "stage1_stage4": script_dir / "run_rain_sage_stage1_stage4.m",
        "configuration": script_dir / "default_rain_sage_configuration.m",
        "rain_entry_legacy": script_dir / "run_rain_sage_pipeline.m",
        "protected_production_entry": root / "scripts" / "sage_pipeline" / "run_nav_sage_pipeline.m",
    }
    result = {name: _file_record(path) for name, path in paths.items()}
    if result["protected_production_entry"]["sha256"].lower() != PROTECTED_PRODUCTION_SHA256:
        raise ValueError("protected production pipeline hash mismatch")
    return result


def build_manifest(
    project_root: Path,
    *,
    scene_id: str,
    prn: str,
    channel: int,
    request_dir: Path | None = None,
    compute_raw_hash: bool = True,
) -> dict[str, Any]:
    root = _absolute(project_root)
    task = resolve_task(root, scene_id, prn, channel)
    output_namespace = expected_output_namespace(root, scene_id, prn)
    assert_output_namespace_absent(output_namespace)
    inputs = _metadata_and_inputs(root, task, compute_raw_hash=compute_raw_hash)
    sources = _source_records(root)
    actual_request_dir = Path(request_dir) if request_dir is not None else REQUEST_ROOT / task["task_id"]
    manifest = {
        "schema_version": "rain-sage-fresh-rerun-request-v1",
        "request_id": task["task_id"],
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
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
            "previous_output_namespace_preserved": task["previous_output_namespace"],
            "rerun_disposition": "previous_artifact_abandoned_as_acceptance_evidence_but_preserved",
            "protected_production_pipeline_sha256": PROTECTED_PRODUCTION_SHA256,
        },
        "request_paths": {
            "request_directory": str(_absolute(actual_request_dir)),
            "execution_receipt_directory": str(_absolute(actual_request_dir) / "receipts"),
        },
    }
    return manifest


def _write_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def write_request(manifest: dict[str, Any], request_dir: Path) -> tuple[Path, str]:
    request_dir = _absolute(request_dir)
    if request_dir.exists():
        raise FileExistsError(f"request namespace already exists: {request_dir}")
    payload = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_path = request_dir / "execution_manifest.json"
    digest = hashlib.sha256(payload).hexdigest()
    _write_exclusive(manifest_path, payload)
    _write_exclusive(request_dir / "execution_manifest.sha256", (digest + "  execution_manifest.json\n").encode("ascii"))
    return manifest_path, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--scene", default="F1023_clear")
    parser.add_argument("--prn", default="G24")
    parser.add_argument("--channel", type=int, default=10)
    parser.add_argument("--request-dir", type=Path, default=None)
    parser.add_argument("--skip-raw-hash", action="store_true", help="only for an explicitly documented preparation pass")
    args = parser.parse_args()
    manifest = build_manifest(
        args.project_root,
        scene_id=args.scene,
        prn=args.prn,
        channel=args.channel,
        request_dir=args.request_dir,
        compute_raw_hash=not args.skip_raw_hash,
    )
    request_dir = Path(args.request_dir) if args.request_dir is not None else REQUEST_ROOT / manifest["request_id"]
    path, digest = write_request(manifest, request_dir)
    print(f"REQUEST_MANIFEST={path}")
    print(f"REQUEST_MANIFEST_SHA256={digest}")
    print(f"OUTPUT_NAMESPACE={manifest['output']['namespace']}")
    print("EXECUTION_NOT_STARTED=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
