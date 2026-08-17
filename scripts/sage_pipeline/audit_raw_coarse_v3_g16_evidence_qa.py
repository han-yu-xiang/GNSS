"""Gold-blind QA for one completed raw-coarse v3 evidence capture.

The audit consumes only the completed subblock evidence, its capture receipts,
the immutable task manifest, the frozen v3 parameter manifest, and the Stage0
window catalog.  It never opens raw IQ and has no reader for later SAGE stages
or posterior labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import raw_coarse_v3_common as common


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TASK = {
    "scene_id": "F1023_V70_D0120_P7",
    "prn": "G16",
    "tracking_channel": "1",
    "sample_rate_hz": "10230000",
}
EXPECTED_WINDOW_COUNT = 2229
EXPECTED_PROFILE_COUNTS = {
    "B1_20msx2_D100": 4458,
    "B2_10msx4_D100": 8916,
    "B2_10msx4_D200": 8916,
}
EXPECTED_SUBBLOCKS = {
    "B1_20msx2_D100": 2,
    "B2_10msx4_D100": 4,
    "B2_10msx4_D200": 4,
}
EXPECTED_BLOCKS = {
    "B1_20msx2_D100": {"0": (0, 1), "1": (2, 3)},
    "B2_10msx4_D100": {"0": (0,), "1": (1,), "2": (2,), "3": (3,)},
    "B2_10msx4_D200": {"0": (0,), "1": (1,), "2": (2,), "3": (3,)},
}
NUMERIC_FIELDS = (
    "recording_time_s", "tow_s", "sample_start_zero_based", "subblock_start_sample_zero_based",
    "subblock_start_time_s", "valid_sample_count", "normalization_rms", "normalization_rms_min",
    "normalization_rms_max", "main_peak_strength", "secondary_peak_strength", "secondary_main_ratio",
    "main_delay_samples", "secondary_delay_samples", "delay_separation_samples", "main_doppler_hz",
    "secondary_doppler_hz", "main_doppler_relative_hz", "secondary_doppler_relative_hz",
    "main_peak_index", "secondary_peak_index",
)
ALLOWED_SEARCH_STATUS = {"valid", "inconclusive", "missing"}
ALLOWED_SECONDARY_STATUS = {"admissible_delay", "none_admissible_delay", "inconclusive", "missing"}
ALLOWED_MISSING_REASONS = {"", "none_admissible_delay", "raw_short", "invalid_rms", "continuity_gap", "inconclusive", "missing"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return common.sha256_file(Path(path))


def parse_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def parse_int(value: Any) -> int | None:
    parsed = parse_float(value)
    return int(parsed) if parsed is not None and parsed.is_integer() else None


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _status_counts(rows: Iterable[Mapping[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field, "")) for row in rows).items()))


def _finite_field_issues(rows: Iterable[Mapping[str, str]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=2):
        for field in NUMERIC_FIELDS:
            raw = row.get(field, "")
            if str(raw).strip() and parse_float(raw) is None:
                issues.append({"csv_line": row_index, "field": field, "value": raw})
    return issues


def _distribution(values: Iterable[float]) -> dict[str, Any]:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return {"count": 0, "min": None, "p01": None, "p50": None, "p99": None, "max": None, "mean": None}

    def quantile(q: float) -> float:
        position = q * (len(ordered) - 1)
        low = int(math.floor(position))
        high = int(math.ceil(position))
        if low == high:
            return ordered[low]
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    return {
        "count": len(ordered),
        "min": ordered[0],
        "p01": quantile(0.01),
        "p50": quantile(0.50),
        "p99": quantile(0.99),
        "max": ordered[-1],
        "mean": statistics.fmean(ordered),
    }


def _load_stage0(path: Path) -> dict[int, dict[str, str]]:
    _fields, rows = read_csv(path)
    if len(rows) != EXPECTED_WINDOW_COUNT:
        raise ValueError(f"Stage0 count is {len(rows)}, expected {EXPECTED_WINDOW_COUNT}")
    result: dict[int, dict[str, str]] = {}
    for row in rows:
        window_id = parse_int(row.get("window_id"))
        if window_id is None or window_id in result:
            raise ValueError("Stage0 window IDs are invalid or duplicated")
        result[window_id] = row
    expected = set(range(1, EXPECTED_WINDOW_COUNT + 1))
    if set(result) != expected:
        raise ValueError("Stage0 window IDs are not exactly 1..2229")
    return result


def _check_manifest_receipts(manifest: Mapping[str, Any], receipt: Mapping[str, Any], run_manifest: Mapping[str, Any], manifest_path: Path, evidence_path: Path, stage0_path: Path) -> dict[str, Any]:
    actual_manifest_sha = sha256_file(manifest_path)
    evidence_sha = sha256_file(evidence_path)
    checks = {
        "manifest_sha_matches_receipt": actual_manifest_sha.lower() == str(receipt.get("manifest_sha256", "")).lower(),
        "manifest_sha_matches_run_manifest": actual_manifest_sha.lower() == str(run_manifest.get("manifest_sha256", "")).lower(),
        "parameter_sha_matches_receipt": receipt.get("parameter_manifest_sha256") == common.parameter_sha256(),
        "parameter_sha_matches_run_manifest": run_manifest.get("parameter_manifest_sha256") == common.parameter_sha256(),
        "evidence_sha_matches_run_manifest": evidence_sha.lower() == str(run_manifest.get("output_sha256", "")).lower(),
        "evidence_path_matches_receipt": str(evidence_path.resolve()).lower() == str(receipt.get("output_file", "")).lower(),
        "stage0_path_matches_receipt": str(stage0_path.resolve()).lower() == str(receipt.get("stage0_path", "")).lower(),
        "capture_type_is_real_evidence": receipt.get("capture_type") == "raw_coarse_v3_subblock_evidence",
        "gold_free_receipt": receipt.get("gold_labels_used_for_selection") is False,
        "gold_free_run_manifest": run_manifest.get("gold_labels_used_for_selection") is False,
        "no_later_stage_read": receipt.get("stage3_stage4_read") is False and run_manifest.get("stage3_stage4_read") is False,
        "no_sage_called": receipt.get("sage_called") is False and run_manifest.get("sage_called") is False,
    }
    return {"checks": checks, "all_pass": all(checks.values()), "actual_manifest_sha256": actual_manifest_sha, "evidence_sha256": evidence_sha}


def audit(evidence_path: Path, receipt_path: Path, run_manifest_path: Path, stage0_path: Path, manifest_path: Path, output_root: Path, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    evidence_path = Path(evidence_path).resolve()
    receipt_path = Path(receipt_path).resolve()
    run_manifest_path = Path(run_manifest_path).resolve()
    stage0_path = Path(stage0_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    for path in (evidence_path, receipt_path, run_manifest_path, stage0_path, manifest_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    receipt = read_json(receipt_path)
    run_manifest = read_json(run_manifest_path)
    task_manifest = read_json(manifest_path)
    stage0 = _load_stage0(stage0_path)
    fields, rows = read_csv(evidence_path)
    expected_fields = {
        "task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "profile_id", "window_id",
        "subblock_index", "block_indices", "subblock_duration_ms", "nav_symbol", "nav_symbol_source",
        "continuity_status", "valid_sample_count", "normalization_rms", "main_peak_strength",
        "secondary_peak_strength", "secondary_main_ratio", "main_delay_samples", "secondary_delay_samples",
        "delay_separation_samples", "main_doppler_hz", "secondary_doppler_hz", "main_doppler_relative_hz",
        "secondary_doppler_relative_hz", "main_peak_index", "secondary_peak_index", "frequency_tie_break",
        "delay_tie_break", "tie_break_indices_json", "search_status", "secondary_status", "feature_missing_reason",
        "v2_parameter_hash", "parameter_hash", "gold_labels_used_for_selection",
    }
    schema_missing = sorted(expected_fields - set(fields))
    receipt_checks = _check_manifest_receipts(task_manifest, receipt, run_manifest, manifest_path, evidence_path, stage0_path)
    count_by_profile = Counter(row.get("profile_id", "") for row in rows)
    count_by_window_profile = Counter((parse_int(row.get("window_id")), row.get("profile_id", "")) for row in rows)
    key_counts = Counter((parse_int(row.get("window_id")), row.get("profile_id", ""), parse_int(row.get("subblock_index"))) for row in rows)
    identity_issues: list[dict[str, Any]] = []
    status_issues: list[dict[str, Any]] = []
    null_issues: list[dict[str, Any]] = []
    mapping_issues: list[dict[str, Any]] = []
    tie_break_issues: list[dict[str, Any]] = []
    delay_issues: list[dict[str, Any]] = []
    doppler_issues: list[dict[str, Any]] = []
    continuity_counts = Counter()
    profile_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    profile_boundary_counts: Counter[tuple[str, str, str]] = Counter()
    exact_profile_pair_counts = Counter()
    rows_by_key: dict[tuple[int, str, int], Mapping[str, str]] = {}
    for row_index, row in enumerate(rows, start=2):
        window_id = parse_int(row.get("window_id"))
        profile = row.get("profile_id", "")
        subblock = parse_int(row.get("subblock_index"))
        key = (window_id, profile, subblock)
        if key_counts[key] > 1:
            identity_issues.append({"csv_line": row_index, "issue": "duplicate_window_profile_subblock", "key": key})
        rows_by_key.setdefault(key, row)
        for field, expected in EXPECTED_TASK.items():
            if str(row.get(field, "")) != expected:
                identity_issues.append({"csv_line": row_index, "field": field, "actual": row.get(field), "expected": expected})
        if profile not in EXPECTED_SUBBLOCKS or subblock is None or not (0 <= subblock < EXPECTED_SUBBLOCKS.get(profile, 0)):
            mapping_issues.append({"csv_line": row_index, "issue": "unknown_profile_or_subblock", "profile": profile, "subblock": subblock})
            continue
        expected_blocks = EXPECTED_BLOCKS[profile][str(subblock)]
        actual_blocks = tuple(int(item) for item in str(row.get("block_indices", "")).split(";") if item != "")
        if actual_blocks != expected_blocks:
            mapping_issues.append({"csv_line": row_index, "issue": "block_mapping", "profile": profile, "subblock": subblock, "actual": actual_blocks, "expected": expected_blocks})
        expected_source = "nav_symbol_1" if expected_blocks[0] < 2 else "nav_symbol_2"
        if row.get("nav_symbol_source") != expected_source:
            mapping_issues.append({"csv_line": row_index, "issue": "nav_symbol_source", "actual": row.get("nav_symbol_source"), "expected": expected_source})
        stage0_row = stage0.get(window_id or -1)
        if stage0_row is None:
            mapping_issues.append({"csv_line": row_index, "issue": "window_not_in_stage0", "window_id": window_id})
        else:
            if str(row.get("sample_start_zero_based")) != str(stage0_row.get("sample_start_zero_based")):
                mapping_issues.append({"csv_line": row_index, "issue": "sample_start_mismatch", "window_id": window_id})
            if str(row.get("nav_symbol")) != str(stage0_row.get("nav_symbol_1" if expected_source == "nav_symbol_1" else "nav_symbol_2")):
                mapping_issues.append({"csv_line": row_index, "issue": "nav_symbol_value_mismatch", "window_id": window_id})
        search_status = str(row.get("search_status", ""))
        secondary_status = str(row.get("secondary_status", ""))
        missing_reason = str(row.get("feature_missing_reason", ""))
        continuity_counts[str(row.get("continuity_status", ""))] += 1
        if search_status not in ALLOWED_SEARCH_STATUS or secondary_status not in ALLOWED_SECONDARY_STATUS or missing_reason not in ALLOWED_MISSING_REASONS:
            status_issues.append({"csv_line": row_index, "search_status": search_status, "secondary_status": secondary_status, "feature_missing_reason": missing_reason})
        if str(row.get("gold_labels_used_for_selection", "")).lower() != "false":
            status_issues.append({"csv_line": row_index, "issue": "gold_flag_not_false"})
        if str(row.get("parameter_hash", "")) != common.parameter_sha256() or str(row.get("v2_parameter_hash", "")) != common.V2_PARAMETER_SHA256:
            status_issues.append({"csv_line": row_index, "issue": "parameter_hash_mismatch"})
        secondary_fields = ("secondary_peak_strength", "secondary_main_ratio", "secondary_delay_samples", "delay_separation_samples", "secondary_doppler_hz", "secondary_doppler_relative_hz")
        secondary_present = secondary_status == "admissible_delay"
        if secondary_present:
            if any(parse_float(row.get(field)) is None for field in secondary_fields):
                null_issues.append({"csv_line": row_index, "issue": "admissible_secondary_missing_value"})
            if parse_int(row.get("delay_separation_samples")) is None or parse_int(row.get("delay_separation_samples")) < 2:
                delay_issues.append({"csv_line": row_index, "issue": "secondary_separation_below_minimum"})
            if missing_reason:
                null_issues.append({"csv_line": row_index, "issue": "admissible_secondary_has_missing_reason", "reason": missing_reason})
        elif any(str(row.get(field, "")).strip() for field in secondary_fields):
            null_issues.append({"csv_line": row_index, "issue": "non_admissible_secondary_has_non_null_value", "status": secondary_status})
        if row.get("frequency_tie_break") != "first_max_in_frozen_frequency_grid" or row.get("delay_tie_break") != "first_max_in_frozen_delay_order":
            tie_break_issues.append({"csv_line": row_index, "issue": "tie_break_label"})
        try:
            tie_json = json.loads(row.get("tie_break_indices_json", ""))
            if not isinstance(tie_json, list):
                raise ValueError("not list")
        except (TypeError, ValueError, json.JSONDecodeError):
            tie_break_issues.append({"csv_line": row_index, "issue": "tie_break_indices_json"})
        for field in NUMERIC_FIELDS:
            value = parse_float(row.get(field))
            if value is not None:
                profile_values[profile][field].append(value)
        for field in ("main_doppler_relative_hz", "secondary_doppler_relative_hz"):
            value = parse_float(row.get(field))
            if value is not None:
                profile_boundary_counts[(profile, field, "zero") if abs(value) < 1e-9 else (profile, field, "nonzero")] += 1
        main_index = parse_int(row.get("main_peak_index"))
        secondary_index = parse_int(row.get("secondary_peak_index"))
        if main_index is not None and main_index not in range(5):
            delay_issues.append({"csv_line": row_index, "issue": "main_delay_index_out_of_grid", "value": main_index})
        if secondary_index is not None and secondary_index not in range(5):
            delay_issues.append({"csv_line": row_index, "issue": "secondary_delay_index_out_of_grid", "value": secondary_index})
        main_rel = parse_float(row.get("main_doppler_relative_hz"))
        main_abs = parse_float(row.get("main_doppler_hz"))
        tracking = parse_float(row.get("tracking_doppler_hz"))
        if main_rel is not None and main_abs is not None and tracking is not None and abs(main_rel - (main_abs - tracking)) > 1e-8:
            doppler_issues.append({"csv_line": row_index, "issue": "main_relative_doppler_identity"})
        second_rel = parse_float(row.get("secondary_doppler_relative_hz"))
        second_abs = parse_float(row.get("secondary_doppler_hz"))
        if second_rel is not None and second_abs is not None and tracking is not None and abs(second_rel - (second_abs - tracking)) > 1e-8:
            doppler_issues.append({"csv_line": row_index, "issue": "secondary_relative_doppler_identity"})

    expected_keys = {(window_id, profile, subblock) for window_id in range(1, EXPECTED_WINDOW_COUNT + 1) for profile, count in EXPECTED_SUBBLOCKS.items() for subblock in range(count)}
    actual_keys = set(rows_by_key)
    missing_keys = sorted(expected_keys - actual_keys, key=lambda item: (item[0], item[1], item[2]))
    unexpected_keys = sorted(actual_keys - expected_keys, key=lambda item: (str(item[0]), str(item[1]), str(item[2])))
    duplicates = {str(key): count for key, count in key_counts.items() if count > 1}

    paired_rows = defaultdict(dict)
    for row in rows:
        window = parse_int(row.get("window_id"))
        sub = parse_int(row.get("subblock_index"))
        paired_rows[(window, sub)][row.get("profile_id", "")] = row
    for key, group in paired_rows.items():
        d100 = group.get("B2_10msx4_D100")
        d200 = group.get("B2_10msx4_D200")
        if d100 and d200:
            fields_to_compare = ("main_delay_samples", "secondary_delay_samples", "main_doppler_hz", "secondary_doppler_hz", "secondary_main_ratio")
            if all(str(d100.get(field, "")) == str(d200.get(field, "")) for field in fields_to_compare):
                exact_profile_pair_counts["B2_D100_D200_all_core_fields_equal"] += 1
            exact_profile_pair_counts["B2_D100_D200_pairs"] += 1

    numerical_issues = _finite_field_issues(rows)
    for profile, values in profile_values.items():
        for field, data in values.items():
            if any(not math.isfinite(value) for value in data):
                numerical_issues.append({"profile": profile, "field": field, "issue": "nonfinite"})
    row_count_pass = len(rows) == sum(EXPECTED_PROFILE_COUNTS.values())
    profile_count_pass = dict(count_by_profile) == EXPECTED_PROFILE_COUNTS
    coverage_pass = not missing_keys and not unexpected_keys and not duplicates
    status_pass = not status_issues and not null_issues
    mapping_pass = not mapping_issues
    numeric_pass = not numerical_issues and not delay_issues and not doppler_issues and not tie_break_issues
    receipt_pass = receipt_checks["all_pass"]
    all_pass = all((row_count_pass, profile_count_pass, coverage_pass, status_pass, mapping_pass, numeric_pass, receipt_pass, not schema_missing))
    result = {
        "qa_type": "raw_coarse_v3_evidence_qa",
        "created_at_utc": utc_now(),
        "status": "PASS" if all_pass else "FAIL",
        "gold_labels_used_for_selection": False,
        "posterior_sources_read": False,
        "raw_iq_read": False,
        "task": EXPECTED_TASK,
        "input_paths": {"evidence": str(evidence_path), "receipt": str(receipt_path), "run_manifest": str(run_manifest_path), "stage0": str(stage0_path), "task_manifest": str(manifest_path)},
        "input_sha256": {"evidence": sha256_file(evidence_path), "receipt": sha256_file(receipt_path), "run_manifest": sha256_file(run_manifest_path), "stage0": sha256_file(stage0_path), "task_manifest": sha256_file(manifest_path)},
        "counts": {"evidence_rows": len(rows), "expected_rows": sum(EXPECTED_PROFILE_COUNTS.values()), "stage0_windows": len(stage0), "profile_counts": dict(sorted(count_by_profile.items())), "expected_profile_counts": EXPECTED_PROFILE_COUNTS, "status_counts": {"search_status": _status_counts(rows, "search_status"), "secondary_status": _status_counts(rows, "secondary_status"), "feature_missing_reason": _status_counts(rows, "feature_missing_reason"), "continuity_status": dict(sorted(continuity_counts.items()))}},
        "checks": {"schema_missing": schema_missing, "row_count_pass": row_count_pass, "profile_count_pass": profile_count_pass, "coverage_pass": coverage_pass, "status_pass": status_pass, "mapping_pass": mapping_pass, "numeric_pass": numeric_pass, "receipt_pass": receipt_pass, "all_pass": all_pass},
        "coverage": {"missing_keys": missing_keys[:100], "missing_key_count": len(missing_keys), "unexpected_keys": unexpected_keys[:100], "unexpected_key_count": len(unexpected_keys), "duplicate_keys": duplicates, "window_id_min": min((key[0] for key in actual_keys if key[0] is not None), default=None), "window_id_max": max((key[0] for key in actual_keys if key[0] is not None), default=None)},
        "issues": {"identity": identity_issues[:100], "identity_count": len(identity_issues), "status": status_issues[:100], "status_count": len(status_issues), "null_semantics": null_issues[:100], "null_count": len(null_issues), "mapping": mapping_issues[:100], "mapping_count": len(mapping_issues), "tie_break": tie_break_issues[:100], "tie_break_count": len(tie_break_issues), "delay": delay_issues[:100], "delay_count": len(delay_issues), "doppler": doppler_issues[:100], "doppler_count": len(doppler_issues), "numerical": numerical_issues[:100], "numerical_count": len(numerical_issues)},
        "numerical_distributions": {profile: {field: _distribution(values) for field, values in sorted(fields_map.items())} for profile, fields_map in sorted(profile_values.items())},
        "grid_boundary_and_cross_profile": {"relative_doppler_boundary_counts": {"|relative|=0": sum(count for (profile, field, kind), count in profile_boundary_counts.items() if kind == "zero")}, "profile_pair_counts": dict(exact_profile_pair_counts), "note": "Boundary and D100/D200 comparisons are diagnostics only; no evidence row is a multipath label."},
        "receipt_checks": receipt_checks,
    }
    output_root = Path(output_root).resolve()
    common.assert_new_sampling_namespace(output_root, project_root)
    (output_root / "evidence_qa_report.json").write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    (output_root / "evidence_qa_hashes.json").write_text(json.dumps({"evidence_qa_report_sha256": sha256_file(output_root / "evidence_qa_report.json"), "evidence_sha256": result["input_sha256"]["evidence"], "receipt_sha256": result["input_sha256"]["receipt"], "task_manifest_sha256": result["input_sha256"]["task_manifest"], "gold_labels_used_for_selection": False}, indent=2) + "\n", encoding="utf-8")
    return result


def write_markdown(result: Mapping[str, Any], path: Path) -> None:
    counts = result["counts"]
    checks = result["checks"]
    issues = result["issues"]
    lines = [
        "# Raw-Coarse v3 G16 Evidence QA",
        "",
        f"Status: **{result['status']}**",
        "",
        "This is a gold-blind evidence QA. It did not read raw IQ, later SAGE-stage outputs, posterior labels, or coverage replay artifacts.",
        "",
        "## Completeness",
        "",
        f"- Stage0 windows: {counts['stage0_windows']}",
        f"- Evidence rows: {counts['evidence_rows']} / expected {counts['expected_rows']}",
        f"- Profiles: `{counts['profile_counts']}`",
        f"- Search status: `{counts['status_counts']['search_status']}`",
        f"- Secondary status: `{counts['status_counts']['secondary_status']}`",
        f"- Missing reason: `{counts['status_counts']['feature_missing_reason']}`",
        f"- Continuity: `{counts['status_counts']['continuity_status']}`",
        "",
        "## Gate results",
        "",
        f"- Schema: `{not bool(checks['schema_missing'])}`",
        f"- Row/profile counts: `{checks['row_count_pass'] and checks['profile_count_pass']}`",
        f"- Window/profile/subblock coverage and uniqueness: `{checks['coverage_pass']}`",
        f"- Identity, status and null semantics: `{checks['status_pass'] and issues['identity_count'] == 0}`",
        f"- B1/B2/NAV mapping: `{checks['mapping_pass']}`",
        f"- Numerical, delay, Doppler and tie-break sanity: `{checks['numeric_pass']}`",
        f"- Receipt/provenance: `{checks['receipt_pass']}`",
        "",
        "## Interpretation",
        "",
        "The evidence rows are coarse correlation evidence only. `admissible_delay`, secondary strength, delay and Doppler do not identify confirmed multipath. No row is assigned a multipath label by this QA.",
        "",
        "## Frozen provenance",
        "",
        f"- Evidence SHA-256: `{result['input_sha256']['evidence']}`",
        f"- Receipt SHA-256: `{result['input_sha256']['receipt']}`",
        f"- Task manifest SHA-256: `{result['input_sha256']['task_manifest']}`",
        "- `gold_labels_used_for_selection=false`",
        "- `raw_iq_read=false`",
        "",
    ]
    if checks["all_pass"]:
        lines.append("Evidence QA passed; the frozen v3.0 feature builder may now be run on this evidence file in a new-only namespace.")
    else:
        lines.append("Evidence QA failed; feature building must not proceed.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--stage0", type=Path, required=True)
    parser.add_argument("--task-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.evidence, args.receipt, args.run_manifest, args.stage0, args.task_manifest, args.output_root)
    write_markdown(result, args.report)
    print(f"EVIDENCE_QA_STATUS={result['status']}")
    print(f"EVIDENCE_QA_OUTPUT={args.output_root.resolve()}")
    print(f"EVIDENCE_QA_REPORT={args.report.resolve()}")
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
