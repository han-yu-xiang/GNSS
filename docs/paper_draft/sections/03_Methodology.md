# 3 Methodology

## 3.1 Overall framework

本文建立一条从真实动态车辆 GNSS 原始观测到统计信道描述的处理链：

```text
GNSS raw IQ
    -> GNSS-SDR preprocessing
    -> NAV-aided SAGE
    -> Stage0–Stage4 hierarchical evidence framework
    -> confirmed multipath path
    -> path-level parameters
    -> statistical GNSS multipath channel modeling
```

其中，SAGE 是从接收信号中提取传播路径的高分辨率工具，而不是本文的最终研究目标。本文关注的是：基于真实动态车辆 GNSS 原始 IQ 数据，获得路径级 delay、Doppler、power 和 phase 等参数，并进一步研究这些参数如何在环境和卫星仰角条件下形成统计性的 GNSS 多径信道模型。因而，路径提取、可靠性验证和信道参数推导被视为相互衔接但具有不同证据层级的步骤。

## 3.2 GNSS raw IQ measurement and NAV-aided preprocessing

研究输入为 GNSS L1 C/A 原始复数 IQ 采样，以及由 GNSS-SDR 对同一观测进行跟踪和导航解析后产生的辅助结果。对于每个 scene–PRN 任务，处理链使用冻结的 tracking channel 及其对应的 telemetry、navigation message、trajectory 和 satellite geometry provenance。本文不在方法描述中假设未由数据源明确提供的硬件参数；采样率、文件位置和输入完整性由 scene metadata、inventory 及每次执行的 manifest 记录。

GNSS-SDR 输出在方法链中承担不同作用。tracking 结果提供卫星通道的跟踪状态及与载波、码相关的低层观测；telemetry 和导航消息提供 NAV bit/symbol 序列及其时间关联；trajectory 用于后续把观测窗口与车辆运动条件关联；satellite geometry 用于提供可用的卫星仰角、方位角及相关几何 provenance。导航信息在 SAGE 前处理中主要用于三项任务：

1. 对接收信号进行 NAV symbol 对齐或确定可用的 symbol 边界；
2. 构造连续且时间定义明确的观测窗口，形成可比较的 40 ms 分析母集；
3. 为后续相关搜索和参数估计提供时间、符号及已知信号结构约束。

这些输入只定义观测和搜索的合法范围，并不预先把窗口标记为 LOS 或多径。几何和环境字段还必须经过时间对齐与完整性 QA，不能用 scene 或 PRN 的汇总均值替代窗口级信息。

## 3.3 Hierarchical SAGE-based multipath extraction framework

本文不把多径分析简化为一次性的“有/无多径”判断，而是使用逐级累积的证据框架。每个 Stage 有明确的输入、输出和状态语义；前一阶段产生的候选不能直接被解释为最终物理结论。

### Stage 0: NAV symbol alignment and valid observation window construction

Stage 0 使用 tracking、telemetry/navigation 和相关时间信息完成 NAV symbol 对齐，构造有效的观测窗口。当前生产链以连续的 40 ms window 作为后续分析母集，并保存有效 NAV symbols、窗口起始位置及其时间映射。Stage 0 的作用是保证输入窗口在信号和时间意义上可分析；它不执行多径判定，也不产生 confirmed multipath 标签。

### Stage 1: Correlation-based candidate screening

Stage 1 对 Stage 0 形成的窗口执行 NAV wipe 及基于相关的快速 delay/Doppler 扫描，识别可能需要进一步建模的 candidate window。该阶段的输出是计算筛选结果和候选集合，candidate 仅表示“进入下一层分析”的资格，不等于多径，更不等于 confirmed multipath。当前论文数据生产主线保留全量 Stage 0 母集，并由已验证的 full-scan Stage 1–Stage 4 pipeline 产生完整证据链；未经后验覆盖验证的 coarse/sampled selector 不承担生产筛选职责。

### Stage 2: Fractional delay and Doppler estimation using SAGE

对 Stage 1 候选窗口，Stage 2 使用 fractional SAGE 对接收信号进行多路径参数估计和模型比较。可用的复基带观测可抽象表示为：

\[
r(t)=\sum_{k=1}^{L} \alpha_k s(t-\tau_k)\exp\{j(2\pi f_k t+\phi_k)\}+n(t),
\]

其中，\(\tau_k\) 表示第 \(k\) 条路径的 delay，\(f_k\) 表示 Doppler，\(\alpha_k\) 表示复幅度的幅值尺度，\(\phi_k\) 表示相位，\(s(t)\) 表示经 NAV/码结构约束的已知信号，\(n(t)\) 表示噪声及未建模残差。Pipeline 对 \(L=1,2,3,4\) 的模型进行 fractional delay/Doppler 估计和选择，并保存模型评估及最终选择结果。

需要特别区分模型阶数和物理确认：选择 \(L\geq2\) 只说明多分量模型在当前窗口的拟合或证据评估中被保留，不能单独解释为 confirmed multipath；同样，\(L\geq3\) 也不是最终确认条件。

### Stage 3: Temporal persistence validation

Stage 3 将相邻或相关窗口的 Stage 2 结果进行时间连续性检查，形成 reliable centers。主要检查维度包括：

- delay 的连续性；
- Doppler 的一致性；
- path power 的稳定性；
- 邻近窗口中证据的持续性。

Stage 3 的 reliable center 是持续性候选或可靠中心，不等于 confirmed multipath。只有在更高层 joint 结果和路径表条件同时满足时，才能进入本文的 confirmed event/path 数据。

### Stage 4: Multi-snapshot joint estimation and confirmed path identification

Stage 4 在多个快照上执行 joint 100 ms 估计，用于检验候选路径在更长时间联合观测中的一致性，并识别可写入事件/路径数据库的有效路径。当前项目采用的 confirmed criterion 保持不变：

```text
joint_valid = 1
AND joint_multipath_count > 0
AND path table contains a valid row with is_multipath = 1
```

三个条件必须同时成立。Stage 4 的 header、joint row 或非空输出本身不足以构成 confirmed multipath；对于合法的 zero-event 输出，应保留其完整的 Stage 证据和状态，而不把它改写成没有传播效应的物理结论。

## 3.4 Path-level parameter extraction

对满足当前 confirmed criterion 的路径，方法链从 Stage 2/Stage 4 的路径级输出中提取或整理以下参数：

- delay；
- Doppler 及相对 Doppler offset；
- relative power 或由复幅度得到的功率尺度；
- phase；
- 在具有连续窗口关联证据时的 path lifetime 或 temporal stability。

这些字段以 `scene_id`、PRN、tracking channel、window/event/path identity 及源 artifact provenance 进行关联。路径级参数是后续信道参数派生和统计建模的输入，不意味着当前项目已经完成 path database 或 channel parameter database。对于尚未具备可靠窗口级时间、几何或环境关联的字段，应保留缺失状态和 provenance，而不能用默认值填充。

## 3.5 Statistical GNSS multipath channel modeling framework

在 coverage-complete 的多场景路径数据基础上，本文计划把路径级参数转换为候选信道统计特征，包括：

- Power Delay Profile (PDP)；
- RMS delay spread；
- Doppler spread；
- Ricean K-factor；
- path count；
- mean excess delay；
- path lifetime 或 temporal stability；
- path power statistics。

这些量构成 candidate parameter pool，而不是已经确定的最终模型参数。最终保留哪些参数，将根据多场景 production 数据的统计稳定性、物理可解释性、变量关系和论文模型需求进行筛选。计划中的统计建模还将结合 scene environment、车辆速度、CN0 以及 LOW/MID/HIGH 卫星仰角分区；当前尚未完成这些分区的统计估计、置信区间、分布选择或模型验证，因此不能把本节写成已经得到统计规律或已经建立最终模型。

本章方法框架的验证边界也需要明确：已验证的是 NAV-aided full SAGE Stage0–Stage4 处理链及其逐任务可复现执行门禁；path/channel 数据库、跨场景统计信道模型和任何加速 sampled pipeline 仍属于 Planned、Implemented 或 Not started 项目，必须以相应的后续 artifact 和 QA 结果为准。
