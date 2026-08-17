"""Rebuild v3.0 component ownership as an explicit membership relation.

This is a schema-only revision.  It consumes the frozen v3.0 window feature
table and the frozen v3.0 component artifact, never raw IQ or later SAGE
stages, and never changes the scientific selector state.  Boundary overlap is
represented as multiple rows in ``promotion_component_membership.csv``; core
components are not merged because their expanded guards happen to overlap.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import raw_coarse_v3_common as common


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "raw-coarse-v3-component-membership-1"
REVISION_TYPE = "component-ownership-schema-only-parent-selector-unchanged"
FORBIDDEN_GOLD_TOKENS = ("stage3", "stage4", "gold", "coverage_replay")

WINDOW_FIELDS = [
    "task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "window_id",
    "promotion_status", "promotion_reason", "legacy_v3_promotion_component_id",
    "not_promoted", "coverage_status", "primary_component_id",
    "primary_component_purpose", "component_membership_count",
    "component_membership_ids", "unique_fine_window", "ownership_schema_version",
    "ownership_schema_sha256", "parent_feature_sha256", "parent_component_sha256",
    "gold_labels_used_for_selection",
]

MEMBERSHIP_FIELDS = [
    "task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "window_id",
    "component_id", "membership_type", "distance_from_core_windows",
    "boundary_provenance", "source_component_provenance", "core_window_count",
    "expanded_window_count", "parent_component_artifact_sha256",
    "ownership_schema_version", "ownership_schema_sha256",
    "gold_labels_used_for_selection",
]

COMPONENT_FIELDS = [
    "task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz",
    "profile_rule", "component_id", "core_seed_window_count", "core_seed_window_ids",
    "expanded_window_count", "expanded_window_ids", "membership_row_count",
    "shared_expanded_window_count", "boundary_expansion_windows", "bridge_gap_windows",
    "closure_radius_windows", "parameter_hash", "parent_component_artifact_sha256",
    "ownership_schema_version", "ownership_schema_sha256", "gold_labels_used_for_selection",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return common.sha256_file(Path(path))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


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


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"integer value expected, got {value!r}") from exc


def parse_window_ids(value: Any) -> list[int]:
    result = [_int(item) for item in str(value or "").split(";") if str(item).strip()]
    if len(result) != len(set(result)):
        raise ValueError("component window IDs contain duplicates")
    return result


def _bool_string(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def reject_gold_blind_path(path: Path) -> None:
    """Reject any input namespace that could be a posterior/gold source."""

    lowered = str(Path(path)).replace("\\", "/").lower()
    if any(token in lowered for token in FORBIDDEN_GOLD_TOKENS):
        raise ValueError(f"gold-blind ownership rebuild rejects path: {path}")


def validate_schema_manifest(schema: Mapping[str, Any], schema_path: Path, expected_sha256: str) -> dict[str, Any]:
    actual_sha256 = sha256_file(schema_path)
    if actual_sha256.lower() != str(expected_sha256).lower():
        raise ValueError(f"schema manifest SHA-256 mismatch: {actual_sha256} != {expected_sha256}")
    if schema.get("manifest_type") != "raw_coarse_v3_component_ownership_schema_manifest":
        raise ValueError("unexpected ownership schema manifest type")
    if schema.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected ownership schema version")
    if schema.get("revision_type") != REVISION_TYPE:
        raise ValueError("ownership manifest is not marked schema-only")
    if schema.get("scientific_selector_retuned") is not False:
        raise ValueError("ownership manifest claims a scientific selector retune")
    if schema.get("gold_labels_used_for_selection") is not False:
        raise ValueError("ownership manifest is not gold-blind")
    freeze = schema.get("selection_freeze") or {}
    if freeze.get("gold_files_read_before_freeze") is not False or freeze.get("gold_event_positions_used_for_selection") is not False:
        raise ValueError("ownership manifest permits gold before freeze")
    ownership_spec = schema.get("ownership_spec")
    if not isinstance(ownership_spec, dict):
        raise ValueError("ownership_spec is missing")
    expected_ownership_sha = sha256_bytes(canonical_json(ownership_spec).encode("utf-8"))
    if schema.get("ownership_schema_sha256") != expected_ownership_sha:
        raise ValueError("ownership_schema_sha256 does not match ownership_spec")
    if schema.get("parent_frozen_parameter_sha256") == schema.get("ownership_schema_sha256"):
        raise ValueError("parent scientific parameter SHA was incorrectly reused as ownership SHA")
    return {"actual_schema_manifest_sha256": actual_sha256, **schema}


def _expected_parent_paths(schema: Mapping[str, Any], feature_root: Path) -> dict[str, Path]:
    names = {
        "feature": "v3_window_features.csv",
        "promotion": "promotion_manifest.csv",
        "component": "promotion_components.csv",
        "run_manifest": "feature_run_manifest.json",
    }
    paths = {key: feature_root / name for key, name in names.items()}
    for path in paths.values():
        reject_gold_blind_path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
    expected = schema.get("parent_artifact_sha256") or {}
    for key, path in paths.items():
        expected_hash = expected.get(key)
        if not expected_hash:
            raise ValueError(f"parent hash missing for {key}")
        actual = sha256_file(path)
        if actual.lower() != str(expected_hash).lower():
            raise ValueError(f"parent artifact hash mismatch for {key}: {actual} != {expected_hash}")
    return paths


def load_parent_artifacts(feature_root: Path, schema: Mapping[str, Any]) -> dict[str, Any]:
    feature_root = Path(feature_root).resolve()
    reject_gold_blind_path(feature_root)
    paths = _expected_parent_paths(schema, feature_root)
    feature_fields, features = read_csv(paths["feature"])
    promotion_fields, promotions = read_csv(paths["promotion"])
    component_fields, components = read_csv(paths["component"])
    run_manifest = read_json(paths["run_manifest"])
    required_features = {"task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "window_id", "promotion_status", "not_promoted", "coverage_status", "gold_labels_used_for_selection", "parameter_hash"}
    required_promotions = {"task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "window_id", "promotion_status", "not_promoted", "coverage_status", "gold_labels_used_for_selection"}
    required_components = {"task_id", "scene_id", "prn", "component_id", "seed_window_count", "first_window_id", "last_window_id", "component_window_ids", "boundary_expansion_windows", "bridge_gap_windows", "closure_radius_windows", "gold_labels_used_for_selection"}
    if not required_features.issubset(feature_fields) or not required_promotions.issubset(promotion_fields) or not required_components.issubset(component_fields):
        raise ValueError("parent v3 artifact schema is incomplete")
    expected_count = int((schema.get("parent_dataset") or {}).get("window_count", 0))
    window_ids = [_int(row["window_id"]) for row in features]
    if expected_count <= 0 or len(features) != expected_count or set(window_ids) != set(range(1, expected_count + 1)) or len(set(window_ids)) != expected_count:
        raise ValueError("parent feature windows are not the expected complete Stage0 window set")
    if len(promotions) != len(features) or {_int(row["window_id"]) for row in promotions} != set(window_ids):
        raise ValueError("parent promotion manifest does not cover the feature windows exactly")
    parent_parameter_sha = str(schema.get("parent_frozen_parameter_sha256", ""))
    if run_manifest.get("parameter_sha256") != parent_parameter_sha:
        raise ValueError("parent feature run parameter SHA mismatch")
    if run_manifest.get("gold_labels_used_for_selection") is not False or run_manifest.get("stage3_stage4_read") is not False:
        raise ValueError("parent feature run is not gold-blind")
    for row in features + promotions + components:
        if not _bool_string(row.get("gold_labels_used_for_selection")) is False:
            raise ValueError("parent artifact gold flag is not false")
    feature_by_window = {_int(row["window_id"]): row for row in features}
    promotion_by_window = {_int(row["window_id"]): row for row in promotions}
    for window_id, feature in feature_by_window.items():
        promotion = promotion_by_window[window_id]
        for field in ("task_id", "scene_id", "prn", "tracking_channel", "sample_rate_hz", "promotion_status", "not_promoted", "coverage_status"):
            if str(feature.get(field, "")) != str(promotion.get(field, "")):
                raise ValueError(f"parent feature/promotion mismatch at window {window_id}, field {field}")
    return {
        "paths": paths,
        "feature_fields": feature_fields,
        "promotion_fields": promotion_fields,
        "component_fields": component_fields,
        "features": features,
        "promotions": promotions,
        "components": components,
        "run_manifest": run_manifest,
        "feature_by_window": feature_by_window,
        "promotion_by_window": promotion_by_window,
        "parent_hashes": {key: sha256_file(path) for key, path in paths.items()},
    }


def _task_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (str(row.get("task_id", "")), str(row.get("scene_id", "")), str(row.get("prn", "")), str(row.get("tracking_channel", "")))


def build_memberships(parent: Mapping[str, Any], schema: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[tuple[str, int], list[str]]]:
    features = list(parent["features"])
    components = sorted(parent["components"], key=lambda row: str(row.get("component_id", "")))
    feature_by_key = {(_task_key(row), _int(row["window_id"])): row for row in features}
    task_windows: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
    promoted_by_task: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
    for row in features:
        task = _task_key(row)
        window_id = _int(row["window_id"])
        task_windows[task].add(window_id)
        if str(row.get("promotion_status", "")) == "coarse_promoted":
            promoted_by_task[task].add(window_id)

    membership_rows: list[dict[str, Any]] = []
    membership_by_key: dict[tuple[str, int], list[str]] = defaultdict(list)
    component_rows: list[dict[str, Any]] = []
    parent_component_sha = parent["parent_hashes"]["component"]
    ownership_sha = str(schema["ownership_schema_sha256"])
    for component in components:
        component_id = str(component.get("component_id", ""))
        if not component_id:
            raise ValueError("component ID is empty")
        task = _task_key(component)
        if task not in task_windows:
            # Old v3 component rows do not carry channel/sample rate.  Resolve
            # those fields from the unique matching feature task identity.
            matching_tasks = [key for key in task_windows if key[:3] == _task_key({"task_id": component.get("task_id"), "scene_id": component.get("scene_id"), "prn": component.get("prn")})[:3]]
            if len(matching_tasks) != 1:
                raise ValueError(f"component {component_id} has no unique parent task")
            task = matching_tasks[0]
        expanded = sorted(parse_window_ids(component.get("component_window_ids")))
        universe = task_windows[task]
        if not set(expanded).issubset(universe):
            raise ValueError(f"component {component_id} expands outside parent window universe")
        first_seed = _int(component.get("first_window_id"))
        last_seed = _int(component.get("last_window_id"))
        core = sorted(window_id for window_id in promoted_by_task[task] if first_seed <= window_id <= last_seed)
        if len(core) != _int(component.get("seed_window_count")):
            raise ValueError(f"component {component_id} core seed count changed")
        if not set(core).issubset(set(expanded)):
            raise ValueError(f"component {component_id} does not contain all core seeds")
        core_set = set(core)
        first_feature = feature_by_key[(task, min(expanded))]
        for window_id in expanded:
            membership_type = "core_seed" if window_id in core_set else "guard"
            distance = min(abs(window_id - seed) for seed in core)
            membership_rows.append({
                "task_id": task[0], "scene_id": task[1], "prn": task[2],
                "tracking_channel": first_feature.get("tracking_channel"),
                "sample_rate_hz": first_feature.get("sample_rate_hz"), "window_id": window_id,
                "component_id": component_id, "membership_type": membership_type,
                "distance_from_core_windows": distance,
                "boundary_provenance": "core_seed_promotion_evidence" if membership_type == "core_seed" else "fixed_boundary_expansion_from_core_component",
                "source_component_provenance": f"parent_promotion_components.csv#{component_id}",
                "core_window_count": len(core), "expanded_window_count": len(expanded),
                "parent_component_artifact_sha256": parent_component_sha,
                "ownership_schema_version": SCHEMA_VERSION, "ownership_schema_sha256": ownership_sha,
                "gold_labels_used_for_selection": "false",
            })
            membership_by_key[(task[0], window_id)].append(component_id)
        component_rows.append({
            "task_id": task[0], "scene_id": task[1], "prn": task[2],
            "tracking_channel": first_feature.get("tracking_channel"), "sample_rate_hz": first_feature.get("sample_rate_hz"),
            "profile_rule": component.get("profile_rule"), "component_id": component_id,
            "core_seed_window_count": len(core), "core_seed_window_ids": ";".join(str(item) for item in core),
            "expanded_window_count": len(expanded), "expanded_window_ids": ";".join(str(item) for item in expanded),
            "membership_row_count": len(expanded), "shared_expanded_window_count": 0,
            "boundary_expansion_windows": component.get("boundary_expansion_windows"),
            "bridge_gap_windows": component.get("bridge_gap_windows"), "closure_radius_windows": component.get("closure_radius_windows"),
            "parameter_hash": schema.get("parent_frozen_parameter_sha256"),
            "parent_component_artifact_sha256": parent_component_sha,
            "ownership_schema_version": SCHEMA_VERSION, "ownership_schema_sha256": ownership_sha,
            "gold_labels_used_for_selection": "false",
        })
    membership_rows.sort(key=lambda row: (row["task_id"], _int(row["window_id"]), row["component_id"]))
    for row in component_rows:
        ids = set(parse_window_ids(row["expanded_window_ids"]))
        task = str(row["task_id"])
        row["shared_expanded_window_count"] = sum(1 for window_id in ids if len(membership_by_key[(task, window_id)]) > 1)
    for key in membership_by_key:
        membership_by_key[key] = sorted(set(membership_by_key[key]))
    return membership_rows, component_rows, membership_by_key


def build_window_manifest(parent: Mapping[str, Any], membership_by_key: Mapping[tuple[str, int], list[str]], schema: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    parent_feature_sha = parent["parent_hashes"]["feature"]
    parent_component_sha = parent["parent_hashes"]["component"]
    ownership_sha = str(schema["ownership_schema_sha256"])
    for row in sorted(parent["features"], key=lambda item: (_task_key(item), _int(item["window_id"]))):
        task = _task_key(row)
        window_id = _int(row["window_id"])
        component_ids = list(membership_by_key.get((task[0], window_id), []))
        result.append({
            "task_id": row.get("task_id"), "scene_id": row.get("scene_id"), "prn": row.get("prn"),
            "tracking_channel": row.get("tracking_channel"), "sample_rate_hz": row.get("sample_rate_hz"),
            "window_id": window_id, "promotion_status": row.get("promotion_status"),
            "promotion_reason": row.get("promotion_reason"),
            "legacy_v3_promotion_component_id": row.get("promotion_component_id"),
            "not_promoted": row.get("not_promoted"), "coverage_status": row.get("coverage_status"),
            "primary_component_id": component_ids[0] if component_ids else "",
            "primary_component_purpose": "deterministic_display_sort_only_not_scientific_ownership" if component_ids else "none",
            "component_membership_count": len(component_ids),
            "component_membership_ids": ";".join(component_ids),
            "unique_fine_window": "true" if component_ids else "false",
            "ownership_schema_version": SCHEMA_VERSION, "ownership_schema_sha256": ownership_sha,
            "parent_feature_sha256": parent_feature_sha, "parent_component_sha256": parent_component_sha,
            "gold_labels_used_for_selection": "false",
        })
    return result


def _multiplicity_distribution(membership_by_key: Mapping[tuple[str, int], list[str]], features: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(len(membership_by_key.get((_task_key(row)[0], _int(row["window_id"])), [])) for row in features)
    return {str(key): counts[key] for key in sorted(counts)}


def rebuild(feature_root: Path, schema_manifest_path: Path, expected_schema_manifest_sha256: str, output_root: Path, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    feature_root = Path(feature_root).resolve()
    schema_manifest_path = Path(schema_manifest_path).resolve()
    output_root = Path(output_root).resolve()
    reject_gold_blind_path(schema_manifest_path)
    schema = validate_schema_manifest(read_json(schema_manifest_path), schema_manifest_path, expected_schema_manifest_sha256)
    parent = load_parent_artifacts(feature_root, schema)
    membership_rows, component_rows, membership_by_key = build_memberships(parent, schema)
    window_rows = build_window_manifest(parent, membership_by_key, schema)
    common.assert_new_sampling_namespace(output_root, project_root)
    membership_path = output_root / "promotion_component_membership.csv"
    component_path = output_root / "promotion_components.csv"
    window_path = output_root / "promotion_manifest.csv"
    write_csv(membership_path, membership_rows, MEMBERSHIP_FIELDS)
    write_csv(component_path, component_rows, COMPONENT_FIELDS)
    write_csv(window_path, window_rows, WINDOW_FIELDS)
    unique_fine = sum(1 for row in window_rows if row["unique_fine_window"] == "true")
    overlap_count = sum(1 for ids in membership_by_key.values() if len(ids) > 1)
    run_manifest = {
        "builder": "rebuild_raw_coarse_v3_component_ownership.py",
        "created_at_utc": utc_now(), "schema_version": SCHEMA_VERSION, "revision_type": REVISION_TYPE,
        "schema_manifest_path": str(schema_manifest_path), "schema_manifest_sha256": schema["actual_schema_manifest_sha256"],
        "ownership_schema_sha256": schema["ownership_schema_sha256"],
        "parent_feature_root": str(feature_root), "parent_artifact_sha256": parent["parent_hashes"],
        "parent_frozen_parameter_sha256": schema["parent_frozen_parameter_sha256"],
        "parent_frozen_parameter_manifest_sha256": schema["parent_frozen_parameter_manifest_sha256"],
        "source_script_sha256": sha256_file(Path(__file__)),
        "feature_row_count": len(window_rows), "component_count": len(component_rows),
        "membership_row_count": len(membership_rows), "unique_fine_window_count": unique_fine,
        "overlap_window_count": overlap_count, "membership_multiplicity_distribution": _multiplicity_distribution(membership_by_key, parent["features"]),
        "component_merge_due_to_boundary": False, "scientific_selector_retuned": False,
        "gold_labels_used_for_selection": False, "raw_iq_read": False,
        "evidence_capture_rerun": False, "stage3_stage4_read": False,
        "posterior_sources_read": False, "not_promoted_semantics_unchanged": True,
        "primary_component_is_display_only": True,
        "files": [membership_path.name, component_path.name, window_path.name],
    }
    run_path = output_root / "ownership_run_manifest.json"
    run_path.write_text(json.dumps(run_manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    artifact_paths = [membership_path, component_path, window_path, run_path]
    hashes = {path.name: sha256_file(path) for path in artifact_paths}
    hashes.update({"schema_manifest_sha256": schema["actual_schema_manifest_sha256"], "ownership_schema_sha256": schema["ownership_schema_sha256"], "gold_labels_used_for_selection": False})
    (output_root / "ownership_artifact_hashes.json").write_text(json.dumps(hashes, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return {"output_root": str(output_root), "run_manifest": run_manifest, "artifact_hashes": hashes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-root", type=Path, required=True)
    parser.add_argument("--schema-manifest", type=Path, required=True)
    parser.add_argument("--expected-schema-manifest-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    result = rebuild(args.feature_root, args.schema_manifest, args.expected_schema_manifest_sha256, args.output_root, args.project_root)
    print(f"OWNERSHIP_OUTPUT={result['output_root']}")
    print(f"OWNERSHIP_MEMBERSHIP_ROWS={result['run_manifest']['membership_row_count']}")
    print(f"OWNERSHIP_UNIQUE_FINE_WINDOWS={result['run_manifest']['unique_fine_window_count']}")
    print(f"OWNERSHIP_OVERLAP_WINDOWS={result['run_manifest']['overlap_window_count']}")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
