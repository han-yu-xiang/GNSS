# 0913DarkroomRx 自发自收信道可用性报告

**报告日期：** 2026-09-15
**用途：** 为 16 个暗室仿真场景建立统一信道质量报告方法，并汇总当前已经完成的 8 个 GNSS-SDR 接收任务。
**报告性质：** 只读诊断汇总；不重新读取 raw IQ，不重新运行 GNSS-SDR、MATLAB 或 SAGE。

## 1. 结论先行

可以为暗室场景输出统一的信道报告，至少包括：

- 信号总时长；
- GNSS-SDR 执行状态和运行时间；
- tracking 层失锁事件数、失锁累计时长和最长单次失锁；
- 明确确认的重捕获次数；
- NMEA/PVT 首次定位时间、有效定位历元、定位覆盖率、最长连续定位和定位输出缺口；
- 输出是否达到预先定义的“动态轨迹可用”门禁。

但必须区分两个事实：

1. 当前已经存在的是 **16 个参数表组合**：4 类环境 × 2 类质量 × Dry/Base 或 RainPooled 两种天气层。它们不是可以直接交给 GNSS-SDR 的 IQ 文件；需要先由信道模拟器按参数表产生实际回放/接收信号。
2. 昨天已经分析的是 8 个 `0913DarkroomRx` GNSS-SDR 任务。它们是现有的先导接收证据，但不构成与 16 个参数表逐一对应的 16 场景验证包，尤其不包含 Special Reflective 的对应任务，也不等同于 16 个 RainPooled 表的接收验证。

当前 8 个任务的结果为：6/8 达到已有审计定义的 `SUSTAINED_FIX`，2/8 为 `INCONCLUSIVE_NO_POSITION_OUTPUT`。其中 Highway/Open POOR 可以定位，Urban POOR 有一段短时连续定位，Mountain/Valley POOR 因没有 NMEA/PVT 输出暂时不能判定。

## 2. 数据与审计范围

|项目|实际值|
|---|---|
|0913 输入 manifest|`E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr\darkroom_rx_0913_gnss_sdr_v1_20260914\batch_manifest.json`|
|Manifest SHA-256|`4c589f7f6df5be6284b9f4c8975c595af963c065b45151707aa3c617d12ba704`|
|GNSS-SDR|WSL `/usr/bin/gnss-sdr`，version `0.0.16`|
|输入采样率|10,230,000 Hz|
|输入格式|interleaved signed int16 little-endian I/Q；GNSS-SDR `item_type=ishort`|
|全量 QA namespace|`E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr_qa\darkroom_rx_0913_all8_20260915_r1`|
|QA schema|`darkroom-rx-signal-quality-audit-v2`|
|审计 manifest SHA-256|`6a1c678a49221b1b2a4dbaeba17765d01316fcc7029a513d6122128c369d08f3`|
|审计工具 SHA-256|`02e72cfea6388090cbb60e8f5c0e2203e53fac2d70b8db3789eb2684cf3ce0ba`|

本报告使用的冻结审计产物及 SHA-256：

|文件|SHA-256|
|---|---|
|`task_summary.csv`|`c2c1de3961920a85f66f0d8f037c6c3b77b6bfde12ce100c5ebba561e3872808`|
|`lock_loss_intervals.csv`|`9f2e4dea266931dbe75d162de7d79a87e15782c569c65b970e9f3e8ba428bb76`|
|`position_intervals.csv`|`9094238643f0f71c442650655ecf6ac4f6610fa7091e32324a2f0230295dce37`|
|`prn_tracking_summary.csv`|`21dd13e158609db7a0e8a4508f3069584d8865a6c8b76355f25761e3d22a7b6e`|

审计过程只读取 receipt、manifest、GNSS-SDR 日志、tracking/telemetry/observables、PVT/NMEA 和已生成 QA CSV；`raw_iq_read_by_auditor=false`，没有读取 raw IQ 内容。

## 3. 统一报告方法

### 3.1 信号总时长

信号总时长取任务 manifest/receipt 中的 `recording_duration_s`，而不是 GNSS-SDR wall-clock runtime。两者分别回答“信号有多长”和“处理花了多久”。

### 3.2 Tracking 失锁与重捕获

每个 GNSS-SDR tracking 文件按 PRN 流统计。当前审计规则为：

- `carrier_lock_test < -0.5` 连续至少 20 ms：记为一次 tracking lock-loss；
- 后续连续至少 100 ms 恢复锁定：记为一次审计器确认的 reacquisition。

因此报告中的“失锁事件数”是所有 PRN tracking 流的事件总数，不是一个已经去重为“整段复合信号只失锁一次”的数；多个卫星可以在相近时间分别发生事件。失锁累计时长也是 PRN 流时长之和，不能直接除以单个信号时长后称为整段信号不可用比例。

没有确认重捕获的事件只能写为“在可见 tracking 记录中未确认恢复”，不能写成永久失锁。tracking 失锁也不能直接等同于车辆 HMI 丢定位。

### 3.3 定位时间和定位覆盖

定位层优先使用 NMEA/PVT：

- 首次有效定位时间：从 GNSS-SDR stdout 的 first-fix marker 给出相对时间边界；
- 有效定位历元：NMEA GGA fix quality=1 且 RMC status=A 的可见历元；
- 定位覆盖率：有效历元数 / 根据相邻输出历元推断的期望历元数；
- 有效定位时长：在 1 Hz 输出条件下，以有效历元数近似表示，并同时报告最长连续有效定位区间；
- 定位输出缺口：仅表示相邻可见输出之间没有输出，不伪造为显式 no-fix；
- 没有 NMEA/PVT：标记为 `INCONCLUSIVE_NO_POSITION_OUTPUT`，不能判为物理不可定位。

已有 `SUSTAINED_FIX` 只表示至少 5 s 连续有效定位输出。对于暗室动态轨迹信道，还应另外冻结一个更严格的 `DYNAMIC_TRAJECTORY_USABLE` 门禁，例如整段覆盖率、最大定位中断时长、首定位时间和重复性；该门禁必须在 16 个场景执行前冻结，不能根据结果事后调整。

### 3.4 最终状态分层

建议每个任务同时保存以下状态，而不是压缩成一个“好/坏”标签：

|层级|建议状态|含义|
|---|---|---|
|执行层|`COMPLETED` / `FAILED`|GNSS-SDR 进程和输出任务是否正常结束|
|tracking 层|`LOCK_EVENTS_OBSERVED` 等|PRN tracking 中的失锁/恢复证据|
|定位层|`SUSTAINED_FIX` / `NO_POSITION_OUTPUT`|是否有可见 NMEA/PVT 定位输出|
|动态轨迹层|`USABLE` / `DEGRADED` / `REJECTED` / `INCONCLUSIVE`|是否通过预先冻结的暗室信道可用性门禁|
|车机层|单独记录|车机地图/HMI 是否显示定位，不能由 GNSS-SDR 结果替代|

## 4. 昨天 8 个任务的定位结果

|任务|环境/条件|信号时长 (s)|GNSS-SDR runtime (s)|tracking PRN数|定位输出|有效/期望历元|覆盖率|首次定位 (s)|有效定位历元（约 s）|最长连续定位 (s)|最大位置缺口 (s)|定位分类|
|---|---|---:|---:|---:|---|---:|---:|---|---:|---:|---:|---|
|`highway_open_good_1023`|Highway/Open / GOOD|138.093|140.531|21|NMEA|110/111|0.991|27–28|110|74|1|SUSTAINED_FIX|
|`highway_open_poor_1023`|Highway/Open / POOR|133.793|152.500|22|NMEA|103/105|0.981|29–30|103|46|1|SUSTAINED_FIX|
|`highway_rain_1023`|Highway/Open / RAIN|134.993|154.968|22|NMEA|106/107|0.991|28–29|106|65|1|SUSTAINED_FIX|
|`mountain_valley_good_1023`|Mountain/Valley / GOOD|124.472|142.078|21|无 NMEA/PVT|0/0|—|—|0|0|—|INCONCLUSIVE_NO_POSITION_OUTPUT|
|`mountain_valley_poor_1023`|Mountain/Valley / POOR|132.459|156.250|21|无 NMEA/PVT|0/0|—|—|0|0|—|INCONCLUSIVE_NO_POSITION_OUTPUT|
|`mountain_valley_rain_1023`|Mountain/Valley / RAIN|137.706|150.844|20|NMEA|67/85|0.788|53–54|67|49|18|SUSTAINED_FIX|
|`urban_good_1023`|Urban / GOOD|133.864|155.703|21|NMEA|12/12|1.000|约59，未见上界|12|12|0|SUSTAINED_FIX*|
|`urban_poor_1023`|Urban / POOR|133.715|153.110|20|NMEA|12/12|1.000|约59，未见上界|12|12|0|SUSTAINED_FIX*|

`*` Urban 的 `SUSTAINED_FIX` 只描述可见的 12 s 连续定位段，不能表述为约 134 s 全程持续定位。

### 4.1 失锁与重捕获明细

|任务|失锁事件数（跨 PRN）|失锁累计时长 (s，跨 PRN)|最长单次失锁 (s)|确认重捕获数|未确认重捕获数|
|---|---:|---:|---:|---:|---:|
|`highway_open_good_1023`|24|17.890|5.106|13|11|
|`highway_open_poor_1023`|21|6.880|5.370|10|11|
|`highway_rain_1023`|20|17.300|5.639|15|5|
|`mountain_valley_good_1023`|28|16.770|5.252|14|14|
|`mountain_valley_poor_1023`|40|11.630|5.527|22|18|
|`mountain_valley_rain_1023`|19|16.320|5.003|12|7|
|`urban_good_1023`|29|6.250|1.581|18|11|
|`urban_poor_1023`|26|14.900|4.728|16|10|
|**合计**|**207**|**107.937**|**5.639**|**120**|**87**|

### 4.2 8 个任务合计

- 信号总时长：`1069.094 s`，约 `17 min 49.094 s`。
- GNSS-SDR 处理 wall-clock：`1205.984 s`，约 `20 min 5.984 s`。
- tracking PRN 流失锁事件：`207` 次。
- 审计器明确确认的重捕获：`120` 次。
- 在可见 tracking 记录中未确认重捕获：`87` 次；不等于永久失锁。
- 跨 PRN 流失锁累计时长：`107.937 s`；不等于单一复合信号的不可用时长。
- 最长单次失锁：`5.639 s`。
- 有位置输出的 6 个任务合计：`410/432` 个有效/期望 NMEA 定位历元，覆盖率约 `0.9491`；该合计不包含两个无 NMEA/PVT 输出任务的未知定位状态。
- 8 个任务中 `SUSTAINED_FIX=6`，`INCONCLUSIVE_NO_POSITION_OUTPUT=2`。

## 5. 当前 POOR 条件的直接判断

### Highway/Open POOR

当前证据支持 GNSS-SDR 可以定位：`103/105`，覆盖率 `0.980952`，最长连续定位 `46 s`，首次定位约 `29–30 s`。tracking 层有 21 次失锁，确认重捕获 10 次；有两个约 1 s 的位置输出缺口。因此它是“可定位但 tracking 事件和少量定位缺口存在”，不是“完全不可定位”。

### Urban POOR

当前证据支持在可见输出段内可以定位：`12/12`，连续 `12 s`，首次定位下界约 `59 s`。但可见定位段仅 12 s，不能把它写成整段约 134 s 连续可用。按照当前“动态轨迹需要相对长时间持续定位”的用途门禁，Urban/POOR 可以作为压力样本保留，但不宜直接作为当前动态定位可用信道。

### Mountain/Valley POOR

当前不能判定。该任务有 tracking、telemetry、observables 等输出，也有 40 次 tracking 失锁，但没有 NMEA/PVT 定位输出。更重要的是 Mountain/Valley GOOD 同样没有 NMEA/PVT，而 Mountain/Valley RAIN 能输出 `67/85` 个有效定位历元。因此现有证据首先指向“定位输出链/任务条件需要进一步诊断”，不足以单独证明 POOR 信号物理上无法定位。

## 6. 16 个仿真场景的报告对象

当前 16 个参数表资产由以下两组组成：

|天气层|目录|组合数|当前状态|
|---|---|---:|---|
|Dry/Base|`E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\0828darkroomPar\tables\`|8|8 张 5 分钟参数表已生成并有导出追溯|
|RainPooled|`E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\rain_effect_layer_stage3_v1_20260830_r5\tables\`|8|8 张 5 分钟参数表已生成并通过已有 Rain QA|

矩阵为：

|环境|Dry/Base GOOD|Dry/Base POOR|RainPooled GOOD|RainPooled POOR|
|---|---|---|---|---|
|Urban|`urban__good.csv`|`urban__poor.csv`|`urban__good__rain.csv`|`urban__poor__rain.csv`|
|Special Reflective|`special_reflective__good.csv`|`special_reflective__poor.csv`|`special_reflective__good__rain.csv`|`special_reflective__poor__rain.csv`|
|Mountain/Valley|`mountain_valley__good.csv`|`mountain_valley__poor.csv`|`mountain_valley__good__rain.csv`|`mountain_valley__poor__rain.csv`|
|Highway/Open|`highway_open__good.csv`|`highway_open__poor.csv`|`highway_open__good__rain.csv`|`highway_open__poor__rain.csv`|

每张表为 `300000 ms`、`3,600,000` 行，固定 canonical schema：

```text
ms,SatelliteID,NLOSPathID,RelativeDelay,RelativeDoppler,RelativeAmplitude,RelativePhase_rad
```

这里的“16 个场景已具备”是参数生成层结论。要得到“16 个场景的自发自收信道报告”，还需要每张表进入信道模拟器，产生对应的实际 IF/IQ 回放或接收文件，再由 GNSS-SDR 逐任务处理并生成与第 4 节相同的审计字段。不能把 CSV 参数表直接当成 GNSS-SDR 定位结果。

## 7. 建议的 16 场景信道报告生产流程

### 阶段 A：冻结输入

为每一个场景建立唯一 task record，冻结：环境、GOOD/POOR、Dry/Base 或 RainPooled、参数表路径及 SHA-256、采样率、回放时长、GNSS-SDR 配置、输出 namespace 和 `new_only=true`。16 个 task record 必须使用新的独立 manifest，不修改现有参数表、Rain 层或 0913 QA artifact。

### 阶段 B：产生可接收信号

信道模拟器读取参数表并输出实际可被 GNSS-SDR 读取的信号。若经过硬件自发自收，则记录回放开始、结束、输出文件大小、格式、采样率和对应 task ID；若是文件型仿真输出，也应生成不可变的输出 receipt。该阶段才产生 16 份可以进入 GNSS-SDR 的信号输入。

### 阶段 C：GNSS-SDR 接收

按唯一 task namespace 顺序执行或受控批量执行。每个任务保持相同的配置语义和报告字段，禁止用某个场景的结果修改另一个场景的阈值。执行成功只代表 GNSS-SDR 任务完成，不代表信道已经通过动态轨迹可用性门禁。

### 阶段 D：只读信道质量审计

每个任务生成一行任务级 summary，同时保留逐 PRN、逐失锁区间和逐定位区间明细：

```text
task_id
environment / quality / weather_layer
signal_duration_s
gnss_sdr_runtime_s
execution_status / exit_code
tracking_prn_count
lock_loss_events_total
lock_loss_duration_sum_s
max_lock_loss_s
confirmed_reacquisition_count
unconfirmed_reacquisition_count
first_fix_time
valid_fix_epochs / expected_fix_epochs
position_coverage
max_continuous_fix_s
position_gap_count / max_position_gap_s
positionability_class
dynamic_trajectory_usability
```

最终 16 行汇总中另设三个总览：

1. `GNSS-SDR output availability`：是否有 NMEA/PVT；
2. `tracking stability`：失锁与恢复；
3. `dynamic trajectory usability`：是否达到冻结的整段可用门禁。

如果要把结果和车机对照，还应增加独立的 vehicle-HMI observation 列，但它不能覆盖 GNSS-SDR 的客观输出层结论。

## 8. 下一步建议

1. 先保留当前 8 个结果作为先导诊断，不把它们冒充成 16 场景完成报告。
2. 在 16 个真实回放/接收任务开始前，冻结 `DYNAMIC_TRAJECTORY_USABLE` 的定位覆盖率、最大中断时长、首定位时间和重复性门禁。
3. 对 Mountain/Valley GOOD/POOR 的 NMEA/PVT 缺失单独做输出链诊断；在该问题未解释前，不要将其标为“信号不能定位”。
4. 完成 16 个信号的 GNSS-SDR 接收后，用同一套 QA 生成 `16/16` 的 channel report，再决定哪些信道进入车辆复测。
5. 当前不建议先用“失锁次数 / 信号秒数”直接定义概率；先按 PRN-observation exposure 形成事件率，再单独报告 PVT 可用率和定位中断分布。

## 9. 状态声明

```text
DARKROOM_PARAMETER_SCENARIO_TABLES=16_AVAILABLE
DARKROOM_SELF_RECEIVE_GNSS_SDR_REPORT=8_TASKS_ANALYZED
DARKROOM_SELF_RECEIVE_16_TASK_REPORT=NOT_YET_COMPLETE
DARKROOM_0913_POSITION_QA_PASS=6_OF_8
DARKROOM_0913_POSITION_QA_INCONCLUSIVE=2_OF_8
DARKROOM_0913_TOTAL_SIGNAL_DURATION_S=1069.094
DARKROOM_0913_TOTAL_TRACKING_LOSS_EVENTS=207
DARKROOM_0913_CONFIRMED_REACQUISITIONS=120
DARKROOM_0913_RAW_IQ_READ_BY_AUDITOR=NO
DARKROOM_0913_GNSS_SDR_INVOKED_BY_AUDITOR=NO
DARKROOM_0913_MATLAB_INVOKED_BY_AUDITOR=NO
DARKROOM_0913_SAGE_INVOKED_BY_AUDITOR=NO
NEXT_DECISION_REQUIRED=FREEZE_16_TASK_SIGNAL_CAPTURE_AND_DYNAMIC_TRAJECTORY_GATE
```
