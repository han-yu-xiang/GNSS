# WP3 独立科学审阅与模型选型报告

- 审阅时点：2026-10-28（Asia/Shanghai）
- 结论：`PASS_WITH_LIMITATIONS`
- 审阅对象：WP3 最终有界分析包 `wp3_20261028T140100Z/`
- 本审阅不重跑拟合、不改写 WP3 原结果、不通过 Gate G，不完成 WP6；Task 5 生产未被干预。

## 1. 总结与建议

WP3 的数据身份、完整场景留出、配对评分、结果哈希和定向测试证据足以支持**范围受限的探索性科学结果**。它不支持宣称 Urban 与 Mountain/Valley 必须采用不同的最终参数分布，也不支持把仰角 M2 作为已验证的普适预测模型。

建议在后续 Mainline Stage2 参数模型中保留一个全局 M0 基线，各参数分开选择分布族；M1 不作为当前最终预测结构；M2 仅把 GSV 实测仰角—相对功率关系留作探索性候选。全局模型参数如下，均是对九个核心场景全数据拟合的场景/窗口平衡伪似然估计，不是独立场景总体参数的无偏推断。参数分布拟合使用 6,335 条 MPC，来自 2,899 个 MPC-bearing Stage2 窗口；没有 MPC 的已选窗口不作为零值分布观测，仍保留在单独的窗口支持/计数总体中：

| 参数 | 建议的核心 M0 基线 | 九场景全数据拟合参数 | 取舍 |
|---|---|---|---|
| 超额时延（chips） | Lognormal，`loc=0` | `shape σ=0.4659688`，`scale=exp(μ)=0.1914930`，即 `ln(τ) ~ Normal(ln 0.1914930, 0.4659688²)` | 唯一呈现稳定候选排名的参数族：完整场景 LOSO 9/9 排名第一。M1、M2 未改善该基线。 |
| 有符号相对多普勒（Hz） | Student-t | `ν=8.97753`，`loc=−0.4420 Hz`，`scale=62.9264 Hz` | Student-t 在核心 LOSO 6/9 排名第一，核心等场景宏 log score 为 −5.71154；Normal 为 −5.75120，仍是重要敏感性候选。WP1 13 场景中 Normal 排名第一 6/13、Student-t 5/13，故不宣称唯一普适胜者。 |
| 相对功率（dB，相对量） | Student-t 主候选；Normal 必须作为近似等价敏感性结果保留 | `ν=7.72049`，`loc=−8.90584 dB`，`scale=5.97587 dB` | 核心宏 score 最好但只比 Normal 高约 `0.01385` nats/window；两族均 4/9 折排名第一。WP1 的 Student-t 为 8/13 折第一、WP3 同方向但差异很小，因此暂用 Student-t 作工作基线，不称其已被明确胜出。尺度参数是 Student-t scale，不是标准差；相对 dB 不是绝对接收功率。 |

这三个是 WP3 **九个核心场景**的拟合值。WP1 的 13 场景全局分析仍是 Mainline 全候选总体基线；不得以本表九场景参数替换或与 WP1/WP2 分数直接相减。

## 2. 证据与计算复核

审阅了正式报告、全数据参数、LOSO fold 与 score、候选排名、配对差、尾部诊断、条件支持/来源表、独立验证记录、执行/测试日志和 M0/M1/M2 实现；并核对 WP1 V0 与 WP2 全局候选结果。主要路径：

- 正式分析：`reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_20261028T140100Z/WP3_正式科研报告.md`
- 全模型参数：同目录 `full_data_model_parameters.csv`
- 逐折分数与配对：同目录 `loso_fold_scores.csv`、`loso_paired_deltas.csv`、`loso_paired_delta_macro.csv`
- 仰角和环境支持：同目录 `condition_support_by_scene_source.csv`、`descriptive_by_environment.csv`
- 尾部：同目录 `loso_tail_diagnostics.csv`
- 实现：`scripts/channel_modeling/mainline_stage2_wp3.py`、`scripts/channel_modeling/run_mainline_stage2_wp3.py`
- 输入基线：WP1 `reports/data_consolidation_20261003/mainline_1023_model_v1/v0_20261024T132210Z/v0_model_report.md`；WP2 `reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_20261025T074332Z/wp2_report.md`

审阅直接从保存的 891 个 score rows、810 个 paired rows 复算：测试身份哈希不一致 `0`；配对 log-score 差与 `score(first model) − score(second model)` 不一致 `0`；留出 scene 出现在对应训练 scene 列表中的记录 `0`。M0/M1/M2 的同范围比较以精确相同测试身份配对；仰角 M2 与 M0/M1 的对比限定在 `GSV_MEASURED` 子总体，未拿不同缺失机制下的总体分数硬比。最终包独立 validator 为 `PASS`、无 findings；原有针对性测试记录为 18/18 PASS，Python 3.12，退出码 0。此次未重复测试或拟合。

**差值符号说明：** 实现的 `M1-M0` 是 `score(M1)−score(M0)`，正值有利于第一个列出的模型；`M2-M1` 同理。原正式报告把该差值文字称作“右侧模型减左侧模型”，容易被按数学表达式的右操作数反读。审阅已按代码、列名和逐折 score 核对：CSV 数值正确，无需局部重算；论文引用应使用上面明确的公式。

## 3. Urban 与 Mountain/Valley：存在样本差异，但不足以采用两套最终参数

核心支持为 Urban 6 场景、2,927 个 Stage2 选中窗口、3,698 MPC；Mountain/Valley 3 场景、1,974 窗口、2,637 MPC。按场景/窗口平衡的窗口中位数汇总，超额时延的环境中位数约 `0.20` 与 `0.21 chips`；多普勒约 `−1.376` 与 `−0.336 Hz`，但场景范围很宽；相对功率约 `−10.400` 与 `−11.026 dB`。这些描述性偏移有显著场景异质，不能把大量 MPC 行当成独立重复。

全核心数据 M1 点估计显示差异（每个参数使用全核心 M0 中宏 score 最优的候选族，仅作描述）：

| 候选族 | Urban | Mountain/Valley |
|---|---|---|
| 时延 Lognormal | `σ=0.44930, scale=0.18649 chips` | `σ=0.49338, scale=0.20191 chips` |
| 多普勒 Student-t | `ν=15.54, loc=−2.256 Hz, scale=58.05 Hz` | `ν=7.79, loc=3.854 Hz, scale=75.52 Hz` |
| 相对功率 Student-t | `ν=92.83, loc=−8.564 dB, scale=6.138 dB` | `ν=3.10, loc=−9.936 dB, scale=5.433 dB` |

然而 M1−M0 的核心等场景配对宏 score 差对候选族全部为负：时延 `−0.0837…−0.0242`，多普勒 `−0.0459…−0.0122`，相对功率 `−0.1519…−0.0166`（最后一项的候选拟合只覆盖 8–9 个可配对场景）。这表示在现有指标和配对场景下，环境拆分并未改善综合场景外预测；分环境结果也不一致，Mountain/Valley 只有三场景。因此环境点估计差异可作为样本描述，不能据此称两种环境“需要”不同参数分布或宣称 Mountain 参数已稳定估计。

## 4. 仰角 M2：相对功率有探索信号，但不是已验证的普适条件模型

核心场景 Stage2 窗口中，GSV 实测仰角覆盖 3,478/4,901（71.0%）；在核心 MPC 行中覆盖 4,948/6,335。M2 的实际拟合输入为 4,948 MPC、2,297 个有 MPC 的窗口、九个核心场景。其余仰角必须分开：GGA 椭球高推算 206 窗口/163 MPC；零高度假设推算 701/787；仍缺失 516/437。来源不合并、不填补。GSV 虽覆盖九个核心场景，角度范围及覆盖密度仍不均（总体约 16°–83°；一个 Urban 场景仅约 22°–39°），故来源/可观测性选择不能视为随机缺失。

| 参数 | GSV M2−M0 核心候选族宏差 | GSV M2−M1 核心候选族宏差 | 审阅 |
|---|---:|---:|---|
| 时延 | 所有候选族负，约 `−0.8860…−0.0448` | `−0.0085…+0.0996`，仅 Weibull 为正；Lognormal 为负 | 不保留仰角时延模型。 |
| 多普勒 | 所有候选族负，约 `−0.1131…−0.0082` | 所有候选族负，约 `−0.0220…−0.0005` | 不保留仰角多普勒模型；Student-t M2 有 2/9 折优化失败。 |
| 相对功率 | 混合：Laplace `+0.0120`、Normal `−0.1247`、Student-t `−0.0231` | 三族汇总均为正，约 `+0.0115…+0.0800`；但 Student-t 在 1/9 折优化失败 | M2 相对 M1 有样本内预测信号，但未稳定超过更简洁 M0；分环境后 Urban 与 Mountain/Valley 不同，不作为最终模型。 |

GSV M2 的相对功率 Student-t 全数据参数在 45° 的环境位置约为 Urban `−7.775 dB`、Mountain/Valley `−8.824 dB`，共享 `ν≈9.566`，仰角斜率 `β≈−1.009 dB/10°`；LOSO 斜率均值/中位汇总为负但训练集重叠、fold 参数并非独立证据。该斜率是 Stage2/GSV 可观测子集内的关联，不能解释为仰角导致功率变化；不能外推至缺失角度 MPC、全部 Stage0 窗口或不同观测源。

## 5. 论文结论边界与最终保留方案

可以作为论文**有界探索性结果**报告：

1. 在已选 Stage2 核心总体中，Lognormal 超额时延在 9 个 complete-scene LOSO 折中稳定排名第一；多普勒 Student-t 在 6/9 折排名第一；相对功率 Student-t 与 Normal 各 4/9。此排名只在本候选集合、成功拟合及本评价口径中成立。
2. 环境点估计和 GSV 相对功率负斜率可以作为假设生成型结果展示；M1/M2 没有证明对 M0 有普遍、跨环境场景外优势。
3. 对尾部只能报告诊断：2,268 条中 279 条拟合不可用，579 条名义目标尾部 path rows 少于 10；行数不是有效独立样本量，不能称整体尾部校准通过。

不应写成确认性结论：Urban/Mountain 必须使用不同分布；仰角具有已验证因果效应；M2 普遍提高场景外预测；当前九场景参数是全 13 场景真值；路径行/LOSO 折独立；尾部分布已校准。候选筛选和效果评价来自同一组 9 个留出场景，不是未触碰的外部验证集；Mountain/Valley 的独立环境样本仅三场景。

**最终方案：** 保留三个参数各自的全局 M0 工作基线（时延 Lognormal、多普勒 Student-t、相对功率 Student-t，同时把 Doppler Normal、relative-power Normal 作为重要近似候选）；拒绝 M1 作为当前正式场景外预测结构；只把 GSV 实测仰角—相对功率 M2 作为后续独立验证的探索性候选；不采用时延/多普勒 M2。九场景参数用于核心子总体描述，整体 13 场景主线仍以 WP1 基线为准，直至统一总体的新验收取代它。

本次没有发现需要重算的数值错误。唯一需修正的是论文叙述中的 delta 符号措辞；原结果不变，已在本独立审阅中给出不歧义定义。该结论仍为 `PASS_WITH_LIMITATIONS`，不自动通过 Gate G、Gate E/F 或 WP6。

## 6. 依赖与下一步

Task 5 CIR 继续由 Windows 本机 serial Coordinator 运行；本次未启动/停止/干预进程，未读取活动 HDF5/MAT/raw IQ。WP3 不改变 Task 5 release 和科学产物。WP4 的 Gate E/F 仍需 Task 5 完成后按既定身份、receipt、HDF5 read-back、PDP 与 QA 验收；WP5 alpha 真实导出继续暂缓；WP6 只能在可用的 CIR 特征关联、WP2/WP3 科学边界、Gate E/F 和独立验证均满足后开展。不得把本次模型选型当作这些依赖已经完成。

本轮唯一优先事项：由 Commander 对上述 M0 基线选型及 M2 探索性保留边界作正式确认；确认前不启动 WP4 以外的新分析，也不启动 alpha/WP5/WP6。
