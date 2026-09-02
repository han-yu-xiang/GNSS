"""Run or validate one immutable v2.2 darkroom parameter request.

Validation is the default.  Generation requires both ``--generate`` and the
explicit v2.2 confirmation flag.  This runner is Python-only and never reads
raw IQ or invokes MATLAB, SAGE, or the GNSS production pipeline.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import gzip
import hashlib
import io
import json
import math
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
    from .darkroom_generator_v2_2_core import (
        BAND_SEQUENCE,
        ENVIRONMENTS,
        FINAL_COLUMNS,
        V22_REQUEST_ROOT,
        V22_RUN_ROOT,
        canonical_json_bytes,
        format_v22_final_rows,
        generate_v22_simulation,
        load_frozen_v22_parent_models,
        load_v22_config,
        sha256_file,
        validate_v22_request,
    )
    from .prepare_darkroom_generator_v2_2_request import FIXED_PYTHON, source_paths
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import (
        BAND_SEQUENCE,
        ENVIRONMENTS,
        FINAL_COLUMNS,
        V22_REQUEST_ROOT,
        V22_RUN_ROOT,
        canonical_json_bytes,
        format_v22_final_rows,
        generate_v22_simulation,
        load_frozen_v22_parent_models,
        load_v22_config,
        sha256_file,
        validate_v22_request,
    )
    from scripts.analysis.channel_modeling.prepare_darkroom_generator_v2_2_request import FIXED_PYTHON, source_paths


LOCK_NAME = ".darkroom_generator_v2_2.active.lock"
RECEIVER_TIMELINE_FIELDS = (
    "simulation_id", "pairing_id", "ms", "elevation_band", "SatelliteID", "quality_mode",
    "base_common_gain_db", "base_common_gain_linear", "quality_state", "quality_event_id",
    "quality_envelope_linear", "effective_common_gain_linear", "phase_observable",
    "quality_depth_source", "quality_duration_source", "quality_recovery_source",
    "quality_support_status", "assumption_flags",
)
QUALITY_EVENT_FIELDS = (
    "simulation_id", "pairing_id", "elevation_band", "SatelliteID", "quality_mode",
    "quality_event_id", "event_start_ms", "entry_ramp_ms", "lock_bad_hold_ms",
    "recovery_duration_ms", "event_end_ms", "floor_linear", "depth_source",
    "duration_source", "recovery_source", "support_status", "complete_event",
)
PATH_BLOCK_FIELDS = (
    "simulation_id", "pairing_id", "environment_class", "quality_mode", "block_id",
    "elevation_band", "SatelliteID", "block_start_ms", "block_end_ms", "NLOSPathID",
    "active", "activation_mask", "K_active", "latent_delay_ns", "latent_doppler_hz",
    "latent_relative_amplitude", "output_relative_amplitude_base", "phase_initial_rad",
    "slot_status", "occupancy_support_status", "multiplicity_support_status",
    "path_parameter_support_status", "prior_only", "assumption_status",
)
PATH_SLOT_FIELDS = (
    "simulation_id", "pairing_id", "environment_class", "quality_mode", "ms",
    "elevation_band", "SatelliteID", "NLOSPathID", "block_id", "active",
    "activation_mask", "latent_delay_ns", "latent_doppler_hz", "latent_relative_amplitude",
    "output_relative_amplitude", "RelativePhase_rad", "slot_status", "assumption_status",
)
STREAM_FIELDS = (
    "simulation_id", "pairing_id", "environment_class", "elevation_band", "scope_id",
    "stream_name", "seed_uint64", "quality_mode", "derivation",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve(project_root: Path, relative: str) -> Path:
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


def _read_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value, raw


def _validate_namespace(project_root: Path, relative: str, request_id: str) -> Path:
    output = _resolve(project_root, relative)
    run_root = _resolve(project_root, V22_RUN_ROOT)
    if output == run_root or not _is_within(output, run_root) or output.parent != run_root or output.name != request_id:
        raise ValueError("v2.2 output must be a direct child of its own run root")
    if any(part.lower() in {"scenes", "sage_results", "reference", "_trash"} for part in output.relative_to(project_root).parts):
        raise ValueError("v2.2 output namespace points to a protected location")
    return output


def _check_parent_manifest_provenance(config: Any, models: Any, request: Mapping[str, Any]) -> None:
    expected = dict(config.source_payload["parent_model_manifests"])
    if dict(request.get("parent_model_manifests", {})) != expected:
        raise ValueError("parent model manifest declarations do not match config")
    if str(models.path_model_manifest_sha256).lower() != str(expected["path"]).lower():
        raise ValueError("path model manifest mismatch")
    if str(models.gain_model_manifest_sha256).lower() != str(expected["gain"]).lower():
        raise ValueError("gain model manifest mismatch")
    if str(models.lock_model_manifest_sha256).lower() != str(expected["recovery"]).lower():
        raise ValueError("lock/recovery composition manifest mismatch")
    artifact_values = {str(value).lower() for value in dict(models.artifact_hashes).values()}
    if str(expected["lock"]).lower() not in artifact_values or str(expected["recovery"]).lower() not in artifact_values:
        raise ValueError("environment lock/recovery parent manifest is not in frozen artifacts")
    if dict(sorted(dict(request.get("parent_artifacts", {})).items())) != dict(sorted(models.artifact_hashes.items())):
        raise ValueError("parent artifact provenance mismatch")


def _validate_request(
    project_root: Path,
    request_path: Path,
    expected_sha256: str,
    *,
    require_output_absent: bool = True,
) -> dict[str, Any]:
    request_path = request_path.resolve()
    request_root = _resolve(project_root, V22_REQUEST_ROOT)
    if not _is_within(request_path, request_root) or request_path.name != "generation_request.json" or request_path.parent.parent != request_root:
        raise ValueError("request must be generation_request.json under a direct v2.2 request namespace")
    request, raw = _read_json_bytes(request_path)
    digest = hashlib.sha256(raw).hexdigest()
    if digest.lower() != str(expected_sha256).lower():
        raise ValueError(f"request SHA-256 mismatch: {digest} != {expected_sha256}")
    if raw != canonical_json_bytes(request):
        raise ValueError("request JSON is not canonical frozen JSON")
    if request_path.parent.name != str(request.get("request_id", "")):
        raise ValueError("request namespace does not match request_id")
    config_path = _resolve(project_root, str(request.get("generator_config_relative_path", "")))
    if not config_path.is_file() or sha256_file(config_path).lower() != str(request.get("generator_config_sha256", "")).lower():
        raise ValueError("generator config hash mismatch")
    config = load_v22_config(config_path, project_root)
    request_obj = validate_v22_request(request, config)
    if request.get("source_scene_ids") != config.source_payload.get("source_scene_provenance", {}).get(request["environment_class"]):
        raise ValueError("source scene provenance does not match frozen config")
    scene_records = request.get("source_scene_metadata")
    if not isinstance(scene_records, list) or len(scene_records) != len(request["source_scene_ids"]):
        raise ValueError("source scene metadata provenance is incomplete")
    for record in scene_records:
        if not isinstance(record, Mapping):
            raise ValueError("invalid source scene metadata record")
        metadata_path = _resolve(project_root, str(record.get("relative_path", "")))
        if not metadata_path.is_file() or sha256_file(metadata_path).lower() != str(record.get("sha256", "")).lower():
            raise ValueError(f"source scene metadata hash mismatch: {metadata_path}")
    models, _parent_config = load_frozen_v22_parent_models(project_root, config)
    _check_parent_manifest_provenance(config, models, request)
    if str(request.get("parent_v21_config_sha256", "")).lower() != str(config.source_payload["parent_v21_config"]["sha256"]).lower():
        raise ValueError("v2.1 parent config provenance mismatch")
    if str(request.get("parent_v21_core_sha256", "")).lower() != str(config.source_payload["parent_v21_core"]["sha256"]).lower():
        raise ValueError("v2.1 parent core provenance mismatch")
    declared_sources = dict(request.get("source_hashes", {}))
    current_sources = {name: sha256_file(path) for name, path in source_paths().items()}
    if declared_sources != current_sources:
        raise ValueError("v2.2 source hash provenance mismatch")
    protected = request.get("protected_pipeline")
    if not isinstance(protected, Mapping):
        raise ValueError("protected pipeline provenance is missing")
    pipeline_path = _resolve(project_root, str(protected.get("relative_path", "")))
    if not pipeline_path.is_file() or sha256_file(pipeline_path).lower() != str(protected.get("sha256", "")).lower():
        raise ValueError("protected pipeline hash mismatch")
    backend = _backend_receipt()
    if Path(sys.executable).resolve() != FIXED_PYTHON.resolve():
        raise ValueError(f"fixed Python mismatch: {sys.executable}")
    for key in ("python_executable", "python_version", "python_implementation", "architecture", "numpy_version", "scipy_version", "numpy_config"):
        if str(backend.get(key)) != str(dict(request.get("backend", {})).get(key)):
            raise ValueError(f"backend receipt mismatch: {key}")
    if request.get("execution_policy") != config.source_payload.get("execution_policy"):
        raise ValueError("execution policy mismatch")
    output_dir = _validate_namespace(project_root, str(request.get("output_namespace", "")), str(request["request_id"]))
    if str(request.get("expected_output_namespace", "")).replace("\\", "/") != str(request.get("output_namespace", "")).replace("\\", "/"):
        raise ValueError("output namespace aliases do not match")
    if require_output_absent and output_dir.exists():
        raise FileExistsError(f"new_only output namespace already exists: {output_dir}")
    lock_path = _resolve(project_root, V22_REQUEST_ROOT) / LOCK_NAME
    if lock_path.exists():
        raise RuntimeError(f"active v2.2 generator lock exists: {lock_path}")
    return {
        "request": request,
        "request_raw": raw,
        "request_sha256": digest,
        "request_obj": request_obj,
        "config": config,
        "config_path": config_path,
        "models": models,
        "output_dir": output_dir,
        "lock_path": lock_path,
        "backend": backend,
        "current_sources": current_sources,
    }


def build_validation_summary(context: Mapping[str, Any]) -> dict[str, Any]:
    request = context["request"]
    return {
        "execution_eligible": True,
        "generation_requested": False,
        "matlab_invoked": False,
        "raw_iq_read": False,
        "sage_invoked": False,
        "batch_invoked": False,
        "process_20_46_mhz": False,
        "request_id": request["request_id"],
        "simulation_id": request["simulation_id"],
        "pairing_id": request["pairing_id"],
        "environment_class": request["environment_class"],
        "quality_mode": request["quality_mode"],
        "elevation_bands": list(request["elevation_bands"]),
        "duration_ms": request["duration_ms"],
        "expected_rows": int(request["duration_ms"]) * 12,
        "master_seed": request["master_seed"],
        "new_only": True,
        "resume_allowed": False,
        "nlos_activation_policy": request["nlos_activation_policy"],
        "all_nlos_slots_active": request["all_nlos_slots_active"],
        "output_namespace": request["output_namespace"],
        "output_path": str(context["output_dir"]),
        "output_absent": True,
        "request_sha256": context["request_sha256"],
        "generator_config_sha256": request["generator_config_sha256"],
        "source_hashes": request["source_hashes"],
        "parent_model_manifests": request["parent_model_manifests"],
        "backend": context["backend"],
        "gold_labels_used_for_generation": False,
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (float, int)):
        value_float = float(value)
        if not math.isfinite(value_float):
            raise ValueError("output contains a non-finite numeric value")
        return format(value_float, ".17g")
    return str(value)


def _write_csv(path: Path, fields: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    names = tuple(fields)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            missing = [name for name in names if name not in row]
            if missing:
                raise ValueError(f"missing output fields for {path.name}: {missing}")
            writer.writerow({name: _csv_value(row[name]) for name in names})


def _write_gzip_csv(path: Path, fields: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    names = tuple(fields)
    with path.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n", extrasaction="raise")
                writer.writeheader()
                for row in rows:
                    missing = [name for name in names if name not in row]
                    if missing:
                        raise ValueError(f"missing output fields for {path.name}: {missing}")
                    writer.writerow({name: _csv_value(row[name]) for name in names})


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_bytes(dict(value)).decode("utf-8"))


def _acquire_lock(lock_path: Path, request: Mapping[str, Any]) -> None:
    if lock_path.exists():
        raise RuntimeError(f"active v2.2 generator lock exists: {lock_path}")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_bytes({"request_id": request["request_id"], "created_utc": _utc_now(), "pid": os.getpid()}).decode("utf-8"))


def _release_lock(lock_path: Path, request_id: str) -> None:
    if not lock_path.exists():
        return
    released = lock_path.with_name(f".darkroom_generator_v2_2.released.{request_id}.{time.time_ns()}.lock")
    os.rename(lock_path, released)


def _write_failure_receipt(context: Mapping[str, Any], status: str, error: str, started_utc: str) -> None:
    output_dir: Path = context["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt = output_dir / "generation_receipt.json"
    if receipt.exists():
        return
    output_files = sorted(path.name for path in output_dir.iterdir() if path.is_file())
    output_hashes = {name: sha256_file(output_dir / name) for name in output_files}
    _write_json(
        receipt,
        {
            "receipt_schema_version": "darkroom-generator-receipt-2.2",
            "status": status,
            "error": error,
            "started_utc": started_utc,
            "ended_utc": _utc_now(),
            "request_id": context["request"]["request_id"],
            "request_sha256": context["request_sha256"],
            "generator_config_sha256": context["request"]["generator_config_sha256"],
            "source_hashes": context["request"]["source_hashes"],
            "backend": context["backend"],
            "output_files": output_files + [receipt.name],
            "output_hashes_excluding_receipt": output_hashes,
            "raw_iq_read": False,
            "matlab": False,
            "sage": False,
            "batch": False,
            "gold_labels_used_for_generation": False,
        },
    )


def _generation_report(request: Mapping[str, Any], result: Any, receipt_base: Mapping[str, Any]) -> str:
    quality_line = ", ".join(f"{band}={count}" for band, count in result.support_summary["quality_event_count_per_band"].items())
    return "\n".join(
        [
            "# Darkroom Multi-Elevation Fixed-Four-Slot Generator v2.2",
            "",
            "This is a Python-only paired Good/Poor conditional parameter pilot. It is not a raw-IQ, MATLAB, SAGE, or production result.",
            "",
            f"- request_id: `{request['request_id']}`",
            f"- environment_class: `{request['environment_class']}`",
            f"- quality_mode: `{request['quality_mode']}`",
            f"- pairing_id: `{request['pairing_id']}`",
            f"- duration_ms: `{request['duration_ms']}`",
            f"- master_seed: `{request['master_seed']}`",
            f"- canonical rows: `{len(result.final_rows)}`",
            f"- quality event count per band: `{quality_line}`",
            f"- generation status: `{receipt_base.get('status', 'completed')}`",
            "",
            "## Frozen semantics",
            "",
            "Canonical columns are exactly: `ms,SatelliteID,NLOSPathID,RelativeDelay,RelativeDoppler,RelativeAmplitude,RelativePhase_rad`.",
            "Every millisecond is ordered Low path 0..3, Mid path 0..3, then High path 0..3.",
            "NLOS slots 1..3 are always active and strictly positive because this is a conditional four-path scenario, not an empirical occurrence-rate claim.",
            "Good/Poor shared path and base-gain streams are paired; Poor adds only a conditional receiver-quality envelope.",
            "Phase is an assumption-only uniform initial phase with 1 ms Doppler recurrence; absolute RF power and hardware-calibrated lock probability are unavailable.",
            "",
            "## Execution policy",
            "",
            "- raw IQ read: false",
            "- MATLAB: false",
            "- SAGE: false",
            "- batch: false",
            "- 20.46 MHz: false",
            "- gold labels used for generation: false",
            "",
        ]
    )


def _generate(context: Mapping[str, Any]) -> dict[str, Any]:
    request = context["request"]
    output_dir: Path = context["output_dir"]
    output_dir.mkdir(parents=True)
    started_utc = _utc_now()
    started_counter = time.perf_counter()
    try:
        result = generate_v22_simulation(context["request_obj"], context["config"], context["models"])
        (output_dir / "generation_request.json").write_bytes(context["request_raw"])
        (output_dir / "generation_request.sha256").write_text(context["request_sha256"] + "\n", encoding="ascii", newline="\n")
        (output_dir / "darkroom_channel_parameters.csv").write_bytes(format_v22_final_rows(result.final_rows).encode("utf-8"))
        _write_gzip_csv(output_dir / "receiver_quality_timeline.csv.gz", RECEIVER_TIMELINE_FIELDS, result.receiver_quality_rows)
        event_rows = []
        for row in result.quality_event_rows:
            band = str(row["elevation_band"])
            event_rows.append(
                {
                    "simulation_id": row["simulation_id"], "pairing_id": row["pairing_id"],
                    "elevation_band": band, "SatelliteID": dict(BAND_SEQUENCE)[band],
                    "quality_mode": row["quality_mode"], "quality_event_id": row["quality_event_id"],
                    "event_start_ms": row["event_start_ms"], "entry_ramp_ms": row["entry_ramp_ms"],
                    "lock_bad_hold_ms": row["lock_bad_hold_ms"], "recovery_duration_ms": row["recovery_duration_ms"],
                    "event_end_ms": row["event_end_ms"], "floor_linear": row["floor_linear"],
                    "depth_source": row["depth_source"], "duration_source": row["duration_source"],
                    "recovery_source": row["recovery_source"], "support_status": row["support_status"],
                    "complete_event": row["complete_event"],
                }
            )
        _write_csv(output_dir / "quality_event_catalog.csv", QUALITY_EVENT_FIELDS, event_rows)
        _write_csv(output_dir / "path_block_catalog.csv", PATH_BLOCK_FIELDS, result.path_block_rows)
        _write_gzip_csv(output_dir / "path_slot_timeline.csv.gz", PATH_SLOT_FIELDS, result.path_slot_rows)
        _write_csv(output_dir / "random_stream_registry.csv", STREAM_FIELDS, result.random_stream_rows)
        _write_json(output_dir / "support_summary.json", result.support_summary)
        receipt_base: dict[str, Any] = {
            "receipt_schema_version": "darkroom-generator-receipt-2.2",
            "status": "completed",
            "started_utc": started_utc,
            "ended_utc": _utc_now(),
            "elapsed_s": time.perf_counter() - started_counter,
        }
        (output_dir / "generation_report.md").write_text(_generation_report(request, result, receipt_base), encoding="utf-8", newline="\n")
        data_files = sorted(path for path in output_dir.iterdir() if path.is_file())
        data_hashes = {path.name: sha256_file(path) for path in data_files}
        manifest = {
            "manifest_schema_version": "darkroom-generator-manifest-2.2",
            "created_utc": _utc_now(),
            "request_id": request["request_id"],
            "request_sha256": context["request_sha256"],
            "generator_id": request["generator_id"],
            "generator_version": request["generator_version"],
            "schema_version": request["schema_version"],
            "environment_class": request["environment_class"],
            "quality_mode": request["quality_mode"],
            "pairing_id": request["pairing_id"],
            "elevation_bands": request["elevation_bands"],
            "output_namespace": request["output_namespace"],
            "row_count": len(result.final_rows),
            "rows_per_millisecond": 12,
            "block_count": result.support_summary["block_count"],
            "quality_event_count_per_band": result.support_summary["quality_event_count_per_band"],
            "all_nlos_slots_active": True,
            "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
            "data_output_hashes": data_hashes,
            "parameter_provenance": {
                "generator_config_sha256": request["generator_config_sha256"],
                "parent_v21_config_sha256": request["parent_v21_config_sha256"],
                "parent_v21_core_sha256": request["parent_v21_core_sha256"],
                "parent_model_manifests": request["parent_model_manifests"],
                "parent_artifacts": request["parent_artifacts"],
                "source_hashes": request["source_hashes"],
                "protected_pipeline": request["protected_pipeline"],
                "backend": request["backend"],
            },
            "quality_policy": request["quality_policy"],
            "gold_labels_used_for_generation": False,
            "raw_iq_read": False,
            "matlab": False,
            "sage": False,
            "batch": False,
        }
        _write_json(output_dir / "generation_manifest.json", manifest)
        output_files = sorted(path.name for path in output_dir.iterdir() if path.is_file())
        output_hashes = {name: sha256_file(output_dir / name) for name in output_files}
        receipt = {
            **receipt_base,
            "request_id": request["request_id"],
            "request_sha256": context["request_sha256"],
            "generator_config_sha256": request["generator_config_sha256"],
            "parent_v21_config_sha256": request["parent_v21_config_sha256"],
            "parent_v21_core_sha256": request["parent_v21_core_sha256"],
            "parent_model_manifests": request["parent_model_manifests"],
            "parent_artifacts": request["parent_artifacts"],
            "source_hashes": request["source_hashes"],
            "backend": context["backend"],
            "environment_class": request["environment_class"],
            "quality_mode": request["quality_mode"],
            "pairing_id": request["pairing_id"],
            "duration_ms": request["duration_ms"],
            "row_count": len(result.final_rows),
            "rows_per_millisecond": 12,
            "block_count": result.support_summary["block_count"],
            "quality_event_count_per_band": result.support_summary["quality_event_count_per_band"],
            "all_nlos_slots_active": True,
            "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
            "output_files": output_files + ["generation_receipt.json"],
            "output_hashes_excluding_receipt": output_hashes,
            "gold_labels_used_for_generation": False,
            "raw_iq_read": False,
            "matlab": False,
            "sage": False,
            "batch": False,
        }
        _write_json(output_dir / "generation_receipt.json", receipt)
        return receipt
    except KeyboardInterrupt as exc:
        _write_failure_receipt(context, "interrupted", f"KeyboardInterrupt: {exc}", started_utc)
        raise
    except Exception as exc:
        _write_failure_receipt(context, "failed", f"{type(exc).__name__}: {exc}", started_utc)
        raise


def _validate_generation_confirmation(generate: bool, confirm: bool) -> None:
    if generate and not confirm:
        raise ValueError("--generate requires --confirm-darkroom-generation-v2-2")
    if confirm and not generate:
        raise ValueError("--confirm-darkroom-generation-v2-2 requires --generate")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--confirm-darkroom-generation-v2-2", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _validate_generation_confirmation(args.generate, args.confirm_darkroom_generation_v2_2)
        if args.validate_only and args.generate:
            raise ValueError("--validate-only cannot be combined with --generate")
        project_root = Path(__file__).resolve().parents[3]
        context = _validate_request(project_root, args.request, args.expected_request_sha256)
        summary = build_validation_summary(context)
        summary["generation_requested"] = bool(args.generate)
        if not args.generate:
            print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        _acquire_lock(context["lock_path"], context["request"])
        try:
            receipt = _generate(context)
        finally:
            _release_lock(context["lock_path"], str(context["request"]["request_id"]))
        print(f"GENERATION_RECEIPT={context['output_dir'] / 'generation_receipt.json'}")
        print(f"ROWS={receipt['row_count']}")
        return 0
    except KeyboardInterrupt:
        print("V22_GENERATOR_INTERRUPTED=KeyboardInterrupt")
        return 130
    except Exception as exc:
        print(f"V22_GENERATOR_REJECTED={type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
