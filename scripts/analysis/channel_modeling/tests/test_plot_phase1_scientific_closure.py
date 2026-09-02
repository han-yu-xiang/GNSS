import sys
from pathlib import Path


HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

from plot_phase1_scientific_closure import finite, safe_name  # noqa: E402


def test_plot_renderer_sanitizes_names_and_rejects_nonfinite_points():
    assert safe_name("Highway/Open–LOW") == "highway_open_low"
    assert finite("1.25") == 1.25
    assert finite("NaN") is None
