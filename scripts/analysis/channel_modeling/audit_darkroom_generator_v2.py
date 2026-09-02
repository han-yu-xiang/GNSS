"""Independently audit one v2 darkroom generation namespace.

This module is intentionally a structural/provenance auditor.  It does not
import the v2 runner, call the generator, read raw data, or inspect SAGE/gold
artifacts.  The canonical table is checked independently from the generation
implementation, then joined to the sidecar timelines for fixed-slot and phase
semantics.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


FINAL_COLUMNS: tuple[str, ...] = (
    "ms",
    "SatelliteID",
    "NLOSPathID",
    "RelativeDelay",
    "RelativeDoppler",
    "RelativeAmplitude",
    "RelativePhase_rad",
)
BAND_SEQUENCE: tuple[tuple[str, str], ...] = (("LOW", "Low"), ("MID", "Mid"), ("HIGH", "High"))
SATELLITE_ORDER = {label: index for index, (_, label) in enumerate(BAND_SEQUENCE)}
V2_RUN_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs"
V2_REQUEST_ROOT = "dataset_generation_logs/channel_modeling/darkroom_generator_v2_requests"
MS_PHASE_STEP_S = 0.001


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        raise ValueError(f"provenance path escapes project root: {relative}")
    return target


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_csv(path: Path, fields: Iterable[str] | None = None, *, gzipped: bool = False) -> list[dict[str, str]]:
    opener = gzip.open if gzipped else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        if fields is not None and tuple(reader.fieldnames) != tuple(fields):
            raise ValueError(f"CSV header mismatch for {path}: {reader.fieldnames}")
        rows: list[dict[str, str]] = []
        for row in reader:
            if None in row:
                raise ValueError(f"CSV has extra fields: {path}")
            rows.append({str(key): "" if value is None else str(value) for key, value in row.items()})
    return rows


def _as_int(value: Any, field: str) -> int:
    text = str(value)
    if text == "":
        raise ValueError(f"empty canonical field: {field}")
    try:
        result = int(text)
    except ValueError as exc:
        raise ValueError(f"invalid integer field: {field}={text!r}") from exc
    if text not in {str(result), f"+{result}"}:
        raise ValueError(f"non-canonical integer field: {field}={text!r}")
    return result


def _as_float(value: Any, field: str) -> float:
    text = str(value)
    if text == "":
        raise ValueError(f"empty canonical field: {field}")
    try:
        result = float(text)
    except ValueError as exc:
        raise ValueError(f"invalid numeric field: {field}={text!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite canonical field: {field}")
    return result


def _wrap_phase(value: float) -> float:
    wrapped = (float(value) + math.pi) % (2.0 * math.pi) - math.pi
    if wrapped >= math.pi:
        wrapped -= 2.0 * math.pi
    return wrapped


def _phase_difference(first: float, second: float) -> float:
    return _wrap_phase(first - second)


def validate_phase_sequence(phases: list[float], doppler_hz: float, tolerance: float = 1e-12) -> None:
    if not math.isfinite(float(doppler_hz)):
        raise ValueError("phase recurrence requires finite Doppler")
    for first, second in zip(phases, phases[1:]):
        expected = _wrap_phase(first + 2.0 * math.pi * float(doppler_hz) * MS_PHASE_STEP_S)
        if abs(_phase_difference(second, expected)) > tolerance:
            raise ValueError(f"phase recurrence mismatch: {second!r} != {expected!r}")


def _parse_canonical_rows(rows: list[dict[str, str]], duration_ms: int) -> tuple[list[dict[str, Any]], int]:
    expected_per_ms = [(label, path_id) for _, label in BAND_SEQUENCE for path_id in range(4)]
    expected_count = int(duration_ms) * len(expected_per_ms)
    if len(rows) != expected_count:
        raise ValueError(f"canonical row count mismatch: {len(rows)} != {expected_count}")
    parsed: list[dict[str, Any]] = []
    empty_count = 0
    for index, row in enumerate(rows):
        if tuple(row) != FINAL_COLUMNS:
            raise ValueError("canonical row field order mismatch")
        empty_count += sum(1 for field in FINAL_COLUMNS if row.get(field, "") == "")
        ms = _as_int(row.get("ms", ""), "ms")
        satellite = row.get("SatelliteID", "")
        path_id = _as_int(row.get("NLOSPathID", ""), "NLOSPathID")
        if satellite not in SATELLITE_ORDER:
            raise ValueError(f"invalid SatelliteID: {satellite!r}")
        if path_id not in (0, 1, 2, 3):
            raise ValueError(f"invalid NLOSPathID: {path_id}")
        expected_ms = index // len(expected_per_ms) + 1
        expected_satellite, expected_path = expected_per_ms[index % len(expected_per_ms)]
        if (ms, satellite, path_id) != (expected_ms, expected_satellite, expected_path):
            raise ValueError(f"canonical order/identity mismatch at row {index}: {(ms, satellite, path_id)}")
        delay = _as_float(row.get("RelativeDelay", ""), "RelativeDelay")
        doppler = _as_float(row.get("RelativeDoppler", ""), "RelativeDoppler")
        amplitude = _as_float(row.get("RelativeAmplitude", ""), "RelativeAmplitude")
        phase = _as_float(row.get("RelativePhase_rad", ""), "RelativePhase_rad")
        if not -math.pi <= phase < math.pi:
            raise ValueError(f"phase outside [-pi,pi): {phase}")
        if path_id == 0:
            if delay != 0.0 or doppler != 0.0 or amplitude <= 0.0:
                raise ValueError("path 0 violates fixed reference semantics")
        elif delay <= 0.0 or amplitude < 0.0:
            raise ValueError("NLOS canonical row violates finite latent/zero-amplitude semantics")
        parsed.append(
            {
                "ms": ms,
                "SatelliteID": satellite,
                "NLOSPathID": path_id,
                "RelativeDelay": delay,
                "RelativeDoppler": doppler,
                "RelativeAmplitude": amplitude,
                "RelativePhase_rad": phase,
            }
        )
    if empty_count:
        raise ValueError(f"canonical table contains {empty_count} empty fields")
    return parsed, empty_count


def audit_canonical_rows(rows: list[dict[str, Any]], duration_ms: int) -> dict[str, Any]:
    normalized: list[dict[str, str]] = []
    for row in rows:
        normalized.append({field: row.get(field, "") for field in FINAL_COLUMNS})
    parsed, empty_count = _parse_canonical_rows(normalized, duration_ms)
    return {
        "row_count": len(parsed),
        "exact_12_rows_per_ms": len(parsed) == int(duration_ms) * 12,
        "canonical_empty_field_count": empty_count,
        "fixed_slot_identity": True,
        "parsed_rows": parsed,
    }


def _parse_bool(value: str, field: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"invalid boolean sidecar field {field}: {value!r}")


def _check_close(actual: float, expected: float, field: str, tolerance: float = 1e-12) -> None:
    if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        raise ValueError(f"{field} mismatch: {actual!r} != {expected!r}")


def _check_request(project_root: Path, request_path: Path, expected_request_sha256: str | None) -> tuple[dict[str, Any], bytes, str]:
    request_path = request_path.resolve()
    request_root = (project_root / V2_REQUEST_ROOT).resolve()
    if not _is_within(request_path, request_root) or request_path.name != "generation_request.json" or request_path.parent.parent != request_root:
        raise ValueError("request is outside the v2 request namespace")
    raw = request_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_request_sha256 is not None and digest.lower() != expected_request_sha256.lower():
        raise ValueError("request SHA-256 mismatch")
    request = json.loads(raw.decode("utf-8"))
    if not isinstance(request, dict) or raw != _canonical_json_bytes(request):
        raise ValueError("request is not canonical frozen JSON")
    if request.get("new_only") is not True or request.get("resume_allowed") is not False:
        raise ValueError("request is not new_only/resume_allowed=false")
    if tuple(request.get("elevation_bands", ())) != ("LOW", "MID", "HIGH"):
        raise ValueError("request does not contain all frozen bands")
    if any(request.get(field) is not False for field in ("raw_iq_read", "matlab", "sage", "batch", "process_20_46_mhz")):
        raise ValueError("request enables a forbidden execution mode")
    config_path = _resolve_project_relative(project_root, request.get("generator_config_relative_path", ""))
    if not config_path.is_file() or _sha256_file(config_path).lower() != str(request.get("generator_config_sha256", "")).lower():
        raise ValueError("generator config provenance mismatch")
    parent_artifacts = request.get("parent_artifacts")
    if not isinstance(parent_artifacts, Mapping) or not parent_artifacts:
        raise ValueError("parent artifact provenance is missing")
    for relative, expected_hash in parent_artifacts.items():
        artifact_path = _resolve_project_relative(project_root, str(relative))
        if not artifact_path.is_file() or _sha256_file(artifact_path).lower() != str(expected_hash).lower():
            raise ValueError(f"parent artifact provenance mismatch: {relative}")
    declared_sources = request.get("source_hashes")
    if not isinstance(declared_sources, Mapping):
        raise ValueError("source hash provenance is missing")
    current_file = Path(__file__).resolve()
    source_paths = {
        "scripts/analysis/channel_modeling/darkroom_generator_v2_core.py": current_file.with_name("darkroom_generator_v2_core.py"),
        "scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_request.py": current_file.with_name("prepare_darkroom_generator_v2_request.py"),
        "scripts/analysis/channel_modeling/run_darkroom_generator_v2.py": current_file.with_name("run_darkroom_generator_v2.py"),
        "scripts/analysis/channel_modeling/audit_darkroom_generator_v2.py": current_file,
    }
    current_sources = {name: _sha256_file(path) for name, path in source_paths.items()}
    if dict(declared_sources) != current_sources:
        raise ValueError("current v2 source hash provenance mismatch")
    protected = request.get("protected_pipeline")
    if not isinstance(protected, Mapping):
        raise ValueError("protected pipeline provenance is missing")
    pipeline_path = _resolve_project_relative(project_root, protected.get("relative_path", ""))
    if not pipeline_path.is_file() or _sha256_file(pipeline_path).lower() != str(protected.get("sha256", "")).lower():
        raise ValueError("protected pipeline provenance mismatch")
    return request, raw, digest


def _check_manifest_hashes(run_dir: Path, manifest: Mapping[str, Any]) -> None:
    hashes = manifest.get("data_output_hashes")
    if not isinstance(hashes, Mapping) or not hashes:
        raise ValueError("generation manifest has no data_output_hashes")
    for name, expected in hashes.items():
        path = run_dir / str(name)
        if not path.is_file() or _sha256_file(path).lower() != str(expected).lower():
            raise ValueError(f"data output hash mismatch: {name}")


def _load_timeline(path: Path) -> dict[tuple[int, str], dict[str, Any]]:
    rows = _read_csv(path, gzipped=True)
    expected_fields = (
        "simulation_id", "ms", "elevation_band", "SatelliteID", "common_gain_db",
        "common_gain_linear", "ordinary_fade_state", "ordinary_fade_event_id",
        "ordinary_fade_envelope_linear", "lock_state", "lock_event_id",
        "lock_envelope_linear", "effective_common_gain_linear", "phase_observable",
        "gain_support_status", "fade_support_status", "lock_support_status", "assumption_flags",
    )
    if not rows or tuple(rows[0]) != expected_fields:
        raise ValueError("receiver timeline schema mismatch")
    result: dict[tuple[int, str], dict[str, Any]] = {}
    expected_count = 0
    for row in rows:
        ms = _as_int(row["ms"], "timeline.ms")
        band = row["elevation_band"]
        satellite = row["SatelliteID"]
        if band not in {item[0] for item in BAND_SEQUENCE} or dict(BAND_SEQUENCE)[band] != satellite:
            raise ValueError("timeline band/SatelliteID mismatch")
        key = (ms, band)
        if key in result:
            raise ValueError("duplicate receiver timeline key")
        effective = _as_float(row["effective_common_gain_linear"], "timeline.effective_common_gain_linear")
        if effective <= 0.0:
            raise ValueError("timeline effective common gain must be positive")
        result[key] = {
            "effective_common_gain_linear": effective,
            "raw": row,
        }
        expected_count += 1
    return result


def _load_slot_timeline(path: Path, duration_ms: int) -> dict[tuple[int, str, int], dict[str, Any]]:
    rows = _read_csv(path, gzipped=True)
    expected_fields = (
        "simulation_id", "ms", "elevation_band", "SatelliteID", "NLOSPathID", "block_id",
        "active", "activation_mask", "latent_delay_ns", "latent_doppler_hz",
        "latent_relative_amplitude", "output_relative_amplitude", "RelativePhase_rad",
        "slot_status", "assumption_status",
    )
    if not rows or tuple(rows[0]) != expected_fields:
        raise ValueError("path slot timeline schema mismatch")
    expected_count = int(duration_ms) * 3 * 3
    if len(rows) != expected_count:
        raise ValueError(f"path slot timeline row count mismatch: {len(rows)} != {expected_count}")
    result: dict[tuple[int, str, int], dict[str, Any]] = {}
    for index, row in enumerate(rows):
        ms = _as_int(row["ms"], "slot.ms")
        band = row["elevation_band"]
        satellite = row["SatelliteID"]
        path_id = _as_int(row["NLOSPathID"], "slot.NLOSPathID")
        if band not in {item[0] for item in BAND_SEQUENCE} or dict(BAND_SEQUENCE)[band] != satellite or path_id not in (1, 2, 3):
            raise ValueError("slot identity mismatch")
        expected_index = (ms - 1) * 9 + list(dict(BAND_SEQUENCE)).index(band) * 3 + path_id - 1
        if index != expected_index:
            raise ValueError("path slot timeline order mismatch")
        key = (ms, band, path_id)
        if key in result:
            raise ValueError("duplicate path slot key")
        active = _parse_bool(row["active"], "slot.active")
        latent_delay = _as_float(row["latent_delay_ns"], "slot.latent_delay_ns")
        latent_doppler = _as_float(row["latent_doppler_hz"], "slot.latent_doppler_hz")
        latent_amplitude = _as_float(row["latent_relative_amplitude"], "slot.latent_relative_amplitude")
        output_amplitude = _as_float(row["output_relative_amplitude"], "slot.output_relative_amplitude")
        phase = _as_float(row["RelativePhase_rad"], "slot.RelativePhase_rad")
        if latent_delay <= 0.0 or latent_amplitude < 0.0 or not -math.pi <= phase < math.pi:
            raise ValueError("invalid latent slot value")
        if active and output_amplitude <= 0.0:
            raise ValueError("active slot must have positive output amplitude")
        if not active and output_amplitude != 0.0:
            raise ValueError("inactive slot must have zero output amplitude")
        result[key] = {
            "ms": ms,
            "band": band,
            "satellite": satellite,
            "path_id": path_id,
            "block_id": row["block_id"],
            "active": active,
            "activation_mask": row["activation_mask"],
            "latent_delay_ns": latent_delay,
            "latent_doppler_hz": latent_doppler,
            "latent_relative_amplitude": latent_amplitude,
            "output_relative_amplitude": output_amplitude,
            "phase": phase,
            "slot_status": row["slot_status"],
            "assumption_status": row["assumption_status"],
        }
    return result


def _load_block_catalog(path: Path, duration_ms: int) -> dict[tuple[str, int, int], dict[str, Any]]:
    expected_fields = (
        "block_id", "elevation_band", "SatelliteID", "block_start_ms", "block_end_ms", "NLOSPathID",
        "active", "activation_mask", "K_active", "latent_delay_ns", "latent_doppler_hz",
        "latent_relative_amplitude", "output_relative_amplitude_base", "phase_initial_rad",
        "slot_status", "occupancy_support_status", "multiplicity_support_status",
        "path_parameter_support_status", "prior_only", "assumption_status",
    )
    rows = _read_csv(path, expected_fields)
    block_count = (int(duration_ms) + 39) // 40
    if len(rows) != block_count * 3 * 3:
        raise ValueError("path block catalog row count mismatch")
    result: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in rows:
        band = row["elevation_band"]
        block_id = row["block_id"]
        prefix = f"{band.lower()}-block-"
        if not block_id.startswith(prefix):
            raise ValueError("block id/band mismatch")
        block_number = int(block_id.rsplit("-", 1)[1])
        path_id = _as_int(row["NLOSPathID"], "block.NLOSPathID")
        if band not in {item[0] for item in BAND_SEQUENCE} or path_id not in (1, 2, 3):
            raise ValueError("block identity mismatch")
        key = (band, block_number, path_id)
        if key in result:
            raise ValueError("duplicate block catalog key")
        result[key] = {
            "block_id": block_id,
            "band": band,
            "block_number": block_number,
            "block_start_ms": _as_int(row["block_start_ms"], "block.block_start_ms"),
            "block_end_ms": _as_int(row["block_end_ms"], "block.block_end_ms"),
            "path_id": path_id,
            "active": _parse_bool(row["active"], "block.active"),
            "activation_mask": row["activation_mask"],
            "k_active": _as_int(row["K_active"], "block.K_active"),
            "latent_delay_ns": _as_float(row["latent_delay_ns"], "block.latent_delay_ns"),
            "latent_doppler_hz": _as_float(row["latent_doppler_hz"], "block.latent_doppler_hz"),
            "latent_relative_amplitude": _as_float(row["latent_relative_amplitude"], "block.latent_relative_amplitude"),
            "output_relative_amplitude_base": _as_float(row["output_relative_amplitude_base"], "block.output_relative_amplitude_base"),
            "phase_initial_rad": _as_float(row["phase_initial_rad"], "block.phase_initial_rad"),
            "slot_status": row["slot_status"],
            "prior_only": _parse_bool(row["prior_only"], "block.prior_only"),
            "assumption_status": row["assumption_status"],
        }
        item = result[key]
        if item["latent_delay_ns"] <= 0.0 or item["latent_relative_amplitude"] < 0.0 or not -math.pi <= item["phase_initial_rad"] < math.pi:
            raise ValueError("invalid block latent values")
    return result


def _check_slot_block_consistency(
    slots: Mapping[tuple[int, str, int], Mapping[str, Any]],
    blocks: Mapping[tuple[str, int, int], Mapping[str, Any]],
    canonical: Mapping[tuple[int, str, int], Mapping[str, Any]],
    timeline: Mapping[tuple[int, str], Mapping[str, Any]],
    duration_ms: int,
) -> dict[str, int]:
    active_count = 0
    inactive_count = 0
    for key, slot in slots.items():
        ms, band, path_id = key
        canonical_row = canonical[(ms, dict(BAND_SEQUENCE)[band], path_id)]
        block_number = (ms - 1) // 40 + 1
        block = blocks[(band, block_number, path_id)]
        if slot["block_id"] != block["block_id"]:
            raise ValueError("slot/block id mismatch")
        for field in ("latent_delay_ns", "latent_doppler_hz", "latent_relative_amplitude"):
            _check_close(float(slot[field]), float(block[field]), f"{field} block constancy")
        expected_active = str(block["activation_mask"])[path_id - 1] == "1"
        if bool(slot["active"]) != expected_active:
            raise ValueError("slot activation mask mismatch")
        if slot["active"]:
            active_count += 1
            if canonical_row["RelativeAmplitude"] <= 0.0:
                raise ValueError("active canonical NLOS amplitude is not positive")
            expected_amplitude = float(timeline[(ms, band)]["effective_common_gain_linear"]) * float(slot["latent_relative_amplitude"])
            _check_close(float(slot["output_relative_amplitude"]), expected_amplitude, "active amplitude composition", 2e-12)
        else:
            inactive_count += 1
            if canonical_row["RelativeAmplitude"] != 0.0 or slot["output_relative_amplitude"] != 0.0:
                raise ValueError("inactive canonical/sidecar amplitude is not exactly zero")
        _check_close(float(canonical_row["RelativeAmplitude"]), float(slot["output_relative_amplitude"]), "canonical/sidecar amplitude", 2e-12)
        _check_close(float(canonical_row["RelativeDelay"]), float(slot["latent_delay_ns"]), "canonical/sidecar delay")
        _check_close(float(canonical_row["RelativeDoppler"]), float(slot["latent_doppler_hz"]), "canonical/sidecar Doppler")
        _check_close(float(canonical_row["RelativePhase_rad"]), float(slot["phase"]), "canonical/sidecar phase")
    if len(slots) != int(duration_ms) * 9:
        raise ValueError("slot consistency did not cover every expected row")
    for band, _ in BAND_SEQUENCE:
        for block_number in range(1, (int(duration_ms) + 39) // 40 + 1):
            grouped = {
                path_id: [slots[(ms, band, path_id)] for ms in range((block_number - 1) * 40 + 1, min(duration_ms, block_number * 40) + 1)]
                for path_id in (1, 2, 3)
            }
            for path_id, rows in grouped.items():
                if not rows:
                    continue
                validate_phase_sequence([float(row["phase"]) for row in rows], float(rows[0]["latent_doppler_hz"]))
                if any(row["block_id"] != blocks[(band, block_number, path_id)]["block_id"] for row in rows):
                    raise ValueError("block membership drift")
    return {"active_nlos_rows": active_count, "inactive_nlos_rows": inactive_count}


def audit_v2_run(
    project_root: Path,
    request_path: Path,
    run_dir: Path,
    expected_request_sha256: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    run_dir = run_dir.resolve()
    request, request_raw, request_sha256 = _check_request(project_root, request_path, expected_request_sha256)
    request_id = str(request["request_id"])
    run_root = (project_root / V2_RUN_ROOT).resolve()
    if not _is_within(run_dir, run_root) or run_dir == run_root or run_dir.name != request_id:
        raise ValueError("run directory is outside request-specific v2 namespace")
    expected_run_dir = _resolve_project_relative(project_root, request.get("output_namespace", ""))
    if run_dir != expected_run_dir:
        raise ValueError("run directory does not match request output namespace")
    if any(part.lower() in {"scenes", "sage_results", "_trash"} for part in run_dir.relative_to(project_root).parts):
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
    if manifest.get("gold_labels_used_for_generation") is not False or receipt.get("gold_labels_used_for_generation") is not False:
        raise ValueError("gold leakage flag is not false")
    parameter_provenance = manifest.get("parameter_provenance")
    if not isinstance(parameter_provenance, Mapping):
        raise ValueError("manifest parameter provenance is missing")
    if parameter_provenance.get("generator_config_sha256") != request.get("generator_config_sha256"):
        raise ValueError("manifest generator config provenance mismatch")
    if dict(parameter_provenance.get("source_hashes", {})) != dict(request.get("source_hashes", {})):
        raise ValueError("manifest source provenance mismatch")
    request_copy = run_dir / "generation_request.json"
    if not request_copy.is_file() or request_copy.read_bytes() != request_raw:
        raise ValueError("run request copy is not byte-identical to frozen request")
    _check_manifest_hashes(run_dir, manifest)

    duration_ms = int(request["duration_ms"])
    canonical_rows_raw = _read_csv(run_dir / "darkroom_channel_parameters.csv", FINAL_COLUMNS)
    canonical_audit = audit_canonical_rows(canonical_rows_raw, duration_ms)
    canonical_by_key = {
        (row["ms"], row["SatelliteID"], row["NLOSPathID"]): row
        for row in canonical_audit["parsed_rows"]
    }
    timeline = _load_timeline(run_dir / "receiver_timeline.csv.gz")
    if len(timeline) != duration_ms * 3:
        raise ValueError("receiver timeline does not contain 3 bands per millisecond")
    band_order = [band for band, _ in BAND_SEQUENCE]
    for ms in range(1, duration_ms + 1):
        actual_bands = [key[1] for key in sorted((key for key in timeline if key[0] == ms), key=lambda item: band_order.index(item[1]))]
        if actual_bands != band_order:
            raise ValueError("receiver timeline band order mismatch")
    blocks = _load_block_catalog(run_dir / "path_block_catalog.csv", duration_ms)
    slots = _load_slot_timeline(run_dir / "path_slot_timeline.csv.gz", duration_ms)
    consistency = _check_slot_block_consistency(slots, blocks, canonical_by_key, timeline, duration_ms)
    registry_rows = _read_csv(run_dir / "random_stream_registry.csv")
    if not registry_rows:
        raise ValueError("random stream registry is empty")
    registry_keys = [(row.get("elevation_band", ""), row.get("scope_id", ""), row.get("stream_name", "")) for row in registry_rows]
    if any(not all(key) for key in registry_keys) or len(registry_keys) != len(set(registry_keys)):
        raise ValueError("random stream registry is not unique/complete")
    support = _read_json(run_dir / "support_summary.json")
    if "INTER_SATELLITE_CORRELATION_NOT_MODELED" not in json.dumps(support, ensure_ascii=False):
        raise ValueError("cross-band correlation assumption is not recorded")
    if "LATENT_INACTIVE_PARAMETER_NOT_PHYSICAL_PATH" not in json.dumps(support, ensure_ascii=False):
        raise ValueError("inactive latent assumption is not recorded")
    for name in ("generator_config_sha256", "source_hashes", "protected_pipeline"):
        if name not in request:
            raise ValueError(f"request provenance missing: {name}")
    return {
        "audit_schema_version": "darkroom-generator-independent-qa-1",
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
            "V2_NAMESPACE_ISOLATION_GATE": "PASS",
            "ALL_BANDS_PRESENT_GATE": "PASS",
            "EXACT_12_ROWS_PER_MS_GATE": "PASS",
            "NO_EMPTY_CANONICAL_FIELD_GATE": "PASS",
            "FIXED_SLOT_IDENTITY_GATE": "PASS",
            "ACTIVATION_ZERO_AMPLITUDE_GATE": "PASS",
            "LATENT_INACTIVE_PARAMETER_GATE": "PASS_WITH_LIMITATIONS",
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
            "Inactive NLOS values are finite latent slot parameters and are not physical paths.",
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
        handle.write(_canonical_json_bytes(dict(result)).decode("utf-8"))
    lines = [
        "# Darkroom Generator v2 Independent QA",
        "",
        f"- overall_pass: `{result.get('overall_pass')}`",
        f"- request_id: `{result.get('request_id')}`",
        f"- request_sha256: `{result.get('request_sha256')}`",
        f"- canonical rows: `{result.get('row_count')}`",
        f"- duration_ms: `{result.get('duration_ms')}`",
        f"- active NLOS rows: `{result.get('active_nlos_rows')}`",
        f"- inactive latent NLOS rows: `{result.get('inactive_nlos_rows')}`",
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
    project_root = args.project_root.resolve()
    try:
        result = audit_v2_run(project_root, args.request, args.run_dir, args.expected_request_sha256)
        if not args.no_write_artifacts:
            paths = _write_audit_artifacts(args.run_dir.resolve(), result)
            result = dict(result) | {"qa_result_path": str(paths[0]), "qa_report_path": str(paths[1])}
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        result = {
            "audit_schema_version": "darkroom-generator-independent-qa-1",
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
        print(f"V2_AUDIT_FAIL={result['error']}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
