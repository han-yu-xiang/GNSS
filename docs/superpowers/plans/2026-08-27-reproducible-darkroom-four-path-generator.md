# Reproducible Environment × Elevation Four-Path Darkroom Generator v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:test-driven-development` for every implementation task and `superpowers:verification-before-completion` before reporting success.

**Goal:** 把四个已经完成并独立 QA 的冻结模型组合成一个可复现、可审计、new-only 的 1 ms 四路径参数生成器。生成器按一个 `environment_class × elevation_band` 请求生成主径槽位 0 和固定 NLOS 槽位 1/2/3，输出用户冻结的七列暗室参数表，并生成完整随机流、统计支持、假设层和文件 hash provenance。

**Architecture:** 采用“immutable generation request → frozen-parent preflight → deterministic seed tree → continuous receiver/common-gain timeline + independent 40 ms path blocks → exact seven-column export → independent auditor”的结构。生成器只消费四个父模型的 CSV/JSON artifact，不重新拟合数据，不读取 Stage0/Stage1/Stage2/Stage3/Stage4、tracking、raw IQ，也不调用 MATLAB/SAGE。公共增益、普通衰落和失锁状态在整个请求时间轴上连续；NLOS 激活、数量和基础路径参数按固定 40 ms 非重叠 block 抽样并在 block 内保持不变；相位按 1 ms Doppler 连续演化。

**Tech Stack:** Python 3.12；NumPy 2.5.1；SciPy 1.18.0；OpenBLAS；标准库 `argparse/csv/json/hashlib/pathlib/dataclasses/enum/gzip/time`; pytest。固定解释器为 `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`，禁止联网安装、升级或复制依赖。

**Spec:** 本计划；`docs/ENVIRONMENT_ELEVATION_PATH_DISTRIBUTION_MODEL_V1_REPORT.md`；`docs/MAIN_PATH_COMMON_GAIN_FADE_MODEL_V1_REPORT.md`；`docs/NLOS_SLOT_ACTIVATION_MODEL_V1_REPORT.md`；`docs/LOCK_AMPLITUDE_PHASE_RECOVERY_MODEL_V1_REPORT.md`；四个冻结 artifact namespace 中的 contract、manifest 和 independent QA。

## Global Constraints

- 当前状态为 `Planned / Not started`。本文只制定实施与 QA 计划，不表示生成器已经实现、运行或验证。
- 本轮以及后续实现均禁止读取 raw IQ、运行 MATLAB、运行 SAGE、启动 batch、处理 20.46 MHz 或改写任何 production/scientific artifact。
- 不修改四个父模型、不重新拟合参数、不覆盖它们的 namespace；父模型只作为 immutable inputs。
- 不写入 `scenes/**/sage_results`、event database partition、production request/manifest、metadata、inventory、tracking 或 telemetry。
- 受保护生产入口 `scripts/sage_pipeline/run_nav_sage_pipeline.m` 必须保持 SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。
- 所有生成请求和生成结果均为 `new_only=true`、`resume_allowed=false`；目标目录存在时 fail closed，不覆盖、不续跑、不自动改名。
- 绝对禁止删除文件。失败或 partial generation artifact 必须原地保留并写 failed/interrupted receipt；下一次尝试使用新的 request/namespace。
- 默认只允许 `EMPIRICAL_CONFIRMED_SUPPORT` 激活模式和 `EMPIRICAL_DIAGNOSTIC_PROXY` 失锁映射模式。强制激活或强制失锁只可作为显式 stress/QA 请求，必须保留 `ASSUMPTION_ONLY` provenance。
- path 0 是仿真参考主径，不保证是物理 LOS，也不保证是四条路径中的最强路径。
- zero-confirmed exposure 不是 LOS；`PRIOR_ONLY` 不是实测验证；`LOCK_BAD` 是接收机 tracking diagnostic，不是物理信号必然消失。
- 相位不是从当前数据拟合得到，必须始终标记 `ASSUMPTION_ONLY_UNIFORM_INITIAL_PLUS_DOPPLER_CONTINUOUS`。
- 当前没有绝对 RF 功率、暗室功率标定、真实硬件失锁深度、路径 lifetime 或 inter-block identity 模型；生成器不得隐含声称已具备这些能力。
- 本计划只新增计划文档，不更新 Engineering/Paper Handoff。只有用户批准后完成真实实现和独立 QA，才根据 Documentation Update Policy 同步状态。

---

## 1. Frozen Parent Baseline

### 1.1 Parent artifacts and independent QA

| Layer | Immutable artifact | SHA-256 | QA artifact SHA-256 | Current status |
|---|---|---:|---:|---|
| Environment × elevation NLOS path distribution | `dataset_generation_logs/channel_modeling/environment_elevation_path_distribution_v1_20260826_r1/model_manifest.json` | `4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c` | `291853d576bf1e0fe4d09641fc0f6c194be7a26a39370546964b41d7d3e1f1aa` | `PASS_WITH_LIMITATIONS` |
| Main/common gain and observable fade | `dataset_generation_logs/channel_modeling/main_path_common_gain_fade_v1_20260826_r4/model_manifest.json` | `6f36dab892622c9b9dc61ecde91fda85ff12ca60eeea4f81fe37760f0acb1e45` | `cfee633b31287fb158af60c61c33ec0e5d69cd26e87bf229696673e66e41882c` | `PASS_WITH_LIMITATIONS` |
| Fixed three-NLOS-slot activation | `dataset_generation_logs/channel_modeling/nlos_slot_activation_v1_20260826_r1/model_manifest.json` | `b47b2a09f9acc5f1ccd65dcf923623dbeea27e3aec3e3e3f04c2e094a3e486d2` | `7dc097938961b0c1cc56a4ef7f583e0e53dd89e57fbc590a8eeeeb7cf86021d3` | `PASS_WITH_LIMITATIONS / READY_FOR_GENERATOR_COMPOSITION=YES` |
| Lock state → amplitude/phase/recovery | `dataset_generation_logs/channel_modeling/lock_amplitude_phase_recovery_v1_20260826_r3/model_manifest.json` | `9eb1847eac27618f80475ceafe62616285a346c5da847afdb0e8f2c5fc63a3ee` | `344022e47631dac874f546d5ec9817203a2b12bab9fb871a51716bae817a70ba` | `PASS_WITH_LIMITATIONS / READY_FOR_GENERATOR_INTEGRATION=YES` |
| Environment lock timing parent | `dataset_generation_logs/channel_modeling/environment_lock_model_v1_20260826_r2/lock_model_manifest.json` | `21c04938cba559b3e042806b093eba82e4e86a44977e95831c715aa03ffc97a5` | inherited through lock-mapping QA | immutable timing input |

The path-model QA was completed before the other composition layers and therefore retained its historical `ready_for_darkroom_generator_integration=NO` flag. That historical flag must not be rewritten. Generator readiness is determined by the current four-parent preflight and their immutable QA artifacts, not by editing an older receipt.

### 1.2 Frozen contracts and parameter files

| Contract/parameter file | SHA-256 |
|---|---:|
| Path `sampling_contract.json` | `48e48bcb4d64c9d0debea74824424573c1b998ac4da10b7804f242d6c3225d38` |
| Gain `main_path_common_gain_fade_model.json` | `a12fa745065ae74dcff5eb2b8746d075a87a1c2d91360273932abf2911a219d3` |
| Gain marginal parameters | `adc790b77e3be3524c27aaa9007270bbfa30c58b68178997c2b009194c1e8221` |
| Gain temporal parameters | `77c383ba4e8a011e5f63bafc24fea1a5b7009144f9ca7cf3453487c6543e24f6` |
| Fade depth/duration parameters | `a181b243e6b3807f9117a6f26fbbb2f7b717a2ca2b842a977b7aa4ae10ee3ef8` |
| Fade entry-rate parameters | `073ab2c9ec7345c1e7715e0ebc5aa9932baa0c12b170378ee1b9f6418ed0b2ab` |
| NLOS activation model | `494f784d0231ab1fc6389d210470b059dd4b1f6e9a2f95c8e3a141da04cc55e2` |
| NLOS slot activation contract | `95c44f6c2b22c4023bb0875dddbf4cd267a18f3e54759dc7d3572ffebddd76e1` |
| Lock/recovery model | `426d657045865ce9b7baa34a1ba361d37d45eb5ce99cc0b7eba7165eda939204` |
| Channel composition contract | `c04e50398e7b1437a5d5eca5cd53ba9173ccdb90fdf25ad174292f3eec8ebab5` |
| Phase policy contract | `4ae11799f32cd1f561f930f7d03f6b91a2a01c29d2e69672ace5bff71ea0095f` |
| Environment lock parameters | `47f0a070053eb6c44daf42a3665c304d3252f9165d297b757084d80865f512bb` |

### 1.3 Frozen reusable-core hashes

The generator may reuse only the validated pure numerical semantics associated with these exact source hashes. A mismatch stops preflight and requires a new generator plan/config revision; it must never silently import a changed helper.

| Pure core | SHA-256 |
|---|---:|
| `path_distribution_core.py` | `5000037f31a0cf9ca59c328bb2e19399827386e522d7fe974367d1f722664b76` |
| `main_path_gain_core.py` | `da831bf0591c3ff9e816a8b12a4d7cd08b0f23f124151ff7ad9298fcb7fbc484` |
| `nlos_slot_activation_core.py` | `371e19362a86dcff3fcc936397cb872d1a5af543b819eea5ede7a281d71c089b` |
| `lock_amplitude_phase_recovery_core.py` | `29e85c4e40f4c30b2551f2a548b520b9f9004b1ac1d68218b576d6fd1563c4ac` |

The generator must add a generator-local common-gain integration adapter. Its purpose is to implement the already-frozen parent design—latent Gaussian AR(1) followed by the selected marginal PPF—while preserving the selected Student-t marginal. It must not use a normal-only `loc + scale*z` approximation when the frozen model family is Student-t.

---

## 2. Architecture Decision

### Recommended: immutable request-driven composition

Use a small immutable generation request containing only the scenario, duration, seed, approved operating modes and output namespace. The runner rehashes the request, all four parent models, all contracts and its own code before generating. This creates one auditable chain from a request SHA to a seven-column table SHA.

Advantages:

- same scientific request and seed reproduce the same scientific rows;
- source/model drift is detected before output creation;
- random streams are isolated by scientific purpose;
- final table remains hardware-facing and compact while sidecars retain support/assumption provenance;
- failed attempts remain immutable and cannot be resumed into a mixed result.

### Rejected: one monolithic script with direct CLI parameters

Direct `--environment --seed --duration` execution has no immutable request hash and makes it easy to omit parent/source receipts. It also weakens replay and auditability.

### Rejected: merge all four parent models into a new mega-model JSON

Copying all parameters creates a second truth source and permits silent drift. The generator config should freeze parent paths/hashes and read them directly.

### Rejected: pre-generate a lookup table for every cell and resample rows

This would replace the fitted continuous distributions with finite empirical lookup samples and would obscure the actual fitted family/copula semantics.

---

## 3. Frozen Generator Contract

### 3.1 Supported condition cells

The exact condition grid is:

```text
environment_class ∈ {
  Urban,
  Special Reflective,
  Mountain/Valley,
  Highway/Open
}

elevation_band ∈ {LOW, MID, HIGH}
```

The final table maps elevation bands to the user-requested `SatelliteID` spelling:

```text
LOW  -> Low
MID  -> Mid
HIGH -> High
```

`SatelliteID` is therefore an elevation-context label in this v1 table, not a GPS PRN identifier. The sidecar retains the canonical `elevation_band` value.

### 3.2 Immutable request schema

Each request must contain at least:

```json
{
  "request_id": "unique execution-attempt identity",
  "simulation_id": "stable scientific simulation identity",
  "generator_id": "darkroom-four-path-generator-v1",
  "environment_class": "Urban",
  "elevation_band": "MID",
  "duration_ms": 10000,
  "master_seed": 20260827,
  "activation_mode": "EMPIRICAL_CONFIRMED_SUPPORT",
  "lock_mapping_mode": "EMPIRICAL_DIAGNOSTIC_PROXY",
  "stress_floor_linear": null,
  "generator_config_relative_path": "configs/channel_modeling/darkroom_four_path_generator_v1.json",
  "generator_config_sha256": "frozen after implementation",
  "expected_output_namespace": "dataset_generation_logs/channel_modeling/darkroom_four_path_generator_v1_runs/<request_id>",
  "new_only": true,
  "resume_allowed": false,
  "gold_labels_used_for_generation": false,
  "raw_iq_read": false,
  "matlab": false,
  "sage": false,
  "batch": false,
  "process_20_46_mhz": false
}
```

Rules:

- `duration_ms` is a positive integer; the output contains exactly `4 × duration_ms` rows.
- `master_seed` is a non-negative integer representable without float conversion.
- `simulation_id` participates in seed derivation; `request_id`, output path and timestamps do not. A fresh retry namespace can therefore reproduce the same scientific sequence exactly.
- v1 fixes `path_parameter_block_ms=40` in the generator config. It is not a request-tunable parameter because the activation support proxy was derived on 40 ms Stage0 windows.
- The final partial block is allowed when `duration_ms` is not divisible by 40; its parameters are sampled once and emitted only for the remaining milliseconds.
- `FORCED_LOCK_LOSS_STRESS` requires `0 < stress_floor_linear < 1`; the default empirical mode requires the field to be null.
- `CONDITIONAL_ACTIVE_STRESS` is permitted only when `request_purpose` is explicitly `QA` or `STRESS`; it is not the default scientific generator mode.
- Request preparation writes a canonical JSON representation and records its SHA-256 outside the JSON. The runner accepts only `--request` plus `--expected-request-sha256`; it never accepts direct environment/seed/output overrides.

### 3.3 Time and block semantics

- Output time step: exactly 1 ms, with `ms=1..duration_ms`.
- NLOS block boundaries: non-overlapping `[1,40]`, `[41,80]`, etc.
- At each block start, independently sample activation state `Z`, conditional path count `K`, K joint path vectors and NLOS initial phases.
- Within a block, NLOS base delay, Doppler and relative amplitude stay fixed.
- Common gain, ordinary fade envelope, lock state/envelope and phase evolve every millisecond and remain continuous across block boundaries.
- Path 0 persists across the complete request. Its initial phase is sampled once and is not reset at NLOS block boundaries.
- NLOS slot identity does not persist across blocks in v1. Even if the same slot is active in adjacent blocks, it is a new block draw and receives a new initial phase. Record `INTER_BLOCK_PATH_IDENTITY_NOT_MODELED`.
- Block activation is independent across blocks. Record `INDEPENDENT_40MS_BLOCK_ASSUMPTION`; do not call it a fitted path birth/death or lifetime model.

### 3.4 Deterministic seed tree

Never use Python's process-randomized `hash()`.

Define:

```python
derive_stream_seed(
    master_seed: int,
    simulation_id: str,
    environment_class: str,
    elevation_band: str,
    scope_id: str,
    stream_name: str,
) -> uint64
```

Algorithm:

1. Serialize the six fields as canonical UTF-8 JSON with sorted keys and no insignificant whitespace.
2. Compute SHA-256.
3. Interpret the first eight digest bytes as an unsigned big-endian 64-bit integer.
4. Pass that integer to `numpy.random.SeedSequence`, then create `numpy.random.Generator(PCG64)`.

Required independent stream names:

```text
common_gain_latent
ordinary_fade_entry
ordinary_fade_depth
ordinary_fade_duration
lock_entry
lock_duration
lock_depth_proxy
lock_recovery_duration
path0_initial_phase
block_activation_occurrence
block_activation_multiplicity
block_nlos_joint_parameters
block_nlos_phase_slot_1
block_nlos_phase_slot_2
block_nlos_phase_slot_3
```

Adding random draws to one stream must not change any other stream. The stream registry and exact names are part of the immutable generator config and manifest.

### 3.5 Normal common-gain process

For the selected cell/parent Student-t marginal and correlation time `tau_s`:

```text
rho_1ms = exp(-0.001 / tau_s)
z[1] ~ Normal(0,1)
z[m] = rho_1ms*z[m-1] + sqrt(1-rho_1ms^2)*epsilon[m]
u[m] = Phi(z[m])
G_normal_db[m] = StudentT_PPF(u[m]; df, loc, scale)
G_normal_linear[m] = 10^(G_normal_db[m]/20)
```

`u` may be clipped only to `nextafter(0,1)` and `nextafter(1,0)` to prevent numerical infinities; no empirical tail clipping is allowed. The selected marginal and `tau_s` source/support status must be recorded.

### 3.6 Ordinary fade process

Use the frozen fade entry-rate, depth and duration parameters:

```text
p_fade_per_ms = 1 - exp(-lambda_fade_per_s / 1000)
D_fade_db ~ frozen lognormal depth model
T_fade_ms = max(1, ceil(1000 * frozen Gamma duration draw))
g_fade_min = 10^(-D_fade_db/20)
```

Because v1 parent fitting did not identify attack/recovery waveform, the generator freezes a transparent composition assumption:

```text
ASSUMPTION_ONLY_ORDINARY_FADE_SHAPE = symmetric raised cosine
```

The first `ceil(T/2)` samples descend from 1 to `g_fade_min`; the remaining samples recover to 1. Exact endpoints, odd-duration split and one-sample event behavior must be unit-tested. Ordinary fades do not overlap; a new fade can enter only when no ordinary fade and no lock/recovery state is active.

If an ordinary fade and lock entry are scheduled for the same millisecond, lock wins. A running ordinary fade is terminated and marked `SUPERSEDED_BY_LOCK`; it does not resume after recovery. This implements the frozen policy `LOCK_ENVELOPE_SUPERSEDES_ORDINARY_FADE_ENVELOPE` without multiplying two untracked depth events.

### 3.7 Receiver lock timeline

The complete request has one environment-conditioned lock state machine:

```text
TRACKED
  -> FADING_TO_LOCK_BAD
  -> LOCK_BAD_HOLD
  -> RECOVERING
  -> TRACKED
```

Rules:

- Entry probability is the exact stored `entry_probability_per_ms` for the requested environment.
- Lock duration is sampled from the frozen environment Gamma model and quantized as `max(20, ceil(seconds*1000))`.
- Entry ramp is `min(20, lock_duration_ms)`; the remaining lock duration is hold.
- Recovery duration is sampled from the frozen environment recovery Gamma model using the same semantics already exercised by the r3 deterministic QA; fallback rows use their explicit `duration_ms`.
- Empirical mode samples a positive lock depth proxy from the frozen observable fade-depth parent. It is not a calibrated hardware loss depth.
- Stress mode uses only the explicit request floor and marks every affected row `ASSUMPTION_ONLY_USER_STRESS_FLOOR`.
- Raised-cosine entry and recovery use the validated r3 core semantics. Exact zero is forbidden in v1; numerical floor remains positive.
- No overlapping lock events; entry trials occur only in `TRACKED` state.
- Successful simulation input has no `INCONCLUSIVE` timeline state. Missing or invalid parameter support fails generation instead of emitting a fabricated physical envelope.

### 3.8 NLOS activation and path parameters

At each 40 ms block:

1. In empirical mode, sample `Z ~ Bernoulli(p_stage4_confirmed_support_active[environment,elevation])`.
2. If `Z=0`, set `K=0` and mask `000`.
3. If `Z=1`, sample `K∈{1,2,3}` from the frozen conditional multiplicity distribution.
4. Draw K conditionally IID joint vectors from the environment Gaussian copula plus requested-cell marginals:
   - `relative_delay_ns`;
   - signed `relative_doppler_hz`;
   - `relative_power_db`, converted by `10^(dB/20)` to linear amplitude ratio.
5. Canonicalize active paths by delay ascending, amplitude descending, Doppler ascending and stable source-draw ID.
6. Apply masks `0→000`, `1→100`, `2→110`, `3→111`.

The dependence model is within each path vector. Cross-path dependence is not fitted; K path vectors are conditionally IID before canonical sorting. Positive relative power dB and amplitudes above 1 remain valid and must not be clipped merely to force path 0 to be strongest.

### 3.9 Phase and amplitude composition

Initial phase:

```text
phi_i[block_start] ~ Uniform(-pi, pi)
```

Evolution:

```text
phi_i[m+1] = wrap_to_pi(phi_i[m] + 2*pi*RelativeDoppler_i*0.001)
```

Path 0 has base `[0 ns, 0 Hz, 1]`. Therefore its phase remains at its request-level initial value unless a future, separately authorized oscillator model is introduced.

At each ms:

```text
G_background[m] = G_normal_linear[m] * G_ordinary_fade[m]
G_effective[m]  = G_background[m] * G_lock[m]

Amplitude_0[m] = G_effective[m]
Amplitude_i[m] = G_effective[m] * Z_i * A_rel_i, i=1,2,3
```

During lock/recovery, `G_ordinary_fade=1` under the supersession rule, while the normal common-gain process remains active. This preserves active NLOS-to-path-0 ratios within each block:

```text
Amplitude_i[m] / Amplitude_0[m] = A_rel_i
```

Lock and recovery never reset physical path phase. During lock hold, diagnostic sidecar may set `phase_observable=false`, but phase still advances mathematically.

### 3.10 Canonical final table

The hardware-facing CSV is exactly:

```text
ms
SatelliteID
NLOSPathID
RelativeDelay
RelativeDoppler
RelativeAmplitude
RelativePhase_rad
```

Semantics:

| Column | Unit/type | Path 0 | Active NLOS | Inactive NLOS |
|---|---|---|---|---|
| `ms` | positive integer | current ms | current ms | current ms |
| `SatelliteID` | `Low/Mid/High` | requested context | requested context | requested context |
| `NLOSPathID` | integer | 0 | 1/2/3 | 1/2/3 |
| `RelativeDelay` | ns | `0` | finite positive draw | blank/null |
| `RelativeDoppler` | Hz | `0` | finite signed draw | blank/null |
| `RelativeAmplitude` | linear amplitude ratio | finite positive dynamic value | finite positive dynamic value | `0` |
| `RelativePhase_rad` | rad in `[-pi,pi)` | finite | finite | blank/null |

CSV nulls are encoded as empty fields, never as the strings `NaN`, `None` or numeric zero. A future hardware adapter that requires numeric placeholders must be separately specified; it may not change this canonical scientific table.

Rows are sorted strictly by `(ms ascending, NLOSPathID ascending)` and use locale-independent decimal formatting. No timestamps or output paths appear in the canonical table, allowing byte-identical replay.

### 3.11 Required sidecars and provenance

The output namespace must contain:

```text
generation_request.json
generation_request.sha256
darkroom_channel_parameters.csv
path_block_catalog.csv
receiver_timeline.csv.gz
random_stream_registry.csv
generation_manifest.json
generation_receipt.json
generation_report.md
independent_qa_result.json
independent_qa_report.md
```

`path_block_catalog.csv` records one row per block/path slot, including base parameters, activation state, K, support status, phase initialization stream and assumption flags.

`receiver_timeline.csv.gz` records one row per ms, including:

```text
simulation_id
ms
environment_class
elevation_band
common_gain_db
common_gain_linear
ordinary_fade_state
ordinary_fade_event_id
ordinary_fade_envelope_linear
lock_state
lock_event_id
lock_envelope_linear
effective_common_gain_linear
phase_observable
gain_support_status
fade_support_status
lock_support_status
recovery_support_status
assumption_flags
```

`random_stream_registry.csv` records stream name, scope ID, derived uint64 seed, derivation algorithm/version and draw count. It must not record mutable NumPy internal state dumps.

Support fields remain separated rather than collapsed into one misleading label:

```text
path_parameter_support_status
occupancy_support_status
multiplicity_support_status
common_gain_support_status
fade_support_status
lock_support_status
recovery_support_status
```

If any required path/multiplicity source is `PRIOR_ONLY`, the affected block must carry `PRIOR_ONLY=true`. Assumption flags are separate, including phase, ordinary-fade shape and inter-block independence.

---

## 4. Planned File Layout

### 4.1 Source/config files

- Create: `configs/channel_modeling/darkroom_four_path_generator_v1.json`
- Create: `scripts/analysis/channel_modeling/darkroom_generator_core.py`
- Create: `scripts/analysis/channel_modeling/prepare_darkroom_generator_request.py`
- Create: `scripts/analysis/channel_modeling/run_darkroom_four_path_generator.py`
- Create: `scripts/analysis/channel_modeling/audit_darkroom_four_path_generator.py`
- Create: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_core.py`
- Create: `scripts/analysis/channel_modeling/tests/test_prepare_darkroom_generator_request.py`
- Create: `scripts/analysis/channel_modeling/tests/test_run_darkroom_four_path_generator.py`
- Create: `scripts/analysis/channel_modeling/tests/test_audit_darkroom_four_path_generator.py`

No parent builder/core file is modified.

### 4.2 Request/output namespaces

```text
dataset_generation_logs/channel_modeling/
  darkroom_four_path_generator_v1_requests/
    <request_id>/
      generation_request.json
      generation_request.sha256

  darkroom_four_path_generator_v1_runs/
    <request_id>/
      ...generated artifacts...
```

Both request and run directories are new-only. A failed request remains where it was written. A retry requires a new `request_id` and output namespace while retaining the same `simulation_id` and `master_seed` when exact replay is desired.

### 4.3 Human-readable report after real implementation and QA

- Create only after real QA: `docs/DARKROOM_FOUR_PATH_RANDOM_GENERATOR_V1_REPORT.md`

---

## Task 1: Freeze Generator Configuration and Request Contracts

**Files:**

- Create: `configs/channel_modeling/darkroom_four_path_generator_v1.json`
- Create: `scripts/analysis/channel_modeling/darkroom_generator_core.py`
- Test: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_core.py`

**Interfaces:**

```python
load_generator_config(path: Path, project_root: Path) -> GeneratorConfig
validate_parent_contracts(config: GeneratorConfig, project_root: Path) -> ParentReceipt
validate_generation_request(payload: Mapping[str, Any], config: GeneratorConfig) -> GenerationRequest
canonical_json_bytes(payload: Mapping[str, Any]) -> bytes
sha256_file(path: Path) -> str
```

- [ ] Write failing tests for all exact parent manifest/contract/QA/core hashes listed in Section 1.
- [ ] Write failing tests for unsupported environments/bands, nonpositive duration, float/string seed, invalid mode combinations, stress mode without explicit floor, and any execution flag enabling raw/MATLAB/SAGE/batch/20.46 MHz.
- [ ] Write path-safety tests rejecting output under `scenes`, `sage_results`, event database, parent model namespaces, `_trash`, project root or an existing directory.
- [ ] Encode the exact 40 ms block size, 1 ms time step, stream registry, output columns, null semantics, unit mapping, parent artifacts and protected pipeline hash in the config.
- [ ] Require the parent QA statuses and preserve every parent limitation; never rewrite parent receipts.
- [ ] Run the focused test and confirm GREEN.

Command after implementation:

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest scripts\analysis\channel_modeling\tests\test_darkroom_generator_core.py -q
```

## Task 2: Implement Immutable Request Preparation

**Files:**

- Create: `scripts/analysis/channel_modeling/prepare_darkroom_generator_request.py`
- Create: `scripts/analysis/channel_modeling/tests/test_prepare_darkroom_generator_request.py`

**CLI:**

```text
--project-root
--config
--request-id
--simulation-id
--environment
--elevation-band
--duration-ms
--master-seed
--activation-mode
--lock-mapping-mode
--stress-floor-linear (stress mode only)
--request-dir
--validate-only
```

- [ ] Write failing tests for canonical request serialization and exact SHA reproduction.
- [ ] Verify request preparation freezes config hash, all parent hashes, backend receipt, expected output path and all no-execution flags.
- [ ] Require request/output directories to be absent; `--validate-only` must create nothing.
- [ ] Reject request ID/path traversal, duplicated scientific fields, output paths outside the declared run root and direct edits that break expected SHA.
- [ ] Emit `generation_request.json` plus a one-line lowercase SHA file only after all checks pass.
- [ ] Verify request preparation never imports/opens raw, tracking, Stage files or any gold table.
- [ ] Run tests and confirm GREEN.

## Task 3: Build Frozen-Artifact Loaders and Common-Gain Integration Adapter

**Files:**

- Modify: `scripts/analysis/channel_modeling/darkroom_generator_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_core.py`

**Interfaces:**

```python
load_path_distribution_artifacts(...) -> FrozenPathModel
load_gain_fade_artifacts(...) -> FrozenGainFadeModel
load_activation_artifacts(...) -> FrozenActivationModel
load_lock_mapping_artifacts(...) -> FrozenLockModel
resolve_cell_support(models, environment, elevation_band) -> CellSupportReceipt
sample_common_gain_process(model, environment, elevation_band, duration_ms, rng) -> CommonGainDraw
```

- [ ] Write tests that load all 12 cells and exactly preserve family names, parameters, copula matrices, support statuses and source scope.
- [ ] Add a regression test proving the common-gain adapter uses Student-t PPF and not `loc + scale*z` when family=`student_t`.
- [ ] Test stationary latent AR(1) recurrence and `rho=exp(-0.001/tau_s)` with deterministic fixtures.
- [ ] Test CDF clipping is numerical-only and all generated dB/linear values remain finite and positive.
- [ ] Test sparse/parent resolution exactly follows stored `parameter_source`; no scene mean or unrecorded fallback is allowed.
- [ ] Keep all parent code/artifacts read-only and run focused tests GREEN.

## Task 4: Implement the Deterministic Random-Stream Registry

**Files:**

- Modify: `scripts/analysis/channel_modeling/darkroom_generator_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_core.py`

**Interfaces:**

```python
derive_stream_seed(...) -> int
make_rng(stream_key: StreamKey) -> np.random.Generator
register_stream(registry: StreamRegistry, stream_key: StreamKey, draw_count: int) -> None
```

- [ ] Test exact SHA-256/uint64 seed vectors for Unicode environment names, slashes in `Highway/Open`, and all three bands.
- [ ] Test same scientific identity/seed reproduces exact streams across processes.
- [ ] Test request ID, output namespace and timestamps do not change scientific streams.
- [ ] Test changing phase streams cannot change activation, path, gain, fade or lock draws.
- [ ] Test changing one block cannot change earlier or later block streams.
- [ ] Reject duplicate stream registration with inconsistent scope/draw count.

## Task 5: Implement Continuous Common-Gain and Ordinary-Fade Timeline

**Files:**

- Modify: `scripts/analysis/channel_modeling/darkroom_generator_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_core.py`

**Interfaces:**

```python
sample_common_gain_timeline(...) -> CommonGainTimeline
sample_ordinary_fade_schedule(...) -> list[FadeEvent]
ordinary_fade_envelope(event: FadeEvent) -> NDArray[np.float64]
compose_background_gain(...) -> NDArray[np.float64]
```

- [ ] Write exact one-/two-/odd-/even-duration raised-cosine endpoint and monotonicity tests.
- [ ] Test `p=1-exp(-lambda/1000)`, no overlap, no event starts outside eligible state and deterministic event IDs.
- [ ] Test depth lognormal and duration Gamma parameter decoding against stored JSON parameter fields.
- [ ] Test gain marginal quantiles and latent autocorrelation with deterministic 4096-draw/direct-latent diagnostics using frozen Monte Carlo tolerances.
- [ ] Test all envelopes are in `(0,1]`, common gain is positive, and no empirical tail clipping occurs.
- [ ] Record ordinary-fade shape as `ASSUMPTION_ONLY`; never relabel it as measured waveform.

## Task 6: Implement Lock/Recovery Timeline and Conflict Policy

**Files:**

- Modify: `scripts/analysis/channel_modeling/darkroom_generator_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_core.py`

**Interfaces:**

```python
sample_lock_schedule(...) -> list[LockEvent]
render_lock_timeline(...) -> LockTimeline
resolve_fade_lock_conflicts(...) -> ReceiverEnvelopeTimeline
```

- [ ] Test entry probability, minimum 20 ms lock duration, 20 ms entry ramp, Gamma duration and recovery sampling against frozen r3 deterministic fixtures.
- [ ] Test state transition legality and no overlapping lock events.
- [ ] Test empirical proxy depth remains positive and stress mode requires an explicit positive floor.
- [ ] Test ordinary fade is terminated on lock entry, lock wins exact same-ms ties and the fade never resumes silently.
- [ ] Test lock/recovery does not reset phase and sets `phase_observable=false` only where required by the diagnostic policy.
- [ ] Test missing/invalid lock parameters fail closed instead of creating `INCONCLUSIVE` physical rows.

## Task 7: Implement 40 ms Activation, K, Joint Paths and Slot Mapping

**Files:**

- Modify: `scripts/analysis/channel_modeling/darkroom_generator_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_core.py`

**Interfaces:**

```python
sample_block_activation(...) -> BlockActivation
sample_joint_nlos_paths(...) -> list[BasePathDraw]
canonicalize_block_paths(...) -> tuple[SlotState, SlotState, SlotState]
build_path_block_catalog(...) -> list[BlockPathRecord]
```

- [ ] Test exact occupancy and conditional-K parameter use for all 12 cells.
- [ ] Test masks `000/100/110/111`, deterministic sorting and K conditionally IID joint draws.
- [ ] Test Gaussian-copula covariance, selected cell marginal families and dB-to-linear amplitude conversion against parent QA fixtures.
- [ ] Test active amplitudes above 1 remain unchanged.
- [ ] Test inactive amplitude=0 and delay/Doppler/phase=null; reject fake numeric-zero propagation fields.
- [ ] Test `PRIOR_ONLY`, `EXPOSURE_ONLY_ZERO_CONFIRMED`, sparse and parent-source statuses propagate without being interpreted as LOS.
- [ ] Test the final partial 40 ms block and `CONDITIONAL_ACTIVE_STRESS` restriction to QA/stress purposes.

## Task 8: Implement Phase Evolution and Canonical Seven-Column Export

**Files:**

- Modify: `scripts/analysis/channel_modeling/darkroom_generator_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_core.py`

**Interfaces:**

```python
initialize_phases(...) -> PhaseState
advance_phase_1ms(phi_rad: float, doppler_hz: float) -> float
compose_millisecond_rows(...) -> tuple[FinalRow, FinalRow, FinalRow, FinalRow]
write_canonical_parameter_csv(path: Path, rows: Iterable[FinalRow]) -> str
```

- [ ] Test path-0 `[0 ns,0 Hz,1]` base and dynamic amplitude composition.
- [ ] Test exact phase recurrence, wrap interval `[-pi,pi)`, no lock reset, path-0 continuity across request and NLOS reset only at block boundaries.
- [ ] Test active NLOS amplitude ratio to path 0 remains equal to the block base amplitude ratio to numerical tolerance.
- [ ] Test exactly four ordered rows per ms and exact `Low/Mid/High` mapping.
- [ ] Test inactive CSV fields are empty and no `NaN/None/null` text leaks into the canonical table.
- [ ] Freeze locale-independent float formatting and an exact golden-byte fixture.

## Task 9: Implement the New-Only Runner and Receipts

**Files:**

- Create: `scripts/analysis/channel_modeling/run_darkroom_four_path_generator.py`
- Create: `scripts/analysis/channel_modeling/tests/test_run_darkroom_four_path_generator.py`

**CLI:**

```text
--request <absolute generation_request.json>
--expected-request-sha256 <64 lowercase/uppercase hex accepted, normalized for comparison>
--validate-only (default behavior)
--generate --confirm-darkroom-generation (both required for writes)
```

- [ ] Write rejection tests for wrong request SHA, tampering, changed config/parent/core/pipeline hash, wrong backend, existing output, forbidden namespace, resume, raw/MATLAB/SAGE/batch flags and unsupported cell.
- [ ] Ensure validation-only displays environment, band, duration, seed, row count, parent hashes, support statuses and target namespace without creating any file.
- [ ] Write a task-level lock under the generator request root so only one generator run writes at a time; stale lock handling must fail and require human review, not auto-delete.
- [ ] During execution, write progress/heartbeat by completed 40 ms blocks and preserve failed/interrupted artifacts.
- [ ] Generate files in deterministic order; write `generation_manifest.json` only after data/sidecars close successfully; hash every output.
- [ ] Receipt records Python executable/hash, Python/NumPy/SciPy/OpenBLAS versions, start/end UTC, exit state, request/config/parent/code hashes, row/block counts, runtime, peak memory and output hashes.
- [ ] Runner stops after one request and never starts another simulation automatically.

## Task 10: Implement an Independent Auditor

**Files:**

- Create: `scripts/analysis/channel_modeling/audit_darkroom_four_path_generator.py`
- Create: `scripts/analysis/channel_modeling/tests/test_audit_darkroom_four_path_generator.py`

**Interfaces:**

```python
audit_generation(project_root: Path, request_path: Path, run_dir: Path) -> AuditResult
```

- [ ] Auditor must not import the runner or call its generation function. It may share only immutable schema constants; all counts, hashes, equations and state transitions are independently recomputed.
- [ ] Add tamper tests for every canonical/sidecar hash, row reorder, duplicate/missing path row, altered phase, altered amplitude ratio, invalid lock transition, wrong support status and hidden non-null inactive fields.
- [ ] Recompute request/config/parent/core/pipeline hashes and verify the output namespace is the exact request target.
- [ ] Verify `duration_ms × 4` rows, ms/path uniqueness, units/domains, path-0 semantics, block constancy, phase recurrence and composition equations.
- [ ] Verify support/assumption flags and prove no Stage/raw/tracking/production artifact was opened by generation.
- [ ] Verify receipt/progress accounting and no failed run is accepted.
- [ ] Emit the fixed gates in Section 5.

## Task 11: Run Static, Regression and Reproducibility QA After User Approval

This task is explicitly deferred until the user approves this plan and Tasks 1–10 are implemented.

- [ ] Run Python compilation for all four new scripts and the core.
- [ ] Run all new focused tests.
- [ ] Run the complete existing channel-modeling regression suite to prove parent behavior remains intact.
- [ ] Verify the protected production SHA.
- [ ] Run `git diff --check` only on scoped new/updated files.
- [ ] Create a deterministic 12-cell QA matrix using new-only QA request/run namespaces:
  - one empirical end-to-end structural request per cell;
  - one internal `CONDITIONAL_ACTIVE_STRESS` draw audit per cell to exercise active path generation even where empirical occupancy yields no active block;
  - 4096 direct distribution/activation draws per cell for quantitative parent-contract checks;
  - deterministic state-machine fixtures for all four environments.
- [ ] Run the independent auditor on every QA output.
- [ ] Re-run the same pure scientific request twice in isolated test namespaces and require byte-identical canonical table, block catalog and receiver timeline after excluding receipt timestamps.
- [ ] Change only `master_seed` and require schema/counts unchanged but at least one scientific row changed.
- [ ] Change only phase stream in a controlled fixture and require all non-phase scientific values unchanged.

Planned commands:

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m py_compile `
  scripts\analysis\channel_modeling\darkroom_generator_core.py `
  scripts\analysis\channel_modeling\prepare_darkroom_generator_request.py `
  scripts\analysis\channel_modeling\run_darkroom_four_path_generator.py `
  scripts\analysis\channel_modeling\audit_darkroom_four_path_generator.py

& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  scripts\analysis\channel_modeling\tests\test_darkroom_generator_core.py `
  scripts\analysis\channel_modeling\tests\test_prepare_darkroom_generator_request.py `
  scripts\analysis\channel_modeling\tests\test_run_darkroom_four_path_generator.py `
  scripts\analysis\channel_modeling\tests\test_audit_darkroom_four_path_generator.py -q

& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  scripts\analysis\channel_modeling\tests -q

Get-FileHash 'E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m' -Algorithm SHA256
```

Expected protected hash remains:

```text
BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C
```

## Task 12: Publish the Generator Report and Synchronize Handoffs After Real QA

**Files after successful execution only:**

- Create: `docs/DARKROOM_FOUR_PATH_RANDOM_GENERATOR_V1_REPORT.md`
- Modify if engineering facts changed: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Modify only if a bounded new research fact is established: `docs/GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`

- [ ] Report all parent/request/config/source/output hashes, exact schema, QA matrix, deterministic replay hashes, support classes and assumptions.
- [ ] Mark the generator `Implemented` only after code/tests; mark it `Validated` only after independent QA passes.
- [ ] Never write that a calibrated absolute-power channel model, physical LOS/NLOS occurrence law, path lifetime model or hardware lock-loss model has been completed.
- [ ] Keep `PAPER_WORKSPACE_INDEX.md` unchanged unless the paper asset structure itself changes.

---

## 5. Fixed QA and Acceptance Gates

The independent auditor must emit:

```text
REQUEST_AND_CONFIG_HASH_GATE = PASS/FAIL
PARENT_MODEL_PROVENANCE_GATE = PASS/FAIL
BACKEND_AND_CODE_HASH_GATE = PASS/FAIL
DETERMINISTIC_STREAM_GATE = PASS/FAIL
COMMON_GAIN_AND_FADE_GATE = PASS_WITH_LIMITATIONS/FAIL
LOCK_STATE_AND_RECOVERY_GATE = PASS_WITH_LIMITATIONS/FAIL
NLOS_ACTIVATION_AND_PATH_GATE = PASS_WITH_LIMITATIONS/FAIL
PHASE_CONTINUITY_GATE = PASS/FAIL
FINAL_TABLE_SCHEMA_GATE = PASS/FAIL
BLOCK_AND_TIMELINE_CONSISTENCY_GATE = PASS/FAIL
PRIOR_AND_ASSUMPTION_PROVENANCE_GATE = PASS/FAIL
NAMESPACE_AND_OUTPUT_HASH_GATE = PASS/FAIL
REPRODUCIBILITY_GATE = PASS/FAIL
INDEPENDENT_GENERATOR_QA = PASS_WITH_LIMITATIONS/FAIL
READY_FOR_DARKROOM_PARAMETER_EXPORT = YES/NO
```

`READY_FOR_DARKROOM_PARAMETER_EXPORT=YES` requires every hard gate PASS and permits only export of this bounded relative four-path parameter model. It does not mean hardware realism, absolute power calibration or universal environment statistics are validated.

Expected `PASS_WITH_LIMITATIONS` reasons even when successful:

- sparse and inherited environment×elevation cells, including `PRIOR_ONLY` cells;
- occupancy is Stage4-confirmed-support proxy, not physical multipath probability;
- ordinary-fade waveform is an explicit composition assumption;
- phase initialization is an explicit assumption;
- lock depth is receiver-diagnostic proxy, not hardware-calibrated attenuation;
- NLOS blocks are independent 40 ms draws without path lifetime/inter-block identity;
- path 0 is a reference slot, not guaranteed physical LOS or strongest path;
- all amplitudes are relative, not calibrated absolute RF power.

Any hard-gate failure freezes that request/run as an immutable failed experiment. Scientific or schema changes require `darkroom-four-path-generator-v2` and a new plan/config/namespace; v1 is never retuned in place.

---

## 6. Completion Boundary

If this plan is later implemented and all QA gates pass, the project will have a reproducible generator for:

```text
one environment × one elevation context × one seed × one duration
  -> continuous common-gain/fade/lock timeline
  -> independent 40 ms NLOS activation/path blocks
  -> four rows per millisecond
  -> delay [ns], Doppler [Hz], amplitude [linear], phase [rad]
```

It will not yet provide:

- calibrated absolute transmit/receive power;
- a guarantee that generated lock events cause a specific darkroom receiver to lose lock;
- a fitted physical LOS-state process;
- event-level satellite trajectory or changing elevation inside one request;
- fitted path lifetime or smooth NLOS identity across blocks;
- antenna/receiver hardware transfer functions;
- waveform synthesis or RF playback control.

Those capabilities, if needed, require separate user decisions and versioned follow-on work.

## 7. Approval Boundary

This planning task stops after this document is reviewed. No generator/config/request/output namespace is created, no test is run, and no model is sampled until the user explicitly approves implementation.

After approval, the authorized sequence is:

```text
Tasks 1–10 implementation with TDD
  -> static + complete regression tests
  -> freeze generator config/code hashes
  -> prepare immutable 12-cell QA requests
  -> validation-only preflight
  -> execute Python-only QA generations
  -> independent QA
  -> report and handoff synchronization
```

No MATLAB, SAGE, raw IQ, batch or 20.46 MHz work is part of that sequence.

