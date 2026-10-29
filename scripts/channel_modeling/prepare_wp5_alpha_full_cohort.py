#!/usr/bin/env python3
"""Validate frozen Mainline Stage2 inputs and write an alpha-export manifest.

This preflight reads only small JSON/CSV metadata and the completed Stage2 MAT
file bytes for SHA-256. It never deserializes MAT/HDF5 or opens raw IQ/CIR data.
Per-run source defects are recorded as REJECTED rows so independent runs may
still proceed; a cohort/ledger global pin failure aborts before output creation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXPECTED_COHORT_SHA256 = "287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229"
EXPECTED_STAGE2_LEDGER_SHA256 = "bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551"
EXPECTED_STAGE4_PIN_MANIFEST_SHA256 = "32c10789efefe4e87cabee4ac8978cd36a4a132f4d3b5640c8e4b8b0851a635d"
EXPECTED_FROZEN_SAGE_SHA256 = "bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c"
DEFAULT_COHORT = Path("dataset_generation_logs/channel_modeling/mainline_1023_cohort_v1_20261022T082520Z/cohort.json")
DEFAULT_LEDGER = Path("dataset_generation_logs/channel_modeling/mainline_1023_model_v1_20261023T135341Z/stage2_ledger.csv")
DEFAULT_SAGE_SOURCE = Path("scripts/sage_pipeline/run_nav_sage_pipeline.m")
DEFAULT_STAGE4_PINS = Path(
    "reports/data_consolidation_20261003/mainline_1023_model_v1/"
    "stage4_joint_summary_sha256_pins_20261023.json"
)

STAGE2_FIELDS = (
    "window_id", "path_id", "selected_L", "is_multipath", "recording_time_s",
    "delay_samples", "excess_delay_samples", "excess_delay_chips",
    "excess_path_length_m", "doppler_hz", "doppler_offset_hz", "relative_power_db",
)
LEDGER_COMPARE_FIELDS = (
    "window_id", "path_id", "selected_L", "is_multipath", "recording_time_s",
    "delay_samples", "excess_delay_samples", "excess_delay_chips",
    "excess_path_length_m", "doppler_hz", "doppler_offset_hz", "relative_power_db",
)
LEDGER_REQUIRED = (
    "run_id", "scene_id", "prn", "tracking_channel", "window_id", "path_id",
    "selected_L", "is_multipath", "recording_time_s", "delay_samples",
    "excess_delay_samples", "excess_delay_chips", "excess_path_length_m",
    "doppler_hz", "doppler_offset_hz", "relative_power_db",
    "source_stage2_csv_sha256", "stage2_source_row_number",
)


@dataclass(frozen=True)
class FrozenPins:
    cohort_sha256: str
    ledger_sha256: str
    stage4_pin_manifest_sha256: str
    frozen_sage_sha256: str
    run_count: int
    path_count: int
    window_count: int
    mpc_count: int
    direct_count: int
    excluded_count: int = 6


class PreflightError(ValueError):
    """A frozen/global identity or schema prerequisite failed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreflightError(f"{label}: cannot read valid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreflightError(f"{label}: expected JSON object: {path}")
    return value


def _under_root(root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise PreflightError(f"{label}: missing relative path")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PreflightError(f"{label}: path escapes project root: {relative}") from exc
    if not path.is_file():
        raise PreflightError(f"{label}: file missing: {path}")
    return path


def _under_project(root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise PreflightError(f"{label}: missing relative path")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PreflightError(f"{label}: path escapes project root: {relative}") from exc
    return path


def _sha_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{64}", value) is None:
        raise PreflightError(f"{label}: malformed SHA-256")
    return value.lower()


def _float(row: dict[str, str], field: str, label: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise PreflightError(f"{label}: invalid numeric {field}") from exc
    if not math.isfinite(value):
        raise PreflightError(f"{label}: nonfinite numeric {field}")
    return value


def _read_csv(path: Path, required: tuple[str, ...], label: str) -> list[dict[str, str]]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise PreflightError(f"{label}: empty CSV header")
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise PreflightError(f"{label}: duplicate CSV header")
            missing = [field for field in required if field not in reader.fieldnames]
            if missing:
                raise PreflightError(f"{label}: missing fields {missing}")
            rows = list(reader)
    except OSError as exc:
        raise PreflightError(f"{label}: read failed: {exc}") from exc
    return rows


def _same_path(left: str, right: Path) -> bool:
    return str(Path(left).resolve()).casefold() == str(right.resolve()).casefold()


def _artifact_map(receipt: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    raw = receipt.get("artifact_manifest")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise PreflightError("receipt artifact_manifest has invalid type")
    artifacts: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str):
            raise PreflightError("receipt artifact_manifest has malformed entry")
        if item["relative_path"] in artifacts:
            raise PreflightError(f"receipt artifact_manifest duplicates {item['relative_path']}")
        artifacts[item["relative_path"]] = item
    return artifacts


def _verify_optional_receipt_artifact(
    artifacts: dict[str, dict[str, Any]] | None,
    relative_name: str,
    path: Path,
    label: str,
    *,
    require_if_manifest: bool = False,
) -> tuple[str, bool]:
    if artifacts is None:
        return sha256_file(path), False
    item = artifacts.get(relative_name)
    if item is None:
        if require_if_manifest:
            raise PreflightError(f"{label}: receipt manifest lacks {relative_name}")
        return sha256_file(path), False
    expected = _sha_text(item.get("sha256"), f"{label} receipt SHA")
    actual = sha256_file(path)
    if actual != expected or path.stat().st_size != int(item.get("size_bytes", -1)):
        raise PreflightError(f"{label}: current file differs from receipt artifact pin")
    return actual, True


def _run_task_preflight(
    root: Path,
    task: dict[str, Any],
    ledger_rows: list[dict[str, str]],
    stage4_pins: dict[str, Any],
    frozen: FrozenPins,
) -> dict[str, Any]:
    run_id = str(task.get("run_id", ""))
    if not run_id:
        raise PreflightError("cohort task has no run_id")
    reasons: list[str] = []
    namespace = _under_project(root, str(task.get("output_namespace", "")), f"{run_id} output namespace")
    if not namespace.is_dir():
        raise PreflightError(f"{run_id}: output namespace is missing")

    receipt_ref = task.get("relocation_receipt")
    if not isinstance(receipt_ref, dict):
        raise PreflightError(f"{run_id}: relocation receipt reference is missing")
    receipt_path = _under_root(root, str(receipt_ref.get("path", "")), f"{run_id} receipt")
    receipt_sha = sha256_file(receipt_path)
    if receipt_sha != _sha_text(receipt_ref.get("sha256"), f"{run_id} receipt pin"):
        reasons.append("RELOCATION_RECEIPT_SHA_MISMATCH")
    if receipt_path.stat().st_size != int(receipt_ref.get("size_bytes", -1)):
        reasons.append("RELOCATION_RECEIPT_SIZE_MISMATCH")
    receipt = _json(receipt_path, f"{run_id} receipt")
    expected_prn = int(re.sub(r"^G", "", str(task.get("prn", ""))))
    try:
        receipt_prn = int(str(receipt.get("prn", "")))
        receipt_channel = int(receipt.get("tracking_channel", -1))
    except (TypeError, ValueError):
        receipt_prn, receipt_channel = -1, -1
    if (
        receipt.get("scene_id") != task.get("scene_id")
        or receipt_prn != expected_prn
        or receipt_channel != int(task.get("tracking_channel", -1))
        or str(receipt.get("frozen_sage_sha256", "")).lower()
        != str(task.get("source_frozen_sage_sha256", "")).lower()
        or receipt.get("relocation_status") != "VERIFIED_SAME_VOLUME_MOVE"
        or receipt.get("resume") is not False
        or receipt.get("matlab_exit_code") != 0
        or not _same_path(str(receipt.get("final_relocated_path", "")), namespace)
    ):
        reasons.append("RELOCATION_RECEIPT_IDENTITY_OR_STATUS_MISMATCH")

    source_frozen_sha = _sha_text(task.get("source_frozen_sage_sha256"), f"{run_id} frozen SAGE SHA")
    if source_frozen_sha != frozen.frozen_sage_sha256.lower():
        reasons.append("FROZEN_SAGE_SHA_MISMATCH")
    artifacts = _artifact_map(receipt)

    stage_csvs = task.get("stage_csvs")
    if not isinstance(stage_csvs, dict):
        raise PreflightError(f"{run_id}: stage_csvs missing")
    source_paths: dict[str, Path] = {}
    source_sha: dict[str, str] = {}
    for key in ("stage2_selected_paths", "stage3_persistence", "stage4_joint_paths"):
        ref = stage_csvs.get(key)
        if not isinstance(ref, dict):
            reasons.append(f"{key.upper()}_REFERENCE_MISSING")
            continue
        path = _under_root(root, str(ref.get("path", "")), f"{run_id} {key}")
        actual = sha256_file(path)
        source_paths[key] = path
        source_sha[key] = actual
        if actual != _sha_text(ref.get("sha256"), f"{run_id} {key} cohort SHA"):
            reasons.append(f"{key.upper()}_PIN_MISMATCH")
        if path.stat().st_size != int(ref.get("size_bytes", -1)):
            reasons.append(f"{key.upper()}_SIZE_MISMATCH")
        relative_name = path.name
        _verify_optional_receipt_artifact(
            artifacts, relative_name, path, f"{run_id} {key}",
            require_if_manifest=(key == "stage2_selected_paths"),
        )

    stage2_ref = stage_csvs.get("stage2_selected_paths", {})
    stage2_path = source_paths.get("stage2_selected_paths")
    stage2_rows: list[dict[str, str]] = []
    if stage2_path:
        try:
            stage2_rows = _read_csv(stage2_path, STAGE2_FIELDS, f"{run_id} Stage2 paths")
        except PreflightError as exc:
            reasons.append("STAGE2_CSV_SCHEMA_OR_READ_FAILURE:" + str(exc))
    stage2_sha = source_sha.get("stage2_selected_paths", "")
    ledger_stage2_sha = {row.get("source_stage2_csv_sha256", "").lower() for row in ledger_rows}
    if stage2_sha and stage2_sha not in ledger_stage2_sha:
        reasons.append("STAGE2_LEDGER_SOURCE_SHA_MISMATCH")
    if stage2_rows:
        if len(stage2_rows) != len(ledger_rows):
            reasons.append("STAGE2_LEDGER_ROW_COUNT_MISMATCH")
        else:
            seen: set[tuple[int, int]] = set()
            for index, (source, ledger) in enumerate(zip(stage2_rows, ledger_rows), start=1):
                try:
                    key = (int(source["window_id"]), int(source["path_id"]))
                    ledger_key = (int(ledger["window_id"]), int(ledger["path_id"]))
                except (KeyError, TypeError, ValueError):
                    reasons.append(f"STAGE2_INVALID_KEY_ROW_{index}")
                    break
                if key in seen:
                    reasons.append(f"STAGE2_DUPLICATE_KEY_ROW_{index}")
                    break
                seen.add(key)
                if key != ledger_key:
                    reasons.append(f"STAGE2_LEDGER_KEY_OR_ORDER_MISMATCH_ROW_{index}")
                    break
                for field in LEDGER_COMPARE_FIELDS:
                    left = _float(source, field, f"{run_id} Stage2 row {index}")
                    right = _float(ledger, field, f"{run_id} ledger row {index}")
                    if abs(left - right) > 1e-12:
                        reasons.append(f"STAGE2_LEDGER_VALUE_MISMATCH_{field}_ROW_{index}")
                        break
                if reasons and reasons[-1].endswith(f"ROW_{index}"):
                    break
                if ledger.get("run_id") != run_id or ledger.get("scene_id") != str(task.get("scene_id")):
                    reasons.append(f"STAGE2_LEDGER_RUN_ID_MISMATCH_ROW_{index}")
                    break
                if ledger.get("source_stage2_csv_sha256", "").lower() != stage2_sha:
                    reasons.append(f"STAGE2_LEDGER_HASH_MISMATCH_ROW_{index}")
                    break
        counts = task.get("stage_counts_from_gate_a", {})
        direct = sum(int(row["is_multipath"]) == 0 for row in stage2_rows)
        mpc = sum(int(row["is_multipath"]) == 1 for row in stage2_rows)
        windows = len({int(row["window_id"]) for row in stage2_rows})
        if (
            len(stage2_rows) != int(counts.get("stage2_selected_path_count", -1))
            or direct != int(counts.get("direct_path_count", -1))
            or mpc != int(counts.get("stage2_mpc_count", -1))
        ):
            reasons.append("GATE_A_STAGE2_COUNTS_MISMATCH")
    else:
        direct = mpc = windows = 0

    mat_path = namespace / "stage2_nav_sage_L1_L4.mat"
    if not mat_path.is_file():
        reasons.append("STAGE2_MAT_MISSING")
        mat_sha = ""
        mat_basis = "MISSING"
        mat_bytes = 0
    else:
        mat_sha, receipt_pinned = _verify_optional_receipt_artifact(
            artifacts, mat_path.name, mat_path, f"{run_id} Stage2 MAT",
            require_if_manifest=artifacts is not None,
        )
        mat_basis = "RELOCATION_RECEIPT_ARTIFACT_MANIFEST" if receipt_pinned else "RECOMPUTED_NO_RECEIPT_PIN"
        mat_bytes = mat_path.stat().st_size

    context_path = namespace / "run_context.json"
    if not context_path.is_file():
        reasons.append("RUN_CONTEXT_MISSING")
    else:
        context = _json(context_path, f"{run_id} run_context")
        if (
            context.get("sceneId") != task.get("scene_id")
            or int(context.get("prn", -1)) != expected_prn
            or int(context.get("trackingChannel", -1)) != int(task.get("tracking_channel", -2))
            or not math.isclose(float(context.get("samplingRateHz", 0)), 10_230_000, rel_tol=0, abs_tol=1)
        ):
            reasons.append("RUN_CONTEXT_IDENTITY_MISMATCH")

    task_pin = stage4_pins.get("stage4_joint_summary_sha256_by_run_id", {}).get(run_id)
    if not isinstance(task_pin, dict):
        reasons.append("STAGE4_SUMMARY_PIN_MISSING")
        stage4_summary_path = namespace / "stage4_joint_summary.csv"
        stage4_summary_sha = ""
    else:
        stage4_summary_path = _under_root(root, str(task_pin.get("path", "")), f"{run_id} Stage4 summary")
        stage4_summary_sha = sha256_file(stage4_summary_path)
        if stage4_summary_sha != _sha_text(task_pin.get("sha256"), f"{run_id} Stage4 summary SHA"):
            reasons.append("STAGE4_SUMMARY_PIN_MISMATCH")
        if stage4_summary_path.parent != namespace:
            reasons.append("STAGE4_SUMMARY_NAMESPACE_MISMATCH")
        _verify_optional_receipt_artifact(
            artifacts, stage4_summary_path.name, stage4_summary_path, f"{run_id} Stage4 summary"
        )

    reliable_path = namespace / "stage3_reliable_centers.csv"
    if not reliable_path.is_file():
        reasons.append("STAGE3_RELIABLE_CENTERS_MISSING")
        reliable_sha = ""
    else:
        reliable_sha, _ = _verify_optional_receipt_artifact(
            artifacts, reliable_path.name, reliable_path,
            f"{run_id} Stage3 reliable centers"
        )

    status = "READY" if not reasons else "REJECTED"
    return {
        "run_id": run_id,
        "scene_id": str(task.get("scene_id", "")),
        "prn": str(task.get("prn", "")),
        "tracking_channel": int(task.get("tracking_channel", -1)),
        "sample_rate_hz": 10_230_000,
        "frozen_sage_sha256": source_frozen_sha,
        "relocation_receipt_path": str(receipt_path),
        "relocation_receipt_sha256": receipt_sha,
        "stage2_mat_path": str(mat_path),
        "stage2_mat_sha256": mat_sha,
        "mat_sha256_basis": mat_basis,
        "stage2_selected_paths_csv_path": str(source_paths.get("stage2_selected_paths", "")),
        "stage2_selected_paths_csv_sha256": stage2_sha,
        "stage3_persistence_csv_path": str(source_paths.get("stage3_persistence", "")),
        "stage3_persistence_csv_sha256": source_sha.get("stage3_persistence", ""),
        "stage3_reliable_centers_csv_path": str(reliable_path),
        "stage3_reliable_centers_csv_sha256": reliable_sha,
        "stage4_joint_summary_csv_path": str(stage4_summary_path),
        "stage4_joint_summary_csv_sha256": stage4_summary_sha,
        "stage4_joint_paths_csv_path": str(source_paths.get("stage4_joint_paths", "")),
        "stage4_joint_paths_csv_sha256": source_sha.get("stage4_joint_paths", ""),
        "expected_stage2_rows": len(stage2_rows),
        "stage2_path_rows": len(stage2_rows),
        "stage2_window_count": windows,
        "stage2_mpc_count": mpc,
        "stage2_direct_count": direct,
        "preflight_status": status,
        "preflight_reason": ";".join(reasons) if reasons else "NONE",
    }


def prepare_manifest(
    project_root: Path,
    cohort_path: Path,
    ledger_path: Path,
    stage4_pin_manifest_path: Path,
    output_dir: Path,
    frozen: FrozenPins,
) -> dict[str, Any]:
    root = project_root.resolve()
    cohort_path = cohort_path.resolve()
    ledger_path = ledger_path.resolve()
    output_dir = output_dir.resolve()
    try:
        cohort_path.relative_to(root)
        ledger_path.relative_to(root)
        output_dir.relative_to((root / "dataset_generation_logs" / "channel_modeling").resolve())
    except ValueError as exc:
        raise PreflightError("cohort, ledger and output paths must remain in their frozen project namespaces") from exc
    if output_dir.exists():
        raise PreflightError(f"output namespace already exists; refusing overwrite: {output_dir}")
    if not output_dir.parent.is_dir():
        raise PreflightError(f"output parent directory is missing: {output_dir.parent}")
    for path, expected, label in (
        (cohort_path, frozen.cohort_sha256, "cohort"),
        (ledger_path, frozen.ledger_sha256, "Stage2 ledger"),
        (stage4_pin_manifest_path.resolve(), frozen.stage4_pin_manifest_sha256, "Stage4 pin manifest"),
    ):
        if not path.is_file():
            raise PreflightError(f"{label} is missing: {path}")
        actual = sha256_file(path)
        if actual != _sha_text(expected, f"expected {label} SHA"):
            raise PreflightError(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")

    sage_source = root / DEFAULT_SAGE_SOURCE
    if not sage_source.is_file() or sha256_file(sage_source) != frozen.frozen_sage_sha256.lower():
        raise PreflightError("frozen SAGE source SHA-256 does not match the cohort pin")
    cohort = _json(cohort_path, "cohort")
    stage4_pins = _json(stage4_pin_manifest_path.resolve(), "Stage4 pin manifest")
    if (
        cohort.get("eligible_count") != frozen.run_count
        or len(cohort.get("tasks", [])) != frozen.run_count
        or cohort.get("excluded_count") != frozen.excluded_count
    ):
        raise PreflightError("frozen cohort counts do not match the approved scope")
    if (
        stage4_pins.get("cohort_sha256", "").lower() != frozen.cohort_sha256.lower()
        or stage4_pins.get("task_count") != frozen.run_count
    ):
        raise PreflightError("Stage4 pin manifest is not bound to the frozen cohort")

    ledger_rows = _read_csv(ledger_path, LEDGER_REQUIRED, "Stage2 ledger")
    if len(ledger_rows) != frozen.path_count:
        raise PreflightError(f"Stage2 ledger has {len(ledger_rows)} rows, expected {frozen.path_count}")
    by_run: dict[str, list[dict[str, str]]] = {}
    global_keys: set[tuple[str, int, int]] = set()
    all_windows: set[tuple[str, int]] = set()
    total_mpc = total_direct = 0
    for row_number, row in enumerate(ledger_rows, start=2):
        run_id = row["run_id"]
        try:
            key = (run_id, int(row["window_id"]), int(row["path_id"]))
            window = (run_id, int(row["window_id"]))
            is_mpc = int(row["is_multipath"])
        except ValueError as exc:
            raise PreflightError(f"Stage2 ledger row {row_number} has invalid identity") from exc
        if key in global_keys:
            raise PreflightError(f"Stage2 ledger has duplicate identity: {key}")
        if is_mpc not in (0, 1):
            raise PreflightError(f"Stage2 ledger row {row_number} has invalid is_multipath")
        global_keys.add(key)
        all_windows.add(window)
        total_mpc += is_mpc
        total_direct += 1 - is_mpc
        by_run.setdefault(run_id, []).append(row)
    if (
        len(by_run) != frozen.run_count
        or len(all_windows) != frozen.window_count
        or total_mpc != frozen.mpc_count
        or total_direct != frozen.direct_count
        or set(stage4_pins.get("stage4_joint_summary_sha256_by_run_id", {})) != set(by_run)
    ):
        raise PreflightError("Stage2 ledger/cohort aggregate identity counts do not match frozen totals")

    tasks = cohort["tasks"]
    task_ids = [str(task.get("run_id", "")) for task in tasks]
    if len(set(task_ids)) != frozen.run_count or set(task_ids) != set(by_run):
        raise PreflightError("cohort run identities do not exactly match the Stage2 ledger")
    rows: list[dict[str, Any]] = []
    for task in tasks:
        run_id = str(task["run_id"])
        source_rows = sorted(by_run[run_id], key=lambda row: int(row["stage2_source_row_number"]))
        rows.append(_run_task_preflight(root, task, source_rows, stage4_pins, frozen))

    output_dir.mkdir()
    manifest_path = output_dir / "input_manifest.csv"
    fields = list(rows[0]) if rows else []
    with manifest_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    summary_manifest_sha256 = sha256_file(manifest_path)
    summary = {
        "status": "PREFLIGHT_PASS" if all(r["preflight_status"] == "READY" for r in rows) else "PREFLIGHT_PARTIAL",
        "cohort_sha256": frozen.cohort_sha256.lower(),
        "stage2_ledger_sha256": frozen.ledger_sha256.lower(),
        "stage4_pin_manifest_sha256": frozen.stage4_pin_manifest_sha256.lower(),
        "frozen_sage_sha256": frozen.frozen_sage_sha256.lower(),
        "run_count": frozen.run_count,
        "ready_run_count": sum(r["preflight_status"] == "READY" for r in rows),
        "rejected_run_count": sum(r["preflight_status"] != "READY" for r in rows),
        "stage2_path_count": frozen.path_count,
        "stage2_window_count": frozen.window_count,
        "stage2_mpc_count": frozen.mpc_count,
        "stage2_direct_count": frozen.direct_count,
        "mat_sha_receipt_pinned_run_count": sum(
            r["mat_sha256_basis"] == "RELOCATION_RECEIPT_ARTIFACT_MANIFEST" for r in rows
        ),
        "mat_sha_recomputed_without_historical_pin_run_count": sum(
            r["mat_sha256_basis"] == "RECOMPUTED_NO_RECEIPT_PIN" for r in rows
        ),
        "run_failures": [
            {"run_id": r["run_id"], "reason": r["preflight_reason"]}
            for r in rows if r["preflight_status"] != "READY"
        ],
        "input_manifest": str(manifest_path),
        "input_manifest_sha256": summary_manifest_sha256,
    }
    with (output_dir / "source_preflight.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return summary


def _cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("E:/GNSS_Multipath_Project"))
    parser.add_argument("--cohort", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--stage4-pin-manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    cohort = args.cohort or (root / DEFAULT_COHORT)
    ledger = args.ledger or (root / DEFAULT_LEDGER)
    stage4_pins = args.stage4_pin_manifest or (
        Path(__file__).resolve().parents[2] / DEFAULT_STAGE4_PINS
    )
    frozen = FrozenPins(
        cohort_sha256=EXPECTED_COHORT_SHA256,
        ledger_sha256=EXPECTED_STAGE2_LEDGER_SHA256,
        stage4_pin_manifest_sha256=EXPECTED_STAGE4_PIN_MANIFEST_SHA256,
        frozen_sage_sha256=EXPECTED_FROZEN_SAGE_SHA256,
        run_count=83,
        path_count=16_761,
        window_count=7_847,
        mpc_count=8_914,
        direct_count=7_847,
        excluded_count=6,
    )
    try:
        summary = prepare_manifest(root, cohort, ledger, stage4_pins, args.output_dir, frozen)
    except PreflightError as exc:
        print(f"WP5_ALPHA_PREFLIGHT=FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["status"] == "PREFLIGHT_PASS" else 3


if __name__ == "__main__":
    raise SystemExit(_cli())
