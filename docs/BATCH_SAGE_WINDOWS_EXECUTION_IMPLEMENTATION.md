# BATCH SAGE Windows 正常用户执行 Wrapper：实现说明

## 1. 交付内容与边界

本次实现为 Windows 正常用户执行路径增加了一个很窄的人工执行边界：

- Wrapper：`scripts/sage_pipeline/Invoke-BatchSageWindows.ps1`
- 首个不可变请求包：`dataset_generation_logs/batch_sage_execution_requests/windows_pilot1_g16_20260809/`

本次**没有**调用 MATLAB、没有运行 SAGE、没有修改 `run_nav_sage_pipeline.m`、`run_batch_sage.py`、metadata、inventory、scene 数据或既有结果。`run_batch_sage.py` 保持为唯一的任务解析、输入门禁、reference 保护、输出冲突检查、串行 MATLAB 调用、Stage QA 与 task 状态记录实现。

PowerShell 只承担正常用户边界、hash 冻结、Pilot-1 scope、跨 execution 锁、MATLAB startup smoke test 与 Python execution receipt，不从 inventory 生成任务，也不复制 Python 的通用 scene 输入门禁。

## 2. 当前唯一释放的 Pilot

| Field | Frozen value |
|---|---|
| Request ID | `windows_pilot1_g16_20260809` |
| Scene / PRN / channel | `F1023_V70_D0120_P7 / G16 / 1` |
| Sampling rate | `10230000 Hz` (10.23 MHz) |
| Output | `scenes/F1023_V70_D0120_P7/sage_results/nav_sage_v2/G16` |
| Plan status at release | `ready`, unique channel, no hard gate failure |
| MATLAB parent identity | exact `TJ-Channel\Jing_` only |
| Execution mode | `new_only`; no automatic resume |

The two 20.46 MHz Wave-B selections remain outside this request and cannot pass this release of the wrapper.

## 3. Wrapper controls

`Invoke-BatchSageWindows.ps1` requires PowerShell 7 and does the following before it can start MATLAB:

1. verifies the manually supplied SHA-256 of `execution_request.json`;
2. verifies SHA-256 for the immutable plan, one-task selection snapshot, pipeline and Python executor;
3. requires the exact frozen Pilot-1 G16/ch1/10.23 MHz request and plan row;
4. verifies the target output directory is still absent;
5. rejects `codexsandboxoffline`, any identity other than `TJ-Channel\Jing_`, and elevated Administrator shells;
6. defaults to validation-only; actual execution requires both `-Execute` and `-ConfirmPilot`;
7. atomically creates `dataset_generation_logs/batch_sage_execution/.windows_runner_active.lock` before smoke/execution;
8. when actual execution is authorized, runs only `matlab -batch "disp('MATLAB_STARTUP_OK')"` as an environment gate, then calls the existing Python executor with an argument array;
9. reads `batch_execution_log.csv` after Python returns, so Python exit code 0 alone cannot be mistaken for a completed task;
10. writes new receipt/log files under `batch_sage_execution/windows_runner_receipts/` and archives the global lock there (or in the Python execution root) after a controlled finish. A crash/forced termination intentionally leaves the active lock for manual review.

The wrapper uses `.NET ProcessStartInfo.ArgumentList`; it does not use `Invoke-Expression`, `cmd /c`, a credential store, `runas`, Scheduled Tasks, or a cross-user automatic launch mechanism.

## 4. Request hash and manual commands

The current request SHA-256 is:

```text
cf55e07bb8258de9682894767de480534463ee84741354c6c053291c82c44b6f
```

From an interactive, non-elevated **PowerShell 7** session owned by `TJ-Channel\Jing_`, first run validation-only:

```powershell
pwsh -NoProfile -File E:\GNSS_Multipath_Project\scripts\sage_pipeline\Invoke-BatchSageWindows.ps1 `
  -RequestManifest E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\windows_pilot1_g16_20260809\execution_request.json `
  -ExpectedRequestSha256 cf55e07bb8258de9682894767de480534463ee84741354c6c053291c82c44b6f
```

This validation command must print `VALIDATION_ONLY_OK matlab_invoked=false`; it does not start MATLAB or Python.

Only after the request package and this hash have been independently reviewed may the normal user choose to run the one-task Pilot-1 execution:

```powershell
pwsh -NoProfile -File E:\GNSS_Multipath_Project\scripts\sage_pipeline\Invoke-BatchSageWindows.ps1 `
  -RequestManifest E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\windows_pilot1_g16_20260809\execution_request.json `
  -ExpectedRequestSha256 cf55e07bb8258de9682894767de480534463ee84741354c6c053291c82c44b6f `
  -Execute -ConfirmPilot
```

Do not add `-ExecutionPolicy Bypass` as a routine workaround. The script should run under the user-managed local PowerShell policy. If any frozen file changes, regenerate and re-review a new request; do not update a hash in place and do not reuse this approval value.

## 5. Verification completed in this implementation task

- The current frozen plan row is the expected `G16/ch1` ready task at 10.23 MHz.
- The request records the current SHA-256 values for plan, selection snapshot, pipeline and executor. `SHA256SUMS.txt` provides the same audit values.
- `Invoke-BatchSageWindows.ps1` passed a PowerShell AST syntax parse with no parser errors.
- No wrapper `-Execute` command, MATLAB process, smoke test, pipeline, or SAGE stage was run.

The sandbox/normal-user split is intentional: Codex must not attempt the final two commands. OpenAI documents that Codex’s Windows sandbox runs descendant commands under a constrained, dedicated execution boundary, which explains why this wrapper requires a separately launched normal-user console rather than attempting to cross that boundary automatically. [OpenAI Windows sandbox design](https://openai.com/index/building-codex-windows-sandbox/)

## 6. After an authorized pilot

The normal-user wrapper will create a fresh Python execution root and a wrapper receipt directory. Codex’s next task is read-only review of:

- `environment_receipt.json`;
- `execution_receipt.json` or `windows_runner_failure.json`;
- Python `batch_execution_log.csv`, task log and report;
- if completed, the new G16 Stage0–Stage4 files and output QA.

Do not release the remaining 10.23 MHz Wave-A tasks, design a 20.46 MHz path, modify the pipeline, or retry automatically until the Pilot-1 receipt and all Stage outputs have been reviewed.
