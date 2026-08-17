# GNSS Multipath SAGE Project — Codex / AI Agent Handoff

> **历史文档：** 当前工程状态唯一来源为 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源为 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。本文件仅作历史审计参考。

**审计时点：** 2026-08-12（Asia/Shanghai）  
**项目根目录：** `E:\GNSS_Multipath_Project`  
**文档性质：** 基于当前文件、结果、日志、回执和脚本的只读交接基线。本文生成时没有运行 MATLAB、SAGE、raw-coarse 或新的 batch 任务，也没有修改已有 scene、metadata、inventory、`sage_results`、manifest、receipt、prototype 或 sampling 产物。

本文不是旧 handoff 的简单复制。若本文与旧文档、设计文档或某个旧计划数字冲突，以本文第 14 节规定的证据优先级处理。

## 0. 新 AI 接手时先读什么

新 Agent 首先应把当前状态理解为：

> 10.23 MHz 的 Pipeline V3 full-scan 已在 reference、Wave-A 和一个长场景 Wave-2A 任务上实际完成；Windows 正常用户执行链已通过 QA。`batch-sampled-v1/v1.1/A0` 离线采样均失败，最新 NumPy raw-coarse Phase-A G16 Retry1 虽然执行完成、覆盖回放为 100%，但三个 profile 都把全部窗口 promotion，因而生产筛选门禁失败。G25 raw-coarse 尚未运行，G11 raw-coarse 尚未运行，Wave-2A 剩余任务暂停，20.46 MHz 未适配。

接手后的默认动作不是重新 full-scan、调 v2 threshold、执行 G25/G11 或处理 20.46 MHz，而是先审计现有证据并设计下一版不泄漏 gold 的 coarse feature / risk screening。任何新实验必须建立新的版本化 namespace 和 immutable manifest。

### 当前不可违反的短规则

- 不能覆盖 reference scene 的任何已有结果，尤其不能覆盖 `G06_nav_sage_v1`。
- 不能修改现有 Pipeline V3、metadata、inventory、Stage0–Stage4 结果或已封存 prototype。
- `joint_valid=1 && joint_multipath_count>0` 才是当前 confirmed multipath 判据；Stage2 `L>=2`、Stage3 reliable center 和 coarse promotion 都不是 confirmed 标签。
- full-scan 结果中的未扫描/未晋级窗口不能被标为 LOS、rejected 或 no-event。
- 当前只允许讨论/验证 10.23 MHz；20.46 MHz 必须拒绝，不能因文件存在而运行。
- 任何 output directory 已存在时，默认 `new_only` 拒绝；不删除、不 resume、不截断 partial 输出。
- G25/G11 的新 raw-coarse execution 不得因为 G16 的“回放覆盖率通过”自动放行；Retry1 的全量 promotion 已证明当前 v2 不是生产筛选器。

## 1. 研究目标与最终路线

项目研究目标是从 GPS L1 C/A 原始复数 IQ、GNSS-SDR tracking/telemetry/observables 输出、RINEX NAV、NMEA 轨迹和卫星几何信息出发，构造 navigation-aided SAGE 处理链：

```text
raw IQ + GNSS-SDR
        │
        ├─ tracking / telemetry / observables / RINEX NAV
        ├─ NMEA trajectory
        └─ NMEA-GSV satellite geometry diagnostic
        │
        ▼
Stage0：NAV symbol 与完整 40 ms window 母集
Stage1：NAV wipe 后 fast correlation / residual candidate screening
Stage2：fractional SAGE，L=1..4
Stage3：跨窗口 persistence / reliable-center
Stage4：5-snapshot joint 100 ms confirmation
        │
        ▼
scene × PRN × tracking channel × window × path event database
        │
        ▼
按卫星仰角 LOW 0–30°、MID 30–60°、HIGH 60–90°，并可结合速度、CN0、场景/环境条件，建立参数化多径/信道统计模型
```

最终目标不是只列出若干“有反射”的窗口，而是建立可追溯的数据集和模型，至少统计：

- 多径发生概率与 coverage-complete 的 negative/no-confirmation 分母；
- confirmed event 的 path count；
- excess delay（samples/chips/后续可换算时间）；
- relative power；
- Doppler offset；
- coherence 与 persistence；
- 仰角分区以及可能的速度、场景和环境条件交互。

截至本审计时，event database 的 schema 仍是设计，统计模型尚未建立；不能把设计字段写成已入库数据。

## 2. 项目目录与真实数据集

### 2.1 顶层目录

当前顶层主要对象如下：

| 路径 | 实际用途/状态 |
|---|---|
| `scenes/` | 19 个标准化 scene；每个 scene 保存 metadata、GNSS-SDR 派生结果、navigation、trajectory、satellite geometry 和预留/已有 `sage_results`。|
| `scripts/preprocessing/` | navigation、trajectory、satellite geometry、inventory 的整理/生成脚本。|
| `scripts/sage_pipeline/` | Pipeline V3、legacy G06 pipeline、batch planner/executor、sampling planner、raw-coarse prototype、Windows wrapper 和测试。|
| `dataset/dataset_inventory.csv` | 当前 19 scene 的只读快照，包含 raw 路径/存储方式、PRN/channel map、输入存在性和 scene-level SAGE 状态。后续 SAGE 执行不会自动回写它。|
| `dataset_generation_logs/` | dry-run、batch 执行、sampling replay、raw-coarse prototype、Phase-A manifest/receipt/progress 的实验日志空间；不是 `sage_results`。|
| `docs/` | 设计文档、QA、诊断、hand-off 和论文材料索引。本文是当前时点新增的长期交接基线。|
| `full_parse_v1/` | 原始 GNSS-SDR 解析批次的派生结果来源，metadata 的 `migration/source_result_path` 和 `source_batch` 多指向此处。|
| `MATLAB_RUNTIME_CACHE_TEST/` | MATLAB 缓存重定向诊断遗留目录；不是 SAGE 结果，不要把它当作当前运行输出。|
| `configs/` | 当前为空，不能假设有未列出的运行配置。|

项目根目录当前不是 Git repository；不要依赖 Git status 判断实验是否安全，必须使用 manifest、hash、文件时间和输出 namespace。

### 2.2 19 个 scene、采样率和 raw 位置

`dataset/dataset_inventory.csv` 当前有 19 行 scene：13 个 10.23 MHz scene、6 个 20.46 MHz scene；18 个是 `standard_scene`，1 个是 reference。采样率和 raw 存储分布如下：

| 采样率 | scene |
|---|---|
| 10.23 MHz（`10230000`） | `F1023_V120_D0121_P2`, `F1023_v50_D0127_P1`, `F1023_V70_D0117_P2`（reference）, `F1023_V70_D0117_P4`, `F1023_V70_D0120_P1`, `F1023_V70_D0120_P5`, `F1023_V70_D0120_P7`, `F1023_V70_D0120_P8`, `F1023_V70_D0120_P9`, `F1023_V70_D0122_P1`, `F1023_V70_D0122_P2`, `F1023_V80_D0117_P8`, `F1023_v90_D0117_P7` |
| 20.46 MHz（`20460000`） | `F2046_V30_D0131_P2`, `F2046_V30_D0131_P4`, `F2046_V30_D0203_P2`, `F2046_V60_D0129_P1`, `F2046_V60_D0129_P3`, `F2046_V60_D0202_P1` |

标准 scene 的 `metadata.json` 中 `raw_iq.path` 通常是外部 raw，例如：

```text
E:\AAGNSSSDR_input\raw_data\F1023_V70_D0120_P7.bin
```

它们的 `storage_mode=external_storage`、`copied_into_scene=false`。reference scene 的 raw 已复制到 scene 内，`storage_mode=scene_local`、`copied_into_scene=true`。因此不能从 scene 目录是否出现 `.bin` 推测 raw 不存在；必须读取 metadata 的真实路径并再次 `Test-Path`/stat。

当前 metadata/stat 中记录的 raw 字节数（十进制）包括：

| scene | raw bytes（约） | 备注 |
|---|---:|---|
| `F1023_V120_D0121_P2` | 24,612,241,920 | 当前最大 raw；Wave-2A G11 使用它 |
| `F1023_v50_D0127_P1` | 3,882,222,080 | Wave-A G25 |
| `F1023_V70_D0117_P2` | 2,512,257,536 | reference，scene-local |
| `F1023_V70_D0117_P4` | 2,648,048,128 | external |
| `F1023_V70_D0120_P1` | 3,657,957,888 | external |
| `F1023_V70_D0120_P5` | 2,541,355,520 | external |
| `F1023_V70_D0120_P7` | 3,537,240,576 | Wave-A G16 |
| `F1023_V70_D0120_P8` | 2,493,841,920 | external |
| `F1023_V70_D0120_P9` | 3,405,578,752 | external |
| `F1023_V70_D0122_P1` | 2,491,810,304 | Wave-A G12 |
| `F1023_V70_D0122_P2` | 5,097,652,736 | external |
| `F1023_V80_D0117_P8` | 2,609,840,640 | external |
| `F1023_v90_D0117_P7` | 2,496,070,144 | external |
| `F2046_V30_D0131_P2` | 5,165,941,248 | 20.46 MHz，未适配 |
| `F2046_V30_D0131_P4` | 5,020,779,008 | 20.46 MHz，未适配 |
| `F2046_V30_D0203_P2` | 6,795,624,960 | 20.46 MHz，未适配 |
| `F2046_V60_D0129_P1` | 3,543,007,744 | 20.46 MHz，未适配 |
| `F2046_V60_D0129_P3` | 5,748,425,216 | 20.46 MHz，未适配 |
| `F2046_V60_D0202_P1` | 4,076,929,536 | 20.46 MHz，未适配 |

raw bytes 是路径/文件状态事实，不是可以直接用于性能归因的唯一变量。

### 2.3 单个 scene 的真实内部结构

典型目录为：

```text
scenes/<sceneId>/
├─ metadata.json
├─ raw/                         # 仅某些 scene/local migration 可能存在；raw 以 metadata 为准
├─ gnss_sdr/
│  ├─ tracking/                 # *_track_ch_<N>.mat
│  ├─ telemetry/                # *_telemetry_ch_<N>.dat
│  ├─ observables/              # 若该 scene 有 observables 派生物
│  └─ ...
├─ navigation/
│  ├─ rinex_nav/RINEXFILE.26N
│  └─ rinex_obs/...
├─ trajectory/
│  └─ <scene>_trajectory.nmea
├─ satellite/
│  ├─ <scene>_satellite_elevation_timeseries.csv
│  └─ <scene>_satellite_elevation_summary.csv
└─ sage_results/
   └─ nav_sage_v2/<PRN>/       # 仅已执行任务；不是每个 scene 都有
```

- `raw/`/scene-local raw：原始复数 IQ 的本地保存位置（并非所有 scene 都有）。
- `gnss_sdr/`：由 `full_parse_v1`/GNSS-SDR 解析得到的 tracking、telemetry、observables 等；tracking MAT 提供 channel/PRN、CN0、Doppler、code frequency、lock、TOW 等，telemetry DAT 提供 NAV bit/symbol 相关内容。
- `navigation/`：标准化的 RINEX NAV/OBS。当前 Pipeline 用 RINEX NAV 做目标 PRN/导航资料过滤和 provenance；并不在当前 geometry 代码中用广播星历重新计算卫星位置。
- `trajectory/`：标准化 NMEA，提供记录时间、RMC 速度以及 GSV 卫星观测上下文。
- `satellite/`：两个 geometry CSV，分别为时间序列和卫星摘要。当前主要由 NMEA GSV 解析得到 elevation/azimuth/SNR 诊断。
- `sage_results/`：只存正式 full-scan Pipeline V3 或 legacy 结果。sampling/raw-coarse 输出绝不能写入这里。

## 3. 数据准备与 GNSS-SDR 输入输出链

### 3.1 实际准备脚本和状态

实际存在的 preprocessing 脚本：

| 脚本 | 实际作用 |
|---|---|
| `scripts/preprocessing/batch_prepare_navigation.py` | 从 GNSS-SDR/迁移来源整理 RINEX NAV/OBS 到 scene 的 `navigation/`，保留源/输出 hash 和状态。|
| `scripts/preprocessing/batch_prepare_trajectory.py` | 整理/复制/规范化 NMEA 到 scene 的 `trajectory/`，保存来源与输出记录。|
| `scripts/preprocessing/batch_generate_satellite_geometry.py` | 批量调用 geometry 逻辑，为 scene 写两个 satellite CSV 和生成状态/receipt。|
| `scripts/preprocessing/satellite_geometry.py` | 从 NMEA GSV/轨迹等生成 elevation/azimuth/SNR 时间序列与摘要；包含时间匹配/diagnostic 逻辑。|
| `scripts/preprocessing/generate_dataset_inventory.py` | 只读扫描 scene、tracking/telemetry/raw/navigation/trajectory/geometry/SAGE 状态，生成 `dataset_inventory.csv` snapshot。|

19 个 scene 的 metadata 当前显示：GNSS-SDR `SUCCESS`、navigation `completed`、trajectory `completed`、satellite geometry `completed`。metadata 的 `processing_status.sage` 仅 reference 为 `completed`；其余 18 个是 `not_run`。这与后来已经产生的 Wave-A/Wave-2A `sage_results` 不矛盾，因为 inventory/metadata 是前期 snapshot，不会自动回写；以正式执行 receipt 和实际目录为准判断后来是否运行。

### 3.2 从 raw IQ 到 Stage0 的输入关系

1. GNSS-SDR 先对 raw IQ 做 tracking/telemetry/observables 解析。
2. 目标 channel 必须由 inventory/metadata 明确解析；有多 channel 映射时不能猜。
3. tracking MAT 与 telemetry DAT、NMEA 轨迹共同进入 Pipeline Stage0。
4. RINEX NAV 提供导航文件 provenance 和 PRN 过滤支持；目标 PRN 的 NAV symbol 仍需与 telemetry/tracking 对齐。
5. NMEA RMC/GSV 提供时间、速度和卫星观测上下文；Stage0 使用可用的速度和 Doppler bound 作输入门禁。
6. Stage0 生成完整有效 NAV symbol catalog 与完整 40 ms window 母集。后续 sampling 只能选择 Stage1 暴露集，不能删除 Stage0 母集。

### 3.3 geometry 的来源和限制

当前 satellite geometry 生成逻辑的关键事实：

- elevation/azimuth/SNR 主要来自 NMEA GSV；RINEX NAV 用途是 GPS PRN/导航过滤和 provenance。
- 当前代码不依据广播星历重新计算卫星位置；metadata 明确记录 `broadcast_ephemeris_position_recomputation=false`。
- 输出是 `<scene>_satellite_elevation_timeseries.csv` 和 `<scene>_satellite_elevation_summary.csv`。
- 旧 sampling planner 的简单 recording-time join 曾全部退化为 warning；v1.1 增加 TOW-aligned diagnostic 后，多数 reference/Wave-A/G11 任务可离线 verified，但这不是 Pipeline 的生产 window-level event geometry join。
- Wave-A G25 的 TOW diagnostic 仍有 fallback（报告记录 coverage 约 `.684`、p95 约 `16.612 s`）。
- 因此当前 Stage4 event 没有可以直接宣称为 production-grade 的逐事件 elevation/azimuth；event database 应保留 `geometry_join_status`, `geometry_time_delta`, `elevation_deg`, `azimuth_deg`, `snr_db` 及缺失原因，而不是用 scene/PRN summary 均值伪造。

## 4. Pipeline V3：接口、Stage0–Stage4 和确认语义

### 4.1 实际入口和输出 namespace

主入口是：

```matlab
run_nav_sage_pipeline(sceneId, PRN, ...,
    'TrackingChannel', channel, ...
    'ProjectRoot', 'E:\GNSS_Multipath_Project', ...
    'Resume', true_or_false)
```

当前代码文件 hash（本审计读取到的版本）：

```text
scripts/sage_pipeline/run_nav_sage_pipeline.m
SHA-256 = 5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab
```

`TrackingChannel` 必须显式提供，`ProjectRoot` 可显式提供，`Resume` 当前默认值为 true，但在安全 batch/wrapper policy 中新任务使用 `new_only`，已有目录或 partial 目录不得直接 resume。输出固定为：

```text
scenes/<sceneId>/sage_results/nav_sage_v2/<PRN>/
```

标准目标约 21 个文件，包括 `run_context.json/.mat`、Stage0 catalog/symbol/window CSV/MAT、`doppler_sign.mat`、Stage1 CSV/MAT/progress、Stage2 model/order/selected/path/MAT/progress、Stage3 persistence/reliable-center/MAT、Stage4 joint summary/paths/MAT 和 overview PNG。实际 QA 必须逐文件检查，不能只看目录存在。

当前 Pipeline 在代码中硬性限制 `sample_rate_hz=10230000`。20.46 MHz scene 即使 tracking、navigation 和 geometry 文件存在，也不能进入此入口；samples/chip、delay/Doppler grid、内存/运行时和 QA 都未适配。

### 4.2 Stage 参数与状态语义

| Stage | 输入 | 当前实际目的/关键参数 | 主要输出 | 语义 |
|---|---|---|---|---|
| Stage0 NAV catalog/window | tracking MAT、telemetry DAT、NMEA、raw/导航上下文 | 目标 PRN；有效 CN0 最低约 30 dB-Hz；carrier lock 约 `>= -0.5`；sample/TOW continuity tolerance；速度/Doppler bound 等门禁；由连续 NAV symbol 构造完整 40 ms window | `stage0_nav_catalog.mat`, `stage0_valid_symbols.csv`, `stage0_valid_40ms_windows.csv` | 全量母集和输入完整性基础；不是多径标签 |
| Doppler sign | raw IQ、tracking/Stage0 | 对 GNSS-SDR Doppler 符号做 raw correlation 校准 | `doppler_sign.mat` | 后续相关搜索的符号 provenance |
| Stage1 fast scan | raw IQ、Stage0 40 ms、NAV symbols | NAV wipe；main Doppler `-125:25:+125 Hz`；main delay `-5:10 samples`；局部 delay refine 约 0.2 sample、局部 Doppler ±30/10 Hz；residual delay main+1 到 +30 integer；residual Doppler step 50 Hz；residual separation >=2 samples、Doppler >=40 Hz；screen 约 -25 dB；最多 24 个 base、至少 8 个 fallback，并加 seed ±2 neighbor | `stage1_nav_fast_scan.csv/.mat`, `stage1_nav_progress.mat` | fast screening/candidate evidence；不是 confirmed |
| Stage2 fractional SAGE | Stage1 candidates | `L=1,2,3,4`；delay 0.1 sample（10.23 MHz 下约 .01 chip）；local delay ±.8 sample；Doppler ±30/5 Hz；10 iterations；tolerance 1e-6；path power >= -25 dB；coherence <= .98；BIC gain 10、RSS gain 0.002% 等 | `stage2_model_orders.csv`, `stage2_selected_windows.csv`, `stage2_selected_paths.csv`, `stage2_nav_sage_L1_L4.mat`, progress | `L>=2` 只表示当前窗口更偏好多分量模型，不等于多径 |
| Stage3 persistence | Stage2 selected fits | radius ±2；minimum consecutive 3；delay tolerance 1.5 samples；Doppler tolerance 40 Hz；power tolerance 10 dB；要求相关路径持续 | `stage3_persistence.csv`, `stage3_reliable_centers.csv`, `stage3_nav_persistence.mat` | persistent/reliable candidate；仍不是最终 confirmed |
| Stage4 joint 100 ms | Stage3 reliable centers、5 个相邻 20 ms snapshot | joint common geometry L1–L4；最多 8 centers；最多 8 iterations；至少 4 snapshots | `stage4_joint_summary.csv`, `stage4_joint_paths.csv`, `stage4_nav_joint_100ms.mat` | 当前 confirmed criterion：joint 有效且包含 multipath path |

当前项目的 confirmed criterion 是：

```text
stage4 joint_valid == 1
AND stage4 joint_multipath_count > 0
AND path table 中有对应 is_multipath=1 path
```

Stage4 summary 的 coherence 主要是 event/model-level 的 `maximum_coherence`；Stage4 path 的功率字段是 `mean_relative_power_db`。不要把它们误写成每条 path 都有独立 coherence。合法的 zero-event 结果可以只有表头的 Stage3/Stage4 CSV，只要 MAT、summary、receipt 和整条链路完整；这不是失败。

## 5. Reference scene 封存基线

### 5.1 基本信息与保护规则

Reference scene：`F1023_V70_D0117_P2`，GPS L1 C/A，10.23 MHz，raw scene-local。GNSS-SDR、navigation、trajectory、satellite geometry 已完成。权威封存报告：

```text
docs/reference_scene_final_validation_report.md       # scene-level封存报告
docs/GNSS_SAGE_PROJECT_HANDOFF_CURRENT.md             # 当前旧 handoff 中的汇总
scenes/F1023_V70_D0117_P2/sage_results/...             # 实际Stage文件
```

reference 的 G06 不能从 `nav_sage_v2/G06` 推测；历史结果在：

```text
scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/
```

`G06_nav_sage_v1` 是历史 legacy baseline，永久 protected。reference 的其他 v2 结果在 `nav_sage_v2/G11`, `G12`, `G25`, `G28`, `G29`, `G32`。任何实验不得覆盖、移动、重命名、删除或对这些目录 resume。

### 5.2 channel 和 Stage 统计

以下是从现有 reference Stage 文件和封存汇总核对得到的实际值。`Stage2 L1/L2/L3/L4` 是最终选择数量；每个 Stage1 candidate 仍尝试四个模型，因此模型评估总行数约为 candidate×4。

| PRN | channel | NAV symbols | 40 ms windows | Stage1 scan/candidate | Stage2 L1/L2/L3/L4 | L>=2 / L>=3 | Stage3 reliable | Stage4 joint | confirmed/path | 分类 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| G06 | 4 | 321 | 319 | 319 / 95 | 8 / 29 / 17 / 41 | 87 / 58 | 2 | 2 | 2 / 4 | confirmed；legacy v1 baseline |
| G11 | 5 | 1177 | 1175 | 1175 / 101 | 45 / 4 / 22 / 30 | 56 / 52 | 7 | 7 | 1 / 1 | confirmed |
| G12 | 6 | 1177 | 1175 | 1175 / 96 | 38 / 12 / 1 / 45 | 58 / 46 | 4 | 4 | 2 / 2 | confirmed |
| G25 | 0 | 1177 | 1175 | 1175 / 52 | 40 / 2 / 0 / 10 | 12 / 10 | 0 | 0 | 0 / 0 | LOS-like/low-multipath control |
| G28 | 1 | 900 | 898 | 898 / 54 | 42 / 4 / 5 / 3 | 12 / 8 | 2 | 2 | 0 / 0 | candidate/rejected by Stage4 |
| G29 | 7 | 1177 | 1175 | 1175 / 77 | 45 / 6 / 2 / 24 | 32 / 26 | 1 | 1 | 1 / 1 | confirmed |
| G32 | 11 | 1177 | 1175 | 1175 / 117 | 31 / 15 / 1 / 70 | 86 / 71 | 11 | 8 | 2 / 3 | confirmed |

Reference 最终有 8 个 confirmed event rows、11 条 multipath paths。分类必须保持：

- **G25：** LOS-like/low-multipath algorithmic control。它不是物理上绝对无反射的证明。
- **G28：** Stage2/Stage3 有候选，但 Stage4 的 joint 结果为 L1-only/`joint_multipath_count=0`，是拒绝案例。
- **G06/G11/G12/G29/G32：** 至少一个 Stage4 confirmed multipath 样本。

### 5.3 Reference confirmed event/path 参数

以下数值来自现有 Stage4 CSV/封存报告；G06 来源是 protected legacy 目录。coherence 为当前 event/model-level summary，不代表每条 path 的独立测量。

| PRN/window | time (s) | paths | excess delay samples/chips | Doppler offset (Hz) | relative power (dB) | coherence |
|---|---:|---:|---|---|---|---:|
| G06/203 | 41.8614130009775 | 3 | 1.6/.16；2.6/.26；8.3/.83 | +149.6643；+199.6643；+149.6643 | +18.1926；+6.9025；+7.1046 | .332664 |
| G06/264 | 43.0814179863148 | 1 | 3.9/.39 | +159.6643 | +22.0595 | .034598 |
| G11/640 | 50.598761485826 | 1 | 1.1/.11 | -10.0131 | -7.4071 | .828954 |
| G12/970 | 57.1917811339198 | 1 | 1.1/.11 | +24.4273 | -15.9205 | .577073 |
| G12/971 | 57.2117812316716 | 1 | 1.1/.11 | -0.5997 | -5.1136 | .886065 |
| G29/80 | 39.3959774193548 | 1 | 1.1/.11 | -5.3357 | -3.1518 | .869766 |
| G32/82 | 39.4369887585533 | 2 | 1.1/.11；2.5/.25 | +19.6643；-65.3357 | -11.3789；-19.5141 | .67738 |
| G32/84 | 39.4769889540567 | 1 | 1.1/.11 | +14.6643 | -8.8364 | .766091 |

这些是“已有确认结果”，不是下一版 sampling 的可用选择标签。gold 事件位置只能用于冻结规则后的后验 coverage replay，不能用于生产选 seed 或调参数。

## 6. Wave-A 和 Wave-2A 实际执行结果

### 6.1 Wave-A 三任务

权威文件：`docs/WAVEA_10MHz_VALIDATION_REPORT.md`、`docs/PILOT1_G16_QA_REPORT.md`、`docs/WAVEA_G25_QA_REPORT.md`、`docs/WAVEA_G12_QA_REPORT.md`。三项均由正常 Windows 用户 wrapper 执行，MATLAB/Python exit 0，21 个目标文件完整，Stage0–Stage4 链路和输出隔离 QA 通过。

| 任务 | channel | executor wall time | Stage0 NAV/windows | Stage1 | Stage2 eval/valid/selected | L1/L2/L3/L4 | L>=2/L>=3 | Stage3 rows/pass/reliable | Stage4 joint/valid | confirmed/path |
|---|---:|---:|---|---|---|---|---|---|---|---:|
| `F1023_V70_D0120_P7/G16` | 1 | 3913.123 s（约65.2 min） | 2231 / 2229 | 2229 valid，0 error | 416 / 340 / 104 | 20/34/17/33 | 84/50 | 167/39/11 | 8/8 | 4/4 |
| `F1023_v50_D0127_P1/G25` | 0 | 2724.903 s（约45.4 min） | 2343 / 2339 | 2339 valid，0 error | 424 / 259 / 106 | 106/0/0/0 | 0/0 | 0/0/0 | 0/0 | 0/0 |
| `F1023_V70_D0122_P1/G12` | 6 | 2949.653 s（约49.2 min） | 1631 / 1629 | 1629 valid，0 error | 428 / 356 / 107 | 21/17/12/57 | 86/69 | 212/65/11 | 8/8 | 3/3 |

Wave-A confirmed event：G16 有 windows 1337、1338、1406、2079 四个 Stage4 rows/四条 path；G12 有 windows 835、836、1278 三个 rows/三条 path；G25 没有 confirmed event 和 path 参数。G16 的 1337/1338 在当前输出中仍是两个独立 Stage4 rows，不能在没有额外 clustering 定义时强行合并成一个物理事件。

G25 的意义是同一执行链上的 LOS-like/low-multipath control：它完成了完整 pipeline、只有 L1 selected、没有 Stage3 reliable center、Stage4 无 multipath。它不是物理绝对 LOS 证明，也不能把 sampling 未扫描窗口自动当作 negative。

### 6.2 Wave-2A 长场景 G11

任务：`F1023_V120_D0121_P2/G11/ch0/10.23MHz`。结果路径：

```text
scenes/F1023_V120_D0121_P2/sage_results/nav_sage_v2/G11/
```

权威 QA：`docs/WAVE2A_G11_QA_REPORT.md`。

| 项目 | 实际结果 |
|---|---|
| Stage0 | 15,224 valid NAV symbols，15,210 个 40 ms windows |
| Stage1 | 全量 15,210 扫描，67 candidates；artifact 时间估计约 8 h 07 min 40 s |
| Stage2 | 268 model rows，258 valid，67 selected；L1/L2/L3/L4=`65/1/0/1`；L>=2=`2`，L>=3=`1`；约 11 h 26 min |
| Stage3 | 4 条 persistence path records，centers 9161 和 15065 均只出现单窗口，可靠 center=0 |
| Stage4 | 0 joint、0 multipath path、0 confirmed event；是完整合法空结果 |
| 总 executor wall time | 70,652.187 s，约 19.6 h；exit 0 |

相对 reference G11 的 1,175 windows，本任务约 12.94× 窗口，Stage1 wall time 约 17.7×。这暴露了吞吐和资源预算瓶颈；现有 QA 不能唯一断言根因是 raw I/O、外部存储、MATLAB 单线程、资源竞争或数据特征。G11 的 full-scan execution QA 是 PASS，但“允许继续 Wave-2A”是旧 QA 当时的执行结论；在 sampling v1/v1.1/A0 和 raw-coarse v2 production gate 失败后，当前路线已暂停 Wave-2A 剩余任务，不应引用旧文档的 GO 句子作为最新放行。

## 7. Batch 规划、执行和 Windows 边界

### 7.1 规划器和执行器

- `scripts/sage_pipeline/generate_batch_sage_plan.py`：读取 inventory，生成 scene–PRN task plan、输入完整性、multi-channel warning、已有结果状态和 report/issues；不运行 SAGE。
- 旧 dry-run 产物在 `dataset_generation_logs/batch_sage/batch_sage_dry_run_20260808T113252Z/` 与 `...113454Z/`，另有 `wave1_selected_tasks.csv`、`wave1_task_review.md`、`wave1_execution_dry_run_report.md`。
- 旧规划 review 使用 124 个 distinct scene–PRN task、25 blocked、5 multi-channel。当前 inventory 将多 channel 显式展开后为 130 个 channel-candidate task（见第 14 节冲突解释）。
- `scripts/sage_pipeline/run_batch_sage.py`：只接受选定 task/plan，支持 dry-run；执行时为每个任务独立构造命名参数 MATLAB 调用，单任务失败不终止其他 selected task，记录状态/时间/错误；已有 output 和 `G06_nav_sage_v1` 必须跳过/拒绝。
- 当前主 SAGE batch executor 是历史 full-scan executor，不等于 raw-coarse executor。

### 7.2 immutable request、hash 和输出安全

Windows request 固定 scene/PRN/channel/rate、输入路径、pipeline/executor hash、request SHA-256、`new_only` 和 output namespace。执行前必须：

1. 重新读取 inventory 和 metadata；
2. 重新确认唯一 channel 或拒绝 multi-channel 猜测；
3. 确认 raw/tracking/telemetry/navigation/trajectory/两份 geometry 存在；
4. 确认 sample rate=10.23 MHz；
5. 确认 output directory 不存在；
6. 重新计算 request SHA 和 source hash；
7. 创建全局 lock；
8. 执行后保存 environment/execution receipt、task log、status history、stdout/stderr、目标文件列表和 hash；
9. partial/failed/interrupted 只保留，不能自动删除或 resume。

### 7.3 为什么由正常 Windows 用户执行 MATLAB

历史 Wave1 直接由 Codex sandbox 身份 `tj-channel\codexsandboxoffline` 启动 MATLAB，五个任务在 Stage0 前失败，返回码 1，出现 `System Error: File system inconsistency`。MATLAB R2025a 的 preferences、TEMP/TMP 重定向和用户缓存诊断没有证明 sandbox 可用；正常 Windows 用户 `TJ-CHANNEL\Jing_` 能通过启动 smoke，且 Pilot/Wave-A 已完成。

曾出现过 smoke marker 输出成功但 MATLAB 退出码 3、`std::terminate`、`ddux.dll/mwddux_matlab.dll` 退出期 crash 的诊断记录；这不能被 marker 成功掩盖。wrapper 必须同时要求 marker 和 exit code 0。当前已实际通过的 Pilot/Wave-A 说明正常用户链可工作，不等于可以放宽 exit-code 门禁。

`scripts/sage_pipeline/Invoke-BatchSageWindows.ps1` 的安全边界是：

- 拒绝 Codex sandbox identity，要求正常用户且非管理员 PowerShell 7；
- 校验 request SHA、project-root containment、exact `scenes/<scene>/sage_results/nav_sage_v2/<PRN>` namespace；
- 拒绝 prefix collision、`nav_sage_v1`、错误 scene/PRN、`..` escape、20.46 MHz 和已存在 output；
- 检查 fixed Python path/object type、pipeline/executor/selection hash；
- 运行 MATLAB startup smoke；
- 建立 global lock；
- 将具体任务门禁和命名参数调用交给 `run_batch_sage.py`；
- 默认 validation-only，只有 `-Execute -ConfirmPilot` 才允许实际执行。

这条正常用户边界是工程事实，不是绕过安全检查的临时办法。

## 8. Sampling v1/v1.1/A0：已经失败，不能放行 sampled pilot

### 8.1 v1 和 v1.1

| 版本 | 实现/输出 | 实际离线结果 | 当前结论 |
|---|---|---|---|
| `batch-sampled-v1` | `generate_batch_sampling_plan.py`；`dataset_generation_logs/sampling_validation/batch_sampled_v1_offline_coverage/` | 11 个 gold task × 10 seeds；N0<=1200 时 full-scan-equivalent。reference 事件 coverage 100%；Wave-A G16 center recall 19/40=`47.5%`、±2 closure 10/40=`25.0%`；G12 center 16/30=`53.3%`、±2 closure 11/30=`36.7%`。| FAIL；未运行真实 sampled SAGE。|
| `batch-sampled-v1.1` | `generate_batch_sampling_plan_v1_1.py`；`.../batch_sampled_v1_1_offline_coverage/`，含 TOW-aligned diagnostic 和 11/21/31/41 blocks | 11 task × 10 seed × 多 block profile 的 hidden-row surrogate replay；budget sweep 到 4800 仍不能让 reference+Wave-A 所有 center/closure 跨 seed 达到 100%。geometry 改善未解决漏检。| FAIL；未运行真实 sampled SAGE。|
| A0 v1.2 | `generate_batch_sampling_plan_v1_2_a0.py`；`.../batch_sampled_v1_2_a0_offline/` | 只用 Stage0/tracking 低成本字段和允许的 geometry diagnostic；11 fixed task；gold selection false。15 个 known confirmed centers recall=`0%`，±2 closure=`0%`。| FAIL；不能作为 production promoter。|

核心逻辑错误不能简化为“guard 不够”：如果 event center 未进入初始暴露集，就不会产生 seed；之后再加 seed±2 不可能发现它。未扫描窗口只能是 `not_scanned`/`coverage_unknown`，不得是 LOS/no-event/rejected。

### 8.2 A0 当前 control 仅作为 promotion 行为观察

A0 的 control 输出曾报告：reference G25 约 27/1175 promoted、2 components；reference G28 约45/898、4 components；Wave-A G25 约118/2339、13 components；Wave-2A G11 约245/15210、20 components。它们只是 planner 行为和 coverage/provenance 记录，不是 false-positive 率，也不等于这些未 promotion/被 promotion 窗口已经被 SAGE 判为 LOS 或多径。

## 9. v1.2 raw-coarse prototype 的实际演化与当前结论

### 9.1 旧标准库 prototype（历史、不可当作当前性能）

`docs/BATCH_SAMPLED_V1_2_RAW_COARSE_PROTOTYPE_REPORT.md` 对旧 namespace `dataset_generation_logs/sampling_validation/batch_sampled_v1_2_prototype/` 的结果记录：

- G16 2229 windows，contiguous raw pass 约 18,806.16 s（5.22 h），历史 full Stage1 背景约 3900 s；旧实现明显更慢；
- 当时三个 profile 最终出现 2229/2229 promotion；G25 未完整完成，G11 未运行；
- 当时名为 D100/D200 的 profile 实际误用了约 ±1 Hz，不能拿来证明 ±100/±200 Hz 科学或性能结论；
- 该 namespace 只作历史诊断，不能覆盖或 resume。

### 9.2 compiled backend 和 NumPy alignment

现有可用 compiled backend 是另一个项目中只读使用的解释器：

```text
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe
Python 3.12.9 AMD64
NumPy 2.5.1
SciPy 1.18.0
OpenBLAS 0.3.33（receipt记录）
```

不允许联网安装、升级、复制该 venv 的 DLL/site-packages，也不修改该项目。审计报告：`docs/RAW_COARSE_COMPILED_BACKEND_AUDIT.md`。

旧 NumPy kernel 的 deterministic G16 microbenchmark 只有 6/12 一致，最大 score 差约 3.37 dB，不能归因于浮点噪声。`docs/RAW_COARSE_NUMPY_KERNEL_ALIGNMENT_REPORT.md` 记录了 root cause：B1 的两个 20 ms block 组合时，旧实现错误地把相同 halfwidth/family 的结果重复追加，导致 B1/B2-D100 的 block 语义交错；这引起 1.76–3.37 dB 差异以及 delay separation 3→2、4→2。

当前修复后的关键冻结值：

```text
parameter/alignment SHA-256:
41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2
kernel version: numpy-batched-complex128-v2-aligned
planner version: batch-sampled-v1.2-b1-b2-c1-prototype-v2-aligned
schema: batch-sampled-v1.2-raw-coarse-schema-3
prototype script:
scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2_v2.py
SHA-256: 959141371075c7f417f945dbe3f915f362a9337bb77582306f2b3ef16919ddfb
```

alignment deterministic test 的 tolerance 为 score `1e-8`、peak-ratio `1e-8 dB`、delay `0 sample`、Doppler `1e-8 Hz`；12/12 records、40/40 subblocks PASS，固定 microbenchmark 约 2.36× speedup。它证明 kernel 语义对齐和小 benchmark 通过，不证明 production selector 通过。

### 9.3 第一次 G16 formal Phase-A 中断

旧 manifest：

```text
dataset_generation_logs/sampling_validation/batch_sampled_v1_2_phase_a_execution_requests_20260812/phase_a1_g16_20260812/execution_manifest.json
SHA-256: bca6c592f3d107841f5b2e9459f48cfacb777cfc8cc28c779a91a0be4e70920c
```

旧 output：

```text
dataset_generation_logs/sampling_validation/batch_sampled_v1_2_phase_a_outputs_20260812/Phase-A1_F1023_V70_D0120_P7_G16_ch1/
```

receipt 为 `interrupted`，原因文本是 `KeyboardInterrupt`，exit code null；progress 显示 21 chunks、1680 windows 后中断，三个 profile 未完整生成。代码证据表明它走外部 `KeyboardInterrupt` 传播路径，不是 executor 独立 stall/total timeout（那些路径有不同的 reason 文本）；日志没有 PowerShell Ctrl+C、Windows signal 或宿主终止的直接证据。因此最保守分类是 `external_interrupt_likely / source unknown`，而不是断言一定是人工 Ctrl+C。该 partial namespace 只作诊断，绝不能当科学结果或 resume 来源。

### 9.4 G16 Retry1：执行成功但筛选失败

Retry1 manifest：

```text
id: phase_a1_g16_retry1_20260812
path: E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_retry_requests_20260812\phase_a1_g16_retry1_20260812\execution_manifest.json
SHA-256: 1f279208d8747a8639ce3599c8621f7a7f8a79e154eac01127f5956c49f6641d
```

output namespace：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_retry_outputs_20260812\Phase-A1-Retry1_F1023_V70_D0120_P7_G16_ch1\
```

receipt 实际记录：2026-08-12 03:51:09.803526Z 至 03:52:10.026973Z；exit 0、status completed、raw read ok；28 chunks、2229 windows；raw bytes `1,847,132,692`；raw pass wall time约 `59.1016 s`，executor wall约 `60.2234 s`，CPU约 `54.53125 s`。三个 profile 均在独立 raw-coarse namespace 生成 manifest/component/cost/coverage 文件，没有写 `scenes/**/sage_results`。

三个 profile 的后验 replay 和 promotion：

| profile | center recall | confirmed ±2 closure | Stage3 reliable-center closure | promoted/N0 | component |
|---|---:|---:|---:|---:|---:|
| B1 `20ms×2_D100` | 4/4=100% | 16/16 unique=100% | 44/44=100% | 2229/2229=100% | 1 |
| B2 `10ms×4_D100` | 4/4=100% | 16/16=100% | 44/44=100% | 2229/2229=100% | 1 |
| B2 `10ms×4_D200` | 4/4=100% | 16/16=100% | 44/44=100% | 2229/2229=100% | 1 |

G16 gold center 是 1337、1338、1406、2079；unique center±2 closure 为 16 个窗口；Stage3 reliable-center closure union 为 44。由于所有窗口都 promotion，coverage 100% 是平凡的全量保留，不是筛选能力。

score saturation 诊断：

- B1 score min约 `-15.087 dB`、median约 `-5.308 dB`；2178/2229 达到 high threshold `-10 dB`，其余 51 个经 bridge 被吸收。
- B2-D100 min约 `-8.410 dB`；所有窗口都高于 high threshold `-10 dB`。
- B2-D200 min约 `-8.714 dB`；所有窗口也都是 high seed。
- 当前 `coarse_score_db=max(subblock residual_proxy dB)`，B2 对四个 10 ms subblock 取 max；`peak_ratio_db` 与 score 同步。这个 proxy 的区分度不足，不应先调 threshold 来掩盖 score definition/feature 问题。
- B1 component artifact 中曾出现 `component_window_count=55,561`，但 distinct promoted window 只有 2229、component 数是 1；该字段是 component merge/overlap 展开的统计异常，不能当作实际母集数量。

因此 `docs/RAW_COARSE_PHASE_A_G16_RETRY1_QA_REPORT.md` 的正确结论是：执行完整性 PASS，gold replay PASS，production filtering FAIL。G25 raw Phase-A 尚未执行，G11 raw Phase-A 尚未执行。没有任何证据允许把当前 v2 作为 sampled SAGE promoter。

## 10. Event database 设计现状

设计文档是 `docs/MULTIPATH_EVENT_DATABASE_DESIGN.md`；目前没有正式 ingest 脚本、Parquet 数据集或统计模型。推荐的逻辑层次如下：

| 表/实体 | 作用 | 事实来源 |
|---|---|---|
| `runs` | scene、PRN、channel、rate、pipeline/prototype/hash、输入路径、执行回执、模式、sampling provenance | run_context、manifest、receipt |
| `window_evidence` | Stage0 全量 window、Stage1 scan/candidate、Stage2 selection、Stage3/4 status、coverage | Stage0–4 CSV/MAT；未扫描状态必须保留 |
| `model_evaluations` | window×L 的 RSS/BIC/valid/selected | `stage2_model_orders.csv` |
| `stage2_paths` | Stage2 候选路径及其 `estimate_stage=stage2` | `stage2_selected_paths.csv` |
| `candidate_events` | Stage3 persistence/reliable center | `stage3_persistence.csv`, `stage3_reliable_centers.csv` |
| `events` | Stage4 joint event、valid、joint multipath count、标签 | `stage4_joint_summary.csv` |
| `event_paths` | confirmed/LOS joint path 的 delay、Doppler、power、source coherence/provenance | `stage4_joint_paths.csv` |

标签建议：

- `confirmed_multipath`：Stage4 criterion 成立且 path 表 multipath 数量一致；
- `rejected_candidate`：必须有明确 Stage4 rejection evidence（例如 joint L1 且 multipath count 0）；Stage4 缺失/无效不能叫 rejected；
- `los_reference`/`los_like_control`：只有 coverage-complete 且有明确 reference/human/control provenance 才能用；G25 可作为 algorithmic control，但不能写成物理绝对 LOS；
- sampling 的 `not_scanned`, `coarse_not_promoted`, `inconclusive` 是 coverage/provenance 状态，不是事件标签。

每条 path 至少需要 `delay_samples`, `delay_chips`, `doppler_offset_hz`, `relative_power_db`，并保留 raw source field（如 `mean_relative_power_db`）。coherence/persistence 要区分 event-level 与 path-level来源。scene、PRN、channel、rate、window、time、elevation/azimuth/SNR、CN0、speed、environment 信息应通过 nullable foreign/provenance 字段关联；geometry join 失败必须保留 null 和 reason。

统计建模前必须保证 negative/no-confirmation 的分母 coverage-complete；sampling 未扫描窗口不能进入 negative denominator。

## 11. 当前已实现、已验证、失败和未开始状态矩阵

| 领域 | 当前状态 | 可写成“已验证”的范围 | 不得过度声称 |
|---|---|---|---|
| 19 scene 标准化 | `validated/completed` | GNSS-SDR、navigation、trajectory、satellite geometry 和 inventory 已生成 | geometry 不是星历重算，event-level join 尚未生产化 |
| Inventory | `validated snapshot` | 19 scene、rate、raw、PRN/channel、输入存在性可审计 | snapshot 不反映后来的 SAGE 输出；124/130 需按第14节解释 |
| Pipeline V3 10.23 | `validated/completed` | reference 7 PRN、Wave-A 3 task、Wave-2A G11 full-scan | 不支持 20.46；不代表全部 scene 已运行 |
| Reference | `validated/completed` | 7 PRN、8 confirmed rows、11 paths；G25/G28 控制/拒绝行为 | G06 legacy baseline 不可覆盖；不等于外部真值 |
| Windows batch 链 | `validated/completed` | normal-user wrapper、smoke、hash、lock、new_only、receipt、QA | 不能在 Codex sandbox 直接启动 MATLAB |
| Wave-A 10.23 | `validated/completed` | G16/G25/G12 3 task PASS，7 confirmed rows，G25 合法空结果 | 不能放行无门禁全量/20.46 |
| Wave-2A G11 full-scan | `validated/completed` | 15,210 windows、完整 exit0、0 confirmed、19.6h | 不能把旧 QA 的“继续执行”当作当前 sampling 放行 |
| `batch-sampled-v1` | `failed and frozen` | 只完成 offline replay | 未运行 sampled SAGE；未扫描不等于 LOS |
| `batch-sampled-v1.1` | `failed and frozen` | block/budget/TOW-aligned offline replay | 1200–4800 仍未通过；不能再简单加 budget |
| A0 v1.2 | `failed and frozen` | 11 task Stage0 feature planner/replay | center/closure recall 0%；不能作为唯一 promoter |
| raw-coarse stdlib prototype | `historical/failed and frozen` | 说明旧内核过慢、全量 promotion、Doppler labels 曾误用 | 不可用作当前 D100/D200 performance 结论 |
| NumPy aligned kernel | `validated kernel, production selector failed` | 12/12 alignment、40/40 subblock、fixed microbenchmark | 不能把 Retry1 的全量 promotion 当筛选成功 |
| G16 Phase-A Retry1 | `execution completed; research gate failed` | exit0、raw read、三 profile、回放 coverage | 2229/2229 promotion；G25/G11 不得自动运行 |
| Phase-A executor | `implemented, guarded` | manifest-only、dry-run、G16→QA→G25 policy、G11 reject、receipt/lock | 当前不自动判断研究 PASS，不自动启动下一 task |
| Event DB | `planned only` | schema/字段/ingest 设计 | 无正式数据库/Parquet/模型 |
| 10.23 扩展 | `paused` | 旧计划 61 候选、12 scene、Wave-2 requests 部分生成 | 不恢复 Wave-2A full-scan |
| 20.46 pipeline | `not started/blocked` | inventory 中确有 6 scene、41 old expansion task | 不得运行当前入口 |
| v1.2/v3 selector redesign | `not started` | 只有 seed-discovery/coarse design 和失败证据 | 不得声称有 multi-feature promoter |

## 12. 当前真实风险与研究限制

1. **算法正确性风险：** Stage2 高阶模型只是窗口级选择；G28、G11 证明高阶/单窗口候选不等于 confirmed。Stage3 persistence 和 Stage4 joint 仍是必要门禁。
2. **数据生产效率风险：** G11 15,210 windows 对应 Stage1 约8.1h、Stage2约11.4h；原因尚未被 profiling 唯一拆分。
3. **sampling 漏检风险：** v1/v1.1/A0 已实际失败；Retry1 raw-coarse 以全量 promotion 逃避漏检，不能称作筛选。
4. **score/feature 风险：** 当前 max residual proxy 对非事件窗口过于饱和；下一版必须做多 subblock consensus、secondary delay/Doppler stability、local contrast、persistence、B1/B2 agreement 等独立 feature 设计，不能对 gold 位置调 threshold。
5. **geometry 时间对齐风险：** NMEA GSV 与 window/TOW 的逐窗口关联尚未生产化；失败时必须 null，不得 summary mean 填充。
6. **20.46 MHz 风险：** samples/chip、delay grid、Doppler grid、内存、运行时和 output QA 全未适配。
7. **统计代表性风险：** 当前只有一个 reference scene、少量 Wave-A/Wave-2A 样本，无 external truth；confirmed/no-confirmation 标签会受 scene、仰角、CN0、环境和 coverage bias 影响。
8. **标签分母风险：** Stage4 zero-event 只有在完整链路/coverage 完整时才能成为 control；coarse-not-promoted 和未扫描窗口不能进入 negative denominator。

## 13. 不可破坏的安全约束

- 永久保护 `scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/` 及 reference 的所有 v2 PRN 结果。
- `scenes/**/sage_results/nav_sage_v2/<PRN>` 已存在时默认 `new_only` 拒绝；不覆盖、不 resume、不删除 partial。
- sampling/coarse 结果只能写 `dataset_generation_logs/sampling_validation/<new_version_namespace>/`，不能回写任何 `sage_results`。
- immutable request 必须有完整 manifest SHA-256、source hash、parameter hash、input receipt 和 exact output namespace。
- 任何 multi-channel task 必须人工选定并独立验证；不能从 channel candidates 猜。
- 20.46 MHz 当前入口硬拒绝；不能借用 10.23 MHz 参数。
- MATLAB 必须由 `TJ-CHANNEL\Jing_` 正常非管理员 PowerShell 7 执行；smoke marker 和 exit code 都必须通过。
- Codex sandbox 不能直接启动 MATLAB；不要用 sandbox 成功/失败替代正常用户 receipt。
- 任务级/全局 lock 必须是独占；lock 存在时停止，不要假设 stale 后自行删除。
- KeyboardInterrupt、stall、timeout、non-zero exit 必须写 interrupted/failed receipt，保留 artifact，不自动 resume/删除/启动下一任务。
- Stage2 `L>=2`、Stage3 reliable、coarse high score/promotion 都不能直接标为 multipath。
- Gold event/Stage3/Stage4 只能在 promoter、threshold、profile、manifest 完全冻结后用于离线 recall；生产选择必须 `gold_labels_used_for_selection=false`。
- 未通过独立 QA，不能生成/放行下一阶段 request；不能因旧文档的 PASS/GO 句子绕过最新 gate。

## 14. 证据优先级与已发现历史冲突

新 Agent 遇到数字冲突时，按以下顺序取证：

1. 实际 Stage0–Stage4 CSV/MAT、实际 output file list；
2. 同一次运行的 execution receipt、task log、progress、stdout/stderr；
3. 独立 QA report；
4. 最新 sealed/final validation report；
5. immutable manifest/request 及其 hash；
6. 当前 inventory/metadata snapshot；
7. design/planning docs；
8. 旧 handoff/daily handoff。

当前已识别的主要冲突/差异类型：

### 14.1 124 vs 130 task count

旧 `BATCH_SAGE_EXECUTION_READINESS_REVIEW.md` 和旧 handoff 以 124 个 distinct scene–PRN 任务为口径：13 个 10.23 scene 83 个任务、6 个 20.46 scene 41 个任务。当前 inventory 仍有 19 个 scene 行，但其中 5 个 scene–PRN pair 是 multi-channel，按实际 channel candidates 展开后为 130 个 task candidates，10.23 展开数为 89、20.46 仍为 41。应明确写成：**124 distinct scene–PRN；130 channel-expanded candidates**，不能把两者混成同一统计。

### 14.2 旧 83 vs 当前 inventory 89 的 10.23 口径

`WAVE2_10MHz_CONTROLLED_EXPANSION_PLAN.md` 是基于旧 124-task snapshot 的计划，写有 83 个 10.23、筛选后 61 个候选。当前 inventory 的 channel-expanded 口径是 89 个 10.23 candidates。61 是旧计划 snapshot 的 candidate pool，不是当前自动重算的正式 pool；不能无审计地把它更新成 61 或 60。

### 14.3 inventory 的 `sage_results_status` 与后来实际结果

inventory/metadata 是 preprocessing snapshot：inventory 记录除 reference 外多为 `not_run`，但 Wave-A/G11 后来在实际 `scenes/**/sage_results/nav_sage_v2/**` 已有结果。对于“是否运行”和结果状态，以执行 receipt、QA 和实际 Stage 文件为准；不要为了追求一致而修改 inventory。

### 14.4 旧 raw-coarse report vs Retry1

旧 stdlib prototype 报告的 5.22h、误用 ±1 Hz 和全量 promotion，不代表当前 aligned NumPy kernel。当前 Retry1 使用真实 ±100/±200 Hz profile、alignment hash `41d3...798ed2`，raw pass 约60s，但仍 2229/2229 promotion。因此性能改善和筛选失败必须分开记录。

### 14.5 sampling geometry diagnostic vs production geometry

v1 的 recording-time join warning、v1.1 的 TOW-aligned offline diagnostic 和当前 SAGE event-level geometry 不是同一层级。TOW diagnostic 的 offline verified 不能写成 Pipeline 已生产集成；G25 fallback 更不能被忽略。

### 14.6 旧 Wave-2A “允许继续” vs 当前暂停

`WAVE2A_G11_QA_REPORT.md` 在 G11 full-scan 执行完成时给出受控继续的 QA 结论；其后 sampling v1/v1.1/A0 和 raw-coarse Retry1 证明 production acceleration gate 未通过。当前更晚的 handoff/QA 结论是暂停剩余 Wave-2A，不恢复 full-scan。

### 14.7 B1 component count anomaly

Retry1 B1 `promotion_components.csv` 的 `component_window_count=55,561` 与 distinct window manifest 的 2,229 不一致；应把它当作组件展开统计异常，不能当作 55,561 个 Stage0 窗口，也不应在本 handoff 中修改该 artifact。

## 15. 关键文件和建议最小读取顺序

### 15.1 主代码和测试

```text
E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m
E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_batch_sage.py
E:\GNSS_Multipath_Project\scripts\sage_pipeline\Invoke-BatchSageWindows.ps1
E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_batch_sampling_raw_coarse_v1_2_v2.py
E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_raw_coarse_phase_a.py
E:\GNSS_Multipath_Project\scripts\sage_pipeline\generate_batch_sampling_plan.py
E:\GNSS_Multipath_Project\scripts\sage_pipeline\generate_batch_sampling_plan_v1_1.py
E:\GNSS_Multipath_Project\scripts\sage_pipeline\generate_batch_sampling_plan_v1_2_a0.py
E:\GNSS_Multipath_Project\scripts\sage_pipeline\summarize_prn_validation.py
E:\GNSS_Multipath_Project\scripts\sage_pipeline\test_run_raw_coarse_phase_a.py
E:\GNSS_Multipath_Project\scripts\sage_pipeline\test_run_batch_sampling_raw_coarse_v1_2_v2.py
```

当前关键 source hash：

```text
run_nav_sage_pipeline.m                         5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab
run_batch_sage.py                               3d4856bdc74d169346ab10f99bf2e7cf94f825e2c835ab8ad76d9ed1d48bddb9
Invoke-BatchSageWindows.ps1                     bed851a978ac9f03d69ddb2dee1e7b0d458424fed6fafffc3d7473e7676b616
run_batch_sampling_raw_coarse_v1_2_v2.py        959141371075c7f417f945dbe3f915f362a9337bb77582306f2b3ef16919ddfb
run_raw_coarse_phase_a.py                        e87f382db0f7c611926d529eb594f99c6e48713a5c4c76ca10eba58f5cbd7b42
generate_batch_sampling_plan_v1_2_a0.py         0953dd1be9b607a9f7ee306bc02953b38d8e882aa14dc22ba7c3e0ba572bd4c
```

`run_nav_sage_pipeline.m` 的 hash 不得在继续实验前默认仍然相同；每次 immutable request 需重新核验。

### 15.2 关键 docs

```text
docs/GNSS_SAGE_PROJECT_HANDOFF_CURRENT.md
docs/reference_scene_final_validation_report.md
docs/WAVEA_10MHz_VALIDATION_REPORT.md
docs/PILOT1_G16_QA_REPORT.md
docs/WAVEA_G25_QA_REPORT.md
docs/WAVEA_G12_QA_REPORT.md
docs/WAVE2A_G11_QA_REPORT.md
docs/MULTIPATH_EVENT_DATABASE_DESIGN.md
docs/BATCH_SAMPLED_V1_OFFLINE_COVERAGE_REPORT.md
docs/BATCH_SAMPLED_V1_1_OFFLINE_COVERAGE_REPORT.md
docs/BATCH_SAMPLED_V1_2_A0_OFFLINE_COVERAGE_REPORT.md
docs/BATCH_SAMPLED_V1_2_SEED_DISCOVERY_DESIGN.md
docs/BATCH_SAMPLED_V1_2_RAW_COARSE_PROTOTYPE_REPORT.md
docs/RAW_COARSE_NUMPY_KERNEL_ALIGNMENT_REPORT.md
docs/RAW_COARSE_PHASE_A_EXECUTION_READINESS.md
docs/RAW_COARSE_PHASE_A_EXECUTOR_IMPLEMENTATION.md
docs/RAW_COARSE_PHASE_A_G16_INTERRUPTION_DIAGNOSTIC.md
docs/RAW_COARSE_PHASE_A_G16_RETRY1_QA_REPORT.md
docs/WAVE2_10MHz_CONTROLLED_EXPANSION_PLAN.md
```

### 15.3 新 Agent 的最小安全读序

1. 本文；
2. `dataset/dataset_inventory.csv` 和目标 scene `metadata.json`；
3. `run_nav_sage_pipeline.m` 的 interface、sample-rate assert、Stage 参数；
4. `reference_scene_final_validation_report.md` 与 reference 实际 Stage4 CSV；
5. 三个 Wave-A QA 和 `WAVE2A_G11_QA_REPORT.md`；
6. 最新 `RAW_COARSE_PHASE_A_G16_RETRY1_QA_REPORT.md`、Retry1 receipt/progress/profile manifests；
7. sampling 三份 FAIL report；
8. raw-coarse alignment report、Phase-A executor code/implementation；
9. 只有在上述状态理解后，才读 design docs 规划新工作；不要先读旧 handoff 并据此执行。

## 16. 论文可直接使用的材料边界

以下是截至当前能够写入论文的事实，分为“已有数据支撑”和“必须等待后续实验”。

### Introduction / Motivation

**可写：** GNSS raw IQ 多径参数提取需要区分 window-level candidate 和 persistent/joint event；最终目标是 elevation-conditioned channel model。  
**仍需等待：** 现有 confirmed event 数量不足以代表环境总体分布，不能宣称普适模型。

### System and Data Acquisition

**可写：** 19 scenes、GPS L1 C/A、13 个 10.23 MHz、6 个 20.46 MHz；raw external/local 规则；scene metadata 和 inventory 结构。  
**来源：** `dataset/dataset_inventory.csv`、各 scene `metadata.json`。  
**仍需等待：** 20.46 MHz 处理与跨采样率比较。

### GNSS-SDR Preprocessing

**可写：** tracking MAT、telemetry DAT、RINEX NAV、NMEA trajectory、NMEA-GSV geometry 的作用和标准化流程。  
**重要限定：** elevation/azimuth 当前来自 GSV 诊断，未做广播星历位置重算；window-level event join 尚未生产化。

### SAGE Multipath Estimation Method

**可写：** Pipeline V3 的 Stage0–Stage4、Stage1 grid、Stage2 L1–L4 fractional delay/Doppler、Stage3 persistence、Stage4 joint criterion。  
**来源：** `run_nav_sage_pipeline.m`、reference/Wave-A/G11 Stage CSV/MAT。  
**不能写：** `L>=2` 直接等于 multipath。

### Reference Validation

**可写：** 一个 reference scene、7 PRN、8 confirmed event rows、11 paths；G25 control、G28 rejected-by-Stage4、G06/G11/G12/G29/G32 confirmed。  
**来源：** reference final report、7 个 output dirs、Stage4 CSV。  
**限定：** G06 是 protected legacy v1，不能声称它是与其他 PRN 完全同一 pipeline 版本。

### Batch Execution and Reproducibility

**可写：** immutable request → hash/preflight → normal-user PowerShell wrapper → MATLAB smoke marker+exit0 → Python executor → 21-file QA；Wave-A 三任务实际 PASS。  
**来源：** request、environment/execution receipt、task logs、QA docs。  
**限定：** Codex sandbox MATLAB 失败；正常用户边界是复现条件的一部分。

### Runtime Scalability Observation

**可写：** reference G11 1,175 windows 与 Wave-2A G11 15,210 windows；Stage1约8.1h、Stage2约11.4h、总约19.6h；窗口约12.94×、Stage1时间约17.7×。  
**不能写：** 不能把某个单一 I/O/CPU 原因当作已证明根因。

### Sampling Acceleration Design

**可写：** v1/v1.1/A0 的硬失败证据；v1.2 raw-coarse contiguous read、NumPy kernel alignment、Retry1约60s raw pass。  
**必须同时写：** Retry1 三个 profile 2229/2229 promotion，filter gate FAIL；不能把 100% replay recall 当作有效加速筛选。

### Limitations

**已有证据：** 单场景 reference、Wave-A/Wave-2A 样本少；无 external truth；geometry join 不生产化；sampling 漏检；20.46 未适配；event DB/model 未实现；环境标签不完整。  
**未来需要：** 新 feature/coarse prototype 的无 gold leakage recall、成本、false-promotion 行为和跨场景验证。

## 17. 建议从现有文件直接制作的论文图表

| 图/表 | 内容 | 原始来源 |
|---|---|---|
| 总体流程图 | raw IQ → GNSS-SDR → preprocessing → Stage0–4 → event DB/model | `run_nav_sage_pipeline.m`、preprocessing scripts、本文第1/4节 |
| 数据目录/处理流程图 | scene 内 raw/gnss_sdr/navigation/trajectory/satellite/sage_results | `metadata.json`、`PROJECT_DATA_STRUCTURE.md` |
| Stage decision funnel | Stage0 windows → Stage1 candidates → Stage2 L orders → Stage3 reliable → Stage4 confirmed | reference 7 PRN Stage CSV、Wave-A QA、G11 QA |
| reference PRN comparison table | channel、N0、L distribution、Stage3/4、confirmed/path | `reference_scene_final_validation_report.md`、各 `sage_results` |
| Wave-A validation table | G16/G25/G12 runtime、21-file QA、confirmed/zero-event | `docs/WAVEA_10MHz_VALIDATION_REPORT.md` |
| G11 scalability figure | windows、Stage1/Stage2 wall time、reference vs long scene | `docs/WAVE2A_G11_QA_REPORT.md`、progress/artifact timestamps |
| confirmed delay/Doppler/power example | reference 8 events/11 paths，Wave-A 7 events/7 paths | `stage4_joint_summary.csv`、`stage4_joint_paths.csv` |
| sampling replay coverage figure | v1/v1.1/A0 per-seed center/closure recall | `dataset_generation_logs/sampling_validation/...`、三份 coverage report |
| raw-coarse performance/selection figure | stdlib旧 prototype vs aligned NumPy Retry1；promotion fraction | `RAW_COARSE_NUMPY_KERNEL_ALIGNMENT_REPORT.md`、Retry1 profile `cost_measurement.json`/`coarse_window_manifest.csv` |

在论文中要把“execution/output QA PASS”和“sampling selector PASS”分别画/写；当前后者是 FAIL。

## 18. Current Status / DO NOT DO / NEXT SAFE ACTION

### CURRENT STATUS

- **已完成且有实际验证：** 19 scene 标准化、navigation/trajectory/geometry、inventory snapshot；10.23 MHz Pipeline V3 full-scan 的 reference 七 PRN、Wave-A G16/G25/G12、Wave-2A G11；Windows 正常用户 batch 链和 QA；NumPy v2 数值 alignment；G16 raw-coarse Retry1 的完整执行与后验 replay。
- **已完成但不可当生产能力：** batch planner/executor、sampling v1/v1.1/A0 offline planner、raw-coarse B1/B2/C1 prototype 和 task-aware Phase-A executor。它们的工程实现存在，但 selector gate 尚未通过。
- **当前失败/冻结：** v1、v1.1、A0 sampling coverage；Retry1 raw-coarse production filtering（全量 promotion）；第一次 G16 Phase-A partial interruption 只作历史诊断。
- **当前未开始或暂停：** v3 feature-based/coarse screening redesign、G25 raw-coarse Phase-A、G11 raw-coarse、Wave-2A 剩余 full-scan、event database ingest、LOW/MID/HIGH 统计模型、20.46 MHz adaptation。

### DO NOT DO

不要继续盲目 full-scan Wave-2A；不要运行 G25/G11 raw-coarse；不要把 Retry1 的 100% coverage 当作生产筛选通过；不要通过 gold event 窗口调 threshold、Doppler grid、bridge 或 block；不要修改现有 Pipeline、reference、inventory、metadata、Stage 结果；不要创建 20.46 request。

### NEXT SAFE ACTION

下一条安全工程任务应是：**基于 Retry1 的真实 score saturation 证据，设计并离线审计一个新的 v1.2/v3 oracle-free feature/coarse screening 版本**。它应全量读取 Stage0 的低成本字段或低成本 raw coarse evidence，冻结 feature/normalization/threshold/provenance 后再做 gold replay；必须同时追踪 center/±2 closure recall、promotion fraction、components、I/O、wall time 和 inconclusive。只有新 promoter 通过硬 coverage gate 且不是全窗口 promotion，才可设计独立 sampled namespace 和最小 pilot；在此之前不恢复 Wave-2A、不运行 G25/G11 raw-coarse、不处理 20.46 MHz。
> **状态迁移（2026-08-12）：** 本文件已转为历史审计参考。当前工程状态唯一来源是 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md)，当前论文状态唯一来源是 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](E:\GNSS_Multipath_Project\docs\GNSS_SAGE_PAPER_HANDOFF_CURRENT.md)。
