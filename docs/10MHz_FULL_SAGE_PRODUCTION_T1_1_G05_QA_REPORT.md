# 10.23 MHz Full SAGE Production T1-1 G05 Independent QA Report

## Overall decision

`T1_1_PRODUCTION_QA = PASS`

The task completed the full Stage0–Stage4 pipeline in its new-only output namespace. Execution, artifact completeness, Stage consistency, and scientific-validity checks all pass under the current fixed Stage4 confirmation criterion. This report is an independent read-only QA record; it does not rerun or modify the production artifact.

## 1. Task information

| Field | Value |
|---|---|
| VTC task | `T1-1` |
| Scene | `F1023_V70_D0120_P9` |
| PRN | `G05` |
| Tracking channel | `ch10` / numeric channel `10` |
| Sample rate | `10230000 Hz` |
| Environment metadata | `Special Reflective` |
| Scene annotation | `Bridge over wide water surface` |
| Road type | `bridge over water` |
| Vehicle speed metadata | `70 km/h` |
| Geometry planning context | `LOW`, mean elevation approximately `19.327°` |
| Production task | `F1023_V70_D0120_P9__G05` |
| Wrapper task | `F1023_V70_D0120_P9__G05__ch10__nav_sage_v2` |

The environment fields are metadata/scene-level annotations. The LOW mean-elevation summary is a planning-context statistic and is not assigned to individual confirmed events without a separate window-level geometry alignment analysis.

## 2. Request and execution provenance

Immutable request:

`E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\vtc_priority_t1_1_d0120p9_g05_20260814\execution_request.json`

Request SHA-256:

`feebda81d6f541c012d0cd898deb0142cacd3e9d28fc83deb634cf827dd9c194`

All rechecked request and source hashes matched:

- Production manifest: `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`
- Plan snapshot: `d2069fcaecec6b6578a971e1bd76e352e2919cf531daff81afbb15756f683644`
- Selection snapshot: `2245695cff9fb34d7f49be041d139919db932c7e83471c00c444d6633a5203c7`
- Task record: `6dd7936ead88fb12a8bef24d2698ae5952fc1870820debaad3c10da75467078c`
- Pipeline: `5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab`
- Python executor: `bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b`
- Windows wrapper: `dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3`

Execution evidence:

- Execution ID: `batch_sage_execution_20260814T060453Z`
- Execution log: `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260814T060453Z\batch_execution_log.csv`
- Wrapper receipt directory: `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\windows_runner_receipts\vtc_priority_t1_1_d0120p9_g05_20260814_20260814T060440076Z`
- Windows identity: `TJ-CHANNEL\Jing_`
- PowerShell: `7.6.4`
- MATLAB: `D:\Program Files\Matlab\bin\matlab.exe`, file version `25.1.0.2802752`
- MATLAB startup smoke: marker present, exit code `0`
- Python executable: `C:\Users\Jing_\AppData\Local\Programs\Python\Python312\python.exe`, exit code `0`
- Task exit code: `0`
- Task status: `completed`
- Runtime: `4696.042 s` (`78.267 min`)

The recorded MATLAB invocation was:

```text
D:\Program Files\Matlab\bin\matlab.exe -batch addpath('E:\GNSS_Multipath_Project\scripts\sage_pipeline'); run_nav_sage_pipeline('F1023_V70_D0120_P9', 'G05', 'TrackingChannel', 10, 'ProjectRoot', 'E:\GNSS_Multipath_Project', 'Resume', false);
```

`'Resume', false` is present and no `'Resume', true` occurrence was found in the real execution evidence.

### Execution Contract QA: PASS

The request identity, request hash, manifest/task/source hashes, approved scope, execution ID, Windows receipt, MATLAB smoke result, Python exit code, task exit code, runtime, and real command preview are mutually consistent.

## 3. New-only Policy QA

### New-only Policy QA: PASS

The pre-execution preflight recorded the target namespace as absent. The execution started from the empty target namespace and created the Stage0–Stage4 artifacts during this run. The status history is exactly:

```text
ready -> running -> completed
```

No evidence of the following was found in the real task log, execution receipt, or output namespace:

- `Stage loaded`
- `Stage resumed`
- `resume checkpoint`
- `loaded checkpoint`
- `existing output reuse`
- `Resume=true`

The per-execution lock remains as an audit file, while the global Windows runner lock is absent after completion. No old SAGE namespace or checkpoint was reused or overwritten.

## 4. Artifact Completeness QA

### Artifact Completeness: PASS

The output was traced from the request and execution log, not inferred from a filename pattern:

`E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P9\sage_results\nav_sage_v2\G05`

The directory contains `21` files, all non-empty. The `11` required production CSV/JSON outputs are present:

- `run_context.json`
- `stage0_valid_symbols.csv`
- `stage0_valid_40ms_windows.csv`
- `stage1_nav_fast_scan.csv`
- `stage2_model_orders.csv`
- `stage2_selected_windows.csv`
- `stage2_selected_paths.csv`
- `stage3_persistence.csv`
- `stage3_reliable_centers.csv`
- `stage4_joint_summary.csv`
- `stage4_joint_paths.csv`

Additional non-empty artifacts include the Stage0/Stage1/Stage2/Stage3/Stage4 MAT progress/result files, `run_context.mat`, `doppler_sign.mat`, and `G05_nav_sage_overview.png`. No zero-byte file or abnormal-termination marker was found.

`run_context.json` agrees with the request: scene `F1023_V70_D0120_P9`, PRN label `G05`, channel `10`, sample rate `10230000`, project root `E:\GNSS_Multipath_Project`, and the exact output directory above.

## 5. Stage statistics and consistency

| Stage | Statistic | Value |
|---|---|---:|
| Stage0 | valid NAV symbols | 2,632 |
| Stage0 | complete 40 ms windows | 2,630 |
| Stage1 | scanned windows | 2,630 |
| Stage1 | selected candidate windows, including neighbors | 113 |
| Stage2 | total model evaluations | 452 |
| Stage2 | selected L=1 | 51 |
| Stage2 | selected L=2 | 44 |
| Stage2 | selected L=3 | 16 |
| Stage2 | selected L=4 | 2 |
| Stage2 | selected L≥2 | 62 |
| Stage2 | selected L≥3 | 18 |
| Stage3 | persistence rows | 82 |
| Stage3 | reliable centers | 12 |
| Stage4 | joint rows | 8 |
| Stage4 | `joint_valid=1` rows | 8 |
| Stage4 | `joint_multipath_count>0` rows | 2 |
| Stage4 | confirmed events | 2 |
| Stage4 | confirmed multipath paths | 2 |

The Stage2 file contains `113` evaluations for each model order L=1,2,3,4. Fourteen non-selected model-evaluation rows have `model_valid=0`; all `113` selected window rows are represented and the Stage2-to-Stage3-to-Stage4 chain is complete.

The identifier and consistency checks passed:

- Stage0 window IDs are unique and all `2,630` are represented in Stage1.
- Stage1 selected windows are unique and present in the scanned Stage1 set.
- Stage3 reliable centers are unique and belong to the Stage2 selected-window set.
- All Stage4 centers belong to the Stage3 reliable-center set.
- Stage4 path `(center_window_id, path_id)` pairs are unique.
- The Stage4 summary multipath counts equal the corresponding `is_multipath=1` path counts.

Stage2 `L≥2` and Stage3 reliable centers are intermediate evidence only. Neither is treated as a confirmed multipath result.

### Stage Consistency QA: PASS

The observed chain is consistent with the fixed hierarchy:

```text
Stage0 2,630 windows
  -> Stage1 2,630 scanned / 113 selected
  -> Stage2 452 model evaluations / 113 selected windows
  -> Stage3 12 reliable centers
  -> Stage4 8 joint rows / 8 valid rows
  -> 2 confirmed events / 2 confirmed paths
```

## 6. Scientific validity QA

The fixed confirmation rule was applied without modification:

```text
joint_valid == 1
AND joint_multipath_count > 0
AND stage4_joint_paths.csv contains is_multipath == 1
```

Two Stage4 rows satisfy the criterion. The other six Stage4 rows are valid joint results with zero multipath count and are not counted as confirmed events. Their optional multipath-only summary field is `NaN`, which is expected for a no-multipath joint row and is not treated as a malformed confirmed path.

All confirmed event/path numeric fields are finite. No duplicate or inconsistent confirmed event/path mapping was found. Confirmed-path values are within the recorded output ranges; no NaN/Inf occurs in the confirmed rows.

### Confirmed event/path table

| Center window | Time (s) | Joint L | Path ID | Excess delay (samples) | Excess delay (chips) | Doppler offset (Hz) | Relative power (dB) | Max coherence | Path count |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 493 | 40.3799649071 | 2 | 2 | 1.1 | 0.11 | 11.7153663155 | -8.4373821093 | 0.8083797061 | 1 |
| 495 | 40.4199650049 | 2 | 2 | 1.2 | 0.12 | 11.9467793930 | -4.1197043369 | 0.7936588931 | 1 |

The absolute selected path delay values are `0.8` and `0.7` samples respectively; the confirmed multipath excess delays are `1.1` and `1.2` samples as recorded in `stage4_joint_paths.csv`. The confirmed-event interpretation is limited to the current Stage4 criterion. It does not assert that other physical multipath is absent from the scene or satellite.

### Scientific Validity QA: PASS

## 7. VTC evidence impact

| Evidence item | Status after QA | Permitted interpretation |
|---|---|---|
| Special Reflective production evidence | `AVAILABLE` | One independently QA-passed production task is now available for the Special Reflective class |
| LOW planning-context evidence | `AVAILABLE` for scene-level context | Mean elevation approximately 19.327° is not an event-level elevation assignment |
| Confirmed path contribution | `+2 events / +2 paths` | Directly traceable to the two Stage4 confirmed rows above |
| Figure 2 representative confirmed path | `CANDIDATE` | Use only with the Stage4 path source and this QA report |
| Figure 3 hierarchical filtering | `CANDIDATE` | The 2,630 → 113 → 12 → 8 → 2 funnel is available as a task-level example |
| Figure 4 environment/path characterization | `PARTIAL / NOT_READY` | Window-level TOW/elevation alignment and broader denominators remain incomplete |

This result is evidence for the Special Reflective class and does not predict or imply the outcome of T1-2 or T1-3. Confirmed, rejected, and zero-event outcomes remain valid categories under the fixed criterion.

## 8. Production acceptance

`T1-1_PRODUCTION_QA = PASS`

The task is eligible to be recorded as the fourth accepted 10.23 MHz production task after refreshing the read-only production summary. The current accepted count becomes `4/67`; the formal A3 G16 artifact remains excluded from this accepted count because of its historical execution-contract caveat. This task does not authorize automatic execution of another task.

## 9. Handoff and state update requirements

Because this is a real production task with independent QA PASS, the following state artifacts require synchronization:

- Engineering Handoff: record T1-1 execution completed, QA PASS, runtime, Stage statistics, output path, and accepted count `4/67`.
- Paper Handoff: record the new Special Reflective QA-passed evidence and two confirmed paths without claiming a completed database or statistical model.
- VTC Evidence Matrix: replace T1-1 preparation-only status with QA-passed available evidence.
- VTC Production Priority Queue: mark T1-1 `QA_PASS / AVAILABLE`; keep T1-2 and T1-3 pending and do not generate their requests.
- Paper Workspace Index: no structural change; no update required.

## 10. Restrictions preserved

The QA did not modify the production manifest, immutable request, pipeline, existing SAGE artifacts, reference/G06 legacy outputs, or any 20.46 MHz task. No new task was started and no resume operation was performed.

`NEXT_VTC_DECISION_REQUIRED = YES` — wait for Commander direction before preparing or executing T1-2/T1-3.
