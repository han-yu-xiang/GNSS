# GNSS 多径 SAGE 项目 AI Agent 交接文档

> **历史文档：** 当前工程状态唯一来源为 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源为 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。本文件仅作历史参考。

> 文档类型：面向新 GPT/Codex Agent 的项目交接与安全运行说明  
> 当前扫描时间：2026-08-07（Asia/Shanghai）  
> 项目根目录：E:\GNSS_Multipath_Project  
> 本文档依据当前文件系统、metadata、dataset_inventory.csv、已有 SAGE CSV/MAT 结果和关键脚本扫描生成。  
> 本次任务只新增本文档；没有修改代码、raw IQ、scene 数据、metadata、inventory 或已有 SAGE 结果。

## 0. 给新 AI Agent 的接手规则

你没有本次聊天的历史上下文时，必须先阅读本文件，再查看实际目录。本文档是当前项目状态的优先说明；较早的 docs/PROJECT_DATA_STRUCTURE.md 只反映数据整理早期状态，不能用来判断 navigation、trajectory、satellite 或 SAGE 是否最新。

项目当前已经越过“整理输入目录”阶段，处于 **SAGE pipeline 的单场景多 PRN 验证阶段**。安全边界如下：

1. scenes/F1023_V70_D0117_P2 是 reference scene，不按普通 scene 清理、迁移或覆盖。
2. scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1 是历史实验基线，禁止覆盖、重命名、移动或删除。
3. 不移动、改写或删除 raw IQ、gnss_sdr、navigation、trajectory、satellite 和已有 sage_results。
4. 运行 SAGE 前必须读取 dataset/dataset_inventory.csv，确认目标 PRN 的唯一 tracking channel。若有多个候选 channel，必须停止并报告，不能自动猜测。
5. 当前通用 MATLAB pipeline 只支持 10.23 MHz。6 个 20.46 MHz scene 虽然已经完成数据准备，但不能通过删除检查或修改参数强行运行。
6. inventory 中的输入完整性和 channel 映射仍有价值，但其 SAGE 状态列在 G11/G25/G28 v2 运行之前生成，SAGE 最新状态必须以实际结果目录和验证汇总为准。
7. 任何修改或长时间实验前，先做只读目录、metadata、输入文件和输出目录检查，并向用户说明将要写入的精确路径。

## 1. 项目背景与最终目标

本项目研究 GNSS 信号在真实车辆/环境场景中的多径现象。输入包括：

- GNSS-SDR 对原始采样的 tracking、telemetry、observables、PVT、NMEA 和 RINEX 解析结果；
- 原始复数 IQ 数据；
- GNSS NAV 符号、车辆轨迹/速度和卫星观测信息；
- GPS L1 C/A 信号模型。

核心算法是带 NAV 符号辅助的 **NAV-wiped fractional SAGE**。它先使用已解调 NAV 符号消除数据比特翻转，再对短时间窗口内的直达径（LOS）和候选多径分量估计：

- 相对时延/超额时延；
- 相对 Doppler；
- 相对路径功率；
- 路径数量及其随时间的持续性；
- 经过更长时间联合拟合后的 confirmed multipath 状态。

最终目标不是只检测几个多径峰，而是建立可跨场景统计的数据集，至少能按下列维度分析：

    scene × PRN × elevation/azimuth × SNR/CN0 × vehicle speed/environment

最终统计模型应支持：

- 多径事件发生率；
- confirmed 多径条数分布；
- 超额时延和路径长度分布；
- 相对 Doppler、相对功率和持续时间分布；
- Stage2 候选到 Stage4 确认的转化率；
- 不同仰角、CN0、车辆速度和环境条件下的多径风险。

当前还没有完成最终统计模型，也没有外部场景真值标注。当前结果用于验证 pipeline 和事件定义，不应直接解释为最终物理统计结论。

## 2. 当前项目目录结构

项目根目录为：

    E:\GNSS_Multipath_Project\
    ├── scenes\
    ├── scripts\
    │   ├── preprocessing\
    │   └── sage_pipeline\
    ├── dataset\
    ├── dataset_generation_logs\
    ├── docs\
    ├── configs\
    └── full_parse_v1\

本次扫描得到的根目录概况为：

| 目录 | 当前用途 | 扫描到的文件/目录规模 |
|---|---|---:|
| scenes | 19 个标准化 scene 及其全部场景级输入、派生数据、SAGE 结果 | 1383 个文件，330 个目录 |
| scripts | preprocessing 和 MATLAB/Python SAGE 工具 | 8 个脚本，2 个子目录 |
| dataset | 跨 scene 的输入清单 | 1 个 CSV |
| dataset_generation_logs | navigation、trajectory、satellite 批处理日志 | 3 个日志 |
| docs | 项目说明和交接文档 | 当前已有 2 个文档，本文件为新增文档 |
| configs | 预留项目级配置目录 | 当前为空 |
| full_parse_v1 | 迁移前的 GNSS-SDR 解析结果源，作为历史保留数据 | 1144 个文件，171 个目录 |

根目录当前没有项目级普通文件。当前扫描未发现根目录 .git，因此不能假设该目录是 Git 工作树，也不能据此推断版本历史或工作区差异。

### 2.1 19 个 scene

10.23 MHz scene（13 个）：

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

20.46 MHz scene（6 个）：

    F2046_V30_D0131_P2
    F2046_V30_D0131_P4
    F2046_V30_D0203_P2
    F2046_V60_D0129_P1
    F2046_V60_D0129_P3
    F2046_V60_D0202_P1

普通 scene 的标准一级结构为：

    scenes/<scene_id>/
    ├── metadata.json
    ├── raw/
    ├── gnss_sdr/
    ├── navigation/
    ├── trajectory/
    ├── satellite/
    └── sage_results/

本次实际检查中，19/19 个 scene 都具备这 7 个一级项；所有 scene 的 metadata、标准 NAV/OBS、trajectory、satellite 两个 CSV、tracking MAT 和 telemetry DAT 关键入口都存在。

### 2.2 单个 scene 内部目录

#### metadata.json

记录 scene 身份、信号类型、采样率、raw IQ 存储方式和各阶段处理状态。重要字段位于：

    {
      "scene_id": "...",
      "scene_role": "standard_scene or reference_scene",
      "signal": {
        "signal_type": "GPS_L1_CA",
        "sample_rate_hz": 10230000 or 20460000,
        "complex_iq": true
      },
      "raw_iq": {
        "storage_mode": "scene_local or external_storage",
        "path": "..."
      },
      "processing_status": {
        "gnss_sdr": "completed",
        "navigation": "completed",
        "trajectory": "completed",
        "satellite_geometry": "completed"
      }
    }

注意：采样率实际在 metadata.signal.sample_rate_hz，不是顶层 metadata.sampling_rate_hz。运行 pipeline 或自行扫描时不要读错字段。

#### raw/

保存或指向原始复数 IQ：

- reference scene 使用 storage_mode=scene_local，实际文件为：

      scenes/F1023_V70_D0117_P2/raw/F1023_V70_D0117_P2.bin

- 其余 18 个 scene 使用 storage_mode=external_storage，metadata 和 raw/data_address.txt 指向：

      E:\AAGNSSDR_input\raw_data\<scene_id>.bin

本次检查确认 19 个 metadata 记录的 raw 路径均实际存在。普通 scene 没有把外部 IQ 复制到项目内。Python preprocessing 工具不会读取 raw IQ；SAGE MATLAB pipeline 会直接读取它。

#### gnss_sdr/

GNSS-SDR 原始解析结果，不能当作可随意重建的中间缓存。标准子目录包括：

    gnss_sdr/
    ├── config/       # scene 使用的 GNSS-SDR .conf
    ├── logs/         # GNSS-SDR 运行日志
    ├── tracking/    # <scene>_track_ch_<n>.dat/.mat
    ├── telemetry/   # <scene>_telemetry_ch_<n>.dat/.mat 和 CRC 统计
    ├── observables/ # observables .dat/.mat
    ├── pvt/         # PVT .dat/.mat
    ├── rinex/       # GNSS-SDR 原始 RINEXFILE.26N/.26O
    └── nmea/        # GNSS-SDR 原始 NMEA 输出

19 个 scene 的 inventory 状态均为 gnss_sdr_status=SUCCESS。tracking 文件名中的 channel 不能单独推断 PRN；必须结合 inventory 中的 prn_tracking_channel_map。

#### navigation/

标准化导航入口，是 GNSS-SDR 原始 RINEX 的副本，不是移动后的源文件：

    gnss_sdr/rinex/RINEXFILE.26N
        → navigation/rinex_nav/RINEXFILE.26N
    gnss_sdr/rinex/RINEXFILE.26O
        → navigation/rinex_obs/RINEXFILE.26O

当前 19/19 scene 已准备完成。reference 的目标文件已存在时，preprocessing 脚本只比较并保留，不覆盖，即使源与目标 hash 不同也不会自动改写。

#### trajectory/

保存标准化 NMEA 轨迹副本：

    gnss_sdr/nmea/<scene_id>_trajectory.nmea
        → trajectory/<scene_id>_trajectory.nmea

当前 19/19 scene 已准备完成。通用 SAGE pipeline 要求 trajectory/ 中恰好一个 .nmea 文件，并从其中读取车辆速度，用于相对 Doppler 约束。

#### satellite/

保存由 NMEA GSV 和 RINEX NAV 过滤生成的派生卫星观测 CSV：

    <scene_id>_satellite_elevation_timeseries.csv
    <scene_id>_satellite_elevation_summary.csv

当前 19/19 scene 均有这两个文件。字段包含 PRN、时间、elevation、azimuth、SNR 等。这里的 SNR 是 NMEA GSV 观测量，不能无说明地当作 tracking CN0。

该目录不是广播星历重算结果：

- elevation、azimuth、SNR 直接解析自时间戳 NMEA GSV；
- RINEX NAV 只用于筛选存在导航记录的 GPS PRN；
- 不根据广播星历重新计算卫星位置；
- 不读取 raw IQ。

#### sage_results/

保存某个 scene 的 SAGE 输出。普通 scene 当前为空；reference scene 保存历史 G06 结果、G11/G25/G28 通用 v2 结果和验证汇总。通用 pipeline 的输出隔离在：

    sage_results/nav_sage_v2/<PRN>/

不要把新的 v2 结果写入 G06_nav_sage_v1，也不要把历史专项诊断文件移动到 v2 目录。

## 3. 完整数据处理流水线

整体数据流是：

    raw complex IQ
        + GNSS-SDR 配置/解析
        ↓
    gnss_sdr tracking / telemetry / observables / pvt / RINEX / NMEA
        ↓
    navigation、trajectory 标准化
        ↓
    satellite geometry 派生 CSV
        ↓
    dataset_inventory.csv（scene 与 PRN/channel 输入清单）
        ↓
    指定 scene + PRN + tracking channel 的 NAV-wiped SAGE Stage0–Stage4
        ↓
    confirmed multipath event/path 表
        ↓
    scene × PRN × elevation/CN0/speed/environment 数据库
        ↓
    统计模型

### 3.1 原始 IQ 与 GNSS-SDR 解析

原始 IQ 是 SAGE 最终读取的信号数据。GNSS-SDR 对每个 scene 产生 tracking、telemetry、observables、PVT、RINEX 和 NMEA。通用 SAGE 当前实际依赖：

    raw_iq.path
    gnss_sdr/tracking/<scene>_track_ch_<channel>.mat
    gnss_sdr/telemetry/<scene>_telemetry_ch_<channel>.dat
    trajectory/<scene>_trajectory.nmea
    navigation/rinex_nav/RINEXFILE.26N
    satellite/*.csv

其中 telemetry 提供已解调的 GPS NAV symbol，tracking MAT 提供时间、相关、Doppler/CN0 等跟踪状态。PRN 与 channel 的关系必须从 inventory 读取，不能按文件名或 channel 编号臆测。

### 3.2 Navigation 标准化

输入：gnss_sdr/rinex/RINEXFILE.26N/.26O。  
输出：navigation/rinex_nav/RINEXFILE.26N 和 navigation/rinex_obs/RINEXFILE.26O。  
工具：scripts/preprocessing/batch_prepare_navigation.py。  
日志：dataset_generation_logs/navigation_prepare_*.log。

脚本会验证 scene_id、输入文件唯一性、目标文件一致性并记录 SHA-256。普通 scene 可复制；reference scene 已有目标文件时只比较、不覆盖。

### 3.3 Trajectory 标准化

输入：gnss_sdr/nmea/<scene>_trajectory.nmea。  
输出：trajectory/<scene>_trajectory.nmea。  
工具：scripts/preprocessing/batch_prepare_trajectory.py。  
日志：dataset_generation_logs/trajectory_prepare_*.log。

脚本会要求能识别出单一轨迹输入，并验证已存在目标。reference scene 采用保留/比较策略。SAGE 使用标准化目录而不是直接依赖 GNSS-SDR 原始 NMEA 位置。

### 3.4 Satellite geometry 生成

输入：

    gnss_sdr/nmea/*.nmea
    navigation/rinex_nav/*.26N

输出：

    satellite/<scene>_satellite_elevation_timeseries.csv
    satellite/<scene>_satellite_elevation_summary.csv

工具：

    scripts/preprocessing/satellite_geometry.py
    scripts/preprocessing/batch_generate_satellite_geometry.py

批处理日志为 dataset_generation_logs/batch_satellite_geometry_*.log。公共算法 satellite_geometry.py 的语义必须保持：GSV 提供 elevation/azimuth/SNR，RINEX NAV 只做 PRN 筛选，不做广播星历位置重算，不读 raw IQ。

### 3.5 Inventory 生成

工具：scripts/preprocessing/generate_dataset_inventory.py。它只读扫描 metadata、GNSS-SDR 日志和 scene 文件结构，输出：

    dataset/dataset_inventory.csv

当前 CSV 是“每个 scene 一行”，不是每个 scene–PRN 一行。它包含：

- scene_id、scene_role、signal_type、sampling_rate_hz；
- raw 路径和存储模式；
- GNSS-SDR 文件存在性、文件数量和 channel；
- tracking channel 与 PRN 的解析映射；
- telemetry、observables、RINEX NAV、trajectory、satellite 状态；
- available_prns、available_prn_count、prn_tracking_channel_map；
- inventory 生成时看到的 sage_results_* 状态；
- warnings。

当前 inventory 统计：

    scene 行数                       19
    10.23 MHz scene                 13
    20.46 MHz scene                  6
    可用 scene–PRN 组合              124
    唯一 PRN→channel 组合            119
    多候选 PRN→channel 组合            5
    gnss_sdr_status=SUCCESS          19/19
    sage_results_status=completed     1 行（reference，生成 inventory 时）
    sage_results_status=not_run      18 行

sage_result_file_count=32 的 reference inventory 值对应早先的 G06 结果，不包括后来生成的 G11/G25/G28 v2 结果。因此当前 SAGE 状态不能只看 inventory，必须扫描实际 sage_results 目录。

### 3.6 SAGE 与未来事件提取

每个任务只能明确指定一个 scene、一个 PRN 和一个 tracking channel。SAGE 输出 Stage0–Stage4 CSV/MAT、运行上下文和 overview PNG。当前已有验证汇总工具只覆盖 reference 的 G06/G11/G25/G28，尚未形成跨 scene 的统一事件数据库。

未来事件提取应以 Stage4 为严格确认层，保留 Stage2、Stage3 的证据字段，不要把 Stage2 的高阶模型直接标成确认事件。建议长期事件键为：

    scene_id + PRN + center_window_id + path_id + pipeline_version

### 3.7 统计建模目标

事件数据库形成后，应将事件时间关联到：

- satellite timeseries 的 elevation、azimuth、NMEA SNR；
- tracking 结果中的 CN0；
- trajectory 的车辆速度；
- scene 条件、位置或未来补充的道路/环境标签。

必须显式区分 NMEA GSV SNR 和 tracking CN0。当前项目没有完成该数据库，也没有最终统计模型；这是后续工作，不得假设这些文件已经存在。

## 4. 当前数据集状态

截至本次扫描，19 个 scene 的准备状态如下：

| 项目 | 状态 |
|---|---|
| scene 数量 | 19 |
| 10.23 MHz scene | 13 |
| 20.46 MHz scene | 6 |
| GNSS-SDR 解析结果 | 19/19，inventory 为 SUCCESS |
| navigation 标准化 | 19/19，metadata 为 completed |
| trajectory 标准化 | 19/19，metadata 为 completed |
| satellite geometry | 19/19，metadata 为 completed，每个 scene 有两个 CSV |
| metadata 记录的 raw 路径存在 | 19/19 |
| dataset inventory | 已生成，19 行、124 个可用 scene–PRN 组合 |
| 普通 scene 正式批量 SAGE | 尚未开始 |
| reference 已完成 v2 PRN | G11、G25、G28 |
| reference 待验证 PRN | G12、G29、G32 |

raw 存储规则为：reference scene 本地保存 1 个 .bin；其余 scene 只在 project scene 中保留地址文件和 metadata 路径，真实 IQ 位于 E:\AAGNSSDR_input\raw_data\<scene_id>.bin。本次检查确认路径存在，但外部存储不属于本项目目录，未来 Agent 不能把它当作项目内文件或擅自复制全部 IQ。

数据准备完成不等于多径建模完成。当前缺少：

- 20.46 MHz 的 pipeline 泛化与回归验证；
- 多 scene SAGE 批处理 runner；
- 跨 scene 的事件主表和路径表；
- 统一的 elevation/CN0/环境关联表；
- 外部场景真值和最终统计模型。

## 5. 通用 SAGE pipeline 状态

主入口：

    scripts/sage_pipeline/run_nav_sage_pipeline.m

MATLAB 调用示例：

    addpath("E:\GNSS_Multipath_Project\scripts\sage_pipeline");

    result = run_nav_sage_pipeline( ...
        "F1023_V70_D0117_P2", ...
        "G11", ...
        "TrackingChannel", 5, ...
        "ProjectRoot", "E:\GNSS_Multipath_Project", ...
        "Resume", true);

接口参数：

- sceneId：scene 文件夹名；
- prn：GPS PRN，可传数字 11 或字符串 "G11"；
- TrackingChannel：必须显式传入、非负整数；
- ProjectRoot：项目根目录，可显式传入；
- Resume：默认 true，允许匹配身份和配置的 checkpoint 恢复。

pipeline 会从 metadata.json 读取 metadata.signal.sample_rate_hz，确认 scene 为 10.23 MHz；确认 raw IQ、tracking MAT、telemetry DAT、trajectory 单一 NMEA、navigation 单一 RINEX NAV 和 satellite 目录存在。它不使用历史 G06 v1 结果作为通用入口输入。

当前代码扫描确认 run_nav_sage_pipeline.m 的 pipeline version 为 3，validated 配置为：

- GPS L1 C/A，名义码率 1.023 MHz；
- 10.23 MHz 下 samplesPerChip=10；
- Stage2 延迟步长 0.1 sample，即 0.01 chip；
- 最大模型阶数 L=4；
- L 表示总路径数，多径数量为 L-1；
- Stage3 默认要求至少 3 个连续窗口；
- Stage4 默认使用 5 个 snapshot，形成约 100 ms 联合估计。

### 5.1 输出目录

每个通用运行的输出目录固定为：

    scenes/<scene_id>/sage_results/nav_sage_v2/<PRN>/

典型输出文件为：

    run_context.json
    run_context.mat
    doppler_sign.mat
    stage0_nav_catalog.mat
    stage0_valid_symbols.csv
    stage0_valid_40ms_windows.csv
    stage1_nav_fast_scan.mat
    stage1_nav_fast_scan.csv
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

pipeline 创建或使用 v2 PRN 输出目录，并在 run_context.json/.mat 中记录 scene、PRN、channel、采样率和实际输入路径。若已有 context 与当前任务 scene/PRN/channel 不一致，代码拒绝复用；Resume 是恢复机制，不是覆盖安全的替代品。

### 5.2 Stage0：NAV symbol catalog

输入：指定 channel 的 telemetry DAT、tracking MAT、标准 trajectory NMEA。  
处理：把 telemetry 中指定 PRN 的连续、完整、质量合格 NAV symbol 与 tracking 时间/状态匹配，并构建连续 40 ms 窗口。NMEA 速度用于车辆运动导致的相对 Doppler 边界。  
输出：

    stage0_nav_catalog.mat
    stage0_valid_symbols.csv
    stage0_valid_40ms_windows.csv

Stage0 是输入覆盖和时间对齐层。没有有效 symbol 或 40 ms 窗口时，后续不能安全解释。

### 5.3 Doppler sign calibration

输入 raw IQ 和候选窗口。代码判断 GNSS-SDR Doppler 符号约定，保存 doppler_sign.mat。该符号会影响 Stage1–Stage4 的相对 Doppler 解释。

### 5.4 Stage1：NAV-wiped fast scan

输入 raw IQ、Stage0 40 ms 窗口、已知 NAV symbol 和 Doppler sign。代码先消除 20 ms data-bit 翻转，再扫描有效 40 ms 窗口中的主径和残差相关峰，筛选基础候选并加入相邻窗口。

输出：

    stage1_nav_fast_scan.mat
    stage1_nav_fast_scan.csv
    stage1_nav_progress.mat

Stage1 是高召回候选生成层，不是多径确认层。stage1_candidate_windows 不能直接当作 confirmed multipath 数量。

### 5.5 Stage2：fractional SAGE L=1–4

对 Stage1 候选执行 fractional-delay SAGE，拟合总路径数 L=1、2、3、4。使用 BIC、RSS 改善、路径功率、最小路径间隔、相对 Doppler 和 coherence 约束选择模型。

输出：

    stage2_nav_sage_L1_L4.mat
    stage2_model_orders.csv
    stage2_selected_windows.csv
    stage2_selected_paths.csv
    stage2_nav_progress.mat

L=1 代表单径模型；L>=2 只表示当前 40 ms 窗口的高阶模型较优，不能直接称为物理上确认的多径。

### 5.6 Stage3：persistence

在 Stage2 中心窗口附近的连续 40 ms 窗口中匹配路径，检查时延、Doppler 和功率是否保持一致，并要求达到最少连续窗口数。输出：

    stage3_nav_persistence.mat
    stage3_persistence.csv
    stage3_reliable_centers.csv

Stage3 将瞬时单窗口候选提升为“持续候选事件”，但仍可能在 Stage4 中回落为单径。

### 5.7 Stage4：joint 100 ms

对 Stage3 可靠中心使用 5 个 snapshot 做共同几何联合估计，总时间约 100 ms。输出：

    stage4_nav_joint_100ms.mat
    stage4_joint_summary.csv
    stage4_joint_paths.csv

当前项目的 confirmed multipath 定义是：

    stage4_joint_summary.csv:
        joint_valid == 1
        且 joint_multipath_count > 0

只有满足这两个条件的 joint 结果才进入当前 confirmed 统计口径。

## 6. 历史实验保护规则与 reference scene

reference scene：

    scenes/F1023_V70_D0117_P2

它除了标准 scene 目录外，还保留历史实验资产：

    legacy_results/
    generate_satellite_elevation.py
    g06_nav_sage_pipeline.m
    analyze_G06_events.m
    plot_G06_window203_correlation.m
    plot_G06_window203_overlay.m
    plot_G06_window203_stage2_internal_ddm.m
    GNSS_SAGE_NAV_HANDOFF.md

这些文件用于保留原始实验过程、诊断和历史交接上下文，不要自动清理。

历史 G06 基线目录：

    scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/

它由 G06 专用 MATLAB pipeline 生成，包含 Stage0–Stage4 结果、overview 和 diagnostics/ 专项诊断。当前通用 v2 pipeline 使用：

    scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/<PRN>/

v2 不读取、不覆盖 G06 v1。G06 v1 和 reference scene 的 raw IQ、旧脚本、旧 RINEX/NMEA 标准化文件都是实验基线的一部分。任何要比较算法版本的工作都应另建输出目录或明确获得用户授权，不能修改这些基线。

## 7. 当前 reference PRN 验证结果

机器可读汇总：

    scenes/F1023_V70_D0117_P2/sage_results/prn_validation_summary.csv

人工报告：

    scenes/F1023_V70_D0117_P2/sage_results/prn_validation_report.md

当前已汇总 PRN 为 G06、G11、G25、G28；表中 Stage2 的 L 是总路径数，L>=2 不是 confirmed 多径数。

| PRN | channel | Stage0 NAV symbols | Stage0 40 ms 窗口 | Stage1 扫描 | Stage1 候选 | Stage2 L1/L2/L3/L4 | Stage3 可靠事件 | Stage4 joint | confirmed MP 事件 |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|
| G06 | 4 | 321 | 319 | 319 | 95 | 8 / 29 / 17 / 41 | 2 | 2 | 2 |
| G11 | 5 | 1177 | 1175 | 1175 | 101 | 45 / 4 / 22 / 30 | 7 | 7 | 1 |
| G25 | 0 | 1177 | 1175 | 1175 | 52 | 40 / 2 / 0 / 10 | 0 | 0 | 0 |
| G28 | 1 | 900 | 898 | 898 | 54 | 42 / 4 / 5 / 3 | 2 | 2 | 0 |

### 7.1 G06：历史强多径基准

- channel 4；结果目录为 sage_results/G06_nav_sage_v1。
- Stage0 覆盖较短：321 个有效 NAV symbol、319 个 40 ms 窗口。
- Stage1 选出 95 个候选；Stage2 有 87 个窗口选择 L>=2，其中 58 个选择 L>=3。
- Stage3 保留窗口 203 和 264；Stage4 两个 joint 结果均确认多径。
- 这是当前最强的历史多径基准，但它来自 G06 专用 v1 实验。其功率和参数定义必须按该结果文件的归一化口径解释，不应直接当成绝对接收功率或外部真值。

### 7.2 G11：v2 pipeline 中确认能力最强的 PRN

- channel 5；结果目录为 sage_results/nav_sage_v2/G11。
- Stage0 覆盖充分：1177 个有效 symbol、1175 个窗口。
- Stage1 选 101 个候选；Stage2 有 56 个 L>=2、52 个 L>=3。
- Stage3 有 7 个可靠中心，Stage4 有 7 个 joint 结果；其中 6 个回落到 L=1，只有窗口 640 保留 L=2 并确认 1 条多径。
- 这说明 Stage2 高阶候选很多，但 Stage4 对短时或模型自由度导致的假象有强筛选作用。

### 7.3 G25：LOS/低多径参考

- channel 0；结果目录为 sage_results/nav_sage_v2/G25。
- Stage0 有 1177 个 symbol、1175 个窗口，覆盖充分。
- Stage1 有 52 个候选；Stage2 有 12 个 L>=2 模型。
- 没有候选满足 Stage3 持续性，因此没有 Stage4 输入和确认事件。
- 合适的表述是“按当前 Stage3/Stage4 标准未确认多径”，不能声称物理上绝对无多径。

### 7.4 G28：持续候选但 joint 回落到单径

- channel 1；结果目录为 sage_results/nav_sage_v2/G28。
- Stage0 有 900 个 symbol、898 个窗口；Stage1 有 54 个候选。
- Stage2 有 12 个 L>=2，其中 8 个 L>=3。
- Stage3 产生 2 个可靠中心，Stage4 也有 2 个有效 joint 结果，但两个结果最终均为 L=1、joint_multipath_count=0。
- 这是“局部窗口持续候选存在，但 100 ms 联合估计未确认多径”的典型对照。

Stage2、Stage3、Stage4 是不同证据层级，未来报告必须保留这种区别。

## 8. 当前已确认多径事件

确认定义仍是 joint_valid=1 且 joint_multipath_count>0。当前共 3 个确认事件、5 条确认多径路径。

### 8.1 事件级结果

| PRN | channel | 中心窗口 | recording time (s) | Stage2 L | Joint L | MP 路径数 | 最小 MP 功率 (dB) | 最大相对 Doppler (Hz) | 最大 coherence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| G06 | 4 | 203 | 41.8614130 | 2 | 4 | 3 | 6.902518 | 199.664302 | 0.332664 |
| G06 | 4 | 264 | 43.0814180 | 2 | 2 | 1 | 22.059548 | 159.664302 | 0.034598 |
| G11 | 5 | 640 | 50.5987615 | 3 | 2 | 1 | -7.407073 | 10.013107 | 0.828954 |

这些是算法意义上的 confirmed 事件，不等于已经经过外部场景真值验证。功率正负和量纲必须沿用各 pipeline CSV 的定义，不能脱离归一化约定做绝对物理解释。

### 8.2 路径级结果

| PRN | 窗口 | path | 超额时延 (samples) | 超额时延 (chips) | Doppler offset (Hz) | 相对功率 (dB) |
|---|---:|---:|---:|---:|---:|---:|
| G06 | 203 | 2 | 1.6 | 0.16 | 149.664302 | 18.192567 |
| G06 | 203 | 3 | 2.6 | 0.26 | 199.664302 | 6.902518 |
| G06 | 203 | 4 | 8.3 | 0.83 | 149.664302 | 7.104596 |
| G06 | 264 | 2 | 3.9 | 0.39 | 159.664302 | 22.059548 |
| G11 | 640 | 2 | 1.1 | 0.11 | -10.013107 | -7.407073 |

主要结果文件：

    # G06 windows 203 and 264
    scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/stage3_reliable_centers.csv
    scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/stage4_joint_summary.csv
    scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/stage4_joint_paths.csv

    # G11 window 640
    scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G11/stage3_reliable_centers.csv
    scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G11/stage4_joint_summary.csv
    scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G11/stage4_joint_paths.csv

G06 还保留 window 203/264 的专项 correlation、delay-power、stage2 DDM 和诊断图片；这些历史诊断不要移动到 v2 目录。

## 9. 关键脚本与文件用途

### 9.1 Preprocessing

| 路径 | 作用 | 主要输入 | 可能写入 |
|---|---|---|---|
| scripts/preprocessing/batch_prepare_navigation.py | 复制并校验 RINEX NAV/OBS 到标准入口；reference 只比较 | gnss_sdr/rinex/*.26N/.26O | navigation/、metadata、日志 |
| scripts/preprocessing/batch_prepare_trajectory.py | 复制并校验标准 NMEA；reference 只比较 | gnss_sdr/nmea/*.nmea | trajectory/、metadata、日志 |
| scripts/preprocessing/satellite_geometry.py | 公共 GSV 解析、NAV PRN 筛选、timeseries/summary 生成 | NMEA、navigation/rinex_nav | 调用方指定的 satellite CSV |
| scripts/preprocessing/batch_generate_satellite_geometry.py | 扫描所有 scene 并批量调用 geometry 算法 | scene navigation/NMEA | satellite/、metadata、批日志 |
| scripts/preprocessing/generate_dataset_inventory.py | 只读扫描输入和文件结构，生成 inventory | metadata、GNSS-SDR 日志、文件树 | dataset/dataset_inventory.csv |

preprocessing 脚本并非全部只读；执行前要确认写入范围。当前任务只做扫描，没有执行这些脚本。

### 9.2 SAGE 与验证

| 路径 | 作用 | 状态 |
|---|---|---|
| scripts/sage_pipeline/run_nav_sage_pipeline.m | 通用 scene + PRN + explicit channel 的 Stage0–Stage4 入口 | 当前主入口，仅支持 10.23 MHz |
| scripts/sage_pipeline/g06_nav_sage_pipeline.m | G06 历史专用 pipeline | 历史基线，保留，不通用化覆盖 |
| scripts/sage_pipeline/summarize_prn_validation.py | 读取 reference 已有 Stage0–Stage4 CSV，生成 PRN 汇总和报告 | 当前显式配置 G06/G11/G25/G28 |

summarize_prn_validation.py 虽然不修改 SAGE result 子目录，但会在 reference 的 sage_results/ 根目录生成/更新 prn_validation_summary.csv 和 prn_validation_report.md。因此执行前仍要检查输出和用户授权。

### 9.3 关键结果和文档

    docs/GNSS_SAGE_AGENT_HANDOFF.md       # 本文档，当前 AI Agent 优先阅读
    docs/GNSS_SAGE_PROJECT_HANDOFF.md     # 较早完整交接，作为补充背景
    docs/PROJECT_DATA_STRUCTURE.md         # 更早的数据结构快照，状态描述已过时
    dataset/dataset_inventory.csv         # 当前输入/channel inventory
    scenes/F1023_V70_D0117_P2/sage_results/prn_validation_summary.csv
    scenes/F1023_V70_D0117_P2/sage_results/prn_validation_report.md
    scenes/F1023_V70_D0117_P2/GNSS_SAGE_NAV_HANDOFF.md

## 10. 当前问题、限制与不确定信息

### 10.1 采样率

- 10.23 MHz：已验证可运行，samplesPerChip=10。
- 20.46 MHz：数据准备已完成，但通用入口在读取 metadata 后主动拒绝。尚未完成 samples/chip、samples/ms、延迟网格、搜索范围、raw 格式、性能和回归验证。
- 不得通过删掉 assert、改写 metadata 或硬改采样率检查来运行 20.46 MHz。

### 10.2 channel 选择

inventory 当前有 124 个可用 scene–PRN 组合，其中 5 个 PRN 在某 scene 有多个候选 channel。文件名只表明 channel，不保证唯一 PRN 映射。运行前必须：

1. 找到 inventory 对应的 scene 行；
2. 确认目标 PRN 在 available_prns；
3. 解析 prn_tracking_channel_map；
4. 只接受单候选 channel；
5. 检查该 channel 的 tracking MAT 和 telemetry DAT 都存在。

### 10.3 RINEX NAV 与 satellite geometry 的用途边界

当前 SAGE 使用 RINEX NAV 和 satellite CSV 作为标准化输入检查和运行上下文的一部分，但 Stage0–Stage4 并不直接使用广播星历重新计算卫星位置，也不从 satellite CSV 重新计算 SAGE 相对路径。不要把当前算法描述成“基于广播星历重算卫星位置的 SAGE”。

### 10.4 batch 化和资源

当前没有可安全直接运行全部 124 个组合的 batch runner。交接信息记录的单个完整 PRN 运行约需 35–73 分钟；Stage1/Stage2 计算和内存开销较大。后续批处理必须具备 dry-run 计划、输入校验、任务级 checkpoint、日志、失败隔离、资源上限、skip/resume 策略和预计耗时。

### 10.5 缺失的科学信息

当前项目没有外部多径真值、完整环境标签、统一事件数据库或最终统计模型。因此 Agent 不能凭空补充道路、建筑、反射面、真实多径标签或统计显著性结论。若需这些信息，应明确标记为待补充数据。

## 11. 下一阶段工作计划

按优先级建议如下。

### Phase A：完成 reference scene 剩余 PRN

当前 inventory 中 reference 的唯一映射为：

    G12 → channel 6
    G29 → channel 7
    G32 → channel 11

建议一次只运行一个 PRN，顺序可从 G12 开始。每次运行前检查目标目录是否已经存在，并先向用户报告 scene、PRN、channel、sampling rate、输入文件和输出路径。完成后需要有意识地扩展 summarize_prn_validation.py 的 PRN 配置；否则该工具会继续只报告 G06/G11/G25/G28。

### Phase B：设计多 scene batch SAGE runner

先实现只读 dry-run 规划，不直接循环全部 124 个组合。每个任务至少记录：

- scene_id、PRN、唯一 channel；
- sampling rate 和 pipeline 支持状态；
- raw/tracking/telemetry/trajectory/navigation/satellite 文件存在性；
- 输出目录是否存在及 context 是否匹配；
- skip、resume、error 策略；
- 任务耗时、日志位置和失败原因。

第一批只选择 10.23 MHz scene；20.46 MHz 必须等单独泛化和回归完成。

### Phase C：建立 multipath event 数据库

统一读取每个 scene–PRN 的 Stage0–Stage4 结果，至少生成：

- 输入和运行上下文；
- Stage0 覆盖率；
- Stage1 扫描与候选比例；
- Stage2 每种模型阶数及路径参数；
- Stage3 持续性和窗口范围；
- Stage4 joint 状态；
- confirmed 事件表和 confirmed 路径表。

必须保留 pipeline version、结果目录和证据层级，避免结果被压成一个无来源的“是否多径”字段。

### Phase D：关联仰角、CN0 和环境因素

以事件 recording time 或中心窗口时间匹配 satellite timeseries、tracking CN0 和 trajectory speed。NMEA SNR 与 tracking CN0 必须使用不同字段名。scene 的环境、道路和位置条件若当前没有文件，必须先建立明确的数据来源和 schema，不能猜测。

### Phase E：建立统计模型

在跨 scene 样本量足够后，统计：

- confirmed 事件发生率；
- 多径条数；
- 超额时延、相对 Doppler、相对功率；
- 持续时间和 Stage3→Stage4 确认率；
- scene、PRN、仰角、CN0、速度和环境条件的差异。

建模前要处理 scene 观测时长、可见 PRN、仰角覆盖和采样率不同造成的偏差。

### Phase F：20.46 MHz 泛化

单独验证：

- raw IQ 读取和数据类型；
- samples/chip、samples/ms、20/40/100 ms 长度；
- fast scan 与 SAGE 搜索网格；
- fractional-delay 单位；
- checkpoint/context 兼容性；
- 与 10.23 MHz 相同物理单位的输出；
- 内存、耗时和 reference regression。

## 12. AI Agent 工作规范

### 12.1 每次任务开始前

1. 读取本文件和目标相关的实际文件；
2. 运行只读目录扫描，不假设文档和文件系统完全同步；
3. 读取目标 scene 的 metadata.json；
4. 从 inventory 确认 sampling rate、raw 路径、PRN 和 channel；
5. 检查输入文件实际存在；
6. 检查输出目录、run_context.json/.mat 和 checkpoint；
7. 检查是否触及 reference 基线。

### 12.2 运行 SAGE 前

至少确认：

    metadata.json
    metadata.signal.sample_rate_hz == 10230000
    metadata.raw_iq.path exists
    gnss_sdr/tracking/<scene>_track_ch_<channel>.mat exists
    gnss_sdr/telemetry/<scene>_telemetry_ch_<channel>.dat exists
    trajectory/*.nmea 恰好一个
    navigation/rinex_nav/*.26N 恰好一个
    satellite/ 目录存在
    PRN→channel 映射唯一
    目标 output context 与当前任务一致或不存在

若任一检查失败，停止并报告具体原因；不能用自动猜测代替缺失信息。

### 12.3 禁止事项

- 不覆盖、移动、删除 G06_nav_sage_v1；
- 不修改 reference scene 的历史脚本、raw IQ、标准化输入或诊断文件；
- 不把普通 scene 的外部 IQ 批量复制进项目；
- 不修改 GNSS-SDR 原始解析结果；
- 不自动选择多候选 tracking channel；
- 不在当前 pipeline 上强行运行 20.46 MHz；
- 不把 Stage2 L>=2 直接计为 confirmed multipath；
- 不把 Stage3 可靠事件直接当作 Stage4 confirmed；
- 不把 satellite geometry 称为广播星历重算结果；
- 不凭空创建缺失的环境标签、真值或结果；
- 不因为默认 Resume=true 就盲目覆盖已有 checkpoint；
- 不在未获授权时运行会写 metadata、inventory、summary 或大量结果的脚本。

### 12.4 修改规范

如果用户要求改代码或增加结果：

1. 先列出会被修改或写入的精确路径；
2. 先保存/核对当前输入和基线状态；
3. 通过新的版本化输出目录或显式备份隔离实验；
4. 对小范围修改先做静态检查或 dry-run；
5. 运行后记录 pipeline version、参数、输入文件、耗时和输出；
6. 在最终报告中明确哪些是现有结果，哪些是新生成结果。

## 13. Current Status

当前项目阶段：**数据准备完成，正在进行 reference scene 的通用 SAGE 多 PRN 验证，尚未进入多 scene 批量和最终统计建模阶段。**

已经完成：

- 19 个 scene 标准目录建立；
- 19/19 GNSS-SDR 解析结果可用；
- 19/19 navigation 标准化；
- 19/19 trajectory 标准化；
- 19/19 satellite geometry CSV 生成；
- dataset inventory 生成，记录 124 个 scene–PRN 组合；
- 通用 run_nav_sage_pipeline.m 完成 scene/PRN/explicit channel 入口和 Stage0–Stage4；
- reference 的 G06 历史基线保留；
- reference 的 G11、G25、G28 v2 结果完成；
- 当前确认事件为 G06 window 203、G06 window 264、G11 window 640，共 3 个事件、5 条路径。

推荐下一任务：**先完成 reference scene 的 G12（channel 6）单 PRN 验证**。执行前必须做第 12.2 节完整检查，并确认 sage_results/nav_sage_v2/G12/ 是否已经存在。完成 G12 后，再按同样流程处理 G29 和 G32，最后有意识地扩展 reference PRN 汇总。不要直接启动 124 个任务，也不要在当前 pipeline 上运行 20.46 MHz scene。
> **状态迁移（2026-08-12）：** 本文件已转为历史参考。当前工程状态唯一来源是 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源是 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。
