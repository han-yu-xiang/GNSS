"""Audit native L=1 versus selected-model support exported from Stage4 MAT."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/vtc2027_spring/evidence/validation_v1"
CONTRACT = OUT / "validation_contract.json"
OUTPUT = OUT / "layer3_native_model_support.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def audit_outputs() -> dict:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if not OUTPUT.is_file():
        raise AssertionError(f"missing Layer 3 output: {OUTPUT}")
    with OUTPUT.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 4:
        raise AssertionError(f"Layer 3 row count {len(rows)} != 4")
    expected = {
        (event["scene_id"], event["prn_label"], str(event["center_window_id"]))
        for event in contract["layer2"]["events"]
    }
    actual = {(row["scene_id"], row["prn_label"], row["center_window_id"]) for row in rows}
    if actual != expected:
        raise AssertionError(f"Layer 3 event mapping mismatch: {actual ^ expected}")
    for row in rows:
        l1_rss = float(row["l1_rss"])
        selected_rss = float(row["selected_rss"])
        delta_bic = float(row["delta_bic"])
        recomputed_reduction = 100 * (l1_rss - selected_rss) / max(l1_rss, 1e-300)
        if abs(recomputed_reduction - float(row["rss_reduction_percent"])) > 1e-6:
            raise AssertionError(f"RSS reduction mismatch: {row}")
        if abs(delta_bic - (float(row["l1_bic"]) - float(row["selected_bic"]))) > 1e-6:
            raise AssertionError(f"BIC difference mismatch: {row}")
        for prefix in ("l1_snapshot_rss_", "selected_snapshot_rss_"):
            for index in range(1, 6):
                if float(row[f"{prefix}{index}"]) < 0:
                    raise AssertionError(f"negative snapshot RSS: {row}")
    result = {
        "audit": "LAYER3_NATIVE_MODEL_AUDIT_PASS",
        "event_count": len(rows),
        "contract_sha256": sha256(CONTRACT),
        "output_sha256": sha256(OUTPUT),
        "positive_delta_bic_count": sum(float(row["delta_bic"]) > 0 for row in rows),
        "positive_rss_reduction_count": sum(float(row["rss_reduction_percent"]) > 0 for row in rows),
    }
    return result


if __name__ == "__main__":
    print(json.dumps(audit_outputs(), indent=2))
