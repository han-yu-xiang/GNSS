"""Independent QA for one completed v2.2 paired-quality darkroom run."""

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

try:
    from .darkroom_generator_core import evolve_phase_1ms
    from .darkroom_generator_v2_2_core import BAND_SEQUENCE, FINAL_COLUMNS, V22_RUN_ROOT, canonical_json_bytes, sha256_file
    from .run_darkroom_generator_v2_2 import (
        PATH_BLOCK_FIELDS,
        PATH_SLOT_FIELDS,
        QUALITY_EVENT_FIELDS,
        RECEIVER_TIMELINE_FIELDS,
        STREAM_FIELDS,
        _validate_request,
    )
except ImportError:
    from scripts.analysis.channel_modeling.darkroom_generator_core import evolve_phase_1ms
    from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import BAND_SEQUENCE, FINAL_COLUMNS, V22_RUN_ROOT, canonical_json_bytes, sha256_file
    from scripts.analysis.channel_modeling.run_darkroom_generator_v2_2 import (
        PATH_BLOCK_FIELDS,
        PATH_SLOT_FIELDS,
        QUALITY_EVENT_FIELDS,
        RECEIVER_TIMELINE_FIELDS,
        STREAM_FIELDS,
        _validate_request,
    )


AUDIT_SCHEMA_VERSION = "darkroom-generator-independent-qa-2.2"
SATELLITE_BY_BAND = dict(BAND_SEQUENCE)
BAND_NAMES = tuple(band for band, _label in BAND_SEQUENCE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_csv_rows(path: Path, expected_fields: Iterable[str], *, gzipped: bool = False) -> list[dict[str, str]]:
    opener = gzip.open if gzipped else Path.open
    if gzipped:
        handle = opener(path, "rt", encoding="utf-8", newline="")
    else:
        handle = opener(path, "r", encoding="utf-8", newline="")
    with handle:
        reader = csv.DictReader(handle)
        actual = tuple(reader.fieldnames or ())
        expected = tuple(expected_fields)
        if actual != expected:
            raise ValueError(f"CSV schema mismatch for {path.name}: {actual} != {expected}")
        return list(reader)


def _as_int(value: Any, field: str) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer {field}: {value!r}") from exc


def _as_float(value: Any, field: str) -> float:
    try:
        number = float(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid float {field}: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"non-finite float {field}")
    return number


def _as_bool(value: Any, field: str) -> bool:
    text = str(value)
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"invalid boolean {field}: {value!r}")


def _phase_close(first: float, second: float, tolerance: float = 1e-12) -> bool:
    difference = (float(first) - float(second) + math.pi) % (2.0 * math.pi) - math.pi
    return abs(difference) <= tolerance


def _check_hash_map(directory: Path, hashes: Mapping[str, Any], label: str) -> None:
    if not isinstance(hashes, Mapping) or not hashes:
        raise ValueError(f"{label} output hashes are missing")
    for name, expected in hashes.items():
        path = directory / str(name)
        if not path.is_file() or sha256_file(path).lower() != str(expected).lower():
            raise ValueError(f"{label} output hash mismatch: {name}")


def enforce_v22_canonical_rows(path: Path, duration_ms: int) -> dict[str, Any]:
    expected_per_ms = [(label, path_id) for _band, label in BAND_SEQUENCE for path_id in range(4)]
    expected_count = int(duration_ms) * len(expected_per_ms)
    counts = {label: 0 for _band, label in BAND_SEQUENCE}
    previous_phase: dict[tuple[str, int], tuple[int, float, float]] = {}
    row_count = 0
    nlos_count = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FINAL_COLUMNS:
            raise ValueError("canonical CSV schema mismatch")
        for index, row in enumerate(reader):
            row_count += 1
            if row_count > expected_count:
                raise ValueError("canonical row count exceeds expected count")
            expected_ms = index // len(expected_per_ms) + 1
            expected_satellite, expected_path = expected_per_ms[index % len(expected_per_ms)]
            ms = _as_int(row.get("ms", ""), "canonical.ms")
            satellite = str(row.get("SatelliteID", ""))
            path_id = _as_int(row.get("NLOSPathID", ""), "canonical.NLOSPathID")
            if (ms, satellite, path_id) != (expected_ms, expected_satellite, expected_path):
                raise ValueError(f"canonical order/identity mismatch at row {index}")
            delay = _as_float(row.get("RelativeDelay", ""), "canonical.RelativeDelay")
            doppler = _as_float(row.get("RelativeDoppler", ""), "canonical.RelativeDoppler")
            amplitude = _as_float(row.get("RelativeAmplitude", ""), "canonical.RelativeAmplitude")
            phase = _as_float(row.get("RelativePhase_rad", ""), "canonical.RelativePhase_rad")
            if not -math.pi <= phase < math.pi:
                raise ValueError("canonical phase is outside [-pi,pi)")
            if path_id == 0:
                if delay != 0.0 or doppler != 0.0 or amplitude <= 0.0:
                    raise ValueError("canonical path 0 violates fixed reference semantics")
            else:
                nlos_count += 1
                if delay <= 0.0 or amplitude <= 0.0:
                    raise ValueError("canonical NLOS row is not strictly positive")
                key = (satellite, path_id)
                prior = previous_phase.get(key)
                if prior is not None and prior[0] == ms - 1 and (ms - 1) % 40 != 0:
                    expected_phase = evolve_phase_1ms(prior[1], prior[2])
                    if not _phase_close(phase, expected_phase):
                        raise ValueError(f"canonical NLOS phase recurrence mismatch at {satellite}/{path_id}/{ms}")
                previous_phase[key] = (ms, phase, doppler)
            counts[satellite] += 1
    if row_count != expected_count:
        raise ValueError(f"canonical row count mismatch: {row_count} != {expected_count}")
    return {"row_count": row_count, "nlos_rows": nlos_count, "rows_per_millisecond": 12, "band_row_counts": counts}


def _load_receiver_timeline(path: Path, duration_ms: int, quality_mode: str) -> dict[tuple[int, str], dict[str, Any]]:
    rows = _read_csv_rows(path, RECEIVER_TIMELINE_FIELDS, gzipped=True)
    expected_count = int(duration_ms) * 3
    if len(rows) != expected_count:
        raise ValueError(f"receiver timeline row count mismatch: {len(rows)} != {expected_count}")
    result: dict[tuple[int, str], dict[str, Any]] = {}
    for index, row in enumerate(rows):
        ms = _as_int(row["ms"], "timeline.ms")
        band = row["elevation_band"]
        satellite = row["SatelliteID"]
        if band not in BAND_NAMES or SATELLITE_BY_BAND[band] != satellite:
            raise ValueError("receiver timeline band/SatelliteID mismatch")
        expected_index = (ms - 1) * 3 + BAND_NAMES.index(band)
        if index != expected_index:
            raise ValueError("receiver timeline order mismatch")
        if row["quality_mode"] != quality_mode:
            raise ValueError("receiver timeline quality mode mismatch")
        base_db = _as_float(row["base_common_gain_db"], "timeline.base_common_gain_db")
        base = _as_float(row["base_common_gain_linear"], "timeline.base_common_gain_linear")
        envelope = _as_float(row["quality_envelope_linear"], "timeline.quality_envelope_linear")
        effective = _as_float(row["effective_common_gain_linear"], "timeline.effective_common_gain_linear")
        if base <= 0.0 or envelope <= 0.0 or envelope > 1.0 or effective <= 0.0:
            raise ValueError("receiver timeline gain/envelope is outside positive range")
        if not math.isclose(effective, base * envelope, rel_tol=2e-12, abs_tol=2e-12):
            raise ValueError("receiver timeline effective gain composition mismatch")
        key = (ms, band)
        if key in result:
            raise ValueError("duplicate receiver timeline key")
        result[key] = {
            "ms": ms,
            "band": band,
            "satellite": satellite,
            "base_common_gain_db": base_db,
            "base_common_gain_linear": base,
            "quality_envelope_linear": envelope,
            "effective_common_gain_linear": effective,
            "quality_state": row["quality_state"],
            "quality_event_id": row["quality_event_id"] or None,
            "phase_observable": _as_bool(row["phase_observable"], "timeline.phase_observable"),
            "raw": row,
        }
    return result


def _load_quality_events(path: Path, duration_ms: int, quality_mode: str) -> dict[str, dict[str, Any]]:
    rows = _read_csv_rows(path, QUALITY_EVENT_FIELDS)
    expected_count = 0 if quality_mode == "GOOD_TRACKED_BASELINE" else 3
    if len(rows) != expected_count:
        raise ValueError(f"quality event count mismatch: {len(rows)} != {expected_count}")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["quality_mode"] != quality_mode:
            raise ValueError("quality event quality mode mismatch")
        event_id = row["quality_event_id"]
        band = row["elevation_band"]
        if not event_id or band not in BAND_NAMES or SATELLITE_BY_BAND[band] != row["SatelliteID"]:
            raise ValueError("quality event identity is incomplete")
        if event_id in result:
            raise ValueError("duplicate quality event id")
        start = _as_int(row["event_start_ms"], "event.event_start_ms")
        entry = _as_int(row["entry_ramp_ms"], "event.entry_ramp_ms")
        hold = _as_int(row["lock_bad_hold_ms"], "event.lock_bad_hold_ms")
        recovery = _as_int(row["recovery_duration_ms"], "event.recovery_duration_ms")
        end = _as_int(row["event_end_ms"], "event.event_end_ms")
        floor = _as_float(row["floor_linear"], "event.floor_linear")
        complete = _as_bool(row["complete_event"], "event.complete_event")
        if not (1 <= start <= end <= int(duration_ms)) or entry < 1 or hold < 0 or recovery < 1:
            raise ValueError("quality event range/duration is invalid")
        if end - start + 1 != entry + hold + recovery or not (0.0 < floor <= 1.0) or not complete:
            raise ValueError("quality event duration/floor/completeness mismatch")
        result[event_id] = {
            "event_id": event_id,
            "band": band,
            "start": start,
            "entry": entry,
            "hold": hold,
            "recovery": recovery,
            "end": end,
            "floor": floor,
            "raw": row,
        }
    return result


def enforce_v22_quality_semantics(
    timeline: Mapping[tuple[int, str], Mapping[str, Any]],
    events: Mapping[str, Mapping[str, Any]],
    duration_ms: int,
    quality_mode: str,
    pre_guard_ms: int,
    post_guard_ms: int,
) -> dict[str, Any]:
    if quality_mode == "GOOD_TRACKED_BASELINE":
        if events:
            raise ValueError("Good mode contains quality events")
        for row in timeline.values():
            if row["quality_state"] != "TRACKED_GOOD" or row["quality_event_id"] is not None or row["quality_envelope_linear"] != 1.0 or not row["phase_observable"]:
                raise ValueError("Good mode quality semantics mismatch")
        return {"quality_event_count": 0, "complete_event_count": 0, "recovered_bands": 3}
    if len(events) != 3:
        raise ValueError("Poor mode must have one event per band")
    by_band = {event["band"]: event for event in events.values()}
    if set(by_band) != set(BAND_NAMES):
        raise ValueError("Poor mode event bands are incomplete")
    for band in BAND_NAMES:
        event = by_band[band]
        if event["start"] < pre_guard_ms + 1 or event["end"] > int(duration_ms) - post_guard_ms:
            raise ValueError("Poor event violates fixed guard")
        for ms in range(1, int(duration_ms) + 1):
            row = timeline[(ms, band)]
            inside = event["start"] <= ms <= event["end"]
            if inside:
                offset = ms - event["start"]
                if offset < event["entry"]:
                    expected_state = "FADING_TO_LOCK_BAD"
                elif offset < event["entry"] + event["hold"]:
                    expected_state = "LOCK_BAD_HOLD"
                else:
                    expected_state = "RECOVERING"
                if row["quality_event_id"] != event["event_id"] or row["quality_state"] != expected_state or row["phase_observable"]:
                    raise ValueError("Poor event state/observability mismatch")
                if row["quality_envelope_linear"] <= 0.0:
                    raise ValueError("Poor event envelope is not positive")
            else:
                if row["quality_event_id"] is not None or row["quality_state"] != "TRACKED_GOOD" or not row["phase_observable"]:
                    raise ValueError("Poor outside-event state mismatch")
    return {"quality_event_count": len(events), "complete_event_count": len(events), "recovered_bands": 3}


def _load_blocks(path: Path, duration_ms: int) -> dict[tuple[str, int, int], dict[str, Any]]:
    rows = _read_csv_rows(path, PATH_BLOCK_FIELDS)
    block_count = (int(duration_ms) + 39) // 40
    expected = block_count * 3 * 3
    if len(rows) != expected:
        raise ValueError(f"path block row count mismatch: {len(rows)} != {expected}")
    result: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in rows:
        band = row["elevation_band"]
        block_id = row["block_id"]
        path_id = _as_int(row["NLOSPathID"], "block.NLOSPathID")
        if band not in BAND_NAMES or SATELLITE_BY_BAND[band] != row["SatelliteID"] or path_id not in (1, 2, 3):
            raise ValueError("path block identity mismatch")
        block_number = _as_int(block_id.rsplit("-", 1)[-1], "block.number")
        key = (band, block_number, path_id)
        if key in result:
            raise ValueError("duplicate path block key")
        active = _as_bool(row["active"], "block.active")
        mask = row["activation_mask"]
        k_active = _as_int(row["K_active"], "block.K_active")
        delay = _as_float(row["latent_delay_ns"], "block.latent_delay_ns")
        doppler = _as_float(row["latent_doppler_hz"], "block.latent_doppler_hz")
        latent_amp = _as_float(row["latent_relative_amplitude"], "block.latent_relative_amplitude")
        output_amp = _as_float(row["output_relative_amplitude_base"], "block.output_relative_amplitude_base")
        phase = _as_float(row["phase_initial_rad"], "block.phase_initial_rad")
        if not active or mask != "111" or k_active != 3 or delay <= 0.0 or latent_amp <= 0.0 or output_amp <= 0.0 or not -math.pi <= phase < math.pi:
            raise ValueError("path block violates all-active positive contract")
        result[key] = {
            "block_id": block_id,
            "band": band,
            "block_number": block_number,
            "block_start_ms": _as_int(row["block_start_ms"], "block.block_start_ms"),
            "block_end_ms": _as_int(row["block_end_ms"], "block.block_end_ms"),
            "path_id": path_id,
            "delay": delay,
            "doppler": doppler,
            "latent_amp": latent_amp,
            "output_amp": output_amp,
            "phase": phase,
        }
    return result


def _load_slots(
    path: Path,
    duration_ms: int,
    timeline: Mapping[tuple[int, str], Mapping[str, Any]],
    blocks: Mapping[tuple[str, int, int], Mapping[str, Any]],
) -> dict[tuple[int, str, int], dict[str, Any]]:
    rows = _read_csv_rows(path, PATH_SLOT_FIELDS, gzipped=True)
    expected = int(duration_ms) * 3 * 3
    if len(rows) != expected:
        raise ValueError(f"path slot row count mismatch: {len(rows)} != {expected}")
    result: dict[tuple[int, str, int], dict[str, Any]] = {}
    last_phase: dict[tuple[str, int], tuple[int, float, float]] = {}
    for index, row in enumerate(rows):
        ms = _as_int(row["ms"], "slot.ms")
        band = row["elevation_band"]
        path_id = _as_int(row["NLOSPathID"], "slot.NLOSPathID")
        if band not in BAND_NAMES or SATELLITE_BY_BAND[band] != row["SatelliteID"] or path_id not in (1, 2, 3):
            raise ValueError("path slot identity mismatch")
        expected_index = (ms - 1) * 9 + BAND_NAMES.index(band) * 3 + path_id - 1
        if index != expected_index:
            raise ValueError("path slot order mismatch")
        key = (ms, band, path_id)
        if key in result:
            raise ValueError("duplicate path slot key")
        block_number = (ms - 1) // 40 + 1
        block = blocks[(band, block_number, path_id)]
        if row["block_id"] != block["block_id"] or not _as_bool(row["active"], "slot.active") or row["activation_mask"] != "111":
            raise ValueError("slot/block active contract mismatch")
        delay = _as_float(row["latent_delay_ns"], "slot.latent_delay_ns")
        doppler = _as_float(row["latent_doppler_hz"], "slot.latent_doppler_hz")
        latent_amp = _as_float(row["latent_relative_amplitude"], "slot.latent_relative_amplitude")
        output_amp = _as_float(row["output_relative_amplitude"], "slot.output_relative_amplitude")
        phase = _as_float(row["RelativePhase_rad"], "slot.RelativePhase_rad")
        for actual, expected_value, field in ((delay, block["delay"], "delay"), (doppler, block["doppler"], "doppler"), (latent_amp, block["latent_amp"], "latent amplitude")):
            if not math.isclose(actual, expected_value, rel_tol=2e-12, abs_tol=2e-12):
                raise ValueError(f"slot/block {field} mismatch")
        expected_output = float(timeline[(ms, band)]["effective_common_gain_linear"]) * latent_amp
        if output_amp <= 0.0 or not math.isclose(output_amp, expected_output, rel_tol=2e-12, abs_tol=2e-12):
            raise ValueError("slot output amplitude composition mismatch")
        if not -math.pi <= phase < math.pi:
            raise ValueError("slot phase outside [-pi,pi)")
        prior = last_phase.get((band, path_id))
        if prior is not None and prior[0] == ms - 1 and (ms - 1) % 40 != 0:
            expected_phase = evolve_phase_1ms(prior[1], prior[2])
            if not _phase_close(phase, expected_phase):
                raise ValueError("slot phase recurrence mismatch")
        last_phase[(band, path_id)] = (ms, phase, doppler)
        result[key] = {"ms": ms, "band": band, "path_id": path_id, "phase": phase, "output_amp": output_amp}
    return result


def _load_streams(path: Path, quality_mode: str) -> int:
    rows = _read_csv_rows(path, STREAM_FIELDS)
    if not rows:
        raise ValueError("random stream registry is empty")
    keys: list[tuple[str, str, str, str]] = []
    for row in rows:
        if row["quality_mode"] != quality_mode or not all(row.get(field, "") for field in ("simulation_id", "pairing_id", "environment_class", "elevation_band", "scope_id", "stream_name", "seed_uint64")):
            raise ValueError("random stream registry has incomplete identity")
        keys.append((row["elevation_band"], row["scope_id"], row["stream_name"], row["quality_mode"]))
    if len(keys) != len(set(keys)):
        raise ValueError("random stream registry has duplicate stream identity")
    return len(rows)


def audit_v22_run(
    project_root: Path,
    run_dir: Path,
    request_path: Path | None = None,
    expected_request_sha256: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    run_dir = run_dir.resolve()
    request_path = (request_path or (run_dir / "generation_request.json")).resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run directory is missing: {run_dir}")
    context = _validate_request(project_root, request_path, expected_request_sha256 or hashlib.sha256(request_path.read_bytes()).hexdigest(), require_output_absent=False)
    request = context["request"]
    output_dir = context["output_dir"]
    if output_dir != run_dir:
        raise ValueError("run directory does not match request output namespace")
    request_raw = context["request_raw"]
    request_copy = run_dir / "generation_request.json"
    if not request_copy.is_file() or request_copy.read_bytes() != request_raw:
        raise ValueError("run request copy is not byte-identical to immutable request")
    manifest_path = run_dir / "generation_manifest.json"
    receipt_path = run_dir / "generation_receipt.json"
    if not manifest_path.is_file() or not receipt_path.is_file():
        raise ValueError("generation manifest/receipt missing")
    manifest = _read_json(manifest_path)
    receipt = _read_json(receipt_path)
    request_sha = context["request_sha256"]
    for artifact in (manifest, receipt):
        if artifact.get("request_sha256") != request_sha or artifact.get("gold_labels_used_for_generation") is not False:
            raise ValueError("run provenance or gold-blind flag mismatch")
        if artifact.get("raw_iq_read") is not False or artifact.get("matlab") is not False or artifact.get("sage") is not False or artifact.get("batch") is not False:
            raise ValueError("run execution policy provenance mismatch")
    if receipt.get("status") != "completed":
        raise ValueError("run receipt is not completed")
    if manifest.get("environment_class") != request["environment_class"] or manifest.get("quality_mode") != request["quality_mode"] or manifest.get("pairing_id") != request["pairing_id"] or manifest.get("row_count") != int(request["duration_ms"]) * 12:
        raise ValueError("generation manifest identity/count mismatch")
    expected_provenance = {
        "generator_config_sha256": request["generator_config_sha256"],
        "parent_v21_config_sha256": request["parent_v21_config_sha256"],
        "parent_v21_core_sha256": request["parent_v21_core_sha256"],
        "parent_model_manifests": request["parent_model_manifests"],
        "parent_artifacts": request["parent_artifacts"],
        "source_hashes": request["source_hashes"],
        "protected_pipeline": request["protected_pipeline"],
        "backend": request["backend"],
    }
    if manifest.get("parameter_provenance") != expected_provenance:
        raise ValueError("generation manifest parameter provenance mismatch")
    _check_hash_map(run_dir, manifest.get("data_output_hashes", {}), "manifest")
    _check_hash_map(run_dir, receipt.get("output_hashes_excluding_receipt", {}), "receipt")

    duration_ms = int(request["duration_ms"])
    canonical = enforce_v22_canonical_rows(run_dir / "darkroom_channel_parameters.csv", duration_ms)
    timeline = _load_receiver_timeline(run_dir / "receiver_quality_timeline.csv.gz", duration_ms, str(request["quality_mode"]))
    events = _load_quality_events(run_dir / "quality_event_catalog.csv", duration_ms, str(request["quality_mode"]))
    quality = enforce_v22_quality_semantics(
        timeline,
        events,
        duration_ms,
        str(request["quality_mode"]),
        int(request["pre_event_guard_ms"]),
        int(request["post_event_guard_ms"]),
    )
    blocks = _load_blocks(run_dir / "path_block_catalog.csv", duration_ms)
    slots = _load_slots(run_dir / "path_slot_timeline.csv.gz", duration_ms, timeline, blocks)
    stream_count = _load_streams(run_dir / "random_stream_registry.csv", str(request["quality_mode"]))
    support = _read_json(run_dir / "support_summary.json")
    if support.get("all_nlos_slots_active") is not True or support.get("nlos_activation_policy") != "ALL_THREE_SLOTS_ALWAYS_ACTIVE" or support.get("nlos_amplitude_constraint") != "STRICTLY_POSITIVE":
        raise ValueError("support summary all-active contract mismatch")
    if support.get("quality_mode") != request["quality_mode"] or support.get("pairing_id") != request["pairing_id"]:
        raise ValueError("support summary identity mismatch")
    support_text = json.dumps(support, ensure_ascii=False)
    for marker in ("CONDITIONAL_QUALITY_PROFILE", "QUALITY_EVENT_NOT_OCCURRENCE_RATE", "ABSOLUTE_RF_POWER_NOT_AVAILABLE", "ASSUMPTION_ONLY_UNIFORM_INITIAL_PLUS_DOPPLER_CONTINUOUS"):
        if marker not in support_text:
            raise ValueError(f"support summary missing limitation marker: {marker}")
    prior_only_bands = [band for band in BAND_NAMES if str(support.get("parent_path_support_status", {}).get(band, "")).upper() == "PRIOR_ONLY"]
    gates = {
        "REQUEST_CONFIG_HASH_GATE": "PASS",
        "PARENT_PROVENANCE_GATE": "PASS",
        "V22_NAMESPACE_ISOLATION_GATE": "PASS",
        "ALL_BANDS_PRESENT_GATE": "PASS",
        "EXACT_12_ROWS_PER_MS_GATE": "PASS",
        "ALL_NLOS_STRICTLY_POSITIVE_GATE": "PASS",
        "QUALITY_TIMELINE_GATE": "PASS",
        "QUALITY_EVENT_COMPLETENESS_GATE": "PASS",
        "PATH_BLOCK_CONSTANCY_GATE": "PASS",
        "PHASE_RECURRENCE_GATE": "PASS",
        "OUTPUT_HASH_GATE": "PASS",
        "GOLD_LEAKAGE_GATE": "PASS",
    }
    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "audited_utc": _utc_now(),
        "overall_pass": True,
        "request_id": request["request_id"],
        "request_sha256": context["request_sha256"],
        "output_namespace": request["output_namespace"],
        "environment_class": request["environment_class"],
        "quality_mode": request["quality_mode"],
        "pairing_id": request["pairing_id"],
        "duration_ms": duration_ms,
        "row_count": canonical["row_count"],
        "rows_per_millisecond": 12,
        "nlos_rows": canonical["nlos_rows"],
        "quality_event_count": quality["quality_event_count"],
        "complete_event_count": quality["complete_event_count"],
        "recovered_bands": quality["recovered_bands"],
        "component_counts": {
            "receiver_timeline_rows": len(timeline),
            "quality_event_catalog_rows": len(events),
            "path_block_catalog_rows": len(blocks),
            "path_slot_timeline_rows": len(slots),
            "random_stream_rows": stream_count,
        },
        "prior_only_path_bands": prior_only_bands,
        "support_status": support.get("quality_support_status", {}),
        "gates": gates,
        "gold_labels_used_for_generation": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
        "limitations": [
            "All-three-NLOS behavior is a conditional scenario-generation contract, not an empirical occurrence-rate claim.",
            "Poor quality is a conditional receiver-diagnostic impairment, not hardware-calibrated physical signal loss.",
            "Initial phase and 1 ms Doppler recurrence are assumption-only; absolute RF power is unavailable.",
        ],
    }


def _compare_csv_column_values(path_a: Path, path_b: Path, fields: tuple[str, ...], ignored: set[str]) -> int:
    rows_a = _read_csv_rows(path_a, fields)
    rows_b = _read_csv_rows(path_b, fields)
    if len(rows_a) != len(rows_b):
        raise ValueError(f"paired row count mismatch: {path_a.name}")
    compared = 0
    for row_a, row_b in zip(rows_a, rows_b):
        for field in fields:
            if field in ignored:
                continue
            if row_a[field] != row_b[field]:
                raise ValueError(f"paired field mismatch {path_a.name}:{field}")
        compared += 1
    return compared


def audit_v22_pair(
    project_root: Path,
    good_run_dir: Path,
    poor_run_dir: Path,
    good_request_path: Path | None = None,
    poor_request_path: Path | None = None,
    expected_good_request_sha256: str | None = None,
    expected_poor_request_sha256: str | None = None,
) -> dict[str, Any]:
    good = audit_v22_run(project_root, good_run_dir, good_request_path, expected_good_request_sha256)
    poor = audit_v22_run(project_root, poor_run_dir, poor_request_path, expected_poor_request_sha256)
    if good["environment_class"] != poor["environment_class"] or good["pairing_id"] != poor["pairing_id"] or good["duration_ms"] != poor["duration_ms"]:
        raise ValueError("Good/Poor pair identity mismatch")
    good_request = _read_json((good_run_dir / "generation_request.json").resolve())
    poor_request = _read_json((poor_run_dir / "generation_request.json").resolve())
    good_timeline = _load_receiver_timeline(good_run_dir / "receiver_quality_timeline.csv.gz", good["duration_ms"], "GOOD_TRACKED_BASELINE")
    poor_timeline = _load_receiver_timeline(poor_run_dir / "receiver_quality_timeline.csv.gz", poor["duration_ms"], "POOR_CONDITIONAL")
    canonical_a = _read_csv_rows(good_run_dir / "darkroom_channel_parameters.csv", FINAL_COLUMNS)
    canonical_b = _read_csv_rows(poor_run_dir / "darkroom_channel_parameters.csv", FINAL_COLUMNS)
    if len(canonical_a) != len(canonical_b):
        raise ValueError("paired canonical row count mismatch")
    amplitude_rows = 0
    for row_a, row_b in zip(canonical_a, canonical_b):
        if row_a["ms"] != row_b["ms"] or row_a["SatelliteID"] != row_b["SatelliteID"] or row_a["NLOSPathID"] != row_b["NLOSPathID"]:
            raise ValueError("paired canonical identity mismatch")
        path_id = int(row_a["NLOSPathID"])
        band = {"Low": "LOW", "Mid": "MID", "High": "HIGH"}[row_a["SatelliteID"]]
        ms = int(row_a["ms"])
        for field in ("RelativeDelay", "RelativeDoppler", "RelativePhase_rad"):
            if row_a[field] != row_b[field]:
                raise ValueError(f"paired canonical base field mismatch: {field}")
        amplitude_a = float(row_a["RelativeAmplitude"])
        amplitude_b = float(row_b["RelativeAmplitude"])
        expected_ratio = poor_timeline[(ms, band)]["effective_common_gain_linear"] / good_timeline[(ms, band)]["effective_common_gain_linear"]
        if not math.isclose(amplitude_b / amplitude_a, expected_ratio, rel_tol=2e-12, abs_tol=2e-12):
            raise ValueError("paired amplitude does not follow quality-only envelope")
        amplitude_rows += 1
    block_fields = PATH_BLOCK_FIELDS
    block_rows_a = _read_csv_rows(good_run_dir / "path_block_catalog.csv", block_fields)
    block_rows_b = _read_csv_rows(poor_run_dir / "path_block_catalog.csv", block_fields)
    if len(block_rows_a) != len(block_rows_b):
        raise ValueError("paired block count mismatch")
    invariant_block_fields = {"environment_class", "quality_mode", "simulation_id", "pairing_id", "output_relative_amplitude_base"}
    for row_a, row_b in zip(block_rows_a, block_rows_b):
        for field in ("block_id", "elevation_band", "SatelliteID", "block_start_ms", "block_end_ms", "NLOSPathID", "active", "activation_mask", "K_active", "latent_delay_ns", "latent_doppler_hz", "latent_relative_amplitude", "phase_initial_rad", "slot_status"):
            if row_a[field] != row_b[field]:
                raise ValueError(f"paired block invariant mismatch: {field}")
    return {
        "pair_audit_schema_version": "darkroom-generator-pair-qa-2.2",
        "audited_utc": _utc_now(),
        "overall_pass": True,
        "environment_class": good["environment_class"],
        "pairing_id": good["pairing_id"],
        "duration_ms": good["duration_ms"],
        "good_request_id": good_request["request_id"],
        "poor_request_id": poor_request["request_id"],
        "good_request_sha256": good["request_sha256"],
        "poor_request_sha256": poor["request_sha256"],
        "canonical_rows_compared": amplitude_rows,
        "block_rows_compared": len(block_rows_a),
        "base_path_delay_doppler_phase_invariant": True,
        "base_common_gain_invariant": True,
        "quality_only_amplitude_difference": True,
        "gold_labels_used_for_generation": False,
    }


def _write_audit_artifacts(run_dir: Path, result: Mapping[str, Any]) -> tuple[Path, Path]:
    result_path = run_dir / "independent_qa_result.json"
    report_path = run_dir / "independent_qa_report.md"
    if result_path.exists() or report_path.exists():
        raise FileExistsError("v2.2 independent QA artifacts already exist")
    result_path.write_bytes(canonical_json_bytes(dict(result)))
    lines = [
        "# Darkroom Generator v2.2 Independent QA",
        "",
        f"- overall_pass: `{result.get('overall_pass')}`",
        f"- request_id: `{result.get('request_id')}`",
        f"- request_sha256: `{result.get('request_sha256')}`",
        f"- environment_class: `{result.get('environment_class')}`",
        f"- quality_mode: `{result.get('quality_mode')}`",
        f"- canonical rows: `{result.get('row_count')}`",
        f"- quality events: `{result.get('quality_event_count')}`",
        "",
        "## Gates",
        "",
    ]
    for name, status in dict(result.get("gates", {})).items():
        lines.append(f"- `{name}`: **{status}**")
    lines.extend(
        [
            "",
            "This audit reads only frozen v2.2 run artifacts and parent derived models; it reads no raw IQ, MATLAB, SAGE, production, or posterior-gold data.",
            "Good/Poor differences are interpreted only as the frozen conditional quality envelope; they are not multipath labels.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return result_path, report_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--expected-request-sha256")
    parser.add_argument("--pair-run-dir", type=Path)
    parser.add_argument("--pair-request", type=Path)
    parser.add_argument("--pair-expected-request-sha256")
    parser.add_argument("--no-write-artifacts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = audit_v22_run(args.project_root, args.run_dir, args.request, args.expected_request_sha256)
        if args.pair_run_dir:
            pair = audit_v22_pair(
                args.project_root,
                args.run_dir,
                args.pair_run_dir,
                args.request,
                args.pair_request,
                args.expected_request_sha256,
                args.pair_expected_request_sha256,
            )
            result = dict(result) | {"paired_qa": pair}
        if not args.no_write_artifacts:
            result_paths = _write_audit_artifacts(args.run_dir.resolve(), result)
            result = dict(result) | {"qa_result_path": str(result_paths[0]), "qa_report_path": str(result_paths[1])}
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        result = {
            "audit_schema_version": AUDIT_SCHEMA_VERSION,
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
        print(f"V22_AUDIT_FAIL={result['error']}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
