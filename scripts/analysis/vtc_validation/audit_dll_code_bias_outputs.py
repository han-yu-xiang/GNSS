"""Audit DLL code-bias case-study outputs."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/vtc2027_spring/evidence/validation_v1"
CONTRACT = OUT / "validation_contract.json"
CASES = OUT / "dll_code_bias_cases.csv"
SUMMARY = OUT / "dll_code_bias_summary.csv"
MANIFEST = OUT / "dll_code_bias_manifest.json"

REQUIRED = {
    "event_label", "scene_id", "prn_label", "environment", "center_window_id",
    "snapshot_index", "mode", "error_source_trial_id", "zero_crossing_chips",
    "bias_chips", "bias_m", "absolute_bias_chips", "absolute_bias_m",
    "valid_crossing", "delay_error_samples", "doppler_error_hz", "power_error_db",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def audit_outputs() -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if not CASES.is_file():
        raise AssertionError(f"missing DLL cases: {CASES}")
    with CASES.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise AssertionError("DLL cases are empty")
    if set(rows[0]) != REQUIRED:
        raise AssertionError(f"DLL schema mismatch: {set(rows[0]) ^ REQUIRED}")
    expected_events = {
        f"{event['scene_id']}_{event['prn_label']}_{event['center_window_id']}"
        for event in contract["layer2"]["events"]
    }
    actual_events = {row["event_label"] for row in rows}
    if actual_events != expected_events:
        raise AssertionError(f"DLL event mapping mismatch: {actual_events ^ expected_events}")
    modes = {row["mode"] for row in rows}
    if modes != {"pre_cancellation", "fitted_model_cancellation", "error_aware_cancellation"}:
        raise AssertionError(f"DLL modes mismatch: {modes}")
    for row in rows:
        if not 1 <= int(float(row["snapshot_index"])) <= 5:
            raise AssertionError(f"invalid DLL snapshot index: {row}")
        bias = float(row["bias_chips"])
        bias_m = float(row["bias_m"])
        if abs(bias_m - bias * float(contract["dll"]["meters_per_chip"])) > 1e-9:
            raise AssertionError(f"chip-to-meter conversion mismatch: {row}")
        if abs(float(row["absolute_bias_chips"]) - abs(bias)) > 1e-9:
            raise AssertionError(f"absolute chip bias mismatch: {row}")
        if abs(float(row["absolute_bias_m"]) - abs(bias_m)) > 1e-9:
            raise AssertionError(f"absolute meter bias mismatch: {row}")
    mode_counts = {mode: sum(row["mode"] == mode for row in rows) for mode in modes}
    for required_mode in ("pre_cancellation", "fitted_model_cancellation"):
        if mode_counts[required_mode] != 20:
            raise AssertionError(f"{required_mode} must contain 4*5=20 rows")
    result = {
        "audit": "DLL_CODE_BIAS_AUDIT_PASS",
        "row_count": len(rows),
        "mode_counts": mode_counts,
        "valid_crossing_count": sum(row["valid_crossing"].strip().lower() in {"1", "true"} for row in rows),
        "contract_sha256": sha256(CONTRACT),
        "cases_sha256": sha256(CASES),
        "summary_sha256": sha256(SUMMARY) if SUMMARY.is_file() else None,
    }
    MANIFEST.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(audit_outputs(), indent=2))
