"""Contract and source-isolation tests for the VTC validation plan."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs" / "vtc2027_spring" / "evidence" / "validation_v1" / "validation_contract.json"


def load_contract() -> dict:
    assert CONTRACT.is_file(), f"missing frozen contract: {CONTRACT}"
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def test_contract_status_and_execution_boundary() -> None:
    contract = load_contract()
    assert contract["status"] == "FROZEN_CONTRACT_EXECUTION_AUTHORIZED_PYTHON"
    assert contract["production_execution"] is False
    assert contract["resume"] is False
    assert "sage_results" not in contract["output_namespace"]
    assert contract["scientific_constraints"]["no_production_namespace_write"] is True


def test_python_only_execution_does_not_interact_with_matlab_runner() -> None:
    contract = load_contract()
    implementation = contract["implementation"]
    assert implementation["language"] == "python"
    assert implementation["max_workers"] == 1
    assert implementation["matlab_process_started"] is False
    assert implementation["matlab_process_attached"] is False
    assert implementation["production_runner_interaction"] is False
    assert len(implementation["entrypoints"]) == 4
    assert len(implementation["modules"]) == 2
    for source in implementation["entrypoints"] + implementation["modules"]:
        path = ROOT / source["path"]
        assert path.is_file(), source
        assert sha256_file(path) == source["sha256"], source


def test_source_paths_exist_and_hashes_match() -> None:
    contract = load_contract()
    assert contract["source_paths"]
    for source in contract["source_paths"]:
        path = Path(source["path"])
        assert path.is_file(), source
        assert path.stat().st_size == source["bytes"], source
        assert sha256_file(path) == source["sha256"], source


def test_layer_counts_and_grids_are_frozen() -> None:
    contract = load_contract()
    layer1 = contract["layer1"]
    layer2 = contract["layer2"]
    assert len(layer1["center_window_ids"]) == 3
    assert layer1["trial_count"] == 3 * 2 * 3 * 3 * 4
    assert layer2["trial_count"] == 4 * 2 * 2 * 3 * 4
    assert len(layer2["events"]) == 4
    assert layer1["snapshot_count"] == layer2["snapshot_count"] == 5
    assert contract["matching"] == {
        "delay_tolerance_samples": 0.2,
        "doppler_tolerance_hz": 5.0,
        "power_tolerance_db": 2.0,
        "normalized_cost": "abs(delay_error)/0.2 + abs(doppler_error)/5 + abs(power_error)/2",
        "one_to_one": True,
    }


def test_stage4_confirmed_criterion_and_layer1_wording() -> None:
    contract = load_contract()
    assert "not LOS" in contract["layer1"]["confirmed_criterion_note"]
    for case in contract["layer1"]["cases"]:
        assert case["confirmed_under_stage4_criterion"] is False
    for event in contract["layer2"]["events"]:
        assert event["confirmed_under_stage4_criterion"] is True
        assert any(path["is_multipath"] == 1 for path in event["native_stage4_paths"])


def test_five_snapshot_ranges_are_contiguous_and_complete() -> None:
    contract = load_contract()
    cases = contract["layer1"]["cases"] + contract["layer2"]["events"]
    for case in cases:
        rows = case["five_snapshot_symbols"]
        assert len(rows) == 5
        assert [row["symbol_id"] for row in rows] == list(range(rows[0]["symbol_id"], rows[0]["symbol_id"] + 5))
        assert all(math.isfinite(row["code_frequency_hz"]) for row in rows)
        assert all(row["nav_symbol"] in {-1, 1} for row in rows)


def test_layer2_injection_separation_is_safe() -> None:
    contract = load_contract()
    for event in contract["layer2"]["events"]:
        native = sorted(path for path in event["native_stage4_paths"] if path["is_multipath"] == 1)
        direct = next(path for path in event["native_stage4_paths"] if path["is_multipath"] == 0)
        for injected_excess in contract["layer2"]["excess_delay_samples"]:
            injected_delay = direct["delay_samples"] + injected_excess
            assert abs(injected_delay - direct["delay_samples"]) >= 1.0
            assert all(abs(injected_delay - path["delay_samples"]) >= 1.0 for path in native)


def test_no_forbidden_execution_or_mutation_strings() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "Resume=true" not in text
    assert "20.46" not in text or "no_20_46_mhz" in text
    assert "production" in text.lower()


if __name__ == "__main__":
    tests = sorted(
        (name, value) for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    )
    for name, test in tests:
        test()
        print(f"PASS {name}")
    print(f"ALL_PASS count={len(tests)}")
