# GNSS Multipath Project 数据结构说明

> 分析日期：2026-08-06  
> 本文档基于当前工作区的只读盘点生成。本文档本身是本次请求要求的输出；除新增本文档外，没有移动、复制或修改任何项目数据、代码、metadata、GNSS-SDR 结果或 raw IQ 文件。

## 1. 项目根目录

当前项目根目录为 `E:\GNSS_Multipath_Project`，一级目录如下：

```text
GNSS_Multipath_Project/
├── scenes/
├── dataset/
├── scripts/
├── configs/
├── docs/
└── full_parse_v1/
```

当前 `scenes/` 目录还包含：

```text
scenes/migration_report.csv
```

`dataset/`、`configs/`、`docs/` 当前没有其他已盘点的数据文件；`scripts/` 当前包含既有 SAGE 脚本目录和脚本文件。

## 2. scenes 总体情况

### 2.1 Scene 数量

当前共有 **19 个 scene**：

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
F2046_V30_D0131_P2
F2046_V30_D0131_P4
F2046_V30_D0203_P2
F2046_V60_D0129_P1
F2046_V60_D0129_P3
F2046_V60_D0202_P1
```

### 2.2 通用 scene 结构

除 reference scene 外，其余 18 个 scene 的一级结构一致：

```text
<scene_id>/
├── metadata.json
├── raw/
├── gnss_sdr/
├── navigation/
├── trajectory/
├── satellite/
└── sage_results/
```

reference scene `F1023_V70_D0117_P2` 的一级结构为：

```text
F1023_V70_D0117_P2/
├── metadata.json
├── raw/
├── gnss_sdr/
├── navigation/
├── trajectory/
├── satellite/
├── sage_results/
├── legacy_results/
├── generate_satellite_elevation.py
├── GNSS_SAGE_NAV_HANDOFF.md
├── g06_nav_sage_pipeline.m
├── analyze_G06_events.m
├── plot_G06_window203_correlation.m
├── plot_G06_window203_stage2_internal_ddm.m
└── plot_G06_window203_overlay.m
```

因此，统一结构已经基本建立，但 reference scene 仍包含模板脚本、交接文档和历史结果，属于有意保留的模板差异。

## 3. 主要目录语义

### `raw/`

raw IQ 的场景级记录目录。

- 18 个普通 scene：只有 `data_address.txt`，内容指向：

  ```text
  E:\AAGNSSSDR_input\raw_data\<scene_id>.bin
  ```

- reference scene：除 `data_address.txt` 外，还保留本地 `F1023_V70_D0117_P2.bin`。
- 当前 raw IQ 的实际统一存储策略是外部存储；reference scene 的本地 IQ 是模板历史遗留输入。
- 后续批处理不应通过 raw 路径读取 IQ，raw 仅作为路径和数据关联记录。

### `gnss_sdr/`

GNSS-SDR 解析结果目录。19 个 scene 均包含相同的一级子目录：

```text
gnss_sdr/
├── config/
├── logs/
├── tracking/
├── telemetry/
├── observables/
├── pvt/
├── rinex/
├── nmea/
├── metadata.json
└── run_status.json
```

其中：

- `config/`：GNSS-SDR 配置文件，每个 scene 1 个 `.conf`。
- `logs/`：GNSS-SDR 运行日志，每个 scene 1 个日志文件。
- `tracking/`：每个 scene 有 12 个 `.dat` 和 12 个 `.mat`，共 24 个 tracking 文件。
- `telemetry/`：各通道 telemetry、MAT 文件和 CRC 统计文件；数量随 scene 变化。
- `observables/`：每个 scene 1 个 `.dat` 和 1 个 `.mat`。
- `pvt/`：每个 scene 1 个 `.dat` 和 1 个 `.mat`。
- `rinex/`：GNSS-SDR 生成的 RINEX 文件。
- `nmea/`：GNSS-SDR 生成的 NMEA 文件。
- `metadata.json`、`run_status.json`：GNSS-SDR 批次、状态和源路径信息。

### `navigation/`

导航和观测 RINEX 的场景级整理目录，目标子结构为：

```text
navigation/
├── rinex_nav/
└── rinex_obs/
```

当前只有 reference scene 具备这两个子目录：

```text
navigation/rinex_nav/RINEXFILE.26N
navigation/rinex_obs/RINEXFILE.26O
```

其余 18 个 scene 当前没有 `navigation/rinex_nav/` 或 `navigation/rinex_obs/` 子目录；它们不是空的 RINEX 目录，而是尚未整理到该层级。

### `trajectory/`

场景级轨迹和位置相关派生输入目录。

- reference scene 有：

  ```text
  trajectory/F1023_V70_D0117_P2_trajectory.nmea
  ```

- 其余 18 个 scene 的 `trajectory/` 当前为空。
- 但所有 19 个 scene 都在 `gnss_sdr/nmea/` 中保留了一份同名 NMEA 输出。

### `satellite/`

卫星几何派生数据目录，不是原始输入。

当前 reference scene 已有：

```text
satellite/F1023_V70_D0117_P2_satellite_elevation_timeseries.csv
satellite/F1023_V70_D0117_P2_satellite_elevation_summary.csv
```

这类文件由 GNSS-SDR NMEA 与 RINEX NAV 二次生成。其长期扩展方向包括卫星仰角、方位角、SNR、可见性和分组统计等。

其余 18 个 scene 的 `satellite/` 当前为空。

### `sage_results/`

SAGE 多径处理结果目录。

- 只有 reference scene 当前含有：

  ```text
  sage_results/G06_nav_sage_v1/
  ```

- 该目录包含 stage0-stage4 的 CSV/MAT 结果、概览图和 diagnostics 诊断产物。
- 其余 18 个 scene 的 `sage_results/` 当前为空，表示尚未运行或尚未整理 SAGE 结果。

## 4. GNSS-SDR 结果实际位置

### 4.1 RINEX 文件

19 个 scene 的 GNSS-SDR RINEX 文件均实际位于：

```text
scenes/<scene_id>/gnss_sdr/rinex/
├── RINEXFILE.26N
└── RINEXFILE.26O
```

因此，`gnss_sdr/rinex/` 并非空目录，并且每个 scene 都包含 `.26N` 和 `.26O`。

需要区分：

- GNSS-SDR 原始输出位置：`gnss_sdr/rinex/`
- 场景标准导航整理位置：`navigation/rinex_nav/` 和 `navigation/rinex_obs/`

当前只有 reference scene 已完成第二种整理。

### 4.2 NMEA 文件

19 个 scene 的 GNSS-SDR NMEA 文件实际位于：

```text
scenes/<scene_id>/gnss_sdr/nmea/<scene_id>_trajectory.nmea
```

reference scene 另外还有：

```text
scenes/F1023_V70_D0117_P2/trajectory/F1023_V70_D0117_P2_trajectory.nmea
```

因此，后续批量 satellite geometry 生成器应优先读取 `gnss_sdr/nmea/`，不能假设所有 scene 都已经把 NMEA 复制到 `trajectory/`。

### 4.3 Tracking 文件

实际位置：

```text
scenes/<scene_id>/gnss_sdr/tracking/
```

每个 scene 均有：

- `<scene_id>_track_ch_0.dat` 至 `<scene_id>_track_ch_11.dat`
- `<scene_id>_track_ch_0.mat` 至 `<scene_id>_track_ch_11.mat`

合计 24 个 tracking 文件/scene。

### 4.4 Observables、PVT、Telemetry

实际位置和典型内容如下：

```text
gnss_sdr/observables/
├── <scene_id>_observables.dat
└── <scene_id>_observables.mat

gnss_sdr/pvt/
├── <scene_id>_pvt.dat
└── <scene_id>_pvt.mat

gnss_sdr/telemetry/
├── *_telemetry_ch_*.dat
├── *_telemetry_ch_*.mat
└── *_telemetry_crc_stats_ch*.txt
```

`telemetry/` 文件数量因 scene 的解析结果不同而变化；目录本身在 19 个 scene 中均存在。

## 5. 结构一致性检查

### 已一致部分

- 19 个 scene 都有根级 `metadata.json`。
- 19 个 scene 都有 `raw/`、`gnss_sdr/`、`navigation/`、`trajectory/`、`satellite/`、`sage_results/` 一级目录。
- 19 个 scene 的 `gnss_sdr/` 都包含 `config`、`logs`、`tracking`、`telemetry`、`observables`、`pvt`、`rinex`、`nmea`。
- 19 个 scene 的 `gnss_sdr/rinex/` 都有 `RINEXFILE.26N` 和 `RINEXFILE.26O`。
- 19 个 scene 的 `gnss_sdr/nmea/` 都有一个 NMEA 文件。
- 19 个 scene 都有卫星几何输出目录 `satellite/`。

### 当前差异

| 项目 | reference scene | 其他 18 个 scene | 影响 |
|---|---|---|---|
| `navigation/rinex_nav/` | 存在，含 `RINEXFILE.26N` | 子目录缺失 | 不能直接按标准导航路径批量读取 NAV |
| `navigation/rinex_obs/` | 存在，含 `RINEXFILE.26O` | 子目录缺失 | GNSS-SDR RINEX 尚未完成场景级整理 |
| `trajectory/` | 含 1 个 NMEA | 目录为空 | 不能把 trajectory 作为所有 scene 的 NMEA 输入入口 |
| `gnss_sdr/nmea/` | 含 1 个 NMEA | 含 1 个 NMEA | 是当前所有 scene 共同具备的 NMEA 入口 |
| `satellite/` | 含 2 个 CSV | 目录为空 | 只有 reference scene 有 satellite geometry 结果 |
| `sage_results/` | 含 `G06_nav_sage_v1` | 目录为空 | 只有 reference scene 有 SAGE 结果 |
| scene 根目录额外文件 | 有脚本、交接文档、legacy_results | 只有 metadata.json | reference scene 是开发模板，不是普通数据实例 |
| raw 内容 | 本地 `.bin` + 地址记录 | 只有外部路径记录 | raw 存储方式存在模板历史差异 |

### `navigation/rinex_nav/` 是否为空？

准确结论是：

- reference scene：存在且非空，包含 `RINEXFILE.26N`。
- 其他 18 个 scene：`navigation/rinex_nav/` 子目录目前不存在，不应描述为“空目录”。
- 所有 scene：`gnss_sdr/rinex/` 存在且包含 `.26N`、`.26O`。

## 6. 标准目标结构

建议以后将每个普通 scene 统一到以下语义结构：

```text
scenes/<scene_id>/
├── metadata.json
├── raw/
│   └── data_address.txt
├── gnss_sdr/
│   ├── config/
│   ├── logs/
│   ├── tracking/
│   ├── telemetry/
│   ├── observables/
│   ├── pvt/
│   ├── rinex/
│   └── nmea/
├── navigation/
│   ├── rinex_nav/
│   └── rinex_obs/
├── trajectory/
├── satellite/
└── sage_results/
```

语义约束：

- `raw/` 只记录外部 raw IQ 地址，不复制 IQ。
- `gnss_sdr/` 保留 GNSS-SDR 原始解析输出。
- `navigation/` 是供后续处理使用的场景级 RINEX 整理入口。
- `trajectory/` 存放轨迹或位置派生数据，不作为 GNSS-SDR NMEA 的唯一入口。
- `satellite/` 只存放由 NMEA、RINEX NAV 等输入派生的卫星几何数据。
- `sage_results/` 只存放 SAGE 及多径估计结果。
- 每个派生目录的状态以 metadata 为准，并区分 `not_prepared`、`not_generated`、`not_run` 和 `available/completed`。

reference scene 可继续保留其模板脚本、交接文档和实验诊断文件，不应强行压平为普通 scene 结构。

## 7. 推荐数据流

```text
外部 raw IQ
E:\AAGNSSSDR_input\raw_data\<scene_id>.bin
        │
        ▼
GNSS-SDR
        │
        ├── gnss_sdr/tracking/
        ├── gnss_sdr/telemetry/
        ├── gnss_sdr/observables/
        ├── gnss_sdr/pvt/
        ├── gnss_sdr/nmea/
        └── gnss_sdr/rinex/
                         │
                         ├── RINEX NAV 整理到 navigation/rinex_nav/
                         └── RINEX OBS 整理到 navigation/rinex_obs/
                                      │
                                      ▼
卫星几何派生
（gnss_sdr/nmea + navigation/rinex_nav）
                                      │
                                      ▼
satellite/
（仰角、方位角、SNR、可见性及统计结果）
                                      │
                                      ▼
SAGE 多径估计
（使用 GNSS-SDR 跟踪/遥测及 satellite geometry）
                                      │
                                      ▼
sage_results/
                                      │
                                      ▼
dataset/
（跨 scene 统计建模数据集）
```

当前实际状态是：GNSS-SDR 结果已经具备，但只有 reference scene 已完成 `navigation` 整理、satellite geometry 和 SAGE 结果；其余 18 个 scene 需要先补齐可用于导航处理的 RINEX 目录，再进入卫星几何和 SAGE 阶段。

## 8. 后续整理建议

1. 将每个 scene 的 `gnss_sdr/rinex/RINEXFILE.26N` 和 `RINEXFILE.26O` 作为导航整理候选，明确采用复制、链接还是登记引用的策略；不得破坏 GNSS-SDR 原始结果。
2. 为 18 个普通 scene 建立 `navigation/rinex_nav/` 和 `navigation/rinex_obs/` 的明确状态；“目录缺失”和“目录存在但为空”应在 metadata 中区分。
3. 批量 satellite geometry 生成器统一读取 `gnss_sdr/nmea/` 和 `navigation/rinex_nav/`，不依赖 `trajectory/` 是否已有 NMEA。
4. satellite geometry 成功后，只写入 `satellite/` 和 scene 根级 `metadata.json`，不读 raw IQ。
5. SAGE 批处理应把 `gnss_sdr/tracking/`、`gnss_sdr/telemetry/`、导航数据和 satellite geometry 作为显式输入，并为每个 scene 单独记录状态和错误。
6. 保留 reference scene 作为模板和回归验证样本；其根目录脚本、handoff 文档、diagnostics 和 `sage_results/G06_nav_sage_v1/` 不应被普通 scene 迁移流程覆盖。
7. 后续 dataset 构建应只消费 metadata 标记为 `available` 的派生数据，并保留来源路径和生成批次日志。

