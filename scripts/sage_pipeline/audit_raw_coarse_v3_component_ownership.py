"""Gold-blind QA for the v3.0 component-ownership schema revision.

The parent v3.0 feature and component artifacts are treated as immutable
inputs.  This audit accepts boundary overlap as an expected relation and
verifies it through the normalized membership table instead of requiring a
partition.  It never reads raw IQ, Stage3/Stage4, coverage replay or gold.
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
from typing import Any, Mapping, Sequence

import raw_coarse_v3_common as common
from rebuild_raw_coarse_v3_component_ownership import (
    COMPONENT_FIELDS,
    MEMBERSHIP_FIELDS,
    SCHEMA_VERSION,
    WINDOW_FIELDS,
    _int,
    build_memberships,
    load_parent_artifacts,
    read_csv,
    read_json,
    reject_gold_blind_path,
    sha256_file,
    validate_schema_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_WINDOWS = 2229
EXPECTED_COMPONENTS = 188
EXPECTED_UNIQUE_FINE = 1222
EXPECTED_OVERLAP_WINDOWS = 26
WINDOW_STEP_S = 0.02


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def finite(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = q * (len(ordered) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def distribution(values: Sequence[float], missing: int, invalid: int) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "missing_or_null": missing,
        "invalid_nonfinite": invalid,
        "min": min(ordered) if ordered else None,
        "p01": percentile(ordered, 0.01),
        "p50": percentile(ordered, 0.50),
        "p90": percentile(ordered, 0.90),
        "p99": percentile(ordered, 0.99),
        "max": max(ordered) if ordered else None,
        "mean": statistics.fmean(ordered) if ordered else None,
    }


def feature_distributions(features: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    categorical = {
        "task_id", "scene_id", "prn", "feature_schema_version", "consensus_profile_id",
        "cross_scale_pair_id", "evidence_status", "feature_missing_reason",
        "promotion_status", "promotion_reason", "promotion_component_id", "not_promoted",
        "coverage_status", "parameter_hash", "evidence_sha256", "gold_labels_used_for_selection",
    }
    fields = [field for field in features[0] if field not in categorical] if features else []
    result: dict[str, Any] = {}
    for field in fields:
        values: list[float] = []
        missing = 0
        invalid = 0
        for row in features:
            raw = row.get(field, "")
            if str(raw).strip() == "":
                missing += 1
            else:
                value = finite(raw)
                if value is None:
                    invalid += 1
                else:
                    values.append(value)
        result[field] = distribution(values, missing, invalid)
    return result


def _task_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (str(row.get("task_id", "")), str(row.get("scene_id", "")), str(row.get("prn", "")), str(row.get("tracking_channel", "")))


def _parse_ids(value: Any) -> list[int]:
    values = [_int(item) for item in str(value or "").split(";") if str(item).strip()]
    if len(values) != len(set(values)):
        raise ValueError("duplicate window IDs in ownership artifact")
    return values


def read_ownership_outputs(ownership_root: Path) -> dict[str, Any]:
    ownership_root = Path(ownership_root).resolve()
    reject_gold_blind_path(ownership_root)
    paths = {
        "membership": ownership_root / "promotion_component_membership.csv",
        "component": ownership_root / "promotion_components.csv",
        "window": ownership_root / "promotion_manifest.csv",
        "run_manifest": ownership_root / "ownership_run_manifest.json",
        "hashes": ownership_root / "ownership_artifact_hashes.json",
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    membership_fields, memberships = read_csv(paths["membership"])
    component_fields, components = read_csv(paths["component"])
    window_fields, windows = read_csv(paths["window"])
    run_manifest = read_json(paths["run_manifest"])
    hashes = read_json(paths["hashes"])
    missing = {
        "membership": sorted(set(MEMBERSHIP_FIELDS) - set(membership_fields)),
        "component": sorted(set(COMPONENT_FIELDS) - set(component_fields)),
        "window": sorted(set(WINDOW_FIELDS) - set(window_fields)),
    }
    if any(missing.values()):
        raise ValueError(f"ownership schema fields missing: {missing}")
    return {"paths": paths, "membership_fields": membership_fields, "component_fields": component_fields, "window_fields": window_fields, "memberships": memberships, "components": components, "windows": windows, "run_manifest": run_manifest, "hashes": hashes}


def audit(feature_root: Path, schema_manifest: Path, expected_schema_sha256: str, ownership_root: Path, output_root: Path, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    feature_root = Path(feature_root).resolve()
    schema_manifest = Path(schema_manifest).resolve()
    ownership_root = Path(ownership_root).resolve()
    reject_gold_blind_path(feature_root)
    reject_gold_blind_path(schema_manifest)
    schema = validate_schema_manifest(read_json(schema_manifest), schema_manifest, expected_schema_sha256)
    parent = load_parent_artifacts(feature_root, schema)
    output = read_ownership_outputs(ownership_root)
    memberships = output["memberships"]
    components = output["components"]
    windows = output["windows"]
    run_manifest = output["run_manifest"]
    issues: list[str] = []

    expected_parent_hashes = parent["parent_hashes"]
    if run_manifest.get("schema_version") != SCHEMA_VERSION:
        issues.append("run_manifest_schema_version")
    if run_manifest.get("ownership_schema_sha256") != schema.get("ownership_schema_sha256"):
        issues.append("run_manifest_ownership_schema_hash")
    if run_manifest.get("parent_artifact_sha256") != expected_parent_hashes:
        issues.append("run_manifest_parent_hashes")
    if run_manifest.get("parent_frozen_parameter_sha256") != schema.get("parent_frozen_parameter_sha256"):
        issues.append("parent_scientific_parameter_hash")
    for key in ("gold_labels_used_for_selection", "raw_iq_read", "evidence_capture_rerun", "stage3_stage4_read", "posterior_sources_read", "scientific_selector_retuned"):
        if run_manifest.get(key) is not False:
            issues.append(f"run_manifest_{key}")
    if run_manifest.get("component_merge_due_to_boundary") is not False:
        issues.append("boundary_component_merge")

    parent_features = parent["features"]
    parent_feature_by_key = {(_task_key(row), _int(row["window_id"])): row for row in parent_features}
    parent_components = {str(row.get("component_id")): row for row in parent["components"]}
    output_components = {str(row.get("component_id")): row for row in components}
    parent_parameter_sha = str(schema.get("parent_frozen_parameter_sha256", ""))
    for row in parent_features + parent["promotions"] + parent["components"]:
        parameter_hash = str(row.get("parameter_hash", ""))
        if parameter_hash not in {"", parent_parameter_sha}:
            issues.append("parent_parameter_hash")
    if len(parent_features) != EXPECTED_WINDOWS or len(windows) != EXPECTED_WINDOWS:
        issues.append("window_count")
    window_keys = [(_task_key(row), _int(row["window_id"])) for row in windows]
    if len(window_keys) != len(set(window_keys)):
        issues.append("window_manifest_duplicate")
    if set(window_keys) != set(parent_feature_by_key):
        issues.append("window_manifest_coverage")
    if set(parent_components) != set(output_components) or len(output_components) != EXPECTED_COMPONENTS:
        issues.append("component_identity_or_count")

    membership_keys = [(_task_key(row), _int(row["window_id"]), str(row.get("component_id", ""))) for row in memberships]
    if len(membership_keys) != len(set(membership_keys)):
        issues.append("membership_duplicate")
    membership_by_window: dict[tuple[str, str, str, int], list[str]] = defaultdict(list)
    membership_by_component: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in memberships:
        component_id = str(row.get("component_id", ""))
        task = _task_key(row)
        window_id = _int(row["window_id"])
        membership_by_window[(*task, window_id)].append(component_id)
        membership_by_component[component_id].append(row)
        if str(row.get("ownership_schema_version")) != SCHEMA_VERSION or str(row.get("ownership_schema_sha256")) != str(schema.get("ownership_schema_sha256")):
            issues.append("membership_schema_provenance")
        if str(row.get("gold_labels_used_for_selection", "")).lower() != "false":
            issues.append("membership_gold_flag")
        if component_id not in parent_components:
            issues.append("membership_unknown_component")
        if str(row.get("membership_type")) not in {"core_seed", "guard"}:
            issues.append("membership_type")
        if str(row.get("boundary_provenance", "")).strip() == "":
            issues.append("membership_boundary_provenance")

    parent_promoted = {(_task_key(row), _int(row["window_id"])) for row in parent_features if row.get("promotion_status") == "coarse_promoted"}
    for row in windows:
        key = (_task_key(row), _int(row["window_id"]))
        memberships_for_window = membership_by_window.get((*key[0], key[1]), [])
        component_ids = [item for item in str(row.get("component_membership_ids", "")).split(";") if item]
        if component_ids != sorted(set(component_ids)):
            issues.append("window_membership_ids_not_deterministic")
        if int(row.get("component_membership_count", "0")) != len(component_ids) or sorted(component_ids) != sorted(memberships_for_window):
            issues.append("window_membership_count_or_ids")
        if str(row.get("unique_fine_window")) != ("true" if component_ids else "false"):
            issues.append("unique_fine_state")
        parent_row = parent_feature_by_key[key]
        for field in ("promotion_status", "promotion_reason", "not_promoted", "coverage_status"):
            if str(row.get(field, "")) != str(parent_row.get(field, "")):
                issues.append(f"window_parent_{field}")
        if str(parent_row.get("promotion_status")) == "not_promoted":
            # Boundary closure rows intentionally retain the frozen window
            # selector state ``not_promoted``.  They may have guard
            # memberships for fine-workload closure, but can never become a
            # core seed or a multipath/LOS label.
            memberships_for_window_rows = [
                membership
                for membership in output["memberships"]
                if _task_key(membership) == key[0] and _int(membership["window_id"]) == key[1]
            ]
            if any(str(membership.get("membership_type")) != "guard" for membership in memberships_for_window_rows):
                issues.append("not_promoted_has_core_membership")
        if key in parent_promoted and not component_ids:
            issues.append("promoted_seed_missing_membership")
        primary = str(row.get("primary_component_id", ""))
        if primary != (component_ids[0] if component_ids else ""):
            issues.append("primary_component_not_display_order")
        if str(row.get("primary_component_purpose", "")) not in {"none", "deterministic_display_sort_only_not_scientific_ownership"}:
            issues.append("primary_component_semantics")
        for field, expected in (("ownership_schema_version", SCHEMA_VERSION), ("ownership_schema_sha256", schema.get("ownership_schema_sha256")), ("parent_feature_sha256", expected_parent_hashes["feature"]), ("parent_component_sha256", expected_parent_hashes["component"])):
            if str(row.get(field, "")) != str(expected):
                issues.append(f"window_provenance_{field}")

    # Verify each output component preserves the parent component's core and
    # expanded sets.  This explicitly prevents a guard overlap from merging
    # two independent evidence components.
    for component_id, parent_component in parent_components.items():
        output_component = output_components.get(component_id)
        if output_component is None:
            continue
        parent_expanded = set(_parse_ids(parent_component.get("component_window_ids")))
        output_expanded = set(_parse_ids(output_component.get("expanded_window_ids")))
        if parent_expanded != output_expanded:
            issues.append(f"component_{component_id}_expanded_set_changed")
        if int(output_component.get("expanded_window_count", "-1")) != len(output_expanded):
            issues.append(f"component_{component_id}_expanded_count")
        if int(output_component.get("core_seed_window_count", "-1")) != int(parent_component.get("seed_window_count", "-2")):
            issues.append(f"component_{component_id}_core_count_changed")
        if int(output_component.get("membership_row_count", "-1")) != len(membership_by_component.get(component_id, [])):
            issues.append(f"component_{component_id}_membership_count")
        if str(output_component.get("gold_labels_used_for_selection", "")).lower() != "false":
            issues.append(f"component_{component_id}_gold_flag")

    multiplicity = Counter(len(membership_by_window.get((*key[0], key[1]), [])) for key in parent_feature_by_key)
    unique_fine = {key for key, ids in membership_by_window.items() if ids}
    overlap_windows = {key for key, ids in membership_by_window.items() if len(ids) > 1}
    promoted_count = sum(1 for row in parent_features if row.get("promotion_status") == "coarse_promoted")
    not_promoted_count = sum(1 for row in parent_features if row.get("promotion_status") == "not_promoted")
    if len(memberships) != 1248:
        issues.append("membership_row_count")
    if len(unique_fine) != EXPECTED_UNIQUE_FINE:
        issues.append("unique_fine_window_count")
    if len(overlap_windows) != EXPECTED_OVERLAP_WINDOWS:
        issues.append("overlap_window_count")
    if multiplicity != Counter({0: 1007, 1: 1196, 2: 26}):
        issues.append("multiplicity_distribution")
    if run_manifest.get("membership_multiplicity_distribution") != {str(k): multiplicity[k] for k in sorted(multiplicity)}:
        issues.append("run_manifest_multiplicity_distribution")
    if int(run_manifest.get("unique_fine_window_count", -1)) != len(unique_fine):
        issues.append("run_manifest_unique_fine_count")
    if int(run_manifest.get("overlap_window_count", -1)) != len(overlap_windows):
        issues.append("run_manifest_overlap_count")

    numeric = feature_distributions(parent_features)
    invalid_numeric = {field: item["invalid_nonfinite"] for field, item in numeric.items() if item["invalid_nonfinite"]}
    if invalid_numeric:
        issues.append("parent_feature_invalid_numeric")
    sizes = [len(_parse_ids(row.get("expanded_window_ids"))) for row in components]
    core_sizes = [int(row.get("core_seed_window_count", "0")) for row in components]
    status_counts = Counter(row.get("promotion_status", "") for row in parent_features)
    coverage_counts = Counter(row.get("coverage_status", "") for row in parent_features)
    behavior = {
        "coarse_seed": status_counts.get("coarse_promoted", 0),
        "coarse_continuation": 0,
        "guard_promoted": coverage_counts.get("coarse_boundary_expansion", 0),
        "not_promoted": not_promoted_count,
        "inconclusive": status_counts.get("inconclusive", 0),
    }
    if behavior["coarse_seed"] != promoted_count or behavior["not_promoted"] != not_promoted_count:
        issues.append("selector_state_counts")

    source_hashes = {
        path.name: sha256_file(path)
        for path in output["paths"].values()
        if path.name != "ownership_artifact_hashes.json"
    }
    recorded_hashes = {key: value for key, value in output["hashes"].items() if key in source_hashes}
    if recorded_hashes != source_hashes:
        issues.append("artifact_hash_ledger")
    if "sage_results" in str(ownership_root).lower() or "sage_results" in str(output_root).lower():
        issues.append("namespace_is_sage_results")

    all_pass = not issues
    result = {
        "qa_type": "raw_coarse_v3_component_ownership_gold_blind_qa",
        "created_at_utc": utc_now(), "status": "PASS" if all_pass else "FAIL",
        "ready_for_posterior_gold_replay": all_pass,
        "gold_labels_used_for_selection": False, "raw_iq_read": False,
        "stage3_stage4_read": False, "coverage_replay_read": False,
        "scientific_selector_retuned": False, "parent_artifacts_modified": False,
        "schema_version": SCHEMA_VERSION, "schema_manifest_sha256": schema["actual_schema_manifest_sha256"],
        "ownership_schema_sha256": schema["ownership_schema_sha256"],
        "parent_parameter_sha256": schema["parent_frozen_parameter_sha256"],
        "parent_artifact_sha256": expected_parent_hashes,
        "counts": {
            "stage0_feature_windows": len(parent_features), "promotion_manifest_windows": len(windows),
            "coarse_seed": behavior["coarse_seed"], "coarse_continuation": behavior["coarse_continuation"],
            "guard_promoted": behavior["guard_promoted"], "not_promoted": behavior["not_promoted"],
            "inconclusive": behavior["inconclusive"], "component_count": len(components),
            "membership_row_count": len(memberships), "unique_fine_windows": len(unique_fine),
            "overlap_window_count": len(overlap_windows),
            "promotion_fraction_unique_fine": len(unique_fine) / len(parent_features),
            "membership_multiplicity_distribution": {str(k): multiplicity[k] for k in sorted(multiplicity)},
        },
        "component_summary": {
            "core_size_min": min(core_sizes) if core_sizes else None,
            "core_size_p50": percentile([float(v) for v in core_sizes], 0.5),
            "core_size_max": max(core_sizes) if core_sizes else None,
            "expanded_size_min": min(sizes) if sizes else None,
            "expanded_size_p50": percentile([float(v) for v in sizes], 0.5),
            "expanded_size_p90": percentile([float(v) for v in sizes], 0.9),
            "expanded_size_max": max(sizes) if sizes else None,
            "full_scene_component": any(size >= len(parent_features) for size in sizes),
            "guard_caused_component_collapse": False,
            "component_ids_preserved": set(parent_components) == set(output_components),
        },
        "workload": {
            "projected_fine_stage1_windows": len(unique_fine),
            "projected_stage1_reduction_windows": len(parent_features) - len(unique_fine),
            "projected_stage1_reduction_fraction": (len(parent_features) - len(unique_fine)) / len(parent_features),
            "stage2_executed": False,
        },
        "feature_distributions_all_windows": numeric,
        "source_hashes": {"ownership_outputs": source_hashes, "qa_script_sha256": sha256_file(Path(__file__))},
        "issues": sorted(set(issues)),
        "selector_semantics": {
            "promotion_rules_changed": False,
            "boundary_radius_changed": False,
            "bridge_rule_changed": False,
            "not_promoted_is_los": False,
            "primary_component_is_scientific_owner": False,
            "overlap_is_explicit_membership_relation": True,
        },
    }
    output_root = Path(output_root).resolve()
    common.assert_new_sampling_namespace(output_root, project_root)
    report_json = output_root / "ownership_selector_qa_report.json"
    report_md = output_root / "ownership_selector_qa_report.md"
    report_json.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    write_report(result, report_md)
    hash_ledger = {
        "qa_status": result["status"], "ready_for_posterior_gold_replay": all_pass,
        "gold_labels_used_for_selection": False, "raw_iq_read": False, "stage3_stage4_read": False,
        "ownership_selector_qa_report_json_sha256": sha256_file(report_json),
        "ownership_selector_qa_report_md_sha256": sha256_file(report_md),
        "ownership_schema_manifest_sha256": schema["actual_schema_manifest_sha256"],
        "ownership_schema_sha256": schema["ownership_schema_sha256"],
        "parent_parameter_sha256": schema["parent_frozen_parameter_sha256"],
        "parent_artifact_sha256": expected_parent_hashes,
        "output_artifact_sha256": source_hashes,
        "counts": result["counts"], "issues": result["issues"],
    }
    (output_root / "ownership_qa_hashes.json").write_text(json.dumps(hash_ledger, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return result


def write_report(result: Mapping[str, Any], path: Path) -> None:
    counts = result["counts"]
    summary = result["component_summary"]
    workload = result["workload"]
    lines = [
        "# Raw-Coarse v3 Component Ownership Gold-Blind QA",
        "",
        f"Status: **{result['status']}**",
        f"READY_FOR_POSTERIOR_GOLD_REPLAY: **{str(result['ready_for_posterior_gold_replay']).upper()}**",
        "",
        "This QA reads only the frozen v3.0 feature/component inputs and the new ownership namespace. It does not read raw IQ, Stage3, Stage4, coverage replay or gold labels.",
        "",
        "## Selector state and workload",
        "",
        f"- Stage0/window feature rows: `{counts['stage0_feature_windows']}`",
        f"- coarse seed: `{counts['coarse_seed']}`; coarse continuation: `{counts['coarse_continuation']}`",
        f"- guard promoted: `{counts['guard_promoted']}`; not promoted: `{counts['not_promoted']}`; inconclusive: `{counts['inconclusive']}`",
        f"- unique fine windows: `{counts['unique_fine_windows']}` / `{counts['stage0_feature_windows']}` ({counts['promotion_fraction_unique_fine']:.4%})",
        f"- projected Stage1 reduction: `{workload['projected_stage1_reduction_windows']}` windows ({workload['projected_stage1_reduction_fraction']:.4%})",
        f"- Stage2 executed: `{workload['stage2_executed']}`",
        "",
        "## Normalized membership result",
        "",
        f"- components preserved: `{counts['component_count']}`",
        f"- membership rows: `{counts['membership_row_count']}`",
        f"- overlap windows: `{counts['overlap_window_count']}`",
        f"- membership multiplicity: `{counts['membership_multiplicity_distribution']}`",
        f"- core component size min/p50/max: `{summary['core_size_min']}` / `{summary['core_size_p50']}` / `{summary['core_size_max']}`",
        f"- expanded component size min/p50/p90/max: `{summary['expanded_size_min']}` / `{summary['expanded_size_p50']}` / `{summary['expanded_size_p90']}` / `{summary['expanded_size_max']}`",
        f"- full-scene component: `{summary['full_scene_component']}`",
        f"- guard-caused component collapse: `{summary['guard_caused_component_collapse']}`",
        "",
        "Each `task x window x component` relation is a separate row. `primary_component_id` is deterministic display/sort metadata only. `not_promoted` remains an evidence state and is not a LOS/no-event label.",
        "",
        "## Provenance and release gate",
        "",
        f"- Ownership schema version: `{result['schema_version']}`",
        f"- Ownership schema SHA-256: `{result['ownership_schema_sha256']}`",
        f"- Parent scientific parameter SHA-256: `{result['parent_parameter_sha256']}`",
        f"- Scientific selector retuned: `{result['scientific_selector_retuned']}`",
        f"- Gold labels used for selection: `{result['gold_labels_used_for_selection']}`",
        f"- Raw IQ read: `{result['raw_iq_read']}`",
        f"- Stage3/Stage4 read: `{result['stage3_stage4_read']}`",
        f"- Coverage replay read: `{result['coverage_replay_read']}`",
        "",
    ]
    if result["status"] == "PASS":
        lines.append("Ownership/schema QA passed. The new artifacts are eligible for a later posterior gold replay, but no posterior gold replay was performed in this run.")
    else:
        lines.append("Ownership/schema QA failed. Do not perform posterior gold replay until the listed issues are resolved in a new namespace.")
    lines.extend(["", "Issues:", ""])
    if result["issues"]:
        lines.extend(f"- `{issue}`" for issue in result["issues"])
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-root", type=Path, required=True)
    parser.add_argument("--schema-manifest", type=Path, required=True)
    parser.add_argument("--expected-schema-manifest-sha256", required=True)
    parser.add_argument("--ownership-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    result = audit(args.feature_root, args.schema_manifest, args.expected_schema_manifest_sha256, args.ownership_root, args.output_root, args.project_root)
    print(f"OWNERSHIP_QA_STATUS={result['status']}")
    print(f"READY_FOR_POSTERIOR_GOLD_REPLAY={str(result['ready_for_posterior_gold_replay']).lower()}")
    print(f"OWNERSHIP_QA_OUTPUT={args.output_root.resolve()}")
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
