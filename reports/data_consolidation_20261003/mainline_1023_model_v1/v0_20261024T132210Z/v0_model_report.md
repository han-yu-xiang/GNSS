# GNSS Mainline Stage2 参数统计 V0：真实数据探索报告

状态：`EXPLORATORY_V0_COMPLETE_WITH_LIMITATIONS`。Gate E/F 仍为 PENDING；本报告不是完整 CIR 信道模型或正式 Gate G 验收。

分析时间（UTC）：2026-10-24T13:22:16.696964+00:00。新结果目录：`C:/Users/Jing_/.codex/worktrees/gnss-cir/GNSS_Multipath_Project/dataset_generation_logs/channel_modeling/mainline_1023_stage2_v0_20261024T132210Z`。

## 1. 研究总体、选择机制与身份

本次核验 83 项任务、13 个录制场景、16761 条 Stage2 路径；其中 7847 条直达/参考路径只用于参数核对，全部 8914 条 MPC 候选进入路径级分析。
Stage0 有效窗口共 285752，Stage2 选中窗口 7847；选中覆盖率 2.7461%，它不是物理多径发生率。未选中 Stage0 窗口不补记为零 MPC。
Stage3/Stage4 仅作属性与敏感性描述，不筛选候选。复合键、连续 path_id、selected_L 和 cohort 标签均核对；精确窗口关联保留全部路径。
同一录制场景内多 PRN/channel 与重叠窗口具有依赖性，不能将 8914 条路径当作独立实验重复。外层验证和不确定性均按完整 scene_id。

| scene_id | environment_class | run_n | stage0_valid_window_n | selected_window_n | selection_coverage_percent | mpc_n | gsv_window_n | derived_window_n | position_matched_n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1023_V120_D0121_P2 | Highway/Open | 13 | 177588 | 841 | 0.473568 | 104 | 145 | 468 | 613 |
| F1023_V70_D0117_P2 | Mountain/Valley | 7 | 7092 | 592 | 8.34743 | 837 | 451 | 141 | 592 |
| F1023_V70_D0117_P4 | Mountain/Valley | 7 | 6250 | 761 | 12.176 | 1093 | 566 | 195 | 761 |
| F1023_V70_D0120_P1 | Urban | 3 | 6327 | 330 | 5.21574 | 334 | 293 | 37 | 330 |
| F1023_V70_D0120_P5 | Urban | 5 | 4242 | 483 | 11.3861 | 671 | 257 | 66 | 321 |
| F1023_V70_D0120_P7 | Urban | 4 | 8916 | 439 | 4.92373 | 707 | 408 | 31 | 439 |
| F1023_V70_D0120_P8 | Urban | 4 | 3540 | 447 | 12.6271 | 442 | 332 | 34 | 366 |
| F1023_V70_D0120_P9 | Special Reflective | 9 | 19909 | 987 | 4.95756 | 1172 | 792 | 195 | 987 |
| F1023_V70_D0122_P1 | Urban | 8 | 12281 | 842 | 6.85612 | 1429 | 639 | 157 | 796 |
| F1023_V70_D0122_P2 | Special Reflective | 7 | 18167 | 669 | 3.6825 | 832 | 344 | 15 | 588 |
| F1023_V80_D0117_P8 | Highway/Open | 5 | 5214 | 449 | 8.61143 | 471 | 369 | 80 | 449 |
| F1023_v50_D0127_P1 | Urban | 5 | 9090 | 386 | 4.24642 | 115 | 104 | 68 | 172 |
| F1023_v90_D0117_P7 | Mountain/Valley | 6 | 7136 | 621 | 8.70235 | 707 | 428 | 178 | 606 |

## 2. 参数定义与数据质量

原字段及单位保留。源代码 flattenStage2 定义超额时延为各路径 delaySamples 减 path 1 delaySamples；Doppler offset 为各路径 dopplerHz 减 path 1 dopplerHz；相对功率为 10log10(|alpha|²/|alpha_1|²)，源实现自带 realmin 保护，本分析没有追加 epsilon。
13 个场景 metadata 的采样率均核验为10,230,000 Hz；源配置码率1,023,000 Hz，故10 samples/chip。时延模型使用原生 chips；1 chip=10 samples=977.51710655 ns。相对功率不是绝对接收功率，相对 Doppler 不是散射体速度。
`variable_data_quality.csv` 同时报告 MPC/参考路径、原生采样点/码片/路径长度、符号、非有限值、零值和 Tukey 异常值；异常值没有自动删除。描述统计标准差和分位数只描述依赖观测行，不构成独立样本推断。
Tukey 标记按每个原字段的浮点数值计算，边界舍入可能令采样点/码片标记数稍异；这不改变任何样本或拟合。观测时延最小值0.1 chip反映当前选择后的支持，不能据正值族外推未观测的小延迟总体。功率为正的327条仍保留：参考路径不是“必然最强或已知物理LOS”的保证。

| variable | finite_n | missing_n | invalid_text_n | nonfinite_n | zero_n | negative_n | mean | std | median | iqr | p5 | p95 | p99 | min | max | tukey_outlier_n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| excess_delay_chips | 8914 | 0 | 0 | 0 | 0 | 0 | 0.236157 | 0.183975 | 0.21 | 0.14 | 0.1 | 0.38 | 0.97 | 0.1 | 3.3 | 195 |
| doppler_offset_hz | 8914 | 0 | 0 | 0 | 1 | 4423 | 1.8023 | 72.5681 | 5.94834 | 100.006 | -100.336 | 99.6643 | 199.664 | -350.336 | 349.664 | 100 |
| relative_power_db | 8914 | 0 | 0 | 0 | 0 | 8587 | -9.37919 | 6.42004 | -11.3618 | 9.36548 | -17.1416 | -0.65397 | 13.994 | -23.7689 | 28.6013 | 149 |

## 3. 候选边际分布与全量描述性参数

正值 Gamma/Lognormal/Weibull 固定 location=0，严格正值支持；零/负值单列且不加 epsilon。Normal/Laplace/Student-t 保留 Doppler 符号及功率 dB。所有拟合记录样本数、参数、数值状态、warnings、对数似然和训练内 AICc/BIC；参数顺序与 SciPy 一致（正值族 shape,loc,scale；Normal/Laplace loc,scale；Student-t df,loc,scale）。SciPy 解析/内部求解不暴露优化标志时明确写明，不伪造收敛标志。
本次全量描述拟合失败 3 项；LOSO 失败或训练场景支持不足 36 项，所有记录仍保存在 CSV 中。不同变量/不同单位的对数似然不可直接比较。只有同变量、同训练总体、同支持范围的候选可比较。

| variable | family | n | status | parameters | loglik | aicc | bic |
| --- | --- | --- | --- | --- | --- | --- | --- |
| excess_delay_chips | gamma | 8914 | PASS | [3.979350773134209, 0.0, 0.059345511629168395] | 7167.29 | -14330.6 | -14316.4 |
| excess_delay_chips | lognormal | 8914 | PASS | [0.46455050943125975, 0.0, 0.2071858686063382] | 8217.69 | -16431.4 | -16417.2 |
| excess_delay_chips | weibull | 8914 | PASS | [1.5763809026177036, 0.0, 0.2653113783796442] | 5700.06 | -11396.1 | -11381.9 |
| doppler_offset_hz | normal | 8914 | PASS | [1.8022976381582365, 72.56405046523312] | -50840.2 | 101684 | 101699 |
| doppler_offset_hz | laplace | 8914 | PASS | [5.9483416013627, 62.268984394211046] | -51920.6 | 103845 | 103859 |
| doppler_offset_hz | student_t | 8914 | PASS | [20.975599595324717, 1.1945429874308044, 68.76307042003062] | -50790.5 | 101587 | 101608 |
| relative_power_db | normal | 8914 | PASS | [-9.379189345126127, 6.419677208356731] | -29222.8 | 58449.6 | 58463.8 |
| relative_power_db | laplace | 8914 | PASS | [-11.36180437281155, 4.950370271296865] | -29350.3 | 58704.6 | 58718.8 |
| relative_power_db | student_t | 8914 | PASS | [8.219891586226147, -9.892251165113088, 5.48510087478984] | -28934.9 | 57875.9 | 57897.2 |

## 4. 独立场景留出验证

每一折重新用训练场景估计参数；同 scene 所有 run、PRN/channel、重叠窗口整体留出。GLOBAL 13折，Urban 6折；其他环境在至少两个训练场景时评估，只有两个场景的环境留出后仅一个训练场景，明确记 INSUFFICIENT_SUPPORT。无随机路径/窗口拆分。
主指标是 held-out scene 的每有限观测平均 log density，再对 scene 等权宏平均。支持违反记为 -Infinity，另列正支持条件分数，绝不隐藏测试集零/负值。训练内 AICc/BIC 不代替此成绩。宏平均候选排名是探索结果，不是经过新的独立数据检验的最终模型选择。

| scope | variable | family | fold_n | evaluated_fold_n | macro_mean_loglik | macro_std_across_scenes | support_violation_n | failed_or_unsupported_fold_n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLOBAL | excess_delay_chips | gamma | 13 | 13 | 0.712347 | 0.585584 | 0 | 0 |
| GLOBAL | excess_delay_chips | lognormal | 13 | 13 | 0.88786 | 0.352101 | 0 | 0 |
| GLOBAL | excess_delay_chips | weibull | 13 | 13 | 0.542103 | 0.574527 | 0 | 0 |
| GLOBAL | doppler_offset_hz | normal | 13 | 13 | -5.72915 | 0.337628 | 0 | 0 |
| GLOBAL | doppler_offset_hz | laplace | 13 | 13 | -5.82688 | 0.212391 | 0 | 0 |
| GLOBAL | doppler_offset_hz | student_t | 13 | 13 | -5.71957 | 0.318865 | 0 | 0 |
| GLOBAL | relative_power_db | normal | 13 | 13 | -3.31946 | 0.495513 | 0 | 0 |
| GLOBAL | relative_power_db | laplace | 13 | 13 | -3.35002 | 0.282564 | 0 | 0 |
| GLOBAL | relative_power_db | student_t | 13 | 13 | -3.32112 | 0.494792 | 0 | 0 |
| ENV:Highway/Open | excess_delay_chips | gamma | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Highway/Open | excess_delay_chips | lognormal | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Highway/Open | excess_delay_chips | weibull | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Highway/Open | doppler_offset_hz | normal | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Highway/Open | doppler_offset_hz | laplace | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Highway/Open | doppler_offset_hz | student_t | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Highway/Open | relative_power_db | normal | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Highway/Open | relative_power_db | laplace | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Highway/Open | relative_power_db | student_t | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Mountain/Valley | excess_delay_chips | gamma | 3 | 3 | 0.746581 | 0.418259 | 0 | 0 |
| ENV:Mountain/Valley | excess_delay_chips | lognormal | 3 | 3 | 0.902224 | 0.283158 | 0 | 0 |
| ENV:Mountain/Valley | excess_delay_chips | weibull | 3 | 3 | 0.465912 | 0.568316 | 0 | 0 |
| ENV:Mountain/Valley | doppler_offset_hz | normal | 3 | 3 | -6.03682 | 0.49832 | 0 | 0 |
| ENV:Mountain/Valley | doppler_offset_hz | laplace | 3 | 3 | -6.08998 | 0.35356 | 0 | 0 |
| ENV:Mountain/Valley | doppler_offset_hz | student_t | 3 | 3 | -6.02616 | 0.505901 | 0 | 0 |
| ENV:Mountain/Valley | relative_power_db | normal | 3 | 3 | -4.02225 | 1.30178 | 0 | 0 |
| ENV:Mountain/Valley | relative_power_db | laplace | 3 | 3 | -3.51529 | 0.59236 | 0 | 0 |
| ENV:Mountain/Valley | relative_power_db | student_t | 3 | 3 | -3.93099 | 1.37096 | 0 | 0 |
| ENV:Special Reflective | excess_delay_chips | gamma | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Special Reflective | excess_delay_chips | lognormal | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Special Reflective | excess_delay_chips | weibull | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Special Reflective | doppler_offset_hz | normal | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Special Reflective | doppler_offset_hz | laplace | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Special Reflective | doppler_offset_hz | student_t | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Special Reflective | relative_power_db | normal | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Special Reflective | relative_power_db | laplace | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Special Reflective | relative_power_db | student_t | 2 | 0 | NA | NA | 0 | 2 |
| ENV:Urban | excess_delay_chips | gamma | 6 | 6 | 0.909077 | 0.188364 | 0 | 0 |
| ENV:Urban | excess_delay_chips | lognormal | 6 | 6 | 1.00885 | 0.166077 | 0 | 0 |
| ENV:Urban | excess_delay_chips | weibull | 6 | 6 | 0.722348 | 0.205895 | 0 | 0 |
| ENV:Urban | doppler_offset_hz | normal | 6 | 6 | -5.61347 | 0.235164 | 0 | 0 |
| ENV:Urban | doppler_offset_hz | laplace | 6 | 6 | -5.75387 | 0.170055 | 0 | 0 |
| ENV:Urban | doppler_offset_hz | student_t | 6 | 6 | -5.61684 | 0.235812 | 0 | 0 |
| ENV:Urban | relative_power_db | normal | 6 | 6 | -3.20597 | 0.147438 | 0 | 0 |
| ENV:Urban | relative_power_db | laplace | 6 | 6 | -3.3116 | 0.0945536 | 0 | 0 |
| ENV:Urban | relative_power_db | student_t | 6 | 6 | -3.20976 | 0.145359 | 0 | 0 |

### 在相同 held-out Urban 场景上的配对比较

下表仅比较同一测试场景、同变量、同候选族的环境模型与global模型，delta为环境模型每样本对数密度减global分数，再对场景等权平均。不能直接用Urban六折均值减global十三折均值来宣称条件模型改善。

| variable | family | paired_scene_n | macro_delta_env_minus_global | improved_scene_n | status |
| --- | --- | --- | --- | --- | --- |
| excess_delay_chips | gamma | 6 | -0.00692989 | 3 | EXPLORATORY |
| excess_delay_chips | lognormal | 6 | -0.00564225 | 1 | EXPLORATORY |
| excess_delay_chips | weibull | 6 | -0.018859 | 3 | EXPLORATORY |
| doppler_offset_hz | normal | 6 | -0.00287236 | 4 | EXPLORATORY |
| doppler_offset_hz | laplace | 6 | -0.00473871 | 3 | EXPLORATORY |
| doppler_offset_hz | student_t | 6 | -0.0100021 | 4 | EXPLORATORY |
| relative_power_db | normal | 6 | -0.0134915 | 2 | EXPLORATORY |
| relative_power_db | laplace | 6 | -0.0188003 | 2 | EXPLORATORY |
| relative_power_db | student_t | 6 | -0.00770983 | 3 | EXPLORATORY |

### 当前证据支持的候选结论

Global和Urban的时延候选中Lognormal留出宏平均最高（首轮真实运行约0.88786和1.00885 nats/观测，精确本次值以上表为准），Gamma没有因文献先验而被指定为赢家。Global Doppler的Student-t与Normal十分接近；Urban Doppler的Normal略高。功率的全量训练内AICc偏好Student-t，但跨场景宏平均Normal略高（global差约0.00166 nats），因此Normal/Student-t均保留为竞争候选，不宣称唯一稳定分布。所有拟合仍受Stage2选择、有限场景和可能的截断/离散网格影响。

逐场景成绩见 `scene_fold_scores.csv`；训练/测试场景身份见 `scene_fold_manifest.json`。逐场景差异和少量独立场景限制外推，不因路径行数多而夸大稳定性。

## 5. 功率—时延与参数依赖

全局 Spearman rho=-0.616410，OLS 斜率=-8.209394 dB/chip，截距=-7.440487 dB，R²=0.055343。
按整个 scene 有放回抽样（保留全部行与重复抽中次数），1000 次、固定seed=20261024，斜率95%百分位区间 [-14.288980, -3.852434]，rho区间 [-0.680960, -0.540977]。这是13个场景下的探索性块重采样区间，不是无限总体保证。
逐场景和环境关系均保留；不依据 pooled rho 单独宣称稳定物理衰减定律。初步回归只检验线性假说，不把相关性解释为因果机制，也未为提高拟合效果删除异常值。
全局线性R²约0.055，跨场景斜率差异明显，故“总体负向关联”有证据，“普适线性衰减定律”没有得到证明。

| scope | label | n | scene_n | slope_db_per_chip | spearman_rho | r_squared | slope_ci_low | slope_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GLOBAL | ALL | 8914 | 13 | -8.20939 | -0.61641 | 0.0553431 | -14.289 | -3.85243 |
| environment_class | Highway/Open | 575 | 2 | 1.99065 | -0.5282 | 0.0121645 | NA | NA |
| environment_class | Mountain/Valley | 2637 | 3 | -7.30463 | -0.604418 | 0.0275207 | -45.4833 | -4.05429 |
| environment_class | Special Reflective | 2004 | 2 | -15.5991 | -0.594463 | 0.17042 | NA | NA |
| environment_class | Urban | 3698 | 6 | -11.2698 | -0.650933 | 0.119 | -27.3767 | -7.16908 |
| scene_id | F1023_V120_D0121_P2 | 104 | 1 | 3.8457 | -0.0107229 | 0.121012 | NA | NA |
| scene_id | F1023_V70_D0117_P2 | 837 | 1 | -4.05429 | -0.389756 | 0.0086572 | NA | NA |
| scene_id | F1023_V70_D0117_P4 | 1093 | 1 | -14.8196 | -0.738349 | 0.167546 | NA | NA |
| scene_id | F1023_V70_D0120_P1 | 334 | 1 | -25.0575 | -0.612484 | 0.268928 | NA | NA |
| scene_id | F1023_V70_D0120_P5 | 671 | 1 | -2.2889 | -0.588576 | 0.00302756 | NA | NA |
| scene_id | F1023_V70_D0120_P7 | 707 | 1 | -18.7534 | -0.643888 | 0.241381 | NA | NA |
| scene_id | F1023_V70_D0120_P8 | 442 | 1 | -48.0899 | -0.775821 | 0.639352 | NA | NA |
| scene_id | F1023_V70_D0120_P9 | 1172 | 1 | -14.3509 | -0.627982 | 0.191172 | NA | NA |
| scene_id | F1023_V70_D0122_P1 | 1429 | 1 | -8.76398 | -0.632109 | 0.13998 | NA | NA |
| scene_id | F1023_V70_D0122_P2 | 832 | 1 | -19.1353 | -0.552387 | 0.1606 | NA | NA |
| scene_id | F1023_V80_D0117_P8 | 471 | 1 | -1.72685 | -0.632042 | 0.00636383 | NA | NA |
| scene_id | F1023_v50_D0127_P1 | 115 | 1 | -54.6556 | -0.681208 | 0.545943 | NA | NA |
| scene_id | F1023_v90_D0117_P7 | 707 | 1 | -45.4833 | -0.746768 | 0.528549 | NA | NA |

参数两两 Spearman 见 `parameter_spearman_correlations.csv`，没有使用路径独立假设下的 p 值。Stage3/4 属性敏感性见 `stage34_attribute_sensitivity.csv`，UNMAPPED 语义保留，Stage4 path编号匹配不被解释为物理身份恒定。

## 6. 选中窗口内 MPC 数量

{"0": 3574, "1": 1412, "2": 1081, "3": 1780}（键为 MPC 数，值为窗口数）。合计必须为7,847。
频数、比例、分位数按全局、scene、environment 写入 `window_mpc_count_summary.csv` 和 `window_mpc_count_descriptive.csv`。本轮不拟合 Poisson/负二项或随机簇模型，也不推断全部 Stage0 窗口的多径发生率。

## 7. 环境、连续仰角与位置条件

独立场景支持为 Urban 6、Mountain/Valley 3、Highway/Open 2、Special Reflective 2。全局为主要基线，Urban 另做完整场景留出；其他环境描述结果不能替代稳定环境专属模型的证据。全量环境参数均为描述，未引入互不相关的四套物理模型。
几何窗口来源实测统计：{"EPHEMERIS_DERIVED": 1665, "GSV_MEASURED": 5128, "MISSING": 1054}；派生高度来源：{"GGA_ELLIPSOIDAL_HEIGHT": 622, "ZERO_HEIGHT_ASSUMPTION": 1043}。位置匹配 7020，仰角/位置联合 6791。
连续仰角分 GSV_MEASURED、EPHEMERIS_DERIVED_GGA_ELLIPSOIDAL_HEIGHT、EPHEMERIS_DERIVED_ZERO_HEIGHT_ASSUMPTION；冻结 High/Mid/Low 分类另作描述，不由分类反推连续角度。缺失值没有填0；负角度如有将独立标为 OUT_OF_FORMAL_RANGE，不归Low。本次有效overlay中 622 个派生高度关联窗口共享 55 条GGA高度观测，按(scene_id,source_file,record_id)去重；零高假设 1043 条不是实测高度。分场景可复算计数见 `geometry_height_source_support.csv`，该表不输出高度数值或源记录身份。
`geometry_condition_summary.csv` 给出来源/场景支持与范围；`elevation_parameter_relations.csv` 给出分来源、分场景的探索性关系，少于3个支持场景标 INSUFFICIENT_SUPPORT。既有独立pilot为145/145，MAE0.269477°、P950.448884°、最大0.491844°；本轮未重算，也不声称旧全量audit包含后来新增pilot身份凭据。
位置只用于覆盖/来源描述。旧空间审计36项均为 INSUFFICIENT_SPATIAL_SUPPORT，不估计空间相关距离、有效独立单元或正式空间模型；没有更改路段阈值。没有精确坐标进入本报告或Git结果。

## 8. 图表与复算

`figures/marginal_*.png`（同时有PDF）包含真实MPC经验密度、拟合密度、ECDF/理论CDF和Q-Q诊断；`power_delay_scene_comparison` 包含全部MPC散点及逐scene回归；`environment_distributions`比较四环境；`window_counts_and_elevation_sources`展示场景计数分布及分来源仰角散点。
图中每个点都来自本次真实输入；合成数据仅出现在单元测试。`analysis_mpc_rows.csv`/`selected_window_rows.csv`为本地复算数据，原账本不变；`model_summary.json`保存所有输入路径/SHA、代码SHA、库版本、设置、失败与主要结果。`artifact_manifest.json`绑定产物。

## 9. 文献方法依据与边界

1. Wang, Chen, Liu, Sensors 2018，[DOI:10.3390/s18041149](https://doi.org/10.3390/s18041149)：已核验[PubMed作者摘要](https://pubmed.ncbi.nlm.nih.gov/29642564/)中的静态城市GNSS实测参数统计及Gamma时延结论；本轮出版社全文访问受限，因此不援引未核验公式、页码或数值。功率—时延线性关系作为Commander指定的待检验假设。本轮对移动场景重新比较候选，不迁移论文参数或把其结果当本数据结论。
2. Yin et al., TVT 2016，[DOI:10.1109/TVT.2015.2506180](https://doi.org/10.1109/TVT.2015.2506180)：已核验作者机构库摘要中被动UMTS信号、CIR、SAGE参数估计和随时间变化的簇分析链条；未取得并逐式核验全文，因此不援引未核验公式/参数。机构来源：https://ir.pku.edu.cn/handle/20.500.11897/457077 。
3. Cai, Yin et al., TCOM 2016，[DOI:10.1109/TCOMM.2016.2578923](https://doi.org/10.1109/TCOMM.2016.2578923)：已核验作者机构库摘要中地铁被动测量、簇内/簇间统计与参数关联的方法方向；全文细节未核验。机构来源：https://portal.research.lu.se/en/publications/an-empirical-random-cluster-model-for-subway-channels-based-on-pa/ 。本V0没有簇追踪，不声称已建立该类随机簇模型。

## 10. 工程路线与后续验收

第一层为本次 SAGE 参数探索V0（完成并有局限），第二层为环境/几何/运动条件的初步探索（稳定共享/分层参数需更多场景证据），第三层等待Task5 CIR及Gate E/F，在完整精确窗口关联后分析CIR/PDP、Stage2选择效应、结构与时间演化。三层是同一工程递进路线。
Task5仅做小型audit/monitor和进程只读取样，记录在 `task5_readonly_snapshot.json`；生产代码、release、worker、Coordinator、监控、历史科学输出未修改。没有raw IQ/MAT/HDF5读取，没有MATLAB/SAGE/GNSS-SDR/CIR新执行。
后续最小步骤：Commander复核V0与候选差异 → Task5完成后独立Gate E/F → 精确关联完整CIR/PDP → 再评估共享条件模型、联合分布与完整结构模型。Phase-2生成AI未授权也未运行。
