# Darkroom Multi-Elevation Fixed-Four-Slot Generator v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为一个指定环境同时生成 Low、Mid、High 三种卫星仰角上下文的可复现暗室参数表；每毫秒固定输出 3 × 4 = 12 个槽位行，所有七列均有数值，同时允许 NLOS 槽位通过 `RelativeAmplitude=0` 表示未激活。

**Architecture:** 采用新的 v2 immutable request 和 new-only namespace。每个 request 固定一个 `environment_class`、持续时间和 master seed，生成器并行构造 Low/Mid/High 三条独立条件时间轴；每个仰角上下文始终拥有 path 0 和 NLOS slot 1/2/3 四个结构槽位。激活模型只控制 NLOS 槽位的有效幅度是否为零，不再控制行是否存在，也不再产生 canonical CSV 空字段。

**Tech Stack:** Python 3.12；NumPy 2.5.1；SciPy 1.18.0；OpenBLAS；标准库 `argparse/csv/json/hashlib/pathlib/dataclasses/gzip/time`；pytest。固定解释器为 `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`。

**Spec:** 用户于 2026-08-27 确认的 fixed-slot 语义；父计划 `docs/superpowers/plans/2026-08-27-reproducible-darkroom-four-path-generator.md`；冻结模型报告 `docs/ENVIRONMENT_ELEVATION_PATH_DISTRIBUTION_MODEL_V1_REPORT.md`、`docs/MAIN_PATH_COMMON_GAIN_FADE_MODEL_V1_REPORT.md`、`docs/NLOS_SLOT_ACTIVATION_MODEL_V1_REPORT.md`、`docs/LOCK_AMPLITUDE_PHASE_RECOVERY_MODEL_V1_REPORT.md`。

## Global Constraints

- 本文是 v2 实施计划，状态为 `Planned / Not started`；创建本文不表示 v2 代码、120 ms v2 表或独立 QA 已完成。
- v1 代码、request 和 120 ms preview 必须永久保留，不覆盖、不改名、不静默修正。v1 preview 仅说明旧单仰角/可空槽位合同，不是 v2 目标输出。
- v2 必须使用全新的配置、源码、request 和 run namespace；不得把科学合同变化伪装成 v1 bugfix。
- 禁止读取 raw IQ、运行 MATLAB、运行 SAGE、启动 batch、处理 20.46 MHz，或写入 `scenes/**/sage_results`。
- 不修改四个冻结父模型、event/path database、tracking、metadata、inventory、production request/manifest 或既有 QA artifact。
- 受保护生产入口 `scripts/sage_pipeline/run_nav_sage_pipeline.m` 必须保持 SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。
- 所有 v2 request/run 为 `new_only=true`、`resume_allowed=false`；目标存在即 fail closed，不覆盖、不续跑、不自动删除。
- 一个输出文件只对应一个环境；Low/Mid/High 必须同时出现，顺序固定且不可由 request 调整。
- `SatelliteID` 在该接口中是仰角上下文标签 `Low/Mid/High`，不是 GPS PRN。
- 四条路径是四个固定硬件槽位，不表示四条物理路径始终激活。
- inactive NLOS canonical row 必须保留完整有限的 delay、Doppler 和 phase，但 `RelativeAmplitude=0`；这些数值是 latent slot parameters，不得解释为已存在的传播路径。
- active NLOS 的 `RelativeAmplitude>0`；path 0 的动态幅度保持正值。
- 相位仍是外加假设 `Uniform(-pi,pi)` 初值加 Doppler 连续演化，不是从 Stage4 拟合所得。
- Low/Mid/High 三条卫星上下文之间的相关性尚未拟合；v2 使用相互独立的 band-keyed random streams，并记录 `INTER_SATELLITE_CORRELATION_NOT_MODELED`。
- `PRIOR_ONLY` cell 允许生成完整数值，但必须在 sidecar/manifest 中保留 `PRIOR_ONLY=true`，不得在 canonical CSV 中留空或把 prior 写成实测验证。

---

## 1. Frozen v2 Output Contract

### 1.1 Exact columns

Canonical CSV 仍严格使用用户冻结的七列及顺序：

```text
ms
SatelliteID
NLOSPathID
RelativeDelay
RelativeDoppler
RelativeAmplitude
RelativePhase_rad
```

单位：

```text
RelativeDelay       = ns
RelativeDoppler     = Hz
RelativeAmplitude   = linear amplitude ratio
RelativePhase_rad   = rad, wrapped to [-pi,pi)
```

不得新增 `active`、`environment`、`support_status` 等 canonical 列；这些只写 sidecar。

### 1.2 Exact row order

每个毫秒必须严格输出：

```text
ms=m, Low,  NLOSPathID=0
ms=m, Low,  NLOSPathID=1
ms=m, Low,  NLOSPathID=2
ms=m, Low,  NLOSPathID=3
ms=m, Mid,  NLOSPathID=0
ms=m, Mid,  NLOSPathID=1
ms=m, Mid,  NLOSPathID=2
ms=m, Mid,  NLOSPathID=3
ms=m, High, NLOSPathID=0
ms=m, High, NLOSPathID=1
ms=m, High, NLOSPathID=2
ms=m, High, NLOSPathID=3
```

排序键冻结为：

```python
SATELLITE_ORDER = {"Low": 0, "Mid": 1, "High": 2}
sort_key = (ms, SATELLITE_ORDER[SatelliteID], NLOSPathID)
```

持续 `duration_ms=D` 时，canonical CSV 必须恰有 `12 × D` 行。120 ms 预览必须恰有 1440 行。

### 1.3 Fixed slots versus activation

每个 band 每个 ms 都有四个结构槽位：

| Slot | Structural presence | Activation | Canonical amplitude | Other canonical parameters |
|---|---|---|---|---|
| path 0 | always | reference path | finite positive dynamic value | delay=0, Doppler=0, finite phase |
| NLOS 1/2/3 active | always | active | finite positive value | finite delay/Doppler/phase |
| NLOS 1/2/3 inactive | always | inactive | exactly `0` | finite latent delay/Doppler/phase |

Canonical CSV 不允许任何空字段、`NaN`、`None` 或 `null`。inactive 状态只能通过幅度 0 识别；精确 activation provenance 必须同时记录在 `path_slot_timeline.csv.gz`。

### 1.4 Latent inactive parameters

每个 40 ms block、每个 band 均先生成三个完整 latent NLOS parameter vectors：

```text
(delay_ns, relative_doppler_hz, relative_power_db)
```

再按 delay 升序、amplitude 降序、Doppler 升序进行稳定排序并映射到 slot 1/2/3。随后 activation model 抽取 `Z` 和 `K`：

```text
K=0 -> mask 000
K=1 -> mask 100
K=2 -> mask 110
K=3 -> mask 111
```

active slot：

```text
RelativeAmplitude = effective_common_gain × 10^(relative_power_db/20)
```

inactive slot：

```text
RelativeAmplitude = 0
```

inactive slot 的 latent delay/Doppler/phase 仅为固定槽位的预生成数值。它们不计入 active path count，不得用于 active-path统计，也不得解释为 confirmed multipath。

### 1.5 Time semantics

- 输出采样间隔固定为 1 ms，`ms=1..duration_ms`。
- NLOS latent parameters、activation mask 和 active relative-amplitude base 在 40 ms 非重叠 block 内固定。
- 每个 band 有独立的 path 0 common-gain/fade/lock timeline。
- 每个 band 的 path 0 初相只在 request 开始时抽取一次。
- 每个 block 的三个 NLOS slot 均抽取初相并按各自 latent Doppler 每 1 ms 演化；inactive 时也演化，以保证 canonical 数值连续和完全填充。
- block 边界重新抽取三个 latent NLOS vectors 和初相；v2 不建立 inter-block path identity/lifetime。
- Low/Mid/High 使用独立 band stream；不拟合跨卫星同步遮挡、共同反射或相关失锁。

### 1.6 One-environment request schema

v2 request 不再接受单个 `elevation_band`。冻结字段至少包括：

```json
{
  "request_schema_version": "darkroom-generator-request-2",
  "request_id": "preview_120ms_urban_all_bands_v2",
  "simulation_id": "preview-120ms-urban-all-bands-v2",
  "generator_id": "darkroom-multi-elevation-four-slot-generator-v2",
  "environment_class": "Urban",
  "elevation_bands": ["LOW", "MID", "HIGH"],
  "duration_ms": 120,
  "master_seed": 20260827,
  "activation_mode": "EMPIRICAL_CONFIRMED_SUPPORT",
  "inactive_slot_parameter_policy": "LATENT_PARAMETERS_WITH_ZERO_AMPLITUDE",
  "lock_mapping_mode": "EMPIRICAL_DIAGNOSTIC_PROXY",
  "new_only": true,
  "resume_allowed": false,
  "raw_iq_read": false,
  "matlab": false,
  "sage": false,
  "batch": false,
  "process_20_46_mhz": false
}
```

`elevation_bands` 必须严格等于 `LOW,MID,HIGH`，不可缺失、重排或由 CLI 覆盖。

---

## 2. Planned File Layout

### Source and config

```text
configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2.json
scripts/analysis/channel_modeling/darkroom_generator_v2_core.py
scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_request.py
scripts/analysis/channel_modeling/run_darkroom_generator_v2.py
scripts/analysis/channel_modeling/audit_darkroom_generator_v2.py
scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_core.py
scripts/analysis/channel_modeling/tests/test_prepare_darkroom_generator_v2_request.py
scripts/analysis/channel_modeling/tests/test_run_darkroom_generator_v2.py
scripts/analysis/channel_modeling/tests/test_audit_darkroom_generator_v2.py
```

### New-only namespaces

```text
dataset_generation_logs/channel_modeling/
  darkroom_generator_v2_requests/<request_id>/
    generation_request.json
    generation_request.sha256

  darkroom_generator_v2_runs/<request_id>/
    generation_request.json
    generation_request.sha256
    darkroom_channel_parameters.csv
    path_block_catalog.csv
    path_slot_timeline.csv.gz
    receiver_timeline.csv.gz
    random_stream_registry.csv
    generation_manifest.json
    generation_receipt.json
    generation_report.md
    independent_qa_result.json
    independent_qa_report.md
```

No v2 file may be written into a v1 request/run namespace.

---

### Task 1: Freeze v2 Schema and Parent Provenance

**Files:**
- Create: `configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2.json`
- Create: `scripts/analysis/channel_modeling/darkroom_generator_v2_core.py`
- Test: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_core.py`

**Interfaces:**
- Consumes: the four immutable v1 parent model manifests/contracts and protected pipeline hash.
- Produces: `GeneratorV2Config`, `GenerationV2Request`, `load_generator_v2_config`, `validate_generation_v2_request`, `load_frozen_parent_models`.

- [ ] **Step 1: Write failing schema tests**

```python
def test_v2_columns_bands_and_row_order_are_frozen():
    assert FINAL_COLUMNS == (
        "ms", "SatelliteID", "NLOSPathID", "RelativeDelay",
        "RelativeDoppler", "RelativeAmplitude", "RelativePhase_rad",
    )
    assert BAND_SEQUENCE == (("LOW", "Low"), ("MID", "Mid"), ("HIGH", "High"))
    assert [(band, path) for band in ("Low", "Mid", "High") for path in range(4)] == EXPECTED_ROWS_PER_MS
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest scripts\analysis\channel_modeling\tests\test_darkroom_generator_v2_core.py -q
```

Expected: import failure because v2 core does not yet exist.

- [ ] **Step 3: Implement immutable config loading and validation**

Freeze exact parent paths/hashes, backend versions, units, 1 ms step, 40 ms block, all-band sequence, zero-amplitude inactive policy, no-execution flags and v2 namespace roots. Reject a single-band request, reordered bands, null-enabled policy, wrong sample rate or any raw/MATLAB/SAGE/batch/20.46 MHz flag.

- [ ] **Step 4: Verify every parent and protected source hash**

Reuse v1 parent artifacts read-only, but compute and compare each declared SHA-256 before returning `FrozenParentModels`. Do not import v1 runner or trust its receipt as a loader.

- [ ] **Step 5: Run tests and confirm GREEN**

Expected: all v2 schema/provenance tests pass; no request or run namespace is created.

### Task 2: Implement Immutable v2 Request Preparation

**Files:**
- Create: `scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_request.py`
- Test: `scripts/analysis/channel_modeling/tests/test_prepare_darkroom_generator_v2_request.py`

**Interfaces:**
- Consumes: `GeneratorV2Config`, frozen parent receipt, CLI environment/duration/seed.
- Produces: canonical `generation_request.json` and `generation_request.sha256`.

- [ ] **Step 1: Write rejection and canonical-hash tests**

```python
def test_request_contains_all_bands_and_no_single_band_override(tmp_path):
    payload = build_v2_request(environment="Urban", duration_ms=120, master_seed=20260827)
    assert payload["elevation_bands"] == ["LOW", "MID", "HIGH"]
    assert "elevation_band" not in payload
    assert payload["inactive_slot_parameter_policy"] == "LATENT_PARAMETERS_WITH_ZERO_AMPLITUDE"
```

- [ ] **Step 2: Implement request preparation**

CLI accepts only project root, config, request/simulation IDs, environment, duration, seed, output request directory and validate-only flag. It must not accept a band argument. It freezes config, parent, v2 core, preparer, runner, auditor, Python, NumPy, SciPy, OpenBLAS and protected pipeline hashes.

- [ ] **Step 3: Enforce new-only path safety**

Reject existing request/output directories, traversal, absolute overrides outside project root, `scenes`, `sage_results`, event database, parent namespaces, `_trash`, v1 namespaces and project root.

- [ ] **Step 4: Run tests and confirm GREEN**

Validation-only must create no file; request creation writes exactly two immutable files.

### Task 3: Implement Band-Isolated Deterministic Streams

**Files:**
- Modify: `scripts/analysis/channel_modeling/darkroom_generator_v2_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_core.py`

**Interfaces:**
- Consumes: master seed, simulation identity, environment, canonical band, scope and stream name.
- Produces: `derive_v2_stream_seed` and `RandomStreamRegistry`.

- [ ] **Step 1: Write exact seed-isolation tests**

```python
def test_low_mid_high_streams_are_distinct_and_reproducible():
    low = derive_v2_stream_seed(7, "sim", "Urban", "LOW", "block-1", "path")
    mid = derive_v2_stream_seed(7, "sim", "Urban", "MID", "block-1", "path")
    high = derive_v2_stream_seed(7, "sim", "Urban", "HIGH", "block-1", "path")
    assert len({low, mid, high}) == 3
    assert low == derive_v2_stream_seed(7, "sim", "Urban", "LOW", "block-1", "path")
```

- [ ] **Step 2: Implement SHA-256/uint64 seed derivation**

Use canonical UTF-8 JSON and the first eight SHA-256 bytes as unsigned big-endian uint64. Request ID, output path and timestamp must not affect scientific streams.

- [ ] **Step 3: Record the cross-band assumption**

Every run manifest and sidecar must contain `INTER_SATELLITE_CORRELATION_NOT_MODELED`; no shared random stream may silently correlate Low/Mid/High.

- [ ] **Step 4: Run tests and confirm GREEN**

Changing only one band stream must not alter either of the other bands.

### Task 4: Generate Three Complete Latent NLOS Slots per Band and Block

**Files:**
- Modify: `scripts/analysis/channel_modeling/darkroom_generator_v2_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_core.py`

**Interfaces:**
- Consumes: environment×band path cell, environment copula, activation cell and block RNGs.
- Produces: `LatentSlotDraw[3]`, `ActivationMask`, `PathBlockRecord[3]`.

- [ ] **Step 1: Write latent-slot and activation tests**

```python
def test_k_one_keeps_all_parameters_but_zeros_inactive_amplitudes():
    slots = fixture_slots_with_k(1)
    assert [slot.active for slot in slots] == [True, False, False]
    assert all(slot.delay_ns > 0 for slot in slots)
    assert all(math.isfinite(slot.doppler_hz) for slot in slots)
    assert all(math.isfinite(slot.initial_phase_rad) for slot in slots)
    assert [slot.output_amplitude_base for slot in slots] == [slots[0].latent_amplitude, 0.0, 0.0]
```

- [ ] **Step 2: Always draw three joint latent vectors**

For each band/block, generate exactly three vectors through the frozen environment copula and requested-band marginals. Preserve positive relative-power dB and amplitudes above 1; do not clip to make path 0 strongest.

- [ ] **Step 3: Apply activation after latent generation**

Sample `Z` and conditional `K` through the frozen activation model. Map `K` to `000/100/110/111`; keep all latent values but set inactive output amplitude base to zero.

- [ ] **Step 4: Preserve scientific labels**

Record `active`, `activation_mask`, `latent_relative_amplitude`, `output_relative_amplitude_base`, occupancy/multiplicity/path support, `PRIOR_ONLY`, and `LATENT_INACTIVE_PARAMETER_NOT_PHYSICAL_PATH` in `path_block_catalog.csv`.

- [ ] **Step 5: Run distribution/activation regression tests**

Test all 12 environment×band cells. Activation frequencies and conditional K must match frozen parent semantics; latent path marginals/copula must match parent QA tolerances.

### Task 5: Generate Independent Band Receiver Timelines

**Files:**
- Modify: `scripts/analysis/channel_modeling/darkroom_generator_v2_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_core.py`

**Interfaces:**
- Consumes: gain/fade/lock parents, environment, each band and duration.
- Produces: three `BandReceiverTimeline` objects.

- [ ] **Step 1: Write timeline shape and isolation tests**

```python
def test_each_band_has_a_complete_one_ms_timeline():
    timelines = build_band_timelines(request_120ms_fixture())
    assert set(timelines) == {"LOW", "MID", "HIGH"}
    assert all(len(timeline.rows) == 120 for timeline in timelines.values())
```

- [ ] **Step 2: Implement Student-t PPF common gain**

For each band, use latent Gaussian AR(1), `rho=exp(-0.001/tau_s)`, Gaussian CDF and the frozen selected marginal PPF. Do not substitute a normal-only `loc+scale*z` approximation.

- [ ] **Step 3: Implement ordinary fade and lock/recovery composition**

Preserve frozen parent timing and lock-supercedes-fade policy. All envelopes remain positive. Lock is a receiver-diagnostic proxy, not calibrated absolute attenuation.

- [ ] **Step 4: Record band identity and support**

`receiver_timeline.csv.gz` must contain one row per `(ms, band)` and therefore `3 × duration_ms` rows, ordered Low/Mid/High inside each ms.

- [ ] **Step 5: Run timeline tests and confirm GREEN**

Verify positivity, legal transitions, no overlap, exact row order and deterministic replay.

### Task 6: Implement Complete Phase State for Active and Inactive Slots

**Files:**
- Modify: `scripts/analysis/channel_modeling/darkroom_generator_v2_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_core.py`

**Interfaces:**
- Consumes: request/band path-0 phase stream and block/band/slot phase streams.
- Produces: finite `RelativePhase_rad` for every canonical row.

- [ ] **Step 1: Write no-null and recurrence tests**

```python
def test_inactive_slot_phase_is_finite_and_evolves_with_latent_doppler():
    first, second = inactive_slot_two_ms_fixture()
    expected = wrap_to_pi(first.phase + 2 * math.pi * first.doppler_hz * 0.001)
    assert math.isfinite(first.phase)
    assert second.phase == pytest.approx(expected, abs=1e-12)
```

- [ ] **Step 2: Implement phase initialization and recurrence**

Use one path-0 initial phase per band/request and one NLOS initial phase per band/block/slot. Update every NLOS phase each ms regardless of activation; never reset phase due to lock state.

- [ ] **Step 3: Label assumption-only semantics**

Record `ASSUMPTION_ONLY_UNIFORM_INITIAL_PLUS_DOPPLER_CONTINUOUS` and `INACTIVE_PHASE_IS_LATENT_NOT_OBSERVABLE` in sidecars/manifests.

- [ ] **Step 4: Run phase tests and confirm GREEN**

Require all phases finite in `[-pi,pi)` and exact recurrence for active/inactive slots.

### Task 7: Compose the Exact 12-Row-per-ms Canonical Table

**Files:**
- Modify: `scripts/analysis/channel_modeling/darkroom_generator_v2_core.py`
- Modify: `scripts/analysis/channel_modeling/tests/test_darkroom_generator_v2_core.py`

**Interfaces:**
- Consumes: three band receiver timelines and three band path-block states.
- Produces: ordered `FinalRow` sequence and locale-independent CSV bytes.

- [ ] **Step 1: Write the exact 120 ms structural fixture**

```python
def test_120ms_output_has_1440_complete_rows_in_exact_order():
    rows = generate_fixture(duration_ms=120)
    assert len(rows) == 1440
    assert [(r.SatelliteID, r.NLOSPathID) for r in rows[:12]] == [
        ("Low", 0), ("Low", 1), ("Low", 2), ("Low", 3),
        ("Mid", 0), ("Mid", 1), ("Mid", 2), ("Mid", 3),
        ("High", 0), ("High", 1), ("High", 2), ("High", 3),
    ]
```

- [ ] **Step 2: Implement amplitude composition**

For each band/ms:

```text
path0 amplitude = effective_common_gain
active NLOS amplitude = effective_common_gain × latent_relative_amplitude
inactive NLOS amplitude = 0
```

Delay/Doppler/phase remain complete for every slot. No `None`, blank, `NaN`, `null` or placeholder string is permitted.

- [ ] **Step 3: Freeze exact formatting**

Use UTF-8, comma delimiter, LF line endings, invariant decimal formatting and exact header. Add a golden-byte test for a deterministic 2 ms fixture.

- [ ] **Step 4: Run table tests and confirm GREEN**

Require exactly four rows per band per ms, 12 rows per ms, no duplicate keys and no empty fields.

### Task 8: Implement the v2 New-Only Runner and Receipts

**Files:**
- Create: `scripts/analysis/channel_modeling/run_darkroom_generator_v2.py`
- Test: `scripts/analysis/channel_modeling/tests/test_run_darkroom_generator_v2.py`

**Interfaces:**
- Consumes: only `--request` and `--expected-request-sha256`.
- Produces: validation-only receipt or one new v2 run namespace.

- [ ] **Step 1: Write preflight rejection tests**

Reject request/hash tampering, single-band/reordered-band payloads, changed parent/config/core/runner/pipeline/backend hash, existing output, active lock, v1 namespace, forbidden execution flags and paths outside the v2 root.

- [ ] **Step 2: Implement validation-only default**

Without explicit `--generate --confirm-darkroom-generation-v2`, print environment, all bands, duration, expected `12×duration` rows, seed, hashes, support statuses and output path; create nothing.

- [ ] **Step 3: Implement generation and immutable receipts**

Write canonical/sidecar files in deterministic order, heartbeat by 40 ms block, hash every output, preserve failed/interrupted artifacts and never auto-resume or auto-delete.

- [ ] **Step 4: Run runner tests and confirm GREEN**

Validation-only must report `matlab=false`, `sage=false`, `raw_iq_read=false`, `batch=false` and `process_20_46_mhz=false`.

### Task 9: Implement an Independent v2 Auditor

**Files:**
- Create: `scripts/analysis/channel_modeling/audit_darkroom_generator_v2.py`
- Test: `scripts/analysis/channel_modeling/tests/test_audit_darkroom_generator_v2.py`

**Interfaces:**
- Consumes: frozen request, v2 run directory and parent artifacts.
- Produces: independent QA JSON/Markdown and hard-gate decision.

- [ ] **Step 1: Write tamper tests**

Cover altered request/output hash, missing/reordered row, duplicate `(ms,SatelliteID,NLOSPathID)`, blank field, inactive nonzero amplitude mismatch, invalid phase recurrence, block drift, wrong band ordering and hidden v1 namespace reuse.

- [ ] **Step 2: Independently recompute structural gates**

Require:

```text
row_count = 12 × duration_ms
band_count_per_ms = 3
slot_count_per_band_per_ms = 4
canonical_empty_field_count = 0
```

- [ ] **Step 3: Independently verify active/inactive semantics**

Join canonical rows to `path_slot_timeline.csv.gz`. Active NLOS requires positive amplitude; inactive NLOS requires exactly zero amplitude while delay/Doppler/phase remain finite. Inactive latent parameters must be excluded from active-path summaries.

- [ ] **Step 4: Verify equations and provenance**

Check path-0 base semantics, amplitude composition, phase recurrence, block constancy, support/prior/assumption labels, deterministic stream registry and all source/output hashes.

- [ ] **Step 5: Run auditor tests and confirm GREEN**

Auditor must not import/call runner generation functions and must not read raw, tracking, Stage or gold data.

### Task 10: Generate a New 120 ms v2 Preview After Implementation Approval

**Files:**
- Create through the v2 request preparer: `dataset_generation_logs/channel_modeling/darkroom_generator_v2_requests/preview_120ms_urban_all_bands_v2_<attempt>/`
- Create through the v2 runner: `dataset_generation_logs/channel_modeling/darkroom_generator_v2_runs/preview_120ms_urban_all_bands_v2_<attempt>/`

**Interfaces:**
- Consumes: the fully frozen v2 code/config and `Urban`, 120 ms, seed `20260827`.
- Produces: 1440-row preview plus sidecars/receipt/independent QA.

- [ ] **Step 1: Run py_compile and all focused tests**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m py_compile `
  scripts\analysis\channel_modeling\darkroom_generator_v2_core.py `
  scripts\analysis\channel_modeling\prepare_darkroom_generator_v2_request.py `
  scripts\analysis\channel_modeling\run_darkroom_generator_v2.py `
  scripts\analysis\channel_modeling\audit_darkroom_generator_v2.py

& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  scripts\analysis\channel_modeling\tests\test_darkroom_generator_v2_core.py `
  scripts\analysis\channel_modeling\tests\test_prepare_darkroom_generator_v2_request.py `
  scripts\analysis\channel_modeling\tests\test_run_darkroom_generator_v2.py `
  scripts\analysis\channel_modeling\tests\test_audit_darkroom_generator_v2.py -q
```

- [ ] **Step 2: Freeze and validation-only check one immutable preview request**

Require request/config/parent/source/backend/pipeline hashes PASS, output absent and lock absent before generation.

- [ ] **Step 3: Generate exactly one preview**

Generate `Urban × {LOW,MID,HIGH}`, duration 120 ms, seed 20260827. Do not generate another environment or start a batch.

- [ ] **Step 4: Run independent QA**

Require exact 1440 rows, complete fields, exact per-ms order, activation/amplitude consistency, finite phases, 3 complete 40 ms blocks per band and all hard provenance gates PASS.

- [ ] **Step 5: Present the preview for user review**

Report the canonical CSV path/hash and show the first 12 rows. Stop for user inspection before any longer or multi-environment generation.

### Task 11: Complete 12-Cell Regression and Publish Status After Preview Approval

**Files:**
- Create only after successful independent QA: `docs/DARKROOM_MULTI_ELEVATION_FIXED_FOUR_SLOT_GENERATOR_V2_REPORT.md`
- Modify when engineering facts change: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Do not modify Paper Handoff unless a bounded scientific result, rather than implementation status, is established.

**Interfaces:**
- Consumes: user-approved 120 ms v2 preview and all v2 tests.
- Produces: implementation/QA report and controlled readiness decision.

- [ ] **Step 1: Run complete channel-modeling regression suite**

Verify all existing parent tests and v1 generator tests remain unchanged and passing.

- [ ] **Step 2: Run direct 12-cell model checks**

For all four environments × three bands, compare latent path draws, activation frequencies, K distribution, gain marginal and state timelines to the frozen parent contracts. Do not treat inactive latent slots as active observations.

- [ ] **Step 3: Run deterministic replay QA**

Two isolated run namespaces with the same scientific request/seed must produce byte-identical canonical tables and deterministic sidecars after excluding receipt timestamps. Changing only the seed must change scientific values without changing schema/count/order.

- [ ] **Step 4: Freeze the report and controlled status**

Use status `Implemented` after code/tests and `Validated` only after independent QA and regression gates pass. Never claim absolute RF calibration, inter-satellite correlation, physical LOS probability, fitted phase distribution or path lifetime completion.

---

## 3. Fixed v2 QA Gates

The independent auditor must emit:

```text
REQUEST_CONFIG_HASH_GATE = PASS/FAIL
PARENT_PROVENANCE_GATE = PASS/FAIL
V2_NAMESPACE_ISOLATION_GATE = PASS/FAIL
ALL_BANDS_PRESENT_GATE = PASS/FAIL
EXACT_12_ROWS_PER_MS_GATE = PASS/FAIL
NO_EMPTY_CANONICAL_FIELD_GATE = PASS/FAIL
FIXED_SLOT_IDENTITY_GATE = PASS/FAIL
ACTIVATION_ZERO_AMPLITUDE_GATE = PASS/FAIL
LATENT_INACTIVE_PARAMETER_GATE = PASS_WITH_LIMITATIONS/FAIL
COMMON_GAIN_FADE_LOCK_GATE = PASS_WITH_LIMITATIONS/FAIL
PHASE_CONTINUITY_GATE = PASS/FAIL
BLOCK_CONSTANCY_GATE = PASS/FAIL
DETERMINISTIC_REPLAY_GATE = PASS/FAIL
OUTPUT_HASH_GATE = PASS/FAIL
INDEPENDENT_GENERATOR_V2_QA = PASS_WITH_LIMITATIONS/FAIL
READY_FOR_120MS_USER_PREVIEW = YES/NO
READY_FOR_LONGER_DARKROOM_EXPORT = YES/NO
```

`READY_FOR_LONGER_DARKROOM_EXPORT=YES` 只表示该相对四槽位参数接口通过结构、确定性和父模型一致性 QA。它不表示暗室绝对功率、跨卫星相关性、真实路径 lifetime、物理 LOS/NLOS 状态或硬件失锁深度已经标定。

## 4. Completion Boundary

若 v2 实现和 QA 全部通过，单个环境 request 将产生：

```text
one environment × one duration × one seed
  -> Low/Mid/High three independent contexts
  -> four fixed structural slots per context
  -> empirical activation masks per 40 ms block
  -> complete latent parameters for inactive NLOS slots
  -> exactly 12 complete rows per millisecond
```

仍不提供：

- 跨 Low/Mid/High 卫星的相关随机过程；
- calibrated absolute RF power；
- inactive latent path 的物理存在声明；
- fitted phase distribution；
- inter-block path identity/lifetime；
- changing elevation within one request；
- waveform synthesis 或 RF playback control。

## 5. Execution Boundary

本计划写入后停止。当前不修改 v1/v2 代码、不生成新的参数表、不运行 Python generator、MATLAB、SAGE 或 batch。

用户批准实施后，执行顺序固定为：

```text
Tasks 1–9 TDD implementation
  -> py_compile and focused tests
  -> freeze v2 config/source hashes
  -> one immutable 120 ms Urban all-band request
  -> validation-only preflight
  -> one Python-only preview generation
  -> independent QA
  -> user review
  -> only then Task 11 full regression/readiness work
```
