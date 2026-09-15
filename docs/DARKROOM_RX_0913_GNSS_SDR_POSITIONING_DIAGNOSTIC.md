# 0913DarkroomRx GNSS-SDR 定位与失锁诊断执行说明

## 1. 目标与状态

本诊断用于回答八段暗室接收记录在固定 GNSS-SDR 配置下是否能够产生定位解、各跟踪 PRN 的失锁持续时间如何，以及车机界面异常更倾向于输入信号过苛刻还是接收端/HMI 恢复特异性。

当前状态为 **Implemented + all 8 GNSS-SDR executions completed + corrected v2 read-only QA completed**。本流程不调用 MATLAB、SAGE 或 raw-coarse，也不写入 `scenes/**/sage_results`。

冻结输入合同：

- 采样率：`10,230,000 Hz`；
- 样本格式：interleaved signed int16 little-endian I/Q，即 GNSS-SDR `ishort`；
- 每个复样本 4 bytes；
- 文件名中的 `pool` 由用户确认表示 `poor`，manifest 中规范化为 `POOR`，原文件名仍保留；
- GPS 信号：GPS L1 C/A；
- WSL：`Ubuntu-22.04`，GNSS-SDR `/usr/bin/gnss-sdr`，版本 `0.0.16`。

Immutable request：

- Manifest：`E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr\darkroom_rx_0913_gnss_sdr_v1_20260914\batch_manifest.json`
- Manifest SHA-256：`4c589f7f6df5be6284b9f4c8975c595af963c065b45151707aa3c617d12ba704`
- 任务数：8；validation-only 为 8/8 PASS；所有 output namespace 在冻结及 validation-only 时均不存在。
- `highway_open_good_1023` 已由正常用户完成 GNSS-SDR smoke execution；其 v2 QA 位于 `dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_highway_good_smoke_20260914_r2`，结果为 `SUSTAINED_FIX`。其余七项随后也已由正常用户执行完成；全量 v2 QA 位于 `dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_all8_20260915_r1`。

## 当前全量审计快照（2026-09-15）

八个任务的 execution receipt 均为 `completed`、exit code `0`。全量定位层审计结果为 6/8 `SUSTAINED_FIX`、2/8 `INCONCLUSIVE_NO_POSITION_OUTPUT`：

|任务|定位分类|QA|说明|
|---|---|---|---|
|`highway_open_poor_1023`|`SUSTAINED_FIX`|PASS|103/105 个有效/期望历元，覆盖率 0.981，最长连续定位 46 s|
|`mountain_valley_poor_1023`|`INCONCLUSIVE_NO_POSITION_OUTPUT`|INCOMPLETE|无 NMEA/PVT；有 tracking 输出和 40 个 tracking 失锁事件，不能据此判定物理上无法定位|
|`urban_poor_1023`|`SUSTAINED_FIX`|PASS|12/12 个有效/期望历元，最长连续定位 12 s；可见定位段较短|

详细汇总见 `docs/DARKROOM_RX_0913_ALL8_SIGNAL_QUALITY_REPORT_CN.md`。Mountain/Valley GOOD 与 POOR 的无定位输出需要先做输出链诊断；已有 namespace 不得 resume 或覆盖。

## 2. 八个任务

|顺序|Task ID|源文件|环境|条件|估计记录时长 (s)|
|---:|---|---|---|---|---:|
|1|`highway_open_good_1023`|`highway_open_good_1023.bin`|Highway/Open|GOOD|138.093|
|2|`highway_open_poor_1023`|`highway_open_pool_1023.bin`|Highway/Open|POOR|133.793|
|3|`highway_rain_1023`|`highway_rain_1023.bin`|Highway/Open|RAIN|134.993|
|4|`mountain_valley_good_1023`|`mountain_open_good_1023.bin`|Mountain/Valley|GOOD|124.472|
|5|`mountain_valley_poor_1023`|`mountain_open_pool_1023.bin`|Mountain/Valley|POOR|132.459|
|6|`mountain_valley_rain_1023`|`mountain_rain_1023.bin`|Mountain/Valley|RAIN|137.706|
|7|`urban_good_1023`|`urban_open_good_1023.bin`|Urban|GOOD|133.864|
|8|`urban_poor_1023`|`urban_open_pool_1023.bin`|Urban|POOR|133.715|

文件总量为 43,747,315,712 bytes（约 40.74 GiB），按冻结格式对应约 17.82 min 的信号记录。每个 raw 文件的 SHA-256、大小、mtime、配置及源码 hash 均记录在 immutable manifest 中。

## 3. 手工步骤一：只运行 GOOD smoke

在正常 Windows PowerShell 7 中运行：

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' `
  'E:\GNSS_Multipath_Project\scripts\analysis\darkroom_rx\run_darkroom_rx_gnss_sdr_batch.py' `
  --manifest 'E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr\darkroom_rx_0913_gnss_sdr_v1_20260914\batch_manifest.json' `
  --expected-manifest-sha256 '4c589f7f6df5be6284b9f4c8975c595af963c065b45151707aa3c617d12ba704' `
  --task-id 'highway_open_good_1023' `
  --execute --confirm-darkroom-rx-gnss-sdr
```

正常行为应包括：先重新验证该 raw SHA-256，再创建唯一 output，随后由 WSL 顺序运行 GNSS-SDR；结束时应打印 `EXECUTION_STATUS=completed` 和 receipt 路径。若出现 nonzero exit、interrupted、output exists、SHA mismatch 或 source/config hash changed，应停止，不要删除或复用该输出。

GOOD smoke 完成后，运行只读 QA：

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' `
  'E:\GNSS_Multipath_Project\scripts\analysis\darkroom_rx\audit_darkroom_rx_signal_quality.py' `
  --manifest 'E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr\darkroom_rx_0913_gnss_sdr_v1_20260914\batch_manifest.json' `
  --expected-manifest-sha256 '4c589f7f6df5be6284b9f4c8975c595af963c065b45151707aa3c617d12ba704' `
  --qa-dir 'E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr_qa\darkroom_rx_0913_highway_good_smoke_20260914_r1' `
  --task-id 'highway_open_good_1023'
```

GOOD smoke 的 execution receipt 已为 completed、tracking 可读且 PVT/NMEA 输出可判读；v2 QA 记录 110/111 个预期位置历元、1 个 `POSITION_OUTPUT_GAP`，并未观察到 explicit no-fix epoch。全量任务已经执行完成；若任务 QA 为 `INCONCLUSIVE_NO_POSITION_OUTPUT`，应先审查配置/输出链，不能直接把它解释为信号无法定位。

## 4. 历史手工步骤二：顺序运行其余七项

GOOD smoke 审计通过后，可用一个批命令按 manifest 顺序运行剩余七项；执行器一次只启动一个 GNSS-SDR，并在首个失败处停止：

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' `
  'E:\GNSS_Multipath_Project\scripts\analysis\darkroom_rx\run_darkroom_rx_gnss_sdr_batch.py' `
  --manifest 'E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr\darkroom_rx_0913_gnss_sdr_v1_20260914\batch_manifest.json' `
  --expected-manifest-sha256 '4c589f7f6df5be6284b9f4c8975c595af963c065b45151707aa3c617d12ba704' `
  --task-id 'highway_open_poor_1023' `
  --task-id 'highway_rain_1023' `
  --task-id 'mountain_valley_good_1023' `
  --task-id 'mountain_valley_poor_1023' `
  --task-id 'mountain_valley_rain_1023' `
  --task-id 'urban_good_1023' `
  --task-id 'urban_poor_1023' `
  --execute --confirm-darkroom-rx-gnss-sdr
```

该命令对应的历史执行已完成。若未来需要处理某项已有输出，partial output 和 receipt 必须保留；该 task 不能从同一 namespace resume，需诊断后另建 immutable request。已经 completed 的任务不要再次包含在后续命令中。

## 5. 全部完成后的只读 QA

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' `
  'E:\GNSS_Multipath_Project\scripts\analysis\darkroom_rx\audit_darkroom_rx_signal_quality.py' `
  --manifest 'E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr\darkroom_rx_0913_gnss_sdr_v1_20260914\batch_manifest.json' `
  --expected-manifest-sha256 '4c589f7f6df5be6284b9f4c8975c595af963c065b45151707aa3c617d12ba704' `
  --qa-dir 'E:\GNSS_Multipath_Project\dataset_generation_logs\darkroom_rx_gnss_sdr_qa\darkroom_rx_0913_all8_20260914_r1'
```

QA 输出包括：

- `task_summary.csv`：任务级执行状态、定位分类、有效定位历元、最长连续定位/无定位、跟踪 PRN 数和失锁总量；
- `prn_tracking_summary.csv`：每个 PRN 的 C/N0、Doppler、锁定比例、失锁次数与时长；
- `lock_loss_intervals.csv`：每次确认失锁的起止时刻、持续时长、是否恢复及右删失状态；
- `position_intervals.csv`：FIX/NO_FIX 时间段；
- `vehicle_observation_template.csv`：需人工填写的车机地图、精度、GPS 时间和重启恢复现象；
- `signal_quality_report_cn.md`：中文汇总与保守归因矩阵；
- `audit_manifest.json`：所有 QA 表的 hash/provenance。

## 6. 冻结判定语义

- tracking 失锁：`carrier_lock_test < -0.5` 连续至少 20 ms；恢复要求连续 100 ms 锁定；时间缺口一律不跨越拼接。
- 定位分类：至少连续 5 s 有效 PVT/NMEA 解记为 `SUSTAINED_FIX`；该门槛是工程报告规则，不是物理信道定律。
- 跟踪失锁与定位中断是两个不同层次，必须分别报告。
- `NO_FIX_OBSERVED` 只表示当前记录与配置下未观察到有效 GNSS-SDR 解，不等于物理无卫星或纯 NLOS。
- 车机异常且 GNSS-SDR 持续定位，只支持“车机接收链、恢复逻辑或 HMI 特异性更可疑”的判断，不能单凭该结果断言车辆硬件损坏。

## 7. 需要人工提供的信息

GNSS-SDR 执行与车机现象无法由离线脚本代替，需人工完成两件事：

1. 按第 3 节先运行 GOOD smoke，并把终端末尾的 receipt/status 发回项目 QA；
2. 对每段同源车机测试填写 `vehicle_observation_template.csv` 中的地图位置、精度、GPS 时间更新、无重启恢复及重启后恢复状态。

其余工作——请求冻结、哈希核验、配置生成、顺序调度、tracking/PVT/NMEA 统计和报告生成——均已脚本化。v1 QA namespace 保留为历史诊断证据，v2 QA namespace 是当前 GOOD smoke 的规范审计结果。
