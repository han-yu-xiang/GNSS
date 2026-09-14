from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

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

from scientific_risk_core import ENVIRONMENTS, load_primary_population, weighted_quantile  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\segoeui.ttf")):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def empirical_ecdf(values: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(values, kind="mergesort")
    x = values[order]
    w = weights[order]
    unique, first = np.unique(x, return_index=True)
    cumulative = np.cumsum(w)
    y = np.array([cumulative[np.searchsorted(x, value, side="right") - 1] for value in unique], dtype=float)
    return unique, y / np.sum(w)


def draw_ecdf(quantiles: pd.DataFrame, frame: pd.DataFrame, png_path: Path, pdf_path: Path) -> None:
    width, height = 1500, 820
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = _font(28)
    panel_font = _font(23)
    label_font = _font(17)
    small_font = _font(14)
    colors = {"Urban": (31, 119, 180), "Mountain/Valley": (217, 95, 2)}
    draw.text((width // 2, 25), "Track-balanced empirical CDF of signed relative Doppler", fill="black", anchor="ma", font=title_font)
    for panel_index, environment in enumerate(ENVIRONMENTS):
        left = 105 + panel_index * 690
        top = 105
        right = left + 555
        bottom = top + 540
        group = frame.loc[frame["environment_class"] == environment]
        values = group["doppler_offset_hz"].to_numpy(float)
        weights = group["analysis_weight"].to_numpy(float)
        x, y = empirical_ecdf(values, weights)
        x_min = float(np.min(x) - 10.0)
        x_max = float(np.max(x) + 10.0)
        draw.rectangle((left, top, right, bottom), outline=(45, 45, 45), width=2)
        draw.text((left + 8, top - 38), f"{environment} (n={len(group)})", fill="black", font=panel_font)
        for y_tick in (0.0, 0.25, 0.50, 0.75, 1.0):
            yy = bottom - y_tick * (bottom - top)
            draw.line((left, yy, right, yy), fill=(220, 220, 220), width=1)
            draw.text((left - 10, yy), f"{y_tick:.2f}", fill=(70, 70, 70), anchor="rm", font=small_font)
        for x_tick in np.linspace(x_min, x_max, 5):
            xx = left + (x_tick - x_min) / (x_max - x_min) * (right - left)
            draw.line((xx, top, xx, bottom), fill=(235, 235, 235), width=1)
            draw.text((xx, bottom + 10), f"{x_tick:.0f}", fill=(70, 70, 70), anchor="ma", font=small_font)
        points: list[tuple[float, float]] = []
        previous_x = x[0]
        previous_y = 0.0
        points.append((left + (previous_x - x_min) / (x_max - x_min) * (right - left), bottom))
        for current_x, current_y in zip(x, y):
            xx = left + (current_x - x_min) / (x_max - x_min) * (right - left)
            yy_previous = bottom - previous_y * (bottom - top)
            yy_current = bottom - current_y * (bottom - top)
            points.append((xx, yy_previous))
            points.append((xx, yy_current))
            previous_x, previous_y = current_x, current_y
        points.append((right, bottom - previous_y * (bottom - top)))
        draw.line(points, fill=colors[environment], width=4, joint="curve")
        rows = quantiles.loc[quantiles["environment"] == environment].iloc[0]
        for percentile, marker_color in (("P10", (20, 120, 20)), ("P50", (130, 80, 10)), ("P90", (110, 20, 120))):
            value = float(rows[percentile + "_hz"])
            xx = left + (value - x_min) / (x_max - x_min) * (right - left)
            draw.line((xx, top, xx, bottom), fill=marker_color, width=2)
            draw.text((xx + 5, top + 18 + 22 * (0 if percentile == "P10" else 1 if percentile == "P50" else 2)), f"{percentile}={value:.1f} Hz", fill=marker_color, font=small_font)
        draw.text((left + (right - left) / 2, height - 45), "Signed relative Doppler (Hz)", fill="black", anchor="ma", font=label_font)
    draw.text((8, 380), "Weighted CDF", fill="black", anchor="lm", font=label_font)
    draw.text((width // 2, height - 15), "Each satellite track has unit total weight; P10/P50/P90 are weighted empirical quantiles.", fill=(40, 40, 40), anchor="ms", font=small_font)
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
    rows: list[dict[str, object]] = []
    for environment in ENVIRONMENTS:
        group = primary.loc[primary["environment_class"] == environment]
        values = group["doppler_offset_hz"].to_numpy(float)
        weights = group["analysis_weight"].to_numpy(float)
        rows.append(
            {
                "environment": environment,
                "model": "Track-balanced empirical CDF",
                "observation_count": int(len(group)),
                "track_count": int(group["track_id"].nunique()),
                "scene_count": int(group["scene_id"].nunique()),
                "P10_hz": weighted_quantile(values, weights, 0.10),
                "P50_hz": weighted_quantile(values, weights, 0.50),
                "P90_hz": weighted_quantile(values, weights, 0.90),
                "weighted_mean_hz": float(np.average(values, weights=weights)),
                "weighted_std_hz": float(np.sqrt(np.average((values - np.average(values, weights=weights)) ** 2, weights=weights))),
                "negative_weight_fraction": float(np.sum(weights[values < 0.0]) / np.sum(weights)),
                "nonnegative_weight_fraction": float(np.sum(weights[values >= 0.0]) / np.sum(weights)),
                "minimum_hz": float(np.min(values)),
                "maximum_hz": float(np.max(values)),
                "unique_value_count": int(np.unique(values).size),
                "weight_sum": float(np.sum(weights)),
                "weight_rule": "1 / retained observation count within each satellite track",
            }
        )
    quantiles = pd.DataFrame(rows)
    table_path = table_root / "signed_doppler_empirical_quantiles.csv"
    quantiles.to_csv(table_path, index=False)
    figure_png = figure_root / "signed_doppler_empirical_cdf.png"
    figure_pdf = figure_root / "signed_doppler_empirical_cdf.pdf"
    draw_ecdf(quantiles, primary, figure_png, figure_pdf)
    payload = {
        "model": "Track-balanced empirical distribution for signed relative Doppler",
        "source_population": str(SOURCE_PATH),
        "source_sha256": sha256_file(SOURCE_PATH),
        "cdf_definition": "F_w(x) = sum_i w_i 1(value_i <= x) / sum_i w_i",
        "quantile_definition": "Pq is the smallest observed value with F_w(value) >= q",
        "quantiles": json.loads(quantiles.to_json(orient="records")),
        "execution_boundary": {
            "raw_iq_read": False,
            "matlab_executed": False,
            "sage_executed": False,
            "production_pipeline_executed": False,
            "manuscript_modified": False,
        },
    }
    model_path = model_root / "signed_doppler_empirical_model.json"
    model_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artifacts = [table_path, model_path, figure_png, figure_pdf]
    qa = {
        "status": "PASS_WITH_LIMITATIONS",
        "source_sha256": sha256_file(SOURCE_PATH),
        "primary_rows": int(len(primary)),
        "environment_counts": {environment: int((primary["environment_class"] == environment).sum()) for environment in ENVIRONMENTS},
        "track_weight_unit_mass": bool(np.allclose(primary.groupby("track_id")["analysis_weight"].sum().to_numpy(float), 1.0)),
        "finite_quantiles": bool(np.isfinite(quantiles[["P10_hz", "P50_hz", "P90_hz"]].to_numpy(float)).all()),
        "quantiles_ordered": bool((quantiles["P10_hz"] <= quantiles["P50_hz"]).all() and (quantiles["P50_hz"] <= quantiles["P90_hz"]).all()),
        "artifact_sha256": {str(path.relative_to(REVIEW_ROOT)): sha256_file(path) for path in artifacts},
    }
    qa_path = qa_root / "signed_doppler_empirical_qa.json"
    qa_path.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(quantiles.to_string(index=False))
    print(json.dumps({"status": qa["status"], "table": str(table_path), "figure": str(figure_png)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
