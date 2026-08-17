# 10.23 MHz Full SAGE Production A1 G11 Post-run QA

审计日期：2026-08-13  
审计性质：只读 post-run QA；未重新运行 MATLAB/SAGE，未读取新的 raw IQ，未修改任何既有 artifact。

## 1. QA结论

`FULL_SAGE_PRODUCTION_TASK_STATUS: PASS`

首个 10.23 MHz full SAGE production task 已真实完成，Stage0–Stage4 输出链完整，且正式输出目录与 immutable request 一致。Stage4 中 3 个 joint result 满足当前 confirmed criterion，另有 5 个 `joint_valid=1` 但无多径路径的合法 zero-event joint result。

本次 QA 只把 Stage4 中同时满足以下条件的记录计为 confirmed event：

```text
joint_valid == 1
AND joint_multipath_count > 0
AND stage4_joint_paths.csv 中存在相同 center_window_id 且 is_multipath == 1 的路径
```

## 2. 任务、request与执行证据

| 字段 | 实际值 |
|---|---|
| scene | `F1023_V70_D0117_P4` |
| PRN | `G11` |
| tracking channel | `ch2` |
| sample rate | `10230000 Hz` |
| request | `dataset_generation_logs/batch_sage_execution_requests/production_10mhz_a1_d0117p4_g11_20260812/execution_request.json` |
| request SHA-256 | `08a8865eb89e9301d33df09cf77fbe94ef9d452f75c4141162d63dcc6ffc68d7` |
| production manifest SHA-256 | `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00` |
| execution log | `dataset_generation_logs/batch_sage_execution/batch_sage_execution_20260813T013710Z/batch_execution_log.csv` |
| execution status | `completed` |
| MATLAB subprocess exit code | `0` |
| Python executor exit code | `0` |
| task duration | `5078.854 s`（约 84.65 min） |
| Python wrapper duration | `5079.264 s` |
| task error | 空 |
| selected task count | `1` |
| rejected task count | `0` |

正常用户 wrapper receipt 位于：

`dataset_generation_logs/batch_sage_execution/windows_runner_receipts/windows_production_10mhz_a1_d0117p4_g11_20260812_20260813T013455024Z/`

其中 `environment_receipt.json` 记录：

- identity：`TJ-CHANNEL\\Jing_`
- PowerShell：`7.6.4`
- MATLAB：`D:\\Program Files\\Matlab\\bin\\matlab.exe`
- MATLAB file version：`25.1.0.2802752`
- startup marker：`MATLAB_STARTUP_OK`
- smoke exit code：`0`
- smoke marker：`true`
- working directory：`E:\\GNSS_Multipath_Project`

`execution_receipt.json` 记录 request SHA 一致、`python_exit_code=0`、`approved_task_completed=true`，并指向上述 batch execution log。wrapper 本身的独立数值 exit code 没有作为字段写入 receipt；本 QA 不从终端输出推断该数值，而以 receipt 的成功完成标志、Python exit code 0、batch status completed 和输出 QA 通过作为执行证据。

executor command preview 中包含 `Resume=true`。这只是当前 Pipeline 的 checkpoint 能力参数；本任务执行前 `preflight_receipt.json` 明确记录 `output_namespace_exists=false`，Stage0 日志显示从 `building` 开始而非 loaded/resumed，因此没有证据表明本次复用了已有输出目录。request 的 `new_only=true`、`resume_allowed=false` 保护策略仍以目标目录不存在为门禁。

## 3. 输出namespace与隔离检查

正式输出目录：

`scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G11/`

检查结果：

- 与 request 的 scene/PRN/channel/rate 一致；
- execution log 只有一个 task row，且只引用该 G11 输出目录；
- 执行前 preflight 记录目标目录不存在；
- global runner lock 执行前不存在，执行后无 active lock 遗留；
- `F1023_V70_D0117_P4/sage_results/nav_sage_v2` 当前只出现本次 `G11` 目录；
- 未指向 reference scene，未指向 `G06_nav_sage_v1`，未覆盖已有 reference/Wave-A/Wave-2A 输出；
- request、execution receipt、task log 均没有第二个批准任务。

`run_context.json` 核对结果：

| 字段 | 值 |
|---|---|
| `sceneId` | `F1023_V70_D0117_P4` |
| `prnLabel` | `G11` |
| `trackingChannel` | `2` |
| `samplingRateHz` | `10230000.0` |
| `outputDir` | `.../scenes/F1023_V70_D0117_P4/sage_results/nav_sage_v2/G11` |
| raw provenance | `E:\\AAGNSSSDR_input\\raw_data\\F1023_V70_D0117_P4.bin` |

QA 没有重新打开 raw；raw 路径和大小仅引用 request/preflight/运行时 `run_context` 记录。

## 4. Stage0–Stage4统计

| 阶段 | 实际结果 | QA解释 |
|---|---:|---|
| Stage0 valid NAV symbols | `895` | CSV 895 行 |
| Stage0 complete 40 ms windows | `893` | CSV 893 行，Stage0母集完整 |
| Stage1 scanned windows | `893` | `scan_valid=1` 为 893/893 |
| Stage1 selected/candidate windows | `110` | Pipeline log 明确为 including neighbors |
| Stage2 model-order rows | `440` | 110 个窗口 × L=1..4 |
| Stage2 model-valid rows | `364` | 其余无效模型不被当作 confirmed |
| Stage2 selected windows | `110` | CSV 110 行 |
| Stage2 final L=1/2/3/4 | `36 / 16 / 17 / 41` | 最终选择数量 |
| Stage2 L≥2 | `74` | 不是 confirmed multipath |
| Stage2 L≥3 | `58` | 仍不是 confirmed multipath |
| Stage3 persistence rows | `173` | persistence evidence |
| Stage3 persistence pass rows | `35` | 可靠性中间证据 |
| Stage3 reliable centers | `8` | CSV 8 行 |
| Stage4 joint rows | `8` | 与 reliable centers 对应 |
| Stage4 `joint_valid=1` | `8/8` | 结构上有效 |
| Stage4 `joint_multipath_count>0` | `3/8` | 候选 confirmed event |
| confirmed events | `3` | 严格 criterion 通过 |
| confirmed multipath paths | `3` | `is_multipath=1` 路径行 |

Stage1 CSV 中 `has_one_strong_residual` 和 `has_two_strong_residuals` 分别为 804 和 738 行；它们是全量扫描的 residual flags，不替代 pipeline 明确报告的 110 个 Stage2 candidate windows。

## 5. Confirmed event/path

| center window | time (s) | joint L | excess delay (samples) | excess delay (chips) | Doppler offset (Hz) | relative power (dB) | maximum coherence | path |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 526 | 57.2731826002 | 2 | 1.1 | 0.11 | -9.5025894889 | -9.9328578207 | 0.83454821898 | path 2 |
| 72 | 48.1931549365 | 2 | 1.7 | 0.17 | +49.6643020953 | -16.7107127458 | 0.00556188439 | path 2 |
| 73 | 48.2131550342 | 2 | 1.0 | 0.10 | +49.6643020953 | -14.6694586093 | 0.00608230841 | path 2 |

直接路径行（`is_multipath=0`）未计入 confirmed path。Stage4 `stage4_joint_paths.csv` 共 11 行，其中 3 行 `is_multipath=1`，8 行为 direct path。

Stage4 的另外 5 个 joint centers（524、525、224、652、654）均为 `joint_valid=1`、`joint_multipath_count=0`，其路径表只有 direct path；它们是合法 zero-event 结果，不是 Stage4 缺失或失败。

## 6. 文件完整性与hash

正式目录共 21 个文件，全部存在且非空。以下为本次 QA 对全部文件计算的 SHA-256：

| 文件 | bytes | SHA-256 |
|---|---:|---|
| `run_context.mat` | 2510 | `34a6ab918aa728207c7acb884ec1f61e17c03ebbf4f93bfd305c15162cb3fa21` |
| `run_context.json` | 1609 | `98a42978dc9fb6d91ce8bcbeb3807913b3876920b65f6f40d4705bfbe736921f` |
| `stage0_valid_symbols.csv` | 142281 | `f5fc672efb901c8785ed64429c6db4b8d9ca99098d8f9a57efebc821ef6810a2` |
| `stage0_valid_40ms_windows.csv` | 130082 | `bfad47636683cf3a0ae1d6fe3e38779bdf2174badae0b0b9cada6aea09016312` |
| `stage0_nav_catalog.mat` | 66240 | `e075a469579defbbf62098f8dc06ea2ae7e6285ae4883902d0640fa0134e35ec` |
| `doppler_sign.mat` | 1251 | `344e180f23cbf2c31c0b207b04bd513d32d6b92d4bcef3fa586841404d293d68` |
| `stage1_nav_progress.mat` | 128233 | `58b2b4b76bff2967aafc54d2596de7ac54db0ed09675d3d7bf30818ea6153d8f` |
| `stage1_nav_fast_scan.csv` | 205762 | `196dbb73ef939b0a5ef3c16f1e4e9f1932a99838a49838fb8a424a441f44702f` |
| `stage1_nav_fast_scan.mat` | 75254 | `8636734f45e861ca390b4ef0b23b5ef1e3c250608e3c276eb5fade0d62f8899e` |
| `stage2_nav_progress.mat` | 121884 | `19494c64001f95f96e7287ea2533fa6a190a27d7014fe81f0788abef2213d665` |
| `stage2_model_orders.csv` | 61666 | `36b896645cde27e540adc4a618a753372ea31a744fb89e58d1496546db0b58a5` |
| `stage2_selected_windows.csv` | 12125 | `286029e197e25fcc617fdf38ca0462b1315984dd171cd5d85289f01364162a53` |
| `stage2_selected_paths.csv` | 25416 | `4d665c2ba698d367100c0a115fe68ee477446d59a241ce19b51409068d432e16` |
| `stage2_nav_sage_L1_L4.mat` | 155988 | `8d19aabd732acd0fec6c72f5d7f55450b53b0138849dcd2ec66df04e08a79eb0` |
| `stage3_persistence.csv` | 13490 | `46de0a900152e274b67993d38d217bd8dd2c0015df30bca7ece23d8afa5df710` |
| `stage3_reliable_centers.csv` | 336 | `415e6c0f851637e28452d9b15158c623990a0e263fe65ef68448aedabb0b2c65` |
| `stage3_nav_persistence.mat` | 6823 | `d861505b8f28d41629d1084ff13336b6ab9387328fd90442ff10ea8e34cf7517` |
| `stage4_joint_summary.csv` | 943 | `3faf642d8d4e0d7b547c8b8b382a927703feeef08a2943e823d07ed2eee283c0` |
| `stage4_joint_paths.csv` | 704 | `62b6bae3f1d1fe3b61f8218048bd3c5e2faf8ade9a2600399e2b6acfebcc7c8` |
| `stage4_nav_joint_100ms.mat` | 11787 | `49ef029975831eceae5eaba521e825f5e69469e1552f040bcd533f41bf6e7d8f` |
| `G11_nav_sage_overview.png` | 288806 | `2e60c3e5cb0411fc6574e79529ddbcbf601af68f6f19debfe9d7fbe3e274d002` |

## 7. 后续生产状态

首个正式 10.23 MHz production task 已完成并通过独立 QA。可以考虑 Batch A 的下一个任务，但必须重新生成/审核独立 immutable request，重新执行 preflight，并继续由正常用户 wrapper 串行执行；不得因为本次 PASS 自动启动第二个任务。

本 QA 不建立 event database、不更新统计模型、不改变 production manifest，也不放行 20.46 MHz、raw-coarse、sampling 或 v3 路线。

### Handoff impact

- Engineering handoff update required: yes
- Paper handoff update required: yes

