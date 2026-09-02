# 主径公共增益 / 衰落深度模型 v1 实施计划

> **执行提示：** 后续实施本计划时，使用 `superpowers:test-driven-development`，并按任务逐项执行和复核。本文件本身仅为 `Planned / Not started`，不代表已运行建模。

**目标：** 基于现有 GNSS-SDR tracking 的 `CN0_SNV_dB_Hz`、`carrier_lock_test`、采样计数和已验证 scene/geometry provenance，建立一个按环境（并在逐时刻 geometry 关联通过时按 LOW/MID/HIGH 仰角）条件化的**相对公共增益与可观测衰落深度模型**。该层使未来四路径暗室参数中的主径幅度可以随时间变化，并为三条 NLOS 相对幅度提供共同乘性尺度。

**架构：** 新模型独立于已完成的 confirmed-NLOS 路径参数模型和接收机失锁模型。它把 tracking C/N0 视为 receiver-observed common-strength proxy，先做 run 内归一化，再分解为正常状态公共增益过程与衰落事件；进入 `LOCK_BAD` 后的真实深度不可观测，按右删失处理。输出是版本化参数、覆盖/支持状态和未来生成器接口，不输出绝对 RF 功率，也不把 path 0 声称为物理 LOS 或最强传播路径。

**技术栈：** Python 3.12；NumPy 2.5.1；SciPy 1.18.0；OpenBLAS；固定解释器 `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`；标准库 CSV/JSON/gzip/hash/dataclass/path；pytest。禁止联网、安装或复制依赖。

**上游事实：**

- 环境锁定诊断模型：`dataset_generation_logs/channel_modeling/environment_lock_model_v1_20260826_r2/lock_model_manifest.json`，SHA-256=`21c04938cba559b3e042806b093eba82e4e86a44977e95831c715aa03ffc97a5`。
- confirmed-NLOS 路径分布模型：`dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/model_manifest.json`，SHA-256=`4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c`。
- 63 个 environment-eligible tracking runs；G06 legacy 因缺少 `run_context.json` 保留审计但排除。
- tracking 已有 `PRN`、`PRN_start_sample_count`、`CN0_SNV_dB_Hz`、`carrier_lock_test`；现有锁模型读取了 894,470 条记录，其中 808,133 条有效、86,337 条 inconclusive。
- scene 时间原点：`dimensions/time_alignment.csv`，SHA-256=`442a7845e52841696eae7be22076e20bb76daf283fa033d6bb675deb8e3b154e`。
- 环境标签：`dimensions/scene_context.csv`，SHA-256=`8a50fcc3196a2256735c45c77119d8a8b6447532a503aeb5a075e103ed1877e3`。
- 建模纳入门禁：`exports/modeling_run_eligibility.csv`，SHA-256=`163bd5d9ce8cf3d0681e29c46b3d3fac3a9cce92877c3288207c789b6123638e`。
- run/provenance 表：`facts/sage_runs.csv`，SHA-256=`f4303749beeb73e922758ef6a1cfb0eef7b4e69d49b2f49ad8b6bf29cb3a7ae5`。
- 生产 Pipeline 保护 SHA-256：`scripts/sage_pipeline/run_nav_sage_pipeline.m`=`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。

---

## 1. 科学边界与术语冻结

### 1.1 能从现有数据学习的量

1. `C/N0` 相对 run 内参考值的变化，即 `common_gain_db`。
2. 在线性幅度域中的相对公共增益：

   `common_gain_linear = 10^(common_gain_db / 20)`。

3. 在 tracking 仍可用时，相对于局部稳健上包络的可观测衰落深度 `fade_depth_db`。
4. 衰落事件进入率、可观测持续时间，以及右删失标记。
5. 正常状态公共增益的边际分布和相关时间尺度。
6. 当逐 tracking 时刻的时间/geometry QA 通过时，按 `environment × elevation_band` 条件化；否则只使用环境父模型，并把对应单元标为 `PRIOR_ONLY` 或 `GEOMETRY_NOT_ESTIMABLE`。

### 1.2 不能从现有数据直接学习的量

- 绝对 RF 功率、接收机前端绝对增益、天线方向图或 dBm 标定值。
- 单独物理 LOS 分量的真实幅度。tracking C/N0 是接收机观测代理，不是 path-0 的直接分离测量。
- `LOCK_BAD` 区间内真实衰落究竟有多深。该深度只能作为下界/删失观测。
- 相位、失锁后的相位演化和恢复波形；这些属于后续“失锁状态到幅度、相位和恢复过程映射”。
- 三个 NLOS 槽位的激活规则、NLOS 路径出现率或 NLOS 与公共增益的统计耦合。

### 1.3 path 0 与公共增益的含义

- `NLOSPathID=0` 是暗室表中的参考/主径槽，不自动等于物理 LOS，也不保证是瞬时最强路径。
- 已冻结的主径默认 `[RelativeDelay=0 ns, RelativeDoppler=0 Hz, RelativeAmplitude=1]` 只是无衰落归一化参考。
- 本层后续输出 `G_common(t)` 后：

  - path 0：`RelativeAmplitude_0(t) = G_common(t)`；
  - 已激活的 NLOS path i：`RelativeAmplitude_i(t) = G_common(t) × A_rel_i`。

- 这是一项明确的共同乘性尺度假设；不是从 Stage4 直接估出的绝对幅度关系。

---

## 2. 方案比较与推荐

| 方案 | 核心做法 | 优点 | 不可接受风险 | 决策 |
|---|---|---|---|---|
| A. 直接拟合各环境绝对 C/N0 | 对 dB-Hz 原值拟合 | 简单 | 混入卫星、仰角、天线、前端增益与记录间偏置，不能解释为主径幅度 | 淘汰 |
| B. `LOCK_BAD → amplitude=0` | 用锁状态代替增益 | 可直接产生“失锁” | 将接收机诊断状态伪装成物理衰减；无法表示锁内衰落 | 淘汰 |
| C. run 内归一化 C/N0 + 局部衰落事件 + 删失处理 | 分离正常公共增益、可观测衰落和不可观测锁后深度 | 与现有数据语义一致；可审计；可与失锁层组合 | 只能得到相对增益，非绝对功率 | **推荐 v1** |

v1 使用方案 C。它不替代现有 lock model；两层以后由独立组合器按明确状态机连接。

---

## 3. 冻结的数据处理定义

### 3.1 物理 tracking 输入去重

- 只解析 `include_in_environment_modeling=1` 的 63 个 run。
- 每个 tracking MAT 在建模前重新计算 SHA-256。
- 以 `(tracking_sha256, PRN, tracking_channel)` 作为物理观测键。若多个 run 指向同一物理 tracking 输入：保留全部 run provenance，但只计一次拟合权重，并输出 `duplicate_physical_input=1`。
- 不允许按文件名猜 PRN/channel，不允许把 G06 legacy 补入。
- tracking 四字段长度必须完全一致；新模型不得沿用“按最短列静默截断”的容错方式。长度不一致时 fail closed。

### 3.2 时间与仰角关联

1. `tracking_time_s = PRN_start_sample_count / 10230000`。
2. `tracking_utc = recording_time_origin_utc + tracking_time_s`。
3. 在同 scene、同 PRN 的 GSV timeseries 中找最近观测；最大时间差固定 5 s。
4. 不插值、不使用 scene/PRN 仰角均值、不使用文件名或 summary 伪造逐时刻 elevation。
5. 仰角 bin 固定：`LOW=[0,30)`、`MID=[30,60)`、`HIGH=[60,90]`。
6. 若无法通过逐时刻关联，记录 `geometry_join_valid=0` 和原因；该记录只进入环境父模型，不进入仰角 cell likelihood。
7. 关联前必须用 Stage0/event-context 中已有 tracking C/N0 做独立时间链一致性抽查；任何系统性偏移超过 `max(2×native_dt, 25 ms)` 时停止，不拟合仰角条件模型。

### 3.3 canonical 20 ms 分析网格

- 将 tracking 观测按真实 `tracking_time_s` 映射到固定 20 ms bin；每个 bin 取有效 C/N0 中位数，不插值空 bin。
- 20 ms 是分析网格，不改变原 tracking 数据，也不声称原观测均为 20 ms。
- continuity gap、无效 C/N0、PRN 不符或混合 lock transition 的 bin 标为 `INCONCLUSIVE`。
- 后续 1 ms 仿真由连续时间相关模型生成，不能把同一个 20 ms 数值机械复制并称为实测 1 ms 分辨率。

### 3.4 run 内参考和局部基线

对每个物理 run：

- `C_ref_run = median(CN0)`，样本仅限有效 `LOCK_GOOD` 记录。
- `common_gain_db(t) = CN0(t) - C_ref_run`。
- `common_gain_linear(t) = 10^(common_gain_db(t)/20)`。
- 局部无衰落参考 `C_upper(t)`：在同一 continuity segment 内，使用 10 s 居中时间窗的 LOCK_GOOD C/N0 第 90 百分位。
- segment 长度在 `[2 s, 10 s)` 时用该 segment 的第 90 百分位；不足 2 s 时标记 `BASELINE_INCONCLUSIVE`，不做衰落事件拟合。
- `fade_depth_db(t) = max(0, C_upper(t) - CN0(t))`。

`C_ref_run` 用于公共增益归一化；`C_upper(t)` 只用于局部衰落深度。两者不得混写。

### 3.5 衰落事件状态机

- 进入：`fade_depth_db >= 3 dB` 持续至少 20 ms。
- 退出：`fade_depth_db <= 1 dB` 连续至少 100 ms。
- primary 阈值依据是固定 3 dB 半功率定义和 hysteresis；不得在查看环境结果后调参。
- 可额外输出 2 dB/6 dB 敏感性计数，但只作诊断，不参与 v1 参数选择。
- continuity gap、记录终止或转入 `LOCK_BAD` 时：事件停止观察并标记右删失；不得将最后一个可见深度当作真实最大深度。
- 一个事件若跨越仰角 bin 边界，保留环境级事件，但设置 `elevation_cell_eligible=0`、`missing_reason=elevation_transition_within_event`。
- `LOCK_BAD` 不是深度数值；进入该状态时记录 `depth_censor_reason=lock_bad_transition`。

---

## 4. 冻结的统计模型结构

### 4.1 正常状态公共增益

- 训练样本：`LOCK_GOOD`、非 fade、非 inconclusive 的 20 ms bin。
- 候选边际族：Student-t、normal、Laplace；统一在 dB 域拟合。
- 全局 family selection 使用 leave-one-scene-out held-out log likelihood；禁止随机按行拆分。
- family tie 顺序固定为上述顺序，绝对 tie tolerance=`1e-9`。
- 参数层级：global → environment → environment×elevation cell。
- 空 cell 继承 environment parent，设置 `PRIOR_ONLY`；无可靠 geometry 的记录只进入 environment/global parent。
- 拟合权重按 scene 平衡：每个 scene 总权重相同，scene 内各物理 run 等权，避免长记录或高采样率独占边际形状。

### 4.2 正常状态时间相关性

- 将已拟合边际通过 CDF 和标准正态逆变换映射到 latent Gaussian 序列。
- 使用 20、40、100、200、500、1000 ms lag 的连续有效 pair，拟合：

  `rho(Δt) = exp(-Δt / tau)`。

- `tau` 约束在 `[0.02 s, 60 s]`；按完整 run/scene 分组估计，禁止跨 gap 或 run 拼接。
- 稀疏 cell 继承 environment `tau`；environment 不可估时继承 global `tau` 并标记来源。
- 未来 1 ms 生成采用 `rho_1ms=exp(-0.001/tau)` 的 latent AR(1)，再经边际 PPF 映射；这是连续时间相关模型，不是把 20 ms 样本伪造为 1 ms 实测值。

### 4.3 衰落进入率

- 暴露量：可用、未处于 fade/LOCK_BAD/inconclusive 的真实时间。
- 事件：按 3.5 的状态机产生。
- 使用 Gamma-Poisson 层级后验估计 global、environment、cell 的 entry rate；空 cell 继承 environment parent。
- 直接 cell 支持按真实 exposure、scene/run 数和事件数单独报告，不使用 bin 行数冒充独立样本量。

### 4.4 衰落深度和持续时间

- 深度：每个事件的 `max_observed_fade_depth_db`，正值候选族 lognormal、Gamma、Weibull，location 固定 0。
- 对转入 LOCK_BAD/gap/记录结尾的事件，深度按右删失似然 `P(D >= d_observed)` 进入拟合。
- 持续时间：候选族 lognormal、Gamma、Weibull；右删失事件使用 survival likelihood。
- 全局统一选择一个深度 family、一个 duration family，均使用 leave-one-scene-out 评分和确定性 tie-break。
- v1 不拟合 attack/recovery waveform，也不拟合 depth-duration copula；两者保持独立并明确标为 downstream assumption。

### 4.5 支持状态

每个 cell 分别输出 gain 和 fade 两套支持状态：

- `DATA_SUPPORTED_WITH_GROUPED_VALIDATION`：至少 2 个 scene、3 个物理 run、60 s 有效 exposure；fade 还要求至少 10 个事件。
- `SPARSE_PARTIAL_POOLING`：有直接样本/exposure，但未达到上述门槛。
- `PRIOR_DOMINANT`：仅 1 个 scene 或 fade 事件数 1–2。
- `PRIOR_ONLY`：无 direct geometry-ready 样本或无事件。
- `NOT_ESTIMABLE_GEOMETRY`：时间/geometry preflight 未通过，禁止生成伪 cell fit。

这些标签说明统计支持，不说明物理上没有衰落。

---

## 5. 输出 namespace 与文件合同

固定 new-only namespace：

`dataset_generation_logs/channel_modeling/main_path_common_gain_fade_v1_20260826_r1/`

若该目录存在，必须停止；禁止 overwrite、resume、删除或自动改名。

计划输出：

| 文件 | 作用 |
|---|---|
| `source_preflight.csv` | 63 eligible/1 excluded、tracking hash、物理输入去重、字段长度与 cadence |
| `geometry_join_coverage.csv` | run/scene/PRN 的逐时刻 geometry 覆盖和失败原因 |
| `common_gain_analysis_grid.csv.gz` | 20 ms 只读派生网格、C/N0、gain、baseline、lock/fade/geometry 状态 |
| `common_gain_run_summary.csv` | 每 run 参考 C/N0、有效 exposure、缺失/删失、支持状态 |
| `fade_event_catalog.csv` | 衰落事件、深度、duration、删失和条件上下文 |
| `cell_coverage.csv` | 4 环境 × 3 仰角的 gain/fade direct support |
| `family_selection.csv` | scene-grouped family 评分与选择 |
| `common_gain_marginal_parameters.csv` | global/environment/cell gain dB 边际参数 |
| `common_gain_temporal_parameters.csv` | latent correlation time 与继承来源 |
| `fade_entry_rate_parameters.csv` | global/environment/cell 进入率后验 |
| `fade_depth_duration_parameters.csv` | 深度/持续时间 family、参数、删失统计 |
| `main_path_common_gain_fade_model.json` | 供未来生成器读取的冻结模型接口 |
| `qa_draw_summary.csv` | 固定 seed 的诊断生成分位数/ACF/事件率，不是最终仿真表 |
| `model_manifest.json` | 输入、源码、config、环境、package、输出 hash 和语义 |
| `run_receipt.json` | start/end UTC、exit code、禁止项、文件列表 |
| `independent_qa_report.md` / `.json` | 独立 QA 结论 |

父 provenance 必须同时记录 lock-model 和 path-model manifest hash，但不得修改二者。

---

## 6. 实施任务（TDD 顺序）

### Task 1：冻结 config、schema 与 namespace

**文件：**

- Create: `configs/channel_modeling/main_path_common_gain_fade_v1.json`
- Create: `scripts/analysis/channel_modeling/main_path_gain_core.py`
- Create: `scripts/analysis/channel_modeling/tests/test_main_path_gain_core.py`

**接口：**

- `load_gain_model_config(path: Path) -> MainGainConfig`
- `validate_parent_provenance(project_root: Path, config: MainGainConfig) -> ParentProvenance`
- `ensure_new_only_namespace(path: Path) -> None`

- [ ] 先写失败测试：错误 parent hash、错误 sample rate、允许 raw/MATLAB/SAGE、已有 output namespace、错误 elevation bin、变化的 3/1 dB threshold 均拒绝。
- [ ] config 冻结 model ID、全部阈值、families、seeds、输出、禁止项、parent manifest/hash、Pipeline hash。
- [ ] 计算 config 和 schema SHA-256；任何 posterior QA 之前固定。
- [ ] 运行 focused tests，期望 PASS。

### Task 2：严格读取 tracking、物理输入去重和锁语义一致性

**文件：**

- Modify: `scripts/analysis/channel_modeling/main_path_gain_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_main_path_gain_core.py`

**接口：**

- `resolve_gain_model_runs(project_root: Path, config: MainGainConfig) -> list[GainRunInput]`
- `read_tracking_observation(run: GainRunInput) -> TrackingObservation`
- `deduplicate_physical_inputs(runs: Sequence[GainRunInput]) -> PhysicalInputAudit`
- `classify_lock_samples(...) -> LockStateSeries`

- [ ] synthetic HDF5 fixture 测试四字段读取、shape、PRN/channel、sample counter monotonic、NaN/invalid C/N0、长度不等 fail closed。
- [ ] parity test：固定 fixture 上的 lock sample 状态、20 ms bad debounce、100 ms reacquisition 与 `build_environment_lock_model.py` 规则完全一致。
- [ ] duplicate hash fixture 证明只计一次拟合权重但保留双 provenance。
- [ ] 真实 preflight 运行时必须重核 63 eligible/1 excluded；数量变化即停止并要求新版本计划。

### Task 3：实现 tracking UTC 与逐时刻 geometry join

**文件：**

- Modify: `scripts/analysis/channel_modeling/main_path_gain_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_main_path_gain_core.py`

**接口：**

- `load_verified_time_origins(...) -> Mapping[str, TimeOrigin]`
- `tracking_sample_to_utc(sample_count: float, fs_hz: int, origin: datetime) -> datetime`
- `join_tracking_geometry(...) -> GeometryJoinResult`
- `elevation_band_for(deg: float) -> str`

- [ ] 测试同 scene/PRN 最近 GSV、5 s 边界、PRN missing、超时、LOW/MID/HIGH 边界和跨 band event。
- [ ] 测试禁止 interpolation、summary mean 和 wrong-PRN fallback。
- [ ] 增加 event-context/Stage0 时间链抽查：系统性偏移超门槛时 `GEOMETRY_PREFLIGHT_FAIL`，不得降级后仍宣称 elevation fit。
- [ ] 输出 geometry coverage，但此 Task 不拟合分布。

### Task 4：构建 20 ms 分析网格和公共增益变换

**文件：**

- Modify: `scripts/analysis/channel_modeling/main_path_gain_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_main_path_gain_core.py`

**接口：**

- `build_analysis_grid(observation: TrackingObservation, bin_ms: int=20) -> list[GainGridRow]`
- `compute_run_reference(rows: Sequence[GainGridRow]) -> float`
- `compute_local_upper_baseline(rows: Sequence[GainGridRow], window_s: float=10.0) -> BaselineResult`
- `db_to_linear_amplitude(gain_db: NDArray) -> NDArray`

- [ ] 测试 1 ms/20 ms native cadence 得到一致的 20 ms bin 语义。
- [ ] 测试 rolling baseline 不跨 gap/run，短 segment fallback 与 `<2 s` inconclusive。
- [ ] 测试 `0 dB→1`、`-6.020599913 dB→0.5`，且所有输出幅度有限、正值。
- [ ] 明确区分 `C_ref_run` 和 `C_upper(t)` 字段，禁止重用列名。

### Task 5：提取 fade event 并实现删失

**文件：**

- Modify: `scripts/analysis/channel_modeling/main_path_gain_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_main_path_gain_core.py`

**接口：**

- `extract_fade_events(rows: Sequence[GainGridRow], config: FadeRule) -> FadeExtractionResult`
- `classify_fade_event_support(event: FadeEvent) -> str`

- [ ] 测试 3 dB/20 ms 进入、1 dB/100 ms 退出和 hysteresis 抖动。
- [ ] 测试 LOCK_BAD、gap、run end 的 right-censoring；确保不输出伪最大深度。
- [ ] 测试跨 elevation band 的 event 只进入 environment fit。
- [ ] 测试 2/6 dB sensitivity 不会改变 primary catalog 或参数 hash。

### Task 6：边际 family selection 与层级参数

**文件：**

- Modify: `scripts/analysis/channel_modeling/main_path_gain_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_main_path_gain_core.py`

**接口：**

- `select_family_by_scene(...) -> FamilySelection`
- `fit_censored_positive_family(...) -> FamilyFit`
- `fit_hierarchical_gain_marginals(...) -> HierarchicalGainResult`
- `fit_hierarchical_fade_models(...) -> HierarchicalFadeResult`
- `fit_gamma_poisson_rates(...) -> HierarchicalRateResult`

- [ ] 正常 gain 的 Student-t/normal/Laplace round-trip、固定 tie-break、失败 fold 保留测试。
- [ ] depth/duration 的 lognormal/Gamma/Weibull 生存似然与删失 fixture 测试。
- [ ] scene-grouped CV 测试，明确 `row_random_split_used=false`。
- [ ] 空 cell exact parent inheritance、geometry-ineligible 不进入 cell likelihood、支持标签测试。
- [ ] rate exposure 使用秒而非 row count；zero-exposure cell 不生成假 empirical rate。

### Task 7：拟合时间相关性并发布未来生成接口

**文件：**

- Modify: `scripts/analysis/channel_modeling/main_path_gain_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_main_path_gain_core.py`

**接口：**

- `fit_latent_correlation_time(...) -> CorrelationTimeFit`
- `sample_normal_common_gain(environment: str, elevation_band: str, duration_ms: int, seed: int, model: MainGainModel) -> NDArray`
- `sample_fade_event_attributes(...) -> list[FadeEventDraw]`

- [ ] OU/AR fixture 测试恢复已知 tau，且不跨 gap 配对。
- [ ] 相同 seed bitwise reproducible，不同 seed 不同；1 ms 输出长度正确。
- [ ] 稀疏 cell 继承来源可审计。
- [ ] sampler 只输出正常公共增益和 fade event 属性，不实现 phase、lock recovery 或 NLOS activation。

### Task 8：构建 new-only 模型 artifact

**文件：**

- Create: `scripts/analysis/channel_modeling/build_main_path_common_gain_fade_model.py`
- Create: `scripts/analysis/channel_modeling/tests/test_build_main_path_common_gain_fade_model.py`

**接口：**

- `build_model(project_root: Path, config_path: Path, output_dir: Path) -> BuildReceipt`

- [ ] existing namespace rejection 测试，原 marker 保持不变。
- [ ] source/config/script/package/protected-pipeline hash preflight 测试。
- [ ] 先写临时 sibling namespace，所有文件 flush/hash/QA-schema 检查后以一次原子目录 rename 发布；异常时保留 failure receipt，不删除 partial。
- [ ] manifest 中写 `raw_iq_read=false`、`matlab_executed=false`、`sage_executed=false`、`batch_executed=false`、`gold_labels_used_for_selection=false`。
- [ ] 真实 build 命令仅在后续明确授权后运行：

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\build_main_path_common_gain_fade_model.py `
  --project-root E:\GNSS_Multipath_Project `
  --config E:\GNSS_Multipath_Project\configs\channel_modeling\main_path_common_gain_fade_v1.json `
  --output E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\main_path_common_gain_fade_v1_20260826_r1
```

### Task 9：独立 auditor 与模型 QA

**文件：**

- Create: `scripts/analysis/channel_modeling/audit_main_path_common_gain_fade_model.py`
- Create: `scripts/analysis/channel_modeling/tests/test_audit_main_path_common_gain_fade_model.py`
- Create on successful execution only: `docs/MAIN_PATH_COMMON_GAIN_FADE_MODEL_V1_REPORT.md`

**接口：**

- `audit_model(project_root: Path, model_dir: Path) -> QaResult`

- [ ] auditor 不 import builder 的拟合函数，只读 source/model/artifact 独立重算关键统计和 hash。
- [ ] QA 必查：input/hash、63/1 eligibility、物理输入去重、geometry join、C/N0 有限性、baseline、gap、lock censoring、family normalization、grouped folds、cell support、rate exposure、tau、seed reproducibility、文件 hash、namespace isolation。
- [ ] 4096 个固定 seed QA draws/cell；检查幅度有限且 >0、分位数和 ACF 与 model 一致。
- [ ] data-supported cell 的 held-out P10/P50/P90 必须落在 scene-block 95% predictive interval；稀疏 cell 记 `NOT_ESTIMABLE_SPARSE_GROUP`，不得伪 PASS。
- [ ] fade posterior predictive count/depth/duration 覆盖按完整 scene holdout 报告；任何 LOCK_BAD 深度被当精确值则 hard FAIL。
- [ ] 验证 protected Pipeline hash 未变，path/lock parent artifact 未修改。
- [ ] 后续独立 QA 命令：

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\audit_main_path_common_gain_fade_model.py `
  --project-root E:\GNSS_Multipath_Project `
  --model-dir E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\main_path_common_gain_fade_v1_20260826_r1
```

### Task 10：静态/回归测试和状态同步

- [ ] `py_compile` 新增三个脚本和 core。
- [ ] 运行所有新增 tests，再运行 `test_build_environment_lock_model.py` 与现有 channel-model tests，确保父模型无回归。
- [ ] 运行 `git diff --check`；确认无 scene、sage_results、raw、metadata、inventory、production artifact 变化。
- [ ] 仅在真实 build + independent QA 完成后更新：
  - `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`：Implemented/Validated 状态、namespace/hash/QA；
  - `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`：只有形成论文可用事实且经审阅时才更新。
- [ ] 计划阶段不更新两个 handoff，也不把模型写成 Completed。

未来验证命令模板：

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m py_compile `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\main_path_gain_core.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\build_main_path_common_gain_fade_model.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\audit_main_path_common_gain_fade_model.py

D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe -m pytest `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_main_path_gain_core.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_build_main_path_common_gain_fade_model.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_audit_main_path_common_gain_fade_model.py `
  E:\GNSS_Multipath_Project\scripts\analysis\test_build_environment_lock_model.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests `
  -q
```

---

## 7. 放行门槛

只有下列条件全部满足，才能把本层标记为 `Validated` 并进入“三个 NLOS 槽位激活规则”实施：

1. 真实 source/hash/eligibility preflight PASS；无重复物理 tracking 双计权。
2. 公共增益被明确限定为 run-normalized C/N0 proxy；没有绝对功率或物理 LOS 声明。
3. 仰角 cell 只使用 same-PRN、逐时刻、≤5 s 的 GSV join；失败 cell 采用 parent/PRIOR_ONLY 而非伪 geometry。
4. 所有 gap/LOCK_BAD/inconclusive 均未被当作精确 fade depth。
5. family selection 和验证均按 scene 分组，未随机拆散相邻 tracking 记录。
6. 12 个 environment×elevation cell 均有模型记录和独立 support/provenance 状态。
7. 固定 seed 1 ms 正常公共增益生成可复现、有限且线性幅度 >0。
8. 独立 QA 为 `PASS` 或带明确稀疏限制的 `PASS_WITH_LIMITATIONS`；任何 provenance、删失、geometry、normalization 或 deterministic QA 失败均不放行。
9. lock/path parent artifacts 和 production Pipeline hash 完全不变。

即使通过，本层仍不是完整暗室生成器。后续顺序保持：

1. 固定 3 个 NLOS 槽位激活规则；
2. 失锁状态到幅度、相位和恢复过程映射；
3. 可复现四路径随机生成器与端到端 QA。

---

## 8. 本次规划状态

```text
MAIN_PATH_COMMON_GAIN_FADE_MODEL = PLANNED / NOT STARTED
ABSOLUTE_RF_POWER_MODEL = NOT AVAILABLE
PHYSICAL_LOS_GAIN_CLAIM = NOT ALLOWED
ENVIRONMENT_ELEVATION_PATH_MODEL = COMPLETED_WITH_LIMITATIONS
ENVIRONMENT_LOCK_MODEL = COMPLETED_WITH_LIMITATIONS
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
DATA_OR_EXISTING_ARTIFACT_MODIFIED = NO
HANDOFF_UPDATE_REQUIRED = NO (plan only)
```
