# GNSS_SAGE 论文与科研状态唯一交接文档

**项目根目录：** `E:\GNSS_Multipath_Project`  
**论文状态唯一来源：** 本文件  
**最后审计时点：** 2026-08-31（Asia/Shanghai）
**面向对象：** 论文写作者、科研人员、方法分析人员  
**研究阶段：** accuracy-first full SAGE 冻结批次及独立批后 QA 已完成；Phase-1 的 Stage3 传统统计建模和 scientific closure 已完成并通过 QA（带明确限制）。coverage-complete event/path database、通用 channel-parameter database、Phase-2 AI 和完整暗室生成器仍是独立后续范围。

> 本文只负责科学问题、贡献、实验解释、论文可写事实、图表、限制和未来路线。工程文件路径、执行门禁、hash和receipt的唯一状态源是 `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`。本文不得把设计、计划或gold前预测写成实验结果。

## Current Phase-1 status at a glance (2026-08-31)

本节是当前 Phase-1 传统建模状态的优先来源，并 supersede 早期把统计模型写成
`Planned / Not started` 的未加日期快照；早期段落仍保留作历史 provenance。下方带日期的
VTC、production 和专题 layer 快照同样只描述各自时点，不覆盖本 current section。

- **Canonical artifacts：** Stage3 模型为 `dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3/`，报告为 `docs/ENVIRONMENT_ELEVATION_STAGE3_ACADEMIC_MODEL_V1_R3_REPORT.md`；scientific closure 为 `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/`，报告为 `docs/PHASE1_TRADITIONAL_CHANNEL_MODELING_SCIENTIFIC_CLOSURE.md`。r3 model manifest SHA-256=`61c4b3aa171b6a59d17607394770b684251d656eeb19813ca13ebed2454b1782`，r3 QA SHA-256=`916304ca04e5e84eb8e3349d9e072b1b36489a8aa0c95e34110b91f2012cfbf5`；r2 closure manifest SHA-256=`45282b4eb5f86e52f4cd39f9b94f04c1596b645cae3d0b6420a089717f429d52`，r2 QA SHA-256=`031f66441dbbfe0a9f5e8e98bdad863da7fc37b7514734649ba85561503480f4`。
- **Stage3 academic population：** 783 observations、445 reliable centers、366 conservative algorithm-level tracks、716 elevation-ready observations、50 runs、12 scenes、18 PRNs。主统计单位为 `WEIGHTED_OBSERVATION`，权重为 `1 / algorithm_track_size`；不把同一 track 的多行当作完全独立样本。
- **Hierarchy：** `Global → Environment → Environment×Elevation`。数据充分时使用本组观测，数据稀疏时部分共享上一级信息；Highway/Open–LOW 保持无直接支持，不人为补数据。
- **Marginal families：** excess delay 使用 `Lognormal`，signed relative Doppler 使用 `Normal`，relative power 使用 `Normal`。联合层使用 Gaussian Copula，但只在 global / environment / support-gated cell 层使用，不声称 12 个 cell 都有独立 covariance 拟合。
- **Robustness：** 使用 scene/run clustering、scene-block bootstrap、run-level sensitivity 和 grouped leave-one-scene-out（LOSO）检查结论稳定性。
- **Stage4 boundary：** 100 条 strict-confirmed Stage4 paths 是 high-confidence selection-sensitivity subset；`STAGE4_SENSITIVITY_RESULT = MATERIAL_DIFFERENCE`。Stage4 不是 ground truth，Stage3 observation/track 也不是物理反射体身份。
- **Scientific closure：** `ENVIRONMENT_EFFECT = INCONCLUSIVE`、`ELEVATION_EFFECT = INCONCLUSIVE`、`ENVIRONMENT_ELEVATION_INTERACTION = PARTIAL`；`RICEAN_K = NOT_IDENTIFIABLE`；persistence 仅表示算法连续观测，不等于真实反射体寿命。`JOURNAL_TRADITIONAL_MODELING_EVIDENCE` 与 `MASTER_THESIS_TRADITIONAL_MODELING_EVIDENCE` 均为 `READY_WITH_LIMITATIONS`。
- **Current paper boundary：** Phase-1 traditional statistical modeling is now `COMPLETE_WITH_LIMITATIONS`。model results completed; manuscript Results synchronization pending（长期论文同步 `Pending / In progress`）。不得扩展为完整 12-cell 实测覆盖、普适环境/仰角规律、Ricean K 或完整物理信道生成器。

## 0. 科研状态词和论文证据规则

- **Completed / Validated：** 已执行并由实际结果和独立QA支持，可作为论文事实；
- **Implemented：** 工具或方法已写入代码，但实验结果未完成，不能写成result；
- **Planned：** 设计或拟议实验，只能写planned experiment/expected validation；
- **Not started：** 没有数据支撑；
- **Failed / Frozen：** 已执行且失败，必须作为负结果或限制保留，不得改写成成功。

论文中的任何数字必须能追溯到实际Stage CSV/MAT、execution receipt、独立QA或后验replay artifact。gold replay之前的预测不能写成结果；未扫描窗口不能写成LOS/no-event；Stage2高阶模型和Stage3持续性不能写成confirmed multipath。

## 1. 科学问题和最终目标

研究问题是：能否从GPS L1 C/A原始复数IQ和GNSS-SDR解析结果中，经过NAV-aided SAGE，稳定提取多径路径的时延、Doppler、相对功率和持续性，并进一步建立按卫星仰角分区的统计信道模型。当前实现中的 `maximum_coherence` 是联合模型级的路径 replica 可分离性诊断量，不是路径级传播参数。

最终目标是构建可追溯的：

```text
scene × PRN × tracking channel × time/window × path
```

事件数据库，并在coverage-complete的窗口分母上，按：

- LOW：0–30°；
- MID：30–60°；
- HIGH：60–90°；

建模多径发生概率、path count、excess delay、relative power、Doppler offset、persistence，并分析CN0、速度、场景/环境等条件；联合模型级 `maximum_coherence` 如使用，仅作为可靠性/可分离性诊断量，不作为 path-level channel parameter。

当前不能声称已经建立 coverage-complete occurrence/negative-denominator 或完整物理信道模型；但上述 bounded Phase-1 Stage3 传统统计模型已经完成并通过 scientific closure QA。

## 2. 数据和实验系统

数据集含19个scene：13个10.23 MHz、6个20.46 MHz；inventory旧计划口径为124个distinct scene-PRN，channel-expanded候选数更高。每个scene包含GNSS-SDR tracking/telemetry、标准化RINEX NAV/OBS、trajectory NMEA、satellite geometry CSV和可选SAGE结果。

数据链为：

```text
raw IQ
 -> GNSS-SDR tracking/telemetry/observables/PVT
 -> navigation + trajectory standardization
 -> NMEA-GSV elevation/azimuth/SNR diagnostic
 -> Stage0 NAV catalog/40 ms window
 -> Stage1 screening
 -> Stage2 fractional SAGE L=1..4
 -> Stage3 persistence
 -> Stage4 joint 100 ms
 -> event/path database
 -> elevation-conditioned statistical model
```

重要方法限制：当前elevation/azimuth主要来自NMEA GSV；RINEX NAV用于PRN/导航记录过滤，并非广播星历位置重算。summary geometry不能直接当作事件窗口瞬时仰角；TOW-aligned join仍是offline diagnostic，失败时应保留null。

## 3. SAGE方法和确认逻辑

### 3.1 Stage0–Stage4

| Stage | 科学作用 | 可写的语义 |
|---|---|---|
| Stage0 | 从tracking/telemetry/NMEA构造有效NAV symbol与完整40 ms window母集 | 完整母集，不是事件标签 |
| Stage1 | NAV wipe后做main/residual correlation screening | 候选证据，不是confirmed |
| Stage2 | 对Stage1候选评估fractional SAGE L=1,2,3,4 | `L>=2`表示多分量模型更合适，不等于物理多径 |
| Stage3 | 检查邻域窗口的delay/Doppler/power persistence | reliable/persistent candidate，不是最终确认 |
| Stage4 | 对100 ms五快照做joint common-geometry拟合 | 当前confirmed criterion的最终阶段 |

当前confirmed multipath定义：`joint_valid=1` 且 `joint_multipath_count>0`，并且path表存在对应`is_multipath=1`路径。Stage4 event-level `maximum_coherence`不能误写成每条path独立coherence；path相对功率字段需保留其source field。

### 3.2 可解释性边界

本研究的confirmed是算法管线内的操作性定义，不是外部电磁真值。G25是同一执行链中的低多径/LOS-like control，G28是候选被Stage4拒绝的control；两者不能单独证明物理环境无反射。论文应把Stage0–Stage4写成层级证据链，而不是把某一层输出直接称为真值。

## 4. 已完成、可直接写入论文的实验结果

### 4.1 Reference scene七PRN

Reference：`F1023_V70_D0117_P2`，10.23 MHz。七PRN已经完成full-scan validation，实际统计：

| PRN | channel | 40 ms windows | Stage1 candidates | L1/L2/L3/L4 selected | Stage3 | Stage4 confirmed/path | 科研分类 |
|---|---:|---:|---:|---:|---:|---:|---|
| G06 | 4 | 319 | 95 | 8/29/17/41 | 2 | 2/4 | confirmed；另有legacy baseline保护 |
| G11 | 5 | 1175 | 101 | 45/4/22/30 | 7 | 1/1 | confirmed sample |
| G12 | 6 | 1175 | 96 | 38/12/1/45 | 4 | 2/2 | confirmed sample |
| G25 | 0 | 1175 | 52 | 40/2/0/10 | 0 | 0/0 | LOS-like/low-multipath control |
| G28 | 1 | 898 | 54 | 42/4/5/3 | 2 | 0/0 | candidate/rejected by Stage4 |
| G29 | 7 | 1175 | 77 | 45/6/2/24 | 1 | 1/1 | confirmed sample |
| G32 | 11 | 1175 | 117 | 31/15/1/70 | 11 | 2/3 | confirmed sample |

Reference共8个Stage4 confirmed event rows、11条confirmed multipath paths。代表性参数包括：G06/203有3条path、excess delay 1.6/2.6/8.3 samples；G06/264为3.9 samples；G11/640为1.1 samples；G12/970和971各为1.1 samples；G29/80为1.1 samples；G32/82有1.1和2.5 samples，G32/84为1.1 samples。Doppler和relative power的逐路径数值应直接引用reference final report和Stage4 CSV；Stage4 `maximum_coherence` 如引用，必须标为event/joint-model级诊断量，不得写成path-level coherence。

论文可以据此展示：同一scene、不同PRN会出现LOS-like、候选拒绝和confirmed multipath三类层级行为；但一个scene不能代表总体环境。

### 4.2 Wave-A三任务

| Task | Stage0 NAV/windows | Stage2 selected L1/L2/L3/L4 | Stage3 reliable | Stage4 confirmed/path | 结论 |
|---|---:|---:|---:|---:|---|
| G16/ch1 | 2231/2229 | 20/34/17/33 | 11 | 4/4 | confirmed/high-multipath sample |
| G25/ch0 | 2343/2339 | 106/0/0/0 | 0 | 0/0 | low-multipath/LOS-like control |
| G12/ch6 | 1631/1629 | 21/17/12/57 | 11 | 3/3 | confirmed/high-order sample |

三项均完成正常用户Windows执行、MATLAB/Python退出、21文件、Stage0–Stage4链、输出隔离和独立QA。总计7个confirmed event rows、7条associated paths。G25 zero-event是完整有效的空结果，不是执行失败，但仍不等于物理无多径。

### 4.3 Wave-2A G11运行规模观察

`F1023_V120_D0121_P2/G11/ch0`有15,210个Stage0 40 ms windows；Stage1全量约8.1小时，Stage2约11.4小时，总耗时约19.6小时。Stage1候选67，Stage2最终分布L1/L2/L3/L4=65/1/0/1，Stage3 reliable=0，Stage4 confirmed=0。

论文可把它写成运行规模和吞吐观察：窗口数约为reference G11的12.94倍，Stage1墙钟时间约17.7倍（时间由artifact时间戳估计）。不能把单一I/O、CPU或MATLAB内部机制当作已证明根因，也不能把G11 zero confirmed解释为算法未运行。

## 5. 采样和raw-coarse实验：可写结果与失败边界

### 5.1 v1/v1.1/A0负结果

- v1稀疏/分层采样：Wave-A G16 center recall 47.5%、+/-2 closure 25.0%；G12 center 53.3%、closure 36.7%；FAIL。
- v1.1连续block/adaptive replay：block 11/21/31/41在1200 budget和seed_00至09的跨任务稳定coverage未达100%；budget扩大到4800仍FAIL。
- A0只用Stage0/tracking/geometry低成本字段，11个gold task的known confirmed center和closure recall为0%；FAIL。

这些负结果可以作为“稀疏抽样不能可靠发现隐藏seed”和“仅靠低成本字段不足以达到硬召回门槛”的方法限制，但不能把未扫描窗口当成negative/LOS。

### 5.2 v2 raw-coarse和v3当前结论

NumPy v2 kernel已经完成12/12数值一致性alignment，真实D100/D200 grid和legacy数学语义保持一致。G16 Retry1 raw-coarse执行本身完成，但三个profile均将2229/2229窗口promotion；因此它只能证明compiled kernel加速方向，不能证明coarse screening有效。

v3正式evidence QA PASS，feature table含2,229 rows，ownership revision保留188 core components和1,222 unique fine windows；gold-blind ownership QA PASS。之后的posterior gold replay只读取已存在Stage3/Stage4作为后验比较，没有重建feature或selector：

| 后验目标 | 覆盖 | Recall | 门禁 |
|---|---:|---:|---|
| confirmed center（母集4） | 2/4 | 50.0000% | FAIL |
| confirmed center +/-2（母集16） | 12/16 | 75.0000% | FAIL |
| Stage3 reliable-center +/-2（母集44） | 25/44 | 56.8182% | FAIL |

漏检仅按冻结artifact中的原因归因：主要为`secondary_doppler_inconsistent`和`cross_scale_disagreement`。没有利用gold位置调threshold、tolerance、component或closure规则。科学结论是：v3.0当前不能放行G25 control request，也不能进入sampled SAGE production；它应作为 `Implemented + QA Validated + Posterior Failed/Frozen` 的 computational acceleration investigation、negative result 和 limitation 保留。v3.1设计暂缓，不再作为论文数据生产的前置阻塞条件。

由于coarse screening未达到posterior event preservation要求，论文数据生成优先采用已经验证通过的full SAGE pipeline。论文核心贡献不依赖v3：

- GNSS raw IQ measurement chain；
- NAV-aided SAGE multipath extraction；
- Stage0-Stage4 reliability hierarchy；
- multipath event/path database；
- elevation-conditioned statistical modeling。

当前accuracy-first production主线为：

```text
validated full SAGE pipeline
  -> multi-scene 10.23 MHz dataset
  -> event database
  -> geometry/time alignment QA
  -> LOW/MID/HIGH statistical modeling
```

该路线目前仍是论文数据生产计划，不代表已经完成所有scene处理、已经建立大规模数据库或已经建立统计模型。

## 6. 论文可直接使用的研究材料

### Introduction / Motivation

可写：GNSS raw IQ多径参数估计需要从单窗口候选逐级提升到persistent/joint event；长recording带来Stage1/Stage2吞吐问题；最终需要elevation-conditioned model。  
不能写：已得到普适多径概率或所有环境的统计规律。

### System and Data Acquisition

可写：19 scene、10.23/20.46 MHz分布、raw local/external存储、GNSS-SDR输入输出链。  
仍需：scene ID中速度/日期/环境编码字典、接收机/天线和环境元数据的完整核实。

### GNSS-SDR Preprocessing

可写：tracking MAT、telemetry DAT、RINEX NAV、NMEA trajectory、NMEA-GSV geometry的作用和标准化脚本。  
必须注明：geometry不是broadcast ephemeris位置重算，window-level event join尚未生产化。

### SAGE Multipath Estimation Method

可写：Stage0 NAV symbol wipe、Stage1 correlation、Stage2 fractional L1-L4、Stage3 persistence、Stage4 joint 100 ms和confirmed criterion。  
不能把L>=2或Stage3 reliable直接写成confirmed。

### Reference Validation

可写：7 PRN matrix、G25 control、G28 rejected candidate、G06/G11/G12/G29/G32 confirmed samples、8 events/11 paths。  
限制：单scene、无外部真值、G06有受保护legacy baseline。

### Batch Execution and Reproducibility

可写：immutable request、hash/preflight、normal-user wrapper、MATLAB smoke、Python executor、21-file QA和Wave-A三任务PASS。  
这是工程可复现性贡献，不要包装成SAGE科学精度提升。

### Runtime Scalability Observation

可写：G11 15,210 windows、Stage1约8.1h、Stage2约11.4h、总约19.6h，以及与reference G11的规模对比。  
不能声称已经证明某个单一性能根因。

### Sampling Acceleration Design

可写：v1/v1.1/A0的失败结果、v2 alignment、v3 evidence/ownership/posterior coverage负结果。  
必须明确：尚无有效sampled SAGE pilot和生产加速比。

### Limitations

当前限制包括：样本数量和环境覆盖不足；无external truth；geometry window-level join未生产化；v1/v1.1/A0/v3 selector失败；coverage-complete event database、negative denominator 和通用物理信道生成器未完成；20.46 MHz未适配；可能存在选择与coverage偏差。Phase-1 bounded traditional statistical model 已在 r3/r2 中完成。

## 7. 历史统计建模路线（2026-08-16 snapshot；superseded by current Phase-1 r3/r2）

本节保留早期路线设计及其当时的 `Planned / Not started` 状态；它不覆盖上面的
Phase-1 canonical status。以下内容仍适用于 coverage-complete occurrence 模型和未来扩展。

只有在event database建立、geometry join通过QA、negative/no-event分母coverage-complete后，才可执行：

1. `P(multipath occurrence | elevation bin, scene/speed/environment)`；
2. `P(path_count | confirmed multipath, conditions)`；
3. excess delay（samples/chips，记录换算公式版本）分布；
4. relative power、Doppler offset、coherence/persistence分布；
5. delay-power、delay-Doppler、path-count-elevation联合关系；
6. scene/PRN/速度/环境分层或混合效应模型。

event database设计中的`confirmed_multipath`、`rejected_candidate`、`los_reference`标签必须带来源和namespace；sampling未扫描状态应为`inconclusive_due_to_sampling`，不能进negative denominator。

## 8. 建议论文图表清单

| 图表 | 当前是否可做 | 原始来源 |
|---|---|---|
| raw IQ→GNSS-SDR→Stage0-4→event DB流程图 | 可以 | preprocessing scripts、`run_nav_sage_pipeline.m` |
| scene目录与数据处理流程图 | 可以 | scene `metadata.json`、engineering handoff |
| Stage0-Stage4漏斗图 | 可以 | reference 7 PRN Stage CSV、Wave-A QA、G11 QA |
| reference七PRN对比表 | 可以 | `reference_scene_final_validation_report.md`、各PRN目录 |
| Wave-A三任务执行/结果表 | 可以 | `WAVEA_10MHz_VALIDATION_REPORT.md`、三份QA |
| reference confirmed delay/Doppler/power示例图 | 可以 | reference Stage4 summary/path CSV |
| G11 runtime scalability图 | 可以，需标时间戳估计 | `WAVE2A_G11_QA_REPORT.md`、progress和task log |
| v1/v1.1/A0 coverage失败图 | 可以，作为负结果 | sampling validation目录和三份报告 |
| v2 raw-coarse runtime vs promotion图 | 可以，需区分kernel加速和selector失败 | Retry1 QA、raw-coarse report/cost artifacts |
| v3 posterior coverage/reason图 | 可以，作为失败结果 | `RAW_COARSE_V3_G16_POSTERIOR_GOLD_COVERAGE_REPORT_R1B.md`、posterior CSV/JSON |
| LOW/MID/HIGH统计分布 | 暂不可下结论 | 等event DB、geometry QA和多scene数据 |
| 20.46 MHz比较图 | 暂不可做 | 必须先单独适配和验证 |

## 9. 当前科研状态矩阵

| 研究内容 | 状态 | 论文表达 |
|---|---|---|
| 19 scene预处理和数据链 | Completed + Validated | 可写方法和数据准备事实 |
| Pipeline V3 10.23验证 | Completed + Validated（已执行task范围） | 可写方法验证，不可外推全部scene |
| Reference七PRN | Completed + Validated | 可写案例和层级判定 |
| Wave-A三任务 | Completed + Validated | 可写受控执行链和7 event/7 path |
| Wave-2A G11 | Completed + Validated | 可写zero-event和runtime scalability |
| Batch执行可复现链 | Completed + Validated | 可写工程复现方法 |
| Sampling v1/v1.1/A0 | Failed + Frozen | 可写负结果/限制 |
| v2 kernel alignment | Validated | 可写数值语义一致性，不等于selector成功 |
| v3 evidence/ownership | Implemented + QA Validated | 可写gold-blind evidence和schema工程事实 |
| v3 posterior selector | Failed / Frozen | 可写加速探索负结果和limitation，不放行production |
| full SAGE production | In progress; A1/A2/G12 Completed + QA PASS；A3 G16 scientific validation completed，未作为Batch A release evidence；Batch A已由G12 controlled acceptance释放 | `F1023_V70_D0117_P4/G11/ch2`、`F1023_V70_D0120_P1/G18/ch2`、`F1023_V70_D0117_P4/G12/ch4`和正式`F1023_V70_D0120_P5/G16/ch1`均有可追溯结果；G16因已识别的初始execution-policy deviation不作为Batch A continuous production放行依据；G12独立QA已PASS，其余任务尚未执行 |
| Event database | Planned / Not started | 只能写设计和future work |
| Phase-1 Stage3 Environment×Elevation传统统计模型 | Completed / PASS_WITH_LIMITATIONS | 可写有边界的传统统计模型结果；不得外推为普适规律 |
| Phase-1 scientific closure | Completed / PASS_WITH_LIMITATIONS | 可写科学结论、稳健性方法和限制 |
| 长期论文 Results 同步 | Pending / In progress | model results completed; manuscript Results synchronization pending |
| 20.46 MHz | Not started | 不能写跨采样率结果 |

## 9.1 首个正式10.23 MHz production result

2026-08-13，首个论文数据生产任务 `F1023_V70_D0117_P4/G11/ch2/10.23MHz` 由正常 Windows 用户执行链完成，并通过独立 post-run QA。正式输出位于：

`scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G11/`

该任务的可记录事实为：Stage0=`895` valid NAV symbols、`893` complete 40 ms windows；Stage1=`893` scanned、`110` selected/candidate windows；Stage2 最终 L1/L2/L3/L4=`36/16/17/41`；Stage3 reliable centers=`8`；Stage4 joint rows=`8`，其中 `3` 个 confirmed multipath events、`3` 条 confirmed multipath paths，另有 `5` 个合法 zero-event joint results。confirmed criterion 仍严格要求 `joint_valid=1`、`joint_multipath_count>0` 且 path 表存在 `is_multipath=1`。

这是一项新增 production artifact 和执行可复现性事实，不是统计模型结果，也不表示已建立完整 event database、已完成所有 10.23 MHz scene 或已得到 LOW/MID/HIGH 分区结论。详情以 `docs/10MHz_FULL_SAGE_PRODUCTION_A1_G11_QA_REPORT.md` 和工程 handoff 的 receipt/hash 记录为准。

### 9.2 第二个正式10.23 MHz production result

2026-08-13，`F1023_V70_D0120_P1/G18/ch2/10.23MHz` 由同一正常 Windows 用户执行链完成，并通过独立只读 post-run QA。正式输出位于：

`scenes/F1023_V70_D0120_P1/sage_results/nav_sage_v2/G18/`

该任务的可记录事实为：Stage0=`2611` valid NAV symbols、`2609` complete 40 ms windows；Stage1=`2609` scanned、`115` selected windows；Stage2 model-order evaluation rows=`460`，最终 L1/L2/L3/L4=`41/26/30/18`；Stage3 reliable centers=`9`；Stage4 joint rows=`8`，其中 `8/8` 为 `joint_valid=1`。按项目严格 confirmed criterion，confirmed multipath events=`0`、confirmed paths=`0`；这是完整的zero-event pipeline output，不被解释为物理LOS结论。

执行证据和独立QA分别位于：

- `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T034529Z/batch_execution_log.csv`
- `docs/10MHz_FULL_SAGE_PRODUCTION_A2_G18_QA_REPORT.md`

该任务耗时=`7737.82 s`，MATLAB smoke marker/exit code、Python executor exit code和task exit code均通过。该新增事实只说明第二个production artifact已生成并通过QA，不表示完整event database、全部scene处理或统计模型已经完成。

### 9.3 正式 A3 G16 科学验证案例

正式 production task `F1023_V70_D0120_P5/G16/ch1/10.23MHz` 已完成 Stage0–Stage4，并通过独立科学 QA。运行时间为 `6497.683 s`（约 `108.29 min`）。实际统计为：Stage0 valid NAV symbols=`1211`、complete 40 ms windows=`1209`；Stage1 scanned=`1209`、selected/candidate=`118`；Stage2 evaluations=`472`，最终 L1/L2/L3/L4=`49/10/22/37`；Stage3 reliable centers=`5`；Stage4 joint rows=`5`，其中 `5/5` 为 `joint_valid=1`；confirmed events=`0`、confirmed paths=`0`。

该案例的 artifact completeness、Stage consistency 和 scientific validity 均为 PASS。按照当前确认规则，Stage2 的 `L>=2` 不是 confirmed multipath，Stage3 reliable center 也不是 confirmed multipath；只有 Stage4 joint confirmation（`joint_valid=1`、`joint_multipath_count>0` 且 path table 存在 `is_multipath=1`）才进入 confirmed event/path。因此，G16 应表述为：**under the current Stage4 confirmation criterion, this task produced zero confirmed multipath events**，而不能表述为 G16 没有物理多径、G16 为 LOS 或该场景不存在反射路径。

需要单独区分科学 artifact 与执行策略记录：原始执行记录存在 request `resume_allowed=false`、实际 command `Resume=true` 的已识别契约偏差；独立 QA 未发现 checkpoint reuse，且该次运行从空 output namespace 开始并完整完成 Stage0–Stage4。executor/request contract 随后已修复并通过 static/dry-run validation。该案例可作为正式 Pipeline Validation 科学案例，但不应被写成 fully production-accepted task，也不作为 Batch A continuous production 的最终放行依据。该正式 A3 G16 与前述 Wave-A G16 validation task 不混合统计。

## 10. 固定未来路线

当前固定路线为：

1. 保留并引用v3.0 posterior FAIL，作为computational acceleration investigation、negative result和limitation；
2. 继续按 immutable manifest、hash、new_only、正常用户 Windows 执行和逐任务 QA 门禁推进 10.23 MHz full SAGE data production；A1/A2 已完成并通过QA，正式 A3 G16 可作为科学验证案例但不作为 Batch A release evidence，其余任务仍为 `Planned / Not started`；
3. 首个 task QA PASS 后，才可准备并执行下一个独立 Batch A task；不得自动串行启动多个任务；
4. 将通过QA的Stage0-Stage4结果接入multipath event/path database；
5. 完成event/window geometry与time alignment QA，失败字段保留null和provenance；
6. 在coverage-complete数据上按LOW/MID/HIGH elevation bin进行统计建模，并关联CN0、速度、scene/environment条件；
7. 20.46 MHz单独适配、单任务验证和独立QA，不能继承10.23 MHz放行结论。

full SAGE production plan准备不等于批量执行；本次状态更新不生成request、不运行batch、不恢复任何任务。v3.1设计可以作为未来独立加速研究，但当前不作为论文数据生产阻塞条件。

## 10.1 当前 production 状态说明（2026-08-14）

当前 full SAGE production 已启动但仍处于逐任务受控生产阶段。`F1023_V70_D0117_P4/G11/ch2/10.23MHz`、`F1023_V70_D0120_P1/G18/ch2/10.23MHz` 和 `F1023_V70_D0117_P4/G12/ch4/10.23MHz` 已完成并通过QA；正式 A3 `F1023_V70_D0120_P5/G16/ch1/10.23MHz` 已完成科学 artifact QA，但因初始 execution-policy deviation 不作为 Batch A continuous production 的最终放行依据。G12修复后controlled acceptance已验证真实 `Resume=false` 和new-only策略，Batch A continuous production已释放。这不表示全部scene已处理、event database已建立或统计模型已完成。后续任务必须继续使用独立 immutable request、hash/preflight、正常用户 Windows wrapper 和逐任务 QA 门禁。v3.0 仍是 posterior failed/frozen 的加速负结果，不作为 production selector。

## 10.2 当前 G12 controlled acceptance 状态（2026-08-14）

`F1023_V70_D0117_P4/G12/ch4/10.23MHz` 已由正常 Windows 用户执行链完成并通过独立 QA。实际证据目录为：

`dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T024904Z/`

`status_history.jsonl` 记录最终状态为 `completed`，executor exit code 为 `0`；task log 记录目标目录已有 `21` 个输出文件，Stage0 为 `895` valid NAV symbols / `893` windows，Stage1 candidates=`99`，Stage2 最终 L1/L2/L3/L4=`30/7/7/55`，Stage3 reliable centers=`15`，Stage4 joint results=`8`。独立 QA 报告 `docs/10MHz_FULL_SAGE_PRODUCTION_CONTRACT_ACCEPTANCE_G12_QA_REPORT.md` 已确认 execution contract、new-only、artifact completeness、stage consistency 和 scientific validity 全部 PASS；Stage4 confirmed events=`3`、confirmed paths=`3`。G12 当前状态为 **Completed / QA PASS / Available evidence**，可计入当前10.23 MHz production accepted count，但不表示完整event database或统计模型已完成。

真实MATLAB command已核对为显式 `'Resume', false`，未发现 `'Resume', true`；因此该任务作为executor/request contract修复后的第一次真实acceptance通过。Batch A continuous production已释放，后续任务仍需逐任务独立request、人工执行和QA。

## VTC2027-Spring Regular Paper 投稿冲刺

VTC投稿是当前长期论文路线之外的一个受控、短篇论文工作区。目标为 `VTC2027-Spring Regular Paper`，外部截止日期为 `2026-09-01`，内部完整稿目标为 `2026-08-31`，篇幅目标为五页。

工作题目为：

> SAGE-Based High-Resolution Multipath Characterization of GPS L1 C/A Signals in Dynamic Vehicular Environments

备选题目为：

> Measurement-Based Characterization of Dynamic GNSS Multipath Using High-Resolution SAGE Path Extraction

VTC论文的定位收敛为：真实动态GPS L1 C/A raw-IQ测量、NAV-aided hierarchical SAGE、高分辨率路径提取和measurement-based path-level characterization。论文不声称提出新的SAGE算法，不声称完成定位/多径抑制，不声称已经建立完整统计信道模型、完整event/path database或处理全部scene。完整PDP/RMS delay spread/Doppler spread/K-factor统计建模仍是长期/期刊路线。

VTC锁定的三项贡献为：

1. 真实动态GNSS raw-IQ测量链及覆盖Urban、Mountain/Valley、Highway/Open、Special Reflective元数据类别的10.23 MHz生产范围；
2. Stage0有效NAV symbol/40 ms window、Stage1 correlation screening、Stage2 fractional SAGE L=1–4、Stage3 temporal persistence和Stage4 100 ms joint confirmation组成的层级提取框架；
3. 以confirmed Stage4 path为基础的excess delay、relative Doppler、relative power及有证据支持时的persistence/lifetime和有限环境/仰角观察。

当前VTC证据状态：

- reference scene七PRN、Wave-A G16/G25/G12：Completed / Validated，可用于层级行为和跨任务执行链事实；
- 正式A1 G11：Completed / QA PASS，3 confirmed events和3 confirmed paths；
- 正式A2 G18：Completed / QA PASS，under the current Stage4 confirmation criterion产生0 confirmed events，不能解释为物理上没有多径；
- 正式A3 G16：科学artifact QA PASS、0 confirmed events/paths，可用于Pipeline Validation，但历史execution-policy deviation使其不作为Batch A continuous production release evidence；
- G12 controlled acceptance：Completed / QA PASS，3 confirmed events和3 confirmed paths，登记为 AVAILABLE evidence；是否进入VTC正文核心Results仍待后续证据筛选；
- VTC evidence-priority production strategy：Planned/Active；Batch A 已释放，但不追求在投稿前完成全部67项任务，优先以少量跨环境、跨仰角候选补齐论文证据缺口；正式队列见 `docs/vtc2027_spring/VTC_PRODUCTION_PRIORITY_QUEUE.md`；该队列不授权执行，也不预测confirmed event。
- event database、channel-parameter database、完整统计模型：Planned / Not started。

VTC工作区已建立于 `docs/vtc2027_spring/`，包括 `VTC_PLAN.md`、`EVIDENCE_MATRIX.md`、`MANUSCRIPT_OUTLINE.md`、`FIGURE_TABLE_PLAN.md` 和 `manuscript/VTC2027_Spring_draft.md`。该目录是投稿资产组织结构，不是新的论文状态源；本文件仍是论文科学状态唯一来源，`docs/PAPER_WORKSPACE_INDEX.md`负责资产导航。

VTC投稿格式资产已进一步建立：`manuscript/latex/main.tex` 使用独立的 IEEE conference-mode skeleton，`references.bib` 保持为无虚构条目的待核验文件，`submission/SUBMISSION_REQUIREMENTS.md` 和 `submission/PAGE_BUDGET.md` 记录官方要求。官方VTC页面未发现专属LaTeX class，因此当前采用 generic IEEE conference `IEEEtran` 约定；本机没有TeX编译器和本地`IEEEtran.cls`，两次官方ZIP只读下载尝试返回0字节，故模板原件和PDF编译状态仍为 **Pending / Not started**，不能写成格式验证完成。Figure 1已形成TikZ源文件和SVG草图，渲染PDF仍待工具链。

VTC结果计划优先展示：Stage1–Stage4层级筛选漏斗、一个真实confirmed path案例、excess delay/relative power/relative Doppler的经验性path-level观察，以及在window-level geometry QA完成后才进行的有限LOW/MID/HIGH和环境比较。raw-coarse/sampling/v3只作为计算加速探索的negative result和limitation保留。

### VTC Evidence-Priority Production Strategy（2026-08-14）

VTC投稿阶段不等待全部67个10.23 MHz production task完成。基于当前reference、Wave-A、Wave-2A、A1/A2和controlled G12证据，下一步采用“small wave → independent QA → evidence matrix update → 决定是否继续”的受控路线。当前只完成规划：Batch A manifest中的48个Batch A行经当前输出目录核对后，有44个新`new_only`候选；A1 G11、controlled G12、A2 G18已排除，历史A3 G16目录受保护且不作为acceptance候选。

当前最大证据缺口是Special Reflective正式production覆盖；LOW/MID/HIGH的定义和GSV摘要已有，但window-level TOW geometry join仍为Missing/Partial。规划中的第一波选择三个不同scene，覆盖Special Reflective、Highway/Open和Mountain/Valley，并尽量形成LOW/HIGH/MID的场景级几何互补。该策略是论文证据规划，不是实验结果，不生成request，不把候选任务写成已完成，也不根据候选任务预测多径。

最低停止条件是：四类环境均有可用于论文的真实QA证据或明确缩小论文表述；LOW/MID/HIGH分析有QA完整的窗口分母；已有confirmed、rejection/control和zero-event案例足以支持计划图表；并且所有正文数字均能追溯到immutable artifact。该条件不要求67/67、20.46 MHz或已完成统计模型。

VTC投稿门禁依次为：生产基础设施和QA可复现、代表性证据覆盖、confirmed path聚合可追溯、核心图表完成、五页英文稿完成、科学一致性QA和最终IEEE/VTC格式QA。上述门禁均为Planned，不能写成已完成。

## 11. 相关工程和专题文档

工程路径、hash、manifest和当前可运行命令请读取：

`docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`

专题科学/工程来源包括：

- `scenes/F1023_V70_D0117_P2/sage_results/reference_scene_final_validation_report.md`
- `docs/WAVEA_10MHz_VALIDATION_REPORT.md`
- `docs/WAVE2A_G11_QA_REPORT.md`
- `docs/MULTIPATH_EVENT_DATABASE_DESIGN.md`
- `docs/STAGE1_STAGE2_BATCH_SAMPLING_DESIGN.md`
- `docs/BATCH_SAMPLED_V1_OFFLINE_COVERAGE_REPORT.md`
- `docs/BATCH_SAMPLED_V1_1_OFFLINE_COVERAGE_REPORT.md`
- `docs/BATCH_SAMPLED_V1_2_A0_OFFLINE_COVERAGE_REPORT.md`
- `docs/RAW_COARSE_V3_G16_POSTERIOR_GOLD_COVERAGE_REPORT_R1B.md`

这些文件支持具体事实，但不再改变本文件作为论文状态唯一来源的定位。

## 12. 新论文作者接手后的第一条建议

先阅读本文件和工程状态唯一来源；不要把旧handoff中的“可继续Wave-2A”、gold前预测或v3 ownership QA PASS误写成当前production selector成功。当前可写材料包括方法链、reference/Wave-A验证、full-SAGE批次事实、sampling/v3 posterior失败作为计算加速负结果和 limitation，以及 r3/r2 的 bounded Phase-1 traditional statistical model。coverage-complete event/path database、通用扩展模型和长期论文 Results 同步仍需分别标注其状态。

## 13. 论文写作框架

已建立论文草稿目录 `docs/paper_draft/`，包括总纲 `manuscript_outline.md` 和 Introduction、Related Work、Methodology、Experimental Setup、Pipeline Validation、Results placeholder、Conclusion 七个章节文件。

- 该目录是论文写作框架，不代表 coverage-complete event database、通用扩展模型或全部 scene 生产已经完成；Phase-1 bounded statistical model 已在 r3/r2 中完成。
- `06_Results_PLACEHOLDER.md` 明确保留未完成生产和统计分析的占位符，不填入预测数字。
- 当前可直接使用的论文事实仍必须追溯到已有 artifact、execution receipt 和 QA report。

状态：`Implemented / Phase-1 model results available; Results synchronization pending`（论文框架已建立；完整论文正文仍需按 canonical r3/r2 结果同步）。

### Methodology chapter draft status

`docs/paper_draft/sections/03_Methodology.md` 已完成一次论文方法章节更新，状态为 `Implemented`。本次更新建立了中文的正式章节结构，覆盖 end-to-end GNSS raw IQ → GNSS-SDR → NAV-aided SAGE → Stage0–Stage4 证据层级 → confirmed path → channel parameter modeling framework，并明确区分 candidate、Stage3 reliable center 与 Stage4 confirmed criterion。

该状态表示论文方法章节框架和初稿已建立；Phase-1 r3/r2 的传统统计模型结果现已完成，但尚未同步进 Results 正文。full SAGE production 的执行门禁、Batch A release 和 coverage-complete event/path database 状态不因该模型完成而改变。

### Pipeline Validation chapter draft status

`docs/paper_draft/sections/05_Pipeline_Validation.md` 已完成一次论文验证章节扩展，状态为 `Implemented`。本次整理了 reference scene 多 PRN 验证、Wave-A 跨任务复现、Wave-2A 长记录规模观察、A1/A2 正式 10.23 MHz production QA 事实，以及正式 A3 G16 的 Stage0–Stage4 科学验证记录；同时保留 sampling/raw-coarse/v3 为 posterior preservation 未通过的 acceleration investigation 与 limitation。

该更新只改变论文草稿资产状态和论文可写验证事实，不改变 Engineering Handoff、production manifest、execution request、G16 artifact 或 Batch A release 状态。G16 的科学结果已可写入 Pipeline Validation；Phase-1 传统统计模型另见上方 current canonical section，Results 正文同步仍待完成。

## 14. Handoff impact

## 14. 2026-08-13 10.23 MHz scene metadata layer

The paper-data metadata layer is now established for the 10.23 MHz full-SAGE production scope. The immutable source artifact is `dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv`, with coverage report `docs/scene_metadata_10MHz_check_report.md`.

- Scope: 13 unique 10.23 MHz scenes and 83 scene-PRN production tasks.
- Coverage: 13/13 production scenes have a metadata row, existing scene metadata, and a consistent raw-path/sample-rate mapping.
- Human annotations: environment class, special condition, road category, and human-description fields are recorded from the supplied collection notes; speed provenance is `human_measurement_description`.
- Category counts: Urban=6, Mountain/Valley=3, Highway/Open=2, Special Reflective=2.
- This is a metadata/data-organization milestone only. It does not mean the dataset, event database, statistical model, or all scenes have been processed.
- Existing per-scene `metadata.json`, production manifest, execution requests, SAGE outputs, and raw files were not rewritten by this update.

Status expression: `Completed + Validated` for the new metadata layer; full 10.23 MHz SAGE production is now `3/67 Completed + QA PASS`，including G12 controlled acceptance；remaining tasks require new requests and independent QA.

## 18. Statistical channel parameter candidate pool

The statistical channel parameter set remains a broader candidate pool for future
extensions; the bounded Phase-1 canonical selection is finalized for the Stage3
population.

Previous candidate parameters:

- PDP
- RMS delay spread
- Doppler spread
- Ricean K-factor

Expanded candidate pool:

- Number of paths
- Mean excess delay
- Path power statistics
- Path lifetime / temporal stability

Status: `Phase-1 canonical selection completed / PASS_WITH_LIMITATIONS`; further
parameter selection for coverage-complete or physical-channel extensions remains
planned. The candidate pool must not be presented as a universal final model, and
Ricean K remains `NOT_IDENTIFIABLE`.

## 15. 论文核心贡献与研究路线更新

论文定位已从：

`SAGE-based GNSS multipath detection/characterization`

调整为：

`SAGE-based path extraction and statistical GNSS multipath channel modeling`

### Current research objective

当前论文主线是把原始 GNSS IQ 和 GNSS-SDR tracking/navigation support 连接到 NAV-aided SAGE 路径提取，再从路径级参数推导信道级参数，最终建立环境条件化的统计 GNSS 多径信道模型：

```text
raw GNSS IQ
  -> GNSS-SDR tracking/navigation support
  -> SAGE multipath path extraction
  -> path-level delay, Doppler, power, phase
  -> PDP, RMS delay spread, Doppler spread, Ricean K-factor
  -> environment-conditioned statistical GNSS multipath channel model
```

### Core contributions (target, with status boundaries)

- GNSS raw IQ measurement chain and GNSS-SDR provenance: current method/data foundation.
- NAV-aided SAGE Stage0–Stage4 reliability hierarchy: implemented and validated within the completed validation scope.
- Path-level delay/Doppler/power/phase extraction: production objective; only completed task artifacts may be presented as results.
- Channel-parameter derivation: Phase-1 r3/r2 已产出 path-level fitted parameters 与 center/channel-level derived statistics；独立、coverage-complete channel-parameter database 仍未完成。
- Environment-conditioned statistical modeling: Phase-1 Stage3 traditional model `Completed / PASS_WITH_LIMITATIONS`；更广泛的 coverage-complete 或普适模型仍未完成。

论文贡献不依赖 raw-coarse v3。v3 保留为 computational acceleration investigation、negative result 和 limitation；其 posterior coverage FAIL/Frozen 状态不作为 production selector。

### Database status and planned structure

```text
scene
  -> path
  -> channel parameter
```

- Scene metadata layer：已完成并通过 13/13 scene 覆盖检查。
- Path database：coverage-complete database 仍 Planned / Not started；Phase-1 使用的 Stage3 academic population 已审计并冻结。
- Channel-parameter database：Phase-1 closure 已有派生统计输出；独立、coverage-complete database 仍 Planned / Not started。
- Statistical model：Phase-1 canonical r3/r2 Completed / PASS_WITH_LIMITATIONS；扩展模型仍需单独授权和证据。

未来仍需完善 coverage-complete path/channel-parameter database、补充论文 Results 同步，并谨慎评估 PDP、RMS delay spread、Doppler spread 等扩展统计量。Ricean K 在当前 Phase-1 证据下保持 `NOT_IDENTIFIABLE`。禁止把 bounded Phase-1 结果写成 final dataset、普适规律或完整物理信道模型。

### Future work / Planned

1. 继续完成并 QA 通过 10.23 MHz full SAGE production tasks。
2. 建立 coverage-complete multipath path database。
3. 建立 channel parameter database，并记录 scene/environment/elevation provenance。
4. 从 path-level 参数派生 PDP、RMS delay spread、Doppler spread 和 Ricean K-factor。
5. 按环境类别及 LOW/MID/HIGH elevation 条件生成统计模型。

当前可以表述为“Phase-1 traditional statistical model completed with limitations”；不得表述为“path/channel database completed”“complete 12-cell measured coverage”或“final dataset completed”。

## 16. 论文数据库 schema 设计

已新增论文数据层 schema 设计文档：`docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md`。该文档只定义四层逻辑结构，不创建真实数据库、不迁移 SAGE 结果：

```text
scene metadata
  -> SAGE path
  -> channel parameter
  -> statistical model
```

- Scene Metadata Table：来源为 `scene_metadata_10MHz.csv`，当前 scene metadata layer 已建立。
- SAGE Path Database：保存一行一条 path 的 delay、Doppler、power、amplitude、phase 及 Stage/provenance；coverage-complete database Planned / Not started。
- Channel Parameter Database：Phase-1 closure 已提供 derived statistics，但独立、coverage-complete database Planned / Not started；Ricean K 保持不可识别。
- Statistical Model Database：r3/r2 已提供 canonical environment/elevation 模型表、分布族、联合依赖和 QA provenance；扩展数据库仍需单独设计。

Schema 文档明确区分 SAGE 直接字段、未来计算字段和论文统计字段，并规定 `scene_id` 为主关联键、`run_id/window_id/event_id/path_id` 为下层唯一性和可追溯性键。r3/r2 canonical model 已完成并通过 QA，但 schema 本身不代表 coverage-complete path database、channel-parameter database 或普适 statistical model 已完成。

## 17. 论文工作区索引

已新增 `docs/PAPER_WORKSPACE_INDEX.md`，用于集中导航论文 handoff、paper draft、scene metadata、production QA、执行记录、数据库设计和历史加速实验文档。该索引是资产导航文件，不改变任何实验状态；未列为 Completed 的项目仍保持 Planned、Implemented 或 Not started 状态。

## Paper Workspace Management Rules

论文相关状态、索引、正文草稿和数据库 schema 必须遵循以下唯一组织体系：

```text
docs/
  GNSS_SAGE_PAPER_HANDOFF_CURRENT.md
        ↓
  PAPER_WORKSPACE_INDEX.md
        ↓
  paper_draft/
        ↓
  GNSS_MULTIPATH_DATABASE_SCHEMA.md
```

### 唯一文件职责

1. `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

   论文科学方向、贡献、状态、限制和路线的唯一状态来源。

2. `docs/PAPER_WORKSPACE_INDEX.md`

   论文资产导航和文件索引。

3. `docs/paper_draft/`

   论文正文、章节草稿和写作材料。

4. `docs/paper_draft/GNSS_MULTIPATH_DATABASE_SCHEMA.md`

   论文数据库设计的唯一 schema 文档。不得创建同职责的替代 schema 文件。

### 硬性禁止规则

除非经过明确人工确认，否则禁止创建新的同类状态文件或重复路线文件，包括但不限于：

- `PAPER_PLAN2.md`
- `PAPER_STATUS_NEW.md`
- `PAPER_STATUS_FINAL.md`
- `DATABASE_DESIGN_FINAL.md`
- `DATABASE_SCHEMA_NEW.md`
- `PAPER_ROADMAP_NEW.md`

禁止为了记录临时状态创建新的 handoff、status 或 plan 文件，避免论文状态分裂。

### 新论文文件创建规则

未来只有在以下条件同时满足时，才允许新增论文文件：

1. 现有四层结构无法容纳该内容；
2. 新文件具有明确且唯一的职责；
3. 新文件必须登记到 `docs/PAPER_WORKSPACE_INDEX.md`；
4. 如果内容改变论文状态、路线、贡献或限制，必须同步更新本 handoff。

### 状态更新规则

- 论文科学状态变化：优先更新本文件。
- 论文资产、章节或设计文件变化：更新 `docs/PAPER_WORKSPACE_INDEX.md`。
- 不创建新的状态文件替代本 handoff。
- `Planned`、`Implemented`、`Validated` 和 `Not started` 不得被写成 `Completed`，除非有对应实验或 QA 证据。

任何新的实验结果、QA、方法变化或可写论文事实都必须检查并同步本文件；如果同时改变工程执行状态，则还必须同步 `GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`。工程和论文文档相互引用，但不得混用为同一状态源。

## Current production execution status (2026-08-14)

正式 A3 task `F1023_V70_D0120_P5/G16/ch1/10.23MHz` 已由用户在正常 Windows PowerShell 环境完成执行并通过独立科学 QA。其历史 immutable request 为：

`dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a3_d0120p5_g16_20260813/execution_request.json`

request SHA-256：`629e22444baa3ae7cede6584ec486312cceb7be541e443eab4c30d53dfa8a094`。

该案例现在可以作为 Pipeline Validation 的科学事实，统计为 Stage0–Stage4 完整输出、0 confirmed event 和0 confirmed path；但由于历史执行记录存在 `resume_allowed=false` 与实际 `Resume=true` 的契约偏差，不作为 Batch A continuous production 的最终放行依据，也不改变 Batch A release 状态。后续仍需新的 controlled new-only acceptance run，再按独立 QA 门禁继续生产。

独立 QA 已确认 G16 output namespace 的 artifact completeness、Stage consistency 和 scientific validity 均 PASS；相关正式结果和 QA 事实已写入 `docs/paper_draft/sections/05_Pipeline_Validation.md`。旧执行 namespace、request 和 artifact 均保持不可变，不因本次论文更新而重写或重新包装为 Batch A acceptance PASS。

## VTC2027 Paper Authoring Skill

项目级论文写作 skill 已新增：`.codex/skills/vtc2027-paper-authoring/SKILL.md`，UI metadata 位于同目录的 `agents/openai.yaml`。

- 状态：`Implemented + Validated`。
- 作用：约束 VTC2027-Spring Regular Paper 的 scope、5页预算、证据边界、Stage4 confirmed criterion、图表选择、IEEEtran/参考文献 QA、投稿节奏和最小必要步骤。
- 该 skill 不改变论文科学结果、production 状态、VTC evidence matrix、event database 或 statistical model 状态；它也不替代本 handoff 的论文科学状态唯一来源。
- 本次未运行实验、未读取 raw IQ、未运行 MATLAB/SAGE/batch，未生成 production request。

## VTC Tier-1 T1-2 G25 independent QA result (2026-08-14)

`F1023_V80_D0117_P8/G25/ch10/10.23MHz` 已完成真实 full Stage0–Stage4 production，并通过独立 QA。该结果为 Highway/Open 的一项可追溯论文证据，不代表 Highway/Open 的统计规律，也不把 HIGH planning context（mean elevation approximately 79°）写成 event-level elevation 结果。

- Execution ID：`batch_sage_execution_20260814T075945Z`；QA 报告：`docs/10MHz_FULL_SAGE_PRODUCTION_T1_2_G25_QA_REPORT.md`。
- Stage0：`1144` valid NAV symbols、`1142` complete 40 ms windows。
- Stage1：`1142` scanned、`112` selected；Stage2：`448` evaluations，final L1/L2/L3/L4=`38/13/12/49`。
- Stage3：`8` reliable centers；Stage4：`8` joint rows、`8/8` joint_valid；在固定 Stage4 confirmation criterion 下为 `2` confirmed events、`2` confirmed paths。
- confirmed path 参数可用于 bounded path-level characterization：两个事件的 excess delay 为 `1.1/1.2 samples`，relative Doppler 为约 `-4.716/-10.714 Hz`，relative power 为约 `-7.853/-11.388 dB`；这些是单任务结果，不是环境统计模型。
- 当前 10.23 MHz accepted production count 更新为 `5/67`；历史 contract-rejected A3 G16 仍不计入。Event database、channel-parameter database 和 statistical model 仍未完成。
- T1-3 Mountain/Valley 仍为必要证据缺口，状态保持 `REQUIRED / pending Commander decision`；未生成 T1-3 request，也未自动继续 production。

## Documentation Update Policy

### VTC Tier-1 T1-1 independent QA result (2026-08-14)

This supersedes the preparation-only state recorded in the T1-1 entry below. The task `F1023_V70_D0120_P9/G05/ch10/10.23MHz` completed a real full Stage0–Stage4 execution under the normal Windows-user execution chain and passed independent read-only QA. The immutable request SHA-256 is `feebda81d6f541c012d0cd898deb0142cacd3e9d28fc83deb634cf827dd9c194`; the execution log is `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T060453Z/batch_execution_log.csv`; the QA report is `docs/10MHz_FULL_SAGE_PRODUCTION_T1_1_G05_QA_REPORT.md`.

The paper-usable facts are: Stage0=`2632` valid NAV symbols and `2630` complete 40 ms windows; Stage1=`2630` scanned and `113` selected windows; Stage2=`452` model evaluations with final L1/L2/L3/L4 counts `51/44/16/2`; Stage3=`12` reliable centers; Stage4=`8` joint rows with `8/8` `joint_valid=1`; and, under the fixed Stage4 confirmation criterion, `2` confirmed events and `2` confirmed multipath paths. These are task-level extraction facts only; they do not complete the event database or statistical model and must not be generalized to the whole Special Reflective class. The LOW label is currently scene-level planning context, not an event-level elevation result.

T1-1 is now `QA_PASS / AVAILABLE` evidence for the VTC evidence matrix. The current production summary accepted count is `4/67`; the historical contract-rejected A3 G16 artifact remains excluded from that count. At the time of the T1-1 QA record, T1-2 and T1-3 had not been generated or executed; the current T1-2 preparation state is recorded below, and no automatic continuation is authorized.

### VTC Tier-1 T1-2 request preparation (2026-08-14)

Following the T1-1 evidence decision, one independent Highway/Open candidate was prepared: `F1023_V80_D0117_P8/G25/ch10/10.23MHz`, with HIGH geometry planning context and mean elevation approximately `79.0°`. The immutable request is `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_2_v80p8_g25_20260814/execution_request.json` with SHA-256 `efd3bec67010856cdf1196202369f927224403015048277f4f57116e5029bb43`. Current status is `REQUEST_PREPARED / READY_FOR_HUMAN_EXECUTION`; current inventory, unique channel mapping, input provenance, output absence, `new_only=true`, `resume_allowed=false`, and the non-MATLAB dry-run all passed.

This is a preparation fact, not a scientific result. No Stage0–Stage4 output, confirmed event/path, zero-event conclusion, LOS interpretation, or Highway/Open statistical conclusion exists for T1-2. No T1-3 request was generated. Human execution and independent QA remain required, and no statistical model or event database status changes are implied.

### VTC Evidence-Priority T1-1 request state (2026-08-14)

`F1023_V70_D0120_P9/G05/ch10/10.23MHz`（Special Reflective / LOW planning context）已完成当前队列要求的 immutable request、输入/路径/哈希 preflight 和不启动 MATLAB 的 executor dry-run。其状态为 `REQUEST_PREPARED / READY_FOR_HUMAN_EXECUTION`，不是 `RUNNING`、`COMPLETED` 或 `AVAILABLE RESULT`；当前没有新的 Stage0–Stage4 或 confirmed path 论文事实。request 位于 `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_1_d0120p9_g05_20260814/execution_request.json`，后续必须由正常 Windows 用户执行并通过独立 QA 后，才可更新论文证据矩阵。该历史 T1-1 准备记录当时尚未生成 T1-2/T1-3 request；当前 T1-2 已在上方独立记录为 Highway/Open G25 准备状态，T1-3 仍未生成。

## Experimental Setup chapter draft status

`docs/paper_draft/sections/04_Experimental_Setup.md` 已完成一次正式 Experimental Setup 章节更新，状态为 `Implemented / Draft completed`。

本次论文资产新增并确认记录了以下测量与预处理信息：

- TEST-TREE RF-Catcher V2 作为RF signal capture and playback device；
- GNSS dome antenna，RHCP，active gain 40 dB，安装于vehicle roof；
- GPS L1 C/A，中心频率1575.42 MHz，interleaved I/Q，little-endian int16；
- GNSS-SDR `item_type=ishort`、sampling frequency 10230000 Hz、GPS_L1_CA acquisition、GPS_L1_CA_DLL_PLL tracking、PLL 40 Hz、DLL 4 Hz、early-late spacing 0.5 chip，以及telemetry、observables、RTKLIB PVT、RINEX和NMEA输出。

本次更新只改变论文 Experimental Setup 资产状态，不改变 full SAGE production 执行门禁、Batch A release、event database、statistical model 或 LOW/MID/HIGH modeling 状态。时间同步、外部时钟、采集触发和UTC对齐细节当前仍未记录，论文中不得补写这些信息。

论文状态同步遵循“按影响范围更新”的规则：

- `GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`负责工程代码、路径、执行、QA、hash、manifest、环境和生产状态；工程动作不自动改写论文状态。
- `GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`只记录科学问题、研究路线、论文贡献、数据库设计、论文可用实验事实、章节状态、limitations和future work。
- `PAPER_WORKSPACE_INDEX.md`只记录论文资产结构变化，例如新增/删除/变更章节、schema、图表目录或分析文件；普通实验结果不单独触发Index更新。
- `dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv`和`production_summary_report.md`由只读production summary工具维护，用于工程生产监控，不是论文数据库，也不替代本文件。

### Paper handoff 更新条件

以下变化需要更新本文件：研究路线、论文贡献、数据库设计、章节状态，或新的论文可用事实（新scene、环境覆盖、validation、统计结果等）。如果只是新增工程工具、execution receipt或生产监控而没有新的论文事实，则不更新本文件。

### 状态和写作边界

必须区分 `Completed / Validated / Implemented / Planned / Not started / Failed-Frozen`。工程事实不能直接写成科学结论；例如应写“under current confirmation criteria, G18 produced zero confirmed multipath events”，不能写成“G18没有多径”。gold replay前预测、单任务结果和未完成数据库不能写成统计模型或最终数据集。

### 单任务同步顺序

标准顺序为：`Execution -> independent QA -> production summary -> Engineering handoff -> 判断是否产生论文事实 -> 必要时更新Paper handoff -> 判断是否产生论文资产 -> 必要时更新Paper Workspace Index`。不得因为一次实验动作而无条件同步全部文档，也不得创建新的重复handoff/status/plan文件。

### VTC Evidence-Priority T1-3 request preparation（2026-08-14）

为补齐当前VTC最小 Mountain/Valley 证据缺口，已完成唯一候选 `F1023_v90_D0117_P7/G11/ch6/10.23 MHz` 的 immutable new-only request、输入/路径/hash preflight 和不启动 MATLAB 的 executor dry-run。该任务环境类别为 Mountain/Valley，几何规划上下文为 MID，场景级几何摘要 mean elevation 为 `35.0°`；这些是实验规划上下文，不是事件级仰角结果。

- 状态：`REQUEST_PREPARED / READY_FOR_HUMAN_EXECUTION`，不是 `RUNNING`、`COMPLETED` 或 `AVAILABLE RESULT`。
- Request：`dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_3_v90p7_g11_20260814/execution_request.json`。
- Request SHA-256：`7a1361445855244ca6ed6f9f640debe1533981c7d4490bab52f45132fb170d47`。
- Dry-run：`accepted_rows=1`、`rejected_rows=0`、`matlab_invoked=false`，且 command preview 明确为 `Resume=false`。
- 当前仍无 T1-3 Stage0–Stage4、confirmed event/path 或 Mountain/Valley 统计论文事实；正常 Windows 用户执行和独立 QA 仍待完成。
- T1-1 与 T1-2 的 `QA_PASS / AVAILABLE` 状态不变；Batch A 仍不得由本次准备记录自动扩展。以上为请求准备时的历史记录，当前 T1-3 执行与 QA 状态见下文。

### VTC Tier-1 T1-3 independent QA result (2026-08-15)

T1-3 `F1023_v90_D0117_P7/G11/ch6/10.23 MHz` is now a completed, independently QA-passed scientific validation/production case for the Mountain/Valley environment class. This is a task-level evidence fact, not a statistical conclusion.

- Evidence source: `docs/10MHz_FULL_SAGE_PRODUCTION_T1_3_G11_QA_REPORT.md`
- Execution/output: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260815T132956Z/` and `scenes/F1023_v90_D0117_P7/sage_results/nav_sage_v2/G11/`
- Stage statistics: Stage0 `1292` valid NAV symbols / `1288` windows; Stage1 `1288/112` scanned/selected; Stage2 `448` evaluations with L1/L2/L3/L4=`45/16/37/14`; Stage3 `10` reliable centers; Stage4 `8` joint rows and `8/8` `joint_valid=1`
- Under the fixed Stage4 criterion, the task produced `1 confirmed event / 1 confirmed path`. This must not be interpreted as proof that the scene or satellite has no other physical multipath.
- The T1-3 result is now `QA_PASS / AVAILABLE` in the VTC evidence records. The MID/approximately-35-degree value remains scene-level planning context; it is not an event-level elevation result.
- Window-level TOW geometry join remains `Missing/Partial`, so geometry-QA-complete LOW/MID/HIGH denominators and strong elevation-conditioned claims are not yet available. Event/path aggregation and geometry/time-alignment QA remain planned; no complete database or statistical model is claimed.
- The VTC minimum evidence stop condition remains unsatisfied, and no T1-4 request is authorized. Batch/production execution decisions remain subject to Commander review.

### VTC evidence consolidation and event/path geometry QA (2026-08-15)

Following the Commander decision to stop SAGE production, the existing Tier-1 results were consolidated into a paper evidence index. This is a traceability asset for the VTC paper, not a claim that the long-term event database or channel-parameter database is complete.

- Evidence index: `docs/vtc2027_spring/evidence/vtc_confirmed_path_database.csv`; 5 confirmed path rows from T1-1 G05 (2), T1-2 G25 (2) and T1-3 G11 (1).
- Evidence summary: `docs/vtc2027_spring/evidence/vtc_evidence_summary.csv`; includes the three confirmed cases, the valid zero-event A2 G18 case, and valid Stage4 non-confirmation rows from the Tier-1 outputs.
- Geometry QA: `docs/vtc2027_spring/evidence/vtc_geometry_alignment_qa.md`; status `PARTIAL`. All five paths have provisional nearest NMEA/GSV diagnostic matches, but none is marked geometry-complete because the observation-clock/TOW-to-UTC bridge and its provenance are not frozen in the production artifacts.
- The current paper can support real dynamic GPS L1 C/A measurement evidence, NAV-aided Stage0–Stage4 hierarchy, confirmed path-level characterization, and bounded diversity across Special Reflective, Highway/Open and Mountain/Valley. It cannot yet support a geometry-QA-complete LOW/MID/HIGH comparison.
- VTC production is stopped at accepted count `6/67`. No T1-4/T1-5 request is created. Long-term event database, channel-parameter database, statistical modeling and complete elevation-conditioned modeling remain `Planned / Not started`.

### VTC manuscript evidence package (2026-08-15)

状态：`Implemented / Prepared`。在 `VTC_PRODUCTION_STATUS = FROZEN` 且不再启动新 SAGE production 的前提下，已从现有 QA-PASS 证据建立论文侧 evidence package：

- 目录：`docs/vtc2027_spring/evidence/`
- 表格源：`manuscript_tables/measurement_configuration.csv`、`manuscript_tables/experimental_evidence_summary.csv`
- 图表数据源：`manuscript_figures/representative_path_case.csv`、`manuscript_figures/hierarchical_filtering_summary.csv`、`manuscript_figures/path_characterization.csv`
- 现有 T1-1/T1-2/T1-3 证据保留 `5 confirmed paths`；G18 作为 QA-PASS 的 valid zero-event case 纳入任务汇总，不解释为物理 LOS 或无反射。
- G25 window 985 被记录为 Figure 2 primary candidate；G05 W493/W495、G25 W970、G11 W1264 保留为替代候选。Stage4 artifact 中不存在直接 Stage1 correlation metric 时，提取表明确写 `NA`，不跨阶段伪造。
- 几何状态仍为 `PARTIAL`；新包只保存 scene-level planning context，不释放 event-level elevation 或 LOW/MID/HIGH 统计结论。
- 该更新不改变工程 handoff、production manifest、request、SAGE artifact、VTC frozen 状态、event database 或 statistical model 状态；正文、`main.tex` 和 `references.bib` 未修改。

论文证据包是论文资产，不能替代长期 event/path database；统计信道模型仍为 `Planned / Not started`。

### VTC manuscript Section II update (2026-08-15)

状态：`Implemented / Draft updated`。已将 `docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md` 的 Section II 重构为正式论文结构：Measurement Platform、Signal Acquisition Configuration、Experimental Scenarios 和 Processing Overview；对应的 `docs/vtc2027_spring/manuscript/latex/main.tex` Section II 已同步。

本次内容只使用现有 evidence package、Experimental Setup 章节和项目文档中已确认的 RF-Catcher V2、GNSS dome antenna、RHCP、GPS L1 C/A、1575.42 MHz、10.23 MHz、interleaved little-endian int16 IQ 以及 GNSS-SDR processing facts。Section II 将 LOW/MID/HIGH 限定为 scene/PRN planning context，并保留 event-level geometry alignment 为 partial；未补写 IF、ADC、车辆型号或时间同步细节。

本次仅更新论文写作资产，不改变 VTC frozen 状态、production execution、request/manifest、SAGE artifact、event database 或 statistical model 状态；没有新增实验结果。`PAPER_WORKSPACE_INDEX.md` 的资产结构未变化，因此无需更新。

### VTC manuscript Section III update (2026-08-16)

状态：`Implemented / Draft updated`。已将 `docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md` 的 Section III 更新为 `NAV-aided Hierarchical SAGE Multipath Extraction`，并同步 `docs/vtc2027_spring/manuscript/latex/main.tex`。

本节包含简洁接收信号模型、NAV-aided initialization、Stage0--Stage4 hierarchical processing、严格 Stage4 confirmed criterion 以及 delay/Doppler/relative power/coherence 等 path-level output。Section III 明确区分 Stage2 `L>=2`、Stage3 reliable center 与 confirmed path，未声称新SAGE estimator、估计器最优性、收敛证明或统计信道模型。

本次是论文写作资产更新，不改变 production、VTC frozen evidence、request/manifest、SAGE artifact、event database 或 statistical model 状态；没有执行实验，也未新增 Figure X/Y 图片文件。

### VTC manuscript Section IV update (2026-08-16)

状态：`Implemented / Draft updated`。已依据冻结的 VTC evidence package，将 `docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md` 和对应 LaTeX 的 Section IV Experimental Results 从占位内容更新为受控的论文结果草稿。

本节只使用已有 QA-PASS 任务、reference-scene hierarchy evidence、`experimental_evidence_summary.csv`、`hierarchical_filtering_summary.csv`、`representative_path_case.csv` 和 `path_characterization.csv`。草稿覆盖 Stage0--Stage4 hierarchical filtering、G25 window 985 的代表性 Stage4 path、当前 5 条 confirmed path 的有限描述性范围，以及 Special Reflective/Highway-Open/Mountain-Valley 的场景级证据边界。G18 被表述为当前 Stage4 criterion 下的合法 zero-event case，reference G28 被表述为 Stage4 non-confirmation/rejection evidence；未将 Stage2 `L>=2` 或 Stage3 reliable center 写成 confirmed multipath。

当前可写的 confirmed path evidence 为 5 条（G05=2、G25=2、G11=1）。文稿明确说明这些数值是有限证据集上的 bounded descriptive observations，不构成完整统计信道模型、环境总体规律或 elevation-conditioned LOW/MID/HIGH 结论。几何对齐仍为 `PARTIAL`，因此未加入事件级仰角统计。上述文字记录的是该次 Section IV 草稿更新时 Fig. 2、Fig. 3、Fig. 4 和 Table II 尚为占位/证据包来源的状态；当前图表生成状态以下方 `VTC manuscript figure and table preparation` 条目为准。

本次只更新论文写作资产；没有运行 MATLAB/SAGE、没有读取 raw IQ、没有新建 production task，也没有修改 Engineering Handoff、production artifact、request、manifest 或 `PAPER_WORKSPACE_INDEX.md`。VTC production frozen 状态和长期 event/path database、statistical model 的 `Planned / Not started` 状态不变。

### VTC manuscript figure and table preparation (2026-08-16)

状态：`Implemented / Prepared / QA validated`。依据冻结的 VTC evidence package，已生成并纳入 LaTeX manuscript 的 Figure 1--4、Table I--II；生成脚本、输入哈希、输出哈希和 gold-blind provenance 记录在 `docs/vtc2027_spring/figures/figure_generation_manifest.json`。本次没有读取 raw IQ，也没有运行 MATLAB、SAGE 或任何 production task。

- Figure 1：端到端 measurement/processing workflow，沿用已审计的 raw IQ → GNSS-SDR → Stage0--Stage4 → confirmed path-level characterization 语义；没有增加未获证实的处理模块。
- Figure 2：G25 `F1023_V80_D0117_P8/G25/ch10`、window 985 的 Stage4 direct/secondary path-level representation。图中只使用实际 Stage4 path table 参数，不伪造不可用的 correlation/residual curve。
- Figure 3：Stage0、Stage1、Stage3、Stage4 和 confirmed-event 的 unique-object flow；Stage2 `L=1--4` evaluations 作为独立注释展示，明确不等同于 unique candidate count。
- Figure 4：五条已确认 path 的 dot/scatter observations，参数为 excess delay、relative power 和 relative Doppler；每个点对应一条实际 path，不绘制 histogram、KDE、拟合或总体分布。`path_characterization.relative_doppler_hz` 已逐行核对为 Stage4 `doppler_offset_hz`，不是绝对 `doppler_hz`。
- Table I：来自 `evidence/manuscript_tables/measurement_configuration.csv` 的紧凑测量与处理配置表。
- Table II：来自 `evidence/manuscript_tables/experimental_evidence_summary.csv` 的四个 QA-passed task-level evidence summary；LOW/MID/HIGH 明确为 scene/PRN planning context，不是 event-level elevation。

LaTeX 集成文件为 `docs/vtc2027_spring/manuscript/latex/main.tex`，图表源文件位于 `docs/vtc2027_spring/figures/`，表格副本位于 `docs/vtc2027_spring/tables/`。使用本机 TeX Live 2026 对隔离副本执行两次 `pdflatex`：两次退出码均为 `0`，最终 PDF 为 **4 pages**，无 LaTeX error、fatal error 或未解析交叉引用；仍有少量 underfull-box 排版警告，需最终 camera-ready polish 时处理。`references.bib` 未被虚构补充，正式参考文献核验仍未完成。

本次更新保留以下科学边界：当前五条 path 只支持有限的 bounded descriptive characterization；geometry alignment 仍为 `PARTIAL`；没有环境总体统计、event-level elevation 统计、multipath occurrence model 或完整 statistical channel model。G18 的 zero-event 仍仅按当前 Stage4 criterion 表述，不解释为物理上没有多径。

### VTC final figure internal-language cleanup (2026-08-17)

状态：`Implemented / QA validated`。本次仅清理正式图像中的内部证据治理标签：Figure 4 的 `Tier A+B descriptive evidence only` 已从图像源中删除；Figure 2/3 中残留的 Stage 编号展示标签已改为科学功能名称。Figure 4 仍使用同一冻结的 30 条路径、四个环境类别、三类路径参数、环境内 median 和样本数 `n`。

生成脚本、输入/输出哈希和审计记录已更新至 `docs/vtc2027_spring/figures/figure_generation_manifest.json`；manifest SHA-256=`7d5fdb66f0cec79eb5ac62e76fad2d50e42593abe066d89a89ce5cf1bc1d0512`。Figure 4 PDF/PNG、表格源数据和 evidence CSV 的数值源未改变；active manuscript/caption/figure 扫描结果均为 `0`，active figure 中 Stage 编号为 `0`。英文和中文 canonical PDF 均为 4 页，Figure 3/4 引用到渲染距离均为 1 页。

这是 presentation-only cleanup，不是新实验、科学结果或方法改变。`SCIENTIFIC_CONTENT_FROZEN=YES` 保持不变；下一步为 `VTC_WRITING_HANDOFF_CONSOLIDATION`。

#### Deferred VTC Final Polish Items

以下项目已登记为 `Deferred / Planned`，不是已完成结果：

1. P1：统一 absolute Doppler 与 relative Doppler 的术语和字段说明。
2. P2：统一 delay、excess delay、sample/chip 单位表述。
3. P3：为五条 path 的小样本描述补充谨慎措辞。
4. P4：继续保持 geometry 为 scene-level planning context，避免 event-level elevation claim。
5. P5：压缩 Section II 测量配置文字以满足投稿版面。
6. P6：压缩 Section III 方法细节，保留 Stage0--Stage4 判据。
7. P7：检查 Results 中图表与正文的优先级和重复叙述。
8. P8：核对 Introduction 的贡献表述与当前 path-extraction scope 一致。
9. P9：核对 Conclusion 不超出 bounded characterization 和 future modeling 边界。
10. P10：全文统一 zero-event operational wording，禁止 LOS/physical absence 推断。
11. P11：检查 Figure/Table 是否存在重复信息或不必要的 evidence-package复述。
12. P12：完成最终 caption 的单位、数据来源和 limitation 检查。
13. P13：统一符号、变量、单位和 LaTeX 字段名。
14. P14：补齐并核验真实参考文献元数据；不得使用虚构引用。
15. P15：完成 Abstract/Introduction/Conclusion 三处叙事闭合。
16. P16：在最终模板下重新检查五页预算和双栏浮动体布局。
17. P17：处理剩余 underfull-box、末页平衡和 camera-ready LaTeX warnings。

下一步建议：进入 `Full Manuscript Final Polish`，先处理 P1--P4 的科学术语与证据边界，再处理 P5--P17 的版面、引用和提交格式；不得由本次图表生成自动放行新的 SAGE production 或 statistical modeling。

### VTC Full Manuscript Integration and Final Polish (2026-08-16)

状态：`Implemented / Submission-candidate draft`。已将 `docs/vtc2027_spring/manuscript/VTC2027_Spring_draft.md` 与 `manuscript/latex/main.tex` 统一为英文 submission-candidate 内容，完成 Abstract、Introduction、Sections II--IV、Conclusion、三项 contribution 对齐、术语审计、图表审计和内部 claim matrix：
`docs/vtc2027_spring/manuscript/claim_matrix_vtc_final_qa.csv`。

最终稿保留的科学范围为：真实动态 GPS L1 C/A raw-IQ 测量、GNSS-SDR支持、NAV-aided Stage0--Stage4 SAGE路径提取和有限 path-level characterization。正文明确：Stage2 `L>=2`、Stage3 reliable center不是confirmed path；confirmed criterion仍为 `joint_valid=1`、`joint_multipath_count>0` 且对应Stage4 path row `is_multipath=1`。G18只表述为当前准则下的valid zero-confirmation结果。五条path只做描述性范围，不承担总体分布、概率、环境因果或统计信道模型结论。

Geometry仍为 `PARTIAL`。LOW/MID/HIGH仅作为scene/PRN metadata context；正文不再使用event-level elevation或elevation-conditioned statistical claim。当前未新增实验、production、raw读取、MATLAB/SAGE执行或统计拟合。

#### P1--P17 closure status

| Item | Status | Closure evidence / remaining action |
|---|---|---|
| P1 Doppler terminology | PASS | 正文统一 absolute carrier Doppler、relative Doppler 和 Stage4 `doppler_offset_hz`。 |
| P2 Delay terminology | PASS | 正文定义 excess delay 为相对direct path的差值，主要单位为samples。 |
| P3 Small-sample wording | PASS | 五条path仅称observed/descriptive/range，不写总体分布或趋势。 |
| P4 Geometry wording | PASS | Section IV改为 `Cross-environment Observations`，明确geometry partial和metadata context边界。 |
| P5 Section II compression | PASS | 保留测量事实，压缩GNSS-SDR产品罗列和未证实硬件信息。 |
| P6 Section III compression | PASS | 保留Stage0--Stage4及最终criterion，压缩非核心解释。 |
| P7 Results priority | PASS | Results保留层级漏斗、代表path、五条path描述和跨场景边界。 |
| P8 Contribution alignment | PASS | Introduction严格保留三项贡献，均有claim-matrix evidence。 |
| P9 Conclusion boundary | PASS | Conclusion只总结path extraction/characterization，统计模型明确为future work。 |
| P10 Zero-event language | PASS | 未使用LOS、no physical multipath或reflection-free表述。 |
| P11 Figure/Table integration | PASS | Figure 1--4、Table I--II与正文引用和编号一致。 |
| P12 Caption audit | PASS | captions说明对象、来源语义和限制；Figure 2不伪造correlation curve。 |
| P13 Symbol/unit audit | PASS | MHz、Hz、dB、s、samples及delay/Doppler变量已统一。 |
| P14 Reference audit | OPEN | `REFERENCE_VERIFICATION_REQUIRED`：`references.bib`无未经核验条目且无citation command；投稿前仍需补充并核验真实文献和背景引用。 |
| P15 Abstract/Introduction/Conclusion alignment | PASS | claim matrix逐项核对，未发现结论超出Introduction贡献的情况。 |
| P16 Five-page budget | PASS | 隔离副本两遍编译最终为4 pages，未为填满版面增加低价值文字。 |
| P17 LaTeX final technical QA | OPEN | 两遍编译无error/fatal/overfull/undefined references；仍有7个underfull-box警告及IEEE末页平衡提示，需camera-ready处理。 |

LaTeX QA记录：使用 TeX Live 2026 `pdflatex` 两遍编译，退出码均为 `0`，最终PDF为 `4 pages`；无LaTeX error、fatal error、undefined reference或undefined citation。当前真实投稿阻塞项为：作者/单位信息未确认、参考文献尚未核验补齐、末页平衡和少量underfull-box的camera-ready排版处理。

当前submission-candidate状态：`MANUSCRIPT_SCIENTIFIC_READY=YES`、`MANUSCRIPT_LANGUAGE_READY=YES`、`REFERENCES_READY=NO`、`LATEX_LAYOUT_READY=YES`、`VTC_SUBMISSION_CANDIDATE_READY=NO`。下一步仅需Commander决定是否进入参考文献核验、作者信息补齐和camera-ready格式检查；不得恢复SAGE production或启动新的实验。

### VTC Reference Verification and Citation Integration (2026-08-16)

状态：`Implemented / Validated`。已完成 VTC manuscript 的 citation-need audit、来源核验、正文引用同步和完整 BibTeX 编译链。本次只更新论文资产和本论文状态，不运行实验、不读取 raw IQ、不运行 MATLAB/SAGE/batch，不修改 production artifact、request、manifest 或 Engineering Handoff。

- 内部审计矩阵：`docs/vtc2027_spring/manuscript/reference_verification_matrix.csv`。
- `references.bib`：9 条正式条目，全部 `metadata_verified=YES`；无 placeholder、无未核验条目、无重复条目。
- 文稿引用：LaTeX 7 个 `\cite{...}` 命令、9 个唯一 citation key；引用已集中在 Introduction、Section II 的 GNSS-SDR/GPS interface 描述和 Section III 的 SAGE 方法背景。Results/Conclusion 的项目自有数字未添加外部引用。
- 审计覆盖 R1 GNSS multipath impact、R2 dynamic/vehicular multipath、R3 high-resolution estimation、R4 original SAGE、R5 SAGE channel-parameter estimation、R6 GNSS-specific characterization、R7 GNSS-SDR 和 R8 GPS L1/C/A technical source。
- Research-gap wording 保持克制：正文没有使用“no previous work has ...”等未经系统检索支持的绝对表述，三项既有贡献未扩大；SAGE引用用于方法背景，不被用来支持本项目的GNSS实验结果。

完整编译链在隔离目录执行：`pdflatex -> bibtex -> pdflatex -> pdflatex`，四步退出码均为 `0`。最终 PDF 为 `5 pages`；`BibTeX warnings=0`、LaTeX errors/fatal errors=`0`、undefined citations=`0`、undefined references=`0`、overfull boxes=`0`、underfull boxes=`7`。原有 underfull warning 未通过无意义文字或脆弱排版方式处理；五页预算满足，但末页平衡和 camera-ready 细节仍需后续审阅。

当前论文状态更新为：`REFERENCES_READY=YES`、`P14_REFERENCE_AUDIT=PASS`、`MANUSCRIPT_SCIENTIFIC_READY=YES`、`MANUSCRIPT_LANGUAGE_READY=YES`、`LATEX_LAYOUT_READY=YES`、`AUTHOR_INFORMATION_REQUIRED=YES`、`VTC_SUBMISSION_CANDIDATE_READY=NO`。未填写作者、单位或邮箱占位符；提交候选仍受作者信息和 camera-ready layout polish 阻塞。`P17` 仍为 `OPEN`（7 underfull warnings/末页平衡），不影响本轮 P14 通过。

### VTC Submission Requirements, Author Metadata and Final PDF Gate (2026-08-16)

状态：`Implemented / Validated`; `VTC_SUBMISSION_CANDIDATE_READY=NO`。本次完成了当前 VTC2027-Spring 官方 CFP、公开 TrackChair 页面和官方 IEEE Author Center 指南的投稿规则核验、作者信息门禁、轨道建议、关键词收敛、隔离编译和逐页 PDF 视觉检查。没有提交论文，没有运行实验，没有读取 raw IQ，没有运行 MATLAB/SAGE/batch，也没有修改工程或 production artifact。

- 审计文档：`docs/vtc2027_spring/submission/VTC2027_SUBMISSION_REQUIREMENTS_AUDIT.md`。
- 当前官方已确认：Regular Paper 截止日期为 `2026-09-01`；初始全文为 `5 pages`；最多 `7 pages`，超过 5 页按 CFP 规定付费；审稿不建议超过 8 页。官方 CFP：`https://events.vtsociety.org/vtc2027-spring/call-for-papers-2/`。
- 公开 TrackChair 页面可访问并列出轨道，但未公开作者可见性/匿名规则，也未在未登录页面展示实际 metadata 字段：`https://vtc2027spring.trackchair.com/`。因此 `AUTHOR_VISIBILITY_RULE=NOT_CONFIRMED`，不得猜测或填写作者。
- 轨道建议：`PRIMARY_TRACK=Positioning Technologies, Localization and Navigation`；`SECONDARY_TRACK=Signal Processing for Wireless Communications`。仅为人工选择建议，没有在 TrackChair 中实际选择或提交。
- 关键词已按 IEEE Author Center 的 3--5 项建议收敛为五项：`GNSS multipath; GPS L1 C/A; raw-IQ measurements; SAGE; delay--Doppler path extraction`。
- 标题保持：`SAGE-Based High-Resolution Multipath Characterization of GPS L1 C/A Signals in Dynamic Vehicular Environments`；未暗示完整 statistical channel model、elevation statistics 或新 SAGE estimator。
- LaTeX 只做了投稿格式范围内的最小调整：Figure 3/4 使用 `0.92\textwidth` 以避免末页只有两条参考文献；关键词由六项减为五项。作者仍保留 `AUTHOR INFORMATION TO BE CONFIRMED` 占位符。
- 隔离链 `pdflatex -> bibtex -> pdflatex -> pdflatex` 四步均为 exit code `0`；最终候选 PDF 为 4 页，位于 `docs/vtc2027_spring/submission/VTC2027_Spring_submission_candidate.pdf`，SHA-256=`A9119E0B82B60BF9EB991A80BCCFA54CE751944DDE8786A2CCBF9E63144B57C8`。逐页视觉检查通过：标题/摘要/双栏、Section II--IV、Figure 1--4、Table I--II、Conclusion 和 References 均可辨认；旧版 5 页末页严重空白问题已通过最小图幅调整消除。
- 本地 PDF QA：US Letter、portrait、unencrypted、PDF 1.7、约 239 kB、字体均嵌入/子集；导入图资源中存在 Type 3 字体，IEEE PDF eXpress/PDF Checker 尚未运行。VTC 是否要求该工具、具体 file-size/paper-size/PDF 规则仍需登录后 portal 或后续官方 final-paper instructions 确认。
- `P14_REFERENCE_AUDIT=PASS`、9 个 BibTeX 条目均被实际引用、BibTeX warnings=`0`、LaTeX errors/fatal/undefined citations/undefined references=`0`。仍有 7 个 underfull-box 警告，但逐页检查未发现影响阅读的明显断行或溢出。

当前提交门禁：`OFFICIAL_REQUIREMENTS_VERIFIED=NO`、`AUTHOR_INFORMATION_REQUIRED=YES`、`AUTHOR_METADATA_INTEGRATED=NO`、`TRACK_READY=YES (recommendation only)`、`PDF_VISUAL_QA_READY=YES`、`PDF_TECHNICAL_QA_READY=NO`、`VTC_SUBMISSION_CANDIDATE_READY=NO`。剩余阻塞为：确认初审作者可见性、取得真实作者元数据（若需要）、确认 VTC 专用模板/上传字段/文件大小/PDF compliance 规则，并在这些信息就绪后重新执行最终技术 QA。VTC 投稿仍需 Commander 人工决定；不得由本次审计触发新的 SAGE production、统计建模或 submission 操作。

### VTC Review-Driven Targeted Revision (2026-08-16)

状态：`Implemented / Validated / Submission scientific content ready`。依据 `docs/vtc2027_spring/manuscript/VTC_SUBMISSION_CANDIDATE_REVIEW.md` 的原始审查结果，完成了针对 4 个 HIGH、6 个 MEDIUM 和 3 个 LOW 问题的定向修订，并生成 `docs/vtc2027_spring/manuscript/VTC_TARGETED_REVISION_RECHECK.md`。本次只修改论文写作资产和投稿候选 PDF；没有运行实验、读取 raw IQ、运行 MATLAB/SAGE/batch 或修改任何 production artifact。

本次修订的核心变化为：

- 明确 NAV-aided 的真实含义：tracking/telemetry 提供同步与样本支持，decoded NAV symbols 用于 PRN/时间对齐、NAV wiping 和完整 40 ms Stage0 窗口构造，PRN/channel association 选择目标流；RINEX/NMEA 保留为导航/运动来源信息，不被表述为事件级几何重构。
- 将 Stage0--Stage4 从流水账改写为 WHAT/WHY 兼具的 progressive evidence hierarchy：Stage1 缩小高成本 SAGE 搜索范围，Stage2 比较局部 L=1--4 模型，Stage3 拒绝孤立/不稳定高阶解，Stage4 以约 100 ms 多快照联合一致性作保守确认。
- 将 Stage4 确认条件首先写成科学定义，再保留实现字段作为审计映射；没有把 `joint_valid`、数量字段或 `is_multipath` 写成外部真值证明。
- 明确五条 confirmed paths 仅支持 bounded descriptive path-level demonstration，不支持总体统计、环境排序、概率估计或完整 statistical channel model；G18 zero-confirmation 和 G28 Stage4 non-confirmation 语义保持不变。
- 收窄跨案例叙述为 `Observations Across the Evaluated Cases`，保留 geometry `PARTIAL` 和 LOW/MID/HIGH 的场景级规划上下文边界。

原 4 个 HIGH 问题均已 `CLOSED`；3 个 MEDIUM 保持 `PARTIALLY_CLOSED`（精确网格/容差未全部公开、Figure 2 数据密度仍紧凑、时间同步/前端信息仍未记录），但均不需要新增实验才能维持当前论文主张；其余 MEDIUM/LOW 已关闭。模拟审稿建议由 `BORDERLINE` 调整为 `WEAK ACCEPT`，这是内部审阅意见而非真实录用预测。

修订后的候选 PDF 为 5 页，四步 `pdflatex -> bibtex -> pdflatex -> pdflatex` 均 exit code=0；BibTeX warnings、最终 undefined citations/references、LaTeX error/fatal 和 overfull boxes 均为 0，仍有 7 个 underfull-box/末页留白的 camera-ready polish 项。当前论文科学内容可提交状态为 `SUBMISSION_SCIENTIFIC_CONTENT_READY=YES`，但 `VTC_SUBMISSION_CANDIDATE_READY=NO` 仍保留，因为作者/单位信息、portal/template/PDF 合规门禁尚未确认。

最新候选 PDF：`docs/vtc2027_spring/submission/VTC2027_Spring_submission_candidate.pdf`，SHA-256=`4134A3729474AAFD280048C645AFF5750FFEAA35F8F6DAE1B689BB3E8508456F`。英文 `main.tex` 仍是唯一投稿正文 source of truth；`VTC2027_Spring_CN_REVIEW.md` 已按修订后的英文稿同步，仅为用户审阅副本。Production 状态、VTC evidence freeze、event database、statistical model 和 Engineering Handoff 不因本次写作修订改变。

### VTC Final Scientific Presentation Cleanup (2026-08-16)

状态：`Implemented / Validated / Submission scientific content ready`。本轮是在 targeted revision 之后进行的最终科学表达清理；没有新增实验或科学分析，保留了原有 reviewer fixes、五条 confirmed paths、G18 zero-confirmation、G28 Stage4 non-confirmation 和既有图表数据。

保留的关键修订包括：NAV-aided 的实际输入到操作链、Stage0--Stage4 的 WHAT/WHY 逻辑、Stage2 `L>=2` 和 Stage3 reliable center 不等于 confirmed path、Stage4 约 100 ms multi-snapshot joint-consistency 动机，以及小样本的路径级范围控制。摘要已去除 Stage 编号和未来工作清单；Introduction 改为正面定义三项贡献；Conclusion 改为路径提取和路径级表征的正向总结。

正式正文清理结果：

- 删除正文、表格和 caption 中的 scene/PRN 文件名、channel、T1/A2 等内部任务标识；保留具有科学意义的 PRN 和场景名称。
- 删除 `joint_valid`、`joint_multipath_count`、`is_multipath`、`doppler_offset_hz` 等实现字段名，保留最终确认准则的科学表述。
- 删除 LOW/MID/HIGH、geometry `PARTIAL`、NMEA/GSV、TOW-to-UTC、event-level geometry 等内部几何治理叙述；正文不提出事件级仰角结论。
- Table II 收敛为 measurement/scenario、environment、PRN、confirmed events、confirmed paths；图 2--4 的 caption 和图内标签改为科学描述，未改变数据点、路径集合或参数。
- 英文 `main.tex`、Markdown draft 和中文审阅副本已同步；`PAPER_WORKSPACE_INDEX.md` 未更新，因为论文资产结构没有变化。

#### MEDIUM_FINAL_ACTION_MATRIX

| Issue | Original concern | Cleanup action | Final target status |
|---|---|---|---|
| M-01 | Exact search grids and tolerances are not fully reproducible from the five-page paper. | Retain the reproducibility-relevant 40-ms windows, approximately 100-ms joint interval, $L=1$--$4$, persistence and relative-Doppler semantics; do not invent undocumented grids or tolerances. | `PARTIALLY_CLOSED` |
| M-03 | Figure 2 remains visually compact. | Remove internal labels and defensive caption language while preserving the direct/secondary path view; no curve or new data is fabricated. | `PARTIALLY_CLOSED` |
| M-05 | Time-synchronization and additional front-end details are unavailable. | Remove internal missing-information discussion from the formal narrative; no undocumented setup detail is added. | `PARTIALLY_CLOSED` |

原 4 个 HIGH issue 仍为 `CLOSED`，原 3 个 LOW issue 仍为 `CLOSED`，MEDIUM 仍为 3 个 `PARTIALLY_CLOSED`，未为改善状态而强行关闭。模拟审稿建议保持 `WEAK ACCEPT`，不是实际录用预测。`NEW_EXPERIMENT_REQUIRED=NO`。

正式稿清理扫描（English LaTeX + Markdown manuscript body）：

```text
INTERNAL_FILE_IDS_REMAINING = 0
IMPLEMENTATION_VARIABLE_NAMES_REMAINING = 0
QA_GOVERNANCE_LANGUAGE_REMAINING = 0
UNNECESSARY_DEFENSIVE_SCOPE_STATEMENTS_REMAINING = 0
```

隔离编译链 `pdflatex -> bibtex -> pdflatex -> pdflatex` 四步退出码均为 `0`。最终 PDF 为 4 页，US Letter portrait；最终 pass 的 LaTeX/BibTeX errors、fatal errors、undefined citations/references 和 overfull boxes 均为 `0`，underfull boxes 为 `3`。逐页视觉检查确认标题、摘要、双栏正文、Table I--II、Figure 1--4、Conclusion 和 References 可读。更新后的候选 PDF 为：
`docs/vtc2027_spring/submission/VTC2027_Spring_submission_candidate.pdf`

其 SHA-256 为 `BA3412D2DBEFD33571D03210F518A3256833FC540C5075A2D805DB1E5CB0C973`。本轮仅更新论文写作资产和候选 PDF；未修改 Engineering Handoff、production summary、production manifest、request、SAGE artifact 或 VTC evidence 数值。作者信息、portal/template/PDF 合规确认和普通 camera-ready 决策仍由 Commander 处理；`VTC_SUBMISSION_CANDIDATE_READY` 不因本轮自动改为 YES。

### VTC LaTeX Asset Integration and Remaining Medium Audit (2026-08-16)

状态：`Implemented / Validated`。本轮仅审计并修复论文 LaTeX 资产路径；没有运行实验、读取 raw IQ、运行 MATLAB/SAGE/batch，未修改 production artifact、request、manifest、VTC evidence 数值或参考文献内容。

- 发现并修复 `docs/vtc2027_spring/manuscript/latex/main.tex` 中 Figure 1--4 的相对路径错误。原路径从 LaTeX 工作目录解析到不存在的 `manuscript/latex/figures/*.pdf`，会触发 pdfTeX 的 draft setting；现已统一改为从 `main.tex` 所在目录解析到唯一正式资产目录 `../../figures/`。没有复制第二套 PDF/PNG，也没有删除历史可编辑源。
- 当前 Figure 1--4 PDF/PNG 均存在且非空；逐个 PDF 可由 Poppler 正常转换，PNG 可正常打开。`figure_generation_manifest.json` 的 10 个 output 和 8 个 source 路径全部存在，实际 SHA-256 与 manifest 全部匹配。正式稿只引用 `docs/vtc2027_spring/figures/` 下的四个 PDF；`manuscript/latex/figures/` 仅保留 Figure 1 的可编辑 SVG/TikZ 源和 README，不被正文引用。
- 从 `docs/vtc2027_spring/manuscript/latex/` 作为真实工作目录执行 `pdflatex -> bibtex -> pdflatex -> pdflatex`，四步退出码均为 `0`。最终 `main.pdf` 为 4 页、US Letter；最终日志无 LaTeX error/fatal、undefined citation/reference、图片缺失或 overfull box，保留 3 个 underfull-box 警告。逐页检查确认 Figure 1、Figure 2、Figure 3、Figure 4、Table I、Table II 均实际渲染并可读。
- 当前正文清理回归仍为：`INTERNAL_FILE_IDS_REMAINING=0`、`IMPLEMENTATION_VARIABLE_NAMES_REMAINING=0`、`QA_GOVERNANCE_LANGUAGE_REMAINING=0`、`UNNECESSARY_DEFENSIVE_SCOPE_STATEMENTS_REMAINING=0`。

#### Remaining MEDIUM audit

- `M-01`：`PARTIALLY_CLOSED`。代码中可核对到 40-ms window、约 100-ms joint interval、`L=1..4`、Stage1/Stage2 搜索步长与部分 persistence/joint 参数，但五页正文仍未公开全部精确 grid/tolerance 和实现细节。本轮不把工程配置表整段搬入正文，也不猜测缺失值；建议后续仅在篇幅允许时补充最影响复现的搜索范围/步长摘要。
- `M-03`：`KEEP / PARTIALLY_CLOSED`。实际 PDF 中 Figure 2 能清楚显示 direct/secondary 的 delay--power 关系、Stage4-confirmed 标识和现有路径参数；单栏缩放后仍可读。它仍是紧凑的代表性参数图而非 correlation/residual 曲线，因此不虚构新曲线或新数据，保留为代表性 Figure。
- `M-05`：`PARTIALLY_CLOSED / NON-BLOCKING`。当前正式稿不依赖未记录的时间同步或额外前端细节来支持已有 claim；因此不重新加入内部缺失信息或未经证实的说明。若未来需要更强的时间/绝对几何结论，仍需独立资料支持。

本轮没有改变 `PAPER_WORKSPACE_INDEX.md`，因为论文资产结构未变化；没有更新 Engineering Handoff。当前 `LATEX_FIGURE_INTEGRATION_READY=YES`、`LOCAL_VSCODE_BUILD_EXPECTED_TO_SHOW_FIGURES=YES`、`NEW_EXPERIMENT_REQUIRED=NO`；`VTC_SUBMISSION_CANDIDATE_READY` 仍受作者信息、portal/PDF 合规确认和普通 camera-ready polish 门禁约束。

### VTC Chinese LaTeX Review Edition (2026-08-16)

状态：`Implemented / Validated / Review-only`。本轮新增中文 LaTeX 和中文 PDF 审阅资产；英文 `docs/vtc2027_spring/manuscript/latex/main.tex` 仍是唯一正式投稿 source of truth。没有修改英文正文、参考文献、Figure 数据、Table 数据、production artifact 或科学结论；没有运行实验、读取 raw IQ、运行 MATLAB/SAGE/batch。

- 中文 LaTeX 源：`docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.tex`。
- 中文审阅 PDF：`docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.pdf`。
- 编译器和链：XeLaTeX → BibTeX → XeLaTeX → XeLaTeX；工作目录为 `docs/vtc2027_spring/manuscript/latex_cn_review/`，四步退出码均为 `0`。
- 中文字体使用 TeX Live 自带 `xeCJK` 与 Fandol 字体；未依赖 Microsoft YaHei、SimSun 或外部下载字体。
- 中文 PDF 明确标注“VTC2027-Spring 中文审阅版（非投稿版本）”，保留作者信息占位符，不包含内部工程治理语言。
- Figure 1--4 直接引用 `docs/vtc2027_spring/figures/` 的正式 PDF；Table I--II 在中文稿中重新排版并保留英文正式稿数值；参考文献直接引用 `../latex/references.bib`，没有复制第二份 BibTeX。
- 中文 PDF 为 4 页，逐页检查确认中文文字、公式、Figure 1--4、Table I--II 和 References 均实际渲染；日志无缺字、图片缺失、LaTeX 错误、fatal error、未解析 citation/reference 或 overfull box，仅有字体样式 fallback 和 1 个 underfull-box 排版警告。
- 中文 Markdown 审阅副本 `docs/vtc2027_spring/manuscript/VTC2027_Spring_CN_REVIEW.md` 已同步为与中文 LaTeX 正文一致的完整内容，并保留用户审阅提示；中文 LaTeX/PDF 不包含这些提示。
- `docs/PAPER_WORKSPACE_INDEX.md` 已登记 `manuscript/latex_cn_review/`，明确其为 `Chinese review derivative / NOT submission source`。工程 Handoff 不更新。

关键 hash：

- English `main.tex`: `CB8BBBD9C1963334C7E01E16E6EBADBE2A13A31BCA9073F7EA8AA3DEAFB4A6CE`（本轮未修改）。
- English `references.bib`: `91EA56A3F111B100C224037EA64BBB7F90BE80A1010A97FD267983E631080345`（本轮未修改）。
- Chinese `main_cn_review.tex`: `FD7FC3DCA1A73ABDEF9257C4916BDB18B718431838B25DD6A6B34B59982DBCF8`。
- Chinese `main_cn_review.pdf`: `43DF8A319C9D7EC5E26231D7D58A0C12EF866B2907C31D6956D4B97517005F4C`。
- Chinese Markdown review copy: `0E5155E807665CE45894340A210A01A3B0A4CD9AFDE6A2399F44433B9BD55481`。

最终门禁为 `ENGLISH_MAIN_TEX_IS_SUBMISSION_SOURCE=YES`、`CHINESE_LATEX_IS_REVIEW_ONLY=YES`、`CHINESE_PDF_READY=YES`、`CHINESE_TEXT_RENDERED=YES`、`NO_MISSING_GLYPHS=YES`、`ALL_FIGURES_RENDERED=YES`、`ALL_TABLES_RENDERED=YES`、`CHINESE_REVIEW_PDF_READY_FOR_USER=YES`、`NEXT_VTC_DECISION_REQUIRED=YES`。XeLaTeX 日志中的字体样式 fallback 和 1 个 underfull-box 警告不影响文字、公式、图表或参考文献渲染。

### VTC Method Academicization and Environment Evidence Audit (2026-08-16)

状态：`Implemented / Audited`。本次只更新论文写作资产、证据 census、图形资产和论文侧状态，没有启动新的 SAGE production、读取 raw IQ 或改变任何 production artifact。

本次完成的论文资产更新：

- 英文正式源 `docs/vtc2027_spring/manuscript/latex/main.tex` 的摘要已从“五条路径/零确认案例”枚举改为真实 raw-IQ、NAV-aided preparation、SAGE path extraction、temporal/joint reliability 和 path-level parameter 的中性叙述。
- Section III 已按 signal/model、path-wise delay--Doppler SAGE、NAV-aligned observation formation、candidate screening/model-order estimation、temporal consistency/joint confirmation 重组；新增的残差更新、归一化 delay--Doppler objective、least-squares gain update、迭代停止条件和主要搜索参数均由当前 `run_nav_sage_pipeline.m` 审计支持。
- 正文和 Figure 1/Figure 3 已优先使用科学功能名称：NAV-aligned observation formation、candidate-window screening、local SAGE estimation、temporal consistency validation 和 multi-snapshot joint confirmation。内部 Stage0--Stage4 代码和 artifact 名称保持不变。
- Figure 2 caption 已收敛为科学内容描述；Figure 4 已升级为 Tier A+B 的四环境 2x2 描述图，展示 excess delay、relative power、signed relative Doppler 和 coherence 以及环境内中位数。
- 当前英文 Markdown、中文 review Markdown 和中文 review LaTeX 已同步；English `main.tex` 仍是正式正文唯一来源。中文 review PDF 的 canonical 文件当时被已有文件句柄锁定，已生成可审阅的 versioned PDF `main_cn_review_audit_20260816.pdf`，不影响投稿源。

### Environment evidence census

全量扫描当前存在的完整 Stage0--Stage4 输出后，形成：

- `docs/vtc2027_spring/evidence/VTC_ENVIRONMENT_EVIDENCE_CENSUS.csv`：18 个去重 scene--PRN--channel task；
- `docs/vtc2027_spring/evidence/VTC_ENVIRONMENT_PATH_CANDIDATES.csv`：29 条去重 Stage4 confirmed-path 候选；
- `docs/vtc2027_spring/evidence/SAGE_REPRODUCIBILITY_PARAMETER_AUDIT.md`：当前 MATLAB 实现的可复现性参数分层审计。

证据层级保持分离：Tier A 为 accepted production/controlled acceptance，Tier B 为科学上兼容的 reference/Wave validation，Tier C 为历史 baseline 或存在执行契约偏差的 artifact。主要环境比较使用 Tier A+B；G06 legacy 和有合同偏差的 A3 G16 不进入主要环境比较。

Tier A+B 的环境级描述性统计为：Urban=4 scenes/4 tasks/7 events/7 paths；Mountain/Valley=3 scenes/9 tasks/13 events/14 paths；Highway/Open=2 scenes/2 tasks/2 events/2 paths；Special Reflective=1 scene/1 task/2 events/2 paths。有效窗口和 derived observation span 均保留 provenance；由于 Stage0 窗口重叠且曝光分母未统一，当前不将 raw event/path count 写成 occurrence rate。当前 geometry alignment 仍为 `PARTIAL`，因此不形成 event-level LOW/MID/HIGH elevation 统计结论。

当前 evidence 可以支持有界的 environment-wise path-parameter description，但不能支持总体环境排序、概率分布拟合、因果解释、完整 statistical channel model 或 elevation-conditioned model。Special Reflective 和 Highway/Open 仍为边际样本覆盖；Mountain/Valley 具有最广的兼容任务覆盖；Urban 结果仍应保持描述性表述。

### Current paper-state interpretation

- `SAGE method academicization`: `Implemented / Validated against current source code`。
- `Environment evidence census`: `Completed / Audited`，仅表示已有 artifact 的汇总，不表示新实验或完整数据库已经完成。
- `Environment comparison`: `Ready for bounded descriptive comparison`，不等于 statistical modeling completed。
- `Path database`, `channel-parameter database`, `statistical model`：仍为 `Planned / Not started`。
- `Additional SAGE runs`: 本次未执行；当前 VTC Commander 的 production stop/frozen decision 保持不变。若未来需要扩大样本，必须另行获得 Commander 批准并生成新的受保护 request。

论文可直接使用的结果必须继续来自已 QA 的 Stage4 confirmed path artifact；Stage2 高阶模型、时间可靠中心、zero-event 和 geometry provisional values 不得被改写为 confirmed physical truth。

### VTC Chinese review canonicalization and Special Reflective supplement preparation (2026-08-17)

- The Chinese review derivative was restored to its canonical path `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review.pdf` after a fresh XeLaTeX/BibTeX compilation and visual verification. It is a 4-page review-only PDF with SHA-256=`32F79236D6EB72466CF85CD5F92EDD9E42814E9F676189CEA88E8F0643400A90`; Figures 1--4, Tables I--II, References, and Chinese text rendered successfully. The temporary `main_cn_review_audit_20260816.pdf` was removed after verification. English `main.tex` remains the submission source of truth.
- A single independent Special Reflective scene was prepared for possible future evidence expansion: `F1023_V70_D0122_P2/G15/ch8/10.23MHz`. The immutable request and dry-run are preparation artifacts only; no new scientific evidence or result is available. Current Tier A+B Special Reflective evidence remains one scene, one task, two confirmed events, and two paths.
- Request preparation record: `dataset_generation_logs/batch_sage_execution_requests/vtc_special_reflective_supplement_p2_g15_20260817/execution_request.json`, SHA-256=`0d8de5948101f67bfc9458785d40f876412617b2fd903d695aab2cb85abd85a5`; preflight passed and the Python-only dry-run did not invoke MATLAB. No result, QA status, event/path count, or environment conclusion was updated for the unexecuted task.
- `SPECIAL_REFLECTIVE_PAPER_DECISION` remains `PENDING / NOT DECIDED`. Figure 4 was not modified. A future decision must use independent-scene coverage and confirmed-path parameter availability, not whether a new result supports an expected trend. Event database, channel-parameter database, and statistical modeling remain `Planned / Not started`.

### VTC Special Reflective supplement G15 (2026-08-17)

- The independent supplement task `F1023_V70_D0122_P2/G15/ch8/10.23MHz` completed full Stage0–Stage4 execution and passed independent QA. The QA artifact is `docs/vtc2027_spring/evidence/VTC_SPECIAL_REFLECTIVE_SUPPLEMENT_G15_QA_REPORT.md`.
- Scientific artifact summary: Stage0 `3695` valid NAV symbols and `3687` complete windows; Stage1 `3687` scanned and `108` selected; Stage2 `432` evaluations with L1/L2/L3/L4=`42/33/10/23`; Stage3 `10` reliable centers; Stage4 `8` valid joint rows; `5` confirmed events and `5` confirmed paths under the fixed Stage4 criterion. This is a path-level evidence update, not a statistical-model result.
- Special Reflective evidence now covers `2` independent scenes, `2` tasks, `7` confirmed events and `7` confirmed paths when combined with `F1023_V70_D0120_P9/G05/ch10`. The evidence is retained in `VTC_ENVIRONMENT_EVIDENCE_CENSUS.csv`, `VTC_ENVIRONMENT_PATH_CANDIDATES.csv`, `vtc_confirmed_path_database.csv`, and `vtc_evidence_summary.csv`.
- Paper inclusion decision: `SPECIAL_REFLECTIVE_PAPER_DECISION=KEEP_IN_MAIN_ENVIRONMENT_COMPARISON`. This is a bounded descriptive inclusion decision based on independent-scene replication and usable path provenance; it does not support a fitted distribution, occurrence probability, elevation-conditioned conclusion, or complete environment characterization.
- Path-level coherence is not stored for the five new G15 Stage4 path rows and remains explicitly missing. Event-level geometry/elevation remains partial; no LOW/MID/HIGH event-level denominator is added.
- Figure 4 and Table II updates are proposals only and were not applied in this QA task. The manuscript, abstract, contributions, results and conclusion were not modified. Event database, channel-parameter database and statistical model remain `Planned / Not started`.
- The VTC Commander `STOP SAGE PRODUCTION` decision remains in force. No automatic continuation or new task is authorized by this evidence update; `NEXT_VTC_DECISION_REQUIRED=YES`.

### VTC Final Environment Integration and Scientific Freeze Candidate (2026-08-17)

状态：`Implemented / Validated / Scientific-content freeze candidate`。本轮只整合已 QA 的 G15 证据并更新论文资产；没有新建 request、读取 raw IQ、运行 MATLAB/SAGE 或修改 production artifact。

- G15 已正式合并到 `VTC_ENVIRONMENT_EVIDENCE_CENSUS.csv` 和 `VTC_ENVIRONMENT_PATH_CANDIDATES.csv`，去重后作为 Tier A、`scientific_usable=yes` 证据进入主比较。当前 census 为 19 个去重任务，path-candidate 表为 34 行，其中 Tier A+B 为 30 条 confirmed path、Tier C 为 4 条，Tier C 不进入主比较。
- 最新 Tier A+B environment coverage 为：Urban=`4 scenes / 4 tasks / 7 events / 7 paths`；Mountain/Valley=`3 / 9 / 13 / 14`；Highway/Open=`2 / 2 / 2 / 2`；Special Reflective=`2 / 2 / 7 / 7`。这些是 bounded descriptive evidence，不是 occurrence rate、环境排序或统计分布。
- Special Reflective 的最终论文决策为 `KEEP_IN_MAIN_ENVIRONMENT_COMPARISON`。G15 与原 G05 合计 2 个独立场景、2 个任务、7 个 confirmed events、7 条 confirmed paths；delay、signed relative Doppler、relative power 对 7 条路径均可用。path-level coherence 仅 `2/7` 可用，G15 的 5 条记录明确缺失，未被填充或替代。
- Figure 4 已由旧的四面板版本改为三面板：excess delay、relative power、signed relative Doppler；每个环境标注真实 path sample size 和中位数。signed relative Doppler 保留为估计源量，不将正负号解释为环境效应。Figure 4 的生成源、manifest 和 PDF/PNG 已更新，图中使用 30 条 Tier A+B confirmed path 记录；coherence 作为可用时的 supporting reliability observable，不再作为统一环境参数。
- Table II 已改为 environment coverage 表：`Environment / Independent scenes / Full-pipeline tasks / Confirmed events / Confirmed paths`，数据由当前 census 重新生成，未写入 task ID、channel、QA 或 LOW/MID/HIGH event-level geometry。
- 英文正式稿、中文 Markdown 审阅稿和中文 LaTeX 审阅稿已同步更新 Abstract、Contribution 3、Experimental Scenarios、Results、Figure 4 caption、Table II、Cross-Environment Observations 和 Conclusion。主叙事仅使用 excess delay、relative Doppler、relative power；Figure 2 仍可展示其代表性案例中真实可用的 coherence。
- 英文编译链 `pdflatex -> bibtex -> pdflatex -> pdflatex` 全部 exit code `0`，当前 `main.pdf` 为 4 页；中文 `xelatex -> bibtex -> xelatex -> xelatex` 全部 exit code `0`，canonical `main_cn_review.pdf` 为 4 页。未发现 LaTeX error、undefined citation/reference 或 missing glyph；剩余字体 fallback/underfull warning 不是 scientific blocker，且本轮已消除 Table II 的 overfull warning。
- 当前 scientific content 可标记为 `SCIENTIFIC_CONTENT_READY_TO_FREEZE=YES`（candidate）。这不等于最终投稿提交完成：作者信息、最终人工阅读和 portal/camera-ready 检查仍由作者执行。`NEXT_ACTION=USER_AUTHOR_REVIEW`。
- `SAGE_PRODUCTION_STOPPED=YES`、`NEW_EXPERIMENT_REQUIRED=NO`、`HIGHWAY_SUPPLEMENT_REQUIRED_NOW=NO`。Event database、channel-parameter database、statistical model 和 event-level geometry/elevation conditioning 仍为 `Planned / Not started` 或 `Partial`；不得在本轮更新为完成。

### VTC Coherence Semantics Correction and Scientific Freeze (2026-08-17)

状态：`Validated / Scientific content frozen`。本次是既有实现和论文派生表的语义纠正，不是新实验、新估计器或新分析方向；未读取 raw IQ，未运行 MATLAB/SAGE，未修改任何原始 Stage4 production artifact。

- `scripts/sage_pipeline/run_nav_sage_pipeline.m` 的 `replicaCoherence` 对当前拟合模型的所有 path replicas 做列归一化，计算不同 replica 之间的 normalized inner product，清除对角线后取最大值。因此 Stage2/Stage4 的 `maximum_coherence` 是 current multi-path model / joint solution 的 event/model-level separability or reliability diagnostic，不是单条 path 的 coherence。
- Stage4 `stage4_joint_summary.csv` 包含 `maximum_coherence`；`stage4_joint_paths.csv` 不包含独立的 path-level coherence 字段。`PATH_LEVEL_COHERENCE_DEFINED=NO`，`STAGE4_MAXIMUM_COHERENCE_LEVEL=EVENT_MODEL`。
- 旧的 paper-oriented path 表曾将 Stage4 summary 的 event/model 数值按 event/window join 到 path 行；在多路径事件中同一数值会重复到多条 path row。该解释已被标记为 `SUPERSEDED COHERENCE INTERPRETATION`。原始 SAGE 输出和历史 audit 保留不变。
- `VTC_ENVIRONMENT_PATH_CANDIDATES.csv`、`vtc_confirmed_path_database.csv`、`path_characterization.csv` 和代表性路径源表中的字段已改名为 `source_event_maximum_coherence`，仅表示 provenance，不再伪装为 path parameter。Figure 2 不再显示该 event/model metric；Figure 4 继续只使用 excess delay、relative power 和 signed relative Doppler 三个 path-level quantities。
- 当前论文 `claim_matrix_vtc_final_qa.csv` 的 C4 已同步改为 delay/relative Doppler/relative power 路径描述，并将 `maximum_coherence` 明确限定为联合解级诊断；历史审计快照保留原样并由本节语义覆盖。
- 当前 Tier A+B 核心 path parameter completeness：`EXCESS_DELAY_COMPLETE=YES`、`RELATIVE_DOPPLER_COMPLETE=YES`、`RELATIVE_POWER_COMPLETE=YES`，30/30 confirmed paths 均具备这三项。四环境 coverage 保持 Urban 4/4/7/7、Mountain/Valley 3/9/13/14、Highway/Open 2/2/2/2、Special Reflective 2/2/7/7。
- G15 QA PASS、Tier A、Special Reflective `2 scenes / 2 tasks / 7 events / 7 paths` 和 `SPECIAL_REFLECTIVE_PAPER_DECISION=KEEP_IN_MAIN_ENVIRONMENT_COMPARISON` 均保持不变；这些结论不依赖 path-level coherence。
- 英文正式稿、中文 LaTeX review source、中文 Markdown review copy、Figure 2/4 source 和 Figure manifest 已同步。正文中不再出现 path-level coherence、secondary-path coherence 或 G15 coherence missing 的表述。
- `SCIENTIFIC_CONTENT_FROZEN=YES`。这表示当前科学正文和语义边界已达到作者审阅冻结候选；不表示投稿门户、作者信息或最终格式提交已完成。`NEXT_ACTION=USER_AUTHOR_REVIEW`。

### VTC Writing Commander continuity

VTC论文撰写策略、Commander决策、scientific freeze、图表策略、作者审阅流程和无上下文接续规则统一登记在 `docs/GNSS_SAGE_VTC_WRITING_HANDOFF_CURRENT.md`。本文件仍负责论文科学状态和论文资产状态；不在此处复制 VTC Writing Handoff 的全文。当前 VTC 写作阶段为 `USER_AUTHOR_REVIEW`，`SAGE_PRODUCTION_STOPPED=YES`，`NEW_EXPERIMENT_REQUIRED=NO`。

### VTC Targeted Author-Review Revision (2026-08-17)

状态：`Implemented / Validated`。本轮为 manuscript-only targeted revision，未改变科学内容或证据边界。

- 英文 `manuscript/latex/main.tex` 已先完成修订，并同步到英文 Markdown、中文 LaTeX review source 和中文 Markdown review copy。
- 八项作者审阅问题均已处理：采样表述、模型阶数解释、路径量定义、G28/G18 场景上下文、G25 联合确认表述、bounded descriptive 中位数语义、观测时长/事件计数语义，以及 Figure 3 的有效 40-ms 窗口和层级确认语义。
- Figure 3 数据、Table II 数值、Figure 4 数据和所有科学判据均未修改；正文仍不声称 path-level coherence。
- English `main.pdf` 与中文 versioned review PDF 均已编译为 4 页并通过文本、引用、图表和视觉 QA。中文 canonical `main_cn_review.pdf` 因已有文件句柄锁定未被强制覆盖；QA 通过的本轮输出为 `main_cn_review_author_revision.pdf`。
- 本轮未读取 raw IQ、未运行 MATLAB/SAGE、未执行 batch/production，也未修改 production artifacts。Engineering Handoff 不需要更新；本文件和 VTC Writing Handoff 已更新以记录本轮论文资产状态。

```text
CURRENT_PHASE=USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN=YES
SAGE_PRODUCTION_STOPPED=YES
NEW_EXPERIMENT_REQUIRED=NO
AUTHOR_REVIEW_TARGETED_REVISION=IMPLEMENTED
MANUSCRIPT_SCIENTIFIC_CONTENT_CHANGED=NO
MANUSCRIPT_DATA_CHANGED=NO
FIGURE_DATA_CHANGED=NO
TABLE_DATA_CHANGED=NO
CURRENT_NEXT_ACTION=USER_AUTHOR_REVIEW
```

### VTC Figure 4 Layout and Chinese Canonical Review PDF (2026-08-17)

状态：`Validated / Implemented`。本轮仅维护英文版面和中文 review PDF canonical asset，未改变论文 scientific content。

- 英文 `main.tex` 已检查 Figure 4 源码位置、首次引用和 float 参数。当前 Figure 4 使用 `figure*`、`[!t]`、`0.92\textwidth`，在第 4 页顶部显示；下方为 IV-D、Conclusion 和 References。版面目标已满足，因此未修改正文或 LaTeX 源码。
- 英文 `main.pdf` 保持 4 页；Figure 4 数据、caption、Figure 1--3、Table I--II 和 Conclusion 均未改变。
- 已将 QA 通过的 `main_cn_review_author_revision.pdf` 文件级覆盖到 `main_cn_review.pdf`。替换后两者 SHA-256 一致，canonical 文件保留为 4 页；revision provenance copy 未删除。
- 本轮未读取 raw IQ、未运行 MATLAB/SAGE/batch/production，也未修改任何 `scenes/**/sage_results` 或其他科学 artifact。Engineering Handoff 不需要更新。

```text
FIG4_LAYOUT_CHANGED=NO
FIG4_LAYOUT_STATUS=VALIDATED_IN_PLACE
FIG4_PAGE=4
FIG4_WIDTH=0.92\textwidth
FIG4_ISOLATED_FINAL_PAGE=NO
FIG4_DATA_CHANGED=NO
FIG4_SCIENTIFIC_CONTENT_CHANGED=NO
TABLE_DATA_CHANGED=NO
ENGLISH_PAGE_COUNT=4
CHINESE_CANONICAL_REPLACEMENT=PASS
CHINESE_CANONICAL_HASH_MATCH=YES
```

### VTC P0/P1/P2 Targeted Revision (2026-08-22)

状态：`Implemented / Validated`。本轮仅按已确认的 P0/P1/P2 revision plan 修改 VTC 双语 manuscript；未读取 raw IQ、未运行 MATLAB/SAGE/batch/production，未改变科学数据或证据边界。

- English `manuscript/latex/main.tex` 完成定点修订，并同步英文 Markdown、中文 LaTeX review source 和中文 Markdown review copy。
- 信号模型、confirmed event/path 定义、Figure 1--4 术语、Figure 2 代表性数值、Figure 3 确认层级、Table I/II 术语和跨环境描述已按清单完成；Figure/Table 底层数据未修改。
- 论文标题更新为 `High-Resolution SAGE Characterization of GPS L1 C/A Multipath in Dynamic Road Environments`；中文标题同步更新。摘要、贡献点、环境分类和路径级参数表述已统一。
- Figure 1--4 已由现有脚本重新生成，仅同步显示标签和展示数值；manifest 已更新，Doppler audit 为 `all_rows_match=true`。
- 英文和中文 LaTeX 编译链均通过，PDF 均为 4 页；未发现 error、fatal、undefined citation/reference 或 overfull。剩余 underfull/字体 fallback warning 不构成科学阻塞。

```text
CURRENT_PHASE=USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN=YES
SAGE_PRODUCTION_STOPPED=YES
NEW_EXPERIMENT_REQUIRED=NO
CURRENT_WORK=VTC manuscript targeted revision
MANUSCRIPT_TARGETED_REVISION=IMPLEMENTED
MANUSCRIPT_DATA_CHANGED=NO
FIGURE_DATA_CHANGED=NO
TABLE_DATA_CHANGED=NO
NEW_EXPERIMENT_EXECUTED=NO
SAGE_EXECUTED=NO
NEXT_ACTION=USER_AUTHOR_REVIEW
```

当前标题字段以本节为最新记录；历史章节保留原样用于审计。下一步为作者最终人工审阅、投稿格式/portal 检查和 PDF compliance 检查，不自动启动新实验或 SAGE production。

### VTC User Follow-up Revision (2026-08-23)

状态：`Implemented / Validated`。根据作者对中文审阅稿的意见，英文正式稿和中文审阅稿已同步完成定点调整。

- 删除 II-A 车辆平台/车辆性能变量说明；删除 II-C 车辆特定运行条件说明。
- 将 II-C 的环境定义改为：具有显著周围反射结构的道路，记为 `Reflective-Feature`，不指向某个已证明的具体反射体。
- 删除 IV-A 中关于层级流程一般性拒绝行为的句子，保留 G28 和 G18 的实际案例描述。
- 在 Table II 中说明独立测量运行：一次独立 raw-IQ 采集记录；一个运行可包含多个 PRN 轨迹。
- 仅做语言和定义同步，科学数据、Table II 数值、Figure 数据、evidence 和 SAGE production 均未改变。
- 中英文 PDF 均为 4 页，编译和视觉检查通过。

```text
CURRENT_PHASE=USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN=YES
SAGE_PRODUCTION_STOPPED=YES
NEW_EXPERIMENT_REQUIRED=NO
CURRENT_WORK=VTC manuscript targeted revision
MANUSCRIPT_DATA_CHANGED=NO
FIGURE_DATA_CHANGED=NO
TABLE_DATA_CHANGED=NO
NEW_EXPERIMENT_EXECUTED=NO
SAGE_EXECUTED=NO
NEXT_ACTION=USER_AUTHOR_REVIEW
```

### Reflective-Feature Definition and Validation Extension Proposal (2026-08-23)

状态：wording=`Implemented / Validated`；semi-simulation/application validation=`Proposed / Not started`。

- 英文正式源、中文 LaTeX review source 和两份 Markdown 副本已同步采用证据化 `Reflective-Feature` 定义：桥梁跨越宽阔水面；城市道路邻近铁路和通信设施。该定义来自现有 human measurement metadata 与 G05/G15 QA，不声称已识别具体反射体或统一镜面反射机制。
- 计划文件：`docs/vtc2027_spring/VTC_SEMI_SIM_AND_APPLICATION_VALIDATION_PLAN.md`。推荐路线为：G18 无 Stage4-confirmed secondary path 的实测背景上注入已知路径；G25/G05 现有 Stage4 模型残差核查；基于记录的 0.5-chip early/late 配置开展 DLL 零交叉偏差和 SAGE 次级分量抵消案例。
- 应用端计划仅允许 signal-level DLL/code-tracking bias；当前没有独立定位真值，不能预先承诺 positioning/pseudorange improvement。
- 当前 manuscript scientific content 继续冻结；计划本身不改变贡献、数据或论文结论。执行需要作者/Commander 明确解冻和授权。
- 中文 `main_cn_review.pdf` 为 4 页并通过编译/视觉检查。英文版本化 `main_reflective_detail.pdf` 为 4 页并通过编译/视觉检查；canonical `main.pdf` 当前被其他进程锁定，尚未替换。

```text
CURRENT_PHASE=USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN=YES
SAGE_PRODUCTION_STOPPED=YES
NEW_EXPERIMENT_REQUIRED=NO
VALIDATION_EXTENSION_PLAN=PROPOSED_NOT_STARTED
VALIDATION_EXECUTION_AUTHORIZED=NO
SCIENTIFIC_DATA_CHANGED=NO
FIGURE_DATA_CHANGED=NO
TABLE_DATA_CHANGED=NO
RAW_IQ_READ=NO
MATLAB_EXECUTED=NO
SAGE_EXECUTED=NO
NEXT_DECISION_REQUIRED=YES
DECISION_OWNER=USER_AUTHOR_COMMANDER
```

### VTC Author Follow-up Revision: II-A, Table II, and IV-A (2026-08-23)

状态：`Implemented / Validated`。根据作者本轮中文审阅意见，英文正式稿、中文 LaTeX 审阅稿及两份 Markdown 镜像已同步完成定点修改；没有新增实验或科学数据。

- 删除 II-A 中在测量平台后提前预告环境类别的重复句，环境描述保留在 II-C 实验场景中。
- 将 Table II 标题缩短为“Measurement coverage and confirmed multipath paths.”；独立测量运行、一个运行可包含多个 PRN 轨迹以及路径计数准则移至 IV-A 正文。
- IV-A 明确写出 Reflective-Feature、Highway/Open 和 Mountain/Valley 的代表性 confirmed-multipath 保留案例，同时保留 G28 和 G18 的最终未确认案例；不改变 Figure 3 或 Table II 的数据。
- 英文 `main.pdf` 和中文 `main_cn_review.pdf` 均重新编译为 4 页；最终编译无 error、fatal、undefined citation/reference 或 overfull。英文保留 3 个 underfull warning，中文保留既有字体 fallback warning。
- 英文 PDF SHA-256=`861945F40B9F54BD02C45A00988A001DCE9A4E6ADF6470CD5BDDC2AC4DBB5A3F`；中文 PDF SHA-256=`97B153021D37C0CFADC53A0738F239525B3D27290B60A2DD217FF01F1D230FDC`。

```text
CURRENT_PHASE=USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN=YES
SAGE_PRODUCTION_STOPPED=YES
NEW_EXPERIMENT_REQUIRED=NO
CURRENT_WORK=VTC manuscript targeted revision
MANUSCRIPT_DATA_CHANGED=NO
FIGURE_DATA_CHANGED=NO
TABLE_DATA_CHANGED=NO
NEW_EXPERIMENT_EXECUTED=NO
RAW_IQ_READ=NO
MATLAB_EXECUTED=NO
SAGE_EXECUTED=NO
NEXT_ACTION=USER_AUTHOR_REVIEW
```

### VTC P1/P2 Final Canonical Overwrite (2026-08-25)

状态：`Implemented / Validated`。作者已批准采纳 P1/P2 建议；英文正式稿、中文 LaTeX 审阅稿及两份 Markdown 镜像已同步，并已覆盖正式源文件和 PDF。

- 当前英文标题为 `Hierarchical SAGE Extraction and Validation of GPS L1 C/A Multipath in Dynamic Road Environments`；中文标题同步为“动态道路环境中 GPS L1 C/A 多径的层级式 SAGE 提取与验证”。
- 已完成 P1/P2 的术语和结构修订，包括 `Reflective-Feature` 物理描述边界、`Measurement runs` 表头、确认多径保留/拒绝案例衔接、Layer 1/Layer 3 支持证据、描述性环境比较、$C/N_0$ 术语和 Figure 4 版式调整。
- 未改变 Table II 数值、Figure 1--4 底层数据、confirmed-path criterion、evidence 或 SAGE 结果；未新增实验，未读取 raw IQ，未运行 MATLAB/SAGE/production。
- 英文正式 PDF 和中文审阅 PDF 均为 4 页；无 LaTeX Error、未定义 citation/reference 或 Overfull。英文仅有少量 Underfull，中文保留既有字体 fallback warning。
- 英文 PDF SHA-256=`FF85A4B1D4D59ADADA2681D8AE6CCD9E5147ED16CA2E80A2A268EBF9E4FEA87B`；中文 PDF SHA-256=`1FAB45FA12DA3BAEBD3B99074AABDBAEE055049F34B2F89B9E8211B1FC7B1807`。

```text
CURRENT_PHASE=USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN=YES
SAGE_PRODUCTION_STOPPED=YES
NEW_EXPERIMENT_REQUIRED=NO
CURRENT_WORK=VTC manuscript targeted revision
MANUSCRIPT_TARGETED_REVISION=IMPLEMENTED
MANUSCRIPT_DATA_CHANGED=NO
FIGURE_DATA_CHANGED=NO
TABLE_DATA_CHANGED=NO
NEW_EXPERIMENT_EXECUTED=NO
RAW_IQ_READ=NO
MATLAB_EXECUTED=NO
SAGE_EXECUTED=NO
PRODUCTION_EXECUTED=NO
NEXT_ACTION=USER_AUTHOR_REVIEW
```

Engineering Handoff 不需要更新；下一步为作者最终人工审阅、投稿格式/portal 检查和 PDF compliance 检查。

### Author Decision: DLL Study Abandoned and Wording Sync (2026-08-25)

状态：`DLL study abandoned / no further execution / no paper admission`。

- 作者决定放弃 DLL code-tracking-bias 实验；不得继续运行或将已有 partial/smoke 输出写入论文。已有文件仅保留作溯源，不改变 MATLAB/SAGE/production 状态。
- 英文正式源和中文 LaTeX 审阅源已同步删除“但不将拟合路径视为物理真值”对应的最后一句；Layer 3 前面的 RSS/BIC 事实和数值未改变。未修改 Figure/Table 数据、evidence 数据或科学结论。
- 英文 `main.pdf` 已重新编译为 4 页，SHA-256=`C02C1EDBAD27AC6A01F4BAB9734F3221E537DCFEEA4147CD4661F1F7581BAE83`；中文源使用 XeLaTeX 独立 job 编译为 4 页，验证副本为 `docs/vtc2027_spring/manuscript/latex_cn_review/main_cn_review_sync_20260825.pdf`，SHA-256=`6AE8A3CE98E4B6C0BA7D3A281A1B34A6CD7AB3D0691D012101AD64ABCD361448`。由于 canonical `main_cn_review.pdf` 被其他进程占用，当前不能覆盖该 PDF；中文源及其编译辅助文件已同步，待释放文件锁后再覆盖 canonical PDF。

```text
CURRENT_PHASE=USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN=YES
SAGE_PRODUCTION_STOPPED=YES
NEW_EXPERIMENT_REQUIRED=NO
DLL_EXECUTION=ABANDONED_BY_AUTHOR
SCIENTIFIC_DATA_CHANGED=NO
FIGURE_DATA_CHANGED=NO
TABLE_DATA_CHANGED=NO
NEW_EXPERIMENT_EXECUTED=NO
RAW_IQ_READ=NO
MATLAB_EXECUTED=NO
SAGE_EXECUTED=NO
NEXT_ACTION=USER_AUTHOR_REVIEW
```

### Stage4 Path-Parameter Derivation Available for VTC Evidence (historical snapshot, 2026-08-25)

状态：`Completed / QA PASS / paper evidence available; manuscript admission pending author review`。本次仅从已通过 QA 的 event/path alignment overlay 派生描述性 Stage4 confirmed-path 参数，未运行新 SAGE 实验，未读取 raw IQ，未修改论文正文或 Figure/Table 数据。

- 参数分区：`dataset/multipath_event_database/v1/partitions/parameter_set_id=parameters_20260825_stage4_path_v1/`。
- 独立 QA：`dataset_generation_logs/multipath_event_channel_parameter_qa_20260825/qa_report.md`，结果 `PASS`。
- 当前可供论文审阅的 bounded facts：100 条 environment-ready confirmed paths、94 个 represented confirmed events、84 条 elevation-ready paths；可追溯的字段包括 excess delay、excess path length、signed relative Doppler、relative power、confirmed path count，以及环境/仰角组的 descriptive median/min/max。
- 16 条 path 缺少可靠事件级仰角，只进入环境描述，不进入 elevation summary。新的仰角统计不得与旧的 scene-level planning elevation 混用。
- 本次 VTC evidence layer 不派生 RMS delay spread、Doppler spread、Ricean K-factor、path lifetime 或 fitted distribution family；这是当时的 VTC scope snapshot。后续 Phase-1 r3/r2 已独立完成 bounded traditional statistical modeling；所有 VTC 论文数字仍需在 Evidence Matrix 中完成 claim admission 后才能写入正文。

```text
VTC_PATH_PARAMETER_EVIDENCE = AVAILABLE_QA_PASS
VTC_PARAMETER_CLAIM_ADMISSION = PENDING_AUTHOR_REVIEW
MANUSCRIPT_DATA_CHANGED = NO
FIGURE_DATA_CHANGED = NO
VTC_STATISTICAL_CHANNEL_MODEL = NOT_STARTED_FOR_VTC_SCOPE
NEXT_ACTION = AUTHOR_REVIEW_AND_EVIDENCE_MATRIX_ADMISSION
```

## 19. Environment-conditioned receiver lock-loss model (historical layer snapshot, 2026-08-26)

状态：`Completed with limitations / implementation QA PASS / bounded tracking diagnostic`。

- 基于已有 GNSS-SDR tracking 输出完成了一个按环境条件化的接收机锁定状态模型。模型使用 63 条 environment-eligible runs，明确排除缺少 `run_context.json` 的 G06 legacy run，并提取 48 个经固定去抖规则确认的诊断失锁区段。
- 模型输出位于 `dataset_generation_logs/channel_modeling/environment_lock_model_v1_20260826_r2/`，包含环境条件化的锁定暴露、失锁区段、失锁进入率和持续时间参数，以及输入/输出 hash provenance。持续时间候选族中 Gamma 按固定 AICc 规则被选中；Highway/Open 的样本支持标记为 `PARTIAL_POOLING_REQUIRED`，其余环境也保留分组支持和有限样本边界。
- 这是一项新的 receiver-level lock-loss / diagnostic simulation layer 事实，不是物理信号消失证明，不是 multipath occurrence probability，也不是从 confirmed path 推导出的路径级统计信道模型。`LOCK_BAD`、失锁持续时间和未来四路径幅度如何映射仍需独立的工程仿真假设。
- 本次结果不改变 VTC 的窄 scope，也不改变 coverage-complete path/channel parameter database 或完整暗室生成器仍未完成的边界。Phase-1 bounded traditional statistical model 的当前状态以本文件的 canonical section 为准；本层若纳入论文，应作为接收机诊断层、仿真假设和局限性材料单独审阅。
- 本次未读取 raw IQ，未运行 MATLAB/SAGE/batch，未修改生产结果；没有据此更新统计模型结论或声称完成最终数据集。

```text
ENVIRONMENT_LOCK_LOSS_MODEL = COMPLETED_WITH_LIMITATIONS
ENVIRONMENT_LOCK_MODEL_PAPER_FACT = AVAILABLE_FOR REVIEW
DARKROOM_COMPLETE_STATISTICAL_CHANNEL_MODEL = NOT_STARTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
NEXT_ACTION = AUTHOR_REVIEW_OF_BOUNDED_LOCK_DIAGNOSTIC_LAYER
```

## 20. Environment × elevation confirmed-NLOS path distribution layer (Completed with sparse prior cells + independent QA PASS, 2026-08-26)

状态：`Completed with limitations / independent QA PASS / conditional path layer`。本次从已经 QA 通过的 Stage4 confirmed multipath path 参数建立了环境×仰角条件化的候选分布层；没有运行 MATLAB/SAGE、读取 raw IQ 或声称完成最终暗室信道模型。

- 输入为 `dataset/multipath_event_database/v1/partitions/parameter_set_id=parameters_20260825_stage4_path_v1/facts/path_parameters.csv`，100 条 environment-ready confirmed paths；其中 84 条具有可靠事件级仰角，16 条只用于环境/全局父分布，不被赋予仰角。源 SHA-256=`2a44913d1c06f78d2748428b1d72f1b4712a6b5d3f33fc598a14fe17a3e3414a`。
- 新模型输出位于 `dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/`，model manifest SHA-256=`4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c`；独立 QA 为 `PASS_WITH_LIMITATIONS`，两项空单元 Urban–LOW 与 Highway/Open–LOW 明确保留为 `PRIOR_ONLY`。
- 12 个环境×仰角单元包含 36 个边际模型。固定 scene-grouped family selection 选择：`relative_delay_ns=lognormal`、signed `relative_doppler_hz=laplace`、`relative_power_db=normal`。功率保持 dB 拟合，线性相对幅度仅按 `10^(relative_power_db/20)` 派生，正 dB 值未裁剪。
- 联合依赖使用环境级 Gaussian copula，并按固定 `n/(n+10)` 向全局模型收缩；没有为稀疏单元虚构 cell-specific covariance。1000 次 scene-block bootstrap 与每单元 4096 次确定性 QA draw 已写入输出并通过审计。
- 该结果只能支撑“在确认存在多径时，环境和可用仰角条件下的 NLOS 路径相对参数分布”这一受限表述，不能单独估计多径发生率。主径/common gain、绝对功率、失锁到增益的映射、相位、path count/path lifetime 和固定四路径毫秒生成规则仍未完成；已有 receiver lock-loss model 仍是独立诊断层。

```text
PATH_DISTRIBUTION_MODEL = COMPLETED_WITH_SPARSE_PRIOR_CELLS
PATH_DISTRIBUTION_MODEL_QA = PASS_WITH_LIMITATIONS
STATISTICAL_CHANNEL_MODEL = BOUNDED_CONDITIONAL_NLOS_LAYER_ONLY
DARKROOM_GENERATOR = NOT_STARTED
EVENT_OCCURRENCE_MODEL = NOT DERIVED
PHASE_MODEL = EXTERNAL_ASSUMPTION / NOT FITTED
MAIN_GAIN_AND_ABSOLUTE_POWER = NOT DERIVED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
NEXT_DECISION_REQUIRED = AUTHORIZE SEPARATE DARKROOM COMPOSITION DESIGN OR HOLD
```

## 21. Main-path common-gain and observable fade modeling layer (Implemented + independent QA PASS_WITH_LIMITATIONS, 2026-08-26)

状态：`Implemented / PASS_WITH_LIMITATIONS / bounded modeling layer`。本次形成了一个可供后续暗室组合使用的 receiver-tracking 公共增益与可观测衰落层；它不是最终统计信道模型，也不是完整四路径生成器。

- 该层基于现有 GNSS-SDR tracking 的 C/N0、carrier lock 状态、采样计数和已核验 geometry provenance，覆盖 63 个 environment-eligible runs、307,572 个 20 ms 分析网格行和 91 个可观测 fade events，其中 30 个为右删失事件。输出位于 `dataset_generation_logs/channel_modeling/main_path_common_gain_fade_v1_20260826_r4/`，独立 QA 为 `PASS_WITH_LIMITATIONS`。
- 可写入论文/研究材料的边界事实是：common gain 是 run 内归一化的 tracking C/N0 proxy，geometry 条件只有在同 scene、同 PRN、5 s 内最近 GSV 关联通过时才使用；不能将该量表述为绝对 RF 功率或物理 LOS 路径幅度。
- 固定规则包括 3 dB/20 ms fade entry、1 dB/100 ms fade exit，以及对 LOCK_BAD、continuity gap 和记录终止的右删失处理。当前直接 fade-event 证据主要集中在 Highway/Open 的仰角 cell，其余环境×仰角 fade cell 明确采用 parent/PRIOR_ONLY 或 sparse partial pooling；因此不支持无条件的全环境/全仰角 fade 规律结论。
- 正常公共增益、可观测衰落深度和持续时间的候选族选择为 Student-t、lognormal 和 Gamma；这些是当前冻结规则下的有界经验拟合结果，不等于最终模型参数，也不构成物理传播定律。
- 该层仍未提供绝对功率、phase、NLOS activation、path count/lifetime、lock-recovery 到物理幅度的映射，也没有完成最终暗室随机四路径毫秒信号生成器。论文中不得据此写成“最终统计信道模型已经建立”。

工程/论文来源文件：`docs/MAIN_PATH_COMMON_GAIN_FADE_MODEL_V1_REPORT.md`、`dataset_generation_logs/channel_modeling/main_path_common_gain_fade_v1_20260826_r4/independent_qa_report.md` 和 `independent_qa_result.json`。本次未运行 raw IQ、MATLAB、SAGE 或 batch，未改变既有 SAGE/production artifact。

```text
MAIN_PATH_COMMON_GAIN_FADE_MODEL = IMPLEMENTED_WITH_LIMITATIONS
MAIN_PATH_COMMON_GAIN_FADE_MODEL_QA = PASS_WITH_LIMITATIONS
MAIN_PATH_COMMON_GAIN_FADE_MODEL_PAPER_FACT = AVAILABLE_FOR REVIEW
COMPLETE_STATISTICAL_CHANNEL_MODEL = NOT COMPLETED
DARKROOM_FOUR_PATH_GENERATOR = NOT STARTED
ABSOLUTE_RF_POWER = NOT_AVAILABLE
PHASE_MODEL = EXTERNAL_ASSUMPTION / NOT FITTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
NEXT_ACTION = AUTHOR_REVIEW_OF_BOUNDED_GAIN_FADE_LAYER
```

## 23. VTC conditional 3-D GMM manuscript integration (2026-08-31)

状态：`Author admitted / bilingual isolated manuscript integrated / QA PASS_WITH_LIMITATIONS`。

- 作者批准将“轨迹加权实测经验分布 + 拟合边际 PDF”图纳入当前 VTC 重构审阅稿。
- 模型仅使用 Urban 和 Mountain/Valley 两类环境以及 LOW/MID/HIGH 三个仰角区间；输入为 518 条持续路径观测、236 条轨迹、36 次测量运行和 9 个场景，其中 487 条具有有效仰角，31 条只用于环境父层估计。
- 条件模型联合使用 `log(excess delay)`、`log1p(absolute relative Doppler)` 和 relative power。模型证据与 QA 中仍保留按场景留一验证选择的 `K=3`、`kappa=16` 以及各单元支持状态；为使首次阅读者聚焦可解释结果，论文正文只表述经按场景留一验证确定的三分量三维 GMM，不再展示池化超参数或支持状态标签。
- signed-Doppler sensitivity 未显示保留符号具有明确预测优势，因此论文主变量采用 absolute relative Doppler；不得据此宣称物理符号对称。
- 英文和中文隔离稿已同步替换旧的边际分位数模型及旧 Figure 2 叙述，加入条件三维 GMM 公式、按场景留一验证、实测--拟合分布比较和结论。按作者审阅意见，摘要中的“部分池化”和超参数句、Section III-A 的跨 PRN 否定性说明、正文中的池化/稀疏支持措辞，以及 Table II 的支持状态列均已删除；科学数据、模型产物和内部 QA 记录未改动。英文 PDF 为 4 页；中文源文件已同步，因原 `main_cn_review.pdf` 被外部进程占用，新版以带日期的独立文件名完成编译验证。
- 作者进一步要求减少正文中的防御性否定表述。中英文稿已删除多普勒符号敏感性解释、GMM 分量的反射体否定说明及重复的 occurrence/complete-model 限定；结果段改为正向描述六个环境--仰角单元中共同的多普勒主峰、功率双峰和组间权重变化。Evidence Matrix 与模型 QA 中的科学边界保持不变。
- 论文不得把该群体称为 confirmed physical paths，不得把 GMM 分量解释为反射体类别，也不得宣称 occurrence model、仰角因果机制或完整随机信道模型。
- 本轮未读取 raw IQ，未运行 MATLAB/SAGE/batch，未改变现有 SAGE/production artifacts；历史 canonical `docs/vtc2027_spring/manuscript/latex/` 仍保持不变。

```text
CURRENT_WORK = VTC conditional GMM manuscript integration
MANUSCRIPT_ROUTE = ISOLATED_BILINGUAL_REVIEW
MODEL_QA = PASS_WITH_LIMITATIONS
AUTHOR_FIGURE_ADMISSION = YES
SCIENTIFIC_CONTENT_CHANGED = YES
SCIENTIFIC_DATA_CHANGED = NO
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
FORMAL_CANONICAL_MANUSCRIPT_CHANGED = NO
NEXT_ACTION = USER_AUTHOR_REVIEW
```

## 22. Fixed three-NLOS-slot activation layer (Completed with limitations + independent QA PASS_WITH_LIMITATIONS, 2026-08-26)

状态：`Completed with limitations / independent QA PASS_WITH_LIMITATIONS / generator-composition input`。本次完成的是受限的 NLOS 槽位激活与条件路径数层，不是完整暗室统计信道模型，也没有声称建立物理多径发生率。

- 该层基于 63 个 eligible runs、169,637 个 Stage0 exposure windows、94 个严格 confirmed events 和 100 条 confirmed NLOS paths；使用 confirmed event center ±2 的连续闭包作为 bounded support proxy。源和输出位于 `dataset_generation_logs/channel_modeling/nlos_slot_activation_v1_20260826_r1/`，model manifest SHA-256=`b47b2a09f9acc5f1ccd65dcf923623dbeea27e3aec3e3e3f04c2e094a3e486d2`。
- 模型采用 environment×elevation 条件的两层结构：先采样支持代理激活状态 Z，再在 active 条件下采样 confirmed event path-count K；K=0/1/2/3 对应固定三 NLOS 槽位的 `000/100/110/111` mask。slot ordering、inactive null 语义和 block-fixed contract 均已写入机器可读产物。
- 全局 confirmed event 的条件 path-count 分布为 K=1/2/3=`89/4/1`。12 个 environment×elevation cell 均有模型记录，但 Urban–LOW 和 Highway/Open–LOW 没有直接 confirmed event，稀疏/先验/partial-pooling 状态必须在论文中明确保留；零 confirmed exposure 不能写成 LOS 或“没有多径”。
- 独立 QA 通过所有 provenance、Stage4 label、exposure closure、slot contract 和 determinism 门禁，结果为 `MODEL_QA=PASS_WITH_LIMITATIONS`。该证据支持论文中描述“confirmed-support 条件下的 NLOS 槽位组合设计”，不支持无条件的物理 occurrence probability、完整信道模型或环境泛化结论。
- 本层没有从数据得到 phase、absolute RF power、path lifetime、inter-block persistence 或 lock-loss 联合物理映射；已有 lock-loss/gain 层仍是独立的 receiver diagnostic layer。最终四路径毫秒级参数表和可运行暗室生成器仍为 `Planned / Not started`。

论文材料报告：`docs/NLOS_SLOT_ACTIVATION_MODEL_V1_REPORT.md`。如未来纳入论文，应作为受限的 generator-composition method/limitation 材料审阅，不能写成“统计信道模型已完成”或“已完成暗室生成器”。本次未改变既有 manuscript、figure/table 或 VTC evidence 内容，也未运行 raw IQ、MATLAB、SAGE、batch 或 20.46 MHz 处理。

```text
NLOS_SLOT_ACTIVATION_PAPER_FACT = AVAILABLE_WITH_LIMITATIONS
NLOS_SLOT_ACTIVATION_MODEL = COMPLETED_WITH_LIMITATIONS
NLOS_SLOT_ACTIVATION_MODEL_QA = PASS_WITH_LIMITATIONS
COMPLETE_STATISTICAL_CHANNEL_MODEL = NOT_COMPLETED
DARKROOM_FOUR_PATH_GENERATOR = NOT_STARTED
PHYSICAL_OCCURRENCE_PROBABILITY = NOT_IDENTIFIED
PATH_LIFETIME_AND_PHASE = NOT_DERIVED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
NEXT_ACTION = AUTHOR_REVIEW_OF_BOUNDED_ACTIVATION_LAYER_OR_HOLD
```

## 21. Lock-state amplitude, phase, and recovery composition layer (historical layer snapshot, 2026-08-26)

状态：`Completed with limitations / implementation QA PASS_WITH_LIMITATIONS / bounded composition layer`。

- 基于已冻结的 tracking lock、common-gain、path-distribution 和 NLOS-slot parent artifacts，完成了一个独立的 receiver lock-state 到相对幅度、恢复过程和相位演化的离线组合层。最终 namespace 为 `dataset_generation_logs/channel_modeling/lock_amplitude_phase_recovery_v1_20260826_r3/`，model manifest SHA-256=`9eb1847eac27618f80475ceafe62616285a346c5da847afdb0e8f2c5fc63a3ee`；独立 QA 为 `PASS_WITH_LIMITATIONS`。
- 可供论文审阅的事实包括：48 个 environment-eligible lock events、307,572 行 20 ms common-gain grid、3,249 行 recovery traces，以及显式的 observed/right-censored/inconclusive 状态 accounting。该层使用 environment-only 的 tracking diagnostic timing；common gain 是 run-normalized C/N0 amplitude proxy，不是绝对 RF power。
- 组合契约将同一 lock envelope 施加于 path 0 和 active NLOS slots；path 0 仍只是仿真参考槽位，不等同于 physical LOS 或必然最强路径。inactive NLOS slot 使用 amplitude=0、delay/Doppler/phase=null。相位采用 `Uniform(-pi,pi)` 初始相位和 Doppler-continuous 1 ms recurrence，是外加假设而非数据拟合结果。
- 该结果不应写成硬件失锁概率、物理信号消失、绝对功率校准、物理 phase model 或完整四路径暗室生成器。强制 lock-loss stress floor 仍需外部明确假设；当前 `DARKROOM_FOUR_PATH_GENERATOR`、path lifetime/inter-block persistence 的联合建模和最终 statistical channel model 仍未完成。
- 论文材料报告为 `docs/LOCK_AMPLITUDE_PHASE_RECOVERY_MODEL_V1_REPORT.md`；如果纳入正文，应作为受限的 receiver-diagnostic/composition method 和 limitation 单独审阅，不能替代已完成的 path-level bounded distribution 层，也不能被表述为最终环境×仰角统计信道模型。

```text
LOCK_TO_AMPLITUDE_PHASE_RECOVERY_LAYER = COMPLETED_WITH_LIMITATIONS
LOCK_TO_AMPLITUDE_PHASE_RECOVERY_QA = PASS_WITH_LIMITATIONS
LOCK_TO_AMPLITUDE_PHASE_RECOVERY_PAPER_FACT = AVAILABLE_FOR_REVIEW
PHASE_MODEL = EXTERNAL_ASSUMPTION / NOT_DATA_FITTED
ABSOLUTE_RF_POWER = NOT_AVAILABLE
HARDWARE_LOCK_LOSS_CALIBRATION = NOT_AVAILABLE
DARKROOM_FOUR_PATH_GENERATOR = NOT STARTED
DARKROOM_COMPLETE_STATISTICAL_CHANNEL_MODEL = NOT_STARTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
NEXT_ACTION = AUTHOR_REVIEW_OF_BOUNDED_LOCK_COMPOSITION_LAYER_OR_HOLD
```

## Phase-1 Stage3 Academic Statistical Channel Model — Current Canonical Status (2026-08-30)

状态：Phase-1 traditional statistical modeling is now `COMPLETE_WITH_LIMITATIONS`；scientific closure 为 `PASS_WITH_LIMITATIONS`，bounded journal/thesis evidence 为 `READY_WITH_LIMITATIONS`。本节是当前传统建模科学结论的最新来源；前述专题层仍保留其各自的边界，不被合并成完整暗室生成器。

- 冻结 canonical model 为 `dataset_generation_logs/channel_modeling/environment_elevation_stage3_path_model_v1_20260829_r3/`，model manifest SHA-256=`61c4b3aa171b6a59d17607394770b684251d656eeb19813ca13ebed2454b1782`，r3 independent QA=`PASS`。Phase-1 closure 结果位于 `dataset_generation_logs/channel_modeling/phase1_scientific_closure_20260830_r2/`，closure manifest SHA-256=`45282b4eb5f86e52f4cd39f9b94f04c1596b645cae3d0b6420a089717f429d52`，独立 QA 为 `PASS`（75 项）。
- Closure 使用 783 条 academic Stage3 reliable/persistent path observations、445 centers、366 algorithm-level tracks、716 elevation-ready observations、50 runs、12 scenes 和 18 PRNs；主统计单位为 `WEIGHTED_OBSERVATION`，权重为 `1 / algorithm_track_size`，不把 row 当作独立样本，使用 scene/run clustering、scene-block bootstrap 和 grouped LOSO。
- 全局候选族为 excess delay=`Lognormal`、signed relative Doppler=`Normal`、relative power=`Normal`。全局三参数 environment effect=`INCONCLUSIVE`，正式 LOW/MID/HIGH elevation effect=`INCONCLUSIVE`；environment×elevation interaction 采用 difference-in-differences、scene-block bootstrap 和 leave-one-scene-out，整体为 `PARTIAL`。12 个 cell 的支持分类保持 5 `DATA_SUPPORTED`、4 `SPARSE_PARTIAL_POOLING`、2 `PRIOR_DOMINANT`、1 `NO_DIRECT_SUPPORT`；Highway/Open–LOW 无直接支持且未作 synthetic fill。
- Stage4 的 100 条 strict-confirmed paths 仅作 selection-sensitivity subset，不是 external truth；delay/Doppler/power 的参数级比较中 2/3 为 `MATERIAL_DIFFERENCE`。path-level fitted parameters 与 center/channel-level derived statistics 分开；conditional RMS spread、power-weighted centroid、component count、relative power 和 algorithm-observed persistence 可审阅，但 persistence 不是 physical reflector lifetime，`RICEAN_K = NOT_IDENTIFIABLE`。
- Joint dependence 的 AI motivation=`STRONG`（尤其 delay–relative-power 的全局关联），但 continuous elevation=`CONDITIONAL`，Phase 2 仍是 planned-only，未训练 MDN/normalizing flow，也未冻结 AI architecture。当前 evidence 可用于有边界的 journal/master-thesis traditional-modeling 结果；不得扩展成 universal propagation law、complete 12-cell coverage、absolute RF power、physical K-factor 或完整暗室生成器结论。
 - 论文证据计划和 derived plot data 在 closure namespace 内，Figure/Table 已按 `CORE`、`SUPPLEMENTARY`、`THESIS_ONLY` 排序。VTC2027-Spring 主文仍遵循较窄的 measurement-to-SAGE path-characterization scope；本次未修改 manuscript body、既有 VTC evidence matrix、Rain/Darkroom artifacts 或 SAGE production artifacts。长期论文的 model results 已完成，但 Results 正文同步仍为 `Pending / In progress`。

```text
PHASE_1_TRADITIONAL_MODEL_BUILD = COMPLETE
PHASE_1_TRADITIONAL_STATISTICAL_MODELING = COMPLETE_WITH_LIMITATIONS
PHASE_1_SCIENTIFIC_CLOSURE = PASS_WITH_LIMITATIONS
JOURNAL_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
MASTER_THESIS_TRADITIONAL_MODELING_EVIDENCE = READY_WITH_LIMITATIONS
ENVIRONMENT_EFFECT = INCONCLUSIVE
ELEVATION_EFFECT = INCONCLUSIVE
ENVIRONMENT_ELEVATION_INTERACTION = PARTIAL
AI_JOINT_DENSITY_MOTIVATION = STRONG
CONTINUOUS_ELEVATION_FOR_PHASE2 = CONDITIONAL
PHASE_2_EXECUTION_AUTHORIZED = NO
DARKROOM_GENERATOR = NOT_STARTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
NEXT_DECISION_REQUIRED = AUTHORIZE PHASE-2 DESIGN/TRAINING OR HOLD; no automatic execution
```
