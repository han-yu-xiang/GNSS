"""Run one immutable, new-only v2.1 darkroom parameter request.

Validation is the default.  Generation requires both ``--generate`` and the
explicit v2.1 confirmation flag.  This runner reads only frozen model
artifacts; it never reads raw IQ, MATLAB, SAGE or production data.
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
    from .darkroom_generator_v2_1_core import (
        ALL_ACTIVE_MASK,
        BAND_SEQUENCE,
        FINAL_COLUMNS,
        V21_RUN_ROOT,
        canonical_json_bytes,
        format_v21_final_rows,
        generate_v21_simulation,
        load_frozen_v21_parent_models,
        load_v21_config,
        sha256_file,
        validate_v21_request,
    )
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_v2_1_core import (
        ALL_ACTIVE_MASK,
        BAND_SEQUENCE,
        FINAL_COLUMNS,
        V21_RUN_ROOT,
        canonical_json_bytes,
        format_v21_final_rows,
        generate_v21_simulation,
        load_frozen_v21_parent_models,
        load_v21_config,
        sha256_file,
        validate_v21_request,
    )


FIXED_PYTHON = Path(r"D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe")
REQUEST_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_requests"
LOCK_NAME = ".darkroom_generator_v2_1.active.lock"

BLOCK_FIELDS: tuple[str, ...] = (
    "block_id", "elevation_band", "SatelliteID", "block_start_ms", "block_end_ms", "NLOSPathID",
    "active", "activation_mask", "K_active", "latent_delay_ns", "latent_doppler_hz",
    "latent_relative_amplitude", "output_relative_amplitude_base", "phase_initial_rad", "slot_status",
    "occupancy_support_status", "multiplicity_support_status", "path_parameter_support_status", "prior_only",
    "assumption_status",
)
SLOT_FIELDS: tuple[str, ...] = (
    "simulation_id", "ms", "elevation_band", "SatelliteID", "NLOSPathID", "block_id", "active",
    "activation_mask", "latent_delay_ns", "latent_doppler_hz", "latent_relative_amplitude",
    "output_relative_amplitude", "RelativePhase_rad", "slot_status", "assumption_status",
)
TIMELINE_FIELDS: tuple[str, ...] = (
    "simulation_id", "ms", "elevation_band", "SatelliteID", "common_gain_db", "common_gain_linear",
    "ordinary_fade_state", "ordinary_fade_event_id", "ordinary_fade_envelope_linear", "lock_state",
    "lock_event_id", "lock_envelope_linear", "effective_common_gain_linear", "phase_observable",
    "gain_support_status", "fade_support_status", "lock_support_status", "assumption_flags",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _read_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value, raw


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


def _validate_namespace(project_root: Path, relative_namespace: str, request_id: str) -> Path:
    normalized = str(relative_namespace).replace("\\", "/")
    prefix = V21_RUN_ROOT + "/"
    if not normalized.startswith(prefix):
        raise ValueError("output namespace is outside the v2.1 run root")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("output namespace contains unsafe path components")
    if parts[-1] != request_id:
        raise ValueError("output namespace must end with request_id")
    root = project_root.resolve()
    run_root = (root / V21_RUN_ROOT).resolve()
    target = (root / normalized).resolve()
    if target == run_root or not _is_within(target, run_root):
        raise ValueError("output namespace is not a request-specific v2.1 directory")
    protected = {"scenes", "sage_results", "_trash", "reference"}
    if any(part.lower() in protected for part in target.relative_to(root).parts):
        raise ValueError("protected namespace cannot be used for v2.1 generation")
    if target.parent != run_root:
        raise ValueError("v2.1 output namespace must be a direct child of the run root")
    return target


def _current_source_hashes() -> dict[str, str]:
    current = Path(__file__).resolve()
    paths = {
        "scripts/analysis/channel_modeling/darkroom_generator_v2_1_core.py": current.with_name("darkroom_generator_v2_1_core.py"),
        "scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_1_request.py": current.with_name("prepare_darkroom_generator_v2_1_request.py"),
        "scripts/analysis/channel_modeling/run_darkroom_generator_v2_1.py": current,
        "scripts/analysis/channel_modeling/audit_darkroom_generator_v2_1.py": current.with_name("audit_darkroom_generator_v2_1.py"),
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"v2.1 source files missing: {missing}")
    return {name: sha256_file(path) for name, path in paths.items()}


def _validate_request(project_root: Path, request_path: Path, expected_sha256: str) -> dict[str, Any]:
    request_path = request_path.resolve()
    request_root = (project_root / REQUEST_ROOT).resolve()
    if not _is_within(request_path, request_root) or request_path.name != "generation_request.json":
        raise ValueError("request must be generation_request.json under the v2.1 request root")
    if request_path.parent.parent != request_root:
        raise ValueError("request must be in a direct request namespace")
    request, raw = _read_json_bytes(request_path)
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha.lower() != str(expected_sha256).lower():
        raise ValueError(f"request SHA-256 mismatch: {actual_sha} != {expected_sha256}")
    if raw != canonical_json_bytes(request):
        raise ValueError("request JSON is not canonical frozen JSON")
    request_id = str(request.get("request_id", ""))
    if request_path.parent.name != request_id:
        raise ValueError("request namespace does not match request_id")
    config_path = _resolve_project_relative(project_root, str(request.get("generator_config_relative_path", "")))
    if not config_path.is_file() or sha256_file(config_path).lower() != str(request.get("generator_config_sha256", "")).lower():
        raise ValueError("generator config hash mismatch")
    config = load_v21_config(config_path, project_root)
    request_obj = validate_v21_request(request, config)
    output_relative = str(request.get("output_namespace", "")).replace("\\", "/")
    if output_relative != str(request.get("expected_output_namespace", output_relative)).replace("\\", "/"):
        raise ValueError("output namespace aliases do not match")
    output_dir = _validate_namespace(project_root, output_relative, request_id)
    models = load_frozen_v21_parent_models(project_root, config)
    declared_parents = dict(sorted(dict(request.get("parent_artifacts", {})).items()))
    if declared_parents != dict(sorted(models.artifact_hashes.items())):
        raise ValueError("parent artifact provenance mismatch")
    if str(request.get("parent_v2_config_sha256", "")).lower() != str(config.source_payload["parent_v2_config"]["sha256"]).lower():
        raise ValueError("parent v2 config provenance mismatch")
    if str(request.get("parent_v2_core_sha256", "")).lower() != str(config.source_payload["parent_v2_core"]["sha256"]).lower():
        raise ValueError("parent v2 core provenance mismatch")
    if str(request.get("parent_model_manifest_sha256", "")) != str(config.source_payload["parent_model_manifest_sha256"]):
        raise ValueError("parent model manifest provenance mismatch")
    declared_sources = dict(request.get("source_hashes", {}))
    current_sources = _current_source_hashes()
    if declared_sources != current_sources:
        raise ValueError("v2.1 source hash mismatch")
    protected = dict(request.get("protected_pipeline", {}))
    pipeline_path = _resolve_project_relative(project_root, str(protected.get("relative_path", "")))
    if not pipeline_path.is_file() or sha256_file(pipeline_path).lower() != str(protected.get("sha256", "")).lower():
        raise ValueError("protected pipeline hash mismatch")
    backend = _backend_receipt()
    if Path(sys.executable).resolve() != FIXED_PYTHON.resolve():
        raise ValueError(f"fixed Python mismatch: {sys.executable}")
    declared_backend = dict(request.get("backend", {}))
    for key in ("python_executable", "python_version", "python_implementation", "architecture", "numpy_version", "scipy_version", "numpy_config"):
        if str(backend.get(key)) != str(declared_backend.get(key)):
            raise ValueError(f"backend receipt mismatch: {key}")
    if output_dir.exists():
        raise FileExistsError(f"new_only output namespace already exists: {output_dir}")
    lock_path = (project_root / REQUEST_ROOT / LOCK_NAME).resolve()
    if lock_path.exists():
        raise RuntimeError(f"active v2.1 generator lock exists: {lock_path}")
    return {
        "request": request,
        "request_obj": request_obj,
        "request_raw": raw,
        "request_sha256": actual_sha,
        "config": config,
        "config_path": config_path,
        "models": models,
        "output_dir": output_dir,
        "lock_path": lock_path,
        "backend": backend,
        "pipeline_path": pipeline_path,
        "current_source_hashes": current_sources,
    }


def _validate_generation_confirmation(generate: bool, confirm: bool) -> None:
    if generate and not confirm:
        raise ValueError("--generate requires --confirm-darkroom-generation-v2-1")
    if confirm and not generate:
        raise ValueError("--confirm-darkroom-generation-v2-1 requires --generate")


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
        "environment_class": request["environment_class"],
        "elevation_bands": list(request["elevation_bands"]),
        "duration_ms": request["duration_ms"],
        "expected_rows": int(request["duration_ms"]) * 12,
        "master_seed": request["master_seed"],
        "nlos_activation_policy": request["nlos_activation_policy"],
        "all_nlos_slots_active": request["all_nlos_slots_active"],
        "output_namespace": request["output_namespace"],
        "output_path": str(context["output_dir"]),
        "request_sha256": context["request_sha256"],
        "generator_config_sha256": request["generator_config_sha256"],
        "parent_artifact_count": len(request.get("parent_artifacts", {})),
        "backend": context["backend"],
        "gold_labels_used_for_generation": False,
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (float, int)):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("sidecar contains a non-finite value")
        return format(number, ".17g")
    return str(value)


def _write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    names = tuple(fieldnames)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            missing = [name for name in names if name not in row]
            if missing:
                raise ValueError(f"missing sidecar fields: {missing}")
            writer.writerow({name: _csv_value(row[name]) for name in names})


def _write_gzip_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[Mapping[str, Any]]) -> None:
    names = tuple(fieldnames)
    with path.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=names, lineterminator="\n", extrasaction="raise")
                writer.writeheader()
                for row in rows:
                    missing = [name for name in names if name not in row]
                    if missing:
                        raise ValueError(f"missing gzip sidecar fields: {missing}")
                    writer.writerow({name: _csv_value(row[name]) for name in names})


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_bytes(dict(value)).decode("utf-8"))


def _acquire_lock(lock_path: Path, request: Mapping[str, Any]) -> None:
    if lock_path.exists():
        raise RuntimeError(f"active v2.1 generator lock exists: {lock_path}")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_bytes({"request_id": request["request_id"], "created_utc": _utc_now(), "pid": os.getpid()}).decode("utf-8"))


def _release_lock(lock_path: Path, request_id: str) -> None:
    if not lock_path.exists():
        return
    released = lock_path.with_name(f".darkroom_generator_v2_1.released.{request_id}.{time.time_ns()}.lock")
    os.rename(lock_path, released)


def _write_failure_receipt(context: Mapping[str, Any], status: str, error: str, started_utc: str) -> None:
    output_dir: Path = context["output_dir"]
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    receipt_path = output_dir / "generation_receipt.json"
    if receipt_path.exists():
        return
    output_hashes = {
        path.name: sha256_file(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != receipt_path.name
    }
    _write_json(
        receipt_path,
        {
            "receipt_schema_version": "darkroom-generator-receipt-2.1",
            "status": status,
            "error": error,
            "started_utc": started_utc,
            "ended_utc": _utc_now(),
            "request_id": context["request"]["request_id"],
            "request_sha256": context["request_sha256"],
            "generator_config_sha256": context["request"]["generator_config_sha256"],
            "source_hashes": context["request"]["source_hashes"],
            "backend": context["backend"],
            "output_files": sorted(path.name for path in output_dir.iterdir() if path.is_file()),
            "output_hashes_excluding_receipt": output_hashes,
            "raw_iq_read": False,
            "matlab": False,
            "sage": False,
            "batch": False,
            "gold_labels_used_for_generation": False,
        },
    )


def _write_generation_report(path: Path, request: Mapping[str, Any], result: Any, receipt: Mapping[str, Any]) -> None:
    lines = [
        "# Darkroom Multi-Elevation Fixed-Four-Slot Generator v2.1 Preview",
        "",
        "This is a Python-only deterministic conditional multipath parameter preview generated from frozen derived model artifacts.",
        "It is not a raw-IQ, MATLAB, SAGE, or production execution result.",
        "",
        f"- request_id: `{request['request_id']}`",
        f"- simulation_id: `{request['simulation_id']}`",
        f"- environment_class: `{request['environment_class']}`",
        f"- elevation_bands: `{','.join(request['elevation_bands'])}`",
        f"- duration_ms: `{request['duration_ms']}`",
        f"- master_seed: `{request['master_seed']}`",
        f"- rows: `{len(result.final_rows)}`",
        "- rows per millisecond: `12`",
        f"- 40 ms blocks per band: `{result.support_summary['block_count']}`",
        f"- generation status: `{receipt.get('status')}`",
        "",
        "## Canonical table schema",
        "",
        "The canonical CSV uses exactly this order:",
        "",
        "`" + "`, `".join(FINAL_COLUMNS) + "`",
        "",
        "Every millisecond is ordered Low path 0..3, Mid path 0..3, then High path 0..3.",
        "NLOS slots 1..3 are always active in this conditional scenario and every emitted NLOS amplitude is strictly positive.",
        "",
        "## Scientific status",
        "",
        "- frozen parent models reused read-only",
        "- all three NLOS slots active: true",
        "- empirical activation model used for generation: false",
        "- conditional multipath scenario: true",
        "- gold labels used for generation: false",
        "- inter-satellite correlation: not modeled",
        "- phase: assumption-only uniform initial phase plus Doppler recurrence",
        "",
        "## Execution policy",
        "",
        "- raw IQ read: false",
        "- MATLAB: false",
        "- SAGE: false",
        "- batch: false",
        "- 20.46 MHz: false",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _generate(context: Mapping[str, Any]) -> dict[str, Any]:
    request = context["request"]
    output_dir: Path = context["output_dir"]
    output_dir.mkdir(parents=True)
    started_utc = _utc_now()
    started_counter = time.perf_counter()
    try:
        result = generate_v21_simulation(context["request_obj"], context["config"], context["models"])
        (output_dir / "generation_request.json").write_bytes(context["request_raw"])
        (output_dir / "generation_request.sha256").write_text(context["request_sha256"] + "\n", encoding="ascii", newline="\n")
        (output_dir / "darkroom_channel_parameters.csv").write_bytes(format_v21_final_rows(result.final_rows).encode("utf-8"))
        _write_csv(output_dir / "path_block_catalog.csv", BLOCK_FIELDS, result.path_block_rows)
        _write_gzip_csv(output_dir / "path_slot_timeline.csv.gz", SLOT_FIELDS, result.path_slot_rows)
        _write_gzip_csv(output_dir / "receiver_timeline.csv.gz", TIMELINE_FIELDS, result.timeline_rows)
        stream_fields = ("simulation_id", "elevation_band", "scope_id", "stream_name", "seed_uint64", "derivation")
        _write_csv(output_dir / "random_stream_registry.csv", stream_fields, result.stream_rows)
        _write_json(output_dir / "support_summary.json", result.support_summary)

        receipt_base: dict[str, Any] = {
            "receipt_schema_version": "darkroom-generator-receipt-2.1",
            "status": "completed",
            "started_utc": started_utc,
            "ended_utc": _utc_now(),
            "elapsed_s": time.perf_counter() - started_counter,
        }
        _write_generation_report(output_dir / "generation_report.md", request, result, receipt_base)
        data_files = sorted(path for path in output_dir.iterdir() if path.is_file())
        data_hashes = {path.name: sha256_file(path) for path in data_files}
        manifest = {
            "manifest_schema_version": "darkroom-generator-manifest-2.1",
            "created_utc": _utc_now(),
            "request_id": request["request_id"],
            "request_sha256": context["request_sha256"],
            "generator_id": request["generator_id"],
            "generator_version": request["generator_version"],
            "environment_class": request["environment_class"],
            "elevation_bands": request["elevation_bands"],
            "output_namespace": request["output_namespace"],
            "row_count": len(result.final_rows),
            "rows_per_millisecond": 12,
            "block_count": result.support_summary["block_count"],
            "all_nlos_slots_active": True,
            "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
            "data_output_hashes": data_hashes,
            "parameter_provenance": {
                "generator_config_sha256": request["generator_config_sha256"],
                "parent_v2_config_sha256": request["parent_v2_config_sha256"],
                "parent_v2_core_sha256": request["parent_v2_core_sha256"],
                "parent_model_manifest_sha256": request["parent_model_manifest_sha256"],
                "parent_artifacts": request["parent_artifacts"],
                "source_hashes": request["source_hashes"],
                "protected_pipeline": request["protected_pipeline"],
                "backend": request["backend"],
            },
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
            "parent_v2_config_sha256": request["parent_v2_config_sha256"],
            "parent_v2_core_sha256": request["parent_v2_core_sha256"],
            "parent_model_manifest_sha256": request["parent_model_manifest_sha256"],
            "parent_artifacts": request["parent_artifacts"],
            "source_hashes": request["source_hashes"],
            "backend": context["backend"],
            "environment_class": request["environment_class"],
            "elevation_bands": request["elevation_bands"],
            "duration_ms": request["duration_ms"],
            "row_count": len(result.final_rows),
            "rows_per_millisecond": 12,
            "block_count": result.support_summary["block_count"],
            "all_nlos_slots_active": True,
            "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
            "output_files": output_files + ["generation_receipt.json"],
            "output_hashes_excluding_receipt": output_hashes,
            "raw_iq_read": False,
            "matlab": False,
            "sage": False,
            "batch": False,
            "gold_labels_used_for_generation": False,
        }
        _write_json(output_dir / "generation_receipt.json", receipt)
        return receipt
    except KeyboardInterrupt as exc:
        _write_failure_receipt(context, "interrupted", f"KeyboardInterrupt: {exc}", started_utc)
        raise
    except Exception as exc:
        _write_failure_receipt(context, "failed", f"{type(exc).__name__}: {exc}", started_utc)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--confirm-darkroom-generation-v2-1", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _validate_generation_confirmation(args.generate, args.confirm_darkroom_generation_v2_1)
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
        print("V21_GENERATOR_INTERRUPTED=KeyboardInterrupt")
        return 130
    except Exception as exc:
        print(f"V21_GENERATOR_REJECTED={type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

