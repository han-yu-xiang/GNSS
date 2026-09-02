"""Derive bounded Stage4 path parameters from the QA-passed alignment overlay.

This module deliberately derives descriptive path/event quantities only.  It does
not read raw IQ, re-run MATLAB/SAGE, fit a stochastic channel model, or infer
Ricean K-factor/path lifetime from fields that are absent or not uniquely defined
in the frozen Stage4 audit schema.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable


PARAMETER_SET_ID = "parameters_20260825_stage4_path_v1"
PARAMETER_VERSION = "stage4-confirmed-path-parameters-v1"
ALIGNMENT_ID = "alignment_20260825_tow_geometry_scene_v1"
ALIGNMENT_VERSION = "sage-event-context-alignment-v1"
SAMPLE_RATE_HZ = 10_230_000.0
CHIP_RATE_HZ = 1_023_000.0
SPEED_OF_LIGHT_MPS = 299_792_458.0

ALIGNMENT_REL = (
    "dataset/multipath_event_database/v1/partitions/"
    f"alignment_id={ALIGNMENT_ID}"
)
ENVIRONMENT_INPUT_REL = f"{ALIGNMENT_REL}/exports/confirmed_paths_environment_ready.csv"
ELEVATION_INPUT_REL = f"{ALIGNMENT_REL}/exports/confirmed_paths_elevation_ready.csv"
ALIGNMENT_MANIFEST_REL = f"{ALIGNMENT_REL}/alignment_manifest.json"
EVENT_ELIGIBILITY_REL = f"{ALIGNMENT_REL}/exports/modeling_event_eligibility.csv"

PATH_COLUMNS = [
    "parameter_set_id",
    "parameter_version",
    "event_path_id",
    "event_id",
    "run_id",
    "scene_id",
    "prn",
    "tracking_channel",
    "center_window_id",
    "path_id",
    "estimate_stage",
    "path_role",
    "is_multipath",
    "label_value",
    "event_utc",
    "environment_class",
    "special_condition",
    "road_type",
    "elevation_deg",
    "elevation_band",
    "azimuth_deg",
    "nmea_snr_db_hz",
    "geometry_join_valid",
    "geometry_time_delta_s",
    "environment_modeling_ready",
    "elevation_modeling_ready",
    "excess_delay_samples",
    "excess_delay_chips",
    "excess_delay_s",
    "excess_path_length_m",
    "doppler_offset_hz",
    "relative_doppler_hz",
    "relative_power_db",
    "source_power_field",
    "source_file",
    "source_file_sha256",
    "source_row_number",
    "parameter_source_status",
]

EVENT_COLUMNS = [
    "parameter_set_id",
    "parameter_version",
    "event_id",
    "run_id",
    "scene_id",
    "prn",
    "center_window_id",
    "event_utc",
    "environment_class",
    "special_condition",
    "road_type",
    "elevation_deg",
    "elevation_band",
    "environment_modeling_ready",
    "elevation_modeling_ready",
    "confirmed_path_count",
    "elevation_modeling_ready_path_count",
    "max_excess_delay_chips",
    "median_excess_delay_chips",
    "mean_excess_delay_chips",
    "max_excess_delay_s",
    "max_excess_path_length_m",
    "min_relative_doppler_hz",
    "max_relative_doppler_hz",
    "relative_doppler_span_hz",
    "median_relative_doppler_hz",
    "min_relative_power_db",
    "max_relative_power_db",
    "median_relative_power_db",
    "parameter_source_status",
]

SUMMARY_COLUMNS = [
    "parameter_set_id",
    "parameter_version",
    "group_dimension",
    "group_value",
    "path_count",
    "event_count",
    "scene_count",
    "elevation_ready_path_count",
    "median_excess_delay_chips",
    "min_excess_delay_chips",
    "max_excess_delay_chips",
    "median_excess_delay_s",
    "median_excess_path_length_m",
    "median_relative_doppler_hz",
    "min_relative_doppler_hz",
    "max_relative_doppler_hz",
    "median_relative_power_db",
    "min_relative_power_db",
    "max_relative_power_db",
    "summary_scope",
]

ISSUE_COLUMNS = [
    "severity",
    "issue_code",
    "event_path_id",
    "event_id",
    "scene_id",
    "prn",
    "detail",
    "action",
    "parameter_version",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float(value: Any, field: str, *, required: bool = True) -> float | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"missing numeric field: {field}")
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite numeric field: {field}={value}")
    return result


def _format(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


def _median(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        raise ValueError("cannot summarize an empty numeric series")
    return float(median(values))


def elevation_band(value: float | str | None) -> str | None:
    """Return the frozen LOW/MID/HIGH band with lower-inclusive boundaries."""

    if value in (None, ""):
        return None
    elevation = float(value)
    if not math.isfinite(elevation) or elevation < 0.0 or elevation > 90.0:
        raise ValueError(f"elevation outside [0, 90] degrees: {value}")
    if elevation < 30.0:
        return "LOW"
    if elevation < 60.0:
        return "MID"
    return "HIGH"


def derive_path_parameters(
    source: dict[str, str],
    *,
    sample_rate_hz: float = SAMPLE_RATE_HZ,
    chip_rate_hz: float = CHIP_RATE_HZ,
    speed_of_light_mps: float = SPEED_OF_LIGHT_MPS,
) -> dict[str, Any]:
    """Derive physical units from one Stage4-confirmed multipath path row."""

    if source.get("estimate_stage") not in (None, "", "stage4_joint"):
        raise ValueError("channel parameters require stage4_joint rows")
    if source.get("is_multipath") != "1":
        raise ValueError("channel parameters require is_multipath=1")
    if source.get("label_value") != "confirmed_multipath":
        raise ValueError("channel parameters require confirmed_multipath rows")

    excess_delay_samples = _float(source.get("excess_delay_samples"), "excess_delay_samples")
    source_excess_delay_chips = _float(
        source.get("excess_delay_chips"), "excess_delay_chips"
    )
    relative_doppler_hz = _float(source.get("doppler_offset_hz"), "doppler_offset_hz")
    relative_power_db = _float(source.get("relative_power_db"), "relative_power_db")
    elevation = _float(source.get("elevation_deg"), "elevation_deg", required=False)
    derived_excess_delay_chips = excess_delay_samples * chip_rate_hz / sample_rate_hz
    if abs(derived_excess_delay_chips - source_excess_delay_chips) > 1e-6:
        raise ValueError(
            "delay samples/chips are inconsistent: "
            f"{derived_excess_delay_chips} != {source_excess_delay_chips}"
        )
    geometry_valid = source.get("geometry_join_valid") == "1"
    elevation_ready = geometry_valid and elevation is not None
    excess_delay_s = excess_delay_samples / sample_rate_hz

    result: dict[str, Any] = {
        "parameter_set_id": PARAMETER_SET_ID,
        "parameter_version": PARAMETER_VERSION,
        "event_path_id": source.get("event_path_id", ""),
        "event_id": source.get("event_id", ""),
        "run_id": source.get("run_id", ""),
        "scene_id": source.get("scene_id", ""),
        "prn": source.get("prn", ""),
        "tracking_channel": source.get("tracking_channel", ""),
        "center_window_id": source.get("center_window_id", ""),
        "path_id": source.get("path_id", ""),
        "estimate_stage": source.get("estimate_stage", ""),
        "path_role": source.get("path_role", ""),
        "is_multipath": source.get("is_multipath", ""),
        "label_value": source.get("label_value", ""),
        "event_utc": source.get("event_utc", ""),
        "environment_class": source.get("environment_class", ""),
        "special_condition": source.get("special_condition", ""),
        "road_type": source.get("road_type", ""),
        "elevation_deg": elevation,
        "elevation_band": elevation_band(elevation),
        "azimuth_deg": _float(source.get("azimuth_deg"), "azimuth_deg", required=False),
        "nmea_snr_db_hz": _float(
            source.get("nmea_snr_db_hz"), "nmea_snr_db_hz", required=False
        ),
        "geometry_join_valid": source.get("geometry_join_valid", ""),
        "geometry_time_delta_s": _float(
            source.get("geometry_time_delta_s"), "geometry_time_delta_s", required=False
        ),
        "environment_modeling_ready": 1,
        "elevation_modeling_ready": 1 if elevation_ready else 0,
        "excess_delay_samples": excess_delay_samples,
        "excess_delay_chips": source_excess_delay_chips,
        "excess_delay_s": excess_delay_s,
        "excess_path_length_m": speed_of_light_mps * excess_delay_s,
        "doppler_offset_hz": relative_doppler_hz,
        "relative_doppler_hz": relative_doppler_hz,
        "relative_power_db": relative_power_db,
        "source_power_field": source.get("source_power_field", ""),
        "source_file": source.get("source_file", ""),
        "source_file_sha256": source.get("source_file_sha256", ""),
        "source_row_number": source.get("source_row_number", ""),
        "parameter_source_status": "complete",
    }
    return result


def aggregate_event_parameters(paths: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate confirmed paths within one event using descriptive statistics."""

    if not paths:
        raise ValueError("cannot aggregate an empty event")
    event_ids = {row["event_id"] for row in paths}
    if len(event_ids) != 1:
        raise ValueError(f"event aggregation received multiple event IDs: {event_ids}")
    first = paths[0]
    delays = [float(row["excess_delay_chips"]) for row in paths]
    delays_s = [float(row["excess_delay_s"]) for row in paths]
    lengths = [float(row["excess_path_length_m"]) for row in paths]
    dopplers = [float(row["relative_doppler_hz"]) for row in paths]
    powers = [float(row["relative_power_db"]) for row in paths]
    elevations = [row["elevation_deg"] for row in paths if row.get("elevation_deg") is not None]
    bands = {row.get("elevation_band") for row in paths if row.get("elevation_band")}
    return {
        "parameter_set_id": PARAMETER_SET_ID,
        "parameter_version": PARAMETER_VERSION,
        "event_id": first["event_id"],
        "run_id": first.get("run_id", ""),
        "scene_id": first.get("scene_id", ""),
        "prn": first.get("prn", ""),
        "center_window_id": first.get("center_window_id", ""),
        "event_utc": first.get("event_utc", ""),
        "environment_class": first.get("environment_class", ""),
        "special_condition": first.get("special_condition", ""),
        "road_type": first.get("road_type", ""),
        "elevation_deg": elevations[0] if elevations else None,
        "elevation_band": next(iter(bands)) if len(bands) == 1 else None,
        "environment_modeling_ready": 1,
        "elevation_modeling_ready": 1
        if all(int(row.get("elevation_modeling_ready", 0)) == 1 for row in paths)
        else 0,
        "confirmed_path_count": len(paths),
        "elevation_modeling_ready_path_count": sum(
            int(row.get("elevation_modeling_ready", 0)) for row in paths
        ),
        "max_excess_delay_chips": max(delays),
        "median_excess_delay_chips": _median(delays),
        "mean_excess_delay_chips": sum(delays) / len(delays),
        "max_excess_delay_s": max(delays_s),
        "max_excess_path_length_m": max(lengths),
        "min_relative_doppler_hz": min(dopplers),
        "max_relative_doppler_hz": max(dopplers),
        "relative_doppler_span_hz": max(dopplers) - min(dopplers),
        "median_relative_doppler_hz": _median(dopplers),
        "min_relative_power_db": min(powers),
        "max_relative_power_db": max(powers),
        "median_relative_power_db": _median(powers),
        "parameter_source_status": "complete",
    }


def summarize_parameter_group(
    group_dimension: str, group_value: str, paths: list[dict[str, Any]]
) -> dict[str, Any]:
    """Summarize a path population without fitting a statistical distribution."""

    if not paths:
        raise ValueError("cannot summarize an empty path population")
    delays = [float(row["excess_delay_chips"]) for row in paths]
    delays_s = [float(row["excess_delay_s"]) for row in paths]
    lengths = [float(row["excess_path_length_m"]) for row in paths]
    dopplers = [float(row["relative_doppler_hz"]) for row in paths]
    powers = [float(row["relative_power_db"]) for row in paths]
    return {
        "parameter_set_id": PARAMETER_SET_ID,
        "parameter_version": PARAMETER_VERSION,
        "group_dimension": group_dimension,
        "group_value": group_value,
        "path_count": len(paths),
        "event_count": len({row["event_id"] for row in paths}),
        "scene_count": len({row["scene_id"] for row in paths}),
        "elevation_ready_path_count": sum(
            int(row.get("elevation_modeling_ready", 0)) for row in paths
        ),
        "median_excess_delay_chips": _median(delays),
        "min_excess_delay_chips": min(delays),
        "max_excess_delay_chips": max(delays),
        "median_excess_delay_s": _median(delays_s),
        "median_excess_path_length_m": _median(lengths),
        "median_relative_doppler_hz": _median(dopplers),
        "min_relative_doppler_hz": min(dopplers),
        "max_relative_doppler_hz": max(dopplers),
        "median_relative_power_db": _median(powers),
        "min_relative_power_db": min(powers),
        "max_relative_power_db": max(powers),
        "summary_scope": "descriptive_confirmed_stage4_paths_only",
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _format(row.get(field)) for field in fieldnames})


def _source_hashes(root: Path, alignment_manifest: dict[str, Any]) -> dict[str, str]:
    return {
        "alignment_manifest_sha256": sha256_file(root / ALIGNMENT_MANIFEST_REL),
        "environment_input_sha256": sha256_file(root / ENVIRONMENT_INPUT_REL),
        "elevation_input_sha256": sha256_file(root / ELEVATION_INPUT_REL),
        "modeling_event_eligibility_sha256": sha256_file(
            root / EVENT_ELIGIBILITY_REL
        ),
        "source_ingestion_manifest_sha256": alignment_manifest["source_hashes"][
            "source_ingestion_manifest_sha256"
        ],
        "pipeline_sha256": alignment_manifest["source_hashes"]["pipeline_sha256"],
        "wrapper_sha256": alignment_manifest["source_hashes"]["wrapper_sha256"],
        "executor_sha256": alignment_manifest["source_hashes"]["executor_sha256"],
        "production_manifest_sha256": alignment_manifest["source_hashes"][
            "production_manifest_sha256"
        ],
        "inventory_sha256": alignment_manifest["source_hashes"]["inventory_sha256"],
    }


def build_parameter_derivation(root: Path) -> Path:
    root = root.resolve()
    final_root = root / "dataset/multipath_event_database/v1/partitions" / (
        f"parameter_set_id={PARAMETER_SET_ID}"
    )
    if final_root.exists():
        raise FileExistsError(f"parameter namespace already exists: {final_root}")

    alignment_manifest_path = root / ALIGNMENT_MANIFEST_REL
    alignment_manifest = json.loads(alignment_manifest_path.read_text(encoding="utf-8"))
    if alignment_manifest.get("independent_qa_status") != "PASS":
        raise RuntimeError("alignment overlay is not independently QA-passed")

    environment_rows = read_csv_rows(root / ENVIRONMENT_INPUT_REL)
    elevation_rows = read_csv_rows(root / ELEVATION_INPUT_REL)
    if len({row["event_path_id"] for row in environment_rows}) != len(environment_rows):
        raise ValueError("environment input contains duplicate event_path_id")
    elevation_ids = {row["event_path_id"] for row in elevation_rows}
    environment_ids = {row["event_path_id"] for row in environment_rows}
    if not elevation_ids.issubset(environment_ids):
        raise ValueError("elevation input contains paths outside environment input")

    derived_paths: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for source in environment_rows:
        derived = derive_path_parameters(source)
        derived["elevation_modeling_ready"] = 1 if source["event_path_id"] in elevation_ids else 0
        derived_paths.append(derived)
        if derived["elevation_modeling_ready"] == 0:
            issues.append(
                {
                    "severity": "warning",
                    "issue_code": "elevation_context_unavailable",
                    "event_path_id": source.get("event_path_id", ""),
                    "event_id": source.get("event_id", ""),
                    "scene_id": source.get("scene_id", ""),
                    "prn": source.get("prn", ""),
                    "detail": source.get("missing_reason")
                    or f"geometry_join_status={source.get('geometry_join_status', '')}",
                    "action": "retain_environment_parameter_exclude_elevation_summary",
                    "parameter_version": PARAMETER_VERSION,
                }
            )

    paths_by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in derived_paths:
        paths_by_event[path["event_id"]].append(path)
    event_rows = [
        aggregate_event_parameters(paths_by_event[event_id])
        for event_id in sorted(paths_by_event)
    ]

    summary_rows: list[dict[str, Any]] = []
    by_environment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in derived_paths:
        by_environment[path["environment_class"]].append(path)
    for value in sorted(by_environment):
        summary_rows.append(
            summarize_parameter_group("environment_class", value, by_environment[value])
        )

    by_elevation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in derived_paths:
        if path["elevation_modeling_ready"] == 1 and path["elevation_band"]:
            by_elevation[path["elevation_band"]].append(path)
    for value in ("LOW", "MID", "HIGH"):
        if value in by_elevation:
            summary_rows.append(
                summarize_parameter_group("elevation_band", value, by_elevation[value])
            )

    table_rows: dict[str, tuple[list[str], list[dict[str, Any]]]] = {
        "facts/path_parameters.csv": (PATH_COLUMNS, derived_paths),
        "facts/event_parameters.csv": (EVENT_COLUMNS, event_rows),
        "summaries/parameter_summary.csv": (SUMMARY_COLUMNS, summary_rows),
        "qa/derivation_issues.csv": (ISSUE_COLUMNS, issues),
    }

    parent = final_root.parent
    with tempfile.TemporaryDirectory(
        dir=parent, prefix=f".{PARAMETER_SET_ID}.staging-"
    ) as staging_text:
        staging = Path(staging_text)
        for relative, (columns, rows) in table_rows.items():
            _write_csv(staging / relative, columns, rows)

        table_hashes = {
            relative: sha256_file(staging / relative)
            for relative in sorted(table_rows)
        }
        environment_ready_count = len(derived_paths)
        elevation_ready_count = sum(
            int(row["elevation_modeling_ready"]) for row in derived_paths
        )
        report = f"""# Stage4 path-parameter derivation — 2026-08-25

## Status

`CHANNEL_PARAMETER_DERIVATION = COMPLETED_WITH_EXCLUSIONS`

This versioned derivation reads only the independently QA-passed modeling-context
alignment overlay. It does not read raw IQ or Stage4 MAT payloads, and it does
not run MATLAB, SAGE, batch execution, or a stochastic channel-model fit.

## Derived quantities

- Path-level excess delay in seconds: `excess_delay_samples / 10230000`.
- Path-level excess path length in meters: `excess_delay_s * 299792458`.
- Signed relative Doppler: copied from the Stage4 `doppler_offset_hz` field.
- Relative power: copied from the Stage4 `mean_relative_power_db` source field.
- Event and group tables contain descriptive counts, medians, minima and maxima
  only; no fitted distribution is produced.
- Elevation bands use lower-inclusive intervals: LOW `[0,30)`, MID `[30,60)`,
  HIGH `[60,90]` degrees.

## Counts

- Environment-ready confirmed paths: {environment_ready_count}.
- Elevation-ready confirmed paths: {elevation_ready_count}.
- Confirmed events represented by the environment-ready paths: {len(event_rows)}.
- Environment groups: {len(by_environment)}; elevation groups: {len(by_elevation)}.
- Explicit elevation exclusions: {len(issues)} paths retained for environment
  summaries but excluded from elevation-group summaries.

## Deliberately not derived

`RMS_DELAY_SPREAD`, `DOPPLER_SPREAD`, `RICEAN_K_FACTOR`, and `PATH_LIFETIME`
remain `NOT_DERIVED` in this version because the current frozen audit schema does
not provide a validated complete power/phase path set, a temporal path identity,
or a separately approved statistical definition for those quantities.

## Provenance and execution record

- Source alignment partition: `{ALIGNMENT_REL}/`.
- Alignment QA status required: `PASS`.
- Raw IQ read: no.
- MATLAB/SAGE/batch started: no.
- Existing SAGE artifacts, requests, manifest, inventory and alignment tables
  modified: no.
- Statistical channel modeling started: no.
"""
        (staging / "derivation_report.md").write_text(report, encoding="utf-8")
        manifest = {
            "parameter_set_id": PARAMETER_SET_ID,
            "parameter_version": PARAMETER_VERSION,
            "created_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "source_alignment_partition": ALIGNMENT_REL,
            "source_hashes": _source_hashes(root, alignment_manifest),
            "derivation_rules": {
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "chip_rate_hz": CHIP_RATE_HZ,
                "speed_of_light_mps": SPEED_OF_LIGHT_MPS,
                "delay_seconds": "excess_delay_samples / sample_rate_hz",
                "relative_doppler_field": "doppler_offset_hz",
                "relative_power_source_field": "mean_relative_power_db",
                "group_statistics": "descriptive_median_min_max_no_fit",
                "elevation_bands": {
                    "LOW": "[0,30)",
                    "MID": "[30,60)",
                    "HIGH": "[60,90]",
                },
            },
            "derived_parameters": [
                "excess_delay_s",
                "excess_path_length_m",
                "relative_doppler_hz",
                "relative_power_db",
                "confirmed_path_count",
                "descriptive_group_medians_and_ranges",
            ],
            "not_derived_parameters": [
                "rms_delay_spread",
                "doppler_spread",
                "ricean_k_factor",
                "path_lifetime",
                "fitted_distribution_family",
            ],
            "table_counts": {
                relative: len(rows) for relative, (_, rows) in table_rows.items()
            },
            "table_sha256": table_hashes,
            "result_counts": {
                "environment_ready_confirmed_path_count": environment_ready_count,
                "elevation_ready_confirmed_path_count": elevation_ready_count,
                "confirmed_event_count": len(event_rows),
                "environment_group_count": len(by_environment),
                "elevation_group_count": len(by_elevation),
                "elevation_exclusion_count": len(issues),
            },
            "gate_record": {
                "raw_iq_read": False,
                "matlab_started": False,
                "sage_started": False,
                "batch_started": False,
                "existing_sage_artifacts_modified": False,
                "statistical_modeling_started": False,
                "channel_parameter_derivation_started": True,
            },
            "status": "completed_with_exclusions",
            "independent_qa_status": "PENDING",
        }
        (staging / "parameter_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        staging.rename(final_root)
    return final_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    output = build_parameter_derivation(args.project_root)
    print(f"PARAMETER_DERIVATION_RESULT=completed_with_exclusions|path={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
