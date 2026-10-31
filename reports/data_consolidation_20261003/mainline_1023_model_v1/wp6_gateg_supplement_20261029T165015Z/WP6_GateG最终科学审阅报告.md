# WP6 Gate G 最终科学审阅补充

**审阅日期：** 2026-10-30（Asia/Shanghai）
**Gate G 建议：`PENDING`（不接受为已验证的场景外联合生成模型）**
**WP6 状态仍为：`COMPLETED_WITH_LIMITATIONS`**

## 1. 范围与冻结输入

本审阅只使用冻结的 Stage2 轻量 CSV 与版本化 SAGE 源码；未读取 MAT/HDF5/raw IQ，未重跑 SAGE、CIR 或 alpha，也未启动生产计算。冻结输入为 13 个 scene、83 个 run、7,847 个 Stage2 已选窗口和 8,914 条 MPC。窗口及路径分别以 `(run_id, window_id)`、`(run_id, window_id, path_id)` 标识。所有计数与标记结论均条件于 Stage2 筛选；未将未选 Stage0 窗口补成零 MPC。

输入 SHA-256：

- `stage2_cir_pdp_window_features.csv`: `258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4`
- `stage2_mpc_cir_alpha_linkage.csv`: `8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b`

结果与折表位于本目录。原始分析包、输入、WP1–WP6 既有结果均未改写。

## 2. Gate G 相关问题的实际证据

### 2.1 Stage2 窗口计数条件的路径标记

已选窗口计数为 N=0/1/2/3：3,574 / 1,412 / 1,081 / 1,780。N=1、2、3 分别覆盖 13 个场景；每场景最少窗口数为 42、10、3。因此 N=3 支持明显偏稀，特别是场景层估计。

计数条件边际模型 M1 在完整外层 13-scene LOSO 中以训练场景内嵌套 LOSO 选族。N=2 的延迟族为 Lognormal 13/13；Doppler 为 Student-t 11/13、Normal 2/13；功率为 Student-t 11/13，另有 Laplace/Normal 各 1 折。N=3 的延迟为 Lognormal 7/13、Gamma 6/13；Doppler 为 Normal 13/13；功率为 Laplace 12/13、Normal 1/13。N=1 延迟的 13 个外层折均无可选择族，候选拟合触及参数下界，故 M1 对 1,412 条 N=1 MPC 无完整三变量评分。

在可完全配对的留出窗口上，M1−M0 场景宏平均对数评分差为 +0.119126 nats/MPC（12 场景为正、1 场景为负）；但这一总体配对排除了全部 N=1。按计数分层，N=2 差值 −0.005815（9 正/4 负），近于无改善；N=3 为 +0.202086（12 正/1 负），但低支持场景仅 3 窗口，且当前连续 Doppler 评分假设仍待复核。故这些是按已实现评分口径的探索性场景外证据，不能证明稳定的完整条件标记生成律。

路径秩诊断显示，N=2 和 N=3 相邻延迟秩在 13/13 场景均固定相差 0.1 chip，正好对应路径分离算法下限；相邻秩相对功率在所有场景均下降，N=2 的秩2−秩1场景中位差为 −7.88455 dB，N=3 为 −7.72253 dB；Doppler 秩差方向不稳定。`path_id` 是按估计延迟排序的算法组件秩，不是物理路径身份。以上反证了把多路径窗口路径集未经检验视为可交换/条件 iid 样本的做法；它不构成物理因果解释。

评分覆盖：M0 为 8,914/8,914 MPC；M1 为 7,502/8,914，未评分部分正是 N=1 的 1,412 条。因而“场景宏平均有 13 个场景得分”不应被误读为每一计数层在每个场景均可估计。

### 2.2 量化时延与 Gaussian Copula

时延 CSV 值位于 0.01-chip 网格，最小值 0.10 chip。实现使用离散格点 Voronoi 单元概率而非连续点密度：对格点 d，单元下界 `max(0.10, d−0.005)`、上界 `d+0.005`，以连续候选族在该单元的 CDF 增量除以 `P(D≥0.10)` 作为格点概率。连续独立基线和 Copula 的时延部分因此以同一离散概率测度评分。

按本轮事先确认的“时延离散、Doppler/功率连续”实现，Copula 数值与独立基线的配对场景差为：C0−M0 −0.007903 nats/MPC（10/13 场景为正）；按计数的 N=1、2、3 分别为 −0.195253、+0.003295、+0.127825。C1−M1 总体为 −0.007115（11 正/2 负），但 N=2 为 −0.151508（10/3），N=3 表面为 +0.422422，只有 8/13 场景可评分且这 8 个均为正；其余 5 个 N=3 外层 Copula 拟合失败。随机化 PIT 敏感性 416 次成功抽样的增益中位数 +0.07079，5–95% 抽样范围 [−0.34468, +0.11381]；这是随机化敏感性范围，不是置信区间。

**新发现的评分前提问题：** 当前仓库的 Mainline SAGE 配置 `scripts/sage_pipeline/core/default_sage_configuration.m` 将 `localDopplerStepHz` 设为 5 Hz，Stage2 局部路径细化代码在 `run_sage_stage1_stage4_core.m` 中使用该步长（审阅时文件 SHA 见 `doppler_5hz_lattice_screen.json`）。该来源检查本身不证明历史每个 run 均使用了同一文件 SHA。对冻结 MPC CSV 按窗口检查相对 Doppler：在 2,861 个 N>1 窗口中，以该窗口首个值作为相位原点，2,753 个窗口（96.225%）的全部路径值与同一相位偏移的 5-Hz 格点一致至 `1e-6` Hz；108 个窗口不完全一致。相位原点随窗口变化，不能以一个全 cohort 固定格点代替。该检查只证明强烈的窗口内格点结构迹象，不单独确定每个窗口生成格点的精确原点，也不证明全部值严格由单一量化机制造成。复算摘要与命令输出见 `doppler_5hz_lattice_screen.json` 和 `doppler_5hz_lattice_screen_20261030T013915.log`。

因此，当前 Copula 计算虽已正确处理时延 ties，但仍把 Doppler 当作连续密度；若 Doppler 的观测机制确为带窗口特定原点的 5-Hz 搜索格点，该评分也不是正确的离散—连续似然。C0/C1 及相关 M1 场景外分数应保留为**连续 Doppler 近似下的诊断结果**，不可据此判定 Copula 有收益或无收益。当前证据不足以确定离散 Doppler 单元边界、每窗口格点原点，以及 108 个不完全吻合窗口的来源；不得按结果反推原点后再把该数据用于自己的评分。

## 3. 独立复核与可复现性

- 定向测试命令：`python -m unittest scripts.channel_modeling.tests.test_mainline_stage2_wp6_gateg scripts.channel_modeling.tests.test_mainline_stage2_wp6 -v`；2026-10-30 01:34:19.344 +08 至 01:34:26.061 +08；退出码 0；56 tests，全部通过。完整输出保存在 `targeted_tests_20261030T013419_plus0800.log`。其中包括 17 项 Gate G 专项测试及 39 项相关 WP6 回归。
- 独立验证器命令：`python scripts/channel_modeling/validate_mainline_stage2_wp6_gateg.py reports/data_consolidation_20261003/mainline_1023_model_v1/wp6_gateg_supplement_20261029T165015Z`；2026-10-30 01:28:32.795 +08 开始，01:30:58 +08 写入结果；退出码 0；39 项检查、0 失败，状态 `PASS_WITH_LIMITATIONS`。原始本地尝试记录为 `validation_attempt_20261029T172834757521Z.json`；可移植摘要为 `independent_validation_gate_g.json`。输入 SHA 与上方一致；M0/M1/C0/C1 重算数量分别为 8,914 / 7,502 / 8,914 / 5,375；最大逐路径评分绝对差分别为 `7.11e−15` / `7.11e−15` / `1.21e−13` / `1.60e−14`。此验证确认实现与保存表格算术/身份一致，不验证连续 Doppler 测度是否符合量化观测。
- 从留出路径/窗口表独立重聚合的场景配对摘要共核对 156 个单元格，最大绝对差 `1.33e−15`；窗口/场景支持为 4,273 个有 MPC 的选中窗口、13 个场景。此为算术复核，不是新的独立样本实验。
- 原始本地执行和输入/输出 manifest 保留在工作树中；其中含有机器绝对路径，不纳入共享提交。可移植的相对路径与 SHA-256 清单为 `portable_result_manifest.json`。运行时绑定的分析模块、runner、WP3 helper SHA 与原始本地输入清单吻合；验证器在运行后修订过，验证摘要同时保存原分析清单中的 validator SHA `3933851f…` 与实际 validator SHA `3463a82a…`，未将后者伪称为分析运行时源码。
- 更早的三次验证失败仍保留：一次 Pandas 字段 `AttributeError`、一次 C1 预期 NaN/可评分项对账失败、一次 held-out window identity/count 对账失败。可移植摘要为 `validation_history_gate_g.json`；原始本地记录未覆盖。之后两次验证成功，最终完整 39 项结果见 `independent_validation_gate_g.json`。

## 4. 最终科学判定

本轮支持的是：Stage2 已选窗口内的经验计数分布；候选 M0 边际族稳定性描述；以及采用量化时延单元、但将 Doppler 近似为连续变量时可复算的复合评分。M1 暴露出明显的计数层差异和 N=1 延迟拟合失败；窗口内按延迟排序的路径标记并不满足未经检验的交换性假设。

**未获得可用于定案的场景外 Copula 证据。** 时延测度已修正，但 Doppler 5-Hz 窗口相位格点尚未建模；Copula 优化失败、N 层覆盖差异及 LOSO 训练集重叠仍须保留。因而当前结果既不证实 Copula，也不否定 Copula。

尚未验证的对象包括：完整有序多路径窗口联合似然、所有路径的条件 iid 生成假设、Stage2 选择机制之外的无条件多径概率、跨窗口复数 alpha 相位相干、绝对接收增益、SAGE 参数到 CIR 的独立物理真值关系及连续物理反射体跟踪。Gate F 的数值一致性不等于这些联合生成能力已验证。

## 5. Gate G 决策与唯一下一步

**Gate G：`PENDING`。** WP6 仍为 `COMPLETED_WITH_LIMITATIONS`；本轮补充分析与数值复核通过，但未达到“一个经过完整场景外评分验证的联合生成模型”的科学验收条件。论文可以报告计数条件支持、边际稳定性、路径秩诊断，以及上述诊断性 Copula 数值；不得将现有 Copula 排名表述为确认的预测收益或无收益。

**唯一下一步：** 从冻结 SAGE 搜索配置和逐窗口元数据独立确定相对 Doppler 的精确格点原点/边界；对 108 个不完全吻合窗口追查适用分支或边界行为；在不改变外层/内层完整场景留出划分的前提下，实施训练折内拟合的 ties-aware Doppler 单元概率，并仅对受影响的原配对比较进行复算。若无法从冻结算法和元数据确定格点原点，不以数据自身估计的 held-out 相位作评分依据，应保留 Copula 未验收结论。完成该项前不建议 Gate G 通过。
