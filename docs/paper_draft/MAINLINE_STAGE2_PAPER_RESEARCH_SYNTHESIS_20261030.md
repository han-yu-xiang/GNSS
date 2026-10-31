# Mainline Stage2 论文科研成果整理与写作定位（2026-10-30）

> 本文是供作者审阅的**新 Mainline 论文素材包**，不是既有 VTC2027 稿件、旧 Stage3 r3 模型或可直接投稿的英文正文。科研状态以 `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md` 为准；下文的数值与适用范围由本包的[证据矩阵](MAINLINE_STAGE2_PAPER_EVIDENCE_AND_FIGURES_20261030.md)追溯。未重新运行 SAGE、CIR、alpha 或模型拟合。

## 1. 推荐论文究竟研究什么

**推荐路线 A：在真实车载 GPS L1 C/A 录制中，对 SAGE 估计出的、条件于 Stage2 选中机制的多径参数进行统计表征，并用完整录制场景留出检验模型复杂度的泛化收益。** 核心问题不是“能否造出一个看似完整的物理信道生成器”，而是：对于当前估计器真正输出的选中窗口和路径，哪些统计规律跨场景相对稳定，哪些环境、仰角及相关结构在训练内看起来有差异却不能带来可靠场景外收益？

| 路线 | 现有强证据 | 决定性限制 | 建议 |
| --- | --- | --- | --- |
| A. 实测数据上的 SAGE 参数统计及场景泛化 | 83 run/13 scene 冻结总体；7,847 已选窗口与 8,914 MPC；全场景留出、计数/边际/条件模型的真实结果和负面结果；固定分箱评分可复核 | 输出条件于 Stage2 选择和算法约束，不是真实传播参数的无条件总体；场景只有 13 个 | **主论文**，标题、摘要和主图围绕它组织 |
| B. SAGE 与 CIR/PDP 联合表征及统计建模 | Gate E/F 的 83-run 载荷 read-back、7,847/7,847 精确窗口关联、16,761/16,761 复数 alpha、PDP 数值重算 | CIR 与 SAGE 共用录制/Stage0 链；PDP 关联预测收益很小；跨窗相干、绝对增益及完整物理重构未验证；Gate G 待验 | 作为路线 A 的**测量域交叉表征与边界检查**，不是主论文“联合生成器已成立”的证据 |

如果目标期刊要求“经验证的完整时变复数物理信道模型”，目前**不具备**该主张。若目标是一个边界明确的测量统计与场景泛化论文，现有证据已足以支撑主体结果；后续主要工作是文献定位、图表重绘/科学复核和正式写作，而非继续调 Copula。

### 可成立的贡献候选（待正式文献对照后确定新颖性措辞）

1. **经身份核验的估计器条件总体。** 在同一冻结 Stage2 定义下，完整保留零 MPC 已选窗口、直达参考和 MPC，并把复数 alpha 与 code-domain CIR/PDP 精确关联。贡献是可追溯的测量—估计—统计对象定义及数据证据，不是把常规文件整理或 QA 自动化称为算法首创。
2. **场景层面的简洁模型选择证据。** 延迟 Lognormal 候选在 WP1 的 13/13 全场景折排名首位，并在后来固定分箱混合评分的 13/13 训练折中再次被选中；相对功率和 Doppler 的族选择更敏感，环境 M1 与 GSV 仰角 M2 未证明稳定优于全局 M0。功率—时延负向关联存在，但条件回归没有场景外预测收益。这是“何处不必增加复杂度”的可发表结果，不是普适传播定律。
3. **对量化估计输出采用明确定义的场景外评分。** 固定 0-Hz 箱中心下，用 0.01-chip 延迟单元概率、5-Hz（10/20-Hz 敏感性）Doppler 箱概率和连续功率密度比较独立边际与 Gaussian Copula。三个箱宽的场景平均增益均为负。方法贡献只能表述为对**预先粗粒化的 Stage2 输出**进行公平预测比较；不能声称恢复了原 SAGE 自适应搜索的精确似然，也不能据此称“参数不相关”。

## 2. 数据、估计器和参数的真正含义

研究总体为 13 个 10.23-MHz 场景、83 个 SAGE run（scene–PRN/channel 处理任务），来自车载 GPS L1 C/A 录制与 GNSS-SDR tracking/NAV 辅助链；环境元数据为 Urban 6、Mountain/Valley 3、Highway/Open 2、Special Reflective 2 个 scene。Stage0 有 285,752 个有效 40-ms 窗口；Stage1 相关筛查后，Stage2 仅选中 7,847 个（2.7461%）。这 7,847 个窗口中，MPC 数量 (N=0,1,2,3) 分别为 3,574、1,412、1,081、1,780，合计 8,914 条 MPC；每个已选窗口另有一条直达**参考**路径，故 Stage2 总路径记录为 16,761。`N=0` 只指选中窗口账本没有额外 SAGE 路径，不代表物理无多径；未入选 Stage0 窗口不能补为 `N=0`。

Stage0 是 NAV 符号对齐/窗口构造，Stage1 是相关候选筛查，Stage2 在候选窗口中评估模型阶数 $L=1,\ldots,4$，按 BIC 与残差增益等规则选阶并迭代估计复数系数和延迟/Doppler；Stage3 可靠中心与 Stage4 多快照确认另有不同科学标签。**本论文主体的 8,914 条是 Stage2 算法 MPC 候选，不是 8,914 条 Stage4 确认物理反射路径。** Stage2 的 $N=L-1$ 及最小路径分离、搜索边界与路径排序都会影响观测分布。相邻延迟秩的固定 0.1-chip 间隔是这种估计器结构的实例，不能解释为物理散射体规律。

对窗口 $i$ 的参考路径记 0、其余估计路径记 $\ell$：

$$
D_{i\ell}=\frac{\hat\tau_{i\ell}-\hat\tau_{i0}}{10}\ \text{chips},\quad
V_{i\ell}=\hat\nu_{i\ell}-\hat\nu_{i0}\ \text{Hz},\quad
P_{i\ell}=10\log_{10}\frac{|\hat\alpha_{i\ell}|^2}{|\hat\alpha_{i0}|^2}\ \text{dB}.
$$

这里 $\hat\tau$ 以 samples 计，10 samples/chip；$D$ 是估计器相对参考路径的**超额时延**，$V$ 是带符号的相对 Doppler，$P$ 是相对功率，参考路径并不必然是物理 LOS 或最强路径。冻结 SAGE 实现先对 NAV-wiped 40-ms 复数观测去均值、以窗口 RMS 归一化，再对局部延迟/Doppler 副本矩阵作复数最小二乘估计 $\hat\alpha$。导出保留实部、虚部、$|\alpha|$ 和弧度主值相位。alpha 可用于**单窗口内**相对复数路径表征，不能视为经前端增益校准的绝对信道系数；跨窗口相位连续性、反射体跟踪尚无证据。

时延搜索步长 0.1 sample，即 0.01 chip；候选路径最小分离 1 sample，即 0.10 chip。局部 Doppler 名义步长 5 Hz，但 `makeGrid` 可能追加非等距上界，且局部搜索起点、边界与迭代结果随窗口和路径变化；2,861 个多 MPC 窗口中 108 个不能用共同平移的 5-Hz 格点完全解释。冻结输出未保存逐轮候选/胜出轨迹，因此不从最终 Doppler 值反推精确自适应观测单元。旧连续 Doppler 点密度综合分数只可作近似诊断，**不得用于正式联合模型排名**。

## 3. 方法链与数学口径

### 3.1 边际、计数与场景外评价

研究对象首先是 $p(N\mid S=1)$，其中 $S=1$ 表示 Stage2 已选；经验计数候选对每个训练 scene 先求 0–3 类比例、再在 scene 间等权平均，不为未见类偷偷平滑。完整 scene 留出 LOSO：一个 scene 的所有 run、PRN、重叠窗口和 MPC 一起作为测试集。边际分布拟合及后续联合候选使用场景/窗口平衡的复合或伪似然；它们不产生路径独立样本意义下的普通置信区间。候选族仅在相同变量、相同训练/测试支持与评分测度内比较；训练折内嵌套选择，测试 scene 不参与该折参数估计。13 个 LOSO 折的训练集彼此高度重叠，不能当作 13 次独立实验。

Delay 候选 Lognormal（固定 `loc=0`）可写 $\log D\sim\mathcal N(\mu_D,\sigma_D^2)$。WP6 全 13-scene 场景/窗口平衡**描述性重拟合**为 `shape=0.510756`、`scale=exp(mu)=0.192930 chips`；这是算法选中 MPC 的工作参数，不是普适传播参数，更不以全样本重拟合分数代替场景外验证。Doppler 的 Normal/Student-t 与相对功率的 Normal/Student-t 应保留竞争候选；WP6 描述性重拟合的 signed Doppler Student-t 为 `df=8.17295, loc=0.759586 Hz, scale=61.77635 Hz`，功率 Normal 为 `loc=-8.15758 dB, scale=6.82687 dB`，但连续 Doppler 参与的联合分数已因观测机制问题降为近似诊断，不能以这些点参数宣称最终物理模型。

环境 M1 将族参数按 Urban/Mountain 分开；GSV 来源纯净的 M2 在正支持族的 `log(scale)` 或有符号族的 `location` 上加 $\beta(e-45^\circ)/10$，并维持环境基线。M2 与 M0/M1 只能在**相同 GSV 有效样本**上配对。WP3 的 9 核心场景（Urban 6、Mountain 3）不同于 WP1 的全 13-scene 总体，二者参数或均分不可直接相减。运动速度虽有描述性来源表，但重复 NMEA 记录、高速度质量问题尚未独立解决，**未拟合运动 M3**。

### 3.2 Code-domain 表征及联合候选的边界

Gate F 的 CIR 是在同一原始 IQ / Stage0 tracking 支持下的 NAV/code/Doppler wipe 相关响应；对每个 Stage0 窗口有 40 个 1-ms 复数快照、451 个 delay bins（$-5:0.1:40$ samples）。其 PDP 按 bin 做非相干功率平均：

$$
\mathrm{PDP}(i,k)=\frac1{40}\sum_{m=1}^{40}|\mathrm{CIR}(i,m,k)|^2.
$$

它不是从 SAGE alpha 重构出的独立传播真值。PDP 的 RMS code-delay width 是相关响应网格上的宽度，**不是**已验证的物理多径 RMS delay spread。WP4 证明的是 83-run 载荷/身份及该公式的数值一致（最大差 0），7,847/7,847 个 Stage2 窗口和 8,914/8,914 条 MPC 可精确链接；63 个边界峰窗口保留。WP5 证明 16,761/16,761 条 alpha 导出在身份、顺序及相对功率上数值一致。两项合起来提供统计表征的可信接口，不是独立信道真值交叉验证。

WP6 曾考察计数×路径独立边际和 Gaussian Copula 的联合候选。若写出 $p(N=n\mid S=1)\prod_{\ell=1}^{n}f(D_\ell,V_\ell,P_\ell)$，须显式标记：标记分布不随 $N$ 变、窗口内路径条件 iid/可交换。这些假设**没有通过**；N=1 条件时延族拟合失败使计数条件模型缺全层覆盖，N=3 场景支持薄弱，路径按延迟排序、不同秩的功率明显不同。故上述乘积只作为已实现的工作基线，不能作为已验收的完整有序多路径生成律。原 WP6 连续 Doppler 的 `−0.101470 nats/MPC-window` Copula 差与联合分数是历史近似诊断，不能用于正式模型排名。

最新可比较目标改为固定分箱观测：$B_w(V)=\lfloor V/w+1/2\rfloor$，0 Hz 为中心，$w=5$ Hz 为主结果，10/20 Hz 为预定敏感性。Delay 以 0.01-chip 单元 $[d-0.005,d+0.005)$ 的截断分布质量评分；Doppler 用 $[(k-1/2)w,(k+1/2)w)$ 的质量；功率用连续密度。独立基线是三项 `log mass + log mass + log density`；Gaussian Copula 候选对 delay/Doppler 两个潜在正态区间做**联合积分**并条件于连续功率的潜在分位数。所有边际族与相关矩阵仅在训练场景拟合，同箱宽、同测试窗口/路径配对。此 estimand 是**粗粒化的估计输出分布**，不是原 SAGE 自适应搜索器的精确似然。

## 4. 已有实验究竟支持什么

- **描述性总体与计数：** 7,847 个已选窗口的 0/1/2/3 计数见上。WP2 留出比较中，截断 Poisson 比经验分类低 `0.171584` nats/选中窗口，NB2 低 `0.0182553`，且 NB2 13/13 折落到均值无穷边界。WP6 场景平衡经验计数的 LOSO 宏均分为 `-1.297385 nats/selected window`；只支持当前 Stage2 条件目标，不支持无条件多径发生率。
- **边际：** WP1 的延迟 Lognormal 在全局 13/13 折排名第一；WP2 对这些保存的 V0 折做敏感性汇总，不是另做 13 次独立拟合。WP3 核心九场景延迟 9/9 首位；最新固定箱宽混合比较的外层训练折延迟族 13/13 选中 Lognormal。原始延迟只观察到 0.1 chip 及以上，尾部/截断与量化限制不可省略。全局 Doppler/功率族更不稳定，不能写“唯一最佳分布”。
- **功率—时延关联：** WP1 pooled Spearman $\rho=-0.616410$，但线性 $R^2=0.055343$；WP2 13/13 留出拟合斜率为负，中位数 `-2.50632 dB/chip`，但条件−边际宏 log-score `-0.0605013`，RMSE 差 `+0.182619 dB`（越大越差）。这是非因果、选择条件下的关联，**未带来可靠场景外预测改进**。
- **环境/仰角：** WP3 核心 9 场景中，M1−M0 的三参数候选族宏差全部为负；GSV 纯净子集的功率 M2−M1 为正但 M2−M0 混合，环境分组收益不一致。Urban 有 6 场景，Mountain 仅 3，其他环境各 2。GSV 实测、星历推导及缺失不能混作同一来源；速度仅描述。保留 M0，M1/M2 作为探索性分析，不声称已验证因果或更优的环境专属模型。
- **CIR/PDP：** Gate E/F 均 `PASS_WITH_LIMITATIONS`。WP6 场景外线性预测相对常数基线的 PDP 峰偏移 RMSE 只下降 `0.007798 samples`，code-delay RMS width RMSE 下降 `0.038769 samples`；这是共享输入链上的很小改善，不足以把 CIR 关联升格为独立传播验证。
- **依赖/固定箱宽：** 5/10/20 Hz 的 Copula−独立边际 scene 宏均差依次 `−0.00768378/−0.00864037/−0.00820576 nats/mark`，每种宽度 10/13 正、3/13 负，后三者损失较大。不能只报告正向场景数，也不能由负均值推出“参数无依赖”。路径秩非交换、N=1 条件模型不可评分与 N=3 低支持仍阻止完整联合生成器的 Gate G；**Gate G=`PENDING`**。

## 5. 推荐章节与素材布置

1. **Introduction：** 动态 GNSS 多径的路径级统计问题；为什么接收机指标和单场景拟合不足以说明场景泛化；定义本文只研究 Stage2 估计输出的条件统计。以“跨场景证据决定复杂度”为中心论点，勿承诺完整物理生成器。
2. **Related Work：** 分四类核对原文：GNSS 实测多径统计、NAV 辅助/高分辨率 SAGE 估计、场景留出/层级统计评估、code-domain CIR 与多径参数关联。对照各文的测量频段、对象（Stage2/Stage4/接收机指标）、样本分层、验证单位和观测量化。现有 WP1 文献摘要只能指示方向，不能代替正式逐篇原文核查；未完成前不写“首次/首创”。
3. **Measurement, Estimator and Dataset：** 录制与 GNSS-SDR 支持、13 scene/83 run 环境支持、Stage0→Stage2 选择、精确键、40-ms 窗口、L=1–4 与 0.01-chip/自适应 Doppler 搜索；放一张工作流图、一张 scene/样本表。Stage3/4 只用于标签差异和适用边界，不把主体变成 confirmed event 论文。
4. **Methodology：** 上述参数定义；场景/窗口平衡拟合、Lognormal 等候选、经验选中窗口计数、完整 scene LOSO/嵌套选择、同身份配对分数；单列固定分箱混合评分及“不是原估计器似然”的声明。CIR/PDP、alpha 作为配套测量层简述，附公式。若篇幅有限，Copula 数学推导与失败诊断放补充材料。
5. **Experimental Setup：** 冻结输入/代码/manifest、训练测试场景分离、全局与条件候选同总体比较、来源缺失与失败保留、等 scene 宏汇总；说明 13 折不是独立重复、不做 MPC 行级显著性推断。旧 `docs/paper_draft/sections/04_Experimental_Setup.md` 的时间性状态与几何描述已过时，不能直接复制。
6. **Results and Discussion：** 先总体/计数，再边际与尾部，再功率—时延、M1/M2 配对，最后 code-domain 关联与固定箱宽依赖负结果。每节写清分母、单位、评价总体、失败/低支持、是否属于描述或场景外证据。固定箱宽的 10 正/3 负与负宏均分应并列呈现。
7. **Limitations：** 选择偏差、搜索量化、场景数与重叠窗口、GSV 缺失、旧 baseline provenance、代码共享测量链、alpha 归一化、计数条件标记与路径排序、Gate G 未通过。不能把这节只放一句“样本有限”。
8. **Conclusion：** 可以结论为“对给定估计器/选中总体，全局简洁基线较复杂候选更稳健；延迟族稳定，其他条件/依赖结构有场景异质”。不得结论为“已构建真实传播的完整联合生成器”。

## 6. 推荐标题与摘要初稿

**中文题目：**《动态道路场景中 GPS L1 C/A 多径的 SAGE 估计参数统计与跨场景泛化》

**English title:** *Scene-Held-Out Statistical Characterization of SAGE-Estimated GPS L1 C/A Multipath in Dynamic Road Environments*

**中文摘要（供审阅）：** 本文研究车载 GPS L1 C/A 录制中，NAV 辅助 SAGE 所估计的多径参数在未见录制场景上的统计稳定性。对 13 个场景、83 个处理任务的冻结总体，我们保留 7,847 个 Stage2 已选窗口、8,914 条候选多径及其窗口身份，并以完整场景留出评估条件于 Stage2 选择的 MPC 计数、超额时延、带符号相对多普勒与相对功率。超额时延的 Lognormal 候选在原全局 13/13 场景折排名首位，并在后续固定观测分箱评价的 13/13 训练折中被选中；相对多普勒和功率的候选族更依赖场景与评价测度。Urban/Mountain 参数拆分及 GSV 仰角条件未显示稳定优于全局基线的场景外收益。基于完整 83-run CIR/PDP 和复数 alpha 身份核验，我们进一步在固定 5、10、20 Hz Doppler 箱目标下比较独立边际和 Gaussian Copula：三种分辨率下后者的等场景平均分差均略负。结果支持以简洁、来源可追溯的条件统计基线描述这一估计输出总体，但不验证原 SAGE 自适应输出似然、完整联合生成器或物理信道真值。

**English abstract (draft):** We characterize the statistical stability of NAV-aided SAGE multipath estimates from vehicle-mounted GPS L1 C/A recordings across held-out measurement scenes. The frozen cohort contains 83 processing runs in 13 scenes, with 7,847 Stage2-selected windows and 8,914 estimated multipath components. We evaluate selected-window path counts and excess delay, signed relative Doppler, and relative-power marks using complete-scene holdout. A lognormal excess-delay candidate ranks first in all 13 original global scene folds and is selected in all 13 training folds of a subsequent fixed-observation-bin analysis; Doppler and power family choices are less stable. Environment-specific and GSV-elevation-conditioned fits do not show a consistent scene-out advantage over a global baseline. Full-cohort CIR/PDP and complex-coefficient audits establish exact window/path linkage and internal numerical consistency, not independent propagation ground truth. Under prespecified 5-, 10-, and 20-Hz Doppler bins, a Gaussian-copula candidate has slightly negative scene-macro score differences relative to independent marginals at all three resolutions. The evidence supports a bounded, estimator- and selection-conditional statistical baseline, but not an exact likelihood for adaptive SAGE outputs or a validated joint physical channel generator.

**English terminology check:** `Stage2-selected`, `estimated MPC`, `direct reference`, `scene-held-out`, `relative power`, `code-domain correlation width` and `fixed-binned Doppler` 必须在正文与图注保持一致；不可把 `estimated` 省略成 physical/confirmed。摘要数值对应的表、限制和输入路径见配套证据矩阵。
