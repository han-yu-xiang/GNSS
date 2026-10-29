# WP6 Mainline Stage2 联合统计信道模型：真实数据分析报告

## 结论摘要

分析总体为 7,847 个 Stage2 已选窗口、8,914 条 MPC，覆盖 13 个 scene / 83 个 run。按 scene 支持度见 `scene_population_summary.csv`。
窗口计数分布（条件于 Stage2 选择）为 `{"0": 3574, "1": 1412, "2": 1081, "3": 1780}`；零 MPC 已选窗口 3,574 个。未入选 Stage0 窗口没有被赋值为零。
场景宏平均计数留出 log-score：-1.297384763093341 nats/窗口。
原连续 Gaussian Copula 评分表记录了独立边际 −16.189600656308468、Copula −16.29107061754208、差值 −0.10146996123360957 nats/窗口；但时延观测只有 128 个不同浮点值（按 0.01 chip 四舍五入为 127 个值）。因此当前 Kendall-τ_b 到连续高斯 Copula 参数的变换及连续密度评分没有处理时延并列/量化，不是合适的混合离散—连续 proper likelihood。该数值仅保留为程序输出诊断，不用于模型排名或声称 Copula 有/无场景外收益。LOSO 折训练集重叠，折间差异也不是独立重复实验。

## 模型与评价口径

本次实现的是一个 Stage2 已选窗口条件下的模块化候选：场景平衡经验计数分布，乘以共享的 MPC 标记边际；完整生成语义额外假定给定计数后路径标记可交换/条件 iid。计数与标记分布是否独立、以及不同计数类别的标记是否同分布，本次没有检验，因此这不是已验证的完整联合生成模型。标记家族在训练折内嵌套 scene 留出选择。边际拟合按场景/窗口平衡权重；外层 joint score 则先对窗口内路径评分求和再对 scene 宏平均；尾部分位数按路径行未经 scene/window 加权计算，三者目标量不同，路径行数也不是独立样本量。Copula 方案因时延量化并列值而不能据当前连续密度分数作有效比较。

全体数据边际候选及参数仅为描述性最终重拟合，不是场景外证据：

```json
{
  "excess_delay_chips": {
    "family": "lognormal",
    "status": "PASS",
    "parameters": {
      "shape": 0.5107560360528611,
      "scale": 0.1929304288963476,
      "loc": 0.0,
      "log_scale": -1.6454256271025645
    }
  },
  "doppler_offset_hz": {
    "family": "student_t",
    "status": "PASS",
    "parameters": {
      "df": 8.172952432234887,
      "loc": 0.7595864546451921,
      "scale": 61.77635324578021
    }
  },
  "relative_power_db": {
    "family": "normal",
    "status": "PASS",
    "parameters": {
      "loc": -8.15757551805896,
      "scale": 6.826866321829932
    }
  }
}
```

相对功率在外层 13 折中 8 折选择 Student-t、5 折选择 Normal；全体重拟合选出的 Normal 只是描述性候选，不能视为稳定唯一家族。优化器失败保留在 `mark_failures.csv`；其中两类的失败信息只记录为 `ABNORMAL:`，不足以诊断根因。

## CIR/PDP 的独立窗口级场景外关联

CIR/PDP 不输入路径标记拟合。SAGE 相对功率加权超额时延矩与 Gate-F 接受的窗口级 PDP 特征分别做完整 scene 留出预测；这是共享数据来源的内部关联，不是独立传播真值、物理 RMS 多径时延扩展或 SAGE 到 CIR 的物理重构。63 个边界峰保留并标记。

| PDP 目标 | Intercept 宏平均 RMSE | Linear 宏平均 RMSE | Linear−Intercept | 可评分 scene |
|---|---:|---:|---:|---:|
| pdp_peak_minus_sage_direct_delay_samples | 4.29815839594569 | 4.290360743420023 | -0.007797652525667331 | 13 |
| pdp_rms_width_code_delay_samples | 2.4853244682137623 | 2.4465553321633235 | -0.038769136050438746 | 13 |

## 解释边界

- MPC 数量模型只适用于 Stage2 已选窗口总体，不估计未选 Stage0 窗口的多径概率。
- 场景是外层泛化单位；每 scene 内窗口可能重叠，同 scene 的多 run/路径行也不构成独立重复。13 个 scene 对总体精度与复杂结构识别仍有限。
- 经验计数模型不平滑训练折未观测类别；相应留出情形保留为 unsupported，而非伪造概率。边际拟合失败、尾部低支持及不具可评分条件的记录均保留。
- 当前计数—标记分解采用标记边际不随窗口 MPC 数量变化的简化假设；没有作为通过的完整联合分布。按计数分组的路径均值可见差异，但路径嵌套于重叠窗口和 scene，不能据此作独立显著性或分层模型结论。
- 由于超额时延量化并列值，当前连续 Gaussian Copula 的 tau 变换和点密度评分不能作为正式预测评分；须在任何 Gate G 依赖前，另行批准并验证适合量化/并列数据的估计与评分。
- 全量 alpha 针对各自归一化 40 ms 窗口；本模型不使用跨窗口相位相干，也不推断绝对接收增益或连续物理反射体。
- WP4 PDP 与 SAGE 来自共享 Stage0/原始测量链；内部数值/预测关系不能作为独立真值验证。

## 可复现结果文件

本地原始 `execution_record.json`、`input_code_manifest.json`、逐折/逐窗口 CSV、`final_mark_model.json`、`summary.json` 和图表记录本次计算。原始 execution/manifests 与 `independent_validation_review_20261029.json` 保留机器本地绝对路径；Git 交付使用路径净化的 `wp6_provenance_git.json` 和 `independent_validation_review_20261029_git.json`，不改写原件。基础独立验收见本地 `independent_validation.json`；增强验证器实际结果、代码审阅与可复核测试证据见上述 Git-safe JSON、`WP6_独立数值验收与模型选型报告.md` 和 `targeted_regression_evidence.md`。增强验证器重算逐 scene PDP 评分/汇总并校验 count 窗口键到源 scene 的绑定，但不独立重拟合所有边际密度，也不使当前 Copula 连续分数适用于并列值。

图表：

- `wp6_selected_window_count.png`
- `wp6_scene_heldout_copula_delta.png`
- `wp6_scene_heldout_pdp_rmse_delta.png`

**状态边界：** WP6 的实现、冻结输入分析、数值核对和独立审阅已完成，整体为 `COMPLETED_WITH_LIMITATIONS` 的候选研究结果；Gate G 仍为 PENDING。可保留 Stage2 条件计数经验分布、Lognormal 时延与 Student-t 多普勒作为候选基线；相对功率 Normal/Student-t 未决，Copula 预测排序无效，计数—标记独立性未验证。不能宣称完整联合生成器已获 Gate G 通过。
