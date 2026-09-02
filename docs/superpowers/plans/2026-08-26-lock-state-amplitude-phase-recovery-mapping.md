# Receiver Lock-State to Amplitude, Phase, and Recovery Mapping v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变已完成的环境×仰角路径分布、主径公共增益/衰落模型和固定三 NLOS 槽位模型的前提下，建立一个可审计的组合层：按环境生成接收机失锁状态，将该状态映射为四条路径共享的幅度包络，保持物理路径相位按相对 Doppler 连续演化，并定义失锁后的恢复过程。

**Architecture:** 采用“冻结父模型 + 独立状态机 + 显式假设层”的结构。环境条件失锁模型只负责 `TRACKED/LOCK_BAD` 进入率和持续时间；公共增益模型提供正常增益与可观测衰落代理；本层用半马尔可夫状态机生成 `TRACKED → FADING_TO_LOCK_BAD → LOCK_BAD_HOLD → RECOVERING → TRACKED`，并将同一实值包络乘到 path 0 和所有 active NLOS 槽位。相位使用冻结的“初相均匀随机 + 1 ms Doppler 连续积分”规则，失锁和恢复均不重置物理路径相位。由于当前数据没有绝对 RF 功率、接收机灵敏度或真实失锁衰减深度，本层必须同时保留科学保守的 `EMPIRICAL_DIAGNOSTIC_PROXY` 与显式外加参数的 `FORCED_LOCK_LOSS_STRESS`，二者不得混写为同一实测模型。

**Tech Stack:** Python 3.12；NumPy 2.5.1；SciPy 1.18.0；OpenBLAS；标准库 `csv/json/gzip/hashlib/dataclasses/pathlib/enum`；pytest。固定解释器为 `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`，禁止联网安装依赖。

**Spec:** `docs/ENVIRONMENT_CONDITIONED_LOCK_MODEL_V1_REPORT.md`; `docs/MAIN_PATH_COMMON_GAIN_FADE_MODEL_V1_REPORT.md`; `docs/NLOS_SLOT_ACTIVATION_MODEL_V1_REPORT.md`; 本计划中的 Frozen Contracts 与 Scientific Design。

## Global Constraints

- 当前状态为 `Planned / Not started`。本文件不代表模型已实现、已拟合或已通过 QA。
- 未来实现只读取已有 10.23 MHz 派生 CSV/JSON/CSV.GZ；禁止读取 raw IQ，禁止运行 MATLAB、SAGE、batch 或任何 20.46 MHz 任务。
- 不修改或覆盖任何 `scenes/**/sage_results`、event database partition、tracking 文件、metadata、inventory、生产 request/manifest、既有模型和 QA artifact。
- 受保护生产入口 `scripts/sage_pipeline/run_nav_sage_pipeline.m` 必须保持 SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。
- 环境失锁模型、公共增益模型、路径分布模型和三槽位激活模型均作为 immutable parent；若任一 parent hash 不一致，builder 必须 fail closed。
- `LOCK_BAD` 是接收机 tracking diagnostic，不是物理信号消失、NLOS 标签、绝对衰减值或 confirmed multipath 标签。
- 失锁进入率和持续时间当前只按 `environment_class` 条件化；elevation band 只作为输出上下文透传，不得伪造 elevation-conditioned lock law。
- path 0 是仿真参考主径槽位，不保证是物理 LOS，也不保证是四条路径中最强者。
- 路径参数的冻结单位保持：delay 为 ns，Doppler 为 Hz，amplitude 为线性幅度比，phase 为 rad。
- path 0 的未叠加公共增益默认元组保持 `[0 ns, 0 Hz, 1]`；最终 path 0 幅度允许随公共增益和失锁包络变化。
- active NLOS 的相对幅度比可大于 1，不得为了强制 path 0 最强而裁剪。
- inactive NLOS slot 保持 `amplitude=0`，而 delay、Doppler、phase 为 null；不得用 0 伪造缺失参数。
- 不把相位写成数据拟合结果。当前相位必须标记为 `ASSUMPTION_ONLY_UNIFORM_INITIAL_PLUS_DOPPLER_CONTINUOUS`。
- 默认模式不得把所有路径硬置零。若需要强制暗室接收机失锁，必须由用户显式提供正值 `stress_floor_linear` 或等价 dB 深度，并标记 `ASSUMPTION_ONLY`。
- 未来输出必须使用独立 new-only namespace：`dataset_generation_logs/channel_modeling/lock_amplitude_phase_recovery_v1_20260826_r1/`。目录已存在时停止，不 overwrite、不 resume、不删除、不自动改名。
- 本计划只新增计划文档，不更新 Engineering/Paper Handoff。只有未来真实 build + independent QA 后，才按文档同步规则判断并更新状态。

---

## Frozen Parent Models and Evidence Baseline

| Parent/evidence | Frozen artifact | SHA-256 / count |
|---|---|---|
| Environment lock model | `dataset_generation_logs/channel_modeling/environment_lock_model_v1_20260826_r2/lock_model_manifest.json` | `21c04938cba559b3e042806b093eba82e4e86a44977e95831c715aa03ffc97a5` |
| Lock parameters | `.../environment_lock_model_parameters.csv` | `47f0a070053eb6c44daf42a3665c304d3252f9165d297b757084d80865f512bb` |
| Lock-event catalog | `.../lock_event_catalog.csv` | `0b2eec22b12b9e853bac8700a37a9a2698aec585be6d96dbfa104632bbeab876`; 48 events |
| Main/common-gain model | `dataset_generation_logs/channel_modeling/main_path_common_gain_fade_v1_20260826_r4/model_manifest.json` | `6f36dab892622c9b9dc61ecde91fda85ff12ca60eeea4f81fe37760f0acb1e45` |
| Common-gain 20 ms grid | `.../common_gain_analysis_grid.csv.gz` | `c5691a42e160e85b5106293499f0ea9e6af96016f27933f29913e8e2e0d8ce09`; 307,572 rows |
| NLOS path distribution | `dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/model_manifest.json` | `4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c` |
| Three-slot activation model | `dataset_generation_logs/channel_modeling/nlos_slot_activation_v1_20260826_r1/model_manifest.json` | `b47b2a09f9acc5f1ccd65dcf923623dbeea27e3aec3e3e3f04c2e094a3e486d2` |
| Protected production pipeline | `scripts/sage_pipeline/run_nav_sage_pipeline.m` | `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c` |

已验证的 lock semantics：

- `carrier_lock_test < -0.5` 为 `LOCK_BAD`；有限且 `>= -0.5` 为 `LOCK_GOOD`。
- bad confirmation 为 20 ms；good reacquisition confirmation 为 100 ms。
- 时间轴为 `PRN_start_sample_count / 10230000`。
- tracking gap 为 `INCONCLUSIVE_GAP`，不能转换为 outage。
- initial acquisition 不进入失锁事件；terminal event 支持 right censoring。
- 63 个 eligible runs 中观察到 48 个 lock-loss intervals。
- 环境进入率由 Gamma-Poisson posterior 给出；持续时间族已选择 Gamma。

已验证的 gain/fade semantics：

- `C_ref_run = median(C/N0 | LOCK_GOOD)`。
- `common_gain_db = C/N0 - C_ref_run`。
- `common_gain_linear = 10^(common_gain_db/20)`。
- fade 进入阈值为 3 dB/20 ms，退出阈值为 1 dB/100 ms。
- `LOCK_BAD` 内的幅度深度是 censored/diagnostic evidence，不是精确物理衰减。
- 已选 normal common-gain family 为 Student-t，observable fade depth 为 lognormal，fade duration 为 Gamma。

---

## Alternatives Considered

### Recommended: shared lock envelope + continuous physical phase

生成一个公共 lock envelope `G_lock[m]`，并应用于 path 0 与所有 active NLOS：

```text
A_0[m] = G_background[m] * G_lock[m]
A_i[m] = G_background[m] * G_lock[m] * Z_i * A_rel_i,  i=1,2,3
```

这样既允许主径随时间衰落，也保持 `A_i/A_0=A_rel_i` 的已拟合相对关系。由于 `A_rel_i` 可大于 1，path 0 不会被错误强制为最强路径。

### Rejected: only attenuate path 0

接收机 lock diagnostic 来自复合相关/跟踪行为，当前数据不能证明它只作用于 path 0。只衰减 path 0 会人为改变已拟合 NLOS/path-0 比值，并可能让 NLOS 在每次失锁时被强制增强为主导路径。

### Rejected: set all four amplitudes to exactly zero

现有 tracking 数据没有绝对 RF 功率、接收机灵敏度或“失锁等于零信号”的证据。硬置零还会使物理相位在数学上不可观测，并制造不连续跳变。

### Rejected: independent random attenuation for four paths

当前数据没有 path-specific lock attenuation 标注，独立衰减会引入无法识别的自由度，并破坏路径间相对幅度的冻结语义。

### Two permitted operating modes

1. `EMPIRICAL_DIAGNOSTIC_PROXY`：使用父 common-gain/fade 模型的 observable fade depth 作为失锁幅度代理，并显式声明“不保证真实接收机失锁”。
2. `FORCED_LOCK_LOSS_STRESS`：使用用户提供的 `stress_floor_linear`/`stress_depth_db` 进行压力测试；该值必须标记 `ASSUMPTION_ONLY`，不能写成数据拟合结果。

不提供 stress floor 时，模式 2 必须 fail closed；不得静默选择默认“足以失锁”的幅度。

---

## Frozen Scientific Design

### 1. One-millisecond state machine

状态枚举：

```text
TRACKED
FADING_TO_LOCK_BAD
LOCK_BAD_HOLD
RECOVERING
INCONCLUSIVE
```

生成流程：

```text
TRACKED
  -- environment entry probability --> FADING_TO_LOCK_BAD
  -- entry envelope complete --------> LOCK_BAD_HOLD
  -- sampled lock duration complete -> RECOVERING
  -- recovery envelope complete -----> TRACKED
```

冻结规则：

- 只在 `TRACKED` exposure 中评估环境条件进入概率；非 tracked 状态不重复触发新事件。
- `lock_bad_duration_ms` 来自父 lock model 的环境 Gamma duration，并向上量化到整数 ms，最小 20 ms。
- `entry_ramp_ms = min(sampled_or_fallback_entry_ms, lock_bad_duration_ms)`；剩余时间为 `LOCK_BAD_HOLD`。该分段必须写入 provenance，不能静默改变总失锁持续时间。
- recovery 在 lock interval 结束后开始；其持续时间不计入父模型的 `LOCK_BAD` duration。
- 若父模型 cell 为 `PARTIAL_POOLING_REQUIRED`/`PRIOR_DOMINANT`，生成结果必须透传 support status。
- `INCONCLUSIVE` 只用于缺失输入、证据 gap 或参数不合法；它不是随机 outage 状态，也不能输出为 LOS/no-event。
- elevation band 仅作为仿真请求上下文和父路径/gain cell 选择键；lock timing 参数仍来自环境父层。

### 2. Lock-event/common-gain evidence alignment

未来 builder 应只读对齐 48 个 `lock_event_catalog.csv` 事件与 20 ms `common_gain_analysis_grid.csv.gz`：

- join key 必须包含 `run_id`，并核对 scene、PRN、tracking channel、environment 一致。
- 时间匹配使用 nearest 20 ms grid row，最大绝对误差 `0.011 s`。
- exact tie 使用较小 `time_bin_index`；禁止插值。
- 不允许跨 run、continuity gap、下一 lock event 或 record boundary。

每个事件使用预先冻结的观察窗：

| Segment | Fixed interval relative to event |
|---|---|
| Pre-entry baseline | `[start-1.0 s, start-0.1 s]`, `LOCK_GOOD` only |
| Entry evidence | `[start-0.1 s, start]` |
| Lock interval | `[start, end]` |
| Recovery evidence | `(end, end+2.0 s]`, until gap/next event/end-of-run |

派生字段：

- `pre_entry_gain_db_median`
- `entry_gain_db_first/last/min`
- `observed_depth_lower_bound_db`
- `first_post_lock_gain_db`
- `recovery_time_to_within_1db_100ms_s`
- `recovery_initial_slope_db_per_s`
- `pre_rows`, `lock_rows`, `post_rows`
- `start_join_delta_s`, `end_join_delta_s`
- `depth_status`, `recovery_status`, `continuity_status`

状态枚举必须至少包含：

```text
DEPTH_PROXY_OBSERVED
DEPTH_RIGHT_CENSORED
RECOVERY_OBSERVED
RECOVERY_RIGHT_CENSORED
RECOVERY_INCONCLUSIVE_GAP
RECOVERY_NO_VALID_BASELINE
EVENT_ALIGNMENT_INCONCLUSIVE
```

`observed_depth_lower_bound_db` 只能称为 tracking/CN0 proxy。它不得覆盖父 observable-fade depth model，也不得被命名为 physical attenuation。

### 3. Amplitude envelope

使用无过冲、端点可精确检查的 raised-cosine 包络：

```text
g_min = 10^(-D_proxy_db/20)

entry(u)    = 1 - (1-g_min) * 0.5 * (1-cos(pi*u)),  u in [0,1]
recovery(u) = g_min + (1-g_min) * 0.5 * (1-cos(pi*u)), u in [0,1]
```

冻结要求：

- `entry(0)=1`，`entry(1)=g_min`。
- `recovery(0)=g_min`，`recovery(1)=1`。
- entry 单调不增，recovery 单调不减，不允许 overshoot。
- `LOCK_BAD_HOLD` 保持 `g_min`；v1 不在 hold 内增加未识别的随机快衰落。
- 默认 `g_min > 0`；exact zero 不允许进入 v1 scientific mode。
- `EMPIRICAL_DIAGNOSTIC_PROXY` 的 `D_proxy_db` 从已冻结 observable-fade depth parent 按 environment/elevation 的 support chain 采样，并记录 `OBSERVABLE_FADE_PARENT_PROXY`。
- `FORCED_LOCK_LOSS_STRESS` 的 `D_proxy_db=-20log10(stress_floor_linear)`，只接受 `0 < stress_floor_linear < 1`，并记录 `ASSUMPTION_ONLY_USER_STRESS_FLOOR`。
- 若 common-gain parent 已输出正在进行的普通 fade，最终 composition scheduler 必须将 ordinary fade 和 lock envelope 标成两个可见状态；不得在没有 provenance 的情况下把两次 depth draw 静默相乘。
- v1 推荐的冲突政策是 `LOCK_ENVELOPE_SUPERSEDES_ORDINARY_FADE_ENVELOPE`，但保留 normal/background common-gain variation。该政策是 composition assumption，必须进入 manifest。

### 4. Recovery duration and support policy

恢复时间从 event-aligned proxy 中派生，定义为：事件结束后 common-gain proxy 首次回到 pre-entry median 的 ±1 dB 内，并连续保持至少 100 ms。

候选 duration families：`lognormal`, `gamma`, `weibull`。选择规则：

1. 使用 right-censored likelihood；gap/inconclusive 事件不作为 uncensored duration。
2. 全局 family 由 AICc 选择，固定字母序 tie-break。
3. 用 leave-one-scene-out grouped log likelihood 做方向性复核；不得随机拆分相邻 events。
4. environment 参数向 global parent 做 partial pooling。
5. `>=10` 个 observed recoveries 且来自 `>=2` scenes：`DATA_SUPPORTED_WITH_GROUPED_VALIDATION`。
6. 有 observed recovery 但不足阈值：`SPARSE_PARTIAL_POOLING`。
7. 无 observed recovery：使用 global parent；若 global 也不满足门禁，则使用 100 ms minimum fallback，并标记 `ASSUMPTION_ONLY_REACQUISITION_DEBOUNCE_FALLBACK`。

raised-cosine、exponential-linear-amplitude 和 linear-in-dB 只作为 shape candidates。使用每个 observed recovery 的归一化轨迹进行 scene-grouped误差比较；如果 shape 选择不稳定，则冻结 raised-cosine 作为最小平滑假设，不能根据单个环境手调。

### 5. Phase policy

每个 block 开始时，对 path 0 和每个 active NLOS 独立生成：

```text
phi_i[1] ~ Uniform(-pi, pi)
phi_i[m+1] = wrap_to_pi(phi_i[m] + 2*pi*RelativeDoppler_i*0.001)
```

冻结规则：

- path 0 默认 `RelativeDoppler=0 Hz`，因此其相位在没有另行授权的 oscillator model 时保持初值。
- active NLOS 使用已拟合的 `RelativeDoppler`；delay、Doppler 和基础幅度在 block 内固定，phase 每 ms 确定性演化。
- `LOCK_BAD_HOLD` 中相位仍连续推进；sidecar 标记 `phase_observable=false`，但不能每 ms 重新随机化。
- recovery 不重置物理 channel phase。
- receiver reacquisition 后的 NCO/PLL phase reset 属于 receiver model，不写入 `RelativePhase_rad`。
- 新 block 或新激活 NLOS slot 才分配新的初始相位；inactive slot phase 保持 null。
- wrap 区间统一为 `[-pi, pi)`，避免 `pi` 与 `-pi` 双表示。

### 6. Final row contract and diagnostic sidecar

未来随机生成器的主表继续使用用户冻结的七列：

```text
ms
SatelliteID
NLOSPathID
RelativeDelay
RelativeDoppler
RelativeAmplitude
RelativePhase_rad
```

语义：

- `ms`：从 1 开始的毫秒索引。
- `SatelliteID`：当前契约中存储 `LOW/MID/HIGH` elevation context；最终生成器实现时应同时在 manifest 中说明它不是 PRN ID。
- `NLOSPathID=0`：参考主径槽位；`1/2/3`：固定 NLOS 槽位。
- `RelativeDelay`：ns。
- `RelativeDoppler`：Hz。
- `RelativeAmplitude`：相对名义参考幅度的线性幅度比。`A_i/A_0` 在 active NLOS 上仍等于抽样的路径相对幅度比。
- `RelativePhase_rad`：`[-pi,pi)`。

主表之外必须生成逐 ms/path 的 diagnostic sidecar，至少包含：

```text
environment_class
elevation_band
lock_state
lock_event_id
lock_mapping_mode
lock_envelope_linear
background_common_gain_linear
amplitude_support_status
lock_depth_source
recovery_status
phase_evolution_mode
phase_observable
path_active
path_status
assumption_status
seed_stream_id
parent_lock_manifest_sha256
parent_gain_manifest_sha256
parent_slot_manifest_sha256
```

主表没有这些字段并不允许丢失 provenance；sidecar 与主表必须通过 `(simulation_id, ms, NLOSPathID)` 一一关联。

---

## Planned File Layout

### Source and configuration

- Create: `configs/channel_modeling/lock_amplitude_phase_recovery_v1.json`
- Create: `scripts/analysis/channel_modeling/lock_amplitude_phase_recovery_core.py`
- Create: `scripts/analysis/channel_modeling/build_lock_amplitude_phase_recovery_model.py`
- Create: `scripts/analysis/channel_modeling/audit_lock_amplitude_phase_recovery_model.py`
- Create: `scripts/analysis/channel_modeling/tests/test_lock_amplitude_phase_recovery_core.py`
- Create: `scripts/analysis/channel_modeling/tests/test_build_lock_amplitude_phase_recovery_model.py`
- Create: `scripts/analysis/channel_modeling/tests/test_audit_lock_amplitude_phase_recovery_model.py`

### Future new-only output namespace

`dataset_generation_logs/channel_modeling/lock_amplitude_phase_recovery_v1_20260826_r1/`

Expected artifacts:

- `source_preflight.csv`
- `lock_gain_alignment_catalog.csv`
- `lock_event_envelope_features.csv`
- `recovery_trace_catalog.csv.gz`
- `recovery_family_selection.csv`
- `environment_recovery_parameters.csv`
- `lock_amplitude_mapping_contract.json`
- `phase_policy_contract.json`
- `composition_contract.json`
- `deterministic_scalar_draws.csv`
- `deterministic_state_sequence.csv.gz`
- `lock_amplitude_phase_recovery_model.json`
- `model_manifest.json`
- `build_receipt.json`
- `model_report.md`
- `independent_qa_result.json`
- `independent_qa_report.md`

### Human-readable status report after real execution

- Create only after successful build/QA: `docs/LOCK_AMPLITUDE_PHASE_RECOVERY_MODEL_V1_REPORT.md`

---

## Task 1: Freeze Configuration, Parent Hashes, and Data Contracts

**Files:**

- Create: `configs/channel_modeling/lock_amplitude_phase_recovery_v1.json`
- Create: `scripts/analysis/channel_modeling/lock_amplitude_phase_recovery_core.py`
- Test: `scripts/analysis/channel_modeling/tests/test_lock_amplitude_phase_recovery_core.py`

- [ ] **Step 1: Write failing configuration/provenance tests**

Test that the loader rejects:

- wrong parent manifest/file SHA;
- unsupported sample rate;
- missing environment;
- an elevation-conditioned lock timing section;
- `stress_floor_linear <=0` or `>=1`;
- output path outside `dataset_generation_logs/channel_modeling/`;
- existing output namespace;
- `resume_allowed=true`;
- any flag enabling raw IQ, MATLAB, SAGE, batch, or 20.46 MHz.

- [ ] **Step 2: Add immutable config schema**

The config must freeze:

```json
{
  "model_id": "lock-amplitude-phase-recovery-v1",
  "time_step_ms": 1,
  "environments": ["Urban", "Special Reflective", "Mountain/Valley", "Highway/Open"],
  "lock_timing_conditioning": "environment_only",
  "phase_policy": "uniform_initial_plus_doppler_continuous",
  "phase_wrap_interval": "[-pi,pi)",
  "default_mapping_mode": "EMPIRICAL_DIAGNOSTIC_PROXY",
  "stress_floor_required_for_stress_mode": true,
  "new_only": true,
  "resume_allowed": false
}
```

Parent paths and exact hashes listed in the Frozen Parent Models table must be embedded, not inferred by filename search.

- [ ] **Step 3: Add core dataclasses/enums**

Implement immutable data types for:

```python
class LockState(Enum): ...
class LockMappingMode(Enum): ...

@dataclass(frozen=True)
class LockEventSchedule: ...

@dataclass(frozen=True)
class PathState: ...

@dataclass(frozen=True)
class MappingProvenance: ...
```

- [ ] **Step 4: Run focused tests**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest scripts\analysis\channel_modeling\tests\test_lock_amplitude_phase_recovery_core.py -q
```

- [ ] **Step 5: Review and freeze config SHA before any fitting/build**

Record canonical JSON SHA-256 in the future build receipt. No source data may be read before this preflight hash is calculated and logged.

---

## Task 2: Build the Lock/Gain Alignment Evidence Layer

**Files:**

- Modify: `scripts/analysis/channel_modeling/lock_amplitude_phase_recovery_core.py`
- Create: `scripts/analysis/channel_modeling/build_lock_amplitude_phase_recovery_model.py`
- Test: `scripts/analysis/channel_modeling/tests/test_build_lock_amplitude_phase_recovery_model.py`

- [ ] **Step 1: Write synthetic alignment tests first**

Cover:

- nearest 20 ms match within 11 ms;
- exact tie uses lower `time_bin_index`;
- run/scene/PRN/channel mismatch fails;
- no cross-gap or cross-next-event recovery;
- missing pre baseline is inconclusive;
- finite recovery and right-censored recovery;
- all 48 source events retained exactly once, including inconclusive events.

- [ ] **Step 2: Implement streaming CSV.GZ join**

Read the common-gain grid by run, not by loading raw tracking or raw IQ. Use bounded-memory grouped processing and never modify the source GZIP file.

- [ ] **Step 3: Derive per-event features with explicit null/status semantics**

No baseline, depth, or recovery value may be filled with zero. Numeric fields remain null and an explicit status explains why.

- [ ] **Step 4: Write evidence artifacts**

Produce `lock_gain_alignment_catalog.csv`, `lock_event_envelope_features.csv`, and `recovery_trace_catalog.csv.gz` under the new-only namespace.

- [ ] **Step 5: Enforce population reconciliation**

Required checks:

```text
source lock events = 48
output event rows = 48
duplicate (run_id,event_id) = 0
cross-run matches = 0
fabricated recovery rows = 0
```

An alignment count below 48 is allowed only if every missing match is retained as `EVENT_ALIGNMENT_INCONCLUSIVE`; it is not allowed to disappear from accounting.

---

## Task 3: Fit Recovery Support and Freeze the Envelope Contract

**Files:**

- Modify: `scripts/analysis/channel_modeling/lock_amplitude_phase_recovery_core.py`
- Modify: `scripts/analysis/channel_modeling/build_lock_amplitude_phase_recovery_model.py`
- Test: `scripts/analysis/channel_modeling/tests/test_build_lock_amplitude_phase_recovery_model.py`

- [ ] **Step 1: Write recovery-likelihood and shape tests**

Test uncensored/censored likelihood, deterministic tie-break, partial pooling, monotone shape, exact endpoints, no overshoot, and unsupported-environment fallback provenance.

- [ ] **Step 2: Implement global family selection**

Compare lognormal/Gamma/Weibull duration families using AICc with right-censored likelihood. Recheck with leave-one-scene-out grouped scores; do not tune by individual lock event.

- [ ] **Step 3: Implement environment partial pooling**

Estimate environment recovery parameters only where support permits. Sparse environments inherit the global parent with an explicit support label.

- [ ] **Step 4: Select recovery shape without event-specific tuning**

Compare raised-cosine, exponential-linear-amplitude, and linear-in-dB on normalized observed traces. If grouped selection is unstable, use raised-cosine and mark it as a frozen smoothness assumption.

- [ ] **Step 5: Freeze amplitude mapping modes**

Write `lock_amplitude_mapping_contract.json` so the empirical proxy and forced stress mode cannot be confused. Include:

```text
physical_lock_depth_identified = false
hardware_lock_loss_calibrated = false
default_exact_zero_allowed = false
stress_floor_source = user_configuration_only
```

---

## Task 4: Implement the Environment Lock State Machine

**Files:**

- Modify: `scripts/analysis/channel_modeling/lock_amplitude_phase_recovery_core.py`
- Test: `scripts/analysis/channel_modeling/tests/test_lock_amplitude_phase_recovery_core.py`

- [ ] **Step 1: Write state-transition tests**

Cover no re-entry while nontracked, exact 1 ms indexing, duration rounding, minimum 20 ms bad interval, recovery completion, no event overlap, deterministic same-seed behavior, and separate random streams by environment/satellite/block.

- [ ] **Step 2: Implement semi-Markov scheduling**

Use the parent environment entry probability only while `TRACKED`; sample the parent Gamma duration only after an entry. Do not derive elevation timing parameters.

- [ ] **Step 3: Preserve support/provenance per event**

Every generated event must record entry source, duration source, environment support status, recovery source, mapping mode, and seed stream ID.

- [ ] **Step 4: Fail closed on unsupported/invalid parameters**

Invalid parameters produce `INCONCLUSIVE` with no simulated amplitude claim; they must not be converted to `TRACKED` or `LOCK_BAD` silently.

---

## Task 5: Implement Shared Amplitude Composition

**Files:**

- Modify: `scripts/analysis/channel_modeling/lock_amplitude_phase_recovery_core.py`
- Test: `scripts/analysis/channel_modeling/tests/test_lock_amplitude_phase_recovery_core.py`

- [ ] **Step 1: Write amplitude-invariant tests**

Test:

- path 0 varies with background gain and lock envelope;
- every active NLOS receives the same common envelope;
- `A_i/A_0` remains equal to the sampled NLOS relative amplitude within tolerance;
- `A_rel_i > 1` remains allowed;
- inactive slot amplitude remains 0 and other parameters null;
- default scientific mode never emits exact zero for active paths;
- stress mode refuses to run without explicit floor;
- entry/recovery continuity and monotonicity;
- lock envelope does not silently double-apply an ordinary fade envelope.

- [ ] **Step 2: Implement composition function**

Target interface:

```python
def compose_path_amplitudes(
    background_common_gain_linear: float,
    lock_envelope_linear: float,
    slot_active: tuple[bool, bool, bool],
    nlos_relative_amplitudes: tuple[float | None, float | None, float | None],
) -> tuple[float, float, float, float]:
    ...
```

- [ ] **Step 3: Add ordinary-fade/lock conflict provenance**

The scheduler must explicitly record whether the lock envelope superseded, coincided with, or was absent from an ordinary fade event. v1 selected policy must be deterministic and written to the contract.

---

## Task 6: Implement Phase Initialization and Doppler-Continuous Evolution

**Files:**

- Modify: `scripts/analysis/channel_modeling/lock_amplitude_phase_recovery_core.py`
- Test: `scripts/analysis/channel_modeling/tests/test_lock_amplitude_phase_recovery_core.py`

- [ ] **Step 1: Write strict phase tests**

Cover:

- seeded uniform initialization in `[-pi,pi)`;
- exact 1 ms Doppler increment;
- positive and negative Doppler;
- wrap at both boundaries;
- path 0 at 0 Hz remains constant;
- phase continuity through entry, hold, and recovery;
- no phase reset on reacquisition;
- inactive phase is null;
- newly activated slot gets one new phase draw only;
- recurrence error `<=1e-12 rad` for deterministic fixture.

- [ ] **Step 2: Implement phase functions**

```python
def wrap_to_pi(phi_rad: float) -> float: ...

def evolve_phase_1ms(phi_rad: float, relative_doppler_hz: float) -> float:
    return wrap_to_pi(phi_rad + 2.0 * math.pi * relative_doppler_hz * 0.001)
```

- [ ] **Step 3: Separate physical phase from receiver observability**

Emit continuous `RelativePhase_rad` for every active path, and separately set `phase_observable=false` during `LOCK_BAD_HOLD`. Do not implement receiver PLL/NCO phase reset in this channel layer.

---

## Task 7: Build Versioned Model Artifacts and Deterministic QA Draws

**Files:**

- Modify: `scripts/analysis/channel_modeling/build_lock_amplitude_phase_recovery_model.py`
- Test: `scripts/analysis/channel_modeling/tests/test_build_lock_amplitude_phase_recovery_model.py`

- [ ] **Step 1: Write new-only/hash/receipt tests**

Cover existing namespace rejection, immutable parent hash rejection, incomplete artifact rejection, canonical manifest hash, no raw/MATLAB/SAGE flags, and no writes under `scenes/`.

- [ ] **Step 2: Generate scalar distribution QA draws**

Use 4096 deterministic draws per environment for entry interval, lock duration, recovery duration, and empirical proxy depth. Keep independent RNG stream names; changing draw order in one layer must not perturb another layer.

- [ ] **Step 3: Generate state-sequence QA fixtures**

Use at least 64 deterministic 60 s sequences per environment for each permitted mode. These are QA trajectories, not production simulation data.

- [ ] **Step 4: Write model and contracts**

The model JSON must record all parent hashes, support statuses, family choices, assumptions, units, state semantics, and the distinction between diagnostic proxy and forced stress mode.

- [ ] **Step 5: Hash every artifact**

Write artifact size/SHA-256 to `model_manifest.json`, then hash the manifest itself in `build_receipt.json`. No mutable “latest” pointer is permitted.

---

## Task 8: Implement Independent Auditor

**Files:**

- Create: `scripts/analysis/channel_modeling/audit_lock_amplitude_phase_recovery_model.py`
- Test: `scripts/analysis/channel_modeling/tests/test_audit_lock_amplitude_phase_recovery_model.py`

- [ ] **Step 1: Write auditor failure tests**

The auditor must reject altered hashes, missing 48-event accounting, unmarked censoring, nonmonotone envelopes, exact-zero default amplitude, phase reset at recovery, invalid inactive-slot semantics, elevation-conditioned lock timing claims, missing stress provenance, and writes outside the versioned namespace.

- [ ] **Step 2: Recompute scientific invariants independently**

The auditor should not trust builder summaries. It must independently recompute event counts, status counts, envelope endpoints, amplitude ratios, phase recurrence, deterministic draws, and support flags from artifacts.

- [ ] **Step 3: Define QA gates**

```text
SOURCE_PROVENANCE_GATE
LOCK_GAIN_ALIGNMENT_GATE
LOCK_TIMING_GATE
AMPLITUDE_MAPPING_GATE
RECOVERY_ENVELOPE_GATE
PHASE_CONTINUITY_GATE
INACTIVE_SLOT_SEMANTICS_GATE
DETERMINISM_GATE
NAMESPACE_AND_HASH_GATE
PROTECTED_PIPELINE_GATE
```

- [ ] **Step 4: Define final status semantics**

`READY_FOR_GENERATOR_INTEGRATION=YES` may be issued only if all hard gates pass. It means the relative simulation composition layer is ready; it does not mean:

- physical lock attenuation is calibrated;
- actual receiver loss is guaranteed;
- a complete darkroom generator has been validated;
- a final statistical channel model has been completed.

Expected scientific status remains `PASS_WITH_LIMITATIONS` while `HARDWARE_LOCK_LOSS_CALIBRATED=NO`.

---

## Task 9: Future Execution Sequence

This task is intentionally not executed now. When separately authorized, use this order:

- [ ] **Step 1: Verify protected source and parent hashes**

```powershell
Get-FileHash -Algorithm SHA256 E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m
Get-FileHash -Algorithm SHA256 E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\environment_lock_model_v1_20260826_r2\lock_model_manifest.json
Get-FileHash -Algorithm SHA256 E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\main_path_common_gain_fade_v1_20260826_r4\model_manifest.json
Get-FileHash -Algorithm SHA256 E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\nlos_slot_activation_v1_20260826_r1\model_manifest.json
```

- [ ] **Step 2: Static compilation**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m py_compile `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\lock_amplitude_phase_recovery_core.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\build_lock_amplitude_phase_recovery_model.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\audit_lock_amplitude_phase_recovery_model.py
```

- [ ] **Step 3: Unit/regression tests**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_lock_amplitude_phase_recovery_core.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_build_lock_amplitude_phase_recovery_model.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_audit_lock_amplitude_phase_recovery_model.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_nlos_slot_activation_core.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_build_nlos_slot_activation_model.py `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_audit_nlos_slot_activation_model.py -q
```

- [ ] **Step 4: Build once into the frozen new-only namespace**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\build_lock_amplitude_phase_recovery_model.py `
  --project-root E:\GNSS_Multipath_Project `
  --config E:\GNSS_Multipath_Project\configs\channel_modeling\lock_amplitude_phase_recovery_v1.json
```

- [ ] **Step 5: Run independent QA**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' `
  E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\audit_lock_amplitude_phase_recovery_model.py `
  --project-root E:\GNSS_Multipath_Project `
  --artifact-root E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\lock_amplitude_phase_recovery_v1_20260826_r1
```

- [ ] **Step 6: Run `git diff --check` and verify no protected data changed**

Do not commit unrelated dirty-worktree files. Do not delete failed or partial artifacts; retain them as audit evidence in their unique namespace.

---

## Acceptance Matrix

| Gate | PASS requirement | Failure consequence |
|---|---|---|
| Source provenance | All parent paths/hashes and pipeline hash exact | Stop before reading model tables |
| Event accounting | All 48 lock events represented exactly once | FAIL; no fitting |
| Alignment | No cross-run/gap leakage; null/status preserved | FAIL |
| Timing | Environment-only entry/duration reproduced within deterministic Monte Carlo tolerance | FAIL |
| Recovery | Censoring included; fallback explicitly tagged | FAIL if silent imputation |
| Amplitude | Shared envelope, ratio invariant, no default hard zero | FAIL |
| Phase | 1 ms Doppler recurrence and no lock/recovery reset | FAIL |
| Slot semantics | Inactive=0/null; active slots preserve parent order | FAIL |
| Determinism | Same seed byte-identical; stream isolation passes | FAIL |
| Namespace/hash | New-only, complete manifest/receipt hashes | FAIL |
| Hardware calibration | Expected `NO` without user calibration | Limitation, not implementation failure |

Suggested numerical QA tolerances:

- amplitude ratio invariant: absolute/relative error `<=1e-12` for deterministic fixtures;
- envelope endpoints: `<=1e-12`;
- phase recurrence: `<=1e-12 rad` modulo `2pi`;
- exact-zero count among active paths in default mode: `0`;
- unexpected state transition count: `0`;
- cross-run alignment count: `0`;
- parent hash mismatch acceptance count: `0`.

---

## Deliverable Boundary and Remaining Decision

完成本计划并通过 QA 后，可得到：

- 环境条件失锁进入/持续时间的可复现状态序列；
- path 0 与 active NLOS 共用的失锁幅度代理包络；
- 连续、不因失锁/恢复重置的路径相位序列；
- 有审计 provenance 的恢复过程；
- 与三 NLOS 槽位模型和后续七列表格生成器兼容的组合契约。

仍不能仅凭当前数据得到：

- 能保证某台暗室接收机真实失锁的绝对幅度阈值；
- 已标定的 RF dB 衰减深度；
- receiver PLL/NCO reacquisition phase reset；
- event-to-event 路径身份或跨 block path lifetime。

因此，最终可复现随机生成器可先采用 `EMPIRICAL_DIAGNOSTIC_PROXY` 完成科学保守集成。若用户要求“保证发生硬件失锁”的暗室 stress 模式，实施前还需单独冻结一个人工输入：`stress_floor_linear`（或等价接收机灵敏度/幅度下限）。该输入不得从现有 tracking lock 标签反推并冒充实测物理衰减。

## Status After This Planning Task

```text
Environment × elevation path-parameter distribution = Completed
Main-path common-gain/fade model = Completed
Fixed three-NLOS-slot activation model = Completed
Lock-to-amplitude/phase/recovery mapping = Planned / Not started
Reproducible final random generator and QA = Not started
```

No experiment is authorized by this plan.
