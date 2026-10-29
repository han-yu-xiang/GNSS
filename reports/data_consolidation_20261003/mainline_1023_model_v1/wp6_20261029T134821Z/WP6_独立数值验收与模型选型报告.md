# WP6 独立数值验收与模型选型报告

日期：2026-10-29（Asia/Shanghai）

结果目录：`wp6_20261029T134821Z/`

状态：模型分析已完成；增强后的独立身份/计数/延迟矩/PDP 分数核验 `PASS_WITH_LIMITATIONS`；独立科学/代码审阅完成并发现需限制解释的统计问题。WP6 可作为 `COMPLETED_WITH_LIMITATIONS` 候选研究结果；Gate G 仍 `PENDING`。

## 1. 输入与执行证据

仅使用 WP4 Gate E/F 已接受的两张冻结 CSV；未读取 HDF5、MAT、raw IQ，也未重跑 SAGE、CIR 或 alpha 导出。

| 输入 | 行数 | SHA-256 |
|---|---:|---|
| `stage2_cir_pdp_window_features.csv` | 7,847 | `258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4` |
| `stage2_mpc_cir_alpha_linkage.csv` | 8,914 | `8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b` |

总体为 83 个 run、13 个 scene、7,847 个 Stage2 已选窗口、8,914 条 MPC。7,847 个窗口中 4,273 个至少有一条 MPC，3,574 个窗口计数为零。窗口计数直方图为 0/1/2/3 = 3,574/1,412/1,081/1,780。零计数只表示该窗口已进入 Stage2 但账本中无 MPC；未选入 Stage2 的 277,905 个 Stage0 窗口没有补成零。

成功分析于 2026-10-29 21:48:24–21:55:18 +08（13:48:24–13:55:18 UTC）完成，Python 3.12.9，运行时间 414.1 秒。首次真实运行 `wp6_20261029T133421Z` 在计算完成后报告组装处因 runner 读取不存在的 `copula_minus_product_score` 字段失败；原失败目录和 traceback 保留。修复仅让 runner 从已有 Copula 与独立边际评分列推导差值，没有改变拟合或评分定义；成功运行写入本目录，不覆盖失败尝试。

## 2. 可操作模型及参数

### 2.1 Stage2 条件计数分量

对已入选窗口 (w\)，令 (N_w\in\{0,1,2,3\}\)。在每个训练折内，以训练 scene 的计数频率等权平均：

\[
\hat p_k=\frac{1}{S_{train}}\sum_{s\in S_{train}}\frac{n_{s,k}}{n_s},\quad
\hat p(N_w=k\mid w\text{ 被 Stage2 选中})=\hat p_k.
\]

不平滑训练折未观测类别。13/13 个外层留出 scene 均有可评分类别，场景宏平均留出 log-score 为 **−1.297385 nats/selected window**。这是 Stage2 条件经验模型，不估计所有 Stage0 窗口的无条件 MPC 发生率，也未证明 0–3 支持可外推至其他采集设置。

### 2.2 MPC 标记分量

对一条 Stage2 MPC 标记 (x=(\tau,\nu,p)\)，其中 \(\tau\) 为超额时延（chips）、\(\nu\) 为有符号相对多普勒（Hz）、\(p\) 为相对功率（dB），候选形式为独立边际乘积，或连续 Gaussian Copula：

\[
f_{\tau,\nu,p}(x)=c_R(F_\tau(\tau),F_\nu(\nu),F_p(p))
f_\tau(\tau)f_\nu(\nu)f_p(p),
\]

其中独立边际基线取 (c_R\equiv1\)。计数 (N_w=n\) 后，当前候选生成语义为给定计数的可交换/条件 iid 标记；这是未验证的简化假设，不是已验证的同窗 MPC 独立性，也未检验标记分布是否依赖 N。训练权重让 scene 等权、scene 内 MPC-bearing 窗口等权、同窗口内路径分摊该窗口权重；这是边际伪似然拟合权重，不是独立样本推断权重。外层 window score 对同窗口路径 log score 求和；尾部分位数诊断则按路径行未加权计算，二者目标量不同。

全体 13 scene 的内层 scene-LOSO 描述性重拟合选择及参数如下。它们不是外层场景预测参数的替代，也不带独立总体置信区间。

| 标记 | 全体内层选择 | 全体描述性拟合参数 | 外层 13 折选择稳定性 |
|---|---|---|---|
| 超额时延 | Lognormal | shape=0.510756；scale=0.192930 chips；loc=0；\(\mu_{\log}=-1.645426\) | 13/13 折选 Lognormal |
| 相对多普勒 | Student-t | df=8.172952；loc=0.759586 Hz；scale=61.776353 Hz | 13/13 折选 Student-t |
| 相对功率 | Normal | loc=−8.157576 dB；scale=6.826867 dB | 8 折 Student-t、5 折 Normal；家族稳定性不足 |

每个外层测试 scene 均完全排除在其参数拟合、内层家族选择和 Copula 估计之外。13 个 LOSO 外层训练集合高度重叠，因此 13 折不是 13 次独立实验。

内层 1,404 条候选拟合记录中保留 6 条 `FAILED_OPTIMIZER`：超额时延 Weibull 4 条、相对功率 Student-t 2 条，优化器消息为 `ABNORMAL:`。未把这些失败记作低分或 PASS；受影响候选在相应完整性要求下不参与该折的可选家族集合。它们提示家族排名受优化稳定性影响，特别是相对功率不应宣称有稳健唯一家族。

## 3. Gaussian Copula 输出的独立审阅：不得作为有效场景外排名

程序在同一组 4,273 个 MPC-bearing Stage2 窗口上记录了以下连续边际/连续 Copula 分数：窗口内先对路径 log density 求和，再 scene 等权宏平均。原始数值保留，但不解释为有效 Copula 预测比较。8,914 条时延值只有 128 个不同浮点值，按 0.01 chip 四舍五入后 127 个值，且量化误差最大约 1e−15。当前实现将 Kendall tau-b 套用连续无 ties 关系 \(\rho=\sin(\pi\tau/2)\)，并对连续边际 CDF 点值计算 Copula 密度；这不是该量化时延的离散—连续混合 proper likelihood。差值与图仅为实现诊断，不能据此选型或声称有/无场景外收益。任何 Gate G 依赖前须经批准采用并验证适合并列/量化观测的评分方法。

| 连续点密度诊断（不作模型排名） | scene 宏平均输出值（nats/window） |
|---|---:|
| 独立边际乘积 | −16.189601 |
| 场景平衡 Gaussian Copula | −16.291071 |
| Copula − 独立边际（正值有利于 Copula） | **−0.101470** |

原始输出中 10/13 个 scene 的差值为正，3 个 scene 为负；差值中位数 +0.400870，范围 −3.057386 至 +0.628624。由于上述 ties 问题，这些方向比例和差值也不作场景外预测结论。**当前不把 Copula 纳入默认模型**，理由是其评分未通过适当的 ties-aware 验收，而不是将原差值视为可靠的“未改善”证据。

全体重拟合 Copula 的描述性相关矩阵（顺序为时延、多普勒、相对功率）为：

\[
R=\begin{bmatrix}
1 & 0.0070 & -0.6341\\
0.0070 & 1 & 0.0462\\
-0.6341 & 0.0462 & 1
\end{bmatrix}.
\]

该连续 Copula 的描述性相关矩阵及 scene 内 Kendall 统计受时延并列值影响，参数只能作为探索摘要；不可据此宣称校准完成的可迁移依赖结构、因果或物理机制。

尾部表保留 234 条诊断（13 scene × 3 标记 × 6 分位数），其中 **72 条 `LOW_SUPPORT`**、162 条描述性诊断。每个标记的低支持数在 p01/p05/p95/p99 分别为 10/2/2/10；p10/p90 无低支持标记。阈值按预期尾部行数 <10 定义，但路径行有同窗聚类，行数不能视为有效独立样本量；即使标成 `DESCRIPTIVE_DIAGNOSTIC` 也不构成尾部校准通过或独立覆盖保证。

## 4. 与 CIR/PDP 的单独窗口级场景外关联

保留 7,847 个窗口，包括零 MPC 窗口与 63 个 PDP 延迟网格边界峰。使用 SAGE 相对功率加权超额时延矩作为单一预测量；模型为只用训练 scene 的截距均值基线与线性回归。该步骤不把 PDP 输入路径标记拟合，也不做未经验证的 SAGE→CIR 物理重构。

| 留出目标 | Intercept 宏平均 RMSE | 线性宏平均 RMSE | 差（线性−基线） | 线性 RMSE 更低的 scene |
|---|---:|---:|---:|---:|
| PDP code-delay RMS width（samples） | 2.485324 | 2.446555 | −0.038769（约 −1.56%） | 10/13 |
| PDP peak−SAGE direct delay（samples） | 4.298158 | 4.290361 | −0.007798（约 −0.18%） | 6/13 |

第一个目标显示小幅场景外误差下降，第二个没有稳定优势；这属于共享原始测量/追踪链的内部关联，不是独立信道真值验证。窗口重叠且 LOSO 训练集合重叠，不能由窗口多推导显著性或强泛化保证。PDP RMS 是 code-delay 相关宽度，不是已验证的物理多径 RMS 时延扩展。

## 5. 可保留的最终基线与不支持的结构

建议的最简可复现候选基线（不是已验收完整生成器）是：

1. Stage2 已选窗口的等 scene 经验计数概率；
2. 给定计数的共享标记边际候选：超额时延 Lognormal、相对多普勒 Student-t；相对功率暂以 Normal 为描述性主候选，但 Normal/Student-t 场景稳定性为 5/13 对 8/13，不应称为稳定唯一家族；
3. Gaussian Copula 暂不纳入默认组件，因为时延并列值使当前连续评分无效，不能据此完成科学排序；
4. CIR/PDP 只作为独立窗口级响应/描述统计，不与复数 alpha 拼接成未经证明的相干信道生成器。

此因子化候选依赖明确的 **Stage2 选择条件**、标记分布不随窗口计数变化以及给定计数后可交换/条件 iid 等尚未验证假设，故不应称为已验证的完整联合生成器。它不预测未选择 Stage0 窗口的 MPC、不产生绝对接收功率或校准增益、不证明跨窗口 alpha 相位相干、不追踪物理反射体、不验证传播真值，也不保证其他采集环境的覆盖。

### 最终数学参数（全体拟合，描述性）

- \(\tau\sim\mathrm{Lognormal}(\mu=-1.645426,\sigma=0.510756)\) chips，等价 scale=0.192930、loc=0；
- \(\nu\sim t_{8.172952}(\mathrm{loc}=0.759586,\mathrm{scale}=61.776353)\) Hz；
- (p_{dB}\sim\mathcal N(-8.157576,6.826867^2)\) dB；
- (N\sim\hat p_k\) 为上文 Stage2 选择条件的经验分布；默认 (f(\tau,\nu,p)=f_\tau f_\nu f_p\)（Copula 不作默认）。

这些全体参数是 deployment candidate 的完整总体重拟合，不是独立预测参数或后验/抽样不确定性区间；复数 alpha 未输入拟合。相对功率与 alpha 的同窗关系仍为 WP5 数据定义，不把相对量转换成绝对增益。

## 6. 独立数值验收、测试与复现

增强独立验证器不导入 WP6 拟合模块，结果为 `PASS_WITH_LIMITATIONS`：7,847 窗口、8,914 MPC、13 scene、4,273 MPC-bearing 窗口、3,574 零 MPC 入选窗口、63 边界峰均对账；延迟矩独立重算最大绝对误差：centroid `3.55e-15` samples、RMS `1.78e-15` samples、直接路径加 MPC 相对功率和 `5.68e-14`。此外，7,847/7,847 count window keys 的 source scene 和 held-out scene 均核对一致；52/52 PDP scene/model/target 的 MAE、RMSE 从逐窗口预测独立重算，最大绝对差 `1.78e-15`，summary 宏平均已对账。验证器不独立重拟合边际密度或校正连续 Copula 对并列时延的 likelihood；这些科学限制由独立审阅明确识别。测试通过不单独证明科学模型。

2026-10-29 最终定向 WP6 测试 33/33 PASS；全 channel-modeling 测试 216/216 PASS；`py_compile` exit 0。增强验证器的 count-scene 与 PDP-score 两个回归，以及新增的“不可评分多路径窗口仍按窗口唯一输出”回归均通过。后者先以真实 `MergeError` RED 复现，再修复为先按窗口去重、再关联 `path_n`；当前全量数据 13/13 外层 mark scene 均可评分，失败分支不在这次真实结果中触发，因此无需重算科学表。最终独立数据复核见路径净化摘要 `independent_validation_review_20261029_git.json`；命令、UTC 时间、退出码和原始绿色测试日志见 `targeted_regression_evidence.md`。此前 32/32、215/215 记录保留为该边界修复前的验证，不作为最终测试数。测试只证明相应代码行为，不替代科学解释。

结果表、分折/逐窗口预测、参数、尾部、失败记录和图表见本目录；程序为：

- `scripts/channel_modeling/mainline_stage2_wp6.py`
- `scripts/channel_modeling/run_mainline_stage2_wp6.py`
- `scripts/channel_modeling/validate_mainline_stage2_wp6.py`
- `scripts/channel_modeling/tests/test_mainline_stage2_wp6.py`

Gate G 仍 `PENDING`。WP6 研究结果可归档为 `COMPLETED_WITH_LIMITATIONS`，但只作为 Stage2 条件经验计数加描述性边际和独立窗口级 PDP 关联的候选。相对功率 Normal/Student-t 家族未决；Copula 的连续 score 不可用于模型排名；count-mark 因子化/标记同分布假设未验证。因此不宣称完整联合生成器通过 Gate G，也不自动开始 Phase-2、alpha/CIR 物理重构或生产计算。

## 7. 独立科学/代码审阅结果与 Gate G 建议

独立只读审阅的关键结论：

1. **Copula 评分无效于当前量化时延。** `excess_delay_chips` 只有 128 个不同值，按 0.01 chip 四舍五入后 127 个值。将 Kendall tau-b 套用连续变量的 `sin(pi*tau/2)` 关系并对 CDF 点值算连续 Copula 密度，没有处理离散—连续混合概率。因此原 Copula−product 差值 `−0.101470 nats/window` 和逐 scene 符号都降为实现诊断，不支持“有收益”或“无收益”结论；以 `INSUFFICIENT_EVIDENCE` 处理。
2. **相对功率分布选择不稳定。** 外层选择为 Student-t 8/13、Normal 5/13；全体 Normal 是描述性候选，不是稳定普适选择。多数候选 score gap 较小，2 个 Student-t 拟合失败，4 个 Weibull 时延拟合失败；失败保留，失败原因 `ABNORMAL:` 信息有限。
3. **当前计数与标记只是因子化基线。** 模型没有检验 path-mark 边际是否随同窗 MPC count 1/2/3 变化；给定计数后共享标记分布为未验证假设，不能声称是已验证完整 joint generator。描述性路径均值按 count 有变化，但嵌套窗口与 scene，不视作独立统计证据。
4. **三个评分/估计目标有差别。** 边际拟合按 scene/window 平衡并在窗口内分摊路径权重；外层 window score 累加同窗路径分数后对 scene 宏平均；tail quantiles 对 MPC 行不加权。必须分别称为不同 estimand，禁止以行数代替有效独立样本量。
5. **独立数值复核未发现已保存表的对账错。** 计数窗口与其源 scene/外层 fold 7,847/7,847 一致；52/52 PDP scene/model/target MAE/RMSE 从 window predictions 重算通过，最大差 `1.78e-15`。这些一致性检查不修复 Copula 方法限制，也不验证窗口重叠独立性。
6. **额外验证失败分支的路径粒度。** 新增的强制拟合失败多路径夹具先复现 `one_to_one` merge 因 MPC 行重复窗口身份而报错；修复后不可评分记录仍一窗一行并保留正确 `path_n`。该分支未在实际 13 个可评分外层 scene 中触发，既有真实分析结果未因此变化。

**Gate G 建议：保持 `PENDING`，当前不通过完整 joint generator 验收。** 唯一优先的后续决策是 Commander 决定是否单独授权：(a) 对 0.01-chip 量化时延实现并验证 tie/discretization-aware 的依赖估计与 proper scoring；(b) 以场景为单位检验 count-conditional mark invariance。未经该授权不增加模型、不进入 Phase-2、不启动任何生产。
