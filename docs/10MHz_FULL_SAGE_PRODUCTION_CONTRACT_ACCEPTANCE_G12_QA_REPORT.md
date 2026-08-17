# 10.23 MHz Full SAGE Controlled Acceptance QA — G12

## Task

| Item | Value |
|---|---|
| Scene | `F1023_V70_D0117_P4` |
| PRN | `G12` |
| Tracking channel | `ch4` / `4` |
| Sample rate | `10230000 Hz` |
| Request ID | `windows_production_contract_acceptance_d0117p4_g12_20260814` |
| Request SHA-256 | `228c67b07fddc6526d320b45bf3495aa56854a478ff39c2fdc0ee6283b74edee` |
| Execution ID | `batch_sage_execution_20260814T024904Z` |
| Output | `scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G12` |

This is an independent read-only post-run QA. No raw-IQ content was opened, and no MATLAB, SAGE, batch executor, resume, or repair action was run during QA.

## Evidence sources

- Immutable request: `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_contract_acceptance_d0117p4_g12_20260814/execution_request.json`
- Request preflight receipt/report: same request directory, `preflight_receipt.json`, `preflight_report.md`
- Normal-user environment receipt: `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_production_contract_acceptance_d0117p4_g12_20260814_20260814T024639097Z/`
- Batch log/report: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T024904Z/batch_execution_log.csv`, `batch_execution_report.md`
- Task log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260814T024904Z/task_logs/F1023_V70_D0117_P4__G12__ch4__nav_sage_v2.log`
- Output directory: `scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G12/`

## 1. Execution Contract QA — PASS

The request SHA recomputed from the immutable JSON is exactly:

`228c67b07fddc6526d320b45bf3495aa56854a478ff39c2fdc0ee6283b74edee`

The request and preflight receipts agree on the following hashes:

- Production manifest: `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00`
- Pipeline: `5ff00366f2d71eff7945418ce484b0fedb7199f1144c2db2fb18268fe5b4b0ab`
- Python executor: `bab7a0422975cb05bcda9a80a75c3577eb7f408a83f2720af2f1e13372b08f1b`
- Windows wrapper: `dd8afb1b3317bf920fe34474e3ceedf06ac4580b2a13c21ea25f8365071143f3`
- Task record: `a37775069fed5de8c92aa9281230e831727322bd86580455eb94adbe1abdbad8`

Scope is consistent across request, receipts, task log, run context and output: `F1023_V70_D0117_P4/G12/ch4/10230000`.

The normal-user environment receipt records `TJ-CHANNEL\\Jing_`, PowerShell `7.6.4`, MATLAB `25.1.0.2802752`, and MATLAB smoke marker `MATLAB_STARTUP_OK` with smoke exit code `0`. The batch execution log records task exit code `0`; the Python executor receipt records Python exit code `0`.

The actual MATLAB command recorded in the batch log, task log and execution receipt is:

```text
D:\Program Files\Matlab\bin\matlab.exe -batch addpath('E:\GNSS_Multipath_Project\scripts\sage_pipeline'); run_nav_sage_pipeline('F1023_V70_D0117_P4', 'G12', 'TrackingChannel', 4, 'ProjectRoot', 'E:\GNSS_Multipath_Project', 'Resume', false);
```

Read-only search of the real execution receipt, task log and batch log found `Resume=false` and no `Resume=true`. This is real execution evidence, not a dry-run preview.

Runtime was `4205.951 s` (approximately `70.10 min`), from `2026-08-14T02:49:04.649257Z` to `2026-08-14T03:59:10.600489Z`.

## 2. New-only Policy QA — PASS

- The preflight report records the target namespace absent before execution.
- The target directory was created at `2026-08-14T02:49:16Z`, after the task start time.
- The request freezes `new_only=true` and `resume_allowed=false`.
- The task log begins with `Stage 0: building navigation-symbol catalog...`; no stage-loading or checkpoint-reuse message is present.
- A read-only search found no `Stage loaded`, `Stage resumed`, `resume checkpoint`, `existing checkpoint reuse`, or equivalent marker.
- The progress MAT files in the output are current-run progress artifacts; there is no evidence that an older checkpoint was loaded.
- The task log ends with `Pipeline completed`, and the wrapper lock path is no longer present.

No old stage checkpoint was reused, no old output was resumed, and no existing result namespace was overwritten. A filesystem timestamp scan found no scene files modified during the execution interval outside the G12 target directory.

## 3. Artifact Completeness — PASS

The target contains `21` non-empty files. The required Stage CSV/JSON artifacts are all present:

- `run_context.json`
- Stage0: `stage0_nav_catalog.mat`, `stage0_valid_symbols.csv`, `stage0_valid_40ms_windows.csv`
- Stage1: `stage1_nav_fast_scan.csv`, `stage1_nav_fast_scan.mat`, `stage1_nav_progress.mat`
- Stage2: `stage2_model_orders.csv`, `stage2_selected_windows.csv`, `stage2_selected_paths.csv`, `stage2_nav_progress.mat`, `stage2_nav_sage_L1_L4.mat`
- Stage3: `stage3_persistence.csv`, `stage3_reliable_centers.csv`, `stage3_nav_persistence.mat`
- Stage4: `stage4_joint_summary.csv`, `stage4_joint_paths.csv`, `stage4_nav_joint_100ms.mat`
- Run support: `run_context.mat`, `doppler_sign.mat`, `G12_nav_sage_overview.png`

All nine MAT files are non-empty and carry a valid MATLAB 5.0 MAT-file header. All eleven required CSV/JSON files are non-empty and readable. No abnormal termination marker, empty output, or missing standard artifact was found. Full MATLAB variable deserialization was not attempted because MATLAB/SAGE execution is prohibited in this QA; the header, size, CSV, JSON and execution-completion checks show no artifact corruption indicator.

## 4. Stage Consistency — PASS

| Stage | Verified result |
|---|---:|
| Stage0 valid NAV symbols | 895 |
| Stage0 complete 40 ms windows | 893 |
| Stage1 scanned windows | 893; all `scan_valid=1`, no row errors |
| Stage1 candidates entering Stage2 | 99 (`stage2_selected_windows.csv`) |
| Stage2 model evaluations | 396 = 99 windows × four model orders |
| Stage2 final L1/L2/L3/L4 | 30 / 7 / 7 / 55 |
| Stage2 L≥2 / L≥3 | 69 / 62 |
| Stage3 persistence rows | 186 |
| Stage3 reliable centers | 15 |
| Stage4 joint rows | 8 |
| Stage4 `joint_valid=1` rows | 8 / 8 |
| Stage4 rows with `joint_multipath_count>0` | 3 |
| Confirmed events | 3 |
| Confirmed multipath paths | 3 |

Window identity checks passed: Stage0 has 893 unique windows; Stage1 has 893 unique rows and is fully contained in Stage0; Stage2 selected windows are 99 unique Stage1 windows; all 15 Stage3 reliable centers are selected Stage2 windows; all eight Stage4 centers are Stage3 reliable centers.

Stage2 `L>=2` and Stage3 reliable centers are intermediate evidence only. Neither is treated as a confirmed multipath label.

## 5. Scientific Validity — PASS

The current confirmed criterion was applied exactly:

```text
joint_valid == 1
AND joint_multipath_count > 0
AND stage4_joint_paths contains is_multipath == 1
```

The three confirmed rows are:

| Center window | Delay (samples) | Excess delay (samples/chips) | Doppler offset (Hz) | Relative power (dB) |
|---:|---:|---:|---:|---:|
| 163 | 1.1 | 1.1 / 0.11 | +8.215468 | -4.704662 |
| 289 | 1.2 | 1.2 / 0.12 | -24.152226 | -16.840482 |
| 290 | 1.0 | 1.0 / 0.10 | -29.098157 | -19.773110 |

For every Stage4 summary row, `joint_multipath_count` equals the number of `is_multipath=1` path rows at the same center. All three confirmed path rows have finite delay, excess-delay, Doppler, and relative-power values; no negative excess delay, NaN, or Inf occurs in the confirmed path fields.

The files contain expected NaN values only in fields whose value is undefined or unavailable under the pipeline semantics, such as final Stage0 continuity fields, fallback vehicle speed, L=1/non-multipath model fields, and Stage4 non-multipath summary power. These are not used as confirmed path parameters and are not malformed confirmed rows.

## 6. Controlled Acceptance Decision

| QA gate | Decision |
|---|---|
| Execution Contract QA | PASS |
| New-only Policy QA | PASS |
| Artifact Completeness | PASS |
| Stage Consistency | PASS |
| Scientific Validity | PASS |

## CONTROLLED_ACCEPTANCE = PASS

The repaired executor/request contract has passed real execution acceptance. Batch A continuous production may be released.

This approval applies only to the completed G12 controlled acceptance task and does not authorize automatic parallel execution. Future production tasks remain subject to independent immutable requests, preflight, normal-user Windows execution, and post-run QA.

## Status and scope notes

- The G12 result is now eligible to be counted as a completed 10.23 MHz production task after this QA.
- The three confirmed events/paths are production evidence under the current Stage4 criterion; they are not a claim that the scene or satellite has no other physical propagation components.
- No statistical channel model or complete event/path database is claimed.
- The production manifest, immutable request, existing results, reference baseline, raw data, metadata and inventory were not modified by this QA.

## Handoff impact

- Engineering Handoff update required: **yes** — G12 acceptance PASS, accepted count `3/67`, and Batch A release were recorded.
- Paper Handoff/VTC evidence update required: **yes** — G12 was registered as `AVAILABLE evidence`; it was not promoted automatically to a core VTC Results claim.
- Production summary refreshed: `dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv` and `production_summary_report.md`.

## QA execution restrictions

- New raw-IQ content read: no
- MATLAB/SAGE/batch run during QA: no
- Existing artifact repaired, overwritten, resumed or deleted: no
