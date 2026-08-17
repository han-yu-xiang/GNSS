# MATLAB Cache Redirect Validation

## Scope and safety

- Date: 2026-08-09
- Purpose: isolate the MATLAB startup filesystem failure before any SAGE execution.
- No scene files, `dataset_inventory.csv`, metadata, SAGE results, pipeline code, or `run_nav_sage_pipeline.m` were read or invoked.
- MATLAB was launched through the same argument-vector process style used by `run_batch_sage.py`: inherited environment, `cwd=E:\GNSS_Multipath_Project`, and `subprocess.run([matlab, ...])` with no shell command and no pipeline expression.
- `MATLAB_PREFDIR`, and in one controlled comparison `TEMP`/`TMP`, were set only in the child process environment. The parent/system environment and the original MathWorks directories were not changed.

## Redirect mechanism

The temporary user configuration redirect used for the test was:

```text
MATLAB_PREFDIR=E:\GNSS_Multipath_Project\MATLAB_RUNTIME_CACHE_TEST
```

This is the MATLAB-supported environment-variable mechanism for selecting a custom preferences directory; see [MathWorks guidance on changing the MATLAB preferences directory](https://www.mathworks.com/matlabcentral/answers/93696-how-do-i-change-the-matlab-preferences-directory-location).

The directory was newly created outside all scene and SAGE-result trees. It is writable by the current process. No ACL or original MathWorks directory was changed.

## Test A: new writable MATLAB preferences directory

Command:

```text
matlab -batch "disp('MATLAB_STARTUP_OK'); disp(tempdir)"
```

Environment differences from the batch executor: only `MATLAB_PREFDIR` was added. `TEMP` and `TMP` remained `C:\Users\Jing_\.codex\codex-temp`.

| Field | Result |
|---|---|
| Executable | `D:\Program Files\Matlab\bin\matlab.EXE` |
| Working directory | `E:\GNSS_Multipath_Project` |
| `MATLAB_PREFDIR` | `E:\GNSS_Multipath_Project\MATLAB_RUNTIME_CACHE_TEST` |
| Exit code | `1` |
| Elapsed time | approximately `1.0884022000` s |
| stdout | Empty |
| `MATLAB_STARTUP_OK` | Not emitted |
| `tempdir` | Not emitted; MATLAB code did not execute |
| stderr | `System Error: File system inconsistency` startup failure |

Captured failure:

```text
Fatal Startup Error:
Dynamic exception type: class std::runtime_error
std::exception::what: System Error: File system inconsistency
ERROR: MATLAB error Exit Status: 0x00000001
```

### Evidence that the redirect was read

After Test A, MATLAB had created the following files below the redirected directory:

```text
MATLAB_RUNTIME_CACHE_TEST\MLintDefaultSettings.txt
MATLAB_RUNTIME_CACHE_TEST\webwindowscale.mlsettings
MATLAB_RUNTIME_CACHE_TEST\webwindowscale\webwindowscaleR2024b.log
MATLAB_RUNTIME_CACHE_TEST\ddux.mlsettings
MATLAB_RUNTIME_CACHE_TEST\ddux\dduxR2024b.log
```

Therefore `MATLAB_PREFDIR` was effective at least for early settings initialization. The failure occurs after those writes and before the requested MATLAB command executes. The generated settings logs describe an R2024b settings upgrade; this is recorded evidence only and is not treated as the cause.

## Test B: preferences and TEMP/TMP redirected to E drive

This comparison kept the Test A preferences directory and additionally set, only for the child process:

```text
TEMP=E:\GNSS_Multipath_Project\MATLAB_RUNTIME_CACHE_TEST\temp
TMP=E:\GNSS_Multipath_Project\MATLAB_RUNTIME_CACHE_TEST\temp
```

| Field | Result |
|---|---|
| Exit code | `1` |
| Elapsed time | approximately `0.8708482999` s |
| stdout | Empty |
| `tempdir` | Not emitted |
| stderr | Same `System Error: File system inconsistency` |
| Test TEMP directory | Remained empty after the failed launch |

Redirecting TEMP/TMP together with the preferences directory did not change the failure.

## Test C: preferences redirected to a writable C drive directory

To distinguish an E-drive filesystem issue from a general startup issue, the child process used:

```text
MATLAB_PREFDIR=C:\Users\Jing_\.codex\codex-temp\matlab_pref_test
TEMP=C:\Users\Jing_\.codex\codex-temp
TMP=C:\Users\Jing_\.codex\codex-temp
```

| Field | Result |
|---|---|
| Exit code | `1` |
| Elapsed time | approximately `0.7950055999` s |
| stdout | Empty |
| `tempdir` | Not emitted |
| stderr | Same `System Error: File system inconsistency` |

MATLAB created the same early settings files under the C-drive redirected preferences directory. Thus the failure is not explained by the E-drive location alone.

## Environment and permission evidence

Current process identity:

```text
tj-channel\codexsandboxoffline
```

MATLAB runtime help reports:

```text
Version: 25.1.0.2973910
```

The earlier executable resource inspection reported `25.1.0.2802752`; this is launcher/file metadata and differs from the runtime version printed by `matlab -help`. Use the `-help` value as the current MATLAB command-line runtime version.

The original MATLAB settings roots still have only this entry for the active sandbox group:

```text
TJ-Channel\CodexSandboxUsers:(I)(OI)(CI)(RX)
```

The new E-drive directory and the C-drive temporary preferences directory are writable, and MATLAB successfully created settings files in both. The MATLAB installation itself is readable/executable by the normal Users group, as expected. No original MathWorks ACL was changed.

## Diagnosis after redirect tests

The redirect experiment does not validate startup. It does establish the following:

1. The `MATLAB_PREFDIR` mechanism is recognized and used for early settings writes.
2. Moving preferences to a writable E-drive directory does not fix startup.
3. Moving both preferences and TEMP/TMP to writable E-drive directories does not fix startup.
4. Moving preferences to a writable C-drive directory also does not fix startup.
5. The failure remains before `disp('MATLAB_STARTUP_OK')`, `tempdir`, or any SAGE code can run.
6. The original MathWorks cache ACL remains a valid environmental concern, but it is not sufficient as the sole explanation for this failure.

The remaining source is not identifiable from the available startup stderr. Candidates requiring separate system-level investigation include another user/profile or license/cache path outside `MATLAB_PREFDIR`, a MATLAB installation/runtime filesystem check, or an interaction between the sandbox process identity and MATLAB startup filesystem APIs. No such cause is asserted without additional evidence.

An attempted `-logfile` launch with the redirected preferences directory also returned the same error and did not create a MATLAB log file, so it provided no additional startup trace.

## Execution gate

Do not run Wave1, invoke `run_batch_sage.py --execute`, or call `run_nav_sage_pipeline.m` until a standalone smoke test passes with:

- exit code `0`;
- `MATLAB_STARTUP_OK` in stdout;
- a valid `tempdir` in stdout;
- no `System Error: File system inconsistency`.

After startup is repaired, validate one new 10.23 MHz task only and require Stage0 output before releasing additional tasks. Keep 20.46 MHz tasks blocked under the current phase-1 pipeline.

## Artifacts and non-modification statement

- Added this report: `docs/MATLAB_CACHE_REDIRECT_VALIDATION.md`.
- Created the requested isolated directory: `E:\GNSS_Multipath_Project\MATLAB_RUNTIME_CACHE_TEST`.
- Created a separate C-drive comparison directory under the existing Codex TEMP root: `C:\Users\Jing_\.codex\codex-temp\matlab_pref_test`.
- The test settings files are retained as diagnostic evidence; no original MathWorks files were changed.
- No pipeline, scene data, metadata, inventory, or existing SAGE result was modified.
