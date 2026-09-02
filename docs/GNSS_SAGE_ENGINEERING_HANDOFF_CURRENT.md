# GNSS_SAGE 工程状态唯一交接文档

**项目根目录：** `E:\GNSS_Multipath_Project`  
**工程状态唯一来源：** 本文件  
**最后审计时点：** 2026-08-30（Asia/Shanghai）
**面向对象：** Codex、AI Agent、开发人员、实验执行人员  
**当前阶段：** accuracy-first full SAGE 主线的冻结 unattended batch 已完成并通过独立批后 QA：57/57 task-level QA ACCEPTED、0 REJECTED；其中 A validation batch 40 个保持 VALIDATED，B/C 正式生产 batch 17 个计入 formal accepted production。当前 formal accepted production 为 26/67（历史 A3 G16 仍为 REJECTED_PROTECTED，不计入）；SAGE 不再自动续跑，database schema/enum/label/derivation v1 已冻结，64-run event/path audit ingest、modeling-context alignment overlay 和 Stage4 path-parameter derivation 已完成并通过独立 QA。G06 legacy 已保留审计但排除建模输入；canonical r3 traditional channel model 及 Phase-1 scientific closure 已完成并通过独立 QA（带明确限制），Phase 2 仍为 planned-only。

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

## 39. Rain MVP static preflight and output-export preparation (Implemented + static Validated; execution pending, 2026-08-18)

- The standalone Rain task list was audited without reading raw-IQ contents, invoking MATLAB, or running SAGE. The nine planned tasks remain serialized and not started: Clear `G24/ch10`, `G29/ch3`, `G13/ch8`, `G12/ch11`; MidRain `G24/ch8`, `G20/ch9`; HeavyRain `G02/ch1`, `G31/ch4`, `G01/ch7`.
- Static preflight output: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_preflight_20260818.csv`. All 9/9 rows are `PASS_STATIC_INPUT_GATE`; this verifies metadata/path/size, 10.23 MHz `ishort` compatibility, tracking/telemetry presence and mapping, and output namespace absence. MATLAB field loading and Stage0 runtime validation remain pending normal-user execution.
- The Rain branch remains isolated under `scripts/sage_pipeline/rain/` and uses `rain_sage_v1/<PRN>` with new-only `Resume=false`. The only Rain-local source change is output export of phase and relative phase/amplitude from the already selected complex `alpha`; Stage1--Stage4 estimation, thresholds, grids, model order, persistence, joint validity, and confirmed-path criterion were not changed. Updated source hash: `run_rain_sage_stage1_stage4.m` = `B98EF879004A6E682227A82B3DA72BA8CA667939D1797FA4CC18AE41DDC34AB9`.
- Rain Python static/unit checks passed `36/36`, `py_compile` passed, PowerShell AST parsing passed, the deletion-command audit passed, and `git diff --check` passed. Normal-user Rain MATLAB syntax smoke is now recorded as `PASS`; the Code Analyzer warnings are non-fatal and were not used to justify algorithm edits.
- The one-start overnight runner is `scripts/sage_pipeline/rain/run_all_rain_sage_overnight.ps1` (static validated). Its read-only QA/summary helper is `scripts/sage_pipeline/rain/audit_rain_sage_overnight_outputs.py`. It uses a named mutex for serialization, runs G24 first as the global gate, continues independent later-task failures only after a valid G24 Stage0--Stage4 result, and never self-modifies source or resumes output.
- Production protection was rechecked after the Rain-local change: `scripts/sage_pipeline/run_nav_sage_pipeline.m` SHA-256 remains `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`, and its Git diff is empty. No production, reference, `nav_sage_v2`, raw-IQ, 20.46 MHz, or prior artifact was modified.

Current Rain gate state:

```text
RAIN_MATLAB_SYNTAX_SMOKE = PASS (normal-user evidence)
RAIN_G24_PREFLIGHT = STATIC_PASS_9_OF_9; RUNTIME_FIELD_LOAD_PENDING
RAIN_SAGE_EXECUTION = NOT_STARTED
RAIN_QA = NOT_STARTED
RAIN_OVERNIGHT_RUNNER = IMPLEMENTED_STATIC_VALIDATED
PRODUCTION_PIPELINE_FROZEN = YES
```

The only next action is for `TJ-CHANNEL\\Jing_` to start
`scripts/sage_pipeline/rain/run_all_rain_sage_overnight.ps1` once. It will run
Clear `G24/ch10` first and then apply the recorded serial policy; no Rain task
has yet executed and no G24 output receipt exists. MidRain and HeavyRain remain
gated until the overnight runner produces an independently reviewable G24 QA.

## 40. Overnight runner interface-gate repair (Implemented + static Validated; execution still not started, 2026-08-18)

- The first real runner start passed the production freeze gate and stopped before MATLAB with `OVERNIGHT_RUNNER_RAIN_INTERFACE_MARKER_VALIDATION_ERROR`. No MATLAB process started and no raw IQ was opened.
- Root cause was `MARKER_CHECK_TOO_BRITTLE`: the runner searched `run_rain_sage_pipeline.m` for the literal quoted text `"run_rain_sage_stage1_stage4"`, while the actual call is `coreResult = run_rain_sage_stage1_stage4( ... )` at lines 82--84. The Rain wiring was present; this was not `RAIN_INTERFACE_WIRING_MISSING`.
- Added `scripts/sage_pipeline/rain/validate_rain_interface.ps1`. It checks evaluator existence, the evaluator's primary function declaration, the whitespace/continuation-tolerant call relationship, and rejects production/shared-core calls. It does not remove the interface gate or allow-list a path.
- The corrected runner is `scripts/sage_pipeline/rain/run_all_rain_sage_overnight.ps1`, SHA-256 `E8E84EDA40A726D06860B018BB47AA96D51968FEF2006CFB1F1F6A8E879FB13B`; validator SHA-256 is `98841A3597A5E39D7433393AFCA649A03CDC559634CBCCE16D90E4F2DDF3220C`.
- Static validation passed: Rain Python suite `37/37`, interface positive/negative cases `6/6`, Python compile, PowerShell AST, deletion-command audit, and `git diff --check`. No runner re-execution was performed after the repair.

Current gate state remains:

```text
PRODUCTION_PIPELINE_FROZEN = YES
PRODUCTION_SHA = BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C
RAIN_STATIC_PREFLIGHT = 9/9 PASS
RAIN_MATLAB_SYNTAX_SMOKE = PASS (normal-user evidence)
RAIN_INTERFACE_GATE = PASS_AFTER_FIX (static actual-source validation)
RAIN_SAGE_EXECUTION = NOT_STARTED
```

The only next action is to start the same overnight command once as the normal
Windows user. The runner must still begin with Clear `G24/ch10`; no G24 result
or final Rain QA report exists yet.

## 41. Rain overnight runner Windows PowerShell 5.1 compatibility repair (Implemented + validated dry-run; execution not started, 2026-08-18)

- The second normal-user runner start failed before MATLAB with `找不到与参数名称“LiteralPath”匹配的参数。` and the catch-site line was reported as `run_all_rain_sage_overnight.ps1:545`. The actual unsupported call was a `New-Item -LiteralPath` invocation in the runner; Windows PowerShell 5.1 exposes `LiteralPath` for `Test-Path`, `Get-Content`, `Add-Content`, `Get-FileHash`, and `Import-Csv`, but not for `New-Item`. The catch line was only the reporting location, not the root cause.
- Fixed only the runner's directory-creation calls from `New-Item -LiteralPath` to `New-Item -Path`. The paths are runner-generated and contain no wildcard characters; input/path safety checks continue to use `-LiteralPath` on cmdlets whose PS5.1 parameter sets support it.
- The compatibility audit also found `ProcessStartInfo.ArgumentList`, which is not available through the .NET Framework path used by Windows PowerShell 5.1. MATLAB invocation now uses the legacy-compatible `ProcessStartInfo.Arguments` string with the existing `-batch` expression and unchanged `'Resume',false` semantics. The expression validator was corrected to match the actual quoted MATLAB name-value syntax `'<Resume>',false`; no execution parameter or scientific logic changed.
- Added `-DryRun`. It runs production freeze/tag/SHA checks, Rain interface validation, Python/MATLAB executable checks, static preflight and all nine task/output namespace checks, acquires/releases the global mutex, prints the planned MATLAB expressions, and does not start MATLAB, open raw IQ, execute SAGE, create Rain output, or create a run namespace.
- Top-level failures now emit `ERROR_MESSAGE`, `ERROR_COMMAND`, `ERROR_LINE`, `ERROR_LINE_NUMBER`, `ERROR_POSITION`, `ERROR_SCRIPT_STACK_TRACE`, `FULLY_QUALIFIED_ERROR_ID`, and `POWERSHELL_VERSION`, and return a nonzero exit code. Task-level failures remain recorded without deleting or resuming artifacts.
- New compatibility tests: `scripts/sage_pipeline/rain/test_rain_overnight_powershell_compatibility.py`. Windows PowerShell 5.1 AST parsing passed; Python `py_compile` passed for all 9 Rain Python files; Rain Python tests passed `43/43`; interface tests passed `6/6`; `git diff --check` passed.
- Windows PowerShell 5.1 dry-run passed with exit code 0: `OVERNIGHT_RUNNER_DRY_RUN=PASS`, `TASK_COUNT=9`, `MATLAB_STARTED=NO`, `RAW_IQ_OPENED=NO`, `SAGE_EXECUTED=NO`, `OUTPUT_SAGE_CREATED=NO`, and `GLOBAL_MUTEX_RELEASED=YES`. All nine expected Rain output namespaces remained absent.
- Updated runner SHA-256=`785AA510011FF0B7239026624F6F4BD723DA54313BF98F1C822AA32A44615C2C`. The frozen production entry remains SHA-256=`BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`, Git diff is empty, and tag `sage-production-recovered-validated` is present.

Current gate state:

```text
PRODUCTION_FREEZE_GATE=PASS
RAIN_INTERFACE_GATE=PASS
WINDOWS_POWERSHELL_5_1_AST=PASS
WINDOWS_POWERSHELL_5_1_DRY_RUN=PASS
MATLAB_STARTED=NO
RAW_IQ_OPENED=NO
RAIN_SAGE_STARTED=NO
RAIN_SAGE_EXECUTION=NOT_STARTED
GLOBAL_MUTEX_RELEASED=YES
FAILURE_CLASS=OVERNIGHT_RUNNER_WINDOWS_POWERSHELL_COMPATIBILITY_ERROR (fixed)
```

The next permitted action is for `TJ-CHANNEL\\Jing_` to review and run the
dry-run command recorded in the task report before any formal overnight start.

## 42. Rain overnight runner formal-path initialization and diagnostics repair (Implemented + validated; execution not started, 2026-08-18)

- The first formal overnight start after the PowerShell compatibility repair failed before MATLAB because the formal logger initialization used an undefined `${NewLine}` under `Set-StrictMode`. The prior dry-run branched before creating `RunDir`/`MasterLog`, so it could not expose this formal-only path. The fix uses `[Environment]::NewLine` and moves dry-run branching after the complete formal pre-MATLAB initialization block.
- The same run exposed a second failure in the new error handler: the expression `$diagnosticLine -replace pattern, replacement` was passed directly into `.WriteLine(...)`, allowing PowerShell to bind two method arguments and treat error text containing `{}` or `{0}` as a composite format string. Diagnostic output now constructs/sanitizes a completed string first and calls `WriteLine([string]$safeLine)` with one argument. A minimal console fallback is nested and fail-safe.
- Added `Test-ErrorDiagnosticsSafe`, covering ordinary text, null ErrorRecord/command, `{0}`, `{}`, Chinese text, multiline text, percent signs, and quotes. The formal initialization path runs this self-test before any MATLAB launch and records `ERROR_DIAGNOSTICS_NEVER_THROWS=PASS`.
- Dry-run now shares the formal path through mutex acquisition, unique run directory, master logger, task schedule, summary directory, diagnostics self-test, frozen production checks, Python/interface checks, all nine task preflight checks, and MATLAB expression construction. It stops before `Invoke-MatlabBatch`. Summary artifacts are scoped under the unique run namespace; historical root summary files from the failed run remain untouched and are explicitly preserved.
- Windows PowerShell 5.1 dry-run passed with exit code 0 in `dataset_generation_logs/darkroom_channel_emulation/rain_sage_overnight_20260817T181521Z/`: `OVERNIGHT_RUNNER_DRY_RUN=PASS`, `FORMAL_INITIALIZATION_PATH=PASS`, `FORMAL_PATH_RUNTIME_CHECK=PASS`, `ERROR_DIAGNOSTICS_NEVER_THROWS=PASS`, `MATLAB_STARTED=NO`, `RAW_IQ_OPENED=NO`, `SAGE_EXECUTED=NO`, `TASK_COUNT=9`, and `GLOBAL_MUTEX_RELEASED=YES`.
- Validation: Python `py_compile=PASS` for all 9 Rain Python files; Rain Python tests `46/46 PASS`; PowerShell 5.1 AST `PASS`; interface tests `6/6 PASS`; all nine Rain SAGE output namespaces remain absent; `git diff --check=PASS`.
- Updated runner SHA-256=`15F2D50A676F462E2F543086D7FE0D254612D756C8FC52881FE91941A05970F0`. The frozen production entry remains SHA-256=`BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`, production diff is empty, and tag `sage-production-recovered-validated` remains present.

Current gate state:

```text
PRODUCTION_FREEZE_GATE=PASS
RAIN_INTERFACE_GATE=PASS
FORMAL_PATH_RUNTIME_CHECK=PASS
ERROR_DIAGNOSTICS_NEVER_THROWS=PASS
WINDOWS_POWERSHELL_5_1_AST=PASS
WINDOWS_POWERSHELL_5_1_RUNTIME_DRY_RUN=PASS
MATLAB_STARTED=NO
RAW_IQ_OPENED=NO
RAIN_SAGE_STARTED=NO
RAIN_SAGE_EXECUTION=NOT_STARTED
GLOBAL_MUTEX_RELEASED=YES
FAILURE_CLASS=RUNNER_RUNTIME_INITIALIZATION_AND_ERROR_LOGGING_BUG (fixed)
```

No formal overnight command is released by this change; the next action remains
the reviewed `-DryRun` command only.

## 43. First formal Rain launch: MATLAB sandbox startup block (Validated failure; Rain execution incomplete, 2026-08-18)

- After the capture fix, the formal runner genuinely reached `TASK=1 START` for Clear `F1023_clear/G24/ch10` and logged `PROCESS_START`/`PROCESS_EXIT` for `D:\Program Files\Matlab\bin\matlab.exe`. The preserved run is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_overnight_20260817T182556Z/`.
- MATLAB returned exit code `1` before MATLAB code/Stage0 execution. stderr is `Fatal Startup Error: System Error: File system inconsistency`; stdout contains only the MATLAB-side failure result. G24 output directory does not exist and all Stage0--Stage4 counts are zero. This is `MATLAB_STARTUP_ENVIRONMENT_FAILURE`, not a Rain input or SAGE algorithm failure.
- The process-capture defect is resolved: stdout/stderr files were written successfully, task record and QA receipt were generated, and the runner stopped at the G24 global gate. The historical run incorrectly returned process exit 0 despite a software-failed G24; the runner now sets a nonzero exit code for `SOFTWARE_FAIL`/`INPUT_BLOCKED` and preserves the stop policy.
- Current Codex identity is `tj-channel\\codexsandboxoffline`; project evidence and the existing Windows execution design require non-elevated `TJ-CHANNEL\\Jing_`. No automatic cross-user `runas`, credential, or scheduled-task bridge exists or was created. A formal identity gate now rejects sandbox/elevated/wrong-user execution before MATLAB launch while leaving `-DryRun` available in Codex.
- A subsequent Windows PowerShell 5.1 dry-run passed after this gate: `FORMAL_INITIALIZATION_PATH=PASS`, `TASK_OUTPUT_CAPTURE_NEVER_THROWS=PASS`, `OVERNIGHT_RUNNER_DRY_RUN=PASS`, `MATLAB_STARTED=NO`, `RAW_IQ_OPENED=NO`, `SAGE_EXECUTED=NO`, and `GLOBAL_MUTEX_RELEASED=YES` in `rain_sage_overnight_20260817T182855Z`.
- No G24 partial output exists, so no move-to-trash action was necessary. The failed run, all logs, receipt, stdout/stderr, and summary artifacts remain retained.
- Updated runner SHA-256=`BB674546CCC518AAC6E45A96ECE7BAB117CF7B9CB69B25541AF9F1B44B00AB94`. Production entry remains SHA-256=`BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C` with empty Git diff and freeze tag present. Static/unit tests remain `46/46 PASS`, PowerShell 5.1 AST PASS, interface tests `6/6 PASS`, and `git diff --check` PASS.

Current gate state:

```text
PRODUCTION_SHA_UNCHANGED=YES
MATLAB_PROCESS_STARTED=YES (sandbox launch attempt)
MATLAB_STARTUP=FAILED_SYSTEM_ERROR_FILE_SYSTEM_INCONSISTENCY
MATLAB_CODE_ENTERED=NO
RAW_IQ_OPENED=NO
RAIN_STAGE0_STARTED=NO
RAIN_SAGE_EXECUTION=BLOCKED_BY_MATLAB_ENVIRONMENT
RAIN_G24_OUTPUT=ABSENT
RAIN_REMAINING_TASKS=NOT_STARTED
NORMAL_USER_IDENTITY_GATE=IMPLEMENTED
WINDOWS_POWERSHELL_5_1_RUNTIME_DRY_RUN=PASS
```

Completion now requires an external normal, non-elevated `TJ-CHANNEL\\Jing_`
PowerShell session. Codex must not retry MATLAB under the sandbox identity.

## Rain Stage0 telemetry table compatibility repair (Implemented; normal-user validation pending, 2026-08-18)

- The latest normal-user Rain launch reached `build_rain_stage0>readRainTelemetryDat` and failed at the telemetry table construction with MATLAB's equal-row-count error. The captured MATLAB diagnostic also explicitly reported that the string name-value syntax for `"VariableNames"` should use the character-vector form for backwards compatibility.
- Source inspection found no telemetry length or orientation defect: `readRainTelemetryDat` derives `recordCount` from 32-byte records, preallocates `towCurrentS`, `sampleCounter`, `towPreambleS`, `navSymbol`, and `prn` as `recordCount x 1` column vectors, and writes one scalar per record. The actual Clear G24 telemetry file is 70,592 bytes = 2,206 complete records; HeavyRain G02 is 91,680 bytes = 2,865 complete records; both have zero remainder.
- The only code change is in `scripts/sage_pipeline/rain/build_rain_stage0.m`: the table name-value parameter was changed from the MATLAB string form `"VariableNames"` to the character-vector form `'VariableNames'`. No `x(:)` normalization, truncation, padding, field replacement, raw-IQ read, or Stage1--Stage4 change was made.
- A static regression assertion was added to `scripts/sage_pipeline/rain/test_rain_standalone_pipeline.py`. Python compilation passed; the selected Rain read-only tests passed `36/36`; the PowerShell Rain interface tests passed `6/6`; source-level Rain MATLAB smoke checks passed. MATLAB runtime smoke was not run in the Codex sandbox.
- The frozen production entry remains unchanged: `scripts/sage_pipeline/run_nav_sage_pipeline.m` SHA-256 is `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C` and its Git diff is empty. No raw IQ, SAGE, overnight runner, nine-task batch, production artifact, or 20.46 MHz task was executed or modified.

Current Rain gate state:

```text
RAIN_STAGE0_TABLE_FIX = IMPLEMENTED
RAIN_TELEMETRY_LENGTH_ORIENTATION = VERIFIED_FOR_CLEAR_G24_AND_HEAVYRAIN_G02
RAIN_STATIC_TESTS = PASS (36/36 selected; destructive temporary-file tests not run)
RAIN_MATLAB_RUNTIME_SMOKE_AFTER_FIX = PENDING_NORMAL_USER
RAIN_G24_STAGE0_TO_STAGE4 = NOT_STARTED_AFTER_FIX
RAIN_HEAVYRAIN_G02_STAGE0_TO_STAGE4 = NOT_STARTED_AFTER_FIX
RAIN_OVERNIGHT_RUNNER = STOPPED_BY_COMMANDER
PRODUCTION_PIPELINE_FROZEN = YES
```

## 44. Long-term mainline C1 G03 canary completion (Completed + QA PASS, 2026-08-18)

- Commander authorization resumed the frozen 10.23 MHz mainline with `NEW_ONLY=true`, `RESUME_ALLOWED=false`, frozen manifest original order, and `MAX_PARALLEL_MATLAB=1`.
- The first eligible manifest task was executed exactly as frozen: `F1023_V120_D0121_P2/G03/ch2`. The production source remained unchanged at SHA-256 `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`; the manifest remained unchanged at SHA-256 `77C20C0ED6C84FA0348DB429948A8BD4900B2E8D86A6D8843B159B9A7A35CF00`.
- Immutable request: `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_c1_d0121p2_g03_20260818/execution_request.json`, SHA-256 `06ACB9FF1634C8B248ED6A46A63BF2E0BEE8934B61F8DE61CE56C11A56F5DC64`.
- Normal-user execution passed under `TJ-CHANNEL\\Jing_`, PowerShell `7.6.4`, MATLAB `25.1.0.2802752`; MATLAB startup smoke passed; task exit code and Python executor exit code were both `0`; runtime was `2073.646 s`.
- Execution log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260818T110255Z/batch_execution_log.csv`; wrapper receipts: `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_production_10mhz_c1_d0121p2_g03_20260818_20260818T110245152Z/`.
- Output: `scenes/F1023_V120_D0121_P2/sage_results/nav_sage_v2/G03/`. All 21 expected files are present and non-empty. Stage counts are 232 valid NAV symbols, 230 Stage0 windows, 230 Stage1 scans, 384 Stage2 model-order rows over 96 selected windows, 8 Stage3 reliable centers, and 8 valid Stage4 joint rows.
- Strict Stage4 classification: `joint_valid=1` for 8/8, `joint_multipath_count>0` for 0 rows, `is_multipath=1` for 0 paths. Result classification is `PASS_NO_CONFIRMED_MULTIPATH`; this is not a physical LOS conclusion.
- Independent QA: `docs/10MHz_FULL_SAGE_PRODUCTION_C1_G03_QA_REPORT.md`. Production monitoring summary and report were refreshed by `scripts/sage_pipeline/audit_10MHz_production_summary.py`.
- Accepted production state is now `8/67`: the prior 7 accepted tasks plus G03. Historical A3 G16 remains `REJECTED_PROTECTED` and is excluded from acceptance. The next eligible queue task is `F1023_V120_D0121_P2/G24/ch2`; 58 frozen eligible tasks remain after G03.
- No production source, manifest, protected artifact, VTC/Paper artifact, Rain/Darkroom artifact, event database, statistical model, or 20.46 MHz task was modified or started by this update.

## 45. C1 G24 completion and independent batch handoff (2026-08-19)

- G24 (`F1023_V120_D0121_P2/G24/ch2`) completed through the normal-user wrapper with request SHA-256 `0C1AE58403396F5C68D2C952C493DBC7733ACC6989882B5DE26ED8ADAAB19676`, task/runtime `11185.234 s`, MATLAB and executor exit code `0`, and explicit `Resume=false`.
- Final output `scenes/F1023_V120_D0121_P2/sage_results/nav_sage_v2/G24/` contains 21/21 non-empty expected files. Stage0=`8265` symbols/`8257` windows; Stage1=`8257` scanned; Stage2=`208` model rows/`52` selected windows; Stage3=`0` reliable centers; Stage4=`0` joint rows. Strict confirmed events/paths=`0/0`; this is a valid zero-event output, not a physical LOS conclusion.
- Independent QA: `docs/10MHz_FULL_SAGE_PRODUCTION_C1_G24_QA_REPORT.md`. Production monitoring summary refreshed. The current round added two accepted tasks: G03 and G24; accepted production is `9/67`, A3 G16 remains `REJECTED_PROTECTED`, and `57` eligible tasks remain.
- Codex-managed continuation is stopped. Independent runner: `scripts/sage_pipeline/Run-UnattendedMainlineBatch.ps1`, started by Scheduled Task `GNSS-SAGE-Unattended-Mainline-20260819` as normal `TJ-CHANNEL\\Jing_`, with queue first task G25, serial single-MATLAB policy, runner state/heartbeat/log and shared lock verified.
- Mainline source SHA remains `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`; manifest SHA remains `77C20C0ED6C84FA0348DB429948A8BD4900B2E8D86A6D8843B159B9A7A35CF00`. No database, elevation matching, statistical modeling, VTC/Paper, Rain/Darkroom, or 20.46 MHz work was started.

The next permitted actions are the two explicitly scoped normal-user MATLAB
commands for Clear `G24/ch10` and HeavyRain `G02/ch1`; do not start the
overnight runner or any other Rain task from this change.

## Rain Stage0 VariableNames container repair (Implemented; runtime validation pending, 2026-08-18)

- The first compatibility repair correctly changed the name-value parameter to `'VariableNames'`, but the next normal-user run exposed that the value was still a cell array of string scalars. MATLAB requires a string array or a cell array of character vectors for multiple table variable names.
- The telemetry table has exactly five data columns and now supplies exactly five non-empty character-vector names in one container: `{'tow_s', 'sample_counter', 'preamble_tow_s', 'nav_symbol', 'prn'}`. No telemetry data shape, length, orientation, or field semantics were changed.
- The static regression assertion in `scripts/sage_pipeline/rain/test_rain_standalone_pipeline.py` now rejects the old nested string-cell form and requires the character-vector cell form. Python compilation, selected Rain tests `36/36`, Rain interface tests `6/6`, source static smoke, production SHA check, and `git diff --check` passed.
- `scripts/sage_pipeline/run_nav_sage_pipeline.m` remains unchanged at SHA-256 `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`. MATLAB runtime validation after this second fix remains pending a normal non-elevated `TJ-CHANNEL\Jing_` session. No raw IQ, SAGE, overnight runner, batch, production artifact, or file deletion was performed.

The only released next commands remain the separately scoped Clear `G24/ch10`
and HeavyRain `G02/ch1` normal-user MATLAB commands; no G31 or overnight command
is released at this stage.

## Rain Stage1–Stage4 result-container packaging repair (Implemented; runtime validation pending, 2026-08-18)

- The normal-user Clear `F1023_clear/G24/ch10` run completed Stage1 (`2204/2204`), Stage2 (`120/120`), Stage3 persistence, and wrote the Stage4 joint artifacts before failing while returning the result from `run_rain_sage_stage1_stage4.m`.
- The failure is a result-container packaging error, not a Stage1–Stage4 numerical failure. The unsafe `struct(...)` constructor treated the non-scalar cell fields `stage2Fits` and `jointFits` as struct-array expansion inputs. In the historical error text, input argument `8` is the `stage2Fits` value and input argument `20` is the `jointFits` value; these numbers are constructor argument positions, not literal array lengths.
- The preserved G24 MAT artifact reports `stage2Fits=120x1` and `jointFits=3x1`. The written Stage4 CSV/MAT artifacts contain three joint rows, all `joint_valid=1`, `joint_multipath_count=0`, and three non-multipath paths; therefore the existing computation is retained as a zero-confirmed-event result pending independent QA.
- The Rain result block now uses scalar initialization plus field assignment and asserts `isstruct(result) && isscalar(result)`. This is `OUTPUT_RESULT_PACKAGING_FIX_ONLY`; no Stage1–Stage4 algorithm, threshold, grid, model selection, optimizer, or confirmation criterion changed.
- Added `scripts/sage_pipeline/rain/test_rain_result_packaging.py` and updated the source-equivalence test to allow this explicit container-only delta. Python `py_compile` and the selected Rain static/regression suite pass `17/17`; MATLAB runtime syntax smoke remains not run under Codex.
- The production entry remains unchanged at SHA-256 `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`. Existing G24 Stage1–Stage4 artifacts were not modified, deleted, moved, or resumed. No HeavyRain, batch, overnight, raw IQ, or MATLAB execution was performed.

Current Rain gate state:

```text
RAIN_RESULT_PACKAGING_FIX = IMPLEMENTED
RAIN_RESULT_PACKAGING_SCALAR_STRUCT = PASS
G24_STAGE1_STAGE2_STAGE3 = COMPLETE_FROM_PRESERVED_ARTIFACTS
G24_STAGE4_OUTPUT = COMPLETE_FROM_PRESERVED_ARTIFACTS
G24_CONFIRMED_EVENTS = 0
G24_CONFIRMED_PATHS = 0
RAIN_MATLAB_RUNTIME_VALIDATION = PENDING_NORMAL_USER
RAIN_G24_RERUN_REQUIRED = NO_FOR_EXISTING_STAGE4_ANALYSIS
RAIN_OVERNIGHT_RUNNER = STOPPED_BY_COMMANDER
PRODUCTION_PIPELINE_FROZEN = YES

## 46. Long-term mainline unattended batch reconciliation (Completed + QA PASS, 2026-08-25)

- The frozen unattended run `dataset_generation_logs/batch_sage_unattended/run_20260819T004818Z/` completed all 57 queued requests. Its retained runner state remains `completed_pending_batch_qa`; the external independent QA is now complete. MATLAB had exited naturally and no batch lock remained.
- Independent QA evidence is `docs/10MHz_FULL_SAGE_UNATTENDED_BATCH_20260819_QA_REPORT.md`, SHA-256=`11aa8f99f7e0245cd074ad31e1229d5c3cf803d1d071e5d0b64162a68a7dadf8`. Request/receipt cardinality is 57/57; all task receipts and execution logs are completed with exit code 0 and explicit `Resume=false`.
- All 57 tasks passed request/provenance/hash, output completeness, run-context identity, Stage0/Stage1, Stage2, Stage3, Stage4 linkage, finite-path and strict Stage4 confirmation QA. The batch contains 40 `A_pipeline_validation_batch` tasks, 14 `B_main_production_batch` tasks and 3 `C_long_running_batch` tasks; these labels match the frozen manifest exactly.
- Aggregate new-batch evidence: Stage0/Stage1 windows=`162864/162864`; Stage2 selected windows=`5639`; Stage3 reliable centers=`420`; Stage4 joint rows=`284`, all `joint_valid`; strict confirmed events/paths=`88/93`. Twenty-six tasks produced zero confirmed events under the current Stage4 criterion; these remain valid zero-event outputs, not physical-LOS conclusions.
- The authoritative monitoring outputs were refreshed by `scripts/sage_pipeline/audit_10MHz_production_summary.py`: `dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv` (77 rows, SHA-256=`097fec8ea82d3ef2dcbad8156be0b35a767c68be1e83ab8630bf9cdd3849e183`) and `production_summary_report.md` (SHA-256=`f8b1aac77cd22e30dff866944408918856acbe4827ae6b2f148e155fc74c1ee2`). All 57 new rows are `completed/PASS`, with no missing required files or warnings, and point to the batch QA report.
- Formal accepted production is now `26/67`: the previous reconciled `9/67` plus the 17 B/C tasks. The 40 A tasks are `VALIDATED` only and are not counted as formal accepted production. Historical A3 G16 remains `REJECTED_PROTECTED`; no artifact was promoted, overwritten, resumed or deleted.
- Frozen source, wrapper, executor, manifest and inventory hashes remain unchanged: production source=`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`, wrapper=`dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3`, executor=`bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b`, manifest=`77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`, inventory=`af368feba90797584d7690d4927ed32de604651a5a62662f4adce348a89e4bb4`.
- Current frozen-manifest queue reconciliation: `NOT_STARTED_ELIGIBLE=0`; the 57 queued tasks are now completed/QA-classified, and the only excluded manifest artifact is protected historical A3 G16. No database, geometry join, channel-parameter derivation or statistical modeling was started.

```text
MAINLINE_BATCH_QA = PASS (57/57)
FORMAL_ACCEPTED_PRODUCTION = 26/67
VALIDATED_ONLY_BATCH_A = 40
REJECTED_PROTECTED = 1 (historical A3 G16)
NOT_STARTED_ELIGIBLE = 0
EVENT_PATH_DATABASE = PLANNED / NOT COMPLETE
CHANNEL_PARAMETER_DATABASE = PLANNED / NOT COMPLETE
GEOMETRY_ALIGNMENT = PARTIAL
STATISTICAL_CHANNEL_MODEL = NOT STARTED
```

This reconciliation phase read no raw IQ and did not start MATLAB/SAGE/batch; it created only the QA evidence and refreshed designated monitoring outputs. Paper Handoff does not require a scientific update because no paper fact, figure, table, or claim changed. The next permitted step was database-rule freeze followed by a read-only dry-run validator; that gate is now recorded in Section 47, and formal ingest/statistical modeling remain blocked.
```

## 47. Event/path database rules freeze and read-only dry-run (Completed + PASS, 2026-08-25)

- Frozen v1 rule artifacts are `dataset/multipath_event_database/v1/_schema/schema.json`, `enums.json`, `label_rules.json` and `derivation_manifest.json`. They define normalized run/window/candidate/event/path/context grains, immutable provenance fields, enum values, units, null policy, strict Stage4 confirmation and the formal-write boundary.
- The strict confirmation rule is unchanged and explicit: `joint_valid=1 AND joint_multipath_count>0 AND corresponding stage4_joint_paths.is_multipath=1`, with summary/path multipath counts required to agree. A zero-event run remains `no_confirmed_event`, never an automatic physical LOS label; `los_reference` requires an explicit reference/control designation.
- Read-only validator implementation is `scripts/event_database/validate_sage_database_dry_run.py`; its unit tests are `scripts/event_database/tests/test_validate_sage_database_dry_run.py`. The validator reads only request/manifest/provenance, run_context and Stage0–Stage4 CSVs; it does not open raw IQ, start MATLAB/SAGE or alter any existing artifact.
- Dry-run evidence is `dataset_generation_logs/multipath_event_database_dry_run_20260825/database_dry_run_report.md` and `database_dry_run_result.json`. Result is `PASS`: current unattended batch `57/57` task namespaces PASS, reference seven-PRN regression PASS, with one retained warning for legacy G06 missing `run_context.json`.
- Current batch aggregate dry-run counts reproduce Stage0 windows=`162864`, Stage2 selected windows=`5639`, Stage3 reliable centers=`420`, Stage4 rows=`284`, strict confirmed events/paths=`88/93`. Reference fixture reproduces `8/11` confirmed events/paths.
- The only created database namespace content is `_schema`; no `facts`, `dimensions`, `labels`, `exports`, event/path tables or channel-parameter tables were written. Event-level geometry context remains `deferred_unavailable`; time alignment and channel-parameter derivation are not complete.
- Frozen source/wrapper/executor/manifest/inventory hashes remain unchanged: `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`, `dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3`, `bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b`, `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`, `af368feba90797584d7690d4927ed32de604651a5a62662f4adce348a89e4bb4`.

```text
DATABASE_RULES_V1 = FROZEN
DATABASE_DRY_RUN = PASS (57 batch + 7 reference)
FORMAL_DATABASE_INGEST = COMPLETED_WITH_WARNINGS (Section 48)
DATABASE_FACT_TABLES = NOT WRITTEN
EVENT_GEOMETRY_CONTEXT = DEFERRED_UNAVAILABLE
CHANNEL_PARAMETER_DERIVATION = NOT STARTED
STATISTICAL_CHANNEL_MODEL = NOT STARTED
NEXT_DECISION_REQUIRED = MODELING-READINESS QA COMPLETE; AUTHORIZE GEOMETRY/SCENE-CONTEXT QA OR HOLD
```

## 48. Formal event/path audit ingest and independent QA (Completed + PASS, 2026-08-25)

- The explicitly authorized next step created the new versioned partition `dataset/multipath_event_database/v1/partitions/ingestion_id=ingestion_20260825_event_path_v1/` and manifest `dataset/multipath_event_database/v1/manifests/ingestions/ingestion_20260825_event_path_v1.json`.
- Independent ingest QA is `PASS`: 64 unique runs (57 current batch + 7 reference), 308 unique Stage4 event rows, 412 Stage4 path rows, strict confirmed events/paths=`96/104`, unique parent/child keys and table hashes consistent.
- G06 legacy is not deleted. Its source/event/path audit rows remain in the partition, while `exports/modeling_eligibility.csv` marks exactly one G06 run as `excluded_legacy_context_missing` and `include_in_modeling_ready_input=0` because no `run_context.json` exists. No timestamp or channel context was fabricated.
- Five geometry summary PRN-missing warnings are recorded in `qa/ingestion_issues.csv`; event-time `event_utc`, elevation and azimuth remain null with `geometry_join_status=deferred_unavailable`. Run-level geometry summaries are retained only as context.
- The ingest wrote only the new versioned database partition and manifest/report. It did not modify existing SAGE artifacts, raw files, manifest, requests, metadata, inventory, pipeline, wrapper or executor. No channel parameters or statistical models were computed.
- Ingest evidence is `dataset_generation_logs/multipath_event_database_ingest_20260825/ingestion_report.md`. Paper Handoff remains unchanged because no paper fact, figure, table or claim changed.

```text
DATABASE_RULES_V1 = FROZEN
EVENT_PATH_AUDIT_INGEST = COMPLETED_WITH_WARNINGS + INDEPENDENT_QA_PASS
INGEST_RUNS = 64
INGEST_EVENTS = 308
INGEST_PATHS = 412
STRICT_CONFIRMED = 96 EVENTS / 104 PATHS
G06_MODELING_INPUT = EXCLUDED_LEGACY_CONTEXT_MISSING
EVENT_GEOMETRY_CONTEXT = DEFERRED_UNAVAILABLE
CHANNEL_PARAMETER_DATABASE = NOT STARTED
STATISTICAL_CHANNEL_MODEL = NOT STARTED
NEXT_DECISION_REQUIRED = AUTHORIZE GEOMETRY/SCENE-CONTEXT QA OR HOLD; STATISTICAL MODELING STILL BLOCKED
```

## 49. Modeling-readiness QA (Completed + BLOCKED, 2026-08-25)

- This section records the pre-alignment blocker snapshot; it is superseded by the completed alignment overlay and independent QA in Section 50 below. It is retained for provenance rather than as the current modeling status.
- Modeling-readiness evidence is `dataset_generation_logs/multipath_event_modeling_readiness_20260825/qa_report.md` and `qa_result.json`.
- The audit partition is structurally valid, but modeling readiness is **BLOCKED**: 308 event-context rows have `0/308` verified event-time geometry joins; all 13 scene-context rows remain `not_annotated`; time alignment is `0/13 verified`; five run/PRN geometry summaries have missing requested PRNs.
- Acceptance classes are preserved: 17 formal accepted production, 40 validated-only A batch, and 7 reference validation. These classes are not silently merged into a single modeling claim.
- G06 legacy is explicitly excluded from modeling-ready input (`excluded_legacy_context_missing`, exactly one run) while its source/event/path audit rows remain retained. No deletion or source modification occurred.
- No channel parameters or statistical model was computed. The next required gate is independently verified geometry/time alignment and scene-context annotation, followed by explicit authorization before statistical modeling.

```text
MODELING_READINESS = BLOCKED
EVENT_GEOMETRY_VALID = 0/308
TIME_ALIGNMENT_VERIFIED = 0/13
SCENE_CONTEXT_ANNOTATED = 0/13
G06_MODELING_INPUT = EXCLUDED
CHANNEL_PARAMETER_DERIVATION = NOT STARTED
STATISTICAL_CHANNEL_MODEL = NOT STARTED
NEXT_DECISION_REQUIRED = AUTHORIZE GEOMETRY/SCENE-CONTEXT QA WORK OR HOLD
```

## 50. Modeling-context alignment overlay (Completed with exclusions + independent QA PASS, 2026-08-25)

- This section records the alignment-only snapshot before channel-parameter derivation; its `CHANNEL_PARAMETER_DERIVATION = NOT STARTED` line is superseded by Section 51 below. It is retained for provenance.
- The original modeling block was an implementation gap in the first audit-to-modeling context layer: the ingest intentionally emitted placeholder values (`event_utc=null`, null geometry, `deferred_unavailable`, `not_annotated`, and unverified time alignment) even though the frozen Stage0/NMEA/RINEX/geometry sources and validated scene metadata were available. This did not indicate a MATLAB/SAGE production failure.
- A new immutable overlay partition was created at `dataset/multipath_event_database/v1/partitions/alignment_id=alignment_20260825_tow_geometry_scene_v1/`. The prior audit partition, SAGE artifacts, raw files, requests, production manifest, wrapper, executor and frozen inventory were not modified.
- Time alignment uses the frozen GPS--UTC offset of 18 seconds, the RINEX/NMEA calendar-date anchor, and Stage0 TOW. All 13/13 scene anchors are verified. Geometry uses same-scene, same-PRN nearest GSV within 5 seconds; no interpolation or scene-average substitution is used.
- The overlay contains 64 modeling runs, 308 event-context rows, 284/308 events with valid geometry, 100 confirmed paths environment-ready, and 84 confirmed paths elevation-ready. G06 legacy remains retained for audit but its 2 events/4 paths are excluded from modeling because the legacy context is missing. Ten events have the requested PRN absent from the geometry timeseries, and twelve events exceed the 5-second nearest-geometry tolerance; these exclusions are explicit in `qa/alignment_issues.csv`.
- Independent QA is `PASS` in `dataset_generation_logs/multipath_event_modeling_alignment_qa_20260825/qa_report.md` and `qa_result.json`. It verifies table counts/hashes, unique keys, 13/13 time alignment, G06 fail-closed behavior, exact exclusion counts, and frozen source/wrapper/executor/production-manifest/inventory hashes.
- This is an engineering data-alignment completion only. No raw IQ was read, and no MATLAB/SAGE/batch task was started. Channel-parameter derivation and statistical modeling remain unstarted. Paper Handoff remains unchanged because no paper fact, figure, table or claim was changed.

```text
MODELING_CONTEXT_ALIGNMENT = COMPLETED_WITH_EXCLUSIONS
MODELING_CONTEXT_ALIGNMENT_QA = PASS
TIME_ALIGNMENT_VERIFIED = 13/13
EVENT_GEOMETRY_VALID = 284/308
ENVIRONMENT_READY_CONFIRMED_PATHS = 100
ELEVATION_READY_CONFIRMED_PATHS = 84
G06_MODELING_INPUT = EXCLUDED_LEGACY_CONTEXT_MISSING
CHANNEL_PARAMETER_DERIVATION = NOT STARTED
STATISTICAL_MODELING = NOT STARTED
NEXT_DECISION_REQUIRED = AUTHORIZE CHANNEL-PARAMETER DERIVATION OR HOLD
```

## 51. Stage4 path-parameter derivation (Completed + independent QA PASS, 2026-08-25)

- The explicitly authorized derivation created the new versioned namespace `dataset/multipath_event_database/v1/partitions/parameter_set_id=parameters_20260825_stage4_path_v1/` and QA evidence `dataset_generation_logs/multipath_event_channel_parameter_qa_20260825/`.
- The derivation consumes only the QA-passed alignment overlay. It produces bounded Stage4 path quantities: excess delay in seconds, excess path length in meters, signed relative Doppler, relative power provenance, confirmed-path counts, and descriptive event/environment/elevation summaries.
- Result counts are 100 environment-ready confirmed paths, 94 represented confirmed events, 84 elevation-ready paths, 4 environment groups and 3 elevation groups. Sixteen paths remain in the environment population but are excluded from elevation summaries because event-level geometry is unavailable/inconclusive.
- Independent QA is `PASS`: table counts/hashes, Stage4-only semantics, unit conversions, event aggregation, environment/elevation denominators, exclusion accounting, source/alignment hashes, frozen production hashes and unchanged source partition were all rechecked.
- RMS delay spread, Doppler spread, Ricean K-factor, path lifetime and fitted distribution families remain `NOT_DERIVED`; no complete statistical channel model was produced. This is descriptive parameter derivation, not statistical modeling.
- No raw IQ was read, and no MATLAB/SAGE/batch task was started. Existing SAGE artifacts, alignment/source partitions, requests, production manifest, wrapper, executor and inventory were not modified. Paper Handoff and the VTC Evidence Matrix were updated to record the new paper-usable evidence; the manuscript body and figures were not changed.

```text
CHANNEL_PARAMETER_DERIVATION = COMPLETED_WITH_EXCLUSIONS
CHANNEL_PARAMETER_DERIVATION_QA = PASS
DERIVED_CONFIRMED_PATHS = 100 ENVIRONMENT / 84 ELEVATION_READY
DERIVED_CONFIRMED_EVENTS = 94
DESCRIPTIVE_SUMMARY_GROUPS = 4 ENVIRONMENT / 3 ELEVATION
STATISTICAL_CHANNEL_MODEL = NOT STARTED
NEXT_DECISION_REQUIRED = AUTHORIZE STATISTICAL MODELING OR HOLD
```

## 52. Environment-conditioned receiver lock-loss model (Completed with limitations + implementation QA PASS, 2026-08-26)

- A standalone tracking-only analysis tool, `scripts/analysis/build_environment_lock_model.py`, was implemented and executed in the immutable namespace `dataset_generation_logs/channel_modeling/environment_lock_model_v1_20260826_r2/`. It resolves modeling inputs through the existing event-database/alignment provenance and reads only existing GNSS-SDR tracking MAT fields; it does not read raw IQ or invoke MATLAB, SAGE or batch.
- The build includes 63 environment-eligible runs out of 64 audit runs. The one G06 legacy run is retained in `excluded_runs.csv` and excluded from modeling because `run_context.json` is missing. The build extracted 48 debounced tracking-diagnostic lock-loss intervals from 894,470 tracking records (808,133 valid and 86,337 inconclusive records).
- The frozen diagnostic semantics are `carrier_lock_test < -0.5` for `LOCK_BAD`, 20 ms bad-lock confirmation, 100 ms good reacquisition, sample-counter time at 10.23 MHz, explicit `INCONCLUSIVE_GAP` handling, acquisition ambiguity exclusion and terminal right-censoring support. Gaps were not bridged and no physical signal-loss claim is made.
- The environment-conditioned entry-rate output uses a Gamma-Poisson posterior with fixed shape/rate prior `(1, 1 s)`; the duration candidates were lognormal, Weibull and Gamma, with Gamma selected by global AICc and deterministic tie-break. Environment support is explicit: Highway/Open is `PARTIAL_POOLING_REQUIRED`; Mountain/Valley, Special Reflective and Urban are `DATA_SUPPORTED_WITH_GROUPED_VALIDATION`. The actual output contains zero terminal right-censored events, although the likelihood implementation supports them.
- Final output manifest SHA-256 is `21c04938cba559b3e042806b093eba82e4e86a44977e95831c715aa03ffc97a5`; the model-builder source SHA-256 is `980eb2de3c8e1375119c1a5fd6f26a73bffe2c76b3f9b6211062468a4562b3e4`; the existing read-only MAT-reader source SHA-256 is `7f4798f693fc1283d1d1a288c9336a6db0806ca8c7167791495a5f95d755391f`.
- The complete result report is `docs/ENVIRONMENT_CONDITIONED_LOCK_MODEL_V1_REPORT.md`. The model output and receipt record `raw_iq_read=false`, `matlab_executed=false`, `sage_executed=false` and `batch_executed=false`. The protected production source remains unchanged at SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
- This is `ENVIRONMENT_LOCK_LOSS_MODEL = COMPLETED_WITH_LIMITATIONS` and `MODEL_IMPLEMENTATION_QA = PASS` for a bounded receiver-tracking diagnostic/simulation layer. It is not the path-level multipath statistical channel model and does not complete elevation-conditioned lock-loss modeling, path lifetime modeling or statistical channel modeling.

```text
ENVIRONMENT_LOCK_LOSS_MODEL = COMPLETED_WITH_LIMITATIONS
ENVIRONMENT_LOCK_MODEL_IMPLEMENTATION = IMPLEMENTED
ENVIRONMENT_LOCK_MODEL_QA = PASS
ENVIRONMENT_LOCK_MODEL_RUNS = 63 ELIGIBLE / 1 G06 EXCLUDED
ENVIRONMENT_LOCK_MODEL_EVENTS = 48
MULTIPATH_STATISTICAL_CHANNEL_MODEL = NOT STARTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
NEXT_DECISION_REQUIRED = AUTHORIZE OR HOLD LOCK-LAYER INTEGRATION INTO THE DARKROOM GENERATOR
```

## 53. Environment × elevation confirmed-NLOS path distribution model (Completed with sparse prior cells + independent QA PASS, 2026-08-26)

- The authorized Python-only modeling step built the new-only namespace `dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/` from the frozen Stage4 path partition `dataset/multipath_event_database/v1/partitions/parameter_set_id=parameters_20260825_stage4_path_v1/`. No raw IQ, tracking input, MATLAB/SAGE execution, batch task or 20.46 MHz data was accessed.
- Source and configuration provenance are frozen: source SHA-256=`2a44913d1c06f78d2748428b1d72f1b4712a6b5d3f33fc598a14fe17a3e3414a`, configuration SHA-256=`94ffdd882e70c2217e51a06deff7466bcccfc25f78d505f2d8dd9d4807bf2cb7`, and model manifest SHA-256=`4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c`. The protected production pipeline remains SHA-256=`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
- The model uses 100 environment-ready confirmed multipath paths, 84 event-level elevation-ready paths and 16 paths retained only for environment/global parents. All 12 environment×elevation cells are represented; Urban–LOW and Highway/Open–LOW are exact `PRIOR_ONLY` cells. The output contains 36 cell marginal records and environment-level, not unsupported cell-level, Gaussian-copula dependence.
- Frozen grouped selection selected lognormal for `relative_delay_ns`, Laplace for signed `relative_doppler_hz`, and normal for `relative_power_db`; fitting used scene-block leave-one-scene-out validation. The dB-to-linear amplitude transform is `10^(relative_power_db/20)` and positive relative-power values were not clipped.
- Independent QA is `PASS_WITH_LIMITATIONS` in `dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/independent_qa_report.md`, with source/label, cell coverage, marginal, copula, normalization, deterministic QA-draw, bootstrap and hash checks passing. The two prior-only cells and sparse support limitations are explicit; no universal empirical validity is claimed.
- This is a bounded conditional confirmed-NLOS path-distribution layer, not the complete darkroom generator or a complete physical channel model. Main/common-path gain and absolute power, phase, lock-loss composition, occurrence/path count, path lifetime and fixed four-path millisecond output remain deferred. The previously completed receiver lock-loss model remains a separate layer.

```text
PATH_DISTRIBUTION_MODEL = COMPLETED_WITH_SPARSE_PRIOR_CELLS
PATH_DISTRIBUTION_MODEL_QA = PASS_WITH_LIMITATIONS
PATH_DISTRIBUTION_SOURCE = STAGE4_CONFIRMED_MULTIPATH_ONLY
PATH_DISTRIBUTION_CELLS = 12 (2 PRIOR_ONLY)
PATH_DISTRIBUTION_MARGINALS = 36
DARKROOM_GENERATOR = NOT STARTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = AUTHORIZE SEPARATE MAIN-GAIN/PHASE/LOCK/PATH-COMPOSITION DESIGN OR HOLD
```

## 54. Main-path common-gain and observable fade model (Completed with limitations + independent QA PASS, 2026-08-26)

- The authorized Python-only build created the new-only namespace `dataset_generation_logs/channel_modeling/main_path_common_gain_fade_v1_20260826_r4/` from existing GNSS-SDR tracking records and verified time/geometry provenance. It did not read raw IQ, invoke MATLAB, invoke SAGE, start batch execution or process 20.46 MHz data. The earlier implementation-failure/diagnostic namespaces were retained and were not overwritten.
- The build resolved 63 environment-eligible runs and 63 unique physical tracking inputs, representing 894,470 tracking records (808,133 valid and 86,337 inconclusive). It produced 307,572 canonical 20 ms grid rows and 91 observable fade events, including 30 right-censored events.
- Scientific semantics are frozen and explicit: common gain is a per-run-normalized tracking C/N0 proxy; `common_gain_linear=10^(common_gain_db/20)` is a relative amplitude scale; it is not calibrated RF power and path 0 is not asserted to be physical LOS. The fixed fade rule is 3 dB for 20 ms to enter and 1 dB for 100 ms to exit. LOCK_BAD, gaps and record ends are not treated as exact fade depth.
- Geometry uses same-scene, same-PRN nearest GSV within 5 s without interpolation or scene-average substitution. All 12 environment×elevation cells have explicit gain support records. Direct fade-event support is limited: Highway/Open has 13/7/7 events in LOW/MID/HIGH, while the other nine cells inherit environment parents and are marked `PRIOR_ONLY`; Highway/Open MID/HIGH remain sparse partial-pooling cells.
- Deterministic scene-grouped selection chose Student-t for normal common gain, lognormal for observable fade depth and Gamma for observable fade duration. These are bounded empirical choices, not universal physical laws. Phase, absolute power, NLOS activation, path count/lifetime, lock-recovery mapping and the complete four-path generator remain outside this layer.
- Independent QA is `PASS_WITH_LIMITATIONS` in `dataset_generation_logs/channel_modeling/main_path_common_gain_fade_v1_20260826_r4/independent_qa_report.md` and `independent_qa_result.json`. Model manifest SHA-256 is `6f36dab892622c9b9dc61ecde91fda85ff12ca60eeea4f81fe37760f0acb1e45`; config SHA-256 is `5baeb0567baf6b24b018c923f50709375271c653d330e6f1888b0469befa9b77`; protected production pipeline SHA remains `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
- The bounded model report is `docs/MAIN_PATH_COMMON_GAIN_FADE_MODEL_V1_REPORT.md`. This completion changes the status of the main/common-gain observable-fade layer only; it does not mark the complete darkroom generator or final statistical channel model as completed.

```text
MAIN_PATH_COMMON_GAIN_FADE_MODEL = COMPLETED_WITH_LIMITATIONS
MAIN_PATH_COMMON_GAIN_FADE_MODEL_QA = PASS_WITH_LIMITATIONS
MAIN_PATH_COMMON_GAIN_FADE_MODEL_RUNS = 63 ELIGIBLE / 63 UNIQUE_PHYSICAL
MAIN_PATH_COMMON_GAIN_FADE_MODEL_GRID = 307572 20MS ROWS
MAIN_PATH_COMMON_GAIN_FADE_MODEL_EVENTS = 91 (30 RIGHT_CENSORED)
MAIN_PATH_COMMON_GAIN_FADE_MODEL_GEOMETRY_ROWS = 173498 VALID
ABSOLUTE_RF_POWER_MODEL = NOT_AVAILABLE
PHYSICAL_LOS_GAIN_CLAIM = NOT_ALLOWED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = AUTHORIZE OR HOLD DARKROOM COMPOSITION INTEGRATION
```

## 55. Fixed three-NLOS-slot activation model (Completed with limitations + independent QA PASS_WITH_LIMITATIONS, 2026-08-26)

- 按已批准的固定三槽位计划完成了 Python-only、new-only 离线构建，输出位于 `dataset_generation_logs/channel_modeling/nlos_slot_activation_v1_20260826_r1/`。model manifest SHA-256=`b47b2a09f9acc5f1ccd65dcf923623dbeea27e3aec3e3e3f04c2e094a3e486d2`，配置 SHA-256=`bd8d3aec2c576598a3ddeb0c24f14c520c0e5e6d1f7c8d321c5d586380da04aa`。
- 输入为 63 个 modeling-eligible runs、169,637 个全量 Stage0 40 ms 窗口、94 个严格 Stage4 confirmed events 和 100 条 confirmed NLOS paths；94 个事件的连续 center ±2 closure 共 470 个 membership。缺少 `run_context.json` 的 G06 legacy run 保留审计但不进入模型。
- 模型结构冻结为两层：`Z~Bernoulli(p_stage4_confirmed_support_active[environment,elevation])`，active 时 `K~Categorical(q1,q2,q3)`；K=0/1/2/3 映射到 `000/100/110/111` 三个 NLOS 槽位。occupancy 是 scene-balanced confirmed-support proxy；multiplicity 只来自 event-level confirmed path count。零确认暴露不是 LOS，也不是物理上无多径的证明。
- 12 个 environment×elevation cell 均有输出；Urban–LOW、Highway/Open–LOW 的 exposure 有但没有直接 confirmed event，相关条件层明确保留有限支持/先验语义。全局 confirmed event 的 K 分布为 `89/4/1`（K=1/2/3）。
- 固定槽位契约包括：主径外置；active slot 按 delay/linear-amplitude/Doppler/source ID 稳定排序；inactive slot 为 `PathActive=0`、`INACTIVE_NO_PATH`、amplitude=0、delay/Doppler/phase=null；块内固定，不宣称跨块 reflector identity。
- 独立 QA 位于该 namespace 的 `independent_qa_report.md` 和 `independent_qa_result.json`，结果 `MODEL_QA=PASS_WITH_LIMITATIONS`、`READY_FOR_GENERATOR_COMPOSITION=YES`。source、Stage4 label、exposure/closure、occupancy、multiplicity、slot、determinism、namespace/hash hard gates 均通过；稀疏 cell 和 proxy 语义仍是限制条件。
- 构建使用 `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`（Python 3.12.9 / NumPy 2.5.1 / SciPy 1.18.0 / OpenBLAS 0.3.33.112.0），执行策略固定为 raw IQ/MATLAB/SAGE/batch/20.46 MHz 全部 false；受保护的 `run_nav_sage_pipeline.m` SHA-256 仍为 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。
- 正式技术报告为 `docs/NLOS_SLOT_ACTIVATION_MODEL_V1_REPORT.md`。本层已可作为后续暗室生成器组合输入，但 final four-path generator、phase、lock-loss composition、path lifetime/inter-block persistence、absolute power 和物理 occurrence model 仍未完成；不得把该层标为完整统计信道模型。

```text
NLOS_SLOT_ACTIVATION_MODEL = COMPLETED_WITH_LIMITATIONS
NLOS_SLOT_ACTIVATION_MODEL_QA = PASS_WITH_LIMITATIONS
NLOS_SLOT_ACTIVATION_MODEL_READY_FOR_GENERATOR_COMPOSITION = YES
NLOS_SLOT_ACTIVATION_RUNS = 63 ELIGIBLE / 1 G06 LEGACY EXCLUDED
NLOS_SLOT_ACTIVATION_EXPOSURE = 169637 STAGE0 WINDOWS / 470 CLOSURE MEMBERSHIPS
NLOS_SLOT_ACTIVATION_EVENTS_PATHS = 94 EVENTS / 100 CONFIRMED NLOS PATHS
DARKROOM_FOUR_PATH_GENERATOR = NOT STARTED
PHYSICAL_MULTIPATH_OCCURRENCE_MODEL = NOT_IDENTIFIED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = AUTHORIZE SEPARATE DARKROOM COMPOSITION INTERFACE DESIGN OR HOLD
```

## 56. Lock-state amplitude/phase/recovery composition layer (Completed with limitations + independent QA PASS_WITH_LIMITATIONS, 2026-08-26)

- 按已批准的 lock-state amplitude/phase/recovery 计划完成了 Python-only 离线实现。代码为 `scripts/analysis/channel_modeling/lock_amplitude_phase_recovery_core.py`、`build_lock_amplitude_phase_recovery_model.py` 和 `audit_lock_amplitude_phase_recovery_model.py`；retry3 配置为 `configs/channel_modeling/lock_amplitude_phase_recovery_v1_retry3.json`。实现只读取既有派生 CSV/CSV.GZ/JSON，不读取 raw IQ，不运行 MATLAB/SAGE/batch，不处理 20.46 MHz。
- 最终结果使用独立 new-only namespace `dataset_generation_logs/channel_modeling/lock_amplitude_phase_recovery_v1_20260826_r3/`。model manifest SHA-256=`9eb1847eac27618f80475ceafe62616285a346c5da847afdb0e8f2c5fc63a3ee`；配置 SHA-256=`5d4230149629e77d0f77a54197a32361dfa877e87ad8980fa7274d89a3ba3efc`；build receipt=`build_receipt.json`；独立 QA=`independent_qa_result.json`/`independent_qa_report.md`。
- 结果 accounting：48 个 environment-eligible lock events、307,572 行 common-gain 20 ms grid、3,249 行 recovery trace、16,384 个确定性 scalar draws 和 256 个确定性状态序列。特征状态为 19 个 observed recovery、15 个 right-censored recovery、11 个 continuity-gap inconclusive 和 3 个 no-valid-baseline；没有把缺失、断点或记录结束伪造成 physical outage/LOS。
- 冻结语义为 environment-only lock timing、`carrier_lock_test < -0.5`、20 ms bad-lock debounce、100 ms good stability、显式 `INCONCLUSIVE_GAP` 和 right-censoring。common gain 是 run-normalized tracking C/N0 amplitude proxy；`10^(common_gain_db/20)` 不是绝对 RF power。失锁包络同时作用于 path 0 和 active NLOS 槽位，但 path 0 不被断言为 physical LOS 或最强路径。
- 相位没有从数据拟合，使用外部假设 `Uniform(-pi,pi)` 初相及每 1 ms 的 Doppler 连续演化；lock loss/recovery 不重置相位。inactive NLOS slot 为 amplitude=0、delay/Doppler/phase=null。默认 `EMPIRICAL_DIAGNOSTIC_PROXY` 不保证硬件物理失锁；强制 stress 模式必须由用户显式提供正值 floor 并标记 `ASSUMPTION_ONLY`。
- 独立 QA 的 source provenance、gain alignment、lock timing、amplitude mapping、recovery envelope、phase continuity、inactive-slot semantics、determinism、namespace/hash 和 protected-pipeline gates 全部通过；状态为 `MODEL_QA=PASS_WITH_LIMITATIONS`、`READY_FOR_GENERATOR_INTEGRATION=YES`、`HARDWARE_LOCK_LOSS_CALIBRATED=NO`。r1 partial build 和 r2 self-referential-manifest QA failure 均保留在各自 namespace，未删除、覆盖、resume 或静默修复。
- 正式技术报告为 `docs/LOCK_AMPLITUDE_PHASE_RECOVERY_MODEL_V1_REPORT.md`。该层是受限 receiver-diagnostic/simulation composition layer，不是完整 statistical channel model、absolute-power calibration、物理失锁概率模型或四路径毫秒级生成器；`STATISTICAL_CHANNEL_MODEL` 与 `DARKROOM_FOUR_PATH_GENERATOR` 仍未完成。下一步仅为独立 generator-composition interface 设计和验证，必须继续沿用 immutable parent/hash/new-only 安全边界。

```text
LOCK_AMPLITUDE_PHASE_RECOVERY_MODEL = COMPLETED_WITH_LIMITATIONS
LOCK_AMPLITUDE_PHASE_RECOVERY_IMPLEMENTATION = IMPLEMENTED
LOCK_AMPLITUDE_PHASE_RECOVERY_QA = PASS_WITH_LIMITATIONS
LOCK_AMPLITUDE_PHASE_RECOVERY_READY_FOR_GENERATOR_INTEGRATION = YES
LOCK_AMPLITUDE_PHASE_RECOVERY_HARDWARE_CALIBRATED = NO
ABSOLUTE_RF_POWER_CALIBRATION = NOT_AVAILABLE
PHASE_DATA_FIT = NO_EXTERNAL_ASSUMPTION_ONLY
DARKROOM_FOUR_PATH_GENERATOR = NOT_STARTED
STATISTICAL_CHANNEL_MODEL = NOT STARTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = AUTHORIZE SEPARATE GENERATOR COMPOSITION INTERFACE DESIGN OR HOLD
```

## 57. Darkroom four-path generator v1 implementation and 120 ms preview (Implemented; full independent QA pending, 2026-08-27)

- 按已批准的四路径暗室参数生成计划新增了 `configs/channel_modeling/darkroom_four_path_generator_v1.json`、`scripts/analysis/channel_modeling/darkroom_generator_core.py`、`prepare_darkroom_generator_request.py` 和 `run_darkroom_four_path_generator.py`。实现只组合已冻结的派生模型，不读取 raw IQ，不运行 MATLAB/SAGE/batch，不处理 20.46 MHz；受保护 production pipeline SHA-256 仍为 `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C`。
- 已通过核心聚焦测试 `9 passed` 和 `py_compile`。这表示当前生成器为 `Implemented`，不表示完整独立 QA、12-cell QA 或 darkroom export gate 已完成。
- 已生成新的 120 ms 只读预览 request/run：`dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_requests/preview_120ms_urban_mid_20260827/` 与 `dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_runs/preview_120ms_urban_mid_20260827/`。request SHA-256=`44cd052ba358284df6e8a2149cd05432e54d18a2a5914aee2662b05756c621a1`；canonical table 为 480 行，严格七列；预览使用 `Urban × MID`、seed=`20260827`、`CONDITIONAL_ACTIVE_STRESS`，仅用于检查四槽位格式，不是 production 或物理多径结论。
- 当前唯一下一步是由用户检查该 120 ms 表；未经后续独立 auditor/全量 QA，不得将生成器标记为 `Validated`，不得声称已完成暗室统计信道模型。

```text
DARKROOM_FOUR_PATH_GENERATOR = IMPLEMENTED
DARKROOM_FOUR_PATH_GENERATOR_QA = NOT_STARTED
DARKROOM_120MS_PREVIEW = GENERATED_FOR_USER_REVIEW
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = REVIEW_120MS_PREVIEW_BEFORE_FULL_GENERATOR_QA
```

## 58. Multi-elevation fixed-four-slot generator v2 contract revision (Planned / Not started, 2026-08-27)

- 用户检查 v1 120 ms preview 后明确修订最终暗室接口：一个环境 request 必须同时输出 `Low`、`Mid`、`High`；每毫秒顺序固定为 `Low path0–3 → Mid path0–3 → High path0–3`，共 12 行，120 ms 应为 1440 行。
- “固定四条路径”被澄清为固定四个结构槽位，不是四条物理路径始终非零激活。NLOS 1/2/3 仍由已冻结 activation model 决定 active mask；inactive slot 的 canonical amplitude 为 0，但 delay、Doppler、phase 必须保留完整有限的 latent 数值，CSV 不允许空字段。inactive latent values 不得解释为 active/confirmed multipath。
- 正式 v2 实施计划为 `docs/superpowers/plans/2026-08-27-darkroom-multi-elevation-four-slot-generator-v2.md`，SHA-256=`D4ADC54555B99F9B24559A1AE662C3F9EF3DEC38DAF3418DEEDA5860FB79040B`。计划要求全新 v2 config/source/request/run/auditor namespace，并冻结 `INTER_SATELLITE_CORRELATION_NOT_MODELED`、`LATENT_INACTIVE_PARAMETER_NOT_PHYSICAL_PATH` 和 prior/support provenance。
- v1 代码、request、preview 和 hash 均保留为历史 artifact；本次只更新计划和工程路线，没有实现 v2、没有生成 v2 参数表、没有运行 Python generator/MATLAB/SAGE/batch。

```text
DARKROOM_GENERATOR_V1 = IMPLEMENTED_PREVIEW_ONLY_NOT_TARGET_CONTRACT
DARKROOM_GENERATOR_V2 = PLANNED_NOT_STARTED
V2_ROWS_PER_MILLISECOND = 12
V2_INACTIVE_NLOS_AMPLITUDE = 0
V2_INACTIVE_NLOS_DELAY_DOPPLER_PHASE = COMPLETE_LATENT_VALUES
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = USER_APPROVAL_TO_IMPLEMENT_V2_PLAN
```

## 59. Multi-elevation fixed-four-slot generator v2 implementation and preview (Implemented; preview QA passed, full regression pending, 2026-08-27)

- 已在 v1 独立 namespace 之外实现 v2 基础设施：`scripts/analysis/channel_modeling/darkroom_generator_v2_core.py`、`prepare_darkroom_generator_v2_request.py`、`run_darkroom_generator_v2.py` 和独立 `audit_darkroom_generator_v2.py`。v2 保留冻结父模型和 v1 correlation/model semantics，只改变多仰角固定结构槽位输出合同。
- v2 合同已实现为一个环境 request 同时输出 `Low`、`Mid`、`High`；每个毫秒按 `Low path0–3 → Mid path0–3 → High path0–3` 输出 12 行。inactive NLOS 槽位保留有限 latent delay/Doppler/phase，canonical `RelativeAmplitude=0`，不得解释为物理传播路径。
- 固定预览 request：`dataset_generation_logs/channel_modeling/darkroom_generator_v2_requests/preview_120ms_urban_all_bands_v2_20260827_r3/generation_request.json`，request SHA-256=`ddb6b26405184601b89d2c85e2934001c683f06795a938b0247e23d46920eb37`。环境为 `Urban`，持续 120 ms，seed=`20260827`，三仰角同时生成；v2 config SHA-256=`d38588144ce6775a959ba15f52f633923915ec9d146a910ea1239aba0326a50b`。
- 成功预览输出 namespace：`dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/preview_120ms_urban_all_bands_v2_20260827_r3/`。canonical `darkroom_channel_parameters.csv` 恰有 1440 行、7 列固定顺序，SHA-256=`03950978902164737bc77e632734954a3908889713aa836bb9175dacb419c949`；独立 QA `independent_qa_result.json` SHA-256=`8a0299b67aa8722408be4f3e9288c169d767057dc5dec4cb53e68eff390934f7`，`overall_pass=true`。
- 独立 gold-blind QA 已通过：请求/配置/父模型/源文件/受保护 pipeline hash、v2 namespace、三仰角完整性、12 行/毫秒、无空 canonical 字段、固定槽位、inactive 零幅度、块内参数与相位递推均通过；120 ms 共 3 个 40 ms block/仰角，1080 个 NLOS 行为 inactive latent zero-amplitude。此结果是参数生成预览，不是 raw IQ、MATLAB、SAGE 或论文实测结果。
- v2 生成期间的早期失败 namespace（无覆盖行为）均保留为诊断证据：`preview_120ms_urban_all_bands_v2_20260827`、`_r1`、`_r2`；最终 r3 使用全新 request/run namespace。v1 config、v1 source、v1 request/run 和受保护 `run_nav_sage_pipeline.m` 均未修改。
- v2 聚焦 py_compile/pytest 为 `15 passed`。完整 `scripts/analysis/channel_modeling/tests` 回归为 `106 passed, 1 failed`；该失败来自既有 v1 测试 payload 未提供当前 v1 校验所要求的 `request_purpose`，不是本次 v2 source 修改造成，v1 测试/代码未被改写。v2 全环境 12-cell regression 尚未完成，不能将 v2 标记为全量 `Validated`。

```text
DARKROOM_GENERATOR_V1 = IMPLEMENTED_PREVIEW_ONLY_NOT_TARGET_CONTRACT
DARKROOM_GENERATOR_V2 = IMPLEMENTED_PREVIEW_QA_PASS_FULL_REGRESSION_PENDING
DARKROOM_120MS_V2_PREVIEW = GENERATED_1440_ROWS_INDEPENDENT_QA_PASS
V2_ROWS_PER_MILLISECOND = 12
V2_INACTIVE_NLOS_AMPLITUDE = 0_WITH_FINITE_LATENT_PARAMETERS
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = USER_REVIEW_OF_120MS_V2_PREVIEW_BEFORE_LONGER_OR_MULTI_ENVIRONMENT_RUN
```

## 60. Multi-elevation fixed-four-slot generator v2.1 all-positive NLOS contract (Implemented; 120 ms preview QA PASS, 2026-08-27)

- 按用户批准的 v2.1 变更完成了独立 Python-only 生成基础设施。v2.1 不修改 v2.0 的数学/模型源文件，而是复用 v2.0 的父模型、随机流、40 ms block、common gain/fade/lock 和相位递推语义；新的 slot contract 将 NLOS 1/2/3 定义为条件性场景中的始终激活槽位，并要求每条输出 NLOS `RelativeAmplitude` 严格大于 0。
- 该 all-positive 规则是 `CONDITIONAL_MULTIPATH_SCENARIO`，不是对真实环境多径发生率的结论，也不表示每个物理观测必然存在三条 NLOS 路径。v2.1 明确记录 `ACTIVATION_MODEL_NOT_USED_FOR_GENERATION`；旧 v2.0 的 empirical activation、zero-amplitude inactive-slot 结果继续作为 immutable 历史 artifact，未被覆盖、修改或重命名。
- 新配置为 `configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2_1.json`，SHA-256=`55befd54988b1aa8838e10a02deae7126305156013283ad52a8c449731ac5814`。v2.1 source hashes 为：core=`a2205bb43698e6c27f2e31a09e532a4cbafd10cafda04b69390d081d959e6a56`、request preparer=`bd14dceabe09b3a153be9bbb2e05799f7a04db49918db2890fb81120b2800e6f`、runner=`097290e97fef3342192cb815c6a08100e79d25a0ca418c4a8d6dfeca10d9b8de`、auditor=`3ae3798756a67ad76ecf290ef41249d6c6096b212d8b58b39643218b19aa5aa8`。受保护的 `run_nav_sage_pipeline.m` SHA-256 仍为 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。
- v2.1 request preparer、new-only runner 和独立 auditor 分别位于 `scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_1_request.py`、`run_darkroom_generator_v2_1.py` 和 `audit_darkroom_generator_v2_1.py`；core 位于 `darkroom_generator_v2_1_core.py`。执行策略固定为 raw IQ/MATLAB/SAGE/batch/20.46 MHz 全部 false，request 必须 all bands、12 rows/ms、new-only，且只能写入 v2.1 namespace。
- 最终 preview request namespace 为 `dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_requests/preview_120ms_urban_all_bands_v2_1_20260827_r1/`，request SHA-256=`f35af78cd2043d68c95ca55ff70aff080e3319fd0f550d8ec50adadddaf563dd`。输出 namespace 为 `dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_runs/preview_120ms_urban_all_bands_v2_1_20260827_r1/`；环境=`Urban`、持续=`120 ms`、seed=`20260827`、三仰角同时输出。canonical `darkroom_channel_parameters.csv` 为 1440 行、固定七列，SHA-256=`474ea2780d591ec9e0391414190a30c7b7b446c334a03ba96621491be9ba076a`；generation manifest SHA-256=`b5c22c97d802ad6fbcefaea6bc43e09daf915225056acb3ea02e7f6126d01b4b`；generation receipt SHA-256=`55c866bc93302c68dac1cbf1314dddd8e83b6b6e11201075a743ecc389549ece`。
- 生成前 runner validation-only 也由独立 request `dataset_generation_logs/channel_modeling/darkroom_generator_v2_1_requests/validation_only_v2_1_20260827/generation_request.json` 验证通过，request SHA-256=`889d0458fe184a01947ad07c1c25af3d63a9ee8e8248870ebc754ee943a4a03b`，`execution_eligible=true`、`generation_requested=false`、`raw_iq_read=false`；对应 run namespace 未创建。
- preview 结果 accounting：`1440` rows、`360` receiver-timeline rows、`27` block-catalog rows、`1080` path-slot rows；NLOS 1/2/3 共 `1080/1080` 行严格为正，inactive NLOS 行=`0`，所有 block 和 slot activation mask=`111`。首行顺序保持 `Low path0–3 → Mid path0–3 → High path0–3`。
- 独立 gold-blind QA 位于该 output namespace 的 `independent_qa_report.md` 和 `independent_qa_result.json`，QA result SHA-256=`f356d87730b7fec176765c34adf5823aafafadbfbf53a1a8dd9ae5a0f4754a0e`。QA `overall_pass=true`，request/config/父模型/source/protected-pipeline hash、namespace、三仰角完整性、12 rows/ms、all-positive NLOS、mask、block/phase consistency、output hash 和 gold-leakage gates 均通过。v2.1 仍是参数生成 preview，不是 raw IQ、MATLAB、SAGE 或论文实测结果。
- 第一次未能完成 auditor 预检的 v2.1 preview namespace `preview_120ms_urban_all_bands_v2_1_20260827` 及 request SHA=`8a2872fcb771a0aec9662d62e423e1ded481fcac7c7eaf33c3954a0c9b8e3ead` 保留为历史诊断 artifact；原因是 auditor 初始实现误引用 core QA helper，修复后按 new-only 使用 `_r1` 重新生成，未覆盖旧 namespace。
- v2.1 聚焦测试为 `12 passed`，四个新文件通过 `py_compile`。全套 channel-modeling regression 本轮未完成（不作为 v2.1 放行门禁），不能把 v2.1 标为全环境/全回归 `Validated`。下一步由用户审阅 v2.1 120 ms 预览，再决定是否开展更长时长或多环境生成；不得据此宣称最终统计信道模型完成。

```text
DARKROOM_GENERATOR_V1 = IMPLEMENTED_PREVIEW_ONLY_NOT_TARGET_CONTRACT
DARKROOM_GENERATOR_V2 = IMPLEMENTED_PREVIEW_QA_PASS_FULL_REGRESSION_PENDING
DARKROOM_GENERATOR_V2_1 = IMPLEMENTED_PREVIEW_QA_PASS_FULL_REGRESSION_PENDING
DARKROOM_GENERATOR_V2_1_NLOS_CONTRACT = ALL_THREE_SLOTS_ALWAYS_ACTIVE_STRICTLY_POSITIVE
DARKROOM_GENERATOR_V2_1_ACTIVATION_MODEL_USED = NO
DARKROOM_GENERATOR_V2_1_CONDITIONAL_SCENARIO = YES
DARKROOM_120MS_V2_1_PREVIEW = GENERATED_1440_ROWS_INDEPENDENT_QA_PASS
DARKROOM_GENERATOR_V2_1_REQUEST_SHA256 = F35AF78CD2043D68C95CA55FF70AFF080E3319FD0F550D8EC50ADADDDAF563DD
DARKROOM_GENERATOR_V2_1_CANONICAL_ROWS = 1440 (1080 POSITIVE NLOS / 0 INACTIVE)
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = USER_REVIEW_OF_120MS_V2_1_PREVIEW_BEFORE_LONGER_OR_MULTI_ENVIRONMENT_RUN
```

## 61. Darkroom environment × quality paired generator v2.2 controlled pilot (Implemented + Validated, 2026-08-27)

- 按批准的 v2.2 计划完成了独立 Python-only environment×quality paired generator。新增配置、quality-profile、generator core、immutable request/matrix preparer、new-only runner、独立 auditor 和矩阵汇总工具均位于 `configs/channel_modeling/` 与 `scripts/analysis/channel_modeling/`；v2.1 source/config、冻结 path/gain/lock/recovery model、production pipeline 和既有 v2.1/v2.0 artifact 均未修改。
- 最终使用全新 matrix namespace `dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices/environment_quality_pair_20s_v2_2_r3_20260827/`，matrix manifest SHA-256=`389917e6810ae243434bec81df3409563a6491a81515b99f557dc3a2198f4a0a`。8 个 request 均 validation-only eligible，`new_only=true`、`resume_allowed=false`、raw/MATLAB/SAGE/batch/20.46 MHz 全部 false；r1/r2 旧 matrix 以及早期 sidecar schema failure run 均保留为 immutable diagnostic evidence。
- 8 个 run 均已生成并通过独立 gold-blind QA：4 个环境（Urban、Special Reflective、Mountain/Valley、Highway/Open）分别配对 `GOOD_TRACKED_BASELINE` 与 `POOR_CONDITIONAL`。每张 canonical table 为 20,000 ms×12 rows/ms=`240,000` 行；矩阵合计 8 tables、24 environment×elevation×quality logical cells、1,920,000 canonical rows。4/4 Good/Poor pair QA 均证明 base common gain、path delay/Doppler/phase invariant，最终差异仅来自冻结 quality envelope。
- 每个 Poor run 含 Low/Mid/High 各一个完整条件质量事件（矩阵共 12 个），每个 Good run 无质量事件；所有 8 个 run 的 NLOS 1/2/3 输出幅度严格为正。Urban LOW 和 Highway/Open LOW 的 path-support `PRIOR_ONLY` 标记继续保留，Highway/Open 的质量/路径层仍受 prior/partial-pooling 限制。
- 矩阵级结果位于独立 QA namespace `dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices/environment_quality_pair_20s_v2_2_r3_qa2_20260827/`：`matrix_qa_summary.csv` SHA-256=`88ebc27971c5c60b33cbdda723d73a9ef145c2a2e45cb7dca5c01d5d313d8fcd`，`matrix_qa_report.md` SHA-256=`eab068ac949abb5b1a5d177610bd5d1ed41dab0c811fc1de4ec2098f618cc7a5`，`MATRIX_QA=true`。第一版 r3 summary 中的 Poor event-count 展示错误已通过新 QA namespace 校正，原报告未覆盖。
- v2.2 关键 source/config hash 已随 request/receipt 冻结：config=`26003c7c0c0cabca45c6a9a175974f1ca336a301eff9c546a9c3bc99e38b5822`；quality=`9b1f3483e9f5a9eb9630afeb2111568aa015802dde6301b40546a8a0d9c3528b`；core=`fb0253c83b82c978c625c9ae22977beee4095155b48b171625f1607097d016cc`；request preparer=`f6a15b9dcf0c6819dc9792816670a7a3a73526112211383bbe00d7f82713b642`；matrix preparer=`6968c111b9e36e9adba96e2900cc9a4686803ae017106191631b35b71b166af0`；runner=`206d6924c8b2e56ba8a77194ee0ab8409b05af2fd50330af55625542b4e26fab`；auditor=`e8f1ad43697380562e68485a91b6d6067dcd03b0495f420e690a36b25f225b8c`；summarizer=`f82f10b4593ae0ca3469f82ec74b06ca49545108315de16e34914a779f34ed10`。
- 代码验证结果为 v2.2 focused tests `31 passed`、v2.1 regression `12 passed`、四个冻结 parent core test `53 passed`，以及全部 v2.2 source `py_compile` PASS。完整 channel-modeling suite 的既有 v1 测试仍有已知 `request_purpose` payload failure；一组包含昂贵 builder/auditor 的 parent 全量组合在末段长时间运行后被安全中断，因此本节不把 full-suite 记为全量 PASS，也没有发现由 v2.2 引入的新科学回归。
- 实际 Python 环境为 `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`（Python 3.12.9、NumPy 2.5.1、SciPy 1.18.0、OpenBLAS 0.3.33.112.0）。8 个 run 的单表 elapsed 约 25.581–36.966 s，合计约 247.579 s；这些是 Python 参数表生成时间，不是 SAGE 或 raw-IQ runtime。
- 该 pilot 只验证了 20 秒、四环境 Good/Poor 条件性生成和配对 provenance。`POOR_CONDITIONAL` 是 receiver-diagnostic conditional impairment，不是硬件标定的物理失锁概率；三条 NLOS 始终激活是条件性四路径合同，不是实测发生率；phase 是外加假设，absolute RF power unavailable。final-duration export、暗室实际回放和完整 statistical channel model 仍未完成。

```text
DARKROOM_GENERATOR_V2_2_IMPLEMENTATION = IMPLEMENTED
DARKROOM_GENERATOR_V2_2_PILOT = COMPLETED_20S
DARKROOM_GENERATOR_V2_2_RUN_QA = PASS (8/8)
DARKROOM_GENERATOR_V2_2_PAIR_QA = PASS (4/4)
DARKROOM_GENERATOR_V2_2_MATRIX_QA = PASS
DARKROOM_GENERATOR_V2_2_CANONICAL_TABLES = 8
DARKROOM_GENERATOR_V2_2_LOGICAL_CELLS = 24
DARKROOM_GENERATOR_V2_2_CANONICAL_ROWS = 1920000
DARKROOM_GENERATOR_V2_2_POOR_EVENTS = 12 (3 PER POOR RUN)
DARKROOM_GENERATOR_V2_2_ZERO_AMPLITUDE_NLOS_ROWS = 0
DARKROOM_GENERATOR_V2_2_GOLD_LABELS_USED = NO
DARKROOM_GENERATOR_V2_2_FINAL_DURATION_EXPORT = NOT STARTED
STATISTICAL_CHANNEL_MODEL = NOT STARTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = USER_DECISION_ON_LONGER_DARKROOM_EXPORT_OR_PAPER_ADMISSION
```

## 62. v2.2 batch generator wrapper and 20 ms contract smoke (Implemented; full eight-cell smoke blocked by frozen duration semantics, 2026-08-27)

- 新增独立批量调用脚本 `scripts/analysis/channel_modeling/run_darkroom_generator_v2_2_batch.py` 及聚焦测试 `scripts/analysis/channel_modeling/tests/test_run_darkroom_generator_v2_2_batch.py`。脚本只编排既有 v2.2 request/runner，不改变 `darkroom_generator_v2_2_core.py` 的科学计算；支持 `--prepare`、`--validate-only` 和显式 `--execute --confirm-darkroom-batch-v2-2`，按 Urban、Special Reflective、Mountain/Valley、Highway/Open × Good/Poor 固定顺序逐项执行，并在全部成功后将 8 张 canonical table 以 hash 可追溯副本导出到集合目录。
- 新脚本当前 SHA-256=`5b420575aa3236a17394b1edc481c02a046f5a52f5061e08bc0590d3451b8140`；既有 v2.2 config/core/request-preparer/matrix-preparer/runner hash 未改变，分别仍为 `26003c7c0c0cabca45c6a9a175974f1ca336a301eff9c546a9c3bc99e38b5822`、`fb0253c83b82c978c625c9ae22977beee4095155b48b171625f1607097d016cc`、`f6a15b9dcf0c6819dc9792816670a7a3a73526112211383bbe00d7f82713b642`、`6968c111b9e36e9adba96e2900cc9a4686803ae017106191631b35b71b166af0`、`206d6924c8b2e56ba8a77194ee0ab8409b05af2fd50330af55625542b4e26fab`。受保护 `run_nav_sage_pipeline.m` SHA-256 仍为 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。已有 20 ms smoke manifest 中记录的是冻结时的旧 wrapper hash，不能作为当前 wrapper provenance；该 smoke 只保留作历史诊断。
- 20 ms smoke 集合使用全新 namespace `dataset_generation_logs/channel_modeling/0828darkroomPar_smoke_20ms_20260827/`，matrix manifest SHA-256=`4cfaf245c5af033c811993bf22109b8dcf462c4291925f1fcf5cbb6fc9f7e45d`。manifest/8 request/new-only/输出隔离 validation-only 通过；实际 8-cell smoke 在第一个 `GOOD_TRACKED_BASELINE` Urban 单元完成 240 行后，第二个 `POOR_CONDITIONAL` 单元由既有 frozen quality profile 以 `QUALITY_EPISODE_DOES_NOT_FIT` 拒绝，因为 20 ms 不能容纳完整质量事件。批处理按安全策略停止，未启动剩余 6 个单元，未导出集合 tables；Good 成功输出和 Poor failed receipt 均保留为诊断证据，未删除、覆盖或 resume。
- 为防止短时长被误当作有效 8-cell 质量生成，wrapper 将 20 ms 明确定义为 validation-only；8-cell `--execute` 只允许 `300000 ms`。正式 5 分钟集合 `dataset_generation_logs/channel_modeling/0828darkroomPar/` 已由用户人工准备，matrix manifest SHA-256=`61ff9777087b2c82f297b649adea2ae5406b658f53cb4fa56342aca9373fcbe9`，8 个 request 均已冻结且输出 namespace、batch lock、tables 目录均不存在；5 分钟生成尚未执行。下一步由用户先运行该 manifest 的 validation-only，再自行决定是否执行 5 分钟 batch。

```text
DARKROOM_GENERATOR_V2_2_BATCH_WRAPPER = IMPLEMENTED
DARKROOM_20MS_BATCH_CONTRACT_VALIDATION = PASS
DARKROOM_20MS_FULL_EIGHT_CELL_SMOKE = BLOCKED_BY_QUALITY_EPISODE_DURATION
DARKROOM_GENERATOR_V2_2_FINAL_DURATION_EXPORT = NOT STARTED
DARKROOM_5MIN_MANIFEST = PREPARED_8_REQUESTS
DARKROOM_5MIN_BATCH = NOT_STARTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_SAGE_EXECUTED = NO
PROCESS_20_46_MHZ = NO
NEXT_DECISION_REQUIRED = USER_VALIDATE_5MIN_MANIFEST_THEN_AUTHORIZE_5MIN_BATCH_CALL
```

## 63. Darkroom v2.2 5-minute eight-cell generation and export (Completed generation/export; independent 5-minute QA not separately recorded, 2026-08-27)

- 本节覆盖 Section 62 中“5 分钟生成尚未执行”的当时状态；Section 62 作为历史执行准备与 20 ms smoke 记录保留，不删除、不改写。当前实际集合 `dataset_generation_logs/channel_modeling/0828darkroomPar/` 的 `batch_execution_receipt.json` 记录 `status=completed`、`completed_count=8`、`request_count=8`，八个环境×质量 request 均 exit code `0`。
- 8 个 request 仍对应四类环境 `Urban`、`Special Reflective`、`Mountain/Valley`、`Highway/Open` 与两种质量模式 `GOOD_TRACKED_BASELINE`、`POOR_CONDITIONAL`；每张 canonical table 为 `300000 ms × 12 rows/ms = 3,600,000` 行，八张表合计 `28,800,000` 行。集合执行时间为 `2026-08-27T07:00:26.687705Z` 至 `2026-08-27T07:59:12.479781Z`，wall-clock 约 `3526 s`。
- 集合 manifest `matrix_manifest.json` SHA-256=`61ff9777087b2c82f297b649adea2ae5406b658f53cb4fa56342aca9373fcbe9`；`request_matrix.csv` SHA-256=`303925e84fad0c02701332dc6110667b50e0866959be2894c24336d0f8ec7832`；batch receipt SHA-256=`c78a030006851fb2b1ff87fd5792368235b54a183d7750e2dd0e06dfc4e69d63`。
- 八张集合导出表位于 `dataset_generation_logs/channel_modeling/0828darkroomPar/tables/`，由 `table_export_manifest.json` 记录；export manifest SHA-256=`f2de55f4803f237449c9f6b7f4722343e5d3c00a6601a0cc62106c5178669feb`。导出是 hash-traceable 副本，authoritative per-request outputs 仍位于 `dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/*_5min_v2_2_0828darkroomPar_20260827/`。
- receipt 和 table-export manifest 均明确 `raw_iq_read=false`、`matlab=false`、`sage=false`、`gold_labels_used_for_generation=false`。这批结果证明 Python 参数生成与导出完成，不等同于暗室硬件回放验收，也不等同于完整统计信道模型完成。
- 当前未发现与 20 秒 `environment_quality_pair_20s_v2_2_r3_qa2_20260827` 等价的独立 5 分钟矩阵 QA 报告。因此工程状态应区分为 `DARKROOM_5MIN_BATCH=COMPLETED_GENERATION_EXPORT` 与 `DARKROOM_5MIN_INDEPENDENT_QA=NOT_RECORDED`；如需用于回放或论文材料，应另行进行只读 QA，不得重写或复用现有 namespace。
- 暗室支线参考文档为 `docs/DARKROOM_GENERATOR_V2_2_REFERENCE.md`，SHA-256=`a3ec004a47026504a6a53a78a33b4cd31f3c5ef6f029069e5a115082df7cd1e9`。该文档是资产导航与交接参考，不是新的工程唯一状态源。

```text
DARKROOM_GENERATOR_V2_2_5MIN_GENERATION = COMPLETED_8_OF_8
DARKROOM_GENERATOR_V2_2_5MIN_EXPORT = COMPLETED_8_TABLES
DARKROOM_GENERATOR_V2_2_5MIN_INDEPENDENT_QA = NOT_RECORDED
DARKROOM_GENERATOR_V2_2_5MIN_CANONICAL_ROWS = 28800000
DARKROOM_GENERATOR_V2_2_5MIN_RAW_IQ_READ = NO
DARKROOM_GENERATOR_V2_2_5MIN_MATLAB = NO
DARKROOM_GENERATOR_V2_2_5MIN_SAGE = NO
DARKROOM_GENERATOR_V2_2_5MIN_GOLD_LABELS_USED = NO
DARKROOM_GENERATOR_V2_2_STATISTICAL_CHANNEL_MODEL = NOT_STARTED
NEXT_DECISION_REQUIRED = INDEPENDENT_5MIN_READ_ONLY_QA_OR_DARKROOM_REPLAY_AUTHORIZATION
```

## 64. Rain full-SAGE nine-task and canonical-table effect-layer execution plan (Planned / Not started, 2026-08-27)

- 用户已确认 Rain Effect Layer 的最终接口固定为作用于现有 v2.2 canonical path table：`ms,SatelliteID,NLOSPathID,RelativeDelay,RelativeDoppler,RelativeAmplitude,RelativePhase_rad`。该层不直接修改 raw IQ，也不修改已有 v2.2 generator/core、5 分钟表或生产 SAGE。
- 正式执行计划位于 `docs/superpowers/plans/2026-08-27-darkroom-rain-effect-layer-final-execution.md`，SHA-256=`57a6646a8a5f4795bfb1ce50937dc904f86f47f55ace870b85f2ed292790965c`。计划将工作串行拆为：9-task Rain full SAGE/independent QA/frozen event-path population，再进行 Clear→MidRain 与 Clear→HeavyRain 的 empirical distribution transport、canonical-table adapter、120 ms smoke 和 24 logical-cell package QA。
- 机器可读 9-task checklist 位于 `dataset_generation_logs/darkroom_channel_emulation/rain_final_planning_20260827/rain_sage_9_task_checklist.csv`，SHA-256=`03dce06a9ffa4279982b89ad487f534f13821662016fc1f650ca8263ac8011a9`。清单包含 9 个唯一 scene/PRN/channel 任务，全部固定为 10.23 MHz；Clear G24 和 HeavyRain G02 标记为 `ARTIFACT_EXISTS_QA_REQUIRED`，其余 7 项标记为 `NOT_STARTED`。
- 执行合同保持 `new_only=true`、`resume_allowed=false`、`max_parallel_matlab=1`、正常用户 PowerShell 7、一次一任务、每任务 QA 后人工放行下一项。现有 G24/G02 必须先独立 QA；如未通过，不得覆盖或在原 namespace 重跑，只能停止并等待新版本 namespace 决策。
- 科学边界保持：三种天气没有共同 PRN，仅 Clear/MidRain 共有 G24；没有可用 geometry/elevation。雨效应层因此定位为 weather-conditioned empirical transform，禁止逐路径相减、仰角条件雨效应或普适因果雨衰声明。Stage4 relative amplitude 不能识别绝对主径雨衰，path0 公共增益/失锁仍由既有 quality/common-gain/lock 层负责。
- 本节只记录已批准的规划资产。本轮未生成 execution request、未读取 raw IQ 内容、未运行 MATLAB/SAGE、未改变任何既有实验 artifact，Rain 9-task production 和雨效应层实现均仍为 `Planned / Not started`。

```text
RAIN_EFFECT_LAYER_INTERFACE = CANONICAL_PATH_TABLE_CONFIRMED
RAIN_FULL_SAGE_FROZEN_TASK_COUNT = 9
RAIN_EXISTING_ARTIFACTS_PENDING_QA = 2
RAIN_FRESH_TASKS_NOT_STARTED = 7
RAIN_FULL_SAGE_EXECUTION = NOT_STARTED
RAIN_EVENT_PATH_DATABASE = NOT_STARTED
RAIN_EFFECT_LAYER_IMPLEMENTATION = NOT_STARTED
RAIN_24_LOGICAL_CELL_PACKAGE = NOT_STARTED
RAW_IQ_CONTENT_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
EXECUTION_REQUEST_CREATED = NO
NEXT_DECISION_REQUIRED = USER_SELECT_PLAN_EXECUTION_MODE_AND_AUTHORIZE_TASK_1
```

## 65. Existing Rain G24/G02 artifact QA (Implemented; artifact audit PASS, execution acceptance inconclusive, 2026-08-27)

- Task 2 of the approved Rain execution plan was performed as an independent, read-only audit of the two pre-existing output directories. Auditor: `scripts/sage_pipeline/rain/audit_rain_sage_task.py` (SHA-256=`bd0dcff63955b0d6701471daf0aa48912a882d7024fcd916051dad28560ea69a`). Regression tests: `scripts/sage_pipeline/rain/test_audit_rain_sage_task.py` (SHA-256=`4579a2073795887fd2b695343e5ffed31de41c89547ee82fb70301a43cb81918`), 6/6 passed. The audit generated only new reports under `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260827/`.
- Clear G24/ch10 artifact `scenes/F1023_clear/sage_results/rain_sage_v1/G24` passed identity, completeness, stage-chain, and numerical checks. It contains 2,206 Stage0 symbols, 2,204 Stage0/Stage1 windows, 480 Stage2 model rows, 120 selected windows, 63 Stage3 persistence rows, 3 reliable centers, 3 Stage4 joint rows, and 0 confirmed events / 0 confirmed multipath paths under the strict Stage4 criterion. One Stage2 invalid model row is reported as a diagnostic count and does not make the written artifact incomplete.
- HeavyRain G02/ch1 artifact `scenes/F1023_heavyrain/sage_results/rain_sage_v1/G02` passed identity, completeness, stage-chain, and numerical checks. It contains 2,865 Stage0 symbols, 2,863 Stage0/Stage1 windows, 480 Stage2 model rows, 120 selected windows, 183 Stage3 persistence rows, 6 reliable centers, 6 Stage4 joint rows, and 1 confirmed event / 1 confirmed multipath path (center window `2096`) under the strict Stage4 criterion. 141 Stage2 invalid model rows are reported as a diagnostic count; written Stage4 output remains structurally complete.
- Neither existing output directory has a successful execution receipt bound to it. Historical overnight records associated with these tasks are failed/non-zero records and were not promoted to success evidence. Accordingly, both artifact audits are structurally PASS, but both overall task dispositions remain `INCONCLUSIVE_NO_EXECUTION_RECEIPT`; the checklist's prior `ARTIFACT_EXISTS_QA_REQUIRED` state is not changed into formal acceptance by this audit.
- QA summary: `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260827/existing_artifact_qa_summary.csv` and `existing_artifact_qa_summary.md`. The detailed per-task QA JSON/report/hash artifacts are in the two task subdirectories. Existing Rain SAGE artifacts and historical failed/partial records were not modified, deleted, moved, resumed, or reinterpreted as new results. The protected production pipeline hash remains `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.

```text
RAIN_EXISTING_ARTIFACT_AUDIT_TASKS=2
RAIN_CLEAR_G24_ARTIFACT_QA=PASS
RAIN_HEAVYRAIN_G02_ARTIFACT_QA=PASS
RAIN_EXISTING_EXECUTION_RECEIPT_ACCEPTANCE=INCONCLUSIVE_2_OF_2_NOT_FOUND
RAIN_CLEAR_G24_CONFIRMED_EVENTS=0
RAIN_CLEAR_G24_CONFIRMED_PATHS=0
RAIN_HEAVYRAIN_G02_CONFIRMED_EVENTS=1
RAIN_HEAVYRAIN_G02_CONFIRMED_PATHS=1
RAIN_EXISTING_ARTIFACTS_MODIFIED=NO
RAW_IQ_CONTENT_READ=NO
MATLAB_EXECUTED=NO
SAGE_EXECUTED=NO
NEXT_DECISION_REQUIRED=RECOVER_OR_BIND_SUCCESS_EXECUTION_RECEIPT_BEFORE_FORMAL_RAIN_ACCEPTANCE
```

## 66. Fresh Rain rerun preparation after receipt ambiguity (Implemented; G24 request ready, execution not started, 2026-08-27)

- Because the existing Clear G24 and HeavyRain G02 directories have no bindable successful execution receipt, the user authorized treating those results as abandoned for the new analysis while preserving them as historical evidence. No old artifact was deleted, moved, overwritten, resumed, or modified.
- A separate fresh-task entry `scripts/sage_pipeline/rain/run_rain_sage_fresh_task.m` was added. It reuses the existing Rain `build_rain_stage0.m` and `run_rain_sage_stage1_stage4.m` implementations, requires an explicit new rerun namespace, rejects `Resume=true`, and does not alter the existing Rain or protected production mathematics. Its SHA-256 is `2b2cfd0e0a704dec5dee5c6c47dc89c77c8f3fbb23a76d10371cd7a002407e41`.
- A separate task-aware wrapper `scripts/sage_pipeline/rain/Invoke-RainSageFreshTask.ps1` was added. It is validation-only by default, requires `-Execute -ConfirmRainSageRerun` for a real call, checks the manifest/source/input hashes, checks the global mutex, enforces normal-user `TJ-CHANNEL\\Jing_` execution, and records a new receipt without cleanup/resume behavior. SHA-256=`ea6e4450f25d354c463f451509c40b6c442317b344621fbd7785b6a17caa0099`.
- Request preparation is provided by `scripts/sage_pipeline/rain/prepare_rain_sage_fresh_request.py`, SHA-256=`f152e25b1cd46bdfa30c49ec1662b27de6ea531ee582bf8747cb76db9fb69ecd`. Rain regression/static verification passed: all 62 Rain Python tests, `py_compile`, and the fresh wrapper PowerShell AST parse.
- Current immutable first-task request is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_rerun_requests_20260827/rain_sage_fresh_rerun_v1__F1023_clear__G24__ch10__20260827_r2/execution_manifest.json`, SHA-256=`e0e1c8bf8c4642c2c72efaf0f899e7186e5212e1021d5bec29659827ce52fa63`. It freezes `F1023_clear/G24/ch10/10230000`, raw byte size `2925003264`, raw SHA-256=`0be6adba273a81b21d6e84e93a4fa1450f7a4a76c093ef1ea17163015f616210`, `new_only=true`, `resume_allowed=false`, and `gold_labels_used_for_selection=false`.
- Dry-run passed with `GLOBAL_LOCK=AVAILABLE`, `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, and `SAGE_EXECUTED=false`. The only approved new output namespace for this task is `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r2/G24`; it was absent at preparation time and remains absent. The prior `r1` request namespace is retained as a superseded, non-executed diagnostic artifact because a later wrapper hash/lock check required a new immutable request.
- The rerun scope remains the nine-task frozen Rain population across Clear, MidRain, and HeavyRain. Execution policy remains serial: execute Clear G24 first, perform independent QA, then require a separate human release before any other Rain task. No G25/G11/mainline production task is released by this preparation.

```text
RAIN_FRESH_RERUN_SCOPE=THREE_RECORDINGS_NINE_TASKS
RAIN_FRESH_G24_REQUEST=PREPARED_R2
RAIN_FRESH_G24_EXECUTION=NOT_STARTED
RAIN_FRESH_G24_DRY_RUN=PASS
RAIN_FRESH_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_OLD_ARTIFACTS_PRESERVED=YES
RAIN_FRESH_TESTS=PASS_62
RAW_IQ_SHA256_PREPARATION=BYTE_HASH_ONLY
MATLAB_EXECUTED=NO
SAGE_EXECUTED=NO
FILES_DELETED_COUNT=0
FILES_MOVED_TO_TRASH=0
TRASH_DIRECTORY_PRESERVED=YES
NO_DELETE_POLICY_VIOLATION=YES
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_G24_FRESH_RERUN_THEN_INDEPENDENT_QA
```

## 67. Fresh Rain G24 r2 execution audit (Receipt completed; output QA failed, 2026-08-27)

- The normal-user execution of the immutable Clear `F1023_clear/G24/ch10` r2 request produced receipt `dataset_generation_logs/darkroom_channel_emulation/rain_sage_rerun_requests_20260827/rain_sage_fresh_rerun_v1__F1023_clear__G24__ch10__20260827_r2/receipts/rain_sage_fresh_rerun_v1__F1023_clear__G24__ch10__20260827_r2_20260827T122356Z_receipt.json`. The receipt records `status=COMPLETED`, `matlab_invoked=true`, and `matlab_exit_code=0`.
- The receipt nevertheless records `output_files=[]`; both stdout and stderr logs are empty, and the frozen r2 output namespace `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r2/G24` does not exist. Therefore no r2 Stage0–Stage4 artifact or scientific result can be accepted from this execution record. The older `scenes/F1023_clear/sage_results/rain_sage_v1/G24` artifact remains preserved and was not substituted for r2.
- Independent read-only audit output is `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260827/rain__clear__G24__ch10__fresh_r2/`; it reports `FAIL_MISSING_OUTPUT`, with `scientific_status=NOT_ASSESSABLE`, no confirmed event/path count, and no raw IQ opened by the auditor. This is an output-binding/completeness anomaly; the available receipt and empty logs do not establish a unique internal MATLAB cause.

```text
RAIN_FRESH_G24_R2_EXECUTOR_RECEIPT=COMPLETED_EXIT_CODE_0
RAIN_FRESH_G24_R2_OUTPUT_FILES=0
RAIN_FRESH_G24_R2_OUTPUT_NAMESPACE_EXISTS=NO
RAIN_FRESH_G24_R2_INDEPENDENT_QA=FAIL_MISSING_OUTPUT
RAIN_FRESH_G24_R2_SCIENTIFIC_RESULT=NOT_ASSESSABLE
RAIN_FRESH_G24_R2_AUDITOR_RAW_IQ_READ=NO
RAIN_FRESH_G24_R2_OLD_ARTIFACT_USED_AS_SUBSTITUTE=NO
RAIN_FRESH_G24_R2_ARTIFACTS_MODIFIED=NO
RAW_IQ_EXECUTED_BY_AUDITOR=NO
MATLAB_EXECUTED_BY_AUDITOR=NO
SAGE_EXECUTED_BY_AUDITOR=NO
NEXT_DECISION_REQUIRED=DIAGNOSE_MISSING_R2_OUTPUT_BEFORE_ANY_OTHER_RAIN_TASK
```

## 68. G24 r2 missing-output root-cause diagnosis (Diagnosis complete; repair not applied, 2026-08-27)

- The confirmed receipt-semantics defect is in `scripts/sage_pipeline/rain/Invoke-RainSageFreshTask.ps1`: completion is assigned solely from `Start-Process` exit code (`0` becomes `COMPLETED`), while `Get-OutputFileRecords` may return an empty list and is not a completion gate. This permits `status=COMPLETED` with `output_files=[]` and no Stage artifact.
- The high-confidence command-boundary cause is the fresh wrapper's `Start-Process -ArgumentList @("-batch", $expression)` call. The generated MATLAB expression contains spaces after semicolons, but the expression is not enclosed as one command-line argument. The working Rain overnight wrapper explicitly quotes the full expression, and the main Windows wrapper uses `.ArgumentList.Add()` for argument-safe process construction. The observed combination—zero-byte stdout/stderr, no expected output directory, and exit code `0`—is consistent with MATLAB receiving only an incomplete batch statement or otherwise not reaching `run_rain_sage_fresh_task`.
- This last MATLAB-side detail is not directly proven because r2 did not record the child process argument vector or a function-entry marker. `build_rain_stage0.m` would create the supplied output directory and write Stage0 files before Stage1, so the absent r2 directory proves that no usable output reached the frozen namespace; it does not prove whether raw IQ was opened by the user-run MATLAB process.
- Recommended repair is executor-only and versioned: use `ProcessStartInfo.ArgumentList` or a correctly quoted single `-batch` statement, add a required-output postcondition that writes a failure/incomplete receipt when outputs are absent, and record child-process/progress provenance. Do not reuse or resume r2; create a new request/output namespace only after the wrapper repair is independently validated.

```text
RAIN_FRESH_G24_R2_ROOT_CAUSE_CLASS=HIGH_CONFIDENCE_EXECUTOR_BATCH_ARGUMENT_BOUNDARY_ERROR
RAIN_FRESH_G24_R2_FALSE_COMPLETION_BUG=CONFIRMED
RAIN_FRESH_G24_R2_MATLAB_FUNCTION_ENTRY=NOT_PROVEN
RAIN_FRESH_G24_R2_RAW_IQ_OPENED_BY_DIAGNOSTIC=NO
RAIN_FRESH_G24_R2_REPAIR=NOT_APPLIED
RAIN_FRESH_G24_R2_REUSE_OR_RESUME=FORBIDDEN
NEXT_DECISION_REQUIRED=VERSIONED_EXECUTOR_REPAIR_AND_NEW_REQUEST_BEFORE_ANY_RAIN_TASK
```

## 69. G24 fresh executor contract repair (Implemented; static validation passed, runtime pending, 2026-08-27)

- The executor-only repair for the preserved G24 r2 missing-output incident is implemented in `scripts/sage_pipeline/rain/Invoke-RainSageFreshTask.ps1`. MATLAB is now launched through `System.Diagnostics.ProcessStartInfo`; under PowerShell 7 the `-batch` switch and the complete expression are added as separate argument-list items, so the expression remains one child-process argument. A quoted `Arguments` fallback remains for Windows PowerShell/.NET Framework compatibility. The repaired wrapper SHA-256 is `08e372367e9130be2059200dde380b9206989f163cb9e0c133f854fff600eda2`.
- Completion is no longer inferred from exit code alone. The wrapper records `process_id`, argument mode, stdout/stderr paths, output namespace existence, required output list, missing output list, and output file hashes. Exit code `0` with any missing required Rain Stage0–Stage4 artifact now produces `FAILED_OUTPUT_MISSING` and a nonzero process result; partial output is preserved and is never resumed or deleted.
- The fresh entry and request preparer are versioned to the new `rain_sage_rerun_v1_20260827_r3` namespace. The entry SHA-256 is `dab8a8be2e2aae40e20e6f216baf09f7d882a2485e7a49470728f2f92f1d3e58`; the preparer SHA-256 is `383666864bc702f830bb07597fa2ba2ff41130469039c2e246d6c289e9e33427`. A new r3 request has not been generated in this step, and the r2 request remains immutable historical evidence rather than an executable request.
- Test-first contract coverage is green: the new executor contract tests pass `11/11`; the complete Rain Python suite passes `67/67`; Rain interface tests pass `6/6`; all Rain Python files compile; and the repaired wrapper passes PowerShell AST parsing. The existing `git diff --check` command still reports a pre-existing trailing-whitespace line in unrelated `docs/GNSS_SAGE_MAINLINE_COMMANDER_HANDOFF_CURRENT.md`; it reports no whitespace error from the new patch itself.
- Protected production entry `scripts/sage_pipeline/run_nav_sage_pipeline.m` remains unchanged at SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`. The r2 manifest SHA remains `e0e1c8bf8c4642c2c72efaf0f899e7186e5212e1021d5bec29659827ce52fa63`, its receipt remains preserved, and the r2 output namespace is still absent. No existing Rain artifact was deleted, moved, overwritten, resumed, or modified.

```text
RAIN_G24_R2_DIAGNOSIS=HIGH_CONFIDENCE_EXECUTOR_BATCH_ARGUMENT_BOUNDARY_ERROR
RAIN_G24_R2_FALSE_COMPLETION_FIX=IMPLEMENTED
RAIN_FRESH_R3_NAMESPACE=rain_sage_rerun_v1_20260827_r3
RAIN_FRESH_R3_REQUEST=NOT_GENERATED
RAIN_FRESH_R2_REUSE_OR_RESUME=FORBIDDEN
RAIN_FRESH_EXECUTOR_TESTS=PASS_11
RAIN_PYTHON_TESTS=PASS_67
RAIN_INTERFACE_TESTS=PASS_6
RAIN_PY_COMPILE=PASS
RAIN_WRAPPER_AST=PASS
PROTECTED_PRODUCTION_PIPELINE_MODIFIED=NO
RAW_IQ_READ_BY_CODEX=NO
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
SAGE_RERUN_REQUIRED=YES
NEXT_DECISION_REQUIRED=GENERATE_NEW_R3_REQUEST_THEN_HUMAN_EXECUTE_G24_FRESH_RERUN
```

## 70. Rain G24 r3 immutable request and dry-run (Prepared; execution not started, 2026-08-27)

- A new r3 request was generated after the executor repair; the r2 request and missing-output receipt remain historical and are not reused. The immutable manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_rerun_requests_20260827/rain_sage_fresh_rerun_v1__F1023_clear__G24__ch10__20260827_r3/execution_manifest.json`, with SHA-256 `293f0f4a11b22a36918ecee63874a03431b1082ba81b2eb5a8490748816b38f1`.
- The frozen task is `F1023_clear/G24/ch10/10230000`; raw metadata records `2925003264` bytes and byte SHA-256 `0be6adba273a81b21d6e84e93a4fa1450f7a4a76c093ef1ea17163015f616210`. The request explicitly freezes `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, and `gold_labels_used_for_selection=false`.
- The only approved new output namespace is `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r3/G24`; it was absent during preparation and validation. The global Rain mutex was available. The repaired source provenance is frozen in the manifest, including entry SHA `dab8a8be2e2aae40e20e6f216baf09f7d882a2485e7a49470728f2f92f1d3e58`, wrapper SHA `08e372367e9130be2059200dde380b9206989f163cb9e0c133f854fff600eda2`, preparer SHA `383666864bc702f830bb07597fa2ba2ff41130469039c2e246d6c289e9e33427`, and protected production SHA `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.
- The PowerShell validation-only run passed with `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, and `SAGE_EXECUTED=false`; it printed the exact r3 MATLAB expression containing `Resume,false`. No MATLAB/SAGE task was started by this preparation, and no old artifact was changed.

```text
RAIN_FRESH_G24_R3_REQUEST=PREPARED
RAIN_FRESH_G24_R3_MANIFEST_SHA256=293f0f4a11b22a36918ecee63874a03431b1082ba81b2eb5a8490748816b38f1
RAIN_FRESH_G24_R3_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_FRESH_G24_R3_GLOBAL_LOCK=AVAILABLE
RAIN_FRESH_G24_R3_DRY_RUN=PASS
RAIN_FRESH_G24_R3_EXECUTION=NOT_STARTED
RAIN_FRESH_G24_R2_REUSE_OR_RESUME=FORBIDDEN
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_G24_R3_THEN_INDEPENDENT_QA
```

## 71. Rain G24 r3 path-binding failure and r4 request (Implemented; execution pending, 2026-08-27)

- The human execution of r3 reached MATLAB through `ProcessStartInfo.ArgumentList`, proving that the earlier command-line argument-boundary repair was effective. The r3 receipt records `matlab_argument_mode=ProcessStartInfo.ArgumentList`, process id `8448`, and MATLAB exit code `1`.
- r3 failed before Stage0 at line 39 of `scripts/sage_pipeline/rain/run_rain_sage_fresh_task.m`. MATLAB reported that the supplied `outputDir` used `E:/...` while the `fullfile`-constructed frozen namespace used `E:\...`; the strict equality assertion therefore rejected an otherwise equivalent Windows path. The r3 namespace remained absent and all required output files were missing. This is a path-representation contract failure, not a Stage0–Stage4 algorithm or numerical failure.
- The minimal fix preserves native Windows separators in `Invoke-RainSageFreshTask.ps1` instead of converting canonical paths to `/`. No Rain scientific parameter, threshold, grid, Stage0–Stage4 implementation, optimizer, or confirmation criterion changed. Because r3 is bound to the previous wrapper hash and new-only execution forbids reuse, r3 is permanently historical and must not be rerun.
- A new r4 namespace/request was generated after the path fix. The immutable manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_rerun_requests_20260827/rain_sage_fresh_rerun_v1__F1023_clear__G24__ch10__20260827_r4/execution_manifest.json`, SHA-256 `13f945ced42dfb940cb952b8e2cdbb8097386dfe6a17538a869d7a123e001197`. It keeps `F1023_clear/G24/ch10/10230000`, the same raw byte hash/provenance, `new_only=true`, `resume_allowed=false`, and the same protected production pipeline.
- The r4 validation-only dry-run passed with `GLOBAL_LOCK=AVAILABLE`, `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, `SAGE_EXECUTED=false`. Its emitted MATLAB expression uses native Windows separators and explicitly contains `Resume,false`. The r4 output namespace is absent. The r3 receipt and r3 request remain preserved; no existing artifact was deleted, moved, overwritten, or resumed.
- Final static verification after the r4 preparation: Rain Python tests `68/68` passed, all Rain Python files compiled, Rain interface tests `6/6` passed, and the repaired wrapper passed PowerShell AST parsing. No MATLAB/SAGE execution was performed by Codex in this repair/preparation step.

```text
RAIN_G24_R3_EXECUTION=FAILED_AT_ENTRY_PATH_ASSERTION
RAIN_G24_R3_OUTPUT_NAMESPACE_EXISTS=NO
RAIN_G24_R3_SCIENTIFIC_STAGE_OUTPUT=NONE
RAIN_G24_R4_REQUEST=PREPARED
RAIN_G24_R4_MANIFEST_SHA256=13f945ced42dfb940cb952b8e2cdbb8097386dfe6a17538a869d7a123e001197
RAIN_G24_R4_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_G24_R4_GLOBAL_LOCK=AVAILABLE
RAIN_G24_R4_DRY_RUN=PASS
RAIN_G24_R4_EXECUTION=NOT_STARTED
RAIN_G24_R3_REUSE_OR_RESUME=FORBIDDEN
RAIN_PYTHON_TESTS=PASS_68
RAIN_PY_COMPILE=PASS
RAIN_INTERFACE_TESTS=PASS_6
RAIN_WRAPPER_AST=PASS
PROTECTED_PRODUCTION_PIPELINE_MODIFIED=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_G24_R4_THEN_INDEPENDENT_QA
```

## 72. Rain Clear G24 r4 execution and independent QA (Completed; QA PASS, valid zero-event, 2026-08-28)

- The normal-user execution of the immutable r4 request completed successfully. Receipt: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_rerun_requests_20260827/rain_sage_fresh_rerun_v1__F1023_clear__G24__ch10__20260827_r4/receipts/rain_sage_fresh_rerun_v1__F1023_clear__G24__ch10__20260827_r4_20260827T144043Z_receipt.json`. It records `status=COMPLETED`, `matlab_invoked=true`, `matlab_argument_mode=ProcessStartInfo.ArgumentList`, and `matlab_exit_code=0`; the frozen request SHA is `13f945ced42dfb940cb952b8e2cdbb8097386dfe6a17538a869d7a123e001197`.
- The output namespace is `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r4/G24`. It contains all 19 required Rain outputs (10 CSV, 8 MAT, and `rain_stage0_provenance.json`), with no missing output and no stderr content. The output was created in the r4 new-only namespace; r2/r3 namespaces and receipts remain preserved and were not reused, overwritten, moved, or deleted.
- Independent read-only QA was completed with the version-aware, Windows-long-path-safe auditor `scripts/sage_pipeline/rain/audit_rain_sage_task.py` (post-fix SHA-256=`a2a6d51a6ea9389e66474dc923ab2a3e61025a91df8fa669848422493d8f48c1`). The final QA artifacts are `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260828/rain__clear__G24__ch10__fresh_r4_final/qa_report.md`, `qa_result.json`, and `artifact_hashes.csv`; `overall_status=QA_PASS`, with identity, completeness, stage consistency, and numerical validity all `PASS`.
- Stage statistics are: 2,206 Stage0 symbols; 2,204 complete 40-ms windows; 2,204 Stage1 scanned windows with 0 invalid scans; 480 Stage2 model rows (120 each for L=1,2,3,4); 120 selected windows; 63 Stage3 persistence rows; 3 Stage3 reliable centers; 3 Stage4 joint rows; and 3/3 `joint_valid`. One Stage2 invalid-model row remains recorded as a diagnostic count; it does not invalidate the complete Stage4 artifact under the independent QA rules.
- Under the strict project confirmation criterion (`joint_valid=1` AND `joint_multipath_count>0` AND a matching Stage4 path with `is_multipath=1`), this task produced 0 confirmed multipath events and 0 confirmed multipath paths. This is a valid zero-event output under the current criterion and is not interpreted as LOS or physical absence of multipath.
- The QA-tool compatibility repair was limited to audit behavior: accepting the versioned r4 Rain namespace and using the Windows extended-path prefix for read-only access to the long receipt path. It did not change Rain Stage0–Stage4 mathematics, thresholds, grids, optimizer, confirmation criterion, or any audited artifact. Rain tests now pass `70/70`; relevant Python files compile; the protected production entry remains unchanged at SHA-256=`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.

```text
RAIN_G24_R4_EXECUTION=COMPLETED
RAIN_G24_R4_RECEIPT_STATUS=VALID
RAIN_G24_R4_MATLAB_EXIT_CODE=0
RAIN_G24_R4_OUTPUT_FILES=19_OF_19
RAIN_G24_R4_INDEPENDENT_QA=PASS
RAIN_G24_R4_SCIENTIFIC_STATUS=PASS_NO_CONFIRMED_MULTIPATH
RAIN_G24_R4_CONFIRMED_EVENTS=0
RAIN_G24_R4_CONFIRMED_PATHS=0
RAIN_G24_R4_ARTIFACT_MODIFIED_BY_AUDITOR=NO
RAIN_G24_R4_RAW_IQ_READ_BY_AUDITOR=NO
RAIN_G24_R4_MATLAB_EXECUTED_BY_AUDITOR=NO
RAIN_G24_R4_SAGE_EXECUTED_BY_AUDITOR=NO
RAIN_R2_R3_ARTIFACTS_PRESERVED=YES
RAIN_AUDITOR_TESTS=PASS_70
RAIN_AUDITOR_PY_COMPILE=PASS
PROTECTED_PRODUCTION_PIPELINE_MODIFIED=NO
NEXT_DECISION_REQUIRED=INDEPENDENTLY_AUDIT_HEAVYRAIN_G02_BEFORE_ANY_OTHER_RAIN_TASK
```

## 73. HeavyRain G02 r4 fresh request and dry-run (Prepared; execution not started, 2026-08-28)

- Following the completed Clear G24 r4 QA, a separate immutable request was prepared for the next explicitly selected Rain task `F1023_heavyrain/G02/ch1/10230000`. The request manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_rerun_requests_20260827/rain_sage_fresh_rerun_v1__F1023_heavyrain__G02__ch1__20260827_r4/execution_manifest.json`, with SHA-256 `faf9c373548e68dbb83c18c3df0ee1877405244ce38e381912cf0bbaacd7b224`.
- The request freezes the checklist-approved single channel mapping `G02 -> ch1`, 10.23 MHz, the existing HeavyRain raw provenance (2,916,090,368 bytes), GNSS-SDR tracking/telemetry/navigation/config/observables inputs, current Rain r4 source hashes, `new_only=true`, `resume_allowed=false`, and `gold_labels_used_for_selection=false`. The historical `scenes/F1023_heavyrain/sage_results/rain_sage_v1/G02` artifact remains preserved and is not used as the new output.
- The new-only output namespace is `scenes/F1023_heavyrain/sage_results/rain_sage_rerun_v1_20260827_r4/G02`; it was absent during preparation and validation. The global Rain mutex was available. The validation-only wrapper check passed with `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, and `SAGE_EXECUTED=false`, and emitted the exact `Resume,false` MATLAB expression.
- No MATLAB, SAGE, or batch execution was started by Codex for G02. Human execution remains a separate gate; after a successful receipt, the output must receive independent read-only Stage0–Stage4 QA before any other Rain task is considered.

```text
RAIN_G02_R4_REQUEST=PREPARED
RAIN_G02_R4_MANIFEST_SHA256=faf9c373548e68dbb83c18c3df0ee1877405244ce38e381912cf0bbaacd7b224
RAIN_G02_R4_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_G02_R4_GLOBAL_LOCK=AVAILABLE
RAIN_G02_R4_DRY_RUN=PASS
RAIN_G02_R4_EXECUTION=NOT_STARTED
RAIN_G02_R4_OLD_ARTIFACT_PRESERVED=YES
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_G02_R4_THEN_INDEPENDENT_QA
```

## 74. Rain HeavyRain G02 r4 execution and independent QA (Completed; QA PASS, 2026-08-29)

- The normal-user execution of the immutable HeavyRain request completed successfully. Receipt: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_rerun_requests_20260827/rain_sage_fresh_rerun_v1__F1023_heavyrain__G02__ch1__20260827_r4/receipts/rain_sage_fresh_rerun_v1__F1023_heavyrain__G02__ch1__20260827_r4_20260828T151735Z_receipt.json`. It records `status=COMPLETED`, `matlab_invoked=true`, `matlab_argument_mode=ProcessStartInfo.ArgumentList`, and `matlab_exit_code=0`; the frozen request SHA is `faf9c373548e68dbb83c18c3df0ee1877405244ce38e381912cf0bbaacd7b224`.
- The output namespace is `scenes/F1023_heavyrain/sage_results/rain_sage_rerun_v1_20260827_r4/G02`. It contains all 19 required Rain outputs, with no missing output. The historical `rain_sage_v1/G02` artifact remains preserved and was not reused, overwritten, moved, or deleted.
- Independent read-only QA was completed with `scripts/sage_pipeline/rain/audit_rain_sage_task.py`. Final QA artifacts are in `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260829/rain__heavyrain__G02__ch1__fresh_r4_final/`; `overall_status=QA_PASS`, with identity, artifact completeness, stage consistency, and numerical validity all `PASS`.
- Stage statistics are: 2,865 Stage0 symbols; 2,863 complete 40-ms windows; 2,863 Stage1 scanned windows with 0 invalid scans; 480 Stage2 model rows (120 each for L=1,2,3,4); 120 selected windows; 183 Stage3 persistence rows; 6 Stage3 reliable centers; 6 Stage4 joint rows; and 6/6 `joint_valid`. One Stage4 center (`2096`) has `joint_multipath_count=1`; the other five valid joint rows are non-multipath rows.
- Under the strict project confirmation criterion (`joint_valid=1` AND `joint_multipath_count>0` AND a matching Stage4 path with `is_multipath=1`), this task produced 1 confirmed multipath event and 1 confirmed multipath path. The confirmed row is center window `2096`, with Stage4 `excess_delay_samples=1.1`, `doppler_offset_hz=24.6643020952847`, and `mean_relative_power_db=-16.0941765143958`; these values are recorded as artifact facts, not a broader weather conclusion.
- The independent QA did not open raw IQ, invoke MATLAB, invoke SAGE, or modify the audited output. The next Rain task remains gated on the user's explicit decision; no G31/G01 execution was started automatically.

```text
RAIN_G02_R4_EXECUTION=COMPLETED
RAIN_G02_R4_RECEIPT_STATUS=VALID
RAIN_G02_R4_MATLAB_EXIT_CODE=0
RAIN_G02_R4_OUTPUT_FILES=19_OF_19
RAIN_G02_R4_INDEPENDENT_QA=PASS
RAIN_G02_R4_SCIENTIFIC_STATUS=PASS_WITH_CONFIRMED_MULTIPATH
RAIN_G02_R4_CONFIRMED_EVENTS=1
RAIN_G02_R4_CONFIRMED_PATHS=1
RAIN_G02_R4_CONFIRMED_CENTER=2096
RAIN_G02_R4_ARTIFACT_MODIFIED_BY_AUDITOR=NO
RAIN_G02_R4_RAW_IQ_READ_BY_AUDITOR=NO
RAIN_G02_R4_MATLAB_EXECUTED_BY_AUDITOR=NO
RAIN_G02_R4_SAGE_EXECUTED_BY_AUDITOR=NO
RAIN_G02_R4_OLD_ARTIFACT_PRESERVED=YES
NEXT_DECISION_REQUIRED=USER_AUTHORIZE_NEXT_RAIN_TASK
```

## 75. Rain MidRain G24/ch8 single-task request and dry-run (Prepared; execution not started, 2026-08-29)

- The next explicitly selected Rain task is `F1023_midrain/G24/ch8/10230000`. The checklist records it as `NOT_STARTED`, `PASS_STATIC_INPUT_GATE`, with no existing Rain output namespace. A dedicated single-task request preparer `scripts/sage_pipeline/rain/prepare_rain_sage_single_task_request.py` was added so a not-started task is not incorrectly routed through the historical-artifact replacement preparer; it reuses the validated r4 Rain entry/wrapper and does not change Stage0–Stage4 mathematics.
- The immutable request manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_midrain__G24__ch8__20260829_r4/execution_manifest.json`, SHA-256 `048bd7286c8f46a780f9d3fc8b569ea94fe1a5f5563c2ce3e71420811337b442`. It freezes the unique `G24 -> ch8` mapping, 10.23 MHz, input provenance and byte hashes, `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, and `gold_labels_used_for_selection=false`.
- The new-only output namespace is `scenes/F1023_midrain/sage_results/rain_sage_rerun_v1_20260827_r4/G24`; it was absent before and after preparation. The global Rain mutex was available. Wrapper validation-only passed with `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, `SAGE_EXECUTED=false`, and the emitted MATLAB expression explicitly uses `Resume,false` and `TrackingChannel,8`.
- No MATLAB/SAGE/batch execution was started by Codex. Human execution remains required; after completion, the resulting receipt and output must receive independent read-only Stage0–Stage4 QA before another Rain task is considered.

```text
RAIN_MIDRAIN_G24_CH8_REQUEST=PREPARED
RAIN_MIDRAIN_G24_CH8_MANIFEST_SHA256=048bd7286c8f46a780f9d3fc8b569ea94fe1a5f5563c2ce3e71420811337b442
RAIN_MIDRAIN_G24_CH8_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_MIDRAIN_G24_CH8_GLOBAL_LOCK=AVAILABLE
RAIN_MIDRAIN_G24_CH8_DRY_RUN=PASS
RAIN_MIDRAIN_G24_CH8_EXECUTION=NOT_STARTED
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_MIDRAIN_G24_CH8_THEN_INDEPENDENT_QA
```

## 76. Rain MidRain G24/ch8 execution and independent QA (Completed; QA PASS, valid zero-event, 2026-08-29)

- The normal-user execution of the immutable MidRain request completed successfully. Receipt: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_midrain__G24__ch8__20260829_r4/receipts/rain_sage_single_task_v1__F1023_midrain__G24__ch8__20260829_r4_20260829T074335Z_receipt.json`. It records `status=COMPLETED`, `matlab_invoked=true`, `matlab_exit_code=0`, `new_only=true`, and `resume_allowed=false`; the frozen request manifest SHA-256 is `048bd7286c8f46a780f9d3fc8b569ea94fe1a5f5563c2ce3e71420811337b442`.
- The output namespace is `scenes/F1023_midrain/sage_results/rain_sage_rerun_v1_20260827_r4/G24`. All 19 required Rain outputs are present and non-empty; no required output is missing. The new r4 namespace is distinct from and preserves the historical `scenes/F1023_midrain/sage_results/rain_sage_v1/G24` artifact.
- Independent read-only QA was completed with `scripts/sage_pipeline/rain/audit_rain_sage_task.py`. The QA artifacts are `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260829/rain__midrain__G24__ch8__fresh_r4_final/qa_report.md`, `qa_result.json`, and `artifact_hashes.csv`. Identity, artifact completeness, stage consistency, and numerical validity all passed; the overall QA result is `QA_PASS`.
- Stage statistics are: 2,688 Stage0 valid symbols; 2,686 complete 40-ms windows; 2,686 Stage1 scanned windows with 0 invalid scans; 468 Stage2 model rows (117 each for L=1,2,3,4), with 3 invalid-model rows retained as a diagnostic count; 117 selected windows; 68 Stage3 persistence rows; 3 Stage3 reliable centers; 3 Stage4 joint rows; and 3/3 `joint_valid` rows. The measured receipt interval was approximately 3,508.688 s (58.48 min).
- Under the strict project confirmation criterion (`joint_valid=1` AND `joint_multipath_count>0` AND a matching Stage4 path with `is_multipath=1`), this task produced 0 confirmed multipath events and 0 confirmed multipath paths. This is a valid zero-event result under the current criterion and is not interpreted as LOS or physical absence of multipath. Stage2 L>=2 and Stage3 reliable centers are not confirmed multipath.
- The independent QA did not open raw IQ, invoke MATLAB, invoke SAGE, or modify the existing output. No subsequent Rain task was started automatically; the next task remains subject to an explicit user decision.

```text
RAIN_MIDRAIN_G24_CH8_EXECUTION=COMPLETED
RAIN_MIDRAIN_G24_CH8_RECEIPT_STATUS=VALID
RAIN_MIDRAIN_G24_CH8_MATLAB_EXIT_CODE=0
RAIN_MIDRAIN_G24_CH8_OUTPUT_FILES=19_OF_19
RAIN_MIDRAIN_G24_CH8_INDEPENDENT_QA=PASS
RAIN_MIDRAIN_G24_CH8_SCIENTIFIC_STATUS=PASS_NO_CONFIRMED_MULTIPATH
RAIN_MIDRAIN_G24_CH8_CONFIRMED_EVENTS=0
RAIN_MIDRAIN_G24_CH8_CONFIRMED_PATHS=0
RAIN_MIDRAIN_G24_CH8_ARTIFACT_MODIFIED_BY_AUDITOR=NO
RAIN_MIDRAIN_G24_CH8_RAW_IQ_READ_BY_AUDITOR=NO
RAIN_MIDRAIN_G24_CH8_MATLAB_EXECUTED_BY_AUDITOR=NO
RAIN_MIDRAIN_G24_CH8_SAGE_EXECUTED_BY_AUDITOR=NO
RAIN_MIDRAIN_G24_CH8_OLD_ARTIFACT_PRESERVED=YES
NEXT_DECISION_REQUIRED=USER_AUTHORIZE_NEXT_RAIN_TASK
```

## 77. Rain MidRain G20/ch9 single-task request and dry-run (Prepared; execution not started, 2026-08-29)

- The next explicitly selected Rain task is `F1023_midrain/G20/ch9/10230000`. The current Rain checklist records it as `NOT_STARTED`, `PASS_STATIC_INPUT_GATE`, with the unique channel mapping `G20 -> ch9` and no existing new r4 output leaf. The historical `scenes/F1023_midrain/sage_results/rain_sage_v1/G20` namespace remains preserved.
- The immutable request manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_midrain__G20__ch9__20260829_r4/execution_manifest.json`, SHA-256 `e241977aac6611d707d20cdf0d72540ae7c535cd0eac6ef869385f1843d52c49`. It freezes the checklist-approved `G20 -> ch9` mapping, 10.23 MHz, the actual input provenance and byte hashes, `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, and `gold_labels_used_for_selection=false`.
- The expected new-only output namespace is `scenes/F1023_midrain/sage_results/rain_sage_rerun_v1_20260827_r4/G20`; it was absent during preparation and dry-run. The global Rain mutex was available. Validation-only wrapper execution passed with `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, and `SAGE_EXECUTED=false`; the emitted MATLAB expression explicitly uses `TrackingChannel,9` and `Resume,false`.
- No MATLAB, SAGE, or batch execution was started by Codex. Human normal-user execution is required. After completion, the receipt and all 19 required Rain outputs must receive independent read-only Stage0–Stage4 QA before the next Rain task is considered.

```text
RAIN_MIDRAIN_G20_CH9_REQUEST=PREPARED
RAIN_MIDRAIN_G20_CH9_MANIFEST_SHA256=e241977aac6611d707d20cdf0d72540ae7c535cd0eac6ef869385f1843d52c49
RAIN_MIDRAIN_G20_CH9_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_MIDRAIN_G20_CH9_GLOBAL_LOCK=AVAILABLE
RAIN_MIDRAIN_G20_CH9_DRY_RUN=PASS
RAIN_MIDRAIN_G20_CH9_EXECUTION=NOT_STARTED
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_MIDRAIN_G20_CH9_THEN_INDEPENDENT_QA
```

## 78. Rain MidRain G20/ch9 execution and independent QA (Completed; QA PASS, valid zero-event, 2026-08-29)

- The normal-user execution of the immutable MidRain request completed successfully. Receipt: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_midrain__G20__ch9__20260829_r4/receipts/rain_sage_single_task_v1__F1023_midrain__G20__ch9__20260829_r4_20260829T104637Z_receipt.json`. It records `status=COMPLETED`, `matlab_invoked=true`, `matlab_exit_code=0`, `new_only=true`, and `resume_allowed=false`; the frozen request manifest SHA-256 is `e241977aac6611d707d20cdf0d72540ae7c535cd0eac6ef869385f1843d52c49`.
- The output namespace is `scenes/F1023_midrain/sage_results/rain_sage_rerun_v1_20260827_r4/G20`. All 19 required Rain outputs are present and non-empty; no required output is missing. The new r4 namespace is distinct from and preserves the historical `scenes/F1023_midrain/sage_results/rain_sage_v1/G20` artifact.
- Independent read-only QA was completed with `scripts/sage_pipeline/rain/audit_rain_sage_task.py`. The QA artifacts are `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260829/rain__midrain__G20__ch9__fresh_r4_final/qa_report.md`, `qa_result.json`, and `artifact_hashes.csv`. Identity, artifact completeness, stage consistency, and numerical validity all passed; the overall QA result is `QA_PASS`.
- Stage statistics are: 2,689 Stage0 valid symbols; 2,687 complete 40-ms windows; 2,687 Stage1 scanned windows with 0 invalid scans; 480 Stage2 model rows (120 each for L=1,2,3,4); 120 selected windows; 121 Stage3 persistence rows; 14 Stage3 reliable centers; 8 Stage4 joint rows; and 8/8 `joint_valid` rows. No invalid Stage2 model rows were reported.
- Under the strict project confirmation criterion (`joint_valid=1` AND `joint_multipath_count>0` AND a matching Stage4 path with `is_multipath=1`), this task produced 0 confirmed multipath events and 0 confirmed multipath paths. All eight Stage4 path rows are non-multipath (`is_multipath=0`). This is a valid zero-event result under the current criterion and is not interpreted as LOS or physical absence of multipath. Stage2 L>=2 and Stage3 reliable centers are not confirmed multipath.
- The measured receipt interval was approximately 3,545.391875 s (59.09 min). The independent QA did not open raw IQ, invoke MATLAB, invoke SAGE, or modify the existing output. No subsequent Rain task was started automatically; the next task remains subject to an explicit user decision.

```text
RAIN_MIDRAIN_G20_CH9_EXECUTION=COMPLETED
RAIN_MIDRAIN_G20_CH9_RECEIPT_STATUS=VALID
RAIN_MIDRAIN_G20_CH9_MATLAB_EXIT_CODE=0
RAIN_MIDRAIN_G20_CH9_OUTPUT_FILES=19_OF_19
RAIN_MIDRAIN_G20_CH9_INDEPENDENT_QA=PASS
RAIN_MIDRAIN_G20_CH9_SCIENTIFIC_STATUS=PASS_NO_CONFIRMED_MULTIPATH
RAIN_MIDRAIN_G20_CH9_CONFIRMED_EVENTS=0
RAIN_MIDRAIN_G20_CH9_CONFIRMED_PATHS=0
RAIN_MIDRAIN_G20_CH9_ARTIFACT_MODIFIED_BY_AUDITOR=NO
RAIN_MIDRAIN_G20_CH9_RAW_IQ_READ_BY_AUDITOR=NO
RAIN_MIDRAIN_G20_CH9_MATLAB_EXECUTED_BY_AUDITOR=NO
RAIN_MIDRAIN_G20_CH9_SAGE_EXECUTED_BY_AUDITOR=NO
RAIN_MIDRAIN_G20_CH9_OLD_ARTIFACT_PRESERVED=YES
NEXT_DECISION_REQUIRED=USER_AUTHORIZE_NEXT_RAIN_TASK
```

## 79. Rain Clear G29/ch3 single-task request and dry-run (Prepared; execution not started, 2026-08-29)

- The next explicitly selected Rain task is `F1023_clear/G29/ch3/10230000`. The current Rain checklist records it as `NOT_STARTED`, `PASS_STATIC_INPUT_GATE`, with the unique channel mapping `G29 -> ch3` and no existing new r4 output leaf. The historical `scenes/F1023_clear/sage_results/rain_sage_v1/G29` namespace remains preserved.
- The immutable request manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_clear__G29__ch3__20260829_r4/execution_manifest.json`, SHA-256 `ecfbc361883f299c59a99f88488fb45b89cfdd9d66ec52ed3175b66813d2dc0e`. It freezes the checklist-approved `G29 -> ch3` mapping, Clear, 10.23 MHz, the actual input provenance and byte hashes, `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, and `gold_labels_used_for_selection=false`.
- The expected new-only output namespace is `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r4/G29`; it was absent during preparation and dry-run. The global Rain mutex was available. Validation-only wrapper execution passed with `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, and `SAGE_EXECUTED=false`; the emitted MATLAB expression explicitly uses `TrackingChannel,3` and `Resume,false`.
- No MATLAB, SAGE, or batch execution was started by Codex. Human normal-user execution is required. After completion, the receipt and all 19 required Rain outputs must receive independent read-only Stage0–Stage4 QA before the next Rain task is considered.

```text
RAIN_CLEAR_G29_CH3_REQUEST=PREPARED
RAIN_CLEAR_G29_CH3_MANIFEST_SHA256=ecfbc361883f299c59a99f88488fb45b89cfdd9d66ec52ed3175b66813d2dc0e
RAIN_CLEAR_G29_CH3_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_CLEAR_G29_CH3_GLOBAL_LOCK=AVAILABLE
RAIN_CLEAR_G29_CH3_DRY_RUN=PASS
RAIN_CLEAR_G29_CH3_EXECUTION=NOT_STARTED
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_CLEAR_G29_CH3_THEN_INDEPENDENT_QA
```

## 80. Rain Clear G29/ch3 execution and independent QA (Completed; QA PASS, valid zero-event, 2026-08-29)

- The normal-user execution of the immutable Clear request completed successfully. Receipt: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_clear__G29__ch3__20260829_r4/receipts/rain_sage_single_task_v1__F1023_clear__G29__ch3__20260829_r4_20260829T115348Z_receipt.json`. It records `status=COMPLETED`, `matlab_invoked=true`, `matlab_exit_code=0`, `new_only=true`, and `resume_allowed=false`; the frozen request manifest SHA-256 is `ecfbc361883f299c59a99f88488fb45b89cfdd9d66ec52ed3175b66813d2dc0e`.
- The output namespace is `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r4/G29`. All 19 required Rain outputs are present and non-empty; no required output is missing. The new r4 namespace is distinct from and preserves the historical `scenes/F1023_clear/sage_results/rain_sage_v1/G29` artifact.
- Independent read-only QA was completed with `scripts/sage_pipeline/rain/audit_rain_sage_task.py`. The QA artifacts are `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260829/rain__clear__G29__ch3__fresh_r4_final/qa_report.md`, `qa_result.json`, and `artifact_hashes.csv`. Identity, artifact completeness, stage consistency, and numerical validity all passed; the overall QA result is `QA_PASS`.
- Stage statistics are: 2,806 Stage0 valid symbols; 2,804 complete 40-ms windows; 2,804 Stage1 scanned windows with 0 invalid scans; 472 Stage2 model rows (118 each for L=1,2,3,4); 118 selected windows; 88 Stage3 persistence rows; 9 Stage3 reliable centers; 8 Stage4 joint rows; and 8/8 `joint_valid` rows. Six invalid Stage2 model rows remain recorded as a diagnostic count and did not prevent the complete Stage4 artifact from passing independent QA.
- Under the strict project confirmation criterion (`joint_valid=1` AND `joint_multipath_count>0` AND a matching Stage4 path with `is_multipath=1`), this task produced 0 confirmed multipath events and 0 confirmed multipath paths. All eight Stage4 path rows have `is_multipath=0`. This is a valid zero-event result under the current criterion and is not interpreted as LOS or physical absence of multipath. Stage2 L>=2 and Stage3 reliable centers are not confirmed multipath.
- The measured receipt interval was approximately 8,972.357 s (149.54 min). The independent QA did not open raw IQ, invoke MATLAB, invoke SAGE, or modify the existing output. No subsequent Rain task was started automatically; the next task remains subject to an explicit user decision.

```text
RAIN_CLEAR_G29_CH3_EXECUTION=COMPLETED
RAIN_CLEAR_G29_CH3_RECEIPT_STATUS=VALID
RAIN_CLEAR_G29_CH3_MATLAB_EXIT_CODE=0
RAIN_CLEAR_G29_CH3_OUTPUT_FILES=19_OF_19
RAIN_CLEAR_G29_CH3_INDEPENDENT_QA=PASS
RAIN_CLEAR_G29_CH3_SCIENTIFIC_STATUS=PASS_NO_CONFIRMED_MULTIPATH
RAIN_CLEAR_G29_CH3_CONFIRMED_EVENTS=0
RAIN_CLEAR_G29_CH3_CONFIRMED_PATHS=0
RAIN_CLEAR_G29_CH3_ARTIFACT_MODIFIED_BY_AUDITOR=NO
RAIN_CLEAR_G29_CH3_RAW_IQ_READ_BY_AUDITOR=NO
RAIN_CLEAR_G29_CH3_MATLAB_EXECUTED_BY_AUDITOR=NO
RAIN_CLEAR_G29_CH3_SAGE_EXECUTED_BY_AUDITOR=NO
RAIN_CLEAR_G29_CH3_OLD_ARTIFACT_PRESERVED=YES
NEXT_DECISION_REQUIRED=USER_AUTHORIZE_NEXT_RAIN_TASK
```

## 81. Rain Clear G13/ch8 single-task request and dry-run (Prepared; execution not started, 2026-08-29)

- The next explicitly selected Rain task is `F1023_clear/G13/ch8/10230000`. The current Rain checklist records it as `NOT_STARTED`, `PASS_STATIC_INPUT_GATE`, with the unique channel mapping `G13 -> ch8` and no existing new r4 output leaf. The historical `scenes/F1023_clear/sage_results/rain_sage_v1/G13` namespace remains preserved.
- The immutable request manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_clear__G13__ch8__20260829_r4/execution_manifest.json`, SHA-256 `e0f5219e3e2c4eea602efbb21811bae64d5c57cc333853ce27095e3f4ee8af5a`. It freezes the checklist-approved `G13 -> ch8` mapping, Clear, 10.23 MHz, the actual input provenance and byte hashes, `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, and `gold_labels_used_for_selection=false`.
- The expected new-only output namespace is `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r4/G13`; it was absent during preparation and dry-run. The global Rain mutex was available. Validation-only wrapper execution passed with `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, and `SAGE_EXECUTED=false`; the emitted MATLAB expression explicitly uses `TrackingChannel,8` and `Resume,false`.
- No MATLAB, SAGE, or batch execution was started by Codex. Human normal-user execution is required. After completion, the receipt and all 19 required Rain outputs must receive independent read-only Stage0–Stage4 QA before the next Rain task is considered.

```text
RAIN_CLEAR_G13_CH8_REQUEST=PREPARED
RAIN_CLEAR_G13_CH8_MANIFEST_SHA256=e0f5219e3e2c4eea602efbb21811bae64d5c57cc333853ce27095e3f4ee8af5a
RAIN_CLEAR_G13_CH8_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_CLEAR_G13_CH8_GLOBAL_LOCK=AVAILABLE
RAIN_CLEAR_G13_CH8_DRY_RUN=PASS
RAIN_CLEAR_G13_CH8_EXECUTION=NOT_STARTED
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_CLEAR_G13_CH8_THEN_INDEPENDENT_QA
```

## 82. Rain Clear G13/ch8 execution and independent QA (Completed; QA PASS, valid zero-event, 2026-08-30)

- The normal-user execution of the immutable Clear request completed successfully. Receipt: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_clear__G13__ch8__20260829_r4/receipts/rain_sage_single_task_v1__F1023_clear__G13__ch8__20260829_r4_20260829T143207Z_receipt.json`. It records `status=COMPLETED`, `matlab_invoked=true`, `matlab_exit_code=0`, `new_only=true`, and `resume_allowed=false`; the frozen request manifest SHA-256 is `e0f5219e3e2c4eea602efbb21811bae64d5c57cc333853ce27095e3f4ee8af5a`.
- The output namespace is `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r4/G13`. All 19 required Rain outputs are present and non-empty; no required output is missing. The new r4 namespace is distinct from and preserves the historical `scenes/F1023_clear/sage_results/rain_sage_v1/G13` artifact.
- Independent read-only QA was completed with `scripts/sage_pipeline/rain/audit_rain_sage_task.py`. The QA artifacts are `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260830/rain__clear__G13__ch8__fresh_r4_final/qa_report.md`, `qa_result.json`, and `artifact_hashes.csv`. Identity, artifact completeness, stage consistency, and numerical validity all passed; the overall QA result is `QA_PASS`.
- Stage statistics are: 2,806 Stage0 valid symbols; 2,804 complete 40-ms windows; 2,804 Stage1 scanned windows with 0 invalid scans; 480 Stage2 model rows (120 each for L=1,2,3,4); 120 selected windows; 89 Stage3 persistence rows; 2 Stage3 reliable centers; 2 Stage4 joint rows; and 2/2 `joint_valid` rows. Two invalid Stage2 model rows remain recorded as a diagnostic count and did not prevent the complete Stage4 artifact from passing independent QA.
- Under the strict project confirmation criterion (`joint_valid=1` AND `joint_multipath_count>0` AND a matching Stage4 path with `is_multipath=1`), this task produced 0 confirmed multipath events and 0 confirmed multipath paths. This is a valid zero-event result under the current criterion and is not interpreted as LOS or physical absence of multipath. Stage2 L>=2 and Stage3 reliable centers are not confirmed multipath.
- The measured receipt interval was approximately 7,236.083 s (120.60 min). The independent QA did not open raw IQ, invoke MATLAB, invoke SAGE, or modify the existing output. No subsequent Rain task was started automatically; the next task remains subject to an explicit user decision.

```text
RAIN_CLEAR_G13_CH8_EXECUTION=COMPLETED
RAIN_CLEAR_G13_CH8_RECEIPT_STATUS=VALID
RAIN_CLEAR_G13_CH8_MATLAB_EXIT_CODE=0
RAIN_CLEAR_G13_CH8_OUTPUT_FILES=19_OF_19
RAIN_CLEAR_G13_CH8_INDEPENDENT_QA=PASS
RAIN_CLEAR_G13_CH8_SCIENTIFIC_STATUS=PASS_NO_CONFIRMED_MULTIPATH
RAIN_CLEAR_G13_CH8_CONFIRMED_EVENTS=0
RAIN_CLEAR_G13_CH8_CONFIRMED_PATHS=0
RAIN_CLEAR_G13_CH8_ARTIFACT_MODIFIED_BY_AUDITOR=NO
RAIN_CLEAR_G13_CH8_RAW_IQ_READ_BY_AUDITOR=NO
RAIN_CLEAR_G13_CH8_MATLAB_EXECUTED_BY_AUDITOR=NO
RAIN_CLEAR_G13_CH8_SAGE_EXECUTED_BY_AUDITOR=NO
RAIN_CLEAR_G13_CH8_OLD_ARTIFACT_PRESERVED=YES
NEXT_DECISION_REQUIRED=USER_AUTHORIZE_NEXT_RAIN_TASK
```

## 83. Rain Clear G12/ch11 single-task request and dry-run (Prepared; execution not started, 2026-08-30)

- The next explicitly selected Rain task is `F1023_clear/G12/ch11/10230000`. The current Rain checklist records it as `NOT_STARTED`, `PASS_STATIC_INPUT_GATE`, with the unique channel mapping `G12 -> ch11` and no existing new r4 output leaf. The historical `scenes/F1023_clear/sage_results/rain_sage_v1/G12` namespace remains preserved.
- The immutable request manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_clear__G12__ch11__20260829_r4/execution_manifest.json`, SHA-256 `a9430b713b1c172a19c7d6d5a35d5ef983185d5f1e306a1049d6e638c2281a5d`. It freezes the checklist-approved `G12 -> ch11` mapping, Clear, 10.23 MHz, the actual input provenance and byte hashes, `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, and `gold_labels_used_for_selection=false`.
- The expected new-only output namespace is `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r4/G12`; it was absent during preparation and dry-run. The global Rain mutex was available. Validation-only wrapper execution passed with `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, and `SAGE_EXECUTED=false`; the emitted MATLAB expression explicitly uses `TrackingChannel,11` and `Resume,false`.
- No MATLAB, SAGE, or batch execution was started by Codex. Human normal-user execution is required. After completion, the receipt and all 19 required Rain outputs must receive independent read-only Stage0–Stage4 QA before the next Rain task is considered.

```text
RAIN_CLEAR_G12_CH11_REQUEST=PREPARED
RAIN_CLEAR_G12_CH11_MANIFEST_SHA256=a9430b713b1c172a19c7d6d5a35d5ef983185d5f1e306a1049d6e638c2281a5d
RAIN_CLEAR_G12_CH11_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_CLEAR_G12_CH11_GLOBAL_LOCK=AVAILABLE
RAIN_CLEAR_G12_CH11_DRY_RUN=PASS
RAIN_CLEAR_G12_CH11_EXECUTION=NOT_STARTED
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_CLEAR_G12_CH11_THEN_INDEPENDENT_QA
```

## 84. Phase-1 traditional channel-modeling scientific closure (Completed with limitations + independent QA PASS, 2026-08-30)

- The canonical traditional model remains the frozen r3 namespace `dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3/`, model manifest SHA-256=`61c4b3aa171b6a59d17607394770b684251d656eeb19813ca13ebed2454b1782`, with its independent QA still `PASS`.
- Phase-1 closure was completed in the new-only namespace `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/`; closure manifest SHA-256=`45282b4eb5f86e52f4cd39f9b94f04c1596b645cae3d0b6420a089717f429d52`; independent closure QA is `PASS` with 75 checks. The earlier r1 closure namespace is retained only as superseded audit history.
- The closure is an academic/statistical interpretation layer over r3, not a new SAGE or MATLAB production capability. It preserves the weighted-observation contract, scene/run clustering, scene-block bootstrap, grouped LOSO, the 12-cell support matrix, Stage4 selection-only semantics, and the `RICEAN_K = NOT_IDENTIFIABLE` boundary.
- No production request, MATLAB/SAGE task, raw-IQ read, Stage0–Stage4 rerun, 20.46 MHz processing, source/wrapper/executor/manifest/inventory modification, Stage4 modification, or darkroom execution was performed. Frozen source/wrapper/executor/manifest/inventory hashes were independently rechecked and matched r3 records.

```text
PHASE_1_TRADITIONAL_MODEL_BUILD = COMPLETE
PHASE_1_SCIENTIFIC_CLOSURE = PASS_WITH_LIMITATIONS
PHASE_1_CLOSURE_INDEPENDENT_QA = PASS
JOURNAL_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
MASTER_THESIS_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
ENVIRONMENT_EFFECT = INCONCLUSIVE
ELEVATION_EFFECT = INCONCLUSIVE
ENVIRONMENT_ELEVATION_INTERACTION = PARTIAL
AI_JOINT_DENSITY_MOTIVATION = STRONG
CONTINUOUS_ELEVATION_FOR_PHASE2 = CONDITIONAL
PHASE_2_EXECUTION_AUTHORIZED = NO
MATLAB_EXECUTED_BY_CODEX = NO
SAGE_EXECUTED_BY_CODEX = NO
BATCH_EXECUTED_BY_CODEX = NO
NEXT_DECISION_REQUIRED=AUTHORIZE PHASE-2 DESIGN/TRAINING OR HOLD
```

## 85. Rain Clear G12/ch11 execution and independent QA (Completed; QA PASS, confirmed event, 2026-08-30)

- The normal-user execution of the immutable Clear request completed successfully. Receipt: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_clear__G12__ch11__20260829_r4/receipts/rain_sage_single_task_v1__F1023_clear__G12__ch11__20260829_r4_20260829T171405Z_receipt.json`. It records `status=COMPLETED`, `matlab_invoked=true`, `matlab_exit_code=0`, `new_only=true`, and `resume_allowed=false`; the frozen request manifest SHA-256 is `a9430b713b1c172a19c7d6d5a35d5ef983185d5f1e306a1049d6e638c2281a5d`.
- The output namespace is `scenes/F1023_clear/sage_results/rain_sage_rerun_v1_20260827_r4/G12`. All 19 required Rain outputs are present and non-empty; no required output is missing. The new r4 namespace is distinct from and preserves the historical `scenes/F1023_clear/sage_results/rain_sage_v1/G12` artifact.
- Independent read-only QA was completed with `scripts/sage_pipeline/rain/audit_rain_sage_task.py`. The QA artifacts are `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260830/rain__clear__G12__ch11__fresh_r4_final/qa_report.md`, `qa_result.json`, and `artifact_hashes.csv`. Identity, artifact completeness, stage consistency, and numerical validity all passed; the overall result is `QA_PASS`.
- Stage statistics are: 2,805 Stage0 valid symbols; 2,803 complete 40-ms windows; 2,803 Stage1 scanned windows with 0 invalid scans; 480 Stage2 model rows (120 each for L=1,2,3,4); 120 selected windows; 193 Stage3 persistence rows; 7 Stage3 reliable centers; 7 Stage4 joint rows; and 7/7 `joint_valid` rows. Forty-five invalid Stage2 model rows remain recorded as a diagnostic count and did not prevent the complete Stage4 artifact from passing independent QA.
- Under the strict project confirmation criterion (`joint_valid=1` AND `joint_multipath_count>0` AND a matching Stage4 path with `is_multipath=1`), this task produced 1 confirmed multipath event and 1 confirmed multipath path. The confirmed center is window `1624`; its confirmed path has `excess_delay_samples=1`, `doppler_offset_hz=9.66430209528471`, and `mean_relative_power_db=-7.85881504136226`. These are artifact-level facts and are not generalized as a weather or environment conclusion. Stage2 L>=2 and Stage3 reliable centers are not themselves confirmed multipath.
- The measured receipt interval was approximately 6,884.261 s (114.74 min). The independent QA did not open raw IQ, invoke MATLAB, invoke SAGE, or modify the existing output. No subsequent Rain task was started automatically; the next task remains subject to an explicit user decision.

```text
RAIN_CLEAR_G12_CH11_EXECUTION=COMPLETED
RAIN_CLEAR_G12_CH11_RECEIPT_STATUS=VALID
RAIN_CLEAR_G12_CH11_MATLAB_EXIT_CODE=0
RAIN_CLEAR_G12_CH11_OUTPUT_FILES=19_OF_19
RAIN_CLEAR_G12_CH11_INDEPENDENT_QA=PASS
RAIN_CLEAR_G12_CH11_SCIENTIFIC_STATUS=PASS_WITH_CONFIRMED_MULTIPATH
RAIN_CLEAR_G12_CH11_CONFIRMED_EVENTS=1
RAIN_CLEAR_G12_CH11_CONFIRMED_PATHS=1
RAIN_CLEAR_G12_CH11_CONFIRMED_CENTER=1624
RAIN_CLEAR_G12_CH11_ARTIFACT_MODIFIED_BY_AUDITOR=NO
RAIN_CLEAR_G12_CH11_RAW_IQ_READ_BY_AUDITOR=NO
RAIN_CLEAR_G12_CH11_MATLAB_EXECUTED_BY_AUDITOR=NO
RAIN_CLEAR_G12_CH11_SAGE_EXECUTED_BY_AUDITOR=NO
RAIN_CLEAR_G12_CH11_OLD_ARTIFACT_PRESERVED=YES
NEXT_DECISION_REQUIRED=USER_AUTHORIZE_NEXT_RAIN_TASK
```

## 86. Rain HeavyRain G31/ch4 single-task request and dry-run (Prepared; execution not started, 2026-08-30)

- The next explicitly selected Rain task is `F1023_heavyrain/G31/ch4/10230000`. The current Rain checklist records it as `NOT_STARTED`, `PASS_STATIC_INPUT_GATE`, with the unique channel mapping `G31 -> ch4` and no existing new r4 output leaf. The historical `scenes/F1023_heavyrain/sage_results/rain_sage_v1/G31` namespace remains preserved.
- The immutable request manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_heavyrain__G31__ch4__20260829_r4/execution_manifest.json`, SHA-256 `e477ae6ffe0a35c40b07395b1ffefacba58113887a3e272eb74e465e8dcd0709`. It freezes the checklist-approved `G31 -> ch4` mapping, HeavyRain, 10.23 MHz, the actual input provenance and byte hashes, `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, and `gold_labels_used_for_selection=false`.
- The expected new-only output namespace is `scenes/F1023_heavyrain/sage_results/rain_sage_rerun_v1_20260827_r4/G31`; it was absent during preparation and dry-run. The global Rain mutex was available. Validation-only wrapper execution passed with `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, and `SAGE_EXECUTED=false`; the emitted MATLAB expression explicitly uses `TrackingChannel,4` and `Resume,false`.
- No MATLAB, SAGE, or batch execution was started by Codex. Human normal-user execution is required. After completion, the receipt and all 19 required Rain outputs must receive independent read-only Stage0–Stage4 QA before the next Rain task is considered.

```text
RAIN_HEAVYRAIN_G31_CH4_REQUEST=PREPARED
RAIN_HEAVYRAIN_G31_CH4_MANIFEST_SHA256=e477ae6ffe0a35c40b07395b1ffefacba58113887a3e272eb74e465e8dcd0709
RAIN_HEAVYRAIN_G31_CH4_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_HEAVYRAIN_G31_CH4_GLOBAL_LOCK=AVAILABLE
RAIN_HEAVYRAIN_G31_CH4_DRY_RUN=PASS
RAIN_HEAVYRAIN_G31_CH4_EXECUTION=NOT_STARTED
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_HEAVYRAIN_G31_CH4_THEN_INDEPENDENT_QA
```

## 87. Rain HeavyRain G31/ch4 execution and independent QA (Completed; QA PASS, confirmed event, 2026-08-30)

- The normal-user execution of the immutable HeavyRain request completed successfully. Receipt: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_heavyrain__G31__ch4__20260829_r4/receipts/rain_sage_single_task_v1__F1023_heavyrain__G31__ch4__20260829_r4_20260830T052857Z_receipt.json`. It records `status=COMPLETED`, `matlab_invoked=true`, `matlab_exit_code=0`, `new_only=true`, and `resume_allowed=false`; the frozen request manifest SHA-256 is `e477ae6ffe0a35c40b07395b1ffefacba58113887a3e272eb74e465e8dcd0709`.
- The output namespace is `scenes/F1023_heavyrain/sage_results/rain_sage_rerun_v1_20260827_r4/G31`. All 19 required Rain outputs are present and non-empty; no required output is missing. The new r4 namespace is distinct from and preserves the historical `scenes/F1023_heavyrain/sage_results/rain_sage_v1/G31` artifact. The execution stdout ends with `RAIN_FRESH_RERUN_COMPLETED` and the expected task/output summary; stderr is empty.
- Independent read-only QA was completed with `scripts/sage_pipeline/rain/audit_rain_sage_task.py`. The QA artifacts are `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260830/rain__heavyrain__G31__ch4__fresh_r4_final/qa_report.md`, `qa_result.json`, and `artifact_hashes.csv`. Identity, artifact completeness, stage consistency, and numerical validity all passed; the overall QA result is `QA_PASS`.
- Stage statistics are: 2,565 Stage0 valid symbols; 2,563 complete 40-ms windows; 2,563 Stage1 scanned windows with 0 invalid scans; 460 Stage2 model rows (115 each for L=1,2,3,4); 115 selected windows; 164 Stage3 persistence rows; 6 Stage3 reliable centers; 6 Stage4 joint rows; and 6/6 `joint_valid` rows. Thirty-five invalid Stage2 model rows remain recorded as a diagnostic count and did not prevent the complete Stage4 artifact from passing independent QA.
- Under the strict project confirmation criterion (`joint_valid=1` AND `joint_multipath_count>0` AND a matching Stage4 path with `is_multipath=1`), this task produced 1 confirmed multipath event and 1 confirmed multipath path. The confirmed center is window `488`; its Stage4 path has `excess_delay_samples=1.1`, `doppler_offset_hz=4.66430209528517`, `mean_relative_power_db=-0.288160839981504`, `relative_phase_rad=-3.10657929808978`, and `relative_amplitude=0.557247640438373`. These are artifact-level facts and are not generalized as a weather conclusion. Stage2 L>=2 and Stage3 reliable centers are not themselves confirmed multipath.
- The measured receipt interval was approximately 8,943.809 s (149.06 min). The independent QA did not open raw IQ, invoke MATLAB, invoke SAGE, or modify the existing output. No subsequent Rain task was started automatically; the next task remains subject to an explicit user decision.

```text
RAIN_HEAVYRAIN_G31_CH4_EXECUTION=COMPLETED
RAIN_HEAVYRAIN_G31_CH4_RECEIPT_STATUS=VALID
RAIN_HEAVYRAIN_G31_CH4_MATLAB_EXIT_CODE=0
RAIN_HEAVYRAIN_G31_CH4_OUTPUT_FILES=19_OF_19
RAIN_HEAVYRAIN_G31_CH4_INDEPENDENT_QA=PASS
RAIN_HEAVYRAIN_G31_CH4_SCIENTIFIC_STATUS=PASS_WITH_CONFIRMED_MULTIPATH
RAIN_HEAVYRAIN_G31_CH4_CONFIRMED_EVENTS=1
RAIN_HEAVYRAIN_G31_CH4_CONFIRMED_PATHS=1
RAIN_HEAVYRAIN_G31_CH4_CONFIRMED_CENTER=488
RAIN_HEAVYRAIN_G31_CH4_ARTIFACT_MODIFIED_BY_AUDITOR=NO
RAIN_HEAVYRAIN_G31_CH4_RAW_IQ_READ_BY_AUDITOR=NO
RAIN_HEAVYRAIN_G31_CH4_MATLAB_EXECUTED_BY_AUDITOR=NO
RAIN_HEAVYRAIN_G31_CH4_SAGE_EXECUTED_BY_AUDITOR=NO
RAIN_HEAVYRAIN_G31_CH4_OLD_ARTIFACT_PRESERVED=YES
NEXT_DECISION_REQUIRED=USER_AUTHORIZE_NEXT_RAIN_TASK
```

## 88. Rain HeavyRain G01/ch7 single-task request and dry-run (Prepared; execution not started, 2026-08-30)

- The next explicitly selected Rain task is `F1023_heavyrain/G01/ch7/10230000`. The current Rain checklist records it as `NOT_STARTED`, `PASS_STATIC_INPUT_GATE`, with the unique channel mapping `G01 -> ch7` and no existing new r4 output leaf. The historical `scenes/F1023_heavyrain/sage_results/rain_sage_v1/G01` namespace is not present as a completed artifact.
- The immutable request manifest is `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_heavyrain__G01__ch7__20260829_r4/execution_manifest.json`, SHA-256 `ddd7efa55c4fca75d13ac7072b753e9fffbc2a4d268d3e68faf9bc7155fb617e`. It freezes the checklist-approved `G01 -> ch7` mapping, HeavyRain, 10.23 MHz, the actual input provenance and byte hashes, `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1`, and `gold_labels_used_for_selection=false`.
- The expected new-only output namespace is `scenes/F1023_heavyrain/sage_results/rain_sage_rerun_v1_20260827_r4/G01`; it was absent during preparation and dry-run. The global Rain mutex was available. Validation-only wrapper execution passed with `EXECUTION_ELIGIBLE=true`, `MATLAB_INVOKED=false`, `RAW_IQ_OPENED=false`, and `SAGE_EXECUTED=false`; the emitted MATLAB expression explicitly uses `TrackingChannel,7` and `Resume,false`.
- No MATLAB, SAGE, or batch execution was started by Codex. Human normal-user execution is required. After completion, the receipt and all 19 required Rain outputs must receive independent read-only Stage0–Stage4 QA before the next Rain task is considered.

```text
RAIN_HEAVYRAIN_G01_CH7_REQUEST=PREPARED
RAIN_HEAVYRAIN_G01_CH7_MANIFEST_SHA256=ddd7efa55c4fca75d13ac7072b753e9fffbc2a4d268d3e68faf9bc7155fb617e
RAIN_HEAVYRAIN_G01_CH7_OUTPUT_NAMESPACE_ABSENT=YES
RAIN_HEAVYRAIN_G01_CH7_GLOBAL_LOCK=AVAILABLE
RAIN_HEAVYRAIN_G01_CH7_DRY_RUN=PASS
RAIN_HEAVYRAIN_G01_CH7_EXECUTION=NOT_STARTED
MATLAB_EXECUTED_BY_CODEX=NO
SAGE_EXECUTED_BY_CODEX=NO
NEXT_DECISION_REQUIRED=HUMAN_EXECUTE_HEAVYRAIN_G01_CH7_THEN_INDEPENDENT_QA
```

## 89. Rain HeavyRain G01/ch7 execution and independent QA (Completed; QA PASS, confirmed event, 2026-08-30)

- The normal-user execution of the immutable HeavyRain request completed successfully. Receipt: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_task_requests_20260829/rain_sage_single_task_v1__F1023_heavyrain__G01__ch7__20260829_r4/receipts/rain_sage_single_task_v1__F1023_heavyrain__G01__ch7__20260829_r4_20260830T083805Z_receipt.json`. It records `status=COMPLETED`, `matlab_invoked=true`, `matlab_exit_code=0`, `new_only=true`, and `resume_allowed=false`; the frozen request manifest SHA-256 is `ddd7efa55c4fca75d13ac7072b753e9fffbc2a4d268d3e68faf9bc7155fb617e`.
- The output namespace is `scenes/F1023_heavyrain/sage_results/rain_sage_rerun_v1_20260827_r4/G01`. All 19 required Rain outputs are present and non-empty; no required output is missing. The new r4 namespace is distinct from and preserves the historical Rain namespace policy; no previous artifact was reused or overwritten. The execution stdout ends with `RAIN_FRESH_RERUN_COMPLETED` and the expected G01/ch7 summary; stderr is empty.
- Independent read-only QA was completed with `scripts/sage_pipeline/rain/audit_rain_sage_task.py`. The final QA artifacts are `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260830/rain__heavyrain__G01__ch7__fresh_r4_final_v2/qa_report.md`, `qa_result.json`, and `artifact_hashes.csv`. Identity, artifact completeness, stage consistency, and numerical validity all passed; the overall QA result is `QA_PASS`. An earlier audit invocation used an invalid extended-path spelling and produced a separate inconclusive diagnostic namespace; that diagnostic artifact was retained and is not the final QA result.
- Stage statistics are: 2,865 Stage0 valid symbols; 2,863 complete 40-ms windows; 2,863 Stage1 scanned windows with 0 invalid scans; 480 Stage2 model rows (120 each for L=1,2,3,4); 120 selected windows; 197 Stage3 persistence rows; 5 Stage3 reliable centers; 5 Stage4 joint rows; and 5/5 `joint_valid` rows. Twenty-five invalid Stage2 model rows remain recorded as a diagnostic count and did not prevent the complete Stage4 artifact from passing independent QA.
- Under the strict project confirmation criterion (`joint_valid=1` AND `joint_multipath_count>0` AND a matching Stage4 path with `is_multipath=1`), this task produced 1 confirmed multipath event and 1 confirmed multipath path. The confirmed center is window `2519`; its Stage4 path has `excess_delay_samples=1.1`, `doppler_offset_hz=14.6643020952847`, `mean_relative_power_db=-9.18660454185309`, `relative_phase_rad=-3.08911682293025`, and `relative_amplitude=0.541765400486335`. These are artifact-level facts and are not generalized as a weather conclusion. Stage2 L>=2 and Stage3 reliable centers are not themselves confirmed multipath.
- The measured receipt interval was approximately 16,231.773 s (270.53 min). The independent QA did not open raw IQ, invoke MATLAB, invoke SAGE, or modify the existing output. No subsequent Rain task was started automatically; the next task remains subject to an explicit user decision.

```text
RAIN_HEAVYRAIN_G01_CH7_EXECUTION=COMPLETED
RAIN_HEAVYRAIN_G01_CH7_RECEIPT_STATUS=VALID
RAIN_HEAVYRAIN_G01_CH7_MATLAB_EXIT_CODE=0
RAIN_HEAVYRAIN_G01_CH7_OUTPUT_FILES=19_OF_19
RAIN_HEAVYRAIN_G01_CH7_INDEPENDENT_QA=PASS
RAIN_HEAVYRAIN_G01_CH7_SCIENTIFIC_STATUS=PASS_WITH_CONFIRMED_MULTIPATH
RAIN_HEAVYRAIN_G01_CH7_CONFIRMED_EVENTS=1
RAIN_HEAVYRAIN_G01_CH7_CONFIRMED_PATHS=1
RAIN_HEAVYRAIN_G01_CH7_CONFIRMED_CENTER=2519
RAIN_HEAVYRAIN_G01_CH7_ARTIFACT_MODIFIED_BY_AUDITOR=NO
RAIN_HEAVYRAIN_G01_CH7_RAW_IQ_READ_BY_AUDITOR=NO
RAIN_HEAVYRAIN_G01_CH7_MATLAB_EXECUTED_BY_AUDITOR=NO
RAIN_HEAVYRAIN_G01_CH7_SAGE_EXECUTED_BY_AUDITOR=NO
RAIN_HEAVYRAIN_G01_CH7_OLD_ARTIFACT_PRESERVED=YES
NEXT_DECISION_REQUIRED=USER_AUTHORIZE_NEXT_RAIN_TASK
```

## 90. Rain Stage3 effect-layer route decision and nine-task audit (Planned / Not started, 2026-08-30)

- All nine approved 10.23 MHz Rain tasks now have completed r4 outputs and at least one independent QA result with `overall_status=QA_PASS` and `execution_receipt_status=VALID`: Clear `G24/ch10`, `G29/ch3`, `G13/ch8`, `G12/ch11`; MidRain `G24/ch8`, `G20/ch9`; HeavyRain `G02/ch1`, `G31/ch4`, `G01/ch7`.
- A read-only Stage3 audit found 24,277 complete Stage0 windows, 1,070 Stage2 selected windows, 1,166 Stage3 persistence rows, 55 Stage3 reliable centers, and 90 path rows that both have `persistence_pass=1` and belong to a reliable center. Structural checks found no duplicate center/path keys, no non-finite delay/Doppler/power values, no selected-order/path-count mismatch, and no accepted run shorter than the frozen three-window persistence requirement.
- Weather support is uneven and internally correlated. Clear contributes 21 centers/31 path rows across four tasks; MidRain contributes 17/17 across two tasks; HeavyRain contributes 17/42 across three tasks. Connecting reliable centers whose frozen `center +/- 2` support intervals overlap gives only 10 Clear, 8 MidRain, and 8 HeavyRain episodes. These episode counts, not the raw 90 rows, define the primary independence boundary for fitting and resampling.
- Commander direction for the Darkroom Rain branch is now to use Stage3 reliable evidence as the inclusion layer for weather-effect modeling because the Stage4 joint-confirmation subset is too restrictive for this specific exploratory model. This does **not** alter, delete, or weaken Stage4 or the global production confirmed-multipath criterion. Stage3 records remain `reliable multipath evidence`, not `confirmed multipath path`; all model manifests and reports must retain that wording. Stage4 artifacts remain immutable and may be retained only as a strict-reference subset, not as the fitting gate.
- The Rain recordings have no validated elevation conditioning and no PRN common to all three weather states. Only G24 forms a Clear/MidRain matched-PRN sensitivity pair; HeavyRain is unpaired. Therefore the planned deliverable is a weather-conditioned empirical transformation layer under an explicit separability assumption, not a causal rain-only propagation law and not an elevation-conditioned model.
- No effect-layer evidence table, fitted distribution, canonical-table transformation, request, or generated weather table was created in this audit. The recommended design is pending user approval. No raw IQ was opened, and no MATLAB, SAGE, or batch task was executed.

```text
RAIN_NINE_TASK_EXECUTION=COMPLETE
RAIN_NINE_TASK_INDEPENDENT_QA=PASS
RAIN_STAGE3_RELIABLE_CENTERS=55
RAIN_STAGE3_RELIABLE_PATH_ROWS=90
RAIN_STAGE3_OVERLAP_EPISODES=26
RAIN_EFFECT_LAYER_INPUT_SEMANTICS=STAGE3_RELIABLE_EVIDENCE
RAIN_EFFECT_LAYER_STAGE4_USED_AS_FIT_GATE=NO
GLOBAL_STAGE4_CONFIRMATION_CRITERION_CHANGED=NO
RAIN_EFFECT_LAYER_STATUS=PLANNED_NOT_STARTED
RAW_IQ_READ_IN_THIS_AUDIT=NO
MATLAB_EXECUTED_IN_THIS_AUDIT=NO
SAGE_EXECUTED_IN_THIS_AUDIT=NO
NEXT_DECISION_REQUIRED=USER_APPROVE_STAGE3_RAIN_EFFECT_LAYER_DESIGN
```

## 91. Rain Stage3 effect layer implementation and eight-table generation (Implemented / QA Validated, 2026-08-30)

- The approved Stage3 Rain route has been implemented as independent Python tooling: `scripts/analysis/channel_modeling/rain_stage3_effect_layer_v1.py`, `run_rain_stage3_effect_layer_v1.py`, and `audit_rain_stage3_effect_layer_v1.py`. The v2.2 canonical generator/core and all nine Rain SAGE artifacts remain unchanged.
- The final new-only namespace is `dataset_generation_logs/channel_modeling/rain_effect_layer_stage3_v1_20260830_r5`. It contains 90 Stage3 reliable path-evidence rows, 26 support episodes, a separate Clear/MidRain/HeavyRain/RainPooled empirical model, and eight 5-minute Rain-transformed canonical tables. Each table has 3,600,000 rows and preserves the seven-column canonical schema.
- `RainPooled` is the pooled MidRain+HeavyRain transformation used for the requested eight tables: Urban, Special Reflective, Mountain/Valley, and Highway/Open, each in GOOD and POOR modes. The same layer is applied to Low/Mid/High bands under the documented no-elevation-conditioning separability assumption.
- The transformation keeps path 0 unchanged, applies deterministic per-`SatelliteID × NLOSPathID × 40 ms block` effects to NLOS slots 1–3, preserves positive NLOS amplitude, and propagates phase from Doppler. Stage3 evidence is used for fitting; Stage4 and gold labels are not used for selection or fitting.
- Independent QA passed: source/output hashes, 8/8 table presence, 3,600,000 rows per table, row identity/order, main-path preservation, finite values, positive NLOS amplitude, 40-ms block constancy, phase recurrence, and namespace isolation. Final collection manifest SHA-256 is `a7dd28086b5b76821b6202f8f9efe6c7386e7f6db4680ae4353682982825c621`; QA SHA-256 is `8b890163e9d0b501fe6f24c44217602340c7803cd413a03b40bb1e7604ab3efd`.
- Earlier r1/r2/r3 namespaces remain preserved diagnostic artifacts; no file was deleted, moved, overwritten, or resumed. The final report is `docs/RAIN_STAGE3_EFFECT_LAYER_REPORT.md`.

```text
RAIN_EFFECT_LAYER_IMPLEMENTATION=COMPLETED
RAIN_EFFECT_LAYER_FINAL_NAMESPACE=rain_effect_layer_stage3_v1_20260830_r5
RAIN_EFFECT_LAYER_EVIDENCE_ROWS=90
RAIN_EFFECT_LAYER_EPISODES=26
RAIN_EFFECT_LAYER_TABLES=8
RAIN_EFFECT_LAYER_ROWS_PER_TABLE=3600000
RAIN_EFFECT_LAYER_QA=PASS
RAIN_EFFECT_LAYER_STAGE4_USED_FOR_FIT=NO
RAIN_EFFECT_LAYER_GOLD_LABELS_USED_FOR_SELECTION=NO
RAIN_EFFECT_LAYER_RAW_IQ_READ=NO
RAIN_EFFECT_LAYER_MATLAB_EXECUTED=NO
RAIN_EFFECT_LAYER_SAGE_EXECUTED=NO
NEXT_DECISION_REQUIRED=INDEPENDENT_REVIEW_OR_DARKROOM_INTEGRATION_APPROVAL
```
