"""Audit Layer 2 incremental recovery outputs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs/vtc2027_spring/evidence/validation_v1/validation_contract.json"
OUT = CONTRACT.parent
TRIALS = OUT / "layer2_multipath_stress_trials.csv"
SUMMARY = OUT / "layer2_multipath_stress_summary.csv"
MANIFEST = OUT / "layer2_multipath_stress_manifest.json"

REQUIRED = {
    "trial_id", "layer", "scene_id", "prn_label", "environment",
    "center_window_id", "source_interval_start_zero_based",
    "source_interval_end_zero_based", "excess_delay_truth_samples",
    "relative_doppler_truth_hz", "relative_power_truth_db", "phase_truth_rad",
    "selected_order", "joint_valid", "injected_match",
    "injected_delay_error_samples", "injected_doppler_error_hz",
    "injected_power_error_db", "injected_match_cost", "native_path_consistency",
    "native_delay_drift_samples", "native_doppler_drift_hz", "native_power_drift_db",
    "joint_rss", "joint_bic", "snapshot_wins", "failure_reason",
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
        raise AssertionError(f"missing Layer 2 output: {TRIALS}")
    rows = read_csv(TRIALS)
    if len(rows) != contract["layer2"]["trial_count"]:
        raise AssertionError(f"Layer 2 row count {len(rows)} != 192")
    if not rows:
        raise AssertionError("Layer 2 output is empty")
    if set(rows[0]) != REQUIRED:
        raise AssertionError(f"Layer 2 schema mismatch: {set(rows[0]) ^ REQUIRED}")
    ids = [row["trial_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("Layer 2 trial IDs are not unique")

    allowed_events = {
        (event["scene_id"], event["prn_label"], str(event["center_window_id"]))
        for event in contract["layer2"]["events"]
    }
    allowed_delay = {float(value) for value in contract["layer2"]["excess_delay_samples"]}
    allowed_doppler = {float(value) for value in contract["layer2"]["relative_doppler_hz"]}
    allowed_power = {float(value) for value in contract["layer2"]["relative_power_db"]}
    allowed_phase = {float(value) for value in contract["layer2"]["relative_phase_rad"]}
    for row in rows:
        key = (row["scene_id"], row["prn_label"], row["center_window_id"])
        if key not in allowed_events:
            raise AssertionError(f"unexpected Layer 2 event: {row}")
        if row["layer"] != "Layer2_MultipathStress":
            raise AssertionError(f"wrong layer label: {row}")
        if as_float(row, "excess_delay_truth_samples") not in allowed_delay:
            raise AssertionError(f"unexpected delay grid value: {row}")
        if as_float(row, "relative_doppler_truth_hz") not in allowed_doppler:
            raise AssertionError(f"unexpected Doppler grid value: {row}")
        if as_float(row, "relative_power_truth_db") not in allowed_power:
            raise AssertionError(f"unexpected power grid value: {row}")
        if as_float(row, "phase_truth_rad") not in allowed_phase:
            raise AssertionError(f"unexpected phase grid value: {row}")
        if not 0 <= int(float(row["snapshot_wins"])) <= 5:
            raise AssertionError(f"invalid snapshot wins: {row}")

    if SUMMARY.is_file():
        summary_rows = read_csv(SUMMARY)
        if sum(int(float(row["trial_count"])) for row in summary_rows) != len(rows):
            raise AssertionError("Layer 2 summary trial counts do not sum to 192")

    result = {
        "audit": "LAYER2_MULTIPATH_STRESS_AUDIT_PASS",
        "trial_count": len(rows),
        "source_events": sorted({
            f"{row['scene_id']}/{row['prn_label']}/{row['center_window_id']}"
            for row in rows
        }),
        "contract_sha256": sha256(CONTRACT),
        "trials_sha256": sha256(TRIALS),
        "summary_sha256": sha256(SUMMARY) if SUMMARY.is_file() else None,
        "injected_recovery_count": sum(row["injected_match"].strip().lower() in {"1", "true"} for row in rows),
        "native_consistency_count": sum(row["native_path_consistency"].strip().lower() in {"1", "true"} for row in rows),
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    result = audit_outputs()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
