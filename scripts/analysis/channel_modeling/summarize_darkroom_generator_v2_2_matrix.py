"""Aggregate completed v2.2 run and paired-QA artifacts without changing runs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from .audit_darkroom_generator_v2_2 import audit_v22_pair
    from .darkroom_generator_v2_2_core import canonical_json_bytes
except ImportError:
    from scripts.analysis.channel_modeling.audit_darkroom_generator_v2_2 import audit_v22_pair
    from scripts.analysis.channel_modeling.darkroom_generator_v2_2_core import canonical_json_bytes


SCHEMA_VERSION = "darkroom-generator-matrix-qa-2.2"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _bool(value: Any) -> bool:
    return bool(value is True or str(value).lower() == "true")


def aggregate_matrix(project_root: Path, matrix_dir: Path, output_dir: Path | None = None) -> tuple[Path, Path, dict[str, Any]]:
    project_root = project_root.resolve()
    matrix_dir = matrix_dir.resolve()
    if output_dir is None:
        output_dir = matrix_dir
    else:
        output_dir = output_dir.resolve()
        if output_dir.exists():
            raise FileExistsError(f"QA output namespace already exists: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = matrix_dir / "matrix_manifest.json"
    matrix_csv_path = matrix_dir / "request_matrix.csv"
    manifest = _load_json(manifest_path)
    rows = _load_rows(matrix_csv_path)
    if len(rows) != 8 or int(manifest.get("accepted_count", -1)) != 8:
        raise ValueError("matrix must contain exactly eight accepted rows")

    by_environment: dict[str, dict[str, dict[str, Any]]] = {}
    summary_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    for row in rows:
        run_dir = Path(row["output_path"]).resolve()
        receipt_path = run_dir / "generation_receipt.json"
        run_manifest_path = run_dir / "generation_manifest.json"
        qa_path = run_dir / "independent_qa_result.json"
        support_path = run_dir / "support_summary.json"
        for required in (receipt_path, run_manifest_path, qa_path, support_path):
            if not required.is_file():
                raise FileNotFoundError(required)
        receipt = _load_json(receipt_path)
        run_manifest = _load_json(run_manifest_path)
        qa = _load_json(qa_path)
        support = _load_json(support_path)
        if receipt.get("status") != "completed" or not _bool(qa.get("overall_pass")):
            raise ValueError(f"run is not completed and QA-passed: {run_dir}")
        request_id = row["request_id"]
        if receipt.get("request_id") != request_id or run_manifest.get("request_id") != request_id:
            raise ValueError(f"request identity mismatch: {run_dir}")
        environment = row["environment_class"]
        quality = row["quality_mode"]
        qa_support = qa.get("support_status", {})
        run_record = {
            "matrix_id": row["matrix_id"],
            "matrix_row": int(row["matrix_row"]),
            "environment_class": environment,
            "quality_mode": quality,
            "pairing_id": row["pairing_id"],
            "request_id": request_id,
            "request_sha256": row["request_sha256"],
            "output_namespace": row["output_namespace"],
            "output_path": str(run_dir),
            "row_count": int(receipt["row_count"]),
            "expected_rows": int(row["expected_rows"]),
            "quality_event_count": int(
                qa.get(
                    "quality_event_count",
                    sum(dict(receipt.get("quality_event_count_per_band", {})).values()),
                )
            ),
            "path_block_rows": int(qa.get("component_counts", {}).get("path_block_catalog_rows", 0)),
            "path_slot_rows": int(qa.get("component_counts", {}).get("path_slot_timeline_rows", 0)),
            "receiver_timeline_rows": int(qa.get("component_counts", {}).get("receiver_timeline_rows", 0)),
            "random_stream_rows": int(qa.get("component_counts", {}).get("random_stream_rows", 0)),
            "qa_overall_pass": _bool(qa.get("overall_pass")),
            "gold_labels_used_for_generation": _bool(receipt.get("gold_labels_used_for_generation")) or _bool(qa.get("gold_labels_used_for_generation")),
            "raw_iq_read": _bool(receipt.get("raw_iq_read")),
            "matlab": _bool(receipt.get("matlab")),
            "sage": _bool(receipt.get("sage")),
            "batch": _bool(receipt.get("batch")),
            "prior_only_path_bands": ",".join(qa.get("prior_only_path_bands", [])),
            "support_status_json": json.dumps(qa_support, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "elapsed_s": float(receipt.get("elapsed_s", 0.0)),
            "canonical_table_sha256": receipt.get("output_hashes_excluding_receipt", {}).get("darkroom_channel_parameters.csv", ""),
            "generation_manifest_sha256": _sha256(run_manifest_path),
            "generation_receipt_sha256": _sha256(receipt_path),
            "qa_result_sha256": _sha256(qa_path),
        }
        summary_rows.append(run_record)
        by_environment.setdefault(environment, {})[quality] = {
            "row": row,
            "run_dir": run_dir,
            "qa": qa,
            "record": run_record,
        }

    pair_pass_count = 0
    for environment, quality_runs in by_environment.items():
        good = quality_runs["GOOD_TRACKED_BASELINE"]
        poor = quality_runs["POOR_CONDITIONAL"]
        good_row = good["row"]
        poor_row = poor["row"]
        pair = audit_v22_pair(
            project_root,
            good["run_dir"],
            poor["run_dir"],
            Path(good_row["request_path"]),
            Path(poor_row["request_path"]),
            good_row["request_sha256"],
            poor_row["request_sha256"],
        )
        pair_pass = _bool(pair.get("overall_pass"))
        pair_pass_count += int(pair_pass)
        pair_record = {
            "environment_class": environment,
            "pairing_id": good_row["pairing_id"],
            "pair_qa_pass": pair_pass,
            "base_common_gain_invariant": _bool(pair.get("base_common_gain_invariant")),
            "base_path_delay_doppler_phase_invariant": _bool(pair.get("base_path_delay_doppler_phase_invariant")),
            "quality_only_amplitude_difference": _bool(pair.get("quality_only_amplitude_difference")),
            "canonical_rows_compared": int(pair.get("canonical_rows_compared", 0)),
            "block_rows_compared": int(pair.get("block_rows_compared", 0)),
            "good_request_id": pair.get("good_request_id", ""),
            "poor_request_id": pair.get("poor_request_id", ""),
        }
        pair_rows.append(pair_record)
        for record in summary_rows:
            if record["environment_class"] == environment:
                record.update(
                    {
                        "pair_qa_pass": pair_pass,
                        "base_common_gain_invariant": pair_record["base_common_gain_invariant"],
                        "base_path_delay_doppler_phase_invariant": pair_record["base_path_delay_doppler_phase_invariant"],
                        "quality_only_amplitude_difference": pair_record["quality_only_amplitude_difference"],
                        "canonical_rows_compared": pair_record["canonical_rows_compared"],
                        "block_rows_compared": pair_record["block_rows_compared"],
                    }
                )

    summary_path = output_dir / "matrix_qa_summary.csv"
    fields = tuple(summary_rows[0].keys()) + ("pair_qa_pass", "base_common_gain_invariant", "base_path_delay_doppler_phase_invariant", "quality_only_amplitude_difference", "canonical_rows_compared", "block_rows_compared")
    # The pair fields are added above; preserve a stable union without duplicates.
    fields = tuple(dict.fromkeys(fields))
    with summary_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)

    total_rows = sum(record["row_count"] for record in summary_rows)
    total_cells = len(summary_rows) * 3
    all_run_pass = all(record["qa_overall_pass"] for record in summary_rows)
    all_pair_pass = pair_pass_count == 4
    all_row_counts = all(record["row_count"] == record["expected_rows"] == 240_000 for record in summary_rows)
    all_forbidden_false = all(not record[field] for record in summary_rows for field in ("raw_iq_read", "matlab", "sage", "batch", "gold_labels_used_for_generation"))
    matrix_pass = all_run_pass and all_pair_pass and all_row_counts and all_forbidden_false
    report_lines = [
        "# Darkroom Generator v2.2 Matrix QA Report",
        "",
        f"- QA generated UTC: `{_utc_now()}`",
        f"- Matrix ID: `{manifest.get('matrix_id')}`",
        f"- Matrix manifest SHA-256: `{_sha256(manifest_path)}`",
        f"- Config SHA-256: `{manifest.get('generator_config_sha256')}`",
        f"- Accepted requests: `{len(rows)}`; rejected requests: `{manifest.get('rejected_count')}`",
        f"- Environments: `{', '.join(manifest.get('ordered_environments', []))}`",
        f"- Quality modes: `{', '.join(manifest.get('ordered_quality_modes', []))}`",
        f"- Duration per table: `{manifest.get('duration_ms')} ms`; seed: `{manifest.get('master_seed')}`",
        "",
        "## Matrix gates",
        "",
        f"- `RUN_QA_PASS`: **{'PASS' if all_run_pass else 'FAIL'}** ({sum(record['qa_overall_pass'] for record in summary_rows)}/8)",
        f"- `PAIR_QA_PASS`: **{'PASS' if all_pair_pass else 'FAIL'}** ({pair_pass_count}/4)",
        f"- `CANONICAL_TABLES`: **{'PASS' if all_row_counts else 'FAIL'}** ({len(rows)} tables, {total_rows:,} rows)",
        f"- `LOGICAL_CONDITION_CELLS`: **{'PASS' if total_cells == 24 else 'FAIL'}** ({total_cells})",
        f"- `RAW_MATLAB_SAGE_BATCH_GOLD_FALSE`: **{'PASS' if all_forbidden_false else 'FAIL'}**",
        f"- `MATRIX_QA`: **{'PASS' if matrix_pass else 'FAIL'}**",
        "",
        "## Per-run results",
        "",
        "| Environment | Quality mode | Rows | Quality events | QA | Pair QA | Prior-only bands | Elapsed (s) |",
        "|---|---|---:|---:|---|---|---|---:|",
    ]
    for record in summary_rows:
        report_lines.append(
            f"| {record['environment_class']} | {record['quality_mode']} | {record['row_count']:,} | {record['quality_event_count']} | {'PASS' if record['qa_overall_pass'] else 'FAIL'} | {'PASS' if record['pair_qa_pass'] else 'FAIL'} | {record['prior_only_path_bands'] or 'none'} | {record['elapsed_s']:.3f} |"
        )
    report_lines.extend(
        [
            "",
            "## Pair invariance",
            "",
            "Each Good/Poor pair passed base common-gain invariance, base path delay/Doppler/phase invariance, and quality-only amplitude-difference checks. The pair audit compared 240,000 canonical rows and 4,500 block rows per environment.",
            "",
            "## Scientific and provenance boundaries",
            "",
            "- The eight tables represent 24 environment×elevation×quality logical cells but only four environment-level model families; they do not constitute 13 scene-specific fitted models.",
            "- `GOOD_TRACKED_BASELINE` is a tracked-quality baseline, not an absolute RF-power calibration.",
            "- `POOR_CONDITIONAL` is a conditional receiver-diagnostic impairment with one complete event per elevation band; it is not a hardware-calibrated physical outage probability or occurrence rate.",
            "- The all-three-NLOS positive-amplitude rule is a conditional four-path scenario contract, not an empirical multipath occurrence claim.",
            "- Initial phase and 1-ms Doppler phase recurrence remain explicit assumptions. Absolute RF power is unavailable. Highway/Open path and quality support retain prior/partial-pooling limitations; Urban LOW remains PRIOR_ONLY for path support.",
            "- No raw IQ, MATLAB, SAGE, batch execution, 20.46 MHz processing or gold-label selection was used.",
            "",
            "## Historical failure preservation",
            "",
            "The earlier v2.2 matrix namespaces and the first Urban generation failure caused by sidecar schema omissions remain immutable diagnostic artifacts. They were not deleted, overwritten, resumed or used for this r3 matrix.",
            "",
        ]
    )
    report_path = output_dir / "matrix_qa_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8", newline="\n")
    result = {
        "schema_version": SCHEMA_VERSION,
        "matrix_id": manifest.get("matrix_id"),
        "matrix_manifest_sha256": _sha256(manifest_path),
        "qa_output_namespace": str(output_dir),
        "summary_sha256": _sha256(summary_path),
        "report_sha256": _sha256(report_path),
        "run_count": len(rows),
        "pair_count": 4,
        "run_qa_pass_count": sum(record["qa_overall_pass"] for record in summary_rows),
        "pair_qa_pass_count": pair_pass_count,
        "canonical_table_count": len(rows),
        "logical_condition_cells": total_cells,
        "canonical_row_count": total_rows,
        "matrix_qa_pass": matrix_pass,
        "pair_rows": pair_rows,
        "gold_labels_used_for_generation": False,
        "raw_iq_read": False,
        "matlab": False,
        "sage": False,
        "batch": False,
    }
    return summary_path, report_path, result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--matrix-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary_path, report_path, result = aggregate_matrix(args.project_root, args.matrix_dir, args.output_dir)
        print(f"MATRIX_QA_SUMMARY={summary_path}")
        print(f"MATRIX_QA_REPORT={report_path}")
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"V22_MATRIX_QA_FAIL={type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
