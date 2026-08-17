# GNSS SAGE VTC2027-Spring Writing Commander Handoff

**Document role:** VTC论文撰写与 Commander 决策的唯一 current handoff  
**Last consolidated:** 2026-08-17 (Asia/Shanghai)  
**Conference:** IEEE VTC2027-Spring Regular Paper  
**Current phase:** `USER_AUTHOR_REVIEW`  
**Scientific content:** `SCIENTIFIC_CONTENT_FROZEN=YES`  
**SAGE production:** `SAGE_PRODUCTION_STOPPED=YES`  
**New experiment gate:** `NEW_EXPERIMENT_REQUIRED=NO`

## 1. Purpose and How to Use This Handoff

本文件不是普通项目总结、实验日志、QA报告或论文内容副本。它负责保存 VTC2027-Spring 论文的科学定位、写作边界、Commander 决策、图表策略、作者审阅流程和无上下文接续规则。

未来任何没有当前聊天上下文的 AI，必须先读取以下三个文件：

1. `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
2. `docs/GNSS_SAGE_VTC_WRITING_HANDOFF_CURRENT.md`
3. `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

读完后，AI 应能理解整个 GNSS/SAGE 项目、VTC 论文的有限科学故事、已冻结的证据边界、当前图表和稿件状态，以及 Codex 下一步只能做什么。

本文件不替代工程交接或论文交接，也不复制完整代码、CSV、MATLAB 输出或全部历史 review。具体工程事实引用工程交接，论文资产和论文可用事实引用 Paper Handoff，写作策略和 Commander 决策集中在本文件。

## 2. Three-Handoff Bootstrap Protocol

### 2.1 Project / Engineering Handoff

权威文件：`docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`。

它负责：

- 数据集、scene、PRN/channel、GNSS-SDR 和目录结构；
- SAGE pipeline、Stage0--Stage4、输入输出和算法限制；
- production、wrapper、manifest、hash、执行身份和 QA；
- raw、20.46 MHz、reference、legacy 和不可覆盖规则；
- 长期 event/path database 与统计信道建模项目状态。

项目中存在的 `docs/GNSS_SAGE_PROJECT_HANDOFF_CURRENT.md` 是历史综合交接，不能替代当前 Engineering Handoff。

### 2.2 VTC Writing Handoff

本文件 `docs/GNSS_SAGE_VTC_WRITING_HANDOFF_CURRENT.md` 负责：

- VTC 论文科学定位和故事线；
- submission scope、scientific freeze 和不应重开的路线；
- 论文术语、confirmed-path 语义、coherence 语义；
- Figure/Table 的科学作用、布局和证据边界；
- 作者审阅、reviewer simulation 和投稿前工作流；
- Commander/Codex 分工及未来 prompt 规范。

### 2.3 Paper Handoff

权威文件：`docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`。

它负责：

- 论文科学问题、贡献、限制和长期论文路线；
- manuscript source、evidence、Figure/Table 路径；
- 当前数值事实、章节状态和论文可用实验结果；
- event/path database、channel-parameter database 和统计模型状态。

### 2.4 New AI Bootstrap Order

推荐启动顺序：

1. 读取 Engineering Handoff，理解项目、算法和工程约束；
2. 读取本 VTC Writing Handoff，理解论文策略、冻结决策和下一步；
3. 读取 Paper Handoff，确认最新论文资产和论文事实；
4. 只有在需要改稿或审计具体资产时，才读取 `main.tex`、`main_cn_review.tex`、相关 Figure/Table/evidence 文件。

新 AI 不应一开始重新扫描整个项目，也不应从旧 daily handoff 或历史 audit 恢复已被 current source supersede 的状态。

## 3. Commander and Codex Responsibilities

### Commander / Technical-Paper Lead

ChatGPT/AI Commander 负责：

- 判断下一步任务和是否真的需要实验；
- 控制 VTC scope 与科学边界；
- 评估 reviewer 风险和 claim-evidence consistency；
- 决定是否接受新的实验建议；
- 向 Codex 提供完整、可复制、边界明确的 prompt；
- 审查 Codex 的文件、hash、编译和 QA 报告。

### Codex / Executor

Codex 负责：

- 读取本地项目文件和当前状态源；
- 修改获授权的 LaTeX/Markdown；
- 从真实 evidence 生成 Figure/Table；
- 编译、渲染、扫描和做一致性 QA；
- 报告实际改变、未改变内容和下一决策点。

Commander 不应要求用户反复手工上传 Codex 已能检查的本地文件。需要 Codex 工作时，prompt 至少应包含 `TASK`、`ALLOWED SCOPE`、`FORBIDDEN SCOPE`、`FILES TO READ`、`CHANGES TO MAKE`、`SCIENTIFIC CONSTRAINTS`、`COMPILE/QA`、`OUTPUT REPORT` 和 `STOP RULE`。

以下事项不得由 Codex 自行决定：新 SAGE run、新环境任务、删除环境、修改 confirmation semantics、改变论文贡献、加入统计模型、删除主要 Figure、改变 VTC scope 或提交论文。Codex 只能提出 recommendation。

## 4. Project and VTC Scope

### 4.1 VTC identity

- **Conference:** IEEE VTC2027-Spring
- **Paper type:** Regular Paper
- **Primary working title:** `SAGE-Based High-Resolution Multipath Characterization of GPS L1 C/A Signals in Dynamic Vehicular Environments`
- **Alternative title:** `Measurement-Based Characterization of Dynamic GNSS Multipath Using High-Resolution SAGE Path Extraction`
- **External submission deadline:** 2026-09-01
- **Internal complete-draft target:** 2026-08-31
- **Target length:** approximately five IEEE conference pages; current compiled sources are four pages and不应为凑页添加低价值文字。

VTC 是长期 GNSS multipath 项目的当前论文分支，不是长期研究终点。VTC 完成后，长期路线可以恢复：

```text
all-data full-SAGE production
  -> complete event/path database
  -> environment/elevation-conditioned statistical GNSS multipath channel modeling
```

### 4.2 Frozen VTC scope

VTC 研究：

```text
real dynamic GPS L1 C/A raw-IQ measurements
  -> GNSS-SDR tracking/navigation support
  -> NAV-aided observation formation
  -> hierarchical SAGE multipath path extraction
  -> temporal consistency
  -> multi-snapshot joint confirmation
  -> environment-wise descriptive path-level characterization
```

核心 path-level quantities：

- excess delay；
- signed relative Doppler；
- relative power。

VTC 不是：

- 完整 stochastic channel model 论文；
- multipath occurrence-rate 论文；
- event-level elevation-conditioned statistical model；
- 20.46 MHz 论文；
- 新 SAGE 理论或新估计器论文。

这些是 scope boundary，正常论文正文不需要反复写成负面免责声明；handoff 必须保留边界以防未来 AI 越界。

## 5. Paper Scientific Story

动态车载 GNSS 中，接收机级 C/N0、残差和定位误差能够反映性能变化，却不能直接分离导致观测变化的传播路径。本文使用 tracking/telemetry 和 decoded navigation products 完成 PRN/time alignment、NAV wiping 和有效观测窗口构造；再使用 SAGE 进行高分辨率 delay--Doppler path separation；最后通过 temporal consistency 与 multi-snapshot joint confirmation 保留具有跨观测支持的 confirmed multipath path。

论文最后比较的是已确认路径的 excess delay、signed relative Doppler 和 relative power 在所评估动态车载环境中的描述性差异。论文不把这些有限样本写成环境因果效应、总体发生率或完成的统计信道模型。

## 6. Method State and Frozen Decisions

### 6.1 Method academicization status

SAGE method academicization：`Implemented + Validated against current source code`。

当前正式 Method 已包含：

- received-signal model；
- path-wise hidden/residual observation；
- normalized delay--Doppler objective；
- fractional-delay replica refinement；
- complex-gain least-squares update；
- iterative SAGE update and stopping settings；
- NAV-aligned observation formation；
- L=1--4 model-order evaluation；
- BIC/RSS selection logic；
- temporal consistency；
- multi-snapshot joint path confirmation。

不要大范围重写 Method。除非作者或 reviewer 发现真正科学错误，或未来明确授权的 reviewer simulation 识别 HIGH blocker，否则只做 targeted revision、语言和版面修改。

### 6.2 Internal and formal terminology

Engineering artifacts 可以继续使用 Stage0--Stage4。正式论文主叙事使用功能名称：

| Internal implementation | Formal manuscript wording |
|---|---|
| Stage0 | NAV-Aligned Observation Formation |
| Stage1 | Candidate-Window Screening |
| Stage2 | Local SAGE Multipath Estimation and Model-Order Selection |
| Stage3 | Temporal Consistency Validation |
| Stage4 | Multi-Snapshot Joint Path Confirmation |

当前活动英文/中文稿正文扫描结果：`STAGE_NUMBER_USAGE_IN_MAIN_TEXT=0`。不要把 Stage0、Stage1 等编号重新写回正式科学叙事。

## 7. Confirmation Semantics

内部真实 confirmed criterion 固定为：

```text
joint_valid == 1
AND joint_multipath_count > 0
AND the corresponding Stage4 path table has is_multipath == 1
```

正式论文不要暴露 `joint_valid`、`joint_multipath_count`、`is_multipath` 等代码字段作为科学解释；应写成：

> confirmed through the final multi-snapshot joint path confirmation.

必须保持：

- L>=2 只是 local model-order evidence，不是 confirmed multipath；
- temporal consistency / reliable center 只是持续性候选，不是 confirmed multipath；
- candidate、reliable candidate 和 confirmed path 必须分开；
- 未扫描或未晋级窗口不能被解释为 LOS、no-event 或 negative physical evidence。

合法 zero-confirmation 表述：

> no multipath event remained after the final joint confirmation.

或：

> none of the candidates was retained as a confirmed multipath event.

禁止写：`no multipath`、`LOS proven`、`reflection absent`、某颗卫星没有物理多径。

## 8. Coherence Semantic Correction

`PATH_LEVEL_COHERENCE_DEFINED=NO`。

当前 `stage4_joint_summary.maximum_coherence` 是 event/joint-model-level diagnostic：它表示当前拟合 path replicas 之间的最大 normalized cross-correlation / separability diagnostic。它不是单条 path 的 propagation parameter。`stage4_joint_paths.csv` 没有独立的 path-level coherence 字段。

此前把 event-level `maximum_coherence` 通过 event/window join 复制到 path rows 的解释已被 `SUPERSEDED`。原始 Stage4 artifact 和历史 audit 保留不变，但未来 AI 不得恢复 path-level coherence statistics、secondary-path coherence 或把该字段当作 Figure 4 的统一参数。

当前 VTC 统一 path parameters 只有：

- excess delay；
- relative Doppler；
- relative power。

Figure 2 当前不显示 coherence；Figure 4 不包含 coherence。任何 source table 中保留的 `source_event_maximum_coherence` 只能作为 provenance，不能进入 path-level statistics。

## 9. Current Measurement Evidence

### 9.1 Environment-wise Tier A+B descriptive baseline

当前 `VTC_ENVIRONMENT_PATH_CANDIDATES.csv` 共 34 行，其中 Tier A+B 为 30 条 confirmed path，Tier C 为 4 条历史/受限 provenance 行，不进入主环境比较。当前 Figure 4 使用 30 条 Tier A+B path observations，来自 8 个独立场景、12 条含 confirmed path 的 PRN tracks；Table II 的 analyzed-track 分母还包括零事件或未形成确认路径的轨迹。

Table II 当前论文术语和数值为：

| Environment | Independent scenes | Analyzed PRN tracks | Confirmed events | Confirmed paths |
|---|---:|---:|---:|---:|
| Urban | 4 | 4 | 7 | 7 |
| Mountain/Valley | 3 | 9 | 13 | 14 |
| Highway/Open | 2 | 2 | 2 | 2 |
| Special Reflective | 2 | 2 | 7 | 7 |

总计为 11 个 scene、17 条 analyzed PRN tracks、29 个 confirmed events 和 30 条 Tier A+B confirmed paths。这里的 path 不是独立环境 replicate；必须同时报告 scene/task 维度，不能把 30 条 path 当作 30 个独立环境样本。

当前 path-level 三个核心字段 30/30 complete：excess delay、relative Doppler、relative power。Figure 4 的 signed relative Doppler 是实际 estimated source quantity；不能把正负号直接解释为环境效应，因为符号同时受 receiver motion、satellite geometry 和 reflector geometry 影响。

### 9.2 Environment-wise observations

这些是当前有限测量中的描述性观察，不是统计显著性、因果证明或环境排名：

- Urban 展现当前观测中最宽的 excess-delay range，最大 observed excess delay 为 4.5 samples；
- Mountain/Valley 贡献最大的 confirmed-path sample，并显示较宽的 relative-Doppler range；
- Special Reflective 已有 2 个独立场景、2 个任务、7 个 confirmed events 和 7 条 confirmed paths，delay、power、Doppler 有明显变化；
- Highway/Open 目前只有 2 条 confirmed paths，观测到的 delay/Doppler range 更紧凑。

总体只能写：observed differences are qualitatively consistent with distinct reflection/scattering conditions across the evaluated vehicular environments。不能写 causal proof、statistical significance、environment ranking、multipath occurrence probability 或 elevation-conditioned law。

### 9.3 Individual evidence cases

| Case | Status | Paper use |
|---|---|---|
| Reference scene `F1023_V70_D0117_P2`, seven PRNs | Completed / Validated | hierarchy、control、rejection 和 confirmed examples |
| Wave-A G16/G25/G12 | Completed / Validated | 跨任务执行链复现；不作为总体统计 |
| Formal A1 `F1023_V70_D0117_P4/G11/ch2` | Completed / QA PASS; 3 events / 3 paths | 正式生产例 |
| Formal A2 `F1023_V70_D0120_P1/G18/ch2` | Completed / QA PASS; zero confirmed events | 合法 zero-event control；不解释为物理无多径 |
| Formal A3 `F1023_V70_D0120_P5/G16/ch1` | Scientific artifact QA PASS; contract caveat | Pipeline Validation 科学案例；不是 Batch A release evidence |
| Controlled G12 `F1023_V70_D0117_P4/G12/ch4` | Completed / QA PASS / Available | 可用证据；是否进入核心 Results 需由 evidence selection 决定 |
| VTC T1-1 `F1023_V70_D0120_P9/G05/ch10` | QA PASS / Available | Special Reflective first scene；2 events / 2 paths |
| VTC T1-2 `F1023_V80_D0117_P8/G25/ch10` | QA PASS / Available | Highway/Open；2 events / 2 paths |
| VTC T1-3 `F1023_v90_D0117_P7/G11/ch6` | QA PASS / Available | Mountain/Valley；1 event / 1 path |
| Special Reflective supplement `F1023_V70_D0122_P2/G15/ch8` | QA PASS / Available | 第二独立 Special Reflective scene；5 events / 5 paths |

G15 的加入使 Special Reflective 最终决策为：

```text
SPECIAL_REFLECTIVE_PAPER_DECISION = KEEP_IN_MAIN_ENVIRONMENT_COMPARISON
```

它仍然只支持 bounded descriptive comparison，不支持 distribution fitting、occurrence probability 或 elevation-conditioned conclusion。

### 9.4 Geometry boundary

当前 geometry/elevation evidence 仍为 `PARTIAL`。Elevation/azimuth/SNR 主要来自 NMEA/GSV-derived geometry；RINEX NAV 用于导航/PRN provenance，不应被表述为已经完成 broadcast-ephemeris event-level reconstruction。绝对 observation-clock bridge、TOW-to-UTC provenance 和 event-level geometry join 尚未冻结。

LOW/MID/HIGH 定义为 0--30°、30--60°、60--90° 的 planning/context bins。当前这些 bins 不能生成 geometry-QA-complete event-level denominator，也不能支持 elevation-conditioned statistics。`scene/PRN mean elevation` 不能替代 event-level elevation。

## 10. Figures

当前正式图资产位于 `docs/vtc2027_spring/figures/`，来源和输出 hash 由 `figures/figure_generation_manifest.json` 追踪。

### Figure 1

作用：measurement / processing / estimation framework，说明 raw IQ 如何经过 GNSS-SDR、NAV-aligned observation formation、candidate screening、SAGE estimation、temporal/joint confirmation 变成 path-level quantities。当前图和 PDF/PNG 已存在并被 LaTeX 引用。

### Figure 2

作用：representative SAGE-extracted multipath case。

当前 primary case：`F1023_V80_D0117_P8/G25/ch10`, window 985。只显示 direct/secondary path 的 delay、relative Doppler、relative power 等真实 path quantities；不显示 coherence，不伪造 correlation/residual curve。

### Figure 3

作用：hierarchical candidate reduction and path confirmation，展示 local fitting/temporal persistence 不等于 final confirmed multipath。

当前最新排版：single-column `figure`，`\columnwidth`；引用在第 2 页，实际图在第 3 页，距离 1 页。Figure 3 在当前 PDF 中可读，未来作者若认为字号不足，只能做 targeted layout/asset review，不改变数据或 hierarchy。

### Figure 4

作用：environment-wise multipath path characteristics。

当前为三面板：

1. excess delay；
2. relative power；
3. signed relative Doppler。

使用 30 条 Tier A+B confirmed path observations，显示真实 individual path points、environment median 和每个环境的真实 `n`。不做 KDE、distribution fitting、regression、occurrence-rate normalization 或 geometry conditioning。

当前最新排版：double-column `figure*`，约 `0.92\textwidth`；引用在第 3 页，实际图在第 4 页，距离 1 页。Figure 4 与 Figure 3 不在同一专用浮动页。

Figure 4 当前图像只保留环境、excess delay、relative power、signed relative Doppler、individual path observations、environment median 和 sample size `n`；内部 evidence-governance 标注已移除。Figure 2/3 的 Stage 编号展示标签也已改为科学功能名称，未改变任何数据点或层级统计。

### VTC Final Figure Internal-Language Cleanup (2026-08-17)

状态：`Implemented / QA validated`。本次只通过既有 Figure 生成脚本重生成图像并更新 manifest；没有读取 raw IQ、运行 MATLAB/SAGE、执行 production 或改变 scientific selector/data。Figure 4 原注释 `Tier A+B descriptive evidence only` 已删除且没有替换免责声明。active manuscript source、captions 和 Figure 1--4 的内部治理语言扫描均为 `0`，active Figure 中 `Stage0`--`Stage4` 编号为 `0`。

英文 `main.pdf` 和中文 canonical `main_cn_review.pdf` 均为 4 页；Figure 3 引用页 2、渲染页 3，Figure 4 引用页 3、渲染页 4，均满足一页距离目标。`SCIENTIFIC_CONTENT_FROZEN=YES` 保持不变。本次完成后不再继续扩展修改，下一步为 `VTC_WRITING_HANDOFF_CONSOLIDATION`。

## 11. Tables

### Table I

测量与 processing configuration，来源：
`docs/vtc2027_spring/evidence/manuscript_tables/measurement_configuration.csv` 和 `docs/vtc2027_spring/tables/table1_measurement_configuration.csv`。当前事实包括 RF-Catcher V2、GNSS dome antenna、RHCP roof mounting、GPS L1 C/A、1575.42 MHz、10.23 MHz、interleaved little-endian int16 IQ、GNSS-SDR support 和 NAV-aided SAGE chain。time synchronization、external clock、IF 等未记录内容不能补写。

### Table II

作用：environment measurement coverage and confirmed multipath paths。正式稿显示列名 `Analyzed PRN tracks`；这是科学可读术语。源 CSV 中仍可能保留机器字段 `full_pipeline_tasks`，未来 AI 不应把该内部字段名直接复制到正文。

Table II 数值已经冻结为第 9.1 节所列四环境表；不得恢复 `Tier A+B`、`census`、`QA`、`production`、manifest、task 等内部治理词到 caption 或正文。

未来 Table III/IV/V 可以作为作者决定后的 manuscript assets，但当前不自动新建或扩大表格体系。

## 12. Manuscript Structure and Latest Layout State

正式英文投稿 source：`docs/vtc2027_spring/manuscript/latex/main.tex`。英文 Markdown：`docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md`，是 working mirror/drafting aid。中文 `main_cn_review.tex` 和 `VTC2027_Spring_CN_REVIEW.md` 是 review derivative，不是投稿源。

`SOURCE_OF_TRUTH: English main.tex is the submission source of truth; Chinese main_cn_review.tex is a review derivative only.`

当前 Section IV：

- **IV-A Hierarchical Path Extraction Behavior**
- **IV-B Representative SAGE-Extracted Multipath Case**
- **IV-C Environment-Wise Path Characteristics**
- **IV-D Cross-Environment Multipath Characteristics**

IV-A 当前已完成 academic rewrite：Stage2 L=1--4 评估是同一窗口的不同 model orders，不是额外独立 observation；G28 是 temporal candidate 被 final joint confirmation 排除的例子；G18 是 final joint confirmation 后没有 retained confirmed event 的合法 zero-confirmation 案例。

当前编译和布局事实：

- English `main.pdf`：4 pages；
- Chinese canonical review `main_cn_review.pdf`：4 pages；
- English compile chain：`pdflatex -> bibtex -> pdflatex -> pdflatex`，exit code 0；
- Chinese compile chain：`xelatex -> bibtex -> xelatex -> xelatex`，exit code 0；
- 无 fatal error、undefined citation/reference 或 overfull box；English 有少量非致命 underfull hbox，Chinese 有字体 fallback 警告；
- Figure 3 first reference page 2 / render page 3；Figure 4 first reference page 3 / render page 4；
- `FIG3_SINGLE_OR_DOUBLE_COLUMN=SINGLE`；`FIG4_SINGLE_OR_DOUBLE_COLUMN=DOUBLE`；`FIG3_4_DEDICATED_FLOAT_PAGE=NO`；
- 当前 PDF 已完成视觉检查，正文、caption、表格、Figure 和 references 可读。

当前 layout cleanup 只改变排版、caption、IV-A 和内部词语，不改变 Figure/Table 数据、Stage 语义或科学数字。

## 13. Writing and Terminology Rules

### 13.1 Formal manuscript language

正式论文不是 QA report、production report、software audit、database census 或 engineering handoff。不得恢复以下内部项目管理词到科学正文：

`census`, `audit`, `Tier A+B`, `QA PASS`, `production`, `manifest`, `namespace`, `execution request`, `checkpoint`, `ledger`, `canonical field`, `source field`, `Commander`, `freeze`。

可使用正常学术词：`processing pipeline`、`implementation`、`measurement`、`observation`、`confirmed path`、`descriptive`。

### 13.2 Defensive wording

正文不应反复堆叠 `does not support`、`does not establish`、`not causal` 等免责声明。优先使用自然限定：

- observed；
- measured；
- in the evaluated measurements；
- currently available；
- qualitatively consistent with；
- bounded descriptive comparison。

边界仍必须保留，但应让论文像论文，而不是审计报告。

### 13.3 Zero-event and small-sample wording

G18 等合法 zero-event 输出必须写成操作性结果，不写成物理否定。30 条路径属于有限 evidence set，不能写成 population distribution、occurrence rate、environment ranking 或 completed statistical model。

## 14. Current Scientific Freeze

`SCIENTIFIC_CONTENT_FROZEN=YES` 的含义：

- 实验数据冻结；
- 方法和 confirmation criterion 冻结；
- Figure 科学数据冻结；
- Table 数字冻结；
- environment groups 和 path-parameter meaning 冻结；
- contribution scientific meaning 冻结。

仍允许作者级修改：

- 句子学术化；
- caption 优化；
- float/layout 优化；
- 英文润色；
- 删除重复；
- 改善可读性；
- 将内部词替换为科学词。

Codex 不得自行：

- 增加新的科学 claim；
- 运行或要求新实验；
- 重算 path 数据；
- 修改 confirmation criterion 或 SAGE；
- 改动 environment evidence；
- 将 coherence 恢复为 path-level parameter；
- 将 scene-level elevation 改写为 event-level elevation。

## 15. Current Author Review Workflow

当前工作方式是 `USER_AUTHOR_REVIEW`：用户阅读 `main_cn_review.pdf`，逐页指出看不懂、太弱、工程味、排版差、表述不自然、Figure 难找、Figure 价值不足或 conclusion 不够强等问题；Commander 判断问题级别；Codex 做小范围 targeted revision。

不要因为一句话不自然就整篇重写。每次修改必须明确文件、段落、科学边界、编译和 stop rule。

当前唯一 next action：`CURRENT_NEXT_ACTION=VTC_WRITING_HANDOFF_CONSOLIDATION`。

## 16. Remaining VTC Roadmap

```text
USER AUTHOR REVIEW
  -> 逐项作者级修改
  -> 完整阅读中文 canonical PDF
  -> 确认英文同步
  -> FINAL REVIEWER SIMULATION
  -> 只处理真正 CRITICAL / HIGH 问题
  -> FINAL ENGLISH POLISH
  -> 补齐 author information
  -> 核验 official VTC submission requirements
  -> PDF compliance
  -> submission freeze package
  -> manual submission before 2026-09-01
```

Reviewer Simulation 当前不要运行；必须等作者审阅完成。未来 review 维度包括 novelty、technical correctness、method reproducibility、experimental sufficiency、claim-evidence consistency、figure/table readability、related work、English quality 和 VTC fit。

理想 gate：`CRITICAL=0`、`HIGH=0`、`SCIENTIFIC_BLOCKER=0`、`NEW_EXPERIMENT_REQUIRED=NO`。Reviewer 若建议新实验，不得自动执行，必须由 Commander 判断。

## 17. Main Reviewer Risks

### 17.1 Novelty perception

SAGE 不是本文新算法。论文价值必须来自：真实车载 raw-IQ measurement、NAV-aided SAGE path extraction、hierarchical reliability 和 environment-wise measured path characterization。不能让论文看起来只是“把 SAGE 跑在 GPS 数据上”。

### 17.2 Environment sample imbalance

Highway/Open 当前只有 2 条 confirmed paths。必须显示真实 `n`，避免总体统计 claim。当前这是 limitation / medium risk，不是要求自动补跑 Highway 的 blocker；`HIGHWAY_SUPPLEMENT_REQUIRED=NO`。

### 17.3 External ground truth

当前没有 external ground truth 足以声称 path detection accuracy 或 ground-truth validation。论文定位是 measurement-based high-resolution multipath characterization。

### 17.4 Remaining non-blocking review items

上一轮 targeted review 的 HIGH issue 为 0、CRITICAL 为 0；M-01（完整 grid/tolerance disclosure）、M-03（紧凑 Figure 2）和 M-05（time synchronization/front-end details undocumented）为 partially closed / non-blocking。不要为填补这些文字风险自动启动新实验。

## 18. Do-Not-Reopen List

当前 VTC 收尾不得重新打开：

- Full 67-task production for VTC；
- 20.46 MHz；
- complete stochastic channel model；
- event-level elevation analysis；
- occurrence-rate study；
- PDP statistical model；
- RMS delay spread model；
- Ricean K-factor model；
- path lifetime model；
- distribution fitting；
- synthetic channel generation；
- Highway supplement merely because `n=2`；
- Special Reflective supplement merely because G15 is now included；
- v3.1/raw-coarse/sampling selector；
- path-level coherence statistics。

长期项目可以在 VTC 提交后重新决策，但不属于当前论文收尾任务。

## 19. Commander / Codex Operating Rules

未来 Codex prompt 应明确：

1. 具体 TASK；
2. ALLOWED SCOPE；
3. FORBIDDEN SCOPE；
4. FILES TO READ；
5. CHANGES TO MAKE；
6. SCIENTIFIC CONSTRAINTS；
7. COMPILE/QA；
8. OUTPUT REPORT；
9. STOP RULE。

任何实际工程动作、实验、QA 或论文资产变化，都必须按影响范围判断是否更新 Engineering Handoff、Paper Handoff 或 Paper Workspace Index。普通 manuscript-only targeted revision 不需要更新 Engineering Handoff；只有论文科学路线、章节状态、论文事实或资产结构变化时才同步相应文档。

不要创建 `VTC_WRITING_HANDOFF_v2.md`、`FINAL_HANDOFF.md`、`LATEST_HANDOFF.md`、日期型 parallel current handoff 或其他重复 status/plan 文件。本文件是唯一 VTC Writing Commander current handoff。

## 20. Source-of-Truth and Conflict Resolution

优先级必须按信息类型理解，而不是使用一个粗暴的全局线性顺序：

| Information type | Authority |
|---|---|
| Engineering fact | actual code/artifact/receipt/QA + Engineering Handoff |
| Writing strategy and Commander decisions | this VTC Writing Handoff |
| Paper current assets and scientific state | Paper Handoff + current `main.tex` |
| Figure/Table numerical source | current evidence CSV/manifest + source artifact |
| Historical audit | provenance only |

如果 handoff、paper、code 和 evidence 冲突：

1. 判断冲突属于 engineering fact 还是 paper interpretation；
2. 检查当前 actual source/artifact；
3. 检查当前对应 handoff；
4. 明确报告冲突和影响；
5. 等 Commander 决定。

不得静默选择旧文档，也不得用历史 audit 覆盖 current source。特别是旧 coherence audit 不能覆盖当前 `PATH_LEVEL_COHERENCE_DEFINED=NO` 的解释；旧 5-path evidence package snapshot 不能覆盖后续已冻结的 30-path Figure 4 environment comparison，但两者都可以作为 provenance 说明其时间和用途。

## 21. Current File Map

### State and navigation

- `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` — 工程唯一状态源；
- `docs/GNSS_SAGE_VTC_WRITING_HANDOFF_CURRENT.md` — VTC writing/Commander 唯一状态源；
- `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` — 论文科学和资产唯一状态源；
- `docs/PAPER_WORKSPACE_INDEX.md` — 论文资产导航，不是状态源；
- `docs/vtc2027_spring/VTC_PLAN.md` — VTC目标和计划；
- `docs/vtc2027_spring/EVIDENCE_MATRIX.md` — claim-to-artifact evidence matrix 和缺失项；
- `docs/vtc2027_spring/VTC_PRODUCTION_PRIORITY_QUEUE.md` — 历史 evidence-priority queue；当前不授权新 execution；
- `docs/vtc2027_spring/MANUSCRIPT_OUTLINE.md` — 五页结构和篇幅计划；
- `docs/vtc2027_spring/FIGURE_TABLE_PLAN.md` — 图表候选、来源和状态。

### Manuscript

- `docs/vtc2027_spring/manuscript/latex/main.tex` — English submission source of truth；
- `docs/vtc2027_spring/manuscript/latex/main.pdf` — 当前 English compiled PDF；
- `docs/vtc2027_spring/manuscript/latex/references.bib` — English references source；
- `docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md` — English working mirror；
- `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.tex` — Chinese review derivative；
- `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.pdf` — 唯一 canonical Chinese review PDF；
- `docs/vtc2027_spring/manuscript/VTC2027_Spring_CN_REVIEW.md` — Chinese review Markdown mirror。

### Evidence, figures, tables

- `docs/vtc2027_spring/evidence/VTC_ENVIRONMENT_EVIDENCE_CENSUS.csv` — environment/task evidence census；
- `docs/vtc2027_spring/evidence/VTC_ENVIRONMENT_PATH_CANDIDATES.csv` — 34 path candidates，其中 Tier A+B 30 条；
- `docs/vtc2027_spring/evidence/vtc_confirmed_path_database.csv` — current traceability index；不要把它误认为长期 path database；
- `docs/vtc2027_spring/evidence/vtc_geometry_alignment_qa.md` — geometry/time alignment，当前 PARTIAL；
- `docs/vtc2027_spring/evidence/manuscript_tables/measurement_configuration.csv` — Table I source；
- `docs/vtc2027_spring/evidence/manuscript_tables/experimental_evidence_summary.csv` — evidence summary source；
- `docs/vtc2027_spring/evidence/manuscript_figures/representative_path_case.csv` — Figure 2 candidates；
- `docs/vtc2027_spring/evidence/manuscript_figures/hierarchical_filtering_summary.csv` — Figure 3 source；
- `docs/vtc2027_spring/evidence/manuscript_figures/path_characterization.csv` — compact path-figure extract；
- `docs/vtc2027_spring/figures/figure_generation_manifest.json` — source/output hashes and generation audit；
- `docs/vtc2027_spring/figures/figure1_workflow.pdf`、`figure2_representative_path.pdf`、`figure3_hierarchical_confirmation.pdf`、`figure4_environment_path_characteristics.pdf` — current PDF figures；
- `docs/vtc2027_spring/tables/table1_measurement_configuration.csv`、`table2_experimental_evidence_summary.csv` — table copies。

### Review and submission

- `docs/vtc2027_spring/manuscript/claim_matrix_vtc_final_qa.csv` — claim-to-evidence audit；
- `docs/vtc2027_spring/manuscript/reference_verification_matrix.csv` — reference verification matrix；
- `docs/vtc2027_spring/manuscript/VTC_SUBMISSION_CANDIDATE_REVIEW.md` — prior simulated review；
- `docs/vtc2027_spring/manuscript/VTC_TARGETED_REVISION_RECHECK.md` — targeted review re-check；
- `docs/vtc2027_spring/submission/VTC2027_SUBMISSION_REQUIREMENTS_AUDIT.md` — official requirement audit；
- `docs/vtc2027_spring/submission/VTC2027_Spring_submission_candidate.pdf` — existing candidate PDF, not final submission。

## 22. Current Status Flags

```text
CURRENT_PHASE=USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN=YES
SAGE_PRODUCTION_STOPPED=YES
NEW_EXPERIMENT_REQUIRED=NO
SPECIAL_REFLECTIVE_PAPER_DECISION=KEEP_IN_MAIN_ENVIRONMENT_COMPARISON
HIGHWAY_SUPPLEMENT_REQUIRED=NO
PATH_LEVEL_COHERENCE_DEFINED=NO
EVENT_LEVEL_GEOMETRY_STATUS=PARTIAL
VTC_MINIMUM_EVIDENCE_STOP_CONDITION=NOT_SATISFIED_AS_GEOMETRY_STOP
ENGLISH_MAIN_TEX_IS_SUBMISSION_SOURCE=YES
CHINESE_LATEX_IS_REVIEW_ONLY=YES
CHINESE_CANONICAL_PDF_ONLY=YES
STAGE_NUMBER_USAGE_IN_MAIN_TEXT=0
CURRENT_NEXT_ACTION=USER_AUTHOR_REVIEW
NEXT_VTC_DECISION_REQUIRED=YES
```

状态词必须保持：`Completed / Validated / Implemented / Planned / Not started / Failed-Frozen`。`Implemented` 或 `Planned` 不能改写成 `Completed`；gold replay 前预测不能写成论文结果；环境 planning context 不能写成 event-level geometry。

## 23. New Commander Startup Protocol

未来 AI 读完三个 handoff 后，不要重新向用户总结整个项目。先确认：

1. 当前阶段：`USER_AUTHOR_REVIEW`；
2. scientific freeze：`SCIENTIFIC_CONTENT_FROZEN=YES`；
3. 当前唯一 next action：作者审阅本轮 targeted revision；
4. 是否存在未完成 Codex 任务：没有已授权的 SAGE/production 任务；VTC production stop 仍有效。

用户指出某一句论文不好时，按局部问题处理：先定位正文、caption、Figure/Table 或证据边界，再给出最小 targeted revision；不要整篇重写，不要新增实验，不要自动启动 Reviewer Simulation。

### Current first response template

```text
CURRENT_PHASE = USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN = YES
SAGE_PRODUCTION_STOPPED = YES
NEW_EXPERIMENT_REQUIRED = NO
CURRENT_NEXT_ACTION = USER_AUTHOR_REVIEW
NEXT_DECISION_REQUIRED = Commander review after author feedback
```

## 24. Consolidation Integrity Flags

```text
VTC_WRITING_HANDOFF_CREATED=YES
THREE_HANDOFF_BOOTSTRAP_DEFINED=YES
COMMANDER_CODEX_ROLE_DEFINED=YES
SCIENTIFIC_FREEZE_DOCUMENTED=YES
COHERENCE_CORRECTION_DOCUMENTED=YES
ENVIRONMENT_EVIDENCE_DOCUMENTED=YES
FIGURE_STRATEGY_DOCUMENTED=YES
WRITING_RULES_DOCUMENTED=YES
REVIEWER_RISKS_DOCUMENTED=YES
DO_NOT_REOPEN_LIST_DOCUMENTED=YES
REDUNDANT_STATUS_SYSTEM_CREATED=NO
ENGINEERING_STATE_CHANGED=NO
SCIENTIFIC_DATA_CHANGED=NO
MANUSCRIPT_SCIENTIFIC_CONTENT_CHANGED=NO
PRODUCTION_ARTIFACT_CHANGED=NO
NEW_EXPERIMENT_EXECUTED=NO
CURRENT_NEXT_ACTION=USER_AUTHOR_REVIEW
```

## 26. Figure 4 Layout and Chinese Canonical PDF Maintenance (2026-08-17)

状态：`Validated / Implemented`。本轮仍属于 `USER_AUTHOR_REVIEW` 下的 layout-only 与 review-asset maintenance；科学内容和数据保持冻结。

### Figure 4 layout check

- 检查了 `main.tex` 中 Figure 4 的 `figure*` 源码位置、首次正文引用和当前浮动参数。Figure 4 已位于其首次讨论之后，使用 IEEE 风格的 top float：`[!t]`，宽度 `0.92\textwidth`。
- 当前英文 `main.pdf` 中 Figure 4 位于第 4 页顶部；其下方紧接 IV-D Cross-Environment Multipath Characteristics，随后为 Conclusion 和 References。因此已满足“非孤立最后一页大图”的目标，本轮不再改动 `main.tex`、图宽或科学文字。
- Figure 4 三个 panel、坐标轴、环境标签、样本数、median、散点、caption 均清晰；Figure 1--3、Table I--II、Conclusion 和 References 未出现因浮动造成的明显恶化。

```text
FIG4_LAYOUT_CHANGED=NO
FIG4_LAYOUT_STATUS=VALIDATED_IN_PLACE
OLD_PAGE=4
NEW_PAGE=4
OLD_WIDTH=0.92\textwidth
NEW_WIDTH=0.92\textwidth
FIG4_ISOLATED_FINAL_PAGE=NO
FIG4_DATA_CHANGED=NO
FIG4_SCIENTIFIC_CONTENT_CHANGED=NO
PAGE_COUNT=4
```

### Chinese canonical review PDF

```text
CHINESE_REVIEW_CANONICAL=main_cn_review.pdf
CHINESE_CANONICAL_REPLACEMENT=PASS
CANONICAL_SOURCE=main_cn_review_author_revision.pdf
HASH_MATCH=YES
CANONICAL_PAGES=4
```

The canonical file was replaced by a file-level copy after confirming that the source revision PDF was non-empty and four pages. The provenance copy was retained. No Chinese source or manuscript content was rewritten.

## 25. Targeted Author-Review Revision (2026-08-17)

状态：`Implemented / Validated`。本轮严格限定为 VTC2027-Spring 论文作者审阅修订；科学内容、数据、图表数值、方法、判据和证据边界均保持冻结。

- 已按 English-first 顺序修订 `manuscript/latex/main.tex`，随后同步 `VTC2027_Spring_draft.md`、`manuscript/latex_cn_review/main_cn_review.tex` 和 `VTC2027_Spring_CN_REVIEW.md`。
- 已处理八项作者指出的 targeted revision：采样叙述、较高阶模型的正向解释、路径量定义、G28/G18 场景识别、G25 联合确认措辞、环境中位数的 bounded descriptive 语义、观测时长/事件计数语义，以及 Figure 3 的 40-ms 基准窗口和层级确认解释。
- 路径级量的正文定义和结果叙事仅保留 excess delay、signed relative Doppler 和 relative power；未引入 path-level coherence。
- Figure 3 仅用于说明从有效 40-ms observation windows 到 confirmed paths 的渐进式确认行为；不作为环境代表性图。环境级描述仍由 Table II 与 Figure 4 承担。未将未入选窗口解释为 LOS 或“无多径”。
- `main.pdf` 英文编译链和中文 review 的 versioned 编译链均通过；两份 PDF 均为 4 页并完成文本、引用、图表和视觉检查。剩余项仅为 underfull/字体 fallback 等非科学阻塞 warning。
- 中文 canonical PDF 仍被已有文件句柄锁定；本轮新生成并完成 QA 的文件为 `manuscript/latex_cn_review/main_cn_review_author_revision.pdf`。中文源文件已完成同步，canonical 文件未被强制覆盖。

```text
CURRENT_PHASE=USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN=YES
SAGE_PRODUCTION_STOPPED=YES
NEW_EXPERIMENT_REQUIRED=NO
AUTHOR_REVIEW_TARGETED_REVISION=IMPLEMENTED
MANUSCRIPT_DATA_CHANGED=NO
FIGURE_DATA_CHANGED=NO
TABLE_DATA_CHANGED=NO
NEW_EXPERIMENT_EXECUTED=NO
RAW_IQ_READ=NO
MATLAB_EXECUTED=NO
SAGE_EXECUTED=NO
CURRENT_NEXT_ACTION=USER_AUTHOR_REVIEW
```
