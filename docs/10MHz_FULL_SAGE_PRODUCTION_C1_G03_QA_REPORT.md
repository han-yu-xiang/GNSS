# 10 MHz Full SAGE Production C1 G03 QA Report

## QA scope and conclusion

This is an independent, read-only post-run QA of the completed Commander-authorized canary task:

- Scene: `F1023_V120_D0121_P2`
- PRN: `G03`
- Tracking channel: `ch2` (channel `2`)
- Sample rate: `10,230,000 Hz` (10.23 MHz)
- QA conclusion: **PASS**
- Production result classification: `PASS_NO_CONFIRMED_MULTIPATH`

The QA did not rerun MATLAB/SAGE, reopen or process raw IQ, or modify the production output. The production execution was performed by the approved normal-user Windows wrapper using the immutable request below.

## 1. Execution verification

| Item | Value |
|---|---|
| Request manifest | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution_requests\production_10mhz_c1_d0121p2_g03_20260818\execution_request.json` |
| Request SHA-256 | `06acb9ff1634c8b248ed6a46a63bf2e0bee8934b61f8de61ce56c11a56f5dc64` |
| Request ID | `windows_production_10mhz_c1_d0121p2_g03_20260818` |
| Production manifest SHA-256 | `77c20c0ed6c84fa0348db429948a8bd4900b2e8d86a6d8843b159b9a7a35cf00` |
| Approved scope | `F1023_V120_D0121_P2/G03/ch2/10230000 Hz` |
| Execution policy | `new_only=true`, `resume_allowed=false`, `max_parallel_matlab=1` |
| Execution log | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260818T110255Z\batch_execution_log.csv` |
| Status history | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260818T110255Z\status_history.jsonl` |
| Task log | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\batch_sage_execution_20260818T110255Z\task_logs\F1023_V120_D0121_P2__G03__ch2__nav_sage_v2.log` |

The executor recorded exactly one approved task with `status=completed`, `exit_code=0`, an empty error message, and the fixed G03 output namespace. Status history records `ready -> running` after preflight and `running -> completed` with reason `matlab_exit_0_and_output_qa_pass`. The recorded MATLAB command contains explicit `Resume=false`.

### Environment and receipt

| Item | Value |
|---|---|
| Environment receipt | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\windows_runner_receipts\windows_production_10mhz_c1_d0121p2_g03_20260818_20260818T110245152Z\environment_receipt.json` |
| Execution receipt | `E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\windows_runner_receipts\windows_production_10mhz_c1_d0121p2_g03_20260818_20260818T110245152Z\execution_receipt.json` |
| Windows identity | `TJ-CHANNEL\Jing_` |
| PowerShell | `7.6.4` |
| MATLAB | `D:\Program Files\Matlab\bin\matlab.exe`, file version `25.1.0.2802752` |
| MATLAB startup smoke | marker present, exit code `0` |
| Python executor exit code | `0` |
| Task exit code | `0` |
| Task duration | `2073.646 s` (about `34.56 min`) |

## 2. Output namespace and file integrity

The approved output is exactly:

`E:\GNSS_Multipath_Project\scenes\F1023_V120_D0121_P2\sage_results\nav_sage_v2\G03\`

The output namespace was absent before execution and is not a protected reference or G16 namespace. It now contains all 21 expected files, each non-empty. `run_context.json` independently matches scene `F1023_V120_D0121_P2`, PRN `G03`, channel `2`, sampling rate `10230000`, and the approved output directory.

## 3. Stage statistics and structural QA

| Stage | QA statistic | Observed value |
|---|---|---:|
| Stage0 | valid NAV symbols | 232 |
| Stage0 | complete 40 ms windows | 230 |
| Stage1 | scanned windows | 230 |
| Stage2 | model-order evaluation rows | 384 (`96 x 4`) |
| Stage2 | final selected windows | 96 |
| Stage2 | selected path rows | 142 |
| Stage3 | persistence rows | 46 |
| Stage3 | reliable centers | 8 |
| Stage4 | joint summary rows | 8 |
| Stage4 | `joint_valid=1` rows | 8 / 8 |

Independent structural checks passed:

- Stage0 window IDs are unique.
- Stage1 window IDs are unique and cover the Stage0 window-ID set.
- Stage2 contains four model-order rows for each of the 96 selected windows.
- Stage3 reliable center IDs are unique.
- Stage4 center IDs are a subset of Stage3 reliable centers.
- Stage4 path center IDs exactly match Stage4 summary center IDs.
- The sum of Stage4 `joint_selected_L` equals the 8 Stage4 path rows.
- All 21 expected output files are present and non-empty.

## 4. Confirmed event/path check

The strict operational confirmed criterion is:

```text
joint_valid == 1
AND joint_multipath_count > 0
AND stage4_joint_paths.csv contains is_multipath == 1
```

Observed values:

- `joint_valid=1`: 8 rows
- `joint_multipath_count>0`: 0 rows
- Stage4 path rows: 8
- Stage4 `is_multipath=1` path rows: 0
- Confirmed multipath events: **0**
- Confirmed multipath paths: **0**

This is a complete, valid zero-confirmed-event production output under the current Stage4 criterion. It is not a scientific LOS conclusion, and it does not convert Stage2 or Stage3 candidates into confirmed multipath.

## 5. Artifact hashes

| File | Bytes | SHA-256 |
|---|---:|---|
| `doppler_sign.mat` | 1246 | `be47d9614ede0c138e6f8117f375ff80acd84f59636c05a333cddbeb8b1f3351` |
| `G03_nav_sage_overview.png` | 261294 | `d9bd7d25794c69b08ad125203b7b254ad20e67f55c6cd5e3fcc9b7a689568929` |
| `run_context.json` | 1628 | `9da122e853f70952dc12427d290e1406ab02ee326bc450945563ed7beb1f89b6` |
| `run_context.mat` | 2493 | `d003d6dc533bc43c6f5530d997f3b234b5ac809cb0b0f881a91c88de4660fcb7` |
| `stage0_nav_catalog.mat` | 19188 | `894fcbe81af8d96d029cf8f23eb3d42943e34e021369a853705050081baa1056` |
| `stage0_valid_40ms_windows.csv` | 33771 | `d12324a40db7d63df62b260040213b688966c72b4c0d905781226ff3fa44e578` |
| `stage0_valid_symbols.csv` | 37464 | `97467e960603e162fa54fce9a449994d9027d6960eaa28d6fe7b26b5b34c9aa2` |
| `stage1_nav_fast_scan.csv` | 53585 | `88fd33cf3999b72703f484ebcd9624f203a3c6a78f748eb5570fdc366fa66711` |
| `stage1_nav_fast_scan.mat` | 20184 | `864e291a9bd5ad226afe57c4e96b2c74c6e444ccaf186b01b0a5a22c5364805c` |
| `stage1_nav_progress.mat` | 34274 | `b6d19e199c0d54cfe6d74236a4ddcaf4ccfe0821a4e8eeeb54dbf77bd1b0c994d` |
| `stage2_model_orders.csv` | 54191 | `3340c4bb8dd314187cf97120087fbe7bd87aa5ce9e3b99833b4dc15ae74ec887` |
| `stage2_nav_progress.mat` | 106669 | `a22c05ff26a5033e0194ed442fa75bc7d0bd7ed741ed00e1eb203a6ca263b3d1` |
| `stage2_nav_sage_L1_L4.mat` | 132374 | `08e2ac74f98768cb5aa69bd21a82031c25640c034aff5c9feae0a29fde9c2776` |
| `stage2_selected_paths.csv` | 10820 | `e8e8594d30bcc46ec3aee09921088c31c05596bcf569e699362ee0304237f9e1` |
| `stage2_selected_windows.csv` | 9582 | `74da0c9ef3ef13f743c28f31ea8090bba91a3f949d7a33d242f842659a1b8efe` |
| `stage3_nav_persistence.mat` | 4187 | `72ea446c9c5b654971ef9b645f7af99305f3035b25b094ca2b951bcb59af8580` |
| `stage3_persistence.csv` | 3731 | `47df73329a3475d05e4e138cff722034aa7156f88f9f7189caa9b95f516ab180` |
| `stage3_reliable_centers.csv` | 333 | `e697139c9229e38da8154eed4435e8016f06a6a7dc2e3f197785a338f80d6728` |
| `stage4_joint_paths.csv` | 474 | `176568453825a02cd15883bc2b85910de0a0290eb2751e32c68e75be5c868e2c` |
| `stage4_joint_summary.csv` | 800 | `527fbb1fb1da1b356018b6d49c37334764fad734fad3a98c07e3cb4b3f2c27cc` |
| `stage4_nav_joint_100ms.mat` | 11538 | `f1b04901a50bc9a8ab93a0aaeeb13549e64b9a37cb680d54aeedd1767610d14b` |

## 6. Decision and handoff impact

The G03 canary is accepted as a completed, QA-passed production task with zero confirmed multipath events under the strict current criterion. This result releases continuation of the frozen 59-task eligible queue, subject to one independent immutable request, normal-user wrapper execution, and QA per task. The manifest and production source remain unchanged. No event database, statistical model, VTC artifact, Rain/Darkroom artifact, or 20.46 MHz task was modified or authorized by this QA.

Handoff impact: Engineering and Mainline Commander handoffs require a current-state update; Paper handoff does not require a scientific update for this zero-confirmed canary result.

## Scope declaration

- raw IQ read/processing during QA: **no**
- MATLAB/SAGE during QA: **no**
- production manifest modification: **no**
- protected output modification: **no**
