"""Generate the frozen VTC figure/table assets without reading raw IQ.

All plots are descriptive visualizations of existing evidence-package CSVs or
the referenced Stage4 path artifact.  This script does not run SAGE, fit a
distribution, infer event-level geometry, or use unconfirmed stages as labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


SCRIPT_VERSION = "vtc-figure-assets-1.3-g15-scientific-label-cleanup"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
EVIDENCE_ROOT = PROJECT_ROOT / "docs" / "vtc2027_spring" / "evidence"
FIGURE_ROOT = PROJECT_ROOT / "docs" / "vtc2027_spring" / "figures"
TABLE_ROOT = PROJECT_ROOT / "docs" / "vtc2027_spring" / "tables"

MEASUREMENT_CSV = EVIDENCE_ROOT / "manuscript_tables" / "measurement_configuration.csv"
SUMMARY_CSV = EVIDENCE_ROOT / "manuscript_tables" / "experimental_evidence_summary.csv"
REPRESENTATIVE_CSV = EVIDENCE_ROOT / "manuscript_figures" / "representative_path_case.csv"
HIERARCHY_CSV = EVIDENCE_ROOT / "manuscript_figures" / "hierarchical_filtering_summary.csv"
PATH_CSV = EVIDENCE_ROOT / "manuscript_figures" / "path_characterization.csv"
ENVIRONMENT_PATH_CSV = EVIDENCE_ROOT / "VTC_ENVIRONMENT_PATH_CANDIDATES.csv"
CENSUS_CSV = EVIDENCE_ROOT / "VTC_ENVIRONMENT_EVIDENCE_CENSUS.csv"
FIGURE1_SVG = FIGURE_ROOT / "figure1_workflow.svg"
FIGURE1_TIKZ = FIGURE_ROOT / "figure1_workflow.tikz"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(value: str) -> float:
    return float(value)


def style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", which="both", direction="out", length=3, width=0.7)
    ax.grid(axis="y", color="0.88", linewidth=0.55)
    ax.set_axisbelow(True)


def save_figure(fig, stem: str) -> list[str]:
    outputs: list[str] = []
    for suffix, kwargs in (("pdf", {}), ("png", {"dpi": 300})):
        path = FIGURE_ROOT / f"{stem}.{suffix}"
        fig.savefig(path, bbox_inches="tight", facecolor="white", **kwargs)
        outputs.append(str(path))
    plt.close(fig)
    return outputs


def generate_figure1() -> list[str]:
    """Render the audited workflow using scientific function labels."""
    labels = [
        ("Raw GPS L1 C/A IQ", "dynamic measurement"),
        ("GNSS tracking", "NAV decoding"),
        ("NAV-aligned", "observation formation"),
        ("Candidate-window", "screening"),
        ("SAGE", "delay--Doppler estimation"),
        ("Temporal", "consistency validation"),
        ("Multi-snapshot", "joint confirmation"),
        ("Path parameters", "delay / Doppler / power"),
    ]
    fig, ax = plt.subplots(figsize=(14.6, 2.05))
    ax.set_xlim(0, len(labels) * 1.78)
    ax.set_ylim(0, 1.0)
    ax.axis("off")
    for index, (title, subtitle) in enumerate(labels):
        x = index * 1.78 + 0.05
        box = FancyBboxPatch(
            (x, 0.29),
            1.43,
            0.38,
            boxstyle="round,pad=0.02,rounding_size=0.025",
            linewidth=0.9,
            edgecolor="0.20",
            facecolor="0.96",
        )
        ax.add_patch(box)
        ax.text(x + 0.715, 0.52, title, ha="center", va="center", fontsize=7.5)
        ax.text(x + 0.715, 0.39, subtitle, ha="center", va="center", fontsize=5.9)
        if index < len(labels) - 1:
            arrow = FancyArrowPatch(
                (x + 1.46, 0.48),
                (x + 1.72, 0.48),
                arrowstyle="-|>",
                mutation_scale=8,
                linewidth=0.8,
                color="0.20",
            )
            ax.add_patch(arrow)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.04)
    return save_figure(fig, "figure1_workflow")


def stage4_rows_for_window(path: Path, window_id: int) -> list[dict[str, str]]:
    rows = read_csv(path)
    return [row for row in rows if int(float(row["center_window_id"])) == window_id]


def audit_relative_doppler(path_rows: list[dict[str, str]]) -> dict[str, object]:
    """Verify that the plotted relative field is the Stage4 offset field."""
    checks: list[dict[str, object]] = []
    for row in path_rows:
        artifact = Path(row["source_artifact_path"])
        candidates = stage4_rows_for_window(artifact, int(row["window_id"]))
        matching = [candidate for candidate in candidates if int(float(candidate["path_id"])) == int(row["path_id"])]
        if len(matching) != 1:
            raise ValueError(f"Could not uniquely match {row['event_id']} to {artifact}")
        stage4 = matching[0]
        plotted = number(row["relative_doppler_hz"])
        offset = number(stage4["doppler_offset_hz"])
        absolute = number(stage4["doppler_hz"])
        if not math.isclose(plotted, offset, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"relative Doppler mismatch for {row['event_id']}")
        checks.append(
            {
                "event_id": row["event_id"],
                "window_id": int(row["window_id"]),
                "path_id": int(row["path_id"]),
                "source_field": "doppler_offset_hz",
                "plotted_relative_doppler_hz": plotted,
                "stage4_doppler_hz": absolute,
                "stage4_doppler_offset_hz": offset,
                "match": True,
                "source_artifact": str(artifact),
            }
        )
    return {"field": "doppler_offset_hz", "all_rows_match": True, "rows": checks}


def generate_figure2(path_rows: list[dict[str, str]], representative_rows: list[dict[str, str]]) -> tuple[list[str], dict[str, object]]:
    primary = next(row for row in representative_rows if row["is_primary_candidate"].lower() == "true")
    window_id = int(primary["window_id"])
    artifact = Path(primary["source_artifact_path"])
    rows = stage4_rows_for_window(artifact, window_id)
    multipath = [row for row in rows if row["is_multipath"] == "1"]
    if len(multipath) != 1:
        raise ValueError("The primary representative must have one confirmed secondary path")

    x = [number(row["excess_delay_samples"]) for row in rows]
    y = [number(row["mean_relative_power_db"]) for row in rows]
    fig, (ax, info) = plt.subplots(1, 2, figsize=(7.0, 3.15), gridspec_kw={"width_ratios": [1.45, 1]})
    ax.axhline(0.0, color="0.75", linewidth=0.7, zorder=0)
    for row, delay, power in zip(rows, x, y):
        confirmed = row["is_multipath"] == "1"
        ax.scatter(
            delay,
            power,
            marker="s" if confirmed else "o",
            s=48 if confirmed else 32,
            facecolor="0.15" if confirmed else "white",
            edgecolor="0.10",
            linewidth=0.9,
            zorder=3,
        )
        ax.annotate(
            "secondary" if confirmed else "direct",
            (delay, power),
            xytext=(4, 5 if confirmed else -12),
            textcoords="offset points",
            fontsize=7.2,
        )
    ax.set_xlabel("Excess delay (samples)")
    ax.set_ylabel("Mean relative power (dB)")
    ax.set_title("Path parameters", fontsize=9)
    ax.set_xlim(-0.12, max(x) + 0.45)
    ax.set_ylim(min(y) - 2.3, 1.1)
    style_axes(ax)
    ax.grid(axis="y", color="0.88", linewidth=0.55)

    info.axis("off")
    info.text(0.0, 0.96, "Representative confirmed case", fontsize=9.2, weight="bold", va="top")
    lines = [
        f"PRN: {artifact.parent.name}",
        f"Selected L: {primary['selected_L']}",
        f"Secondary delay: {primary['delay_samples']} samples",
        f"Relative Doppler: {float(primary['doppler_hz']):.4f} Hz",
        f"Relative power: {float(primary['relative_power_db']):.4f} dB",
        "Jointly confirmed path",
    ]
    info.text(0.0, 0.82, "\n".join(lines), fontsize=7.7, va="top", linespacing=1.40)
    info.text(0.0, 0.08, "Direct/secondary path parameters", fontsize=6.8, va="bottom", color="0.25")
    fig.suptitle("Representative confirmed G25 path", fontsize=10, y=0.99)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.86, bottom=0.18, wspace=0.35)
    audit = {
        "case": "F1023_V80_D0117_P8/G25/ch10",
        "window_id": window_id,
        "source_artifact": str(artifact),
        "visualization": "direct/secondary Stage4 path parameter representation",
        "correlation_curve_generated": False,
        "coherence_displayed": False,
        "coherence_semantics": "Stage4 maximum_coherence is an event/joint-model metric, not a path parameter",
    }
    return save_figure(fig, "figure2_representative_path"), audit


def generate_figure3(hierarchy_rows: list[dict[str, str]]) -> list[str]:
    wanted = [
        ("G05", "Special Reflective", "F1023_V70_D0120_P9__G05__ch10__nav_sage_v2"),
        ("G25", "Highway/Open", "F1023_V80_D0117_P8__G25__ch10__nav_sage_v2"),
        ("G11", "Mountain/Valley", "F1023_v90_D0117_P7__G11__ch6__nav_sage_v2"),
    ]
    by_id = {row["task_id"]: row for row in hierarchy_rows}
    fig, axes = plt.subplots(1, 3, figsize=(8.2, 2.65), sharey=True)
    stage_names = ["Valid\nobs.", "Candidate\nwins.", "Temporal\nsupport", "Joint\nsupport", "Confirmed\npaths"]
    keys = ["Stage0_count", "Stage1_selected", "Stage3_reliable", "Stage4_joint_rows", "confirmed_events"]
    all_values = [int(by_id[task_id][key]) for _, _, task_id in wanted for key in keys]
    common_ylim = max(all_values) * 1.23
    for index, (label, context, task_id) in enumerate(wanted):
        row = by_id[task_id]
        values = [int(row[key]) for key in keys]
        ax = axes[index]
        positions = list(range(len(values)))
        bars = ax.bar(positions, values, color=["0.82", "0.67", "0.52", "0.36", "0.12"], edgecolor="0.15", linewidth=0.65)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value + max(values) * 0.025, str(value), ha="center", va="bottom", fontsize=7.0)
        ax.set_xticks(positions, stage_names, fontsize=5.8)
        ax.set_title(f"{label}\n{context}", fontsize=8.0)
        ax.set_ylim(0, common_ylim)
        ax.set_xlim(-0.5, len(values) - 0.5)
        ax.grid(axis="y", color="0.88", linewidth=0.55)
        style_axes(ax)
    axes[0].set_ylabel("Unique analysis objects (count)")
    fig.suptitle("Hierarchical candidate reduction and path confirmation", fontsize=9.5, y=1.04)
    stage2_text = "Local model-order evaluations (L=1--4; side annotation, not unique candidates): 452  |  448  |  448"
    fig.text(0.5, 0.84, stage2_text, ha="center", fontsize=7.0, color="0.20")
    fig.text(0.5, -0.01, "Local L=1--4 model-order evaluations are evidence annotations, not an additional unique-object stage.", ha="center", fontsize=7.2)
    fig.subplots_adjust(left=0.075, right=0.99, top=0.72, bottom=0.31, wspace=0.18)
    return save_figure(fig, "figure3_hierarchical_confirmation")


def generate_figure4(path_rows: list[dict[str, str]]) -> tuple[list[str], dict[str, object]]:
    groups = ["Special Reflective", "Highway/Open", "Mountain/Valley"]
    markers = {"Special Reflective": "^", "Highway/Open": "o", "Mountain/Valley": "s"}
    group_x = {name: index for index, name in enumerate(groups)}
    panels = [
        ("excess_delay_samples", "Excess delay (samples)"),
        ("relative_power_db", "Relative power (dB)"),
        ("relative_doppler_hz", "Relative Doppler (Hz)"),
    ]
    path_labels: dict[str, str] = {}
    path_number_by_prn: dict[str, int] = {}
    for row in path_rows:
        prn = row["PRN"]
        path_number_by_prn[prn] = path_number_by_prn.get(prn, 0) + 1
        path_labels[row["event_id"]] = f"{prn} path {path_number_by_prn[prn]}"
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.55))
    for ax, (field, ylabel) in zip(axes, panels):
        for row in path_rows:
            group = row["environment"]
            x = group_x[group] + (int(row["window_id"]) % 7 - 3) * 0.018
            ax.scatter(x, number(row[field]), marker=markers[group], s=38, facecolor="white", edgecolor="0.10", linewidth=0.85, zorder=3)
            label_offset = (3, 3)
            if row["environment"] == "Special Reflective":
                label_offset = (3, -12) if row["window_id"] == "493" else (3, 4)
            ax.annotate(path_labels[row["event_id"]], (x, number(row[field])), xytext=label_offset, textcoords="offset points", fontsize=6.0)
        ax.set_xticks(range(len(groups)), ["Special\nReflective", "Highway/\nOpen", "Mountain/\nValley"], fontsize=6.8)
        ax.set_ylabel(ylabel, fontsize=8.0)
        style_axes(ax)
        ax.grid(axis="y", color="0.88", linewidth=0.55)
    legend = [Line2D([0], [0], marker=markers[group], color="0.10", markerfacecolor="white", linestyle="None", markersize=5, label=group) for group in groups]
    axes[-1].legend(handles=legend, loc="best", fontsize=6.4, frameon=False)
    fig.suptitle("Observed parameters of five jointly confirmed paths", fontsize=9.5, y=1.03)
    fig.text(0.5, -0.01, "Each marker represents one confirmed path.", ha="center", fontsize=7.2)
    fig.subplots_adjust(left=0.075, right=0.98, top=0.82, bottom=0.30, wspace=0.35)
    audit = {
        "n_points": len(path_rows),
        "parameters": [field for field, _ in panels],
        "units": {field: ylabel for field, ylabel in panels},
        "doppler_semantic": "relative_doppler_hz equals Stage4 doppler_offset_hz for all plotted rows",
        "distribution_fit": False,
        "geometry_conditioning": False,
    }
    return save_figure(fig, "figure4_path_characteristics"), audit


def generate_figure4_environment(path_rows: list[dict[str, str]]) -> tuple[list[str], dict[str, object]]:
    """Render a bounded environment-wise description of selected confirmed paths."""
    groups = ["Urban", "Mountain/Valley", "Highway/Open", "Special Reflective"]
    group_x = {name: index for index, name in enumerate(groups)}
    panels = [
        ("excess_delay_samples", "Excess delay (samples)"),
        ("relative_power_db", "Relative power (dB)"),
        ("relative_doppler_hz", "Signed relative Doppler (Hz)"),
    ]
    rows = [row for row in path_rows if row.get("inclusion_tier") in {"Tier A", "Tier B"}]
    group_counts = {
        group: sum(row["environment"] == group for row in rows)
        for group in groups
    }
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.75), sharex=True)
    for ax, (field, ylabel) in zip(axes, panels):
        for group in groups:
            values = [number(row[field]) for row in rows if row["environment"] == group]
            if not values:
                continue
            x0 = group_x[group]
            offsets = [((index % 5) - 2) * 0.028 for index in range(len(values))]
            ax.scatter(
                [x0 + offset for offset in offsets],
                values,
                s=22,
                facecolor="white",
                edgecolor="0.10",
                linewidth=0.7,
                zorder=3,
            )
            median = float(statistics.median(values))
            ax.plot([x0 - 0.17, x0 + 0.17], [median, median], color="0.10", linewidth=1.4, zorder=4)
        ax.set_xticks(
            range(len(groups)),
            [
                f"Urban\n(n={group_counts['Urban']})",
                f"Mountain/\nValley\n(n={group_counts['Mountain/Valley']})",
                f"Highway/\nOpen\n(n={group_counts['Highway/Open']})",
                f"Special\nReflective\n(n={group_counts['Special Reflective']})",
            ],
            fontsize=6.2,
        )
        ax.set_ylabel(ylabel, fontsize=7.8)
        style_axes(ax)
        ax.set_xlim(-0.5, len(groups) - 0.5)
    fig.suptitle("Environment-wise confirmed path characteristics", fontsize=9.4, y=1.02)
    fig.subplots_adjust(left=0.075, right=0.985, top=0.82, bottom=0.28, wspace=0.35)
    audit = {
        "n_points": len(rows),
        "groups": groups,
        "parameters": [field for field, _ in panels],
        "tiers": ["Tier A", "Tier B"],
        "source": str(ENVIRONMENT_PATH_CSV),
        "median_marker": True,
        "sample_size_labels": True,
        "internal_annotation_removed": True,
        "doppler_choice": "SIGNED",
        "doppler_semantic": "signed relative Doppler remains the estimated source quantity; sign is not interpreted as an environment effect",
        "distribution_fit": False,
        "regression": False,
        "geometry_conditioning": False,
        "independence_warning": "paths are not independent environment replicates; scene and task counts must be reported separately",
        "coherence_excluded_from_main_figure": True,
        "coherence_path_level_defined": False,
        "event_model_metric_source": "stage4_joint_summary.maximum_coherence",
        "event_model_metric_used_in_environment_figure": False,
    }
    return save_figure(fig, "figure4_environment_path_characteristics"), audit


def write_table_sources() -> list[str]:
    TABLE_ROOT.mkdir(parents=True, exist_ok=True)
    measurement = read_csv(MEASUREMENT_CSV)[0]
    table1_rows = [
        ("Receiver", measurement["receiver"]),
        ("Hardware version", measurement["hardware_version"]),
        ("Antenna", measurement["antenna_type"]),
        ("Polarization", measurement["polarization"]),
        ("Mounting", measurement["mounting"]),
        ("Signal", measurement["signal"]),
        ("Carrier/center frequency", measurement["carrier_frequency"]),
        ("Sampling rate", measurement["sampling_rate"]),
        ("IQ format", measurement["iq_format"]),
        ("Processing chain", measurement["processing_chain"]),
    ]
    table1 = TABLE_ROOT / "table1_measurement_configuration.csv"
    with table1.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["parameter", "value", "source"])
        writer.writerows((parameter, value, str(MEASUREMENT_CSV)) for parameter, value in table1_rows)

    table2 = TABLE_ROOT / "table2_experimental_evidence_summary.csv"
    with table2.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["environment", "independent_scenes", "full_pipeline_tasks", "confirmed_events", "confirmed_paths", "source"])
        census_rows = [
            row for row in read_csv(CENSUS_CSV)
            if row["evidence_tier"] in {"Tier A", "Tier B"} and row["scientific_usable"] == "yes"
        ]
        for environment in ["Urban", "Mountain/Valley", "Highway/Open", "Special Reflective"]:
            rows = [row for row in census_rows if row["environment"] == environment]
            writer.writerow([
                environment,
                len({row["scene"] for row in rows}),
                len(rows),
                sum(int(row["confirmed_events"]) for row in rows),
                sum(int(row["confirmed_paths"]) for row in rows),
                str(CENSUS_CSV),
            ])
    return [str(table1), str(table2)]


def build_manifest(outputs: Iterable[str], audits: dict[str, object], table_outputs: list[str]) -> Path:
    sources = [MEASUREMENT_CSV, SUMMARY_CSV, CENSUS_CSV, REPRESENTATIVE_CSV, HIERARCHY_CSV, ENVIRONMENT_PATH_CSV, FIGURE1_SVG, FIGURE1_TIKZ, Path(__file__)]
    manifest = {
        "schema_version": SCRIPT_VERSION,
        "project_root": str(PROJECT_ROOT),
        "raw_iq_read": False,
        "sage_executed": False,
        "sources": {str(path): sha256(path) for path in sources},
        "outputs": {},
        "audits": audits,
    }
    for path_text in list(outputs) + table_outputs:
        path = Path(path_text)
        manifest["outputs"][str(path)] = sha256(path)
    path = FIGURE_ROOT / "figure_generation_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", choices=("all", "1", "2", "3", "4"), default="all")
    args = parser.parse_args()
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)

    path_rows = read_csv(PATH_CSV)
    representative_rows = read_csv(REPRESENTATIVE_CSV)
    hierarchy_rows = read_csv(HIERARCHY_CSV)
    # Audit the same Tier A+B path source used by the environment-wise figure.
    # This keeps the plotted source and the signed-Doppler provenance check aligned.
    doppler_audit = audit_relative_doppler(read_csv(ENVIRONMENT_PATH_CSV))
    outputs: list[str] = []
    audits: dict[str, object] = {"doppler_audit": doppler_audit}

    if args.figure in ("all", "1"):
        outputs.extend(generate_figure1())
    if args.figure in ("all", "2"):
        generated, audit = generate_figure2(path_rows, representative_rows)
        outputs.extend(generated)
        audits["figure2"] = audit
    if args.figure in ("all", "3"):
        outputs.extend(generate_figure3(hierarchy_rows))
    if args.figure in ("all", "4"):
        environment_rows = read_csv(ENVIRONMENT_PATH_CSV)
        generated, audit = generate_figure4_environment(environment_rows)
        outputs.extend(generated)
        audits["figure4"] = audit

    table_outputs = write_table_sources() if args.figure == "all" else []
    if args.figure != "all":
        audits["requested_figure"] = args.figure
    manifest = build_manifest(outputs, audits, table_outputs)
    print(json.dumps({"outputs": outputs, "tables": table_outputs, "manifest": str(manifest), "doppler_audit": doppler_audit}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
