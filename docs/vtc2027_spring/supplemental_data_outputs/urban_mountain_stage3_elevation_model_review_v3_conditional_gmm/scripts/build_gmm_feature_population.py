#!/usr/bin/env python3
"""Build the transformed feature population for the conditional GMM review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ENVIRONMENTS = ("Urban", "Mountain/Valley")
BANDS = ("LOW", "MID", "HIGH")
PRIMARY_ROWS = 518
CELL_READY_ROWS = 487
MISSING_ELEVATION_ROWS = 31


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def transform_row(raw: Mapping[str, str]) -> dict[str, Any]:
    environment = raw["environment_class"]
    if environment not in ENVIRONMENTS:
        raise ValueError(f"unexpected environment: {environment}")
    elevation_ready = raw.get("elevation_ready") == "1"
    elevation_band = raw.get("elevation_band", "") if elevation_ready else ""
    if elevation_ready and elevation_band not in BANDS:
        raise ValueError(f"unexpected elevation band: {elevation_band}")
    delay = float(raw["excess_delay_samples"])
    signed_doppler = float(raw["doppler_offset_hz"])
    power = float(raw["relative_power_db"])
    weight = float(raw["track_weight_recomputed_primary"])
    if not all(math.isfinite(value) for value in (delay, signed_doppler, power, weight)):
        raise ValueError(f"non-finite source value: {raw['stage3_path_id']}")
    if delay <= 0.0 or weight <= 0.0:
        raise ValueError(f"invalid positive source value: {raw['stage3_path_id']}")
    absolute_doppler = abs(signed_doppler)
    return {
        **dict(raw),
        "absolute_doppler_hz": absolute_doppler,
        "log_excess_delay": math.log(delay),
        "log1p_absolute_doppler": math.log1p(absolute_doppler),
        "cell_id": f"{environment}__{elevation_band}" if elevation_ready else "",
        "cell_ready": "1" if elevation_ready else "0",
        "parent_scope_role": "CELL_AND_ENVIRONMENT" if elevation_ready else "ENVIRONMENT_PARENT_ONLY",
    }


def weighted_neff(weights: Sequence[float]) -> float:
    total = float(sum(weights))
    return total * total / float(sum(weight * weight for weight in weights))


def build_cell_support(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for environment in ENVIRONMENTS:
        for band in BANDS:
            scoped = [row for row in rows if row.get("cell_id") == f"{environment}__{band}"]
            weights = [float(row["track_weight_recomputed_primary"]) for row in scoped]
            observation_count = len(scoped)
            track_count = len({row["track_id"] for row in scoped})
            scene_count = len({row["scene_id"] for row in scoped})
            status = "STRONGLY_PARTIALLY_POOLED" if observation_count < 50 or scene_count < 3 else "DATA_SUPPORTED"
            output.append(
                {
                    "environment_class": environment,
                    "elevation_band": band,
                    "cell_id": f"{environment}__{band}",
                    "observation_count": observation_count,
                    "track_count": track_count,
                    "run_count": len({row["run_id"] for row in scoped}),
                    "scene_count": scene_count,
                    "sum_weights": sum(weights),
                    "kish_effective_sample_size": weighted_neff(weights),
                    "support_status": status,
                }
            )
    return output


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    output_root = args.output_root.resolve()
    source_path = project_root / "docs/vtc2027_spring/supplemental_data_outputs/urban_mountain_stage3_elevation_model_review_v2_doppler_audit/population/population_primary_admitted.csv"
    decision_path = output_root / "diagnostics/doppler_transform_decision.json"
    feature_path = output_root / "population/gmm_feature_population.csv"
    support_path = output_root / "population/gmm_cell_support.csv"
    manifest_path = output_root / "population/gmm_feature_population_manifest.json"
    existing = [path for path in (feature_path, support_path, manifest_path) if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError("feature output exists; rerun with --overwrite")
    if not source_path.is_file() or not decision_path.is_file():
        raise FileNotFoundError("v2 primary population or Task-2 transform decision is missing")
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if decision.get("primary_model_variable") != "absolute_relative_doppler_magnitude_hz":
        raise ValueError("Task-2 primary Doppler transform decision is not absolute magnitude")
    raw_rows = read_csv(source_path)
    if len(raw_rows) != PRIMARY_ROWS:
        raise ValueError(f"expected {PRIMARY_ROWS} source rows, got {len(raw_rows)}")
    rows = [transform_row(raw) for raw in raw_rows]
    if sum(row["cell_ready"] == "1" for row in rows) != CELL_READY_ROWS:
        raise ValueError("cell-ready denominator changed")
    if sum(row["cell_ready"] == "0" for row in rows) != MISSING_ELEVATION_ROWS:
        raise ValueError("missing-elevation denominator changed")
    by_track: dict[str, float] = {}
    for row in rows:
        by_track[row["track_id"]] = by_track.get(row["track_id"], 0.0) + float(row["track_weight_recomputed_primary"])
    if any(abs(total - 1.0) > 1e-10 for total in by_track.values()):
        raise ValueError("recomputed primary track weights do not sum to one")
    source_fields = list(raw_rows[0].keys())
    added_fields = ["absolute_doppler_hz", "log_excess_delay", "log1p_absolute_doppler", "cell_id", "cell_ready", "parent_scope_role"]
    write_csv(feature_path, rows, source_fields + added_fields)
    support_rows = build_cell_support(rows)
    write_csv(support_path, support_rows, list(support_rows[0].keys()))
    manifest = {
        "population_id": "vtc_stage3_urban_mountain_gmm_feature_population_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source_path),
        "source_sha256": sha256_file(source_path),
        "transform_decision_sha256": sha256_file(decision_path),
        "counts": {"primary_rows": len(rows), "cell_ready_rows": sum(row["cell_ready"] == "1" for row in rows), "missing_elevation_rows": sum(row["cell_ready"] == "0" for row in rows), "track_count": len(by_track), "cell_count": len(support_rows)},
        "doppler_transform": "absolute_doppler_hz=abs(doppler_offset_hz); log1p_absolute_doppler=log1p(absolute_doppler_hz)",
        "delay_transform": "log_excess_delay=log(excess_delay_samples)",
        "missing_elevation_policy": "retain_for_environment_parent_only; exclude_from_LOW_MID_HIGH_cells; no_imputation",
        "execution_boundary": {"raw_iq_read": False, "matlab_started": False, "sage_started": False, "batch_started": False, "stage4_source_used": False, "formal_manuscript_modified": False, "v1_modified": False, "v2_modified": False, "evidence_matrix_modified": False, "handoff_modified": False},
        "outputs": {"gmm_feature_population.csv": sha256_file(feature_path), "gmm_cell_support.csv": sha256_file(support_path)},
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
