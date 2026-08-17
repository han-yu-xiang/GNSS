# GNSS SAGE Daily AI Agent Handoff — 2026-08-07

> **历史文档：** 当前工程状态唯一来源为 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源为 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。本日报仅保留历史记录。

## 0. 给新 AI Agent 的启动指令

这是一份面向 AI Agent 的可执行交接文档。新的 GPT/Codex 启动后，应先阅读本文件，再检查实际目录和 CSV/JSON 文件；不要仅凭本文件推断文件一定存在。

当前下一项任务是：

> 只读检查并完成 reference scene `F1023_V70_D0117_P2` 的 G32 SAGE 验证。不要直接开始多 scene batch SAGE。

本文件记录截至 2026-08-07 的项目状态。今天没有修改代码、metadata、inventory 或已有 SAGE 实验结果；新增内容仅为本交接文档。

## 1. 项目目标与总体路线

项目研究目标是将 GNSS-SDR 解析结果、原始 GNSS IQ、导航信息、接收机轨迹、卫星几何信息与 SAGE 算法结合，用于：

1. 检测 GNSS 信号中的多径候选和持续事件；
2. 估计直达路径及反射路径的 delay、Doppler、relative power、coherence 等参数；
3. 将事件与 PRN、时间、卫星仰角、CN0、轨迹和场景环境因素关联；
4. 最终建立可用于统计建模的数据集：`scene × PRN × elevation` 条件下的多径模型数据集。

总体路线为：

```text
raw IQ
  -> GNSS-SDR tracking/telemetry/observables/PVT
  -> navigation RINEX 与 trajectory NMEA 标准化
  -> satellite elevation/geometry CSV
  -> dataset_inventory.csv 与输入完整性检查
  -> NAV symbol catalog
  -> Stage1 fast scan
  -> Stage2 fractional SAGE L=1..4
  -> Stage3 adjacent-window persistence
  -> Stage4 joint 100 ms confirmation
  -> multipath event database
  -> elevation/CN0/环境因素统计
  -> scene×PRN×elevation 统计模型
```

## 2. 当前项目阶段定位

当前项目已经完成：

- 19 个 scene 的基础目录和数据标准化工作；
- GNSS-SDR 结果、RINEX NAV、trajectory、satellite geometry 的整理；
- `dataset/dataset_inventory.csv` 的生成与检查；
- 通用化 `scripts/sage_pipeline/run_nav_sage_pipeline.m`（Pipeline V3）；
- reference scene 的多 PRN SAGE 验证：G06、G11、G12、G25、G28、G29 已有结果。

当前处于：

> `F1023_V70_D0117_P2` reference scene 多 PRN 验证阶段，距离完成 reference scene 矩阵还差 G32。

之后才能进入完整 reference 分析、事件数据库设计以及 batch SAGE 的干运行和小批量测试。

当前 pipeline 主要支持 10.23 MHz 数据。项目中虽然存在 20.46 MHz scene，但不能在未检查采样率和代码假设前直接运行当前 pipeline。

## 3. 项目根目录与关键目录

项目根目录为：

```text
E:\GNSS_Multipath_Project
```

主要目录：

- `scenes/`：每个采集场景的 raw、GNSS-SDR、导航、轨迹、卫星几何和 SAGE 结果。
- `scripts/preprocessing/`：导航、轨迹、卫星几何和 inventory 预处理脚本。
- `scripts/sage_pipeline/`：通用 MATLAB SAGE pipeline，以及 PRN 汇总脚本。
- `dataset/`：`dataset_inventory.csv` 等数据集级索引和元数据。
- `dataset_generation_logs/`：批量预处理和数据生成日志。
- `full_parse_v1/`：GNSS-SDR 全量解析相关配置或历史处理材料；使用前先检查其实际内容。
- `configs/`：项目配置文件。
- `docs/`：项目 handoff、数据结构和每日交接文档。

reference scene 为：

```text
scenes/F1023_V70_D0117_P2/
```

其关键目录含义：

- `raw/`：scene-local 原始复数 IQ；当前文件为 `raw/F1023_V70_D0117_P2.bin`。
- `gnss_sdr/`：GNSS-SDR 解析产物，包含 `tracking/`、`telemetry/`、`observables/`、`pvt/`、`nmea/`、`rinex/` 和配置/日志。
- `navigation/rinex_nav/`：标准化 NAV 文件 `RINEXFILE.26N`。
- `trajectory/`：标准化 NMEA 文件 `F1023_V70_D0117_P2_trajectory.nmea`。
- `satellite/`：由 NMEA 与 RINEX NAV 生成的卫星 elevation/geometry CSV。
- `sage_results/`：历史 G06 基线和通用 v2 PRN 输出。

reference scene 当前 metadata 中确认：

- `scene_role=reference_scene`；
- GPS L1 C/A，复数 IQ；
- `sample_rate_hz=10230000`；
- GNSS-SDR、navigation、trajectory、SAGE、satellite geometry 均为 `completed`；
- satellite geometry 输出为：
  - `satellite/F1023_V70_D0117_P2_satellite_elevation_timeseries.csv`
  - `satellite/F1023_V70_D0117_P2_satellite_elevation_summary.csv`

## 4. 数据索引与输入状态

实际索引文件：

```text
dataset/dataset_inventory.csv
```

reference scene 在 inventory 中的关键记录为：

| 字段 | 当前值 |
|---|---|
| scene role | `reference_scene` |
| sampling rate | `10230000 Hz` |
| raw storage | `scene_local` |
| GNSS-SDR | `SUCCESS` |
| tracking | 24 个文件（12 DAT、12 MAT） |
| telemetry | 7 个 DAT、7 个 MAT |
| RINEX NAV | 存在 |
| trajectory | 存在 |
| satellite geometry | `completed`，2 个 CSV |
| available PRNs | G06、G11、G12、G25、G28、G29、G32 |
| PRN-channel map | G06:4，G11:5，G12:6，G25:0，G28:1，G29:7，G32:11 |
| inventory warnings | 空 |

raw IQ 的路径和 storage 规则不能从普通 scene 复制：reference scene 使用本地文件：

```text
scenes/F1023_V70_D0117_P2/raw/F1023_V70_D0117_P2.bin
```

运行任一 PRN 前仍须实际检查：inventory mapping、metadata、raw IQ、对应 tracking MAT、对应 telemetry DAT、RINEX NAV、trajectory、satellite CSV、采样率和目标输出目录。

## 5. SAGE pipeline 约定

主脚本：

```text
scripts/sage_pipeline/run_nav_sage_pipeline.m
```

典型调用参数：

```matlab
run_nav_sage_pipeline( ...
    "F1023_V70_D0117_P2", ...
    "G32", ...
    "TrackingChannel", 11, ...
    "ProjectRoot", "E:\\GNSS_Multipath_Project", ...
    "Resume", true)
```

G32 的 channel=11 来自当前 inventory，正式运行前仍需重新做只读唯一性和文件存在检查。

pipeline 当前约定：

- 输入：`sceneId`、`PRN`、显式 `TrackingChannel`、`ProjectRoot`；
- 当前有效采样率范围重点是 10.23 MHz；
- 输出：`scenes/<sceneId>/sage_results/nav_sage_v2/<PRN>/`；
- `Resume=true` 时允许使用已有 checkpoint；中断时保留 checkpoint 和已有中间结果；
- 不应依赖自动猜 channel，channel 必须由 inventory 和实际文件共同确认。

各阶段作用：

- Stage0：读取 telemetry NAV symbols，建立 NAV symbol catalog，去除/标记无效 symbol，并形成完整 40 ms windows。
- Stage1：NAV wipe 后进行快速 delay/Doppler 扫描，筛选局部残差峰和候选窗口，并扩展邻居窗口供 Stage2 使用。
- Stage2：对候选 40 ms 窗口运行 fractional-delay SAGE，比较 `L=1..4`，输出模型阶数、路径和选择结果。`L>=2` 只是局部高阶模型证据，不等于 confirmed multipath。
- Stage3：在相邻窗口之间检查路径 delay、Doppler、power 的持续性，形成 reliable centers。
- Stage4：使用约 100 ms、5 个 snapshot 的 joint estimation，对 Stage3 中心进行联合确认。当前 confirmed 定义为 `joint_valid==1 && joint_multipath_count>0`。

## 6. 今天完成的工作（2026-08-07）

### 6.1 G12 验证

对 `F1023_V70_D0117_P2 / G12 / channel 6` 先完成只读输入检查，然后使用未修改的通用 pipeline 完成 Stage0–Stage4。

输出目录：

```text
scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G12/
```

关键结果：1177 个有效 NAV symbols、1175 个 40 ms windows；Stage1 96 个候选窗口；Stage2 选择 L1/L2/L3/L4 为 38/12/1/45，`L>=2=58`、`L>=3=46`；Stage3 4 个 reliable centers；Stage4 4 个 joint 结果；确认窗口 970、971，共 2 个 confirmed multipath events。

### 6.2 G29 验证

对 `F1023_V70_D0117_P2 / G29 / channel 7` 先完成只读输入检查，然后使用以下逻辑参数运行未修改 pipeline：

```text
sceneId=F1023_V70_D0117_P2
PRN=G29
TrackingChannel=7
ProjectRoot=E:\GNSS_Multipath_Project
```

输出目录：

```text
scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G29/
```

运行正常完成，MATLAB 进程已退出；期间出现的 figure export coordinate-toolbar warning 是非致命 warning，不影响 CSV/MAT 结果。

G29 结果为：1177 个有效 NAV symbols、1175 个 40 ms windows；Stage1 扫描 1175 个窗口，Stage2 候选 77 个窗口；Stage2 共评估 308 个模型（77×4），最终选择 L1/L2/L3/L4 为 45/6/2/24，`L>=2=32`、`L>=3=26`；Stage3 1 个 reliable center，中心窗口 80；Stage4 1 个 joint 结果、1 个 joint multipath、1 个 confirmed event。

G29 confirmed event：窗口 80，时间 `39.3959774193548 s`，超额 delay `1.1 samples / 0.11 chip`，Doppler offset `-5.33569790471529 Hz`，relative power `-3.15175805378153 dB`，coherence `0.869766075861875`。

今天的运行没有覆盖 G06、G11、G12、G25、G28，也没有修改 metadata、inventory 或其它 scene 文件。

## 7. Reference scene PRN 验证矩阵

### 7.1 当前矩阵

| PRN | Tracking channel | 状态 | 输出位置 |
|---|---:|---|---|
| G06 | 4 | 已完成；历史 v1 reference baseline | `sage_results/G06_nav_sage_v1/` |
| G11 | 5 | 已完成；通用 v2 | `sage_results/nav_sage_v2/G11/` |
| G12 | 6 | 已完成；今日验证并保留 | `sage_results/nav_sage_v2/G12/` |
| G25 | 0 | 已完成；LOS/低多径参考 | `sage_results/nav_sage_v2/G25/` |
| G28 | 1 | 已完成；候选但 Stage4 拒绝 | `sage_results/nav_sage_v2/G28/` |
| G29 | 7 | 已完成；今日验证并保留 | `sage_results/nav_sage_v2/G29/` |
| G32 | 11 | 未完成；下一项任务 | 目标 `sage_results/nav_sage_v2/G32/` 当前不存在 |

### 7.2 已完成 PRN 的 Stage0–Stage4 统计

表中 Stage1 candidates 是进入 Stage2 的候选窗口数量；Stage2 的 L1–L4 是最终选择窗口按模型阶数分组；Stage4 confirmed 按 `joint_valid==1 && joint_multipath_count>0` 统计。

| PRN | Ch | NAV symbols | 40 ms windows | Stage1 scanned | Stage1 candidates | L1 | L2 | L3 | L4 | L>=2 | L>=3 | Stage3 reliable | Stage4 joint | Confirmed MP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| G06 | 4 | 321 | 319 | 319 | 95 | 8 | 29 | 17 | 41 | 87 | 58 | 2 | 2 | 2 |
| G11 | 5 | 1177 | 1175 | 1175 | 101 | 45 | 4 | 22 | 30 | 56 | 52 | 7 | 7 | 1 |
| G12 | 6 | 1177 | 1175 | 1175 | 96 | 38 | 12 | 1 | 45 | 58 | 46 | 4 | 4 | 2 |
| G25 | 0 | 1177 | 1175 | 1175 | 52 | 40 | 2 | 0 | 10 | 12 | 10 | 0 | 0 | 0 |
| G28 | 1 | 900 | 898 | 898 | 54 | 42 | 4 | 5 | 3 | 12 | 8 | 2 | 2 | 0 |
| G29 | 7 | 1177 | 1175 | 1175 | 77 | 45 | 6 | 2 | 24 | 32 | 26 | 1 | 1 | 1 |

补充：G06 是历史 `G06_nav_sage_v1` 结果，不能把它当作与 G11/G12/G25/G28/G29 完全同版本的 v2 实验；比较时必须保留 pipeline 版本差异说明。

## 8. 当前 confirmed multipath 事件

以下是截至今天从实际 Stage4 结果中确认的 6 个事件、7 条路径。G06 的结果文件位于历史 v1 目录，其他 PRN 位于通用 v2 目录。

| PRN | Window | Time (s) | Excess delay (samples/chips) | Doppler offset (Hz) | Relative power (dB) | Coherence | 结果文件 |
|---|---:|---:|---|---:|---:|---:|---|
| G06 | 203 | 41.8614130 | 1.6 / 0.16；2.6 / 0.26；8.3 / 0.83 | +149.664302；+199.664302；+149.664302 | +18.192567；+6.902518；+7.104596 | 0.332664 | `sage_results/G06_nav_sage_v1/stage4_joint_paths.csv`；summary 同目录 |
| G06 | 264 | 43.0814180 | 3.9 / 0.39 | +159.664302 | +22.059548 | 0.034598 | `sage_results/G06_nav_sage_v1/stage4_joint_paths.csv`；summary 同目录 |
| G11 | 640 | 50.5987615 | 1.1 / 0.11 | -10.013107 | -7.407073 | 0.828954 | `sage_results/nav_sage_v2/G11/stage4_joint_paths.csv`；summary 同目录 |
| G12 | 970 | 57.1917811 | 1.1 / 0.11 | +24.427319 | -15.920538 | 0.577073 | `sage_results/nav_sage_v2/G12/stage4_joint_paths.csv`；summary 同目录 |
| G12 | 971 | 57.2117812 | 1.1 / 0.11 | -0.599715 | -5.113573 | 0.886065 | `sage_results/nav_sage_v2/G12/stage4_joint_paths.csv`；summary 同目录 |
| G29 | 80 | 39.3959774 | 1.1 / 0.11 | -5.335698 | -3.151758 | 0.869766 | `sage_results/nav_sage_v2/G29/stage4_joint_paths.csv`；summary 同目录 |

G06 window 203 有 3 条确认路径，因此事件数为 1、路径数为 3；G06 window 264 有 1 条路径。G11、G12、G29 各确认 1 条路径/事件。上述参数是当前算法输出，不应在没有额外校准和外部场景标注时解释为唯一的物理反射真值。

## 9. 当前实验结论

当前应采用以下三类解释：

### 9.1 LOS/低多径参考：G25

G25 有 52 个 Stage1 candidates 和 12 个 Stage2 `L>=2` 窗口，但没有形成 Stage3 reliable event，因此没有 Stage4 joint 输入，也没有 confirmed multipath。它适合作为当前 reference scene 内的 LOS/低多径算法对照。

准确表述是“按当前 Stage3/Stage4 判据未确认多径”，不能表述为物理上绝对无多径。

### 9.2 候选但拒绝：G28

G28 有 54 个 Stage1 candidates、12 个 `L>=2` 和 8 个 `L>=3` 窗口，Stage3 保留 2 个中心，Stage4 也产生 2 个 joint 结果，但两个 joint 结果都回落到 L=1、`joint_multipath_count=0`。因此它是候选但被联合确认拒绝的样本，说明 Stage2 高阶模型和短时持续性不足以直接证明多径。

### 9.3 confirmed multipath：G06、G11、G12、G29

- G06：历史 v1 基线，2 个 confirmed events、4 条 confirmed paths；window 203 具有最多路径和最大 delay 范围，适合做强多径流程基准。
- G11：7 个 Stage3/Stage4 中心中仅窗口 640 通过 Stage4，说明 joint 100 ms 筛选较强；确认路径 delay 为 0.11 chip。
- G12：4 个 Stage3/Stage4 中心中窗口 970、971 通过，具有两条短 delay confirmed paths。
- G29：仅 1 个 Stage3/Stage4 中心窗口 80 即通过 Stage4，确认一条 0.11 chip、相对 Doppler 为 -5.336 Hz 的路径。

当前结论是：Stage2 高阶模型用于发现局部候选，Stage3 检查时间持续性，Stage4 joint common-geometry 约束才产生当前的 confirmed multipath 统计。G28 的结果尤其说明 `L>=2` 不等于 confirmed；G11 的 7 到 1 的收缩也说明 Stage4 是重要的拒绝层。

## 10. 现有汇总文件的注意事项

当前已有：

- `scenes/F1023_V70_D0117_P2/sage_results/prn_validation_summary.csv`
- `scenes/F1023_V70_D0117_P2/sage_results/prn_validation_report.md`
- `scenes/F1023_V70_D0117_P2/sage_results/reference_prn_analysis_report.md`

经实际读取，`prn_validation_summary.csv` 当前仍为 5 行，包含 G06、G11、G25、G28、G12，尚未纳入今天新增的 G29。现有 `reference_prn_analysis_report.md` 也仍是五 PRN 分析，不包含 G29。不要在本次交接文档中假装这些汇总已经包含 G29。

推荐在 G32 完成后，一次性只读读取 G06/G11/G12/G25/G28/G29/G32 的 Stage0–Stage4 CSV，再安全更新或生成完整 reference 汇总和分析；更新前先检查是否需要保留历史字段和既有内容。

## 11. 关键代码、脚本和结果文件

### 11.1 预处理脚本

- `scripts/preprocessing/batch_prepare_navigation.py`：批量准备/标准化 navigation。
- `scripts/preprocessing/batch_prepare_trajectory.py`：批量准备/标准化 trajectory。
- `scripts/preprocessing/satellite_geometry.py`：生成单 scene 卫星几何/elevation。
- `scripts/preprocessing/batch_generate_satellite_geometry.py`：批量生成 satellite geometry。
- `scripts/preprocessing/generate_dataset_inventory.py`：生成 `dataset_inventory.csv`。

### 11.2 SAGE 脚本

- `scripts/sage_pipeline/run_nav_sage_pipeline.m`：当前通用 Stage0–Stage4 pipeline，不要为单个验证随意改算法。
- `scripts/sage_pipeline/g06_nav_sage_pipeline.m`：G06 历史/专用流程，不能用来覆盖或重建 G06 v1。
- `scripts/sage_pipeline/summarize_prn_validation.py`：读取已有 PRN 结果并生成汇总的辅助脚本；使用前先确认它当前支持的 PRN 范围和输出字段。

### 11.3 重要结果路径

- G06 immutable baseline：`scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/`
- G11：`scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G11/`
- G12：`scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G12/`
- G25：`scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G25/`
- G28：`scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G28/`
- G29：`scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G29/`
- G32 目标目录：`scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G32/`，截至本交接生成时不存在。

每个完整 PRN 输出通常包括：`run_context.json`、`stage0_valid_symbols.csv`、`stage0_valid_40ms_windows.csv`、`stage1_nav_fast_scan.csv`、`stage2_model_orders.csv`、`stage2_selected_windows.csv`、`stage3_reliable_centers.csv`、`stage4_joint_summary.csv`、`stage4_joint_paths.csv` 及对应 MAT/checkpoint/overview 文件。G06 v1 的文件集合略有历史差异，先列目录再读取。

## 12. 实验保护规则

未来 AI Agent 必须遵守：

1. `G06_nav_sage_v1` 是历史 reference baseline，绝不覆盖、删除、重跑写回或“整理替换”。
2. 不修改已有 G11、G12、G25、G28、G29 Stage0–Stage4 结果；新实验写入新的明确 PRN 目录或经用户明确授权的目录。
3. 不修改 `metadata.json`、`dataset_inventory.csv` 或其它 scene 文件来绕过输入问题。
4. 运行 SAGE 前必须先读取 inventory 和 metadata，并验证 raw IQ、tracking MAT、telemetry DAT、RINEX NAV、trajectory、satellite geometry、采样率、channel 唯一性和输出目录状态。
5. 不凭空假设文件存在；所有路径必须用实际文件检查确认。尤其要区分 `gnss_sdr/nmea` 与标准化 `trajectory/`、`gnss_sdr/rinex` 与标准化 `navigation/rinex_nav/`。
6. 输出目录已存在时不得自动覆盖；若需要续跑，必须确认是同一 scene/PRN/channel/采样率/代码上下文，并使用保留 checkpoint 的 resume 方式。
7. 如果运行中断，保留 checkpoint 和已写出的中间结果，不删除、不清空、不用新的空目录覆盖旧结果。
8. G06 v1 与通用 v2 的结果必须保留 pipeline 版本差异，不能未经校准直接混合解释绝对功率。
9. Stage2 的 `L>=2`、Stage3 reliable event 和 Stage4 confirmed event 是不同证据层级，汇报时不能混称。
10. 任何批量运行前先做 dry-run：只解析 inventory、输入路径、采样率、channel、输出冲突和预估任务列表，不启动 SAGE。

## 13. 不可改变的下一阶段路线

推荐顺序固定为：

1. 完成 reference scene G32 的只读输入检查，然后运行 G32 完整 Stage0–Stage4；channel 使用 inventory 中的 11，但运行前必须重新确认唯一性和实际文件。
2. 读取七颗 PRN 的所有 Stage0–Stage4 结果，生成 reference scene 完整 PRN 汇总和分析报告；在这一步补入 G29、G32，明确 G06 v1 与 v2 的版本差异。
3. 设计 `multipath event database` 的字段、主键、事件级/路径级关系和结果文件 provenance。至少保留 scene、PRN、channel、window、time、elevation、CN0、Stage2/3/4 状态、delay、Doppler、relative power、coherence、pipeline version 和源文件路径。
4. 设计 batch SAGE dry-run，只输出任务清单、输入完整性和潜在冲突，不运行算法。
5. 选择少量非 reference scene 做小批量测试，核对 10.23 MHz 输入和输出隔离。
6. 经过小批量结果审查后，才进入全量 SAGE 运行和后续统计建模。

不要跳过 G32，也不要在 reference scene 分析完成前直接开始多 scene 全量 SAGE。

## 14. Current Status

截至 2026-08-07 结束时：

- 项目处于“数据已标准化、inventory 已完成、通用 SAGE 已泛化、reference scene 多 PRN 验证接近完成”的阶段。
- reference scene 已完成 G06、G11、G12、G25、G28、G29；G32 尚未运行。
- 当前实际 confirmed multipath 为 G06 两个事件、G11 一个、G12 两个、G29 一个；G25 无 Stage3/Stage4 confirmed，G28 有 Stage3/Stage4 候选但无 confirmed。
- G29 的完整结果已经存在于 `sage_results/nav_sage_v2/G29/`，但现有 `prn_validation_summary.csv` 和 `reference_prn_analysis_report.md` 尚未更新纳入 G29。
- G06 历史 `G06_nav_sage_v1` 必须继续作为不可覆盖的 reference baseline。

下一次启动后的第一任务：

> 先检查 `F1023_V70_D0117_P2 / G32 / channel 11` 的 inventory、metadata、raw IQ、tracking、telemetry、navigation、trajectory、satellite geometry 和空的目标输出目录；检查通过并获得运行确认后，再运行 G32。不要直接开始 batch SAGE。
> **状态迁移（2026-08-12）：** 本日报只保留历史记录。当前工程状态唯一来源是 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源是 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。
