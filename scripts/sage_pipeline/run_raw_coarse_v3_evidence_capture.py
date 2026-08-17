"""Capture raw-coarse v3 per-subblock evidence without changing the v2 kernel.

The v2 NumPy debug path is the numerical authority.  This adapter extracts
auditable evidence from that path and checks its window aggregate against
``process_window_numpy``.  It is intentionally fixture-only by default: a
real raw task requires an immutable task manifest and the explicit
``--allow-real-raw`` switch, so importing or accidentally invoking this module
cannot start a formal G16 capture.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import raw_coarse_v3_common as common

try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - environment dependent
    np = None

import run_batch_sampling_raw_coarse_v1_2 as legacy
import run_batch_sampling_raw_coarse_v1_2_v2 as v2


EVIDENCE_FIELDS = [
    "task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz",
    "profile_id", "profile_family", "window_id", "recording_time_s", "tow_s",
    "sample_start_zero_based", "subblock_id", "subblock_index",
    "block_indices", "subblock_start_sample_zero_based", "subblock_start_time_s",
    "subblock_duration_ms", "nav_symbol", "nav_symbol_source",
    "continuity_status",
    "valid_sample_count", "normalization_rms", "normalization_rms_min",
    "normalization_rms_max", "main_peak_strength", "secondary_peak_strength",
    "secondary_main_ratio", "main_delay_samples", "secondary_delay_samples",
    "delay_separation_samples", "main_doppler_hz", "secondary_doppler_hz",
    "main_doppler_relative_hz", "secondary_doppler_relative_hz",
    "main_peak_index", "secondary_peak_index", "frequency_tie_break",
    "delay_tie_break", "tie_break_indices_json", "search_status", "secondary_status",
    "feature_missing_reason", "v2_parameter_hash", "parameter_hash",
    "gold_labels_used_for_selection",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _null_row(identity: Mapping[str, Any], reason: str, search_status: str, secondary_status: str = "inconclusive") -> dict[str, Any]:
    row = {field: None for field in EVIDENCE_FIELDS}
    row.update(identity)
    row.update({
        "search_status": search_status,
        "secondary_status": secondary_status,
        "feature_missing_reason": reason,
        "continuity_status": "gap" if reason == "continuity_gap" else None,
        "v2_parameter_hash": common.V2_PARAMETER_SHA256,
        "parameter_hash": common.parameter_sha256(),
        "gold_labels_used_for_selection": "false",
    })
    return row


def profile_groups(profile: legacy.CoarseProfile) -> tuple[tuple[int, ...], ...]:
    return ((0, 1), (2, 3)) if profile.family == "B1" else ((0,), (1,), (2,), (3,))


def _identity(task: Mapping[str, Any], profile: legacy.CoarseProfile, subblock_index: int, group: Sequence[int], row: legacy.Stage0Row) -> dict[str, Any]:
    first_block = int(group[0])
    subblock_start = int(row.sample_start + first_block * legacy.TEN_MS_SAMPLES)
    recording_time = row.recording_time_s
    subblock_time = recording_time + first_block * legacy.TEN_MS_SAMPLES / legacy.SAMPLE_RATE_HZ if _finite(recording_time) else None
    return {
        "task_id": task.get("task_id"),
        "scene_id": task.get("scene_id"),
        "prn": task.get("prn"),
        "tracking_channel": task.get("tracking_channel"),
        "sample_rate_hz": task.get("sample_rate_hz", legacy.SAMPLE_RATE_HZ),
        "profile_id": profile.profile_id,
        "profile_family": profile.family,
        "window_id": row.window_id,
        "recording_time_s": row.recording_time_s,
        "tow_s": row.tow_s,
        "sample_start_zero_based": row.sample_start,
        "subblock_id": f"w{row.window_id:06d}_s{subblock_index:02d}",
        "subblock_index": subblock_index,
        "block_indices": ";".join(str(index) for index in group),
        "subblock_start_sample_zero_based": subblock_start,
        "subblock_start_time_s": subblock_time,
        "subblock_duration_ms": profile.subblock_ms,
        "nav_symbol": row.nav_symbol_1 if first_block < 2 else row.nav_symbol_2,
        "nav_symbol_source": "nav_symbol_1" if first_block < 2 else "nav_symbol_2",
    }


def _raw_block_rms(view: memoryview, row: legacy.Stage0Row, chunk_start_sample: int, block_index: int) -> tuple[float | None, int | None, str | None]:
    if np is None:
        return None, None, "numpy_unavailable"
    raw = np.frombuffer(view, dtype="<i2")
    if raw.size % 2:
        return None, None, "raw_iq_alignment_invalid"
    raw = raw.reshape(-1, 2)
    step = legacy.SAMPLES_PER_CHIP * legacy.CHIP_STRIDE
    count = math.ceil(legacy.TEN_MS_SAMPLES / step)
    sample_offsets = np.arange(count, dtype=np.int64) * step
    phase_offsets = np.asarray(legacy.DELAY_PHASES, dtype=np.int64)
    local_start = int(row.sample_start - chunk_start_sample + block_index * legacy.TEN_MS_SAMPLES)
    indices = local_start + sample_offsets[:, None] + phase_offsets[None, :]
    if indices.size == 0 or int(indices.min()) < 0 or int(indices.max()) >= raw.shape[0]:
        return None, None, "raw_short"
    values = raw[indices[:, 0], :].astype(np.float64)
    complex_values = values[:, 0] + 1j * values[:, 1]
    rms = float(np.sqrt(np.mean(np.abs(complex_values) ** 2)))
    if not math.isfinite(rms) or rms <= 0:
        return None, int(count), "invalid_rms"
    return rms, int(count), None


def _failure_rows(task: Mapping[str, Any], row: legacy.Stage0Row, reason: str, status: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for profile in v2.PROFILES:
        for index, group in enumerate(profile_groups(profile)):
            result.append(_null_row(_identity(task, profile, index, group, row), reason, status))
    return result


def _stage0_continuity_status(rows: Sequence[legacy.Stage0Row], index: int) -> str:
    """Return a conservative sample-continuity state without using gold."""
    if index <= 0:
        return "ok"
    previous = rows[index - 1]
    current = rows[index]
    delta = int(current.sample_start - previous.sample_start)
    if delta <= 0:
        return "continuity_invalid"
    # Stage0 windows normally overlap.  A gap larger than one complete window
    # cannot be covered by the preceding window and must not be treated as a
    # valid temporal evidence track.
    if delta > legacy.WINDOW_SAMPLES:
        return "continuity_gap"
    return "ok"


def _metric_values(metric: Mapping[str, Any]) -> tuple[float | None, float | None, float | None, int | None, int | None, int | None]:
    main_index = metric.get("main_peak_index")
    second_index = metric.get("secondary_peak_index")
    main_power = metric.get("main_peak")
    second_power = metric.get("second_peak")
    separation = metric.get("delay_separation_samples")
    def as_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return (
        float(main_power) if _finite(main_power) else None,
        float(second_power) if _finite(second_power) else None,
        float(metric["residual_proxy"]) if _finite(metric.get("residual_proxy")) else None,
        as_int(main_index), as_int(second_index), as_int(separation),
    )


def _aggregate_from_debug(debug: Mapping[str, Any], profile: legacy.CoarseProfile) -> dict[str, Any]:
    metrics = [subblock["metric"] for subblock in debug["profiles"][profile.profile_id]["subblocks"]]
    scores = [float(metric["score_db"]) for metric in metrics]
    return {
        "coarse_main_peak": max(float(metric["main_peak"]) for metric in metrics),
        "coarse_second_peak": max(float(metric["second_peak"]) for metric in metrics),
        "residual_proxy": max(float(metric["residual_proxy"]) for metric in metrics),
        "coarse_score_db": max(scores),
        "peak_ratio_db": max(scores),
        "delay_separation_samples": max(int(metric["delay_separation_samples"]) for metric in metrics if metric["delay_separation_samples"] != ""),
    }


def assert_v2_aggregate_equivalence(view: memoryview, chunk_start_sample: int, row: legacy.Stage0Row, task: Mapping[str, Any]) -> dict[str, Any]:
    """Check the debug-derived aggregate against the unchanged v2 API."""
    if np is None:
        raise RuntimeError("NumPy is required for v3 evidence capture")
    code = v2.cached_ca_code(str(task["prn"]))
    debug = v2._numpy_debug_window(view, chunk_start_sample, row, v2.PROFILES, code)
    direct = v2.process_window_numpy(view, chunk_start_sample, row, v2.PROFILES, code)
    checks: list[dict[str, Any]] = []
    for profile in v2.PROFILES:
        derived = _aggregate_from_debug(debug, profile)
        actual = direct[profile.profile_id]
        score_delta = abs(float(derived["coarse_score_db"]) - float(actual["coarse_score_db"]))
        delay_equal = derived["delay_separation_samples"] == int(actual["delay_separation_samples"])
        checks.append({"profile_id": profile.profile_id, "score_delta": score_delta, "delay_equal": delay_equal})
        if score_delta > common.STRICT_TOLERANCES["score_db"] or not delay_equal:
            raise ValueError(f"v3/v2 aggregate mismatch for {profile.profile_id}: {checks[-1]}")
    return {"pass": True, "checks": checks, "gold_labels_used_for_selection": False}


def capture_window_evidence(
    view: memoryview,
    chunk_start_sample: int,
    row: legacy.Stage0Row,
    task: Mapping[str, Any],
    continuity_status: str = "ok",
    verify_v2_equivalence: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract one window's subblock rows from the v2-equivalent debug path."""
    if np is None:
        return _failure_rows(task, row, "numpy_unavailable", "inconclusive"), {"v2_equivalence": False}
    if continuity_status != "ok":
        return _failure_rows(task, row, "continuity_gap", "continuity_gap"), {"v2_equivalence": False}
    # Validate raw coverage and RMS before accepting any correlation metric.
    rms_by_block: list[float] = []
    valid_count_by_block: list[int] = []
    for block_index in range(4):
        rms, count, reason = _raw_block_rms(view, row, chunk_start_sample, block_index)
        if reason is not None:
            return _failure_rows(task, row, reason, reason), {"v2_equivalence": False}
        assert rms is not None and count is not None
        rms_by_block.append(rms)
        valid_count_by_block.append(count)
    try:
        code = v2.cached_ca_code(str(task["prn"]))
        debug = v2._numpy_debug_window(view, chunk_start_sample, row, v2.PROFILES, code)
        equivalence = (
            assert_v2_aggregate_equivalence(view, chunk_start_sample, row, task)
            if verify_v2_equivalence
            else {"pass": True, "checks": [], "skipped": True}
        )
    except (IndexError, EOFError, ValueError) as exc:
        return _failure_rows(task, row, f"correlation_inconclusive:{type(exc).__name__}", "inconclusive"), {"v2_equivalence": False}
    output: list[dict[str, Any]] = []
    for profile in v2.PROFILES:
        half = str(profile.doppler_half_width_hz)
        for subblock in debug["profiles"][profile.profile_id]["subblocks"]:
            subblock_index = int(subblock["subblock_index"])
            group = tuple(int(value) for value in subblock["block_indices"])
            identity = _identity(task, profile, subblock_index, group, row)
            metric = subblock["metric"]
            main_power, second_power, ratio, main_index, second_index, separation = _metric_values(metric)
            secondary_valid = second_index is not None and separation is not None and separation >= 2 and second_power is not None
            doppler_by_block: list[Mapping[str, Any]] = []
            main_dopplers: list[float] = []
            secondary_dopplers: list[float] = []
            tie_indices: list[dict[str, Any]] = []
            for block_index in group:
                block_profile = debug["blocks"][half][block_index]["profiles"][half]
                doppler_by_block.append(block_profile)
                if main_index is not None:
                    main_dopplers.append(float(block_profile["best_doppler_by_delay_hz"][main_index]))
                if secondary_valid and second_index is not None:
                    secondary_dopplers.append(float(block_profile["best_doppler_by_delay_hz"][second_index]))
                tie_indices.append({
                    "block_index": block_index,
                    "best_frequency_index_by_delay": block_profile["best_frequency_index_by_delay"],
                })
            main_doppler = sum(main_dopplers) / len(main_dopplers) if main_dopplers else None
            secondary_doppler = sum(secondary_dopplers) / len(secondary_dopplers) if secondary_dopplers else None
            row_out = dict(identity)
            row_out.update({
                "valid_sample_count": sum(valid_count_by_block[index] for index in group),
                "normalization_rms": sum(rms_by_block[index] for index in group) / len(group),
                "normalization_rms_min": min(rms_by_block[index] for index in group),
                "normalization_rms_max": max(rms_by_block[index] for index in group),
                "main_peak_strength": main_power,
                "secondary_peak_strength": second_power if secondary_valid else None,
                "secondary_main_ratio": ratio if secondary_valid else None,
                "main_delay_samples": metric.get("main_peak_delay_samples") if main_index is not None else None,
                "secondary_delay_samples": metric.get("secondary_peak_delay_samples") if secondary_valid else None,
                "delay_separation_samples": separation if secondary_valid else None,
                "main_doppler_hz": main_doppler,
                "secondary_doppler_hz": secondary_doppler if secondary_valid else None,
                "main_doppler_relative_hz": main_doppler - float(row.tracking_doppler_hz) if main_doppler is not None else None,
                "secondary_doppler_relative_hz": secondary_doppler - float(row.tracking_doppler_hz) if secondary_doppler is not None else None,
                "main_peak_index": main_index,
                "secondary_peak_index": second_index if secondary_valid else None,
                "frequency_tie_break": "first_max_in_frozen_frequency_grid",
                "delay_tie_break": "first_max_in_frozen_delay_order",
                "tie_break_indices_json": json.dumps(tie_indices, sort_keys=True, separators=(",", ":")),
                "search_status": "valid",
                "secondary_status": "admissible_delay" if secondary_valid else "none_admissible_delay",
                "feature_missing_reason": "" if secondary_valid else "none_admissible_delay",
                "continuity_status": continuity_status,
                "v2_parameter_hash": common.V2_PARAMETER_SHA256,
                "parameter_hash": common.parameter_sha256(),
                "gold_labels_used_for_selection": "false",
            })
            output.append(row_out)
    return output, {"v2_equivalence": equivalence, "gold_labels_used_for_selection": False}


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str] = EVIDENCE_FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _sha256_json(value: Any) -> str:
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")).hexdigest()


def _task_from_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    task = dict(manifest.get("task", {}))
    required = ("task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz")
    missing = [field for field in required if field not in task]
    if missing:
        raise ValueError(f"task manifest missing fields: {missing}")
    if int(task["sample_rate_hz"]) != legacy.SAMPLE_RATE_HZ:
        raise ValueError("v3 capture currently supports only 10.23MHz")
    if str(task["prn"]) not in {f"G{index:02d}" for index in range(1, 33)}:
        raise ValueError("invalid GPS PRN")
    return task


def load_task_manifest(path: Path, expected_sha256: str, project_root: Path = common.PROJECT_ROOT) -> dict[str, Any]:
    path = Path(path).resolve()
    actual = common.sha256_file(path)
    if actual.lower() != expected_sha256.lower():
        raise ValueError(f"task manifest SHA-256 mismatch: expected {expected_sha256}, got {actual}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("gold_labels_used_for_selection") is not False:
        raise ValueError("task manifest gold leakage flag is not false")
    if manifest.get("replay_after_freeze", True) is not False:
        raise ValueError("real capture manifest must prohibit posterior replay during capture")
    forbidden = json.dumps(manifest, ensure_ascii=True).lower()
    if "stage3" in forbidden or "stage4" in forbidden or "gold_event" in forbidden:
        raise ValueError("real capture task manifest contains forbidden gold/stage paths")
    task = _task_from_manifest(manifest)
    output_namespace = Path(manifest.get("output", {}).get("namespace", "")).resolve()
    allowed_root = Path(project_root).resolve() / "dataset_generation_logs" / "sampling_validation"
    if not common.is_within(output_namespace, allowed_root) or not output_namespace.name.startswith("batch_sampled_v1_3_"):
        raise ValueError("real capture output is outside the v1.3 new-only namespace")
    if output_namespace.exists():
        raise FileExistsError("real capture output namespace already exists")
    if "sage_results" in output_namespace.parts or common.is_within(output_namespace, Path(project_root).resolve() / "scenes"):
        raise ValueError("real capture output cannot be under scenes or sage_results")
    return manifest


def run_real_capture(manifest_path: Path, expected_sha256: str, project_root: Path = common.PROJECT_ROOT) -> dict[str, Any]:
    manifest = load_task_manifest(manifest_path, expected_sha256, project_root)
    task = _task_from_manifest(manifest)
    parameter_manifest = common.load_frozen_manifest(
        Path(manifest["v3_parameter_manifest"]["path"]),
        str(manifest["v3_parameter_manifest"]["sha256"]),
        project_root,
    )
    if parameter_manifest["parameter_sha256"] != manifest.get("parameter_sha256"):
        raise ValueError("task manifest parameter SHA-256 does not match frozen v3 manifest")
    legacy_task = legacy.TaskSpec(task["task_id"], "v3", task["scene_id"], task["prn"], int(task["tracking_channel"]))
    metadata, raw_path, total_samples = legacy.load_metadata_and_raw(project_root, legacy_task)
    rows = legacy.load_stage0(project_root, legacy_task, total_samples)
    inputs = manifest.get("inputs", {})
    required_input_fields = ("metadata_path", "metadata_sha256", "raw_path", "raw_sha256", "stage0_path", "stage0_sha256")
    missing_inputs = [field for field in required_input_fields if not inputs.get(field)]
    if missing_inputs:
        raise ValueError(f"immutable task manifest missing input receipts: {missing_inputs}")
    metadata_path = legacy.metadata_path(project_root, legacy_task)
    if str(inputs["metadata_path"]).lower() != str(metadata_path).lower():
        raise ValueError("task manifest metadata path does not match task")
    if common.sha256_file(metadata_path).lower() != str(inputs["metadata_sha256"]).lower():
        raise ValueError("metadata source hash mismatch")
    if str(inputs["raw_path"]).lower() != str(raw_path).lower():
        raise ValueError("task manifest raw path does not match metadata raw_iq.path")
    recorded_raw_hash = inputs["raw_sha256"]
    actual_raw_hash = common.sha256_file(raw_path)
    if actual_raw_hash.lower() != str(recorded_raw_hash).lower():
        raise ValueError("raw source hash mismatch")
    stage0_path = legacy.result_path(project_root, legacy_task) / "stage0_valid_40ms_windows.csv"
    if str(inputs["stage0_path"]).lower() != str(stage0_path).lower():
        raise ValueError("task manifest Stage0 path does not match task")
    if common.sha256_file(stage0_path) != inputs["stage0_sha256"]:
        raise ValueError("Stage0 source hash mismatch")
    output_root = common.assert_new_sampling_namespace(Path(manifest["output"]["namespace"]), project_root)
    task_payload = {**task, "sample_rate_hz": legacy.SAMPLE_RATE_HZ}
    all_rows: list[dict[str, Any]] = []
    chunk_receipt: list[dict[str, Any]] = []
    start = time.perf_counter()
    for plan, view in legacy.RawChunkReader(raw_path, rows).iter_chunks():
        chunk_start = time.perf_counter()
        for index in plan.window_indices:
            continuity = _stage0_continuity_status(rows, index)
            evidence, _diagnostic = capture_window_evidence(
                view,
                plan.start_sample,
                rows[index],
                task_payload,
                continuity_status=continuity,
                verify_v2_equivalence=False,
            )
            all_rows.extend(evidence)
        chunk_receipt.append({
            "chunk_id": plan.chunk_id,
            "start_sample": plan.start_sample,
            "bytes_read": plan.byte_count,
            "window_count": len(plan.window_indices),
            "elapsed_s": time.perf_counter() - chunk_start,
        })
    write_csv(output_root / "subblock_evidence.csv", all_rows)
    receipt = {
        "capture_type": "raw_coarse_v3_subblock_evidence",
        "created_at_utc": utc_now(),
        "manifest_path": str(Path(manifest_path).resolve()),
        "manifest_sha256": expected_sha256,
        "parameter_manifest_sha256": manifest["parameter_sha256"],
        "task": task,
        "raw_path": str(raw_path),
        "stage0_path": str(stage0_path),
        "stage0_window_count": len(rows),
        "evidence_row_count": len(all_rows),
        "chunk_count": len(chunk_receipt),
        "chunks": chunk_receipt,
        "wall_clock_s": time.perf_counter() - start,
        "gold_labels_used_for_selection": False,
        "stage3_stage4_read": False,
        "sage_called": False,
        "output_file": str((output_root / "subblock_evidence.csv").resolve()),
    }
    receipt["output_sha256"] = common.sha256_file(output_root / "subblock_evidence.csv")
    (output_root / "capture_receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (output_root / "capture_run_manifest.json").write_text(json.dumps({
        "capture_type": receipt["capture_type"],
        "manifest_sha256": receipt["manifest_sha256"],
        "parameter_manifest_sha256": receipt["parameter_manifest_sha256"],
        "task": receipt["task"],
        "evidence_schema_version": common.EVIDENCE_SCHEMA_VERSION,
        "gold_labels_used_for_selection": False,
        "stage3_stage4_read": False,
        "sage_called": False,
        "source_hashes": {
            "raw_sha256": manifest.get("inputs", {}).get("raw_sha256"),
            "stage0_sha256": manifest["inputs"]["stage0_sha256"],
        },
        "output_file": receipt["output_file"],
        "output_sha256": receipt["output_sha256"],
    }, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return receipt


def run_fixture(output_root: Path, project_root: Path = common.PROJECT_ROOT) -> dict[str, Any]:
    if np is None:
        raise RuntimeError("fixture requires NumPy to exercise the v2-equivalent kernel")
    output_root = common.assert_new_sampling_namespace(output_root, project_root)
    task = {"task_id": "fixture_v3_g16", "scene_id": "FIXTURE", "prn": "G16", "tracking_channel": 1, "sample_rate_hz": legacy.SAMPLE_RATE_HZ}
    row = legacy.Stage0Row(1, 100, 1, -1, -3000.0, 1023000.0, 100.0, 10.0)
    sample_count = legacy.WINDOW_SAMPLES + 8
    generator = np.random.default_rng(1701)
    iq = generator.integers(-2000, 2000, size=(sample_count, 2), dtype=np.int16)
    evidence, diagnostic = capture_window_evidence(memoryview(iq.tobytes()).cast("h"), 98, row, task, verify_v2_equivalence=True)
    write_csv(output_root / "subblock_evidence.csv", evidence)
    receipt = {
        "capture_type": "synthetic_fixture_only",
        "created_at_utc": utc_now(),
        "task": task,
        "evidence_row_count": len(evidence),
        "diagnostic": diagnostic,
        "raw_iq_read": False,
        "gold_labels_used_for_selection": False,
        "stage3_stage4_read": False,
        "sage_called": False,
        "fixture_seed": 1701,
    }
    (output_root / "fixture_receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=common.PROJECT_ROOT)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--task-manifest", type=Path, default=None)
    parser.add_argument("--expected-manifest-sha256", default=None)
    parser.add_argument("--allow-real-raw", action="store_true")
    parser.add_argument("--fixture", action="store_true")
    args = parser.parse_args(argv)
    output_root = args.output_root or (args.project_root / "dataset_generation_logs" / "sampling_validation" / "batch_sampled_v1_3_evidence_capture_fixture_20260812")
    if args.fixture:
        result = run_fixture(output_root, args.project_root)
        print(f"V3_FIXTURE_OUTPUT={output_root.resolve()}")
        print(f"EVIDENCE_ROWS={result['evidence_row_count']}")
        return 0
    if not args.allow_real_raw:
        raise SystemExit("REAL_RAW_CAPTURE_DISABLED: use --fixture for this offline implementation test; a future immutable task manifest plus --allow-real-raw is required")
    if args.task_manifest is None or not args.expected_manifest_sha256:
        raise SystemExit("real capture requires --task-manifest and --expected-manifest-sha256")
    receipt = run_real_capture(args.task_manifest, args.expected_manifest_sha256, args.project_root)
    print(f"V3_EVIDENCE_RECEIPT={output_root.resolve() / 'capture_receipt.json'}")
    print(f"EVIDENCE_ROWS={receipt['evidence_row_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
