# MATLAB Batch Failure Diagnostic

## Scope and safety

This diagnostic examines the failed Wave1 batch execution only. No MATLAB command was launched during this investigation, no SAGE stage was rerun, and no code, metadata, inventory, raw IQ, scene result or checkpoint was modified.

Failure batch:

`E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260808T121058Z`

## Executive conclusion

The immediate failure is a MATLAB process startup/filesystem failure, before MATLAB reached `run_nav_sage_pipeline.m`:

```text
Fatal Startup Error:
Dynamic exception type: class std::runtime_error
std::exception::what: System Error: File system inconsistency
ERROR: MATLAB error Exit Status: 0x00000001
```

All five tasks failed with the same message and MATLAB return code `1` within `0.714–0.846 s`. No Stage0 banner, `run_context.json`, output directory or Stage0–Stage4 file was created. The common startup signature makes a MATLAB/environment problem much more likely than a scene-specific input problem.

There is also a separate executor defect that was not reached because MATLAB failed before parsing the command: the batch command passes `TrackingChannel` and `ProjectRoot` as positional arguments, while the current MATLAB function requires named `TrackingChannel` and `ProjectRoot` parameters. This must be corrected or explicitly verified before any retry.

## 1. Failure log and actual invocation

Authoritative files:

- `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260808T121058Z\batch_execution_log.csv`
- `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260808T121058Z\status_history.jsonl`
- `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260808T121058Z\task_logs\*.log`

The five commands recorded in the task logs were of this form:

```text
matlab -batch addpath('E:\GNSS_Multipath_Project\scripts\sage_pipeline'); run_nav_sage_pipeline('F1023_V70_D0120_P7', 'G16', 1, 'E:\GNSS_Multipath_Project');
```

| Order | Scene | PRN | Channel | MATLAB return | Duration | Result |
|---:|---|---:|---:|---:|---:|---|
| 1 | `F1023_V70_D0120_P7` | G16 | 1 | 1 | 0.846 s | startup failure |
| 2 | `F1023_v50_D0127_P1` | G25 | 0 | 1 | 0.728 s | startup failure |
| 3 | `F1023_V70_D0122_P1` | G12 | 6 | 1 | 0.763 s | startup failure |
| 4 | `F2046_V30_D0131_P4` | G18 | 5 | 1 | 0.726 s | startup failure |
| 5 | `F2046_V60_D0202_P1` | G32 | 5 | 1 | 0.714 s | startup failure |

The status history proves serial execution: each task transitioned `ready → running → failed`, and the next task started only after the previous task ended. The executor's preflight transition was `preflight_passed` for all five tasks.

## 2. MATLAB executable and launch environment

Read-only checks found:

| Check | Observation | Interpretation |
|---|---|---|
| `where matlab` | `D:\Program Files\Matlab\bin\matlab.exe` | One PATH resolution; no duplicate MATLAB executable was reported. |
| File existence | `True` | The executable file exists. |
| File type | Regular `matlab.exe`, 924,376 bytes | The path is not a missing or directory target. |
| File version | `25.1.0.2802752` | MATLAB R2025a-era executable metadata. |
| Runtime directory | `D:\Program Files\Matlab\runtime\win64` exists | The matching runtime directory is present. |
| PATH | Contains `D:\Program Files\Matlab\runtime\win64` and `D:\Program Files\Matlab\bin` | PATH is structurally consistent. |
| Current identity | `tj-channel\codexsandboxoffline` | MATLAB was launched from a restricted sandbox identity. |
| MATLAB runtime probe | Not performed | A real startup test was intentionally not run. |

The executable is readable/executable through the inherited `BUILTIN\Users` permission. File metadata alone cannot establish that the binary launches successfully.

## 3. Current working directory and runner-created directories

The failed task logs and `run_batch_sage.py` agree on the project root:

- Current shell working directory: `E:\GNSS_Multipath_Project`
- Executor `subprocess.run(..., cwd=...)`: `E:\GNSS_Multipath_Project`
- MATLAB `ProjectRoot`: `E:\GNSS_Multipath_Project`
- MATLAB `addpath`: `E:\GNSS_Multipath_Project\scripts\sage_pipeline`

The runner does not call `tempfile`, does not set `TEMP`, `TMP` or MATLAB preferences, and does not create a per-task working directory. It creates only this expected batch audit tree:

```text
dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260808T121058Z\
├── task_logs\
├── locks\
├── status_history.jsonl
├── batch_execution_log.csv
├── batch_execution_report.md
└── batch_execution_summary.md
```

The relevant code paths are `scripts/sage_pipeline/run_batch_sage.py:451` for `cwd`, and `:587–591` for `log_root`, `task_logs` and `locks` creation. No abnormal MATLAB working directory was created.

## 4. TEMP, TMP and MATLAB cache paths

### 4.1 TEMP/TMP

Both environment variables inherited by the executor are:

```text
TEMP=C:\Users\Jing_\.codex\codex-temp
TMP=C:\Users\Jing_\.codex\codex-temp
```

The directory exists. Read-only enumeration found approximately 181 directories, 898 files and 17.5 MB. The root contains two Codex-managed subdirectories; nested files are predominantly browser/Codex cache databases and ordinary Chromium `LOCK`/`LOG` files. No MATLAB-specific `matlab`, `MathWorks`, `mltemp` or `mwtemp` path was found in scanned names.

The `TJ-Channel\CodexSandboxUsers` ACL entry on this TEMP root grants `Modify`. The current sandbox identity belongs to that group. Therefore the current TEMP root is writable for the sandbox group, although this does not prove every MATLAB startup component can use it successfully.

### 4.2 MATLAB user cache and preferences

The MATLAB-related user directories present on disk are:

```text
C:\Users\Jing_\AppData\Local\MathWorks\MATLAB\R2025a
C:\Users\Jing_\AppData\Roaming\MathWorks\MATLAB\R2025a
```

Observed contents:

- Local `R2025a`: 2 files, approximately 10.0 MB, including `toolbox_cache-25.1.0-1812969456-win64.xml`.
- Roaming `R2025a`: 17 files and 2 directories, approximately 1.0 MB, including `matlab.mlsettings`, `epfwk_cache-25.1.0...json` and startup preferences.
- No MATLAB-specific `LOCK` filename was found in these two R2025a directories.
- No `MATLAB_PREFDIR` environment variable is defined.

The important permission finding is:

```text
TJ-Channel\CodexSandboxUsers: ReadAndExecute, Synchronize
```

on both MATLAB R2025a cache roots and their R2025a child directories. The current process belongs to `TJ-Channel\CodexSandboxUsers`. There is no `Modify` or `FullControl` grant for that group on these MATLAB cache locations; full control is retained by the interactive user, Administrators and SYSTEM.

This is the highest-priority environment hypothesis: MATLAB startup may need to update preferences, cache, licensing or framework state under Local/Roaming MathWorks, but the sandbox identity can only read/execute those locations. The evidence is strong but not proven because a MATLAB startup probe was deliberately not run.

Free-space checks were limited by the sandbox: free space on `E:` was observable and approximately 1.1 TB; `fsutil` access to `C:` and `D:` was denied. No conclusion about free space on the MATLAB/system volume should be inferred.

## 5. Residual locks, temporary files and output paths

### Executor locks

The failed batch contains exactly five 178-byte `.lock` files, one per selected task. Each is a JSON audit record containing the task ID, execution ID and creation timestamp. These are expected executor locks, not MATLAB lock files:

```json
{
  "task_id": "F1023_V70_D0120_P7__G16__ch1__nav_sage_v2",
  "execution_id": "batch_sage_execution_20260808T121058Z"
}
```

They should be retained. The executor intentionally keeps them so a retry uses a new execution namespace instead of accidentally resuming the failed attempt.

### Task logs and scene outputs

There are exactly five 396-byte task logs. They contain the command, start time and MATLAB startup error. All five target directories remain absent:

```text
scenes/F1023_V70_D0120_P7/sage_results/nav_sage_v2/G16
scenes/F1023_v50_D0127_P1/sage_results/nav_sage_v2/G25
scenes/F1023_V70_D0122_P1/sage_results/nav_sage_v2/G12
scenes/F2046_V30_D0131_P4/sage_results/nav_sage_v2/G18
scenes/F2046_V60_D0202_P1/sage_results/nav_sage_v2/G32
```

No partial `run_context.json`, checkpoint MAT or Stage CSV exists in these targets. No reference result directory was touched.

### TEMP residue

The Codex TEMP tree contains ordinary browser cache `LOCK` files, but they are under Codex/Chromium subdirectories, not under a MATLAB cache or project output tree. Their timestamps precede the Wave1 launch. There is no evidence that `run_batch_sage.py` created them; the runner has no TEMP/cache creation code.

## 6. Reference standalone run comparison

### Evidence available

The repository does not contain a raw MATLAB shell transcript for the successful reference G12/G29 standalone runs. Therefore the exact standalone executable path, current folder, TEMP/TMP values and preference/cache locations cannot be reconstructed from files alone. Available evidence is:

- `docs/GNSS_SAGE_PROJECT_HANDOFF.md:293–300`, which documents `addpath(...)` followed by a named-parameter MATLAB call.
- `docs/GNSS_SAGE_DAILY_HANDOFF_20260807.md:146–153`, which documents the same named-parameter convention.
- `scenes/F1023_V70_D0117_P2/sage_results/nav_sage_v2/G12/run_context.json`, which records a successful G12 context with channel 6, 10.23 MHz and the expected project/scene/output paths.
- The existing G29 output and handoff record, which confirm a successful standalone result but do not record a command-line transcript.

### Call-shape difference

The current pipeline begins with:

```matlab
function result = run_nav_sage_pipeline(sceneId, prn, varargin)
```

and defines named `inputParser` parameters `TrackingChannel`, `ProjectRoot` and `Resume`. The documented/reference call shape is:

```matlab
run_nav_sage_pipeline( ...
    "F1023_V70_D0117_P2", ...
    "G32", ...
    "TrackingChannel", 11, ...
    "ProjectRoot", "E:\\GNSS_Multipath_Project", ...
    "Resume", true)
```

The batch executor actually emitted:

```matlab
run_nav_sage_pipeline( ...
    'F1023_V70_D0120_P7', ...
    'G16', ...
    1, ...
    'E:\\GNSS_Multipath_Project')
```

This is not an equivalent call. After MATLAB startup is fixed, the numeric channel and project-root strings would be passed as unnamed `varargin` entries and are expected to fail `inputParser` rather than bind to `TrackingChannel` and `ProjectRoot`. This is a latent batch-executor bug, not the cause of the observed startup error.

### Other differences

| Aspect | Successful reference evidence | Wave1 batch |
|---|---|---|
| MATLAB call | Named `TrackingChannel`/`ProjectRoot` documented | Positional channel/root emitted by executor |
| `addpath` | Project `scripts/sage_pipeline` path documented | Same project pipeline path |
| Project root | Explicit `E:\GNSS_Multipath_Project` | Explicit same root and `cwd` |
| Process mode | Exact standalone mode not recorded | `matlab -batch`, one new process per task |
| TEMP/TMP | Not recorded in project artifacts | Both set to Codex TEMP |
| MATLAB cache ACL | Not recorded for successful run | Sandbox group has RX only on MathWorks R2025a dirs |
| Sample rate | Reference outputs are 10.23 MHz | Wave A 10.23 MHz; Wave B 20.46 MHz selected by plan |

The shared project root and `addpath` are not suspicious. The unrecorded standalone environment means it is not possible to prove whether the successful reference runs used a different user identity, writable cache, MATLAB desktop process or TEMP/TMP configuration.

## 7. Additional blocker discovered from source inspection

The current `run_nav_sage_pipeline.m` header says it supports only 10.23 MHz. `resolveInputs` asserts `samplingRateHz == 10.23e6` and raises `Phase-1 run_nav_sage_pipeline supports only 10.23 MHz` for other rates.

The Wave1 plan selected two 20.46 MHz tasks as Wave B. They failed before this assertion because MATLAB did not start, but after the startup and call-shape issues are resolved, the current pipeline is expected to reject them before Stage0. This is a separate plan/pipeline compatibility issue and must not be bypassed by deleting the sampling-rate assertion.

## 8. Diagnostic decision and next safe steps

### Primary diagnosis

`System Error: File system inconsistency` is a MATLAB startup/environment failure. The strongest concrete environmental lead is read-only access for the Codex sandbox group to the MATLAB R2025a Local/Roaming cache and preference roots, while TEMP/TMP point to a writable Codex temp tree.

### Do not do yet

- Do not rerun the failed batch.
- Do not delete the five executor locks or task logs.
- Do not modify MathWorks ACLs, TEMP/TMP, MATLAB installation files or user preferences from this project task without explicit system-level approval.
- Do not modify `run_nav_sage_pipeline.m` just to make the batch call appear to work.
- Do not launch Wave B 20.46 MHz under the current phase-1 pipeline.

### Recommended diagnostic sequence for a separately approved environment repair

1. Arrange a MATLAB execution identity/environment with a writable MATLAB preference/cache location, or explicitly configure a writable MATLAB preference directory outside protected project data. Preserve current values and ACLs as a backup before any system-level change.
2. Run a minimal MATLAB startup smoke test only, outside the SAGE pipeline, and record executable path, MATLAB version, identity, working directory, TEMP/TMP and preference/cache locations.
3. Correct the executor call construction to use named `TrackingChannel` and `ProjectRoot` parameters, then perform a non-SAGE command-preview/static test.
4. Re-run a fresh preflight with a new execution namespace and one 10.23 MHz task only. Do not reuse the current locks or treat the old attempt as resumable.
5. Require Stage0 output and completion QA for that one task before releasing the remaining 10.23 MHz Wave A tasks.
6. Keep Wave B blocked until a separately approved 20.46 MHz-compatible pipeline/configuration has been designed and validated.

## Current diagnostic status

The failure is not attributable to missing scene inputs: batch preflight passed all five tasks, and the MATLAB process failed before pipeline input resolution. The project is blocked at the execution-environment and executor-call-contract layers. No SAGE result should be added to the event database from this batch.
