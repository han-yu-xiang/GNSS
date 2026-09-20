"""Generate and audit an immutable 48-realization darkroom collection.

The wrapper is deliberately a collection orchestrator.  Its dry-table math is
delegated to the frozen v2.2 core; its Rain transformation is delegated to the
frozen Rain Stage3 effect-layer transformer.  It does not read raw IQ, call
MATLAB/SAGE/GNSS-SDR, fit a new model, or write under ``scenes/**/sage_results``.

The formal collection is prepared first, then executed with an explicit
confirmation, and audited as a separate step.  A partially written namespace
is never resumed or overwritten; a retry must use a new collection namespace.
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import os
import platform
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .darkroom_generator_v2_2_core import (
        BAND_SEQUENCE,
        ELEVATION_BANDS,
        ENVIRONMENTS,
        GenerationV22Request,
        FINAL_COLUMNS,
        format_v22_final_rows,
        generate_v22_simulation,
        load_frozen_v22_parent_models,
        load_v22_config,
        sha256_file as v22_sha256_file,
    )
    from .prepare_darkroom_generator_v2_2_request import (
        FIXED_PYTHON,
        _backend_receipt,
        source_paths,
    )
    from .rain_stage3_effect_layer_v1 import apply_effect_to_file
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import (
        BAND_SEQUENCE,
        ELEVATION_BANDS,
        ENVIRONMENTS,
        GenerationV22Request,
        FINAL_COLUMNS,
        format_v22_final_rows,
        generate_v22_simulation,
        load_frozen_v22_parent_models,
        load_v22_config,
        sha256_file as v22_sha256_file,
    )
    from scripts.analysis.channel_modeling.prepare_darkroom_generator_v2_2_request import (
        FIXED_PYTHON,
        _backend_receipt,
        source_paths,
    )
    from scripts.analysis.channel_modeling.rain_stage3_effect_layer_v1 import apply_effect_to_file


PROJECT_ROOT = Path(__file__).resolve().parents[3]
COLLECTION_ROOT_RELATIVE = Path("dataset_generation_logs/channel_modeling")
CONFIG_RELATIVE = Path("configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2_2.json")
RAIN_COLLECTION_RELATIVE = Path("dataset_generation_logs/channel_modeling/rain_effect_layer_stage3_v1_20260830_r5")
RAIN_MODEL_RELATIVE = RAIN_COLLECTION_RELATIVE / "rain_effect_model.json"
BASE_EXPORT_MANIFEST_RELATIVE = Path("dataset_generation_logs/channel_modeling/0828darkroomPar/table_export_manifest.json")

COLLECTION_ID = "darkroom_5min_multiseed_48_20260915"
SMOKE_COLLECTION_ID = "darkroom_5min_multiseed_48_20260915_smoke_20ms"
FORMAL_DURATION_MS = 300_000
SMOKE_DURATION_MS = 20
ROWS_PER_MS = 12
FORMAL_TABLE_COUNT = 48
MIN_FREE_BYTES = 16_000_000_000

ENVIRONMENT_SLUGS = {
    "Urban": "urban",
    "Special Reflective": "special_reflective",
    "Mountain/Valley": "mountain_valley",
    "Highway/Open": "highway_open",
}
SLUG_TO_ENVIRONMENT = {slug: name for name, slug in ENVIRONMENT_SLUGS.items()}
MODES = ("good", "poor", "rain")
INDEXES = ("01", "02", "03", "04")
QUALITY_MODE_BY_MODE = {
    "good": "GOOD_TRACKED_BASELINE",
    "poor": "POOR_CONDITIONAL",
    "rain": "GOOD_TRACKED_BASELINE",
}
WEATHER_LAYER_BY_MODE = {"good": "Dry", "poor": "Dry", "rain": "RainPooled"}
BASE_SEEDS = {
    ("urban", "01"): 202609150101,
    ("urban", "02"): 202609150102,
    ("urban", "03"): 202609150103,
    ("urban", "04"): 202609150104,
    ("special_reflective", "01"): 202609150201,
    ("special_reflective", "02"): 202609150202,
    ("special_reflective", "03"): 202609150203,
    ("special_reflective", "04"): 202609150204,
    ("mountain_valley", "01"): 202609150301,
    ("mountain_valley", "02"): 202609150302,
    ("mountain_valley", "03"): 202609150303,
    ("mountain_valley", "04"): 202609150304,
    ("highway_open", "01"): 202609150401,
    ("highway_open", "02"): 202609150402,
    ("highway_open", "03"): 202609150403,
    ("highway_open", "04"): 202609150404,
}

COLLECTION_MANIFEST_SCHEMA = "darkroom-5min-multiseed-collection-1"
GENERATION_MANIFEST_FIELDS = (
    "collection_id",
    "task_id",
    "environment_class",
    "environment_slug",
    "mode",
    "sample_index",
    "base_master_seed",
    "rain_seed",
    "quality_mode",
    "base_quality",
    "weather_layer",
    "duration_ms",
    "expected_rows",
    "actual_rows",
    "pairing_id",
    "request_id",
    "base_source_table",
    "base_source_sha256",
    "final_table",
    "generator_version",
    "generator_config_sha256",
    "v2_core_source_sha256",
    "rain_model_sha256",
    "generation_status",
    "structural_qa_status",
    "final_sha256",
)
QA_SUMMARY_FIELDS = (
    "task_id",
    "final_table",
    "mode",
    "rows",
    "rows_per_millisecond",
    "schema_ok",
    "identity_ok",
    "finite_ok",
    "amplitude_positive_ok",
    "base_source_ok",
    "rain_main_unchanged",
    "sha256",
    "qa_status",
    "failure_reason",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_collection_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise ValueError("collection_id contains unsupported characters")
    return value


def derive_rain_seed(base_master_seed: int) -> int:
    if isinstance(base_master_seed, bool) or int(base_master_seed) < 0:
        raise ValueError("base_master_seed must be a non-negative integer")
    return int(base_master_seed) + 900_000


def table_filename(environment_slug: str, mode: str, sample_index: str) -> str:
    if environment_slug not in SLUG_TO_ENVIRONMENT:
        raise ValueError(f"unsupported environment slug: {environment_slug}")
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode}")
    if sample_index not in INDEXES:
        raise ValueError(f"unsupported sample index: {sample_index}")
    return f"{environment_slug}__{mode}__{sample_index}.csv"


def build_collection_matrix(*, collection_id: str, duration_ms: int) -> list[dict[str, Any]]:
    collection_id = _normalise_collection_id(collection_id)
    if isinstance(duration_ms, bool) or int(duration_ms) < 1:
        raise ValueError("duration_ms must be positive")
    rows: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        environment_slug = ENVIRONMENT_SLUGS[environment]
        for mode in MODES:
            for sample_index in INDEXES:
                base_seed = BASE_SEEDS[(environment_slug, sample_index)]
                rain_seed = derive_rain_seed(base_seed) if mode == "rain" else None
                filename = table_filename(environment_slug, mode, sample_index)
                task_id = f"{collection_id}__{environment_slug}__{mode}__{sample_index}"
                good_filename = table_filename(environment_slug, "good", sample_index)
                rows.append(
                    {
                        "collection_id": collection_id,
                        "task_id": task_id,
                        "environment_class": environment,
                        "environment_slug": environment_slug,
                        "mode": mode,
                        "sample_index": sample_index,
                        "base_master_seed": base_seed,
                        "rain_seed": rain_seed,
                        "quality_mode": QUALITY_MODE_BY_MODE[mode],
                        "base_quality": "GOOD_TRACKED_BASELINE" if mode == "rain" else QUALITY_MODE_BY_MODE[mode],
                        "weather_layer": WEATHER_LAYER_BY_MODE[mode],
                        "duration_ms": int(duration_ms),
                        "expected_rows": int(duration_ms) * ROWS_PER_MS,
                        "actual_rows": None,
                        "pairing_id": f"{environment_slug}__{sample_index}__paired__20260915",
                        "request_id": task_id,
                        "base_source_table": f"tables/{good_filename}" if mode == "rain" else None,
                        "base_source_sha256": None,
                        "final_table": f"tables/{filename}",
                        "generator_version": "2.2.0",
                        "generator_config_sha256": None,
                        "v2_core_source_sha256": None,
                        "rain_model_sha256": None,
                        "generation_status": "PLANNED",
                        "structural_qa_status": "NOT_RUN",
                        "final_sha256": None,
                        "new_only": True,
                        "resume_allowed": False,
                    }
                )
    return rows


def build_smoke_matrix(*, collection_id: str) -> list[dict[str, Any]]:
    """Return a complete GOOD/POOR/RAIN pair for one 5-minute smoke run.

    The frozen Poor quality profile cannot represent a complete event in a
    20-ms output.  This smoke therefore keeps the real duration and limits
    the matrix to one environment/index, without changing any model rule.
    """

    return [
        row
        for row in build_collection_matrix(collection_id=collection_id, duration_ms=FORMAL_DURATION_MS)
        if row["environment_slug"] == "urban" and row["sample_index"] == "01"
    ]


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_collection_namespace(project_root: Path, collection_dir: Path, *, require_absent: bool) -> Path:
    project_root = project_root.resolve()
    root = (project_root / COLLECTION_ROOT_RELATIVE).resolve()
    candidate = collection_dir.resolve()
    if candidate == root or candidate.parent != root or not _is_within(candidate, root):
        raise ValueError("collection_dir must be a direct child of dataset_generation_logs/channel_modeling")
    protected_parts = {part.lower() for part in candidate.relative_to(project_root).parts}
    if {"scenes", "sage_results", "_trash"}.intersection(protected_parts):
        raise ValueError("collection_dir points to a protected namespace")
    if candidate.name in {"darkroom_generator_v2_2_requests", "darkroom_generator_v2_2_runs", "darkroom_generator_v2_2_matrices"}:
        raise ValueError("collection_dir cannot be a frozen v2.2 root")
    if require_absent and candidate.exists():
        raise FileExistsError(f"new-only collection namespace already exists: {candidate}")
    return candidate


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    _write_exclusive(path, _canonical_json_bytes(dict(value)))


def _write_csv_exclusive(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(fields), lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})


def _read_canonical_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    if raw != _canonical_json_bytes(value):
        raise ValueError(f"JSON is not canonical frozen JSON: {path}")
    return value, raw


def _backend_provenance() -> dict[str, Any]:
    backend = _backend_receipt()
    backend["fixed_python_required"] = str(FIXED_PYTHON.resolve())
    return backend


def _load_context(project_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    if Path(sys.executable).resolve() != FIXED_PYTHON.resolve():
        raise RuntimeError(f"fixed Python required: {FIXED_PYTHON}, got {sys.executable}")

    config_path = project_root / CONFIG_RELATIVE
    config = load_v22_config(config_path, project_root)
    models, _parent_config = load_frozen_v22_parent_models(project_root, config)
    source_hashes: dict[str, str] = {}
    for name, path in source_paths().items():
        if not path.is_file():
            raise FileNotFoundError(path)
        source_hashes[name] = sha256_file(path)
    wrapper_path = Path(__file__).resolve()
    source_hashes[wrapper_path.relative_to(project_root).as_posix()] = sha256_file(wrapper_path)

    rain_model_path = project_root / RAIN_MODEL_RELATIVE
    rain_manifest_path = project_root / RAIN_COLLECTION_RELATIVE / "rain_effect_layer_manifest.json"
    rain_run_manifest_path = project_root / RAIN_COLLECTION_RELATIVE / "rain_effect_layer_run_manifest.json"
    base_export_manifest_path = project_root / BASE_EXPORT_MANIFEST_RELATIVE
    for path in (rain_model_path, rain_manifest_path, rain_run_manifest_path, base_export_manifest_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    rain_model, _rain_model_raw = _read_canonical_json(rain_model_path)
    if rain_model.get("model_id") != "rain-stage3-effect-layer-v1":
        raise ValueError("unexpected Rain model id")
    if rain_model.get("stage4_used_for_fit") is not False or rain_model.get("gold_labels_used_for_selection") is not False:
        raise ValueError("Rain model provenance is not Stage4/gold blind")
    if rain_model.get("source_semantics") != "STAGE3_RELIABLE_EVIDENCE":
        raise ValueError("unexpected Rain model source semantics")
    return {
        "config": config,
        "config_path": config_path,
        "config_sha256": sha256_file(config_path),
        "models": models,
        "source_hashes": source_hashes,
        "v2_core_source_sha256": sha256_file(project_root / "scripts/analysis/channel_modeling/darkroom_generator_v2_2_core.py"),
        "quality_profile_sha256": sha256_file(project_root / "scripts/analysis/channel_modeling/darkroom_quality_profile_v2_2.py"),
        "rain_model": rain_model,
        "rain_model_path": rain_model_path,
        "rain_model_sha256": sha256_file(rain_model_path),
        "rain_manifest_path": rain_manifest_path,
        "rain_manifest_sha256": sha256_file(rain_manifest_path),
        "rain_run_manifest_path": rain_run_manifest_path,
        "rain_run_manifest_sha256": sha256_file(rain_run_manifest_path),
        "base_export_manifest_path": base_export_manifest_path,
        "base_export_manifest_sha256": sha256_file(base_export_manifest_path),
        "backend": _backend_provenance(),
    }


def _collection_manifest(
    *,
    project_root: Path,
    collection_dir: Path,
    collection_id: str,
    duration_ms: int,
    matrix: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    smoke: bool,
) -> dict[str, Any]:
    relative_collection = collection_dir.resolve().relative_to(project_root.resolve()).as_posix()
    return {
        "manifest_schema_version": COLLECTION_MANIFEST_SCHEMA,
        "collection_id": collection_id,
        "created_utc": _utc_now(),
        "purpose": "isolated 3-task wrapper smoke collection" if smoke else "5-minute multi-seed darkroom parameter collection",
        "smoke": smoke,
        "collection_relative_path": relative_collection,
        "table_count": len(matrix),
        "duration_ms": int(duration_ms),
        "expected_rows_per_table": int(duration_ms) * ROWS_PER_MS,
        "expected_total_rows": int(duration_ms) * ROWS_PER_MS * len(matrix),
        "ordered_environments": list(ENVIRONMENTS),
        "ordered_modes": list(MODES),
        "ordered_sample_indices": list(INDEXES),
        "final_columns": list(FINAL_COLUMNS),
        "rows_per_millisecond": ROWS_PER_MS,
        "band_order": [list(item) for item in BAND_SEQUENCE],
        "path_ids_per_band": [0, 1, 2, 3],
        "matrix": [dict(row) for row in matrix],
        "generator": {
            "generator_id": context["config"].model_id,
            "generator_version": context["config"].generator_version,
            "config_relative_path": CONFIG_RELATIVE.as_posix(),
            "config_sha256": context["config_sha256"],
            "v2_core_source_sha256": context["v2_core_source_sha256"],
            "quality_profile_sha256": context["quality_profile_sha256"],
            "source_hashes": dict(sorted(context["source_hashes"].items())),
        },
        "rain_layer": {
            "collection_relative_path": RAIN_COLLECTION_RELATIVE.as_posix(),
            "collection_manifest_sha256": context["rain_manifest_sha256"],
            "run_manifest_sha256": context["rain_run_manifest_sha256"],
            "model_relative_path": RAIN_MODEL_RELATIVE.as_posix(),
            "model_sha256": context["rain_model_sha256"],
            "weather_layer": "RainPooled",
            "base_relation": "RAIN_NN_DERIVED_FROM_MATCHING_GOOD_NN",
            "main_path_policy": "unchanged_by_stage3_rain_layer",
            "nlos_policy": "apply_pooled_rain_transform_to_slots_1_2_3_and_keep_positive",
            "stage4_used_for_fit": False,
            "gold_labels_used_for_selection": False,
        },
        "historical_reference": {
            "base_export_manifest_relative_path": BASE_EXPORT_MANIFEST_RELATIVE.as_posix(),
            "base_export_manifest_sha256": context["base_export_manifest_sha256"],
            "note": "Historical v2.2 export reference only; no existing table is renamed or overwritten.",
        },
        "execution_policy": {
            "new_only": True,
            "resume_allowed": False,
            "raw_iq_read": False,
            "matlab": False,
            "sage": False,
            "gnss_sdr": False,
            "process_20_46_mhz": False,
            "gold_labels_used_for_generation": False,
        },
        "new_only": True,
        "resume_allowed": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "gnss_sdr": False,
        "process_20_46_mhz": False,
        "gold_labels_used_for_generation": False,
        "python": context["backend"],
        "frozen_before_generation": True,
    }


def _readme_text(manifest: Mapping[str, Any]) -> str:
    duration_ms = int(manifest["duration_ms"])
    duration_label = "5-minute" if duration_ms == FORMAL_DURATION_MS else "20-ms smoke"
    return "\n".join(
        [
            "# Darkroom multi-seed collection",
            "",
            f"This is an isolated {duration_label} collection of generated channel parameter tables.",
            "It is not an RF replay, PVT result, vehicle validation result, or absolute-power calibration.",
            "",
            f"- table count: {manifest['table_count']}",
            f"- duration per table (ms): {manifest['duration_ms']}",
            f"- matrix: {len(manifest['ordered_environments'])} environments x {len(manifest['ordered_modes'])} modes x {len(manifest['ordered_sample_indices'])} realizations",
            "- modes: GOOD and POOR are dry v2.2 quality profiles; RAIN is the matching GOOD realization plus RainPooled.",
            "- Rain #NN is derived only from the corresponding GOOD #NN table.",
            "- every table contains Low/Mid/High path IDs 0..3 at each millisecond.",
            "- only the frozen v2.2 generator and frozen Rain Stage3 effect layer are used.",
            "- raw IQ, MATLAB, SAGE, GNSS-SDR, 20.46 MHz processing, and gold labels are not used.",
            "",
            "Use the manifest and SHA files as the immutable provenance anchor.  A failed or partial namespace must not be resumed; use a new collection namespace for any retry.",
            "",
        ]
    )


def prepare_collection(*, project_root: Path, collection_dir: Path, collection_id: str, duration_ms: int, smoke: bool = False) -> tuple[Path, str]:
    collection_dir = validate_collection_namespace(project_root, collection_dir, require_absent=True)
    if duration_ms not in {SMOKE_DURATION_MS, FORMAL_DURATION_MS}:
        raise ValueError("duration_ms must be 20 ms smoke or 300000 ms formal")
    if smoke and duration_ms != FORMAL_DURATION_MS:
        raise ValueError("the complete Poor smoke requires duration_ms=300000")
    context = _load_context(project_root)
    matrix = build_smoke_matrix(collection_id=collection_id) if smoke else build_collection_matrix(collection_id=collection_id, duration_ms=duration_ms)
    if not smoke and duration_ms == FORMAL_DURATION_MS and len(matrix) != FORMAL_TABLE_COUNT:
        raise AssertionError("formal collection matrix must contain 48 tables")
    collection_dir.mkdir(parents=True)
    (collection_dir / "tables").mkdir()
    (collection_dir / "provenance").mkdir()
    manifest = _collection_manifest(
        project_root=project_root,
        collection_dir=collection_dir,
        collection_id=collection_id,
        duration_ms=duration_ms,
        matrix=matrix,
        context=context,
        smoke=smoke,
    )
    manifest_path = collection_dir / "provenance" / "collection_manifest.json"
    _write_json_exclusive(manifest_path, manifest)
    manifest_sha = sha256_file(manifest_path)
    _write_exclusive(collection_dir / "provenance" / "collection_manifest.sha256", f"{manifest_sha}  collection_manifest.json\n".encode("ascii"))
    _write_exclusive(collection_dir / "README.md", _readme_text(manifest).encode("utf-8"))
    progress = {"event": "collection_frozen", "collection_id": collection_id, "manifest_sha256": manifest_sha, "utc": _utc_now()}
    _write_exclusive(collection_dir / "provenance" / "generation_progress.jsonl", (_canonical_json_bytes(progress)).replace(b"\n", b"\n"))
    return manifest_path, manifest_sha


def _load_collection_manifest(collection_dir: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    manifest_path = collection_dir / "provenance" / "collection_manifest.json"
    digest_path = collection_dir / "provenance" / "collection_manifest.sha256"
    if not manifest_path.is_file() or not digest_path.is_file():
        raise FileNotFoundError("frozen collection manifest is missing")
    manifest, raw = _read_canonical_json(manifest_path)
    digest = hashlib.sha256(raw).hexdigest()
    if digest.lower() != str(expected_sha256).lower():
        raise ValueError(f"collection manifest SHA-256 mismatch: {digest} != {expected_sha256}")
    recorded = digest_path.read_text(encoding="ascii").strip().split()[0]
    if recorded.lower() != digest.lower():
        raise ValueError("collection_manifest.sha256 does not match collection manifest")
    if manifest.get("manifest_schema_version") != COLLECTION_MANIFEST_SCHEMA:
        raise ValueError("unsupported collection manifest schema")
    if bool(manifest.get("smoke")) and len(manifest.get("matrix", [])) != 3:
        raise ValueError("smoke collection must contain exactly three tasks")
    if not bool(manifest.get("smoke")) and len(manifest.get("matrix", [])) != FORMAL_TABLE_COUNT:
        raise ValueError("formal collection must contain exactly 48 tasks")
    if manifest.get("new_only") is False or manifest.get("execution_policy", {}).get("new_only") is not True:
        raise ValueError("collection new-only policy is missing")
    if manifest.get("execution_policy", {}).get("resume_allowed") is not False:
        raise ValueError("collection resume policy is not false")
    return manifest, digest


def _assert_prepared_collection(
    *, project_root: Path, collection_dir: Path, manifest: Mapping[str, Any], context: Mapping[str, Any], require_empty_tables: bool
) -> None:
    if manifest["collection_relative_path"] != collection_dir.resolve().relative_to(project_root.resolve()).as_posix():
        raise ValueError("collection path provenance mismatch")
    matrix = manifest.get("matrix")
    if not isinstance(matrix, list) or len(matrix) != int(manifest["table_count"]):
        raise ValueError("collection matrix is malformed")
    if int(manifest["duration_ms"]) not in {SMOKE_DURATION_MS, FORMAL_DURATION_MS}:
        raise ValueError("unsupported collection duration")
    if require_empty_tables:
        for row in matrix:
            target = collection_dir / str(row["final_table"])
            if target.exists():
                raise FileExistsError(f"new-only execution refuses existing table: {target}")
        for name in (
            "generation_manifest.csv",
            "qa_summary.csv",
            "collection_generation_receipt.json",
            "collection_qa_report.json",
            "provenance/collection_failure_receipt.json",
        ):
            if (collection_dir / name).exists():
                raise FileExistsError(f"new-only execution refuses existing collection artifact: {collection_dir / name}")
    declared_config_hash = str(manifest["generator"]["config_sha256"]).lower()
    if sha256_file(context["config_path"]).lower() != declared_config_hash:
        raise ValueError("generator config changed after collection freeze")
    if dict(manifest["generator"]["source_hashes"]) != dict(sorted(context["source_hashes"].items())):
        raise ValueError("generator source hash set changed after collection freeze")
    if str(manifest["generator"]["v2_core_source_sha256"]).lower() != str(context["v2_core_source_sha256"]).lower():
        raise ValueError("v2.2 core source changed after collection freeze")
    if str(manifest["rain_layer"]["model_sha256"]).lower() != str(context["rain_model_sha256"]).lower():
        raise ValueError("Rain model changed after collection freeze")
    if Path(sys.executable).resolve() != FIXED_PYTHON.resolve():
        raise RuntimeError(f"fixed Python required: {FIXED_PYTHON}, got {sys.executable}")
    free = shutil.disk_usage(collection_dir.anchor or project_root.anchor).free
    if int(manifest["duration_ms"]) == FORMAL_DURATION_MS and free < MIN_FREE_BYTES:
        raise OSError(f"insufficient free disk space for formal collection: {free} bytes")


def _append_progress(path: Path, event: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(_canonical_json_bytes(dict(event)).decode("utf-8"))


def _request_for_row(row: Mapping[str, Any], context: Mapping[str, Any]) -> GenerationV22Request:
    quality = str(row["quality_mode"])
    quality_policy = context["config"].source_payload["quality_policy"]["poor_mode"]
    return GenerationV22Request(
        request_id=str(row["request_id"]),
        simulation_id=str(row["request_id"]),
        pairing_id=str(row["pairing_id"]),
        environment_class=str(row["environment_class"]),
        elevation_bands=tuple(ELEVATION_BANDS),
        duration_ms=int(row["duration_ms"]),
        master_seed=int(row["base_master_seed"]),
        quality_mode=quality,
        pre_event_guard_ms=int(quality_policy["pre_event_guard_ms"]),
        post_event_guard_ms=int(quality_policy["post_event_guard_ms"]),
        entry_ramp_cap_ms=int(quality_policy["entry_ramp_cap_ms"]),
        output_namespace=str(row["final_table"]),
    )


def _write_v22_table(path: Path, result: Any) -> int:
    encoded = format_v22_final_rows(result.final_rows).encode("utf-8")
    _write_exclusive(path, encoded)
    return len(result.final_rows)


def _acquire_collection_lock(path: Path, collection_id: str, manifest_sha256: str) -> None:
    if path.exists():
        raise RuntimeError(f"active collection lock exists: {path}")
    payload = {"collection_id": collection_id, "manifest_sha256": manifest_sha256, "pid": os.getpid(), "created_utc": _utc_now()}
    _write_exclusive(path, _canonical_json_bytes(payload))


def _release_collection_lock(path: Path, collection_id: str) -> None:
    if not path.exists():
        return
    released = path.with_name(f".collection.active.released.{collection_id}.{time.time_ns()}.lock")
    os.rename(path, released)


def _write_failure_receipt(collection_dir: Path, manifest_sha256: str, error: str) -> None:
    path = collection_dir / "provenance" / "collection_failure_receipt.json"
    if path.exists():
        return
    _write_json_exclusive(
        path,
        {
            "schema_version": "darkroom-5min-multiseed-failure-1",
            "collection_manifest_sha256": manifest_sha256,
            "status": "failed",
            "error": error,
            "created_utc": _utc_now(),
            "raw_iq_read": False,
            "matlab": False,
            "sage": False,
            "gnss_sdr": False,
            "resume_allowed": False,
        },
    )


def read_generation_manifest(path: Path) -> list[dict[str, str]]:
    """Read the generated task manifest without silently accepting no-op files."""

    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        required = {"task_id", "actual_rows", "final_sha256", "generation_status"}
        if not required.issubset(fieldnames):
            raise ValueError(f"generation manifest is missing required fields: {sorted(required.difference(fieldnames))}")
        rows = list(reader)
    if not rows:
        raise ValueError("generation manifest is empty")
    return rows


def execute_collection(*, project_root: Path, collection_dir: Path, expected_manifest_sha256: str) -> Path:
    collection_dir = validate_collection_namespace(project_root, collection_dir, require_absent=False)
    manifest, manifest_sha = _load_collection_manifest(collection_dir, expected_manifest_sha256)
    context = _load_context(project_root)
    _assert_prepared_collection(project_root=project_root, collection_dir=collection_dir, manifest=manifest, context=context, require_empty_tables=True)
    lock_path = collection_dir / "provenance" / ".collection.active.lock"
    _acquire_collection_lock(lock_path, str(manifest["collection_id"]), manifest_sha)
    progress_path = collection_dir / "provenance" / "generation_progress.jsonl"
    completed: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        _append_progress(progress_path, {"event": "execution_started", "utc": _utc_now(), "pid": os.getpid()})
        for row in manifest["matrix"]:
            task_id = str(row["task_id"])
            _append_progress(progress_path, {"event": "task_started", "task_id": task_id, "utc": _utc_now()})
            target = collection_dir / str(row["final_table"])
            target.parent.mkdir(parents=True, exist_ok=True)
            if str(row["mode"]) == "rain":
                source = collection_dir / str(row["base_source_table"])
                if not source.is_file():
                    raise FileNotFoundError(f"matching GOOD source is missing for Rain task: {source}")
                source_hash = sha256_file(source)
                actual_rows = apply_effect_to_file(
                    source,
                    target,
                    context["rain_model"],
                    weather="RainPooled",
                    master_seed=int(row["rain_seed"]),
                )["rows"]
            else:
                request = _request_for_row(row, context)
                result = generate_v22_simulation(request, context["config"], context["models"])
                actual_rows = _write_v22_table(target, result)
                del result
                gc.collect()
                source_hash = None
            output_hash = sha256_file(target)
            final_row = dict(row)
            final_row.update(
                {
                    "actual_rows": actual_rows,
                    "base_source_sha256": source_hash,
                    "generator_config_sha256": context["config_sha256"],
                    "v2_core_source_sha256": context["v2_core_source_sha256"],
                    "rain_model_sha256": context["rain_model_sha256"] if str(row["mode"]) == "rain" else None,
                    "generation_status": "COMPLETED",
                    "structural_qa_status": "PENDING",
                    "final_sha256": output_hash,
                }
            )
            completed.append(final_row)
            _append_progress(
                progress_path,
                {"event": "task_completed", "task_id": task_id, "rows": actual_rows, "sha256": output_hash, "utc": _utc_now()},
            )
        _write_csv_exclusive(collection_dir / "generation_manifest.csv", GENERATION_MANIFEST_FIELDS, completed)
        receipt = {
            "schema_version": "darkroom-5min-multiseed-generation-receipt-1",
            "collection_id": manifest["collection_id"],
            "collection_manifest_sha256": manifest_sha,
            "table_count": len(completed),
            "duration_ms": manifest["duration_ms"],
            "expected_total_rows": manifest["expected_total_rows"],
            "actual_total_rows": sum(int(row["actual_rows"]) for row in completed),
            "elapsed_s": time.perf_counter() - started,
            "status": "completed",
            "raw_iq_read": False,
            "matlab": False,
            "sage": False,
            "gnss_sdr": False,
            "process_20_46_mhz": False,
            "gold_labels_used_for_generation": False,
            "new_only": True,
            "resume_allowed": False,
        }
        _write_json_exclusive(collection_dir / "provenance" / "collection_generation_receipt.json", receipt)
        _append_progress(progress_path, {"event": "execution_completed", "utc": _utc_now(), "elapsed_s": receipt["elapsed_s"]})
        return collection_dir / "generation_manifest.csv"
    except KeyboardInterrupt as exc:
        _append_progress(progress_path, {"event": "execution_interrupted", "utc": _utc_now(), "error": f"KeyboardInterrupt: {exc}"})
        _write_failure_receipt(collection_dir, manifest_sha, f"KeyboardInterrupt: {exc}")
        raise
    except Exception as exc:
        _append_progress(progress_path, {"event": "execution_failed", "utc": _utc_now(), "error": f"{type(exc).__name__}: {exc}"})
        _write_failure_receipt(collection_dir, manifest_sha, f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _release_collection_lock(lock_path, str(manifest["collection_id"]))


def _parse_float(value: Any) -> float:
    result = float(str(value))
    if not math.isfinite(result):
        raise ValueError("non-finite value")
    return result


def validate_canonical_rows(rows: Iterable[Mapping[str, Any]], *, duration_ms: int) -> dict[str, Any]:
    expected_order = [(satellite, path_id) for _band, satellite in BAND_SEQUENCE for path_id in range(4)]
    path_ids = {satellite: [] for _band, satellite in BAND_SEQUENCE}
    count = 0
    for row in rows:
        if set(row.keys()) != set(FINAL_COLUMNS):
            raise ValueError("canonical columns mismatch")
        ms = int(row["ms"])
        if ms < 1 or ms > int(duration_ms):
            raise ValueError("millisecond out of range")
        path_id = int(row["NLOSPathID"])
        identity = (str(row["SatelliteID"]), path_id)
        expected = expected_order[count % ROWS_PER_MS]
        if identity != expected or ms != count // ROWS_PER_MS + 1:
            raise ValueError("canonical row order or identity mismatch")
        for field in FINAL_COLUMNS[3:]:
            _parse_float(row[field])
        if _parse_float(row["RelativeAmplitude"]) <= 0:
            raise ValueError("amplitude must be strictly positive")
        path_ids[str(row["SatelliteID"])].append(path_id)
        count += 1
    expected_count = int(duration_ms) * ROWS_PER_MS
    if count != expected_count:
        raise ValueError(f"row count mismatch: {count} != {expected_count}")
    return {
        "rows": count,
        "rows_per_millisecond": ROWS_PER_MS,
        "path_ids_per_band": path_ids,
    }


def _audit_one_table(path: Path, *, duration_ms: int, mode: str, source_path: Path | None) -> dict[str, Any]:
    expected_order = [(satellite, path_id) for _band, satellite in BAND_SEQUENCE for path_id in range(4)]
    result = {
        "rows": 0,
        "schema_ok": True,
        "identity_ok": True,
        "finite_ok": True,
        "amplitude_positive_ok": True,
        "base_source_ok": True,
        "rain_main_unchanged": True,
        "failure_reason": "",
    }
    source_handle = source_path.open("r", encoding="utf-8-sig", newline="") if source_path is not None else None
    output_handle = path.open("r", encoding="utf-8-sig", newline="")
    source_reader = csv.DictReader(source_handle) if source_handle is not None else None
    output_reader = csv.DictReader(output_handle)
    block_effects: dict[tuple[str, int, int], tuple[float, float, float]] = {}
    try:
        if tuple(output_reader.fieldnames or ()) != FINAL_COLUMNS:
            result["schema_ok"] = False
            result["failure_reason"] = "output schema mismatch"
            return result
        if source_reader is not None and tuple(source_reader.fieldnames or ()) != FINAL_COLUMNS:
            result["base_source_ok"] = False
            result["failure_reason"] = "base source schema mismatch"
            return result
        for output_row in output_reader:
            index = result["rows"]
            expected_band, expected_path = expected_order[index % ROWS_PER_MS]
            try:
                ms = int(output_row["ms"])
                path_id = int(output_row["NLOSPathID"])
                if ms != index // ROWS_PER_MS + 1 or ms > int(duration_ms):
                    result["identity_ok"] = False
                if (str(output_row["SatelliteID"]), path_id) != (expected_band, expected_path):
                    result["identity_ok"] = False
                values = [_parse_float(output_row[field]) for field in FINAL_COLUMNS[3:]]
                if values[2] <= 0:
                    result["amplitude_positive_ok"] = False
            except (KeyError, TypeError, ValueError) as exc:
                result["finite_ok"] = False
                result["failure_reason"] = f"invalid numeric/identity value: {exc}"
                result["rows"] += 1
                continue
            if source_reader is not None:
                source_row = next(source_reader, None)
                if source_row is None:
                    result["base_source_ok"] = False
                else:
                    if any(output_row[field] != source_row[field] for field in ("ms", "SatelliteID", "NLOSPathID")):
                        result["base_source_ok"] = False
                    source_values = [_parse_float(source_row[field]) for field in FINAL_COLUMNS[3:]]
                    if path_id == 0:
                        if any(abs(a - b) > 1e-10 for a, b in zip(values, source_values)):
                            result["rain_main_unchanged"] = False
                    elif mode == "rain":
                        block = (ms - 1) // 40
                        key = (str(output_row["SatelliteID"]), path_id, block)
                        effect = (
                            values[0] - source_values[0],
                            values[1] - source_values[1],
                            math.log(values[2] / source_values[2]),
                        )
                        prior = block_effects.get(key)
                        if prior is None:
                            block_effects[key] = effect
                        elif any(abs(a - b) > 1e-10 for a, b in zip(prior, effect)):
                            result["base_source_ok"] = False
                            result["failure_reason"] = "Rain effect is not constant within a 40 ms block"
            result["rows"] += 1
        if result["rows"] != int(duration_ms) * ROWS_PER_MS:
            result["identity_ok"] = False
            result["failure_reason"] = f"row count mismatch: {result['rows']} != {int(duration_ms) * ROWS_PER_MS}"
        if source_reader is not None and next(source_reader, None) is not None:
            result["base_source_ok"] = False
            result["failure_reason"] = "base source has extra rows"
    finally:
        output_handle.close()
        if source_handle is not None:
            source_handle.close()
    checks = (result["schema_ok"], result["identity_ok"], result["finite_ok"], result["amplitude_positive_ok"], result["base_source_ok"], result["rain_main_unchanged"])
    if not result["failure_reason"] and not all(checks):
        result["failure_reason"] = "one or more structural checks failed"
    return result


def audit_collection(*, project_root: Path, collection_dir: Path, expected_manifest_sha256: str) -> Path:
    collection_dir = validate_collection_namespace(project_root, collection_dir, require_absent=False)
    manifest, manifest_sha = _load_collection_manifest(collection_dir, expected_manifest_sha256)
    context = _load_context(project_root)
    _assert_prepared_collection(project_root=project_root, collection_dir=collection_dir, manifest=manifest, context=context, require_empty_tables=False)
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    generation_manifest_path = collection_dir / "generation_manifest.csv"
    generation_rows: list[dict[str, str]] = []
    generation_by_task: dict[str, dict[str, str]] = {}
    if not generation_manifest_path.is_file():
        failures.append(f"missing generation manifest: {generation_manifest_path}")
    else:
        try:
            generation_rows = read_generation_manifest(generation_manifest_path)
            generation_by_task = {str(row["task_id"]): row for row in generation_rows}
            if len(generation_by_task) != len(generation_rows) or len(generation_rows) != len(manifest["matrix"]):
                failures.append("generation manifest task count or uniqueness mismatch")
        except Exception as exc:
            failures.append(f"generation manifest invalid: {type(exc).__name__}: {exc}")
    for row in manifest["matrix"]:
        target = collection_dir / str(row["final_table"])
        source_path = collection_dir / str(row["base_source_table"]) if row["mode"] == "rain" else None
        if not target.is_file():
            failure = f"missing output: {target}"
            failures.append(failure)
            records.append({**row, "rows": 0, "rows_per_millisecond": ROWS_PER_MS, "schema_ok": False, "identity_ok": False, "finite_ok": False, "amplitude_positive_ok": False, "base_source_ok": False, "rain_main_unchanged": False, "sha256": "", "qa_status": "FAIL", "failure_reason": failure})
            continue
        if row["mode"] == "rain" and (source_path is None or not source_path.is_file()):
            failure = f"missing matching GOOD source: {source_path}"
            failures.append(failure)
            records.append({**row, "rows": 0, "rows_per_millisecond": ROWS_PER_MS, "schema_ok": False, "identity_ok": False, "finite_ok": False, "amplitude_positive_ok": False, "base_source_ok": False, "rain_main_unchanged": False, "sha256": sha256_file(target), "qa_status": "FAIL", "failure_reason": failure})
            continue
        try:
            detail = _audit_one_table(target, duration_ms=int(manifest["duration_ms"]), mode=str(row["mode"]), source_path=source_path)
        except Exception as exc:
            detail = {"rows": 0, "schema_ok": False, "identity_ok": False, "finite_ok": False, "amplitude_positive_ok": False, "base_source_ok": False, "rain_main_unchanged": False, "failure_reason": f"audit exception: {type(exc).__name__}: {exc}"}
        output_hash = sha256_file(target)
        generation_row = generation_by_task.get(str(row["task_id"]))
        ok = all(detail.get(key, False) for key in ("schema_ok", "identity_ok", "finite_ok", "amplitude_positive_ok", "base_source_ok", "rain_main_unchanged"))
        expected_rows = int(row["expected_rows"])
        if detail.get("rows") != expected_rows:
            ok = False
            detail["failure_reason"] = detail.get("failure_reason") or f"row count mismatch: {detail.get('rows')} != {expected_rows}"
        if generation_row is None:
            ok = False
            detail["failure_reason"] = detail.get("failure_reason") or "task missing from generation manifest"
        else:
            if generation_row.get("generation_status") != "COMPLETED":
                ok = False
                detail["failure_reason"] = detail.get("failure_reason") or "generation status is not COMPLETED"
            if generation_row.get("actual_rows") != str(detail.get("rows")):
                ok = False
                detail["failure_reason"] = detail.get("failure_reason") or "generation manifest row count mismatch"
            if generation_row.get("final_sha256", "").lower() != output_hash.lower():
                ok = False
                detail["failure_reason"] = detail.get("failure_reason") or "generation manifest hash mismatch"
        if not ok:
            failures.append(f"{row['task_id']}: {detail.get('failure_reason')}")
        records.append(
            {
                "task_id": row["task_id"],
                "final_table": row["final_table"],
                "mode": row["mode"],
                "rows": detail.get("rows", 0),
                "rows_per_millisecond": ROWS_PER_MS,
                "schema_ok": ok and detail.get("schema_ok", False),
                "identity_ok": ok and detail.get("identity_ok", False),
                "finite_ok": ok and detail.get("finite_ok", False),
                "amplitude_positive_ok": ok and detail.get("amplitude_positive_ok", False),
                "base_source_ok": ok and detail.get("base_source_ok", False),
                "rain_main_unchanged": ok and detail.get("rain_main_unchanged", False),
                "sha256": output_hash,
                "qa_status": "PASS" if ok else "FAIL",
                "failure_reason": detail.get("failure_reason", ""),
            }
        )
    if (collection_dir / "qa_summary.csv").exists() or (collection_dir / "collection_qa_report.json").exists():
        raise FileExistsError("new-only QA refuses an existing QA artifact")
    _write_csv_exclusive(collection_dir / "qa_summary.csv", QA_SUMMARY_FIELDS, records)
    report = {
        "schema_version": "darkroom-5min-multiseed-qa-1",
        "collection_id": manifest["collection_id"],
        "collection_manifest_sha256": manifest_sha,
        "table_count": len(records),
        "expected_total_rows": manifest["expected_total_rows"],
        "actual_total_rows": sum(int(row["rows"]) for row in records),
        "generation_manifest_sha256": sha256_file(generation_manifest_path) if generation_manifest_path.is_file() else None,
        "passed_table_count": sum(row["qa_status"] == "PASS" for row in records),
        "failed_table_count": sum(row["qa_status"] != "PASS" for row in records),
        "pass": not failures and len(records) == int(manifest["table_count"]),
        "failures": failures,
        "gold_blind": True,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "gnss_sdr": False,
        "process_20_46_mhz": False,
        "new_only": True,
        "resume_allowed": False,
    }
    _write_json_exclusive(collection_dir / "collection_qa_report.json", report)
    return collection_dir / "collection_qa_report.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--prepare", action="store_true")
    actions.add_argument("--execute", action="store_true")
    actions.add_argument("--qa", action="store_true")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--collection-id", default=COLLECTION_ID)
    parser.add_argument("--collection-dir", type=Path, required=True)
    parser.add_argument("--duration-ms", type=int, default=FORMAL_DURATION_MS)
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--smoke", action="store_true", help="prepare the isolated three-task full-duration smoke collection")
    parser.add_argument("--confirm-darkroom-5min-collection", action="store_true")
    parser.add_argument("--confirm-darkroom-smoke", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        project_root = args.project_root.resolve()
        collection_dir = args.collection_dir.resolve()
        if args.prepare:
            if args.smoke and args.duration_ms != FORMAL_DURATION_MS:
                raise ValueError("--smoke requires --duration-ms 300000")
            path, digest = prepare_collection(
                project_root=project_root,
                collection_dir=collection_dir,
                collection_id=_normalise_collection_id(args.collection_id),
                duration_ms=args.duration_ms,
                smoke=args.smoke,
            )
            print(f"COLLECTION_MANIFEST={path}")
            print(f"COLLECTION_MANIFEST_SHA256={digest}")
            manifest, _ = _load_collection_manifest(collection_dir, digest)
            print(f"TABLE_COUNT={manifest['table_count']}")
            print("GENERATION_EXECUTED=false")
            return 0
        if not args.expected_manifest_sha256:
            raise ValueError("--expected-manifest-sha256 is required for execute/qa")
        if args.execute:
            manifest, _ = _load_collection_manifest(collection_dir, args.expected_manifest_sha256)
            if manifest.get("smoke") is True:
                if not args.confirm_darkroom_smoke:
                    raise ValueError("smoke execution requires --confirm-darkroom-smoke")
            elif not args.confirm_darkroom_5min_collection:
                raise ValueError("formal execution requires --confirm-darkroom-5min-collection")
            path = execute_collection(project_root=project_root, collection_dir=collection_dir, expected_manifest_sha256=args.expected_manifest_sha256)
            print(f"GENERATION_MANIFEST={path}")
            print("GENERATION_STATUS=COMPLETED")
            return 0
        path = audit_collection(project_root=project_root, collection_dir=collection_dir, expected_manifest_sha256=args.expected_manifest_sha256)
        report = json.loads(path.read_text(encoding="utf-8"))
        print(f"QA_REPORT={path}")
        print(f"QA_PASS={str(bool(report['pass'])).upper()}")
        return 0 if report["pass"] else 1
    except KeyboardInterrupt:
        print("DARKROOM_MULTISEED_INTERRUPTED=KeyboardInterrupt")
        return 130
    except Exception as exc:
        print(f"DARKROOM_MULTISEED_REJECTED={type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
