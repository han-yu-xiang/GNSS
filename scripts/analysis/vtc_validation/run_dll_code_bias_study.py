"""Pure-Python static DLL discriminator code-bias case study."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from vtc_validation_common import (
    ValidationCase,
    cancel_secondary,
    dll_zero_crossing,
    load_observations,
    prepare_case,
    solve_snapshot_alpha,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONTRACT = ROOT / "docs/vtc2027_spring/evidence/validation_v1/validation_contract.json"

FIELDS = [
    "event_label", "scene_id", "prn_label", "environment", "center_window_id",
    "snapshot_index", "mode", "error_source_trial_id", "zero_crossing_chips",
    "bias_chips", "bias_m", "absolute_bias_chips", "absolute_bias_m",
    "valid_crossing", "delay_error_samples", "doppler_error_hz", "power_error_db",
]


def _row(
    case: ValidationCase,
    snapshot_index: int,
    mode: str,
    trial_id: str,
    bias_chips: float,
    valid: bool,
    meters_per_chip: float,
    delay_error: float,
    doppler_error: float,
    power_error: float,
) -> dict[str, Any]:
    bias_m = bias_chips * meters_per_chip
    return {
        "event_label": f"{case.scene_id}_{case.prn_label}_{case.center_window_id}",
        "scene_id": case.scene_id,
        "prn_label": case.prn_label,
        "environment": case.environment,
        "center_window_id": case.center_window_id,
        "snapshot_index": snapshot_index,
        "mode": mode,
        "error_source_trial_id": trial_id,
        "zero_crossing_chips": bias_chips,
        "bias_chips": bias_chips,
        "bias_m": bias_m,
        "absolute_bias_chips": abs(bias_chips),
        "absolute_bias_m": abs(bias_m),
        "valid_crossing": valid,
        "delay_error_samples": delay_error,
        "doppler_error_hz": doppler_error,
        "power_error_db": power_error,
    }


def build_case_rows(
    case: ValidationCase,
    observations: list[np.ndarray],
    successful_errors: list[dict[str, Any]],
    spacing_chips: float,
    meters_per_chip: float,
    offset_grid_chips: np.ndarray,
) -> list[dict[str, Any]]:
    if len(case.native_paths) < 2:
        raise ValueError("DLL case does not contain a selected secondary path")
    amplitudes = [
        solve_snapshot_alpha(case.native_paths, observed, context)
        for observed, context in zip(observations, case.contexts, strict=True)
    ]
    rows: list[dict[str, Any]] = []
    for snapshot_index, (observed, context, alpha) in enumerate(
        zip(observations, case.contexts, amplitudes, strict=True), start=1
    ):
        pre_bias, _, pre_valid = dll_zero_crossing(
            observed, context, case.direct_path, spacing_chips, offset_grid_chips
        )
        rows.append(_row(
            case, snapshot_index, "pre_cancellation", "NONE", pre_bias,
            pre_valid, meters_per_chip, math.nan, math.nan, math.nan,
        ))

        fitted_residual = cancel_secondary(
            observed, context, case.native_paths, alpha, 0.0, 0.0, 0.0
        )
        fitted_bias, _, fitted_valid = dll_zero_crossing(
            fitted_residual, context, case.direct_path, spacing_chips, offset_grid_chips
        )
        rows.append(_row(
            case, snapshot_index, "fitted_model_cancellation", "NONE", fitted_bias,
            fitted_valid, meters_per_chip, math.nan, math.nan, math.nan,
        ))

        for error in successful_errors:
            delay_error = float(error["injected_delay_error_samples"])
            doppler_error = float(error["injected_doppler_error_hz"])
            power_error = float(error["injected_power_error_db"])
            residual = cancel_secondary(
                observed, context, case.native_paths, alpha,
                delay_error, doppler_error, power_error,
            )
            bias, _, valid = dll_zero_crossing(
                residual, context, case.direct_path, spacing_chips, offset_grid_chips
            )
            rows.append(_row(
                case, snapshot_index, "error_aware_cancellation",
                str(error["trial_id"]), bias, valid, meters_per_chip,
                delay_error, doppler_error, power_error,
            ))
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({(row["event_label"], row["environment"], row["mode"]) for row in rows})
    output = []
    for event, environment, mode in keys:
        subset = [row for row in rows if (
            row["event_label"], row["environment"], row["mode"]
        ) == (event, environment, mode)]
        valid = [row for row in subset if bool(row["valid_crossing"])]
        chips = np.array([float(row["absolute_bias_chips"]) for row in valid], dtype=float)
        meters = np.array([float(row["absolute_bias_m"]) for row in valid], dtype=float)
        output.append({
            "event_label": event, "environment": environment, "mode": mode,
            "row_count": len(subset), "valid_crossing_count": len(valid),
            "median_abs_bias_chips": float(np.median(chips)) if chips.size else math.nan,
            "p10_abs_bias_chips": float(np.percentile(chips, 10)) if chips.size else math.nan,
            "p90_abs_bias_chips": float(np.percentile(chips, 90)) if chips.size else math.nan,
            "median_abs_bias_m": float(np.median(meters)) if meters.size else math.nan,
            "p10_abs_bias_m": float(np.percentile(meters, 10)) if meters.size else math.nan,
            "p90_abs_bias_m": float(np.percentile(meters, 90)) if meters.size else math.nan,
        })
    return output


def run(
    contract_path: Path = DEFAULT_CONTRACT,
    max_errors: int | None = None,
    max_events: int | None = None,
    layer2_trials_path: Path | None = None,
) -> int:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract["production_execution"] or contract["resume"]:
        raise ValueError("validation contract is not isolated from production/resume")
    output_dir = Path(contract["output_namespace"])
    layer2_path = layer2_trials_path or output_dir / "layer2_multipath_stress_trials.csv"
    if not layer2_path.is_file():
        raise FileNotFoundError("Layer 2 trials are required before DLL study")
    successful = [
        row for row in _read_csv(layer2_path)
        if row["injected_match"].strip().lower() in {"1", "true"}
    ]
    if not successful:
        raise ValueError("no successful Layer 2 recovery rows are available")
    if max_errors is not None:
        successful = successful[:max_errors]
    rows: list[dict[str, Any]] = []
    spacing = float(contract["dll"]["early_late_space_chips"])
    meters_per_chip = float(contract["dll"]["meters_per_chip"])
    offsets = np.arange(-1.0, 1.0001, 0.01)
    events = contract["layer2"]["events"]
    if max_events is not None:
        events = events[:max_events]
    for event in events:
        case = prepare_case(contract, event)
        observations, _ = load_observations(case)
        rows.extend(build_case_rows(
            case, observations, successful, spacing, meters_per_chip, offsets
        ))
        _write_csv(output_dir / "dll_code_bias_cases.partial.csv", rows)
        print(f"DLL completed {case.scene_id}/{case.prn_label}/{case.center_window_id}", flush=True)
    smoke = max_errors is not None or max_events is not None or layer2_trials_path is not None
    output_name = "dll_code_bias_cases.smoke.csv" if smoke else "dll_code_bias_cases.csv"
    _write_csv(output_dir / output_name, rows)
    if not smoke:
        summary = _summary(rows)
        with (output_dir / "dll_code_bias_summary.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
            writer.writeheader()
            writer.writerows(summary)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--max-errors", type=int)
    parser.add_argument("--max-events", type=int)
    parser.add_argument("--layer2-trials", type=Path)
    args = parser.parse_args()
    return run(args.contract, args.max_errors, args.max_events, args.layer2_trials)


if __name__ == "__main__":
    raise SystemExit(main())
