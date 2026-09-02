import sys
from pathlib import Path


HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

from audit_phase1_scientific_closure import (  # noqa: E402
    CELL_ORDER,
    CLOSURE_REQUIRED_FILES,
    REQUIRED_DECISION_KEYS,
    decision_block_values,
    validate_support_grid,
)


def test_closure_contract_has_all_machine_readable_outputs():
    assert "effect_table.csv" in CLOSURE_REQUIRED_FILES
    assert "support_gap_decision.csv" in CLOSURE_REQUIRED_FILES
    assert "publication_plot_data.csv" in CLOSURE_REQUIRED_FILES
    assert len(CLOSURE_REQUIRED_FILES) >= 15


def test_support_grid_requires_the_frozen_twelve_cells():
    rows = [
        {
            "environment_class": cell.split("__")[0],
            "elevation_band": cell.split("__")[1],
            "cell_id": cell,
            "support_status": "NO_DIRECT_SUPPORT" if cell == "Highway/Open__LOW" else "DATA_SUPPORTED",
            "direct_observation_count": "0" if cell == "Highway/Open__LOW" else "10",
        }
        for cell in CELL_ORDER
    ]
    assert validate_support_grid(rows)


def test_support_grid_rejects_synthetic_highway_open_low_support():
    rows = [
        {
            "environment_class": cell.split("__")[0],
            "elevation_band": cell.split("__")[1],
            "cell_id": cell,
            "support_status": "DATA_SUPPORTED",
            "direct_observation_count": "10",
        }
        for cell in CELL_ORDER
    ]
    assert not validate_support_grid(rows)


def test_decision_block_parser_requires_the_complete_gate():
    block = "\n".join(f"{key} = VALUE" for key in REQUIRED_DECISION_KEYS)
    parsed = decision_block_values(block)
    assert set(parsed) == set(REQUIRED_DECISION_KEYS)
    assert parsed["PHASE_1_TRADITIONAL_MODEL_BUILD"] == "VALUE"
