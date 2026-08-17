# GNSS SAGE ChatGPT Conversation Handoff — 2026-08-13

> **用途**：这是本轮 ChatGPT 对话的交接文档。  
> 它不是工程状态唯一来源，也不是论文状态唯一来源。  
> 新接手 AI 必须联合阅读以下三份文档后继续工作：
>
> 1. `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` — 工程状态唯一来源  
> 2. `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` — 论文状态唯一来源  
> 3. **本文件** — 当前对话中的决策、工作节奏、交互约定、正在执行任务和近期上下文
>
> 论文资产导航另见：`docs/PAPER_WORKSPACE_INDEX.md`

---

## 1. 项目核心目标

项目根目录：

`E:\GNSS_Multipath_Project`

当前论文/研究主线已经明确为：

**SAGE-based path extraction and statistical GNSS multipath channel modeling**

不是把 SAGE 算法本身作为最终研究目标，而是：

```text
raw GNSS IQ
  -> GNSS-SDR tracking/navigation support
  -> NAV-aided full SAGE path extraction
  -> confirmed multipath event/path data
  -> path-level delay / Doppler / power / phase
  -> classical channel parameters
  -> environment/elevation-conditioned statistical GNSS multipath channel model
```

当前生产范围严格限定为：

**10.23 MHz**

20.46 MHz 当前不进入 production，不要顺手处理。

---

## 2. 当前总路线：accuracy-first full SAGE

此前为了降低 full SAGE 计算成本，做过 raw-coarse / sampling / v3 selector 探索。

v3.0 最终 posterior gold replay 失败：

- Stage4 confirmed center recall：`2/4 = 50%`
- confirmed center ±2：`12/16 = 75%`
- Stage3 reliable-center ±2：`25/44 = 56.8182%`

主要 miss attribution：

- `secondary_doppler_inconsistent`
- `cross_scale_disagreement`

因此：

- v3.0 = `Implemented + QA Validated + Posterior Failed/Frozen`
- v3.1 暂停
- v3 不再作为 production blocker
- 正式论文数据生产改为 **accuracy-first full Stage0–Stage4 SAGE**

当前生产链：

```text
raw IQ
 -> GNSS-SDR outputs
 -> Stage0
 -> Stage1
 -> Stage2
 -> Stage3
 -> Stage4
 -> confirmed event/path database
 -> channel parameter database
 -> statistical model
```

不要继续优化 v3，除非用户未来明确重新开启该方向。

---

## 3. 10.23 MHz 数据规模与生产规划

10.23 MHz production inventory：

- scenes：`13`
- scene–PRN inventory tasks：`83`
- production manifest tasks：`67`
- 已有/历史完成任务：`11`
- multi-channel blocked：`5`
- 正式 production manifest SHA-256：

`77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`

正式 manifest：

`dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json`

Batch 规划：

- Batch A：48
- Batch B：14
- Batch C：5

5 个 multi-channel blocked task 不得自动选择 channel：

- `F1023_V120_D0121_P2/G06`: ch6、ch9
- `F1023_V120_D0121_P2/G12`: ch5、ch11
- `F1023_V120_D0121_P2/G19`: ch0、ch1、ch3
- `F1023_V120_D0121_P2/G29`: ch3、ch10
- `F1023_V70_D0120_P9/G23`: ch3、ch10

这些 blocked task 未来需要人工科学依据，不得猜测。

---

## 4. 正式 production 已完成任务

### 4.1 Production A1 — G11

Task：

`F1023_V70_D0117_P4/G11/ch2/10.23MHz`

QA：

`PASS`

正式输出：

`scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G11/`

关键统计：

- Stage0 NAV symbols：895
- Stage0 40 ms windows：893
- Stage1 scanned / selected：893 / 110
- Stage2 evaluations：440
- Stage2 L1/L2/L3/L4：36 / 16 / 17 / 41
- Stage3 reliable centers：8
- Stage4 joint rows：8
- Stage4 joint_valid：8/8
- confirmed events：3
- confirmed multipath paths：3
- runtime：5078.854 s（约 84.65 min）

Confirmed center windows：

`526`, `72`, `73`

### 4.2 Production A2 — G18

Task：

`F1023_V70_D0120_P1/G18/ch2/10.23MHz`

QA：

`PASS`

正式输出：

`scenes/F1023_V70_D0120_P1/sage_results/nav_sage_v2/G18/`

关键统计：

- Stage0 NAV symbols：2611
- Stage0 windows：2609
- Stage1 scanned / selected：2609 / 115
- Stage2 evaluations：460
- Stage2 L1/L2/L3/L4：41 / 26 / 30 / 18
- Stage3 reliable centers：9
- Stage4 joint rows：8
- Stage4 joint_valid：8/8
- confirmed events：0
- confirmed multipath paths：0
- runtime：7737.82 s（约 128.96 min）

这是合法的 **zero-confirmed-event production output**。

禁止把它写成“G18没有多径”或“科学LOS结论”。

正确表述应类似：

> under the current confirmation criterion, this task produced zero confirmed multipath events.

当前正式 production 完成数：

**2 / 67 QA PASS**

---

## 5. Production Summary 工具已建立

只读生产统计汇总工具已完成：

`E:\GNSS_Multipath_Project\scripts\sage_pipeline\audit_10MHz_production_summary.py`

输出：

- `dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv`
- `dataset_generation_logs/production_monitoring_10MHz/production_summary_report.md`

职责：

- 记录 production task execution / QA / runtime
- Stage0–Stage4 counts
- confirmed events / paths
- provenance/status
- 支持后续 67-task 生产监控

明确：

**它不是论文 channel parameter database。**

它不负责：

- RMS delay spread
- Doppler spread
- K-factor
- PDP统计建模

固定 production 流程应为：

```text
Execution
 -> independent QA
 -> Production Summary refresh
 -> Engineering Handoff update
 -> 判断是否产生 paper-level scientific fact / asset
```

---

## 6. 当前 Batch A representative task

Batch A 候选只读审计完成。

Top 5：

1. `F1023_V70_D0120_P5/G16/ch1` — Urban
2. `F1023_V70_D0120_P8/G16/ch4` — Urban
3. `F1023_V80_D0117_P8/G12/ch4` — Highway/Open
4. `F1023_v90_D0117_P7/G11/ch6` — Mountain/Valley
5. `F1023_V70_D0117_P4/G12/ch4` — Mountain/Valley

人工已确认代表任务：

**`F1023_V70_D0120_P5/G16/ch1/10.23MHz`**

选择目的：

- Batch A 连续生产前 representative validation
- 典型 Urban
- unique single channel
- 输入完整
- 非 blocked
- 非极端特殊反射场景

---

## 7. G16 当前正在正常执行

Immutable request：

`E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\production_10mhz_a3_d0120p5_g16_20260813\execution_request.json`

Request SHA-256：

`629e22444baa3ae7cede6584ec486312cceb7be541e443eab4c30d53dfa8a094`

Preflight：

`PASS — REQUEST_READY_FOR_HUMAN_EXECUTION`

已确认：

- G16 → ch1 唯一映射
- 10.23 MHz
- 输入完整
- target output namespace 不存在
- global lock 不存在
- new_only=true
- resume_allowed=false
- 不影响 G11 / G18 / reference / legacy

**当前状态：用户已在正常 Windows PowerShell 中启动 G16，正在执行中。**

**运行态只读审计（2026-08-13）：** preflight 完成后，已观察到本次运行的 wrapper receipt namespace
`dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_production_10mhz_a3_d0120p5_g16_20260813_20260813T073458826Z/`、executor run namespace
`dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T073512Z/`、其中的task lock
`dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T073512Z/locks/F1023_V70_D0120_P5__G16__ch1__nav_sage_v2.lock`，以及目标目录
`scenes/F1023_V70_D0120_P5/sage_results/nav_sage_v2/G16` 已初始化。这些证据只表示任务已进入运行态，不表示 Stage0–Stage4 完成、receipt 成功或 QA PASS；`2/67` 完成计数保持不变。

在收到成功完成 receipt 并完成独立 post-run QA 前，不得删除、移动、覆盖或 resume 这些运行中/部分输出，不得启动第二个 production task。

因此新接手 AI 当前第一件工程事不是再创建 request，也不是启动新任务，而是：

> 等 G16 正常完成后，执行 independent post-run QA。

但不要承诺后台等待；用户会把完成结果主动发回来。

---

## 8. 极重要：执行命令路径规则

本轮对话中曾两次发生 AI 把真实 request 目录名“脑补拆层级”的错误。

例如真实目录：

`production_10mhz_a3_d0120p5_g16_20260813`

绝不能自行改写成：

`production_10mhz\a3_d0120p5_g16_20260813`

硬规则：

1. PowerShell 命令中的路径必须逐字符复制 Codex/实际 artifact 提供的完整路径。
2. 不得根据命名规律重新拼路径。
3. 若有任何不确定，先：
   `Test-Path "<完整路径>"`
4. 若第一次路径失败，必须回到原始 artifact 路径重新核对，不能在错误路径上继续猜。
5. 如果上下文太复杂，允许要求用户让 Codex 输出目录树/manifest/request路径梳理；不要凭记忆继续拼。

这是用户明确要求长期遵守的规则。

---

## 9. G16 完成后的工程顺序

已确定顺序：

```text
G16 execution
 -> G16 independent QA
 -> Production Summary refresh
 -> Engineering Handoff update
 -> representative validation conclusion
 -> 若 PASS，进入 Batch A continuous production planning/execution
```

G16 QA 应至少检查：

- execution receipt
- MATLAB / Python / task exit code
- output namespace
- 21 expected Stage0–Stage4 files
- run_context scene / PRN / channel / rate
- Stage0 NAV symbols / windows
- Stage1 scanned / selected
- Stage2 evaluations + L1/L2/L3/L4
- Stage3 reliable centers
- Stage4 joint rows / joint_valid
- confirmed events / paths
- runtime
- hash/provenance
- new_only isolation

Confirmed criterion严格保持：

```text
joint_valid == 1
AND joint_multipath_count > 0
AND stage4_joint_paths.csv contains matching is_multipath == 1 path
```

Stage2 L>=2 或 Stage3 reliable 都不能直接等于 confirmed multipath。

如果 G16 representative QA PASS：

可判断是否具备开启 **Batch A continuous production** 的工程条件。

不要自动运行下一个任务，仍需按项目安全链执行。

---

## 10. Scene Metadata 已建立（仅10.23 MHz）

正式文件：

`dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv`

13/13 scene 已覆盖。

环境分类：

- Urban：6
- Mountain/Valley：3
- Highway/Open：2
- Special Reflective：2

速度分布：

- 50 km/h：1
- 70 km/h：9
- 80 km/h：1
- 90 km/h：1
- 120 km/h：1

人工确认的 13 个 scene：

1. `F1023_V120_D0121_P2` — 高速公路
2. `F1023_V70_D0117_P2` — 河谷地区公路
3. `F1023_V70_D0117_P4` — 上山公路
4. `F1023_V70_D0120_P1` — 法兰克福高楼城市市内
5. `F1023_V70_D0120_P5` — 普通城区道路（房子不高）
6. `F1023_V70_D0120_P7` — 普通城区道路，电车轨道旁，有电车经过
7. `F1023_V70_D0120_P8` — 普通城区道路
8. `F1023_V70_D0120_P9` — 宽阔水面的大桥
9. `F1023_V70_D0122_P1` — 普通城区街道
10. `F1023_V70_D0122_P2` — 火车开过、信号塔附近、很多树的城市道路
11. `F1023_V80_D0117_P8` — 超开阔道路
12. `F1023_v50_D0127_P1` — 下雨天城区道路
13. `F1023_v90_D0117_P7` — 盘山公路（比较开阔）

一级环境分类固定为当前四类用于草稿和数据库候选分析，但最终统计可根据样本表现调整。

---

## 11. 论文当前定位与文件体系

论文状态唯一来源：

`docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

论文资产导航：

`docs/PAPER_WORKSPACE_INDEX.md`

论文草稿：

`docs/paper_draft/`

当前管理硬规则：

论文侧不再创建重复状态源，例如：

- `PAPER_PLAN2.md`
- `PAPER_STATUS_NEW.md`
- `PAPER_STATUS_FINAL.md`
- `DATABASE_SCHEMA_NEW.md`
- `DATABASE_DESIGN_FINAL_FINAL.md`

除非已有结构确实无法容纳且用户明确需要。

论文侧核心管理体系固定为：

```text
docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md
        ↓
docs/PAPER_WORKSPACE_INDEX.md
        ↓
docs/paper_draft/
        ↓
docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md
```

新论文内容文件可以在 `paper_draft/` 下按明确唯一职责增加，但不能制造新的平行状态源。

---

## 12. 论文草稿当前状态

已建立：

`docs/paper_draft/manuscript_outline.md`

章节：

- `sections/01_Introduction.md`
- `sections/02_Related_Work.md`
- `sections/03_Methodology.md`
- `sections/04_Experimental_Setup.md`
- `sections/05_Pipeline_Validation.md`
- `sections/06_Results_PLACEHOLDER.md`
- `sections/07_Conclusion.md`

Introduction 已写入中文科研草稿。

Introduction 的科学叙事已人工确认：

```text
动态车辆 GNSS 多径问题
 -> 传统 receiver-level indicators 只能描述性能影响
 -> 需要 path-level propagation characterization
 -> SAGE 作为高分辨率路径提取工具
 -> 由 path parameters 推导经典 channel parameters
 -> 建立 environment-conditioned statistical GNSS multipath channel model
```

重要定位：

**SAGE 是工具，不是论文最终目标。**

---

## 13. 数据库 schema 当前状态

论文数据库 schema：

`docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md`

当前仅设计，真实数据库未建立。

四层：

### Layer 1 — Scene Metadata
已完成。

### Layer 2 — SAGE Path Database
Planned / Not started.

一条传播路径一行，保存：

- scene_id
- PRN
- event/window
- path_id
- delay
- Doppler
- amplitude/power
- phase
- provenance / confirmation semantics

### Layer 3 — Channel Parameter Database
Planned / Not started.

一条 channel observation window / valid observation 一行。

### Layer 4 — Statistical Model Database
Planned / Not started.

保存环境/仰角条件下统计模型结果。

项目里还存在：

`docs/MULTIPATH_EVENT_DATABASE_DESIGN.md`

其职责偏 normalized run/window/candidate/confirmed-event/path ingestion 与 QA。

未来实际数据库实现时应区分：

```text
Event Database
 -> Confirmed Path Database
 -> Channel Parameter Database
 -> Statistical Model
```

不要把生产汇总表当科研数据库。

---

## 14. 当前 channel parameter candidate pool

当前策略：

**先完整候选，production 数据完成后再根据统计稳定性、物理解释性和模型价值筛选。**

核心候选：

- Power Delay Profile (PDP)
- RMS delay spread
- Doppler spread
- Ricean K-factor

扩展候选：

- Number of paths
- Mean excess delay
- Path power statistics
- Path lifetime / temporal stability

最终哪个参数表现不好，可以从论文最终模型中删掉。

当前草稿和 schema 应先保留这些候选。

后续还要考虑：

- multipath occurrence probability
- elevation conditioning
- environment conditioning
- possibly speed as auxiliary variable

仰角分组仍为：

- LOW 0–30°
- MID 30–60°
- HIGH 60–90°

但 Introduction 不必过度展开仰角分组，主要放 Methodology / Results。

---

## 15. Documentation Update Policy（硬规则）

Codex 已将统一 Documentation Update Policy 写入：

- Engineering handoff
- Paper handoff
- Paper Workspace Index

必须遵守。

### Engineering Handoff

记录：

- 工程流程状态变化
- production / batch进度
- QA PASS/FAIL
- 新工程工具
- 新工程能力
- 路线调整

### Paper Handoff

仅在产生科研/论文事实时更新：

- 论文路线/贡献改变
- schema/model设计改变
- 新论文可用 validation / dataset fact
- 论文章节状态变化
- statistical result 产生

普通工程动作不自动更新 Paper handoff。

### PAPER_WORKSPACE_INDEX

只有论文资产新增/删除/结构变化时更新。

### Production Summary

每个正式 production task 在 QA 后必须刷新：

- execution status
- QA status
- runtime
- Stage counts
- confirmed events / paths

### 标准同步顺序

```text
Execution
 -> QA
 -> Production Summary
 -> Engineering Handoff
 -> 判断是否需要 Paper Handoff
 -> 判断是否需要 PAPER_WORKSPACE_INDEX
```

禁止创建重复状态文件。

禁止把工程事实直接写成论文科学结论。

---

## 16. 用户的工作方式与交互要求

### 16.1 涉及 Codex 下一步时必须给提示词

用户明确要求：

> 只要回答里提到“让 Codex 做什么”，就必须同时给一段可直接复制给 Codex 的完整提示词。

不要只描述任务。

### 16.2 执行命令必须谨慎

PowerShell命令必须严格使用真实 artifact 路径，不自行拼接。

### 16.3 用户希望随时看到双轨进度

用户可能随时问：

- 工程进度
- 论文进度
- 下一步是什么

回答应默认同时从 Engineering Track 和 Paper Track 展示。

### 16.4 当前工程优先级

主线是：

> 尽快生产 10.23 MHz 论文数据，然后建立数据库与统计模型，开始文章 Results。

不要重新陷入不必要的算法优化。

---

## 17. 当前工程侧流程进度

```text
[Completed] 10.23 MHz inventory / manifest / production plan
[Completed] Windows immutable request + normal-user wrapper + QA chain
[Completed] Production A1 G11 — QA PASS
[Completed] Production A2 G18 — QA PASS
[Completed] Read-only Production Summary Tool
[Completed] Batch A representative candidate audit
[Completed] Representative task selection: D0120_P5/G16/ch1
[Completed] G16 immutable request + preflight
[RUNNING]   G16 representative full SAGE execution
[Next]      G16 independent QA
[Next]      refresh production summary
[Next]      update engineering handoff
[Next]      representative readiness decision
[Next]      if PASS -> Batch A continuous production
[Later]     Batch B
[Later]     Batch C long tasks
[Later]     path/event database
[Later]     channel parameter database
[Later]     statistical modeling
```

---

## 18. 当前论文侧流程进度

```text
[Completed] Paper handoff
[Completed] Paper workspace index
[Completed] manuscript outline
[Completed] 10.23 MHz scene metadata
[Completed] database schema design
[Completed] Introduction Chinese logic/draft
[Completed] candidate channel parameter pool planning
[Not started / drafting next] Related Work
[Not started / drafting next] Methodology
[Not started / drafting next] Experimental Setup full prose
[Partial] Pipeline Validation (facts exist, prose still developing)
[Blocked on data] Results
[Not started] Real path database
[Not started] Real channel parameter database
[Not started] Statistical model
```

工程和论文可以并行：

```text
Engineering:
G16 -> QA -> Batch A production

Paper:
Introduction refinement -> Related Work -> Methodology -> Experimental Setup
```

但 production 数据仍是项目主线。

---

## 19. 新接手 AI 的读取顺序

没有上下文的 AI 应按下面顺序工作：

### 第一步
读：

`docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`

确认工程事实、pipeline、production状态、hash/provenance、安全门禁。

### 第二步
读：

`docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

确认论文主题、贡献、当前可写内容、未完成结果、统计建模路线。

### 第三步
读：

本 ChatGPT handoff。

理解：

- 当前正在跑 G16
- 近期决策历史
- v3为何被冻结
- 用户的交互习惯
- PowerShell路径规则
- Documentation Update Policy
- 工程/论文双轨的下一步顺序

### 第四步
如涉及论文文件，读：

`docs/PAPER_WORKSPACE_INDEX.md`

### 第五步
如涉及数据库，读：

`docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md`

不要只凭聊天记忆猜当前状态。

---

## 20. 当前最安全的下一动作

目前 G16 正在用户本机执行。

**不要创建第二个 execution request，不要启动第二个 SAGE task。**

用户下一步大概率会发送：

`WINDOWS_TASK_COMPLETED execution_log=...`

或 G16执行结果。

收到后：

1. 先做独立 G16 post-run QA；
2. QA通过后刷新 production summary；
3. 更新 Engineering handoff；
4. 判断 G16 是否足以作为 Batch A representative validation PASS；
5. 如产生新的论文资产/论文可用 validation fact，再按 Documentation Update Policy 判断是否更新 Paper handoff / Workspace Index；
6. 只有上述步骤完成后，再讨论 Batch A continuous production。

---

## 21. 不要忘记的科学语义

- Stage2 `L>=2` ≠ confirmed multipath
- Stage3 reliable ≠ confirmed multipath
- Stage4 只有严格 criterion 才是 confirmed event/path
- zero-event production output 是合法结果
- 未扫描 / 未晋级不能写成 LOS
- 工程 `zero confirmed event` 不能直接升级成科学“无多径”
- raw-coarse / sampling / v3 不进入 production data
- 20.46 MHz 当前不处理
- 数据库尚未真正建立
- statistical model 尚未建立
- 不得提前填 Results 数字或结论

---

## 22. 近期论文 Introduction 核心表述

当前认可的主旨：

> 动态车辆 GNSS 环境中的多径不应只被视作一个定位误差项，而应被视作具有时间变化、环境依赖和卫星几何依赖的传播信道问题。本文利用 SAGE 作为高分辨率路径提取工具，从真实 10.23 MHz GNSS 原始 IQ 数据中获得路径级 delay / Doppler / power / phase，并进一步推导 PDP、RMS delay spread、Doppler spread、Ricean K-factor、path count、mean excess delay、path power statistics 和 path lifetime 等候选统计特征，以建立环境相关的 GNSS 多径统计信道模型。

最终参数池允许在真实多场景结果出来后删减。

---

## 23. 对话交接结论

当前项目已经完成：

- 方法验证
- production infrastructure
- two formal production tasks
- production monitoring tool
- scene metadata
- paper management framework
- database schema design
- Introduction research logic

当前正在：

**Batch A representative G16 full SAGE execution**

下一阶段目标：

**验证 G16 -> 开启 Batch A continuous production -> 累积 10.23 MHz path/event data -> 建立真实数据库 -> channel parameter derivation -> environment/elevation-conditioned statistical modeling -> paper Results**
