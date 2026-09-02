# VTC2027-Spring 论文 P0 / P1 / P2 定点修改清单

> 用途：供 Codex / 其他 AI 执行当前 VTC2027-Spring 论文的定点修改。  
> 基础版本：当前 `main.pdf` / `main.tex` 对应的 4 页英文稿。  
> 当前阶段：`USER_AUTHOR_REVIEW`。  
> 本文档只定义论文写作与术语修改，不授权新增实验、重跑 SAGE、修改 Figure/Table 科学数据或改变论文科学边界。

---

## 0. 执行原则

### 0.1 当前工作性质

本轮是：

```text
WORK_TYPE = VTC manuscript targeted revision
CURRENT_PHASE = USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN = YES
SAGE_PRODUCTION_STOPPED = YES
NEW_EXPERIMENT_REQUIRED = NO
```

### 0.2 修改顺序

严格按以下顺序：

```text
1. English main.tex
2. English Markdown mirror（如仍维护）
3. Chinese review LaTeX
4. Chinese review Markdown
5. Relevant VTC/Paper handoff
6. Recompile + visual QA
```

英文 `main.tex` 始终是正式投稿 source of truth。

### 0.3 禁止事项

不得：

- 新增实验；
- 运行 MATLAB / SAGE / batch production；
- 修改任何 raw IQ；
- 修改 `scenes/**/sage_results`；
- 修改 confirmed multipath criterion；
- 修改 Figure 2/3/4 的科学数据；
- 修改 Table II 冻结数值；
- 引入 path-level coherence；
- 将 zero-confirmation 写成“无多径/LOS proven”；
- 将 30 条 confirmed paths 写成 30 个独立环境样本；
- 新增 occurrence-rate / stochastic channel model / elevation-conditioned statistical model；
- 为了填页数增加低价值内容；
- 大范围重写整篇论文。

---

# P0 — 必须修改

P0 是技术一致性、术语准确性或读者理解层面的硬问题。必须全部处理。

---

## P0-1. 修正式 (1) 中 `L` 与 direct path 的定义冲突

### 当前问题

当前信号模型类似：

```latex
r(t) = s_0(t) + \sum_{\ell=1}^{L}
\alpha_\ell s(t-\tau_\ell)e^{j2\pi\Delta f_\ell t}+n(t)
```

但正文又把 `L=1,2,3,4` 当作**总模型阶数 / 总路径数**：

- `L=1`：direct only；
- `L=2`：direct + one secondary；
- `L=3`：three components；
- `L=4`：four components。

按当前式子，`L=2` 会变成：

```text
direct + path1 + path2 = 3 components
```

与后文、Figure 2、model-order selection 含义冲突。

同时后文定义：

```latex
\Delta\tau_\ell = \tau_\ell-\tau_0
```

但当前式 (1) 的 direct contribution `s_0(t)` 没有显式定义 `\tau_0`。

### 修改目标

统一 `L` 为**模型中的总路径数**。

优先采用类似：

```latex
r(t)=
\sum_{\ell=0}^{L-1}
\alpha_\ell
s(t-\tau_\ell)
\exp\!\left(j2\pi \Delta f_\ell t\right)
+n(t)
```

随后说明：

```text
ℓ = 0 denotes the direct component.
τ0 is the direct-path delay reference.
Δf0 = 0 when Doppler offsets are referenced to the direct component.
```

确保全文保持：

```text
L = 1 -> direct only
L = 2 -> direct + one secondary component
L = 3 -> three components
L = 4 -> four components
```

### 注意

- 先核对当前代码/Method 对 `L` 的真实语义；
- 不得为了修公式改变实际算法；
- 只解决符号和论文模型定义一致性。

---

## P0-2. 修正 Section IV-A 与 Figure 3 的案例衔接

### 当前问题

Figure 3 实际展示：

```text
G05 — Special Reflective
G25 — Highway/Open
G11 — Mountain/Valley
```

但紧邻正文突然开始解释：

```text
G28
G18
```

读者容易以为 G28/G18 就是 Figure 3 的三个案例之一，造成叙事断裂。

### 修改目标

先解释 Figure 3 当前真正展示的三个案例，再引出 G28 / G18 作为“拒绝/零确认”补充案例。

建议逻辑：

```text
1. Figure 3 illustrates progressive reduction for three representative
   confirmed-path cases from Special Reflective, Highway/Open,
   and Mountain/Valley.

2. The same hierarchy also rejects candidates that do not survive
   final confirmation.

3. Then introduce:
   - Mountain/Valley G28: temporally consistent candidate(s)
     rejected by final multi-snapshot joint confirmation.
   - Urban G18: no candidate retained as a confirmed multipath event
     after final joint confirmation.

4. Conclude:
   these examples jointly demonstrate both retention and rejection behavior.
```

建议英文骨架：

```text
Figure 3 illustrates the progressive candidate reduction for three
representative confirmed-path examples from the Special Reflective,
Highway/Open, and Mountain/Valley scenarios. The same hierarchy also
rejects candidates that do not survive final confirmation. In the
Mountain/Valley G28 track, temporally consistent candidates were
rejected during multi-snapshot joint confirmation, whereas in the
Urban G18 track, no candidate remained as a confirmed multipath event
after final joint confirmation. Together, these cases illustrate both
retention and rejection behavior of the hierarchical procedure.
```

### 特别要求

- 不再在 Results 正文写 `F1023_V70_D0120_P1` 等文件名；
- 使用环境类型 + PRN；
- G28 → `Mountain/Valley`；
- G18 → `Urban`；
- 核对 G28 是 singular 还是 plural：
  当前工程统计显示 Stage3 temporally consistent / reliable candidates 数量不止 1，
  不要机械写 `a candidate`。

---

## P0-3. Table I：`Receiver` 改为准确的采集设备术语

### 当前问题

Table I 当前类似：

```text
Receiver | TEST-TREE RF-Catcher V2
```

但正文实际把 RF-Catcher V2 描述为 RF signal capture / playback device。

这不是论文意义上的完整 GNSS receiver。

### 修改目标

优先改为：

```text
Acquisition device | TEST-TREE RF-Catcher V2
```

可选：

```text
RF front end
```

但默认推荐 `Acquisition device`，最稳妥。

同时：

```text
Confirmed configuration
```

这种列名带审计/验收味，改为：

```text
Configuration
```

---

## P0-4. 明确定义 `confirmed event` 与 `confirmed path`

### 当前问题

Table II 同时存在：

```text
Confirmed events
Confirmed paths
```

例如：

```text
Mountain/Valley = 13 events / 14 paths
```

说明一个 event 可能包含多条 confirmed secondary paths。

但正文没有给普通读者定义二者区别。

### 修改目标

在 Table II 首次出现前后、或 Section III-E / Section IV-A 最自然的位置补一句：

```text
A confirmed event denotes one jointly confirmed observation interval,
which may contain one or more confirmed secondary paths.
```

中文：

```text
一个已确认事件表示一个通过联合确认的观测区间，
其中可包含一条或多条已确认次级路径。
```

### 注意

- 不暴露 `joint_valid`、`joint_multipath_count`、`is_multipath` 等代码字段；
- 保持科学定义，而不是工程 artifact 定义。

---

## P0-5. Figure 1 路径参数名称与正文统一

### 当前问题

Figure 1 最后一格目前使用：

```text
delay / Doppler / power
```

而论文真正定义和比较的是：

```text
excess delay
relative Doppler
relative power
```

### 修改目标

Figure 1 最后一格改为：

```text
excess delay / relative Doppler / relative power
```

caption 与正文同步。

---

## P0-6. Figure 2 统一 delay / excess delay 表述

### 当前问题

正文同时写：

```text
excess delay = 1.1 samples
secondary delay = 1.2 samples
```

Figure 2 又写：

```text
Secondary delay: 1.2 samples
```

同时横轴是：

```text
Excess delay (samples)
```

容易让读者误以为同一条 path 有两个互相矛盾的 delay。

### 修改目标

Figure 2 和正文统一只使用论文主参数：

```text
Excess delay: 1.1 samples
Relative Doppler: -4.72 Hz
Relative power: -7.85 dB
```

删除：

```text
Secondary delay: 1.2 samples
```

除非确有非常必要的科学理由保留 absolute/relative delay distinction；
若保留则必须明确定义 direct-path reference，但默认建议删除。

### 纵轴术语

若 Figure 2 当前纵轴为：

```text
Mean relative power (dB)
```

核对该值是否确实为多 snapshot 平均。

- 若不是论文明确使用的平均量：改为 `Relative power (dB)`；
- 若确实是平均值：正文必须说明平均方式。

默认优先统一为：

```text
Relative power (dB)
```

---

# P1 — 强烈建议修改

P1 主要清理工程报告/审计语言、自造术语、防御性表达，以及无线/GNSS术语不统一问题。

---

## P1-1. 删除 `bounded` 这类内部审计语言

### 当前问题

正文多处存在：

```text
bounded descriptive comparison
bounded comparison
```

这是内部 evidence governance 语言，不像正常 IEEE 论文。

### 修改目标

直接删除 `bounded`。

例如：

```text
These measurements provide a basis for bounded descriptive comparison...
```

改为：

```text
The extracted path parameters are compared across four evaluated
road-environment categories.
```

Conclusion 中：

```text
supports bounded comparison
```

改为自然的：

```text
supports comparison of the measured path characteristics across
the evaluated environments
```

---

## P1-2. 删除 Introduction 中 `conservative in its confirmation rule`

### 当前问题

类似：

```text
path-level analysis that is both physically interpretable and
conservative in its confirmation rule
```

语气像作者在提前为算法辩护。

### 修改目标

直接陈述科学问题：

```text
Real dynamic raw-IQ measurements therefore require path-level analysis
that distinguishes locally fitted components from temporally persistent
and jointly confirmed paths.
```

---

## P1-3. `traceable path observations` 改成科学论文术语

### 当前问题

`traceable` 带 provenance / QA 味。

### 修改目标

可改为：

```text
path-resolved multipath estimation
```

或：

```text
reliable path-level characterization
```

优先前者。

---

## P1-4. 删除自造术语 `mother set`

### 当前问题

III-C 当前类似：

```text
The resulting valid observations are the mother set for subsequent estimation.
```

`mother set` 不是这里的标准无线/GNSS术语。

### 修改目标

改为：

```text
The resulting valid observation windows form the input set for
subsequent candidate screening and estimation.
```

后一句类似：

```text
this formation step does not assign a multipath label
```

若只是内部审计说明，建议删除。

---

## P1-5. `reliable center` 改成自然术语

### 当前问题

`reliable center` 是内部 pipeline 术语，不够学术自然。

### 修改目标

全文改成：

```text
temporally consistent candidate
```

例如：

```text
A reliable center requires...
```

改：

```text
A temporally consistent candidate is retained when...
```

```text
centered on a reliable window
```

改：

```text
centered on the temporally consistent candidate window
```

---

## P1-6. `snapshot wins` 改成标准模型选择表述

### 当前问题

```text
requires at least four snapshot wins
```

像代码变量。

### 修改目标

改成：

```text
a higher-order model is retained only if it is favored in at least
four of the five snapshots
```

或基于代码真实逻辑的等价表述。

---

## P1-7. 删除 `joint-confirmation path-table criterion`

### 当前问题

```text
satisfies the joint-confirmation path-table criterion
```

把程序 artifact `path table` 带进了科学正文。

### 修改目标

改为：

```text
Only a valid joint solution in which a secondary component satisfies
the final joint-confirmation criteria is retained as a confirmed
multipath path.
```

不暴露内部 CSV/field 名。

---

## P1-8. Figure 3 清理审计式 labels

### 当前问题

Figure 3 中存在：

```text
Candidate wins.
Unique analysis objects (count)
Local model-order evaluations ... not unique candidates
not an additional unique-object stage
```

过度像统计口径审计图。

### 修改目标

图内优先统一为：

```text
Valid 40-ms windows
Screened candidates
Temporally consistent candidates
Jointly evaluated candidates
Confirmed paths
```

纵轴：

```text
Count
```

关于 `L=1--4` 是同一窗口的不同模型阶数，正文保留一次解释即可。

不要在图里重复两次：

```text
not unique candidates
not an additional unique-object stage
```

若必须保留 model-order evaluation annotation，压缩成一句中性注释：

```text
Local model-order evaluations: L = 1--4 per screened window
```

---

## P1-9. 删除 observation-span / occurrence-rate 防御段落

### 当前问题

当前 Results C 有一整段：

```text
The observation spans derived from...
177.38 s / 203.16 s / 383.98 s / 150.50 s...
Because valid observation windows overlap...
event counts are used ... rather than normalized occurrence-rate estimates.
```

论文并没有声称 occurrence rate。

主动写这一段，会把 reviewer 注意力引向：

```text
denominator 不完整
不能做 occurrence-rate
```

而这并非当前论文必须解决的问题。

### 修改目标

**建议整段删除。**

Table II 保留 measurement coverage 即可。

除非删除后影响某个必要 claim，否则不要保留这些 observation-span 数值。

---

## P1-10. Highway/Open 不主动强调“样本少”

### 当前问题

IV-D 类似：

```text
The currently available Highway/Open paths are fewer...
```

Figure 4 已经有 `n=2`，无需正文再次自我提醒。

### 修改目标

改成：

```text
The Highway/Open paths occupy a comparatively compact observed
delay and relative-Doppler range in the present measurements.
```

或更短。

---

## P1-11. Conclusion 删除“还没做完什么”的尾句

### 当前问题

当前结尾类似：

```text
Future work will expand independent scene coverage and develop
the path and channel-parameter databases required for broader
statistical analysis.
```

会主动提醒 reviewer：

- coverage 还不够；
- database 没建立；
- statistical analysis 没完成。

这些并非当前 VTC 主结果所必需。

### 修改目标

建议删除该 future-work 尾句，改成正向结束：

```text
The results demonstrate that the proposed processing chain can resolve
and compare confirmed GNSS multipath components in excess delay,
relative Doppler, and relative power under real dynamic road measurements.
```

不要新增新的 limitation。

---

## P1-12. 全文统一无线/GNSS术语

做一次全局术语审查。

### A. `NAV-aided / navigation-aided`

当前混用。

建议优先统一成：

```text
navigation-data-aided
```

标题/小节若过长，可局部保留：

```text
navigation-aided
```

但必须一致。

---

### B. `NAV wiping`

建议改为标准一些的：

```text
navigation-bit wipe-off
```

或：

```text
navigation-data wipe-off
```

GPS L1 C/A 场景优先：

```text
navigation-bit wipe-off
```

---

### C. `decoded navigation symbols`

优先：

```text
decoded navigation data bits
```

如果实现确实以 20-ms NAV bit 为基本单位。

---

### D. `carrier-to-noise density`

改为：

```text
carrier-to-noise-density ratio (C/N0)
```

若正文没有真正使用 SNR，不要为了并列而写：

```text
C/N0 or SNR
```

---

### E. `scene / scenario / environment / case`

统一层级。

推荐：

```text
environment category
    = Urban / Mountain/Valley / Highway/Open / Reflective-Feature 等

measurement run
    = 一次独立数据采集

PRN track
    = 某 measurement run 内的一条卫星轨迹
```

尽量避免正文继续混用：

```text
scene
scenario
case
measurement
```

尤其 Table II 的：

```text
Independent scenes
```

建议改为：

```text
Independent measurement runs
```

---

### F. direct path 术语

统一：

```text
direct component
```

或：

```text
direct path
```

不要在同一段反复切换：

```text
direct contribution
direct component
direct path
```

推荐 Method 中：

```text
direct component
```

Results 中：

```text
direct path
```

若能全文统一一种更好。

---

### G. Doppler

定义一次后统一：

```text
relative Doppler
```

若 Figure 4 强调符号，可写：

```text
signed relative Doppler
```

但不要正文在：

```text
Doppler
relative Doppler
signed relative Doppler
```

三种之间无规则切换。

---

### H. delay

环境比较统一：

```text
excess delay
```

不要在 Figure 1/2/4 与正文混用：

```text
delay
secondary delay
excess delay
```

除非明确区分定义。

---

### I. power

统一：

```text
relative power
```

不要混用：

```text
power
relative power
mean relative power
```

除非平均值有明确方法定义。

---

## P1-13. 重新命名或定义 `Special Reflective`

### 当前问题

`Special Reflective` 不是无线传播领域常见标准环境类别，像内部人工标签。

### 推荐方案

优先考虑改成：

```text
Reflective-Feature
```

或：

```text
Reflective-Structure
```

当前更推荐：

```text
Reflective-Feature
```

因为这类场景包含显著潜在反射特征，但不能声称具体 reflector 物理机制已经验证。

### Section II-C 中增加一句定义

例如：

```text
The reflective-feature category contains road measurements with
prominent surrounding structures or surfaces that can support strong
reflections, including bridge/water and rail/infrastructure settings.
```

注意措辞：

- 不要写 `proven strong reflectors`；
- 不要把环境标签当作物理真值。

若改类别名，需要同步：

-正文；
- Table II；
- Figure 3；
- Figure 4；
- captions；
- Chinese review；
- handoff 中论文术语。

不要改原始 evidence 文件中的工程 metadata 值，除非明确需要；可以在论文层做 display-name 映射。

---

## P1-14. Section II-C 不再只是重复四类环境名单

### 当前问题

II-A 已经提过四类环境，II-C 又只列：

```text
Urban
Special Reflective
Highway/Open
Mountain/Valley
```

信息重复。

### 修改目标

把 II-C 改成一小段真正有信息的场景描述。

建议骨架：

```text
Measurements cover four road-environment categories:
dense urban roads, mountain/valley roads, open/highway roads,
and scenes containing prominent reflective features.
These categories describe the measurement surroundings rather
than vehicle-specific operating conditions.
```

如已将 `Special Reflective` 改名，则同步使用新名称。

---

## P1-15. Section II-D 与 III-C 去重

### 当前问题

II-D 和 III-C 都在重复：

```text
tracking/telemetry
PRN/time alignment
navigation wipe-off
40-ms windows
```

### 修改目标

II-D 只讲宏观 workflow + Figure 1：

```text
Fig. 1 summarizes the processing chain from raw-IQ acquisition
to path-level parameter estimation. GNSS-SDR tracking and decoded
navigation data provide the timing and data-bit information required
for observation formation, after which candidate screening, SAGE
estimation, temporal validation, and joint confirmation are applied.
```

III-C 再讲具体 observation formation 方法。

---

## P1-16. `BIC gain` 改成明确的标准表述

### 当前问题

```text
a BIC gain of at least 10
```

BIC 通常越小越好，“gain”没有定义方向。

### 修改目标

如果代码真实逻辑是：

```text
BIC(previous order) - BIC(higher order) >= 10
```

则写：

```text
the higher-order model must reduce the BIC by at least 10
```

必须先核对代码/Method artifact，不能猜。

---

## P1-17. 解释 40-ms windows 与 5×20-ms snapshots 的关系

### 当前问题

前文一直使用：

```text
40-ms observation windows
```

III-E 突然出现：

```text
five contiguous 20-ms snapshots
approximately 100 ms
```

读者可能误以为窗口定义前后冲突。

### 修改目标

改成：

```text
For final joint confirmation, a 100-ms interval centered on each
temporally consistent candidate is partitioned into five contiguous
20-ms snapshots.
```

随后再写 joint estimation / model selection。

---

## P1-18. Results C 第一段重写 denominator 关系

### 当前问题

当前类似：

```text
30 path observations from 12 path-bearing PRN tracks across
8 independent scenes; Table II summarizes...
```

`path-bearing PRN tracks` 是自造术语，而且 8/12 与 Table II 的 11/17 容易让人混淆。

### 修改目标

建议改成：

```text
Across 17 analyzed PRN tracks from 11 independent measurement runs,
12 tracks from 8 runs yielded 30 jointly confirmed multipath paths.
```

这样一次讲清：

```text
total analyzed coverage = 11 runs / 17 tracks
positive confirmed-path subset = 8 runs / 12 tracks / 30 paths
```

随后再引出 Table II / Figure 4。

---

# P2 — 润色与结构优化

P2 不属于硬错误，但建议完成以提高投稿稿的专业性、可读性和精炼度。

---

## P2-1. 合并 Section IV-C 与 IV-D

### 当前问题

目前：

```text
IV-C Environment-Wise Path Characteristics
IV-D Cross-Environment Multipath Characteristics
```

两节内容存在重复：

- IV-C 给 range / median / Figure 4；
- IV-D 又按四环境解释一次。

### 修改目标

考虑合并成：

```text
C. Multipath Characteristics Across Measurement Environments
```

推荐结构：

```text
Paragraph 1:
measurement coverage + confirmed-path subset

Paragraph 2:
ranges + medians + Figure 4

Paragraph 3:
environment-wise physical interpretation
```

合并后检查版面，避免 Fig. 4 浮动恶化。

如果合并明显破坏版面，可保留 C/D，但删除重复句。

---

## P2-2. 降低 IV-D 中环境因果暗示

### Mountain/Valley

当前类似：

```text
broad range of relative Doppler, consistent with richer
time-varying propagation geometries under vehicle motion
```

`richer propagation geometries` 模糊且带因果推断。

建议：

```text
Mountain/Valley measurements exhibit a broad observed range of
relative Doppler, indicating substantial variation among the
resolved propagation components.
```

---

### Reflective category

当前类似：

```text
consistent with localized strong-reflector conditions
```

如果没有独立 reflector ground truth，偏强。

建议：

```text
reflecting substantial path-to-path variation in these measurement settings
```

或：

```text
consistent with the presence of prominent surrounding reflective structures
```

后者仍需注意只是环境描述，不是反射体机制验证。

---

## P2-3. IV-D 最后一句降 overclaim

### 当前问题

类似：

```text
The framework therefore resolves and characterizes
environment-associated multipath behavior...
```

容易让人理解为已经建立环境效应关系。

### 修改目标

改成：

```text
The framework therefore enables path-level comparison of multipath
characteristics across the evaluated measurement environments.
```

---

## P2-4. 修改标题，弱化 `vehicular` 作为研究主体

### 当前标题

```text
SAGE-Based High-Resolution Multipath Characterization of
GPS L1 C/A Signals in Dynamic Vehicular Environments
```

### 问题

正文自己明确：

```text
the vehicle served as the dynamic antenna platform;
vehicle type and vehicle performance were not treated as research variables
```

因此 `vehicular environments` 容易让 VTC reviewer 期待：

- V2V/V2I；
- vehicular propagation channel；
- vehicle-specific channel behavior。

而当前研究核心实际是：

```text
dynamic road measurement
+ GNSS multipath path extraction
+ SAGE
```

### 推荐标题候选

优先：

```text
High-Resolution SAGE Characterization of GPS L1 C/A Multipath
in Dynamic Road Environments
```

备选：

```text
SAGE-Based High-Resolution Multipath Characterization of
GPS L1 C/A Signals from Dynamic Road Measurements
```

修改标题后必须同步检查：

- Abstract；
- Introduction；
- Contribution 3；
- Section II；
- Conclusion；
- PPT / handoff 标题字段。

---

## P2-5. 摘要去掉项目/审计口吻

### 当前问题

类似：

```text
These measurements provide a basis for bounded descriptive comparison...
```

### 推荐改法

```text
The confirmed paths provide estimates of excess delay,
relative Doppler, and relative power, which are compared across
four evaluated road-environment categories.
```

如果前句已说 path-level quantities，可避免重复。

---

## P2-6. Introduction 第一项贡献改得更像论文贡献

### 当前问题

类似：

```text
it establishes a real dynamic GPS L1 C/A raw-IQ measurement
and processing basis
```

`establishes ... basis` 像项目总结。

### 推荐

```text
First, it presents a real-world GPS L1 C/A raw-IQ measurement
and processing chain that combines GNSS-SDR tracking products
with navigation-data-aided observation formation.
```

同时检查第二、第三贡献的并列语法是否一致。

---

## P2-7. References 中保护缩写大小写

检查 `.bib` 中标题：

```text
GPS
GNSS-SDR
SAGE
CMCD
```

防止 BibTeX 自动输出成：

```text
Gps
Gnss-sdr
Sage
Cmcd
```

使用花括号保护，例如：

```bibtex
{GPS}
{GNSS-SDR}
{SAGE}
{CMCD}
```

只修 bibliography capitalization，不改变引用内容。

---

## P2-8. 结果数字精度适当收敛

当前代表性案例使用：

```text
-4.7159 Hz
-7.8526 dB
60.5369 s
```

对于会议论文正文，可考虑适当简化为：

```text
-4.72 Hz
-7.85 dB
60.54 s
```

原则：

- Figure/source evidence 保留完整精度；
- 正文展示使用与测量/估计精度相称的小数位；
- 同一 quantity 全文精度风格一致；
- 不因 rounding 改变任何结论。

---

# 3. 全文统一后的推荐术语表

| 概念 | 推荐正式论文术语 |
|---|---|
| 四类大环境 | `environment category` |
| 一次独立采集 | `measurement run` |
| 某卫星跟踪对象 | `PRN track` |
| GPS 导航数据辅助 | `navigation-data-aided` |
| 去导航比特 | `navigation-bit wipe-off` |
| 40 ms 输入观测 | `valid 40-ms observation window` |
| 初筛结果 | `screened candidate` / `candidate window` |
| 时间持续候选 | `temporally consistent candidate` |
| 最终联合确认 | `multi-snapshot joint confirmation` |
| 一个联合确认区间 | `confirmed event` |
| 已确认次级传播路径 | `confirmed multipath path` |
| 相对直达路径的时延 | `excess delay` |
| 相对直达路径的 Doppler | `relative Doppler` |
| 相对直达路径功率 | `relative power` |
| RF-Catcher V2 | `acquisition device` |
| 图表计数纵轴 | `Count` |
| 特殊反射类（建议） | `Reflective-Feature` |

---

# 4. 建议删除/替换词扫描

修改后对英文正文、captions、Figure labels、Table labels 做全文扫描。

## 应删除或人工判断的词

```text
bounded
mother set
reliable center
snapshot wins
path-table criterion
unique analysis objects
Candidate wins
Confirmed configuration
VTC study
VTC research
reported excess delay
descriptive only
F1023_
QA PASS
production
manifest
Tier A+B
joint_valid
joint_multipath_count
is_multipath
LOS proven
no multipath
path-level coherence
```

说明：

- handoff / evidence / audit 文件允许保留工程词；
- **正式论文正文、Figure、Table、caption** 中不应出现内部治理语言。

---

# 5. 修改后必须重新检查的科学不变量

完成 P0/P1/P2 后确认：

```text
L = 1 means direct-only model
L = 2 means direct + one secondary component

L >= 2 != confirmed multipath
temporally consistent candidate != confirmed multipath
final confirmation = multi-snapshot joint confirmation
```

以及：

```text
Path-level quantities:
- excess delay
- relative Doppler
- relative power
```

继续保持：

```text
PATH_LEVEL_COHERENCE_DEFINED = NO
```

Figure/Table 科学数据不变：

```text
FIGURE_DATA_CHANGED = NO
TABLE_DATA_CHANGED = NO
```

除以下显示层修改外：

- Figure 1 parameter labels；
- Figure 2 terminology / displayed rounding；
- Figure 3 labels / annotation simplification；
- 环境 display name（如 Special Reflective -> Reflective-Feature）。

这些属于 presentation / terminology change，不是 underlying scientific data change。

---

# 6. 编译与 QA

修改后重新编译英文、中文。

## English

检查：

```text
LaTeX errors = 0
fatal errors = 0
undefined citations = 0
undefined references = 0
overfull boxes = 0 or manually reviewed
Figure 1-4 present
Table I-II present
References present
```

逐页视觉检查：

- Figure 3 labels 是否清晰；
- Figure 4 仍位于合理位置；
- Table I / II 不溢出；
- 修改标题后第一页不异常；
- IV-C/IV-D 合并后 float 不恶化；
- 正文仍约 4–5 IEEE pages；
- 不为了压页数破坏字号/间距。

## Chinese review

英文最终确认后再同步中文。

中文重点消除：

```text
“有界描述性比较”
“母集”
“可靠中心”
“快照获胜”
“路径表判据”
“独立分析对象”
“特殊反射”
```

如英文选择新的 `Reflective-Feature`，中文建议统一为：

```text
显著反射特征场景
```

或经作者最终确认的自然中文名称。

---

# 7. Codex 输出报告要求

执行完成后按以下格式报告。

## A. P0

```text
P0-1 formula L/tau0 consistency = PASS/FAIL
P0-2 Fig3/IV-A narrative alignment = PASS/FAIL
P0-3 Table I acquisition terminology = PASS/FAIL
P0-4 event/path definition = PASS/FAIL
P0-5 Fig1 parameter terminology = PASS/FAIL
P0-6 Fig2 delay terminology = PASS/FAIL
```

## B. P1

逐项报告 P1-1 ～ P1-18：

```text
changed / not changed / reason
```

若不执行某项，必须说明原因，不可静默跳过。

## C. P2

逐项报告 P2-1 ～ P2-8。

对于：

```text
title change
Special Reflective rename
IV-C/IV-D merge
```

若实际版面/术语审查认为不宜执行，必须先报告理由，不要擅自扩大修改范围。

## D. Files changed

列出：

```text
main.tex
English Markdown mirror
main_cn_review.tex
Chinese Markdown review
Figure source/asset if label-only update
VTC Writing Handoff
Paper Handoff
references.bib if capitalization fixed
```

## E. Compile/QA

报告：

```text
English pages
Chinese pages
LaTeX/BibTeX status
undefined citation/reference
overfull/underfull warnings
visual QA
Fig. 4 final page/location
```

## F. Frozen state

最后明确：

```text
SCIENTIFIC_CONTENT_CHANGED = NO
SCIENTIFIC_DATA_CHANGED = NO
NEW_EXPERIMENT_EXECUTED = NO
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
PRODUCTION_EXECUTED = NO

CURRENT_PHASE = USER_AUTHOR_REVIEW
SCIENTIFIC_CONTENT_FROZEN = YES
SAGE_PRODUCTION_STOPPED = YES
```

---

# 8. Stop Rule

完成本文档规定的 P0 / P1 / P2 targeted revision、英中同步、handoff 更新和 QA 后立即停止。

不要自动：

- 启动新的 reviewer simulation；
- 新增实验；
- 重跑 SAGE；
- 修改 Figure/Table scientific data；
- 补统计模型；
- 增加 occurrence-rate；
- 增加 elevation-conditioned analysis；
- 开始投稿。

如发现新的**科学内容问题**，只报告给 Commander / 作者，不自行扩展修改范围。
