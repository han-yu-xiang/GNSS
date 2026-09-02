"""Freeze the source identities, windows, grids, and gates for VTC validation.

This script is intentionally independent of MATLAB and the production wrapper.
It reads existing metadata/Stage artifacts and writes one immutable contract.
It does not read signal samples; raw files are hashed in chunks only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "docs" / "vtc2027_spring" / "evidence" / "validation_v1" / "validation_contract.json"
PIPELINE = ROOT / "scripts" / "sage_pipeline" / "run_nav_sage_pipeline.m"
METADATA_CSV = ROOT / "dataset_generation_logs" / "production_planning_10mhz_20260812" / "scene_metadata_10MHz.csv"
PYTHON_ENTRYPOINTS = [
    ROOT / "scripts" / "analysis" / "vtc_validation" / "run_layer1_controlled_recovery.py",
    ROOT / "scripts" / "analysis" / "vtc_validation" / "run_layer2_multipath_stress.py",
    ROOT / "scripts" / "analysis" / "vtc_validation" / "export_layer3_native_model_support.py",
    ROOT / "scripts" / "analysis" / "vtc_validation" / "run_dll_code_bias_study.py",
]
PYTHON_MODULES = [
    ROOT / "scripts" / "analysis" / "vtc_validation" / "vtc_validation_common.py",
    ROOT / "scripts" / "analysis" / "vtc_validation" / "mat_v5_reader.py",
]

SCENES = {
    "G18": {
        "scene_id": "F1023_V70_D0120_P1",
        "prn_label": "G18",
        "prn": 18,
        "channel": 2,
        "environment": "Urban",
    },
    "G25": {
        "scene_id": "F1023_V80_D0117_P8",
        "prn_label": "G25",
        "prn": 25,
        "channel": 10,
        "environment": "Highway/Open",
    },
    "G05": {
        "scene_id": "F1023_V70_D0120_P9",
        "prn_label": "G05",
        "prn": 5,
        "channel": 10,
        "environment": "Special Reflective",
    },
}

LAYER2_EVENTS = [
    ("G25", 985),
    ("G25", 970),
    ("G05", 493),
    ("G05", 495),
]


def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"Missing JSON source: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        fail(f"Missing CSV source: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    if not path.is_file():
        fail(f"Cannot hash missing source: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def source_record(path: Path, role: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "role": role,
        "path": str(path),
        "bytes": stat.st_size,
        "sha256": sha256_file(path),
    }


def first_three_g18_zero_centers(summary_rows: list[dict[str, str]]) -> list[int]:
    rows = [
        row
        for row in summary_rows
        if row.get("joint_valid", "").strip().lower() in {"1", "true"}
        and int(float(row["joint_multipath_count"])) == 0
    ]
    rows.sort(key=lambda row: float(row["recording_time_s"]))
    if len(rows) < 3:
        fail(f"G18 has only {len(rows)} valid zero-event rows; three are required")
    return [int(float(row["center_window_id"])) for row in rows[:3]]


def event_path_rows(path_rows: list[dict[str, str]], center_id: int) -> list[dict[str, str]]:
    return [
        row for row in path_rows
        if int(float(row["center_window_id"])) == center_id
    ]


def event_is_confirmed(summary_rows: list[dict[str, str]], path_rows: list[dict[str, str]], center_id: int) -> bool:
    summaries = [
        row for row in summary_rows
        if int(float(row["center_window_id"])) == center_id
    ]
    paths = event_path_rows(path_rows, center_id)
    return any(
        row.get("joint_valid", "").strip().lower() in {"1", "true"}
        and int(float(row["joint_multipath_count"])) > 0
        and path.get("is_multipath", "").strip().lower() in {"1", "true"}
        for row in summaries
        for path in paths
    )


def five_snapshot_rows(symbol_rows: list[dict[str, str]], center_id: int) -> list[dict[str, Any]]:
    # Stage4 uses the Stage0 window row's symbol_index as a one-based catalog row.
    # The five joint snapshots are center-2:center+2 in that symbol catalog.
    by_symbol_id = {int(float(row["symbol_id"])): row for row in symbol_rows}
    center_row = by_symbol_id.get(center_id)
    if center_row is None:
        fail(f"No symbol row aligned with Stage0 window id {center_id}")
    center_symbol = int(float(center_row["symbol_id"]))
    selected: list[dict[str, Any]] = []
    for symbol_id in range(center_symbol - 2, center_symbol + 3):
        row = by_symbol_id.get(symbol_id)
        if row is None:
            fail(f"Missing five-snapshot symbol row {symbol_id} for center {center_id}")
        if row.get("continuous_to_next", "").strip().lower() not in {"1", "true"} and symbol_id < center_symbol + 2:
            fail(f"Non-contiguous symbol sequence around center {center_id}")
        selected.append({
            "symbol_id": symbol_id,
            "sample_start_zero_based": int(float(row["sample_start_zero_based"])),
            "recording_time_s": float(row["recording_time_s"]),
            "tow_s": float(row["tow_s"]),
            "nav_symbol": int(float(row["nav_symbol"])),
            "tracking_doppler_hz": float(row["tracking_doppler_hz"]),
            "code_frequency_hz": float(row["code_frequency_hz"]),
        })
    return selected


def scene_paths(scene_key: str) -> dict[str, Path]:
    spec = SCENES[scene_key]
    scene = ROOT / "scenes" / spec["scene_id"]
    output = scene / "sage_results" / "nav_sage_v2" / spec["prn_label"]
    config = scene / "gnss_sdr" / "config" / f"{spec['scene_id']}.conf"
    context_path = output / "run_context.json"
    context = read_json(context_path)
    raw_path = Path(context["rawFile"])
    return {
        "scene": scene,
        "output": output,
        "context": context_path,
        "raw": raw_path,
        "config": config,
        "stage0_windows": output / "stage0_valid_40ms_windows.csv",
        "stage0_symbols": output / "stage0_valid_symbols.csv",
        "stage4_summary": output / "stage4_joint_summary.csv",
        "stage4_paths": output / "stage4_joint_paths.csv",
        "stage4_mat": output / "stage4_nav_joint_100ms.mat",
        "tracking": Path(context["trackingFile"]),
        "telemetry": Path(context["telemetryFile"]),
    }


def make_case(scene_key: str, center_id: int | None = None, must_confirm: bool = False) -> dict[str, Any]:
    spec = SCENES[scene_key]
    paths = scene_paths(scene_key)
    summary = read_csv(paths["stage4_summary"])
    path_rows = read_csv(paths["stage4_paths"])
    symbols = read_csv(paths["stage0_symbols"])
    event: dict[str, Any] = {
        "scene_id": spec["scene_id"],
        "prn_label": spec["prn_label"],
        "prn": spec["prn"],
        "tracking_channel": spec["channel"],
        "environment": spec["environment"],
        "center_window_id": center_id,
        "confirmed_under_stage4_criterion": None,
        "five_snapshot_symbols": None,
        "native_stage4_paths": None,
    }
    if center_id is not None:
        event["confirmed_under_stage4_criterion"] = event_is_confirmed(summary, path_rows, center_id)
        if must_confirm and not event["confirmed_under_stage4_criterion"]:
            fail(f"Event is not confirmed under fixed Stage4 criterion: {scene_key}/{center_id}")
        event["five_snapshot_symbols"] = five_snapshot_rows(symbols, center_id)
        event["native_stage4_paths"] = [
            {key: (int(float(value)) if key in {"path_id", "is_multipath", "joint_selected_L"} else float(value) if key not in {"center_window_id"} else int(float(value)))
             for key, value in row.items()}
            for row in event_path_rows(path_rows, center_id)
        ]
    return event


def main() -> int:
    output_dir = CONTRACT_PATH.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    source_paths: list[dict[str, Any]] = [source_record(PIPELINE, "frozen_pipeline_source")]
    scene_info: dict[str, Any] = {}
    for key in SCENES:
        paths = scene_paths(key)
        scene_info[key] = {
            "scene_id": SCENES[key]["scene_id"],
            "prn_label": SCENES[key]["prn_label"],
            "environment": SCENES[key]["environment"],
            "raw_path": str(paths["raw"]),
            "raw_bytes": paths["raw"].stat().st_size,
        }
        for role, path in [
            (f"{key}_run_context", paths["context"]),
            (f"{key}_gnss_sdr_config", paths["config"]),
            (f"{key}_stage0_windows", paths["stage0_windows"]),
            (f"{key}_stage0_symbols", paths["stage0_symbols"]),
            (f"{key}_stage4_summary", paths["stage4_summary"]),
            (f"{key}_stage4_paths", paths["stage4_paths"]),
            (f"{key}_stage4_mat", paths["stage4_mat"]),
            (f"{key}_tracking_mat", paths["tracking"]),
            (f"{key}_telemetry_dat", paths["telemetry"]),
            (f"{key}_raw_iq", paths["raw"]),
        ]:
            print(f"HASHING {role}: {path}", flush=True)
            source_paths.append(source_record(path, role))

    g18_paths = scene_paths("G18")
    g18_summary = read_csv(g18_paths["stage4_summary"])
    g18_zero_centers = first_three_g18_zero_centers(g18_summary)

    contract = {
        "contract_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_CONTRACT_EXECUTION_AUTHORIZED_PYTHON",
        "execution_authorized_by": "author_python_confirmation_2026-08-23",
        "production_execution": False,
        "resume": False,
        "implementation": {
            "language": "python",
            "max_workers": 1,
            "matlab_process_started": False,
            "matlab_process_attached": False,
            "production_runner_interaction": False,
            "entrypoints": [
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(path),
                }
                for path in PYTHON_ENTRYPOINTS
            ],
            "modules": [
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(path),
                }
                for path in PYTHON_MODULES
            ],
        },
        "sample_rate_hz": 10_230_000,
        "samples_per_chip": 10.0,
        "samples_per_ms": 10_230,
        "samples_per_20ms": 204_600,
        "samples_per_40ms": 409_200,
        "output_namespace": str(ROOT / "docs" / "vtc2027_spring" / "evidence" / "validation_v1"),
        "source_paths": source_paths,
        "source_scene_summary": scene_info,
        "layer1": {
            "name": "controlled_injected_path_recovery",
            "scene_key": "G18",
            "confirmed_criterion_note": "No Stage4-confirmed secondary path under the current criterion; not LOS or multipath-free.",
            "center_window_ids": g18_zero_centers,
            "cases": [make_case("G18", center_id, must_confirm=False) for center_id in g18_zero_centers],
            "excess_delay_samples": [1.1, 3.0],
            "relative_doppler_hz": [-30.0, 0.0, 30.0],
            "relative_power_db": [-5.0, -10.0, -15.0],
            "relative_phase_rad": [0.0, math.pi / 2, math.pi, 3 * math.pi / 2],
            "snapshot_count": 5,
            "trial_count": 216,
        },
        "layer2": {
            "name": "incremental_recovery_on_confirmed_multipath_backgrounds",
            "events": [make_case(scene_key, center_id, must_confirm=True) for scene_key, center_id in LAYER2_EVENTS],
            "excess_delay_samples": [2.5, 4.0],
            "relative_doppler_hz": [-30.0, 30.0],
            "relative_power_db": [-8.0, -12.0, -16.0],
            "relative_phase_rad": [0.0, math.pi / 2, math.pi, 3 * math.pi / 2],
            "snapshot_count": 5,
            "trial_count": 192,
            "native_path_truth_note": "Only the added synthetic path has known truth; native paths are consistency references.",
        },
        "matching": {
            "delay_tolerance_samples": 0.2,
            "doppler_tolerance_hz": 5.0,
            "power_tolerance_db": 2.0,
            "normalized_cost": "abs(delay_error)/0.2 + abs(doppler_error)/5 + abs(power_error)/2",
            "one_to_one": True,
        },
        "estimator": {
            "maximum_model_order": 4,
            "delay_step_samples": 0.1,
            "minimum_path_separation_samples": 1.0,
            "local_delay_half_width_samples": 0.8,
            "local_doppler_step_hz": 5.0,
            "local_doppler_half_width_hz": 30.0,
            "minimum_path_power_db": -25.0,
            "maximum_path_coherence": 0.98,
            "minimum_sequential_bic_gain": 10.0,
            "minimum_joint_snapshot_wins": 4,
            "joint_snapshot_count": 5,
            "sage_iterations": 10,
            "sage_tolerance": 1e-6,
        },
        "dll": {
            "early_late_space_chips": 0.5,
            "dll_bw_hz": 4.0,
            "code_rate_hz": 1_023_000.0,
            "meters_per_chip": 299_792_458.0 / 1_023_000.0,
            "case_count": 4,
            "discriminator": "verify_local_gnss_sdr_formula_else_normalized_noncoherent_early_late_envelope",
        },
        "paper_admission_gate": {
            "layer1_recovery_rate_minimum_by_power_db": {"-5": 0.80, "-10": 0.80},
            "layer2_recovery_rate_minimum_by_power_db": {"-8": 0.70, "-12": 0.70},
            "dll_events_with_median_absolute_bias_reduction_minimum": 3,
            "all_adverse_cases_retained": True,
        },
        "scientific_constraints": {
            "no_production_namespace_write": True,
            "no_stage0_stage4_production_rerun": True,
            "no_threshold_tuning": True,
            "no_pvt_or_positioning_claim": True,
            "no_pseudorange_improvement_claim": True,
            "no_20_46_mhz": True,
        },
    }

    CONTRACT_PATH.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {CONTRACT_PATH}")
    print(f"G18_ZERO_CENTERS={g18_zero_centers}")
    print("LAYER1_TRIALS=216")
    print("LAYER2_TRIALS=192")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CONTRACT_FREEZE_FAILED: {exc}", file=sys.stderr)
        raise
