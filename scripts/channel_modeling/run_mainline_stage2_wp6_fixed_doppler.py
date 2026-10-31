"""Run fixed-bin Stage2 Doppler Gate G analysis from the pinned light CSVs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import traceback

import numpy as np
import pandas as pd
import scipy

import mainline_stage2_wp6 as wp6
import mainline_stage2_wp6_fixed_doppler as fixed


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = PROJECT_ROOT / "reports/data_consolidation_20261003/mainline_1023_model_v1"
FROZEN_DIR = MODEL_ROOT / "wp4_gate_ef_final_20261029T181100"
DEFAULT_FEATURES = FROZEN_DIR / "stage2_cir_pdp_window_features.csv"
DEFAULT_MPCS = FROZEN_DIR / "stage2_mpc_cir_alpha_linkage.csv"
ANALYSIS_SOURCES = (
    "scripts/channel_modeling/mainline_stage2_wp3.py",
    "scripts/channel_modeling/mainline_stage2_wp6.py",
    "scripts/channel_modeling/mainline_stage2_wp6_gateg.py",
    "scripts/channel_modeling/mainline_stage2_wp6_fixed_doppler.py",
    "scripts/channel_modeling/run_mainline_stage2_wp6_fixed_doppler.py",
)


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
    frame.to_csv(path, index=False, encoding="utf-8", na_rep="")


def _new_output_dir(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(exist_ok=False)
    return path.resolve()


def summarize_scene_scores(scene_scores):
    rows = []
    for width, group in scene_scores.groupby("width_hz", sort=True):
        values = pd.to_numeric(group.C0_minus_M0_nats_per_mpc, errors="coerce")
        valid = values[np.isfinite(values)]
        rows.append({
            "width_hz": float(width), "scored_scene_n": int(len(valid)),
            "unscored_scene_n": int(len(values) - len(valid)),
            "mean_scene_paired_delta_nats_per_mpc": float(valid.mean()) if len(valid) else np.nan,
            "median_scene_paired_delta_nats_per_mpc": float(valid.median()) if len(valid) else np.nan,
            "min_scene_paired_delta_nats_per_mpc": float(valid.min()) if len(valid) else np.nan,
            "max_scene_paired_delta_nats_per_mpc": float(valid.max()) if len(valid) else np.nan,
            "scenes_positive": int((valid > 0).sum()), "scenes_negative": int((valid < 0).sum()),
            "scenes_tied": int((valid == 0).sum()),
            "paired_window_n": int(pd.to_numeric(group.paired_window_n, errors="coerce").sum()),
            "unpaired_window_n": int(pd.to_numeric(group.unpaired_window_n, errors="coerce").sum()),
            "interpretation": "DESCRIPTIVE_COMPLETE_SCENE_LOSO; OUTER_TRAINING_SETS_OVERLAP",
        })
    return pd.DataFrame(rows)


def render_report(population, summary, scene_scores, fold_parameters, diagnostics,
                  input_manifest, source_hashes, started_utc, completed_utc):
    main = summary.loc[summary.width_hz.eq(fixed.DOPPLER_PRIMARY_WIDTH_HZ)]
    sensitivity = summary.loc[summary.width_hz.ne(fixed.DOPPLER_PRIMARY_WIDTH_HZ)]
    lines = [
        "# Gate G 固定分箱 Doppler 与混合 Copula 场景外评分报告",
        "",
        f"- 实际运行：{started_utc} 至 {completed_utc}。",
        f"- 输入：{population['mpc_n']} 条 Stage2 MPC，{population['window_n']} 个已选窗口，"
        f"{population['scene_n']} 个场景；固定输入 SHA 与记录见 `execution_record.json`。",
        "- 评分目标：固定分箱的 Stage2 Doppler 标记分布，条件于 Stage2 已选且含 MPC 的窗口；"
        "不代表原始自适应 SAGE 搜索输出的精确似然。",
        "- 固定箱：0 Hz 为中心，边界 `(k+1/2)w`，半开区间，恰落边界归入右侧箱；5 Hz 为主结果，"
        "10/20 Hz 仅敏感性分析，箱宽未由留出数据选择。",
        "- 混合测度：delay 0.01-chip 单元概率 × Doppler 固定箱概率 × relative-power 连续密度；"
        "Copula 对两个离散 latent 区间联合积分，条件于连续 power PIT。",
        "- 评价：13 场景外层 LOSO；delay/power 候选族和 Doppler Normal/Student-t 均只在每个外层训练集的内层留场景比较；"
        "M0/C0 使用同一外层留出 MPC、窗口和箱宽配对评分。拟合权重为场景平衡、窗口平衡并在窗口内按路径均分的复合权重。",
        "",
        "## 5 Hz 主结果",
        "",
        "| 有效场景 | 未评分场景 | 场景平均 C0−M0 (nats/mark) | 中位数 | 范围 | 正/负/平 | 配对窗口 | 未配对窗口 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if len(main):
        row = main.iloc[0]
        lines.append("| {scored_scene_n} | {unscored_scene_n} | {mean_scene_paired_delta_nats_per_mpc:.6g} | "
                     "{median_scene_paired_delta_nats_per_mpc:.6g} | [{min_scene_paired_delta_nats_per_mpc:.6g}, "
                     "{max_scene_paired_delta_nats_per_mpc:.6g}] | {scenes_positive}/{scenes_negative}/{scenes_tied} | "
                     "{paired_window_n} | {unpaired_window_n} |".format(**row.to_dict()))
    lines += ["", "## 逐场景主结果", "", "| 留出场景 | M0 窗口均分 | C0 窗口均分 | C0−M0 | 配对/未配对窗口 |", "|---|---:|---:|---:|---:|"]
    primary_scenes = scene_scores.loc[scene_scores.width_hz.eq(fixed.DOPPLER_PRIMARY_WIDTH_HZ)]
    for row in primary_scenes.itertuples(index=False):
        lines.append(f"| {row.scene_id} | {row.M0_mean_per_paired_window:.6g} | "
                     f"{row.C0_mean_per_paired_window:.6g} | {row.C0_minus_M0_nats_per_mpc:.6g} | "
                     f"{row.paired_window_n}/{row.unpaired_window_n} |")
    lines += ["", "## 箱宽敏感性", "", "| 箱宽 (Hz) | 有效场景 | 平均 C0−M0 | 中位数 | 正/负场景 | 配对窗口 | 未配对窗口 |",
              "|---:|---:|---:|---:|---:|---:|---:|"]
    for row in sensitivity.itertuples(index=False):
        lines.append(f"| {row.width_hz:g} | {row.scored_scene_n} | {row.mean_scene_paired_delta_nats_per_mpc:.6g} | "
                     f"{row.median_scene_paired_delta_nats_per_mpc:.6g} | "
                     f"{row.scenes_positive}/{row.scenes_negative} | {row.paired_window_n} | {row.unpaired_window_n} |")
    family_rows = []
    for width, group in fold_parameters.loc[fold_parameters.variable.eq("doppler_offset_hz")].groupby("width_hz"):
        counts = group.family.fillna("UNSELECTED").astype(str).value_counts().to_dict()
        family_rows.append(f"{width:g} Hz: " + ", ".join(f"{family} {count}/13" for family, count in sorted(counts.items())))
    lines += ["", "## 训练折与失败情况", "", "外层训练折内 Doppler 族选择频数：" + ("；".join(family_rows) or "无"),
              f"Copula 拟合状态计数：`{diagnostics.status.value_counts(dropna=False).to_dict()}`。",
              "所有失败/未评分行都留在逐折及逐路径表；汇总不把失败折静默计入配对均值。详见 `copula_diagnostics.csv`、"
              "`outer_fold_parameters.csv` 和 `heldout_path_scores.csv`。",
              "", "## 科学解释与 Gate G 边界", "",
              "该分析给出固定 0-centered Doppler bins 下，三个 MPC 标记的训练折内边际与 Gaussian Copula 复合模型的完整场景留出评分。"
              "它不恢复也不近似宣称恢复了历史 SAGE 自适应局部搜索每轮的候选单元；其预测目标仅是本文明确固定后的分箱观测分布。",
              "每个 MPC 行的联合标记得分以等场景/等窗口权重形成复合评分；窗口内多路径不是独立重复。Copula 增益只能说明所选标记评分上的场景外关联线索，"
              "不能证明路径可交换、条件 iid、计数条件标记稳定或有序窗口联合生成器成立。",
              "Stage2 计数模型的 N=1 条件拟合失败、N=2/3 支持有限及路径秩依赖仍未解决；跨窗口 alpha 相位相干、绝对增益标定、"
              "物理反射路径连续性和 SAGE 到 code-domain CIR 的新重构能力不在本次评分对象内。",
              "Gate G 不因评分改善自动通过；综合全部建模目标、样本支持和独立审阅后给出状态建议。",
              "", "## 可复现输入与实现", "",
              f"输入 MPC SHA-256：`{input_manifest['mpc_sha256']}`；Feature SHA-256：`{input_manifest['features_sha256']}`。",
              "实现/输入代码 SHA-256 见 `input_code_manifest.json`；运行命令、Python/SciPy 版本和逐折进度见 `execution_record.json`。",
              "未读取 MAT/HDF5/raw-IQ，也未运行 SAGE/CIR/alpha 或修改冻结科学产物。", ""]
    return "\n".join(lines)


def run_analysis(features_path, mpc_path, output_dir, quadrature_order=24):
    output = _new_output_dir(output_dir)
    started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {
        "status": "RUNNING", "started_at_utc": started_utc,
        "started_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": " ".join(sys.argv), "output_dir": str(output),
        "scope": "pinned light CSV only; no SAGE/CIR/alpha/MAT/HDF5/raw-IQ",
        "git_head": None, "outer_completed_fold_n": 0, "outer_total_fold_n": 13,
        "widths_hz": list(fixed.DOPPLER_WIDTHS_HZ),
        "primary_width_hz": fixed.DOPPLER_PRIMARY_WIDTH_HZ,
        "quadrature_order": int(quadrature_order), "python": sys.version,
        "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__,
        "scipy": scipy.__version__,
    }
    _write_json(output / "execution_record.json", record)
    log_path = output / "execution.log"

    def log(message):
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with log_path.open("a", encoding="utf-8", newline="\n") as target:
            target.write(f"[{stamp}] {message}\n")
        print(f"[{stamp}] {message}", flush=True)

    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, check=False)
        record["git_head"] = head.stdout.strip() if head.returncode == 0 else None
        windows, mpcs, input_manifest = wp6.load_wp6_inputs(features_path, mpc_path)
        source_hashes = {relative: _sha256(PROJECT_ROOT / relative) for relative in ANALYSIS_SOURCES}
        scenes = sorted(windows.scene_id.astype(str).unique().tolist())
        population = {
            "window_n": int(len(windows)), "mpc_n": int(len(mpcs)), "scene_n": len(scenes),
            "run_n": int(mpcs.run_id.nunique()), "scene_ids": scenes,
            "selected_window_count_histogram": {
                str(count): int(pd.to_numeric(windows.stage2_mpc_count).astype(int).eq(count).sum())
                for count in wp6.COUNT_SUPPORT},
            "scope": "frozen Stage2-selected windows only; selected-window count marks are not unconditional Stage0 counts",
        }
        _write_json(output / "input_code_manifest.json", {
            "input_manifest": input_manifest, "frozen_expected_sha256": wp6.EXPECTED_INPUT_HASHES,
            "analysis_source_sha256": source_hashes,
            "score_contract": {
                "target": "fixed-binned Stage2 Doppler conditional on Stage2 selection",
                "doppler_bin_edges_hz": "(k+1/2)*w; zero-centered; half-open; ties to upper bin",
                "widths_hz": list(fixed.DOPPLER_WIDTHS_HZ), "primary_width_hz": 5.0,
                "sensitivity_widths_hz": [10.0, 20.0],
                "delay_measure": "0.01-chip lattice cell probability conditional on 0.10-chip minimum",
                "doppler_measure": "fixed bin probability",
                "power_measure": "continuous density per dB",
                "copula_measure": "joint integration over delay and Doppler latent intervals conditional on continuous power PIT",
                "outer_evaluation": "13-scene LOSO; each held-out scene excluded from all model fitting and inner selection",
                "width_selection": "none; primary and sensitivity widths fixed in advance",
                "path_rows_as_independent_replicates": False,
                "adaptive_sage_exact_likelihood": False,
            },
        })
        _write_json(output / "population_summary.json", population)
        record["inputs"] = input_manifest
        record["analysis_source_sha256"] = source_hashes
        record["population"] = population
        _write_json(output / "execution_record.json", record)
        log(f"Pinned inputs validated: {population['run_n']} runs, {population['scene_n']} scenes, "
            f"{population['window_n']} selected windows, {population['mpc_n']} MPC rows.")

        def progress(index, total, held_scene):
            record["outer_completed_fold_n"] = int(index)
            record["last_completed_outer_scene"] = str(held_scene)
            _write_json(output / "execution_record.json", record)
            log(f"Completed outer scene {index}/{total}: held out {held_scene}.")

        result = fixed.evaluate_fixed_bin_loso(
            mpcs, widths=fixed.DOPPLER_WIDTHS_HZ, expected_scenes=13,
            progress_callback=progress, copula_quadrature_order=int(quadrature_order))
        tables = {
            "folds.csv": result["folds"],
            "inner_family_selection.csv": result["family_selection"],
            "outer_fold_parameters.csv": result["parameters"],
            "copula_diagnostics.csv": result["copula_diagnostics"],
            "heldout_path_scores.csv": result["path_scores"],
            "heldout_window_scores.csv": result["window_scores"],
            "paired_scene_score_comparisons.csv": result["scene_scores"],
        }
        for name, frame in tables.items():
            _write_csv(output / name, frame)
        summary = summarize_scene_scores(result["scene_scores"])
        _write_csv(output / "fixed_bin_scene_summary.csv", summary)
        observed_bins = []
        for width in fixed.DOPPLER_WIDTHS_HZ:
            ids = fixed.doppler_bin_indices(mpcs.doppler_offset_hz.to_numpy(float), width)
            counts = pd.Series(ids).value_counts().sort_index()
            for bin_id, count in counts.items():
                observed_bins.append({"width_hz": width, "bin_index": int(bin_id),
                                      "lower_inclusive_hz": float((bin_id - .5) * width),
                                      "upper_exclusive_hz": float((bin_id + .5) * width),
                                      "observed_mpc_row_n": int(count)})
        _write_csv(output / "observed_doppler_bin_support.csv", pd.DataFrame(observed_bins))
        completed_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
        report = render_report(population, summary, result["scene_scores"], result["parameters"],
                               result["copula_diagnostics"], input_manifest, source_hashes,
                               started_utc, completed_utc)
        (output / "固定分箱Doppler_场景外评分报告.md").write_text(
            report, encoding="utf-8", newline="\n")
        result_hashes = {path.name: _sha256(path) for path in sorted(output.iterdir())
                         if path.is_file() and path.name not in {
                             "execution_record.json", "output_sha256_manifest.json", "execution.log"}}
        _write_json(output / "output_sha256_manifest.json", result_hashes)
        record.update({"status": "ANALYSIS_COMPLETE_VALIDATION_PENDING",
                       "completed_at_utc": completed_utc, "outer_completed_fold_n": 13,
                       "result_files": result_hashes, "result_file_n": len(result_hashes),
                       "validation": "PENDING"})
        _write_json(output / "execution_record.json", record)
        log(f"Analysis complete; independent validation pending; output={output}")
        return output
    except Exception as exc:
        record.update({"status": "FAILED", "failed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})
        _write_json(output / "execution_record.json", record)
        log(f"FAILED: {type(exc).__name__}: {exc}")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--mpcs", type=Path, default=DEFAULT_MPCS)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--quadrature-order", type=int, default=24)
    args = parser.parse_args(argv)
    if args.quadrature_order < 8 or args.quadrature_order > 128:
        parser.error("--quadrature-order must be between 8 and 128")
    target = args.output_dir
    if target is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = MODEL_ROOT / f"wp6_gateg_fixed_doppler_bins_{stamp}"
    output = run_analysis(args.features, args.mpcs, target, args.quadrature_order)
    record = json.loads((output / "execution_record.json").read_text(encoding="utf-8"))
    record["process_exit_code"] = 0
    _write_json(output / "execution_record.json", record)
    print(f"FIXED_DOPPLER_OUTPUT={output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
