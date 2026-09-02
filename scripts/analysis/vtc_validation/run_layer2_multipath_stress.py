"""Pure-Python Layer 2 runner for the frozen VTC validation contract."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections.abc import Iterator
from pathlib import Path
from statistics import median
from typing import Any

from vtc_validation_common import (
    EstimatorConfig,
    MatchingTolerances,
    ValidationCase,
    estimate_joint,
    estimator_from_contract,
    inject_observations,
    load_observations,
    match_injected_and_native,
    prepare_case,
    tolerances_from_contract,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACT = ROOT / "docs/vtc2027_spring/evidence/validation_v1/validation_contract.json"

FIELDS = [
    "trial_id", "layer", "scene_id", "prn_label", "environment",
    "center_window_id", "source_interval_start_zero_based",
    "source_interval_end_zero_based", "excess_delay_truth_samples",
    "relative_doppler_truth_hz", "relative_power_truth_db", "phase_truth_rad",
    "selected_order", "joint_valid", "injected_match",
    "injected_delay_error_samples", "injected_doppler_error_hz",
    "injected_power_error_db", "injected_match_cost", "native_path_consistency",
    "native_delay_drift_samples", "native_doppler_drift_hz", "native_power_drift_db",
    "joint_rss", "joint_bic", "snapshot_wins", "failure_reason",
]


def enumerate_trials(contract: dict[str, Any]) -> Iterator[dict[str, Any]]:
    ordinal = 0
    layer = contract["layer2"]
    for event in layer["events"]:
        for delay in layer["excess_delay_samples"]:
            for doppler in layer["relative_doppler_hz"]:
                for power in layer["relative_power_db"]:
                    for phase in layer["relative_phase_rad"]:
                        ordinal += 1
                        yield {
                            "trial_id": f"L2_{ordinal:04d}",
                            "case": event,
                            "delay": float(delay),
                            "doppler": float(doppler),
                            "power": float(power),
                            "phase": float(phase),
                        }


def _base_row(case: ValidationCase, trial: dict[str, Any]) -> dict[str, Any]:
    starts = [int(snapshot["sample_start_zero_based"]) for snapshot in case.snapshots]
    return {
        "trial_id": trial["trial_id"], "layer": "Layer2_MultipathStress",
        "scene_id": case.scene_id, "prn_label": case.prn_label,
        "environment": case.environment, "center_window_id": case.center_window_id,
        "source_interval_start_zero_based": min(starts),
        "source_interval_end_zero_based": max(starts) + case.sample_count - 1,
        "excess_delay_truth_samples": trial["delay"],
        "relative_doppler_truth_hz": trial["doppler"],
        "relative_power_truth_db": trial["power"], "phase_truth_rad": trial["phase"],
        "selected_order": math.nan, "joint_valid": False, "injected_match": False,
        "injected_delay_error_samples": math.nan, "injected_doppler_error_hz": math.nan,
        "injected_power_error_db": math.nan, "injected_match_cost": math.nan,
        "native_path_consistency": False, "native_delay_drift_samples": math.nan,
        "native_doppler_drift_hz": math.nan, "native_power_drift_db": math.nan,
        "joint_rss": math.nan, "joint_bic": math.nan, "snapshot_wins": 0,
        "failure_reason": "NOT_RUN",
    }


def execute_trial(
    case: ValidationCase,
    base_observations: list,
    trial: dict[str, Any],
    estimator: EstimatorConfig,
    tolerances: MatchingTolerances,
) -> dict[str, Any]:
    if len(case.native_paths) < 2:
        raise ValueError("Layer 2 case has no native confirmed secondary path")
    row = _base_row(case, trial)
    observations = inject_observations(
        base_observations, case, trial["delay"], trial["doppler"],
        trial["power"], trial["phase"],
    )
    result = estimate_joint(
        observations, case.direct_path, case.contexts, case.doppler_bound_hz, estimator
    )
    injected, native = match_injected_and_native(
        result.selected,
        (trial["delay"], trial["doppler"], trial["power"]),
        case.native_paths[1], case.direct_path, case.native_relative_power_db[1], tolerances,
    )
    row.update(
        selected_order=result.selected_order, joint_valid=result.joint_valid,
        injected_match=injected.found,
        injected_delay_error_samples=injected.delay_error_samples,
        injected_doppler_error_hz=injected.doppler_error_hz,
        injected_power_error_db=injected.power_error_db,
        injected_match_cost=injected.cost,
        native_path_consistency=native.found,
        native_delay_drift_samples=native.delay_error_samples,
        native_doppler_drift_hz=native.doppler_error_hz,
        native_power_drift_db=native.power_error_db,
        joint_rss=result.joint_rss, joint_bic=result.joint_bic,
        snapshot_wins=result.snapshot_wins,
    )
    if not result.joint_valid:
        row["failure_reason"] = "SELECTED_MODEL_INVALID"
    elif result.selected_order < 3:
        row["failure_reason"] = "PATH_MERGING_OR_ORDER_UNDER_SELECTION"
    elif not injected.found:
        row["failure_reason"] = "INJECTED_PATH_OUTSIDE_TOLERANCE"
    elif not native.found:
        row["failure_reason"] = "NATIVE_PATH_DISPLACEMENT"
    elif result.selected_order > 3:
        row["failure_reason"] = "ORDER_OVER_SELECTION"
    else:
        row["failure_reason"] = "PASS"
    return row


def _write_rows(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({
        (row["scene_id"], row["prn_label"], row["environment"], float(row["relative_power_truth_db"]))
        for row in rows
    })
    output = []
    for scene, prn, environment, power in keys:
        subset = [row for row in rows if (
            row["scene_id"], row["prn_label"], row["environment"],
            float(row["relative_power_truth_db"])
        ) == (scene, prn, environment, power)]
        finite = [row for row in subset if all(math.isfinite(float(row[key])) for key in (
            "injected_delay_error_samples", "injected_doppler_error_hz", "injected_power_error_db"
        ))]
        output.append({
            "layer": "Layer2_MultipathStress", "scene_id": scene, "prn_label": prn,
            "environment": environment, "relative_power_db": power,
            "trial_count": len(subset),
            "recovery_count": sum(bool(row["injected_match"]) for row in subset),
            "recovery_rate": sum(bool(row["injected_match"]) for row in subset) / max(len(subset), 1),
            "native_consistency_count": sum(bool(row["native_path_consistency"]) for row in subset),
            "native_consistency_rate": sum(bool(row["native_path_consistency"]) for row in subset) / max(len(subset), 1),
            "median_abs_delay_error_samples": median(abs(float(row["injected_delay_error_samples"])) for row in finite) if finite else math.nan,
            "median_abs_doppler_error_hz": median(abs(float(row["injected_doppler_error_hz"])) for row in finite) if finite else math.nan,
            "median_abs_power_error_db": median(abs(float(row["injected_power_error_db"])) for row in finite) if finite else math.nan,
        })
    return output


def run(contract_path: Path = DEFAULT_CONTRACT, max_trials: int | None = None) -> int:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract["production_execution"] or contract["resume"]:
        raise ValueError("validation contract is not isolated from production/resume")
    output_dir = Path(contract["output_namespace"])
    output_dir.mkdir(parents=True, exist_ok=True)
    estimator = estimator_from_contract(contract)
    tolerances = tolerances_from_contract(contract)
    rows: list[dict[str, Any]] = []
    case_cache: dict[tuple[str, int], tuple[ValidationCase, list]] = {}
    for ordinal, trial in enumerate(enumerate_trials(contract), start=1):
        if max_trials is not None and ordinal > max_trials:
            break
        key = (str(trial["case"]["prn_label"]), int(trial["case"]["center_window_id"]))
        if key not in case_cache:
            case = prepare_case(contract, trial["case"])
            observations, _ = load_observations(case)
            case_cache[key] = (case, observations)
            print(f"Layer 2 loaded {case.scene_id}/{case.prn_label}/{case.center_window_id}", flush=True)
        case, base = case_cache[key]
        try:
            row = execute_trial(case, base, trial, estimator, tolerances)
        except Exception as exc:
            row = _base_row(case, trial)
            row["failure_reason"] = f"PYTHON_ERROR: {type(exc).__name__}: {exc}"
        rows.append(row)
        if ordinal % 4 == 0:
            _write_rows(output_dir / "layer2_multipath_stress_trials.partial.csv", rows, FIELDS)
            print(f"Layer 2 progress {ordinal}/192", flush=True)
    output_name = "layer2_multipath_stress_trials.csv" if max_trials is None else "layer2_multipath_stress_trials.smoke.csv"
    _write_rows(output_dir / output_name, rows, FIELDS)
    if max_trials is None:
        summary = _summary(rows)
        _write_rows(output_dir / "layer2_multipath_stress_summary.csv", summary, list(summary[0]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--max-trials", type=int)
    args = parser.parse_args()
    return run(args.contract, args.max_trials)


if __name__ == "__main__":
    raise SystemExit(main())
