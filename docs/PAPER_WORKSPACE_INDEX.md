# Paper Workspace Index

## Paper Status

### Current authoritative Phase-1 status (2026-08-31)

| 项目 | 当前状态 |
|---|---|
| Phase-1 Stage3 traditional statistical model | **Completed / PASS_WITH_LIMITATIONS** |
| Phase-1 scientific closure | **Completed / PASS_WITH_LIMITATIONS** |
| Long-term manuscript synchronization | **Pending / In progress** |

Canonical model/report：`dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3/`、`docs/ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_R3_REPORT.md`。Canonical closure/report：`dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/`、`docs/PHASE1_TRADITIONAL_CHANNEL_MODELING_SCIENTIFIC_CLOSURE.md`。

Phase-1 Stage3 academic population：783 observations、445 centers、366 algorithm-level tracks、716 elevation-ready observations、50 runs、12 scenes、18 PRNs。主统计单位为 `WEIGHTED_OBSERVATION`，权重为 `1 / algorithm_track_size`；层次为 `Global → Environment → Environment×Elevation`。全局边际族为 delay `Lognormal`、signed relative Doppler `Normal`、relative power `Normal`；Gaussian Copula 只在 global / environment / support-gated cell 层使用。Stage4 仅作为 high-confidence selection-sensitivity subset，结果为 `MATERIAL_DIFFERENCE`，不是 ground truth。

11/12 个 environment×elevation 组合有 Stage3 直接观测；Highway/Open–LOW 无直接支持，不做假填充。环境主效应与仰角主效应均为 `INCONCLUSIVE`，交互作用为 `PARTIAL`；Ricean K 不可识别，persistence 仅为算法观测持续性。**model results completed; manuscript Results synchronization pending**。本状态不表示完整 12-cell 实测覆盖、普适规律或完整物理信道生成器已完成。

当前论文主题：

**SAGE-based path extraction and statistical GNSS multipath channel modeling**

当前主线：

```text
raw GNSS IQ
  -> GNSS-SDR tracking/navigation support
  -> SAGE path extraction
  -> path-level delay/Doppler/power/phase
  -> candidate channel parameters: PDP, RMS delay spread, Doppler spread, Ricean K-factor,
     number of paths, mean excess delay, path power statistics, path lifetime/temporal stability
  -> environment-conditioned statistical GNSS multipath channel model
```

当前论文生产状态：

- 10.23 MHz full SAGE production：冻结批次已完成并通过独立批后 QA；formal accepted production 为 26/67，详见 Engineering Handoff。
- 13 个 10.23 MHz measurement scenes：scene metadata layer 已建立。
- 首个正式 production task `F1023_V70_D0117_P4/G11/ch2`：QA PASS。
- `F1023_V70_D0120_P1/G18/ch2`：正式输出已完成并通过独立 post-run QA；属于第二个 QA-passed production result。
- `F1023_V70_D0120_P5/G16/ch1`：Stage0–Stage4 科学 artifact 已完成并通过独立科学 QA；因历史 execution-policy deviation 不作为 Batch A release evidence。
- `F1023_V70_D0117_P4/G12/ch4`：正常 Windows 用户执行已完成并通过独立 QA，executor exit code=0、目标目录21个输出文件、3 confirmed events/3 paths；可作为 Available evidence，不自动写入VTC核心Results。
- coverage-complete path database：Planned / Not started；Phase-1 Stage3 academic population 已审计并用于 canonical model。
- standalone coverage-complete channel parameter database：Planned / Not started；Phase-1 closure 的派生统计输出已完成。
- Phase-1 statistical model：Completed / PASS_WITH_LIMITATIONS；扩展模型/完整物理生成器不在当前完成声明内。
- raw-coarse v3：negative result，Posterior Failed / Frozen，不是 production selector。

## Core Status Documents

| 文件 | 用途 | 状态 |
|---|---|---|
| `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` | 论文科学问题、贡献、可写结果、限制和论文路线的唯一状态来源 | Current / authoritative |
| `docs/GNSS_SAGE_VTC_WRITING_HANDOFF_CURRENT.md` | VTC2027-Spring 写作策略、scientific freeze、图表策略、Commander/Codex 接续规则 | Current / Commander-oriented VTC writing handoff |
| `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` | 工程代码、输入输出、执行、QA、hash 和 manifest 状态；供论文追溯工程事实 | Current engineering cross-reference |
| `docs/GNSS_SAGE_CHATGPT_CONVERSATION_HANDOFF_CURRENT.md` | 当前对话决策、工作节奏、运行中任务和接续提示；不是工程或论文状态来源 | Current conversation cross-reference |
| `docs/PAPER_WORKSPACE_INDEX.md` | 本论文工作区导航 | Implemented |
| `docs/GNSS_SAGE_PROJECT_HANDOFF_CURRENT.md` | 历史综合项目交接；不是当前论文唯一状态来源 | Historical reference |
| `docs/GNSS_SAGE_CODEX_PROJECT_HANDOFF_20260812.md` | 历史 Codex 工程交接 | Historical reference |

状态含义：`Completed` 表示已执行并验证；`Implemented` 表示代码/文档已实现但不等同于实验完成；`Validated` 表示已通过相应测试或 QA；`Planned` 表示已规划；`Not started` 表示尚未开始。

## Manuscript Structure

论文工作区目录：`docs/paper_draft/`

| 文件 | 作用 | 状态 |
|---|---|---|
| `docs/paper_draft/manuscript_outline.md` | 论文主线、章节结构、path-to-channel 建模路线和数据库路线 | Implemented / current outline |
| `docs/paper_draft/sections/01_Introduction.md` | dynamic GNSS multipath、统计信道建模动机、receiver-level indicator 限制 | Implemented outline / Phase-1 result context pending |
| `docs/paper_draft/sections/02_Related_Work.md` | GNSS multipath characterization、高分辨率参数估计、统计无线信道建模文献框架 | Implemented outline / literature filling pending |
| `docs/paper_draft/sections/03_Methodology.md` | end-to-end pipeline、NAV-aided SAGE Stage0–Stage4、path-level parameters、channel parameter derivation、environment-conditioned modeling | Implemented / draft updated; Phase-1 model-result synchronization pending |
| `docs/paper_draft/sections/04_Experimental_Setup.md` | TEST-TREE RF-Catcher V2、GNSS dome antenna、GPS L1 C/A、IQ格式、GNSS-SDR configuration、10.23 MHz dataset、scene metadata与执行环境 | Implemented / Draft completed; time synchronization details pending |
| `docs/paper_draft/sections/05_Pipeline_Validation.md` | reference 多 PRN、Wave-A 跨任务复现、Wave-2A 长记录、A1/A2/G16 production QA 和 acceleration limitation | Implemented / G16 scientific case recorded; additional production QA pending |
| `docs/paper_draft/sections/06_Results_PLACEHOLDER.md` | dataset、event/path、delay/Doppler/power、channel model 结果占位 | Placeholder / model results completed; manuscript Results synchronization pending |
| `docs/paper_draft/sections/07_Conclusion.md` | 最终 path extraction 和 statistical channel model 结论占位 | Implemented outline / Phase-1 conclusion synchronization pending |
| `docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md` | scene、path、channel parameter、statistical model 四层 schema 设计 | Designed / actual database Not started |

## VTC2027-Spring Submission Workspace

`docs/vtc2027_spring/` 是 VTC2027-Spring Regular Paper 的专用论文资产工作区，不是新的状态源。论文科学状态仍以 `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` 为准，工程执行状态仍以 `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` 为准。

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `docs/vtc2027_spring/README.md` | 投稿范围、目录职责和证据纪律 | Implemented |
| `docs/vtc2027_spring/VTC_PLAN.md` | VTC目标、working title、贡献、时间线和submission gates | Implemented / Planned execution |
| `docs/vtc2027_spring/EVIDENCE_MATRIX.md` | 论文 claim-to-artifact 证据矩阵和缺失项 | Implemented / evidence completion pending |
| `docs/vtc2027_spring/VTC_PRODUCTION_PRIORITY_QUEUE.md` | VTC evidence-priority production候选评分、Tier 1/2/3、first wave和最低停止条件 | Planned / read-only planning artifact; no execution authorized |
| `docs/vtc2027_spring/MANUSCRIPT_OUTLINE.md` | 五页论文结构和篇幅预算 | Implemented / draft planning |
| `docs/vtc2027_spring/FIGURE_TABLE_PLAN.md` | 图表候选及其原始证据路径 | Implemented / Figure 1 source draft available; final figures pending |
| `docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md` | 英文论文骨架和受控占位符 | Implemented skeleton / results pending |
| `docs/vtc2027_spring/manuscript/latex/main.tex` | 英文 IEEE conference-mode LaTeX 正式投稿正文 source of truth | Implemented / local build and Figure 1--4 integration validated |
| `docs/vtc2027_spring/manuscript/latex/references.bib` | 英文稿唯一参考文献源 | Implemented / verified entries |
| `docs/vtc2027_spring/submission/SUBMISSION_REQUIREMENTS.md` | 2026-08-14 VTC/IEEE 投稿要求基线（保留历史记录） | Historical baseline / superseded by current audit |
| `docs/vtc2027_spring/submission/PAGE_BUDGET.md` | 五页篇幅预算和压缩优先级 | Implemented planning asset |
| `docs/vtc2027_spring/submission/VTC2027_SUBMISSION_REQUIREMENTS_AUDIT.md` | 当前官方 VTC2027 投稿要求、作者可见性、轨道、PDF 和最终门禁审计 | Implemented / Validated; author and portal blockers remain |
| `docs/vtc2027_spring/submission/VTC2027_Spring_submission_candidate.pdf` | 基于当前 LaTeX 源的本地 4 页 submission-candidate PDF；未填真实作者信息，未提交 | Implemented / Visual QA validated; not submission-ready |
| `docs/vtc2027_spring/manuscript/VTC_SUBMISSION_CANDIDATE_REVIEW.md` | 当前 VTC 投稿候选稿的模拟审稿式综合审查、评分、风险表和 Top-10 修改优先级 | Implemented / Review artifact; no manuscript source change |
| `docs/vtc2027_spring/manuscript/VTC2027_Spring_CN_REVIEW.md` | 当前英文投稿候选稿的中文用户审阅文本；非投稿源 | Implemented / synced review copy; English `main.tex` remains authoritative |
| `docs/vtc2027_spring/manuscript/latex_cn_review/` | 中文 XeLaTeX 审阅版及其 PDF；直接引用正式图形和参考文献，不是投稿源 | Implemented / review-only PDF generated |
| `docs/vtc2027_spring/figures/` | 正式论文 Figure 1--4 的唯一 PDF/PNG 输出及其生成 manifest；Figure 4 为 Tier A+B 四环境路径特征描述图 | Implemented / assets and hashes validated |
| `docs/vtc2027_spring/manuscript/latex/figures/` | 保留的 Figure 1 可编辑 SVG/TikZ 源和 README；不被正文引用 | Source archive / not manuscript output |
| `docs/vtc2027_spring/manuscript/latex/template_reference/` | 官方 IEEE 模板原件保留位置 | Pending manual retrieval |
| `docs/vtc2027_spring/tables/`、`evidence/`、`submission/` | 表格、证据抽取和最终提交包工作目录 | Planned / final package not started |

VTC工作区当前的实际状态：A1 G11、A2 G18、G12 controlled acceptance和参考/验证案例可作为已有证据；正式A3 G16可作为科学Pipeline Validation案例但不是Batch A放行依据；G12已通过独立QA，但是否进入VTC核心Results仍需证据矩阵审查。VTC不声称完整event database、完整统计信道模型或所有scene已完成。

## Dataset and Metadata

### Scene-level sources

| 文件 | 用途 | 状态 |
|---|---|---|
| `dataset/dataset_inventory.csv` | 全部 scene、采样率、raw/GNSS-SDR/navigation/trajectory/geometry 和 PRN/channel inventory | Completed / Validated source inventory |
| `dataset_generation_logs/production_planning_10mhz_20260812/production_inventory_10MHz.csv` | 10.23 MHz scene-PRN production audit inventory | Completed / Validated planning artifact |
| `dataset_generation_logs/production_planning_10mhz_20260812/scene_environment_annotation_list.csv` | 13 个 production scene 的人工环境确认输入清单 | Completed / Validated |
| `dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv` | 10.23 MHz measurement environment metadata layer | Completed / Validated, 13/13 scene coverage |
| `docs/scene_metadata_10MHz_check_report.md` | scene metadata、raw path、sample-rate 和 inventory 覆盖检查 | Validated |
| `docs/SCENE_ENVIRONMENT_ANNOTATION_CHECKLIST.md` | 人工环境类型、道路类型和速度确认清单 | Completed checklist |
| `dataset_generation_logs/production_planning_10mhz_20260812/audit_manifest.json` | production planning 审计 provenance | Audit artifact |
| `dataset_generation_logs/production_planning_10mhz_20260812/status_summary.json` | production planning 状态摘要 | Planning status artifact |

### Production planning

| 文件 | 用途 | 状态 |
|---|---|---|
| `dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json` | 允许进入 10.23 MHz production 的 immutable task manifest；排除已完成和 blocked 任务 | Implemented / Planned execution source |
| `docs/10MHz_FULL_SAGE_PRODUCTION_INVENTORY_AND_PLAN.md` | 10.23 MHz production inventory、任务分类和生产准备 | Planning document |
| `docs/10MHz_FULL_SAGE_PRODUCTION_EXECUTION_PLAN_v1.md` | Batch A/B/C、preflight、checkpoint、failure recovery 和数据库准备 | Planned / Not an execution result |
| `docs/WAVE2_10MHz_CONTROLLED_EXPANSION_PLAN.md` | 历史受控扩展候选与 Wave 规划 | Historical planning reference |

## Experimental Evidence

### VTC evidence consolidation

| 文件 | 用途 | 状态 |
|---|---|---|
| `docs/vtc2027_spring/evidence/vtc_confirmed_path_database.csv` | T1-1/T1-2/T1-3 confirmed Stage4 path 的论文追溯索引，不复制 SAGE artifact | Implemented / QA audited; 5 rows |
| `docs/vtc2027_spring/evidence/vtc_evidence_summary.csv` | confirmed case、valid zero-event case 与 Stage4 non-confirmation evidence 汇总 | Implemented / QA audited |
| `docs/vtc2027_spring/evidence/vtc_geometry_alignment_qa.md` | event-level TOW/UTC/NMEA-GSV geometry alignment QA 与缺失项 | Completed audit; PARTIAL |
| `docs/vtc2027_spring/evidence/VTC_ENVIRONMENT_EVIDENCE_CENSUS.csv` | 所有已发现完整 Stage0--Stage4 scene--PRN--channel 任务的环境、证据层级、窗口和确认事件/路径 census | Completed / Audited; 18 tasks |
| `docs/vtc2027_spring/evidence/VTC_ENVIRONMENT_PATH_CANDIDATES.csv` | 去重后的 Stage4 confirmed-path 候选及 delay、signed Doppler、power、coherence provenance | Completed / Audited; 29 rows |
| `docs/vtc2027_spring/evidence/SAGE_REPRODUCIBILITY_PARAMETER_AUDIT.md` | 从当前 MATLAB 实现提取并分层的论文复现参数与 SAGE 更新机制审计 | Implemented / Audited |
| `docs/vtc2027_spring/evidence/VTC_METHOD_ACADEMICIZATION_ENVIRONMENT_EVIDENCE_AUDIT.md` | 本轮 Method 学术化、证据层级、环境比较充分性和后续最小计划的综合审计 | Implemented / Audit report |

这些文件是 VTC 论文证据索引，不是长期 event/path database、channel-parameter database 或 statistical model database。geometry candidate 值仍未达到 geometry-complete event-level evidence 门槛。

### Reference scene

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `scenes/F1023_V70_D0117_P2/sage_results/reference_scene_final_validation_report.md` | reference scene 七 PRN Stage0–Stage4 封存基线 | Completed / Validated |
| `scenes/F1023_V70_D0117_P2/sage_results/reference_prn_analysis_report.md` | 七 PRN 传播特征与分类分析 | Completed analysis |
| `scenes/F1023_V70_D0117_P2/sage_results/prn_validation_summary.csv` | reference PRN 验证汇总 | Completed validation artifact |
| `scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/` | reference G11/G12/G25/G28/G29/G32 结果目录 | Existing validated results |
| `scenes/F1023_V70_D0117_P2/sage_results/G06_nav_sage_v1/` | G06 历史 legacy baseline | Immutable protected baseline |

### Wave-A and Wave-2A

| 文件 | 用途 | 状态 |
|---|---|---|
| `docs/WAVEA_10MHz_VALIDATION_REPORT.md` | G16、G25、G12 三任务 10.23 MHz 执行链闭环总结 | Completed / Validated |
| `docs/PILOT1_G16_QA_REPORT.md` | G16 Windows Pilot QA | Completed / Validated |
| `docs/WAVEA_G25_QA_REPORT.md` | G25 LOS-like control QA | Completed / Validated |
| `docs/WAVEA_G12_QA_REPORT.md` | G12 Wave-A QA | Completed / Validated |
| `docs/WAVE2A_G11_QA_REPORT.md` | 长场景 G11 full-scan runtime、zero-event 和输出 QA | Completed / Validated |

### First formal production result

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `docs/10MHz_FULL_SAGE_PRODUCTION_A1_G11_QA_REPORT.md` | 首个正式 production task `F1023_V70_D0117_P4/G11/ch2` 的独立 post-run QA | PASS / Completed |
| `scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G11/` | 首个正式 production Stage0–Stage4 输出 | Completed / QA PASS |
| `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T013710Z/batch_execution_log.csv` | 首个 production 执行日志 | Completed execution evidence |
| `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T013710Z/` | 首个 production status、task log、receipt 和输出记录 | Completed execution evidence |

### G18 production execution and QA

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a2_d0120p1_g18_20260813/execution_request.json` | G18 单任务 immutable execution request | Validated request / executed |
| `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a2_d0120p1_g18_20260813/request_readiness_report.md` | G18 request/preflight 和 normal-user wrapper 说明 | PASS for wrapper / executed |
| `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a2_d0120p1_g18_20260813/preflight_receipt.json` | G18 执行前输入和 namespace 检查 | Preflight PASS |
| `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T034529Z/status_history.jsonl` | G18 从 ready 到 completed 的状态记录 | Completed evidence |
| `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T034529Z/task_logs/F1023_V70_D0120_P1__G18__ch2__nav_sage_v2.log` | G18 task log | Completed |
| `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T034529Z/batch_execution_log.csv` | G18 单任务 execution log | Completed execution evidence |
| `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_production_10mhz_a2_d0120p1_g18_20260813_20260813T034259453Z/` | G18 normal-user environment/execution receipts | MATLAB smoke + executor PASS |
| `scenes/F1023_V70_D0120_P1/sage_results/nav_sage_v2/G18/` | G18 Stage0–Stage4 production output | Completed / QA PASS |
| `docs/10MHz_FULL_SAGE_PRODUCTION_A2_G18_QA_REPORT.md` | G18 独立 post-run QA（含 zero-event output validity） | PASS / Completed |

G18 已通过独立 post-run QA，可作为第二个 production execution/QA 事实引用；其 zero-event 结果不应被解释为物理 LOS 结论。该更新不表示 event database、全部 scene 或统计模型已经完成。

### G12 controlled acceptance execution and QA

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_contract_acceptance_d0117p4_g12_20260814/execution_request.json` | G12 修复后 contract acceptance immutable request；SHA=`228c67b07fddc6526d320b45bf3495aa56854a478ff39c2fdc0ee6283b74edee` | Validated request / executed |
| `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_production_contract_acceptance_d0117p4_g12_20260814_20260814T024639097Z/` | G12 normal-user smoke、环境和executor receipts | MATLAB smoke + executor PASS |
| `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T024904Z/batch_execution_log.csv` | G12 实际execution log | Completed execution evidence |
| `scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G12/` | G12 Stage0–Stage4 production output | Completed / QA PASS |
| `docs/10MHz_FULL_SAGE_PRODUCTION_CONTRACT_ACCEPTANCE_G12_QA_REPORT.md` | G12 独立 contract/new-only/artifact/scientific QA | PASS / Available evidence |

G12 的当前 Stage4 criterion 结果为 3 confirmed events 和 3 confirmed paths；它已登记为论文可用 evidence，但尚未自动提升为VTC核心 Results 主张。该更新不表示 event database、全部 scene 或统计模型已经完成。

## Database Design

| 文件 | 用途 | 状态 |
|---|---|---|
| `docs/MULTIPATH_EVENT_DATABASE_DESIGN.md` | 详细 run/window/candidate/confirmed-event/path 规范化事件库设计、ingestion 和 QA 规则 | Designed / actual database Not started |
| `docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md` | 论文面向的四层 schema：scene、SAGE path、channel parameter、statistical model | Designed / Phase-1 model outputs available; expanded tables pending |

关系主线：

```text
scene
  -> path
  -> channel parameter
  -> statistical model
```

已完成的是 scene metadata layer 以及 Phase-1 canonical statistical model 输出；coverage-complete path database 和独立 channel-parameter database 仍未完成。

## Channel Parameter Candidate Pool

The current paper schema retains a broader candidate pool, but the Phase-1 canonical
selection is now finalized for the bounded Stage3 population: excess delay is
Lognormal, signed relative Doppler is Normal, and relative power is Normal. Further
parameters and a coverage-complete database remain separately gated.

- Phase-1 fitted path parameters: excess delay, signed relative Doppler, and relative power.
- Derived/extended candidates for later evaluation: PDP, number of paths, mean excess delay, RMS delay spread, and Doppler spread.
- Ricean K-factor: retained as a scientific boundary; not identifiable from the current evidence.
- Optional candidates for later evaluation: path power statistics, path lifetime, path temporal stability.
- Selection criteria: statistical stability, physical interpretability, variable relationships and model requirements.
- Source design: `docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md`.

## Batch Execution and Reproducibility Assets

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `docs/BATCH_SAGE_DRY_RUN_DESIGN.md` | batch dry-run 规划 | Designed |
| `docs/BATCH_SAGE_EXECUTION_READINESS_REVIEW.md` | ready/blocked/multi-channel 任务审核 | Completed review |
| `docs/BATCH_SAGE_WINDOWS_EXECUTION_DESIGN.md` | 正常 Windows 用户执行 MATLAB 的安全架构 | Designed |
| `docs/BATCH_SAGE_WINDOWS_EXECUTION_IMPLEMENTATION.md` | Windows wrapper 实现说明 | Implemented / Validated by prior pilot flow |
| `scripts/sage_pipeline/run_batch_sage.py` | 任务解析、preflight、状态和 MATLAB pipeline 调用门禁 | Implemented / production execution component |
| `scripts/sage_pipeline/Invoke-BatchSageWindows.ps1` | identity、smoke、hash、lock、namespace 和人工确认门禁 | Implemented / normal-user execution component |
| `dataset_generation_logs/batch_sage_execution_requests/` | immutable request、SHA、preflight 和 selected snapshot | Existing request artifacts |
| `dataset_generation_logs/batch_sage_execution/` | execution receipts、status、task logs 和 batch outputs | Existing execution artifacts |

这些文件支持论文中的 reproducibility/execution section，但不是科学结果本身。

## Historical Acceleration and Negative Results

raw-coarse/sampling 资产必须作为方法探索、负结果或 limitation 归档，不能写成 production selector 或 coverage-complete 数据结果。

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `docs/STAGE1_STAGE2_BATCH_SAMPLING_DESIGN.md` | full-scan 与 sampled strategy 设计 | Design / historical |
| `docs/BATCH_SAMPLED_V1_OFFLINE_COVERAGE_REPORT.md` | v1 offline coverage replay | Failed / archived |
| `docs/BATCH_SAMPLED_V1_1_OFFLINE_COVERAGE_REPORT.md` | v1.1 adaptive replay | Failed / archived |
| `docs/BATCH_SAMPLED_V1_2_SEED_DISCOVERY_DESIGN.md` | v1.2 oracle-free seed discovery 设计 | Design / not production |
| `docs/BATCH_SAMPLED_V1_2_A0_OFFLINE_COVERAGE_REPORT.md` | A0 planner coverage | Failed / archived |
| `docs/BATCH_SAMPLED_V1_2_RAW_COARSE_PROTOTYPE_REPORT.md` | B1/B2/C1 prototype 初版 | Failed/archived |
| `docs/BATCH_SAMPLED_V1_2_RAW_COARSE_PROTOTYPE_V2_REPORT.md` | NumPy kernel/performance prototype | Kernel validated; selector/Phase-A gates not production |
| `docs/RAW_COARSE_NUMPY_KERNEL_ALIGNMENT_REPORT.md` | legacy/reference 数值一致性对齐 | Validated kernel artifact |
| `docs/RAW_COARSE_V3_G16_EVIDENCE_FEATURE_QA_REPORT.md` | v3 evidence/feature QA | QA validated |
| `docs/RAW_COARSE_V3_COMPONENT_OWNERSHIP_FIX_REPORT.md` | v3 ownership schema 修复 | Schema QA validated |
| `docs/RAW_COARSE_V3_G16_POSTERIOR_GOLD_COVERAGE_REPORT_R1B.md` | v3 posterior replay | Failed / Frozen negative result |
| `dataset_generation_logs/sampling_validation/` | v1/v1.1/A0/v2/v3 manifests、replay、prototype 和 QA artifacts | Historical validation namespace; not production data |

论文可讨论 v3 的计算加速探索、posterior coverage failure 和 limitation，但不得把未进入 production 的 sampling/coarse 结果当作最终 event/path 数据。

## Preprocessing and Measurement Provenance

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `dataset_generation_logs/navigation_prepare_20260806_134959_505548.log` | RINEX NAV/OBS 整理过程日志 | Completed preprocessing log |
| `dataset_generation_logs/trajectory_prepare_20260806_135239_205975.log` | trajectory NMEA 整理过程日志 | Completed preprocessing log |
| `dataset_generation_logs/batch_satellite_geometry_20260806_141452_394272.log` | satellite geometry 生成过程日志 | Completed preprocessing log |
| `scenes/<scene_id>/metadata.json` | scene、raw provenance、GNSS-SDR/navigation/trajectory/geometry 状态 | Existing source metadata |
| `scenes/<scene_id>/navigation/` | RINEX NAV/OBS | Existing input provenance |
| `scenes/<scene_id>/trajectory/` | NMEA trajectory | Existing input provenance |
| `scenes/<scene_id>/satellite/` | geometry timeseries/summary | Existing derived geometry; time-alignment QA remains relevant |

本索引只记录文本和文件系统中的论文资产，不打开 raw `.bin` 内容。

## Future Research Outputs

待生成或待完成：

- coverage-complete path database；
- standalone coverage-complete channel parameter database；
- expanded statistical model database beyond the canonical Phase-1 r3/r2 outputs；
- event/path ingest validator and QA exports；
- PDP、delay spread、Doppler spread、K-factor 等统计图；
- manuscript Results 中的 environment/elevation 分层图表同步；
- dataset overview、Stage funnel、runtime/scalability 和 validation tables；
- G18 及后续 Batch production 的独立 QA 结果。

这些项目均不得在完成相应实验和 QA 前标记为 Completed。

## Current Completed Items

- 论文 handoff 和 paper draft outline 已建立。
- 13 个 10.23 MHz scene 的 scene metadata layer 已建立并通过覆盖检查。
- reference scene 七 PRN 验证已完成并封存。
- Wave-A G16/G25/G12 验证已完成并通过 QA。
- Wave-2A G11 full-scan 已完成并通过 QA，提供长场景规模观察。
- 首个 10.23 MHz formal production task G11 已完成并通过独立 QA。
- 第二个 10.23 MHz formal production task G18 已完成并通过独立 QA。
- 修复后 G12 controlled acceptance 已完成真实执行并通过独立 QA，提供 3 confirmed events 和 3 confirmed paths 的 Available evidence。
- 正式 A3 G16 已完成 Stage0–Stage4 科学 artifact 和独立科学 QA；因历史 execution-policy deviation 不作为 Batch A release evidence。
- 论文 database schema 和 event database design 已完成设计；coverage-complete fact tables 仍未建立。
- Phase-1 Stage3 canonical traditional statistical model r3 与 scientific closure r2 已完成并通过独立 QA（PASS_WITH_LIMITATIONS）。

## Future Missing Items

- 其余 10.23 MHz production tasks 的 execution receipts 和独立 QA。
- VTC核心Results的证据筛选和G12是否纳入正文（G12执行与独立QA已完成，但尚未自动准入）。
- coverage-complete path/event database。
- coverage-complete channel parameter derivation/database and broader QA。
- manuscript Results synchronization: model results completed; manuscript Results synchronization pending。
- final paper figures, tables and cross-scene conclusions based on the bounded model。

## Safety and Status Rules

- `G06_nav_sage_v1` 和 reference outputs 不得覆盖。
- Existing output 默认 `new_only=true`；不得静默 resume、删除或覆盖 partial artifact。
- 20.46 MHz 当前不属于 production scope。
- raw-coarse/sampling/v3 输出不得写入 `scenes/**/sage_results`。

## Documentation Update Policy

论文与工程文档按职责分层维护，不创建新的重复状态源：

| 文档/资产 | 只在何时更新 | 职责 |
|---|---|---|
| `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` | 工程流程、工具、能力、production/QA/Batch、hash/manifest/环境或工程路线变化 | 工程状态唯一来源 |
| `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` | 科学路线、贡献、数据库设计、章节状态或新的论文可用事实变化 | 论文状态唯一来源 |
| `docs/PAPER_WORKSPACE_INDEX.md` | 论文资产结构新增、删除或职责变化 | 论文资产导航 |
| `dataset_generation_logs/production_monitoring_10MHz/` | 每个正式production任务独立QA后更新只读汇总 | 工程生产监控，不是论文数据库 |

标准同步顺序：`Execution -> QA -> Production Summary -> Engineering Handoff -> 判断论文事实 -> 必要时Paper Handoff -> 判断论文资产 -> 必要时Workspace Index`。

禁止因为普通实验结果无条件修改所有handoff；禁止创建`ENGINEERING_STATUS_NEW.md`、`PAPER_STATUS_NEW.md`、`PAPER_PLAN_V2.md`、`FINAL_STATUS.md`等重复状态文件；禁止把工程事实写成未经支持的论文结论。状态必须保持`Completed / Validated / Implemented / Planned / Not started / Failed-Frozen`的含义边界。
- 未通过独立 QA 的任务不能写入论文 final results 或累计统计。
- planned/implemented/validated 不能被改写成 completed/result。

## Handoff Impact

本索引新增了论文资产导航，论文 handoff 已同步记录；工程 handoff 不变。

### VTC manuscript evidence package (2026-08-15)

`docs/vtc2027_spring/evidence/` 已新增正式论文证据包结构：

| 目录/文件 | 用途 | 状态 |
|---|---|---|
| `docs/vtc2027_spring/evidence/README.md` | evidence package 范围、来源、提取规则和科学边界 | Implemented / Prepared |
| `docs/vtc2027_spring/evidence/manuscript_tables/` | 论文表格 CSV 提取源 | Implemented / Prepared |
| `docs/vtc2027_spring/evidence/manuscript_figures/` | 论文图表 CSV 提取源 | Implemented / Prepared |
| `docs/vtc2027_spring/evidence/extracted_data/` | 额外论文提取数据保留区；当前无额外数据 | Implemented / Reserved |

当前包只引用已 QA-PASS 的 T1-1/T1-2/T1-3 和 G18 zero-event evidence，不复制 SAGE artifact，不生成统计信道模型，也不改变 VTC production frozen 状态。

### VTC Chinese review and Special Reflective evidence assets (2026-08-17)

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.pdf` | 当前唯一 canonical Chinese review PDF；非投稿 source | Implemented / visually Validated |
| `docs/vtc2027_spring/evidence/VTC_CHINESE_PDF_CANONICALIZATION_SPECIAL_REFLECTIVE_SUPPLEMENT_REPORT.md` | Canonical PDF verification 和 Special Reflective 补充准备审计 | Implemented / Prepared; no new experiment |
| `dataset_generation_logs/batch_sage_execution_requests/vtc_special_reflective_supplement_p2_g15_20260817/` | 单一 Special Reflective independent-scene immutable request、snapshot 和 preflight | Retained / Executed; request provenance for the QA-passed G15 result |

| `docs/vtc2027_spring/evidence/VTC_SPECIAL_REFLECTIVE_SUPPLEMENT_G15_QA_REPORT.md` | Independent QA and paper inclusion decision for the second Special Reflective scene | Validated / Available |

该 supplement request 本身不是论文结果；其后已由正常用户执行并通过独立 QA。当前可用的论文证据和纳入决策以 `VTC_SPECIAL_REFLECTIVE_SUPPLEMENT_G15_QA_REPORT.md` 及已更新的 evidence CSV 为准。当前 Figure 4 未修改。
