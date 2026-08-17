"""Build auditable raw-coarse v3 window features from subblock evidence.

This builder consumes only ``subblock_evidence.csv``.  It never reads gold or
Stage3/Stage4 files.  The selector intentionally excludes adjacent-window
persistence, local novelty, and robust-z features in v3.0; the output keeps a
full evidence vector and an explicit evidence-state rather than collapsing to
the old maximum-score proxy.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import raw_coarse_v3_common as common


FEATURE_FIELDS = [
    "task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "window_id",
    "recording_time_s", "tow_s", "sample_start_zero_based", "feature_schema_version",
    "consensus_profile_id", "secondary_present_count", "secondary_present_fraction",
    "secondary_ratio_median", "secondary_ratio_mad", "secondary_ratio_iqr",
    "secondary_ratio_min", "secondary_ratio_max", "secondary_delay_median_samples",
    "secondary_delay_mad_samples", "secondary_delay_range_samples", "secondary_delay_valid_fraction",
    "secondary_doppler_median_hz", "secondary_doppler_mad_hz", "secondary_doppler_range_hz",
    "secondary_doppler_valid_fraction", "b1_secondary_present_count", "b2_d100_secondary_present_count",
    "b2_d200_secondary_present_count", "cross_scale_pair_id", "cross_scale_match_count",
    "cross_scale_comparable_count", "cross_scale_agreement_fraction",
    "cross_scale_delay_disagreement_samples", "cross_scale_doppler_disagreement_hz",
    "cross_scale_d200_match_count", "cross_scale_d200_comparable_count",
    "cross_scale_d200_agreement_fraction", "cross_scale_d200_delay_disagreement_samples",
    "cross_scale_d200_doppler_disagreement_hz", "evidence_status", "feature_missing_reason",
    "promotion_status", "promotion_reason", "promotion_component_id", "not_promoted",
    "coverage_status", "parameter_hash", "evidence_sha256", "gold_labels_used_for_selection",
]

PROMOTION_FIELDS = [
    "task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "window_id",
    "promotion_status", "promotion_reason", "promotion_component_id", "not_promoted",
    "coverage_status", "boundary_expanded", "guard_radius_windows", "parameter_hash",
    "feature_sha256", "gold_labels_used_for_selection",
]

COMPONENT_FIELDS = [
    "task_id", "scene_id", "prn", "profile_rule", "component_id", "seed_window_count",
    "promoted_window_count", "first_window_id", "last_window_id", "component_window_ids",
    "boundary_expansion_windows", "bridge_gap_windows", "closure_radius_windows",
    "parameter_hash", "gold_labels_used_for_selection",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _int(value: Any) -> int | None:
    try:
        result = int(float(value))
    except (TypeError, ValueError):
        return None
    return result


def _median(values: Sequence[float]) -> float | None:
    return float(statistics.median(values)) if values else None


def _mad(values: Sequence[float]) -> float | None:
    if not values:
        return None
    med = statistics.median(values)
    return float(statistics.median([abs(value - med) for value in values]))


def _iqr(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return 0.0 if values else None
    ordered = sorted(values)
    try:
        quartiles = statistics.quantiles(ordered, n=4, method="inclusive")
    except statistics.StatisticsError:
        return 0.0
    return float(quartiles[2] - quartiles[0])


def _range(values: Sequence[float]) -> float | None:
    return float(max(values) - min(values)) if values else None


def _parse_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _validate_evidence_source(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    if "stage3" in str(path).lower() or "stage4" in str(path).lower() or "gold" in str(path).lower():
        raise ValueError("v3 feature builder refuses gold/Stage3/Stage4 evidence path")
    required = {
        "task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "profile_id",
        "window_id", "subblock_index", "secondary_status", "secondary_main_ratio",
        "secondary_delay_samples", "secondary_doppler_hz", "v2_parameter_hash", "parameter_hash",
        "gold_labels_used_for_selection",
    }
    if rows:
        missing = sorted(required - set(rows[0]))
        if missing:
            raise ValueError(f"evidence schema missing fields: {missing}")
    for row in rows:
        if str(row.get("gold_labels_used_for_selection", "")).lower() != "false":
            raise ValueError("evidence row is not marked gold_labels_used_for_selection=false")
        if str(row.get("parameter_hash", "")).strip() != common.parameter_sha256():
            raise ValueError("evidence parameter hash does not match frozen v3 parameter spec")
        if str(row.get("v2_parameter_hash", "")).strip() != common.V2_PARAMETER_SHA256:
            raise ValueError("evidence v2 parameter hash does not match aligned v2 authority")


def _valid_secondary(row: Mapping[str, str]) -> bool:
    if str(row.get("secondary_status", "")) != "admissible_delay":
        return False
    return all(_float(row.get(field)) is not None for field in ("secondary_main_ratio", "secondary_delay_samples", "secondary_doppler_hz"))


def _profile_summary(rows: Sequence[Mapping[str, str]], expected_subblocks: int) -> dict[str, Any]:
    valid = [row for row in rows if _valid_secondary(row)]
    ratios = [_float(row.get("secondary_main_ratio")) for row in valid]
    delays = [_float(row.get("secondary_delay_samples")) for row in valid]
    dopplers = [_float(row.get("secondary_doppler_hz")) for row in valid]
    ratios = [value for value in ratios if value is not None]
    delays = [value for value in delays if value is not None]
    dopplers = [value for value in dopplers if value is not None]
    search_missing = [row for row in rows if str(row.get("search_status", "")) != "valid"]
    return {
        "secondary_present_count": len(valid),
        "secondary_present_fraction": len(valid) / expected_subblocks if expected_subblocks else None,
        "secondary_ratio_median": _median(ratios),
        "secondary_ratio_mad": _mad(ratios),
        "secondary_ratio_iqr": _iqr(ratios),
        "secondary_ratio_min": min(ratios) if ratios else None,
        "secondary_ratio_max": max(ratios) if ratios else None,
        "secondary_delay_median_samples": _median(delays),
        "secondary_delay_mad_samples": _mad(delays),
        "secondary_delay_range_samples": _range(delays),
        "secondary_delay_valid_fraction": len(delays) / expected_subblocks if expected_subblocks else None,
        "secondary_doppler_median_hz": _median(dopplers),
        "secondary_doppler_mad_hz": _mad(dopplers),
        "secondary_doppler_range_hz": _range(dopplers),
        "secondary_doppler_valid_fraction": len(dopplers) / expected_subblocks if expected_subblocks else None,
        "search_missing_count": len(search_missing),
        "row_count": len(rows),
        "expected_subblocks": expected_subblocks,
    }


def _cross_scale(
    b1_rows: Sequence[Mapping[str, str]],
    b2_rows: Sequence[Mapping[str, str]],
    delay_tolerance: float,
    doppler_tolerance: float,
) -> dict[str, Any]:
    b1_by_subblock = {int(float(row["subblock_index"])): row for row in b1_rows}
    b2_by_subblock = {int(float(row["subblock_index"])): row for row in b2_rows}
    mapped = ((0, 0), (0, 1), (1, 2), (1, 3))
    comparable = 0
    matches = 0
    delay_disagreement: list[float] = []
    doppler_disagreement: list[float] = []
    for b1_index, b2_index in mapped:
        left = b1_by_subblock.get(b1_index)
        right = b2_by_subblock.get(b2_index)
        if left is None or right is None or not _valid_secondary(left) or not _valid_secondary(right):
            continue
        left_delay = _float(left.get("secondary_delay_samples"))
        right_delay = _float(right.get("secondary_delay_samples"))
        left_doppler = _float(left.get("secondary_doppler_hz"))
        right_doppler = _float(right.get("secondary_doppler_hz"))
        if None in (left_delay, right_delay, left_doppler, right_doppler):
            continue
        comparable += 1
        delay_delta = abs(left_delay - right_delay)
        doppler_delta = abs(left_doppler - right_doppler)
        delay_disagreement.append(delay_delta)
        doppler_disagreement.append(doppler_delta)
        if delay_delta <= delay_tolerance and doppler_delta <= doppler_tolerance:
            matches += 1
    return {
        "cross_scale_match_count": matches,
        "cross_scale_comparable_count": comparable,
        "cross_scale_agreement_fraction": matches / comparable if comparable else None,
        "cross_scale_delay_disagreement_samples": max(delay_disagreement) if delay_disagreement else None,
        "cross_scale_doppler_disagreement_hz": max(doppler_disagreement) if doppler_disagreement else None,
    }


def _promotion_state(
    b2_summary: Mapping[str, Any],
    cross: Mapping[str, Any],
    missing_evidence: bool,
    parameter_spec: Mapping[str, Any],
) -> tuple[str, str]:
    rule = parameter_spec["candidate_evidence_state"]
    if missing_evidence:
        return "inconclusive", "missing_or_invalid_subblock_evidence"
    if b2_summary["secondary_present_count"] == 0:
        return "not_promoted", "no_admissible_secondary"
    if b2_summary["secondary_present_count"] < int(rule["secondary_presence_min_count"]) or b2_summary["secondary_present_fraction"] < float(rule["secondary_presence_min_fraction"]):
        return "not_promoted", "multi_subblock_consensus_below_rule"
    if b2_summary["secondary_delay_mad_samples"] is None or b2_summary["secondary_doppler_mad_hz"] is None:
        return "inconclusive", "consistency_metric_missing"
    if b2_summary["secondary_delay_mad_samples"] > float(rule["delay_mad_max_samples"]):
        return "not_promoted", "secondary_delay_inconsistent"
    if b2_summary["secondary_doppler_mad_hz"] > float(rule["doppler_mad_max_hz"]):
        return "not_promoted", "secondary_doppler_inconsistent"
    if cross["cross_scale_comparable_count"] < int(rule["minimum_comparable_cross_scale_pairs"]):
        return "inconclusive", "cross_scale_incomparable"
    if cross["cross_scale_agreement_fraction"] < float(rule["cross_scale_min_agreement_fraction"]):
        return "not_promoted", "cross_scale_disagreement"
    return "coarse_promoted", "multi_subblock_and_cross_scale_consensus"


def _componentize(feature_rows: list[dict[str, Any]], parameter_spec: Mapping[str, Any]) -> tuple[dict[tuple[str, int], str], list[dict[str, Any]]]:
    rule = parameter_spec["temporal_component_rule"]
    bridge = int(rule["bridge_gap_windows"])
    boundary = int(rule["boundary_expansion_windows"])
    task_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        task_groups[(str(row.get("task_id", "")), str(row.get("scene_id", "")), str(row.get("prn", "")), str(row.get("tracking_channel", "")))].append(row)
    ids: dict[tuple[str, int], str] = {}
    component_rows: list[dict[str, Any]] = []
    component_serial = 0
    for task_key, task_rows in sorted(task_groups.items()):
        promoted = sorted(int(row["window_id"]) for row in task_rows if row.get("promotion_status") == "coarse_promoted")
        components: list[list[int]] = []
        for window_id in promoted:
            if components and window_id - components[-1][-1] - 1 <= bridge:
                components[-1].append(window_id)
            else:
                components.append([window_id])
        universe = {int(row["window_id"]) for row in task_rows}
        for number, seeds in enumerate(components, start=1):
            component_serial += 1
            component_id = f"v3c{component_serial:05d}"
            expanded = set(seeds)
            for seed in seeds:
                for offset in range(1, boundary + 1):
                    if seed - offset in universe:
                        expanded.add(seed - offset)
                    if seed + offset in universe:
                        expanded.add(seed + offset)
            for window_id in expanded:
                ids[(task_key[0], window_id)] = component_id
            first = task_rows[0]
            component_rows.append({
                "task_id": first.get("task_id"), "scene_id": first.get("scene_id"), "prn": first.get("prn"),
                "profile_rule": "v3.0_evidence_state_only",
                "component_id": component_id, "seed_window_count": len(seeds),
                "promoted_window_count": len(expanded), "first_window_id": min(seeds), "last_window_id": max(seeds),
                "component_window_ids": ";".join(str(value) for value in sorted(expanded)),
                "boundary_expansion_windows": boundary, "bridge_gap_windows": bridge,
                "closure_radius_windows": int(rule["closure_radius_windows"]),
                "parameter_hash": common.parameter_sha256(), "gold_labels_used_for_selection": "false",
            })
    return ids, component_rows


def build_feature_rows(evidence_rows: Sequence[Mapping[str, str]], evidence_sha256: str, parameter_spec: Mapping[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    spec = parameter_spec or common.V3_PARAMETER_SPEC
    grouped: dict[tuple[str, int], dict[str, list[Mapping[str, str]]]] = defaultdict(lambda: defaultdict(list))
    metadata: dict[tuple[str, int], Mapping[str, str]] = {}
    for row in evidence_rows:
        task_id = str(row.get("task_id", ""))
        window_id = _int(row.get("window_id"))
        if window_id is None:
            raise ValueError("evidence window_id is invalid")
        grouped[(task_id, window_id)][str(row.get("profile_id", ""))].append(row)
        metadata[(task_id, window_id)] = row
    feature_rows: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda item: (item[0], item[1])):
        task_id, window_id = key
        profiles = grouped[key]
        b1_rows = profiles.get("B1_20msx2_D100", [])
        b2_rows = profiles.get("B2_10msx4_D100", [])
        b2d200_rows = profiles.get("B2_10msx4_D200", [])
        b1_summary = _profile_summary(b1_rows, 2)
        b2_summary = _profile_summary(b2_rows, 4)
        b2d200_summary = _profile_summary(b2d200_rows, 4)
        cross = _cross_scale(b1_rows, b2_rows, float(spec["cross_scale_tolerance"]["delay_samples"]), float(spec["cross_scale_tolerance"]["doppler_hz"]))
        cross_d200 = _cross_scale(b1_rows, b2d200_rows, float(spec["cross_scale_tolerance"]["delay_samples"]), float(spec["cross_scale_tolerance"]["doppler_hz"]))
        missing_evidence = any(summary["row_count"] != summary["expected_subblocks"] or summary["search_missing_count"] > 0 for summary in (b1_summary, b2_summary, b2d200_summary))
        status, reason = _promotion_state(b2_summary, cross, missing_evidence, spec)
        source = metadata[key]
        row = {
            "task_id": task_id, "scene_id": source.get("scene_id"), "prn": source.get("prn"),
            "tracking_channel": source.get("tracking_channel"), "sample_rate_hz": source.get("sample_rate_hz"),
            "window_id": window_id, "recording_time_s": source.get("recording_time_s"), "tow_s": source.get("tow_s"),
            "sample_start_zero_based": source.get("sample_start_zero_based"),
            "feature_schema_version": common.FEATURE_SCHEMA_VERSION,
            "consensus_profile_id": "B2_10msx4_D100",
            **{field: b2_summary.get(field) for field in ("secondary_present_count", "secondary_present_fraction", "secondary_ratio_median", "secondary_ratio_mad", "secondary_ratio_iqr", "secondary_ratio_min", "secondary_ratio_max", "secondary_delay_median_samples", "secondary_delay_mad_samples", "secondary_delay_range_samples", "secondary_delay_valid_fraction", "secondary_doppler_median_hz", "secondary_doppler_mad_hz", "secondary_doppler_range_hz", "secondary_doppler_valid_fraction")},
            "b1_secondary_present_count": b1_summary["secondary_present_count"],
            "b2_d100_secondary_present_count": b2_summary["secondary_present_count"],
            "b2_d200_secondary_present_count": b2d200_summary["secondary_present_count"],
            "cross_scale_pair_id": "B1_20msx2_D100:B2_10msx4_D100",
            **cross,
            "cross_scale_d200_match_count": cross_d200["cross_scale_match_count"],
            "cross_scale_d200_comparable_count": cross_d200["cross_scale_comparable_count"],
            "cross_scale_d200_agreement_fraction": cross_d200["cross_scale_agreement_fraction"],
            "cross_scale_d200_delay_disagreement_samples": cross_d200["cross_scale_delay_disagreement_samples"],
            "cross_scale_d200_doppler_disagreement_hz": cross_d200["cross_scale_doppler_disagreement_hz"],
            "evidence_status": "inconclusive" if missing_evidence else "complete",
            "feature_missing_reason": "missing_profile_or_subblock_evidence" if missing_evidence else "",
            "promotion_status": status, "promotion_reason": reason, "promotion_component_id": None,
            "not_promoted": "true" if status != "coarse_promoted" else "false",
            "coverage_status": "coarse_evidence_only",
            "parameter_hash": common.parameter_sha256(), "evidence_sha256": evidence_sha256,
            "gold_labels_used_for_selection": "false",
        }
        feature_rows.append(row)
    component_ids, component_rows = _componentize(feature_rows, spec)
    for row in feature_rows:
        row["promotion_component_id"] = component_ids.get((str(row.get("task_id", "")), int(row["window_id"])))
    promoted_seed_ids = {int(row["window_id"]) for row in feature_rows if row.get("promotion_status") == "coarse_promoted"}
    for row in feature_rows:
        component_id = row["promotion_component_id"]
        if component_id is not None and row["promotion_status"] == "coarse_promoted":
            row["coverage_status"] = "coarse_promotion_component"
        elif component_id is not None and int(row["window_id"]) not in promoted_seed_ids:
            row["coverage_status"] = "coarse_boundary_expansion"
            row["promotion_reason"] = "boundary_expansion_from_coarse_component"
    return feature_rows, component_rows


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def build_from_evidence(evidence_path: Path, output_root: Path, parameter_manifest_path: Path, parameter_manifest_sha256: str, project_root: Path = common.PROJECT_ROOT) -> dict[str, Any]:
    common.load_frozen_manifest(parameter_manifest_path, parameter_manifest_sha256, project_root)
    fields, rows = _parse_rows(evidence_path)
    _validate_evidence_source(evidence_path, rows)
    output_root = common.assert_new_sampling_namespace(output_root, project_root)
    evidence_sha256 = common.sha256_file(evidence_path)
    feature_rows, component_rows = build_feature_rows(rows, evidence_sha256)
    feature_sha256_path = output_root / "v3_window_features.csv"
    _write_csv(feature_sha256_path, feature_rows, FEATURE_FIELDS)
    feature_sha256 = common.sha256_file(feature_sha256_path)
    promotion_rows = []
    for row in feature_rows:
        promotion_rows.append({
            "task_id": row["task_id"], "scene_id": row["scene_id"], "prn": row["prn"],
            "tracking_channel": row["tracking_channel"], "sample_rate_hz": row["sample_rate_hz"],
            "window_id": row["window_id"], "promotion_status": row["promotion_status"],
            "promotion_reason": row["promotion_reason"], "promotion_component_id": row["promotion_component_id"],
            "not_promoted": row["not_promoted"], "coverage_status": row["coverage_status"],
            "boundary_expanded": "true" if row["coverage_status"] == "coarse_boundary_expansion" else "false",
            "guard_radius_windows": common.V3_PARAMETER_SPEC["temporal_component_rule"]["closure_radius_windows"],
            "parameter_hash": common.parameter_sha256(), "feature_sha256": feature_sha256,
            "gold_labels_used_for_selection": "false",
        })
    _write_csv(output_root / "promotion_manifest.csv", promotion_rows, PROMOTION_FIELDS)
    _write_csv(output_root / "promotion_components.csv", component_rows, COMPONENT_FIELDS)
    run_manifest = {
        "builder": "build_raw_coarse_v3_features.py",
        "created_at_utc": utc_now(),
        "evidence_path": str(Path(evidence_path).resolve()),
        "evidence_sha256": evidence_sha256,
        "parameter_manifest_path": str(Path(parameter_manifest_path).resolve()),
        "parameter_manifest_sha256": parameter_manifest_sha256,
        "parameter_sha256": common.parameter_sha256(),
        "feature_row_count": len(feature_rows), "component_count": len(component_rows),
        "gold_labels_used_for_selection": False, "stage3_stage4_read": False,
        "adjacent_window_persistence_in_selector": False,
        "local_novelty_in_selector": False, "robust_z_in_selector": False,
        "files": ["v3_window_features.csv", "promotion_manifest.csv", "promotion_components.csv"],
    }
    (output_root / "feature_run_manifest.json").write_text(json.dumps(run_manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {**run_manifest, "feature_sha256": feature_sha256, "fields": fields}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--parameter-manifest", type=Path, required=True)
    parser.add_argument("--parameter-manifest-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=common.PROJECT_ROOT)
    args = parser.parse_args(argv)
    result = build_from_evidence(args.evidence, args.output_root, args.parameter_manifest, args.parameter_manifest_sha256, args.project_root)
    print(f"V3_FEATURE_OUTPUT={args.output_root.resolve()}")
    print(f"FEATURE_ROWS={result['feature_row_count']}")
    print(f"COMPONENTS={result['component_count']}")
    print("GOLD_LABELS_USED_FOR_SELECTION=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
