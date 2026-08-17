"""Posterior gold replay for the frozen G16 raw-coarse v3 selector.

The freeze gate is evaluated before any Stage3/Stage4 file is opened.  After
that gate, this script only compares existing G16 gold center windows with the
already-frozen ownership union.  It never rebuilds features/components and
never changes scientific selector parameters.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import raw_coarse_v3_common as common


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PARAMETER_SHA256 = "3f6330f8c88b4901feda2e0cb9bd9e8dcd6350aec6270fd0d3985f5ca2669642"
EXPECTED_OWNERSHIP_SCHEMA_SHA256 = "29e557d330fd2b510360ea3bb30a286088032b1a44eb4cb76fe5dc94da4929de"
EXPECTED_SCHEMA_MANIFEST_SHA256 = "1dae14dbdbdd5093aeea479d739a1d8a89e09e9527053030dfd30573f5c18160"
EXPECTED_EVIDENCE_SHA256 = "60b3259cdc054d3e6b982bf8c03cb620594cfa7db62f7ff57cfa5d1a27d7caa4"
EXPECTED_FEATURE_SHA256 = "330a31efb3bdd3ae94b58497ab80cecc6ed190fb69deda2f471a729be85b95c6"
EXPECTED_PROMOTION_SHA256 = "e4952df180eb07d56c091ace3bf31b9f08301c265a83b9634e3e3f675a382dc9"
EXPECTED_MEMBERSHIP_SHA256 = "2e6038e4b4d230f1aaa308f76b15b1678bbdd3b89481e2fc2442b135b16147c8"
EXPECTED_OWNERSHIP_QA_STATUS = "PASS"
EXPECTED_WINDOWS = 2229
EXPECTED_UNIQUE_FINE_WINDOWS = 1222
EXPECTED_CONFIRMED_COUNT = 4
EXPECTED_CONFIRMED_CLOSURE_COUNT = 16
EXPECTED_STAGE3_CLOSURE_COUNT = 44
FORBIDDEN_INPUT_TOKENS = ("coverage_replay", "posterior_replay")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return common.sha256_file(Path(path))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object expected: {path}")
    return value


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def as_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def reject_input_namespace(path: Path) -> None:
    lowered = str(Path(path)).replace("\\", "/").lower()
    if any(token in lowered for token in FORBIDDEN_INPUT_TOKENS):
        raise ValueError(f"selection input cannot come from replay output namespace: {path}")
    if "sage_results" in lowered:
        return


def require_hash(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        raise ValueError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return actual


def pre_gold_freeze_gate(
    parameter_manifest_path: Path,
    ownership_schema_path: Path,
    feature_root: Path,
    ownership_root: Path,
    evidence_qa_report_path: Path,
    ownership_qa_report_path: Path,
    ownership_qa_hashes_path: Path,
) -> dict[str, Any]:
    """Verify every selection artifact before opening any gold file."""

    for path in (parameter_manifest_path, ownership_schema_path, feature_root, ownership_root, evidence_qa_report_path, ownership_qa_report_path, ownership_qa_hashes_path):
        if not Path(path).exists():
            raise FileNotFoundError(path)
    parameter_manifest_sha = require_hash(parameter_manifest_path, "a83677564cbcf896c2bd2613a918b3efda7e7fdeeeb607e944822db356125d36", "parameter manifest")
    schema_manifest_sha = require_hash(ownership_schema_path, EXPECTED_SCHEMA_MANIFEST_SHA256, "ownership schema manifest")
    parameter_manifest = read_json(parameter_manifest_path)
    schema_manifest = read_json(ownership_schema_path)
    if parameter_manifest.get("parameter_sha256") != EXPECTED_PARAMETER_SHA256:
        raise ValueError("parent scientific parameter SHA mismatch")
    if schema_manifest.get("ownership_schema_sha256") != EXPECTED_OWNERSHIP_SCHEMA_SHA256:
        raise ValueError("ownership schema SHA mismatch")
    if schema_manifest.get("parent_frozen_parameter_sha256") != EXPECTED_PARAMETER_SHA256:
        raise ValueError("ownership schema parent parameter SHA mismatch")
    if schema_manifest.get("gold_labels_used_for_selection") is not False:
        raise ValueError("ownership schema is not gold-blind")

    feature_path = Path(feature_root) / "v3_window_features.csv"
    promotion_path = Path(feature_root) / "promotion_manifest.csv"
    membership_path = Path(ownership_root) / "promotion_component_membership.csv"
    feature_sha = require_hash(feature_path, EXPECTED_FEATURE_SHA256, "feature artifact")
    promotion_sha = require_hash(promotion_path, EXPECTED_PROMOTION_SHA256, "promotion artifact")
    membership_sha = require_hash(membership_path, EXPECTED_MEMBERSHIP_SHA256, "membership artifact")

    evidence_qa = read_json(evidence_qa_report_path)
    ownership_qa = read_json(ownership_qa_report_path)
    ownership_hashes = read_json(ownership_qa_hashes_path)
    if evidence_qa.get("status") != "PASS" or evidence_qa.get("gold_labels_used_for_selection") is not False or evidence_qa.get("raw_iq_read") is not False:
        raise ValueError("evidence QA gate is not a gold-blind PASS")
    if ownership_qa.get("status") != EXPECTED_OWNERSHIP_QA_STATUS or ownership_qa.get("ready_for_posterior_gold_replay") is not True:
        raise ValueError("ownership QA is not PASS/ready")
    if ownership_qa.get("gold_labels_used_for_selection") is not False or ownership_qa.get("raw_iq_read") is not False or ownership_qa.get("stage3_stage4_read") is not False or ownership_qa.get("coverage_replay_read") is not False:
        raise ValueError("ownership QA is not gold-blind")
    if ownership_qa.get("issues") != []:
        raise ValueError("ownership QA has unresolved issues")
    recorded_output = ownership_hashes.get("output_artifact_sha256", {})
    if recorded_output.get("promotion_component_membership.csv") != membership_sha:
        raise ValueError("ownership QA ledger does not match membership artifact")
    if ownership_hashes.get("parent_parameter_sha256") != EXPECTED_PARAMETER_SHA256:
        raise ValueError("ownership QA ledger parent parameter mismatch")
    feature_fields, feature_rows = read_csv(feature_path)
    promotion_fields, promotion_rows = read_csv(promotion_path)
    membership_fields, membership_rows = read_csv(membership_path)
    if len(feature_rows) != EXPECTED_WINDOWS or len(promotion_rows) != EXPECTED_WINDOWS:
        raise ValueError("frozen selection artifacts do not contain 2229 windows")
    if len(membership_rows) != 1248:
        raise ValueError("frozen membership artifact does not contain 1248 rows")
    if int(ownership_qa.get("counts", {}).get("unique_fine_windows", -1)) != EXPECTED_UNIQUE_FINE_WINDOWS:
        raise ValueError("frozen unique fine-window count is not 1222")
    if feature_rows and any(str(row.get("gold_labels_used_for_selection", "")).lower() != "false" for row in feature_rows):
        raise ValueError("feature artifact contains a non-false gold flag")
    if promotion_rows and any(str(row.get("gold_labels_used_for_selection", "")).lower() != "false" for row in promotion_rows):
        raise ValueError("promotion artifact contains a non-false gold flag")
    if membership_rows and any(str(row.get("gold_labels_used_for_selection", "")).lower() != "false" for row in membership_rows):
        raise ValueError("membership artifact contains a non-false gold flag")
    return {
        "freeze_checked_at_utc": utc_now(),
        "parameter_manifest_path": str(parameter_manifest_path.resolve()),
        "parameter_manifest_sha256": parameter_manifest_sha,
        "parameter_sha256": EXPECTED_PARAMETER_SHA256,
        "ownership_schema_path": str(ownership_schema_path.resolve()),
        "ownership_schema_manifest_sha256": schema_manifest_sha,
        "ownership_schema_sha256": EXPECTED_OWNERSHIP_SCHEMA_SHA256,
        "feature_artifact_path": str(feature_path.resolve()),
        "feature_artifact_sha256": feature_sha,
        "promotion_artifact_path": str(promotion_path.resolve()),
        "promotion_artifact_sha256": promotion_sha,
        "membership_artifact_path": str(membership_path.resolve()),
        "membership_artifact_sha256": membership_sha,
        "evidence_qa_report_path": str(Path(evidence_qa_report_path).resolve()),
        "evidence_qa_report_sha256": sha256_file(evidence_qa_report_path),
        "evidence_qa_status": evidence_qa.get("status"),
        "ownership_qa_report_path": str(Path(ownership_qa_report_path).resolve()),
        "ownership_qa_report_sha256": sha256_file(ownership_qa_report_path),
        "ownership_qa_hashes_path": str(Path(ownership_qa_hashes_path).resolve()),
        "ownership_qa_hashes_sha256": sha256_file(ownership_qa_hashes_path),
        "ownership_qa_status": ownership_qa.get("status"),
        "selection_artifacts_frozen_before_gold": True,
        "feature_row_count": len(feature_rows),
        "membership_row_count": len(membership_rows),
        "unique_fine_window_count": EXPECTED_UNIQUE_FINE_WINDOWS,
        "feature_fields": feature_fields,
        "promotion_fields": promotion_fields,
        "membership_fields": membership_fields,
    }


def bounded_closure(centers: Iterable[int], universe: set[int], radius: int = 2) -> set[int]:
    return {window_id for center in centers for window_id in range(center - radius, center + radius + 1) if window_id in universe}


def load_gold(stage3_path: Path, stage4_summary_path: Path, stage4_paths_path: Path) -> dict[str, Any]:
    stage3_fields, stage3_rows = read_csv(stage3_path)
    stage4_fields, stage4_rows = read_csv(stage4_summary_path)
    stage4_path_fields, stage4_path_rows = read_csv(stage4_paths_path)
    confirmed_rows = [
        row for row in stage4_rows
        if as_int(row.get("joint_valid")) == 1 and (as_int(row.get("joint_multipath_count")) or 0) > 0
    ]
    confirmed_centers = sorted({as_int(row.get("center_window_id")) for row in confirmed_rows if as_int(row.get("center_window_id")) is not None})
    reliable_rows = [row for row in stage3_rows if as_int(row.get("reliable_multipath")) == 1]
    reliable_centers = sorted({as_int(row.get("center_window_id")) for row in reliable_rows if as_int(row.get("center_window_id")) is not None})
    return {
        "stage3_fields": stage3_fields,
        "stage3_rows": stage3_rows,
        "stage4_fields": stage4_fields,
        "stage4_rows": stage4_rows,
        "stage4_path_fields": stage4_path_fields,
        "stage4_path_rows": stage4_path_rows,
        "confirmed_rows": confirmed_rows,
        "confirmed_centers": confirmed_centers,
        "reliable_rows": reliable_rows,
        "reliable_centers": reliable_centers,
        "gold_source_hashes": {
            "stage3_reliable_centers.csv": sha256_file(stage3_path),
            "stage4_joint_summary.csv": sha256_file(stage4_summary_path),
            "stage4_joint_paths.csv": sha256_file(stage4_paths_path),
        },
    }


def coverage_rows(
    family: str,
    target_windows: Iterable[int],
    window_by_id: Mapping[int, Mapping[str, str]],
    membership_by_window: Mapping[int, list[Mapping[str, str]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window_id in sorted(set(target_windows)):
        window = window_by_id[window_id]
        memberships = membership_by_window.get(window_id, [])
        core_ids = sorted({str(row["component_id"]) for row in memberships if row.get("membership_type") == "core_seed"})
        guard_ids = sorted({str(row["component_id"]) for row in memberships if row.get("membership_type") == "guard"})
        if core_ids:
            coverage_kind = "direct_core"
        elif guard_ids:
            coverage_kind = "guard_only"
        else:
            coverage_kind = "not_covered"
        # The normalized membership table is the authoritative frozen
        # representation of the unique fine-window union for this replay.
        # Feature rows do not carry the post-ownership `unique_fine_window`
        # column, so do not infer coverage from a missing feature field.
        unique_fine_window = bool(memberships)
        rows.append({
            "gold_family": family,
            "window_id": window_id,
            "promotion_status": window.get("promotion_status", ""),
            "promotion_reason": window.get("promotion_reason", ""),
            "coverage_status": window.get("coverage_status", ""),
            "not_promoted": window.get("not_promoted", ""),
            "unique_fine_window": "true" if unique_fine_window else "false",
            "component_membership_count": len(memberships),
            "component_membership_ids": ";".join(sorted({str(row["component_id"]) for row in memberships})),
            "core_component_ids": ";".join(core_ids),
            "guard_component_ids": ";".join(guard_ids),
            "coverage_kind": coverage_kind,
            "direct_core_covered": "true" if bool(core_ids) else "false",
            "guard_only_covered": "true" if bool(guard_ids) and not core_ids else "false",
            "inconclusive": "true" if window.get("promotion_status") == "inconclusive" else "false",
            "membership_provenance": "|".join(
                f"{row['component_id']}:{row['membership_type']}:d{row['distance_from_core_windows']}"
                for row in sorted(memberships, key=lambda item: (str(item["component_id"]), str(item["membership_type"])))
            ),
        })
    return rows


def summarize_family(rows: Sequence[Mapping[str, Any]], expected_count: int) -> dict[str, Any]:
    counts = Counter(str(row["coverage_kind"]) for row in rows)
    inconclusive = sum(str(row["inconclusive"]).lower() == "true" for row in rows)
    covered = sum(str(row["unique_fine_window"]).lower() == "true" for row in rows)
    return {
        "target_window_count": len(rows),
        "expected_target_window_count": expected_count,
        "covered_window_count": covered,
        "recall": covered / len(rows) if rows else None,
        "direct_core_count": counts.get("direct_core", 0),
        "direct_core_fraction": counts.get("direct_core", 0) / len(rows) if rows else None,
        "guard_only_count": counts.get("guard_only", 0),
        "guard_only_fraction": counts.get("guard_only", 0) / len(rows) if rows else None,
        "not_covered_count": counts.get("not_covered", 0),
        "not_covered_fraction": counts.get("not_covered", 0) / len(rows) if rows else None,
        "inconclusive_count": inconclusive,
    }


def miss_attribution(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if row.get("coverage_kind") != "not_covered":
            continue
        reason = str(row.get("promotion_reason", ""))
        if row.get("promotion_status") == "inconclusive":
            layer = "inconclusive_feature"
        elif "secondary_presence" in reason:
            layer = "secondary_presence"
        elif "delay" in reason:
            layer = "secondary_delay_consistency"
        elif "doppler" in reason:
            layer = "secondary_doppler_consistency"
        elif "cross_scale" in reason:
            layer = "b1_b2_cross_scale_agreement"
        elif row.get("promotion_status") == "coarse_promoted":
            layer = "component_or_guard_closure"
        else:
            layer = "feature_promotion_not_selected"
        result.append({"gold_family": row["gold_family"], "window_id": row["window_id"], "promotion_status": row["promotion_status"], "promotion_reason": reason, "miss_layer": layer})
    return result


def write_report(path: Path, result: Mapping[str, Any], detail_rows: Sequence[Mapping[str, Any]]) -> None:
    summaries = result["coverage_summary"]
    lines = [
        "# G16 Raw-Coarse v3 Posterior Gold Coverage Replay",
        "",
        f"Overall decision: **{str(result['g16_v3_posterior_coverage_pass']).upper()}**",
        "",
        "This replay was executed only after the frozen selection artifacts passed evidence and ownership gold-blind QA. It did not rebuild features/components or change any scientific selector parameter. Stage3/Stage4 are used here only as posterior gold sources.",
        "",
        "## Freeze gate before gold read",
        "",
        f"- Parent scientific parameter SHA-256: `{result['freeze_gate']['parameter_sha256']}`",
        f"- Ownership schema SHA-256: `{result['freeze_gate']['ownership_schema_sha256']}`",
        f"- Feature SHA-256: `{result['freeze_gate']['feature_artifact_sha256']}`",
        f"- Promotion SHA-256: `{result['freeze_gate']['promotion_artifact_sha256']}`",
        f"- Membership SHA-256: `{result['freeze_gate']['membership_artifact_sha256']}`",
        f"- Evidence QA: `{result['freeze_gate']['evidence_qa_status']}`",
        f"- Ownership QA: `{result['freeze_gate']['ownership_qa_status']}`",
        f"- Selection artifacts frozen before gold: `{result['freeze_gate']['selection_artifacts_frozen_before_gold']}`",
        "",
        "## Gold sets",
        "",
        f"- Confirmed Stage4 centers ({len(result['gold']['confirmed_centers'])}): `{result['gold']['confirmed_centers']}`",
        f"- Confirmed center +/-2 unique closure ({len(result['gold']['confirmed_closure'])}): `{sorted(result['gold']['confirmed_closure'])}`",
        f"- Stage3 reliable centers ({len(result['gold']['reliable_centers'])}): `{result['gold']['reliable_centers']}`",
        f"- Stage3 reliable-center +/-2 unique union ({len(result['gold']['stage3_closure'])}): `{sorted(result['gold']['stage3_closure'])}`",
        "",
        "## Coverage summary",
        "",
        "| Gold family | Target | Covered | Recall | Direct/core | Guard-only | Uncovered | Inconclusive |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for family in ("confirmed_center", "confirmed_center_pm2", "stage3_reliable_center_pm2"):
        item = summaries[family]
        lines.append(f"| {family} | {item['target_window_count']} | {item['covered_window_count']} | {item['recall']:.4%} | {item['direct_core_count']} ({item['direct_core_fraction']:.4%}) | {item['guard_only_count']} ({item['guard_only_fraction']:.4%}) | {item['not_covered_count']} | {item['inconclusive_count']} |")
    lines.extend([
        "",
        "`direct/core` means at least one `core_seed` membership. `guard-only` means the unique window is covered only by fixed boundary/closure membership. A not-promoted guard is not relabeled as a selected seed, LOS reference or no-event window.",
        "",
        "## Gold-window coverage detail",
        "",
        "The complete machine-readable detail is in `posterior_gold_window_coverage.csv`. The following table preserves the promotion state and component membership for every target-family window.",
        "",
        "| Family | Window | Promotion | Reason | Coverage | Members | Core | Guard | Inconclusive |",
        "|---|---:|---|---|---|---:|---|---|---|",
    ])
    for row in detail_rows:
        lines.append(f"| {row['gold_family']} | {row['window_id']} | {row['promotion_status']} | {row['promotion_reason']} | {row['coverage_kind']} | {row['component_membership_count']} | {row['core_component_ids'] or '-'} | {row['guard_component_ids'] or '-'} | {row['inconclusive']} |")
    lines.extend(["", "## Miss attribution", ""])
    if result["miss_attribution"]:
        lines.extend(f"- window `{row['window_id']}` in `{row['gold_family']}`: `{row['miss_layer']}`; frozen reason=`{row['promotion_reason']}`" for row in result["miss_attribution"])
    else:
        lines.append("No missed target windows; no parameter or rule attribution was required.")
    lines.extend([
        "",
        "## Release decision",
        "",
        f"`G16_V3_POSTERIOR_COVERAGE_PASS={str(result['g16_v3_posterior_coverage_pass']).upper()}`",
        "",
        f"Frozen projected fine workload: `{result['workload']['unique_fine_windows']}/{result['workload']['stage0_windows']}` = `{result['workload']['fraction']:.4%}`. The workload target was not used to tune or alter the selector.",
        "",
    ])
    if result["g16_v3_posterior_coverage_pass"]:
        lines.append("All three hard coverage gates passed. The project may prepare an identical-frozen scientific-selector G25 control request, but this replay did not generate or execute that request.")
    else:
        lines.append("At least one hard coverage gate failed. Keep v3.0 as an immutable failed experiment and do not prepare G25 from this result; design v3.1 separately without tuning to individual gold windows.")
    lines.extend(["", "## Gold source hashes", ""])
    for name, digest in result["gold"]["source_hashes"].items():
        lines.append(f"- `{name}`: `{digest}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def replay(
    parameter_manifest_path: Path,
    ownership_schema_path: Path,
    feature_root: Path,
    ownership_root: Path,
    evidence_qa_report_path: Path,
    ownership_qa_report_path: Path,
    ownership_qa_hashes_path: Path,
    stage3_path: Path,
    stage4_summary_path: Path,
    stage4_paths_path: Path,
    output_root: Path,
    report_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    freeze_gate = pre_gold_freeze_gate(parameter_manifest_path, ownership_schema_path, feature_root, ownership_root, evidence_qa_report_path, ownership_qa_report_path, ownership_qa_hashes_path)
    # This is the first point at which posterior sources are opened.
    gold = load_gold(stage3_path, stage4_summary_path, stage4_paths_path)
    feature_fields, feature_rows = read_csv(Path(feature_root) / "v3_window_features.csv")
    membership_fields, membership_rows = read_csv(Path(ownership_root) / "promotion_component_membership.csv")
    if len(feature_rows) != EXPECTED_WINDOWS or len(membership_rows) != 1248:
        raise ValueError("frozen selection rows changed after pre-gold gate")
    universe = {as_int(row.get("window_id")) for row in feature_rows if as_int(row.get("window_id")) is not None}
    if len(universe) != EXPECTED_WINDOWS:
        raise ValueError("frozen feature window universe is invalid")
    window_by_id = {as_int(row["window_id"]): row for row in feature_rows}
    membership_by_window: dict[int, list[Mapping[str, str]]] = {}
    for row in membership_rows:
        window_id = as_int(row.get("window_id"))
        if window_id is None:
            raise ValueError("membership window ID is invalid")
        membership_by_window.setdefault(window_id, []).append(row)
    confirmed_closure = bounded_closure(gold["confirmed_centers"], universe)
    stage3_closure = bounded_closure(gold["reliable_centers"], universe)
    if len(gold["confirmed_centers"]) != EXPECTED_CONFIRMED_COUNT:
        raise ValueError(f"confirmed center count is {len(gold['confirmed_centers'])}, expected {EXPECTED_CONFIRMED_COUNT}")
    if len(confirmed_closure) != EXPECTED_CONFIRMED_CLOSURE_COUNT:
        raise ValueError(f"confirmed closure count is {len(confirmed_closure)}, expected {EXPECTED_CONFIRMED_CLOSURE_COUNT}")
    if len(stage3_closure) != EXPECTED_STAGE3_CLOSURE_COUNT:
        raise ValueError(f"Stage3 closure count is {len(stage3_closure)}, expected {EXPECTED_STAGE3_CLOSURE_COUNT}")
    detail_rows: list[dict[str, Any]] = []
    detail_rows.extend(coverage_rows("confirmed_center", gold["confirmed_centers"], window_by_id, membership_by_window))
    detail_rows.extend(coverage_rows("confirmed_center_pm2", confirmed_closure, window_by_id, membership_by_window))
    detail_rows.extend(coverage_rows("stage3_reliable_center_pm2", stage3_closure, window_by_id, membership_by_window))
    summaries = {
        "confirmed_center": summarize_family([row for row in detail_rows if row["gold_family"] == "confirmed_center"], EXPECTED_CONFIRMED_COUNT),
        "confirmed_center_pm2": summarize_family([row for row in detail_rows if row["gold_family"] == "confirmed_center_pm2"], EXPECTED_CONFIRMED_CLOSURE_COUNT),
        "stage3_reliable_center_pm2": summarize_family([row for row in detail_rows if row["gold_family"] == "stage3_reliable_center_pm2"], EXPECTED_STAGE3_CLOSURE_COUNT),
    }
    misses = miss_attribution(detail_rows)
    coverage_pass = all(summaries[name]["recall"] == 1.0 for name in summaries)
    result: dict[str, Any] = {
        "replay_type": "raw_coarse_v3_g16_posterior_coverage_replay",
        "created_at_utc": utc_now(),
        "gold_read_started_after_freeze_gate": True,
        "g16_v3_posterior_coverage_pass": coverage_pass,
        "ready_for_identical_frozen_g25_control_request": coverage_pass,
        "selector_rebuilt": False,
        "feature_builder_rerun": False,
        "raw_iq_read": False,
        "raw_capture_rerun": False,
        "matlab_called": False,
        "sage_called": False,
        "gold_labels_used_for_selection": False,
        "freeze_gate": freeze_gate,
        "gold": {
            "confirmed_centers": gold["confirmed_centers"],
            "confirmed_closure": sorted(confirmed_closure),
            "reliable_centers": gold["reliable_centers"],
            "stage3_closure": sorted(stage3_closure),
            "confirmed_stage4_rows": len(gold["confirmed_rows"]),
            "reliable_stage3_rows": len(gold["reliable_rows"]),
            "source_hashes": gold["gold_source_hashes"],
            "source_paths": {"stage3_reliable_centers.csv": str(stage3_path.resolve()), "stage4_joint_summary.csv": str(stage4_summary_path.resolve()), "stage4_joint_paths.csv": str(stage4_paths_path.resolve())},
        },
        "coverage_summary": summaries,
        "miss_attribution": misses,
        "workload": {"stage0_windows": EXPECTED_WINDOWS, "unique_fine_windows": EXPECTED_UNIQUE_FINE_WINDOWS, "fraction": EXPECTED_UNIQUE_FINE_WINDOWS / EXPECTED_WINDOWS, "selection_artifacts_unchanged_after_gold": True},
        "detail_row_count": len(detail_rows),
        "detail_fields": sorted({key for row in detail_rows for key in row}),
        "feature_fields_count": len(feature_fields),
        "membership_fields_count": len(membership_fields),
    }
    output_root = Path(output_root).resolve()
    common.assert_new_sampling_namespace(output_root, project_root)
    detail_path = output_root / "posterior_gold_window_coverage.csv"
    summary_path = output_root / "posterior_coverage_summary.json"
    manifest_path = output_root / "posterior_replay_manifest.json"
    write_csv(detail_path, detail_rows, [
        "gold_family", "window_id", "promotion_status", "promotion_reason", "coverage_status", "not_promoted", "unique_fine_window",
        "component_membership_count", "component_membership_ids", "core_component_ids", "guard_component_ids", "coverage_kind",
        "direct_core_covered", "guard_only_covered", "inconclusive", "membership_provenance",
    ])
    summary_path.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    manifest = {
        "replay_type": result["replay_type"], "created_at_utc": result["created_at_utc"],
        "freeze_gate": freeze_gate, "gold": result["gold"],
        "selector_rebuilt": False, "feature_builder_rerun": False,
        "gold_labels_used_for_selection": False, "posterior_comparison_only": True,
        "stage3_stage4_read": True, "raw_iq_read": False,
        "coverage_summary": summaries, "workload": result["workload"],
        "source_script_sha256": sha256_file(Path(__file__)),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    write_report(report_path, result, detail_rows)
    hash_ledger = {
        "g16_v3_posterior_coverage_pass": coverage_pass,
        "ready_for_identical_frozen_g25_control_request": coverage_pass,
        "gold_labels_used_for_selection": False,
        "raw_iq_read": False,
        "selection_artifacts_unchanged_after_gold": True,
        "posterior_gold_window_coverage_sha256": sha256_file(detail_path),
        "posterior_coverage_summary_sha256": sha256_file(summary_path),
        "posterior_replay_manifest_sha256": sha256_file(manifest_path),
        "posterior_coverage_report_sha256": sha256_file(report_path),
        "posterior_replay_script_sha256": sha256_file(Path(__file__)),
        "freeze_gate": freeze_gate,
        "gold_source_hashes": gold["gold_source_hashes"],
        "coverage_summary": summaries,
    }
    hashes_path = output_root / "posterior_replay_hashes.json"
    hashes_path.write_text(json.dumps(hash_ledger, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    result["output_paths"] = {"detail": str(detail_path), "summary": str(summary_path), "manifest": str(manifest_path), "report": str(report_path), "hashes": str(hashes_path)}
    result["output_hashes"] = {key: value for key, value in hash_ledger.items() if key.endswith("sha256")}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameter-manifest", type=Path, required=True)
    parser.add_argument("--ownership-schema", type=Path, required=True)
    parser.add_argument("--feature-root", type=Path, required=True)
    parser.add_argument("--ownership-root", type=Path, required=True)
    parser.add_argument("--evidence-qa-report", type=Path, required=True)
    parser.add_argument("--ownership-qa-report", type=Path, required=True)
    parser.add_argument("--ownership-qa-hashes", type=Path, required=True)
    parser.add_argument("--stage3", type=Path, required=True)
    parser.add_argument("--stage4-summary", type=Path, required=True)
    parser.add_argument("--stage4-paths", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    result = replay(
        args.parameter_manifest, args.ownership_schema, args.feature_root, args.ownership_root,
        args.evidence_qa_report, args.ownership_qa_report, args.ownership_qa_hashes,
        args.stage3, args.stage4_summary, args.stage4_paths, args.output_root, args.report, args.project_root,
    )
    print(f"G16_V3_POSTERIOR_COVERAGE_PASS={str(result['g16_v3_posterior_coverage_pass']).upper()}")
    print(f"READY_FOR_IDENTICAL_FROZEN_G25_CONTROL_REQUEST={str(result['ready_for_identical_frozen_g25_control_request']).upper()}")
    print(f"POSTERIOR_REPLAY_OUTPUT={args.output_root.resolve()}")
    print(f"POSTERIOR_REPLAY_REPORT={args.report.resolve()}")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
