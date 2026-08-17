# MATLAB Batch Startup Root-Cause Analysis

## Scope and conclusion

This is an environment-only diagnostic. No SAGE task, scene data, pipeline code, metadata, inventory, or existing result was read or modified during this analysis.

The available evidence no longer supports treating `MATLAB_PREFDIR` or `TEMP`/`TMP` permissions as the sole root cause. MATLAB recognizes and writes to fresh redirected preference directories on both E: and C:, yet exits before executing even `disp('MATLAB_STARTUP_OK')` with:

```text
System Error: File system inconsistency
```

The strongest remaining hypothesis is an execution-identity mismatch: Codex runs MATLAB as a restricted local account, while the installed MATLAB/MathWorks user state belongs to the normal interactive Windows user. This is not yet proven causally because the same smoke test has not been run under the normal user identity.

## 1. Execution identity versus normal Windows user

| Property | Codex execution process | Normal interactive user |
|---|---|---|
| Account | `tj-channel\codexsandboxoffline` | `TJ-Channel\Jing_` |
| Local group membership | `CodexSandboxUsers`, `Users` | `Administrators`, `Users` |
| Observed privilege set | Only `SeChangeNotifyPrivilege` was enabled in `whoami /all` | Not measured from inside this sandbox; local-account metadata shows Administrators membership |
| Console session | Not the interactive console user | `jing_` is currently active in console session ID 4 |
| Effective access to MathWorks user state | Usually inherited `RX`; some child directories cannot be enumerated | Explicit `Full Control` ACE on the inspected MathWorks user roots |

The difference is concrete in ACLs. For example, the following user roots grant the sandbox group only read/execute while granting `TJ-Channel\Jing_` full control:

```text
C:\Users\Jing_\AppData\Local\MathWorks
C:\Users\Jing_\AppData\Local\MathWorks\MATLAB\R2025a
C:\Users\Jing_\AppData\Roaming\MathWorks
C:\Users\Jing_\AppData\Roaming\MathWorks\MATLAB\R2025a
```

Typical ACL evidence:

```text
TJ-Channel\CodexSandboxUsers:(I)(OI)(CI)(RX)
TJ-Channel\Jing_:(I)(OI)(CI)(F)
```

This means a MATLAB process launched by Codex can read much of the normal user's MathWorks state but cannot reliably update it, even though the process inherits `USERPROFILE=C:\Users\Jing_` and related `APPDATA`/`LOCALAPPDATA` values.

## 2. MATLAB startup paths inspected

| Area | Observed path(s) | Current sandbox result | Diagnostic meaning |
|---|---|---|---|
| Preferences/settings | `C:\Users\Jing_\AppData\Roaming\MathWorks\MATLAB\R2025a` | Root and files are `RX` for sandbox; `Jing_` has full control | A known mismatch, but custom `MATLAB_PREFDIR` did not fix startup alone. |
| Local toolbox cache | `C:\Users\Jing_\AppData\Local\MathWorks\MATLAB\R2025a\toolbox_cache-25.1.0-1812969456-win64.xml` | Exists; sandbox has `RX`, normal user has full control | May be accessed independently of the preferences redirect. |
| Local MathWorks services | `C:\Users\Jing_\AppData\Local\MathWorks\ServiceHost` and `mwEndpointRegistry` | Sandbox has `RX` | These locations are outside `MATLAB_PREFDIR`. |
| User licensing state | `C:\Users\Jing_\AppData\Roaming\MathWorks\licensing`, `mwhome`, `user_id` | Sandbox has `RX` | Potential dependency for signed-in/licensed MATLAB state. |
| Credentials | `C:\Users\Jing_\AppData\Roaming\MathWorks\credentials` | Sandbox received `Access denied` when attempting read-only directory enumeration | Stronger than a normal read-only condition; it can affect MathWorks login/service discovery. |
| ProgramData | `C:\ProgramData\MathWorks\R2025a` | Exists; contains `ShellExtensions`; no direct access-denied evidence | Not a leading failure candidate from current evidence. |
| Installed license manifest | `D:\Program Files\Matlab\licenses\license_info.xml` | Exists and is readable under normal Users `RX` ACL | Installation license manifest is not visibly blocked. |
| MATLAB runtime | `D:\Program Files\Matlab\runtime\win64`, `bin\win64`, `sys\java\jre\win64\jre` | Present with normal Users `RX` ACL | Read/execute access is expected for an installed program. `matlab -help` works. |
| Installation toolbox cache | `D:\Program Files\Matlab\toolbox\local\toolbox_cache-mcr-win64.xml` | Exists and readable with normal Users `RX` ACL | No direct permission failure observed. |
| Windows system temp | `C:\Windows\Temp` | Sandbox could not enumerate it and `icacls` returned access denied | Current `TEMP`/`TMP` are elsewhere; this remains only a possible auxiliary startup/crash-reporting dependency, not a demonstrated cause. |

Note: `os.access(..., W_OK)` is not used as proof on Windows because it can report writable despite restrictive ACLs. The analysis relies on `icacls`, direct enumeration, and the actual MATLAB startup results.

## 3. What the redirect experiments establish

The prior validation report recorded three failing smoke-test variants, all limited to:

```text
matlab -batch "disp('MATLAB_STARTUP_OK'); disp(tempdir)"
```

| Variant | Child-process changes | Outcome |
|---|---|---|
| Baseline | None | Exit `1`; no marker or `tempdir`; filesystem-inconsistency error. |
| A | Fresh writable E-drive `MATLAB_PREFDIR` | Exit `1`; MATLAB created settings files in the redirected directory before failing. |
| B | Variant A plus fresh E-drive `TEMP` and `TMP` | Exit `1`; same error; redirected temp subdirectory remained empty. |
| C | Fresh writable C-drive `MATLAB_PREFDIR` | Exit `1`; MATLAB again created early settings files before failing. |

Consequences:

1. `MATLAB_PREFDIR` is honored for early settings initialization.
2. Neither a fresh preference directory nor a fresh TEMP/TMP directory is sufficient.
3. The startup failure is after early settings writes but before requested MATLAB code runs.
4. Original preferences/cache ACLs remain relevant, but they are not an adequate standalone explanation.
5. The failure is not explained solely by use of the E: drive.

Detailed evidence is retained in `docs/MATLAB_CACHE_REDIRECT_VALIDATION.md` and `docs/MATLAB_STARTUP_VALIDATION_REPORT.md`.

## 4. Supporting logs and their limits

The inspected MathWorks ServiceHost logs contain two relevant observations:

- The client log records `Cannot start service: MatlabLogin as dependency: credentials not satisfied.`
- The same log records failed access-token requests with `SSL connect error` / `CURLcode=35`.

These entries show that the existing MathWorks ServiceHost environment associated with this user profile has credential/network dependency failures. They do **not** contain `System Error: File system inconsistency`, and their timestamps cannot prove that they are emitted by the short-lived batch process. They are supporting context, not a root-cause attribution.

Windows Application events for IDs 1000, 1001, and 1026 were also queried. No recent MATLAB crash/fault event was correlated with the 2026-08-09 batch smoke tests. A returned MATLAB WER event was historical (2026-07-26) and was a `RADAR_PRE_LEAK_64` report, not this startup failure.

The attempted MATLAB `-logfile` smoke launch did not create a log before failure, so it added no startup trace.

## 5. Ranked root-cause hypotheses

| Rank | Hypothesis | Evidence for | Evidence against / limitation |
|---|---|---|---|
| 1 | Sandbox identity cannot use one or more persistent MathWorks user-state paths (credentials, licensing, ServiceHost, endpoint registry, local cache) | Separate OS account; restrictive `RX` ACLs; credentials directory cannot be enumerated; preference redirect does not cover all paths | No direct MATLAB trace identifies the exact denied path. |
| 2 | MATLAB startup expects the interactive `Jing_` profile/service context and cannot operate fully under `codexsandboxoffline` | Active normal-user console session; product state is owned by `Jing_`; ServiceHost log has credentials dependency failure | Requires an identity-controlled smoke-test comparison to prove. |
| 3 | A system-level MATLAB/runtime filesystem compatibility or installation issue affects every identity | Failure is a generic filesystem runtime error before MATLAB code; redirect experiments do not resolve it | `matlab -help` and early redirected-settings writes succeed; normal user has not yet been tested. |
| 4 | TEMP or preferences alone are the root cause | Initial ACL mismatch was real | Contradicted by fresh C/E preference and TEMP/TMP tests. |
| 5 | Installation/runtime folders are unreadable | None | Basic normal-Users `RX` ACLs are present and `matlab -help` works. |

## 6. Minimal sandbox-attribution validation plan

The decisive test is an identity-controlled comparison, not another SAGE run.

### Required control test: native normal-user session

Run the following from a normal Windows Command Prompt or PowerShell opened directly by the active `TJ-Channel\Jing_` user, **outside Codex**. It does not load project code, does not use a scene directory, and runs only the allowed startup marker.

```bat
set "MATLAB_PREFDIR=%TEMP%\matlab_pref_smoke_%RANDOM%"
"D:\Program Files\Matlab\bin\matlab.exe" -batch "disp('MATLAB_STARTUP_OK')"
echo ExitCode=%ERRORLEVEL%
```

Record the exit code, stdout/stderr, the generated `MATLAB_PREFDIR` path, and elapsed time. Do not set a persistent environment variable; this `set` applies only to that command-shell process.

### Interpretation

| Normal-user smoke result | Meaning | Safe next action |
|---|---|---|
| Exit `0` and marker appears | Strong evidence that the Codex sandbox identity/environment is the blocker | Keep SAGE execution outside Codex or arrange an approved execution method under the normal user; do not weaken ACLs blindly. |
| Same filesystem-inconsistency failure | Sandbox identity is not the sole cause | Escalate to MATLAB installation/runtime and Windows filesystem diagnostics; do not retry Wave1. |
| Different license/credential error | User-state/service access is implicated | Resolve licensing/service state under the normal user before revisiting batch execution. |

This task cannot automatically impersonate `Jing_` from `codexsandboxoffline`: doing so would require user credentials, a pre-authorized scheduled task, or another system-level execution mechanism. None is assumed or created here.

## 7. If the native control still fails

Perform these system-level diagnostics separately, still using only the one-line marker smoke test:

1. Capture a Process Monitor trace for `MATLAB.exe` and `matlab.exe`, filtering for `ACCESS DENIED`, `NAME NOT FOUND`, and filesystem-related results during the one-second startup interval.
2. Compare the first failing path under the normal user with the sandbox result; do not grant broad permissions until the exact path and required access type are known.
3. Check MATLAB installation integrity/repair through an approved MathWorks/IT workflow rather than editing files beneath `D:\Program Files\Matlab`.
4. If a credential or ServiceHost path appears in the trace, repair it from the normal `Jing_` session, not by granting the sandbox account full access to the whole profile.

## 8. Safety status

- No SAGE, MATLAB pipeline, or project scene was run in this task.
- No source code, metadata, inventory, experiment result, license file, user profile ACL, or MathWorks directory was modified.
- This report is the only project file created by this task.
- The next allowed execution gate remains a successful standalone `MATLAB_STARTUP_OK` smoke test; Wave1 must remain blocked until then.
