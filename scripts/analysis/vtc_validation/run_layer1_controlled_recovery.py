"""Pure-Python Layer 1 runner for the frozen VTC validation contract."""

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
    match_injected,
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
    "selected_order", "joint_valid", "injected_match", "delay_error_samples",
    "doppler_error_hz", "power_error_db", "match_cost", "joint_rss",
    "joint_bic", "snapshot_wins", "failure_reason",
]


def enumerate_trials(contract: dict[str, Any]) -> Iterator[dict[str, Any]]:
    ordinal = 0
    layer = contract["layer1"]
    for case in layer["cases"]:
        for delay in layer["excess_delay_samples"]:
            for doppler in layer["relative_doppler_hz"]:
                for power in layer["relative_power_db"]:
                    for phase in layer["relative_phase_rad"]:
                        ordinal += 1
                        yield {
                            "trial_id": f"L1_{ordinal:04d}",
                            "case": case,
                            "delay": float(delay),
                            "doppler": float(doppler),
                            "power": float(power),
                            "phase": float(phase),
                        }


def _base_row(case: ValidationCase, trial: dict[str, Any]) -> dict[str, Any]:
    starts = [int(snapshot["sample_start_zero_based"]) for snapshot in case.snapshots]
    return {
        "trial_id": trial["trial_id"],
        "layer": "Layer1_Controlled",
        "scene_id": case.scene_id,
        "prn_label": case.prn_label,
        "environment": case.environment,
        "center_window_id": case.center_window_id,
        "source_interval_start_zero_based": min(starts),
        "source_interval_end_zero_based": max(starts) + case.sample_count - 1,
        "excess_delay_truth_samples": trial["delay"],
        "relative_doppler_truth_hz": trial["doppler"],
        "relative_power_truth_db": trial["power"],
        "phase_truth_rad": trial["phase"],
        "selected_order": math.nan,
        "joint_valid": False,
        "injected_match": False,
        "delay_error_samples": math.nan,
        "doppler_error_hz": math.nan,
        "power_error_db": math.nan,
        "match_cost": math.nan,
        "joint_rss": math.nan,
        "joint_bic": math.nan,
        "snapshot_wins": 0,
        "failure_reason": "NOT_RUN",
    }


def execute_trial(
    case: ValidationCase,
    base_observations: list,
    trial: dict[str, Any],
    estimator: EstimatorConfig,
    tolerances: MatchingTolerances,
) -> dict[str, Any]:
    row = _base_row(case, trial)
    observations = inject_observations(
        base_observations, case, trial["delay"], trial["doppler"],
        trial["power"], trial["phase"],
    )
    result = estimate_joint(
        observations, case.direct_path, case.contexts, case.doppler_bound_hz, estimator
    )
    match = match_injected(
        result.selected, trial["delay"], trial["doppler"], trial["power"], tolerances
    )
    row.update(
        selected_order=result.selected_order,
        joint_valid=result.joint_valid,
        injected_match=match.found,
        delay_error_samples=match.delay_error_samples,
        doppler_error_hz=match.doppler_error_hz,
        power_error_db=match.power_error_db,
        match_cost=match.cost,
        joint_rss=result.joint_rss,
        joint_bic=result.joint_bic,
        snapshot_wins=result.snapshot_wins,
    )
    if result.selected_order < 2:
        row["failure_reason"] = "NO_SECONDARY_MODEL_SELECTED"
    elif not result.joint_valid:
        row["failure_reason"] = "SELECTED_MODEL_INVALID"
    elif not match.found:
        row["failure_reason"] = "INJECTED_PATH_OUTSIDE_TOLERANCE"
    else:
        row["failure_reason"] = "PASS"
    return row


def _write_rows(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _summary(rows: list[dict[str, Any]], powers: list[float]) -> list[dict[str, Any]]:
    output = []
    for power in powers:
        subset = [row for row in rows if float(row["relative_power_truth_db"]) == float(power)]
        finite = [
            row for row in subset
            if all(math.isfinite(float(row[key])) for key in (
                "delay_error_samples", "doppler_error_hz", "power_error_db"
            ))
        ]
        output.append({
            "layer": "Layer1_Controlled",
            "relative_power_db": power,
            "trial_count": len(subset),
            "recovery_count": sum(bool(row["injected_match"]) for row in subset),
            "recovery_rate": sum(bool(row["injected_match"]) for row in subset) / max(len(subset), 1),
            "median_abs_delay_error_samples": median(abs(float(row["delay_error_samples"])) for row in finite) if finite else math.nan,
            "median_abs_doppler_error_hz": median(abs(float(row["doppler_error_hz"])) for row in finite) if finite else math.nan,
            "median_abs_power_error_db": median(abs(float(row["power_error_db"])) for row in finite) if finite else math.nan,
            "finite_error_count": len(finite),
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
    case_cache: dict[int, tuple[ValidationCase, list]] = {}
    for ordinal, trial in enumerate(enumerate_trials(contract), start=1):
        if max_trials is not None and ordinal > max_trials:
            break
        center = int(trial["case"]["center_window_id"])
        if center not in case_cache:
            case = prepare_case(contract, trial["case"])
            observations, _ = load_observations(case)
            case_cache[center] = (case, observations)
            print(f"Layer 1 loaded {case.scene_id}/{case.prn_label}/{center}", flush=True)
        case, base = case_cache[center]
        try:
            row = execute_trial(case, base, trial, estimator, tolerances)
        except Exception as exc:  # retain every failed trial
            row = _base_row(case, trial)
            row["failure_reason"] = f"PYTHON_ERROR: {type(exc).__name__}: {exc}"
        rows.append(row)
        if ordinal % 4 == 0:
            _write_rows(output_dir / "layer1_controlled_trials.partial.csv", rows, FIELDS)
            print(f"Layer 1 progress {ordinal}/216", flush=True)
    output_name = "layer1_controlled_trials.csv" if max_trials is None else "layer1_controlled_trials.smoke.csv"
    _write_rows(output_dir / output_name, rows, FIELDS)
    if max_trials is None:
        summary = _summary(rows, [float(value) for value in contract["layer1"]["relative_power_db"]])
        _write_rows(output_dir / "layer1_controlled_summary.csv", summary, list(summary[0]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--max-trials", type=int)
    args = parser.parse_args()
    return run(args.contract, args.max_trials)


if __name__ == "__main__":
    raise SystemExit(main())
