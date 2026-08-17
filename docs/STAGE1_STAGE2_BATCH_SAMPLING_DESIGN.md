# Stage1/Stage2 批量采样与窗口选择设计

## 0. 文档状态与边界

本文是设计文档，不是算法实现。生成本文件时只读取了：

- `scripts/sage_pipeline/run_nav_sage_pipeline.m`；
- `docs/WAVE2A_G11_QA_REPORT.md`；
- reference scene 的 `reference_scene_final_validation_report.md`、`reference_prn_analysis_report.md` 及已有 Stage0–Stage4 结果；
- `docs/WAVEA_10MHz_VALIDATION_REPORT.md`；
- `docs/MULTIPATH_EVENT_DATABASE_DESIGN.md`、`docs/BATCH_SAGE_DRY_RUN_DESIGN.md`；
- reference/current scene 的 Stage0、卫星几何和结果文件结构。

没有运行 MATLAB/SAGE，没有修改 Pipeline、scene、metadata、inventory 或已有结果。本设计不改变当前 `nav_sage_v2` 结果的解释，也不授权任何新的 SAGE 运行。

## 1. 决策摘要

建议将未来生产运行分成两个明确模式：

| 模式 | Stage0 | Stage1 | Stage2 | 用途 |
|---|---|---|---|---|
| `full-scan` | 保留全部有效 NAV symbols 和全部完整 40 ms windows | 扫描全部 Stage0 windows | 按现有 Pipeline V3 规则只处理 Stage1 候选，仍评估 L=1–4 | reference scene、论文/算法验证、采样策略回归金标准 |
| `batch-sampled-v1` | 仍保留全部 Stage0 windows | 对可复现的分层样本和候选 guard band 扫描，默认上限 1,200 个窗口 | 只处理已经有完整 Stage1 结果的候选及其相邻闭包，保持 L=1–4 | 多 scene 生产统计的候选方案，必须先通过回归验证 |

推荐的第一版生产采样配置如下：

- `N0 <= 1,200` 时默认使用 `full-scan`，避免对短场景人为降低覆盖率；
- `N0 > 1,200` 时 `batch-sampled-v1` 的 Stage1 总窗口上限为 **1,200**，包括初始样本和后续 guard/触发扩展；
- 初始代表性样本目标为 **800** 个窗口；预留最多 **400** 个窗口给 Stage1 候选的相邻闭包、短时 burst 和风险触发扩展；
- 时间分层使用 24 个等时/等窗口序列层，每层至少 20 个窗口；
- 每个实际存在的 elevation group 至少 20 个窗口；C/N0 低、中、高三个分位层各至少 20 个窗口；
- Stage2 保持当前 Pipeline V3 的 `maximumBaseCandidates=24`、`neighborRadius=2`，理论上最多 120 个 Stage2 candidate windows、最多 480 个 L1–L4 model evaluations；若闭包无法在预算内完成，任务必须标为 `sampling_inconclusive` 并升级为 full-scan，不能静默丢弃候选。

**Wave-2A 剩余任务建议：先暂停自动继续，等待采样策略完成离线覆盖验证和独立实现验证。** G11 可以作为已经完成的 full-scan 金标准保留；如果有必须继续 Wave-2A 的外部进度要求，只能由人工逐任务批准、仍按现有 full-scan 串行运行，不能现在直接切换为未经验证的 sampled 模式，也不能并行运行。

## 2. 当前规模问题的实际证据

### 2.1 Pipeline V3 的实际处理结构

当前 `run_nav_sage_pipeline.m` 明确执行：

1. Stage0 从连续有效 NAV telemetry/tracking 记录构建完整 symbol catalog 和 40 ms window catalog；
2. Stage1 调用 `runFastScan(windowCatalog, ...)`，默认遍历整个 `windowCatalog`；
3. Stage1 通过 residual peak 结果调用 `chooseStage2Candidates`；
4. Stage2 对 candidate windows 逐个执行 L=1、2、3、4 模型；
5. Stage3 在 Stage2 fits 中按窗口 ID 的 `±2` 邻域检查路径持续性，要求最小连续长度 3；
6. Stage4 对可靠中心使用 5 个 20 ms snapshot 做 joint 100 ms estimation。

当前配置中与采样设计直接相关的值是：

- `minimumCn0DbHz=30`；
- `maximumBaseCandidates=24`；
- `minimumBaseCandidates=8`；
- `neighborRadius=2`；
- `persistenceRadius=2`；
- `persistenceMinimumConsecutive=3`；
- `jointSnapshotCount=5`；
- `maximumJointCenters=8`。

Stage0 window CSV 已经包含可用于低成本分层的字段：`window_id`、`recording_time_s`、`tow_s`、`tracking_doppler_hz`、`code_frequency_hz`、`cn0_db_hz`、`vehicle_speed_kmh`、`speed_source` 和 `relative_doppler_bound_hz`。卫星几何 timeseries 的实际字段为 `utc_time`、`prn`、`elevation_deg`、`azimuth_deg`、`snr_db_hz`、`elevation_group` 等；summary CSV 是 run/PRN 层摘要，不能直接冒充事件中心的瞬时 elevation。

### 2.2 已有结果的规模对照

| 运行 | Stage0 symbols | 40 ms windows | Stage1 扫描 | Stage1 candidates | Stage2 evaluations | 观测耗时 |
|---|---:|---:|---:|---:|---:|---|
| reference G11 | 1,177 | 1,175 | 1,175 | 101 | 404 | Stage1 约 27.5 min，Stage2 约 40.4 min（由 artifact 时间戳估计） |
| Wave-2A G11 | 15,224 | 15,210 | 15,210 | 67 | 268 | Stage1 约 8.1 h，Stage2 约 11.4 h，总计约 19.6 h |

Wave-2A G11 的候选数反而低于 reference G11，但全量 Stage1 仍要扫描 15,210 个窗口；这说明主要瓶颈不是单纯的 Stage2 candidate 数量。长 raw IQ、外部存储和 I/O 可能影响耗时，但现有 QA 没有完成 profiler，不能把它们断言为唯一根因。

同时，现有 batch plan 对该任务使用约 1,175 windows 的低置信度 reference prior，而真实结果为 15,210 windows。因此未来 plan 必须把窗口数估计误差和采样模式明确记录，不能继续把 reference prior 当作生产预算。

## 3. 采样设计必须遵守的算法约束

### 3.1 Stage0 全量保留

Stage0 是后续所有窗口、时间、TOW、CN0、速度和几何关联的母表。即使 Stage1 采用采样，仍必须：

- 生成并保存全部有效 NAV symbols；
- 生成并保存全部完整 40 ms windows；
- 为每个窗口保留 `window_id` 和 `sample_start_zero_based`；
- 保留 `cn0_db_hz`、`vehicle_speed_kmh`、`relative_doppler_bound_hz` 等低成本上下文；
- 让 sampled 结果可以回到同一次 Stage0 catalog，而不是重新编号窗口。

不能因为窗口没有进入 Stage1，就从 Stage0 删除它，也不能把“未扫描”写成“Stage1 failed”。

### 3.2 Stage1 未扫描状态必须显式表示

当前 Pipeline V3 的 `stage1Table` 默认与 `windowCatalog` 等长，并用 `scan_valid` 和 `error_message` 表示扫描结果。未来 sampled 实现必须增加明确的状态，例如：

- `scan_status=sampled_scanned`；
- `scan_status=guard_scanned`；
- `scan_status=not_selected`；
- `scan_status=failed`。

`not_selected` 不能写成 `scan_valid=0`，否则 Pipeline 会把正常的采样缺口当成失败并产生错误告警。每个运行必须保存完整的 `sampling_plan`，包括已选和未选窗口。

### 3.3 Stage2 与 Stage3 的相邻窗口闭包

Stage2 不是任意稀疏窗口拟合：Stage3 会从 `center_window_id ± 2` 查找邻居，并要求至少 3 个连续匹配。因此：

- 一个 Stage1 candidate seed 不能直接进入 Stage2；
- candidate seed 的 `±2` 邻域必须先完成 Stage1；
- 进入 Stage2 的窗口必须有完整 Stage1 主路径和 residual screening 字段；
- Stage2 candidate set 必须保存连续窗口闭包，不能只留下 seed；
- 如果邻域缺失或预算耗尽，不能把中心标为 rejected 或 LOS，应标为 `sampling_inconclusive` 并触发局部 full-scan/任务升级。

Stage4 的 5 个 snapshot 来自完整 Stage0 symbol catalog，但这不能弥补 Stage3 缺失的相邻 Stage2 fits。

## 4. `full-scan` 模式定义

`full-scan` 是当前已经验证过的模式，定义为：

- Stage0：全部有效 symbols 和全部 40 ms windows；
- Stage1：`stage1_nav_fast_scan.csv` 对所有 Stage0 windows 逐行扫描；
- Stage2：使用当前 `chooseStage2Candidates`，对 Stage1 candidate 和 `neighborRadius=2` 邻域执行 L1–L4；
- Stage3：使用当前 `persistenceRadius=2`、最小连续数 3；
- Stage4：使用当前 5-snapshot joint 100 ms 逻辑；
- `sampling_mode=full-scan`、`unscanned_window_count=0`。

reference scene 七 PRN、论文中的算法对照、sampling policy 的 gold baseline 都必须使用 full-scan。已有 `G06_nav_sage_v1` 和 reference 的 `nav_sage_v2/Gxx` 不得重跑覆盖；任何新的 full-scan 对照必须使用新的、明确版本化的输出目录。

## 5. `batch-sampled-v1` 推荐策略

### 5.1 预算和最低样本数

以下数值是第一版建议值，必须通过第 8 节的回归实验后才能冻结为生产规则：

| 分层/预算 | 推荐值 | 说明 |
|---|---:|---|
| Stage1 总上限 | 1,200 windows | 包括初始样本、guard 和自适应扩展 |
| 初始 Stage1 目标 | 800 windows | 在看到 Stage1 residual 结果前完成 |
| 时间层数 | 24 | 按归一化 recording time/window index 分层 |
| 每个时间层最低样本 | 20 | 至少 480 个窗口；层内不足 20 时取该层全部窗口 |
| elevation group 最低样本 | 每个实际存在的 Low/Mid/High 组 20 | 最多增加 60 个；没有可靠 window-level geometry 时不伪造分组 |
| C/N0 分层 | P0–P20、P20–P80、P80–P100 | 每层最低 20 个，共 60 个；阈值来自全量 Stage0，不来自 sampled 子集 |
| 短时 burst 保留 | 每个时间层 1 个确定性 11-window block（可用时） | 中心 ±5，最多 264 个窗口，和其他层重叠时去重 |
| 自适应/guard 预算 | 最多 400 个窗口 | 优先覆盖 Stage1 candidate 的 ±2，再覆盖高风险 burst ±5 |
| Stage2 base candidate | 当前最多 24 个 | 不改变 Pipeline V3 参数 |
| Stage2 candidate 闭包 | 当前理论最多 120 个窗口 | 24 个 seed × `2*neighborRadius+1`，重叠去重 |
| Stage2 模型评估上限 | 480 | 120 candidate × L1–L4 |

这些层是集合的下限，不是简单相加的固定配额；同一个窗口可以同时满足时间、elevation、C/N0 和 burst 条件。最终集合不得超过 1,200。对于不足以满足最低数的场景，取可用窗口全部样本并记录 `stratum_underfilled`，不能复制窗口或用其他时间段冒充。

### 5.2 可复现选择顺序

所有选择都以 Stage0 window catalog 按 `window_id` 升序作为唯一基准。推荐顺序如下：

1. **建立窗口母集。** 只从完整 Stage0 windows 选择，记录 `sampling_universe_count=N0`。
2. **生成时间层。** 优先使用 `recording_time_s`；存在时间断裂时，同时保存基于 `window_id` 的 fallback。将场景分成 24 个等序列层，层内用确定性等距 rank 选择至少 20 个窗口。
3. **加入短时 burst。** 每个时间层选一个由 `SHA-256(scene_id|PRN|profile_version|time_bin)` 决定的中心，加入可用的中心 ±5 窗口。该 block 用于提高对短暂、局部事件的覆盖，不代表已经发现多径。
4. **加入 elevation 层。** 用卫星 geometry timeseries 的 `elevation_group` 或数值 elevation 进行 window-level 时间 join；Low/Mid/High 每组至少 20 个。只使用已验证的 UTC 对齐；不能只按 PRN 和 geometry summary 均值关联。
5. **加入 C/N0 层。** 使用全量 Stage0 `cn0_db_hz` 的 P20/P80 阈值，把有效 windows 分成低、中、高三层，每层至少 20 个。C/N0 不足或全相同要记录 warning。
6. **补足初始预算。** 从尚未选择的窗口中使用固定步长的系统网格，再用固定 seed 的 hash-reservoir 补足到 800；seed 必须写入 `sampling_plan.json`，不能使用当前时间或 MATLAB 随机状态。
7. **运行初始 Stage1。** 只扫描初始集合，输出中显式区分 `sampled_scanned` 和 `not_selected`。
8. **确定 Stage1 candidate seed。** 对已扫描行使用现有 Pipeline V3 的 validity、residual peak 和 score 规则；不把未扫描行参与排名，也不把它们当成低分窗口。
9. **补齐 candidate guard。** 对每个进入 Stage2 排名的 seed，优先扫描缺失的 `window_id ± 2`；对高风险 seed 可在剩余预算内扩展到 ±5。所有扩展窗口必须有 Stage1 结果后才允许进入 Stage2。
10. **执行 Stage2。** 只对 Stage1 完整且满足 candidate/guard 闭包的 windows 评估 L1–L4。若候选闭包超过 120 或 1,200 Stage1 预算，保持 checkpoint 并将该任务升级为 full-scan，而不是截断低排名候选。
11. **执行 Stage3/Stage4。** 只对完整邻域的 Stage2 fits 执行现有逻辑。对因 sampling 缺口无法判断的中心标记 `inconclusive_due_to_sampling`，不能标为 rejected 或 LOS。

### 5.3 低成本风险指标

以下指标均可以在 Stage0/几何 join 阶段获得，不需要读取 raw IQ 做相关运算：

- `cn0_db_hz` 的绝对分位和相邻窗口变化；
- elevation group 转换、elevation 梯度和低仰角窗口；
- `vehicle_speed_kmh` 及其变化；
- `relative_doppler_bound_hz`、tracking Doppler 的变化；
- Stage0 的连续性边界、时间断点和场景首尾窗口；
- geometry 的 `snr_db_hz`，与 tracking C/N0 保持不同字段和不同语义。

这些指标只能用于提高采样覆盖，不是多径标签。建议把风险窗口按标准化 rank 排序，而不是现在就增加未经验证的硬阈值；所有阈值或 rank 规则必须进入 profile version。

### 5.4 elevation 时间关联规则

当前 geometry timeseries 使用 `utc_time`，而 Stage0 window 主要使用 `recording_time_s`/`tow_s`。在 sampled 选择和后续数据库入库前必须生成显式映射表，至少包含：

- `window_id`、`recording_time_s`、`tow_s`；
- `geometry_source_utc`、`geometry_time_delta_s`；
- `elevation_deg`、`azimuth_deg`、`snr_db_hz`、`elevation_group`；
- `geometry_join_method`、`geometry_join_valid`、`geometry_scope`。

如果没有经过验证的 UTC 锚点，只能使用时间层和 Stage0 C/N0；不得用 PRN 的 geometry summary 均值把所有窗口标成同一仰角，也不得因 geometry 无法对齐而静默删除任务。

## 6. 短时多径事件的漏检控制

### 6.1 能做的保护

当前 Stage3 的最小持续性是 3 个连续 40 ms windows，Stage4 使用 100 ms joint snapshots。为保护这类事件，sampled 模式必须：

- 对所有 Stage1 candidate seed 扫描并保存 `±2` guard；
- 对高风险 seed 尽可能保存 `±5` extended burst；
- 保留每个时间层的确定性 11-window burst；
- 事件中心附近一旦发现 candidate，优先消耗扩展预算，不先扫描无关长尾窗口；
- guard 不完整时将结果标为 sampling 不充分，而不是 negative。

### 6.2 不能承诺的内容

稀疏采样无法数学上保证捕获一个与 CN0、仰角、速度和 residual screening 均无相关的单个 40 ms 窗口。即使事件满足 Stage3 的最小三窗口持续性，系统网格仍可能跨过整个事件。因此：

- `batch-sampled-v1` 的 `confirmed_event_count=0` 只能表示“在已覆盖窗口中没有确认事件”；
- 不能自动把 sampled 无事件 run 标为 `los_reference`；
- full-scan 是当前唯一可以作为无采样漏检金标准的模式；
- 生产库必须保存 `sampling_coverage_status` 和 `sampling_confidence`，将未覆盖风险与物理负结果分开。

## 7. 输出、状态和数据库兼容设计

### 7.1 不覆盖现有结果

当前 pipeline 的输出路径固定为 `scenes/<scene>/sage_results/nav_sage_v2/<PRN>`，且当前入口没有 `SamplingMode` 或 `SamplingPlan` 参数。仅靠 batch executor 不能安全地把 sampled 结果塞入现有 v2 目录。未来实现必须先设计新的版本化 namespace，例如：

```text
scenes/<scene>/sage_results/nav_sage_batch_sampled_v1/<PRN>/
```

或完全独立的 batch result root。不得覆盖 `nav_sage_v2/Gxx`、reference scene 结果或 `G06_nav_sage_v1`。本文件不授权创建该目录，也不要求现在改 pipeline。

### 7.2 建议的 sampling artifacts

每个 sampled run 至少保存：

- `sampling_plan.json`：profile version、seed、N0、N1 budget、时间/elevation/CN0 阈值、geometry join 状态和完整选窗规则；
- `sampling_window_manifest.csv`：每个 Stage0 window 一行，包含 selected/not_selected、selection reason、time/elevation/CN0 strata、guard type、scan status；
- `stage1_nav_fast_scan.csv/.mat`：只包含已扫描结果，或保留所有 window 但以显式 `scan_status` 表示未扫描；两者必须由 schema version 明确定义；
- 现有 Stage2/3/4 CSV/MAT，但增加 sampled run provenance；
- `sampling_qa.json` 或报告：coverage、inconclusive centers、预算是否耗尽和 full-scan escalation 建议。

### 7.3 数据库新增运行字段

在 `MULTIPATH_EVENT_DATABASE_DESIGN.md` 已定义的 `sage_runs`/window 层上建议增加：

| 字段 | 含义 |
|---|---|
| `sampling_mode` | `full-scan` 或 `batch-sampled-v1` |
| `sampling_profile_version` | 采样规则版本 |
| `sampling_plan_sha256` | 不可变采样清单指纹 |
| `selection_seed` | 确定性 hash seed 或 seed id |
| `stage0_window_count` | 全量 Stage0 window 数 |
| `stage1_sampled_count` | 实际 Stage1 扫描数 |
| `stage1_unscanned_count` | 未扫描数 |
| `stage2_candidate_count` | 实际进入 Stage2 的窗口数 |
| `sampling_coverage_status` | `complete`、`guard_complete`、`inconclusive` |
| `sampling_confidence` | 采样覆盖置信度，不是物理真值概率 |
| `full_scan_reference_run_id` | 若存在同一任务 full-scan 金标准，则记录其 run id |

已有 confirmed/rejected/LOS 标签规则不能被采样模式放宽。特别是 sampled 无事件不能自动升级为 `los_reference`；缺少 coverage 证据时应使用 `no_confirmed_event` 或 `inconclusive_due_to_sampling`。

## 8. 验证实验设计

### 8.1 Gold baselines

先不重跑任何已有目录，把已有 full-scan 结果作为只读金标准：

- reference scene 七 PRN：8 个 confirmed event windows、11 条 confirmed multipath paths；G25 是低复杂度参考，G28 是 Stage4 拒绝案例，G06/G11/G12/G29/G32 有 confirmed 样本；
- Wave-A：G16、G12 共 7 个 confirmed event/path 记录，G25 为无 confirmed 的控制样本；
- Wave-2A G11：15,210 个 full-scan windows、67 个 candidate、268 个 Stage2 model rows、0 个 confirmed event，且有精确的 19.6 h runtime 证据。

这些 gold 文件只读使用，任何 sampled 验证必须使用新版本化输出目录和新的 `run_id`。

### 8.2 实验分组

建议先做离线采样计划 replay，再做极少量实际 sampled run：

1. 对 reference 七 PRN、Wave-A 三任务和 Wave-2A G11 生成 `batch-sampled-v1` 的 window manifests，不运行 SAGE；检查已知 event center 及其 Stage3 所需 `±2` 闭包是否被覆盖。
2. 对确定性 profile 使用固定 `seed_00`；为估计不同 hash 保留的方差，再生成 `seed_01`–`seed_09` 共 10 个可复现实验计划。每个计划都要有独立 hash 和输出 namespace。
3. 只有离线覆盖检查通过后，选择一个 reference-derived 任务和一个长场景任务做 sampled 实际执行；保持单线程、人工批准、独立 QA。
4. 不把 sampled 结果写回现有 full-scan 目录；成功后再与 gold 对齐。

### 8.3 核心指标

每个 sampled run 对 gold 计算：

- **confirmed event recall**：gold Stage4 `joint_valid=1 && joint_multipath_count>0` 的中心，按同一 `scene_id/PRN` 的 window ID 或明确时间容差匹配；
- **confirmed path recall**：事件匹配后，按 excess delay、signed Doppler 和相对功率容差匹配路径；
- **false confirmed rate**：sampled 确认事件不在 gold 事件集合中的比例；
- **Stage3 center recall**：gold reliable center 是否有完整 Stage1/Stage2 五窗口闭包；
- **Stage2 model distribution**：L1/L2/L3/L4、L≥2、L≥3 的数量和占比差异；
- **Stage1 reduction**：`1 - stage1_sampled_count/stage0_window_count`；
- **Stage2 reduction**：candidate count、`candidate_count×4` model evaluations 的减少量；
- **wall-clock/I/O**：Stage1、Stage2、总耗时、raw read 量和 checkpoint 恢复行为；
- **coverage audit**：每个 time/elevation/CN0 strata 的实际样本数、burst 覆盖和未覆盖窗口比例。

事件匹配不能只比较总数；必须同时比较中心窗口、路径参数和 Stage3/Stage4 漏斗。没有 event 的 G25、G28 和 Wave-2A G11 用于检查 false positive，但 sampled 的无事件结论只有在 coverage 完整时才具有 negative-control 意义。

### 8.4 建议验收门槛

第一版生产放行建议采用保守门槛：

- reference + Wave-A 已知 confirmed event 的 recall 必须为 100%；
- confirmed path recall 不低于 95%，且任何漏掉的路径都必须有可解释的 coverage warning；
- G25、G28、Wave-2A G11 在 coverage 完整时不得产生 gold 中不存在的 confirmed event；
- 每个已知 event 的 Stage3 `±2` 闭包必须完整，否则该 run 自动升级 full-scan；
- Stage2 L1/L2/L3/L4 比例的单 run 绝对差异目标不超过 10 个百分点；超过时只可作为探索性 sampled 结果；
- 对 `N0 > 1,200` 的长场景，Stage1 至少减少 60%，同时 Stage2 不能因为候选截断而丢失已知 event；
- 任一已知 confirmed event 漏检、输出 partial 或 sampling manifest 缺失时，sampled 模式不得进入正式统计数据库。

100% 的小样本 event recall 是当前阶段应优先于 runtime reduction 的门槛。若后续多 scene 统计显示 1,200 预算不足，应增加预算或对该 scene-PRN 使用 full-scan，而不是降低召回门槛。

## 9. 运行前后的 QA 门禁

未来实现 sampled executor 前必须确认：

### 运行前

- inventory 的 scene/PRN/channel 唯一映射和输入完整性再次通过；
- sample rate 是 Pipeline 已支持的 10.23 MHz；
- pipeline、sampling profile、geometry join 规则和 plan hash 一致；
- output namespace 不存在且与 full-scan 结果隔离；
- `sampling_plan.json` 是 immutable，包含完整 window manifest；
- Stage0 全量预算、Stage1 1,200 上限和 Stage2 120 candidate 上限可执行；
- 发现 geometry 无法可靠对齐时，任务仍可使用 time/CN0 分层，但必须记录 warning，不得编造 elevation。

### 运行后

- Stage0 window count 与 sampling manifest 的母集一致；
- 未扫描窗口不是 Stage1 failed；
- 每个 Stage2 candidate 有四个 L 模型结果和一个 selected model；
- Stage3 center 都能追溯到完整的 Stage2 ±2 闭包；
- Stage4 path 数与 `joint_selected_L` 一致；
- sampled 无事件不自动标为 LOS；
- 运行、sampling plan、Stage 输出和 event database ingestion 使用同一 `run_id`，并记录 `sampling_mode`；
- batch 输出只写新 namespace，不写 scene metadata/inventory 和已有 `nav_sage_v2` 目录。

## 10. 下一阶段工作顺序

1. 先冻结 `batch-sampled-v1` 的 schema、selection seed、分层规则和 QA 枚举。
2. 编写只读 sampling planner，先对现有 Stage0/geometry 生成 manifests，不调用 MATLAB。
3. 用 reference 七 PRN 和 Wave-A gold 进行 offline event-window coverage replay。
4. 设计一个隔离的 sampled Pipeline 入口或版本化 output namespace；不要通过手工删改现有 Stage CSV 伪造 sampled 运行。
5. 对一个短场景和 Wave-2A G11 这类长场景做实际 sampled pilot，逐任务 QA。
6. 若满足 event/path recall 和 Stage2 分布门槛，再恢复 Wave-2A 剩余任务的 sampled/controlled execution；否则继续对特定任务 full-scan 或增加采样预算。
7. 采样策略稳定后，才把 `sampling_mode`、coverage 和 plan hash 接入 multipath event database，再进入多 scene 统计建模。

## Current Status

当前状态是：reference scene full-scan 验证已封存，Wave-A 三任务已通过 QA，Wave-2A G11 full-scan 已通过 QA 但暴露出 15,210 窗口、约 19.6 小时的规模风险。Stage1/Stage2 sampled 模式尚未实现、尚未运行、尚未完成召回率验证。

因此下一次 AI Agent 启动后的第一任务不是直接继续 Wave-2A 或启动全量 SAGE，而是根据本文生成只读 sampling manifest 并对已有 reference/Wave-A/G11 结果执行 coverage replay。Wave-2A 剩余任务在 sampling profile 通过验证前建议暂停自动放行；若人工决定继续，必须保持现有 full-scan、正常 Windows 用户、串行执行和逐任务 QA，不能把 sampled 设计当作已实现功能。
