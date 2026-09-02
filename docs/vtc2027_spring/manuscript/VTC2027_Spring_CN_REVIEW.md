# 动态道路环境中 GPS L1 C/A 多径的层级式 SAGE 提取与验证

本文件是当前英文 LaTeX 稿的中文审阅副本。英文 `main.tex` 是正式投稿正文的唯一来源；本文件与 `main_cn_review.tex` 仅用于人工审阅，不改变实验或结果状态。

## 摘要

从真实动态道路原始 IQ 测量中表征 GNSS 多径具有挑战性，因为反射分量会随运动演化，而接收机层面的指标不能直接分辨单条传播路径。本文评估一种导航数据辅助的层级式 SAGE 框架，用于 GPS L1 C/A 原始 IQ 测量。跟踪和遥测产品结合解码后的导航数据比特，为导航比特擦除和有效 40 ms 观测窗口构造提供 PRN/时间对齐，PRN/通道关联用于选择目标信号流。候选窗口筛选、分数时延—多普勒 SAGE 估计、时间一致性验证以及多快照联合确认逐步收敛路径集合。本文通过实测背景上的受控注入路径恢复和原生 $L=1$ 与选定模型的比较来评估估计器行为。已确认路径提供超额时延、相对多普勒和相对功率估计，用于在四类所评估道路环境之间进行路径级比较。

**关键词：** GNSS 多径；GPS L1 C/A；原始 IQ 测量；SAGE；时延—多普勒路径提取。

> 【用户审阅提示】请重点审阅：摘要是否准确表达真实测量、路径级参数和四类道路环境的描述性比较，且没有扩大为总体统计结论。

## I. 引言

全球导航卫星系统支持车辆导航和智能交通，但动态道路环境中的反射会使接收信号随时间变化 [@eissfeller1996gpsdynamic; @mora1998multipath; @beitler2015cmcd]。建筑物、地形、车辆和其他结构可能引入传播分量；随着天线移动，这些分量的时延、多普勒和功率也会发生变化。载波与噪声密度比（$C/N_0$）、伪距残差和定位误差可以作为接收机层面性能退化的有用指标，但它们不能直接揭示造成某次观测的传播分量 [@bilich2007snr; @xie2011vehicular; @beitler2015cmcd]。

因此，真实动态原始 IQ 测量需要一种路径级分析方法，用于区分相关候选、具有时间支持的分量以及经过联合确认的路径。已有的高分辨率参数提取方法为测量信号和传播观测之间提供了连接 [@fleury1999sage]。本文将这一基础应用于导航数据辅助的层级式处理流程，将候选筛选、时间一致性和多快照联合确认组织为路径分辨的多径估计。

本文有三项贡献：

1. 给出真实 GPS L1 C/A 原始 IQ 测量与处理链，将 GNSS-SDR 跟踪产品与导航数据辅助的观测形成结合起来。
2. 评估一个具有逐级候选筛选、时间一致性检查和多快照联合确认的导航数据辅助层级式 SAGE 处理框架。
3. 通过受控注入路径恢复和原生模型拟合支持评估估计器行为，并针对具有代表性的动态道路环境，对 SAGE 提取路径的超额时延、相对多普勒和相对功率进行基于测量的路径级比较。

> 【用户审阅提示】请重点审阅：三项贡献是否保持正面、克制，并将 SAGE 表述为路径提取框架，而不是新的估计器或已完成的完整信道模型。

## II. 测量与实验设置

### A. 测量平台

测量平台使用 TEST-TREE RF-Catcher V2 射频信号捕获与回放设备以及一副 GNSS 圆顶天线。该天线为右旋圆极化（RHCP），有源增益为 40 dB，并安装在车辆车顶。

### B. 信号采集配置

测量信号为 GPS L1 C/A，中心频率为 1575.42 MHz [@gpsis200n2022]。原始样本以交错同相/正交（I/Q）数据形式存储，采用小端有符号 16 位格式。本文分析的测量数据采用 10.23 MHz（10230000 Hz）采样率。

### C. 实验场景

测量覆盖四类道路环境：密集城市道路、山地/谷地道路、开阔/高速道路，以及包含显著周围结构或表面、可能支持较强反射的 Reflective-Feature 场景。在本文数据中，该类别包括跨越宽阔水面的桥梁场景，以及邻近铁路和通信设施的城市道路场景。

### D. 处理流程概览

整体测量与处理框架如图 1 所示。原始捕获数据经 GNSS-SDR 跟踪和导航解码，进入 NAV 对齐观测形成、候选筛选、时延—多普勒估计和路径确认。GNSS-SDR 支持链遵循可配置软件定义 GNSS 接收机架构的既有描述 [@fernandez2011gnsssdr]。详细的估计和确认逻辑在第三节介绍。

**表 I. 测量与处理配置**

| 项目 | 配置 |
|---|---|
| 采集设备 | TEST-TREE RF-Catcher V2 |
| 天线 | GNSS 圆顶天线；RHCP；车顶安装 |
| 信号 | GPS L1 C/A；中心频率 1575.42 MHz |
| 采样率 | 10.23 MHz（10230000 Hz） |
| IQ 格式 | 交错 I/Q；小端有符号 int16 |
| GNSS-SDR 支持 | 用于观测准备的跟踪和导航支持 |
| SAGE 处理链 | NAV 对齐观测形成、候选筛选、局部 SAGE 估计、时间一致性和联合路径确认 |

**图 1.** 测量与处理流程：从动态射频捕获，经跟踪和 NAV 解码，到 NAV 对齐观测形成、候选筛选、时延—多普勒估计、时间验证、多快照确认和超额时延/相对多普勒/相对功率。

> 【用户审阅提示】请重点审阅：硬件、天线、GPS L1 C/A、1575.42 MHz、10.23 MHz、I/Q 格式和动态环境表述是否与已确认资料一致。

## III. 导航数据辅助的层级式 SAGE 多径估计

### A. 信号与多径模型

SAGE 估计遵循空间交替广义期望最大化（space-alternating generalized expectation-maximization）框架 [@fessler1994sage]，以及该方法在移动无线信道高分辨率参数估计中的既有应用 [@fleury1999sage]。接收复基带信号表示为

\[
r(t)=\sum_{\ell=0}^{L-1}\alpha_\ell s(t-\tau_\ell)\exp(j2\pi\Delta f_\ell t)+n(t),
\]

其中，$L$ 为模型中的总分量数，$\ell=0$ 表示直达分量。直达路径时延 $\tau_0$ 是时延参考；多普勒偏移相对于直达分量定义，因此 $\Delta f_0=0$。每个分量具有复增益 $\alpha_\ell$、时延 $\tau_\ell$ 和相对多普勒偏移 $\Delta f_\ell$；复增益包含幅度和相位。因此，$L=1$ 表示仅含直达分量的模型，$L=2$ 表示直达分量加一条次级分量。

### B. 基于 SAGE 的时延—多普勒参数估计

对于第 $i$ 次迭代中的第 $\ell$ 条路径，代码先从观测中减去其他路径的当前合成贡献，形成隐藏信号

\[
r_\ell^{(i)}(t)=r(t)-\sum_{k\ne\ell}\hat{\alpha}_k^{(i)}q(t;\hat{\tau}_k^{(i)},\hat{\Delta f}_k^{(i)}),
\]

其中 $q(\cdot)$ 为带分数时延和多普勒的码复制。随后以归一化时延—多普勒相关目标细化当前路径：

\[
(\hat{\tau}_\ell,\hat{\Delta f}_\ell)=\mathop{\arg\max}_{\tau,\Delta f}\frac{|q(\tau,\Delta f)^H r_\ell^{(i)}|^2}{q(\tau,\Delta f)^Hq(\tau,\Delta f)}.
\]

粗网格相关由 FFT/IFFT 实现，局部细化使用显式分数时延复制；随后通过当前复制矩阵的最小二乘求解更新复增益。最多迭代 10 次，或当残差 RSS 的相对变化低于 $10^{-6}$ 时停止。局部 SAGE 时延网格步长为 0.1 sample（0.01 chip），邻域半宽为 0.8 sample；局部多普勒范围为相对跟踪估计的 $\pm30$ Hz，步长为 5 Hz。

### C. 导航数据辅助的观测形成

特定通道的跟踪和遥测信息提供同步与样本支持。解码后的导航数据比特提供与 PRN 和时间对齐的已知序列，用于导航比特擦除和完整 40 ms 观测窗口构造；PRN/通道关联用于选择目标跟踪信号流。由此形成的有效观测窗口构成后续候选筛选和估计的输入集合。在 10.23 MHz 下，采样与 C/A 码片的关系为每码片 10 个样本。

### D. 候选筛选与局部模型阶数估计

候选窗口筛选使用 $\pm125$ Hz、25 Hz 步长的主多普勒搜索、局部相关细化，以及受跟踪得到的相对多普勒界约束的残差搜索。筛选结果缩小了进入高成本局部 SAGE 拟合的窗口集合。对每个筛选窗口评估 $L=1,2,3,4$ 的分数时延—多普勒模型。阶数逐级增加必须满足模型有效、高阶模型使 BIC 降低至少 10，且增量 RSS 降低至少为 0.002\%。较高模型阶数表明引入额外信号分量能够改善局部观测的模型表示，而最终路径确认还需满足时间一致性和多快照联合验证。

### E. 时间一致性与多快照联合确认

时间验证在相邻窗口之间比较路径时延、多普勒和相对功率。当候选在半径 2 的窗口范围内形成至少 3 个连续匹配窗口，且容差分别为 1.5 samples、40 Hz 和 10 dB 时，将其保留为时间一致候选。对于最终联合确认，以每个时间一致候选为中心的 100 ms 区间被划分为连续的 5 个 20 ms 快照。联合模型选择使用相同的 BIC 降低规则；只有在 5 个快照中至少 4 个支持高阶模型时，才保留该高阶模型。只有有效的联合解中次级分量满足最终联合确认条件时，才保留为已确认多径路径；局部高阶选择和时间一致候选仍属于中间证据。

以直达分量（$\ell=0$）为参考，分量 $\ell$ 的超额时延定义为 $\Delta\tau_\ell=\tau_\ell-\tau_0$，主要以 samples 表示；chip 数值由单位换算得到。相对多普勒（$\Delta f_\ell$）表示相对于直达分量的多普勒偏移，而不是绝对载波多普勒。对于联合估计，相对功率由 5 个快照上的平均路径功率计算，并以直达分量归一化。上述参数用于表征所评估环境中的已确认传播路径。一个已确认事件表示一个通过联合确认的观测区间，其中可包含一条或多条已确认次级路径。

> 【用户审阅提示】请重点审阅：NAV 的实际作用链、候选筛选/局部估计/时间验证/联合确认的功能边界，以及约 100 ms 联合确认的科学动机。

## IV. 实验结果

### A. 层级式路径提取行为

为表征候选分量在处理链中的逐步收敛过程，本文总结了有效的 40 ms 观测窗口、筛选候选、时间一致候选以及最终联合确认结果。图 3 展示了三个最终保留已确认多径路径的代表性案例，分别来自 Reflective-Feature、Highway/Open 和 Mountain/Valley 环境（G05、G25 和 G11）。相对地，在 Mountain/Valley 的 G28 轨迹中，时间一致候选在多快照联合确认阶段被拒绝；而在 Urban 的 G18 轨迹中，最终联合确认后没有候选保留为已确认多径事件。因此，这些案例同时展示了确认多径的保留和最终未确认的情况；环境间的路径特征比较则基于表 II 和图 4 汇总的确认路径。

其中，一次测量运行指一次单独的原始 IQ 采集记录；同一次运行可以分析多个 PRN 轨迹；路径仅在联合确认准则下计数。

**表 II. 测量覆盖与已确认多径路径。**

| 环境 | 测量运行数 | 分析 PRN 轨迹数 | 已确认事件 | 已确认路径 |
|---|---:|---:|---:|---:|
| 城市（Urban） | 4 | 4 | 7 | 7 |
| 山地/谷地（Mountain/Valley） | 3 | 9 | 13 | 14 |
| 高速/开阔（Highway/Open） | 2 | 2 | 2 | 2 |
| 反射特征（Reflective-Feature） | 2 | 2 | 7 | 7 |


### B. 代表性 SAGE 提取多径案例

图 2 展示来自高速/开阔环境的代表性 G25 测量。保留的联合确认路径具有 1.1 samples 的超额时延、$-4.72$ Hz 的相对多普勒和 $-7.85$ dB 的相对功率；其观测时间约为 60.54 s，选择的模型阶数为 $L=2$。联合确认的直达和次级分量在估计的时延—多普勒表示中得到分辨，其相对功率见图 2。

**图 2.** 来自高速/开阔环境的代表性已确认 G25 路径。图中展示直达和次级分量及其超额时延、相对多普勒和相对功率。

**图 3.** 三个代表性测量案例中，从有效 40 ms 观测窗口经候选筛选、时间一致性和多快照联合确认到已确认路径的层级式缩减。该图用于说明处理层级中的确认行为。

### C. 所评估测量环境中的描述性路径级观察

在 11 个测量运行的 17 条分析 PRN 轨迹中，有 8 个运行的 12 条轨迹获得了 30 条联合确认多径路径。表 II 汇总完整的分析覆盖情况，其中包括零确认或未形成确认路径的轨迹。这里的比较针对所分析运行中的路径级观测，属于描述性比较。所有已确认路径观测中，超额时延范围为 1.0--4.5 samples，相对多普勒范围为 $-78.552$ 至 $49.664$ Hz，相对功率范围为 $-19.773$ 至 $-0.894$ dB。Urban、Mountain/Valley、Highway/Open 和 Reflective-Feature 的超额时延中位数分别为 1.20、1.10、1.15 和 1.20 samples；相应的相对多普勒中位数分别为 $-3.820$、$-0.468$、$-7.715$ 和 $31.540$ Hz。图 4 展示这三个路径参数及其环境内中位数。

**图 4.** 所评估测量环境中的路径特征。各面板展示单条路径的超额时延、相对功率和相对多普勒；标签给出各环境的样本数 $n$，横线表示环境内中位数。

Urban 测量呈现当前观测中最宽的超额时延范围，最大超额时延为 4.5 samples。Mountain/Valley 测量呈现较宽的相对多普勒观测范围，表明解析出的传播分量之间存在较大变化。Reflective-Feature 的 7 条路径来自两个测量运行，并在超额时延、相对功率和相对多普勒上呈现变化。两个 Highway/Open 观测在已观测时延和相对多普勒上呈现相对集中的范围。该框架因此能够支持在所评估测量环境之间进行路径级多径特征比较。

> 【用户审阅提示】请重点审阅：环境证据表、代表性路径参数、G18 零确认表述以及局部模型/时间验证/联合确认的状态区分是否与英文稿一致。

## V. 结论

本文评估了一条真实动态 GPS L1 C/A 原始 IQ 测量链，以及一个用于路径级多径提取的导航数据辅助层级式 SAGE 框架。该估计器结合路径级时延—多普勒细化、导航对齐观测、时间一致性和多快照联合确认。结果表明，所提出的处理链能够在真实动态道路测量中解析并比较已确认 GNSS 多径分量的超额时延、相对多普勒和相对功率。受控注入路径恢复和原生 $L=1$ 与 $L=2$ 模型比较，为估计器行为提供了互补证据，同时保持了已知注入真值与 SAGE 得到的原生路径估计之间的区别。

> 【用户审阅提示】请重点审阅：结论是否正面总结路径提取和路径级表征，同时没有把当前结果扩大为完整统计信道模型或总体规律。

## 参考文献

以下书目信息与英文稿及 LaTeX 参考文献保持一致。

[1] J. A. Fessler and A. O. Hero, “Space-Alternating Generalized Expectation-Maximization Algorithm,” *IEEE Transactions on Signal Processing*, vol. 42, no. 10, pp. 2664--2677, Oct. 1994, doi: 10.1109/78.324732.

[2] B. H. Fleury, M. Tschudin, R. Heddergott, D. Dahlhaus, and K. I. Pedersen, “Channel Parameter Estimation in Mobile Radio Environments Using the SAGE Algorithm,” *IEEE Journal on Selected Areas in Communications*, vol. 17, no. 3, pp. 434--450, Mar. 1999, doi: 10.1109/49.753729.

[3] B. Eissfeller and J. O. Winkel, “GPS Dynamic Multipath Analysis in Urban Areas,” in *Proceedings of the 9th International Technical Meeting of the Satellite Division of the Institute of Navigation (ION GPS 1996)*, Kansas City, MO, pp. 719--727, Sep. 1996.

[4] E. J. Mora-Castro, C. J. Carrascosa-Sanz, and G. Ortega, “Characterisation of the Multipath Effects on the GPS Pseudorange and Carrier Phase Measurements,” in *Proceedings of the 11th International Technical Meeting of the Satellite Division of the Institute of Navigation (ION GPS 1998)*, Nashville, TN, pp. 1065--1074, Sep. 1998.

[5] P. Xie, M. G. Petovello, and C. Basnayake, “Multipath Signal Assessment in the High Sensitivity Receivers for Vehicular Applications,” in *Proceedings of the 24th International Technical Meeting of the Satellite Division of the Institute of Navigation (ION GNSS 2011)*, Portland, OR, pp. 1764--1776, Sep. 2011.

[6] A. Beitler, A. Tollkuehn, D. Giustiniano, and B. Plattner, “CMCD: Multipath Detection for Mobile GNSS Receivers,” in *Proceedings of the 2015 International Technical Meeting of the Institute of Navigation*, Dana Point, CA, pp. 455--464, Jan. 2015.

[7] A. Bilich and K. M. Larson, “Mapping the GPS Multipath Environment Using the Signal-to-Noise Ratio (SNR),” *Radio Science*, vol. 42, no. 6, p. RS6003, 2007, doi: 10.1029/2007RS003652.

[8] C. Fernandez-Prades, J. Arribas, P. Closas, C. Aviles, and L. Esteve, “GNSS-SDR: An Open Source Tool for Researchers and Developers,” in *Proceedings of the 24th International Technical Meeting of the Satellite Division of the Institute of Navigation (ION GNSS 2011)*, Portland, OR, pp. 780--794, Sep. 2011.

[9] Navstar GPS Directorate, “IS-GPS-200N: Navstar GPS Space Segment/Navigation User Interfaces,” Interface Specification IS-GPS-200N, Revision N, Aug. 1, 2022. Available: https://www.gps.gov/sites/default/files/2025-07/IS-GPS-200N.pdf
