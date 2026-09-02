"""Export frozen native L=1-versus-selected Stage4 model support in Python."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from mat_v5_reader import load_mat_v5


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "docs/vtc2027_spring/evidence/validation_v1/validation_contract.json"


def source_path(contract: dict[str, Any], role: str) -> Path:
    matches = [item for item in contract["source_paths"] if item["role"] == role]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one contract source for role {role}")
    return Path(matches[0]["path"])


def _number(value: Any) -> float:
    array = np.asarray(value)
    if array.size != 1:
        raise ValueError("expected scalar MAT value")
    return float(array.reshape(-1)[0])


def build_layer3_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mat_cache: dict[str, dict[str, Any]] = {}
    for event in contract["layer2"]["events"]:
        prn_label = event["prn_label"]
        mat_path = source_path(contract, f"{prn_label}_stage4_mat")
        content = mat_cache.setdefault(str(mat_path), load_mat_v5(mat_path))
        center = int(event["center_window_id"])
        fit = next(
            item for item in content["jointFits"]
            if int(_number(item["centerWindowId"])) == center
        )
        selected_order = int(_number(fit["selectedOrder"]))
        models = fit["models"]
        l1 = models[0]
        selected = models[selected_order - 1]
        l1_rss = _number(l1["rss"])
        selected_rss = _number(selected["rss"])
        l1_bic = _number(l1["bic"])
        selected_bic = _number(selected["bic"])
        l1_snapshot = np.asarray(l1["snapshotRss"], dtype=float).reshape(-1)
        selected_snapshot = np.asarray(selected["snapshotRss"], dtype=float).reshape(-1)
        if l1_snapshot.size != 5 or selected_snapshot.size != 5:
            raise ValueError(f"expected five snapshot RSS values at {prn_label}/{center}")
        row: dict[str, Any] = {
            "scene_id": event["scene_id"],
            "prn_label": prn_label,
            "environment": event["environment"],
            "center_window_id": center,
            "selected_order": selected_order,
            "l1_valid": bool(_number(l1["valid"])),
            "selected_valid": bool(_number(selected["valid"])),
            "l1_rss": l1_rss,
            "selected_rss": selected_rss,
            "rss_reduction_percent": 100.0 * (l1_rss - selected_rss) / max(l1_rss, np.finfo(float).tiny),
            "l1_bic": l1_bic,
            "selected_bic": selected_bic,
            "delta_bic": l1_bic - selected_bic,
            "l1_snapshot_wins": int(_number(l1["snapshotWins"])),
            "selected_snapshot_wins": int(_number(selected["snapshotWins"])),
        }
        for index in range(5):
            row[f"l1_snapshot_rss_{index + 1}"] = float(l1_snapshot[index])
            row[f"selected_snapshot_rss_{index + 1}"] = float(selected_snapshot[index])
        rows.append(row)
    return rows


def main() -> int:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    output = Path(contract["output_namespace"]) / "layer3_native_model_support.csv"
    rows = build_layer3_rows(contract)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Layer 3 wrote {len(rows)} native event rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
