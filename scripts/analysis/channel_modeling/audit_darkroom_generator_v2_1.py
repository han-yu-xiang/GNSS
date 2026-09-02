"""Independent gold-blind QA for v2.1 all-positive darkroom artifacts."""

from __future__ import annotations

import argparse
import contextlib
import csv
import gzip
import hashlib
import io
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from . import audit_darkroom_generator_v2 as _v2_audit
    from .darkroom_generator_v2_1_core import (
        ALL_ACTIVE_MASK,
        BAND_SEQUENCE,
        FINAL_COLUMNS,
        V21_RUN_ROOT,
        canonical_json_bytes,
        load_v21_config,
        load_frozen_v21_parent_models,
        sha256_file,
        validate_v21_request,
    )
except ImportError:
    from scripts.analysis.channel_modeling import audit_darkroom_generator_v2 as _v2_audit
    from scripts.analysis.channel_modeling.darkroom_generator_v2_1_core import (
        ALL_ACTIVE_MASK,
        BAND_SEQUENCE,
        FINAL_COLUMNS,
        V21_RUN_ROOT,
        canonical_json_bytes,
        load_v21_config,
        load_frozen_v21_parent_models,
        sha256_file,
        validate_v21_request,
    )


FIXED_PYTHON = Path(r"D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe")
V21_REQUEST_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_requests"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value, raw


def _read_csv(path: Path, fields: Iterable[str] | None = None, *, gzipped: bool = False) -> list[dict[str, str]]:
    if gzipped:
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            header = tuple(reader.fieldnames or ())
    else:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            header = tuple(reader.fieldnames or ())
    if fields is not None and header != tuple(fields):
        raise ValueError(f"CSV schema mismatch for {path}: {header}")
    return rows


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


def _source_paths() -> dict[str, Path]:
    current = Path(__file__).resolve()
    return {
        "scripts/analysis/channel_modeling/darkroom_generator_v2_1_core.py": current.with_name("darkroom_generator_v2_1_core.py"),
        "scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_1_request.py": current.with_name("prepare_darkroom_generator_v2_1_request.py"),
        "scripts/analysis/channel_modeling/run_darkroom_generator_v2_1.py": current.with_name("run_darkroom_generator_v2_1.py"),
        "scripts/analysis/channel_modeling/audit_darkroom_generator_v2_1.py": current,
    }


def _check_request(project_root: Path, request_path: Path, expected_request_sha256: str | None) -> tuple[dict[str, Any], bytes, str, Any, Any]:
    request_path = request_path.resolve()
    request_root = (project_root / V21_REQUEST_ROOT).resolve()
    if not _is_within(request_path, request_root) or request_path.name != "generation_request.json" or request_path.parent.parent != request_root:
        raise ValueError("request is outside the v2.1 request namespace")
    request, raw = _read_json_bytes(request_path)
    digest = hashlib.sha256(raw).hexdigest()
    if expected_request_sha256 is not None and digest.lower() != str(expected_request_sha256).lower():
        raise ValueError("request SHA-256 mismatch")
    if raw != canonical_json_bytes(request):
        raise ValueError("request is not canonical frozen JSON")
    if request_path.parent.name != str(request.get("request_id", "")):
        raise ValueError("request namespace does not match request_id")
    config_path = _resolve_project_relative(project_root, str(request.get("generator_config_relative_path", "")))
    if not config_path.is_file() or sha256_file(config_path).lower() != str(request.get("generator_config_sha256", "")).lower():
        raise ValueError("generator config provenance mismatch")
    config = load_v21_config(config_path, project_root)
    request_obj = validate_v21_request(request, config)
    parent_v2_path = _resolve_project_relative(project_root, str(config.source_payload["parent_v2_config"]["relative_path"]))
    if str(request.get("parent_v2_config_sha256", "")).lower() != str(config.source_payload["parent_v2_config"]["sha256"]).lower():
        raise ValueError("parent v2 config request provenance mismatch")
    if str(request.get("parent_v2_core_sha256", "")).lower() != str(config.source_payload["parent_v2_core"]["sha256"]).lower():
        raise ValueError("parent v2 core request provenance mismatch")
    models = load_frozen_v21_parent_models(project_root, config)
    if dict(sorted(dict(request.get("parent_artifacts", {})).items())) != dict(sorted(models.artifact_hashes.items())):
        raise ValueError("parent artifact provenance mismatch")
    if str(request.get("parent_model_manifest_sha256", "")) != str(config.source_payload["parent_model_manifest_sha256"]):
        raise ValueError("parent model manifest provenance mismatch")
    source_paths = _source_paths()
    current_sources = {name: sha256_file(path) for name, path in source_paths.items()}
    if dict(request.get("source_hashes", {})) != current_sources:
        raise ValueError("v2.1 source hash provenance mismatch")
    protected = request.get("protected_pipeline")
    if not isinstance(protected, Mapping):
        raise ValueError("protected pipeline provenance is missing")
    pipeline_path = _resolve_project_relative(project_root, str(protected.get("relative_path", "")))
    if not pipeline_path.is_file() or sha256_file(pipeline_path).lower() != str(protected.get("sha256", "")).lower():
        raise ValueError("protected pipeline provenance mismatch")
    if str(request.get("output_namespace", "")).replace("\\", "/") != str(request.get("expected_output_namespace", "")).replace("\\", "/"):
        raise ValueError("output namespace aliases do not match")
    backend = _backend_receipt()
    declared_backend = dict(request.get("backend", {}))
    if Path(sys.executable).resolve() != FIXED_PYTHON.resolve():
        raise ValueError(f"fixed Python mismatch: {sys.executable}")
    for key in ("python_executable", "python_version", "python_implementation", "architecture", "numpy_version", "scipy_version", "numpy_config"):
        if str(backend.get(key)) != str(declared_backend.get(key)):
            raise ValueError(f"backend receipt mismatch: {key}")
    return request, raw, digest, config, models


def enforce_v21_canonical_rows(rows: list[Mapping[str, Any]]) -> None:
    for row in rows:
        try:
            path_id = int(row.get("NLOSPathID", -1))
            amplitude = float(row.get("RelativeAmplitude", "nan"))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid v2.1 canonical NLOS row") from exc
        if path_id in (1, 2, 3) and (not math.isfinite(amplitude) or amplitude <= 0.0):
            raise ValueError("v2.1 NLOS amplitude must be strictly positive")


def enforce_v21_support_summary(summary: Mapping[str, Any]) -> None:
    serialized = json.dumps(dict(summary), ensure_ascii=False, sort_keys=True)

    def marker(key: str, text: str) -> bool:
        return summary.get(key) is True or summary.get(text) is True or text in serialized

    if not marker("all_nlos_slots_active", "ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT"):
        raise ValueError("ALL_THREE_NLOS_SLOTS_ALWAYS_ACTIVE_CONTRACT is not recorded")
    if not marker("activation_model_used_for_generation", "ACTIVATION_MODEL_NOT_USED_FOR_GENERATION"):
        raise ValueError("ACTIVATION_MODEL_NOT_USED_FOR_GENERATION is not recorded")
    if not marker("conditional_multipath_scenario", "CONDITIONAL_MULTIPATH_SCENARIO"):
        raise ValueError("CONDITIONAL_MULTIPATH_SCENARIO is not recorded")


def _check_manifest_hashes(run_dir: Path, manifest: Mapping[str, Any]) -> None:
    hashes = manifest.get("data_output_hashes")
    if not isinstance(hashes, Mapping) or not hashes:
        raise ValueError("generation manifest has no data_output_hashes")
    for name, expected in hashes.items():
        path = run_dir / str(name)
        if not path.is_file() or sha256_file(path).lower() != str(expected).lower():
            raise ValueError(f"data output hash mismatch: {name}")


def _check_receipt_hashes(run_dir: Path, receipt: Mapping[str, Any]) -> None:
    hashes = receipt.get("output_hashes_excluding_receipt")
    if not isinstance(hashes, Mapping) or not hashes:
        raise ValueError("generation receipt has no output hashes")
    for name, expected in hashes.items():
        path = run_dir / str(name)
        if not path.is_file() or sha256_file(path).lower() != str(expected).lower():
            raise ValueError(f"receipt output hash mismatch: {name}")


def audit_v21_run(
    project_root: Path,
    request_path: Path,
    run_dir: Path,
    expected_request_sha256: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    run_dir = run_dir.resolve()
    request, request_raw, request_sha256, config, _models = _check_request(project_root, request_path, expected_request_sha256)
    request_id = str(request["request_id"])
    run_root = (project_root / V21_RUN_ROOT).resolve()
    if not _is_within(run_dir, run_root) or run_dir == run_root or run_dir.name != request_id or run_dir.parent != run_root:
        raise ValueError("run directory is outside the direct v2.1 namespace")
    expected_run_dir = _resolve_project_relative(project_root, str(request["output_namespace"]))
    if run_dir != expected_run_dir:
        raise ValueError("run directory does not match request output namespace")
    if any(part.lower() in {"scenes", "sage_results", "_trash", "reference"} for part in run_dir.relative_to(project_root).parts):
        raise ValueError("run directory is protected")
    manifest_path = run_dir / "generation_manifest.json"
    receipt_path = run_dir / "generation_receipt.json"
    if not manifest_path.is_file() or not receipt_path.is_file():
        raise ValueError("generation manifest/receipt missing")
    manifest = _read_json(manifest_path)
    receipt = _read_json(receipt_path)
    if manifest.get("request_sha256") != request_sha256 or receipt.get("request_sha256") != request_sha256:
        raise ValueError("request hash mismatch in run artifacts")
    if manifest.get("status") == "failed" or receipt.get("status") != "completed":
        raise ValueError("run receipt is not completed")
    for artifact in (manifest, receipt):
        if artifact.get("gold_labels_used_for_generation") is not False:
            raise ValueError("gold leakage flag is not false")
        if artifact.get("all_nlos_slots_active") is not True:
            raise ValueError("all-active contract is not recorded")
    parameter_provenance = manifest.get("parameter_provenance")
    if not isinstance(parameter_provenance, Mapping):
        raise ValueError("manifest parameter provenance is missing")
    expected_provenance = {
        "generator_config_sha256": request["generator_config_sha256"],
        "parent_v2_config_sha256": request["parent_v2_config_sha256"],
        "parent_v2_core_sha256": request["parent_v2_core_sha256"],
        "parent_model_manifest_sha256": request["parent_model_manifest_sha256"],
        "parent_artifacts": request["parent_artifacts"],
        "source_hashes": request["source_hashes"],
        "protected_pipeline": request["protected_pipeline"],
        "backend": request["backend"],
    }
    if dict(parameter_provenance) != expected_provenance:
        raise ValueError("manifest parameter provenance mismatch")
    request_copy = run_dir / "generation_request.json"
    if not request_copy.is_file() or request_copy.read_bytes() != request_raw:
        raise ValueError("run request copy is not byte-identical to frozen request")
    _check_manifest_hashes(run_dir, manifest)
    _check_receipt_hashes(run_dir, receipt)

    duration_ms = int(request["duration_ms"])
    canonical_rows_raw = _read_csv(run_dir / "darkroom_channel_parameters.csv", FINAL_COLUMNS)
    canonical_audit = _v2_audit.audit_canonical_rows(canonical_rows_raw, duration_ms)
    enforce_v21_canonical_rows(canonical_audit["parsed_rows"])
    canonical_by_key = {
        (row["ms"], row["SatelliteID"], row["NLOSPathID"]): row
        for row in canonical_audit["parsed_rows"]
    }
    timeline = _v2_audit._load_timeline(run_dir / "receiver_timeline.csv.gz")
    if len(timeline) != duration_ms * 3:
        raise ValueError("receiver timeline does not contain exactly 3 bands per millisecond")
    band_order = [band for band, _ in BAND_SEQUENCE]
    for ms in range(1, duration_ms + 1):
        actual_bands = [key[1] for key in sorted((key for key in timeline if key[0] == ms), key=lambda item: band_order.index(item[1]))]
        if actual_bands != band_order:
            raise ValueError("receiver timeline band order mismatch")
    blocks = _v2_audit._load_block_catalog(run_dir / "path_block_catalog.csv", duration_ms)
    slots = _v2_audit._load_slot_timeline(run_dir / "path_slot_timeline.csv.gz", duration_ms)
    consistency = _v2_audit._check_slot_block_consistency(slots, blocks, canonical_by_key, timeline, duration_ms)
    if consistency["inactive_nlos_rows"] != 0 or consistency["active_nlos_rows"] != duration_ms * 9:
        raise ValueError("v2.1 all-active row counts are inconsistent")
    if any(slot["activation_mask"] != ALL_ACTIVE_MASK or slot["active"] is not True for slot in slots.values()):
        raise ValueError("slot sidecar violates all-active mask")
    if any(block["activation_mask"] != ALL_ACTIVE_MASK or block["active"] is not True or block["k_active"] != 3 for block in blocks.values()):
        raise ValueError("block catalog violates all-active mask")
    registry_rows = _read_csv(run_dir / "random_stream_registry.csv")
    if not registry_rows:
        raise ValueError("random stream registry is empty")
    registry_keys = [(row.get("elevation_band", ""), row.get("scope_id", ""), row.get("stream_name", "")) for row in registry_rows]
    if any(not all(key) for key in registry_keys) or len(registry_keys) != len(set(registry_keys)):
        raise ValueError("random stream registry is not unique/complete")
    support = _read_json(run_dir / "support_summary.json")
    enforce_v21_support_summary(support)
    if "INTER_SATELLITE_CORRELATION_NOT_MODELED" not in json.dumps(support, ensure_ascii=False):
        raise ValueError("cross-band correlation assumption is not recorded")
    if str(request.get("nlos_activation_policy")) != "ALL_THREE_SLOTS_ALWAYS_ACTIVE":
        raise ValueError("request activation policy mismatch")
    return {
        "audit_schema_version": "darkroom-generator-independent-qa-2.1",
        "audited_utc": _utc_now(),
        "overall_pass": True,
        "request_id": request_id,
        "request_sha256": request_sha256,
        "output_namespace": request["output_namespace"],
        "environment_class": request["environment_class"],
        "elevation_bands": request["elevation_bands"],
        "duration_ms": duration_ms,
        "row_count": canonical_audit["row_count"],
        "rows_per_millisecond": 12,
        "block_count": (duration_ms + 39) // 40,
        "active_nlos_rows": consistency["active_nlos_rows"],
        "inactive_nlos_rows": consistency["inactive_nlos_rows"],
        "all_nlos_slots_active": True,
        "nlos_activation_policy": "ALL_THREE_SLOTS_ALWAYS_ACTIVE",
        "canonical_empty_field_count": canonical_audit["canonical_empty_field_count"],
        "component_counts": {
            "receiver_timeline_rows": len(timeline),
            "path_block_catalog_rows": len(blocks),
            "path_slot_timeline_rows": len(slots),
            "random_stream_rows": len(registry_rows),
        },
        "gates": {
            "REQUEST_CONFIG_HASH_GATE": "PASS",
            "PARENT_PROVENANCE_GATE": "PASS",
            "V21_NAMESPACE_ISOLATION_GATE": "PASS",
            "ALL_BANDS_PRESENT_GATE": "PASS",
            "EXACT_12_ROWS_PER_MS_GATE": "PASS",
            "NO_EMPTY_CANONICAL_FIELD_GATE": "PASS",
            "FIXED_SLOT_IDENTITY_GATE": "PASS",
            "ALL_NLOS_STRICTLY_POSITIVE_GATE": "PASS",
            "ALL_ACTIVE_MASK_GATE": "PASS",
            "PHASE_AND_BLOCK_SEMANTICS_GATE": "PASS",
            "OUTPUT_HASH_GATE": "PASS",
            "GOLD_LEAKAGE_GATE": "PASS",
        },
        "gold_labels_used_for_generation": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "limitations": [
            "All-three-NLOS behavior is a conditional scenario contract, not an empirical occurrence-rate claim.",
            "Low/Mid/High inter-satellite correlation is not modeled.",
            "Initial phase distribution and Doppler phase recurrence are assumption-only.",
        ],
    }


def _write_audit_artifacts(run_dir: Path, result: Mapping[str, Any]) -> tuple[Path, Path]:
    result_path = run_dir / "independent_qa_result.json"
    report_path = run_dir / "independent_qa_report.md"
    if result_path.exists() or report_path.exists():
        raise FileExistsError("independent QA artifacts already exist; refusing overwrite")
    with result_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_bytes(dict(result)).decode("utf-8"))
    lines = [
        "# Darkroom Generator v2.1 Independent QA",
        "",
        f"- overall_pass: `{result.get('overall_pass')}`",
        f"- request_id: `{result.get('request_id')}`",
        f"- request_sha256: `{result.get('request_sha256')}`",
        f"- canonical rows: `{result.get('row_count')}`",
        f"- duration_ms: `{result.get('duration_ms')}`",
        f"- active NLOS rows: `{result.get('active_nlos_rows')}`",
        f"- inactive NLOS rows: `{result.get('inactive_nlos_rows')}`",
        "",
        "## Gates",
        "",
    ]
    for name, status in dict(result.get("gates", {})).items():
        lines.append(f"- `{name}`: **{status}**")
    lines.extend(
        [
            "",
            "This audit is gold-blind and Python-only; it reads no raw IQ, MATLAB, SAGE or posterior-gold artifact.",
            "The all-three-NLOS condition is a conditional scenario-generation contract, not an empirical occurrence label.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return result_path, report_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--expected-request-sha256")
    parser.add_argument("--no-write-artifacts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = audit_v21_run(args.project_root, args.request, args.run_dir, args.expected_request_sha256)
        if not args.no_write_artifacts:
            paths = _write_audit_artifacts(args.run_dir.resolve(), result)
            result = dict(result) | {"qa_result_path": str(paths[0]), "qa_report_path": str(paths[1])}
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        result = {
            "audit_schema_version": "darkroom-generator-independent-qa-2.1",
            "audited_utc": _utc_now(),
            "overall_pass": False,
            "error": f"{type(exc).__name__}: {exc}",
            "gold_labels_used_for_generation": False,
        }
        if not args.no_write_artifacts and args.run_dir.exists():
            try:
                _write_audit_artifacts(args.run_dir.resolve(), result)
            except Exception:
                pass
        print(f"V21_AUDIT_FAIL={result['error']}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
