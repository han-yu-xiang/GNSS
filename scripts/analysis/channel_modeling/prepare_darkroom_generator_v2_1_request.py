"""Freeze an immutable request for the v2.1 all-positive NLOS generator."""

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
    from .darkroom_generator_v2_1_core import (
        BAND_SEQUENCE,
        V21_RUN_ROOT,
        canonical_json_bytes,
        load_frozen_v21_parent_models,
        load_v21_config,
        sha256_file,
        validate_v21_request,
    )
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_v2_1_core import (
        BAND_SEQUENCE,
        V21_RUN_ROOT,
        canonical_json_bytes,
        load_frozen_v21_parent_models,
        load_v21_config,
        sha256_file,
        validate_v21_request,
    )


FIXED_PYTHON = Path(r"D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe")
REQUEST_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_requests"
REQUEST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _within(path: Path, root: Path) -> bool:
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


def validate_request_payload_shape(payload: Mapping[str, Any]) -> None:
    if "elevation_band" in payload:
        raise ValueError("single elevation_band is forbidden; v2.1 requires all bands")
    if tuple(payload.get("elevation_bands", ())) != ("LOW", "MID", "HIGH"):
        raise ValueError("elevation_bands must be exactly LOW,MID,HIGH")
    if payload.get("nlos_activation_policy") != "ALL_THREE_SLOTS_ALWAYS_ACTIVE":
        raise ValueError("nlos_activation_policy must be ALL_THREE_SLOTS_ALWAYS_ACTIVE")
    if payload.get("all_nlos_slots_active") is not True:
        raise ValueError("all_nlos_slots_active must be true")
    if payload.get("conditional_multipath_scenario") is not True:
        raise ValueError("conditional_multipath_scenario must be true")
    if payload.get("inactive_slot_parameter_policy") != "NOT_APPLICABLE_ALL_SLOTS_ACTIVE":
        raise ValueError("inactive slot policy mismatch")
    if payload.get("new_only") is not True:
        raise ValueError("new_only must be true")
    for field_name in ("resume_allowed", "raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz", "gold_labels_used_for_generation"):
        if payload.get(field_name) is not False:
            raise ValueError(f"{field_name} must be false")


def _source_paths() -> dict[str, Path]:
    current = Path(__file__).resolve()
    return {
        "scripts/analysis/channel_modeling/darkroom_generator_v2_1_core.py": current.with_name("darkroom_generator_v2_1_core.py"),
        "scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_1_request.py": current,
        "scripts/analysis/channel_modeling/run_darkroom_generator_v2_1.py": current.with_name("run_darkroom_generator_v2_1.py"),
        "scripts/analysis/channel_modeling/audit_darkroom_generator_v2_1.py": current.with_name("audit_darkroom_generator_v2_1.py"),
    }


def build_v21_request_payload(
    *,
    project_root: Path,
    config_path: Path,
    request_id: str,
    simulation_id: str,
    environment: str,
    duration_ms: int,
    master_seed: int,
    lock_mapping_mode: str,
    request_purpose: str = "PREVIEW",
    output_namespace: str | None = None,
) -> dict[str, Any]:
    if not REQUEST_PATTERN.fullmatch(request_id):
        raise ValueError("request_id contains unsupported characters")
    project_root = project_root.resolve()
    config_path = config_path.resolve()
    if not _within(config_path, project_root):
        raise ValueError("v2.1 config must be inside project root")
    config = load_v21_config(config_path, project_root)
    models = load_frozen_v21_parent_models(project_root, config)
    output_namespace = output_namespace or f"{V21_RUN_ROOT}/{request_id}"
    output_rel = output_namespace.replace("\\", "/")
    run_root = (project_root / V21_RUN_ROOT).resolve()
    output_dir = (project_root / output_rel).resolve()
    if not _within(output_dir, run_root) or output_dir == run_root or output_rel.split("/")[-1] != request_id:
        raise ValueError("unsafe v2.1 output namespace")
    if output_dir.exists():
        raise FileExistsError(f"v2.1 output namespace already exists: {output_dir}")
    if Path(sys.executable).resolve() != FIXED_PYTHON.resolve():
        raise RuntimeError(f"fixed Python required: {FIXED_PYTHON}, got {sys.executable}")
    backend = _backend_receipt()
    source_paths = _source_paths()
    missing_sources = [name for name, path in source_paths.items() if not path.is_file()]
    if missing_sources:
        raise FileNotFoundError(f"v2.1 sources must exist before request freeze: {missing_sources}")
    parent_v2_config = config.source_payload["parent_v2_config"]
    parent_v2_core = config.source_payload["parent_v2_core"]
    payload: dict[str, Any] = {
        "request_schema_version": "darkroom-generator-request-2.1",
        "request_id": request_id,
        "simulation_id": simulation_id,
        "request_created_utc": _utc_now(),
        "request_purpose": request_purpose,
        "generator_id": config.model_id,
        "generator_version": config.generator_version,
        "schema_version": str(config.source_payload.get("schema_version", "darkroom-generator-schema-2.1")),
        "sample_rate_hz": config.sample_rate_hz,
        "environment_class": environment,
        "elevation_bands": list(config.elevation_bands),
        "duration_ms": int(duration_ms),
        "master_seed": int(master_seed),
        "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
        "all_nlos_slots_active": True,
        "conditional_multipath_scenario": True,
        "inactive_slot_parameter_policy": "NOT_APPLICABLE_ALL_SLOTS_ACTIVE",
        "lock_mapping_mode": lock_mapping_mode,
        "generator_config_relative_path": config_path.relative_to(project_root).as_posix(),
        "generator_config_sha256": sha256_file(config_path),
        "parent_v2_config_sha256": str(parent_v2_config["sha256"]),
        "parent_v2_core_sha256": str(parent_v2_core["sha256"]),
        "parent_model_manifest_sha256": str(config.source_payload["parent_model_manifest_sha256"]),
        "parent_artifacts": dict(sorted(models.artifact_hashes.items())),
        "protected_pipeline": dict(config.source_payload["protected_pipeline"]),
        "source_hashes": {name: sha256_file(path) for name, path in source_paths.items()},
        "backend": backend,
        "output_namespace": output_rel,
        "expected_output_namespace": output_rel,
        "new_only": True,
        "resume_allowed": False,
        "gold_labels_used_for_generation": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "process_20_46_mhz": False,
        "execution_policy": dict(config.source_payload["execution_policy"]),
        "band_order": [list(item) for item in BAND_SEQUENCE],
        "rows_per_millisecond": 12,
    }
    validate_request_payload_shape(payload)
    validate_v21_request(payload, config)
    return payload


def canonical_request_bytes(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(dict(payload))


def write_v21_request_namespace(request_dir: Path, payload: Mapping[str, Any]) -> tuple[Path, str]:
    request_dir = request_dir.resolve()
    if request_dir.exists():
        raise FileExistsError(f"request namespace already exists: {request_dir}")
    request_dir.mkdir(parents=True)
    request_path = request_dir / "generation_request.json"
    request_path.write_bytes(canonical_request_bytes(payload))
    request_sha = sha256_file(request_path)
    (request_dir / "generation_request.sha256").write_text(request_sha + "\n", encoding="ascii", newline="\n")
    return request_path, request_sha


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--simulation-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--duration-ms", type=int, required=True)
    parser.add_argument("--master-seed", type=int, required=True)
    parser.add_argument("--lock-mapping-mode", default="EMPIRICAL_DIAGNOSTIC_PROXY")
    parser.add_argument("--request-purpose", default="PREVIEW")
    parser.add_argument("--request-dir", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project_root = args.project_root.resolve()
    request_dir = args.request_dir.resolve()
    request_root = (project_root / REQUEST_ROOT).resolve()
    if not _within(request_dir, request_root) or request_dir.parent != request_root or request_dir.name != args.request_id:
        raise ValueError("request_dir must be a new direct child of the v2.1 request root")
    payload = build_v21_request_payload(
        project_root=project_root,
        config_path=args.config,
        request_id=args.request_id,
        simulation_id=args.simulation_id,
        environment=args.environment,
        duration_ms=args.duration_ms,
        master_seed=args.master_seed,
        lock_mapping_mode=args.lock_mapping_mode,
        request_purpose=args.request_purpose,
    )
    if args.validate_only:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    request_path, request_sha = write_v21_request_namespace(request_dir, payload)
    print(f"GENERATION_REQUEST={request_path}")
    print(f"REQUEST_SHA256={request_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

