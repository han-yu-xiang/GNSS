# GNSS-SAGE 主线运行 Commander 交接手册

**项目根目录：** `E:\GNSS_Multipath_Project`  
**支线身份：** Long-Term Mainline / 主线运行  
**本文件职责：** 让一个完全没有聊天上下文的新 AI，在读取工程交接、论文交接和本文件后，直接接任长期主线 Commander，继续推进“全数据 SAGE → event/path database → channel-parameter database → environment/elevation-conditioned statistical channel modeling”。  
**当前日期：** 2026-08-31
**重要：** VTC 写作和暗室信道仿真已拆到其它对话；本对话只负责长期主线运行。  

## Current Phase-1 Stage3 Academic Statistical Model Status (2026-08-31)

本节是当前 Phase-1 scientific status 的优先来源；8 月 25 日前的建模
blocked/not-started 记录保留为历史执行上下文，不再覆盖本节。

- Canonical Stage3 model：`dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3/`；report：`docs/ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_R3_REPORT.md`。
- Canonical scientific closure：`dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/`；report：`docs/PHASE1_TRADITIONAL_CHANNEL_MODELING_SCIENTIFIC_CLOSURE.md`。两者均已完成并通过独立 QA，状态为 `COMPLETE_WITH_LIMITATIONS / PASS_WITH_LIMITATIONS`。
- Stage3 academic population 为 783 observations、445 centers、366 algorithm-level tracks、716 elevation-ready observations、50 runs、12 scenes、18 PRNs；主统计单位为 `WEIGHTED_OBSERVATION`，权重为 `1 / algorithm_track_size`。
- 建模层次为 `Global → Environment → Environment×Elevation`；边际族为 delay `Lognormal`、signed relative Doppler `Normal`、relative power `Normal`。Gaussian Copula 只在 global / environment / support-gated cell 层使用，不声称 12 个 cell 都有独立 covariance。
- 稳健性证据包括 scene-block bootstrap、run-level sensitivity 和 grouped LOSO。Stage4 100 条 strict-confirmed paths 仅为 high-confidence selection-sensitivity subset；其结果为 `MATERIAL_DIFFERENCE`，不是 ground truth。
- Scientific closure 为 environment effect `INCONCLUSIVE`、elevation effect `INCONCLUSIVE`、environment×elevation interaction `PARTIAL`；Ricean K 不可识别，persistence 仅为算法观测持续性。
- `PHASE_1_TRADITIONAL_STATISTICAL_MODELING = COMPLETE_WITH_LIMITATIONS`。coverage-complete event/path database、通用 channel-parameter database、Phase-2 AI、20.46 MHz 和完整暗室生成器仍不在本次完成范围；长期论文 Results 同步为 `Pending / In progress`。

---

## 0. 新 AI 启动顺序

必须先读取：

1. `GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
2. `GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`
3. 本文件 `GNSS_SAGE_MAINLINE_COMMANDER_HANDOFF_CURRENT.md`

然后恢复：

```text
ROLE = COMMANDER / TECHNICAL LEAD
CODEX_ROLE = EXECUTOR

VTC_BRANCH_OWNER = OTHER_CONVERSATION
DARKROOM_BRANCH_OWNER = OTHER_CONVERSATION
MAINLINE_BRANCH_OWNER = THIS_CONVERSATION

LONG_TERM_MAINLINE = ACTIVE
```

不要重新规划整个项目。

不要重新做 VTC 写作。

不要把暗室 Rain Overlay 工作混入主线 production。

---

## 1. 主线真正目标

长期主线固定为：

```text
all GNSS raw IQ
    ↓
GNSS-SDR preprocessing
    ↓
NAV-aided full SAGE
    ↓
QA-approved confirmed event/path results
    ↓
coverage-complete event/path database
    ↓
channel-parameter database
    ↓
geometry/time alignment
    ↓
environment/elevation-conditioned statistical modeling
    ↓
channel model / simulation interface
```

最终科研目标不是“跑完 SAGE”本身，而是形成可追溯的：

```text
scene
× PRN
× tracking channel
× time/window
× event
× path
```

数据库，并进一步研究：

- multipath occurrence probability；
- path count；
- excess delay；
- relative power；
- relative Doppler；
- mean excess delay；
- RMS delay spread；
- Doppler spread；
- Ricean K-factor；
- persistence / lifetime；
- environment dependence；
- elevation dependence；
- CN0 / speed / scene 条件。

当前工程和论文交接明确：coverage-complete event/path database、独立通用 channel-parameter database 和完整暗室统计生成器尚未完成；但 bounded Phase-1 Stage3 traditional statistical model 已完成并通过 closure QA。

---

## 2. 与两个其它对话的边界

### VTC

VTC 论文已经交给其它对话。

本主线对话不得：

- 修改 VTC `main.tex`；
- 修改 VTC 图表；
- 修改 VTC scientific freeze；
- 重新解释 VTC claim；
- 为 VTC 临时补实验，除非用户明确把任务移回本对话。

主线新结果未来可以成为期刊/长期论文数据，但不要自动回写 VTC。

### 暗室仿真

Darkroom / Rain Channel Emulation 已交给其它对话。

本主线只负责提供未来可复用的：

```text
base environment path/channel statistics
```

不负责当前 Clear/MidRain/HeavyRain 的紧急 SAGE、Rain Overlay 或模拟 IQ 生成。

两个支线最终可以共享长期数据库，但运行治理必须分开。

---

## 3. 当前工程事实必须继承 Engineering Handoff

必须以实际 artifact + `GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` 为工程事实源。

当前已知核心事实：

```text
PROJECT_ROOT = E:\GNSS_Multipath_Project
TOTAL_SCENES = 19
10.23_MHz_SCENES = 13
20.46_MHz_SCENES = 6
```

当前 pipeline：

```text
raw IQ
→ GNSS-SDR
→ Stage0
→ Stage1
→ Stage2
→ Stage3
→ Stage4
→ confirmed event/path
```

当前 `run_nav_sage_pipeline.m`：

- 支持显式 `sceneId`
- 支持显式 `PRN`
- 支持显式 `TrackingChannel`
- 支持显式 `ProjectRoot`
- 支持 `Resume`
- 当前只允许 10.23 MHz
- 20.46 MHz 暂未适配

10.23 MHz 下：

```text
~10 samples/chip
Stage2 fractional delay step = 0.1 sample
```

---

## 4. Stage0–Stage4 的不可改变语义

### Stage0

有效 NAV symbol / 40 ms window 母集。

不是多径事件。

### Stage1

candidate screening。

不是 confirmed multipath。

### Stage2

对候选做 fractional SAGE、评估 `L=1..4`。

```text
L >= 2 ≠ confirmed multipath
```

### Stage3

temporal persistence / reliable center。

```text
Stage3 reliable ≠ confirmed multipath
```

### Stage4

multi-snapshot joint confirmation。

当前 confirmed criterion 必须继续严格使用：

```text
joint_valid == 1
AND
joint_multipath_count > 0
AND
matching path row has is_multipath == 1
```

只有最终通过 Stage4 的 multipath path 才进入 confirmed event/path database。

---

## 5. Coherence 语义永久冻结

必须继承当前纠正结果：

```text
PATH_LEVEL_COHERENCE_DEFINED = NO
```

`maximum_coherence` 是：

```text
event/model-level
joint-solution replica separability / reliability diagnostic
```

不是：

```text
per-path propagation parameter
```

不得在主线数据库中把 event-level `maximum_coherence` 重复 join 到每条 path 后再当 path-level coherence 分析。

如果数据库保留它，应命名成类似：

```text
source_event_maximum_coherence
```

或单独放 event/model table。

---

## 6. 当前已有 SAGE 结果的保护规则

既有结果不可覆盖。

尤其：

- reference scene 结果；
- `G06_nav_sage_v1` historical baseline；
- reference 其它 PRN；
- Wave-A 结果；
- Wave-2A G11；
- accepted production results；
- VTC T1-1/T1-2/T1-3；
- G15 Special Reflective supplement；
- historical A3 G16 contract-deviation artifact。

原则：

```text
existing output = protected
```

主线恢复生产时优先使用：

```text
new_only = true
resume_allowed = false
```

中断：

```text
保留 partial artifact / checkpoint
不自动删
不自动覆盖
不自动 resume
```

---

## 7. 当前 accepted / known result 状态

Engineering Handoff 中最近记录的 accepted 10.23 MHz production count 已更新到：

```text
7 / 67
```

其中包括此前已接受结果以及 G15 supplement；historical A3 G16 因执行契约偏差继续不计 accepted production。

主线 Commander 不得只凭旧 summary 数字做决定。

在真正恢复 production 前，Codex 必须做一次**只读 current-state reconciliation**：

1. 当前 production manifest；
2. current production summary；
3. existing `scenes/**/sage_results`；
4. QA reports；
5. accepted-state rule；
6. historical G16 exclusion；
7. VTC G15 addition；
8. remaining planned tasks。

最终生成一个唯一的：

```text
MAINLINE_CURRENT_ACCEPTED_STATE
```

再批准下一任务。

---

## 8. 原 STOP 状态如何处理

Engineering Handoff 中存在明确 Commander 决策：

```text
STOP SAGE PRODUCTION
```

该 STOP 当时是为了：

```text
VTC evidence consolidation
```

因此：

**本文件不能静默假定 STOP 已经失效。**

但用户现在新开主线运行对话，意图是把长期主线单独继续管理。

新 Commander 接手后必须先做一次状态恢复：

```text
MAINLINE_RESUME_INTENT = PRESENT
OLD_VTC_STOP = HISTORICAL_ACTIVE_CONSTRAINT
```

然后：

1. 只读检查当前工程状态；
2. 确认没有其它正在运行的 SAGE / MATLAB task；
3. 确认 VTC 和暗室 branch 不会写同一 output namespace；
4. 确认 current production manifest / accepted-state；
5. 再向用户明确提出或接受一次：
   `RESUME LONG-TERM MAINLINE PRODUCTION`
6. 只有得到明确主线恢复授权后才创建新的 production request。

如果用户在新对话第一句话已经明确：

> “继续主线生产 / 恢复主线运行”

则可视为恢复意图，但仍必须做只读 preflight 后再执行。

---

## 9. 主线恢复后第一目标

不要一上来直接跑所有剩余任务。

第一阶段：

### P0 — Current-state reconciliation

读取：

- Engineering Handoff；
- production manifest；
- production summary；
- QA reports；
- existing outputs；
- inventory；
- metadata。

输出：

```text
accepted tasks
completed-but-not-accepted tasks
existing validation-only tasks
planned tasks
blocked tasks
multi-channel tasks
20.46 MHz tasks
```

### P1 — Freeze next production queue

基于 current manifest 选择下一批 10.23 MHz task。

选择规则：

- 不覆盖 existing output；
- 输入完整；
- tracking channel 唯一或已冻结；
- GNSS-SDR / NAV / trajectory / geometry 具备；
- 10.23 MHz；
- target namespace absent；
- 未在其它 branch 使用同一 output；
- 不使用 gold outcome 挑任务。

### P2 — One-task execution

一次只批准一个任务。

### P3 — Independent QA

每个 task 完成后先 QA。

### P4 — Ingest

QA PASS 后才进入长期 event/path database。

---

## 10. 不要重新走已失败的加速路线

当前主线是：

```text
accuracy-first full SAGE
```

不要重新把生产主线改回：

- sampled SAGE v1；
- v1.1；
- A0；
- raw-coarse v2 selector；
- raw-coarse v3 selector。

这些路线已有失败/冻结记录。

它们可以未来作为独立 acceleration research，但不能阻塞 full SAGE 主线。

当前原则：

```text
validated full SAGE > unvalidated acceleration selector
```

---

## 11. Windows / MATLAB 执行治理

必须继承工程交接：

Codex sandbox 不应直接宣称自己可以完成正式 MATLAB production。

已验证正式链：

```text
immutable execution request
→ normal Windows user PowerShell 7 wrapper
→ identity check
→ MATLAB smoke
→ hash / lock / output preflight
→ Python executor
→ MATLAB run_nav_sage_pipeline
→ receipt / log
→ independent QA
```

当前正常用户身份：

```text
TJ-CHANNEL\Jing_
```

关键安全规则：

```text
new_only = true
resume_allowed = false
max_parallel_matlab = 1
```

不得为了速度自动并发 MATLAB。

---

## 12. 任务选择时不能用结果偏好

禁止：

> 只挑预计有多径的任务。

生产 selection 应尽量独立于最终 SAGE outcome。

可用依据：

- environment coverage；
- scene coverage；
- PRN/channel completeness；
- geometry planning context；
- input completeness；
- compute cost；
- current database gap。

不能用：

- “这个任务看起来会有 confirmed path”
- “这个能让结果更漂亮”

作为 production selection 标准。

---

## 13. zero-event 仍是合法数据

完整 pipeline 输出：

```text
confirmed events = 0
confirmed paths = 0
```

仍可以是合法结果。

必须记录为：

```text
zero confirmed multipath event under current Stage4 confirmation criterion
```

不得改写为：

- no physical multipath；
- LOS proven；
- no reflection；
- algorithm failed。

长期 occurrence modeling 最终需要这些 negative/zero denominator。

---

## 14. 主线数据库的正确层级

长期正式数据库建议至少分：

```text
scene table
measurement / PRN-track table
window table
event table
path table
channel-parameter table
statistical-model table
```

不要只做一张大 CSV 把所有东西重复 join。

推荐关系：

```text
scene
  └─ measurement track
       └─ window
            └─ event
                 └─ path
```

event-level：

- joint validity；
- confirmed event；
- source_event_maximum_coherence；
- event time；
- geometry/time link。

path-level：

- direct / multipath role；
- excess delay；
- Doppler offset；
- relative power；
- complex gain / phase if available；
- path provenance。

---

## 15. 主线数据库第一版必须解决的关键问题

### 15.1 Stable IDs

至少需要：

```text
scene_id
run_id
track_id
window_id
event_id
path_id
```

### 15.2 Provenance

每行可以追溯到：

```text
source Stage CSV/MAT
SAGE version/hash
request
execution
QA
```

### 15.3 Negative denominator

未来 occurrence probability 不能只看 confirmed events。

必须保留完整：

```text
valid Stage0 window denominator
```

并明确：

- screened but rejected；
- Stage2 high-order；
- Stage3 persistent；
- Stage4 rejected；
- Stage4 confirmed；
- not processed / inconclusive。

### 15.4 Geometry join

当前 window/event-level geometry 仍未完全生产化。

不能用 scene mean elevation 冒充 event elevation。

长期统计建模前必须完成：

```text
observation clock / TOW
↔ UTC / trajectory / GSV geometry
```

的可追溯 join。

---

## 16. LONG-TERM statistical modeling gate

本节的门禁针对 coverage-complete occurrence/physical-channel 扩展模型。它不再表示
canonical Phase-1 r3/r2 traditional model 尚未开始；r3/r2 已在有限 Stage3 population
和 support-aware hierarchy 下完成。

只有满足以下门禁，才进入正式统计模型：

```text
EVENT_PATH_DB_COMPLETE_ENOUGH = YES
NEGATIVE_DENOMINATOR_DEFINED = YES
GEOMETRY_ALIGNMENT_QA = PASS / SUFFICIENT
ENVIRONMENT_METADATA_COMPLETE = YES
PARAMETER_UNITS_FROZEN = YES
```

之后才能正式做：

### Occurrence

\[
P(\text{confirmed multipath}\mid\text{environment,elevation,...})
\]

### Path count

\[
P(N_\text{MP}\mid\text{confirmed multipath, conditions})
\]

### Excess delay

经验分布 / fitted distribution。

### Relative power

经验分布 / fitted distribution。

### Relative Doppler

signed / magnitude 两种语义分开。

### Mean excess delay

从 event/path power-weighted delay 派生。

### RMS delay spread

严格定义后计算。

### Doppler spread

按 event/window 或 path set 定义，不能混用。

### Ricean K-factor

只有 direct + multipath power 标度定义一致时计算。

### Lifetime / persistence

必须先冻结时间连续性定义和 window overlap 语义。

---

## 17. 分布拟合不要提前

正式建模时推荐：

1. empirical ECDF；
2. summary stats；
3. candidate distribution family；
4. parameter estimation；
5. AIC/BIC；
6. goodness-of-fit；
7. bootstrap uncertainty；
8. scene-level / PRN-level sensitivity；
9. avoid pseudo-replication。

候选 family 可包括：

- Lognormal；
- Gamma；
- Weibull；
- Exponential；
- Gaussian；
- Laplace；
- mixture；

但必须由数据决定，不提前锁死。

---

## 18. 环境与仰角统计

Phase-1 已完成有限支持的 Environment×Elevation traditional model；本节保留的
geometry/time-alignment要求仍适用于 coverage-complete occurrence、物理解释和未来扩展，
不能反向覆盖 r3/r2 的当前完成状态。

长期目标包括：

```text
Urban
Mountain/Valley
Highway/Open
Special Reflective
...
```

以及：

```text
LOW = 0–30°
MID = 30–60°
HIGH = 60–90°
```

但当前 Paper Handoff 已明确：

```text
window/event-level geometry alignment = PARTIAL
```

因此主线下一阶段必须把 geometry/time alignment 做成正式数据链，而不是继续用 scene-level planning elevation 代替。

---

## 19. 20.46 MHz 路线

当前：

```text
20.46 MHz = BLOCKED / NOT ADAPTED
```

不要直接把 20.46 MHz raw 喂给现有 10.23 MHz pipeline。

未来单独阶段：

```text
P20-1 audit hardcoded 10.23 MHz assumptions
P20-2 parameterize sample rate
P20-3 unit/numerical tests
P20-4 single 20.46 MHz pilot
P20-5 independent QA
P20-6 compare semantics with 10.23 MHz
P20-7 then expand
```

在 10.23 MHz 主线数据库明显推进前，不建议把 20.46 MHz 变成当前最高优先级。

---

## 20. 主线与暗室支线未来接口

暗室 branch 需要：

```text
base environment channel model
```

因此主线未来输出应支持：

```text
sample_environment_channel(environment, conditions, seed)
```

概念。

主线负责真实环境统计：

```text
Urban / Highway / Mountain / ...
```

暗室 branch 负责：

```text
weather overlay
+ channel realization
+ simulated IQ
+ RF playback
```

不要在主线里把 weather overlay 写死进基础环境模型。

---

## 21. 主线与未来论文的关系

主线最终更适合形成：

- 完整统计信道建模论文；
- 期刊论文；
- measurement dataset / channel model paper。

相比 VTC，未来主线论文可以重点展开：

- occurrence probability；
- environment/elevation dependence；
- delay spread；
- Doppler spread；
- K-factor；
- lifetime；
- mixed-effects / hierarchical modeling；
- model validation；
- synthetic channel generation。

Phase-1 bounded traditional model 已完成；当前主线应优先保持生产/数据库 provenance，
并把已完成结果同步到长期论文，不能再把统计建模写成尚未开始。

---

## 22. 当前优先级

主线建议固定为：

```text
P0 read the current authoritative handoffs and canonical Phase-1 r3/r2 status
P1 preserve the frozen full-SAGE production and QA record
P2 complete coverage-complete event/path database work only when separately authorized
P3 complete geometry/time alignment for future occurrence/generalization claims
P4 complete the standalone channel-parameter database and its QA
P5 synchronize bounded Phase-1 model results into the long-term manuscript
P6 separately decide on coverage-complete extensions or Phase-2 AI
P7 separately decide on 20.46 MHz adaptation
```

---

## 23. 新 Commander 接手后的下一步

新对话启动后，**不要立即跑 MATLAB**。

第一条 Codex 工作应该是只读恢复当前状态，特别核对 canonical Phase-1 r3/r2；
不得因为本文件中的历史队列段落自动创建或启动新的 SAGE task。

```text
GNSS Mainline Current-State Reconciliation
```

只读完成：

1. 当前 project structure；
2. current inventory；
3. current production manifest；
4. current production summary；
5. all existing 10.23 MHz SAGE output namespaces；
6. QA report mapping；
7. accepted / rejected / validation-only classification；
8. protected output list；
9. remaining 10.23 MHz planned tasks；
10. any currently running / locked task；
11. branch conflict check：
   - VTC
   - Darkroom
12. whether a separately authorized next mainline task is actually needed。

**不要执行 SAGE。**

报告交给 Commander。

Phase-1 当前已完成；Commander 再决定是否同步论文 Results 或授权新的独立路线：

```text
RESUME_MAINLINE_PRODUCTION = YES/NO
NEXT_TASK = ...
```

---

## 24. 新 Commander 第一个 Codex prompt 应包含的结构

未来不要只发：

> “继续主线。”

完整 prompt 至少包括：

```text
TASK
READ-ONLY SCOPE
SOURCE-OF-TRUTH
FILES TO INSPECT
ACCEPTED-STATE RULE
PROTECTED OUTPUTS
BRANCH CONFLICT CHECK
NO MATLAB / NO SAGE
OUTPUT TABLE
RECOMMENDED NEXT TASK
STOP
```

Commander 审核后，再单独发 production request preparation prompt。

---

## 25. 主线恢复后每个 task 的固定循环

```text
SELECT ONE TASK
↓
INPUT / OUTPUT PREFLIGHT
↓
IMMUTABLE REQUEST
↓
DRY-RUN
↓
COMMANDER REVIEW
↓
NORMAL USER WINDOWS EXECUTION
↓
MATLAB/SAGE
↓
INDEPENDENT QA
↓
UPDATE CURRENT ACCEPTED STATE
↓
INGEST TO EVENT/PATH DB
↓
SELECT NEXT TASK
```

不要自动串行下一项。

---

## 26. 不可自动执行的重大决策

Codex 不得自行：

- reopen 20.46 MHz；
- 修改 SAGE confirmed criterion；
- 修改 Stage semantics；
- 恢复 failed selector；
- 改 pipeline 算法；
- 删除旧 artifact；
- resume historical output；
- 并发多个 MATLAB；
- 改 database scientific definitions；
- 宣称 statistical model completed；
- 因某环境样本少就擅自补跑；
- 把 VTC / Darkroom task 混进 mainline production。

这些必须 Commander 批准。

---

## 27. Source-of-truth

### 工程事实

优先：

```text
actual current artifact / source code
→ GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md
```

### 科研语义 / 长期目标

优先：

```text
GNSS_SAGE_PAPER_HANDOFF_CURRENT.md
```

### 主线运行策略和分支职责

优先：

```text
GNSS_SAGE_MAINLINE_COMMANDER_HANDOFF_CURRENT.md
```

历史 QA / audit：

只作 provenance，不覆盖 current state。

---

## 28. 冲突处理

如果：

```text
Engineering Handoff
vs production summary
vs actual output
```

不一致：

1. 不猜；
2. 检查实际 artifact；
3. 检查 current QA；
4. 按 accepted-state rule 分类；
5. 报告冲突；
6. Commander 决定；
7. 再更新 current handoff。

不要静默篡改历史状态。

---

## 29. 当前状态 flags

```text
PROJECT_ROOT = E:\GNSS_Multipath_Project

MAINLINE_BRANCH = ACTIVE
VTC_BRANCH_OWNER = OTHER_CONVERSATION
DARKROOM_BRANCH_OWNER = OTHER_CONVERSATION

CURRENT_PIPELINE_RATE = 10.23 MHz
20_46_MHZ_READY = NO

SAGE_PIPELINE_VALIDATED = YES
FULL_SAGE_PRODUCTION_COMPLETE = NO

LATEST_KNOWN_ACCEPTED_PRODUCTION_COUNT = 26/67
ACCEPTED_STATE_RECONCILIATION_REQUIRED = NO (2026-08-25 QA reconciliation)

EVENT_PATH_DATABASE = VERSIONED AUDIT PARTITION INGESTED; coverage-complete database not complete
CHANNEL_PARAMETER_DATABASE = PLANNED / NOT COMPLETE
GEOMETRY_ALIGNMENT = PARTIAL
PHASE_1_TRADITIONAL_STATISTICAL_MODELING = COMPLETE_WITH_LIMITATIONS
PHASE_1_SCIENTIFIC_CLOSURE = PASS_WITH_LIMITATIONS
STATISTICAL_CHANNEL_MODEL = COMPLETE_WITH_LIMITATIONS (Phase-1 bounded; full/general model not complete)
DATABASE_RULES_V1 = FROZEN
DATABASE_DRY_RUN = PASS (57 batch + 7 reference)
FORMAL_EVENT_PATH_INGEST = COMPLETED_WITH_WARNINGS + INDEPENDENT_QA_PASS

OLD_VTC_STOP_EXISTS = YES
MAINLINE_RESUME_REQUIRES_CURRENT_STATE_RECONCILIATION = NO (reconciled 2026-08-25; Phase-1 closure 2026-08-30)

CURRENT_NEXT_ACTION =
    SYNCHRONIZE PHASE-1 RESULTS INTO LONG-TERM MANUSCRIPT OR HOLD; NO AUTOMATIC EXTENSION
```

---

## 30. 新 AI 启动口令

用户可以直接发：

> 请先读取《GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT》《GNSS_SAGE_PAPER_HANDOFF_CURRENT》和《GNSS_SAGE_MAINLINE_COMMANDER_HANDOFF_CURRENT》。你现在接任长期主线 Commander，Codex 是执行者。VTC 和暗室仿真都由其它对话负责，本对话只负责全数据 SAGE、event/path database、channel parameters 和后续统计信道建模。不要重新规划项目，也不要直接运行 SAGE。先恢复 current accepted state、原 production STOP、受保护结果和剩余任务，然后给我一个完整的 Codex 只读状态核对 prompt；核对完成后再决定是否恢复主线 production。

---

## 31. 新 AI 读完后应回复什么

不要大段复述历史。

只恢复：

```text
当前接管：长期 GNSS-SAGE 主线
VTC：其它对话
暗室：其它对话

当前主线目标：
full SAGE
→ event/path DB
→ channel-parameter DB
→ geometry alignment
→ statistical channel model

当前已知 accepted production：26/67（2026-08-25 independent batch QA）
当前 Phase-1 traditional statistical model：COMPLETE_WITH_LIMITATIONS
当前 Phase-1 scientific closure：PASS_WITH_LIMITATIONS
当前数据库：coverage-complete event/path 与独立 channel-parameter database 未完成
当前 geometry：PARTIAL
当前旧 STOP：存在，源于 VTC 阶段

唯一下一步：
同步 Phase-1 bounded model results 到长期论文 Results，或等待 Commander 指令；
不自动启动新的 MATLAB/SAGE。
```

然后直接给用户完整 Codex prompt。

---

## 32. 核心一句话

> **主线当前保留 accuracy-first full-SAGE、数据库和几何对齐路线；Phase-1 Stage3 Environment×Elevation 传统统计模型已经完成但有边界，下一步是论文 Results 同步或等待 Commander，而不是把它夸大为普适传播规律。**

## 33. Commander-authorized C1 G03 production update (2026-08-18)

Commander authorization `RESUME_LONG_TERM_MAINLINE_PRODUCTION=YES` was executed under the frozen manifest contract: `FROZEN_MANIFEST_ORIGINAL_ORDER`, `OVERRIDE_QUEUE_ORDER=NO`, `NEW_ONLY=true`, `RESUME_ALLOWED=false`, and `MAX_PARALLEL_MATLAB=1`.

The first queue task, `F1023_V120_D0121_P2/G03/ch2`, completed through the normal-user Windows wrapper. The immutable request is `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_c1_d0121p2_g03_20260818/execution_request.json` with SHA-256 `06ACB9FF1634C8B248ED6A46A63BF2E0BEE8934B61F8DE61CE56C11A56F5DC64`. The production source and manifest remain frozen and unchanged at SHA-256 `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C` and `77C20C0ED6C84FA0348DB429948A8BD4900B2E8D86A6D8843B159B9A7A35CF00`.

Execution evidence:

- normal identity `TJ-CHANNEL\\Jing_`, non-admin PowerShell `7.6.4`;
- MATLAB startup smoke marker and exit code `0`;
- Python executor exit code `0`, task exit code `0`, runtime `2073.646 s`;
- execution log `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260818T110255Z/batch_execution_log.csv`;
- independent QA `docs/10MHz_FULL_SAGE_PRODUCTION_C1_G03_QA_REPORT.md`.

G03 output is `scenes/F1023_V120_D0121_P2/sage_results/nav_sage_v2/G03/`, with 21/21 expected artifacts non-empty. Stage4 has 8/8 valid joint rows but zero rows satisfying the strict confirmed criterion and zero `is_multipath=1` paths. Classification is `PASS_NO_CONFIRMED_MULTIPATH`, not a physical LOS claim.

Current accepted-state and queue:

```text
ACCEPTED_PRODUCTION = 8/67
REJECTED_PROTECTED = 1 (historical A3 G16; unchanged)
ELIGIBLE_REMAINING = 58
NEXT_FROZEN_TASK = F1023_V120_D0121_P2/G24/ch2
QUEUE_POLICY = FROZEN_MANIFEST_ORIGINAL_ORDER
MAX_PARALLEL_MATLAB = 1
EVENT_PATH_DATABASE = PLANNED / NOT COMPLETE
```

The production summary CSV/report was refreshed as an artifact inventory. Accepted-state counting continues to exclude protected A3 G16 despite its retained scientific artifact and historical summary row. Paper handoff does not require a scientific update for this zero-confirmed canary; Engineering and Mainline Commander handoffs are updated here.

## 34. C1 stop point and independent unattended runner (2026-08-19)

G24 completed naturally after the stop instruction. Its independent QA is `docs/10MHz_FULL_SAGE_PRODUCTION_C1_G24_QA_REPORT.md`; classification is `PASS_NO_CONFIRMED_MULTIPATH` with `0` confirmed events and `0` confirmed paths. The current round therefore has `NEW_ACCEPTED=2` (G03, G24), `ACCEPTED=9/67`, `REJECTED_PROTECTED=1` (A3 G16), and `REMAINING_NOT_STARTED_ELIGIBLE=57`.

All frozen engineering hashes were rechecked after G24:

```text
PRODUCTION_SOURCE_SHA256 = BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C
MANIFEST_SHA256 = 77C20C0ED6C84FA0348DB429948A8BD4900B2E8D86A6D8843B159B9A7A35CF00
WRAPPER_SHA256 = DD8AFB1B3317BF920FE34474E3CEEDF06AC4580B2A13C21EA25F8365071143F3
EXECUTOR_SHA256 = BAB7A0422975CB05BCDA9A80A75C3577EB7F408A83F2720AF2F1E13372B08F1B
```

Codex-managed automatic continuation is now stopped. The remaining queue is delegated to:

```text
RUNNER = scripts/sage_pipeline/Run-UnattendedMainlineBatch.ps1
SCHEDULED_TASK = GNSS-SAGE-Unattended-Mainline-20260819
RUN_AS = TJ-CHANNEL\Jing_ (Interactive, Limited/non-admin)
RUN_DIRECTORY = dataset_generation_logs/batch_sage_unattended/run_20260819T004818Z
RUNNER_PID = 25520
CURRENT_TASK = F1023_V120_D0121_P2__G25
QUEUE_TOTAL = 57
QUEUE_POLICY = FROZEN_MANIFEST_ORIGINAL_ORDER
MAX_PARALLEL_MATLAB = 1
UNATTENDED_RUNNER_CREATED = YES
UNATTENDED_RUNNER_DRY_RUN = PASS
UNATTENDED_RUNNER_STARTED = YES
UNATTENDED_RUNNER_INDEPENDENT_FROM_CODEX = YES
FIRST_TASK_IDENTITY_VERIFIED = YES
CODEX_MANAGED_BATCH = STOPPED
```

The runner uses the existing immutable-request → Windows-wrapper → Python executor → MATLAB chain, waits for each wrapper return, applies only the minimum execution-integrity gate, and fail-stops on drift/collision/receipt/output/exit-code ambiguity. It does not start event database, elevation matching, or statistical modeling. After the frozen queue finishes, the runner leaves `BATCH_POST_RUN_QA_REQUIRED`; unified scientific QA must then classify all new tasks before any downstream ingest.

## 35. Mainline batch completion and accepted-state reconciliation (2026-08-25)

The frozen queue run `20260819T004818Z` has completed all 57 requests. The retained runner state is `completed_pending_batch_qa`, and the independent post-run QA is now complete in `docs/10MHz_FULL_SAGE_UNATTENDED_BATCH_20260819_QA_REPORT.md`.

```text
REQUESTS = 57
RECEIPTS = 57
TASK_LEVEL_QA = 57/57 ACCEPTED, 0 REJECTED
A_PIPELINE_VALIDATION = 40 (VALIDATED, not formal accepted production)
B_MAIN_PRODUCTION = 14 (accepted)
C_LONG_RUNNING = 3 (accepted)
FORMAL_ACCEPTED_PRODUCTION = 26/67
REJECTED_PROTECTED = 1 (historical A3 G16)
NOT_STARTED_ELIGIBLE = 0
QUEUE_POLICY = FROZEN_MANIFEST_ORIGINAL_ORDER
MAX_PARALLEL_MATLAB = 1
```

The new batch aggregate is Stage0/Stage1 `162864/162864` windows, Stage2 `5639` selected windows, Stage3 `420` reliable centers, Stage4 `284` joint-valid rows, and strict confirmed `88` events / `93` paths. Twenty-six tasks are valid zero-confirmed-event outputs under the fixed Stage4 criterion.

Authoritative monitoring was refreshed at:

- `dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv` — 77 rows, 57 new rows `completed/PASS`;
- `dataset_generation_logs/production_monitoring_10MHz/production_summary_report.md`;
- `docs/10MHz_FULL_SAGE_UNATTENDED_BATCH_20260819_QA_REPORT.md` — SHA-256 `11aa8f99f7e0245cd074ad31e1229d5c3cf803d1d071e5d0b64162a68a7dadf8`.

The production source, wrapper, executor, manifest and inventory hashes remain frozen. The database rules are now frozen and the read-only dry-run validator has passed; no event/path database facts, geometry join, channel-parameter derivation or statistical modeling has started. Formal ingest still requires a separate Commander decision. Do not launch another MATLAB task automatically.

## 36. Database rules freeze and dry-run gate (2026-08-25)

The v1 schema/enum/label/derivation manifests are frozen under `dataset/multipath_event_database/v1/_schema/`. The reproducible validator is `scripts/event_database/validate_sage_database_dry_run.py`; evidence is `dataset_generation_logs/multipath_event_database_dry_run_20260825/database_dry_run_report.md` plus `database_dry_run_result.json`.

```text
DATABASE_RULES_V1 = FROZEN
DATABASE_DRY_RUN = PASS (current batch 57/57; reference fixture 7/7)
DRY_RUN_WARNING = legacy G06 run_context.json absent; adapter warning retained
FORMAL_DATABASE_INGEST = COMPLETED_WITH_WARNINGS (Section 37)
DATABASE_FACT_TABLES = NOT WRITTEN
EVENT_GEOMETRY_CONTEXT = DEFERRED_UNAVAILABLE
CHANNEL_PARAMETER_DERIVATION = NOT STARTED
STATISTICAL_CHANNEL_MODEL = NOT STARTED
NEXT_DECISION_REQUIRED = MODELING-READINESS QA COMPLETE; AUTHORIZE GEOMETRY/SCENE-CONTEXT QA OR HOLD
```

The dry-run reproduced current-batch strict confirmed events/paths `88/93` and reference regression `8/11`. It read no raw IQ and did not start MATLAB/SAGE. The subsequent authorized event/path audit ingest is recorded in Section 37; no channel-parameter or statistical-model tables were created. Paper Handoff remains unchanged because no paper fact, figure, table or claim changed.

## 37. Formal event/path audit ingest and modeling gate (2026-08-25)

The explicitly authorized ingest created `dataset/multipath_event_database/v1/partitions/ingestion_id=ingestion_20260825_event_path_v1/` and passed independent QA. It contains 64 unique runs, 308 Stage4 event rows, 412 Stage4 path rows and strict confirmed `96/104` events/paths. G06 legacy is retained for audit but excluded from modeling-ready input because `run_context.json` is missing; no source artifact was deleted.

Event-time geometry remains deferred: all event context rows keep UTC/elevation/azimuth null, and five run/PRN geometry-summary warnings are recorded. No channel parameters or statistical modeling has started. Modeling-readiness QA is now complete and blocked; the next gate is geometry/scene-context QA, with G06 excluded unless a future independently verified legacy adapter is authorized.

## 38. Modeling-readiness QA gate (2026-08-25)

Modeling-readiness QA is complete but **BLOCKED**. The partition has 64 runs, 308 events and 412 paths, but verified event-time geometry is `0/308`, verified time alignment is `0/13`, and scene context is `not_annotated` for all 13 scenes. Five geometry summary PRN-missing warnings remain explicit. G06 is retained for audit and excluded from modeling-ready input because its legacy `run_context.json` is missing. No channel parameters or statistical model were computed.

Next decision: authorize geometry/time-alignment and scene-context QA work, or hold. Statistical modeling remains blocked.

## 39. Current Phase-1 Stage3 academic statistical model status (2026-08-31)

This section supersedes the Phase-1 modeling status stated in Sections 35–38;
those sections remain preserved as historical batch, ingest, and modeling-gate
records.

- The canonical Stage3 model is `dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3/`, with report `docs/ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_R3_REPORT.md`. The canonical scientific closure is `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/`, with report `docs/PHASE1_TRADITIONAL_CHANNEL_MODELING_SCIENTIFIC_CLOSURE.md`.
- Both canonical namespaces passed independent QA. Model manifest SHA-256 is `61c4b3aa171b6a59d17607394770b684251d656eeb19813ca13ebed2454b1782`; r3 QA SHA-256 is `916304ca04e5e84eb8e3349d9e072b1b36489a8aa0c95e34110b91f2012cfbf5`; closure manifest SHA-256 is `45282b4eb5f86e52f4cd39f9b94f04c1596b645cae3d0b6420a089717f429d52`; closure QA SHA-256 is `031f66441dbbfe0a9f5e8e98bdad863da7fc37b7514734649ba85561503480f4`.
- The frozen production provenance still matches: source/pipeline `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`, wrapper `dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3`, executor `bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b`, and production manifest `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`.
- The Stage3 academic population is 783 observations, 445 reliable centers, 366 conservative algorithm-level tracks, 716 elevation-ready observations, 50 runs, 12 scenes, and 18 PRNs. The primary statistical unit is `WEIGHTED_OBSERVATION` with weight `1 / algorithm_track_size`.
- The hierarchy is `Global → Environment → Environment×Elevation`. Marginal families are delay `Lognormal`, signed relative Doppler `Normal`, and relative power `Normal`. Gaussian Copula dependence is used only at global / environment / support-gated cell levels; there is no claim of independently fitted covariance for all 12 cells.
- Robustness uses scene-block bootstrap, run-level sensitivity, and grouped LOSO. Support remains 5 `DATA_SUPPORTED`, 4 `SPARSE_PARTIAL_POOLING`, 2 `PRIOR_DOMINANT`, and 1 `NO_DIRECT_SUPPORT`; Highway/Open–LOW has no direct support and receives no synthetic fill.
- Stage4 strict-confirmed paths are a high-confidence selection-sensitivity subset only. `STAGE4_SENSITIVITY_RESULT = MATERIAL_DIFFERENCE`; Stage4 is not ground truth. Environment effect and elevation effect are `INCONCLUSIVE`, while environment×elevation interaction is `PARTIAL`.
- `PHASE_1_TRADITIONAL_STATISTICAL_MODELING = COMPLETE_WITH_LIMITATIONS` and `PHASE_1_SCIENTIFIC_CLOSURE = PASS_WITH_LIMITATIONS`. Ricean K remains not identifiable; persistence is algorithm-observed persistence only, not physical reflector lifetime. Long-term manuscript Results synchronization is pending/in progress. No automatic MATLAB/SAGE continuation is authorized by this documentation update.
