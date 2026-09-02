#!/usr/bin/env python3
"""Plot paper-support figures from the Phase-1 derived plot-data table.

Only ``publication_plot_data.csv`` is read.  The script never reads raw IQ,
MATLAB/SAGE output, or the production queue.  It is intentionally a small
renderer: scientific inclusion, support labels, and VTC/journal scope remain
decisions recorded in the closure tables and report.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


DEFAULT_INPUT_REL = Path("dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/publication_plot_data.csv")
DEFAULT_OUTPUT_REL = Path("dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/figures")
PARAMETERS = ("excess_delay_samples", "doppler_offset_hz", "relative_power_db")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def finite(value: Any) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_").lower()


def _load_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - depends on the analysis environment
        raise RuntimeError("matplotlib is required to render closure figures") from exc
    return plt


def render_summary(rows: Iterable[dict[str, str]], output_dir: Path) -> list[Path]:
    plt = _load_matplotlib()
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("plot_id") == "summary" and row.get("metric") == "median":
            grouped[str(row.get("parameter"))].append(row)
    written: list[Path] = []
    for parameter in PARAMETERS:
        selected = grouped.get(parameter, [])
        if not selected:
            continue
        labels = [f"{row.get('scope')}:{row.get('scope_id')}" for row in selected]
        values = [finite(row.get("y")) for row in selected]
        valid = [(label, value) for label, value in zip(labels, values) if value is not None]
        if not valid:
            continue
        figure, axis = plt.subplots(figsize=(11, 5.5))
        axis.bar(range(len(valid)), [value for _, value in valid], color="#356f9f")
        axis.set_xticks(range(len(valid)), [label for label, _ in valid], rotation=70, ha="right", fontsize=7)
        axis.set_ylabel(parameter)
        axis.set_title(f"Phase-1 weighted median summary: {parameter}")
        axis.grid(axis="y", alpha=0.25)
        figure.tight_layout()
        path = output_dir / f"summary_{safe_name(parameter)}.png"
        figure.savefig(path, dpi=220)
        plt.close(figure)
        written.append(path)
    return written


def render_stage3_stage4_cdf(rows: Iterable[dict[str, str]], output_dir: Path) -> list[Path]:
    plt = _load_matplotlib()
    grouped: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        if row.get("plot_id") != "stage3_stage4_cdf" or row.get("scope") != "global":
            continue
        x_value = finite(row.get("x"))
        y_value = finite(row.get("y"))
        if x_value is not None and y_value is not None:
            grouped[(str(row.get("parameter")), str(row.get("population")))].append((x_value, y_value))
    written: list[Path] = []
    for parameter in PARAMETERS:
        figure, axis = plt.subplots(figsize=(7.5, 5.5))
        plotted = False
        for population, color in (("STAGE3_WEIGHTED_PRIMARY", "#356f9f"), ("STAGE4_STRICT_CONFIRMED", "#c45b3c")):
            points = sorted(grouped.get((parameter, population), []))
            if not points:
                continue
            axis.plot([point[0] for point in points], [point[1] for point in points], label=population, color=color, linewidth=1.8)
            plotted = True
        if not plotted:
            plt.close(figure)
            continue
        axis.set_xlabel(parameter)
        axis.set_ylabel("Empirical CDF")
        axis.set_ylim(0.0, 1.0)
        axis.set_title(f"Stage3/Stage4 selection sensitivity: {parameter}")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
        figure.tight_layout()
        path = output_dir / f"stage3_stage4_cdf_{safe_name(parameter)}.png"
        figure.savefig(path, dpi=220)
        plt.close(figure)
        written.append(path)
    return written


def render(input_path: Path, output_dir: Path) -> list[Path]:
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    if not output_dir.is_relative_to(input_path.parent):
        raise ValueError("figure output must remain inside the project closure namespace")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_rows(input_path)
    return render_summary(rows, output_dir) + render_stage3_stage4_cdf(rows, output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    root = args.project_root.resolve()
    input_path = (args.input or root / DEFAULT_INPUT_REL).resolve()
    output_dir = (args.output_dir or root / DEFAULT_OUTPUT_REL).resolve()
    try:
        paths = render(input_path, output_dir)
    except Exception as exc:
        print(f"PHASE1_PLOT_RENDER_REJECTED={exc}")
        return 2
    print(f"PHASE1_PLOT_RENDERED={len(paths)}")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
