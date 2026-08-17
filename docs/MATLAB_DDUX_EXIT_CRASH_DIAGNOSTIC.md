# MATLAB R2025a Batch Exit Crash Diagnostic

## Scope and non-actions

This is a read-only environment diagnostic for the normal Windows user
`TJ-CHANNEL\Jing_`. It does not run SAGE, call `run_nav_sage_pipeline`, call
the Python batch executor, modify the wrapper/pipeline, or alter scene data,
metadata, inventory, execution requests, or existing results.

The evidence is limited to the two existing Windows-wrapper smoke runs, their
receipts/logs, and the MATLAB crash-dump text. No new MATLAB process was
started by Codex for this report: the Codex sandbox is not the normal user
environment and would not be a valid reproduction of this failure.

## 1. Evidence read

| Source | Finding |
|---|---|
| `windows_pilot1_g16_20260809T045310463Z/environment_receipt.json` | Normal user, PowerShell 7.6.4; marker present; MATLAB exit code `0`; duration `137.286 s`. |
| `windows_pilot1_g16_20260809T045310463Z/windows_runner_failure.json` | That attempt subsequently stopped at the Python `FilePath` type error. It did not fail in MATLAB smoke. |
| `windows_pilot1_g16_20260809T050143806Z/environment_receipt.json` | Same normal identity, executable, working directory and request; marker present; MATLAB exit code `3`; duration `8.381 s`. |
| `...T050143806Z/matlab_startup_smoke.stdout.log` | Contains exactly `MATLAB_STARTUP_OK`. |
| `...T050143806Z/matlab_startup_smoke.stderr.log` and `C:\Users\Jing_\AppData\Local\Temp\matlab_crash_dump.38520-1` | Exit-time `std::terminate()` report, current thread `GTP_6`, with `ddux.dll` and `mwddux_matlab.dll` in the captured stack. |

The second run correctly stopped before Python/SAGE because the wrapper requires both marker presence **and** native process exit code `0`. The global lock was archived as an audit file; no active worker or SAGE result was left behind.

## 2. Important correction: stability is not yet established

The available evidence is **one normal exit and one exit crash**, not two or
more identical crashes. Therefore it is not accurate to claim that this command
is deterministically “marker success followed by exit code 3.”

| Attempt | UTC start | Marker | Exit code | Duration | Interpretation |
|---|---:|---:|---:|---:|---|
| 1 | 2026-08-09 04:53:10 | yes | `0` | 137.286 s | MATLAB smoke completed; wrapper later hit the independently fixed Python path type error. |
| 2 | 2026-08-09 05:01:44 | yes | `3` | 8.381 s | MATLAB executed the smoke expression, then terminated abnormally during shutdown. |

This supports an **intermittent exit-path failure hypothesis**. It does not
support lowering the wrapper gate or treating the marker as proof that a full
SAGE process has completed safely.

## 3. Installed MATLAB identity

The crash dump is the authoritative runtime record:

```text
MATLAB Version: 25.1.0.2973910 (R2025a) Update 1
MATLAB Root:    D:\Program Files\Matlab
Architecture:   win64
OS:             Windows 11 Professional, Build 26200
```

`matlab.exe` file metadata reports `25.1.0.2802752`; this differs from the
runtime build in the crash dump and must not be used alone to identify the
installed Update. The three stack-referenced binaries exist under the installed
root (`ddux.dll`, `mwddux_matlab.dll`, `mcr.dll`), but they do not expose usable
file-version metadata through Windows Explorer/`FileVersionInfo`.

MathWorks documents that Updates are cumulative, can be installed directly
without intermediate updates, and availability is checked from MATLAB via
**Help > Check for Updates**. It also documents `version -description` as a
way to report the installed Update. [MathWorks update FAQ](https://www.mathworks.com/support/faq/mathworks-update-notifications.html)

At the time of this diagnosis, publicly accessible official pages confirm that
R2025a remains an updateable release, but they do **not** expose a reliable
machine-specific “latest R2025a Update number” to this unauthenticated process.
Do not infer a particular Update number from community posts. The normal user
must use the installed MATLAB update UI or MathWorks account/download portal to
determine the update currently offered to this license; no update was attempted
here.

## 4. What the crash stack supports — and what it does not

### Supported by direct evidence

The smoke command printed its marker. The crash happens after MATLAB calls its
full-exit path (`mnFullExitFcn`), on a `GTP_6` thread while shutdown waits for a
scheduled task/thread-pool component. The lower captured frames contain:

```text
mwddux_matlab.dll -> ddux::DduxEventKeyStatus::operator=
libmwfoundation_threadpool.dll -> ScheduledTaskSubmitter::shutdown
VCRUNTIME140.dll -> purecall
```

This makes the incident an **exit/shutdown-path native MATLAB component crash**,
not a GNSS input, SAGE algorithm, MATLAB function-parser, raw-IQ, or Python
executor failure.

### Not established by the evidence

- `ddux`/`mwddux_matlab` are internal module names; the dump does not establish
  their product feature, nor prove that a MATLAB user preference, telemetry
  service, licensing service, or graphics feature caused the fault.
- The dump lists a GameViewer virtual display adapter, NVIDIA, Intel graphics
  and hardware OpenGL, but also says graphics was uninitialized. This is useful
  support information, not evidence of a GPU cause.
- `mcr.dll`, `VCRUNTIME140.dll`, and the thread-pool frames are on the failure
  path, but do not prove corrupted runtime files or a missing Visual C++ runtime.
- The normal-user identity rules out the earlier Codex sandbox startup failure
  as the direct cause of this event; it does not prove that all user-profile or
  service interactions are healthy.

## 5. Minimal reproduction record: maximum three runs

Two valid normal-user baseline records already exist. Do **not** run a broad
matrix of shell flags now. One additional, identical normal-user test is enough
to complete a three-run baseline:

```powershell
$matlab = 'D:\Program Files\Matlab\bin\matlab.exe'
& $matlab -batch "disp('MATLAB_STARTUP_OK')"
$exitCode = $LASTEXITCODE
"MATLAB_SMOKE_EXIT_CODE=$exitCode"
```

Run it from an interactive, non-elevated `TJ-CHANNEL\Jing_` PowerShell 7
session with the ordinary user environment, not from Codex. Preserve stdout,
stderr, start/end time, exit code, and any newly named `matlab_crash_dump.*`
file. This is not SAGE and does not call project code.

Interpret the third observation as follows:

- exit `0`: the fault is demonstrably intermittent; do not yet trust it for a
  long production run, but prioritize MATLAB update/repair before another Pilot;
- exit `3` with the same shutdown frames: strengthen the reproducible MATLAB
  exit-crash case and submit the support package below;
- startup failure before marker: this is a different environment failure and
  should be recorded separately.

Do not use `-r` in place of `-batch` as a production workaround. If, after an
official update/repair decision, a parameter comparison is still needed, vary
only one startup condition in a new, explicitly approved diagnostic plan; do
not fold that experiment into the SAGE wrapper.

## 6. Required MathWorks support package

If the third baseline also crashes, provide MathWorks Support with:

1. the full text of `matlab_crash_dump.38520-1` and any new dump from test 3;
2. both smoke stdout/stderr pairs and the two `environment_receipt.json` files;
3. exact command line: `matlab -batch "disp('MATLAB_STARTUP_OK')"`;
4. MATLAB runtime identity `25.1.0.2973910 (R2025a) Update 1`, MATLAB root,
   executable file version, Windows 11 build 26200, and all displayed GPU/driver
   versions from the dump;
5. the fact that attempt 1 exited `0` after 137.286 seconds, while attempt 2
   printed the same marker but exited `3` after 8.381 seconds;
6. confirmation that no SAGE/project MATLAB code was on the call path.

Avoid sharing unrelated raw GNSS data, project files, license credentials, or
full environment dumps unless MathWorks specifically requests them.

## 7. Safest next step

**Do not relax the wrapper’s `exit code = 0` rule and do not rerun Pilot-1.**

The safest next action is for the normal user to **check for, then plan an
official cumulative R2025a update or repair** through MathWorks, after retaining
the two receipts and crash dump. This is safer than special-casing exit code 3,
because the observed failure is in MATLAB native shutdown rather than project
code. If an update/repair is not immediately possible, run only the single
third baseline above and submit the concise support package if it reproduces.

Only after MATLAB can repeatedly exit `0` for the minimal smoke should the
existing wrapper be rerun in validation-only mode and a fresh Pilot-1 execution
be considered.
