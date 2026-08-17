# MATLAB Startup Validation Report

## Test date and scope

- Date: 2026-08-09
- Purpose: validate the MATLAB process startup environment before any new batch SAGE execution.
- Scope: MATLAB startup only. No scene files, inventory, metadata, SAGE results, or `run_nav_sage_pipeline.m` were read or invoked.
- MATLAB invocation was performed with the same process semantics used by `scripts/sage_pipeline/run_batch_sage.py`: an argument-vector `subprocess.run` call, inherited environment, and `cwd=E:\GNSS_Multipath_Project`. The only MATLAB argument was the smoke-test expression below.

## Startup smoke-test result

Command expression:

```text
matlab -batch "disp('MATLAB_STARTUP_OK'); disp(tempdir)"
```

| Field | Observed value |
|---|---|
| PATH-resolved executable | `D:\Program Files\Matlab\bin\matlab.EXE` |
| Working directory | `E:\GNSS_Multipath_Project` |
| Environment | Inherited unchanged from the batch-executor process |
| Exit code | `1` |
| Startup elapsed time | `0.7874667001888156` seconds (approximately 0.787 s) |
| stdout | Empty |
| `MATLAB_STARTUP_OK` marker | Not emitted |
| `tempdir` output | Unavailable because MATLAB failed before executing the expression |

Captured stderr:

```text
Fatal Startup Error:
Dynamic exception type: class std::runtime_error
std::exception::what: System Error: File system inconsistency
ERROR: MATLAB error Exit Status: 0x00000001
```

The failure is therefore reproduced independently of the SAGE pipeline and occurs before MATLAB code execution. It is not an input-file or scene-level failure.

## MATLAB version

- Executable file/product version from the Windows version resource: `25.1.0.2802752`.
- This corresponds to the installed MATLAB R2025a-era executable.
- A non-startup `matlab -version` probe returned exit code `0` but produced no text; the version above comes from the executable version resource rather than from a MATLAB command.

## TEMP/TMP validation

| Check | Result |
|---|---|
| `TEMP` | `C:\Users\Jing_\.codex\codex-temp` |
| `TMP` | `C:\Users\Jing_\.codex\codex-temp` |
| Python-resolved temporary directory | `C:\Users\Jing_\.codex\codex-temp` |
| TEMP directory exists | Yes |
| TEMP write/read/delete probe | Passed |
| TMP write/read/delete probe | Passed |
| Probe files remaining after cleanup | None |

The current temporary root is writable for this process. This does not establish that MATLAB can write its own preference/cache directories.

## MATLAB cache and preference ACL check

Current process identity:

```text
tj-channel\codexsandboxoffline
```

The relevant MATLAB R2025a directories exist:

```text
C:\Users\Jing_\AppData\Local\MathWorks\MATLAB\R2025a
C:\Users\Jing_\AppData\Roaming\MathWorks\MATLAB\R2025a
```

`icacls` reports the following effective group entry on both directories:

```text
TJ-Channel\CodexSandboxUsers:(I)(OI)(CI)(RX)
```

The same directories grant full control to `TJ-Channel\Jing_`, `BUILTIN\Administrators`, and `NT AUTHORITY\SYSTEM`, but the active identity is `tj-channel\codexsandboxoffline`. The active group entry is read/execute only and does not include Modify or Full Control.

For comparison, the TEMP root ACL includes Modify for the active sandbox group:

```text
TJ-Channel\CodexSandboxUsers:(OI)(CI)(M)
```

No write probe was performed inside the MATLAB cache directories; the cache ACL check was read-only and did not alter user preferences or cache files.

## Diagnosis

The minimal startup test reproduces the previous Wave1 failure exactly:

1. MATLAB resolves to the expected installed executable.
2. The process starts in the expected project working directory with the expected inherited TEMP/TMP values.
3. The failure happens before `disp('MATLAB_STARTUP_OK')` and before `tempdir` can be evaluated.
4. TEMP/TMP are present and writable, so they are not the only apparent filesystem constraint.
5. MATLAB Local/Roaming R2025a cache and preference roots are accessible to the active group only as `RX`, while MATLAB startup commonly needs to create or update user-level state.

The cache/preferences ACL mismatch is the strongest current environmental lead, but this report does not claim definitive causality from ACL inspection alone. The project does not authorize changing Windows ACLs, MATLAB preferences, TEMP/TMP, or the MATLAB installation as part of this validation.

## Safe release gate for SAGE execution

Do not rerun Wave1 or invoke `run_nav_sage_pipeline.m` until an approved environment repair or execution identity is available and the exact smoke test passes with all of the following:

- exit code `0`;
- stdout contains `MATLAB_STARTUP_OK`;
- stdout contains a valid MATLAB `tempdir`;
- startup completes without `System Error: File system inconsistency`.

After that gate passes, validate one new 10.23 MHz task first and require Stage0 output before releasing the remaining Wave A tasks. Keep 20.46 MHz tasks blocked because the current phase-1 pipeline does not support that sample rate.

## Change and artifact safety

- `run_batch_sage.py` was not modified during this validation.
- `run_nav_sage_pipeline.m` was not invoked or modified.
- No scene data, `metadata.json`, `dataset_inventory.csv`, or existing SAGE result was modified.
- TEMP/TMP probe files were deleted immediately after the write/read test.
- This report is the only project artifact added by this task.
