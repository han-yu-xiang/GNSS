"""Audit Layer 1 controlled-recovery outputs without changing source artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs/vtc2027_spring/evidence/validation_v1/validation_contract.json"
OUT = CONTRACT.parent
TRIALS = OUT / "layer1_controlled_trials.csv"
SUMMARY = OUT / "layer1_controlled_summary.csv"
MANIFEST = OUT / "layer1_controlled_manifest.json"


REQUIRED = {
    "trial_id", "layer", "scene_id", "prn_label", "environment",
    "center_window_id", "source_interval_start_zero_based",
    "source_interval_end_zero_based", "excess_delay_truth_samples",
    "relative_doppler_truth_hz", "relative_power_truth_db", "phase_truth_rad",
    "selected_order", "joint_valid", "injected_match", "delay_error_samples",
    "doppler_error_hz", "power_error_db", "match_cost", "joint_rss",
    "joint_bic", "snapshot_wins", "failure_reason",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(row: dict[str, str], key: str) -> float:
    return float(row[key])


def audit_outputs() -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if not TRIALS.is_file():
        raise AssertionError(f"missing Layer 1 output: {TRIALS}")
    rows = read_csv(TRIALS)
    if len(rows) != contract["layer1"]["trial_count"]:
        raise AssertionError(f"Layer 1 row count {len(rows)} != 216")
    if not rows:
        raise AssertionError("Layer 1 output is empty")
    if set(rows[0]) != REQUIRED:
        raise AssertionError(f"Layer 1 schema mismatch: {set(rows[0]) ^ REQUIRED}")
    ids = [row["trial_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("Layer 1 trial IDs are not unique")

    grids = contract["layer1"]
    allowed_delay = {float(value) for value in grids["excess_delay_samples"]}
    allowed_doppler = {float(value) for value in grids["relative_doppler_hz"]}
    allowed_power = {float(value) for value in grids["relative_power_db"]}
    allowed_phase = {float(value) for value in grids["relative_phase_rad"]}
    expected_centers = {str(value) for value in grids["center_window_ids"]}
    for row in rows:
        if row["layer"] != "Layer1_Controlled":
            raise AssertionError(f"wrong layer label: {row}")
        if row["center_window_id"] not in expected_centers:
            raise AssertionError(f"unexpected center: {row}")
        if as_float(row, "excess_delay_truth_samples") not in allowed_delay:
            raise AssertionError(f"unexpected delay grid value: {row}")
        if as_float(row, "relative_doppler_truth_hz") not in allowed_doppler:
            raise AssertionError(f"unexpected Doppler grid value: {row}")
        if as_float(row, "relative_power_truth_db") not in allowed_power:
            raise AssertionError(f"unexpected power grid value: {row}")
        if as_float(row, "phase_truth_rad") not in allowed_phase:
            raise AssertionError(f"unexpected phase grid value: {row}")
        if int(float(row["snapshot_wins"])) not in range(0, 6):
            raise AssertionError(f"invalid snapshot wins: {row}")
        if "scenes" in row["source_interval_start_zero_based"]:
            raise AssertionError("output row contains a production namespace")

    if SUMMARY.is_file():
        summary_rows = read_csv(SUMMARY)
        if len(summary_rows) != len(allowed_power):
            raise AssertionError("Layer 1 summary does not have one row per power level")
        if sum(int(float(row["trial_count"])) for row in summary_rows) != len(rows):
            raise AssertionError("Layer 1 summary trial counts do not sum to 216")

    result = {
        "audit": "LAYER1_CONTROLLED_AUDIT_PASS",
        "trial_count": len(rows),
        "source_cases": sorted(expected_centers),
        "contract_sha256": sha256(CONTRACT),
        "trials_sha256": sha256(TRIALS),
        "summary_sha256": sha256(SUMMARY) if SUMMARY.is_file() else None,
        "recovery_count": sum(row["injected_match"].strip().lower() in {"1", "true"} for row in rows),
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    result = audit_outputs()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
