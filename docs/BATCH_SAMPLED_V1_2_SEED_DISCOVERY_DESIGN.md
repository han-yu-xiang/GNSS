# batch-sampled-v1.2 Seed Discovery / Adaptive Screening 设计

**项目：** `E:\GNSS_Multipath_Project`  
**文档状态：** 规划与算法/工程设计；本次未运行 MATLAB、SAGE 或 raw-IQ prototype  
**适用范围：** 当前已验证的 10.23 MHz Pipeline V3；不处理 20.46 MHz  
**禁止动作：** 不修改 `run_nav_sage_pipeline.m`、scene、metadata、inventory、已有 full-scan 结果或 v1/v1.1 sampling validation 结果；不生成 execution request。

## 1. 设计结论先行

`batch-sampled-v1` 和 `batch-sampled-v1.1` 的失败不是“随机 seed 不够”或“guard 只需要从 ±2 加大到 ±5”。失败的结构性原因是：初始样本没有观察到某个事件中心时，Pipeline V3 的 Stage1 candidate 规则根本不会产生该中心的 seed；后续 guard 只能围绕已经存在的 seed 展开。

v1.2 应把问题改写为：

```text
Stage0 全量窗口
    -> 全部窗口低成本风险发现（无物理标签）
    -> 连续高风险区域 promotion
    -> 对 promotion 区域运行原始完整 Stage1
    -> 根据真实 Stage1 candidate 规则补齐 ±2，必要时 ±5/更大连续 block
    -> 只对完整 fine/guard 闭包运行原始 Stage2
    -> 原 Stage3/Stage4 判据保持不变
```

推荐主方案是 **Hybrid coarse-to-fine**：

1. 全量使用 Stage0/tracking/telemetry/geometry 可得到的低成本特征建立透明、固定版本的风险底图；
2. 对全部 Stage0 window 执行一个极低成本、可选 raw-IQ coarse screen，而不是只抽稀窗口；
3. 将 coarse 高风险点合并为连续区域并 promotion，区域外不调用完整 Stage1；
4. fine Stage1 完全沿用 Pipeline V3 的主峰、残差峰、Doppler/delay 搜索和 candidate 规则；
5. Stage2/Stage3/Stage4 只使用 fine 结果，不把 coarse score 当作 SAGE 参数或确认标签。

在 coarse prototype 和离线 replay 通过前，不恢复 Wave-2A 剩余 full-scan，也不生成 sampled execution request。

## 2. 当前证据、输入边界与术语

### 2.1 必须读取的实际来源

本设计依据以下当前文件和已有结果：

- `scripts/sage_pipeline/run_nav_sage_pipeline.m`
- `docs/BATCH_SAMPLED_V1_OFFLINE_COVERAGE_REPORT.md`
- `docs/BATCH_SAMPLED_V1_1_OFFLINE_COVERAGE_REPORT.md`
- `docs/GNSS_SAGE_PROJECT_HANDOFF_CURRENT.md`
- `scenes/F1023_V70_D0117_P2/sage_results/reference_scene_final_validation_report.md`
- `docs/WAVEA_10MHz_VALIDATION_REPORT.md`
- `docs/WAVE2A_G11_QA_REPORT.md`
- 各 gold run 的 `stage0_valid_40ms_windows.csv`、`stage1_nav_fast_scan.csv`、`stage2_*`、`stage3_*`、`stage4_*`。

这些文件是验证和设计依据，不允许在生产规则中读取 gold event 位置来挑窗口。

### 2.2 Gold 集合

离线设计验证仍使用 11 个 scene–PRN task：

| 组 | Task | 已知 confirmed event |
|---|---|---|
| Reference | `F1023_V70_D0117_P2/G06/ch4` | 203、264 |
| Reference | `F1023_V70_D0117_P2/G11/ch5` | 640 |
| Reference | `F1023_V70_D0117_P2/G12/ch6` | 970、971 |
| Reference | `F1023_V70_D0117_P2/G25/ch0` | 无；LOS/low-multipath control |
| Reference | `F1023_V70_D0117_P2/G28/ch1` | 无；Stage3/Stage4 rejection control |
| Reference | `F1023_V70_D0117_P2/G29/ch7` | 80 |
| Reference | `F1023_V70_D0117_P2/G32/ch11` | 82、84 |
| Wave-A | `F1023_V70_D0120_P7/G16/ch1` | 1337、1338、1406、2079 |
| Wave-A | `F1023_v50_D0127_P1/G25/ch0` | 无；negative/control |
| Wave-A | `F1023_V70_D0122_P1/G12/ch6` | 835、836、1278 |
| Wave-2A | `F1023_V120_D0121_P2/G11/ch0` | 无；长场景 negative/control |

confirmed event 的定义只来自现有 full-scan Stage4：`joint_valid == 1 && joint_multipath_count > 0`，并由 path 表核对 `is_multipath=1`。v1.2 选择阶段不能读取这些位置；replay 完成后才可计算 recall。

### 2.3 v1/v1.1 已经证明什么

- v1：reference 因 `N0 <= 1200` 是 full-scan-equivalent，已知事件覆盖 100%；Wave-A G16 event-center recall `47.5%`、±2 closure recall `25.0%`；G12 分别 `53.3%`、`36.7%`。
- v1.1：在 block 11/21/31/41、1200 总 fine budget、seed_00–seed_09 下，最好的加权 adaptive center recall 为 `83.33%`，closure recall 为 `80.67%`；G16 最好 adaptive center/closure `62.5%/60.0%`，G12 最好 `90.0%/90.0%`，仍未达 100%。
- v1.1 budget sweep 到 4800 仍没有跨 seed、跨 reference+Wave-A positive task 的稳定 100% center+closure；因此 v1.2 不再把“增大随机抽样预算”当作主要方向。
- v1.1 的 strict replay 已确认 hidden Stage1 行不能用于产生初始 seed；这是 v1.2 必须保留的规则。

## 3. Pipeline V3 当前 Stage0 与 Stage1 的真实实现

### 3.1 Stage0 真实母集

`buildSymbolCatalog` 位于 `run_nav_sage_pipeline.m` 约 630–692 行，实际做了：

1. 读取 telemetry DAT 的每条 32-byte record：`tow_s`、`sample_counter`、`preamble_tow_s`、`nav_symbol`、`prn`；
2. 只保留目标 PRN 和 NAV symbol `±1`；
3. 按 sample counter 找最近 tracking sample，误差必须不超过 `sampleStepTolerance=2`；
4. 要求 tracking PRN 一致、Doppler 有限、CN0≥30 dB-Hz；
5. 有限的 carrier lock test 必须不低于 `-0.5`；
6. 记录与下一条 telemetry 的 sample step、TOW step 和 `continuous_to_next`。

`buildFortyMsCatalog` 约 695–750 行再要求：

- 两个相邻 20 ms step 连续，且原 telemetry row 真正相邻；
- sample step 接近 `samplesPer20Ms`，TOW step 接近 0.020 s；
- 每个 window 由两个已知 NAV symbol 组成，记录 `split_samples`；
- 记录 NMEA 插值速度及其来源；无法插值时使用 `fallback_120_kmh` 作为 Doppler bound 的算法上界来源；
- 形成完整 `window_id`、`symbol_index`、`sample_start_zero_based`、`recording_time_s`、`tow_s`、`nav_symbol_1/2`、`tracking_doppler_hz`、`code_frequency_hz`、`cn0_db_hz`、`vehicle_speed_kmh`、`speed_source`、`relative_doppler_bound_hz`。

因此 v1.2 的第一条硬约束是：**Stage0 CSV/MAT 的所有 window_id 永远保留，coarse/fine 只改变后续可供性，不删除或改写 Stage0。**

### 3.2 当前 tracking MAT 实际可见的低成本字段

当前 Pipeline 的 `readTrackingMat`（约 563–587 行）只读取并标准化：

- `PRN_start_sample_count` 或 `PRN_start_sample_counter`；
- `PRN`；
- `carrier_doppler_hz`；
- `code_freq_chips`；
- `CN0_SNV_dB_Hz` 或 `CN0_dB_Hz`；
- 可选 `carrier_lock_test`；
- 可选 `TOW_ms`。

对代表性 reference/Wave-A tracking MAT 做只读二进制字段名检查，还能看到：

- `Prompt_I`、`Prompt_Q`；
- `carrier_doppler_rate_hz`；
- `code_freq_rate_chips`；
- `code_error_chips`、`code_error_filt_chips`。

但当前 reader 没有读取这些额外字段；在检查到的 MAT 中没有看到可以直接假设存在的 `Early`/`Late` 字段。因此：

- Prompt I/Q、carrier/code rate、code error 是**可研究的候选 feature**，但需要独立 schema probe/小型提取器；
- 不能在当前工程中声称已经有 Early/Late discriminator feature；
- 当前 Stage0 window CSV 只有上述已落盘字段，纯 Python 离线第一版只能可靠使用 CSV 字段和 geometry diagnostic。

### 3.3 Stage1 `runFastScan` 的真实步骤

`runFastScan` 约 815–858 行逐 window 调用 `scanOneWindow`；当前 full-scan 每个完整 Stage0 window 都进入此循环。`scanOneWindow` 约 861–930 行的实际顺序为：

1. `loadNavWipedFortyMs` 调 `readIq` 读取 40 ms raw IQ；
2. 按 `nav_symbol_1/2` 对两个 20 ms 段做 NAV wipe；
3. 减均值、RMS normalize；
4. 由该 window 的 `code_frequency_hz` 生成 GPS C/A replica FFT context；
5. 以 `dopplerSign * tracking_doppler_hz` 为主 Doppler reference；
6. 主路径 coarse grid：delay `-5:1:10` samples，共 16 个 delay 点；Doppler `reference-125:25:reference+125`，共 11 个点；
7. 选择主路径后做两轮局部 refine：delay 步长 `0.2` sample、局部半宽 `1` sample；Doppler 步长 `10 Hz`、局部半宽 `30 Hz`；
8. 用 `solveAmplitudes` 估计主路径并从 normalized observed 中减去主路径，得到 residual；
9. residual delay 从主路径后至少 `1` sample 延伸到最大 excess delay `30` samples，以整数 delay 搜索；
10. residual Doppler 以该窗口 `relative_doppler_bound_hz` 为范围、步长 `50 Hz`；
11. 对 residual metric 排序，按至少 `2` samples 和 `40 Hz` 的独立性分离，保留最多 3 个 residual peak；
12. 以 `screenResidualPowerDb=-25 dB` 产生 `has_one_strong_residual`、`has_two_strong_residuals`，并写 `screen_score_db`。

`chooseStage2Candidates` 约 969–1002 行只看**已经产生的 Stage1 fine table**：

- valid row 必须 `scan_valid==1` 且 residual peak1 有限；
- two-peak rows 按 peak2 power 排序，one-peak rows 按 peak1 power 排序；
- 最多 `maximumBaseCandidates=24` 个 base，少于 8 个时按规则补到 `minimumBaseCandidates=8`；
- 每个 base 加 `neighborRadius=2` 的邻域，最后去重；
- Stage2 只收到该结果。

这解释了为什么 v1/v1.1 不能只扩大 guard：hidden window 从未进入上述 `stage1` fine table 时，不可能产生 `base`。

## 4. 当前 Stage1/Stage2 的计算成本分解

以下是基于真实代码的成本结构，不是 profiler 结果。墙钟比例和任何新方案的加速数字在 prototype 前都只能作为待测量假设。

### 4.1 每个 full Stage1 window 的成本

| 步骤 | 真实操作 | 成本/风险判断 | 可否 proxy |
|---|---|---|---|
| raw IQ 读取 | `readIq` 每次 `fopen`、`fseek(startSample*4)`、读取 40 ms 的 interleaved int16 I/Q，再转 double/complex | 高；相邻 40 ms windows 实际重叠约 20 ms，但当前实现重复打开和读取；Wave-2A 长场景会重复访问外部 raw | 可用 contiguous chunk/block read；不能改变 fine 结果 |
| NAV wipe/normalize | 两段乘已知 ±1，均值/RMS | 线性 O(N)，相对 FFT 较低，但每个 fine window 都重复 | coarse 可同样执行短段；tracking-only 无法代替 signal wipe |
| code context | `generateGpsCaCode`、构造 code index/time、`fft(localCode)` | 每 window 重建；是可缓存/量化的低层优化点，尤其 code frequency 变化平缓时 | 可使用按长度/quantized code frequency 的 cache，但必须 prototype 验证偏差 |
| 主 delay/Doppler grid | 16×11 grid；每个 Doppler 在 `gridSearchPath` 中一次 FFT + 一次 IFFT，取 16 个 delay metric | 每 window 约 11 对 FFT/IFFT，属于主要成本 | 粗 Doppler/更少 delay 点/短积分/共享 FFT |
| 主路径 refine | 2 轮；每轮约 0.2-sample delay 局部 grid 和 10-Hz Doppler 局部 grid，每点用 replica dot product | 比完整 FFT grid 小，但 direct O(N) dot 数量仍不低 | coarse 完全跳过；fine 不变 |
| amplitude solve/residual | 构造 replica、线性 amplitude solve、重构 residual | 中等；为 residual scan 必需 | coarse 可只保留 normalized peak/residual proxy；不能替代 fine residual |
| residual delay/Doppler grid | delay 约从 main+1 到 main+30 的整数点；Doppler 由 per-window bound、50 Hz spacing；每 Doppler 又做 FFT/IFFT | **当前 Stage1 最可能的高成本部分**，grid 宽度随 `relative_doppler_bound_hz` 变化；fallback speed 会使范围保守 | coarse 用少量 Doppler 假设/更粗 spacing/短积分/低分辨率 residual |
| residual peak sort/separation | 将 delay×Doppler metric 全部排序，做独立性筛选并保留 top3 | 相比 FFT 次要，但 metric 矩阵和 sort 会随 residual grid 增大 | coarse 只取少量 top-k 或分块 maxima |
| checkpoint | 每 20 个窗口保存 `stage1_nav_progress.mat` | 非主计算，但长任务频繁写 MAT 可能增加 I/O | coarse 使用 append/分块 manifest；fine 仍保持可恢复 |

### 4.2 代码层面的重复成本

- `readIq` 在 Stage1 每个 window 单独打开 raw；Stage2 对每个 candidate 又重新读取同一 40 ms 和重新构造 context，Stage1/Stage2 之间没有 raw/context cache。
- 40 ms windows 由相邻 20 ms NAV symbol 生成，存在重叠读取机会；当前实现没有利用。
- Stage2 `fitAllOrders` 对每个 candidate 重新构造 L1 seed，然后 L=2–4 逐阶做 residual initialization 和最多 `maximumSageIterations=10` 的 SAGE refine；因此 Stage2 不是简单的四次廉价扫描。
- Stage3/Stage4 只在较少 candidate/reliable center 上运行；当前 G11 的主要吞吐证据是 Stage1 约 8.1 h、Stage2 约 11.4 h，不能把 Stage3/4 当作主要瓶颈。

### 4.3 为什么 G11 的 15,210 fine windows 很贵

Wave-2A G11 full-scan 有 15,210 个 Stage1 windows、67 个 Stage2 candidate、268 个 Stage2 model rows，Stage1 约 8.1 h、Stage2 约 11.4 h、总约 19.6 h。它证明的是现有实现的吞吐风险，不证明某个单一内部操作的精确占比。v1.2 的目标是降低 `N0 × C_fine_stage1` 和重复 raw I/O，而不是把最终 fine Stage1/Stage2 判据放宽。

## 5. Oracle-free Seed Discovery 方案比较

### 5.1 严格 oracle-free 定义

生产运行中，以下信息在 coarse promotion 前禁止使用：

- 任何 Stage4 confirmed event window/location；
- Stage3 reliable center/Stage4 labels；
- 未晋级窗口的 full Stage1 row；
- 用 full-scan Stage1 的 residual power 反推 coarse score；
- 用当前 gold event 位置人工添加 forced block。

full-scan Stage1/Stage2/Stage4 只能在一次已冻结 selection 后作为离线 gold replay 的**事后测量**，输出 recall、漏检原因和控制组统计，不能修改已冻结的 promoter。离线 report 必须同时标注 `gold_labels_used_for_selection=false`。

### 5.2 方案 A：全窗口 Stage0/tracking/telemetry/geometry feature risk score

**输入：** 全量 Stage0 CSV；可选的 read-only tracking MAT 特征提取；通过验证的 TOW-aligned geometry；不读 raw IQ。

**建议 feature：**

| Feature | 物理依据 | 主要局限 |
|---|---|---|
| `cn0_db_hz` 绝对值、局部下降、rolling MAD/方差 | 多径相消/增强会造成快速功率起伏；CN0 是低成本 tracking 质量信号 | 低仰角、遮挡、弱信号、AGC/接收机变化也会造成同样变化；Stage0 window CN0 是两个 symbol 的 min |
| `tracking_doppler_hz` 局部 slope、二阶差分、短时残差 | 多径会扰动载波跟踪；变化率可揭示非平稳干扰 | 真实车辆加减速、oscillator、tracking noise 也会改变 Doppler；绝对 Doppler 不是多径标签 |
| `code_frequency_hz`、`code_freq_rate_chips`、code error | 码跟踪早晚相关器失真和多径延迟会改变 discriminator/code loop | 当前 Stage0 只写 code frequency；额外 rate/error 需 MAT extractor；loop dynamics 也会产生误报 |
| `carrier_lock_test`、lock drop/recovery | 多径可能造成载波锁定不稳 | 锁丢失更可能是低 CN0/遮挡；只能作质量/coverage feature，不能把 lock drop 直接 promotion 为多径 |
| `Prompt_I/Q` 功率、相位差、局部变化 | 现有 MAT 中可见 Prompt_I/Prompt_Q；多径会改变 prompt correlator 的复数幅相 | 当前 reader 未读取；不同 tracking loop、相位 unwrap、导航符号影响需要独立验证 |
| `code_error_chips`/filtered error | 等价于可用的 code discriminator residual proxy | 现有 MAT 仅字段名可见，需确认向量长度、时间对齐和符号；没有 Early/Late 字段可假设 |
| `relative_doppler_bound_hz` | 描述速度/算法应搜的相对 Doppler 范围，可用来归一化风险和限制 coarse grid | 它是运动学上界，不是多径能量；本身不能 promotion |
| `vehicle_speed_kmh`、speed change | 运动速度影响多径时间变化、Doppler 范围和需要的 block width | 不是多径证据；NMEA 缺失时可能是 fallback 上界，不得当实测速度 |
| telemetry/Nav continuity、sample/TOW gap | 标出不适合作闭包或需要升级的窗口 | 断点不是多径；应标 `coverage_inconclusive` 而非高风险事件 |
| verified window-level elevation/azimuth/SNR、局部 slope | 仰角和几何改变反射可见性；局部 elevation change 有助于传播条件分层 | 当前 geometry 不是星历重算，TOW join 还未集成生产；没有 verified join 时禁止用 summary 均值 |

**透明 score 形式：** 用事先冻结的 feature list、方向、权重和阈值；每个 run 内用 median/MAD 或固定物理归一化，不训练事件分类器。示意为：

```text
R_feature(w) = frozen_weighted_sum(
    CN0_drop/variation,
    Doppler_rate_anomaly,
    code_error_anomaly,
    Prompt_IQ_anomaly,
    verified_geometry_change,
    quality_adjustments)
```

缺失 feature 必须记录 `feature_missing`，不能填 0 伪造正常值；quality/gap 只能阻止错误 promotion 或触发 inconclusive。阈值必须在读取 gold 标签前冻结。

**优点：** 纯 Python 可从 Stage0 CSV 起步，完全不读 raw；适合全数据集预筛、成本估计和可解释性。  
**淘汰条件：** 如果在 gold replay 中任何 known center 或 ±2 closure 仍漏检，不能作为唯一 production promoter；不能用 random seed 或加预算修复。

### 5.3 方案 B：全部窗口低分辨率 raw coarse correlation/residual scan

**核心：** 对全部 Stage0 windows 打开 raw，但只做低分辨率、短积分、少 grid 的 detection proxy；不做 fine refine、BIC、SAGE 或最终 path estimate。

建议的 prototype 参数族（不是当前 pipeline 参数、不是已执行结果）：

| 维度 | 当前 fine Stage1 | coarse prototype 候选 |
|---|---|---|
| 信号长度 | 每 window 40 ms，约 `409,200` complex samples @10.23 MHz | 10 ms×4 或 20 ms×2 子段；先比较短段 max/median/variance |
| NAV wipe | 40 ms 两个 20 ms symbol 精确 wipe | 使用 Stage0 已知 symbol 对每个 10/20 ms 子段 wipe；不改变 fine wipe |
| 主 delay | `-5:1:10`（16 点），之后 0.2 sample refine | 例如步长 1–2 samples；先覆盖 main+可能 excess 的宽范围，再由 fine 重估 |
| 主 Doppler | ±125 Hz、25 Hz step（11 点） | tracking-centered 少量假设，或 100–200 Hz step 的粗范围；不得当作最终 Doppler |
| residual delay | main+1 至 +30 samples，整数 | 更粗步长或少量 residual delay bins；只保留 top-k proxy |
| residual Doppler | `±relative_doppler_bound_hz`、50 Hz step，逐 Doppler FFT/IFFT | 更少假设/更粗步长；可先仅使用 tracking-centered Doppler 和少量 offset |
| refine | 两轮 delay/Doppler local refine | 不做 |
| amplitude/SAGE/BIC | Stage1 主路径 amplitude/residual；Stage2 另行 SAGE/BIC | 不做 amplitude model selection；只输出 normalized peak、residual ratio、coarse separation |
| raw read | 每 window `fopen/fseek/fread` 40 ms；相邻窗口重复读 | 按连续 window block 一次读取 overlapping raw chunk，内存切片；至少避免每窗口 reopen/seek |
| 输出 | full Stage1 row、候选峰、error | `coarse_score`、top coarse peak、quality、raw chunk provenance；不能直接写 `scan_valid`/confirmed |

复杂度方向是 `O(N_coarse log N_coarse × D_coarse)` 加少量 delay peak，而不是 fine 的 40 ms、主 FFT grid、局部 direct refine、全 residual grid、排序和多次 raw reopen。实际收益取决于：短积分的漏检、Doppler bins、window overlap reuse、code FFT cache 和磁盘读取；不能在 prototype 前把某个倍率写成结果。

**物理风险：** 短积分和粗 Doppler 会漏掉弱/快速变化事件；因此应至少在每个 40 ms window 上保留多个短子段的 `max`/`p90` 和局部连续性，不能只取单个 10 ms 平均。粗 scan 只负责 promotion，fine Stage1/Stage2 判据不变。

### 5.4 方案 C：多尺度/分块 coarse-to-fine screening

这是 B 的调度化版本，加入连续性和风险区域合并：

1. Level 0：全量 Stage0/tracking feature；
2. Level 1：全量或全量分块 coarse raw，按连续 block 输出 coarse score；
3. Level 2：对超过 hysteresis threshold 的 block 做较高分辨率 coarse/bridge；
4. Level 3：只对连续高风险区域调用完整 fine Stage1；
5. 从 fine Stage1 的真实 candidate 规则产生 seed，补齐 ±2；预算允许时补 ±5 或更大 block；
6. Stage2 只在完整闭包运行。

**优点：** 短时事件不会因单个孤立窗口未入样本而完全消失；block 合并可减少不必要的边界 fine 调用；可以自然表达 `inconclusive`。  
**局限：** 需要 coarse prototype 和独立 namespace；hysteresis/连接规则增加状态管理；若 coarse 本身不敏感，连续 block 只会稳定地扩大漏检区域。

### 5.5 方案 D：仅全量 tracking feature + 确定性连续 block

这是最低工程成本的 fallback：用 A 的 feature score 在全时轴上做 deterministic threshold、bridge 和 block promotion，不访问 raw。它可以作为纯 Python baseline，但不应先验假设能达到 100% recall。v1.1 已说明“连续 block 本身”不能解决 hidden center 问题；D 只有在 A feature replay 通过后才可考虑。

### 5.6 方案选择

| 方案 | 现在可纯离线验证 | 召回潜力 | 成本潜力 | 决策 |
|---|---|---|---|---|
| A feature-only | 可以，Stage0 CSV/geometry；MAT extra feature 需小 extractor | 中/低，取决于 tracking 对多径的敏感性 | 很高 | 作为立即 baseline，不作为默认 production 唯一方案 |
| B low-res raw | 需要极小 raw prototype 才能得到 coarse score | 高于 A，尤其可覆盖 tracking 未明显异常的事件 | 中/高，需 measured | 作为必要的 recall fallback |
| C 多尺度 block | 需要 B 或可靠 A；调度可离线测试 | 最高的结构潜力，能保留局部短时事件 | 目标是低于全 fine，但未实测 | **推荐主架构** |
| D feature+block only | 可以 | 未知，不能由 v1.1 推断 | 最高 | 仅作对照，不直接放行 |

## 6. 推荐的 v1.2 主架构

### 6.1 固定阶段

#### Phase 0：全量 Stage0 和低成本 feature map

- 保留全量 `stage0_valid_40ms_windows.csv` 的 window_id 和源字段。
- 计算不读 raw 的 feature：CN0、Doppler/code frequency、速度/bound、sample/TOW gap、局部 slope/variance、可用 geometry join 状态。
- 如果独立 MAT extractor 已通过 schema QA，再加入 Prompt I/Q、Doppler rate、code rate/error；否则字段为 null 并写 `feature_missing`。
- 用冻结 score 生成 `feature_risk_score`，不生成 physical event label。

#### Phase 1：全窗口 coarse discovery

- 主配置：对全部 Stage0 windows 做低成本 raw coarse；按连续 chunk 读 raw，复用重叠数据。
- 每个 40 ms window 至少由多个 10/20 ms 子段计算 summary，保留 `coarse_max_score`、`coarse_persistence_score` 和 quality flags。
- 如果 raw coarse prototype 证明对全部任务过重，先使用 A feature map 作为 prefilter，但不得把 A prefilter 误称为已达到生产 recall。
- coarse 只写独立 manifest，不写 full Stage1 CSV，不修改 `nav_sage_v2`。

#### Phase 2：promotion 和连续区域合并

- 使用预先冻结的 high/low hysteresis threshold；高阈值点为 seed，低阈值用于桥接相邻高风险点。
- 将相邻 window_id 连成 components；填补 component 内部小间隙；每个 component 向两侧扩至少一个预留范围。
- promotion reason 允许：`feature_risk`、`coarse_residual`、`coarse_short_block`、`coarse_persistence`、`bridge_between_risk_points`、`guard_of_fine_candidate`、`forced_boundary_guard`。
- 不使用 event center、gold Stage1 hidden row 或 Stage4 label 作为 reason。

#### Phase 3：fine Stage1

- 只对 promotion components 和其 boundary/guard block 调用**原始完整 Stage1**。
- fine Stage1 使用现有 40 ms、精确 NAV wipe、当前 delay/Doppler/residual grid 和 `-25 dB` screen，不改变最终判据。
- fine 结果仅在 fine-scanned windows 内参与当前 `chooseStage2Candidates`；不能把 coarse score 直接映射成 `has_two_strong_residuals`。
- 多个 coarse component 合并后应去重，fine read/candidate 只执行一次；所有 window 写 `fine_scanned=true/false`。

#### Phase 4：adaptive closure

- 由 fine Stage1 的实际 Pipeline V3 candidate rule 产生最多 24 个 base seed。
- 每个 base seed 补齐 `window_id ±2`；缺少任何邻居即不得进入 Stage3/Stage4 可靠判断。
- 预算允许时，对高风险或接近 component 边界的 seed 加 `±5` 或连续 11-window burst；扩展仍只由已经可见的 fine candidate 触发。
- 如果一个新增 guard 又出现 fine candidate，则递归扩展到预定上限；否则标记 closure complete。
- 不能为了达到预算上限而随机填充窗口；也不能在预算不足时把未覆盖中心标为 rejected/LOS。

#### Phase 5：原始 Stage2–Stage4

- 只对 fine Stage1 candidate 与完整闭包执行 L1–L4、Stage3 persistence、Stage4 joint。
- BIC/RSS/path power/coherence、Stage3 persistence、Stage4 `joint_valid` 判据全部保持原样。
- sampled/coarse run 的 confirmed criterion 与 full-scan 完全一致；coarse 不得降低 false positive 门槛。

### 6.2 Fine budget 比较，不再固定 1200

fine budget 是实际调用完整 Stage1 的**唯一 window 数上限**，包含初始 promotion、component 内连续窗口、boundary 和 adaptive guard；Stage0/coarse 全量不计入 fine budget。设计阶段固定比较三档：

| Profile | Fine Stage1 budget | 适用问题 | 超预算处理 |
|---|---:|---|---|
| F1200 | 1200 | 与 v1/v1.1 对照；短/中等场景成本上限 | 不得截断闭包；超出则 `inconclusive` 或升级 full-scan |
| F2400 | 2400 | 检验连续 risk regions 是否需要更多局部覆盖 | 同上；只增加由 coarse/fine 触发的区域 |
| F4800 | 4800 | 检验较复杂场景和多 event components | 仍必须低于 G11 全量 fine；超出不能伪称 sampled |

不把这三档当作“必然通过”的预算。对每个 gold task/config 报告：

```text
N0
N_coarse (=N0)
N_fine_initial
N_fine_guard
N_fine_total
N_stage2_candidate
N_stage2_model_rows
N_inconclusive_centers
event_center_recall
±2_closure_recall
stage3_closure_recall
coarse_time
fine_time
stage2_time
total_time
normalized_cost_vs_full_scan
```

目标是让 `N_fine_total < 15,210` 且总成本显著低于 G11 full-scan；更严格的 pilot 目标建议为在 100% recall 后再要求 normalized cost 至少减少 50%，但这只是待验证的 release target，不是当前实验结果。不能用未经测量的 `C_coarse/C_fine` 比例替代 wall-clock/CPU/I/O 记录。

### 6.3 总成本模型

用可测量的 cost unit，而不是窗口数直接当时间：

```text
T_v1_2 = N0 * C_coarse
       + N_fine_total * C_fine_stage1
       + N_stage2_candidate * C_stage2_candidate
       + T_stage3_stage4
       + T_I/O_and_manifest

T_full = N0 * C_fine_stage1
       + N_stage2_candidate_full * C_stage2_candidate
       + T_stage3_stage4_full
```

理论加速来自：

- coarse 短积分/粗 grid；
- contiguous raw chunk read，减少 `fopen/fseek/fread` 和 20 ms overlap 重复读取；
- coarse 不做 fine local refine、full residual grid、amplitude/BIC/SAGE；
- fine 只覆盖 risk components 和 guard；
- Stage2 只处理真实 fine candidate，而不是 coarse 全量。

潜在新瓶颈是：全量 coarse 仍需 raw I/O；短积分窗口数可能是 `4×N0`；component 过多会使 fine budget接近全量；MAT/CSV 写入、外部 raw storage 和 MATLAB/Python 进程交互可能吞掉理论收益；coarse code FFT cache 不当会产生错误或收益消失。这些必须由 prototype 测量。

## 7. Feature risk 的详细使用规则

### 7.1 Prompt/Early/Late 与 tracking 特征

现有代表性 tracking MAT 明确能看到 `Prompt_I/Prompt_Q`，但没有可依赖的 Early/Late 字段名；当前 Pipeline reader 未用它们。因此分三层：

1. **立即可用：** Stage0 CSV 的 CN0、tracking Doppler、code frequency、lock、relative Doppler bound、speed、TOW/sample continuity。
2. **极小 schema probe 后可用：** Prompt I/Q、Doppler rate、code rate、code error；只提取字段 shape、sample index 对齐和少量 derived statistics，不启动 SAGE。
3. **不可假设：** Early/Late correlator 值；除非每个 scene/channel 的 MAT schema probe 都确认并写 provenance，否则不进入 score。

建议 derived statistics 以 window 为中心计算：

- absolute、first difference、second difference、local MAD；
- 5-window/11-window rolling values，但窗口边界/断点明确记录；
- 不使用未来 Stage1/Stage2 结果；
- 对 CN0/Doppler/code error 的异常只作 risk evidence，不作 multipath label。

### 7.2 Geometry 使用门槛

只有 window-level TOW/UTC join 同时满足既定 coverage、nearest-time p95、NMEA identity gate 时，才可以把 elevation/azimuth/SNR 作为 feature。否则：

- geometry feature 为 null；
- `geometry_join_status=warning_fallback`；
- score 不使用 PRN summary mean；
- 不因 geometry 缺失删除 window；
- 不把缺失 geometry 当作 LOW/MID/HIGH。

这一规则与 v1.1 的 TOW diagnostic 一致，但 v1.1 diagnostic 尚未成为生产 Pipeline/DB 组件。

## 8. 状态、manifest 和 provenance 设计

### 8.1 Run-level 字段

建议在新版本 namespace 中写入 `sampling_run_context.json`：

| 字段 | 语义 |
|---|---|
| `sampling_version` | `batch-sampled-v1.2` |
| `screening_architecture` | `hybrid_feature_plus_coarse_raw` / 明确 profile |
| `coarse_algorithm_version` | coarse 代码/参数版本 |
| `coarse_parameter_hash` | coarse grid、积分、threshold、I/O 策略 hash |
| `fine_pipeline_version` | `Pipeline V3` |
| `fine_pipeline_sha256` | 实际 fine entrypoint hash |
| `source_stage0_sha256` | 完整 Stage0 catalog hash |
| `source_tracking/telemetry/geometry_sha256` | 输入 provenance |
| `coarse_all_stage0_windows` | 必须为 true |
| `fine_budget` | 1200/2400/4800 |
| `guard_policy` | ±2、±5、component boundary rule |
| `gold_labels_used_for_selection` | 生产必须 false；replay output 单独记录 |
| `output_namespace` | 建议 `sage_results/nav_sage_v1_2_coarse_fine/<PRN>` |
| `sampling_status` | `planned`、`coarse_complete`、`fine_partial`、`fine_complete`、`inconclusive`、`qa_pass`、`qa_fail` |

建议的 `sage_results/nav_sage_v1_2_coarse_fine/` 只是设计 namespace，当前不存在且本任务不创建它；不得复用 `nav_sage_v2`。

### 8.2 Window-level 字段

建议 `coarse_window_manifest.csv` 至少包含：

```text
scene_id, prn, tracking_channel, window_id, symbol_index,
sample_start_zero_based, recording_time_s, tow_s,
stage0_source_row, stage0_catalog_sha256,
feature_score, feature_status, feature_missing,
coarse_scanned, coarse_score, coarse_score_components,
coarse_main_delay, coarse_main_doppler, coarse_residual_score,
coarse_subblock_count, coarse_raw_read_id, coarse_quality,
promotion_status, promotion_reason, promotion_component_id,
fine_scanned, fine_scan_status,
guard_scanned, guard_radius, guard_reason,
stage2_eligible, stage3_closure_status, coverage_status,
not_promoted, inconclusive, sampling_version,
coarse_parameter_hash, fine_parameter_hash
```

状态语义必须固定：

- `coarse_scanned=true`：全量 Stage0 window 都应为 true；
- `fine_scanned=true`：实际调用完整 fine Stage1；
- `guard_scanned=true`：因 seed/closure 被加入 fine；
- `not_promoted=true`：coarse 后没有进入 fine，**不表示 LOS**；
- `coarse_not_promoted`：当前 coarse 阶段结果；
- `inconclusive=true`：预算不足、geometry/continuity 缺口或 closure 不完整，不能作 negative；
- `stage2_eligible=true`：fine Stage1 candidate/closure 满足进入 Stage2 的数据条件；
- `sampling_status=qa_pass`：仅在 gold replay/实际 pilot 的全部 QA gate 通过后设置。

Replay-only 字段应放在独立 `coverage_replay_v1_2.csv`，例如 `gold_event_center_overlap`、`gold_closure_overlap`、`replay_label`；不能回写生产 manifest，避免将 gold leakage 伪装成 provenance。

## 9. 严格离线验证方案

### 9.1 验证前冻结

在读取任何 Stage4 event location 前冻结：

- feature list、方向、score 权重和阈值；
- coarse 参数 profile；
- block merge/hysteresis/guard 规则；
- fine budgets F1200/F2400/F4800；
- tie-break hash 和版本；
- 输出目录和 manifest schema。

冻结后才能读取 full-scan Stage1/Stage2/Stage4 作为 posterior gold。

### 9.2 必须报告的 recall

对 reference 七 PRN、Wave-A G16/G25/G12、Wave-2A G11 全部重复：

1. coarse coverage：N0 是否全部 `coarse_scanned`；
2. initial promotion event-center recall；
3. final fine event-center recall；
4. final fine `±2` closure recall；
5. Stage3 reliable center ±2 closure recall；
6. F1200/F2400/F4800 的 Nfine、component 数、guard 数和 `inconclusive` 数；
7. coarse/fine/Stage2 分项与总成本；
8. 漏检原因：`coarse_below_threshold`、`component_boundary_gap`、`fine_budget_exhausted`、`missing_continuity`、`geometry_unavailable` 等；
9. selection 是否读了 gold hidden row，必须为 false。

硬门槛：reference + Wave-A 所有 known confirmed event center 及其 ±2 closure 对选定 production profile 达到 100%。任何一个漏检均为 FAIL，不得用平均 recall、增加随机 seed 或改写 event window 弥补。

### 9.3 Negative/control 约束

G25、G28、Wave-2A G11 和 Wave-A G25 的 full-scan 结果没有 confirmed event；其中 G28 有 Stage3/Stage4 LOS-only rejection，不能被 coarse promotion 强行解释为 confirmed。

离线阶段至少记录：

- 每个 control 的 coarse score 分布、promotion fraction、component 数；
- 与 G16/G12 positive 的相同统计；
- control 是否因 threshold 规则系统性获得异常高 promotion；
- G28 是否保持“可有 candidate/persistence，但 Stage4 rejection”的语义。

coarse promotion 本身不是 false positive label，不能因为某个 control 有 promotion 就判算法错误；真正的 false-confirmed gate 只能在独立 sampled pipeline 实际跑到 Stage4 后判断。实际 pilot 的硬约束是：G25/Wave-A G25/Wave-2A G11 不得产生未经 Stage4 criterion 支持的 confirmed event，G28 不得把现有 rejected pattern 解释成 confirmed multipath。

### 9.4 v1.2 不能通过时的处理

- 纯 feature A 漏检：不加随机 seed；进入 raw coarse prototype。
- raw coarse 全量仍漏检：冻结失败报告，检查短积分/多子块/粗 Doppler coverage；不能偷看 gold 调阈值。
- 1200 超预算：比较 F2400/F4800；仍超则 `inconclusive` 或按该 task full-scan 人工批准，不能截断闭包。
- F4800 仍不能做到 recall 100% 且总成本优势不足：当前架构淘汰，不恢复 Wave-2A。

## 10. 哪些现在可以纯 Python 离线验证，哪些需要 prototype

### 10.1 现在可做、但本任务不执行的纯 Python 工作

只读取以下文件即可：

- gold tasks 的 `stage0_valid_40ms_windows.csv`；
- v1.1 已有 TOW-aligned geometry diagnostic 结果（仅在 verified 时使用）；
- full-scan Stage4 用于 replay 后验测量；
- 不打开 raw，不调用 MATLAB。

可验证：

1. A 的 Stage0-only feature extraction、rolling feature、gap/continuity flags；
2. 固定 score、hysteresis、continuous component merge；
3. F1200/F2400/F4800 的 promotion/fine window budget 模拟；
4. Stage3 ±2 closure 的 manifest 可供性；
5. gold replay 的 center/closure recall（gold 只在选择冻结后读取）；
6. `G25/G28/G11` control promotion rate 和 provenance 安全性；
7. manifest/status/hash schema 单元测试。

但纯 Stage0 CSV 不能真实生成 Prompt I/Q、code error 或 raw residual coarse score；这些字段只能标 missing，不能伪造。

### 10.2 必须新增极小 prototype 才能验证的部分

- B 的全窗口 raw coarse correlation；
- C 的 coarse raw + contiguous chunk I/O + multi-subblock score；
- Prompt I/Q、Doppler rate、code error 的 MAT schema/value extraction；
- 粗 grid 对短时/弱多径的真实 recall；
- coarse 与 fine 的实际 CPU、I/O、内存和 wall-clock 比例。

现有 full-scan Stage1 CSV 不能替代这些 coarse 输出。把 hidden full Stage1 residual power 直接当 coarse score 会造成 oracle leakage，只能作为另一个明确标注的后验分析，不能证明生产 coarse 算法。

## 11. 最小 prototype 设计（本任务不执行）

如果 Stage0-only A 的纯离线 replay 不能达到门槛，最小 raw prototype 只允许三个 task：

1. **positive short/medium：** `F1023_V70_D0120_P7/G16/ch1`，N0=2229，已知 4 个 confirmed event；
2. **negative/control：** `F1023_v50_D0127_P1/G25/ch0`，N0=2339，已知 0 confirmed event；
3. **long stress/control：** `F1023_V120_D0121_P2/G11/ch0`，N0=15210，full-scan Stage1约8.1 h、Stage2约11.4 h、总约19.6 h，已知 0 confirmed event。

reference G25/G28 仍用于纯离线 gold/control replay，不增加 prototype task 数量。

prototype 只应：

- 读 Stage0 窗口和 raw；
- 计算 10/20 ms multi-subblock coarse score；
- 输出 coarse manifest、score、每个 raw chunk 读取次数/bytes、CPU/wall-clock、内存峰值；
- 不调用 `run_nav_sage_pipeline.m`；
- 不跑 Stage2/Stage3/Stage4；
- 不写任何 `sage_results`；
- 输出写 `dataset_generation_logs/sampling_validation/batch_sampled_v1_2_prototype/`，该路径在本任务中不创建；
- 用冻结 selection 后的 full-scan Stage4 只做事后 center/closure recall。

prototype 的最小比较矩阵：

| 版本 | 10/20 ms | coarse delay | coarse Doppler | raw read |
|---|---|---|---|---|
| A0 | 不读 raw | N/A | N/A | 0 |
| B1 | 20 ms×2 | 1 sample | 100/200 Hz coarse | per contiguous chunk |
| B2 | 10 ms×4 | 1–2 samples | tracking-centered few bins | per contiguous chunk |
| C1 | B2 + block merge/hysteresis | 同 B2 | 同 B2 | reuse overlap |

选择应依据 gold recall、control promotion、实际成本和 failure mode；不得直接选择“最接近已知事件”的配置。

## 12. 推荐、备选与淘汰方案

### 推荐主方案：C / Hybrid feature + full-window coarse raw + local fine

理由：

- 让所有 Stage0 window 至少经过同一类低成本发现，避免 v1/v1.1 的 sparse blind spot；
- 连续 block 和多子块 max 可覆盖短时事件；
- fine candidate 仍由现有 Stage1 规则产生，科学判据不变；
- ±2 closure 是状态门禁，不是事后补洞；
- 有明确的 F1200/F2400/F4800 预算和 `inconclusive` 分支；
- 可通过 contiguous raw read、短 FFT 和 coarse grid 测出理论加速来源。

### 备选方案：A feature-only + deterministic block

先纯 Python 实现，成本最低、便于验证 schema/状态/coverage；仅当全 gold recall 100%、controls 无异常 promotion，且后续 MAT feature/schema 验证通过，才可作为 production coarse。否则只作 prefilter，不能跳过 B/C。

### 淘汰方案

- 继续 v1 的离散稀疏抽样；
- 继续 v1.1 仅扩大 block、budget 或 ±2/±5 而不增加全窗口 discovery；
- 用 full-scan hidden Stage1 行直接选 seed；
- 用 PRN geometry summary 均值填充 window elevation；
- 用 tracking CN0/lock 单一阈值直接标 confirmed/LOS；
- 把 coarse score 写进 `stage1_nav_fast_scan.csv` 冒充 fine Stage1；
- 把 F4800 或任何单 seed/单 task 局部通过结果写成 production guarantee。

## 13. 版本化 namespace 与工程边界

当前 Pipeline V3 将输出固定到：

```text
scenes/<scene>/sage_results/nav_sage_v2/<PRN>
```

它没有 `SamplingMode`/`SamplingPlan` 参数，会从 Stage0 扫描全部 windows。因此 v1.2 不能仅靠现有 batch executor 把 sampled result 安全塞进 `nav_sage_v2`。未来实现必须选一项：

- 独立 `run_nav_sage_pipeline_v1_2_coarse_fine.m`/等价入口，并显式 output root；或
- 对 Pipeline V3 做经过 review 的 output/selection abstraction，同时保持 full-scan default 和判据不变。

推荐 namespace：

```text
scenes/<scene>/sage_results/nav_sage_v1_2_coarse_fine/<PRN>
```

配套 sampling artifacts：

```text
dataset_generation_logs/sampling_validation/batch_sampled_v1_2/
├── sampling_validation_manifest_v1_2.json
├── <task>/coarse_window_manifest.csv
├── <task>/coarse_features.csv
├── <task>/promotion_manifest.csv
├── <task>/coverage_replay_v1_2.csv
└── <task>/cost_measurement.json
```

以上均是建议路径，本任务未创建。`nav_sage_v2`、reference/G06 legacy、v1/v1.1 validation namespace 均不可修改。

## 14. 下一步最小实现任务

下一步应优先做**纯 Python、只读、无 MATLAB 的 A0 离线实现**，顺序固定为：

1. 读取 11 个 gold task 的 Stage0 CSV，检查所有 window_id、字段缺失、sample/TOW gap 和 Stage0 hash；
2. 实现固定版本的 Stage0 feature extraction、rolling anomaly、hysteresis 和连续 component merge；
3. 生成独立 v1.2 coarse/promotion manifest，不写 `sage_results`；
4. 冻结 promoter 后再读取 full-scan Stage1/Stage3/Stage4，计算 initial/final center recall、±2 closure recall、Stage3 closure、control promotion rate；
5. 对 F1200/F2400/F4800 做纯 manifest budget replay，超预算标 inconclusive；
6. 如果 A0 在任何 known positive center/closure 漏检，停止调参，不恢复 Wave-2A，进入上述三个 task 的 B1/B2/C1 raw prototype 设计评审；
7. 只有 prototype 实测 coarse recall、I/O、CPU、内存和成本后，才决定是否实现独立 `nav_sage_v1_2_coarse_fine` pipeline；
8. prototype/pipeline 通过 gold/control QA 后，才考虑短场景 sampled pilot，再考虑 G11 长场景 sampled pilot。

本设计不授权执行上述 prototype，也不授权恢复任何 Wave-2A full-scan 或处理 20.46 MHz。

## 15. Current Status

- **已验证事实：** 现有 Stage1 为每个 Stage0 window 读取 40 ms raw、做精确 NAV wipe、主 delay/Doppler grid、局部 refine、residual full grid 和 peak selection；Stage2 对候选重复读取并做 L1–L4/SAGE/BIC。Wave-2A G11 的 Stage1约8.1 h、Stage2约11.4 h、总约19.6 h。
- **已验证失败：** v1/v1.1 的 sparse/continuous-block sampling 在 Wave-A positive 上漏 center/closure；budget 4800 也没有 all-seed 稳定通过。
- **当前设计状态：** v1.2 推荐全量低成本 discovery + 连续局部 fine，不再靠随机稀疏 sampling；A/B/C/D 方案、状态字段、cost model、offline gate 和最小 prototype 已设计。
- **尚未实现：** Stage0 feature planner v1.2、raw coarse evaluator、coarse-to-fine pipeline、新 namespace、真实 sampled pilot、event database ingest。
- **下一步：** 先实现并离线验证纯 Python A0；只有 A0 不满足 100% gold center/±2 closure，才进入 G16/G25/G11 三 task 的极小 raw coarse prototype。期间不运行 MATLAB/SAGE，不恢复 Wave-2A 剩余 full-scan，不处理 20.46 MHz。

