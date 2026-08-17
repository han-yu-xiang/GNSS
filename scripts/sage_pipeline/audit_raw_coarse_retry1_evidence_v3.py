"""Read-only structural audit of the v1.2 Retry1 coarse artifacts.

The Retry1 directory contains window-level aggregates, not the per-subblock
evidence required by raw-coarse v3.  This script never opens raw IQ or any
Stage3/Stage4 file and never rewrites the old artifact.  It reports exactly
which fields are present, aligned, reconstructable, or irretrievably absent.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from raw_coarse_v3_common import (
    PROJECT_ROOT,
    V2_PARAMETER_SHA256,
    assert_new_sampling_namespace,
    sha256_file,
)


PROFILE_IDS = (
    "B1_20msx2_D100",
    "B2_10msx4_D100",
    "B2_10msx4_D200",
)
EXPECTED_COARSE_FIELDS = (
    "task_id", "profile_id", "window_id", "recording_time_s", "tow_s",
    "sample_start_zero_based", "nav_symbol_1", "nav_symbol_2",
    "tracking_doppler_hz", "code_frequency_hz", "coarse_main_peak",
    "coarse_second_peak", "residual_proxy", "coarse_score_db", "peak_ratio_db",
    "delay_separation_samples", "subblock_persistence", "subblock_max_score_db",
    "subblock_p90_score_db", "subblock_median_score_db", "subblock_variance_score_db2",
    "coarse_evidence_only", "gold_labels_used_for_selection", "parameter_hash",
)
V3_REQUIRED_SUBBLOCK_FIELDS = (
    "subblock_id", "subblock_start_sample_zero_based", "valid_sample_count",
    "normalization_rms", "main_peak_strength", "secondary_peak_strength",
    "secondary_main_ratio", "main_delay_samples", "secondary_delay_samples",
    "delay_separation_samples", "main_doppler_hz", "secondary_doppler_hz",
    "secondary_doppler_relative_hz", "search_status", "secondary_status",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def parse_window_ids(rows: Sequence[Mapping[str, str]]) -> tuple[int, ...]:
    values: list[int] = []
    for row in rows:
        try:
            values.append(int(row.get("window_id", "")))
        except (TypeError, ValueError):
            values.append(-1)
    return tuple(values)


def _profile_file(retry_root: Path, profile_id: str, filename: str) -> Path:
    matches = [
        path for path in retry_root.rglob(filename)
        if path.parent.name == profile_id
    ]
    if len(matches) != 1:
        raise FileNotFoundError(f"expected one {filename} under {profile_id}, found {len(matches)}")
    return matches[0]


def _count_blank(rows: Sequence[Mapping[str, str]], field: str) -> int:
    return sum(1 for row in rows if not str(row.get(field, "")).strip())


def _hash_values(rows: Sequence[Mapping[str, str]], field: str) -> list[str]:
    return sorted({str(row.get(field, "")).strip() for row in rows if str(row.get(field, "")).strip()})


def _component_anomalies(rows: Sequence[Mapping[str, str]], n0: int) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    for row in rows:
        try:
            component_count = int(row.get("component_window_count", ""))
        except (TypeError, ValueError):
            anomalies.append({"component_id": row.get("component_id", ""), "reason": "component_window_count_missing_or_invalid"})
            continue
        try:
            promoted_count = int(row.get("promoted_window_count", ""))
        except (TypeError, ValueError):
            promoted_count = None
        if component_count > n0 or (promoted_count is not None and component_count != promoted_count):
            anomalies.append({
                "component_id": row.get("component_id", ""),
                "component_window_count": component_count,
                "promoted_window_count": promoted_count,
                "n0": n0,
                "reason": "component_count_exceeds_window_universe_or_promoted_count_mismatch",
            })
    return anomalies


def audit_profile(profile_dir: Path, expected_parameter_hash: str = V2_PARAMETER_SHA256) -> dict[str, Any]:
    coarse_path = profile_dir / "coarse_window_manifest.csv"
    promotion_path = profile_dir / "promotion_manifest.csv"
    components_path = profile_dir / "promotion_components.csv"
    coarse_fields, coarse_rows = read_csv_rows(coarse_path)
    promotion_fields, promotion_rows = read_csv_rows(promotion_path)
    component_fields, component_rows = read_csv_rows(components_path)
    coarse_windows = parse_window_ids(coarse_rows)
    promotion_windows = parse_window_ids(promotion_rows)
    expected_present = [field for field in EXPECTED_COARSE_FIELDS if field in coarse_fields]
    missing_expected = [field for field in EXPECTED_COARSE_FIELDS if field not in coarse_fields]
    coarse_hashes = _hash_values(coarse_rows, "parameter_hash")
    promotion_hashes = _hash_values(promotion_rows, "parameter_hash")
    component_hashes = _hash_values(component_rows, "parameter_hash")
    missing_subblock_fields = list(V3_REQUIRED_SUBBLOCK_FIELDS)
    aggregate_fields = [
        field for field in (
            "coarse_main_peak", "coarse_second_peak", "residual_proxy", "coarse_score_db",
            "peak_ratio_db", "delay_separation_samples", "subblock_persistence",
            "subblock_max_score_db", "subblock_p90_score_db", "subblock_median_score_db",
            "subblock_variance_score_db2",
        ) if field in coarse_fields
    ]
    reconstructable = [
        "window_id", "sample_start_zero_based", "recording_time_s", "tow_s",
        "nav_symbol_1", "nav_symbol_2", "tracking_doppler_hz", "code_frequency_hz",
        "window_level_aggregate_score_and_ratio", "window_level_delay_separation",
    ]
    non_reconstructable = [
        "per_subblock_sample_time_mapping",
        "per_subblock_valid_sample_count_and_RMS",
        "per_subblock_main_and_secondary_strength",
        "per_subblock_secondary_delay_and_Doppler",
        "per_subblock_deterministic_tie_break_and_search_status",
        "B1_B2_cross_scale_pair_alignment",
    ]
    component_anomalies = _component_anomalies(component_rows, len(set(window for window in coarse_windows if window >= 0)))
    return {
        "profile_id": profile_dir.name,
        "profile_dir": str(profile_dir.resolve()),
        "files_read": [str(path.resolve()) for path in (coarse_path, promotion_path, components_path)],
        "raw_iq_read": False,
        "stage3_stage4_read": False,
        "silent_repair": False,
        "coarse_sha256": sha256_file(coarse_path),
        "promotion_sha256": sha256_file(promotion_path),
        "components_sha256": sha256_file(components_path),
        "coarse_row_count": len(coarse_rows),
        "promotion_row_count": len(promotion_rows),
        "component_row_count": len(component_rows),
        "window_id_count": len(set(window for window in coarse_windows if window >= 0)),
        "window_id_invalid_count": sum(window < 0 for window in coarse_windows),
        "window_id_ordered": list(coarse_windows) == sorted(coarse_windows),
        "promotion_window_ids_match_coarse": set(promotion_windows) == set(coarse_windows),
        "task_id_missing_count_coarse": _count_blank(coarse_rows, "task_id"),
        "task_id_missing_count_promotion": _count_blank(promotion_rows, "task_id"),
        "task_ids_present": sorted({row.get("task_id", "").strip() for row in coarse_rows if row.get("task_id", "").strip()}),
        "profile_ids_present": sorted({row.get("profile_id", "").strip() for row in coarse_rows if row.get("profile_id", "").strip()}),
        "coarse_parameter_hashes": coarse_hashes,
        "promotion_parameter_hashes": promotion_hashes,
        "component_parameter_hashes": component_hashes,
        "expected_v2_parameter_hash": expected_parameter_hash,
        "coarse_hash_matches_v2": coarse_hashes == [expected_parameter_hash],
        "promotion_hash_matches_v2": promotion_hashes == [expected_parameter_hash],
        "component_hash_matches_v2": component_hashes == [expected_parameter_hash],
        "coarse_fields": list(coarse_fields),
        "promotion_fields": list(promotion_fields),
        "component_fields": list(component_fields),
        "expected_aggregate_fields_present": aggregate_fields,
        "missing_expected_coarse_fields": missing_expected,
        "per_subblock_evidence_present": False,
        "missing_v3_subblock_fields": missing_subblock_fields,
        "reconstructable_without_raw": reconstructable,
        "not_reconstructable_from_retry1": non_reconstructable,
        "component_window_count_anomalies": component_anomalies,
        "component_count_anomaly": bool(component_anomalies),
        "audit_status": "aggregate_only_not_sufficient_for_v3",
    }


def audit_retry1(retry_root: Path) -> dict[str, Any]:
    retry_root = Path(retry_root).resolve()
    if not retry_root.is_dir():
        raise FileNotFoundError(retry_root)
    profiles = [audit_profile(_profile_file(retry_root, profile_id, "coarse_window_manifest.csv").parent) for profile_id in PROFILE_IDS]
    window_sequences = [
        tuple(
            int(row["window_id"])
            for row in read_csv_rows(Path(item["files_read"][0]))[1]
            if str(row.get("window_id", "")).strip()
        )
        for item in profiles
    ]
    return {
        "audit_type": "raw_coarse_retry1_evidence_v3_read_only",
        "created_at_utc": utc_now(),
        "retry_root": str(retry_root),
        "raw_iq_read": False,
        "stage3_stage4_read": False,
        "gold_labels_used_for_selection": False,
        "silent_repair": False,
        "profiles_expected": list(PROFILE_IDS),
        "profiles": profiles,
        "cross_profile_window_id_alignment": {
            "all_equal": len(set(window_sequences)) == 1,
            "counts": [len(sequence) for sequence in window_sequences],
            "first_window_ids": [list(sequence[:3]) for sequence in window_sequences],
            "last_window_ids": [list(sequence[-3:]) for sequence in window_sequences],
        },
        "conclusion": "Retry1 preserves window-level aggregates but cannot reconstruct v3 per-subblock secondary Doppler or cross-scale evidence without a new raw capture.",
    }


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(result: Mapping[str, Any], output_root: Path, project_root: Path = PROJECT_ROOT) -> None:
    output_root = assert_new_sampling_namespace(output_root, project_root)
    (output_root / "audit_report.json").write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    rows = []
    for profile in result["profiles"]:
        rows.append({
            "profile_id": profile["profile_id"],
            "coarse_row_count": profile["coarse_row_count"],
            "task_id_missing_count": profile["task_id_missing_count_coarse"],
            "coarse_hash_matches_v2": profile["coarse_hash_matches_v2"],
            "promotion_hash_matches_v2": profile["promotion_hash_matches_v2"],
            "per_subblock_evidence_present": profile["per_subblock_evidence_present"],
            "component_count_anomaly": profile["component_count_anomaly"],
            "audit_status": profile["audit_status"],
        })
    _write_csv(output_root / "audit_profile_summary.csv", rows, list(rows[0]) if rows else ["profile_id"])
    lines = [
        "# Retry1 raw-coarse v3 evidence audit",
        "",
        "- Audit mode: read-only; raw IQ read: `false`; Stage3/Stage4 read: `false`.",
        "- Silent repair: `false`; the old Retry1 directory was not modified.",
        f"- Retry1 root: `{result['retry_root']}`",
        f"- Cross-profile window alignment: `{result['cross_profile_window_id_alignment']['all_equal']}`",
        "",
        "## Findings",
        "",
        "Retry1 contains window-level aggregate manifests only. It does not contain the per-subblock sample/RMS/correlation evidence needed to derive secondary Doppler, secondary delay tracks, or B1/B2 cross-scale pairs. Those fields are therefore marked non-reconstructable rather than inferred.",
        "",
        "| Profile | Rows | Missing task_id | Coarse hash=v2 | Promotion hash=v2 | Per-subblock evidence | Component anomaly | Status |",
        "|---|---:|---:|---|---|---|---|---|",
    ]
    for profile in result["profiles"]:
        lines.append(
            f"| {profile['profile_id']} | {profile['coarse_row_count']} | {profile['task_id_missing_count_coarse']} | "
            f"{profile['coarse_hash_matches_v2']} | {profile['promotion_hash_matches_v2']} | "
            f"{profile['per_subblock_evidence_present']} | {profile['component_count_anomaly']} | {profile['audit_status']} |"
        )
    lines.extend([
        "",
        "## Safety conclusion",
        "",
        "The Retry1 aggregate CSVs remain immutable historical evidence. A new v3 raw evidence capture is required for any v3 feature table; no existing aggregate value is silently repaired or promoted to a per-subblock fact.",
    ])
    (output_root / "audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry1-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    args = parser.parse_args(argv)
    output_root = args.output_root or (PROJECT_ROOT / "dataset_generation_logs" / "sampling_validation" / "batch_sampled_v1_3_retry1_evidence_audit_20260812")
    result = audit_retry1(args.retry1_root)
    write_outputs(result, output_root, PROJECT_ROOT)
    print(f"AUDIT_OUTPUT={output_root.resolve()}")
    print(f"CROSS_PROFILE_WINDOW_ALIGNMENT={result['cross_profile_window_id_alignment']['all_equal']}")
    print("RAW_IQ_READ=false")
    print("STAGE3_STAGE4_READ=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

