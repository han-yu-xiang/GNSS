# batch-sampled-v1.1 离线 Coverage Replay 报告

## 1. 最终判定

**FAIL：`batch-sampled-v1.1` 不得进入实际 sampled SAGE pilot。**

判定依据是用户定义的硬门禁：reference scene 与 Wave-A 的所有已知 confirmed multipath event center 及其 `±2` Stage2/Stage3 closure 必须达到 100%，且 Stage1 总预算不得超过 1,200。reference 的已知事件仍然全部覆盖，但 Wave-A G16/G12 在所有 block family 的 1,200-window replay 中仍有 center 或 closure 漏覆盖。因此，不能因为 reference 达到 100%，或因为自适应 `±2` 能修复部分窗口，就放行实际 sampled SAGE。

本次没有调用 MATLAB、SAGE、`run_nav_sage_pipeline.m`，没有打开 raw IQ，也没有写入任何 scene、metadata、inventory 或已有 `sage_results`。

## 2. 任务范围与只读输入

本次 v1.1 只读读取以下内容：

- `docs/STAGE1_STAGE2_BATCH_SAMPLING_DESIGN.md`；
- `docs/BATCH_SAMPLED_V1_OFFLINE_COVERAGE_REPORT.md`；
- 现有独立 planner `scripts/sage_pipeline/generate_batch_sampling_plan.py`；
- gold task 已有的 `stage0_valid_40ms_windows.csv`；
- gold task 已有的全量 `stage1_nav_fast_scan.csv`，仅作为离线 Stage1 surrogate；
- 已有 `stage3_reliable_centers.csv` 和 `stage4_joint_summary.csv`，仅用于 coverage replay；
- trajectory NMEA、satellite elevation timeseries CSV，以及任务的既有 run context/source hash。

gold Stage3/Stage4 标签只用于事后评估，未用于选择初始窗口、seed 或 adaptive block。Stage1 surrogate 的隐藏行不会参与初始 seed 排序。

已知 confirmed event center 共 15 个：

| 来源 | confirmed event centers |
|---|---|
| reference G06 | 203、264 |
| reference G11 | 640 |
| reference G12 | 970、971 |
| reference G29 | 80 |
| reference G32 | 82、84 |
| Wave-A G16 | 1337、1338、1406、2079 |
| Wave-A G12 | 835、836、1278 |

reference G25、G28，Wave-A G25 和 Wave-2A G11 的已有 full-scan 结果没有 confirmed event；这些任务在本报告中仍被执行 replay，但没有正样本 event recall 分母。

每个 event 的 closure 检查窗口为 center 的连续五窗：

| task/PRN | center | `±2` closure window IDs |
|---|---:|---|
| reference G06 | 203 | 201–205 |
| reference G06 | 264 | 262–266 |
| reference G11 | 640 | 638–642 |
| reference G12 | 970 | 968–972 |
| reference G12 | 971 | 969–973 |
| reference G29 | 80 | 78–82 |
| reference G32 | 82 | 80–84 |
| reference G32 | 84 | 82–86 |
| Wave-A G16 | 1337 | 1335–1339 |
| Wave-A G16 | 1338 | 1336–1340 |
| Wave-A G16 | 1406 | 1404–1408 |
| Wave-A G16 | 2079 | 2077–2081 |
| Wave-A G12 | 835 | 833–837 |
| Wave-A G12 | 836 | 834–838 |
| Wave-A G12 | 1278 | 1276–1280 |

## 3. v1 漏检来源：不是单纯缺少 `±2` guard

第一版 v1 的问题是初始选择以离散窗口、分层补样和少量 burst 为主。已有结果显示：

- Wave-A G16：event-center recall `19/40 = 47.5%`，`±2` closure recall `10/40 = 25.0%`；
- Wave-A G12：event-center recall `16/30 = 53.3%`，`±2` closure recall `11/30 = 36.7%`。

如果一个 confirmed event center 没有进入初始 Stage1 暴露集，就不会产生 Pipeline V3 的 Stage1 candidate seed。之后只扫描已有 seed 的 `±2` 邻域，无法“创造”一个不存在的 seed。因此，单纯增加 guard 宽度不能解决所有漏检；它只能修复已经被初始阶段看到的 center 周围的 closure。

v1.1 的 replay 明确把这个过程拆成两阶段：

1. 只把初始连续 block 内的 Stage1 surrogate 行暴露给 Pipeline V3 candidate rule；
2. 仅从这些可见行产生最多 24 个 base seed；
3. 先加入每个 seed 的 `±2`；
4. 预算仍足够时，再加入固定 11-window 的 seed `±5` block；
5. 不查看隐藏 Stage1 行来重新挑选 seed。

因此，v1.1 的 adaptive replay 没有把隐藏 gold event 直接补进来，能够区分“center 从未暴露”与“center 暴露但 closure 不完整”。

## 4. v1.1 实现的 sampling 策略

新增独立脚本：

```text
E:\GNSS_Multipath_Project\scripts\sage_pipeline\generate_batch_sampling_plan_v1_1.py
```

它不修改 full-scan pipeline，Stage0 母集始终完整保留。每个 manifest 都包含每一个原始 `window_id`，并标记 `selected/not_selected`、初始或 adaptive phase、selection reason、time stratum、seed、geometry join 状态和 source hash。

### 4.1 初始阶段

- `N0 <= 1200`：标记 `full-scan-equivalent`，全部 Stage0 window 暴露给 Stage1；
- `N0 > 1200`：使用 24 个时间层，优先选择连续短 block；
- 评估初始 block 长度 11、21、31、41；
- 初始目标通常为 800；为了在 24 个时间层至少保留一个完整 block，实际初始预算为 `max(800, 24 × block_length)`，仍不超过总预算；因此 41-window profile 的初始目标为 984；
- block center 由时间层内确定性位置、`seed` 和 profile 派生的稳定 hash 决定，不读取 gold event；
- Stage0 的 C/N0 P20/P80、24 时间层和连续 block 信息被记录，但 v1.1 的主要选择驱动是时间连续性，不把 C/N0 或 geometry summary 当作事件标签。

### 4.2 Stage1 surrogate 与 adaptive 阶段

初始窗口的 Stage1 surrogate 采用当前 Pipeline V3 的候选排序规则：

- `scan_valid == 1` 且 `residual_peak1_power_db` 有效；
- 先按 `has_two_strong_residuals` 的第二残差功率排序；
- 再按第一残差功率排序；
- 最多 24 个 base candidate，少于最低数量时保留现有规则的 fallback；
- 这段排序只接收初始暴露窗口，隐藏行不会参加排序。

adaptive 阶段顺序固定为：

```text
initial continuous blocks
        -> visible Stage1 candidate seeds
        -> seed ±2
        -> seed ±5 (固定 11-window block，仅当预算允许)
```

Stage2 只应处理 Stage1 candidate/closure 的结果；本次没有执行实际 Stage2，只有在离线回放中模拟其窗口暴露闭包。

## 5. 任务规模与 final replay 输出

最终几何对齐版 replay 的权威输出位于：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_1_offline_coverage\tow_aligned
```

同一 `batch_sampled_v1_1_offline_coverage` parent 下还保留了几何校准完成前的第一次 provisional replay；本报告的统计、门禁和后续 AI Agent 应以 `tow_aligned` 子目录为准，provisional 文件不作为最终结论来源。

该目录包含：

- 11 个 scene-PRN gold task；
- `seed_00` 至 `seed_09` 共 10 个 seed；
- 4 个 1,200-window profile：11、21、31、41-window initial block；
- 440 个 `sampling_plan.json`；
- 440 个 `sampling_window_manifest.csv`；
- `coverage_replay_v1_1.csv`；
- `coverage_replay_events_v1_1.csv`；
- `coverage_replay_stage3_centers_v1_1.csv`；
- `budget_sweep_v1_1.csv`；
- `sampling_validation_manifest_v1_1.json`。

总文件数为 885，零字节文件为 0，所有文件均位于上述新 validation 目录内。根 manifest 明确记录：

```text
full_scan_stage1_surrogate_used=true
hidden_stage1_rows_used_for_seed_selection=false
gold_labels_used_for_selection=false
matlab_invoked=false
sage_invoked=false
raw_iq_opened=false
event_recall_gate_passed_for_1200_profiles=false
```

11 个任务的 Stage0 母集规模如下；所有任务采样率为 10.23 MHz：

| task | channel | Stage0 N0 | 1,200 profile 中 Stage1 选择量 | gold confirmed event |
|---|---:|---:|---:|---:|
| reference G06 | 4 | 319 | 319 | 2 |
| reference G11 | 5 | 1,175 | 1,175 | 1 |
| reference G12 | 6 | 1,175 | 1,175 | 2 |
| reference G25 | 0 | 1,175 | 1,175 | 0 |
| reference G28 | 1 | 898 | 898 | 0 |
| reference G29 | 7 | 1,175 | 1,175 | 1 |
| reference G32 | 11 | 1,175 | 1,175 | 2 |
| Wave-A G16 | 1 | 2,229 | 约 775–1,012 | 4 |
| Wave-A G25 | 0 | 2,339 | 约 769–1,010 | 0 |
| Wave-A G12 | 6 | 1,629 | 约 760–1,011 | 3 |
| Wave-2A G11 | 0 | 15,210 | 约 697–919 | 0 |

对于 `N0 <= 1200` 的任务，实际选择数是全量 N0，不会为了满足一个较低的 diagnostic budget 而错误删减 full-scan-equivalent 任务。

## 6. 1,200-window coverage 结果

下表对 15 个已知 confirmed event center、4 个 block family、10 个 seed 做加权汇总。`initial` 是初始连续 block 暴露之后的结果；`adaptive` 是加入 seed `±2`、预算允许时加入固定 `±5` 后的结果。

| 初始 block | initial center | adaptive center | initial `±2` closure | adaptive `±2` closure |
|---:|---:|---:|---:|---:|
| 11 | 73.33% | 81.33% | 66.67% | 76.67% |
| 21 | 76.67% | 81.33% | 72.00% | 75.33% |
| 31 | 82.67% | 83.33% | 79.33% | 80.00% |
| 41 | 80.00% | 81.33% | 79.33% | 80.67% |

这说明连续 block 确实比第一版离散选择更容易把候选区域带入初始 Stage1，adaptive 也能提高部分 center/closure 覆盖；但最好的 1,200-window aggregate 仍只有 83.33% center recall 和 80.67% closure recall，距离 100% 门禁有明显差距。

### 6.1 reference scene

reference 的 8 个 confirmed event center 在四种 block profile、十个 seed 中全部覆盖：

- event center：`320/320 = 100%`；
- `±2` closure：`320/320 = 100%`；
- reference Stage3 reliable center closure：`100%`。

这是因为 reference 的任务均为 full-scan-equivalent，不能证明长场景 sampled 策略已经可靠。

### 6.2 Wave-A G16

G16 confirmed centers 为 `1337、1338、1406、2079`。按 profile 汇总如下：

| block | initial center | adaptive center | initial closure | adaptive closure | adaptive Stage3 closure |
|---:|---:|---:|---:|---:|---:|
| 11 | 12.50% | 37.50% | 0.00% | 20.00% | 27.27% |
| 21 | 45.00% | 62.50% | 35.00% | 45.00% | 51.82% |
| 31 | 57.50% | 60.00% | 50.00% | 52.50% | 40.00% |
| 41 | 60.00% | 62.50% | 60.00% | 60.00% | 58.18% |

没有任何 G16 profile 达到所有已知 center 和 closure 的 100%。

### 6.3 Wave-A G12

G12 confirmed centers 为 `835、836、1278`。按 profile 汇总如下：

| block | initial center | adaptive center | initial closure | adaptive closure | adaptive Stage3 closure |
|---:|---:|---:|---:|---:|---:|
| 11 | 83.33% | 90.00% | 66.67% | 90.00% | 60.00% |
| 21 | 56.67% | 56.67% | 46.67% | 50.00% | 28.18% |
| 31 | 70.00% | 70.00% | 63.33% | 63.33% | 34.55% |
| 41 | 53.33% | 56.67% | 50.00% | 56.67% | 38.18% |

即使 G12 的最好 profile 达到 90% adaptive center/closure recall，仍没有达到 100%。

### 6.4 具体漏检例子

这些例子来自 `coverage_replay_events_v1_1.csv`，不是根据 gold label 反向改写 sampling：

- G16、11-window、`seed_00`：1337 和 1338 的 center 在 adaptive 阶段出现，但 closure 仍缺 1339/1340；1406 和 2079 的 center 没有被选中；
- G12、11-window、`seed_00`：1278 在 adaptive 阶段仍为 `center_not_selected`；
- G12 的其他 seed 中，835/836 有时 center 被选中，但 closure 缺 834/835；
- G16 的 1406、2079 以及 G12 的 1278 反复出现 `center_not_selected`，说明扩大已有 seed 的 guard 并不能恢复没有初始 seed 的事件。

在 1,200-window event replay 中，初始阶段最主要的失败原因是 `center_not_selected`；adaptive 后仍有大量 `center_not_selected`，其余失败为 `closure_not_selected:<window_ids>`。因此本次 FAIL 不能归因于“只少加了 `±2` guard”。

## 7. Stage3 closure replay

Stage3 的 gold reliable center 同样要求中心窗口及 `±2` 邻居进入可供 Stage2 评估的集合。reference 所有 Stage3 closure 均通过；Wave-A 的 closure 结果与 confirmed event 一致地失败：

- G16：按 11/21/31/41 profile，adaptive closure 分别为 `27.27% / 51.82% / 40.00% / 58.18%`；
- G12：按 11/21/31/41 profile，adaptive closure 分别为 `60.00% / 28.18% / 34.55% / 38.18%`。

本次没有运行 Stage2/Stage3，因此这些是“窗口可供性 closure”，不是重新计算出的 reliable event 数量。它们用于回答后续实际 pipeline 是否具备完整输入闭包，不能冒充 sampled Stage3 结果。

## 8. Budget sweep 与最低可行性判断

为了判断 1,200 失败是预算不足还是 sampling 结构不适合，脚本对每个 block family、每个 seed 扫描了以下总预算：

```text
800, 1000, 1200, 1400, 1600, 1800, 2000, 2200,
2400, 2800, 3200, 4000, 4800
```

结果：

- 没有任何一个 `(block_length, total_budget)` 组合能让所有 `seed_00` 至 `seed_09`、所有 reference + Wave-A positive task 同时达到 center 和 closure 100%；
- 某个固定 seed 的局部通过组合确实出现过：41-window/1600（`seed_00`、`seed_06`）、41-window/2200（`seed_07`）、21-window/4000（`seed_09`）；这些不是跨 seed 稳定的最低可行预算，不能作为 pilot 配置；
- 预算继续增加时，当前结构仍只围绕最多 24 个 visible Stage1 seed 加 `±2`/固定 `±5`。一旦真实 event center 没有产生 seed，剩余预算不会自动探索全新的隐藏区间；因此单纯增加 budget 不能保证召回；
- 4800 diagnostic sweep 仍没有 all-seed pass，证明当前“初始时间 block + 最多 24 seed 的局部扩展”结构不适合作为生产 sampled strategy。

结论不是“已找到一个可放行的 1,600-window 方案”，而是：当前 sampling family 没有跨 seed 的稳健最低预算。若要继续 sampled 方向，必须改变探索/反馈结构，例如增加可验证的全时段低成本 Stage1 screening、让 adaptive pass 能够发现新的 seed，或使用覆盖保证而不是只围绕已有候选做局部扩展；不能只把 `±2` 改成更大的固定 guard。

## 9. Geometry window-level 对齐：独立问题与改进结果

geometry 结果不参与 gold event 选择，本节单独报告时间关联问题。v1 的旧方法是：

```text
trajectory first valid RMC + Stage0 recording_time_s
```

这个假设要求 trajectory 文件从 raw capture time zero 开始。实际任务的 Stage0 `recording_time_s` 起点与 trajectory NMEA 起点不一致，因此会产生约 40 秒级的系统偏差。

v1.1 新增独立的 TOW join diagnostic：

1. 使用 Stage0 每个窗口自身的 `tow_s`；
2. 使用 trajectory 的第一条有效 RMC 作为 UTC anchor；
3. 在 0–30 秒确定性候选范围内，以所有 Stage0 window 与 PRN-specific geometry timeseries 的时间重合为依据估计 GPS–UTC offset；
4. 只在 window-level coverage 至少 90%、nearest-time p95 不超过 5 秒、geometry 的 NMEA 文件身份一致时标记 `verified`；
5. 不使用 PRN summary 平均值，不使用 Stage3/Stage4 event label；不满足门槛则继续 `warning_fallback` 到 time+C/N0。

旧 recording-time join 与 v1.1 TOW join 的结果：

| task | 旧 coverage / p95 | v1.1 TOW coverage / p95 | 估计 GPS–UTC offset | 状态 |
|---|---:|---:|---:|---|
| reference G06 | 0.000 / 40.863 s | 1.000 / 1.682 s | 17 s | verified |
| reference G11 | 0.000 / 40.125 s | 1.000 / 1.160 s | 17 s | verified |
| reference G12 | 0.000 / 40.118 s | 1.000 / 1.160 s | 17 s | verified |
| reference G25 | 0.000 / 40.115 s | 1.000 / 1.160 s | 17 s | verified |
| reference G28 | 0.000 / 39.862 s | 1.000 / 1.043 s | 16 s | verified |
| reference G29 | 0.000 / 40.122 s | 1.000 / 1.160 s | 17 s | verified |
| reference G32 | 0.000 / 40.123 s | 1.000 / 1.160 s | 17 s | verified |
| Wave-A G16 | 0.117 / 42.115 s | 1.000 / 0.490 s | 17 s | verified |
| Wave-A G25 | 0.000 / 62.437 s | 0.684 / 16.612 s | 23 s | warning_fallback |
| Wave-A G12 | 0.208 / 29.163 s | 1.000 / 2.182 s | 17 s | verified |
| Wave-2A G11 | 0.855 / 20.219 s | 1.000 / 0.490 s | 16 s | verified |

这项改进证明旧 geometry failure 不是唯一的 event 漏检来源：TOW 对齐可以把多项任务恢复到 verified，但 sampling coverage 数字和漏检中心仍然没有因此达到 100%。Wave-A G25 的 geometry timeseries 覆盖/一致性仍不足，planner 必须继续 fallback，不能伪造 elevation。

## 10. 静态检查与单元测试

静态语法检查通过：

```text
python -B -m py_compile scripts\sage_pipeline\generate_batch_sampling_plan.py scripts\sage_pipeline\generate_batch_sampling_plan_v1_1.py scripts\sage_pipeline\test_generate_batch_sampling_plan.py scripts\sage_pipeline\test_generate_batch_sampling_plan_v1_1.py
```

回归测试通过：

```text
cd /d E:\GNSS_Multipath_Project\scripts\sage_pipeline
python -B -m unittest test_generate_batch_sampling_plan.py test_generate_batch_sampling_plan_v1_1.py
```

结果：

```text
Ran 8 tests in 0.258s
OK
```

v1.1 新增测试覆盖：

- hidden Stage1 高分行不能参加 visible seed selection；
- 初始选择由连续 block 构成且受 initial budget 限制；
- adaptive 使用固定 seed `±5` block，且 extended diagnostic budget 不被错误截断到 1,200；
- G16 的 TOW geometry join 能独立于旧 recording-time 偏移达到 verified，且 geometry 对齐没有读 gold event。

## 11. 保护与后续建议

本次生成物全部写入新的 validation namespace，没有覆盖：

- `run_nav_sage_pipeline.m`；
- reference scene 的任何已有 Stage0–Stage4 结果；
- Wave-A/Wave-2A 的任何已有 `nav_sage_v2` 结果；
- metadata、inventory、raw IQ 或 scene 数据。

在 sampled pilot 通过前，后续 AI Agent 不得生成或执行实际 sampled SAGE request。推荐顺序是：

1. 保留本报告及 `tow_aligned` replay 作为 v1.1 失败基线；
2. 将 TOW geometry join 独立纳入后续 planner，但继续保留 warning/fallback 门禁；
3. 重新设计能发现“初始 sample 之外新 seed”的 adaptive screening，而不是扩大固定 `±2/±5`；
4. 先用同一批 reference + Wave-A gold 做离线 replay，要求每个 seed 的 event center 和 `±2` closure 均为 100%；
5. 只有通过后，才在新的 output namespace 做单任务 sampled dry-run；
6. 在 sampled 方案通过前，生产批处理继续使用已验证的 full-scan Windows wrapper/QA 流程。

## Current Status

当前处于 **batch-sampled-v1.1 离线策略修复与验证完成、实际 sampled pilot 禁止放行** 阶段。

已经完成：

- v1.1 独立连续 block planner 实现；
- 11/21/31/41 初始 block 对比；
- 10 个 seed 的初始/自适应 coverage replay；
- full-scan Stage1 surrogate 的 Pipeline V3 candidate 规则 replay；
- seed `±2` 与预算允许的固定 `±5` adaptive replay；
- 800–4800 诊断 budget sweep；
- reference + Wave-A confirmed event center/closure 检查；
- Stage3 reliable center closure 检查；
- 独立 TOW geometry window-level 对齐校准；
- Python 静态检查和 8 项单元测试。

下一次启动后的第一任务不是调用 MATLAB，也不是生成 sampled execution request。应先基于本报告设计 v1.2 的新 seed discovery/adaptive screening，并在不修改已有 SAGE 结果的前提下重新离线验证；在所有 reference + Wave-A known event center 及其 `±2` closure 达到 100% 前，状态保持 **FAIL / no sampled pilot**。
