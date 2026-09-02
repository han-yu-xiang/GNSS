# 暗室 GNSS 四路径信道参数建模与 16 个仿真场景进度报告

**报告日期：** 2026-08-30  
**报告用途：** 上级领导阶段汇报、暗室联调前技术交接  
**当前状态：** 模型分层实现完成；基础 8 表生成完成；Rain 8 表生成并独立 QA 通过；暗室硬件回放与绝对功率标定尚未完成

## 一、执行摘要

本项目已经建立一套面向暗室信道模拟器的、可复现的 GNSS 四路径参数生成体系。该体系以实测 GPS L1 C/A 数据形成的路径和接收机跟踪证据为基础，将输出组织为：

```text
环境条件 × 卫星仰角上下文 × 信号质量状态 × 天气层
    ↓
每毫秒 Low / Mid / High 三类卫星上下文
    ↓
每类固定输出 1 条主径 + 3 条 NLOS 次径
    ↓
相对时延、相对多普勒、相对幅度、相对相位
```

当前形成的“16 个场景”准确含义是 **16 个仿真组合**，而不是 16 个独立实测采集 scene：

- 4 类环境：Urban、Special Reflective、Mountain/Valley、Highway/Open；
- 2 类质量状态：GOOD_TRACKED_BASELINE、POOR_CONDITIONAL；
- 2 类天气层：Dry/Base、RainPooled；
- 合计：`4 × 2 × 2 = 16` 个仿真组合。

每个组合已生成 5 分钟参数表：

- 每毫秒 12 行：Low/Mid/High × path 0/1/2/3；
- 每表 3,600,000 行；
- 16 表合计 57,600,000 行；
- 文件合计 4,707,788,450 bytes，约 4.71 GB（十进制）。

阶段性结论如下：

1. **环境×仰角 NLOS 路径分布模型已建立并通过带限制 QA。**
2. **主径公共增益/可观测衰落模型已建立并通过带限制 QA。**
3. **接收机失锁进入率与持续时间诊断模型已建立。**
4. **GOOD/POOR 条件质量状态、幅度包络、恢复和相位连续演化已实现。**
5. **固定 1 主径 + 3 NLOS 的 canonical 输出合同已实现。**
6. **8 个基础环境×质量表已完成 5 分钟生成和哈希导出。**
7. **基于 9 个晴/中雨/大雨任务的 Stage3 可靠路径证据，RainPooled 雨效应层已实现；8 个加载雨层的表已生成并独立 QA 通过。**

需要强调：当前成果可称为**经验条件化暗室参数生成模型**，不能称为已完成的绝对 RF 功率模型、因果性降雨传播定律或经过暗室硬件回放验证的最终信道模型。

## 二、总体技术路线

### 2.1 基础暗室参数模型

基础模型链为：

```text
实测 GNSS 数据与已验证 SAGE/Tracking 产物
    ↓
Stage4 confirmed NLOS 路径参数
    ├─ 环境×仰角路径边缘分布
    └─ 参数相关性 Copula

GNSS-SDR tracking 诊断量
    ├─ 主径公共增益与衰落深度/持续时间
    ├─ 环境条件失锁进入率与失锁持续时间
    └─ 失锁—恢复幅度包络

外加且显式标记的相位假设
    └─ 初相均匀随机 + Doppler 连续演化

以上各层组合
    ↓
v2.2 四路径毫秒级 canonical 参数表
```

### 2.2 雨效应层

雨效应支线采用：

```text
Clear / MidRain / HeavyRain 的完整 Rain SAGE 任务
    ↓
Stage3 temporal-persistence reliable path evidence
    ↓
Clear 与 RainPooled 的经验分布差异
    ↓
对基础 canonical 表中 NLOS 路径进行分块变换
    ↓
RainPooled 参数表
```

Rain 支线选择 Stage3 的原因是：Stage4 联合确认准则对本批雨场景过于严格，无法提供足够的天气比较样本。该选择仅适用于探索性雨效应层；**Stage3 reliable path evidence 不等于 Stage4 confirmed multipath path**，也不改变主线 SAGE 的 confirmed criterion。

## 三、输出参数表合同

所有基础表和 Rain 表均固定使用以下七列，名称和顺序不变：

```text
ms,SatelliteID,NLOSPathID,RelativeDelay,RelativeDoppler,RelativeAmplitude,RelativePhase_rad
```

| 字段 | 单位/范围 | 含义 |
|---|---|---|
| `ms` | ms | 时间索引，从 1 开始 |
| `SatelliteID` | `Low` / `Mid` / `High` | 仰角上下文标签，不是实际 PRN |
| `NLOSPathID` | 0 / 1 / 2 / 3 | 0 为主径结构槽位；1–3 为 NLOS 槽位 |
| `RelativeDelay` | ns | 相对时延 |
| `RelativeDoppler` | Hz | 相对多普勒 |
| `RelativeAmplitude` | 线性幅度比 | 所有输出路径均保持有限且严格为正 |
| `RelativePhase_rad` | rad | 相对相位 |

每一毫秒严格按以下顺序输出：

```text
Low  path0, path1, path2, path3
Mid  path0, path1, path2, path3
High path0, path1, path2, path3
```

当前主径结构约定为：

- `RelativeDelay = 0 ns`；
- `RelativeDoppler = 0 Hz`；
- `RelativeAmplitude` **不是恒定 1**，而是由公共增益和质量包络共同决定；
- 初始相位随机，因主径相对多普勒为 0，当前相对相位在无额外机制时保持不变。

NLOS path 1–3 的时延、多普勒和相对幅度按环境×仰角路径模型采样，并在 40 ms 路径参数块内固定；相位按 1 ms 分辨率随相对多普勒连续演化。

## 四、环境×仰角路径参数分布拟合

### 4.1 数据来源与规模

基础 NLOS 参数模型严格使用 Stage4 confirmed multipath path 参数：

- 100 条 environment-ready confirmed multipath paths；
- 94 个 confirmed events；
- 35 个 runs；
- 11 个 scenes；
- 84 条路径具有可独立对齐的事件级仰角；
- 16 条路径仅进入环境/全局父分布，不强行分配仰角。

仰角分档固定为：

- LOW：`[0°, 30°)`；
- MID：`[30°, 60°)`；
- HIGH：`[60°, 90°]`。

直接观测支持如下。数字是已确认 NLOS 路径数量，不是多径发生概率：

| 环境 | LOW | MID | HIGH |
|---|---:|---:|---:|
| Urban | 0（`PRIOR_ONLY`） | 30 | 10 |
| Special Reflective | 19 | 1（`PRIOR_DOMINANT`） | 2（`PRIOR_DOMINANT`） |
| Mountain/Valley | 5（稀疏） | 9（稀疏） | 4（稀疏） |
| Highway/Open | 0（`PRIOR_ONLY`） | 3（稀疏） | 1（`PRIOR_DOMINANT`） |

因此，Urban–LOW 和 Highway/Open–LOW 没有直接路径样本，采用环境父分布并明确标记 `PRIOR_ONLY`；没有伪造观测。Highway/Open 整体支持最弱，不能据此提出强泛化结论。

### 4.2 分布族选择

分布族在 11 个代表 scene 上使用 leave-one-scene-out held-out log likelihood 进行确定性选择，结果为：

| 参数 | 候选分布 | 选定分布 |
|---|---|---|
| 相对时延 `relative_delay_ns` | Lognormal / Gamma / Weibull | **Lognormal** |
| 有符号相对多普勒 `relative_doppler_hz` | Student-t / Normal / Laplace | **Laplace** |
| 相对功率 `relative_power_db` | Student-t / Normal / Laplace | **Normal** |

线性相对幅度由功率差固定换算：

```text
RelativeAmplitude = 10^(relative_power_db / 20)
```

原始 Stage4 中少数大于 0 dB 的相对功率值被保留，没有擅自裁剪。

### 4.3 分层拟合、相关性和不确定性

模型采用：

```text
全局父分布
    → 环境父分布
        → 环境×仰角单元分布
```

稀疏单元通过固定 prior-equivalent weight 进行 partial pooling，而不是对极少样本强行独立拟合。三个路径参数之间的依赖由环境级 Gaussian copula 表示，并向全局 copula 收缩；没有拟合缺乏数据支撑的单元级协方差。

不确定性采用 1,000 次 scene-block bootstrap，而不是把相邻路径当作独立同分布样本。该设计降低了相邻事件和同一 scene 重复证据造成的虚假置信度。

## 五、主径公共增益与衰落模型

### 5.1 为什么主径不是固定幅度 1

如果主径幅度永久固定为 1，就无法模拟整体接收强度下降、深衰落或接收机诊断失锁过程。当前模型因此把 path 0 作为**结构参考槽位**，而不是声称它一定是物理 LOS 或始终最强路径。

主径及全部 NLOS 路径共享公共幅度尺度：

```text
A_i[m] = G_background[m] × G_quality[m] × Z_i × A_rel_i
```

其中：

- `G_background`：由 tracking C/N0 代理拟合的背景公共增益；
- `G_quality`：GOOD/POOR 质量状态包络；
- `Z_i`：结构槽位/块级因素；
- `A_rel_i`：NLOS 相对幅度；path 0 的参考项取 1。

因此，主径和次径可以一起衰落，同时保持一个 40 ms 块内的相对路径组成。

### 5.2 数据与拟合

公共增益/衰落模型使用 63 条 environment-eligible tracking runs：

- 894,470 条 tracking 记录；
- 808,133 条有效记录；
- 86,337 条 inconclusive 记录；
- 307,572 条 canonical 20 ms grid 记录；
- 91 个可观测 fade events；
- 30 个右删失 fade events。

定义：

- 每个 run 的参考值 `C_ref_run` 为有效 `LOCK_GOOD` C/N0 中位数；
- `common_gain_db = CN0 - C_ref_run`；
- 10 s 居中的 90% 分位 C/N0 作为局部上包络；
- 衰落进入：深度至少 3 dB 且持续至少 20 ms；
- 衰落退出：恢复到距上包络不超过 1 dB 且持续至少 100 ms。

选定分布为：

| 模型量 | 选定分布 |
|---|---|
| 正常公共增益 | Student-t |
| 可观测衰落深度 | Lognormal |
| 可观测衰落持续时间 | Gamma |

这些量是 run-normalized tracking 代理，不是绝对接收功率，也不是暗室功放 dB 标定值。

## 六、“信号质量差”的正式定义

### 6.1 Tracking 诊断层的坏锁定义

底层接收机诊断规则为：

- `carrier_lock_test < -0.5`：`LOCK_BAD`；
- 有限且 `>= -0.5`：`LOCK_GOOD`；
- 缺失或非有限：`INCONCLUSIVE`；
- 连续坏锁至少 20 ms 才确认失锁进入；
- 连续好锁至少 100 ms 才确认重新获得锁定；
- tracking 时间断点不跨越连接，不把断点伪造为一次失锁。

环境条件失锁模型使用 Gamma-Poisson 后验估计进入率，并把每毫秒进入概率写为：

```text
p_1ms = 1 - exp(-lambda / 1000)
```

失锁持续时间在 Lognormal、Weibull、Gamma 候选中选择 Gamma。当前 48 个诊断失锁事件的总体持续时间中位数约 1.349 s，P90 约 5.237 s。

### 6.2 生成器中的 GOOD 与 POOR

| 模式 | 生成语义 | 事件安排 |
|---|---|---|
| `GOOD_TRACKED_BASELINE` | 质量状态固定为 `TRACKED_GOOD`，质量包络为 1 | 每个仰角带 0 个条件质量事件 |
| `POOR_CONDITIONAL` | `FADING_TO_LOCK_BAD → LOCK_BAD_HOLD → RECOVERING` | 每个 Low/Mid/High 仰角带各 1 个完整事件 |

POOR 事件具有：

- 最长 20 ms 的进入渐变；
- 100 ms 事件前保护区和 100 ms 事件后保护区；
- 失锁持续时间来自冻结环境 lock model；
- 深度来自可观测 fade parent proxy；
- 恢复来自冻结恢复模型或父模型；
- 进入和恢复采用 raised-cosine 包络；
- 采用 `FAIL_CLOSED_NO_TRUNCATION`，不能为了适配短记录而截断质量事件。

必须区分两个概念：

1. tracking 数据中的 `LOCK_BAD` 是接收机诊断状态；
2. 参数表中的 `POOR_CONDITIONAL` 是为了构造可对比暗室压力场景而显式安排的条件事件。

当前 5 分钟 POOR 表不是按实测进入概率随机决定“是否发生事件”，而是每个仰角带固定安排一个完整事件。因此它适合 Good/Poor 对照和暗室压力测试，**不等于某环境真实失锁概率**。

`LOCK_BAD` 也不等于物理信号功率为零、不等于 NLOS、不等于“卫星消失”。幅度模型采用正数包络，科学组合模式的数值下限为 `1e-12`，避免把诊断状态错误解释为严格零功率。

## 七、三条 NLOS 路径与相位规则

当前最终合同要求每个仰角上下文始终输出 3 条 NLOS 路径，并满足：

- path 1、2、3 始终存在；
- 三条路径的幅度均严格大于 0；
- 参数从“已存在 confirmed multipath 时”的路径分布中采样；
- 不使用早期的概率激活模型决定空槽。

这是用户批准的**固定四路径暗室输入合同**，不是实测多径条数分布。真实 Stage4 数据中大部分 event 只有一条 confirmed multipath；固定三条 NLOS 是仿真结构选择，不能解释为任意时刻都真实存在三条物理多径。

当前数据没有可拟合的路径相位，因此相位采用显式外加假设：

```text
phi_0 ~ Uniform(-pi, pi)
phi[m+1] = wrap_to_pi(phi[m] + 2*pi*RelativeDoppler*0.001)
```

相位不因质量事件自动重置。该规则确保 1 ms 时间轴上相位与相对多普勒连续一致，但不代表已经从实测数据拟合出相位分布。

## 八、RainPooled 雨效应层

### 8.1 Rain SAGE 证据

雨效应层使用 9 个已执行并完成独立 QA 的 Rain SAGE 任务：

- Clear：G24/ch10、G29/ch3、G13/ch8、G12/ch11；
- MidRain：G24/ch8、G20/ch9；
- HeavyRain：G02/ch1、G31/ch4、G01/ch7。

只保留 `persistence_pass=1` 且中心窗口出现在 Stage3 reliable centers 中的路径证据：

| 天气 | 任务数 | Episode | Stage3 可靠路径行 |
|---|---:|---:|---:|
| Clear | 4 | 10 | 31 |
| MidRain | 2 | 8 | 17 |
| HeavyRain | 3 | 8 | 42 |
| RainPooled（Mid+Heavy） | 5 | 16 | 59 |

合计 90 条 Stage3 可靠路径证据、26 个 episode。

### 8.2 拟合与变换

Rain 层不做逐路径 Clear–Rain 相减，也不声称同一 PRN/路径能够一一匹配。拟合权重采用：

```text
任务等权
→ 任务内 episode 等权
→ episode 内路径等权
```

分别保留 Clear 与 RainPooled 在以下三个量上的加权经验分布：

- `log(delay_ns)`；
- 有符号 `doppler_hz`；
- `power_db`。

对同一分位位置 `u`，NLOS 变换可概括为：

```text
Delta_log_delay(u) = Q_Rain(log_delay, u) - Q_Clear(log_delay, u)
delay_rain = delay_base × exp(Delta_log_delay)

Delta_doppler(u) = Q_Rain(doppler, u) - Q_Clear(doppler, u)
doppler_rain = doppler_base + Delta_doppler

Delta_power_db(u) = Q_Rain(power_db, u) - Q_Clear(power_db, u)
amplitude_rain = amplitude_base × 10^(Delta_power_db / 20)
```

变换按 `SatelliteID × NLOSPathID × 40 ms block` 采样一次；同一块内时延、多普勒和幅度保持不变。相位从原 canonical 相位继续按雨后多普勒连续演化。

主径 path 0 在 Rain v1 中保持不变。这意味着当前 Rain 层描述的是 NLOS 参数分布变化，**尚未建模雨导致的绝对主径衰减**。

由于当前雨证据没有经过可靠的仰角条件化拟合，同一 RainPooled 变换被应用到 Low/Mid/High。这是明确的可分离性假设，不是“雨效应与仰角无关”的实测结论。

### 8.3 雨层科学边界

当前结果不能证明：

- 雨造成固定 dB 衰减；
- RainPooled 差异完全由降雨因果引起；
- Stage3 每条路径都是 Stage4 confirmed multipath；
- 雨效应已经按环境或仰角分别独立拟合；
- MidRain 与 HeavyRain 已有足够支持形成稳定的两套独立生产层。

当前 Rain layer 的正确定位是：**基于有限晴/雨实测 Stage3 可靠路径证据形成的、可加载到既有暗室表上的经验天气条件变换层。**

## 九、16 个仿真组合及现有产物

### 9.1 Dry/Base 八表

根目录：

`dataset_generation_logs/channel_modeling/0828darkroomPar/tables/`

### 9.2 RainPooled 八表

根目录：

`dataset_generation_logs/channel_modeling/rain_effect_layer_stage3_v1_20260830_r5/tables/`

| 编号 | 环境 | 质量 | 天气层 | 文件 | 状态 |
|---:|---|---|---|---|---|
| 1 | Urban | Good | Dry/Base | `urban__good.csv` | 已生成 |
| 2 | Urban | Poor | Dry/Base | `urban__poor.csv` | 已生成 |
| 3 | Special Reflective | Good | Dry/Base | `special_reflective__good.csv` | 已生成 |
| 4 | Special Reflective | Poor | Dry/Base | `special_reflective__poor.csv` | 已生成 |
| 5 | Mountain/Valley | Good | Dry/Base | `mountain_valley__good.csv` | 已生成 |
| 6 | Mountain/Valley | Poor | Dry/Base | `mountain_valley__poor.csv` | 已生成 |
| 7 | Highway/Open | Good | Dry/Base | `highway_open__good.csv` | 已生成 |
| 8 | Highway/Open | Poor | Dry/Base | `highway_open__poor.csv` | 已生成 |
| 9 | Urban | Good | RainPooled | `urban__good__rain.csv` | 已生成、Rain QA PASS |
| 10 | Urban | Poor | RainPooled | `urban__poor__rain.csv` | 已生成、Rain QA PASS |
| 11 | Special Reflective | Good | RainPooled | `special_reflective__good__rain.csv` | 已生成、Rain QA PASS |
| 12 | Special Reflective | Poor | RainPooled | `special_reflective__poor__rain.csv` | 已生成、Rain QA PASS |
| 13 | Mountain/Valley | Good | RainPooled | `mountain_valley__good__rain.csv` | 已生成、Rain QA PASS |
| 14 | Mountain/Valley | Poor | RainPooled | `mountain_valley__poor__rain.csv` | 已生成、Rain QA PASS |
| 15 | Highway/Open | Good | RainPooled | `highway_open__good__rain.csv` | 已生成、Rain QA PASS |
| 16 | Highway/Open | Poor | RainPooled | `highway_open__poor__rain.csv` | 已生成、Rain QA PASS |

每张表均为 300,000 ms、3,600,000 行。Rain QA 同时重新核验了 8 张基础源表的 SHA-256、行数和 schema，再检查雨后表的主径不变、NLOS 幅度正值、40 ms 块一致性和相位连续性。

## 十、验证与可追溯性

### 10.1 基础生成器验证

20 秒验证矩阵已经完成：

- 8/8 单运行 QA PASS；
- 4/4 Good/Poor 配对 QA PASS；
- 24 个 environment×elevation×quality logical cells 覆盖；
- 所有 NLOS 1/2/3 幅度严格大于 0；
- Good/Poor 保持共同增益、路径时延、多普勒和初始相位的配对随机性，差异仅来自质量包络；
- Poor 共 12 个条件事件，即 4 个环境 × Low/Mid/High 各一个。

5 分钟基础集合已完成 8/8 生成和哈希导出。基础集合的完整、等价独立矩阵 QA 没有单独形成与 20 秒完全相同的报告；但 Rain r5 QA 已对这 8 张 5 分钟基础表进行源哈希、行数、schema 和变换前后身份核验。

### 10.2 Rain 层验证

Rain r5 独立 QA 结果为 PASS，验证：

- 8/8 Rain 表存在，每表 3,600,000 行；
- 90 条 evidence、26 个 episode 与 manifest 一致；
- canonical 七列、行身份和行顺序不变；
- path 0 在 `1e-10` 容差内不变；
- 所有 NLOS 幅度有限且严格为正；
- 40 ms 效果块恒定；
- 相位递推与输出多普勒一致；
- 没有读取 Stage4/gold 参与 Rain 拟合；
- 输出不在 `scenes/**/sage_results` 下。

### 10.3 关键不可变 provenance

| Artifact | SHA-256 |
|---|---|
| v2.2 generator config | `26003c7c0c0cabca45c6a9a175974f1ca336a301eff9c546a9c3bc99e38b5822` |
| 基础 8 表 export manifest | `f2de55f4803f237449c9f6b7f4722343e5d3c00a6601a0cc62106c5178669feb` |
| Path distribution model manifest | `4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c` |
| Main gain/fade model manifest | `6f36dab892622c9b9dc61ecde91fda85ff12ca60eeea4f81fe37760f0acb1e45` |
| Environment lock model manifest | `21c04938cba559b3e042806b093eba82e4e86a44977e95831c715aa03ffc97a5` |
| Lock amplitude/phase/recovery manifest | `9eb1847eac27618f80475ceafe62616285a346c5da847afdb0e8f2c5fc63a3ee` |
| Rain effect model | `9e57ac9b24648f6e42a15d2185d9370fe19a5999507696e3e5ad765da36d3455` |
| Rain collection manifest | `a7dd28086b5b76821b6202f8f9efe6c7386e7f6db4680ae4353682982825c621` |
| Rain QA | `8b890163e9d0b501fe6f24c44217602340c7803cd413a03b40bb1e7604ab3efd` |

受保护主线 `scripts/sage_pipeline/run_nav_sage_pipeline.m` 未因暗室模型修改，记录 SHA-256 为：

`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`

## 十一、当前可交付能力

### 11.1 已具备

1. 按 Urban、Special Reflective、Mountain/Valley、Highway/Open 选择环境；
2. 按 Good/Poor 选择接收质量压力状态；
3. 按 Dry/Base 或 RainPooled 选择天气层；
4. 同时输出 Low/Mid/High 三种卫星仰角上下文；
5. 每个上下文输出固定四路径；
6. 以 1 ms 步长提供 5 分钟参数；
7. 提供可复现 seed、immutable manifest、文件哈希和 QA 证据；
8. 可将表作为暗室信道模拟器的参数输入候选。

### 11.2 尚未完成

1. 暗室硬件端的实际回放、接口时序和端到端接收机响应验证；
2. 绝对 RF 功率、噪声底、功放/衰减器范围和接收机灵敏度标定；
3. Rain 对主径绝对衰减的独立模型；
4. MidRain 与 HeavyRain 分层后分别加载到 4 环境×2质量的生产表；
5. 雨效应的环境条件化和仰角条件化拟合；
6. 物理多径发生率、真实路径数、路径寿命及跨块时间相关性模型；
7. 实测相位分布；
8. 证明 RainPooled 差异具有纯粹降雨因果性。

## 十二、风险、限制与管理口径

| 风险/限制 | 当前控制方式 |
|---|---|
| 样本量不均衡 | 使用分层父分布、partial pooling、scene-block bootstrap，并显式标记稀疏状态 |
| Urban–LOW、Highway/Open–LOW 无直接 Stage4 路径样本 | 标记 `PRIOR_ONLY`，不伪造样本 |
| Highway/Open 支持弱 | 限定为初步/候选模型，不做强泛化 |
| 固定三条 NLOS 与实测路径数不一致 | 明确为暗室结构合同，不解释为发生率 |
| POOR 每带固定一次事件 | 明确为条件压力测试，不解释为实际失锁概率 |
| 相位无实测拟合 | 明确标记为均匀初相+多普勒连续演化假设 |
| Rain 使用 Stage3 | 明确标记可靠证据而非 Stage4 confirmed |
| 雨效应没有 matched PRN 全覆盖 | 使用分布层变换，不做逐路径相减，不作因果结论 |
| 无绝对 RF 标定 | 输出仅为相对参数，不声称固定 dB 雨衰 |

## 十三、建议的下一阶段决策

若目标是尽快进入暗室实验，建议按以下顺序推进：

1. **接口验收：** 选取一个 Dry/Good 和一个 Rain/Poor 表，确认暗室设备能按七列合同、12 行/ms 和 5 分钟时间轴稳定加载；
2. **小规模闭环：** 先进行短片段回放，检查接收机是否能正确响应主径公共增益、NLOS 时延/多普勒和 POOR 状态包络；
3. **绝对功率标定：** 由暗室设备量程、接收机灵敏度和目标 C/N0 范围给出相对幅度到绝对 RF 设置的映射；
4. **天气层选择：** 由负责人决定继续使用 RainPooled，还是在获得更多证据后分别冻结 MidRain 和 HeavyRain 层；
5. **结果闭环：** 对回放后的 GNSS-SDR tracking/positioning 输出进行只读 QA，验证仿真参数与接收机现象的对应关系。

不建议在完成暗室回放和绝对功率标定之前，把当前 16 表表述为“最终物理信道模型”或“已验证的降雨衰减模型”。

## 十四、向领导汇报的建议结论

可以简洁汇报为：

> 项目已经完成四类道路环境、两类接收质量状态以及晴天/雨况两类天气层的组合建模，形成 16 个五分钟暗室参数场景，共 5,760 万行参数。系统能够以 1 ms 分辨率为低、中、高仰角卫星分别生成一条主径和三条次径的相对时延、相对多普勒、相对幅度和相对相位。基础路径参数来自已确认的 SAGE 路径证据，主径衰落与失锁过程来自 GNSS-SDR tracking 诊断模型，雨效应层来自 9 个晴/中雨/大雨任务的 Stage3 可靠路径证据。现阶段模型和数据产物已具备可复现性与哈希追溯能力，下一步重点是暗室设备接口、绝对功率标定和端到端回放验证。

同时必须附加以下边界说明：

> 当前成果属于经验条件化暗室参数模型。POOR 是条件压力场景，不是环境的真实失锁概率；RainPooled 是有限样本下的经验雨效应层，不是固定 dB 雨衰或严格因果定律；固定三条 NLOS 是暗室结构合同，不是实测路径数结论。

## 十五、状态登记

| 工作项 | 状态 |
|---|---|
| 环境×仰角路径分布拟合 | `Completed / QA PASS_WITH_LIMITATIONS` |
| 主径公共增益/衰落模型 | `Completed / QA PASS_WITH_LIMITATIONS` |
| 环境条件失锁模型 | `Completed / QA PASS_WITH_LIMITATIONS` |
| 失锁—幅度—相位—恢复映射 | `Implemented / QA PASS_WITH_LIMITATIONS` |
| 固定四路径 v2.2 生成器 | `Implemented / 20 s matrix QA PASS` |
| 5 分钟 Dry/Base 8 表 | `Generation/Export Completed` |
| Stage3 RainPooled 雨效应层 | `Implemented / QA PASS` |
| 5 分钟 RainPooled 8 表 | `Completed / QA PASS` |
| 16 场景暗室硬件回放 | `Not started` |
| 绝对 RF 功率标定 | `Not started` |
| 完整物理/因果天气信道模型 | `Not completed` |

本报告是对既有模型、产物和 QA 事实的汇总，不执行新实验，也不改变任何模型参数、SAGE 结果或 immutable artifact。
