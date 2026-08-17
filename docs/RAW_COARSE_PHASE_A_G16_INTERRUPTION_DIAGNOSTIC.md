# G16 Phase-A 中断诊断与重新执行准备

生成日期：2026-08-12

本报告只分析第一次 G16 Phase-A 的 interrupted artifact，并记录一个全新的 fresh-run manifest。没有运行第二次 raw-coarse，没有调用 MATLAB/SAGE，没有运行 G25/G11，也没有删除、移动、覆盖或 resume 旧输出。

## 1. 结论摘要

第一次运行的最保守分类为：`external_interrupt_likely`，但具体来源为 `unknown`。

证据表明：

- executor 父进程在 `invoke_evaluator()` 的 `except KeyboardInterrupt` 分支收到 `KeyboardInterrupt`；
- receipt 的错误文本是 `KeyboardInterrupt; evaluator terminated and outputs preserved`，不是 stall 或 total timeout 文本；
- 运行时间约 57.61 s，远低于 1800 s stall timeout 和 48 h total timeout；
- 21 个 chunk 持续完成，最大相邻 chunk 间隔约 4.49 s，没有长时间无进度或 raw I/O error 证据；
- worker stderr 只有 `WORKER_INTERRUPTED`，没有 traceback、Ctrl+C 标记、signal number 或 PowerShell transcript；
- 因此不能证明是用户按下 Ctrl+C，也不能证明是 Windows 控制台、宿主环境或其他外部终止源。

第一次运行不是科学上完成的 Phase-A 结果，不能用于 coverage、promotion、cost 或任何 multipath 结论。

## 2. 诊断对象与不可变历史证据

旧 manifest：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_execution_requests_20260812\phase_a1_g16_20260812\execution_manifest.json
SHA-256: bca6c592f3d107841f5b2e9459f48cfacb777cfc8cc28c779a91a0be4e70920c
```

旧输出目录：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_outputs_20260812\Phase-A1_F1023_V70_D0120_P7_G16_ch1
```

旧 receipt：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_outputs_20260812\Phase-A1_F1023_V70_D0120_P7_G16_ch1\execution_receipt.json
```

旧 receipt 的关键字段：

| 字段 | 实际值 |
|---|---|
| `request_id` | `phase_a1_g16_20260812` |
| `status` | `interrupted` |
| `raw_read_status` | `interrupted` |
| `exit_code` | `null` |
| `error` | `KeyboardInterrupt; evaluator terminated and outputs preserved` |
| `resume` | `false` |
| `automatic_next_task` | `false` |
| `gold_labels_used_for_selection` | `false` |

旧目录被保留为诊断 artifact。它不允许再次执行：executor 的 `new_only` 门禁会拒绝已存在的 output namespace。

## 3. KeyboardInterrupt 的代码传播路径

旧版本 executor 的相关路径为：

1. `main()` 解析 `--execute`，调用 `execute()`。
2. `execute()` 获取全局锁后调用 `invoke_evaluator()`。
3. `invoke_evaluator()` 通过 `subprocess.Popen()` 启动 worker Python 进程。
4. 父进程在监控循环中等待 worker，并检查输出文件 mtime。
5. 父进程的 `except KeyboardInterrupt` 捕获 Python 层中断，调用 `process.terminate()`，将状态写成 `interrupted`，并写入上述 error 文本。
6. worker 的 `run_worker()` 也有独立的 `except KeyboardInterrupt`，向 stderr 写入 `WORKER_INTERRUPTED` 并返回 130。

当前代码定位：

- 父进程捕获路径：`scripts/sage_pipeline/run_raw_coarse_phase_a.py` 的 `invoke_evaluator()`；
- worker 捕获路径：同文件的 `run_worker()`；
- 内部 stall/total timeout 路径：同文件 `invoke_evaluator()` 监控循环；
- raw coarse 执行主体：`run_task_with_v2_adapter()` → `run_raw_pass_adapter()` → 冻结 v2 kernel。

receipt 和 stderr 共同说明本次走的是 `KeyboardInterrupt` 路径，而不是代码主动产生的 `KeyboardInterrupt`。原代码没有安装 signal handler，因此无法从旧 artifact 中恢复 signal number 或信号来源。

## 4. timeout、stall、子进程与终端证据判断

### 4.1 executor timeout/stall

代码中的内部门禁是：

- `STALL_TIMEOUT_SECONDS = 1800.0`；
- `TOTAL_TIMEOUT_SECONDS = 48 * 3600.0`。

若触发 stall，error 应为 `stall timeout exceeded (...)`；若触发总时长门禁，error 应为 `total timeout exceeded (...)`。旧 receipt 没有这两类文字，而是精确的 `KeyboardInterrupt` error，因此没有证据支持 `internal_timeout_bug`。

旧 receipt schema 没有独立的 `interruption_reason` 字段，所以只能依据 error 文本和代码路径区分。新 executor 已增加：

- `interruption_reason`；
- `interrupt_provenance`；
- `last_progress_age_s`；
- `executor_pid`、`worker_pid`；
- `execution_context`，包含 phase、current function、current chunk、last progress。

### 4.2 子进程终止

父进程在收到 `KeyboardInterrupt` 后会终止 worker。旧 stderr 的 `WORKER_INTERRUPTED` 与中断传播一致，但它不能证明最初的中断来自 worker；也没有 worker exit code 被完整写入父 receipt，父 receipt 的 `exit_code=null` 是该路径的现状。

### 4.3 PowerShell/Windows 控制台

项目 artifact 中没有 PowerShell transcript、Windows console event receipt、Ctrl+C 文本、SIGINT/SIGTERM 编号或宿主终止记录。因此：

```text
是否由 TJ-CHANNEL\Jing_ 手动 Ctrl+C：unknown
是否由 PowerShell 控制台产生：unknown
是否由 Codex/宿主环境注入中断：unknown
```

只能说 Python 父进程确实收到了 `KeyboardInterrupt`，其来源不能从现有日志唯一确定。

## 5. 最后 20 条以上 progress 记录与运行节奏

原始 progress 文件：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_outputs_20260812\Phase-A1_F1023_V70_D0120_P7_G16_ch1\progress.jsonl
```

该文件共有 23 条记录：`input_loaded`、`selection_frozen` 和 21 条 `chunk_completed`。最后 21 条 chunk 记录均已读取；最后一条为：

```text
timestamp_utc=2026-08-12T03:14:51.978950Z
event=chunk_completed
chunk_id=chunk_00021
processed_windows=80
total_windows=2229
bytes_read=66290540
```

汇总：

| 指标 | 值 |
|---|---:|
| 最后成功 chunk | `chunk_00021` |
| 已完成 chunk | 21 |
| Stage0 总窗口 | 2229 |
| 已处理窗口 | 1680（21×80） |
| 累计实际读取字节 | 1,392,101,328 |
| 第一条 chunk 时间 | 2026-08-12 03:13:58.441017Z |
| 最后一条正常 progress | 2026-08-12 03:14:51.978950Z |
| receipt 结束时间 | 2026-08-12 03:14:53.733919Z |
| 最后 progress 到 receipt 的间隔 | 1.754969 s |
| 第一到最后 chunk 的间隔 | 53.537933 s |
| 平均相邻 chunk 间隔 | 2.676897 s |
| 前 5 个间隔平均值 | 2.238434 s |
| 后 5 个间隔平均值 | 3.614654 s |
| 最大相邻 chunk 间隔 | 4.487440 s |

旧 progress schema 没有 `elapsed`、`estimated_remaining`、`heartbeat`、累计 `processed_windows` 或累计 `bytes_read` 字段；这些字段不是“0”，而是未记录。上表的累计窗口/字节和时间差是本次只读分析推导值。没有发现 chunk_failed、raw_read_error 或长时间 heartbeat 缺失。

整体表现为持续推进，后半段 chunk 间隔略长，但 21 个 chunk 的样本不足以确认性能退化；它不符合 1800 秒 stall 的表现，也没有 I/O 异常证据。

## 6. 已生成 partial artifact 的边界

旧目录中存在：

- `coarse_parameter.json`；
- `coarse_parameter.sha256`；
- `selection_freeze.json`；
- `phaseA_F1023_V70_D0120_P7_G16_ch1\input_receipt.json`；
- `progress.jsonl`；
- `executor_stdout.log`；
- `executor_stderr.log`；
- `execution_receipt.json`。

旧目录没有完整三个 profile 的 coarse window manifest、promotion manifest、component、cost、coverage replay，也没有完整 Phase-A receipt。因此这些 partial 文件只用于诊断，不能被当作科学结果、fine Stage1 输入或 QA PASS 依据。

## 7. 仅限观测性的代码调整

修改文件：

```text
E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_raw_coarse_phase_a.py
```

调整范围严格限于：

- 安装 `SIGINT`、`SIGTERM`、Windows 可用时的 `SIGBREAK` handler，仅记录 provenance 后保留 `KeyboardInterrupt` 语义；
- progress JSONL 增加 PID、parent PID、phase、current function、current chunk、累计窗口、累计字节、elapsed 和 estimated remaining；
- receipt 增加中断原因、信号 provenance、执行上下文、父/子 PID、last-progress age；
- 对内部 stall 与 total timeout 使用独立 `internal_stall_timeout` / `internal_total_timeout` reason；
- retry manifest 只允许固定 G16、ch1、10.23 MHz，并验证 fresh-only、resume=false、旧 interrupted receipt 和 executor hash；
- 不改变 raw-coarse 数学 kernel、B1/B2 profile、真实 Doppler offsets、threshold、normalization、promotion、gold selection 或输出科学字段。

当前 executor hash：

```text
e87f382db0f7c611926d529eb594f99c6e48713a5c4c76ca10eba58f5cbd7b42
```

相关测试：

- `py_compile`：通过；
- `test_run_raw_coarse_phase_a.py`：20/20 通过；
- 覆盖 retry identity、resume rejection、SIGINT provenance、旧 output new-only rejection 等场景。

## 8. G16 fresh retry manifest

新的 manifest namespace：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_retry_requests_20260812
```

新的 manifest：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_retry_requests_20260812\phase_a1_g16_retry1_20260812\execution_manifest.json
```

属性：

| 字段 | 值 |
|---|---|
| manifest id | `phase_a1_g16_retry1_20260812` |
| manifest SHA-256 | `1f279208d8747a8639ce3599c8621f7a7f8a79e154eac01127f5956c49f6641d` |
| `fresh_run_only` | `true` |
| `resume_allowed` | `false` |
| `supersedes_interrupted_manifest` | `phase_a1_g16_20260812` |
| `previous_interruption_receipt` | 旧 G16 `execution_receipt.json` 的绝对路径 |
| scene/PRN/channel | `F1023_V70_D0120_P7/G16/ch1` |
| sample rate | 10.23 MHz |
| parameter SHA-256 | `41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2` |
| kernel | `numpy-batched-complex128-v2-aligned` |
| Python | `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe` |
| gold selection | `false` |

新的 output namespace：

```text
E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_phase_a_retry_outputs_20260812\Phase-A1-Retry1_F1023_V70_D0120_P7_G16_ch1
```

旧 output namespace 与新 output namespace 完全分离。旧目录未被删除或覆盖，新目录在 validation-only 时不存在。

## 9. 新 manifest validation-only 结果

使用新 manifest 和其 SHA 执行的 validation-only 结果：

```text
REQUEST_ID=phase_a1_g16_retry1_20260812
TASK=F1023_V70_D0120_P7/G16/ch1/10230000
BACKEND_PYTHON=D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe
BACKEND_PYTHON_VERSION=3.12.9
NUMPY=2.5.1
SCIPY=1.18.0
KERNEL_VERSION=numpy-batched-complex128-v2-aligned
PARAMETER_SHA256=41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2
OUTPUT_EXISTS=False
EVALUATOR_TASK_API_AVAILABLE=True
EXECUTION_ELIGIBLE=True
EXECUTE_DISPATCH_AVAILABLE=True
RAW_IQ_READ_DURING_VALIDATION=false
```

validation-only 没有读取大规模 raw IQ、没有创建 retry output 目录、没有创建全局锁、没有运行 evaluator。

## 10. 最终边界与下一步

当前只具备 fresh G16 retry 的人工执行准备条件，不代表 G16 Phase-A 已成功，也不代表研究门禁通过。旧 interrupted artifact 必须继续保留；不得 resume、删除后复用、把 partial profile 当结果或启动 G25/G11。

唯一下一步：由正常 Windows 用户在人工确认后，使用新的 G16 retry manifest 进行一次 fresh-only 正式执行；执行结束后先做独立 QA。若再次 interrupted/failed，保留新 artifact 并停止，不自动重试、不启动 G25。
