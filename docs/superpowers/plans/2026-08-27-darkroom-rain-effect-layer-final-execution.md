# Darkroom Rain Effect Layer Final Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对 Clear、MidRain、HeavyRain 三段 10.23 MHz 实测数据中全部 9 个已映射卫星完成受控 full Rain SAGE、独立 QA、Rain event/path 数据库和可叠加到现有 canonical path table 的经验型雨效应层。

**Architecture:** 工作分为两个串行子项目。子项目 A 只负责 9 个 Rain SAGE 任务、逐任务独立 QA 和冻结的 Rain event/path population；子项目 B 只读取 QA-PASS population，拟合 `Clear -> MidRain` 与 `Clear -> HeavyRain` 的分布级经验传输，并以独立流式适配器作用于现有 v2.2 canonical table。旧 v2.2 generator、生产 SAGE、既有 Rain artifact 和 5 分钟表均保持不可变。

**Tech Stack:** MATLAB Rain branch；Windows PowerShell 7；Python 3.12.9；NumPy 2.5.1；SciPy 1.18.0；CSV/JSON/SHA-256；pytest/unittest。

**Spec:** `docs/DARKROOM_GENERATOR_V2_2_REFERENCE.md`（canonical table 合同）、`docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`（唯一工程状态源）、用户于 2026-08-27 确认“雨效应层固定作用于现有暗室 canonical path table”。

## Global Constraints

- 只处理 `F1023_clear`、`F1023_midrain`、`F1023_heavyrain` 的 9 个冻结任务，采样率固定为 `10230000 Hz`。
- Rain SAGE 使用 `scripts/sage_pipeline/rain/` 独立分支；禁止修改 `scripts/sage_pipeline/run_nav_sage_pipeline.m`，其受保护 SHA-256 必须保持 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。
- 每个执行 request 必须满足 `execution_mode=new_only`、`new_only=true`、`resume_allowed=false`、`max_parallel_matlab=1`。
- MATLAB 只能由正常 Windows 用户 `TJ-CHANNEL\Jing_` 在 PowerShell 7 中人工启动；Codex 不得从 sandbox 启动 MATLAB。
- 一次只执行一个任务；每个任务必须完成 independent QA 后，才允许准备下一个任务。任何失败均停止队列，禁止自动继续。
- 绝对禁止删除 artifact。现有、失败、partial、zero-event、旧 runner 和 QA 文件全部保留；不得覆盖、resume 或静默修正。
- Clear G24 与 HeavyRain G02 的既有 `rain_sage_v1` 目录先做 independent QA；QA PASS 则复用，QA FAIL 则保留并提交新 namespace 设计给用户裁决，不能在原目录重跑。
- Stage0 扫描母集必须完整；Stage1 扫描全部 Stage0 窗口；Stage2 仅处理 Stage1 候选；Stage3/Stage4 按冻结 Rain 配置执行。
- Stage2 `L>=2` 不是 confirmed multipath；Stage3 reliable center 不是 confirmed multipath。
- confirmed criterion 固定为 `joint_valid==1 AND joint_multipath_count>0 AND stage4_joint_paths.is_multipath==1`。
- zero-confirmed-event 只能解释为“在当前 Stage4 联合确认准则下未产生 confirmed multipath event”，不能解释为物理无多径或 LOS。
- Rain 数据没有可用 NMEA/PVT/trajectory/window-level geometry；本计划禁止仰角条件雨效应和 event-level elevation claim。
- 三种天气没有共同 PRN；仅 Clear/MidRain 共有 G24。禁止逐路径相减和伪造跨天气路径对应。
- 雨效应层是 `weather-conditioned empirical transform`，不是已隔离全部混杂因素的普适因果降雨模型。
- canonical table 固定列顺序：`ms,SatelliteID,NLOSPathID,RelativeDelay,RelativeDoppler,RelativeAmplitude,RelativePhase_rad`。
- 单位固定：delay=`ns`，Doppler=`Hz`，amplitude=`linear amplitude ratio`，phase=`rad`。
- 每毫秒顺序固定：`Low path0..3`、`Mid path0..3`、`High path0..3`；每毫秒 12 行。
- v2.2 的 `path_parameter_block_ms=40` 保持不变；NLOS 1/2/3 仍为结构上始终激活且 amplitude 严格大于 0。
- Rain 层不覆盖 path0 的公共增益/失锁过程。Stage4 relative amplitude 以主径归一化，不能据此学习绝对主径雨衰；path0 继续由既有 common-gain/quality/lock 层负责。
- Clear 层必须是 identity；MidRain/HeavyRain 只变换 NLOS 1/2/3 的四维参数。
- 不处理 20.46 MHz，不修改 confirmation criterion，不运行旧 overnight runner。

---

## Frozen Nine-Task Population

权威机器可读清单：`dataset_generation_logs/darkroom_channel_emulation/rain_final_planning_20260827/rain_sage_9_task_checklist.csv`。

| Gate order | Weather | Scene/PRN/channel | Static input | Current output | Required disposition |
|---:|---|---|---|---|---|
| 1 | Clear | `F1023_clear/G24/ch10` | PASS | 19 files exist | Independent QA first; no rerun unless a new namespace is separately approved |
| 2 | HeavyRain | `F1023_heavyrain/G02/ch1` | PASS | 19 files exist | Independent QA first; no rerun unless a new namespace is separately approved |
| 3 | MidRain | `F1023_midrain/G24/ch8` | PASS | absent | First fresh SAGE task; matched-PRN anchor against Clear G24 |
| 4 | MidRain | `F1023_midrain/G20/ch9` | PASS | absent | Second fresh SAGE task; complete MidRain population |
| 5 | Clear | `F1023_clear/G29/ch3` | PASS | absent | Fresh SAGE + QA |
| 6 | Clear | `F1023_clear/G13/ch8` | PASS | absent | Fresh SAGE + QA |
| 7 | Clear | `F1023_clear/G12/ch11` | PASS | absent | Fresh SAGE + QA |
| 8 | HeavyRain | `F1023_heavyrain/G31/ch4` | PASS | absent | Fresh SAGE + QA |
| 9 | HeavyRain | `F1023_heavyrain/G01/ch7` | PASS | absent | Fresh SAGE + QA |

---

### Task 1: Freeze the Rain Full-SAGE Task Contract

**Files:**
- Create: `configs/rain_sage/rain_full_sage_9_task_v1.json`
- Create: `scripts/sage_pipeline/rain/prepare_rain_sage_task_request.py`
- Create: `scripts/sage_pipeline/rain/test_prepare_rain_sage_task_request.py`
- Read only: `dataset_generation_logs/darkroom_channel_emulation/rain_sage_preflight_20260818.csv`
- Read only: `scenes/F1023_clear/metadata.json`
- Read only: `scenes/F1023_midrain/metadata.json`
- Read only: `scenes/F1023_heavyrain/metadata.json`

**Interfaces:**
- Consumes: one of the nine exact `(scene_id, prn, tracking_channel)` records and current source hashes.
- Produces: one immutable `execution_request.json`, one sidecar SHA-256, and one validation-only readiness report; it never invokes MATLAB.

- [ ] **Step 1: Write schema tests before implementation**

```python
def test_frozen_population_has_exactly_nine_unique_tasks():
    records = load_task_contract(CONTRACT)
    assert len(records) == 9
    assert len({(r["scene_id"], r["prn"]) for r in records}) == 9

def test_every_task_is_new_only_10mhz_single_channel():
    for record in load_task_contract(CONTRACT):
        assert record["sample_rate_hz"] == 10_230_000
        assert record["new_only"] is True
        assert record["resume_allowed"] is False
        assert record["max_parallel_matlab"] == 1
        assert isinstance(record["tracking_channel"], int)
```

- [ ] **Step 2: Run the contract tests and verify they fail because files do not yet exist**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  'E:\GNSS_Multipath_Project\scripts\sage_pipeline\rain\test_prepare_rain_sage_task_request.py' -q
```

Expected: FAIL on missing contract/preparer, not on an unrelated import error.

- [ ] **Step 3: Implement the exact contract schema**

Each JSON task record must contain:

```json
{
  "task_id": "rain_full_sage_v1__F1023_midrain__G24__ch8",
  "weather_condition": "MidRain",
  "scene_id": "F1023_midrain",
  "prn": "G24",
  "tracking_channel": 8,
  "sample_rate_hz": 10230000,
  "raw_path": "absolute path resolved from metadata.json",
  "raw_size_bytes": 2903638528,
  "tracking_path": "absolute mapped tracking MAT path",
  "telemetry_path": "absolute mapped telemetry DAT path",
  "navigation_path": "absolute navigation XML path",
  "expected_output_namespace": "E:\\GNSS_Multipath_Project\\scenes\\F1023_midrain\\sage_results\\rain_sage_v1\\G24",
  "execution_mode": "new_only",
  "new_only": true,
  "resume_allowed": false,
  "max_parallel_matlab": 1,
  "gold_labels_used_for_selection": false
}
```

The preparer must resolve actual paths from metadata and mapping artifacts, calculate hashes for metadata, tracking, telemetry, navigation, Rain MATLAB sources, wrapper and request, and reject direct user-supplied channel/raw/output overrides.

- [ ] **Step 4: Add fail-closed tests**

Cover: wrong PRN/channel, 20.46 MHz, raw missing, telemetry missing, tracking missing, output already exists for a fresh task, altered source hash, duplicate task, `Resume=true`, and a task not in the frozen nine-task contract.

- [ ] **Step 5: Run tests, py_compile and diff check**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m py_compile `
  'E:\GNSS_Multipath_Project\scripts\sage_pipeline\rain\prepare_rain_sage_task_request.py'
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  'E:\GNSS_Multipath_Project\scripts\sage_pipeline\rain\test_prepare_rain_sage_task_request.py' -q
git -C 'E:\GNSS_Multipath_Project' diff --check
```

- [ ] **Step 6: Review and commit the contract implementation**

```powershell
git add -- 'configs/rain_sage/rain_full_sage_9_task_v1.json' `
  'scripts/sage_pipeline/rain/prepare_rain_sage_task_request.py' `
  'scripts/sage_pipeline/rain/test_prepare_rain_sage_task_request.py'
git commit -m 'feat: freeze nine-task rain SAGE contract'
```

### Task 2: Independently QA Existing Clear G24 and HeavyRain G02

**Files:**
- Create: `scripts/sage_pipeline/rain/audit_rain_sage_task.py`
- Create: `scripts/sage_pipeline/rain/test_audit_rain_sage_task.py`
- Read only: `scenes/F1023_clear/sage_results/rain_sage_v1/G24/**`
- Read only: `scenes/F1023_heavyrain/sage_results/rain_sage_v1/G02/**`
- Produce new-only: `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_qa_20260827/<task_id>/`

**Interfaces:**
- Consumes: exact task contract record plus one existing output directory.
- Produces: `qa_result.json`, `qa_report.md`, `artifact_hashes.csv`; status is `QA_PASS`, `QA_FAIL`, or `INCONCLUSIVE`.

- [ ] **Step 1: Write tests for strict Stage semantics and artifact completeness**

```python
def test_confirmed_event_requires_all_three_conditions():
    assert confirmed(joint_valid=1, joint_multipath_count=1, has_mp_path=True)
    assert not confirmed(joint_valid=1, joint_multipath_count=0, has_mp_path=True)
    assert not confirmed(joint_valid=1, joint_multipath_count=1, has_mp_path=False)

def test_header_only_stage4_is_valid_zero_event_when_pipeline_completed():
    result = audit_fixture("header_only_stage4")
    assert result["confirmed_events"] == 0
    assert result["scientific_status"] == "VALID_ZERO_CONFIRMED_EVENT"
```

- [ ] **Step 2: Implement read-only QA**

The auditor must verify identity, required 19-file set, readable CSV/MAT presence, Stage0 symbol/window identities, Stage1 scanned rows, Stage2 `4 × selected_windows` model accounting, Stage3-to-Stage4 center linkage, finite confirmed path fields, phase availability semantics, output isolation and hashes. It must not edit source artifacts.

- [ ] **Step 3: Run unit tests**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  'E:\GNSS_Multipath_Project\scripts\sage_pipeline\rain\test_audit_rain_sage_task.py' -q
```

- [ ] **Step 4: Audit G24 and G02 in separate new-only QA namespaces**

Expected pre-audit counts to reconcile, not to force:

```text
Clear G24: Stage0 windows=2204, Stage2 selected=120, Stage3=3, Stage4=3,
           confirmed events=0, confirmed paths=0.
Heavy G02: Stage0 windows=2863, Stage2 selected=120, Stage3=6, Stage4=6,
           confirmed events=1, confirmed paths=1.
```

- [ ] **Step 5: Apply the gate**

If both pass, mark their checklist disposition `QA_ACCEPTED_EXISTING`. If either fails or is inconclusive, preserve it and stop; do not generate a rerun request until a new versioned output namespace is explicitly approved.

### Task 3: Implement a Single-Task Rain Execution Wrapper

**Files:**
- Create: `scripts/sage_pipeline/rain/Invoke-RainSageWindows.ps1`
- Create: `scripts/sage_pipeline/rain/test_invoke_rain_sage_windows.py`
- Read only: `scripts/sage_pipeline/rain/run_rain_sage_pipeline.m`
- Do not modify: `scripts/sage_pipeline/run_nav_sage_pipeline.m`

**Interfaces:**
- Consumes: only `-RequestManifest` and `-ExpectedRequestSha256`.
- Produces in validation-only mode: readiness receipt and exact MATLAB expression without starting MATLAB.
- Produces in execute mode: stdout/stderr, process receipt and immutable output hashes for one task.

- [ ] **Step 1: Write PowerShell contract tests**

Tests must reject wrong request SHA, altered request, direct scene/channel overrides, output already present, `Resume=true`, 20.46 MHz, missing input, changed Rain source hash, non-normal-user identity and a second simultaneous task.

- [ ] **Step 2: Implement validation-only as the default**

The generated MATLAB call must have this semantic form:

```matlab
run_rain_sage_pipeline("F1023_midrain", "G24", ...
    "TrackingChannel", 8, ...
    "ProjectRoot", "E:\GNSS_Multipath_Project", ...
    "Resume", false, ...
    "PreflightOnly", false)
```

Validation-only must report `matlab_invoked=false`, show the exact task/input/output/hashes and reject an existing output namespace.

- [ ] **Step 3: Implement explicit execution gate**

Execution requires both `-Execute` and `-ConfirmRainSage`. It must acquire one global Rain runner lock, preserve partial output on failure, write interruption/failure receipt, release the lock, and never auto-start another task.

- [ ] **Step 4: Run static and synthetic tests**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  'E:\GNSS_Multipath_Project\scripts\sage_pipeline\rain\test_invoke_rain_sage_windows.py' -q
powershell.exe -NoProfile -Command "[void][System.Management.Automation.Language.Parser]::ParseFile('E:\GNSS_Multipath_Project\scripts\sage_pipeline\rain\Invoke-RainSageWindows.ps1',[ref]`$null,[ref]`$null)"
git -C 'E:\GNSS_Multipath_Project' diff --check
```

- [ ] **Step 5: Commit the wrapper only after validation-only proves `Resume=false`**

```powershell
git add -- 'scripts/sage_pipeline/rain/Invoke-RainSageWindows.ps1' `
  'scripts/sage_pipeline/rain/test_invoke_rain_sage_windows.py'
git commit -m 'feat: add single-task rain SAGE executor'
```

### Task 4: Execute and QA the Seven Missing Rain SAGE Tasks

**Files:**
- Create per task: `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_execution_requests_20260827/<task_id>/execution_request.json`
- Create per task: `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_execution_20260827/<task_id>/`
- Write SAGE only to the exact absent `scenes/<scene>/sage_results/rain_sage_v1/<PRN>` namespace.
- Update only the planning checklist after independent QA; never rewrite SAGE outputs.

**Interfaces:**
- Consumes: Tasks 1–3 and a user-approved exact PowerShell command.
- Produces: seven full Stage0–Stage4 outputs and seven independent QA reports, one at a time.

- [ ] **Step 1: Prepare, validate and execute MidRain G24/ch8**

Prepare its immutable request, run validation-only, verify `'Resume', false`, obtain explicit user approval, execute as `TJ-CHANNEL\Jing_`, then run independent QA. Stop if the task is not `QA_PASS`.

- [ ] **Step 2: Prepare, validate and execute MidRain G20/ch9**

Repeat the full request → validation-only → human execution → independent QA chain. Stop if not `QA_PASS`.

- [ ] **Step 3: Prepare, validate and execute Clear G29/ch3**

Repeat the full gated chain. Do not derive scientific conclusions from event count during execution.

- [ ] **Step 4: Prepare, validate and execute Clear G13/ch8**

Repeat the full gated chain and retain valid zero-event output if produced.

- [ ] **Step 5: Prepare, validate and execute Clear G12/ch11**

Repeat the full gated chain and record actual runtime rather than predicting it.

- [ ] **Step 6: Prepare, validate and execute HeavyRain G31/ch4**

Repeat the full gated chain; no task may start automatically after it.

- [ ] **Step 7: Prepare, validate and execute HeavyRain G01/ch7**

Repeat the full gated chain and close the nine-task execution population only if all existing/fresh outputs have independent QA PASS.

- [ ] **Step 8: Verify protected production hash and no-delete receipt after every task**

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath `
  'E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m').Hash.ToLowerInvariant()
```

Expected exactly: `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`.

### Task 5: Freeze the Nine-Task Completion Census

**Files:**
- Create: `scripts/sage_pipeline/rain/summarize_rain_full_sage_population.py`
- Create: `scripts/sage_pipeline/rain/test_summarize_rain_full_sage_population.py`
- Produce: `dataset_generation_logs/darkroom_channel_emulation/rain_full_sage_population_20260827/`

**Interfaces:**
- Consumes: exactly nine QA results and source artifact hashes.
- Produces: `task_summary.csv`, `stage_statistics.csv`, `confirmed_event_path_counts.csv`, `population_manifest.json`, `population_report.md`.

- [ ] **Step 1: Write tests that require exactly nine unique QA-PASS tasks**

The summarizer must reject duplicate scene/PRN, missing weather, missing QA, a task outside the frozen matrix, an altered artifact hash and any non-PASS task.

- [ ] **Step 2: Implement the census without reading raw IQ**

Include Stage0 symbols/windows, Stage1 scanned/selected, Stage2 evaluations and L1–L4 selection, Stage3 reliable centers, Stage4 rows/joint-valid, confirmed events/paths, runtime, hashes and zero-confirmed semantics.

- [ ] **Step 3: Run the census and freeze its SHA-256 manifest**

Release gate:

```text
RAIN_FULL_SAGE_TASKS_QA_PASS = 9/9
RAIN_WEATHER_CLASSES_PRESENT = Clear,MidRain,HeavyRain
RAIN_MODELING_POPULATION_FROZEN = YES
```

### Task 6: Build the Rain Event/Path Database

**Files:**
- Create: `scripts/analysis/channel_modeling/build_rain_event_path_database_v1.py`
- Create: `scripts/analysis/channel_modeling/tests/test_build_rain_event_path_database_v1.py`
- Produce: `dataset/rain_effect_database/v1/partitions/ingestion_id=<frozen-id>/`

**Interfaces:**
- Consumes: Task 5 population manifest and Stage0/Stage4 CSVs from QA-PASS tasks only.
- Produces: `facts/rain_runs.csv`, `facts/rain_events.csv`, `facts/rain_paths.csv`, `ingestion_manifest.json`, `ingestion_report.md`.

- [ ] **Step 1: Define and test database keys**

```text
run_id   = weather + scene_id + prn + tracking_channel
event_id = run_id + center_window_id
path_id  = event_id + stage4 path_id
```

Tests must enforce uniqueness, source-row traceability and SHA-256 provenance.

- [ ] **Step 2: Implement `rain_runs.csv`**

Store all nine runs including valid-window denominator, duration, zero-confirmed status, confirmed counts and QA status. A zero-confirmed row remains a valid run, not a LOS label.

- [ ] **Step 3: Implement `rain_events.csv` and `rain_paths.csv`**

Only confirmed events/paths use the strict Stage4 criterion. Preserve:

```text
excess_delay_samples
doppler_offset_hz
mean_relative_power_db
relative_amplitude
phase_rad
relative_phase_rad
relative_phase_available
```

- [ ] **Step 4: Add science-boundary tests**

Reject Stage2/Stage3 rows as confirmed data, reject non-finite confirmed parameters, and verify no elevation field is synthesized.

- [ ] **Step 5: Run tests and freeze the ingestion manifest**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  'E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_build_rain_event_path_database_v1.py' -q
```

### Task 7: Fit the Weather-Conditioned Empirical Transport

**Files:**
- Create: `configs/channel_modeling/darkroom_rain_effect_layer_v1.json`
- Create: `scripts/analysis/channel_modeling/fit_darkroom_rain_effect_layer_v1.py`
- Create: `scripts/analysis/channel_modeling/tests/test_fit_darkroom_rain_effect_layer_v1.py`
- Produce: `dataset_generation_logs/channel_modeling/darkroom_rain_effect_layer_v1_models/<model_id>/`

**Interfaces:**
- Consumes: frozen Rain database plus exact ingestion-manifest SHA-256.
- Produces: `rain_effect_model.json`, `marginal_transforms.csv`, `joint_rank_donor_pool.csv`, `support_summary.csv`, `fit_manifest.json`, `fit_report.md`.

- [ ] **Step 1: Freeze the fitting contract before reading outcome summaries**

The model contract must state:

```text
Clear       = identity baseline
MidRain     = empirical Clear-to-MidRain transport
HeavyRain   = empirical Clear-to-HeavyRain transport
weighting   = equal total weight per PRN within each weather
uncertainty = PRN-block bootstrap
geometry    = unavailable; no elevation-conditioned rain fit
```

- [ ] **Step 2: Write transformation tests**

```python
def test_clear_is_exact_identity():
    assert apply_effect(BASE_ROW, weather="Clear", seed=7) == BASE_ROW

def test_nlos_amplitude_remains_strictly_positive():
    assert apply_effect(NLOS_ROW, weather="HeavyRain", seed=7)["RelativeAmplitude"] > 0.0

def test_phase_is_wrapped_half_open():
    phase = apply_effect(NLOS_ROW, weather="MidRain", seed=7)["RelativePhase_rad"]
    assert -math.pi <= phase < math.pi
```

- [ ] **Step 3: Implement the marginal domains**

Use these exact transformed domains:

```text
delay:     z_tau = log1p(RelativeDelay_ns), output max(0, expm1(z_tau'))
doppler:   z_f   = signed RelativeDoppler_Hz, output z_f'
amplitude: z_a   = 20*log10(RelativeAmplitude), output 10**(z_a'/20)
phase:     circular offset wrapped to [-pi, pi)
```

- [ ] **Step 4: Implement coupled empirical transport**

For each target-weather donor path, compute its four marginal ranks within that weather. Map those ranks through both target and Clear inverse empirical CDFs to create a coupled delta vector. Apply the vector to one 40 ms base block. Use the same donor row for delay/Doppler/amplitude/phase so the four changes are not independently shuffled.

- [ ] **Step 5: Keep matched G24 as an audit diagnostic**

Clear G24 versus MidRain G24 must be reported separately as a matched-PRN anchor, but it must not be used to select favorable thresholds, remove other PRNs or create path-to-path correspondences.

- [ ] **Step 6: Define support states**

```text
MEASURED_EMPIRICAL: target weather has confirmed-path support
PARTIAL_POOL: support exists but bootstrap interval is unstable or PRN count is small
PRIOR_ONLY: no confirmed target-weather path; use the frozen parent path prior and prohibit measured-effect claims
```

The fitter must fail closed if Clear has no confirmed-path support because the required baseline transport cannot be identified.

- [ ] **Step 7: Run unit tests and freeze the model hash**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  'E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_fit_darkroom_rain_effect_layer_v1.py' -q
```

### Task 8: Implement the Canonical-Table Rain-Layer Adapter

**Files:**
- Create: `scripts/analysis/channel_modeling/apply_darkroom_rain_effect_layer_v1.py`
- Create: `scripts/analysis/channel_modeling/tests/test_apply_darkroom_rain_effect_layer_v1.py`
- Do not modify: `scripts/analysis/channel_modeling/darkroom_generator_v2_2_core.py`

**Interfaces:**
- Consumes: immutable v2.2 canonical table, source table SHA, Rain model manifest/SHA, weather, seed and new output namespace.
- Produces: a seven-column canonical table with identical row order plus separate provenance/receipt files.

- [ ] **Step 1: Write schema/order tests**

```python
EXPECTED_COLUMNS = [
    "ms", "SatelliteID", "NLOSPathID", "RelativeDelay",
    "RelativeDoppler", "RelativeAmplitude", "RelativePhase_rad",
]

def test_each_ms_has_exact_low_mid_high_path_order():
    assert rows_for_ms(OUTPUT, 1) == [
        ("Low", 0), ("Low", 1), ("Low", 2), ("Low", 3),
        ("Mid", 0), ("Mid", 1), ("Mid", 2), ("Mid", 3),
        ("High", 0), ("High", 1), ("High", 2), ("High", 3),
    ]
```

- [ ] **Step 2: Implement chunked streaming**

Process complete 40 ms blocks only; never split a 480-row block (`40 ms × 12 rows/ms`) across transform state. Preserve `ms`, `SatelliteID`, `NLOSPathID` and the exact seven-column order.

- [ ] **Step 3: Implement path0 pass-through and NLOS transform**

`NLOSPathID=0` is byte-value-equivalent in its four parameter fields before and after the Rain layer. `NLOSPathID=1/2/3` receive the target-weather coupled transform and retain strictly positive amplitude.

- [ ] **Step 4: Preserve phase continuity**

At each 40 ms block start, apply the sampled circular phase offset once. Within the block, preserve the existing 1 ms Doppler phase evolution and wrap each output to `[-pi, pi)`.

- [ ] **Step 5: Add deterministic seed/hash tests**

Same source hash + model hash + weather + seed must produce the same output hash. Changing the seed may change sampled effect vectors but must not change schema, row identity, task scope or model provenance.

- [ ] **Step 6: Run tests and static checks**

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m py_compile `
  'E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\apply_darkroom_rain_effect_layer_v1.py'
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' -m pytest `
  'E:\GNSS_Multipath_Project\scripts\analysis\channel_modeling\tests\test_apply_darkroom_rain_effect_layer_v1.py' -q
```

### Task 9: Perform Gold-Free Model and Adapter QA

**Files:**
- Create: `scripts/analysis/channel_modeling/audit_darkroom_rain_effect_layer_v1.py`
- Create: `scripts/analysis/channel_modeling/tests/test_audit_darkroom_rain_effect_layer_v1.py`
- Produce new-only: `dataset_generation_logs/channel_modeling/darkroom_rain_effect_layer_v1_qa/<qa_id>/`

**Interfaces:**
- Consumes: frozen model and deterministic 120 ms test outputs.
- Produces: `qa_result.json`, `qa_report.md`, `distribution_checks.csv`, `canonical_contract_checks.csv`.

- [ ] **Step 1: Generate a deterministic 120 ms preview**

Use three complete 40 ms blocks and all three weather modes. This is Python-only adapter validation, not a new SAGE experiment.

- [ ] **Step 2: Verify canonical constraints**

Check exact columns, 12 rows/ms, Low→Mid→High ordering, path IDs 0–3, finite values, nonnegative delay, positive NLOS amplitude, wrapped phase, 40 ms block consistency and path0 pass-through.

- [ ] **Step 3: Verify distribution behavior**

Check Clear identity, Mid/Heavy target marginal reproduction, joint rank dependence, PRN-bootstrap uncertainty, support status, no silent `PRIOR_ONLY` promotion to empirical evidence and no event-level elevation claim.

- [ ] **Step 4: Verify effect-layer composition order**

Audit receipts must record:

```text
base environment/elevation path model
-> rain effect layer
-> existing quality/common-gain/lock layer
-> canonical output
```

The Rain layer must not reapply the quality envelope or alter the lock-state timeline.

- [ ] **Step 5: Apply release gates**

```text
EXECUTION_OUTPUT_PASS       = all artifacts/hash/schema complete
RAIN_MODEL_SUPPORT_PASS     = Clear baseline identified and each released target has measured or explicitly tagged prior support
CANONICAL_ADAPTER_PASS      = exact seven-column contract and deterministic output
SCIENTIFIC_SCOPE_PASS       = empirical weather transform; no causal/elevation overclaim
```

### Task 10: Build the Final 24-Combination Darkroom Package

**Files:**
- Create: `scripts/analysis/channel_modeling/prepare_darkroom_rain_effect_matrix_v1.py`
- Create: `scripts/analysis/channel_modeling/run_darkroom_rain_effect_matrix_v1.py`
- Create: `scripts/analysis/channel_modeling/tests/test_darkroom_rain_effect_matrix_v1.py`
- Produce new-only: `dataset_generation_logs/channel_modeling/darkroom_rain_effect_layer_v1_collections/<collection_id>/`

**Interfaces:**
- Consumes: the eight existing v2.2 environment×quality tables and one frozen Rain model.
- Produces: 24 logical combinations = 4 environments × 2 quality states × 3 weather states.

- [ ] **Step 1: Freeze a 24-cell manifest**

Each cell must record base environment, quality mode, weather, source table/hash, model/hash, seed, duration and output namespace. Clear cells are identity references; MidRain and HeavyRain cells produce new transformed tables.

- [ ] **Step 2: Run validation-only**

Require `accepted_rows=24`, `rejected_rows=0`, all Mid/Heavy output namespaces absent, all source/model hashes valid and no MATLAB/SAGE/raw access.

- [ ] **Step 3: Execute a 120 ms 24-cell smoke**

Run only after Task 9 PASS. Perform independent matrix QA; preserve all failed/partial namespaces.

- [ ] **Step 4: Execute the 5-minute package only after smoke QA PASS**

The 5-minute package contains 24 logical combinations. To avoid unnecessary duplication, its manifest may reference the eight immutable Clear source tables while physically generating the 16 MidRain/HeavyRain transformed tables. A hardware-export step may later materialize 24 standalone files without changing scientific values.

- [ ] **Step 5: Freeze package receipt and hashes**

Record 24-cell status, row counts, source/model/output hashes, seed, execution environment and no-experiment flags for the Python transformation stage.

### Task 11: Final Documentation and Handoff Synchronization

**Files:**
- Create after validation: `docs/DARKROOM_RAIN_EFFECT_LAYER_V1_REFERENCE.md`
- Modify: `docs/DARKROOM_GENERATOR_V2_2_REFERENCE.md`
- Modify: `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`
- Do not modify Paper Handoff unless the user separately approves a paper claim.

**Interfaces:**
- Consumes: all QA-PASS receipts, database/model/package manifests and hashes.
- Produces: one stable Rain-layer reference and updated authoritative engineering status.

- [ ] **Step 1: Record controlled status vocabulary**

Use only:

```text
Rain full SAGE: Completed only after 9/9 independent QA PASS
Rain database: Completed only after ingest QA PASS
Rain effect layer: Implemented after code/tests; Validated only after model/adapter QA PASS
24-cell package: Completed only after manifest, execution and independent matrix QA PASS
Darkroom hardware replay: Not started until actual replay evidence exists
```

- [ ] **Step 2: Record limitations prominently**

Document one recording per weather, unmatched PRNs, G24-only Clear/Mid anchor, absent geometry, unavailable absolute main-path rain attenuation and the distinction between empirical transformation and causal rain physics.

- [ ] **Step 3: Record all immutable hashes and next decision**

Handoff must identify exact task/database/model/package manifests and QA locations. It must not convert `PARTIAL_POOL` or `PRIOR_ONLY` into measured evidence.

---

## Operational Stop Rules

Stop immediately and preserve artifacts if any of the following occurs:

- request/hash/source mismatch;
- output namespace already exists for a fresh task;
- `Resume=true` appears anywhere;
- MATLAB startup marker absent or exit code nonzero;
- task identity differs from frozen scene/PRN/channel/rate;
- any required Stage output is missing or unreadable;
- Stage linkage or strict confirmed criterion fails;
- protected production SHA changes;
- a target weather has no empirical support and the result is not explicitly marked `PRIOR_ONLY`;
- canonical output changes column order, per-ms row order, units, path0 values or NLOS positivity;
- any script attempts deletion, resume, automatic next-task execution or writes to old v2.2/Rain namespaces.

## Final Acceptance Definition

The darkroom Rain experiment branch is complete only when all conditions hold:

```text
RAIN_SAGE_9_TASK_QA_PASS = 9/9
RAIN_EVENT_PATH_DATABASE_QA = PASS
CLEAR_BASELINE_MODEL = IDENTIFIED
MIDRAIN_EFFECT_LAYER = VALIDATED_OR_EXPLICITLY_PRIOR_TAGGED
HEAVYRAIN_EFFECT_LAYER = VALIDATED_OR_EXPLICITLY_PRIOR_TAGGED
CANONICAL_ADAPTER_QA = PASS
RAIN_24_LOGICAL_CELL_SMOKE_QA = PASS
RAIN_5MIN_PACKAGE_QA = PASS
PRODUCTION_PIPELINE_SHA_UNCHANGED = YES
FILES_DELETED_COUNT = 0
```

This completes the software/data preparation for darkroom replay. It does not itself prove hardware replay validity or a universal physical rain channel model.
