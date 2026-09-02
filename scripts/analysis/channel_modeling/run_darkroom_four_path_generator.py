"""Run one immutable, new-only darkroom four-path generation request.

The runner consumes only frozen derived-model artifacts.  It never opens raw IQ,
tracking, telemetry, SAGE, MATLAB, or production output.  Validation is the
default; generation requires both ``--generate`` and an explicit confirmation.
"""

from __future__ import annotations

import argparse
import csv
import contextlib
import gzip
import hashlib
import io
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .darkroom_generator_core import (
        FINAL_COLUMNS,
        canonical_json_bytes,
        generate_simulation,
        load_frozen_models,
        load_generator_config,
        sha256_file,
        validate_generation_request,
    )
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_core import (
        FINAL_COLUMNS,
        canonical_json_bytes,
        generate_simulation,
        load_frozen_models,
        load_generator_config,
        sha256_file,
        validate_generation_request,
    )


FIXED_PYTHON = Path(r"D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe")
REQUEST_ROOT = "dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_requests"
RUN_ROOT = "dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_runs"
LOCK_NAME = ".darkroom_generator.active.lock"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value, raw


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve_project_relative(project_root: Path, relative: str) -> Path:
    root = project_root.resolve()
    target = (root / str(relative)).resolve()
    if not _is_within(target, root):
        raise ValueError(f"path escapes project root: {relative}")
    return target


def _backend_receipt() -> dict[str, Any]:
    import numpy as np
    import scipy

    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        np.__config__.show()
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "architecture": platform.architecture()[0],
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "numpy_config": output.getvalue().strip(),
    }


def _validate_namespace(project_root: Path, relative_namespace: str, run_id: str) -> Path:
    normalized = str(relative_namespace).replace("\\", "/")
    expected_prefix = RUN_ROOT + "/"
    if not normalized.startswith(expected_prefix):
        raise ValueError("output namespace is outside the generator run root")
    if normalized.split("/")[-1] != run_id or "/../" in f"/{normalized}/" or normalized.endswith("/.."):
        raise ValueError("unsafe output namespace")
    run_root = (project_root / RUN_ROOT).resolve()
    target = (project_root / normalized).resolve()
    if not _is_within(target, run_root) or target == run_root:
        raise ValueError("output namespace is not a request-specific run directory")
    if any(part.lower() in {"scenes", "sage_results", "_trash"} for part in target.relative_to(project_root.resolve()).parts):
        raise ValueError("protected namespace cannot be used for generation")
    return target


def _validate_request(project_root: Path, request_path: Path, expected_sha256: str) -> dict[str, Any]:
    request, raw = _read_json_bytes(request_path)
    actual_request_sha = hashlib.sha256(raw).hexdigest()
    if actual_request_sha.lower() != expected_sha256.lower():
        raise ValueError(f"request SHA-256 mismatch: {actual_request_sha} != {expected_sha256}")
    if raw != canonical_json_bytes(request):
        raise ValueError("request JSON is not in canonical frozen form")
    config_rel = str(request.get("generator_config_relative_path", ""))
    config_path = _resolve_project_relative(project_root, config_rel)
    config_sha = sha256_file(config_path)
    if config_sha.lower() != str(request.get("generator_config_sha256", "")).lower():
        raise ValueError("generator config hash mismatch")
    config = load_generator_config(config_path, project_root)
    validate_generation_request(request, config)
    output_relative = str(request.get("expected_output_namespace", request.get("output_namespace", "")))
    if output_relative != str(request.get("output_namespace", "")):
        raise ValueError("output namespace aliases do not match")
    output_dir = _validate_namespace(project_root, output_relative, str(request["request_id"]))
    models = load_frozen_models(project_root, config)
    expected_parents = {str(k): str(v) for k, v in dict(request.get("parent_artifacts", {})).items()}
    if expected_parents != dict(sorted(models.artifact_hashes.items())):
        raise ValueError("parent artifact provenance mismatch")
    current_source_hashes = {
        "scripts/analysis/channel_modeling/darkroom_generator_core.py": sha256_file(Path(__file__).with_name("darkroom_generator_core.py")),
        "scripts/analysis/channel_modeling/prepare_darkroom_generator_request.py": sha256_file(Path(__file__).with_name("prepare_darkroom_generator_request.py")),
        "scripts/analysis/channel_modeling/run_darkroom_four_path_generator.py": sha256_file(Path(__file__)),
    }
    declared_sources = dict(request.get("source_hashes", {}))
    if declared_sources != current_source_hashes:
        raise ValueError("generator source hash mismatch")
    protected = dict(request.get("protected_pipeline", {}))
    pipeline_path = _resolve_project_relative(project_root, str(protected.get("relative_path", "")))
    if sha256_file(pipeline_path).lower() != str(protected.get("sha256", "")).lower():
        raise ValueError("protected pipeline hash mismatch")
    backend = _backend_receipt()
    declared_backend = dict(request.get("backend", {}))
    if Path(sys.executable).resolve() != FIXED_PYTHON.resolve():
        raise ValueError(f"fixed Python mismatch: {sys.executable}")
    for key in ("python_executable", "python_version", "numpy_version", "scipy_version"):
        if str(backend.get(key)) != str(declared_backend.get(key)):
            raise ValueError(f"backend receipt mismatch: {key}")
    if output_dir.exists():
        raise FileExistsError(f"new_only output namespace already exists: {output_dir}")
    request_root = (project_root / REQUEST_ROOT).resolve()
    lock_path = request_root / LOCK_NAME
    return {
        "request": request,
        "request_raw": raw,
        "request_sha256": actual_request_sha,
        "config": config,
        "config_path": config_path,
        "models": models,
        "output_dir": output_dir,
        "lock_path": lock_path,
        "backend": backend,
        "pipeline_path": pipeline_path,
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not (value == value and abs(value) != float("inf")):
            raise ValueError("non-finite sidecar value")
        return format(value, ".17g")
    return str(value)


def _write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _csv_value(row.get(name)) for name in writer.fieldnames})


def _write_gzip_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=list(fieldnames), lineterminator="\n", extrasaction="raise")
                writer.writeheader()
                for row in rows:
                    writer.writerow({name: _csv_value(row.get(name)) for name in writer.fieldnames})


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_bytes(dict(value)).decode("utf-8"))


def _acquire_lock(lock_path: Path, request: Mapping[str, Any]) -> None:
    if lock_path.exists():
        raise RuntimeError(f"active generator lock exists: {lock_path}")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_bytes({"request_id": request["request_id"], "created_utc": _utc_now(), "pid": os.getpid()}).decode("utf-8"))


def _release_lock(lock_path: Path, request_id: str) -> None:
    if not lock_path.exists():
        return
    released = lock_path.with_name(f".darkroom_generator.released.{request_id}.lock")
    if released.exists():
        raise RuntimeError(f"released lock receipt already exists: {released}")
    os.rename(lock_path, released)


def _write_generation_report(path: Path, request: Mapping[str, Any], result: Any, receipt: Mapping[str, Any]) -> None:
    lines = [
        "# Darkroom Four-Path Generator v1 Preview",
        "",
        "This is a Python-only deterministic preview generated from frozen derived model artifacts.",
        "It is not a raw-IQ, MATLAB, SAGE, or production execution result.",
        "",
        f"- request_id: `{request['request_id']}`",
        f"- simulation_id: `{request['simulation_id']}`",
        f"- environment_class: `{request['environment_class']}`",
        f"- elevation_band: `{request['elevation_band']}`",
        f"- duration_ms: `{request['duration_ms']}`",
        f"- master_seed: `{request['master_seed']}`",
        f"- rows: `{len(result.final_rows)}`",
        f"- 40 ms blocks: `{result.support_summary['block_count']}`",
        f"- activation_mode: `{request['activation_mode']}`",
        "",
        "## Canonical table schema",
        "",
        "The CSV uses exactly this order:",
        "",
        "`" + "`, `".join(FINAL_COLUMNS) + "`",
        "",
        "Inactive NLOS slots use blank delay/Doppler/phase and amplitude `0`; this preview uses the explicit QA-only active stress mode so that all three NLOS slot formats are visible.",
        "",
        "## Support and assumption status",
        "",
        "```json",
        json.dumps(result.support_summary, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Execution policy",
        "",
        "- raw IQ read: false",
        "- MATLAB: false",
        "- SAGE: false",
        "- batch: false",
        "- gold labels used for generation: false",
        "",
        f"Receipt status: `{receipt.get('status')}`.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _generate(context: Mapping[str, Any]) -> dict[str, Any]:
    request = context["request"]
    output_dir: Path = context["output_dir"]
    output_dir.mkdir(parents=True)
    start = time.perf_counter()
    started_utc = _utc_now()
    result = generate_simulation(request=validate_generation_request(request, context["config"]), config=context["config"], models=context["models"])
    # Copy the byte-identical frozen request into the run namespace.
    (output_dir / "generation_request.json").write_bytes(context["request_raw"])
    (output_dir / "generation_request.sha256").write_text(context["request_sha256"] + "\n", encoding="ascii", newline="\n")
    _write_csv(output_dir / "darkroom_channel_parameters.csv", FINAL_COLUMNS, result.final_rows)
    block_fields = (
        "block_id", "block_start_ms", "block_end_ms", "NLOSPathID", "active",
        "RelativeDelay", "RelativeDoppler", "relative_amplitude_base", "path_status",
        "activation_mode", "occupancy_support_status", "multiplicity_support_status",
        "path_parameter_support_status", "prior_only", "phase_initial_rad", "assumption_status",
    )
    _write_csv(output_dir / "path_block_catalog.csv", block_fields, result.path_block_rows)
    timeline_fields = tuple(result.timeline_rows[0].keys()) if result.timeline_rows else ("simulation_id", "ms")
    _write_gzip_csv(output_dir / "receiver_timeline.csv.gz", timeline_fields, result.timeline_rows)
    stream_fields = ("scope_id", "stream_name", "seed_uint64", "derivation", "draw_count")
    _write_csv(output_dir / "random_stream_registry.csv", stream_fields, result.stream_rows)
    _write_json(output_dir / "support_summary.json", result.support_summary)
    data_files = sorted(path.name for path in output_dir.iterdir() if path.is_file())
    data_hashes = {name: sha256_file(output_dir / name) for name in data_files}
    manifest = {
        "manifest_schema_version": "darkroom-generator-manifest-1",
        "created_utc": _utc_now(),
        "request_id": request["request_id"],
        "request_sha256": context["request_sha256"],
        "generator_id": request["generator_id"],
        "generator_version": request["generator_version"],
        "output_namespace": request["output_namespace"],
        "row_count": len(result.final_rows),
        "block_count": result.support_summary["block_count"],
        "output_hashes": data_hashes,
        "gold_labels_used_for_generation": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
    }
    _write_json(output_dir / "generation_manifest.json", manifest)
    elapsed = time.perf_counter() - start
    receipt: dict[str, Any] = {
        "receipt_schema_version": "darkroom-generator-receipt-1",
        "status": "completed",
        "started_utc": started_utc,
        "ended_utc": _utc_now(),
        "elapsed_s": elapsed,
        "request_id": request["request_id"],
        "request_sha256": context["request_sha256"],
        "generator_config_sha256": request["generator_config_sha256"],
        "source_hashes": request["source_hashes"],
        "backend": context["backend"],
        "row_count": len(result.final_rows),
        "block_count": result.support_summary["block_count"],
        "output_files": sorted(path.name for path in output_dir.iterdir() if path.is_file()),
        "output_hashes": {path.name: sha256_file(path) for path in output_dir.iterdir() if path.is_file()},
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "gold_labels_used_for_generation": False,
    }
    _write_json(output_dir / "generation_receipt.json", receipt)
    _write_generation_report(output_dir / "generation_report.md", request, result, receipt)
    receipt["output_files"] = sorted(path.name for path in output_dir.iterdir() if path.is_file())
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--confirm-darkroom-generation", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[3]
    context = _validate_request(project_root, args.request.resolve(), args.expected_request_sha256)
    request = context["request"]
    if args.generate and not args.confirm_darkroom_generation:
        raise ValueError("--generate requires --confirm-darkroom-generation")
    if args.confirm_darkroom_generation and not args.generate:
        raise ValueError("--confirm-darkroom-generation requires --generate")
    validation = {
        "execution_eligible": True,
        "generation_requested": bool(args.generate),
        "matlab_invoked": False,
        "raw_iq_read": False,
        "request_id": request["request_id"],
        "simulation_id": request["simulation_id"],
        "environment_class": request["environment_class"],
        "elevation_band": request["elevation_band"],
        "duration_ms": request["duration_ms"],
        "master_seed": request["master_seed"],
        "expected_rows": int(request["duration_ms"]) * 4,
        "output_namespace": request["output_namespace"],
        "output_path": str(context["output_dir"]),
        "request_sha256": context["request_sha256"],
        "generator_config_sha256": request["generator_config_sha256"],
        "parent_artifact_count": len(request["parent_artifacts"]),
        "backend": context["backend"],
        "gold_labels_used_for_generation": False,
    }
    if not args.generate:
        print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    _acquire_lock(context["lock_path"], request)
    try:
        receipt = _generate(context)
        print(f"GENERATION_RECEIPT={context['output_dir'] / 'generation_receipt.json'}")
        print(f"ROWS={receipt['row_count']}")
        return 0
    finally:
        _release_lock(context["lock_path"], str(request["request_id"]))


if __name__ == "__main__":
    raise SystemExit(main())
