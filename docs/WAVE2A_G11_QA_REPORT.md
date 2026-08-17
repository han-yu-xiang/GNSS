# Wave-2A G11 执行后只读 QA 报告

## 1. QA 范围与结论

本报告针对唯一任务 `F1023_V120_D0121_P2/G11/ch0/10.23MHz`，只读取 Windows wrapper 回执、batch 执行日志、状态历史、任务日志、Stage0–Stage4 输出及 reference scene 对照结果。未运行 MATLAB、SAGE 或 Python batch executor，未修改 pipeline、scene、metadata、inventory 或已有 SAGE 结果。

最终结论：**PASS**。

G11 的 Windows 正常用户执行链、MATLAB smoke、Python executor、MATLAB pipeline、Stage0–Stage4 输出 QA 均通过。Stage3 和 Stage4 没有可靠/联合多径事件，但对应 CSV/MAT 输出完整，属于本次输入下的有效空结果，不是执行失败或结果缺失。

**允许继续 Wave-2A 剩余任务：是，但必须保持受控串行执行。** 当前 G11 的总耗时约 19.6 小时，Stage1 约 8.1 小时，Stage2 约 11.4 小时；后续任务应继续逐任务、非并行、每次独立 QA，不能把本次耗时当作普通短任务预算。

## 2. 任务、请求与执行证据

| 项目 | 核验结果 |
|---|---|
| scene / PRN / channel | `F1023_V120_D0121_P2 / G11 / 0` |
| sampling rate | `10.23MHz`（`10,230,000 Hz`） |
| task id | `F1023_V120_D0121_P2__G11__ch0__nav_sage_v2` |
| request manifest | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\windows_wave2a1_v120_g11_20260809\execution_request.json` |
| request SHA-256 | `a43a5d483cadeb01337df96a1d539bad21e349b6cf338bf28f29cf17b76efd8c` |
| execution root | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260809T094948Z` |
| execution log | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260809T094948Z\batch_execution_log.csv` |
| batch report | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260809T094948Z\batch_execution_report.md` |
| task log | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260809T094948Z\task_logs\F1023_V120_D0121_P2__G11__ch0__nav_sage_v2.log` |
| status history | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260809T094948Z\status_history.jsonl` |
| wrapper receipt | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\windows_runner_receipts\windows_wave2a1_v120_g11_20260809_20260809T094931508Z` |
| MATLAB executable | `D:\Program Files\Matlab\bin\matlab.exe` |
| Windows identity | `TJ-CHANNEL\Jing_` |
| PowerShell | `7.6.4` |
| Python executable | `C:\Users\Jing_\AppData\Local\Programs\Python\Python312\python.exe` |
| output namespace | `E:\GNSS_Multipath_Project\scenes\F1023_V120_D0121_P2\sage_results\nav_sage_v2\G11` |

`batch_execution_log.csv` 记录了单任务 `completed`，开始时间 `2026-08-09T09:49:48.203417+00:00`，结束时间 `2026-08-10T05:27:20.390264+00:00`，耗时 `70652.187 s`，MATLAB 返回码 `0`，错误字段为空。batch report 为 `selected_rows=1`、`accepted_rows=1`、`rejected_rows=0`、`matlab_invoked=true`。

状态历史为：

```text
ready -> running  (preflight_passed)
running -> completed (matlab_exit_0_and_output_qa_pass, exit_code=0)
```

## 3. Windows wrapper、smoke 与 executor QA

wrapper environment receipt 和 execution receipt 均指向同一个 request、同一个任务和同一个输出 namespace。wrapper 使用正常 Windows 用户 `TJ-CHANNEL\Jing_`，不是 Codex sandbox 身份。

MATLAB startup smoke 结果：

- `smoke_exit_code=0`；
- `smoke_marker_present=true`，输出包含 `MATLAB_STARTUP_OK`；
- 开始 `2026-08-09T09:49:31.7368245+00:00`，结束 `2026-08-09T09:49:47.8395643+00:00`；
- smoke 耗时 `16.103 s`；
- MATLAB 文件版本 `25.1.0.2802752`（R2025a Update 1）。

Python executor 结果：

- `python_exit_code=0`；
- 开始 `2026-08-09T09:49:47.9809114+00:00`，结束 `2026-08-10T05:27:20.4487024+00:00`；
- executor 耗时 `70652.468 s`；
- `approved_task_completed=true`；
- result status 为 `completed`，task-level `exit_code=0`，错误字段为空。

任务日志在 Stage4 附近包含一条非致命 graphics/UI 乱码信息。它没有导致 MATLAB 或 executor 非零退出，也没有阻止 overview PNG 和 Stage4 输出落盘，因此记录为**非阻塞 warning**，不是 partial/failed 状态。

## 4. 输出目录与 21 个目标文件

目标目录为：

```text
E:\GNSS_Multipath_Project\scenes\F1023_V120_D0121_P2\sage_results\nav_sage_v2\G11
```

目录内恰好 21 个文件，全部存在且字节数大于 0：

| 文件 | 字节数 |
|---|---:|
| `run_context.mat` | 2,499 |
| `run_context.json` | 1,629 |
| `stage0_valid_symbols.csv` | 2,482,918 |
| `stage0_valid_40ms_windows.csv` | 2,285,429 |
| `stage0_nav_catalog.mat` | 948,743 |
| `doppler_sign.mat` | 1,252 |
| `stage1_nav_progress.mat` | 2,143,569 |
| `stage1_nav_fast_scan.csv` | 3,532,054 |
| `stage1_nav_fast_scan.mat` | 1,107,107 |
| `stage2_nav_progress.mat` | 75,346 |
| `stage2_model_orders.csv` | 37,851 |
| `stage2_selected_windows.csv` | 5,531 |
| `stage2_selected_paths.csv` | 4,694 |
| `stage2_nav_sage_L1_L4.mat` | 92,714 |
| `stage3_persistence.csv` | 516 |
| `stage3_reliable_centers.csv` | 98 |
| `stage3_nav_persistence.mat` | 2,691 |
| `stage4_joint_summary.csv` | 208 |
| `stage4_joint_paths.csv` | 162 |
| `stage4_nav_joint_100ms.mat` | 2,518 |
| `G11_nav_sage_overview.png` | 256,252 |

`stage3_reliable_centers.csv`、`stage4_joint_summary.csv` 和 `stage4_joint_paths.csv` 虽然是表头加空数据行，但文件本身非空，且与 Stage3/Stage4 的零事件结果一致。没有发现 partial、failed 或缺少目标文件的情况。

## 5. Stage0–Stage4 结果

| 阶段 | 实际结果 | QA 判断 |
|---|---|---|
| Stage0 | `15,224` 个有效 NAV symbols；`15,210` 个完整 40 ms 窗口 | 完成 |
| Stage1 | 扫描 `15,210` 个窗口；任务日志显示进度完成至 `15,210/15,210`；选出 `67` 个窗口（含邻居） | 完成；无中断记录 |
| Stage2 | `67 × 4 = 268` 行 L1–L4 模型评估；其中 `258` 行模型有效；最终选择 `67` 个窗口 | 完成 |
| Stage2 模型分布 | L1=`65`，L2=`1`，L3=`0`，L4=`1`；L≥2=`2`，L≥3=`1` | 高阶模型很少 |
| Stage3 | `stage3_persistence.csv` 有 `4` 条候选路径记录；可靠中心 `0` | 完成；全部未通过持续性门禁 |
| Stage4 | joint 结果 `0`；joint multipath 路径 `0`；confirmed multipath 事件 `0` | 完成后的有效空结果 |

### Stage3 候选持续性

4 条 persistence 记录均为 `matched_window_count=1`、`longest_consecutive_count=1`、`persistence_pass=0`、`match_pattern=00100`，因此没有进入 `stage3_reliable_centers.csv`：

- center window `9161`：selected L=`4`，3 条候选路径；
- center window `15065`：selected L=`2`，1 条候选路径。

这表示 Stage2 曾发现少量高阶/候选结构，但没有足够跨窗口持续性支持其成为可靠多径事件。

### Stage4 事件与路径参数

本次没有 confirmed multipath 事件，也没有 joint multipath 路径。因此不存在可报告的 `delay`、`Doppler offset`、`relative power`、`coherence` 或路径数量；这些字段对本次任务标记为 **N/A（Stage4 无路径行）**，不能从 Stage2 候选路径冒充 confirmed 事件参数。

## 6. 与 reference scene G11 的计算规模对照

对照来源为 `E:\GNSS_Multipath_Project\scenes\F1023_V70_D0117_P2\sage_results\reference_prn_analysis_report.md` 中的 reference G11 记录。两者不是同一 scene/raw IQ；reference G11 为 channel 5，本次 Wave-2A G11 为 channel 0，因此该比较用于规模和传播结果对照，不用于证明场景间物理等价。

| 指标 | reference G11 | Wave-2A G11 | 变化 |
|---|---:|---:|---:|
| NAV symbols | 1,177 | 15,224 | 约 12.93× |
| 40 ms / Stage1 扫描窗口 | 1,175 / 1,175 | 15,210 / 15,210 | 约 12.94× |
| Stage1 候选窗口 | 101 | 67 | 本次绝对数量更少 |
| Stage2 模型评估 | 404 | 268 | 本次更少 |
| Stage2 L1/L2/L3/L4 | 45 / 4 / 22 / 30 | 65 / 1 / 0 / 1 | 本次高阶模型明显更少 |
| Stage2 L≥2 / L≥3 | 56 / 52 | 2 / 1 | 本次更少 |
| Stage3 reliable centers | 7 | 0 | 本次为 0 |
| Stage4 joint results | 7 | 0 | 本次为 0 |
| confirmed events / paths | 1 / 1 | 0 / 0 | 本次无确认事件 |

### Stage1 异常长耗时

当前任务的完整 executor 耗时为 `70652.187 s`，即约 `19 h 37 min 32 s`。根据 Stage1 progress 文件和最终 Stage1 CSV 的 UTC 文件时间戳估计，Stage1 约从 `2026-08-09 09:51:03.940Z` 持续到 `2026-08-09 17:58:44Z`，约 **8 h 07 min 40 s**。该数值是基于输出文件时间戳的近似值，不是 pipeline 内置的精确 profiler 计时。

reference G11 同样按 artifact 时间戳估计，Stage1 约 `27 min 33 s`。因此本次 Stage1 墙钟时间约为 reference 的 `17.7×`，而窗口数量约为 `12.9×`；按窗口平均，本次也更慢。Stage2 当前约从 `17:59:52.560Z` 到 `2026-08-10 05:26:12Z`，约 `11 h 26 min 19 s`，reference 约 `40 min 23 s`。

可以确认的是：本次计算规模远大于 reference，且 Stage1/Stage2 确实耗时异常长；不能仅凭现有 QA 证据断言根因。当前场景的长 raw IQ、外部 raw 存储、磁盘 I/O、MATLAB 单线程/资源竞争或窗口数据特征都可能影响耗时，需另行 profiling。G11 已完整结束且返回码为 0，所以该问题目前是**运行效率/资源预算风险**，不是结果完整性失败。

## 7. 输出隔离与已有结果保护

以 execution log 的 MATLAB 任务时间窗 `2026-08-09T09:49:48.203417Z` 至 `2026-08-10T05:27:20.390264Z` 扫描整个 `scenes/**/sage_results/nav_sage_v2`：

- 时间窗内检测到的变更文件数：`21`；
- 目标 G11 目录内变更文件数：`21`；
- 目标目录之外的变更文件数：`0`。

因此本次写入只落在：

```text
scenes/F1023_V120_D0121_P2/sage_results/nav_sage_v2/G11
```

未发现写入 reference scene、`G06_nav_sage_v1`、Wave-A 的 G16/G25/G12，或其他 scene/PRN 的 `nav_sage_v2` 目录的证据。该结论限定于本次执行时间窗的文件时间扫描，不替代版本控制或全量内容哈希审计。

## 8. 研究解释与放行建议

本次 G11 在当前 scene 中是一个有效的无 confirmed-multipath 结果：Stage1 产生了 67 个候选窗口，Stage2 仅有 2 个 L≥2、1 个 L≥3 选择；Stage3 的 4 条候选路径均只在单窗口出现，未通过持续性；Stage4 因没有可靠中心而没有 joint 路径和 confirmed 事件。不能把“confirmed=0”解释为算法未运行，也不能把 Stage2 候选直接标为多径。

建议放行 Wave-2A 剩余任务，但遵守以下运行条件：

- 继续由 `TJ-CHANNEL\Jing_` 的正常 Windows PowerShell 7 执行；
- 每个 request 保持单任务、固定 channel、固定输出 namespace；
- 不并行启动 MATLAB；
- 每个任务开始前重新做 request SHA、输入完整性和输出冲突检查；
- 继续以 `exit_code=0`、21 个非空目标文件、Stage0–Stage4 链路和隔离扫描作为独立 QA 门禁；
- 对长场景预留至少一整天的墙钟时间，并保留 checkpoint，不因“看起来很慢”而删除中间结果；
- 在 Wave-2A 完成后再单独做 runtime profiling 和批量调度优化，不在本 QA 中修改 pipeline。

**最终判定：PASS；允许继续执行 Wave-2A 剩余任务，但必须按上述受控串行和逐任务 QA 条件进行。**
