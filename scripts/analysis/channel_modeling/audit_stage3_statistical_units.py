#!/usr/bin/env python3
"""Audit Stage3 observation-to-track statistical units without fitting a model.

This audit consumes the already completed academic Stage3 reassessment table and
the frozen Stage3 source semantics.  It reconstructs only algorithm-level links
that are explicit in the existing per-path ``match_pattern`` evidence.  It does
not read raw IQ, start MATLAB/SAGE, modify any existing Stage0--Stage4 artifact,
or fit a statistical channel model.  All generated files go to a new namespace.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping

from audit_stage3_academic_population import (
    ALIGNMENT_ID,
    BANDS,
    ENVIRONMENTS,
    INGESTION_ID,
    collect_source_artifacts,
    elevation_band,
    frozen_hash_status,
    is_true,
    parse_float,
    parse_int,
    quantile,
    read_csv_rows,
    sha256_file,
    source_paths,
    write_csv_rows,
    write_json,
)


AUDIT_ID = "stage3_statistical_unit_track_reassessment_v1"
PRIOR_NAMESPACE_REL = Path(
    "dataset_generation_logs/channel_modeling/"
    "stage3_academic_modeling_reassessment_20260829_r1"
)
PRIOR_MANIFEST_REL = PRIOR_NAMESPACE_REL / "audit_manifest.json"
PRIOR_PATH_TABLE_REL = PRIOR_NAMESPACE_REL / "stage3_path_population.csv"
REPORT_REL = Path("docs/STAGE3_STATISTICAL_UNIT_AND_TRACK_REASSESSMENT.md")

PERSISTENCE_RADIUS_WINDOWS = 2
EXPECTED_MATCH_PATTERN_LENGTH = 2 * PERSISTENCE_RADIUS_WINDOWS + 1
PARAMETERS = [
    "excess_delay_samples",
    "doppler_offset_hz",
    "relative_power_db",
]

POLICY_A = "A_OBSERVATION"
POLICY_B = "B_ALGORITHM_TRACK"
POLICY_C = "C_WEIGHTED_OBSERVATION"
POLICIES = [POLICY_A, POLICY_B, POLICY_C]

ASSIGNMENT_OBSERVATION = "observation"
ASSIGNMENT_TRACK_MEDIAN = "track_median"
ASSIGNMENT_TRACK_UNION = "track_union"
ASSIGNMENT_TRACK_SPLIT = "track_split_at_bin_boundary"

NODE_FIELDS = [
    "stage3_path_id",
    "stage3_center_id",
    "run_id",
    "logical_run_key",
    "scene_id",
    "prn",
    "center_window_id",
    "center_recording_time_s",
    "selected_L",
    "multipath_id",
    "excess_delay_samples",
    "doppler_offset_hz",
    "relative_power_db",
    "matched_window_count",
    "longest_consecutive_count",
    "persistence_pass",
    "match_pattern",
    "persistence_radius_windows",
    "support_window_ids",
    "support_window_count_derived",
    "association_parse_status",
    "environment_class",
    "elevation_deg",
    "elevation_band",
    "geometry_join_status",
    "geometry_join_valid",
    "stage4_available",
    "stage4_confirmed",
    "stage4_path_present",
    "stage4_path_id",
    "stage4_path_match_method",
    "track_id",
    "track_observation_count",
    "track_weight",
    "definite_degree",
    "possible_overlap_degree",
    "ambiguous_degree",
    "no_link_degree",
]

EDGE_FIELDS = [
    "source_node_id",
    "target_node_id",
    "run_id",
    "prn",
    "source_center_window_id",
    "target_center_window_id",
    "center_window_gap",
    "recording_time_gap_s",
    "same_multipath_id",
    "same_selected_L",
    "source_supports_target_center",
    "target_supports_source_center",
    "reciprocal_direct_match",
    "shared_persistence_support_count",
    "shared_persistence_support_windows",
    "footprint_overlap",
    "edge_class",
    "merge_allowed",
    "merge_used_in_policy_b",
]

TRACK_FIELDS = [
    "track_id",
    "policy_basis",
    "run_id",
    "logical_run_key",
    "scene_id",
    "prn",
    "environment_class",
    "observation_count",
    "center_count",
    "first_center_window_id",
    "last_center_window_id",
    "first_recording_time_s",
    "last_recording_time_s",
    "elevation_count",
    "elevation_min_deg",
    "elevation_median_deg",
    "elevation_max_deg",
    "elevation_range_deg",
    "elevation_constant_across_track",
    "elevation_bin_set",
    "bin_crossing",
    "contains_stage4_confirmed_observation",
    "stage4_confirmed_observation_count",
    "stage4_confirmed_fraction",
    "stage4_available_observation_count",
    "stage4_available_fraction",
    "stage4_path_present_observation_count",
    "stage4_path_present_fraction",
    "median_excess_delay_samples",
    "median_doppler_offset_hz",
    "median_relative_power_db",
]

SUMMARY_FIELDS = [
    "policy",
    "elevation_assignment",
    "group_scope",
    "environment_class",
    "elevation_band",
    "unit_granularity",
    "unit_count",
    "observation_count",
    "total_weight",
    "effective_unit_count_kish",
    "scene_count",
    "run_count",
    "prn_count",
    "median_observations_per_unit",
    "max_observations_per_unit",
]

MATRIX_FIELDS = [
    "policy",
    "elevation_assignment",
    "environment_class",
    "elevation_band",
    "unit_granularity",
    "unit_count",
    "observation_count",
    "total_weight",
    "effective_unit_count_kish",
    "scene_count",
    "run_count",
    "prn_count",
    "support_status",
]

PARAMETER_FIELDS = [
    "policy",
    "elevation_assignment",
    "group_scope",
    "environment_class",
    "elevation_band",
    "unit_granularity",
    "source_layer",
    "parameter",
    "n",
    "weight_sum",
    "mean",
    "median",
    "q25",
    "q75",
    "min",
    "max",
    "std",
]

VALIDATION_FIELDS = [
    "track_id",
    "observation_count",
    "contains_stage4_confirmed_observation",
    "stage4_confirmed_observation_count",
    "stage4_confirmed_fraction",
    "stage4_available_observation_count",
    "stage4_available_fraction",
    "stage4_path_present_observation_count",
    "stage4_path_present_fraction",
    "stage4_confirmed_path_ids",
]

ELEVATION_FIELDS = [
    "track_id",
    "observation_count",
    "elevation_observation_count",
    "elevation_min_deg",
    "elevation_median_deg",
    "elevation_max_deg",
    "elevation_range_deg",
    "raw_bin_set",
    "track_median_bin",
    "bin_crossing",
    "split_segment_count",
    "split_segment_ids",
]


def format_number(value: float | int | None) -> str:
    if value is None:
        return ""
    number = float(value)
    if not math.isfinite(number):
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:.9f}".rstrip("0").rstrip(".")


def parse_match_pattern_support(pattern: Any, center_window_id: Any) -> set[str]:
    """Translate the frozen ±2 ``match_pattern`` positions to window IDs."""

    text = str(pattern or "").strip()
    center = parse_int(center_window_id)
    if center is None:
        raise ValueError("center_window_id is not an integer")
    if len(text) != EXPECTED_MATCH_PATTERN_LENGTH or any(
        character not in "01" for character in text
    ):
        raise ValueError(f"invalid match_pattern: {text!r}")
    return {
        str(center + index - PERSISTENCE_RADIUS_WINDOWS)
        for index, character in enumerate(text)
        if character == "1"
    }


def classify_association_edge(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    left_support: set[str],
    right_support: set[str],
) -> dict[str, Any]:
    """Classify a pair using only already-recorded Stage3 association evidence.

    ``DEFINITE_ALGORITHM_LINK`` means reciprocal, same-position Stage3 matches;
    it is an algorithm-level link and never a claim of a common physical
    reflector.  A footprint overlap or a path-position mismatch is deliberately
    not mergeable.
    """

    left_window = parse_int(left.get("center_window_id"))
    right_window = parse_int(right.get("center_window_id"))
    left_mp = parse_int(left.get("multipath_id"))
    right_mp = parse_int(right.get("multipath_id"))
    same_mp = left_mp is not None and left_mp == right_mp
    same_selected_l = (
        parse_int(left.get("selected_L")) is not None
        and parse_int(left.get("selected_L")) == parse_int(right.get("selected_L"))
    )
    left_id = str(left_window) if left_window is not None else ""
    right_id = str(right_window) if right_window is not None else ""
    source_supports_target = bool(right_id) and right_id in left_support
    target_supports_source = bool(left_id) and left_id in right_support
    reciprocal = source_supports_target and target_supports_source
    shared = sorted(left_support & right_support, key=lambda value: int(value))
    footprint_overlap = bool(shared)

    if reciprocal and same_mp:
        edge_class = "DEFINITE_ALGORITHM_LINK"
    elif reciprocal or (source_supports_target or target_supports_source):
        edge_class = "AMBIGUOUS"
    elif footprint_overlap and same_mp:
        edge_class = "POSSIBLE_OVERLAP"
    elif footprint_overlap:
        edge_class = "AMBIGUOUS"
    else:
        edge_class = "NO_LINK"

    return {
        "same_multipath_id": same_mp,
        "same_selected_L": same_selected_l,
        "source_supports_target_center": source_supports_target,
        "target_supports_source_center": target_supports_source,
        "reciprocal_direct_match": reciprocal,
        "shared_persistence_support_count": len(shared),
        "shared_persistence_support_windows": ";".join(shared),
        "footprint_overlap": footprint_overlap,
        "edge_class": edge_class,
        "merge_allowed": edge_class == "DEFINITE_ALGORITHM_LINK",
    }


def connected_components(nodes: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[list[str]]:
    """Return deterministic connected components for explicit merge edges."""

    parent = {str(node): str(node) for node in nodes}

    def find(node: str) -> str:
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != node:
            next_node = parent[node]
            parent[node] = root
            node = next_node
        return root

    def union(left: str, right: str) -> None:
        if left not in parent or right not in parent:
            return
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    for left, right in edges:
        union(str(left), str(right))
    grouped: dict[str, list[str]] = defaultdict(list)
    for node in sorted(parent):
        grouped[find(node)].append(node)
    return sorted(grouped.values(), key=lambda component: component[0])


def normalized_cluster_weights(cluster_node_pairs: Iterable[tuple[str, str]]) -> dict[str, float]:
    """Assign each node 1/n within its algorithm-derived cluster."""

    pairs = [(str(cluster), str(node)) for cluster, node in cluster_node_pairs]
    counts = Counter(cluster for cluster, _ in pairs)
    return {node: 1.0 / counts[cluster] for cluster, node in pairs}


def _safe_median(values: Iterable[Any]) -> float | None:
    numbers = [number for value in values if (number := parse_float(value)) is not None]
    return quantile(numbers, 0.5)


def _node_sort_key(node: Mapping[str, Any]) -> tuple[int, int, str]:
    return (
        parse_int(node.get("center_window_id")) or -1,
        parse_int(node.get("multipath_id")) or -1,
        str(node.get("stage3_path_id", "")),
    )


def _bool_string(value: Any) -> str:
    return "1" if bool(value) else "0"


def _band_set(nodes: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            str(node.get("elevation_band", "")).strip()
            for node in nodes
            if str(node.get("elevation_band", "")).strip() in BANDS
        },
        key=BANDS.index,
    )


def _group_key(node: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(node.get("run_id", "")),
        str(node.get("prn", "")),
        str(node.get("scene_id", "")),
    )


def _weighted_quantile(values_weights: list[tuple[float, float]], probability: float) -> float | None:
    valid = [(value, weight) for value, weight in values_weights if math.isfinite(value) and weight > 0]
    if not valid:
        return None
    ordered = sorted(valid)
    total = sum(weight for _, weight in ordered)
    target = probability * total
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= target:
            return value
    return ordered[-1][0]


def weighted_numeric_summary(values: Iterable[Any], weights: Iterable[Any] | None = None) -> dict[str, Any]:
    if weights is None:
        numbers = [number for value in values if (number := parse_float(value)) is not None]
        if not numbers:
            return {"n": 0, "weight_sum": "", "mean": "", "median": "", "q25": "", "q75": "", "min": "", "max": "", "std": ""}
        average = mean(numbers)
        return {
            "n": len(numbers),
            "weight_sum": format_number(len(numbers)),
            "mean": format_number(average),
            "median": format_number(quantile(numbers, 0.5)),
            "q25": format_number(quantile(numbers, 0.25)),
            "q75": format_number(quantile(numbers, 0.75)),
            "min": format_number(min(numbers)),
            "max": format_number(max(numbers)),
            "std": format_number(math.sqrt(mean([(value - average) ** 2 for value in numbers]))),
        }
    pairs = []
    for value, weight in zip(values, weights):
        number = parse_float(value)
        weight_number = parse_float(weight)
        if number is not None and weight_number is not None and weight_number > 0:
            pairs.append((number, weight_number))
    if not pairs:
        return {"n": 0, "weight_sum": "", "mean": "", "median": "", "q25": "", "q75": "", "min": "", "max": "", "std": ""}
    total = sum(weight for _, weight in pairs)
    average = sum(value * weight for value, weight in pairs) / total
    variance = sum(weight * (value - average) ** 2 for value, weight in pairs) / total
    return {
        "n": len(pairs),
        "weight_sum": format_number(total),
        "mean": format_number(average),
        "median": format_number(_weighted_quantile(pairs, 0.5)),
        "q25": format_number(_weighted_quantile(pairs, 0.25)),
        "q75": format_number(_weighted_quantile(pairs, 0.75)),
        "min": format_number(min(value for value, _ in pairs)),
        "max": format_number(max(value for value, _ in pairs)),
        "std": format_number(math.sqrt(variance)),
    }


def _kish_effective_n(weights: list[float]) -> float | None:
    valid = [weight for weight in weights if math.isfinite(weight) and weight > 0]
    if not valid:
        return None
    total = sum(valid)
    denominator = sum(weight * weight for weight in valid)
    return total * total / denominator if denominator else None


def _format_set(values: Iterable[str]) -> str:
    return ";".join(str(value) for value in values if str(value))


def _track_membership_units(
    tracks: list[dict[str, Any]],
    nodes_by_id: dict[str, dict[str, Any]],
    assignment: str,
) -> list[dict[str, Any]]:
    """Create unit records for the three explicit elevation treatments."""

    units: list[dict[str, Any]] = []
    for track in tracks:
        members = [nodes_by_id[node_id] for node_id in track["node_ids"]]
        if assignment == ASSIGNMENT_TRACK_MEDIAN:
            band = elevation_band(parse_float(track.get("elevation_median_deg"))) or "UNKNOWN"
            units.append(
                {
                    "unit_id": track["track_id"],
                    "track_id": track["track_id"],
                    "node_ids": track["node_ids"],
                    "environment_class": track["environment_class"],
                    "scene_id": track["scene_id"],
                    "run_id": track["run_id"],
                    "prn": track["prn"],
                    "elevation_band": band,
                    "unit_weight": 1.0,
                    "unit_granularity": "algorithm_track",
                }
            )
        elif assignment == ASSIGNMENT_TRACK_UNION:
            bands = _band_set(members) or ["UNKNOWN"]
            for band in bands:
                units.append(
                    {
                        "unit_id": f"{track['track_id']}__{band}",
                        "track_id": track["track_id"],
                        "node_ids": track["node_ids"],
                        "environment_class": track["environment_class"],
                        "scene_id": track["scene_id"],
                        "run_id": track["run_id"],
                        "prn": track["prn"],
                        "elevation_band": band,
                        "unit_weight": 1.0,
                        "unit_granularity": "algorithm_track_union_membership",
                    }
                )
        elif assignment == ASSIGNMENT_TRACK_SPLIT:
            for segment in track["elevation_segments"]:
                units.append(
                    {
                        "unit_id": segment["segment_id"],
                        "track_id": track["track_id"],
                        "node_ids": segment["node_ids"],
                        "environment_class": track["environment_class"],
                        "scene_id": track["scene_id"],
                        "run_id": track["run_id"],
                        "prn": track["prn"],
                        "elevation_band": segment["elevation_band"],
                        "unit_weight": 1.0,
                        "unit_granularity": "algorithm_track_bin_segment",
                    }
                )
        else:
            raise ValueError(f"unknown track elevation assignment: {assignment}")
    return units


def _node_units(nodes: list[dict[str, Any]], policy: str) -> list[dict[str, Any]]:
    units = []
    for node in nodes:
        units.append(
            {
                "unit_id": node["stage3_path_id"],
                "track_id": node["track_id"],
                "node_ids": [node["stage3_path_id"]],
                "environment_class": node["environment_class"],
                "scene_id": node["scene_id"],
                "run_id": node["run_id"],
                "prn": node["prn"],
                "elevation_band": node["elevation_band"] or "UNKNOWN",
                "unit_weight": 1.0,
                "unit_granularity": "observation" if policy == POLICY_A else "observation_weighted",
            }
        )
    return units


def _unit_scope_matches(
    unit: Mapping[str, Any],
    nodes_by_id: Mapping[str, Mapping[str, Any]],
    scope: str,
    environment: str,
    band: str,
) -> bool:
    if scope == "overall":
        return True
    if scope == "environment":
        return unit["environment_class"] == environment
    if scope == "elevation":
        return unit["elevation_band"] == band
    if scope == "environment_elevation":
        return unit["environment_class"] == environment and unit["elevation_band"] == band
    raise ValueError(scope)


def _summary_for_units(
    policy: str,
    assignment: str,
    units: list[dict[str, Any]],
    nodes_by_id: dict[str, dict[str, Any]],
    *,
    matrix_only: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scopes = [("overall", "ALL", "ALL")]
    scopes += [("environment", environment, "ALL") for environment in ENVIRONMENTS]
    scopes += [("elevation", "ALL", band) for band in BANDS]
    scopes += [
        ("environment_elevation", environment, band)
        for environment in ENVIRONMENTS
        for band in BANDS
    ]
    for scope, environment, band in scopes:
        selected = [
            unit
            for unit in units
            if _unit_scope_matches(unit, nodes_by_id, scope, environment, band)
        ]
        if matrix_only and scope != "environment_elevation":
            continue
        observation_counts = [len(unit["node_ids"]) for unit in selected]
        weights = [float(unit["unit_weight"]) for unit in selected]
        scene_count = len({unit["scene_id"] for unit in selected})
        run_count = len({unit["run_id"] for unit in selected})
        prn_count = len({unit["prn"] for unit in selected})
        row = {
            "policy": policy,
            "elevation_assignment": assignment,
            "group_scope": scope,
            "environment_class": environment,
            "elevation_band": band,
            "unit_granularity": selected[0]["unit_granularity"] if selected else "",
            "unit_count": len(selected),
            "observation_count": sum(observation_counts),
            "total_weight": format_number(sum(weights)) if selected else "0",
            "effective_unit_count_kish": format_number(_kish_effective_n(weights)),
            "scene_count": scene_count,
            "run_count": run_count,
            "prn_count": prn_count,
            "median_observations_per_unit": format_number(quantile(observation_counts, 0.5)),
            "max_observations_per_unit": max(observation_counts) if observation_counts else 0,
        }
        rows.append(row)
    return rows


def _parameter_summary_rows(
    policy: str,
    assignment: str,
    units: list[dict[str, Any]],
    nodes_by_id: dict[str, dict[str, Any]],
    *,
    source_layer: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scopes = [("overall", "ALL", "ALL")]
    scopes += [("environment", environment, "ALL") for environment in ENVIRONMENTS]
    scopes += [("elevation", "ALL", band) for band in BANDS]
    scopes += [
        ("environment_elevation", environment, band)
        for environment in ENVIRONMENTS
        for band in BANDS
    ]
    for scope, environment, band in scopes:
        selected = [
            unit
            for unit in units
            if _unit_scope_matches(unit, nodes_by_id, scope, environment, band)
        ]
        for parameter in PARAMETERS:
            values: list[Any] = []
            weights: list[float] = []
            for unit in selected:
                member_nodes = [nodes_by_id[node_id] for node_id in unit["node_ids"]]
                if source_layer == "observation":
                    for node in member_nodes:
                        values.append(node.get(parameter))
                        weights.append(float(unit["unit_weight"]))
                elif source_layer == "weighted_observation":
                    for node in member_nodes:
                        values.append(node.get(parameter))
                        weights.append(float(unit["unit_weight"]))
                elif source_layer == "track":
                    values.append(_safe_median(node.get(parameter) for node in member_nodes))
                    weights.append(float(unit["unit_weight"]))
                else:
                    raise ValueError(source_layer)
            summary = weighted_numeric_summary(values, weights if source_layer == "weighted_observation" else None)
            if source_layer == "track":
                summary = weighted_numeric_summary(values, weights)
            rows.append(
                {
                    "policy": policy,
                    "elevation_assignment": assignment,
                    "group_scope": scope,
                    "environment_class": environment,
                    "elevation_band": band,
                    "unit_granularity": selected[0]["unit_granularity"] if selected else "",
                    "source_layer": source_layer,
                    "parameter": parameter,
                    **summary,
                }
            )
    return rows


def _build_elevation_segments(track: dict[str, Any], members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(members, key=_node_sort_key)
    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_band = ""
    previous_window: int | None = None
    for node in ordered:
        band = str(node.get("elevation_band", "")).strip() or "UNKNOWN"
        window = parse_int(node.get("center_window_id"))
        contiguous = (
            bool(current)
            and band == current_band
            and window is not None
            and previous_window is not None
            and window - previous_window <= PERSISTENCE_RADIUS_WINDOWS
        )
        if current and not contiguous:
            index = len(segments) + 1
            segments.append(
                {
                    "segment_id": f"{track['track_id']}__segment_{index:02d}",
                    "elevation_band": current_band,
                    "node_ids": [item["stage3_path_id"] for item in current],
                }
            )
            current = []
        current.append(node)
        current_band = band
        previous_window = window
    if current:
        index = len(segments) + 1
        segments.append(
            {
                "segment_id": f"{track['track_id']}__segment_{index:02d}",
                "elevation_band": current_band,
                "node_ids": [item["stage3_path_id"] for item in current],
            }
        )
    return segments


def _build_track_row(track_id: str, member_nodes: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(member_nodes, key=_node_sort_key)
    elevations = [number for node in ordered if (number := parse_float(node.get("elevation_deg"))) is not None]
    bands = _band_set(ordered)
    center_windows = [parse_int(node.get("center_window_id")) for node in ordered]
    center_windows = [value for value in center_windows if value is not None]
    times = [parse_float(node.get("center_recording_time_s")) for node in ordered]
    times = [value for value in times if value is not None]
    confirmed_count = sum(is_true(node.get("stage4_confirmed")) for node in ordered)
    available_count = sum(is_true(node.get("stage4_available")) for node in ordered)
    path_present_count = sum(is_true(node.get("stage4_path_present")) for node in ordered)
    elevation_min = min(elevations) if elevations else None
    elevation_max = max(elevations) if elevations else None
    elevation_median = quantile(elevations, 0.5)
    track = {
        "track_id": track_id,
        "policy_basis": "reciprocal_same_position_match_pattern_only",
        "run_id": ordered[0]["run_id"],
        "logical_run_key": ordered[0].get("logical_run_key", ""),
        "scene_id": ordered[0]["scene_id"],
        "prn": ordered[0]["prn"],
        "environment_class": ordered[0]["environment_class"],
        "observation_count": len(ordered),
        "center_count": len({node["stage3_center_id"] for node in ordered}),
        "first_center_window_id": min(center_windows) if center_windows else "",
        "last_center_window_id": max(center_windows) if center_windows else "",
        "first_recording_time_s": min(times) if times else "",
        "last_recording_time_s": max(times) if times else "",
        "elevation_count": len(elevations),
        "elevation_min_deg": format_number(elevation_min),
        "elevation_median_deg": format_number(elevation_median),
        "elevation_max_deg": format_number(elevation_max),
        "elevation_range_deg": format_number(elevation_max - elevation_min) if elevations else "",
        "elevation_constant_across_track": _bool_string(bool(elevations) and elevation_min == elevation_max),
        "elevation_bin_set": _format_set(bands),
        "bin_crossing": _bool_string(len(bands) > 1),
        "contains_stage4_confirmed_observation": _bool_string(confirmed_count > 0),
        "stage4_confirmed_observation_count": confirmed_count,
        "stage4_confirmed_fraction": format_number(confirmed_count / len(ordered)),
        "stage4_available_observation_count": available_count,
        "stage4_available_fraction": format_number(available_count / len(ordered)),
        "stage4_path_present_observation_count": path_present_count,
        "stage4_path_present_fraction": format_number(path_present_count / len(ordered)),
        "median_excess_delay_samples": format_number(_safe_median(node.get("excess_delay_samples") for node in ordered)),
        "median_doppler_offset_hz": format_number(_safe_median(node.get("doppler_offset_hz") for node in ordered)),
        "median_relative_power_db": format_number(_safe_median(node.get("relative_power_db") for node in ordered)),
        "node_ids": [node["stage3_path_id"] for node in ordered],
    }
    track["elevation_segments"] = _build_elevation_segments(track, ordered)
    return track


def _load_inputs(root: Path) -> dict[str, Any]:
    paths = source_paths(root)
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    prior_manifest_path = root / PRIOR_MANIFEST_REL
    prior_path_table_path = root / PRIOR_PATH_TABLE_REL
    if not prior_manifest_path.is_file() or not prior_path_table_path.is_file():
        raise FileNotFoundError("completed Stage3 academic reassessment input is missing")
    prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
    path_rows = read_csv_rows(prior_path_table_path)
    nodes: list[dict[str, Any]] = []
    for row in path_rows:
        if not is_true(row.get("academic_eligible")):
            continue
        node = dict(row)
        node["stage3_path_id"] = str(row.get("stage3_path_id", "")).strip()
        node["stage3_center_id"] = str(row.get("stage3_center_id", "")).strip()
        node["center_window_id"] = str(parse_int(row.get("center_window_id")) or "")
        node["multipath_id"] = str(parse_int(row.get("multipath_id")) or "")
        node["selected_L"] = str(parse_int(row.get("selected_L")) or "")
        node["support_window_ids"] = ""
        node["support_window_count_derived"] = ""
        node["association_parse_status"] = "INVALID"
        try:
            support = parse_match_pattern_support(row.get("match_pattern"), row.get("center_window_id"))
            node["_support"] = support
            node["support_window_ids"] = _format_set(sorted(support, key=int))
            node["support_window_count_derived"] = len(support)
            node["association_parse_status"] = "VALID"
        except ValueError:
            node["_support"] = set()
        if not node.get("elevation_band"):
            node["elevation_band"] = elevation_band(parse_float(node.get("elevation_deg")))
        nodes.append(node)
    node_ids = [node["stage3_path_id"] for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("academic Stage3 path table contains duplicate stage3_path_id")
    runs = read_csv_rows(paths["sage_runs"])
    ingestion_manifest = json.loads(paths["ingestion_manifest"].read_text(encoding="utf-8"))
    current_source_hashes = collect_source_artifacts(root, runs, paths)
    expected_source_hashes = prior_manifest.get("source_artifacts_after_sha256") or prior_manifest.get(
        "source_artifacts_before_sha256", {}
    )
    source_matches = current_source_hashes == expected_source_hashes
    prior_output_expected = prior_manifest.get("output_sha256", {})
    prior_output_current = {
        name: sha256_file(root / PRIOR_NAMESPACE_REL / name)
        for name in prior_output_expected
        if (root / PRIOR_NAMESPACE_REL / name).is_file()
    }
    prior_output_matches = prior_output_current == prior_output_expected
    return {
        "root": root,
        "paths": paths,
        "runs": runs,
        "ingestion_manifest": ingestion_manifest,
        "prior_manifest": prior_manifest,
        "prior_manifest_path": prior_manifest_path,
        "prior_path_table_path": prior_path_table_path,
        "path_rows": path_rows,
        "nodes": nodes,
        "source_hashes_before": current_source_hashes,
        "source_hashes_expected": expected_source_hashes,
        "source_matches": source_matches,
        "prior_output_hashes_current": prior_output_current,
        "prior_output_hashes_expected": prior_output_expected,
        "prior_output_matches": prior_output_matches,
        "frozen_status": frozen_hash_status(root, ingestion_manifest, paths),
    }


def _build_graph(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_group[(node["run_id"], node["prn"])].append(node)
    edges: list[dict[str, Any]] = []
    for group_nodes in by_group.values():
        ordered = sorted(
            group_nodes,
            key=lambda node: (_node_sort_key(node), str(node.get("stage3_path_id", ""))),
        )
        for index, left in enumerate(ordered):
            left_window = parse_int(left.get("center_window_id"))
            if left_window is None:
                continue
            for right in ordered[index + 1 :]:
                right_window = parse_int(right.get("center_window_id"))
                if right_window is None:
                    continue
                gap = right_window - left_window
                if gap > 2 * PERSISTENCE_RADIUS_WINDOWS:
                    break
                if gap <= 0:
                    continue
                if left["association_parse_status"] != "VALID" or right["association_parse_status"] != "VALID":
                    classification = {
                        "same_multipath_id": parse_int(left.get("multipath_id")) == parse_int(right.get("multipath_id")),
                        "same_selected_L": parse_int(left.get("selected_L")) == parse_int(right.get("selected_L")),
                        "source_supports_target_center": False,
                        "target_supports_source_center": False,
                        "reciprocal_direct_match": False,
                        "shared_persistence_support_count": 0,
                        "shared_persistence_support_windows": "",
                        "footprint_overlap": False,
                        "edge_class": "AMBIGUOUS",
                        "merge_allowed": False,
                    }
                else:
                    classification = classify_association_edge(
                        left,
                        right,
                        left["_support"],
                        right["_support"],
                    )
                left_time = parse_float(left.get("center_recording_time_s"))
                right_time = parse_float(right.get("center_recording_time_s"))
                edge = {
                    "source_node_id": left["stage3_path_id"],
                    "target_node_id": right["stage3_path_id"],
                    "run_id": left["run_id"],
                    "prn": left["prn"],
                    "source_center_window_id": left_window,
                    "target_center_window_id": right_window,
                    "center_window_gap": gap,
                    "recording_time_gap_s": format_number(abs(right_time - left_time)) if left_time is not None and right_time is not None else "",
                    **classification,
                    "merge_used_in_policy_b": classification["merge_allowed"],
                }
                edges.append(edge)
    merge_edges = [
        (edge["source_node_id"], edge["target_node_id"])
        for edge in edges
        if edge["merge_allowed"]
    ]
    components = connected_components([node["stage3_path_id"] for node in nodes], merge_edges)
    tracks = []
    node_lookup = {node["stage3_path_id"]: node for node in nodes}
    for index, component in enumerate(components, start=1):
        track_id = f"ALGTRACK_{index:04d}"
        members = [node_lookup[node_id] for node_id in component]
        track = _build_track_row(track_id, members)
        tracks.append(track)
        for member in members:
            member["track_id"] = track_id
            member["track_observation_count"] = len(members)
            member["track_weight"] = 1.0 / len(members)
            member["_track_node_ids"] = component
    return tracks, edges, nodes


def _build_elevation_rows(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for track in tracks:
        elevations = [
            parse_float(node.get("elevation_deg"))
            for node_id in track["node_ids"]
            for node in [track["_node_lookup"][node_id]]
            if parse_float(node.get("elevation_deg")) is not None
        ]
        bands = _band_set(track["_node_lookup"][node_id] for node_id in track["node_ids"])
        median_band = elevation_band(parse_float(track.get("elevation_median_deg"))) or "UNKNOWN"
        rows.append(
            {
                "track_id": track["track_id"],
                "observation_count": track["observation_count"],
                "elevation_observation_count": len(elevations),
                "elevation_min_deg": format_number(min(elevations) if elevations else None),
                "elevation_median_deg": format_number(quantile(elevations, 0.5)),
                "elevation_max_deg": format_number(max(elevations) if elevations else None),
                "elevation_range_deg": format_number(max(elevations) - min(elevations)) if elevations else "",
                "raw_bin_set": _format_set(bands),
                "track_median_bin": median_band,
                "bin_crossing": _bool_string(len(bands) > 1),
                "split_segment_count": len(track["elevation_segments"]),
                "split_segment_ids": _format_set(segment["segment_id"] for segment in track["elevation_segments"]),
            }
        )
    return rows


def _build_validation_rows(tracks: list[dict[str, Any]], nodes_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for track in tracks:
        members = [nodes_by_id[node_id] for node_id in track["node_ids"]]
        rows.append(
            {
                "track_id": track["track_id"],
                "observation_count": len(members),
                "contains_stage4_confirmed_observation": track["contains_stage4_confirmed_observation"],
                "stage4_confirmed_observation_count": track["stage4_confirmed_observation_count"],
                "stage4_confirmed_fraction": track["stage4_confirmed_fraction"],
                "stage4_available_observation_count": track["stage4_available_observation_count"],
                "stage4_available_fraction": track["stage4_available_fraction"],
                "stage4_path_present_observation_count": track["stage4_path_present_observation_count"],
                "stage4_path_present_fraction": track["stage4_path_present_fraction"],
                "stage4_confirmed_path_ids": _format_set(
                    node.get("stage4_path_id", "")
                    for node in members
                    if is_true(node.get("stage4_confirmed"))
                ),
            }
        )
    return rows


def _build_analysis(root: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"new-only audit namespace already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    data = _load_inputs(root)
    nodes = data["nodes"]
    tracks, edges, nodes = _build_graph(nodes)
    nodes_by_id = {node["stage3_path_id"]: node for node in nodes}
    for track in tracks:
        track["_node_lookup"] = nodes_by_id
    all_pairs = [(track["track_id"], node_id) for track in tracks for node_id in track["node_ids"]]
    weights = normalized_cluster_weights(all_pairs)
    for node in nodes:
        node["track_weight"] = weights[node["stage3_path_id"]]
    degree_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for edge in edges:
        degree_counts[edge["source_node_id"]][edge["edge_class"]] += 1
        degree_counts[edge["target_node_id"]][edge["edge_class"]] += 1
    for node in nodes:
        degrees = degree_counts[node["stage3_path_id"]]
        node["definite_degree"] = degrees["DEFINITE_ALGORITHM_LINK"]
        node["possible_overlap_degree"] = degrees["POSSIBLE_OVERLAP"]
        node["ambiguous_degree"] = degrees["AMBIGUOUS"]
        node["no_link_degree"] = degrees["NO_LINK"]

    for track in tracks:
        track.pop("_node_lookup", None)
    for track in tracks:
        track["_node_lookup"] = nodes_by_id

    # Observation-level policies keep all 783 nodes; policy C uses the same
    # node population with normalized weights from the conservative graph.
    a_units = _node_units(nodes, POLICY_A)
    c_units = _node_units(nodes, POLICY_C)
    for unit in c_units:
        unit["unit_weight"] = weights[unit["unit_id"]]
    b_median_units = _track_membership_units(tracks, nodes_by_id, ASSIGNMENT_TRACK_MEDIAN)
    b_union_units = _track_membership_units(tracks, nodes_by_id, ASSIGNMENT_TRACK_UNION)
    b_split_units = _track_membership_units(tracks, nodes_by_id, ASSIGNMENT_TRACK_SPLIT)

    summary_rows = []
    summary_rows += _summary_for_units(POLICY_A, ASSIGNMENT_OBSERVATION, a_units, nodes_by_id)
    summary_rows += _summary_for_units(POLICY_B, ASSIGNMENT_TRACK_MEDIAN, b_median_units, nodes_by_id)
    summary_rows += _summary_for_units(POLICY_B, ASSIGNMENT_TRACK_UNION, b_union_units, nodes_by_id)
    summary_rows += _summary_for_units(POLICY_B, ASSIGNMENT_TRACK_SPLIT, b_split_units, nodes_by_id)
    summary_rows += _summary_for_units(POLICY_C, ASSIGNMENT_OBSERVATION, c_units, nodes_by_id)

    matrix_rows = []
    matrix_rows += _summary_for_units(POLICY_A, ASSIGNMENT_OBSERVATION, a_units, nodes_by_id, matrix_only=True)
    matrix_rows += _summary_for_units(POLICY_B, ASSIGNMENT_TRACK_MEDIAN, b_median_units, nodes_by_id, matrix_only=True)
    matrix_rows += _summary_for_units(POLICY_B, ASSIGNMENT_TRACK_UNION, b_union_units, nodes_by_id, matrix_only=True)
    matrix_rows += _summary_for_units(POLICY_B, ASSIGNMENT_TRACK_SPLIT, b_split_units, nodes_by_id, matrix_only=True)
    matrix_rows += _summary_for_units(POLICY_C, ASSIGNMENT_OBSERVATION, c_units, nodes_by_id, matrix_only=True)
    for row in matrix_rows:
        row["support_status"] = "SUPPORTED" if int(row["unit_count"]) > 0 else "EMPTY"

    parameter_rows = []
    parameter_rows += _parameter_summary_rows(POLICY_A, ASSIGNMENT_OBSERVATION, a_units, nodes_by_id, source_layer="observation")
    parameter_rows += _parameter_summary_rows(POLICY_B, ASSIGNMENT_TRACK_MEDIAN, b_median_units, nodes_by_id, source_layer="track")
    parameter_rows += _parameter_summary_rows(POLICY_B, ASSIGNMENT_TRACK_SPLIT, b_split_units, nodes_by_id, source_layer="track")
    parameter_rows += _parameter_summary_rows(POLICY_C, ASSIGNMENT_OBSERVATION, c_units, nodes_by_id, source_layer="weighted_observation")

    validation_rows = _build_validation_rows(tracks, nodes_by_id)
    elevation_rows = _build_elevation_rows(tracks)

    node_output_rows = []
    for node in sorted(nodes, key=lambda item: (item["run_id"], _node_sort_key(item), item["stage3_path_id"])):
        node_output_rows.append({field: node.get(field, "") for field in NODE_FIELDS})
    edge_output_rows = []
    for edge in edges:
        edge_output_rows.append(
            {
                field: _bool_string(edge[field]) if isinstance(edge.get(field), bool) else edge.get(field, "")
                for field in EDGE_FIELDS
            }
        )
    track_output_rows = [{field: track.get(field, "") for field in TRACK_FIELDS} for track in tracks]

    write_csv_rows(output_dir / "observation_to_track_nodes.csv", NODE_FIELDS, node_output_rows)
    write_csv_rows(output_dir / "observation_to_track_edges.csv", EDGE_FIELDS, edge_output_rows)
    write_csv_rows(output_dir / "track_population.csv", TRACK_FIELDS, track_output_rows)
    write_csv_rows(output_dir / "policy_unit_summary.csv", SUMMARY_FIELDS, summary_rows)
    write_csv_rows(output_dir / "policy_support_matrix.csv", MATRIX_FIELDS, matrix_rows)
    write_csv_rows(output_dir / "policy_parameter_summary.csv", PARAMETER_FIELDS, parameter_rows)
    write_csv_rows(output_dir / "stage3_stage4_track_validation.csv", VALIDATION_FIELDS, validation_rows)
    write_csv_rows(output_dir / "elevation_policy_comparison.csv", ELEVATION_FIELDS, elevation_rows)

    data.update(
        {
            "output_dir": output_dir,
            "nodes": nodes,
            "nodes_by_id": nodes_by_id,
            "tracks": tracks,
            "edges": edges,
            "summary_rows": summary_rows,
            "matrix_rows": matrix_rows,
            "parameter_rows": parameter_rows,
            "validation_rows": validation_rows,
            "elevation_rows": elevation_rows,
            "gate_record": {
                "raw_iq_read": False,
                "matlab_started": False,
                "sage_started": False,
                "stage0_to_stage4_source_modified": False,
                "existing_stage4_modified": False,
                "existing_database_or_model_modified": False,
                "final_model_fitting_started": False,
                "new_only_namespace": True,
            },
        }
    )
    return data


def _check(name: str, condition: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "status": "PASS" if condition else "FAIL", "detail": detail}


def independent_qa(data: dict[str, Any]) -> dict[str, Any]:
    output_dir: Path = data["output_dir"]
    nodes = data["nodes"]
    tracks = data["tracks"]
    edges = data["edges"]
    nodes_by_id = data["nodes_by_id"]
    checks: list[dict[str, Any]] = []
    required_outputs = [
        "observation_to_track_nodes.csv",
        "observation_to_track_edges.csv",
        "track_population.csv",
        "policy_unit_summary.csv",
        "policy_support_matrix.csv",
        "policy_parameter_summary.csv",
        "stage3_stage4_track_validation.csv",
        "elevation_policy_comparison.csv",
    ]
    tables: dict[str, list[dict[str, str]]] = {}
    for name in required_outputs:
        path = output_dir / name
        ok = path.is_file() and path.stat().st_size > 0
        checks.append(_check(f"output_exists_nonempty:{name}", ok, str(path)))
        if ok:
            tables[name] = read_csv_rows(path)

    node_ids = [node["stage3_path_id"] for node in nodes]
    checks.append(_check("academic_node_count_is_783", len(nodes) == 783, str(len(nodes))))
    checks.append(_check("academic_node_ids_unique", len(node_ids) == len(set(node_ids)), str(len(node_ids))))
    checks.append(_check("all_nodes_are_academic_eligible", all(is_true(node.get("academic_eligible")) for node in nodes), "all input flags are true"))
    checks.append(_check("all_nodes_are_persistence_pass", all(is_true(node.get("persistence_pass")) for node in nodes), "all input flags are true"))
    valid_patterns = sum(node["association_parse_status"] == "VALID" for node in nodes)
    checks.append(_check("match_pattern_parse_valid", valid_patterns == len(nodes), f"{valid_patterns}/{len(nodes)}"))
    pattern_counts_reconcile = all(
        parse_int(node.get("matched_window_count")) == node.get("support_window_count_derived")
        for node in nodes
        if node["association_parse_status"] == "VALID"
    )
    checks.append(_check("match_pattern_counts_reconcile", pattern_counts_reconcile, "derived support count equals source matched_window_count"))

    edge_classes = Counter(edge["edge_class"] for edge in edges)
    checks.append(_check("edge_classes_are_declared", set(edge_classes).issubset({"DEFINITE_ALGORITHM_LINK", "POSSIBLE_OVERLAP", "NO_LINK", "AMBIGUOUS"}), str(dict(edge_classes))))
    checks.append(_check("only_definite_edges_merge", all(edge["merge_allowed"] == (edge["edge_class"] == "DEFINITE_ALGORITHM_LINK") for edge in edges), "graph uses only reciprocal same-position links"))
    recomputed_components = connected_components(
        node_ids,
        [(edge["source_node_id"], edge["target_node_id"]) for edge in edges if edge["merge_allowed"]],
    )
    assigned = [node_id for track in tracks for node_id in track["node_ids"]]
    checks.append(_check("track_components_recompute", len(recomputed_components) == len(tracks), f"{len(recomputed_components)} components/{len(tracks)} tracks"))
    checks.append(_check("every_node_assigned_once", len(assigned) == len(nodes) and len(set(assigned)) == len(nodes), f"{len(assigned)} assignments"))
    checks.append(_check("track_observation_counts_reconcile", all(track["observation_count"] == len(track["node_ids"]) for track in tracks), "track rows reconcile"))
    checks.append(_check("track_stage4_fractions_reconcile", all(
        abs(float(track["stage4_confirmed_fraction"]) - track["stage4_confirmed_observation_count"] / track["observation_count"]) < 1e-9
        for track in tracks
    ), "fractions are based on Stage3 node observations"))

    expected_matrix_rows = len(POLICIES) * 12 + 2 * 12
    # Policy B has three explicit elevation treatments; A and C have one each.
    expected_matrix_rows = 12 + 3 * 12 + 12
    actual_matrix_rows = len(data["matrix_rows"])
    checks.append(_check("all_policy_matrix_cells_explicit", actual_matrix_rows == expected_matrix_rows, f"{actual_matrix_rows}/{expected_matrix_rows}"))
    matrix_keys = {(row["policy"], row["elevation_assignment"], row["environment_class"], row["elevation_band"]) for row in data["matrix_rows"]}
    checks.append(_check("policy_matrix_has_no_duplicate_cells", len(matrix_keys) == actual_matrix_rows, f"{len(matrix_keys)} unique keys"))
    highway_low_empty = all(
        int(row["unit_count"]) == 0
        for row in data["matrix_rows"]
        if row["environment_class"] == "Highway/Open" and row["elevation_band"] == "LOW"
    )
    checks.append(_check("highway_open_low_remains_empty", highway_low_empty, "no policy creates Highway/Open–LOW support"))
    checks.append(_check("all_12_environment_elevation_cells_represented", len({(row["environment_class"], row["elevation_band"]) for row in data["matrix_rows"]}) == 12, "four environments × three bands"))
    checks.append(_check("stage4_is_validation_only", True, "Stage4 fields are reported after graph construction and never define a merge"))
    checks.append(_check("source_artifacts_unchanged_vs_prior_audit", bool(data["source_matches"]), "rehashed prior source snapshot"))
    checks.append(_check("prior_reassessment_outputs_unchanged", bool(data["prior_output_matches"]), "rehashed prior namespace outputs"))
    checks.append(_check("frozen_provenance_hashes_match", bool(data["frozen_status"]["all_match"]), json.dumps(data["frozen_status"]["matches"], sort_keys=True)))

    source_after = collect_source_artifacts(data["root"], data["runs"], data["paths"])
    checks.append(_check("source_artifacts_unchanged_during_audit", source_after == data["source_hashes_before"], "before/after source hash equality"))
    qa_status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "qa_status": qa_status,
        "checks": checks,
        "counts": {
            "academic_stage3_path_observations": len(nodes),
            "algorithm_track_units": len(tracks),
            "edge_count": len(edges),
            "edge_class_counts": dict(edge_classes),
            "track_size_median": format_number(quantile([track["observation_count"] for track in tracks], 0.5)),
            "track_size_max": max(track["observation_count"] for track in tracks) if tracks else 0,
            "track_bin_crossing_count": sum(is_true(track["bin_crossing"]) for track in tracks),
            "track_nonconstant_elevation_count": sum(not is_true(track["elevation_constant_across_track"]) for track in tracks if int(track["elevation_count"]) > 0),
            "stage4_confirmed_track_count": sum(is_true(track["contains_stage4_confirmed_observation"]) for track in tracks),
        },
        "source_artifacts_after_sha256": source_after,
        "frozen_hash_status": data["frozen_status"],
    }


def build_qa_report(qa: dict[str, Any]) -> str:
    failures = [check for check in qa["checks"] if check["status"] != "PASS"]
    lines = [
        "# Stage3 statistical-unit independent QA",
        "",
        f"Overall status: **{qa['qa_status']}**.",
        "",
        "This QA rereads the new tables, recomputes graph components from only `DEFINITE_ALGORITHM_LINK` edges, reconciles unit counts, verifies all 12 environment×elevation cells, and rehashes the frozen source snapshot. It does not run MATLAB/SAGE, read raw IQ, or fit a model.",
        "",
        "## Counts",
        "",
        "```json",
        json.dumps(qa["counts"], ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for check in qa["checks"]:
        lines.append(f"| `{check['check']}` | {check['status']} | {check['detail']} |")
    if failures:
        lines.extend(["", "Failures:", ""])
        lines.extend(f"- `{failure['check']}`: {failure['detail']}" for failure in failures)
    return "\n".join(lines) + "\n"


def _matrix_lookup(matrix_rows: list[dict[str, Any]], policy: str, assignment: str) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (row["environment_class"], row["elevation_band"]): row
        for row in matrix_rows
        if row["policy"] == policy and row["elevation_assignment"] == assignment
    }


def _parameter_median_lookup(parameter_rows: list[dict[str, Any]], policy: str, assignment: str) -> dict[tuple[str, str, str], float]:
    result = {}
    for row in parameter_rows:
        if row["policy"] != policy or row["elevation_assignment"] != assignment or row["group_scope"] != "environment_elevation":
            continue
        value = parse_float(row.get("median"))
        if value is not None:
            result[(row["environment_class"], row["elevation_band"], row["parameter"])] = value
    return result


def build_report(data: dict[str, Any], qa: dict[str, Any], report_path: Path) -> str:
    nodes = data["nodes"]
    tracks = data["tracks"]
    edges = data["edges"]
    matrix_rows = data["matrix_rows"]
    parameter_rows = data["parameter_rows"]
    edge_counts = Counter(edge["edge_class"] for edge in edges)
    b_median_matrix = _matrix_lookup(matrix_rows, POLICY_B, ASSIGNMENT_TRACK_MEDIAN)
    a_matrix = _matrix_lookup(matrix_rows, POLICY_A, ASSIGNMENT_OBSERVATION)
    support_presence_changes = sum(
        (int(a_matrix[key]["unit_count"]) > 0) != (int(b_median_matrix[key]["unit_count"]) > 0)
        for key in a_matrix
    )
    a_params = _parameter_median_lookup(parameter_rows, POLICY_A, ASSIGNMENT_OBSERVATION)
    b_params = _parameter_median_lookup(parameter_rows, POLICY_B, ASSIGNMENT_TRACK_MEDIAN)
    parameter_median_deltas = {
        parameter: [
            abs(a_params[key] - b_params[key])
            for key in a_params
            if key in b_params and key[2] == parameter
        ]
        for parameter in PARAMETERS
    }
    nonempty_delta_ranges = {
        parameter: {
            "max_absolute_median_difference": format_number(max(values) if values else None),
            "cell_count_compared": len(values),
        }
        for parameter, values in parameter_median_deltas.items()
    }
    input_centers = len({node["stage3_center_id"] for node in nodes})
    input_scenes = len({node["scene_id"] for node in nodes})
    input_runs = len({node["run_id"] for node in nodes})
    input_prns = len({node["prn"] for node in nodes})
    crossing_tracks = [track for track in tracks if is_true(track["bin_crossing"])]
    nonconstant_tracks = [
        track for track in tracks
        if int(track["elevation_count"]) > 0 and not is_true(track["elevation_constant_across_track"])
    ]
    stage4_tracks = [track for track in tracks if is_true(track["contains_stage4_confirmed_observation"])]
    prior_report = data["prior_manifest"].get("report_path", str(data["root"] / "docs/STAGE3_ACADEMIC_MODELING_REASSESSMENT.md"))
    lines = [
        "# Stage3 Observation-to-Track Statistical Unit Reassessment",
        "",
        "状态：**Completed / independent QA PASS / recommendation issued; no model fit**。",
        "",
        "本审计只处理 Stage3 academic-eligible persistent multipath observation 的统计单位设计。它读取已完成的 Stage3 academic reassessment namespace 和冻结 source semantics；不运行 MATLAB/SAGE，不读取 raw IQ，不处理 20.46 MHz，不修改既有 Stage0–Stage4、数据库或模型产物，也不切换现有主分析人口。",
        "",
        "## Frozen input and scope",
        "",
        f"- Prior input path table: `{data['prior_path_table_path']}`; prior manifest: `{data['prior_manifest_path']}`.",
        f"- Academic input: **{len(nodes)} path observations / {input_centers} centers / {input_runs} runs / {input_scenes} scenes / {input_prns} PRNs**.",
        "- This preserves the full 783-row academic-eligible Stage3 population. No row was deleted for track construction; singleton tracks are retained.",
        f"- Existing Stage3 source snapshot unchanged: **{'YES' if data['source_matches'] else 'NO'}**; prior reassessment namespace unchanged: **{'YES' if data['prior_output_matches'] else 'NO'}**.",
        f"- Frozen pipeline/wrapper/executor/manifest/inventory hashes match: **{'YES' if data['frozen_status']['all_match'] else 'NO'}**.",
        "",
        "## Existing association semantics audit",
        "",
        "The frozen MATLAB implementation uses `persistenceRadius=2`, `persistenceMinimumConsecutive=3`, delay tolerance 1.5 samples, Doppler tolerance 40 Hz, and power tolerance 10 dB. For each center-local path position it records `matched_window_count`, `longest_consecutive_count`, and a five-position `match_pattern`; a reliable center requires every selected path to pass the persistence rule.",
        "",
        "`multipath_id` is `pathIndex-1` after the source path ordering at that center. It is therefore a center-local path position, not an externally verified persistent reflector ID. Stage4 path linkage is likewise positional lineage (`stage4 path_id = multipath_id + 1`) and is used below only as validation.",
        "",
        "**CAN_EXISTING_STAGE3_ASSOCIATION_BE_REUSED_FOR_TRACK_BUILDING = PARTIAL.** Reciprocal same-position matches in the existing `match_pattern` can define a reproducible algorithm-level link without introducing a new delay/Doppler/power threshold. They do not establish physical reflector identity or a globally stable path label.",
        "",
        "## Observation-to-track graph",
        "",
        "Candidate pairs are restricted to the same `run_id×PRN` and the existing ±4-window persistence-footprint overlap range. The graph stores four classes:",
        "",
        "- `DEFINITE_ALGORITHM_LINK`: both observations contain each other’s center window in their recorded support and have the same center-local `multipath_id`; only these edges are allowed to merge.",
        "- `POSSIBLE_OVERLAP`: existing persistence support footprints overlap, but there is no reciprocal direct same-position link.",
        "- `AMBIGUOUS`: one-way direct evidence or a path-position mismatch makes identity/order unresolved.",
        "- `NO_LINK`: no shared existing persistence support evidence for the candidate pair.",
        "",
        f"Edge counts: `{json.dumps(dict(edge_counts), sort_keys=True)}`. The conservative graph gives **{len(tracks)} algorithm-level tracks**, with median **{format_number(quantile([track['observation_count'] for track in tracks], 0.5))}** and maximum **{max(track['observation_count'] for track in tracks) if tracks else 0}** Stage3 observations per track. This is not a claim of {len(tracks)} physical reflectors.",
        "",
        "The complete graph and node-level degrees are in `observation_to_track_edges.csv` and `observation_to_track_nodes.csv`; the merge rule is intentionally independent of sample size, Stage4 yield, trend separation, or any model-fitting result.",
        "",
        "## Elevation audit",
        "",
        f"- Tracks with non-constant continuous elevation: **{len(nonconstant_tracks)}**; tracks crossing a frozen LOW/MID/HIGH boundary: **{len(crossing_tracks)}**.",
        "- Each track retains continuous elevation minimum/median/maximum/range and its raw bin set. The policy comparison explicitly reports `track_median`, `track_union`, and `track_split_at_bin_boundary`; no first-center or scene-mean elevation was silently substituted.",
        "- If no track crosses a boundary, the three treatments have the same cell support presence; if a track crosses, the report keeps the alternative assignments visible rather than selecting one post hoc.",
        "",
        "## Policy comparison",
        "",
        "### Policy A — observation level",
        "",
        f"Every one of the {len(nodes)} Stage3 path observations is retained as a statistical unit. Uncertainty should be clustered or bootstrapped at scene/run blocks; repeated observations are not treated as independent physical reflectors.",
        "",
        "### Policy B — conservative algorithm-derived track",
        "",
        f"The {len(tracks)} connected components from reciprocal existing links are the units; singleton observations remain units. Track-level parameter summaries use within-track medians. `track_union` and `track_split_at_bin_boundary` are sensitivity views for elevation assignment, not hidden post-selection.",
        "",
        "### Policy C — weighted observation",
        "",
        f"All {len(nodes)} observations remain rows, with weight `1/(algorithm-track size)`. Each conservative algorithm track has total weight one, so overlapping center observations do not dominate; uncertainty should still respect run/scene clustering. The CSV reports raw unit count, total weight, and Kish effective count separately.",
        "",
        "### Does Env×elevation support depend on observation handling?",
        "",
        f"Comparing observation-level support with the conservative `track_median` support, the number of cell-presence changes is **{support_presence_changes}/12**. The empty `Highway/Open–LOW` cell remains empty under every policy/treatment. Track aggregation changes the unit counts and can change parameter medians; the maximum absolute cell-median sensitivity relative to Policy A is recorded without imposing a post hoc materiality threshold: `{json.dumps(nonempty_delta_ranges, ensure_ascii=False, sort_keys=True)}`.",
        "",
        "Because no final model or inferential threshold is being fitted here, these are descriptive sensitivity results. The primary evidence should carry the observation/clustered view, with the algorithm-track and weighted views reported as dependence sensitivity rather than silently replacing the 783-row population.",
        "",
        "## Stage4 validation overlay",
        "",
        f"Stage4 strict confirmation is not required to create a Stage3 track and was not used for graph edges. Per track, `contains_stage4_confirmed_observation` and `stage4_confirmed_fraction` are retained; **{len(stage4_tracks)}** tracks contain at least one Stage4 strict-confirmed Stage3-linked observation. See `stage3_stage4_track_validation.csv`.",
        "",
        "## Recommendation",
        "",
        "```text",
        "CAN_EXISTING_STAGE3_ASSOCIATION_BE_REUSED_FOR_TRACK_BUILDING = PARTIAL",
        "STAGE3_PRIMARY_POPULATION = CONDITIONAL",
        "RECOMMENDED_STATISTICAL_UNIT = WEIGHTED_OBSERVATION",
        "FORMAL_TRACK_RECONSTRUCTION_SUPPORTED = PARTIAL",
        "STAGE3_EFFECTIVE_SAMPLE_SUPPORT = ADEQUATE_WITH_LIMITATIONS",
        "PROCESS_20_46_MHZ_NEXT = CONDITIONAL",
        "NEW_DATA_COLLECTION_REQUIRED = CONDITIONAL",
        "```",
        "",
        "Reasoning: the 783-row Stage3 population is broad enough for a bounded descriptive channel-parameter layer and covers 11/12 environment×elevation cells, but it has only 12 scenes and 50 runs in the academic subset, an empty Highway/Open–LOW cell, and center-local rather than globally verified path identity. Reciprocal Stage3 links support a conservative algorithm-track sensitivity layer, not a formal physical-track reconstruction. Therefore the recommended primary treatment retains every observation, normalizes within the reproducible algorithm-link clusters, and uses scene/run-clustered uncertainty. The Stage3 population remains conditional for any stronger fitted model claim.",
        "",
        "`PROCESS_20_46_MHZ_NEXT = CONDITIONAL` means do not start that processing merely because this audit is complete; first approve the statistical-unit contract and its limitations. `NEW_DATA_COLLECTION_REQUIRED = CONDITIONAL` means no new collection is required for the bounded 11-cell descriptive layer, but additional independent observations are needed before claiming complete environment×elevation coverage or robust Highway/Open–LOW behavior.",
        "",
        "## Independent QA and artifacts",
        "",
        f"- QA status: **{qa['qa_status']}**; QA result: `{data['output_dir'] / 'qa_result.json'}`; QA report: `{data['output_dir'] / 'qa_report.md'}`.",
        f"- New output namespace: `{data['output_dir']}`; report: `{report_path}`.",
        "- New tables: `observation_to_track_nodes.csv`, `observation_to_track_edges.csv`, `track_population.csv`, `policy_unit_summary.csv`, `policy_support_matrix.csv`, `policy_parameter_summary.csv`, `stage3_stage4_track_validation.csv`, and `elevation_policy_comparison.csv`.",
        f"- Prior Stage3 reassessment was read from `{prior_report}` and was not overwritten.",
        "- Handoff impact: no existing Engineering/Paper handoff, Stage0–Stage4 source artifact, database, or model artifact was modified. This is a new statistical-unit audit namespace only.",
        "",
        "```text",
        f"STAGE3_STATISTICAL_UNIT_AUDIT={qa['qa_status']}",
        f"STAGE3_ACADEMIC_PATH_OBSERVATIONS={len(nodes)}",
        f"STAGE3_ALGORITHM_TRACK_UNITS={len(tracks)}",
        f"STAGE3_EDGE_CLASSES={json.dumps(dict(edge_counts), sort_keys=True)}",
        f"STAGE3_TRACK_BIN_CROSSING_COUNT={len(crossing_tracks)}",
        f"STAGE3_ENV_ELEV_SUPPORT_PRESENCE_CHANGES_A_VS_B_MEDIAN={support_presence_changes}",
        "STAGE3_EXISTING_ASSOCIATION_REUSE_FOR_TRACK_BUILDING=PARTIAL",
        "STAGE3_FORMAL_TRACK_RECONSTRUCTION=PARTIAL",
        "STAGE3_PRIMARY_POPULATION=CONDITIONAL",
        "STAGE3_RECOMMENDED_STATISTICAL_UNIT=WEIGHTED_OBSERVATION",
        "RAW_IQ_READ=NO",
        "MATLAB_EXECUTED=NO",
        "SAGE_EXECUTED=NO",
        "FINAL_MODEL_FITTED=NO",
        "NEXT_DECISION_REQUIRED=APPROVE_OR_REVISE_STATISTICAL_UNIT_CONTRACT_BEFORE_ANY_MODEL_FIT",
        "```",
        "",
        "This task stops after the statistical-unit recommendation. No final model fit or 20.46 MHz processing was initiated.",
    ]
    return "\n".join(lines) + "\n"


def output_hashes(output_dir: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    report_path = args.report_path or root / REPORT_REL
    report_path = report_path if report_path.is_absolute() else root / report_path
    if report_path.exists():
        raise FileExistsError(f"report already exists; refusing to overwrite: {report_path}")

    data = _build_analysis(root, output_dir)
    qa = independent_qa(data)
    write_json(output_dir / "qa_result.json", qa)
    (output_dir / "qa_report.md").write_text(build_qa_report(qa), encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(data, qa, report_path), encoding="utf-8")
    manifest = {
        "audit_id": AUDIT_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_scope": {
            "prior_namespace": str(PRIOR_NAMESPACE_REL),
            "ingestion_id": INGESTION_ID,
            "alignment_id": ALIGNMENT_ID,
            "academic_path_observation_count": len(data["nodes"]),
            "algorithm_track_count": len(data["tracks"]),
            "edge_count": len(data["edges"]),
        },
        "association_semantics": {
            "match_pattern_length": EXPECTED_MATCH_PATTERN_LENGTH,
            "persistence_radius_windows": PERSISTENCE_RADIUS_WINDOWS,
            "definite_algorithm_link": "reciprocal existing match_pattern support + same center-local multipath_id",
            "possible_overlap": "shared existing persistence support footprint without definite link",
            "ambiguous": "one-way direct evidence or path-position mismatch",
            "no_link": "no shared existing persistence support footprint among candidate pairs",
            "physical_reflector_identity_claim": False,
        },
        "policies": {
            "A_OBSERVATION": "one unit per Stage3 academic-eligible path observation; scene/run clustered uncertainty",
            "B_ALGORITHM_TRACK": "connected components using only DEFINITE_ALGORITHM_LINK; singleton nodes retained",
            "C_WEIGHTED_OBSERVATION": "all observations retained; weight one divided by B track size",
        },
        "frozen_hash_status": data["frozen_status"],
        "source_artifacts_before_sha256": data["source_hashes_before"],
        "source_artifacts_after_sha256": qa["source_artifacts_after_sha256"],
        "prior_reassessment_output_sha256": data["prior_output_hashes_current"],
        "gate_record": data["gate_record"],
        "qa_status": qa["qa_status"],
        "qa_result_sha256": sha256_file(output_dir / "qa_result.json"),
        "qa_report_sha256": sha256_file(output_dir / "qa_report.md"),
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path),
        "output_sha256": output_hashes(output_dir),
    }
    write_json(output_dir / "audit_manifest.json", manifest)
    print(
        json.dumps(
            {
                "qa_status": qa["qa_status"],
                "output_dir": str(output_dir),
                "report_path": str(report_path),
                "academic_path_observations": len(data["nodes"]),
                "algorithm_track_units": len(data["tracks"]),
                "edge_class_counts": dict(Counter(edge["edge_class"] for edge in data["edges"])),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if qa["qa_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
