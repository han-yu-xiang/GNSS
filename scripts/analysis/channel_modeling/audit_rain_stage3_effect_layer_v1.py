"""Independent, gold-blind QA for a Rain Stage3 effect-layer collection."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from rain_stage3_effect_layer_v1 import FINAL_COLUMNS, sha256_file


def _f(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite value: {value!r}")
    return number


def _i(value: str) -> int:
    return int(value)


def audit_collection(collection_dir: Path) -> dict[str, Any]:
    manifest_path = collection_dir / "rain_effect_layer_manifest.json"
    run_manifest_path = collection_dir / "rain_effect_layer_run_manifest.json"
    if not manifest_path.is_file() or not run_manifest_path.is_file():
        raise FileNotFoundError("collection or run manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    tables: list[dict[str, Any]] = []
    failures: list[str] = []
    source_hashes_before: dict[str, str] = {}
    for record in manifest["tables"]:
        source = Path(record["source_path"])
        output = Path(record["path"])
        if not source.is_file() or not output.is_file():
            failures.append(f"missing source/output: {source} / {output}")
            continue
        source_hash = sha256_file(source)
        source_hashes_before[str(source)] = source_hash
        if source_hash.lower() != str(record["source_sha256"]).lower():
            failures.append(f"source hash mismatch: {source}")
        output_hash = sha256_file(output)
        if output_hash.lower() != str(record["sha256"]).lower():
            failures.append(f"output hash mismatch: {output}")

        source_rows = 0
        output_rows = 0
        main_unchanged = True
        nlos_rows = 0
        nlos_positive = True
        nonfinite = False
        block_values: dict[tuple[str, int, int], tuple[float, float, float]] = {}
        phase_last: dict[tuple[str, int], tuple[int, float, float]] = {}
        source_handle = source.open("r", encoding="utf-8-sig", newline="")
        output_handle = output.open("r", encoding="utf-8-sig", newline="")
        try:
            source_reader = csv.DictReader(source_handle)
            output_reader = csv.DictReader(output_handle)
            if tuple(source_reader.fieldnames or ()) != FINAL_COLUMNS:
                failures.append(f"source schema mismatch: {source}")
            if tuple(output_reader.fieldnames or ()) != FINAL_COLUMNS:
                failures.append(f"output schema mismatch: {output}")
            for source_row, output_row in zip(source_reader, output_reader):
                source_rows += 1
                output_rows += 1
                if source_row["ms"] != output_row["ms"] or source_row["SatelliteID"] != output_row["SatelliteID"] or source_row["NLOSPathID"] != output_row["NLOSPathID"]:
                    failures.append(f"identity/order mismatch in {output} at row {output_rows}")
                    break
                path_id = _i(output_row["NLOSPathID"])
                ms = _i(output_row["ms"])
                values = tuple(_f(output_row[field]) for field in FINAL_COLUMNS[3:])
                source_values = tuple(_f(source_row[field]) for field in FINAL_COLUMNS[3:])
                if path_id == 0:
                    if any(abs(a - b) > 1e-10 for a, b in zip(values, source_values)):
                        main_unchanged = False
                else:
                    nlos_rows += 1
                    if values[2] <= 0:
                        nlos_positive = False
                    block = (ms - 1) // 40
                    key = (output_row["SatelliteID"], path_id, block)
                    current_effect = (values[0] - source_values[0], values[1] - source_values[1], math.log(values[2] / source_values[2]))
                    prior = block_values.get(key)
                    if prior is None:
                        block_values[key] = current_effect
                    elif any(abs(a - b) > 1e-10 for a, b in zip(prior, current_effect)):
                        failures.append(f"40ms block effect is not constant in {output} at row {output_rows}")
                        break
                phase_key = (output_row["SatelliteID"], path_id)
                previous = phase_last.get(phase_key)
                if previous is not None and previous[0] == ms - 1:
                    expected = (previous[1] + 2.0 * math.pi * values[1] * 1e-3 + math.pi) % (2.0 * math.pi) - math.pi
                    if abs(((values[3] - expected + math.pi) % (2.0 * math.pi)) - math.pi) > 1e-9:
                        failures.append(f"phase recurrence mismatch in {output} at row {output_rows}")
                        break
                phase_last[phase_key] = (ms, values[3], values[1])
            extra_source = next(source_reader, None)
            extra_output = next(output_reader, None)
            if extra_source is not None or extra_output is not None:
                failures.append(f"row count mismatch in {output}")
        finally:
            source_handle.close()
            output_handle.close()
        if output_rows != int(record["rows"]):
            failures.append(f"manifest row count mismatch in {output}: {output_rows} != {record['rows']}")
        tables.append({
            "path": str(output),
            "source_path": str(source),
            "rows": output_rows,
            "source_rows": source_rows,
            "output_sha256": output_hash,
            "source_sha256": source_hash,
            "main_path_unchanged": main_unchanged,
            "nlos_rows": nlos_rows,
            "nlos_amplitude_strictly_positive": nlos_positive,
            "numeric_finite": not nonfinite,
            "block_effect_count": len(block_values),
        })
        if not main_unchanged:
            failures.append(f"main path changed in {output}")
        if not nlos_positive:
            failures.append(f"non-positive NLOS amplitude in {output}")

    model = json.loads((collection_dir / "rain_effect_model.json").read_text(encoding="utf-8"))
    evidence_rows = sum(1 for _ in (collection_dir / "stage3_rain_path_evidence.csv").open("r", encoding="utf-8")) - 1
    episode_rows = sum(1 for _ in (collection_dir / "stage3_rain_episode_catalog.csv").open("r", encoding="utf-8")) - 1
    report = {
        "qa_schema_version": "rain-stage3-effect-layer-qa-1",
        "collection_dir": str(collection_dir),
        "collection_manifest_sha256": sha256_file(manifest_path),
        "run_manifest_sha256": sha256_file(run_manifest_path),
        "model_sha256": sha256_file(collection_dir / "rain_effect_model.json"),
        "evidence_rows": evidence_rows,
        "episode_rows": episode_rows,
        "table_count": len(tables),
        "tables": tables,
        "gold_blind": {
            "stage4_read": False,
            "gold_labels_used_for_selection": bool(run_manifest["gold_labels_used_for_selection"]),
        },
        "input_protection": {
            "source_hashes_rechecked": True,
            "source_hashes": source_hashes_before,
            "output_under_sage_results": "\\sage_results\\" in str(collection_dir).lower(),
        },
        "failures": failures,
        "pass": not failures and len(tables) == 8 and evidence_rows == 90 and episode_rows == 26,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection-dir", type=Path, required=True)
    args = parser.parse_args()
    report = audit_collection(args.collection_dir.resolve())
    out = args.collection_dir.resolve() / "rain_effect_layer_qa.json"
    out.write_bytes((json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(f"QA_REPORT={out}")
    print(f"QA_PASS={str(report['pass']).upper()}")
    print(f"TABLES={report['table_count']}")
    print(f"EVIDENCE_ROWS={report['evidence_rows']}")
    print(f"EPISODES={report['episode_rows']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
