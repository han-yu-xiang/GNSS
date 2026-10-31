# WP6 Gate G：Doppler 观测机制专项审阅

**审阅日期：** 2026-10-30（Asia/Shanghai）
**结论：** Doppler 输出存在算法诱导的自适应离散候选结构，但冻结结果不足以恢复外生、可用于场景外概率评分的精确观测单元；受影响比较未重算。**Gate G 继续 `PENDING`，WP6 继续 `COMPLETED_WITH_LIMITATIONS`。**

## 1. 范围与冻结证据

本审阅只处理 Doppler 搜索与联合模型评分，不重跑 WP6、SAGE、CIR 或 alpha，不读取 Stage2 MAT、HDF5、raw IQ 或 CIR 科学载荷。使用冻结 Stage2 linkage、Gate E run inventory，以及 108 个异常窗口对应的轻量 Stage0/Stage1/Stage2 CSV 和每个相关 run 的小型 `doppler_sign.mat` 配置/符号元数据。

- Mainline 总体仍为 83 runs、13 scenes、7,847 个 Stage2 已选窗口、8,914 条 MPC。筛查 2,861 个 N>1 窗口，其中 2,753 个相对 Doppler 差值可与窗口内某个平移后的 5-Hz 格点吻合，108 个不完全吻合。
- Stage2 linkage CSV SHA-256：`8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b`。Gate E inventory 与 83-run 来源账本核对；108 个异常窗口来自 24 个 run、9 个 scene。相关 24 个 run 的 Stage0/Stage2 CSV 实际 SHA 均匹配 inventory pin，Stage2 mapping 均为 PASS；Stage1 CSV 实际 SHA 也逐 run 记录在 `affected_run_input_manifest.csv`。
- 83/83 inventory 的 `frozen_sage_sha256` 均为 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`，与历史提交 `ab9dc4ee5f895a65ba3d5908ec666078d606d77c` 中 `scripts/sage_pipeline/run_nav_sage_pipeline.m` 的实际 SHA-256 一致。相关 24 个 run 的 24 份小型配置快照（总计 29,979 bytes）均记录 `localDopplerStepHz=5`、`localDopplerHalfWidthHz=30`、`scanResidualDopplerStepHz=50`、`maximumSageIterations=10`、`sageTolerance=1e-6`、`mainDopplerHalfWidthHz=125`、`scanMainDopplerStepHz=25`、`pipelineVersion=3`；24 个 `dopplerSignUsed` 均为 +1。没有发现这 108 个窗口对应的 run 之间存在配置分支差异证据。该 SHA 是冻结源码 pin 和配置快照的证据，并非对历史进程内存的直接取证。

未把 5-Hz 筛查的首个留出观测值当作评分原点。它只用于描述两条 MPC 之间的差值结构。

## 2. 冻结算法推出的观测机制

历史冻结源码的关键路径如下（行号对应上列固定提交）：

1. `fitAllOrders` 以 `dopplerSignUsed * Stage0.tracking_doppler_hz` 作为 `referenceDoppler`，并以 Stage1 主峰初始化直达分量；MPC 的逐阶拟合调用 `initializeResidualPath` 与 `runSage`（1211–1247 行）。
2. `initializeResidualPath` 使用上一个模型的直达 Doppler 为中心，候选为 `directDoppler + makeGrid(-B,+B,50)`，其中 B 是该 Stage0 窗口的速度条件边界（1281–1294 行）。因此 B 随窗口而变，起始候选也随上一个模型估计而变。
3. `makeGrid(min,max,step)` 先产生 `min + k·step`，再在 `max - last > 0.25·step` 时将 `max` 单独追加（2096–2106 行）。所以初始 50-Hz 网格仅当末端余隙大于 12.5 Hz 时才额外包含 `+B`；附加端点不保证处在规则 50-Hz 网格相位上。
4. `runSage` 最多执行 10 轮；每轮按路径顺序更新路径并重新估计复数幅度，RSS 相对变化满足阈值时提前停止（1314–1350 行）。Stage2 的 `refinePath` 对每条路径各做两次坐标更新；Doppler 候选围绕该路径当前估计值 ±30 Hz、裁剪到全局 `referenceDoppler ± B`，再以 5-Hz 步长调用同一个 `makeGrid`（1987–2021 行）。局部裁剪后的最大端点也可能因 1.25-Hz 余隙规则被额外追加。
5. 输出 `doppler_offset_hz` 是最终路径 Doppler 减去最终排序后第一条（直达）路径 Doppler（1487–1491 行）。从同一窗口所有绝对 Doppler 中减去同一个直达值会平移格点相位，但不会改变路径间差值；因此它本身不能解释窗口内不等距差异。它确实意味着相对 offset 的零点不是统一外生格点原点。
6. `refineJointPath` 也使用 `makeGrid`（1753–1792 行），但它属于 Stage4 多快照 joint 路径输出，不是 Stage2 `stage2_selected_paths.csv` 的生成路径，不能用它替代 Stage2 搜索历史。

由算法能推出的是：最终结果来自依赖先前估计、路径顺序、局部裁剪区间、模型阶数和停止轮次的离散候选搜索。它不是“一个连续潜在 Doppler 被固定 5-Hz 等宽区间量化”的简单测量机制。只有 `localDopplerStepHz=5` 并不能定义每个最终标记的概率单元。

## 3. 108 个不完全对齐窗口

独立重建使用每 run 的真实符号 `dopplerSignUsed`、Stage0 的速度边界 B、tracking Doppler、Stage1 主峰/残差候选，以及 Stage2 最终各路径绝对值和相对 offset。分类是基于冻结算法和保存结果的机制签名；源码没有保存逐路径逐轮搜索轨迹，故签名不等于完整的候选选择历史。

| 证据分类 | 数量 | 解释与证据强度 |
| --- | ---: | --- |
| 初始 50-Hz `makeGrid(-B,+B)` 按端点规则会追加 `+B`；最终 MPC offset 中有 `±B` | 105 | 与初始额外端点被保留或在后续局部搜索中再次选中的输出一致。结果表证明初始追加条件与最终端点值同时成立；未保存每轮候选索引，不能逐条证明最终值具体由哪一轮产生。 |
| 初始网格会追加 `+B`；最终不再有 `±B`，但规则格点相位与附加端点相位均出现在最终路径中 | 2 | 与额外端点在后续 5-Hz 局部更新中向内移动相符；具体路径、轮次与中间点不可由现存轻量结果唯一恢复，故是有依据的解释而非逐迭代证明。 |
| 初始网格不追加 `+B`，但最终路径落到真实全局 `referenceDoppler+B` | 1 | G19/ch11、window 4100：B=105.8697587655 Hz，初始末端余隙 11.739517531 Hz（≤12.5 Hz），所以初始 50-Hz 网格不含 `+B`；Stage2 最终 MPC absolute Doppler 为 −3408.435905297 Hz，等于 `tracking-reference + B`。这与后续裁剪局部网格追加上界的机制相符。精确中间迭代轨迹仍未保存。 |

汇总：N=2 有 28 个异常窗口，N=3 有 80 个；108/108 最终路径相位诊断同时包含 `−B mod 5` 规则支路和 `+B mod 5` 端点支路；105/108 有最终相对 offset 达 `±B`；1/108 有最终 absolute Doppler 达到真实 tracking reference 的全局边界；Stage1 residual peak 在其自身主峰 ±B 处出现的窗口有 14 个（仅作上游佐证，不当作 Stage2 轨迹证据）。108 个窗口的最大窗口内 5-Hz 配对残差最小值为 0.007399574 Hz、中位数 1.288325452 Hz、最大值 2.497763399 Hz；最小偏差已远高于 1e-6 Hz 筛查阈值，不是单纯浮点舍入噪声。没有放宽容差。

9 个受影响场景的异常窗口数：`F1023_V70_D0117_P4` 1；`F1023_V70_D0120_P1` 23；`F1023_V70_D0120_P5` 1；`F1023_V70_D0120_P7` 44；`F1023_V70_D0120_P8` 14；`F1023_V70_D0120_P9` 14；`F1023_V70_D0122_P1` 5；`F1023_V70_D0122_P2` 5；`F1023_v50_D0127_P1` 1。完整 108 个窗口、path IDs、最终值、边界和余隙见 `doppler_nonaligned_windows.csv`；逐场景计数见 `doppler_nonaligned_scene_summary.csv`。

**108 个窗口并非一个统一异常来源。** 现有证据可把 107 个窗口与初始化的额外端点分支联系起来，并把剩余 1 个联系到后续全局边界裁剪；但 2 个端点支路向内移动的确切迭代路径、以及其余端点最终由哪轮胜出，因缺少 Stage2 per-path/per-iteration 记录而不能进一步断言。路径不同的搜索中心、局部网格原点、模型阶数和迭代轮次都可能造成最终偏移差异。没有证据表明这 108 个异常由某个单一配置分支或浮点误差造成。

## 4. 观测单元和评分判定

**没有恢复出可用于本轮场景外模型比较的、外生且精确的 Doppler 概率单元。** 现有保存的 Stage0/Stage1/Stage2 CSV 和配置快照没有逐路径逐轮记录：每轮搜索中心、实际裁剪的候选向量、端点是否追加、候选得分、胜出索引、路径更新顺序/模型阶数和停止轮次。最终路径点本身只给出了算法输出，不能替代这些前置搜索状态。

解释范围要精确：若评分目标是“给定每个窗口实际候选搜索状态时，预测算法选择的离散 Doppler 输出”，连续 PDF 不是该候选选择的单元概率。另一方面，窗口间 B/参考/搜索状态变化可能使**跨窗口边际**成为平滑或混合分布；这意味着连续密度并非对所有可能 estimand 都天然错误。本次既有 WP6 scorer 没有定义或验证这个跨窗口、边际化搜索状态的替代目标，也没有显式建模共享搜索相位及同窗口聚类，因此原连续分数不能为本轮要求的条件测量机制或完整联合生成器提供决定性证据。它们的算术未被否定，但 Gate G 的预测解释必须降为近似诊断。

从留出 MPC 的最终值反推其 5-Hz 相位或 Voronoi 单元会把待评分结果用于定义自己的评分格点，形成结果依赖/泄漏；它不是独立元数据。即使补齐逐轮轨迹，若候选支持依赖同一留出 IQ 的前序估计，也必须把该自适应估计/选择过程纳入预测测度，或明确声明评分条件于一个可在结果出现前获得的搜索状态；不能把数据依赖状态冒充为外生协变量。

因此本轮**没有实施离散 Doppler 单元概率，也没有重新计算受影响 LOSO 分数**。这是对指定的条件观测机制评分 fail-closed；不意味着 Copula 无效，也不意味着所有平滑边际 estimand 均不可能。

受影响的既有比较包括：

- `product_mark_log_score` 将 delay 用格点质量评分，但把 Doppler 与相对功率作为连续密度相加；因此包含 Doppler 项的 M0/M1 路径分数、计数条件标记对比和模型族比较，都不能作为观察到的 SAGE 输出上的正确概率评分。M1 的 N=1 拟合失败仍是独立限制。
- 混合 Gaussian Copula scorer 对量化 delay 积分，但对 `MARK_VARIABLES[1:]`（其中包含 Doppler）使用连续 PIT/密度与 Copula 因子；C0/C1 的场景外 joint log-score、Copula 对独立基线的增益/损失以及依赖参数解释，仍是连续 Doppler 近似下的诊断，不得宣称有收益或无收益。
- 以连续 Doppler likelihood 选择 Normal/Student-t 的 Doppler 边际排名也只是平滑近似诊断，不能解释为离散 SAGE 输出测度下已校准的预测比较。

因此旧 paired 表中的 M1−M0 `+0.119126`、C0−M0 `−0.007903`、C1−M1 `−0.007115` nats/MPC **不能作为本轮条件 Doppler 观测机制下 Gate G 取舍的有效场景外证据**；这些是原连续-Doppler近似下仍可复核的历史算术，而非已证伪数值。M1 的 `+0.119126` 还只覆盖可配对的 N=2/3 MPC，排除了因拟合失败而无分数的 1,412 条 N=1 MPC。这里没有用新方法生成替代分数。

不受这一问题直接影响的是 Stage2 已选窗口条件下的经验计数频数/仅计数场景外分数、独立报告的 delay 0.01-chip 单元分数，以及单独且样本完全配对报告的 power-only 分数。它们不自动验证计数—标记条件独立、路径交换性或完整联合生成律。之前的连续 Doppler 汇总数字可以留作历史诊断，但其预测排名已失去正式验收效力；本报告不将它们重新包装为修正结果。

## 5. 可保留结论与 Gate G

可保留：Stage2 选中窗口中的经验计数统计；已正确用离散格点质量处理的 delay 结果；path_id 是延迟排序的 SAGE 组件秩而非物理路径身份；多路径窗口的路径标记存在顺序结构，不应未经验证按可交换或条件 iid 处理。N=1 的计数条件延迟拟合失败、N=3 的低场景支持及 LOSO 折之间训练集重叠限制继续成立。

不能保留为已验证结论：现有 Doppler 连续密度下的 Copula 收益/损失、包含 Doppler 的 M0/M1 场景外综合分数、计数条件标记不变性、完整有序窗口联合似然或经过验证的完整联合生成器。窗口归一化 alpha 的跨窗口相位相干、绝对信道增益和物理反射体跟踪也仍未验证。

**最终建议：Gate G 保持 `PENDING`。** 当前有足够证据确认算法观测机制是自适应离散搜索、并淘汰原综合连续 Doppler 评分的正式比较效力；但没有足够信息产生新的适当场景外依赖分数。计数与部分边际模型可作为 Stage2 选择条件下的有限统计描述，不等于通过完整联合生成器 Gate。

**下一步唯一优先事项：** 若仍要验收 Copula/联合生成能力，先取得或在经授权的新估计协议中保存可在留出结果前确定的 Doppler 搜索状态/候选支持，并定义该自适应 SAGE 输出机制下的预测概率测度；在此之前不继续重算旧 LOSO 分数。不要从现有 held-out Doppler 值估计格点后做自评分。

## 6. 可复核文件

- `analysis_summary.json`：总体数字、来源身份、配置快照、科学判定和受影响评分范围。
- `doppler_nonaligned_windows.csv`：108 个唯一窗口的逐窗证据与 path Doppler。
- `doppler_nonaligned_scene_summary.csv`：9 个 scene 汇总。
- `doppler_sign_metadata.csv`：24 个相关 run 的 sign 与冻结配置快照摘要（只读小型 MAT 元数据）。
- `affected_run_input_manifest.csv`：24 个相关 run 的 Stage0/Stage1/Stage2 CSV 与 sign 元数据 SHA-256。
- `execution_record.json`：实际命令类型、时间、输入身份和退出码。
- `independent_validation.json`：18 项定向独立数据/算术/来源及交付完整性检查，18/18 PASS；它不验证 Doppler 概率测度或完整模型泛化。
- `output_sha256_manifest.json`：对本结果包中其余文件的 SHA-256 与字节数清单，用于交付后完整性复核。

未修改任何 WP6/SAGE 科学代码或冻结数据；没有运行 SAGE/CIR/alpha 或整套 WP6，也没有读取大型科学载荷。初步统计曾把 Stage1 `main_doppler_hz` 错用作全局 tracking reference；该表未用于最终判断，最终 108 窗口报告按冻结源码规定使用 `dopplerSignUsed × Stage0 tracking_doppler_hz`，修正记录保存在 `analysis_summary.json` / `execution_record.json`。另一个早期独立表格校验因 PowerShell `Where-Object` 谓词书写错误产生 9/12 个假阴性；原始校验 JSON 保存在 `validation_attempt_20261030T154828_checker_syntax.json`，该失败尝试保留作审计记录。修正谓词后的最终独立校验为 18/18 PASS，未修改任何数据表。
