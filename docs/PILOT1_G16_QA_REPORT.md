# Pilot-1 G16 Post-Execution QA Report

## Verdict

**PASS — conditional GO for the remaining 10.23 MHz Wave-A tasks.**

This read-only QA covers `F1023_V70_D0120_P7 / G16 / channel 1 / 10.23 MHz`. It did not rerun MATLAB/SAGE or alter task, scene, metadata, inventory, pipeline, execution-request, or result data.

Conditional GO means the two remaining Wave-A tasks need new reviewed immutable requests and serial normal-user execution. All existing gates remain mandatory: MATLAB smoke exit code `0`, Python/executor preflight, output absence, reference protection, and no automatic resume. This does not authorize 20.46 MHz Wave-B.

## 1. Execution status

| Check | Result |
|---|---|
| Windows user / shell | `TJ-CHANNEL\Jing_`; PowerShell `7.6.4` |
| MATLAB smoke | marker present; exit `0`; 12.595 s |
| Python | `C:\Users\Jing_\AppData\Local\Programs\Python\Python312\python.exe`; exit `0`; 3913.409 s |
| MATLAB task | exit `0`; 3913.123 s (65.219 min) |
| Executor status | `ready -> running -> completed` |
| Completion reason | `matlab_exit_0_and_output_qa_pass` |

The executor recorded exactly one task: `F1023_V70_D0120_P7__G16__ch1__nav_sage_v2`. Its MATLAB call used named `TrackingChannel=1`, `ProjectRoot=E:\GNSS_Multipath_Project`, and `Resume=true` parameters.

Evidence:

- `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_pilot1_g16_20260809_20260809T051049713Z/environment_receipt.json`
- `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_pilot1_g16_20260809_20260809T051049713Z/execution_receipt.json`
- `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T051102Z/batch_execution_log.csv`
- `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T051102Z/status_history.jsonl`
- `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T051102Z/task_logs/F1023_V70_D0120_P7__G16__ch1__nav_sage_v2.log`

## 2. Context and Stage0–Stage4 QA

`run_context.json` matches the frozen Pilot scope: scene `F1023_V70_D0120_P7`, PRN `G16`, channel `1`, sampling rate `10230000 Hz`, correct raw/tracking/telemetry/NAV/NMEA/geometry inputs, and exact output namespace `scenes/F1023_V70_D0120_P7/sage_results/nav_sage_v2/G16`.

All 21 target artifacts are present and non-empty: run context, Stage0–Stage4 CSV/MAT files, progress MAT files, Doppler-sign record, and overview PNG. No required executor QA output is missing.

| Stage | Result |
|---|---|
| Stage0 | 2231 valid NAV symbols; 2229 complete 40 ms windows. |
| Stage1 | 2229/2229 scan-valid; 0 `error_message` rows; 1866 one-strong and 1714 two-strong residual rows. |
| Stage2 | 416 model evaluations; 340 valid fits; 104 final selected windows. L1=20, L2=34, L3=17, L4=33; L>=2=84; L>=3=50. |
| Stage3 | 167 path-persistence rows; 39 persistence-pass rows; 11 reliable center rows. |
| Stage4 | 8 joint summaries; all `joint_valid=1`; Stage4 MAT/summary/path files present. |

The 76 invalid Stage2 candidate-model rows are not task failures: every selected Stage2 window has a final model and the executor completion QA passed. No Stage1 error, task-log fatal error, partial-only output state, or failed task state was found.

## 3. Confirmed multipath output

By the current output semantics (`joint_valid=1` and `joint_multipath_count>0`), this run contains **4 confirmed Stage4 event rows and 4 associated multipath paths**.

| Center window | Time (s) | Joint L | Excess delay (samples / chips) | Doppler offset (Hz) | Relative power (dB) | Coherence |
|---:|---:|---:|---:|---:|---:|---:|
| 1337 | 68.502853 | 2 | 1.2 / 0.12 | +19.6532 | -4.5894 | 0.6678 |
| 1338 | 68.522853 | 2 | 1.0 / 0.10 | +19.9106 | -3.2640 | 0.6829 |
| 1406 | 69.882856 | 2 | 1.1 / 0.11 | -3.0423 | -6.3379 | 0.8809 |
| 2079 | 83.342881 | 2 | 1.1 / 0.11 | -3.8204 | -5.0925 | 0.8778 |

Windows 1337 and 1338 are separate Stage4 rows. No higher-level clustering artifact exists, so QA does not claim that they are separate physical reflections; future event-database ingestion must decide grouping.

## 4. Isolation and overwrite audit

- The selected snapshot, execution CSV and report contain one task only.
- The execution tree contains one task log and one task lock only.
- During the recorded execution interval, a scan of all `scenes/**/sage_results/nav_sage_v2/**` files found 21 modified files, all and only under `F1023_V70_D0120_P7/nav_sage_v2/G16`.
- The preflight required target absence, then created this new G16 directory. Reference outputs and `G06_nav_sage_v1` do not appear in this execution log or timestamp scan.

This timestamp scan is strong post-run evidence of isolation, not a cryptographic pre-run snapshot. It cannot prove that an unrecorded file was created and deleted, but no such action appears in the audited logs.

## 5. Wave-A decision

The Pilot validates the normal-user wrapper path and all Stage0–Stage4 outputs for one non-reference 10.23 MHz scene. The following may proceed as fresh, individually reviewed, serial Windows requests:

1. `F1023_v50_D0127_P1 / G25 / channel 0`
2. `F1023_V70_D0122_P1 / G12 / channel 6`

For each, retain the normal `TJ-CHANNEL\Jing_` PowerShell 7 boundary, new request SHA, smoke marker **and exit 0**, Python preflight, output-conflict check, per-task post-run QA, and manual release of the next task only after review. The previously observed intermittent MATLAB exit-3 event remains a hard stop if it recurs. 20.46 MHz Wave-B remains blocked.
