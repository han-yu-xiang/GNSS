"""Run the scoped Gate G supplement on the frozen light Stage2 tables only."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sys
import traceback

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy

import mainline_stage2_wp6 as wp6
import mainline_stage2_wp6_gateg as gateg


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = PROJECT_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1"
FROZEN_DIR = MODEL_ROOT / "wp4_gate_ef_final_20261029T181100"
DEFAULT_FEATURES = FROZEN_DIR / "stage2_cir_pdp_window_features.csv"
DEFAULT_MPCS = FROZEN_DIR / "stage2_mpc_cir_alpha_linkage.csv"
SOURCE_FILES = (
    "scripts/channel_modeling/mainline_stage2_wp3.py",
    "scripts/channel_modeling/mainline_stage2_wp6.py",
    "scripts/channel_modeling/mainline_stage2_wp6_gateg.py",
    "scripts/channel_modeling/run_mainline_stage2_wp6_gateg.py",
    "scripts/channel_modeling/validate_mainline_stage2_wp6_gateg.py",
)
MODELS = ("M0_independent", "M1_count_conditional", "C0_mixed_copula",
          "C1_count_mixed_copula")


class EventLog:
    def __init__(self, path):
        self.path = Path(path)

    def write(self, message):
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        line = f"[{stamp}] {message}"
        print(line, flush=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as target:
            target.write(line + "\n")


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe(value):
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return _safe(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    if value is pd.NA or value is pd.NaT:
        return None
    return value


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(_safe(value), indent=2, ensure_ascii=False,
                                   allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_csv(path, frame):
    serial = frame.copy()
    for column in serial.columns:
        if serial[column].dtype == object:
            serial[column] = serial[column].map(
                lambda item: json.dumps(_safe(item), ensure_ascii=False, separators=(",", ":"))
                if isinstance(item, (dict, list, tuple, np.ndarray)) else item)
    serial.to_csv(path, index=False, encoding="utf-8")


def _new_output_dir(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(exist_ok=False)
    return path.resolve()


def _model_summary(scene_scores, count_scores, randomized):
    rows = []
    for model in MODELS:
        values = pd.to_numeric(scene_scores[f"{model}_scene_macro_log_score"], errors="coerce")
        valid = values[np.isfinite(values)]
        rows.append({"model": model, "scored_scene_n": int(len(valid)),
                     "unscored_scene_n": int(len(values) - len(valid)),
                     "scene_macro_mean_log_score_nats_per_mpc": float(valid.mean()) if len(valid) else np.nan,
                     "scene_median_log_score_nats_per_mpc": float(valid.median()) if len(valid) else np.nan,
                     "scene_min_log_score_nats_per_mpc": float(valid.min()) if len(valid) else np.nan,
                     "scene_max_log_score_nats_per_mpc": float(valid.max()) if len(valid) else np.nan})
    comparison_rows = []
    for column, label in (("M1_minus_M0_nats_per_mpc", "M1−M0"),
                          ("C0_minus_M0_nats_per_mpc", "C0−M0"),
                          ("C1_minus_M1_nats_per_mpc", "C1−M1")):
        values = pd.to_numeric(scene_scores[column], errors="coerce")
        valid = values[np.isfinite(values)]
        comparison_rows.append({
            "comparison": label, "paired_scene_n": int(len(valid)),
            "mean_scene_paired_delta_nats_per_mpc": float(valid.mean()) if len(valid) else np.nan,
            "median_scene_paired_delta_nats_per_mpc": float(valid.median()) if len(valid) else np.nan,
            "min_scene_paired_delta_nats_per_mpc": float(valid.min()) if len(valid) else np.nan,
            "max_scene_paired_delta_nats_per_mpc": float(valid.max()) if len(valid) else np.nan,
            "scenes_positive": int((valid > 0).sum()), "scenes_negative": int((valid < 0).sum()),
            "scenes_tied": int((valid == 0).sum()),
            "mean_paired_window_n": float(pd.to_numeric(
                scene_scores.loc[values.notna(), column.replace("nats_per_mpc", "paired_window_n")],
                errors="coerce").mean()) if len(valid) else 0,
            "interpretation": "DESCRIPTIVE_COMPLETE_SCENE_LOSO; LOSO_TRAINING_SETS_OVERLAP",
        })
    by_count_rows = []
    for count, group in count_scores.groupby("n_mpc", sort=True):
        for column, label in (("M1_minus_M0_nats_per_mpc", "M1−M0"),
                              ("C0_minus_M0_nats_per_mpc", "C0−M0"),
                              ("C1_minus_M1_nats_per_mpc", "C1−M1")):
            values = pd.to_numeric(group[column], errors="coerce")
            valid = values[np.isfinite(values)]
            by_count_rows.append({
                "n_mpc": int(count), "comparison": label, "paired_scene_n": int(len(valid)),
                "mean_scene_paired_delta_nats_per_mpc": float(valid.mean()) if len(valid) else np.nan,
                "median_scene_paired_delta_nats_per_mpc": float(valid.median()) if len(valid) else np.nan,
                "min_scene_paired_delta_nats_per_mpc": float(valid.min()) if len(valid) else np.nan,
                "max_scene_paired_delta_nats_per_mpc": float(valid.max()) if len(valid) else np.nan,
                "scenes_positive": int((valid > 0).sum()), "scenes_negative": int((valid < 0).sum()),
                "scenes_tied": int((valid == 0).sum()),
                "interpretation": "DESCRIPTIVE_COUNT_STRATUM_SCENE_LOSO; SAME_HELDOUT_WINDOWS",
            })
    random_values = pd.to_numeric(randomized.get("copula_minus_independent", pd.Series(dtype=float)),
                                  errors="coerce")
    random_values = random_values[np.isfinite(random_values)]
    random_summary = {
        "successful_draw_n": int(len(random_values)),
        "failed_draw_n": int(len(randomized) - len(random_values)),
        "gain_mean_nats_per_mpc": float(random_values.mean()) if len(random_values) else None,
        "gain_median_nats_per_mpc": float(random_values.median()) if len(random_values) else None,
        "gain_p05_nats_per_mpc": float(random_values.quantile(.05)) if len(random_values) else None,
        "gain_p95_nats_per_mpc": float(random_values.quantile(.95)) if len(random_values) else None,
        "interpretation": "TRAINING_ONLY_RANDOMIZED_PIT_SENSITIVITY; NOT A SEPARATE TEST OR CI",
    }
    return pd.DataFrame(rows), pd.DataFrame(comparison_rows), pd.DataFrame(by_count_rows), random_summary


def _parameter_stability(parameters):
    rows = []
    for record in parameters.to_dict("records"):
        raw = record.get("parameters_json", "{}")
        parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
        for name, value in parsed.items():
            if isinstance(value, (int, float)) and np.isfinite(value):
                rows.append({"model": record["model"], "count_condition": record["count_condition"],
                             "variable": record["variable"], "family": record["family"],
                             "parameter": name, "value": float(value),
                             "outer_held_out_scene_id": record["outer_held_out_scene_id"]})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["model", "count_condition", "variable", "family", "parameter",
                                     "fold_n", "median", "min", "max"])
    return frame.groupby(["model", "count_condition", "variable", "family", "parameter"],
                         dropna=False, sort=True).value.agg(
        fold_n="count", median="median", min="min", max="max").reset_index()


def _parameter_family_frequency(parameters):
    chosen = parameters.loc[parameters.status.eq("PASS")].copy()
    if chosen.empty:
        return pd.DataFrame(columns=["model", "count_condition", "variable", "family", "fold_n"])
    result = chosen.groupby(["model", "count_condition", "variable", "family"],
                            dropna=False, sort=True).size().rename("fold_n").reset_index()
    result["outer_fold_n"] = int(parameters.outer_held_out_scene_id.nunique())
    return result


def _rank_effect_summary(rank_contrasts):
    if rank_contrasts.empty:
        return pd.DataFrame()
    rows = []
    for key, group in rank_contrasts.groupby(["n_mpc", "variable", "from_rank", "to_rank"], sort=True):
        values = pd.to_numeric(group.median_within_window_delta, errors="coerce").dropna()
        rows.append({"n_mpc": int(key[0]), "variable": key[1], "from_rank": int(key[2]),
                     "to_rank": int(key[3]), "scene_n": int(len(values)),
                     "scene_median_delta_median": float(values.median()) if len(values) else np.nan,
                     "scene_median_delta_min": float(values.min()) if len(values) else np.nan,
                     "scene_median_delta_max": float(values.max()) if len(values) else np.nan,
                     "scenes_positive": int((values > 0).sum()), "scenes_negative": int((values < 0).sum()),
                     "scenes_tied": int((values == 0).sum()),
                     "unit": {"excess_delay_chips": "chips", "doppler_offset_hz": "Hz",
                              "relative_power_db": "dB"}[key[1]]})
    return pd.DataFrame(rows)


def _plot_summary(output, count_scores, rank_effects):
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    colors = {1: "#3b6fb6", 2: "#e28e2c", 3: "#4b9b69"}
    for count, group in count_scores.groupby("n_mpc", sort=True):
        x = int(count) + np.linspace(-0.08, 0.08, len(group))
        axes[0].scatter(x, group.M1_minus_M0_nats_per_mpc, s=30, alpha=.8,
                        color=colors[int(count)], label=f"N={count}")
    axes[0].axhline(0, color="black", linewidth=.8)
    axes[0].set_xticks([1, 2, 3])
    axes[0].set_xlabel("MPC count within Stage2-selected window")
    axes[0].set_ylabel("M1 − M0 held-out score (nats / MPC)")
    axes[0].set_title("Count-conditioned margins: scene-held-out paired deltas")
    axes[0].legend(frameon=False)

    variable_order = (("excess_delay_chips", "Delay"), ("doppler_offset_hz", "Doppler"),
                      ("relative_power_db", "Relative power"))
    for index, (variable, label) in enumerate(variable_order):
        subset = rank_effects.loc[rank_effects.variable.eq(variable)]
        axes[1].scatter(np.arange(len(subset)) + index * .04,
                        subset.scene_median_delta_median, s=26, label=label)
    axes[1].axhline(0, color="black", linewidth=.8)
    axes[1].set_xlabel("Count/rank contrast index")
    axes[1].set_ylabel("Median within-window adjacent-rank delta")
    axes[1].set_title("SAGE delay-ranked component contrasts\n(descriptive; not physical path identity)")
    axes[1].legend(frameon=False)
    fig.tight_layout()
    path = Path(output) / "gateg_count_condition_and_rank_diagnostics.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path.name


def _report_text(summary, support, model_summary, comparisons, count_comparisons,
                 family_frequency, rank_effects, random_summary, figure):
    support_lines = [
        "| N MPC | selected windows | scenes | min windows/scene | MPC rows |",
        "|---:|---:|---:|---:|---:|",
    ]
    for count, group in support.groupby("n_mpc", sort=True):
        per_scene = group.selected_mpc_window_n
        support_lines.append(f"| {int(count)} | {int(per_scene.sum())} | {group.scene_id.nunique()} | "
                             f"{int(per_scene.min())} | {int(group.mpc_row_n.sum())} |")
    if len(model_summary):
        model_lines = ["| 模型 | 可评分场景 | 平均场景宏平均分 (nats/MPC) | 中位数 | 范围 |",
                       "|---|---:|---:|---:|---:|"]
        for row in model_summary.to_dict("records"):
            model_lines.append(f"| {row['model']} | {row['scored_scene_n']}/13 | "
                               f"{row['scene_macro_mean_log_score_nats_per_mpc']:.6f} | "
                               f"{row['scene_median_log_score_nats_per_mpc']:.6f} | "
                               f"[{row['scene_min_log_score_nats_per_mpc']:.6f}, "
                               f"{row['scene_max_log_score_nats_per_mpc']:.6f}] |")
    else:
        model_lines = ["场景级模型结果不可用。"]
    comp_lines = ["| 比较 | 配对场景 | 平均配对差 | 中位配对差 | 正/负/平场景 |",
                  "|---|---:|---:|---:|---:|"]
    for row in comparisons.to_dict("records"):
        comp_lines.append(f"| {row['comparison']} | {row['paired_scene_n']}/13 | "
                          f"{row['mean_scene_paired_delta_nats_per_mpc']:.6f} | "
                          f"{row['median_scene_paired_delta_nats_per_mpc']:.6f} | "
                          f"{row['scenes_positive']}/{row['scenes_negative']}/{row['scenes_tied']} |")
    by_count_lines = ["| N | 比较 | 配对场景 | 平均差 | 正/负/平场景 |", "|---:|---|---:|---:|---:|"]
    for row in count_comparisons.to_dict("records"):
        by_count_lines.append(f"| {row['n_mpc']} | {row['comparison']} | {row['paired_scene_n']}/13 | "
                              f"{row['mean_scene_paired_delta_nats_per_mpc']:.6f} | "
                              f"{row['scenes_positive']}/{row['scenes_negative']}/{row['scenes_tied']} |")
    family_top = family_frequency.sort_values(["model", "count_condition", "variable", "fold_n"],
                                               ascending=[True, True, True, False]).groupby(
        ["model", "count_condition", "variable"], sort=True).head(1)
    family_lines = ["| 模型 | N | 属性 | 最常选族 | fold 数/13 |", "|---|---:|---|---|---:|"]
    for row in family_top.to_dict("records"):
        family_lines.append(f"| {row['model']} | {row['count_condition']} | {row['variable']} | "
                            f"{row['family']} | {row['fold_n']}/{row['outer_fold_n']} |")
    rank_lines = ["| N | 属性 | path rank 对比 | 场景中位数差的中位数 | 正/负场景 | 单位 |",
                  "|---:|---|---|---:|---:|---|"]
    for row in rank_effects.to_dict("records"):
        rank_lines.append(f"| {row['n_mpc']} | {row['variable']} | {row['from_rank']}→{row['to_rank']} | "
                          f"{row['scene_median_delta_median']:.6g} | "
                          f"{row['scenes_positive']}/{row['scenes_negative']} | {row['unit']} |")
    return f"""# WP6 Gate G 补充科学审阅：计数条件标记与量化时延依赖

## 执行与范围

本报告只分析冻结的 Stage2 已选窗口轻量 CSV，不读取 MAT/HDF5/raw IQ，不重跑 SAGE、CIR 或 alpha。统计总体为 13 个 scene 中的 7,847 个 Stage2 已选窗口与 8,914 条 MPC；计数及标记推断仅条件于 Stage2 筛选，不将未选 Stage0 窗口补为零 MPC。时延为 0.01-chip 搜索格点，最小格点 0.10 chip，按格点 Voronoi 区间的离散概率质量评分；多普勒和相对功率仍按连续密度评分。

模型均使用完整外层 leave-one-scene-out (LOSO)，边际族选择在每个外层训练集内部再做 scene-LOSO。M0 是不按 MPC 数量条件化的单路径标记边际；M1 按 N=1/2/3 拟合边际；C0/M0 与 C1/M1 比较训练折估计的混合 Gaussian Copula。每个模型比较只在相同的留出窗口上配对，并报告场景宏平均对数评分差。LOSO 折训练集高度重叠，以下是场景外描述性比较，不将 13 折当作 13 次独立重复或据此构造常规置信区间。

## 数据支持

| N MPC | selected windows | scenes | min windows/scene | MPC rows |
|---:|---:|---:|---:|---:|
{chr(10).join(support_lines[2:])}

每个 N 的支持均跨 13 个场景，但最小场景支持分别可由表中看见。N=0 的 Stage2 已选窗口属于既有计数总体，不提供路径标记行，也未被构造成零标记训练记录。

## 场景留出评分

| 模型 | 可评分场景 | 平均场景宏平均分 (nats/MPC) | 中位数 | 范围 |
|---|---:|---:|---:|---:|
{chr(10).join(model_lines[2:])}

| 比较 | 配对场景 | 平均配对差 | 中位配对差 | 正/负/平场景 |
|---|---:|---:|---:|---:|
{chr(10).join(comp_lines[2:])}

按计数分层的配对比较：

{chr(10).join(by_count_lines)}

正差代表右侧模型在该配对评分上更高。该评分是按选中窗口等权、窗口内按 MPC 平均的单路径属性复合评分；它不是多路径窗口的完整联合密度，也不校正不同场景间的抽样不确定性。

## 边际族稳定性与路径顺序诊断

每折只使用对应外层训练场景选边际族；表列每个结构下最常见的选择。折间训练集重叠，频数是稳定性描述，不是独立选择概率。

{chr(10).join(family_lines)}

SAGE 将 Stage2 路径按估计时延排序，`path_id` 是该估计器输出的组件秩，不是经验证的跨窗口物理路径身份。相邻路径秩的场景平衡差异如下；这检验了窗口内可交换/条件 iid 假设的可疑性，但不是因果或反射体解释。

{chr(10).join(rank_lines)}

图表：`{figure}`。随机化 PIT 仅作为训练折敏感性对照，使用固定种子；成功抽样 {random_summary['successful_draw_n']} 次、失败 {random_summary['failed_draw_n']} 次，Copula 相对独立基线增益中位数 {random_summary['gain_median_nats_per_mpc']} nats/MPC（5–95% 抽样分位范围 {random_summary['gain_p05_nats_per_mpc']} 至 {random_summary['gain_p95_nats_per_mpc']}）。这不是检验、置信区间或另一组独立数据。

## 科学边界与 Gate G 建议

本补充区分三层结论：N 条件标记边际的场景外评分、单 MPC 内三个属性依赖的 ties-aware 场景外评分、以及完整有序多路径窗口的联合生成。前两者由表格直接给证据；第三者还需要考虑窗口内路径秩/依赖，不能由逐 MPC 复合评分推出。当前模型也不描述 Stage2 选择机制之外的所有观测窗口，不验证时变复数相位、绝对增益或物理路径连续性。

Gate G 最终建议由独立复核结合配对评分和秩诊断判定；不以总体合并的路径行数制造显著性。若条件边际或 Copula 未显示稳定场景外收益，保留更简单的条件总体模型并明确其生成假设未经验证，不把“拟合可执行”写成“联合生成已验证”。
"""


def run_analysis(features_path, mpc_path, output_dir, randomized_pit_draws=32, seed=20261030):
    output = _new_output_dir(output_dir)
    log = EventLog(output / "execution.log")
    started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {
        "status": "RUNNING", "started_at_utc": started_utc,
        "started_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": " ".join(sys.argv), "process_exit_code": None, "output_dir": str(output),
        "project_root": str(PROJECT_ROOT), "git_head": None,
        "python": sys.version, "platform": platform.platform(), "scipy": scipy.__version__,
        "randomized_pit_draws_per_outer_fold": int(randomized_pit_draws), "seed": int(seed),
        "scope": "frozen light Stage2 CSVs only; no MAT/HDF5/raw IQ or production execution",
        "outer_completed_fold_n": 0, "outer_total_fold_n": 13,
    }
    _write_json(output / "execution_record.json", record)
    try:
        import subprocess
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                                capture_output=True, text=True, check=False)
        record["git_head"] = result.stdout.strip() if result.returncode == 0 else None
        hashes = {name: _sha256(PROJECT_ROOT / name) for name in SOURCE_FILES}
        windows, mpcs, input_manifest = wp6.load_wp6_inputs(features_path, mpc_path)
        frame = gateg.prepare_ranked_marks(mpcs)
        record["inputs"] = input_manifest
        record["source_sha256"] = hashes
        record["population"] = {
            "selected_windows": int(len(windows)), "MPC_rows": int(len(mpcs)),
            "scenes": sorted(windows.scene_id.astype(str).unique().tolist()),
            "window_key": list(wp6.WINDOW_KEY), "MPC_key": list(wp6.MPC_KEY),
            "selected_window_count_histogram": {
                str(k): int((pd.to_numeric(windows.stage2_mpc_count).astype(int) == k).sum())
                for k in wp6.COUNT_SUPPORT},
            "population_scope": "Stage2-selected windows only; conditional on Stage2 selection",
        }
        record["source_sha256"] = hashes
        _write_json(output / "input_code_manifest.json", {
            "input_manifest": input_manifest,
            "frozen_sha256_pins": wp6.EXPECTED_INPUT_HASHES,
            "source_files": hashes,
            "analysis_contract": {
                "delay_grid_chips": gateg.DELAY_GRID_CHIPS,
                "minimum_delay_chips": gateg.MIN_DELAY_CHIPS,
                "M0": "count-independent scene/window-balanced mark marginals",
                "M1": "N=1/2/3 conditional marginals; Stage2-selected windows only",
                "C0_C1": "mixed discrete-delay/continuous Doppler-power Gaussian Copula",
                "evaluation": "nested complete-scene LOSO; paired held-out window scoring",
                "MPC_rows_as_replicates": False,
                "ordered_window_joint_density": False,
            },
        })
        _write_json(output / "population_summary.json", record["population"])
        _write_csv(output / "count_scene_support.csv", gateg.build_count_scene_support(frame))
        log.write(f"Validated frozen input: {len(windows)} selected windows; {len(mpcs)} MPCs; "
                  f"{windows.scene_id.nunique()} scenes; {len(frame)} ranked MPC rows.")

        def progress(index, total, scene):
            record["outer_completed_fold_n"] = int(index)
            record["last_completed_outer_scene"] = str(scene)
            _write_json(output / "execution_record.json", record)
            log.write(f"Completed outer LOSO fold {index}/{total}; held out {scene}.")

        results = gateg.evaluate_nested_loso(frame, randomized_pit_draws=randomized_pit_draws,
                                             seed=seed, progress_callback=progress)
        table_files = {
            "folds.csv": results["folds"],
            "inner_family_selection.csv": results["family_selection"],
            "outer_fold_parameters.csv": results["parameters"],
            "copula_diagnostics.csv": results["copula_diagnostics"],
            "heldout_path_scores.csv": results["path_scores"],
            "heldout_window_scores.csv": results["window_scores"],
            "heldout_scene_scores.csv": results["scene_scores"],
            "heldout_count_scene_scores.csv": results["count_scene_scores"],
            "randomized_pit_sensitivity.csv": results["randomized_pit_sensitivity"],
            "path_rank_scene_summary.csv": results["rank_summary"],
            "path_rank_scene_contrasts.csv": results["rank_contrasts"],
            "count_scene_support.csv": results["count_scene_support"],
        }
        for name, table in table_files.items():
            _write_csv(output / name, table)
        model_summary, comparisons, count_comparisons, random_summary = _model_summary(
            results["scene_scores"], results["count_scene_scores"],
            results["randomized_pit_sensitivity"])
        family_frequency = _parameter_family_frequency(results["parameters"])
        parameter_stability = _parameter_stability(results["parameters"])
        rank_effects = _rank_effect_summary(results["rank_contrasts"])
        _write_csv(output / "model_scene_score_summary.csv", model_summary)
        _write_csv(output / "paired_scene_score_comparisons.csv", comparisons)
        _write_csv(output / "count_stratum_scene_comparisons.csv", count_comparisons)
        _write_csv(output / "selected_family_frequency.csv", family_frequency)
        _write_csv(output / "outer_parameter_fold_stability.csv", parameter_stability)
        _write_csv(output / "path_rank_effect_summary.csv", rank_effects)
        summary = {
            "population": record["population"], "model_scores": model_summary.to_dict("records"),
            "paired_scene_comparisons": comparisons.to_dict("records"),
            "count_stratum_comparisons": count_comparisons.to_dict("records"),
            "randomized_pit_sensitivity": random_summary,
            "path_rank_effects": rank_effects.to_dict("records"),
            "parameter_family_frequency": family_frequency.to_dict("records"),
            "interpretation": "DESCRIPTIVE_SCENE_LOSO; TRAINING_FOLDS_OVERLAP; NO_PATH_ROW_INFERENCE",
        }
        _write_json(output / "gate_g_summary.json", summary)
        figure = _plot_summary(output, results["count_scene_scores"], rank_effects)
        report = _report_text(summary, results["count_scene_support"], model_summary, comparisons,
                              count_comparisons, family_frequency, rank_effects, random_summary, figure)
        (output / "WP6_GateG补充科学审阅报告.md").write_text(report, encoding="utf-8", newline="\n")

        record.update({"status": "ANALYSIS_COMPLETE_VALIDATION_PENDING",
                       "completed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "outer_completed_fold_n": 13,
                       "validation": "NOT_RUN"})
        _write_json(output / "execution_record.json", record)
        log.write(f"Analysis outputs written; independent validation pending: {output}")
        files = sorted(path for path in output.iterdir() if path.is_file() and path.name not in {
            "output_sha256_manifest.json", "execution_record.json"})
        output_hashes = {path.name: _sha256(path) for path in files}
        _write_json(output / "output_sha256_manifest.json", output_hashes)
        record["result_files"] = output_hashes
        record["result_file_count"] = len(output_hashes)
        _write_json(output / "execution_record.json", record)
        return output
    except Exception as exc:
        record.update({"status": "FAILED", "failed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "process_exit_code": 1, "error": f"{type(exc).__name__}: {exc}",
                       "traceback": traceback.format_exc()})
        _write_json(output / "execution_record.json", record)
        log.write(f"FAILED: {type(exc).__name__}: {exc}")
        log.write(traceback.format_exc())
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--mpcs", type=Path, default=DEFAULT_MPCS)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--randomized-pit-draws", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20261030)
    args = parser.parse_args(argv)
    target = args.output_dir
    if target is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = MODEL_ROOT / f"wp6_gateg_supplement_{stamp}"
    if args.randomized_pit_draws < 0:
        parser.error("--randomized-pit-draws must be nonnegative")
    output = run_analysis(args.features, args.mpcs, target, args.randomized_pit_draws, args.seed)
    record_path = output / "execution_record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["process_exit_code"] = 0
    _write_json(record_path, record)
    print(f"GATEG_OUTPUT={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
