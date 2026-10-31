# WP6 Mainline Stage2 联合统计信道模型：真实数据分析报告

## 结论摘要

分析总体为 7,847 个 Stage2 已选窗口、8,914 条 MPC，覆盖 13 个 scene / 83 个 run。按 scene 支持度见 `scene_population_summary.csv`。
窗口计数分布（条件于 Stage2 选择）为 `{"0": 3574, "1": 1412, "2": 1081, "3": 1780}`；零 MPC 已选窗口 3,574 个。未入选 Stage0 窗口没有被赋值为零。
场景宏平均计数留出 log-score：-1.297384763093341 nats/窗口。
路径边际可评分 scene=13，连续 Gaussian Copula 可评分 scene=13；对应宏平均 score=-16.189600656308468 / -16.29107061754208 nats/MPC 窗口。Copula−独立边际=-0.10146996123360957 nats/MPC 窗口，仅作为诊断，时延量化/并列值使当前连续 Copula 点密度不能用于模型排名。LOSO 折训练集重叠，折间差异仅作场景敏感性描述。
计数与产品边际路径标记的因子化联合留出 score=-10.434218742947845 nats/Stage2 已选窗口，覆盖 13/13 个 scene。每窗口为计数 log-score 加该窗口路径产品边际 log-score 之和；零 MPC 已选窗口的空标记项为 0。该联合分数采用标记分布不随计数变化及条件 iid/可交换假设，不是 Copula 联合分数，也未验证窗口内路径独立性。

## 模型与评价口径

主模型先拟合 Stage2 已选窗口的场景平衡经验计数分布；对 MPC 的超额时延、相对多普勒、相对功率使用训练折内嵌套完整 scene 留出选择 WP1/WP3 候选边际族，比较独立边际与场景平衡 Gaussian Copula。场景外联合基线为计数概率乘以窗口内各路径产品边际密度之积；先在每个 selected window 汇总，再按 scene 等权宏平均。该联合基线明确假设给定 Stage2 选中及窗口计数后路径标记可交换且条件 iid，标记分布不再随计数变化；数据未验证这些假设。Copula 连续密度因量化/并列延迟不能用于推断排名，故联合计数—标记数值不包含 Copula 项。路径、重叠窗口和 LOSO 折不被视为独立场景样本。

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
- 全量 alpha 针对各自归一化 40 ms 窗口；本模型不使用跨窗口相位相干，也不推断绝对接收增益或连续物理反射体。
- WP4 PDP 与 SAGE 来自共享 Stage0/原始测量链；内部数值/预测关系不能作为独立真值验证。

## 可复现结果文件

本机执行记录为 `execution_record.json`、`input_code_manifest.json` 和 `independent_validation.json`；适合共享与 Git 的相对路径 provenance/validation 摘要为 `wp6_provenance_git.json` 与 `independent_validation_git.json`，其 SHA 和命令记录在 `targeted_regression_evidence.md`。逐折/逐窗口 CSV、`final_mark_model.json`、`summary.json` 和图表记录本次分析结果。

图表：

- `wp6_selected_window_count.png`
- `wp6_scene_heldout_copula_delta.png`
- `wp6_scene_heldout_pdp_rmse_delta.png`

**状态边界：** 本报告是 WP6 模型与场景外实验结果，不自动构成 Gate G PASS；Gate G 仍需独立审阅本次输出、科学适用性及未见场景支持。
