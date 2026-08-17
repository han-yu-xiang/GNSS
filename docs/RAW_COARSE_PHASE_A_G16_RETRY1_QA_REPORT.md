# RAW-Coarse Phase-A1 Retry1 G16 独立只读 QA 报告

## 1. QA 范围与结论

本报告只读检查 Phase-A1-Retry1 的 G16 raw-coarse 输出和已有 G16 full-scan gold 结果。此次 QA 没有运行 raw-coarse、MATLAB、SAGE、Stage2、Stage3 或 Stage4，也没有访问或执行 G25/G11。

结论分为两个层次：

- **执行完整性：PASS。** Retry1 正常退出，exit code=0，raw 读取成功，2229 个 Stage0 窗口全部处理，三个冻结 profile 均生成完整 coarse 输出，没有写入 `sage_results`。
- **事件覆盖回放：PASS，但为全量 promotion 的平凡覆盖。** 三个 profile 都覆盖了 4/4 个 confirmed event center、全部 16 个唯一 center±2 closure 窗口，以及 Stage3 reliable-center closure。
- **筛选能力：FAIL。** 三个 profile 都将 2229/2229 个窗口提升为 promotion，均只有一个覆盖整个时间轴的组件，没有产生任何可供 fine Stage1 减少计算量的筛选效果。因此本次 raw-coarse 不能作为生产筛选器，也不应据此放行后续 G25 或 G11。

“100% recall”在本报告中不能被解读为算法已经具备高质量筛选能力；它是“所有窗口都被保留”得到的无信息量上界。

## 2. 只读证据与完整性检查

### 2.1 Retry1 receipt

主 receipt：

`E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_retry_outputs_20260812\Phase-A1-Retry1_F1023_V70_D0120_P7_G16_ch1\execution_receipt.json`

关键字段：

| 字段 | 值 |
|---|---|
| request_id | `phase_a1_g16_retry1_20260812` |
| status | `completed` |
| exit_code | `0` |
| raw_read_status | `ok` |
| raw bytes | `1,847,132,692` |
| chunks | `28` |
| windows_processed | `2,229/2,229` |
| kernel | `numpy-batched-complex128-v2-aligned` |
| parameter SHA-256 | `41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2` |
| prototype/script SHA-256 | `959141371075c7f417f945dbe3f915f362a9337bb77582306f2b3ef16919ddfb` |
| Python | `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe` |
| start UTC | `2026-08-12T03:51:09.803526Z` |
| end UTC | `2026-08-12T03:52:10.026973Z` |
| receipt wall interval | 60.22 s |
| last event | `profile_written` |

Progress 文件：

`E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_retry_outputs_20260812\Phase-A1-Retry1_F1023_V70_D0120_P7_G16_ch1\progress.jsonl`

Progress 记录显示 28 个 chunk 均完成，最终处理进度为 2229/2229，最后一个事件为三个 profile 写入完成。executor 和 worker 的 stderr 文件为空属于本次无错误退出的正常表现；receipt 中没有 error 或 interruption reason。

### 2.2 三个 profile 输出

Retry1 task 目录：

`E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_retry_outputs_20260812\Phase-A1-Retry1_F1023_V70_D0120_P7_G16_ch1\phaseA_F1023_V70_D0120_P7_G16_ch1`

三个 profile 为：

- `B1_20msx2_D100`
- `B2_10msx4_D100`
- `B2_10msx4_D200`

每个 profile 均有 `coarse_window_manifest.csv`、`promotion_manifest.csv`、`promotion_components.csv`、`cost_measurement.json`、`run_manifest.json` 和 `coverage_replay.csv`。每个 profile 的 window manifest 和 promotion manifest 均对应 2229 个 Stage0 窗口。输出位于新的 Phase-A retry namespace，不在任何 `scenes/*/sage_results` 下；本次没有产生 Stage1/Stage2/Stage3/Stage4 结果文件，也没有覆盖 reference 或历史 SAGE 结果。

各 profile 的 `run_manifest.json` 和参数 receipt 均表明这是 coarse-only 执行；gold 只在冻结后用于 coverage replay，`gold_labels_used_for_selection=false`。

## 3. Gold 定义与事件集合

本次仅从已有 full-scan G16 结果读取 gold：

- Stage4 summary：`E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P7\sage_results\nav_sage_v2\G16\stage4_joint_summary.csv`
- Stage3 reliable centers：`E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P7\sage_results\nav_sage_v2\G16\stage3_reliable_centers.csv`
- Stage3 persistence：`E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P7\sage_results\nav_sage_v2\G16\stage3_persistence.csv`

按当前项目 confirmed criterion：`joint_valid=1` 且 `joint_multipath_count>0` 的 Stage4 center 为：

`1337, 1338, 1406, 2079`

因此 confirmed event center 数量为 4。对每个 center 取 `center±2` 后，因 1337 与 1338 的窗口范围重叠，唯一 closure 窗口总数为 16，而不是 4×5=20。

Stage3 reliable-center 文件中的可靠中心共有 11 个：

`947, 959, 965, 966, 1337, 1338, 1406, 2079, 957, 1393, 2004`

其去重后的 ±2 closure union 共 44 个窗口。本报告把“Stage3 reliable-center closure recall”解释为这些 Stage3 reliable centers 及其 ±2 窗口在 coarse promotion 中的覆盖率；它是离线 replay 指标，不是本次重新运行 Stage3 的结果。

## 4. G16 覆盖回放结果

Retry task 的 `post_freeze_coverage_summary.json` 以及三个 profile 的 `coverage_replay.csv` 给出相同结果：

| Profile | confirmed centers | center recall | confirmed ±2 closure | ±2 closure recall | Stage3 reliable-center closure |
|---|---:|---:|---:|---:|---:|
| B1_20msx2_D100 | 4/4 | 100% | 16/16 | 100% | 100% |
| B2_10msx4_D100 | 4/4 | 100% | 16/16 | 100% | 100% |
| B2_10msx4_D200 | 4/4 | 100% | 16/16 | 100% | 100% |

`coverage_replay.csv` 对 1337、1338、1406、2079 的每一行都记录：center promoted=1、closure expected=5、closure promoted=5、closure missing=0。由于 1337/1338 的 closure 有重叠，汇总的唯一窗口数为 16。三个 profile 均覆盖 Stage3 reliable-center closure 的 44/44 个窗口。

这说明 Retry1 没有发生事件中心或 closure 漏检，但原因是全量 promotion，而不是 coarse score 成功把事件从负样本中筛出。

## 5. 三个 profile 的 promotion 与组件统计

| Profile | Stage0 N0 | promoted windows | promotion fraction | high-seed / other reason | component count | 实际 distinct promoted windows |
|---|---:|---:|---:|---|---:|---:|
| B1_20msx2_D100 | 2229 | 2229 | 100.00% | 2178 high/low-hysteresis；51 bridge | 1 | 2229 |
| B2_10msx4_D100 | 2229 | 2229 | 100.00% | 2229 high/low-hysteresis | 1 | 2229 |
| B2_10msx4_D200 | 2229 | 2229 | 100.00% | 2229 high/low-hysteresis | 1 | 2229 |

三个 profile 的唯一组件都从 window 1 延伸到 window 2229，覆盖整个场景时间轴。没有 `not_promoted` 窗口，也没有形成可降低 fine Stage1 数量的局部 promotion 区域。

注意：B1 的 `promotion_components.csv` 原始字段中记录了 `component_window_count=55,561`，但同一行的 `promoted_window_count=2,229`，且逐窗口 `promotion_manifest.csv` 只有 2229 个 distinct window。55,561 与 N0 不一致，应视为组件合并/重叠展开后的计数异常，不能当作实际窗口数或重复的 Stage0 母集。本 QA 使用逐窗口 manifest 的 2229 和组件数量 1 作为实际 promotion 统计，并将该字段异常留作后续代码 QA；本报告没有修改它。

## 6. Score distribution

`coarse_score_db` 的统计直接来自三个 profile 的 `coarse_window_manifest.csv`，单位为 dB。当前冻结参数中的 high threshold 为 -10 dB，low threshold 为 -14 dB；本次没有改变任何阈值。

| Profile | min | P05 | P10 | P25 | median | P75 | P90 | P95 | P99 | max | mean | std |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B1_20msx2_D100 | -15.0871 | -9.1874 | -8.3199 | -6.8655 | -5.3080 | -3.7166 | -2.1389 | -1.1768 | -0.2467 | -0.0042 | -5.2998 | 2.3702 |
| B2_10msx4_D100 | -8.4098 | -5.7516 | -4.9167 | -3.6502 | -2.1789 | -0.9994 | -0.3615 | -0.1831 | -0.0388 | -0.0001 | -2.4654 | 1.7497 |
| B2_10msx4_D200 | -8.7136 | -5.7659 | -5.0721 | -3.7402 | -2.2745 | -1.0407 | -0.4120 | -0.2143 | -0.0433 | -0.0014 | -2.5224 | 1.7469 |

分布揭示了 promotion 饱和的直接原因：

- B1 中有 2178/2229 个窗口已经达到 high threshold；剩余 51 个窗口虽然低于 high threshold，但在连续低阈值/bridge 规则下与大组件连通。
- B2-D100 的最小 score 仍为 -8.41 dB，B2-D200 的最小 score 为 -8.71 dB；二者均高于 -10 dB high threshold，所以每一个窗口都是 high seed。
- B2 使用 4 个 10 ms subblock 的 `max` 聚合，短时高 residual 更容易使窗口达到 high threshold；B1 使用 2 个 20 ms subblock，同样使用 max 聚合但分布较低，仍然不足以形成筛选。
- 三个 profile 的 score 都不是常数，说明不是简单的数值输出全相同；问题是 score 与固定 promotion threshold 的相对标度/区分度不足。

当前输出中的 `coarse_score_db` 是 subblock score 的最大值，subblock score 来自 `residual_proxy`/secondary-to-main 相关度的 dB 形式；`peak_ratio_db` 在当前 manifest 中与该窗口 score 同步记录。这种 max-residual proxy 在几乎所有窗口都接近 0 dB 的情况下，不能提供足够的主峰/次峰区分度。该结论是对既有输出的诊断，不是本次重新拟合阈值，也不是对 gold 事件位置的反向调参。

## 7. 为什么出现 2229/2229 promotion

原因按 profile 分解如下：

1. **B2-D100 和 B2-D200：high seed 已经覆盖全体窗口。** 其全部 2229 个 score 都不低于 -10 dB，因此 hysteresis 之前就形成全场 high seed；bridge、boundary expansion 不是主要原因。
2. **B1：high seed 加连续 bridge 覆盖全场。** 2178 个窗口直接满足 high/low-hysteresis promotion，另外 51 个窗口处于可连接的局部低分段，被 `bridge_gap=2` 的连续组件规则吸收；最终生成一个从 1 到 2229 的组件。
3. **连续性规则把局部差异转化为全场组件。** 当高风险点密集分布、低分间隔没有超过允许 bridge gap 时，固定 boundary expansion 和 bridge 规则会保留整段连续区域。这是规则按设计运行的结果，但在当前 score 标度下组件已经退化为整个场景。
4. **这不是 gold leakage。** 三个 profile 的 selection provenance 均为 `gold_labels_used_for_selection=false`；gold 只在参数、promotion manifest 和组件冻结后用于 replay。因此全量 promotion 的问题不能通过“读取 gold 位置”解释，也不能通过修改 gold 对应窗口来修复。

## 8. 成本、I/O 与输出隔离

三个 profile 复用同一次 raw contiguous pass，因此 `cost_measurement.json` 中的 raw 读取成本不应按三个 profile 简单相加。共同的 raw pass 指标为：

| 指标 | 值 |
|---|---:|
| actual raw bytes | 1,847,132,692 |
| theoretical per-window reopen bytes | 3,648,427,200 |
| unique Stage0 window union bytes | 1,825,035,500 |
| reused samples | 455,847,925 |
| chunk count | 28 |
| actual open / seek | 28 / 28 |
| theoretical per-window open / seek | 2229 / 2229 |
| read reduction vs per-window reopen | 49.37% |
| raw-pass wall time | 59.10 s |
| executor receipt wall interval | 60.22 s |
| CPU time | 54.53 s |
| peak traced memory | 142,415,656 bytes |
| average coarse time per window | 0.0265 s |

以历史 G16 full Stage1 约 3900 s 作为方向性背景，Retry1 raw-coarse raw pass 约为其 1.52%；但这只是 coarse 计算/读取时间，不等同于完整 SAGE pipeline runtime。成本门槛方面，raw-coarse 很快；筛选门槛方面，它没有减少任何 fine window。

## 9. 是否具备当前生产筛选能力

### 9.1 已证明的能力

- 能够正确读取 G16 raw 和全量 Stage0 window。
- 能够在一次 contiguous chunk pass 中完成三个冻结 profile 的 coarse 输出。
- 能够稳定产生可回放的 window-level manifest、component、cost 和 coverage 文件。
- 在当前已知 gold 上没有漏掉 center、±2 closure 或 Stage3 reliable-center closure。

### 9.2 尚未具备的能力

当前 raw-coarse **不具备可用的生产筛选能力**，因为：

- 三个 profile 的 promotion fraction 均为 100%。
- 每个 profile 只有一个覆盖全场景的 component。
- `not_promoted` 数量为 0，无法减少后续 fine Stage1 的候选窗口。
- 100% recall 完全由全量保留造成，不能证明 coarse score 对 multipath 与非 multipath 窗口具有区分能力。

所以当前 Phase-A1-Retry1 的整体筛选 QA 为 **FAIL**。更精确地说，执行和覆盖 replay 为 PASS，production filtering gate 为 FAIL。

## 10. 研究解释与限制

本报告不把未被筛选的窗口标记为 LOS，也不把被 promotion 的窗口标记为 confirmed multipath。coarse promotion 只能表示“需要进一步 fine 检查的 evidence”，confirmed multipath 仍须由既有 Stage4 criterion 判定。Retry1 namespace 中没有新的 Stage4 结果。

本报告也不建议在本次 QA 中调 threshold、Doppler grid、score 定义或 bridge 规则。2229/2229 已足以说明当前冻结组合的筛选区分度不足，下一步应作为独立算法设计/验证任务处理，而不是用 G16 gold 位置反复调参。

## 11. 最终判定

| QA 项目 | 判定 |
|---|---|
| Receipt / exit / raw I/O 完整性 | PASS |
| 三 profile 完成 | PASS |
| G16 confirmed event center recall | PASS，4/4 |
| G16 confirmed ±2 closure recall | PASS，16/16 unique |
| Stage3 reliable-center closure replay | PASS，44/44 |
| Promotion 的非全量区分能力 | FAIL，三个 profile 均 2229/2229 |
| 当前 raw-coarse 可作为 production promoter | **FAIL** |
| 是否允许本 QA 后执行 G25/G11 | **不允许** |

本报告未执行、未授权、也未生成 G25 或 G11 命令。当前 raw-coarse 应继续停留在 prototype 诊断阶段；任何后续参数或 score 设计必须先形成新的冻结版本并重新进行不泄漏 gold 的离线验证。
