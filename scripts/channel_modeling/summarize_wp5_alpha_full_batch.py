#!/usr/bin/env python3
"""Create a small per-run output/hash manifest for a completed WP5 alpha batch.

This is a provenance/reporting step only: it does not read MAT files, change
science outputs, or recompute alpha. It hashes the generated CSV outputs and
binds their row counts to the batch and independent-validation receipts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


class SummaryError(ValueError):
    """The batch receipts or output files do not form a consistent full batch."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SummaryError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SummaryError(f"expected JSON object: {path}")
    return value


def read_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise SummaryError(f"missing or duplicate CSV header: {path}")
            return list(reader)
    except OSError as exc:
        raise SummaryError(f"cannot read CSV {path}: {exc}") from exc


def count_csv_rows(path: Path) -> int:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        next(reader, None)
        return sum(1 for _ in reader)


def count_alpha_states(path: Path) -> tuple[int, int, int, int]:
    available = missing = power_pass = power_mismatch = 0
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"alpha_status", "relative_power_check_status"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise SummaryError(f"alpha CSV lacks status columns: {path}")
        for row in reader:
            available += row["alpha_status"] == "AVAILABLE"
            missing += row["alpha_status"] == "MISSING"
            power_pass += row["relative_power_check_status"] == "PASS"
            power_mismatch += row["relative_power_check_status"] == "MISMATCH"
    return available, missing, power_pass, power_mismatch


def relative_path(path_text: str, root: Path, label: str) -> str:
    path = Path(path_text).resolve()
    try:
        return path.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise SummaryError(f"{label} escapes expected root: {path_text}") from exc


def summarize_outputs(project_root: Path, output_root: Path, report_dir: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    report_dir = report_dir.resolve()
    if not output_root.is_dir():
        raise SummaryError(f"output root does not exist: {output_root}")
    if report_dir.exists():
        raise SummaryError(f"report directory already exists; refusing overwrite: {report_dir}")

    required_files = (
        "input_manifest.csv", "source_preflight.json", "batch_export_summary.json",
        "run_export_audit.csv", "independent_validation_per_run.csv",
        "independent_validation_summary.json", "stage2_alpha_all_paths.csv",
        "stage2_modeling_ledger_all_paths.csv",
    )
    for name in required_files:
        if not (output_root / name).is_file():
            raise SummaryError(f"required batch evidence is missing: {output_root / name}")

    manifest_path = output_root / "input_manifest.csv"
    manifest_sha = sha256_file(manifest_path)
    manifest = read_rows(manifest_path)
    preflight = read_json(output_root / "source_preflight.json")
    batch = read_json(output_root / "batch_export_summary.json")
    validation = read_json(output_root / "independent_validation_summary.json")
    audit = read_rows(output_root / "run_export_audit.csv")
    validated_runs = read_rows(output_root / "independent_validation_per_run.csv")

    if batch.get("status") != "COMPLETE" or validation.get("status") != "PASS":
        raise SummaryError("batch and independent validation must both be successful")
    if not (manifest_sha.lower() == str(batch.get("input_manifest_sha256", "")).lower()
            == str(validation.get("input_manifest_sha256", "")).lower()):
        raise SummaryError("manifest SHA differs across batch or validation evidence")
    run_ids = [row.get("run_id", "") for row in manifest]
    if not run_ids or len(run_ids) != len(set(run_ids)):
        raise SummaryError("input manifest has no runs or duplicate run_id")
    if len(audit) != len(run_ids) or len(validated_runs) != len(run_ids):
        raise SummaryError("per-run manifest, export audit and validation counts differ")
    audit_by_id = {row.get("run_id", ""): row for row in audit}
    validation_by_id = {row.get("run_id", ""): row for row in validated_runs}
    if set(audit_by_id) != set(run_ids) or set(validation_by_id) != set(run_ids):
        raise SummaryError("run identities differ between manifest, audit and validation")

    output_records: list[dict[str, Any]] = []
    alpha_bytes = ledger_bytes = total_alpha = total_missing = 0
    total_power_pass = total_power_mismatch = total_rows = 0
    for source in manifest:
        run_id = source["run_id"]
        exported = audit_by_id[run_id]
        validated = validation_by_id[run_id]
        if exported.get("status") != "EXPORTED" or validated.get("status") != "PASS":
            raise SummaryError(f"run did not pass export and independent validation: {run_id}")

        expected_run_dir = (output_root / run_id).resolve()
        alpha_path = expected_run_dir / "stage2_alpha.csv"
        ledger_path = expected_run_dir / "stage2_modeling_ledger.csv"
        if Path(exported.get("alpha_output_path", "")).resolve() != alpha_path.resolve():
            raise SummaryError(f"alpha output path differs from batch namespace: {run_id}")
        if Path(exported.get("modeling_ledger_path", "")).resolve() != ledger_path.resolve():
            raise SummaryError(f"ledger output path differs from batch namespace: {run_id}")
        if not alpha_path.is_file() or not ledger_path.is_file():
            raise SummaryError(f"per-run output is missing: {run_id}")

        alpha_rows = count_csv_rows(alpha_path)
        ledger_rows = count_csv_rows(ledger_path)
        available, missing, power_pass, power_mismatch = count_alpha_states(alpha_path)
        expected_rows = int(source["stage2_path_rows"])
        if alpha_rows != expected_rows or ledger_rows != expected_rows:
            raise SummaryError(f"per-run output row count differs from input: {run_id}")
        if int(exported["stage2_path_rows"]) != expected_rows:
            raise SummaryError(f"run audit row count differs from input: {run_id}")
        if (available != int(exported["alpha_available_count"])
                or missing != int(exported["alpha_missing_count"])
                or power_pass != int(exported["relative_power_pass_count"])
                or power_mismatch != int(exported["relative_power_mismatch_count"])):
            raise SummaryError(f"per-run status counts differ from export audit: {run_id}")

        output_records.append({
            "run_id": run_id,
            "scene_id": source["scene_id"],
            "prn": source["prn"],
            "tracking_channel": source["tracking_channel"],
            "preflight_status": source["preflight_status"],
            "export_status": exported["status"],
            "independent_validation_status": validated["status"],
            "mat_sha256_basis": source["mat_sha256_basis"],
            "stage2_mat_sha256": source["stage2_mat_sha256"],
            "stage2_selected_paths_csv_sha256": source["stage2_selected_paths_csv_sha256"],
            "stage2_path_rows": expected_rows,
            "stage2_window_count": source["stage2_window_count"],
            "stage2_mpc_count": source["stage2_mpc_count"],
            "stage2_direct_count": source["stage2_direct_count"],
            "alpha_available_count": available,
            "alpha_missing_count": missing,
            "relative_power_pass_count": power_pass,
            "relative_power_mismatch_count": power_mismatch,
            "alpha_output_relative_path": f"{run_id}/stage2_alpha.csv",
            "alpha_output_sha256": sha256_file(alpha_path),
            "alpha_output_size_bytes": alpha_path.stat().st_size,
            "alpha_rows": alpha_rows,
            "ledger_output_relative_path": f"{run_id}/stage2_modeling_ledger.csv",
            "ledger_output_sha256": sha256_file(ledger_path),
            "ledger_output_size_bytes": ledger_path.stat().st_size,
            "ledger_rows": ledger_rows,
            "stage2_mat_relative_path": relative_path(source["stage2_mat_path"], project_root, run_id),
            "stage2_selected_paths_relative_path": relative_path(
                source["stage2_selected_paths_csv_path"], project_root, run_id),
        })
        alpha_bytes += alpha_path.stat().st_size
        ledger_bytes += ledger_path.stat().st_size
        total_rows += alpha_rows
        total_alpha += available
        total_missing += missing
        total_power_pass += power_pass
        total_power_mismatch += power_mismatch

    if total_rows != int(batch["stage2_path_count"]):
        raise SummaryError("sum of per-run output rows differs from batch total")
    if (
        total_alpha != int(validation["alpha_available_count"])
        or total_missing != int(validation["alpha_missing_count"])
        or total_power_mismatch != int(validation["relative_power_mismatch_count"])
    ):
        raise SummaryError("per-run alpha/power status totals differ from independent validation")

    combined_alpha = output_root / "stage2_alpha_all_paths.csv"
    combined_ledger = output_root / "stage2_modeling_ledger_all_paths.csv"
    combined_alpha_rows = count_csv_rows(combined_alpha)
    combined_ledger_rows = count_csv_rows(combined_ledger)
    if combined_alpha_rows != total_rows or combined_ledger_rows != total_rows:
        raise SummaryError("combined output row counts differ from per-run outputs")

    report_dir.mkdir(parents=True, exist_ok=False)
    per_run_path = report_dir / "per_run_output_manifest.csv"
    fields = list(output_records[0])
    with per_run_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_records)

    report = {
        "status": "PASS",
        "generated_from_existing_outputs_only": True,
        "input_manifest_sha256": manifest_sha,
        "cohort_sha256": preflight["cohort_sha256"],
        "stage2_ledger_sha256": preflight["stage2_ledger_sha256"],
        "stage4_pin_manifest_sha256": preflight["stage4_pin_manifest_sha256"],
        "frozen_sage_sha256": preflight["frozen_sage_sha256"],
        "run_count": len(run_ids),
        "stage2_path_count": total_rows,
        "stage2_window_count": int(batch["stage2_window_count"]),
        "stage2_mpc_count": int(batch["stage2_mpc_count"]),
        "stage2_direct_count": int(batch["stage2_direct_count"]),
        "alpha_available_count": total_alpha,
        "alpha_missing_count": total_missing,
        "relative_power_pass_count": total_power_pass,
        "relative_power_mismatch_count": total_power_mismatch,
        "mat_sha_receipt_pinned_run_count": preflight[
            "mat_sha_receipt_pinned_run_count"],
        "mat_sha_recomputed_without_historical_pin_run_count": preflight[
            "mat_sha_recomputed_without_historical_pin_run_count"],
        "combined_alpha": {
            "path": "stage2_alpha_all_paths.csv",
            "sha256": sha256_file(combined_alpha),
            "size_bytes": combined_alpha.stat().st_size,
            "rows": combined_alpha_rows,
        },
        "combined_modeling_ledger": {
            "path": "stage2_modeling_ledger_all_paths.csv",
            "sha256": sha256_file(combined_ledger),
            "size_bytes": combined_ledger.stat().st_size,
            "rows": combined_ledger_rows,
        },
        "per_run_output_manifest": per_run_path.name,
        "per_run_output_manifest_sha256": sha256_file(per_run_path),
        "per_run_output_manifest_rows": len(output_records),
        "per_run_science_csv_bytes": alpha_bytes + ledger_bytes,
        "combined_science_csv_bytes": combined_alpha.stat().st_size + combined_ledger.stat().st_size,
    }
    summary_path = report_dir / "wp5_alpha_full_summary.json"
    with summary_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    result = summarize_outputs(args.project_root, args.output_root, args.report_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
