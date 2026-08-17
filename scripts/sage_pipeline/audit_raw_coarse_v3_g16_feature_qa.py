"""Gold-blind QA for frozen raw-coarse v3.0 feature/selector artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import raw_coarse_v3_common as common


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_WINDOWS = 2229
WINDOW_STEP_S = 0.02
EXPECTED_PARAMETER_SHA256 = "3f6330f8c88b4901feda2e0cb9bd9e8dcd6350aec6270fd0d3985f5ca2669642"


def sha256_file(path: Path) -> str:
    return common.sha256_file(Path(path))


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def finite(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def distribution(values: list[float], missing: int) -> dict[str, Any]:
    return {
        "count": len(values),
        "missing_or_null": missing,
        "min": min(values) if values else None,
        "p01": percentile(values, 0.01),
        "p50": percentile(values, 0.50),
        "p90": percentile(values, 0.90),
        "p99": percentile(values, 0.99),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def numeric_distributions(rows: list[dict[str, str]], fields: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields:
        values: list[float] = []
        missing = 0
        invalid = 0
        for row in rows:
            raw = row.get(field, "")
            if str(raw).strip() == "":
                missing += 1
                continue
            value = finite(raw)
            if value is None:
                invalid += 1
            else:
                values.append(value)
        item = distribution(values, missing)
        item["invalid_nonfinite"] = invalid
        result[field] = item
    return result


def parse_component_ids(value: str) -> list[int]:
    return [int(item) for item in str(value).split(";") if str(item).strip()]


def audit(feature_root: Path, output_root: Path, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    feature_root = Path(feature_root).resolve()
    feature_path = feature_root / "v3_window_features.csv"
    promotion_path = feature_root / "promotion_manifest.csv"
    component_path = feature_root / "promotion_components.csv"
    run_manifest_path = feature_root / "feature_run_manifest.json"
    paths = (feature_path, promotion_path, component_path, run_manifest_path)
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    feature_fields, features = read_csv(feature_path)
    promotion_fields, promotions = read_csv(promotion_path)
    component_fields, components = read_csv(component_path)
    run_manifest = read_json(run_manifest_path)

    expected_window_ids = set(range(1, EXPECTED_WINDOWS + 1))
    feature_ids = [int(row["window_id"]) for row in features if row.get("window_id", "").strip()]
    promotion_ids = [int(row["window_id"]) for row in promotions if row.get("window_id", "").strip()]
    feature_id_counts = Counter(feature_ids)
    promotion_id_counts = Counter(promotion_ids)
    feature_id_set = set(feature_ids)
    promotion_id_set = set(promotion_ids)

    provenance_issues: list[str] = []
    if run_manifest.get("parameter_sha256") != EXPECTED_PARAMETER_SHA256:
        provenance_issues.append("feature_run_manifest_parameter_sha256_mismatch")
    if run_manifest.get("gold_labels_used_for_selection") is not False:
        provenance_issues.append("feature_run_manifest_gold_flag")
    if run_manifest.get("stage3_stage4_read") is not False:
        provenance_issues.append("feature_run_manifest_later_stage_read_flag")
    if run_manifest.get("adjacent_window_persistence_in_selector") is not False:
        provenance_issues.append("temporal_persistence_enabled")
    if run_manifest.get("local_novelty_in_selector") is not False or run_manifest.get("robust_z_in_selector") is not False:
        provenance_issues.append("reserved_feature_enabled")
    for row in features + promotions:
        if str(row.get("gold_labels_used_for_selection", "")).lower() != "false":
            provenance_issues.append("row_gold_flag")
            break
        if str(row.get("parameter_hash", "")) != EXPECTED_PARAMETER_SHA256:
            provenance_issues.append("row_parameter_hash")
            break

    status_counts = Counter(row.get("promotion_status", "") for row in features)
    coverage_counts = Counter(row.get("coverage_status", "") for row in features)
    reason_counts = Counter(row.get("promotion_reason", "") for row in features)
    evidence_counts = Counter(row.get("evidence_status", "") for row in features)
    if len(features) != EXPECTED_WINDOWS:
        provenance_issues.append("feature_row_count_not_2229")
    if feature_id_set != expected_window_ids or any(count != 1 for count in feature_id_counts.values()):
        provenance_issues.append("feature_window_id_coverage_or_duplicate")
    if promotion_id_set != expected_window_ids or any(count != 1 for count in promotion_id_counts.values()):
        provenance_issues.append("promotion_window_id_coverage_or_duplicate")
    if len(promotions) != len(features):
        provenance_issues.append("feature_promotion_row_count_mismatch")
    if any(row.get("feature_sha256", "") != sha256_file(feature_path) for row in promotions):
        provenance_issues.append("promotion_feature_hash_mismatch")

    # v3.0 has no separate continuation state.  Report the categories implied
    # by the frozen output fields without rewriting the source artifact.
    behavior_counts = Counter()
    for row in features:
        status = row.get("promotion_status", "")
        coverage = row.get("coverage_status", "")
        if status == "coarse_promoted":
            behavior_counts["coarse_seed"] += 1
        elif coverage == "coarse_boundary_expansion":
            behavior_counts["guard_promoted"] += 1
        elif status == "inconclusive":
            behavior_counts["inconclusive"] += 1
        else:
            behavior_counts["not_promoted"] += 1
    behavior_counts["coarse_continuation"] = 0

    component_metrics: list[dict[str, Any]] = []
    component_union: set[int] = set()
    component_overlap: set[int] = set()
    for row in components:
        expanded = parse_component_ids(row.get("component_window_ids", ""))
        before = set(expanded) & component_union
        component_overlap.update(before)
        component_union.update(expanded)
        size = len(expanded)
        first_expanded = min(expanded) if expanded else None
        last_expanded = max(expanded) if expanded else None
        component_metrics.append({
            "component_id": row.get("component_id"),
            "seed_window_count": int(row.get("seed_window_count", "0")),
            "expanded_window_count": size,
            "first_seed_window_id": int(row.get("first_window_id", "0")),
            "last_seed_window_id": int(row.get("last_window_id", "0")),
            "first_expanded_window_id": first_expanded,
            "last_expanded_window_id": last_expanded,
            "duration_s": (last_expanded - first_expanded + 1) * WINDOW_STEP_S if expanded else 0.0,
            "seed_density": (int(row.get("seed_window_count", "0")) / size) if size else None,
        })
    sizes = [item["expanded_window_count"] for item in component_metrics]
    durations = [item["duration_s"] for item in component_metrics]
    fine_ids = {int(row["window_id"]) for row in features if row.get("promotion_component_id", "").strip()}
    fine_ids_from_components = set(component_union)
    if fine_ids != fine_ids_from_components:
        provenance_issues.append("feature_component_union_mismatch")
    if component_overlap:
        provenance_issues.append("component_overlap")
    if not fine_ids.issubset(expected_window_ids):
        provenance_issues.append("fine_window_outside_stage0")

    # These fields are categorical/provenance strings even when they are empty
    # for every row.  Do not feed them through the numeric finite-value audit:
    # an empty feature_missing_reason is valid evidence completeness, and
    # evidence_status is a state machine value, not a numeric feature.
    categorical_fields = {
        "task_id", "scene_id", "prn", "feature_schema_version",
        "consensus_profile_id", "cross_scale_pair_id", "evidence_status",
        "feature_missing_reason", "promotion_status", "promotion_reason",
        "promotion_component_id", "not_promoted", "coverage_status",
        "parameter_hash", "evidence_sha256", "gold_labels_used_for_selection",
    }
    numeric_fields = [field for field in feature_fields if field not in categorical_fields]
    distributions = numeric_distributions(features, numeric_fields)
    invalid_numeric = {field: item["invalid_nonfinite"] for field, item in distributions.items() if item["invalid_nonfinite"]}
    if invalid_numeric:
        provenance_issues.append("invalid_numeric_feature_values")

    projected_fine = len(fine_ids)
    workload = {
        "stage0_windows": EXPECTED_WINDOWS,
        "projected_fine_stage1_windows": projected_fine,
        "projected_stage1_reduction_windows": EXPECTED_WINDOWS - projected_fine,
        "projected_stage1_reduction_fraction": (EXPECTED_WINDOWS - projected_fine) / EXPECTED_WINDOWS,
        "projected_stage1_fraction": projected_fine / EXPECTED_WINDOWS,
        "stage2_executed": False,
        "stage2_workload_projected": "not estimated from this v3 feature artifact",
    }
    all_pass = not provenance_issues and len(component_metrics) > 0 and projected_fine < EXPECTED_WINDOWS
    result = {
        "qa_type": "raw_coarse_v3_g16_feature_selector_qa",
        "created_at_utc": now_utc(),
        "status": "PASS" if all_pass else "FAIL",
        "gold_labels_used_for_selection": False,
        "posterior_sources_read": False,
        "raw_iq_read": False,
        "later_stage_sources_read": False,
        "feature_root": str(feature_root),
        "source_hashes": {
            "v3_window_features.csv": sha256_file(feature_path),
            "promotion_manifest.csv": sha256_file(promotion_path),
            "promotion_components.csv": sha256_file(component_path),
            "feature_run_manifest.json": sha256_file(run_manifest_path),
        },
        "schema": {"feature_fields": feature_fields, "promotion_fields": promotion_fields, "component_fields": component_fields},
        "counts": {
            "feature_rows": len(features),
            "promotion_rows": len(promotions),
            "component_count": len(components),
            "promotion_status": dict(sorted(status_counts.items())),
            "coverage_status": dict(sorted(coverage_counts.items())),
            "behavior_status": dict(sorted(behavior_counts.items())),
            "promotion_reason": dict(sorted(reason_counts.items())),
            "evidence_status": dict(sorted(evidence_counts.items())),
            "projected_fine_windows": projected_fine,
        },
        "component_summary": {
            "component_count": len(component_metrics),
            "expanded_window_union_count": len(component_union),
            "overlap_window_count": len(component_overlap),
            "size_min": min(sizes) if sizes else None,
            "size_p50": percentile([float(value) for value in sizes], 0.5),
            "size_p90": percentile([float(value) for value in sizes], 0.9),
            "size_max": max(sizes) if sizes else None,
            "duration_s_min": min(durations) if durations else None,
            "duration_s_p50": percentile(durations, 0.5),
            "duration_s_p90": percentile(durations, 0.9),
            "duration_s_max": max(durations) if durations else None,
            "full_scene_component": any(size >= EXPECTED_WINDOWS for size in sizes),
            "components": component_metrics,
        },
        "feature_distributions_all_windows": distributions,
        "workload": workload,
        "provenance_issues": provenance_issues,
        "parameter_sha256": run_manifest.get("parameter_sha256"),
        "selector_semantics": {
            "production_feature_families": ["multi_subblock_consensus", "secondary_delay_consistency", "secondary_doppler_consistency", "b1_b2_cross_scale_agreement"],
            "temporal_persistence_in_selector": False,
            "local_novelty_in_selector": False,
            "robust_z_in_selector": False,
            "coarse_continuation_status": "not represented in v3.0 output; reported as 0",
            "guard_promoted_definition": "fixed boundary expansion rows with coverage_status=coarse_boundary_expansion; not evidence seeds",
            "not_promoted_is_los": False,
        },
    }
    output_root = Path(output_root).resolve()
    common.assert_new_sampling_namespace(output_root, project_root)
    report_json = output_root / "feature_selector_qa_report.json"
    report_json.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    hashes = {"feature_selector_qa_report.json": sha256_file(report_json), **result["source_hashes"], "gold_labels_used_for_selection": False}
    (output_root / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return result


def write_report(result: Mapping[str, Any], path: Path) -> None:
    counts = result["counts"]
    summary = result["component_summary"]
    workload = result["workload"]
    lines = [
        "# Raw-Coarse v3.0 G16 Feature and Selector QA",
        "",
        f"Status: **{result['status']}**",
        "",
        "This is a gold-blind selector-behavior QA. It used only the completed v3 evidence-derived artifacts and did not read raw IQ, later SAGE stages, old coverage replay, confirmed centers, or gold labels.",
        "",
        "## Selector counts",
        "",
        f"- Feature rows/windows: `{counts['feature_rows']}`",
        f"- Promotion status: `{counts['promotion_status']}`",
        f"- Coverage status: `{counts['coverage_status']}`",
        f"- Derived behavior categories: `{counts['behavior_status']}`",
        f"- Promotion reasons: `{counts['promotion_reason']}`",
        f"- Inconclusive: `{counts['behavior_status'].get('inconclusive', 0)}`",
        "",
        "In v3.0, `coarse_seed` corresponds to `promotion_status=coarse_promoted`; `guard_promoted` corresponds only to fixed boundary expansion. `coarse_continuation` is not represented because temporal persistence is explicitly disabled in the frozen selector and is reported as zero. `not_promoted` is not a LOS label.",
        "",
        "## Components and projected workload",
        "",
        f"- Components: `{summary['component_count']}`",
        f"- Expanded fine-window union: `{summary['expanded_window_union_count']}`",
        f"- Component size min/p50/p90/max: `{summary['size_min']}` / `{summary['size_p50']}` / `{summary['size_p90']}` / `{summary['size_max']}` windows",
        f"- Component duration min/p50/p90/max: `{summary['duration_s_min']}` / `{summary['duration_s_p50']}` / `{summary['duration_s_p90']}` / `{summary['duration_s_max']}` seconds",
        f"- Full-scene component: `{summary['full_scene_component']}`",
        f"- Projected fine Stage1 windows: `{workload['projected_fine_stage1_windows']}` / `{workload['stage0_windows']}`",
        f"- Projected Stage1 reduction: `{workload['projected_stage1_reduction_windows']}` windows ({workload['projected_stage1_reduction_fraction']:.4%})",
        "- Stage2 was not run and its workload is not inferred from this artifact.",
        "",
        "## Feature distributions",
        "",
        "The complete per-feature distribution is stored in `feature_selector_qa_report.json`; it includes count, missing/null count, invalid count, min, p01, p50, p90, p99, max and mean for every numeric feature column across all 2229 windows.",
        "",
        "| Feature | Count | Missing | P01 | P50 | P99 | Max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for field, item in result["feature_distributions_all_windows"].items():
        def fmt(value: Any) -> str:
            return "" if value is None else f"{value:.6g}" if isinstance(value, float) else str(value)
        lines.append(f"| `{field}` | {item['count']} | {item['missing_or_null']} | {fmt(item['p01'])} | {fmt(item['p50'])} | {fmt(item['p99'])} | {fmt(item['max'])} |")
    lines.extend([
        "",
        "## Frozen provenance",
        "",
        f"- Parameter SHA-256: `{result['parameter_sha256']}`",
        f"- Feature table SHA-256: `{result['source_hashes']['v3_window_features.csv']}`",
        f"- Promotion manifest SHA-256: `{result['source_hashes']['promotion_manifest.csv']}`",
        f"- Component artifact SHA-256: `{result['source_hashes']['promotion_components.csv']}`",
        f"- Feature run manifest SHA-256: `{result['source_hashes']['feature_run_manifest.json']}`",
        "- `gold_labels_used_for_selection=false` for all artifacts.",
        "- Temporal persistence, local novelty and robust-z are disabled in v3.0.",
        "",
        "## Release decision",
        "",
    ])
    if result["status"] == "PASS":
        lines.append("Feature/selector behavior QA passed without gold leakage. This does not establish event recall or production validity. The artifacts are READY_FOR_POSTERIOR_GOLD_REPLAY only; no posterior replay was executed in this run.")
    else:
        lines.append("Feature/selector behavior QA failed. Do not run posterior gold replay until the listed provenance or behavior issues are resolved in a new namespace.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.feature_root, args.output_root)
    write_report(result, args.report)
    print(f"FEATURE_QA_STATUS={result['status']}")
    print(f"FEATURE_QA_OUTPUT={args.output_root.resolve()}")
    print(f"FEATURE_QA_REPORT={args.report.resolve()}")
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
