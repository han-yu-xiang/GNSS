# 0913DarkroomRx 八任务 GNSS-SDR 定位与信号质量综合报告

## 1. 报告目的与结论

本报告汇总 `0913DarkroomRx` 八个 10.23 MHz GNSS-SDR 任务的实际执行 receipt、已生成输出和独立 v2 只读审计结果，重点回答：POOR 条件下 GNSS-SDR 是否能够形成定位输出，以及 tracking 失锁现象与定位输出之间的关系。

结论如下：

- 八个任务均有 `status=completed`、`exit_code=0` 的执行 receipt；执行 receipt 中记录的 raw hash verification 均为 `true`，并且执行策略为 `new_only=true`、`resume_allowed=false`。
- 八个任务中，六个任务达到本审计的工程分类 `SUSTAINED_FIX`：Highway/Open 的 GOOD、POOR、RAIN，Mountain/Valley 的 RAIN，以及 Urban 的 GOOD、POOR。
- 两个任务为 `INCONCLUSIVE_NO_POSITION_OUTPUT`：Mountain/Valley 的 GOOD 和 POOR。它们有 tracking、telemetry、observables 等输出，但没有可用的 NMEA/PVT 定位输出。因此不能据此断言 Mountain/Valley POOR 信号物理上不能定位。
- POOR 条件目前已有两个可以直接回答“能定位”的结果：Highway/Open POOR 为 `103/105` 个有效/期望定位历元，Urban POOR 为 `12/12`；二者均达到至少 5 s 连续有效定位的工程门槛。
- tracking lock-loss 与 PVT/NMEA 定位输出是两个独立观测层。本批次共记录 207 个经去抖确认的 tracking 失锁事件，但不能把该数字直接换算成车辆定位丢失比例。

本报告是 GNSS-SDR 输出层诊断，不是车机地图行为判定，也不把 `POOR` 文件名解释成物理信道结论。

## 2. 审计范围与 provenance

### 2.1 输入与执行批次

|项目|实际值|
|---|---|
|Immutable batch manifest|`E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr\darkroom_rx_0913_gnss_sdr_v1_20260914\batch_manifest.json`|
|Manifest SHA-256|`4c589f7f6df5be6284b9f4c8975c595af963c065b45151707aa3c617d12ba704`|
|输入格式|10.23 MHz、interleaved signed int16 little-endian I/Q；GNSS-SDR `ishort`|
|GNSS-SDR|WSL Ubuntu-22.04，`/usr/bin/gnss-sdr`，version `0.0.16`|
|执行方式|用户在正常 Windows PowerShell 中顺序执行 7 个剩余任务；原 GOOD smoke 已先完成|
|审计工具|`scripts/analysis/darkroom_rx/audit_darkroom_rx_signal_quality_v2.py`|
|审计工具 SHA-256|`02e72cfea6388090cbb60e8f5c0e2203e53fac2d70b8db3789eb2684cf3ce0ba`|
|本次全量审计 namespace|`dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_all8_20260915_r1`|
|全量审计 manifest SHA-256|`6a1c678a49221b1b2a4dbaeba17765d01316fcc7029a513d6122128c369d08f3`|

审计只读取已生成的 receipt、tracking/telemetry/observables/PVT/NMEA/日志和 manifest 元数据；本次审计未读取 raw IQ，未调用 GNSS-SDR、MATLAB 或 SAGE。

### 2.2 执行完整性

- `AUDITED_TASKS=8`。
- 八个任务执行状态均为 `completed`，执行退出码均为 `0`。
- 八个输出 namespace 均为独立目录；receipt 记录执行前 output 不存在，未采用 resume。
- 八个任务共生成 504 个输出文件，合计 442,941,294 bytes。
- 本报告不修改任何原始 raw、执行 receipt、GNSS-SDR 输出或此前 QA namespace。

## 3. 八个任务的定位结果

表中的“定位分类”是审计工具的工程语义：至少有 5 s 连续有效 PVT/NMEA 解才记为 `SUSTAINED_FIX`。`POSITION_OUTPUT_GAP` 是缺少可见输出的时间段，不等价于显式 NO_FIX 或物理失锁。

|任务|环境/条件|记录时长 (s)|GNSS-SDR runtime (s)|tracking PRN数|位置源|有效/期望历元|覆盖率|最长连续定位 (s)|首次定位时间边界 (s)|失锁事件|最大失锁 (s)|输出文件|QA|
|---|---|---:|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---|
|`highway_open_good_1023`|Highway/Open / GOOD|138.093|140.531|21|NMEA|110/111|0.991|74|27–28|24|5.106|65|PASS|
|`highway_open_poor_1023`|Highway/Open / POOR|133.793|152.500|22|NMEA|103/105|0.981|46|29–30|21|5.370|65|PASS|
|`highway_rain_1023`|Highway/Open / RAIN|134.993|154.968|22|NMEA|106/107|0.991|65|28–29|20|5.639|65|PASS|
|`mountain_valley_good_1023`|Mountain/Valley / GOOD|124.472|142.078|21|无|0/0|—|0|—|28|5.252|57|INCOMPLETE|
|`mountain_valley_poor_1023`|Mountain/Valley / POOR|132.459|156.250|21|无|0/0|—|0|—|40|5.527|57|INCOMPLETE|
|`mountain_valley_rain_1023`|Mountain/Valley / RAIN|137.706|150.844|20|NMEA|67/85|0.788|49|53–54|19|5.003|65|PASS|
|`urban_good_1023`|Urban / GOOD|133.864|155.703|21|NMEA|12/12|1.000|12|59–未见上界|29|1.581|65|PASS|
|`urban_poor_1023`|Urban / POOR|133.715|153.110|20|NMEA|12/12|1.000|12|59–未见上界|26|4.728|65|PASS|

### 3.1 POOR 结果的直接回答

#### Highway/Open POOR

该任务可以定位。审计在 NMEA 中看到 103 个有效定位历元，按相邻输出历元推断的期望数量为 105，位置输出覆盖率为 `0.980952`。最长连续有效定位为 46 s，首次定位由 stdout 的 receiver-time marker 约束在 29–30 s。未观察到显式 no-fix 历元；有两个各 1 s 的 `POSITION_OUTPUT_GAP`。tracking 层有 21 个确认失锁事件，最大单次约 5.370 s。

因此，当前证据支持“Highway/Open POOR 在 GNSS-SDR 中仍能形成持续定位”，但不支持“tracking 从未失锁”。

#### Urban POOR

该任务也可以定位。审计在 NMEA 中看到 12/12 个有效定位历元，覆盖率为 1.0，最长连续定位为 12 s，首次定位下界约为 59 s。未观察到显式 no-fix 历元；tracking 层有 26 个确认失锁事件，最大单次约 4.728 s。

这里需要保留一个重要限制：虽然定位历元连续达到工程门槛，但当前输出中可见的定位段只有 12 s，不能把它表述为整段约 134 s 记录都持续定位。

#### Mountain/Valley POOR

当前不能判断其是否能够定位。该任务执行成功并产生 tracking、telemetry、observables 等文件，但没有 NMEA 或可用 PVT 定位输出，因此审计分类为 `INCONCLUSIVE_NO_POSITION_OUTPUT`。tracking 层记录了 40 个确认失锁事件、最大单次约 5.527 s，但这仍不能替代 PVT/NMEA 证据。

Mountain/Valley GOOD 也出现相同的“无定位输出”现象，而 Mountain/Valley RAIN 能形成 67/85 个有效定位历元。这说明当前首先需要审查 Mountain/Valley 的定位输出链、配置和日志，而不是直接将 POOR 归因于“信号过于苛刻”。

## 4. 按环境和条件的比较

### 4.1 Highway/Open

Highway/Open 的 GOOD、POOR、RAIN 三项均形成 `SUSTAINED_FIX`。三者定位输出覆盖率分别为 0.991、0.981 和 0.991，POOR 比 GOOD 少两个有效/期望历元，最长连续定位由 74 s 降为 46 s，但没有变成无法定位。三项首次定位边界均约在 27–30 s。

在当前这一条记录、当前配置下，Highway/Open POOR 的表现更接近“可定位但 tracking 事件较多、定位输出有少量缺口”，而不是“完全不能定位”。

### 4.2 Urban

Urban GOOD 和 POOR 都形成 12/12 的连续有效定位输出，均在约 59 s 之后出现首个定位证据。两者的可见定位段均只有 12 s，因此应将其记为“短时段 sustained fix”，不能据此评价整个记录时长内的持续可用性。

### 4.3 Mountain/Valley

Mountain/Valley GOOD 与 POOR 均没有 NMEA/PVT 定位输出，分别被审计为 `INCONCLUSIVE_NO_POSITION_OUTPUT`；RAIN 则形成 67/85 个有效定位历元，覆盖率 0.788，并包含一个 18 s 的位置输出缺口。当前条件对比不完整，不能从 GOOD/POOR 的这两个无定位输出任务直接估计“POOR 失锁概率”。

## 5. Tracking 失锁统计（独立于定位输出）

本节统计来自 tracking 输出的去抖失锁事件，不是 PVT/NMEA 无解时间，也不是车辆接收机失锁时间。

- 八个任务共 207 个确认 tracking lock-loss 事件。
- 汇总确认失锁时长约 107.937 s；最长单次事件约 5.639 s。
- 事件时长分布：小于 0.1 s 的 112 个，0.1–小于 0.5 s 的 60 个，0.5–小于 1 s 的 10 个，至少 1 s 的 25 个。
- 其中 120 个事件有审计器确认的 reacquisition，87 个没有确认的 reacquisition；后者不能直接解释为整段信号永久失锁，因为还受到 tracking 文件边界和观测连续性的影响。
- 按任务计数：Highway/Open GOOD/POOR/RAIN 为 24/21/20；Mountain/Valley GOOD/POOR/RAIN 为 28/40/19；Urban GOOD/POOR 为 29/26。

本项目当前采用的 tracking 观测规则是：`carrier_lock_test < -0.5` 连续至少 20 ms 记为失锁，连续 100 ms 锁定才确认恢复。该规则用于工程诊断，不能直接当作车辆地图定位状态。

## 6. 输出完整性与异常项

### 6.1 完整性

- 六个有定位输出的任务各有 65 个输出文件，并有 NMEA、PVT、tracking、telemetry、observables 及日志。
- Mountain/Valley GOOD 和 POOR 各有 57 个文件；两者共同缺少 NMEA/PVT 定位输出，因此输出层完整性只能记为 `INCOMPLETE`，不是执行退出失败。
- 八个任务的执行 receipt 均为完成态，且 GNSS-SDR exit code 为 0。因而“没有定位输出”不是由 receipt 直接报告的执行异常，而是输出产品层的缺失。

### 6.2 未观察到的内容

- 八个任务均没有被审计器标记为显式 `NO_FIX` 历元；Mountain/Valley GOOD/POOR 是“没有定位输出”，不是“输出了无解历元”。
- 审计没有把 tracking lock-loss 解释为物理多径、车机失锁或车辆硬件故障。
- 审计没有改变 POOR/GOOD/RAIN 标签，也没有读取和重解释 raw IQ 的样本内容。

## 7. 工程判定

|任务组|当前判定|是否可直接回答“GNSS-SDR能定位”|
|---|---|---|
|Highway/Open POOR|`SUSTAINED_FIX`，QA PASS|可以；但存在 tracking 失锁和少量位置输出缺口|
|Urban POOR|`SUSTAINED_FIX`，QA PASS|可以；但当前可见定位段只有 12 s|
|Mountain/Valley POOR|`INCONCLUSIVE_NO_POSITION_OUTPUT`，QA INCOMPLETE|不可以；需先解决/解释 PVT/NMEA 缺失|
|八任务整体|6/8 定位层 PASS，2/8 定位层 INCOMPLETE|不能把八项整体概括为全部能定位或全部不能定位|

## 8. 相关 artifact

- 全量任务汇总：[task_summary.csv](../dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_all8_20260915_r1/task_summary.csv)
- 中文 v2 审计汇总：[signal_quality_report_cn.md](../dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_all8_20260915_r1/signal_quality_report_cn.md)
- Tracking 逐 PRN 汇总：[prn_tracking_summary.csv](../dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_all8_20260915_r1/prn_tracking_summary.csv)
- 失锁区间：[lock_loss_intervals.csv](../dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_all8_20260915_r1/lock_loss_intervals.csv)
- 定位区间：[position_intervals.csv](../dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_all8_20260915_r1/position_intervals.csv)
- 审计 provenance：[audit_manifest.json](../dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_all8_20260915_r1/audit_manifest.json)
- 原始执行输出根目录：[runs](../dataset_generation_logs/darkroom_rx_gnss_sdr/darkroom_rx_0913_gnss_sdr_v1_20260914/runs)
- 原始执行 receipt 根目录：[receipts](../dataset_generation_logs/darkroom_rx_gnss_sdr/darkroom_rx_0913_gnss_sdr_v1_20260914/receipts)

## 9. 下一步建议

唯一优先事项是先对 Mountain/Valley GOOD 与 POOR 的无 NMEA/PVT 输出做输出链诊断：核对对应配置、stdout 末尾、PVT/NMEA writer 路径和文件生成状态，确认是 GNSS-SDR 输出链问题还是确实没有形成解。完成该诊断前，不应重跑或 resume 既有 namespace，也不应把 Mountain/Valley POOR 标为“无法定位”。

## 10. 状态声明

```text
DARKROOM_RX_ALL8_EXECUTION=COMPLETED_8_OF_8
DARKROOM_RX_ALL8_RECEIPT_EXIT0=8_OF_8
DARKROOM_RX_ALL8_POSITION_QA_PASS=6_OF_8
DARKROOM_RX_ALL8_POSITION_QA_INCOMPLETE=2_OF_8
DARKROOM_RX_HIGHWAY_POOR_POSITIONABILITY=SUSTAINED_FIX
DARKROOM_RX_URBAN_POOR_POSITIONABILITY=SUSTAINED_FIX
DARKROOM_RX_MOUNTAIN_POOR_POSITIONABILITY=INCONCLUSIVE_NO_POSITION_OUTPUT
DARKROOM_RX_TOTAL_TRACKING_LOSS_EVENTS=207
DARKROOM_RX_RAW_IQ_READ_BY_AUDITOR=NO
DARKROOM_RX_GNSS_SDR_INVOKED_BY_AUDITOR=NO
DARKROOM_RX_MATLAB_INVOKED_BY_AUDITOR=NO
DARKROOM_RX_SAGE_INVOKED_BY_AUDITOR=NO
NEXT_DECISION_REQUIRED=DIAGNOSE_MOUNTAIN_GOOD_POOR_POSITION_OUTPUT_CHAIN
```
