# GNSS_SAGE 工程状态唯一交接文档

**项目根目录：** `E:\GNSS_Multipath_Project`  
**工程状态唯一来源：** 本文件  
**最后审计时点：** 2026-08-18（Asia/Shanghai）
**面向对象：** Codex、AI Agent、开发人员、实验执行人员  
**当前阶段：** 从算法验证阶段进入论文数据生产阶段；当前主线是 accuracy-first full SAGE data production，已有6个10.23 MHz production task通过独立QA；G12 controlled acceptance、VTC Tier-1 T1-1 G05、T1-2 G25和T1-3 Mountain/Valley G11均已通过真实执行验收。根据 Commander 决策，SAGE production 当前已 STOPPED，转入 VTC evidence consolidation 和 event-level geometry/time-alignment QA。正式A3 G16仍因历史executor/request contract mismatch不计入production acceptance，其余任务保持 Planned / Not started。

> 本文只负责工程事实、文件、输入输出、执行、QA、hash、provenance 和下一步操作。论文科学叙事的唯一状态来源是 `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`。其他 handoff、设计稿、诊断稿和日报均为历史/专题参考，不再作为独立的当前工程状态源。

## 0. 状态词和证据优先级

严格使用以下状态：

- **Completed：** 已执行并完成，且有实际文件或回执支持；
- **Implemented：** 代码已实现，但不代表正式实验完成或生产门禁通过；
- **Validated：** 已通过明确的静态、单元、数值或实验 QA；
- **Planned：** 仅设计或计划，尚未执行；
- **Not started：** 尚未开始；
- **Failed / Frozen：** 已执行但门禁失败，artifact 必须保留，不得重写成成功。

发生冲突时按以下顺序取证：

1. 实际 `scenes/<scene>/sage_results` Stage CSV/MAT、`run_context`；
2. 同次 execution receipt、progress、stdout/stderr、task log、status history；
3. 独立 QA 报告；
4. immutable manifest、hash ledger、run manifest；
5. 当前 `dataset/dataset_inventory.csv` 和 scene `metadata.json`；
6. 设计文档；
7. 旧 handoff、daily handoff 和旧 summary。

inventory/metadata 是前期输入快照，不会自动回写后续 SAGE 执行状态；不能因为其中 `sage_results_status=not_run` 就否认实际存在且 QA 通过的结果。

## 1. 当前工程结论

### 1.1 已验证并可引用的工程事实

- 19 个 scene 已完成 GNSS-SDR 结果、navigation、trajectory、satellite geometry 标准化；`dataset/dataset_inventory.csv` 已生成。
- 当前 `run_nav_sage_pipeline.m` 的工程入口已通用化，可显式接收 `sceneId`、`PRN`、`TrackingChannel`、`ProjectRoot` 和 `Resume`；当前只允许 10.23 MHz。
- reference scene `F1023_V70_D0117_P2` 的 7 PRN full-scan 已完成并封存。
- Wave-A 10.23 MHz 的 G16、G25、G12 均完成 Windows 正常用户执行和独立 QA PASS。
- Wave-2A 长场景 `F1023_V120_D0121_P2/G11/ch0` full-scan 完成并 QA PASS，但暴露约 19.6 小时吞吐瓶颈。
- batch plan、dry-run、manifest/hash、normal-user PowerShell wrapper、MATLAB smoke、全局锁、new-only 和 QA 链已实际验证。
- v2 NumPy raw-coarse kernel 数值对齐 microbenchmark 已 PASS；这只证明 kernel 与 legacy/reference 语义一致，不证明 selector 有筛选能力。

### 1.1.1 当前路线决策

项目生产路线已从“优先开发 sampling/coarse selector 以降低 SAGE 计算量”调整为 **accuracy-first full SAGE data production**。当前论文数据生产主线为：

```text
raw IQ
  -> GNSS-SDR outputs
  -> Stage0
  -> Stage1
  -> Stage2
  -> Stage3
  -> Stage4
  -> confirmed event/path database
```

这不是全量批量完成声明；10.23 MHz production 已于 2026-08-13 由正常用户 wrapper 启动，当前已有六个任务通过独立 QA；Batch A representative `F1023_V70_D0120_P5/G16/ch1` 的历史执行仍因 executor/request contract mismatch 未通过 production acceptance，尚未计入 Completed；G12 controlled acceptance 已作为修复后真实验收任务通过并释放 Batch A，VTC Tier-1 T1-1 `F1023_V70_D0120_P9/G05/ch10`、T1-2 `F1023_V80_D0117_P8/G25/ch10` 和 T1-3 `F1023_v90_D0117_P7/G11/ch6` 也已完成并通过独立 QA，其他 production tasks 仍为 `Planned / Not started`。

### 1.1.2 首个正式 production task（Completed + QA PASS）

- 选择任务：`F1023_V70_D0117_P4/G11/ch2/10.23MHz`；production manifest task key 为 `F1023_V70_D0117_P4__G11`，Windows wrapper task id 为 `F1023_V70_D0117_P4__G11__ch2__nav_sage_v2`。
- 选择依据：Batch A 首个普通任务；inventory/metadata显示tracking channel唯一为2；raw路径存在且文件大小非零；tracking、telemetry、RINEX NAV、trajectory、两个geometry CSV均存在；目标`nav_sage_v2/G11`目录不存在；不是reference、completed或multi-channel blocked任务。
- production manifest保持不变：`dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json`，SHA-256=`77C20C0ED6C84FA0348DB429948A8BD4900B2E8D86A6D8843B159B9A7A35CF00`。
- immutable request：`dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a1_d0117p4_g11_20260812/execution_request.json`，SHA-256=`08a8865eb89e9301d33df09cf77fbe94ef9d452f75c4141162d63dcc6ffc68d7`。
- request同时冻结batch plan SHA=`a1b962acc43e0645620730f71d11086d0a08df8fe5bdcb45a8a14e3161347c20`、selected snapshot SHA=`5668125a7298f6d129fc9d1d59fd8c2c908a7b1dc6d89526eb1a2a593469a4f4`、pipeline SHA=`5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab`、executor SHA=`3d4856bdc74d169346ab10f99bf2e7cf94f825e2c835ab8ad76d9ed1d48bd9b9`以及wrapper SHA=`bed851a978ac9f03d69ddbb2dee1e7b0d458424fed6fafffc3d7473e7676b616`。
- 固定安全参数：`new_only=true`、`resume_allowed=false`、`max_parallel_matlab=1`、`sample_rate_hz=10230000`；输出只允许为`scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G11`。
- request preflight为`PASS_FOR_NORMAL_USER_WRAPPER; CODEX_EXECUTION_BLOCKED`。当前Codex身份为`tj-channel\\codexsandboxoffline`，不能运行wrapper；必须由非管理员`TJ-CHANNEL\\Jing_` PowerShell 7执行，MATLAB smoke marker和exit code均为0后才调用Python executor。
- 正式执行记录：`dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T013710Z/batch_execution_log.csv`；正常用户 receipt：`dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_production_10mhz_a1_d0117p4_g11_20260812_20260813T013455024Z/`。
- 正式输出：`scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G11/`；独立 QA：`docs/10MHz_FULL_SAGE_PRODUCTION_A1_G11_QA_REPORT.md`。
- QA 结论：`FULL_SAGE_PRODUCTION_TASK_STATUS=PASS`；Stage0 为 895 symbols/893 windows，Stage1 为 893 scanned/110 selected，Stage2 最终 L1/L2/L3/L4=`36/16/17/41`，Stage3 reliable centers=8，Stage4 joint=8，其中 confirmed events=3、confirmed multipath paths=3。
- MATLAB startup smoke marker 和 exit code 均通过；Python executor exit code=0；execution log 单任务 completed，task duration=`5078.854 s`。本次没有自动启动第二个任务。
- 首个 task 的 request、pipeline、executor、wrapper 和 production manifest hash 仍以 immutable request/receipt/QA 为准；production manifest 未修改。剩余 Batch A 任务必须重新生成独立 request、重新 preflight，并继续逐任务 QA。

### 1.1.3 Batch A第二个任务（Completed + QA PASS）

- 选择任务：`F1023_V70_D0120_P1/G18/ch2/10.23MHz`；这是规划文档中首个任务之后的下一个 Batch A 普通单channel任务。inventory映射唯一为 ch2，metadata/GNSS-SDR/navigation/trajectory/satellite geometry输入均存在，目标输出目录不存在。
- request namespace：`dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a2_d0120p1_g18_20260813/`。
- immutable request：`execution_request.json`，SHA-256=`ff2138044f45a39f578577600eeddac14e5419cd5c08d8bc60f7421e2a91c9fa`。
- request冻结production manifest SHA=`77C20C0ED6C84FA0348DB429948A8BD4900B2E8D86A6D8843B159B9A7A35CF00`、task record SHA=`7016a99f604bb13ef857c54f375fa6a0f0b64c48cb00cf77d198014dd1da12d7`、selection SHA=`c676961f356903c20516e12f7a6c83181118806d1286d3270de0ddd959a8fd9b`、pipeline/executor/wrapper hash以及inventory/plan hash。
- 安全参数：`new_only=true`、`resume_allowed=false`、`max_parallel_matlab=1`、`gold_labels_used_for_selection=false`；唯一输出为`scenes/F1023_V70_D0120_P1/sage_results/nav_sage_v2/G18`。
- request preflight：`PASS_FOR_NORMAL_USER_WRAPPER; CODEX_EXECUTION_BLOCKED`。当前Codex sandbox未运行MATLAB/SAGE/batch；正式执行由非管理员`TJ-CHANNEL\\Jing_` PowerShell 7完成，MATLAB smoke marker和exit code均通过。
- 正式执行记录：`dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T034529Z/batch_execution_log.csv`；正常用户 receipt：`dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_production_10mhz_a2_d0120p1_g18_20260813_20260813T034259453Z/`。
- 正式输出：`scenes/F1023_V70_D0120_P1/sage_results/nav_sage_v2/G18/`；独立 QA：`docs/10MHz_FULL_SAGE_PRODUCTION_A2_G18_QA_REPORT.md`。
- QA 结论：`FULL_SAGE_PRODUCTION_TASK_STATUS=PASS`；Stage0 为2611 symbols/2609 windows，Stage1为2609 scanned/115 selected，Stage2最终 L1/L2/L3/L4=`41/26/30/18`，Stage3 reliable centers=9，Stage4 joint=8且8/8 `joint_valid=1`；按严格 confirmed criterion，confirmed events=0、confirmed multipath paths=0。
- Python executor exit code=0，task exit code=0，task duration=`7737.82 s`。这是合法的完整 zero-event 输出，不作物理LOS结论；本次没有自动启动第三个任务。
- completed formal production count：`6/67` production manifest tasks（`F1023_V70_D0117_P4/G11/ch2`、`F1023_V70_D0120_P1/G18/ch2`、G12 controlled acceptance、VTC Tier-1 T1-1 `F1023_V70_D0120_P9/G05/ch10`、T1-2 `F1023_V80_D0117_P8/G25/ch10` 和 T1-3 `F1023_v90_D0117_P7/G11/ch6`均已完成并 QA PASS）；`F1023_V70_D0120_P5/G16/ch1`已有历史artifact但未通过production acceptance，production manifest未修改，其余任务仍为 `Planned / Not started`。

### 1.1.4 当前 Batch A representative task（Execution completed，contract QA REJECTED）

- 任务：`F1023_V70_D0120_P5/G16/ch1/10.23MHz`。
- immutable request：`dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a3_d0120p5_g16_20260813/execution_request.json`。
- request SHA-256：`629e22444baa3ae7cede6584ec486312cceb7be541e443eab4c30d53dfa8a094`。
- request preflight：`PASS — REQUEST_READY_FOR_HUMAN_EXECUTION`；该状态只表示可由人工wrapper执行，不表示SAGE已完成。
- 正常用户 `TJ-CHANNEL\\Jing_` 已完成一次wrapper执行；对应执行日志目录为 `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T073512Z/`，独立QA报告为 `docs/10MHz_FULL_SAGE_PRODUCTION_A3_G16_QA_REPORT.md`。
- 执行receipt和output artifact已保留在上述execution namespace；全局锁已释放。目标 `scenes/F1023_V70_D0120_P5/sage_results/nav_sage_v2/G16` 仅作为本次被拒收执行的历史artifact保留，不能由修复后的executor复用、覆盖或resume。
- 当前正式production完成数为 `3/67`；G16虽已生成执行artifact，但因executor/request contract mismatch未通过production acceptance，仍不得计入Completed；G12已通过修复后controlled acceptance和独立post-run QA。
- Stage0–Stage4 artifact completeness和科学字段检查通过，但独立production acceptance因contract mismatch REJECTED：immutable request冻结 `resume_allowed=false`，实际MATLAB invocation包含 `Resume=true`。本次不据此声称重新resume了checkpoint；合约违规本身足以拒绝接收。
- 旧immutable request及其manifest保持不变；修复后旧request因内嵌旧executor/wrapper hash而应当fail closed，不能复用、修改或resume现有G16输出。未执行重跑，也未启动下一任务。
- G16历史artifact仍不可复用、覆盖或resume；其production acceptance拒绝状态保持不变。修复后的G12 controlled acceptance已完成独立QA并释放Batch A。后续每个任务仍必须使用独立immutable `new_only` request、人工Windows wrapper、逐任务QA和summary更新，不得自动并行或跳过门禁。

### 1.1.5 修复后 Controlled Batch A acceptance：G12（Completed + QA PASS）

- 任务：`F1023_V70_D0117_P4/G12/ch4/10.23MHz`；request ID=`windows_production_contract_acceptance_d0117p4_g12_20260814`。
- immutable request：`dataset_generation_logs/batch_sage_execution_requests/production_10mhz_contract_acceptance_d0117p4_g12_20260814/execution_request.json`；SHA-256=`228c67b07fddc6526d320b45bf3495aa56854a478ff39c2fdc0ee6283b74edee`。
- 实际执行记录：`dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T024904Z/batch_execution_log.csv`；正常用户 receipt：`dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_production_contract_acceptance_d0117p4_g12_20260814_20260814T024639097Z/`。
- 独立 QA：`docs/10MHz_FULL_SAGE_PRODUCTION_CONTRACT_ACCEPTANCE_G12_QA_REPORT.md`；Execution Contract、New-only Policy、Artifact Completeness、Stage Consistency 和 Scientific Validity 均为 `PASS`。
- 真实 MATLAB command 已核对为显式 `Resume=false`，未发现 `Resume=true`；MATLAB smoke marker/exit code、Python executor exit code和task exit code均为0。运行时=`4205.951 s`。
- Stage统计：Stage0=`895` valid NAV symbols/`893` windows；Stage1=`893` scanned/`99` candidates；Stage2=`396` evaluations，L1/L2/L3/L4=`30/7/7/55`，L≥2/L≥3=`69/62`；Stage3 reliable centers=`15`；Stage4=`8` joint rows，8/8 `joint_valid=1`；confirmed events=`3`、confirmed paths=`3`。
- confirmed criterion仍严格为 `joint_valid=1`、`joint_multipath_count>0` 且 path表存在 `is_multipath=1`。这不是统计模型或完整event database完成声明。
- 现有summary已刷新至 `dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv` 和 `production_summary_report.md`，G12作为当前production manifest任务计入；避免与同一execution重复计数。
- **Batch A continuous production：`RELEASED`**。释放只表示后续任务可以按逐任务人工门禁继续，不表示可以并行、自动串行或跳过独立QA。

### 1.2 已实现但尚未生产放行

- batch executor、sampling planner v1/v1.1/A0、raw-coarse B1/B2/C1、Phase-A task-aware executor、v3 evidence/feature/ownership工具均已实现。
- G16 v3 evidence QA PASS：22,290 条 subblock evidence 覆盖 2,229 个 Stage0 windows；feature table 2,229 行；ownership revision 188 components、1,222 unique fine windows。
- v3 ownership/schema QA PASS，但后验 gold replay FAIL：confirmed center 2/4、confirmed +/-2 12/16、Stage3 reliable-center +/-2 25/44。因此 v3.0 不能作为 production selector，也不能据此放行 G25。

### 1.3 当前失败、暂停和禁止事项

- batch-sampled-v1、v1.1、A0 离线 coverage replay 均 FAIL；没有真实 sampled SAGE pilot。
- raw-coarse v2 G16 Retry1 三个 profile 都出现 2,229/2,229 promotion；计算快不等于筛选有效，production filtering gate FAIL。
- v3.0 posterior gate FAIL；完整定位为 `Implemented + QA Validated + Posterior Failed/Frozen`，是不可变的加速探索失败实验，不是production selector。
- v3.1设计暂缓，当前不作为论文数据生产的阻塞条件；不得为了恢复v3.1而延迟已验证full SAGE主线。
- G25 raw-coarse、G11 raw-coarse、sampled SAGE、Wave-2A 剩余 full-scan 暂停。
- 20.46 MHz 当前 Pipeline 入口硬拒绝；不得误跑。

## 2. 顶层目录和数据结构

| 路径 | 工程职责 | 当前状态 |
|---|---|---|
| `E:\GNSS_Multipath_Project\scenes` | 标准 scene、输入、geometry、正式 `sage_results` | 19 scene；已有结果受保护 |
| `E:\GNSS_Multipath_Project\scripts\preprocessing` | navigation、trajectory、geometry、inventory整理 | 已实现并完成19 scene标准化 |
| `E:\GNSS_Multipath_Project\scripts\sage_pipeline` | Pipeline V3、batch、wrapper、sampling、raw-coarse、QA测试 | 主工程代码 |
| `E:\GNSS_Multipath_Project\dataset` | inventory快照；未来数据库入口 | inventory已生成，event database未实现 |
| `E:\GNSS_Multipath_Project\dataset_generation_logs` | plan、request、receipt、progress、sampling/raw-coarse artifacts | 只读追溯和新版本namespace |
| `E:\GNSS_Multipath_Project\docs` | 工程/论文状态、设计、诊断、QA、历史handoff | 本文件和论文handoff为两个唯一当前源 |
| `E:\GNSS_Multipath_Project\full_parse_v1` | GNSS-SDR历史解析来源 | 作为source provenance |
| `E:\GNSS_Multipath_Project\MATLAB_RUNTIME_CACHE_TEST` | MATLAB缓存诊断目录 | 非SAGE输出 |

单个 scene 的标准结构：

```text
scenes/<scene_id>/
├── metadata.json
├── raw/                         # 仅scene-local或迁移场景可能有本地raw
├── gnss_sdr/
│   ├── tracking/                # *_track_ch_<N>.mat
│   ├── telemetry/               # *_telemetry_ch_<N>.dat
│   ├── observables/ pvt/ logs/ config/ ...
├── navigation/rinex_nav/        # RINEXFILE.26N等
├── navigation/rinex_obs/
├── trajectory/                  # <scene>_trajectory.nmea
├── satellite/                   # elevation timeseries/summary CSV
└── sage_results/
    └── nav_sage_v2/<PRN>/       # 仅正式full-scan结果
```

当前 dataset 口径必须区分：19 个 scene；13 个 10.23 MHz scene、6 个 20.46 MHz scene；124 个 distinct scene-PRN pair；部分 multi-channel 展开后约130个 channel-expanded candidates。旧计划中的83个10.23任务/61个候选是旧snapshot口径，不能与当前channel-expanded口径混用。

raw IQ 不能由目录名猜测。必须读取 scene `metadata.json` 的 `raw_iq.path` 和 `storage_mode`：reference raw 为 scene-local，其余多数为 `E:\AAGNSSSDR_input\raw_data\<scene_id>.bin` 外部文件。运行前重新验证路径、大小和hash。

## 3. 标准化和GNSS-SDR输入链

```text
raw complex IQ
  -> GNSS-SDR acquisition/tracking/telemetry/observables/PVT
  -> tracking MAT + telemetry DAT + RINEX + NMEA
  -> navigation/trajectory标准化
  -> NMEA-GSV geometry CSV + inventory
  -> SAGE Stage0-Stage4
  -> QA-approved event/path
  -> future event database and statistical model
```

关键脚本与输出：

| 脚本/输入 | 输出和用途 | 状态 |
|---|---|---|
| `scripts/preprocessing/batch_prepare_navigation.py` | `navigation/rinex_nav`、`rinex_obs`；保留source/output hash | Completed/Validated |
| `scripts/preprocessing/batch_prepare_trajectory.py` | 标准 trajectory NMEA | Completed/Validated |
| `scripts/preprocessing/satellite_geometry.py`、`batch_generate_satellite_geometry.py` | NMEA GSV派生 elevation/azimuth/SNR timeseries和summary | Completed/Validated |
| `scripts/preprocessing/generate_dataset_inventory.py` | scene、PRN/channel、输入存在性和warning | Completed/Validated |
| tracking MAT | CN0、carrier Doppler、code frequency、lock、TOW、channel映射 | SAGE核心输入 |
| telemetry DAT | GPS NAV symbol/catalog | Stage0核心输入 |
| RINEX NAV `.26N` | navigation provenance和GPS PRN过滤 | 不是当前geometry位置重算来源 |
| trajectory NMEA | RMC时间/速度、GSV上下文 | Stage0/geometry上下文 |

卫星几何的实际限制：elevation/azimuth/SNR主要来自 NMEA GSV；RINEX NAV 只用于GPS PRN/导航记录过滤；当前没有从broadcast ephemeris重新计算卫星位置。因此 summary elevation不能冒充窗口级瞬时elevation。TOW-aligned geometry diagnostic只属于offline诊断，尚未集成正式event-level生产join；失败必须保留null和reason。

## 4. Pipeline V3工程接口和输出

主入口：

```matlab
run_nav_sage_pipeline(sceneId, PRN, ...,
    'TrackingChannel', channel, ...,
    'ProjectRoot', 'E:\GNSS_Multipath_Project', ...,
    'Resume', true_or_false)
```

当前实际限制：

- `TrackingChannel` 必须显式冻结，multi-channel不自动猜；
- `ProjectRoot` 应显式传入；
- `Resume=true` 只代表匹配checkpoint的恢复能力，不是覆盖授权；batch生产使用`new_only`，目标目录必须不存在；production executor必须从immutable request显式传入 `Resume=false`，不能依赖MATLAB函数默认值；
- 代码硬性要求 `sample_rate_hz=10230000`；20.46 MHz不能进入此入口；
- 10.23 MHz下约10 samples/chip，Stage2 fractional delay 0.1 sample约0.01 chip。

Stage语义：

| Stage | 主要输入 | 工程输出 | 语义 |
|---|---|---|---|
| Stage0 | tracking MAT、telemetry DAT、trajectory | `stage0_valid_symbols.csv`、`stage0_valid_40ms_windows.csv`、catalog MAT | 全量window母集，不是多径标签 |
| Doppler sign | raw/tracking/Stage0 | `doppler_sign.mat` | Doppler符号provenance |
| Stage1 | raw、Stage0、NAV wipe | `stage1_nav_fast_scan.csv/.mat`、progress | screening/candidate，不是confirmed |
| Stage2 | Stage1 candidates | L1-L4 model/order/selected/path/MAT | `L>=2`只表示多分量模型选择，不等于多径 |
| Stage3 | Stage2 fits | persistence/reliable centers | 持续候选，不是最终确认 |
| Stage4 | Stage3 centers、100 ms snapshots | joint summary/paths/MAT | `joint_valid=1 && joint_multipath_count>0`，且path表有`is_multipath=1`，才是当前confirmed criterion |

标准正式结果目录通常应有21个目标文件。Stage3/Stage4只有表头的CSV可以是合法zero-event结果；目录存在或checkpoint存在本身不能证明任务完成。

## 5. 已完成正式full-scan实验和QA

### 5.1 Reference scene

`scene_id=F1023_V70_D0117_P2`，10.23 MHz，7 PRN，GNSS-SDR/navigation/trajectory/geometry均完成。实际Stage统计如下；L1/L2/L3/L4为最终选择数量：

| PRN | ch | NAV | 40ms | Stage1 scan/candidate | L1/L2/L3/L4 | L>=2/L>=3 | Stage3 | Stage4 | confirmed/path |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| G06 | 4 | 321 | 319 | 319/95 | 8/29/17/41 | 87/58 | 2 | 2 | 2/4 |
| G11 | 5 | 1177 | 1175 | 1175/101 | 45/4/22/30 | 56/52 | 7 | 7 | 1/1 |
| G12 | 6 | 1177 | 1175 | 1175/96 | 38/12/1/45 | 58/46 | 4 | 4 | 2/2 |
| G25 | 0 | 1177 | 1175 | 1175/52 | 40/2/0/10 | 12/10 | 0 | 0 | 0/0 |
| G28 | 1 | 900 | 898 | 898/54 | 42/4/5/3 | 12/8 | 2 | 2 | 0/0 |
| G29 | 7 | 1177 | 1175 | 1175/77 | 45/6/2/24 | 32/26 | 1 | 1 | 1/1 |
| G32 | 11 | 1177 | 1175 | 1175/117 | 31/15/1/70 | 86/71 | 11 | 8 | 2/3 |

保护规则：`scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/`是历史baseline，永久不可覆盖、移动、删除或resume；reference的G11/G12/G25/G28/G29/G32以及nav_sage_v2结果同样不可覆盖。

### 5.2 Wave-A 10.23 MHz

| Task | Stage0 NAV/windows | Stage1 | Stage2 selected / L1-L4 | Stage3 reliable | Stage4 confirmed/path | QA |
|---|---:|---|---|---:|---:|---|
| `F1023_V70_D0120_P7/G16/ch1` | 2231/2229 | 2229 valid | 104 / 20/34/17/33 | 11 | 4/4 | PASS |
| `F1023_v50_D0127_P1/G25/ch0` | 2343/2339 | 2339 valid | 106 / 106/0/0/0 | 0 | 0/0 | PASS |
| `F1023_V70_D0122_P1/G12/ch6` | 1631/1629 | 1629 valid | 107 / 21/17/12/57 | 11 | 3/3 | PASS |

三任务均由正常Windows用户执行，Python/MATLAB/executor退出状态、21文件、Stage链和输出隔离均通过QA；G25是同一执行链中的LOS-like/low-multipath control，不是物理上绝对无反射的证明。

### 5.3 Wave-2A G11长场景

任务：`F1023_V120_D0121_P2/G11/ch0/10.23MHz`。实际QA PASS：Stage0为15,224 NAV symbols、15,210 windows；Stage1扫描15,210、67候选；Stage2 268次L1-L4评估、67 selected，L1/L2/L3/L4=65/1/0/1；Stage3 reliable centers=0；Stage4 joint=0、confirmed=0。Stage1约8.1小时，Stage2约11.4小时，总耗时约19.6小时。它是有效zero-event结果，也暴露了当前full-scan生产效率风险；不能据此恢复剩余Wave-2A。

## 6. Batch执行和Windows环境

安全链：

```text
dataset_inventory.csv
  -> batch_sage_plan.csv/report
  -> selected_tasks.csv人工allowlist
  -> immutable execution_request.json + SHA256
  -> TJ-CHANNEL\Jing_正常用户PowerShell 7 wrapper
  -> identity/TEMP/MATLAB smoke/hash/lock/output preflight
  -> run_batch_sage.py
  -> MATLAB run_nav_sage_pipeline.m
  -> execution receipt/status/task log
  -> 独立QA
```

Codex sandbox用户无法稳定启动MATLAB；正常用户 `TJ-CHANNEL\Jing_` 可以启动。wrapper职责是身份检查、MATLAB startup smoke、request SHA、全局锁、output namespace和人工确认；SAGE安全规则仍只由`run_batch_sage.py`/manifest门禁负责，不在wrapper复制科学逻辑。MATLAB smoke要求marker和exit code=0，不得放宽。

当前不可绕过的执行规则：

1. 只接受immutable manifest和Expected SHA，不接受用户临时传入scene/PRN/raw绕过manifest；
2. `new_only`：目标目录存在即拒绝；中断artifact保留，不能删除、覆盖或自动resume；
3. 一次只执行一个批准任务，G16->独立QA->G25政策必须保持；G11 raw-coarse无条件拒绝；
4. 任何失败写`failed/interrupted receipt`，记录stdout/stderr、progress、hash和已有输出；不自动启动下一任务；
5. sampled/raw-coarse输出不得写入`scenes/**/sage_results`，必须使用独立版本namespace。

## 7. Sampling和raw-coarse当前工程状态

### 7.1 v1/v1.1/A0

- v1：稀疏/分层采样，Wave-A G16 event-center recall 47.5%、+/-2 closure 25.0%；FAIL。
- v1.1：连续block和adaptive +/-2/必要+/-5；1200至4800 budget sweep仍无法在seed_00至09稳定达到known center和closure 100%；FAIL。
- A0：仅Stage0/tracking/geometry低成本feature；11个gold task中confirmed center recall=0%、closure=0%；FAIL。

这些窗口未扫描/未晋级状态不能标LOS、rejected或no-event，只能表示coverage未覆盖或not_promoted。

### 7.2 v2 raw-coarse和NumPy alignment

旧标准库kernel过慢，曾约5.22小时；后续NumPy compiled kernel与legacy数值语义对齐，12/12 fixed microbenchmark通过，严格容差仍为score 1e-8、delay 0 sample等。G16 Retry1正式运行完成，但B1/B2三个profile均`2229/2229` promotion，故selector filtering FAIL。该结果不能与v3 posterior coverage混淆：v2 Retry1的“全覆盖”是全窗口晋级造成的，不是有效筛选。

### 7.3 v3 evidence/feature/ownership/posterior

v3 evidence QA和ownership/schema QA均已通过，但后验gold replay只做冻结union比较，不重建selector：

| 目标 | 覆盖 | Recall |
|---|---:|---:|
| Stage4 confirmed center | 2/4 | 50.0000% |
| confirmed center +/-2 | 12/16 | 75.0000% |
| Stage3 reliable-center +/-2 | 25/44 | 56.8182% |

gold前冻结物料：2,229 feature rows、188 components、1,222 unique fine windows、ownership schema `raw-coarse-v3-component-membership-1`。漏检解释仅使用冻结promotion reason：`secondary_doppler_inconsistent`和`cross_scale_disagreement`；不能据此反调参数。结论：`G16_V3_POSTERIOR_COVERAGE_PASS=false`，不能准备G25 v3 request。v3.0保留为 `Implemented + QA Validated + Posterior Failed/Frozen`，不进入production；v3.1当前暂停。

## 8. 当前关键hash和artifact

| 对象 | 路径/版本 | SHA-256或状态 |
|---|---|---|
| v3 parent scientific parameter | `dataset_generation_logs/sampling_validation/batch_sampled_v1_3_parameter_manifest_r6_20260812/v3_parameter_schema_manifest.json` | parameter=`3f6330f8c88b4901feda2e0cb9bd9e8dcd6350aec6270fd0d3985f5ca2669642`; manifest=`a83677564cbcf896c2bd2613a918b3efda7e7fdeeeb607e944822db356125d36` |
| ownership schema | `.../batch_sampled_v1_3_component_ownership_schema_20260812/ownership_schema_manifest.json` | schema=`29e557d330fd2b510360ea3bb30a286088032b1a44eb4cb76fe5dc94da4929de`; manifest=`1dae14dbdbdd5093aeea479d739a1d8a89e09e9527053030dfd30573f5c18160` |
| formal evidence | `.../batch_sampled_v1_3_g16_evidence_outputs_20260812_r1_F1023_V70_D0120_P7_G16_ch1/subblock_evidence.csv` | `60b3259cdc054d3e6b982bf8c03cb620594cfa7db62f7ff57cfa5d1a27d7caa4` |
| feature table | `.../batch_sampled_v1_3_g16_feature_outputs_20260812_r1_F1023_V70_D0120_P7_G16_ch1/v3_window_features.csv` | `330a31efb3bdd3ae94b58497ab80cecc6ed190fb69deda2f471a729be85b95c6` |
| parent promotion | same feature namespace `/promotion_manifest.csv` | `e4952df180eb07d56c091ace3bf31b9f08301c265a83b9634e3e3f675a382dc9` |
| ownership membership | `.../batch_sampled_v1_3_g16_component_ownership_outputs_20260812_r1_F1023_V70_D0120_P7_G16_ch1/promotion_component_membership.csv` | `2e6038e4b4d230f1aaa308f76b15b1678bbdd3b89481e2fc2442b135b16147c8` |
| evidence QA | `.../batch_sampled_v1_3_g16_evidence_qa_20260812_r1_F1023_V70_D0120_P7_G16_ch1/evidence_qa_report.json` | `c67c4309b551239337183236b75ea21e399f68316bad302ac287ffe1a9af2f14`, PASS |
| ownership QA | `.../batch_sampled_v1_3_g16_component_ownership_qa_20260812_r1c_F1023_V70_D0120_P7_G16_ch1/ownership_selector_qa_report.json` | `4780ed0196800fe91daf3d8a42832d122ab4db4dcfcb200cf806d25aee30a0dc`, PASS |
| posterior replay | `.../batch_sampled_v1_3_g16_posterior_gold_replay_20260812_r1b_F1023_V70_D0120_P7_G16_ch1/` | report hash `bd07ab267be8f46dbd036edeae5bcc7ca6efd8cb0160bf8fac9f7ce7b98f5edf`, PASS=false |
| current v2 kernel | `scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2_v2.py` | `959141371075c7f417f945dbe3f915f362a9337bb77582306f2b3ef16919ddfb`（继续实验前必须重算） |

## 9. 工程状态矩阵

| 项目 | 状态 | 当前可做什么 |
|---|---|---|
| 19 scene标准化/inventory | Completed + Validated | 只读输入审计、读取当前快照 |
| Pipeline V3 10.23 full-scan | Completed + Validated（已覆盖的task范围） | 仅按immutable request执行新10.23任务；当前不盲跑 |
| reference七PRN | Completed + Validated | 只读基线和论文材料 |
| Wave-A G16/G25/G12 | Completed + Validated | 只读QA/统计 |
| Wave-2A G11 | Completed + Validated | runtime/zero-event对照；不据此自动放行 |
| batch/Windows安全链 | Completed + Validated | 生成/审核新request；执行仍需人工门禁 |
| sampling v1/v1.1/A0 | Implemented + Failed/Frozen | 只能作为负结果和设计依据 |
| raw-coarse v2 | Implemented + kernel Validated；selector Failed | 不运行G25/G11 |
| raw-coarse v3 | Implemented + QA Validated + Posterior Failed/Frozen | 保留加速探索；v3.1暂停，不作为full SAGE生产阻塞 |
| 10.23 MHz full SAGE production | 6/67 Completed + QA PASS；G16 contract QA REJECTED，未计入Completed；当前由 Commander STOPPED 以进行 VTC evidence consolidation；remaining Planned / Not started | `F1023_V70_D0117_P4/G11/ch2`、`F1023_V70_D0120_P1/G18/ch2`、`F1023_V70_D0117_P4/G12/ch4`、VTC T1-1 `F1023_V70_D0120_P9/G05/ch10`、T1-2 `F1023_V80_D0117_P8/G25/ch10`和T1-3 `F1023_v90_D0117_P7/G11/ch6`已完成独立QA；`F1023_V70_D0120_P5/G16/ch1`已有执行artifact但因 `Resume` contract mismatch未获production acceptance；production manifest保持不变 |
| event database | Planned / Not started | 先完成schema和ingest实现 |
| LOW/MID/HIGH统计模型 | Not started | 等coverage-complete multi-scene数据 |
| 20.46 MHz | Not started / blocked | 单独适配和单任务验证 |

## 10. 不可破坏的安全约束

1. 永久保护reference所有既有结果，特别是 `G06_nav_sage_v1`；不覆盖、不移动、不删除、不resume。
2. 既有`nav_sage_v2`目录和Wave-A/G11结果不可覆盖。
3. 每次操作先查inventory、metadata、input path、output existence、manifest/hash；禁止凭空假设文件存在。
4. multi-channel必须人工选择并冻结channel；不能自动取第一个。
5. 20.46 MHz不能调用当前入口。
6. existing output默认new_only；中断保留checkpoint和partial artifact，不自动删除或resume。
7. Codex sandbox不直接调用MATLAB；由`TJ-CHANNEL\Jing_`正常用户PowerShell 7执行wrapper；smoke marker和exit code必须同时通过。
8. sampled/raw-coarse输出只能写新版本`dataset_generation_logs/sampling_validation/...` namespace，不能写`scenes/**/sage_results`。
9. gold只能在selector和provenance完全冻结后用于posterior recall；`gold_labels_used_for_selection=false`必须可审计。
10. 未独立QA PASS不得自动放行下一任务/阶段；不得把implemented/planned写成completed/result。

## 11. 当前安全命令和下一工程任务

只读审计/验证应从项目根目录执行：

```powershell
Set-Location E:\GNSS_Multipath_Project
Get-Content .\docs\GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md
Get-Content .\dataset\dataset_inventory.csv
```

任何新实验前至少重新执行：

```text
读取当前metadata/inventory
验证实际input存在、sample rate和唯一channel
验证pipeline/prototype/source hash
验证immutable manifest SHA
验证new_only output namespace为空
验证global lock不存在
```

正式 A3 G16 已完成一次用户正常Windows环境执行，但因executor/request contract mismatch未通过production acceptance；该旧request和artifact继续保留，禁止修改、复用或resume。修复后的G12 controlled acceptance已完成真实QA并释放Batch A；后续任务可以按新的immutable `new_only` request、人工preflight、正常Windows用户执行和逐任务独立QA继续，但不得自动并行或跳过门禁。raw-coarse v3.0继续作为失败且冻结的加速探索保存，v3.1设计暂缓；20.46 MHz仍不处理。

## 12. 历史文档索引

以下文件仍保留，作为专题证据或历史记录，不再与本文件并列为工程状态源：

- `docs/GNSS_SAGE_PROJECT_HANDOFF.md`
- `docs/GNSS_SAGE_AGENT_HANDOFF.md`
- `docs/GNSS_SAGE_DAILY_HANDOFF_20260807.md`
- `docs/GNSS_SAGE_PROJECT_HANDOFF_CURRENT.md`
- `docs/GNSS_SAGE_CODEX_PROJECT_HANDOFF_20260812.md`
- `docs/RAW_COARSE_V3_G16_POSTERIOR_GOLD_COVERAGE_REPORT_R1B.md`
- reference/Wave-A/Wave-2A QA、sampling设计和diagnostic文档

如果历史文档与本文件冲突，以实际artifact/receipt/QA和本文件的当前汇总为准。

## 13. Handoff impact

## 14. 2026-08-13 10.23 MHz scene metadata layer

工程数据层新增并验证了 10.23 MHz production scene metadata 文件：`dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv`；覆盖检查报告为 `docs/scene_metadata_10MHz_check_report.md`。

- 范围：13 个唯一 10.23 MHz scene、83 个 scene-PRN production task。
- 覆盖：13/13 scene 均有 metadata 行，且与现有 `scenes/<scene_id>/metadata.json`、production inventory 的 scene/raw/sample-rate provenance 一致。
- 人工字段：environment class、special condition、road type、human description；速度 provenance 固定为 `human_measurement_description`。
- 环境分布：Urban=6、Mountain/Valley=3、Highway/Open=2、Special Reflective=2。
- 本次新增的是独立 metadata layer；没有改写 scene 原始 `metadata.json`、production manifest、execution request、SAGE 结果、raw 或任何历史 artifact。
- 当前生产状态更新为：10.23 MHz full SAGE production 为 `4/67 Completed + QA PASS`；G12 controlled acceptance已通过并释放Batch A，VTC T1-1 G05已完成独立QA并登记为可用证据；G16 representative仍因contract QA REJECTED不计入Completed，不能复用其旧artifact；其余任务仍未执行，后续必须继续一任务一immutable request、人工执行和独立QA。

状态表达：新增 scene metadata layer 为 `Completed + Validated`；production、event database 和统计建模状态保持原有值。

本文件是工程状态唯一来源；任何后续真实代码、数据、实验、QA、hash、manifest或环境变化都必须先检查并更新本文件。论文影响由 `GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` 单独管理。

## 15. 2026-08-13 10.23 MHz production summary monitoring

已新增只读汇总工具：`scripts/sage_pipeline/audit_10MHz_production_summary.py`。

- 输入范围：`scenes/**/sage_results/nav_sage_v2/**` 中已有非空结果目录，以及对应的非raw execution log/receipt、QA Markdown和当前10 MHz production manifest provenance。
- 输出目录：`dataset_generation_logs/production_monitoring_10MHz/`。
- 输出文件：`production_summary_10MHz.csv` 和 `production_summary_report.md`。
- 任务字段覆盖scene、PRN、channel、sample rate、result scope、execution/QA status、runtime、Stage0–Stage4计数、confirmed event/path计数、输出文件完整性和provenance/warning路径。
- 工具只读取JSON/CSV/Markdown和结果目录文件状态；不打开raw IQ，不读取MAT信号载荷，不运行MATLAB/SAGE/batch，不计算PDP、delay spread、Doppler spread或K-factor。
- 当前只读快照发现14个非空`nav_sage_v2`结果namespace，均为10.23 MHz；其中当前production manifest任务4个有输出，G11、G18和G12已`completed + QA PASS`，G16仍为科学artifact QA PASS但contract acceptance rejected，不能据此进入Completed统计；reference、Wave-A和Wave-2A结果保留在汇总中并通过`result_scope`区分。G12已进入`production_summary_10MHz.csv`并避免重复计数。

该工具是production monitoring基础设施，不改变任何SAGE结果、QA报告、manifest、request或raw；它不构成新的production执行或放行授权。

## 16. Documentation Update Policy

本项目采用按影响范围同步的文档更新规则，避免每次动作都修改全部 handoff 或产生重复状态源。

### 16.1 Engineering handoff 必须更新的情况

以下变化必须更新本文件 `GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`：

1. 工程流程状态变化：pipeline阶段、production开始/完成、QA PASS/FAIL、Batch状态或任务状态变化；
2. 新增工程工具：production summary、QA、validation、audit或其他执行辅助脚本；
3. 新增工程能力：wrapper、执行流程、自动化检查、checkpoint或failure-recovery能力；
4. 重要实验路线或工程路线调整，例如v3路线改变、production路线调整；
5. 新的工程hash、manifest、request、receipt、环境或可运行命令事实。

### 16.2 Paper handoff 只在产生论文影响时更新

只有下列变化才更新 `GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`：

1. 研究路线或科学问题变化；
2. 论文贡献、方法解释、limitations或future-work变化；
3. 数据库设计或论文数据结构变化；
4. 新的论文可用实验事实，例如新scene完成、新环境覆盖、新validation结果或新的统计结果；
5. 论文正文/章节状态变化，例如Introduction或Methodology完成。

普通工程工具新增、单纯execution监控变化或尚未形成论文事实的工程进度，不自动更新Paper handoff。

### 16.3 Paper Workspace Index 只记录资产结构变化

只有新增、删除或改变论文资产结构时，才更新 `docs/PAPER_WORKSPACE_INDEX.md`，包括论文章节、数据库schema、图表目录和论文分析文件。普通实验结果更新不单独触发Index更新；如果实验同时产生新的论文资产，则按资产实际变化登记。

### 16.4 Production summary 的固定职责

每个正式production任务在独立QA后必须进入现有只读汇总工具及其输出：

`scripts/sage_pipeline/audit_10MHz_production_summary.py`

输出位置为 `dataset_generation_logs/production_monitoring_10MHz/`，至少记录execution status、QA status、runtime、Stage0–Stage4统计和confirmed event/path数量。Production summary是工程生产监控，不是论文数据库，也不替代event/path database。

### 16.5 单任务完成后的同步顺序

```text
Execution
  -> independent QA
  -> production summary update
  -> Engineering handoff update
  -> decide whether a paper fact exists
  -> update Paper handoff only when required
  -> update Paper Workspace Index only when a paper asset changed
```

若任务仅完成规划或代码实现而没有新的工程事实，必须保留 `Planned` 或 `Implemented` 状态；不得写成 `Completed` 或实验 `Result`。任何handoff更新都不得修改production artifact、QA结果、manifest、request或hash。

### 16.6 禁止行为

- 不得因为一次实验或工具动作而无条件修改所有handoff；
- 不得创建重复状态文件，例如 `ENGINEERING_STATUS_NEW.md`、`PAPER_STATUS_NEW.md`、`PAPER_PLAN_V2.md` 或 `FINAL_STATUS.md`；
- 不得把工程事实写成未经支持的论文结论；例如只能写“under current confirmation criteria, G18 produced zero confirmed multipath events”，不能写成“G18没有多径”；
- 不得把Implemented/Planned、gold前预测或单次zero-event输出扩大为统计模型、完整数据库或全部scene结论。

该规则本身只改变文档管理流程，不代表任何新实验或production任务已执行。

## 17. 2026-08-14 production executor/request contract fix

### 17.3 VTC Tier-1 T1-1 execution and independent QA (Completed + QA PASS)

- 任务：`F1023_V70_D0120_P9/G05/ch10/10.23MHz`；环境元数据为 `Special Reflective`，LOW 仰角仅作为场景级规划上下文，当前没有将其写成事件级几何结论。
- immutable request：`dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_1_d0120p9_g05_20260814/execution_request.json`；request SHA-256=`feebda81d6f541c012d0cd898deb0142cacd3e9d28fc83deb634cf827dd9c194`。
- 正式执行记录：`dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T060453Z/batch_execution_log.csv`；正常用户 receipt 目录：`dataset_generation_logs/batch_sage_execution/windows_runner_receipts/vtc_priority_t1_1_d0120p9_g05_20260814_20260814T060440076Z/`。
- 正式输出：`scenes/F1023_V70_D0120_P9/sage_results/nav_sage_v2/G05/`；独立 QA：`docs/10MHz_FULL_SAGE_PRODUCTION_T1_1_G05_QA_REPORT.md`。
- 执行契约、新-only 策略、artifact 完整性、Stage 链一致性和科学字段有效性均为 `PASS`；MATLAB smoke marker/exit code、Python executor exit code 和 task exit code 均为 0。运行时=`4696.042 s`。
- Stage统计：Stage0=`2632` valid NAV symbols/`2630` complete 40 ms windows；Stage1=`2630` scanned/`113` selected；Stage2=`452` evaluations，最终 L1/L2/L3/L4=`51/44/16/2`，L≥2/L≥3=`62/18`；Stage3 persistence rows=`82`、reliable centers=`12`；Stage4=`8` joint rows、8/8 `joint_valid=1`。
- 按固定 confirmed criterion，Stage4 confirmed events=`2`、confirmed multipath paths=`2`。这表示该任务在当前判据下产生了两个可追溯的 confirmed event/path 记录，不是对物理环境“必然存在/不存在多径”的绝对判断。
- 本次独立 QA 后，VTC T1-1 状态为 `QA_PASS / AVAILABLE`；production summary 已刷新。当前工程 accepted production count 为 `4/67`，不把历史 contract-rejected 的 A3 G16 计入该数；production manifest 未修改，T1-2/T1-3 仍需单独 Commander 决策，不自动执行。

### 17.1 Controlled Batch A acceptance request（执行前记录）

- Selected task: `F1023_V70_D0117_P4/G12/ch4/10.23MHz`, production task `F1023_V70_D0117_P4__G12`.
- Selection state: `Batch A`, ordinary single-channel task, unique inventory mapping `G12=>ch4`, complete recorded non-raw input provenance, target output absent; not A1, A2, G16, reference, or multi-channel blocked.
- Immutable request: `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_contract_acceptance_d0117p4_g12_20260814/execution_request.json`.
- Request SHA-256: `228c67b07fddc6526d320b45bf3495aa56854a478ff39c2fdc0ee6283b74edee`.
- Preflight: `PASS`; manifest, task record, inventory, input existence, non-raw hashes, output collision, global lock, and current pipeline/executor/wrapper hashes matched. Raw was checked for metadata-only existence/size and not opened.
- Dry-run: `PASS`, `matlab_invoked=false`; generated MATLAB expression contains `'Resume', false` and the dry-run artifact contains zero `Resume ... true` occurrences.
- Request policy: `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`; normal-user `TJ-CHANNEL\\Jing_` PowerShell wrapper remains required for any later human execution.
- Dry-run artifacts: `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_contract_acceptance_d0117p4_g12_20260814/dry_run_execution_log/`.
- 该节记录的是执行前状态：`Implemented + preflight/dry-run Validated; execution NOT STARTED`。随后实际执行和独立QA结果见17.2；执行前的immutable request、preflight和dry-run artifact均保持不变。

本次工程修复源于 G16 Batch A production QA 发现的 contract mismatch：immutable request 明确冻结 `execution_mode=new_only`、`new_only=true`、`resume_allowed=false`，但旧版 Python executor 的 MATLAB command builder 将 `Resume=true` 硬编码传给 `run_nav_sage_pipeline.m`。旧 pipeline 函数本身未修改，其默认参数 `Resume=true` 也未修改；修复目标是让 production executor 显式执行 request policy，而不是依赖函数默认值。

- 修复状态：`Implemented + static/dry-run Validated`；本次没有重新运行 MATLAB、SAGE 或任何 production task。
- 新安全链：immutable request + expected SHA → Windows wrapper 转发 request/SHA → `run_batch_sage.py` 重新校验 request policy、scope、路径和hash →共享 command builder 显式生成 `Resume=false` → MATLAB pipeline。
- 已修改：`scripts/sage_pipeline/run_batch_sage.py`、`scripts/sage_pipeline/Invoke-BatchSageWindows.ps1`、`docs/BATCH_SAGE_WINDOWS_EXECUTION_DESIGN.md`；已新增 request-contract Python 单元测试和 wrapper PowerShell AST/static test。
- 当前代码hash：`run_batch_sage.py`=`bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b`；`Invoke-BatchSageWindows.ps1`=`dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3`。
- 旧生产request `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a3_d0120p5_g16_20260813/execution_request.json` 的SHA=`629e22444baa3ae7cede6584ec486312cceb7be541e443eab4c30d53dfa8a094`，production manifest SHA=`77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`；二者均保持不变。旧request内嵌旧executor/wrapper hash，面对当前代码必须 fail closed，不能修改或复用。
- 验证结果：Python `py_compile`通过；全量 `unittest` 为 `102 tests, OK`；PowerShell AST/request-forwarding static test通过；合成request dry-run确认 `matlab_invoked=false` 且 command 使用 `Resume=false`；旧G16 request因代码hash过期被拒绝。未生成新production request。
- 执行前放行状态为未释放；该状态已由后续G12真实acceptance PASS更新，当前实际放行结论见17.2。

### 17.2 Controlled Batch A acceptance execution and independent QA（G12，Completed + QA PASS）

- G12已由正常用户 `TJ-CHANNEL\\Jing_` 通过现有Windows wrapper完成真实执行；execution ID=`batch_sage_execution_20260814T024904Z`，status history最终为`completed`，task exit code=`0`。
- 真实MATLAB invocation包含`'Resume', false`；execution contract QA和new-only policy QA均PASS，没有发现旧checkpoint reuse、旧Stage resume或旧namespace覆盖。
- 21个production output文件均存在且非空，Stage0–Stage4链和confirmed path一致性检查PASS。严格Stage4 criterion得到3个confirmed events和3条confirmed paths。
- 独立QA报告：`docs/10MHz_FULL_SAGE_PRODUCTION_CONTRACT_ACCEPTANCE_G12_QA_REPORT.md`。现有summary已刷新，G12行的`execution_status=completed`、`QA_status=PASS`、runtime=`4205.951 s`。
- **Batch A continuous production = `RELEASED`**。后续仍必须一任务一request、一任务一人工执行、一任务一独立QA；不得将release解释为自动批量或并行授权。
- 正式production accepted count更新为`3/67`；旧A3 G16 contract-rejected artifact仍保留但不计入该数量。

本次先完成executor/request合同修复和dry-run验证，随后G12真实acceptance及独立QA PASS。工程状态已更新；G12作为论文可用的新增production evidence同步记录在Paper Handoff/VTC证据矩阵中，但不提前写统计模型结论。

## 18. Project-local Codex governance skill (Implemented + Validated)

- 新增项目级 Codex skill：`.codex/skills/gnss-sage-project-commander/SKILL.md`；UI metadata 位于 `.codex/skills/gnss-sage-project-commander/agents/openai.yaml`。
- Skill职责：约束 GNSS/SAGE、full-SAGE production、QA、provenance、VTC evidence 和 Engineering/Paper handoff 的执行流程；固定当前状态源、new-only contract、Stage0–Stage4 scientific semantics、confirmed criterion、zero-event表述和Commander决策边界。
- Skill状态：`Implemented + Validated`。官方 `quick_validate.py` 已使用本机已有的 `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -X utf8` 通过；skill目录仅包含 `SKILL.md` 和 `agents/openai.yaml`，无额外依赖、脚本或重复状态文件。
- 本次只新增工程治理能力；未运行 MATLAB/SAGE/batch，未读取 raw IQ，未修改 production manifest、request、scene、metadata、inventory 或任何既有 SAGE artifact。当前 production 状态、accepted count、VTC 队列和论文科学状态均未因该 skill 改变。

## 19. VTC Tier-1 T1-2 G25 production QA (Completed + Validated)

- Task：`F1023_V80_D0117_P8/G25/ch10/10.23MHz`，执行 ID：`batch_sage_execution_20260814T075945Z`。
- Immutable request：`dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_2_v80p8_g25_20260814/execution_request.json`；request SHA-256：`efd3bec67010856cdf1196202369f927224403015048277f4f57116e5029bb43`。
- Execution/QA：正常 Windows 用户 `TJ-CHANNEL\Jing_` 执行；MATLAB smoke marker 和 exit code 均通过；Python/task exit code 均为 `0`；真实 MATLAB invocation 使用 `Resume=false`；独立 QA 报告为 `docs/10MHz_FULL_SAGE_PRODUCTION_T1_2_G25_QA_REPORT.md`。
- Output：`scenes/F1023_V80_D0117_P8/sage_results/nav_sage_v2/G25`，21/21 标准文件非空，new-only 从空 namespace 完成，无旧 checkpoint reuse。
- Stage 统计：Stage0 `1144` symbols / `1142` windows；Stage1 `1142/112` scanned/selected；Stage2 `448` evaluations，L1/L2/L3/L4=`38/13/12/49`；Stage3 `8` reliable centers；Stage4 `8` rows，`8/8` joint_valid；confirmed=`2` events / `2` paths。
- Production summary 已刷新为 16 个 10.23 MHz result rows、10 个 QA PASS rows；按 accepted-state 规则计入后正式 production accepted count 为 `5/67`，历史 contract-rejected A3 G16 仍不计入。
- VTC 影响：Highway/Open evidence `Available / QA PASS`；HIGH 仍是 scene/PRN planning context，不是 event-level elevation 结论。Mountain/Valley 仍需 Commander 判断，未生成 T1-3 request。
- 本次没有运行新的 MATLAB/SAGE；QA 未修改 manifest、immutable request、既有 SAGE artifact、metadata 或 inventory。后续不得自动启动 T1-3。

## 20. VTC Tier-1 T1-3 G11 production QA (Completed + Validated)

- Task: `F1023_v90_D0117_P7/G11/ch6/10.23MHz`; environment metadata `Mountain/Valley`; MID and approximately 35 degree elevation are scene-level planning context only.
- Immutable request: `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_3_v90p7_g11_20260814/execution_request.json`; request SHA-256=`7a1361445855244ca6ed6f9f640debe1533981c7d4490bab52f45132fb170d47`.
- Execution log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260815T132956Z/batch_execution_log.csv`; QA report: `docs/10MHz_FULL_SAGE_PRODUCTION_T1_3_G11_QA_REPORT.md`.
- Normal Windows-user execution passed MATLAB smoke and Python/task exit checks; actual command used `Resume=false`; task status was `completed`; runtime=`4901.428 s`.
- Output: `scenes/F1023_v90_D0117_P7/sage_results/nav_sage_v2/G11/`; 21/21 expected files were present and non-empty, with no evidence of checkpoint reuse or output contamination.
- Stage statistics: Stage0=`1292` valid NAV symbols/`1288` complete windows; Stage1=`1288` scanned/`112` selected; Stage2=`448` evaluations and L1/L2/L3/L4=`45/16/37/14`; Stage3=`10` reliable centers; Stage4=`8` joint rows and `8/8` `joint_valid=1`.
- Strict Stage4 confirmation produced `1` confirmed event and `1` confirmed multipath path. Stage2 higher-order models and Stage3 reliable centers remain intermediate evidence, not confirmed events.
- Engineering status: accepted 10.23 MHz production count is now `6/67`; T1-3 is `QA_PASS / AVAILABLE`. The production manifest remains unchanged; the protected historical G16 artifact remains excluded from accepted count.
- VTC Mountain/Valley task-level evidence is available, but window-level TOW geometry join remains `Missing/Partial`; this blocks geometry-complete LOW/MID/HIGH denominators. No T1-4 request was created. The next engineering route is event/path aggregation and geometry/time-alignment QA, subject to Commander review.

## 21. Commander STOP: VTC evidence consolidation (2026-08-15)

- Commander decision: **STOP SAGE PRODUCTION**. Do not create T1-4/T1-5 requests, run MATLAB/SAGE, modify the production pipeline, modify immutable requests, or alter existing SAGE artifacts.
- Accepted production count remains `6/67`: T1-1 G05, T1-2 G25 and T1-3 G11 are QA-passed VTC evidence cases; the historical A3 G16 artifact remains excluded under the executor/request contract rule.
- The current engineering task is now evidence consolidation and event-level geometry/time-alignment QA. The paper evidence index is `docs/vtc2027_spring/evidence/`; it does not replace the long-term event/path database or production manifest.
- New paper-support artifacts: `docs/vtc2027_spring/evidence/vtc_confirmed_path_database.csv`, `vtc_evidence_summary.csv`, and `vtc_geometry_alignment_qa.md`.
- Geometry QA status is `PARTIAL`: five confirmed paths have provisional nearest NMEA/GSV matches, but no event is geometry-complete because the observation-clock/TOW-to-UTC bridge and its provenance are not frozen in the production artifacts. No mean elevation or scene label was promoted to event-level truth.
- This route change does not modify production manifest, request, pipeline, metadata, inventory, raw data, or any `scenes/**/sage_results` artifact. Further production requires a new Commander decision after evidence/geometry review.

## 22. VTC Chinese canonical review and Special Reflective supplement preparation (2026-08-17)

- Chinese review PDF canonicalization completed: `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.pdf`; current SHA-256=`32F79236D6EB72466CF85CD5F92EDD9E42814E9F676189CEA88E8F0643400A90`, 4 pages. The obsolete temporary `main_cn_review_audit_20260816.pdf` was removed only after compile/render/hash verification. This is a paper-review asset update, not a production result.
- One independent-scene Special Reflective supplement was selected for preparation only: `F1023_V70_D0122_P2/G15/ch8/10.23MHz`. Selection is based on independent scene coverage, input completeness, single-channel readiness, and absent output namespace; it does not predict a positive multipath outcome.
- Immutable request: `dataset_generation_logs/batch_sage_execution_requests/vtc_special_reflective_supplement_p2_g15_20260817/execution_request.json`; request SHA-256=`0d8de5948101f67bfc9458785d40f876412617b2fd903d695aab2cb85abd85a5`.
- Preflight and Python-only dry-run are `PASS`: one row accepted, zero rejected, `matlab_invoked=false`, `new_only=true`, `resume_allowed=false`, and the command preview contains `Resume=false`. Dry-run artifacts are in `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260816T163442Z/`; the detailed preflight is beside the request.
- Execution status is `NOT STARTED`. Codex did not launch MATLAB; any later execution must be a human-reviewed normal-user `TJ-CHANNEL\\Jing_` PowerShell wrapper call. No second task, Highway/Open supplement, or automatic continuation is authorized. No production count, QA result, event count, or paper environment conclusion changed.

## 23. Special Reflective supplement G15 execution and independent QA (Completed + Validated, 2026-08-17)

- Task: `F1023_V70_D0122_P2/G15/ch8/10.23MHz`. This was the single approved Special Reflective supplement task; no second supplement or automatic continuation was started.
- Immutable request: `dataset_generation_logs/batch_sage_execution_requests/vtc_special_reflective_supplement_p2_g15_20260817/execution_request.json`; request SHA-256=`0d8de5948101f67bfc9458785d40f876412617b2fd903d695aab2cb85abd85a5`.
- Normal-user execution: identity `TJ-CHANNEL\\Jing_`; MATLAB smoke marker and exit code passed; Python executor and task exit codes were `0`; actual invocation used `Resume=false`. Execution log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260816T164900Z/batch_execution_log.csv`; runtime=`7711.011 s`.
- Output: `scenes/F1023_V70_D0122_P2/sage_results/nav_sage_v2/G15/`; exactly 21 expected files were present and non-empty. Independent QA report: `docs/vtc2027_spring/evidence/VTC_SPECIAL_REFLECTIVE_SUPPLEMENT_G15_QA_REPORT.md`.
- Stage statistics: Stage0=`3695` valid NAV symbols / `3687` complete windows; Stage1=`3687` scanned / `108` selected; Stage2=`432` evaluations with L1/L2/L3/L4=`42/33/10/23`; Stage3=`10` reliable centers; Stage4=`8` joint rows and `8/8` `joint_valid`; strict confirmed criterion yielded `5` events / `5` paths.
- Production monitoring was refreshed by the read-only summary tool: `18` 10.23 MHz result rows and `12` QA-PASS rows. The formal manifest has `8` result namespaces; under the current accepted-state rule (excluding the historical contract-deviation A3 G16 artifact), accepted production count is `7/67`.
- The G15 result adds a second independent Special Reflective scene and is now a traceable paper-evidence case. It does not create an event database, channel-parameter database, or statistical model; path-level coherence is unavailable for the five new path rows, and event-level geometry remains partial.
- Commander `STOP SAGE PRODUCTION` remains unchanged. No further request, Highway/Open supplement, Mountain/Valley supplement, or automatic continuation is authorized by this update. Existing manifest, requests, metadata, inventory, pipeline, and prior SAGE artifacts remain protected.

## 24. Darkroom rain recording audit and partial scene standardization (2026-08-17)

- Branch status: `DARKROOM_CHANNEL_EMULATION_BRANCH=ACTIVE`; current subtask was `AUDIT_AND_STANDARDIZE_RAIN_RECORDINGS`. The VTC branch and its evidence decisions were not changed.
- Three new, non-production scene input namespaces were organized from `rain/`: `scenes/F1023_clear`, `scenes/F1023_midrain`, and `scenes/F1023_heavyrain`. Non-raw configuration/result files were copied with hash verification; raw files remain external under `rain/` and are referenced by metadata with `copied_into_scene=false`.
- New metadata: `scenes/F1023_clear/metadata.json`, `scenes/F1023_midrain/metadata.json`, and `scenes/F1023_heavyrain/metadata.json`. Their SHA-256 values are respectively `dff272792a93ef4f726b9b47d1bc6fd8ed73926d7f523b7e1740510a54d94593`, `4702447442ed1499914100e99e0bf83e6ddf696afadd9a9047403c663db2bc29`, and `366af5b5f22889049c5e8d0e5fa73602d3277700f25abc4bae8204ca565a6d31`.
- All three source configurations confirm GPS L1 C/A and `sample_rate_hz=10230000`. Raw file hashes were captured for provenance only; no raw IQ samples were processed by this audit.
- Telemetry-derived channel/PRN mappings are: clear ch1/G24, ch3/G29, ch11/G12; midrain ch1/G24, ch7/G20; heavyrain ch1/G02, ch2/G01, ch6/G31. The three-way common PRN intersection is empty, so `rain_common_prn_candidates.csv` has schema only and no SAGE candidate.
- GNSS-SDR status for each rain recording is `Partial`: tracking, telemetry, and observables files exist, but no GNSS-SDR completion log/exit receipt was found; PVT, NMEA, RINEX NAV, trajectory, and satellite geometry are missing. These scenes are not SAGE-ready and are not in the production manifest or `dataset/dataset_inventory.csv`.
- Audit artifacts are under `dataset_generation_logs/darkroom_channel_emulation/`: `rain_input_inventory.csv` (136 rows, SHA-256 `aafbe4ec33ba0c741e2f2aa8f3f3d8fd02f79ea922aa06cc3d359c15de88709b`), `rain_file_mapping.csv` (139 rows, SHA-256 `9c06ac402436ab813be376c2c773cbeac36c9739d8dedfd87fabc0d987a7870d`), `rain_common_prn_candidates.csv`, `rain_provenance_manifest.json` (SHA-256 `c274bbf9c10020549ba1a81f451e2ab0c26fcd4c22f2df13322b5c145e1a57eb`), and `rain_scene_standardization_report.md`.
- Status: non-raw organization and provenance capture `Completed/Validated`; GNSS-SDR/NAV/trajectory/geometry inputs `Partial/Missing`; SAGE `Not started/Blocked`. No MATLAB, SAGE, batch task, raw-IQ processing, raw deletion, or existing SAGE artifact modification occurred.
- Engineering next decision: before any future request, establish a matched PRN across weather conditions and complete/verify GNSS-SDR, navigation, trajectory, and geometry provenance. Do not add these partial scenes to production or infer rain effects from their current files.

## 25. Darkroom Rain GNSS-SDR rerun and separate Rain adapter (2026-08-17)

- This section supersedes the pre-rerun Rain facts recorded in Section 24; the earlier artifacts remain preserved under dataset_generation_logs/darkroom_channel_emulation/superseded_pre_rerun_20260817/ and are not silently reused.
- Current source rerun ID is 20260817_gnss_sdr_rerun. The current source recordings are rain/F1023_clear/F1023_clear.bin (2,925,003,264 bytes, SHA-256 0be6adba273a81b21d6e84e93a4fa1450f7a4a76c093ef1ea17163015f616210), rain/F1023_midrain/F1023_midrain.bin (2,903,638,528 bytes, SHA-256 22f8074e6fa0e78790f87dc3c4114d1420963335a541b19dda57e087ac81fa69), and rain/F1023_heavyrain/F1023_heavyrain.bin (2,916,090,368 bytes, SHA-256 6be60750a59c1726c0c2f87dcc32df43c2dd698e40637c3775f8703f24aba6b7). Hashing was for provenance; no raw IQ samples were processed.
- Non-raw current rerun outputs were refreshed into scenes/F1023_clear/, scenes/F1023_midrain/, and scenes/F1023_heavyrain/. The current metadata hashes are 4fe463bf5cfa3024c31174fb5a029dad5935223f075be0e73cdf3c671f1aa1ce, f98a775f531b71f0fff63659fa6628646f3eedacef63917394f3dea4f75266b4, and 0d8026b93d17f4250aa4ac2a299d550a8785e205935d41c3590cdc446e1544ec, respectively. Raw remains external and copied_into_scene=false.
- Current telemetry-derived mappings are: clear ch3/G29, ch8/G13, ch10/G24, ch11/G12; midrain ch8/G24, ch9/G20; heavyrain ch1/G02, ch4/G31, ch7/G01. The all-three PRN intersection is empty. G24 is a clear/midrain matched pair. Under the frozen Rain MVP policy, common PRN is preferred for matched validation but is not required for per-recording pooled analysis.
- The current input and mapping files contain 141 rows each with SHA-256 c4550c18987e8c5f5de7833b282fd7502a65d29194c573cf281502940d06b2c1 and 10957142bd2e49a1c17ecb46c726e6a5b4806121042a570da571800c43e4e631. The current provenance manifest is dataset_generation_logs/darkroom_channel_emulation/rain_provenance_manifest.json, SHA-256 835921126c7dd1e16bf4d28abc20a4665aa9837bb4ab1c1e536f73389a3e1f2b; the static audit outputs are rain_sage_input_audit.json and rain_sage_input_audit.csv.
- Rain policy is now explicit: RAIN_SAGE_USE_SEPARATE_PIPELINE=YES; NMEA, PVT, RINEX, trajectory, and geometry are not Rain MVP prerequisites; elevation conditioning is disabled. The XML navigation output is retained as provenance. Static input audit marked all nine mapped scene/channel combinations rain_sage_input_ready=YES, but execution_ready=false because MATLAB tracking-MAT schema validation and shared Stage1–Stage4 core extraction remain outstanding.
- The production dependency audit found that input resolution requires trajectory/NMEA/RINEX in the formal pipeline, while Stage0 uses NMEA only for optional speed interpolation and the fallback relative-Doppler bound. Raw indexing and NAV wipe use tracking/telemetry-derived sample and NAV-symbol fields. Stage1–Stage4 do not read NMEA/geometry, but they are private local functions in the monolithic run_nav_sage_pipeline.m; no independent Rain copy has been made.
- New Rain branch files are scripts/sage_pipeline/rain/audit_rain_sage_inputs.py (SHA-256 ab5c8726778451193c47b22c35b8e6a3c67eba1efa7c0b54d1ddb2d51f9485d5), test_audit_rain_sage_inputs.py (SHA-256 d5cc406987946dfc906e18f1e939e578b410165a9f710da8d3f27762cff344b6), build_rain_stage0.m (SHA-256 7a1f5fba2fc25a8e466988cdc365265f5bdc1039bfb342325984b9305a49d16b), run_rain_sage_pipeline.m (SHA-256 6ec350d06b081c6629bd39b792c0e5c948c02018bb75af8fbb6491fccaa81434), and README.md (SHA-256 b45efa2305513a4c81858bdcb8ef4c4ddc5a8b374d270ea743d081f0cfaa6566).
- build_rain_stage0.m preserves the Stage0 window/symbol semantics, uses explicit NaN and unavailable_no_NMEA for unavailable speed, and never opens raw IQ. run_rain_sage_pipeline.m is preflight-only by default, rejects Resume=true, uses the branch-local scenes/<scene>/sage_results/rain_sage_v1/<PRN>/ namespace, and fails closed for full Stage1–Stage4 execution until a reviewed shared-core extraction exists.
- The Rain parameter comparison records CORE_PARAMETER_DRIFT=NONE_BY_DESIGN; this means no second Stage1–Stage4 parameter set was introduced, not that Rain full SAGE has been validated. Full Rain SAGE remains Not started / Blocked by shared-core extraction.
- Static checks and Rain Python tests passed: py_compile passed and 7 tests, OK. The auditor reported three scenes, nine statically ready mapped channels, matched-pair candidate G24, and raw_iq_samples_opened=false. MATLAB was not started; no SAGE, batch request, VTC artifact, production artifact, or main dataset inventory was modified. The MATLAB executable is present for a future normal-user preflight, but no MATLAB syntax/run validation was invoked in this task.
- The three Rain sage_results roots were checked empty. No formal nav_sage_v2 output was created. The Rain branch is not in the 10.23 MHz production manifest.
- Status: rerun input discovery and non-raw scene standardization Completed + Validated; static audit and Rain adapter Implemented + Validated at the Python/static level; Rain Stage1–Stage4 shared-core extraction Planned / Not started; full Rain SAGE Not started; weather-conditioned path statistics Planned / Not started.
- Unique next action: review and extract the validated Stage1–Stage4 core into a separately testable shared module without changing production parameters, then perform a normal-user MATLAB MAT-schema preflight for one approved Rain channel. Do not create a request or run Rain SAGE until that review is complete.


## 26. Shared Stage1–Stage4 core extraction audit (Implemented; MATLAB regression pending, 2026-08-17)

- This section supersedes the shared-core status statements in Section 25; Section 25 and all prior artifacts remain preserved. The current Rain provenance manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_provenance_manifest.json`, SHA-256=`f267e599199ba7116df805768001903f209f0ea3ac9476c53be50c8315561d49`.
- The pre-refactor production source hash was `5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab`. The current production entry is `scripts/sage_pipeline/run_nav_sage_pipeline.m`, SHA-256=`95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0`.
- Shared files are `scripts/sage_pipeline/core/default_sage_configuration.m` (SHA-256=`ac06ad3191ca7ca05480fb84c0465a5082c157f4eaad1ae3018e26e1abed1319`), `scripts/sage_pipeline/core/run_sage_stage1_stage4_core.m` (SHA-256=`338708127559ab6b75af47bc1d858fbd70e449830a895a9909c008218fab2e8e`), and `scripts/sage_pipeline/core/compute_sage_doppler_bound.m` (SHA-256=`c59d7928d88d0dd483061e72d321313ef22dae97b1d3ada41b641856a9d606ae`). Rain adapters are `build_rain_stage0.m` SHA-256=`e2c002a4a2f9eb2d4020e38de43dc17043a29e27768f0598dd12636e074d83ab` and `run_rain_sage_pipeline.m` SHA-256=`6d529b005a5652f3ee31a5fc033a8c44e38c3ade17c396c4d3a0688e02718060`.
- Production still owns input resolution, GNSS-SDR decoding, Stage0, run context, final summary, and overview plotting. Stage1–Stage4 numerical execution, checkpoint/output orchestration, NAV-wiped loading, correlation/SAGE helpers, persistence, joint estimation, and record constructors are in the shared core. The Rain entry calls the same core when full execution is explicitly requested; its default remains preflight-only and its namespace remains `scenes/<scene>/sage_results/rain_sage_v1/<PRN>/`.
- The Doppler-bound audit found no new fallback or parameter drift. The former production finite-speed and unavailable-speed formula is centralized in `compute_sage_doppler_bound.m`; production and Rain Stage0 call that utility. Frozen Stage1/Stage2 grids, thresholds, Stage3 persistence, Stage4 joint criterion, and confirmed-path criterion were not changed by design.
- Static/source validation is complete: shared-core structural tests `18/18 PASS`; all current Python regression tests `120/120 PASS`; relevant `py_compile PASS`. MATLAB syntax/runtime, deterministic production regression, frozen-artifact replay, and Rain G24 MATLAB preflight were not run because Codex must not launch MATLAB in the sandbox.
- Status: shared-core extraction `Implemented + static Validated`; MATLAB/production numerical regression `Planned / Not started`; Rain full SAGE `Not started / Blocked`; Rain G24 preflight `Not started`; no Rain request exists. Existing `nav_sage_v2`, Rain output roots, reference results, and prior prototype artifacts were not modified.
- Unique next action: a normal Windows user must run the independent MATLAB deterministic/production regression against the shared core. Only if that gate passes may the Commander review a manual Rain G24 preflight. Do not create a Rain request, run Rain full SAGE, run G25/G11, resume any artifact, or process 20.46 MHz.


## 27. Protected shared-core MATLAB regression harness prepared (2026-08-17)

- The first requested baseline `F1023_V70_D0117_P2/G06/ch4` was audited but not used: its protected legacy `G06_nav_sage_v1` directory lacks `run_context.json`, so strict frozen provenance is insufficient. It was not modified.
- The selected strict baseline is `F1023_V70_D0117_P2/G28/ch1`, with complete Stage0–Stage4 CSV/MAT outputs and `run_context.json` at `scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G28/`. This is a reference-scene validated rejected-candidate/control case, not a new experiment result.
- New thin harness: `scripts/sage_pipeline/regression/run_shared_core_regression.m`, SHA-256=`66aa5caff2d51f24636a6880573c76edb5f5b67e6c839421351703b3a1d550bc`. It loads frozen Stage0, forces `Resume=false`, calls only the shared Stage1–Stage4 core, rejects an existing namespace, writes only under `dataset_generation_logs/darkroom_channel_emulation/shared_core_matlab_regression_<UTC>/`, and compares categorical/index identity plus numeric fields. It does not copy Stage1–Stage4 algorithms.
- Harness static test: `scripts/sage_pipeline/regression/test_shared_core_regression_harness.py`, SHA-256=`ad84d7fda60252a902721fd9f1f105f43b2e824430d6683723950d824d073294`; 5/5 PASS. The full existing Python suite remains 120/120 PASS. The current Rain provenance manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_provenance_manifest.json`, SHA-256=`e878250d5e9e4a0234ab652625d7ff2a693fa2e564269a42272946b5a946292c`.
- MATLAB regression was not run in Codex. Current status remains `PRODUCTION_REFACTOR_REGRESSION=INCOMPLETE`, `RAIN_G24_PREFLIGHT=NOT_RUN`, and `RAIN_FULL_SAGE_RELEASE_RECOMMENDATION=NO`. No Rain request, full Rain SAGE, G25/G11 run, 20.46 MHz run, or existing artifact modification occurred.
- Unique next action: `TJ-CHANNEL\Jing_` must run the exact MATLAB harness command recorded in `sage_shared_core_regression_report.md`. Only a genuine regression PASS can unlock the separate `F1023_clear/G24/ch10` `PreflightOnly=true` command. Stop after that preflight; do not start Rain full SAGE automatically.

## 28. Regression harness BOM input fix (Implemented + static Validated; MATLAB rerun pending, 2026-08-17)

- The manually observed MATLAB failure is classified as `HARNESS_INPUT_PARSING_FAILURE`, not an algorithm regression: MATLAB execution was real with exit code `1`, the UTF-8-BOM scene metadata was read before the shared core, and `SHARED_CORE_ENTERED=NO`. The current statuses remain `PRODUCTION_REFACTOR_REGRESSION=INCOMPLETE` and `RAIN_G24_PREFLIGHT=NOT_RUN`.
- Root cause is `UTF8_BOM_IN_SCENE_METADATA` in `scenes/F1023_V70_D0117_P2/metadata.json`. Its baseline SHA-256 is `960ecd47b390dc8a74dce989a782cbacc9552d680fb6bd5d8dc470b24ee7aa5b` both before and after the fix; its first 16 bytes remain `EF BB BF 7B 0D 0A 20 20 20 20 22 73 63 65 6E 65`. `BASELINE_JSON_MODIFIED=NO`.
- `scripts/sage_pipeline/regression/run_shared_core_regression.m` now uses its local `readJsonWithBom` helper for all harness JSON inputs (`run_context.json` and `metadata.json`). The reader supports UTF-8 with/without BOM and UTF-16LE/UTF-16BE BOM, and fails closed for empty, BOM-only, blank, undecodable, or invalid JSON. It does not alter the source metadata or shared Stage1--Stage4 core. New harness SHA-256=`6d4cacd57f7d96dce6ae7b38d6ea7bec4a95ffb82496fcaeb34271f9341be5ef`.
- `scripts/sage_pipeline/regression/test_shared_core_regression_harness.py` adds encoding, failure-mode, no-character-deletion, and baseline SHA/BOM checks. Static harness tests passed `9/9`; all discovered project Python tests passed `102/102`; `py_compile` passed for all discovered test modules. Test SHA-256=`fd0a4512e174fdf6aace3916093af564114805a30f8121b9f966be902bced906`.
- `dataset_generation_logs/darkroom_channel_emulation/rain_provenance_manifest.json` records the reader, root cause, previous MATLAB exit code, `shared_core_entered_on_last_attempt=false`, `baseline_json_modified=false`, and the new source hashes. Current manifest SHA-256=`6ba5efc7df5133951033991f565135719e7514ef10bfb8c19ef041fcb8945e8b`.
- No MATLAB rerun was performed by Codex; no G24 preflight, Rain SAGE, batch task, raw-IQ sample processing, metadata change, baseline artifact change, or shared-core change occurred. The next and only action is for normal user `TJ-CHANNEL\Jing_` to rerun the updated MATLAB harness command in the regression report. If and only if it returns a genuine regression PASS may the Commander review the separate G24 preflight. Do not run Rain SAGE automatically.

## 29. Shared-core syntax repair after second real MATLAB attempt (Implemented + static Validated; MATLAB regression pending, 2026-08-17)

- The second normal-user execution passed the BOM reader and reached the shared-core call, but MATLAB stopped while parsing `scripts/sage_pipeline/core/run_sage_stage1_stage4_core.m` at line `113`, column `17`. The preserved receipt is `dataset_generation_logs/darkroom_channel_emulation/shared_core_matlab_regression_20260817T092506Z/regression_receipt.json`; it records `MATLAB_EXIT_CODE=1`, `SHARED_CORE_FILE_REACHED=YES`, `SHARED_CORE_NUMERICAL_EXECUTION=NOT_STARTED`, and `FAILED_BEFORE_NUMERICAL_CORE_EXECUTION`. This is `SHARED_CORE_MATLAB_SYNTAX_ERROR`, not `ALGORITHM_REGRESSION_FAILURE`.
- Exact root cause: the extracted line was `result = struct(` without MATLAB line continuation, while the next line began the name/value arguments. The syntax-only repair is `result = struct( ...`. The current production entry retains the valid corresponding form at `run_nav_sage_pipeline.m:139`; no Stage1–Stage4 computation or parameter was changed.
- Core SHA-256 changed from the pre-repair recorded value `338708127559ab6b75af47bc1d858fbd70e449830a895a9909c008218fab2e8e` to `968cc30ebd81e6a1e1d7d724421b947518d19ae043e2c4c86ace914a854f2628`. `default_sage_configuration.m` and `compute_sage_doppler_bound.m` are unchanged. Change classification is `CHANGE_TYPE=SYNTAX_REPAIR`, `ALGORITHM_CHANGE=NONE`.
- The shared-core structural test now checks multiline MATLAB-call continuation. Static scan found no remaining bare line-ending `(` or two-dot continuation typo in the audited core/configuration/Doppler/adapter sources. Structural test status is `8/8 PASS` (SHA-256=`08cb250bea4e78169ce9e038be8518bb0da4dd65c465bc1e245de307e90daed5`); regression harness status is `9/9 PASS`; the complete explicit Python test scope is `130/130 PASS` (`root=102`, `core=8`, `rain=11`, `regression=9`); `py_compile` is PASS.
- The earlier `120/120` versus `102/102` discrepancy was a scope difference, not deleted tests: `120` was root `102` plus core `7` plus Rain `11`, while the later root-only discovery command reported `102`; subdirectories lack `__init__.py` and are not recursively discovered. The current complete scope is explicitly separated and totals `130` after the new tests.
- G28 baseline `nav_sage_v2` files, `run_context`, scene metadata, Stage CSV/MAT artifacts, and all existing production/reference outputs remain unchanged. The BOM-fix failure history remains preserved; the syntax-failure artifact is also preserved. Current `PRODUCTION_REFACTOR_REGRESSION=INCOMPLETE`, `RAIN_G24_PREFLIGHT=NOT_RUN`, and `RAIN_FULL_SAGE_RELEASE_RECOMMENDATION=NO`. Current provenance manifest SHA-256=`4808b7fa20ed8b4570a39077b8fdad404c70aac63b2fdca740ff60297b362dae`.
- The only next action is for `TJ-CHANNEL\Jing_` to run the updated `run_shared_core_regression` PowerShell command recorded in `sage_shared_core_regression_report.md`, without `exit $matlabExitCode` so the console remains open. Do not run G24 preflight, Rain SAGE, production SAGE, batch, or 20.46 MHz until a genuine MATLAB parser/numerical regression PASS is obtained.

## 30. Complete shared-core result-struct syntax repair and parse-only gate (Implemented + static Validated; MATLAB parser pending, 2026-08-17)

- The third normal-user MATLAB attempt passed the BOM reader and the repaired line 113, then exposed the next continuation defect at `run_sage_stage1_stage4_core.m:114:40`. The preserved artifact is `dataset_generation_logs/darkroom_channel_emulation/shared_core_matlab_regression_20260817T093812Z/`; receipt SHA-256=`f2985790bcc7545c5dc4991bb3fa19f8fe00d24f82a807e3d98ef05a3e415984`. This remains `SHARED_CORE_MATLAB_SYNTAX_ERROR`, with `SHARED_CORE_FILE_REACHED=YES` and numerical execution not started; it is not an algorithm regression.
- Root cause was a trailing comma at the end of each continued name/value line in the shared-core result constructor. The comma on line 114 was the final character (column 40 is the line termination); the missing token was MATLAB `...`. Lines 113–125 now use explicit continuation markers. The corresponding production result constructor at `run_nav_sage_pipeline.m:139-149` was used as the syntax reference and was not modified.
- This is a syntax-only repair: `run_sage_stage1_stage4_core.m` changed from the prior recorded `968cc30ebd81e6a1e1d7d724421b947518d19ae043e2c4c86ace914a854f2628` to SHA-256=`e3e61c37a9835972a3f680de9bf79f1fc4beda7e18edbbbd2abf6f90dce7430c`; algorithm parameters, Stage1–Stage4 logic, confirmed criterion, production entry, configuration, and Doppler utility were not changed.
- A parse-only MATLAB entry point was added at `scripts/sage_pipeline/regression/run_matlab_syntax_smoke.m`, SHA-256=`395a97d1ffce0c1e68c6b013d47d22d2d15a29ca308a7815393ff7341622f737`. It calls `checkcode` only on the audited core/configuration/regression/Rain adapter files and reports `raw_iq_opened=false` and `sage_executed=false`; it has not been run by Codex. The syntax audit is recorded in `dataset_generation_logs/darkroom_channel_emulation/shared_core_extraction_syntax_diff.md`, SHA-256=`fd7fca968854362b87efcd754737c8b48d3b845745b5d9c9b3d8429d25d08b3`.
- Static verification is complete: Python test scope `131/131 PASS` (`root=102`, `core=9`, `rain=11`, `regression=9`) and `py_compile=PASS`. Structural test SHA-256=`5ed698f5bb675bc0cd6782b53f111df9e748e2a1b6cf89e03f622612d6611776`. Current provenance manifest SHA-256=`bb34f9773e76ca4084e0ce207a7bb03571553c3c0b3bd3fc6747eedc35111e03`.
- Current authoritative status is `BOM_PARSE=PASS`, `SHARED_CORE_FILE_REACHED=YES` on the last preserved attempt, `SHARED_CORE_NUMERICAL_EXECUTION=NOT_STARTED`, `PRODUCTION_REFACTOR_REGRESSION=INCOMPLETE`, `RAIN_G24_PREFLIGHT=NOT_RUN`, and `RAIN_FULL_SAGE_RELEASE_RECOMMENDATION=NO`. No raw IQ samples, MATLAB command, SAGE, G24 preflight, Rain run, batch task, 20.46 MHz task, or existing artifact was executed or modified by Codex.
- The unique next action is for `TJ-CHANNEL\Jing_` to run `run_matlab_syntax_smoke` in a normal Windows MATLAB environment. Only if it returns `MATLAB_SYNTAX_SMOKE=PASS` may the retry-3 numerical regression command in `sage_shared_core_regression_report.md` be run. No Rain/G24 request or execution is authorized before a genuine MATLAB syntax and numerical regression PASS.

## 31. Rain MVP standalone-route decision (Implemented + static Validated; MATLAB pending, 2026-08-17)

- Commander decision: `SHARED_CORE_REFACTOR_ROUTE=FROZEN`; `PRODUCTION_PIPELINE=MUST_RETURN_TO_VALIDATED_BEHAVIOR`; `RAIN_PIPELINE=STANDALONE_BRANCH_LOCAL_IMPLEMENTATION`. Repeated shared-core extraction/parser failures make further Rain-driven production refactoring unacceptable.
- The previous real syntax-smoke log `dataset_generation_logs/darkroom_channel_emulation/matlab_syntax_smoke_20260817.log` contains only file-level `FAIL/PASS` lines and the final MATLAB error; it does not contain per-diagnostic line, column, message, or severity. The generic smoke harness was therefore changed to emit normalized `DIAGNOSTIC file/line/column/severity/id/message` records and to distinguish warnings from parser errors. No current per-file MATLAB diagnostic is claimed until a normal-user smoke is rerun.
- The previous smoke reported `FAIL` for `run_sage_stage1_stage4_core.m`, `run_shared_core_regression.m`, and `build_rain_stage0.m`, while `default_sage_configuration.m`, `compute_sage_doppler_bound.m`, and `run_rain_sage_pipeline.m` were reported `PASS`. Because the old harness classified an unsupported `checkcode` diagnostic structure as failure, the old log alone cannot prove that all three were MATLAB parser errors.
- Shared-core state is now explicitly `IMPLEMENTED_BUT_NOT_VALIDATED` and `FROZEN_FOR_RAIN_MVP`. `run_sage_stage1_stage4_core.m` remains preserved and is not a Rain release gate; `run_shared_core_regression.m` remains preserved and is not being further repaired for Rain.
- Production audit found `run_nav_sage_pipeline.m` SHA-256=`95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0`, differing from the recorded pre-refactor validated hash `5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab`. No traceable backup or historical source bytes were found under the project or `E:\`; no manual reconstruction or untraceable restore was attempted. Therefore `PRODUCTION_PIPELINE_CURRENT_STATE=MODIFIED_BY_REFACTOR` and production must not be released as restored.
- New branch-local Rain files are `scripts/sage_pipeline/rain/run_rain_sage_stage1_stage4.m` (SHA-256=`da857b76b7d292be681196ee716c54d2162847f58e80ea12060efc316aec4208`), `default_rain_sage_configuration.m` (SHA-256=`3b66d369586a8e6fa264eb3f9c1361df552284997ba1d04adc2a92fed40b16f1`), and `compute_rain_doppler_bound.m` (SHA-256=`b8c3e3d20a5f13fbecdfc52beaa953f636c63ccc99ef67ac9ba0d7f5e098beca`). The Stage1–Stage4 numerical body is byte-identical to the extracted source body after the top-level function rename; no algorithm parameter or confirmed criterion changed.
- `run_rain_sage_pipeline.m` and `build_rain_stage0.m` no longer add or call `scripts/sage_pipeline/core`; Rain uses tracking+telemetry Stage0, explicit unavailable speed/geometry values, local configuration/fallback helpers, `Resume=false`, and `scenes/<scene>/sage_results/rain_sage_v1/<PRN>/` only. `run_rain_matlab_syntax_smoke.m` is Rain-only and calls the diagnostic helper with `Scope="rain"`.
- Static status after this route change: `py_compile=PASS`; explicit Python tests `142/142 PASS` (`root=102`, `core=13`, `rain=18`, `regression=9`). Current Rain standalone Stage1–Stage4 SHA-256=`ccf8071df74a86493f5e297c33cc928ae6670bf9432021526a87fb10199fe1dc`, standalone test SHA-256=`d99d1015700cafd1ebfb6b708c79ba2dffd6f082c34e1bae7d280b1f9aac97d5`, and provenance manifest SHA-256=`c7a155a5078d4412e3ac118c5ee20b32b25845626491c384e134101c778c7c1d`. No MATLAB, raw-IQ processing, G24 preflight, Rain SAGE, production SAGE, batch, or 20.46 MHz task was run. Rain remains `NOT_READY` until production restoration is traceably resolved and the Rain-only MATLAB syntax smoke passes.
- Required release gates are ordered: (A) recover/restore a traceable validated production source; (B) pass source-level Rain algorithm-equivalence audit; (C) Rain-only MATLAB syntax smoke with diagnostics; (D) G24 `PreflightOnly=true`; (E) one explicitly approved Rain SAGE task. No automatic continuation is allowed.

## 32. Emergency exact production-source recovery audit (Blocked, 2026-08-17)

- Commander emergency freeze required exact recovery of `scripts/sage_pipeline/run_nav_sage_pipeline.m` with historical validated SHA-256=`5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab`. The current production entry was rehashed as SHA-256=`95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0` (26,143 bytes).
- Before searching, the current modified bytes were preserved read-only at `dataset_generation_logs/darkroom_channel_emulation/production_pipeline_recovery_20260817/run_nav_sage_pipeline.modified_by_shared_core_refactor.m`; its SHA-256 is `95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0`. `current_modified_sha256.txt` records the same value. `CURRENT_MODIFIED_COPY_PRESERVED=YES`.
- The traceable candidate ledger is `dataset_generation_logs/darkroom_channel_emulation/production_pipeline_recovery_candidates.csv`, SHA-256=`c5ea97e258122a408a9c070b34189bb587c138dae4c6f50531e304f1d709b3e0`. It contains two same-name artifacts (current source and preserved modified copy), both hash `95f608ac...`, and zero exact-target matches. No historical source bytes were recovered.
- Search coverage included the project and E:\ same-name tree; relevant project backup/archive/copy names; the only project archive (`docs/paper_draft.zip`, no relevant `.m` entry); project logs, handoffs, manifests, receipts and provenance; Git status/top-level/remote/log/reflog/fsck (project and E:\ are not Git repositories; all Git history/object checks returned exit 128); `C:\Users\Jing_\AppData\Roaming\Code\User\History`; project `.history`; MATLAB/temp/autosave locations; OneDrive; File History; and Recycle Bin. The target SHA was found only as recorded provenance text, not as file content/source bytes.
- Therefore `PRODUCTION_VALIDATED_SOURCE_RECOVERY=BLOCKED` and `EXACT_HASH_NOT_FOUND=YES`. The production entry was not reconstructed, overwritten, or copied from shared core. `PRODUCTION_PIPELINE_SHA256=95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0`; `PRODUCTION_PIPELINE_FROZEN=NO` pending exact source recovery. No `PRODUCTION_SAGE_PIPELINE_FREEZE.md` was created because the sole freeze condition was not met.
- The recovery policy itself is frozen: `PRODUCTION_SAGE_PIPELINE_POLICY=FROZEN`, `FROZEN_TARGET_SHA256=5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab`, and Rain/shared-core/darkroom work must not modify the production entry. This policy freeze must not be confused with a successful byte-level recovery; the current file remains `PRODUCTION_PIPELINE_FROZEN=NO` until the target bytes are found and rehashed.
- The recovery state is also recorded in `dataset_generation_logs/darkroom_channel_emulation/rain_provenance_manifest.json`, now valid JSON with SHA-256=`34151d19a287d6467e72dbe4f4fb5bde5f231793816513fe4d15f9c9d2828269`, including the preserved-copy path, candidate-ledger hash, exact-target status, and no-production-modification assertion.
- Rain remains branch-local under `scripts/sage_pipeline/rain/`; the Rain branch did not modify the production entry during this audit. The user-reported normal-user Rain syntax smoke fact (`RAIN_MATLAB_SYNTAX_SMOKE=PASS`, `MATLAB_EXIT_CODE=0`) is retained as reported evidence and was not rerun by Codex. `RAIN_G24_PREFLIGHT=NOT_RUN` remains mandatory.
- No MATLAB, SAGE, G24 preflight, raw-IQ processing, batch execution, production restoration, or VTC/Paper update occurred. The unique next action is Commander direction or supply of a traceable exact historical source; do not reconstruct or run Rain/production before that.

## 33. Validated-equivalent production recovery preparation (Implemented + static Validated; MATLAB pending, 2026-08-17)

- Commander decision: `EXACT_HISTORICAL_SOURCE_RECOVERY=BLOCKED`; the route is now `VALIDATED_EQUIVALENT_PRODUCTION_RECOVERY=ACTIVE`. Further shared-core architecture work is frozen. The shared-core files and their regression harness remain audit evidence only; Rain remains paused.
- P0 created a project-local Git repository with a deliberately narrow `.gitignore` and committed the pre-recovery source state before restoration edits. Checkpoint commit: `0f9726e8be94af19064b2ac44cd007a61048730c`, message `checkpoint: preserve pre-recovery GNSS SAGE source state`. Raw/bulk files, SAGE outputs, generated logs, caches, and temporary/build artifacts were not staged.
- P2 damage audit: `dataset_generation_logs/darkroom_channel_emulation/production_refactor_damage_audit.md`. Available source evidence classified the shared-core change as interface adaptation/mechanical extraction; no source-level `ALGORITHM_CHANGE` or `UNKNOWN` item was identified. Numerical equivalence is still unvalidated and must not be inferred.
- Recovery provenance manifest: `dataset_generation_logs/darkroom_channel_emulation/rain_provenance_manifest.json`, current SHA-256=`2e012111e2ebe56c7c1118656c0f251b663c24f6e27970168b921143b4ab8705`; it records exact recovery blocked, the new validated-equivalent candidate, source/test hashes, and `PRODUCTION_PIPELINE_FROZEN=false`.
- P3 restored a new self-contained monolithic candidate at `scripts/sage_pipeline/run_nav_sage_pipeline.m`, SHA-256=`f1a16ceea6bcdafd46a85bce478d18e96f4dcd19e9bcb3991fb35b867e2b2088`. Stage1–Stage4, configuration, and Doppler-bound helper are local in this entry; there is no production `coreDirectory`, `addpath(core,...)`, or `run_sage_stage1_stage4_core` dependency. The old modified source remains preserved at `dataset_generation_logs/darkroom_channel_emulation/production_pipeline_recovery_20260817/run_nav_sage_pipeline.modified_by_shared_core_refactor.m` with SHA-256=`95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def0`.
- P5/P6 prepared, but did not run, the production-only MATLAB Code Analyzer smoke `scripts/sage_pipeline/regression/run_production_matlab_syntax_smoke.m` (SHA-256=`8b4de75ae9b84fa637e7896763bd24dd70d75e889e6c8c0fd1068a1f3d97ced3`) and protected G28 numerical replay harness `scripts/sage_pipeline/regression/run_production_recovery_regression.m` (SHA-256=`3cb5bb87d3cb058f63d444bd2d3eca0cb593b527498be0e568eecc634849991c`). The numerical harness fixes G28/ch1/10.23 MHz, passes `Resume=false`, regenerates Stage0 from copied non-raw inputs, compares against frozen baseline Stage0 and Stage1–Stage4 artifacts, and writes only to a fresh `dataset_generation_logs/darkroom_channel_emulation/production_recovery_<UTC>/` namespace. The baseline `scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G28` is never an output target.
- New static structure test: `scripts/sage_pipeline/regression/test_production_recovery_structure.py` (SHA-256=`e9175188c235ba6ba4913aa0fbc4b4fdc461be0b20fa380f387fa142dfc18a02`). Existing core structure tests were updated to distinguish the frozen audit copy from the new monolithic production route.
- Python `py_compile` passed. The compiled local Python verification passed `102/102` existing unit tests plus explicit core/Rain/shared-core-regression/production-recovery suites `13+11+7+9+6=46/46`, total `148/148 PASS`. No MATLAB, production SAGE, Rain SAGE, G24 preflight, batch task, raw-IQ processing, or 20.46 MHz task was run.
- Current gates:

```text
EXACT_SOURCE_RECOVERY=BLOCKED
VALIDATED_EQUIVALENT_RECOVERY=READY_FOR_MATLAB_VALIDATION
PRODUCTION_MATLAB_SYNTAX_SMOKE=NOT_RUN
G28_NUMERICAL_REGRESSION=NOT_RUN
PRODUCTION_PIPELINE_FROZEN=NO
RAIN_G24_PREFLIGHT=NOT_RUN
RAIN_SAGE_EXECUTION=NOT_STARTED
```

- The source restoration edits remain intentionally uncommitted after the checkpoint. Do not create `PRODUCTION_SAGE_PIPELINE_FREEZE.md`, commit/tag the restored candidate, run production/Rain, or resume any task until a normal Windows user `TJ-CHANNEL\\Jing_` runs the syntax smoke and then, only after syntax PASS, the protected G28 numerical replay. The sole next engineering action is that gated MATLAB validation.

## 32. GNSS-SDR weather-effect MVP audit (Completed + Validated, 2026-08-17)

- Added the read-only analysis tool `scripts/analysis/rain_gnss_sdr/audit_rain_gnss_sdr_mvp.py` (SHA-256 `7f4798f693fc1283d1d1a288c9336a6db0806ca8c7167791495a5f95d755391f`). It reads existing standardized GNSS-SDR artifacts only; it does not open raw IQ content, invoke the MATLAB executable, rerun GNSS-SDR, or run SAGE.
- The generated meeting package is frozen under `dataset_generation_logs/darkroom_channel_emulation/gnss_sdr_weather_mvp_20260817/`. It contains the summary, scene/PRN metrics, matched G24 comparison, field inventory, provenance, meeting brief, and four figures. Two superseded self-generated diagnostic directories were retained separately; no source artifact was deleted, moved, or overwritten.
- Artifact-backed channel mappings were validated as clear: ch3/G29, ch8/G13, ch10/G24, ch11/G12; midrain: ch8/G24, ch9/G20; heavyrain: ch1/G02, ch4/G31, ch7/G01. The only same-PRN weather comparison is clear G24/ch10 versus midrain G24/ch8; heavyrain is not a same-satellite matched comparison.
- The MVP reports receiver-level C/N0, tracking-valid fraction/duration, lock-continuity diagnostics, robust Doppler/code-frequency variation, telemetry/CRC, and observables evidence. Missing trajectory/geometry and unsupported weather-propagation conclusions remain explicitly unavailable/not established.
- Existing production-source provenance was checked before and after generation. The actual pre-existing source hash is `f1a16ceea6bcdafd46a85bce478d18e96f4dcd19e9bcb3991fb35b867e2b2088`, whereas the Commander request cited `95f608acb9c7920fcef88855c866fb74465e1a080893b1ea276ab00df838def`; this discrepancy was recorded and no rollback or source modification was performed.
- Engineering status: the GNSS-SDR weather-effect MVP is `Completed + Validated` as a read-only receiver-level audit. It is not a rain-propagation law, multipath model, geometry study, or production SAGE result. The existing protected pipeline/source-restoration gate remains unchanged.

## 34. G28 recovery result-container packaging fix (Implemented + static Validated; MATLAB pending, 2026-08-17)

- The normal-user G28 recovery run at `dataset_generation_logs/darkroom_channel_emulation/production_recovery_regression_20260817T123353Z/` reached Stage0, Stage1, Stage2, Stage3, and Stage4, then failed at `run_sage_stage1_stage4_local` result packaging. Stage4 CSV/MAT files were written before the failure; this is `FAILURE_CLASS=PRODUCTION_RECOVERY_RESULT_PACKAGING_ERROR`, not an algorithm regression.
- The localized MATLAB message quoted struct input argument positions 20 and 8. Input 8 is the `stage2Fits` value and input 20 is `jointFits`; both are non-scalar cell containers. The unsafe constructor could expand the result into a struct array. The tokens are argument positions, not literal array lengths 20 and 8.
- Fixed only the production result container in `scripts/sage_pipeline/run_nav_sage_pipeline.m`: initialize `result=struct()`, assign every Stage1–Stage4 output as a field, and assert `isscalar(result)`. No Stage numerical code, configuration, threshold, grid, model selection, path output, or confirmation criterion changed.
- The recovery harness `scripts/sage_pipeline/regression/run_production_recovery_regression.m` now captures the return value and asserts a scalar struct. Structural test: `scripts/sage_pipeline/regression/test_production_recovery_structure.py`.
- Fix report: `dataset_generation_logs/darkroom_channel_emulation/production_recovery_result_packaging_fix_20260817/result_packaging_fix_report.md`, SHA-256=`d9d58cea4eeb53d8911e2206ccf206650a35b359951489a59cb090868bc6567b`.
- Updated hashes: production source=`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`; recovery harness=`e0745a3dee9542d85089ea3f1189ffe258f2b65dac7c3a057e0ce5b0e6df4cf7`; structural test=`3fea7d444748f9eddfbac7be79a97189e8941fa5889b2295cbf1c24fe6b2297b`.
- Verification: `py_compile=PASS`, relevant production/core structure tests `20/20 PASS`, and `git diff --check=PASS`. The failed recovery namespace and protected G28 baseline remain unchanged and retained.

```text
EXACT_SOURCE_RECOVERY=BLOCKED
VALIDATED_EQUIVALENT_RECOVERY=INCOMPLETE
PRODUCTION_MATLAB_SYNTAX_SMOKE=NOT_RUN
G28_NUMERICAL_REGRESSION=NOT_RUN
PRODUCTION_PIPELINE_FROZEN=NO
RAIN_G24_PREFLIGHT=NOT_RUN
RAIN_SAGE_EXECUTION=NOT_STARTED
```

- The only next action is for normal Windows user `TJ-CHANNEL\\Jing_` to review and run the protected `run_production_recovery_regression` command. Codex must not launch MATLAB; do not run Rain, G24, production, or another task before that gate.

## 35. G28 recovery comparator indexing repair (Implemented + static Validated; MATLAB comparison pending, 2026-08-18)

- The normal-user G28 recovery run at `dataset_generation_logs/darkroom_channel_emulation/production_recovery_regression_20260817T152437Z/` completed Stage0, Stage1, Stage2, Stage3, Stage4, and output generation. MATLAB then exited with `表变量名称必须为字符串标量或字符向量。` in `compareTableFile` at the dynamic table access. The preserved run is classified `SAGE_EXECUTION_COMPLETED` plus `COMPARISON_HARNESS_FAILED`; numerical equivalence remains incomplete. This is `REGRESSION_COMPARATOR_TABLE_VARIABLE_INDEXING_ERROR`, not a SAGE, production-stage, or Stage4 failure.
- Root cause is mechanical MATLAB table-name indexing: `readtable(..., "VariableNamingRule", "preserve")` exposed `Properties.VariableNames` as a cell array of character vectors; iterating that cell array with `for name = reshape(...)` produced a 1-by-1 cell instead of a scalar character vector. The source had `exactNames` (not `commonNames`) as the equivalent common-name set. No comparison field was skipped and no tolerance was changed.
- `scripts/sage_pipeline/regression/run_production_recovery_regression.m` now normalizes cell/string/char table variable-name representations and extracts scalar character names before every dynamic table access. Stage0 table equality, Stage1 candidate detection, and Stage4 path identity use the same normalization. The harness also implements an optional `CompareExistingActualDir` read-only mode that validates the G28 context, confines the actual directory to the darkroom namespace, does not call `run_nav_sage_pipeline`, and writes only to a fresh comparison namespace.
- New harness SHA-256=`50ab8429cd12a9f687021690dbed396cf6aea2b821afd89ee52144fc1d42e080`. New comparator tests are `scripts/sage_pipeline/regression/test_production_recovery_comparator.py`, SHA-256=`78aee03b856307d5004a609efe032738180bd70d32f3e83ca13a878ff7568f21`; the updated structure test SHA-256=`86da644c614d29fbfd84df52185f9bbba10b7516a9fb0a35cb71188041c96d1`. The fix report is `dataset_generation_logs/darkroom_channel_emulation/production_recovery_comparator_fix_20260818/comparator_fix_report.md`, SHA-256=`df16522c9c8edd90880cae617189ca43ee1ebef440ffbe78dfc5b11c599a117`.
- MATLAB-free validation passed: all regression Python modules `py_compile=PASS`; production-recovery structure/comparator tests `16/16 PASS`; shared-core regression harness tests `9/9 PASS`; trailing-whitespace/diff hygiene `PASS`. No MATLAB, raw-IQ sample read, SAGE, G24 preflight, batch task, Rain run, or 20.46 MHz run occurred.
- The current production entry remains unchanged at SHA-256=`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`. The protected G28 baseline and the preserved interrupted/failed recovery artifacts remain unchanged. The preserved actual output contains `run_context.json`, `stage0_nav_catalog.mat`, and all required Stage1--Stage4 CSVs, so it is sufficient for a strict comparison-only replay; no SAGE rerun is required solely for this comparator repair.
- Current flags remain:

```text
EXACT_SOURCE_RECOVERY=BLOCKED
PRODUCTION_EXECUTION=PASS
VALIDATED_EQUIVALENT_RECOVERY=INCOMPLETE
PRODUCTION_PIPELINE_FROZEN=NO
RAIN_G24_PREFLIGHT=NOT_RUN
RAIN_SAGE_EXECUTION=NOT_STARTED
```

- The sole next action is for normal Windows user `TJ-CHANNEL\\Jing_` to review and run the comparison-only command recorded in `dataset_generation_logs/darkroom_channel_emulation/production_recovery_comparator_fix_20260818/comparator_fix_report.md`. Do not rerun G28 SAGE, run Rain/G24, start production, or process 20.46 MHz until that comparison result is independently reviewed.

## 36. G28 comparison path-canonicalization repair (Implemented + static Validated; MATLAB comparison pending, 2026-08-18)

- The first normal-user comparison-only retry failed before reading comparison tables because `isPathWithinRoot` rejected the actual directory even though it is physically under the darkroom namespace. The reported actual path was `E:/GNSS_Multipath_Project/dataset_generation_logs/darkroom_channel_emulation/production_recovery_regression_20260817T152437Z/project/scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G28`; the root is constructed from `fullfile(ProjectRoot, "dataset_generation_logs", "darkroom_channel_emulation")`. This is `FAILURE_CLASS=REGRESSION_HARNESS_PATH_NORMALIZATION_ERROR`, not a production or SAGE failure.
- The previous helper only replaced separators and applied a raw prefix comparison. It did not canonicalize absolute paths, resolve `.`/`..`, collapse duplicate separators, or make the path representation independent of MATLAB char/string behavior.
- `isPathWithinRoot` now canonicalizes both paths with `java.io.File.getCanonicalPath()` and a JVM-free lexical fallback, normalizes slash direction, resolves dot segments, compares case-insensitively, allows the root itself and descendants, enforces a separator directory boundary, and fails closed on canonicalization errors. No G28-specific allow-list or assertion bypass was added.
- Updated recovery harness SHA-256=`f3c520a9f9aad46f5a217d329a79edf4305096bd28f7d7f625c31d2a40fd1b0f`. Path/comparator test SHA-256=`3c35c0de3651dc1d774e1340abd3b323ff8ae99b941999ec3b5250e1727c7690`; path safety report=`dataset_generation_logs/darkroom_channel_emulation/production_recovery_path_safety_fix_20260818/path_safety_fix_report.md`, SHA-256=`3beb1f2c32c25aad76c7810ad703dea09c96dcaeece641b11035d68466f9b867`.
- MATLAB-free validation passed: production-recovery/comparator/path tests `19/19 PASS`; regression-module `py_compile=PASS`; path-fix whitespace and `git diff --check` `PASS`. No MATLAB, raw-IQ read, SAGE, Rain, batch, G24 preflight, or 20.46 MHz execution occurred.
- Production source remains unchanged at SHA-256=`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`. G28 baseline `run_context.json` remains SHA-256=`5f11979294f753ebae7656e3ee039e1525c6c96aebf76e2bd2aa2e07e37cda2f`; baseline last-write time remains 2026-08-06. The preserved actual output remains unchanged, and no comparison-only output namespace was created by the failed retry.
- Current flags remain:

```text
PRODUCTION_EXECUTION=PASS
NUMERICAL_EQUIVALENCE_COMPARISON=INCOMPLETE
VALIDATED_EQUIVALENT_RECOVERY=INCOMPLETE
PRODUCTION_PIPELINE_FROZEN=NO
RAIN_G24_PREFLIGHT=NOT_RUN
```

- The sole next action is for normal Windows user `TJ-CHANNEL\\Jing_` to run the updated comparison-only command in `dataset_generation_logs/darkroom_channel_emulation/production_recovery_path_safety_fix_20260818/path_safety_fix_report.md`. Stop after comparison and review; do not rerun SAGE or start Rain/production.

## 37. G28 comparison aggregate-pass repair (Implemented + MATLAB-free Validated; comparison pending, 2026-08-18)

- The normal-user `CompareExistingActualDir` run at `dataset_generation_logs/darkroom_channel_emulation/production_recovery_compare_existing_20260817T164259Z/` reached the final table comparison. All eight Stage1--Stage4 CSVs had equal baseline/actual row counts, equal visible categorical values, equal numeric values within the frozen tolerance, and `exact_mismatch_count=0`; the existing receipt also reports PASS for the Stage0 catalog and Stage1--Stage4 identity checks. The only contradictory fields were `pass=0` and `message=mismatch` on every row.
- Root cause was an `OVERALL_PASS_LOGIC_BUG` in `compareTableFile`: `emptyComparisonRecord()` initialized `record.pass=false`, and the old no-difference path retained that false value when aggregating categorical and numeric checks. The comparator therefore reported false despite passing comparison components. This is a comparator implementation failure, not evidence of a production/SAGE numerical regression.
- `scripts/sage_pipeline/regression/run_production_recovery_regression.m` now computes explicit row-count, column-count, variable-name-set, variable-order, variable-type, required-column, exact, categorical, numeric, and `overall_pass` components. The file-level aggregate is the AND of those required components; the final comparison also retains Stage0 catalog identity and baseline-unchanged gates. No tolerance was relaxed and no output column was ignored or reordered.
- The repaired harness writes `production_recovery_schema_comparison.csv` on the next fresh comparison-only run with column counts, missing/extra columns, order equality, imported MATLAB type equality, and type details. The old receipt did not contain imported type classes; they are intentionally not invented retroactively. A separate `confirmedEventPathIdentity` gate now explicitly compares Stage4 `joint_valid`, `joint_multipath_count`, `(center_window_id,path_id,is_multipath)`, and confirmed path counts.
- Current repaired hashes: comparator harness=`F62AA999E191767B52CA1AEC31B6F4CF8B3768F342638FE6A05E54BCEBF8A041`; comparator test=`DC5A2B653A3F0CF915DD1200F4D58D5E045EF47275A5DDFD3B5C059A6C17A909`; structure test=`86DA644C614D29FBFD84DFE52185F9BBBA10B7516A9FB0A35CB71188041C96D1`; report=`dataset_generation_logs/darkroom_channel_emulation/production_recovery_comparator_aggregate_fix_20260818/aggregate_pass_fix_report.md`, SHA-256=`ECC81CA2A49028E659C300F01380D1E102E60D4A27383BA79EC9C4D1D837F17D`.
- MATLAB-free verification passed: production-recovery/comparator/path tests=`22/22 PASS`, regression-module `py_compile=PASS`, and `git diff --check=PASS`. The protected production source remains `scripts/sage_pipeline/run_nav_sage_pipeline.m` SHA-256=`BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`. The protected G28 baseline and the existing actual recovery artifact remain unchanged. No MATLAB, raw-IQ read, SAGE, Rain, G24 preflight, batch, or 20.46 MHz task was run.
- The next comparison-only run is still required before declaring numerical equivalence complete. Until its repaired receipt and schema CSV are independently reviewed, status remains:

```text
PRODUCTION_EXECUTION=PASS
STAGE1_NUMERIC_COMPARISON=PASS (existing comparison evidence)
STAGE2_NUMERIC_COMPARISON=PASS (existing comparison evidence)
STAGE3_NUMERIC_COMPARISON=PASS (existing comparison evidence)
STAGE4_NUMERIC_COMPARISON=PASS (existing comparison evidence)
OVERALL_REGRESSION_PASS=INCOMPLETE_PENDING_REPAIRED_COMPARISON
VALIDATED_EQUIVALENT_RECOVERY=INCOMPLETE
PRODUCTION_PIPELINE_FROZEN=NO
RAIN_G24_PREFLIGHT=NOT_RUN
```

- The unique next action is for normal Windows user `TJ-CHANNEL\\Jing_` to run the comparison-only command in the aggregate-pass fix report and then review the new `comparison_summary.csv`, `production_recovery_schema_comparison.csv`, receipt, and explicit Stage4 confirmed identity. Do not rerun G28 SAGE, run Rain/G24, start production, or process 20.46 MHz before that review.

## 38. Production SAGE recovery finalized and frozen (Validated + Frozen; 2026-08-18)

- The final normal-user MATLAB comparison-only run is preserved at `dataset_generation_logs/darkroom_channel_emulation/production_recovery_compare_existing_20260817T170347Z/`. Its receipt SHA-256 is `A5B9390CA70EAE5F513EB3795B11DF4D0971B56210C41ED56C94B97624FA41FB`, status is `PASS`, `comparison_mode=existing_output_read_only`, `raw_iq_opened=false`, `sage_executed=false`, `MATLAB_EXIT_CODE=0`, and `PRODUCTION_REFACTOR_REGRESSION=PASS`.
- Final comparison evidence: `comparison_summary.csv` SHA-256=`BB70293F145218959E7A53CFB87D5231B54A8AA6E4EA88287500237525F226F7`; `production_recovery_schema_comparison.csv` SHA-256=`4AA43AC87E5EF0014C1812CC660CCED6D9CB9270456B6966A24A1F53303D0808`. All eight Stage1--Stage4 CSVs passed row count, column count, variable-name set, variable order, imported MATLAB types, required columns, exact fields, categorical fields, numeric tolerance, and overall checks; max absolute/relative errors are zero. Stage0 catalog identity and baseline unchanged also passed.
- The explicit Stage4 identity gate passed: `joint_valid`, `joint_multipath_count`, path identity including `is_multipath`, and confirmed event/path counts. The historical/recovered G28 baseline comparison is therefore validated equivalent under the frozen comparator. This does not change the scientific confirmation criterion.
- Validated production source: `scripts/sage_pipeline/run_nav_sage_pipeline.m`, SHA-256=`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`. The historical original SHA=`5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab` remains unrecovered; therefore `EXACT_SOURCE_RECOVERY=BLOCKED`, not PASS.
- The prior real full execution evidence is retained: Stage0 completed, Stage1 completed, Stage2 `54/54`, Stage3 completed, and Stage4 completed. The final freeze record is `dataset_generation_logs/darkroom_channel_emulation/PRODUCTION_SAGE_PIPELINE_FREEZE.md`, SHA-256=`E4D2854145A92C34AC51766A3B787512F3C25D237E62248F9CE0BF50FA2F27E7`.
- Production is now frozen and no longer depends on `scripts/sage_pipeline/core/`; the production entry is the validated-equivalent monolithic implementation. `SHARED_CORE_ROUTE=FROZEN_FOR_RAIN_MVP` remains in force. Rain branch, darkroom modeling, and shared-core work must not modify the frozen production entry or freeze record; every future Rain code task must verify the production SHA before and after.
- Final engineering states:

```text
EXACT_SOURCE_RECOVERY=BLOCKED
VALIDATED_EQUIVALENT_RECOVERY=PASS
PRODUCTION_EXECUTION=PASS
PRODUCTION_REFACTOR_REGRESSION=PASS
PRODUCTION_PIPELINE_FROZEN=YES
RAIN_MATLAB_SYNTAX_SMOKE=PASS
RAIN_G24_PREFLIGHT=NOT_RUN
RAIN_SAGE_EXECUTION=NOT_STARTED
```

- No Rain task, G24 preflight, production SAGE task, raw-IQ processing, or 20.46 MHz task was run in this closure. The next decision remains Commander-controlled; do not automatically start Rain or production after the freeze.
