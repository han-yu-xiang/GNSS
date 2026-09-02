# 10.23 MHz Full SAGE C1 Reconciliation — 2026-08-19

## Decision

Codex-managed continuation is stopped after G24. The remaining frozen queue has been delegated to the independent Windows Scheduled Task runner. No G25+ task was created or started by Codex.

## Frozen gates

| Gate | SHA-256 / value |
|---|---|
| Production source `run_nav_sage_pipeline.m` | `BFFC123C97AF77F0A797F417D3866E9A34FEAB7729C5C1575352F53BC3571B9C` |
| Production manifest | `77C20C0ED6C84FA0348DB429948A8BD4900B2E8D86A6D8843B159B9A7A35CF00` |
| Windows wrapper | `DD8AFB1B3317BF920FE34474E3CEEDF06AC4580B2A13C21EA25F8365071143F3` |
| Python executor | `BAB7A0422975CB05BCDA9A80A75C3577EB7F408A83F2720AF2F1E13372B08F1B` |
| Policy | `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1` |

All four current hashes match the frozen values. The source and manifest were not modified.

## New production tasks completed this round

| Task | Request SHA-256 | MATLAB / executor | Stage0 → Stage4 | QA / classification |
|---|---|---|---|---|
| `F1023_V120_D0121_P2/G03/ch2` | `06ACB9FF1634C8B248ED6A46A63BF2E0BEE8934B61F8DE61CE56C11A56F5DC64` | completed, exit `0`, `2073.646 s` | `232 / 230 / 230 / 96 / 8 / 8` | [G03 QA](</E:/GNSS_Multipath_Project/docs/10MHz_FULL_SAGE_PRODUCTION_C1_G03_QA_REPORT.md>): PASS, `0/0` confirmed |
| `F1023_V120_D0121_P2/G24/ch2` | `0C1AE58403396F5C68D2C952C493DBC7733ACC6989882B5DE26ED8ADAAB19676` | completed, exit `0`, `11185.234 s` | `8265 / 8257 / 8257 / 52 / 0 / 0` | [G24 QA](</E:/GNSS_Multipath_Project/docs/10MHz_FULL_SAGE_PRODUCTION_C1_G24_QA_REPORT.md>): PASS, `0/0` confirmed |

Stage tuple columns are `valid NAV symbols / Stage0 windows / Stage1 scans / Stage2 selected windows / Stage3 reliable centers / Stage4 joint rows`. G24 Stage3/4 header-only outputs are valid zero-event artifacts.

Execution evidence:

- G03 log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260818T110255Z/`; receipt under `windows_production_10mhz_c1_d0121p2_g03_20260818_20260818T110245152Z/`.
- G24 log: `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260818T130227Z/`; receipt under `windows_production_10mhz_c1_d0121p2_g24_20260818_20260818T130217990Z/`.
- Both normal-user wrapper receipts prove `TJ-CHANNEL\Jing_`, MATLAB smoke exit `0`, Python exit `0`, task exit `0`, and explicit `Resume=false`.

## Current state

```text
TOTAL_FROZEN = 67
ACCEPTED = 9
REJECTED_PROTECTED = 1 (historical A3 G16; unchanged)
NEW_ACCEPTED = 2 (G03, G24)
FAILED/BLOCKED = 0 new tasks this round
REMAINING_NOT_STARTED_ELIGIBLE = 57
NEXT_ELIGIBLE_TASK = F1023_V120_D0121_P2__G25/ch5
```

The production monitoring summary was refreshed at `dataset_generation_logs/production_monitoring_10MHz/production_summary_10MHz.csv`. Accepted-state counting continues to exclude protected A3 G16 despite its retained historical artifact.

## Frozen queue, original manifest order

```text
01 F1023_V120_D0121_P2__G25
02 F1023_V120_D0121_P2__G28
03 F1023_V120_D0121_P2__G32
04 F1023_v50_D0127_P1__G11
05 F1023_v50_D0127_P1__G28
06 F1023_v50_D0127_P1__G29
07 F1023_v50_D0127_P1__G31
08 F1023_V70_D0117_P4__G25
09 F1023_V70_D0117_P4__G28
10 F1023_V70_D0117_P4__G29
11 F1023_V70_D0117_P4__G31
12 F1023_V70_D0117_P4__G32
13 F1023_V70_D0120_P1__G26
14 F1023_V70_D0120_P1__G27
15 F1023_V70_D0120_P1__G29
16 F1023_V70_D0120_P1__G31
17 F1023_V70_D0120_P5__G18
18 F1023_V70_D0120_P5__G23
19 F1023_V70_D0120_P5__G26
20 F1023_V70_D0120_P5__G27
21 F1023_V70_D0120_P7__G18
22 F1023_V70_D0120_P7__G26
23 F1023_V70_D0120_P7__G31
24 F1023_V70_D0120_P8__G16
25 F1023_V70_D0120_P8__G18
26 F1023_V70_D0120_P8__G23
27 F1023_V70_D0120_P8__G26
28 F1023_V70_D0120_P9__G16
29 F1023_V70_D0120_P9__G18
30 F1023_V70_D0120_P9__G26
31 F1023_V70_D0120_P9__G27
32 F1023_V70_D0120_P9__G28
33 F1023_V70_D0120_P9__G29
34 F1023_V70_D0120_P9__G31
35 F1023_V70_D0122_P1__G13
36 F1023_V70_D0122_P1__G14
37 F1023_V70_D0122_P1__G15
38 F1023_V70_D0122_P1__G17
39 F1023_V70_D0122_P1__G19
40 F1023_V70_D0122_P1__G22
41 F1023_V70_D0122_P1__G24
42 F1023_V70_D0122_P2__G10
43 F1023_V70_D0122_P2__G12
44 F1023_V70_D0122_P2__G13
45 F1023_V70_D0122_P2__G19
46 F1023_V70_D0122_P2__G23
47 F1023_V70_D0122_P2__G24
48 F1023_V80_D0117_P8__G12
49 F1023_V80_D0117_P8__G28
50 F1023_V80_D0117_P8__G29
51 F1023_V80_D0117_P8__G31
52 F1023_V80_D0117_P8__G32
53 F1023_v90_D0117_P7__G12
54 F1023_v90_D0117_P7__G25
55 F1023_v90_D0117_P7__G28
56 F1023_v90_D0117_P7__G29
57 F1023_v90_D0117_P7__G32
```

## Independent unattended runner handoff

| Item | Value |
|---|---|
| Runner | `scripts/sage_pipeline/Run-UnattendedMainlineBatch.ps1` |
| Task Scheduler command shim | `scripts/sage_pipeline/Run-UnattendedMainlineBatch.cmd` |
| Scheduled Task | `GNSS-SAGE-Unattended-Mainline-20260819` |
| Principal | `TJ-CHANNEL\Jing_`, Interactive, Limited/non-admin |
| Dry-run | `PASS`; queue `57`; first task `F1023_V120_D0121_P2__G25` |
| Current run | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_unattended\run_20260819T004818Z\` |
| Runner PID | `25520` |
| State / heartbeat | `runner_state.json` / `heartbeat.json` in the current run directory |
| Runner log | `runner.log` in the current run directory |
| Scheduler stdout/stderr | `dataset_generation_logs/batch_sage_unattended/scheduled_task_stdout.log` and `scheduled_task_stderr.log` |
| Current task | `F1023_V120_D0121_P2__G25`, request ordinal `001`, request SHA `B2C77CCA1C6720CF29558588FA57BCD90AD553835628ABDEDF6BC9E135B6B78B` |
| Shared runner lock | `dataset_generation_logs/batch_sage_unattended/.unattended_runner_active.lock` |
| Handoff status | `UNATTENDED_RUNNER_CREATED=YES`, `DRY_RUN=PASS`, `STARTED=YES`, `INDEPENDENT_FROM_CODEX=YES`, `FIRST_TASK_IDENTITY_VERIFIED=YES` |

The runner waits synchronously for each wrapper and stops fail-safe on any hash, policy, receipt, output, lock, or exit-code anomaly. It leaves the final state at `BATCH_POST_RUN_QA_REQUIRED`; no database, elevation matching, or statistical modeling is started automatically.

For status, read the current `runner_state.json` and `heartbeat.json`. Do not stop the task while its heartbeat says `MATLAB_RUNNING`. After a natural task return, an operator may stop future scheduling with:

```powershell
Stop-ScheduledTask -TaskName 'GNSS-SAGE-Unattended-Mainline-20260819'
```

The post-run QA entry point is:

```powershell
python scripts/sage_pipeline/audit_10MHz_production_summary.py --project-root E:\GNSS_Multipath_Project
```

This updates the monitoring summary; the final unified scientific QA must still apply the strict Stage4 confirmed criterion to every newly executed task before any database or modeling work.
