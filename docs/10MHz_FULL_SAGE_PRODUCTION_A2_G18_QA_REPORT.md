# 10 MHz Full SAGE Production A2 G18 QA Report

## QA scope and conclusion

This is an independent, read-only post-run QA of the completed production task:

- Scene: `F1023_V70_D0120_P1`
- PRN: `G18`
- Tracking channel: `ch2` (channel `2`)
- Sample rate: `10,230,000 Hz` (10.23 MHz)
- QA conclusion: **PASS**
- Production task status: `FULL_SAGE_PRODUCTION_TASK_STATUS=PASS`

The QA did not rerun MATLAB/SAGE, reopen or process raw IQ, or modify any production artifact. The production execution itself was performed earlier by the approved normal-user Windows wrapper; this document validates its receipts and outputs.

## 1. Execution verification

### Immutable request and approved scope

| Item | Value |
|---|---|
| Request manifest | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\production_10mhz_a2_d0120p1_g18_20260813\execution_request.json` |
| Request SHA-256 | `ff2138044f45a39f578577600eeddac14e5419cd5c08d8bc60f7421e2a91c9fa` |
| Request ID | `windows_production_10mhz_a2_d0120p1_g18_20260813` |
| Production manifest SHA-256 | `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00` |
| Approved scope | `F1023_V70_D0120_P1/G18/ch2/10230000 Hz` |
| Execution mode | `new_only=true`, `resume_allowed=false`, serial single-task execution |
| Execution log | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260813T034529Z\batch_execution_log.csv` |
| Status history | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260813T034529Z\status_history.jsonl` |
| Task log | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260813T034529Z\task_logs\F1023_V70_D0120_P1__G18__ch2__nav_sage_v2.log` |

The execution log contains one approved task. It records `status=completed`, `exit_code=0`, an empty error message, and the exact G18 output namespace. The status history records `ready -> running` after preflight and `running -> completed` with reason `matlab_exit_0_and_output_qa_pass`.

### Environment and receipt

| Item | Value |
|---|---|
| Environment receipt | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\windows_runner_receipts\windows_production_10mhz_a2_d0120p1_g18_20260813_20260813T034259453Z\environment_receipt.json` |
| Execution receipt | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\windows_runner_receipts\windows_production_10mhz_a2_d0120p1_g18_20260813_20260813T034259453Z\execution_receipt.json` |
| Windows identity | `TJ-CHANNEL\Jing_` |
| PowerShell | `7.6.4` |
| MATLAB | `D:\Program Files\Matlab\bin\matlab.exe`, file version `25.1.0.2802752` |
| MATLAB startup smoke | marker present, exit code `0` |
| Python executor exit code | `0` |
| Executor task exit code | `0` |
| Task duration | `7737.82 s` (about `128.96 min`) |
| Task interval UTC | `2026-08-13T03:45:29.092292+00:00` to `2026-08-13T05:54:26.912742+00:00` |

The receipt therefore confirms a successful normal-user wrapper invocation and successful Python executor return. No error or partial/interrupted status is recorded.

## 2. Output namespace and file integrity

The approved output is exactly:

`E:\GNSS_Multipath_Project\scenes\F1023_V70_D0120_P1\sage_results\nav_sage_v2\G18\`

The preflight receipt recorded `output_namespace_exists=false` before execution. The completed output contains exactly 21 expected files, and every file is non-empty:

`run_context.mat`, `run_context.json`, `stage0_valid_symbols.csv`, `stage0_valid_40ms_windows.csv`, `stage0_nav_catalog.mat`, `doppler_sign.mat`, `stage1_nav_progress.mat`, `stage1_nav_fast_scan.csv`, `stage1_nav_fast_scan.mat`, `stage2_nav_progress.mat`, `stage2_model_orders.csv`, `stage2_selected_windows.csv`, `stage2_selected_paths.csv`, `stage2_nav_sage_L1_L4.mat`, `stage3_persistence.csv`, `stage3_reliable_centers.csv`, `stage3_nav_persistence.mat`, `stage4_joint_summary.csv`, `stage4_joint_paths.csv`, `stage4_nav_joint_100ms.mat`, and `G18_nav_sage_overview.png`.

`run_context.json` independently matches:

- `sceneId=F1023_V70_D0120_P1`
- `prnLabel=G18`
- `trackingChannel=2`
- `samplingRateHz=10230000`
- output directory equal to the approved namespace

The execution log contains only the approved G18 task, and the output path is not a reference namespace, legacy `G06_nav_sage_v1`, or any other PRN namespace. No evidence in the execution receipt, status history, task log, or output manifest indicates a write outside this task’s approved output.

## 3. Stage statistics

| Stage | QA statistic | Observed value | Check |
|---|---|---:|---|
| Stage0 | valid NAV symbols | 2,611 | PASS |
| Stage0 | complete 40 ms windows | 2,609 | PASS |
| Stage1 | scanned windows | 2,609 / 2,609 | PASS |
| Stage1 | selected windows including neighbors | 115 | PASS |
| Stage2 | model-order evaluation rows | 460 (`115 x 4`) | PASS |
| Stage2 | final selected windows | 115 | PASS |
| Stage2 | selected L=1 / L=2 / L=3 / L=4 | 41 / 26 / 30 / 18 | PASS |
| Stage2 | selected L>=2 / L>=3 | 74 / 48 | PASS |
| Stage2 | selected path rows | 255 | PASS |
| Stage3 | reliable centers | 9 | PASS |
| Stage4 | joint summary rows | 8 | PASS |
| Stage4 | `joint_valid=1` rows | 8 / 8 | PASS |

Additional read-only structural checks passed:

- Stage0 window IDs are unique.
- Stage1 window IDs are unique and cover the Stage0 window-ID set.
- Stage2 has four model-order rows per selected window.
- Stage3 reliable center IDs are unique.
- Stage4 summary center IDs are unique and are a subset of Stage3 reliable centers.
- Stage4 path center IDs exactly match the Stage4 summary center IDs.
- Required numeric score/RSS/BIC fields are finite where applicable.
- All 21 output files are non-empty.

## 4. Confirmed event/path check

The operational confirmed criterion used for this QA is:

```text
joint_valid == 1
AND joint_multipath_count > 0
AND stage4_joint_paths.csv contains is_multipath == 1
```

Observed Stage4 values:

- `joint_valid=1`: 8 rows
- `joint_multipath_count>0`: 0 rows
- Stage4 path rows: 8
- Stage4 `is_multipath=1` path rows: 0
- Confirmed multipath events: **0**
- Confirmed multipath paths: **0**

This is a complete, valid zero-confirmed-event production output under the pipeline’s criterion. It is not classified here as a scientific LOS conclusion; this report only validates production execution and output completeness. Multipath-specific Stage4 fields that are not applicable to the all-single-path result may contain `NaN`/zero placeholders according to the pipeline schema and do not invalidate the zero-event output.

## 5. QA decision

All required execution, identity, output, Stage0–Stage4 chain, exit-code, and confirmed-criterion checks passed. The G18 task can be marked as the second completed and QA-passed 10.23 MHz full-SAGE production task.

The next production task must still use a new immutable request and independent preflight. This QA does not authorize automatic execution of another task.

## Scope declaration

This QA turn performed no new experiment:

- raw IQ read/processing: **no**
- MATLAB: **no**
- SAGE: **no**
- batch executor: **no**
- production artifact modification: **no**

