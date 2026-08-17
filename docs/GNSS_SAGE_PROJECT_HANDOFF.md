# GNSS SAGE 项目完整交接文档

> **历史文档：** 当前工程状态唯一来源为 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源为 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。本文件仅作历史参考。

> 状态快照日期：2026-08-06（Asia/Shanghai）  
> 项目根目录：`E:\GNSS_Multipath_Project`  
> 面向对象：没有历史对话上下文、需要接手后续开发和运行工作的 AI Agent  
> 本文档依据当前文件系统、`dataset_inventory.csv`、已有 Stage0–Stage4 结果和验证汇总生成。除新增本文档外，没有修改代码、scene 数据或既有结果。

## 0. 接手时先读这一节

当前项目已经越过“整理输入目录”的阶段，处于 **SAGE pipeline 单场景多 PRN 验证阶段**。

接手者必须遵守以下边界：

1. `scenes/F1023_V70_D0117_P2` 是 reference scene，不按普通 scene 清理或迁移。
2. `scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1` 是不可覆盖的历史基准实验。
3. 不移动或改写 raw IQ、`gnss_sdr`、`navigation`、`trajectory`、`satellite` 和已有 `sage_results`。
4. 运行 SAGE 前必须从 `dataset/dataset_inventory.csv`确认 PRN 与 tracking channel 的唯一映射；多个候选时停止，不能自动选择。
5. 当前通用 MATLAB pipeline **仅支持 10.23 MHz**。6 个 20.46 MHz scene 已完成数据准备，但不能直接交给当前 pipeline。
6. `dataset_inventory.csv` 生成于本轮 G25/G28/G11 运行之前。它是当前输入完整性和 channel 映射的依据，但其中 `sage_results_*` 列已滞后；reference scene 的最新 SAGE 状态应以实际目录和 `prn_validation_summary.csv` 为准。
7. `docs/PROJECT_DATA_STRUCTURE.md` 是较早的数据整理阶段快照，其中关于 navigation、trajectory、satellite 尚未准备的描述已经过时。当前状态以本文档和实际文件为准。

## 1. 项目目标

项目的最终目标是建立 GNSS 多径统计建模平台：利用已有 GNSS-SDR 解析结果、导航/轨迹信息和原始复数 IQ 数据，通过 **NAV-wiped fractional SAGE** 对 GPS L1 C/A 信号的直达径和多径分量进行估计，并把结果组织为可跨场景分析的数据集。

目标产物不是单次多径检测，而是可按以下维度查询和统计的模型：

- scene / 场景条件；
- 卫星 PRN；
- 卫星仰角、方位角和 SNR/CN0 条件；
- 路径超额时延、相对 Doppler、相对功率、持续时间；
- 车辆速度和环境/位置条件；
- LOS、候选多径、持续多径和联合确认多径等置信层级。

目标数据流为：

```text
raw complex IQ
        +
GNSS-SDR tracking / telemetry / observables / PVT / NMEA / RINEX
        ↓
scene-level navigation + trajectory standardization
        ↓
satellite geometry (elevation / azimuth / SNR, derived data)
        ↓
NAV-wiped fractional SAGE Stage0–Stage4
        ↓
confirmed multipath event extraction
        ↓
scene × PRN × elevation/CN0/environment statistical dataset
        ↓
multipath statistical model
```

## 2. 项目目录和数据组织

### 2.1 项目根目录

```text
E:\GNSS_Multipath_Project\
├── scenes/                       # 19 个标准化 scene、迁移报告和所有场景级数据
├── scripts/
│   ├── preprocessing/            # navigation/trajectory/satellite/inventory 工具
│   └── sage_pipeline/            # MATLAB SAGE pipeline 与验证汇总工具
├── dataset/                      # 跨 scene 数据清单；当前含 dataset_inventory.csv
├── dataset_generation_logs/      # 数据准备批处理日志
├── docs/                         # 项目结构和交接文档
├── configs/                      # 预留的项目级配置目录，当前无配置文件
└── full_parse_v1/                # 迁移前 GNSS-SDR 解析结果源；保留、不要修改
```

补充文件：

- `scenes/migration_report.csv`：从 `full_parse_v1` 复制 GNSS-SDR结果时的迁移统计。
- `dataset/dataset_inventory.csv`：19 个 scene 的 SAGE 输入 inventory，共 124 个可用 scene–PRN 组合。
- `dataset_generation_logs/navigation_prepare_*.log`：navigation 标准化日志。
- `dataset_generation_logs/trajectory_prepare_*.log`：trajectory 标准化日志。
- `dataset_generation_logs/batch_satellite_geometry_*.log`：satellite geometry 批处理日志。

### 2.2 19 个 scene

10.23 MHz（13 个）：

```text
F1023_V120_D0121_P2
F1023_v50_D0127_P1
F1023_V70_D0117_P2       # reference scene
F1023_V70_D0117_P4
F1023_V70_D0120_P1
F1023_V70_D0120_P5
F1023_V70_D0120_P7
F1023_V70_D0120_P8
F1023_V70_D0120_P9
F1023_V70_D0122_P1
F1023_V70_D0122_P2
F1023_V80_D0117_P8
F1023_v90_D0117_P7
```

20.46 MHz（6 个）：

```text
F2046_V30_D0131_P2
F2046_V30_D0131_P4
F2046_V30_D0203_P2
F2046_V60_D0129_P1
F2046_V60_D0129_P3
F2046_V60_D0202_P1
```

除 reference scene 的保留实验文件外，18 个普通 scene 的一级结构一致：

```text
scenes/<scene_id>/
├── metadata.json
├── raw/
├── gnss_sdr/
├── navigation/
├── trajectory/
├── satellite/
└── sage_results/
```

完整标准结构为：

```text
scenes/<scene_id>/
├── metadata.json
├── raw/
│   └── data_address.txt                 # 普通 scene：外部 raw IQ 地址
├── gnss_sdr/
│   ├── config/                          # 本 scene 的 GNSS-SDR .conf
│   ├── logs/                            # GNSS-SDR运行日志
│   ├── tracking/                        # *_track_ch_<n>.dat/.mat
│   ├── telemetry/                       # *_telemetry_ch_<n>.dat/.mat、CRC统计
│   ├── observables/                     # observables .dat/.mat
│   ├── pvt/                             # PVT .dat/.mat
│   ├── rinex/                           # GNSS-SDR原始 RINEXFILE.26N/.26O
│   └── nmea/                            # GNSS-SDR NMEA轨迹输出
├── navigation/
│   ├── rinex_nav/RINEXFILE.26N          # 标准化 NAV 副本
│   └── rinex_obs/RINEXFILE.26O          # 标准化 OBS 副本
├── trajectory/
│   └── <scene_id>_trajectory.nmea       # 标准化 NMEA 副本
├── satellite/
│   ├── <scene_id>_satellite_elevation_timeseries.csv
│   └── <scene_id>_satellite_elevation_summary.csv
└── sage_results/                        # SAGE 输出；普通 scene 当前为空
```

`satellite/` 是目录名，metadata 中对应状态字段是 `satellite_geometry`。这里的数据是派生数据，不是 geometry 原始输入。

### 2.3 Reference scene 的有意差异

`F1023_V70_D0117_P2` 除标准目录外还保留：

```text
legacy_results/
generate_satellite_elevation.py
g06_nav_sage_pipeline.m
analyze_G06_events.m
plot_G06_window203_correlation.m
plot_G06_window203_overlay.m
plot_G06_window203_stage2_internal_ddm.m
GNSS_SAGE_NAV_HANDOFF.md
```

这些是实验历史、诊断脚本和旧交接记录，不要自动清理。reference scene 的本地 raw IQ 也有意保留：

```text
scenes/F1023_V70_D0117_P2/raw/F1023_V70_D0117_P2.bin
```

## 3. 数据来源与准备流程

### 3.1 Raw IQ

- reference scene：`storage_mode=scene_local`，真实 IQ 位于 scene 的 `raw/` 中。
- 其余 18 个 scene：`storage_mode=external_storage`，真实 IQ 位于：

  ```text
  E:\AAGNSSSDR_input\raw_data\<scene_id>.bin
  ```

- 普通 scene 的 `raw/data_address.txt` 和 `metadata.json.raw_iq.path` 记录外部路径，未复制 IQ。
- 当前核验结果：19 个 metadata 所记录的 raw 路径都真实存在。
- SAGE 会读取 raw IQ；Python 数据准备工具不会读取 raw IQ。

### 3.2 GNSS-SDR 输出

19 个 scene 的 `gnss_sdr` 均已存在且 inventory 中状态为 `SUCCESS`。关键来源文件是：

```text
gnss_sdr/tracking/<scene_id>_track_ch_<channel>.mat
gnss_sdr/telemetry/<scene_id>_telemetry_ch_<channel>.dat
gnss_sdr/observables/<scene_id>_observables.dat/.mat
gnss_sdr/pvt/<scene_id>_pvt.dat/.mat
gnss_sdr/rinex/RINEXFILE.26N
gnss_sdr/rinex/RINEXFILE.26O
gnss_sdr/nmea/<scene_id>_trajectory.nmea
```

tracking channel 与 PRN 不是文件名可直接推断的固定关系。必须使用 inventory 中的 `prn_tracking_channel_map`，并要求目标 PRN 只有一个候选 channel。

### 3.3 Navigation 标准化

工具将 GNSS-SDR RINEX **复制**到 scene 标准入口，不移动、不删除源文件：

```text
gnss_sdr/rinex/RINEXFILE.26N → navigation/rinex_nav/RINEXFILE.26N
gnss_sdr/rinex/RINEXFILE.26O → navigation/rinex_obs/RINEXFILE.26O
```

19 个 scene 当前均已完成，metadata 中 navigation 状态为 completed。reference scene 已有目标文件时只比较一致性，不覆盖。

### 3.4 Trajectory 标准化

```text
gnss_sdr/nmea/<scene_id>_trajectory.nmea
    → trajectory/<scene_id>_trajectory.nmea
```

19 个 scene 当前均已完成。源 NMEA 保留不变。当前 SAGE pipeline 从 `trajectory/` 读取 NMEA 速度信息。

### 3.5 Satellite geometry

生成逻辑：

```text
gnss_sdr/nmea/*.nmea
        +
navigation/rinex_nav/*.26N
        ↓
scripts/preprocessing/satellite_geometry.py
        ↓
satellite/<scene_id>_satellite_elevation_timeseries.csv
satellite/<scene_id>_satellite_elevation_summary.csv
```

算法语义必须保持清楚：

- elevation、azimuth、SNR 来自 NMEA GSV；
- RINEX NAV 只用于筛选存在导航记录的 GPS PRN；
- 不使用广播星历重新计算卫星位置；
- 不读取 raw IQ。

19 个 scene 均已生成这两个 CSV，metadata 中 `processing_status.satellite_geometry=completed`，inventory 中也均为 completed。

### 3.6 SAGE 输出

SAGE 消费的核心数据是：

- raw complex IQ；
- 指定 channel 的 tracking MAT；
- 指定 channel 的 telemetry DAT（提供已解调 GPS NAV symbols）；
- 标准化 trajectory NMEA（车辆速度约束）。

通用入口还会检查标准 `navigation/`、`satellite/` 目录并把 RINEX NAV、satellite CSV 路径写入运行上下文，但当前 Stage0–Stage4 数学流程 **不直接用 RINEX 广播星历或 satellite CSV 重算相关结果**。不要误称当前 SAGE 为基于星历重算卫星位置的算法。

## 4. 当前数据集状态

截至本文档生成时：

| 项目 | 状态 |
|---|---|
| scene 数量 | 19 |
| GNSS-SDR 解析成功 | 19/19 |
| navigation 标准化 | 19/19 |
| trajectory 标准化 | 19/19 |
| satellite geometry | 19/19 |
| raw 路径实际存在 | 19/19 |
| dataset inventory | 已生成 |
| 可用 scene–PRN 组合 | 124 |
| 10.23 MHz scene | 13 |
| 20.46 MHz scene | 6 |
| 多 scene SAGE | 尚未开始 |

数据准备完成并不等于 SAGE 完成。除 reference scene 外，普通 scene 的 `sage_results/` 当前没有正式批量 SAGE 结果。

`dataset/dataset_inventory.csv` 包含：scene、signal、sampling rate、raw 路径、GNSS-SDR状态、tracking/telemetry 文件、channel–PRN 映射、navigation、trajectory、satellite geometry、可用 PRN 和 SAGE结果扫描字段。使用它前应注意：输入相关字段仍是当前批处理的依据，但 SAGE 状态列早于后续 G25/G28/G11 运行。

## 5. 当前通用 SAGE pipeline

入口：

```text
scripts/sage_pipeline/run_nav_sage_pipeline.m
```

调用形式：

```matlab
addpath("E:\GNSS_Multipath_Project\scripts\sage_pipeline");

result = run_nav_sage_pipeline( ...
    "<scene_id>", ...
    "G<PRN>", ...
    "TrackingChannel", <channel>, ...
    "ProjectRoot", "E:\GNSS_Multipath_Project");
```

PRN 也可传数字。`TrackingChannel` 必须显式提供；pipeline 不自动选择多个 channel。`Resume` 默认 `true`，只允许 scene、PRN、channel、采样率和输入路径一致的 checkpoint 被复用。

输出目录固定为：

```text
scenes/<scene_id>/sage_results/nav_sage_v2/<PRN>/
```

每次运行保存：

```text
run_context.json
run_context.mat
doppler_sign.mat
stage0_nav_catalog.mat
stage0_valid_symbols.csv
stage0_valid_40ms_windows.csv
stage1_nav_fast_scan.mat/.csv
stage1_nav_progress.mat
stage2_nav_sage_L1_L4.mat
stage2_model_orders.csv
stage2_selected_windows.csv
stage2_selected_paths.csv
stage2_nav_progress.mat
stage3_nav_persistence.mat
stage3_persistence.csv
stage3_reliable_centers.csv
stage4_nav_joint_100ms.mat
stage4_joint_summary.csv
stage4_joint_paths.csv
<PRN>_nav_sage_overview.png
```

### 5.1 Stage0–Stage4

1. **Stage0 — NAV symbol catalog**  
   对指定 PRN/channel 的 telemetry NAV symbols 与 tracking 时间/多普勒状态进行匹配，筛选连续、完整且质量合格的 symbol，构建连续 40 ms（两个 20 ms NAV symbol）窗口。NMEA 速度用于相对 Doppler 约束。

2. **Doppler sign calibration**  
   从 raw IQ 与候选窗口判断应使用的 GNSS-SDR Doppler 符号，结果保存到 `doppler_sign.mat`。

3. **Stage1 — NAV-wiped fast scan**  
   用已知 NAV symbol 消除 20 ms data-bit 翻转，在所有有效 40 ms 窗口做快速主径/残差峰扫描。按残差峰分数选择基础候选，并加入相邻窗口。Stage1 是高召回候选生成，不是最终多径确认。

4. **Stage2 — fractional SAGE L=1–4**  
   对 Stage1 候选执行 fractional-delay SAGE。延迟栅格为 0.1 sample；在10.23 MHz下等于0.01 chip。分别拟合总路径数 L=1、2、3、4，结合 BIC、RSS改善、路径功率、最小间隔、相对 Doppler 和相干性约束选择模型。多径条数是 `L-1`。

5. **Stage3 — persistence**  
   在中心窗口附近的连续 40 ms 窗口中匹配 Stage2 路径，要求时延、Doppler和功率具有一致性，并满足最少连续窗口数。Stage3 将单窗口候选提升为“持续事件”。

6. **Stage4 — joint 100 ms**  
   对 Stage3 可靠中心执行5个 snapshot、总计100 ms的common-geometry联合估计。只有 joint 结果有效且 `joint_multipath_count > 0`，才在当前验证口径中记为 confirmed multipath。

### 5.2 当前采样率限制

- 10.23 MHz：当前已验证，`samplesPerChip=10`，可运行。
- 20.46 MHz：当前入口会在读取metadata后主动拒绝；尚未完成数学参数、搜索网格、raw格式和性能回归验证。
- 不要通过删除采样率检查强行运行 20.46 MHz。应单独设计第二阶段采样率泛化并做 reference/regression 验证。

## 6. Reference experiment 与不可覆盖资产

Reference scene：

```text
scenes/F1023_V70_D0117_P2
```

历史 G06 基准：

```text
scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1
```

它由原始 G06 专用pipeline生成，包含 Stage0–Stage4 CSV/MAT、overview 和 diagnostics。以下两份历史脚本保持实验记录：

```text
scripts/sage_pipeline/g06_nav_sage_pipeline.m
scenes/F1023_V70_D0117_P2/g06_nav_sage_pipeline.m
```

二者不应被通用化过程覆盖。通用入口不读取 `G06_nav_sage_v1`，其输出使用 `nav_sage_v2/<PRN>` 隔离。

Reference scene 当前 inventory 中可用 PRN/channel 是：

| PRN | Tracking channel | 当前验证状态 |
|---|---:|---|
| G06 | 4 | 已完成历史 `G06_nav_sage_v1` |
| G11 | 5 | 已完成 `nav_sage_v2/G11` |
| G12 | 6 | 待验证 |
| G25 | 0 | 已完成 `nav_sage_v2/G25` |
| G28 | 1 | 已完成 `nav_sage_v2/G28` |
| G29 | 7 | 待验证 |
| G32 | 11 | 待验证 |

## 7. 单场景多 PRN 验证结果

机器可读汇总：

```text
scenes/F1023_V70_D0117_P2/sage_results/prn_validation_summary.csv
```

人工阅读报告：

```text
scenes/F1023_V70_D0117_P2/sage_results/prn_validation_report.md
```

### 7.1 数值总表

| PRN | Ch | NAV symbols | 40 ms窗口 | Stage1扫描 | Stage1候选 | L1 | L2 | L3 | L4 | L>=2 | L>=3 | Stage3可靠 | Stage4 joint | confirmed MP事件 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| G06 | 4 | 321 | 319 | 319 | 95 | 8 | 29 | 17 | 41 | 87 | 58 | 2 | 2 | 2 |
| G11 | 5 | 1177 | 1175 | 1175 | 101 | 45 | 4 | 22 | 30 | 56 | 52 | 7 | 7 | 1 |
| G25 | 0 | 1177 | 1175 | 1175 | 52 | 40 | 2 | 0 | 10 | 12 | 10 | 0 | 0 | 0 |
| G28 | 1 | 900 | 898 | 898 | 54 | 42 | 4 | 5 | 3 | 12 | 8 | 2 | 2 | 0 |

### 7.2 各 PRN 解释

#### G25 — 当前 LOS/低多径参考

- Stage0具有1177个有效symbol和1175个完整窗口，数据覆盖充分。
- Stage1选出52个候选；Stage2中40个选择L=1，12个选择L>=2。
- Stage3没有任何候选满足相邻窗口持续性，因此Stage4没有输入。
- 解释：存在单窗口高阶拟合，但没有形成时间连续、可复现的多径事件。当前可把G25作为reference scene内的 LOS/低多径对照，不应说“绝对无多径”，而应说“按当前Stage3/Stage4标准未确认多径”。

#### G28 — 有持续候选，但joint回落到单径

- 900个有效symbol、898个窗口，Stage1选54个候选。
- Stage2有12个L>=2，其中8个L>=3。
- Stage3产生2个可靠中心；Stage4也产生2个有效joint结果。
- 两个joint结果最终都选择L=1，`joint_multipath_count=0`。
- 解释：40 ms局部窗口中存在可持续候选结构，但扩大到100 ms联合估计后，高阶路径证据不足。它是“候选但未确认多径”的典型案例。

#### G06 — 历史基准，两个确认事件

- 数据段较短：321个有效symbol、319个窗口。
- Stage1选95个候选；Stage2有87个L>=2、58个L>=3，高阶模型占比高。
- Stage3保留窗口203和264两个可靠中心。
- Stage4分别选择joint L=4和L=2，确认两个多径事件。
- 解释：G06是当前最强的历史多径基准，但属于v1专用实验。其高阶比例和相对功率定义应按该pipeline输出口径解释，不要直接当作绝对物理功率。

#### G11 — 通用pipeline验证中最强的多径候选PRN

- 1177个有效symbol、1175个窗口，Stage1选101个候选。
- Stage2选择56个L>=2、52个L>=3，明显高于G25/G28。
- Stage3产生7个可靠中心。
- Stage4产生7个有效joint结果；其中6个回落到L=1，只有窗口640保留L=2并确认一条多径。
- 解释：Stage2高阶模型很多，但100 ms joint确认率只有1/7。这同时说明G11确有可确认事件，也说明Stage4对单窗口/短持续假象起到强筛选作用。

## 8. 当前 confirmed multipath 事件

当前确认口径：`stage4_joint_summary.csv` 中 `joint_valid=1` 且 `joint_multipath_count>0`。

### 8.1 事件级清单

| PRN | Ch | 中心窗口 | 时间(s) | Stage2 L | Joint L | 确认MP路径数 | 最小MP功率(dB) | 最大相对Doppler(Hz) | 最大coherence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| G06 | 4 | 203 | 41.8614 | 2 | 4 | 3 | 6.90252 | 199.664 | 0.332664 |
| G06 | 4 | 264 | 43.0814 | 2 | 2 | 1 | 22.0595 | 159.664 | 0.0345984 |
| G11 | 5 | 640 | 50.5988 | 3 | 2 | 1 | -7.40707 | 10.0131 | 0.828954 |

这些是算法确认事件，不等于已经通过外部真值验证。功率正负和量纲应沿用输出CSV定义，不要脱离pipeline归一化约定做绝对功率解释。

### 8.2 路径级清单

| PRN | 窗口 | Path | 超额时延(samples) | 超额时延(chips) | Doppler offset(Hz) | 相对功率(dB) |
|---|---:|---:|---:|---:|---:|---:|
| G06 | 203 | 2 | 1.6 | 0.16 | 149.664 | 18.1926 |
| G06 | 203 | 3 | 2.6 | 0.26 | 199.664 | 6.90252 |
| G06 | 203 | 4 | 8.3 | 0.83 | 149.664 | 7.10460 |
| G06 | 264 | 2 | 3.9 | 0.39 | 159.664 | 22.0595 |
| G11 | 640 | 2 | 1.1 | 0.11 | -10.0131 | -7.40707 |

结果文件位置：

```text
# G06 windows 203 and 264
scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/
├── stage3_reliable_centers.csv
├── stage4_joint_summary.csv
└── stage4_joint_paths.csv

# G11 window 640
scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G11/
├── stage3_reliable_centers.csv
├── stage4_joint_summary.csv
└── stage4_joint_paths.csv
```

G06还保留窗口203/264专项诊断和绘图结果；不要把这些历史诊断文件移动到通用v2目录。

## 9. 当前分析结论

### 9.1 三层证据不能混用

- **Stage2 candidate/model selection**：说明单个40 ms窗口中高阶模型比L=1更符合当前准则；高召回，但可能受噪声、局部相关峰或模型自由度影响。
- **Stage3 persistence**：要求相邻窗口中的路径参数保持一致，排除大量瞬时高阶拟合。
- **Stage4 joint confirmation**：用100 ms共同几何结构重新拟合；若最终仍选择L>=2，才是当前项目的confirmed multipath。

因此：

- 不能用“Stage2选择L>=2”直接计为确认多径。
- Stage3可靠事件仍可能在Stage4回落到L=1，G28和G11的6个事件已经证明这一点。
- 当前reference scene中，G25是低多径/LOS对照，G28是持续候选但未joint确认，G06和G11有joint确认事件。

### 9.2 当前样本量仍不足以建立最终统计模型

目前只有一个scene完成4个PRN的验证，confirmed事件共3个、confirmed MP路径共5条。该数量适合验证pipeline和事件定义，不足以对场景、仰角或环境因素形成稳定统计结论。后续必须扩大到剩余PRN和多scene。

## 10. 下一步工作规划

建议按以下顺序推进，避免直接跳到全量运行：

### Phase A：完成reference scene剩余PRN

剩余唯一映射：

```text
G12 → TrackingChannel 6
G29 → TrackingChannel 7
G32 → TrackingChannel 11
```

每次运行前检查目标目录不存在，并使用相同10.23 MHz参数。完成后扩展或重跑 `summarize_prn_validation.py` 的PRN列表，更新reference汇总。注意：该工具当前显式列出G06/G11/G25/G28；加入新PRN需要有意识地修改工具配置，而不是静默漏报。

### Phase B：设计 batch SAGE runner

不要直接循环全部124个组合。先设计只读规划/清单模式，至少包含：

- scene_id、PRN、唯一channel；
- sampling rate；
- raw/tracking/telemetry/trajectory存在性；
- 目标目录是否存在；
- pipeline支持状态；
- skip/resume/error策略；
- 每任务耗时和失败隔离。

第一批只选择10.23 MHz scene。当前单PRN完整运行约35–73分钟，批量工具需要checkpoint、日志、并发/资源上限和可恢复性设计。

### Phase C：统一事件提取

为每个scene–PRN提取：

- Stage0数据覆盖；
- Stage1候选比例；
- Stage2模型阶数和路径参数；
- Stage3持续性；
- Stage4确认状态；
- confirmed事件及路径表；
- 运行上下文和算法版本。

应生成长期稳定的事件主键，例如：

```text
scene_id + PRN + center_window_id + path_id + pipeline_version
```

### Phase D：关联 satellite / CN0 / 环境因素

以事件记录时间匹配：

- satellite timeseries中的elevation、azimuth、SNR；
- Stage0/Stage1中的CN0；
- trajectory速度；
- scene_id编码或未来场景标签中的环境、道路和位置条件。

必须区分卫星NMEA SNR与tracking CN0，不能把两个字段无说明地混为同一测量量。

### Phase E：建立多径统计模型

按scene、PRN、仰角区间、CN0、速度和环境条件统计：

- confirmed事件发生率；
- 多径条数分布；
- 超额时延/路径长度分布；
- 相对Doppler和相对功率分布；
- 持续时间和联合确认率；
- Stage2候选到Stage4确认的转化率。

在建模前先处理scene间观测时长不同、可见PRN不同和仰角覆盖不均衡问题。

### Phase F：20.46 MHz泛化

单独完成并验证：

- raw IQ读取格式；
- samples/chip、samples/ms和延迟网格；
- fast scan/SAGE搜索范围；
- checkpoint配置兼容性；
- 与10.23 MHz结果的物理单位一致性；
- 性能和内存压力。

## 11. 运行与安全注意事项

### 11.1 SAGE运行前检查

1. 从inventory读取目标scene，确认 `sampling_rate_hz=10230000`。
2. 确认目标PRN在 `available_prns` 中。
3. 解析 `prn_tracking_channel_map`，只接受一个channel候选。
4. 检查以下文件真实存在：

   ```text
   metadata.json
   metadata.raw_iq.path
   gnss_sdr/tracking/<scene_id>_track_ch_<channel>.mat
   gnss_sdr/telemetry/<scene_id>_telemetry_ch_<channel>.dat
   trajectory/*.nmea
   navigation/rinex_nav/*.26N
   ```

5. 检查输出 `sage_results/nav_sage_v2/<PRN>` 是否已存在。
6. 若已存在，先读取 `run_context.json/.mat` 和checkpoint；不要盲目重跑或覆盖。
7. 对reference scene确认 `G06_nav_sage_v1`、G25、G28、G11文件数量和时间未被目标操作涉及。

### 11.2 禁止事项

- 不覆盖、移动或删除 `G06_nav_sage_v1`。
- 不改写 raw IQ 或把18个外部IQ复制进scene。
- 不修改 `gnss_sdr`原始解析结果。
- 不以自动猜测替代明确channel映射。
- 不在当前pipeline上强制运行20.46 MHz。
- 不把Stage2高阶模型直接标为confirmed multipath。
- 不把satellite geometry称为原始输入或广播星历重算结果。
- 不依赖旧文档中的过时数据状态；始终核对实际目录。

### 11.3 Pipeline已知假设/风险

- raw IQ格式、telemetry DAT记录结构和tracking MAT变量结构沿用原G06实验假设。
- trajectory目录要求恰好一个NMEA文件。
- Stage1/Stage2计算开销大；单PRN运行可能超过1小时。
- 默认resume会复用身份匹配的checkpoint；它是恢复机制，不是“覆盖安全”的替代品。
- Stage4确认仍是算法判定，尚无外部场景真值标注。

## 12. 关键脚本与用途

### 12.1 Preprocessing

| 脚本 | 用途 | 写入范围 |
|---|---|---|
| `scripts/preprocessing/batch_prepare_navigation.py` | 将`.26N/.26O`从`gnss_sdr/rinex`复制到`navigation/rinex_nav`和`rinex_obs`；比较reference文件一致性 | navigation、metadata、navigation日志 |
| `scripts/preprocessing/batch_prepare_trajectory.py` | 将GNSS-SDR NMEA复制到`trajectory/`；reference只比较不覆盖 | trajectory、metadata、trajectory日志 |
| `scripts/preprocessing/satellite_geometry.py` | 公共GSV解析与PRN筛选算法；输出仰角、方位角、SNR时序/摘要 | 调用方指定的satellite输出 |
| `scripts/preprocessing/batch_generate_satellite_geometry.py` | 扫描全部scene并调用公共算法；已有reference结果默认skip | satellite、metadata、batch日志 |
| `scripts/preprocessing/generate_dataset_inventory.py` | 只读扫描metadata、GNSS-SDR日志和文件结构，生成SAGE输入inventory | `dataset/dataset_inventory.csv` |

### 12.2 SAGE

| 脚本 | 用途 | 状态 |
|---|---|---|
| `scripts/sage_pipeline/g06_nav_sage_pipeline.m` | 历史G06专用实现 | 保留，不修改 |
| `scripts/sage_pipeline/run_nav_sage_pipeline.m` | scene + PRN + explicit TrackingChannel通用入口，Stage0–Stage4，当前仅10.23 MHz | 当前主入口 |
| `scripts/sage_pipeline/summarize_prn_validation.py` | 只读汇总reference已有CSV，生成PRN验证总表与confirmed事件清单 | 当前显式覆盖G06/G11/G25/G28 |

### 12.3 关键文档和结果

| 文件 | 用途/时效性 |
|---|---|
| `docs/GNSS_SAGE_PROJECT_HANDOFF.md` | 当前完整交接，优先阅读 |
| `docs/PROJECT_DATA_STRUCTURE.md` | 较早结构盘点；数据准备状态已过时 |
| `dataset/dataset_inventory.csv` | 当前输入/channel inventory；SAGE状态列早于v2多PRN运行 |
| `scenes/F1023_V70_D0117_P2/sage_results/prn_validation_summary.csv` | 当前reference多PRN机器可读汇总 |
| `scenes/F1023_V70_D0117_P2/sage_results/prn_validation_report.md` | 当前confirmed事件和路径报告 |
| `scenes/F1023_V70_D0117_P2/GNSS_SAGE_NAV_HANDOFF.md` | reference历史实验交接，作为背景而非全项目当前状态 |

## 13. 推荐给下一个 AI Agent 的启动步骤

1. 只读列出项目根目录和19个scene，不假定工作区与本文档完全同步。
2. 读取本文档、`dataset_inventory.csv`、reference的`prn_validation_summary.csv`。
3. 核对目标任务是否属于：剩余PRN验证、batch runner、事件提取、统计关联或20.46 MHz泛化。
4. 若要运行SAGE，先完成第11.1节检查，并先向用户报告唯一channel、输入路径、目标目录状态。
5. 若目标是剩余reference PRN，建议顺序从G12开始，一次只运行一个PRN，并在每次结束后更新汇总。
6. 若目标是批量化，先实现dry-run计划和失败隔离，不要直接启动124个任务。
7. 所有物理结论必须保留证据层级：Stage2候选、Stage3持续、Stage4确认、外部真值是四个不同概念。
> **状态迁移（2026-08-12）：** 本文件已转为历史参考。当前工程状态唯一来源是 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源是 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。
