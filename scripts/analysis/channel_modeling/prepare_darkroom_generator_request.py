"""Prepare an immutable, new-only request for the darkroom generator.

This module only reads frozen model artifacts and writes a request namespace.
It never opens raw IQ, tracking, telemetry, SAGE output, or MATLAB files.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .darkroom_generator_core import (
        canonical_json_bytes,
        load_frozen_models,
        load_generator_config,
        sha256_file,
        validate_generation_request,
    )
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_core import (
        canonical_json_bytes,
        load_frozen_models,
        load_generator_config,
        sha256_file,
        validate_generation_request,
    )


FIXED_PYTHON = Path(r"D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe")
REQUEST_ROOT = "dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_requests"
RUN_ROOT = "dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_runs"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _relative_to_project(project_root: Path, path: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


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


def build_request_payload(
    *,
    project_root: Path,
    config_path: Path,
    request_id: str,
    simulation_id: str,
    environment: str,
    elevation_band: str,
    duration_ms: int,
    master_seed: int,
    activation_mode: str,
    lock_mapping_mode: str,
    stress_floor_linear: float | None,
    request_purpose: str,
    output_namespace: str,
) -> dict[str, Any]:
    if not REQUEST_ID_PATTERN.fullmatch(request_id):
        raise ValueError("request_id contains unsupported characters")
    if not simulation_id.strip():
        raise ValueError("simulation_id must be non-empty")
    project_root = project_root.resolve()
    config_path = config_path.resolve()
    if not _is_within(config_path, project_root):
        raise ValueError("config must be inside project root")
    config = load_generator_config(config_path, project_root)
    models = load_frozen_models(project_root, config)
    config_rel = _relative_to_project(project_root, config_path)
    config_sha = sha256_file(config_path)
    run_root = (project_root / RUN_ROOT).resolve()
    expected_output = (project_root / output_namespace).resolve()
    if not _is_within(expected_output, run_root):
        raise ValueError("output namespace is outside the generator run root")
    if expected_output == run_root:
        raise ValueError("output namespace must name a request-specific directory")
    if output_namespace.replace("\\", "/").split("/")[-1] != request_id:
        raise ValueError("output namespace final component must equal request_id")
    if expected_output.exists():
        raise FileExistsError(f"new_only output namespace already exists: {expected_output}")
    if request_purpose not in {"PREVIEW", "QA", "STRESS", "PRODUCTION"}:
        raise ValueError("unsupported request_purpose")
    if activation_mode == "CONDITIONAL_ACTIVE_STRESS" and request_purpose not in {"QA", "STRESS"}:
        raise ValueError("active stress is restricted to QA/STRESS requests")
    backend = _backend_receipt()
    expected_python = FIXED_PYTHON.resolve()
    if Path(sys.executable).resolve() != expected_python:
        raise RuntimeError(f"fixed compiled Python required: {expected_python}, got {sys.executable}")
    source_hashes = {
        "scripts/analysis/channel_modeling/darkroom_generator_core.py": sha256_file(Path(__file__).with_name("darkroom_generator_core.py")),
        "scripts/analysis/channel_modeling/prepare_darkroom_generator_request.py": sha256_file(Path(__file__)),
        "scripts/analysis/channel_modeling/run_darkroom_four_path_generator.py": sha256_file(Path(__file__).with_name("run_darkroom_four_path_generator.py")) if Path(__file__).with_name("run_darkroom_four_path_generator.py").is_file() else None,
    }
    parent_artifacts = dict(sorted(models.artifact_hashes.items()))
    payload: dict[str, Any] = {
        "request_schema_version": "darkroom-generator-request-1",
        "request_id": request_id,
        "simulation_id": simulation_id,
        "request_created_utc": _utc_now(),
        "request_purpose": request_purpose,
        "generator_id": config.model_id,
        "generator_version": str(config.source_payload.get("generator_version", "")),
        "sample_rate_hz": int(config.source_payload.get("sample_rate_hz", 0)),
        "environment_class": environment,
        "elevation_band": elevation_band,
        "duration_ms": int(duration_ms),
        "master_seed": int(master_seed),
        "activation_mode": activation_mode,
        "lock_mapping_mode": lock_mapping_mode,
        "stress_floor_linear": stress_floor_linear,
        "generator_config_relative_path": config_rel,
        "generator_config_sha256": config_sha,
        "parent_artifacts": parent_artifacts,
        "protected_pipeline": dict(config.source_payload.get("protected_pipeline", {})),
        "source_hashes": source_hashes,
        "backend": backend,
        "output_namespace": output_namespace.replace("\\", "/"),
        "expected_output_namespace": output_namespace.replace("\\", "/"),
        "new_only": True,
        "resume_allowed": False,
        "gold_labels_used_for_generation": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "execution_policy": dict(config.source_payload.get("execution_policy", {})),
    }
    validate_generation_request(payload, config)
    if payload["source_hashes"]["scripts/analysis/channel_modeling/run_darkroom_four_path_generator.py"] is None:
        raise FileNotFoundError("runner must exist before freezing a request")
    return payload


def write_request_namespace(request_dir: Path, payload: Mapping[str, Any]) -> tuple[Path, str]:
    request_dir = request_dir.resolve()
    if request_dir.exists():
        raise FileExistsError(f"request namespace already exists: {request_dir}")
    request_bytes = canonical_json_bytes(dict(payload))
    request_dir.mkdir(parents=True)
    request_path = request_dir / "generation_request.json"
    sha_path = request_dir / "generation_request.sha256"
    request_path.write_bytes(request_bytes)
    request_sha = sha256_file(request_path)
    sha_path.write_text(request_sha + "\n", encoding="ascii", newline="\n")
    return request_path, request_sha


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--simulation-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--elevation-band", required=True)
    parser.add_argument("--duration-ms", type=int, required=True)
    parser.add_argument("--master-seed", type=int, required=True)
    parser.add_argument("--activation-mode", required=True)
    parser.add_argument("--lock-mapping-mode", required=True)
    parser.add_argument("--stress-floor-linear", type=float, default=None)
    parser.add_argument("--request-purpose", default="PREVIEW")
    parser.add_argument("--request-dir", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project_root = args.project_root.resolve()
    output_namespace = f"{RUN_ROOT}/{args.request_id}"
    payload = build_request_payload(
        project_root=project_root,
        config_path=args.config,
        request_id=args.request_id,
        simulation_id=args.simulation_id,
        environment=args.environment,
        elevation_band=args.elevation_band,
        duration_ms=args.duration_ms,
        master_seed=args.master_seed,
        activation_mode=args.activation_mode,
        lock_mapping_mode=args.lock_mapping_mode,
        stress_floor_linear=args.stress_floor_linear,
        request_purpose=args.request_purpose,
        output_namespace=output_namespace,
    )
    request_dir = args.request_dir.resolve()
    expected_root = (project_root / REQUEST_ROOT).resolve()
    if not _is_within(request_dir, expected_root) or request_dir.parent != expected_root:
        raise ValueError("request_dir must be a direct child of the declared request root")
    if request_dir.name != args.request_id:
        raise ValueError("request_dir final component must equal request_id")
    if args.validate_only:
        print(json.dumps({"validation_only": True, "request": payload, "request_dir": str(request_dir)}, ensure_ascii=False, indent=2))
        return 0
    request_path, request_sha = write_request_namespace(request_dir, payload)
    print(f"REQUEST_PATH={request_path}")
    print(f"REQUEST_SHA256={request_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
