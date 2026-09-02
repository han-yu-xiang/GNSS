# Darkroom Environment × Signal-Quality Paired Generator v2.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不修改 v2.1 及任何冻结父模型的前提下，为 Urban、Special Reflective、Mountain/Valley、Highway/Open 四类环境生成成对的 `GOOD_TRACKED_BASELINE` 与 `POOR_CONDITIONAL` 暗室参数表；每张表同时包含 Low/Mid/High 和固定 path 0–3，最终形成 8 张表、24 个环境×仰角×质量条件单元。

**Architecture:** 新增独立 v2.2 quality-profile layer，将“路径参数随机流”和“信号质量随机流”解耦。每个环境的 Good/Poor request 共享 `pairing_id`、路径参数、初相和基础 common-gain 随机流；Poor 仅额外叠加一个按环境参数条件生成的完整衰落/失锁/恢复包络。canonical 七列表保持不变，质量状态、参数来源和支持级别写入独立 sidecar；所有 request/run 均 immutable、new-only、可复现。

**Tech Stack:** Python 3.12.9；NumPy 2.5.1；SciPy 1.18.0；OpenBLAS 0.3.33.112.0；标准库 `argparse/csv/gzip/hashlib/json/pathlib/dataclasses/enum/time`；pytest。固定解释器为 `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`。

**Spec:** 用户于 2026-08-27 批准的“4环境×3仰角×2质量模式”设计；`docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` Sections 52–60；`configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2_1.json`；冻结父模型报告 `docs/ENVIRONMENT_ELEVATION_PATH_DISTRIBUTION_MODEL_V1_REPORT.md`、`docs/MAIN_PATH_COMMON_GAIN_FADE_MODEL_V1_REPORT.md`、`docs/ENVIRONMENT_CONDITIONED_LOCK_MODEL_V1_REPORT.md`、`docs/LOCK_AMPLITUDE_PHASE_RECOVERY_MODEL_V1_REPORT.md`。

## Global Constraints

- 本文状态为 `Planned / Not started`。创建本文不表示 v2.2 已实现、8 张参数表已生成或全环境 QA 已通过。
- v2.1 配置、源码、request、preview、QA 和 hash 全部作为 immutable parent 保留；不得覆盖、改名、静默修正或复用其输出 namespace。
- v2.2 必须重新验证并冻结以下父级 SHA-256：path model manifest=`4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c`；gain model manifest=`6f36dab892622c9b9dc61ecde91fda85ff12ca60eeea4f81fe37760f0acb1e45`；environment lock model manifest=`21c04938cba559b3e042806b093eba82e4e86a44977e95831c715aa03ffc97a5`；lock/recovery composition manifest=`9eb1847eac27618f80475ceafe62616285a346c5da847afdb0e8f2c5fc63a3ee`。
- 不修改 `scripts/sage_pipeline/run_nav_sage_pipeline.m`；其受保护 SHA-256 必须保持 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。
- 禁止读取 raw IQ、运行 MATLAB、运行 SAGE、启动 production/batch、处理 20.46 MHz，或写入 `scenes/**/sage_results`。
- 不修改 frozen path/gain/lock/recovery 模型、event database、metadata、inventory、production manifest、旧 generator artifact 或旧 QA。
- v2.2 request/run 必须 `new_only=true`、`resume_allowed=false`；目标目录存在即 fail closed，不删除、不覆盖、不 resume。
- canonical CSV 七列和顺序保持：`ms,SatelliteID,NLOSPathID,RelativeDelay,RelativeDoppler,RelativeAmplitude,RelativePhase_rad`。
- 每个 ms 严格输出 `Low path0–3 → Mid path0–3 → High path0–3`，共 12 行。
- NLOS 1/2/3 始终激活且 `RelativeAmplitude>0`；这是条件性四路径仿真合同，不是实测多径发生率结论。
- path 0 不是 physical LOS 声明。其基础参数为 `[0 ns, 0 Hz, amplitude base 1]`，输出幅度受 common gain 和 quality envelope 共同调制。
- 相位仍为外加假设：初相 `Uniform(-pi,pi)`，随后按 Doppler 每 1 ms 连续递推；失锁/恢复不重置相位。
- `POOR_CONDITIONAL` 是条件性 receiver-diagnostic impairment，不是硬件标定的物理失锁模型，也不代表绝对 RF 功率或固定 dB 衰减。
- 在没有联合训练证据前冻结条件独立近似：路径 delay/Doppler/latent relative amplitude 不因 Good/Poor 重拟合；质量模式只改变公共幅度包络和相位可观测 sidecar。
- Low/Mid/High 的质量事件时刻使用独立 band-keyed 随机流；记录 `INTER_SATELLITE_QUALITY_EVENT_CORRELATION_NOT_MODELED`。
- 8 张表是 4 个环境×2个质量模式；13 个 scene_id 只作为环境模型来源标签，不生成 26 个伪装成独立拟合模型的结果。

---

## 1. Frozen v2.2 Scientific Contract

### 1.1 Environment and output matrix

固定环境顺序：

```text
Urban
Special Reflective
Mountain/Valley
Highway/Open
```

冻结的 source-scene provenance：

| Environment | Source scene IDs |
|---|---|
| Urban | `F1023_V70_D0120_P1`, `F1023_V70_D0120_P5`, `F1023_V70_D0120_P7`, `F1023_V70_D0120_P8`, `F1023_V70_D0122_P1`, `F1023_v50_D0127_P1` |
| Special Reflective | `F1023_V70_D0120_P9`, `F1023_V70_D0122_P2` |
| Mountain/Valley | `F1023_V70_D0117_P2`, `F1023_V70_D0117_P4`, `F1023_v90_D0117_P7` |
| Highway/Open | `F1023_V120_D0121_P2`, `F1023_V80_D0117_P8` |

这些 scene IDs 只记录环境模型的数据来源；request 不得选择某个 scene 后声称生成了 scene-specific distribution。

冻结的 path-support 标记：

| Environment | LOW | MID | HIGH |
|---|---|---|---|
| Urban | `PRIOR_ONLY` | `DATA_SUPPORTED_WITH_GROUPED_VALIDATION` | `DATA_SUPPORTED_WITH_GROUPED_VALIDATION` |
| Special Reflective | `DATA_SUPPORTED_WITH_GROUPED_VALIDATION` | `PRIOR_DOMINANT` | `PRIOR_DOMINANT` |
| Mountain/Valley | `SPARSE_PARTIAL_POOLING` | `SPARSE_PARTIAL_POOLING` | `SPARSE_PARTIAL_POOLING` |
| Highway/Open | `PRIOR_ONLY` | `SPARSE_PARTIAL_POOLING` | `PRIOR_DOMINANT` |

冻结的 environment lock evidence：Urban 16 events、Special Reflective 7、Mountain/Valley 23、Highway/Open 2；Highway/Open 的 lock model 必须保留 `PRIOR_DOMINANT/PARTIAL_POOLING_REQUIRED`，不得升级为 direct-data support。

固定质量顺序：

```text
GOOD_TRACKED_BASELINE
POOR_CONDITIONAL
```

固定仰角顺序：

```text
LOW -> Low
MID -> Mid
HIGH -> High
```

因此 pilot matrix 恰有 8 个 immutable request，每个 request 输出三种仰角，总计 24 个逻辑条件单元。

### 1.2 Paired-comparison semantics

同一环境的 Good/Poor request 必须共享：

```text
pairing_id
master_seed
40 ms NLOS block parameters
path 0 initial phase
NLOS initial phases
base common-gain process
Low/Mid/High band stream keys
```

Poor 独有：

```text
quality-event placement stream
lock-duration stream
recovery-duration stream
depth-proxy stream
quality envelope
phase_observable=false interval
```

配对 QA 必须证明 Good/Poor 的 `RelativeDelay`、`RelativeDoppler`、latent NLOS amplitude、初相和 base common gain 逐元素一致；最终 `RelativeAmplitude` 只能因 quality envelope 不同。

### 1.3 GOOD_TRACKED_BASELINE

Good 是“跟踪稳定基线”，不是绝对高 C/N0 或标定 RF 功率：

```text
quality_state = TRACKED_GOOD
quality_event_count_per_band = 0
quality_envelope_linear = 1
phase_observable = true
ordinary_fade_event_process = disabled for paired quality experiment
effective_common_gain = base_common_gain
```

base common gain 仍来自冻结的 environment×elevation common-gain 模型，因此保留正常相对幅度起伏。

### 1.4 POOR_CONDITIONAL

Poor 是“至少包含一个完整差质量事件的条件性片段”：

```text
quality_event_count_per_band = 1
entry_ramp_ms = min(20, lock_duration_ms)
state sequence = FADING_TO_LOCK_BAD -> LOCK_BAD_HOLD -> RECOVERING
depth source = existing observable-fade parent proxy
lock duration source = existing environment lock model
recovery source = existing environment recovery model or its frozen parent
quality envelope shape = existing raised-cosine entry/recovery
phase_observable = false throughout the event sequence
phase_internal_state = continuous, no reset
depth_db = max(0, sampled_observable_fade_depth_db)
floor_linear = max(1e-12, min(1, 10^(-depth_db/20)))
```

Poor 模式不使用 empirical entry probability 判断“是否发生”，因为该 request 已经条件在差质量事件存在；必须记录：

```text
ENTRY_PROBABILITY_NOT_USED_CONDITIONAL_POOR_MODE
CONDITIONAL_EVENT_NOT_OCCURRENCE_RATE
HARDWARE_LOCK_LOSS_CALIBRATED_FALSE
```

事件在每个 band 内独立确定性放置。固定前后保护区：

```text
pre_event_guard_ms = 100
post_event_guard_ms = 100
```

如果抽取的 `lock_duration_ms + recovery_duration_ms + 200` 超出 request duration，必须以 `QUALITY_EPISODE_DOES_NOT_FIT` fail closed；不得截断、缩短、补零或换 seed 后静默继续。

### 1.5 Amplitude and phase equations

对 path 0：

```text
A_0[m] = G_base[m] * Q[m]
```

对 NLOS slot i=1,2,3：

```text
A_i[m] = G_base[m] * Q[m] * A_rel_i[block]
```

其中：

```text
G_base[m] > 0
Q[m] in (0,1]
A_rel_i[block] > 0
```

因此 canonical 中 path 0 和三条 NLOS 的幅度始终有限且严格大于零。

相位递推：

```text
phi_i[m+1] = wrap_to_pi(phi_i[m] + 2*pi*RelativeDoppler_i*0.001)
```

path 0 的 RelativeDoppler 为 0，因此其内部相位保持初值；Poor 期间只改变 `phase_observable`，不改变 canonical phase recurrence。

### 1.6 Pilot duration and seed

受控 pilot 固定：

```text
duration_ms = 20000
master_seed = 20260827
Urban pairing_id = urban-quality-pair-20260827
Special Reflective pairing_id = special-reflective-quality-pair-20260827
Mountain/Valley pairing_id = mountain-valley-quality-pair-20260827
Highway/Open pairing_id = highway-open-quality-pair-20260827
```

20 s pilot 用于容纳当前环境 lock-duration 分布的典型长事件并执行完整恢复 QA；若任一抽样事件仍无法完整放入，整个对应 request fail closed。本 pilot 不是最终暗室回放时长；更长输出必须在 pilot QA 后另建 immutable request。

---

## 2. File and Namespace Design

### 2.1 New files

```text
configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2_2.json

scripts/analysis/channel_modeling/darkroom_quality_profile_v2_2.py
scripts/analysis/channel_modeling/darkroom_generator_v2_2_core.py
scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_2_request.py
scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_2_matrix.py
scripts/analysis/channel_modeling/run_darkroom_generator_v2_2.py
scripts/analysis/channel_modeling/audit_darkroom_generator_v2_2.py

scripts/analysis/channel_modeling/tests/test_darkroom_quality_profile_v2_2.py
scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_2_core.py
scripts/analysis/channel_modeling/tests/test_prepare_darkroom_generator_v2_2_request.py
scripts/analysis/channel_modeling/tests/test_prepare_darkroom_generator_v2_2_matrix.py
scripts/analysis/channel_modeling/tests/test_run_darkroom_generator_v2_2.py
scripts/analysis/channel_modeling/tests/test_audit_darkroom_generator_v2_2.py
```

### 2.2 New-only namespaces

```text
dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_requests/
dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/
dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices/
```

Matrix ID：

```text
environment_quality_pair_20s_v2_2_20260827
```

每个 request/run ID 必须包含 normalized environment、quality mode、duration 和版本，不得引用 v2.1 run directory。

### 2.3 Output artifacts per run

```text
generation_request.json
generation_request.sha256
darkroom_channel_parameters.csv
receiver_quality_timeline.csv.gz
quality_event_catalog.csv
path_block_catalog.csv
path_slot_timeline.csv.gz
random_stream_registry.csv
support_summary.json
generation_manifest.json
generation_receipt.json
generation_report.md
independent_qa_result.json
independent_qa_report.md
```

`receiver_quality_timeline.csv.gz` 固定字段：

```text
simulation_id
pairing_id
ms
elevation_band
SatelliteID
quality_mode
base_common_gain_db
base_common_gain_linear
quality_state
quality_event_id
quality_envelope_linear
effective_common_gain_linear
phase_observable
quality_depth_source
quality_duration_source
quality_recovery_source
quality_support_status
assumption_flags
```

`quality_event_catalog.csv` 固定字段：

```text
simulation_id
pairing_id
elevation_band
SatelliteID
quality_mode
quality_event_id
event_start_ms
entry_ramp_ms
lock_bad_hold_ms
recovery_duration_ms
event_end_ms
floor_linear
depth_source
duration_source
recovery_source
support_status
complete_event
```

---

## 3. Public Interfaces

### 3.1 Quality profile core

`darkroom_quality_profile_v2_2.py` must expose:

```python
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import numpy as np

GOOD_TRACKED_BASELINE = "GOOD_TRACKED_BASELINE"
POOR_CONDITIONAL = "POOR_CONDITIONAL"

@dataclass(frozen=True)
class QualityProfileRequest:
    simulation_id: str
    pairing_id: str
    environment_class: str
    elevation_band: str
    duration_ms: int
    master_seed: int
    quality_mode: str
    pre_event_guard_ms: int = 100
    post_event_guard_ms: int = 100

@dataclass(frozen=True)
class QualityTimelineResult:
    states: tuple[str, ...]
    event_ids: tuple[str | None, ...]
    envelope_linear: np.ndarray
    phase_observable: tuple[bool, ...]
    event_catalog: tuple[dict[str, Any], ...]
    support_status: str

generate_quality_timeline(
    request: QualityProfileRequest,
    frozen_models: Any,
    random_stream_registry: list[dict[str, Any]],
) -> QualityTimelineResult
```

The implementation must use the parent lock/recovery/depth distributions and the existing endpoint-preserving raised-cosine helper; it must not call the current v2 adapter path that hardcodes `stress_floor_linear=None`.

### 3.2 Generator core

`darkroom_generator_v2_2_core.py` must expose:

```python
@dataclass(frozen=True)
class GenerationV22Request:
    request_id: str
    simulation_id: str
    pairing_id: str
    environment_class: str
    elevation_bands: tuple[str, ...]
    duration_ms: int
    master_seed: int
    quality_mode: str
    output_namespace: str

@dataclass(frozen=True)
class V22SimulationResult:
    final_rows: tuple[dict[str, Any], ...]
    receiver_quality_rows: tuple[dict[str, Any], ...]
    quality_event_rows: tuple[dict[str, Any], ...]
    path_block_rows: tuple[dict[str, Any], ...]
    path_slot_rows: tuple[dict[str, Any], ...]
    random_stream_rows: tuple[dict[str, Any], ...]
    support_summary: dict[str, Any]

validate_v22_request(payload: Mapping[str, Any], config: Any) -> GenerationV22Request

generate_v22_simulation(
    request: GenerationV22Request,
    config: Any,
    frozen_models: Any,
) -> V22SimulationResult
```

Base stream derivation must use `pairing_id` for path blocks, phases and common gain; quality-event streams must include `quality_mode` so Poor-only draws cannot perturb paired base streams.

---

## 4. Implementation Tasks

### Task 1: Freeze v2.2 config and parent provenance

**Files:**
- Create: `configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2_2.json`
- Create: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_2_core.py`

**Interfaces:**
- Consumes: v2.1 config SHA `55befd54988b1aa8838e10a02deae7126305156013283ad52a8c449731ac5814`; v2.1 core SHA `a2205bb43698e6c27f2e31a09e532a4cbafd10cafda04b69390d081d959e6a56`.
- Produces: frozen v2.2 schema, mode names, output roots and parent hashes.

- [ ] **Step 1:** Write a failing schema test requiring version `2.2.0`, both quality modes, all four environments, all three bands, 12 rows/ms, all-positive NLOS and exact seven columns.
- [ ] **Step 2:** Run `& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_2_core.py -q`; expect failure because the v2.2 config/core do not exist.
- [ ] **Step 3:** Create the v2.2 config with parent v2.1 hashes, model-manifest hashes, quality contracts, 100 ms guards, one conditional event per band, positive floor `1e-12`, request/run roots and forbidden-execution flags.
- [ ] **Step 4:** Add config-loader scaffolding to the core test fixture and verify incorrect parent hashes, wrong environment order, missing quality modes and a non-10.23 MHz sample rate fail closed.
- [ ] **Step 5:** Re-run the focused test; expect schema tests PASS.

### Task 2: Implement deterministic Good/Poor quality timelines with TDD

**Files:**
- Create: `scripts/analysis/channel_modeling/darkroom_quality_profile_v2_2.py`
- Create: `scripts/analysis/channel_modeling/tests/test_darkroom_quality_profile_v2_2.py`

**Interfaces:**
- Consumes: `QualityProfileRequest`, frozen `lock_models` and `fade_models`, parent raised-cosine semantics.
- Produces: `QualityTimelineResult` with exact per-ms states/envelopes and event catalog.

- [ ] **Step 1:** Write tests proving Good emits exactly `duration_ms` `TRACKED_GOOD` states, no event rows, all-one envelope and all-true phase observability.
- [ ] **Step 2:** Write tests with deterministic synthetic distributions proving Poor emits exactly one complete `FADING_TO_LOCK_BAD -> LOCK_BAD_HOLD -> RECOVERING` event, positive envelope floor, exact endpoints and false phase observability only inside the event.
- [ ] **Step 3:** Write tests proving Poor fails with `QUALITY_EPISODE_DOES_NOT_FIT` rather than truncating an overlong event.
- [ ] **Step 4:** Write tests proving Low/Mid/High use distinct quality stream seeds and repeated execution with the same request is byte-deterministic.
- [ ] **Step 5:** Run the new test file; expect failures because the module does not exist.
- [ ] **Step 6:** Implement the dataclasses, mode validation, deterministic stream derivation, duration/recovery/depth sampling, valid-start sampling, raised-cosine envelope and support provenance.
- [ ] **Step 7:** Run the new test file; expect all tests PASS.

### Task 3: Compose v2.1 all-positive paths with v2.2 paired quality

**Files:**
- Create: `scripts/analysis/channel_modeling/darkroom_generator_v2_2_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_2_core.py`

**Interfaces:**
- Consumes: v2.1 `_sample_all_active_block` scientific semantics, v2.2 quality timeline, frozen model loader.
- Produces: `GenerationV22Request`, `V22SimulationResult`, canonical formatter and all sidecar rows.

- [ ] **Step 1:** Add failing tests for exact 12-row/ms ordering, all-positive NLOS, path0 base delay/Doppler, 40 ms block constancy and phase recurrence.
- [ ] **Step 2:** Add a paired Good/Poor test asserting exact equality of delay, Doppler, latent amplitude, base common gain and phase, with final-amplitude differences equal to the Poor quality envelope.
- [ ] **Step 3:** Add a test that canonical CSV contains no environment/quality columns while sidecars contain both `quality_mode` and support provenance.
- [ ] **Step 4:** Implement config loading, request validation, paired random-stream derivation, base common-gain sampling, v2.1 all-active block reuse, quality composition and exact row formatting.
- [ ] **Step 5:** Add support flags for the two exact path `PRIOR_ONLY` cells (`Urban|LOW`, `Highway/Open|LOW`) and all sparse/parent quality sources.
- [ ] **Step 6:** Run v2.2 core and quality tests; expect PASS.
- [ ] **Step 7:** Run existing v2.1 core tests; expect unchanged PASS and verify no v2.1 file hash changed.

### Task 4: Build immutable single-request and eight-request matrix preparers

**Files:**
- Create: `scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_2_request.py`
- Create: `scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_2_matrix.py`
- Create: `scripts/analysis/channel_modeling/tests/test_prepare_darkroom_generator_v2_2_request.py`
- Create: `scripts/analysis/channel_modeling/tests/test_prepare_darkroom_generator_v2_2_matrix.py`

**Interfaces:**
- Consumes: v2.2 config, scene metadata, source hashes, environment/quality matrix.
- Produces: canonical `generation_request.json`, request SHA, `request_matrix.csv`, `matrix_manifest.json` and matrix SHA.

- [ ] **Step 1:** Write request tests requiring `pairing_id`, quality mode, all bands, 20,000 ms, 10.23 MHz, all-positive contract, source scene IDs, parent hashes, `new_only=true` and every execution flag false.
- [ ] **Step 2:** Write rejection tests for unknown environment, unknown quality mode, single-band override, scene label outside the selected environment, existing namespace, path traversal and any raw/MATLAB/SAGE/batch/20.46 MHz flag.
- [ ] **Step 3:** Write matrix tests requiring exactly 8 rows ordered by environment then Good/Poor, exactly 4 pairing IDs, paired identical master seeds and unique request/output namespaces.
- [ ] **Step 4:** Implement canonical JSON serialization, source hashing, backend receipt, scene-metadata lookup and direct-child new-only namespace checks.
- [ ] **Step 5:** Implement matrix generation with `duration_ms=20000`, `master_seed=20260827` and immutable environment source-scene lists.
- [ ] **Step 6:** Run both preparer test files; expect PASS.

### Task 5: Implement hash-gated new-only runner

**Files:**
- Create: `scripts/analysis/channel_modeling/run_darkroom_generator_v2_2.py`
- Create: `scripts/analysis/channel_modeling/tests/test_run_darkroom_generator_v2_2.py`

**Interfaces:**
- Consumes: one immutable request path and `--expected-request-sha256`.
- Produces: validation summary or one complete v2.2 run namespace.

- [ ] **Step 1:** Write tests requiring validation-only by default and explicit `--generate --confirm-darkroom-generation-v2-2` for writes.
- [ ] **Step 2:** Write tests rejecting mismatched request/config/source/model hashes, wrong Python backend, an existing output directory, nested/old namespace, resume, and all forbidden execution flags.
- [ ] **Step 3:** Implement request revalidation, parent hash checks, global v2.2 lock, atomic per-file writes inside the newly created request-specific directory, receipt writing and failure preservation.
- [ ] **Step 4:** Implement outputs listed in Section 2.3 and hash every artifact in `generation_manifest.json`.
- [ ] **Step 5:** Ensure exceptions write a failed receipt without deleting partial files, without resume and without auto-starting another request.
- [ ] **Step 6:** Run runner tests; expect PASS.

### Task 6: Implement independent v2.2 auditor

**Files:**
- Create: `scripts/analysis/channel_modeling/audit_darkroom_generator_v2_2.py`
- Create: `scripts/analysis/channel_modeling/tests/test_audit_darkroom_generator_v2_2.py`

**Interfaces:**
- Consumes: one completed run directory and frozen request/config/source hashes.
- Produces: `independent_qa_result.json` and `independent_qa_report.md`.

- [ ] **Step 1:** Write tests for canonical completeness, exact ordering, finite values, strictly positive path amplitudes and phase recurrence.
- [ ] **Step 2:** Write Good-specific tests: no quality event, all-one envelope, all tracked, all phase observable.
- [ ] **Step 3:** Write Poor-specific tests: one complete event per band, non-unity impairment envelope, full recovery, positive floor and false observability only during the event.
- [ ] **Step 4:** Write paired-run tests comparing a Good/Poor pair through `pairing_id`, proving base path/gain identity and quality-only output differences.
- [ ] **Step 5:** Write provenance tests for prior-only/sparse cells, environment lock support, scene labels, model hashes, protected pipeline hash and `gold_labels_used_for_generation=false`.
- [ ] **Step 6:** Implement the auditor and fail closed on any missing row, duplicate key, hash mismatch, incomplete Poor event, unexpected Good event or existing-parent mutation.
- [ ] **Step 7:** Run auditor tests; expect PASS.

### Task 7: Static checks and full compatibility regression

**Files:**
- Verify only; no scientific artifact generation.

- [ ] **Step 1:** Run `py_compile` on all six new v2.2 source files.
- [ ] **Step 2:** Run all six v2.2 test files; expect zero failures.
- [ ] **Step 3:** Run all v2.1 focused tests and all lock/gain/path-distribution focused tests; expect no new regression.
- [ ] **Step 4:** Run the full `scripts/analysis/channel_modeling/tests` suite and record every result; no v2.2 release if any new failure is attributable to v2.2.
- [ ] **Step 5:** Recompute and verify v2.1 config/core and production-pipeline hashes against the frozen values in this plan.
- [ ] **Step 6:** Run `git diff --check` and inspect `git diff --name-only`; only the approved v2.2 files, tests, plan and eventual Engineering Handoff update may appear.

### Task 8: Prepare and validation-only check the 8-request pilot matrix

**Files:**
- Create under: `dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices/environment_quality_pair_20s_v2_2_20260827/`
- Create under: `dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_requests/`

- [ ] **Step 1:** Run the matrix preparer with the frozen 20,000 ms duration and seed 20260827.
- [ ] **Step 2:** Verify `request_matrix.csv` has exactly 8 accepted rows, 0 rejected rows, 8 unique output namespaces and four Good/Poor pairs.
- [ ] **Step 3:** Run validation-only for all 8 requests by reading each exact request path/SHA from `request_matrix.csv`; do not generate output.
- [ ] **Step 4:** Confirm all eight report `execution_eligible=true`, `generation_requested=false`, output absent and forbidden execution flags false.
- [ ] **Step 5:** Freeze the matrix manifest and SHA; stop if any request is not eligible.

### Task 9: Generate and QA the controlled Urban pair

**Files:**
- Create two new run namespaces under: `dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/`

- [ ] **Step 1:** Generate Urban Good using its exact request path/SHA and explicit confirmation flag.
- [ ] **Step 2:** Run independent QA; require PASS.
- [ ] **Step 3:** Generate Urban Poor using the paired exact request path/SHA.
- [ ] **Step 4:** Run independent QA and paired Good/Poor QA; require PASS.
- [ ] **Step 5:** Verify each table has 240,000 rows, each NLOS row is positive, and the Poor table has one complete event per Low/Mid/High.
- [ ] **Step 6:** Stop the execution if the Urban pair fails; preserve all artifacts and do not generate the other environments.

### Task 10: Generate the remaining three environment pairs sequentially

**Files:**
- Create six new run namespaces under the v2.2 run root.

- [ ] **Step 1:** Generate and audit Special Reflective Good, then Poor, then paired QA.
- [ ] **Step 2:** Generate and audit Mountain/Valley Good, then Poor, then paired QA.
- [ ] **Step 3:** Generate and audit Highway/Open Good, then Poor, then paired QA.
- [ ] **Step 4:** Stop on the first failure; preserve existing successful and failed artifacts; never skip directly to the next environment.
- [ ] **Step 5:** Verify final matrix accounting: 8 tables, 1,920,000 canonical rows, 24 environment×band×quality cells, 0 zero-amplitude NLOS rows.

### Task 11: Aggregate QA, status report and handoff sync

**Files:**
- Create: `dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices/environment_quality_pair_20s_v2_2_20260827/matrix_qa_summary.csv`
- Create: `dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices/environment_quality_pair_20s_v2_2_20260827/matrix_qa_report.md`
- Modify only after successful implementation/execution: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`

- [ ] **Step 1:** Aggregate per-run row count, quality-event count, prior/support flags, request/run/QA hashes and paired invariance checks.
- [ ] **Step 2:** Report separately: implementation status, per-run QA, pair QA, matrix QA and known scientific limitations.
- [ ] **Step 3:** State explicitly that 8 tables represent 24 logical conditions but only 4 environment-level fitted families; do not claim 13 independent scene models.
- [ ] **Step 4:** State that Poor is conditional receiver-diagnostic impairment, phase is assumption-only, absolute RF power is unavailable and Highway/Open quality evidence is prior-dominant.
- [ ] **Step 5:** Update Engineering Handoff only with actual completed code/artifact/hash/QA facts. Do not update Paper Handoff unless the user separately authorizes a paper-status change.
- [ ] **Step 6:** Stop after the 20 s pilot matrix. Do not automatically generate longer darkroom records.

---

## 5. Release Gates

### Gate A — Implementation

```text
V2_2_PY_COMPILE = PASS
V2_2_FOCUSED_TESTS = PASS
V2_1_REGRESSION = PASS
PARENT_HASHES_UNCHANGED = YES
PROTECTED_PIPELINE_HASH_UNCHANGED = YES
```

### Gate B — Request readiness

```text
MATRIX_REQUEST_COUNT = 8
VALIDATION_ONLY_ELIGIBLE = 8/8
OUTPUT_NAMESPACES_ABSENT = 8/8
NEW_ONLY = TRUE
RESUME_ALLOWED = FALSE
RAW/MATLAB/SAGE/BATCH = FALSE
```

### Gate C — Urban pair

```text
URBAN_GOOD_QA = PASS
URBAN_POOR_QA = PASS
URBAN_PAIRED_INVARIANCE = PASS
URBAN_POOR_COMPLETE_EVENT_PER_BAND = 3/3
URBAN_ZERO_AMPLITUDE_NLOS = 0
```

### Gate D — Full matrix

```text
RUN_QA_PASS = 8/8
PAIR_QA_PASS = 4/4
CANONICAL_TABLES = 8
LOGICAL_CONDITION_CELLS = 24
CANONICAL_ROWS = 1,920,000
ZERO_AMPLITUDE_NLOS_ROWS = 0
PRIOR_ONLY_PROVENANCE_PRESERVED = YES
```

任何 gate FAIL：

```text
status = FAILED_OR_INCOMPLETE
preserve_artifacts = true
auto_resume = false
auto_delete = false
continue_next_environment = false
```

---

## 6. Explicit Non-Goals

- 不拟合新的 path distribution family。
- 不按 13 个 scene 分别伪造 scene-specific model。
- 不估计绝对 RF 功率、天线增益或暗室标定 dBm。
- 不把 receiver diagnostic lock event 称为物理信号中断。
- 不引入 NLOS occurrence probability；三条 NLOS 仍按 v2.1 条件性全激活合同生成。
- 不拟合 event-level 或 inter-satellite correlation。
- 不改变 phase assumption。
- 不运行 MATLAB/SAGE，不读取 raw IQ，不处理20.46 MHz。
- 不自动生成超出 20 s pilot 的最终暗室回放时长。

---

## 7. Expected Deliverable After Approved Execution

```text
4 environment model families
8 immutable parameter tables
24 environment × elevation × quality condition cells
20,000 ms per table
240,000 canonical rows per table
1,920,000 canonical rows total
Low/Mid/High in every table
path 0–3 in every millisecond and every band
all NLOS amplitudes strictly positive
Good/Poor paired base parameters identical
Poor quality event complete for every band
all hashes, manifests, receipts and QA reports frozen
```

The 20 s pilot is the end of this plan. A later final-duration export requires a separate user decision and new immutable requests.
