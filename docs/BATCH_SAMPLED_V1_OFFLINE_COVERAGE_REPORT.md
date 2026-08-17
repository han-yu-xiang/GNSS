# batch-sampled-v1 离线 Sampling Planner 与 Coverage Replay 报告

## 1. 任务范围与最终判定

本次任务实现并验证了第一阶段只读 sampling planner。整个过程：

- 未运行 MATLAB；
- 未运行 SAGE、相关或拟合计算；
- 未打开 raw IQ；
- 未修改 `run_nav_sage_pipeline.m`、scene、metadata、inventory 或任何已有 `sage_results`；
- 只读取已有 Stage0 window catalog、trajectory NMEA、卫星 geometry timeseries、Stage3 reliable centers 和 Stage4 joint summary。

最终判定：**FAIL（不放行实际 `batch-sampled-v1` SAGE pilot）**。

原因不是 planner 崩溃，而是覆盖率门禁未通过：reference scene 的已知 confirmed events 全部覆盖，但 Wave-A G16/G12 的已知 confirmed event center 及其 Stage3 所需 `±2` 闭包出现漏覆盖。按照设计文档“任何已知 confirmed event 漏检不得放行”的规则，当前 sampled 策略只能继续作为离线实验方案，不能进入实际 sampled SAGE。

## 2. 新增实现与测试

新增独立 planner：

```text
E:\GNSS_Multipath_Project\scripts\sage_pipeline\generate_batch_sampling_plan.py
```

新增单元测试：

```text
E:\GNSS_Multipath_Project\scripts\sage_pipeline\test_generate_batch_sampling_plan.py
```

测试结果：

```text
Ran 4 tests in 0.029s
OK
```

已通过的测试覆盖：

- deterministic seed 可重复；
- `N0 <= 1200` 时全量 window 保留并标记 `full-scan-equivalent`；
- 长场景 Stage1 选择数不超过 1,200，24 个时间层各满足至少 20 个样本，所有 Stage0 window ID 保留；
- Stage3 `±2` closure 覆盖判定正确。

静态语法检查通过：

```text
python -B -m py_compile scripts\sage_pipeline\generate_batch_sampling_plan.py
```

单元测试命令：

```text
python -B -m unittest discover -s scripts\sage_pipeline -p test_generate_batch_sampling_plan.py -v
```

## 3. 输出与写入隔离

所有生成物写入新目录：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_offline_coverage
```

本次生成：

- 11 个 gold scene-PRN 任务；
- `seed_00` 至 `seed_09` 共 10 个确定性 seed；
- `sampling_plan.json`：110 个；
- `sampling_window_manifest.csv`：110 个；
- 根级 coverage/replay 和 validation manifest 文件：4 个；
- 文件总数：224；
- 零字节文件：0；
- 路径中包含 `sage_results` 的生成物：0；
- 输出目录之外的生成物：0。

根级清单为：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_offline_coverage\sampling_validation_manifest.json
```

根清单明确记录 `matlab_invoked=false`、`sage_invoked=false`、`raw_iq_opened=false`，且 gold labels 未参与 window selection。

主要汇总文件：

```text
coverage_replay.csv
coverage_replay_events.csv
coverage_replay_stage3_centers.csv
```

每个 manifest 都保留完整 Stage0 `window_id` 母集，并记录 `selected/not_selected`、`selection_reason`、`stratum`、`seed`、`sampling_mode`、C/N0、geometry join 状态和时间信息。

## 4. Planner 实际执行规则

实现遵循 `docs/STAGE1_STAGE2_BATCH_SAMPLING_DESIGN.md`：

- Stage0 母集完整保留；
- `N0 <= 1200`：所有窗口被选中，`sampling_mode=full-scan-equivalent`；
- `N0 > 1200`：Stage1 最多 1,200 个窗口，初始目标 800，剩余预算最多 400；
- 24 个时间层，每层至少 20 个窗口；
- 每个时间层生成确定性的 11-window burst；
- 全量 Stage0 C/N0 使用 P20/P80 划分低、中、高层；
- geometry 可信时才使用 Low/Mid/High elevation 分层；
- 其余预算使用 seed 派生的确定性 hash 补样和低成本风险 burst；
- 所有选择均只使用 Stage0 字段和 geometry/NMEA，不执行 raw IQ 相关计算；
- `seed_00` 至 `seed_09` 的 manifest 独立生成、互不覆盖。

## 5. 11 个任务的规模与 geometry 结果

| 任务 | Stage0 N0 | Stage1 选择数 | Stage1 reduction | geometry coverage | p95 nearest Δt | mode |
|---|---:|---:|---:|---:|---:|---|
| reference G06/ch4 | 319 | 319 | 0.00% | 0.000 | 40.863 s | full-scan-equivalent |
| reference G11/ch5 | 1,175 | 1,175 | 0.00% | 0.000 | 40.125 s | full-scan-equivalent |
| reference G12/ch6 | 1,175 | 1,175 | 0.00% | 0.000 | 40.118 s | full-scan-equivalent |
| reference G25/ch0 | 1,175 | 1,175 | 0.00% | 0.000 | 40.115 s | full-scan-equivalent |
| reference G28/ch1 | 898 | 898 | 0.00% | 0.000 | 39.862 s | full-scan-equivalent |
| reference G29/ch7 | 1,175 | 1,175 | 0.00% | 0.000 | 40.122 s | full-scan-equivalent |
| reference G32/ch11 | 1,175 | 1,175 | 0.00% | 0.000 | 40.123 s | full-scan-equivalent |
| Wave-A G16/ch1 | 2,229 | 1,200 | 46.164% | 0.117 | 42.115 s | batch-sampled-v1 |
| Wave-A G25/ch0 | 2,339 | 1,200 | 48.696% | 0.000 | 62.437 s | batch-sampled-v1 |
| Wave-A G12/ch6 | 1,629 | 1,200 | 26.335% | 0.208 | 29.163 s | batch-sampled-v1 |
| Wave-2A G11/ch0 | 15,210 | 1,200 | 92.110% | 0.855 | 20.219 s | batch-sampled-v1 |

### Geometry 结论

所有 11 个任务最终均为 `geometry_join_status=warning_fallback`，没有任务使用 Low/Mid/High elevation 分层。原因是 window-level geometry 关联未达到 planner 的可信门槛：coverage 至少 90%，nearest-time p95 不超过 5 秒，并且需要 trajectory/geometry 的 NMEA 身份一致。

planner 没有使用 PRN-level geometry summary 均值伪造 window elevation，而是记录 warning 并退化为 time+C/N0 采样，符合设计要求。现有 geometry 时间序列只覆盖 Stage0 时间轴的一部分，不能直接视为完整窗口级上下文；后续如需使用 elevation，必须先解决 raw recording time 与 NMEA UTC 的可靠锚定及覆盖范围问题。

## 6. Gold confirmed event coverage

Coverage replay 从已有 Stage4 summary 使用既定规则读取 gold event：`joint_valid == 1 && joint_multipath_count > 0`。planner selection 没有读取这些标签；它们只用于 replay。

### 6.1 Reference scene

reference scene 的 8 个 confirmed event centers 为：

- G06：203、264；
- G11：640；
- G12：970、971；
- G29：80；
- G32：82、84；
- G25/G28：没有 confirmed event。

7 个 reference task 均为 `N0 <= 1200` 的 full-scan-equivalent：

- event center coverage：`80/80`（8 events × 10 seeds）；
- event `±2` closure coverage：`80/80`；
- reference confirmed event recall：100%；
- reference event closure recall：100%。

Gold Stage3 reliable centers 的 `±2` closure 也全部覆盖：

- G06：`20/20`；
- G11：`70/70`；
- G12：`40/40`；
- G28：`20/20`；
- G29：`10/10`；
- G32：`110/110`；
- G25 没有 reliable center。

reference Stage3 closure 总体为 `270/270`。

### 6.2 Wave-A G16

Wave-A G16 的 gold confirmed event centers 为 `1337、1338、1406、2079`。10 个 seed 的 replay 结果：

- center coverage：`19/40 = 47.5%`；
- `±2` closure coverage：`10/40 = 25.0%`；
- event-center recall 按 seed 约为 25%–75%；
- closure recall 每个 seed 均为 0%；
- Stage3 reliable center 有 11 个，closure coverage 为 `14/110 = 12.7%`。

具体漏覆盖包括：

- window 1337：center 5/10 覆盖，closure 0/10；
- window 1338：center 3/10 覆盖，closure 0/10；
- window 1406：center 1/10 覆盖，closure 0/10；
- window 2079：center 和 closure 均 10/10 覆盖。

### 6.3 Wave-A G12

Wave-A G12 的 gold confirmed event centers 为 `835、836、1278`。10 个 seed 的 replay 结果：

- center coverage：`16/30 = 53.3%`；
- `±2` closure coverage：`11/30 = 36.7%`；
- event-center recall 按 seed 在约 33.3%–100% 间变化；
- closure recall 按 seed 在约 33.3%–66.7% 间变化；
- Stage3 reliable center 有 11 个，closure coverage 为 `52/110 = 47.3%`。

具体结果为：

- window 835：center 5/10，closure 0/10；
- window 836：center 1/10，closure 1/10；
- window 1278：center 和 closure 均 10/10。

### 6.4 Wave-A G25 与 Wave-2A G11

Wave-A G25 和 Wave-2A G11 的 full-scan gold 中没有 confirmed event，因而 event recall 对它们为 N/A，而不是 100% 的正样本召回率。两者也没有可用于 closure replay 的 Stage3 reliable center。

它们可以作为后续 sampled 实际运行的 negative/control 对照，但当前 planner 只做窗口覆盖，尚未实际运行 sampled SAGE，因此还不能计算 false-confirmed rate。

## 7. Seed 稳定性与失败原因

每个任务均生成 10 个 seed manifest；采样窗口集合随 seed 变化，且每个 task 的 10 个 manifest 均独立保存。reference full-scan-equivalent 的实际选择集合不应随 seed 改变；Wave-A 和 Wave-2A sampled task 的 selection 会随 seed 变化。

当前失败不是某一个 seed 的偶然问题：

- reference 的 10 个 seed 全部通过；
- G16 的所有 seed 都有至少一个 confirmed event closure 漏覆盖；
- G12 的所有 seed 都有 confirmed event center 或 closure 漏覆盖；
- Stage3 reliable center closure 也在 G16/G12 大量缺失。

这说明当前 1,200 窗口静态分层、11-window burst 和低成本风险扩展仍不能替代“看到 Stage1 candidate 后再补齐 `±2` guard”的自适应闭包。planner 阶段无法知道 Stage1 residual candidate，因此不能提前保证所有需要的 guard band；这正是实际 sampled pipeline 必须实现显式 adaptive guard pass 的原因。

## 8. 当前没有执行的指标

本次严格不运行相关/拟合计算，因此以下指标没有被伪造：

- sampled Stage1 residual candidate count；
- sampled Stage2 L1/L2/L3/L4 model distribution；
- sampled Stage3 persistence pass；
- sampled Stage4 joint result/confirmed event count；
- sampled runtime、raw I/O 和 MATLAB memory；
- sampled false-confirmed rate。

当前报告的 `Stage1 reduction` 是计划层面的窗口削减比例，不是实际运行耗时加速比。只有将来在新 namespace 中实现并运行 sampled pipeline 后，才能测量真实 Stage1/Stage2 wall-clock。

## 9. Pilot 放行门禁

设计文档建议的 sampled pilot 门槛包括：

1. reference + Wave-A 已知 confirmed event recall 100%；
2. confirmed path recall 至少 95%；
3. 每个已知 event 的 Stage3 `±2` closure 完整；
4. 不产生 gold 中不存在的 confirmed event；
5. Stage2 模型分布和输出 QA 通过；
6. 采样 plan hash、coverage 状态和输出隔离完整。

本次结果已经在第 1 和第 3 项失败：Wave-A G16/G12 的 known event center/closure 漏覆盖。因此：

**`batch-sampled-v1` 当前未达到实际 sampled SAGE pilot 门槛，禁止生成或执行 sampled SAGE request。**

## 10. 下一步建议

1. 不修改已有 full-scan 结果；保留本次 110 个 plan/manifest 作为失败但可复现的 coverage baseline。
2. 先解决 geometry window-level UTC 对齐，使 elevation 分层具有可验证输入；在此之前继续使用 time+C/N0 fallback。
3. 设计 Stage1 adaptive pass：初始 Stage1 sample 发现 candidate 后，优先扫描其 `±2` guard，必要时扩展 `±5`，并在预算不足时自动标记 `sampling_inconclusive`。
4. 增加基于 gold coverage replay 的 planner 回归测试，要求 G16/G12 已知 event closure 全部覆盖后才进入新 pilot。
5. 实际 sampled 运行必须使用新版本化 output namespace，不能写入现有 `nav_sage_v2` 或任何 reference 结果目录。
6. 在 sampled pilot 通过前，Wave-2A 剩余任务不要切换到 sampled 模式；若必须取得完整科学基线，只能按现有 full-scan、正常 Windows 用户、串行和逐任务 QA 继续。

## Current Status

第一阶段只读 sampling planner 已实现，11 个 gold task、10 个确定性 seed、110 个 plan/manifest 已生成并完成 coverage replay。reference scene 8/8 confirmed event centers 及闭包全部覆盖，但 Wave-A G16/G12 覆盖失败；geometry 11 个任务均因 window-level 时间覆盖不足退化为 time+C/N0。

当前状态：**规划和离线验证完成，`batch-sampled-v1` 未放行，尚未执行任何 sampled SAGE。** 下一项任务应是分析漏覆盖窗口、完善 adaptive guard/geometry 对齐策略并重新进行离线 replay，而不是调用 MATLAB。
