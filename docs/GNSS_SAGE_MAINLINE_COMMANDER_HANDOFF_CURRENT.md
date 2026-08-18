# GNSS-SAGE 主线运行 Commander 交接手册

**项目根目录：** `E:\GNSS_Multipath_Project`  
**支线身份：** Long-Term Mainline / 主线运行  
**本文件职责：** 让一个完全没有聊天上下文的新 AI，在读取工程交接、论文交接和本文件后，直接接任长期主线 Commander，继续推进“全数据 SAGE → event/path database → channel-parameter database → environment/elevation-conditioned statistical channel modeling”。  
**当前日期：** 2026-08-17  
**重要：** VTC 写作和暗室信道仿真已拆到其它对话；本对话只负责长期主线运行。  

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

当前工程和论文交接都明确：完整 event/path database、channel-parameter database 和 statistical model 尚未完成。

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

但当前主线对话优先**生产和数据库**，不要过早进入新论文写作。

---

## 22. 当前优先级

主线建议固定为：

```text
P0 current-state reconciliation
P1 resume authorization / queue freeze
P2 continue 10.23 MHz full SAGE one task at a time
P3 independent QA after every task
P4 build actual event/path database
P5 geometry/time alignment
P6 channel-parameter derivation
P7 environment/elevation statistical model
P8 20.46 MHz adaptation
P9 model validation / simulation interface
```

---

## 23. 新 Commander 接手后的唯一下一步

新对话启动后，**不要立即跑 MATLAB**。

第一条 Codex 工作应该是：

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
12. proposed next single mainline task。

**不要执行 SAGE。**

报告交给 Commander。

Commander 再决定：

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

LATEST_KNOWN_ACCEPTED_PRODUCTION_COUNT = 7/67
ACCEPTED_STATE_RECONCILIATION_REQUIRED = YES

EVENT_PATH_DATABASE = PLANNED / NOT COMPLETE
CHANNEL_PARAMETER_DATABASE = PLANNED / NOT COMPLETE
GEOMETRY_ALIGNMENT = PARTIAL
STATISTICAL_CHANNEL_MODEL = NOT STARTED

OLD_VTC_STOP_EXISTS = YES
MAINLINE_RESUME_REQUIRES_CURRENT_STATE_RECONCILIATION = YES

CURRENT_NEXT_ACTION =
    READ-ONLY MAINLINE CURRENT-STATE RECONCILIATION
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

当前已知 accepted production：7/67（需只读重核）
当前 20.46 MHz：未放行
当前数据库：未完成
当前 geometry：PARTIAL
当前旧 STOP：存在，源于 VTC 阶段

唯一下一步：
先让 Codex 做只读 current-state reconciliation，
不运行 MATLAB/SAGE。
```

然后直接给用户完整 Codex prompt。

---

## 32. 核心一句话

> **主线现在的任务不是继续写 VTC，也不是做雨天暗室 demo，而是恢复长期 accuracy-first full-SAGE 数据生产，建立 coverage-complete event/path database，完成 geometry/time alignment，再进入 environment/elevation-conditioned GNSS multipath statistical channel modeling。**
