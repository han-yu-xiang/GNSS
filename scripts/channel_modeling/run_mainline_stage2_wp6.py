"""Reproducible WP6 runner for the SHA-pinned Mainline Stage2 tables."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import mainline_stage2_wp6 as wp6


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = PROJECT_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1"
FROZEN_INPUT_DIR = RESULT_ROOT / "wp4_gate_ef_final_20261029T181100"
DEFAULT_FEATURES = FROZEN_INPUT_DIR / "stage2_cir_pdp_window_features.csv"
DEFAULT_MPCS = FROZEN_INPUT_DIR / "stage2_mpc_cir_alpha_linkage.csv"
CODE_FILES = (
    "scripts/channel_modeling/mainline_stage2_wp6.py",
    "scripts/channel_modeling/mainline_stage2_wp3.py",
    "scripts/channel_modeling/run_mainline_stage2_wp6.py",
    "scripts/channel_modeling/validate_mainline_stage2_wp6.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def _write_json(path: Path, value):
    path.write_text(json.dumps(_json_safe(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def _write_frame(path: Path, frame: pd.DataFrame):
    serial = frame.copy()
    for column in serial.columns:
        if serial[column].dtype == object:
            serial[column] = serial[column].map(
                lambda value: json.dumps(_json_safe(value), ensure_ascii=False, separators=(",", ":"))
                if isinstance(value, (dict, list, tuple, np.ndarray)) else value)
    serial.to_csv(path, index=False, encoding="utf-8")


def create_new_output_directory(target):
    """Create a fresh result directory, refusing all existing destinations."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    return target.resolve()


def build_provenance_manifest(project_root, inputs):
    """Bind exact frozen source bytes and the four code files used by WP6."""
    root = Path(project_root).resolve()
    required = {
        "features_sha256", "mpc_sha256", "features_path", "mpc_path",
        "features_rows", "mpc_rows", "window_key", "mpc_key", "population_scope",
    }
    missing = required.difference(inputs)
    if missing:
        raise ValueError(f"provenance inputs missing required fields: {sorted(missing)}")
    expected = {"features": wp6.FEATURES_SHA256, "mpcs": wp6.MPC_SHA256}
    actual = {"features": str(inputs["features_sha256"]).lower(),
              "mpcs": str(inputs["mpc_sha256"]).lower()}
    for label in expected:
        if actual[label] != expected[label]:
            raise ValueError(f"{label} SHA does not match frozen WP6 pin")
        if len(actual[label]) != 64 or any(char not in "0123456789abcdef" for char in actual[label]):
            raise ValueError(f"{label} SHA is not a 64-character hexadecimal digest")
    code_files = {}
    for relative in CODE_FILES:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"required WP6 source file is missing: {relative}")
        code_files[path.name] = {"relative_path": relative, "path": str(path), "sha256": _sha256(path)}
    return {
        "schema_version": 1,
        "source_inputs": {
            "features": {"path": str(inputs["features_path"]), "sha256": actual["features"],
                         "rows": int(inputs["features_rows"])},
            "mpcs": {"path": str(inputs["mpc_path"]), "sha256": actual["mpcs"],
                     "rows": int(inputs["mpc_rows"])},
        },
        "window_key": list(inputs["window_key"]),
        "mpc_key": list(inputs["mpc_key"]),
        "population_scope": str(inputs["population_scope"]),
        "code_root": str(root),
        "code_files": code_files,
    }


def summarize_population(windows, mpcs):
    """Summarize selected-window denominator and actual path-row inventory."""
    if windows.duplicated(list(wp6.WINDOW_KEY)).any():
        raise ValueError("population summary has duplicate selected-window keys")
    if mpcs.duplicated(list(wp6.MPC_KEY)).any():
        raise ValueError("population summary has duplicate MPC path keys")
    counts = pd.to_numeric(windows["stage2_mpc_count"], errors="coerce")
    if counts.isna().any() or not np.array_equal(counts.to_numpy(), np.rint(counts.to_numpy())):
        raise ValueError("population summary has invalid Stage2 window counts")
    observed = mpcs.groupby(list(wp6.WINDOW_KEY)).size()
    expected = windows.set_index(list(wp6.WINDOW_KEY))["stage2_mpc_count"].astype(int)
    if not observed.reindex(expected.index, fill_value=0).astype(int).equals(expected):
        raise ValueError("Stage2 window counts do not match path-row inventory")
    boundary = wp6._normalise_boundary_flags(windows["pdp_peak_at_grid_boundary"])
    histogram = {str(category): int((counts.astype(int) == category).sum())
                 for category in wp6.COUNT_SUPPORT}
    return {
        "window_n": int(len(windows)),
        "mpc_n": int(len(mpcs)),
        "scene_n": int(windows["scene_id"].nunique()),
        "run_n": int(windows["run_id"].nunique()),
        "zero_mpc_selected_window_n": int((counts == 0).sum()),
        "selected_window_count_histogram": histogram,
        "boundary_peak_window_n": int(boundary.sum()),
        "population_scope": "Stage2-selected windows only; conditional on Stage2 selection",
    }


def summarize_scene_population(windows, mpcs):
    """Retain scene-level selected-window and candidate-path support."""
    window_counts = windows.groupby("scene_id", sort=True).agg(
        run_n=("run_id", "nunique"), window_n=("window_id", "size"),
        boundary_peak_window_n=("pdp_peak_at_grid_boundary", "sum"))
    count_hist = pd.crosstab(windows["scene_id"],
                             pd.to_numeric(windows["stage2_mpc_count"], errors="raise").astype(int))
    for category in wp6.COUNT_SUPPORT:
        if category not in count_hist.columns:
            count_hist[category] = 0
    count_hist = count_hist.rename(columns={category: f"mpc_count_{category}_window_n"
                                             for category in wp6.COUNT_SUPPORT})
    path_counts = mpcs.groupby("scene_id", sort=True).size().rename("mpc_n")
    result = window_counts.join(count_hist, how="left").join(path_counts, how="left").fillna(0)
    result.index.name = "scene_id"
    result = result.reset_index()
    for column in ("run_n", "window_n", "boundary_peak_window_n", "mpc_n",
                   *(f"mpc_count_{category}_window_n" for category in wp6.COUNT_SUPPORT)):
        result[column] = result[column].astype(int)
    return result


def add_copula_score_delta(scene_scores):
    """Derive the paired copula-minus-product score from the returned score columns."""
    required = {"product_marginal_mean_window_log_score",
                "gaussian_copula_mean_window_log_score"}
    missing = required.difference(scene_scores.columns)
    if missing:
        raise ValueError(f"mark scene scores missing required columns: {sorted(missing)}")
    result = scene_scores.copy()
    product = pd.to_numeric(result["product_marginal_mean_window_log_score"], errors="coerce")
    copula = pd.to_numeric(result["gaussian_copula_mean_window_log_score"], errors="coerce")
    result["copula_minus_product_score"] = copula - product
    return result


def build_joint_count_mark_scores(count_window_scores, mark_window_scores, selected_windows):
    """Combine held-out count and product-mark terms over every selected window.

    The resulting factorized joint score assumes the fitted mark law is
    invariant conditional on selected-window MPC count and sums conditional-iid
    path log densities. It is not a Copula score or an independence claim.
    """
    selected = wp6._canonicalize_keys(
        selected_windows, (*wp6.WINDOW_KEY, "scene_id"), "selected windows")
    if selected.duplicated(list(wp6.WINDOW_KEY)).any():
        raise ValueError("selected windows contain duplicate identity")
    required_selected = {"stage2_mpc_count"}
    if not required_selected.issubset(selected.columns):
        raise ValueError("selected windows missing stage2_mpc_count")
    counts = pd.to_numeric(selected.stage2_mpc_count, errors="coerce").to_numpy(float)
    if (not np.isfinite(counts).all() or (counts < 0).any()
            or not np.array_equal(counts, np.rint(counts))):
        raise ValueError("selected window MPC counts must be finite nonnegative integers")
    selected = selected.copy()
    selected["stage2_mpc_count"] = np.rint(counts).astype(int)

    count = wp6._canonicalize_keys(
        count_window_scores, (*wp6.WINDOW_KEY, "scene_id"), "count window scores")
    if count.duplicated(list(wp6.WINDOW_KEY)).any():
        raise ValueError("count window scores contain duplicate identity")
    selected_keys = set(map(tuple, selected[list(wp6.WINDOW_KEY)].itertuples(index=False, name=None)))
    count_keys = set(map(tuple, count[list(wp6.WINDOW_KEY)].itertuples(index=False, name=None)))
    if count_keys != selected_keys:
        raise ValueError("count score identities do not exactly match selected windows")
    selected_by_key = selected.set_index(list(wp6.WINDOW_KEY))
    count_by_key = count.set_index(list(wp6.WINDOW_KEY)).reindex(selected_by_key.index)
    if not count_by_key.scene_id.astype(str).equals(selected_by_key.scene_id.astype(str)):
        raise ValueError("count score scene does not match selected window")
    if "outer_held_out_scene_id" in count_by_key:
        if not count_by_key.outer_held_out_scene_id.astype(str).equals(selected_by_key.scene_id.astype(str)):
            raise ValueError("count score fold does not match selected window scene")
    if "stage2_mpc_count" in count_by_key:
        count_values = pd.to_numeric(count_by_key.stage2_mpc_count, errors="coerce").to_numpy(float)
        if not np.array_equal(count_values, selected_by_key.stage2_mpc_count.to_numpy(dtype=float)):
            raise ValueError("count score changed selected-window MPC count")

    marks = wp6._canonicalize_keys(
        mark_window_scores, (*wp6.WINDOW_KEY, "scene_id"), "mark window scores")
    if marks.duplicated(list(wp6.WINDOW_KEY)).any():
        raise ValueError("mark window scores contain duplicate identity")
    positive = selected.loc[selected.stage2_mpc_count.gt(0)].copy()
    positive_keys = set(map(tuple, positive[list(wp6.WINDOW_KEY)].itertuples(index=False, name=None)))
    mark_keys = set(map(tuple, marks[list(wp6.WINDOW_KEY)].itertuples(index=False, name=None)))
    if mark_keys != positive_keys:
        raise ValueError("mark score identities do not exactly match MPC-bearing selected windows")
    positive_by_key = positive.set_index(list(wp6.WINDOW_KEY))
    marks_by_key = marks.set_index(list(wp6.WINDOW_KEY)).reindex(positive_by_key.index)
    if not marks_by_key.scene_id.astype(str).equals(positive_by_key.scene_id.astype(str)):
        raise ValueError("mark score scene does not match selected window")

    mark_score_column = "product_marginal_log_score"
    if mark_score_column not in marks_by_key:
        raise ValueError("mark scores missing product_marginal_log_score")
    mark_values = pd.to_numeric(marks_by_key[mark_score_column], errors="coerce")
    if "product_score_status" in marks_by_key:
        mark_valid = marks_by_key.product_score_status.astype(str).eq("SCORED")
    else:
        mark_valid = marks_by_key.status.astype(str).isin(
            {"SCORED", "PRODUCT_ONLY_COPULA_UNAVAILABLE"})
    mark_valid &= np.isfinite(mark_values.to_numpy(dtype=float))
    mark_counts = pd.to_numeric(marks_by_key.path_n, errors="coerce") if "path_n" in marks_by_key else None
    if mark_counts is None:
        raise ValueError("mark window scores missing path_n")
    if not np.array_equal(mark_counts.to_numpy(dtype=float),
                          positive_by_key.stage2_mpc_count.to_numpy(dtype=float)):
        raise ValueError("mark score path_n does not match selected-window MPC count")

    rows = []
    for row in selected.itertuples(index=False):
        identity = tuple(str(getattr(row, key)) for key in wp6.WINDOW_KEY)
        count_row = count_by_key.loc[identity]
        count_status = str(count_row.status)
        count_score = pd.to_numeric(pd.Series([count_row.log_score]), errors="coerce").iloc[0]
        count_valid = count_status == "SCORED" and np.isfinite(count_score)
        count_n = int(row.stage2_mpc_count)
        if count_n == 0:
            mark_score, mark_status = 0.0, "EMPTY_MARK_SET"
            valid_mark = True
        else:
            mark_row = marks_by_key.loc[identity]
            mark_score = float(mark_values.loc[identity]) if bool(mark_valid.loc[identity]) else np.nan
            mark_status = "SCORED" if bool(mark_valid.loc[identity]) else "UNSCORABLE_MARK_SCORE"
            valid_mark = bool(mark_valid.loc[identity])
        overall = ("SCORED" if count_valid and valid_mark else
                   "UNSUPPORTED_COUNT_CATEGORY" if not count_valid and count_status == "UNSUPPORTED_COUNT_CATEGORY"
                   else "UNSCORABLE_COUNT_SCORE" if not count_valid else "UNSCORABLE_MARK_SCORE")
        joint = float(count_score + mark_score) if overall == "SCORED" else np.nan
        rows.append({
            "run_id": identity[0], "window_id": identity[1], "scene_id": str(row.scene_id),
            "outer_held_out_scene_id": str(row.scene_id), "stage2_mpc_count": count_n,
            "count_log_score": float(count_score) if count_valid else np.nan,
            "mark_component_log_score": float(mark_score) if valid_mark else np.nan,
            "mark_component_status": mark_status, "joint_product_log_score": joint,
            "status": overall,
        })
    per_window = pd.DataFrame(rows)
    scene_rows = []
    for scene_id, group in per_window.groupby("scene_id", sort=True, dropna=False):
        scored = group.status.eq("SCORED")
        scene_status = "SCORED" if scored.all() else (
            "UNSUPPORTED_COUNT_CATEGORY" if group.status.eq("UNSUPPORTED_COUNT_CATEGORY").any()
            else "UNSCORABLE_COUNT_SCORE" if group.status.eq("UNSCORABLE_COUNT_SCORE").any()
            else "UNSCORABLE_MARK_SCORE")
        scene_rows.append({
            "scene_id": scene_id, "window_n": int(len(group)),
            "scored_window_n": int(scored.sum()), "unscorable_window_n": int((~scored).sum()),
            "status": scene_status,
            "joint_product_mean_log_score": (float(group.joint_product_log_score.mean())
                                              if scored.all() else np.nan),
        })
    return per_window, pd.DataFrame(scene_rows)


def _scene_macro(values, status=None):
    series = pd.to_numeric(values, errors="coerce")
    if status is not None:
        series = series.loc[status.astype(str).eq("SCORED")]
    finite = series[np.isfinite(series.to_numpy(dtype=float))]
    return float(finite.mean()) if not finite.empty else None


def _make_figures(output, summary, count_scene, mark_scene, pdp_scores):
    figures = []
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    categories = [0, 1, 2, 3]
    hist = summary["selected_window_count_histogram"]
    ax.bar([str(item) for item in categories], [hist[str(item)] for item in categories], color="#4169a1")
    ax.set(xlabel="MPC count per Stage2-selected window", ylabel="Selected windows",
           title="MPC count distribution (conditional on Stage2 selection)")
    ax.grid(axis="y", alpha=.25)
    fig.tight_layout()
    path = output / "wp6_selected_window_count.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    figures.append(path.name)

    valid_mark = mark_scene.loc[mark_scene.status.astype(str).eq("SCORED")].copy()
    if not valid_mark.empty:
        fig, ax = plt.subplots(figsize=(9.0, 4.5))
        valid_mark = valid_mark.sort_values("outer_held_out_scene_id")
        x = np.arange(len(valid_mark))
        ax.bar(x, valid_mark["copula_minus_product_score"], color="#497f67")
        ax.axhline(0.0, color="black", linewidth=.8)
        ax.set_xticks(x, valid_mark["outer_held_out_scene_id"], rotation=60, ha="right")
        ax.set(xlabel="Held-out scene", ylabel="Copula minus product score (nats/window)",
               title="Copula score diagnostic only — not a model ranking")
        ax.text(.01, .99,
                "Tied/quantized delay invalidates this continuous point-density comparison.",
                transform=ax.transAxes, ha="left", va="top", fontsize=8,
                bbox={"facecolor": "white", "alpha": .85, "edgecolor": "none"})
        ax.grid(axis="y", alpha=.25)
        fig.tight_layout()
        path = output / "wp6_scene_heldout_copula_delta.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        figures.append(path.name)

    if not pdp_scores.empty:
        scored = pdp_scores.loc[pdp_scores.status.astype(str).eq("SCORED")].copy()
        pivot = scored.pivot_table(index=["outer_held_out_scene_id", "target"],
                                   columns="model", values="rmse", aggfunc="first").reset_index()
        if {"INTERCEPT", "LINEAR"}.issubset(pivot.columns):
            pivot["linear_minus_intercept_rmse"] = pivot["LINEAR"] - pivot["INTERCEPT"]
            labels = pivot["outer_held_out_scene_id"].astype(str) + "\n" + pivot["target"].str.replace(
                "pdp_", "", regex=False).str.replace("_code_delay_samples", "", regex=False)
            fig, ax = plt.subplots(figsize=(11.0, 5.0))
            x = np.arange(len(pivot))
            ax.bar(x, pivot["linear_minus_intercept_rmse"], color="#9a704b")
            ax.axhline(0.0, color="black", linewidth=.8)
            ax.set_xticks(x, labels, rotation=65, ha="right", fontsize=7)
            ax.set_ylabel("Linear minus intercept RMSE (samples)")
            ax.set_title("CIR/PDP window-level held-out scene association")
            ax.grid(axis="y", alpha=.25)
            fig.tight_layout()
            path = output / "wp6_scene_heldout_pdp_rmse_delta.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            figures.append(path.name)
    return figures


def _make_report(summary, count_scene, mark_scene, joint_scene, pdp_scores, final_model, figures):
    count_macro = _scene_macro(count_scene["mean_log_score"], count_scene["status"])
    product_status = (mark_scene.product_score_status.astype(str)
                      if "product_score_status" in mark_scene
                      else mark_scene.status.astype(str))
    copula_status = (mark_scene.copula_score_status.astype(str)
                     if "copula_score_status" in mark_scene
                     else mark_scene.status.astype(str))
    product_rows = mark_scene.loc[product_status.eq("SCORED")]
    copula_rows = mark_scene.loc[copula_status.eq("SCORED")]
    paired_rows = mark_scene.loc[product_status.eq("SCORED") & copula_status.eq("SCORED")]
    product_mean = _scene_macro(product_rows["product_marginal_mean_window_log_score"])
    copula_mean = _scene_macro(copula_rows["gaussian_copula_mean_window_log_score"])
    copula_delta = _scene_macro(paired_rows["copula_minus_product_score"])
    joint_macro = _scene_macro(joint_scene["joint_product_mean_log_score"], joint_scene["status"])
    pdp_rows = []
    for target in sorted(pdp_scores.target.astype(str).unique()):
        selected = pdp_scores.loc[pdp_scores.target.astype(str).eq(target)
                                  & pdp_scores.status.astype(str).eq("SCORED")]
        means = {model: _scene_macro(selected.loc[selected.model.astype(str).eq(model), "rmse"])
                 for model in ("INTERCEPT", "LINEAR")}
        delta = (means["LINEAR"] - means["INTERCEPT"]
                 if means["LINEAR"] is not None and means["INTERCEPT"] is not None else None)
        pdp_rows.append((target, means["INTERCEPT"], means["LINEAR"], delta,
                         int(selected.outer_held_out_scene_id.nunique())))
    family_counts = {}
    params = final_model.get("full_population_refits", {})
    for variable, fit in params.items():
        family_counts[variable] = {"family": fit.get("family"), "status": fit.get("status"),
                                   "parameters": fit.get("parameters", {})}
    lines = [
        "# WP6 Mainline Stage2 联合统计信道模型：真实数据分析报告", "",
        "## 结论摘要", "",
        f"分析总体为 {summary['window_n']:,} 个 Stage2 已选窗口、{summary['mpc_n']:,} 条 MPC，覆盖 {summary['scene_n']} 个 scene / {summary['run_n']} 个 run。按 scene 支持度见 `scene_population_summary.csv`。",
        f"窗口计数分布（条件于 Stage2 选择）为 `{json.dumps(summary['selected_window_count_histogram'], ensure_ascii=False)}`；零 MPC 已选窗口 {summary['zero_mpc_selected_window_n']:,} 个。未入选 Stage0 窗口没有被赋值为零。",
        f"场景宏平均计数留出 log-score：{count_macro if count_macro is not None else '不可计算'} nats/窗口。",
        f"路径边际可评分 scene={len(product_rows)}，连续 Gaussian Copula 可评分 scene={len(copula_rows)}；对应宏平均 score={product_mean} / {copula_mean} nats/MPC 窗口。Copula−独立边际={copula_delta} nats/MPC 窗口，仅作为诊断，时延量化/并列值使当前连续 Copula 点密度不能用于模型排名。LOSO 折训练集重叠，折间差异仅作场景敏感性描述。",
        f"计数与产品边际路径标记的因子化联合留出 score={joint_macro} nats/Stage2 已选窗口，覆盖 {int(joint_scene.status.eq('SCORED').sum())}/{len(joint_scene)} 个 scene。每窗口为计数 log-score 加该窗口路径产品边际 log-score 之和；零 MPC 已选窗口的空标记项为 0。该联合分数采用标记分布不随计数变化及条件 iid/可交换假设，不是 Copula 联合分数，也未验证窗口内路径独立性。",
        "", "## 模型与评价口径", "",
        "主模型先拟合 Stage2 已选窗口的场景平衡经验计数分布；对 MPC 的超额时延、相对多普勒、相对功率使用训练折内嵌套完整 scene 留出选择 WP1/WP3 候选边际族，比较独立边际与场景平衡 Gaussian Copula。场景外联合基线为计数概率乘以窗口内各路径产品边际密度之积；先在每个 selected window 汇总，再按 scene 等权宏平均。该联合基线明确假设给定 Stage2 选中及窗口计数后路径标记可交换且条件 iid，标记分布不再随计数变化；数据未验证这些假设。Copula 连续密度因量化/并列延迟不能用于推断排名，故联合计数—标记数值不包含 Copula 项。路径、重叠窗口和 LOSO 折不被视为独立场景样本。",
        "", "全体数据边际候选及参数仅为描述性最终重拟合，不是场景外证据：", "",
        "```json", json.dumps(_json_safe(family_counts), indent=2, ensure_ascii=False), "```", "",
        "## CIR/PDP 的独立窗口级场景外关联", "",
        f"CIR/PDP 不输入路径标记拟合。SAGE 相对功率加权超额时延矩与 Gate-F 接受的窗口级 PDP 特征分别做完整 scene 留出预测；这是共享数据来源的内部关联，不是独立传播真值、物理 RMS 多径时延扩展或 SAGE 到 CIR 的物理重构。{summary['boundary_peak_window_n']} 个边界峰保留并标记。",
        "", "| PDP 目标 | Intercept 宏平均 RMSE | Linear 宏平均 RMSE | Linear−Intercept | 可评分 scene |", "|---|---:|---:|---:|---:|",
    ]
    for target, base, linear, delta, scene_n in pdp_rows:
        lines.append(f"| {target} | {base} | {linear} | {delta} | {scene_n} |")
    lines.extend([
        "", "## 解释边界", "",
        "- MPC 数量模型只适用于 Stage2 已选窗口总体，不估计未选 Stage0 窗口的多径概率。",
        "- 场景是外层泛化单位；每 scene 内窗口可能重叠，同 scene 的多 run/路径行也不构成独立重复。13 个 scene 对总体精度与复杂结构识别仍有限。",
        "- 经验计数模型不平滑训练折未观测类别；相应留出情形保留为 unsupported，而非伪造概率。边际拟合失败、尾部低支持及不具可评分条件的记录均保留。",
        "- 全量 alpha 针对各自归一化 40 ms 窗口；本模型不使用跨窗口相位相干，也不推断绝对接收增益或连续物理反射体。",
        "- WP4 PDP 与 SAGE 来自共享 Stage0/原始测量链；内部数值/预测关系不能作为独立真值验证。",
        "", "## 可复现结果文件", "",
        "本目录内 `execution_record.json`、`input_code_manifest.json`、逐折/逐窗口 CSV、`final_mark_model.json`、`summary.json` 和图表记录本次计算。独立验收由 `validate_mainline_stage2_wp6.py` 单独完成并保存 `independent_validation.json`。",
        "", "图表：" , "",
    ])
    lines.extend(f"- `{name}`" for name in figures)
    lines.extend(["", "**状态边界：** 本报告是 WP6 模型与场景外实验结果，不自动构成 Gate G PASS；Gate G 仍需独立审阅本次输出、科学适用性及未见场景支持。", ""])
    return "\n".join(lines)


def run_analysis(features_path, mpc_path, output_dir):
    """Run frozen-input WP6 analysis and create a self-contained result package."""
    start = datetime.now(timezone.utc)
    output = create_new_output_directory(output_dir)
    record = {
        "status": "RUNNING", "started_utc": start.isoformat(),
        "command": [sys.executable, *sys.argv], "python": sys.version,
        "platform": platform.platform(), "pid": os.getpid(),
        "features_path": str(Path(features_path).resolve()),
        "mpc_path": str(Path(mpc_path).resolve()),
        "output_path": str(output),
    }
    _write_json(output / "execution_record.json", record)
    try:
        windows, mpcs, input_manifest = wp6.load_wp6_inputs(features_path, mpc_path)
        population = summarize_population(windows, mpcs)
        scene_population = summarize_scene_population(windows, mpcs)
        manifest_inputs = {
            "features_sha256": input_manifest["features_sha256"],
            "mpc_sha256": input_manifest["mpc_sha256"],
            "features_path": input_manifest["features_path"],
            "mpc_path": input_manifest["mpc_path"],
            "features_rows": input_manifest["features_rows"],
            "mpc_rows": input_manifest["mpc_rows"],
            "window_key": input_manifest["window_key"],
            "mpc_key": input_manifest["mpc_key"],
            "population_scope": input_manifest["population_scope"],
        }
        provenance = build_provenance_manifest(PROJECT_ROOT, manifest_inputs)
        _write_json(output / "input_code_manifest.json", provenance)

        count_window_frames, count_scene_frames, probability_frames = [], [], []
        count_folds = []
        all_scenes = sorted(windows.scene_id.astype(str).unique())
        for held_scene in all_scenes:
            test_mask = windows.scene_id.astype(str).eq(held_scene)
            training, test = windows.loc[~test_mask].copy(), windows.loc[test_mask].copy()
            probabilities, per_window, per_scene = wp6.score_count_fold(training, test)
            per_window.insert(0, "outer_held_out_scene_id", held_scene)
            per_scene.insert(0, "outer_held_out_scene_id", held_scene)
            count_window_frames.append(per_window)
            count_scene_frames.append(per_scene)
            probability_frames.append(pd.DataFrame([{
                "outer_held_out_scene_id": held_scene,
                "count_category": int(category), "probability": float(probability),
                "training_scene_ids": sorted(training.scene_id.astype(str).unique().tolist()),
                "training_scene_n": int(training.scene_id.nunique()),
            } for category, probability in probabilities.items()]))
            count_folds.append({"held_out_scene_id": held_scene,
                                "training_scene_ids": sorted(training.scene_id.astype(str).unique().tolist()),
                                "test_window_n": int(len(test)),
                                "fit_status": "PASS"})

        mark_result = wp6.evaluate_nested_mark_loso(mpcs)
        mark_result["scene_scores"] = add_copula_score_delta(mark_result["scene_scores"])
        mark_scenes = sorted(mpcs.scene_id.astype(str).unique())
        if not mark_result["window_scores"].empty:
            mark_result["window_scores"] = mark_result["window_scores"].copy()
            mark_result["window_scores"]["training_scene_ids"] = mark_result["window_scores"]\
                .outer_held_out_scene_id.map(
                    lambda held: json.dumps([scene for scene in mark_scenes if scene != str(held)],
                                            separators=(",", ":")))
        final_mark = wp6.fit_final_mark_model(mpcs)
        window_summaries = wp6.derive_window_delay_summaries(windows, mpcs)
        scene_folds = wp6.make_wp6_scene_folds(windows, mpcs)
        pdp_predictions, pdp_scores = wp6.evaluate_cir_pdp_loso(window_summaries, scene_folds)
        count_windows = pd.concat(count_window_frames, ignore_index=True)
        count_scenes = pd.concat(count_scene_frames, ignore_index=True)
        count_probabilities = pd.concat(probability_frames, ignore_index=True)
        count_fold_frame = pd.DataFrame(count_folds)
        joint_windows, joint_scenes = build_joint_count_mark_scores(
            count_windows, mark_result["window_scores"],
            windows[[*wp6.WINDOW_KEY, "scene_id", "stage2_mpc_count"]])

        outputs = {
            "selected_window_delay_summaries.csv": window_summaries,
            "scene_population_summary.csv": scene_population,
            "count_folds.csv": count_fold_frame,
            "count_probabilities.csv": count_probabilities,
            "count_window_scores.csv": count_windows,
            "count_scene_scores.csv": count_scenes,
            "count_mark_joint_window_scores.csv": joint_windows,
            "count_mark_joint_scene_scores.csv": joint_scenes,
            "mark_folds.csv": mark_result["folds"],
            "mark_parameters.csv": mark_result["parameters"],
            "mark_failures.csv": mark_result["failures"],
            "mark_tails.csv": mark_result["tails"],
            "mark_window_scores.csv": mark_result["window_scores"],
            "mark_scene_scores.csv": mark_result["scene_scores"],
            "mark_copula_diagnostics.csv": mark_result["copula_diagnostics"],
            "mark_inner_family_scores.csv": mark_result["inner_scores"],
            "pdp_window_predictions.csv": pdp_predictions,
            "pdp_scene_scores.csv": pdp_scores,
        }
        for filename, frame in outputs.items():
            _write_frame(output / filename, frame)

        final_selection = {
            "selection": final_mark["selection"],
            "selection_failures": final_mark["selection_failures"].to_dict(orient="records"),
            "full_population_refits": final_mark["full_population_refits"],
            "full_population_copula": final_mark["full_population_copula"],
            "full_population_copula_diagnostics": final_mark["full_population_copula_diagnostics"],
            "full_refit_scope": final_mark["full_refit_scope"],
        }
        _write_json(output / "final_mark_model.json", final_selection)

        valid_mark = mark_result["scene_scores"]
        product_scorable = valid_mark.loc[
            valid_mark.product_score_status.astype(str).eq("SCORED")]
        copula_scorable = valid_mark.loc[
            valid_mark.copula_score_status.astype(str).eq("SCORED")]
        paired_scorable = valid_mark.loc[
            valid_mark.product_score_status.astype(str).eq("SCORED")
            & valid_mark.copula_score_status.astype(str).eq("SCORED")]
        summary = {
            **population,
            "count_scene_macro_mean_log_score": _scene_macro(count_scenes.mean_log_score,
                                                              count_scenes.status),
            "count_scorable_scene_n": int(count_scenes.loc[count_scenes.status.eq("SCORED"),
                                                             "scene_id"].nunique()),
            "mark_scorable_scene_n": int(product_scorable.scene_id.nunique()),
            "product_marginal_scene_macro_score": _scene_macro(
                product_scorable.product_marginal_mean_window_log_score),
            "mark_copula_scorable_scene_n": int(copula_scorable.scene_id.nunique()),
            "copula_scene_macro_score": _scene_macro(
                copula_scorable.gaussian_copula_mean_window_log_score),
            "copula_minus_product_scene_macro_score": _scene_macro(
                paired_scorable.copula_minus_product_score),
            "mark_unscorable_scene_n": int(valid_mark.loc[
                valid_mark.product_score_status.ne("SCORED"), "scene_id"].nunique()),
            "mark_copula_unscorable_scene_n": int(valid_mark.loc[
                valid_mark.copula_score_status.ne("SCORED"), "scene_id"].nunique()),
            "count_mark_joint_scene_macro_mean_log_score": _scene_macro(
                joint_scenes.joint_product_mean_log_score, joint_scenes.status),
            "count_mark_joint_scorable_scene_n": int(joint_scenes.loc[
                joint_scenes.status.eq("SCORED"), "scene_id"].nunique()),
            "count_mark_joint_unscorable_window_n": int(joint_windows.status.ne("SCORED").sum()),
            "mark_failure_record_n": int(len(mark_result["failures"])),
            "mark_low_support_tail_record_n": int(mark_result["tails"].status.astype(str).eq("LOW_SUPPORT").sum())
                if "status" in mark_result["tails"] else 0,
            "pdp_scene_scores": {},
            "limitations": [
                "Stage2-selected population only; no unconditional Stage0 count inference",
                "scene-held-out folds overlap in their training sets; fold spread is descriptive",
                "MPC marks are scored as an exchangeable conditional-iid composite model",
                "CIR/PDP association shares measurement inputs and is not independent propagation truth",
                "no absolute gain or cross-window alpha phase coherence claim",
            ],
        }
        for target, group in pdp_scores.groupby("target", sort=True):
            scored = group.loc[group.status.eq("SCORED")]
            target_summary = {}
            for model_name in ("INTERCEPT", "LINEAR"):
                model_rows = scored.loc[scored.model.eq(model_name)]
                target_summary[model_name] = {
                    "scene_macro_mae": _scene_macro(model_rows.mae),
                    "scene_macro_rmse": _scene_macro(model_rows.rmse),
                    "scored_scene_n": int(model_rows.scene_id.nunique()),
                }
            baseline_rmse = target_summary["INTERCEPT"]["scene_macro_rmse"]
            linear_rmse = target_summary["LINEAR"]["scene_macro_rmse"]
            target_summary["linear_minus_intercept_rmse"] = (
                linear_rmse - baseline_rmse if linear_rmse is not None and baseline_rmse is not None else None)
            summary["pdp_scene_scores"][target] = target_summary

        figure_names = _make_figures(output, summary, count_scenes, mark_result["scene_scores"], pdp_scores)
        summary["figures"] = figure_names
        _write_json(output / "summary.json", summary)
        (output / "WP6_联合统计信道模型科研报告.md").write_text(
            _make_report(summary, count_scenes, mark_result["scene_scores"], joint_scenes, pdp_scores,
                         final_mark, figure_names), encoding="utf-8")
        end = datetime.now(timezone.utc)
        record.update(status="COMPLETE", ended_utc=end.isoformat(),
                      elapsed_seconds=(end - start).total_seconds(),
                      input_manifest=provenance["source_inputs"],
                      output_file_n=len(list(output.iterdir())))
        _write_json(output / "execution_record.json", record)
        print(json.dumps({"status": "COMPLETE", "output": str(output),
                          "window_n": population["window_n"], "mpc_n": population["mpc_n"],
                          "scene_n": population["scene_n"], "summary": summary},
                         indent=2, ensure_ascii=False))
        return output
    except Exception as exc:
        end = datetime.now(timezone.utc)
        record.update(status="FAILED", ended_utc=end.isoformat(),
                      elapsed_seconds=(end - start).total_seconds(),
                      error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        _write_json(output / "execution_record.json", record)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--mpcs", type=Path, default=DEFAULT_MPCS)
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="new output path; default is a UTC-stamped WP6 directory")
    args = parser.parse_args(argv)
    target = args.output_dir
    if target is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = RESULT_ROOT / f"wp6_{timestamp}"
    run_analysis(args.features, args.mpcs, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
