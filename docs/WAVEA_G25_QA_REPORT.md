# Wave-A G25 Post-Execution QA Report

## Verdict

**PASS — G12 may now receive its own new immutable execution request.**

This report is a read-only QA of `F1023_v50_D0127_P1 / G25 / channel 0 / 10.23 MHz`. No MATLAB/SAGE process was started and no existing code, scene, metadata, inventory, request, or result was changed. The only new artifact of this QA is this report.

G12 is not executed or released by this report. It must use a fresh one-task request, its own reviewed SHA, normal-user serial execution, and a separate post-run QA.

## 1. Wrapper, Python, MATLAB, and executor audit

| Check | Result |
|---|---|
| Request | `windows_wavea1_g25_20260809`; request SHA `d9c4...cdb9` |
| Windows user / shell | `TJ-CHANNEL\Jing_`; PowerShell `7.6.4` |
| MATLAB smoke | marker present; exit `0`; 14.074 s |
| Python | CPython 3.12 path recorded; exit `0`; 2725.085 s |
| MATLAB G25 task | exit `0`; 2724.903 s (45.415 min) |
| Executor state history | `ready -> running -> completed` |
| Completion reason | `matlab_exit_0_and_output_qa_pass` |

The execution receipt records exactly one approved task: `F1023_v50_D0127_P1__G25__ch0__nav_sage_v2`. The MATLAB expression used named `TrackingChannel=0`, `ProjectRoot=E:\GNSS_Multipath_Project`, and `Resume=true`.

Authoritative audit records:

- `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_wavea1_g25_20260809_20260809T064618700Z/environment_receipt.json`
- `dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_wavea1_g25_20260809_20260809T064618700Z/execution_receipt.json`
- `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T064633Z/batch_execution_log.csv`
- `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T064633Z/status_history.jsonl`
- `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T064633Z/task_logs/F1023_v50_D0127_P1__G25__ch0__nav_sage_v2.log`

## 2. Context and Stage0–Stage4 completeness

`run_context.json` agrees with the frozen scope: scene `F1023_v50_D0127_P1`, PRN `G25`, channel `0`, sample rate `10230000 Hz`, scene-specific raw/tracking/telemetry/NAV/NMEA/geometry inputs, and exact output `scenes/F1023_v50_D0127_P1/sage_results/nav_sage_v2/G25`.

All 21 target artifacts exist and are non-empty, including run context, Stage0–Stage4 CSV/MAT files, progress MAT files, Doppler-sign record, and overview PNG. The Stage3/Stage4 CSV files are intentionally header-only (not zero-byte files), consistent with their empty event sets.

| Stage | Result |
|---|---|
| Stage0 | 2343 valid NAV symbols; 2339 complete 40 ms windows. |
| Stage1 | 2339/2339 scan-valid; 0 `error_message` rows; 2120 one-strong and 2044 two-strong residual screening rows. |
| Stage2 | 424 L1–L4 model evaluations; 259 valid candidate fits; 106 final selected windows. L1=106; L2/L3/L4=0; L>=2=0; L>=3=0. |
| Stage3 | Header/MAT output complete; 0 persistence rows, 0 persistence-pass rows, 0 reliable centers. |
| Stage4 | Header/MAT output complete; 0 joint summaries, 0 joint-valid results, 0 joint paths. |

The 165 Stage2 candidate-model rows with `model_valid=0` are not an execution failure: every selected Stage2 window has a final L1 choice, executor output QA passed, and no Stage1 errors or failed task state exists. The zero Stage3/Stage4 rows follow from the absence of any Stage2 L>=2 window.

The task log contains one nonfatal, garbled graphics/UI message after the Stage4 heading. Its exact source cannot be classified from the mojibake text alone. The overview PNG exists and is non-empty (261,590 bytes), all data artifacts passed executor QA, and no data-path failure is evidenced; it is recorded as a non-blocking visual-output warning for future MATLAB environment review.

## 3. Confirmed multipath assessment

The current confirmed-event condition is `joint_valid=1` plus `joint_multipath_count>0` in `stage4_joint_summary.csv`. G25 has:

- confirmed Stage4 event rows: **0**;
- confirmed Stage4 multipath paths: **0**;
- reliable Stage3 centers: **0**.

This is a complete pipeline result with no Stage4-confirmed multipath, compatible with an L1-only/low-multipath or LOS-like outcome. It is not a partial run and does not provide delay, Doppler, power, or coherence parameters because no confirmed path exists.

## 4. Output isolation and protection audit

- The selected snapshot, batch execution log, status history, report, task-log tree and per-task lock contain one G25 task only.
- A scan of all `scenes/**/sage_results/nav_sage_v2/**` files modified between the recorded MATLAB start/end times found exactly 21 files, all under `F1023_v50_D0127_P1/nav_sage_v2/G25`.
- No modified `nav_sage_v2` file was found under the reference scene, `G06_nav_sage_v1`, G16, or another scene/PRN during this execution interval.
- The preflight/output gate required G25 output absence; the execution created the new target rather than overwriting an existing result.

Timestamp evidence is not a cryptographic pre-run filesystem snapshot, so it cannot prove that an unrecorded file was created and deleted. The execution records contain no evidence of such an operation or of any target beyond G25.

## 5. G12 request decision

G25 provides a second successful normal-user Windows execution with smoke exit `0`, Python exit `0`, MATLAB exit `0`, full output QA, and preserved result isolation. Therefore it is appropriate to **generate — but not yet execute — one new immutable G12 request** for:

```text
F1023_V70_D0122_P1 / G12 / channel 6 / 10.23 MHz
```

The request must contain no other task and preserve current wrapper/Python protections: normal `TJ-CHANNEL\Jing_` PowerShell 7, single task, 10.23 MHz, `new_only`, no resume, absent output, request hashes, smoke marker plus exit `0`, serial execution, and another standalone post-run QA. Wave-B 20.46 MHz remains blocked.
