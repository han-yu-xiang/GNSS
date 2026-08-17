# 5 Pipeline Validation

## 5.1 Validation objectives

本章验证的对象不是单独的 SAGE 优化器是否收敛，而是从真实 GNSS 原始 IQ、导航辅助预处理到多径路径确认的完整处理流程。验证重点包括四个方面：

1. **层级路径确认的有效性**：检查 Stage0–Stage4 是否按照预定义的证据层级工作，并明确 candidate、reliable candidate 与 confirmed multipath path 的边界；
2. **跨任务可复现性**：检查不同 scene、PRN 和 tracking channel 是否能够在相同 pipeline 语义下生成一致的输入输出结构；
3. **长记录可扩展性**：使用长时间动态 GNSS 记录观察 full SAGE 在窗口规模显著增加时的可执行性和计算负担；
4. **生产执行可靠性**：检查 immutable request、输入门禁、正常 Windows 用户执行链、MATLAB/Python 状态、输出隔离和独立 QA 是否形成闭环。

在这一框架中，Stage2 的模型阶数或模型选择只能表示窗口级拟合证据，Stage3 的 reliable center 只能表示时间持续性候选；二者都不是最终 confirmed multipath。当前论文采用的最终确认条件由 Stage4 joint 结果和有效路径表共同定义。

## 5.2 Reference scene multi-PRN validation

Reference scene `F1023_V70_D0117_P2` 用于在固定采集场景内检验多 PRN 条件下的 pipeline 行为。七个 PRN 共享同一 scene 级数据来源，但其 Stage1–Stage4 漏斗并不相同，因此可以同时观察 LOS-like/control、候选被拒绝和 Stage4 confirmed sample 三类结果。该 scene 是方法验证基线，不是最终统计数据集，也不能代表所有环境条件。

下表中的“Stage2 candidate windows”指进入 Stage2 处理的候选窗口数；“Stage4 confirmed”按 `event/path` 表示最终 confirmed event rows 与 `is_multipath=1` path rows。当前可追溯汇总没有为每个 PRN 都提供已通过 window-level geometry/time-alignment QA 的 LOW/MID/HIGH 类别，因此除项目明确标记的 G25 高仰角 control 外，其余项暂不作仰角推断。

| PRN | Elevation category | Stage2 candidate windows | Stage3 reliable centers | Stage4 confirmed event/path | Interpretation |
|---|---|---:|---:|---:|---|
| G06 | 待 geometry/time-alignment QA | 95 | 2 | 2/4 | confirmed sample；另有受保护的 legacy baseline |
| G11 | 待 geometry/time-alignment QA | 101 | 7 | 1/1 | confirmed sample |
| G12 | 待 geometry/time-alignment QA | 96 | 4 | 2/2 | confirmed sample |
| G25 | HIGH control（当前项目标记） | 52 | 0 | 0/0 | LOS-like/low-multipath control；不是物理“无多径”结论 |
| G28 | 待 geometry/time-alignment QA | 54 | 2 | 0/0 | Stage2/Stage3 candidate，最终被 Stage4 拒绝 |
| G29 | 待 geometry/time-alignment QA | 77 | 1 | 1/1 | confirmed sample |
| G32 | 待 geometry/time-alignment QA | 117 | 11 | 2/3 | confirmed sample |

这组结果说明，同一动态 scene 内不同 PRN 可以在层级证据框架下表现出不同状态：G25 提供 control，G28 展示候选经过持续性后仍可能被 Stage4 拒绝，G06、G11、G12、G29 和 G32 则提供 confirmed multipath/path 案例。该结果验证的是方法链的区分能力，不是对环境条件下多径概率的统计估计。

## 5.3 Cross-task validation with Wave-A experiments

为检验 pipeline 的行为不依赖单一 reference scene，项目进一步对三个独立的 10.23 MHz Wave-A task 执行了正常 Windows 用户执行和独立 QA：G16、G25 和 G12。三项任务均完成输入链检查、MATLAB smoke、Python executor、Stage0–Stage4 输出完整性和输出隔离检查。

| Task | Stage0 complete windows | Stage2 selected L1/L2/L3/L4 | Stage3 reliable centers | Stage4 confirmed event/path | Validation interpretation |
|---|---:|---:|---:|---:|---|
| G16/ch1 | 2,229 | 20/34/17/33 | 11 | 4/4 | confirmed/high-multipath execution case |
| G25/ch0 | 2,339 | 106/0/0/0 | 0 | 0/0 | complete zero-event control output |
| G12/ch6 | 1,629 | 21/17/12/57 | 11 | 3/3 | confirmed and high-order execution case |

这里的目的在于验证跨 scene、PRN 和 channel 的可复现执行链，而不是从三个任务推导统计规律。尤其是 G25 的 zero-event 结果表示在当前确认条件下没有 confirmed event/path；它是完整有效的 pipeline 输出，不应被改写为物理意义上的“没有多径”。

## 5.4 Long-duration scalability validation

Wave-2A task `F1023_V120_D0121_P2/G11/ch0` 用于观察较长动态记录下 full SAGE 的处理规模。该任务包含 15,210 个 Stage0 40 ms windows；Stage1 全量扫描约耗时 8.1 h，Stage2 约耗时 11.4 h，总耗时约 19.6 h。其 Stage1 candidate 数为 67，Stage2 最终模型分布为 L1/L2/L3/L4 = 65/1/0/1，Stage3 reliable centers 为 0，Stage4 confirmed event 为 0。

这一结果证明 full SAGE pipeline 能够在长记录上实际完成运行并产生完整 zero-event 输出，同时量化了窗口规模增加带来的显著计算负担。它不表示计算效率问题已经解决，也不能把 zero confirmed event解释为算法未执行或环境物理结论。该观察为后续 production 资源规划提供依据；出于事件完整性要求，当前论文数据生产仍采用 accuracy-first full SAGE pipeline。

## 5.5 Formal 10.23 MHz production validation

论文中的 validation 与 production 具有不同职责。validation 主要回答方法链和执行链是否可靠、可复现、可 QA；production 则在相同门禁下生成后续论文数据资产。production task 通过独立 QA 后，才可作为论文数据来源，但单个 task 仍不等于完整 event/path database，也不等于已经得到统计模型。

### 5.5.1 Production A1: F1023_V70_D0117_P4/G11/ch2

正式 production A1 task `F1023_V70_D0117_P4/G11/ch2/10.23MHz` 已完成并通过独立 QA。可记录的 Stage 统计为：Stage0 完整 40 ms windows = 893；Stage1 scanned windows = 893，selected/candidate windows = 110；Stage2 model-order rows = 440，最终 L1/L2/L3/L4 = 36/16/17/41；Stage3 reliable centers = 8；Stage4 joint rows = 8，其中 3 个 joint result 满足 confirmed criterion；confirmed events = 3，confirmed multipath paths = 3。

该任务的正式输出是 production artifact，能够作为后续 event/path ingest 的输入，但不代表完整数据库或所有 10.23 MHz scene 已经处理完成。相关事实应以 `docs/10MHz_FULL_SAGE_PRODUCTION_A1_G11_QA_REPORT.md` 及其 execution evidence 为准。

### 5.5.2 Production A2: F1023_V70_D0120_P1/G18/ch2

正式 production A2 task `F1023_V70_D0120_P1/G18/ch2/10.23MHz` 已完成并通过独立 QA。Stage0 完整 40 ms windows = 2,609；Stage1 scanned windows = 2,609，selected windows = 115；Stage2 model-order evaluation rows = 460，最终 L1/L2/L3/L4 = 41/26/30/18；Stage3 reliable centers = 9；Stage4 joint rows = 8，`joint_valid=1` rows = 8/8。

按照当前 confirmed criterion，该任务的 confirmed events = 0，confirmed paths = 0。这应表述为：**under the current confirmation criterion, this task produced zero confirmed multipath events**。它是完整、有效的 zero-event production output，不应写成“G18 has no multipath”，也不应被解释为最终 LOS 结论。

### 5.5.3 Production A3: F1023_V70_D0120_P5/G16/ch1

该正式 production task `F1023_V70_D0120_P5/G16/ch1/10.23MHz` 已完成 Stage0–Stage4 执行，并通过独立科学 QA。其运行时间为 `6497.683 s`，约 `108.29 min`。主要统计如下：

| Stage | 结果 |
|---|---:|
| Stage0 valid NAV symbols | 1,211 |
| Stage0 complete 40 ms windows | 1,209 |
| Stage1 scanned windows | 1,209 |
| Stage1 selected/candidate windows | 118 |
| Stage2 model-order evaluations | 472 |
| Stage2 final L1/L2/L3/L4 selection | 49/10/22/37 |
| Stage3 reliable centers | 5 |
| Stage4 joint rows | 5 |
| Stage4 joint_valid | 5/5 |
| Confirmed multipath events | 0 |
| Confirmed multipath paths | 0 |

按照当前项目的确认规则，Stage2 中的 `L>=2` 模型选择只表示较高阶模型拟合证据，不等同于 confirmed multipath；Stage3 reliable center 表示具有时间持续性的候选，也不等同于 confirmed multipath。只有同时满足 Stage4 `joint_valid=1`、`joint_multipath_count>0`，并且路径表包含有效 `is_multipath=1` 路径时，才进入 confirmed event/path 统计。因此，本任务的结果应表述为：**under the current Stage4 confirmation criterion, this task produced zero confirmed multipath events**。该 zero-event 结果是完整、有效的 Stage4 输出，不应被解释为 G16 没有物理多径、G16 为 LOS 或该场景不存在反射路径。

从科学输出角度看，该任务的 artifact completeness、Stage consistency 和 scientific validity 均通过独立 QA。需要与科学输出分开记录的是，原始执行记录曾出现 request `resume_allowed=false` 而实际 MATLAB command 使用 `Resume=true` 的执行契约偏差；独立 QA 未发现 checkpoint reuse，且本次运行从空 output namespace 开始并完整完成 Stage0–Stage4。该 executor/request contract 随后已修复并通过 static/dry-run validation。因而本案例可作为科学流程和 Pipeline Validation 的正式案例，但不应被重新表述为 fully production-accepted task，也不作为 Batch A continuous production 的最终放行依据。

本节的 G16 指正式 production task `F1023_V70_D0120_P5/G16/ch1`，与前述 Wave-A 验证中的 G16 task 属于不同执行记录；二者不应混合统计。该案例进一步补充了 pipeline 在多级筛选后得到合法 zero-event Stage4 输出的情形。

## 5.6 Computational acceleration investigation

为降低长记录 full SAGE 的计算成本，项目曾探索 sampling、raw-coarse 和 v3 selector 等加速路线。离线 coverage replay 和 posterior gold replay 表明，这些方案尚未达到论文数据生产所要求的 event preservation 门槛；v3.0 已保留为 `Implemented + QA Validated + Posterior Failed/Frozen` 的计算加速负结果。

该结论属于方法限制和 negative result，而不是项目失败。由于当前研究目标优先保证 confirmed event/path 的完整性，论文生产路线调整为：

```text
validated full SAGE pipeline
    -> multi-scene 10.23 MHz dataset
    -> event/path database
    -> geometry and time-alignment QA
    -> LOW/MID/HIGH statistical modeling
```

因此，本章把 acceleration investigation 作为可复现的探索和 limitation 讨论，不把 sampling 或 raw-coarse 输出当作 production selector，也不把尚未通过后验覆盖门禁的加速结果写成计算效率改进结论。
