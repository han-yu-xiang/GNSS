from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OUTPUT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = (
    Path(r"E:\GNSS_Multipath_Project")
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/"
    "population/gmm_feature_population.csv"
)
SOURCE_MANIFEST = SOURCE_CSV.with_name("gmm_feature_population_manifest.json")
SOURCE_QA = (
    SOURCE_CSV.parents[1]
    / "qa/independent_qa_report.md"
)

ENVIRONMENTS = ("Urban", "Mountain/Valley")
ELEVATION_BANDS = ("LOW", "MID", "HIGH")
MODELING_FIELDS = (
    "excess_delay_samples",
    "absolute_doppler_hz",
    "relative_power_db",
)
SIGNED_DOPPLER_FIELD = "doppler_offset_hz"
WEIGHT_FIELD = "track_weight_recomputed_primary"
EXPECTED_CELL_COUNTS = {
    "Urban/LOW": 18,
    "Urban/MID": 169,
    "Urban/HIGH": 129,
    "Mountain/Valley/LOW": 22,
    "Mountain/Valley/MID": 117,
    "Mountain/Valley/HIGH": 32,
}


def _bool_mask(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1"})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_primary_population(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {
        "primary_population_included",
        "elevation_ready",
        "cell_ready",
        "environment_class",
        "elevation_band",
        "track_id",
        WEIGHT_FIELD,
        *MODELING_FIELDS,
        SIGNED_DOPPLER_FIELD,
        "scene_id",
        "run_id",
        "center_window_id",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"missing required fields: {missing}")
    return frame[_bool_mask(frame["primary_population_included"])].copy()


def audit_population(
    frame: pd.DataFrame,
    *,
    enforce_expected_counts: bool = True,
) -> dict[str, Any]:
    required = {
        "elevation_ready",
        "cell_ready",
        "environment_class",
        "elevation_band",
        "track_id",
        WEIGHT_FIELD,
        *MODELING_FIELDS,
        SIGNED_DOPPLER_FIELD,
        "scene_id",
        "run_id",
        "center_window_id",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"missing required fields: {missing}")

    numeric_fields = [*MODELING_FIELDS, SIGNED_DOPPLER_FIELD, WEIGHT_FIELD]
    numeric = frame[numeric_fields].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("non-finite modeling or weight value")
    if (numeric[WEIGHT_FIELD] <= 0).any():
        raise ValueError("track weights must be positive")
    if frame["track_id"].isna().any():
        raise ValueError("track_id contains missing values")

    env_values = set(frame["environment_class"].dropna().astype(str))
    if not env_values.issubset(set(ENVIRONMENTS)):
        raise ValueError(f"unexpected environment classes: {sorted(env_values)}")
    band_values = set(frame["elevation_band"].dropna().astype(str))
    if not band_values.issubset(set(ELEVATION_BANDS)):
        raise ValueError(f"unexpected elevation bands: {sorted(band_values)}")

    track_sums = (
        numeric.assign(track_id=frame["track_id"].to_numpy())
        .groupby("track_id")[WEIGHT_FIELD]
        .sum()
    )
    max_track_sum_error = float(np.max(np.abs(track_sums.to_numpy() - 1.0)))
    if max_track_sum_error > 1e-9:
        raise ValueError(
            f"track weights do not sum to one; maximum error={max_track_sum_error}"
        )

    elevation_ready = _bool_mask(frame["elevation_ready"])
    cell_ready = _bool_mask(frame["cell_ready"])
    cell_frame = frame[elevation_ready & cell_ready].copy()
    cell_frame["cell_id"] = (
        cell_frame["environment_class"].astype(str)
        + "/"
        + cell_frame["elevation_band"].astype(str)
    )
    cell_counts = {
        str(key): int(value)
        for key, value in cell_frame["cell_id"].value_counts().sort_index().items()
    }
    if enforce_expected_counts and cell_counts != EXPECTED_CELL_COUNTS:
        raise ValueError(
            f"cell counts changed: expected={EXPECTED_CELL_COUNTS}, actual={cell_counts}"
        )

    scene_counts = {
        str(key): int(value)
        for key, value in (
            cell_frame.groupby("cell_id")["scene_id"].nunique().sort_index()
        ).items()
    }
    if enforce_expected_counts and any(value < 2 for value in scene_counts.values()):
        raise ValueError(f"a cell has fewer than two scenes: {scene_counts}")

    environment_groups = frame.groupby(["run_id", "center_window_id"]).ngroups
    elevation_groups = cell_frame.groupby(["run_id", "center_window_id"]).ngroups

    return {
        "row_counts": {
            "primary_population_rows": int(len(frame)),
            "elevation_ready_rows": int(elevation_ready.sum()),
            "cell_ready_rows": int(len(cell_frame)),
            "missing_elevation_rows": int((~elevation_ready).sum()),
        },
        "environment_counts": {
            str(key): int(value)
            for key, value in frame["environment_class"].value_counts().sort_index().items()
        },
        "cell_counts": cell_counts,
        "cell_scene_counts": scene_counts,
        "track_counts": {
            "unique_tracks": int(frame["track_id"].nunique()),
            "max_weight_sum_error": max_track_sum_error,
        },
        "run_window_group_counts": {
            "environment_only": int(environment_groups),
            "elevation_ready": int(elevation_groups),
        },
        "fields": {
            "delay": {
                "field": "excess_delay_samples",
                "unit": "samples relative to the direct-path reference",
            },
            "doppler_primary": {
                "field": "absolute_doppler_hz",
                "unit": "Hz, absolute relative Doppler",
            },
            "doppler_signed": {
                "field": SIGNED_DOPPLER_FIELD,
                "unit": "Hz, signed relative Doppler",
            },
            "power": {
                "field": "relative_power_db",
                "unit": "dB relative to the direct-path reference",
            },
            "weight": {
                "field": WEIGHT_FIELD,
                "unit": "track-balanced analysis weight",
            },
        },
        "scope": {
            "environments": list(ENVIRONMENTS),
            "elevation_bands": list(ELEVATION_BANDS),
            "observation_semantics": "retained or persistent path observations",
            "not_full_channel_cir": True,
            "stage4_not_used": True,
            "dmc_not_used": True,
        },
    }


def _write_report(result: dict[str, Any], path: Path) -> None:
    rows = result["row_counts"]
    lines = [
        "# Path-Level Modeling Input Audit",
        "",
        "This audit records the read-only population contract for the isolated path-level modeling review.",
        "The rows are retained or persistent path observations, not a complete CIR or a set of confirmed physical paths.",
        "",
        "## Counts",
        "",
        f"- Primary population rows: {rows['primary_population_rows']}",
        f"- Elevation-ready rows: {rows['elevation_ready_rows']}",
        f"- Cell-ready rows: {rows['cell_ready_rows']}",
        f"- Missing-elevation rows excluded from cell models: {rows['missing_elevation_rows']}",
        f"- Unique tracks: {result['track_counts']['unique_tracks']}",
        f"- Environment-only run-window groups: {result['run_window_group_counts']['environment_only']}",
        f"- Elevation-ready run-window groups: {result['run_window_group_counts']['elevation_ready']}",
        "",
        "## Environment-Elevation Counts",
        "",
        "| Cell | Rows | Source scenes |",
        "|---|---:|---:|",
    ]
    for cell, count in result["cell_counts"].items():
        lines.append(f"| {cell} | {count} | {result['cell_scene_counts'][cell]} |")
    lines += [
        "",
        "## Modeling Fields",
        "",
        "| Quantity | Field | Unit |",
        "|---|---|---|",
    ]
    for name, spec in result["fields"].items():
        lines.append(f"| {name} | `{spec['field']}` | {spec['unit']} |")
    lines += [
        "",
        "## Boundary",
        "",
        "The current review can fit path-level delay-Doppler and path-relative-power distributions and derive a retained-path delay-dispersion ECDF.",
        "It does not contain the full per-snapshot CIR needed for a complete PDP, received fading-envelope fit, full-channel RMS delay spread, or snapshot-lag correlation.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    frame = load_primary_population(SOURCE_CSV)
    result = audit_population(frame)
    result["source"] = {
        "population_csv": str(SOURCE_CSV),
        "population_csv_sha256": sha256_file(SOURCE_CSV),
        "population_manifest": str(SOURCE_MANIFEST),
        "population_manifest_sha256": sha256_file(SOURCE_MANIFEST),
        "independent_qa_report": str(SOURCE_QA),
        "independent_qa_report_sha256": sha256_file(SOURCE_QA),
    }
    qa_dir = OUTPUT_ROOT / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    (qa_dir / "input_audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_report(result, qa_dir / "input_audit_report.md")


if __name__ == "__main__":
    main()
