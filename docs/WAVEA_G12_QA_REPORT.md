# Wave-A G12 Post-Execution QA Report

## Scope and verdict

This is a post-execution **read-only QA** review of the approved Wave-A task.
No MATLAB, SAGE pipeline, Python executor, scene data, metadata, inventory, or
prior result was changed while preparing this report.

| Item | Value |
|---|---|
| Approved task | `F1023_V70_D0122_P1__G12__ch6__nav_sage_v2` |
| Scene / PRN / channel | `F1023_V70_D0122_P1` / `G12` / `6` |
| Sampling rate | 10.23 MHz (`10230000` Hz) |
| Output namespace | `scenes/F1023_V70_D0122_P1/sage_results/nav_sage_v2/G12` |
| Immutable request | `dataset_generation_logs/batch_sage_execution_requests/windows_wavea2_g12_20260809/execution_request.json` |
| Request SHA-256 | `fd1e5d1ec0de38bf87951563f68798fab03dbf1707a680961d6adf1bad32494a` |
| Execution root | `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260809T082111Z` |
| Final QA verdict | **PASS** |

The task completed through the normal-user Windows wrapper. The MATLAB smoke
gate, Python executor, MATLAB task, executor output QA, and all Stage0--Stage4
outputs completed successfully. Observed writes are confined to the intended
G12 output namespace.

## Wrapper and executor evidence

The runner receipt directory is
`dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_wavea2_g12_20260809_20260809T082057041Z`.
It records expected identity `TJ-CHANNEL\\Jing_`, PowerShell `7.6.4`, and:

```text
D:\Program Files\Matlab\bin\matlab.exe
```

| Check | Result |
|---|---|
| `MATLAB_STARTUP_OK` marker | present |
| MATLAB smoke exit code | `0` |
| Smoke duration | 14.055 s |
| Python executable | CPython `Python312` |
| Python executor exit code | `0` |
| Approved task completed flag | `true` |

`batch_execution_log.csv`, `batch_execution_report.md`, status history, and
the task log consistently show one task. State changed from
`ready -> running` (`preflight_passed`) to `running -> completed`
(`matlab_exit_0_and_output_qa_pass`). The recorded named-parameter MATLAB call
is scoped to this scene, PRN, channel, project root, and fixed output namespace.

MATLAB began `2026-08-09T08:21:11.622774Z`, ended
`2026-08-09T09:10:21.275914Z`, returned `0`, and ran `2949.653` seconds
(about 49.16 minutes). The executor records no task error.

## Output completeness and Stage chain

`run_context.json` and its MAT counterpart identify scene
`F1023_V70_D0122_P1`, PRN `G12`, tracking channel `6`, and sample rate
`10230000`. The target directory contains all **21 expected non-empty files**:

- run context (JSON/MAT), Doppler-sign record, overview PNG;
- Stage0 NAV catalog (MAT/CSV);
- Stage1 fast scan (CSV/MAT/progress);
- Stage2 model-order, selections/paths, SAGE data, and progress files;
- Stage3 persistence and reliable-center files (CSV/MAT);
- Stage4 joint-summary and joint-path files (CSV/MAT).

| Stage | QA result | Key result |
|---|---|---|
| Stage0 | complete | 1,631 valid NAV symbols; 1,629 complete 40 ms windows |
| Stage1 | complete | 1,629 valid rows, 0 errors |
| Stage2 | complete | 107 selected windows; 428 model rows, 356 valid |
| Stage3 | complete | 212 rows; 65 passing rows; 11 reliable centers |
| Stage4 | complete | 8 valid joint summaries; 3 confirmed events / 3 paths |

Stage2 selected-model distribution: `L1=21`, `L2=17`, `L3=12`, `L4=57`,
thus `L>=2=86` and `L>=3=69`. This is consistent with the subsequent
persistence and joint-confirmation results, not a partial Stage2 run.

The task log includes a non-fatal garbled graphics/UI message after Stage4.
The overview PNG and all data outputs exist; MATLAB returned zero and executor
output QA passed. It is therefore recorded as a non-blocking visual warning,
not evidence of a failed SAGE stage.

## Confirmed multipath events

Stage4 joint-summary and joint-path CSVs contain three confirmed events. Each
has `joint_valid=1` and one multipath path.

| PRN | Center window | Time (s) | Joint L | Delay (samples / chips) | Doppler offset (Hz) | Relative power (dB) | Coherence | Paths |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| G12 | 835 | 44.9110977517107 | 2 | 1.4 / 0.14 | -71.5654432731581 | -16.2501226962046 | 0.184742563164214 | 1 |
| G12 | 836 | 44.9310977517107 | 2 | 1.3 / 0.13 | -71.4648759076238 | -15.3692890811629 | 0.187127715719209 | 1 |
| G12 | 1278 | 53.7711064516129 | 2 | 4.5 / 0.45 | -78.5522071033497 | -13.2119027229851 | 0.109428071806393 | 1 |

| Center window | Path delay (samples) | Path Doppler (Hz) |
|---:|---:|---:|
| 835 | 1.6 | -1623.0892469841 |
| 836 | 1.5 | -1623.82156536075 |
| 1278 | 4.6 | -1638.09578620491 |

Values above were extracted from existing Stage4 CSV outputs only; they were
not recomputed during QA.

## Isolation and preservation checks

The execution-root report lists one approved task, task log, status history,
and expected locks. A timestamp-based scan spanning the MATLAB task interval
found exactly 21 modified files under `scenes/**/sage_results/nav_sage_v2/**`;
all were under:

```text
scenes/F1023_V70_D0122_P1/sage_results/nav_sage_v2/G12
```

No observed writes were under the reference scene, `G06_nav_sage_v1`, prior
Pilot-1 G16, Wave-A G25, or any other scene/PRN namespace. Wrapper/executor
records also show the required new-only output-absence preflight.

This is strong filesystem and execution-log isolation evidence. Timestamp
evidence cannot cryptographically prove absence of an unrecorded
create-and-delete action; no such action is indicated by receipts, logs, or
the observed result tree.

## Wave-A closure decision

**PASS — the three-task 10.23 MHz Wave-A validation is closed.**

| Wave-A task | QA result | Validation contribution |
|---|---|---|
| `F1023_V70_D0120_P7/G16/ch1` | PASS | high-multipath case; 4 Stage4 confirmed-event rows |
| `F1023_v50_D0127_P1/G25/ch0` | PASS | low-multipath / LOS-like case; no Stage4 confirmed events |
| `F1023_V70_D0122_P1/G12/ch6` | PASS | high-order and confirmed-multipath case; 3 Stage4 confirmed events |

All three used the reviewed normal-user Windows safety chain and passed smoke,
Python, MATLAB, executor, Stage0--Stage4, output-completeness, and isolation
checks. This closes the planned Wave-A validation scope; it does **not**
authorize unrestricted batch execution or a 20.46 MHz task. The next task
should remain a separately reviewed small 10.23 MHz continuation and/or the
planned multipath-event database ingestion, with a new immutable request and
the same post-execution QA gate.
