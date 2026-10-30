# Mainline Stage2 论文证据矩阵、图表与缺口（2026-10-30）

与[论文科研成果整理](MAINLINE_STAGE2_PAPER_RESEARCH_SYNTHESIS_20261030.md)配套。本文件是作者选择论点与素材的索引，不改变任何冻结结果。以下“验证”指相应审阅范围内的数据身份/数值/场景外检验；不等同于传播物理真值、跨总体外推或 Gate G 通过。

## 1. 证据来源字典（均为仓库相对路径）

表中编号是**本文件引用缩写**，不是新的数据集或状态来源。旧 VTC/Stage3 r3 与 Mainline Stage2 的总体不同，不进入本矩阵的模型参数表。

| 编号 | 一手结果、独立审阅与直接源码 |
| --- | --- |
| S0 | `scripts/sage_pipeline/run_nav_sage_pipeline.m`（Stage0–Stage2、`flattenStage2`、路径排序/相对量、窗口归一化、`makeGrid`）；冻结生产 SHA 以 WP5 报告和 WP4 inventory 记录为准，不能把当前 HEAD 文件自动当作历史进程内存字节。 |
| V0 | `reports/data_consolidation_20261003/mainline_1023_model_v1/v0_20261024T132210Z/v0_model_report.md`；同目录 `population_support_by_scene.csv`、`variable_data_quality.csv`、`scene_fold_scores.csv`、`scene_loso_summary.csv`、`power_delay_relation.csv`、`independent_review.md`。 |
| W2 | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_20261025T074332Z/wp2_report.md`；同目录 `marginal_stability_by_fold.csv`、`tail_calibration_by_scene.csv`、`power_delay_loso_by_scene.csv`、`selected_count_loso_summary.csv`。独立复核：`reports/data_consolidation_20261003/mainline_1023_model_v1/wp2_independent_acceptance_20261025T151500Z/wp2_independent_acceptance.md`。 |
| W3 | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_20261028T140100Z/WP3_正式科研报告.md`；同目录 `full_data_model_parameters.csv`、`condition_support_by_scene_source.csv`、`loso_fold_scores.csv`、`loso_paired_deltas.csv`、`loso_paired_delta_macro.csv`、`motion_source_support_by_scene.csv`。独立审阅：`reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_independent_review_20261028/WP3_独立科学审阅与模型选型报告.md`；实现：`scripts/channel_modeling/mainline_stage2_wp3.py`。 |
| W4 | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp4_gate_ef_final_20261029T181100/WP4_Gate_EF_独立科学验收报告.md`；同目录 `gate_e_f_summary_git.json`、`gate_e_run_inventory_git.csv`、`stage2_cir_pdp_window_features.csv`、`stage2_mpc_cir_alpha_linkage.csv`、`gate_f_scene_summary.csv`。 |
| W5 | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp5_alpha_full_83run_20261029T055629Z/WP5_83run_alpha_full_acceptance.md`；同目录 `per_run_output_manifest.csv`、`wp5_alpha_full_summary.json`、`wp5_alpha_full_code_provenance.json`；实现：`scripts/channel_modeling/export_stage2_complex_alpha.m`。 |
| W6 | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_20261029T154500Z_final/WP6_联合统计信道模型科研报告.md`、`WP6_独立科学验收报告.md`；同目录 `summary.json`、`count_scene_scores.csv`、`mark_scene_scores.csv`、`pdp_scene_scores.csv`、`final_mark_model.json`；实现：`scripts/channel_modeling/mainline_stage2_wp6.py`。其中连续 Doppler 联合分数被后续审阅限制，不能作为最终排名。 |
| GG | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_gateg_supplement_20261029T165015Z/WP6_GateG最终科学审阅报告.md`；同目录 `count_stratum_scene_comparisons.csv`、`path_rank_scene_contrasts.csv`、`heldout_path_scores.csv`。 |
| DG | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_gateg_doppler_grid_audit_20261030T153436/WP6_GateG_Doppler观测机制专项审阅.md`；同目录 `doppler_nonaligned_windows.csv`、`analysis_summary.json`；冻结 `makeGrid` 机制见 S0。 |
| FB | `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_gateg_fixed_doppler_bins_20261030T120121Z/WP6_GateG_固定箱宽Doppler独立科学审阅.md`；同目录 `fixed_bin_scene_summary.csv`、`paired_scene_score_comparisons.csv`、`inner_family_selection.csv`、`heldout_window_scores.csv`、`independent_validation_portable.json`；实现：`scripts/channel_modeling/mainline_stage2_wp6_fixed_doppler.py`。 |

本包的最小来源锁：Stage2 MPC ledger SHA-256 `bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551`（W4/W5）；WP4 轻量窗口 CSV SHA-256 `258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4`，MPC linkage CSV SHA-256 `8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b`（FB/GG）。全量 alpha CSV 保留于 `E:/GNSS_Multipath_Project/dataset_generation_logs/channel_modeling/mainline_1023_wp5_alpha_full_83run_20261029T055629Z/`，不纳入 Git；准确文件与 SHA 在 W5 manifest 中。以上路径均应在正式论文复现清单再次核对，不以文字摘要替代 manifest。

## 2. 逐结论证据矩阵

状态：`充分验证` = 在指定估计对象/验收口径内可复核；`有限支持` = 观察和计算成立但推断边界明显；`探索性` = 可报告诊断但不应作为定案模型；`无证据` = 不能宣称；`后续修正` = 历史数值/说法被新评价口径限制或否定。每行的来源编号可在上表找到**具体文件路径**。

| 科学问题与状态 | 方法 / 数据来源与实验设计 | 实际数值及建议图表 | 可写结论 | 限制 / 源文件 |
| --- | --- | --- | --- | --- |
| 总体究竟是什么？`充分验证` | 冻结 Stage0→Stage2 身份与唯一键核对；83 run/13 scene；选中窗口与路径账本对账 | 285,752 Stage0 有效窗口；7,847 Stage2 已选（2.7461%）；8,914 MPC、7,847 参考、16,761 总路径；F1/T1 | 描述**SAGE 选中**的算法输出总体 | 选择覆盖率不是物理多径发生率；同场景 PRN/重叠窗口非独立。V0、W4、S0 |
| Stage2 已选窗口的 MPC 数量如何？`充分验证/有限支持` | 窗口为统计单位；`N=L−1`；WP2 截断 Poisson/NB2/经验类别 LOSO，WP6 场景平衡经验概率 | N=0/1/2/3 为 3,574/1,412/1,081/1,780；Poisson−经验 `−0.171584`、NB2−经验 `−0.0182553` nats/窗；NB2 13/13 均值无穷边界；WP6 经验计数 LOSO `−1.297385 nats/已选窗`；F2/T2 | 简单经验计数是当前条件总体的可用基线；未证明复杂计数模型必要 | 未选 Stage0 不补零；NB2 无稳定有限内部 MLE；计数类别受 L≤4 限制。W2、W6、S0 |
| 超额时延族是否稳定？`有限支持` | V0 全 13-scene LOSO 同变量候选比；WP3 九核心场景；FB 13 外层折内嵌套选族/0.01-chip 单元 | Lognormal V0 `13/13` 第一、WP3 核心 `9/9` 第一、FB `13/13` 外层训练折选中；最小观测 `0.10 chip`；F3/T2 | 在当前候选、筛选和评价口径下，Lognormal 是最稳的延迟工作族 | 原 V0 连续密度排名为探索性；0.01-chip 量化与 0.10-chip 截断须披露；不是物理时延普适律。V0、W3、FB、S0 |
| 带符号 Doppler 有单一分布吗？`有限支持/后续修正` | V0 候选族全场景留出；FB 预定箱宽、训练折内选族；DG 追查搜索机制 | V0 Normal/Student-t/Laplace 首位 `6/5/2` 折；FB 5-Hz Student-t/Normal 为 `11/2`，10/20-Hz Student-t 为 `13/0`；多 MPC 窗口 108/2,861 不完全同格；F3/T2 | 分布族选择对观测测度/场景敏感；仅对固定箱目标给出预测性比较 | 旧连续 Doppler 点密度综合模型排名失效；原自适应输出单元未恢复。V0、DG、FB |
| 相对功率族稳定吗？`有限支持` | V0 13-scene 与 FB 13 外层训练折对 Normal/Student-t 等候选 | V0 Student-t/Normal/Laplace 首位 `8/3/2`；FB 三箱宽下 Student-t/Normal 各 `8/5`；F3/T2 | 不把 Student-t 尾参数或 Normal 当唯一跨场景真值 | 相对 dB 非绝对功率；原训练总体/权重与 FB 不同。V0、W2、FB |
| 留出尾部已经校准了吗？`探索性/证据不足` | W2 用保存的训练折参数预测 p01/p05/p10/p90/p95/p99，并在留出 scene 比对经验分位数/覆盖 | `1,026` 个诊断中 `324` 个低于预设期望尾部支持 10；W3 九核心场景另有 `2,268` 个尾部记录，其中 `279` 拟合不可用、`579` 名义尾部路径行少于 10；T2/补充 | 可报告具体分位数误差与不支持项，不能统一宣布“尾部 PASS” | 名义路径行不是独立有效样本量；W2 重用 V0 折参数、W3 是不同核心总体。W2、W3 |
| 功率与时延负相关可用于预测吗？`有限支持` | V0 pooled Spearman/线性；W2 完整 scene LOSO 的条件 vs 边际同身份预测 | `rho=−0.616410`、线性 `R²=0.055343`；13/13 折斜率负；条件−边际宏 log-score `−0.0605013`，RMSE 差 `+0.182619 dB`（条件更差）；F4 | 负向**估计参数关联**可写，预测收益和因果衰减律不可写 | 同窗/重叠/场景簇；V0 slope 与 W2 slope 不同权重，不能混成同一参数。V0、W2 |
| Urban 与 Mountain 是否需要独立参数？`有限支持/否定该强主张` | W3 九核心 scene：同测试键的 M1−M0 配对分数；Urban 6、Mountain 3 | 三参数的各候选族总体宏差均负；时延 `−0.0837…−0.0242`，Doppler `−0.0459…−0.0122`，功率 `−0.1519…−0.0166`（部分功率族只 8/9 配对）；F5 | 存在样本点估计差异，但不支持将 M1 作为更佳场景外主模型 | 只 9 核心 scene；不同族/支持不可横比；Mountain 3 scene 不足强推断。W3 |
| 仰角是否有稳定条件效应？`探索性` | W3 只在 GSV_MEASURED 同样本比较 M2/M1/M0；来源分层 | 核心 GSV：3,478/4,901 窗口、4,948/6,335 MPC；功率 M2−M1 三族正，但 M2−M0 混合；F5 | 可以呈现来源纯净的相对功率关联假设 | GSV 选择/覆盖不均；derived/GGA 与 zero-height 不混作实测；时延/Doppler M2 无稳健增益。W3、V0 |
| 车辆运动条件模型已验证？`无证据` | W3 motion 来源与复用审计，没有拟合 M3 | 核心有速度的窗口 3,372；源 NMEA 记录仅 144 个且复用，最高速度 142.378 m/s 待质量核验 | 只能说明记录可用性和限制，不写运动机制/效应 | 不做速度—路径因果或条件模型主张。W3 |
| CIR/PDP 是否与 SAGE 正确关联？`充分验证/有限支持` | W4 83-run HDF5 read-back、逐块 CIR/PDP 公式重算、严格 run/window/path 键 | Gate E/F `PASS_WITH_LIMITATIONS`；`7,847/7,847` 窗口、`8,914/8,914` MPC 关联；`11,430,080` 快照/451 bins；PDP 最大差 0；63 个边界峰；F6/T1 | 可写身份和**内部数值一致性** | 1 个旧 baseline 缺历史 HDF5 pin，full auditor 起始源码 SHA 未捕获；共享测量链不是独立真值；PDP 宽度非物理 RMS spread。W4 |
| 复数 alpha 是否真实可用？`充分验证/有限支持` | W5 逐源 MAT 与导出表独立重建、路径和相对功率核对 | `83/83` run；`16,761/16,761` 有限 alpha；缺失/错位 0；复数分量最大差 `4.996e−16`；T1 | 同窗口相对幅度/相位与路径属性可精确关联 | 40-ms 独立 RMS 归一化；5 个 MAT 缺历史逐文件 SHA pin；跨窗相干/绝对增益未验。W5、S0 |
| SAGE 参数能改善 PDP 场景外预测吗？`有限支持` | W6 两个窗口级 PDP 目标对比常数基线与线性模型，完整场景留出 | 峰偏移 RMSE `4.298158→4.290361 samples`；code-delay RMS 宽度 `2.485324→2.446555 samples`；F6 | 共享输入链存在可测但很小的预测关联 | 非独立传播真值、非物理 RMS delay spread；不支撑主论文路线 B 的强联合预测主张。W6、W4 |
| 独立边际 vs Copula 有可靠场景外优势吗？`有限支持/否定优势主张` | FB 0-Hz 中心 5/10/20-Hz 固定箱，delay/Doppler 离散质量+power 密度，13-scene paired nested LOSO | `C0−M0 = −0.00768378/−0.00864037/−0.00820576 nats/mark`；每宽度 10 正/3 负，5-Hz 范围 `[-0.347325,+0.115527]`；F7/T2 | 固定分箱目标可科学比较；现有数据**未见稳定场景宏平均 Copula 收益** | 不等于无依赖；三宽度绝对分数不可互比；不等于原自适应输出似然。FB、DG |
| 完整联合生成器/时变物理模型是否通过？`无证据` | GG 的 N 条件标记/路径秩审阅 + FB 的固定箱评分 | N=1 的 1,412 条标记无完整条件族评分；N=3 最少场景仅 3 个窗口；N>1 路径秩非交换；Gate G=`PENDING`；T2 | 不写“已验证完整联合生成器” | 条件 iid、绝对增益、跨窗相位、物理反射路径持续性均未验。GG、FB、W5 |

**历史结论处理：** W6 的连续 Doppler 综合 log-score/Copula 差只作为当时实现和后续问题发现的溯源，不在正文模型优劣表中出现；GG 的“时延离散、Doppler 连续”Copula 分数也只作诊断。正式依赖对比以 FB 同箱宽/同测试身份为准；这没有证明原自适应搜索过程的输出似然。WP3 九核心场景和全 13-scene 结果不能混用一个分母或参数。所有 LOSO 折互相共享 12 个训练场景，场景宏分差只描述本 13 场景的未见场景敏感性，不给路径行级独立显著性或普通 13 次独立实验置信区间。

## 3. 图表/表格清单与论文用途

“现有”仅指已保存素材，**不是未经复查就准入正式稿**。实际是否复用须检查轴、标签、颜色、来源和图注；下表列的是最少而充分的一组。

| ID / 优先级 | 欲证明的问题；横纵轴、单位 | 数据文件和字段 / 现有图 | 处理与科学风险 |
| --- | --- | --- | --- |
| F1 **正文必备** | 测量→GNSS-SDR/NAV→Stage0/1→Stage2 参数与选择→完整 scene 留出→WP4/5 辅证；流程图无数值轴 | S0、V0、W4、W5；既有 `docs/paper_draft/manuscript_outline.md` 仅旧路线文字 | **需重画**简洁矢量图；把 Stage3/4 与本论文 Stage2 主总体分开，不把 CIR 画成从 alpha 重构的独立真值 |
| T1 **正文必备** | 各环境/scene 的 run、Stage0 有效窗、Stage2 已选窗、MPC、CIR 关联与仰角来源；计数及 `%` | V0 `population_support_by_scene.csv`、W4 `gate_f_scene_summary.csv`、W3 `condition_support_by_scene_source.csv`；现有 V0 报告表 | **整理重排**而非重新分析；表头注明分母，精确坐标不入稿；两场景环境支持不足单独标注 |
| F2 **正文必备** | N=0/1/2/3 的已选窗口数/比例；横轴 MPC 数，纵轴窗口数或 % | V0 `window_mpc_count_summary.csv`、W6 `summary.json`；现有 `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_20261029T154500Z_final/wp6_selected_window_count.png` | 可复用但须视觉 QA；图注写 `N | Stage2 selected`，不得标为所有观测窗口“多径发生率” |
| F3 **正文必备** | 三个标记的经验分布、候选与场景差异；横轴 delay chips / signed Doppler Hz / relative power dB，纵轴概率或密度并注明测度 | V0 `variable_data_quality.csv`、`scene_loso_summary.csv`、`figures/marginal_*.png`；FB `observed_doppler_bin_support.csv`、`inner_family_selection.csv` | V0 图可供初稿观察；**正式 Doppler/量化 delay 面板需按固定观测箱/格点重新绘制**，不能用连续点密度图暗示原算法似然；场景带或小倍图不把 8,914 路径当独立 CI |
| F4 **正文必备** | 未见 scene 的模型复杂度/预测方向；横轴 held-out scene，纵轴同支持 log-score 差（nats/目标单位）或 RMSE 差（dB） | W2 `power_delay_loso_by_scene.csv`、W3 `loso_paired_deltas.csv`；现有 `reports/data_consolidation_20261003/mainline_1023_model_v1/wp3_20261028T140100Z/figures/loso_paired_score_deltas.png` | 建议以 `M1−M0`、`M2−M0` 与 power-delay 对照分面；WP3 现有图先核 delta 符号，M2 必须限定 GSV 同样本、不得与九场景以外分数拼接 |
| F5 **正文/补充二选一** | Urban/Mountain 估计量差异及 GSV 来源覆盖；横轴 scene/环境或仰角 °，纵轴 scene-level 中位 delay chips / power dB | W3 `descriptive_by_scene.csv`、`condition_support_by_scene_source.csv`；现有 `figures/core_environment_scene_medians.png` 和 `figures/gsv_elevation_window_medians.png`（W3 目录） | 可复用，适合说明异质和缺失，不作因果或两套环境模型已获胜证据；Mountain 仅 3 scene |
| F6 **补充优先** | Code-domain 样本数/精确关联、PDP 目标线性−常数的场景外 RMSE 差；横轴 scene，纵轴差（samples） | W4 `stage2_cir_pdp_window_features.csv`、W6 `pdp_scene_scores.csv`；现有 `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_20261029T154500Z_final/wp6_scene_heldout_pdp_rmse_delta.png` | 现有图须核负号“较好”；图注为 code-delay 相关宽度，不是物理 RMS delay spread。若要展示真正 PDP 曲线需另做受控载荷选例，本论文路线 A **非必需** |
| F7 **正文或补充必备** | 固定分箱依赖结构是否稳健；横轴 13 个留出 scene，纵轴 `C0−M0`（nats/mark），另以 5/10/20-Hz 摘要表呈现宏均差 | FB `paired_scene_score_comparisons.csv`、`fixed_bin_scene_summary.csv`；旧 `reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_20261029T154500Z_final/wp6_scene_heldout_copula_delta.png` | **必须用 FB 轻量表重画；旧连续 Doppler 图禁入正文排名。** 图上明确 10 正/3 负、宏均为负；相同宽度内比较，不比较跨宽度绝对 log-score |
| T2 **正文必备** | 统计对象、训练/测试单位、候选族与状态的总表；列为 estimand、分母、候选、同支持 LOSO 成绩、结论/失败 | V0/W2/W3/W6/FB 的上述结果表 | **需编表**，不同测度、不同核心总体的分数不排在同一排行榜；低支持/失败单列，不把 Gate F 数值 QA 与模型预测混成一个 PASS |

`F1/T1/F2/F3/F4/T2` 是路线 A 的最小正文组；`F5/F6/F7` 可依稿长取舍，但若正文讨论 Copula，F7 或同等逐场景表必须出现。不要直接复用旧 `wp6_scene_heldout_copula_delta.png`。本轮未绘新图；图表行均是**制作计划**而非已交付稿件。

## 4. 缺口与最小后续工作

| 类别 | 缺什么、为什么 | 现有冻结数据能否解决 / 最小工作 | 不做会限制什么 |
| --- | --- | --- | --- |
| **A：发表前必须** | 正式逐篇文献对照：当前 WP1 文献仅部分摘要/来源已核；须核测量对象、估计器、场景分层和评价单位，才能确定差异点及引用 | 主要是文献与写作工作，不需新科学生产；用正式参考文献清单逐条核原文 | 不能宣称方法首创或与现有 GNSS/SAGE 研究的明确优势 |
| **A：发表前必须** | 明确论文唯一估计对象、预先声明的主要指标与负结果；将历史连续 Doppler/旧 VTC Stage3 数字与 Mainline Stage2 正文隔离 | 已有 V0/W2/W3/W4/W5/W6/GG/DG/FB 足够；编辑正文/图注时逐 claim 对证据矩阵复核 | 若混用，将产生错误模型排名、错误分母或把 Stage2 候选写成 confirmed physical truth |
| **A：发表前必须** | 用 FB 逐场景轻量表重画依赖对照，并对 T1/T2 的分母、轴单位、图例和可见失败/低支持做科学图表 QA；至少完成正式英文摘要—正文—结论的同数值核对 | 可完全用冻结 CSV/PNG，轻量绘图与人工审阅；不要求 SAGE/CIR 重算 | Copula 10 正/3 负与负宏均分若只取一面会误导；旧连续评分图不可用于正式排名 |
| **B：有价值非必需** | 增加真正新场景或独立采集批次验证外部泛化，特别是 Mountain 和两场景环境；当前 13 scene、相互重叠 LOSO 训练限制推断 | 不能仅靠冻结 13 scene 创造新独立场景；需要额外数据/授权。当前论文主张仅限定本总体、完整场景留出时可不做 | 不得声称跨设备、跨城市/季节或所有环境普适 |
| **B：有价值非必需** | 针对尾部低支持、GSV 缺失和速度记录复用做限定敏感性/来源 QA | 一部分可用现有轻量表解决；如需真实速度/时间真值须外部记录。不为主线重跑 WP3 | 尾部、仰角及运动作用只可报告探索或不报告 |
| **B：有价值非必需** | 提供一个 code-domain CIR/PDP 代表例图或独立测量对照 | 代表例曲线需受控读取已冻结 HDF5，属于另行授权的小范围素材制作；独立真值需新测量 | 路线 B 无法升为强物理一致性/重构主张；路线 A 不受影响 |
| **C：独立后续研究** | Count-conditioned **完整** marks、有序路径结构/交换性、可评分的自适应 Doppler 输出测度及 Gate G | 冻结最终值不含逐轮搜索状态，不能逆造；需要新的估计协议或全新可验证假设，不在本文稿件整理范围 | 不能宣称经过场景外验证的完整联合生成器 |
| **C：独立后续研究** | 绝对校准增益、跨 40-ms 窗口相干相位、连续反射体跟踪、物理时变信道合成及 Phase-2 AI | 当前 alpha/CIR 证据不能直接补齐；需额外校准/同步/物理验证 | 不能宣称完整时变复数物理信道或生成式模型已验收 |

**结论性缺口判断：** 对路线 A 的**限定性论文论点**，目前没有必须新增 SAGE/CIR/alpha 的大规模实验；必须完成的是文献、正式图表和逐 claim 写作审阅。若作者坚持路线 B 的“真实物理联合/时变生成模型”或跨未知测量域的普适预测主张，上述 B/C 缺口将转为阻断项；不能靠改标题或降低 Gate G 准则解决。
