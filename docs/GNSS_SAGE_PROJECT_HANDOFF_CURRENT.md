# GNSS SAGE 项目当前交接与研究总结

> **历史文档：** 当前工程状态唯一来源为 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源为 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。本文件仅作历史参考。

**项目根目录：** `E:\GNSS_Multipath_Project`  
**基线日期：** 2026-08-11（Asia/Shanghai）  
**文档对象：** 后续 AI Agent、研究人员、实验执行人员与论文写作者  
**当前总状态：** 10.23 MHz full-scan Pipeline V3、reference scene 七 PRN、Wave-A 三任务和 Wave-2A G11 已有实测结果；批量执行安全链已验证；`batch-sampled-v1` 与 `batch-sampled-v1.1` 均已完成离线 replay 但判定 **FAIL / no sampled pilot**；20.46 MHz 尚未适配；事件数据库和最终统计信道模型尚未实现。

> 本文是“截至当前时点”的长期基线，不是待办设计稿。文中使用四种状态：**已实验验证**、**已实现但未放行**、**仅设计/规划**、**未开始/无数据支撑**。后续不得把后三者写成实验结论。

## 0. 权威来源、读取顺序与已知版本冲突

### 0.1 后续 AI 应采用的来源优先级

出现数字或状态不一致时，按以下顺序取证：

1. 实际 `scenes/<scene>/sage_results/...` 下的 Stage CSV/MAT 与 `run_context.json`；
2. 对应 Windows execution receipt、`batch_execution_log.csv`、status history、task log 和独立 QA 报告；
3. 最终封存报告，如 `reference_scene_final_validation_report.md`、`WAVEA_10MHz_VALIDATION_REPORT.md`、`WAVE2A_G11_QA_REPORT.md`；
4. 最新 sampling 最终 manifest/CSV，v1.1 必须使用 `dataset_generation_logs/sampling_validation/batch_sampled_v1_1_offline_coverage/tow_aligned/`；
5. `dataset/dataset_inventory.csv` 用于 scene 输入状态和 PRN/channel 映射；
6. 设计文档用于解释计划，不用于证明功能已经实现或实验已经通过；
7. 早期 handoff、daily handoff 和旧 summary 仅作历史参考。

### 0.2 已确认的历史冲突

| 冲突 | 当前结论 | 应以何者为准 |
|---|---|---|
| 早期 `docs/PROJECT_DATA_STRUCTURE.md` 曾描述只有 reference scene 完成标准化 | 当前 19 个 scene 的 GNSS-SDR、navigation、trajectory、satellite geometry 输入均已整理；inventory 中相应存在性字段为真，geometry 均为 `completed` | 当前 `dataset/dataset_inventory.csv`、各 scene `metadata.json`、实际目录和 2026-08-06 生成日志 |
| `dataset_inventory.csv.sage_results_status` 对非 reference scene 仍常为 `not_run` | inventory 是未随实验回写的输入快照；Wave-A 和 Wave-2A G11 的结果实际存在且已 QA PASS | 实际 `sage_results`、execution log、QA 报告；不要修改 inventory 来“修正”历史快照 |
| `prn_validation_summary.csv` 只有五 PRN | reference 最终基线是七 PRN；G29/G32 不在旧 CSV 中 | `reference_scene_final_validation_report.md` 与七个实际结果目录 |
| `MULTIPATH_EVENT_DATABASE_DESIGN.md` 的旧 Current Status 写 batch runner 尚未创建 | batch planner、executor 和 Windows wrapper 后来均已实现 | 当前脚本与 batch/Windows QA 文档 |
| `WAVE2A_G11_QA_REPORT.md` 当时允许受控继续剩余 Wave-2A | 后续 runtime/sampling 工作表明不应继续盲目 full-scan；剩余任务当前暂停 | 较新的 sampling 设计及 v1/v1.1 FAIL 报告 |
| 某些任务说明仍称 v1.1 “正在进行/尚待完成” | v1.1 已实现、已做 440 次主 replay 与 budget sweep，最终 FAIL | `docs/BATCH_SAMPLED_V1_1_OFFLINE_COVERAGE_REPORT.md` 和 `.../tow_aligned/sampling_validation_manifest_v1_1.json` |

## 1. 研究总目标与科学问题

本项目从 GPS L1 C/A 原始复数 IQ、GNSS-SDR tracking/telemetry/导航与轨迹输出出发，用 navigation-symbol-aided SAGE 提取多径路径，并将每个结果追溯到 `scene × PRN × tracking channel × time/window`。最终目标不是只发现少量案例，而是建立可统计、可复现的多径/信道模型数据集，至少包括：

- 多径发生概率；
- 路径数量；
- 相对 LOS 的 excess delay（samples、chips，必要时派生距离）；
- 相对功率；
- Doppler offset；
- coherence 与时间持续性；
- scene、PRN、仰角、CN0、速度和环境条件的关联。

最终仰角条件固定为：

- `LOW`：0–30°；
- `MID`：30–60°；
- `HIGH`：60–90°。

当前已经得到的是 SAGE 算法规则下的 `confirmed multipath`，不是外部测量真值。最终统计模型必须同时使用 confirmed paths 和**覆盖完整**的 negative/no-event 窗口；采样模式中未扫描的窗口不能作为 negative，也不能推断为 LOS。

## 2. 项目目录与数据集结构

### 2.1 根目录

| 路径 | 当前用途 |
|---|---|
| `scenes/` | 19 个标准 scene；保存 metadata、标准输入、几何和 SAGE 结果 |
| `scripts/preprocessing/` | navigation、trajectory、satellite geometry 与 inventory 生成脚本 |
| `scripts/sage_pipeline/` | Pipeline V3、legacy G06、batch planner/executor、Windows wrapper、sampling planner 与测试 |
| `dataset/` | 当前主清单 `dataset_inventory.csv`；未来 event database 的建议落点，但数据库尚未创建 |
| `dataset_generation_logs/` | 标准化日志、batch plan/execution/request/receipt、sampling validation 生成物 |
| `docs/` | 设计、诊断、QA、封存报告和本交接文档 |
| `configs/` | 项目配置材料；运行前仍需按实际文件检查，不应由本文假设内容 |
| `full_parse_v1/` | GNSS-SDR 完整解析历史来源/工作区；标准 scene 已把所需结果整理到 `scenes/` |
| `MATLAB_RUNTIME_CACHE_TEST/` | MATLAB 启动诊断产生的隔离测试目录，不是 SAGE 数据集 |

### 2.2 单个标准 scene

```text
scenes/<scene_id>/
├── metadata.json
├── raw/
├── gnss_sdr/
│   ├── config/
│   ├── logs/
│   ├── tracking/
│   ├── telemetry/
│   ├── observables/
│   ├── pvt/
│   ├── rinex/
│   ├── nmea/
│   ├── metadata.json
│   └── run_status.json
├── navigation/
│   ├── rinex_nav/
│   └── rinex_obs/
├── trajectory/
├── satellite/
└── sage_results/
```

- `metadata.json`：scene ID/role、信号、采样率、raw IQ 路径与存储方式、处理状态、标准化 provenance。
- `raw/`：reference scene 存放本地 IQ；其余 scene 通常仅保留地址说明，实际 IQ 在外部目录。
- `gnss_sdr/tracking/`：逐 channel tracking `.dat/.mat`；当前 SAGE 读取指定 channel 的 MAT。
- `gnss_sdr/telemetry/`：逐 channel NAV telemetry/CRC 文件；当前 SAGE 读取指定 channel 的 telemetry DAT。
- `gnss_sdr/observables/`、`pvt/`：GNSS-SDR observables/PVT 输出，可用于后续上下文和 QA，但不是当前 Pipeline V3 的核心 SAGE 输入。
- `gnss_sdr/rinex/`、`nmea/`：GNSS-SDR 原始整理来源。
- `navigation/`：标准化的 RINEX NAV/OBS 副本。
- `trajectory/`：标准化 `<scene_id>_trajectory.nmea`。
- `satellite/`：NMEA GSV 派生的逐时刻与 PRN summary CSV。
- `sage_results/`：full-scan 或 legacy 实验结果。未来 sampled 结果必须使用新 namespace，不能混入现有 `nav_sage_v2`。

reference scene 还含 `legacy_results/`，其 `sage_results/G06_nav_sage_v1/` 是受保护的历史算法基线。

### 2.3 19 个 scene 和采样率分布

`dataset/dataset_inventory.csv` 当前有 19 行、124 个 scene–PRN 任务：13 个 10.23 MHz scene（83 个任务）和 6 个 20.46 MHz scene（41 个任务）。

| Scene | Role | Rate | 可用 PRN 数 | Raw 模式 |
|---|---|---:|---:|---|
| `F1023_V120_D0121_P2` | standard | 10.23 MHz | 10 | external |
| `F1023_v50_D0127_P1` | standard | 10.23 MHz | 5 | external |
| `F1023_V70_D0117_P2` | reference | 10.23 MHz | 7 | scene-local |
| `F1023_V70_D0117_P4` | standard | 10.23 MHz | 7 | external |
| `F1023_V70_D0120_P1` | standard | 10.23 MHz | 5 | external |
| `F1023_V70_D0120_P5` | standard | 10.23 MHz | 5 | external |
| `F1023_V70_D0120_P7` | standard | 10.23 MHz | 4 | external |
| `F1023_V70_D0120_P8` | standard | 10.23 MHz | 4 | external |
| `F1023_V70_D0120_P9` | standard | 10.23 MHz | 9 | external |
| `F1023_V70_D0122_P1` | standard | 10.23 MHz | 8 | external |
| `F1023_V70_D0122_P2` | standard | 10.23 MHz | 7 | external |
| `F1023_V80_D0117_P8` | standard | 10.23 MHz | 6 | external |
| `F1023_v90_D0117_P7` | standard | 10.23 MHz | 6 | external |
| `F2046_V30_D0131_P2` | standard | 20.46 MHz | 7 | external |
| `F2046_V30_D0131_P4` | standard | 20.46 MHz | 8 | external |
| `F2046_V30_D0203_P2` | standard | 20.46 MHz | 7 | external |
| `F2046_V60_D0129_P1` | standard | 20.46 MHz | 6 | external |
| `F2046_V60_D0129_P3` | standard | 20.46 MHz | 8 | external |
| `F2046_V60_D0202_P1` | standard | 20.46 MHz | 5 | external |

### 2.4 Raw IQ 规则

- reference：`scenes/F1023_V70_D0117_P2/raw/F1023_V70_D0117_P2.bin`，约 2.34 GiB。
- 其余 18 个：`E:\AAGNSSSDR_input\raw_data\<scene_id>.bin`，由 metadata 和 `raw/data_address.txt` 指向；当前只读检查中均存在。
- 最大的当前 raw 是 `F1023_V120_D0121_P2.bin`，约 24.61 GB（十进制）/22.92 GiB；该事实与 Wave-2A G11 的长运行直接相关，但不是已证实的唯一性能根因。
- 运行前必须读取 metadata 的 `raw_iq.path` 并 `Test-Path`，不能用 scene 名拼接后假设存在。

### 2.5 标准化生成方式与状态

| 数据 | 脚本 | 实际动作 | 状态/日志 |
|---|---|---|---|
| Navigation | `scripts/preprocessing/batch_prepare_navigation.py` | 从 `gnss_sdr/rinex` 复制（不移动）唯一 `.26N/.26O` 到 `navigation/rinex_nav`、`rinex_obs`，校验已有目标和 SHA-256 | 19 scene 已整理；`dataset_generation_logs/navigation_prepare_20260806_134959_505548.log` |
| Trajectory | `scripts/preprocessing/batch_prepare_trajectory.py` | 从 `gnss_sdr/nmea` 复制唯一 trajectory NMEA 到 `trajectory/`；reference 已有目标只比较不覆盖 | 19 scene 已整理；`dataset_generation_logs/trajectory_prepare_20260806_135239_205975.log` |
| Satellite geometry | `scripts/preprocessing/satellite_geometry.py`、`batch_generate_satellite_geometry.py` | 解析 NMEA RMC/GSV，RINEX NAV 只用于 GPS PRN 过滤，原子写两个 CSV | 19 scene 均 `completed`、每 scene 两个 CSV；`dataset_generation_logs/batch_satellite_geometry_20260806_141452_394272.log` |
| Inventory | `scripts/preprocessing/generate_dataset_inventory.py` | 只读扫描 scene，生成 scene-level CSV、PRN/channel map、输入存在性和 warning | `dataset/dataset_inventory.csv`；当前 19 scene/124 task |

## 3. GNSS-SDR 输入输出链和卫星几何

### 3.1 数据流

```text
raw complex IQ
  -> GNSS-SDR acquisition/tracking/telemetry/observables/PVT
  -> tracking MAT + telemetry DAT + RINEX + NMEA
  -> standardized navigation/trajectory
  -> NMEA-GSV satellite geometry + dataset inventory
  -> SAGE Stage0–Stage4
  -> QA-approved events/paths
  -> future event database
  -> future elevation/speed/scene-conditioned statistical channel model
```

### 3.2 各 GNSS-SDR 数据的当前用途

| 输入 | 当前用途 |
|---|---|
| Tracking MAT | PRN/channel 对应的 tracking sample、carrier Doppler、code frequency、CN0、lock、tracking TOW；Stage0 对齐和后续搜索中心/质量门禁 |
| Telemetry DAT | 已解码 GPS NAV symbol、PRN、sample counter、TOW；构造可擦除 NAV 的连续 20 ms symbol 与 40 ms window |
| RINEX NAV `.26N` | 标准 navigation 输入；当前 geometry 生成器仅提取含星历记录的 GPS PRN 作为 GSV 过滤集合 |
| RINEX OBS `.26O` | 已标准化保留，当前 Pipeline V3 不直接读取 |
| Trajectory NMEA | RMC 速度/UTC 与 GSV；Pipeline Stage0 尝试提供 vehicle speed 和 Doppler bound，geometry 由 GSV 生成 |
| Observables/PVT | 保留用于后续定位/信号质量/时间关联研究；当前确认规则不依赖这些目录 |

### 3.3 Geometry 的真实逻辑和限制

实际输出为：

- `satellite/<scene_id>_satellite_elevation_timeseries.csv`
- `satellite/<scene_id>_satellite_elevation_summary.csv`

`satellite_geometry.py` 的明确实现语义是：

- elevation、azimuth、NMEA SNR 来自带时间戳的 NMEA GSV；
- RINEX NAV 只用于保留具有 GPS ephemeris 记录的 PRN；
- **没有**从 broadcast ephemeris 重新计算卫星 ECEF/接收机视线/仰角；
- summary 是 PRN/run-level 摘要，不能冒充 event/window 的瞬时仰角。

第一版 sampling planner 用 `trajectory first RMC + recording_time_s` 做 window/UTC join，在 11 个 gold task 上全部退化为 warning；v1.1 增加了只用于离线诊断的 TOW+RMC 确定性 offset 校准，使 reference 七项、Wave-A G16/G12、Wave-2A G11 达到验证门槛，Wave-A G25 仍 fallback。该 TOW join **尚未**集成到 SAGE Pipeline 或正式 event database，因此当前 Stage4 事件没有可直接声明的 elevation/azimuth。

## 4. SAGE Pipeline V3

### 4.1 入口、接口和当前采样率边界

主入口：`scripts/sage_pipeline/run_nav_sage_pipeline.m`

```matlab
run_nav_sage_pipeline(sceneId, prn, ...
    "TrackingChannel", channel, ...
    "ProjectRoot", "E:\GNSS_Multipath_Project", ...
    "Resume", true)
```

- `sceneId`、`prn` 是必需位置参数；`prn` 可接受数值或 `Gxx` 字符串。
- `TrackingChannel` 是必需 name-value 参数，必须显式给出，pipeline 不替用户在 multi-channel 中猜测。
- `ProjectRoot` 可选，默认由脚本位置推导，但 batch/可复现实验应显式冻结。
- `Resume` 默认 `true`，只表示可加载匹配的 checkpoint/已有阶段；它**不是覆盖许可**。batch 生产使用 `new_only` 且输出目录必须不存在。
- 代码在输入解析阶段明确 `assert(sample_rate_hz == 10.23e6)`。因此当前只验证 10.23 MHz；20.46 MHz 虽存在于 inventory/旧 dry-run plan，也不能调用本 pipeline。
- 10.23 MHz 下 `samplesPerChip=10`；Stage2 0.1 sample 即 0.01 chip。

### 4.2 Stage0–Stage4 流程

| Stage | 输入 | 目的和关键逻辑 | 主要输出 | 状态语义 |
|---|---|---|---|---|
| Stage0 NAV catalog | telemetry DAT、tracking MAT、trajectory NMEA | 只保留目标 PRN、NAV symbol ±1、CN0≥30 dB-Hz、lock≥-0.5、sample/TOW 连续的 symbol；以连续 20 ms symbol 构造完整 40 ms window，记录 CN0、速度来源与 Doppler bound | `stage0_valid_symbols.csv`、`stage0_valid_40ms_windows.csv`、`stage0_nav_catalog.mat` | 全量母集；sampling 方案也不得删 Stage0 window |
| Doppler sign | raw IQ、Stage0/跟踪信息 | 对 GNSS-SDR Doppler 符号进行 raw correlation 校准 | `doppler_sign.mat` | 后续 Stage1–4 使用的符号 provenance |
| Stage1 fast scan | raw IQ、Stage0 windows、NAV symbols | NAV wipe 后对当前 full-scan 的每个有效 40 ms window 扫描 main/residual peak；残差强度门槛 -25 dB；最多 24 个 base、至少 8 个 fallback，并加入每个 seed 的 ±2 邻窗 | `stage1_nav_fast_scan.csv/.mat`、`stage1_nav_progress.mat` | screening/candidate 证据，不是 confirmed multipath |
| Stage2 fractional SAGE | Stage1 candidate windows | 对每个 candidate 评估 L=1,2,3,4；0.1 sample delay grid、最小 path separation 1 sample、path power≥-25 dB、coherence≤0.98、顺序 BIC gain≥10、incremental RSS gain≥0.002% | `stage2_model_orders.csv`、`stage2_selected_windows.csv`、`stage2_selected_paths.csv`、MAT/progress | `L>=2` 只表示当前窗口选中了多分量模型，**不等于 confirmed multipath** |
| Stage3 persistence | Stage2 fits | 对中心的 ±2 window 检查 delay/Doppler/power 一致性；最小连续长度 3，容差 1.5 sample、40 Hz、10 dB；所有中心多径需通过 | `stage3_persistence.csv`、`stage3_reliable_centers.csv`、`stage3_nav_persistence.mat` | persistent/reliable candidate；仍不是最终确认 |
| Stage4 joint 100 ms | Stage3 reliable centers、五个相邻 20 ms snapshot | common-geometry joint L1–L4，最多处理排序后的 8 个中心；至少 4 snapshot 胜过 L1；最多 8 iterations | `stage4_joint_summary.csv`、`stage4_joint_paths.csv`、`stage4_nav_joint_100ms.mat` | 当前 confirmed criterion：`joint_valid=1 && joint_multipath_count>0`，且入库 QA 还应核对 path 表确有 `is_multipath=1` |

Stage4 的 coherence 当前是 event/model-level `maximum_coherence`，不是每条 path 独立 coherence。`stage4_joint_paths.csv` 的功率字段为 `mean_relative_power_db`；数据库可映射为 canonical `relative_power_db`，但必须保留 source field。

### 4.3 21 个标准目标文件

一个完整 `nav_sage_v2/<PRN>` 当前应有 21 个文件：

1. `run_context.json`, `run_context.mat`
2. `stage0_nav_catalog.mat`, `stage0_valid_symbols.csv`, `stage0_valid_40ms_windows.csv`
3. `doppler_sign.mat`
4. `stage1_nav_fast_scan.csv`, `stage1_nav_fast_scan.mat`, `stage1_nav_progress.mat`
5. `stage2_model_orders.csv`, `stage2_selected_windows.csv`, `stage2_selected_paths.csv`, `stage2_nav_sage_L1_L4.mat`, `stage2_nav_progress.mat`
6. `stage3_persistence.csv`, `stage3_reliable_centers.csv`, `stage3_nav_persistence.mat`
7. `stage4_joint_summary.csv`, `stage4_joint_paths.csv`, `stage4_nav_joint_100ms.mat`
8. `<PRN>_nav_sage_overview.png`，例如 `G16_nav_sage_overview.png`

只有表头的 Stage3/Stage4 CSV 可以是合法的 zero-event 结果；不能仅因无数据行判为失败。反之，目录存在或 checkpoint 存在也不能证明完整完成。

## 5. Reference scene 七 PRN 封存基线

### 5.1 Scene 和来源

- `scene_id=F1023_V70_D0117_P2`
- role=`reference_scene`
- sample rate=`10230000 Hz`
- raw IQ 为 scene-local
- GNSS-SDR、navigation、trajectory、satellite geometry 当前均完成
- 最终权威报告：`scenes/F1023_V70_D0117_P2/sage_results/reference_scene_final_validation_report.md`

### 5.2 完整 Stage 统计

| PRN | Ch | NAV | 40 ms | Stage1 scan | candidates | L1/L2/L3/L4 | L≥2 | L≥3 | Stage3 | Stage4 | confirmed event/path | 归类 |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| G06 | 4 | 321 | 319 | 319 | 95 | 8/29/17/41 | 87 | 58 | 2 | 2 | 2/4 | confirmed；legacy v1 |
| G11 | 5 | 1177 | 1175 | 1175 | 101 | 45/4/22/30 | 56 | 52 | 7 | 7 | 1/1 | confirmed |
| G12 | 6 | 1177 | 1175 | 1175 | 96 | 38/12/1/45 | 58 | 46 | 4 | 4 | 2/2 | confirmed |
| G25 | 0 | 1177 | 1175 | 1175 | 52 | 40/2/0/10 | 12 | 10 | 0 | 0 | 0/0 | LOS/low-multipath reference |
| G28 | 1 | 900 | 898 | 898 | 54 | 42/4/5/3 | 12 | 8 | 2 | 2 | 0/0 | candidate rejected by Stage4 |
| G29 | 7 | 1177 | 1175 | 1175 | 77 | 45/6/2/24 | 32 | 26 | 1 | 1 | 1/1 | confirmed |
| G32 | 11 | 1177 | 1175 | 1175 | 117 | 31/15/1/70 | 86 | 71 | 11 | 8 | 2/3 | confirmed |

每个 Stage2 candidate 都评估四个模型，因此 L1–L4 evaluation 总数依次为 380、404、384、208、216、308、468。这里的 L1/L2/L3/L4 是最终选中数，不是所有 attempted/valid fit 数。

Stage3 center：G06 203/264；G11 641/642/317/640/643/730/769；G12 972/970/971/651；G25 无；G28 693/298；G29 80；G32 83/82/84/143/144/145/759/760/761/347/349。

### 5.3 Reference confirmed events

共有 8 个 confirmed event、11 条 confirmed multipath path。下表 delay 是相对 LOS 的 excess delay；Doppler 是 signed offset；coherence 是 event-level maximum coherence。

| PRN/window | Time s | MP paths | Excess delay sample/chip | Doppler offset Hz | Relative power dB | Coherence |
|---|---:|---:|---|---|---|---:|
| G06/203 | 41.8614130009775 | 3 | 1.6/.16; 2.6/.26; 8.3/.83 | +149.6643; +199.6643; +149.6643 | +18.1926; +6.9025; +7.1046 | .332664 |
| G06/264 | 43.0814179863148 | 1 | 3.9/.39 | +159.6643 | +22.0595 | .034598 |
| G11/640 | 50.5987614858260 | 1 | 1.1/.11 | -10.0131 | -7.4071 | .828954 |
| G12/970 | 57.1917811339198 | 1 | 1.1/.11 | +24.4273 | -15.9205 | .577073 |
| G12/971 | 57.2117812316716 | 1 | 1.1/.11 | -0.5997 | -5.1136 | .886065 |
| G29/80 | 39.3959774193548 | 1 | 1.1/.11 | -5.3357 | -3.1518 | .869766 |
| G32/82 | 39.4369887585533 | 2 | 1.1/.11; 2.5/.25 | +19.6643; -65.3357 | -11.3788; -19.5141 | .677380 |
| G32/84 | 39.4769889540567 | 1 | 1.1/.11 | +14.6643 | -8.8363 | .766091 |

### 5.4 物理解释边界和保护

- G25 是当前阈值下的 algorithmic LOS/low-multipath control，不证明真实信道绝对无反射。
- G28 证明 Stage2 高阶和 Stage3 persistence 不足以确认多径：两个 Stage4 row 均 `joint_valid=1` 但 joint L=1、MP count=0。
- G06/G11/G12/G29/G32 至少有一个符合当前 Stage4 criterion 的事件。
- `scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/` 是永久保护 baseline，不能覆盖、移动、删除或写入辅助文件。
- 其他六个 reference 结果位于 `sage_results/nav_sage_v2/Gxx/`。G06 与六个 V3 run 的版本 provenance 必须保留，不能假装是同一 namespace。

## 6. Batch 规划、执行与 QA 体系

### 6.1 Dry-run plan

主 plan 快照：`dataset_generation_logs/batch_sage/batch_sage_dry_run_20260808T113454Z/batch_sage_plan.csv`。

| 状态 | 数量 | 语义 |
|---|---:|---|
| `ready` | 92 | 当时通过 plan 输入门禁；其中 64 个 10.23、28 个 20.46 |
| `not_started` + blocked | 25 | 输入/geometry/channel warning 硬阻断 |
| `completed_or_existing` | 6 | reference 的六个 v2 结果 |
| `skipped` | 1 | protected G06 legacy |
| multi-channel | 5 | 全部 blocked，必须人工选择，planner 不自动挑 channel |

注意：旧 planner 把 20.46 MHz 列为可规划 rate，但实际 `run_nav_sage_pipeline.m` 仍只允许 10.23 MHz。后续 executor/wrapper 的 10.23 rate gate 优先；不能因 plan row=`ready` 就运行 20.46。

### 6.2 关键脚本

- `scripts/sage_pipeline/generate_batch_sage_plan.py`：inventory -> scene–PRN task；检查 raw/tracking/telemetry/navigation/trajectory/geometry、multi-channel、输出冲突，输出 plan/report/issues/manifest；不运行 MATLAB。
- `scripts/sage_pipeline/run_batch_sage.py`：只接受 plan + 显式 `selected_tasks.csv`；默认 dry-run；`--execute` 才调用 MATLAB；重新 preflight、验证 pipeline hash、固定输出 namespace、隔离单任务失败、记录 status/history/log。
- `scripts/sage_pipeline/Invoke-BatchSageWindows.ps1`：正常用户身份/immutable request 的 Windows 外层；不复制 Python executor 的 SAGE policy。

### 6.3 状态和完成 QA

任务状态包括 `not_started`、`ready`、`running`、`completed`、`failed`、`skipped`；plan 还用 `completed_or_existing`。完成至少要求：

- MATLAB return code 0；
- Python executor 状态 `completed`；
- 21 个目标文件存在且非空；
- `run_context` 与 request 的 scene/PRN/channel/rate 一致；
- Stage0–Stage4 链路可读，合法空表不误判；
- 输出仅位于批准的 target；
- 单独 post-run QA PASS 后才放行下一任务/阶段。

### 6.4 Immutable request 与重现性

每个执行请求位于 `dataset_generation_logs/batch_sage_execution_requests/<request_id>/`，冻结：

- one-task selection snapshot；
- scene、PRN、channel、sample rate；
- plan、pipeline、executor 与 selection SHA-256；
- `experiment_namespace=nav_sage_v2`；
- `execution_mode=new_only`；
- `resume_allowed=false`；
- `max_parallel_matlab=1`；
- MATLAB executable、approved Windows identity、startup smoke requirement。

执行审计在 `dataset_generation_logs/batch_sage_execution/<timestamp>/`，Windows receipt 在 `.../windows_runner_receipts/<request_timestamp>/`。现有输出目录一旦存在，request 不得复用；checkpoint/resume 必须作为另一个明确审批问题处理，不能自动重试。

## 7. Codex sandbox 与 Windows MATLAB 执行边界

### 7.1 已实验确认的失败

初始 Wave1 由 `tj-channel\codexsandboxoffline` 直接 `subprocess` 启动 MATLAB，五个任务都在 Stage0 前失败，return code 1，错误为：

```text
System Error: File system inconsistency
```

重定向 TEMP/TMP、`MATLAB_PREFDIR` 和新建可写 cache 目录均未解决。ACL 和 profile 检查显示 sandbox 进程继承了 `Jing_` 的 profile 路径，但对 MathWorks preferences、toolbox cache、ServiceHost、licensing/credentials 等目录的权限/身份上下文与正常交互用户不同。现有证据支持“Codex sandbox 执行身份不适合启动该 MATLAB 安装”这一工程结论，但没有证明某一个内部文件就是唯一 root cause。

### 7.2 正常用户和 DDUX 退出期事件

`TJ-CHANNEL\Jing_` 正常 Windows 用户可以启动 MATLAB。诊断期间曾出现一次 marker 已打印但退出 code 3 的 native shutdown crash，stack 含 `ddux.dll` / `mwddux_matlab.dll`，MATLAB 为 `25.1.0.2973910 (R2025a) Update 1`，exe file metadata 为 `25.1.0.2802752`。另一次同环境 smoke 为 exit 0，因此这是间歇性退出路径证据，不应臆断为单一服务或用户设置故障。

安全结论始终不变：wrapper 必须同时要求 `MATLAB_STARTUP_OK` marker 和 exit code 0；绝不能把 marker 存在或 exit 3 当作成功。需要进一步解决时，应保留 crash dump/receipt，考虑官方 Update/repair 或向 MathWorks 提交，而不是放宽门禁。

### 7.3 当前采用的架构

Codex 只负责生成/审核 request、hash、计划与只读 QA；MATLAB 由 `TJ-CHANNEL\Jing_` 在非管理员 PowerShell 7 中手工调用 `Invoke-BatchSageWindows.ps1`。wrapper 当前职责：

1. 验证正常 Windows identity 并拒绝 sandbox principal；
2. 验证 request SHA-256 及其引用的 plan/selection/pipeline/executor hash；
3. 用规范化、Windows 不区分大小写的真实目录边界检查，拒绝 prefix collision、`..`、跨盘逃逸；
4. 将 output 严格限定到 `scenes/<exact scene>/sage_results/nav_sage_v2/<exact PRN>`；
5. 默认 validation-only；必须同时 `-Execute -ConfirmPilot`；
6. 获取全局 Windows runner lock；
7. 先执行最小 MATLAB smoke，要求 marker+exit0；
8. 以已验证的 Python executable 调用唯一 executor；
9. 读取 execution log 确认唯一批准任务 `completed`，生成 environment/execution receipt；
10. 不解释 inventory、不选择 channel、不复制 Pipeline 或 Python task gates。

## 8. Wave-A 10.23 MHz 验证

权威汇总：`docs/WAVEA_10MHz_VALIDATION_REPORT.md`；单任务 QA：`PILOT1_G16_QA_REPORT.md`、`WAVEA_G25_QA_REPORT.md`、`WAVEA_G12_QA_REPORT.md`。

### 8.1 执行与统计

| Task | Runtime | NAV/40ms | Stage2 eval valid selected | L1/L2/L3/L4 | L≥2/L≥3 | Stage3 reliable | Stage4 joint | confirmed event/path |
|---|---:|---|---|---|---|---:|---:|---:|
| `F1023_V70_D0120_P7/G16/ch1` | 3913.123 s / 65.219 min | 2231/2229 | 416/340/104 | 20/34/17/33 | 84/50 | 11 | 8 | 4/4 |
| `F1023_v50_D0127_P1/G25/ch0` | 2724.903 s / 45.415 min | 2343/2339 | 424/259/106 | 106/0/0/0 | 0/0 | 0 | 0 | 0/0 |
| `F1023_V70_D0122_P1/G12/ch6` | 2949.653 s / 49.16 min | 1631/1629 | 428/356/107 | 21/17/12/57 | 86/69 | 11 | 8 | 3/3 |

三项均由正常用户 wrapper 执行，MATLAB/Python exit 0、21 文件完整、输出隔离 PASS。G25 的 Stage3/4 header-only/zero-row 是合法空事件结果，不是中断。

### 8.2 Wave-A confirmed events

| Task/window | Time s | Excess delay sample/chip | Doppler offset Hz | Relative power dB | Coherence |
|---|---:|---|---:|---:|---:|
| G16/1337 | 68.502853 | 1.2/.12 | +19.6532 | -4.5894 | .6678 |
| G16/1338 | 68.522853 | 1.0/.10 | +19.9106 | -3.2640 | .6829 |
| G16/1406 | 69.882856 | 1.1/.11 | -3.0423 | -6.3379 | .8809 |
| G16/2079 | 83.342881 | 1.1/.11 | -3.8204 | -5.0925 | .8778 |
| G12/835 | 44.9110977517107 | 1.4/.14 | -71.565443 | -16.250123 | .184743 |
| G12/836 | 44.9310977517107 | 1.3/.13 | -71.464876 | -15.369289 | .187128 |
| G12/1278 | 53.7711064516129 | 4.5/.45 | -78.552207 | -13.211903 | .109428 |

G12 QA 另列的是 path 的绝对 delay/Doppler（例如 path Doppler 约 -1623 Hz）；上表是相对 LOS 的 excess delay 与 Doppler offset。二者字段语义不同，不是矛盾。

### 8.3 Wave-A 结论

三种关键行为均出现：confirmed multipath（G16/G12）、合法无事件/LOS-like control（G25）、稳定的执行与隔离。它证明 10.23 MHz 下“immutable request → normal-user wrapper → smoke → Python executor → Pipeline V3 → 21-file QA”是可控的；只放行**受控、串行、逐任务审批与 QA**，不证明可以无门禁全量运行，也不支持 20.46 MHz。

## 9. Wave-2A G11 与 10.23 MHz 扩展状态

### 9.1 G11 full-scan 实测

任务：`F1023_V120_D0121_P2/G11/ch0/10.23MHz`。权威 QA：`docs/WAVE2A_G11_QA_REPORT.md`。

- 最终 PASS；MATLAB/Python exit 0；21 文件完整并隔离。
- 执行：2026-08-09 09:49:48Z 至 2026-08-10 05:27:20Z，70652.187 s，约 19 h 37 min 32 s。
- Stage0：15,224 NAV symbols、15,210 个 40 ms windows。
- Stage1：全量扫描 15,210；约 8 h 07 min 40 s；选 67 candidate。
- Stage2：268 rows、258 valid、67 selected；L1/L2/L3/L4=65/1/0/1；约 11 h 26 min 19 s。
- Stage3：4 条 path record，center 9161（L4、3 paths）和 15065（L2、1 path）；均 `00100`、最长连续 1；reliable center=0。
- Stage4：0 joint、0 path、0 confirmed，属于完整合法空结果。
- reference G11 只有 1,175 windows；本任务约 12.94× windows，Stage1 约 17.7× wall time。外部 raw I/O、单线程、资源竞争和数据特征均只是待 profiling 假设，不能写成已证明原因。

### 9.2 Wave-2 规划快照和当前变化

`docs/WAVE2_10MHz_CONTROLLED_EXPANSION_PLAN.md` 的筛选链：124 总任务 → 83 个 10.23 → 排除 reference 7 → 排除 12 blocked → 64 → 排除 Wave-A 已有 3 → **61 个候选、12 scene**。

Wave-2A 五项：

| 顺序 | Task | 当前状态 |
|---:|---|---|
| 1 | `F1023_V120_D0121_P2/G11/ch0` | 已执行，QA PASS；full-scan gold |
| 2 | `F1023_V70_D0117_P4/G12/ch4` | immutable request 已生成；输出不存在；暂停未执行 |
| 3 | `F1023_V70_D0120_P1/G18/ch2` | request 已生成；暂停未执行 |
| 4 | `F1023_V70_D0120_P5/G23/ch0` | request 已生成；暂停未执行 |
| 5 | `F1023_V80_D0117_P8/G31/ch1` | request 已生成；暂停未执行 |

因此 61 是生成计划时的新任务 pool；其中 G11 后来完成，按该快照尚余 60 个未执行候选。没有重新生成当前 plan，不能把“60”冒充一个新的正式 plan 版本。

Wave-2B 仅是规划，未生成/放行：`F1023_V70_D0120_P8/G16/ch4`、`F1023_V70_D0120_P9/G05/ch10`、`F1023_V70_D0122_P2/G15/ch8`、`F1023_v90_D0117_P7/G11/ch6`、`F1023_V70_D0120_P7/G18/ch4`、`F1023_v50_D0127_P1/G11/ch10`、`F1023_V70_D0122_P1/G13/ch5`。

**当前释放状态：** Wave-2A 剩余 full-scan 不应继续盲跑；它们虽有 request，仍处于暂停，需等待新 sampling 策略离线通过或由研究负责人对必要 full-scan 金标准逐任务另行批准。

## 10. Stage1/Stage2 batch sampling 设计与实际验证

### 10.1 两种模式

| 模式 | Stage0 | Stage1 | Stage2 | 用途/状态 |
|---|---|---|---|---|
| `full-scan` | 全量 | 全量 40 ms windows | 仅 Stage1 candidates、L1–L4 | 已验证；reference/论文 gold；成本高 |
| `batch-sampled-v1` | 全量 | 可复现样本+adaptive guard，设计上限 1200 | 仅有完整 Stage1/closure 的 candidates | planner/replay 已实现但 FAIL；未运行真实 sampled SAGE |

初始设计：`N0<=1200` 使用 `full-scan-equivalent`；长任务总 Stage1≤1200，初始目标 800、预留最多 400；24 个时间层、每层至少 20；确定性 11-window burst；Stage0 CN0 P20/P80 分 Low/Mid/High；可靠时加入 elevation LOW/MID/HIGH；固定 seed；Stage1 seed 的 ±2 closure 必须完整，预算允许再 ±5。Stage2 仍只处理 Stage1 candidate。

重要状态语义：

- `selected`、`not_selected`、`scan_failed` 必须区分；
- 未扫描 window 不能叫 rejected、LOS 或 no-event；
- sampled 无 confirmed 只能表示“已覆盖窗口未确认”，coverage 不完整时为 `sampling_inconclusive`；
- sampled 结果必须新版本化 namespace，**不得写回 `nav_sage_v2`**。

### 10.2 v1 planner 和离线 replay：已实现但 FAIL

实现：`generate_batch_sampling_plan.py`；测试：`test_generate_batch_sampling_plan.py`；报告：`docs/BATCH_SAMPLED_V1_OFFLINE_COVERAGE_REPORT.md`。

11 task × 10 seeds = 110 plans/manifests：reference 七 PRN + Wave-A G16/G25/G12 + Wave-2A G11。所有输出在 `dataset_generation_logs/sampling_validation/batch_sampled_v1_offline_coverage/`，未写任何 `sage_results`。

- reference 因 N0≤1200 为 full-scan-equivalent：8/8 event centers 与 80/80 closure 100%；Stage3 closure 270/270。
- Wave-A G16：event center `19/40=47.5%`；±2 closure `10/40=25.0%`。
- Wave-A G12：event center `16/30=53.3%`；±2 closure `11/30=36.7%`。
- Wave-A G25、Wave-2A G11 没有 confirmed event，recall 为 N/A，不能记为正样本 100%。
- 11 项 geometry 均为 warning fallback，只使用 time+CN0；没有用 PRN summary 均值伪造 elevation。

失败根因不只是缺 guard：event center 若不在初始 Stage1 暴露集，就不会产生 seed，围绕已有 seed 添加 ±2 无法发现它。

### 10.3 v1.1 连续 block + strict adaptive replay：已完成、仍 FAIL

实现：`generate_batch_sampling_plan_v1_1.py`；测试：`test_generate_batch_sampling_plan_v1_1.py`；最终报告：`docs/BATCH_SAMPLED_V1_1_OFFLINE_COVERAGE_REPORT.md`；权威输出：`.../batch_sampled_v1_1_offline_coverage/tow_aligned/`。

- 11 task × 10 seeds × 4 block profiles = 440 `sampling_plan.json` + 440 manifest。
- block=11/21/31/41；24 时间层；初始预算 `max(800,24×block_length)`，41-window profile 初始 984。
- full-scan `stage1_nav_fast_scan.csv` 只作 offline surrogate。
- 只有初始 selected row 的 Stage1 可参与 Pipeline V3 candidate 排序；hidden row 不可选 seed。
- adaptive 顺序：最多 24 visible seeds → seed±2 → 预算允许的固定 seed±5。
- Gold Stage3/Stage4 标签只在事后算 recall，不参与选窗。

1200 budget 的 15 个 known positive event 加权结果：

| Block | Initial center | Adaptive center | Initial ±2 closure | Adaptive ±2 closure |
|---:|---:|---:|---:|---:|
| 11 | 73.33% | 81.33% | 66.67% | 76.67% |
| 21 | 76.67% | 81.33% | 72.00% | 75.33% |
| 31 | 82.67% | 83.33% | 79.33% | 80.00% |
| 41 | 80.00% | 81.33% | 79.33% | 80.67% |

reference 仍 100%，但这是 short/full-scan-equivalent，不能证明长 scene 策略。G16 最好 adaptive center/closure 仅 62.5%/60%；G12 11-block 最好为 90%/90%，仍低于硬门槛。

budget sweep 800–4800：没有任一 `(block,budget)` 对 seed_00–09、全部 positive task 稳定达到 center+closure 100%。少数单 seed 在 1600/2200/4000 局部通过不能作为 production minimum。结构会在最多 24 个 visible seed 周围饱和，剩余预算不能发现新隐藏 seed，因此不是简单把预算或 guard 增大即可。

v1.1 的 TOW geometry diagnostic 使多数 task join verified；Wave-A G25 仍 coverage=.684、p95=16.612s、fallback。geometry 改进没有消除 event 漏检，说明二者是独立问题。

Python static compile 与 8 个单元测试通过，但 sampling scientific gate 失败。**最终状态：FAIL / no sampled pilot / 不得生成 sampled execution request。**

### 10.4 下一版真正需要解决的问题

当前应称为 v1.2 或新的明确 profile，而不是把失败的 v1.1 当作已放行。它必须具备“发现初始 sample 之外新 seed”的全时段低成本 screening/adaptive exploration；继续使用 full-scan Stage1 surrogate 时仍不得偷看 hidden row。放行门槛保持：reference+Wave-A 每个 known confirmed center 和其 ±2 closure 对所有要求的 seeds 达到 100%，且预算/coverage/status 可审计。

## 11. Multipath event database 设计现状

权威设计：`docs/MULTIPATH_EVENT_DATABASE_DESIGN.md`。**仅 schema/流程设计完成；数据库目录、ingest 脚本和正式 Parquet 均未创建。**

建议 canonical 层：

| 表/实体 | 粒度 | 用途 |
|---|---|---|
| `scenes`, `scene_context` | scene/context version | 输入、环境、采集 provenance |
| `sage_runs` | scene–PRN–channel–namespace run | pipeline/hash/参数、Stage count、QA、sampling provenance |
| `nav_symbols` | NAV symbol | Stage0 连续性与 tracking context |
| `window_evidence` | 40 ms window | Stage0 context、Stage1 scan、Stage2 selected 摘要与 coverage 状态 |
| `model_evaluations` | window×L | Stage2 L1–L4 RSS/BIC/valid/selected |
| `stage2_paths` | Stage2 path | 候选参数，明确 `estimate_stage=stage2` |
| `stage3_persistence_paths` | center×candidate path | 持续性证据 |
| `candidate_events` | Stage3 reliable center | 等待/进入 Stage4 的 candidate |
| `events` | Stage4 joint row | confirmed/rejected event 事实 |
| `event_paths` | Stage4 path | LOS 与 confirmed multipath paths |
| `event_context`/`time_alignment`/geometry | event/window | UTC、elevation、azimuth、CN0、speed 与 join QA |
| `labels` | versioned run/event label | algorithm/reference/human/external truth provenance |
| `ingestion_issues` | QA issue | partial/schema drift/join/consistency 错误 |

主键至少包含 `scene_id + prn + tracking_channel + experiment_namespace`，再生成不可变 `run_id`；window/path ID 只在 run 内有效。推荐 Parquet 为 canonical、CSV 为审计导出、JSON 为 schema/manifest。

标签：

- `confirmed_multipath`：Stage4 `joint_valid=1`、`joint_multipath_count>0`，且 path 表 `is_multipath=1` 数量一致。
- `rejected_candidate`：有明确 Stage4 rejection evidence，例如 valid joint L1/MP count0；Stage4 missing/invalid 不能叫 rejected。
- `los_reference`：只能由 reference manifest/人工 control 指定，并且 no confirmed；不能由普通 run 的零事件自动推出。
- sampled coverage 不完整时：`inconclusive_due_to_sampling` 或 `no_confirmed_event_in_sampled_coverage`，不是 LOS。

后续入库必须保存 `sampling_mode/profile_version/seed/plan_hash/selected status/coverage status/unscanned count/full_scan_reference_run_id`，并将 tracking CN0 与 NMEA SNR 分列。scene ID 中 `V70/D0117/P2` 的正式环境语义当前没有项目内可验证字典，不得自行解释。

## 12. 最终参数化信道建模目标

事件数据库形成并通过 coverage QA 后，按 LOW/MID/HIGH elevation bin 建模：

1. `P(multipath occurrence | elevation bin, scene/speed/environment)`：分母必须包含 coverage-complete 的事件/无事件机会窗口；
2. `P(path_count | multipath, conditions)`；
3. excess delay 分布（samples/chips，派生 meters 要保存公式版本）；
4. relative power 分布；
5. signed Doppler offset 与 magnitude 分布；
6. event coherence 与 Stage3 persistence/run length；
7. 参数间联合关系，如 delay–power、delay–Doppler、path count–elevation；
8. scene/PRN/channel/速度/环境的分层或混合效应。

这些模型当前**未开始**，也没有足够 multi-scene confirmed/negative 数据支撑论文统计结论。reference+Wave 数据只能展示方法与案例，不能替代总体分布。

## 13. 当前完成、进行中、未开始状态表

| 层次 | 项目 | 状态 |
|---|---|---|
| 已完成/已验证 | 19 scene 标准化、navigation/trajectory/geometry、inventory 124 tasks | 完成 |
| 已完成/已验证 | Pipeline V3 在 10.23 MHz 多 PRN/channel full-scan | reference 7 + Wave-A 3 + Wave2A G11 有结果 |
| 已完成/已验证 | reference 分类和 8 event/11 path baseline | 封存 |
| 已完成/已验证 | batch planner、allowlist executor、Windows wrapper/hash/lock/smoke/QA 链 | Wave-A/Wave2A 实测通过 |
| 已完成/已验证 | Wave-A G16/G25/G12 | 3 PASS；7 event/7 path |
| 已完成/已验证 | Wave2A G11 full-scan | PASS；0 confirmed；暴露 19.6h 瓶颈 |
| 已实现但未放行 | sampling planner v1 | offline replay FAIL |
| 已实现但未放行 | sampling planner v1.1、TOW diagnostic、budget sweep | offline replay FAIL；no pilot |
| 仅设计 | multipath event database schema/ingest 流程 | 未实现 |
| 暂停 | Wave2A 剩余 4 request、Wave2B、其余 10.23 expansion | 不得盲跑 |
| 未开始 | 独立 sampled SAGE pipeline/output namespace/真实 sampled pilot | 门禁未通过 |
| 未开始 | event database ingestion 与 elevation/CN0/speed/environment join | 无正式数据库 |
| 未开始 | LOW/MID/HIGH 统计信道模型 | 数据不足 |
| 未开始 | 20.46 MHz pipeline 适配、单任务验证、batch | 当前入口硬拒绝 |

## 14. 当前技术风险与研究风险

| 风险 | 类型 | 当前证据与边界 | 应对 |
|---|---|---|---|
| Stage2/3 false candidate 与 Stage4规则依赖 | 算法正确性 | G28、G11 展示高阶/持续性不等于 confirmed；无 external truth | 保留分阶段证据，做外部/人工 validation，不降低 confirmed criterion |
| Stage1/2 wall time | 数据生产效率 | G11 15,210 windows、8.1h+11.4h、总19.6h | sampling/scalable screening；串行；profile I/O/CPU 后再结论 |
| Sampling 漏检 | 科学有效性 | v1 G16/G12 recall 失败；v1.1 1200及4800 sweep无 all-seed pass | no pilot；改变 seed discovery 结构；100% gold gate |
| Geometry 时间对齐 | 数据关联 | legacy join 失败；v1.1 TOW diagnostic 多数改善但未生产集成，G25仍失败 | 版本化 time_alignment，保存 delta/coverage/p95；失败留 null |
| 20.46 未适配 | 工程/算法 | pipeline 明确 assert 10.23；samples/chip、delay grid、计算量未验证 | 单独代码适配、单任务 preflight/pilot/QA，不复用10.23放行 |
| 样本代表性 | 研究统计 | reference 仅一 scene；Wave-A/Wave2A 数量少且按可运行任务选择 | 扩大 scene、覆盖 elevation/速度/环境；报告 selection bias |
| Zero-event 误标 | 研究标签 | G25/G11 是 algorithmic no-confirmed，采样未扫描更不能做 negative | 仅 coverage-complete negative；LOS须 reference/human provenance |
| 版本混杂 | 重现性 | G06 v1 vs v2，future sampled namespace 尚无 | run_id/namespace/hash/provenance，禁止覆盖 |
| MATLAB 启动/退出稳定性 | 执行环境 | sandbox filesystem error、正常用户一次 DDUX exit crash | normal-user wrapper、smoke marker+exit0、receipt、官方 repair/update |

## 15. 不可破坏的安全约束

1. 永不覆盖/移动/删除 `reference/G06_nav_sage_v1`；不向其写辅助文档或数据库标记。
2. reference 已有 G11/G12/G25/G28/G29/G32 和 Wave-A/Wave2A 结果不可覆盖。
3. 每次运行前读取当前 inventory、metadata、真实 input path 和 output existence；不凭文件命名猜测。
4. Multi-channel task 必须人工选 channel 并冻结在 request；不得自动取第一个。
5. 当前 20.46 MHz 不得误跑 `run_nav_sage_pipeline.m`。
6. Existing output 默认 `new_only`；`Resume=true` 不是覆盖授权。失败 checkpoint 保留，不删除，不自动 retry。
7. Codex sandbox 不直接启动 MATLAB；由正常 `TJ-CHANNEL\Jing_` 非管理员 PowerShell 7 手工执行 wrapper。
8. Wrapper smoke 必须 marker+exit0；不得放宽 code 0 门禁。
9. 只运行单任务 immutable request、SHA-256 冻结、全局锁、严格 output namespace；不得用可变 selection 替换已审批请求。
10. 未经独立 post-run QA PASS，不自动放行下一任务或阶段。
11. sampled 结果不得写 `nav_sage_v2`，必须新版本 namespace；当前尚无已批准 namespace/入口。
12. sampled 未扫描窗口不能标 LOS/rejected/no-event；coverage 不完整必须 inconclusive。
13. Stage2 L≥2、Stage3 reliable 都不能替代 Stage4 confirmed criterion。
14. Geometry summary 均值不能伪造 event elevation；失败字段留 null/warning。
15. 不修改 metadata/inventory 来反映 batch 实验状态；实验事实由 result/log/receipt/QA 记录。

## 16. 后续固定路线与门禁

原定路线的第一 sampling gate 已有明确结果：v1.1 离线验证已经完成但 FAIL。因此安全路线应解释为一个需要循环的门控流程：

1. **先封存并复核 v1.1 `tow_aligned` FAIL 基线；设计 v1.2/new adaptive seed-discovery strategy。** 不调用 MATLAB。
2. 用同一 reference+Wave-A gold 和严格 hidden-row 规则做离线 replay；要求所有 known confirmed center 与 ±2 closure 100%。不通过则继续迭代，不得 pilot。
3. 若 PASS，才实现独立 sampled pipeline/入口和版本化 output namespace；不得改写 full-scan Pipeline V3 结果。
4. 对一个短 scene–PRN 做单任务 sampled pilot、完整 21-file-equivalent/sampling provenance QA，并与 full-scan 比较。
5. 对 Wave-2A G11 长场景做 sampled pilot，比较 event recall、Stage2 model distribution、runtime、coverage/inconclusive。
6. 两个 pilot 均 PASS 后恢复 Wave-2A 剩余四项，仍正常用户、串行、逐任务 QA。
7. 扩大 10.23 MHz 数据生产，持续校准 runtime 和 sampling bias。
8. 实现 event database validator/ingest，先以 reference 8 event/11 path 做回归，再接入 Wave-A/Wave2A。
9. 完成 window/event TOW–UTC–geometry join QA，按 LOW/MID/HIGH 和 CN0/speed/scene 统计。
10. 最后单独适配 20.46 MHz：samples/chip、delay/Doppler grid、内存/运行时、单任务 gold 和 Windows request 全部重新验证，不能继承 10.23 的放行。

## 17. 论文可直接使用的研究材料

### 17.1 Introduction / Motivation

**当前可写：** 从 raw IQ 到路径参数和 elevation-conditioned model 的目标；多径检测不能用单窗口高阶拟合直接确认；长 recording 的 exhaustive Stage1/2 计算瓶颈。  
**来源：** 本文、`STAGE1_STAGE2_BATCH_SAMPLING_DESIGN.md`、G11 QA。  
**尚不能写成结论：** 各 elevation bin 的多径发生率和分布；不同环境的显著性。

### 17.2 System and Data Acquisition

**当前可写：** 19 scene、13×10.23 MHz/6×20.46 MHz、124 scene–PRN；scene 目录和 raw external/local 规则；reference raw 和最大 raw 规模。  
**来源：** `dataset/dataset_inventory.csv`、各 `metadata.json`、raw file stat。  
**尚缺：** scene ID 中速度/日期/位置编码的正式采集字典、天线/接收机/环境标注；不得从 ID 自行解释。

### 17.3 GNSS-SDR Preprocessing

**当前可写：** tracking/telemetry/RINEX/NMEA 标准化链；navigation/trajectory 复制和 SHA；NMEA GSV geometry、RINEX NAV PRN-filter-only。  
**来源：** `scripts/preprocessing/*.py`、三份 20260806 日志、metadata。  
**限制：** 当前 geometry 不是 broadcast ephemeris position recomputation；event-level join 尚未生产化。

### 17.4 SAGE Multipath Estimation Method

**当前可写：** NAV symbol wipe、40 ms fast scan、fractional SAGE L1–L4、persistence、joint 100 ms；参数表可以直接从 `defaultConfiguration` 提取。  
**来源：** `scripts/sage_pipeline/run_nav_sage_pipeline.m`。  
**需谨慎：** 只在 10.23 MHz 验证；G06 是 legacy v1。

### 17.5 Stage0–Stage4 Decision Logic

**当前可写：** Stage2 L≥2 screening、Stage3 persistence candidate、Stage4 criterion；G28/G25/G11 为空/拒绝例。  
**来源：** pipeline code、reference final report、Wave QA。  
**尚缺：** 与外部真值的 detection probability/false-alarm rate。

### 17.6 Reference Validation

**当前可写：** 七 PRN matrix、三类算法行为、8 confirmed events/11 paths、delay/Doppler/power/coherence 示例。  
**来源：** `reference_scene_final_validation_report.md` 与各 PRN Stage CSV。  
**限制：** 一个 scene，不代表总体传播环境；G06 版本不同。

### 17.7 Batch Execution and Reproducibility

**当前可写：** plan/allowlist/new_only/hash/lock/smoke/receipt/21-file QA；sandbox失败和正常用户 boundary。  
**来源：** Windows design/implementation、diagnostic docs、execution requests/receipts、Wave QA。  
**论文定位：** 工程可复现性与安全执行，不应包装成 SAGE 科学性能提升。

### 17.8 Runtime Scalability Observation

**当前可写：** reference G11 1175 windows 对 Wave2A G11 15210；后者 Stage1约8.1h、Stage2约11.4h、总19.6h；窗口12.94×、Stage1时间约17.7×。  
**来源：** `WAVE2A_G11_QA_REPORT.md`、execution/task logs、progress artifact timestamps。  
**尚不能写：** 精确复杂度阶数或 I/O/CPU root cause；需要 profiler 和更多 scene。

### 17.9 Sampling Acceleration Design

**当前可写：** full-scan vs sampled、1200 budget、24 strata、CN0/elevation/time、closure/inconclusive semantics；v1/v1.1 strict replay 的负结果。负结果本身可作为方法约束和消融材料。  
**来源：** sampling design、v1/v1.1 reports、coverage CSV/budget sweep。  
**必须明确：** 没有运行真实 sampled SAGE；v1/v1.1 FAIL；不能声称加速比或 event preservation。

### 17.10 Limitations

可直接列出：单 reference scene；Wave-A/Wave2A 样本少；无 external truth；20.46 未适配；sampling gate失败；event database/统计模型未实现；geometry event join 未生产化；environment metadata 不完整；selection/coverage bias 尚未量化。

## 18. 建议论文图表清单及原始数据

| 图/表 | 可否现在制作 | 原始来源 |
|---|---|---|
| End-to-end 数据流程图 | 可以 | 本文 §3、`scripts/preprocessing/`、Pipeline V3 |
| Stage0–Stage4 算法/决策流程图 | 可以 | `run_nav_sage_pipeline.m`、本文 §4 |
| 19 scene/采样率/PRN 数据集表 | 可以 | `dataset/dataset_inventory.csv` |
| Reference 七 PRN Stage 漏斗图 | 可以 | `reference_scene_final_validation_report.md`；各 `stage0/1/2/3/4` CSV |
| Reference PRN 对比表/三类标签表 | 可以 | 同上；`reference_prn_analysis_report.md` 仅作五 PRN历史交叉核对 |
| Reference confirmed delay–Doppler–power 示例图 | 可以 | `G06_nav_sage_v1/stage4_joint_*`、`nav_sage_v2/Gxx/stage4_joint_*`、各 `<PRN>_nav_sage_overview.png` |
| Wave-A 三任务验证表 | 可以 | `docs/WAVEA_10MHz_VALIDATION_REPORT.md`、三份 QA、对应 Stage CSV |
| G11 runtime scalability 图 | 可以（注明时间戳估计） | `docs/WAVE2A_G11_QA_REPORT.md`、`batch_sage_execution_20260809T094948Z/`、Stage progress/files |
| Sampling v1 center/closure recall 图 | 可以，作为失败结果 | `sampling_validation/batch_sampled_v1_offline_coverage/coverage_replay*.csv` |
| v1.1 block length × initial/adaptive recall 图 | 可以，作为失败结果 | `.../batch_sampled_v1_1_offline_coverage/tow_aligned/coverage_replay_v1_1.csv`、`coverage_replay_events_v1_1.csv` |
| v1.1 budget sweep/all-seed pass 图 | 可以 | `.../tow_aligned/budget_sweep_v1_1.csv` |
| Geometry legacy vs TOW join 图 | 可以，标为 planner diagnostic | v1/v1.1 reports 与各 `sampling_plan.json` |
| LOW/MID/HIGH occurrence/path distribution | **不可以下结论** | 等 event database、verified join 和多 scene coverage 后生成 |
| 20.46 vs 10.23 性能/参数图 | **无数据支撑** | 必须先适配和验证 20.46 |

## 19. Current Status 与新 AI 的第一条操作建议

当前项目不再处于“验证 reference PRN”或“实现 batch executor”的阶段；这两项已经完成。也不应把 Wave-2A G11 的 PASS 解释为应该继续所有 full-scan：G11 已经证明当前 full-scan 对长 recording 的吞吐不可接受，而 v1/v1.1 又证明当前 sampled family 会漏掉 known event/closure。

**新 AI 接手后的第一条建议：不要调用 MATLAB，不要继续盲目 full-scan Wave-2A，不要生成 sampled execution request。先阅读并封存确认 `docs/BATCH_SAMPLED_V1_1_OFFLINE_COVERAGE_REPORT.md` 与 `.../tow_aligned/` 已完成且 FAIL；随后设计能发现初始样本之外新 seed 的 v1.2/adaptive screening，并在同一 gold set 上完成严格离线覆盖验证。只有 known confirmed event center 与 ±2 closure 达到 100% 后，才进入独立 sampled namespace 的实际 pilot。**
> **状态迁移（2026-08-12）：** 本文件已转为历史参考。当前工程状态唯一来源是 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源是 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。
