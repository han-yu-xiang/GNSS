# 10 MHz Full SAGE Production T1-2 G25 Independent QA Report

## 1. Task information

| Item | Value |
|---|---|
| VTC task | T1-2 |
| Scene | `F1023_V80_D0117_P8` |
| PRN | `G25` |
| Tracking channel | `ch10` |
| Sample rate | `10230000 Hz` |
| Environment metadata | `Highway/Open` |
| Geometry planning context | `HIGH`, mean elevation approximately `79.0°` |
| Execution ID | `batch_sage_execution_20260814T075945Z` |
| Output namespace | `scenes/F1023_V80_D0117_P8/sage_results/nav_sage_v2/G25` |

The Highway/Open and HIGH labels are scene/PRN planning context. They are not event-level elevation labels and do not predict multipath outcome.

## 2. Execution contract QA

**Execution Contract QA: PASS**

Evidence was read from the immutable request, environment receipt, execution receipt, actual batch execution log, status history, and task log. The request SHA-256 was independently recomputed as:

`efd3bec67010856cdf1196202369f927224403015048277f4f57116e5029bb43`

Key frozen provenance:

- Production manifest SHA-256: `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`
- Task-record SHA-256: `a9a3b7a2d158f4a39a4d7e9a2a40a922983d188f8c1ffc49616fae2a7e86f1f3`
- Pipeline SHA-256: `5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab`
- Executor SHA-256: `bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b`
- Windows wrapper SHA-256: `dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3`

Execution evidence:

- Windows identity: `TJ-CHANNEL\Jing_`
- PowerShell: `7.6.4`
- Python exit code: `0`
- Task exit code: `0`
- MATLAB startup marker: `MATLAB_STARTUP_OK`
- MATLAB smoke exit code: `0`
- MATLAB executable version: `25.1.0.2802752`
- Execution duration: `3800.307 s` (`63.338 min`); wrapper receipt duration: `3800.499 s`
- Actual MATLAB command contained `Resume=false`:

  `run_nav_sage_pipeline('F1023_V80_D0117_P8', 'G25', 'TrackingChannel', 10, 'ProjectRoot', 'E:\GNSS_Multipath_Project', 'Resume', false);`

No `Resume=true` occurrence was found in the actual execution evidence.

## 3. New-only policy QA

**New-only Policy QA: PASS**

- The pre-execution receipt records `target_output_namespace_exists=false` and `global_runner_lock_exists=false`.
- The output namespace was created after execution began; it was absent during preflight.
- The task log starts with Stage0 construction and then reports Stage1 progress from `20 / 1142` through `1142 / 1142`.
- No `Stage loaded`, `loaded checkpoint`, `resume checkpoint`, `existing result reuse`, or equivalent checkpoint-reuse record was found.
- `new_only=true` and `resume_allowed=false` are present in both the request and executor receipt.
- The current active global runner lock is absent. The per-task lock file retained under the historical execution directory is an execution receipt artifact, not an active lock.

The output is therefore treated as a fresh run. No old Stage checkpoint or prior result was reused.

## 4. Artifact completeness QA

**Artifact Completeness: PASS**

The output namespace contains **21 files**, all non-empty. The required schema files are present:

- `run_context.json`, `run_context.mat`;
- Stage0 catalog, symbols, windows, and `doppler_sign.mat`;
- Stage1 CSV, MAT, and progress MAT;
- Stage2 model orders, selected windows, selected paths, L1–L4 MAT, and progress MAT;
- Stage3 persistence, reliable centers, and MAT;
- Stage4 joint summary, joint paths, and MAT;
- `G25_nav_sage_overview.png`.

No missing required file, zero-byte file, abnormal-termination marker, or malformed CSV/JSON was observed. The run context matches scene `F1023_V80_D0117_P8`, PRN `G25`, channel `10`, and `10230000 Hz`.

## 5. Stage statistics and consistency

| Stage | Result |
|---|---:|
| Stage0 valid NAV symbols | 1144 |
| Stage0 complete 40 ms windows | 1142 |
| Stage1 scanned windows | 1142 |
| Stage1 selected windows | 112 |
| Stage2 model evaluations | 448 |
| Stage2 final L=1 / L=2 / L=3 / L=4 | 38 / 13 / 12 / 49 |
| Stage2 L>=2 / L>=3 | 74 / 61 |
| Stage3 persistence rows | 184 |
| Stage3 reliable centers | 8 |
| Stage4 joint rows | 8 |
| Stage4 `joint_valid=1` rows | 8 |
| Stage4 rows with `joint_multipath_count>0` | 2 |

The Stage chain is complete and linked as Stage0 → Stage1 → Stage2 → Stage3 → Stage4. The 74 Stage2 L>=2 selections and 8 Stage3 reliable centers are intermediate evidence; neither is counted as confirmed multipath.

Reliable centers are windows `970`, `971`, `982`, `985`, `986`, `1062`, `1063`, and `1064`.

## 6. Scientific validity QA

**Scientific Validity: PASS**

The fixed confirmation criterion was applied without modification:

```text
joint_valid == 1
AND joint_multipath_count > 0
AND matching stage4_joint_paths.is_multipath == 1
```

There are 2 confirmed event centers and 2 confirmed multipath paths. The other 6 Stage4 joint rows are valid joint results with `joint_multipath_count=0`; they are valid Stage4 rejection/zero-multipath outcomes under the criterion, not evidence that the satellite or environment is physically multipath-free.

Confirmed events and paths:

| Center window | Recording time (s) | Joint L | Path | Excess delay (samples) | Excess delay (chips) | Relative Doppler (Hz) | Relative power (dB) | Coherence | Snapshot wins vs L1 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 985 | 60.5369477028 | 2 | 2 | 1.1 | 0.11 | -4.7159073064 | -7.8526072870 | 0.8733628888 | 5 |
| 970 | 60.2369466276 | 2 | 2 | 1.2 | 0.12 | -10.7135060438 | -11.3878729184 | 0.8089162440 | 5 |

The confirmed path fields are finite, event/path mappings are unique, and no NaN/Inf occurs in confirmed path rows. Six valid zero-multipath Stage4 summary rows contain `NaN` for `minimum_multipath_power_db`, which is the expected non-applicable value when no multipath component is present; it is not used as a confirmed path parameter.

## 7. VTC evidence impact

- Highway/Open formal-production evidence: **AVAILABLE**.
- HIGH planning-context evidence: **AVAILABLE, scene/PRN level only**.
- Confirmed path contribution: **+2 events / +2 paths**.
- Figure 2 representative multipath case: **CANDIDATE**, subject to comparison with existing QA-passed cases.
- Figure 3 hierarchical filtering: **ALREADY_SUFFICIENT**; T1-2 supplies an additional traceable case but does not change the established hierarchy evidence.
- Figure 4 path/environment characterization: **PARTIAL**; path-level delay/Doppler/power are available, while event-level elevation dependence remains unvalidated.

T1-2 closes the current Highway/Open production evidence gap for one independently QA-passed scene. It does not establish a Highway/Open statistical law, an elevation effect, or a complete environment database.

## 8. T1-3 necessity assessment

`T1_3_RECOMMENDATION = REQUIRED`

Mountain/Valley remains the principal formal-production environment gap before the VTC minimum evidence stop condition. This is a planning decision only; no T1-3 request was generated and no next task was started.

`NEXT_VTC_DECISION_REQUIRED = YES`

## 9. Production acceptance

`T1_2_PRODUCTION_QA = PASS`

This task may be counted as an accepted 10.23 MHz production task after the production summary is refreshed. The immutable production manifest and request remain unchanged. No automatic T1-3 continuation is authorized.

## 10. Evidence locations

- Immutable request: `dataset_generation_logs/batch_sage_execution_requests/vtc_priority_t1_2_v80p8_g25_20260814/execution_request.json`
- Environment receipt and smoke logs: `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/vtc_priority_t1_2_v80p8_g25_20260814_20260814T075937436Z/`
- Execution receipt: `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/vtc_priority_t1_2_v80p8_g25_20260814_20260814T075937436Z/execution_receipt.json`
- Execution log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T075945Z/batch_execution_log.csv`
- Task log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T075945Z/task_logs/F1023_V80_D0117_P8__G25__ch10__nav_sage_v2.log`
- SAGE output: `scenes/F1023_V80_D0117_P8/sage_results/nav_sage_v2/G25/`

## 11. Execution and modification record

- Raw IQ content read during QA: **no**
- MATLAB run during QA: **no**
- SAGE run during QA: **no**
- New production task started during QA: **no**
- T1-3 request generated: **no**
- Existing SAGE artifact/request/manifest modified by QA: **no**

The only new artifact from this QA action is this independent report; monitoring and handoff updates are recorded separately as authorized by the T1-2 QA procedure.
