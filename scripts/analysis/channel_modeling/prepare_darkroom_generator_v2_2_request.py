"""Freeze one immutable v2.2 paired-quality darkroom generation request.

The request builder is deliberately independent from the GNSS/SAGE execution
chain.  It reads frozen derived model metadata and scene metadata provenance,
but never opens raw IQ or invokes MATLAB, SAGE, or a production runner.
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
    from .darkroom_generator_v2_2_core import (
        BAND_SEQUENCE,
        ENVIRONMENTS,
        ELEVATION_BANDS,
        V22_REQUEST_ROOT,
        V22_RUN_ROOT,
        canonical_json_bytes,
        load_frozen_v22_parent_models,
        load_v22_config,
        sha256_file,
        validate_v22_request,
    )
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import (
        BAND_SEQUENCE,
        ENVIRONMENTS,
        ELEVATION_BANDS,
        V22_REQUEST_ROOT,
        V22_RUN_ROOT,
        canonical_json_bytes,
        load_frozen_v22_parent_models,
        load_v22_config,
        sha256_file,
        validate_v22_request,
    )


FIXED_PYTHON = Path(r"D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe")
REQUEST_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
PAIRING_IDS = {
    "Urban": "urban-quality-pair-20260827",
    "Special Reflective": "special-reflective-quality-pair-20260827",
    "Mountain/Valley": "mountain-valley-quality-pair-20260827",
    "Highway/Open": "highway-open-quality-pair-20260827",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve(project_root: Path, relative: str) -> Path:
    root = project_root.resolve()
    candidate = (root / str(relative)).resolve()
    if not _within(candidate, root):
        raise ValueError(f"path escapes project root: {relative}")
    return candidate


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


def source_paths() -> dict[str, Path]:
    """Return the complete v2.2 code provenance set used by all validators."""

    current = Path(__file__).resolve()
    return {
        "scripts/analysis/channel_modeling/darkroom_quality_profile_v2_2.py": current.with_name("darkroom_quality_profile_v2_2.py"),
        "scripts/analysis/channel_modeling/darkroom_generator_v2_2_core.py": current.with_name("darkroom_generator_v2_2_core.py"),
        "scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_2_request.py": current,
        "scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_2_matrix.py": current.with_name("prepare_darkroom_generator_v2_2_matrix.py"),
        "scripts/analysis/channel_modeling/run_darkroom_generator_v2_2.py": current.with_name("run_darkroom_generator_v2_2.py"),
        "scripts/analysis/channel_modeling/audit_darkroom_generator_v2_2.py": current.with_name("audit_darkroom_generator_v2_2.py"),
    }


def _metadata_provenance(project_root: Path, environment: str, scene_ids: list[str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for scene_id in scene_ids:
        relative = f"scenes/{scene_id}/metadata.json"
        path = _resolve(project_root, relative)
        if not path.is_file():
            raise FileNotFoundError(f"source scene metadata is missing: {path}")
        # Metadata is input provenance only.  It is intentionally not used to
        # infer a new environment label or to inspect any raw data.
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"scene metadata is not readable JSON: {path}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"scene metadata is not a JSON object: {path}")
        records.append({"scene_id": scene_id, "relative_path": relative, "sha256": sha256_file(path)})
    return records


def _output_path(project_root: Path, relative: str, request_id: str) -> Path:
    output = _resolve(project_root, relative)
    run_root = _resolve(project_root, V22_RUN_ROOT)
    if not _within(output, run_root) or output == run_root or output.parent != run_root or output.name != request_id:
        raise ValueError("unsafe v2.2 output namespace")
    if output.exists():
        raise FileExistsError(f"v2.2 output namespace already exists: {output}")
    return output


def validate_request_payload_shape(payload: Mapping[str, Any]) -> None:
    required = (
        "pairing_id", "quality_mode", "source_scene_ids", "source_scene_metadata",
        "parent_model_manifests", "parent_artifacts", "source_hashes", "backend",
        "protected_pipeline", "generator_config_sha256", "generator_config_relative_path",
    )
    missing = [name for name in required if name not in payload]
    if missing:
        raise ValueError(f"v2.2 request provenance fields missing: {','.join(missing)}")
    if payload.get("quality_mode") not in {"GOOD_TRACKED_BASELINE", "POOR_CONDITIONAL"}:
        raise ValueError("quality_mode is not frozen")
    if tuple(payload.get("elevation_bands", ())) != ELEVATION_BANDS:
        raise ValueError("elevation_bands must be exactly LOW,MID,HIGH")
    if payload.get("nlos_activation_policy") != "ALL_THREE_SLOTS_ALWAYS_ACTIVE":
        raise ValueError("nlos_activation_policy must be ALL_THREE_SLOTS_ALWAYS_ACTIVE")
    if payload.get("all_nlos_slots_active") is not True:
        raise ValueError("all_nlos_slots_active must be true")
    if payload.get("conditional_multipath_scenario") is not True:
        raise ValueError("conditional_multipath_scenario must be true")
    if payload.get("new_only") is not True:
        raise ValueError("new_only must be true")
    forbidden = ("resume_allowed", "raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz", "gold_labels_used_for_generation")
    for field_name in forbidden:
        if payload.get(field_name) is not False:
            raise ValueError(f"{field_name} must be false")


def build_v22_request_payload(
    *,
    project_root: Path,
    config_path: Path,
    request_id: str,
    environment: str,
    quality_mode: str,
    duration_ms: int,
    master_seed: int,
    pairing_id: str,
    simulation_id: str | None = None,
    request_purpose: str = "PILOT_20S",
    output_namespace: str | None = None,
) -> dict[str, Any]:
    if not REQUEST_PATTERN.fullmatch(request_id):
        raise ValueError("request_id contains unsupported characters")
    project_root = project_root.resolve()
    config_path = config_path.resolve()
    if not _within(config_path, project_root):
        raise ValueError("v2.2 config must be inside project root")
    config = load_v22_config(config_path, project_root)
    if environment not in ENVIRONMENTS:
        raise ValueError(f"unsupported environment: {environment}")
    if quality_mode not in {"GOOD_TRACKED_BASELINE", "POOR_CONDITIONAL"}:
        raise ValueError(f"unsupported quality mode: {quality_mode}")
    if pairing_id != PAIRING_IDS[environment]:
        raise ValueError("pairing_id does not match the frozen environment pairing")
    models, _parent_config = load_frozen_v22_parent_models(project_root, config)
    output_relative = output_namespace or f"{V22_RUN_ROOT}/{request_id}"
    _output_path(project_root, output_relative, request_id)
    if Path(sys.executable).resolve() != FIXED_PYTHON.resolve():
        raise RuntimeError(f"fixed Python required: {FIXED_PYTHON}, got {sys.executable}")
    backend = _backend_receipt()
    paths = source_paths()
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"v2.2 sources must exist before request freeze: {missing}")
    source_scene_ids = list(config.source_payload["source_scene_provenance"][environment])
    metadata_records = _metadata_provenance(project_root, environment, source_scene_ids)
    protected = dict(config.source_payload["protected_pipeline"])
    pipeline_path = _resolve(project_root, str(protected["relative_path"]))
    if not pipeline_path.is_file() or sha256_file(pipeline_path).lower() != str(protected["sha256"]).lower():
        raise ValueError("protected pipeline hash mismatch before request freeze")
    parent_manifests = dict(config.source_payload["parent_model_manifests"])
    payload: dict[str, Any] = {
        "request_schema_version": "darkroom-generator-request-2.2",
        "request_id": request_id,
        "simulation_id": simulation_id or request_id,
        "pairing_id": pairing_id,
        "request_created_utc": _utc_now(),
        "request_purpose": request_purpose,
        "generator_id": config.model_id,
        "generator_version": config.generator_version,
        "schema_version": str(config.source_payload.get("schema_version", "darkroom-generator-schema-2.2")),
        "sample_rate_hz": config.sample_rate_hz,
        "environment_class": environment,
        "source_scene_ids": source_scene_ids,
        "source_scene_metadata": metadata_records,
        "elevation_bands": list(config.elevation_bands),
        "duration_ms": int(duration_ms),
        "master_seed": int(master_seed),
        "quality_mode": quality_mode,
        "pre_event_guard_ms": int(config.source_payload["quality_policy"]["poor_mode"]["pre_event_guard_ms"]),
        "post_event_guard_ms": int(config.source_payload["quality_policy"]["poor_mode"]["post_event_guard_ms"]),
        "entry_ramp_cap_ms": int(config.source_payload["quality_policy"]["poor_mode"]["entry_ramp_cap_ms"]),
        "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
        "all_nlos_slots_active": True,
        "conditional_multipath_scenario": True,
        "inactive_slot_parameter_policy": "NOT_APPLICABLE_ALL_SLOTS_ACTIVE",
        "lock_mapping_mode": "EMPIRICAL_DIAGNOSTIC_PROXY",
        "generator_config_relative_path": config_path.relative_to(project_root).as_posix(),
        "generator_config_sha256": sha256_file(config_path),
        "parent_v21_config_sha256": str(config.source_payload["parent_v21_config"]["sha256"]),
        "parent_v21_core_sha256": str(config.source_payload["parent_v21_core"]["sha256"]),
        "parent_model_manifests": parent_manifests,
        "parent_artifacts": dict(sorted(models.artifact_hashes.items())),
        "protected_pipeline": protected,
        "source_hashes": {name: sha256_file(path) for name, path in paths.items()},
        "backend": backend,
        "output_namespace": str(output_relative).replace("\\", "/"),
        "expected_output_namespace": str(output_relative).replace("\\", "/"),
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
        "canonical_columns": list(config.source_payload["final_columns"]),
        "quality_policy": dict(config.source_payload["quality_policy"]),
    }
    validate_request_payload_shape(payload)
    validate_v22_request(payload, config)
    return payload


def canonical_request_bytes(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(dict(payload))


def write_v22_request_namespace(request_dir: Path, payload: Mapping[str, Any]) -> tuple[Path, str]:
    request_dir = request_dir.resolve()
    if request_dir.exists():
        raise FileExistsError(f"v2.2 request namespace already exists: {request_dir}")
    request_dir.parent.mkdir(parents=True, exist_ok=True)
    request_dir.mkdir()
    request_path = request_dir / "generation_request.json"
    raw = canonical_request_bytes(payload)
    request_path.write_bytes(raw)
    request_sha = __import__("hashlib").sha256(raw).hexdigest()
    (request_dir / "generation_request.sha256").write_text(request_sha + "\n", encoding="ascii", newline="\n")
    return request_path, request_sha


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--quality-mode", required=True)
    parser.add_argument("--pairing-id", required=True)
    parser.add_argument("--duration-ms", type=int, required=True)
    parser.add_argument("--master-seed", type=int, required=True)
    parser.add_argument("--simulation-id")
    parser.add_argument("--request-purpose", default="PILOT_20S")
    parser.add_argument("--request-dir", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        project_root = args.project_root.resolve()
        request_root = _resolve(project_root, V22_REQUEST_ROOT)
        request_dir = args.request_dir.resolve()
        if not _within(request_dir, request_root) or request_dir.parent != request_root or request_dir.name != args.request_id:
            raise ValueError("request_dir must be a new direct child of the v2.2 request root")
        payload = build_v22_request_payload(
            project_root=project_root,
            config_path=args.config,
            request_id=args.request_id,
            environment=args.environment,
            quality_mode=args.quality_mode,
            duration_ms=args.duration_ms,
            master_seed=args.master_seed,
            pairing_id=args.pairing_id,
            simulation_id=args.simulation_id,
            request_purpose=args.request_purpose,
        )
        if args.validate_only:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        request_path, request_sha = write_v22_request_namespace(request_dir, payload)
        print(f"GENERATION_REQUEST={request_path}")
        print(f"REQUEST_SHA256={request_sha}")
        return 0
    except Exception as exc:
        print(f"V22_REQUEST_REJECTED={type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
