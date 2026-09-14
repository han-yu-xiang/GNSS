from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
REVIEW_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = Path(r"E:\GNSS_Multipath_Project")
SOURCE_PATH = (
    PROJECT_ROOT
    / "docs/vtc2027_spring/supplemental_data_outputs/"
    "urban_mountain_stage3_elevation_model_review_v3_conditional_gmm/"
    "population/gmm_feature_population.csv"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scientific_risk_core import ENVIRONMENTS, evaluate_gmm_complexity, load_primary_population  # noqa: E402


VARIABLES = (
    ("doppler_offset_hz", "Signed relative Doppler (Hz)"),
    ("relative_power_db", "Relative path power (dB)"),
)
COMPONENTS = (1, 2, 3)
SEEDS = (2026091301, 2026091302, 2026091303)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def draw_complexity_figure(summary: pd.DataFrame, png_path: Path, pdf_path: Path) -> None:
    width, height = 1500, 900
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(28)
    panel_font = _font(22)
    label_font = _font(17)
    small_font = _font(14)
    draw.text((width // 2, 24), "Scene-held-out GMM complexity comparison", fill="black", anchor="ma", font=title_font)
    colors = {"Urban": (31, 119, 180), "Mountain/Valley": (217, 95, 2)}
    for panel_index, (environment, variable_label) in enumerate(
        ((environment, label) for environment in ENVIRONMENTS for _, label in VARIABLES)
    ):
        variable = VARIABLES[panel_index % len(VARIABLES)][0]
        left = 100 + (panel_index % 2) * 690
        top = 100 + (panel_index // 2) * 370
        right = left + 560
        bottom = top + 260
        panel = summary[(summary["environment"] == environment) & (summary["value"] == variable)].sort_values("components")
        values = panel["scene_loso_nlpd_mean"].to_numpy(float)
        errors = panel["scene_loso_nlpd_se"].to_numpy(float)
        y_min = max(0.0, float(np.min(values - errors)) * 0.92)
        y_max = float(np.max(values + errors)) * 1.12
        if y_max <= y_min:
            y_max = y_min + 1.0
        draw.rectangle((left, top, right, bottom), outline=(40, 40, 40), width=2)
        draw.text((left + 10, top - 38), f"{environment}: {variable_label}", fill="black", font=panel_font)
        for tick in np.linspace(y_min, y_max, 4):
            y = bottom - (tick - y_min) / (y_max - y_min) * (bottom - top)
            draw.line((left, y, right, y), fill=(220, 220, 220), width=1)
            draw.text((left - 10, y), f"{tick:.2f}", fill=(70, 70, 70), anchor="rm", font=small_font)
        x_positions = np.linspace(left + 100, right - 100, len(panel))
        bar_width = 70
        for x, (_, row), err in zip(x_positions, panel.iterrows(), errors):
            value = float(row["scene_loso_nlpd_mean"])
            y_value = bottom - (value - y_min) / (y_max - y_min) * (bottom - top)
            draw.rectangle((x - bar_width / 2, y_value, x + bar_width / 2, bottom), fill=colors[environment])
            y_low = bottom - (value - err - y_min) / (y_max - y_min) * (bottom - top)
            y_high = bottom - (value + err - y_min) / (y_max - y_min) * (bottom - top)
            draw.line((x, y_low, x, y_high), fill=(20, 20, 20), width=3)
            draw.line((x - 10, y_low, x + 10, y_low), fill=(20, 20, 20), width=3)
            draw.line((x - 10, y_high, x + 10, y_high), fill=(20, 20, 20), width=3)
            draw.text((x, bottom + 18), f"K={int(row['components'])}", fill="black", anchor="ma", font=label_font)
            if row["selection_status"] == "SELECTED_ONE_SE_RULE":
                draw.text((x, top + 8), "selected", fill=(20, 80, 20), anchor="ma", font=small_font)
        draw.text((left - 64, (top + bottom) // 2), "LOSO NLPD", fill="black", anchor="mm", font=label_font)
    draw.text(
        (width // 2, height - 28),
        "Bars: mean scene-held-out negative log predictive density; whiskers: ±1 standard error. Lower is better.",
        fill=(40, 40, 40),
        anchor="ms",
        font=small_font,
    )
    png_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(png_path, format="PNG")
    image.save(pdf_path, format="PDF", resolution=150.0)


def main() -> int:
    table_root = REVIEW_ROOT / "tables"
    model_root = REVIEW_ROOT / "model"
    figure_root = REVIEW_ROOT / "figures"
    qa_root = REVIEW_ROOT / "qa"
    for directory in (table_root, model_root, figure_root, qa_root):
        directory.mkdir(parents=True, exist_ok=True)

    primary = load_primary_population(SOURCE_PATH)
    summary_rows: list[pd.DataFrame] = []
    fold_rows: list[pd.DataFrame] = []
    selections: dict[str, Any] = {}
    for environment in ENVIRONMENTS:
        frame = primary.loc[primary["environment_class"].astype(str) == environment].copy()
        selections[environment] = {}
        for variable, _ in VARIABLES:
            summary, folds = evaluate_gmm_complexity(frame, variable, COMPONENTS, SEEDS)
            summary.insert(0, "environment", environment)
            folds.insert(0, "environment", environment)
            summary_rows.append(summary)
            fold_rows.append(folds)
            selected = summary.loc[summary["selection_status"] == "SELECTED_ONE_SE_RULE"].iloc[0]
            selections[environment][variable] = {
                "selected_components": int(selected["components"]),
                "best_mean_components": int(selected["best_mean_components"]),
                "one_se_threshold": float(selected["one_se_threshold"]),
                "selected_scene_loso_nlpd_mean": float(selected["scene_loso_nlpd_mean"]),
                "selected_maximum_weighted_cdf_deviation": float(selected["maximum_weighted_cdf_deviation"]),
            }
    summary_frame = pd.concat(summary_rows, ignore_index=True)
    fold_frame = pd.concat(fold_rows, ignore_index=True)
    summary_path = table_root / "gmm_complexity_summary.csv"
    folds_path = table_root / "gmm_loso_folds.csv"
    summary_frame.to_csv(summary_path, index=False)
    fold_frame.to_csv(folds_path, index=False)
    figure_png = figure_root / "gmm_complexity_scene_loso_nlpd.png"
    figure_pdf = figure_root / "gmm_complexity_scene_loso_nlpd.pdf"
    draw_complexity_figure(summary_frame, figure_png, figure_pdf)

    model_payload = {
        "experiment": "K=1/2/3 weighted one-dimensional Gaussian-mixture scene-LOSO comparison",
        "source_population": str(SOURCE_PATH),
        "source_sha256": sha256_file(SOURCE_PATH),
        "population": {
            "primary_rows": int(len(primary)),
            "environment_counts": {environment: int((primary["environment_class"] == environment).sum()) for environment in ENVIRONMENTS},
            "track_count": int(primary["track_id"].nunique()),
            "scene_count": int(primary["scene_id"].nunique()),
            "outlier_rows_removed": 0,
        },
        "weight_rule": "Within each fit or scene fold, each track has total analysis weight one.",
        "complexity_rule": "Select the smallest K whose mean scene-held-out NLPD is within one standard error of the best mean.",
        "components_tested": list(COMPONENTS),
        "seeds": list(SEEDS),
        "selections": selections,
        "execution_boundary": {
            "raw_iq_read": False,
            "matlab_executed": False,
            "sage_executed": False,
            "production_pipeline_executed": False,
            "source_population_modified": False,
            "manuscript_modified": False,
        },
    }
    model_path = model_root / "gmm_complexity_results.json"
    model_path.write_text(json.dumps(model_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artifact_paths = [summary_path, folds_path, model_path, figure_png, figure_pdf]
    manifest = {
        "status": "COMPLETED_REVIEW_ONLY",
        "source_sha256": sha256_file(SOURCE_PATH),
        "artifact_sha256": {str(path.relative_to(REVIEW_ROOT)): sha256_file(path) for path in artifact_paths},
        "artifact_paths": [str(path.relative_to(REVIEW_ROOT)) for path in artifact_paths],
    }
    manifest_path = qa_root / "execution_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMPLETED_REVIEW_ONLY", "summary": str(summary_path), "folds": str(folds_path), "selections": selections}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
